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
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME") # Get DB name from env

# MongoDB connection
client = MongoClient(MONGO_URI)

if not MONGO_DB_NAME:
    raise ValueError("MONGO_DB_NAME environment variable not set.")

db = client.get_database(MONGO_DB_NAME) # Use get_database for clarity
settings_collection = db["settings"]

# --- Maintenance Mode Logic ---

MAINTENANCE_PREFIX = "maintenance_"

def is_maintenance_mode():
    """Checks if maintenance mode is enabled in settings."""
    setting = settings_collection.find_one({"_id": "maintenance_status"})
    return setting.get("enabled", False) if setting else False

def set_maintenance_mode(enabled: bool):
    """Enables or disables maintenance mode."""
    settings_collection.update_one(
        {"_id": "maintenance_status"},
        {"$set": {"enabled": enabled}},
        upsert=True
    )
    logger.info(f"Maintenance mode {'enabled' if enabled else 'disabled'}.")

def get_collection_name(base_name: str) -> str:
    """Returns the correct collection name based on maintenance mode."""
    if is_maintenance_mode():
        return f"{MAINTENANCE_PREFIX}{base_name}"
    return base_name

def clear_maintenance_collections():
    """Drops all collections prefixed with 'maintenance_'."""
    if not is_maintenance_mode():
        logger.warning("Clear maintenance data called, but maintenance mode is not active.")
        # Decide if we should still clear or return an error. Let's clear for now.
        # return False

    collections_to_drop = [name for name in db.list_collection_names() if name.startswith(MAINTENANCE_PREFIX)]
    if not collections_to_drop:
        logger.info("No maintenance collections found to clear.")
        return True
        
    try:
        for name in collections_to_drop:
            db.drop_collection(name)
            logger.info(f"Dropped maintenance collection: {name}")
        return True
    except Exception as e:
        logger.error(f"Error clearing maintenance collections: {e}", exc_info=True)
        return False

# --- Collection Getters ---
# Instead of exporting collections directly, export functions that get the right one

def get_nba_collection():
    return db[get_collection_name("nba")]

def get_ncaab_collection():
    return db[get_collection_name("ncaab")]

def get_fade_alerts_collection():
    return db[get_collection_name("fade_alerts")]

def get_users_collection():
    # Typically, users should persist across modes, but adjust if needed
    return db["users"]

def get_raw_api_responses_collection():
    # Raw responses might also be shared or separated based on need
    return db[get_collection_name("raw_api_responses")]

# --- Original Collections (for reference or specific non-maintenance tasks if any) ---
# It's better to refactor code to use the getters above.
# Keep these lines commented out or remove if fully refactored.
# nba_collection = get_nba_collection()
# ncaab_collection = get_ncaab_collection()
# fade_alerts_collection = get_fade_alerts_collection()
# users_collection = get_users_collection()
# raw_api_responses_collection = get_raw_api_responses_collection()

def setup_indexes():
    """Creates indexes on the MongoDB collections."""
    try:
        # Define collections and their indexes
        collections_indexes = {
            "nba": [[("date", ASCENDING)]],
            "ncaab": [[("date", ASCENDING)]],
            "fade_alerts": [
                [("game_id", ASCENDING)],
                [("date", ASCENDING)],
                [("sport", ASCENDING)],
                [("status", ASCENDING)],
                [("created_at", ASCENDING)]
            ],
            "users": [ # Users collection is not prefixed
                [("user_id", ASCENDING)],
                [("last_seen", ASCENDING)]
            ],
             "raw_api_responses": [] # TTL index handled separately
        }

        # Create indexes for both normal and maintenance collections
        for base_name, indexes in collections_indexes.items():
            # Users collection is special, not prefixed
            collection_names_to_index = [base_name] if base_name == "users" else [base_name, f"{MAINTENANCE_PREFIX}{base_name}"]
            
            for collection_name in collection_names_to_index:
                collection = db[collection_name]
                for index_spec in indexes:
                    try:
                        collection.create_index(index_spec)
                        logger.debug(f"Index {index_spec} created/ensured for {collection_name}")
                    except OperationFailure as e:
                         # Ignore index already exists errors, log others
                        if 'index already exists' not in str(e).lower():
                             logger.warning(f"Could not create index {index_spec} for {collection_name}: {e}")
                        else:
                            logger.debug(f"Index {index_spec} already exists for {collection_name}")
        
        # Create TTL index for raw responses (expire after 24 hours)
        try:
            # Apply TTL index to both normal and maintenance raw response collections
            raw_collection_names = ["raw_api_responses", f"{MAINTENANCE_PREFIX}raw_api_responses"]
            for collection_name in raw_collection_names:
                collection = db[collection_name]
                collection.create_index(
                    [('fetched_at', ASCENDING)],
                    expireAfterSeconds=86400 # 24 * 60 * 60 seconds
                )
            logger.info("TTL index created/ensured for raw_api_responses collections.")
        except OperationFailure as e:
            # Handle potential error if index already exists with different options
            if 'Cannot create index' in str(e) and 'different options' in str(e):
                logger.warning(f"TTL index on {collection_name} already exists with different options: {e}")
            else:
                raise # Re-raise other errors

        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

# Create indexes on module import
setup_indexes()