
import os
import asyncio
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import aiohttp
from typing import Dict, List, Optional

# Conversation states
WAITING_CUSTOM_MC, WAITING_CUSTOM_VOLUME, WAITING_CUSTOM_MIN_AGE, WAITING_CUSTOM_MAX_AGE, WAITING_CUSTOM_LIQUIDITY, WAITING_CUSTOM_HOLDERS = range(6)

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
    
    async def get_new_tokens(self, limit: int = 500, filters: dict = None) -> List[Dict]:
        """Get newly created tokens on Solana using search endpoint with filters"""
        async with aiohttp.ClientSession() as session:
            # Build URL with filters - let the API do the filtering
            params = [
                f"sortBy=createdAt",
                f"sortOrder=desc",
                f"limit={limit}"
            ]
            
            # Add filters if provided
            if filters:
                if filters.get('min_mc', 0) > 0:
                    params.append(f"minMarketCap={filters['min_mc']}")
                if filters.get('max_mc', float('inf')) < float('inf'):
                    params.append(f"maxMarketCap={filters['max_mc']}")
                if filters.get('min_volume', 0) > 0:
                    params.append(f"minVolume_24h={filters['min_volume']}")
                if filters.get('min_liquidity', 0) > 0:
                    params.append(f"minLiquidity={filters['min_liquidity']}")
                if filters.get('min_holders', 0) > 0:
                    params.append(f"minHolders={filters['min_holders']}")
                
                # Convert age filters to timestamps
                current_time = int(datetime.now().timestamp())
                max_age_minutes = filters.get('max_age_minutes', float('inf'))
                min_age_minutes = filters.get('min_age_minutes', 0)
                
                print(f"🕐 Timestamp calc: current_time={current_time}, min_age={min_age_minutes}min, max_age={max_age_minutes}min")
                
                # Initialize timestamp variables
                min_created = None
                max_created = None
                
                # Only add timestamp filters if values are not infinity
                if max_age_minutes < float('inf'):
                    # minCreatedAt = current time - max age (oldest allowed)
                    min_created = current_time - int(max_age_minutes * 60)
                    print(f"  minCreatedAt={min_created} (tokens created AFTER {max_age_minutes} min ago)")
                    params.append(f"minCreatedAt={min_created}")
                
                if min_age_minutes > 0:
                    # maxCreatedAt = current time - min age (most recent allowed)
                    max_created = current_time - int(min_age_minutes * 60)
                    print(f"  maxCreatedAt={max_created} (tokens created BEFORE {min_age_minutes} min ago)")
                    params.append(f"maxCreatedAt={max_created}")
                
                # Only show search window if both timestamps are defined
                if min_created is not None and max_created is not None:
                    print(f"  ⚠️  Search window: {min_created} to {max_created} (span: {max_created - min_created}s = {(max_created - min_created)/60:.1f}min)")
            
            url = f"{self.BASE_URL}/search?{'&'.join(params)}"
            print(f"Requesting with filters: {url}")
            
            try:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    print(f"SolanaTracker Status: {resp.status}")
                    if resp.status == 200:
                        response = await resp.json()
                        # Search endpoint returns {"status": "success", "data": [...], "total": X}
                        if response.get('status') == 'success':
                            tokens_data = response.get('data', [])
                        else:
                            tokens_data = response if isinstance(response, list) else []
                        
                        print(f"SolanaTracker found {len(tokens_data)} tokens (Total available: {response.get('total', 'unknown') if isinstance(response, dict) else 'unknown'})")
                        
                        # Convert to our format
                        tokens = []
                        
                        for item in tokens_data:
                            # Search endpoint returns different structure
                            # Data is at root level, not nested in token/pools
                            address = item.get('mint', '')
                            if not address:
                                continue
                            
                            # Get created_time from tokenDetails.time (Unix timestamp in seconds)
                            token_details = item.get('tokenDetails', {})
                            created_at = token_details.get('time', 0) or 0
                            
                            # Debug: log timestamp for first few tokens
                            if len(tokens) < 3:
                                print(f"Token {item.get('symbol', '?')}: created_time={created_at}, type={type(created_at)}")
                            
                            # Get market data directly from root level
                            mc = item.get('marketCapUsd', 0) or 0
                            volume_24h = item.get('volume_24h', 0) or 0
                            liquidity = item.get('liquidityUsd', 0) or 0
                            
                            # Get holder count from root level
                            holder_count = item.get('holders', 0) or 0
                            
                            tokens.append({
                                'address': address,
                                'name': item.get('name', 'Unknown'),
                                'symbol': item.get('symbol', '?'),
                                'mc': mc,
                                'v24hUSD': volume_24h,
                                'liquidity': liquidity,
                                'createdAt': created_at,
                                'priceChange24h': 0,
                                'holders': holder_count
                            })
                        
                        print(f"Successfully parsed {len(tokens)} tokens")
                        if tokens:
                            sample = tokens[0]
                            created = sample.get('createdAt')
                            print(f"Sample token data: {sample.get('symbol')} - holders: {sample.get('holders')}, createdAt: {created}")
                            if created:
                                from datetime import datetime as dt
                                try:
                                    # Show human-readable date
                                    readable_date = dt.fromtimestamp(created).strftime('%Y-%m-%d %H:%M:%S')
                                    print(f"Token creation date: {readable_date}")
                                    age_calc = (dt.now().timestamp() - created) / 60
                                    print(f"Age in minutes: {age_calc:.2f}")
                                    age_hours = age_calc / 60
                                    print(f"Age in hours: {age_hours:.2f}")
                                    age_days = age_hours / 24
                                    print(f"Age in days: {age_days:.2f}")
                                except Exception as e:
                                    print(f"Error parsing timestamp: {e}")
                        
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
            'min_age_minutes': 0,  # Minimum age filter in minutes
            'max_age_minutes': 10080,  # 7 days default (7*24*60)
            'min_liquidity': 0,
            'min_holders': 0
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

