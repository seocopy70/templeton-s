# Templeton S — 현재 작업 상태

최종 갱신: 2026-09-26

## 현재 단계

**Phase 3 — 실제 API 연결 및 React 실데이터 검증**

## 현재 목표

1. Oracle의 현재 작업본을 보호한다.
2. React/Vite 흰 화면의 실제 원인을 확인한다.
3. 기존 Streamlit 수준의 핵심 대시보드를 React로 확보한다.
4. 검증된 기준본을 GitHub에 저장한다.
5. 이후 Local VS Code → GitHub → Oracle 흐름으로 전환한다.

## 현재까지 확인된 구조

- Oracle 프로젝트: `~/templeton-s/`
- FastAPI: `:8001`
- React/Vite: 정적 build
- Caddy: HTTPS / 정적 파일 / reverse proxy
- DB: Neon Postgres
- React public path: `/templeton/`
- API public path: `/templeton-api/`
- API systemd service: `templeton-api.service`

## 현재 알려진 문제

`https://seo-email.duckdns.org/templeton/` 접속 시 흰 화면.

React build 자체는 성공한 것으로 알려져 있으나 runtime/browser 원인은 아직 확정하지 않았다.

가능성:
- JavaScript runtime error
- asset 경로 또는 Caddy 설정
- Recharts 등 프론트 dependency
- API fetch/runtime 처리
- 실제 서비스 중인 dist가 예상과 다른 경우

**원인을 추측하여 구조를 크게 변경하지 않는다.**

## GitHub / Oracle 기준본 상태

현재 Oracle 작업본이 GitHub보다 앞서 있을 가능성이 있다.

따라서 먼저:
1. Oracle `git status`
2. remote / branch 확인
3. frontend/api 실제 파일 확인
4. Caddy 및 systemd 확인
5. 현재 dist 확인
6. API 직접 호출 확인

후 안전하게 기준본을 정한다.

**Oracle 작업본 확인 전에는 reset, force push, 대량 삭제를 하지 않는다.**

## 다음 작업

### 1순위
Oracle의 실제 현재 상태를 확인한다.

### 2순위
React 흰 화면의 원인을 최소 범위에서 해결한다.

### 3순위
기존 Streamlit의 핵심 정보를 React 화면에 표시한다.

### 4순위
실제 `/scores`, `/prices` API를 연결하고 수치를 검증한다.

### 5순위
검증된 작업본을 GitHub 기준본으로 확립한다.

## 2026-09-26 진행 기록 — React 화면 정상화

- Oracle 실제 작업본 확인 결과 `~/templeton-s/`가 현재 프로젝트 작업 디렉터리이며, 기존 Streamlit 코드(`app.py`, `src/*`)와 React/Vite(`frontend/`), FastAPI(`api/`)가 함께 존재함.
- React 흰 화면 원인은 Vite의 public base path 누락으로 확인됨. `vite.config.js`에 `base: '/templeton/'`를 추가하고 재빌드함.
- `dist/index.html`의 JS/CSS/favicon 경로가 모두 `/templeton/...`로 생성되는 것을 확인함.
- 공개 URL `/templeton/`에서 React 화면이 정상 표시됨.
- 현재 화면의 종목/Score/가격 등은 React의 mock 데이터가 표시되는 상태로 판단됨. Score History는 아직 실제 연결되지 않음.
- FastAPI의 현재 `/`는 200이지만 `/scores`, `/prices`는 404. 실제 데이터 연결은 아직 미완료.
- 기존 Streamlit `app.py` 및 `src/market_data.py`, `src/score_engine.py`를 확인한 결과 실제 KIS 현재가/일봉 데이터와 기존 Templeton Score 계산 로직이 이미 존재함. 따라서 React 이식에서는 새 계산 로직을 만들기보다 기존 로직을 API에 연결하는 것을 우선함.

### 작업 방향 확정 — Main App 우선 이식

레포 전체를 확인한 결과 Templeton S는 단일 앱이 아니라 다음 계층으로 확장되어 있음.
- **Main App**: `app.py` + `src/kis_client.py` + `src/market_data.py` + `src/score_engine.py` + 시장모드/공시/AI/판단기록/사후검증 모듈
- **Macro 확장**: `src/macro/*`, `scripts/collect_macro.py`, GitHub Actions `macro_data.yml`, Streamlit `pages/2_🌐_Macro_Monitor.py`
- **Backtest 확장**: `backtest/*`, `scripts/run_backtest.py`
- **Daily/Ops 확장**: `scripts/daily_collect.py`, `scripts/daily_log.py`, 관련 GitHub Actions
- **React/FastAPI 이식본**: 현재 Oracle 작업본의 `frontend/`, `api/`는 아직 GitHub main에 기준선으로 반영되지 않은 상태.

