import os

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

# Create a singleton instance of the Config class.
config = Config()