#!/usr/bin/env python3
"""Minimum in-plane material width (MIN10) screening.

1. Named sections: contact fingers (depth samples behind each contact), tab necks, cross-joint
   slot side ligaments and slot end bridges.
2. Edge-pair bridges: every nonadjacent cut-edge pair whose shortest connector enters material
   from both edges and stays inside the profile.
Sampling can prove a failure; a pass is screening, not a width certification.
"""
from __future__ import annotations

import argparse
import itertools

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points

from fixture_common import load_spec, local_s, poly, write_json


def _segments(g):
    if g.geom_type == "LineString":
        return [g]
    if hasattr(g, "geoms"):
        return [s for x in g.geoms for s in _segments(x)]
    return []


def cut_section(p, point, axis):
    point, axis = np.array(point, float), np.array(axis, float) / np.linalg.norm(axis)
    cut = p.intersection(LineString([point - axis * 1000, point + axis * 1000]))
    return [(s.length, [list(s.coords[0]), list(s.coords[-1])]) for s in _segments(cut) if s.distance(Point(point)) < 1e-5]


def named_sections(spec, tabs):
    by = {d["name"]: d for d in spec["plates"]}
    polys = {n: poly(d) for n, d in by.items()}
    rows = []
    for c in spec["contacts"]:
        if not c.get("rib"):
            continue
        d = by[c["rib"]]
        o, U, V = (np.array(d[k]) for k in ("origin", "u", "v"))
        p, n = np.array(c["contact"]) - o, np.array(c["normal"],float)
        q, nn = np.array([p @ U, p @ V]), np.array([n @ U, n @ V])
        nn /= np.linalg.norm(nn)
        tan = np.array([-nn[1], nn[0]])
        samples = []
        for depth in (.25, .5, 1, 2, 5, 10):
            s = cut_section(polys[d["name"]], q - nn * depth, tan)
            if s:
                width, line = min(s)
                samples.append({"depth_mm": depth, "width_mm": width, "line_local": line})
        assert samples, c["name"]
        rows.append({"feature": "contact_finger", "id": c["name"], "plate": d["name"], **min(samples, key=lambda s: s["width_mm"])})
    for i, t in enumerate(tabs, 1):
        s = cut_section(polys[t["plate"]], [t["local_s"], -t["engagement_mm"] / 2], [1, 0])
        assert s, t
        width, line = min(s)
        rows.append({"feature": "tab_neck", "id": "TAB%02d" % i, "plate": t["plate"], "width_mm": width, "line_local": line})
    # Cross-halving joints only; cap tab joints carry no lap section and are screened as edge pairs.
    for i, j in enumerate([j for j in spec.get("joints", []) if "xy" in j], 1):
        for side in ("a", "b"):
            d = by[j[side]]
            pl = polys[d["name"]]
            s, h, w = local_s(d, j["xy"]), j["lap_height_mm"], j["slot_width_mm"]
            bottom = j[f"{side}_slot"] == "bottom"
            lo, hi = (.25, h / 2 - .25) if bottom else (h / 2 + .25, h - .25)
            for sign in (-1, 1):
                samples = [{"width_mm": wd, "line_local": ln, "height_mm": float(z)}
                           for z in np.linspace(lo, hi, 5) for wd, ln in cut_section(pl, [s + sign * (w / 2 + .01), float(z)], [1, 0])]
                if samples:
                    rows.append({"feature": "slot_side_ligament", "id": "J%02d-%s-%s" % (i, side, "L" if sign < 0 else "R"),
                                 "plate": d["name"], **min(samples, key=lambda r: r["width_mm"])})
            sec = cut_section(pl, [s, h / 2 + (.2 if bottom else -.2)], [0, 1])
            if sec:
                width, line = min(sec)
                rows.append({"feature": "slot_end_bridge", "id": "J%02d-%s-END" % (i, side), "plate": d["name"], "width_mm": width, "line_local": line})
    return rows


def edge_pair_minimum(d):
    p = orient(poly(d), sign=1)
    edges = []
    for rid, ring in enumerate([p.exterior] + list(p.interiors)):
        coords = list(ring.coords)
        N = len(coords) - 1
        for i, (a, b) in enumerate(zip(coords, coords[1:])):
            u = np.array(b) - np.array(a)
            if np.linalg.norm(u) < 1e-6:
                continue
            edges.append((rid, i, N, LineString([a, b]), np.array([-u[1], u[0]]) / np.linalg.norm(u)))
    best = None
    for a, b in itertools.combinations(edges, 2):
        if a[0] == b[0] and (abs(a[1] - b[1]) == 1 or abs(a[1] - b[1]) == a[2] - 1):
            continue
        pa, pb = nearest_points(a[3], b[3])
        width = pa.distance(pb)
        if width < 1e-5 or (best and width >= best["width_mm"]):
            continue
        v = (np.array(pb.coords[0]) - np.array(pa.coords[0])) / width
        if v @ a[4] < .01 or (-v) @ b[4] < .01:
            continue
        line = LineString([pa, pb])
        if not p.buffer(1e-7).covers(line) or not all(p.contains(line.interpolate(t, normalized=True)) for t in (.1, .25, .5, .75, .9)):
            continue
        best = {"plate": d["name"], "width_mm": width, "line_local": [list(pa.coords[0]), list(pb.coords[0])]}
    return best


def audit(spec, tabs, edge_plates=None):
    limit = spec.get("min_width_mm", 10.0)
    eps = 1e-4
    rows = named_sections(spec, tabs)
    cats = {}
    from clamp_mount import min_width_for
    for r in rows:
        r["limit_mm"] = min_width_for(spec, r["plate"])
        r["status"] = "fail" if r["width_mm"] < r["limit_mm"] - eps else "pass"
        c = cats.setdefault(r["feature"], {"checked": 0, "failed": 0, "minimum_mm": 1e9})
        c["checked"] += 1
        c["failed"] += r["status"] == "fail"
        c["minimum_mm"] = min(c["minimum_mm"], r["width_mm"])
    names = edge_plates if edge_plates is not None else [d["name"] for d in spec["plates"]]
    by = {d["name"]: d for d in spec["plates"]}
    edge = [m for m in (edge_pair_minimum(by[n]) for n in names) if m]
    edge_min = min((m["width_mm"] for m in edge), default=None)
    edge_fail = [m for m in edge if m["width_mm"] < min_width_for(spec, m["plate"]) - eps]
    for t in (9.99, 10.01):  # threshold self-check of the section method
        assert abs(cut_section(Polygon([(0, 0), (t, 0), (t, 20), (0, 20)]), [t / 2, 10], [1, 0])[0][0] - t) < 1e-9
    failed = sum(c["failed"] for c in cats.values()) + len(edge_fail)
    return {"limit_mm": limit, "categories": cats, "edge_pair": {"plates": names, "minimum_mm": edge_min, "failures": edge_fail, "per_plate": edge},
            "status": "fail" if failed else "pass", "scope": "sampled sections + edge-pair screening; not a width certification. Cross-joint sections cover joints with an xy crossing; cap tab joints are covered by the edge-pair screen only",
            "measurements": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", help="spec with final plates")
    ap.add_argument("tab_report", help="tabs_slots.py report")
    ap.add_argument("out")
    a = ap.parse_args()
    import json
    rep = audit(load_spec(a.spec), json.load(open(a.tab_report))["tabs"])
    write_json(a.out, rep)
    print(rep["status"], rep["categories"], rep["edge_pair"]["minimum_mm"])


if __name__ == "__main__":
    main()
