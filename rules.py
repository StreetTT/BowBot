import discord
import os

# --- CONFIGURATION ---
# Fill in your specific details here.
# To get IDs, enable Developer Mode in Discord Settings > Advanced,
# then right-click on the channel or message and select "Copy ID".

CHANNEL_ID = 1277388445983178826  # The ID of the channel containing the messages
MESSAGE_ID_RULES = 1277693073140351050  # The ID of the first message to edit
MESSAGE_ID_CONSEQUENCES = 1277693075774374019  # The ID of the second message to edit
MESSAGE_ID_CONFIRM = 1277693076634206279  # The ID of the third message to edit

# --- INTENTS SETUP ---
# `intents.messages` is required to fetch and edit messages.
intents = discord.Intents.default()
intents.messages = True

# --- BOT INITIALIZATION ---
# We create a bot instance. A command prefix is not needed as we are not using commands.
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    """
    This event is triggered once the bot successfully connects to Discord.
    The script will perform its edits and then shut down.
    """
    print(f'Logged in as {bot.user.name} ({bot.user.id})') #type: ignore
    print('---------------------------------------------------')
    print('Starting the message editing process...')

    try:
        # --- FETCH THE CHANNEL ---
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print(f"ERROR: Could not find the channel with ID {CHANNEL_ID}. "
                  "Please check the ID and make sure the bot is in that server.")
            await bot.close()
            return

        # --- PROCESS FIRST MESSAGE ---
        try:
            print(f"Attempting to edit message {MESSAGE_ID_RULES}...")
            msg1 = await channel.fetch_message(MESSAGE_ID_RULES) #type: ignore
            embed1 = discord.Embed(
                color=0x9cff96,
                title="**Welcome to BOWVILLE!**",
                description="To ensure our town remains a safe and enjoyable, please abide by the local laws.",
            ).add_field(
                    name="Respect Others",
                    value="Disagreement may happen, but all discussions must remain civil. Harassment, personal attacks, and hate speech (racism, sexism, homophobia, etc.) are grounds for immediate exile from BOWVILLE.",
                    inline=False,
                ).add_field(
                    name="SFW Content Only",
                    value="This is a community for everyone. Keep all shared content (that includes text, images, emotes, usernames, and avatars) appropriate for a general audience.",
                    inline=False,
                ).add_field(
                    name="No Spam",
                    value="Flooding chat with repetitive messages, mass-mentioning other citizens, or spamming memes drowns everyone else out. Please be considerate.",
                    inline=False,
                ).add_field(
                    name="No Unsolicited Promotion",
                    value="We love to see what our citizens create, but this isn't the place for unsolicited ads. Please get a 'permit' (permission) from the <@&1277385321851654216> before promoting other servers, socials, or projects.",
                    inline=False,
                ).add_field(
                    name="Keep the Town Tidy",
                    value="Help us keep things organized. Keep conversations on-topic for their designated channels (e.g., <#1391326305806450771> for bots commands, <#1277532982307196929> for photos, <#1389886944913395803> for general TV discussion).",
                    inline=False,
                ).add_field(
                    name="No Doxxing or Malicious Content",
                    value="A citizen's privacy is their most important property. Sharing anyone's private information (doxxing) or posting malicious links is a zero-tolerance offense and grounds for immediate and permanent exile.",
                    inline=False,
                ).add_field(
                    name="Protect your fellow citizens",
                    value="All spoilers for new media must be contained within spoiler tags. Use \|| on either side of your message to black it out.\n\|| Like so \|| = || Like so ||",
                    inline=False,
                ).add_field(
                    name="Respect the Town Council",
                    value="Our moderators (<@&1277385321851654216>) are here to keep BOWVILLE safe and fun. Please follow their instructions. If you have an issue with a moderation decision, discuss it privately with them via DM.",
                    inline=False,
                )
            await msg1.edit(content=None, embed=embed1)
            print(f"✅ Successfully edited message {MESSAGE_ID_RULES}.")
        except discord.NotFound:
            print(f"❌ ERROR: Could not find a message with ID `{MESSAGE_ID_RULES}` in the specified channel.")
        except discord.Forbidden:
            print(f"❌ ERROR: The bot does not have permission to edit message `{MESSAGE_ID_RULES}`.")
        except Exception as e:
            print(f"An unexpected error occurred while editing message 1: {e}")


        # --- PROCESS SECOND MESSAGE ---
        try:
            print(f"Attempting to edit message {MESSAGE_ID_CONSEQUENCES}...")
            msg2 = await channel.fetch_message(MESSAGE_ID_CONSEQUENCES) #type: ignore
            embed2 =  discord.Embed(
                color=0x9cff96,
                description="Breaking these rules can result in one (or more) of the following: mute, kick, ban, warn\nThese rules can and will change over time so make sure to check them regularly",
            )
            await msg2.edit(content=None, embed=embed2)
            print(f"✅ Successfully edited message {MESSAGE_ID_CONSEQUENCES}.")
        except discord.NotFound:
            print(f"❌ ERROR: Could not find a message with ID `{MESSAGE_ID_CONSEQUENCES}` in the specified channel.")
        except discord.Forbidden:
            print(f"❌ ERROR: The bot does not have permission to edit message `{MESSAGE_ID_CONSEQUENCES}`.")
        except Exception as e:
            print(f"An unexpected error occurred while editing message 2: {e}")
        

        # --- PROCESS THIRD MESSAGE ---
        try:
            print(f"Attempting to edit message {MESSAGE_ID_CONFIRM}...")
            msg2 = await channel.fetch_message(MESSAGE_ID_CONFIRM) #type: ignore
            embed3 =  discord.Embed(
                color=0x9cff96,
                title="React with ✅ to enter BOWVILLE",
                description="By reacting, you agree to abide by the Laws of the Town and all further iterations of them.",
            )
            await msg2.edit(content=None, embed=embed3)
            print(f"✅ Successfully edited message {MESSAGE_ID_CONFIRM}.")
        except discord.NotFound:
            print(f"❌ ERROR: Could not find a message with ID `{MESSAGE_ID_CONFIRM}` in the specified channel.")
        except discord.Forbidden:
            print(f"❌ ERROR: The bot does not have permission to edit message `{MESSAGE_ID_CONFIRM}`.")
        except Exception as e:
            print(f"An unexpected error occurred while editing message 3: {e}")


    except Exception as e:
        print(f"A critical error occurred: {e}")
    finally:
        # --- SHUTDOWN ---
        print('---------------------------------------------------')
        print("Task complete. The bot will now shut down.")
        await bot.close()


# --- RUN THE BOT ---
# It is highly recommended to use an environment variable for your bot token for security.
# IMPORTANT: Replace "YOUR_BOT_TOKEN" with your actual bot token.
try:
    token = "YOUR_BOT_TOKEN"
    token = os.getenv("DISCORD_BOT_TOKEN") or token
    if token == "YOUR_BOT_TOKEN":
         print("ERROR: Please replace 'YOUR_BOT_TOKEN' with your actual bot token before running.")
    else:
        # We use bot.start() for Client, which is equivalent to bot.run() for Bot.
        bot.run(token)
except (ValueError, discord.errors.LoginFailure) as e:
    print(f"Error running bot: {e}")

