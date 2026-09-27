# Templeton S — 현재 작업 상태

최종 갱신: 2026-09-27

## 현재 단계

**Phase 3 — 새 React 이식 및 Oracle 배포 완료**

## 작업 기준

- 기능/화면 Source of Truth: 정상 작동하는 기존 Streamlit
- 최종 React: Streamlit을 기준으로 새로 작성
- 기존 Oracle React: 프로토타입/검증용이며 최종본으로 사용하지 않음
- Oracle: 새 React production build의 배포 대상

기본 흐름:
```
Streamlit
  ↓
새 React 작성
  ↓
검증된 FastAPI / KIS / Score 연결
  ↓
실데이터 검증
  ↓
GitHub 기준본
  ↓
Oracle 새 build
  ↓
기존 Oracle React 덮어쓰기
```

## 2026-09-27 React 이식/배포 완료

- GitHub `origin/main`을 Oracle `main`에 동기화: `e0a7646`
- 기존 Oracle 로컬 작업물은 `~/templeton-backup-20260927/`에 백업
- 새 `frontend/`의 Oracle production build 성공
- `npm ci`는 lockfile 부재로 실패했지만 `npm run build`는 정상 성공
- Caddy가 `/templeton/*`을 `~/templeton-s/frontend/dist`에서 서비스하는 구조 확인
- 실제 FastAPI `/health` 정상
- 실제 `/scores`에서 KIS/Templeton Score 데이터 반환 확인
- 브라우저의 `/templeton/`에서 새 React 대시보드 정상 표시 확인
- 따라서 **React 이식 및 Oracle 배포는 완료**로 판정한다.

## 현재 알려진 구조

- Oracle 프로젝트: `~/templeton-s/`
- FastAPI: `:8001`
- React/Vite: 정적 build
- Caddy: HTTPS / 정적 파일 / reverse proxy
- DB: Neon Postgres
- React public path: `/templeton/`
- API public path: `/templeton-api/`
- API systemd service: `templeton-api.service`

## KIS 상태 — 닫힘

KIS 연동은 현재 단계에서 정상 동작으로 간주하고 종료한다.

- Streamlit에서 KIS 데이터 수신 확인
- Oracle에서 KIS 데이터 수집 확인
- 실제 React/API 경로에서도 KIS 데이터 표시 확인

과거 GitHub Actions 인증 문제는 실제 새 수집 경로에서 실패할 때 다시 본다.

## 핵심 운영/데이터 아키텍처 — 2026-09-26 확정

앱 실행과 자동 축적은 분리한다.

```
앱 실행 → 현재 상태 조회/표시
09:30·17:00 → 데이터 + 판단 스냅샷 축적
```

평일 09:30 / 17:00 KST, 하루 2회 Oracle에서 자동 수집한다. 각 수집 시점에 KIS, Templeton Score 입력, FRED/매크로, AI 판단에 필요한 시장 컨텍스트를 하나의 시점 스냅샷으로 기록한다.

AI Guide는 당시 데이터와 함께 보존하고, Panic Watch는 같은 스냅샷을 여러 시점에 걸쳐 추적한다. 사후검증은 원래 판단과 분리한다.

## Neon DB 구조 재정비 방향

현재 Neon은 `prices_daily` / `templeton_scores` / `macro_daily` 중심의 단순 구조다. 바로 대량 변경하지 않고 실제 Oracle DB 스키마와 코드 사용처를 대조한 뒤 단계적으로 확장한다.

목표 개념:

```
collection_run → market_snapshot → raw/context data + score
                         ↓
                    ai_judgment
                         ↓
                 panic_event/state
                         ↓
                      outcome
```

## AI 판단 모델 운영 원칙 — 2026-09-27 확정

현재 AI 연동은 **Groq API + Llama 3.3 70B**다. Groq과 xAI Grok을 혼동하지 않는다.

