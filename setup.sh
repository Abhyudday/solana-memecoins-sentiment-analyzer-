#!/bin/bash

echo "🚀 Setting up Solana Memecoin Tracker Bot..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cp env_template.txt .env
    echo "⚠️  Please edit .env with your API keys:"
    echo "   - TELEGRAM_BOT_TOKEN (from @BotFather)"
    echo "   - BIRDEYE_API_KEY (from https://birdeye.so)"
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python telegram_bot.py"

