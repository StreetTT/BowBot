from supabase import create_client, Client
from config import config
from datetime import datetime, timezone
from typing import TypedDict, List, Optional, Literal, Any, Dict, cast
from copy import deepcopy
from config import get_logger
# FIXME: All IDs from discord should be strings: Must be done at night for minimal disruption

# --- Type Definitions ---
# These TypedDicts define the expected structure of data stored in Supabase tables.

class MoneyDropConfig(TypedDict):
    """Settings for the random money drop feature."""
    enabled: bool                  # Whether money drops are active.
    chance: float                  # Probability of a money drop occurring (e.g., 0.05 for 5%).
    min_amount: int                # Minimum money awarded per drop.
    max_amount: int                # Maximum money awarded per drop.
    allowed_channels: List[str]    # List of channel IDs where the bot is allowed to respond.
                                   # An empty list means all channels are allowed. [-1] means none are allowed.

class EconomyConfig(TypedDict):
    """TypedDict for the economy settings within a server's config."""
    work_cooldown_hours: int       # Cooldown for the 'work' command.
    steal_cooldown_hours: int      # Cooldown for the 'steal' command.
    work_min_amount: int           # Minimum earnings from 'work'.
    work_max_amount: int           # Maximum earnings from 'work'.
    steal_chance: float            # Success chance for 'steal'.
    steal_penalty: int             # Money lost if 'steal' fails.
    steal_max_percentage: float    # Max percentage of target's balance that can be stolen.
    starting_balance: int          # Initial balance for new users.
    currency_name: str             # Name of the in-game currency (e.g., "pounds").
    currency_symbol: str           # Symbol of the in-game currency (e.g., "£").
    log_channel: Optional[str]             # Channel ID for logging economy actions, if set.

class ServerConfig(TypedDict):
    """TypedDict for the 'server_configs' table."""
    guild_id: str                  # Discord guild (server) ID.
    notes: Optional[str]           # For me to remember which server is which, 9/10 times holds the server name
    prefix: str                    # Bot's command prefix for this guild.
    embed_color: str               # Default embed color (hex string).
    allowed_channels: List[str]    # List of channel IDs where the bot is allowed to respond.
                                   # An empty list means all channels are allowed. [-1] means none are allowed.
    economy: EconomyConfig         # Nested dictionary for economy settings specific to this server.
    moneydrop: MoneyDropConfig     # Money drop settings for this server.
    update_log: Optional[str]      # Channel ID for logging Bot updates, if set.
    config_log: Optional[str]      # Channel ID for logging configuration changes, if set.

class EconomyData(TypedDict):
    """TypedDict for the 'economy' table, storing individual user economy data."""
    guild_id: str                  # Discord guild ID.
    user_id: str                   # Discord user ID.
    balance: int                   # User's current balance.
    last_work: Optional[str]       # Timestamp of the last 'work' command (ISO format string).
    last_steal: Optional[str]      # Timestamp of the last 'steal' command (ISO format string).
    participant: bool              # If User has participated in the economy (used the bot)

class EconomyLog(TypedDict):
    """TypedDict for the 'economy_logs' table, tracking all economy transactions."""
    id: int                        # Unique log entry ID (auto-incrementing in DB).
    guild_id: str                  # Discord guild ID where transaction occurred.
    user_id: str                   # User ID involved in the transaction.
    action: str                    # Description of the action (e.g., "work", "steal_success").
    amount: int                    # Amount of currency involved.
    type: Literal["BOT", "USER"]   # Whether the action was initiated by a "BOT" or a "USER".
    target_user_id: Optional[str]  # Optional: User ID targeted by the action (e.g., in steal).
    timestamp: str                 # Timestamp of the transaction (ISO format string).

# Initialize the Supabase client using credentials from the `config` object.
# This client instance is used for all database operations.
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

