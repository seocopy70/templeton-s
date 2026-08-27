"""
시장 데이터 수집 · 6종목 현재가 + 일봉 지표 (Phase 2 STEP 2)
- 현재가/등락률/52주고점대비 (기존)
- 연율화 변동성, 20일 모멘텀 (신규 — 일봉 60개 기반)
- 일봉 조회 실패 시에도 가격 데이터는 정상 반환 (Risk는 중립 처리)
"""
from __future__ import annotations

import logging
import math
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Optional

from config import SYMBOLS, POLL_INTERVAL_SEC
from kis_client import KISClient

logger = logging.getLogger(__name__)

CANDLE_COUNT = 60  # 변동성 계산에 사용할 일봉 수 (최대 100)


def compute_volatility(closes: list[float]) -> Optional[float]:
    """
    연율화 변동성(%) = 일수익률 표준편차(표본) × √252 × 100
    closes는 최신 → 과거 순. 신뢰하려면 최소 11개 이상의 봉이 필요.
    """
    if len(closes) < 11:
        return None
    returns = [
        (closes[i] - closes[i + 1]) / closes[i + 1]
        for i in range(len(closes) - 1)
    ]
    daily_std = statistics.stdev(returns)
    return round(daily_std * math.sqrt(252) * 100, 2)


def compute_momentum(closes: list[float], days: int = 20) -> Optional[float]:
    """최근 N거래일 수익률(%) — 향후 상대강도/추세 지표의 재료"""
    if len(closes) <= days:
        return None
    return round((closes[0] / closes[days] - 1) * 100, 2)


def fetch_all_prices(client: KISClient) -> list[dict[str, Any]]:
    """6개 종목 현재가 + 일봉 지표 일괄 조회"""
    results = []
    for symbol, name in SYMBOLS.items():
        try:
            data = client.get_current_price(symbol)
            data["name"] = name
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
            # 52주 고점 대비 하락률 계산
            if data.get("current_price") and data.get("high_52w") and data["high_52w"] > 0:
                data["drop_from_52w_high"] = round(
                    (data["high_52w"] - data["current_price"]) / data["high_52w"] * 100, 2
                )
            else:
                data["drop_from_52w_high"] = None

            # --- 일봉 지표 (Phase 2 STEP 2) ---
            # 실패해도 종목 전체를 실패 처리하지 않는다 — Risk만 중립 폴백.
            try:
                closes = client.get_daily_closes(symbol, CANDLE_COUNT)
                data["volatility_annual"] = compute_volatility(closes)
                data["momentum_20d"] = compute_momentum(closes)
                data["candle_days"] = len(closes)
            except Exception as e:
                logger.warning("일봉 조회 실패 %s (%s): %s — Risk 중립 처리", name, symbol, e)
                data["volatility_annual"] = None
                data["momentum_20d"] = None
                data["candle_days"] = 0

            results.append(data)
            logger.info(
                "%s (%s) %s원 %.2f%% 변동성=%s",
                name,
                symbol,
                data.get("current_price"),
                data.get("change_rate") or 0,
                data.get("volatility_annual"),
            )
        except Exception as e:
            logger.error("조회 실패 %s (%s): %s", name, symbol, e)
            results.append({"symbol": symbol, "name": name, "error": str(e)})
        # API 호출 제한 고려 (간단한 간격)
        time.sleep(0.3)
    return results


def run_polling_loop(max_iterations: int | None = None):
    """
    주기적으로 6종목 가격을 가져와 출력.
    max_iterations=None 이면 무한 루프.
    """
    client = KISClient()
    iteration = 0
    while True:
        iteration += 1
        logger.info("===== Poll #%d =====", iteration)
        prices = fetch_all_prices(client)
        print("\n--- Templeton S · Market Snapshot ---")
        for p in prices:
            if "error" in p:
                print(f"  {p['name']}: ERROR {p['error']}")
            else:
                drop = p.get("drop_from_52w_high")
                drop_str = f" (52w 고점대비 -{drop}%)" if drop is not None else ""
                vol = p.get("volatility_annual")
                vol_str = f" [변동성 {vol:.1f}%]" if vol is not None else ""
                print(
                    f"  {p['name']:20s} {p.get('current_price'):>10}원 "
                    f"{p.get('change_rate') or 0:>+6.2f}%{drop_str}{vol_str}"
                )
        print("-------------------------------------\n")

        if max_iterations is not None and iteration >= max_iterations:
            break
        time.sleep(POLL_INTERVAL_SEC)