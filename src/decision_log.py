"""
판단 기록 (Phase 4.5+ / Phase 6 연동)
Score + 의견 + event_ids + regime/rank 를 JSONL로 저장.
동일 종목의 중복 기록은 억제한다.
사후 검증(1주/1개월 수익)은 post_verify.py 가 담당.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "data" / "decisions.jsonl"

# 같은 종목 재기록 최소 간격 (시간)
MIN_HOURS_BETWEEN_LOGS = 6
# Score 변화가 이 이상이면 간격과 무관하게 기록
SCORE_DELTA_FORCE = 3.0


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _latest_for_symbol(symbol: str) -> Optional[dict]:
    if not LOG_PATH.exists():
        return None
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("symbol")) == str(symbol):
            return row
    return None


def should_log_decision(
    symbol: str,
    score_data: dict[str, Any],
    event_trigger: Optional[str] = None,
    force: bool = False,
) -> bool:
    """
    True일 때만 파일에 기록.
    - force / 이벤트 트리거(none 아님) → 기록
    - 의견 변경 → 기록
    - Score |Δ| >= SCORE_DELTA_FORCE → 기록
    - 마지막 기록 후 MIN_HOURS_BETWEEN_LOGS 미만이고 위 조건 없으면 스킵
    """
    if force:
        return True
    trigger = event_trigger or "none"
    if trigger and trigger != "none":
        return True

    prev = _latest_for_symbol(symbol)
    if prev is None:
        return True

    new_opinion = score_data.get("opinion")
    old_opinion = prev.get("opinion")
    if new_opinion and old_opinion and new_opinion != old_opinion:
        return True

    try:
        new_total = float(score_data.get("total") or 0)
        old_total = float(prev.get("total") or 0)
        if abs(new_total - old_total) >= SCORE_DELTA_FORCE:
            return True
    except (TypeError, ValueError):
        pass

    prev_ts = _parse_ts(str(prev.get("ts") or ""))
    if prev_ts is None:
        return True
    now = datetime.now(timezone.utc)
    if prev_ts.tzinfo is None:
        prev_ts = prev_ts.replace(tzinfo=timezone.utc)
    if now - prev_ts >= timedelta(hours=MIN_HOURS_BETWEEN_LOGS):
        return True
    return False


def log_decision(
    symbol: str,
    name: str,
    score_data: dict[str, Any],
    price: Optional[float] = None,
    extra: Optional[dict] = None,
    event_ids: Optional[list[str]] = None,
    event_trigger: Optional[str] = None,
    force: bool = False,
    market_regime: Optional[str] = None,
    panic_type: Optional[str] = None,
    opportunity_rank: Optional[int] = None,
    opportunity_score: Optional[float] = None,
) -> bool:
    """
    조건에 맞을 때만 기록. 기록했으면 True, 스킵이면 False.
    실패해도 본 로직을 막지 않는다.
    """
    try:
        if not should_log_decision(
            symbol, score_data, event_trigger=event_trigger, force=force
        ):
            return False

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
            "event_ids": list(event_ids) if event_ids else [],
            "event_trigger": event_trigger or "none",
            "market_regime": market_regime or "normal",
            "panic_type": panic_type or "none",
            "opportunity_rank": opportunity_rank,
            "opportunity_score": opportunity_score,
        }
        if extra:
            record["extra"] = extra
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(f"[decision_log] write failed: {e}")
        return False


def recent_decisions(
    limit: int = 50,
    symbol: Optional[str] = None,
) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []

    out: list[dict] = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if symbol and str(row.get("symbol")) != str(symbol):
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def decisions_as_table_rows(records: list[dict]) -> list[dict]:
    rows = []
    for r in records:
        ts = r.get("ts") or ""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts_disp = dt.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception:
            ts_disp = ts[:16] if ts else "—"

        price = r.get("price")
        try:
            price_str = f"{float(price):,.0f}" if price is not None else "—"
        except (TypeError, ValueError):
            price_str = "—"

        total = r.get("total")
        total_str = f"{float(total):.1f}" if total is not None else "—"

        eids = r.get("event_ids") or []
        if isinstance(eids, list):
            eid_str = ", ".join(str(x) for x in eids[:3])
            if len(eids) > 3:
                eid_str += f" +{len(eids) - 3}"
        else:
            eid_str = "—"
        if not eid_str:
            eid_str = "—"

        rows.append({
            "시각": ts_disp,
            "종목": r.get("name") or r.get("symbol") or "—",
            "코드": r.get("symbol") or "—",
            "가격": price_str,
            "Score": total_str,
            "의견": r.get("opinion") or "—",
            "비관신호": r.get("pessimism_signal") or "—",
            "트리거": r.get("event_trigger") or "—",
            "시장모드": r.get("market_regime") or "—",
            "공황분류": r.get("panic_type") or "—",
            "기회순위": r.get("opportunity_rank") if r.get("opportunity_rank") is not None else "—",
            "event_ids": eid_str,
        })
    return rows
