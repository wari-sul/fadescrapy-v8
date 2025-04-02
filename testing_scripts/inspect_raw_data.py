import logging
from bson import ObjectId # Import ObjectId to query by ID

# Assuming your project structure allows these imports
from db.connection import db # Import the database object

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def inspect_raw_data(doc_id_str: str):
    """Fetches a raw response document by ID and prints relevant parts."""
    logger.info(f"Attempting to fetch raw response document with ID: {doc_id_str}")

    if db is None:
        logger.critical("Database object (db) is None. Cannot connect.")
        return

    try:
        raw_collection = db.raw_api_responses
        doc_id = ObjectId(doc_id_str) # Convert string ID to ObjectId

        document = raw_collection.find_one({"_id": doc_id})

        if not document:
            logger.error(f"Document with ID {doc_id_str} not found in raw_api_responses collection.")
            return

        logger.info(f"Found document for sport: {document.get('sport')}, date: {document.get('date')}")

        raw_json = document.get('raw_json')
        if not raw_json or not isinstance(raw_json, dict):
            logger.error("raw_json field is missing or not a dictionary.")
            return

        # Assuming the structure contains a list of games, similar to what the API functions return
        # Let's look for a 'games' key or similar. Adjust if structure is different.
        games = None
        if 'games' in raw_json: # Common pattern seen in processing
             games = raw_json['games']
        elif 'data' in raw_json and 'games' in raw_json['data']: # Another possible structure
             games = raw_json['data']['games']
        elif isinstance(raw_json, list): # Maybe the root is the list of games?
             games = raw_json

        if not games or not isinstance(games, list) or len(games) == 0:
            logger.error("Could not find a list of games within the raw_json.")
            logger.info(f"Raw JSON keys: {list(raw_json.keys())}")
            return

        # Print odds for the first game found
        first_game = games[0]
        game_id = first_game.get('id') or first_game.get('game_id', 'N/A')
        logger.info(f"\n--- Odds data for the first game (ID: {game_id}) ---")

        odds_data = first_game.get('odds')
        if odds_data and isinstance(odds_data, list):
            if not odds_data:
                logger.info("Odds list is empty.")
            else:
                logger.info(f"Found {len(odds_data)} odds entries. Printing all:")
                for i, odds_entry in enumerate(odds_data):
                    logger.info(f"Entry {i+1}: {odds_entry}")
                    # Specifically check for book_id
                    book_id = odds_entry.get('book_id')
                    if book_id is not None:
                        logger.info(f"  -> Found book_id: {book_id}")
                    else:
                        logger.info("  -> No 'book_id' key found in this entry.")
        elif odds_data:
             logger.warning(f"Odds data found but is not a list: {type(odds_data)}")
             logger.info(f"Odds data content: {odds_data}")
        else:
            logger.info("No 'odds' key found in the first game.")

        logger.info("--- End of odds data ---")

    except ImportError:
         logger.error("Failed to import ObjectId from bson. Make sure 'pymongo' is installed.")
    except Exception as e:
        logger.error(f"An error occurred during inspection: {e}", exc_info=True)


if __name__ == "__main__":
    # Use the ID from the previous test run log
    target_doc_id = "67ed34339291cf7791c1e967"
    inspect_raw_data(target_doc_id)