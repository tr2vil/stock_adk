"""진화 안전장치 — LLM 제안 검증·적용·버전 관리 (순수 함수, 결정론적).

MACD+RSI 전략 v2 대응. 허용목록 방식으로 Evolution Agent가 변경 가능한
파라미터와 그 범위를 엄격히 제한한다.

- 허용 목록(allow-list): EVOLUTION_GUARDRAILS에 명시된 파라미터만 변경 가능.
  position.* 등 미명시 파라미터는 무조건 거부.
- 범위 검증: 각 제안값이 [low, high] 이내여야 한다.
- 타입 검증: INT_PARAMS는 정수.
- 교차 검증: macd.fast < macd.slow, rsi.buy_low < rsi.buy_high.
"""
from __future__ import annotations

import copy

from .schema import StrategyConfig, EvolutionProposal, ProposedChange  # noqa: F401

# 파라미터별 허용 범위 (이 목록에 없으면 변경 불가)
EVOLUTION_GUARDRAILS: dict[str, tuple[float, float]] = {
    # RSI 진입/청산 임계값
    "rsi.buy_low": (40.0, 55.0),
    "rsi.buy_high": (65.0, 80.0),
    "rsi.pullback_zone_high": (50.0, 62.0),
    # MACD 기간
    "macd.fast": (8, 20),
    "macd.slow": (20, 35),
    # 거래량 필터
    "volume_filter.multiplier": (1.0, 3.0),
    "volume_filter.lookback": (10, 30),
    # HMA 기간 (구조 파라미터인 timeframe/enabled는 변경 불가)
    "hma_filter.period": (20, 200),
    # 손절 룩백
    "stop_loss.lookback_candles": (5, 20),
}

# 정수여야 하는 파라미터
INT_PARAMS = {
    "macd.fast", "macd.slow",
    "hma_filter.period",
    "stop_loss.lookback_candles",
    "volume_filter.lookback",
}


def _as_proposal(proposal) -> EvolutionProposal:
    if isinstance(proposal, EvolutionProposal):
        return proposal
    return EvolutionProposal.model_validate(proposal)


def validate_proposal(proposal) -> tuple[bool, str]:
    """제안의 모든 변경이 가드레일을 통과하는지 검증.

    Returns:
        (ok, message). ok=False면 message에 첫 위반 사유.
    """
    prop = _as_proposal(proposal)
    if not prop.changes:
        return False, "no changes proposed"

    for ch in prop.changes:
        param = ch.param
        if param not in EVOLUTION_GUARDRAILS:
            return False, f"{param}: not an evolvable parameter (protected)"
        value = ch.proposed
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False, f"{param}: proposed value must be numeric (got {value!r})"
        if param in INT_PARAMS and float(value) != int(value):
            return False, f"{param}: must be an integer (got {value})"
        low, high = EVOLUTION_GUARDRAILS[param]
        if not (low <= value <= high):
            return False, f"{param}: {value} is out of range [{low}, {high}]"

    return True, "OK"


def bump_version(version: str) -> str:
    """시맨틱 버전 마이너 증가: '2.0.0' → '2.1.0'."""
    parts = version.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
        return f"{major}.{minor + 1}.0"
    except (IndexError, ValueError):
        return f"{version}.1"


def apply_proposal(
    strategy: StrategyConfig,
    proposal,
    *,
    approved_by: str = "user",
    now_iso: str = "",
) -> tuple[StrategyConfig | None, list[dict], str | None]:
    """검증 통과 시 제안을 적용한 새 StrategyConfig를 반환.

    Returns:
        (new_strategy, applied_changes, error)
        - 성공: (StrategyConfig, [{param,current,proposed}, ...], None)
        - 실패: (None, [], "사유")
    원본 strategy는 변경하지 않는다.
    """
    ok, msg = validate_proposal(proposal)
    if not ok:
        return None, [], msg

    prop = _as_proposal(proposal)
    data = copy.deepcopy(strategy.model_dump())

    applied: list[dict] = []
    for ch in prop.changes:
        section, _, key = ch.param.partition(".")
        value = int(ch.proposed) if ch.param in INT_PARAMS else float(ch.proposed)
        current = data[section][key]
        data[section][key] = value
        applied.append({"param": ch.param, "current": current, "proposed": value})

    # 교차 검증: macd.fast < macd.slow
    if data["macd"]["fast"] >= data["macd"]["slow"]:
        return None, [], (
            f"macd.fast({data['macd']['fast']}) must be < macd.slow({data['macd']['slow']})"
        )

    # 교차 검증: rsi.buy_low < rsi.buy_high
    if data["rsi"]["buy_low"] >= data["rsi"]["buy_high"]:
        return None, [], (
            f"rsi.buy_low({data['rsi']['buy_low']}) must be < rsi.buy_high({data['rsi']['buy_high']})"
        )

    data["version"] = bump_version(strategy.version)
    data["updated_at"] = now_iso
    data["updated_by"] = approved_by or "evolution_agent"

    new_strategy = StrategyConfig.model_validate(data)
    return new_strategy, applied, None