def normalize_timestamp(timestamp: int) -> int:
    """Normalize timestamp to seconds (handle both seconds and milliseconds)"""
    if timestamp > 1e12:  # Likely milliseconds
        return int(timestamp / 1000)
    return int(timestamp)

def format_age(timestamp: int) -> str:
    """Format token age"""
    if not timestamp or timestamp <= 0:
        return "N/A"
    
    normalized_timestamp = normalize_timestamp(timestamp)
    age_seconds = datetime.now().timestamp() - normalized_timestamp
    
    if age_seconds < 0:
        return "N/A"
    
    age_minutes = age_seconds / 60
    age_hours = age_seconds / 3600
    
    # Show seconds for very new tokens (< 1 minute)
    if age_seconds < 60:
        return f"{int(age_seconds)}s"
    elif age_minutes < 60:
        return f"{int(age_minutes)}m"
    elif age_hours < 24:
        return f"{int(age_hours)}h"
    else:
        return f"{int(age_hours / 24)}d"

def parse_number(text: str) -> float:
    """Parse numbers with K, M, B suffixes"""
    text = text.strip().upper().replace('$', '').replace(',', '')
    
    multiplier = 1
    if text.endswith('K'):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith('M'):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith('B'):
        multiplier = 1_000_000_000
        text = text[:-1]
    
    try:
        return float(text) * multiplier
    except ValueError:
        return 0

def parse_time_input(text: str) -> float:
    """Parse time input and convert to minutes"""
    text = text.strip().lower().replace(' ', '')
    
    # Handle different time units
    if text.endswith('m') or text.endswith('min') or text.endswith('minutes'):
        # Minutes
        num_str = text.replace('m', '').replace('in', '').replace('utes', '')
        try:
            return float(num_str)
        except ValueError:
            return 0
    elif text.endswith('h') or text.endswith('hr') or text.endswith('hours'):
        # Hours to minutes
        num_str = text.replace('h', '').replace('r', '').replace('ours', '')
        try:
            return float(num_str) * 60
        except ValueError:
            return 0
    elif text.endswith('d') or text.endswith('day') or text.endswith('days'):
        # Days to minutes
        num_str = text.replace('d', '').replace('ay', '').replace('s', '')
        try:
            return float(num_str) * 24 * 60
        except ValueError:
            return 0
    else:
        # Assume minutes if no unit specified
        try:
            return float(text)
        except ValueError:
            return 0

