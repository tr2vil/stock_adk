"""Rule-based 매매 신호 생성 — 순수 함수, LLM 미사용, 완전 결정론적.

strategy.yaml(StrategyConfig)을 입력으로 받아 BUY/SELL/HOLD 를 산출한다.
설계서 4.4 generate_signal 규칙을 그대로 구현하되, 판단 근거(reasoning)도 함께 반환한다.

우선순위:
1. 뉴스 방어   : 감성 < threshold AND 신뢰도 > confidence_min  → HOLD (매수 차단)
2. 손절        : 보유 중 가격 < 진입가 × (1 - stop_loss.rate) → SELL
3. 모멘텀 매도 : RSI > rsi_sell_threshold AND 감성 < 0.2        → SELL
4. 모멘텀 매수 : RSI < rsi_buy_threshold AND 가격 > MA AND 감성 > sentiment_min → BUY
5. 그 외       : HOLD
"""
from __future__ import annotations

from .schema import StrategyConfig

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"


def generate_signal(
    strategy: StrategyConfig,
    *,
    rsi: float | None,
    price: float,
    ma: float | None,
    sentiment: float,
    confidence: float,
    entry_price: float | None = None,
) -> dict:
    """신호 + 근거를 반환.

    Args:
        strategy: 활성 전략
        rsi: 현재 RSI (None이면 모멘텀 규칙 평가 생략)
        price: 현재가
        ma: 이동평균 (None이면 매수 조건의 MA 비교 생략)
        sentiment: 감성 점수 (-1.0 ~ 1.0)
        confidence: 감성 신뢰도 (0.0 ~ 1.0)
        entry_price: 보유 종목 진입가 (None이면 손절 규칙 생략)

    Returns:
        dict: {"signal": "BUY"|"SELL"|"HOLD", "reasoning": str}
    """
    m = strategy.momentum
    nd = strategy.news_defense
    sl = strategy.stop_loss

    # 1. 뉴스 방어 (매수 차단)
    if sentiment < nd.sentiment_threshold and confidence > nd.confidence_min:
        return {
            "signal": HOLD,
            "reasoning": (
                f"뉴스 방어 발동: 감성 {sentiment:.2f} < {nd.sentiment_threshold} "
                f"(신뢰도 {confidence:.2f})"
            ),
        }

    # 2. 손절
    if entry_price and price < entry_price * (1 - sl.rate):
        return {
            "signal": SELL,
            "reasoning": (
                f"손절: 현재가 {price} < 진입가 {entry_price} × (1-{sl.rate})"
            ),
        }

    # 3. 모멘텀 매도
    if rsi is not None and rsi > m.rsi_sell_threshold and sentiment < 0.2:
        return {
            "signal": SELL,
            "reasoning": f"모멘텀 매도: RSI {rsi:.1f} > {m.rsi_sell_threshold}, 감성 {sentiment:.2f}",
        }

    # 4. 모멘텀 매수
    if (
        rsi is not None
        and rsi < m.rsi_buy_threshold
        and (ma is None or price > ma)
        and sentiment > m.sentiment_min
    ):
        return {
            "signal": BUY,
            "reasoning": (
                f"모멘텀 매수: RSI {rsi:.1f} < {m.rsi_buy_threshold}, "
                f"가격 {price} > MA {ma}, 감성 {sentiment:.2f} > {m.sentiment_min}"
            ),
        }

    return {"signal": HOLD, "reasoning": "조건 미충족"}
