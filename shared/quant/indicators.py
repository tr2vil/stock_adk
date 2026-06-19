"""기술 지표 — 순수 함수 (외부 의존성 없음, 결정론적).

가격 시계열(list[float], 오래된→최신 순)을 입력받아 지표를 계산한다.
데이터 부족 시 None 을 반환하여 호출측에서 안전하게 처리하게 한다.
"""
from __future__ import annotations


def sma(prices: list[float], period: int) -> float | None:
    """단순 이동평균. 데이터가 period 미만이면 None."""
    if period <= 0 or len(prices) < period:
        return None
    window = prices[-period:]
    return sum(window) / period


def rsi(prices: list[float], period: int = 14) -> float | None:
    """Wilder RSI. 데이터가 period+1 미만이면 None.

    상승/하락 평균을 Wilder 평활(smoothing)로 계산한다.
    """
    if period <= 0 or len(prices) < period + 1:
        return None

    gains, losses = [], []
    for prev, cur in zip(prices, prices[1:]):
        diff = cur - prev
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    # 초기 평균 (첫 period 구간)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder 평활로 최신까지 진행
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 4)


def atr(highs: list[float], lows: list[float], closes: list[float],
        period: int = 14) -> float | None:
    """Average True Range. 세 시계열 길이가 같고 period+1 이상이어야 한다."""
    n = len(closes)
    if not (len(highs) == len(lows) == n) or n < period + 1:
        return None

    trs = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)

    # Wilder 평활
    cur = sum(trs[:period]) / period
    for tr in trs[period:]:
        cur = (cur * (period - 1) + tr) / period
    return round(cur, 4)
