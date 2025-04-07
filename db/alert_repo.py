import logging
from datetime import datetime, timedelta
import pytz
from .connection import get_fade_alerts_collection, get_collection_name # Import getter function and name helper
from typing import Optional

# Get logger
logger = logging.getLogger(__name__)

def get_fade_alert_stats(sport=None, days=30):
    """Gets statistics for fade alerts over the past X days."""
    try:
        cutoff_date = datetime.now(pytz.UTC) - timedelta(days=days)
        match = {
            "created_at": {"$gte": cutoff_date},
            "status": {"$in": ["won", "lost"]} # Corrected status values
        }
        if sport:
            match["sport"] = sport
            
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": {
                        "sport": "$sport",
                        "rating": "$rating"
                    },
                    "total": {"$sum": 1},
                    "winners": {
                        "$sum": {"$cond": [{"$eq": ["$status", "won"]}, 1, 0]} # Corrected status value
                    }
                }
            },
            {
                "$project": {
                    "sport": "$_id.sport",
                    "rating": "$_id.rating",
                    "total": 1,
                    "winners": 1,
                    "win_rate": {
                        "$multiply": [
                            {"$divide": ["$winners", "$total"]},
                            100
                        ]
                    }
                }
            },
            {"$sort": {"rating": -1}}
        ]
        
        return list(get_fade_alerts_collection().aggregate(pipeline))
    except Exception as e:
        logger.error(f"Error getting fade alert stats: {e}")
        return []

def get_recent_fade_alerts(sport=None, limit=10):
    """Gets most recent fade alerts with their results."""
    try:
        query = {}
        if sport:
            query["sport"] = sport
            
        return list(get_fade_alerts_collection().find(
            query,
            sort=[("created_at", -1)],
            limit=limit
        ))
    except Exception as e:
        logger.error(f"Error getting recent fade alerts: {e}")
        return []

def get_pending_fade_alerts():
    """Gets all pending fade alerts."""
    try:
        return list(get_fade_alerts_collection().find({"status": "pending"}))
    except Exception as e:
        logger.error(f"Error getting pending fade alerts: {e}")
        return []

def store_fade_alert(game_id: str, sport: str, date: str, market: str,
                     faded_outcome_label: str, faded_value: Optional[float],
                     odds: int, implied_probability: float, # Added odds and IP
                     tickets_percent: float, money_percent: float, rating: int, # Added rating
                     reason: str, status: str = "pending", **kwargs): # Removed threshold_used
    """Stores a new fade alert based on market and outcome using the new formula."""
    try:
        alert = {
            "game_id": game_id,
            "sport": sport,
            "date": date,
            "market": market,
            "faded_outcome_label": faded_outcome_label,
            "faded_value": faded_value,
            "odds": odds, # Store the odds used for calculation
            "implied_probability": implied_probability, # Store the calculated IP
            "tickets_percent": tickets_percent,
            "money_percent": money_percent,
            "reason": reason, # Updated reason based on T% vs IP
            "status": status,
            "rating": rating, # Store the rating
            "created_at": datetime.now(pytz.UTC),
            "updated_at": datetime.now(pytz.UTC)
            # threshold_used removed
        }
        alert.update(kwargs) # Include any extra fields passed

        # Use a filter that uniquely identifies this specific fade opportunity
        filter_query = {
            "game_id": game_id,
            "market": market,
            "faded_outcome_label": faded_outcome_label
        }

        # Since the calling function already checked for existence for this date,
        # we can directly insert.
        result = get_fade_alerts_collection().insert_one(alert)
        # Return True if insert was acknowledged (result.inserted_id exists)
        return result.acknowledged
        # logger.debug(f"Store fade alert result: Matched={result.matched_count}, Modified={result.modified_count}, UpsertedId={result.upserted_id}")
    except Exception as e:
        logger.error(f"Error storing fade alert for game {game_id}, market {market}: {e}", exc_info=True)
        return False

def update_fade_alert_result(alert_id, status):
    """Updates the result of a fade alert."""
    try:
        result = get_fade_alerts_collection().update_one(
            {"_id": alert_id} if isinstance(alert_id, str) else {"game_id": alert_id},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.now(pytz.UTC)
                }
            }
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating fade alert result: {e}")
        return False

def get_fade_alerts_since(date_str: str):
    """Gets all fade alerts created on or after a specific date (YYYYMMDD)."""
    try:
        # Convert date string to datetime object at the start of the day in UTC
        start_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=pytz.UTC)
        query = {"created_at": {"$gte": start_date}}
        # Fetch all matching alerts, sorted by creation time
        return list(get_fade_alerts_collection().find(query).sort("created_at", -1))
    except ValueError:
        logger.error(f"Invalid date format provided to get_fade_alerts_since: {date_str}")
        return []
    except Exception as e:
        logger.error(f"Error getting fade alerts since {date_str}: {e}")
        return []

def update_fade_performance_stats(stats_data: dict):
    """Updates or inserts the overall fade performance statistics."""
    # This function needs a dedicated collection or a specific document ID
    # Assuming a 'performance_stats' collection for simplicity
    try:
        # Get the correct performance_stats collection name based on maintenance mode
        stats_collection_name = get_collection_name("performance_stats")
        stats_collection = get_fade_alerts_collection().database[stats_collection_name]
        # Use a fixed ID to always update the same document
        stats_collection.update_one(
            {"_id": "fade_performance"},
            {"$set": stats_data},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error updating fade performance stats: {e}")
        return False

def get_fade_alert_subscribers(game_id, sport):
    """Placeholder: Get users subscribed to alerts for a specific game."""
    # In a real implementation, this would query a user preferences/subscriptions table
    logger.warning("Placeholder function get_fade_alert_subscribers called. Returning empty list.")
    return [] # Return empty list for now
