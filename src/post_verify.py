"""
Phase 6 — 판단 기록 사후 검증

기록 시점 가격 대비 이후 1주(~5거래일)·1개월(~20거래일) 수익률을 붙이고
의견별 평균 수익률·히트율을 요약한다.

원칙:
- 프로그램이 계산, AI 해석은 하지 않음 (숫자만)
- 자동매수/추천 문구 없음
- 데이터가 부족하면 None으로 두고 UI에서 "대기" 표시
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from decision_log import LOG_PATH, recent_decisions

# 거래일 기준 (대략)
TRADING_DAYS_1W = 5
TRADING_DAYS_1M = 20

# 의견 그룹
POSITIVE_OPINIONS = {"분할매수 관심", "적극적 관심"}
NEGATIVE_OPINIONS = {"매수 회피"}
NEUTRAL_OPINIONS = {"관망", "보유/관찰"}


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _find_forward_close(
    bars: list[dict[str, Any]],
    decision_date: str,
    trading_days: int,
) -> Optional[tuple[str, float]]:
    """
    decision_date 당일 또는 그 이전 가장 가까운 봉을 기준으로,
    그로부터 trading_days 개 이후 봉의 (date, close)를 반환.
    bars는 최신→과거 순.
    """
    if not bars or trading_days < 1:
        return None

    # 과거→최신 인덱스로 다루기 쉽게 뒤집지 않고, decision 위치 찾기
    # bars[0] = 최신
    idx_decision = None
    for i, b in enumerate(bars):
        if b["date"] <= decision_date:
            idx_decision = i
            break
    if idx_decision is None:
        # 모든 봉이 decision_date 이후 → 아직 시작 전
        return None

    # idx_decision 에서 trading_days 만큼 "미래"로 이동 = 인덱스 감소
    target_idx = idx_decision - trading_days
    if target_idx < 0:
        # 아직 해당 거래일만큼 지나지 않음
        return None

    b = bars[target_idx]
    return b["date"], float(b["close"])


def attach_forward_returns(
    records: list[dict],
    bars_by_symbol: dict[str, list[dict[str, Any]]],
) -> list[dict]:
    """
    각 record에 ret_1w, ret_1m, price_1w, price_1m, date_1w, date_1m 을 추가.
    bars_by_symbol: symbol -> get_daily_bars 결과
    """
    out: list[dict] = []
    for r in records:
        row = dict(r)
        symbol = str(r.get("symbol") or "")
        price = r.get("price")
        ts = _parse_ts(str(r.get("ts") or ""))
        bars = bars_by_symbol.get(symbol) or []

        row["ret_1w"] = None
        row["ret_1m"] = None
        row["price_1w"] = None
        row["price_1m"] = None
        row["date_1w"] = None
        row["date_1m"] = None
        row["verify_status"] = "no_price"

        if price is None or ts is None:
            out.append(row)
            continue

        try:
            base_price = float(price)
        except (TypeError, ValueError):
            out.append(row)
            continue
        if base_price <= 0:
            out.append(row)
            continue

        decision_date = _date_str(ts.astimezone(timezone.utc) if ts.tzinfo else ts)

        if not bars:
            row["verify_status"] = "no_bars"
            out.append(row)
            continue

        # 1주
        fwd_w = _find_forward_close(bars, decision_date, TRADING_DAYS_1W)
        if fwd_w:
            d, c = fwd_w
            row["date_1w"] = d
            row["price_1w"] = c
            row["ret_1w"] = round((c / base_price - 1.0) * 100, 2)

        # 1개월
        fwd_m = _find_forward_close(bars, decision_date, TRADING_DAYS_1M)
        if fwd_m:
            d, c = fwd_m
            row["date_1m"] = d
            row["price_1m"] = c
            row["ret_1m"] = round((c / base_price - 1.0) * 100, 2)

        if row["ret_1w"] is not None or row["ret_1m"] is not None:
            row["verify_status"] = "ok"
        else:
            row["verify_status"] = "waiting"  # 아직 기간 미경과

        out.append(row)
    return out


def summarize_by_opinion(verified: list[dict]) -> list[dict]:
    """
    의견별 건수·평균 1w/1m 수익률·히트율.
    히트 정의 (v0.1 단순):
      - 긍정 의견 + ret > 0 → hit
      - 부정 의견 + ret < 0 → hit
      - 그 외는 히트율 계산에서 제외(중립)
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in verified:
        op = r.get("opinion") or "—"
        groups[op].append(r)

    rows = []
    for opinion, items in sorted(groups.items(), key=lambda x: -len(x[1])):
        rets_w = [r["ret_1w"] for r in items if r.get("ret_1w") is not None]
        rets_m = [r["ret_1m"] for r in items if r.get("ret_1m") is not None]

        hits_w = misses_w = 0
        hits_m = misses_m = 0
        for r in items:
            op = r.get("opinion") or ""
            rw = r.get("ret_1w")
            rm = r.get("ret_1m")
            if op in POSITIVE_OPINIONS:
                if rw is not None:
                    if rw > 0:
                        hits_w += 1
                    else:
                        misses_w += 1
                if rm is not None:
                    if rm > 0:
                        hits_m += 1
                    else:
                        misses_m += 1
            elif op in NEGATIVE_OPINIONS:
                if rw is not None:
                    if rw < 0:
                        hits_w += 1
                    else:
                        misses_w += 1
                if rm is not None:
                    if rm < 0:
                        hits_m += 1
                    else:
                        misses_m += 1

        def _hit_rate(h, m):
            t = h + m
            if t == 0:
                return None
            return round(h / t * 100, 1)

        rows.append({
            "의견": opinion,
            "건수": len(items),
            "1주 평균(%)": round(sum(rets_w) / len(rets_w), 2) if rets_w else None,
            "1주 표본": len(rets_w),
            "1주 히트율(%)": _hit_rate(hits_w, misses_w),
            "1개월 평균(%)": round(sum(rets_m) / len(rets_m), 2) if rets_m else None,
            "1개월 표본": len(rets_m),
            "1개월 히트율(%)": _hit_rate(hits_m, misses_m),
        })
    return rows


