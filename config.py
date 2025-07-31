import os
import logging
from logging.handlers import RotatingFileHandler

class Config:
    """
    This class centralizes access to critical environment-specific settings.
    These variables are typically defined in a `.env` file
    at the root of the project for local development.
    """
    def __init__(self) -> None:
        # Retrieve SUPABASE_URL from environment variables.
        superbase_url = os.environ.get("SUPABASE_URL")
        if not superbase_url:
            raise ValueError("SUPABASE_URL environment variable is not set.")
        self.SUPABASE_URL = superbase_url.strip() # .strip() removes leading/trailing whitespace.

        # Retrieve SUPABASE_KEY from environment variables.
        superbase_key = os.environ.get("SUPABASE_KEY")
        if not superbase_key:
            raise ValueError("SUPABASE_KEY environment variable is not set.")
        self.SUPABASE_KEY = superbase_key.strip()

        # Retrieve DISCORD_BOT_TOKEN from environment variables.
        discord_bot_token = os.environ.get("DISCORD_BOT_TOKEN")
        if not discord_bot_token:
            raise ValueError("DISCORD_BOT_TOKEN environment variable is not set.")
        self.DISCORD_BOT_TOKEN = discord_bot_token.strip()

        apofy_api_key = os.environ.get("APIFY_API_KEY")
        if not apofy_api_key:
            raise ValueError("APIFY_API_KEY environment variable is not set.")
        self.APIFY_API_KEY = apofy_api_key.strip()

# Create a singleton instance of the Config class.
config = Config()

def get_logger(name: str = "BowBot") -> logging.Logger:
    """
    Configures and retrieves a logger instance.

    This function sets up a root logger with both a file and console handler
    on its first call. Subsequent calls will return a logger instance
    that inherits this configuration, preventing duplicate handlers and log messages.

    Args:
        name (str): The name for the logger, typically __name__ from the calling module.

    Returns:
        logging.Logger: A configured logger instance.
    """
    logger = logging.getLogger(name)

    # Check if the root logger has already been configured to avoid duplicate handlers
    if not logging.getLogger().hasHandlers():
        # Set the level for the root logger to the lowest level of its handlers
        logging.getLogger().setLevel(logging.DEBUG)

        # Use a more informative log format
        log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s(%(lineno)d) - %(message)s')
        log_file = 'bot.log'

        # Setup file handler
        file_handler = RotatingFileHandler(
            log_file, mode='a', maxBytes=5*1024*1024,  # Max 5 MB per log file
            backupCount=2, encoding='utf-8', delay=False  # Keep 2 backup files
        )
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG)

        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(logging.INFO)

        # Add handlers to the root logger
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().addHandler(console_handler)

    return logger
