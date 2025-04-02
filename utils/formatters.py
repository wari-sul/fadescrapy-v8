from typing import Optional, Dict, Tuple
from datetime import datetime
import logging
from logging_setup import logger
from utils.game_processing import get_spread_info # Removed get_bet_percentages

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

# calculate_fade_rating_v2 moved to utils/game_processing.py to avoid circular import

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

def format_fade_alert(game: dict, opportunity: dict, result_status: Optional[str] = "pending") -> Optional[str]:
    """
    Formats a fade alert message based on the opportunity data and result status,
    using the Ticket% vs Implied Probability formula and includes star rating (Structure V4.11).

    Args:
        game: The game data dictionary.
        opportunity: The fade opportunity dictionary from find_fade_opportunities.
        result_status: The status of the alert ('pending', 'won', 'lost', None).

    Returns:
        A formatted string message or None if formatting fails.
    """
    try:
        # --- Extract Game Info ---
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        # --- Add Logging ---
        game_id_fmt = game.get('game_id', 'N/A')
        logger.info(f"[format_fade_alert] Checking game {game_id_fmt}. Game keys: {list(game.keys())}. Home team type: {type(home_team).__name__}, Away team type: {type(away_team).__name__}")
        # --- End Logging ---
        # Use team abbreviations if display names are missing/long
        home_display = home_team.get('abbr') if home_team else 'Home'
        away_display = away_team.get('abbr') if away_team else 'Away'
        if not home_team or not away_team:
             logger.warning(f"[format_fade_alert] Returning None because home_team or away_team is missing/falsy for game {game_id_fmt}")
             return None # Need team objects

        sport = opportunity.get('sport', 'unknown')
        sport_name = 'NBA' if sport == 'nba' else 'NCAAB' if sport == 'ncaab' else sport.upper()
        game_status = game.get('status', 'unknown')
        game_id_log = opportunity.get('game_id', 'N/A') # For logging

        # --- Extract Opportunity Info ---
        market = opportunity.get('market')
        faded_outcome_label = opportunity.get('faded_outcome_label')
        faded_value = opportunity.get('faded_value') # Spread/Total value
        odds = opportunity.get('odds')
        implied_prob = opportunity.get('implied_probability')
        # Accept either key format for flexibility
        tickets_pct = opportunity.get('T%') or opportunity.get('tickets_percent')
        money_pct = opportunity.get('M%') or opportunity.get('money_percent')
        rating = opportunity.get('rating', 0) # Get the rating

        if not all([market, faded_outcome_label, odds is not None, implied_prob is not None, tickets_pct is not None, money_pct is not None]):
            logger.warning(f"Incomplete opportunity data for formatting: {game_id_log}")
            return None

        # --- Determine "Bet Against" Side and Value ---
        bet_against_label = "N/A"
        bet_against_value_str = "" # For spread/total value

        if market == 'Spread':
            opponent_spread_val = None
            if faded_value is not None:
                try:
                    opponent_spread_val = -float(faded_value)
                    bet_against_value_str = f"{opponent_spread_val:+.1f}" # Always show sign
                except (ValueError, TypeError):
                    bet_against_value_str = "N/A"

            if faded_outcome_label == 'Home':
                bet_against_label = f"{away_display} {bet_against_value_str}"
            elif faded_outcome_label == 'Away':
                bet_against_label = f"{home_display} {bet_against_value_str}"

        elif market == 'Total':
            bet_against_value_str = str(faded_value) if faded_value is not None else "N/A"
            if faded_outcome_label == 'Over':
                bet_against_label = f"Under {bet_against_value_str}"
            elif faded_outcome_label == 'Under':
                bet_against_label = f"Over {bet_against_value_str}"

        elif market == 'Moneyline':
            # No value string needed for ML bet against label
            if faded_outcome_label == 'Home':
                bet_against_label = f"{away_display} ML"
            elif faded_outcome_label == 'Away':
                bet_against_label = f"{home_display} ML"

        # --- Format Faded Outcome Value ---
        faded_value_str = ""
        if faded_value is not None and market != 'Moneyline': # ML value is usually 0
             try:
                 faded_val_num = float(faded_value)
                 faded_value_str = f" ({faded_val_num:+.1f})" if market == 'Spread' else f" ({faded_val_num})"
             except (ValueError, TypeError):
                 faded_value_str = f" ({faded_value})"

        faded_outcome_full_label = f"{faded_outcome_label}{faded_value_str}"

        # --- Build Message (Structure V4.11) ---
        message_lines = []
        stars = "⭐" * rating
        header_icon = "🚨"
        result_prefix = "Take" # Default for pending

        if result_status == 'won':
            header_icon = "✅"
            result_prefix = "✅ Result: Fade Won - Took"
        elif result_status == 'lost':
            header_icon = "❌"
            result_prefix = "❌ Result: Fade Lost - Took"

        # Header
        # Remove stars from header
        message_lines.append(f"{header_icon} <b>{sport_name} Fade Alert</b> {header_icon}")

        # Game Info
        message_lines.append(f"<b>Game:</b> {away_display} <b>vs</b> {home_display}")
        if game_status.lower() in ['complete', 'closed', 'final']:
            boxscore = game.get('boxscore', {})
            away_score = boxscore.get('total_away_points', '?')
            home_score = boxscore.get('total_home_points', '?')
            message_lines.append(f"<b>Status:</b> Final Score: {away_display} {away_score} - {home_score} {home_display}")
        else:
            start_time_str = game.get('start_time')
            time_display = "Time N/A"
            if start_time_str:
                try:
                    start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                    time_display = start_dt.strftime("%I:%M %p UTC") # Consider converting to user's timezone later
                except ValueError:
                    time_display = start_time_str
            status_icon = get_game_status_icon(game_status)
            message_lines.append(f"<b>Status:</b> {time_display} - {status_icon}")

        # Analysis
        message_lines.append(f"\n📊 <b>Analysis (Book ID 15 - Public Betting):</b>")
        # Remove bullet points and leading spaces
        message_lines.append(f"<b>Public Favors:</b> {faded_outcome_full_label} <b>({tickets_pct:.1f}% of tickets)</b>")
        message_lines.append(f"Money %: {money_pct:.1f}%")
        message_lines.append(f"Odds: {odds} (Implied Probability: {implied_prob:.1f}%)")

        # Fade Signal
        t_minus_ip = tickets_pct - implied_prob
        message_lines.append(f"\n📉 <b>Fade Signal:</b> Public betting (Ticket %) is significantly higher (<b>{t_minus_ip:.1f}%</b>) than the odds suggest ({implied_prob:.1f}%), and the money flow ({money_pct:.1f}%) isn't strongly backing the public trend.")

        # Recommendation
        message_lines.append(f"\n✅ <b>Suggested Fade:</b>")
        # Remove bullet points and leading spaces
        message_lines.append(f"{result_prefix} <b>{bet_against_label}</b>")

            # Add Fade Rating at the end (indent this inside the try block)
        message_lines.append(f"\nFade Rating : {stars}") # Correct indentation

            # Return inside the try block
        return "\n".join(message_lines) # Correct indentation
        # Remove the duplicate/mis-indented return statement

    except Exception as e:
        game_id_log = opportunity.get('game_id', 'UNKNOWN')
        faded_label_log = opportunity.get('faded_outcome_label', 'UNKNOWN')
        logger.error(f"Error formatting fade alert for game {game_id_log}, opp: {faded_label_log}: {e}", exc_info=True)
        return None # Return None on error