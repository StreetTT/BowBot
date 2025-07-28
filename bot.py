import discord
from discord.ext import commands
import os
import random
from config import config, get_logger
from utils.supabase_client import get_server_config, update_user_economy
from typing import List, Union
logger = get_logger()


# --- Bot Setup ---
# `message_content` is required to read message content for commands and money drops.
# `members` is required to access member information (e.g., for `on_member_join`).
DEFAULT_PREFIX = "-"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# --- Dynamic Prefix ---
async def get_prefix(bot: commands.Bot, message: discord.Message) -> Union[List[str], str]:
    """
    Gets the server-specific prefix from the database.
    If no guild (e.g., in DMs) or no custom prefix is set, it falls back to the default.
    """
    if not message.guild:
        return commands.when_mentioned_or(DEFAULT_PREFIX)(bot, message)
    server_config = await get_server_config(message.guild.id)
    # Allow bot to be mentioned or use the configured prefix.
    return commands.when_mentioned_or(server_config.get('prefix', DEFAULT_PREFIX))(bot, message)

# Initialize the bot removing the default help command to allow for a custom one.
bot = commands.Bot(command_prefix=get_prefix, intents=intents)
bot.remove_command('help')

# --- Bot Events ---
@bot.event
async def on_ready() -> None:
    """
    Event that runs when the bot is fully connected to Discord.
    It logs the bot's details and initiates retroactive setup for guilds and members.
    """
    if bot.user is not None:
        logger.info(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
        logger.info('Performing retroactive setup for guilds and members...')
        await retroactive_setup()
        logger.info("Setup complete.")

async def retroactive_setup() -> None:
    """
    Ensures that all existing guilds and their members have corresponding entries in the Supabase database.
    This prevents issues if the bot is added to a server or restarts and misses join events.
    """
    if not bot.guilds:
        logger.warning("Bot is not in any guilds.")
        return
    for guild in bot.guilds:
        # Fetching the server config will automatically create a default entry if one doesn't exist.
        await get_server_config(guild.id)

        # Iterate through all members in the guild to ensure they have economy entries.
        for member in guild.members:
            if not member.bot:
                await update_user_economy(guild.id, member.id, {})

@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    """
    Event triggered when the bot joins a new guild.
    It creates a new server configuration entry in the database for the joined guild.
    """
    logger.info(f"Joined new guild: {guild.name} ({guild.id}). Creating server config.")
    await get_server_config(guild.id) # Creates default config if not exists.

@bot.event
async def on_member_join(member: discord.Member) -> None:
    """
    Event triggered when a new member joins a guild where the bot is present.
    It creates an economy entry for the new member in the database.
    """
    if not member.bot:
        logger.info(f"New member {member.name} joined {member.guild.name}. Creating economy entry.")
        await update_user_economy(member.guild.id, member.id, {})

@bot.event
async def on_message(message: discord.Message) -> None:
    """
    Handles incoming messages for potential events and processes bot commands.
    This event is critical as it processes all non-bot messages for various features.
    """
    if message.author.bot or not message.guild:
        return # Ignore messages from bots and messages not in a guild.

    # Money Drop Logic
    try:
        guild_id = message.guild.id
        server_config = await get_server_config(guild_id)
        eco_config = server_config.get('economy', {})
        drop_config = server_config.get('moneydrop', {})

        # Check if money drops are enabled and if a random chance condition is met.
        if drop_config.get('enabled') and random.random() < drop_config.get('chance', 0.05):
            allowed_channels = drop_config.get('allowed_channels', [])

            if allowed_channels == ["-1"]: # If explicitly disallowed.
                logger.debug(f"Money drop disallowed in all channels for guild {guild_id}.")
                pass
            # If all channels are allowed (empty list) or the current channel is in the allowed list.
            elif not allowed_channels or str(message.channel.id) in allowed_channels:
                if isinstance(message.channel, discord.TextChannel):
                    # Import DropView locally to avoid circular dependencies between cogs and bot.py.
                    from cogs.events import DropView
                    # Determine the random amount for the money drop.
                    amount = random.randint(drop_config.get('min_amount', 50), drop_config.get('max_amount', 250))
                    symbol = eco_config.get('currency_symbol', '£')

                    # Create and send an embed message with a "Claim!" button.
                    embed = discord.Embed(
                        title="💰 A Wild Money Drop Appeared! 💰",
                        description=f"Quick! The first person to click the button gets **{symbol}{amount}**!",
                        color=discord.Color.gold()
                    )
                    view = DropView(amount=amount, currency_symbol=symbol, guild_id=guild_id, bot=bot)
                    view.message = await message.channel.send(embed=embed, view=view)
                    logger.info(f"Money drop initiated in guild {guild_id}, channel {message.channel.id}")
                else:
                    logger.debug(f"Money drop attempted in non-text channel {message.channel.id} in guild {guild_id}.")
            else:
                logger.debug(f"Money drop not allowed in channel {message.channel.id} for guild {guild_id}.")

    except Exception as e:
        logger.error(f"Error in on_message money drop for guild {message.guild.id}: {e}", exc_info=True)

    # This ensures that bot commands are still processed even if a money drop occurs.
    await bot.process_commands(message)

# --- Command Logging Hooks ---
@bot.before_invoke
async def before_command(ctx: commands.Context) -> None:
    """
    Log information before a command is invoked.
    Provides details about who used which command, in which guild and channel.
    """
    if ctx.guild and ctx.channel:
        logger.info(
            f"Invoking command '{ctx.command}' by {ctx.author} (ID: {ctx.author.id}) in "
            f"Guild '{ctx.guild.name}' (ID: {ctx.guild.id}), Channel #{getattr(ctx.channel, 'name', 'Unknown')} (ID: {ctx.channel.id})"
        )

@bot.after_invoke
async def after_command(ctx: commands.Context) -> None:
    """
    Log after a command is successfully invoked.
    Indicates which command completed successfully for a given user.
    """
    if not ctx.command_failed: # Check if the command did not raise an error.
        logger.info(f"Successfully executed '{ctx.command}' for {ctx.author}.")

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """
    Log and handle errors that occur during command invocation.
    Provides user-friendly error messages for common issues.
    """
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error(f"Command '{ctx.command}' failed for {ctx.author}. Error: {error}", exc_info=True)

    # Provide specific feedback to the user based on the error type.
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"You're missing a required argument: `{error.param.name}`. Use the help command for more info.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("You provided an invalid argument. Use the help command for more info.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to use this command.")
    else:
        # Generic error message for unhandled exceptions.
        await ctx.send("An unexpected error occurred. The developers have been notified.")


async def load_cogs() -> None:
    """
    Loads all cogs (extensions) from the 'cogs' directory.
    Cogs organize bot commands and events into separate, manageable files.
    """
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'): 
            try:
                # Load the cog as a Discord.py extension.
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f'Loaded cog: {filename}')
            except Exception as e:
                logger.error(f'Failed to load cog {filename}', exc_info=True)


async def main() -> None:
    """
    Main function to run the bot.
    Initializes cogs and starts the Discord bot client.
    """
    async with bot:
        await load_cogs() # Load all bot functionalities.
        await bot.start(config.DISCORD_BOT_TOKEN)