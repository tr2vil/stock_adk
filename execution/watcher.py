"""
가격 워처 (Phase 2) — 장중 5분 폴링, LLM 미사용.

활성 플랜이 있는 종목의 현재가를 토스 REST로 폴링하고, 결정론적
사다리 상태머신(shared.strategy.evaluate_ladder)을 평가하여 교차 시
지정가 주문(order_manager.place_limit, DRY_RUN)을 낸다.

- 시작/중지: 수동 토글(orchestrator API). 자동 시작 안 함(실주문 안전).
- 장 시간: KR 09:00~15:30 KST 평일에만 동작(그 외 tick은 skip).
- 토스 호출은 blocking requests이므로 asyncio.to_thread로 감싼다.
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from shared import strategy as strat
from shared.config import settings
from shared.logger import get_logger
from execution.order_manager import OrderManager
from execution.toss_rest import TossRESTClient

logger = get_logger("execution.watcher")

_KST = ZoneInfo("Asia/Seoul")
_ET = ZoneInfo("America/New_York")  # 서머타임 자동 반영

# 워처 전용 싱글턴: 일일 거래 카운트를 tick 간 유지한다.
_toss = TossRESTClient()
_order_manager = OrderManager()
_last_reset_date = None  # 일일 카운트 리셋 기준일(KST)


def _maybe_reset_daily_count() -> None:
    """KST 날짜가 바뀌면 일일 거래 카운트를 리셋(누적으로 한도 영구차단 방지)."""
    global _last_reset_date
    today = datetime.now(_KST).date()
    if _last_reset_date != today:
        _order_manager.reset_daily_count()
        _last_reset_date = today
        logger.info("watcher_daily_count_reset", date=str(today))


def is_kr_market_open(now: datetime | None = None) -> bool:
    """KR 정규장(평일 09:00~15:30 KST) 개장 여부."""
    now = now or datetime.now(_KST)
    if now.weekday() >= 5:  # 토(5)·일(6)
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 <= minutes <= 15 * 60 + 30


def is_us_market_open(now: datetime | None = None) -> bool:
    """US 정규장(평일 09:30~16:00 ET, 서머타임 반영) 개장 여부."""
    now = now or datetime.now(_ET)
    now = now.astimezone(_ET)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 16 * 60


def is_market_open(market: str, now: datetime | None = None) -> bool:
    """종목 시장(KR/US)별 개장 여부."""
    return is_us_market_open(now) if (market or "").upper() == "US" else is_kr_market_open(now)


def market_sessions() -> dict:
    """현재 KR/US 시장 개장 상태."""
    return {"KR": is_kr_market_open(), "US": is_us_market_open()}


def _now_ms() -> int:
    return int(datetime.now(_KST).timestamp() * 1000)


async def run_watcher_tick() -> dict:
    """워처 1회 실행. 비활성/폐장 시 skip. 활성 플랜 종목을 평가·발주.

    Returns:
        dict: 이번 tick 요약(상태 저장에도 사용)
    """
    now_ms = _now_ms()
    base = {"ran_at": now_ms, "dry_run": settings.DRY_RUN, "markets": market_sessions()}

    if not await strat.aget_watcher_enabled():
        return {**base, "status": "disabled"}

    _maybe_reset_daily_count()  # 날짜 경계에서 일일 거래 카운트 리셋

    # 활성 플랜이 있는 종목만 대상
    plans = await strat.aget_all_plans()
    active = [p for p in plans if p.get("active")]
    if not active:
        status = {**base, "status": "no_active_plans", "evaluated": 0}
        await strat.aset_watcher_status(status)
        return status

    # 종목별 자기 시장 개장 시에만 평가 (KR/US 각각 게이팅)
    active = [p for p in active if is_market_open(p.get("market", "KR"))]
    if not active:
        status = {**base, "status": "market_closed", "evaluated": 0}
        await strat.aset_watcher_status(status)
        return status

    symbols = [p["symbol"] for p in active]

    # 현재가 + 보유 동기화 (blocking → to_thread)
    price_resp, balance_resp = await asyncio.gather(
        asyncio.to_thread(_toss.get_prices, symbols),
        asyncio.to_thread(_toss.get_balance),
    )
    price_map = _parse_prices(price_resp)
    holdings_map = _parse_holdings(balance_resp)

    results = []
    for p in active:
        sym = p["symbol"]
        try:
            res = await _evaluate_symbol(p, price_map.get(sym), holdings_map.get(sym, 0), now_ms)
            results.append(res)
        except Exception as e:  # 한 종목 실패가 전체를 막지 않도록
            logger.error("watcher_symbol_failed", symbol=sym, error=str(e))
            results.append({"symbol": sym, "status": "error", "error": str(e)})

    fills_total = sum(len(r.get("fills", [])) for r in results)
    status = {
        **base, "status": "ran", "evaluated": len(active),
        "fills": fills_total, "symbols": results,
    }
    await strat.aset_watcher_status(status)
    logger.info("watcher_tick", evaluated=len(active), fills=fills_total)
    return status


async def _evaluate_symbol(plan: dict, current_price, total_qty: int, now_ms: int) -> dict:
    """단일 종목 평가 → 발주 → 사다리 상태 저장."""
    sym = plan["symbol"]
    market = plan.get("market", "KR")

    active_plan = plan.get("active") or {}
    if current_price is None or current_price <= 0:
        return {"symbol": sym, "status": "no_price"}

    # 밴드 설정 (종목 오버라이드 병합)
    config = await strat.aget_band_config(sym)
    swing_fraction = float(config.get("swing_fraction", 0.20))
    hysteresis_pct = float(config.get("hysteresis_pct", 0.03))
    cooldown_sec = int(config.get("cooldown_sec", 1800))
    notional_swing_qty = int(config.get("notional_swing_qty", 0))

    # 포지션 산정: 코어 고정, 봇은 스윙 수량만 거래
    core_qty = int(total_qty * (1 - swing_fraction))  # floor
    swing_qty = total_qty - core_qty
    # 매수 기준 수량: 보유가 있으면 swing_qty, 신규 진입(보유 0)이면 notional 사용
    buy_base_qty = swing_qty if swing_qty > 0 else notional_swing_qty

    # 사다리: 없으면 materialize (승인 시 생성되지만 구버전 플랜 대비)
    ladder = active_plan.get("ladder")
    if not ladder:
        ladder = strat.build_ladder(active_plan, config)

    fills, new_ladder = strat.evaluate_ladder(
        ladder, current_price, total_qty, swing_qty, core_qty,
        hysteresis_pct, cooldown_sec, now_ms, buy_base_qty=buy_base_qty,
    )

    # 발주 (DRY_RUN 경유)
    placed = []
    for f in fills:
        result = _order_manager.place_limit(
            symbol=sym, market=market, side=f["side"], qty=f["qty"], price=f["price"],
        )
        placed.append({**f, "result": result.get("status")})
        logger.info(
            "watcher_order", symbol=sym, side=f["side"], qty=f["qty"],
            price=f["price"], result=result.get("status"),
        )

    await strat.aupdate_active_ladder(sym, new_ladder)

    return {
        "symbol": sym, "status": "ok", "price": current_price,
        "total_qty": total_qty, "core_qty": core_qty, "swing_qty": swing_qty,
        "fills": placed,
    }


def _parse_prices(resp) -> dict:
    """get_prices 응답 → {symbol: lastPrice}."""
    out = {}
    if not isinstance(resp, dict):
        return out
    for row in resp.get("result", []) or []:
        try:
            out[row["symbol"]] = float(row.get("lastPrice", 0))
        except (ValueError, TypeError, KeyError):
            continue
    return out


def _parse_holdings(resp) -> dict:
    """get_balance 응답 → {symbol: quantity}."""
    out = {}
    if not isinstance(resp, dict):
        return out
    result = resp.get("result", resp)
    items = result.get("items", []) if isinstance(result, dict) else []
    for it in items or []:
        try:
            out[it["symbol"]] = int(float(it.get("quantity", 0)))
        except (ValueError, TypeError, KeyError):
            continue
    return out
