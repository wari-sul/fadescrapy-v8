import logging
from .connection import nba_collection, ncaab_collection

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

def _process_game_data(game: dict) -> Optional[dict]:
    """Helper function to process raw game data from aggregation."""
    try:
        # Ensure essential IDs are present before processing
        home_id = game.get('home_team_id')
        away_id = game.get('away_team_id')
        teams_list = game.get('teams')
        if not home_id or not away_id or not teams_list:
            logger.warning(f"Skipping game processing due to missing IDs/teams list: game_id={game.get('game_id')}")
            return None # Indicate failure to process

        game['home_team'] = next((t for t in teams_list if t.get('id') == home_id), None)
        game['away_team'] = next((t for t in teams_list if t.get('id') == away_id), None)

        if not game['home_team'] or not game['away_team']:
             logger.warning(f"Could not find home/away team objects for game_id={game.get('game_id')}")
             # Continue processing other fields if possible, but log the issue

        # Process boxscore for completed games
        if game.get('status', '').lower() in ['complete', 'closed'] and game.get('boxscore'):
            if not game.get('winning_team_id'):
                home_score = game['boxscore'].get('total_home_points')
                away_score = game['boxscore'].get('total_away_points')
                # Only assign winner if scores are valid numbers
                if isinstance(home_score, (int, float)) and isinstance(away_score, (int, float)):
                    if home_score > away_score:
                        game['winning_team_id'] = home_id
                    elif away_score > home_score:
                        game['winning_team_id'] = away_id

        # Extract market data
        if game.get('markets'):
            game['spread'] = game['markets'].get('spread', [])
            game['moneyline'] = game['markets'].get('moneyline', [])
            game['total'] = game['markets'].get('total', [])
            del game['markets']

        # Clean up raw fields
        if 'home_team_id' in game: del game['home_team_id']
        if 'away_team_id' in game: del game['away_team_id']
        if 'teams' in game: del game['teams']

        return game # Return the processed game

    except Exception as e:
        logger.error(f"Error processing game data for game_id={game.get('game_id')}: {e}", exc_info=True)
        return None # Indicate failure to process


def get_scheduled_games(collection, date):
    """Gets scheduled games for the date with betting data."""
    try:
        pipeline = [
            {"$match": {"date": date}},
            {"$unwind": "$data.games"},
            {
                "$project": {
                    "_id": 0,
                    "game_id": "$data.games.id",
                    "status": "$data.games.status",
                    "status_display": "$data.games.status_display",
                    "start_time": "$data.games.start_time",
                    "num_bets": "$data.games.num_bets",
                    "teams": "$data.games.teams",
                    "home_team_id": "$data.games.home_team_id",
                    "away_team_id": "$data.games.away_team_id",
                    "winning_team_id": "$data.games.winner_id",
                    "boxscore": "$data.games.boxscore",
                    "markets": "$data.games.markets.15.event",
                    "odds": "$data.games.odds" # Added odds field for bet percentages
                }
            }
        ]
        
        games_raw = list(collection.aggregate(pipeline))
        
        # Process games using the helper function, filtering out None results
        processed_games = [processed for game in games_raw if (processed := _process_game_data(game)) is not None]
        
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
            {
                "$project": {
                    "_id": 0,
                    "game_id": "$data.games.id",
                    "status": "$data.games.status",
                    "status_display": "$data.games.status_display",
                    "start_time": "$data.games.start_time",
                    "teams": "$data.games.teams",
                    "home_team_id": "$data.games.home_team_id",
                    "away_team_id": "$data.games.away_team_id",
                    "winning_team_id": "$data.games.winner_id",
                    "boxscore": "$data.games.boxscore",
                    "markets": "$data.games.markets.15.event",
                    "odds": "$data.games.odds" # Added odds field for bet percentages
                }
            }
        ]
        
        games_raw = list(collection.aggregate(pipeline))
        
        # Process games using the helper function, filtering out None results
        processed_games = [processed for game in games_raw if (processed := _process_game_data(game)) is not None]
        
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
            {
                "$project": {
                    "_id": 0,
                    "game_id": "$data.games.id",
                    "status": "$data.games.status",
                    "status_display": "$data.games.status_display",
                    "start_time": "$data.games.start_time",
                    "num_bets": "$data.games.num_bets",
                    "teams": "$data.games.teams",
                    "home_team_id": "$data.games.home_team_id",
                    "away_team_id": "$data.games.away_team_id",
                    "winning_team_id": "$data.games.winner_id",
                    "boxscore": "$data.games.boxscore",
                    "markets": "$data.games.markets.15.event",
                    "odds": "$data.games.odds"
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
        processed_game = _process_game_data(result[0])
        return processed_game

    except Exception as e:
        logger.error(f"Error in get_game_by_id for game_id {game_id}: {e}", exc_info=True)
        return None
