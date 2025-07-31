import discord
from discord.ext import commands
import random
from typing import Optional, List, Dict, Union
from utils.helpers import *

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
                