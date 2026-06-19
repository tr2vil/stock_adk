"""매매 성과 통계 — 순수 함수, 결정론적 (LLM에 입력으로 제공).

청산된 매매(round-trip) 레코드 리스트를 받아 통계를 산출한다.
각 레코드는 최소한 다음 키를 가진다(없으면 안전하게 무시):
    {
      "ticker": str,
      "signal": "BUY"|"SELL",       # 신호 종류
      "rsi": float,                  # 신호 시 RSI
      "sentiment": float,            # 신호 시 감성
      "return_rate": float | None,   # 청산 수익률 (예: 0.012 = +1.2%). None이면 미청산
    }
설계서 5.2 분석 파이프라인의 stats 구조를 따른다.
"""
from __future__ import annotations

import math


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _bucket(returns_by_bucket: dict[str, list[float]]) -> dict[str, float | None]:
    """구간별 평균 수익률(없으면 None)."""
    return {k: (round(_mean(v), 5) if v else None) for k, v in returns_by_bucket.items()}


def sharpe_ratio(returns: list[float], periods_per_year: int = 252) -> float:
    """단순 샤프 지수(무위험수익률 0 가정), 연율화."""
    if len(returns) < 2:
        return 0.0
    mu = _mean(returns)
    var = sum((r - mu) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return round((mu / std) * math.sqrt(periods_per_year), 4)


def max_drawdown(returns: list[float]) -> float:
    """수익률 시퀀스로 만든 누적 곡선의 최대 낙폭(MDD, 음수 또는 0)."""
    if not returns:
        return 0.0
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        equity *= (1 + r)
        peak = max(peak, equity)
        mdd = min(mdd, equity / peak - 1)
    return round(mdd, 5)


def compute_performance(trades: list[dict]) -> dict:
    """매매 레코드 → 성과 통계 dict.

    return_rate 가 있는(청산된) 레코드만 수익률 통계에 사용한다.
    """
    closed = [t for t in trades if isinstance(t.get("return_rate"), (int, float))]
    returns = [float(t["return_rate"]) for t in closed]
    total = len(closed)

    wins = [r for r in returns if r > 0]
    win_rate = round(len(wins) / total, 4) if total else 0.0

    # 신호별 정확도(수익 발생 비율)
    def _accuracy(sig: str) -> float | None:
        rs = [float(t["return_rate"]) for t in closed if t.get("signal") == sig]
        if not rs:
            return None
        return round(len([r for r in rs if r > 0]) / len(rs), 4)

    # RSI 구간별 수익률
    rsi_buckets: dict[str, list[float]] = {"<25": [], "25-30": [], "30-35": [], ">=35": []}
    for t in closed:
        rsi = t.get("rsi")
        if rsi is None:
            continue
        r = float(t["return_rate"])
        if rsi < 25:
            rsi_buckets["<25"].append(r)
        elif rsi < 30:
            rsi_buckets["25-30"].append(r)
        elif rsi < 35:
            rsi_buckets["30-35"].append(r)
        else:
            rsi_buckets[">=35"].append(r)

    # 감성 구간별 수익률
    sent_buckets: dict[str, list[float]] = {"<-0.5": [], "-0.5~0": [], "0~0.5": [], ">0.5": []}
    for t in closed:
        s = t.get("sentiment")
        if s is None:
            continue
        r = float(t["return_rate"])
        if s < -0.5:
            sent_buckets["<-0.5"].append(r)
        elif s < 0:
            sent_buckets["-0.5~0"].append(r)
        elif s < 0.5:
            sent_buckets["0~0.5"].append(r)
        else:
            sent_buckets[">0.5"].append(r)

    return {
        "total_trades": total,
        "win_rate": win_rate,
        "avg_return": round(_mean(returns), 5),
        "sharpe_ratio": sharpe_ratio(returns),
        "max_drawdown": max_drawdown(returns),
        "signal_accuracy": {"BUY": _accuracy("BUY"), "SELL": _accuracy("SELL")},
        "rsi_performance": _bucket(rsi_buckets),
        "sentiment_performance": _bucket(sent_buckets),
    }
