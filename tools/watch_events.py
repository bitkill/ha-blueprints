#!/usr/bin/env python3
"""Live-print Home Assistant state_changed + call_service events.

Usage:
    tools/watch_events.py                     # all state/service activity (30s)
    tools/watch_events.py -f bilresa          # filter to entities matching "bilresa"
    tools/watch_events.py --services light    # only light.* service calls
    tools/watch_events.py -t 120              # run for 120 seconds
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ha import HA  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-f", "--filter", default="",
                        help="Case-insensitive substring to match against entity_id")
    parser.add_argument("--services", default="",
                        help="Comma-separated service domains to show (e.g. light,automation). "
                             "Empty = all.")
    parser.add_argument("-t", "--seconds", type=float, default=30.0,
                        help="How long to listen (default 30s)")
    parser.add_argument("--no-state", action="store_true", help="Hide state_changed events")
    parser.add_argument("--no-service", action="store_true", help="Hide call_service events")
    args = parser.parse_args()

    needle = args.filter.lower()
    allowed_domains = {s.strip() for s in args.services.split(",") if s.strip()} or None

    with HA() as ha:
        ha.subscribe("state_changed")
        ha.subscribe("call_service")

        print(f"listening {args.seconds}s — filter={args.filter!r} services={allowed_domains}")
        t0 = time.time()
        for event in ha.events(timeout=args.seconds):
            if time.time() - t0 >= args.seconds:
                break
            et = event.get("event_type")
            d = event.get("data", {})
            ts = time.time() - t0
            if et == "state_changed" and not args.no_state:
                eid = d.get("entity_id", "")
                if needle and needle not in eid.lower():
                    continue
                ns = d.get("new_state") or {}
                os_ = d.get("old_state") or {}
                attrs = ns.get("attributes", {}) or {}
                extra = ""
                if "event_type" in attrs:
                    extra = f"  event_type={attrs['event_type']}"
                print(f"[{ts:6.2f}s] 🔘 {eid}  {os_.get('state')}→{ns.get('state')}{extra}")
            elif et == "call_service" and not args.no_service:
                dom = d.get("domain", "")
                if allowed_domains and dom not in allowed_domains:
                    continue
                svc = d.get("service", "")
                sd = d.get("service_data", {})
                if needle:
                    # Filter by target entity_id if present
                    target_ids = sd.get("entity_id") or d.get("target", {}).get("entity_id") or ""
                    if isinstance(target_ids, list):
                        target_ids = " ".join(target_ids)
                    if needle not in str(target_ids).lower():
                        continue
                print(f"[{ts:6.2f}s] 📞 {dom}.{svc}  {sd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
