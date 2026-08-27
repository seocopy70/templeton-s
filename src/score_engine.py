"""
Templeton Score 계산 엔진 (v0.5)
- v0.1: 가격 기반 지표만 사용 (Value는 placeholder 50점)
- v0.2: Value(25%) 요소에 PER/PBR 실계산 반영
- v0.3: Pessimism(15%) 요소에 시장 대비 상대 비관 반영 (마스터 문서 §10)
- v0.4: Risk(15%) 요소에 일봉 기반 연율화 변동성 반영 (Phase 2 STEP 2)
- v0.5: Quality(15%) ROE/부채비율, Growth(10%) 매출·영업이익 성장률 실계산
  · 벤치마크: KODEX 200 (069500)
  · 종목이 시장보다 크게 하락 → '개별 악재 가능성' 가점 (템플턴 기회 탐색 영역)
  · 시장 전체 급락 → '시장 공포' 가점 (최대 비관 = 기회 원칙)
  · 벤치마크 데이터가 없으면 v0.1 방식으로 우아하게 폴백
  · 앵커/계수는 실험용 초기값 — Phase 7 백테스트로 조정 예정
"""
from __future__ import annotations

from typing import Any, Optional

# ---------------------------------------------------------------
# 시장 벤치마크: KODEX 200 (관심종목 목록에 반드시 포함되어야 함)
# TODO: 종목 확대 시 config.py로 이동 검토
# ---------------------------------------------------------------
MARKET_BENCHMARK_SYMBOL = "069500"

# ---------------------------------------------------------------
# Value 스코어 앵커 테이블 (v0.2 초안)
#   (지표값, 점수) 쌍 — 사이값은 선형 보간, 범위 밖은 끝값 클램프.
#   템플턴 원칙: 낮은 밸류에이션 = 매력.
# ---------------------------------------------------------------
PER_ANCHORS: list[tuple[float, float]] = [
    (5.0, 95.0),    # 딥밸류
    (10.0, 80.0),   # 매력적
    (15.0, 60.0),   # 적정
    (20.0, 45.0),   # 다소 비쌈
    (30.0, 25.0),   # 비쌈
    (40.0, 15.0),   # 매우 비쌈
]

PBR_ANCHORS: list[tuple[float, float]] = [
    (0.5, 95.0),    # 딥밸류
    (0.8, 82.0),
    (1.2, 65.0),
    (1.8, 45.0),
    (2.5, 30.0),
    (4.0, 15.0),    # 매우 비쌈
]

# ---------------------------------------------------------------
# Risk 스코어 앵커 테이블 (v0.4 초안) — 연율화 변동성(%)
#   낮은 변동성 = 안정 = 높은 점수.
#   참고: KODEX200 ETF ~10-13%, 대형주 ~20-30%, 급락 종목 40%+
# ---------------------------------------------------------------
RISK_ANCHORS: list[tuple[float, float]] = [
    (10.0, 95.0),   # 초저변동성 (안정형 ETF 수준)
    (15.0, 85.0),
    (20.0, 70.0),   # 대형주 평균 하단
    (30.0, 50.0),   # 보통 수준
    (40.0, 32.0),
    (55.0, 15.0),   # 매우 높은 변동성
]


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _interp_anchors(anchors: list[tuple[float, float]], x: float) -> float:
    """
    앵커 테이블 선형 보간. (결정론적 순수 함수 — Phase 2 성공 기준)
    """
    pts = sorted(anchors)
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x1 <= x <= x2:
            if x2 == x1:
                return y1
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    return pts[-1][1]


def calc_value(data: dict[str, Any]) -> float:
    """
    Value (25%) — PER/PBR 기반 실계산 (v0.2)
      - PER 점수와 PBR 점수를 50:50으로 합산
      - 하나만 있으면 그 하나만 사용
      - 둘 다 없으면(ETF 등) 중립 50점
    """
    per = data.get("per")
    pbr = data.get("pbr")

    per_score: Optional[float] = _interp_anchors(PER_ANCHORS, per) if per else None
    pbr_score: Optional[float] = _interp_anchors(PBR_ANCHORS, pbr) if pbr else None

    if per_score is not None and pbr_score is not None:
        return clamp(per_score * 0.5 + pbr_score * 0.5)
    if per_score is not None:
        return clamp(per_score)
    if pbr_score is not None:
        return clamp(pbr_score)
    return 50.0  # 밸류에이션 데이터 없음 → 중립


