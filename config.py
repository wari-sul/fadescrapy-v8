import os
import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants and Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("CRITICAL: BOT_TOKEN environment variable not set!")
    import sys
    sys.exit(1)

LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

ADMIN_IDS = []
admin_ids_str = os.getenv("ADMIN_IDS", "")
if admin_ids_str:
    try:
        ADMIN_IDS = [int(id_str.strip()) for id_str in admin_ids_str.split(",") if id_str.strip()]
    except ValueError:
        print("ERROR: Invalid ADMIN_IDS format in environment variables. Should be comma-separated integers.")
if not ADMIN_IDS:
    print("WARNING: ADMIN_IDS environment variable not set or empty. Admin commands will not work.")

COMMAND_TIMEOUT = 10  # seconds before considering a command "slow"

class Config:
    """Configuration management class for storing and retrieving bot settings."""
    def __init__(self):
        self._settings = {
            # Default settings
            'max_retries': 3,
            'update_interval': 300,
            'maintenance_mode': False,
            'fade_rating_threshold': 3,
        }
        self._lock = asyncio.Lock()  # Lock for thread safety

    async def get_setting(self, key, default=None):
        """Get a configuration setting by key."""
        async with self._lock:
            return self._settings.get(key, default)

    async def update_setting(self, key, value_str):
        """Update a setting with proper type conversion."""
        try:
            # If setting exists, try to convert to the same type
            async with self._lock:
                if key in self._settings:
                    original_value = self._settings[key]
                    if isinstance(original_value, bool):
                        # Handle boolean conversion
                        value = value_str.lower() in ('true', 'yes', '1', 'on')
                    elif isinstance(original_value, int):
                        value = int(value_str)
                    elif isinstance(original_value, float):
                        value = float(value_str)
                    else:
                        # String or other types
                        value = value_str
                else:
                    # New setting, use as string by default
                    value = value_str
                
                self._settings[key] = value
                from logging_setup import logger
                logger.info(f"Updated setting {key} to {value}")
                return True
                
        except (ValueError, TypeError) as e:
            from logging_setup import logger
            logger.error(f"Error updating setting {key}: {e}")
            return False

    async def get_all_settings(self):
        """Get a dictionary of all settings."""
        async with self._lock:
            return self._settings.copy()
            
    def is_admin(self, user_id):
        """Check if a user ID is in the admin list."""
        return user_id in ADMIN_IDS

# Create the config instance
config = Config()

def is_admin(user_id):
    """Check if a user is an admin."""
    return user_id in ADMIN_IDS