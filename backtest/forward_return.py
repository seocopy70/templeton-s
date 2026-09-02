"""
Forward Performance Engine — 판단 이후 성과만 계산 (판단 입력에 사용 금지)
"""
from __future__ import annotations

from typing import Any, Optional

# 프로토콜 확정 구간
HORIZONS = (5, 20, 60, 120, 252)


def _ret(base: float, future: float) -> Optional[float]:
    if base is None or base <= 0 or future is None or future <= 0:
        return None
    return round((future / base - 1.0) * 100, 2)


def forward_metrics(
    *,
    base_price: float,
    future_bars_asc: list[dict[str, Any]],
    bench_base: Optional[float],
    bench_future_asc: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    future_bars_asc: as_of 이후 봉, 날짜 오름차순
    """
    out: dict[str, Any] = {"horizons": {}}
    if not base_price or base_price <= 0:
        return out

    for h in HORIZONS:
        if len(future_bars_asc) < h:
            out["horizons"][str(h)] = {
                "ret": None,
                "bench_ret": None,
                "excess": None,
                "date": None,
            }
            continue
        fb = future_bars_asc[h - 1]
        ret = _ret(base_price, float(fb["close"]))
        bench_ret = None
        excess = None
        if bench_base and bench_base > 0 and len(bench_future_asc) >= h:
            bb = bench_future_asc[h - 1]
            bench_ret = _ret(bench_base, float(bb["close"]))
            if ret is not None and bench_ret is not None:
                excess = round(ret - bench_ret, 2)
        out["horizons"][str(h)] = {
            "ret": ret,
            "bench_ret": bench_ret,
            "excess": excess,
            "date": fb.get("date"),
        }

    # 단순 MDD: 구간 내 고점 대비 최대 낙폭 (가격 시계열)
    if future_bars_asc:
        peak = base_price
        max_dd = 0.0
        for b in future_bars_asc[:252]:
            c = float(b["close"])
            if c > peak:
                peak = c
            dd = (c / peak - 1.0) * 100
            if dd < max_dd:
                max_dd = dd
        out["mdd_252"] = round(max_dd, 2)
    else:
        out["mdd_252"] = None

    # 비용 자리만 예약
    out["cost"] = {
        "transaction": 0.0,
        "tax": 0.0,
        "slippage": 0.0,
        "net_adjust": 0.0,
    }
    return out
