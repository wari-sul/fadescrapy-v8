import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv
from pymongo import MongoClient

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# --- DB Connection ---
client = None
try:
    if not MONGO_URI:
        logger.error("MONGO_URI environment variable not set.")
        exit(1)
    client = MongoClient(MONGO_URI)
    client.admin.command('ping')
    db_client = client["db-mongodb-sgp1-64608"]
    nba_collection = db_client["nba"]
    logger.info("Successfully connected to MongoDB.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    if client:
        client.close()
    exit(1)

# --- Import necessary functions ---
try:
    from db.game_repo import update_or_insert_data, get_scheduled_games, get_game_by_team
    from db.utils import get_eastern_time_date # Correct function name
except ImportError as e:
     logger.error(f"Failed to import necessary project modules: {e}")
     if client: client.close()
     exit(1)
except AttributeError: # Fallback if get_eastern_time_date_str moved or renamed
    def get_eastern_time_date_str():
        try:
            eastern = pytz.timezone('US/Eastern')
            return datetime.now(eastern).strftime('%Y%m%d')
        except Exception: return datetime.now().strftime('%Y%m%d')


# --- Dummy Data (Matching structure expected by update_or_insert_data) ---
dummy_nba_game_for_insert = {
    "id": "NBA999001",
    "status": "scheduled",
    "start_time": datetime.now(pytz.UTC).isoformat(),
    "home_team_id": 101,
    "away_team_id": 102,
    "teams": [
        {"id": 101, "display_name": "Dummy Lakers"},
        {"id": 102, "display_name": "Dummy Clippers"}
    ],
    "odds": [ { "book_id": 15, "home_tickets": 0.85, "home_money": 0.90, "away_tickets": 0.15, "away_money": 0.10 } ],
    "markets": { "15": { "event": { "spread": [ {"team_id": 101, "value": -5.5, "odds": -110}, {"team_id": 102, "value": +5.5, "odds": -110} ]}}},
    "num_bets": 1000, "status_display": "Scheduled", "boxscore": None, "winner_id": None
}

nba_payload_for_insert = {
    "metadata": {"source": "refactor_test_script", "timestamp": datetime.now(pytz.UTC).isoformat()},
    "data": { "games": [dummy_nba_game_for_insert] }
}


# --- Main Test Function ---
def main():
    """Inserts dummy data and tests the refactored game repo functions."""
    processed_correctly_scheduled = False
    processed_correctly_team = False
    today_date_str, _ = get_eastern_time_date() # Use correct function and unpack tuple

    try:
        # 1. Insert/Update dummy data to ensure it's present
        logger.info(f"Inserting/Updating dummy NBA game for date: {today_date_str}")
        update_or_insert_data(nba_collection, nba_payload_for_insert, today_date_str)
        logger.info("Dummy data inserted/updated.")

        # 2. Test get_scheduled_games
        logger.info("\n--- Testing get_scheduled_games ---")
        scheduled_games = get_scheduled_games(nba_collection, today_date_str)
        if not scheduled_games:
            logger.error("get_scheduled_games returned no games!")
        else:
            logger.info(f"Found {len(scheduled_games)} game(s). Checking first game...")
            first_game = scheduled_games[0]
            # Check if processing occurred (presence of 'home_team', absence of 'teams')
            if 'home_team' in first_game and first_game['home_team'] is not None and 'teams' not in first_game:
                logger.info("First game appears correctly processed by helper function.")
                logger.info(f"  Home Team: {first_game.get('home_team', {}).get('display_name')}")
                logger.info(f"  Spread data exists: {'spread' in first_game}")
                processed_correctly_scheduled = True
            else:
                logger.error("First game does NOT appear correctly processed.")
                logger.error(f"  Game data: {first_game}")


        # 3. Test get_game_by_team
        logger.info("\n--- Testing get_game_by_team ---")
        team_games = get_game_by_team(nba_collection, today_date_str, "Dummy Lakers")
        if not team_games:
            logger.error("get_game_by_team returned no games!")
        else:
            logger.info(f"Found {len(team_games)} game(s) for team. Checking first game...")
            first_team_game = team_games[0]
            # Check if processing occurred
            if 'home_team' in first_team_game and first_team_game['home_team'] is not None and 'teams' not in first_team_game:
                logger.info("First team game appears correctly processed by helper function.")
                logger.info(f"  Home Team: {first_team_game.get('home_team', {}).get('display_name')}")
                logger.info(f"  Spread data exists: {'spread' in first_team_game}")
                processed_correctly_team = True
            else:
                logger.error("First team game does NOT appear correctly processed.")
                logger.error(f"  Game data: {first_team_game}")

    except Exception as e:
        logger.error(f"An error occurred during the test: {e}", exc_info=True)
    finally:
        logger.info("\n--- Refactor Test Summary ---")
        logger.info(f"get_scheduled_games processing successful: {processed_correctly_scheduled}")
        logger.info(f"get_game_by_team processing successful: {processed_correctly_team}")
        if client:
            client.close()
            logger.info("MongoDB connection closed.")

if __name__ == "__main__":
    main()