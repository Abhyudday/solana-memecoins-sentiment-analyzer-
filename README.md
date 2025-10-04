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

2. Get Telegram bot token:
   - Create bot with @BotFather on Telegram
   - Copy the bot token

3. Configure:
```bash
# Set environment variable:
export TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional: Add Birdeye API for better data (paid)
export BIRDEYE_API_KEY=your_birdeye_key_here
```

4. Run:
```bash
python telegram_bot.py
```

## Usage

- `/start` - Start the bot
- Use buttons to set filters and search tokens

