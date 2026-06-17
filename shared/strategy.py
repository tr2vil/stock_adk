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


# ── 워치리스트 ──

async def aget_watchlist() -> list[dict]:
    """워치리스트 조회. [{symbol, market, name}]"""
    raw = await get_async_redis().get(_WATCHLIST_KEY)
    return json.loads(raw) if raw else []


async def aset_watchlist(items: list[dict]) -> None:
    await get_async_redis().set(_WATCHLIST_KEY, json.dumps(items, ensure_ascii=False))


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
    }
