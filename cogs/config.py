import discord
from discord.ext import commands
from utils.supabase_client import get_server_config, update_server_config, ServerConfig
from utils.helpers import get_embed_color, guild_only
from typing import List, Optional

def get_allowed_str(bot: commands.Bot, channels: List[str]):
    """Formats a list of channel IDs into a user-friendly string."""
    if not channels:
        return "All channels currently allowed." # If empty, all are allowed.
    elif channels == ["-1"]:
        return "All channels currently disallowed." # If "-1", none are allowed.
    else:
        # Format channel mentions for display, filtering out invalid channel IDs.
        general_channels_list = [f"<#{_id}>" for _id in channels if bot.get_channel(int(_id))]
        return "\n".join(general_channels_list) if general_channels_list else "No valid channels set."

class ConfigCog(commands.Cog, name="Configuration"):
    """Cog for all configuration-related commands."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="config")
    @guild_only()
    @commands.has_permissions(administrator=True)
    async def config_command(self, ctx: commands.Context):
        """Displays the main configuration menu."""
        view = ConfigMainMenuView(ctx, self)
        embed = await view.update_embed("general")
        view.message = await ctx.send(embed=embed, view=view)

class ConfigMainMenuView(discord.ui.View):
    """The main view for navigating and editing bot configurations."""
    def __init__(self, ctx: commands.Context, cog: ConfigCog) -> None:
        super().__init__(timeout=300)
        self.ctx = ctx
        self.bot = ctx.bot
        self.cog = cog
        self.message: Optional[discord.Message] = None
        self.current_section = "general"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the command author can interact with the view."""
        return interaction.user.id == self.ctx.author.id

    async def update_embed(self, section: str) -> discord.Embed:
        """Updates the embed to display the specified configuration section."""
        assert self.ctx.guild is not None
        self.current_section = section
        config = await get_server_config(self.ctx.guild.id)
        color = await get_embed_color(self.ctx.guild.id)
        eco = config.get('economy', {})
        drop = eco.get('money_drop', {})

        if section == "general":
            embed = discord.Embed(title="General Settings", color=color)
            embed.add_field(name="Prefix", value=f"`{config.get('prefix', '!')}`")
            embed.add_field(name="Embed Color", value=f"`{config.get('embed_color', '#0000FF')}`")
            embed.add_field(name="Allowed Channels", value=get_allowed_str(self.bot, config.get("allowed_channels", [])), inline=False)
        elif section == "currency":
            embed = discord.Embed(title="Currency Settings", color=color)
            embed.add_field(name="Name", value=f"**{eco['currency_name']}**")
            embed.add_field(name="Symbol", value=f"**{eco['currency_symbol']}**")
            embed.add_field(name="Starting Balance", value=f"**{eco['currency_symbol']}{eco['starting_balance']}**")
        elif section == "work":
            embed = discord.Embed(title="Work Settings", color=color)
            embed.add_field(name="Cooldown", value=f"**{eco['work_cooldown_hours']}h**")
            embed.add_field(name="Range", value=f"**{eco['currency_symbol']}{eco['work_min_amount']} - {eco['currency_symbol']}{eco['work_max_amount']}**")
        elif section == "steal":
            embed = discord.Embed(title="Steal Settings", color=color)
            embed.add_field(name="Cooldown", value=f"**{eco['steal_cooldown_hours']}h**")
            embed.add_field(name="Chance", value=f"**{eco['steal_chance'] * 100:.0f}%**")
            embed.add_field(name="Penalty", value=f"**{eco['currency_symbol']}{eco['steal_penalty']}**")
            embed.add_field(name="Max %", value=f"**{eco['steal_max_percentage'] * 100:.0f}%**")
        elif section == "moneydrop":
            embed = discord.Embed(title="Money Drop Settings", color=color)
            embed.add_field(name="Enabled", value=f"**{drop.get('enabled', False)}**")
            embed.add_field(name="Chance", value=f"**{drop.get('chance', 0.05) * 100:.0f}%**")
            embed.add_field(name="Min-Max", value=f"**{eco['currency_symbol']}{drop.get('min_amount', 50)} - {eco['currency_symbol']}{drop.get('max_amount', 250)}**")
            embed.add_field(name="Channels", value=get_allowed_str(self.bot, drop.get("allowed_channels", [])) or "All", inline=False)
        else:
            embed = discord.Embed(title="Configuration", description="Invalid section.", color=color)
            
        return embed

    @discord.ui.button(label="General", style=discord.ButtonStyle.primary, custom_id="config:general")
    async def general(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = await self.update_embed("general")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Currency", style=discord.ButtonStyle.primary, custom_id="config:currency")
    async def currency(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = await self.update_embed("currency")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Work", style=discord.ButtonStyle.primary, custom_id="config:work")
    async def work(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = await self.update_embed("work")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Steal", style=discord.ButtonStyle.primary, custom_id="config:steal")
    async def steal(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = await self.update_embed("steal")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Money Drop", style=discord.ButtonStyle.primary, custom_id="config:moneydrop")
    async def moneydrop(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = await self.update_embed("moneydrop")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, custom_id="config:edit")
    async def edit(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Opens the appropriate modal to edit the current section."""
        assert self.ctx.guild is not None
        config = await get_server_config(self.ctx.guild.id)
        
        modals = {
            "general": GeneralSettingsModal(self.ctx, self, config),
            "currency": CurrencySettingsModal(self.ctx, self, config),
            "work": WorkSettingsModal(self.ctx, self, config),
            "steal": StealSettingsModal(self.ctx, self, config),
            "moneydrop": MoneyDropSettingsModal(self.ctx, self, config)
        }
        
        if modal := modals.get(self.current_section):
            await interaction.response.send_modal(modal)

# --- Modals for Editing Configuration ---

class GeneralSettingsModal(discord.ui.Modal, title="Edit General Settings"):
    def __init__(self, ctx: commands.Context, parent_view: ConfigMainMenuView, config: ServerConfig):
        super().__init__()
        self.ctx = ctx
        self.parent_view = parent_view
        
        self.prefix = discord.ui.TextInput(label="Prefix", default=config.get('prefix', '!'))
        self.embed_color = discord.ui.TextInput(label="Embed Color", default=config.get('embed_color', '#0000FF'))
        self.add_item(self.prefix)
        self.add_item(self.embed_color)

    async def on_submit(self, interaction: discord.Interaction):
        assert self.ctx.guild is not None, "This command can only be used in a guild."
        
        try:
            if not self.prefix.value or len(self.prefix.value) > 10: # Check if prefix is empty or too long
                raise ValueError("Prefix must be between 1 and 10 characters.")
            if self.prefix.value.isdigit(): # Check if prefix is a number
                raise ValueError("Prefix cannot be a number.")
            
            # Check if embed color is a valid hex
            hex_int = int(self.embed_color.value.lstrip('#'), 16)
            if len(self.embed_color.value.lstrip('#')) != 6 or hex_int < 0 or hex_int > 0xFFFFFF:
                raise ValueError("Embed color must be a valid hex color (e.g., #0000FF).")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid input: {e}", ephemeral=True)
            return
        
        await update_server_config(self.ctx.guild.id, prefix=self.prefix.value, embed_color=self.embed_color.value)
        await interaction.response.send_message("General settings updated!", ephemeral=True)
        
        embed = await self.parent_view.update_embed("general")
        if self.parent_view.message:
            await self.parent_view.message.edit(embed=embed)


class CurrencySettingsModal(discord.ui.Modal, title="Edit Currency Settings"):
    def __init__(self, ctx: commands.Context, parent_view: ConfigMainMenuView, config: ServerConfig):
        super().__init__()
        self.ctx = ctx
        self.parent_view = parent_view
        eco = config.get('economy', {})
        
        self.currency_name = discord.ui.TextInput(label="Currency Name", default=eco.get('currency_name', 'pounds'))
        self.currency_symbol = discord.ui.TextInput(label="Currency Symbol", default=eco.get('currency_symbol', '£'))
        self.starting_balance = discord.ui.TextInput(label="Starting Balance", default=str(eco.get('starting_balance', 1000)))
        self.add_item(self.currency_name)
        self.add_item(self.currency_symbol)
        self.add_item(self.starting_balance)

    async def on_submit(self, interaction: discord.Interaction):
        assert self.ctx.guild is not None, "This command can only be used in a guild."
        
        try: # Validate and convert starting balance to an integer.
            if not (self.starting_balance.value and self.starting_balance.value.isdigit()):
                raise ValueError("Please enter a number.")
            starting_balance = int(self.starting_balance.value)
            if starting_balance < 0:
                raise ValueError("Starting balance must be non-negative.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid starting balance: {e}", ephemeral=True)
            return
        
        if not self.currency_symbol.value or len(self.currency_symbol.value) > 5: # Check if currency symbol is empty or too long
            await interaction.response.send_message("Invalid currency symbol: Currency symbol must be between 1 and 5 characters.", ephemeral=True)
            return
        
        if not self.currency_name.value or len(self.currency_name.value) > 20: # Check if currency name is empty or too long
            await interaction.response.send_message("Invalid currency name: Currency name must be between 1 and 20 characters.", ephemeral=True)
            return

        economy_settings = {
            "currency_name": self.currency_name.value,
            "currency_symbol": self.currency_symbol.value,
            "starting_balance": starting_balance
        }
        await update_server_config(self.ctx.guild.id, economy=economy_settings)
        await interaction.response.send_message("Currency settings updated!", ephemeral=True)

        embed = await self.parent_view.update_embed("currency")
        if self.parent_view.message:
            await self.parent_view.message.edit(embed=embed)


class WorkSettingsModal(discord.ui.Modal, title="Edit Work Settings"):
    def __init__(self, ctx: commands.Context, parent_view: ConfigMainMenuView, config: ServerConfig):
        super().__init__()
        self.ctx = ctx
        self.parent_view = parent_view
        eco = config.get('economy', {})

        self.work_cooldown_hours = discord.ui.TextInput(label="Work Cooldown (hours)", default=str(eco.get('work_cooldown_hours', 1)))
        self.work_min_amount = discord.ui.TextInput(label="Work Min Amount", default=str(eco.get('work_min_amount', 50)))
        self.work_max_amount = discord.ui.TextInput(label="Work Max Amount", default=str(eco.get('work_max_amount', 500)))
        self.add_item(self.work_cooldown_hours)
        self.add_item(self.work_min_amount)
        self.add_item(self.work_max_amount)
        
    async def on_submit(self, interaction: discord.Interaction):
        assert self.ctx.guild is not None, "This command can only be used in a guild."

        try: # Validate and convert work cooldown to an integer.
            if not (self.work_cooldown_hours.value and self.work_cooldown_hours.value.isdigit()):
                raise ValueError("Cooldown hours must be a valid number.")
            work_cooldown_hours = int(self.work_cooldown_hours.value)
            if work_cooldown_hours < 0:
                raise ValueError("Cooldown hours must be non-negative.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid cooldown hours: {e}", ephemeral=True)
            return

        try: # Validate and convert work amount range to an integer.

            if ((not (self.work_min_amount.value and self.work_max_amount.value)) and 
                (not (self.work_min_amount.value.isdigit() and self.work_max_amount.value.isdigit()))):
                raise ValueError("Min and max amounts must be valid numbers.")
            
            work_min_amount = int(self.work_min_amount.value)
            work_max_amount = int(self.work_max_amount.value)
            if work_min_amount < 0 or work_max_amount < 0:
                raise ValueError("Min and max amounts must be non-negative.")
            if work_min_amount > work_max_amount:
                raise ValueError("Min amount cannot be greater than max amount.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid work amount: {e}", ephemeral=True)
            return

        economy_settings = {
            "work_cooldown_hours": work_cooldown_hours,
            "work_min_amount": work_min_amount,
            "work_max_amount": work_max_amount
        }
        await update_server_config(self.ctx.guild.id, economy=economy_settings)
        await interaction.response.send_message("Work settings updated!", ephemeral=True)
        
        embed = await self.parent_view.update_embed("work")
        if self.parent_view.message:
            await self.parent_view.message.edit(embed=embed)

class StealSettingsModal(discord.ui.Modal, title="Edit Steal Settings"):
    def __init__(self, ctx: commands.Context, parent_view: ConfigMainMenuView, config: ServerConfig):
        super().__init__()
        self.ctx = ctx
        self.parent_view = parent_view
        eco = config.get('economy', {})

        self.steal_cooldown_hours = discord.ui.TextInput(label="Steal Cooldown (hours)", default=str(eco.get('steal_cooldown_hours', 6)))
        self.steal_chance = discord.ui.TextInput(label="Steal Chance (0.0 to 1.0)", default=str(eco.get('steal_chance', 0.65)))
        self.steal_penalty = discord.ui.TextInput(label="Steal Penalty", default=str(eco.get('steal_penalty', 100)))
        self.steal_max_percentage = discord.ui.TextInput(label="Steal Max Percentage (0.0 to 1.0)", default=str(eco.get('steal_max_percentage', 0.25)))
        self.add_item(self.steal_cooldown_hours)
        self.add_item(self.steal_chance)
        self.add_item(self.steal_penalty)
        self.add_item(self.steal_max_percentage)

    async def on_submit(self, interaction: discord.Interaction):
        assert self.ctx.guild is not None, "This command can only be used in a guild."

        try: # Validate and convert steal cooldown to an integer.
            if not (self.steal_cooldown_hours.value and self.steal_cooldown_hours.value.isdigit()):
                raise ValueError("Cooldown hours must be a valid number.")
            steal_cooldown_hours = int(self.steal_cooldown_hours.value)
            if steal_cooldown_hours < 0:
                raise ValueError("Cooldown hours must be non-negative.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid cooldown hours: {e}", ephemeral=True)
            return
        
        try: # Validate and convert steal chance to a float.
            if not (self.steal_chance.value and self.steal_chance.value.replace('.', '', 1).isdigit()):
                raise ValueError("Steal chance must be a valid number between 0.0 and 1.0.")
            steal_chance = float(self.steal_chance.value)
            if not (0 <= steal_chance <= 1):
                raise ValueError("Steal chance must be between 0.0 and 1.0.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid steal chance: {e}", ephemeral=True)
            return
        
        try: # Validate and convert steal penalty to an integer.
            if not (self.steal_penalty.value and self.steal_penalty.value.isdigit()):
                raise ValueError("Steal penalty must be a valid number.")
            steal_penalty = int(self.steal_penalty.value)
            if steal_penalty < 0:
                raise ValueError("Steal penalty must be non-negative.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid steal penalty: {e}", ephemeral=True)
            return
        
        try: # Validate and convert steal max percentage to a float.
            if not (self.steal_max_percentage.value and self.steal_max_percentage.value.replace('.', '', 1).isdigit()):
                raise ValueError("Steal max percentage must be a valid number between 0.0 and 1.0.")
            steal_max_percentage = float(self.steal_max_percentage.value)
            if not (0 <= steal_max_percentage <= 1):
                raise ValueError("Steal max percentage must be between 0.0 and 1.0.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid steal max percentage: {e}", ephemeral=True)
            return

        economy_settings = {
            "steal_cooldown_hours": steal_cooldown_hours,
            "steal_chance": steal_chance,
            "steal_penalty": steal_penalty,
            "steal_max_percentage": steal_max_percentage
        }
        await update_server_config(self.ctx.guild.id, economy=economy_settings)
        await interaction.response.send_message("Steal settings updated!", ephemeral=True)

        embed = await self.parent_view.update_embed("steal")
        if self.parent_view.message:
            await self.parent_view.message.edit(embed=embed)


class MoneyDropSettingsModal(discord.ui.Modal, title="Edit Money Drop Settings"):
    def __init__(self, ctx: commands.Context, parent_view: ConfigMainMenuView, config: ServerConfig):
        super().__init__()
        self.ctx = ctx
        self.parent_view = parent_view
        drop = config.get('economy', {}).get('money_drop', {})

        self.enabled = discord.ui.TextInput(label="Enabled (True/False)", default=str(drop.get('enabled', False)))
        self.chance = discord.ui.TextInput(label="Chance (0.0 to 1.0)", default=str(drop.get('chance', 0.05)))
        self.min_amount = discord.ui.TextInput(label="Min Amount", default=str(drop.get('min_amount', 50)))
        self.max_amount = discord.ui.TextInput(label="Max Amount", default=str(drop.get('max_amount', 150)))
        self.add_item(self.enabled)
        self.add_item(self.chance)
        self.add_item(self.min_amount)
        self.add_item(self.max_amount)
        
    async def on_submit(self, interaction: discord.Interaction):
        assert self.ctx.guild is not None, "This command can only be used in a guild."

        try: # Validate enabled value.
            if self.enabled.value.lower() not in ('true', 'false', "0", "1", "yes", "no", "on", "off"):
                raise ValueError("Enabled must be 'True' or 'False'.")
            enabled = self.enabled.value.lower() in ('true', "1", "yes", "on")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid enabled value: {e}", ephemeral=True)
            return
        
        try: # Validate and convert chance to a float.
            if not (self.chance.value and self.chance.value.replace('.', '', 1).isdigit()):
                raise ValueError("Chance must be a valid number between 0.0 and 1.0.")
            chance = float(self.chance.value)
            if not (0 <= chance <= 1):
                raise ValueError("Chance must be between 0.0 and 1.0.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid chance: {e}", ephemeral=True)
            return

        try: # Validate and convert amount range to an integer.

            if ((not (self.min_amount.value and self.max_amount.value)) and
                (not (self.min_amount.value.isdigit() and self.max_amount.value.isdigit()))):
                raise ValueError("Min and max amounts must be valid numbers.")

            min_amount = int(self.min_amount.value)
            max_amount = int(self.max_amount.value)
            if min_amount < 0 or max_amount < 0:
                raise ValueError("Min and max amounts must be non-negative.")
            if min_amount > max_amount:
                raise ValueError("Min amount cannot be greater than max amount.")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid amount: {e}", ephemeral=True)
            return

        money_drop_settings = {
            "enabled": enabled,
            "chance": chance,
            "min_amount": min_amount,
            "max_amount": max_amount
        }
        await update_server_config(self.ctx.guild.id, economy={"money_drop": money_drop_settings})
        await interaction.response.send_message("Money Drop settings updated!", ephemeral=True)

        embed = await self.parent_view.update_embed("moneydrop")
        if self.parent_view.message:
            await self.parent_view.message.edit(embed=embed)

async def setup(bot: commands.Bot) -> None:
    """Sets up the ConfigCog and adds it to the bot."""
    await bot.add_cog(ConfigCog(bot))