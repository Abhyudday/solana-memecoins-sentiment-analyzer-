# Solana Memecoins Sentiment Analyzer Bot

A comprehensive Telegram bot for tracking and analyzing Solana memecoins with AI-powered sentiment analysis.

## Features

🔍 **Smart Memecoin Filtering**
- Filter by market cap, volume, liquidity, and estimated holders
- Preset filters (High MC, High Volume, Small Cap, etc.)
- Custom filter creation with natural language

📊 **AI-Powered Sentiment Analysis**
- Real-time Twitter sentiment analysis using Grok AI
- Bullish/Bearish/Neutral sentiment detection
- Sample tweets display

💧 **Live Data Integration**
- Real-time data from DexScreener API
- Support for Raydium, Orca, and Serum DEXs
- Cached results for performance

🚀 **User-Friendly Interface**
- Clean button-based navigation
- No complex commands needed
- Markdown-formatted results

## Tech Stack

- **Python 3.10+**
- **python-telegram-bot** (v20+) - Async Telegram bot framework
- **SQLAlchemy + PostgreSQL** - Database and caching
- **DexScreener API** - Solana token data
- **Twitter API v2** (via tweepy) - Social media data
- **xAI Grok API** - AI sentiment analysis
- **Railway** - Cloud hosting platform

## Prerequisites

Before deploying, you'll need:

1. **Telegram Bot Token**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Create a new bot with `/newbot`
   - Save the bot token

