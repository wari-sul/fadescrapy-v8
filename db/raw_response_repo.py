import logging
import pytz
from datetime import datetime
from .connection import db_connection # Assuming db_connection holds the client/db reference

# Get logger
logger = logging.getLogger(__name__)

# Collection reference (adjust 'your_database_name' if needed)
try:
    # Ensure db_connection is not None before accessing attributes
    if db_connection:
        raw_api_responses_collection = db_connection.get_database().raw_api_responses
    else:
        logger.critical("Database connection (db_connection) is None. Cannot get raw_api_responses collection.")
        raw_api_responses_collection = None
except AttributeError as e:
    logger.critical(f"Failed to get raw_api_responses collection: {e}. Make sure db_connection is initialized correctly.")
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