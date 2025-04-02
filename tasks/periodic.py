import asyncio
import time
import psutil
import os
from logging_setup import logger
from config import config
from aiogram import Bot
from db.utils import get_eastern_time_date # Import specific function
# Need to check where rate_limiter comes from for line 52
from utils.rate_limiter import rate_limiter # Assuming it's imported correctly
from utils.game_processing import fetch_and_store_data
from services.alert_monitor import alert_monitor
from services.metrics import metrics
from .fade_alerts import update_fade_alerts

async def periodic_tasks(bot: Bot):
    """Runs periodic tasks like updating data, alerts, and monitoring."""
    update_count = 0
    last_cleanup_time = time.time()
    # Get intervals from config, provide defaults
    update_interval = await config.get_setting('update_interval', 300)
    cleanup_interval = 3600  # 1 hour for less frequent cleanups

    while True:
        try:
            update_count += 1
            current_time = time.time()
            start_time = current_time
            logger.info(f"--- Starting Periodic Update #{update_count} ---")

            # --- Data Updates ---
            # Run data fetches concurrently
            date_today, _ = get_eastern_time_date()
            nba_fetch_task = asyncio.create_task(fetch_and_store_data(date=date_today, sport="nba"))
            ncaab_fetch_task = asyncio.create_task(fetch_and_store_data(date=date_today, sport="ncaab"))

            # Wait for fetches to complete
            nba_success = await nba_fetch_task
            ncaab_success = await ncaab_fetch_task
            logger.info(f"Data fetch results: NBA={nba_success}, NCAAB={ncaab_success}")

            # --- Fade Alert Updates ---
            # Run after data fetch is complete
            if nba_success or ncaab_success:
                await update_fade_alerts()

            # --- System Monitoring & Cleanup ---
            try:
                await alert_monitor.check_and_alert(bot)
                
                # Less frequent cleanups
                if current_time - last_cleanup_time > cleanup_interval:
                    metrics.cleanup_old_data()
                    rate_limiter.cleanup_old_data()
                    last_cleanup_time = current_time
                    logger.info("Performed periodic cleanup of metrics and rate limiter data.")
            except psutil.NoSuchProcess:
                logger.warning("psutil.NoSuchProcess error during monitoring.")
            except Exception as e:
                logger.error(f"Error during system monitoring or cleanup: {e}", exc_info=True)

            # --- Completion & Sleep ---
            total_time = time.time() - start_time
            logger.info(f"--- Periodic Update #{update_count} completed in {total_time:.2f}s ---")

            # Dynamically get sleep interval from config
            current_update_interval = await config.get_setting('update_interval', 300)
            sleep_duration = max(10, current_update_interval - total_time)  # Ensure min sleep
            logger.debug(f"Sleeping for {sleep_duration:.1f} seconds...")
            await asyncio.sleep(sleep_duration)

        except asyncio.CancelledError:
            logger.info("Periodic tasks loop cancelled.")
            break  # Exit the loop cleanly
        except Exception as e:
            # Log unexpected errors in the main loop, but keep running
            logger.error(f"!!! Unexpected error in periodic_tasks main loop: {e}", exc_info=True)
            logger.info("Waiting 60 seconds before retrying periodic tasks loop...")
            await asyncio.sleep(60)  # Wait longer after a major loop error

async def start_periodic_tasks(bot: Bot):
    """Start the periodic task loop."""
    asyncio.create_task(periodic_tasks(bot))
    logger.info("Started periodic background tasks.")