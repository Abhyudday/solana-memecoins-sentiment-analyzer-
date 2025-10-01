"""Twitter API client for fetching tweets about Solana memecoins."""

import tweepy
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


class TwitterClient:
    """Twitter API v2 client using tweepy."""
    
    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token
        self.client = tweepy.Client(bearer_token=bearer_token)
        
    def _is_valid_solana_address(self, address: str) -> bool:
        """Validate if a string is a valid Solana address."""
        if not address or len(address) != 44:
            return False
        
        # Basic base58 character check
        base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        return all(c in base58_chars for c in address)
    
    def _clean_tweet_text(self, text: str) -> str:
        """Clean and normalize tweet text."""
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    async def search_tweets_by_ca(self, ca: str, token_name: str = "", 
                                 max_results: int = 50, days_back: int = 7) -> List[Dict[str, Any]]:
        """Search for tweets mentioning a contract address or token name."""
        if not self._is_valid_solana_address(ca):
            logger.error(f"Invalid Solana address: {ca}")
            return []
        
        # Build search query - prioritize token name as tweets rarely include full CA
        # Note: Avoid cashtag ($) operator as it's not available in basic Twitter API tiers
        query_parts = []
        
        # If we have a token name, prioritize it (most common in tweets)
        if token_name and len(token_name) > 2:
            token_name_clean = token_name.strip()
            # Add token name - quoted for exact match and plain
            query_parts.append(f'"{token_name_clean}"')
            # Only add plain name if it's not too short/common
            if len(token_name_clean) > 3:
                query_parts.append(token_name_clean)
        else:
            # No token name - search by CA
            # Use partial CA strings which are more common in tweets
            ca_start = ca[:12]
            ca_end = ca[-12:]
            query_parts.append(ca_start)
            query_parts.append(ca_end)
        
        # Combine with OR and add context filters
        # Keep query simple and under Twitter's limit
        base_query = ' OR '.join(query_parts[:3])  # Limit to 3 parts max
        query = f"({base_query}) (solana OR crypto) -is:retweet lang:en"
        
        logger.info(f"Twitter search query: {query}")
        
        # Calculate start time (days back)
        start_time = datetime.utcnow() - timedelta(days=days_back)
        
        try:
            tweets = tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                max_results=min(max_results, 100),  # Twitter API limit
                start_time=start_time,
                tweet_fields=['created_at', 'author_id', 'public_metrics', 'context_annotations'],
                expansions=['author_id'],
                user_fields=['username', 'verified', 'public_metrics']
            ).flatten(limit=max_results)
            
            tweet_data = []
            users_data = {}
            
            # Process tweets
            for tweet in tweets:
                if not tweet or not tweet.text:
                    continue
                
                # Get user info if available
                author_info = {}
                if hasattr(tweet, 'author_id') and tweet.author_id:
                    # This would be populated if we had user expansion data
                    author_info = {
                        'id': tweet.author_id,
                        'username': 'unknown',
                        'verified': False
                    }
                
                tweet_info = {
                    'id': tweet.id,
                    'text': self._clean_tweet_text(tweet.text),
                    'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                    'author': author_info,
                    'metrics': {
                        'retweet_count': tweet.public_metrics.get('retweet_count', 0) if tweet.public_metrics else 0,
                        'like_count': tweet.public_metrics.get('like_count', 0) if tweet.public_metrics else 0,
                        'reply_count': tweet.public_metrics.get('reply_count', 0) if tweet.public_metrics else 0,
                    } if tweet.public_metrics else {},
                    'url': f"https://twitter.com/user/status/{tweet.id}"
                }
                
                tweet_data.append(tweet_info)
            
            logger.info(f"Found {len(tweet_data)} tweets for CA: {ca}")
            return tweet_data
            
        except tweepy.TooManyRequests:
            logger.warning("Twitter API rate limit exceeded")
            return []
        except tweepy.Unauthorized:
            logger.error("Twitter API unauthorized - check bearer token")
            return []
        except Exception as e:
            logger.error(f"Error searching tweets: {e}")
            return []
    
    def get_sample_tweets_text(self, tweets: List[Dict[str, Any]], max_tweets: int = 3) -> List[str]:
        """Get sample tweet texts for display."""
        sample_tweets = []
        
        for tweet in tweets[:max_tweets]:
            text = tweet.get('text', '')
            if len(text) > 100:
                text = text[:97] + "..."
            
            metrics = tweet.get('metrics', {})
            likes = metrics.get('like_count', 0)
            retweets = metrics.get('retweet_count', 0)
            
            sample_text = f"💬 {text}"
            if likes > 0 or retweets > 0:
                sample_text += f"\n   👍 {likes} ❤️ | 🔄 {retweets} RT"
            
            sample_tweets.append(sample_text)
        
        return sample_tweets
    
    def prepare_tweets_for_sentiment(self, tweets: List[Dict[str, Any]]) -> str:
        """Prepare tweets text for sentiment analysis."""
        if not tweets:
            return ""
        
        tweet_texts = []
        for i, tweet in enumerate(tweets[:20], 1):  # Limit to 20 tweets for API
            text = tweet.get('text', '').strip()
            if text:
                tweet_texts.append(f"Tweet {i}: {text}")
        
        return "\n\n".join(tweet_texts)
    
    async def test_connection(self) -> bool:
        """Test if the Twitter API connection is working."""
        try:
            # Try a simple search
            tweets = tweepy.Paginator(
                self.client.search_recent_tweets,
                query="solana lang:en",
                max_results=10
            ).flatten(limit=1)
            
            # Check if we got any results
            tweet_list = list(tweets)
            return len(tweet_list) > 0
            
        except Exception as e:
            logger.error(f"Twitter API test failed: {e}")
            return False


async def test_twitter_client():
    """Test function for the Twitter client."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    
    if not bearer_token:
        print("No Twitter bearer token found in environment")
        return
    
    client = TwitterClient(bearer_token)
    
    # Test connection
    if await client.test_connection():
        print("✅ Twitter API connection successful")
    else:
        print("❌ Twitter API connection failed")
        return
    
    # Test search
    test_ca = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC for testing
    tweets = await client.search_tweets_by_ca(test_ca, "USDC", max_results=5)
    
    print(f"Found {len(tweets)} tweets")
    for tweet in tweets[:3]:
        print(f"- {tweet['text'][:100]}...")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_twitter_client())
