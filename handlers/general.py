from aiogram import Dispatcher, types
from aiogram.filters import Command
from logging_setup import logger
import db
from utils.rate_limiter import rate_limited_command

async def cmd_start(message: types.Message):
    """Handle /start command."""
    user = message.from_user
    logger.info(f"User started bot: ID={user.id}, Name='{user.full_name}', Username=@{user.username}")

    # Check if user just joined (optional, requires DB lookup)
    # is_new_user = await db.is_new_user(user.id)
    # if is_new_user:
    #     await db.record_user_join(user.id, user.username, user.full_name)

    eastern_date, eastern_time = db.get_eastern_time_date()
    await message.answer(
        f"Hello, <b>{user.full_name}</b>! 👋\n\n"
        f"Welcome to the Sports Betting Info Bot.\n"
        f"I provide game schedules, scores, betting odds, and fade opportunities for NBA and NCAAB.\n\n"
        f"Use /help to see the full list of available commands.\n\n"
        f"Current Eastern Time: {eastern_date} {eastern_time}"
    )

async def cmd_help(message: types.Message):
    """Handle /help command."""
    from config import is_admin
    eastern_date, eastern_time = db.get_eastern_time_date()

    # Base help text for all users
    help_text = f"""
<b>Sports Betting Info Bot Commands:</b>

📅 <b>General:</b>
/start - Display the welcome message.
/help - Show this help information.

🏀 <b>NBA:</b>
/nba [YYYYMMDD] - Get NBA games & odds for today or a specific date.
/nbateam [team name] - Search today's NBA games by team name (e.g., Lakers).
/fadenba - Show potential NBA fade betting opportunities for today.

🏫 <b>NCAAB (College Basketball):</b>
/ncaab [YYYYMMDD] - Get NCAAB games & odds for today or a specific date.
/ncaabteam [team name] - Search today's NCAAB games by team name (e.g., Duke).
/fadencaab - Show potential NCAAB fade opportunities for today.

📊 <b>Fade Alerts:</b>
/fades - Show all fade opportunities for today (NBA & NCAAB).
/fadestats - View historical performance of fade alerts (win rates by rating).
/fadehistory - Show results of the most recent fade alerts.

<i>Fade alerts identify situations where public betting patterns suggest potential value in betting against the public favorite. Use responsibly.</i>
"""

    # Add admin commands if the user is an admin
    if is_admin(message.from_user.id):
        help_text += """
-----------------------------
👮‍♂️ <b>Admin Commands:</b>
/warn [user_id] [reason] - Issue a warning to a user.
/tempban [user_id] [hours] [reason] - Temporarily ban a user.
/userinfo [user_id] - View detailed user activity and history.
/banlist - List currently banned users and remaining time.
/botstats - View bot performance and usage statistics.
/health - Check current system resource usage (CPU, Memory).
/broadcast [message] - Send a message to all known users (use with caution!).
/config [setting] [value] - View or update a bot configuration setting.
/config list - List all configurable settings.
/getlogs [lines] - Retrieve recent bot logs (default 50 lines).
"""

    help_text += f"\n-----------------------------\n🕒 Current Time: {eastern_date} {eastern_time}"
    await message.answer(help_text)

def register_general_handlers(dp: Dispatcher):
    """Register general command handlers."""
    dp.message.register(
        rate_limited_command(cooldown_message="Please wait a moment before using /start again.")(cmd_start),
        Command("start")
    )

    dp.message.register(
        rate_limited_command(cooldown_message="Please wait before requesting /help again.")(cmd_help),
        Command("help")
    )