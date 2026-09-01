"""
KIS Open API 클라이언트 (Phase 2 STEP 2)

- Access Token 발급 (POST — tokenP는 POST 전용)
- 국내주식/ETF 현재가 조회 (+ 밸류에이션 지표: PER / PBR / EPS)
- 일봉 조회 (변동성/모멘텀 계산용)
- 일시적 5xx/네트워크 오류 지수 백오프 재시도
- 비-JSON 응답 방어: 빈 본문/HTML을 명확한 메시지의 에러로 변환
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import requests

from config import (
    BASE_URL,
    KIS_APP_KEY,
    KIS_APP_SECRET,
    KIS_ENV,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.8


class KISClient:
    def __init__(self):
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self.base_url = BASE_URL
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0

    # -------------------------------------------------------------
    # 내부 유틸: 재시도 / 상세 에러 / JSON 방어
    # -------------------------------------------------------------

    def _request_with_retry(
        self,
        url: str,
        method: str = "GET",
        **kwargs,
    ) -> requests.Response:
        """
        5xx/네트워크 오류는 지수 백오프로 재시도하고,
        4xx는 즉시 반환한다.

        method: "GET"(기본) 또는 "POST"
        tokenP는 반드시 POST여야 한다.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if method.upper() == "POST":
                    resp = requests.post(
                        url,
                        timeout=10,
                        **kwargs,
                    )
                else:
                    resp = requests.get(
                        url,
                        timeout=10,
                        **kwargs,
                    )

                if resp.status_code < 500:
                    return resp

                last_exc = requests.HTTPError(
                    f"{resp.status_code} Server Error",
                    response=resp,
                )

            except (requests.ConnectionError, requests.Timeout) as e:
                last_exc = e

            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))

                logger.warning(
                    "KIS API 일시 오류(%s) — %.1f초 후 재시도 (%d/%d)",
                    last_exc,
                    delay,
                    attempt,
                    MAX_RETRIES,
                )

                time.sleep(delay)

        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _raise_detail(resp: requests.Response) -> None:
        """
        HTTP 오류 시 KIS 응답 본문의 실제 원인(msg1/msg_cd)을 추출한다.
        """
        try:
            resp.raise_for_status()

        except requests.HTTPError as e:
            detail = ""

            try:
                body = resp.json()

                msg = (
                    body.get("msg1")
                    or body.get("error_description")
                    or ""
                )

                code = (
                    body.get("msg_cd")
                    or body.get("error_code")
                    or ""
                )

                if msg or code:
                    detail = f" — KIS 응답: [{code}] {msg}"

            except Exception:
                pass

            raise RuntimeError(
                f"KIS HTTP {resp.status_code} 오류{detail}"
            ) from e

    @staticmethod
    def _parse_json(
        resp: requests.Response,
        context: str,
    ) -> dict:
        """
        비-JSON 응답 방어.

        빈 본문/HTML 에러페이지를 만나면
        'Expecting value' 대신 원인을 알 수 있는 에러를 던진다.
        """
        try:
            return resp.json()

        except ValueError:
            preview = (resp.text or "").strip()[:200]

            raise RuntimeError(
                f"KIS {context} 응답이 JSON이 아님 "
                f"(HTTP {resp.status_code}) — 본문: {preview!r}"
            ) from None

    # -------------------------------------------------------------
    # API
    # -------------------------------------------------------------

    def _get_token(self) -> str:
        """
        Access Token 발급 또는 캐시된 토큰 반환.

        tokenP는 POST 전용!
        """
        now = time.time()

        if (
            self.access_token
            and now < self.token_expires_at - 60
        ):
            return self.access_token

        url = f"{self.base_url}/oauth2/tokenP"

        headers = {
            "content-type": "application/json",
        }

        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        resp = self._request_with_retry(
            url,
            method="POST",
            headers=headers,
            json=body,
        )

        self._raise_detail(resp)

        data = self._parse_json(
            resp,
            "토큰 발급",
        )

        self.access_token = data["access_token"]

        expires_in = int(
            data.get("expires_in", 86400)
        )

        self.token_expires_at = now + expires_in

        logger.info(
            "KIS access token 발급 완료 (env=%s)",
            KIS_ENV,
        )

        return self.access_token

    def get_current_price(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        국내주식/ETF 현재가 조회.

        TR: FHKST01010100

        - per/pbr: 0 이하·빈값 → None
        - eps: 적자면 음수 그대로 유지
        """
        token = self._get_token()

        url = (
            f"{self.base_url}"
            "/uapi/domestic-stock/v1/quotations/"
            "inquire-price"
        )

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100",
            "custtype": "P",
        }

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
        }

        resp = self._request_with_retry(
            url,
            headers=headers,
            params=params,
        )

        self._raise_detail(resp)

        data = self._parse_json(
            resp,
            f"현재가 조회({symbol})",
        )

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS API 오류: {data.get('msg1')} "
                f"(rt_cd={data.get('rt_cd')})"
            )

        out = data.get("output", {})

        return {
            "symbol": symbol,
            "current_price": self._to_float(
                out.get("stck_prpr")
            ),
            "change": self._to_float(
                out.get("prdy_vrss")
            ),
            "change_rate": self._to_float(
                out.get("prdy_ctrt")
            ),
            "volume": self._to_int(
                out.get("acml_vol")
            ),
            "open": self._to_float(
                out.get("stck_oprc")
            ),
            "high": self._to_float(
                out.get("stck_hgpr")
            ),
            "low": self._to_float(
                out.get("stck_lwpr")
            ),
            "prev_close": self._to_float(
                out.get("stck_sdpr")
            ),
            "high_52w": self._to_float(
                out.get("stck_dryy_hgpr")
                or out.get("w52_hgpr")
            ),
            "low_52w": self._to_float(
                out.get("stck_dryy_lwpr")
                or out.get("w52_lwpr")
            ),
            "per": self._to_valuation(
                out.get("per")
            ),
            "pbr": self._to_valuation(
                out.get("pbr")
            ),
            "eps": self._to_float(
                out.get("eps")
            ),
            "raw": out,
        }

    def get_financial_ratios(
        self,
        symbol: str,
        annual: bool = True,
    ) -> dict[str, Any]:
        """
        국내주식 재무비율 조회.

        KIS TR: FHKST66430300

        연간 재무비율을 기본으로 사용한다.
        데이터가 없으면 예외를 발생시켜 호출 측에서
        중립 처리할 수 있도록 한다.
        """
        token = self._get_token()

        url = (
            f"{self.base_url}"
            "/uapi/domestic-stock/v1/finance/financial-ratio"
        )

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST66430300",
            "custtype": "P",
        }

        params = {
            "FID_DIV_CLS_CODE": "0" if annual else "1",
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": symbol,
        }

        resp = self._request_with_retry(
            url,
            headers=headers,
            params=params,
        )

        self._raise_detail(resp)

        data = self._parse_json(
            resp,
            f"재무비율 조회({symbol})",
        )

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS API 오류: {data.get('msg1')} "
                f"(rt_cd={data.get('rt_cd')})"
            )

        rows = data.get("output") or []

        if not rows:
            raise RuntimeError(
                f"재무비율 데이터 없음: {symbol}"
            )

        rows = sorted(
            rows,
            key=lambda row: str(
                row.get("stac_yymm", "")
            ),
            reverse=True,
        )

        latest = rows[0]

        return {
            "financial_period": latest.get("stac_yymm"),
            "revenue_growth": self._to_float(
                latest.get("grs")
            ),
            "operating_profit_growth": self._to_float(
                latest.get("bsop_prfi_inrt")
            ),
            "net_income_growth": self._to_float(
                latest.get("ntin_inrt")
            ),
            "roe": self._to_float(
                latest.get("roe_val")
            ),
            "eps": self._to_float(
                latest.get("eps")
            ),
            "bps": self._to_float(
                latest.get("bps")
            ),
            "retained_ratio": self._to_float(
                latest.get("rsrv_rate")
            ),
            "debt_ratio": self._to_float(
                latest.get("lblt_rate")
            ),
        }

    def get_daily_closes(
        self,
        symbol: str,
        count: int = 60,
    ) -> list[float]:
        """
        일봉 종가 목록 (최신 → 과거 순).

        변동성/모멘텀 계산용.

        TR:
            FHKST03010100

        KIS API는 조회 시작일/종료일을 요구하므로
        최근 약 180일 범위를 조회한 뒤
        최신 count개만 사용한다.
        """

        token = self._get_token()

        url = (
            f"{self.base_url}"
            "/uapi/domestic-stock/v1/quotations/"
            "inquire-daily-itemchartprice"
        )

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST03010100",
            "custtype": "P",
        }

        # ---------------------------------------------------------
        # KIS API 필수 날짜 파라미터
        # ---------------------------------------------------------

        end_date = datetime.now().date()

        start_date = (
            end_date - timedelta(days=180)
        )

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date.strftime(
                "%Y%m%d"
            ),
            "FID_INPUT_DATE_2": end_date.strftime(
                "%Y%m%d"
            ),
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        }

        resp = self._request_with_retry(
            url,
            headers=headers,
            params=params,
        )

        self._raise_detail(resp)

        data = self._parse_json(
            resp,
            f"일봉 조회({symbol})",
        )

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS API 오류: {data.get('msg1')} "
                f"(rt_cd={data.get('rt_cd')})"
            )

        rows = data.get("output2") or []

        # 날짜 기준 최신→과거 정렬 (KIS 응답 순서에 의존하지 않음)
        def _row_date(row):
            d = row.get("stck_bsop_date") or row.get("date") or ""
            return str(d)

        rows = sorted(rows, key=_row_date, reverse=True)

        closes: list[float] = []
        for row in rows:
            c = self._to_float(row.get("stck_clpr"))
            if c is not None and c > 0:
                closes.append(c)

        return closes[:count]

    def get_daily_bars(
        self,
        symbol: str,
        count: int = 120,
    ) -> list[dict[str, Any]]:
        """
        일봉 (날짜 + 종가) 목록. 최신 → 과거 순.

        Returns:
            [{"date": "YYYY-MM-DD", "close": float}, ...]
        Phase 6 사후 검증·과거 시뮬레이션용.
        """
        token = self._get_token()

        url = (
            f"{self.base_url}"
            "/uapi/domestic-stock/v1/quotations/"
            "inquire-daily-itemchartprice"
        )

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST03010100",
            "custtype": "P",
        }

        end_date = datetime.now().date()
        # 넉넉히 조회 (거래일 기준 count보다 여유)
        start_date = end_date - timedelta(days=max(300, count * 2))

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        }

        resp = self._request_with_retry(
            url,
            headers=headers,
            params=params,
        )
        self._raise_detail(resp)
        data = self._parse_json(resp, f"일봉바 조회({symbol})")

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS API 오류: {data.get('msg1')} "
                f"(rt_cd={data.get('rt_cd')})"
            )

        rows = data.get("output2") or []

        def _row_date(row):
            d = row.get("stck_bsop_date") or row.get("date") or ""
            return str(d)

        rows = sorted(rows, key=_row_date, reverse=True)

        bars: list[dict[str, Any]] = []
        for row in rows:
            raw = _row_date(row)
            if len(raw) != 8 or not raw.isdigit():
                continue
            c = self._to_float(row.get("stck_clpr"))
            if c is None or c <= 0:
                continue
            bars.append({
                "date": f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}",
                "close": c,
            })

        return bars[:count]

    # -------------------------------------------------------------
    # 변환 유틸
    # -------------------------------------------------------------

    @staticmethod
    def _to_float(
        v,
    ) -> Optional[float]:
        if v is None or v == "":
            return None

        try:
            return float(v)

        except (TypeError, ValueError):
            return None

    @classmethod
    def _to_valuation(
        cls,
        v,
    ) -> Optional[float]:
        """
        PER/PBR 전용.

        0 이하·빈값은
        '비교 불가' → None.

        EPS는 이 함수를 사용하지 않는다.
        """
        f = cls._to_float(v)

        if f is None or f <= 0:
            return None

        return f

    @staticmethod
    def _to_int(
        v,
    ) -> Optional[int]:
        if v is None or v == "":
            return None

        try:
            return int(float(v))

        except (TypeError, ValueError):
            return None