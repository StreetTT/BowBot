import discord
from discord.ext import commands
import random
import asyncio
from typing import Optional, List, Dict, Any, Union, Set
from utils.supabase_client import get_user_economy_data, update_user_balance
from utils.helpers import *

#FIXME: You shouldn't be able to play blackjack and roulette at the same time

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
    def __init__(self, author: Union[discord.User, discord.Member], active_games: Dict[int,Optional[discord.Message]]) -> None:
        super().__init__(timeout=60.0)
        self.author = author
        self.action: Optional[str] = None
        self.message: Optional[discord.Message] = None
        self.active_games = active_games # Store the matrix
        self.player_id = author.id

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
        Removes the player from the active games set.
        """
        if self.player_id in self.active_games:
            if self.message:
                # Edit the original message to remove the view (buttons).
                await self.message.edit(view=None)
            # Remove the player from the active games set if the game times out
            if self.player_id in self.active_games:
                self.active_games.pop(self.player_id)


class BlackjackCog(commands.Cog, name="Blackjack"):
    """
    Commands for playing blackjack in Discord.
    Integrates with the server's economy system.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_games: Dict[int, Optional[discord.Message]] = {} # Track active games by user ID

    @commands.command(name='blackjack', aliases=['bj', '21'])
    @guild_only()
    @in_allowed_channels()
    async def blackjack(self, ctx: commands.Context, *, bet_str: str) -> None:
        """
        Starts a game of blackjack.
        Parameters:
        - `bet`: The amount of money the player wants to bet (can be "all" or a percentage like "50%").
        """
        assert ctx.guild is not None
        user_id = ctx.author.id

        # --- Prevent Concurrent Games ---
        if user_id in self.active_games and self.active_games[user_id] is not None:
            await send_embed(ctx, f"You are already in a blackjack game! Please finish your [current game]({self.active_games[user_id].jump_url}) before starting another.") # type: ignore
            return

        self.active_games.update({user_id:None}) # Add player to active games immediately

        try:
            # Fetch player's economy data.
            user_data = await get_user_economy_data(ctx.guild.id, user_id)
            balance = user_data.get('balance', 0)

            # Determine Bet Amount 
            try:
                bet = await amount_str_to_int(bet_str, balance, ctx)
            except commands.BadArgument:
                return # Exit if bad arg given

            # Validate the final bet amount
            if bet <= 0:
                await send_embed(ctx, "Bet must be a positive amount.")
                return
            if bet > balance:
                formatted_balance = await format_currency(ctx.guild.id, balance)
                await send_embed(ctx, f"You don't have enough to bet that much. Your balance is {formatted_balance}.")
                return

            # Initialize a new blackjack game.
            game = BlackjackGame(user_id, bet)
            game.start_game()

            game_message: Optional[discord.Message] = None

            async def update_game_embed(game_over: bool = False, view: Optional[discord.ui.View] = None) -> Optional[discord.Message]:
                """
                Helper function to update the game embed display.
                Shows player and dealer hands, and hides dealer's second card if game is not over.
                """
                assert ctx.guild is not None
                nonlocal game_message # Allow modification of `game_message` from outer scope.
                color = await get_embed_color(ctx.guild.id)
                embed = discord.Embed(title=f"Blackjack - Betting {await format_currency(ctx.guild.id, bet)}", color=color)

                # Format player's hand for display.
                player_hand_str = " ".join([f"{c['rank']}{c['suit']}" for c in game.player_hand])
                player_value = game.get_hand_value(game.player_hand)
                embed.add_field(name=f"**{ctx.author.display_name}**'s Hand ({player_value})", value=player_hand_str, inline=False)

                # Format dealer's hand. Hide the second card if the game is not over.
                dealer_hand_str = " ".join([f"{c['rank']}{c['suit']}" for c in game.dealer_hand]) if game_over else f"{game.dealer_hand[0]['rank']}{game.dealer_hand[0]['suit']} ❓"
                dealer_value = game.get_hand_value(game.dealer_hand)
                embed.add_field(name=f"Dealer's Hand ({dealer_value if game_over else '?'})", value=dealer_hand_str, inline=False)

                # Edit the existing message or send a new one.
                embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
                if game_message:
                    await game_message.edit(embed=embed, view=view)
                    return game_message
                else:
                    game_message = await ctx.send(embed=embed, view=view)  # type: ignore
                    return game_message

            # Check for immediate blackjack (player gets 21 on first two cards).
            if game.get_hand_value(game.player_hand) == 21:
                winnings = int(bet * 1.5) # Blackjack usually pays 1.5x the bet.
                await update_user_balance(ctx.guild.id, user_id, winnings, "blackjack_win", "BOT")
                await update_game_embed(game_over=True, view=None) # Show final hands.
                formatted_winnings = await format_currency(ctx.guild.id, winnings)
                await send_embed(ctx, f"Blackjack! You win {formatted_winnings}!")
                if log_channel_id := (await get_server_config(ctx.guild.id)).get('log_channel'):
                    await post_money_log(self.bot, ctx.guild.id, log_channel_id, "blackjack_win", winnings, "BOT", user_id)
                return # Game ends

            # Main game loop.
            while True:
                # Pass the active_games set to the view for timeout cleanup
                view = BlackjackView(ctx.author, self.active_games)
                # Attach the game message to the view for timeout handling and redirection
                view.message = await update_game_embed(view=view)
                self.active_games[ctx.author.id] = view.message

                if not view.message:
                    raise commands.CommandError(
                        "Failed to update the game embed. The original message may have been deleted, or I might have lost permissions to edit it."
                    )
                # Create tasks to wait for either a button interaction or a chat message ('h' or 's').
                message_waiter = asyncio.create_task(
                    self.bot.wait_for(
                        'message',
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['h', 's']
                    )
                )
                view_waiter = asyncio.create_task(view.wait())

                # Wait for either the message or the button press to complete.
                done, pending = await asyncio.wait(
                    [message_waiter, view_waiter],
                    return_when=asyncio.FIRST_COMPLETED # Return as soon as one task finishes.
                )

                # Cancel any pending tasks to clean up resources.
                for future in pending:
                    future.cancel()

                # Get the result of the completed task
                action: Optional[str] = None
                result: Union[discord.Message, Any] = done.pop().result()

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
                        if log_channel_id := (await get_server_config(ctx.guild.id)).get('log_channel'):
                            await post_money_log(self.bot, ctx.guild.id, log_channel_id, "blackjack_loss", -bet, "BOT", user_id)
                        return # Game Ends
                    continue # Continue Game Loop

                elif action == "stand":
                    # Player stands, now dealer plays.
                    while game.get_hand_value(game.dealer_hand) < 17:
                        game.dealer_hand.append(game.deal_card()) # Dealer hits until 17 or more.

                    await update_game_embed(game_over=True, view=None) # Show final hands.
                    player_value = game.get_hand_value(game.player_hand)
                    dealer_value = game.get_hand_value(game.dealer_hand)

                    # Determine the winner.
                    if dealer_value > 21 or player_value > dealer_value:
                        # Player wins if dealer busts or player has higher score.
                        winnings = int(bet * 1.5) # Blackjack usually pays 1.5x the bet.
                        await update_user_balance(ctx.guild.id, user_id, winnings, "blackjack_win", "BOT") # Player wins bet.
                        await send_embed(ctx, f"You win {await format_currency(ctx.guild.id, winnings)}!")
                        if log_channel_id := (await get_server_config(ctx.guild.id)).get('log_channel'):
                            await post_money_log(self.bot, ctx.guild.id, log_channel_id, "blackjack_win", winnings, "BOT", user_id)
                    elif player_value < dealer_value:
                        # Player loses if dealer has higher score.
                        await update_user_balance(ctx.guild.id, user_id, -bet, "blackjack_loss", "BOT") # Player loses bet.
                        await send_embed(ctx, f"You lose {await format_currency(ctx.guild.id, -bet)}.")
                        if log_channel_id := (await get_server_config(ctx.guild.id)).get('log_channel'):
                            await post_money_log(self.bot, ctx.guild.id, log_channel_id, "blackjack_loss", -bet, "BOT", user_id)
                    else:
                        # It's a push (tie).
                        await send_embed(ctx, "It's a push! Your bet is returned.")
                        await update_user_balance(ctx.guild.id, user_id, 0, "blackjack_push", "BOT") # No change to balance.
                    return # Game Ends

                elif action == "timeout":
                    # on_timeout handles removal from active_games_set already
                    await send_embed(ctx, "You took too long to respond!")
                    return # Game ends

        finally:
            # Ensure player is removed from active games regardless of how the command exits
            if user_id in self.active_games:
                self.active_games.pop(user_id)

async def setup(bot: commands.Bot) -> None:
    """
    Sets up the Blackjack cog by adding it to the bot.
    This function is called by Discord.py when loading extensions.
    """
    await bot.add_cog(BlackjackCog(bot))