# Templeton S — 현재 작업 상태

최종 갱신: 2026-09-27

## 현재 단계

**Phase 2 — 새 Snapshot + Collector 구축**

## 이번 단계에서 확인한 실제 상태

- GitHub main에는 기존 Streamlit/Oracle/React 코드가 함께 존재한다.
- 기존 src/main.py는 KIS → Score → 로컬 decision log 중심의 기존 실행 진입점이다.
- scripts/daily_collect.py는 존재하지만 오래된 모듈 참조와 random mock fallback이 있어 운영 수집에 사용하지 않는다.
- 기존 score_engine.py는 현재 Templeton Score v0.5 계산 기준으로 보존한다.
- 기존 ai_interpreter.py는 Groq + Llama 3.3 70B를 사용하고 있다.
- 기존 Neon은 prices_daily / templeton_scores / macro_daily 중심이다.

## 새 구조 구현 상태

작업 브랜치: rebuild/snapshot-pipeline

추가 완료:
- collector/snapshot.py — 단일 Snapshot 수집 경로
- collector/ai.py — provider/model 교체 가능한 AI 계층, 현재 Groq 기본
- collector/panic.py — 동일 Snapshot 기반 Panic Watch 상태 계산
- scripts/collect_snapshot.py — 새 collector 진입점
- Neon에 collection_runs / market_snapshots / snapshot_scores / ai_judgments / panic_watch_states 추가
- AI provider/model/version/prompt/input/output 기록 구조 추가
- Oracle용 09:30 / 17:00 systemd timer 템플릿 추가
- 기존 daily collector workflow는 운영 스케줄에서 제거하고 수동 검증용으로 전환
- snapshot pipeline compile CI 추가

## 운영 원칙

앱 실행 → 현재 시황/가격 조회만 수행

평일 09:30 / 17:00 KST →
KIS + FRED/시장 컨텍스트 → Snapshot → Score → AI → Panic Watch → Neon

현재 데이터와 가장 최근 정기 Snapshot 판단은 화면/API에서 별도로 표시한다.

## 아직 검증하지 않은 것

- GitHub CI 실제 성공
- 실제 KIS/FRED/Groq/Neon을 이용한 end-to-end Snapshot 생성
- Oracle에 새 collector를 설치/활성화
- 09:30 / 17:00 실제 자동 실행
- 새 FastAPI/React 연결

## 다음 작업

1. 새 collector CI/실행 검증
2. Neon end-to-end Snapshot 1회 생성 확인
3. FastAPI를 현재 데이터 + 최근 Snapshot 판단 조회 구조로 재작성
4. React 새 화면 구현
5. 통합 테스트 후 GitHub main 기준본 확정
6. Oracle 기존 실행체계를 새 코드로 교체
7. 09:30 / 17:00 자동수집 실제 검증

## 안전

- reset / force push / 대량 삭제 금지
- 기존 코드와 DB는 검증 전 폐기하지 않는다.
- 실제 코드/서버 상태를 문서보다 우선한다.
