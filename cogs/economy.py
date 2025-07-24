import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta, timezone
from utils.supabase_client import (
    get_user_economy_data,
    update_user_balance,
    update_user_economy,
    get_server_config,
    supabase # Direct Supabase client instance, for raw queries.
)
from typing import Optional, List, Union
from utils.helpers import send_embed, format_currency, get_embed_color

class Economy(commands.Cog):
    """
    Commands for interacting with the server's economy system.
    This cog handles user balances, a leaderboard, and minigames like work and steal.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name='balance', aliases=['bal'])
    async def balance(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None) -> None:
        """
        Checks your or another user's balance.
        Parameters: 
        - `member`: Optional. The member whose balance to check. Defaults to the command invoker.
        """
        if not ctx.guild:
            return

        # If no member is specified, default to the command author.
        member = member or ctx.author
        
        # Fetch economy data for the specified user. `get_user_economy_data` usually creates data if none
        user_data = await get_user_economy_data(ctx.guild.id, member.id)
        balance_val = user_data.get('balance', 0)
        
        formatted_bal = await format_currency(ctx.guild.id, balance_val)
        await send_embed(ctx, f"**{member.display_name}**'s balance is {formatted_bal}.")

    @commands.command(name='leaderboard', aliases=['lb'])
    async def leaderboard(self, ctx: commands.Context) -> None:
        """
        Shows the server's economy leaderboard, displaying the top 10 richest users.
        """
        # If you dont have an entry in the log, dont show up in the leaderboard
        if not ctx.guild:
            return

        # Query Supabase for top 10 users by balance in the current guild.
        # `.order('balance', desc=True)` sorts by balance in descending order.
        # `.limit(10)` restricts the results to the top 10.
        response = supabase.table('economy').select("user_id, balance").eq('guild_id', ctx.guild.id).order('balance', desc=True).limit(10).execute()
        if not response.data:
            # If no data is returned (no one has money yet), inform the user.
            await send_embed(ctx, "No one has any money yet!")
            return

        # Get the embed color from the server's configuration.
        color = await get_embed_color(ctx.guild.id)
        embed = discord.Embed(title="Leaderboard", color=color)

        # Iterate through the fetched data to populate the leaderboard embed.
        for i, entry in enumerate(response.data):
            try:
                # Attempt to get the user object from bot's cache or fetch it from Discord.
                user = self.bot.get_user(entry['user_id']) or await self.bot.fetch_user(entry['user_id'])
                formatted_bal = await format_currency(ctx.guild.id, entry['balance'])
                embed.add_field(name=f"{i+1}. {user.name}", value=f"{formatted_bal}", inline=False)
            except discord.NotFound:
                # If a user is not found (e.g., left the server), display as "Unknown User".
                formatted_bal = await format_currency(ctx.guild.id, entry['balance'])
                embed.add_field(name=f"{i+1}. Unknown User", value=f"{formatted_bal}", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name='work')
    async def work(self, ctx: commands.Context) -> None:
        """
        Allows a user to 'work' to earn a random amount of money.
        Includes a cooldown mechanism.
        """
        if not ctx.guild:
            return
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

    @commands.command(name='steal')
    async def steal(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        """
        Attempt to steal money from another member. If no member is specified, a random user is chosen.
        Includes cooldowns, chance, penalties, and maximum steal percentages.
        Parameters:
        - `member`: Optional. The target member to steal from. If None, a random non-bot member is chosen.
        """
        if not ctx.guild:
            return

        # If no target member is specified, select a random non-bot member from the guild.
        if member is None:
            # Filter out bots and the command author themselves.
            members: List[discord.Member] = [m for m in ctx.guild.members if not m.bot and m.id != ctx.author.id]
            if not members:
                await send_embed(ctx, "There's no one to steal from!")
                return
            member = random.choice(members) # Pick a random member.

        guild_id = ctx.guild.id
        user_id = ctx.author.id
        config = await get_server_config(guild_id)
        eco_config = config['economy']

        # Check for steal cooldown.
        user_data = await get_user_economy_data(guild_id, user_id)
        last_steal_str: Optional[str] = user_data.get('last_steal')
        if last_steal_str:
            last_steal_time = datetime.fromisoformat(last_steal_str).astimezone(timezone.utc)
            cooldown = timedelta(hours=eco_config['steal_cooldown_hours'])
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
                await send_embed(ctx, f"**{member.display_name}** has no money to steal!")
                return

            # Calculate amount stolen: random between 1 and max percentage of target's balance.
            amount_stolen = random.randint(1, max(1, int(target_balance * eco_config['steal_max_percentage'])))
            # Update balances and log transactions for both stealer and victim.
            await update_user_balance(guild_id, user_id, amount_stolen, "steal_success", "USER", member.id)
            await update_user_balance(guild_id, member.id, -amount_stolen, "stolen_from", "USER", user_id)

            formatted_stolen = await format_currency(guild_id, amount_stolen)
            await send_embed(ctx, f"Success! You stole {formatted_stolen} from **{member.display_name}**.")
        else:
            # Steal failed logic: apply penalty to the stealer.
            penalty = eco_config['steal_penalty']
            await update_user_balance(guild_id, user_id, -penalty, "steal_fail", "USER", member.id)
            formatted_penalty = await format_currency(guild_id, penalty)
            await send_embed(ctx, f"You were caught! You paid a penalty of {formatted_penalty}.")


async def setup(bot: commands.Bot) -> None:
    """
    Sets up the Economy cog by adding it to the bot.
    This function is called by Discord.py when loading extensions.
    """
    await bot.add_cog(Economy(bot))