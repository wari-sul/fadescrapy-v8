import logging
# Import sub-modules
from .connection import (
    nba_collection, ncaab_collection, 
    fade_alerts_collection, setup_indexes
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
__all__ = [
    'nba_collection', 'ncaab_collection', 'fade_alerts_collection',
    'update_or_insert_data', 'get_scheduled_games', 'get_game_by_team',
    'get_fade_alert_stats', 'get_recent_fade_alerts', 'get_pending_fade_alerts',
    'store_fade_alert', 'update_fade_alert_result', 'get_eastern_time_date'
]

logger.info("Database module initialized successfully")