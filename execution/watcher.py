"""
가격 워처 — 장중 5분 폴링, MACD+RSI 모멘텀 전략.

5분봉 MACD+RSI 신호 엔진을 주 신호 생성기로 사용하고,
상위 TF(일봉/1시간봉) HMA 우상향 여부를 마스터 필터로 적용한다.

- 시작/중지: 수동 토글(orchestrator API). 자동 시작 안 함(실주문 안전).
- 장 시간: KR 09:00~15:30 KST / US 09:30~16:00 ET 평일에만 동작.
- 토스 호출은 blocking requests이므로 asyncio.to_thread로 감싼다.
"""
import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from shared import strategy as strat
from shared.config import settings
from shared.logger import get_logger
from shared.quant import strategy_store as qstore
from shared.quant import signal as signal_mod
from shared.quant import signal_state
from shared.quant import indicators as ind
from shared.quant.trade_log import arecord_trade
from execution.order_manager import OrderManager
from execution.toss_rest import TossRESTClient

logger = get_logger("execution.watcher")

_KST = ZoneInfo("Asia/Seoul")
_ET = ZoneInfo("America/New_York")

_toss = TossRESTClient()
_order_manager = OrderManager()
_last_reset_date = None


def _maybe_reset_daily_count() -> None:
    global _last_reset_date
    today = datetime.now(_KST).date()
    if _last_reset_date != today:
        _order_manager.reset_daily_count()
        _last_reset_date = today
        logger.info("watcher_daily_count_reset", date=str(today))


def is_kr_market_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(_KST)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 <= minutes <= 15 * 60 + 30


def is_us_market_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(_ET)
    now = now.astimezone(_ET)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 16 * 60


def is_market_open(market: str, now: datetime | None = None) -> bool:
    return is_us_market_open(now) if (market or "").upper() == "US" else is_kr_market_open(now)


def market_sessions() -> dict:
    return {"KR": is_kr_market_open(), "US": is_us_market_open()}


def _now_ms() -> int:
    return int(datetime.now(_KST).timestamp() * 1000)


def _parse_candles(resp: dict) -> list[dict]:
    """get_candles 응답 → [{closePrice, highPrice, lowPrice, openPrice, volume}] (오래된→최신)."""
    if not isinstance(resp, dict):
        return []
    result = resp.get("result", {})
    candles = result.get("candles", []) if isinstance(result, dict) else []
    out = []
    for c in candles:
        try:
            out.append({
                "timestamp": c.get("timestamp", 0),
                "openPrice": float(c.get("openPrice", 0)),
                "highPrice": float(c.get("highPrice", 0)),
                "lowPrice": float(c.get("lowPrice", 0)),
                "closePrice": float(c.get("closePrice", 0)),
                "volume": float(c.get("volume", 0)),
            })
        except (ValueError, TypeError):
            continue
    return out


def _parse_prices(resp: dict) -> dict:
    out = {}
    if not isinstance(resp, dict):
        return out
    for row in resp.get("result", []) or []:
        try:
            out[row["symbol"]] = float(row.get("lastPrice", 0))
        except (ValueError, TypeError, KeyError):
            continue
    return out


def _parse_holdings(resp: dict) -> dict:
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


async def run_watcher_tick() -> dict:
    """워처 1회 실행. 비활성/폐장 시 skip."""
    now_ms = _now_ms()
    base = {"ran_at": now_ms, "dry_run": settings.DRY_RUN, "markets": market_sessions()}

    if not await strat.aget_watcher_enabled():
        return {**base, "status": "disabled"}

    _maybe_reset_daily_count()

    # 워치리스트에서 모니터링 종목 조회
    watchlist = await strat.aget_watchlist()
    if not watchlist:
        status = {**base, "status": "no_watchlist", "evaluated": 0}
        await strat.aset_watcher_status(status)
        return status

    # 장 시간 필터 (종목별 시장 기준)
    active = [w for w in watchlist if is_market_open(w.get("market", "KR"))]
    if not active:
        status = {**base, "status": "market_closed", "evaluated": 0}
        await strat.aset_watcher_status(status)
        return status

    symbols = [w["symbol"] for w in active]

    # 현재가 + 보유 조회 (일괄)
    price_resp, balance_resp = await asyncio.gather(
        asyncio.to_thread(_toss.get_prices, symbols),
        asyncio.to_thread(_toss.get_balance),
    )
    price_map = _parse_prices(price_resp)
    holdings_map = _parse_holdings(balance_resp)

    # 활성 전략 로드 (tick마다 1회)
    strategy = await qstore.aget_active_strategy()

    results = []
    for w in active:
        sym = w["symbol"]
        try:
            res = await _evaluate_symbol(w, price_map, holdings_map, strategy, now_ms)
            results.append(res)
        except Exception as e:
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


