"""규칙 기반 공시/뉴스 제목 분류 (Phase 4.2 초안 — LLM 없이 동작)"""
from __future__ import annotations

from typing import Tuple

# (키워드 부분문자열, category, importance, sentiment, value_impact)
_RULES: list[tuple[str, str, str, str, str]] = [
    # critical
    ("횡령", "risk", "critical", "critical_negative", "likely"),
    ("배임", "risk", "critical", "critical_negative", "likely"),
    ("회계처리", "risk", "critical", "critical_negative", "likely"),
    ("감사의견", "risk", "critical", "critical_negative", "likely"),
    ("상장폐지", "risk", "critical", "critical_negative", "likely"),
    ("거래정지", "risk", "critical", "critical_negative", "likely"),
    # high — 실적/자본
    ("잠정실적", "earnings", "high", "neutral", "possible"),
    ("영업(잠정)실적", "earnings", "high", "neutral", "possible"),
    ("실적발표", "earnings", "high", "neutral", "possible"),
    ("유상증자", "capital", "high", "negative", "likely"),
    ("전환사채", "capital", "high", "negative", "possible"),
    ("CB발행", "capital", "high", "negative", "possible"),
    ("공급계약", "contract", "high", "positive", "possible"),
    ("단일판매", "contract", "high", "positive", "possible"),
    # medium
    ("자사주", "treasury", "medium", "positive", "possible"),
    ("배당", "dividend", "medium", "positive", "possible"),
    ("최대주주", "governance", "medium", "neutral", "possible"),
    ("대표이사", "governance", "medium", "neutral", "possible"),
    ("소송", "risk", "medium", "negative", "possible"),
    ("특허", "other", "medium", "positive", "possible"),
]


def classify_disclosure_title(title: str) -> Tuple[str, str, str, str]:
    """
    Returns: (category, importance, sentiment, value_impact)
    제목 키워드 매칭. 매칭 없으면 other/low/neutral/unlikely.
    """
    t = (title or "").replace(" ", "")
    for key, cat, imp, sent, impact in _RULES:
        if key.replace(" ", "") in t:
            return cat, imp, sent, impact
    return "other", "low", "neutral", "unlikely"
