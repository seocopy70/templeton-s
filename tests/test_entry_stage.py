import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from regime.market_regime import calc_drawdown, dd_stage, detect_market_regime
from regime.entry_stage import decide_entry
from regime.panic_classifier import classify_stock_panic
from regime.opportunity_rank import score_opportunity
import ai_interpreter


def _entry(**kw):
    base = dict(
        code="005930", base_opinion="관망", total_score=57.0,
        components={"quality": 95, "value": 20, "price": 85, "risk": 15},
        market_dd=-19.4, drop_from_52w_high=27.0, opportunity_score=60.0,
        panic_type="panic_like", events=[], events_checked=True,
    )
    base.update(kw)
    return decide_entry(**base)


def test_calc_drawdown_and_stage():
    assert calc_drawdown([90, 100, 110], current=90) == -18.18
    assert dd_stage(-9.9) == 0 and dd_stage(-10) == 1 and dd_stage(-17.5) == 2 and dd_stage(-25) == 3
    assert dd_stage(None) == 0


def test_regime_stays_panic_after_one_day_rebound():
    # 단기 조건(2~3일 누적)은 안 걸리지만 고점 대비 -19%면 panic_zone 유지
    r = detect_market_regime([90.5, 90.0, 90.2, 90.4], [0.3, 0.2, -0.1], 0.3, benchmark_drawdown=-19.4)
    assert r.regime == "panic_zone" and r.dd_stage == 2


def test_regime_default_unchanged_without_drawdown():
    r = detect_market_regime([100, 100, 100, 100], [0.1, 0.2], 0.1)
    assert r.regime == "normal" and r.dd_stage == 0


def test_stage_requires_both_market_and_stock_drawdown():
    assert _entry()["stage"] == 2                                   # min(시장2, 종목1 or 2)
    assert _entry(market_dd=-3.0)["stage"] == 0                     # 시장 무풍 → 단계 없음
    assert _entry(drop_from_52w_high=5.0)["stage"] == 0             # 종목이 안 눌림


def test_gates_block_and_keep_base_opinion():
    for kw, why in [
        (dict(panic_type="adverse"), "adverse"),
        (dict(events_checked=False), "events_unchecked"),
        (dict(total_score=35.9), "score_floor"),
        (dict(opportunity_score=30.0), "opportunity_low"),
        (dict(events=[{"importance": "high", "sentiment": "negative"}]), "negative_disclosure"),
        (dict(components={"quality": 10}), "quality_floor"),
    ]:
        out = _entry(**kw)
        assert out["stage"] == 0 and why in out["blocked_by"], (kw, out)
        assert out["opinion"] == "관망"


def test_etf_skips_event_gate_and_uses_market_steps():
    out = _entry(code="069500", components={"quality": 50}, drop_from_52w_high=19.0, events_checked=False)
    assert out["stage"] == 2 and out["opinion"] == "분할매수 검토 2차"


def test_panic_label_distinguishes_unchecked():
    p = classify_stock_panic(market_regime="panic_zone", change_rate=-0.3, market_change=-1.0,
                             events=[], events_checked=False)
    assert "공시 미조회" in " ".join(p["reasons"])


def test_opportunity_accepts_snapshot_keys_and_penalizes_volatility():
    row = lambda risk: {"code": "005930", "drop_from_52w_high": 25.0,
                        "score": {"components": {"value": 50, "price": 80, "quality": 80, "risk": risk}},
                        "panic": {"type": "panic_like"}}
    calm, wild = score_opportunity(row(90))["opportunity_score"], score_opportunity(row(15))["opportunity_score"]
    assert calm > wild
    assert score_opportunity(row(90))["parts"]["drop_score"] > 45     # 52주 낙폭이 반영됨


def test_risk_label_direction():
    comps = {"value": 50, "price": 50, "pessimism": 50, "quality": 50, "growth": 50}
    wild = ai_interpreter._build_fallback_comment("X", {"components": {**comps, "risk": 15}, "total": 50}, "관망")
    calm = ai_interpreter._build_fallback_comment("X", {"components": {**comps, "risk": 94}, "total": 50}, "관망")
    assert any("변동성 확대" in n for n in wild["negatives"])
    assert any("변동성 안정" in n for n in calm["positives"])
