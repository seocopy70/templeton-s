"""
Historical Snapshot — as_of 시점 입력 묶음 + 판단 결과 저장용
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

ENGINE_VERSION = "score_v0.5"


def build_score_input(
    *,
    symbol: str,
    name: str,
    as_of: str,
    price: float,
    change_rate: Optional[float],
    high_52w: Optional[float],
    low_52w: Optional[float],
    closes: list[float],
    volatility_annual: Optional[float],
    momentum_20d: Optional[float],
) -> dict[str, Any]:
    """Score Engine에 넣을 PIT 입력. 재무는 v0.1에서 비움 → 중립 폴백."""
    drop = None
    if high_52w and price and high_52w > 0:
        drop = round((high_52w - price) / high_52w * 100, 2)

    return {
        "symbol": symbol,
        "name": name,
        "current_price": price,
        "change_rate": change_rate,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "drop_from_52w_high": drop,
        "closes": closes,
        "volatility_annual": volatility_annual,
        "momentum_20d": momentum_20d,
        "candle_days": len(closes),
        # 재무 PIT 미구현
        "per": None,
        "pbr": None,
        "roe": None,
        "debt_ratio": None,
        "revenue_growth_3y": None,
        "op_income_growth_3y": None,
    }


def make_snapshot_id(symbol: str, as_of: str, engine_version: str) -> str:
    raw = f"{symbol}|{as_of}|{engine_version}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def pack_record(
    *,
    symbol: str,
    name: str,
    as_of: str,
    score_input: dict[str, Any],
    score_data: dict[str, Any],
    market_regime: str,
    panic_class: dict[str, Any],
    opportunity_rank: Optional[int],
    opportunity_score: Optional[float],
    bench_change: Optional[float],
) -> dict[str, Any]:
    sid = make_snapshot_id(symbol, as_of, ENGINE_VERSION)
    return {
        "snapshot_id": sid,
        "engine_version": ENGINE_VERSION,
        "as_of": as_of,
        "symbol": symbol,
        "name": name,
        "price": score_input.get("current_price"),
        "change_rate": score_input.get("change_rate"),
        "total": score_data.get("total"),
        "opinion": score_data.get("opinion"),
        "components": score_data.get("components"),
        "market_regime": market_regime,
        "panic_type": (panic_class or {}).get("type"),
        "panic_label": (panic_class or {}).get("label_ko"),
        "opportunity_rank": opportunity_rank,
        "opportunity_score": opportunity_score,
        "bench_change": bench_change,
        "data_notes": [
            "price_pit_ok",
            "financials_unavailable_v0.1",
            "events_empty_unless_injected",
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def dump_jsonl(path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
