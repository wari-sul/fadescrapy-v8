import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import os
import sys

# Import our modules
from config import BOT_TOKEN, ADMIN_IDS
from logging_setup import logger
from middleware import MaintenanceMiddleware, ErrorHandlingMiddleware, UserTrackingMiddleware
from services.alert_monitor import alert_monitor
from services.metrics import metrics

async def on_startup(dispatcher: Dispatcher, bot: Bot):
    """Actions to perform on bot startup."""
    logger.info("Bot starting up...")

    # 2. Initial data fetch
    from utils.game_processing import fetch_and_store_data
    logger.info("Performing initial data fetch...")
    await fetch_and_store_data(sport="nba")
    await fetch_and_store_data(sport="ncaab")
    logger.info("Initial data fetch complete.")

    # 3. Start periodic tasks
    from tasks.periodic import start_periodic_tasks
    await start_periodic_tasks(bot)
    logger.info("Periodic background tasks started.")

    # 4. Notify admin(s) bot is online
    from datetime import datetime
    startup_message = f"✅ Bot started successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    for admin_id in ADMIN_IDS:
        if not admin_id: continue
        try:
            await bot.send_message(admin_id, startup_message)
        except Exception as e:
            logger.warning(f"Could not send startup notification to admin {admin_id}: {e}")

    logger.info("Bot is now running and polling for updates...")

async def on_shutdown(dispatcher: Dispatcher, bot: Bot):
    """Actions to perform on bot shutdown."""
    logger.info("Bot shutting down...")

    # 1. Notify admin(s)
    from datetime import datetime
    shutdown_message = f"⚠️ Bot is shutting down at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    for admin_id in ADMIN_IDS:
        if not admin_id: continue
        try:
            # Use send_message with a timeout to avoid blocking shutdown
            await asyncio.wait_for(bot.send_message(admin_id, shutdown_message), timeout=2.0)
        except Exception as e:
            logger.warning(f"Could not send shutdown notification to admin {admin_id}: {e}")

    # 2. Close bot session
    logger.info("Closing bot session...")
    try:
        await bot.session.close()
    except Exception as e:
        logger.error(f"Error closing bot session: {e}")

    # 3. Close storage connection (if applicable, e.g., Redis)
    # logger.info("Closing FSM storage...")
    # await storage.close() # If storage requires closing

    logger.info("Shutdown sequence complete.")

# Initialize bot and dispatcher
if not BOT_TOKEN:
    logger.critical("CRITICAL: BOT_TOKEN environment variable not set!")
    sys.exit(1)

# Create bot instance with HTML parsing as default
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Use MemoryStorage for now, can be replaced with Redis later if needed
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Register middlewares in order (outer middleware runs first)
dp.update.outer_middleware(MaintenanceMiddleware())
dp.update.outer_middleware(ErrorHandlingMiddleware())
dp.update.outer_middleware(UserTrackingMiddleware())

# Register handlers
from handlers import register_all_handlers
# register_all_handlers(dp) # Moved to main()

# Register startup and shutdown handlers
dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)


async def main():
    # Ensure startup tasks like deleting webhook happen before polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted and pending updates dropped before polling.")
    except Exception as e:
        logger.error(f"Could not delete webhook/drop updates before polling: {e}")

    # Start polling
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Register handlers just before polling
    register_all_handlers(dp)

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.critical(f"Bot failed to start or crashed: {e}", exc_info=True)