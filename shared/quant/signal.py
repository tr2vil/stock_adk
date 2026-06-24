"""MACD + RSI 모멘텀 전략 신호 생성 (Ross Cameron 원칙 기반).

제1매매법: MACD 골든크로스 + RSI 필터 → 분할 청산 (1차 50%, 2차 잔량)
제2매매법: RSI 하락 다이버전스 + 눌림목 → 전량 청산

5분봉을 진입/청산 타임프레임으로 사용하며,
상위 TF(일봉/1시간봉) HMA 우상향 여부를 마스터 필터로 적용한다.
"""
from __future__ import annotations

from .schema import StrategyConfig
from .indicators import macd as _macd, rsi as _rsi, rsi_series, find_swing_highs, volume_ratio

# ── 상태 상수 ────────────────────────────────────────────────────────────────
IDLE = "IDLE"

# 제1매매법 상태
M1_Q_LOW = "M1_QUEUED_RSI_LOW"    # 골든크로스 + RSI<50 → RSI 50 상향 대기
M1_Q_HIGH = "M1_QUEUED_RSI_HIGH"  # 골든크로스 + RSI≥70 → 눌림목 후 반등 대기
M1_OPEN_1 = "M1_OPEN_FIRST"       # 진입, 1차 목표 미달성 (전량 보유)
M1_OPEN_2 = "M1_OPEN_SECOND"      # 1차 50% 익절 완료, 잔량 50% 감시

# 제2매매법 상태
M2_DIV = "M2_DIVERGENCE"  # 하락 다이버전스 감지 → 데드크로스 대기
M2_COOL = "M2_COOLDOWN"   # 데드크로스 발생 → 조정 중, 골든크로스 재전환 대기
M2_OPEN = "M2_OPEN"       # 진입, 1:2 도달 또는 데드크로스 청산 대기

# ── 공개 상수 (외부 참조용) ──────────────────────────────────────────────────
BUY = "BUY"
SELL_HALF = "SELL_HALF"
SELL_ALL = "SELL_ALL"
NONE = "NONE"


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _c(candles: list[dict], key: str) -> list[float]:
    return [float(c[key]) for c in candles]


def _swing_low(candles: list[dict], n: int) -> float:
    """최근 n개 캔들 저점의 최솟값 (손절가 산출)."""
    lows = _c(candles, "lowPrice")
    return min(lows[-n:]) if len(lows) >= n else min(lows)


def _target(entry: float, sl: float) -> float:
    """1:2 손익비 목표가."""
    return round(entry + (entry - sl) * 2, 2)


def _no_action(state: dict, reason: str, inds: dict | None = None) -> dict:
    return {"action": NONE, "reasoning": reason, "new_state": state, "indicators": inds or {}}


def _enter_long(
    candles: list[dict],
    state: dict,
    inds: dict,
    strategy: StrategyConfig,
    method: int,
    next_state: str,
    reason: str,
) -> dict:
    """BUY 신호 + 상태 갱신 (진입가·손절가·목표가 계산)."""
    entry = _c(candles, "closePrice")[-1]
    sl = _swing_low(candles, strategy.stop_loss.lookback_candles)
    tgt = _target(entry, sl)
    new_state = {
        **state,
        "state": next_state,
        "method": method,
        "entry_price": entry,
        "stop_loss": sl,
        "target1": tgt,
        "target_full": tgt,
    }
    return {"action": BUY, "reasoning": reason, "new_state": new_state, "indicators": inds}


# ── 공개 API ─────────────────────────────────────────────────────────────────