def calc_price_attractiveness(data: dict[str, Any]) -> float:
    """Price Attractiveness (20%) — 52주 고점 대비 하락률 기반 초안"""
    drop = data.get("drop_from_52w_high")
    if drop is None:
        return 50.0
    # 0% 하락 → 30점, 30% 하락 → 약 90점 수준으로 선형 매핑 (초안)
    return clamp(30 + drop * 2.0)


def calc_pessimism(data: dict[str, Any], market: Optional[dict[str, Any]] = None) -> float:
    """
    Market Pessimism (15%) — 시장 대비 상대 비관 (v0.3)

      ① 개별 종목의 당일 하락 → 가점 (v0.1 로직, 완화)
      ② 시장보다 큰 폭 하락(상대 하락) → 개별 악재 가능성 가점 ★핵심
      ③ 시장 자체가 급락 → 시장 전체 공포 가점 (템플턴: 최대 비관 = 기회)

    market: 벤치마크(KODEX 200)의 가격 데이터 dict. 없으면 ①만 적용(폴백).
    """
    change = data.get("change_rate")
    if change is None:
        return 40.0

    score = 40.0

    # ① 개별 당일 하락
    if change < 0:
        score += min(abs(change) * 1.5, 15.0)
    else:
        score -= 5.0
    if market is not None:
        m_change = market.get("change_rate")
        if m_change is not None:
            # ② 상대 하락: 양수 = 시장보다 더 하락 → 개별 비관 신호
            rel = m_change - change
            if rel > 0:
                score += min(rel * 3.0, 25.0)
            # ③ 시장 전체 공포
            if m_change < -1.0:
                score += min(abs(m_change) * 2.5, 10.0)

    return clamp(score)


def classify_pessimism_signal(
    data: dict[str, Any], market: Optional[dict[str, Any]] = None
) -> str:
    """
    비관 신호 분류 (UI 표시 및 Phase 3 AI 해석 레이어용):
      - "individual"  : 시장보다 1.5%p 이상 추가 하락 → 개별 악재 조사 필요
      - "market_wide" : 시장이 -1% 이상 급락 → 시장 전체 위험회피
      - "none"        : 뚜렷한 비관 신호 없음
    """
    change = data.get("change_rate")
    m_change = market.get("change_rate") if market else None
    if change is None:
        return "none"
    if m_change is not None and (m_change - change) >= 1.5:
        return "individual"
    if m_change is not None and m_change <= -1.0:
        return "market_wide"
    return "none"


def calc_risk(data: dict[str, Any]) -> float:
    """
    Risk (15%) — 연율화 변동성 기반 (v0.4)
      - market_data가 일봉으로 계산한 volatility_annual(%)를 앵커 보간
      - 데이터 없으면 중립 50점 (폴백)
      - 템플턴 원칙: 높은 변동성 = 더 넓은 안전마진이 필요 → Risk 점수 하락으로 반영
    """
    vol = data.get("volatility_annual")
    if vol is None or vol <= 0:
        return 50.0
    return clamp(_interp_anchors(RISK_ANCHORS, vol))


# Quality 앵커 — ROE(%)
ROE_ANCHORS: list[tuple[float, float]] = [
    (5.0, 25.0),
    (8.0, 40.0),
    (12.0, 60.0),
    (15.0, 75.0),
    (20.0, 90.0),
    (25.0, 95.0),
]

# 부채비율(%) — 낮을수록 좋음
DEBT_ANCHORS: list[tuple[float, float]] = [
    (30.0, 95.0),
    (50.0, 80.0),
    (80.0, 60.0),
    (120.0, 40.0),
    (200.0, 20.0),
    (300.0, 10.0),
]

# Growth 앵커 — 성장률(%)
GROWTH_ANCHORS: list[tuple[float, float]] = [
    (-20.0, 15.0),
    (-5.0, 35.0),
    (0.0, 45.0),
    (5.0, 60.0),
    (15.0, 80.0),
    (30.0, 95.0),
]


