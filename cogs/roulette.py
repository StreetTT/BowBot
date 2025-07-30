import discord
from discord.ext import commands
import random
import asyncio
from typing import Optional, Dict, Any, Union
from utils.supabase_client import get_user_economy_data, update_user_balance
from utils.helpers import *

# --- Roulette Game Constants ---

ROULETTE_NUMBERS = {
    0: "green", 1: "red", 2: "black", 3: "red", 4: "black", 5: "red",
    6: "black", 7: "red", 8: "black", 9: "red", 10: "black", 11: "black",
    12: "red", 13: "black", 14: "red", 15: "black", 16: "red", 17: "black",
    18: "red", 19: "red", 20: "black", 21: "red", 22: "black", 23: "red",
    24: "black", 25: "red", 26: "black", 27: "red", 28: "black", 29: "black",
    30: "red", 31: "black", 32: "red", 33: "black", 34: "red", 35: "black", 36: "red"
}

PAYOUTS = {
    "single": 35,
    "color": 1,
    "parity": 1,
    "dozen": 2,
    "row": 2
}

def format_number_with_emojis(number: int) -> str:
    """Formats a number with digit emojis for a more visual display."""
    num_str = str(number)
    emoji_map = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return "".join(emoji_map.get(digit, digit) for digit in num_str)

def create_roulette_board() -> str:
    """Creates a string representation of the roulette board with emojis."""
    red_square = '🟥'
    black_square = '⬛'
    green_square = '🟩'
    
    board = "```\n"
    board += "┌──────────────────────────────────────────────────────────────────┐\n"
    board += f"│                               {green_square} 0 {green_square}                           │\n"
    board += "├─────┬────────────────────────────────────────────────────────────┤\n"
    
    # Numbers grid with colors
    for row in range(3, 0, -1):
        board += f"│®️{format_number_with_emojis(row)}│"
        for col in range(1, 13):
            num = (col - 1) * 3 + row
            color = ROULETTE_NUMBERS[num]
            square = red_square if color == 'red' else black_square
            board += f" {num}{square}"
        board += "│\n"
    
    board += "├─────┼──────────────────┬────────────────────┬────────────────────┤\n"
    board += "│     │       #️⃣1️⃣      │        #️⃣2️⃣        │         #️⃣3️⃣      │\n"
    board += "└─────┴──────────────────┴────────────────────┴────────────────────┘\n"
    board += "```"
    return board


class RouletteGame:
    """Represents a single game of roulette."""
    def __init__(self, player_id: int, bet: int, bet_type: str, bet_choice: Any):
        self.player_id = player_id
        self.bet = bet
        self.bet_type = bet_type
        self.bet_choice = bet_choice

    def spin(self) -> Dict[str, Union[int, str]]:
        """Spins the roulette wheel and returns the winning number and color."""
        winning_number = random.randint(0, 36)
        return {"number": winning_number, "color": ROULETTE_NUMBERS[winning_number]}

    def get_winnings(self, result: Dict[str, Union[int, str]]) -> int:
        """Calculates the winnings based on the bet and the result."""
        winning_number = int(result["number"])
        winning_color = result["color"]

        if self.bet_type == "single":
            if winning_number == self.bet_choice:
                return self.bet * PAYOUTS["single"]
        elif self.bet_type == "color":
            if winning_color == self.bet_choice:
                return self.bet * PAYOUTS["color"]
        elif self.bet_type == "parity":
            if winning_number != 0:
                is_even = winning_number % 2 == 0
                if (self.bet_choice == "even" and is_even) or \
                   (self.bet_choice == "odd" and not is_even):
                    return self.bet * PAYOUTS["parity"]
        elif self.bet_type == "dozen":
            if winning_number != 0 and (self.bet_choice - 1) * 12 < winning_number <= self.bet_choice * 12:
                return self.bet * PAYOUTS["dozen"]
        elif self.bet_type == "rpw":
            # Row 1 numbers are 1 mod 3
            # Row 2 numbers are 2 mod 3
            # Row 3 numbers are 0 mod 3
            if winning_number != 0 and winning_number % 3 == self.bet_choice % 3:
                return self.bet * PAYOUTS["column"]
        
        return -self.bet


class RouletteView(discord.ui.View):
    """A Discord UI View for placing bets in Roulette."""
    def __init__(self, author: Union[discord.User, discord.Member], bot: commands.Bot, active_games: Dict[int, Optional[discord.Message]]):
        super().__init__(timeout=60.0)
        self.author = author
        self.bot = bot
        self.bet_type: Optional[str] = None
        self.bet_choice: Any = None
        self.message: Optional[discord.Message] = None
        self.player_id = author.id
        self.active_games = active_games


    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    async def _handle_choice_view(self, interaction: discord.Interaction, bet_type: str, choices: Dict[str, Any]):
        self.bet_type = bet_type
        view = discord.ui.View()

        for label, choice_val in choices.items():
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)
            async def callback(interaction: discord.Interaction, choice=choice_val):
                self.bet_choice = choice
                self.stop()
                await interaction.response.defer()
            button.callback = lambda i, c=choice_val: callback(i, c) #type: ignore
            view.add_item(button)
        
        await interaction.response.edit_message(view=view)

    @discord.ui.button(label="Red/Black", style=discord.ButtonStyle.primary, row=0)
    async def color_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice_view(interaction, "color", {"Red 🟥": "red", "Black ⬛": "black"})

    @discord.ui.button(label="Even/Odd", style=discord.ButtonStyle.primary, row=0)
    async def parity_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice_view(interaction, "parity", {"Even ✌️": "even", "Odd ☝️": "odd"})

    @discord.ui.button(label="Dozen", style=discord.ButtonStyle.primary, row=1)
    async def dozen_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice_view(interaction, "dozen", {"1-12 #️⃣1️⃣": 1, "13-24 #️⃣2️⃣": 2, "25-36 #️⃣3️⃣": 3})

    @discord.ui.button(label="Row", style=discord.ButtonStyle.primary, row=1)
    async def column_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice_view(interaction, "row", {"®️1️⃣": 1, "®️2️⃣": 2, "®️3️⃣": 3})

    @discord.ui.button(label="Number", style=discord.ButtonStyle.danger, row=2)
    async def number_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bet_type = "single"
        # asking the user to type the number, for simplicity, 
        await interaction.response.send_message("Please type the number you want to bet on (0-36).", ephemeral=True)
        
        def check(m):
            return m.author == self.author and m.channel == interaction.channel and m.content.isdigit() and 0 <= int(m.content) <= 36

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30.0)
            self.bet_choice = int(msg.content)
            await msg.delete()
            self.stop()
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to choose a number.", ephemeral=True)
            self.bet_type = None
            self.stop()

    async def on_timeout(self) -> None:
        if self.player_id in self.active_games:
            if self.message:
                # Edit the original message to remove the view (buttons).
                await self.message.edit(view=None)
            # Remove the player from the active games set if the game times out
            if self.player_id in self.active_games:
                self.active_games.pop(self.player_id)
        if self.message:
            await self.message.edit(view=None)