def generate_signal(
    strategy: StrategyConfig,
    candles_5m: list[dict],
    hma_is_rising: bool | None,
    state: dict,
) -> dict:
    """MACD+RSI 신호 1회 평가.

    Args:
        strategy:      활성 전략 설정
        candles_5m:    5분봉 OHLCV (오래된→최신), 최소 35개 필요 / 60개 권장
                       각 dict: {closePrice, highPrice, lowPrice, openPrice, volume}
        hma_is_rising: 상위 TF HMA 상승 여부 (None=데이터 부족 → 필터 완화)
        state:         현재 신호 상태 (quant:signal:state:{symbol})

    Returns:
        dict: {
            "action": "NONE"|"BUY"|"SELL_HALF"|"SELL_ALL",
            "reasoning": str,
            "new_state": dict,    # Redis에 저장할 갱신 상태
            "indicators": dict,   # 지표값 (로깅용)
        }
    """
    if len(candles_5m) < 35:
        return _no_action(state, "캔들 데이터 부족 (최소 35개)")

    closes = _c(candles_5m, "closePrice")
    highs = _c(candles_5m, "highPrice")
    volumes = _c(candles_5m, "volume")

    m = _macd(closes, strategy.macd.fast, strategy.macd.slow, strategy.macd.signal)
    cur_rsi = _rsi(closes, strategy.rsi.period)

    if m is None or cur_rsi is None:
        return _no_action(state, "MACD/RSI 계산 불가 (데이터 부족)")

    vol_r = volume_ratio(volumes, strategy.volume_filter.lookback) if strategy.volume_filter.enabled else None
    vol_ok = (
        not strategy.volume_filter.enabled
        or vol_r is None
        or vol_r >= strategy.volume_filter.multiplier
    )
    # HMA 마스터 필터: None(데이터 없음)은 허용, False(하향)만 차단
    hma_allows_buy = (hma_is_rising is not False)

    inds = {
        "macd_line": m["macd_line"],
        "signal_line": m["signal_line"],
        "histogram": m["histogram"],
        "rsi": cur_rsi,
        "golden_cross": m["golden_cross"],
        "dead_cross": m["dead_cross"],
        "macd_positive": m["is_positive"],
        "hma_rising": hma_is_rising,
        "volume_ratio": vol_r,
    }

    cur_state = state.get("state", IDLE)
    cur_price = closes[-1]
    prev_rsi = state.get("prev_rsi")

    # ── 상태머신 디스패치 ─────────────────────────────────────────────────────
    if cur_state == IDLE:
        result = _idle_tick(strategy, candles_5m, closes, highs, m, cur_rsi, prev_rsi,
                            hma_allows_buy, vol_ok, inds, state)
    elif cur_state in (M1_Q_LOW, M1_Q_HIGH):
        result = _m1_queued_tick(strategy, candles_5m, m, cur_rsi, prev_rsi,
                                 hma_allows_buy, vol_ok, inds, state)
    elif cur_state == M1_OPEN_1:
        result = _m1_open1_tick(cur_price, m, cur_rsi, inds, state)
    elif cur_state == M1_OPEN_2:
        result = _m1_open2_tick(cur_price, m, cur_rsi, inds, state)
    elif cur_state == M2_DIV:
        result = _m2_div_tick(m, inds, state)
    elif cur_state == M2_COOL:
        result = _m2_cool_tick(strategy, candles_5m, m, cur_rsi, hma_allows_buy, inds, state)
    elif cur_state == M2_OPEN:
        result = _m2_open_tick(cur_price, m, inds, state)
    else:
        result = _no_action(state, f"알 수 없는 상태: {cur_state}", inds)

    result["new_state"]["prev_rsi"] = cur_rsi
    return result


# ── 상태별 핸들러 ─────────────────────────────────────────────────────────────

def _idle_tick(
    strategy: StrategyConfig,
    candles: list[dict],
    closes: list[float],
    highs: list[float],
    m: dict,
    cur_rsi: float,
    prev_rsi: float | None,
    hma_ok: bool,
    vol_ok: bool,
    inds: dict,
    state: dict,
) -> dict:
    """IDLE: 제2매매법(다이버전스) → 제1매매법(골든크로스) 순서로 우선 검사."""

    # ── 제2매매법: RSI 하락 다이버전스 스캔 ──────────────────────────────────
    if strategy.divergence.enabled:
        rsi_s = rsi_series(closes, strategy.rsi.period)
        if rsi_s is not None:
            offset = strategy.rsi.period
            aligned_highs = highs[offset:]
            if len(aligned_highs) == len(rsi_s):
                peaks = find_swing_highs(
                    aligned_highs, rsi_s,
                    window=strategy.divergence.swing_window,
                    count=2,
                )
                if peaks and len(peaks) == 2:
                    p1, p2 = peaks  # p1=이전, p2=최근
                    recent_enough = p2["index"] >= len(aligned_highs) - 30
                    if (p2["price_high"] > p1["price_high"]       # 가격 고점 상승
                            and p2["rsi_high"] < p1["rsi_high"]   # RSI 고점 하락
                            and recent_enough):
                        new_state = {**state, "state": M2_DIV}
                        return {
                            "action": NONE,
                            "reasoning": (
                                f"제2매매법: RSI 하락 다이버전스 감지 "
                                f"(가격 {p1['price_high']:.0f}→{p2['price_high']:.0f} ↑, "
                                f"RSI {p1['rsi_high']:.1f}→{p2['rsi_high']:.1f} ↓)"
                            ),
                            "new_state": new_state,
                            "indicators": inds,
                        }

    # ── 제1매매법: MACD 골든크로스 ───────────────────────────────────────────
    if not m["golden_cross"]:
        return _no_action(state, "신호 없음", inds)

    if not vol_ok:
        return _no_action(
            state,
            f"골든크로스 발생, 거래량 부족 ({inds.get('volume_ratio', 0):.2f}x < {strategy.volume_filter.multiplier}x)",
            inds,
        )

    buy_low = strategy.rsi.buy_low
    buy_high = strategy.rsi.buy_high

    # Case A: 정상 진입 구간 (50 ≤ RSI < 70)
    if buy_low <= cur_rsi < buy_high:
        if not hma_ok:
            return _no_action(state, f"골든크로스 + RSI {cur_rsi:.1f} but HMA 하향 → 진입 차단", inds)
        return _enter_long(
            candles, state, inds, strategy, method=1, next_state=M1_OPEN_1,
            reason=f"제1매매법 진입: 골든크로스 + RSI {cur_rsi:.1f} (정상 구간 {buy_low}~{buy_high})",
        )

    # Case B: RSI 미달 → RSI 50 상향 돌파 대기
    if cur_rsi < buy_low:
        return {
            "action": NONE,
            "reasoning": f"제1매매법: 골든크로스 but RSI {cur_rsi:.1f}<{buy_low} → RSI {buy_low} 돌파 대기",
            "new_state": {**state, "state": M1_Q_LOW},
            "indicators": inds,
        }

    # Case C: RSI 과열(≥70) → 눌림목 대기
    return {
        "action": NONE,
        "reasoning": f"제1매매법: 골든크로스 but RSI {cur_rsi:.1f}≥{buy_high} → 눌림목 대기",
        "new_state": {**state, "state": M1_Q_HIGH},
        "indicators": inds,
    }


