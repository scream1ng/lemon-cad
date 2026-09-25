#!/usr/bin/env python3
"""Two integral tabs per base-seated plate, matching slots in the seat plate.

Feet may widen only below spec.tab_slot.foot_height_mm; profile above that height is preserved.
Tab positions are searched per part-number family (all instances share a profile), then a
backtracking pass picks one option per family so slots keep min_bridge_mm apart and widened
footprints do not collide. Pinned positions (tab_slot.pinned) skip the search.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import pickle
from pathlib import Path

import numpy as np
import shapely
from shapely import area, distance, intersection
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from fixture_common import clean, load_spec, local_s, poly, set_profile, world_xy, write_json

DEFAULTS = {
    "width_mm": 12.0, "engagement_mm": 4.8, "slot_clearance_mm": 0.2, "foot_height_mm": 12.0,
    "min_bridge_mm": 10.4, "min_tab_spacing_mm": 24.0, "wide_plate_mm": 90.0, "wide_spacing_ratio": 0.45,
    "search_step_mm": 2.0, "max_tab_beyond_foot_mm": 48.0, "search_bound": 30000, "pinned": {},
}


def params(spec):
    return {**DEFAULTS, **spec.get("tab_slot", {})}


def bottom_cuts(d, joints):
    """Bottom-open cross-joint slots in plate d (plate-local boxes)."""
    cuts = []
    for j in joints:
        for side in ("a", "b"):
            if j[side] == d["name"] and j[f"{side}_slot"] == "bottom":
                s, hw = local_s(d, j["xy"]), j["slot_width_mm"] / 2
                cuts.append(box(s - hw, 0, s + hw, j["lap_height_mm"] / 2 + .1))
    return unary_union(cuts)


def footprint(d, p, P, T):
    section = p.intersection(LineString([(-1000, P["foot_height_mm"] / 2), (1000, P["foot_height_mm"] / 2)]))
    segs = list(section.geoms) if hasattr(section, "geoms") else [section]
    return unary_union([world_xy(d, box(s.bounds[0], -T / 2, s.bounds[2], T / 2)) for s in segs if s.length > 1e-6])


def slot_world(d, s, P, T):
    hl, hw = (P["width_mm"] + P["slot_clearance_mm"]) / 2, (T + P["slot_clearance_mm"]) / 2
    return world_xy(d, box(s - hl, -hw, s + hl, hw))


def assert_seat_frame(seat):
    """Slots are computed in world XY; the seat plate frame must coincide with world XY."""
    o, u, v = (np.array(seat[k]) for k in ("origin", "u", "v"))
    assert np.allclose(o[:2], 0) and np.allclose(u, [1, 0, 0]) and np.allclose(v, [0, 1, 0]), "seat plate frame must be world XY"


def foot_option(d, fam, a, b, base_poly, cuts, oldobs, P, T, min_width, slots=None):
    """Return (added_area, new_profile, slots, footprints) or None if the pair is invalid.

    slots: optional {(plate name, s): slot polygon} computed once per family search."""
    p = poly(d)
    lo, _, hi, _ = p.bounds
    ends = [x for x, y in d["outer"] if abs(y) < 1e-6]
    fl, fh = min(ends), max(ends)
    hw = P["width_mm"] / 2
    if b - a < P["min_tab_spacing_mm"] or (hi - lo > P["wide_plate_mm"] and b - a < P["wide_spacing_ratio"] * (hi - lo)):
        return None
    qs = [slots[f["name"], s] if slots else slot_world(f, s, P, T) for s in (a, b) for f in fam]
    if any(x.distance(y) < P["min_bridge_mm"] for x, y in itertools.combinations(qs, 2)):
        return None
    foot = box(min(fl, a - hw), 0, max(fh, b + hw), P["foot_height_mm"]).difference(cuts)
    pnew = p.union(foot)
    if pnew.geom_type != "Polygon":
        return None
    if not all(pnew.buffer(1e-7).covers(box(s - hw, 0, s + hw, min_width)) for s in (a, b)):
        return None
    fs = [footprint(f, pnew, P, T) for f in fam]
    if any(x.intersection(oldobs).area > 1e-5 for x in fs):
        return None
    if any(x.intersection(y).area > 1e-5 for x, y in itertools.combinations(fs, 2)):
        return None
    return pnew.difference(p).area, pnew, qs, fs


def family_options(fam, base_poly, joints, oldobs, P, T, min_width):
    d = fam[0]
    p = poly(d)
    ends = [x for x, y in d["outer"] if abs(y) < 1e-6]
    fl, fh = min(ends), max(ends)
    lo, _, hi, _ = p.bounds
    cuts = bottom_cuts(d, joints)
    hw, ext = P["width_mm"] / 2, P["max_tab_beyond_foot_mm"]
    one, slots = [], {}
    for s in np.arange(math.ceil(fl - ext), math.floor(fh + ext) + .01, P["search_step_mm"]):
        qs = [slot_world(f, s, P, T) for f in fam]
        if any(not base_poly.covers(q) or q.distance(base_poly.boundary) < P["min_bridge_mm"] for q in qs):
            continue
        if box(s - hw, 0, s + hw, P["foot_height_mm"]).intersection(cuts).area > 1e-4:
            continue
        one.append(float(s))
        slots.update({(f["name"], float(s)): q for f, q in zip(fam, qs)})
    vals = []
    for a, b in itertools.combinations(one, 2):
        opt = foot_option(d, fam, a, b, base_poly, cuts, oldobs, P, T, min_width, slots)
        if opt:
            added, pnew, qs, fs = opt
            vals.append(((added, -(b - a), abs((a + b - fl - fh) / 2)), [a, b], pnew, MultiPolygon(qs), unary_union(fs)))
    vals.sort(key=lambda x: x[0])
    return vals


CACHE_KEEP = 64                                 # newest entries kept (about 0.6 MB each)
CODE = hashlib.sha256(b"".join(Path(__file__).with_name(n).read_bytes() for n in ("tabs_slots.py", "fixture_common.py"))).hexdigest()


def cached_family_options(cache_dir, fam, base_poly, joints, oldobs, P, T, min_width):
    """family_options, cached on disk by every input it reads plus this code's hash; output is identical."""
    if cache_dir is None:
        return family_options(fam, base_poly, joints, oldobs, P, T, min_width)
    key = hashlib.sha256(json.dumps({
        "code": CODE, "shapely": shapely.__version__, "fam": [{k: f.get(k) for k in ("name", "outer", "holes", "origin", "u", "v", "w")} for f in fam],
        "joints": joints, "base": base_poly.wkb_hex, "oldobs": oldobs.wkb_hex, "P": P, "T": T, "min_width": min_width,
    }, sort_keys=True, default=str).encode()).hexdigest()
    path = Path(cache_dir) / f"{key}.pickle"
    try:
        vals = pickle.loads(path.read_bytes()); path.touch()
        return vals
    except (OSError, pickle.PickleError, EOFError, AttributeError, ValueError):
        pass
    vals = family_options(fam, base_poly, joints, oldobs, P, T, min_width)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp"); tmp.write_bytes(pickle.dumps(vals)); tmp.replace(path)
        for old in sorted(path.parent.glob("*.pickle"), key=lambda f: f.stat().st_mtime)[:-CACHE_KEEP]:
            old.unlink(missing_ok=True)
    except OSError:
        pass
    return vals


