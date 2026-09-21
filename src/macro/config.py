"""FRED macro series configuration."""
from __future__ import annotations
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES = {
    "DGS10": {"name": "US 10-Year Treasury Yield", "unit": "percent", "frequency": "daily"},
    "DFF": {"name": "Effective Federal Funds Rate", "unit": "percent", "frequency": "daily"},
    "DTWEXBGS": {"name": "Nominal Broad US Dollar Index", "unit": "index", "frequency": "daily"},
    "DEXKOUS": {"name": "South Korean Won to 1 US Dollar", "unit": "KRW_per_USD", "frequency": "daily"},
    "SP500": {"name": "S&P 500", "unit": "index", "frequency": "daily"},
    "NASDAQCOM": {"name": "NASDAQ Composite", "unit": "index", "frequency": "daily"},
}