def _m1_queued_tick(
    strategy: StrategyConfig,
    candles: list[dict],
    m: dict,
    cur_rsi: float,
    prev_rsi: float | None,
    hma_ok: bool,
    vol_ok: bool,
    inds: dict,
    state: dict,
) -> dict:
    """제1매매법 대기 큐: MACD 정배열 유지 확인 후 진입 조건 감시."""
    cur_state = state["state"]

    # MACD 역배열 → 큐 취소
    if not m["is_positive"]:
        return {
            "action": NONE,
            "reasoning": "MACD 역배열 전환 → 대기 큐 취소, IDLE 복귀",
            "new_state": {**state, "state": IDLE},
            "indicators": inds,
        }

    buy_low = strategy.rsi.buy_low

    if cur_state == M1_Q_LOW:
        # RSI가 50을 상향 돌파하는 순간 진입
        crossed_up = prev_rsi is not None and prev_rsi < buy_low and cur_rsi >= buy_low
        if crossed_up:
            if not hma_ok:
                return _no_action(state, f"RSI {buy_low} 돌파 but HMA 하향 → 진입 차단", inds)
            return _enter_long(
                candles, state, inds, strategy, method=1, next_state=M1_OPEN_1,
                reason=f"제1매매법 큐 진입: RSI {prev_rsi:.1f}→{cur_rsi:.1f} ({buy_low} 상향 돌파)",
            )

    elif cur_state == M1_Q_HIGH:
        # 눌림목: RSI가 pullback_zone_high 이하로 내려온 뒤 반등 시작
        zone_top = strategy.rsi.pullback_zone_high
        bouncing = (
            prev_rsi is not None
            and cur_rsi <= zone_top     # 눌림목 구간까지 하락
            and cur_rsi > prev_rsi      # 반등 시작
            and cur_rsi >= buy_low      # 50 이상 유지
        )
        if bouncing:
            if not hma_ok:
                return _no_action(state, f"눌림목 반등 확인 but HMA 하향 → 진입 차단", inds)
            return _enter_long(
                candles, state, inds, strategy, method=1, next_state=M1_OPEN_1,
                reason=f"제1매매법 눌림목 진입: RSI {cur_rsi:.1f} ({buy_low}~{zone_top} 반등 확인)",
            )

    return _no_action(state, f"{cur_state}: 대기 중 (RSI {cur_rsi:.1f})", inds)


def _m1_open1_tick(
    cur_price: float, m: dict, cur_rsi: float, inds: dict, state: dict,
) -> dict:
    """제1매매법: 1차 목표가 대기 (전량 보유)."""
    sl = state.get("stop_loss") or 0
    t1 = state.get("target1") or 0

    if sl and cur_price <= sl:
        return {
            "action": SELL_ALL,
            "reasoning": f"손절: {cur_price:.0f} ≤ SL {sl:.0f}",
            "new_state": {**state, "state": IDLE},
            "indicators": inds,
        }

    if t1 and cur_price >= t1:
        return {
            "action": SELL_HALF,
            "reasoning": f"제1매매법 1차 익절 50%: {cur_price:.0f} ≥ 목표 {t1:.0f}",
            "new_state": {**state, "state": M1_OPEN_2},
            "indicators": inds,
        }

    return _no_action(state, f"M1 보유: 현재 {cur_price:.0f}, SL {sl:.0f}, 목표 {t1:.0f}", inds)


