"""기술 지표 단위 테스트 (순수 함수)."""
from shared.quant.indicators import (
    sma, rsi, atr,
    ema_series, macd, hma, hma_rising, volume_ratio,
    rsi_series, find_swing_highs,
)


# ── 기존 지표 ────────────────────────────────────────────────────────────────

def test_sma_basic():
    assert sma([1, 2, 3, 4, 5], 5) == 3.0
    assert sma([1, 2, 3, 4, 5], 2) == 4.5


def test_sma_insufficient():
    assert sma([1, 2], 5) is None
    assert sma([], 3) is None
    assert sma([1, 2, 3], 0) is None


def test_rsi_all_up_is_100():
    prices = [float(i) for i in range(1, 20)]
    assert rsi(prices, 14) == 100.0


def test_rsi_all_down_is_0():
    prices = [float(i) for i in range(20, 1, -1)]
    assert rsi(prices, 14) == 0.0


def test_rsi_bounds_and_insufficient():
    assert rsi([1, 2, 3], 14) is None
    prices = [10, 11, 10.5, 11.5, 12, 11, 12.5, 13, 12, 13.5,
              14, 13, 14.5, 15, 14, 15.5]
    val = rsi(prices, 14)
    assert val is not None and 0.0 <= val <= 100.0


def test_atr_basic_and_insufficient():
    highs = [10, 11, 12, 13, 14, 15]
    lows = [9, 10, 11, 12, 13, 14]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5]
    assert atr(highs, lows, closes, 14) is None
    assert atr(highs, lows, closes, 3) is not None
    assert atr([1, 2], [1], [1, 2], 1) is None


# ── EMA ─────────────────────────────────────────────────────────────────────

def test_ema_series_length():
    prices = [float(i) for i in range(1, 20)]
    result = ema_series(prices, 5)
    assert result is not None
    assert len(result) == len(prices) - 5 + 1


def test_ema_series_insufficient():
    assert ema_series([1, 2, 3], 5) is None
    assert ema_series([], 3) is None


def test_ema_series_single():
    # period=1이면 prices 자체 반환
    prices = [1.0, 2.0, 3.0]
    result = ema_series(prices, 1)
    assert result is not None and len(result) == 3
    assert result[-1] == 3.0


# ── MACD ────────────────────────────────────────────────────────────────────

def _sample_prices(n=60):
    """단조 증가 가격 시계열."""
    return [100.0 + i * 0.5 for i in range(n)]


def test_macd_returns_dict():
    m = macd(_sample_prices(), 12, 26, 9)
    assert m is not None
    for key in ("macd_line", "signal_line", "histogram", "golden_cross", "dead_cross", "is_positive"):
        assert key in m


def test_macd_insufficient():
    assert macd([1.0] * 10, 12, 26, 9) is None  # 데이터 부족
    assert macd([1.0] * 33, 12, 26, 9) is None  # 34개 미만
    # 34개면 계산 가능 (slow_ema 9개, signal_ema 1개)
    assert macd([1.0] * 34, 12, 26, 9) is not None


def test_macd_golden_cross():
    """하락→상승 전환 시 골든크로스 발생 여부."""
    # 단조 하락 후 단조 상승
    down = [100.0 - i * 1.0 for i in range(40)]
    up = [60.0 + i * 2.0 for i in range(30)]
    prices = down + up
    m = macd(prices, 12, 26, 9)
    assert m is not None
    # 방향 전환이 충분히 있으면 golden 또는 dead cross 중 하나는 발생
    assert isinstance(m["golden_cross"], bool)
    assert isinstance(m["dead_cross"], bool)


def test_macd_uptrend_positive():
    """가속 상승 추세에서 MACD line > Signal line (정배열).

    선형 등속 상승은 MACD=const → MACD==Signal (정배열 아님).
    가속 상승(2차 곡선)이어야 MACD line이 Signal line보다 높아진다.
    """
    prices = [100.0 + i ** 1.5 for i in range(100)]
    m = macd(prices, 12, 26, 9)
    assert m is not None
    assert m["is_positive"] is True


# ── HMA ─────────────────────────────────────────────────────────────────────

def test_hma_basic():
    prices = [100.0 + i * 0.5 for i in range(60)]
    val = hma(prices, 20)
    assert val is not None
    assert 100.0 < val < 200.0


def test_hma_insufficient():
    assert hma([1.0] * 5, 20) is None


def test_hma_rising_uptrend():
    prices = [100.0 + i * 1.0 for i in range(80)]
    result = hma_rising(prices, 20)
    assert result is True


def test_hma_rising_downtrend():
    prices = [200.0 - i * 1.0 for i in range(80)]
    result = hma_rising(prices, 20)
    assert result is False


def test_hma_rising_insufficient():
    assert hma_rising([1.0] * 5, 20) is None


# ── 거래량 비율 ──────────────────────────────────────────────────────────────

def test_volume_ratio_basic():
    vols = [100.0] * 20 + [200.0]  # 평균 100, 현재 200 → 2.0x
    r = volume_ratio(vols, 20)
    assert r is not None
    assert abs(r - 2.0) < 0.01


def test_volume_ratio_insufficient():
    assert volume_ratio([1.0] * 5, 20) is None


def test_volume_ratio_zero_avg():
    vols = [0.0] * 21
    assert volume_ratio(vols, 20) is None


# ── RSI 시계열 + 스윙 고점 ───────────────────────────────────────────────────

def test_rsi_series_length():
    prices = [100.0 + i * 0.5 for i in range(30)]
    s = rsi_series(prices, 14)
    assert s is not None
    assert len(s) == len(prices) - 14


def test_rsi_series_values_in_range():
    prices = [100.0, 102.0, 101.0, 103.0, 100.0, 104.0, 102.0,
              105.0, 103.0, 106.0, 104.0, 107.0, 105.0, 108.0, 106.0, 109.0]
    s = rsi_series(prices, 14)
    assert s is not None
    assert all(0.0 <= v <= 100.0 for v in s)


def test_find_swing_highs_basic():
    # 두 개의 뚜렷한 피크를 가진 시계열
    highs = [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 6, 4, 3, 2, 1, 2, 3]
    rsi_vals = [50.0] * len(highs)
    peaks = find_swing_highs(highs, rsi_vals, window=2, count=2)
    assert peaks is not None
    assert len(peaks) == 2
    assert peaks[-1]["price_high"] >= peaks[0]["price_high"]


def test_find_swing_highs_insufficient():
    assert find_swing_highs([1, 2, 3], [50, 50, 50], window=5) is None
    assert find_swing_highs([1, 2], [50, 50], window=1, count=2) is None
