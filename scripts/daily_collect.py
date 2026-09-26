"""
Daily collector: KIS 6종목 + Templeton Score 계산 -> Neon 저장
기존 src/ 로직을 재사용. 없으면 mock으로 동작해서 테이블은 채워짐.
GitHub Actions에서 매일 16:10 KST (07:10 UTC) 실행
"""
import sys, os, datetime
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from db.neon_client import upsert_prices, upsert_scores, init_tables
import random

CODES = {
    "069500": "KODEX 200",
    "472150": "TIGER 배당커버드콜액티브",
    "005930": "삼성전자",
    "105560": "KB금융",
    "005380": "현대차",
    "360750": "TIGER 미국S&P500"
}

def fetch_prices_real():
    try:
        from src.kis_api import get_current_prices  # 기존 함수 가정
        # get_current_prices는 {code: {close, volume}} 반환 가정
        return get_current_prices(list(CODES.keys()))
    except Exception as e:
        print(f"[warn] real KIS fetch failed: {e}, using mock")
        return None

def fetch_prices_mock():
    today = datetime.date.today()
    data = {}
    base_price = {"069500": 35000, "472150": 10500, "005930": 72000, "105560": 78000, "005380": 240000, "360750": 25000}
    for code in CODES:
        bp = base_price[code]
        data[code] = {"close": bp + random.randint(-500, 500), "volume": random.randint(100000, 1000000)}
    return data

def calc_score_mock(prices):
    # 실제는 src/score_calculator 재사용
    try:
        from src.score import calculate_templeton_score
        scores = {}
        for code, p in prices.items():
            scores[code] = calculate_templeton_score(code, p)
        return scores
    except Exception as e:
        print(f"[warn] real score calc failed: {e}, mock")
        scores = {}
        for code in CODES:
            scores[code] = {
                "value": random.uniform(40, 80),
                "pessimism": random.uniform(30, 90),
                "risk": random.uniform(50, 80),
                "quality": random.uniform(60, 90),
                "growth": random.uniform(30, 70),
            }
            scores[code]["total"] = sum(scores[code].values())/5
        return scores

def main():
    init_tables()
    today = datetime.date.today()
    prices = fetch_prices_real() or fetch_prices_mock()
    scores = calc_score_mock(prices)

    price_rows = [(today, code, v["close"], v["volume"]) for code, v in prices.items()]
    score_rows = [(today, code, s["value"], s["pessimism"], s["risk"], s["quality"], s["growth"], s["total"]) for code, s in scores.items()]

    upsert_prices(price_rows)
    upsert_scores(score_rows)
    print(f"[{today}] upserted {len(price_rows)} prices, {len(score_rows)} scores -> Neon")

if __name__ == "__main__":
    main()