
import asyncio
from typing import Optional, Tuple, List, Dict
from logging_setup import logger
from api import nba, ncaab # Corrected import
import db
from config import config

def determine_winner(game: dict) -> Optional[dict]:
    """Determines winner based on winning_team_id first, then scores if needed."""
    home_team = game.get('home_team')
    away_team = game.get('away_team')
    if not home_team or not away_team:
        return None

    # 1. Check official winning_team_id if provided
    winning_team_id = game.get('winning_team_id')
    if winning_team_id:
        if home_team.get('id') == winning_team_id:
            return home_team
        if away_team.get('id') == winning_team_id:
            return away_team
        # If ID doesn't match known teams, something is wrong
        logger.warning(f"Game {game.get('game_id')}: winning_team_id {winning_team_id} doesn't match home/away teams.")

    # 2. If no official winner ID, check scores from boxscore
    boxscore = game.get('boxscore')
    if boxscore and game.get('status', '').lower() in ['complete', 'closed']:
        home_score = boxscore.get('total_home_points')
        away_score = boxscore.get('total_away_points')

        # Only declare winner if scores are present and not equal
        if home_score is not None and away_score is not None:
             if home_score > away_score:
                  return home_team
             elif away_score > home_score:
                  return away_team

    # If game not complete or scores unavailable, return None
    return None

def get_spread_info(game: dict, team_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Get spread value (as string) and odds (as string) for a team."""
    try:
        # Corrected path: The spread list is directly under the 'spread' key after DB processing
        spreads = game.get('spread', []) # Look directly for 'spread' key
        if not isinstance(spreads, list): return None, None

        for spread_data in spreads:
             # Check if spread_data is a dict and has the required keys
             if isinstance(spread_data, dict) and spread_data.get('team_id') == team_id:
                  value = spread_data.get('value') # e.g., -7.5, +3.0
                  odds = spread_data.get('odds')   # e.g., -110, +100

                  # Return as strings, handle potential None values
                  return str(value) if value is not None else None, str(odds) if odds is not None else None
                  
        logger.debug(f"Team {team_id} not found in spread data for game {game.get('id') or game.get('game_id')}")
    except Exception as e:
        logger.error(f"Error extracting spread info for team {team_id} in game {game.get('id') or game.get('game_id')}: {e}")
    return None, None

def get_bet_percentages(game: dict, team_id: int) -> Tuple[Optional[float], Optional[float]]:
    """Get betting percentages (tickets and money) for a team's spread."""
    try:
        odds_list = game.get('odds', [])
        if not isinstance(odds_list, list):
            logger.debug(f"No odds data found or invalid format for game {game.get('id') or game.get('game_id')}")
            return None, None

        # Find the odds object for book_id 15 (DraftKings)
        dk_odds = next((o for o in odds_list if isinstance(o, dict) and o.get('book_id') == 15), None)

        if not dk_odds:
            logger.debug(f"No odds found for book_id 15 in game {game.get('id') or game.get('game_id')}")
            return None, None

        # Determine if the requested team_id is home or away
        home_id = game.get('home_team_id') or game.get('home_team', {}).get('id')
        
        tickets_pct = None
        money_pct = None

        if team_id == home_id:
            tickets_pct = dk_odds.get('home_tickets')
            money_pct = dk_odds.get('home_money')
        else: # Assume it's the away team
            tickets_pct = dk_odds.get('away_tickets')
            money_pct = dk_odds.get('away_money')

        # Convert decimal (0.5) to percentage (50.0) if not None
        tickets_float = float(tickets_pct * 100) if tickets_pct is not None else None
        money_float = float(money_pct * 100) if money_pct is not None else None

        return tickets_float, money_float

    except Exception as e:
        logger.error(f"Error extracting bet percentages for team {team_id} in game {game.get('id') or game.get('game_id')}: {e}", exc_info=True)

    return None, None

async def fetch_and_store_data(date: Optional[str] = None, sport: str = "nba") -> bool:
    """Fetches and stores sports data, handling potential API errors."""
    max_retries = await config.get_setting('max_retries', 3)
    collection = db.nba_collection if sport == "nba" else db.ncaab_collection
    fetch_func = nba.get_nba_data if sport == "nba" else ncaab.get_ncaab_data # Use imported modules

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} fetching {sport.upper()} data for date: {date or 'today'}")
            
            # Direct call - these are synchronous functions
            data = fetch_func(date)

            if data:
                # Convert potentially blocking operation to a background task
                target_date = date or db.get_eastern_time_date()[0]  # This is synchronous
                
                # Run the synchronous DB operation in a thread pool
                loop = asyncio.get_running_loop()
                # Wrap the list of games ('data') into the dict structure expected by the DB function
                db_payload = {"metadata": {}, "data": {"games": data}}
                result = await loop.run_in_executor(
                    None, lambda: db.update_or_insert_data(collection, db_payload, target_date)
                )
                
                logger.info(f"{sport.upper()} data storage result for {target_date}: {result}")
                return True  # Success
            else:
                logger.warning(f"Attempt {attempt + 1}: No data returned from {sport.upper()} API for {date or 'today'}.")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # General errors
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {sport.upper()} data (Attempt {attempt + 1}).")
            await asyncio.sleep(5 * (attempt + 1))
        except Exception as e:
            logger.error(f"Unexpected error in fetch_and_store_data for {sport} (Attempt {attempt + 1}): {e}", exc_info=True)
            await asyncio.sleep(5 * (attempt + 1))  # Wait before retry

    logger.error(f"Failed to fetch and store {sport.upper()} data after {max_retries} attempts for {date or 'today'}.")
    return False  # Failed after all retries

