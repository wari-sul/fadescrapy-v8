import asyncio
from typing import Optional, Tuple, List, Dict, Any # Added Any
from logging_setup import logger
from api import nba, ncaab # Corrected import
# Import specific functions and getters
from db.connection import get_nba_collection, get_ncaab_collection
from db.game_repo import update_or_insert_data, get_scheduled_games
from db.utils import get_eastern_time_date
from config import config
# Removed import of calculate_fade_rating_v2 to break circular dependency

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
        # Look directly for the top-level 'spread' key created by _process_game_data
        spreads = game.get('spread', [])
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

# --- NEW FUNCTION ---
# --- NEW HELPER FUNCTION ---
def calculate_implied_probability(odds: int) -> Optional[float]:
    """Calculates implied probability from American odds."""
    if odds is None:
        return None
    try:
        odds = int(odds)
        if odds < 0: # Negative odds
            return (abs(odds) / (abs(odds) + 100)) * 100
        elif odds > 0: # Positive odds
            return (100 / (odds + 100)) * 100
        else: # Zero odds? Unlikely but handle
             return None
    except (ValueError, TypeError):
        logger.warning(f"Invalid odds format for probability calculation: {odds}")
        return None

# --- REVISED FUNCTION ---
# Placed before get_market_data_book15
def calculate_fade_rating_v2(t_pct: Optional[float], m_pct: Optional[float], implied_prob: Optional[float]) -> int:
    """
    Calculates a 1-5 star rating for a fade opportunity based on the new formula.
    Requires: (T% - IP >= 15%) AND (T% > M%)

    Args:
        t_pct: Ticket percentage for the faded outcome.
        m_pct: Money percentage for the faded outcome.
        implied_prob: Implied probability for the faded outcome.

    Returns:
        An integer rating from 0 to 5.
    """
    if None in [t_pct, m_pct, implied_prob]:
        return 0 # Cannot rate without all data points

    # Base condition check
    difference = t_pct - implied_prob
    if not (difference >= 15.0 and t_pct > m_pct):
        return 0 # Does not meet minimum fade criteria

    # Calculate stars
    stars = 1 # Start with 1 star for meeting base criteria

    # Add stars based on difference magnitude
    if difference >= 25.0:
        stars += 1
    if difference >= 35.0:
        stars += 1

    # Add stars based on Ticket % magnitude
    if t_pct >= 85.0:
        stars += 1
    if t_pct >= 95.0:
        stars += 1

    # Cap at 5 stars
    return min(stars, 5)

# --- REMOVED FUNCTION ---
# get_market_data_book15 is no longer needed as we flatten the data in _process_game_data

