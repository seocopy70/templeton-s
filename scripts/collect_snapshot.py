#!/usr/bin/env python3
"""Run one production snapshot. Intended for Oracle systemd timer/cron."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow direct execution as: python scripts/collect_snapshot.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.snapshot import run_collection

parser = argparse.ArgumentParser()
parser.add_argument("--slot", choices=["09:30", "17:00"], default=None)
args = parser.parse_args()

snapshot_id = run_collection(slot=args.slot)
print(f"snapshot_id={snapshot_id}")
