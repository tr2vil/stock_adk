"""US 소형주 유니버스 스캐너 — yfinance 기반.

Ross Cameron 매매법에 적합한 종목 조건:
  - 시가총액: $300M ~ $2B (소형주)
  - 유통주식수(Float): 100M주 이하
  - 상대 거래량: 평균의 1.5배 이상
  - 시가 갭: 전일 종가 대비 +4% 이상

빅테크(Mega-Cap)는 Float이 수십억 주에 달해 '에어 포켓' 급등이 발생하지 않으므로
이 전략에 적합하지 않다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── 기본 필터 기준값 ────────────────────────────────────────────────────────
DEFAULT_FILTERS = {
    "market_cap_min": 300_000_000,    # $300M
    "market_cap_max": 2_000_000_000,  # $2B
    "float_max": 100_000_000,         # 100M주
    "rel_volume_min": 1.5,            # 평균 거래량의 1.5배
    "gap_min": 0.04,                  # +4% 갭업
}

FIT_OK = "fit"
FIT_BORDER = "border"
FIT_REJECT = "reject"


@dataclass
class ScreenResult:
    symbol: str
    market_cap: float | None = None         # USD
    float_shares: float | None = None       # 주수
    rel_volume: float | None = None         # 배수
    gap_pct: float | None = None            # 소수 (0.05 = 5%)
    current_price: float | None = None
    company_name: str = ""
    fit: str = FIT_REJECT                   # "fit" | "border" | "reject"
    reasons: list[str] = field(default_factory=list)   # 부적합 사유
    border_reasons: list[str] = field(default_factory=list)  # 경계 사유

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "current_price": self.current_price,
            "market_cap": self.market_cap,
            "float_shares": self.float_shares,
            "rel_volume": self.rel_volume,
            "gap_pct": self.gap_pct,
            "fit": self.fit,
            "reasons": self.reasons,
            "border_reasons": self.border_reasons,
        }


def _fmt_cap(v: float | None) -> str:
    if v is None:
        return "N/A"
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    return f"${v / 1_000_000:.0f}M"


def check_stock(symbol: str, filters: dict | None = None) -> ScreenResult:
    """단일 종목 유니버스 적합성 판정.

    Args:
        symbol: US 티커 (예: "CRWD", "AAPL")
        filters: 필터 기준 (None이면 DEFAULT_FILTERS 사용)

    Returns:
        ScreenResult
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed")
        return ScreenResult(symbol=symbol, fit=FIT_REJECT, reasons=["yfinance 미설치"])

    f = {**DEFAULT_FILTERS, **(filters or {})}
    result = ScreenResult(symbol=symbol.upper())

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        result.company_name = info.get("shortName") or info.get("longName") or symbol
        result.current_price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        result.market_cap = info.get("marketCap")
        result.float_shares = info.get("floatShares")

        # 상대 거래량
        avg_vol = info.get("averageVolume") or info.get("averageVolume10days")
        cur_vol = info.get("volume") or info.get("regularMarketVolume")
        if avg_vol and cur_vol and avg_vol > 0:
            result.rel_volume = round(cur_vol / avg_vol, 2)

        # 시가 갭
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        open_price = info.get("open") or info.get("regularMarketOpen")
        if prev_close and open_price and prev_close > 0:
            result.gap_pct = round((open_price - prev_close) / prev_close, 4)

    except Exception as e:
        logger.warning("yfinance fetch failed for %s: %s", symbol, e)
        result.reasons.append(f"데이터 조회 실패: {e}")
        result.fit = FIT_REJECT
        return result

    # ── 판정 ────────────────────────────────────────────────────────────────
    hard_fail = []    # 완전 부적합
    border = []       # 경계 (사용자 판단)

    # 시가총액
    cap = result.market_cap
    if cap is None:
        hard_fail.append("시가총액 데이터 없음")
    elif cap > f["market_cap_max"] * 5:
        hard_fail.append(f"빅테크 ({_fmt_cap(cap)}) — Float 과다 우려")
    elif cap > f["market_cap_max"]:
        border.append(f"시가총액 상단 초과 ({_fmt_cap(cap)} > $2B)")
    elif cap < f["market_cap_min"]:
        border.append(f"시가총액 하단 미달 ({_fmt_cap(cap)} < $300M, 유동성 주의)")

    # 유통주식수
    fl = result.float_shares
    if fl is None:
        border.append("Float 데이터 없음 (수동 확인 필요)")
    elif fl > f["float_max"] * 10:
        hard_fail.append(f"Float 과다 ({fl / 1_000_000:.0f}M주) — 급등 불가")
    elif fl > f["float_max"]:
        border.append(f"Float 상단 초과 ({fl / 1_000_000:.0f}M주 > 100M주)")

    # 상대 거래량 (장중에만 의미 있음, 없으면 경고만)
    rv = result.rel_volume
    if rv is not None and rv < f["rel_volume_min"]:
        border.append(f"상대 거래량 부족 ({rv:.1f}x < {f['rel_volume_min']}x)")

    # 시가 갭 (당일 장 시작 기준, 장 이후에는 참고값)
    gp = result.gap_pct
    if gp is not None and gp < f["gap_min"]:
        border.append(f"시가 갭 부족 ({gp * 100:.1f}% < {f['gap_min'] * 100:.0f}%)")

    # 최종 판정
    if hard_fail:
        result.fit = FIT_REJECT
        result.reasons = hard_fail
        result.border_reasons = border
    elif border:
        result.fit = FIT_BORDER
        result.border_reasons = border
    else:
        result.fit = FIT_OK

    return result


def check_stocks(symbols: list[str], filters: dict | None = None) -> list[dict]:
    """복수 종목 일괄 판정.

    Returns:
        list of ScreenResult.to_dict()
    """
    results = []
    for sym in symbols:
        sym = sym.strip().upper()
        if not sym:
            continue
        try:
            r = check_stock(sym, filters)
            results.append(r.to_dict())
        except Exception as e:
            logger.error("screener error for %s: %s", sym, e)
            results.append({
                "symbol": sym, "fit": FIT_REJECT,
                "reasons": [f"오류: {e}"], "border_reasons": [],
            })
    return results
