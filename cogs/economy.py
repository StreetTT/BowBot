import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta, timezone
from string import ascii_uppercase, digits
from utils.supabase_client import (
    get_user_economy_data,
    update_user_balance,
    update_user_economy,
    get_server_config,
    get_multiple_user_economy_data,
    EconomyData
)
from typing import Optional, List, Union, Dict, Any
from utils.helpers import *

# Number of entries per page in the leaderboard
LEADERBOARD_ENTRIES_PER_PAGE = 10

class LeaderboardView(discord.ui.View):
    """
    A Discord UI View for the paginated leaderboard, containing navigation buttons.
    """
    def __init__(self, ctx: commands.Context, all_entries: List[EconomyData], total_pages: int) -> None:
        super().__init__(timeout=120.0)  # Timeout after 2 minutes of inactivity
        self.ctx = ctx
        self.all_entries = all_entries
        self.total_pages = total_pages
        self.current_page = 0
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Ensures that only the command invoker can interact with the buttons.
        """
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your leaderboard!", ephemeral=True)
            return False
        return True

    async def _update_leaderboard_embed(self) -> discord.Embed:
        """
        Helper to create and return the leaderboard embed for the current page.
        """
        assert self.ctx.guild is not None

        guild_id = self.ctx.guild.id 
        color = await get_embed_color(guild_id)
        embed = discord.Embed(title=f"Leaderboard", color=color)

        start_index = self.current_page * LEADERBOARD_ENTRIES_PER_PAGE
        end_index = start_index + LEADERBOARD_ENTRIES_PER_PAGE
        
        # Determine the users to display on the current page
        current_page_entries = self.all_entries[start_index:end_index]

        # Add fields for each user on the current page
        for i, entry in enumerate(current_page_entries):
            global_rank = start_index + i + 1 # Calculate rank
            user_id = entry['user_id']
            balance_val = entry['balance']

            try:
                user: discord.User = self.ctx.bot.get_user(user_id) or await self.ctx.bot.fetch_user(user_id)
                user_name = user.display_name
                # user_avatar_url = user.display_avatar.url # Removed: Not used for individual display
            except discord.NotFound:
                user_name = "Unknown User"
                # user_avatar_url = "" # Removed: Not used for individual display

            formatted_bal = await format_currency(guild_id, balance_val)
            
            embed.add_field(
                name=f"{global_rank}. {user_name}",
                value=f"{formatted_bal}",
                inline=False
            )
            # if user_avatar_url:
            #     embed.set_thumbnail(url=user_avatar_url) # Removed: Only allows one thumbnail per embed.


        embed.set_footer(text=f"Requested by {self.ctx.author.display_name} | Page {self.current_page + 1}/{self.total_pages}",
                         icon_url=self.ctx.author.display_avatar.url if self.ctx.author.avatar else None
        )
        return embed

    async def _update_message(self) -> None:
        """Updates the message with the new embed and view."""
        if self.message:
            embed = await self._update_leaderboard_embed()
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Left", style=discord.ButtonStyle.blurple)
    async def left_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = (self.current_page - 1) % self.total_pages
        await interaction.response.edit_message(embed=await self._update_leaderboard_embed(), view=self)

    @discord.ui.button(label="Self", style=discord.ButtonStyle.grey)
    async def self_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        user_id = self.ctx.author.id
        # Find the user's rank
        for i, entry in enumerate(self.all_entries):
            if entry['user_id'] == user_id:
                target_page = i // LEADERBOARD_ENTRIES_PER_PAGE
                if self.current_page != target_page:
                    self.current_page = target_page
                    await interaction.response.edit_message(embed=await self._update_leaderboard_embed(), view=self)
                else:
                    await interaction.response.send_message("You are already on your page!", ephemeral=True)
                return
        await interaction.response.send_message("You are not currently on the leaderboard. Participate in the economy!", ephemeral=True)

    @discord.ui.button(label="Right ➡️", style=discord.ButtonStyle.blurple)
    async def right_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = (self.current_page + 1) % self.total_pages
        await interaction.response.edit_message(embed=await self._update_leaderboard_embed(), view=self)

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None) # Remove buttons on timeout

class EconomyCog(commands.Cog, name="Economy"):
    """
    Commands for interacting with the server's economy system.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name='balance', aliases=['bal'])
    @guild_only()
    @in_allowed_channels()
    async def balance(self, ctx: commands.Context, member_str: Optional[Union[discord.Member, str]] = None) -> None:
        """
        Checks your or another user's balance.
        Parameters: 
        - `member`: Optional. The member whose balance to check. Defaults to the command invoker.
        """
        assert ctx.guild is not None
        member = ctx.author


        # If no member is specified, default to the command author.
        if member_str:
            try:
                member = await get_user_from_arg(member_str, ctx)
            except Exception as e:
                if not (str(e) == "Member not found."):
                    raise  # re-raise unexpected exceptions
                    
        # Fetch economy data for the specified user. `get_user_economy_data` usually creates data if none
        user_data = await get_user_economy_data(ctx.guild.id, member.id)
        balance_val = user_data.get('balance', 0)
        
        formatted_bal = await format_currency(ctx.guild.id, balance_val)
        await send_embed(ctx, f"{member.mention}'s balance is {formatted_bal}.", image_url=member.display_avatar.url)

    @commands.command(name='leaderboard', aliases=['lb'])
    @guild_only()
    @in_allowed_channels()
    async def leaderboard(self, ctx: commands.Context) -> None:
        """
        Shows the server's economy leaderboard, displaying paginated results.
        """
        assert ctx.guild is not None

        all_entries = await get_multiple_user_economy_data(ctx.guild.id)
        all_entries.sort(key=lambda x: x['balance'], reverse=True)

        if not all_entries:
            await send_embed(ctx, "No one has participated in the economy yet.")
            return

        total_pages = (len(all_entries) + LEADERBOARD_ENTRIES_PER_PAGE - 1) // LEADERBOARD_ENTRIES_PER_PAGE
        
        # Initialize the view and send the first page
        view = LeaderboardView(ctx, all_entries, total_pages)
        initial_embed = await view._update_leaderboard_embed()
        view.message = await ctx.send(embed=initial_embed, view=view)


    @commands.command(name='work', aliases=['w'])
    @guild_only()
    @in_allowed_channels()
    async def work(self, ctx: commands.Context) -> None:
        """
        Allows a user to 'work' to earn a random amount of money.
        """
        assert ctx.guild is not None

        guild_id = ctx.guild.id
        user_id = ctx.author.id
        # Get server and economy specific configurations.
        config = await get_server_config(guild_id)
        eco_config = config['economy']

        # Fetch user's economy data to check their last work time.
        user_data = await get_user_economy_data(guild_id, user_id)
        last_work_str: Optional[str] = user_data.get('last_work')
        if last_work_str:
            # Convert the stored ISO format string timestamp to a timezone-aware datetime object.
            last_work_time = datetime.fromisoformat(last_work_str).astimezone(timezone.utc)
            
            # Check if the cooldown period has passed.
            cooldown = timedelta(hours=eco_config['work_cooldown_hours'])
            if datetime.now(timezone.utc) < last_work_time + cooldown:
                remaining = (last_work_time + cooldown) - datetime.now(timezone.utc)
                # Inform the user about the remaining cooldown.
                await send_embed(ctx, f"You're tired. You can work again in **{str(timedelta(seconds=int(remaining.total_seconds())))}**.")
                return

        # Calculate random earnings within the configured range.
        earnings = random.randint(eco_config['work_min_amount'], eco_config['work_max_amount'])
        await update_user_balance(guild_id, user_id, earnings, "work", "USER")
        await update_user_economy(guild_id, user_id, {'last_work': datetime.now(timezone.utc).isoformat()})

        # Inform the user about their earnings.
        formatted_earnings = await format_currency(guild_id, earnings)
        await send_embed(ctx, f"You worked hard and earned {formatted_earnings}!")

        if log_channel_id := eco_config.get('log_channel'):
            await post_money_log(self.bot, guild_id, log_channel_id, "work", earnings, "USER", user_id)

    @commands.command(name='steal', aliases=['rob', 's'])
    @guild_only()
    @in_allowed_channels()
    async def steal(self, ctx: commands.Context, member: Optional[Union[discord.Member, str]] = None) -> None:
        """
        Attempt to steal money from another member.
        Parameters:
        - `member`: Optional. The target member to steal from. If None, a random non-bot member is chosen.
        """
        assert ctx.guild is not None

        try:
            member = await get_user_from_arg(member, ctx, True)
        except Exception as e:
            if str(e) == "No non-bot members in the guild.":
                await send_embed(ctx, "There's no one to steal from!")
                return
            else:
                raise  # re-raise unexpected exceptions

        guild_id = ctx.guild.id
        user_id = ctx.author.id
        config = await get_server_config(guild_id)
        eco_config = config['economy']

        # Check for steal cooldown.
        user_data = await get_user_economy_data(guild_id, user_id)
        last_steal_str: Optional[str] = user_data.get('last_steal')
        if last_steal_str:
            last_steal_time = datetime.fromisoformat(last_steal_str).astimezone(timezone.utc)
            cooldown = timedelta(hours=eco_config.get('steal_cooldown_hours', 6))
            if datetime.now(timezone.utc) < last_steal_time + cooldown:
                remaining = (last_steal_time + cooldown) - datetime.now(timezone.utc)
                await send_embed(ctx, f"You need to lay low. You can steal again in **{str(timedelta(seconds=int(remaining.total_seconds())))}**.")
                return

        # Prevent stealing from self.
        if member.id == user_id:
            await send_embed(ctx, "You can't steal from yourself.")
            return
        # Prevent stealing from bots.
        if member.bot:
            await send_embed(ctx, "You can't steal from bots.")
            return

        # Update the 'last_steal' timestamp immediately, regardless of success, to start cooldown.
        await update_user_economy(guild_id, user_id, {'last_steal': datetime.now(timezone.utc).isoformat()})

        # Determine if the steal attempt is successful based on configured chance.
        if random.random() < eco_config['steal_chance']:
            # Steal successful logic.
            target_data = await get_user_economy_data(guild_id, member.id)
            target_balance = target_data.get('balance', 0)
            if target_balance < 1:
                # Cannot steal if target has no money.
                await send_embed(ctx, f"**{member.mention}** has no money to steal!", image_url=member.display_avatar.url)

                if log_channel_id := eco_config.get('log_channel'):
                    await post_money_log(self.bot, guild_id, log_channel_id, "steal_denied", 0, "USER", user_id, member.id)
                return

            # Calculate amount stolen: random between 1 and max percentage of target's balance.
            amount_stolen = random.randint(1, max(1, int(target_balance * eco_config['steal_max_percentage'])))
            # Update balances and log transactions for both stealer and victim.
            await update_user_balance(guild_id, user_id, amount_stolen, "steal_success", "USER", member.id)
            await update_user_balance(guild_id, member.id, -amount_stolen, "stolen_from", "USER", user_id)

            formatted_stolen = await format_currency(guild_id, amount_stolen)
            await send_embed(ctx, f"Success! You stole {formatted_stolen} from **{member.mention}**.", image_url=member.display_avatar.url)
            if log_channel_id := eco_config.get('log_channel'):
                await post_money_log(self.bot, guild_id, log_channel_id, "steal_success", amount_stolen, "USER", user_id, member.id)
                await post_money_log(self.bot, guild_id, log_channel_id, "stolen_from", -amount_stolen, "USER", member.id, user_id)
        else:
            # Steal failed logic: apply penalty to the stealer.
            penalty = eco_config['steal_penalty']
            await update_user_balance(guild_id, user_id, -penalty, "steal_fail", "USER", member.id)
            formatted_penalty = await format_currency(guild_id, penalty)
            await send_embed(ctx, f"You were caught! You paid a penalty of {formatted_penalty}.")
            if log_channel_id := eco_config.get('log_channel'):
                await post_money_log(self.bot, guild_id, log_channel_id, "steal_fail", -penalty, "USER", user_id, member.id)

    @commands.command(name='give', aliases=['donate', 'g'])
    @guild_only()
    @in_allowed_channels()
    async def give(self, ctx: commands.Context, member: Optional[Union[discord.Member, str]] = None, *, amount: Optional[str] = None) -> None:
        """
        Attempt to give money to another member.
        Parameters:
        - `member`: Optional. The target member to give to. If None, a random non-bot member is chosen.
        - `amount`: The amount to give to a person. If None, a random amount between 1 and 20 is given.
        """
        assert ctx.guild is not None

        try:
            member = await get_user_from_arg(member, ctx, True)
        except Exception as e:
            if str(e) == "No non-bot members in the guild.":
                await send_embed(ctx, "There's no one to steal from!")
                return
            else:
                raise  # re-raise unexpected exceptions

        guild_id = ctx.guild.id
        user_id = ctx.author.id

        # Prevent giving to self.
        if member.id == user_id:
            await send_embed(ctx, "You can't give to yourself.")
            return
        # Prevent giving to bots.
        if member.bot:
            await send_embed(ctx, "You can't give from bots.")
            return

        user_data = await get_user_economy_data(guild_id, user_id)
        user_balance = user_data.get('balance', 0)

        # Determine Amount 
        if amount:
            amount_given = await amount_str_to_int(amount, user_balance, ctx)
        else:
            # Random between 1 and max percentage of target's balance.
            amount_given = random.randint(1, min(20, user_balance))
        
        # Validate the final amount
        if amount_given <= 0:
            await send_embed(ctx, "Bet must be a positive amount.")
            return
        if amount_given > user_balance:
            formatted_balance = await format_currency(ctx.guild.id, user_balance)
            await send_embed(ctx, f"You don't have enough to give that much. Your balance is {formatted_balance}.")
            return
        
        await update_user_balance(guild_id, user_id, -amount_given, "give_success", "USER", member.id)
        await update_user_balance(guild_id, member.id, amount_given, "given_to", "USER", user_id)

        formatted_given = await format_currency(guild_id, amount_given)
        await send_embed(ctx, f"Success! You gave {formatted_given} to **{member.mention}**.", image_url=member.display_avatar.url)

        config = await get_server_config(guild_id)
        eco_config = config['economy']
        if log_channel_id := eco_config.get('log_channel'):
            await post_money_log(self.bot, guild_id, log_channel_id, "give_success", -amount_given, "USER", user_id, member.id)
            await post_money_log(self.bot, guild_id, log_channel_id, "given_to", amount_given, "USER", member.id, user_id)
    

    @commands.command(name='link', aliases=['l'])
    @guild_only()
    @in_allowed_channels()
    async def link(self, ctx: commands.Context, username: str) -> None:
        """
        Links a TikTok username to the user's economy profile.
        Parameters:
        - `username`: The TikTok username to link.
        """
        assert ctx.guild is not None
        user_data = await get_user_economy_data(ctx.guild.id, ctx.author.id)
        prefix = (await get_server_config(ctx.guild.id))["prefix"]


        already_linked = user_data.get('tiktok', {}).get('id')
        if already_linked:
            await send_embed(ctx, "You already have a TikTok account linked. Contact the Bot Owner to unlink it.")
            return

        code = "BowBot-" + ''.join(random.choices(ascii_uppercase + digits, k=8))
        username = username.lstrip("@")

        await update_user_economy(ctx.guild.id, ctx.author.id, {
            'tiktok': {
                'username': username,
                'code': code,
                'code_expires': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                'link': f"https://www.tiktok.com/@{username}"
            }
        })

        embed = discord.Embed(
            title="TikTok Account Verification",
            description=(
                f"Great! Your TikTok username has been set to **{username}**.\n\n"
                f"To verify your account and start earning, please **add the following code to your TikTok bio**:\n\n"
                f"```\n{code}\n```\n\n"
                f"Once you've updated your bio, go to the [server]({ctx.message.jump_url}) and run the `{prefix}verify` command."
            ),
            color=await get_embed_color(ctx.guild.id)
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else ctx.bot.user.display_avatar.url)
        embed.set_footer(text="This code expires in 1 hour.")
        dm_message = await ctx.author.send(embed=embed)
        await send_embed(ctx,f"{ctx.author.mention}, I've sent you a [DM]({dm_message.jump_url}) with instructions on how to verify your account.")

    @commands.command(name='verify', aliases=['v'])
    @guild_only()
    @in_allowed_channels()
    async def verify(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None

        user_data = await get_user_economy_data(ctx.guild.id, ctx.author.id)
        tiktok_data = user_data.get('tiktok', {})
        prefix = (await get_server_config(ctx.guild.id))["prefix"]
        if not ((code := tiktok_data.get('code')) and (username := tiktok_data.get('username'))):
            await send_embed(ctx, f"You don't have a TikTok account linked. Use `{prefix}link <username>` to link your account.")
            return
        
        code_expires = tiktok_data.get('code_expires')
        if code_expires is not None and datetime.fromisoformat(code_expires).astimezone(timezone.utc) < datetime.now(timezone.utc):
            await send_embed(ctx, f"Your TikTok verification code has expired. Please link your account again using `{prefix}link <username>`.")
            return

        # Verify the TikTok account
        await send_embed(ctx, f"Verifying your TikTok account...")
        try:
            res = await tiktok.verify_user(username, code)
        except Exception as e:
            await send_embed(ctx, f"Verification failed: {e}")
            return

        if res.get("verified") and (tiktok_id := res.get('tiktok_id')):

            await update_user_economy(
                ctx.guild.id, 
                ctx.author.id, 
                {'tiktok': {'code': None, 'id': tiktok_id, "code_expires": None}}
            )

            # Update the economy data to mark the user as a participant.
            await send_embed(ctx, "Your TikTok account has been successfully verified! You can now earn from TikTok lives.")
            return
        
        await send_embed(ctx, f"Verification failed, please try again.")

    # TODO: Random Messages for Steal + Work
    # Beg Command: send a request a person can respond to (by button) that'll auto give the money 

async def setup(bot: commands.Bot) -> None:
    """
    Sets up the Economy cog by adding it to the bot.
    This function is called by Discord.py when loading extensions.
    """
    await bot.add_cog(EconomyCog(bot))