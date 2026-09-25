#!/usr/bin/env python3
"""Place a toggle-clamp mounting pattern on its mount plate from the clamp contact and force direction.

Hardware canonical frame (references/hardware/<id>.json): origin at base front edge on the mounting
plane, +x toward the pad, +z away from the mounting plane; spindle axis at x = reach.
Given contact c, surface normal n (force = -n) and arm direction a:
  z = n, x = a projected normal to z, y = z x x; mounting face F = mount-plate face on the +z side;
  origin O = c - x*reach + z*((F - c).z). Holes = O + x*hx + y*hy, mapped to plate-local coordinates.
Reports hole fit, material ligament, base-footprint support and spindle extension needed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

from fixture_common import load_spec, set_profile, write_json

HARDWARE = Path(__file__).resolve().parent.parent / "references" / "hardware"


def unit(x):
    x = np.asarray(x, float)
    if not np.isfinite(x).all() or np.linalg.norm(x) < 1e-9:
        raise ValueError('clamp direction is zero or nonfinite')
    return x / np.linalg.norm(x)


def pin_pads(spec):
    """Plate names declared as pin pads by pin_locators[].pad."""
    return {p["pad"] for p in spec.get("pin_locators", []) if p.get("pad")}


def min_width_for(spec, plate_name):
    """A clamp cap or pin pad on a standard plate uses that plate's ligament; every other plate keeps the spec limit."""
    limit = spec.get("min_width_mm", 10.0)
    if plate_name in pin_pads(spec):
        limit = min(limit, json.loads((HARDWARE / "pin-pad.json").read_text())["standard_pad"]["min_ligament_mm"])
    for clamp in spec.get("clamps", []):
        if clamp["mount_plate"] == plate_name:
            std = json.loads((HARDWARE / f"{clamp['hardware'].lower()}.json").read_text()).get("standard_mount_plate")
            if std:
                limit = min(limit, std["min_ligament_mm"])
    return limit


