import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties # Import from correct submodule
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

# --- Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")

# --- Validate Config ---
if not BOT_TOKEN:
    logger.critical("BOT_TOKEN environment variable not set. Cannot send message.")
    exit(1)

ADMIN_IDS = []
if ADMIN_IDS_STR:
    try:
        ADMIN_IDS = [int(id_str.strip()) for id_str in ADMIN_IDS_STR.split(",") if id_str.strip()]
    except ValueError:
        logger.error("Invalid ADMIN_IDS format. Should be comma-separated integers.")
        # Continue without admin IDs, but log the error

if not ADMIN_IDS:
    logger.critical("ADMIN_IDS environment variable not set or empty. Cannot determine recipient.")
    exit(1)

TARGET_ADMIN_ID = ADMIN_IDS[0] # Send to the first admin ID

# --- Sample Alert Message ---
# (Using HTML formatting similar to format_fade_alert)
SAMPLE_ALERT_MESSAGE = """
🚨 <b>Test Fade Alert (NBA)</b> 🏀 🚨
Game: Test Team B @ Test Team A
Fading: <b>Test Team B (+7.5)</b>
Reason: This is a test message to verify alert sending.
Rating: ⭐️⭐️⭐️⭐️ (4-Star)
Bet Against: <b>Test Team B +7.5</b> (Odds: -115)
"""

async def send_test_alert():
    """Initializes bot and sends the test alert message."""
    # Use DefaultBotProperties for parse_mode
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logger.info(f"Attempting to send test alert to Admin ID: {TARGET_ADMIN_ID}")
    try:
        await bot.send_message(
            chat_id=TARGET_ADMIN_ID,
            text=SAMPLE_ALERT_MESSAGE
        )
        logger.info(f"Successfully sent test alert to Admin ID: {TARGET_ADMIN_ID}")
    except TelegramAPIError as e:
        logger.error(f"Telegram API Error sending test alert to {TARGET_ADMIN_ID}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending test alert to {TARGET_ADMIN_ID}: {e}", exc_info=True)
    finally:
        # Close the bot session gracefully
        await bot.session.close()
        logger.info("Bot session closed.")

if __name__ == "__main__":
    asyncio.run(send_test_alert())