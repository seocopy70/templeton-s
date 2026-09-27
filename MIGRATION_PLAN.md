# Templeton S — React 이식 및 Oracle 배포 계획

작성 기준: 2026-09-27

## 최종 목표

기존 Streamlit 기반 Templeton S의 핵심 기능을 기준으로 **새 React/Vite 버전을 새로 작성**하고 Oracle Cloud에서 안정적으로 운영한다.

> **중요:** 기존 Oracle React 구현을 계속 수정해서 완성하는 방식이 아니다. 기존 Oracle React는 이전 단계의 프로토타입/검증 결과이며, 최종본은 Streamlit을 기준으로 새로 작성한 React를 Oracle에 배포해 기존 배포본을 덮어쓴다.

## 확정된 구현 전략

### Source of Truth
- 기능과 화면 동작의 기준: 정상 작동하는 기존 **Streamlit**
- 데이터/API 동작의 검증 참고: 이미 확인된 FastAPI + KIS + Templeton Score
- 기존 Oracle React: **최종 구현의 출발점이 아님**

### 최종 흐름

```
Streamlit 기능/화면 분석
        ↓
새 React/Vite 코드 작성
        ↓
기존 검증 API 연결
        ↓
실데이터 검증
        ↓
GitHub에 새 React 기준본 확립
        ↓
Oracle build/deploy
        ↓
기존 Oracle React 배포본 덮어쓰기
```

### 기존 Oracle React의 취급
- 기존 Oracle React 코드를 기능 추가의 기반으로 삼지 않는다.
- 기존 코드가 이미 해결한 API 경로, 데이터 필드, public path, 배포 방식 등은 참고할 수 있다.
- 새 React가 완성되면 기존 React build/deployment는 새 build로 교체한다.
- 불필요한 기존 React 코드 보존/정리 작업 자체를 별도 목표로 삼지 않는다.

## Phase 0 — 현재 상태 확인 및 작업본 보호
- Oracle 작업본과 GitHub 상태 비교
- Git 상태/브랜치/remote 확인
- 현재 frontend, backend, Caddy, systemd 확인
- React 흰 화면 원인 확인
- 작업본 손실 없이 기준 상태 확보

**완료 조건:** 어느 작업본이 최신인지 확인하고 안전하게 수정할 수 있는 상태.

## Phase 1 — React 프로토타입/이전 작업 검증
- 과거 Oracle React 프로토타입의 현재 상태 확인
- public path, API path, 실데이터 연결 등 이미 검증된 부분 확인
- 최종본으로 계속 확장하지 않고 참고자료로 경계 확정

**완료 조건:** 기존 프로토타입에서 재사용할 수 있는 검증 정보와 버릴 구현을 구분함.

## Phase 2 — 새 React 버전 작성
정상 작동하는 Streamlit을 기준으로 새 React/Vite 화면을 새 구조로 작성한다.

최소한 다음을 표시한다.
- Templeton S 헤더 및 현재 상태
- 주요 종목 6개
- 종목별 score
- Value / Price / Pessimism / Quality / Growth / Risk
- 상태 표시
- 최근 가격 차트
- 종목 상세 정보
- 데이터 날짜 및 연결 상태

**완료 조건:** 기존 Streamlit을 열지 않아도 핵심 정보를 확인할 수 있는 새 React 버전이 동작함.

## Phase 3 — 실제 API 연결 및 검증
대상:
- `GET /templeton-api/`
- `GET /templeton-api/scores`
- `GET /templeton-api/prices?days=30`

원칙:
```
새 React → FastAPI → 기존 데이터/계산 로직
```

mock 데이터는 실제 API 연결이 안정화될 때까지 임시 fallback으로만 사용한다.

**완료 조건:** 새 React에서 실제 score와 price 데이터가 표시되고 API 오류 상태도 확인 가능함.

## Phase 4 — 기존 계산 로직 보존 확인
새 React 이식 때문에 기존 백엔드/DB/계산 로직이 불필요하게 변경되지 않았는지 확인한다.

중점:
- KODEX 200 (069500) benchmark
- score components
- valuation/price 관련 계산
- 데이터 날짜 기준
- no-lookahead 원칙

**완료 조건:** 새 React 화면의 핵심 수치가 기존 계산 결과와 일치함.

## Phase 5 — GitHub를 기준본으로 확립
- 새 React + API 연동 코드를 GitHub에 반영
- frontend/api/deploy 관련 기준 코드 확보
- clone 후 build 가능한 상태 확인

**완료 조건:** GitHub가 **새 React 버전의 기준 저장소**가 됨.

## Phase 6 — 새 React를 Oracle에 배포
기본 흐름:
```
Local VS Code
  ↓ git commit / push
GitHub
  ↓ git pull
Oracle
  ↓ 새 React npm run build
  ↓ 기존 React build를 새 build로 교체
  ↓ Caddy reload
```

**완료 조건:** Oracle의 기존 React 배포본이 새 React 버전으로 교체되고 public URL에서 검증됨.

## Phase 7 — 자동 배포 및 운영 개선
필요할 경우:
- GitHub Actions 자동 배포
- 데이터 freshness 표시
- score 변화
- 오류 표시
- 모바일 대응
- 운영 편의 개선

**자동화와 UI 개선은 새 React 기본 이식이 안정화된 뒤 진행한다.**

## 현재 우선순위

**P0:** 기존 프로토타입의 검증 범위 확정 → Streamlit 기능 분석 → 새 React 작성

**P1:** 새 React 실제 API 연결 → Streamlit 핵심 기능 재현 → GitHub 기준본 확립

**P2:** 새 React Oracle 배포/교체 → 자동화 → UI/운영 개선