def calc_quality(data: dict[str, Any]) -> float:
    """
    Quality (15%) — ROE + 부채비율 (v0.5)
    - ROE 높을수록, 부채비율 낮을수록 가점
    - 둘 다 없으면 중립 50 (ETF 등)
    """
    roe = data.get("roe")
    debt = data.get("debt_ratio")

    scores = []
    if roe is not None:
        scores.append(_interp_anchors(ROE_ANCHORS, float(roe)))
    if debt is not None:
        scores.append(_interp_anchors(DEBT_ANCHORS, float(debt)))

    if not scores:
        return 50.0
    return clamp(sum(scores) / len(scores))


def calc_growth(data: dict[str, Any]) -> float:
    """
    Growth (10%) — 매출/영업이익/순이익 성장률 평균 (v0.5)
    - 재무비율 API의 grs / bsop_prfi_inrt / ntin_inrt 활용
    - 데이터 없으면 중립 50
    """
    vals = []
    for key in ("revenue_growth", "operating_profit_growth", "net_income_growth"):
        v = data.get(key)
        if v is not None:
            vals.append(float(v))

    if not vals:
        return 50.0

    avg_g = sum(vals) / len(vals)
    return clamp(_interp_anchors(GROWTH_ANCHORS, avg_g))


def score_to_opinion(score: float) -> str:
    if score < 40:
        return "매수 회피"
    if score < 60:
        return "관망"
    if score < 75:
        return "보유/관찰"
    if score < 85:
        return "분할매수 관심"
    return "적극적 관심"


def calculate_templeton_score(
    data: dict[str, Any], market: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    v0.5 Score 계산.
    Value=PER/PBR, Pessimism=시장대비, Risk=변동성, Quality=ROE/부채, Growth=성장률.
    market(벤치마크 데이터)은 선택 인자 — 없으면 폴백 동작.
    """
    value = calc_value(data)
    price = calc_price_attractiveness(data)
    pessimism = calc_pessimism(data, market)
    quality = calc_quality(data)
    growth = calc_growth(data)
    risk = calc_risk(data)

    total = (
        value * 0.25
        + price * 0.20
        + pessimism * 0.15
        + quality * 0.15
        + growth * 0.10
        + risk * 0.15
    )
    total = clamp(total)

    m_change = market.get("change_rate") if market else None
    change = data.get("change_rate")
    rel = (m_change - change) if (m_change is not None and change is not None) else None

    return {
        "total": round(total, 1),
        "components": {
            "value": round(value, 1),
            "price": round(price, 1),
            "pessimism": round(pessimism, 1),
            "quality": round(quality, 1),
            "growth": round(growth, 1),
            "risk": round(risk, 1),
        },
        "value_inputs": {
            "per": data.get("per"),
            "pbr": data.get("pbr"),
            "method": (
                "per+pbr"
                if (data.get("per") and data.get("pbr"))
                else "per" if data.get("per")
                else "pbr" if data.get("pbr")
                else "neutral"
            ),
        },
        "pessimism_inputs": {
            "stock_change": change,
            "market_change": m_change,
            "relative_drop": round(rel, 2) if rel is not None else None,
            "signal": classify_pessimism_signal(data, market),
        },
        "risk_inputs": {
            "volatility_annual": data.get("volatility_annual"),
            "momentum_20d": data.get("momentum_20d"),
            "days_used": data.get("candle_days"),
            "method": "stdev_252" if data.get("volatility_annual") else "neutral",
        },
        "quality_inputs": {
            "roe": data.get("roe"),
            "debt_ratio": data.get("debt_ratio"),
            "method": (
                "roe+debt" if (data.get("roe") is not None and data.get("debt_ratio") is not None)
                else "roe" if data.get("roe") is not None
                else "debt" if data.get("debt_ratio") is not None
                else "neutral"
            ),
        },
        "growth_inputs": {
            "revenue_growth": data.get("revenue_growth"),
            "operating_profit_growth": data.get("operating_profit_growth"),
            "net_income_growth": data.get("net_income_growth"),
            "method": (
                "financial_ratio" if any(
                    data.get(k) is not None
                    for k in ("revenue_growth", "operating_profit_growth", "net_income_growth")
                )
                else "neutral"
            ),
        },
        "opinion": score_to_opinion(total),
    }