2. **Twitter API Bearer Token**
   - Go to [Twitter Developer Portal](https://developer.twitter.com/)
   - Create a new app or use existing one
   - Generate a Bearer Token with read permissions
   - Save the bearer token

3. **xAI API Key**
   - Visit [x.ai/api](https://x.ai/api)
   - Sign up and get your API key
   - Save the API key

4. **Railway Account**
   - Sign up at [Railway.app](https://railway.app/)
   - Install Railway CLI (optional for local development)

## Local Development Setup

### 1. Clone the Repository

```bash
cd solana-memecoins-sentiment-analyzer
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Copy the `env_template.txt` to `.env`:

```bash
cp env_template.txt .env
```

Edit `.env` and fill in your credentials:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
XAI_API_KEY=your_xai_api_key_here
DATABASE_URL=postgresql://username:password@localhost:5432/memecoin_bot
ENVIRONMENT=development
```

### 4. Set Up Local PostgreSQL (Optional)

If testing locally with a database:

```bash
# Install PostgreSQL
# Create database
createdb memecoin_bot

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://username:password@localhost:5432/memecoin_bot
```

### 5. Run the Bot

```bash
python bot.py
```

The bot should now be running! Open Telegram and message your bot with `/start`.

## Railway Deployment

### Method 1: Deploy from GitHub (Recommended)

1. **Push Code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/solana-memecoin-bot.git
   git push -u origin main
   ```

2. **Create New Project on Railway**
   - Go to [Railway.app](https://railway.app/)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Add PostgreSQL Database**
   - In your Railway project, click "New"
   - Select "Database" → "Add PostgreSQL"
   - Railway will automatically create a `DATABASE_URL` environment variable

4. **Add Environment Variables**
   - Go to your service settings
   - Click "Variables" tab
   - Add the following variables:
     ```
     TELEGRAM_BOT_TOKEN=your_bot_token
     TWITTER_BEARER_TOKEN=your_twitter_token
     XAI_API_KEY=your_xai_key
     ENVIRONMENT=production
     ```
   - Note: `DATABASE_URL` is automatically set by Railway's PostgreSQL

5. **Deploy**
   - Railway will automatically detect the `Procfile` and `runtime.txt`
   - The bot will build and deploy automatically
   - Check logs for any errors

### Method 2: Deploy with Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Add PostgreSQL
railway add --database postgresql

# Set environment variables
railway variables set TELEGRAM_BOT_TOKEN=your_bot_token
railway variables set TWITTER_BEARER_TOKEN=your_twitter_token
railway variables set XAI_API_KEY=your_xai_key
railway variables set ENVIRONMENT=production

# Deploy
railway up
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Token from @BotFather |
| `TWITTER_BEARER_TOKEN` | Yes | Twitter API v2 Bearer Token |
| `XAI_API_KEY` | Yes | xAI Grok API key |
| `DATABASE_URL` | Yes | PostgreSQL connection string (auto-set by Railway) |
| `ENVIRONMENT` | No | `development` or `production` (default: development) |

## Usage

### Start the Bot

Send `/start` to your bot on Telegram to see the main menu.

### Memecoin Filters

1. Click "🔍 Memecoin Filters"
2. Choose a preset filter or create custom:
   - **High MC**: Market cap over $100K
   - **High Vol**: 24h volume over $10K
   - **Active Users**: 100+ estimated holders
   - **Small Cap**: Market cap under $1M
   - **Mid Cap**: Market cap $1M-$10M
   - **High Liquidity**: Liquidity over $50K

#### Custom Filter Examples

- `100k mc, 10k volume, 100+ users`
- `mc > 500k, vol > 25k`
- `1m mc, 50k vol, 200 holders`

**Supported terms:**
- `mc`, `market cap` - Market capitalization
- `vol`, `volume` - 24-hour trading volume
- `holders`, `users` - Estimated holder count
- `liq`, `liquidity` - Available liquidity

**Suffixes:**
- `k` = thousand (1,000)
- `m` = million (1,000,000)
- `b` = billion (1,000,000,000)

### Sentiment Analysis

1. Click "📊 Sentiment Analyzer"
2. Click "🔍 Analyze Token Sentiment"
3. Enter a Solana contract address (44 characters)
4. Wait for analysis (30-60 seconds)

The bot will:
- Search recent Twitter mentions (last 7 days)
- Analyze sentiment with Grok AI
- Show bullish/bearish/neutral assessment
- Display sample tweets

**Note:** Requires at least 5 tweets for reliable analysis.

## Project Structure

```
solana-memecoins-sentiment-analyzer/
├── bot.py                 # Main bot application
├── db.py                  # Database models and operations
├── dex_client.py          # DexScreener API client
├── twitter_client.py      # Twitter API client
├── grok_client.py         # xAI Grok API client
├── filters.py             # Filter parsing utilities
├── keyboards.py           # Telegram keyboard builders
├── requirements.txt       # Python dependencies
├── Procfile              # Railway deployment config
├── runtime.txt           # Python version specification
├── env_template.txt      # Environment variables template
├── README.md             # This file
└── tests/                # Unit tests
    └── test_filters.py   # Filter parsing tests
```

## Testing

Run unit tests:

```bash
pytest tests/
```

Test filter parsing:

```bash
python filters.py
```

Test DexScreener client:

```bash
python dex_client.py
```

## API Rate Limits

### DexScreener API
- Rate limit: ~1 request/second
- No authentication required
- Caching: 5 minutes for memecoin data

### Twitter API v2
- Rate limit: Varies by plan (Basic: 10K tweets/month)
- Bearer token authentication
- Search limited to last 7 days

### xAI Grok API
- Rate limit: Depends on your plan
- API key authentication
- Caching: 1 hour for sentiment results

## Caching Strategy

The bot implements intelligent caching to minimize API calls:

- **Memecoin Data**: Cached for 5 minutes
- **Sentiment Analysis**: Cached for 1 hour
- **Database Cleanup**: Runs every 6 hours
- **Old Cache Removal**: Entries older than 7 days

## Security Considerations

- ✅ All API keys stored in environment variables
- ✅ Input validation for contract addresses
- ✅ No eval/exec usage
- ✅ SQL injection protection via SQLAlchemy ORM
- ✅ Rate limiting for external APIs
- ⚠️ No authentication - bot is public
- ⚠️ Consider adding user whitelist for production

## Troubleshooting

### Bot Not Responding

1. Check Railway logs: `railway logs`
2. Verify all environment variables are set
3. Ensure bot token is correct
4. Check if bot is running: Should see "Starting Solana Memecoins..." in logs

### Database Connection Errors

1. Verify PostgreSQL is running on Railway
2. Check `DATABASE_URL` environment variable
3. Ensure database tables are created (bot creates them automatically on first run)

### API Errors

**DexScreener:**
- Error 429: Rate limited, wait 5 seconds
- No results: Token might not be on Solana/supported DEXs

**Twitter:**
- Error 401: Invalid bearer token
- Error 429: Rate limit exceeded, wait or upgrade plan
- No tweets: Token might be new or unpopular

**Grok:**
- Error 401: Invalid API key
- Error 429: Rate limit exceeded
- Timeout: Normal for long analyses, handled automatically

### Common Issues

**"Invalid Solana contract address"**
- Ensure address is exactly 44 characters
- Must be valid base58 encoding
- Check for typos

**"Insufficient data for sentiment analysis"**
- Token needs at least 5 recent tweets
- Try a more popular token
- Token might be too new

**"No results found"**
- Adjust filter criteria (less restrictive)
- Try preset filters first
- Some tokens might not have enough data

## Performance Optimization

- Uses async/await for concurrent operations
- Database caching reduces API calls by ~80%
- Connection pooling for database
- Rate limiting prevents API bans

## Limitations

- Only supports Solana blockchain tokens
- Twitter search limited to last 7 days
- Sentiment analysis is not financial advice
- Estimated holders is an approximation
- Only searches Raydium, Orca, and Serum DEXs

## Future Enhancements

- [ ] Multi-chain support (Ethereum, BSC, etc.)
- [ ] Price alerts and notifications
- [ ] Portfolio tracking
- [ ] Advanced charting
- [ ] User authentication and preferences
- [ ] Webhook support for real-time updates
- [ ] More DEX integrations
- [ ] Reddit sentiment analysis
- [ ] Historical trend analysis

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - feel free to use this project for personal or commercial purposes.

## Disclaimer

⚠️ **IMPORTANT DISCLAIMER**

This bot provides information and analysis tools only. It is **NOT financial advice**.

- Always do your own research (DYOR)
- Cryptocurrency investments are high risk
- Past performance doesn't guarantee future results
- Sentiment analysis can be inaccurate
- Never invest more than you can afford to lose

The developers are not responsible for any financial losses incurred from using this bot.

## Support

For issues, questions, or feature requests:

1. Check this README first
2. Review Railway logs for errors
3. Open an issue on GitHub
4. Contact the development team

## Acknowledgments

- **DexScreener** - For providing free DEX data API
- **Twitter** - For social media data access
- **xAI** - For Grok AI sentiment analysis
- **Railway** - For easy deployment platform
- **python-telegram-bot** - For excellent Telegram bot framework

---

**Happy memecoin hunting! 🚀**

Remember to always trade responsibly and never invest more than you can afford to lose.
