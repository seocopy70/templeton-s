# Templeton S (템플턴S)
개인용 AI 투자 코치 · 존 템플턴 가치투자 원칙 기반

## 현재 상태
- Phase 0 완료: 투자철학 / Rules v0.1 / 6종목 확정 / Score 설계 / 데이터 스키마
- Phase 1 완료: KIS Open API 연동 + 6종목 현재가 수집
- Phase 2 완료: Templeton Score v0.5 (Value/Pessimism/Risk/Quality/Growth)
- Phase 3 진행: AI 해석 + 판단 기록 UI
- Phase 4 초안: DART 공시 설계·골격·대시보드 섹션
- Streamlit 웹 대시보드

## 확정 6종목
| 코드 | 종목 |
|------|------|
| 069500 | KODEX 200 |
| 472150 | TIGER 배당커버드콜액티브 |
| 005930 | 삼성전자 |
| 105560 | KB금융 |
| 005380 | 현대차 |
| 360750 | TIGER 미국S&P500 |

## 빠른 시작 (Phase 1)

1. 한국투자증권 KIS Developers에서 App Key / App Secret 발급  
   https://apiportal.koreainvestment.com/

2. 환경 설정
```bash
cd templeton_s
cp config/.env.example config/.env
# config/.env 에 실제 키 입력
```

3. 의존성 설치
```bash
pip install -r requirements.txt
```

4. 터미널 실행
```bash
cd src
py main.py
```

5. **웹 대시보드 실행** (권장)
```bash
pip install -r requirements.txt
streamlit run app.py
```
브라우저가 자동으로 열리며 6종목 현황 + Score를 확인할 수 있습니다.

성공 시 6개 종목의 현재가와 초안 Score가 출력됩니다.

## 문서
- `docs/Templeton_Investment_Rules_v0.1.md`
- `docs/Data_Schema_v0.1.md`
- `docs/Templeton_Score_Calculation_v0.1.md`
- `docs/KIS_API_Guide.md`
- `docs/Phase4_News_Disclosure_Design_v0.1.md`

## 원칙 요약
- AI는 참모, 최종 결정은 사용자
- 가격과 가치를 분리
- 프로그램이 계산, AI가 해석
- 자동매매는 초기 범위에서 제외
