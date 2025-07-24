import discord
from discord.ext import commands
import random
import asyncio
from typing import Optional, List, Dict, Any, Union
from utils.supabase_client import get_server_config, get_user_economy_data, update_user_balance
from utils.helpers import send_embed, format_currency, get_embed_color

class BlackjackGame:
    """
    Represents a single game of blackjack between a player and the dealer.
    This class encapsulates game state and core blackjack logic.
    """
    def __init__(self, player_id: int, bet: int) -> None:
        self.player_id = player_id
        self.bet = bet
        self.deck = self.create_deck()
        self.player_hand: List[Dict[str, str]] = []
        self.dealer_hand: List[Dict[str, str]] = []

    def create_deck(self) -> List[Dict[str, str]]:
        """
        Creates a standard 52-card deck with ranks and suits, then shuffles it.
        Each card is represented as a dictionary, e.g., `{'rank': 'A', 'suit': '♠️'}`.
        """
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        suits = ['♠️', '♥️', '♦️', '♣️']
        # Generate all combinations of ranks and suits to form the deck.
        deck = [{'rank': rank, 'suit': suit} for rank in ranks for suit in suits]
        random.shuffle(deck) # Shuffle the deck for randomness.
        return deck

    def get_card_value(self, card: Dict[str, str]) -> int:
        """
        Gets the numerical value of a single card.
        Face cards (J, Q, K) are 10. Aces are initially 11 but can be 1.
        """
        if card['rank'] in ['J', 'Q', 'K']:
            return 10
        if card['rank'] == 'A':
            return 11 # Aces are initially valued at 11.
        return int(card['rank'])

    def get_hand_value(self, hand: List[Dict[str, str]]) -> int:
        """
        Calculates the total value of a blackjack hand, accounting for Aces.
        Aces adjust their value from 11 to 1 if the hand's total exceeds 21.
        """
        value = sum(self.get_card_value(card) for card in hand)
        num_aces = sum(1 for card in hand if card['rank'] == 'A')
        # Adjust Ace value from 11 to 1 if the hand is busted (over 21).
        while value > 21 and num_aces:
            value -= 10 # Subtract 10 to change Ace's value from 11 to 1.
            num_aces -= 1
        return value

    def deal_card(self) -> Dict[str, str]:
        """
        Deals a single random card from the deck and removes it.
        Ensures cards are not reused.
        """
        return self.deck.pop(random.randint(0, len(self.deck) - 1))

    def start_game(self) -> None:
        """
        Initializes the blackjack game by dealing two cards to the player and two to the dealer.
        """
        self.player_hand.extend([self.deal_card(), self.deal_card()])
        self.dealer_hand.extend([self.deal_card(), self.deal_card()])

