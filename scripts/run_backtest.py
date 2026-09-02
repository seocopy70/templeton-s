#!/usr/bin/env python3
"""
Templeton-S 백테스트 CLI (본 앱과 분리)

예:
  python scripts/run_backtest.py --as-of 2024-08-05
  python scripts/run_backtest.py --start 2024-07-01 --end 2024-08-15 --step 3
  python scripts/run_backtest.py --scenario crash_sample
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    p = argparse.ArgumentParser(description="Templeton-S Point-in-Time backtest")
    p.add_argument("--as-of", help="단일 판단일 YYYY-MM-DD")
    p.add_argument("--start", help="기간 시작")
    p.add_argument("--end", help="기간 끝")
    p.add_argument("--step", type=int, default=5, help="거래일 간격 (기본 5)")
    p.add_argument("--scenario", help="내장 시나리오: crash_sample|bear_sample|normal_sample")
    p.add_argument("--no-save", action="store_true", help="파일 저장 안 함")
    args = p.parse_args()

    from backtest.runner import run_as_of, run_range, run_scenario

    save = not args.no_save
    try:
        if args.scenario:
            run_scenario(args.scenario, save=save)
        elif args.as_of:
            run_as_of(args.as_of, save=save)
        elif args.start and args.end:
            run_range(args.start, args.end, step=args.step, save=save)
        else:
            p.print_help()
            print("\n예: python scripts/run_backtest.py --scenario crash_sample")
            return 2
    except Exception as e:
        print(f"[run_backtest] error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
