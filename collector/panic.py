"""Deterministic Panic Watch state derived from the same market snapshot."""
from __future__ import annotations
from typing import Any


def evaluate(stock: dict[str, Any], market: dict[str, Any] | None, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    stock_change = stock.get("change_rate")
    market_change = market.get("change_rate") if market else None
    relative = None
    if stock_change is not None and market_change is not None:
        relative = round(float(market_change) - float(stock_change), 2)

    if market_change is not None and float(market_change) <= -5:
        status = "PANIC"
    elif (stock_change is not None and float(stock_change) <= -5) or (relative is not None and relative >= 4):
        status = "WATCH"
    elif market_change is not None and float(market_change) <= -2:
        status = "WATCH"
    else:
        status = "NORMAL"

    reason = f"stock={stock_change}, market={market_change}, relative_drop={relative}"
    return {
        "status": status,
        "reason": reason,
        "stock_change": stock_change,
        "market_change": market_change,
        "relative_drop": relative,
        "previous_status": (previous or {}).get("status"),
    }
