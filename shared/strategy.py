"""
스윙 밴드 매매 전략 저장소 (Redis 기반).

데이터:
- 워치리스트: 사용자가 모니터링할 종목
- 밴드 설정: 전역 기본값 + 종목별 오버라이드 (사다리 매도/매수, 스윙 비율)
- 플랜: LLM이 제안(proposed) → 사용자 승인(active)

키:
  strategy:watchlist
  strategy:config:_default
  strategy:config:{symbol}
  strategy:plan:proposed:{symbol}
  strategy:plan:active:{symbol}
"""
import re
import json

from shared.redis_client import get_async_redis

# ── 기본 밴드 설정 ──
# sell_ladder offset_pct: 기대값(target_price) 기준 상대 오프셋
# buy_ladder  offset_pct: 적정매수가(buy_anchor) 기준 상대 오프셋
# fraction: 스윙 트랜치 중 해당 단에서 매도/매수할 비율
DEFAULT_BAND_CONFIG = {
    "swing_fraction": 0.20,  # 보유의 20%만 스윙(나머지 80% 코어 고정)
    "notional_swing_qty": 0,  # 0 보유(신규 진입) 시 매수 기준 트랜치 수량. 0이면 신규 매수 안 함(안전 기본값)
    "hysteresis_pct": 0.03,  # 재무장 히스테리시스: 체결가 대비 ±3% 되돌림 필요
    "cooldown_sec": 1800,    # 재무장 쿨다운: 마지막 체결 후 최소 30분
    "sell_ladder": [
        {"offset_pct": 0.00, "fraction": 0.34},
        {"offset_pct": 0.05, "fraction": 0.33},
        {"offset_pct": 0.10, "fraction": 0.33},
    ],
    "buy_ladder": [
        {"offset_pct": 0.00, "fraction": 0.34},
        {"offset_pct": -0.05, "fraction": 0.33},
        {"offset_pct": -0.10, "fraction": 0.33},
    ],
}

_WATCHLIST_KEY = "strategy:watchlist"
_CFG_PREFIX = "strategy:config:"
_PLAN_PROPOSED = "strategy:plan:proposed:"
_PLAN_ACTIVE = "strategy:plan:active:"
_WATCHER_ENABLED = "strategy:watcher:enabled"
_WATCHER_STATUS = "strategy:watcher:status"
_TRADING_BUDGET_KEY = "settings:trading_budget_usd"


# ── 워치리스트 ──

async def aget_watchlist() -> list[dict]:
    """워치리스트 조회. [{symbol, market, name}]"""
    raw = await get_async_redis().get(_WATCHLIST_KEY)
    return json.loads(raw) if raw else []


async def aset_watchlist(items: list[dict]) -> None:
    await get_async_redis().set(_WATCHLIST_KEY, json.dumps(items, ensure_ascii=False))


# ── 트레이딩 예산 ──

async def aget_trading_budget() -> float:
    """총 트레이딩 예산(USD) 조회. 미설정이면 0.0."""
    raw = await get_async_redis().get(_TRADING_BUDGET_KEY)
    try:
        return float(raw) if raw else 0.0
    except (ValueError, TypeError):
        return 0.0


async def aset_trading_budget(budget_usd: float) -> None:
    """총 트레이딩 예산(USD) 저장."""
    await get_async_redis().set(_TRADING_BUDGET_KEY, str(max(0.0, budget_usd)))


async def aget_allocated_budget(watchlist: list[dict] | None = None) -> float:
    """워치리스트 종목들에 이미 배분된 예산 합계(USD)."""
    if watchlist is None:
        watchlist = await aget_watchlist()
    return sum(float(w.get("budget_usd", 0)) for w in watchlist)


# ── 밴드 설정 ──

async def aget_band_config(symbol: str | None = None) -> dict:
    """밴드 설정 조회. symbol을 주면 전역 기본값에 종목별 오버라이드를 병합.

    오버라이드된 키만 교체(사다리/스윙비율은 통째 교체).
    """
    r = get_async_redis()
    raw_default = await r.get(_CFG_PREFIX + "_default")
    cfg = json.loads(raw_default) if raw_default else dict(DEFAULT_BAND_CONFIG)

    if symbol:
        raw_override = await r.get(_CFG_PREFIX + symbol)
        if raw_override:
            cfg = {**cfg, **json.loads(raw_override)}
    return cfg


