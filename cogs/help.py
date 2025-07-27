import discord
from discord.ext import commands
from utils.helpers import *
from typing import Optional, cast, List, Union, Dict

class HelpCog(commands.Cog, name="Help"):
    """
    Provides the custom help command for the bot.
    This cog replaces Discord.py's default help command to offer more tailored assistance.
    """
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
            # If no parent, it's a top-level command.
            return f"`{prefix}{command.name} {command.signature}`"

        parent_names: List[str] = []
        current_parent: Optional[commands.Group] = parent #type: ignore
        # Traverse up the command hierarchy to get all parent names.
        while current_parent is not None:
            # Use `cast` to help type checkers
            parent_as_cmd = cast(commands.Command, current_parent)
            parent_names.insert(0, parent_as_cmd.name) # Insert at the beginning to maintain order.
            current_parent = current_parent.parent #type: ignore

        full_name = " ".join(parent_names) # Join parent names.
        return f"`{prefix}{full_name} {command.name} {command.signature}`"

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context, *, command_or_cog_name: Optional[str] = None) -> None:
        """
        Shows help for a specific command, a cog, or lists all available commands.
        Parameters:
        - `command_or_cog_name`: Optional. The name of the command or cog to get help for.
                                 If None, lists all commands.
        """
        if ctx.guild:
            # Get the bot's prefix for the current guild.
            prefix_list: Union[List[str], str] = await self.bot.get_prefix(ctx.message)
            # Handle cases where prefix_list might be shorter than expected or not a list
            prefix = prefix_list[2] if isinstance(prefix_list, list) and len(prefix_list) > 2 else (prefix_list[0] if isinstance(prefix_list, list) and len(prefix_list) > 0 else prefix_list)
            prefix = cast(str, prefix)
            color = await get_embed_color(ctx.guild.id)
        else:
            prefix = self.bot.user.mention # type: ignore
            color = await get_embed_color()

        if command_or_cog_name is None:
            # --- Displaying General Help (All Commands) ---
            embed = discord.Embed(
                title="Bot Commands",
                description=f"Use `{prefix}help [command]` for more info on a category or command.",
                color=color
            )

            # Group commands by their top-level cog or categorize them as "Uncategorized".
            categorized_commands: Dict[str, List[commands.Command]] = {}
            for command in self.bot.walk_commands():
                if command.hidden:
                    continue
                # Exclude specific cogs (like "Events") from general help or place them under "Uncategorized".
                cog_name = command.cog_name if command.cog_name and command.cog_name not in ["Events"] else "Uncategorized"
                
                # Only show top-level commands or groups in the general help list.
                if command.parent is None:
                    if cog_name not in categorized_commands:
                        categorized_commands[cog_name] = []
                    categorized_commands[cog_name].append(command)

            # Sort cogs and commands alphabetically for a cleaner display.
            for cog_name in sorted(categorized_commands.keys()):
                commands_in_cog = sorted(categorized_commands[cog_name], key=lambda c: c.name)
                commands_display = []
                for command in commands_in_cog:
                    if isinstance(command, commands.Group):
                        # For command groups, list subcommands.
                        subcommands = [f"`{c.name}`" for c in command.commands if not c.hidden]
                        if subcommands:
                            commands_display.append(f"**{command.name}** ({' '.join(subcommands)})")
                        else:
                            # Handle groups with no visible subcommands.
                            commands_display.append(f"**{command.name}**")
                    else:
                        commands_display.append(f"`{command.name}`")
                
                if commands_display:
                    # Add a field for each cog/category with its commands.
                    embed.add_field(name=cog_name, value=" ".join(commands_display), inline=False)
            
            await ctx.send(embed=embed)
            return

        # --- Displaying Help for a Specific Cog or Command ---
        # Try to find a cog first (case-insensitive for user input by capitalizing).
        if cog := self.bot.get_cog(command_or_cog_name.capitalize()):
            embed = discord.Embed(
                title=f"Cog: {cog.qualified_name}",
                description=cog.description or "No description available.",
                color=color
            )
            for command in cog.get_commands():
                if not command.hidden:
                    # List each command within the cog with its help text.
                    embed.add_field(name=command.name, value=command.help or "No description.", inline=False)
            await ctx.send(embed=embed)
        # If not a cog, try to find a command (case-insensitive).
        elif command := self.bot.get_command(command_or_cog_name.lower()):
            embed = discord.Embed(
                title=f"Command: {command.qualified_name}",
                description=command.help or "No description available.",
                color=color
            )
            # Display command aliases.
            aliases = ", ".join([f"`{a}`" for a in command.aliases])
            if aliases:
                embed.add_field(name="Aliases", value=aliases, inline=False)

            # Display the full command usage signature.
            usage = self.get_command_signature(command, prefix)
            embed.add_field(name="Usage", value=usage, inline=False)
            
            # If it's a command group, list its subcommands.
            if isinstance(command, commands.Group):
                subcommands_list = [f"`{sub.name}`" for sub in command.commands if not sub.hidden]
                if subcommands_list:
                    embed.add_field(name="Subcommands", value=" ".join(subcommands_list), inline=False)

            await ctx.send(embed=embed)
            return
        else:
            # If neither a cog nor a command is found.
            await send_embed(ctx, f"Sorry, I couldn't find a command or cog named `{command_or_cog_name}`.")

async def setup(bot: commands.Bot) -> None:
    """
    Sets up the HelpCog by adding it to the bot.
    This function is called by Discord.py when loading extensions.
    """
    await bot.add_cog(HelpCog(bot))