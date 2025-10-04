import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import aiohttp
from typing import Dict, List, Optional

# User session storage
user_filters: Dict[int, Dict] = {}

class SolanaTrackerAPI:
    """Solana Tracker API client for real-time Solana token data"""
    
    BASE_URL = "https://data.solanatracker.io"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.headers = {
            "Accept": "application/json"
        }
        if api_key:
            self.headers["x-api-key"] = api_key
    
    async def get_new_tokens(self, limit: int = 50) -> List[Dict]:
        """Get newly created tokens on Solana"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.BASE_URL}/tokens/latest"
            
            try:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    print(f"SolanaTracker Status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        tokens_data = data if isinstance(data, list) else []
                        print(f"SolanaTracker found {len(tokens_data)} tokens")
                        
                        # Convert to our format
                        tokens = []
                        
                        for item in tokens_data:
                            token = item.get('token', {})
                            pools = item.get('pools', [])
                            
                            if not pools:
                                continue
                            
                            # Get primary pool (first one, usually highest liquidity)
                            pool = pools[0]
                            
                            address = token.get('mint', '')
                            if not address:
                                continue
                            
                            creation = token.get('creation', {})
                            created_at = creation.get('created_time', 0)
                            
                            mc = pool.get('marketCap', {}).get('usd', 0) or 0
                            volume_24h = pool.get('txns', {}).get('volume24h', 0) or 0
                            liquidity = pool.get('liquidity', {}).get('usd', 0) or 0
                            
                            tokens.append({
                                'address': address,
                                'name': token.get('name', 'Unknown'),
                                'symbol': token.get('symbol', '?'),
                                'mc': mc,
                                'v24hUSD': volume_24h,
                                'liquidity': liquidity,
                                'createdAt': created_at,
                                'priceChange24h': 0
                            })
                        
                        # Sort by creation time (newest first)
                        tokens.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
                        return tokens[:limit]
                    else:
                        error_text = await resp.text()
                        print(f"SolanaTracker Error: {error_text}")
            except Exception as e:
                print(f"SolanaTracker Error: {e}")
            return []

def init_user_filters(user_id: int):
    """Initialize default filters for a user"""
    if user_id not in user_filters:
        user_filters[user_id] = {
            'min_mc': 0,
            'max_mc': float('inf'),
            'min_volume': 0,
            'max_age_hours': 168,  # 7 days default
            'min_liquidity': 0
        }

def format_number(num: float) -> str:
    """Format large numbers with K, M, B suffixes"""
    if num >= 1_000_000_000:
        return f"${num/1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"${num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"${num/1_000:.2f}K"
    else:
        return f"${num:.2f}"

def format_age(timestamp: int) -> str:
    """Format token age"""
    age_seconds = datetime.now().timestamp() - timestamp
    age_hours = age_seconds / 3600
    
    if age_hours < 1:
        return f"{int(age_seconds / 60)}m"
    elif age_hours < 24:
        return f"{int(age_hours)}h"
    else:
        return f"{int(age_hours / 24)}d"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    init_user_filters(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
        [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
        [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🚀 *Solana Memecoin Tracker*\n\n"
        "Track the latest Solana memecoins with real-time data.\n\n"
        "• Search tokens by filters\n"
        "• Real-time market data\n"
        "• Latest tokens first\n\n"
        "Get started by setting your filters or search now!"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_filters_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show filter configuration menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💰 Market Cap", callback_data="filter_mc")],
        [InlineKeyboardButton("📊 Volume (24h)", callback_data="filter_volume")],
        [InlineKeyboardButton("⏰ Max Age", callback_data="filter_age")],
        [InlineKeyboardButton("💧 Min Liquidity", callback_data="filter_liquidity")],
        [InlineKeyboardButton("🔄 Reset Filters", callback_data="reset_filters")],
        [InlineKeyboardButton("« Back", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⚙️ *Filter Settings*\n\nSelect a filter to configure:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_current_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display current filter settings"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    init_user_filters(user_id)
    filters = user_filters[user_id]
    
    text = "📊 *Current Filters:*\n\n"
    text += f"💰 Market Cap: ${filters['min_mc']:,.0f} - "
    max_mc_display = "∞" if filters['max_mc'] == float('inf') else f"${filters['max_mc']:,.0f}"
    text += f"{max_mc_display}\n"
    text += f"📊 Min Volume (24h): ${filters['min_volume']:,.0f}\n"
    text += f"⏰ Max Age: {filters['max_age_hours']}h\n"
    text += f"💧 Min Liquidity: ${filters['min_liquidity']:,.0f}\n"
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Edit Filters", callback_data="filters")],
        [InlineKeyboardButton("« Back", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def filter_mc_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Market cap filter menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("$0 - $100K", callback_data="mc_0_100k")],
        [InlineKeyboardButton("$100K - $1M", callback_data="mc_100k_1m")],
        [InlineKeyboardButton("$1M - $10M", callback_data="mc_1m_10m")],
        [InlineKeyboardButton("$10M+", callback_data="mc_10m_plus")],
        [InlineKeyboardButton("Any", callback_data="mc_any")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💰 *Select Market Cap Range:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_volume_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volume filter menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("$0+", callback_data="vol_0")],
        [InlineKeyboardButton("$10K+", callback_data="vol_10k")],
        [InlineKeyboardButton("$50K+", callback_data="vol_50k")],
        [InlineKeyboardButton("$100K+", callback_data="vol_100k")],
        [InlineKeyboardButton("$500K+", callback_data="vol_500k")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📊 *Select Minimum 24h Volume:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_age_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Age filter menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("1 Hour", callback_data="age_1h")],
        [InlineKeyboardButton("6 Hours", callback_data="age_6h")],
        [InlineKeyboardButton("24 Hours", callback_data="age_24h")],
        [InlineKeyboardButton("7 Days", callback_data="age_7d")],
        [InlineKeyboardButton("Any", callback_data="age_any")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⏰ *Select Maximum Token Age:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_liquidity_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liquidity filter menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("$0+", callback_data="liq_0")],
        [InlineKeyboardButton("$5K+", callback_data="liq_5k")],
        [InlineKeyboardButton("$20K+", callback_data="liq_20k")],
        [InlineKeyboardButton("$50K+", callback_data="liq_50k")],
        [InlineKeyboardButton("$100K+", callback_data="liq_100k")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💧 *Select Minimum Liquidity:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def search_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search and display tokens based on filters"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    init_user_filters(user_id)
    filters = user_filters[user_id]
    
    await query.edit_message_text("🔍 Searching for tokens... Please wait.")
    
    all_tokens = []
    
    try:
        # Use Solana Tracker API (best for Solana tokens)
        print("Fetching tokens from SolanaTracker API...")
        api_key = os.getenv('SOLANATRACKER_API_KEY', '')
        solana_api = SolanaTrackerAPI(api_key if api_key else None)
        all_tokens = await solana_api.get_new_tokens(limit=100)
        
        if not all_tokens:
            keyboard = [[InlineKeyboardButton("« Back", callback_data="back_main")]]
            await query.edit_message_text(
                "❌ No tokens found.\n\n"
                "This could be due to:\n"
                "• Network issues\n"
                "• API rate limits\n"
                "• Try again in a moment",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Filter tokens
        filtered_tokens = []
        current_time = datetime.now().timestamp()
        
        for token in all_tokens:
            # Get market data
            mc = token.get('mc', 0) or 0
            volume_24h = token.get('v24hUSD', 0) or 0
            liquidity = token.get('liquidity', 0) or 0
            created_at = token.get('createdAt', 0) or 0
            
            # Calculate age in hours
            if created_at:
                age_hours = (current_time - created_at) / 3600
            else:
                age_hours = float('inf')
            
            # Apply filters
            if (filters['min_mc'] <= mc <= filters['max_mc'] and
                volume_24h >= filters['min_volume'] and
                age_hours <= filters['max_age_hours'] and
                liquidity >= filters['min_liquidity']):
                filtered_tokens.append(token)
        
        if not filtered_tokens:
            keyboard = [[InlineKeyboardButton("« Back", callback_data="back_main")]]
            await query.edit_message_text(
                "😔 No tokens match your filters.\n\nTry adjusting your criteria.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Display results (top 10)
        result_text = f"🎯 *Found {len(filtered_tokens)} tokens*\n\n"
        
        for i, token in enumerate(filtered_tokens[:10], 1):
            name = token.get('name', 'Unknown')
            symbol = token.get('symbol', '?')
            address = token.get('address', '')
            mc = token.get('mc', 0) or 0
            volume = token.get('v24hUSD', 0) or 0
            created_at = token.get('createdAt', 0)
            
            age = format_age(created_at) if created_at else 'N/A'
            
            result_text += f"*{i}. {name}* (${symbol})\n"
            result_text += f"💰 MC: {format_number(mc)}\n"
            result_text += f"📊 Vol: {format_number(volume)}\n"
            result_text += f"⏰ Age: {age}\n"
            result_text += f"🔗 `{address}`\n\n"
        
        if len(filtered_tokens) > 10:
            result_text += f"_...and {len(filtered_tokens) - 10} more tokens_\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="search")],
            [InlineKeyboardButton("« Back", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            result_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        keyboard = [[InlineKeyboardButton("« Back", callback_data="back_main")]]
        await query.edit_message_text(
            f"❌ Error fetching data: {str(e)}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_filter_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle filter value selections"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    init_user_filters(user_id)
    data = query.data
    
    # Market cap filters
    if data == "mc_0_100k":
        user_filters[user_id]['min_mc'] = 0
        user_filters[user_id]['max_mc'] = 100_000
    elif data == "mc_100k_1m":
        user_filters[user_id]['min_mc'] = 100_000
        user_filters[user_id]['max_mc'] = 1_000_000
    elif data == "mc_1m_10m":
        user_filters[user_id]['min_mc'] = 1_000_000
        user_filters[user_id]['max_mc'] = 10_000_000
    elif data == "mc_10m_plus":
        user_filters[user_id]['min_mc'] = 10_000_000
        user_filters[user_id]['max_mc'] = float('inf')
    elif data == "mc_any":
        user_filters[user_id]['min_mc'] = 0
        user_filters[user_id]['max_mc'] = float('inf')
    
    # Volume filters
    elif data == "vol_0":
        user_filters[user_id]['min_volume'] = 0
    elif data == "vol_10k":
        user_filters[user_id]['min_volume'] = 10_000
    elif data == "vol_50k":
        user_filters[user_id]['min_volume'] = 50_000
    elif data == "vol_100k":
        user_filters[user_id]['min_volume'] = 100_000
    elif data == "vol_500k":
        user_filters[user_id]['min_volume'] = 500_000
    
    # Age filters
    elif data == "age_1h":
        user_filters[user_id]['max_age_hours'] = 1
    elif data == "age_6h":
        user_filters[user_id]['max_age_hours'] = 6
    elif data == "age_24h":
        user_filters[user_id]['max_age_hours'] = 24
    elif data == "age_7d":
        user_filters[user_id]['max_age_hours'] = 168
    elif data == "age_any":
        user_filters[user_id]['max_age_hours'] = float('inf')
    
    # Liquidity filters
    elif data == "liq_0":
        user_filters[user_id]['min_liquidity'] = 0
    elif data == "liq_5k":
        user_filters[user_id]['min_liquidity'] = 5_000
    elif data == "liq_20k":
        user_filters[user_id]['min_liquidity'] = 20_000
    elif data == "liq_50k":
        user_filters[user_id]['min_liquidity'] = 50_000
    elif data == "liq_100k":
        user_filters[user_id]['min_liquidity'] = 100_000
    
    # Reset filters
    elif data == "reset_filters":
        user_filters[user_id] = {
            'min_mc': 0,
            'max_mc': float('inf'),
            'min_volume': 0,
            'max_age_hours': 168,
            'min_liquidity': 0
        }
    
    await query.answer("✅ Filter updated!")
    await show_filters_menu(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks"""
    query = update.callback_query
    data = query.data
    
    if data == "filters":
        await show_filters_menu(update, context)
    elif data == "show_filters":
        await show_current_filters(update, context)
    elif data == "filter_mc":
        await filter_mc_menu(update, context)
    elif data == "filter_volume":
        await filter_volume_menu(update, context)
    elif data == "filter_age":
        await filter_age_menu(update, context)
    elif data == "filter_liquidity":
        await filter_liquidity_menu(update, context)
    elif data == "search":
        await search_tokens(update, context)
    elif data == "back_main":
        keyboard = [
            [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
            [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
            [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🚀 *Solana Memecoin Tracker*\n\nWhat would you like to do?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        # Handle filter selections
        await handle_filter_selection(update, context)

def main():
    """Start the bot"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable not set")
        return
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start bot
    print("🤖 Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

