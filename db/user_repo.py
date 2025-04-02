import logging
from datetime import datetime
import pytz
from .connection import get_users_collection # Import the getter function

# Get logger
logger = logging.getLogger(__name__)

async def save_user_stats(user_id, commands, last_seen, join_date=None, ban_history=None, warning_history=None):
    """Save user statistics to database."""
    try:
        # Create document to update/insert
        update_data = {
            "user_id": user_id,
            "commands": commands,
            "last_seen": last_seen,
            "updated_at": datetime.now(pytz.UTC)
        }
        
        # Only add these fields if they have values
        if join_date:
            update_data["join_date"] = join_date
            
        if ban_history:
            update_data["ban_history"] = ban_history
            
        if warning_history:
            update_data["warning_history"] = warning_history
        
        # Upsert the user document
        result = get_users_collection().update_one(
            {"user_id": user_id},
            {"$set": update_data},
            upsert=True
        )
        
        logger.debug(f"Saved stats for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving user stats for {user_id}: {e}")
        return False