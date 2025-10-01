"""Database models and operations for the Solana memecoins sentiment analyzer bot."""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class MemecoinCache(Base):
    """Cache table for DexScreener memecoin data."""
    __tablename__ = "memecoins_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ca = Column(String(44), nullable=False, index=True)  # Contract Address
    name = Column(String(255), nullable=True)
    symbol = Column(String(50), nullable=True)
    mc = Column(Float, nullable=True)  # Market Cap
    volume_24h = Column(Float, nullable=True)
    liquidity = Column(Float, nullable=True)
    holders_estimate = Column(Integer, nullable=True)
    price_usd = Column(Float, nullable=True)
    price_change_24h = Column(Float, nullable=True)
    dex_url = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserFilter(Base):
    """User preferences and filters."""
    __tablename__ = "user_filters"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(50), nullable=False, index=True)
    filter_name = Column(String(100), nullable=False)
    filter_string = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SentimentCache(Base):
    """Cache table for sentiment analysis results."""
    __tablename__ = "sentiment_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ca = Column(String(44), nullable=False, index=True)
    sentiment = Column(String(20), nullable=False)  # bullish, bearish, neutral
    explanation = Column(Text, nullable=True)
    tweet_count = Column(Integer, nullable=False, default=0)
    sample_tweets = Column(Text, nullable=True)  # JSON string of sample tweets
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class DatabaseManager:
    """Database connection and operations manager."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def create_tables(self):
        """Create all tables if they don't exist."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def get_cached_memecoin(self, ca: str, max_age_minutes: int = 5) -> Optional[MemecoinCache]:
        """Get cached memecoin data if it's fresh enough."""
        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
            return session.query(MemecoinCache).filter(
                MemecoinCache.ca == ca,
                MemecoinCache.timestamp > cutoff_time
            ).first()
    
    def cache_memecoin(self, memecoin_data: Dict[str, Any]) -> None:
        """Cache memecoin data."""
        with self.get_session() as session:
            # Remove old cache entries for this CA
            session.query(MemecoinCache).filter(MemecoinCache.ca == memecoin_data['ca']).delete()
            
            # Add new cache entry
            cache_entry = MemecoinCache(
                ca=memecoin_data['ca'],
                name=memecoin_data.get('name'),
                symbol=memecoin_data.get('symbol'),
                mc=memecoin_data.get('mc'),
                volume_24h=memecoin_data.get('volume_24h'),
                liquidity=memecoin_data.get('liquidity'),
                holders_estimate=memecoin_data.get('holders_estimate'),
                price_usd=memecoin_data.get('price_usd'),
                price_change_24h=memecoin_data.get('price_change_24h'),
                dex_url=memecoin_data.get('dex_url')
            )
            session.add(cache_entry)
            session.commit()
    
    def get_cached_memecoins_by_filter(self, filters: Dict[str, Any], max_age_minutes: int = 5) -> List[MemecoinCache]:
        """Get cached memecoins that match the given filters."""
        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
            query = session.query(MemecoinCache).filter(MemecoinCache.timestamp > cutoff_time)
            
            if 'mc_min' in filters:
                query = query.filter(MemecoinCache.mc >= filters['mc_min'])
            if 'mc_max' in filters:
                query = query.filter(MemecoinCache.mc <= filters['mc_max'])
            if 'volume_min' in filters:
                query = query.filter(MemecoinCache.volume_24h >= filters['volume_min'])
            if 'volume_max' in filters:
                query = query.filter(MemecoinCache.volume_24h <= filters['volume_max'])
            if 'holders_min' in filters:
                query = query.filter(MemecoinCache.holders_estimate >= filters['holders_min'])
            if 'liquidity_min' in filters:
                query = query.filter(MemecoinCache.liquidity >= filters['liquidity_min'])
            
            return query.order_by(MemecoinCache.mc.desc()).limit(20).all()
    
    def save_user_filter(self, chat_id: str, filter_name: str, filter_string: str) -> None:
        """Save user filter preferences."""
        with self.get_session() as session:
            # Remove existing filter with same name for this user
            session.query(UserFilter).filter(
                UserFilter.chat_id == chat_id,
                UserFilter.filter_name == filter_name
            ).delete()
            
            # Add new filter
            user_filter = UserFilter(
                chat_id=chat_id,
                filter_name=filter_name,
                filter_string=filter_string
            )
            session.add(user_filter)
            session.commit()
    
    def get_user_filters(self, chat_id: str) -> List[UserFilter]:
        """Get all saved filters for a user."""
        with self.get_session() as session:
            return session.query(UserFilter).filter(UserFilter.chat_id == chat_id).all()
    
    def get_cached_sentiment(self, ca: str, max_age_hours: int = 1) -> Optional[SentimentCache]:
        """Get cached sentiment analysis if it's fresh enough."""
        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            return session.query(SentimentCache).filter(
                SentimentCache.ca == ca,
                SentimentCache.timestamp > cutoff_time
            ).first()
    
    def cache_sentiment(self, ca: str, sentiment: str, explanation: str, 
                       tweet_count: int, sample_tweets: str) -> None:
        """Cache sentiment analysis results."""
        with self.get_session() as session:
            # Remove old cache entries for this CA
            session.query(SentimentCache).filter(SentimentCache.ca == ca).delete()
            
            # Add new cache entry
            cache_entry = SentimentCache(
                ca=ca,
                sentiment=sentiment,
                explanation=explanation,
                tweet_count=tweet_count,
                sample_tweets=sample_tweets
            )
            session.add(cache_entry)
            session.commit()
    
    def cleanup_old_cache(self, max_age_days: int = 7) -> None:
        """Clean up old cache entries."""
        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
            
            # Clean up old memecoin cache
            session.query(MemecoinCache).filter(MemecoinCache.timestamp < cutoff_time).delete()
            
            # Clean up old sentiment cache
            session.query(SentimentCache).filter(SentimentCache.timestamp < cutoff_time).delete()
            
            session.commit()


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def init_database(database_url: str) -> DatabaseManager:
    """Initialize the database manager."""
    global db_manager
    db_manager = DatabaseManager(database_url)
    db_manager.create_tables()
    return db_manager


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    if db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return db_manager