async def _evaluate_symbol(
    watch_item: dict,
    price_map: dict,
    holdings_map: dict,
    strategy,
    now_ms: int,
) -> dict:
    """단일 종목 신호 평가 → 발주 → 상태 저장."""
    sym = watch_item["symbol"]
    market = watch_item.get("market", "KR")
    total_qty = holdings_map.get(sym, 0)

    # ── 1분봉 캔들 조회 (Toss는 1m·1d만 지원) ───────────────────────────────
    candles_1m_resp = await asyncio.to_thread(_toss.get_candles, sym, "1m", 200)
    candles_1m = _parse_candles(candles_1m_resp)

    if len(candles_1m) < 35:
        logger.warning("watcher_insufficient_candles", symbol=sym, count=len(candles_1m))
        return {"symbol": sym, "status": "insufficient_candles", "count": len(candles_1m)}

    # 현재가: 1m 봉 마지막 종가 사용 (Toss get_prices는 US 배치 조회 미지원)
    current_price = price_map.get(sym) or candles_1m[-1]["closePrice"]
    if not current_price or current_price <= 0:
        return {"symbol": sym, "status": "no_price"}

    # ── 상위 TF HMA 마스터 필터 ──────────────────────────────────────────────
    hma_rising_val = None
    if strategy.hma_filter.enabled:
        hma_period = strategy.hma_filter.period
        hma_tf = strategy.hma_filter.timeframe
        hma_resp = await asyncio.to_thread(_toss.get_candles, sym, hma_tf, hma_period + 20)
        hma_candles = _parse_candles(hma_resp)
        if len(hma_candles) >= hma_period:
            hma_closes = [c["closePrice"] for c in hma_candles]
            hma_rising_val = ind.hma_rising(hma_closes, hma_period)

    # ── 신호 상태 로드 + 신호 생성 ───────────────────────────────────────────
    state = await signal_state.aget_state(sym)
    result = signal_mod.generate_signal(strategy, candles_1m, hma_rising_val, state)

    action = result["action"]
    new_state = result["new_state"]
    reasoning = result["reasoning"]
    inds = result.get("indicators", {})

    # ── 발주 ─────────────────────────────────────────────────────────────────
    placed = []

    # 종목별 배분 예산으로 매수 수량 계산
    budget_usd = float(watch_item.get("budget_usd", 0))
    entry_qty = max(1, int(budget_usd / current_price)) if budget_usd > 0 and current_price > 0 else 0

    entry_price_for_log = None

    if action == signal_mod.BUY:
        if entry_qty > 0:
            order_result = _order_manager.place_limit(sym, market, "buy", entry_qty, current_price)
            placed.append({
                "action": "BUY", "qty": entry_qty, "price": current_price,
                "result": order_result.get("status"),
            })
            entry_price_for_log = current_price
            logger.info("watcher_buy", symbol=sym, qty=entry_qty, price=current_price,
                        budget_usd=budget_usd, result=order_result.get("status"), reasoning=reasoning)
        else:
            logger.warning("watcher_buy_skipped_no_budget", symbol=sym,
                           note="budget_usd not set on watchlist item")

    elif action == signal_mod.SELL_HALF:
        half_qty = max(1, total_qty // 2)
        order_result = _order_manager.place_limit(sym, market, "sell", half_qty, current_price)
        placed.append({
            "action": "SELL_HALF", "qty": half_qty, "price": current_price,
            "result": order_result.get("status"),
        })
        entry_price_for_log = state.get("entry_price")
        logger.info("watcher_sell_half", symbol=sym, qty=half_qty, price=current_price,
                    result=order_result.get("status"), reasoning=reasoning)

    elif action == signal_mod.SELL_ALL:
        if total_qty > 0:
            order_result = _order_manager.place_limit(sym, market, "sell", total_qty, current_price)
            placed.append({
                "action": "SELL_ALL", "qty": total_qty, "price": current_price,
                "result": order_result.get("status"),
            })
            entry_price_for_log = state.get("entry_price")
            logger.info("watcher_sell_all", symbol=sym, qty=total_qty, price=current_price,
                        result=order_result.get("status"), reasoning=reasoning)

    # ── 상태 저장 + trade_log 기록 ───────────────────────────────────────────
    await signal_state.aput_state(sym, new_state)

    if action != signal_mod.NONE:
        # SELL 시 손익률 계산
        return_rate = None
        if action in (signal_mod.SELL_HALF, signal_mod.SELL_ALL) and entry_price_for_log and entry_price_for_log > 0:
            return_rate = round((current_price - entry_price_for_log) / entry_price_for_log, 4)

        trade_qty = (
            entry_qty if action == signal_mod.BUY
            else (total_qty // 2 if action == signal_mod.SELL_HALF else total_qty)
        )
        await arecord_trade({
            "ts": now_ms,
            "ticker": sym,
            "signal": action,
            "rsi": inds.get("rsi"),
            "sentiment": 0.0,
            "confidence": 1.0,
            "strategy_version": strategy.version,
            "side": "buy" if action == signal_mod.BUY else "sell",
            "quantity": trade_qty,
            "price": current_price,
            "entry_price": entry_price_for_log,
            "return_rate": return_rate,
            "reasoning": reasoning,
        })

    return {
        "symbol": sym,
        "status": "ok",
        "price": current_price,
        "total_qty": total_qty,
        "action": action,
        "reasoning": reasoning,
        "signal_state": new_state.get("state"),
        "hma_rising": hma_rising_val,
        "fills": placed,
        "indicators": inds,
    }
