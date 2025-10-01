"""Telegram inline keyboard utilities for the memecoin bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class KeyboardBuilder:
    """Builder class for Telegram inline keyboards."""
    
    def __init__(self):
        self.buttons: List[List[InlineKeyboardButton]] = []
    
    def add_button(self, text: str, callback_data: str, url: Optional[str] = None) -> 'KeyboardBuilder':
        """Add a button to a new row."""
        if url:
            button = InlineKeyboardButton(text, url=url)
        else:
            button = InlineKeyboardButton(text, callback_data=callback_data)
        self.buttons.append([button])
        return self
    
    def add_row(self, buttons: List[tuple]) -> 'KeyboardBuilder':
        """Add a row of buttons. Each tuple is (text, callback_data) or (text, callback_data, url)."""
        row = []
        for button_data in buttons:
            if len(button_data) == 3:
                text, callback_data, url = button_data
                button = InlineKeyboardButton(text, url=url)
            else:
                text, callback_data = button_data
                button = InlineKeyboardButton(text, callback_data=callback_data)
            row.append(button)
        self.buttons.append(row)
        return self
    
    def build(self) -> InlineKeyboardMarkup:
        """Build the keyboard markup."""
        return InlineKeyboardMarkup(self.buttons)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get the main menu keyboard."""
    return (KeyboardBuilder()
            .add_button("🔍 Memecoin Filters", "menu_filters")
            .add_button("📊 Sentiment Analyzer", "menu_sentiment")
            .add_button("ℹ️ Help", "menu_help")
            .build())


def get_filters_menu_keyboard() -> InlineKeyboardMarkup:
    """Get the filters menu keyboard."""
    return (KeyboardBuilder()
            .add_button("🚀 High MC (100k+)", "filter_high_mc")
            .add_button("📈 High Vol (10k+)", "filter_high_vol")
            .add_button("👥 Active Users (100+ holders)", "filter_active_users")
            .add_button("💎 Small Cap (<1M MC)", "filter_small_cap")
            .add_button("🏆 Mid Cap (1M-10M MC)", "filter_mid_cap")
            .add_button("💧 High Liquidity (50k+)", "filter_high_liquidity")
            .add_button("⚙️ Custom Filter", "filter_custom")
            .add_button("🔙 Back to Main Menu", "menu_main")
            .build())


def get_sentiment_menu_keyboard() -> InlineKeyboardMarkup:
    """Get the sentiment analyzer menu keyboard."""
    return (KeyboardBuilder()
            .add_button("🔍 Analyze Token Sentiment", "sentiment_analyze")
            .add_button("ℹ️ How it Works", "sentiment_help")
            .add_button("🔙 Back to Main Menu", "menu_main")
            .build())


def get_memecoin_results_keyboard(memecoins: List[Dict[str, Any]], page: int = 0, 
                                total_pages: int = 1) -> InlineKeyboardMarkup:
    """Get keyboard for memecoin results with pagination."""
    builder = KeyboardBuilder()
    
    # Add individual memecoin buttons (show details)
    for i, memecoin in enumerate(memecoins):
        symbol = memecoin.get('symbol', '???')
        mc = memecoin.get('mc', 0)
        mc_formatted = format_number(mc)
        
        button_text = f"📊 {symbol} (${mc_formatted})"
        callback_data = f"memecoin_details_{memecoin.get('ca', '')}"
        
        builder.add_button(button_text, callback_data)
    
    # Add pagination if needed
    if total_pages > 1:
        pagination_buttons = []
        
        if page > 0:
            pagination_buttons.append(("⬅️ Previous", f"page_{page-1}"))
        
        pagination_buttons.append((f"Page {page+1}/{total_pages}", "noop"))
        
        if page < total_pages - 1:
            pagination_buttons.append(("➡️ Next", f"page_{page+1}"))
        
        builder.add_row(pagination_buttons)
    
    # Add back button
    builder.add_button("🔙 Back to Filters", "menu_filters")
    
    return builder.build()


