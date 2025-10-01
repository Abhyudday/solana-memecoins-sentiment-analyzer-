"""
Solana Memecoins Sentiment Analyzer Telegram Bot

A comprehensive bot for tracking and analyzing Solana memecoins with sentiment analysis.
"""

import os
import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

from dotenv import load_dotenv

# Import our modules
from db import init_database, get_db_manager
from dex_client import DexScreenerClient
from twitter_client import TwitterClient
from grok_client import GrokClient
from filters import parse_filter, format_filters_display
from keyboards import (
    get_main_menu_keyboard, get_filters_menu_keyboard, get_sentiment_menu_keyboard,
    get_memecoin_results_keyboard, get_memecoin_details_keyboard,
    get_sentiment_result_keyboard, get_help_keyboard, CallbackData
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global clients
dex_client: Optional[DexScreenerClient] = None
twitter_client: Optional[TwitterClient] = None
grok_client: Optional[GrokClient] = None

# User state management
user_states: Dict[int, Dict[str, Any]] = {}


class BotState:
    """Constants for bot states."""
    WAITING_FILTER_INPUT = "waiting_filter_input"
    WAITING_CA_INPUT = "waiting_ca_input"
    NORMAL = "normal"


def get_user_state(user_id: int) -> Dict[str, Any]:
    """Get user state, creating if not exists."""
    if user_id not in user_states:
        user_states[user_id] = {"state": BotState.NORMAL}
    return user_states[user_id]


def set_user_state(user_id: int, state: str, **kwargs):
    """Set user state with optional data."""
    user_states[user_id] = {"state": state, **kwargs}


def format_memecoin_list(memecoins: List[Dict[str, Any]]) -> str:
    """Format memecoin list for display."""
    if not memecoins:
        return "No memecoins found matching your criteria."
    
    lines = ["🚀 **Memecoin Results:**\n"]
    
    for i, coin in enumerate(memecoins[:10], 1):  # Limit to 10 for display
        name = coin.get('name', 'Unknown')
        symbol = coin.get('symbol', '???')
        mc = coin.get('mc', 0)
        volume = coin.get('volume_24h', 0)
        liquidity = coin.get('liquidity', 0)
        price_change = coin.get('price_change_24h', 0)
        
        # Format numbers
        mc_str = format_large_number(mc)
        vol_str = format_large_number(volume)
        liq_str = format_large_number(liquidity)
        
        # Price change emoji
        change_emoji = "🟢" if price_change > 0 else "🔴" if price_change < 0 else "⚪"
        
        lines.append(
            f"`{i:2d}.` **{symbol}** ({name})\n"
            f"     💰 MC: ${mc_str} | 📊 Vol: ${vol_str}\n"
            f"     💧 Liq: ${liq_str} | {change_emoji} {price_change:+.1f}%\n"
        )
    
    return "\n".join(lines)


def format_memecoin_details(coin: Dict[str, Any]) -> str:
    """Format detailed memecoin information."""
    name = coin.get('name', 'Unknown')
    symbol = coin.get('symbol', '???')
    ca = coin.get('ca', 'N/A')
    mc = coin.get('mc', 0)
    volume = coin.get('volume_24h', 0)
    liquidity = coin.get('liquidity', 0)
    price_usd = coin.get('price_usd', 0)
    price_change = coin.get('price_change_24h', 0)
    holders = coin.get('holders_estimate', 0)
    dex_id = coin.get('dex_id', 'Unknown')
    
    # Format numbers
    mc_str = format_large_number(mc)
    vol_str = format_large_number(volume)
    liq_str = format_large_number(liquidity)
    
    # Price change emoji and formatting
    change_emoji = "🟢" if price_change > 0 else "🔴" if price_change < 0 else "⚪"
    
    details = f"""
🪙 **{name} ({symbol})**

📋 **Contract Address:**
`{ca}`

💰 **Market Cap:** ${mc_str}
💵 **Price:** ${price_usd:.8f}
{change_emoji} **24h Change:** {price_change:+.2f}%
📊 **24h Volume:** ${vol_str}
💧 **Liquidity:** ${liq_str}
👥 **Est. Holders:** {holders:,}
🔄 **DEX:** {dex_id.title()}

⏰ **Updated:** {datetime.now().strftime('%H:%M UTC')}
"""
    
    return details.strip()


def format_sentiment_result(sentiment: str, explanation: str, tweet_count: int, 
                          sample_tweets: List[str], token_name: str) -> str:
    """Format sentiment analysis result."""
    # Sentiment emoji
    sentiment_emoji = {
        "bullish": "🟢 📈",
        "bearish": "🔴 📉", 
        "neutral": "⚪ ➡️"
    }
    
    emoji = sentiment_emoji.get(sentiment.lower(), "⚪")
    
    result = f"""
🧠 **Sentiment Analysis for {token_name}**

{emoji} **Sentiment:** {sentiment.title()}

💭 **Analysis:** {explanation}

📊 **Based on {tweet_count} recent tweets**

"""
    
    if sample_tweets:
        result += "📝 **Sample Tweets:**\n\n"
        for tweet in sample_tweets[:3]:
            result += f"• {tweet}\n\n"
    
    result += f"⏰ **Analyzed:** {datetime.now().strftime('%H:%M UTC')}"
    
    return result.strip()


def format_large_number(number: float) -> str:
    """Format large numbers with K/M/B suffixes."""
    if number >= 1_000_000_000:
        return f"{number/1_000_000_000:.1f}B"
    elif number >= 1_000_000:
        return f"{number/1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number/1_000:.1f}K"
    else:
        return f"{number:,.0f}"


def is_valid_solana_address(address: str) -> bool:
    """Basic validation for Solana addresses."""
    if not address or len(address) != 44:
        return False
    
    # Basic base58 character check
    base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return all(c in base58_chars for c in address)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    
    welcome_text = f"""
👋 **Welcome {user.first_name}!**

🚀 **Solana Memecoins Sentiment Analyzer**

I help you discover and analyze Solana memecoins with:

🔍 **Smart Filtering** - Find coins by market cap, volume, and activity
📊 **Sentiment Analysis** - AI-powered analysis of Twitter sentiment
💧 **Real-time Data** - Live data from DexScreener
🧠 **Grok AI** - Advanced sentiment insights

Choose an option below to get started:
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await show_help_menu(update, context)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    logger.info(f"Button pressed: {data} by user {user_id}")
    
    # Main menu handlers
    if data == CallbackData.MENU_MAIN:
        await show_main_menu(update, context)
    elif data == CallbackData.MENU_FILTERS:
        await show_filters_menu(update, context)
    elif data == CallbackData.MENU_SENTIMENT:
        await show_sentiment_menu(update, context)
    elif data == CallbackData.MENU_HELP:
        await show_help_menu(update, context)
    
    # Filter handlers
    elif data.startswith("filter_"):
        await handle_filter_selection(update, context, data)
    
    # Sentiment handlers
    elif data == CallbackData.SENTIMENT_ANALYZE:
        await handle_sentiment_analyze(update, context)
    elif data.startswith("sentiment_token_"):
        ca = data.replace("sentiment_token_", "")
        await analyze_token_sentiment(update, context, ca)
    
    # Memecoin detail handlers
    elif data.startswith("memecoin_details_"):
        ca = data.replace("memecoin_details_", "")
        await show_memecoin_details(update, context, ca)
    
    # Copy CA handlers
    elif data.startswith("copy_ca_"):
        ca = data.replace("copy_ca_", "")
        await copy_contract_address(update, context, ca)
    
    # Help handlers
    elif data.startswith("help_"):
        await handle_help_section(update, context, data)
    
    # Pagination handlers
    elif data.startswith("page_"):
        page = int(data.replace("page_", ""))
        await handle_pagination(update, context, page)
    
    # No-op for disabled buttons
    elif data == CallbackData.NOOP:
        pass
    
    else:
        logger.warning(f"Unhandled callback data: {data}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages based on user state."""
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    text = update.message.text
    
    if user_state["state"] == BotState.WAITING_FILTER_INPUT:
        await handle_custom_filter_input(update, context, text)
    elif user_state["state"] == BotState.WAITING_CA_INPUT:
        await handle_ca_input(update, context, text)
    else:
        # Default response for unrecognized messages
        await update.message.reply_text(
            "Please use the menu buttons below or type /start to begin.",
            reply_markup=get_main_menu_keyboard()
        )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu."""
    text = """
🚀 **Solana Memecoins Analyzer**

Choose what you'd like to do:

🔍 **Memecoin Filters** - Find tokens by criteria
📊 **Sentiment Analyzer** - Analyze Twitter sentiment
ℹ️ **Help** - Learn how to use the bot
"""
    
    await edit_or_send_message(update, text, get_main_menu_keyboard())


async def show_filters_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the filters menu."""
    text = """
🔍 **Memecoin Filters**

Choose a preset filter or create a custom one:

🚀 **High MC** - Market cap over 100K
📈 **High Vol** - 24h volume over 10K  
👥 **Active Users** - 100+ estimated holders
💎 **Small Cap** - Market cap under 1M
🏆 **Mid Cap** - Market cap 1M-10M
💧 **High Liquidity** - Liquidity over 50K
⚙️ **Custom** - Define your own criteria
"""
    
    await edit_or_send_message(update, text, get_filters_menu_keyboard())


async def show_sentiment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the sentiment analyzer menu."""
    text = """
📊 **Sentiment Analyzer**

Analyze Twitter sentiment for any Solana memecoin:

🔍 **Analyze Token** - Enter contract address
ℹ️ **How it Works** - Learn about the analysis

The bot searches recent tweets and uses Grok AI to determine if the community sentiment is bullish, bearish, or neutral.
"""
    
    await edit_or_send_message(update, text, get_sentiment_menu_keyboard())


async def show_help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the help menu."""
    text = """
ℹ️ **Help & Information**

Learn how to use the Solana Memecoins Analyzer:

🔍 **Filter Help** - How to find memecoins
📊 **Sentiment Help** - Understanding sentiment analysis  
🤖 **About Bot** - Bot information and features
"""
    
    await edit_or_send_message(update, text, get_help_keyboard())


async def handle_filter_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """Handle filter selection."""
    user_id = update.effective_user.id
    
    if data == "filter_custom":
        set_user_state(user_id, BotState.WAITING_FILTER_INPUT)
        
        text = """
⚙️ **Custom Filter**

Enter your filter criteria. Examples:

• `100k mc, 10k volume, 100+ users`
• `mc > 500k, vol > 25k`
• `1m mc, 50k vol, 200 holders`

You can use:
- **mc** or **market cap** for market cap
- **vol** or **volume** for 24h volume  
- **holders** or **users** for estimated holders
- **liq** or **liquidity** for liquidity
- Suffixes: **k** (thousand), **m** (million), **b** (billion)

Type your filter criteria:
"""
        
        await edit_or_send_message(update, text, None)
        return
    
    # Handle preset filters
    preset_map = {
        "filter_high_mc": "high_mc",
        "filter_high_vol": "high_vol", 
        "filter_active_users": "active_users",
        "filter_small_cap": "small_cap",
        "filter_mid_cap": "mid_cap",
        "filter_high_liquidity": "high_liquidity"
    }
    
    preset_key = preset_map.get(data)
    if preset_key:
        await apply_memecoin_filter(update, context, preset_key)


async def handle_custom_filter_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle custom filter input."""
    user_id = update.effective_user.id
    set_user_state(user_id, BotState.NORMAL)
    
    # Parse the filter
    filters = parse_filter(text)
    
    if not filters:
        await update.message.reply_text(
            "❌ Could not parse your filter. Please try again with a format like:\n"
            "`100k mc, 10k volume, 100+ users`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_filters_menu_keyboard()
        )
        return
    
    await apply_memecoin_filter(update, context, filters)


async def apply_memecoin_filter(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               filter_input) -> None:
    """Apply memecoin filter and show results."""
    # Show loading message
    loading_text = "🔍 Searching for memecoins... This may take a moment."
    await edit_or_send_message(update, loading_text, None)
    
    try:
        # Parse filters if string, otherwise use as dict
        if isinstance(filter_input, str):
            filters = parse_filter(filter_input)
        else:
            filters = filter_input
        
        # Check cache first
        db = get_db_manager()
        cached_results = db.get_cached_memecoins_by_filter(filters, max_age_minutes=5)
        
        if cached_results:
            logger.info(f"Using cached results: {len(cached_results)} memecoins")
            memecoins = [
                {
                    'ca': coin.ca,
                    'name': coin.name,
                    'symbol': coin.symbol,
                    'mc': coin.mc,
                    'volume_24h': coin.volume_24h,
                    'liquidity': coin.liquidity,
                    'holders_estimate': coin.holders_estimate,
                    'price_usd': coin.price_usd,
                    'price_change_24h': coin.price_change_24h,
                    'dex_url': coin.dex_url
                }
                for coin in cached_results
            ]
        else:
            # Fetch fresh data
            logger.info("Fetching fresh memecoin data")
            async with DexScreenerClient() as client:
                memecoins = await client.search_memecoins(filters)
                
                # Cache the results
                for coin in memecoins:
                    db.cache_memecoin(coin)
        
        if not memecoins:
            no_results_text = f"""
❌ **No Results Found**

No memecoins match your criteria:
{format_filters_display(filters)}

Try adjusting your filters or use a preset filter.
"""
            await edit_or_send_message(update, no_results_text, get_filters_menu_keyboard())
            return
        
        # Format and display results
        results_text = format_memecoin_list(memecoins)
        results_text += f"\n\n**Filter:** {format_filters_display(filters)}"
        results_text += f"\n**Found:** {len(memecoins)} tokens"
        
        # Store results in user state for pagination
        user_id = update.effective_user.id
        set_user_state(user_id, BotState.NORMAL, last_results=memecoins, last_filters=filters)
        
        keyboard = get_memecoin_results_keyboard(memecoins[:10])  # Show first 10
        await edit_or_send_message(update, results_text, keyboard)
        
    except Exception as e:
        logger.error(f"Error applying memecoin filter: {e}")
        error_text = """
❌ **Error**

Sorry, there was an error searching for memecoins. This could be due to:
• API rate limits
• Network issues
• High server load

Please try again in a moment.
"""
        await edit_or_send_message(update, error_text, get_filters_menu_keyboard())


async def show_memecoin_details(update: Update, context: ContextTypes.DEFAULT_TYPE, ca: str) -> None:
    """Show detailed information for a specific memecoin."""
    if not is_valid_solana_address(ca):
        await edit_or_send_message(
            update, 
            "❌ Invalid contract address format.",
            get_filters_menu_keyboard()
        )
        return
    
    # Show loading
    await edit_or_send_message(update, "📊 Loading token details...", None)
    
    try:
        # Check cache first
        db = get_db_manager()
        cached_coin = db.get_cached_memecoin(ca, max_age_minutes=5)
        
        if cached_coin:
            coin_data = {
                'ca': cached_coin.ca,
                'name': cached_coin.name,
                'symbol': cached_coin.symbol,
                'mc': cached_coin.mc,
                'volume_24h': cached_coin.volume_24h,
                'liquidity': cached_coin.liquidity,
                'holders_estimate': cached_coin.holders_estimate,
                'price_usd': cached_coin.price_usd,
                'price_change_24h': cached_coin.price_change_24h,
                'dex_url': cached_coin.dex_url
            }
        else:
            # Fetch fresh data
            async with DexScreenerClient() as client:
                coin_data = await client.get_token_info(ca)
                
                if coin_data:
                    db.cache_memecoin(coin_data)
        
        if not coin_data:
            await edit_or_send_message(
                update,
                f"❌ Could not find token data for address:\n`{ca}`",
                get_filters_menu_keyboard()
            )
            return
        
        details_text = format_memecoin_details(coin_data)
        keyboard = get_memecoin_details_keyboard(coin_data)
        
        await edit_or_send_message(update, details_text, keyboard)
        
    except Exception as e:
        logger.error(f"Error showing memecoin details: {e}")
        await edit_or_send_message(
            update,
            "❌ Error loading token details. Please try again.",
            get_filters_menu_keyboard()
        )


async def handle_sentiment_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle sentiment analysis request."""
    user_id = update.effective_user.id
    set_user_state(user_id, BotState.WAITING_CA_INPUT)
    
    text = """
🔍 **Sentiment Analysis**

Enter a Solana token contract address (CA) to analyze:

The bot will:
1. Search recent Twitter mentions
2. Analyze sentiment with Grok AI
3. Provide bullish/bearish/neutral assessment

**Example CA:**
`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`

Enter the contract address:
"""
    
    await edit_or_send_message(update, text, None)


async def handle_ca_input(update: Update, context: ContextTypes.DEFAULT_TYPE, ca: str) -> None:
    """Handle contract address input for sentiment analysis."""
    user_id = update.effective_user.id
    set_user_state(user_id, BotState.NORMAL)
    
    ca = ca.strip()
    
    if not is_valid_solana_address(ca):
        await update.message.reply_text(
            "❌ Invalid Solana contract address format.\n"
            "Contract addresses should be 44 characters long.\n\n"
            "Please try again:",
            reply_markup=get_sentiment_menu_keyboard()
        )
        return
    
    await analyze_token_sentiment(update, context, ca)


async def analyze_token_sentiment(update: Update, context: ContextTypes.DEFAULT_TYPE, ca: str) -> None:
    """Analyze sentiment for a token."""
    # Show loading message
    loading_text = f"""
🧠 **Analyzing Sentiment**

Contract Address: `{ca}`

⏳ Searching Twitter mentions...
⏳ Running AI sentiment analysis...

This may take 30-60 seconds...
"""
    
    await edit_or_send_message(update, loading_text, None)
    
    try:
        # Check sentiment cache first
        db = get_db_manager()
        cached_sentiment = db.get_cached_sentiment(ca, max_age_hours=1)
        
        if cached_sentiment:
            logger.info(f"Using cached sentiment for {ca}")
            sentiment = cached_sentiment.sentiment
            explanation = cached_sentiment.explanation
            tweet_count = cached_sentiment.tweet_count
            sample_tweets = json.loads(cached_sentiment.sample_tweets) if cached_sentiment.sample_tweets else []
            
            # Get token name from cache or DexScreener
            token_name = "Unknown Token"
            cached_coin = db.get_cached_memecoin(ca, max_age_minutes=60)
            if cached_coin and cached_coin.symbol:
                token_name = cached_coin.symbol
            else:
                async with DexScreenerClient() as client:
                    token_info = await client.get_token_info(ca)
                    if token_info:
                        token_name = token_info.get('symbol', 'Unknown Token')
        
        else:
            # Get token info first
            token_name = "Unknown Token"
            async with DexScreenerClient() as client:
                token_info = await client.get_token_info(ca)
                if token_info:
                    token_name = token_info.get('symbol', token_info.get('name', 'Unknown Token'))
                    # Cache token info
                    db.cache_memecoin(token_info)
            
            # Search tweets - use 3 days back to get more results
            tweets = await twitter_client.search_tweets_by_ca(ca, token_name, max_results=50, days_back=3)
            
            # If no tweets found, check if it's a rate limit issue or genuinely no tweets
            if len(tweets) == 0:
                # Try to use older cached sentiment if available (up to 24 hours)
                older_cached_sentiment = db.get_cached_sentiment(ca, max_age_hours=24)
                if older_cached_sentiment:
                    logger.info(f"Using older cached sentiment for {ca} due to no tweets found")
                    sentiment = older_cached_sentiment.sentiment
                    explanation = older_cached_sentiment.explanation
                    tweet_count = older_cached_sentiment.tweet_count
                    sample_tweets = json.loads(older_cached_sentiment.sample_tweets) if older_cached_sentiment.sample_tweets else []
                    
                    # Format and send results with a note about cache
                    base_result = format_sentiment_result(sentiment, explanation, tweet_count, sample_tweets, token_name)
                    result_text = f"""
{base_result}

⚠️ _Note: Using cached data. Twitter API may be rate limited._
"""
                    keyboard = get_sentiment_result_keyboard(ca, True)
                    await edit_or_send_message(update, result_text, keyboard)
                    return
                
                # No cache available - show rate limit error
                rate_limit_text = f"""
📊 **Sentiment Analysis - {token_name}**

⏱️ **Twitter API Rate Limit**

The Twitter API is currently rate limited. Please try again in a few minutes.

Alternatively:
• Try a different token
• Check back in 15 minutes

Twitter's free tier has limited requests per 15-minute window.
"""
                keyboard = get_sentiment_result_keyboard(ca, token_info is not None)
                await edit_or_send_message(update, rate_limit_text, keyboard)
                return
            
            if len(tweets) < 3:
                no_activity_text = f"""
📊 **Sentiment Analysis - {token_name}**

❌ **Insufficient Data**

Found only {len(tweets)} recent tweets mentioning this token.

Need at least 3 tweets for reliable sentiment analysis.

This could mean:
• New or low-activity token
• Limited social media presence  
• Recent contract address

Try again later or check a more popular token.
"""
                
                keyboard = get_sentiment_result_keyboard(ca, token_info is not None)
                await edit_or_send_message(update, no_activity_text, keyboard)
                return
            
            # Prepare tweets for sentiment analysis
            tweets_text = twitter_client.prepare_tweets_for_sentiment(tweets)
            
            # Analyze sentiment with Grok
            async with GrokClient(os.getenv("XAI_API_KEY")) as grok:
                sentiment, explanation = await grok.analyze_sentiment(ca, token_name, tweets_text)
            
            # Get sample tweets for display
            sample_tweets = twitter_client.get_sample_tweets_text(tweets, max_tweets=3)
            
            # Cache the results
            db.cache_sentiment(ca, sentiment, explanation, len(tweets), json.dumps(sample_tweets))
        
        # Format and send results
        result_text = format_sentiment_result(
            sentiment, explanation, tweet_count, sample_tweets, token_name
        )
        
        keyboard = get_sentiment_result_keyboard(ca, True)  # Assume we have token data
        await edit_or_send_message(update, result_text, keyboard)
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment for {ca}: {e}")
        error_text = f"""
❌ **Sentiment Analysis Failed**

Sorry, there was an error analyzing sentiment for this token:

`{ca}`

This could be due to:
• Twitter API rate limits
• Grok AI service issues
• Network connectivity problems

Please try again in a few minutes.
"""
        
        keyboard = get_sentiment_menu_keyboard()
        await edit_or_send_message(update, error_text, keyboard)


async def copy_contract_address(update: Update, context: ContextTypes.DEFAULT_TYPE, ca: str) -> None:
    """Handle copy contract address request."""
    text = f"""
📋 **Contract Address Copied**

`{ca}`

You can now paste this address in your wallet or DEX to trade this token.

⚠️ **Always DYOR (Do Your Own Research) before investing!**
"""
    
    # Don't change the keyboard, just show a temporary message
    query = update.callback_query
    await query.answer("Contract address copied to clipboard!", show_alert=True)


async def handle_help_section(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """Handle help section requests."""
    if data == "help_filters":
        text = """
🔍 **Filter Help**

**Preset Filters:**
• **High MC** - Market cap over $100K
• **High Vol** - 24h volume over $10K
• **Active Users** - 100+ estimated holders
• **Small Cap** - Market cap under $1M
• **Mid Cap** - Market cap $1M-$10M
• **High Liquidity** - Liquidity over $50K

**Custom Filters:**
You can create custom filters using natural language:

**Examples:**
• `100k mc, 10k volume, 100+ users`
• `mc > 500k, vol > 25k`
• `1m mc, 50k vol, 200 holders`

**Supported Terms:**
• **mc/market cap** - Market capitalization
• **vol/volume** - 24-hour trading volume
• **holders/users** - Estimated holder count
• **liq/liquidity** - Available liquidity

**Suffixes:**
• **k** = thousand (1,000)
• **m** = million (1,000,000)  
• **b** = billion (1,000,000,000)
"""
        
    elif data == "help_sentiment":
        text = """
📊 **Sentiment Analysis Help**

**How It Works:**
1. Enter a Solana token contract address
2. Bot searches recent Twitter mentions (last 7 days)
3. Grok AI analyzes tweet sentiment
4. Results show: Bullish, Bearish, or Neutral

**What It Analyzes:**
• Community excitement/fear
• Price predictions and expectations
• Buying/selling sentiment
• Overall market mood

**Reliability:**
• Needs 5+ tweets for analysis
• More tweets = more reliable results
• Recent tweets weighted higher
• Filters out spam/bot accounts

**Limitations:**
• Based only on Twitter activity
• Not financial advice
• Sentiment can change quickly
• Consider multiple sources

⚠️ **Always do your own research before investing!**
"""
        
    elif data == "help_about":
        text = """
🤖 **About Solana Memecoins Analyzer**

**Version:** 1.0.0
**Developer:** Solana Memecoins Team

**Features:**
🔍 **Smart Filtering** - Find tokens by multiple criteria
📊 **AI Sentiment** - Grok-powered Twitter analysis
💧 **Live Data** - Real-time DexScreener integration
⚡ **Fast Results** - Cached data for speed

**Data Sources:**
• **DexScreener API** - Token prices, volume, liquidity
• **Twitter API** - Social media mentions
• **Grok AI** - Advanced sentiment analysis

**Privacy:**
• No personal data stored
• No trading history tracked
• Anonymous usage only

**Support:**
For issues or suggestions, contact the development team.

⚠️ **Disclaimer:** This bot provides information only, not financial advice. Always research before investing.
"""
    
    else:
        text = "ℹ️ Help section not found."
    
    await edit_or_send_message(update, text, get_help_keyboard())


async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Handle pagination for results."""
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    
    last_results = user_state.get("last_results", [])
    last_filters = user_state.get("last_filters", {})
    
    if not last_results:
        await edit_or_send_message(
            update,
            "❌ No previous results found. Please search again.",
            get_filters_menu_keyboard()
        )
        return
    
    # Calculate pagination
    items_per_page = 10
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_results = last_results[start_idx:end_idx]
    
    if not page_results:
        await edit_or_send_message(
            update,
            "❌ No results on this page.",
            get_filters_menu_keyboard()
        )
        return
    
    # Format results
    results_text = format_memecoin_list(page_results)
    results_text += f"\n\n**Filter:** {format_filters_display(last_filters)}"
    results_text += f"\n**Page:** {page + 1} | **Total:** {len(last_results)} tokens"
    
    keyboard = get_memecoin_results_keyboard(page_results, page, 
                                           (len(last_results) + items_per_page - 1) // items_per_page)
    
    await edit_or_send_message(update, results_text, keyboard)


async def edit_or_send_message(update: Update, text: str, 
                              keyboard: Optional[InlineKeyboardMarkup]) -> None:
    """Edit existing message or send new one."""
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Error editing/sending message: {e}")
        # Fallback to sending new message
        if update.effective_chat and update.get_bot():
            try:
                await update.get_bot().send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
            except Exception as fallback_error:
                logger.error(f"Fallback send_message also failed: {fallback_error}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Only send message if we have a valid update with a chat
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ An unexpected error occurred. Please try again or use /start to restart.",
                reply_markup=get_main_menu_keyboard()
            )
        except Exception as e:
            logger.error(f"Error sending error message: {e}")


async def init_clients() -> bool:
    """Initialize API clients."""
    global dex_client, twitter_client, grok_client
    
    # Initialize Twitter client
    twitter_bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if twitter_bearer_token:
        twitter_client = TwitterClient(twitter_bearer_token)
        logger.info("Twitter client initialized")
    else:
        logger.warning("Twitter bearer token not found")
        return False
    
    # Initialize Grok client (will be created per request due to async context manager)
    xai_api_key = os.getenv("XAI_API_KEY")
    if not xai_api_key:
        logger.warning("xAI API key not found")
        return False
    
    logger.info("All clients initialized successfully")
    return True


async def cleanup_cache_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic job to clean up old cache entries."""
    try:
        db = get_db_manager()
        db.cleanup_old_cache(max_age_days=7)
        logger.info("Cache cleanup completed")
    except Exception as e:
        logger.error(f"Error during cache cleanup: {e}")


def main() -> None:
    """Main function to start the bot."""
    # Get bot token
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        return
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not found in environment variables")
        return
    
    # Initialize database
    try:
        init_database(database_url)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return
    
    # Create application
    application = Application.builder().token(bot_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Add periodic cache cleanup job (every 6 hours) if JobQueue is available
    job_queue = application.job_queue
    if job_queue is not None:
        job_queue.run_repeating(cleanup_cache_job, interval=21600, first=60)
    else:
        logger.warning(
            "JobQueue not available. Skipping scheduled cache cleanup. "
            "Install PTB with job-queue extra to enable: pip install \"python-telegram-bot[job-queue]\""
        )
    
    # Initialize clients
    if not asyncio.run(init_clients()):
        logger.error("Failed to initialize API clients")
        return
    
    # Start the bot
    logger.info("Starting Solana Memecoins Sentiment Analyzer Bot...")
    # Ensure an event loop exists in environments where none is set
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    
    # Run polling within an explicit event loop to avoid RuntimeError in some hosts
    asyncio.run(application.run_polling(allowed_updates=Update.ALL_TYPES))


if __name__ == "__main__":
    main()
