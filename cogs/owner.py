import discord
from discord.ext import commands
from utils.supabase_client import get_server_with_update_feed
from utils.helpers import *
import asyncio

class OwnerCog(commands.Cog, name="Owner"):
    """
    Commands for interacting with the bot owners.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="postupdate", aliases=['pu'])
    @is_bot_owner_check()
    async def postupdate(self, ctx: commands.Context, version: str) -> None:
        """
        Posts a Bot update message to all subscribed channels.
        The next message you send will be used as the update description.
        Parameters:
        - `version`: The version of the update.
        """
        await ctx.send("Please send the update description in the next message.")

        def check(message: discord.Message) -> bool:
            return message.author == ctx.author and message.channel == ctx.channel

        try:
            update_message = await self.bot.wait_for('message', timeout=300.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("You took too long to provide the update description.")
            return

        channels = await get_server_with_update_feed()
        for channel_dict in channels:
            channel = self.bot.get_channel(int(channel_dict["update_log"])) # type: ignore
            if channel and isinstance(channel, discord.TextChannel):
                guild_id = channel_dict.get("guild_id")
                if guild_id:
                    embed_color = await get_embed_color(guild_id)
                    embed = discord.Embed(title="BowBot Update", color=embed_color)
                    
                    # Use the content of the message sent after the command
                    split_description = update_message.content.split("\n")
                    for line in split_description:
                        parts = line.strip().split(":", 1)  # Split at the first colon
                        if len(parts) < 2:
                            title = "\u200b"
                            description = parts[0].strip()
                        else:
                            title = parts[0].strip()
                            description = parts[1].strip()
                        embed.add_field(name=title, value=description, inline=False)

                    embed.set_footer(text=f"Version: {version}")
                    await channel.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    """
    Sets up the Owner cog by adding it to the bot.
    This function is called by Discord.py when loading extensions.
    """
    await bot.add_cog(OwnerCog(bot))