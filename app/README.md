# ChatGPT telegram bot-Aiogram 3

This is a Telegram bot that integrates with GPT models. It's designed to provide a friendly and informative assistant named Donna.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Usage](#usage)
- [Running Tests](#running-tests)

## Installation

To set up your environment and install the required dependencies, run the following commands:

```bash
cd app
pip install --force-reinstall -r requirements.txt
```

## Configuration

Start by duplicating the `.env.example` file and renaming it to `.env`:

```bash
cp .env.example .env
```

Then, manually edit the `.env` file with your Telegram bot token, OpenAI API key, and database URL.

## Database Setup

Run the service to create the database tables:

```bash
python3 main.py
```

Than, stop the service using `Ctrl+C`.

Before using the bot, you need to set up the database with default users and configurations.

Go to terminal:

```bash
psql 'your_database_url'
```

And execute following SQL command:

```sql
INSERT INTO users (userid, role, is_allowed, tokens_used) VALUES (REPLACE_WITH_YOUR_TELEGRAM_ID,'user', True, 0);
```

Then, add config to the database:

```sql
INSERT INTO config (gpt_model, temperature, prompt_assistant) VALUES ('gpt-4-1106-preview', 0.7, 'Take a deep breath and think aloud step-by-step. Act as assistant Your name is Donna You are female You should be friendly You should not use official tone Your answers should be simple, and laconic but informative Before providing an answer check information above one more time Try to solve tasks step by step I will send you questions or topics to discuss and you will answer me You interface right now is a telegram messenger Some of messages you will receive from user was transcribed from voice messages. If task is too abstract or you see more than one way to solve it or you need more information to solve it - ask me for more information from user. It is important to understand what user wants to get from you. But don''t ask too much questions - it is annoying for user.');
```

Now, you can close psql session using following command:

```bash
\q
```

## Usage

To start the bot:

```bash
python3 main.py
```

For debugging:

```bash
python3 main.py --debug
```

## Running Tests

Execute the test script to run the tests:

```bash
python3 main-telegram-bot-app.py
```
