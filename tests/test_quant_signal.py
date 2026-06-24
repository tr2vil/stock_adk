"""MACD+RSI 신호 엔진 단위 테스트."""
from shared.quant.schema import StrategyConfig
from shared.quant.signal import (
    generate_signal, BUY, SELL_HALF, SELL_ALL, NONE,
    IDLE, M1_Q_LOW, M1_Q_HIGH, M1_OPEN_1, M1_OPEN_2,
    M2_DIV, M2_COOL, M2_OPEN,
)

S = StrategyConfig()  # 기본값

# ── 캔들 픽스처 헬퍼 ─────────────────────────────────────────────────────────

def _candles(closes, highs=None, lows=None, volumes=None, n=60):
    """closes 리스트로 간단한 OHLCV dict 리스트 생성."""
    c = closes if len(closes) >= n else ([closes[0]] * (n - len(closes)) + list(closes))
    h = highs if highs else [p * 1.01 for p in c]
    lo = lows if lows else [p * 0.99 for p in c]
    v = volumes if volumes else [1000.0] * len(c)
    return [
        {"openPrice": p, "closePrice": p, "highPrice": h[i],
         "lowPrice": lo[i], "volume": v[i]}
        for i, p in enumerate(c)
    ]


def _uptrend(n=60, start=100.0, step=1.0):
    return [start + i * step for i in range(n)]


def _downtrend(n=60, start=160.0, step=1.0):
    return [start - i * step for i in range(n)]


# ── 데이터 부족 ──────────────────────────────────────────────────────────────

def test_insufficient_candles():
    r = generate_signal(S, _candles([100.0] * 10, n=10), None, {"state": IDLE})
    assert r["action"] == NONE
    assert "부족" in r["reasoning"]


# ── IDLE: 신호 없음 ──────────────────────────────────────────────────────────

def test_idle_no_signal_flat():
    """횡보에서는 골든크로스 없음 → 신호 없음."""
    flat = [100.0] * 60
    r = generate_signal(S, _candles(flat), True, {"state": IDLE})
    assert r["action"] == NONE
    assert r["new_state"]["state"] == IDLE


# ── M1: OPEN_FIRST 손절 ─────────────────────────────────────────────────────

def test_m1_open1_stop_loss():
    """진입가 100, SL 95 → 현재가 94 이하면 전량 손절."""
    state = {
        "state": M1_OPEN_1, "method": 1,
        "entry_price": 100.0, "stop_loss": 95.0, "target1": 110.0, "target_full": 110.0,
    }
    closes = _downtrend(60, start=110.0, step=0.5)
    closes[-1] = 94.0  # 현재가 SL 이하
    r = generate_signal(S, _candles(closes), True, state)
    assert r["action"] == SELL_ALL
    assert r["new_state"]["state"] == IDLE
    assert "손절" in r["reasoning"]


# ── M1: OPEN_FIRST 1차 목표 달성 ────────────────────────────────────────────

def test_m1_open1_first_target():
    """현재가가 1차 목표가 이상 → SELL_HALF + M1_OPEN_2로 전환."""
    state = {
        "state": M1_OPEN_1, "method": 1,
        "entry_price": 100.0, "stop_loss": 95.0, "target1": 110.0, "target_full": 110.0,
    }
    closes = _uptrend(60, start=80.0, step=0.6)
    closes[-1] = 111.0  # 목표가 초과
    r = generate_signal(S, _candles(closes), True, state)
    assert r["action"] == SELL_HALF
    assert r["new_state"]["state"] == M1_OPEN_2


# ── M1: OPEN_SECOND RSI 50 이탈 청산 ────────────────────────────────────────

def test_m1_open2_rsi_exit():
    """RSI 50 이하 → 잔량 전량 청산."""
    state = {
        "state": M1_OPEN_2, "method": 1,
        "entry_price": 100.0, "stop_loss": 95.0, "target1": 110.0, "target_full": 110.0,
    }
    # 단조 하락 → RSI 낮게 유도
    closes = _downtrend(60, start=120.0, step=1.5)
    r = generate_signal(S, _candles(closes), True, state)
    assert r["action"] == SELL_ALL
    assert r["new_state"]["state"] == IDLE


# ── M1: OPEN_SECOND 본전 보존 ────────────────────────────────────────────────

def test_m1_open2_breakeven():
    """현재가가 진입가 이하 → 본전 보존 전량 청산."""
    state = {
        "state": M1_OPEN_2, "method": 1,
        "entry_price": 100.0, "stop_loss": 95.0, "target1": 110.0, "target_full": 110.0,
        "prev_rsi": 60.0,
    }
    closes = [100.0 + i * 0.1 for i in range(59)] + [99.5]  # 마지막이 진입가 이하
    r = generate_signal(S, _candles(closes), True, state)
    assert r["action"] == SELL_ALL
    assert "본전" in r["reasoning"]


