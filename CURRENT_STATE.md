# Templeton S — 현재 작업 상태

최종 갱신: 2026-09-26

## 현재 단계

**Phase 0 — 현재 상태 확인 및 작업본 보호**

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
