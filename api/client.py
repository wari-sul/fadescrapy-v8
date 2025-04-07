import os
import requests
import logging
import pytz
from datetime import datetime
from dotenv import load_dotenv

# Get logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Common headers for API requests
# Load API Token from environment variable
ACTION_NETWORK_AUTH_TOKEN = os.getenv("ACTION_NETWORK_AUTH_TOKEN")
if not ACTION_NETWORK_AUTH_TOKEN:
    logger.warning("ACTION_NETWORK_AUTH_TOKEN environment variable not set. API requests may fail.")
    # Provide a default or raise an error if the token is absolutely required
    # ACTION_NETWORK_AUTH_TOKEN = "YOUR_DEFAULT_OR_PLACEHOLDER_TOKEN" # Example placeholder

API_HEADERS = {
    "authorization": ACTION_NETWORK_AUTH_TOKEN or "", # Use loaded token or empty string if not found
    "accept": "application/json",
    "origin": "https://www.actionnetwork.com",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

# API Base URLs
NCAAB_API_URL = "https://api.actionnetwork.com/web/v2/scoreboard/publicbetting/ncaab"
NBA_API_URL = "https://api.actionnetwork.com/web/v2/scoreboard/publicbetting/nba"

def make_request(url, params=None):
    """Make an API request with error handling"""
    try:
        logger.debug(f"Making API request to {url} with params {params}")
        response = requests.get(url, headers=API_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        # Removed temporary logging of raw response
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None

def get_eastern_time_date(date_str=None):
    """Gets current date in Eastern Time (ET) zone in YYYYMMDD format."""
    et_timezone = pytz.timezone('America/New_York')
    if date_str:
        try:
            # Parse the input date string (assumed format: YYYYMMDD)
            dt_obj = datetime.strptime(date_str, "%Y%m%d")
            # Localize the naive datetime directly to ET
            et_datetime = et_timezone.localize(dt_obj)
            et_date_str = et_datetime.strftime("%Y%m%d") # Should now correctly return the input date string
            # Get the current time in ET for the time string part (as the input date has no time)
            now_et = datetime.now(et_timezone)
            et_time_str = now_et.strftime("%I:%M %p ET")
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

def format_api_response(response_data, sport, date):
    """Formats API response data consistently for both NBA and NCAAB."""
    if not response_data or 'games' not in response_data:
        logger.warning(f"Invalid {sport.upper()} API response format")
        return []
        
    games = response_data.get('games', [])
    logger.info(f"Received {len(games)} {sport.upper()} games for {date}")
    
    # Add sport type and date to each game for downstream processing
    for game in games:
        game['sport'] = sport
        game['date'] = date
        
    return games