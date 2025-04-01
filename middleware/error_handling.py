from aiogram import types
from aiogram.exceptions import TelegramAPIError
from logging_setup import logger
from config import ADMIN_IDS
import asyncio

class ErrorHandlingMiddleware:
    async def __call__(self, handler, event: types.Update, data: dict):
        """Handle errors during event processing and log them."""
        try:
            return await handler(event, data)
        except Exception as e:
            # Attempt to extract user and event details for logging
            user = data.get("event_from_user")
            user_info = f"User ID: {user.id}" if user else "User: Unknown"
            event_type = type(event).__name__

            error_details = f"Error in {event_type} processing for {user_info}."
            if isinstance(event, types.Message) and event.text:
                error_details += f" Original text: '{event.text[:100]}...'"
            elif isinstance(event, types.CallbackQuery) and event.data:
                error_details += f" Callback data: '{event.data}'"

            # Log the exception with traceback
            logger.exception(f"{error_details} Exception: {e}")

            # Inform the user generically
            try:
                # Use event.answer if possible (Messages, Callbacks)
                if hasattr(event, 'answer') and callable(event.answer):
                    await event.answer(
                        "❌ An error occurred while processing your request.\n"
                        "The administrators have been notified. Please try again later."
                    )
                # Add fallbacks for other event types if needed
            except Exception as notify_error:
                logger.error(f"Failed to send error notification to user {user.id if user else 'Unknown'}: {notify_error}")

            # Notify admins about critical errors (optional)
            if isinstance(e, (TelegramAPIError, asyncio.TimeoutError)):  # Add other critical types
                admin_notification = f"🚨 Critical Error Detected 🚨\n\n{error_details}\nError: {type(e).__name__}: {e}"
                for admin_id in ADMIN_IDS:
                    if not admin_id: continue
                    try:
                        # Use the bot instance from data if available, otherwise global `bot`
                        current_bot = data.get('bot')
                        if current_bot:
                            await current_bot.send_message(admin_id, admin_notification[:4000])  # Limit length
                    except Exception as admin_notify_error:
                        logger.error(f"Failed to send critical error alert to admin {admin_id}: {admin_notify_error}")

            # Do not re-raise the exception here, as we've handled it.
            return None  # Explicitly indicate handled