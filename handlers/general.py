from aiogram import Dispatcher, types
from aiogram.filters import Command
from logging_setup import logger
from db.utils import get_eastern_time_date # Import specific function
from utils.rate_limiter import rate_limited_command

async def cmd_start(message: types.Message):
    """Handle /start command."""
    user = message.from_user
    logger.info(f"User started bot: ID={user.id}, Name='{user.full_name}', Username=@{user.username}")

    # Check if user just joined (optional, requires DB lookup)
    # is_new_user = await db.is_new_user(user.id)
    # if is_new_user:
    #     await db.record_user_join(user.id, user.username, user.full_name)

    eastern_date, eastern_time = get_eastern_time_date()
    await message.answer(
        f"Hello, <b>{user.full_name}</b>! 👋\n\n"
        f"Welcome to the Sports Betting Info Bot.\n"
        f"I provide game schedules, scores, betting odds, and fade opportunities for NBA and NCAAB.\n\n"
        f"Use /help to see the full list of available commands.\n\n"
        f"Current Eastern Time: {eastern_date} {eastern_time}"
    )

async def cmd_help(message: types.Message):
    """Handle /help command."""
    from config import config # Import the config object
    eastern_date, eastern_time = get_eastern_time_date()

    # Base help text for all users
    help_text = f"""
<b>Sports Betting Info Bot Commands:</b>

📅 <b>General:</b>
/start - Display the welcome message.
/help - Show this help information.

 /explain - Explain common betting terms.

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
    if config.is_admin(message.from_user.id): # Call is_admin on the config object
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
 /maintenance [on|off|clear|status] - Manage maintenance mode (uses separate DB).
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

    dp.message.register(
        rate_limited_command(cooldown_message="Please wait before requesting /explain again.")(cmd_explain),
        Command("explain")
    )



async def cmd_explain(message: types.Message):
    """Handle /explain command - Explain common betting terms."""
    logger.info(f"User {message.from_user.id} requested betting term explanations.")
    explanation = (
        "📚 <b>Common Betting Terms Explained:</b>\n\n"
        "🔹 <b>Line/Spread:</b> The number of points used to handicap the favorite team. Betting on the favorite (- points) means they must win by more than the spread. Betting on the underdog (+ points) means they must win outright or lose by less than the spread.\n\n"
        "🔹 <b>Moneyline (ML):</b> A bet on which team will win the game outright, regardless of the point spread. Odds determine the payout (negative odds for favorites, positive for underdogs).\n\n"
        "🔹 <b>Total (Over/Under):</b> A bet on whether the combined final score of both teams will be OVER or UNDER a specific number set by the sportsbook.\n\n"
        "   - <b>Over:</b> Betting the combined score will be HIGHER than the total line.\n"
        "   - <b>Under:</b> Betting the combined score will be LOWER than the total line.\n\n"
        "🔹 <b>Fade:</b> Betting *against* a particular outcome, often one that is heavily favored by the public (high ticket percentage) but not necessarily backed by sharp money (money percentage) or implied odds."
    )
    try:
        await message.answer(explanation, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error sending explanation: {e}", exc_info=True)
        await message.answer("❌ Sorry, couldn't send the explanation.")