# --- Default Values ---
# Define the default economy configuration.
# This ensures consistency for new servers and provides a fallback for missing settings.
DEFAULT_MONEY_DROP_CONFIG: MoneyDropConfig = {
    "enabled": False,
    "chance": 0.05, # 5% chance per message for a money drop.
    "min_amount": 50,
    "max_amount": 150,
    "allowed_channels": ["-1"]
}
DEFAULT_ECONOMY_CONFIG: EconomyConfig = {
    "work_cooldown_hours": 1,
    "steal_cooldown_hours": 6,
    "work_min_amount": 50,
    "work_max_amount": 500,
    "steal_chance": 0.65, # 65% chance for a successful steal.
    "steal_penalty": 100,
    "steal_max_percentage": 0.25, # Max 25% of target's balance can be stolen.
    "starting_balance": 1000,
    "currency_name": "pounds",
    "currency_symbol": "£",
    "log_channel": None
}

def deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merges two dictionaries.
    Updates `destination` with values from `source`. If a key exists in both and its value
    is a dictionary, the merge is applied recursively to that nested dictionary.
    This is useful for applying default configurations while preserving existing custom settings.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # If the value is a dictionary, create or get the nested dictionary in destination
            # and recursively merge.
            node = destination.setdefault(key, {})
            deep_merge(value, node)
        else:
            # Otherwise, simply update the value in destination.
            destination[key] = value
    return destination

async def get_server_config(guild_id: int) -> ServerConfig:
    """
    Fetches the server's configuration from Supabase.
    If no configuration is found for the guild, a new default entry is created and returned.
    This function ensures that every guild the bot is in has a valid configuration.
    """
    # Query the 'server_configs' table for the specific guild_id.
    # `maybe_single()` attempts to return a single record or None.
    response = supabase.table('server_configs').select("*").eq('guild_id', str(guild_id)).maybe_single().execute()

    if response and response.data:
        data = response.data
        # Create a deep copy of the default economy config to preserve it.
        full_eco_config = deepcopy(DEFAULT_ECONOMY_CONFIG)
        # This allows partial updates.
        if 'economy' in data and isinstance(data['economy'], dict):
            deep_merge(cast(Dict[str, Any], data['economy']), cast(Dict[str, Any], full_eco_config))

        data['economy'] = full_eco_config # Update the economy part of the config.
        return cast(ServerConfig, data) # Cast the result to ServerConfig TypedDict.
    else:
        # If no configuration is found, create a new default configuration.
        new_config: ServerConfig = {
            "guild_id": str(guild_id),
            "notes": None,
            "prefix": "-",
            "embed_color": "#0000FF",
            "allowed_channels": [], # Empty list means all channels are allowed by default.
            "economy": deepcopy(DEFAULT_ECONOMY_CONFIG),
            "moneydrop": deepcopy(DEFAULT_MONEY_DROP_CONFIG),
            "update_log": None,
            "config_log": None
        }
        # Insert the new default configuration into the 'server_configs' table.
        supabase.table('server_configs').insert(dict(new_config)).execute()
        return new_config

async def update_server_config(guild_id: int, **kwargs: Any) -> None:
    """
    Updates the server's configuration in Supabase using keyword arguments.
    Allows for partial updates and handles merging of nested 'economy' settings.
    Parameters:
    - `guild_id`: The ID of the guild to update.
    - `**kwargs`: Keyword arguments representing the fields to update (e.g., `prefix="new!"`).
    """
    current_config = await get_server_config(guild_id) # Fetch current config to merge changes.
    update_data: Dict[str, Any] = {}

    for key, value in kwargs.items():
        if key == "economy" and isinstance(value, dict):
            # If the 'economy' key is being updated, perform a deep merge.
            eco_settings_copy = deepcopy(cast(Dict[str, Any],current_config['economy']))
            update_data['economy'] = deep_merge(value, eco_settings_copy)
        elif key == "moneydrop" and isinstance(value, dict):
            # If the 'moneydrop' key is being updated, perform a deep merge.
            moneydrop_copy = deepcopy(cast(Dict[str, Any], current_config['moneydrop']))
            update_data['moneydrop'] = deep_merge(value, moneydrop_copy)
        else:
            update_data[key] = value

    if update_data:
        # Perform the update operation in Supabase.
        supabase.table('server_configs').update(update_data).eq('guild_id', str(guild_id)).execute()

