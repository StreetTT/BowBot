import discord
from discord.ext import commands
from typing import Optional
from utils.supabase_client import update_user_balance, get_server_config
from utils.helpers import format_currency
from cogs.economy import post_money_log


class DropView(discord.ui.View):
    """
    View for the money drop button. This allows users to claim random money drops.
    Discord.ui.View enables interactive components like buttons on messages.
    """
    def __init__(self, amount: int, currency_symbol: str, guild_id: int, bot: commands.Bot) -> None:
        super().__init__(timeout=30.0)
        self.amount = amount
        self.currency_symbol = currency_symbol
        self.guild_id = guild_id
        self.bot = bot
        self.claimed = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Claim!", style=discord.ButtonStyle.green)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """
        Callback function for the "Claim!" button.
        Handles the logic when a user attempts to claim the money drop.
        Parameters:
        - `interaction`: The interaction object representing the button click.
        - `button`: The button object that was clicked.
        """
        if self.claimed:
            # If already claimed, send an ephemeral message (only visible to the interactor).
            await interaction.response.send_message("Sorry, this drop has already been claimed!", ephemeral=True)
            return

        self.claimed = True # Mark the drop as claimed.
        # Update the button's label and style to indicate it's claimed and disable it.
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.grey
        button.disabled = True
        if interaction.message:
            self.message = interaction.message
            await interaction.message.edit(view=self)

        # Update the user's balance in the database.
        await update_user_balance(self.guild_id, interaction.user.id, self.amount, "money_drop_claim", "BOT")
        formatted_amount = await format_currency(self.guild_id, self.amount)

        # Send an ephemeral message confirming the claim to the user.
        await interaction.response.send_message(f"You claimed {formatted_amount}!", ephemeral=True)

        if log_channel_id := (await get_server_config(self.guild_id)).get('log'):
            await post_money_log(self.bot, self.guild_id, log_channel_id, "money_drop_claim", self.amount, "BOT", interaction.user.id)

    async def on_timeout(self) -> None:
        """
        Called when the view times out (i.e., no one clicks the button within the timeout period).
        Updates the message to indicate the drop went unclaimed and disables the button.
        """
        if self.message and not self.claimed:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.label = "Unclaimed"
                    item.style = discord.ButtonStyle.grey
                    item.disabled = True
            await self.message.edit(view=self)


class EventsCog(commands.Cog, name="Events"):
    """
    Handles background tasks and events like money drops.
    This cog is intended for functionalities that run in response to Discord events
    or on a schedule, rather than direct commands.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # def cog_unload(self) -> None:
    #     """
    #     Cleanup method called when the cog is unloaded.
    #     Currently empty, but can be used for stopping tasks or closing resources.
    #     """
    #     pass # Placeholder for future cleanup tasks.

async def setup(bot: commands.Bot) -> None:
    """
    Sets up the Events cog by adding it to the bot.
    This function is called by Discord.py when loading extensions.
    """
    # The line `await bot.add_cog(EventsCog(bot))` is commented out because
    # the main `on_message` event responsible for initiating money drops
    # is handled directly in `bot.py` to avoid circular import issues.
    # If this cog had other independent event listeners, it would be uncommented.
    # await bot.add_cog(EventsCog(bot))
    pass