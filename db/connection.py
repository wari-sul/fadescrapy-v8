import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.errors import OperationFailure

# Get logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client["db-mongodb-sgp1-64608"]
nba_collection = db["nba"]
ncaab_collection = db["ncaab"]
fade_alerts_collection = db["fade_alerts"]
users_collection = db["users"]

def setup_indexes():
    """Creates indexes on the MongoDB collections."""
    try:
        # Create date index for game collections
        nba_collection.create_index([("date", ASCENDING)])
        ncaab_collection.create_index([("date", ASCENDING)])
        
        # Create indexes for fade alerts collection
        fade_alerts_collection.create_index([("game_id", ASCENDING)])
        fade_alerts_collection.create_index([("date", ASCENDING)])
        fade_alerts_collection.create_index([("sport", ASCENDING)])
        fade_alerts_collection.create_index([("status", ASCENDING)])
        fade_alerts_collection.create_index([("created_at", ASCENDING)])
        
        # Create indexes for users collection
        users_collection.create_index([("user_id", ASCENDING)])
        users_collection.create_index([("last_seen", ASCENDING)])
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

# Create indexes on module import
setup_indexes()