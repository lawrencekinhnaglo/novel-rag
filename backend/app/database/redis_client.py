"""Enhanced Redis client for caching with background processing support."""
import json
import hashlib
from typing import Optional, List, Dict, Any, Callable, TypeVar
import redis.asyncio as redis
from app.config import settings
import logging
import asyncio
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

# Redis client instance
redis_client: Optional[redis.Redis] = None

# Type var for generic caching
T = TypeVar('T')


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
    logger.info(f"Redis connected at {settings.REDIS_HOST}:{settings.REDIS_PORT}")


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


class CacheManager:
    """Generic cache manager with support for various data types."""
    
    def __init__(self, client: redis.Redis, prefix: str = "cache:", ttl: int = None):
        self.client = client
        self.prefix = prefix
        self.ttl = ttl or settings.CACHE_TTL
    
    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{self.prefix}{key}"
    
    def _hash_key(self, data: str) -> str:
        """Create a hash key from data."""
        return hashlib.md5(data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a cached value."""
        full_key = self._make_key(key)
        data = await self.client.get(full_key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set a cached value."""
        full_key = self._make_key(key)
        try:
            if isinstance(value, (dict, list)):
                data = json.dumps(value, ensure_ascii=False, default=str)
            else:
                data = str(value)
            await self.client.set(full_key, data, ex=ttl or self.ttl)
            return True
        except Exception as e:
            logger.error(f"Cache set failed for {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a cached value."""
        full_key = self._make_key(key)
        await self.client.delete(full_key)
        return True
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        full_key = self._make_key(key)
        return await self.client.exists(full_key) > 0
    
    async def get_or_set(self, key: str, factory: Callable, ttl: int = None) -> Any:
        """Get from cache or set using factory function."""
        value = await self.get(key)
        if value is not None:
            logger.debug(f"Cache hit: {key}")
            return value
        
        logger.debug(f"Cache miss: {key}")
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        await self.set(key, value, ttl)
        return value
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern."""
        full_pattern = self._make_key(pattern)
        keys = await self.client.keys(full_pattern)
        if keys:
            await self.client.delete(*keys)
            return len(keys)
        return 0


class EmbeddingCache(CacheManager):
    """Cache for embeddings to avoid recomputation."""
    
    def __init__(self, client: redis.Redis):
        super().__init__(client, prefix="emb:", ttl=86400 * 7)  # 7 days for embeddings
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get cached embedding for text."""
        key = self._hash_key(text)
        data = await self.get(key)
        return data
    
    async def set_embedding(self, text: str, embedding: List[float]) -> bool:
        """Cache an embedding."""
        key = self._hash_key(text)
        return await self.set(key, embedding)


class QueryCache(CacheManager):
    """Cache for RAG query results."""
    
    def __init__(self, client: redis.Redis):
        super().__init__(client, prefix="query:", ttl=3600)  # 1 hour for queries
    
    async def get_query_result(self, query: str, series_id: int = None) -> Optional[Dict]:
        """Get cached query result."""
        key = self._hash_key(f"{query}:{series_id or 'all'}")
        return await self.get(key)
    
    async def set_query_result(self, query: str, result: Dict, series_id: int = None) -> bool:
        """Cache query result."""
        key = self._hash_key(f"{query}:{series_id or 'all'}")
        return await self.set(key, result)
    
    async def invalidate_series(self, series_id: int) -> int:
        """Invalidate all cached queries for a series."""
        # For simplicity, clear all query cache when series data changes
        return await self.clear_pattern("*")


class KnowledgeCache(CacheManager):
    """Cache for knowledge base items."""
    
    def __init__(self, client: redis.Redis):
        super().__init__(client, prefix="kb:", ttl=1800)  # 30 minutes
    
    async def get_knowledge_list(self, category: str = None) -> Optional[List[Dict]]:
        """Get cached knowledge list."""
        key = f"list:{category or 'all'}"
        return await self.get(key)
    
    async def set_knowledge_list(self, items: List[Dict], category: str = None) -> bool:
        """Cache knowledge list."""
        key = f"list:{category or 'all'}"
        return await self.set(key, items)
    
    async def invalidate(self) -> int:
        """Invalidate all knowledge cache."""
        return await self.clear_pattern("*")


class ConversationCache(CacheManager):
    """Cache manager for conversation threads."""
    
    MESSAGES_SUFFIX = ":messages"
    CONTEXT_SUFFIX = ":context"
    
    def __init__(self, client: redis.Redis):
        super().__init__(client, prefix="conv:", ttl=settings.CACHE_TTL)
    
    async def cache_message(self, session_id: str, message: Dict[str, Any]):
        """Cache a message in a conversation thread."""
        key = f"{self.prefix}{session_id}{self.MESSAGES_SUFFIX}"
        await self.client.rpush(key, json.dumps(message, ensure_ascii=False, default=str))
        await self.client.expire(key, self.ttl)
    
    async def get_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get cached messages for a conversation."""
        key = f"{self.prefix}{session_id}{self.MESSAGES_SUFFIX}"
        messages = await self.client.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages]
    
    async def cache_context(self, session_id: str, context: Dict[str, Any]):
        """Cache conversation context (RAG results, graph data, etc.)."""
        key = f"{self.prefix}{session_id}{self.CONTEXT_SUFFIX}"
        await self.client.set(key, json.dumps(context, ensure_ascii=False, default=str), ex=self.ttl)
    
    async def get_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached context for a conversation."""
        key = f"{self.prefix}{session_id}{self.CONTEXT_SUFFIX}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def clear_session(self, session_id: str):
        """Clear all cached data for a session."""
        keys = await self.client.keys(f"{self.prefix}{session_id}*")
        if keys:
            await self.client.delete(*keys)
    
    async def extend_ttl(self, session_id: str):
        """Extend TTL for an active session."""
        keys = await self.client.keys(f"{self.prefix}{session_id}*")
        for key in keys:
            await self.client.expire(key, self.ttl)


class BackgroundTaskQueue:
    """Simple background task queue using Redis lists."""
    
    def __init__(self, client: redis.Redis, queue_name: str = "tasks"):
        self.client = client
        self.queue_name = f"queue:{queue_name}"
    
    async def enqueue(self, task_type: str, data: Dict[str, Any], priority: int = 0) -> str:
        """Add a task to the queue."""
        task_id = f"{task_type}:{datetime.now().timestamp()}"
        task = {
            "id": task_id,
            "type": task_type,
            "data": data,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        if priority > 0:
            # High priority goes to the front
            await self.client.lpush(self.queue_name, json.dumps(task, default=str))
        else:
            await self.client.rpush(self.queue_name, json.dumps(task, default=str))
        
        return task_id
    
    async def dequeue(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Get next task from queue."""
        if timeout > 0:
            result = await self.client.blpop(self.queue_name, timeout=timeout)
            if result:
                return json.loads(result[1])
        else:
            result = await self.client.lpop(self.queue_name)
            if result:
                return json.loads(result)
        return None
    
    async def queue_length(self) -> int:
        """Get number of pending tasks."""
        return await self.client.llen(self.queue_name)
    
    async def clear(self) -> int:
        """Clear all tasks from queue."""
        length = await self.queue_length()
        await self.client.delete(self.queue_name)
        return length


# Cache instances
_embedding_cache: Optional[EmbeddingCache] = None
_query_cache: Optional[QueryCache] = None
_knowledge_cache: Optional[KnowledgeCache] = None
_conversation_cache: Optional[ConversationCache] = None
_task_queue: Optional[BackgroundTaskQueue] = None


def get_embedding_cache() -> EmbeddingCache:
    """Get embedding cache instance."""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache(get_redis())
    return _embedding_cache


def get_query_cache() -> QueryCache:
    """Get query cache instance."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(get_redis())
    return _query_cache


def get_knowledge_cache() -> KnowledgeCache:
    """Get knowledge cache instance."""
    global _knowledge_cache
    if _knowledge_cache is None:
        _knowledge_cache = KnowledgeCache(get_redis())
    return _knowledge_cache


async def get_conversation_cache() -> ConversationCache:
    """Get conversation cache instance."""
    global _conversation_cache
    if _conversation_cache is None:
        _conversation_cache = ConversationCache(get_redis())
    return _conversation_cache


def get_task_queue(queue_name: str = "default") -> BackgroundTaskQueue:
    """Get task queue instance."""
    return BackgroundTaskQueue(get_redis(), queue_name)


# Decorator for caching function results
def cached(prefix: str, ttl: int = 3600, key_builder: Callable = None):
    """Decorator to cache async function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                cache = CacheManager(get_redis(), prefix=f"{prefix}:", ttl=ttl)
                
                # Build cache key
                if key_builder:
                    key = key_builder(*args, **kwargs)
                else:
                    key = hashlib.md5(f"{args}:{kwargs}".encode()).hexdigest()
                
                # Try cache
                cached_value = await cache.get(key)
                if cached_value is not None:
                    return cached_value
                
                # Execute and cache
                result = await func(*args, **kwargs)
                await cache.set(key, result)
                return result
            except Exception as e:
                logger.warning(f"Cache error, falling back to direct call: {e}")
                return await func(*args, **kwargs)
        return wrapper
    return decorator