class BlackjackView(discord.ui.View):
    """
    A Discord UI View for the Blackjack game, containing "Hit" and "Stand" buttons.
    Manages user interactions and ensures only the game's author can interact.
    """
    def __init__(self, author: Union[discord.User, discord.Member]) -> None:
        super().__init__(timeout=60.0)
        self.author = author
        self.action: Optional[str] = None
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Ensures that only the player who started the game can interact with the buttons.
        """
        if interaction.user.id != self.author.id:
            # Send an ephemeral message (only visible to the interactor) if it's not their game.
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, custom_id="hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """
        Callback for the "Hit" button. Records the action and stops the view.
        `defer()` acknowledges the interaction immediately to prevent "interaction failed" messages.
        """
        self.action = "hit"
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red, custom_id="stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """
        Callback for the "Stand" button. Records the action and stops the view.
        `defer()` acknowledges the interaction immediately to prevent "interaction failed" messages.
        """
        self.action = "stand"
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        """
        Called when the view times out (no interaction within the timeout period).
        """
        if self.message:
            # Edit the original message to remove the view (buttons).
            await self.message.edit(view=None) #type: ignore

class Blackjack(commands.Cog):
    """
    Commands for playing blackjack in Discord.
    Integrates with the server's economy system.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name='blackjack', aliases=['bj'])
    async def blackjack(self, ctx: commands.Context, bet: int) -> None:
        """
        Starts a game of blackjack.
        Parameters:
        - `bet`: The amount of money the player wants to bet.
        """
        if not ctx.guild:
            return # Ensure command is used in a guild (server).

        user_id = ctx.author.id
        # Check if the user has administrator permissions.
        is_admin = ctx.author.guild_permissions.administrator # type: ignore
        server_config = await get_server_config(ctx.guild.id)
        # Retrieve allowed channels for bot commands from server configuration.
        allowed_channels = server_config.get('allowed_channels', [])

        # Check channel permissions if not an admin and allowed channels are configured.
        if not is_admin and allowed_channels and ctx.channel.id not in allowed_channels:
            await send_embed(ctx, "You can't play in this channel!")
            return

        # Fetch player's economy data.
        user_data = await get_user_economy_data(ctx.guild.id, user_id)
        balance = user_data.get('balance', 0)

        # Validate the bet amount.
        if bet <= 0:
            await send_embed(ctx, "Bet must be a positive amount.")
            return
        if bet > balance:
            # Inform the user if they don't have enough money.
            formatted_balance = await format_currency(ctx.guild.id, balance)
            await send_embed(ctx, f"You don't have enough to bet that much. Your balance is {formatted_balance}.")
            return

        # Initialize a new blackjack game.
        game = BlackjackGame(user_id, bet)
        game.start_game()

        game_message: Optional[discord.Message] = None # Stores the main game message.

        async def update_game_embed(game_over: bool = False, view: Optional[discord.ui.View] = None) -> Optional[discord.Message]:
            """
            Helper function to update the game embed display.
            Shows player and dealer hands, and hides dealer's second card if game is not over.
            """
            nonlocal game_message # Allow modification of `game_message` from outer scope.
            if ctx.guild:
                color = await get_embed_color(ctx.guild.id) # Get embed color from server config.
                embed = discord.Embed(title="Blackjack", color=color)

                # Format player's hand for display.
                player_hand_str = " ".join([f"{c['rank']}{c['suit']}" for c in game.player_hand])
                player_value = game.get_hand_value(game.player_hand)
                embed.add_field(name=f"**{ctx.author.display_name}**'s Hand ({player_value})", value=player_hand_str, inline=False)

                # Format dealer's hand. Hide the second card if the game is not over.
                dealer_hand_str = " ".join([f"{c['rank']}{c['suit']}" for c in game.dealer_hand]) if game_over else f"{game.dealer_hand[0]['rank']}{game.dealer_hand[0]['suit']} ❓"
                dealer_value = game.get_hand_value(game.dealer_hand)
                embed.add_field(name=f"Dealer's Hand ({dealer_value if game_over else '?'})", value=dealer_hand_str, inline=False)

                # Add footer instructions if the game is ongoing.
                if not game_over:
                    embed.set_footer(text="Click a button or type 'h' for hit, 's' for stand.")

                # Edit the existing message or send a new one.
                if game_message:
                    await game_message.edit(embed=embed, view=view)
                    return game_message
                else:
                    game_message = await ctx.send(embed=embed, view=view) # type: ignore
                    return game_message # type: ignore

        # Check for immediate blackjack (player gets 21 on first two cards).
        if game.get_hand_value(game.player_hand) == 21:
            winnings = int(bet * 1.5) # Blackjack usually pays 1.5x the bet.
            await update_user_balance(ctx.guild.id, user_id, winnings, "blackjack_win", "BOT")
            await update_game_embed(game_over=True, view=None) # Show final hands.
            formatted_winnings = await format_currency(ctx.guild.id, winnings)
            await send_embed(ctx, f"Blackjack! You win {formatted_winnings}!")
            return

        # Main game loop.
        while True:
            view = BlackjackView(ctx.author)
            # Attach the game message to the view for timeout handling.
            view.message = await update_game_embed(view=view)

            if not view.message:
                raise commands.CommandError(
                    "Failed to update the game embed. The original message may have been deleted, or I might have lost permissions to edit it."
                )
            # Create tasks to wait for either a button interaction or a chat message ('h' or 's').
            message_waiter = asyncio.create_task(
                self.bot.wait_for(
                    'message',
                    # Check if message is from the correct author, in the correct channel, and is 'h' or 's'.
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['h', 's']
                )
            )
            view_waiter = asyncio.create_task(view.wait()) # Wait for a button press.

            # Wait for either the message or the button press to complete.
            done, pending = await asyncio.wait(
                [message_waiter, view_waiter],
                return_when=asyncio.FIRST_COMPLETED # Return as soon as one task finishes.
            )

            # Cancel any pending tasks to clean up resources.
            for future in pending:
                future.cancel()

            action: Optional[str] = None
            result: Union[discord.Message, Any] = done.pop().result() # Get the result of the completed task.

            if isinstance(result, discord.Message): # If a message was sent, determine action based on its content.
                action = 'hit' if result.content.lower() == 'h' else 'stand'
                try:
                    await result.delete() # Attempt to delete the command message for cleanliness.
                except (discord.Forbidden, discord.NotFound):
                    pass
            else: # If a button was pressed, get the action from the view.
                action = view.action
            
            # Remove buttons from the message after an action or timeout.
            if game_message:
                await game_message.edit(view=None)

            if action == "hit":
                game.player_hand.append(game.deal_card()) # Deal a new card to the player.
                if game.get_hand_value(game.player_hand) > 21: # Player busts (goes over 21).
                    await update_user_balance(ctx.guild.id, user_id, -bet, "blackjack_loss", "BOT") # Deduct bet.
                    await update_game_embed(game_over=True, view=None) # Show final hands.
                    formatted_bet = await format_currency(ctx.guild.id, bet)
                    await send_embed(ctx, f"Bust! You lose {formatted_bet}.")
                    return
                continue

            elif action == "stand":
                # Player stands, now dealer plays.
                while game.get_hand_value(game.dealer_hand) < 17:
                    game.dealer_hand.append(game.deal_card()) # Dealer hits until 17 or more.

                await update_game_embed(game_over=True, view=None) # Show final hands.
                player_value = game.get_hand_value(game.player_hand)
                dealer_value = game.get_hand_value(game.dealer_hand)
                formatted_bet = await format_currency(ctx.guild.id, bet)

                # Determine the winner.
                if dealer_value > 21 or player_value > dealer_value:
                    # Player wins if dealer busts or player has higher score.
                    await update_user_balance(ctx.guild.id, user_id, bet, "blackjack_win", "BOT") # Player wins bet.
                    await send_embed(ctx, f"You win {formatted_bet}!")
                elif player_value < dealer_value:
                    # Player loses if dealer has higher score.
                    await update_user_balance(ctx.guild.id, user_id, -bet, "blackjack_loss", "BOT") # Player loses bet.
                    await send_embed(ctx, f"You lose {formatted_bet}.")
                else:
                    # It's a push (tie).
                    await send_embed(ctx, "It's a push! Your bet is returned.")
                return

            elif action == "timeout":
                # Handle timeout: Player didn't respond in time.
                await send_embed(ctx, "You took too long to respond!")
                return

async def setup(bot: commands.Bot) -> None:
    """
    Sets up the Blackjack cog by adding it to the bot.
    This function is called by Discord.py when loading extensions.
    """
    await bot.add_cog(Blackjack(bot))