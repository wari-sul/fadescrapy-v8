import asyncio
import logging
import argparse # Added
from datetime import datetime, timedelta
from typing import Optional # Added for type hinting

# Assuming your project structure allows these imports
from api import nba, ncaab
from utils.game_processing import find_fade_opportunities, get_market_data_book15 # Updated function name
# from db.utils import get_eastern_time_date # No longer needed for default date

# Configure basic logging for the test
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Modified function signature
async def test_logic_for_sport(sport: str, date_str: Optional[str] = None):
    """Fetches data for a specific sport and date, then tests the fade logic."""
    logger.info(f"--- Testing Fade Logic for {sport.upper()} on {date_str or 'Default Date'} ---")
    fetch_func = nba.get_nba_data if sport == "nba" else ncaab.get_ncaab_data

    # Use the provided date_str
    logger.info(f"Fetching {sport.upper()} data (Date: {date_str or 'Default'})...")

    try:
        loop = asyncio.get_running_loop()
        # Pass the specific date_str to the fetch function
        games = await loop.run_in_executor(None, lambda: fetch_func(date_str))

        if not games:
            logger.warning(f"No {sport.upper()} games data returned from API for date: {date_str or 'Default'}.")
            return

        logger.info(f"Fetched {len(games)} {sport.upper()} games. Processing for fades...")

        fades_found_count = 0
        for i, game in enumerate(games):
            game_id = game.get('id') or game.get('game_id', 'N/A')
            home_team = game.get('home_team', {}).get('name', 'N/A')
            away_team = game.get('away_team', {}).get('name', 'N/A')
            logger.info(f"\nProcessing Game {i+1}/{len(games)}: {away_team} @ {home_team} (ID: {game_id})")

            # --- Verification Step 1: Check book_id 15 data extraction ---
            logger.debug("Attempting to extract market data for book_id 15...")
            market_data = get_market_data_book15(game) # Use the updated function
            if market_data:
                logger.info(f"Successfully extracted market data for book_id 15:")
                # Log extracted data for verification (optional, can be verbose)
                # logger.info(f"  Spread: {market_data.get('spread')}")
                # logger.info(f"  Total: {market_data.get('total')}")
                # logger.info(f"  Moneyline: {market_data.get('moneyline')}")

                # --- Verification Step 2: Find Opportunities ---
                opportunities = find_fade_opportunities(game, sport)
                if opportunities:
                    fades_found_count += len(opportunities)
                    logger.info(f"*** Found {len(opportunities)} Fade Opportunities: ***")
                    for opp in opportunities:
                        # Added Implied Probability to log output
                        logger.info(f"  - Market: {opp.get('market')}, Fading: {opp.get('faded_outcome_label')} ({opp.get('faded_value', 'N/A')}), "
                                    f"Odds: {opp.get('odds')}, IP: {opp.get('implied_probability'):.1f}%, "
                                    f"Reason: {opp.get('reason')}, T%: {opp.get('T%'):.1f}, M%: {opp.get('M%'):.1f}")
                else:
                    logger.info("No fade opportunities found based on the formula.")
            else:
                # Log the raw odds data if extraction failed, to help debug keys
                logger.warning(f"Could not extract market data for book_id 15.")
                # Log raw market data if available
                raw_markets = game.get('markets', {})
                dk_market_raw = raw_markets.get('15')
                if dk_market_raw:
                     logger.warning(f"Raw book_id '15' market data: {dk_market_raw}")
                else:
                     logger.warning("No book_id '15' market object found in game data.")


        logger.info(f"--- Finished processing {sport.upper()} for {date_str or 'Default Date'}. Total fades found: {fades_found_count} ---")

    except Exception as e:
        logger.error(f"An error occurred during {sport.upper()} test for {date_str or 'Default Date'}: {e}", exc_info=True)


# Modified main to accept arguments
async def main(sport_to_test: str, date_to_test: Optional[str]):
    await test_logic_for_sport(sport_to_test, date_to_test)

# Added argument parsing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test fade logic for NBA or NCAAB games on a specific date.")
    parser.add_argument("sport", choices=["nba", "ncaab"], help="The sport to test ('nba' or 'ncaab').")
    parser.add_argument("date", nargs='?', default=None, help="Optional date in YYYYMMDD format. Defaults to API default (likely today).")

    args = parser.parse_args()

    # Validate date format if provided
    if args.date and not (args.date.isdigit() and len(args.date) == 8):
         print(f"Error: Invalid date format '{args.date}'. Please use YYYYMMDD.")
         exit(1)
    try:
        if args.date:
            datetime.strptime(args.date, "%Y%m%d")
    except ValueError:
         print(f"Error: Invalid date value '{args.date}'. Please use YYYYMMDD.")
         exit(1)


    asyncio.run(main(args.sport, args.date))