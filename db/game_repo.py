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
        
        games = list(collection.aggregate(pipeline))
        
        # Process games for response
        for game in games:
            try:
                game['home_team'] = next(t for t in game['teams'] if t['id'] == game['home_team_id'])
                game['away_team'] = next(t for t in game['teams'] if t['id'] == game['away_team_id'])
                
                # Process boxscore for completed games
                if game['status'].lower() in ['complete', 'closed'] and game.get('boxscore'):
                    if not game.get('winning_team_id'):
                        home_score = game['boxscore'].get('total_home_points', 0)
                        away_score = game['boxscore'].get('total_away_points', 0)
                        if home_score > away_score:
                            game['winning_team_id'] = game['home_team_id']
                        elif away_score > home_score:
                            game['winning_team_id'] = game['away_team_id']
                
                if game.get('markets'):
                    game['spread'] = game['markets'].get('spread', [])
                    game['moneyline'] = game['markets'].get('moneyline', [])
                    game['total'] = game['markets'].get('total', [])
                    del game['markets']
                
                del game['home_team_id']
                del game['away_team_id']
                del game['teams']
            except Exception as e:
                logger.error(f"Error processing game {game.get('game_id')}: {e}")
                continue
        
        return games
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
        
        games = list(collection.aggregate(pipeline))
        
        # Process games for response (same processing as get_scheduled_games)
        for game in games:
            try:
                game['home_team'] = next(t for t in game['teams'] if t['id'] == game['home_team_id'])
                game['away_team'] = next(t for t in game['teams'] if t['id'] == game['away_team_id'])
                
                # Process boxscore for completed games
                if game['status'].lower() in ['complete', 'closed'] and game.get('boxscore'):
                    if not game.get('winning_team_id'):
                        home_score = game['boxscore'].get('total_home_points', 0)
                        away_score = game['boxscore'].get('total_away_points', 0)
                        if home_score > away_score:
                            game['winning_team_id'] = game['home_team_id']
                        elif away_score > home_score:
                            game['winning_team_id'] = game['away_team_id']
                
                if game.get('markets'):
                    game['spread'] = game['markets'].get('spread', [])
                    game['moneyline'] = game['markets'].get('moneyline', [])
                    game['total'] = game['markets'].get('total', [])
                    del game['markets']
                
                del game['home_team_id']
                del game['away_team_id']
                del game['teams']
            except Exception as e:
                logger.error(f"Error processing game {game.get('game_id')}: {e}")
                continue
        
        return games
    except Exception as e:
        logger.error(f"Error in get_game_by_team: {e}")
        return []