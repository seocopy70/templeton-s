# Templeton S — 현재 작업 상태

최종 갱신: 2026-09-27

## 현재 단계

**Phase 2 — 새 React 버전 작성 단계 (1차 구현 완료, 빌드 검증 대기)**

## 가장 중요한 작업 기준

### 기존 Oracle React를 수정하는 것이 아니다

현재 Templeton S React 작업의 기준은 다음과 같이 확정한다.

- **기능/화면 Source of Truth:** 정상 작동하는 기존 Streamlit
- **최종 React:** Streamlit을 기준으로 **새로 작성**
- **기존 Oracle React:** 이전에 만든 프로토타입/검증용 구현. 최종 구현의 출발점이 아님.
- **Oracle의 역할:** 새 React가 완성·검증된 뒤 최종 build를 배포하는 대상 서버.
- **최종 배포:** 새 React build로 기존 Oracle React 배포본을 덮어쓴다.

따라서 앞으로 작업 지시에서 “React 이식”, “React 수정”, “Oracle React 작업”이라고 표현하더라도 별도 지시가 없는 한 **기존 Oracle React를 계속 패치하는 의미로 해석하지 않는다.**

기본 작업 흐름:

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
Oracle 새 build 배포
   ↓
기존 Oracle React 덮어쓰기
```

### 지금까지 완료된 것은 무엇인가

이전 작업에서 다음은 이미 완료/검증된 상태다.

1. Oracle React 프로토타입 작성 및 흰 화면 문제 해결
2. FastAPI adapter 작성
3. Oracle FastAPI `/scores` 실데이터 검증
4. 공개 `/templeton/` 및 `/templeton-api/scores` 검증
5. 실제 KIS 데이터 + Templeton Score가 React/API 경로에서 전달되는 것 확인
6. React의 일부 API 연동 및 가격 History 연결 방향 확인

이 작업들은 **최종 새 React를 완성한 것이 아니라, 새 React를 만들 때 사용할 API/데이터/배포 정보를 검증한 이전 단계**다.

따라서 기존 Oracle React를 계속 고쳐서 최종본으로 만드는 작업은 하지 않는다.

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

KIS 연동은 현재 단계에서 **정상 동작으로 간주하고 종료**한다.

- Streamlit에서 KIS 데이터 수신 확인
- Oracle에서 KIS 데이터 수집 확인
- 기존 KISClient를 사용하는 실제 데이터 경로 확인
- GitHub Actions의 과거 인증 문제는 새 수집 경로가 실제 Oracle에서 실패할 때 다시 본다.

따라서 지금은 KIS 인증/Secret 문제를 추가로 파고들지 않는다.

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

## 새 React 1차 구현 — 2026-09-27

Streamlit `app.py`를 기능/화면 기준으로 삼아 기존 Oracle React와 분리된 새 Vite/React 구현을 `frontend/`에 작성했다.

구성:
- `frontend/App.jsx`: 현재 상태, 6종목, Templeton Score 6요소, 상세 입력값, 가격 History, 최근 판단, 데이터 상태
- `frontend/styles.css`: 반응형 대시보드 UI
- `frontend/main.jsx`, `index.html`, `vite.config.js`: 독립 Vite 실행 구조
- 실제 FastAPI `/scores`, `/prices/{symbol}/history`, `/market-overview`, `/decisions` 연결
- mock 주식 데이터 없음. API 실패 시 오류 상태를 표시
- `/templeton/` public path를 새 Vite build의 base로 설정
- 향후 AI/DART 상세 화면은 해당 데이터를 제공하는 API가 준비된 뒤 실제 데이터로 추가한다. 가짜 결과를 만들지 않는다.

빌드 검증:
- `.github/workflows/frontend-build.yml`을 추가하여 Node 22 + `npm install` + `npm run build` CI 검증 경로를 만들었다.
- 현재 실행 환경에서는 외부 DNS가 차단되어 npm 패키지 설치를 통한 로컬 build 실행은 완료하지 못했다. 따라서 **코드 작성 완료와 CI 검증 경로 확보** 상태이며, 실제 build 성공 판정은 GitHub Actions 또는 Oracle에서 확인한다.

## 현재 알려진 문제

기존 문서와 실제 작업본 사이에 차이가 있을 수 있으므로 실제 코드/서버 상태를 우선 확인한다.

## 다음 작업

1. GitHub Actions 또는 Oracle에서 새 `frontend/`의 실제 `npm run build` 성공을 확인한다.
2. 새 React를 Oracle의 별도 경로/임시 build로 올려 실제 API와 브라우저에서 검증한다. 기존 Oracle React는 아직 덮어쓰지 않는다.
3. Streamlit과 새 React의 핵심 수치/화면을 대조하여 누락 기능을 보완한다.
4. 검증이 끝난 새 React build를 Oracle의 기존 React 배포본에 덮어쓴다.
5. 이후 자동 수집/AI 판단/운영 개선을 단계적으로 연결한다.

## 기록 원칙

이 파일에는 작업 연속성에 필요한 최소한의 내용만 기록한다. 주요 단계가 끝날 때 현재 단계/완료/문제/다음 작업만 갱신한다.
