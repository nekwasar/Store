import os
from typing import Optional

from redis import asyncio as aioredis


async def cache_get(key: str) -> Optional[str]:
    try:
        return await _r.get(f"cache:{key}")
    except Exception:
        return None


async def cache_set(key: str, value: str, ttl: int = 300):
    try:
        await _r.setex(f"cache:{key}", ttl, value)
    except Exception:
        pass


async def cache_delete(pattern: str):
    try:
        keys = await _r.keys(f"cache:{pattern}")
        if keys:
            await _r.delete(*keys)
    except Exception:
        pass
