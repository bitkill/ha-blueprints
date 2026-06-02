#!/usr/bin/env python3
"""Live-print ZHA button/device events, optionally filtered by device IEEE.

Useful for discovering the exact event shape (command, args) before writing
an automation trigger.

Usage:
    tools/zha_listen.py                                   # all ZHA events (15s)
    tools/zha_listen.py --ieee 54:ef:44:10:00:76:df:30   # single device
    tools/zha_listen.py --ieee 54:ef:44:10:00:76:df:30 --ieee 54:ef:44:10:00:7b:f5:db
    tools/zha_listen.py -t 30                             # run for 30 seconds
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ha import HA  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ieee", action="append", default=[],
                        help="Filter to this device IEEE address (repeatable for multiple devices)")
    parser.add_argument("-t", "--seconds", type=float, default=15.0,
                        help="How long to listen (default 15s)")
    args = parser.parse_args()

    ieee_filter = {addr.lower() for addr in args.ieee}

    with HA() as ha:
        ha.subscribe("zha_event")
        print(f"listening {args.seconds}s"
              + (f" — ieee={args.ieee}" if ieee_filter else " — all devices")
              + " (press a button now)")
        t0 = time.time()
        count = 0
        for event in ha.events(timeout=args.seconds):
            if time.time() - t0 >= args.seconds:
                break
            data = event.get("data", {})
            ieee = data.get("device_ieee", "").lower()
            if ieee_filter and ieee not in ieee_filter:
                continue
            ts = time.time() - t0
            print(f"\n[{ts:.2f}s]")
            print(json.dumps(data, indent=2))
            count += 1

    print(f"\n({count} event{'s' if count != 1 else ''} captured)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