이식 전략은 **전체 기능을 한꺼번에 옮기지 않고 Main App을 먼저 기존 Streamlit과 기능/데이터 기준으로 최대한 동일하게 복원**한다. Main App의 실제 KIS 가격·60일 일봉·Templeton Score·시장모드·관심종목 표/상세·판단기록을 먼저 React에서 검증한 뒤, Macro / Backtest / Daily/Ops를 순차 이식한다.

현재 React의 mock 종목/Score/가격은 실제 데이터 연결 전 임시 UI이며, 기존 `app.py`의 계산 로직을 재작성하지 않는다. API 계층은 기존 Python 모듈을 호출하는 얇은 어댑터로 설계한다.

### 다음 작업
1. 기존 Streamlit 화면의 실제 기능/표시 항목과 현재 React 구현을 대조한다.
2. 기존 KIS/Score/DB 흐름을 최대한 보존하면서 React용 FastAPI API 설계를 확정한다.
3. `/scores`, `/prices`, History를 실제 데이터로 연결하고 수치를 검증한다.

## 기록 원칙

이 파일에는 작업 연속성에 필요한 최소한의 내용만 기록한다.

각 주요 단계가 끝날 때 다음만 갱신한다.
- 현재 단계
- 완료한 작업
- 현재 문제
- 다음 작업

문서 자체를 만드는 것이 목적이 아니다.


## 2026-09-26 운영 원칙 — 작업계획 및 연속성 기록

- 현재 확정된 수정계획은 **Main App 우선 → 실제 데이터/API 연결 → 수치 검증 → GitHub 기준본 확립 → Macro → Backtest → Daily/Ops 순차 이식**이다.
- 작업 중 중요한 변경, 검증 결과, 실패/보류, 다음 단계가 생기면 사용자의 별도 요청이 없어도 `CURRENT_STATE.md`를 최소한으로 갱신한다.
- 기록은 수학증명 프로젝트와 같은 방식으로 **작업 연속성을 위한 기준점**으로 사용한다. 완료된 작업을 반복하지 않고, 실제 코드/서버 상태와 문서가 다르면 실제 상태를 우선 확인한 뒤 기록을 수정한다.
- 단순한 중간 작업이나 이미 기록된 내용을 반복해서 문서화하지 않는다.
- 다음 채팅에서 작업을 재개할 때는 `PROJECT_INSTRUCTIONS.md`, `MIGRATION_PLAN.md`, `CURRENT_STATE.md`를 먼저 확인하고, `CURRENT_STATE.md`의 다음 작업부터 이어간다.


## 2026-09-26 Main App 기능 대조 완료

기존 Streamlit `app.py`를 기준으로 React Main App의 1차 이식 범위를 확정했다.

### React Main App에 우선 필요한 실제 데이터/API
- `/scores`: 6개 관심종목의 현재가, 등락률, 52주 고점대비, PER/PBR/EPS, Templeton Score 및 6개 구성요소, 의견, Value/Pessimism/Risk/Quality/Growth 입력값
- `/prices/:symbol/history` 또는 동등한 History API: 기존 KIS `get_daily_closes()` 기반 60일 일봉
- `/market-overview`: KOSPI/KOSDAQ/S&P500/NASDAQ/Nikkei225와 약 1개월 추이
- `/decisions`: 기존 `decision_log.py`의 최근 판단 기록 및 종목 필터
- 이후 단계 API: DART 공시, 시장모드/공황분류/기회순위, 사후검증

### 계산 로직 보존 원칙
React에서 Score를 다시 계산하지 않는다.
- 가격/재무: `KISClient.get_current_price()`, `get_financial_ratios()`
- 일봉: `get_daily_closes()`
- 지표: `market_data.compute_volatility()`, `compute_momentum()`
- Score: `calculate_templeton_score()`
- 시장 요약: `fetch_market_overview()`
- 판단 기록: `recent_decisions()`, `decisions_as_table_rows()`

즉 FastAPI는 기존 Python 로직을 호출해 JSON으로 전달하는 **얇은 adapter**로 만든다.

### 현재 React 화면과의 차이
- 화면 구조/스타일: 정상 표시 확인
- 가격/Score: 현재 mock → 실제 KIS/Score로 교체 필요
- Score History: 현재 미연결 → 실제 60일 일봉/히스토리 API 연결 필요
- 시장 요약: Streamlit 기능은 아직 React 미이식
- 판단 기록: React 미이식
- DART/시장모드/기회순위/사후검증: Main App 1차 연결 후 순차 이식

### 안전성 결정
현재 Oracle의 `frontend/`, `api/`, `data/decisions.jsonl`는 GitHub main의 검증된 기준본과 분리된 작업본이다. 따라서 **현재 단계에서는 GitHub main에 API 코드를 임의로 덮어쓰지 않는다.** Oracle 작업본의 실제 API/React 파일을 먼저 비교한 뒤, 검증된 변경만 기준본으로 반영한다.

