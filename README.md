# Solana Memecoin Tracker Bot

Fast Telegram bot for tracking new Solana memecoins with real-time data.

## Features

- Real-time token data from Solana Tracker API
- Custom filters (market cap, volume, age, liquidity)
- Latest tokens first (newest memecoins)
- Modern minimal UI with buttons
- Fast and responsive

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Get API keys:
   - Telegram: Create bot with @BotFather
   - Solana Tracker: Get free API key from [Solana Tracker](https://docs.solanatracker.io/public-data-api/docs)

3. Configure:
```bash
# Required:
export TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Optional (10,000 free requests/month, recommended):
export SOLANATRACKER_API_KEY=your_solanatracker_api_key
```

4. Run:
```bash
python telegram_bot.py
```

## Usage

- `/start` - Start the bot
- Use buttons to set filters and search tokens

