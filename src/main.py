"""
템플턴S Phase 2 진입점
- KIS API로 6종목 현재가 수집
- Templeton Score v0.3 계산 (Value: PER/PBR, Pessimism: 시장 대비 상태)
- 콘솔 출력

사용법:
 1. config/.env 에 KIS_APP_KEY, KIS_APP_SECRET 설정
 2. cd src && python main.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# src를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import validate_config, LOG_LEVEL
from kis_client import KISClient
from market_data import fetch_all_prices
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL
from decision_log import log_decision

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("templeton_s")

SIGNAL_LABEL = {
    "individual": "개별 악재 가능성",
    "market_wide": "시장 전체 위험회피",
    "none": "신호 없음",
}


def main():
    print("=" * 56)
    print(" TEMPLETON S · Phase 2~3 · Score v0.5")
    print("=" * 56)

    try:
        validate_config()
    except ValueError as e:
        print(f"\n[설정 오류] {e}")
        print("config/.env.example 을 참고하여 config/.env 파일을 만들어 주세요.")
        sys.exit(1)

    client = KISClient()
    prices = fetch_all_prices(client)

    # 시장 벤치마크(KODEX 200) 찾기 — 실패 시 None (폴백 동작)
    market = next(
        (p for p in prices
         if p.get("symbol") == MARKET_BENCHMARK_SYMBOL and "error" not in p),
        None,
    )
    if market:
        print(f"\n시장 벤치마크 KODEX 200: {market.get('change_rate'):+.2f}%\n")
    else:
        print("\n[경고] 벤치마크(KODEX 200) 조회 실패 — Pessimism 폴백 모드\n")

    print("--- 관심 종목 스냅샷 + Templeton Score (v0.5) ---\n")
    for p in prices:
        if "error" in p:
            print(f"{p['name']:22s} ERROR: {p['error']}")
            continue

        score_result = calculate_templeton_score(p, market)
        try:
            log_decision(
                symbol=p.get("symbol", ""),
                name=p.get("name", ""),
                score_data=score_result,
                price=p.get("current_price"),
            )
        except Exception:
            pass
        drop = p.get("drop_from_52w_high")
        drop_str = f"52w고점대비 -{drop}%" if drop is not None else ""
        pi = score_result["pessimism_inputs"]
        signal = SIGNAL_LABEL.get(pi["signal"], pi["signal"])

        print(f"{p['name']:22s} {p.get('current_price'):>10}원 "
              f"{(p.get('change_rate') or 0):>+6.2f}% {drop_str}")
        print(f"  → Score {score_result['total']:5.1f} | {score_result['opinion']}")
        print(f"  components: {score_result['components']}")
        print(f"  비관신호   : {signal} "
              f"(종목 {pi['stock_change']}% vs 시장 {pi['market_change']}%)")
        print()

    print("Phase 2~3: Value ✅ · Pessimism ✅ · Risk ✅ · Quality ✅ · Growth ✅ · AI 해석 ✅")
    

if __name__ == "__main__":
    main()