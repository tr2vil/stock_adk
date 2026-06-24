"""MACD+RSI 신호 상태 영속성 — Redis 백엔드.

종목별 신호 상태머신의 현재 상태(진입 여부, 진입가, 손절가, 목표가 등)를
Redis에 저장한다. 워처 tick 간 상태를 유지하기 위해 사용한다.

키: quant:signal:state:{symbol}
"""
from __future__ import annotations

import json

from shared.redis_client import get_async_redis

_PREFIX = "quant:signal:state:"


async def aget_state(symbol: str) -> dict:
    """종목 신호 상태 조회. 없으면 IDLE 초기 상태 반환."""
    raw = await get_async_redis().get(f"{_PREFIX}{symbol}")
    return json.loads(raw) if raw else {"state": "IDLE"}


async def aput_state(symbol: str, state: dict) -> None:
    """종목 신호 상태 저장."""
    await get_async_redis().set(
        f"{_PREFIX}{symbol}",
        json.dumps(state, ensure_ascii=False),
    )


async def areset_state(symbol: str) -> None:
    """종목 신호 상태 초기화 (IDLE 복귀)."""
    await get_async_redis().delete(f"{_PREFIX}{symbol}")


async def aget_all_states() -> dict[str, dict]:
    """모든 종목 신호 상태 조회 (모니터링용)."""
    r = get_async_redis()
    keys = await r.keys(f"{_PREFIX}*")
    if not keys:
        return {}
    values = await r.mget(*keys)
    result = {}
    for key, val in zip(keys, values):
        symbol = key.decode() if isinstance(key, bytes) else key
        symbol = symbol.replace(_PREFIX, "")
        if val:
            try:
                result[symbol] = json.loads(val)
            except Exception:
                pass
    return result
