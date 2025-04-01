import asyncio
from config import config, is_admin
from logging_setup import logger

class MaintenanceMiddleware:
    async def __call__(self, handler, event, data):
        """Check maintenance mode."""
        is_maintenance = await config.get_setting('maintenance_mode', False)
        if is_maintenance:
            user = data.get("event_from_user")
            if user and not is_admin(user.id):  # Allow admins during maintenance
                try:
                    await event.answer("🔧 The bot is currently undergoing maintenance. Please try again later.")
                except Exception:
                    pass  # Ignore errors sending maintenance message
                return  # Stop processing for non-admins
        return await handler(event, data)