def parse_custom_filter(text: str, filter_type: str) -> Dict:
    """Parse custom filter input like '>5', '<100', '50-100', '50k', etc."""
    text = text.strip().lower()
    result = {}
    
    # Handle range format: "50-100", "50k-1m"
    if '-' in text and not text.startswith('-'):
        parts = text.split('-')
        if len(parts) == 2:
            if filter_type == 'age':
                min_val = parse_time_input(parts[0])
                max_val = parse_time_input(parts[1])
            else:
                min_val = parse_number(parts[0])
                max_val = parse_number(parts[1])
            result['min'] = min_val
            result['max'] = max_val
            return result
    
    # Handle comparison operators
    if text.startswith('>'):
        if filter_type == 'age':
            val = parse_time_input(text[1:])
        else:
            val = parse_number(text[1:])
        result['min'] = val
        if filter_type in ['mc', 'volume', 'liquidity']:
            result['max'] = float('inf')
    elif text.startswith('<'):
        if filter_type == 'age':
            val = parse_time_input(text[1:])
        else:
            val = parse_number(text[1:])
        result['max'] = val
        if filter_type in ['mc', 'volume', 'liquidity']:
            result['min'] = 0
    else:
        # Single value - treat as minimum for age, or exact value
        if filter_type == 'age':
            val = parse_time_input(text)
        else:
            val = parse_number(text)
        result['min'] = val
        if filter_type in ['mc', 'volume', 'liquidity']:
            result['max'] = float('inf')
    
    return result

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
        [InlineKeyboardButton("⏰ Min Age", callback_data="filter_min_age")],
        [InlineKeyboardButton("⏱️ Max Age", callback_data="filter_max_age")],
        [InlineKeyboardButton("💧 Min Liquidity", callback_data="filter_liquidity")],
        [InlineKeyboardButton("👥 Min Holders", callback_data="filter_holders")],
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
    
    def format_time_display(minutes: float) -> str:
        if minutes == float('inf'):
            return "∞"
        elif minutes >= 1440:  # >= 1 day
            days = minutes / 1440
            return f"{days:.1f}d" if days != int(days) else f"{int(days)}d"
        elif minutes >= 60:  # >= 1 hour
            hours = minutes / 60
            return f"{hours:.1f}h" if hours != int(hours) else f"{int(hours)}h"
        else:
            return f"{int(minutes)}m"
    
    text = "📊 *Current Filters:*\n\n"
    text += f"💰 Market Cap: ${filters['min_mc']:,.0f} - "
    max_mc_display = "∞" if filters['max_mc'] == float('inf') else f"${filters['max_mc']:,.0f}"
    text += f"{max_mc_display}\n"
    text += f"📊 Min Volume (24h): ${filters['min_volume']:,.0f}\n"
    text += f"⏰ Min Age: {format_time_display(filters['min_age_minutes'])}\n"
    text += f"⏱️ Max Age: {format_time_display(filters['max_age_minutes'])}\n"
    text += f"💧 Min Liquidity: ${filters['min_liquidity']:,.0f}\n"
    text += f"👥 Min Holders: {filters['min_holders']:,}\n"
    
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
        [InlineKeyboardButton("✏️ Custom", callback_data="mc_custom")],
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
        [InlineKeyboardButton("✏️ Custom", callback_data="vol_custom")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📊 *Select Minimum 24h Volume:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_min_age_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Minimum age filter menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("0 Minutes (Any)", callback_data="min_age_0m")],
        [InlineKeyboardButton("5 Minutes+", callback_data="min_age_5m")],
        [InlineKeyboardButton("30 Minutes+", callback_data="min_age_30m")],
        [InlineKeyboardButton("1 Hour+", callback_data="min_age_1h")],
        [InlineKeyboardButton("6 Hours+", callback_data="min_age_6h")],
        [InlineKeyboardButton("24 Hours+", callback_data="min_age_24h")],
        [InlineKeyboardButton("✏️ Custom", callback_data="min_age_custom")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⏰ *Select Minimum Token Age:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_max_age_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maximum age filter menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("10 Minutes", callback_data="max_age_10m")],
        [InlineKeyboardButton("30 Minutes", callback_data="max_age_30m")],
        [InlineKeyboardButton("1 Hour", callback_data="max_age_1h")],
        [InlineKeyboardButton("6 Hours", callback_data="max_age_6h")],
        [InlineKeyboardButton("24 Hours", callback_data="max_age_24h")],
        [InlineKeyboardButton("7 Days", callback_data="max_age_7d")],
        [InlineKeyboardButton("Any", callback_data="max_age_any")],
        [InlineKeyboardButton("✏️ Custom", callback_data="max_age_custom")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⏱️ *Select Maximum Token Age:*",
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
        [InlineKeyboardButton("✏️ Custom", callback_data="liq_custom")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💧 *Select Minimum Liquidity:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def filter_holders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Holders filter menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("0+ (Any)", callback_data="holders_0")],
        [InlineKeyboardButton("10+", callback_data="holders_10")],
        [InlineKeyboardButton("50+", callback_data="holders_50")],
        [InlineKeyboardButton("100+", callback_data="holders_100")],
        [InlineKeyboardButton("500+", callback_data="holders_500")],
        [InlineKeyboardButton("1000+", callback_data="holders_1000")],
        [InlineKeyboardButton("✏️ Custom", callback_data="holders_custom")],
        [InlineKeyboardButton("« Back", callback_data="filters")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👥 *Select Minimum Holders:*",
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
    
    # Get current time ONCE for consistent filtering
    current_time = datetime.now().timestamp()
    
    try:
        # Use Solana Tracker API with server-side filtering
        print("=" * 60)
        print("FILTERS BEING SENT TO API:")
        print(f"  min_mc: {filters.get('min_mc', 'NOT SET')}")
        print(f"  max_mc: {filters.get('max_mc', 'NOT SET')}")
        print(f"  min_volume: {filters.get('min_volume', 'NOT SET')}")
        print(f"  min_liquidity: {filters.get('min_liquidity', 'NOT SET')}")
        print(f"  min_holders: {filters.get('min_holders', 'NOT SET')}")
        print(f"  min_age_minutes: {filters.get('min_age_minutes', 'NOT SET')}")
        print(f"  max_age_minutes: {filters.get('max_age_minutes', 'NOT SET')}")
        print("=" * 60)
        
        print("Fetching tokens from SolanaTracker API...")
        api_key = os.getenv('SOLANATRACKER_API_KEY', '')
        solana_api = SolanaTrackerAPI(api_key if api_key else None)
        # Pass filters to API for server-side filtering (scans ALL tokens)
        all_tokens = await solana_api.get_new_tokens(limit=500, filters=filters)
        print(f"Received {len(all_tokens)} tokens from API after parsing (filtered by API)")
        
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
        
        # API already did filtering, only validate data quality (no age re-filtering)
        filtered_tokens = []
        
        print(f"Validating {len(all_tokens)} tokens (API pre-filtered)")
        print(f"Applied filters: MC={filters['min_mc']}-{filters['max_mc']}, Vol>={filters['min_volume']}, Age={filters['min_age_minutes']}-{filters['max_age_minutes']}min, Liq>={filters['min_liquidity']}, Holders>={filters['min_holders']}")
        
        skipped_no_timestamp = 0
        skipped_filters = 0
        filter_reasons = {'mc': 0, 'volume': 0, 'age_min': 0, 'age_max': 0, 'liquidity': 0, 'holders': 0}
        
        for token in all_tokens:
            # Get market data with better validation
            try:
                mc = float(token.get('mc', 0) or 0)
                volume_24h = float(token.get('v24hUSD', 0) or 0)
                liquidity = float(token.get('liquidity', 0) or 0)
                created_at = int(token.get('createdAt', 0) or 0)
                holders = int(token.get('holders', 0) or 0)
            except (ValueError, TypeError) as e:
                print(f"Skipped token due to invalid data: {e}")
                continue
            
            # Skip tokens without valid timestamp (API should have filtered these)
            if not created_at or created_at <= 0:
                skipped_no_timestamp += 1
                if skipped_no_timestamp <= 3:
                    print(f"Token without timestamp: {token.get('symbol')} - created_at was {created_at}")
                continue
            
            # Check for future timestamps
            normalized_timestamp = normalize_timestamp(created_at)
            age_seconds = current_time - normalized_timestamp
            if age_seconds < 0:
                print(f"Skipped token with future timestamp: {token.get('symbol')} - timestamp: {created_at}")
                continue
            
            # Only re-filter fields that API doesn't support or for data validation
            # DO NOT re-filter age since API already did it with correct timestamp
            passes_mc = filters['min_mc'] <= mc <= filters['max_mc']
            passes_volume = volume_24h >= filters['min_volume']
            passes_liquidity = liquidity >= filters['min_liquidity']
            passes_holders = holders >= filters['min_holders']
            
            if passes_mc and passes_volume and passes_liquidity and passes_holders:
                filtered_tokens.append(token)
            else:
                skipped_filters += 1
                if not passes_mc: filter_reasons['mc'] += 1
                if not passes_volume: filter_reasons['volume'] += 1
                if not passes_liquidity: filter_reasons['liquidity'] += 1
                if not passes_holders: filter_reasons['holders'] += 1
        
        print(f"Filtered results: {len(filtered_tokens)} passed, {skipped_filters} failed filters, {skipped_no_timestamp} had no timestamp")
        print(f"Filter fail reasons: MC={filter_reasons['mc']}, Vol={filter_reasons['volume']}, AgeMin={filter_reasons['age_min']}, AgeMax={filter_reasons['age_max']}, Liq={filter_reasons['liquidity']}, Holders={filter_reasons['holders']}")
        if filtered_tokens:
            sample = filtered_tokens[0]
            print(f"Sample filtered token: {sample.get('symbol')} - MC: {sample.get('mc')}, Holders: {sample.get('holders')}, Age: {format_age(sample.get('createdAt', 0))}")
        
        if not filtered_tokens:
            keyboard = [[InlineKeyboardButton("« Back", callback_data="back_main")]]
            filter_summary = f"MC: {format_number(filters['min_mc'])}+\n" if filters['min_mc'] > 0 else ""
            filter_summary += f"Holders: {filters['min_holders']:,}+\n" if filters['min_holders'] > 0 else ""
            filter_summary += f"Liq: {format_number(filters['min_liquidity'])}+\n" if filters['min_liquidity'] > 0 else ""
            filter_summary += f"Vol: {format_number(filters['min_volume'])}+\n" if filters['min_volume'] > 0 else ""
            
            await query.edit_message_text(
                f"😔 No tokens match your filters.\n\n{filter_summary if filter_summary else 'Try adjusting your criteria.'}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Display results (top 10)
        result_text = f"🎯 *Found {len(filtered_tokens)} tokens*\n\n"
        
        for i, token in enumerate(filtered_tokens[:10], 1):
            try:
                name = str(token.get('name', 'Unknown'))[:30]  # Limit name length
                symbol = str(token.get('symbol', '?'))[:10]  # Limit symbol length
                address = str(token.get('address', ''))
                mc = float(token.get('mc', 0) or 0)
                volume = float(token.get('v24hUSD', 0) or 0)
                liquidity = float(token.get('liquidity', 0) or 0)
                created_at = int(token.get('createdAt', 0) or 0)
                holders = int(token.get('holders', 0) or 0)
                
                age = format_age(created_at) if created_at else 'N/A'
                
                # Display token without buy button
                result_text += f"*{i}. {name}* (${symbol})\n"
                result_text += f"📍 `{address}`\n"
                
                result_text += f"💰 MC: {format_number(mc)} | 📊 Vol: {format_number(volume)}\n"
                result_text += f"💧 Liq: {format_number(liquidity)} | ⏰ {age}"
                if holders > 0:
                    result_text += f" | 👥 {holders:,}\n\n"
                else:
                    result_text += f"\n\n"
            except Exception as e:
                print(f"Error formatting token {i}: {e}")
                continue
        
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

async def start_custom_mc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom market cap input"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💰 *Custom Market Cap Filter*\n\n"
        "Enter your custom market cap filter:\n\n"
        "Examples:\n"
        "• `>100k` - Greater than $100K\n"
        "• `<1m` - Less than $1M\n"
        "• `500k-2m` - Between $500K and $2M\n"
        "• `50000` - Minimum $50,000\n\n"
        "Type your value or /cancel to go back:",
        parse_mode='Markdown'
    )
    return WAITING_CUSTOM_MC

async def start_custom_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom volume input"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📊 *Custom Volume Filter*\n\n"
        "Enter your custom 24h volume filter:\n\n"
        "Examples:\n"
        "• `>50k` - Greater than $50K\n"
        "• `<100k` - Less than $100K\n"
        "• `10k` - Minimum $10K\n\n"
        "Type your value or /cancel to go back:",
        parse_mode='Markdown'
    )
    return WAITING_CUSTOM_VOLUME

async def start_custom_min_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom minimum age input"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⏰ *Custom Minimum Age Filter*\n\n"
        "Enter minimum token age:\n\n"
        "Examples:\n"
        "• `5m` - At least 5 minutes old\n"
        "• `2h` - At least 2 hours old\n"
        "• `1d` - At least 1 day old\n"
        "• `>30m` - Greater than 30 minutes\n"
        "• `0` - No minimum\n\n"
        "Supported units: m (minutes), h (hours), d (days)\n"
        "Type your value or /cancel to go back:",
        parse_mode='Markdown'
    )
    return WAITING_CUSTOM_MIN_AGE

