import logging
import os
from logging.handlers import TimedRotatingFileHandler
from config import LOG_LEVEL

def setup_logging():
    """Configure logging with file and console handlers."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            print(f"Error creating log directory '{log_dir}': {e}")

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(funcName)s:%(lineno)d]'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)-8s - %(message)s'
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels at root

    # Prevent duplicate handlers if setup_logging is called multiple times
    if root_logger.hasHandlers():
        # Return logger if already configured
        return logging.getLogger(__name__)

    # File handler for all logs (rotate daily)
    log_file_path = os.path.join(log_dir, 'bot.log')
    file_handler = TimedRotatingFileHandler(
        log_file_path, when="midnight", interval=1, backupCount=7, encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # Log everything to the main file

    # File handler for errors only (rotate daily)
    error_log_path = os.path.join(log_dir, 'errors.log')
    error_handler = TimedRotatingFileHandler(
        error_log_path, when="midnight", interval=1, backupCount=7, encoding='utf-8'
    )
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)  # Only errors

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(LOG_LEVEL)  # Use level from config/env

    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    # Silence libraries that are too verbose if needed
    # logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging()