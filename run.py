import asyncio
import signal
import sys
from logging_setup import logger
from bot import dp, bot

async def shutdown_handler(sig: signal.Signals, loop: asyncio.AbstractEventLoop):
    """Handles shutdown signals."""
    logger.info(f"Received exit signal {sig.name}... Initiating graceful shutdown.")

    # Get all running tasks except the current one (the handler itself)
    tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task()]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks...")
    for task in tasks:
        task.cancel()

    # Wait for tasks to complete cancellation
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, asyncio.CancelledError):
            continue  # Expected cancellation
        elif isinstance(result, Exception):
            logger.error(f"Exception during task cancellation ({tasks[i].get_name()}): {result}")

    # Stop the event loop
    loop.stop()

async def main():
    """Main function that starts the bot."""
    try:
        # Start polling for updates
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("Main polling loop cancelled.")
    except Exception as e:
        logger.critical(f"!!! Unhandled exception in main polling loop: {e}", exc_info=True)
    finally:
        logger.info("Polling stopped.")

if __name__ == "__main__":
    try:
        # Get the event loop
        loop = asyncio.get_event_loop()
        
        # Add signal handlers for graceful termination
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(shutdown_handler(s, loop))
            )
        
        # Run the main function
        logger.info("Starting bot...")
        loop.run_until_complete(main())
        
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping.")
    except Exception as e:
        logger.critical(f"Fatal error during startup or main loop execution: {e}", exc_info=True)
    finally:
        if loop.is_running():
            loop.stop()
        # Don't close the loop here to avoid issues with pending tasks
        logger.info("Application shut down.")