### 다음 실제 작업
1. Oracle의 현재 `api/main.py`와 `frontend/src/App.jsx`를 실제 파일 기준으로 다시 확인한다.
2. 기존 Python 모듈을 그대로 호출하는 최소 API adapter를 만든다.
3. `/scores` → React 종목표/카드 연결.
4. `/prices` 또는 history API → 실제 60일 History 연결.
5. 공개 URL에서 실제 수치와 오류/호출량을 검증한다.
6. 검증 후 GitHub 기준본을 안전하게 확립한다.


## 2026-09-26 실제 구현 진행 결과

- `api/main.py`를 GitHub main에 추가했다. 기존 `src/market_data.py`, `src/kis_client.py`, `src/score_engine.py`, `src/market_overview.py`, `src/decision_log.py`를 호출하는 thin adapter 방식이다.
- 추가 API: `GET /scores`, `GET /prices/{symbol}/history?count=60`, `GET /market-overview`, `GET /decisions` (기존 `/`, `/health` 유지)
- `/scores`는 기존 6종목 수집 → 재무비율 보강 → 기존 `calculate_templeton_score()` 호출 순서로 구성했다.
- API 호출량을 줄이기 위해 scores/market-overview에 60초 메모리 캐시를 적용했다.
- `requirements.txt`에 FastAPI/Uvicorn 의존성을 추가했다.
- 기존 `src/`의 직접 import 구조를 보존하기 위해 API에서 `src`를 import path에 추가했다.
- **검증 제한:** 현재 Oracle의 `api/main.py`와 `frontend/`는 아직 GitHub main에 없는 별도 작업본이므로, 이번 세션에서는 실제 Oracle 서버에 새 API를 배포하거나 공개 URL에서 실데이터 응답을 확인할 수 없었다. 따라서 API 구현은 GitHub 기준본에 반영했지만 '실행 검증 완료'로 기록하지 않는다.
- React `App.jsx`도 Oracle 작업본에만 존재하는 상태이므로, 현재는 기존 화면 코드를 덮어쓰지 않았다. 다음 서버 접근/동기화 단계에서 실제 React 코드에 API 응답을 연결하고 공개 URL에서 검증한다.
- **판정:** API adapter 구현 PASS(코드 반영), 실행/실데이터 검증 OPEN.


## 2026-09-26 최신 진행 기준 — Oracle API 실데이터 연결 확인

- Oracle에서 FastAPI `/scores` 실행 검증 완료: `HTTP 200`, 응답 타입 `list`, 6개 종목, 첫 종목 `069500`, 첫 Score `48.8`.
- 초기 `/scores` 500 원인은 FastAPI 반환 타입 annotation이 실제 반환값과 불일치한 것(`dict[str, Any]` 선언 vs `list[dict[str, Any]]` 반환)이었음. Oracle에서 타입 선언을 `list[dict[str, Any]]`로 수정하고 재검증하여 해결.
- `/prices`에서도 KIS 실데이터와 기존 Score 계산 결과가 정상 반환됨. 따라서 KIS → 기존 Python 계산 → FastAPI 흐름은 실제 Oracle에서 동작하는 것으로 확인.
- React `frontend/src/App.jsx`에 `normalizeScoreRow()` adapter를 추가하여 실제 API 필드(`symbol`, `current_price`, `change_rate`, `low_52w`, `score.total/components`)를 기존 화면 데이터 구조로 변환하도록 수정.
- React의 `/scores` fetch도 기존 mock merge 방식에서 `setTickers(d.map(normalizeScoreRow))` 방식으로 변경됨.
- React 코드 수정 전 `frontend/src/App.jsx.before-real-scores` 백업을 생성함. API 타입 수정 전에도 `api/main.py.before-scores-type-fix` 백업을 생성함.
- **현재 미완료:** React 빌드 및 공개 `/templeton/` 화면에서 실제 점수가 표시되는지 검증하지 않음.
- **현재 주의:** `mockTickers`와 랜덤 `generateHistory()`는 아직 코드에 남아 있음. 따라서 Score History는 실제 데이터가 아니며, 실제 화면 검증 후 제거/대체 여부를 결정해야 함. mock-only 설명/수치가 실제 데이터와 섞이지 않도록 다음 단계에서 정리.
- Oracle의 `db/neon_client.py`에는 React 이식과 직접 관계없는 별도 변경이 있으므로, 원인/필요성이 확인되기 전에는 GitHub main에 덮어쓰지 않음.
- **다음 작업:** (1) `frontend`에서 `npm run build` 성공 확인 → (2) Caddy가 제공하는 공개 `/templeton/`에서 실제 API 점수/가격 표시 확인 → (3) 브라우저 오류 및 API 호출 검증 → (4) 랜덤 Score History 처리 → (5) 검증된 Oracle 변경만 GitHub 기준본으로 반영.
