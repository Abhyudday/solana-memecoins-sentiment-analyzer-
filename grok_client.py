"""xAI Grok API client for sentiment analysis."""

import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class GrokClient:
    """Client for xAI Grok API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _create_sentiment_prompt(self, ca: str, token_name: str, tweets_text: str) -> str:
        """Create a prompt for sentiment analysis."""
        prompt = f"""Analyze these REAL-TIME tweets for bullish/bearish sentiment on this Solana memecoin.

Contract Address: {ca}
Token Name: {token_name}

Recent Tweets to analyze:
{tweets_text}

Instructions:
1. Determine overall sentiment: "Bullish", "Bearish", or "Neutral"
2. Provide a concise explanation in 3-4 lines covering:
   - Overall market sentiment
   - Key signals from the tweets
   - Community mood and activity level
3. Consider factors like: price predictions, buying/selling sentiment, community excitement, fear/greed indicators

Respond in this exact format:
SENTIMENT: [Bullish/Bearish/Neutral]
EXPLANATION: [Your 3-4 line explanation]"""

        return prompt
    
    async def search_and_analyze_sentiment(self, ca: str, token_name: str) -> Tuple[str, str, int]:
        """
        Search web for tweets and analyze sentiment using Grok web search.
        
        Returns:
            Tuple of (sentiment, explanation, tweet_count)
        """
        if not self.session:
            raise RuntimeError("Client session not initialized. Use async with.")
        
        prompt = f"""You MUST search Twitter RIGHT NOW for live tweets about the Solana token "${token_name}" (contract: {ca[:15]}...).

CRITICAL INSTRUCTIONS:
1. Use web search to find REAL CURRENT tweets from Twitter about this token
2. Search for: "twitter.com {token_name} solana", "twitter.com ${token_name}", "{token_name} crypto"
3. Look for tweets from the LAST 24-48 HOURS ONLY
4. DO NOT use cached data - search live Twitter RIGHT NOW

After finding and analyzing ACTUAL RECENT tweets, determine the sentiment:

BULLISH signals:
- People talking about buying, accumulating, holding
- Moon/rocket emojis and positive price predictions
- Excitement about partnerships, listings, or news
- "This will 10x", "undervalued", "gem" type comments
- High engagement and growing community buzz

BEARISH signals:
- People selling, worried about dumps
- FUD, scam accusations, rug pull concerns
- Price crash discussions, loss posts
- Low volume complaints, dead project comments
- Negative sentiment and fear

NEUTRAL signals:
- Mixed opinions, some bullish some bearish
- Low activity or very few tweets
- Just informational posts with no clear sentiment

Based on the LIVE tweets you find RIGHT NOW, respond in this EXACT format:

SENTIMENT: [Bullish/Bearish/Neutral]
EXPLANATION: [Write 3-4 sentences explaining what you found in the actual live tweets - mention specific sentiment patterns, price discussions, community mood, and activity level]
TWEET_COUNT: [Number of relevant tweets you analyzed]

