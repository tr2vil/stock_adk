"""기술 지표 — 순수 함수 (외부 의존성 없음, 결정론적).

가격 시계열(list[float], 오래된→최신 순)을 입력받아 지표를 계산한다.
데이터 부족 시 None 을 반환하여 호출측에서 안전하게 처리하게 한다.
"""
from __future__ import annotations

import math


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


def ema_series(prices: list[float], period: int) -> list[float] | None:
    """지수 이동평균 전체 시계열 (오래된→최신). MACD 계산용.

    시드는 첫 period개의 SMA로 설정하고 이후 EMA로 평활한다.
    반환 길이 = len(prices) - period + 1.
    """
    if period <= 0 or len(prices) < period:
        return None
    k = 2.0 / (period + 1)
    seed = sum(prices[:period]) / period
    result = [seed]
    for p in prices[period:]:
        result.append(p * k + result[-1] * (1 - k))
    return result


def macd(
    prices: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> dict | None:
    """MACD (이동평균 수렴·발산) 지표.

    Args:
        prices: 종가 시계열 (오래된→최신)
        fast: 단기 EMA 기간 (기본 12)
        slow: 장기 EMA 기간 (기본 26)
        signal_period: 시그널 EMA 기간 (기본 9)

    Returns:
        dict: macd_line·signal_line·histogram (현재/이전), golden_cross·dead_cross·is_positive
        None: 데이터 부족 (최소 slow + signal_period - 1 개 필요)
    """
    if len(prices) < slow + signal_period - 1:
        return None

    fast_s = ema_series(prices, fast)
    slow_s = ema_series(prices, slow)
    if fast_s is None or slow_s is None:
        return None

    n = len(slow_s)
    fast_aligned = fast_s[len(fast_s) - n:]
    macd_s = [f - s for f, s in zip(fast_aligned, slow_s)]

    if len(macd_s) < signal_period:
        return None

    sig_s = ema_series(macd_s, signal_period)
    if sig_s is None:
        return None

    ns = len(sig_s)
    macd_aligned = macd_s[len(macd_s) - ns:]

    m_cur, s_cur = macd_aligned[-1], sig_s[-1]
    h_cur = m_cur - s_cur
    m_prev = macd_aligned[-2] if ns >= 2 else None
    s_prev = sig_s[-2] if ns >= 2 else None
    h_prev = (m_prev - s_prev) if (m_prev is not None and s_prev is not None) else None

    golden = m_prev is not None and s_prev is not None and m_prev <= s_prev and m_cur > s_cur
    dead = m_prev is not None and s_prev is not None and m_prev >= s_prev and m_cur < s_cur

    return {
        "macd_line": round(m_cur, 6),
        "signal_line": round(s_cur, 6),
        "histogram": round(h_cur, 6),
        "macd_prev": round(m_prev, 6) if m_prev is not None else None,
        "signal_prev": round(s_prev, 6) if s_prev is not None else None,
        "histogram_prev": round(h_prev, 6) if h_prev is not None else None,
        "golden_cross": golden,
        "dead_cross": dead,
        "is_positive": m_cur > s_cur,
    }


def _wma_series(prices: list[float], period: int) -> list[float] | None:
    """가중 이동평균 전체 시계열 (HMA 내부용)."""
    if period <= 0 or len(prices) < period:
        return None
    w = list(range(1, period + 1))
    w_sum = sum(w)
    return [
        sum(wt * p for wt, p in zip(w, prices[i - period + 1:i + 1])) / w_sum
        for i in range(period - 1, len(prices))
    ]


def hma(prices: list[float], period: int) -> float | None:
    """Hull Moving Average 최신 단일값.

    HMA(n) = WMA(2·WMA(n/2) − WMA(n), √n)
    """
    half = max(1, period // 2)
    sqrt_n = max(1, int(math.sqrt(period)))

    s_half = _wma_series(prices, half)
    s_full = _wma_series(prices, period)
    if s_half is None or s_full is None:
        return None

    n_full = len(s_full)
    if len(s_half) < n_full:
        return None

    raw = [2 * h - f for h, f in zip(s_half[len(s_half) - n_full:], s_full)]
    final = _wma_series(raw, sqrt_n)
    return round(final[-1], 4) if final else None


def hma_rising(prices: list[float], period: int, lookback: int = 2) -> bool | None:
    """HMA 상승 여부 (최근 lookback+1 개 HMA 값이 연속 상승인지).

    Returns:
        True: 상승 추세, False: 하락·횡보, None: 데이터 부족
    """
    half = max(1, period // 2)
    sqrt_n = max(1, int(math.sqrt(period)))

    s_half = _wma_series(prices, half)
    s_full = _wma_series(prices, period)
    if s_half is None or s_full is None:
        return None

    n_full = len(s_full)
    if len(s_half) < n_full:
        return None

    raw = [2 * h - f for h, f in zip(s_half[len(s_half) - n_full:], s_full)]
    hma_s = _wma_series(raw, sqrt_n)
    if not hma_s or len(hma_s) < lookback + 1:
        return None

    vals = hma_s[-(lookback + 1):]
    return all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))


def volume_ratio(volumes: list[float], lookback: int = 20) -> float | None:
    """현재 거래량 / 최근 lookback개 평균 거래량 배수.

    Returns:
        float: 배수 (1.5 = 평균의 1.5배), None: 데이터 부족 또는 평균 0
    """
    if lookback <= 0 or len(volumes) < lookback + 1:
        return None
    avg = sum(volumes[-lookback - 1:-1]) / lookback
    if avg == 0:
        return None
    return round(volumes[-1] / avg, 3)


def rsi_series(prices: list[float], period: int = 14) -> list[float] | None:
    """Wilder RSI 전체 시계열 (다이버전스 감지용).

    반환 길이 = len(prices) - period.
    """
    if period <= 0 or len(prices) < period + 1:
        return None

    diffs = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
    gains = [max(d, 0.0) for d in diffs]
    losses = [max(-d, 0.0) for d in diffs]

    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period

    def _to_rsi(g: float, l: float) -> float:
        if l == 0:
            return 100.0
        rs = g / l
        return round(100.0 - 100.0 / (1.0 + rs), 4)

    result = [_to_rsi(avg_g, avg_l)]
    for g, l in zip(gains[period:], losses[period:]):
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + l) / period
        result.append(_to_rsi(avg_g, avg_l))

    return result


def find_swing_highs(
    highs: list[float],
    rsi_vals: list[float],
    window: int = 5,
    count: int = 2,
) -> list[dict] | None:
    """최근 스윙 고점 목록 (RSI 하락 다이버전스 감지용).

    Args:
        highs: 캔들 고가 시계열
        rsi_vals: 동일 길이 RSI 시계열
        window: 스윙 고점 판별 윈도우 (양쪽 각 window개)
        count: 반환할 최근 스윙 고점 수

    Returns:
        list[dict]: [{"index", "price_high", "rsi_high"}, ...] (오래된→최신)
        None: 스윙 고점이 count개 미만
    """
    if len(highs) != len(rsi_vals) or len(highs) < window * 2 + 1:
        return None

    peaks = []
    for i in range(window, len(highs) - window):
        left = highs[i - window:i]
        right = highs[i + 1:i + window + 1]
        if highs[i] >= max(left) and highs[i] >= max(right):
            peaks.append({"index": i, "price_high": highs[i], "rsi_high": rsi_vals[i]})

    return peaks[-count:] if len(peaks) >= count else None


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
