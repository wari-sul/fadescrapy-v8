import asyncio
import time
from aiogram import types
from logging_setup import logger
from services.user_manager import user_manager

class UserTrackingMiddleware:
    # List of commands allowed even when banned
    ALLOWED_BANNED_COMMANDS = {'/start', '/help'}  # Include slash

    async def __call__(self, handler, event: types.Update, data: dict):
        """Track user activity and enforce bans."""
        # Works for Message, CallbackQuery, etc. that have 'from_user'
        user = data.get("event_from_user")  # Standard key provided by aiogram
        if not user:
            return await handler(event, data)  # Skip if no user context

        # Determine command/action
        command = "unknown"
        if isinstance(event, types.Message) and event.text and event.text.startswith('/'):
            command = event.text.split()[0].lower()
        elif isinstance(event, types.CallbackQuery):
            command = f"callback:{event.data.split(':')[0]}"  # Example: 'callback:action'

        # Check for banned users
        banned, ban_reason = await user_manager.is_banned(user.id)
        if banned:
            # Check if the command is allowed while banned
            if command not in self.ALLOWED_BANNED_COMMANDS:
                ban_info = user_manager.banned_users.get(user.id)  # Get full info if needed
                time_left_sec = ban_info['until'] - time.time() if ban_info else 0
                time_left_hr = int(time_left_sec / 3600) if time_left_sec > 0 else 0

                ban_message = (
                    f"❌ You are currently banned from using most bot features.\n"
                    f"Reason: {ban_reason or 'Not specified'}"
                )
                if time_left_hr > 0:
                    ban_message += f"\nTime remaining: ~{time_left_hr} hours"
                ban_message += f"\n\nYou can still use: {' '.join(self.ALLOWED_BANNED_COMMANDS)}"

                try:
                    # Use event.answer() if available (Message, CallbackQuery)
                    if hasattr(event, 'answer'):
                        await event.answer(ban_message)
                    # Fallback for other update types might be needed if applicable
                except Exception as e:
                    logger.error(f"Error sending banned message to {user.id}: {e}")
                return  # Stop processing banned user for restricted command

        # Update user stats (run in background)
        try:
            # Use asyncio.create_task to avoid blocking the middleware chain
            asyncio.create_task(user_manager.update_user_activity(user.id, command))
        except Exception as e:
            # Log error but don't block the handler
            logger.error(f"Error creating task for updating user stats for {user.id}: {e}")

        # Proceed to the next middleware or handler
        return await handler(event, data)