def get_memecoin_details_keyboard(memecoin: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Get keyboard for individual memecoin details."""
    builder = KeyboardBuilder()
    
    # Add DexScreener link
    dex_url = memecoin.get('dex_url', '')
    if dex_url:
        builder.add_button("📈 View on DexScreener", "noop", dex_url)
    
    # Add sentiment analysis button
    ca = memecoin.get('ca', '')
    if ca:
        builder.add_button("🧠 Analyze Sentiment", f"sentiment_token_{ca}")
    
    # Add copy CA button
    if ca:
        builder.add_button("📋 Copy Contract Address", f"copy_ca_{ca}")
    
    # Add back button
    builder.add_button("🔙 Back to Results", "back_to_results")
    
    return builder.build()


def get_sentiment_result_keyboard(ca: str, has_dex_data: bool = False) -> InlineKeyboardMarkup:
    """Get keyboard for sentiment analysis results."""
    builder = KeyboardBuilder()
    
    # Add view token details if we have DexScreener data
    if has_dex_data:
        builder.add_button("📊 View Token Details", f"memecoin_details_{ca}")
    
    # Add analyze again button
    builder.add_button("🔄 Analyze Again", f"sentiment_token_{ca}")
    
    # Add copy CA button
    builder.add_button("📋 Copy Contract Address", f"copy_ca_{ca}")
    
    # Add back button
    builder.add_button("🔙 Back to Sentiment Menu", "menu_sentiment")
    
    return builder.build()


def get_help_keyboard() -> InlineKeyboardMarkup:
    """Get help menu keyboard."""
    return (KeyboardBuilder()
            .add_button("🔍 Filter Help", "help_filters")
            .add_button("📊 Sentiment Help", "help_sentiment")
            .add_button("🤖 About Bot", "help_about")
            .add_button("🔙 Back to Main Menu", "menu_main")
            .build())


def get_confirmation_keyboard(action: str, data: str = "") -> InlineKeyboardMarkup:
    """Get confirmation keyboard for actions."""
    return (KeyboardBuilder()
            .add_row([
                ("✅ Yes", f"confirm_{action}_{data}"),
                ("❌ No", f"cancel_{action}")
            ])
            .build())


def get_pagination_keyboard(current_page: int, total_pages: int, 
                          base_callback: str) -> InlineKeyboardMarkup:
    """Get pagination keyboard."""
    builder = KeyboardBuilder()
    
    if total_pages <= 1:
        return builder.build()
    
    buttons = []
    
    # Previous button
    if current_page > 0:
        buttons.append(("⬅️", f"{base_callback}_page_{current_page-1}"))
    
    # Page indicator
    buttons.append((f"{current_page+1}/{total_pages}", "noop"))
    
    # Next button
    if current_page < total_pages - 1:
        buttons.append(("➡️", f"{base_callback}_page_{current_page+1}"))
    
    if buttons:
        builder.add_row(buttons)
    
    return builder.build()


def get_back_button_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """Get a simple back button keyboard."""
    return (KeyboardBuilder()
            .add_button("🔙 Back", callback_data)
            .build())


def format_number(number: float) -> str:
    """Format number with appropriate suffix for display."""
    if number >= 1_000_000_000:
        return f"{number/1_000_000_000:.1f}B"
    elif number >= 1_000_000:
        return f"{number/1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number/1_000:.1f}K"
    else:
        return f"{int(number)}"


def truncate_text(text: str, max_length: int = 30) -> str:
    """Truncate text for button display."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


# Callback data constants
class CallbackData:
    """Constants for callback data."""
    
    # Main menu
    MENU_MAIN = "menu_main"
    MENU_FILTERS = "menu_filters"
    MENU_SENTIMENT = "menu_sentiment"
    MENU_HELP = "menu_help"
    
    # Filters
    FILTER_HIGH_MC = "filter_high_mc"
    FILTER_HIGH_VOL = "filter_high_vol"
    FILTER_ACTIVE_USERS = "filter_active_users"
    FILTER_SMALL_CAP = "filter_small_cap"
    FILTER_MID_CAP = "filter_mid_cap"
    FILTER_HIGH_LIQUIDITY = "filter_high_liquidity"
    FILTER_CUSTOM = "filter_custom"
    
    # Sentiment
    SENTIMENT_ANALYZE = "sentiment_analyze"
    SENTIMENT_HELP = "sentiment_help"
    
    # Help
    HELP_FILTERS = "help_filters"
    HELP_SENTIMENT = "help_sentiment"
    HELP_ABOUT = "help_about"
    
    # Actions
    NOOP = "noop"
    BACK_TO_RESULTS = "back_to_results"


# Test the keyboards
if __name__ == "__main__":
    # Test main menu
    main_kb = get_main_menu_keyboard()
    print("Main menu keyboard created successfully")
    
    # Test filters menu
    filters_kb = get_filters_menu_keyboard()
    print("Filters menu keyboard created successfully")
    
    # Test with sample memecoin data
    sample_memecoins = [
        {"symbol": "PEPE", "mc": 150000, "ca": "test_ca_1"},
        {"symbol": "DOGE", "mc": 2500000, "ca": "test_ca_2"},
    ]
    
    results_kb = get_memecoin_results_keyboard(sample_memecoins)
    print("Results keyboard created successfully")
