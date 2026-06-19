"""신호/주문/매매결과 기록·조회 (Redis 백엔드).

Evolution Agent의 성과 분석(performance.compute_performance) 입력을 공급한다.
설계서의 PostgreSQL signals/orders 테이블을 단순화한 Redis LIST 구현이다.
(향후 PostgreSQL 마이그레이션 시 이 모듈 인터페이스만 유지하면 됨)

- 신호 로그: `quant:trades` (LIST, 최신이 앞)
각 레코드:
    {
      "ts": int(ms), "ticker": str, "signal": str, "rsi": float,
      "sentiment": float, "confidence": float, "strategy_version": str,
      "side": str|None, "quantity": int|None, "price": float|None,
      "entry_price": float|None, "return_rate": float|None, "reasoning": str
    }
"""
from __future__ import annotations

import json

from shared.redis_client import get_async_redis

_TRADES_KEY = "quant:trades"
_TRADES_MAX = 5000


async def arecord_trade(record: dict) -> None:
    """매매/신호 레코드 1건 추가."""
    r = get_async_redis()
    await r.lpush(_TRADES_KEY, json.dumps(record, ensure_ascii=False))
    await r.ltrim(_TRADES_KEY, 0, _TRADES_MAX - 1)


async def aget_recent_trades(limit: int = 1000, since_ms: int | None = None) -> list[dict]:
    """최근 매매 레코드(최신순). since_ms 지정 시 그 이후만."""
    raw = await get_async_redis().lrange(_TRADES_KEY, 0, limit - 1)
    out = [json.loads(x) for x in raw]
    if since_ms is not None:
        out = [t for t in out if t.get("ts", 0) >= since_ms]
    return out
