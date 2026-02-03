import hashlib
import json
from typing import Optional

import redis.asyncio as redis

from src.core.config import get_settings

settings = get_settings()


class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    async def get_cache(self, key: str) -> Optional[dict]:
        if not settings.ENABLE_PROMPT_CACHE:
            return None

        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_cache(self, key: str, value: dict, ttl: int = None):
        if not settings.ENABLE_PROMPT_CACHE:
            return

        ttl = ttl or settings.CACHE_TTL
        await self.redis.setex(key, ttl, json.dumps(value))

    def generate_cache_key(
        self, tenant_id: str, provider: str, model: str, prompt: str
    ) -> str:
        content = f"{tenant_id}:{provider}:{model}:{prompt}"
        return f"cache:{hashlib.sha256(content.encode()).hexdigest()}"

    async def check_rate_limit(
        self, tenant_id: str, limit: int
    ) -> tuple[bool, int]:
        key = f"rate_limit:{tenant_id}"
        current = await self.redis.get(key)

        if current is None:
            await self.redis.setex(key, 60, 1)
            return True, limit - 1

        current = int(current)
        if current >= limit:
            return False, 0

        await self.redis.incr(key)
        return True, limit - current - 1


redis_client = RedisClient()
