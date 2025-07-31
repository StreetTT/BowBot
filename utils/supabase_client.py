from supabase import create_client, Client
from config import config
from datetime import datetime, timezone
from typing import TypedDict, List, Optional, Literal, Any, Dict, cast, Tuple, Union
from copy import deepcopy
from config import get_logger

# Type Definitions 

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
    streamer: Optional[str]        # Discord user ID of the streamer, if set.

class TikTokData(TypedDict):
    username: Optional[str]        # TikTok username of the user.
    id: Optional[str]              # TikTok ID of the user.
    code: Optional[str]            # TikTok code for linking.
    code_expires: Optional[str]    # Expiry time for the TikTok code (ISO format string).
    link: Optional[str]            # TikTok link for the user.

class EconomyData(TypedDict):
    """TypedDict for the 'economy' table, storing individual user economy data."""
    guild_id: str                  # Discord guild ID.
    user_id: str                   # Discord user ID.
    balance: int                   # User's current balance.
    last_work: Optional[str]       # Timestamp of the last 'work' command (ISO format string).
    last_steal: Optional[str]      # Timestamp of the last 'steal' command (ISO format string).
    participant: bool              # If User has participated in the economy (used the bot)
    tiktok: TikTokData         # TikTok related data, e.g., username or link.

class EconomyLog(TypedDict):
    """TypedDict for the 'economy_logs' table, tracking all economy transactions."""
    id: int                        # Unique log entry ID (auto-incrementing in DB).
    guild_id: str                  # Discord guild ID where transaction occurred.
    user_id: str                   # User ID involved in the transaction.
    action: str                    # Description of the action (e.g., "work", "steal_success").
    amount: int                    # Amount of currency involved.
    type: Literal["BOT", "USER", "TIKTOK"] # Whether the action was initiated by "TIKTOK", "BOT" or "USER".
    target_user_id: Optional[str]  # Optional: User ID targeted by the action (e.g., in steal).
    timestamp: str                 # Timestamp of the transaction (ISO format string).

class CachedData(TypedDict):
    updated_at: datetime
    data: Dict[str, Any]

# Global Variables 

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
logger = get_logger()

# Default Values 

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
DEFAULT_TIKTOK_DATA: TikTokData = {
    "username": None,
    "id": None,
    "code": None,
    "code_expires": None,
    "link": None
}

SERVER_CONFIG_CACHE: Dict[str, CachedData] = {}
ECONOMY_CACHE: Dict[Tuple[str, str], CachedData] = {}
TTL = 60 * 10

# General Functions 

def deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges two dictionaries.
    
    Updates `destination` with values from `source`. If a key exists in both and its 
    value is a dictionary, the merge is applied recursively to that nested dictionary.

    Args:
        source (Dict[str, Any]): The dictionary with data to merge from.
        destination (Dict[str, Any]): The dictionary to merge into.

    Returns:
        Dict[str, Any]: The merged destination dictionary.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # If the value is a dictionary, create or get the nested dictionary in destination and recursively merge.
            node = destination.setdefault(key, {})
            deep_merge(value, node)
        else:
            # Otherwise, simply update the value in destination.
            destination[key] = value
    return destination

def determine_cache(table: str, data: Dict[Any, Any] = {}) -> Union[Tuple[Dict[str, CachedData], Optional[str]], Tuple[Dict[Tuple[str, str], CachedData], Optional[Tuple[str, str]]]]:
    """Determines the appropriate cache and cache key for a given table and data.

    Args:
        table (str): The name of the table, must be 'server_configs' or 'economy'.
        data (Dict[Any, Any], optional): Dictionary containing identifiers like 
            'guild_id' and 'user_id'. Defaults to {}.

    Raises:
        ValueError: If the table name is not 'server_configs' or 'economy'.

    Returns:
        Union[Tuple[Dict[str, CachedData], Optional[int]], Tuple[Dict[Tuple[str, str], CachedData], Optional[Tuple[int, int]]]]: 
            A tuple containing the appropriate cache and the cache key.
              
    """
    if table not in ("server_configs", "economy"):  
        logger.warning(f"Invalid table '{table}' for caching.")
        raise ValueError(f"Invalid table '{table}' for caching.")
    
    if (table == "server_configs"): 
        return cast(Dict[str, CachedData], SERVER_CONFIG_CACHE), str(data.get("guild_id"))
    else:
        cache_key = (str(data["guild_id"]), str(data["user_id"])) if data.get("user_id") and data.get("guild_id") else None
        return cast(Dict[Tuple[str, str], CachedData],ECONOMY_CACHE), cache_key

