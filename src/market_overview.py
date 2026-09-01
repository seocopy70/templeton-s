"""
주요 시장 요약 (한국 · 미국 · 일본)
- 한국: KIS 업종지수 API (KOSPI/KOSDAQ)
- 미국·일본: Yahoo Finance chart API (키 불필요, 실패 시 ETF 대리)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import requests

from kis_client import KISClient

logger = logging.getLogger(__name__)

# KIS 업종 코드
KIS_INDEX = {
    "KOSPI": "0001",
    "KOSDAQ": "1001",
}

# Yahoo 심볼
YAHOO = {
    "S&P500": "^GSPC",
    "NASDAQ": "^IXIC",
    "Nikkei225": "^N225",
}

# 국내 ETF 대리 (Yahoo 실패 시)
ETF_PROXY = {
    "S&P500": "360750",  # TIGER 미국S&P500
}


def _yahoo_quote_and_closes(symbol: str, days: int = 30) -> Optional[dict[str, Any]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "3mo"}
    headers = {"User-Agent": "Mozilla/5.0 TempletonS/1.0"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return None
        r0 = result[0]
        meta = r0.get("meta") or {}
        indicators = (r0.get("indicators") or {}).get("quote") or [{}]
        closes_raw = indicators[0].get("close") or []
        timestamps = r0.get("timestamp") or []

        closes = []
        for c in closes_raw:
            if c is not None:
                try:
                    closes.append(float(c))
                except (TypeError, ValueError):
                    pass
        # 최신 → 과거
        closes = list(reversed(closes))[-days:]
        closes = list(reversed(closes))  # 차트용 오래된→최신으로 다시
        # 위 정리: 차트는 오래된→최신이 편함
        ordered = []
        for c in closes_raw:
            if c is not None:
                try:
                    ordered.append(float(c))
                except (TypeError, ValueError):
                    pass
        ordered = ordered[-days:]

        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None and ordered:
            price = ordered[-1]
        change_rate = None
        if price is not None and prev:
            try:
                change_rate = (float(price) / float(prev) - 1.0) * 100.0
            except (TypeError, ValueError, ZeroDivisionError):
                change_rate = None
        if change_rate is None and len(ordered) >= 2 and ordered[-2]:
            change_rate = (ordered[-1] / ordered[-2] - 1.0) * 100.0

        return {
            "price": float(price) if price is not None else None,
            "change_rate": round(change_rate, 2) if change_rate is not None else None,
            "closes": ordered,
            "source": "yahoo",
        }
    except Exception as e:
        logger.warning("Yahoo %s 실패: %s", symbol, e)
        return None


def _kis_index(client: KISClient, index_code: str) -> Optional[dict[str, Any]]:
    """국내 업종 현재가. TR: FHPUP02100000 계열 — 환경에 따라 경로 상이할 수 있음."""
    token = client._get_token()
    # 현재가
    url = f"{client.base_url}/uapi/domestic-stock/v1/quotations/inquire-index-price"
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": client.app_key,
        "appsecret": client.app_secret,
        "tr_id": "FHPUP02100000",
        "custtype": "P",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": index_code,
    }
    try:
        resp = client._request_with_retry(url, headers=headers, params=params)
        data = client._parse_json(resp, f"지수({index_code})")
        if data.get("rt_cd") != "0":
            logger.warning("KIS index rt_cd=%s %s", data.get("rt_cd"), data.get("msg1"))
            return None
        out = data.get("output") or {}
        if isinstance(out, list):
            out = out[0] if out else {}
        price = client._to_float(out.get("bstp_nmix_prpr") or out.get("stck_prpr"))
        change_rate = client._to_float(out.get("bstp_nmix_prdy_ctrt") or out.get("prdy_ctrt"))
        return {
            "price": price,
            "change_rate": change_rate,
            "closes": [],
            "source": "kis",
        }
    except Exception as e:
        logger.warning("KIS index %s 실패: %s", index_code, e)
        return None


def _kis_index_closes(client: KISClient, index_code: str, count: int = 30) -> list[float]:
    from datetime import datetime, timedelta

    token = client._get_token()
    url = f"{client.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice"
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": client.app_key,
        "appsecret": client.app_secret,
        "tr_id": "FHKUP03500100",
        "custtype": "P",
    }
    end = datetime.now().date()
    start = end - timedelta(days=90)
    params = {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": index_code,
        "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",
    }
    try:
        resp = client._request_with_retry(url, headers=headers, params=params)
        data = client._parse_json(resp, f"지수단일봉({index_code})")
        if data.get("rt_cd") != "0":
            return []
        rows = data.get("output2") or data.get("output") or []
        if isinstance(rows, dict):
            rows = [rows]

        def _d(row):
            return str(row.get("stck_bsop_date") or row.get("date") or "")

        rows = sorted(rows, key=_d)  # 오래된 → 최신
        closes = []
        for row in rows:
            c = client._to_float(
                row.get("bstp_nmix_prpr") or row.get("stck_clpr") or row.get("close")
            )
            if c is not None and c > 0:
                closes.append(c)
        return closes[-count:]
    except Exception as e:
        logger.warning("KIS index closes %s: %s", index_code, e)
        return []


def _etf_fallback(client: KISClient, code: str) -> Optional[dict[str, Any]]:
    try:
        p = client.get_current_price(code)
        closes = client.get_daily_closes(code, 30)
        # closes는 최신→과거 → 차트용 뒤집기
        ordered = list(reversed(closes)) if closes else []
        return {
            "price": p.get("current_price"),
            "change_rate": p.get("change_rate"),
            "closes": ordered,
            "source": f"etf:{code}",
        }
    except Exception as e:
        logger.warning("ETF fallback %s: %s", code, e)
        return None


def fetch_market_overview(client: Optional[KISClient] = None) -> list[dict[str, Any]]:
    """
    표시용 리스트:
    [{key, name, region, price, change_rate, closes, source, ok}]
    """
    if client is None:
        client = KISClient()

    items: list[dict[str, Any]] = []

    # 한국
    for name, code in KIS_INDEX.items():
        q = _kis_index(client, code)
        closes = _kis_index_closes(client, code, 30) if q else []
        if q and (q.get("price") is not None or closes):
            if closes:
                q["closes"] = closes
            items.append({
                "key": name,
                "name": name,
                "region": "KR",
                "price": q.get("price"),
                "change_rate": q.get("change_rate"),
                "closes": q.get("closes") or [],
                "source": q.get("source"),
                "ok": True,
            })
        else:
            # KODEX200 대리 for KOSPI only
            if name == "KOSPI":
                fb = _etf_fallback(client, "069500")
                if fb:
                    items.append({
                        "key": name,
                        "name": "KOSPI(대용 KODEX200)",
                        "region": "KR",
                        **{k: fb[k] for k in ("price", "change_rate", "closes", "source")},
                        "ok": True,
                    })
                    continue
            items.append({
                "key": name,
                "name": name,
                "region": "KR",
                "price": None,
                "change_rate": None,
                "closes": [],
                "source": None,
                "ok": False,
            })

    # 미국 · 일본 (Yahoo)
    for name, ysym in YAHOO.items():
        y = _yahoo_quote_and_closes(ysym, 30)
        if y and y.get("price") is not None:
            items.append({
                "key": name,
                "name": name,
                "region": "US" if "Nikkei" not in name else "JP",
                "price": y.get("price"),
                "change_rate": y.get("change_rate"),
                "closes": y.get("closes") or [],
                "source": y.get("source"),
                "ok": True,
            })
        elif name == "S&P500":
            fb = _etf_fallback(client, ETF_PROXY["S&P500"])
            if fb:
                items.append({
                    "key": name,
                    "name": "S&P500(대용 ETF)",
                    "region": "US",
                    **{k: fb[k] for k in ("price", "change_rate", "closes", "source")},
                    "ok": True,
                })
            else:
                items.append({
                    "key": name,
                    "name": name,
                    "region": "US",
                    "price": None,
                    "change_rate": None,
                    "closes": [],
                    "source": None,
                    "ok": False,
                })
        else:
            items.append({
                "key": name,
                "name": name,
                "region": "JP" if "Nikkei" in name else "US",
                "price": None,
                "change_rate": None,
                "closes": [],
                "source": None,
                "ok": False,
            })

    return items
