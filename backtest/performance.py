"""
Performance Analyzer — 의견·Score 구간별 요약 (L1/L2)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from .forward_return import HORIZONS


def _avg(xs: list[float]) -> Optional[float]:
    if not xs:
        return None
    return round(sum(xs) / len(xs), 2)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """records: decision + forward 가 합쳐진 리스트."""
    by_opinion: dict[str, list] = defaultdict(list)
    by_regime: dict[str, list] = defaultdict(list)
    score_buckets: dict[str, list] = defaultdict(list)

    for r in records:
        by_opinion[r.get("opinion") or "—"].append(r)
        by_regime[r.get("market_regime") or "—"].append(r)
        total = r.get("total")
        try:
            t = float(total)
        except (TypeError, ValueError):
            bucket = "unknown"
        else:
            if t < 40:
                bucket = "0-39"
            elif t < 60:
                bucket = "40-59"
            elif t < 75:
                bucket = "60-74"
            elif t < 85:
                bucket = "75-84"
            else:
                bucket = "85-100"
        score_buckets[bucket].append(r)

    def group_stats(groups: dict[str, list]) -> list[dict]:
        rows = []
        for key, items in sorted(groups.items(), key=lambda x: -len(x[1])):
            row: dict[str, Any] = {"key": key, "n": len(items)}
            for h in HORIZONS:
                rets = []
                excesses = []
                for it in items:
                    hz = (it.get("forward") or {}).get("horizons") or {}
                    cell = hz.get(str(h)) or {}
                    if cell.get("ret") is not None:
                        rets.append(float(cell["ret"]))
                    if cell.get("excess") is not None:
                        excesses.append(float(cell["excess"]))
                row[f"ret_{h}"] = _avg(rets)
                row[f"excess_{h}"] = _avg(excesses)
                row[f"n_{h}"] = len(rets)
            rows.append(row)
        return rows

    return {
        "n_total": len(records),
        "by_opinion": group_stats(by_opinion),
        "by_regime": group_stats(by_regime),
        "by_score_bucket": group_stats(score_buckets),
    }


def print_summary(summary: dict[str, Any]) -> None:
    print(f"\n=== Backtest summary (n={summary.get('n_total', 0)}) ===")
    for title, key in [
        ("Opinion (L2)", "by_opinion"),
        ("Regime", "by_regime"),
        ("Score bucket (L1)", "by_score_bucket"),
    ]:
        print(f"\n-- {title} --")
        rows = summary.get(key) or []
        if not rows:
            print("  (empty)")
            continue
        for r in rows:
            parts = [f"{r['key']:16s} n={r['n']:3d}"]
            for h in (5, 20, 60):
                ret = r.get(f"ret_{h}")
                ex = r.get(f"excess_{h}")
                if ret is None:
                    parts.append(f"+{h}d: —")
                else:
                    parts.append(
                        f"+{h}d: {ret:+.1f}% (xs {ex:+.1f}%)"
                        if ex is not None
                        else f"+{h}d: {ret:+.1f}%"
                    )
            print("  " + " | ".join(parts))
