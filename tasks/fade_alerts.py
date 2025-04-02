import asyncio
from datetime import datetime, timedelta # Added timedelta
from typing import List, Dict, Optional, Tuple
from logging_setup import logger
# Imports are already correct from the previous attempt. No changes needed here.
from db.connection import get_nba_collection, get_ncaab_collection, get_fade_alerts_collection
from db.game_repo import get_game_by_id
from db.alert_repo import (
    get_pending_fade_alerts, update_fade_alert_result, get_fade_alert_subscribers,
    get_fade_alerts_since, update_fade_performance_stats, store_fade_alert
)
from db.utils import get_eastern_time_date
from utils.game_processing import find_fade_opportunities, get_spread_info # Use new function
from utils.formatters import format_fade_alert # Removed calculate_fade_rating for now
from utils.game_processing import determine_winner # Corrected import location

async def update_fade_alerts():
    """Update status of existing fade alerts for completed games."""
    logger.info("Updating status of fade alerts for completed games...")
    try:
        date, _ = get_eastern_time_date() # Already correct
        
        # Get all pending fade alerts from database (run sync db call in executor)
        loop = asyncio.get_running_loop()
        pending_alerts = await loop.run_in_executor(None, get_pending_fade_alerts) # Already correct
        if not pending_alerts:
            logger.info("No pending fade alerts to update.")
            return
            
        logger.info(f"Found {len(pending_alerts)} pending fade alerts to check.")
        
        # Process them in small batches to avoid overloading
        updated_count = 0
        for alert in pending_alerts:
            try:
                # Extract needed information from the alert
                game_id = alert.get('game_id')
                sport = alert.get('sport')
                market = alert.get('market')
                faded_outcome_label = alert.get('faded_outcome_label')
                alert_id = alert.get('_id') # Needed for update and logging

                if not all([game_id, sport, market, faded_outcome_label, alert_id]):
                    logger.warning(f"Incomplete alert data for ID {alert_id}: Missing required fields. Marking as 'error'.")
                    # Attempt to update status to 'error' to prevent reprocessing
                    try:
                        # Use the correct function name: update_fade_alert_result
                        await loop.run_in_executor(None, lambda: update_fade_alert_result(alert_id, "error")) # Already correct
                    except Exception as update_err:
                         logger.error(f"Failed to update status to 'error' for incomplete alert {alert_id}: {update_err}")
                    continue

                # Get latest game data (run sync db call in executor)
                # Ensure game_repo is imported if not already
                collection = get_nba_collection() if sport == "nba" else get_ncaab_collection() # Already correct
                game = await loop.run_in_executor(None, lambda: get_game_by_id(collection, game_id)) # Already correct

                if not game:
                    logger.warning(f"Game {game_id} not found for alert update (Alert ID: {alert_id}).")
                    # Consider setting status to 'error' or 'cancelled' if game consistently not found?
                    continue

                # Check if game is completed
                game_status = game.get('status', '').lower()
                if game_status not in ['complete', 'closed', 'final']:
                    continue  # Game not finished yet, skip update for now

                # --- Determine Fade Result based on Market ---
                fade_result: Optional[bool] = None
                if market == 'Spread':
                    fade_result = determine_spread_fade_result(game, alert)
                elif market == 'Total':
                    fade_result = determine_total_fade_result(game, alert)
                elif market == 'Moneyline':
                    fade_result = determine_moneyline_fade_result(game, alert)
                else:
                    logger.warning(f"Unknown market type '{market}' for alert ID {alert_id}")
                    continue # Skip if market is unknown

                # --- Update Status ---
                new_status = None
                if fade_result is True:
                    new_status = "won"
                elif fade_result is False:
                    new_status = "lost"
                # If fade_result is None (push or error), keep status as 'pending'

                if new_status:
                    # Assuming update_fade_alert_status was a typo for update_fade_alert_result
                    success = await loop.run_in_executor(None, lambda: update_fade_alert_result(alert_id, new_status)) # Already correct
                    if success:
                        updated_count += 1
                        logger.info(f"Updated alert {alert_id} status to {new_status}")
                        # Optional: Send notification ONLY if status was successfully updated
                        # TODO: Update notify_fade_alert_result signature if needed
                        # await notify_fade_alert_result(game, alert, new_status)
                    else:
                         logger.error(f"Failed to update status for alert {alert_id}")
                else:
                    logger.info(f"No status update needed for alert {alert_id} (Result: Push or Error)")

            except Exception as e:
                logger.error(f"Error updating fade alert {alert.get('_id')}: {e}", exc_info=True)
                
        logger.info(f"Updated {updated_count} fade alert statuses.")
        
        # Run performance analysis 
        await analyze_fade_performance()
        
    except Exception as e:
        logger.error(f"Error in update_fade_alerts: {e}", exc_info=True)

