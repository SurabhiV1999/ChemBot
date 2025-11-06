"""
Redis Cache Manager
Handles caching of Q&A pairs to avoid redundant LLM calls
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis
from ..config import settings

logger = logging.getLogger(__name__)


class RedisCacheManager:
    """
    Manages Redis caching for question-answer pairs
    """
    
    def __init__(self):
        self.enabled = settings.REDIS_CACHE_ENABLED
        self.ttl = settings.REDIS_CACHE_TTL
        self.client: Optional[redis.Redis] = None
        self._initialized = False

        if self.enabled:
            # Create async Redis client
            # Note: Connection pool is created lazily on first command
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            logger.info(f"Created Redis client for {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        else:
            logger.info("Redis caching is disabled")

    async def _ensure_initialized(self):
        """Ensure Redis connection is established (called on first use)"""
        if not self.enabled or self._initialized:
            return

        try:
            # Test connection
            await self.client.ping()
            self._initialized = True
            logger.info(f"✅ Redis connection established successfully")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.enabled = False
            self._initialized = False
    
    async def ping(self) -> bool:
        """Test Redis connection"""
        if not self.enabled or not self.client:
            return False
        
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    def _generate_cache_key(self, question: str, content_id: str, **kwargs) -> str:
        """
        Generate a unique cache key for a question
        
        Args:
            question: The user's question
            content_id: ID of the content being queried
            **kwargs: Additional parameters that affect the answer
        
        Returns:
            Hash-based cache key
        """
        # Normalize question (lowercase, strip whitespace)
        normalized_question = question.lower().strip()
        
        # Create a string with all relevant parameters
        cache_string = f"{content_id}:{normalized_question}"
        
        # Include other parameters that affect the answer
        if kwargs:
            # Sort kwargs for consistency
            sorted_kwargs = sorted(kwargs.items())
            cache_string += ":" + json.dumps(sorted_kwargs, sort_keys=True)
        
        # Generate SHA256 hash
        cache_key = hashlib.sha256(cache_string.encode()).hexdigest()
        
        # Prefix with namespace
        return f"chembot:qa:{cache_key}"
    
    async def get_cached_answer(self, question: str, content_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached answer for a question

        Args:
            question: The user's question
            content_id: ID of the content being queried
            **kwargs: Additional parameters

        Returns:
            Cached answer dict or None if not found
        """
        if not self.enabled or not self.client:
            logger.debug("Cache disabled or client not available")
            return None

        try:
            # Ensure connection is established
            await self._ensure_initialized()

            if not self.enabled:  # May have been disabled by _ensure_initialized
                return None

            cache_key = self._generate_cache_key(question, content_id, **kwargs)
            logger.info(f"🔍 Looking up cache key: {cache_key[:50]}...")

            cached_data = await self.client.get(cache_key)

            if cached_data:
                logger.info(f"🎯 CACHE HIT - Returning cached answer for: '{question[:70]}...'")
                return json.loads(cached_data)
            else:
                logger.info(f"❌ CACHE MISS - No cached answer found for: '{question[:70]}...'")
                return None

        except Exception as e:
            logger.error(f"❌ Error retrieving from cache: {e}", exc_info=True)
            return None
    
    async def cache_answer(self, question: str, content_id: str, answer_data: Dict[str, Any], **kwargs):
        """
        Cache an answer for a question

        Args:
            question: The user's question
            content_id: ID of the content being queried
            answer_data: The answer data to cache
            **kwargs: Additional parameters
        """
        if not self.enabled or not self.client:
            logger.debug("Cache disabled or client not available - skipping cache write")
            return

        try:
            # Ensure connection is established
            await self._ensure_initialized()

            if not self.enabled:  # May have been disabled by _ensure_initialized
                return

            cache_key = self._generate_cache_key(question, content_id, **kwargs)

            # Add cache metadata
            cache_data = {
                **answer_data,
                "cached": True,
                "cache_key": cache_key
            }

            # Store with TTL
            logger.info(f"💾 Storing in cache with key: {cache_key[:50]}...")
            await self.client.setex(
                cache_key,
                self.ttl,
                json.dumps(cache_data)
            )

            logger.info(f"✅ CACHED - Successfully cached answer for: '{question[:70]}...' (TTL: {self.ttl}s)")

        except Exception as e:
            logger.error(f"❌ Error caching answer: {e}", exc_info=True)
    
    async def invalidate_content_cache(self, content_id: str):
        """
        Invalidate all cached answers for a specific content
        
        Args:
            content_id: Content ID to invalidate
        """
        if not self.enabled or not self.client:
            return
        
        try:
            # Find all keys for this content
            pattern = f"chembot:qa:*{content_id}*"
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.client.scan(cursor, match=pattern, count=100)
                if keys:
                    await self.client.delete(*keys)
                    deleted_count += len(keys)
                
                if cursor == 0:
                    break
            
            logger.info(f"Invalidated {deleted_count} cached answers for content {content_id}")
        
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.enabled or not self.client:
            return {"enabled": False}
        
        try:
            info = await self.client.info()
            
            return {
                "enabled": True,
                "connected": True,
                "total_keys": info.get("db0", {}).get("keys", 0),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
        
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"enabled": True, "connected": False, "error": str(e)}
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate"""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)
    
    async def clear_all_cache(self):
        """Clear all cached data (use with caution!)"""
        if not self.enabled or not self.client:
            return
        
        try:
            pattern = "chembot:qa:*"
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.client.scan(cursor, match=pattern, count=100)
                if keys:
                    await self.client.delete(*keys)
                    deleted_count += len(keys)
                
                if cursor == 0:
                    break
            
            logger.warning(f"Cleared all cache: {deleted_count} keys deleted")
        
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")


# Global cache instance
_cache_instance: Optional[RedisCacheManager] = None


def get_cache_manager() -> RedisCacheManager:
    """Get or create global cache manager instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCacheManager()
    return _cache_instance