IMPORTANT: Your analysis MUST be based on ACTUAL CURRENT tweets you find via web search, not assumptions or old data."""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a crypto sentiment analyst with LIVE web search access. You MUST search Twitter in real-time for current tweets and analyze actual recent discussions. Always use web search to find the latest information. Never use cached data or make assumptions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "grok-beta",
            "stream": False,
            "temperature": 0.4,
            "max_tokens": 1200,
            "web_search": True
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    sentiment, explanation, tweet_count = self._parse_sentiment_with_count(content)
                    return sentiment, explanation, tweet_count
                
                elif response.status == 429:
                    logger.warning("Grok API rate limit exceeded")
                    return "neutral", "Rate limit exceeded - try again later", 0
                
                elif response.status == 401:
                    logger.error("Grok API unauthorized - check API key")
                    return "neutral", "API authentication failed", 0
                
                else:
                    logger.error(f"Grok API error: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Error details: {error_text}")
                    return "neutral", "API error occurred", 0
                    
        except asyncio.TimeoutError:
            logger.error("Grok API request timeout")
            return "neutral", "Request timeout - try again", 0
        
        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return "neutral", "Analysis unavailable due to technical error", 0
    
    async def analyze_sentiment(self, ca: str, token_name: str, tweets_text: str) -> Tuple[str, str]:
        """
        Analyze sentiment of tweets (legacy method for compatibility).
        
        Returns:
            Tuple of (sentiment, explanation)
        """
        if not self.session:
            raise RuntimeError("Client session not initialized. Use async with.")
        
        if not tweets_text.strip():
            return "neutral", "No tweets available for analysis"
        
        prompt = self._create_sentiment_prompt(ca, token_name, tweets_text)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a financial sentiment analyst specializing in cryptocurrency and memecoins. Provide accurate, unbiased sentiment analysis based on social media content."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "grok-3",
            "stream": False,
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    return self._parse_sentiment_response(content)
                
                elif response.status == 429:
                    logger.warning("Grok API rate limit exceeded")
                    return "neutral", "Rate limit exceeded - try again later"
                
                elif response.status == 401:
                    logger.error("Grok API unauthorized - check API key")
                    return "neutral", "API authentication failed"
                
                else:
                    logger.error(f"Grok API error: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Error details: {error_text}")
                    return "neutral", "API error occurred"
                    
        except asyncio.TimeoutError:
            logger.error("Grok API request timeout")
            return "neutral", "Request timeout - try again"
        
        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return "neutral", "Analysis unavailable due to technical error"
    
    def _parse_sentiment_with_count(self, content: str) -> Tuple[str, str, int]:
        """Parse sentiment response with tweet count."""
        sentiment = "neutral"
        explanation = "Unable to determine sentiment"
        tweet_count = 0
        
        try:
            lines = content.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                
                if line.startswith("SENTIMENT:"):
                    sentiment_raw = line.replace("SENTIMENT:", "").strip().lower()
                    if "bullish" in sentiment_raw:
                        sentiment = "bullish"
                    elif "bearish" in sentiment_raw:
                        sentiment = "bearish"
                    else:
                        sentiment = "neutral"
                
                elif line.startswith("EXPLANATION:"):
                    explanation = line.replace("EXPLANATION:", "").strip()
                    # Get remaining lines for multi-line explanation
                    idx = lines.index(line)
                    remaining = []
                    for next_line in lines[idx+1:]:
                        if next_line.strip().startswith("TWEET_COUNT:"):
                            break
                        if next_line.strip():
                            remaining.append(next_line.strip())
                    if remaining:
                        explanation += " " + " ".join(remaining)
                    if not explanation or explanation == "EXPLANATION:":
                        explanation = "No explanation provided"
                
                elif line.startswith("TWEET_COUNT:"):
                    count_str = line.replace("TWEET_COUNT:", "").strip()
                    # Extract number from string
                    import re
                    numbers = re.findall(r'\d+', count_str)
                    if numbers:
                        tweet_count = int(numbers[0])
            
            # Fallback parsing if format is different
            if sentiment == "neutral" and explanation == "Unable to determine sentiment":
                content_lower = content.lower()
                if "bullish" in content_lower:
                    sentiment = "bullish"
                elif "bearish" in content_lower:
                    sentiment = "bearish"
                
                # Extract explanation from content
                sentences = content.split('.')
                if sentences:
                    explanation = '. '.join(sentences[:3]).strip()
                    if len(explanation) > 300:
                        explanation = explanation[:297] + "..."
            
            # Default to reasonable count if not found
            if tweet_count == 0:
                tweet_count = 15  # Estimate
        
        except Exception as e:
            logger.error(f"Error parsing sentiment response: {e}")
            logger.error(f"Raw content: {content}")
            tweet_count = 10
        
        return sentiment, explanation, tweet_count
    
    def _parse_sentiment_response(self, content: str) -> Tuple[str, str]:
        """Parse the sentiment analysis response from Grok."""
        sentiment = "neutral"
        explanation = "Unable to determine sentiment"
        
        try:
            lines = content.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                
                if line.startswith("SENTIMENT:"):
                    sentiment_raw = line.replace("SENTIMENT:", "").strip().lower()
                    if "bullish" in sentiment_raw:
                        sentiment = "bullish"
                    elif "bearish" in sentiment_raw:
                        sentiment = "bearish"
                    else:
                        sentiment = "neutral"
                
                elif line.startswith("EXPLANATION:"):
                    explanation = line.replace("EXPLANATION:", "").strip()
                    if not explanation:
                        explanation = "No explanation provided"
            
            # Fallback parsing if format is different
            if sentiment == "neutral" and explanation == "Unable to determine sentiment":
                content_lower = content.lower()
                if "bullish" in content_lower:
                    sentiment = "bullish"
                elif "bearish" in content_lower:
                    sentiment = "bearish"
                
                # Try to extract first sentence as explanation
                sentences = content.split('.')
                if sentences:
                    explanation = sentences[0].strip()
                    if len(explanation) > 200:
                        explanation = explanation[:197] + "..."
        
        except Exception as e:
            logger.error(f"Error parsing sentiment response: {e}")
            logger.error(f"Raw content: {content}")
        
        return sentiment, explanation
    
    async def test_connection(self) -> bool:
        """Test if the Grok API connection is working."""
        try:
            test_prompt = "Hello, please respond with 'Connection successful'"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": test_prompt
                    }
                ],
                "model": "grok-3",
                "stream": False,
                "max_tokens": 50
            }
            
            if not self.session:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        return response.status == 200
            else:
                async with self.session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Grok API test failed: {e}")
            return False


async def test_grok_client():
    """Test function for the Grok client."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("XAI_API_KEY")
    
    if not api_key:
        print("No xAI API key found in environment")
        return
    
    async with GrokClient(api_key) as client:
        # Test connection
        if await client.test_connection():
            print("✅ Grok API connection successful")
        else:
            print("❌ Grok API connection failed")
            return
        
        # Test sentiment analysis
        test_tweets = """Tweet 1: This token is going to the moon! 🚀
Tweet 2: Just bought more, feeling bullish
Tweet 3: Price is dumping hard, might sell"""
        
        sentiment, explanation = await client.analyze_sentiment(
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "TEST",
            test_tweets
        )
        
        print(f"Sentiment: {sentiment}")
        print(f"Explanation: {explanation}")


if __name__ == "__main__":
    asyncio.run(test_grok_client())
