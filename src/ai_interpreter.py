# src/ai_interpreter.py
"""
템플턴S - AI 해석 레이어 (Groq 기반)
숫자에 의미 부여: "왜 이 점수인가?"를 자연어로 설명

컴포넌트 키는 score_engine과 동일하게 소문자 사용:
  value, price, pessimism, quality, growth, risk
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# Groq는 선택 (없어도 규칙 기반으로 동작)
try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False
    Groq = None  # noqa


def _get_comp(components: Dict, key: str, default: float = 50.0) -> float:
    """소문자/대문자 키 모두 허용 (하위 호환)"""
    if key in components:
        return float(components[key])
    title = key.title() if key != "pessimism" else "Pessimism"
    if title in components:
        return float(components[title])
    # 흔한 변형
    for k, v in components.items():
        if k.lower() == key.lower():
            return float(v)
    return default


# ── 규칙 기반 해석 (폴백) ────────────────────────
def _build_fallback_comment(
    name: str,
    score_data: Dict,
    opinion: str,
) -> Dict:
    components = score_data.get("components", {})
    total = score_data.get("total", 0)

    value = _get_comp(components, "value")
    price = _get_comp(components, "price")
    pessimism = _get_comp(components, "pessimism")
    quality = _get_comp(components, "quality")
    risk = _get_comp(components, "risk")
    growth = _get_comp(components, "growth")

    positives = []
    negatives = []

    if value >= 60:
        positives.append(f"밸류에이션 매력 (Value {value:.0f})")
    elif value < 40:
        negatives.append(f"밸류에이션 부담 (Value {value:.0f})")

    if pessimism >= 65:
        positives.append(f"시장 비관 과도 (Pessimism {pessimism:.0f})")
    elif pessimism < 35:
        negatives.append(f"시장 과열 양상 (Pessimism {pessimism:.0f})")

    if quality >= 65:
        positives.append(f"기업 펀더멘털 양호 (Quality {quality:.0f})")
    elif quality < 40:
        negatives.append(f"기업 질 우려 (Quality {quality:.0f})")

    if risk <= 35:
        positives.append(f"변동성 안정 (Risk {risk:.0f})")
    elif risk >= 65:
        negatives.append(f"변동성 확대 (Risk {risk:.0f})")

    if growth >= 60:
        positives.append(f"성장 모멘텀 (Growth {growth:.0f})")
    elif growth < 40:
        negatives.append(f"성장 둔화 (Growth {growth:.0f})")

    if not positives and not negatives:
        comment = f"{name}은(는) 현재 주요 지표가 중립권에 위치해 관망이 필요한 상황입니다."
    else:
        pos_text = ", ".join(positives) if positives else "뚜렷한 긍정 요인 없음"
        neg_text = ", ".join(negatives) if negatives else "뚜렷한 부정 요인 없음"
        comment = (
            f"{name}의 종합 점수 {total:.1f}점은 "
            f"긍정 요인({pos_text})과 "
            f"부정 요인({neg_text})이 혼재된 결과입니다."
        )

    counter_argument = _build_counter_argument(name, components)

    return {
        "comment": comment,
        "positives": positives or ["뚜렷한 긍정 요인 없음"],
        "negatives": negatives or ["뚜렷한 부정 요인 없음"],
        "counter_argument": counter_argument,
        "source": "rule_based",
    }


def _build_counter_argument(name: str, components: Dict) -> str:
    vals = [_get_comp(components, k) for k in ("value", "price", "pessimism", "quality", "growth", "risk")]
    total_score = sum(vals) / max(len(vals), 1)
    if total_score >= 65:
        return (
            f"다만 {name}에 대한 낙관은 거시 환경 악화, 업황 둔화, "
            f"또는 시장 전체 조정으로 쉽게 무너질 수 있습니다. "
            f"분할 매수 시에도 1회 투자 비중을 제한하는 것이 안전합니다."
        )
    elif total_score >= 50:
        return (
            f"현재 {name}의 중립적 평가가 향후 실적 서프라이즈나 악재로 "
            f"한쪽으로 급변할 수 있으므로, 명확한 트리거가 발생할 때까지 "
            f"추가 매수보다는 관망이 합리적입니다."
        )
    else:
        return (
            f"{name}의 낮은 점수가 일시적 저점 매력으로 전환될 가능성도 있으나, "
            f"구조적 문제인지 일시적 요인인지 구분하지 않은 상태에서는 매수 근거가 부족합니다."
        )


# ── 판단 변경 조건 자동 생성 ──────────────────────
def build_change_conditions(
    name: str,
    score_data: Dict,
    current_price: Optional[float] = None,
) -> List[str]:
    components = score_data.get("components", {})
    total = score_data.get("total", 50)
    conditions = []

    price_val = None
    if current_price is not None:
        try:
            price_val = float(current_price)
        except (TypeError, ValueError):
            price_val = None

    if price_val and price_val > 0:
        if total >= 65:
            conditions.append(f"현재가({price_val:,.0f}원) 대비 -10% 하락 시 매수 관심도 상승")
            conditions.append(f"현재가 대비 +15% 상승 시 비중 축소 검토")
        elif total >= 50:
            conditions.append(f"현재가({price_val:,.0f}원) 대비 -15% 하락 시 저평가 매력 부각")
        else:
            conditions.append(f"현재가({price_val:,.0f}원) 대비 -20% 이상 하락 시 손실 위험 점검")

    if _get_comp(components, "value") >= 60:
        conditions.append("실적 전망 -10% 이상 하향 시 밸류에이션 매력 약화")
    if _get_comp(components, "pessimism") >= 65:
        conditions.append("시장 심리 회복 조짐(뉴스/거래량) 보일 시 비관 점수 하락")
    if _get_comp(components, "risk") >= 65:
        conditions.append("변동성 축소 시 리스크 점수 개선 가능")

    conditions.append("주요 공시(실적, 유상증자, 자사주) 발생 시 즉시 재평가")
    conditions.append("시장 전체 -5% 이상 하락 시 개별 이슈 vs 시장 이슈 구분")

    return conditions[:5]


# ── Groq API 연동 ───────────────────────────────
class AICoach:
    """AI 투자 코치 - Groq API 기반 (무료)"""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        if self.api_key and HAS_GROQ:
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                print(f"⚠️ Groq 클라이언트 초기화 실패: {e}")
                self.client = None

    def generate_comment(
        self,
        name: str,
        code: str,
        score_data: Dict,
        opinion: str,
        market_ctx: Optional[str] = None,
    ) -> Dict:
        if not self.client:
            return _build_fallback_comment(name, score_data, opinion)

        try:
            return self._call_groq(name, code, score_data, opinion, market_ctx)
        except Exception as e:
            print(f"⚠️ AI 코멘트 실패 ({name}): {e} — 규칙 기반 사용")
            return _build_fallback_comment(name, score_data, opinion)

    def _call_groq(
        self,
        name: str,
        code: str,
        score_data: Dict,
        opinion: str,
        market_ctx: Optional[str],
    ) -> Dict:
        components = score_data.get("components", {})
        total = score_data.get("total", 0)

        value = _get_comp(components, "value")
        price = _get_comp(components, "price")
        pessimism = _get_comp(components, "pessimism")
        quality = _get_comp(components, "quality")
        risk = _get_comp(components, "risk")
        growth = _get_comp(components, "growth")

        prompt = f"""당신은 존 템플턴의 가치투자 원칙을 따르는 신중한 투자 코치입니다.
