"""Score v0.3 검증 — 실행: python diag.py"""
from kis_client import KISClient
from market_data import fetch_all_prices
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL

client = KISClient()
prices = fetch_all_prices(client)

market = next((p for p in prices
               if p.get("symbol") == MARKET_BENCHMARK_SYMBOL and "error" not in p), None)
print(f"벤치마크 KODEX 200: {market['change_rate']:+.2f}%\n" if market else "벤치마크 없음(폴백)\n")

print(f"{'종목':<16}{'등락률':>8}{'상대':>7}{'비관':>7}{'신호':>12}{'총점':>7}")
print("-" * 62)
for p in prices:
    if "error" in p:
        print(f"{p['name']:<16} ERROR")
        continue
    s = calculate_templeton_score(p, market)
    pi = s["pessimism_inputs"]
    rel = f"{pi['relative_drop']:+.2f}" if pi['relative_drop'] is not None else "—"
    print(f"{p['name']:<16}{(p.get('change_rate') or 0):>+7.2f}{rel:>7}"
          f"{s['components']['pessimism']:>7.1f}{pi['signal']:>12}{s['total']:>7.1f}")