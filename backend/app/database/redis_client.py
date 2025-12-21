"""Redis client for caching conversation threads."""
import json
from typing import Optional, List, Dict, Any
import redis.asyncio as redis
from app.config import settings

# Redis client instance
redis_client: Optional[redis.Redis] = None


async def init_redis():
    """Initialize Redis connection."""
    global redis_client
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )
    # Test connection
    await redis_client.ping()


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()


def get_redis() -> redis.Redis:
    """Get Redis client."""
    if not redis_client:
        raise RuntimeError("Redis not initialized")
    return redis_client


class ConversationCache:
    """Cache manager for conversation threads."""
    
    PREFIX = "conv:"
    MESSAGES_SUFFIX = ":messages"
    CONTEXT_SUFFIX = ":context"
    
    def __init__(self, client: redis.Redis):
        self.client = client
        self.ttl = settings.CACHE_TTL
    
    async def cache_message(self, session_id: str, message: Dict[str, Any]):
        """Cache a message in a conversation thread."""
        key = f"{self.PREFIX}{session_id}{self.MESSAGES_SUFFIX}"
        await self.client.rpush(key, json.dumps(message))
        await self.client.expire(key, self.ttl)
    
    async def get_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get cached messages for a conversation."""
        key = f"{self.PREFIX}{session_id}{self.MESSAGES_SUFFIX}"
        messages = await self.client.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages]
    
    async def cache_context(self, session_id: str, context: Dict[str, Any]):
        """Cache conversation context (RAG results, graph data, etc.)."""
        key = f"{self.PREFIX}{session_id}{self.CONTEXT_SUFFIX}"
        await self.client.set(key, json.dumps(context), ex=self.ttl)
    
    async def get_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached context for a conversation."""
        key = f"{self.PREFIX}{session_id}{self.CONTEXT_SUFFIX}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def clear_session(self, session_id: str):
        """Clear all cached data for a session."""
        keys = await self.client.keys(f"{self.PREFIX}{session_id}*")
        if keys:
            await self.client.delete(*keys)
    
    async def extend_ttl(self, session_id: str):
        """Extend TTL for an active session."""
        keys = await self.client.keys(f"{self.PREFIX}{session_id}*")
        for key in keys:
            await self.client.expire(key, self.ttl)


async def get_conversation_cache() -> ConversationCache:
    """Get conversation cache instance."""
    return ConversationCache(get_redis())