# --- REVISED FUNCTION ---
def find_fade_opportunities(game: dict, sport: str) -> List[Dict[str, Any]]:
    """
    Analyzes a game's betting data (book_id 15) using the Ticket% vs Implied Probability formula.

    Args:
        game: The game data dictionary.
        sport: The sport ('nba' or 'ncaab').

    Returns:
        A list of dictionaries, each representing a fade opportunity.
    """
    # --- Add Diagnostic Logging ---
    game_id_log = game.get('id') or game.get('game_id', 'N/A')
    logger.info(f"[find_fade_opportunities] Called for game {game_id_log}, sport {sport}.")
    # --- End Diagnostic Logging ---

    opportunities = []
    game_id = game.get('id') or game.get('game_id')
    # Get team IDs from the nested team objects added by _process_game_data
    home_team = game.get('home_team')
    away_team = game.get('away_team')
    home_team_id = home_team.get('id') if home_team else None
    away_team_id = away_team.get('id') if away_team else None

    if not game_id or not home_team_id or not away_team_id:
        logger.warning(f"[find_fade_opportunities] Returning early: Missing critical IDs in game data: game_id={game_id}, home_id={home_team_id}, away_id={away_team_id}")
        return []

    # --- Add Detailed Market Data Logging ---
    spread_outcomes = game.get('spread') # Get potential list or None
    total_outcomes = game.get('total')
    moneyline_outcomes = game.get('moneyline')
    logger.debug(f"[find_fade_opportunities] Game {game_id} market data received: "
                 f"spread={type(spread_outcomes).__name__} (len={len(spread_outcomes) if isinstance(spread_outcomes, list) else 'N/A'}), "
                 f"total={type(total_outcomes).__name__} (len={len(total_outcomes) if isinstance(total_outcomes, list) else 'N/A'}), "
                 f"moneyline={type(moneyline_outcomes).__name__} (len={len(moneyline_outcomes) if isinstance(moneyline_outcomes, list) else 'N/A'})")
    # Ensure they are lists for the check below, default to empty list if None or not list
    spread_outcomes = spread_outcomes if isinstance(spread_outcomes, list) else []
    total_outcomes = total_outcomes if isinstance(total_outcomes, list) else []
    moneyline_outcomes = moneyline_outcomes if isinstance(moneyline_outcomes, list) else []
    # --- End Detailed Market Data Logging ---

    if not spread_outcomes and not total_outcomes and not moneyline_outcomes:
        # Log the actual game object keys if markets are missing
        logger.warning(f"[find_fade_opportunities] No market outcomes (spread, total, moneyline lists are all empty) found in game data for {game_id}. Game keys: {list(game.keys())}. Returning empty list.")
        return []

    # Thresholds
    threshold_overvalued = 15.0 # Ticket% - Implied Probability >= 15%

    # --- Process Helper ---
    def _process_outcome(outcome: dict, market_type: str):
        """Processes a single market outcome for fade opportunities."""
        logger.info(f"[find_fade_opportunities._process_outcome] ENTERED for game {game_id}, market {market_type}. Outcome keys: {list(outcome.keys()) if isinstance(outcome, dict) else 'Not a dict'}") # Log entry
        nonlocal opportunities # Allow modification of the outer list
        try:
            odds = outcome.get('odds')
            # Access bet_info directly from the outcome
            bet_info = outcome.get('bet_info', {})
            tickets_pct_raw = bet_info.get('tickets', {}).get('percent')
            money_pct_raw = bet_info.get('money', {}).get('percent')
            side = outcome.get('side')
            value = outcome.get('value') # Spread/Total line

            # Convert percentages to float
            t_pct = float(tickets_pct_raw) if tickets_pct_raw is not None else None
            m_pct = float(money_pct_raw) if money_pct_raw is not None else None

            if None in [odds, t_pct, m_pct, side]:
                logger.info(f"[find_fade_opportunities._process_outcome] Skipping outcome for game {game_id} due to missing data (odds={odds}, t_pct={t_pct}, m_pct={m_pct}, side={side}). Outcome: {outcome}") # Changed to INFO
                return # Use return inside helper

            implied_prob = calculate_implied_probability(odds)
            if implied_prob is None:
                logger.info(f"[find_fade_opportunities._process_outcome] Skipping outcome for game {game_id} due to invalid odds for IP calc: {odds}. Outcome: {outcome}") # Changed to INFO
                return # Use return inside helper

            # Apply the new formula conditions (INDENTED)
            is_overvalued = (t_pct - implied_prob) >= threshold_overvalued
            is_public_driven = t_pct > m_pct

            # --- ADD DETAILED LOGGING FOR CHECK (INDENTED) ---
            logger.debug(f"[find_fade_opportunities._process_outcome] Game {game_id}, Market {market_type}, Side {side}, Value {value}: "
                         f"t_pct={t_pct:.1f}, m_pct={m_pct:.1f}, odds={odds}, implied_prob={implied_prob:.1f}, "
                         f"threshold={threshold_overvalued:.1f} -> is_overvalued={is_overvalued}, is_public_driven={is_public_driven}")
            # --- END DETAILED LOGGING ---

            if is_overvalued and is_public_driven:
                # --- ADD LOGGING ---
                logger.info(f"[find_fade_opportunities._process_outcome] Fade condition MET for game {game_id}, market {market_type}, side {side}. Appending opportunity.")
                # --- END LOGGING ---
                # Calculate rating
                rating = calculate_fade_rating_v2(t_pct, m_pct, implied_prob)

                # Determine the label for the faded outcome based on market_type passed to helper
                if market_type == 'spread' or market_type == 'moneyline':
                    faded_label = 'Home' if side == 'home' else 'Away'
                elif market_type == 'total':
                    faded_label = 'Over' if side == 'over' else 'Under'
                else:
                    faded_label = side # Fallback (shouldn't happen with current structure)

                reason = f"T% ({t_pct:.1f}) - IP ({implied_prob:.1f}) >= {threshold_overvalued} AND T% > M% ({m_pct:.1f})"

                opportunities.append({
                    'game_id': game_id,
                    'sport': sport,
                    'market': market_type.capitalize(), # Capitalize (Spread, Total, Moneyline)
                    'faded_outcome_label': faded_label, # Home, Away, Over, Under
                    'faded_value': value, # The actual line/total value being faded
                    'odds': odds,
                    'implied_probability': round(implied_prob, 2),
                    'T%': t_pct, # Already float
                    'M%': m_pct, # Already float
                    'rating': rating,
                    'reason': reason,
                })
        except Exception as e:
             logger.error(f"Error processing outcome {outcome} in game {game_id}: {e}", exc_info=True)
    # --- End Helper ---

    # --- Log lengths before loops ---
    logger.info(f"[find_fade_opportunities] Before loops for game {game_id}: "
                f"spread_outcomes len={len(spread_outcomes)}, "
                f"total_outcomes len={len(total_outcomes)}, "
                f"moneyline_outcomes len={len(moneyline_outcomes)}")
    # --- End log ---

    # --- Check Each Market Outcome using Helper --- (Corrected Indentation)
    for outcome in spread_outcomes:
        _process_outcome(outcome, 'spread')
    for outcome in total_outcomes:
        _process_outcome(outcome, 'total')
    for outcome in moneyline_outcomes:
        _process_outcome(outcome, 'moneyline')

    return opportunities # Corrected Indentation

