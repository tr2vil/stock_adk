"""활성 전략 + 버전 이력 저장소 (Redis 백엔드).

- 활성 전략: `quant:strategy:active` (StrategyConfig JSON)
- 버전 이력: `quant:strategy:versions` (LIST, 최신이 앞. 각 항목은 스냅샷+메타)
- 대기 제안: `quant:evolution:pending:<id>` (HiL 승인 대기)

시드 기본값은 config/strategy.yaml 에서 로드한다(최초 1회 Redis 주입).
순수 로직(검증/적용)은 guardrails 모듈에 있고, 여기서는 영속화만 담당한다.
"""
from __future__ import annotations

import os
import json
import uuid

import yaml

from shared.redis_client import get_async_redis
from shared.logger import get_logger
from .schema import StrategyConfig

logger = get_logger("quant.strategy_store")

_ACTIVE_KEY = "quant:strategy:active"
_VERSIONS_KEY = "quant:strategy:versions"
_PENDING_PREFIX = "quant:evolution:pending:"
_VERSIONS_MAX = 100

_SEED_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "strategy.yaml"
)


def load_seed_strategy() -> StrategyConfig:
    """config/strategy.yaml 시드를 StrategyConfig 로 로드(없으면 기본값)."""
    try:
        with open(_SEED_PATH, encoding="utf-8") as f:
            return StrategyConfig.model_validate(yaml.safe_load(f) or {})
    except FileNotFoundError:
        logger.warning("strategy_seed_missing", path=_SEED_PATH)
        return StrategyConfig()


async def aget_active_strategy() -> StrategyConfig:
    """활성 전략 조회. Redis에 없으면 시드를 주입 후 반환."""
    raw = await get_async_redis().get(_ACTIVE_KEY)
    if raw:
        return StrategyConfig.model_validate(json.loads(raw))
    seed = load_seed_strategy()
    await _aset_active(seed)
    await _apush_version(seed, note="seed")
    logger.info("strategy_seeded", version=seed.version)
    return seed


async def _aset_active(strategy: StrategyConfig) -> None:
    await get_async_redis().set(_ACTIVE_KEY, strategy.model_dump_json())


async def _apush_version(strategy: StrategyConfig, *, note: str = "",
                         analysis: str = "", changes: list | None = None,
                         performance_before: dict | None = None,
                         approved_by: str = "seed") -> None:
    record = {
        "version": strategy.version,
        "strategy": strategy.model_dump(),
        "note": note,
        "analysis": analysis,
        "changes": changes or [],
        "performance_before": performance_before or {},
        "approved_by": approved_by,
        "applied_at": strategy.updated_at,
    }
    r = get_async_redis()
    await r.lpush(_VERSIONS_KEY, json.dumps(record, ensure_ascii=False))
    await r.ltrim(_VERSIONS_KEY, 0, _VERSIONS_MAX - 1)


async def acommit_new_version(strategy: StrategyConfig, *, analysis: str = "",
                              changes: list | None = None,
                              performance_before: dict | None = None,
                              approved_by: str = "user") -> None:
    """승인된 새 전략을 활성으로 설정하고 버전 이력에 기록."""
    await _aset_active(strategy)
    await _apush_version(
        strategy, note="evolution", analysis=analysis, changes=changes,
        performance_before=performance_before, approved_by=approved_by,
    )
    logger.info("strategy_committed", version=strategy.version, by=approved_by,
                changes=len(changes or []))


async def aget_version_history(limit: int = 5) -> list[dict]:
    """최근 버전 이력(최신순)."""
    raw = await get_async_redis().lrange(_VERSIONS_KEY, 0, limit - 1)
    return [json.loads(x) for x in raw]


async def arollback(version: str) -> tuple[StrategyConfig | None, str]:
    """지정 버전으로 롤백. 해당 스냅샷을 활성으로 복원하고 이력에 기록."""
    raw = await get_async_redis().lrange(_VERSIONS_KEY, 0, _VERSIONS_MAX - 1)
    for item in raw:
        rec = json.loads(item)
        if rec["version"] == version:
            restored = StrategyConfig.model_validate(rec["strategy"])
            await _aset_active(restored)
            await _apush_version(restored, note=f"rollback->{version}", approved_by="user")
            logger.info("strategy_rolledback", version=version)
            return restored, "OK"
    return None, f"version {version} not found in history"


# ── 대기 제안 (HiL 승인) ──

async def aput_pending_proposal(payload: dict) -> str:
    """대기 제안 저장. proposal_id 반환. 24시간 TTL."""
    pid = uuid.uuid4().hex[:12]
    payload = {**payload, "id": pid}
    await get_async_redis().set(
        _PENDING_PREFIX + pid, json.dumps(payload, ensure_ascii=False), ex=86400
    )
    return pid


async def aget_pending_proposal(pid: str) -> dict | None:
    raw = await get_async_redis().get(_PENDING_PREFIX + pid)
    return json.loads(raw) if raw else None


async def adelete_pending_proposal(pid: str) -> None:
    await get_async_redis().delete(_PENDING_PREFIX + pid)
