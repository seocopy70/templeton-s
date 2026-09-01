"""
시장 모드: normal / watch / panic_zone
2~3일 관찰 후 확정 (하루만으로 panic_zone 확정하지 않음)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional, Sequence


# 임계값 (설계 문서 v0.1)
WATCH_DAY_PCT = -2.0
WATCH_DAY_SOFT = -1.5
WATCH_DOWN_RATIO = 2 / 3
CONFIRM_3D_PCT = -4.5
CONFIRM_2D_PCT = -5.5
EXTREME_DAY_PCT = -5.0
EXTREME_2D_PCT = -8.0


@dataclass
class RegimeResult:
    regime: str  # normal | watch | panic_zone
    label_ko: str
    reasons: list[str]
    bench_1d: Optional[float] = None
    bench_2d: Optional[float] = None
    bench_3d: Optional[float] = None
    down_ratio: Optional[float] = None
    extreme: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _returns_from_closes(closes: Sequence[float], days: int) -> Optional[float]:
    """closes: 최신→과거. days=1 → 1일 수익률(%)."""
    if not closes or len(closes) < days + 1:
        return None
    try:
        now = float(closes[0])
        past = float(closes[days])
        if past <= 0:
            return None
        return round((now / past - 1.0) * 100.0, 2)
    except (TypeError, ValueError, IndexError):
        return None


def detect_market_regime(
    benchmark_closes: Sequence[float],
    stock_day_changes: Sequence[Optional[float]],
    benchmark_day_change: Optional[float] = None,
) -> RegimeResult:
    """
    benchmark_closes: 벤치마크 일봉 종가 최신→과거
    stock_day_changes: 관심종목 당일 등락률(%) 목록
    benchmark_day_change: 있으면 1d에 우선 사용 (실시간 시세)
    """
    r1 = benchmark_day_change
    if r1 is None:
        r1 = _returns_from_closes(benchmark_closes, 1)
    r2 = _returns_from_closes(benchmark_closes, 2)
    r3 = _returns_from_closes(benchmark_closes, 3)

    changes = [c for c in stock_day_changes if c is not None]
    down_ratio = None
    if changes:
        down_ratio = sum(1 for c in changes if c < 0) / len(changes)

    reasons: list[str] = []
    extreme = False
    if r1 is not None and r1 <= EXTREME_DAY_PCT:
        extreme = True
        reasons.append(f"당일 벤치마크 {r1:+.2f}% (극단 구간 참고)")
    if r2 is not None and r2 <= EXTREME_2D_PCT:
        extreme = True
        reasons.append(f"2일 누적 {r2:+.2f}% (극단 구간 참고)")

    # 확정: 멀티데이
    confirm = False
    if r3 is not None and r3 <= CONFIRM_3D_PCT:
        confirm = True
        reasons.append(f"3거래일 누적 {r3:+.2f}% ≤ {CONFIRM_3D_PCT}%")
    if r2 is not None and r2 <= CONFIRM_2D_PCT:
        confirm = True
        reasons.append(f"2거래일 누적 {r2:+.2f}% ≤ {CONFIRM_2D_PCT}%")

    if confirm and down_ratio is not None and down_ratio < 0.5:
        # 확산 약하면 한 단계 완화
        reasons.append(f"관심종목 하락 비율 {down_ratio:.0%}로 확산 제한 → 확정 보류 검토")
        # 여전히 confirm 유지하되 사유에 남김 (설계: 가능하면 확산 유지)

    if confirm:
        label = "공포 구간 (관찰 확정)"
        if extreme:
            label = "공포 구간 · 역사적 급락 참고"
        return RegimeResult(
            regime="panic_zone",
            label_ko=label,
            reasons=reasons or ["멀티데이 하락 조건 충족"],
            bench_1d=r1,
            bench_2d=r2,
            bench_3d=r3,
            down_ratio=down_ratio,
            extreme=extreme,
        )

    # 주시
    watch = False
    if r1 is not None and r1 <= WATCH_DAY_PCT:
        watch = True
        reasons.append(f"당일 벤치마크 {r1:+.2f}% ≤ {WATCH_DAY_PCT}%")
    if (
        r1 is not None
        and r1 <= WATCH_DAY_SOFT
        and down_ratio is not None
        and down_ratio >= WATCH_DOWN_RATIO
    ):
        watch = True
        reasons.append(
            f"당일 {r1:+.2f}% + 관심종목 하락 {down_ratio:.0%} ≥ {WATCH_DOWN_RATIO:.0%}"
        )

    if watch:
        return RegimeResult(
            regime="watch",
            label_ko="시장 주시 (2~3일 관찰)",
            reasons=reasons or ["강한 하루 하락"],
            bench_1d=r1,
            bench_2d=r2,
            bench_3d=r3,
            down_ratio=down_ratio,
            extreme=extreme,
        )

    return RegimeResult(
        regime="normal",
        label_ko="정상",
        reasons=["멀티데이·당일 기준 미충족"],
        bench_1d=r1,
        bench_2d=r2,
        bench_3d=r3,
        down_ratio=down_ratio,
        extreme=False,
    )
