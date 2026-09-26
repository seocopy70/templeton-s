# Templeton S 작업 지침

## 현재 작업 목적

기존 Streamlit을 기능적 기준으로 삼아 Templeton S의 새 운영 시스템을 구축하고 Oracle에서 새 코드로 교체한다.

핵심 흐름:

Streamlit 기능 기준 → 새 Collector → Market Snapshot → Score → AI Judgment → Panic Watch → Neon → FastAPI → React → GitHub 검증 → Oracle 배포

## 원칙

- 기존 Oracle src/main.py와 기존 React를 새 구조의 기준으로 삼지 않는다.
- 검증된 Templeton Score 계산 로직과 Streamlit의 기능은 보존한다.
- 기존 코드를 살릴지 고민하는 것보다 새 구조 구현을 우선한다.
- scripts/daily_collect.py는 random mock/오래된 모듈 참조 때문에 운영 수집에 사용하지 않는다.
- reset / force push / 대량 삭제 금지.
- 작은 단위로 구현하고 각 단계에서 실제 코드와 실행 상태를 검증한다.

## 데이터 동작

- Oracle은 24/7 실행한다.
- 평일 09:30 / 17:00 KST에 자동 수집한다.
- 수집 시 Snapshot → Score → AI 판단 → Panic Watch → Neon 저장.
- 앱 실행 시에는 현재 시황/가격을 조회해 표시하지만 새 Snapshot이나 AI 판단을 생성하지 않는다.
- 화면에는 현재 데이터의 기준 시각과 최근 정기 Snapshot의 판단 시각을 구분한다.
- 사후검증은 당시 Snapshot/판단을 변경하지 않고 별도 Outcome으로 기록한다.

## AI

현재 실제 연동은 Groq API + Llama 3.3 70B이다. Groq과 xAI Grok을 혼동하지 않는다.

신규 구조에서는 provider/model/version/input/output을 기록하고 provider를 교체 가능한 계층으로 둔다. 지금은 Groq을 유지하고, 데이터가 쌓인 뒤 동일 Snapshot에 여러 모델을 적용해 실제 Outcome으로 비교한다.

## 작업 진행

현재는 새 Snapshot/Collector의 최소 운영 경로를 먼저 완성한다. 이후 FastAPI/React, 통합 테스트, GitHub 기준본 확정, Oracle 교체 및 실제 09:30/17:00 검증 순으로 진행한다.
