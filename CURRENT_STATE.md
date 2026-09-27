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

## 2026-09-27 FRED 매크로 Snapshot 연결

- src/fred_client.py 추가
- FRED_API_KEY를 사용해 다음 최신 관측치를 Snapshot마다 조회:
  - DGS10: 미국 10년 국채금리
  - DFII10: 미국 10년 실질금리
  - BAA10Y: Baa 회사채-10년 국채 스프레드
  - FEDFUNDS: 연방기금금리
  - CPIAUCSL: 미국 CPI
- FRED 실패 시 KIS Snapshot 자체는 실패시키지 않고 macro_data.status에 상태를 남김
- FRED 결과를 market_snapshots.macro_data에 저장
- 동일 매크로 컨텍스트를 당시 AI 판단의 input_data에도 보존
- FRED 값은 매 Snapshot 시점에 다시 조회하므로 당시 판단 컨텍스트를 보존

## 다음 작업

1. Oracle에서 최신 GitHub 코드 pull
2. FRED 연동 포함 Snapshot을 실제 1회 수동 실행
3. Neon에서 macro_data 실제 값 확인
4. AI judgment에 FRED 컨텍스트가 함께 저장됐는지 확인
5. 문제 없으면 현재 cron으로 자동 축적
6. 이후 충분한 데이터가 쌓이면 AI 모델 비교/Outcome 분석 및 필요한 UI 연결

## 기록 원칙

문서 기록 자체가 목적이 아니다. 실제 작업의 연속성을 위해 완료/문제/다음 작업만 최소한으로 기록.