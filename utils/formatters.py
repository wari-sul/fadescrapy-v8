from typing import Optional, Dict, Tuple
from datetime import datetime
import logging
from logging_setup import logger
from utils.game_processing import get_bet_percentages, get_spread_info

def get_game_status_icon(status: str) -> str:
    """Returns appropriate icon for game status."""
    status_map = {
        "scheduled": "⏳ Scheduled",
        "inprogress": "🔴 LIVE",
        "complete": "✅ Completed",
        "closed": "✅ Final", # Often used interchangeably with complete
        "postponed": "⏰ Postponed",
        "cancelled": "❌ Cancelled",
        "suspended": "⏸️ Suspended",
        "delayed": "⏳ Delayed",
    }
    # Normalize status
    status_lower = status.lower().replace('_', '').replace('-', '')
    return status_map.get(status_lower, f"❓ {status.title()}") # Default with original status

def calculate_fade_rating(bet_percent: Optional[float], money_percent: Optional[float]) -> int:
    """Calculate fade rating (0-5 stars) based on betting percentages."""
    if bet_percent is None or money_percent is None:
        return 0  # Cannot calculate rating without data
        
    # NEW RATING SYSTEM
    # 5 Stars: Both <10%
    if bet_percent < 10 and money_percent < 10:
        return 5
        
    # 4 Stars: One <10%, the other <20%
    if (bet_percent < 10 and money_percent < 20) or (money_percent < 10 and bet_percent < 20):
        return 4
        
    # 3 Stars: Both <20%
    if bet_percent < 20 and money_percent < 20:
        return 3
        
    # Default fallback (shouldn't happen with our criteria)
    return 0

def format_game_info(game: dict, sport: str = "nba") -> str:
    """Format game information for display."""
    try:
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        if not home_team or not away_team:
            return "Invalid game data - missing team information"

        home_name = home_team.get('display_name', 'Home Team')
        away_name = away_team.get('display_name', 'Away Team')
        
        # Get status with icon
        status = game.get('status', 'unknown')
        status_display = get_game_status_icon(status)
        
        # Format game start time
        start_time_str = game.get('start_time')
        time_str = "Time not available"
        if start_time_str:
            try:
                start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                time_str = start_dt.strftime("%I:%M %p UTC")
            except ValueError:
                time_str = start_time_str
        
        # Get spread for both teams
        home_id = home_team.get('id') or game.get('home_team_id')
        away_id = away_team.get('id') or game.get('away_team_id')
        home_spread, home_odds = get_spread_info(game, home_id)
        away_spread, away_odds = get_spread_info(game, away_id)
        
        # Format spread info for display
        home_spread_str = f"{home_spread} ({home_odds})" if home_spread else "N/A"
        away_spread_str = f"{away_spread} ({away_odds})" if away_spread else "N/A"
        
        # Format based on game status
        if status.lower() in ['complete', 'closed']:
            # Show final score
            boxscore = game.get('boxscore', {})
            home_score = boxscore.get('total_home_points', '?')
            away_score = boxscore.get('total_away_points', '?')
            
            return (
                f"🏟️ <b>{away_name} @ {home_name}</b>\n"
                f"📊 <b>FINAL:</b> {away_name} {away_score} - {home_score} {home_name}\n"
                f"📈 Spread: {away_name} {away_spread_str} | {home_name} {home_spread_str}"
            )
        else:
            # Show scheduled game
            return (
                f"🏟️ <b>{away_name} @ {home_name}</b>\n"
                f"⏰ {time_str} - {status_display}\n"
                f"📈 Spread: {away_name} {away_spread_str} | {home_name} {home_spread_str}"
            )
            
    except Exception as e:
        logger.error(f"Error formatting game info: {e}", exc_info=True)
        return "Error formatting game information"