async def get_user_economy_data(guild_id: int, user_id: int) -> EconomyData:
    """
    Fetches a user's full economy data from Supabase.
    If an entry for the user doesn't exist, a new one is created with default values.
    Ensures every active user has an economy profile.
    """
    # Query the 'economy' table for the user's data in a specific guild.
    response = supabase.table('economy').select("*").eq('guild_id', str(guild_id)).eq('user_id', str(user_id)).maybe_single().execute()
    if response and response.data:
        return cast(EconomyData, response.data) # Return existing data.

    # If no data found, create a new entry.
    server_config = await get_server_config(guild_id) # Get starting balance from server config.
    starting_balance = server_config['economy']['starting_balance']
    new_user_data: EconomyData = {
        'guild_id': str(guild_id),
        'user_id': str(user_id),
        'balance': starting_balance,
        'last_work': None,
        'last_steal': None,
        'participant': False
    }
    # Insert the new user economy data into the 'economy' table.
    supabase.table('economy').insert(dict(new_user_data)).execute()
    return new_user_data

async def update_user_economy(guild_id: int, user_id: int, data: Dict[str, Any]) -> None:
    """
    Updates specific fields in a user's economy data.
    Automatically creates the user's entry if it doesn't exist before updating.
    Parameters:
    - `guild_id`: The ID of the guild.
    - `user_id`: The ID of the user.
    - `data`: A dictionary of fields to update and their new values.
    """
    # Call `get_user_economy_data` first to ensure the user's entry exists.
    await get_user_economy_data(guild_id, user_id)
    if data:
        # Perform the update operation in Supabase.
        supabase.table('economy').update(data).eq('guild_id', str(guild_id)).eq('user_id', str(user_id)).execute()

async def update_user_balance(guild_id: int, user_id: int, change: int, action: str, type: Literal["BOT", "USER"], target_user_id: Optional[int] = None) -> int:
    """
    Updates a user's balance and logs the transaction to the 'economy_logs' table.
    This is the primary function for any balance modification.
    Parameters:
    - `guild_id`: The ID of the guild.
    - `user_id`: The ID of the user whose balance is being updated.
    - `change`: The amount to add to (positive) or subtract from (negative) the balance.
    - `action`: A string describing the reason for the balance change (e.g., "work", "steal_success").
    - `type`: Indicates who initiated the action: "BOT" or "USER".
    - `target_user_id`: Optional. The ID of another user involved in the transaction (e.g., the target of a steal).
    Returns:
    - The new balance of the user.
    """
    user_data = await get_user_economy_data(guild_id, user_id) # Ensure user exists.
    current_balance = user_data.get('balance', 0)
    new_balance = current_balance + change

    await update_user_economy(guild_id, user_id, {'balance': new_balance, 'participant': True}) # Update balance in 'economy' table.
    # Log the transaction details.
    await log_economy_action(guild_id, user_id, action, change, type, target_user_id)
    return new_balance

async def log_economy_action(guild_id: int, user_id: int, action: str, amount: int, type: Literal["BOT", "USER"], target_user_id: Optional[int] = None) -> None:
    """
    Logs an economy transaction to the 'economy_logs' table.
    This provides an audit trail for all currency movements.
    Includes error handling for logging failures.
    """
    try:
        supabase.table('economy_logs').insert({
            'guild_id': str(guild_id),
            'user_id': str(user_id),
            'action': action,
            'amount': amount,
            'type': type,
            'target_user_id': str(target_user_id) if target_user_id else None,
            'timestamp': datetime.now(tz=timezone.utc).isoformat() # Store timestamp in ISO 8601 format with UTC timezone.
        }).execute()
    except Exception as e:
        # Log any errors that occur during the logging process to the bot's log file.
        get_logger().error(f"Error logging economy action: {e}", exc_info=True)

async def get_server_with_update_feed() -> List[ServerConfig]:
    """
    Retrieves the update feed channels from each guild.
    """
    try:
        response = supabase.table('server_configs').select("*").execute()
        if response and response.data:
            return [cast(ServerConfig, config) for config in response.data if config["update_log"] is not None]
        return []
    except Exception as e:
        get_logger().error(f"Error fetching bot log channels: {e}", exc_info=True)
        return []