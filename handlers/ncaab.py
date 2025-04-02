from datetime import datetime
import asyncio
from aiogram import types, Router, F
from aiogram.filters import Command
from logging_setup import logger
from utils.rate_limiter import rate_limited_command
from utils.formatters import format_game_info
from utils.message_helpers import send_games_in_chunks
from tasks.fade_alerts import update_fade_alerts
from utils.game_processing import fetch_and_process_games # Correct location
from tasks.fade_alerts import process_new_fade_alerts # Correct location and likely intended function
# Import specific functions instead of the whole db module
from db.connection import get_ncaab_collection
from db.game_repo import get_game_by_team
from db.utils import get_eastern_time_date

# Create a router for NCAAB commands
router = Router()

@router.message(Command("ncaab"))
@rate_limited_command("Please wait before checking NCAAB games again.")
async def cmd_ncaab(message: types.Message):
    """Handle /ncaab command."""
    try:
        args = message.text.split()
        date_str = args[1] if len(args) > 1 else None

        if date_str:
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

        logger.info(f"User {message.from_user.id} requested NCAAB games for {date}")
        games = await fetch_and_process_games("ncaab", date)

        if not games:
            await message.answer(f"🏫 No NCAAB games found scheduled for {date}.")
            return

        await message.answer(f"🏫 <b>NCAAB Games for {date}</b> ({time_str})")
        await send_games_in_chunks(message, games, "ncaab")

    except Exception as e:
        logger.error(f"Error in cmd_ncaab: {e}", exc_info=True)
        await message.answer("❌ Sorry, an error occurred while retrieving NCAAB games.")

@router.message(Command("ncaabteam"))
@rate_limited_command("Please wait before searching NCAAB teams again.")
async def cmd_ncaabteam(message: types.Message):
    """Handle /ncaabteam command."""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            await message.answer(
                "❌ Please provide a college team name.\nExample: `/ncaabteam Duke`"
            )
            return

        team_name = args[1].strip()
        date, time_str = get_eastern_time_date()

        logger.info(f"User {message.from_user.id} searched NCAAB teams for '{team_name}' on {date}")
        await fetch_and_process_games("ncaab", date)
        
        # Run the synchronous DB operation in a thread pool
        loop = asyncio.get_running_loop()
        games = await loop.run_in_executor(
            None, 
            # Use the imported functions and collection getter
            lambda: get_game_by_team(get_ncaab_collection(), date, team_name)
        )

        if not games:
            await message.answer(
                f"🏫 No NCAAB games found involving '{team_name}' for today ({date}). Check spelling?"
            )
            return

        await message.answer(f"🏫 <b>NCAAB Games involving '{team_name}' for {date}</b> ({time_str})")
        for game in games:
            game_info = format_game_info(game, "ncaab")
            await message.answer(game_info)
            await asyncio.sleep(0.1)

    except Exception as e:
        logger.error(f"Error in cmd_ncaabteam: {e}", exc_info=True)
        await message.answer("❌ Sorry, an error occurred searching NCAAB team games.")

@router.message(Command("fadencaab"))
@rate_limited_command("Please wait before checking NCAAB fade alerts again.")
async def cmd_fadencaab(message: types.Message):
    """Handle /fadencaab command - Show NCAAB fade betting opportunities."""
    logger.info(f"User {message.from_user.id} requested NCAAB fade alerts.")
    try:
        date, time_str = get_eastern_time_date()
        games = await fetch_and_process_games("ncaab", date)

        if not games:
            await message.answer(f"🏫 No NCAAB games found for today ({date}) to analyze.")
            return

        await message.answer(f"🔍 Analyzing NCAAB games for fade opportunities ({time_str})...")
        # Use the correctly imported function name (and removed message arg)
        fade_messages = await process_new_fade_alerts(games, "ncaab") # Removed message argument
        
        if not fade_messages:
            await message.answer("✅ No significant NCAAB fade opportunities found based on current criteria.")
        else:
            for alert_msg in fade_messages:
                await message.answer(alert_msg)
                await asyncio.sleep(0.1) # Small delay between messages

    except Exception as e:
        logger.error(f"Error in cmd_fadencaab: {e}", exc_info=True)
        await message.answer("❌ An error occurred processing NCAAB fade opportunities.")

def register_ncaab_handlers(dp):
    """Register all NCAAB command handlers with the dispatcher."""
    dp.include_router(router)