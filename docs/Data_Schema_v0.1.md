# Data Schema v0.1
**템플턴S · 데이터 항목 정의**

## 레이어 구조
1. Market Data Layer — 실시간/준실시간 가격·거래 데이터
2. Fundamental Layer — 재무·밸류에이션
3. Macro / Market Context Layer — 지수·금리·환율 등
4. Event Layer — 뉴스·공시

프로그램이 수집·계산하고, AI는 처리된 결과만 해석한다.

---

## A. 실시간/준실시간 시장 데이터 (Market Data)

| 필드명 | 타입 | 설명 | 출처 예시 |
|--------|------|------|-----------|
| symbol | str | 종목코드 | 005930, 069500 |
| name | str | 종목명 | |
| current_price | float | 현재가 | KIS inquire-price |
| change | float | 전일대비 | |
| change_rate | float | 등락률 (%) | |
| volume | int | 거래량 | |
| trading_value | float | 거래대금 | |
| open | float | 시가 | |
| high | float | 고가 | |
| low | float | 저가 | |
| prev_close | float | 전일종가 | |
| high_52w | float | 52주 최고가 | |
| low_52w | float | 52주 최저가 | |
| high_52w_date | date | 52주 최고가 일자 | |
| market_cap | float | 시가총액 (개별주) | |
| timestamp | datetime | 데이터 수신 시각 | |

**프로그램 생성 필드**
- drop_from_52w_high (%)
- drop_from_recent_high
- relative_performance_vs_benchmark

---

## B. 재무·밸류에이션 데이터 (Fundamental)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| per | float | 현재 PER |
| pbr | float | 현재 PBR |
| eps | float | EPS (TTM 등) |
| bps | float | BPS |
| roe | float | ROE |
| debt_ratio | float | 부채비율 |
| operating_margin | float | 영업이익률 |
| net_margin | float | 순이익률 |
| revenue_growth_3y | float | 3년 매출 성장률 |
| op_income_growth_3y | float | 3년 영업이익 성장률 |
| avg_per_5y | float | 과거 5년 평균 PER |
| avg_pbr_5y | float | 과거 5년 평균 PBR |
| dividend_yield | float | 배당수익률 |
| free_cash_flow | float | 잉여현금흐름 |
| interest_coverage | float | 이자보상배율 |

**ETF 전용**
- nav, tracking_error, expense_ratio, distribution_yield, underlying_index

---

## C. 시장·매크로 데이터

| 필드명 | 설명 |
|--------|------|
| kospi | KOSPI 지수 |
| kosdaq | KOSDAQ 지수 |
| sp500_proxy | TIGER 미국S&P500 가격 또는 지수 |
| usdkrw | 원달러 환율 |
| market_volatility | 변동성 지표 (가능 시) |
| interest_rate | 기준금리 등 |

---

## D. 이벤트 데이터 (뉴스·공시)

| 필드명 | 설명 |
|--------|------|
| news_title | 뉴스 제목 |
| news_summary | 요약 |
| news_sentiment | 호재 / 중립 / 악재 / 치명적 악재 |
| impact_on_value | 내재가치 영향 여부 (AI 판단) |
| disclosure_type | 실적, 유상증자, 자사주, 배당, 계약, 소송 등 |
| disclosure_date | 공시일 |
| importance | 높음 / 중간 / 낮음 |

**이벤트 트리거 조건**
- 가격이 일정 기준 이상 급변
- 중요 공시 발생
- 중요 뉴스 발생 → AI 재분석 호출

---

## E. 데이터베이스 테이블 초안 (SQLite / PostgreSQL)

### symbols
- symbol (PK), name, asset_type (stock/etf), market (KR/US), is_active, notes

### market_snapshots
- id, symbol, current_price, change, change_rate, volume, high_52w, low_52w, drop_from_52w_high, timestamp

### fundamentals
- id, symbol, as_of_date, per, pbr, roe, debt_ratio, ... (위 필드들)

### scores
- id, symbol, score_date, total_score, value_score, price_score, pessimism_score, quality_score, growth_score, risk_score, opinion, rationale_json

### judgments
- id, symbol, judgment_time, score, opinion, reasons, counter_reasons, change_conditions, outcome_checked_at, outcome_return

### events
- id, symbol, event_type, title, summary, sentiment, importance, occurred_at, processed
