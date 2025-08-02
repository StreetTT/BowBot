import discord
from discord.ext import commands
from utils.supabase_client import get_server_config
from typing import Optional, List, Union, Any
import random
from core.tiktok import TikTokService
from config import get_logger
from rapidfuzz import fuzz

log = get_logger()

DEFAULT_EMBED_COLOR = "#0000FF"  # Default blue color for embeds
BOT_OWNERS = [1011944834669486142]
ACTION_DICT = {
    "work": "work 💼",
    "steal_success": "theft successful 🦹‍♂️",
    "stolen_from": "stolen from 😱",
    "steal_denied": "theft denied 🚫",
    "steal_fail": "theft failed ❌",
    "give_success": "gave 🎁",
    "given_to": "given to 🤝",
    "money_drop_claim": "money drop claim 💸"
}

async def post_money_log(bot: commands.Bot, guild_id: int, log_channel_id: Union[int, str], action: str, amount: int, type: str, user_id: int, target_user_id: Optional[int] = None):
    """Posts a formatted economy log to the specified channel."""
    if isinstance(log_channel_id, str):
        log_channel_id = int(log_channel_id)

    log_channel = bot.get_channel(log_channel_id)
    if not isinstance(log_channel, discord.TextChannel):
        return

    color = await get_embed_color(guild_id)
    user = bot.get_user(user_id)

    title  = f"{ACTION_DICT.get(action, action).capitalize()}"
    
    # Determine the title and description based on the action
    if amount > 0:
        color = discord.Color.green()
    elif amount < 0:
        color = discord.Color.red()
    else:
        color = discord.Color.greyple()

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="User", value=user.mention if user else f"ID: {user_id}", inline=True)
    embed.add_field(name="Amount", value=str(amount), inline=True)

    if target_user_id:
        target_user = bot.get_user(target_user_id)
        embed.add_field(name="Target User", value=target_user.mention if target_user else f"ID: {target_user_id}", inline=True)

    embed.set_footer(text=f"Type: {type} | Date: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    await log_channel.send(embed=embed)

async def post_config_log(bot: commands.Bot, guild_id: int, log_channel_id: Union[int, str], changed_by: discord.Member, setting: str, old_value: Any, new_value: Any, method: str = "BOT"):
    """Posts a formatted configuration log to the specified channel."""
    if isinstance(log_channel_id, str):
        log_channel_id = int(log_channel_id)

    old_value = str(old_value) if old_value is not None else "None"
    new_value = str(new_value) if new_value is not None else "None"

    log_channel = bot.get_channel(log_channel_id)
    if not isinstance(log_channel, discord.TextChannel):
        return

    color = await get_embed_color(guild_id)
    
    embed = discord.Embed(title="⚙️ Configuration Change", color=color)
    embed.add_field(name="Setting Changed", value=f"`{setting}`", inline=False)
    # Use code block formatting only if the value does not contain '<' or '>'
    def setting_format(val):
        if '<' in val and '>' in val:
            return val
        return f"```\n{val}\n```"

    embed.add_field(name="Old Value", value=setting_format(old_value), inline=True)
    embed.add_field(name="New Value", value=setting_format(new_value), inline=True)
    
    embed.set_footer(text=f"Changed by: {changed_by.display_name} | Method: {method} | Date: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", 
                     icon_url=changed_by.display_avatar.url
    )
    await log_channel.send(embed=embed)

async def get_embed_color(guild_id: Optional[Union[int, str]] = None) -> discord.Color:
    """
    Gets the configured embed color for a given guild from the Supabase database.
    Falls back to a default color if no custom color is set or if the set color is invalid.
    Parameters:
    - `guild_id`: The ID of the guild.
    Returns:
    - A `discord.Color` object.
    """
    if isinstance(guild_id, str):
        guild_id = int(guild_id)

    if guild_id:
        # Fetch server configuration. `get_server_config` handles defaults if no config exists.
        server_config = await get_server_config(guild_id)
        # Get the `embed_color` from the config, defaulting to "#0000FF" (blue) if not set.
        hex_color: str = server_config.get('embed_color', DEFAULT_EMBED_COLOR)
    else:
        hex_color = DEFAULT_EMBED_COLOR  # Use default color if no guild ID is provided.

    try:
        # Convert hexadecimal string (e.g., "#RRGGBB") to an integer suitable for `discord.Color`.
        # `lstrip('#')` removes the '#' prefix, and `int(..., 16)` converts from base 16.
        return discord.Color(int(hex_color.lstrip('#'), 16))
    except (ValueError, TypeError):
        # If conversion fails (e.g., invalid hex string), return the default color.
        return discord.Color(int(DEFAULT_EMBED_COLOR.lstrip('#'), 16))

async def format_currency(guild_id: int, amount: int, include_name: bool = False) -> str:
    """
    Formats a given amount of currency with the guild's custom currency symbol and name.
    Adjusts the currency name for pluralization (e.g., "pound" vs. "pounds").
    Parameters:
    - `guild_id`: The ID of the guild.
    - `amount`: The integer amount of currency.
    Returns:
    - A formatted string, e.g., "**£100 pounds**".
    """
    # Fetch server configuration to get economy settings.
    config = await get_server_config(guild_id)
    # Access the 'economy' sub-dictionary, defaulting to an empty dict if it doesn't exist.
    economy_config = config.get('economy', {})
    # Get the currency symbol and name from economy config, with defaults.
    symbol: str = economy_config.get('currency_symbol', '£')
    name: str = economy_config.get('currency_name', 'pounds')

    # Apply pluralization to the currency name if the amount is not 1 and the name doesn't already end in 's'.
    if amount != 1 and not name.endswith('s'):
        name += 's'
    elif name.endswith('s') and amount == 1:
        name = name[:-1] # Remove the 's'

    # Return the formatted string. Bold the symbol and amount.
    return f"**{symbol}{amount}**{(' ' + name) if include_name else ''}"

async def send_embed(ctx: commands.Context, description: str, title: Optional[str] = None, image_url: Optional[str] = None) -> None:
    """
    Sends a standardized embed message to the context's channel.
    Automatically applies the guild's configured embed color.
    Parameters:
    - `description`: The main text content of the embed.
    - `title`: Optional. The title of the embed.
    """
    
    # Get the custom embed color for the guild.
    assert ctx.guild is not None
    color = await get_embed_color(ctx.guild.id)
    embed = discord.Embed(description=description, color=color)
    if image_url is not None:
        embed.set_thumbnail(url=image_url)
    embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    if title:
        embed.title = title
    # Send the embed message to the channel where the command was invoked.
    await ctx.send(embed=embed)

async def get_user_from_arg(user_arg: Optional[Union[str, discord.Member]], ctx: commands.Context, random_if_invalid: bool = False):
    assert ctx.guild is not None

    if isinstance(user_arg, discord.Member):
        return user_arg

    members = [m for m in list(ctx.guild.members) if not m.bot]
    if not members:
        raise Exception("How tf...")

    if isinstance(user_arg, str):
        matches = []
        for member in members:
            # Filter out any None names
            names_to_check = [name for name in [member.nick, member.global_name, member.name] if name]

            if not names_to_check:
                continue

            # Calculate a score for each name and take the maximum score..
            scores = [fuzz.WRatio(user_arg.lower(), name.lower()) for name in names_to_check]
            if (max_score := max(scores)):
                matches.append((max_score, member))

        # Sort members by score in descending order
        sorted_members = [member for score, member in sorted(matches, key=lambda x: x[0], reverse=True)]

        if len(sorted_members) >= 1: # If theres one or more matches, return the most likely one
            return sorted_members[0]
         
    if not random_if_invalid:
        raise Exception("Member not found.")
    
    # Filter select a random member, excluding the command's author.
    members: List[discord.Member] = [m for m in ctx.guild.members if not m.bot and m.id != ctx.author.id]
    if not members:
        raise Exception("No non-bot members in the guild.")
    return random.choice(members) # Pick a random member.


def guild_only():
    """
    A custom command check that ensures the command is used only within a guild.
    If used in a DM, it sends an ephemeral message and prevents the command from running.
    """
    async def predicate(ctx):
        if ctx.guild is None:
            await ctx.author.send("This command can only be used in a server.")
            return False
        return True
    return commands.check(predicate)

async def channel_check(ctx: commands.Context, allowed_channels: List[str]):
    # If allowed_channels is empty, all channels are allowed.
    if not allowed_channels:
        return True
    
    # If allowed_channels is ["-1"] or current channel ID isn't in the allowed list.
    if allowed_channels == ["-1"] or str(ctx.channel.id) not in allowed_channels:
        return False
    
    return True


def in_allowed_channels():
    """
    A custom command check that ensures the command is used in a channel
    allowed by the server's general configuration.
    Requires the command to be used in a guild.
    """
    async def predicate(ctx: commands.Context):
        assert ctx.guild is not None

        server_config = await get_server_config(ctx.guild.id)
        allowed_channels = server_config.get('allowed_channels', [])

        return await channel_check(ctx, allowed_channels)
    return commands.check(predicate)

def in_moneydrop_channels():
    """
    A custom command check that ensures the command is used in a channel
    allowed by the server's money drop configuration.
    Requires the command to be used in a guild.
    """
    async def predicate(ctx: commands.Context):
        assert ctx.guild is not None

        server_config = await get_server_config(ctx.guild.id)
        # Access moneydrop config, defaulting to an empty dict if not present
        moneydrop_config = server_config.get('moneydrop', {})
        allowed_channels = moneydrop_config.get('allowed_channels', [])

        return await channel_check(ctx, allowed_channels)
    
    return commands.check(predicate)

async def amount_str_to_int(amount_str: str , balance: int, ctx: commands.Context) -> int:
    amount_str_lower = amount_str.lower()
    if amount_str_lower in ("all", "max", "life savings"):
        return balance
    elif amount_str_lower.endswith("%"):
        try:
            percentage_value = float(amount_str_lower[:-1]) # Extract the number before '%'
            if not (0 < percentage_value <= 100):
                await send_embed(ctx, "Percentage bet must be between 1% and 100%.")
                raise commands.BadArgument
            amount_str_lower = int(balance * (percentage_value / 100))
        except ValueError:
            await send_embed(ctx, "Invalid percentage format. Use e.g., '50%'.")
            raise commands.BadArgument
    else:
        try:
            amount_str_lower = int(amount_str_lower)
        except ValueError:
            await send_embed(ctx, "Amount must be a valid number, 'all', or a percentage (e.g., '50%').")
            raise commands.BadArgument
    
    # Ensure bet is an integer at this point
    return int(amount_str_lower)

def is_bot_owner_check():
    """
    A custom command check that ensures the command is used by a bot owner.
    """
    predicate = is_bot_owner
    
    return commands.check(predicate)

def is_bot_owner(ctx: commands.Context):
    if ctx.author.id in BOT_OWNERS:
        return True
    else:
        return False
    
tiktok = TikTokService()