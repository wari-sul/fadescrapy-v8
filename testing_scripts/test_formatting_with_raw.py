import json
import sys
import os
from datetime import datetime

# Add project root to sys.path to allow imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.formatters import format_game_info, format_fade_alert
from utils.game_processing import find_fade_opportunities
from logging_setup import logger # Use configured logger

def process_raw_game_for_testing(raw_game: dict) -> dict:
    """
    Simulates the essential data transformation done by db.get_scheduled_games
    and db._process_game_data for testing purposes.
    """
    processed_game = {}
    try:
        # --- Mimic DB Projection ---
        processed_game['game_id'] = raw_game.get('id')
        processed_game['status'] = raw_game.get('status')
        processed_game['start_time'] = raw_game.get('start_time')
        home_team_id = raw_game.get('home_team_id')
        away_team_id = raw_game.get('away_team_id')
        teams_list = raw_game.get('teams', [])
        # Project market data for book '15' into 'markets' key
        processed_game['markets'] = raw_game.get('markets', {}).get('15', {}).get('event', {})
        # Include other potentially needed fields (add more if formatters/finders need them)
        processed_game['boxscore'] = raw_game.get('boxscore')
        processed_game['winning_team_id'] = raw_game.get('winning_team_id')

        # --- Mimic _process_game_data ---
        if not home_team_id or not away_team_id or not teams_list:
            logger.warning(f"Skipping game due to missing IDs/teams: {processed_game.get('game_id')}")
            return None

        processed_game['home_team'] = next((t for t in teams_list if t.get('id') == home_team_id), None)
        processed_game['away_team'] = next((t for t in teams_list if t.get('id') == away_team_id), None)

        if not processed_game['home_team'] or not processed_game['away_team']:
             logger.warning(f"Could not find home/away team objects for game_id={processed_game.get('game_id')}")
             # Decide if we should return None or continue partially
             # For testing formatting, we need team names, so returning None might be best
             return None

        # Add simplified winner determination if needed (only if status is complete)
        if processed_game.get('status', '').lower() in ['complete', 'closed'] and not processed_game.get('winning_team_id'):
             boxscore = processed_game.get('boxscore')
             if boxscore:
                 home_score = boxscore.get('total_home_points')
                 away_score = boxscore.get('total_away_points')
                 if isinstance(home_score, (int, float)) and isinstance(away_score, (int, float)):
                     if home_score > away_score:
                         processed_game['winning_team_id'] = home_team_id
                     elif away_score > home_score:
                         processed_game['winning_team_id'] = away_team_id

        return processed_game

    except Exception as e:
        logger.error(f"Error processing raw game {raw_game.get('id')}: {e}", exc_info=True)
        return None

def main():
    raw_file_path = os.path.join(project_root, 'raw_api_dumps', 'nba_raw_20250402.json')
    sport = "nba"

    if not os.path.exists(raw_file_path):
        print(f"Error: Raw data file not found at {raw_file_path}")
        return

    try:
        with open(raw_file_path, 'r') as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON from {raw_file_path}: {e}")
        return

    raw_games = raw_data.get('games', [])
    if not raw_games:
        print("No games found in the raw data file.")
        return

    print(f"--- Testing Game Formatting ({len(raw_games)} games) ---")
    all_opportunities = []
    for i, raw_game in enumerate(raw_games):
        print(f"\n--- Processing Game {i+1} (ID: {raw_game.get('id')}) ---")
        processed_game = process_raw_game_for_testing(raw_game)

        if not processed_game:
            print("Failed to process game data.")
            continue

        # Test format_game_info
        formatted_game_info = format_game_info(processed_game, sport)
        print("\nFormatted Game Info (/nba command):")
        print(formatted_game_info)

        # Test find_fade_opportunities
        print("\nFinding Fade Opportunities...")
        opportunities = find_fade_opportunities(processed_game, sport)
        if opportunities:
            print(f"Found {len(opportunities)} fade opportunities.")
            all_opportunities.extend(opportunities) # Store for later formatting
            # Optionally print raw opportunities found
            # for opp in opportunities:
            #     print(f"  - {opp}")
        else:
            print("No fade opportunities found for this game.")

    print(f"\n\n--- Testing Fade Alert Formatting ({len(all_opportunities)} total opportunities) ---")
    if not all_opportunities:
        print("No fade opportunities found overall to format.")
        return

    # Need to re-process games to pass the correct one to format_fade_alert
    game_map = {g.get('id'): g for g in raw_games}

    for i, opp in enumerate(all_opportunities):
        print(f"\n--- Formatting Opportunity {i+1} ---")
        game_id = opp.get('game_id')
        raw_game = game_map.get(game_id)
        if not raw_game:
            print(f"Error: Could not find raw game data for game_id {game_id} to format alert.")
            continue

        processed_game = process_raw_game_for_testing(raw_game)
        if not processed_game:
             print(f"Error: Failed to re-process game data for game_id {game_id} to format alert.")
             continue

        # Test format_fade_alert (using the opportunity dict directly)
        formatted_alert = format_fade_alert(processed_game, opp, result_status="pending") # Test pending status
        if formatted_alert:
            print(formatted_alert)
        else:
            print(f"Failed to format fade alert for opportunity: {opp}")


if __name__ == "__main__":
    main()