async def start_custom_max_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom maximum age input"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⏱️ *Custom Maximum Age Filter*\n\n"
        "Enter maximum token age:\n\n"
        "Examples:\n"
        "• `30m` - Maximum 30 minutes old\n"
        "• `2h` - Maximum 2 hours old\n"
        "• `<1d` - Less than 1 day old\n"
        "• `0` - No maximum\n\n"
        "Supported units: m (minutes), h (hours), d (days)\n"
        "Type your value or /cancel to go back:",
        parse_mode='Markdown'
    )
    return WAITING_CUSTOM_MAX_AGE

async def start_custom_liquidity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom liquidity input"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💧 *Custom Liquidity Filter*\n\n"
        "Enter your custom minimum liquidity:\n\n"
        "Examples:\n"
        "• `>25k` - Greater than $25K\n"
        "• `<200k` - Less than $200K\n"
        "• `50k` - Minimum $50K\n\n"
        "Type your value or /cancel to go back:",
        parse_mode='Markdown'
    )
    return WAITING_CUSTOM_LIQUIDITY

async def start_custom_holders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom holders input"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "👥 *Custom Holders Filter*\n\n"
        "Enter your custom minimum holder count:\n\n"
        "Examples:\n"
        "• `>100` - Greater than 100 holders\n"
        "• `<5000` - Less than 5000 holders\n"
        "• `250` - Minimum 250 holders\n\n"
        "Type your value or /cancel to go back:",
        parse_mode='Markdown'
    )
    return WAITING_CUSTOM_HOLDERS