# # Helper function to check conditions for a specific outcome
#     def check_fade(market: str, outcome_label: str, T_pct: Optional[float], M_pct: Optional[float]):
#         if T_pct is None or M_pct is None:
#             return None # Skip if data is missing
#
#         is_ml = market == 'Moneyline'
#         threshold_disc = threshold_discrepancy_ml if is_ml else threshold_discrepancy_spread_total
#
#         reason = None
#         if T_pct >= threshold_consensus:
#             reason = f"High T% (>= {threshold_consensus}%)"
#         elif M_pct >= threshold_consensus:
#             reason = f"High M% (>= {threshold_consensus}%)"
#         elif T_pct >= threshold_discrepancy_ticket_min and (T_pct - M_pct >= threshold_disc):
#             reason = f"Discrepancy (T% >= {threshold_discrepancy_ticket_min}%, T%-M% >= {threshold_disc}%)"
#
#         if reason:
#             return {
#                 'game_id': game_id,
#                 'sport': sport,
#                 'market': market,
#                 'faded_outcome_label': outcome_label, # e.g., "Home Spread", "Over"
#                 'T%': T_pct,
#                 'M%': M_pct,
#                 'reason': reason,
#                 'threshold_used': threshold_disc if 'Discrepancy' in reason else threshold_consensus
#                 # Add line/total value later if needed for storage/display
#             }
#         return None
#
#     # --- Check Spread ---
#     spread_pct = percentages.get('spread', {})
#     home_spread_fade = check_fade('Spread', 'Home', spread_pct.get('home_T%'), spread_pct.get('home_M%'))
#     away_spread_fade = check_fade('Spread', 'Away', spread_pct.get('away_T%'), spread_pct.get('away_M%'))
#     if home_spread_fade: opportunities.append(home_spread_fade)
#     if away_spread_fade: opportunities.append(away_spread_fade)
#
#     # --- Check Total ---
#     total_pct = percentages.get('total', {})
#     over_fade = check_fade('Total', 'Over', total_pct.get('over_T%'), total_pct.get('over_M%'))
#     under_fade = check_fade('Total', 'Under', total_pct.get('under_T%'), total_pct.get('under_M%'))
#     if over_fade: opportunities.append(over_fade)
#     if under_fade: opportunities.append(under_fade)
#
#     # --- Check Moneyline ---
#     ml_pct = percentages.get('moneyline', {})
#     home_ml_fade = check_fade('Moneyline', 'Home', ml_pct.get('home_T%'), ml_pct.get('home_M%'))
#     away_ml_fade = check_fade('Moneyline', 'Away', ml_pct.get('away_T%'), ml_pct.get('away_M%'))
#     if home_ml_fade: opportunities.append(home_ml_fade)
#     if away_ml_fade: opportunities.append(away_ml_fade)
#
#     # Add specific line/total values if needed (example for spread)
#     # This might be better done when storing/formatting the alert
#     for opp in opportunities:
#         if opp['market'] == 'Spread':
#              team_id_to_check = home_team_id if opp['faded_outcome_label'] == 'Home' else away_team_id
#              spread_val, _ = get_spread_info(game, team_id_to_check)
#              opp['faded_value'] = spread_val # Store the spread value being faded
#         # TODO: Add similar logic for Total line and ML odds if required
#
#     # return opportunities # This return is commented out as it's part of the dead code block

async def fetch_and_store_data(date: Optional[str] = None, sport: str = "nba") -> bool:
    """Fetches and stores sports data, handling potential API errors."""
    max_retries = await config.get_setting('max_retries', 3)
    collection = get_nba_collection() if sport == "nba" else get_ncaab_collection()
    fetch_func = nba.get_nba_data if sport == "nba" else ncaab.get_ncaab_data # Use imported modules

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} fetching {sport.upper()} data for date: {date or 'today'}")

            # Direct call - these are synchronous functions
            data = fetch_func(date)

            if data:
                # Convert potentially blocking operation to a background task
                target_date = date or get_eastern_time_date()[0]  # This is synchronous

                # Run the synchronous DB operation in a thread pool
                loop = asyncio.get_running_loop()
                # Wrap the list of games ('data') into the dict structure expected by the DB function
                db_payload = {"metadata": {}, "data": {"games": data}}
                result = await loop.run_in_executor(
                    None, lambda: update_or_insert_data(collection, db_payload, target_date)
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
        collection = get_nba_collection() if sport == "nba" else get_ncaab_collection()

        # Run the synchronous DB operation in a thread pool
        loop = asyncio.get_running_loop()
        games = await loop.run_in_executor(
            None, lambda: get_scheduled_games(collection, date)
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