import discord
from discord.ext import commands
from utils.supabase_client import get_server_config, update_server_config
from utils.helpers import send_embed, get_embed_color
from typing import Optional, List, Any
# FIXME: This Command sucks, Refactor

def get_allowed_str(bot, channels: List[Any]):
    channels_str = ""
    if not channels:
        channels_str = "All channels currently allowed." # If empty, all are allowed.
    elif channels == [-1]:
        channels_str = "All channels currently disallowed." # If -1, none are allowed.
    else:
        # Format channel mentions for display, filtering out invalid channel IDs.
        general_channels_list = [f"<#{_id}>" for _id in channels if bot.get_channel(_id)]
        channels_str = "\n".join(general_channels_list) if general_channels_list else "No valid channels set."
    return channels_str

class ConfigCog(commands.Cog, name="Configuration"):
    """
    Commands for server administrators to configure the bot's settings.
    This cog provides a centralized way to manage various bot behaviors,
    such as prefixes, embed colors, economy settings, and allowed channels.
    All commands within this cog require administrator permissions.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _show_all_settings(self, ctx: commands.Context) -> None:
        """
        Helper function to display all server settings in a comprehensive embed message.
        This provides an overview of the bot's current configuration.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return

        # Fetch the current server configuration and extract economy settings.
        config = await get_server_config(ctx.guild.id)
        eco = config['economy']
        drop = eco.get('money_drop', {}) # Get money drop settings, defaulting to empty dict if not present.

        # Get the embed color from the server's configuration.
        color = await get_embed_color(ctx.guild.id)
        embed = discord.Embed(title=f"{ctx.guild.name}'s Bot Settings", color=color)

        # Retrieve the list of allowed channels for general bot commands.
        general_channels = config.get("allowed_channels", [])
        general_channels_str = get_allowed_str(self.bot, general_channels)

        # Retrieve the list of allowed channels specifically for money drops.
        moneydrop_channels = drop.get("allowed_channels", [])
        moneydrop_channels_str = get_allowed_str(self.bot, moneydrop_channels)


        # Add fields to the embed for different categories of settings.
        embed.add_field(name="General", value=f"Prefix: `{config['prefix']}`\n"
                        f"Color: `{config['embed_color']}`\n"
                        f"Channels: {general_channels_str}", inline=False)
        embed.add_field(name="Currency", value=f"Name: **{eco['currency_name']}**\n"
                        f"Symbol: **{eco['currency_symbol']}**", inline=True)
        embed.add_field(name="Starting Balance", value=f"**{eco['currency_symbol']}{eco['starting_balance']}**", inline=True)
        embed.add_field(name="Work", value=f"Cooldown: **{eco['work_cooldown_hours']}h**\n"
                        f"Range: **{eco['currency_symbol']}{eco['work_min_amount']} - {eco['currency_symbol']}{eco['work_max_amount']}**", inline=False)
        embed.add_field(name="Steal", value=f"Cooldown: **{eco['steal_cooldown_hours']}h**\n"
                        f"Chance: **{eco['steal_chance'] * 100:.0f}%**\n"
                        f"Penalty: **{eco['currency_symbol']}{eco['steal_penalty']}**\n"
                        f"Max: **{eco['steal_max_percentage'] * 100:.0f}%** of balance", inline=False)
        embed.add_field(name="Money Drops", value=f"Enabled: **{drop.get('enabled', False)}**\n"
                                                    f"Chance: **{drop.get('chance', 0.05) * 100:.0f}% per message**\n"
                                                    f"Min: **{eco['currency_symbol']}{drop.get('min_amount', 50)}**\n"
                                                    f"Max: **{eco['currency_symbol']}{drop.get('max_amount', 250)}**\n"
                                                    f"Channels: {moneydrop_channels_str}", inline=False)

        # Add a footer instructing users on how to get more specific help.
        embed.set_footer(text=f"Use '{config['prefix']}help config' to see how to change these values.")
        await ctx.send(embed=embed)

    @commands.group(name='config', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_cmd(self, ctx: commands.Context) -> None:
        """
        Base command for bot configuration.
        If no subcommand is given, it shows all current bot settings.
        """
        await self._show_all_settings(ctx)

    # --- GENERAL SUB-GROUP ---
    @config_cmd.group(name='general', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_general(self, ctx: commands.Context) -> None:
        """
        View or edit general bot settings like prefix and embed color.
        If no subcommand is given, it shows current general settings.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        general_channels = config.get("allowed_channels", [])
        general_channels_str = get_allowed_str(self.bot, general_channels)
        
        await send_embed(ctx, title="General Settings", description=f"Prefix: `{config['prefix']}`\nEmbed Color: `{config['embed_color']}`\nChannels: {general_channels_str}")

    @config_general.command(name="prefix")
    @commands.has_permissions(administrator=True)
    async def general_prefix(self, ctx: commands.Context, new_prefix: Optional[str] = None) -> None:
        """
        View or set the bot's command prefix.
        Parameters:
        - `new_prefix`: Optional. The new prefix to set. If None, shows current prefix.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        if new_prefix is None:
            # If no new prefix is provided, display the current one.
            config = await get_server_config(ctx.guild.id)
            await send_embed(ctx, f"The current prefix is `{config['prefix']}`.")
        else:
            # Update the prefix in the database.
            await update_server_config(ctx.guild.id, prefix=new_prefix)
            await send_embed(ctx, f"Command prefix updated to `{new_prefix}`.")

    @config_general.command(name="color")
    @commands.has_permissions(administrator=True)
    async def general_color(self, ctx: commands.Context, new_color: Optional[str] = None) -> None:
        """
        View or set the bot's embed color. Color should be a hexadecimal string (e.g., "#0000FF").
        Parameters:
        - `new_color`: Optional. The new hexadecimal color string. If None, shows current color.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        if new_color is None:
            config = await get_server_config(ctx.guild.id)
            await send_embed(ctx, f"The current embed color is `{config['embed_color']}`.")
        else:
            await update_server_config(ctx.guild.id, embed_color=new_color)
            await send_embed(ctx, f"Embed color updated to `{new_color}`.")

    @config_general.group(name="channel", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def general_channel(self, ctx: commands.Context) -> None:
        """
        Manage allowed channels for the bot.
        If no subcommand is given, lists currently allowed channels.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        channels = config.get("allowed_channels", [])
        if not channels:
            await send_embed(ctx, "All channels are currently allowed.")
            return

        # Create a list of channel mentions for display.
        channel_mentions = [f"<#{_id}>" for _id in channels if self.bot.get_channel(_id)]
        if not channel_mentions:
             await send_embed(ctx, "No valid channels set in the allowed list.")
             return
        await send_embed(ctx, title="Allowed Channels", description="\n".join(channel_mentions))

    @general_channel.command(name="toggle")
    @commands.has_permissions(administrator=True)
    async def general_channel_toggle(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """
        Toggle a specific channel in the allowed list.
        Adds the channel if not present, removes it if present.
        Parameters:
        - `channel`: The Discord text channel to toggle (automatically converted by Discord.py).
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        channels = config.get("allowed_channels", [])
        
        # If the setting is currently to disallow all ([-1]), reset to an empty list.
        # This allows individual channels to be added after disallowing all.
        if channels == [-1]:
            channels = []

        if channel.id in channels:
            channels.remove(channel.id)
            await send_embed(ctx, f"Removed {channel.mention} from allowed channels.")
        else:
            channels.append(channel.id)
            await send_embed(ctx, f"Added {channel.mention} to allowed channels.")
        # Update the allowed channels list in the database.
        await update_server_config(ctx.guild.id, allowed_channels=channels)

    @general_channel.command(name="all")
    @commands.has_permissions(administrator=True)
    async def general_channel_all(self, ctx: commands.Context) -> None:
        """
        Allows the bot to operate in all channels by setting the allowed_channels list to empty.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        await update_server_config(ctx.guild.id, allowed_channels=[])
        await send_embed(ctx, "All channels are now allowed.")

    @general_channel.command(name="none")
    @commands.has_permissions(administrator=True)
    async def general_channel_none(self, ctx: commands.Context) -> None:
        """
        Disallows the bot from operating in any channel by setting allowed_channels to [-1].
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        await update_server_config(ctx.guild.id, allowed_channels=[-1])
        await send_embed(ctx, "All channels are now disallowed.")


    # --- CURRENCY SUB-GROUP ---
    @config_cmd.group(name='currency', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_currency(self, ctx: commands.Context) -> None:
        """
        View or edit currency settings (name, symbol, starting balance).
        If no subcommand is given, shows current currency settings.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        eco = config['economy']
        await send_embed(ctx, title="Currency Settings", description=f"Name: **{eco['currency_name']}**\nSymbol: **{eco['currency_symbol']}**\nStarting Balance: **{eco['currency_symbol']}{eco['starting_balance']}**")

    @config_currency.command(name="name")
    @commands.has_permissions(administrator=True)
    async def currency_name(self, ctx: commands.Context, *, new_name: Optional[str] = None) -> None:
        """
        View or set the currency's name (e.g., dollars, coins).
        Parameters:
        - `new_name`: Optional. The new name for the currency. If None, shows current name.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        if new_name is None:
            config = await get_server_config(ctx.guild.id)
            await send_embed(ctx, f"The current currency name is **{config['economy']['currency_name']}**.")
        else:
            # Update nested dictionary field using a dictionary for `economy`.
            await update_server_config(ctx.guild.id, economy={'currency_name': new_name})
            await send_embed(ctx, f"Currency name updated to **{new_name}**.")

    @config_currency.command(name="symbol")
    @commands.has_permissions(administrator=True)
    async def currency_symbol(self, ctx: commands.Context, new_symbol: Optional[str] = None) -> None:
        """
        View or set the currency's symbol (e.g., $, £).
        Parameters:
        - `new_symbol`: Optional. The new symbol for the currency. If None, shows current symbol.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        if new_symbol is None:
            config = await get_server_config(ctx.guild.id)
            await send_embed(ctx, f"The current currency symbol is **{config['economy']['currency_symbol']}**.")
        else:
            await update_server_config(ctx.guild.id, economy={'currency_symbol': new_symbol})
            await send_embed(ctx, f"Currency symbol updated to **{new_symbol}**.")

    @config_currency.command(name="starting_balance")
    @commands.has_permissions(administrator=True)
    async def starting_balance(self, ctx: commands.Context, amount: Optional[int] = None) -> None:
        """
        View or set the starting balance for new users who join the server.
        Parameters:
        - `amount`: Optional. The new starting balance. If None, shows current starting balance.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        symbol = config['economy']['currency_symbol']
        if amount is None:
            await send_embed(ctx, f"The current starting balance is **{symbol}{config['economy']['starting_balance']}**.")
        else:
            await update_server_config(ctx.guild.id, economy={'starting_balance': amount})
            await send_embed(ctx, f"Starting balance updated to **{symbol}{amount}**.")

    # --- WORK SUB-GROUP ---
    @config_cmd.group(name='work', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_work(self, ctx: commands.Context) -> None:
        """
        View or edit settings for the 'work' command (cooldown, min/max earnings).
        If no subcommand is given, shows current work settings.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        eco = config['economy']
        symbol = eco['currency_symbol']
        await send_embed(ctx, title="Work Command Settings", description=f"Cooldown: **{eco['work_cooldown_hours']} hours**\nMinimum Amount: **{symbol}{eco['work_min_amount']}**\nMaximum Amount: **{symbol}{eco['work_max_amount']}**")

    @config_work.command(name="cooldown")
    @commands.has_permissions(administrator=True)
    async def work_cooldown(self, ctx: commands.Context, hours: Optional[int] = None) -> None:
        """
        View or set the cooldown period for the 'work' command in hours.
        Parameters:
        - `hours`: Optional. The new cooldown in hours. If None, shows current cooldown.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        if hours is None:
            config = await get_server_config(ctx.guild.id)
            await send_embed(ctx, f"The current work cooldown is **{config['economy']['work_cooldown_hours']} hours**.")
        else:
            await update_server_config(ctx.guild.id, economy={'work_cooldown_hours': hours})
            await send_embed(ctx, f"Work cooldown updated to **{hours} hours**.")

    @config_work.command(name="min")
    @commands.has_permissions(administrator=True)
    async def work_min(self, ctx: commands.Context, amount: Optional[int] = None) -> None:
        """
        View or set the minimum amount of money earned from the 'work' command.
        Parameters:
        - `amount`: Optional. The new minimum amount. If None, shows current minimum.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        symbol = config['economy']['currency_symbol']
        if amount is None:
            await send_embed(ctx, f"The current minimum work amount is **{symbol}{config['economy']['work_min_amount']}**.")
        else:
            await update_server_config(ctx.guild.id, economy={'work_min_amount': amount})
            await send_embed(ctx, f"Minimum work amount updated to **{symbol}{amount}**.")

    @config_work.command(name="max")
    @commands.has_permissions(administrator=True)
    async def work_max(self, ctx: commands.Context, amount: Optional[int] = None) -> None:
        """
        View or set the maximum amount of money earned from the 'work' command.
        Parameters:
        - `amount`: Optional. The new maximum amount. If None, shows current maximum.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        symbol = config['economy']['currency_symbol']
        if amount is None:
            await send_embed(ctx, f"The current maximum work amount is **{symbol}{config['economy']['work_max_amount']}**.")
        else:
            await update_server_config(ctx.guild.id, economy={'work_max_amount': amount})
            await send_embed(ctx, f"Maximum work amount updated to **{symbol}{amount}**.")
    
    # --- STEAL SUB-GROUP ---
    @config_cmd.group(name='steal', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_steal(self, ctx: commands.Context) -> None:
        """
        View or edit settings for the 'steal' command (cooldown, chance, penalty, max percentage).
        If no subcommand is given, shows current steal settings.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        eco = config['economy']
        symbol = eco['currency_symbol']
        await send_embed(ctx, title="Steal Command Settings", description=f"Cooldown: **{eco['steal_cooldown_hours']} hours**\nChance: **{eco['steal_chance'] * 100:.0f}%**\nPenalty: **{symbol}{eco['steal_penalty']}**\nMax: **{eco['steal_max_percentage'] * 100:.0f}%** of balance")

    @config_steal.command(name="cooldown")
    @commands.has_permissions(administrator=True)
    async def steal_cooldown(self, ctx: commands.Context, hours: Optional[int] = None) -> None:
        """
        View or set the cooldown period for the 'steal' command in hours.
        Parameters:
        - `hours`: Optional. The new cooldown in hours. If None, shows current cooldown.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        if hours is None:
            config = await get_server_config(ctx.guild.id)
            await send_embed(ctx, f"The current work cooldown is **{config['economy']['steal_cooldown_hours']} hours**.")
        else:
            await update_server_config(ctx.guild.id, economy={'steal_cooldown_hours': hours})
            await send_embed(ctx, f"Steal cooldown updated to **{hours} hours**.")
        
    
    @config_steal.command(name="chance")
    @commands.has_permissions(administrator=True)
    async def steal_chance(self, ctx: commands.Context, chance: Optional[float] = None) -> None:
        """
        View or set the chance to successfully steal (as a decimal, e.g., 0.25 for 25%).
        Parameters:
        - `chance`: Optional. The new chance as a decimal. If None, shows current chance.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        if chance is None:
            config = await get_server_config(ctx.guild.id)
            await send_embed(ctx, f"The current steal success chance is **{config['economy']['steal_chance'] * 100:.0f}%**.")
        else:
            await update_server_config(ctx.guild.id, economy={'steal_chance': chance})
            await send_embed(ctx, f"Steal success chance updated to **{chance * 100:.0f}%**.")

    @config_steal.command(name="penalty")
    @commands.has_permissions(administrator=True)
    async def steal_penalty(self, ctx: commands.Context, amount: Optional[int] = None) -> None:
        """
        View or set the amount of money a user loses if their steal attempt fails.
        Parameters:
        - `amount`: Optional. The new penalty amount. If None, shows current penalty.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        symbol = config['economy']['currency_symbol']
        if amount is None:
            await send_embed(ctx, f"The current steal penalty is **{symbol}{config['economy']['steal_penalty']}**.")
        else:
            await update_server_config(ctx.guild.id, economy={'steal_penalty': amount})
            await send_embed(ctx, f"Steal penalty updated to **{symbol}{amount}**.")

    @config_steal.command(name="max")
    @commands.has_permissions(administrator=True)
    async def steal_max(self, ctx: commands.Context, percentage: Optional[float] = None) -> None:
        """
        View or set the maximum percentage of a victim's balance that can be stolen.
        Parameters:
        - `percentage`: Optional. The new maximum percentage as a decimal. If None, shows current max.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        if percentage is None:
            config = await get_server_config(ctx.guild.id)
            await send_embed(ctx, f"The current max steal amount is **{config['economy']['steal_max_percentage'] * 100:.0f}%** of target's balance.")
        else:
            await update_server_config(ctx.guild.id, economy={'steal_max_percentage': percentage})
            await send_embed(ctx, f"Max steal percentage updated to **{percentage * 100:.0f}%**.")


    @config_cmd.group(name='moneydrop', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_moneydrop(self, ctx: commands.Context) -> None:
        """
        View or edit settings for random money drops (enabled, chance, min/max amounts, channels).
        If no subcommand is given, shows current money drop settings.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        drop = config['economy'].get('money_drop', {})
        symbol = config['economy']['currency_symbol']

        moneydrop_channels = drop.get("allowed_channels", [])
        moneydrop_channels_str = get_allowed_str(self.bot, moneydrop_channels)

        await send_embed(
            ctx,
            title="Money Drop Settings",
            description=f"Enabled: **{drop.get('enabled', False)}**\n"
                        f"Chance: **{drop.get('chance', 0.05) * 100:.0f}% per message**\n"
                        f"Min: **{symbol}{drop.get('min_amount', 50)}**\n"
                        f"Max: **{symbol}{drop.get('max_amount', 250)}**\n"
                        f"Channels: {moneydrop_channels_str}"
        )

    @config_moneydrop.command(name="enabled")
    @commands.has_permissions(administrator=True)
    async def moneydrop_enabled(self, ctx: commands.Context, toggle: Optional[bool] = None) -> None:
        """
        View or set whether money drops are enabled (True/False).
        Parameters:
        - `toggle`: Optional. Boolean value to enable or disable. If None, shows current status.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        if toggle is None:
            await send_embed(ctx, f"Money drops are currently **{'enabled' if config['economy']['money_drop']['enabled'] else 'disabled'}**.")
        else:
            money_drop_config = config['economy'].get('money_drop', {})
            money_drop_config['enabled'] = toggle
            await update_server_config(ctx.guild.id, economy={'money_drop': money_drop_config})
            await send_embed(ctx, f"Money drops have been **{'enabled' if toggle else 'disabled'}**.")

    @config_moneydrop.command(name="chance")
    @commands.has_permissions(administrator=True)
    async def moneydrop_chance(self, ctx: commands.Context, chance: Optional[float] = None) -> None:
        """
        View or set the probability (as a decimal) of a money drop occurring per message.
        Parameters:
        - `chance`: Optional. The new chance as a decimal (e.g., 0.05 for 5%). If None, shows current chance.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        if chance is None:
            await send_embed(ctx, f"Current money drop chance: **{config['economy']['money_drop']['chance'] * 100:.0f}%** per message.")
        else:
            money_drop_config = config['economy'].get('money_drop', {})
            money_drop_config['chance'] = chance
            await update_server_config(ctx.guild.id, economy={'money_drop': money_drop_config})
            await send_embed(ctx, f"Money drop chance updated to **{chance * 100:.0f}%** per minute.")

    @config_moneydrop.command(name="min")
    @commands.has_permissions(administrator=True)
    async def moneydrop_min(self, ctx: commands.Context, amount: Optional[int] = None) -> None:
        """
        View or set the minimum amount of money that can appear in a money drop.
        Parameters:
        - `amount`: Optional. The new minimum amount. If None, shows current minimum.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        symbol = config['economy']['currency_symbol']
        if amount is None:
            await send_embed(ctx, f"Minimum drop amount is **{symbol}{config['economy']['money_drop']['min_amount']}**.")
        else:
            money_drop_config = config['economy'].get('money_drop', {})
            money_drop_config['min_amount'] = amount
            await update_server_config(ctx.guild.id, economy={'money_drop': money_drop_config})
            await send_embed(ctx, f"Minimum drop amount updated to **{symbol}{amount}**.")

    @config_moneydrop.command(name="max")
    @commands.has_permissions(administrator=True)
    async def moneydrop_max(self, ctx: commands.Context, amount: Optional[int] = None) -> None:
        """
        View or set the maximum amount of money that can appear in a money drop.
        Parameters:
        - `amount`: Optional. The new maximum amount. If None, shows current maximum.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        symbol = config['economy']['currency_symbol']
        if amount is None:
            await send_embed(ctx, f"Maximum drop amount is **{symbol}{config['economy']['money_drop']['max_amount']}**.")
        else:
            money_drop_config = config['economy'].get('money_drop', {})
            money_drop_config['max_amount'] = amount
            await update_server_config(ctx.guild.id, economy={'money_drop': money_drop_config})
            await send_embed(ctx, f"Maximum drop amount updated to **{symbol}{amount}**.")

    @config_moneydrop.group(name="channel", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def moneydrop_channel(self, ctx: commands.Context) -> None:
        """
        Manage allowed channels for money dropping.
        If no subcommand is given, lists currently allowed channels for money drops.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        channels = config["economy"]["money_drop"].get("allowed_channels", [])
        channels_str = get_allowed_str(self.bot, channels)
        await send_embed(ctx, title="Allowed Money Drop Channels", description="\n".join(channels_str))

    @moneydrop_channel.command(name="toggle")
    @commands.has_permissions(administrator=True)
    async def moneydrop_channel_toggle(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """
        Toggle a specific channel in the allowed list for money drops.
        Adds the channel if not present, removes it if present.
        Parameters:
        - `channel`: The Discord text channel to toggle.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        money_drop_config = config['economy'].get('money_drop', {})
        channels = money_drop_config.get("allowed_channels", [])
        
        # If currently disallowing all channels ([-1]), reset to empty list.
        if channels == [-1]:
            channels = []

        if channel.id in channels:
            channels.remove(channel.id)
            await send_embed(ctx, f"Removed {channel.mention} from allowed money drop channels.")
        else:
            channels.append(channel.id)
            await send_embed(ctx, f"Added {channel.mention} to allowed money drop channels.")
        
        money_drop_config['allowed_channels'] = channels # Update the nested dictionary.
        await update_server_config(ctx.guild.id, economy={'money_drop': money_drop_config})

    @moneydrop_channel.command(name="all")
    @commands.has_permissions(administrator=True)
    async def moneydrop_channel_all(self, ctx: commands.Context) -> None:
        """
        Allows money drops in all channels by setting the allowed_channels list to empty.
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        money_drop_config = config['economy'].get('money_drop', {})
        money_drop_config['allowed_channels'] = []
        await update_server_config(ctx.guild.id, economy={'money_drop': money_drop_config})
        await send_embed(ctx, "All channels are now allowed for money drops.")

    @moneydrop_channel.command(name="none")
    @commands.has_permissions(administrator=True)
    async def moneydrop_channel_none(self, ctx: commands.Context) -> None:
        """
        Disallows money drops in all channels by setting allowed_channels to [-1].
        """
        if not ctx.guild:
            await send_embed(ctx, "You must be in a server to use this command.")
            return
        config = await get_server_config(ctx.guild.id)
        money_drop_config = config['economy'].get('money_drop', {})
        money_drop_config['allowed_channels'] = [-1]
        await update_server_config(ctx.guild.id, economy={'money_drop': money_drop_config})
        await send_embed(ctx, "All channels are now disallowed for money drops.")

async def setup(bot: commands.Bot) -> None:
    """
    Sets up the ConfigCog by adding it to the bot.
    This function is called by Discord.py when loading extensions.
    """
    await bot.add_cog(ConfigCog(bot))