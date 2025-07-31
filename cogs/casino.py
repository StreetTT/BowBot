import discord
from discord.ext import commands
from typing import Optional, Dict
from utils.supabase_client import get_user_economy_data, update_user_balance
from utils.helpers import *
from core.roulette import *
from core.blackjack import *

class CasinoCog(commands.Cog, name="Casino"):
    """Commands for gambling."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_games: Dict[int, Optional[discord.Message]] = {}

    @commands.command(name='roulette', aliases=['r'])
    @guild_only()
    @in_allowed_channels()
    async def roulette(self, ctx: commands.Context, *, bet_str: str):
        """Starts a game of roulette.

        In roulette, a wheel with numbers from 0-36 is spun. The goal is to predict where the ball will land. 
        You can bet on single numbers, colors, even/odd, and more, the more specific the bet is, the higher the payout.
        
        For the bet, you can use a specific amount, "all" of your balance, or a percentage (e.g. "50%").
        """
        assert ctx.guild is not None
        user_id = ctx.author.id

        # Prevent Concurrent Games
        if user_id in self.active_games:
            await send_embed(ctx, f"You are already in a game! Please finish your [current game]({self.active_games[user_id].jump_url}) before starting another.") # type: ignore
            return
        self.active_games.update({user_id:None})

        try:
            # Validate Bet
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

            # Setup Game
            view = RouletteView(ctx.author, self.bot, active_games=self.active_games)
            board_display = create_roulette_board()
            game_message = await ctx.send(f"Place your bet:\n{board_display}", view=view)
            view.message = game_message
            self.active_games[user_id] = game_message
            
            # Wait for user input
            await view.wait()
            if view.bet_type is None:
                if user_id in self.active_games:
                    self.active_games.pop(user_id)
                return

            # Spin the Wheel
            game = RouletteGame(user_id, bet, view.bet_type, view.bet_choice)
            result = game.spin()
            winnings = game.get_winnings(result)

            # Display Result
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
            
            # Update Embed
            if winnings > 0:
                formatted_winnings = await format_currency(ctx.guild.id, winnings)
                embed.description = f"Congratulations! You won {formatted_winnings}!"
                action = "won"
            else:
                formatted_loss = await format_currency(ctx.guild.id, abs(winnings))
                embed.description = f"Sorry, you lost {formatted_loss}."
                action = "loss"

            embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
            await game_message.edit(embed=embed, view=None)

            # Update User Balance
            await update_user_balance(ctx.guild.id, user_id, winnings, f"roulette_{action}", "BOT")
            if log_channel_id := (await get_server_config(ctx.guild.id))['economy'].get('log_channel'):
                await post_money_log(self.bot, ctx.guild.id, log_channel_id, f"roulette_{action}", winnings, "BOT", user_id)

        finally:
            if user_id in self.active_games:
                self.active_games.pop(user_id)

    @commands.command(name='blackjack', aliases=['bj', '21'])
    @guild_only()
    @in_allowed_channels()
    async def blackjack(self, ctx: commands.Context, *, bet_str: str) -> None:
        """Starts a game of blackjack against the dealer.

        Your goal is to get a hand value closer to 21 than the dealer without going over.
        Use the buttons to hit (receive a card) or stand (end your turn). Bare in mind Aces can be 1 or 11, whilst face cards are 10.

        For the bet, you can use a specific amount, "all" of your balance, or a percentage (e.g. "50%").
        """
        assert ctx.guild is not None
        user_id = ctx.author.id

        # Prevent Concurrent Games
        if user_id in self.active_games and self.active_games[user_id] is not None:
            await send_embed(ctx, f"You are already in a game! Please finish your [current game]({self.active_games[user_id].jump_url}) before starting another.") # type: ignore
            return
        self.active_games.update({user_id:None})

        try:
            # Validate Bet
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

            # Start Game
            game = BlackjackGame(user_id, bet)
            game.start_game()
            game_message: Optional[discord.Message] = None

            async def update_game_embed(msg: Optional[discord.Message], game_over: bool = False, view: Optional[discord.ui.View] = None) -> Optional[discord.Message]:
                """
                Helper function to update the game embed display.
                Shows player and dealer hands, and hides dealer's second card if game is not over.
                """
                assert ctx.guild is not None
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
                if msg:
                    await msg.edit(embed=embed, view=view)
                    return msg
                else:
                    message = await ctx.send(embed=embed, view=view)  # type: ignore
                    return message

            # Check for immediate blackjack.
            if game.get_hand_value(game.player_hand) == 21:
                winnings = int(bet * 1.5) # Blackjack usually pays 1.5x the bet.
                await update_user_balance(ctx.guild.id, user_id, winnings, "blackjack_win", "BOT")
                game_message = await update_game_embed(game_message,game_over=True, view=None) # Show final hands.
                formatted_winnings = await format_currency(ctx.guild.id, winnings)
                await send_embed(ctx, f"Blackjack! You win {formatted_winnings}!")
                if log_channel_id := (await get_server_config(ctx.guild.id))['economy'].get('log_channel'):
                    await post_money_log(self.bot, ctx.guild.id, log_channel_id, "blackjack_win", winnings, "BOT", user_id)
                return # Game ends

            # Main game loop.
            while True:
                # Setup Game
                view = BlackjackView(ctx.author, self.active_games)
                game_message = await update_game_embed(game_message, view=view)
                view.message = game_message
                self.active_games[ctx.author.id] = view.message
                if not view.message:
                    raise commands.CommandError(
                        "Failed to update the game embed. The original message may have been deleted, or I might have lost permissions to edit it."
                    )
                
                # Wait for user input
                message_waiter = asyncio.create_task(
                    self.bot.wait_for(
                        'message',
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['h', 's']
                    )
                )
                view_waiter = asyncio.create_task(view.wait())
                done, pending = await asyncio.wait(
                    [message_waiter, view_waiter],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for future in pending:
                    future.cancel()
                action: Optional[str] = None
                result: Union[discord.Message, Any] = done.pop().result()
                if isinstance(result, discord.Message):
                    action = 'hit' if result.content.lower() == 'h' else 'stand'
                    try:
                        await result.delete() # Attempt to delete the command message for cleanliness.
                    except (discord.Forbidden, discord.NotFound):
                        pass
                else: # If a button was pressed, get the action from the view.
                    action = view.action
                if game_message:
                    await game_message.edit(view=None) # Remove buttons from the message after an action or timeout.

                # Display the result of the action.
                if action == "hit":
                    game.player_hand.append(game.deal_card()) # Deal a new card to the player.
                    if game.get_hand_value(game.player_hand) > 21: # Player busts (goes over 21).
                        await update_user_balance(ctx.guild.id, user_id, -bet, "blackjack_loss", "BOT") # Deduct bet.
                        game_message = await update_game_embed(game_message,game_over=True, view=None) # Show final hands.
                        formatted_bet = await format_currency(ctx.guild.id, bet)
                        await send_embed(ctx, f"Bust! You lose {formatted_bet}.")
                        if log_channel_id := (await get_server_config(ctx.guild.id))['economy'].get('log_channel'):
                            await post_money_log(self.bot, ctx.guild.id, log_channel_id, "blackjack_loss", -bet, "BOT", user_id)
                        return # Game Ends
                    continue # Continue Game Loop

                elif action == "stand":
                    # Player stands, now dealer plays.
                    while game.get_hand_value(game.dealer_hand) < 17:
                        game.dealer_hand.append(game.deal_card()) # Dealer hits until 17 or more.

                    # Show final hands.
                    await update_game_embed(game_message, game_over=True, view=None)
                    player_value = game.get_hand_value(game.player_hand)
                    dealer_value = game.get_hand_value(game.dealer_hand)

                    # Determine the winner.
                    if dealer_value > 21 or player_value > dealer_value:
                        winnings = int(bet * 1.5) 
                        await update_user_balance(ctx.guild.id, user_id, winnings, "blackjack_win", "BOT") # Player wins bet.
                        await send_embed(ctx, f"You win {await format_currency(ctx.guild.id, winnings)}!")
                        if log_channel_id := (await get_server_config(ctx.guild.id))['economy'].get('log_channel'):
                            await post_money_log(self.bot, ctx.guild.id, log_channel_id, "blackjack_win", winnings, "BOT", user_id)
                    elif player_value < dealer_value:
                        await update_user_balance(ctx.guild.id, user_id, -bet, "blackjack_loss", "BOT") # Player loses bet.
                        await send_embed(ctx, f"You lose {await format_currency(ctx.guild.id, bet)}.")
                        if log_channel_id := (await get_server_config(ctx.guild.id))['economy'].get('log_channel'):
                            await post_money_log(self.bot, ctx.guild.id, log_channel_id, "blackjack_loss", -bet, "BOT", user_id)
                    else:
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
    """Sets up the Casino cog by adding it to the bot."""
    await bot.add_cog(CasinoCog(bot))