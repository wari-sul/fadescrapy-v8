import asyncio
import time
from collections import defaultdict
from typing import Tuple, Optional, Dict
from logging_setup import logger
from db.user_repo import save_user_stats # Import the specific function

class UserManager:
    def __init__(self):
        self.banned_users = {}  # user_id -> {until: timestamp, reason: str, by_admin: int}
        self.user_stats = defaultdict(lambda: {
            'commands': defaultdict(int),
            'last_seen': 0,
            'join_date': None,
            'ban_history': [],
            'warning_history': []
        })
        self._lock = asyncio.Lock()
        self._last_warn = defaultdict(float)  # user_id -> last warn timestamp

    async def is_banned(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Check if user is banned. Returns (is_banned, reason)."""
        async with self._lock:
            if user_id in self.banned_users:
                if time.time() < self.banned_users[user_id]['until']:
                    return True, self.banned_users[user_id]['reason']
                else:
                    # Ban expired, remove it
                    del self.banned_users[user_id]
            return False, None

    async def tempban_user(self, user_id: int, hours: int, reason: str, by_admin: int):
        """Temporarily ban a user."""
        until = time.time() + (hours * 3600)
        async with self._lock:
            self.banned_users[user_id] = {
                'until': until,
                'reason': reason,
                'by_admin': by_admin
            }
            # Ensure structure exists before appending
            if 'ban_history' not in self.user_stats[user_id]:
                 self.user_stats[user_id]['ban_history'] = []
            self.user_stats[user_id]['ban_history'].append({
                'timestamp': time.time(),
                'duration': hours,
                'reason': reason,
                'by_admin': by_admin
            })
        logger.info(f"User {user_id} banned for {hours} hours by {by_admin}. Reason: {reason}")

    async def warn_user(self, user_id: int, reason: str, by_admin: int):
        """Issue a warning to a user."""
        async with self._lock:
            if 'warning_history' not in self.user_stats[user_id]:
                self.user_stats[user_id]['warning_history'] = []
            self.user_stats[user_id]['warning_history'].append({
                'timestamp': time.time(),
                'reason': reason,
                'by_admin': by_admin
            })
        logger.info(f"User {user_id} warned by {by_admin}. Reason: {reason}")

    def get_warnings(self, user_id: int) -> list:
        """Get a user's warning history."""
        # No lock needed for read-only access if modifications are properly locked
        return self.user_stats.get(user_id, {}).get('warning_history', [])

    async def get_user_stats(self, user_id: int) -> Optional[dict]:
        """Safely get a copy of user stats."""
        async with self._lock:
            if user_id in self.user_stats:
                # Return a copy to prevent modification outside the lock
                return self.user_stats[user_id].copy()
            return None

    async def update_user_activity(self, user_id: int, command: str):
        """Update user's command count and last seen time."""
        async with self._lock:
            stats = self.user_stats[user_id]
            stats['commands'][command] += 1
            stats['last_seen'] = time.time()
            if stats['join_date'] is None:
                stats['join_date'] = time.time()

            # Save to DB periodically (e.g., every 10 commands)
            total_commands = sum(stats['commands'].values())
            if total_commands % 10 == 0:
                 # Run DB save in background without blocking middleware
                 asyncio.create_task(self._save_to_db(user_id))

    async def _save_to_db(self, user_id: int):
        """Save user stats to database (async)."""
        stats_copy = await self.get_user_stats(user_id)
        if not stats_copy:
             logger.warning(f"Attempted to save stats for non-existent user ID: {user_id}")
             return

        try:
            # Call the imported function directly
            await save_user_stats(
                user_id=user_id,
                commands=dict(stats_copy.get('commands', {})),
                last_seen=stats_copy.get('last_seen', 0),
                join_date=stats_copy.get('join_date'),
                ban_history=stats_copy.get('ban_history', []),
                warning_history=stats_copy.get('warning_history', [])
            )
            logger.debug(f"Saved stats for user {user_id} to database.")
        except Exception as e:
            logger.error(f"Unexpected error saving stats for {user_id}: {e}", exc_info=True)

# Create singleton instance
user_manager = UserManager()