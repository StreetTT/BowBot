import discord
from discord.ext import commands
from utils.helpers import *
from typing import Optional, cast, List, Dict

class HelpCog(commands.Cog, name="Help"):
    """Provides a custom help command for the bot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def get_command_signature(self, command: commands.Command, prefix: str) -> str:
        """
        Recursively gets the full signature of a command, including its parent commands/groups.
        This helps users understand how to invoke nested commands.
        Parameters:
        - `prefix`: The bot's command prefix.
        Returns:
        - A string representing the full command signature, e.g., `!config general prefix <new_prefix>`.
        """
        parent = command.parent
        if parent is None:
            return f"`{prefix}{command.name} {command.signature}`"

        parent_names: List[str] = []
        current_parent: Optional[commands.Group] = parent #type: ignore
        # Traverse up the command hierarchy to get all parent names.
        while current_parent is not None:
            parent_as_cmd = cast(commands.Command, current_parent)
            parent_names.insert(0, parent_as_cmd.name) # Insert at the beginning to maintain order.
            current_parent = current_parent.parent #type: ignore


        full_name = " ".join(parent_names)
        return f"`{prefix}{full_name} {command.name} {command.signature}`"

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context, *, name: Optional[str] = None) -> None:
        """
        Shows help for a specific command, a cog, or lists all available commands.
        Parameters:
        - `name`: Optional. The name of the command or cog to get help for.
                                 If None, lists all commands.
        """
        if ctx.guild:
            # Get the bot's prefix for the current guild.
            prefix_list = await self.bot.get_prefix(ctx.message)
            prefix = prefix_list[2] if isinstance(prefix_list, list) and len(prefix_list) > 2 else (
                prefix_list[0] if isinstance(prefix_list, list) else prefix_list)
            prefix = cast(str, prefix)
            color = await get_embed_color(ctx.guild.id)
        else:
            prefix = self.bot.user.mention # type: ignore
            color = await get_embed_color()

        # --- GENERAL HELP ---
        if name is None:
            embed = discord.Embed(
                title="Bot Commands",
                description=f"Use `{prefix}help [command|category]` for more info.",
                color=color
            )

            # Group commands by their top-level cog or categorize them as "Uncategorized".
            categorized_commands: Dict[str, List[commands.Command]] = {}
            for command in self.bot.walk_commands():
                if command.hidden or command.cog_name == "Events":
                    continue
                if command.parent is not None:
                    continue  # only show top-level in main view

                cog_name = command.cog_name or "Uncategorized"
                categorized_commands.setdefault(cog_name, []).append(command)

            for cog_name in sorted(categorized_commands.keys()):
                if cog_name == "Owner" and not is_bot_owner(ctx):
                    continue
                commands_list = sorted(categorized_commands[cog_name], key=lambda c: c.name)
                commands_display = [f"`{cmd.name}`" for cmd in commands_list]
                if commands_display:
                    embed.add_field(name=cog_name, value=" ".join(commands_display), inline=False)

            await ctx.send(embed=embed)
            return

        # --- COG HELP ---
        if cog := self.bot.get_cog(name.capitalize()):
            if not (name.lower() == "events" or 
                    (name.lower() == "owner" and not is_bot_owner(ctx))):
                embed = discord.Embed(
                    title=f"{cog.qualified_name} Commands",
                    description=cog.description or "No description available.",
                    color=color
                )
                for cmd in cog.get_commands():
                    if not cmd.hidden:
                        embed.add_field(
                            name=f"`{prefix}{cmd.qualified_name} {cmd.signature}`",
                            value=cmd.short_doc or "No description.",
                            inline=False
                        )
                await ctx.send(embed=embed)
                return

        # --- COMMAND or SUBCOMMAND HELP ---
        command = self.bot.get_command(name.lower())
        if command:
            embed = discord.Embed(
                title=f"Help for `{command.qualified_name}`",
                description=command.help or "No description available.",
                color=color
            )

            embed.add_field(name="Usage", value=self.get_command_signature(command, prefix), inline=False)

            if command.aliases:
                aliases = ", ".join(f"`{a}`" for a in command.aliases)
                embed.add_field(name="Aliases", value=aliases, inline=False)

            if isinstance(command, commands.Group):
                subcommands = [f"`{sub.name}`" for sub in command.commands if not sub.hidden]
                if subcommands:
                    embed.add_field(name="Subcommands", value=" ".join(subcommands), inline=False)

            await ctx.send(embed=embed)
            return

        # --- NOT FOUND ---
        await send_embed(ctx, f"Sorry, I couldn't find a command or category named `{name}`.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
