"""Rule 신호 생성 단위 테스트 (순수 함수, 결정론적)."""
from shared.quant.schema import StrategyConfig
from shared.quant.signal import generate_signal, BUY, SELL, HOLD

S = StrategyConfig()  # 기본값: rsi_buy 30 / sell 70, sl 0.05, news -0.7/0.8, sent_min -0.3


def test_news_defense_blocks_buy():
    r = generate_signal(S, rsi=25, price=100, ma=90, sentiment=-0.8, confidence=0.9)
    assert r["signal"] == HOLD  # 강한 악재 → 매수 차단


def test_stop_loss_sell():
    r = generate_signal(S, rsi=50, price=94, ma=90, sentiment=0.0,
                        confidence=0.5, entry_price=100)
    assert r["signal"] == SELL  # 94 < 100×0.95


def test_momentum_sell():
    r = generate_signal(S, rsi=75, price=100, ma=90, sentiment=0.1, confidence=0.5)
    assert r["signal"] == SELL  # RSI>70, 감성<0.2


def test_momentum_buy():
    r = generate_signal(S, rsi=25, price=100, ma=90, sentiment=0.0, confidence=0.5)
    assert r["signal"] == BUY  # RSI<30, 가격>MA, 감성>-0.3


def test_buy_blocked_when_price_below_ma():
    r = generate_signal(S, rsi=25, price=85, ma=90, sentiment=0.0, confidence=0.5)
    assert r["signal"] == HOLD  # 가격<MA → 매수 조건 미충족


def test_hold_default():
    r = generate_signal(S, rsi=50, price=100, ma=90, sentiment=0.0, confidence=0.5)
    assert r["signal"] == HOLD


def test_strategy_change_alters_signal():
    """진화로 rsi_buy_threshold가 낮아지면 동일 입력의 신호가 바뀐다."""
    base = generate_signal(S, rsi=28, price=100, ma=90, sentiment=0.0, confidence=0.5)
    assert base["signal"] == BUY  # 28 < 30
    evolved = S.model_copy(deep=True)
    evolved.momentum.rsi_buy_threshold = 26
    after = generate_signal(evolved, rsi=28, price=100, ma=90, sentiment=0.0, confidence=0.5)
    assert after["signal"] == HOLD  # 28 > 26 → 더 이상 매수 안 함
