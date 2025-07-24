import discord
from discord.ext import commands
from utils.supabase_client import get_server_config
from typing import Optional

DEFAULT_EMBED_COLOR = discord.Color.blue()

async def get_embed_color(guild_id: int) -> discord.Color:
    """
    Gets the configured embed color for a given guild from the Supabase database.
    Falls back to a default color if no custom color is set or if the set color is invalid.
    Parameters:
    - `guild_id`: The ID of the guild.
    Returns:
    - A `discord.Color` object.
    """
    # Fetch server configuration. `get_server_config` handles defaults if no config exists.
    server_config = await get_server_config(guild_id)
    # Get the `embed_color` from the config, defaulting to "#0000FF" (blue) if not set.
    hex_color: str = server_config.get('embed_color', '#0000FF')
    try:
        # Convert hexadecimal string (e.g., "#RRGGBB") to an integer suitable for `discord.Color`.
        # `lstrip('#')` removes the '#' prefix, and `int(..., 16)` converts from base 16.
        return discord.Color(int(hex_color.lstrip('#'), 16))
    except (ValueError, TypeError):
        # If conversion fails (e.g., invalid hex string), return the default color.
        return DEFAULT_EMBED_COLOR

async def format_currency(guild_id: int, amount: int) -> str:
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

    # Return the formatted string. Bold the symbol and amount.
    return f"**{symbol}{amount}** {name}" # Updated to include name

async def send_embed(ctx: commands.Context, description: str, title: Optional[str] = None) -> None:
    """
    Sends a standardized embed message to the context's channel.
    Automatically applies the guild's configured embed color.
    Parameters:
    - `description`: The main text content of the embed.
    - `title`: Optional. The title of the embed.
    """
    if not ctx.guild:
        return # Cannot send guild-specific embeds outside a guild.

    # Get the custom embed color for the guild.
    color = await get_embed_color(ctx.guild.id)
    embed = discord.Embed(description=description, color=color)
    if title:
        embed.title = title
    # Send the embed message to the channel where the command was invoked.
    await ctx.send(embed=embed)