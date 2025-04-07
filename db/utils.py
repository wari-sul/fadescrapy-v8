import logging
import pytz
import os # Added import for os module
from datetime import datetime

logger = logging.getLogger(__name__)

def get_eastern_time_date(date_str=None):
    """Gets current date in Eastern Time (ET) zone in YYYYMMDD format."""
    et_timezone = pytz.timezone('America/New_York')
    if date_str:
        try:
            # Parse the input date string (assumed format: YYYYMMDD)
            dt_obj = datetime.strptime(date_str, "%Y%m%d")
            # Localize the naive datetime directly to ET - Assuming input is naive local time intended for ET
            # If input represents UTC, use: et_datetime = dt_obj.replace(tzinfo=pytz.utc).astimezone(et_timezone)
            # If input represents naive ET, use:
            et_datetime = et_timezone.localize(dt_obj)

            et_date_str = et_datetime.strftime("%Y%m%d")
            # Get the current time in ET for the time string part (as the input date has no time)
            now_et = datetime.now(et_timezone)
            et_time_str = now_et.strftime("%I:%M %p ET") # Use current time for the time part
            return et_date_str, et_time_str
        except ValueError as e:
            logger.error(f"Invalid date format provided ('{date_str}'). Falling back to current date. Error: {e}")
            # Fall back to current date
            now = datetime.now(et_timezone)
            return now.strftime("%Y%m%d"), now.strftime("%I:%M %p ET")
    else:
        # Get current date in ET
        now = datetime.now(et_timezone)
        return now.strftime("%Y%m%d"), now.strftime("%I:%M %p ET")


def ensure_dir_exists(dir_path):
    """Ensures that a directory exists, creating it if necessary."""
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
            logger.info(f"Created directory: {dir_path}")
        except OSError as e:
            logger.error(f"Error creating directory {dir_path}: {e}")
            raise # Re-raise the exception if creation fails