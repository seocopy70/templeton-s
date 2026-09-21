# Templeton S - Macro Data Layer v0.1

## 목적
FRED 기반 시장·거시 데이터 수집 기반을 기존 Templeton Score와 분리한다.

v0.1 범위는 수집·저장·검증뿐이다. Macro Risk Score나 기존 Templeton Score에는 아직 연결하지 않는다.

## 수집 series
- DGS10: 미국 10년 국채금리
- DFF: 미국 유효 연방기금금리
- DTWEXBGS: 미국 명목 광의 달러지수
- DEXKOUS: 원/달러 환율
- SP500: S&P 500
- NASDAQCOM: Nasdaq Composite

## 원칙
- 관측일과 수집시각을 분리한다.
- series별 원천 CSV를 보존한다.
- 처리 데이터는 macro_daily.csv로 피벗한다.
- FRED의 비수치 관측값은 원본에 보존하고 분석용 변환에서 제외한다.
- 중복 관측일은 최신 수집값으로 대체한다.
- 한 series 실패가 다른 series 수집을 막지 않는다.
- API key는 코드에 저장하지 않고 GitHub Actions Secret FRED_API_KEY에서 주입한다.
- 기존 데이터가 있으면 최근 7일을 겹쳐 받아 수정된 관측값을 반영한다. 최초 실행만 전체 이력을 받는다.
- 이 v0.1 데이터는 아직 과거 백테스트나 Macro Score 계산에 사용하지 않는다.

## 실행
로컬에서는 FRED_API_KEY 환경변수를 설정한 뒤 scripts/collect_macro.py를 실행한다.
GitHub Actions에서는 평일 09:00 UTC 자동 실행 및 수동 실행을 지원한다.

## 중요한 한계: revision / vintage
FRED의 현재 API 관측값은 과거 관측치가 수정될 수 있다. 현재 저장 구조의 retrieved_at은 "언제 가져왔는가"를 기록할 뿐, 각 과거 시점에서 시장 참가자가 실제로 이용할 수 있었던 값을 복원하는 완전한 vintage 데이터는 아니다.

따라서:
1. 현재 구조는 **수집 데이터셋**으로만 취급한다.
2. 과거 시점의 Macro 신호를 백테스트하려면 FRED realtime/vintage 기능을 이용한 별도 vintage 저장층이 필요하다.
3. 그 vintage 층이 검증되기 전에는 Macro 데이터를 Templeton Score나 백테스트에 연결하지 않는다.

## 다음 Gate
최소 7–14일 수집 후 결측·지연, 단위·스케일, 이상치, publication/revision 특성을 검증한다.
그 다음 vintage 설계와 Macro Stress/Risk 신호를 별도 검증하고, 기존 Score와의 연결 여부를 판단한다.
