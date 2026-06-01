"""
Redis memory manager for short-term context and caching with TTL.
"""
import json
import logging
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
from .base import BaseMemoryManager

logger = logging.getLogger(__name__)

class RedisMemoryManager(BaseMemoryManager):
    """
    Redis-based memory manager for short-term data with TTL.
    Good for conversation context, caching, rate limiting, and ephemeral state.

    All direct Redis access is private (_redis). Use cache_* and store_* methods.
    """

    def __init__(self, host: str, port: int, password: Optional[str] = None, db: int = 0):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self._redis: Optional[redis.Redis] = None

    @property
    def redis(self) -> Optional[redis.Redis]:
        """Direct Redis client access (internal use only). Prefer cache_* methods."""
        return self._redis

    async def initialize(self) -> None:
        """Initialize the Redis connection."""
        try:
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self._redis.ping()
            logger.info("Redis memory manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis memory manager: {e}")
            raise

    async def shutdown(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.close()
            logger.info("Redis memory manager shutdown")
    
    async def store_lead_memory(self, lead_id: str, memory_type: str, data: Dict[str, Any]) -> bool:
        """
        Store memory associated with a lead in Redis.
        Note: Redis is not ideal for long-term relational storage, but can be used for caching.
        For persistent lead memory, Postgres is preferred.
        """
        try:
            key = f"lead:{lead_id}:memory:{memory_type}"
            value = json.dumps(data)
            await self._redis.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Failed to store lead memory in Redis for {lead_id}: {e}")
            return False

    async def retrieve_lead_memory(self, lead_id: str, memory_type: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve memory associated with a lead from Redis.
        """
        try:
            key = f"lead:{lead_id}:memory:{memory_type}"
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve lead memory from Redis for {lead_id}: {e}")
            return None

    async def store_conversation_context(self, lead_id: str, context: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Store short-term conversation context with TTL.
        This is the primary use case for Redis in this system.
        """
        try:
            key = f"lead:{lead_id}:context"
            value = json.dumps(context)
            await self._redis.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"Failed to store conversation context in Redis for {lead_id}: {e}")
            return False

    async def retrieve_conversation_context(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve short-term conversation context.
        """
        try:
            key = f"lead:{lead_id}:context"
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve conversation context from Redis for {lead_id}: {e}")
            return None

    # ─── Cache operations (abstract from BaseMemoryManager) ───────────────────

    async def cache_get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        try:
            value = await self._redis.get(key)
            if value:
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            return None
        except Exception as e:
            logger.error(f"Failed to get cached value for {key}: {e}")
            return None

    async def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Set a value in cache with TTL."""
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            await self._redis.setex(key, ttl_seconds, serialized)
            return True
        except Exception as e:
            logger.error(f"Failed to set cached value for {key}: {e}")
            return False

    async def cache_delete(self, key: str) -> bool:
        """Delete a value from cache."""
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete cached value for {key}: {e}")
            return False

    # ─── Structured storage (delegates to lead_memory methods) ────────────────

    async def store(self, namespace: str, key: str, data: Dict[str, Any]) -> bool:
        """Store structured data using lead_memory as backing store."""
        try:
            full_key = f"{namespace}:{key}"
            value = json.dumps(data, ensure_ascii=False)
            await self._redis.set(full_key, value)
            return True
        except Exception as e:
            logger.error(f"Failed to store structured data {namespace}:{key}: {e}")
            return False

    async def retrieve(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve structured data."""
        try:
            full_key = f"{namespace}:{key}"
            value = await self._redis.get(full_key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve structured data {namespace}:{key}: {e}")
            return None

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete structured data."""
        try:
            full_key = f"{namespace}:{key}"
            await self._redis.delete(full_key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete structured data {namespace}:{key}: {e}")
            return False

    async def search_by_text(self, namespace: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Redis doesn't support full-text search natively. Returns empty list."""
        logger.warning("Redis does not support text search. Use PostgreSQL or Qdrant.")
        return []

    # ─── Redis-specific methods ───────────────────────────────────────────────

    async def increment_daily_counter(self, key: str, expiry_seconds: int = 86400) -> int:
        """Increment a counter with automatic expiry. Useful for daily message limits."""
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, expiry_seconds)
                results = await pipe.execute()
                return results[0]
        except Exception as e:
            logger.error(f"Failed to increment daily counter for {key}: {e}")
            return 0

    async def get_daily_counter(self, key: str) -> int:
        """Get the current value of a daily counter."""
        try:
            value = await self._redis.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Failed to get daily counter for {key}: {e}")
            return 0

    async def set_rate_limit(self, lead_id: str, action: str, limit: int, window_seconds: int) -> bool:
        """Set a rate limit for a specific lead and action."""
        try:
            key = f"rate_limit:{lead_id}:{action}"
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()
            current_count = results[0]
            return current_count <= limit
        except Exception as e:
            logger.error(f"Failed to set rate limit for {lead_id}:{action}: {e}")
            return False

    # ─── Abstract methods (delegates to specialized managers) ──────────────────

    async def search_similar_memories(self, query_vector: List[float], memory_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError("Vector search requires Qdrant memory manager")

    async def store_interaction_history(self, lead_id: str, interaction_type: str, data: Dict[str, Any]) -> bool:
        raise NotImplementedError("Interaction history requires PostgreSQL memory manager")

    async def retrieve_interaction_history(self, lead_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError("Interaction history retrieval requires PostgreSQL memory manager")
