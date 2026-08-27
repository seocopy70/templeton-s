# Templeton Score Calculation v0.1
**점수 계산식 초안**

총점 = Σ (각 요소 점수 × 비중)  
각 요소는 0~100으로 정규화한 뒤 비중을 곱한다. 최종 점수는 0~100으로 클리핑.

## 가중치
- Value: 0.25
- Price Attractiveness: 0.20
- Market Pessimism: 0.15
- Quality: 0.15
- Growth: 0.10
- Risk: 0.15

---

## 1. Value Score (25%)
```
value_score = clamp(0, 100,
  50
  + per_discount_factor * 40
  + pbr_discount_factor * 30
  + quality_adjustment   # -30 ~ +20
)
```
- per_discount_factor = (avg_per_5y - current_per) / avg_per_5y  (할인율)
- pbr_discount_factor 동일 방식
- 현재 밸류가 역사 평균보다 비싸면 음수 → 점수 하락
- ETF는 기초지수/유사 ETF 대비 상대 밸류 사용

## 2. Price Attractiveness Score (20%)
```
price_score = clamp(0, 100,
  drop_from_52w_high * 1.2
  + relative_drop_vs_market * 0.8
)
```
- 52주 고점 대비 하락률이 클수록 가점
- 시장 대비 더 많이 떨어졌을 때 추가 가점
- 가치 훼손이 확인되면 상한 제한 적용 가능

## 3. Market Pessimism Score (15%)
```
pessimism_score = clamp(0, 100,
  40
  + relative_underperformance * 1.5
  + news_fear_ratio * 30
  + volume_spike_bonus
)
```
- 개별 종목이 시장보다 크게 하락 + 공포 뉴스 많을수록 점수↑

## 4. Quality Score (15%)
```
quality_score = base_from_roe_debt_margin_cashflow
                + competitive_position_bonus
                - risk_penalty
```
- ROE 높고 부채 낮고 현금흐름 안정적일수록 높음
- ETF는 전략 안정성·구성 종목 품질로 대체

## 5. Growth Score (10%)
```
growth_score = weighted_avg(매출성장, 이익성장, 전망성장)
```
- 중장기 성장 확인 시 가점, 급격한 둔화 시 감점

## 6. Risk Score (15%) — 차감 방식
```
risk_score = 100 - risk_penalty
```
- 업황·재무·규제·소송·환율 위험 합산 차감
- 치명적 위험 확인 시 전체 Score에 추가 페널티 (-15 ~ -30)

## 최종
```
Templeton_Score = (
  Value * 0.25
  + Price * 0.20
  + Pessimism * 0.15
  + Quality * 0.15
  + Growth * 0.10
  + Risk * 0.15
)
```

## 의사코드 (Python 스타일)
```python
def calculate_templeton_score(data: dict) -> dict:
    value = calc_value(data)
    price = calc_price_attractiveness(data)
    pessimism = calc_pessimism(data)
    quality = calc_quality(data)
    growth = calc_growth(data)
    risk = calc_risk(data)

    total = (
        value * 0.25
        + price * 0.20
        + pessimism * 0.15
        + quality * 0.15
        + growth * 0.10
        + risk * 0.15
    )
    total = max(0, min(100, total))

    opinion = score_to_opinion(total)
    return {
        "total": round(total, 1),
        "components": {
            "value": value,
            "price": price,
            "pessimism": pessimism,
            "quality": quality,
            "growth": growth,
            "risk": risk,
        },
        "opinion": opinion,
    }

def score_to_opinion(score: float) -> str:
    if score < 40:
        return "매수 회피"
    if score < 60:
        return "관망"
    if score < 75:
        return "보유/관찰"
    if score < 85:
        return "분할매수 관심"
    return "적극적 관심"
```

## 주의
- 이 수식은 v0.1 초안이다. 실제 데이터를 쌓고 백테스트하면서 가중치와 계수를 조정한다.
- AI는 이 점수를 해석할 뿐, 점수 자체를 계산하지 않는다.
