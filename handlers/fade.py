import asyncio
from aiogram import Dispatcher, types
from aiogram.filters import Command
from logging_setup import logger
import db
from utils.rate_limiter import rate_limited_command
from utils.game_processing import fetch_and_process_games
from utils.message_helpers import send_long_message
from tasks.fade_alerts import process_new_fade_alerts # Corrected function name

async def cmd_fadenba(message: types.Message):
    """Handle /fadenba command - Show NBA fade betting opportunities."""
    logger.info(f"User {message.from_user.id} requested NBA fade alerts.")
    try:
        date, time_str = db.get_eastern_time_date()
        games = await fetch_and_process_games("nba", date)
        # --- Add Diagnostic Logging ---
        logger.info(f"[cmd_fadenba] fetch_and_process_games returned {len(games)} games for date {date}.")
        # --- End Diagnostic Logging ---

        if not games:
            await message.answer(f"🏀 No NBA games found for today ({date}) to analyze.")
            return

        await message.answer(f"🔍 Analyzing NBA games for fade opportunities ({time_str})...")
        # --- Add Diagnostic Logging ---
        logger.info(f"[cmd_fadenba] Calling process_new_fade_alerts with {len(games)} games.")
        # --- End Diagnostic Logging ---
        fade_messages = await process_new_fade_alerts(games, "nba")
        # --- Add Diagnostic Logging ---
        logger.info(f"[cmd_fadenba] process_new_fade_alerts returned {len(fade_messages)} messages.")
        # --- End Diagnostic Logging ---
        
        if not fade_messages:
            await message.answer("✅ No significant NBA fade opportunities found based on current criteria.")
        else:
            for alert_msg in fade_messages:
                await message.answer(alert_msg, parse_mode='HTML') # Revert back to HTML
                await asyncio.sleep(0.1) # Small delay between messages

    except Exception as e:
        logger.error(f"Error in cmd_fadenba: {e}", exc_info=True)
        await message.answer("❌ An error occurred processing NBA fade opportunities.")

async def cmd_fadencaab(message: types.Message):
    """Handle /fadencaab command - Show NCAAB fade betting opportunities."""
    logger.info(f"User {message.from_user.id} requested NCAAB fade alerts.")
    try:
        date, time_str = db.get_eastern_time_date()
        games = await fetch_and_process_games("ncaab", date)

        if not games:
            await message.answer(f"🏫 No NCAAB games found for today ({date}) to analyze.")
            return

        await message.answer(f"🔍 Analyzing NCAAB games for fade opportunities ({time_str})...")
        fade_messages = await process_new_fade_alerts(games, "ncaab")
        
        if not fade_messages:
            await message.answer("✅ No significant NCAAB fade opportunities found based on current criteria.")
        else:
            for alert_msg in fade_messages:
                await message.answer(alert_msg, parse_mode='HTML') # Revert back to HTML
                await asyncio.sleep(0.1) # Small delay between messages

    except Exception as e:
        logger.error(f"Error in cmd_fadencaab: {e}", exc_info=True)
        await message.answer("❌ An error occurred processing NCAAB fade opportunities.")

async def cmd_fades(message: types.Message):
    """Handle /fades command - Show today's fade opportunities for both NBA and NCAAB."""
    logger.info(f"User {message.from_user.id} requested all fade alerts.")
    date, time_str = db.get_eastern_time_date()
    await message.answer(f"🔍 Fetching and analyzing games for all fade opportunities ({time_str})...")

    try:
        nba_fade_messages = []
        ncaab_fade_messages = []
        any_nba_games = False
        any_ncaab_games = False

        # Process NBA
        nba_games = await fetch_and_process_games("nba", date)
        if nba_games:
            any_nba_games = True
            nba_fade_messages = await process_new_fade_alerts(nba_games, "nba")
            if not nba_fade_messages:
                 await message.answer("🏀 No significant NBA fade opportunities found.")
        else:
            await message.answer(f"🏀 No NBA games found for today ({date}).")

        await asyncio.sleep(0.5)  # Small delay

        # Process NCAAB
        ncaab_games = await fetch_and_process_games("ncaab", date)
        if ncaab_games:
            any_ncaab_games = True
            ncaab_fade_messages = await process_new_fade_alerts(ncaab_games, "ncaab")
            if not ncaab_fade_messages:
                 await message.answer("🏫 No significant NCAAB fade opportunities found.")
        else:
            await message.answer(f"🏫 No NCAAB games found for today ({date}).")

        # Send collected messages
        all_fade_messages = nba_fade_messages + ncaab_fade_messages
        if all_fade_messages:
            await message.answer("--- Fade Opportunities Found ---")
            for alert_msg in all_fade_messages:
                await message.answer(alert_msg, parse_mode='HTML') # Revert back to HTML
                await asyncio.sleep(0.1)
        elif any_nba_games or any_ncaab_games: # Only say no fades if games were actually checked
             await message.answer("✅ No significant fade opportunities found for either sport.")
        # If no games found for either, messages were already sent above.

        await message.answer("✅ Fade analysis complete.")

    except Exception as e:
        logger.error(f"Error in cmd_fades: {e}", exc_info=True)
        await message.answer("❌ An error occurred processing fade opportunities.")