# Cache CUD 

def cache_upsert(table: str, data: Dict[Any, Any] = {}) -> None:
    """Upserts (updates or inserts) data into the appropriate cache.

    Args:
        table (str): The name of the table to cache data for.
        data (Dict[Any, Any], optional): The data record to be cached. Defaults to {}.
    """
    try:
        cache, cache_key = determine_cache(table, data)
    except ValueError as e:
        return

    if cache_key:
        logger.debug(f"Upserting to cache for table '{table}' with key '{cache_key}'.")
        cache[cache_key] = {"updated_at": datetime.now(timezone.utc), "data": data} # type: ignore
    else:
        logger.debug(f"Cache miss for table '{table}'.")


def cache_retrieve(table: str, conditions:Dict[Any, Any]) -> Optional[List[Dict[str, Any]]]:
    """Retrieves data from the cache if it exists and is not expired.

    Args:
        table (str): The name of the table to retrieve from.
        conditions (Dict[Any, Any]): The conditions to find the data in the cache, 
            e.g., {'guild_id': 123}.

    Returns:
        Optional[List[Dict[str, Any]]]: A list containing the cached data dictionary, 
                                        or None if not found or expired.
    """
    try:
        cache, cache_key = determine_cache(table, conditions)
    except ValueError as e:
        return
    
    if cache_key and cache_key in cache:
        if (datetime.now(timezone.utc) - cache[cache_key]["updated_at"]).total_seconds() < TTL: # type: ignore
            logger.debug(f"Retrieved from cache for table '{table}' with key '{cache_key}'.")
            return [cache[cache_key]["data"]] # type: ignore
        else:
            logger.debug(f"Cache expired for table '{table}' with key '{cache_key}'.")
    else:
        logger.debug(f"Cache miss for table '{table}'.")
    return 
    
def cache_delete(table: str, conditions: Dict[Any, Any] = {}) -> None:
    """Deletes an entry from the cache based on the provided conditions.

    Args:
        table (str): The name of the table associated with the cache.
        conditions (Dict[Any, Any], optional): The conditions to identify the cache 
            entry to delete. Defaults to {}.
    """
    try:
        cache, cache_key = determine_cache(table, conditions)
    except ValueError as e:
        return

    if cache_key and cache_key in cache:
        logger.debug(f"Deleting from cache for table '{table}' with key '{cache_key}'.")
        cache.pop(cache_key) # type: ignore
    else:
        logger.debug(f"Cache miss for table '{table}'.")

# Supabase CRUD 

def create(table: str, data: Dict[Any, Any] = {}) -> None:
    """Creates a new record in a Supabase table and adds it to the cache.

    Args:
        table (str): The name of the Supabase table.
        data (Dict[Any, Any], optional): The data for the new record. Defaults to {}.

    Raises:
        Exception: If the database transaction fails.
    """
    logger.debug(f"Creating in Supabase for table '{table}'.")
    # Attempt to save in supabase
    try:
        supabase.table(table).insert(data).execute()
        logger.info(f"Successfully created record in table '{table}'.")
    except Exception as e:
        logger.error(f"Failed to create record in table '{table}': {e}", exc_info=True)
        raise Exception(f"Failed to save user information in {table}: {e}")
    
    # Attempt to save in cache
    cache_upsert(table, data)
    

def retrieve(table: str, conditions:Dict[Any, Any] = {}) -> List[Dict[Any, Any]]:
    """Retrieves records from a Supabase table, utilizing the cache first.

    If data is not in the cache or is expired, it fetches from Supabase, 
    then updates the cache.

    Args:
        table (str): The name of the Supabase table.
        conditions (Dict[Any, Any], optional): A dictionary of conditions to filter 
            the query (e.g., {'guild_id': 123}). Defaults to {}.

    Raises:
        Exception: If the database transaction fails.

    Returns:
        List[Dict[Any, Any]]: A list of dictionaries representing the retrieved records.
    """
    # Attempt to retrieve from cache
    data = cache_retrieve(table, conditions)
    if data:
        return data
    
    logger.debug(f"Fetching from Supabase in table '{table}' with conditions: {conditions}")
    # Attempt to fetch from supabase
    try:
        query = supabase.table(table).select("*")
        for key, value in conditions.items():
            query = query.eq(key, value)
        response = query.execute()
        data = response.data
        logger.info(f"Successfully retrieved records from table '{table}'.")
    except Exception as e:
        logger.error(f"Failed to retrieve records from table '{table}' with conditions {conditions}: {e}", exc_info=True)
        raise Exception(f"Failed to retrieve records from {table}: {e}")
    
    for record in data:
        # Attempt to save in cache
        cache_upsert(table, record)
    
    return data if data else []


