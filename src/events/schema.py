"""이벤트 스키마 (Phase 4.0)"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Optional


IMPORTANCE_ORDER = ("low", "medium", "high", "critical")


def importance_rank(level: str) -> int:
    try:
        return IMPORTANCE_ORDER.index(level)
    except ValueError:
        return 0


@dataclass
class Event:
    event_id: str
    source: str  # dart | news | manual
    symbol: str
    name: str
    ts: str
    title: str
    category: str = "other"
    importance: str = "low"
    sentiment: str = "neutral"
    value_impact: str = "unlikely"  # unlikely | possible | likely
    url: str = ""
    raw_summary: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Event":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        payload = {k: v for k, v in d.items() if k in known}
        return cls(**payload)