async def notify_fade_alert_result(game: dict, alert: dict):
    """Notify subscribed users about fade alert results based on the updated alert data."""
    try:
        loop = asyncio.get_running_loop()
        game_id = alert.get('game_id')
        sport = alert.get('sport')
        result_status = alert.get('status') # Should be 'won' or 'lost' at this point
        alert_id = alert.get('_id', 'UNKNOWN') # For logging

        if not game_id or not sport or result_status not in ['won', 'lost']:
             logger.warning(f"Cannot notify for alert {alert_id}: Missing data or invalid status '{result_status}'.")
             return

        # Get subscribed users for this game/alert (run sync db call in executor)
        # Assuming subscription is still based on game_id and sport for now
        subscribers = await loop.run_in_executor(None, lambda: get_fade_alert_subscribers(game_id, sport)) # Already correct
        if not subscribers:
            return  # No subscribers to notify

        # Format the alert message using the new formatter
        # Pass the alert dict itself as the 'opportunity' argument
        alert_msg = format_fade_alert(
            game=game,
            opportunity=alert,
            result_status=result_status
        )
        if not alert_msg:
            logger.warning(f"Failed to format result message for alert {alert_id}")
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
                logger.error(f"Failed to send fade result to user {user_id} for alert {alert_id}: {e}")

    except Exception as e:
        logger.error(f"Error in notify_fade_alert_result for alert {alert_id}: {e}", exc_info=True)

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

# --- Result Determination Functions ---

def determine_spread_fade_result(game: dict, alert: dict) -> Optional[bool]:
    """
    Determine if the fade against the spread was successful.
    Success means the team/side being faded *did not* cover their spread.

    Args:
        game: The completed game data dictionary.
        alert: The fade alert dictionary containing market, faded_outcome_label, faded_value.

    Returns:
        True if the fade won (faded side didn't cover), False if the fade lost, None if push or error.
    """
    try:
        faded_outcome = alert.get('faded_outcome_label') # 'Home' or 'Away'
        spread_value = alert.get('faded_value') # The spread of the faded side

        if faded_outcome not in ['Home', 'Away'] or spread_value is None:
            logger.warning(f"Invalid spread alert data for game {game.get('id')}: {alert.get('_id')}")
            return None

        # Get final score
        boxscore = game.get('boxscore', {})
        home_score = boxscore.get('total_home_points')
        away_score = boxscore.get('total_away_points')
        home_team_id = game.get('home_team_id') or game.get('home_team', {}).get('id')
        away_team_id = game.get('away_team_id') or game.get('away_team', {}).get('id')

        if None in [home_score, away_score, home_team_id, away_team_id]:
            logger.warning(f"Missing score or team ID data for game {game.get('id')}")
            return None

        # Calculate actual margin relative to the faded team
        if faded_outcome == 'Home':
            actual_margin = home_score - away_score
        else: # Fading Away team
            actual_margin = away_score - home_score

        # Did the faded team cover their spread?
        # Margin > Spread Value means they covered (e.g., -7 > -7.5, or +3 > +2.5)
        # Margin == Spread Value is a push
        if actual_margin == spread_value:
            logger.info(f"Spread push detected for game {game.get('id')}, alert {alert.get('_id')}")
            return None # Push

        faded_team_covered = actual_margin > spread_value

        # Fade wins if the faded team did NOT cover
        return not faded_team_covered

    except Exception as e:
        logger.error(f"Error determining spread fade result for alert {alert.get('_id')}: {e}", exc_info=True)
        return None

