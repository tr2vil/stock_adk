"""
Decision Engine - 가중 합산 및 최종 판단 로직
Based on TRADING_SYSTEM_SPEC.md Section 4.2
"""
import json

from shared.models import TradeDecision, Market, SignalStrength
from shared.redis_client import get_sync_redis, seed_defaults
from shared.logger import get_logger

_logger = get_logger("orchestrator.decision_engine")

# Default values (used as fallback and for Redis seeding)
_DEFAULT_WEIGHTS = {
    "technical": 0.30,
    "fundamental": 0.25,
    "news": 0.20,
    "expert": 0.15,
    "risk": 0.10,
}

_DEFAULT_THRESHOLDS = {
    "buy": 0.3,
    "sell": -0.3,
}

# Seed defaults into Redis (only if keys do not exist)
seed_defaults({
    "weights": json.dumps(_DEFAULT_WEIGHTS),
    "thresholds": json.dumps(_DEFAULT_THRESHOLDS),
})


def _load_weights() -> dict:
    try:
        raw = get_sync_redis().get("weights")
        if raw:
            return json.loads(raw)
    except Exception as e:
        _logger.warning("weights_load_failed", error=str(e))
    return dict(_DEFAULT_WEIGHTS)


def _load_thresholds() -> dict:
    try:
        raw = get_sync_redis().get("thresholds")
        if raw:
            return json.loads(raw)
    except Exception as e:
        _logger.warning("thresholds_load_failed", error=str(e))
    return dict(_DEFAULT_THRESHOLDS)


# Agent weights for final score calculation
WEIGHTS = _load_weights()

# Decision thresholds
THRESHOLDS = _load_thresholds()


def reload_config():
    """Reload WEIGHTS and THRESHOLDS from Redis."""
    global WEIGHTS, THRESHOLDS
    WEIGHTS = _load_weights()
    THRESHOLDS = _load_thresholds()
    _logger.info("config_reloaded", weights=WEIGHTS, thresholds=THRESHOLDS)

# Signal to score mapping
SIGNAL_SCORES = {
    SignalStrength.STRONG_BUY: 1.0,
    SignalStrength.BUY: 0.5,
    SignalStrength.HOLD: 0.0,
    SignalStrength.SELL: -0.5,
    SignalStrength.STRONG_SELL: -1.0,
    "strong_buy": 1.0,
    "buy": 0.5,
    "hold": 0.0,
    "sell": -0.5,
    "strong_sell": -1.0,
}


def signal_to_score(signal: str | SignalStrength) -> float:
    """Convert signal string to numeric score."""
    if isinstance(signal, str):
        signal = signal.lower().strip()
    return SIGNAL_SCORES.get(signal, 0.0)


def compute_final_score(agent_results: dict[str, float]) -> float:
    """각 Agent 스코어를 가중 합산합니다.

    Args:
        agent_results: Dict mapping agent name to score (-1.0 to 1.0)
            예: {"technical": 0.5, "fundamental": 0.3, "news": 0.2, ...}

    Returns:
        float: Weighted final score
    """
    score = sum(
        agent_results.get(key, 0.0) * weight
        for key, weight in WEIGHTS.items()
    )
    return round(score, 4)


def determine_action(final_score: float) -> str:
    """Determine trade action based on final score.

    Args:
        final_score: Weighted score from compute_final_score

    Returns:
        str: "BUY", "SELL", or "HOLD"
    """
    if final_score > THRESHOLDS["buy"]:
        return "BUY"
    elif final_score < THRESHOLDS["sell"]:
        return "SELL"
    else:
        return "HOLD"


def make_decision(
    ticker: str,
    market: Market,
    agent_results: dict[str, float],
    risk_output: dict,
    current_price: float = 0.0,
) -> TradeDecision:
    """최종 매매 의사결정을 생성합니다.

    Args:
        ticker: 종목코드
        market: Market enum (KR or US)
        agent_results: Dict mapping agent name to score
        risk_output: Output from risk_agent containing position sizing info
        current_price: Current stock price

    Returns:
        TradeDecision: Final trade decision with all parameters
    """
    final_score = compute_final_score(agent_results)
    action = determine_action(final_score)

    # Get position size from risk agent output
    quantity = risk_output.get("position_size", 0)

    # If risk level is HIGH, reduce quantity by 50%
    if risk_output.get("risk_level") == "high":
        quantity = max(1, quantity // 2)

    # If action is HOLD, set quantity to 0
    if action == "HOLD":
        quantity = 0

    # Get price levels from risk agent
    stop_loss = risk_output.get("stop_loss_price", 0.0)
    take_profit = risk_output.get("take_profit_price", 0.0)
    target_price = current_price or risk_output.get("current_price", 0.0)

    # Build reasoning
    score_parts = [f"{k}: {v:.2f}" for k, v in agent_results.items()]
    reasoning = f"가중합산 {final_score:.3f} → {action}. 개별점수: {', '.join(score_parts)}"

    return TradeDecision(
        ticker=ticker,
        market=market,
        action=action,
        final_score=final_score,
        quantity=quantity,
        target_price=target_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reasoning=reasoning,
        agent_scores=agent_results,
    )
