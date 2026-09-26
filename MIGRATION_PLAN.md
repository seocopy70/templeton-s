# Templeton S — React 이식 및 Oracle 배포 계획

작성 기준: 2026-09-26

## 최종 목표

기존 Streamlit 기반 Templeton S의 핵심 기능을 React/Vite 화면으로 이식하고 Oracle Cloud에서 안정적으로 운영한다.

### Phase 0 — 현재 상태 확인 및 작업본 보호
- Oracle 작업본과 GitHub 상태 비교
- Git 상태/브랜치/remote 확인
- 현재 frontend, backend, Caddy, systemd 확인
- React 흰 화면 원인 확인
- 작업본 손실 없이 기준 상태 확보

**완료 조건:** 어느 작업본이 최신인지 확인하고 안전하게 수정할 수 있는 상태.

### Phase 1 — React 화면 정상화
- `/templeton/` 흰 화면 원인 확인
- React mount 및 정적 asset 확인
- 필요한 경우 최소 화면으로 원인 분리
- 정상 렌더링 확인

**완료 조건:** public URL에서 React 화면이 정상 표시됨.

### Phase 2 — Streamlit 핵심 화면 이식
최소한 다음을 표시한다.
- Templeton S 헤더 및 현재 상태
- 주요 종목 6개
- 종목별 score
- Value / Price / Pessimism / Quality / Growth / Risk
- 상태 표시
- 최근 가격 차트
- 종목 상세 정보
- 데이터 날짜 및 연결 상태

**완료 조건:** 기존 Streamlit을 열지 않아도 핵심 정보를 확인할 수 있음.

### Phase 3 — 실제 API 연결 및 검증
대상:
- `GET /templeton-api/`
- `GET /templeton-api/scores`
- `GET /templeton-api/prices?days=30`

원칙:
```
React → FastAPI → Neon Postgres
```

mock 데이터는 실제 API 연결이 안정화될 때까지 임시 fallback으로만 사용한다.

**완료 조건:** 실제 score와 price 데이터가 화면에 표시되고 API 오류 상태도 확인 가능함.

### Phase 4 — 기존 계산 로직 보존 확인
React 이식 때문에 기존 백엔드/DB/계산 로직이 불필요하게 변경되지 않았는지 확인한다.

중점:
- KODEX 200 (069500) benchmark
- score components
- valuation/price 관련 계산
- 데이터 날짜 기준
- no-lookahead 원칙

**완료 조건:** React 화면의 핵심 수치가 기존 계산 결과와 일치함.

### Phase 5 — GitHub를 기준본으로 확립
- 현재 검증된 작업본을 GitHub에 반영
- frontend/api/deploy 관련 기준 코드 확보
- clone 후 build 가능한 상태 확인

이 단계 전에는 Oracle 작업본을 확인하지 않은 상태에서 reset/force push를 하지 않는다.

**완료 조건:** GitHub가 Templeton 코드의 기준 저장소가 됨.

### Phase 6 — Oracle 배포 표준화
기본 흐름:
```
Local VS Code
  ↓ git commit / push
GitHub
  ↓ git pull
Oracle
  ↓ npm run build
  ↓ Caddy reload
```

수동 배포가 먼저 안정화된 뒤 필요하면 자동 배포를 검토한다.

### Phase 7 — 자동 배포 및 운영 개선
필요할 경우:
- GitHub Actions 자동 배포
- 데이터 freshness 표시
- score 변화
- 오류 표시
- 모바일 대응
- 운영 편의 개선

**자동화와 UI 개선은 기본 이식이 안정화된 뒤 진행한다.**

## 현재 우선순위

**P0:** 작업본 보호 → 흰 화면 해결 → 최소 React 화면

**P1:** 실제 API 연결 → Streamlit 핵심 기능 재현 → GitHub 기준본 확립

**P2:** 배포 표준화 → 자동화 → UI/운영 개선
