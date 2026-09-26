#!/usr/bin/env python3
"""Run one production snapshot. Intended for Oracle systemd timer/cron."""
from __future__ import annotations
import argparse
from collector.snapshot import run_collection

parser = argparse.ArgumentParser()
parser.add_argument("--slot", choices=["09:30", "17:00"], default=None)
args = parser.parse_args()

snapshot_id = run_collection(slot=args.slot)
print(f"snapshot_id={snapshot_id}")
