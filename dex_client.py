"""DexScreener API client for fetching Solana memecoin data."""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

logger = logging.getLogger(__name__)


class PairInfo(BaseModel):
    """Model for DexScreener pair information."""
    chainId: str
    dexId: str
    url: str
    pairAddress: str
    baseToken: Dict[str, Any]
    quoteToken: Dict[str, Any]
    priceNative: Optional[str] = None
    priceUsd: Optional[str] = None
    volume: Optional[Dict[str, Any]] = None
    priceChange: Optional[Dict[str, Any]] = None
    liquidity: Optional[Dict[str, Any]] = None
    fdv: Optional[float] = None
    marketCap: Optional[float] = None
    info: Optional[Dict[str, Any]] = None


class DexScreenerResponse(BaseModel):
    """Model for DexScreener API response."""
    schemaVersion: str
    pairs: Optional[List[PairInfo]] = None


class DexScreenerClient:
    """Async client for DexScreener API."""
    
    BASE_URL = "https://api.dexscreener.com"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_delay = 1.0  # 1 second between requests
        self._last_request_time = 0.0
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a rate-limited request to DexScreener API."""
        if not self.session:
            raise RuntimeError("Client session not initialized. Use async with.")
        
        # Rate limiting
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as response:
                self._last_request_time = asyncio.get_event_loop().time()
                
                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 429:
                    logger.warning("Rate limited by DexScreener API")
                    await asyncio.sleep(5)  # Wait 5 seconds before retrying
                    return await self._make_request(endpoint, params)
                else:
                    logger.error(f"DexScreener API error: {response.status}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error making request to DexScreener: {e}")
            return {}
    
    async def search_pairs(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search for pairs by query."""
        endpoint = f"/latest/dex/search/"
        params = {"q": query}
        
        data = await self._make_request(endpoint, params)
        pairs = data.get("pairs", [])
        
        # Filter for Solana pairs only
        solana_pairs = [
            pair for pair in pairs 
            if pair.get("chainId") == "solana" and 
            pair.get("dexId") in ["raydium", "orca", "serum"]
        ]
        
        return solana_pairs[:limit]
    
    async def get_pair_by_address(self, address: str) -> Optional[Dict[str, Any]]:
        """Get pair details by address."""
        endpoint = f"/latest/dex/pairs/solana/{address}"
        
        data = await self._make_request(endpoint)
        pairs = data.get("pairs", [])
        
        return pairs[0] if pairs else None
    
    async def get_trending_pairs(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get comprehensive list of Solana pairs including trending and new."""
        all_pairs = []
        
        # Try boosted tokens first
        try:
            endpoint = "/token-boosts/top/v1"
            data = await self._make_request(endpoint)
            boosted_tokens = data if isinstance(data, list) else []
            
            for token_data in boosted_tokens[:50]:
                if token_data.get("chainId") == "solana":
                    token_address = token_data.get("tokenAddress")
                    if token_address:
                        pair_data = await self.get_pair_by_address(token_address)
                        if pair_data:
                            all_pairs.append(pair_data)
                        await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Error fetching boosted tokens: {e}")
        
        # Comprehensive search with various terms to get more coverage
        logger.info("Using comprehensive search method")
        search_terms = [
            "solana", "pump", "bonk", "dogwifhat", "pepe", "meme", "coin",
            "inu", "shiba", "doge", "elon", "moon", "rocket", "chad", "wojak",
            "token", "sol", "based", "trump", "biden", "cat", "dog", "frog"
        ]
        
        for term in search_terms:
            try:
                pairs = await self.search_pairs(term, limit=30)
                for pair in pairs:
                    fdv = pair.get("fdv", 0)
                    volume_24h = pair.get("volume", {}).get("h24", 0) if pair.get("volume") else 0
                    liquidity_usd = pair.get("liquidity", {}).get("usd", 0) if pair.get("liquidity") else 0
                    
                    base_token = pair.get("baseToken", {})
                    token_symbol = base_token.get("symbol", "").lower()
                    
                    # Skip well-known tokens
                    known_tokens = ["sol", "usdc", "usdt", "btc", "eth", "ray", "orca", "serum", "wsol"]
                    if any(known == token_symbol for known in known_tokens):
                        continue
                    
                    # Very inclusive filter: 1K - 1B market cap, some volume
                    if (1_000 <= fdv <= 1_000_000_000 and volume_24h >= 0):
                        all_pairs.append(pair)
                
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Error searching pairs for term {term}: {e}")
                continue
        
        # Remove duplicates based on token address
        seen_addresses = set()
        unique_pairs = []
        for pair in all_pairs:
            address = pair.get("baseToken", {}).get("address")
            if address and address not in seen_addresses:
                seen_addresses.add(address)
                unique_pairs.append(pair)
        
        return unique_pairs[:limit]
    
    def _parse_pair_data(self, pair_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse pair data into a standardized format."""
        base_token = pair_data.get("baseToken", {})
        volume_data = pair_data.get("volume", {})
        liquidity_data = pair_data.get("liquidity", {})
        price_change = pair_data.get("priceChange", {})
        
        # Estimate holders based on liquidity and volume (rough approximation)
        liquidity_usd = liquidity_data.get("usd", 0) if liquidity_data else 0
        volume_24h = volume_data.get("h24", 0) if volume_data else 0
        holders_estimate = max(10, int((liquidity_usd / 1000) + (volume_24h / 10000)))
        
        return {
            "ca": base_token.get("address", ""),
            "name": base_token.get("name", "Unknown"),
            "symbol": base_token.get("symbol", "???"),
            "mc": pair_data.get("fdv", 0),
            "volume_24h": volume_24h,
            "liquidity": liquidity_usd,
            "holders_estimate": holders_estimate,
            "price_usd": float(pair_data.get("priceUsd", 0)) if pair_data.get("priceUsd") else 0,
            "price_change_24h": price_change.get("h24", 0) if price_change else 0,
            "dex_url": pair_data.get("url", ""),
            "pair_address": pair_data.get("pairAddress", ""),
            "dex_id": pair_data.get("dexId", ""),
        }
    
    async def search_memecoins(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for memecoins based on filters - returns ALL matching tokens."""
        # Get comprehensive pairs
        pairs = await self.get_trending_pairs(200)
        
        filtered_pairs = []
        for pair in pairs:
            parsed_data = self._parse_pair_data(pair)
            
            # Apply filters
            if filters.get("mc_min", 0) and parsed_data["mc"] < filters["mc_min"]:
                continue
            if filters.get("mc_max") and parsed_data["mc"] > filters["mc_max"]:
                continue
            if filters.get("volume_min", 0) and parsed_data["volume_24h"] < filters["volume_min"]:
                continue
            if filters.get("volume_max") and parsed_data["volume_24h"] > filters["volume_max"]:
                continue
            if filters.get("holders_min", 0) and parsed_data["holders_estimate"] < filters["holders_min"]:
                continue
            if filters.get("liquidity_min", 0) and parsed_data["liquidity"] < filters["liquidity_min"]:
                continue
            
            filtered_pairs.append(parsed_data)
        
        # Sort by activity indicators (newest/most active first)
        # Use multiple factors: volume, price change, liquidity
        # Higher recent activity = likely newer or trending token
        filtered_pairs.sort(
            key=lambda x: (
                x["volume_24h"] * (1 + abs(x["price_change_24h"])/100) * 
                (1 if x["liquidity"] > 10000 else 0.5)
            ), 
            reverse=True
        )
        
        # Return ALL matching tokens (not limited)
        return filtered_pairs
    
    async def get_token_info(self, ca: str) -> Optional[Dict[str, Any]]:
        """Get token information by contract address."""
        pair_data = await self.get_pair_by_address(ca)
        if not pair_data:
            return None
        
        return self._parse_pair_data(pair_data)


async def test_dex_client():
    """Test function for the DexScreener client."""
    async with DexScreenerClient() as client:
        # Test search
        results = await client.search_pairs("pepe")
        print(f"Found {len(results)} pairs for 'pepe'")
        
        # Test trending
        trending = await client.get_trending_pairs(10)
        print(f"Found {len(trending)} trending pairs")
        
        # Test filters
        filters = {"mc_min": 100000, "volume_min": 10000}
        filtered = await client.search_memecoins(filters)
        print(f"Found {len(filtered)} memecoins matching filters")


if __name__ == "__main__":
    asyncio.run(test_dex_client())