async def receive_custom_mc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process custom market cap"""
    user_id = update.effective_user.id
    init_user_filters(user_id)
    text = update.message.text
    
    parsed = parse_custom_filter(text, 'mc')
    if 'min' in parsed:
        user_filters[user_id]['min_mc'] = parsed['min']
    if 'max' in parsed:
        user_filters[user_id]['max_mc'] = parsed['max']
    
    await update.message.reply_text("✅ Market cap filter updated!")
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
        [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
        [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
    ]
    await update.message.reply_text(
        "🚀 *Solana Memecoin Tracker*\n\nWhat would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def receive_custom_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process custom volume"""
    user_id = update.effective_user.id
    init_user_filters(user_id)
    text = update.message.text
    
    parsed = parse_custom_filter(text, 'volume')
    if 'min' in parsed:
        user_filters[user_id]['min_volume'] = parsed['min']
    
    await update.message.reply_text("✅ Volume filter updated!")
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
        [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
        [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
    ]
    await update.message.reply_text(
        "🚀 *Solana Memecoin Tracker*\n\nWhat would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def receive_custom_min_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process custom minimum age"""
    user_id = update.effective_user.id
    init_user_filters(user_id)
    text = update.message.text
    
    parsed = parse_custom_filter(text, 'age')
    if 'min' in parsed:
        user_filters[user_id]['min_age_minutes'] = parsed['min']
    
    await update.message.reply_text("✅ Minimum age filter updated!")
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
        [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
        [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
    ]
    await update.message.reply_text(
        "🚀 *Solana Memecoin Tracker*\n\nWhat would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def receive_custom_max_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process custom maximum age"""
    user_id = update.effective_user.id
    init_user_filters(user_id)
    text = update.message.text
    
    parsed = parse_custom_filter(text, 'age')
    if 'max' in parsed:
        user_filters[user_id]['max_age_minutes'] = parsed['max']
    elif 'min' in parsed:
        user_filters[user_id]['max_age_minutes'] = parsed['min']
    
    await update.message.reply_text("✅ Maximum age filter updated!")
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
        [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
        [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
    ]
    await update.message.reply_text(
        "🚀 *Solana Memecoin Tracker*\n\nWhat would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def receive_custom_liquidity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process custom liquidity"""
    user_id = update.effective_user.id
    init_user_filters(user_id)
    text = update.message.text
    
    parsed = parse_custom_filter(text, 'liquidity')
    if 'min' in parsed:
        user_filters[user_id]['min_liquidity'] = parsed['min']
    
    await update.message.reply_text("✅ Liquidity filter updated!")
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
        [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
        [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
    ]
    await update.message.reply_text(
        "🚀 *Solana Memecoin Tracker*\n\nWhat would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def receive_custom_holders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process custom holders"""
    user_id = update.effective_user.id
    init_user_filters(user_id)
    text = update.message.text
    
    parsed = parse_custom_filter(text, 'holders')
    if 'min' in parsed:
        user_filters[user_id]['min_holders'] = int(parsed['min'])
    
    await update.message.reply_text("✅ Holders filter updated!")
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
        [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
        [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
    ]
    await update.message.reply_text(
        "🚀 *Solana Memecoin Tracker*\n\nWhat would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def cancel_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel custom input"""
    keyboard = [
        [InlineKeyboardButton("🔍 Search Tokens", callback_data="search")],
        [InlineKeyboardButton("⚙️ Set Filters", callback_data="filters")],
        [InlineKeyboardButton("📊 Current Filters", callback_data="show_filters")]
    ]
    await update.message.reply_text(
        "❌ Cancelled.\n\n🚀 *Solana Memecoin Tracker*\n\nWhat would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

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
    
    # Minimum age filters (in minutes)
    elif data == "min_age_0m":
        user_filters[user_id]['min_age_minutes'] = 0
    elif data == "min_age_5m":
        user_filters[user_id]['min_age_minutes'] = 5
    elif data == "min_age_30m":
        user_filters[user_id]['min_age_minutes'] = 30
    elif data == "min_age_1h":
        user_filters[user_id]['min_age_minutes'] = 60
    elif data == "min_age_6h":
        user_filters[user_id]['min_age_minutes'] = 360
    elif data == "min_age_24h":
        user_filters[user_id]['min_age_minutes'] = 1440
    
    # Maximum age filters (in minutes)
    elif data == "max_age_10m":
        user_filters[user_id]['max_age_minutes'] = 10
    elif data == "max_age_30m":
        user_filters[user_id]['max_age_minutes'] = 30
    elif data == "max_age_1h":
        user_filters[user_id]['max_age_minutes'] = 60
    elif data == "max_age_6h":
        user_filters[user_id]['max_age_minutes'] = 360
    elif data == "max_age_24h":
        user_filters[user_id]['max_age_minutes'] = 1440
    elif data == "max_age_7d":
        user_filters[user_id]['max_age_minutes'] = 10080
    elif data == "max_age_any":
        user_filters[user_id]['max_age_minutes'] = float('inf')
    
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
    
    # Holder filters
    elif data == "holders_0":
        user_filters[user_id]['min_holders'] = 0
    elif data == "holders_10":
        user_filters[user_id]['min_holders'] = 10
    elif data == "holders_50":
        user_filters[user_id]['min_holders'] = 50
    elif data == "holders_100":
        user_filters[user_id]['min_holders'] = 100
    elif data == "holders_500":
        user_filters[user_id]['min_holders'] = 500
    elif data == "holders_1000":
        user_filters[user_id]['min_holders'] = 1000
    
    # Reset filters
    elif data == "reset_filters":
        user_filters[user_id] = {
            'min_mc': 0,
            'max_mc': float('inf'),
            'min_volume': 0,
            'min_age_minutes': 0,
            'max_age_minutes': 10080,  # 7 days in minutes
            'min_liquidity': 0,
            'min_holders': 0
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
    elif data == "filter_min_age":
        await filter_min_age_menu(update, context)
    elif data == "filter_max_age":
        await filter_max_age_menu(update, context)
    elif data == "filter_liquidity":
        await filter_liquidity_menu(update, context)
    elif data == "filter_holders":
        await filter_holders_menu(update, context)
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
    
    # Create conversation handlers for custom filters
    conv_handler_mc = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_custom_mc, pattern="^mc_custom$")],
        states={
            WAITING_CUSTOM_MC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_mc)]
        },
        fallbacks=[CommandHandler("cancel", cancel_custom)]
    )
    
    conv_handler_volume = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_custom_volume, pattern="^vol_custom$")],
        states={
            WAITING_CUSTOM_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_volume)]
        },
        fallbacks=[CommandHandler("cancel", cancel_custom)]
    )
    
    conv_handler_min_age = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_custom_min_age, pattern="^min_age_custom$")],
        states={
            WAITING_CUSTOM_MIN_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_min_age)]
        },
        fallbacks=[CommandHandler("cancel", cancel_custom)]
    )
    
    conv_handler_max_age = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_custom_max_age, pattern="^max_age_custom$")],
        states={
            WAITING_CUSTOM_MAX_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_max_age)]
        },
        fallbacks=[CommandHandler("cancel", cancel_custom)]
    )
    
    conv_handler_liquidity = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_custom_liquidity, pattern="^liq_custom$")],
        states={
            WAITING_CUSTOM_LIQUIDITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_liquidity)]
        },
        fallbacks=[CommandHandler("cancel", cancel_custom)]
    )
    
    conv_handler_holders = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_custom_holders, pattern="^holders_custom$")],
        states={
            WAITING_CUSTOM_HOLDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_holders)]
        },
        fallbacks=[CommandHandler("cancel", cancel_custom)]
    )
    
    # Add handlers (order matters - conversation handlers first)
    application.add_handler(conv_handler_mc)
    application.add_handler(conv_handler_volume)
    application.add_handler(conv_handler_min_age)
    application.add_handler(conv_handler_max_age)
    application.add_handler(conv_handler_liquidity)
    application.add_handler(conv_handler_holders)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start bot
    print("🤖 Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

