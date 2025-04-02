import asyncio
from datetime import datetime
from aiogram import Dispatcher, types
from aiogram.filters import Command
from logging_setup import logger
# Import specific functions instead of the whole db module
from db.connection import get_nba_collection
from db.game_repo import get_game_by_team
from db.utils import get_eastern_time_date
from utils.rate_limiter import rate_limited_command
from utils.formatters import format_game_info
from utils.message_helpers import send_games_in_chunks
from utils.game_processing import fetch_and_process_games

async def cmd_nba(message: types.Message):
    """Handle /nba command."""
    try:
        args = message.text.split()
        date_str = args[1] if len(args) > 1 else None

        if date_str:
            # Validate YYYYMMDD format
            if not (date_str.isdigit() and len(date_str) == 8):
                await message.answer(
                    "❌ Invalid date format. Use YYYYMMDD (e.g., 20250324) or omit for today."
                )
                return
            try:
                datetime.strptime(date_str, "%Y%m%d")
                date, time_str = get_eastern_time_date(date_str)
            except ValueError:
                await message.answer(f"❌ Invalid date: {date_str}.")
                return
        else:
            date, time_str = get_eastern_time_date()

        logger.info(f"User {message.from_user.id} requested NBA games for {date}")

        # Fetch games (includes fetch_and_store_data)
        games = await fetch_and_process_games("nba", date)

        if not games:
            await message.answer(f"🏀 No NBA games found scheduled for {date}.")
            return

        # Send header
        await message.answer(f"🏀 <b>NBA Games for {date}</b> ({time_str})")

        # Send games in chunks
        await send_games_in_chunks(message, games, "nba")

    except Exception as e:
        logger.error(f"Error in cmd_nba: {e}", exc_info=True)
        await message.answer("❌ Sorry, an error occurred while retrieving NBA games.")

async def cmd_nbateam(message: types.Message):
    """Handle /nbateam command."""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            await message.answer(
                "❌ Please provide a team name to search for.\n"
                "Example: `/nbateam Lakers`"
            )
            return

        team_name = args[1].strip()
        date, time_str = get_eastern_time_date()  # Search for today's games

        logger.info(f"User {message.from_user.id} searched NBA teams for '{team_name}' on {date}")

        # Fetch today's data first to ensure it's up-to-date
        from utils.game_processing import fetch_and_store_data
        await fetch_and_store_data(date=date, sport="nba")

        # Get games by team name (case-insensitive search)
        # Use the collection getter function
        games = get_game_by_team(get_nba_collection(), date, team_name)

        if not games:
            await message.answer(
                f"🏀 No NBA games found involving a team matching '{team_name}' for today ({date}).\n"
                f"Try checking the spelling or using a different name variation."
            )
            return

        # Send header
        await message.answer(f"🏀 <b>NBA Games involving '{team_name}' for {date}</b> ({time_str})")

        # Send game info
        for game in games:
            game_info = format_game_info(game, "nba")
            await message.answer(game_info)
            await asyncio.sleep(0.1)  # Small delay between messages

    except Exception as e:
        logger.error(f"Error in cmd_nbateam: {e}", exc_info=True)
        await message.answer("❌ Sorry, an error occurred while searching for NBA team games.")

def register_nba_handlers(dp: Dispatcher):
    """Register NBA-related command handlers."""
    dp.message.register(
        rate_limited_command("Please wait before checking NBA games again.")(cmd_nba),
        Command("nba")
    )
    
    dp.message.register(
        rate_limited_command("Please wait before searching NBA teams again.")(cmd_nbateam),
        Command("nbateam")
    )