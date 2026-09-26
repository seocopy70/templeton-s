"""Provider-agnostic AI judgment adapter.

Production default: Groq + Llama 3.3 70B.  The collector only depends on
AIProvider, so another provider can be added without changing snapshot logic.
"""
from __future__ import annotations

import os
from typing import Any

PROMPT_VERSION = "snapshot-ai-v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _fallback(score: dict[str, Any], name: str) -> dict[str, Any]:
    c = score.get("components", {})
    positives = []
    negatives = []
    if c.get("value", 50) >= 60: positives.append("밸류에이션 매력")
    if c.get("pessimism", 50) >= 65: positives.append("시장 비관 신호")
    if c.get("quality", 50) >= 65: positives.append("기업 질 양호")
    if c.get("growth", 50) >= 60: positives.append("성장 지표 양호")
    if c.get("risk", 50) >= 65: negatives.append("변동성 부담")
    if c.get("quality", 50) < 40: negatives.append("기업 질 우려")
    if c.get("growth", 50) < 40: negatives.append("성장 둔화")
    return {
        "comment": f"{name} 종합점수 {score.get('total', 0):.1f}. 주요 지표를 함께 확인해야 합니다.",
        "positives": positives or ["뚜렷한 긍정 요인 없음"],
        "negatives": negatives or ["뚜렷한 부정 요인 없음"],
        "counter_argument": "현재 지표만으로 구조적 변화와 일시적 가격 변동을 구분할 수 없습니다.",
        "source": "rule_based",
    }


class AIProvider:
    name = "none"
    model = "none"
    version = "v1"

    def judge(self, *, name: str, code: str, score: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class GroqProvider(AIProvider):
    name = "groq"
    version = "v1"

    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        self._client = None
        if self.api_key:
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
            except Exception:
                self._client = None

    def judge(self, *, name: str, code: str, score: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if not self._client:
            return _fallback(score, name)

        c = score.get("components", {})
        prompt = f"""당신은 Templeton S의 보조 판단 엔진입니다.
과도한 확신을 피하고 숫자와 반대 근거를 함께 설명하세요.
종목: {name} ({code})
총점: {score.get('total')}
세부: {c}
시장/매크로 컨텍스트: {context}
반드시 다음 형식으로 한국어로 답하세요.
COMMENT: 2~3문장
POSITIVE: 긍정 요인 1~2개
NEGATIVE: 부정 요인 1~2개
COUNTER: 반대 근거 1~2문장
"""
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            raw = response.choices[0].message.content or ""
            parsed = self._parse(raw, score, name)
            parsed["_raw_text"] = raw
            parsed["_provider"] = self.name
            parsed["_model"] = getattr(response, "model", None) or self.model
            return parsed
        except Exception:
            return _fallback(score, name)

    @staticmethod
    def _parse(raw: str, score: dict[str, Any], name: str) -> dict[str, Any]:
        section = None
        comment = ""
        positives: list[str] = []
        negatives: list[str] = []
        counter = ""
        for line in raw.splitlines():
            line = line.strip()
            if not line: continue
            u = line.upper()
            if u.startswith("COMMENT:"):
                section = "comment"; comment = line.split(":", 1)[1].strip(); continue
            if u.startswith("POSITIVE:") or u == "POSITIVE:":
                section = "positive"; continue
            if u.startswith("NEGATIVE:") or u == "NEGATIVE:":
                section = "negative"; continue
            if u.startswith("COUNTER:"):
                section = "counter"; counter = line.split(":", 1)[1].strip(); continue
            clean = line.lstrip("-•* ").strip()
            if section == "positive": positives.append(clean)
            elif section == "negative": negatives.append(clean)
            elif section == "counter": counter = (counter + " " + clean).strip()
        if not comment and not positives and not negatives:
            return _fallback(score, name)
        return {
            "comment": comment or raw[:300],
            "positives": positives[:3] or ["뚜렷한 긍정 요인 없음"],
            "negatives": negatives[:3] or ["뚜렷한 부정 요인 없음"],
            "counter_argument": counter or "현재 정보만으로 판단을 확정할 수 없습니다.",
            "source": "groq",
        }


def get_provider() -> AIProvider:
    provider = os.getenv("AI_PROVIDER", "groq").strip().lower()
    if provider == "groq":
        return GroqProvider()
    raise ValueError(f"Unsupported AI_PROVIDER: {provider}")