async def cmd_fadestats(message: types.Message):
    """Handle /fadestats command - Show fade alert performance stats."""
    logger.info(f"User {message.from_user.id} requested fade statistics.")
    try:
        # Run the synchronous DB operations in a thread pool
        loop = asyncio.get_running_loop()
        nba_stats = await loop.run_in_executor(
            None, 
            lambda: db.get_fade_alert_stats(sport="nba")
        )
        ncaab_stats = await loop.run_in_executor(
            None, 
            lambda: db.get_fade_alert_stats(sport="ncaab")
        )

        stats_msg = ["📊 <b>Fade Alert Performance (Last 30 Days)</b>\n"]

        def format_stats(sport_name, icon, stats_list):
            if stats_list:
                stats_msg.append(f"\n{icon} <b>{sport_name} Fade Performance:</b>")
                for stat in stats_list:
                    rating = stat.get('rating', '?')
                    win = stat.get('wins', 0)
                    loss = stat.get('losses', 0)
                    push = stat.get('pushes', 0)
                    total = win + loss + push
                    win_rate = (win / (win + loss) * 100) if win + loss > 0 else 0
                    stars = '⭐' * rating
                    
                    stats_msg.append(
                        f"{stars} ({rating}-Star): {win}W - {loss}L - {push}P "
                        f"({total} total, {win_rate:.1f}% win rate)"
                    )
            else:
                stats_msg.append(f"\n{icon} <b>{sport_name}:</b> No fade performance data available.")

        format_stats("NBA", "🏀", nba_stats)
        format_stats("NCAAB", "🏫", ncaab_stats)

        if len(stats_msg) == 1:  # Only header was added
            stats_msg.append("No fade alert results available for the past 30 days.")

        await message.answer("\n".join(stats_msg))

    except Exception as e:
        logger.error(f"Error in cmd_fadestats: {e}", exc_info=True)
        await message.answer("❌ An error occurred retrieving fade statistics.")

async def cmd_fadehistory(message: types.Message):
    """Handle /fadehistory command - Show recent fade alert results."""
    logger.info(f"User {message.from_user.id} requested fade history.")
    try:
        limit = 5  # Number of recent results per sport
        
        # Run the synchronous DB operations in a thread pool
        loop = asyncio.get_running_loop()
        nba_alerts = await loop.run_in_executor(
            None, 
            lambda: db.get_recent_fade_alerts(sport="nba", limit=limit)
        )
        ncaab_alerts = await loop.run_in_executor(
            None, 
            lambda: db.get_recent_fade_alerts(sport="ncaab", limit=limit)
        )

        history_msg = [f"📜 <b>Recent Fade Alert Results (Last {limit} per sport)</b>\n"]

        def format_history(sport_name, icon, alerts_list):
            if alerts_list:
                history_msg.append(f"\n{icon} <b>{sport_name} Recent Fade Results:</b>")
                for alert in alerts_list:
                    date = alert.get('date', 'N/A')
                    teams = alert.get('teams', 'Unknown Matchup')
                    fade_team = alert.get('fade_team', 'Unknown Team')
                    rating = alert.get('rating', 0)
                    result = alert.get('result', 'unknown').lower()
                    
                    result_icon = '✅' if result == 'win' else '❌' if result == 'loss' else '⚖️' 
                    stars = '⭐' * rating
                    
                    history_msg.append(
                        f"{date}: {teams}\n"
                        f"Faded: {fade_team} {stars} - {result_icon} {result.upper()}"
                    )
            else:
                history_msg.append(f"\n{icon} <b>{sport_name}:</b> No recent fade history.")

        format_history("NBA", "🏀", nba_alerts)
        format_history("NCAAB", "🏫", ncaab_alerts)

        if len(history_msg) == 1:  # Only header added
            history_msg.append("No recent fade alert history found for any sport.")

        # Send potentially long message in chunks
        full_message = "\n".join(filter(None, history_msg))
        await send_long_message(message.chat.id, full_message)

    except Exception as e:
        logger.error(f"Error in cmd_fadehistory: {e}", exc_info=True)
        await message.answer("❌ An error occurred retrieving fade history.")

def register_fade_handlers(dp: Dispatcher):
    """Register fade-related command handlers."""
    dp.message.register(
        rate_limited_command("Please wait before checking NBA fade alerts again.")(cmd_fadenba),
        Command("fadenba")
    )
    
    dp.message.register(
        rate_limited_command("Please wait before checking NCAAB fade alerts again.")(cmd_fadencaab),
        Command("fadencaab")
    )
    
    dp.message.register(
        rate_limited_command("Please wait before requesting all fade alerts again.")(cmd_fades),
        Command("fades")
    )
    
    dp.message.register(
        rate_limited_command("Please wait before requesting fade statistics.")(cmd_fadestats),
        Command("fadestats")
    )
    
    dp.message.register(
        rate_limited_command("Please wait before requesting fade history.")(cmd_fadehistory),
        Command("fadehistory")
    )