과도한 확신이나 매수 권유는 피하고, 항상 근거와 반대 근거를 함께 제시합니다.

[종목 정보]
- 이름: {name} ({code})
- 현재 의견: {opinion}
- 총점: {total:.1f} / 100

[세부 점수 (0~100)]
- Value (밸류에이션): {value:.0f}
- Price (가격 매력): {price:.0f}
- Pessimism (시장 비관): {pessimism:.0f}
- Quality (기업 질): {quality:.0f}
- Risk (위험): {risk:.0f}
- Growth (성장): {growth:.0f}

[시장 상황]
{market_ctx or "특이사항 없음"}

[출력 형식 — 반드시 준수]
COMMENT: (2~3문장 종합 코멘트)
POSITIVE:
- (긍정 요인 1)
- (긍정 요인 2)
NEGATIVE:
- (부정 요인 1)
- (부정 요인 2)
COUNTER: (현재 의견에 대한 리스크 1~2문장)

[톤 가이드]
- "무조건 사라", "팔아라" 같은 단정적 표현 금지
- "분할매수 검토", "관망", "보유" 등 중립적 권고
- 한국어만 사용
- 200자 이내로 간결하게
"""

        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )

        text = response.choices[0].message.content
        return self._parse_response(text, name, components)

    def _parse_response(self, text: str, name: str, components: Dict) -> Dict:
        comment = ""
        positives = []
        negatives = []
        counter = ""

        section = None
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            upper = line.upper()
            if upper.startswith("COMMENT:"):
                section = "comment"
                comment = line.split(":", 1)[1].strip()
                continue
            if upper.startswith("POSITIVE"):
                section = "positive"
                continue
            if upper.startswith("NEGATIVE"):
                section = "negative"
                continue
            if upper.startswith("COUNTER"):
                section = "counter"
                counter = line.split(":", 1)[1].strip() if ":" in line else ""
                continue

            if section == "comment" and not comment:
                comment = line
            elif section == "positive":
                clean = line.lstrip("-•·* ").strip()
                if clean:
                    positives.append(clean)
            elif section == "negative":
                clean = line.lstrip("-•·* ").strip()
                if clean:
                    negatives.append(clean)
            elif section == "counter":
                counter += " " + line

        if not positives and not negatives:
            return _build_fallback_comment(
                name,
                {"components": components, "total": sum(_get_comp(components, k) for k in ("value", "price", "pessimism", "quality", "growth", "risk")) / 6},
                "",
            )

        return {
            "comment": comment or text[:200],
            "positives": positives or ["뚜렷한 긍정 요인 없음"],
            "negatives": negatives or ["뚜렷한 부정 요인 없음"],
            "counter_argument": counter.strip() or _build_counter_argument(name, components),
            "source": "groq",
        }


# 싱글톤
_coach = None


def get_coach() -> AICoach:
    global _coach
    if _coach is None:
        _coach = AICoach()
    return _coach
