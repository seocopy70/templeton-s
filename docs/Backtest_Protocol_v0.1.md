# Templeton-S 백테스트 검증 프로토콜 v0.1

> PHASE A 확정 · 2026-09-02  
> 원칙: 본 앱 미수정 · Point-in-Time · 정보시간≠결과시간 · Score Engine 공유·데이터 공급 분리

## 0. 목적

과거 시점 **T**에서 Templeton-S가 **이용 가능했던 정보만**으로 Score·의견·(가능 시) 시장모드/공황분류/기회순위를 재현하고,  
그 판단 이후 **실제 성과**를 측정한다.

- 판단 과정: T 이전·이용가능 정보만  
- 평가 과정: T 이후 주가·벤치마크 (미래 데이터는 평가 전용)

## 1. 판단 단위

| 항목 | 확정 (v0.1) |
|------|-------------|
| 단위 | **거래일 1회 스냅샷** |
| 기준 | 해당일 **종가(as-of close)** |
| 장중 재현 | 하지 않음 |
| 이벤트 트리거 | 보조 로그 가능, 기본 루프는 일 단위 |

## 2. 과거시점 기준

- `as_of = YYYY-MM-DD` (KST 거래일)  
- 해당일 종가까지를 “그날 장 마감 후 알 수 있는 가격 정보”로 본다.  
- 장 마감 후 공시(16:00 이후 등)는 **다음 거래일**부터 이용 가능 (보수적).

## 3. 정보 이용 가능 시점 규칙

| 데이터 | 규칙 (v0.1) |
|--------|-------------|
| 주가·일봉 | `date <= as_of` 인 봉만 |
| 52주 고저 | as_of 기준 직전 252거래일 윈도우 |
| 변동성·모멘텀 | as_of 이전 일봉으로만 계산 |
| 재무(PER/PBR 등) | v0.1: **미사용 또는 None** (공시일 DB 부재). Quality/Growth/Value는 중립 폴백 |
| DART 공시 | `available_at`/`rcept_dt` ≤ as_of 만 (연동 시). 없으면 이벤트 빈 리스트 |
| 뉴스 | v0.1 미사용 |

> 재무 Point-in-Time DB는 PHASE B 확장. 지금은 **가격 기반 재현의 신뢰**를 우선한다.

## 4. 백테스트 대상

- **확정 6종목** (config.SYMBOLS)  
- 벤치마크: **KODEX 200 (069500)**  
- 미국 직접상장 주식 제외 (국내 상장 ETF만)

## 5. 평가 기간 (거래일)

`+5, +20, +60, +120, +252`  
각 구간: 종목 수익률, 벤치 수익률, **초과수익(excess)**  
가능 시 구간 MDD(종목)

## 6. 벤치마크

- 기본: KODEX 200 동일 구간 수익률  
- 기록 필드: `ret`, `bench_ret`, `excess`

## 7. 합격 기준

**v0.1에서 숫자 고정하지 않음.**  
Level1→2 결과를 본 뒤 목적에 맞게 정의한다.

### 검증 레벨

| Level | 내용 |
|-------|------|
| L1 Score Validation | Score 구간별 이후 수익·초과수익 |
| L2 Decision Validation | 의견·regime·panic·opportunity_rank별 성과 |
| L3 Portfolio | (이후) 다종목 자산곡선 |

### 위험 감지 (별도 지표)

- 의견 `매수 회피` / regime `watch`·`panic_zone` 이후 벤치 급락 여부  
- Detection lead time: 실제 급락 시작일 대비 경고 선행 거래일 (시나리오 분석 시)

## 8. 엔진·재현성

- 결과에 반드시 `engine_version` (예: `score_v0.5`)  
- Historical Snapshot ID/내용 저장 → 동일 as_of 재실행 시 Score 재현 가능해야 함  
- 본 앱 `app.py`·실시간 경로 **수정 금지**. `backtest/`·`scripts/run_backtest.py`만 사용

## 9. 본 앱과의 관계

```
본 앱          →  현재 데이터 공급 → Score Engine → 현재 판단
백테스트       →  PIT 데이터 공급 → Score Engine → 과거 판단 → Forward 평가
```

Score Engine 코드는 `src/score_engine.py`를 **import만** 한다.

## 10. Phase 5-R 반영

논의 이후 추가된 로직도 동일 PIT 규칙으로 재현·기록한다.

- `market_regime` (normal / watch / panic_zone)  
- `panic_type`  
- `opportunity_rank` / `opportunity_score`  

(공시 없는 구간은 events=[] 로 보수 분류)

## 11. 개발 순서 (본 문서 이후)

| Phase | 내용 | v0.1 |
|-------|------|------|
| A | 프로토콜 확정 | **본 문서** |
| B–D | PIT·Snapshot | 코드 |
| E–F | Score 연결·단일일 재현 | 코드 |
| G | 다수 날짜 | 코드 |
| H | 시나리오(폭락 등) | 코드 초안 |
| I–K | 포트폴리오·OOS | 이후 |
