import logging
from .client import NCAAB_API_URL, make_request, get_eastern_time_date, format_api_response
from db.raw_response_repo import store_raw_response # Import the storage function

logger = logging.getLogger(__name__)

def get_ncaab_data(date=None):
    """Fetch NCAAB data from API."""
    try:
        # Get Eastern time date
        date_str, _ = get_eastern_time_date(date)
        
        # Make API request
        params = {'date': date_str}
        response_data = make_request(NCAAB_API_URL, params)

        # Store the raw response before formatting (if successful)
        if response_data:
            store_raw_response(sport='ncaab', date_str=date_str, response_data=response_data)
        
        # Format response
        formatted_games = format_api_response(response_data, 'ncaab', date_str)
        logger.info(f"Processed {len(formatted_games)} NCAAB games for {date_str}")
        return formatted_games
    
    except Exception as e:
        logger.error(f"Error fetching NCAAB data: {e}", exc_info=True)
        return []