"""
Redis client for job queue and caching
"""

import json
import logging
from typing import Any, Dict, Optional

import aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis client
redis_client: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """Initialize Redis connection"""
    global redis_client
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        # Test connection
        await redis_client.ping()
        logger.info("Redis connection established successfully")

    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Continuing without Redis...")
        redis_client = None


async def get_redis() -> Optional[aioredis.Redis]:
    """Get Redis client"""
    return redis_client


class RedisManager:
    """Redis operations manager"""

    def __init__(self):
        self.client = redis_client

    async def set(self, key: str, value: Any, expire: int = None) -> bool:
        """Set a value in Redis"""
        if not self.client:
            return False

        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            await self.client.set(key, value, ex=expire or settings.REDIS_EXPIRE)
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis"""
        if not self.client:
            return None

        try:
            value = await self.client.get(key)
            if value is None:
                return None

            # Try to parse as JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis"""
        if not self.client:
            return False

        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self.client:
            return False

        try:
            return bool(await self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False

    async def push_to_queue(self, queue_name: str, item: Dict[str, Any]) -> bool:
        """Push item to Redis queue"""
        if not self.client:
            return False

        try:
            await self.client.lpush(queue_name, json.dumps(item))
            return True
        except Exception as e:
            logger.error(f"Redis LPUSH error: {e}")
            return False

    async def pop_from_queue(
        self, queue_name: str, timeout: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Pop item from Redis queue"""
        if not self.client:
            return None

        try:
            result = await self.client.brpop(queue_name, timeout=timeout)
            if result:
                _, item = result
                return json.loads(item)
            return None
        except Exception as e:
            logger.error(f"Redis BRPOP error: {e}")
            return None

    async def get_queue_length(self, queue_name: str) -> int:
        """Get queue length"""
        if not self.client:
            return 0

        try:
            return await self.client.llen(queue_name)
        except Exception as e:
            logger.error(f"Redis LLEN error: {e}")
            return 0


# Global Redis manager instance
redis_manager = RedisManager()
