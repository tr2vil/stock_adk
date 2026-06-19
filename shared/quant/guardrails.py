"""진화 안전장치 — LLM 제안 검증·적용·버전 관리 (순수 함수, 결정론적).

LLM(Evolution Agent)이 비합리적/위험한 파라미터를 제안해도 시스템을 보호한다.
설계서 5.4 가드레일을 구현하되, 다음을 강제한다.

- 허용 목록(allow-list): EVOLUTION_GUARDRAILS 에 명시된 파라미터만 변경 가능.
  position.* 등 미명시 파라미터 변경 제안은 무조건 거부 → 리스크 안전구역 보호.
- 범위 검증: 각 제안값이 [low, high] 이내여야 한다.
- 타입 검증: ma_period 는 정수.
- 교차 검증: 적용 후 rsi_buy_threshold < rsi_sell_threshold 유지.
"""
from __future__ import annotations

import copy

from .schema import StrategyConfig, EvolutionProposal, ProposedChange

# 파라미터별 허용 범위 (이 목록에 없으면 변경 불가)
# 설계서 5.4 명시값 + (확장) ma_period / confidence_min 범위.
EVOLUTION_GUARDRAILS: dict[str, tuple[float, float]] = {
    "momentum.rsi_buy_threshold": (15, 40),
    "momentum.rsi_sell_threshold": (60, 85),
    "momentum.ma_period": (5, 60),            # 확장: 설계서 미명시 → 합리적 범위 지정
    "momentum.sentiment_min": (-0.5, 0.3),
    "stop_loss.rate": (0.03, 0.15),
    "news_defense.sentiment_threshold": (-0.9, -0.5),
    "news_defense.confidence_min": (0.5, 0.95),  # 확장
}

# 정수여야 하는 파라미터
INT_PARAMS = {"momentum.ma_period"}


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
    """시맨틱 버전 마이너 증가: '1.2.0' → '1.3.0'. 파싱 실패 시 '.N' 부가."""
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
    """검증 통과 시 제안을 적용한 새 StrategyConfig 를 반환.

    Returns:
        (new_strategy, applied_changes, error)
        - 성공: (StrategyConfig, [{param,current,proposed}, ...], None)
        - 실패: (None, [], "사유")
    원본 strategy 는 변경하지 않는다.
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

    # 교차 검증: 적용 후 매수 임계값 < 매도 임계값
    if data["momentum"]["rsi_buy_threshold"] >= data["momentum"]["rsi_sell_threshold"]:
        return None, [], (
            f"rsi_buy_threshold({data['momentum']['rsi_buy_threshold']}) must be "
            f"< rsi_sell_threshold({data['momentum']['rsi_sell_threshold']})"
        )

    data["version"] = bump_version(strategy.version)
    data["updated_at"] = now_iso
    data["updated_by"] = approved_by or "evolution_agent"

    new_strategy = StrategyConfig.model_validate(data)
    return new_strategy, applied, None
