"""가격 변화 기반 이벤트 재조회 트리거 (Phase 4.4 초안)"""
from __future__ import annotations

from typing import Any, Optional


def should_refetch_events(
    change_rate: Optional[float],
    market_change_rate: Optional[float] = None,
    abs_move_threshold: float = 3.0,
    relative_threshold: float = 2.0,
) -> bool:
    """
    True이면 공시/뉴스 재조회 + AI 재분석을 권장.
    - |종목 등락| >= abs_move_threshold
    - 또는 시장 대비 추가 하락(상대) >= relative_threshold
    """
    if change_rate is None:
        return False
    if abs(change_rate) >= abs_move_threshold:
        return True
    if market_change_rate is not None:
        relative = market_change_rate - change_rate  # 양수 = 시장보다 더 하락
        if relative >= relative_threshold:
            return True
    return False


def trigger_reason(
    change_rate: Optional[float],
    market_change_rate: Optional[float] = None,
) -> str:
    if change_rate is None:
        return "no_price"
    if abs(change_rate) >= 3.0:
        return f"abs_move:{change_rate:+.2f}%"
    if market_change_rate is not None:
        rel = market_change_rate - change_rate
        if rel >= 2.0:
            return f"relative_drop:{rel:+.2f}%p"
    return "none"