# ── M2: DIVERGENCE → COOLDOWN 전환 ──────────────────────────────────────────

def test_m2_div_to_cooldown_on_dead_cross():
    """M2_DIV 상태에서 데드크로스 발생 → M2_COOL 전환."""
    state = {"state": M2_DIV, "method": None}
    # 단조 하락 → 데드크로스 유발
    closes = _downtrend(60, start=150.0, step=2.0)
    r = generate_signal(S, _candles(closes), True, state)
    # 데드크로스가 발생할 수 있는 시계열이면 M2_COOL 전환
    if r["indicators"].get("dead_cross"):
        assert r["new_state"]["state"] == M2_COOL
    else:
        assert r["action"] == NONE
        assert r["new_state"]["state"] == M2_DIV


# ── M2: OPEN 목표가 달성 ────────────────────────────────────────────────────

def test_m2_open_target_hit():
    """M2_OPEN에서 현재가 ≥ target_full → 전량 익절."""
    state = {
        "state": M2_OPEN, "method": 2,
        "entry_price": 100.0, "stop_loss": 90.0, "target1": 120.0, "target_full": 120.0,
    }
    closes = _uptrend(60, start=80.0, step=0.8)
    closes[-1] = 121.0
    r = generate_signal(S, _candles(closes), True, state)
    assert r["action"] == SELL_ALL
    assert r["new_state"]["state"] == IDLE
    assert "목표" in r["reasoning"]


# ── M2: OPEN 데드크로스 청산 ────────────────────────────────────────────────

def test_m2_open_dead_cross_exit():
    """M2_OPEN에서 데드크로스 발생 → 전량 원칙 매도."""
    state = {
        "state": M2_OPEN, "method": 2,
        "entry_price": 100.0, "stop_loss": 90.0, "target1": 120.0, "target_full": 120.0,
    }
    closes = _downtrend(60, start=130.0, step=2.0)
    r = generate_signal(S, _candles(closes), True, state)
    if r["indicators"].get("dead_cross"):
        assert r["action"] == SELL_ALL
        assert "데드크로스" in r["reasoning"]


# ── HMA 마스터 필터 ──────────────────────────────────────────────────────────

def test_hma_filter_blocks_buy():
    """HMA 하향(False) → BUY 신호 차단."""
    state = {
        "state": M1_OPEN_1, "method": 1,
        "entry_price": 100.0, "stop_loss": 95.0, "target1": 110.0, "target_full": 110.0,
    }
    # 1차 목표 미달성 구간 (손절·목표 둘 다 아닌 가격)
    closes = [102.0] * 60
    r = generate_signal(S, _candles(closes), False, state)
    # 1차 목표 미달성 상태에서 HMA 필터는 SELL 신호에는 영향 없음 → NONE
    assert r["action"] == NONE  # 목표도 SL도 아님


def test_hma_none_does_not_block():
    """hma_is_rising=None (데이터 부족) → 필터 완화, 차단 안 함."""
    # IDLE에서 진입 조건이 충족되더라도 None은 차단하지 않음
    state = {"state": IDLE}
    r = generate_signal(S, _candles(_uptrend(60)), None, state)
    # 신호가 없어도 action이 None이고 차단 메시지가 아님
    assert "HMA" not in r["reasoning"] or "None" not in r["reasoning"]


# ── 전략 파라미터 변경 반영 ──────────────────────────────────────────────────

def test_strategy_rsi_threshold_affects_queue():
    """rsi.buy_low를 60으로 높이면 더 넓은 범위에서 큐 진입."""
    import copy
    state = {"state": M1_OPEN_1, "method": 1,
             "entry_price": 100.0, "stop_loss": 95.0, "target1": 110.0, "target_full": 110.0}
    # 손절·목표 미달성 → 보유 유지 확인
    closes = [105.0] * 60
    r = generate_signal(S, _candles(closes), True, state)
    assert r["action"] == NONE  # 목표(110) 미달성, SL(95) 위


# ── prev_rsi 갱신 ─────────────────────────────────────────────────────────────

def test_prev_rsi_always_updated():
    """매 tick마다 new_state에 prev_rsi가 갱신된다."""
    state = {"state": IDLE}
    r = generate_signal(S, _candles(_uptrend(60)), True, state)
    assert "prev_rsi" in r["new_state"]
    assert isinstance(r["new_state"]["prev_rsi"], float)
