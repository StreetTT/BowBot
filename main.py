import asyncio
import os
from dotenv import load_dotenv
from bot import main

if __name__ == "__main__":
    # Ensure the .env file is loaded and the bot token is available.
    load_dotenv()
    if not os.path.exists('.env'):
        raise FileNotFoundError("The .env file is missing. Please create it with your bot token.")

    # Start the bot.
    # This is the entry point for the entire bot application.
    asyncio.run(main())

    # TODO: Roulette
    # TODO: MI5 ( 007 Roles)
    # TODO: PvP
    # TODO: Family Tree
    # TODO: Bank of Bow : 100K per person (More ways to lose money)
    # TODO: TikFinity Link
    # TODO: Shop: Roles, Chat, multipliers
    # TODO: Chat Revive
    # TODO: Invite Link
    # TODO: Edit About
    # TODO: Recent Transaction Log
    # TODO: Graphs n Shi