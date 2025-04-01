import logging
import pytz
from datetime import datetime
from .connection import db # Import the database object 'db'

# Get logger
logger = logging.getLogger(__name__)

# Collection reference
try:
    # Ensure db object is not None before accessing attributes
    if db is not None: # Correct check for None
        raw_api_responses_collection = db.raw_api_responses # Use db directly
    else:
        logger.critical("Database object (db) is None. Cannot get raw_api_responses collection.")
        raw_api_responses_collection = None
except AttributeError as e:
    # This might happen if the collection name is wrong or db object is malformed
    logger.critical(f"Failed to get raw_api_responses collection from db object: {e}")
    raw_api_responses_collection = None

def store_raw_response(sport: str, date_str: str, response_data: dict):
    """Stores the raw API response data."""
    if raw_api_responses_collection is None:
        logger.error("raw_api_responses_collection is not initialized. Cannot store raw response.")
        return False
        
    try:
        if not response_data or not isinstance(response_data, dict):
            logger.warning(f"Invalid or empty response_data provided for {sport} on {date_str}. Not storing.")
            return False

        document = {
            "sport": sport,
            "date": date_str, # The date the data represents
            "fetched_at": datetime.now(pytz.UTC), # Timestamp of when it was fetched
            "raw_json": response_data # Store the parsed JSON dictionary
        }
        
        # Using insert_one as we want a new record for each fetch
        result = raw_api_responses_collection.insert_one(document)
        logger.info(f"Stored raw {sport.upper()} API response for date {date_str} with ID: {result.inserted_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing raw API response for {sport} on {date_str}: {e}", exc_info=True)
        return False