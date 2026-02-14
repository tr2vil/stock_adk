"""
Redis client utilities for prompt and weight management.
Provides both sync (startup) and async (API) clients.
"""
import json

import redis
import redis.asyncio as aioredis

from shared.config import settings
from shared.logger import get_logger

logger = get_logger("shared.redis")

_sync_client: redis.Redis | None = None
_async_client: aioredis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    """Return a sync Redis client (lazy singleton)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _sync_client


def get_async_redis() -> aioredis.Redis:
    """Return an async Redis client (lazy singleton)."""
    global _async_client
    if _async_client is None:
        _async_client = aioredis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _async_client


# ── Seed ──

def seed_defaults(defaults: dict[str, str]) -> int:
    """Seed Redis with default values for keys that do not exist (SET NX).
    Returns the count of keys seeded.
    """
    try:
        r = get_sync_redis()
        seeded = 0
        for key, value in defaults.items():
            if r.set(key, value, nx=True):
                seeded += 1
                logger.info("redis_seed", key=key, length=len(value))
        return seeded
    except Exception as e:
        logger.warning("redis_seed_failed", error=str(e))
        return 0


# ── Sync prompt helpers (for agent startup) ──

def get_prompt(agent_name: str) -> str | None:
    """Get prompt from Redis (sync)."""
    try:
        return get_sync_redis().get(f"prompt:{agent_name}")
    except Exception:
        return None


def get_prompt_safe(agent_name: str, fallback: str) -> str:
    """Get prompt from Redis with fallback on failure."""
    result = get_prompt(agent_name)
    if result:
        return result
    logger.warning("redis_prompt_fallback", agent=agent_name)
    return fallback


# ── Async prompt helpers (for API endpoints) ──

async def aget_prompt(agent_name: str) -> str | None:
    """Get prompt from Redis (async)."""
    return await get_async_redis().get(f"prompt:{agent_name}")


async def aset_prompt(agent_name: str, text: str) -> None:
    """Set prompt in Redis (async)."""
    await get_async_redis().set(f"prompt:{agent_name}", text)


# ── Async weights helpers ──

async def aget_weights() -> dict | None:
    """Get weights from Redis (async)."""
    raw = await get_async_redis().get("weights")
    return json.loads(raw) if raw else None


async def aset_weights(weights: dict) -> None:
    """Set weights in Redis (async)."""
    await get_async_redis().set("weights", json.dumps(weights))


# ── Async thresholds helpers ──

async def aget_thresholds() -> dict | None:
    """Get thresholds from Redis (async)."""
    raw = await get_async_redis().get("thresholds")
    return json.loads(raw) if raw else None


async def aset_thresholds(thresholds: dict) -> None:
    """Set thresholds in Redis (async)."""
    await get_async_redis().set("thresholds", json.dumps(thresholds))
