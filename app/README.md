# Telegram bot

```bash
cd app
```

## Installation

```bash
pip install --force-reinstall -r requirements.txt
```

## Configuration

```bash
cp .env.example .env
```

Manyally edit `.env` file.

Manually edit database to add default users and config.

## add_default_users

<!-- TODO: fix the code -->
```SQL
INSERT INTO users (username, role) VALUES ('kirmark', 'premium');
```

## add_default_config

<!-- TODO: add default config -->

## Usage

```bash
python3 main.py
```

## Usage with debug

```bash
python3 main.py --debug 
```

## Run tests

```bash
python3 main-telegram-bot-app.py
```