def place(clamp, plate, T, min_width, segments=32):
    hw = json.loads((HARDWARE / f"{clamp['hardware'].lower()}.json").read_text())
    z = unit(clamp["surface_normal"])
    x = unit(np.array(clamp["arm_direction"], float) - z * (np.array(clamp["arm_direction"]) @ z))
    y = np.cross(z, x)
    o, U, V, W = (np.array(plate[k], float) for k in ("origin", "u", "v", "w"))
    assert abs(abs(W @ z) - 1) < 1e-6, f"{plate['name']}: mount plate is not normal to the clamp axis"
    face = o + W * (T / 2) * np.sign(W @ z)
    c = np.array(clamp["contact"], float)
    reach = hw["closed_geometry"]["reach_base_front_to_spindle_axis_mm"]
    underarm = hw["closed_geometry"]["underarm_height_mm"]
    O = c - x * reach + z * ((face - c) @ z)
    local = lambda p: [float((p - o) @ U), float((p - o) @ V)]
    dia = hw["mounting"]["fixture_plate_preparation"]["nominal_laser_cut_tap_drill_diameter_mm"]
    holes = []
    for hx, hy, _ in hw["mounting"]["hole_centres_canonical_mm"]:
        centre = local(O + x * hx + y * hy)
        holes.append(Polygon(Point(centre).buffer(dia / 2, quad_segs=segments // 4).exterior.coords))
    e = hw["base"]["extent_in_canonical_frame"]
    footprint = Polygon([local(O + x * px + y * py) for px, py in
                         ((e["x_min_mm"], e["y_min_mm"]), (e["x_max_mm"], e["y_min_mm"]), (e["x_max_mm"], e["y_max_mm"]), (e["x_min_mm"], e["y_max_mm"]))])
    std = hw.get("standard_mount_plate")
    if std:
        (cx, cy), hx, hy = std["centre_canonical_mm"], std["along_x_mm"] / 2, std["across_y_mm"] / 2
        standard = [local(O + x * (cx + sx * hx) + y * (cy + sy * hy)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    else:
        standard = None
    outer = Polygon(plate["outer"])
    existing = [Polygon(h) for h in plate["holes"]]
    # A pre-existing identical pilot hole is reusable; all other cutouts remain obstacles.
    others = [q for q in existing if not any(q.symmetric_difference(h).area < 1e-6 for h in holes)]
    conflicts = any(h.intersects(q) for h in holes for q in others)
    pattern_present = all(any(q.symmetric_difference(h).area < 1e-6 for q in existing) for h in holes)
    ligament = min([outer.exterior.distance(h) for h in holes] + [a.distance(b) for i, a in enumerate(holes) for b in holes[i + 1:]]
                   + [h.distance(q) for h in holes for q in others])
    inside = all(outer.contains(h) for h in holes)
    contact_height = float((c - face) @ z)
    extension = underarm - contact_height
    row = {"tag": clamp["tag"], "hardware": hw["id"], "mount_plate": plate["name"],
           "frame": {"origin": O.tolist(), "x": x.tolist(), "y": y.tolist(), "z": z.tolist()},
           "force_direction": (-z).tolist(), "contact": c.tolist(),
           "hole_centres_local": [list(h.centroid.coords[0]) for h in holes],
           "hole_centres_world": [(O + x * hx + y * hy).tolist() for hx, hy, _ in hw["mounting"]["hole_centres_canonical_mm"]],
           "hole_preparation": hw["mounting"]["fixture_plate_preparation"],
           "standard_outline_local": standard,
           "holes_inside_plate": inside, "min_ligament_mm": ligament, "ligament_limit_mm": min_width,
           "base_footprint_supported": outer.buffer(1e-6).covers(footprint) and not any(q.intersection(footprint).area > 1e-6 for q in others),
           "pattern_conflicts": conflicts, "pattern_present": pattern_present,
           "target_workpiece": clamp.get("part"), "supporting_locator": clamp.get("support"),
           "contact_height_above_mount_face_mm": contact_height, "spindle_extension_below_arm_mm": extension,
           "schematic_pivot_offset_mm": float(np.linalg.norm(O + z * underarm - np.array(clamp["schematic_pivot"]))) if clamp.get("schematic_pivot") else None}
    from mount_height import nominal
    row["mounting_height"] = nominal(clamp, plate, T, hw)
    geometric_ok = not conflicts and (clamp.get("apply_hole_pattern") or pattern_present) and inside and ligament >= min_width - 1e-4 and row["base_footprint_supported"] and extension >= 0 and row["mounting_height"]["status"] != "fail"
    row["status"] = "fail" if not geometric_ok else "unknown"  # spindle adjustment range is unknown for GH-201-B
    row["note"] = "motion clearance and spindle adjustment range not verified"
    return row, holes, footprint


def mount(spec):
    by = {d["name"]: d for d in spec["plates"]}
    rows = []
    for clamp in spec.get("clamps", []):
        plate = by[clamp["mount_plate"]]
        row, holes, _ = place(clamp, plate, spec["thickness_mm"], min_width_for(spec, plate["name"]))
        if clamp.get("apply_hole_pattern"):
            if row["pattern_conflicts"] or not row["holes_inside_plate"]:
                raise ValueError(f"{clamp['tag']}: mounting pattern conflicts with existing cutouts or plate boundary")
            existing = [Polygon(h) for h in plate["holes"]]
            merged = list(plate["holes"])
            for h in holes:
                if not any(q.symmetric_difference(h).area < 1e-6 for q in existing):
                    merged.append(list(h.exterior.coords)[:-1])
            result = Polygon(plate["outer"], merged)
            if not result.is_valid:
                raise ValueError(f"{clamp['tag']}: invalid merged mounting holes")
            set_profile(plate, result)
        row["applied"] = bool(clamp.get("apply_hole_pattern"))
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec")
    ap.add_argument("out")
    a = ap.parse_args()
    rows = mount(load_spec(a.spec))
    write_json(a.out, rows)
    for r in rows:
        print(r["tag"], r["status"], "inside", r["holes_inside_plate"], "lig %.2f" % r["min_ligament_mm"], "ext %.1f" % r["spindle_extension_below_arm_mm"])


if __name__ == "__main__":
    main()