def update(table: str, attributes: Dict[Any, Any] = {}, conditions: Dict[Any, Any] = {}) -> None:
    """Updates records in a Supabase table and refreshes the corresponding cache entries.

    Args:
        table (str): The name of the Supabase table.
        attributes (Dict[Any, Any], optional): A dictionary of the fields to update. 
            Defaults to {}.
        conditions (Dict[Any, Any], optional): A dictionary of conditions to filter which 
            records to update. Defaults to {}.

    Raises:
        Exception: If the database update fails.
    """
    logger.debug(f"Updating in Supabase for table '{table}' with conditions: {conditions}")
    # Attempt to update supabase
    try:
        query = supabase.table(table).update(attributes)
        for key, value in conditions.items():
            query = query.eq(key, value)
        query.execute()
        logger.info(f"Successfully updated record in table '{table}'.")
    except Exception as e:
        logger.error(f"Failed to update records in table '{table}' with conditions {conditions}: {e}", exc_info=True)
        raise Exception(f"Failed to update records in {table}: {e}")
    
    logger.debug(f"Updating cache for table '{table}' after database update for conditions: {conditions}.")
    # Retrieve the updated records from Supabase and upsert them into the cache
    data = []
    try:
        query = supabase.table(table).select("*")
        for key, value in conditions.items():
            query = query.eq(key, value)
        response = query.execute()
        data = response.data
        if data:
            for record in data:
                cache_upsert(table, record)
        logger.info(f"Successfully updated cache for {len(data)} records in table '{table}'.")
    except Exception as e:
        logger.error(f"Cache update after DB update failed for table '{table}' with conditions {conditions}: {e}", exc_info=True)
        if data:
            logger.warning(f"Deleting cache entries for table '{table}' due to post-update cache failure. Conditions: {conditions}")
            for record in data:
                cache_delete(table, record)


def delete(table: str, conditions: Dict[Any, Any] = {}) -> None:
    """Deletes records from a Supabase table and removes them from the cache.

    Args:
        table (str): The name of the Supabase table.
        conditions (Dict[Any, Any], optional): A dictionary of conditions to filter which 
            records to delete. Defaults to {}.

    Raises:
        Exception: If the database deletion fails.
    """
    logger.debug(f"Deleting from Supabase for table '{table}' with conditions: {conditions}")
    try:
        query = supabase.table(table).delete()
        for key, value in conditions.items():
            query = query.eq(key, value)
        query.execute()
        logger.info(f"Successfully deleted from table '{table}' with conditions: {conditions}")
    except Exception as e:
        logger.error(f"Failed to delete records from table '{table}' with conditions {conditions}: {e}", exc_info=True)
        raise Exception(f"Failed to delete records from {table}: {e}")
    
    cache_delete(table, conditions)

# BowBot Functions 

async def get_server_config(guild_id: int) -> ServerConfig:
    """Fetches a server's configuration, creating a default one if it doesn't exist.

    This function ensures that a valid configuration is always available for a guild.

    Args:
        guild_id (int): The Discord guild ID for which to fetch the configuration.

    Returns:
        ServerConfig: The server's configuration dictionary.
    """
    res = cast(List[ServerConfig], retrieve("server_configs",{"guild_id": guild_id}))
    
    if res:
        data = res[0]
        logger.debug(f"Found server config for guild_id {guild_id}.")
    else:
        logger.info(f"No config found for guild_id {guild_id}. Creating a new default config.")
        # If no configuration is found, create a new default configuration and insert it into the database
        data: ServerConfig = {
            "guild_id": str(guild_id),
            "notes": None,
            "prefix": "-",
            "embed_color": "#0000FF",
            "allowed_channels": [],
            "economy": deepcopy(DEFAULT_ECONOMY_CONFIG),
            "moneydrop": deepcopy(DEFAULT_MONEY_DROP_CONFIG),
            "update_log": None,
            "config_log": None,
            "streamer": None
        }
        create("server_configs", cast(Dict, data))
    
    return data

