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
DUMMY_NBA_GAME_ID = "NBA999001"
DUMMY_NCAAB_GAME_ID = "NCAAB999002"

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
    ncaab_collection = db_client["ncaab"]
    logger.info("Successfully connected to MongoDB.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    if client:
        client.close()
    exit(1)

# --- Helper to get Eastern Time Date ---
def get_eastern_time_date_str():
    """Gets the current date in Eastern Time as YYYYMMDD string."""
    try:
        eastern = pytz.timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        return now_eastern.strftime('%Y%m%d')
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error("Timezone 'US/Eastern' not found. Make sure 'pytz' is installed.")
        return datetime.now().strftime('%Y%m%d') # Fallback
    except Exception as e:
        logger.error(f"Error getting Eastern time date: {e}")
        return datetime.now().strftime('%Y%m%d') # Fallback

# --- Check Function ---
def check_game_exists(collection, date_str, game_id_to_find):
    """Checks if a specific game_id exists within the data for a given date."""
    try:
        document = collection.find_one({"date": date_str})
        if not document:
            logger.info(f"No document found for date {date_str} in {collection.name}.")
            return False

        games_data = document.get("data", {}).get("games", [])
        if not games_data:
            logger.info(f"Document for date {date_str} in {collection.name} has no 'games' data.")
            return False

        for game in games_data:
            # Check both 'id' and 'game_id' as they might be used interchangeably
            if game.get("id") == game_id_to_find or game.get("game_id") == game_id_to_find:
                logger.info(f"Found game {game_id_to_find} for date {date_str} in {collection.name}.")
                return True

        logger.info(f"Game {game_id_to_find} NOT found within games for date {date_str} in {collection.name}.")
        return False
    except Exception as e:
        logger.error(f"Error checking for game {game_id_to_find} in {collection.name}: {e}")
        return False

# --- Execute Checks ---
try:
    today_date_str = get_eastern_time_date_str()
    logger.info(f"Checking for dummy data using date: {today_date_str}")

    nba_found = check_game_exists(nba_collection, today_date_str, DUMMY_NBA_GAME_ID)
    ncaab_found = check_game_exists(ncaab_collection, today_date_str, DUMMY_NCAAB_GAME_ID)

    print("\n--- Check Results ---")
    print(f"Dummy NBA Game ({DUMMY_NBA_GAME_ID}) found for {today_date_str}: {nba_found}")
    print(f"Dummy NCAAB Game ({DUMMY_NCAAB_GAME_ID}) found for {today_date_str}: {ncaab_found}")
    print("---------------------\n")

    if nba_found:
        logger.info("Dummy NBA game exists. You can proceed with testing /fadenba or /fades.")
    else:
        logger.warning("Dummy NBA game NOT found. You may need to run 'insert_dummy_fades.py' again before testing.")

    # Note: We expect NCAAB to be False as we commented out its insertion last time.
    if ncaab_found:
         logger.warning("Dummy NCAAB game found unexpectedly. It might be from an earlier test run.")


except Exception as e:
    logger.error(f"Script failed during check: {e}")
finally:
    if client:
        client.close()
        logger.info("MongoDB connection closed.")