import logging
# Removed direct collection imports; they are passed as arguments to functions
# from .connection import nba_collection, ncaab_collection

# Get logger
logger = logging.getLogger(__name__)

def update_or_insert_data(collection, data, date):
    """Updates existing data or inserts new data into MongoDB."""
    try:
        if not data or not isinstance(data, dict):
            raise ValueError("Invalid data format")
        
        document = {
            "date": date,
            "metadata": data.get("metadata", {}),
            "data": data.get("data", {})
        }
        
        result = collection.update_one(
            {"date": date},
            {"$set": document},
            upsert=True
        )
        
        return "updated" if result.matched_count else "inserted"
    except Exception as e:
        logger.error(f"Error in update_or_insert_data: {e}")
        raise

from typing import Optional # Add Optional for type hint

def _process_game_data(raw_game_data: dict) -> Optional[dict]:
    """
    Helper function to process a single raw game object retrieved from the DB.
    Extracts relevant fields and flattens market data for book 15.
    """
    try:
        game_id = raw_game_data.get('id')
        if not game_id:
            logger.warning("Skipping game processing due to missing game ID.")
            return None

        processed_game = {
            'game_id': game_id,
            'status': raw_game_data.get('status'),
            'status_display': raw_game_data.get('status_display'),
            'start_time': raw_game_data.get('start_time'),
            'num_bets': raw_game_data.get('num_bets'),
            'boxscore': raw_game_data.get('boxscore'),
            'winning_team_id': raw_game_data.get('winner_id'), # Use winner_id from raw data
            'sport': raw_game_data.get('sport'), # Ensure sport is carried over if added before storage
            'date': raw_game_data.get('date'),   # Ensure date is carried over if added before storage
            'home_team': None, # Initialize
            'away_team': None, # Initialize
            'spread': [],      # Initialize market data
            'moneyline': [],   # Initialize market data
            'total': [],       # Initialize market data
        }

        # Extract Team Info
        home_id = raw_game_data.get('home_team_id')
        away_id = raw_game_data.get('away_team_id')
        teams_list = raw_game_data.get('teams')

        if not home_id or not away_id or not isinstance(teams_list, list):
            logger.warning(f"Missing team IDs or teams list for game {game_id}. Cannot extract team objects.")
        else:
            processed_game['home_team'] = next((t for t in teams_list if t.get('id') == home_id), None)
            processed_game['away_team'] = next((t for t in teams_list if t.get('id') == away_id), None)
            if not processed_game['home_team'] or not processed_game['away_team']:
                logger.warning(f"Could not find home/away team objects within teams list for game {game_id}")

        # Determine winner from boxscore if not already present and game complete
        if not processed_game['winning_team_id'] and processed_game['status'] and processed_game['status'].lower() in ['complete', 'closed'] and processed_game['boxscore']:
            home_score = processed_game['boxscore'].get('total_home_points')
            away_score = processed_game['boxscore'].get('total_away_points')
            if isinstance(home_score, (int, float)) and isinstance(away_score, (int, float)):
                if home_score > away_score:
                    processed_game['winning_team_id'] = home_id
                elif away_score > home_score:
                    processed_game['winning_team_id'] = away_id

        # Extract and Flatten Market Data for Book 15
        # Access the nested structure directly from raw_game_data
        markets_book_15 = raw_game_data.get('markets', {}).get('15', {}).get('event', {})

        if markets_book_15 and isinstance(markets_book_15, dict):
            logger.debug(f"Processing markets for game {game_id}: {markets_book_15}")
            processed_game['spread'] = markets_book_15.get('spread', [])
            processed_game['moneyline'] = markets_book_15.get('moneyline', [])
            processed_game['total'] = markets_book_15.get('total', [])
            if not processed_game['spread']:
                 logger.warning(f"No spread data found within markets[15][event] for game {game_id}. Market content: {markets_book_15}")
        else:
            logger.warning(f"No markets[15][event] data found for game {game_id}")


        return processed_game # Return the processed game

    except Exception as e:
        game_id_log = raw_game_data.get('id', 'UNKNOWN')
        logger.error(f"Error processing game data for game_id={game_id_log}: {e}", exc_info=True)
        return None # Indicate failure to process


def get_scheduled_games(collection, date):
    """Gets scheduled games for the date with betting data."""
    try:
        pipeline = [
            {"$match": {"date": date}},
            {"$unwind": "$data.games"},
            # Project the entire game object
            {
                "$project": {
                    "_id": 0,
                    "game_data": "$data.games"
                }
            }
        ]
        
        games_raw = list(collection.aggregate(pipeline))
        
        # Process games using the helper function, filtering out None results
        processed_games = [processed for game_doc in games_raw if (processed := _process_game_data(game_doc.get('game_data', {}))) is not None]
        
        return processed_games
    except Exception as e:
        logger.error(f"Error in get_scheduled_games: {e}")
        return []

def get_game_by_team(collection, date, team_name):
    """Gets games for a specific team."""
    try:
        pipeline = [
            {"$match": {"date": date}},
            {"$unwind": "$data.games"},
            {
                "$match": {
                    "data.games.teams": {
                        "$elemMatch": {
                            "display_name": {"$regex": team_name, "$options": "i"}
                        }
                    }
                }
            },
            # Project the entire game object
            {
                "$project": {
                    "_id": 0,
                    "game_data": "$data.games"
                }
            }
        ]
        
        games_raw = list(collection.aggregate(pipeline))
        
        # Process games using the helper function, filtering out None results
        processed_games = [processed for game_doc in games_raw if (processed := _process_game_data(game_doc.get('game_data', {}))) is not None]
        
        return processed_games
    except Exception as e:
        logger.error(f"Error in get_game_by_team: {e}")
        return []

def get_game_by_id(collection, game_id):
    """Gets a single game by its ID and processes it."""
    try:
        # Ensure game_id is treated correctly (might be int or str)
        try:
            # Attempt to convert to int if it looks like one, else keep as str
            processed_game_id = int(game_id) if isinstance(game_id, str) and game_id.isdigit() else game_id
        except ValueError:
            processed_game_id = game_id # Keep as string if conversion fails

        pipeline = [
            # Match the document containing the game (can match on date if needed, but game_id should be unique)
            # Unwind the games array to process each game individually
            {"$unwind": "$data.games"},
            # Match the specific game using its ID
            {"$match": {"data.games.id": processed_game_id}},
            # Project the required fields (same as get_scheduled_games)
            # Project the entire game object
             {
                "$project": {
                    "_id": 0,
                    "game_data": "$data.games"
                }
            },
            # Limit to 1 since we expect only one game per ID
            {"$limit": 1}
        ]

        result = list(collection.aggregate(pipeline))

        if not result:
            logger.warning(f"Game with ID {game_id} not found in collection {collection.name}.")
            return None

        # Process the found game using the helper
        processed_game = _process_game_data(result[0].get('game_data', {}))
        return processed_game

    except Exception as e:
        logger.error(f"Error in get_game_by_id for game_id {game_id}: {e}", exc_info=True)
        return None
