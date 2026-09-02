"""
Templeton-S Backtest (본 앱과 분리)

Point-in-Time 재현 → Score Engine(공유) → Forward 평가
"""
from .runner import run_as_of, run_range, run_scenario

__all__ = ["run_as_of", "run_range", "run_scenario"]
