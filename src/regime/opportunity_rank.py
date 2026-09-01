"""공포/주시 구간용 가치 기준 검토 순위 (Score와 별도)"""
from __future__ import annotations

from typing import Any, Optional


# 개별주 우선 (ETF는 페널티)
ETF_CODES = {"069500", "472150", "360750"}


def _comp(components: dict, key: str, default: float = 50.0) -> float:
    if not components:
        return default
    if key in components:
        try:
            return float(components[key])
        except (TypeError, ValueError):
            return default
    for k, v in components.items():
        if str(k).lower() == key.lower():
            try:
                return float(v)
            except (TypeError, ValueError):
                return default
    return default


def score_opportunity(row: dict[str, Any]) -> dict[str, Any]:
    """
    row keys: code, name, score_data, panic_type, price_data
    """
    s = row.get("score_data") or {}
    components = s.get("components") or {}
    code = str(row.get("code") or "")
    panic_type = (row.get("panic_class") or {}).get("type") or "none"

    value = _comp(components, "value")
    price = _comp(components, "price")
    quality = _comp(components, "quality")
    risk = _comp(components, "risk")

    # 낙폭: price 매력과 고점 대비를 함께
    drop = (s.get("context") or {}).get("vs_52w_high")
    try:
        drop_f = float(drop) if drop is not None else 0.0
    except (TypeError, ValueError):
        drop_f = 0.0
    # 10~40% 낙폭 구간을 선호 (너무 작거나 극단 단독은 중간)
    if 10 <= drop_f <= 40:
        drop_score = 70 + min(drop_f, 30)
    elif drop_f > 40:
        drop_score = 75
    else:
        drop_score = 45

    # 가중 합
    raw = (
        value * 0.30
        + price * 0.20
        + quality * 0.15
        + drop_score * 0.15
        + (100 - risk) * 0.10  # risk 높으면 감점
    )

    if panic_type == "panic_like":
        raw += 8
    elif panic_type == "adverse":
        raw -= 20
    elif panic_type == "hold":
        raw -= 5

    if code in ETF_CODES:
        raw -= 12  # 기업 가치 프레임 약함

    score = max(0.0, min(100.0, round(raw, 1)))
    return {
        "opportunity_score": score,
        "parts": {
            "value": value,
            "price": price,
            "quality": quality,
            "drop_score": round(drop_score, 1),
            "risk": risk,
            "panic_type": panic_type,
        },
    }


def rank_opportunities(ok_results: list[dict]) -> list[dict]:
    """기회 점수 내림차순. 각 행에 opportunity_* 필드 추가한 복사 목록."""
    ranked = []
    for r in ok_results:
        if not r.get("ok"):
            continue
        op = score_opportunity(r)
        item = {
            **r,
            "opportunity_score": op["opportunity_score"],
            "opportunity_parts": op["parts"],
        }
        ranked.append(item)
    ranked.sort(key=lambda x: x.get("opportunity_score") or 0, reverse=True)
    for i, item in enumerate(ranked, 1):
        item["opportunity_rank"] = i
    return ranked
