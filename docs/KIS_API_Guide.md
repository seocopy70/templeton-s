# KIS Open API 연동 가이드 (Phase 1)
**템플턴S · 한국투자증권 Open API**

공식 포털: https://apiportal.koreainvestment.com/

## 1. 사전 준비

1. 한국투자증권 계좌 보유
2. https://apiportal.koreainvestment.com/ 접속 → KIS Developers 서비스 신청
3. App Key / App Secret 발급 (실전 + 모의 각각 가능)
4. 계좌번호(앞 8자리) + 상품코드(뒤 2자리, 보통 01) 확인

**보안**
- App Key / App Secret은 절대 코드에 하드코딩하지 말 것
- `.env` 파일 또는 환경변수 / 시크릿 매니저 사용
- `.env`는 gitignore에 반드시 추가

## 2. 환경 구분

| 구분 | REST Base URL | WebSocket |
|------|---------------|-----------|
| 실전 | https://openapi.koreainvestment.com:9443 | ws://ops.koreainvestment.com:21000 |
| 모의 | https://openapivts.koreainvestment.com:29443 | ws://ops.koreainvestment.com:31000 |

Phase 1은 **모의투자**부터 시작하는 것을 강력 권장.

## 3. 인증 (Access Token)

```
POST /oauth2/tokenP
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "appkey": "발급받은_APP_KEY",
  "appsecret": "발급받은_APP_SECRET"
}
```

응답의 `access_token`을 이후 모든 REST 호출 헤더에 사용.  
유효기간 약 24시간 (일반 개인 기준). 만료 전 재발급.

WebSocket용 접속키는 별도 `/oauth2/Approval` 사용.

## 4. Phase 1 핵심 API — 주식 현재가

```
GET /uapi/domestic-stock/v1/quotations/inquire-price
Headers:
  content-type: application/json; charset=utf-8
  authorization: Bearer {access_token}
  appkey: {APP_KEY}
  appsecret: {APP_SECRET}
  tr_id: FHKST01010100
  custtype: P   # 개인

Query:
  FID_COND_MRKT_DIV_CODE = J   # 주식
  FID_INPUT_ISCD = 005930      # 종목코드
```

주요 응답 필드 (output):
- stck_prpr : 현재가
- prdy_vrss : 전일대비
- prdy_ctrt : 등락률
- acml_vol : 누적거래량
- stck_oprc / stck_hgpr / stck_lwpr : 시/고/저
- stck_sdpr : 전일종가 등

ETF도 동일 TR로 조회 가능 (국내상장 ETF).

## 5. 템플턴S 6종목 코드

| 종목 | 코드 |
|------|------|
| KODEX 200 | 069500 |
| TIGER 배당커버드콜액티브 | 472150 |
| 삼성전자 | 005930 |
| KB금융 | 105560 |
| 현대차 | 005380 |
| TIGER 미국S&P500 | 360750 |

## 6. Phase 1 성공 기준
앱(또는 스크립트)을 실행하면 위 6개 종목의 현재가·등락률이 실제 시장 움직임에 따라 갱신되는 것을 확인.

## 7. 주의사항
- API 호출 제한(초당/분당) 존재 → 폴링 간격 조절 (예: 5~10초)
- 장 마감 후에는 전일 종가 기준 데이터
- 해외주식/실시간 WebSocket은 Phase 1 이후 확장
- 자동매매 기능은 v1에서 제외 (마스터 문서 원칙)

## 8. 참고 자료
- 공식 API 포털: https://apiportal.koreainvestment.com/
- 공식 GitHub 예제: https://github.com/koreainvestment/open-trading-api
- Wikidocs (한글 가이드): 검색 “한국투자증권 OpenAPI”