async def aset_band_config(scope: str, config: dict) -> None:
    """밴드 설정 저장. scope = '_default' 또는 종목코드."""
    await get_async_redis().set(_CFG_PREFIX + scope, json.dumps(config, ensure_ascii=False))


# ── 플랜 (제안/활성) ──

async def aget_proposed_plan(symbol: str) -> dict | None:
    raw = await get_async_redis().get(_PLAN_PROPOSED + symbol)
    return json.loads(raw) if raw else None


async def aset_proposed_plan(symbol: str, plan: dict) -> None:
    await get_async_redis().set(_PLAN_PROPOSED + symbol, json.dumps(plan, ensure_ascii=False))


async def aget_active_plan(symbol: str) -> dict | None:
    raw = await get_async_redis().get(_PLAN_ACTIVE + symbol)
    return json.loads(raw) if raw else None


async def aset_active_plan(symbol: str, plan: dict) -> None:
    await get_async_redis().set(_PLAN_ACTIVE + symbol, json.dumps(plan, ensure_ascii=False))


async def adelete_active_plan(symbol: str) -> None:
    await get_async_redis().delete(_PLAN_ACTIVE + symbol)


async def aget_all_plans() -> list[dict]:
    """워치리스트 종목별 제안/활성 플랜을 모아서 반환."""
    watch = await aget_watchlist()
    out = []
    for item in watch:
        sym = item["symbol"]
        out.append({
            "symbol": sym,
            "market": item.get("market"),
            "name": item.get("name"),
            "proposed": await aget_proposed_plan(sym),
            "active": await aget_active_plan(sym),
        })
    return out


# ── 분석 리포트 → 제안 플랜 파싱 (best-effort) ──

_ACTION_CONVICTION = {"BUY": 0.7, "HOLD": 0.4, "SELL": 0.2}


def _parse_number(text: str) -> float | None:
    """'₩345,000' / '$182.5' 등에서 숫자만 추출."""
    m = re.search(r"([0-9][0-9,]*\.?[0-9]*)", text.replace(",", ""))
    # 위에서 콤마 제거했으므로 다시 단순 매칭
    m = re.search(r"([0-9]+\.?[0-9]*)", text.replace(",", ""))
    return float(m.group(1)) if m else None


def build_proposed_plan(
    symbol: str,
    market: str,
    name: str,
    report: str,
    current_price: float,
) -> dict:
    """5-에이전트 분석 마크다운에서 기대값/적정매수가/확신도를 추출(실패 시 현재가 기반 기본값).

    하이브리드: 여기서 제안하고, 사용자가 승인 시 수정 가능.
    """
    action_m = re.search(r"\*\*Action\*\*:\s*(BUY|SELL|HOLD)", report or "", re.IGNORECASE)
    action = action_m.group(1).upper() if action_m else "HOLD"
    conviction = _ACTION_CONVICTION.get(action, 0.4)

    # 목표가 파싱 → 기대값(매도 앵커)
    target_price = None
    tm = re.search(r"목표가[^0-9]*([0-9,]+\.?[0-9]*)", report or "")
    if tm:
        target_price = _parse_number(tm.group(1))
    if not target_price or target_price <= 0:
        target_price = round(current_price * 1.10, 2)  # 기본: 현재가 +10%

    # 손절가 파싱 → 적정매수가(매수 앵커) 후보, 없으면 현재가 -5%
    buy_anchor = None
    sm = re.search(r"손절가[^0-9]*([0-9,]+\.?[0-9]*)", report or "")
    if sm:
        buy_anchor = _parse_number(sm.group(1))
    if not buy_anchor or buy_anchor <= 0:
        buy_anchor = round(current_price * 0.95, 2)  # 기본: 현재가 -5%

    return {
        "symbol": symbol,
        "market": market,
        "name": name,
        "current_price": current_price,
        "target_price": target_price,
        "buy_anchor": buy_anchor,
        "action": action,
        "conviction": conviction,
        "report": report,
        "source": "llm",
        # 결정론적 기본 근거(추출 LLM 성공 시 덮어씀)
        "target_basis": "분석 리포트의 목표가 파싱값" if tm else "현재가 +10% 기본값(목표가 미검출)",
        "buy_basis": "분석 리포트의 손절가 파싱값" if sm else "현재가 -5% 기본값(지지선 미검출)",
    }