지금은 모델 교체보다 데이터 수집 → Snapshot → Score → AI 판단 → Neon 기록의 안정화가 우선이다. provider/model/version을 교체 가능하게 보존하고, 충분한 데이터가 쌓인 뒤 동일 Snapshot 기반으로 모델을 비교한다.

## 다음 작업

Panic Watch 기본 연결과 Oracle 검증이 완료되었다. 다음은 **사후 outcome 자동 검증을 실제 운영에 연결**하는 단계다.

1. Oracle에서 outcome schema/collector를 pull 후 수동 실행 검증
2. 평일 18:30 KST outcome evaluator 자동 실행 연결
3. Snapshot 시점 AI 판단과 1/5/20일 실제 결과를 별도 조회하는 화면/API 연결
4. FRED/매크로 실제 데이터 컨텍스트를 Snapshot에 연결
5. 충분한 데이터가 쌓인 뒤 AI 모델 비교/교체 가능 구조를 실제 운용
6. 이후 필요한 UI 개선은 실제 축적 데이터에 맞춰 단계적으로 진행

## 2026-09-27 운영 Snapshot 파이프라인 — 완료

- 기존 `scripts/daily_log.py`는 수동/기존 JSONL 기록용으로 보존하고 production collector로 대체하지 않음
- `scripts/snapshot_collect.py`를 Oracle에서 실제 실행해 KIS 실데이터 6종목 + Templeton Score 수집 확인
- Neon 연결 문제(`NEON_DATABASE_URL`의 `sslmode` 오기입)를 수정하고 연결 정상 확인
- 실제 Neon 기존 스키마에 맞춰 collector/schema를 additive 방식으로 정렬
- UUID adaptation 문제를 수정
- 수동 Snapshot 1회 실행 성공:
  - `collection_runs`: `completed`
  - `market_snapshots`: 1건
  - `ai_judgments`: 6건
  - `panic_events`: 1건
- AI 판단은 실제 `provider=groq`, `model=llama-3.3-70b-versatile`로 저장된 것을 Neon에서 확인
- Oracle cron을 평일 09:30 / 17:00 KST로 전환 완료:
  - 09:30 KST → 00:30 UTC
  - 17:00 KST → 08:00 UTC
- 앱 실행과 자동 축적은 분리된 상태:
  - 앱 실행 → 현재 데이터 조회/표시
  - cron → 시점 Snapshot/AI 판단 축적


## 2026-09-27 Panic Watch 1차 구현

- FastAPI `/panic-watch` 추가: Neon의 `market_snapshots` + `panic_events` 누적 기록을 읽기 전용으로 제공
- React에 Panic Watch 패널 추가: Snapshot 시점, 시장 regime, 정상/활성 위험 신호, 관련 종목, KODEX 200 등락률 표시
- 앱 조회는 DB를 변경하지 않고 누적 Snapshot을 읽기만 함
- GitHub 기준 코드 반영 완료
- 다음: Oracle pull → FastAPI 재시작 → React build → 브라우저 검증

## 2026-09-27 Snapshot Outcome 1차 구현

- `snapshot_outcomes`를 종목별 `symbol + horizon_days` 기준으로 확장
- `scripts/snapshot_outcomes.py` 추가
  - 원본 Snapshot/AI 판단을 변경하지 않음
  - 1/5/20일 후 실제 거래일 가격을 KIS 일봉에서 조회
  - 종목 수익률 및 KODEX 200 대비 수익률을 별도 저장
  - 원래 Snapshot의 AI opinion을 결과에 보존
- FastAPI `/snapshot-outcomes` 추가
- 현재 Snapshot이 1건뿐이므로 아직 평가 대상 horizon이 충분히 경과하지 않은 것은 정상
- 다음: Oracle pull → 수동 evaluator 실행 → DB 결과 확인 → 평일 18:30 KST 자동화

## 기록 원칙

이 파일에는 작업 연속성에 필요한 최소한의 내용만 기록한다. 주요 단계가 끝날 때 현재 단계/완료/문제/다음 작업만 갱신한다.