def format_fade_alert(game: dict, sport: str = "nba", completed: bool = False, winner_covered_spread: Optional[bool] = None) -> Optional[str]:
    """Format fade alert message based on game state."""
    try:
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        if not home_team or not away_team: return None

        # Correctly get team IDs from either 'id' field or directly from game
        home_id = home_team.get('id') or game.get('home_team_id')
        away_id = away_team.get('id') or game.get('away_team_id')
        if not home_id or not away_id: 
            logger.debug(f"Missing team IDs in game {game.get('id') or game.get('game_id')}")
            return None

        home_display = home_team.get('display_name', 'Home Team')
        away_display = away_team.get('display_name', 'Away Team')

        # Get betting percentages for both teams
        home_tickets, home_money = get_bet_percentages(game, home_id)
        away_tickets, away_money = get_bet_percentages(game, away_id)

        # Add debug logging
        logger.debug(f"Game {game.get('id') or game.get('game_id')}: Home ({home_id}): {home_tickets}%/{home_money}%, Away ({away_id}): {away_tickets}%/{away_money}%")

        # Check if we have valid betting data
        if None in (home_tickets, home_money, away_tickets, away_money):
            logger.debug(f"Missing betting data for game {game.get('id') or game.get('game_id')}")
            return None

        # NEW LOGIC: Identify fade candidates where both percentages are low
        fade_candidate = None
        fade_team_id = None
        fade_tickets = None
        fade_money = None
        opponent_display = None

        if home_tickets < 20 and home_money < 20:
            fade_candidate = home_team
            fade_team_id = home_id
            fade_tickets, fade_money = home_tickets, home_money
            opponent_display = away_display
        elif away_tickets < 20 and away_money < 20:
            fade_candidate = away_team
            fade_team_id = away_id
            fade_tickets, fade_money = away_tickets, away_money
            opponent_display = home_display

        if not fade_candidate:
            return None # No fade opportunity found

        fade_display = fade_candidate.get('display_name', 'Faded Team')

        # Get spread info for the fade candidate
        spread_value_str, spread_odds_str = get_spread_info(game, fade_team_id)
        if spread_value_str is None: 
            logger.debug(f"Missing spread value for team {fade_team_id} in game {game.get('id') or game.get('game_id')}")
            return None # Need spread value

        # Format spread value nicely (+ sign if positive)
        try:
            spread_val_num = float(spread_value_str)
            formatted_spread = f"+{spread_val_num}" if spread_val_num > 0 else str(spread_val_num)
        except ValueError:
            formatted_spread = spread_value_str # Use as is if not number

        # Calculate fade rating
        rating = calculate_fade_rating(fade_tickets, fade_money)
        
        # Use a lower threshold for testing
        min_rating_threshold = 2  # Lower threshold for testing (default was 3)
        if rating < min_rating_threshold:
            return None # Only show opportunities meeting threshold

        stars = "⭐️" * rating
        sport_name = 'NBA' if sport == 'nba' else 'NCAA Basketball'
        icon = "🏀" if sport == 'nba' else "🏫"

        # Determine opponent and get their spread
        opponent_display = None
        opponent_spread_str = None
        if fade_team_id == home_id:
            opponent_id = away_id
            opponent_display = away_display
            opponent_spread_str, _ = get_spread_info(game, opponent_id)
        else:
            opponent_id = home_id
            opponent_display = home_display
            opponent_spread_str, _ = get_spread_info(game, opponent_id)
            
        # Format opponent spread
        formatted_opponent_spread = ""
        if opponent_spread_str:
             try:
                 opp_spread_num = float(opponent_spread_str)
                 formatted_opponent_spread = f"+{opp_spread_num}" if opp_spread_num > 0 else str(opp_spread_num)
             except ValueError:
                 formatted_opponent_spread = opponent_spread_str

        # Construct Game Line based on who is home/away
        if fade_team_id == home_id: # Fading home team
            game_line = f"Game: {opponent_display} ({formatted_opponent_spread}) vs. {fade_display} ({formatted_spread})"
        else: # Fading away team
            game_line = f"Game: {fade_display} ({formatted_spread}) vs. {opponent_display} ({formatted_opponent_spread})"

        # Message based on game state
        if not completed:
            # Pre-game alert (Desired Format 1.1)
            message_lines = [
                f"🚨Fade Alert 🚨",
                f"Sport: {sport_name}",
                game_line,
                f"Percentage of Total Bets on {fade_display}: {fade_tickets:.1f}%",
                f"Percentage of Total Money on {fade_display}: {fade_money:.1f}%",
                f"{stars} ({rating}-Star Fade)",
                f"Take: {fade_display} ({formatted_spread})", # Removed odds, changed wording
            ]
            # Add start time if available
            start_time_str = game.get('start_time')
            if start_time_str:
                try:
                    start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                    start_formatted = start_dt.strftime("%I:%M %p UTC")
                    message_lines.append(f"⏰ Starts: {start_formatted}")
                except ValueError:
                    pass
                    
        else:
            # Post-game result logic
            if winner_covered_spread is True:
                # Winner state (Desired Format 1.2.1)
                result_icon = "✅✅✅"
                result_header = f"{result_icon} Fade Alert Result {result_icon}"
                result_line = f"Winner: {fade_display} ({formatted_spread}) {result_icon}"
            elif winner_covered_spread is False:
                 # Loser state (Desired Format 1.2.2)
                result_icon = "❌"
                result_header = f"{result_icon}Fade Alert Result {result_icon}"
                result_line = f"Loser: {fade_display} ({formatted_spread}) {result_icon}"
            else:
                # Uncertain state (Keep previous icons/text for this edge case)
                result_icon = "❓❓❓"
                result_header = f"{result_icon} Fade Result Uncertain {result_icon}"
                result_line = "Result: Outcome unclear (push or data issue)."

            message_lines = [
                result_header,
                f"Sport: {sport_name}",
                game_line,
                f"Percentage of Total Bets on {fade_display}: {fade_tickets:.1f}%",
                f"Percentage of Total Money on {fade_display}: {fade_money:.1f}%",
                f"{stars} ({rating}-Star Fade)",
                result_line,
            ]
            # Add game scores if available
            if game.get('boxscore'):
                away_score = game['boxscore'].get('total_away_points', '?')
                home_score = game['boxscore'].get('total_home_points', '?')
                message_lines.append(f"Final Score: {away_display} {away_score} - {home_score} {home_display}")


        return "\n".join(message_lines)

    except Exception as e:
        logger.error(f"Error formatting fade alert for game {game.get('game_id')}: {e}", exc_info=True)
        return None # Return None on error