def lap_foot_check(seated, joints, P):
    """A bottom slot taller than its cut (lap/2) is refilled by the foot box up to foot_height."""
    for d in seated:
        p = poly(d)
        for j in joints:
            for side in ("a", "b"):
                if j[side] != d["name"] or j[f"{side}_slot"] != "bottom" or j["lap_height_mm"] / 2 + .1 >= P["foot_height_mm"]:
                    continue
                s, z, e = local_s(d, j["xy"]), P["foot_height_mm"] - .25, j["slot_width_mm"] / 2 + .5
                if not p.contains(Point(s, z)) and p.contains(Point(s - e, z)) and p.contains(Point(s + e, z)):
                    raise ValueError(f"{d['name']} x {j['a' if side == 'b' else 'b']}: lap_height_mm {j['lap_height_mm']:g} < "
                                     f"2 x foot_height_mm {P['foot_height_mm']:g}; feet would fill the slot. "
                                     f"Use lap_height_mm >= {2 * P['foot_height_mm']:g}")


def why_no_options(fam, base_poly, joints, oldobs, P, T, min_width):
    """Re-walk family_options and count what rejected each tab position and pair."""
    d = fam[0]
    ends = [x for x, y in d["outer"] if abs(y) < 1e-6]
    fl, fh = min(ends), max(ends)
    cuts, hw, ext = bottom_cuts(d, joints), P["width_mm"] / 2, P["max_tab_beyond_foot_mm"]
    edge, cut, one, best = 0, 0, [], 0.0
    for s in np.arange(math.ceil(fl - ext), math.floor(fh + ext) + .01, P["search_step_mm"]):
        qs = [slot_world(f, s, P, T) for f in fam]
        if any(not base_poly.covers(q) or q.distance(base_poly.boundary) < P["min_bridge_mm"] for q in qs):
            edge += 1
            best = max(best, min(q.distance(base_poly.boundary) if base_poly.covers(q) else 0.0 for q in qs))
        elif box(s - hw, 0, s + hw, P["foot_height_mm"]).intersection(cuts).area > 1e-4:
            cut += 1
        else:
            one.append(float(s))
    pairs = sum(1 for a, b in itertools.combinations(one, 2)
                if not foot_option(d, fam, a, b, base_poly, cuts, oldobs, P, T, min_width))
    grow = (f" (best {best:.1f} of {P['min_bridge_mm']:g} min_bridge_mm: grow the seat {P['min_bridge_mm'] - best:.1f} mm)"
            if edge else "")
    return (f"{len(one)} usable tab positions; {edge} too close to the seat edge{grow}, "
            f"{cut} on a bottom slot, {pairs} pairs rejected by spacing/bridge/foot overlap")