def determine_total_fade_result(game: dict, alert: dict) -> Optional[bool]:
    """
    Determine if the fade against the total was successful.
    Success means the actual result was the opposite of the faded outcome.

    Args:
        game: The completed game data dictionary.
        alert: The fade alert dictionary containing market, faded_outcome_label, faded_value.

    Returns:
        True if the fade won, False if the fade lost, None if push or error.
    """
    try:
        faded_outcome = alert.get('faded_outcome_label') # 'Over' or 'Under'
        total_line = alert.get('faded_value') # The total line being faded

        if faded_outcome not in ['Over', 'Under'] or total_line is None:
            logger.warning(f"Invalid total alert data for game {game.get('id')}: {alert.get('_id')}")
            return None

        # Get final score
        boxscore = game.get('boxscore', {})
        home_score = boxscore.get('total_home_points')
        away_score = boxscore.get('total_away_points')

        if None in [home_score, away_score]:
            logger.warning(f"Missing score data for game {game.get('id')}")
            return None

        actual_total = home_score + away_score

        # Check for push
        if actual_total == total_line:
            logger.info(f"Total push detected for game {game.get('id')}, alert {alert.get('_id')}")
            return None # Push

        # Determine success
        if faded_outcome == 'Over':
            # Fade wins if actual total is UNDER the line
            return actual_total < total_line
        elif faded_outcome == 'Under':
            # Fade wins if actual total is OVER the line
            return actual_total > total_line
        else:
            return None # Should not happen

    except Exception as e:
        logger.error(f"Error determining total fade result for alert {alert.get('_id')}: {e}", exc_info=True)
        return None

def determine_moneyline_fade_result(game: dict, alert: dict) -> Optional[bool]:
    """
    Determine if the fade against the moneyline was successful.
    Success means the opponent of the faded team won the game.

    Args:
        game: The completed game data dictionary.
        alert: The fade alert dictionary containing market, faded_outcome_label.

    Returns:
        True if the fade won, False if the fade lost, None if winner unclear or error.
    """
    try:
        faded_outcome = alert.get('faded_outcome_label') # 'Home' or 'Away'

        if faded_outcome not in ['Home', 'Away']:
            logger.warning(f"Invalid moneyline alert data for game {game.get('id')}: {alert.get('_id')}")
            return None

        # Determine the actual winner
        # Use the determine_winner function which handles different game states/data points
        winner_data = determine_winner(game) # Assuming determine_winner is imported
        if not winner_data:
            logger.warning(f"Could not determine winner for game {game.get('id')} for ML fade alert {alert.get('_id')}")
            return None # Cannot determine winner

        winning_team_id = winner_data.get('id')
        home_team_id = game.get('home_team_id') or game.get('home_team', {}).get('id')
        away_team_id = game.get('away_team_id') or game.get('away_team', {}).get('id')

        if not home_team_id or not away_team_id:
             logger.warning(f"Missing team IDs in game {game.get('id')}")
             return None

        # Determine success
        if faded_outcome == 'Home':
            # Fade wins if Away team won
            return winning_team_id == away_team_id
        elif faded_outcome == 'Away':
            # Fade wins if Home team won
            return winning_team_id == home_team_id
        else:
            return None # Should not happen

    except Exception as e:
        logger.error(f"Error determining moneyline fade result for alert {alert.get('_id')}: {e}", exc_info=True)
        return None



async def analyze_fade_performance():
    """Analyze historical fade performance and update statistics."""
    try:
        loop = asyncio.get_running_loop()
        # Get recent fade alerts (last 30 days) (run sync db call in executor)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        fade_alerts = await loop.run_in_executor(None, lambda: get_fade_alerts_since(thirty_days_ago)) # Already correct
        
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
        await loop.run_in_executor(None, lambda: update_fade_performance_stats(performance_data)) # Already correct
        logger.info(f"Updated fade performance stats: {win_percentage:.1f}% win rate ({won}/{won+lost})")
        
    except Exception as e:
        logger.error(f"Error analyzing fade performance: {e}", exc_info=True)

