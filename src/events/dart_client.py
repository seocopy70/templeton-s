"""
DART Open API 클라이언트 (Phase 4.1 골격)

사용 전:
  1) https://opendart.fss.or.kr 에서 API 키 발급
  2) config/.env 에 DART_API_KEY=... 설정

키 없으면 빈 목록을 반환하고 앱은 정상 동작(공시 섹션만 비어 있음).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional
from xml.etree import ElementTree as ET

import requests

from events.classifier import classify_disclosure_title
from events.schema import Event

logger = logging.getLogger(__name__)

DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"

# 종목코드(6자리) → DART 고유번호(8자리). 필요 시 확장.
# 공식 corpCode.xml 로 갱신 가능.
CORP_CODES: dict[str, str] = {
    "005930": "00126380",  # 삼성전자
    "005380": "00164742",  # 현대자동차
    "105560": "00164779",  # KB금융
}


class DartClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DART_API_KEY", "")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def get_recent_disclosures(
        self,
        symbol: str,
        name: str = "",
        days: int = 30,
        max_count: int = 10,
    ) -> list[Event]:
        if not self.enabled:
            logger.info("DART_API_KEY 없음 — 공시 조회 스킵")
            return []

        corp = CORP_CODES.get(symbol)
        if not corp:
            logger.info("DART corp_code 미등록 종목: %s", symbol)
            return []

        end = datetime.now().date()
        begin = end - timedelta(days=days)
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp,
            "bgn_de": begin.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_count": min(max_count, 100),
        }
        try:
            resp = requests.get(DART_LIST_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("DART 조회 실패 %s: %s", symbol, e)
            return []

        if str(data.get("status")) not in ("000", "013"):  # 013 = 데이터 없음
            logger.warning("DART status=%s msg=%s", data.get("status"), data.get("message"))
            return []

        events: list[Event] = []
        for row in data.get("list") or []:
            title = row.get("report_nm") or ""
            cat, imp, sent, impact = classify_disclosure_title(title)
            rcept = row.get("rcept_no") or ""
            events.append(
                Event(
                    event_id=f"dart-{rcept}" if rcept else f"dart-{symbol}-{len(events)}",
                    source="dart",
                    symbol=symbol,
                    name=name or symbol,
                    ts=str(row.get("rcept_dt") or ""),
                    title=title,
                    category=cat,
                    importance=imp,
                    sentiment=sent,
                    value_impact=impact,
                    url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}" if rcept else "",
                    raw_summary=title,
                    extra={"corp_code": corp, "rcept_no": rcept},
                )
            )
            if len(events) >= max_count:
                break
        return events