async def update_server_config(guild_id: int, data: Dict[str, Any]) -> None:
    """Updates a server's configuration in Supabase.

    Handles partially updated configurations by performing a deep merge of the existing configuration
    with the provided data.

    Args:
        guild_id (int): The ID of the guild to update.
        data (Dict[str, Any]): A dictionary of fields to update and their new values. Should be a partial dict based on ServerConfig.
    """
    update_data: Dict[str, Any] = {}
    logger.info(f"Updating server config for guild_id {guild_id}.")
    logger.debug(f"Data:{data}")

    for key, value in data.items():
        if key in ("economy", "moneydrop"):
            logger.debug(f"Performing deep merge for '{key}' on guild_id {guild_id}")
            current_config = await get_server_config(guild_id) # Fetch current config to merge changes.
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
        update_data["guild_id"] = str(guild_id)
        update("server_configs", update_data)

async def get_user_economy_data(guild_id: int, user_id: int) -> EconomyData:
    """Fetches a user's economy data, creating a default entry if it doesn't exist.

    Ensures every user has an economy profile within a guild.

    Args:
        guild_id (int): The Discord guild ID.
        user_id (int): The Discord user ID.

    Returns:
        EconomyData: The user's economy data dictionary.
    """
    res = cast(List[EconomyData], retrieve("economy",{"guild_id": guild_id, "user_id": user_id}))
    
    if res:
        data = res[0]
        logger.debug(f"Found economy data for user {user_id} in guild {guild_id}.")
    else:
        # If no configuration is found, create a new default configuration and insert it into the database
        logger.info(f"No economy data found for user {user_id} in guild {guild_id}. Creating a new default entry.")
        server_config = await get_server_config(guild_id) # Get starting balance from server config.
        starting_balance = server_config['economy']['starting_balance']
        data: EconomyData = {
            'guild_id': str(guild_id),
            'user_id': str(user_id),
            'balance': starting_balance,
            'last_work': None,
            'last_steal': None,
            'participant': False,
            'tiktok': DEFAULT_TIKTOK_DATA
        }
        create("economy", cast(Dict, data))
    
    return data

async def get_multiple_user_economy_data(guild_id: int, user_ids: List[int] = []) -> List[EconomyData]:
    """Fetches multiple user's economy data. 

    If no user IDs are provided, fetches all users in the guild.
    
    Args:
        guild_id (int): The Discord guild ID.
        user_ids (List[int]): A list of Discord user IDs.
    
    Returns:
        List[EconomyData]: A list of user's economy data dictionaries.
    """
    result: List[EconomyData] = []

    # Get as many user_ids from cache as possible
    user_ids_to_fetch = set(user_ids)
    cache_query = {"guild_id": guild_id}
    if user_ids:
        for user_id in user_ids: 
            cache_query.update({"user_id": user_id})
            users = cache_retrieve("economy", cache_query)
            if users:
                result.append(cast(EconomyData, users[0]))
                user_ids_to_fetch.remove(user_id)


    # Fetch remaining user_ids from Supabase
    if not user_ids or user_ids_to_fetch:
        res = supabase.table('economy').select("*").eq('guild_id', str(guild_id))
        if user_ids_to_fetch:
            res = res.in_('user_id', [str(uid) for uid in user_ids_to_fetch])
        res = res.execute()

        if res and res.data:
            logger.info(f"Found {len(res.data)} economy data")

            for row in res.data:
                cache_upsert("economy", row)
                result.append(cast(EconomyData, row))
        return result
    logger.warning(f"No economy data found for user_ids {user_ids} in guild_id {guild_id}.")
    return []

