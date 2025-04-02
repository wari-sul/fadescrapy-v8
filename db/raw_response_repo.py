import logging
import pytz
from datetime import datetime
from .connection import get_raw_api_responses_collection # Import the getter function

# Get logger
logger = logging.getLogger(__name__)

# Removed module-level collection variable; will get it inside the function

def store_raw_response(sport: str, date_str: str, response_data: dict):
    """Stores the raw API response data."""
    # Get the correct collection based on current maintenance mode
    collection = get_raw_api_responses_collection()
    if collection is None: # The getter might return None if db connection failed, though unlikely here
        logger.error("Failed to get raw_api_responses_collection. Cannot store raw response.")
        return False # Or raise an error
        
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
        result = collection.insert_one(document)
        logger.info(f"Stored raw {sport.upper()} API response for date {date_str} with ID: {result.inserted_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing raw API response for {sport} on {date_str}: {e}", exc_info=True)
        return False