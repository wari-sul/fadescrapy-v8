import os
import logging
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
    fade_alerts_collection = db_client["fade_alerts"]
    logger.info("Successfully connected to MongoDB.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    if client:
        client.close()
    exit(1)

# --- Delete Function ---
def delete_alerts_by_game_id(collection, game_id):
    """Deletes all alerts matching a specific game_id."""
    try:
        logger.info(f"Attempting to delete alerts for game_id: {game_id} from {collection.name}...")
        result = collection.delete_many({"game_id": game_id})
        logger.info(f"Deleted {result.deleted_count} alert(s) for game_id: {game_id}.")
        return result.deleted_count
    except Exception as e:
        logger.error(f"Error deleting alerts for game_id {game_id}: {e}")
        return 0

# --- Execute Deletions ---
try:
    deleted_nba = delete_alerts_by_game_id(fade_alerts_collection, DUMMY_NBA_GAME_ID)
    deleted_ncaab = delete_alerts_by_game_id(fade_alerts_collection, DUMMY_NCAAB_GAME_ID)

    logger.info(f"Finished deleting dummy alerts. NBA deleted: {deleted_nba}, NCAAB deleted: {deleted_ncaab}")

except Exception as e:
    logger.error(f"Script failed during deletion: {e}")
finally:
    if client:
        client.close()
        logger.info("MongoDB connection closed.")