async def update_user_economy(guild_id: int, user_id: int, data: Dict[str, Any]) -> None:
    """Updates a user's economy data in Supabase.

    Handles partially updated configurations by performing a deep merge of the existing configuration
    with the provided data.

    Args:
        guild_id (int): The ID of the guild.
        user_id (int): The ID of the user.
        data (Dict[str, Any]): A dictionary of fields to update and their new values.
    """
    logger.info(f"Updating user economy for user_id {user_id} in guild_id {guild_id}.")
    logger.debug(f"Data: {data}")
    update_data: Dict[str, Any] = {}

    for key, value in data.items():
        logger.debug(f"Performing deep merge for '{key}' for user_id {user_id} in guild_id {guild_id}")
        if key == "tiktok" and isinstance(value, dict):
            # If the 'tiktok' key is being updated, perform a deep merge.
            current_config = await get_user_economy_data(guild_id, user_id)
            tiktok_copy = deepcopy(cast(Dict[str, Any], current_config['tiktok']))
            update_data["tiktok"] = deep_merge(value, tiktok_copy)
        else:
            update_data[key] = value
    
    if update_data:
        update("economy", update_data)

async def update_user_balance(guild_id: int, user_id: int, change: int, action: str, type: Literal["BOT", "USER", "TIKTOK"], target_user_id: Optional[int] = None) -> int:
    """Updates a user's balance and logs the transaction.

    This is the primary function for any balance modification, ensuring data 
    consistency and logging.

    Args:
        guild_id (int): The ID of the guild.
        user_id (int): The ID of the user whose balance is changing.
        change (int): The amount to add (positive) or subtract (negative).
        action (str): A string describing the reason for the change (e.g., "work").
        type (Literal["BOT", "USER", "TIKTOK"]): The initiator of the action.
        target_user_id (Optional[int], optional): The ID of another user involved in 
            the transaction (e.g., the target of a steal). Defaults to None.

    Returns:
        int: The user's new balance after the update.
    """
    logger.info(f"Updating balance for user_id {user_id} in guild_id {guild_id}.")
    logger.debug (f"Change: {change}, Action: {action}, Type: {type}, Target: {target_user_id}")
    user_data = await get_user_economy_data(guild_id, user_id) # Ensure user exists.
    current_balance = user_data.get('balance', 0)
    new_balance = current_balance + change

    await update_user_economy(guild_id, user_id, {'balance': new_balance, 'participant': True}) # Update balance in 'economy' table.
    # Log the transaction details.
    await log_economy_action(guild_id, user_id, action, change, type, target_user_id)
    logger.info(f"New balance for user_id {user_id} in guild_id {guild_id}")
    logger.debug(f"{current_balance} -> {new_balance}")
    return new_balance

async def log_economy_action(guild_id: int, user_id: int, action: str, amount: int, type: Literal["BOT", "USER", "TIKTOK"], target_user_id: Optional[int] = None) -> None:
    """Logs an economy transaction to the 'economy_logs' table.

    Provides an audit trail for all currency movements.

    Args:
        guild_id (int): The guild ID where the transaction occurred.
        user_id (int): The user ID involved in the transaction.
        action (str): Description of the action (e.g., "work", "steal_success").
        amount (int): The amount of currency involved.
        type (Literal["BOT", "USER", "TIKTOK"]): The initiator of the action.
        target_user_id (Optional[int], optional): The user ID targeted by the action. 
            Defaults to None.
    
    Raises:
        Exception: If the database insert operation fails.
    """
    data = {
        "action": action,
        "amount": amount,
        "type": type,
        "target_user_id": str(target_user_id) if target_user_id else None,
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    logger.info(f"Logging economy action for guild_id {guild_id}")
    logger.debug(f"Data: {data}")
    try:
        supabase.table('economy_logs').insert(data).execute()
        logger.info(f"Successfully logged economy action for guild_id {guild_id}.")
    except Exception as e:
        logger.error(f"Failed to log economy action to 'economy_logs' table. Data: {data}. Error: {e}", exc_info=True)
        raise e

async def get_server_with_update_feed() -> List[ServerConfig]:
    """Retrieves all server configurations that have an update feed channel set.

    Returns:
        List[ServerConfig]: A list of server configuration dictionaries for servers 
                            with a non-null 'update_log' channel.
    """
    logger.info("Fetching all server configs to find update feeds.")
    try:
        response = supabase.table('server_configs').select("*").execute()
        if response and response.data:
            for record in response.data:
                cache_upsert("server_configs", record)
            filtered_configs = [cast(ServerConfig, config) for config in response.data if config["update_log"] is not None]
            logger.info(f"Found {len(filtered_configs)} servers with update feeds.")
            return filtered_configs
        logger.info("No server configs found.")
        return []
    except Exception as e:
        logger.error(f"Failed to retrieve servers with update feed. Error: {e}", exc_info=True)
        return []