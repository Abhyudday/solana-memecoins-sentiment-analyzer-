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
from filters import parse_filter, format_filters_display
from keyboards import (
    get_main_menu_keyboard, get_filters_menu_keyboard,
    get_memecoin_results_keyboard, get_memecoin_details_keyboard,
    get_help_keyboard, get_filter_builder_keyboard, get_filter_param_keyboard,
    CallbackData
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User state management
user_states: Dict[int, Dict[str, Any]] = {}


class BotState:
    """Constants for bot states."""
    NORMAL = "normal"
    BUILDING_FILTER = "building_filter"


def get_user_state(user_id: int) -> Dict[str, Any]:
    """Get user state, creating if not exists."""
    if user_id not in user_states:
        user_states[user_id] = {"state": BotState.NORMAL}
    return user_states[user_id]


def set_user_state(user_id: int, state: str, **kwargs):
    """Set user state with optional data."""
    user_states[user_id] = {"state": state, **kwargs}


def format_memecoin_list(memecoins: List[Dict[str, Any]], page_size: int = 15) -> str:
    """Format memecoin list for display."""
    if not memecoins:
        return "No memecoins found matching your criteria."
    
    lines = ["🚀 **Memecoin Results:**\n"]
    
    for i, coin in enumerate(memecoins[:page_size], 1):
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

🚀 **Solana Memecoins Analyzer**

I help you discover Solana memecoins with:

🔍 **Smart Filtering** - Find coins by market cap, volume, liquidity & holders
🔧 **Interactive Builder** - Custom filters with easy controls
💧 **Real-time Data** - Live data from DexScreener
⚡ **Fast Results** - Comprehensive token discovery

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
    elif data == CallbackData.MENU_HELP:
        await show_help_menu(update, context)
    
    # Filter handlers
    elif data.startswith("filter_"):
        await handle_filter_selection(update, context, data)
    
    # Filter builder handlers
    elif data == "filter_builder":
        await show_filter_builder(update, context)
    elif data.startswith("builder_"):
        await handle_builder_action(update, context, data)
    elif data.startswith("set_"):
        await handle_set_filter_value(update, context, data)
    elif data.startswith("clear_"):
        await handle_clear_filter(update, context, data)
    
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
ℹ️ **Help** - Learn how to use the bot
"""
    
    await edit_or_send_message(update, text, get_main_menu_keyboard())


async def show_filters_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the filters menu."""
    text = """
🔍 **Memecoin Filters**

Choose a preset filter or build a custom one:

🔧 **Build Custom** - Interactive filter builder with controls
🚀 **High MC** - Market cap over 100K
📈 **High Vol** - 24h volume over 10K  
👥 **Active Users** - 100+ estimated holders
💎 **Small Cap** - Market cap under 1M
🏆 **Mid Cap** - Market cap 1M-10M
💧 **High Liquidity** - Liquidity over 50K
"""
    
    await edit_or_send_message(update, text, get_filters_menu_keyboard())


async def show_help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the help menu."""
    text = """
ℹ️ **Help & Information**

Learn how to use the Solana Memecoins Analyzer:

🔍 **Filter Help** - How to find memecoins  
🤖 **About Bot** - Bot information and features
"""
    
    await edit_or_send_message(update, text, get_help_keyboard())


async def handle_filter_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """Handle filter selection."""
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


async def show_filter_builder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the interactive filter builder."""
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    
    # Initialize builder_filters if not exists
    if 'builder_filters' not in user_state:
        user_state['builder_filters'] = {}
    
    current_filters = user_state.get('builder_filters', {})
    
    text = """
🔧 **Custom Filter Builder**

Configure your filter criteria:
Click on each parameter to set values or click "Any" to remove restrictions.

When ready, click **Search** to find memecoins.
"""
    
    keyboard = get_filter_builder_keyboard(current_filters)
    await edit_or_send_message(update, text, keyboard)


async def handle_builder_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """Handle filter builder actions."""
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    
    if 'builder_filters' not in user_state:
        user_state['builder_filters'] = {}
    
    current_filters = user_state['builder_filters']
    
    if data == "builder_search":
        # Execute search with current filters
        if not current_filters:
            query = update.callback_query
            await query.answer("⚠️ Please set at least one filter!", show_alert=True)
            return
        await apply_memecoin_filter(update, context, current_filters)
    
    elif data == "builder_reset":
        # Reset all filters
        user_state['builder_filters'] = {}
        await show_filter_builder(update, context)
    
    elif data == "builder_mc":
        # Show MC setting keyboard
        mc_min = current_filters.get('mc_min')
        mc_max = current_filters.get('mc_max')
        text = "💰 **Set Market Cap Filter**\n\nChoose a preset value or clear:"
        keyboard = get_filter_param_keyboard('mc', mc_min, mc_max)
        await edit_or_send_message(update, text, keyboard)
    
    elif data == "builder_volume":
        # Show Volume setting keyboard
        vol_min = current_filters.get('volume_min')
        vol_max = current_filters.get('volume_max')
        text = "📊 **Set 24h Volume Filter**\n\nChoose a preset value or clear:"
        keyboard = get_filter_param_keyboard('volume', vol_min, vol_max)
        await edit_or_send_message(update, text, keyboard)
    
    elif data == "builder_liquidity":
        # Show Liquidity setting keyboard
        liq_min = current_filters.get('liquidity_min')
        liq_max = current_filters.get('liquidity_max')
        text = "💧 **Set Liquidity Filter**\n\nChoose a preset value or clear:"
        keyboard = get_filter_param_keyboard('liquidity', liq_min, liq_max)
        await edit_or_send_message(update, text, keyboard)
    
    elif data == "builder_holders":
        # Show Holders setting keyboard
        holders_min = current_filters.get('holders_min')
        holders_max = current_filters.get('holders_max')
        text = "👥 **Set Holders Filter**\n\nChoose a preset value or clear:"
        keyboard = get_filter_param_keyboard('holders', holders_min, holders_max)
        await edit_or_send_message(update, text, keyboard)


async def handle_set_filter_value(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """Handle setting a specific filter value."""
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    
    if 'builder_filters' not in user_state:
        user_state['builder_filters'] = {}
    
    # Parse the data: set_{param}_{minmax}_{value}
    parts = data.replace('set_', '').split('_')
    if len(parts) >= 3:
        param = parts[0]
        min_or_max = parts[1]
        value = int(parts[2])
        
        filter_key = f"{param}_{min_or_max}"
        user_state['builder_filters'][filter_key] = value
    
    # Return to builder
    await show_filter_builder(update, context)


async def handle_clear_filter(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """Clear a specific filter parameter."""
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    
    if 'builder_filters' not in user_state:
        user_state['builder_filters'] = {}
    
    # Parse: clear_{param}
    param = data.replace('clear_', '')
    
    # Remove both min and max for this param
    user_state['builder_filters'].pop(f'{param}_min', None)
    user_state['builder_filters'].pop(f'{param}_max', None)
    
    # Return to builder
    await show_filter_builder(update, context)


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
        
        # ALWAYS fetch fresh data - NO CACHE for filters
        logger.info("Fetching fresh memecoin data")
        async with DexScreenerClient() as client:
            memecoins = await client.search_memecoins(filters)
        
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
        page_size = 15
        results_text = format_memecoin_list(memecoins, page_size)
        results_text += f"\n\n**Filter:** {format_filters_display(filters)}"
        results_text += f"\n**Found:** {len(memecoins)} tokens"
        
        # Store results in user state for pagination
        user_id = update.effective_user.id
        set_user_state(user_id, BotState.NORMAL, last_results=memecoins, last_filters=filters)
        
        keyboard = get_memecoin_results_keyboard(memecoins[:page_size])
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

**Custom Filter Builder:**
Use the interactive filter builder to:
1. Click on **Market Cap**, **Volume**, **Liquidity**, or **Holders**
2. Select preset values (Min/Max)
3. Click **Any** to remove restrictions
4. Click **Search** to find tokens

The builder makes it easy to combine multiple criteria without typing!
"""
        
    elif data == "help_about":
        text = """
🤖 **About Solana Memecoins Analyzer**

**Version:** 2.0.0
**Developer:** Solana Memecoins Team

**Features:**
🔍 **Smart Filtering** - Find tokens by multiple criteria
🔧 **Interactive Builder** - Easy-to-use filter controls
💧 **Live Data** - Real-time DexScreener integration
⚡ **Fast Results** - Comprehensive token discovery

**Data Sources:**
• **DexScreener API** - Token prices, volume, liquidity

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
    items_per_page = 15
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
    results_text = format_memecoin_list(page_results, items_per_page)
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
    # No external API clients needed - DexScreener is initialized per-request
    logger.info("Bot initialized successfully")
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