def solve(options, P):
    slotg = {k: np.array([v[3] for v in vs], dtype=object) for k, vs in options.items()}
    footg = {k: np.array([v[4] for v in vs], dtype=object) for k, vs in options.items()}
    bridge, chosen, visits = P["min_bridge_mm"], {}, [0]

    def rec(remaining):
        visits[0] += 1
        if visits[0] > P["search_bound"]:
            raise RuntimeError("tab search bound reached")
        if not remaining:
            return True
        pn = min(remaining, key=lambda k: len(remaining[k]))
        for i in remaining[pn]:
            others = {}
            for key, idx in remaining.items():
                if key == pn:
                    continue
                idx = idx[distance(slotg[key][idx], slotg[pn][i]) >= bridge - 1e-7]
                if len(idx):
                    idx = idx[area(intersection(footg[key][idx], footg[pn][i])) < 1e-5]
                if not len(idx):
                    break
                others[key] = idx
            else:
                chosen[pn] = int(i)
                if rec(others):
                    return True
        return False

    assert rec({k: np.arange(len(v)) for k, v in options.items()}), "no compatible tab layout"
    return chosen, visits[0]


def design(spec, log=print):
    """Mutates spec['plates'] in place; returns the tab/slot report."""
    P, T = params(spec), spec["thickness_mm"]
    min_width = spec.get("min_width_mm", 10.0)
    plates = spec["plates"]
    by = {d["name"]: d for d in plates}
    joints = spec.get("joints", [])
    seated = [d for d in plates if d.get("seat")]
    seats = {d["seat"] for d in seated}
    assert len(seats) == 1, "one seat plate supported"
    seat = by[seats.pop()]
    assert_seat_frame(seat)
    base_poly = poly(seat)
    families = {}
    for d in seated:
        families.setdefault(d["part_number"], []).append(d)
    for fam in families.values():
        assert all(f["outer"] == fam[0]["outer"] and f["holes"] == fam[0]["holes"] for f in fam), "family profiles differ"
    lap_foot_check(seated, joints, P)
    oldfeet = {d["name"]: footprint(d, poly(d), P, T) for d in seated}
    oldobs = {pn: unary_union([q for n, q in oldfeet.items() if by[n]["part_number"] != pn]) for pn in families}

    layout, visits = {}, 0
    if set(P["pinned"]) >= set(families):
        for pn, fam in families.items():
            a, b = P["pinned"][pn]
            for q in (slot_world(f, s, P, T) for s in (a, b) for f in fam):
                assert base_poly.covers(q) and q.distance(base_poly.boundary) >= P["min_bridge_mm"], f"pinned slot too close to seat edge: {pn}"
            opt = foot_option(fam[0], fam, a, b, base_poly, bottom_cuts(fam[0], joints), oldobs[pn], P, T, min_width)
            assert opt, f"pinned tabs invalid for {pn}"
            layout[pn] = ([a, b], opt[1], opt[0])
        mode = "pinned"
    else:
        options = {}
        cache_dir = Path(spec["_dir"]) / ".fixture-cache" / "tabs" if spec.get("_dir") else None
        for pn, fam in families.items():
            options[pn] = cached_family_options(cache_dir, fam, base_poly, joints, oldobs[pn], P, T, min_width)
            log(f"  {pn}: {len(options[pn])} tab options")
            if not options[pn]:
                raise ValueError(f"no two-tab options for {pn}: "
                                 + why_no_options(fam, base_poly, joints, oldobs[pn], P, T, min_width))
        chosen, visits = solve(options, P)
        layout = {pn: (options[pn][i][1], options[pn][i][2], options[pn][i][0][0]) for pn, i in chosen.items()}
        mode = "search"

    tabs, extensions = [], []
    bp = base_poly
    hw = P["width_mm"] / 2
    for d in seated:
        s_pair, pnew, added = layout[d["part_number"]]
        old = poly(d)
        above = box(-1e4, P["foot_height_mm"], 1e4, 1e4)
        assert pnew.intersection(above).symmetric_difference(old.intersection(above)).area < 1e-3
        p = pnew
        for s in s_pair:
            p = p.union(box(s - hw, -P["engagement_mm"], s + hw, .01))
            q = slot_world(d, s, P, T)
            assert bp.covers(q), f"slot outside seat: {d['name']} s={s}"
            bp = bp.difference(q)
            tabs.append({"plate": d["name"], "part_number": d["part_number"], "local_s": s,
                         "width_mm": P["width_mm"], "engagement_mm": P["engagement_mm"],
                         "slot_length_mm": P["width_mm"] + P["slot_clearance_mm"],
                         "slot_width_mm": T + P["slot_clearance_mm"],
                         "slot_xy": list(map(list, list(q.exterior.coords)[:-1]))})
        set_profile(d, clean(p))
        extensions.append({"plate": d["name"], "added_foot_area_mm2": added, "tab_spacing_mm": s_pair[1] - s_pair[0]})
    set_profile(seat, bp)
    bridge = min(a.distance(b) for a, b in itertools.combinations([Polygon(h) for h in seat["holes"]], 2))
    return {"mode": mode, "search_visits": visits, "seat": seat["name"], "tab_count": len(tabs),
            "seated_plates": len(seated), "families": len(families),
            "tab_positions": {pn: v[0] for pn, v in layout.items()},
            "minimum_seat_cutout_bridge_mm": bridge, "slot_count": len(tabs),
            "params": {k: v for k, v in P.items() if k != "pinned"}, "tabs": tabs, "foot_extensions": extensions}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec")
    ap.add_argument("out")
    a = ap.parse_args()
    spec = load_spec(a.spec)
    report = design(spec)
    write_json(a.out, report)
    print({k: v for k, v in report.items() if k not in ("tabs", "foot_extensions", "tab_positions")})


if __name__ == "__main__":
    main()
