"""사다리 상태머신 단위 테스트 (순수 함수, Redis/네트워크 불필요)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.strategy import (
    build_ladder, evaluate_ladder, ARMED, FILLED, DEFAULT_BAND_CONFIG,
    parse_extracted_anchors, apply_extracted_anchors,
)
from execution.watcher import is_kr_market_open, is_us_market_open, is_market_open

_KST = ZoneInfo("Asia/Seoul")
CFG = DEFAULT_BAND_CONFIG


def test_build_ladder_prices_and_count():
    plan = {"target_price": 100.0, "buy_anchor": 90.0}
    ladder = build_ladder(plan, CFG)
    assert len(ladder) == 6  # 3 매도 + 3 매수
    sells = [l for l in ladder if l["side"] == "SELL"]
    buys = [l for l in ladder if l["side"] == "BUY"]
    # 매도단: target × (1+offset)
    assert sells[0]["price"] == 100.0          # +0%
    assert sells[1]["price"] == 105.0          # +5%
    assert sells[2]["price"] == 110.0          # +10%
    # 매수단: anchor × (1+offset)
    assert buys[0]["price"] == 90.0            # 0%
    assert round(buys[1]["price"], 2) == 85.5  # -5%
    assert buys[2]["price"] == 81.0            # -10%
    assert all(l["state"] == ARMED for l in ladder)


def test_sell_fires_above_price():
    plan = {"target_price": 100.0, "buy_anchor": 90.0}
    ladder = build_ladder(plan, CFG)
    # 현재가 106 → 매도단 0(100),1(105) 발화, 2(110) 미발화
    fills, new = evaluate_ladder(ladder, 106.0, total_qty=100, swing_qty=20,
                                 core_qty=80, hysteresis_pct=0.03,
                                 cooldown_sec=1800, now_ms=1_000_000)
    sell_fills = [f for f in fills if f["side"] == "SELL"]
    assert {f["id"] for f in sell_fills} == {"sell-0", "sell-1"}
    # 수량 = floor(swing_qty × fraction): 20×0.34=6, 20×0.33=6
    assert all(f["qty"] == 6 for f in sell_fills)
    assert [l for l in new if l["id"] == "sell-0"][0]["state"] == FILLED
    assert [l for l in new if l["id"] == "sell-2"][0]["state"] == ARMED


def test_core_protection_clamps_sell():
    """스윙 수량이 매도 사다리 합보다 작아도 코어 밑으로는 못 판다."""
    plan = {"target_price": 100.0, "buy_anchor": 90.0}
    ladder = build_ladder(plan, CFG)
    # 보유 82, 코어 80 → 스윙 2주만 매도 가능. 매도단 다수 발화해도 합 ≤ 2
    fills, _ = evaluate_ladder(ladder, 120.0, total_qty=82, swing_qty=2,
                               core_qty=80, hysteresis_pct=0.03,
                               cooldown_sec=1800, now_ms=1_000_000)
    total_sell = sum(f["qty"] for f in fills if f["side"] == "SELL")
    assert total_sell <= 2


def test_rearm_requires_hysteresis_and_cooldown():
    plan = {"target_price": 100.0, "buy_anchor": 90.0}
    ladder = build_ladder(plan, CFG)
    # sell-0 을 FILLED + 방금 체결로 세팅
    for l in ladder:
        if l["id"] == "sell-0":
            l["state"] = FILLED
            l["last_fill_at"] = 1_000_000
            l["last_fill_price"] = 100.0

    # 쿨다운 미경과 → 재무장 안 됨
    _, new = evaluate_ladder(ladder, 90.0, 100, 20, 80, 0.03, 1800,
                             now_ms=1_000_000 + 60 * 1000)
    assert [l for l in new if l["id"] == "sell-0"][0]["state"] == FILLED

    # 쿨다운 경과 + 가격이 97 미만(100×0.97)으로 하락 → 재무장
    _, new2 = evaluate_ladder(ladder, 96.0, 100, 20, 80, 0.03, 1800,
                              now_ms=1_000_000 + 1801 * 1000)
    assert [l for l in new2 if l["id"] == "sell-0"][0]["state"] == ARMED

    # 쿨다운 경과했지만 가격이 충분히 안 내려옴(98) → 재무장 안 됨
    _, new3 = evaluate_ladder(ladder, 98.0, 100, 20, 80, 0.03, 1800,
                              now_ms=1_000_000 + 1801 * 1000)
    assert [l for l in new3 if l["id"] == "sell-0"][0]["state"] == FILLED


def test_buy_fires_below_price():
    plan = {"target_price": 100.0, "buy_anchor": 90.0}
    ladder = build_ladder(plan, CFG)
    # 현재가 84 → 매수단 0(90),1(85.5) 발화, 2(81) 미발화
    fills, _ = evaluate_ladder(ladder, 84.0, total_qty=100, swing_qty=20,
                               core_qty=80, hysteresis_pct=0.03,
                               cooldown_sec=1800, now_ms=1_000_000)
    buy_ids = {f["id"] for f in fills if f["side"] == "BUY"}
    assert buy_ids == {"buy-0", "buy-1"}


def test_buy_bootstrap_from_flat():
    """보유 0(신규 진입)이면 swing_qty=0이라 기본 매수는 0주지만,
    buy_base_qty(notional)를 넘기면 매수가 발화한다. 매도는 0주 유지."""
    plan = {"target_price": 100.0, "buy_anchor": 90.0}
    ladder = build_ladder(plan, CFG)
    # buy_base_qty 미지정 → swing_qty=0 → 매수도 0
    fills_none, _ = evaluate_ladder(ladder, 84.0, total_qty=0, swing_qty=0,
                                    core_qty=0, hysteresis_pct=0.03,
                                    cooldown_sec=1800, now_ms=1_000_000)
    assert [f for f in fills_none if f["side"] == "BUY"] == []
    # buy_base_qty=30 → 매수 발화 (floor(30×0.34)=10 등), 매도는 보유0이라 없음
    fills, _ = evaluate_ladder(ladder, 84.0, total_qty=0, swing_qty=0,
                               core_qty=0, hysteresis_pct=0.03,
                               cooldown_sec=1800, now_ms=1_000_000, buy_base_qty=30)
    buys = [f for f in fills if f["side"] == "BUY"]
    assert {f["id"] for f in buys} == {"buy-0", "buy-1"}
    assert buys[0]["qty"] == 10  # floor(30 × 0.34)
    assert [f for f in fills if f["side"] == "SELL"] == []


def test_market_hours():
    assert is_kr_market_open(datetime(2026, 6, 17, 10, 0, tzinfo=_KST))   # 평일 10:00
    assert is_kr_market_open(datetime(2026, 6, 17, 9, 0, tzinfo=_KST))    # 경계 09:00
    assert is_kr_market_open(datetime(2026, 6, 17, 15, 30, tzinfo=_KST))  # 경계 15:30
    assert not is_kr_market_open(datetime(2026, 6, 17, 8, 59, tzinfo=_KST))
    assert not is_kr_market_open(datetime(2026, 6, 17, 15, 31, tzinfo=_KST))
    assert not is_kr_market_open(datetime(2026, 6, 20, 11, 0, tzinfo=_KST))  # 토요일


def test_us_market_hours_and_dispatch():
    _ET = ZoneInfo("America/New_York")
    assert is_us_market_open(datetime(2026, 6, 17, 10, 0, tzinfo=_ET))       # 평일 10:00 ET
    assert is_us_market_open(datetime(2026, 6, 17, 9, 30, tzinfo=_ET))       # 경계 09:30
    assert is_us_market_open(datetime(2026, 6, 17, 16, 0, tzinfo=_ET))       # 경계 16:00
    assert not is_us_market_open(datetime(2026, 6, 17, 9, 29, tzinfo=_ET))
    assert not is_us_market_open(datetime(2026, 6, 17, 16, 1, tzinfo=_ET))
    assert not is_us_market_open(datetime(2026, 6, 20, 12, 0, tzinfo=_ET))   # 토요일
    # 디스패치: market 인자로 KR/US 분기
    assert is_market_open("US", datetime(2026, 6, 17, 10, 0, tzinfo=_ET))
    assert is_market_open("KR", datetime(2026, 6, 17, 10, 0, tzinfo=_KST))


def test_parse_extracted_anchors():
    assert parse_extracted_anchors('{"target_price": 232, "buy_anchor": 199}') == {
        "target_price": 232, "buy_anchor": 199,
    }
    # 코드펜스/잡텍스트 섞여도 추출
    fenced = '```json\n{"target_price": 1, "buy_anchor": 2}\n```'
    assert parse_extracted_anchors(fenced)["target_price"] == 1
    assert parse_extracted_anchors("") is None
    assert parse_extracted_anchors("no json here") is None


def test_apply_extracted_anchors_validates():
    base = {"target_price": 100.0, "buy_anchor": 95.0, "conviction": 0.4,
            "target_basis": "old", "buy_basis": "old", "source": "llm"}
    # 정상 반영
    out = apply_extracted_anchors(dict(base), {
        "target_price": 232.0, "buy_anchor": 199.0,
        "target_basis": "전문가 목표가 기준", "buy_basis": "지지선 기준",
        "conviction": 0.7,
    }, current_price=207.0)
    assert out["target_price"] == 232.0 and out["buy_anchor"] == 199.0
    assert out["target_basis"] == "전문가 목표가 기준"
    assert out["conviction"] == 0.7 and out["source"] == "llm_extracted"

    # 비합리값(현재가 3배 초과)은 무시 → 기존값 유지
    out2 = apply_extracted_anchors(dict(base), {"target_price": 99999.0}, current_price=207.0)
    assert out2["target_price"] == 100.0

    # extracted 없음 → 원본 유지
    assert apply_extracted_anchors(dict(base), None, 207.0)["target_price"] == 100.0
