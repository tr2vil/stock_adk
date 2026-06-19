"""기술 지표 단위 테스트 (순수 함수)."""
from shared.quant.indicators import sma, rsi, atr


def test_sma_basic():
    assert sma([1, 2, 3, 4, 5], 5) == 3.0
    assert sma([1, 2, 3, 4, 5], 2) == 4.5


def test_sma_insufficient():
    assert sma([1, 2], 5) is None
    assert sma([], 3) is None
    assert sma([1, 2, 3], 0) is None


def test_rsi_all_up_is_100():
    prices = [float(i) for i in range(1, 20)]  # 단조 증가
    assert rsi(prices, 14) == 100.0


def test_rsi_all_down_is_0():
    prices = [float(i) for i in range(20, 1, -1)]  # 단조 감소
    assert rsi(prices, 14) == 0.0


def test_rsi_bounds_and_insufficient():
    assert rsi([1, 2, 3], 14) is None  # 데이터 부족
    prices = [10, 11, 10.5, 11.5, 12, 11, 12.5, 13, 12, 13.5,
              14, 13, 14.5, 15, 14, 15.5]
    val = rsi(prices, 14)
    assert val is not None and 0.0 <= val <= 100.0


def test_atr_basic_and_insufficient():
    highs = [10, 11, 12, 13, 14, 15]
    lows = [9, 10, 11, 12, 13, 14]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5]
    assert atr(highs, lows, closes, 14) is None  # 데이터 부족
    assert atr(highs, lows, closes, 3) is not None
    # 길이 불일치 → None
    assert atr([1, 2], [1], [1, 2], 1) is None
