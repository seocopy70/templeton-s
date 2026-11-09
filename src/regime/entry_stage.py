"""분할매수 단계(entry stage) 판정 — 총점(Templeton Score)과 별도 경로.

배경: 총점 75 이상이어야 '분할매수 관심'인데, 폭락장에서는
  - Risk(15%)가 변동성 급등으로 ~15점까지 떨어지고
  - Pessimism(15%)은 '당일' 등락만 보며
  - Value(25%)는 절대 PER/PBR 기준이라
고품질 종목도 총점이 55~65에 머문다(관측 최고 64.6). 그래서 의견이 구조적으로 '관망'에 고정된다.
이 모듈은 '시장 낙폭 × 종목 낙폭' 단계 + 안전 게이트로 분할매수 검토 단계를 따로 낸다.
(실행 지시가 아니라 '검토 후보' 표시. 모든 숫자는 백테스트로 조정할 초기값)
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from regime.market_regime import DD_STEPS, dd_stage

# 종목 단독 낙폭(52주 고점 대비) 단계 — 개별주는 지수보다 더 빠지므로 더 깊게 잡는다
STOCK_STEPS: tuple[float, ...] = (-15.0, -25.0, -35.0)
ETF_CODES = {"069500", "472150", "360750"}

SCORE_FLOOR = 40.0      # 총점이 '매수 회피'(<40)면 낙폭만으로 승격하지 않음
QUALITY_FLOOR = 25.0    # 초기값. (KB금융·현대차 Quality가 부채비율 때문에 낮게 나오는 문제는 별도 수정 필요)
OPP_MIN = 50.0          # 기회 점수 하한

STAGE_OPINION = {1: "분할매수 검토 1차", 2: "분할매수 검토 2차", 3: "분할매수 검토 3차"}


def _has_negative_event(events: Optional[Sequence[dict]]) -> bool:
    for e in events or []:
        if not isinstance(e, dict):
            continue
        if e.get("importance") == "critical":
            return True
        if e.get("importance") in ("high", "critical") and e.get("sentiment") in (
            "negative", "critical_negative"
        ):
            return True
    return False


def decide_entry(
    *,
    code: str,
    base_opinion: str,
    total_score: float,
    components: dict[str, Any],
    market_dd: Optional[float],
    drop_from_52w_high: Optional[float],   # 양수 % (예: 25.0 = 고점 대비 -25%)
    opportunity_score: Optional[float],
    panic_type: str,
    events: Optional[Sequence[dict]],
    events_checked: bool,
) -> dict[str, Any]:
    """단계(stage)와 최종 의견. 게이트에 걸리면 base_opinion 유지 + blocked_by 사유 기록."""
    is_etf = code in ETF_CODES
    market_stage = dd_stage(market_dd)
    stock_dd = -float(drop_from_52w_high) if drop_from_52w_high is not None else None
    stock_stage = dd_stage(stock_dd, DD_STEPS if is_etf else STOCK_STEPS)

    # 시장도, 종목도 함께 눌려야 단계가 오른다 (시장 무풍 속 개별 급락은 '악재 의심'이지 기회 아님)
    stage = min(market_stage, stock_stage)

    blocked: list[str] = []
    if stage >= 1:
        if total_score < SCORE_FLOOR:
            blocked.append("score_floor")
        if float(components.get("quality", 50.0)) < QUALITY_FLOOR:
            blocked.append("quality_floor")
        if panic_type == "adverse":
            blocked.append("adverse")
        if _has_negative_event(events):
            blocked.append("negative_disclosure")
        if not is_etf and not events_checked:
            blocked.append("events_unchecked")
        if opportunity_score is not None and opportunity_score < OPP_MIN:
            blocked.append("opportunity_low")

    passed = stage >= 1 and not blocked
    return {
        "stage": stage if passed else 0,
        "raw_stage": stage,
        "market_stage": market_stage,
        "stock_stage": stock_stage,
        "market_drawdown": market_dd,
        "stock_drawdown": stock_dd,
        "blocked_by": blocked,
        "opinion": STAGE_OPINION[stage] if passed else base_opinion,
        "opinion_base": base_opinion,
    }
