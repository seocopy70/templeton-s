# 일일 판단 기록 운영 (Daily Log) v0.1

> GitHub Actions로 장후 스냅샷 적재 · 레포에 영속 저장

## 스케줄

| 항목 | 값 |
|------|-----|
| 한국 장 마감 | 15:30 KST |
| 실행 시각 | **17:30 KST** (마감 약 2시간 후) |
| cron (UTC) | `30 8 * * 1-5` (월~금) |
| 수동 실행 | Actions → Daily decision log → Run workflow |

## 동작

1. `scripts/daily_log.py` 실행
2. 6종목 시세·Score·시장모드·공황분류·기회순위 계산
3. **당일(KST) 아직 없는 종목만** `data/decisions.jsonl`에 append
4. 변경 시 봇 커밋 후 `main` push

AI 해석은 호출하지 않는다 (비용·안정성). UI에서 열 때와 동일 Score 규칙만 사용.

## GitHub Secrets (필수)

Repository → Settings → Secrets and variables → Actions

| Secret | 필수 | 설명 |
|--------|------|------|
| `KIS_APP_KEY` | ✓ | KIS 앱키 |
| `KIS_APP_SECRET` | ✓ | KIS 시크릿 |
| `KIS_ENV` | 권장 | `paper` 또는 `real` (없으면 paper) |
| `DART_API_KEY` | 선택 | 급락 시 공시 보강 |
| `GROQ_API_KEY` | 불필요 | 일일 스크립트에서 미사용 |

## 로컬 수동 실행

```bash
# config/.env 에 키 설정 후
python scripts/daily_log.py
```

## 파일

- `scripts/daily_log.py`
- `.github/workflows/daily_log.yml`
- `data/decisions.jsonl` (gitignore 예외로 추적)

## 주의

- KIS **IP 허용**: Actions runner IP는 가변 → paper 모드는 상대적으로 완화, real은 포털 IP 정책 확인
- 당일 중복 방지: 같은 날짜(KST) 기록이 있으면 해당 종목 스킵
- Streamlit Cloud 로컬 디스크와 별개 — **소스 of truth는 깃 레포 jsonl**
