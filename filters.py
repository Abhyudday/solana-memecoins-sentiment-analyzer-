"""Filter parsing utilities for memecoin search criteria."""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


class FilterParser:
    """Parser for user filter strings."""
    
    # Preset filters
    PRESETS = {
        "high_mc": {
            "name": "High MC (100k+)",
            "filters": {"mc_min": 100_000}
        },
        "high_vol": {
            "name": "High Vol (10k+)",
            "filters": {"volume_min": 10_000}
        },
        "active_users": {
            "name": "Active Users (100+ holders)",
            "filters": {"holders_min": 100}
        },
        "small_cap": {
            "name": "Small Cap (<1M MC)",
            "filters": {"mc_max": 1_000_000}
        },
        "mid_cap": {
            "name": "Mid Cap (1M-10M MC)",
            "filters": {"mc_min": 1_000_000, "mc_max": 10_000_000}
        },
        "high_liquidity": {
            "name": "High Liquidity (50k+)",
            "filters": {"liquidity_min": 50_000}
        }
    }
    
    def __init__(self):
        # Regex patterns for parsing custom filters
        self.patterns = {
            "mc": re.compile(r"(?:mc|market\s*cap|marketcap)\s*[><=]+\s*([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)", re.IGNORECASE),
            "volume": re.compile(r"(?:vol|volume)\s*[><=]+\s*([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)", re.IGNORECASE),
            "holders": re.compile(r"(?:holders?|users?)\s*[><=]+\s*([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)", re.IGNORECASE),
            "liquidity": re.compile(r"(?:liquidity|liq)\s*[><=]+\s*([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)", re.IGNORECASE),
        }
        
        # Operator patterns
        self.operator_patterns = {
            "mc": re.compile(r"(?:mc|market\s*cap|marketcap)\s*([><=]+)", re.IGNORECASE),
            "volume": re.compile(r"(?:vol|volume)\s*([><=]+)", re.IGNORECASE),
            "holders": re.compile(r"(?:holders?|users?)\s*([><=]+)", re.IGNORECASE),
            "liquidity": re.compile(r"(?:liquidity|liq)\s*([><=]+)", re.IGNORECASE),
        }
    
    def _parse_number_with_suffix(self, number_str: str, suffix: str) -> float:
        """Parse number with k/m/b suffix."""
        try:
            number = float(number_str)
            suffix = suffix.lower()
            
            if suffix == 'k':
                return number * 1_000
            elif suffix == 'm':
                return number * 1_000_000
            elif suffix == 'b':
                return number * 1_000_000_000
            else:
                return number
        except ValueError:
            return 0.0
    
    def _determine_operator_type(self, operator: str) -> str:
        """Determine if operator is min (>=, >) or max (<=, <)."""
        if operator in ['>', '>=']:
            return 'min'
        elif operator in ['<', '<=']:
            return 'max'
        else:
            return 'min'  # Default to min
    
    def parse_custom_filter(self, filter_string: str) -> Dict[str, Any]:
        """Parse custom filter string into filter dict."""
        filters = {}
        
        if not filter_string or not filter_string.strip():
            return filters
        
        try:
            # Normalize the string
            filter_string = filter_string.strip().lower()
            
            # Parse each filter type
            for filter_type, pattern in self.patterns.items():
                matches = pattern.findall(filter_string)
                
                for match in matches:
                    if len(match) >= 2:
                        number_str, suffix = match[0], match[1]
                        value = self._parse_number_with_suffix(number_str, suffix)
                        
                        # Determine operator type
                        operator_match = self.operator_patterns[filter_type].search(filter_string)
                        if operator_match:
                            operator = operator_match.group(1)
                            op_type = self._determine_operator_type(operator)
                            
                            key = f"{filter_type}_{op_type}"
                            filters[key] = value
                        else:
                            # Default to min
                            filters[f"{filter_type}_min"] = value
            
            logger.info(f"Parsed filters: {filters}")
            return filters
            
        except Exception as e:
            logger.error(f"Error parsing filter string '{filter_string}': {e}")
            return {}
    
    def parse_simple_format(self, filter_string: str) -> Dict[str, Any]:
        """Parse simple format like '100k mc, 10k volume, 100+ users'."""
        filters = {}
        
        if not filter_string or not filter_string.strip():
            return filters
        
        try:
            # Split by commas and parse each part
            parts = [part.strip() for part in filter_string.split(',')]
            
            for part in parts:
                part = part.lower()
                
                # Market cap patterns
                mc_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)\s*(?:mc|market\s*cap)', part)
                if mc_match:
                    value = self._parse_number_with_suffix(mc_match.group(1), mc_match.group(2))
                    filters['mc_min'] = value
                    continue
                
                # Volume patterns
                vol_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)\s*(?:vol|volume)', part)
                if vol_match:
                    value = self._parse_number_with_suffix(vol_match.group(1), vol_match.group(2))
                    filters['volume_min'] = value
                    continue
                
                # Holders/users patterns
                holders_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)\s*\+?\s*(?:holders?|users?)', part)
                if holders_match:
                    value = self._parse_number_with_suffix(holders_match.group(1), holders_match.group(2))
                    filters['holders_min'] = value
                    continue
                
                # Liquidity patterns
                liq_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)\s*(?:liq|liquidity)', part)
                if liq_match:
                    value = self._parse_number_with_suffix(liq_match.group(1), liq_match.group(2))
                    filters['liquidity_min'] = value
                    continue
            
            logger.info(f"Parsed simple format filters: {filters}")
            return filters
            
        except Exception as e:
            logger.error(f"Error parsing simple format '{filter_string}': {e}")
            return {}
    
    def get_preset_filter(self, preset_key: str) -> Dict[str, Any]:
        """Get preset filter by key."""
        preset = self.PRESETS.get(preset_key)
        if preset:
            return preset["filters"]
        return {}
    
    def get_preset_name(self, preset_key: str) -> str:
        """Get preset filter name by key."""
        preset = self.PRESETS.get(preset_key)
        if preset:
            return preset["name"]
        return "Unknown Preset"
    
    def list_presets(self) -> List[Tuple[str, str]]:
        """List all available presets as (key, name) tuples."""
        return [(key, preset["name"]) for key, preset in self.PRESETS.items()]
    
    def parse_filter(self, filter_input: str) -> Dict[str, Any]:
        """
        Main parsing function that tries different formats.
        
        Args:
            filter_input: User input string
            
        Returns:
            Dict with parsed filters
        """
        if not filter_input or not filter_input.strip():
            return {}
        
        filter_input = filter_input.strip()
        
        # Try preset first
        preset_key = filter_input.lower().replace(" ", "_").replace("-", "_")
        if preset_key in self.PRESETS:
            return self.get_preset_filter(preset_key)
        
        # Try simple format first (more user-friendly)
        simple_filters = self.parse_simple_format(filter_input)
        if simple_filters:
            return simple_filters
        
        # Fall back to custom format
        return self.parse_custom_filter(filter_input)
    
    def format_filters_display(self, filters: Dict[str, Any]) -> str:
        """Format filters for display to user."""
        if not filters:
            return "No filters applied"
        
        display_parts = []
        
        # Market Cap
        if 'mc_min' in filters:
            display_parts.append(f"MC ≥ ${self._format_number(filters['mc_min'])}")
        if 'mc_max' in filters:
            display_parts.append(f"MC ≤ ${self._format_number(filters['mc_max'])}")
        
        # Volume
        if 'volume_min' in filters:
            display_parts.append(f"Vol ≥ ${self._format_number(filters['volume_min'])}")
        if 'volume_max' in filters:
            display_parts.append(f"Vol ≤ ${self._format_number(filters['volume_max'])}")
        
        # Holders
        if 'holders_min' in filters:
            display_parts.append(f"Holders ≥ {int(filters['holders_min'])}")
        if 'holders_max' in filters:
            display_parts.append(f"Holders ≤ {int(filters['holders_max'])}")
        
        # Liquidity
        if 'liquidity_min' in filters:
            display_parts.append(f"Liquidity ≥ ${self._format_number(filters['liquidity_min'])}")
        if 'liquidity_max' in filters:
            display_parts.append(f"Liquidity ≤ ${self._format_number(filters['liquidity_max'])}")
        
        return " | ".join(display_parts)
    
    def _format_number(self, number: float) -> str:
        """Format number with appropriate suffix."""
        if number >= 1_000_000_000:
            return f"{number/1_000_000_000:.1f}B"
        elif number >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number/1_000:.1f}K"
        else:
            return f"{int(number)}"


# Global parser instance
filter_parser = FilterParser()


def parse_filter(filter_input: str) -> Dict[str, Any]:
    """Convenience function to parse filters."""
    return filter_parser.parse_filter(filter_input)


def get_preset_filters() -> List[Tuple[str, str]]:
    """Get list of preset filters."""
    return filter_parser.list_presets()


def format_filters_display(filters: Dict[str, Any]) -> str:
    """Format filters for display."""
    return filter_parser.format_filters_display(filters)


# Test the parser
if __name__ == "__main__":
    parser = FilterParser()
    
    # Test cases
    test_cases = [
        "100k mc, 10k volume, 100+ users",
        "mc > 1m, vol > 50k",
        "high_mc",
        "market cap >= 500000, volume >= 25000, holders >= 200",
        "1m mc, 100k vol, 500 liq"
    ]
    
    for test in test_cases:
        result = parser.parse_filter(test)
        display = parser.format_filters_display(result)
        print(f"Input: '{test}'")
        print(f"Parsed: {result}")
        print(f"Display: {display}")
        print("---")
