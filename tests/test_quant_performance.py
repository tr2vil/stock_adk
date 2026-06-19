"""성과 통계 단위 테스트 (순수 함수)."""
from shared.quant.performance import (
    compute_performance, sharpe_ratio, max_drawdown,
)


def test_empty():
    p = compute_performance([])
    assert p["total_trades"] == 0
    assert p["win_rate"] == 0.0
    assert p["signal_accuracy"]["BUY"] is None


def test_win_rate_and_avg():
    trades = [
        {"signal": "SELL", "rsi": 28, "sentiment": 0.3, "return_rate": 0.02},
        {"signal": "SELL", "rsi": 33, "sentiment": -0.1, "return_rate": -0.01},
        {"signal": "SELL", "rsi": 22, "sentiment": 0.6, "return_rate": 0.03},
        {"signal": "BUY", "rsi": 24, "sentiment": 0.1, "return_rate": None},  # 미청산 제외
    ]
    p = compute_performance(trades)
    assert p["total_trades"] == 3
    assert p["win_rate"] == round(2 / 3, 4)
    assert p["avg_return"] == round((0.02 - 0.01 + 0.03) / 3, 5)


def test_signal_accuracy():
    trades = [
        {"signal": "SELL", "return_rate": 0.01},
        {"signal": "SELL", "return_rate": -0.02},
        {"signal": "BUY", "return_rate": 0.05},
    ]
    p = compute_performance(trades)
    assert p["signal_accuracy"]["SELL"] == 0.5
    assert p["signal_accuracy"]["BUY"] == 1.0


def test_rsi_and_sentiment_buckets():
    trades = [
        {"signal": "SELL", "rsi": 22, "sentiment": -0.6, "return_rate": 0.01},
        {"signal": "SELL", "rsi": 27, "sentiment": 0.2, "return_rate": -0.02},
        {"signal": "SELL", "rsi": 40, "sentiment": 0.7, "return_rate": 0.03},
    ]
    p = compute_performance(trades)
    assert p["rsi_performance"]["<25"] == 0.01
    assert p["rsi_performance"]["25-30"] == -0.02
    assert p["rsi_performance"][">=35"] == 0.03
    assert p["rsi_performance"]["30-35"] is None
    assert p["sentiment_performance"]["<-0.5"] == 0.01
    assert p["sentiment_performance"][">0.5"] == 0.03


def test_sharpe_and_mdd():
    assert sharpe_ratio([0.01]) == 0.0  # 표본 부족
    assert sharpe_ratio([0.01, 0.01, 0.01]) == 0.0  # 무변동 → std 0
    s = sharpe_ratio([0.02, -0.01, 0.03, -0.02, 0.01])
    assert isinstance(s, float)
    # MDD: 하락이 있으면 음수
    assert max_drawdown([0.1, -0.2, 0.05]) < 0
    assert max_drawdown([0.01, 0.02]) == 0.0  # 단조 상승 → 0
