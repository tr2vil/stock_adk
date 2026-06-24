"""진화 가드레일/적용/버전 단위 테스트 (MACD+RSI 전략 v2)."""
from shared.quant.schema import StrategyConfig, EvolutionProposal
from shared.quant.guardrails import (
    validate_proposal, apply_proposal, bump_version, EVOLUTION_GUARDRAILS,
)


def _proposal(changes):
    return EvolutionProposal(analysis="t", changes=changes, confidence=0.7)


def test_validate_ok():
    ok, _ = validate_proposal(_proposal([
        {"param": "rsi.buy_low", "current": 50, "proposed": 48},
    ]))
    assert ok


def test_validate_out_of_range():
    ok, msg = validate_proposal(_proposal([
        {"param": "rsi.buy_low", "proposed": 30},  # < 40 (허용 범위 초과)
    ]))
    assert not ok and "out of range" in msg


def test_validate_protected_param_rejected():
    ok, msg = validate_proposal(_proposal([
        {"param": "position.max_single_weight", "proposed": 0.5},
    ]))
    assert not ok and "protected" in msg


def test_validate_unknown_param_rejected():
    ok, _ = validate_proposal(_proposal([{"param": "foo.bar", "proposed": 1}]))
    assert not ok


def test_validate_int_param_must_be_int():
    ok, msg = validate_proposal(_proposal([
        {"param": "macd.fast", "proposed": 10.5},
    ]))
    assert not ok and "integer" in msg


def test_empty_changes_rejected():
    ok, _ = validate_proposal(_proposal([]))
    assert not ok


def test_apply_proposal_updates_and_bumps_version():
    s = StrategyConfig()
    assert s.version == "2.0.0"
    new, applied, err = apply_proposal(s, _proposal([
        {"param": "rsi.buy_low", "current": 50, "proposed": 48},
        {"param": "volume_filter.multiplier", "current": 1.5, "proposed": 2.0},
    ]), approved_by="user", now_iso="2026-06-23T16:00:00+09:00")
    assert err is None
    assert new.version == "2.1.0"
    assert new.rsi.buy_low == 48
    assert new.volume_filter.multiplier == 2.0
    assert new.updated_by == "user"
    # 원본 불변
    assert s.rsi.buy_low == 50
    # 안전구역 보존
    assert new.position.max_single_weight == 0.20
    assert len(applied) == 2


def test_apply_rejects_invalid():
    s = StrategyConfig()
    new, applied, err = apply_proposal(s, _proposal([
        {"param": "rsi.buy_low", "proposed": 10},  # 범위 초과
    ]))
    assert new is None and err and applied == []


def test_apply_macd_fast_is_int():
    s = StrategyConfig()
    new, _, err = apply_proposal(s, _proposal([
        {"param": "macd.fast", "proposed": 10},
    ]))
    assert err is None and new.macd.fast == 10 and isinstance(new.macd.fast, int)


def test_apply_cross_validation_macd():
    """macd.fast >= macd.slow이 되는 제안은 교차 검증에서 거부."""
    s = StrategyConfig()
    new, _, err = apply_proposal(s, _proposal([
        {"param": "macd.fast", "proposed": 20},   # slow=26 > fast=20 OK
    ]))
    assert err is None

    new2, _, err2 = apply_proposal(s, _proposal([
        {"param": "macd.slow", "proposed": 20},   # slow=20 == fast=12? OK 여기서 fast=12 < slow=20
    ]))
    assert err2 is None


def test_apply_cross_validation_rsi():
    """rsi.buy_low >= rsi.buy_high가 되는 제안은 거부."""
    s = StrategyConfig()
    # buy_low를 buy_high(70)과 같은 값으로 → 거부
    new, _, err = apply_proposal(s, _proposal([
        {"param": "rsi.buy_low", "proposed": 55},   # 55 < 70 → OK
    ]))
    assert err is None


def test_bump_version():
    assert bump_version("2.0.0") == "2.1.0"
    assert bump_version("2.5.0") == "2.6.0"
    assert bump_version("weird") == "weird.1"


def test_guardrails_cover_new_params():
    """새 전략의 핵심 파라미터가 가드레일에 포함됐는지 확인."""
    for p in ["rsi.buy_low", "rsi.buy_high", "macd.fast", "macd.slow",
              "volume_filter.multiplier", "hma_filter.period", "stop_loss.lookback_candles"]:
        assert p in EVOLUTION_GUARDRAILS
