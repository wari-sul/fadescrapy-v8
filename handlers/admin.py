from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
import asyncio
import time
from datetime import datetime, timedelta

from config import config # Import config instead of is_admin
from logging_setup import logger
from utils.rate_limiter import rate_limited_command
from utils.message_helpers import send_long_message
from services.user_manager import user_manager
from services.metrics import metrics
from services.alert_monitor import alert_monitor
from db.connection import is_maintenance_mode, set_maintenance_mode, clear_maintenance_collections


router = Router()

@router.message(Command("warn"))
@rate_limited_command()
async def cmd_warn(message: types.Message):
    """Warn a user (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    try:
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            await message.answer(
                "Usage: `/warn <user_id> <reason>`\n"
                "Example: `/warn 123456 Spamming commands`"
            )
            return

        user_id_str = args[1]
        reason = args[2].strip()

        if not user_id_str.isdigit():
            await message.answer(f"❌ Invalid User ID: '{user_id_str}'. Must be an integer.")
            return
        user_id = int(user_id_str)

        if not reason:
            await message.answer("❌ Please provide a reason for the warning.")
            return

        await user_manager.warn_user(user_id, reason, message.from_user.id)
        warning_count = len(user_manager.get_warnings(user_id))

        admin_feedback = f"⚠️ User {user_id} has been warned.\nReason: {reason}\nTotal warnings: {warning_count}"
        user_notification = f"⚠️ You have received warning #{warning_count}.\nReason: {reason}\n\n"

        # Auto-ban logic (e.g., on 3rd warning)
        if warning_count >= 3:
            ban_duration_hours = 24
            ban_reason = f"Automatic {ban_duration_hours}h ban after {warning_count} warnings."
            await user_manager.tempban_user(user_id, ban_duration_hours, ban_reason, message.from_user.id)

            admin_feedback += f"\n\n🚫 User automatically banned for {ban_duration_hours} hours due to repeated warnings."
            user_notification += f"🚫 **You have been automatically banned for {ban_duration_hours} hours.**"
        else:
            user_notification += f"Accumulating multiple warnings ({warning_count}/3) may lead to a temporary ban."

        await message.answer(admin_feedback)

        # Notify the warned user
        try:
            from bot import bot  # Import here to avoid circular imports
            await bot.send_message(user_id, user_notification)
        except TelegramAPIError as e:
            logger.warning(f"Could not notify user {user_id} about warning (they might have blocked the bot): {e}")
        except Exception as e:
            logger.error(f"Error sending warning notification to user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in /warn command: {e}", exc_info=True)
        await message.answer("❌ An error occurred while issuing the warning.")


@router.message(Command("tempban"))
@rate_limited_command()
async def cmd_tempban(message: types.Message):
    """Temporarily ban a user (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    try:
        args = message.text.split(maxsplit=3)
        if len(args) < 4:
            await message.answer(
                "Usage: `/tempban <user_id> <hours> <reason>`\n"
                "Example: `/tempban 123456 48 Repeated spam`"
            )
            return

        user_id_str = args[1]
        duration_str = args[2]
        reason = args[3].strip()

        if not user_id_str.isdigit():
            await message.answer(f"❌ Invalid User ID: '{user_id_str}'. Must be an integer.")
            return
        user_id = int(user_id_str)

        if not duration_str.isdigit():
            await message.answer(f"❌ Invalid duration: '{duration_str}'. Must be an integer number of hours.")
            return
        duration_hours = int(duration_str)

        if not (1 <= duration_hours <= 720):  # Limit ban duration (e.g., 1 hour to 30 days)
            await message.answer("❌ Ban duration must be between 1 and 720 hours.")
            return

        if not reason:
            await message.answer("❌ Please provide a reason for the temporary ban.")
            return

        await user_manager.tempban_user(user_id, duration_hours, reason, message.from_user.id)
        await message.answer(
            f"🚫 User {user_id} has been temporarily banned.\n"
            f"Duration: {duration_hours} hours\n"
            f"Reason: {reason}"
        )

        # Notify the banned user
        try:
            from bot import bot  # Import here to avoid circular imports
            await bot.send_message(
                user_id,
                f"🚫 You have been temporarily banned for **{duration_hours} hours**.\n"
                f"Reason: {reason}\n\n"
                f"You will be able to use most bot features again after the ban expires."
            )
        except TelegramAPIError as e:
            logger.warning(f"Could not notify user {user_id} about ban (they might have blocked the bot): {e}")
        except Exception as e:
            logger.error(f"Error sending ban notification to user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in /tempban command: {e}", exc_info=True)
        await message.answer("❌ An error occurred while processing the temporary ban.")


@router.message(Command("userinfo"))
@rate_limited_command()
async def cmd_userinfo(message: types.Message):
    """View detailed user information and history (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /userinfo [user_id]")
            return

        user_id_str = args[1]
        if not user_id_str.isdigit():
            await message.answer(f"❌ Invalid User ID: '{user_id_str}'. Must be an integer.")
            return
        user_id = int(user_id_str)

        stats = await user_manager.get_user_stats(user_id)
        if not stats:
            # Check if user exists in TG but not in our stats
            try:
                from bot import bot  # Import here to avoid circular imports
                user = await bot.get_chat(user_id)
                await message.answer(f"⚠️ User {user_id} ({user.full_name}) exists but has no activity stats.")
            except TelegramAPIError:
                await message.answer(f"❌ User {user_id} not found in Telegram or our records.")
            except Exception as e:
                logger.error(f"Error checking user existence in TG: {e}", exc_info=True)
                await message.answer(f"❌ User {user_id} not found in our records.")
            return

        current_time = time.time()
        info_msg = [f"👤 <b>User Information - ID: {user_id}</b>"]

        # Basic Info
        join_ts = stats.get('join_date')
        last_seen_ts = stats.get('last_seen', 0)

        join_date_str = datetime.fromtimestamp(join_ts).strftime('%Y-%m-%d %H:%M:%S') if join_ts else "Never"
        last_seen_str = datetime.fromtimestamp(last_seen_ts).strftime('%Y-%m-%d %H:%M:%S') if last_seen_ts else "Never"
        inactive_seconds = current_time - last_seen_ts if last_seen_ts else 0
        inactive_time_str = str(timedelta(seconds=int(inactive_seconds))) if last_seen_ts else "N/A"

        is_currently_banned, ban_reason = await user_manager.is_banned(user_id)
        ban_status = f"Banned (Reason: {ban_reason or 'N/A'})" if is_currently_banned else "Not Banned"

        info_msg.extend([
            f"\n📅 Joined: {join_date_str}",
            f"🕒 Last Active: {last_seen_str} ({inactive_time_str} ago)",
            f"📊 Total Commands Logged: {sum(stats.get('commands', {}).values())}",
            f"🚫 Ban Status: {ban_status}"
        ])

        # Warning History
        warnings = stats.get('warning_history', [])
        if warnings:
            info_msg.append("\n⚠️ <b>Warning History:</b>")
            for i, warn in enumerate(warnings, 1):
                warn_time = datetime.fromtimestamp(warn.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')
                info_msg.append(f"{i}. {warn_time}: {warn.get('reason', 'N/A')} (by {warn.get('by_admin', 'Unknown')})")
        else:
            info_msg.append("\n⚠️ No warnings recorded.")

        # Ban History
        bans = stats.get('ban_history', [])
        if bans:
            info_msg.append("\n🚫 <b>Ban History:</b>")
            for i, ban in enumerate(bans, 1):
                ban_time = datetime.fromtimestamp(ban.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')
                duration = ban.get('duration', 0)
                info_msg.append(f"{i}. {ban_time}: {duration}h ban - {ban.get('reason', 'N/A')} (by {ban.get('by_admin', 'Unknown')})")
        else:
            info_msg.append("\n🚫 No ban history recorded.")

        # Command Usage (Top 10)
        commands_dict = stats.get('commands', {})
        if commands_dict:
            info_msg.append("\n📈 <b>Command Usage (Top 10):</b>")
            sorted_commands = sorted(commands_dict.items(), key=lambda item: item[1], reverse=True)[:10]
            for cmd, count in sorted_commands:
                info_msg.append(f"/{cmd}: {count} times")
        else:
            info_msg.append("\n📈 No command usage recorded.")

        # Send in chunks if needed
        message_text = "\n".join(info_msg)
        await send_long_message(message.chat.id, message_text)

    except Exception as e:
        logger.error(f"Error in /userinfo command: {e}", exc_info=True)
        await message.answer("❌ Error retrieving user information.")


@router.message(Command("banlist"))
@rate_limited_command()
async def cmd_banlist(message: types.Message):
    """View currently banned users (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    try:
        current_time = time.time()
        banned_list_details = []

        # Access safely if UserManager becomes async
        async with user_manager._lock:
            active_bans = {uid: info for uid, info in user_manager.banned_users.items() if info['until'] > current_time}

        if not active_bans:
            await message.answer("✅ No users are currently banned.")
            return

        ban_msg = ["🚫 <b>Currently Banned Users:</b>\n"]
        for user_id, ban_info in active_bans.items():
            time_left_seconds = ban_info['until'] - current_time
            time_left_str = str(timedelta(seconds=int(time_left_seconds)))
            ban_msg.append(
                f"👤 ID: {user_id}\n"
                f"⏳ Remaining: {time_left_str}\n"
                f"📝 Reason: {ban_info.get('reason', 'N/A')}\n"
                f"👮 By Admin: {ban_info.get('by_admin', 'N/A')}\n"
            )

        full_message = "\n".join(ban_msg)
        await send_long_message(message.chat.id, full_message)

    except Exception as e:
        logger.error(f"Error in /banlist command: {e}", exc_info=True)
        await message.answer("❌ Error retrieving ban list.")


@router.message(Command("botstats"))
@rate_limited_command()
async def cmd_botstats(message: types.Message):
    """Displays bot performance and usage statistics (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    try:
        stats = metrics.get_stats()
        stats_msg = ["📊 <b>Bot Performance Statistics</b>\n"]

        stats_msg.append(f"⏱️ Uptime: {stats['uptime']}")
        stats_msg.append(f"🧠 Memory Usage: {stats['memory_usage_mb']:.2f} MB")
        stats_msg.append(f"👥 Active Users Tracked: {stats['total_active_users_tracked']}")
        stats_msg.append(f"📈 Total Commands Logged: {stats['total_commands_logged']}")
        stats_msg.append(f"❗️ Total Errors Logged: {stats['total_errors_logged']}")
        stats_msg.append(f"📉 Overall Error Rate: {stats['overall_error_rate']:.2f}%")

        if stats["command_stats"]:
            stats_msg.append("\n🚀 <b>Command Performance (Top 10 by Usage):</b>")
            limit = 10
            count = 0
            for cmd, cmd_stats in stats["command_stats"].items():
                stats_msg.append(
                    f"/{cmd}: {cmd_stats['usage_count']} uses, "
                    f"{cmd_stats['avg_latency_ms']:.0f}ms avg, "
                    f"{cmd_stats['error_rate_percent']:.1f}% errors"
                )
                count += 1
                if count >= limit:
                    break
                
            if len(stats["command_stats"]) > limit:
                stats_msg.append(f"... and {len(stats['command_stats']) - limit} more commands")

        else:
            stats_msg.append("\nNo command performance data logged yet.")

        full_message = "\n".join(stats_msg)
        await send_long_message(message.chat.id, full_message)

    except Exception as e:
        logger.error(f"Error in /botstats command: {e}", exc_info=True)
        await message.answer("❌ An error occurred while generating bot statistics.")


@router.message(Command("health"))
@rate_limited_command()
async def cmd_health(message: types.Message):
    """Checks system health (CPU, Memory) - Admin only."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    try:
        import os
        import psutil
        from datetime import timedelta
        
        process = psutil.Process(os.getpid())
        cpu_percent = process.cpu_percent(interval=0.1)  # Short interval for quick check
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        uptime_seconds = time.time() - metrics.start_time

        health_msg = [
            "💚 <b>System Health Report</b> 💚\n",
            f"⏱️ Uptime: {str(timedelta(seconds=int(uptime_seconds)))}",
            f"💻 CPU Usage: {cpu_percent:.1f}%",
            f"🧠 Memory Usage: {memory_mb:.2f} MB",
            # Add DB connection check if possible
            # db_status = await db.check_connection()
            # f"💾 DB Status: {'Connected' if db_status else 'Disconnected'}"
        ]

        await message.answer("\n".join(health_msg))

    except Exception as e:
        logger.error(f"Error in /health command: {e}", exc_info=True)
        await message.answer("❌ An error occurred while checking system health.")


@router.message(Command("broadcast"))
@rate_limited_command(cooldown_message="Please wait at least 1 minute between broadcasts.")
async def cmd_broadcast(message: types.Message):
    """Sends a message to all known users (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "Usage: /broadcast [message text]\n"
            "The message will be sent to all users who have interacted with the bot."
        )
        return

    broadcast_text = args[1].strip()
    # Get all user IDs from stats (or a dedicated user table if you have one)
    async with user_manager._lock:
        all_user_ids = list(user_manager.user_stats.keys())

    if not all_user_ids:
        await message.answer("❌ No users found to broadcast to.")
        return

    await message.answer(f"🚀 Starting broadcast to {len(all_user_ids)} users...")
    logger.info(f"Admin {message.from_user.id} initiated broadcast to {len(all_user_ids)} users.")

    success_count = 0
    fail_count = 0
    start_time = time.time()

    from bot import bot  # Import here to avoid circular imports
    for user_id in all_user_ids:
        try:
            await bot.send_message(user_id, broadcast_text)
            success_count += 1
            await asyncio.sleep(0.05)  # Small delay to avoid rate limits
        except TelegramAPIError as e:
            logger.warning(f"Failed to broadcast to user {user_id}: {e}")
            fail_count += 1
        except Exception as e:
            logger.error(f"Unexpected error broadcasting to user {user_id}: {e}")
            fail_count += 1

        # Periodic progress update for long broadcasts
        if (success_count + fail_count) % 100 == 0:
            await message.answer(f"Progress: {success_count + fail_count}/{len(all_user_ids)} users processed...")

    elapsed_time = time.time() - start_time
    await message.answer(
        f"✅ Broadcast Complete!\n\n"
        f"Sent: {success_count}\n"
        f"Failed: {fail_count}\n"
        f"Time: {elapsed_time:.1f} seconds"
    )


@router.message(Command("config"))
@rate_limited_command()
async def cmd_config(message: types.Message):
    """Views or updates bot configuration settings (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    from config import config  # Import here to avoid circular imports
    
    args = message.text.split(maxsplit=2)
    # Usage: /config list | /config [setting] | /config [setting] [new_value]

    if len(args) == 1:
        await message.answer("Usage: /config list | /config [setting] | /config [setting] [new_value]")
        return

    sub_command = args[1].lower()

    if sub_command == "list":
        settings = await config.get_all_settings()
        settings_text = ["📋 <b>Bot Configuration Settings:</b>\n"]
        for key, value in settings.items():
            settings_text.append(f"• {key} = {value}")
        await message.answer("\n".join(settings_text))
        return

    elif len(args) == 2:
        # View a specific setting
        setting_key = sub_command
        value = await config.get_setting(setting_key)
        if value is None:
            await message.answer(f"❌ Setting '{setting_key}' not found.")
        else:
            await message.answer(f"📝 {setting_key} = {value}")
        return

    elif len(args) == 3:
        # Update a setting
        setting_key = sub_command
        new_value = args[2]
        result = await config.update_setting(setting_key, new_value)
        if result:
            await message.answer(f"✅ Updated: {setting_key} = {new_value}")
        else:
            await message.answer(f"❌ Failed to update setting '{setting_key}'.")
        return

    else:
        await message.answer("❌ Invalid command format. Use /config list | /config [setting] | /config [setting] [value]")


@router.message(Command("getlogs"))
@rate_limited_command()
async def cmd_getlogs(message: types.Message):
    """Retrieves recent bot logs (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    import os
    
    args = message.text.split()
    lines_to_get = 50  # Default number of lines
    if len(args) > 1 and args[1].isdigit():
        lines_to_get = min(int(args[1]), 500)  # Limit maximum lines for performance

    log_file_path = os.path.join("logs", 'bot.log')  # Assuming default log file name

    try:
        # Read last N lines of log file
        with open(log_file_path, 'r', encoding='utf-8') as file:
            # Simple way to get last N lines - read all and take last N
            all_lines = file.readlines()
            
        log_content = ''.join(all_lines[-lines_to_get:])
        
        # Send as text if it's small enough, or as a text file
        if len(log_content) < 4000:
            await message.answer(f"📋 Last {lines_to_get} log lines:\n```\n{log_content}\n```")
        else:
            from io import BytesIO
            log_file = BytesIO(log_content.encode('utf-8'))
            from bot import bot  # Import here to avoid circular imports
            await bot.send_document(
                message.chat.id, 
                types.BufferedInputFile(
                    log_file.getvalue(), 
                    filename=f"bot_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                ),
                caption=f"📋 Last {lines_to_get} log lines"
            )

    except Exception as e:
        logger.error(f"Error retrieving logs in /getlogs: {e}", exc_info=True)
        await message.answer(f"❌ Error retrieving logs: {type(e).__name__}: {e}")



@router.message(Command("maintenance"))
@rate_limited_command()
async def cmd_maintenance(message: types.Message):
    """Manage bot maintenance mode (admin only)."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ This command is restricted to administrators.")
        return

    args = message.text.split(maxsplit=1)
    subcommand = args[1].lower() if len(args) > 1 else "status"

    logger.info(f"Admin {message.from_user.id} used /maintenance {subcommand}")

    try:
        if subcommand == "on":
            set_maintenance_mode(True)
            await message.answer("🔧 Maintenance mode **enabled**. Bot will use separate 'maintenance_*' collections.")
        elif subcommand == "off":
            set_maintenance_mode(False)
            await message.answer("✅ Maintenance mode **disabled**. Bot is using normal collections.")
        elif subcommand == "status":
            status = is_maintenance_mode()
            await message.answer(f"🔧 Maintenance mode is currently **{'ENABLED' if status else 'DISABLED'}**.")
        elif subcommand == "clear":
            if not is_maintenance_mode():
                await message.answer("⚠️ Cannot clear maintenance data: Maintenance mode is currently **DISABLED**.")
                return
            
            await message.answer("⏳ Clearing maintenance data (collections starting with 'maintenance_')... This might take a moment.")
            success = clear_maintenance_collections() # This is synchronous
            if success:
                await message.answer("✅ Maintenance data cleared successfully.")
            else:
                await message.answer("❌ Failed to clear maintenance data. Check logs.")
        else:
            await message.answer("Usage: /maintenance [on|off|clear|status]")

    except Exception as e:
        logger.error(f"Error in /maintenance command: {e}", exc_info=True)
        await message.answer("❌ An error occurred while managing maintenance mode.")


def register_admin_handlers(dp):
    """Register all admin command handlers."""
    router.message.register(cmd_maintenance, Command("maintenance"))

    dp.include_router(router)