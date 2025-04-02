import os
import logging
from datetime import datetime
import pytz # Need pytz for timezone
from dotenv import load_dotenv
from pymongo import MongoClient

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# --- DB Connection ---
client = None # Initialize client to None
try:
    if not MONGO_URI:
        logger.error("MONGO_URI environment variable not set. Please check your .env file.")
        exit(1)
    client = MongoClient(MONGO_URI)
    # Ping the server to confirm connection
    client.admin.command('ping')
    db_client = client["db-mongodb-sgp1-64608"] # Use the actual db name from connection.py
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
        logger.error("Timezone 'US/Eastern' not found. Make sure the 'pytz' library is installed and updated.")
        return datetime.now().strftime('%Y%m%d') # Fallback to system time date
    except Exception as e:
        logger.error(f"Error getting Eastern time date: {e}")
        return datetime.now().strftime('%Y%m%d') # Fallback

# --- Dummy Data ---
today_date_str = get_eastern_time_date_str()
logger.info(f"Using date: {today_date_str} for dummy data.")

# Note: The structure here includes 'markets' as it might appear raw from an API,
# and 'odds' as expected by get_bet_percentages after some processing.
# The 'get_scheduled_games' function in game_repo.py transforms 'markets' into 'spread', 'moneyline', 'total'.
# The fade alert logic uses get_bet_percentages (needs 'odds') and get_spread_info (needs 'spread' after processing).
# To be safe and mimic potential raw data + processed data, we include both structures where relevant.
# The update_or_insert_data function stores whatever is passed in the 'data' field.

dummy_nba_game = {
    "id": "NBA999001",
    "game_id": "NBA999001", # Include game_id as it's used interchangeably
    "status": "scheduled",
    "start_time": datetime.now(pytz.UTC).isoformat(),
    "home_team_id": 101,
    "away_team_id": 102,
    "teams": [
        {"id": 101, "display_name": "Dummy Lakers"},
        {"id": 102, "display_name": "Dummy Clippers"}
    ],
    "home_team": {"id": 101, "display_name": "Dummy Lakers"}, # Add processed team info
    "away_team": {"id": 102, "display_name": "Dummy Clippers"}, # Add processed team info
    "odds": [ # Structure for get_bet_percentages
        {
            "book_id": 15,
            "home_tickets": 0.85,
            "home_money": 0.90,
            "away_tickets": 0.15, # Fade target (<0.20)
            "away_money": 0.10  # Fade target (<0.20)
        }
    ],
    "markets": { # Raw structure potentially from API
         "15": { # Book ID 15
             "event": {
                 "spread": [
                     {"team_id": 101, "value": -5.5, "odds": -110},
                     {"team_id": 102, "value": +5.5, "odds": -110} # Fade target spread
                 ],
                 "moneyline": [],
                 "total": []
             }
         }
    },
    "spread": [ # Processed structure for get_spread_info
        {"team_id": 101, "value": -5.5, "odds": -110},
        {"team_id": 102, "value": +5.5, "odds": -110}
    ],
    "num_bets": 1000,
    "status_display": "Scheduled",
    "boxscore": None,
    "winner_id": None,
    "winning_team_id": None # Explicitly add winning_team_id
}

dummy_ncaab_game = {
    "id": "NCAAB999002",
    "game_id": "NCAAB999002",
    "status": "scheduled",
    "start_time": datetime.now(pytz.UTC).isoformat(),
    "home_team_id": 201,
    "away_team_id": 202,
    "teams": [
        {"id": 201, "display_name": "Dummy Duke"},
        {"id": 202, "display_name": "Dummy UNC"}
    ],
    "home_team": {"id": 201, "display_name": "Dummy Duke"},
    "away_team": {"id": 202, "display_name": "Dummy UNC"},
    "odds": [
        {
            "book_id": 15,
            "home_tickets": 0.18, # Fade target (<0.20)
            "home_money": 0.12,  # Fade target (<0.20)
            "away_tickets": 0.82,
            "away_money": 0.88
        }
    ],
     "markets": {
         "15": {
             "event": {
                 "spread": [
                     {"team_id": 201, "value": +3.0, "odds": -110}, # Fade target spread
                     {"team_id": 202, "value": -3.0, "odds": -110}
                 ],
                 "moneyline": [],
                 "total": []
             }
         }
    },
    "spread": [
        {"team_id": 201, "value": +3.0, "odds": -110},
        {"team_id": 202, "value": -3.0, "odds": -110}
    ],
    "num_bets": 500,
    "status_display": "Scheduled",
    "boxscore": None,
    "winner_id": None,
    "winning_team_id": None
}

# --- Payload for DB Function ---
nba_payload = {
    "metadata": {"source": "dummy_data_script", "timestamp": datetime.now(pytz.UTC).isoformat()},
    "data": {
        "games": [dummy_nba_game]
    }
}

ncaab_payload = {
    "metadata": {"source": "dummy_data_script", "timestamp": datetime.now(pytz.UTC).isoformat()},
    "data": {
        "games": [dummy_ncaab_game]
    }
}

# --- DB Update Function (adapted from db/game_repo.py) ---
def update_or_insert_dummy_data(collection, data, date):
    """Updates existing data or inserts new data into MongoDB."""
    try:
        if not data or not isinstance(data, dict):
            raise ValueError("Invalid data format")

        document = {
            "date": date,
            "metadata": data.get("metadata", {}),
            "data": data.get("data", {}) # Store the whole payload under 'data' key
        }

        result = collection.update_one(
            {"date": date},
            {"$set": document},
            upsert=True
        )

        if result.upserted_id:
            logger.info(f"Inserted dummy data for date {date} into {collection.name}. Upserted ID: {result.upserted_id}")
        elif result.matched_count:
            logger.info(f"Updated dummy data for date {date} in {collection.name}. Matched: {result.matched_count}, Modified: {result.modified_count}")
        else:
             logger.warning(f"Update operation for dummy data on {date} in {collection.name} resulted in no changes (maybe data was identical?).")

        return "updated" if result.matched_count else "inserted"
    except Exception as e:
        logger.error(f"Error in update_or_insert_dummy_data for {collection.name}: {e}")
        raise

# --- Execute Inserts ---
try:
    logger.info(f"Attempting to insert/update dummy NBA data for date: {today_date_str}")
    update_or_insert_dummy_data(nba_collection, nba_payload, today_date_str)

    # logger.info(f"Attempting to insert/update dummy NCAAB data for date: {today_date_str}")
    # update_or_insert_dummy_data(ncaab_collection, ncaab_payload, today_date_str) # Skip NCAAB for isolated NBA test

    logger.info("Dummy data insertion script finished successfully.")

except Exception as e:
    logger.error(f"Script failed during DB update: {e}")
    if client:
        client.close()
    exit(1)
finally:
    if client:
        client.close()
        logger.info("MongoDB connection closed.")