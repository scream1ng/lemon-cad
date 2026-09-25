#!/usr/bin/env python3
"""Every base-seated upright must be crossed by a perpendicular member (shop rule: no lone ribs).

A crossing is a spec joint between two seated uprights whose planes are perpendicular. Cross-halving
joints (with `xy`) must also have both slots cut into the outlines. A plate may carry
`cross_support_exception: "<reason>"` instead; that is unknown pending engineering review, never pass.
"""
from __future__ import annotations

import argparse

import numpy as np
from shapely.geometry import Point, Polygon

from fixture_common import load_spec, local_s, write_json


def slot_cut(d, j, side):
    """True when the plate outline is open at the slot centre for this side of a cross-halving joint."""
    s, h = local_s(d, j["xy"]), j["lap_height_mm"]
    z = h / 4 if j[f"{side}_slot"] == "bottom" else 3 * h / 4
    return not Polygon(d["outer"], d.get("holes", [])).contains(Point(s, z))


def audit(spec):
    by = {d["name"]: d for d in spec["plates"]}
    uprights = [d for d in spec["plates"] if d.get("seat")]
    names = {d["name"] for d in uprights}
    crossed = {n: [] for n in names}
    bad_joints = []
    for j in spec.get("joints", []):
        a, b = j.get("a"), j.get("b")
        if a not in names or b not in names:
            continue  # cap tabs and other non-upright joints do not cross-support
        if abs(float(np.dot(by[a]["w"], by[b]["w"]))) > 0.05:
            continue
        if "xy" in j and not all(slot_cut(by[n], j, side) for n, side in ((a, "a"), (b, "b"))):
            bad_joints.append({"a": a, "b": b, "xy": j["xy"], "reason": "cross-halving slot not cut into both outlines"})
            continue
        crossed[a].append(b)
        crossed[b].append(a)
    rows = []
    for d in uprights:
        n, reason = d["name"], d.get("cross_support_exception")
        status = "pass" if crossed[n] else "unknown" if reason else "fail"
        rows.append({"plate": n, "crossed_by": sorted(set(crossed[n])), "exception": reason, "status": status})
    statuses = [r["status"] for r in rows] + ["fail"] * len(bad_joints)
    return {"status": "fail" if "fail" in statuses else "unknown" if "unknown" in statuses else "pass",
            "plates": rows, "bad_joints": bad_joints,
            "scope": "joint topology and slot presence only; stiffness and dry-fit squareness remain rib_construction evidence",
            "next_action": None if "fail" not in statuses else
            "Add a perpendicular cross-halving member for each lone upright, or record cross_support_exception with a reason."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec")
    ap.add_argument("out")
    a = ap.parse_args()
    r = audit(load_spec(a.spec))
    write_json(a.out, r)
    for row in r["plates"]:
        print(row["plate"], row["status"], ",".join(row["crossed_by"]) or "-")


if __name__ == "__main__":
    main()
