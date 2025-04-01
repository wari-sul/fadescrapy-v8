from aiogram import Dispatcher
from .general import register_general_handlers
from .nba import register_nba_handlers
from .ncaab import register_ncaab_handlers
from .fade import register_fade_handlers
from .admin import register_admin_handlers

def register_all_handlers(dp: Dispatcher):
    """Register all handlers with the dispatcher."""
    # Order matters: register admin handlers first, then general, then others
    register_admin_handlers(dp)
    register_general_handlers(dp)
    register_nba_handlers(dp)
    register_ncaab_handlers(dp)
    register_fade_handlers(dp)
    
    # Import and register any other handlers here