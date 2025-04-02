import asyncio
from datetime import datetime, timedelta # Added timedelta
from typing import List, Dict, Optional, Tuple
from logging_setup import logger
import db
from db.connection import fade_alerts_collection # Import the collection
from db.alert_repo import store_fade_alert # Import the storage function
from utils.game_processing import get_bet_percentages, get_spread_info
from utils.formatters import format_fade_alert, calculate_fade_rating # Added calculate_fade_rating
from utils.game_processing import determine_winner # Corrected import location

async def update_fade_alerts():
    """Update status of existing fade alerts for completed games."""
    logger.info("Updating status of fade alerts for completed games...")
    try:
        date, _ = db.get_eastern_time_date() # Assuming this is okay as it might be quick/non-blocking
        
        # Get all pending fade alerts from database (run sync db call in executor)
        loop = asyncio.get_running_loop()
        pending_alerts = await loop.run_in_executor(None, db.get_pending_fade_alerts)
        if not pending_alerts:
            logger.info("No pending fade alerts to update.")
            return
            
        logger.info(f"Found {len(pending_alerts)} pending fade alerts to check.")
        
        # Process them in small batches to avoid overloading
        updated_count = 0
        for alert in pending_alerts:
            try:
                # Extract needed information 
                game_id = alert.get('game_id')
                sport = alert.get('sport')
                team_id = alert.get('team_id')
                
                if not all([game_id, sport, team_id]):
                    logger.warning(f"Incomplete alert data for ID {alert.get('_id')}")
                    continue
                    
                # Get latest game data (run sync db call in executor)
                collection = db.nba_collection if sport == "nba" else db.ncaab_collection
                game = await loop.run_in_executor(None, lambda: db.get_game_by_id(collection, game_id))
                
                if not game:
                    logger.warning(f"Game {game_id} not found for alert update.")
                    continue
                
                # Check if game is completed
                status = game.get('status', '').lower()
                if status not in ['complete', 'closed', 'final']:
                    continue  # Game not finished yet
                    
                # Determine the winner and if spread was covered
                winner_data = determine_winner(game)
                if not winner_data:
                    logger.warning(f"Could not determine winner for game {game_id}")
                    continue
                    
                winning_team_id = winner_data.get('id')
                winner_covered_spread = determine_spread_coverage(game, winning_team_id, team_id)
                # Update alert status (run sync db call in executor)
                new_status = "won" if winner_covered_spread else "lost"
                alert_id = alert.get('_id') # Get id first for lambda
                await loop.run_in_executor(None, lambda: db.update_fade_alert_status(alert_id, new_status))
                updated_count += 1
                
                
                # Optional: Send notification to subscribed users about the result
                await notify_fade_alert_result(game, sport, team_id, winner_covered_spread)
                
            except Exception as e:
                logger.error(f"Error updating fade alert {alert.get('_id')}: {e}", exc_info=True)
                
        logger.info(f"Updated {updated_count} fade alert statuses.")
        
        # Run performance analysis 
        await analyze_fade_performance()
        
    except Exception as e:
        logger.error(f"Error in update_fade_alerts: {e}", exc_info=True)

async def notify_fade_alert_result(game: dict, sport: str, faded_team_id: int, winner_covered_spread: bool):
    """Notify subscribed users about fade alert results."""
    try:
        loop = asyncio.get_running_loop()
        # Get subscribed users for this game/alert (run sync db call in executor)
        game_id = game.get('id') # Get id first for lambda
        subscribers = await loop.run_in_executor(None, lambda: db.get_fade_alert_subscribers(game_id, sport))
        if not subscribers:
            return  # No subscribers to notify
            
        # Format the alert message
        alert_msg = format_fade_alert(
            game=game,
            sport=sport,
            completed=True,
            winner_covered_spread=winner_covered_spread
        )
        if not alert_msg:
            return  # No message to send
            
        # Import bot here to avoid circular imports
        from bot import bot
        
        # Send to subscribers
        for user_id in subscribers:
            try:
                await bot.send_message(
                    user_id, 
                    alert_msg
                )
                await asyncio.sleep(0.1)  # Small delay between messages
            except Exception as e:
                logger.error(f"Failed to send fade result to user {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in notify_fade_alert_result: {e}", exc_info=True)

