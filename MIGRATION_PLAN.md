# Templeton S — 새 운영 구조 구축 계획

작성 기준: 2026-09-27

## 목표

기존 Streamlit의 기능을 기준으로 새 Collector/데이터 기록/판단/API/React 시스템을 만든 뒤 Oracle의 기존 실행체계를 새 코드로 교체한다.

## 단계

### Phase 1 — 기능/데이터 기준 확정
- Streamlit 기능을 기준 목록으로 확정
- 기존 Score 계산 로직은 보존
- 현재 데이터와 정기 Snapshot을 분리

### Phase 2 — 새 Snapshot + Collector
- 평일 09:30 / 17:00 KST
- KIS + FRED/매크로 + 시장 컨텍스트 수집
- Market Snapshot 생성
- Templeton Score 계산
- AI 판단 생성 및 provider/model/version/input/output 저장
- Panic Watch 상태 저장
- Neon 기록

### Phase 3 — FastAPI
- 현재 데이터 조회 API
- 최근 Snapshot/AI 판단 조회 API
- Snapshot/판단 기준시각과 현재시각을 구분

### Phase 4 — React
- 현재 시황/가격
- 최근 정기 Snapshot 판단
- 종목별 Score 및 구성요소
- 데이터 기준시각/연결상태

### Phase 5 — 통합 검증
- 동일 입력에 대한 Score 일치 확인
- Snapshot 불변성 확인
- 앱 실행이 Snapshot을 생성하지 않는지 확인
- AI 메타데이터 재현성 확인

### Phase 6 — GitHub 기준본 확정
- 검증된 새 구조를 main에 반영
- legacy collector를 운영 경로에서 제외

### Phase 7 — Oracle 교체
- 기존 실행체계를 새 collector/API/React로 교체
- systemd timer로 09:30 / 17:00 자동수집
- 24/7 API/React 운영
- 실제 자동수집 검증

## 금지

- 기존 src/main.py를 새 collector의 진입점으로 재사용하지 않는다.
- 기존 React를 새 화면의 기준으로 삼지 않는다.
- scripts/daily_collect.py를 운영 수집에 사용하지 않는다.
- reset / force push / 대량 삭제를 하지 않는다.