def verified_table_rows(verified: list[dict]) -> list[dict]:
    """UI 테이블용 한글 컬럼."""
    rows = []
    for r in verified:
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

        def _ret_str(v):
            if v is None:
                return "—"
            sign = "+" if v > 0 else ""
            return f"{sign}{v:.2f}%"

        status = r.get("verify_status") or ""
        status_kr = {
            "ok": "검증됨",
            "waiting": "대기(기간 미경과)",
            "no_bars": "일봉 없음",
            "no_price": "가격 없음",
        }.get(status, status)

        rows.append({
            "시각": ts_disp,
            "종목": r.get("name") or r.get("symbol") or "—",
            "코드": r.get("symbol") or "—",
            "기록가격": price_str,
            "Score": f"{float(r['total']):.1f}" if r.get("total") is not None else "—",
            "의견": r.get("opinion") or "—",
            "시장모드": r.get("market_regime") or "—",
            "1주 수익": _ret_str(r.get("ret_1w")),
            "1개월 수익": _ret_str(r.get("ret_1m")),
            "상태": status_kr,
        })
    return rows


def load_and_verify(
    client: Any,
    limit: int = 50,
    symbol: Optional[str] = None,
) -> tuple[list[dict], list[dict]]:
    """
    판단 기록을 읽고 일봉을 조회해 선도 수익률을 붙인 뒤
    (verified_records, summary_by_opinion) 반환.
    client: KISClient 인스턴스 (get_daily_bars 필요)
    """
    records = recent_decisions(limit=limit, symbol=symbol)
    if not records:
        return [], []

    symbols = sorted({str(r.get("symbol")) for r in records if r.get("symbol")})
    bars_by_symbol: dict[str, list[dict]] = {}
    for sym in symbols:
        try:
            bars_by_symbol[sym] = client.get_daily_bars(sym, count=120)
        except Exception as e:
            print(f"[post_verify] daily bars failed {sym}: {e}")
            bars_by_symbol[sym] = []

    verified = attach_forward_returns(records, bars_by_symbol)
    summary = summarize_by_opinion(verified)
    return verified, summary