def determine_spread_coverage(game: dict, winning_team_id: int, faded_team_id: int) -> bool:
    """Determine if the fade was successful (if the team being faded did not cover the spread)."""
    try:
        # Get the spread value for the faded team
        spread_value_str, _ = get_spread_info(game, faded_team_id)
        if not spread_value_str:
            logger.warning(f"No spread info found for team {faded_team_id} in game {game.get('id')}")
            return None  # Can't determine
            
        # Convert spread to float
        try:
            spread_value = float(spread_value_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid spread value: {spread_value_str}")
            return None
            
        # Get final score
        boxscore = game.get('boxscore', {})
        if not boxscore:
            logger.warning(f"No boxscore found for game {game.get('id')}")
            return None
            
        home_team_id = game.get('home_team_id') or game.get('home_team', {}).get('id')
        away_team_id = game.get('away_team_id') or game.get('away_team', {}).get('id')
        
        if not home_team_id or not away_team_id:
            logger.warning(f"Missing team IDs in game {game.get('id')}")
            return None
            
        home_score = boxscore.get('total_home_points', 0)
        away_score = boxscore.get('total_away_points', 0)
        
        if home_score is None or away_score is None:
            logger.warning(f"Missing score data in game {game.get('id')}")
            return None
            
        # Calculate actual margin
        if faded_team_id == home_team_id:
            actual_margin = home_score - away_score
        else:
            actual_margin = away_score - home_score
            
        # Did the faded team cover their spread?
        # If spread is -5.5, team must win by 6+ to cover
        # If spread is +5.5, team must lose by 5 or less (or win) to cover
        faded_team_covered = actual_margin > spread_value
        
        # For a fade to be successful, we want the faded team to NOT cover
        return not faded_team_covered
        
    except Exception as e:
        logger.error(f"Error determining spread coverage: {e}", exc_info=True)
        return None

async def analyze_fade_performance():
    """Analyze historical fade performance and update statistics."""
    try:
        loop = asyncio.get_running_loop()
        # Get recent fade alerts (last 30 days) (run sync db call in executor)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        fade_alerts = await loop.run_in_executor(None, lambda: db.get_fade_alerts_since(thirty_days_ago))
        
        if not fade_alerts:
            logger.info("No fade alerts found for performance analysis.")
            return
            
        # Calculate performance metrics
        total = len(fade_alerts)
        won = sum(1 for alert in fade_alerts if alert.get('status') == 'won')
        lost = sum(1 for alert in fade_alerts if alert.get('status') == 'lost')
        pending = total - won - lost
        
        win_percentage = (won / (won + lost)) * 100 if (won + lost) > 0 else 0
        
        # Additional analysis by rating
        by_rating = {}
        for i in range(1, 6):  # 1-5 star ratings
            rating_alerts = [a for a in fade_alerts if a.get('rating') == i]
            rating_won = sum(1 for a in rating_alerts if a.get('status') == 'won')
            rating_lost = sum(1 for a in rating_alerts if a.get('status') == 'lost')
            
            if rating_won + rating_lost > 0:
                win_pct = (rating_won / (rating_won + rating_lost)) * 100
                by_rating[i] = {
                    'total': len(rating_alerts),
                    'won': rating_won,
                    'lost': rating_lost,
                    'pending': len(rating_alerts) - rating_won - rating_lost,
                    'win_percentage': win_pct
                }
        
        # By sport analysis
        by_sport = {}
        for sport in ['nba', 'ncaab']:
            sport_alerts = [a for a in fade_alerts if a.get('sport') == sport]
            sport_won = sum(1 for a in sport_alerts if a.get('status') == 'won')
            sport_lost = sum(1 for a in sport_alerts if a.get('status') == 'lost')
            
            if sport_won + sport_lost > 0:
                win_pct = (sport_won / (sport_won + sport_lost)) * 100
                by_sport[sport] = {
                    'total': len(sport_alerts),
                    'won': sport_won,
                    'lost': sport_lost,
                    'pending': len(sport_alerts) - sport_won - sport_lost,
                    'win_percentage': win_pct
                }
        
        # Save performance data
        performance_data = {
            'last_updated': datetime.now(),
            'total_alerts': total,
            'won': won,
            'lost': lost,
            'pending': pending,
            'win_percentage': win_percentage,
            'by_rating': by_rating,
            'by_sport': by_sport,
        }
        
        # Run sync db call in executor
        await loop.run_in_executor(None, lambda: db.update_fade_performance_stats(performance_data))
        logger.info(f"Updated fade performance stats: {win_percentage:.1f}% win rate ({won}/{won+lost})")
        
    except Exception as e:
        logger.error(f"Error analyzing fade performance: {e}", exc_info=True)

async def process_new_fade_alerts(games: list, sport: str) -> List[str]:
    """
    Process new games for potential fade alerts, store them,
    and return a list of formatted alert messages.
    """
    fade_alert_messages = [] # Changed variable name and type hint
    for game in games:
        try:
            # Skip completed games
            status = game.get('status', '').lower()
            if status in ['complete', 'closed', 'final']:
                continue
                
            # Process for fade alert
            alert = format_fade_alert(game, sport)
            if alert:
                # Extract details for storage
                home_team = game.get('home_team', {})
                away_team = game.get('away_team', {})
                home_id = home_team.get('id') or game.get('home_team_id')
                away_id = away_team.get('id') or game.get('away_team_id')
                
                if not home_id or not away_id:
                    continue
                    
                # Determine which team is being faded
                home_tickets, home_money = get_bet_percentages(game, home_id)
                away_tickets, away_money = get_bet_percentages(game, away_id)
                
                fade_team_id = None
                fade_tickets = None
                fade_money = None
                
                if home_tickets and home_money and home_tickets < 20 and home_money < 20:
                    fade_team_id = home_id
                    fade_tickets, fade_money = home_tickets, home_money
                elif away_tickets and away_money and away_tickets < 20 and away_money < 20:
                    fade_team_id = away_id
                    fade_tickets, fade_money = away_tickets, away_money
                    
                if fade_team_id and fade_tickets is not None and fade_money is not None:
                    # Calculate rating
                    # Import moved to top
                    rating = calculate_fade_rating(fade_tickets, fade_money)
                    
                    # Get spread info
                    spread_value_str, spread_odds_str = get_spread_info(game, fade_team_id)
                    spread_value = float(spread_value_str) if spread_value_str else None
                    
                    # Store in database
                    alert_data = {
                        'game_id': game.get('game_id') or game.get('id'),
                        'sport': sport,
                        'date': db.get_eastern_time_date()[0],
                        'team_id': fade_team_id,
                        'spread_value': spread_value,
                        'tickets_percent': fade_tickets,
                        'money_percent': fade_money,
                        'rating': rating,
                        'status': 'pending',
                        'created_at': datetime.now()
                    }
                    
                    # Store only if doesn't already exist (run sync db call in executor)
                    loop = asyncio.get_running_loop() # Get loop inside this async function
                    game_id_for_check = alert_data['game_id'] # Get vars for lambda
                    team_id_for_check = fade_team_id
                    # Check if alert already exists using find_one
                    existing = await loop.run_in_executor(
                        None,
                        lambda: fade_alerts_collection.find_one({
                            "game_id": game_id_for_check,
                            "team_id": team_id_for_check
                        })
                    )
                    
                    # The 'alert' variable here is the formatted message string from line 255
                    formatted_alert_message = alert
                    
                    if not existing:
                        # Run sync db call in executor, passing individual args
                        await loop.run_in_executor(
                            None,
                            lambda: store_fade_alert(
                                game_id=alert_data['game_id'],
                                sport=alert_data['sport'],
                                date=alert_data['date'],
                                team_id=alert_data['team_id'],
                                spread_value=alert_data['spread_value'],
                                tickets_percent=alert_data['tickets_percent'],
                                money_percent=alert_data['money_percent'],
                                rating=alert_data['rating'],
                                status=alert_data['status']
                            )
                        )
                        # Append the formatted message, not the raw data
                        fade_alert_messages.append(formatted_alert_message)
                        logger.info(f"Stored new {sport} fade alert for team {fade_team_id} in game {alert_data['game_id']}")
                
        except Exception as e:
            logger.error(f"Error processing game for fade alerts: {e}", exc_info=True)
            
    return fade_alert_messages # Return the list of messages