class RouletteCog(commands.Cog, name="Roulette"):
    """Commands for playing roulette."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_games: Dict[int, Optional[discord.Message]] = {}

    @commands.command(name='roulette', aliases=['r'])
    @guild_only()
    @in_allowed_channels()
    async def roulette(self, ctx: commands.Context, *, bet_str: str):
        """Starts a game of roulette."""
        assert ctx.guild is not None
        user_id = ctx.author.id

        if user_id in self.active_games:
            await send_embed(ctx, "You are already in a roulette game! Please finish it before starting another.")
            return

        try:
            user_data = await get_user_economy_data(ctx.guild.id, user_id)
            balance = user_data.get('balance', 0)

            try:
                bet = await amount_str_to_int(bet_str, balance, ctx)
            except commands.BadArgument:
                return

            if bet <= 0:
                await send_embed(ctx, "Bet must be a positive amount.")
                return
            if bet > balance:
                formatted_balance = await format_currency(ctx.guild.id, balance)
                await send_embed(ctx, f"You don't have enough to bet that much. Your balance is {formatted_balance}.")
                return

            view = RouletteView(ctx.author, self.bot, active_games=self.active_games)
            board_display = create_roulette_board()
            game_message = await ctx.send(f"Place your bet:\n{board_display}", view=view)
            view.message = game_message
            self.active_games[user_id] = game_message


            await view.wait()

            if view.bet_type is None:
                if user_id in self.active_games:
                    self.active_games.pop(user_id)
                return

            game = RouletteGame(user_id, bet, view.bet_type, view.bet_choice)
            result = game.spin()
            winnings = game.get_winnings(result)
            
            await update_user_balance(ctx.guild.id, user_id, winnings, "roulette_game", "BOT")

            # --- Emoji Bet Display ---
            bet_display = ""
            if view.bet_type == "single":
                bet_display = f"Single Number: {format_number_with_emojis(view.bet_choice)}"
            elif view.bet_type == "color":
                color_emoji = "🟥" if view.bet_choice == "red" else "⬛"
                bet_display = f"Color: {color_emoji}"
            elif view.bet_type == "parity":
                parity_emoji = "✌️" if view.bet_choice == "even" else "☝️"
                bet_display = f"Parity: {parity_emoji}"
            elif view.bet_type == "dozen":
                dozen_emoji = f"#️⃣ + {format_number_with_emojis(view.bet_choice)}"
                bet_display = f"Dozen {dozen_emoji}"
            elif view.bet_type == "row":
                row_emoji = f"®️ + {format_number_with_emojis(view.bet_choice)}"
                bet_display = f"Row {row_emoji}"


            color = await get_embed_color(ctx.guild.id)
            embed = discord.Embed(title="Roulette Results", color=color)
            winning_color_emoji = "🟥" if result['color'] == "red" else "⬛" if result['color'] == "black" else "🟩"
            
            winning_row = (int(result['number']) % 3)
            if winning_row == 0:
                winning_row = 3
            winning_row_emoji = f"®️{format_number_with_emojis(winning_row)}"
            winning_dozen_emoji = f"#️⃣{format_number_with_emojis(int(result['number'])// 12 + 1)}"
            winning_number_display = format_number_with_emojis(int(result['number']))
            
            embed.add_field(name="Winning Number", value=f"{winning_color_emoji} {winning_number_display} ({winning_row_emoji}, {winning_dozen_emoji})")
            embed.add_field(name="Your Bet", value=bet_display, inline=False)
            
            if winnings > 0:
                formatted_winnings = await format_currency(ctx.guild.id, winnings)
                embed.description = f"Congratulations! You won {formatted_winnings}!"
                action = "won"
            else:
                formatted_loss = await format_currency(ctx.guild.id, abs(winnings))
                embed.description = f"Sorry, you lost {formatted_loss}."
                action = "loss"

            await game_message.edit(embed=embed, view=None)

            if log_channel_id := (await get_server_config(ctx.guild.id))['economy'].get('log_channel'):
                await post_money_log(self.bot, ctx.guild.id, log_channel_id, f"roulette_{action}", winnings, "BOT", user_id)

        finally:
            if user_id in self.active_games:
                self.active_games.pop(user_id)


async def setup(bot: commands.Bot) -> None:
    """Sets up the Roulette cog by adding it to the bot."""
    await bot.add_cog(RouletteCog(bot))