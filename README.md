# Solana Memecoin Tracker Bot

Fast Telegram bot for tracking new Solana memecoins with real-time data.

## Features

- Real-time token data from Birdeye API
- Custom filters (market cap, volume, age, liquidity)
- Latest tokens first
- Modern minimal UI with buttons
- Fast and responsive

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Get API keys:
   - Telegram: Create bot with @BotFather
   - Birdeye: Get API key from https://birdeye.so

3. Configure:
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. Run:
```bash
python telegram_bot.py
```

## Usage

- `/start` - Start the bot
- Use buttons to set filters and search tokens

