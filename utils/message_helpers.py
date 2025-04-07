import asyncio
from aiogram import Bot, types
from logging_setup import logger
from utils.formatters import format_game_info

async def send_long_message(chat_id: int, text: str, parse_mode: str = None, max_length: int = 4096):
    """Sends a long message by splitting it into chunks."""
    from bot import bot  # Import here to avoid circular imports
    
    if len(text) <= max_length:
        try:
            await bot.send_message(chat_id, text, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Failed to send message chunk to {chat_id}: {e}")
        return

    parts = []
    while len(text) > 0:
        if len(text) <= max_length:
            parts.append(text)
            break
        # Find the last newline character before the limit
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            # No newline found, split at max_length
            split_pos = max_length
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip('\n') # Remove leading newline from next part

    for part in parts:
        try:
            await bot.send_message(chat_id, part, parse_mode=parse_mode)
            await asyncio.sleep(0.1) # Small delay between parts
        except Exception as e:
            logger.error(f"Failed to send message chunk to {chat_id}: {e}")

async def send_games_in_chunks(message: types.Message, games: list, sport: str):
    """Formats and sends a list of games in chunks."""
    current_message_parts = []
    current_length = 0
    max_chunk_length = 3900 # Reduce further for more safety buffer

    for game in games:
        game_text = format_game_info(game, sport)
        game_text_len = len(game_text)

        if current_length + game_text_len + 1 > max_chunk_length: # +1 for newline
            # Send the current chunk
            if current_message_parts:
                await send_long_message(message.chat.id, "\n".join(current_message_parts))
            # Start a new chunk
            current_message_parts = [game_text]
            current_length = game_text_len
        else:
            current_message_parts.append(game_text)
            current_length += game_text_len + 1

    # Send any remaining games in the last chunk
    if current_message_parts:
        await send_long_message(message.chat.id, "\n".join(current_message_parts))