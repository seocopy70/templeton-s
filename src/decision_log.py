"""
판단 기록 (Phase 6 초안)
Score + 의견 + 핵심 근거를 JSONL로 저장해 사후 검증에 사용한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# 프로젝트 루트/data/decisions.jsonl
ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "data" / "decisions.jsonl"


def log_decision(
    symbol: str,
    name: str,
    score_data: dict[str, Any],
    price: Optional[float] = None,
    extra: Optional[dict] = None,
) -> None:
    """한 줄 JSON으로 판단 기록. 실패해도 본 로직을 막지 않는다."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "name": name,
            "price": price,
            "total": score_data.get("total"),
            "opinion": score_data.get("opinion"),
            "components": score_data.get("components"),
            "pessimism_signal": (score_data.get("pessimism_inputs") or {}).get("signal"),
            "value_method": (score_data.get("value_inputs") or {}).get("method"),
            "quality_method": (score_data.get("quality_inputs") or {}).get("method"),
            "growth_method": (score_data.get("growth_inputs") or {}).get("method"),
        }
        if extra:
            record["extra"] = extra
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        # 로깅 실패는 무시 (투자 판단 흐름을 막지 않음)
        print(f"[decision_log] write failed: {e}")


def recent_decisions(limit: int = 50) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
