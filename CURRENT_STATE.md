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

## 기록 원칙

이 파일에는 작업 연속성에 필요한 최소한의 내용만 기록한다.

각 주요 단계가 끝날 때 다음만 갱신한다.
- 현재 단계
- 완료한 작업
- 현재 문제
- 다음 작업

문서 자체를 만드는 것이 목적이 아니다.