def parse_extracted_anchors(text: str) -> dict | None:
    """추출 에이전트의 JSON 응답을 파싱(코드펜스/잡텍스트 허용)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def apply_extracted_anchors(plan: dict, extracted: dict | None, current_price: float) -> dict:
    """추출된 앵커/근거를 플랜에 검증·반영. 비정상값은 무시(기존값 유지).

    유효 조건: 양수. current_price>0이면 합리 범위(현재가의 0.3~3배) 클램프.
    """
    if not extracted:
        return plan

    def _valid(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        if v <= 0:
            return None
        if current_price > 0 and not (current_price * 0.3 <= v <= current_price * 3):
            return None
        return round(v, 2)

    tp = _valid(extracted.get("target_price"))
    ba = _valid(extracted.get("buy_anchor"))
    if tp is not None:
        plan["target_price"] = tp
    if ba is not None:
        plan["buy_anchor"] = ba
    if extracted.get("target_basis"):
        plan["target_basis"] = str(extracted["target_basis"])[:300]
    if extracted.get("buy_basis"):
        plan["buy_basis"] = str(extracted["buy_basis"])[:300]
    try:
        conv = float(extracted.get("conviction"))
        if 0 <= conv <= 1:
            plan["conviction"] = conv
    except (TypeError, ValueError):
        pass
    if tp is not None or ba is not None:
        plan["source"] = "llm_extracted"
    return plan


# ══════════════════════════════════════════════════════════════════
# 사다리 상태머신 (Phase 2 — 결정론적, LLM 미사용)
#
# 활성 플랜에 사다리(ladder)를 materialize하여 저장한다. 각 단(level)은
# 가격·수량비율·상태를 가진다.
#   state ∈ ARMED | FILLED
#     ARMED : 교차 시 발주 대상
#     FILLED: 이미 체결(DRY_RUN은 즉시 체결 가정). 히스테리시스+쿨다운
#             조건 충족 시 ARMED로 재무장.
# 재무장(단별 히스테리시스): 매도단은 체결가보다 hysteresis% 아래로
# 되돌아오고 cooldown 경과 시 ARMED, 매수단은 그 반대. → "고점 실현·
# 저점 되사기" 반복 + 단별 thrash 방지.
# ══════════════════════════════════════════════════════════════════

ARMED = "ARMED"
FILLED = "FILLED"


def build_ladder(plan: dict, config: dict) -> list[dict]:
    """활성 플랜 + 밴드 설정으로 사다리 단들을 materialize.

    매도단 가격 = target_price × (1 + offset_pct)
    매수단 가격 = buy_anchor  × (1 + offset_pct)

    Returns:
        list[dict]: [{id, side, level, price, fraction, state,
                      last_fill_at, last_fill_price}]
    """
    target = float(plan.get("target_price") or 0)
    anchor = float(plan.get("buy_anchor") or 0)
    ladder: list[dict] = []

    for i, lv in enumerate(config.get("sell_ladder", [])):
        price = round(target * (1 + float(lv["offset_pct"])), 2)
        ladder.append({
            "id": f"sell-{i}", "side": "SELL", "level": i,
            "price": price, "fraction": float(lv["fraction"]),
            "state": ARMED, "last_fill_at": None, "last_fill_price": None,
        })
    for i, lv in enumerate(config.get("buy_ladder", [])):
        price = round(anchor * (1 + float(lv["offset_pct"])), 2)
        ladder.append({
            "id": f"buy-{i}", "side": "BUY", "level": i,
            "price": price, "fraction": float(lv["fraction"]),
            "state": ARMED, "last_fill_at": None, "last_fill_price": None,
        })
    return ladder


def evaluate_ladder(
    ladder: list[dict],
    current_price: float,
    total_qty: int,
    swing_qty: int,
    core_qty: int,
    hysteresis_pct: float,
    cooldown_sec: int,
    now_ms: int,
    buy_base_qty: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """사다리를 평가하여 (발주 목록, 갱신된 사다리)를 반환하는 순수 함수.

    1) 재무장: FILLED 단이 히스테리시스+쿨다운 충족 시 ARMED로 복귀.
    2) 발주: ARMED 단이 가격 교차 시 발주(매도 price≥단가, 매수 price≤단가).
       DRY_RUN 가정으로 발주 즉시 FILLED 처리(last_fill 기록).
    코어 보호: 매도 누적 후 보유가 core_qty 밑으로 내려가지 않도록 클램프.

    매도 수량 = floor(swing_qty × fraction)  — 보유 기반(코어 보호).
    매수 수량 = floor(buy_base_qty × fraction) — buy_base_qty 미지정 시 swing_qty.
    → 보유 0(신규 진입)이면 swing_qty=0이라 매수가 안 되므로, 워처가
      notional_swing_qty를 buy_base_qty로 넘겨 부트스트랩을 허용한다.

    Args:
        total_qty: 현재 보유 수량(토스 동기화값)
        swing_qty: 스윙 매도 가능 수량 = total_qty - core_qty
        core_qty: 코어 고정 수량(이 밑으로 매도 금지)
        buy_base_qty: 매수 트랜치 기준 수량(신규 진입 대응). None이면 swing_qty.

    Returns:
        (fills, new_ladder)
          fills: [{id, side, qty, price}]
          new_ladder: 상태 갱신된 사다리(원본 비변경)
    """
    if buy_base_qty is None:
        buy_base_qty = swing_qty
    new = [dict(lv) for lv in ladder]

    # 1) 재무장 (발주 평가 전에 수행)
    for lv in new:
        if lv["state"] != FILLED or not lv.get("last_fill_at"):
            continue
        if (now_ms - lv["last_fill_at"]) / 1000.0 < cooldown_sec:
            continue
        if lv["side"] == "SELL" and current_price <= lv["price"] * (1 - hysteresis_pct):
            lv["state"] = ARMED
        elif lv["side"] == "BUY" and current_price >= lv["price"] * (1 + hysteresis_pct):
            lv["state"] = ARMED

    # 2) 발주
    fills: list[dict] = []
    committed_sell = 0  # 이번 평가에서 매도 확정된 누적 수량(코어 보호용)
    for lv in new:
        if lv["state"] != ARMED:
            continue

        if lv["side"] == "SELL" and current_price >= lv["price"]:
            qty = int(swing_qty * lv["fraction"])  # floor, 보유 기반
            if qty <= 0:
                continue
            # 코어 보호: 보유 - 누적매도 - 이번수량 ≥ core_qty
            allowed = total_qty - committed_sell - core_qty
            if allowed <= 0:
                continue
            qty = min(qty, allowed)
            committed_sell += qty
            fills.append({"id": lv["id"], "side": "SELL", "qty": qty, "price": lv["price"]})
            lv["state"] = FILLED
            lv["last_fill_at"] = now_ms
            lv["last_fill_price"] = current_price
        elif lv["side"] == "BUY" and current_price <= lv["price"]:
            qty = int(buy_base_qty * lv["fraction"])  # floor, 신규 진입 기준
            if qty <= 0:
                continue
            fills.append({"id": lv["id"], "side": "BUY", "qty": qty, "price": lv["price"]})
            lv["state"] = FILLED
            lv["last_fill_at"] = now_ms
            lv["last_fill_price"] = current_price

    return fills, new


async def aupdate_active_ladder(symbol: str, ladder: list[dict]) -> None:
    """활성 플랜의 ladder 필드만 갱신 저장(플랜이 있을 때만)."""
    plan = await aget_active_plan(symbol)
    if not plan:
        return
    plan["ladder"] = ladder
    await aset_active_plan(symbol, plan)


# ── 워처 토글 / 상태 (수동 토글) ──

async def aget_watcher_enabled() -> bool:
    return (await get_async_redis().get(_WATCHER_ENABLED)) == "1"


async def aset_watcher_enabled(enabled: bool) -> None:
    await get_async_redis().set(_WATCHER_ENABLED, "1" if enabled else "0")


async def aget_watcher_status() -> dict:
    raw = await get_async_redis().get(_WATCHER_STATUS)
    return json.loads(raw) if raw else {}


async def aset_watcher_status(status: dict) -> None:
    await get_async_redis().set(_WATCHER_STATUS, json.dumps(status, ensure_ascii=False))
