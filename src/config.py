"""템플턴S 설정 로드"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 기준 .env 로드
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "config" / ".env")
load_dotenv(ROOT / ".env")  # 루트에 있을 경우도 지원

KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ENV = os.getenv("KIS_ENV", "paper").lower()  # paper | real
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "")
KIS_ACCOUNT_PRODUCT = os.getenv("KIS_ACCOUNT_PRODUCT", "01")

POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "10"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DART_API_KEY = os.getenv("DART_API_KEY", "")
NEWS_ENABLED = os.getenv("NEWS_ENABLED", "false").lower() in ("1", "true", "yes")

# Base URL
if KIS_ENV == "real":
    BASE_URL = "https://openapi.koreainvestment.com:9443"
else:
    BASE_URL = "https://openapivts.koreainvestment.com:29443"

# 관심종목 12종목
# 기존 6종목은 유지하고, 시장 흐름 파악을 위해 6종목을 추가한다.
# 섹터 분류/섹터별 점수는 추후 별도 작업에서 추가한다.
SYMBOLS = {
    "069500": "KODEX 200",
    "472150": "TIGER 배당커버드콜액티브",
    "005930": "삼성전자",
    "105560": "KB금융",
    "005380": "현대차",
    "360750": "TIGER 미국S&P500",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "012450": "한화에어로스페이스",
    "034020": "두산에너빌리티",
    "207940": "삼성바이오로직스",
    "005490": "POSCO홀딩스",
}

def validate_config():
    missing = []
    if not KIS_APP_KEY:
        missing.append("KIS_APP_KEY")
    if not KIS_APP_SECRET:
        missing.append("KIS_APP_SECRET")
    if missing:
        raise ValueError(f"필수 환경변수가 없습니다: {', '.join(missing)}. config/.env 를 확인하세요.")
