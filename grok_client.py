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
        prompt = f"""Analyze these tweets for bullish/bearish sentiment on this Solana memecoin.

Contract Address: {ca}
Token Name: {token_name}

Tweets to analyze:
{tweets_text}

Instructions:
1. Determine overall sentiment: "Bullish", "Bearish", or "Neutral"
2. Provide a brief 1-sentence explanation of your reasoning
3. Consider factors like: price predictions, buying/selling sentiment, community excitement, fear/greed indicators

Respond in this exact format:
SENTIMENT: [Bullish/Bearish/Neutral]
EXPLANATION: [Your 1-sentence explanation]"""

        return prompt
    
    async def analyze_sentiment(self, ca: str, token_name: str, tweets_text: str) -> Tuple[str, str]:
        """
        Analyze sentiment of tweets about a memecoin.
        
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
            "model": "grok-beta",
            "stream": False,
            "temperature": 0.3
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
                "model": "grok-beta",
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
