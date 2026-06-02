#!/usr/bin/env python3
"""Look up entity IDs by friendly name, area, or domain.

Usage:
    tools/entity_ids.py "sofa"                       # search by name (case-insensitive substring)
    tools/entity_ids.py --domain light               # all lights
    tools/entity_ids.py --area Kitchen               # all entities in Kitchen area
    tools/entity_ids.py --area Kitchen --domain light  # combine filters
    tools/entity_ids.py --available                  # exclude unavailable entities
    tools/entity_ids.py                              # list everything
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ha import HA  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", nargs="?", default="",
                        help="Case-insensitive substring to match against friendly name or entity_id")
    parser.add_argument("--domain", "-d", default="",
                        help="Filter by domain (e.g. light, switch, climate)")
    parser.add_argument("--area", "-a", default="",
                        help="Filter by area name (case-insensitive substring)")
    parser.add_argument("--available", action="store_true",
                        help="Exclude entities whose state is 'unavailable'")
    args = parser.parse_args()

    needle = args.name.lower()
    domain_filter = args.domain.lower()
    area_filter = args.area.lower()

    with HA() as ha:
        states = ha.rpc({"type": "get_states"})
        entities = ha.rpc({"type": "config/entity_registry/list"})
        devices = ha.rpc({"type": "config/device_registry/list"})
        areas = ha.rpc({"type": "config/area_registry/list"})

    area_name_by_id = {a["area_id"]: a["name"] for a in areas}
    device_area_by_id = {d["id"]: d.get("area_id") for d in devices}
    entity_area = {}
    for e in entities:
        area_id = e.get("area_id") or device_area_by_id.get(e.get("device_id") or "")
        entity_area[e["entity_id"]] = area_name_by_id.get(area_id or "", "")

    state_by_id = {s["entity_id"]: s["state"] for s in states}

    rows = []
    for s in states:
        eid = s["entity_id"]
        domain = eid.split(".")[0]
        friendly = s["attributes"].get("friendly_name", "")
        area = entity_area.get(eid, "")
        state = s["state"]

        if domain_filter and domain != domain_filter:
            continue
        if area_filter and area_filter not in area.lower():
            continue
        if needle and needle not in friendly.lower() and needle not in eid.lower():
            continue
        if args.available and state == "unavailable":
            continue

        rows.append((eid, friendly, area, state))

    rows.sort(key=lambda r: (r[2].lower(), r[0]))

    if not rows:
        print("(no matches)")
        return 0

    col_w = max(len(r[0]) for r in rows)
    name_w = max(len(r[1]) for r in rows)
    area_w = max(len(r[2]) for r in rows) if any(r[2] for r in rows) else 0

    for eid, friendly, area, state in rows:
        area_col = f"  [{area}]" if area_w else ""
        print(f"{eid:{col_w}}  {friendly:{name_w}}{area_col}  {state}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