async def fetch_and_process_games(sport: str, date: str) -> list:
    """Fetch games and process them for display."""
    try:
        # Fetch the data first
        success = await fetch_and_store_data(date=date, sport=sport)
        if not success:
            logger.warning(f"Failed to fetch {sport.upper()} data for {date}")
            return []
            
        # Get games from database
        collection = db.nba_collection if sport == "nba" else db.ncaab_collection
        
        # Run the synchronous DB operation in a thread pool
        loop = asyncio.get_running_loop()
        games = await loop.run_in_executor(
            None, lambda: db.get_scheduled_games(collection, date)
        )
        
        if not games:
            logger.info(f"No {sport.upper()} games found for {date}")
            
        return games
    except Exception as e:
        logger.error(f"Error in fetch_and_process_games for {sport}: {e}", exc_info=True)
        return []

def determine_opponent_spread_result(game: dict, fade_team_id: int, fade_team_spread: float) -> Optional[bool]:
    """
    Determines if the opponent of the fade_team covered their spread.
    Returns True if opponent covered (fade won), False if opponent failed (fade lost), None if push/error.
    """
    try:
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        boxscore = game.get('boxscore')
        if not home_team or not away_team or not boxscore:
            return None # Not enough data

        home_id = home_team.get('id')
        away_id = away_team.get('id')
        home_score = boxscore.get('total_home_points')
        away_score = boxscore.get('total_away_points')

        if home_score is None or away_score is None:
            return None # Scores missing

        # Identify opponent
        if fade_team_id == home_id:
             opponent_id = away_id
             opponent_score = away_score
             fade_score = home_score
        elif fade_team_id == away_id:
             opponent_id = home_id
             opponent_score = home_score
             fade_score = away_score
        else:
             logger.warning(f"fade_team_id {fade_team_id} not in game {game.get('game_id')}")
             return None

        # The opponent's spread is simply the negative of the fade_team's spread
        opponent_spread = -fade_team_spread

        # Calculate opponent's margin vs their spread
        opponent_margin = opponent_score - fade_score
        result_margin = opponent_margin + opponent_spread

        if result_margin > 0:
             return True # Opponent covered, Fade Won
        elif result_margin < 0:
             return False # Opponent failed to cover, Fade Lost
        else:
             return None # Push

    except Exception as e:
        logger.error(f"Error determining opponent spread result for game {game.get('game_id')}: {e}", exc_info=True)
        return None