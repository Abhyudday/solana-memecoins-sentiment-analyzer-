import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import aiohttp
from typing import Dict, List, Optional

# User session storage
user_filters: Dict[int, Dict] = {}

class GeckoTerminalAPI:
    """GeckoTerminal API client for real-time Solana token data"""
    
    BASE_URL = "https://api.geckoterminal.com/api/v2"
    
    async def get_new_tokens(self, limit: int = 50) -> List[Dict]:
        """Get newly created tokens on Solana"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.BASE_URL}/networks/solana/new_pools"
            params = {"page": 1}
            
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    print(f"GeckoTerminal Status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        pools = data.get('data', [])
                        print(f"GeckoTerminal found {len(pools)} pools")
                        
                        # Convert to our format
                        tokens = []
                        seen_addresses = set()
                        
                        for pool in pools:
                            attributes = pool.get('attributes', {})
                            base_token_price = attributes.get('base_token_price_usd', '0')
                            
                            address = attributes.get('base_token_address', '')
                            if address and address not in seen_addresses:
                                seen_addresses.add(address)
                                
                                # Parse values safely
                                try:
                                    fdv = float(attributes.get('fdv_usd', 0) or 0)
                                    volume_24h = float(attributes.get('volume_usd', {}).get('h24', 0) or 0)
                                    liquidity = float(attributes.get('reserve_in_usd', 0) or 0)
                                except (ValueError, TypeError):
                                    fdv = volume_24h = liquidity = 0
                                
                                # Parse timestamp
                                created_at_str = attributes.get('pool_created_at', '')
                                created_at = 0
                                if created_at_str:
                                    try:
                                        from datetime import datetime as dt
                                        created_at = dt.fromisoformat(created_at_str.replace('Z', '+00:00')).timestamp()
                                    except:
                                        created_at = 0
                                
                                tokens.append({
                                    'address': address,
                                    'name': attributes.get('name', 'Unknown'),
                                    'symbol': attributes.get('base_token_symbol', '?'),
                                    'mc': fdv,
                                    'v24hUSD': volume_24h,
                                    'liquidity': liquidity,
                                    'createdAt': created_at,
                                    'priceChange24h': float(attributes.get('price_change_percentage', {}).get('h24', 0) or 0)
                                })
                        
                        # Sort by creation time (newest first)
                        tokens.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
                        return tokens[:limit]
            except Exception as e:
                print(f"GeckoTerminal Error: {e}")
            return []

class DexScreenerAPI:
    """DexScreener API client for real-time Solana token data"""
    
    BASE_URL = "https://api.dexscreener.com/latest"
    
    async def get_new_tokens(self, limit: int = 50) -> List[Dict]:
        """Get newly created tokens on Solana"""
        async with aiohttp.ClientSession() as session:
            # Get tokens by specific DEXs on Solana
            dexes = ['raydium', 'orca', 'jupiter']
            all_pairs = []
            
            for dex in dexes:
                url = f"{self.BASE_URL}/dex/pairs/solana"
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            pairs = data.get('pairs', [])
                            if pairs:
                                all_pairs.extend(pairs)
                                break  # Got data, no need to try other dexes
                except Exception as e:
                    print(f"DexScreener {dex} error: {e}")
                    continue
            
            if not all_pairs:
                print(f"DexScreener: No pairs found")
                return []
            
            print(f"DexScreener found {len(all_pairs)} pairs")
            
            # Convert to our format
            tokens = []
            seen_addresses = set()
            
            for pair in all_pairs:
                base_token = pair.get('baseToken', {})
                address = base_token.get('address', '')
                
                if address and address not in seen_addresses:
                    seen_addresses.add(address)
                    
                    created_at = pair.get('pairCreatedAt', 0)
                    if created_at:
                        created_at = created_at / 1000  # Convert from ms to seconds
                    
                    tokens.append({
                        'address': address,
                        'name': base_token.get('name', 'Unknown'),
                        'symbol': base_token.get('symbol', '?'),
                        'mc': pair.get('fdv', 0) or pair.get('marketCap', 0) or 0,
                        'v24hUSD': pair.get('volume', {}).get('h24', 0) or 0,
                        'liquidity': pair.get('liquidity', {}).get('usd', 0) or 0,
                        'createdAt': created_at,
                        'priceChange24h': pair.get('priceChange', {}).get('h24', 0) or 0
                    })
            
            # Sort by creation time (newest first)
            tokens.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
            return tokens[:limit]

class BirdeyeAPI:
    """Birdeye API client for real-time Solana token data"""
    
    BASE_URL = "https://public-api.birdeye.so"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "X-API-KEY": api_key,
            "Accept": "application/json"
        }
    
    async def get_new_tokens(self, limit: int = 50) -> List[Dict]:
        """Get newly created tokens on Solana"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.BASE_URL}/defi/tokenlist"
            params = {
                "sort_by": "v24hUSD",
                "sort_type": "desc",
                "offset": 0,
                "limit": limit
            }
            
            async with session.get(url, headers=self.headers, params=params) as resp:
                print(f"Birdeye Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get('data', {}).get('tokens', [])
                    if not items:
                        items = data.get('data', [])
                    print(f"Birdeye found {len(items)} tokens")
                    return items
                else:
                    error_text = await resp.text()
                    print(f"Birdeye Error: {error_text}")
                    return []
    
    async def get_token_details(self, address: str) -> Optional[Dict]:
        """Get detailed token information"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.BASE_URL}/defi/v3/token/overview"
            params = {"address": address}
            
            async with session.get(url, headers=self.headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('data', {})
                return None

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
        # Try GeckoTerminal first (free, reliable)
        print("Trying GeckoTerminal API...")
        gecko_api = GeckoTerminalAPI()
        all_tokens = await gecko_api.get_new_tokens(limit=100)
        
        # If no results, try DexScreener
        if not all_tokens:
            print("Trying DexScreener API...")
            dex_api = DexScreenerAPI()
            all_tokens = await dex_api.get_new_tokens(limit=100)
        
        # If still no results and Birdeye key is available, try Birdeye
        if not all_tokens:
            api_key = os.getenv('BIRDEYE_API_KEY', '')
            if api_key:
                print("Trying Birdeye API as fallback...")
                birdeye_api = BirdeyeAPI(api_key)
                all_tokens = await birdeye_api.get_new_tokens(limit=100)
        
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

