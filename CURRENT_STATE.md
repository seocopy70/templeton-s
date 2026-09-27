# Templeton S — 현재 작업 상태

최종 갱신: 2026-09-27

## 현재 단계

**Phase 3 — 새 React 이식 및 Oracle 배포 완료 / 운영 데이터 축적 단계**

## 작업 기준

- 기능/화면 Source of Truth: 정상 작동하는 기존 Streamlit
- 최종 React: Streamlit을 기준으로 새로 작성
- 기존 Oracle React: 프로토타입/검증용이며 최종본으로 사용하지 않음
- Oracle: 새 React production build의 배포 대상

## 2026-09-27 React 이식/배포 완료

- 새 React/Vite 작성 및 Oracle production build 성공
- Caddy /templeton/* 정적 서비스 확인
- FastAPI /health, /scores 실제 KIS 데이터 확인
- 브라우저 /templeton/ 정상 표시
- React 이식 및 Oracle 배포 완료

## 현재 구조

- Oracle: ~/templeton-s/
- FastAPI: :8001
- React/Vite: 정적 build
- Caddy: HTTPS / 정적 파일 / reverse proxy
- DB: Neon Postgres
- React public path: /templeton/
- API public path: /templeton-api/
- API service: templeton-api.service

## 핵심 운영 구조

앱 실행과 자동 축적은 분리한다.

```
앱 실행 → 현재 상태 조회/표시
평일 09:30·17:00 → KIS + Score + FRED + AI 판단 Snapshot
평일 18:30 → 1/5/20일 Outcome 평가
```

앱을 열어도 역사 기록은 생성하지 않는다.

## 2026-09-27 Snapshot 파이프라인 완료

- scripts/snapshot_collect.py Oracle 실데이터 실행 성공
- KIS 6종목 + Templeton Score 저장
- Neon collection_runs / market_snapshots / ai_judgments / panic_events 정상
- 실제 AI: provider=groq, model=llama-3.3-70b-versatile
- 평일 09:30 / 17:00 KST 자동 수집 cron 등록

## 2026-09-27 Panic Watch 완료

- FastAPI /panic-watch 추가 및 Oracle 검증 완료
- React Panic Watch 패널 연결
- Snapshot 누적 기록을 읽기 전용으로 조회

## 2026-09-27 Snapshot Outcome 완료

- snapshot_outcomes를 snapshot_id + symbol + horizon_days 기준으로 확장
- scripts/snapshot_outcomes.py 추가
- 1/5/20일 실제 거래일 가격 및 KODEX 200 대비 수익률 저장
- 원본 AI 판단은 변경하지 않음
- FastAPI /snapshot-outcomes 추가
- Oracle 수동 evaluator 실행 성공(created=0: 아직 미래 horizon 미도래)
- 평일 18:30 KST 자동 평가 cron 등록
- Oracle /snapshot-outcomes API 정상 응답 확인

## 2026-09-27 FRED 매크로 연동 완료

- src/fred_client.py 추가
- Oracle config/.env의 FRED_API_KEY 확인
- 실제 FRED API 호출 성공
- 다음 관측치가 실제 Snapshot에 저장되는 것까지 검증:
  - DGS10: 미국 10년 국채금리
  - DFII10: 미국 10년 실질금리
  - BAA10Y: Baa 회사채-10년 국채 스프레드
  - FEDFUNDS: 연방기금금리
  - CPIAUCSL: 미국 CPI
- FRED 결과를 market_snapshots.macro_data에 저장
- 동일 매크로 컨텍스트를 당시 AI 판단의 input_data에도 보존
- FRED 실패 시 KIS Snapshot 자체는 실패시키지 않고 macro_data.status에 상태를 남김
- 실제 Snapshot 1회 실행 및 Neon read-only 검증 완료
- 검증된 Snapshot: 8b28bbd5-86a0-4dd3-984a-522a869817d2
- 검증된 run: 56c22437-24e0-4b97-a691-15af90bf8413

## 2026-09-27 Streamlit 기능 보강 React UI 구현

Streamlit에서 확인된 기존 핵심 화면 중 React에 빠져 있던 영역을 새 React 구조에 추가했다.

- KOSPI / KOSDAQ / S&P500 / NASDAQ / Nikkei225 시장 기본 정보
- 주요 시장 약 1개월 추이 그래프
- 관심종목 6개 통합 현황 표
- DART 최근 공시 영역 및 원문 링크
- Neon에 저장된 실제 AI Snapshot 판단 기록 조회
- Snapshot 1/5/20일 사후검증 결과 영역 및 KODEX 200 상대성과
- 기존 Panic Watch와 종목별 상세 화면은 유지
- 새 API: `/disclosures`, `/ai-judgments`

현재 코드는 GitHub main 기준으로 구현 완료했으며 Oracle 반영은 build/브라우저 검증 후 확정한다.

## 2026-09-27 UI 밀도/데이터 표시 보정

- `/market-overview`의 실제 응답이 배열인 점을 React에서 정규화해 시장 기본정보/추이 표시를 복구
- 최근 공시는 8건만 조회하고 내부 스크롤 영역으로 축소
- 최근 판단 기록도 고정 높이 내부 스크롤 적용
- 종목별 Score 상세 막대는 기본 접힘으로 변경하고 표시 시에도 높이를 축소
- 시장 추이 그래프를 카드당 컴팩트하게 조정
- GitHub main 반영 완료; Oracle build/브라우저 검증 대기

## 2026-09-27 초기 화면 로딩 개선

- `/latest-snapshot` read-only API 추가: Neon의 최신 Snapshot을 KIS 재조회 없이 반환
- React는 최신 Snapshot을 먼저 표시하고, 동시에 `/scores`로 현재 KIS 데이터를 갱신
- 첫 화면에서 5~8초간 빈 화면/스켈레톤만 기다리는 체감을 줄임
- 30초 자동 갱신은 실시간 투자 목적과 맞지 않아 **10분 자동 갱신**으로 변경
- 수동 새로고침은 기존대로 즉시 현재 데이터 재조회
- Snapshot 표시와 현재 데이터 갱신을 구분하고 앱 실행 자체가 기록을 생성하지 않는 원칙 유지

## 현재 운영 상태

- 개발/이식/배포 작업은 완료
- 현재는 실제 시장 데이터를 자동 축적하면서 Outcome을 기다리는 운영 검증 단계
- 평일 09:30 / 17:00 KST Snapshot 자동수집
- 평일 18:30 KST 1/5/20일 Outcome 자동평가
- 앱 실행은 현재 데이터 조회/표시만 수행하며 Snapshot을 생성하지 않음
- 추가 기능 개발은 당분간 보류하고 실제 데이터 축적과 성과검증을 우선함

## 다음 작업

1. 새 React UI를 Oracle에서 pull/build 후 브라우저 검증
2. 자동수집 cron의 실제 실행 여부 확인
3. 1/5/20일 horizon 도래 후 snapshot_outcomes 생성 확인
4. 충분한 데이터 축적 후 AI 판단과 KODEX 200 대비 성과 분석
5. 필요할 때만 AI 모델 비교 및 관련 UI 확장

## 기록 원칙

문서 기록 자체가 목적이 아니다. 실제 작업의 연속성을 위해 완료/문제/다음 작업만 최소한으로 기록.
