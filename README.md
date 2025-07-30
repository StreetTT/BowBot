# BowBot

BowBot is a feature-rich Discord bot built with `discord.py`. It offers a variety of interactive features, including a server economy system, games like Blackjack, and extensive configuration options for server administrators. The bot uses a Supabase backend to persist data, ensuring a seamless experience across server restarts.

-----

## Features

  - **Economy System**:
      - Earn money by "working".
      - Steal from other users with a configurable success chance and penalty.
      - Check your balance or the balance of others.
      - A server-wide leaderboard to see who's on top.
      - Give money to other users.
  - **Blackjack Game**:
      - Play a game of Blackjack against the dealer.
      - Bet your in-game currency for a chance to win more.
  - **Configuration**:
      - Server administrators can configure various aspects of the bot, including:
          - **General Settings**: Bot prefix, embed colors, and allowed channels for commands.
          - **Currency Settings**: Currency name, symbol, and starting balance for new users.
          - **Work Settings**: Cooldown and earning range for the `work` command.
          - **Steal Settings**: Cooldown, success chance, penalty, and maximum steal percentage for the `steal` command.
          - **Money Drop Settings**: Enable/disable money drops, the chance of a drop, the amount range, and allowed channels.
          - **Log Channels**: Set up channels for update logs, configuration changes, and economy logs.
  - **Custom Help Command**: A dynamic help command that provides information on all available commands and categories.
  - **Owner Commands**: Special commands for the bot owner, such as posting updates to all subscribed servers.

-----

## Getting Started

### Prerequisites

  - Python 3.8 or higher
  - A Discord Bot Token
  - A Supabase project for the database

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/BowBot.git
    cd BowBot
    ```

2.  **Install the dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up your environment variables:**
    Create a `.env` file in the root of the project and add the following:

    ```
    DISCORD_BOT_TOKEN="your_discord_bot_token"
    SUPABASE_URL="your_supabase_url"
    SUPABASE_KEY="your_supabase_key"
    ```

    These are all required for the bot to function.

4.  **Run the bot:**

    ```bash
    python main.py
    ```

## Configuration

The bot's configuration is managed through a combination of commands and a Supabase backend. You need to set up this backend correctly with the following tables and schemas for the bot to work. It's also highly recommended to enable **Row Level Security (RLS)** on your tables and define policies to control access to the data. 

Once done a server administrators can use the `!config` command to open a menu for editing settings. Additionally, there are commands like `!setchannels` and `!setmoneydropchannels` for more specific configurations.

#### `server_configs`

This table stores the configuration for each server the bot is in.

| Column           | Type     | Notes                                                                                                                              |
| ------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `guild_id`       | `text`   | **Primary Key**. The Discord server's ID.                                                                                          |
| `notes`          | `text`   | Optional notes for the server.                                                                                                     |
| `prefix`         | `text`   | The command prefix for the bot in this server. Default is `-`.                                                                     |
| `embed_color`    | `text`   | The default hex color for embeds. Default is `#0000FF`.                                                                            |
| `allowed_channels` | `jsonb` | An array of channel IDs where the bot is allowed to respond. An empty array means all channels are allowed. `["-1"]` means none. |
| `economy`        | `jsonb`  | A JSON object containing the economy settings for the server.                                                           |
| `moneydrop`      | `jsonb`  | A JSON object containing the money drop settings for the server.                                                        |
| `update_log`     | `text`   | The channel ID for bot update logs.                                                                                                |
| `config_log`     | `text`   | The channel ID for configuration change logs.                                                                                      |
| `streamer`     | `text`   | The discord user ID of the streamer.                                ID for configuration change logs.                                                                                      |

---

#### `economy`

This table stores the economy data for each user in a server.

| Column      | Type     | Notes                                                 |
| ----------- | -------- | ----------------------------------------------------- |
| `guild_id`  | `text`   | **Part of a composite primary key**. The Discord server's ID. |
| `user_id`   | `text`   | **Part of a composite primary key**. The Discord user's ID.   |
| `balance`   | `integer`| The user's current balance.                           |
| `last_work` | `timestamptz` | The timestamp of the last time the user used the `work` command. |
| `last_steal`| `timestamptz` | The timestamp of the last time the user used the `steal` command. |
| `participant`| `boolean` | `true` if the user has participated in the economy.   |
| `tiktok` | `jsonb` |  A JSON object containing the tiktok data for the user. |

---

#### `economy_logs`

This table logs all economy-related transactions.

| Column           | Type        | Notes                                                        |
| ------------------ | ----------- | ------------------------------------------------------------ |
| `id`             | `bigint`    | **Primary Key**. Auto-incrementing.                          |
| `guild_id`       | `text`      | The Discord server's ID where the transaction occurred.      |
| `user_id`        | `text`      | The user ID involved in the transaction.                     |
| `action`         | `text`      | The action that was performed (e.g., "work", "steal_success"). |
| `amount`         | `integer`   | The amount of currency involved in the transaction.          |
| `type`           | `text`      | Who initiated the action: "TIKTOK", "BOT" or "USER".                   |
| `target_user_id` | `text`      | The user ID of the target of the action (e.g., in a steal).  |
| `timestamp`      | `timestamptz` | The timestamp of when the transaction occurred.              |

-----

## Usage

Here are some of the main commands available in the bot:

  - **`!help`**: Shows the help message with a list of all commands and categories.
  - **`!balance`**: Checks your or another user's balance.
  - **`!leaderboard`**: Displays the server's economy leaderboard.
  - **`!work`**: Work to earn money.
  - **`!steal <member>`**: Attempt to steal money from another member.
  - **`!give <member> <amount>`**: Give money to another member.
  - **`!blackjack <bet>`**: Starts a game of blackjack with the specified bet.
  - **`!config`**: Opens the configuration menu for server administrators.

-----

## To-Do

The following features are planned for future development:

  - Roulette game
  - Chat Revive feature
  - Family Tree
  - Shop for multipliers
  - Invite Link
  - Edit About section
  - Recent Transaction Log
  - Graphs and stats