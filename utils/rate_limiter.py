import time
import functools
import asyncio
from collections import defaultdict
from typing import Tuple, Optional
from aiogram import types
from logging_setup import logger
from config import ADMIN_IDS, COMMAND_TIMEOUT, is_admin
from services.metrics import metrics

class RateLimiter:
    def __init__(self):
        self.command_times = defaultdict(list)  # user_id -> list of command timestamps
        self.cooldowns = {
            'default': 3,       # 3 seconds between commands
            'start': 30,        # 30 seconds between /start commands
            'help': 10,         # 10 seconds between /help commands
            'nba': 5,
            'ncaab': 5,
            'nbateam': 5,
            'ncaabteam': 5,
            'fadenba': 10,
            'fadencaab': 10,
            'fades': 10,
            'fadestats': 15,
            'fadehistory': 15,
            'warn': 5,
            'tempban': 5,
            'userinfo': 5,
            'banlist': 10,
            'analytics': 15,
            'botstats': 15,
            'health': 10,
            'broadcast': 60,
            'config': 5,
        }

    def check_rate_limit(self, user_id: int, command: str) -> Tuple[bool, float]:
        """Check if user is rate limited. Returns (is_limited, wait_time)."""
        current_time = time.time()
        command_key = command[1:] if command.startswith('/') else command
        cooldown = self.cooldowns.get(command_key, self.cooldowns['default'])

        self.command_times[user_id] = [t for t in self.command_times[user_id]
                                     if current_time - t < max(self.cooldowns.values())]

        if self.command_times[user_id]:
            time_since_last = current_time - self.command_times[user_id][-1]
            if time_since_last < cooldown:
                return True, cooldown - time_since_last

        self.command_times[user_id].append(current_time)
        return False, 0

    def cleanup_old_data(self):
        """Remove data older than the longest cooldown."""
        current_time = time.time()
        longest_cooldown = max(self.cooldowns.values())
        for user_id in list(self.command_times.keys()):
            self.command_times[user_id] = [t for t in self.command_times[user_id]
                                         if current_time - t < longest_cooldown]
            if not self.command_times[user_id]:
                del self.command_times[user_id]

rate_limiter = RateLimiter()

def rate_limited_command(cooldown_message="Please wait before using this command again."):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(message: types.Message, *args, **kwargs):
            if not message or not hasattr(message, 'from_user'):
                event = next((arg for arg in args if isinstance(arg, types.Message)), None)
                if not event:
                    event = kwargs.get('message', kwargs.get('event'))
                if not event or not hasattr(event, 'from_user'):
                    logger.warning("Rate limiter couldn't find user object in handler.")
                    return await func(message, *args, **kwargs)
                message = event

            user_id = message.from_user.id
            
            # Skip rate limiting for admins
            if is_admin(user_id):
                # Log command but don't rate limit
                command = message.text.split()[0].lower() if hasattr(message, 'text') and message.text and message.text.startswith('/') else "unknown"
                start_time = time.monotonic()
                success = True
                try:
                    return await func(message, *args, **kwargs)
                except Exception as e:
                    success = False
                    raise e
                finally:
                    end_time = time.monotonic()
                    execution_time = end_time - start_time
                    metrics.log_command(command, user_id, execution_time, success)
                    if execution_time > COMMAND_TIMEOUT:
                        logger.warning(f"Slow command execution: {command} took {execution_time:.2f}s for admin {user_id}")
                
            command = message.text.split()[0].lower() if hasattr(message, 'text') and message.text and message.text.startswith('/') else "unknown"

            is_limited, wait_time = rate_limiter.check_rate_limit(user_id, command)
            if is_limited:
                try:
                    await message.answer(
                        f"{cooldown_message} (Try again in {wait_time:.1f} seconds)"
                    )
                except Exception as e:
                    logger.error(f"Error sending rate limit message to {user_id}: {e}")
                return

            # Log execution time with metrics
            start_time = time.monotonic()
            success = True
            try:
                return await func(message, *args, **kwargs)
            except Exception as e:
                success = False
                # Re-raise the exception to be caught by the error middleware
                raise e
            finally:
                end_time = time.monotonic()
                execution_time = end_time - start_time
                metrics.log_command(command, user_id, execution_time, success)
                if execution_time > COMMAND_TIMEOUT:
                    logger.warning(f"Slow command execution: {command} took {execution_time:.2f}s for user {user_id}")

        return wrapper
    return decorator