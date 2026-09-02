"""
Point-in-Time Data Engine

특정 as_of 날짜에 이용 가능했던 일봉만 반환한다.
본 앱 실시간 공급기와 공유하지 않는다.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from kis_client import KISClient  # noqa: E402

# 메모리 캐시: symbol -> list[{date, close}] newest-first full history fetched
_BARS_CACHE: dict[str, list[dict[str, Any]]] = {}


def _parse_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def fetch_bars_chunked(
    client: KISClient,
    symbol: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """
    KIS 일봉을 기간 청크로 조회 후 병합.
    반환: 최신→과거, [{date, close}, ...]
    """
    token = client._get_token()
    url = (
        f"{client.base_url}"
        "/uapi/domestic-stock/v1/quotations/"
        "inquire-daily-itemchartprice"
    )
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": client.app_key,
        "appsecret": client.app_secret,
        "tr_id": "FHKST03010100",
        "custtype": "P",
    }

    # 약 100봉/요청 가정 → 달력 150일 단위
    all_rows: dict[str, float] = {}
    cursor_end = end
    min_start = start
    safety = 0
    while cursor_end >= min_start and safety < 40:
        safety += 1
        cursor_start = max(min_start, cursor_end - timedelta(days=150))
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": cursor_start.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": cursor_end.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        }
        resp = client._request_with_retry(url, headers=headers, params=params)
        client._raise_detail(resp)
        data = client._parse_json(resp, f"PIT bars({symbol})")
        if data.get("rt_cd") != "0":
            break
        rows = data.get("output2") or []
        if not rows:
            cursor_end = cursor_start - timedelta(days=1)
            continue
        for row in rows:
            raw = str(row.get("stck_bsop_date") or "")
            if len(raw) != 8:
                continue
            c = client._to_float(row.get("stck_clpr"))
            if c is None or c <= 0:
                continue
            d = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
            all_rows[d] = c
        # 다음 청크: 받은 가장 오래된 날짜 이전
        oldest = min(all_rows.keys()) if all_rows else None
        if oldest:
            cursor_end = _parse_date(oldest) - timedelta(days=1)
        else:
            cursor_end = cursor_start - timedelta(days=1)
        if cursor_start <= min_start:
            break

    bars = [
        {"date": d, "close": all_rows[d]}
        for d in sorted(all_rows.keys(), reverse=True)
    ]
    return bars


def load_bars(
    client: KISClient,
    symbol: str,
    start: str,
    end: str,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """start/end inclusive YYYY-MM-DD. Cache by symbol+range key loosely by symbol full pull."""
    cache_key = f"{symbol}:{start}:{end}"
    if use_cache and cache_key in _BARS_CACHE:
        return _BARS_CACHE[cache_key]
    bars = fetch_bars_chunked(
        client, symbol, _parse_date(start), _parse_date(end)
    )
    if use_cache:
        _BARS_CACHE[cache_key] = bars
    return bars


def bars_as_of(
    bars: list[dict[str, Any]],
    as_of: str,
) -> list[dict[str, Any]]:
    """as_of 당일 포함 이전 봉만 (최신→과거)."""
    return [b for b in bars if b["date"] <= as_of]


def bars_after(
    bars: list[dict[str, Any]],
    as_of: str,
) -> list[dict[str, Any]]:
    """as_of 이후 봉만. 평가용. 날짜 오름차순으로 반환."""
    future = [b for b in bars if b["date"] > as_of]
    return sorted(future, key=lambda x: x["date"])


def price_as_of(bars_upto: list[dict[str, Any]]) -> Optional[float]:
    if not bars_upto:
        return None
    return float(bars_upto[0]["close"])


def high_low_52w(bars_upto: list[dict[str, Any]], window: int = 252) -> tuple[Optional[float], Optional[float]]:
    window_bars = bars_upto[:window]
    if not window_bars:
        return None, None
    closes = [float(b["close"]) for b in window_bars]
    return max(closes), min(closes)


def change_rate_1d(bars_upto: list[dict[str, Any]]) -> Optional[float]:
    if len(bars_upto) < 2:
        return None
    c0 = float(bars_upto[0]["close"])
    c1 = float(bars_upto[1]["close"])
    if c1 <= 0:
        return None
    return round((c0 / c1 - 1.0) * 100, 2)


def closes_list(bars_upto: list[dict[str, Any]], n: int = 60) -> list[float]:
    return [float(b["close"]) for b in bars_upto[:n]]