def _m1_open2_tick(
    cur_price: float, m: dict, cur_rsi: float, inds: dict, state: dict,
) -> dict:
    """제1매매법: 잔량 50% 감시 (데드크로스·RSI50 이탈·본전 보존)."""
    entry = state.get("entry_price") or 0
    sl = state.get("stop_loss") or 0
    exit_thr = 50.0

    reasons = []
    if m["dead_cross"]:
        reasons.append("MACD 데드크로스")
    if cur_rsi <= exit_thr:
        reasons.append(f"RSI {cur_rsi:.1f}≤{exit_thr}")
    if entry and cur_price <= entry:
        reasons.append(f"본전 보존 ({cur_price:.0f}≤진입가 {entry:.0f})")
    if sl and cur_price <= sl:
        reasons.append(f"손절 {sl:.0f}")

    if reasons:
        return {
            "action": SELL_ALL,
            "reasoning": f"제1매매법 잔량 청산: {' / '.join(reasons)}",
            "new_state": {**state, "state": IDLE},
            "indicators": inds,
        }

    return _no_action(
        state,
        f"M1 잔량 보유: RSI {cur_rsi:.1f}, MACD {'정배열' if m['is_positive'] else '역배열'}",
        inds,
    )


def _m2_div_tick(m: dict, inds: dict, state: dict) -> dict:
    """제2매매법: 다이버전스 감지 후 데드크로스 대기."""
    if m["dead_cross"]:
        return {
            "action": NONE,
            "reasoning": "제2매매법: 데드크로스 발생 → 조정 구간 진입, 골든크로스 재전환 대기",
            "new_state": {**state, "state": M2_COOL},
            "indicators": inds,
        }
    return _no_action(state, "제2매매법: 다이버전스 후 데드크로스 대기 중", inds)


def _m2_cool_tick(
    strategy: StrategyConfig,
    candles: list[dict],
    m: dict,
    cur_rsi: float,
    hma_ok: bool,
    inds: dict,
    state: dict,
) -> dict:
    """제2매매법: 조정 구간 → 골든크로스 재전환 + RSI ≥ 50 시 진입."""
    if not m["golden_cross"]:
        return _no_action(state, f"제2매매법 조정 중: RSI {cur_rsi:.1f}", inds)

    if cur_rsi < strategy.rsi.buy_low:
        return _no_action(
            state,
            f"골든크로스 but RSI {cur_rsi:.1f}<{strategy.rsi.buy_low} → 조정 계속 대기",
            inds,
        )

    # 제2매매법은 RSI 70 이상 과열 구간도 진입 허용 (강한 2차 상승 포착)
    rsi_note = " (RSI 과열구간, 2차 상승 허용)" if cur_rsi >= strategy.rsi.buy_high else ""
    return _enter_long(
        candles, state, inds, strategy, method=2, next_state=M2_OPEN,
        reason=f"제2매매법 진입: 조정 후 골든크로스 재전환 + RSI {cur_rsi:.1f}{rsi_note}",
    )


def _m2_open_tick(cur_price: float, m: dict, inds: dict, state: dict) -> dict:
    """제2매매법: 전량 청산 감시 (1:2 목표 또는 데드크로스)."""
    tgt = state.get("target_full") or 0
    sl = state.get("stop_loss") or 0

    if tgt and cur_price >= tgt:
        return {
            "action": SELL_ALL,
            "reasoning": f"제2매매법 목표 달성 전량 익절: {cur_price:.0f} ≥ {tgt:.0f}",
            "new_state": {**state, "state": IDLE},
            "indicators": inds,
        }

    if m["dead_cross"]:
        return {
            "action": SELL_ALL,
            "reasoning": "제2매매법 데드크로스 → 원칙 매도 전량 청산",
            "new_state": {**state, "state": IDLE},
            "indicators": inds,
        }

    if sl and cur_price <= sl:
        return {
            "action": SELL_ALL,
            "reasoning": f"손절: {cur_price:.0f} ≤ SL {sl:.0f}",
            "new_state": {**state, "state": IDLE},
            "indicators": inds,
        }

    return _no_action(state, f"M2 보유: 현재 {cur_price:.0f}, 목표 {tgt:.0f}, SL {sl:.0f}", inds)
