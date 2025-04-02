import logging
# Import sub-modules
# Import only functions, not direct collections
from .connection import (
    setup_indexes,
    # Import getters if they need to be exported from db module directly,
    # otherwise, modules should import them from db.connection
    get_nba_collection, get_ncaab_collection, get_fade_alerts_collection,
    get_users_collection, get_raw_api_responses_collection,
    is_maintenance_mode, set_maintenance_mode, clear_maintenance_collections
)
from .game_repo import (
    update_or_insert_data, get_scheduled_games, get_game_by_team
)
from .alert_repo import (
    get_fade_alert_stats, get_recent_fade_alerts, get_pending_fade_alerts,
    store_fade_alert, update_fade_alert_result
)
from .utils import get_eastern_time_date

logger = logging.getLogger(__name__)

# Setup indexes on import
setup_indexes()

# Export everything
# Export functions and getters instead of direct collections
__all__ = [
    # Connection getters & functions
    'get_nba_collection', 'get_ncaab_collection', 'get_fade_alerts_collection',
    'get_users_collection', 'get_raw_api_responses_collection',
    'is_maintenance_mode', 'set_maintenance_mode', 'clear_maintenance_collections',
    'setup_indexes',
    # Game Repo functions
    'update_or_insert_data', 'get_scheduled_games', 'get_game_by_team',
    # Alert Repo functions
    'get_fade_alert_stats', 'get_recent_fade_alerts', 'get_pending_fade_alerts',
    'store_fade_alert', 'update_fade_alert_result',
    # Utils functions (already imported)
    'get_eastern_time_date'
    # Add other repo functions if needed, e.g., from user_repo, raw_response_repo
]

logger.info("Database module initialized successfully")