"""종목 단위: panic_like / adverse / hold / none"""
from __future__ import annotations

from typing import Any, Optional, Sequence


def classify_stock_panic(
    *,
    market_regime: str,
    change_rate: Optional[float],
    market_change: Optional[float],
    events: Optional[Sequence[dict]] = None,
) -> dict[str, Any]:
    """
    Returns: {type, label_ko, reasons}
    """
    events = list(events or [])
    reasons: list[str] = []

    has_critical = any(
        isinstance(e, dict) and e.get("importance") == "critical"
        for e in events
    )
    has_high_neg = any(
        isinstance(e, dict)
        and e.get("importance") in ("high", "critical")
        and e.get("sentiment") in ("negative", "critical_negative")
        for e in events
    )

    if has_critical or has_high_neg:
        if has_critical:
            reasons.append("critical 공시")
        if has_high_neg:
            reasons.append("high 악재성 공시")
        return {
            "type": "adverse",
            "label_ko": "악재형 의심",
            "reasons": reasons,
        }

    if market_regime == "normal":
        # 시장 정상인데 종목만 급락
        if (
            change_rate is not None
            and change_rate <= -4.0
            and (market_change is None or market_change > -1.5)
        ):
            reasons.append(f"시장 대비 단독 급락 {change_rate:+.2f}%")
            return {
                "type": "adverse",
                "label_ko": "개별 급락 점검",
                "reasons": reasons,
            }
        return {"type": "none", "label_ko": "—", "reasons": []}

    # watch / panic_zone
    rel = None
    if change_rate is not None and market_change is not None:
        rel = market_change - change_rate  # + = 시장보다 더 하락

    if change_rate is not None and change_rate <= -4.0 and rel is not None and rel >= 2.0:
        reasons.append(f"시장 대비 추가 하락 {rel:+.2f}%p")
        return {
            "type": "adverse",
            "label_ko": "과매도·개별 점검",
            "reasons": reasons,
        }

    if change_rate is not None and change_rate < 0:
        reasons.append(f"시장 급락 동행 {change_rate:+.2f}%")
        if not events:
            reasons.append("중요 악재 공시 미확인")
        return {
            "type": "panic_like",
            "label_ko": "공황형 후보",
            "reasons": reasons,
        }

    return {
        "type": "hold",
        "label_ko": "보류",
        "reasons": reasons or ["뚜렷한 급락·공시 없음"],
    }
