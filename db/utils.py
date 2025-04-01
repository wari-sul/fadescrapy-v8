import logging
import pytz
from datetime import datetime

logger = logging.getLogger(__name__)

def get_eastern_time_date(date_str=None):
    """Gets current date in Eastern Time (ET) zone in YYYYMMDD format."""
    et_timezone = pytz.timezone('America/New_York')
    if date_str:
        try:
            # Parse the input date string (assumed format: YYYYMMDD)
            dt_obj = datetime.strptime(date_str, "%Y%m%d")
            # Convert to Eastern Time
            et_datetime = dt_obj.replace(tzinfo=pytz.UTC).astimezone(et_timezone)
            et_date_str = et_datetime.strftime("%Y%m%d")
            et_time_str = et_datetime.strftime("%I:%M %p ET")
            return et_date_str, et_time_str
        except ValueError as e:
            logger.error(f"Invalid date format: {date_str}. Error: {e}")
            # Fall back to current date
            now = datetime.now(et_timezone)
            return now.strftime("%Y%m%d"), now.strftime("%I:%M %p ET")
    else:
        # Get current date in ET
        now = datetime.now(et_timezone)
        return now.strftime("%Y%m%d"), now.strftime("%I:%M %p ET")