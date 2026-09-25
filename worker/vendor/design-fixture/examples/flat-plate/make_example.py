#!/usr/bin/env python3
"""Worked example: write a fixture spec from scratch for a 160 x 100 x 6 mm flat plate.

Writes workpiece.step (the part placed in the fixture frame) and spec.json next to this file.
Then run:  python ../../scripts/build.py spec.json OUT

Design reasoning (fixture frame: base top at z = 0, part bottom face at z = 60):
- Primary datum: part bottom face. A1, A2 on rib R1 (y = -30), A3 on rib R2 (y = +30): three
  non-collinear 20 mm lands, normal +z.
- Secondary datum: long edge y = -50. B1, B2 on ribs S1/S2 (x = -40, +40), normal +y.
- Tertiary datum: short edge x = -80. C1 on rib C1, normal +x.
- Every contact normal lies in its rib's plane, so the contact is on the rib outline (required by
  audit_width contact fingers and by laser-cut construction).
- Clamp T1 (GH-201-B) presses down at (0, 30, 66), directly over A3. Arm points -y, so the clamp
  base sits behind the part on plate P_T1 (face z = 66), carried by two identical cheeks K1/K2.
  Face height 66 matches the clamping surface; underarm 25.1 mm needs 25.1 mm spindle
  extension (reported, adjustment range unknown).
- No lone ribs: every upright is crossed by a perpendicular 40 mm brace through cross-halving
  slots (brace slotted from the top, upright from the bottom): X1/X2 cross R1/R2, XS crosses
  S1/S2, XC crosses C1 and XK ties the clamp cheeks K1/K2.
Rib outlines are rectangles plus only the contact lands and cross slots; tabs are added by tabs_slots.py.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))

X, Y, Z = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]
NEG_Y = [0.0, -1.0, 0.0]


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def rib_xz(name, pn, y, outer, contacts, role="Locator rib"):
    """Upright in the world XZ plane at y: local x = world x, local y = world z; u x v = w."""
    return {"name": name, "part_number": pn, "role": role, "origin": [0.0, y, 0.0], "u": X, "v": Z, "w": NEG_Y,
            "outer": outer, "holes": [], "contacts": contacts, "seat": "BASE"}


def rib_yz(name, pn, x, outer, contacts, role="Locator rib"):
    """Upright in the world YZ plane at x: local x = world y, local y = world z."""
    return {"name": name, "part_number": pn, "role": role, "origin": [x, 0.0, 0.0], "u": Y, "v": Z, "w": X,
            "outer": outer, "holes": [], "contacts": contacts, "seat": "BASE"}


plates = [
    # Seat plate: frame must be world XY with origin x, y = 0. Top face at z = 0.
    {"name": "BASE", "part_number": "FP01", "role": "Base", "origin": [0.0, 0.0, -2.5], "u": X, "v": Y, "w": Z,
     "outer": rect(-160, -120, 160, 150), "holes": [], "contacts": []},
    # Primary ribs: body 10 mm below the part, 20 mm wide lands up to z = 60.
    rib_xz("R1", "FP02", -30.0, [[-65, 0], [65, 0], [65, 50], [60, 50], [60, 60], [40, 60], [40, 50],
                                 [-40, 50], [-40, 60], [-60, 60], [-60, 50], [-65, 50]], ["A1", "A2"]),
    rib_xz("R2", "FP03", 30.0, [[-25, 0], [25, 0], [25, 50], [10, 50], [10, 60], [-10, 60], [-10, 50], [-25, 50]], ["A3"]),
    # Secondary ribs: edge at local x = -50 (world y = -50) touches the part's long edge.
    rib_yz("S1", "FP04", -40.0, rect(-90, 0, -50, 70), ["B1"]),
    rib_yz("S2", "FP04", 40.0, rect(-90, 0, -50, 70), ["B2"]),
    # Tertiary rib: edge at local x = -80 (world x = -80) touches the short edge.
    rib_xz("C1", "FP05", 0.0, rect(-115, 0, -80, 70), ["C1"]),
    # Clamp support: two identical cheeks under a horizontal mount plate.
    rib_yz("K1", "FP06", -22.0, rect(84, 0, 127, 61), [], "Clamp support cheek"),
    rib_yz("K2", "FP06", 22.0, rect(84, 0, 127, 61), [], "Clamp support cheek"),
    {"name": "P_T1", "part_number": "FP07", "role": "GH-201-B mount plate; M5 x 0.8 tap after laser",
     "origin": [0.0, 0.0, 63.5], "u": X, "v": Y, "w": Z, "outer": rect(-30, 80.4, 30, 130.4), "holes": [], "contacts": []},
]
BRACE_H, SLOT_W = 40.0, 5.2  # brace height = lap height; slot = 5 mm stock + 0.2 mm clearance
plates += [
    {**rib_yz("X1", "FP08", -12.0, rect(-45, 0, 45, BRACE_H), [], "Cross brace"),
     "brace_merge_exception": {"with": "X2", "reason": "SYNTHETIC EXAMPLE, not a user decision: twin brace pair kept to exercise same-part-number (FP08 x2) tab families; a real fixture merges them"}},
    rib_yz("X2", "FP08", 12.0, rect(-45, 0, 45, BRACE_H), [], "Cross brace"),
    rib_xz("XS", "FP09", -70.0, rect(-55, 0, 55, BRACE_H), [], "Cross brace"),
    rib_yz("XC", "FP10", -100.0, rect(-30, 0, 30, BRACE_H), [], "Cross brace"),
    rib_xz("XK", "FP11", 100.0, rect(-35, 0, 35, BRACE_H), [], "Cross brace"),
]
joints = []


def cross(upright, brace, xy):
    """Cross-halving joint: upright slotted from the bottom, brace from the top, both to half lap height."""
    from shapely.geometry import Polygon, box
    by = {d["name"]: d for d in plates}
    for name, lo, hi in ((upright, -1.0, BRACE_H / 2), (brace, BRACE_H / 2, BRACE_H + 1.0)):
        d = by[name]
        s = xy[0] - d["origin"][0] if d["u"] == X else xy[1] - d["origin"][1]
        cut = Polygon(d["outer"]).difference(box(s - SLOT_W / 2, lo, s + SLOT_W / 2, hi))
        d["outer"] = [list(map(float, p)) for p in cut.exterior.coords[:-1]]
    joints.append({"a": upright, "b": brace, "xy": xy, "lap_height_mm": BRACE_H, "slot_width_mm": SLOT_W,
                   "a_slot": "bottom", "b_slot": "top"})


for upright, brace, xy in [("R1", "X1", [-12.0, -30.0]), ("R1", "X2", [12.0, -30.0]), ("R2", "X1", [-12.0, 30.0]),
                           ("R2", "X2", [12.0, 30.0]), ("S1", "XS", [-40.0, -70.0]), ("S2", "XS", [40.0, -70.0]),
                           ("C1", "XC", [-100.0, 0.0]), ("K1", "XK", [-22.0, 100.0]), ("K2", "XK", [22.0, 100.0])]:
    cross(upright, brace, xy)


def contact(name, p, n, rib, role):
    return {"name": name, "contact": p, "normal": n, "part": "Plate", "rib": rib, "role": role}


spec = {
    "schema_version": "1.2", "project_id": "EXAMPLE-FLAT-PLATE", "revision": "R1", "units": "mm",
    "thickness_mm": 5.0, "min_width_mm": 10.0,
    "plates": plates,
    "joints": joints,
    "assembly_layers": [["X1", "X2", "XS", "XC", "XK"], ["R1", "R2", "S1", "S2", "C1", "K1", "K2"], ["P_T1"]],
    "contacts": [
        contact("A1", [-50.0, -30.0, 60.0], Z, "R1", "Primary"),
        contact("A2", [50.0, -30.0, 60.0], Z, "R1", "Primary"),
        contact("A3", [0.0, 30.0, 60.0], Z, "R2", "Primary"),
        contact("B1", [-40.0, -50.0, 63.0], Y, "S1", "Secondary"),
        contact("B2", [40.0, -50.0, 63.0], Y, "S2", "Secondary"),
        contact("C1", [-80.0, 0.0, 63.0], X, "C1", "Tertiary"),
    ],
    "locating_groups": {"plate": ["A1", "A2", "A3", "B1", "B2", "C1"]},
    "clamps": [{"tag": "T1", "hardware": "GH-201-B", "mount_plate": "P_T1", "contact": [0.0, 30.0, 66.0],
                "surface_normal": Z, "arm_direction": [0.0, -1.0, 0.0], "apply_hole_pattern": True, "part": "Plate", "support": "A3"}],
    "workpiece": {"placed_step": "workpiece.step", "source_files": ["workpiece.step"], "parts": {"Plate": "Part_Plate"}, "source_to_fixture": [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]},
    "insertion": {"offsets_mm": [0.2, 0.5, 1, 2, 4, 8, 15, 30, 60, 100], "default_axis": Z, "along_w": []},
}

# Standard GH-201-B 60 x 50 mm cap rests on two cheeks. Locate its XY position during dry fit
# against the measured base frame, then retain with proposed underside stitch welds.
# Base tabs remain mandatory; upper cap tabs are not added when they inflate the mount.
for c in spec["contacts"]:
    c["face"] = {"type":"plane", "point":c["contact"], "outward_normal":[-v for v in c["normal"]]}
spec["supports"] = [{"id":c["name"], "plate":c["rib"], "part":c["part"], "contact":c["contact"],
                     "normal":c["normal"]} for c in spec["contacts"] if c["role"] == "Primary"]
spec["retention"] = [{"members":[d["name"], "BASE"], "method":"weld", "proposed_fillet_leg_mm":3,
                       "proposed_runs":"two 20 mm runs on accessible base edges, symmetric about the rib centre",
                       "status":"unknown", "reason":"example design proposal; weld strength and distortion not validated"}
                      for d in spec["plates"] if d.get("seat")]
spec["retention"] += [{"members":["K1","P_T1"],"method":"Cap rests on cheek top; position from base datums during dry fit, then propose two 20 mm, 3 mm underside fillet welds. Verify cap placement and weld distortion.","status":"unknown"},
                       {"members":["K2","P_T1"],"method":"Cap rests on cheek top; position from base datums during dry fit, then propose two 20 mm, 3 mm underside fillet welds. Verify cap placement and weld distortion.","status":"unknown"}]
spec["assumptions"] = ["Demonstration workpiece and proposed fixture weld sizes; requires engineering validation.",
                       "Operator seats secondary and tertiary datums; positive lateral seating during welding remains unresolved.",
                       "Bundled GH-201-B geometry is supplied-pose reference CAD; closed seating and motion require verification."]

if __name__ == "__main__":
    import numpy as np
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir
    from export_step import write_step, solid
    from clamp_mount import place
    shapes={"Part_Plate":BRepPrimAPI_MakeBox(gp_Pnt(-80,-50,60),gp_Pnt(80,50,66)).Shape()}
    write_step(HERE/"workpiece.step",shapes)
    for c in spec['contacts']:c['constraint_role']='fixed_datum'
    spec['assembly_locating']={'master_part':'Plate','datum_rationale':'Single flat workpiece on three non-collinear supports.',
        'mating_contacts':[], 'loading_stages':[{'id':'load-plate','parts':['Plate'],
        'fixture_contacts':[c['name'] for c in spec['contacts']], 'mating_contacts':[],
        'seating_directions':{'Plate':{'Primary':[0,0,-1],'Secondary':[0,-1,0],'Tertiary':[-1,0,0]}}}]}
    spec['assumptions']=[a for a in spec['assumptions'] if 'Red GH' not in a]+['Actual GH-201-B STEP is inserted by the exporter in its supplied pose. Closed operation and spindle adjustment require verification.']
    (HERE/"spec.json").write_text(json.dumps(spec,indent=2))
    print("Wrote example spec and workpiece; exporter inserts actual purchased hardware.")
