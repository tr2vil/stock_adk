"""진화 가드레일/적용/버전 단위 테스트 (순수 함수)."""
from shared.quant.schema import StrategyConfig, EvolutionProposal
from shared.quant.guardrails import (
    validate_proposal, apply_proposal, bump_version, EVOLUTION_GUARDRAILS,
)


def _proposal(changes):
    return EvolutionProposal(analysis="t", changes=changes, confidence=0.7)


def test_validate_ok():
    ok, _ = validate_proposal(_proposal([
        {"param": "momentum.rsi_buy_threshold", "current": 30, "proposed": 26},
    ]))
    assert ok


def test_validate_out_of_range():
    ok, msg = validate_proposal(_proposal([
        {"param": "momentum.rsi_buy_threshold", "proposed": 50},  # >40
    ]))
    assert not ok and "out of range" in msg


def test_validate_protected_param_rejected():
    # position.* 은 가드레일 목록에 없음 → 변경 불가
    ok, msg = validate_proposal(_proposal([
        {"param": "position.max_single_weight", "proposed": 0.5},
    ]))
    assert not ok and "protected" in msg


def test_validate_unknown_param_rejected():
    ok, _ = validate_proposal(_proposal([{"param": "foo.bar", "proposed": 1}]))
    assert not ok


def test_validate_ma_period_must_be_int():
    ok, msg = validate_proposal(_proposal([
        {"param": "momentum.ma_period", "proposed": 20.5},
    ]))
    assert not ok and "integer" in msg


def test_empty_changes_rejected():
    ok, _ = validate_proposal(_proposal([]))
    assert not ok


def test_apply_proposal_updates_and_bumps_version():
    s = StrategyConfig()
    assert s.version == "1.0.0"
    new, applied, err = apply_proposal(s, _proposal([
        {"param": "momentum.rsi_buy_threshold", "current": 30, "proposed": 26},
        {"param": "stop_loss.rate", "current": 0.05, "proposed": 0.04},
    ]), approved_by="user", now_iso="2026-06-19T16:00:00+09:00")
    assert err is None
    assert new.version == "1.1.0"
    assert new.momentum.rsi_buy_threshold == 26
    assert new.stop_loss.rate == 0.04
    assert new.updated_by == "user"
    # 원본 불변
    assert s.momentum.rsi_buy_threshold == 30
    # 안전구역 보존
    assert new.position.max_single_weight == 0.20
    assert len(applied) == 2


def test_apply_rejects_invalid():
    s = StrategyConfig()
    new, applied, err = apply_proposal(s, _proposal([
        {"param": "stop_loss.rate", "proposed": 0.01},  # <0.03 (손절 완화 금지)
    ]))
    assert new is None and err and applied == []


def test_apply_ma_period_is_int():
    s = StrategyConfig()
    new, _, err = apply_proposal(s, _proposal([
        {"param": "momentum.ma_period", "proposed": 15},
    ]))
    assert err is None and new.momentum.ma_period == 15 and isinstance(new.momentum.ma_period, int)


def test_bump_version():
    assert bump_version("1.0.0") == "1.1.0"
    assert bump_version("2.5.0") == "2.6.0"
    assert bump_version("weird") == "weird.1"


def test_guardrails_cover_spec_params():
    for p in ["momentum.rsi_buy_threshold", "momentum.rsi_sell_threshold",
              "momentum.sentiment_min", "stop_loss.rate",
              "news_defense.sentiment_threshold"]:
        assert p in EVOLUTION_GUARDRAILS