async def process_new_fade_alerts(games: list, sport: str) -> List[str]:
    """
    Process new games for potential fade alerts, store them,
    and return a list of formatted alert messages.
    """
    fade_alert_messages = [] # Changed variable name and type hint
    logger.info(f"[process_new_fade_alerts] Received {len(games)} games to process.") # Added log
    for i, game in enumerate(games): # Added index
        game_id_log = game.get('game_id', 'N/A') # Use consistent game_id logging
        try:
            status = game.get('status', 'UNKNOWN_STATUS').lower()
            # --- Add Diagnostic Logging ---
            logger.info(f"[process_new_fade_alerts] Processing game {i+1}/{len(games)} (ID: {game_id_log}) with status: '{status}'")
            # --- End Diagnostic Logging ---

            # Skip completed games
            if status in ['complete', 'closed', 'final']:
                logger.info(f"[process_new_fade_alerts] Skipping game {game_id_log} due to status '{status}'.") # Added log
                continue
                
            # --- This part should now be reached if status is not complete ---
            logger.info(f"[process_new_fade_alerts] Game {game_id_log} status OK. Calling find_fade_opportunities...") # Added log
            potential_opportunities = find_fade_opportunities(game, sport)

            if not potential_opportunities:
                logger.info(f"[process_new_fade_alerts] find_fade_opportunities returned no opportunities for game {game_id_log}.") # Added log
                continue # No opportunities found for this game

            loop = asyncio.get_running_loop() # Get loop once per game if opportunities exist
            current_date_str = get_eastern_time_date()[0] # Already correct

            for opp_index, opp in enumerate(potential_opportunities): # Add index for logging
                logger.debug(f"Processing opportunity {opp_index + 1}/{len(potential_opportunities)} for game {game_id_log}...")
                try:
                    # Prepare data for storage and checking
                    # Map faded_outcome_label to a more structured representation if needed
                    # For now, using the label directly.
                    # Prepare data for storage based on the new opportunity structure
                    # Prepare data for storage based on the new opportunity structure
                    alert_data = {
                        'game_id': opp['game_id'],
                        'sport': opp['sport'],
                        'date': current_date_str,
                        'market': opp['market'],
                        'faded_outcome_label': opp['faded_outcome_label'],
                        'faded_value': opp.get('faded_value'), # Spread/Total value
                        'odds': opp['odds'], # Odds of the faded outcome
                        'implied_probability': opp['implied_probability'], # Calculated IP
                        'tickets_percent': opp['T%'],
                        'money_percent': opp['M%'],
                        'rating': opp['rating'], # Added rating
                        'reason': opp['reason'], # New reason based on T% vs IP
                        'status': 'pending',
                        'created_at': datetime.now() # Use non-timezone aware for consistency? Check DB storage.
                        # Removed threshold_used, team_id
                    }

                    # Check if this specific fade opportunity already exists
                    # Check if a PENDING alert already exists
                    existing_alert = await loop.run_in_executor(
                        None,
                        lambda: get_fade_alerts_collection().find_one({
                            "game_id": alert_data['game_id'],
                            "market": alert_data['market'],
                            "faded_outcome_label": alert_data['faded_outcome_label'],
                            "date": current_date_str,
                            "status": "pending" # Check specifically for pending status
                        })
                    )
                    logger.info(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: Checked for existing PENDING alert. Found: {'Yes' if existing_alert else 'No'}")

                    alert_to_format = None # Initialize variable to hold the alert data for formatting

                    if existing_alert:
                        # Use the existing alert data for formatting
                        alert_to_format = existing_alert
                        logger.info(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: Using existing alert {existing_alert.get('_id')}. alert_to_format set.")
                    
                    elif not existing_alert: # Only try to store if no existing PENDING alert was found
                        # Store the new fade alert and capture the result
                        def store_wrapper(data):
                            try:
                                # Ensure 'created_at' is a datetime object before storing
                                data['created_at'] = datetime.now()
                                return store_fade_alert(**data)
                            except Exception as e:
                                logger.error(f"[store_wrapper] Exception inside executor: {e}", exc_info=True)
                                return False # Indicate failure

                        store_future = loop.run_in_executor(
                            None,
                            store_wrapper, # Call the wrapper
                            alert_data # Pass data as argument to wrapper
                        )
                        store_successful = await store_future # Explicitly await the future
                        logger.info(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: Store attempt result: {store_successful}")

                        if store_successful:
                            # Use the newly created alert_data for formatting
                            alert_to_format = alert_data
                            logger.info(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: Stored new alert. alert_to_format set.")
                        else:
                            logger.error(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: Failed to store alert. alert_to_format remains None.")

                    # Format the message if we have an alert (either existing or newly stored)
                    if alert_to_format:
                        logger.info(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: Attempting to format message using alert data: {alert_to_format.get('_id', 'NEW')}...")
                        # Use alert_to_format which contains either the existing doc or the new data
                        formatted_message = format_fade_alert(game=game, opportunity=alert_to_format, result_status="pending")
                        logger.info(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: Formatting result: type={type(formatted_message).__name__}, value='{str(formatted_message)[:100]}...'")
                        if formatted_message:
                            fade_alert_messages.append(formatted_message)
                        else:
                             logger.warning(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: Formatting failed. Message not appended.")
                    else: # Add this else block
                        logger.warning(f"GAME {alert_data['game_id']} OPP {opp_index + 1}: No alert to format (neither existing nor newly stored). Message not appended.")

                except Exception as inner_e:
                    logger.error(f"Error processing opportunity for game {game.get('id')}: {inner_e}", exc_info=True)
            # --- END NEW FADE LOGIC ---
        except Exception as e:
            logger.error(f"Error processing game for fade alerts: {e}", exc_info=True)
            
    return fade_alert_messages # Return the list of messages