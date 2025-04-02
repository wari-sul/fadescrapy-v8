import asyncio
import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv
# No MongoClient needed as we won't call process_new_fade_alerts

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

# --- Import necessary functions ---
try:
    from utils.formatters import format_fade_alert, calculate_fade_rating
    from utils.game_processing import get_bet_percentages, get_spread_info
except ImportError as e:
    logger.error(f"Failed to import necessary project modules: {e}")
    logger.error("Make sure this script is run from the project root directory (e:\\Jobs\\fadescrapy v8).")
    exit(1)

# --- Hardcoded Dummy Data (with completed status and boxscore) ---
dummy_nba_game_completed = {
    "id": "NBA999001", "game_id": "NBA999001",
    "status": "complete", # Changed status
    "start_time": datetime.now(pytz.UTC).isoformat(),
    "home_team_id": 101, "away_team_id": 102,
    "teams": [ {"id": 101, "display_name": "Dummy Lakers"}, {"id": 102, "display_name": "Dummy Clippers"} ],
    "home_team": {"id": 101, "display_name": "Dummy Lakers"},
    "away_team": {"id": 102, "display_name": "Dummy Clippers"},
    "odds": [ { "book_id": 15, "home_tickets": 0.85, "home_money": 0.90, "away_tickets": 0.15, "away_money": 0.10 } ],
    "markets": { "15": { "event": { "spread": [ {"team_id": 101, "value": -5.5, "odds": -110}, {"team_id": 102, "value": +5.5, "odds": -110} ]}}},
    "spread": [ {"team_id": 101, "value": -5.5, "odds": -110}, {"team_id": 102, "value": +5.5, "odds": -110} ],
    "num_bets": 1000, "status_display": "Final", # Changed status display
    "boxscore": {"total_home_points": 110, "total_away_points": 100}, # Added boxscore
    "winner_id": 101, "winning_team_id": 101 # Added winner
}

# --- Main Test Function ---
async def main():
    """Generates and prints post-game alert formats using hardcoded data."""
    logger.info("Generating post-game alert formats using hardcoded data...")

    # --- Test Winner Format (winner_covered_spread = True) ---
    logger.info("\n--- Testing WINNER Format ---")
    winner_alert_msg = format_fade_alert(
        game=dummy_nba_game_completed,
        sport="nba",
        completed=True,
        winner_covered_spread=True # Simulate fade success
    )
    if winner_alert_msg:
        print(winner_alert_msg)
    else:
        logger.warning("Failed to generate WINNER format message.")

    # --- Test Loser Format (winner_covered_spread = False) ---
    logger.info("\n--- Testing LOSER Format ---")
    loser_alert_msg = format_fade_alert(
        game=dummy_nba_game_completed,
        sport="nba",
        completed=True,
        winner_covered_spread=False # Simulate fade failure
    )
    if loser_alert_msg:
        print(loser_alert_msg)
    else:
        logger.warning("Failed to generate LOSER format message.")

    logger.info("\n--- Test Complete ---")


if __name__ == "__main__":
    asyncio.run(main())