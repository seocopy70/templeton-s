# Templeton-S 백테스트 설계 v0.1

> 본 앱과 엄격 분리 · Point-in-Time · 2026-09-02

## 폴더 구조

```
templeton_s/
├── src/                    # 본 앱 (수정하지 않음)
│   └── score_engine.py     # import only
├── backtest/
│   ├── __init__.py
│   ├── point_in_time.py    # as_of 기준 이용가능 데이터만
│   ├── snapshot.py         # Historical Snapshot
│   ├── forward_return.py   # 평가 전용 미래 수익
│   ├── performance.py      # 요약·레벨 통계
│   └── runner.py           # 단일일·기간·시나리오 실행
├── scripts/
│   └── run_backtest.py     # CLI 진입점
└── data/
    └── backtest/           # 스냅샷·결과 jsonl (gitignore 가능)
```

## 데이터 흐름

```
as_of (날짜)
  → Point-in-Time Engine (일봉 ≤ as_of)
  → Historical Snapshot
  → Score Engine (shared) + regime/panic/rank
  → Decision record
  → Forward Return Engine (일봉 > as_of)  ※ 판단에 미사용
  → Performance Analyzer
```

## v0.1 한계

- 재무 Point-in-Time DB 없음 → Value/Quality/Growth는 데이터 없을 때 중립
- KIS 일봉 조회 구간·횟수 제한 → 장기 구간은 청크 조회
- 공시 히스토리 미연동 시 panic 분류는 가격·regime 중심
- 거래비용·세금은 필드만 예약 (0 처리)

## CLI 예

```bash
# 단일일
python scripts/run_backtest.py --as-of 2024-08-05

# 기간 (매 N 거래일)
python scripts/run_backtest.py --start 2024-01-02 --end 2024-03-29 --step 5

# 폭락 시나리오 샘플 (내장 구간)
python scripts/run_backtest.py --scenario crash_sample
```
