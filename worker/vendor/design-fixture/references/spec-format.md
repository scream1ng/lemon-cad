# Fixture spec format (laser-cut scripts)

`scripts/build.py` turns one JSON spec into the delivery package. Write the spec only after the
survey, orientation and locating decisions in [the weld workflow](weld-workflow.md) are made; the scripts
check and finish geometry, they do not choose datums. Worked example:
`examples/flat-plate/make_example.py`.

All values are millimetres in one right-handed fixture frame. Recommended: base top face at z = 0.

## Top level

| Key | Required | Meaning |
|---|---|---|
| `schema_version`, `project_id`, `revision`, `units` | yes | Copied into every delivery JSON record |
| `thickness_mm` | yes | Sheet thickness for every plate |
| `min_width_mm` | no (10) | Minimum in-plane material width limit |
| `plates` | yes | Plate records (below) |
| `contacts` | yes | Workpiece contact schedule (below) |
| `joints` | no | Cross-halving joints between uprights (below) |
| `locating_groups` | no | Legacy per-part diagnostic only; it cannot approve assembly location |
| `assembly_locating` | yes for location approval | Master part, datum rationale, cumulative loading stages, mating contacts and seating directions |
| `clamps` | no | Clamp placements (below) |
| `workpiece` | for CAD checks | `placed_step`, `parts`, optional `weld_surface`, `reference_prefix` |
| `assembly_layers` | no | `[[plate names], ...]` install order; unlisted plates follow |
| `insertion` | no | `offsets_mm`, `default_axis`, `along_w` (plates inserted along their own `w`) |
| `tab_slot` | no | Overrides of `tabs_slots.DEFAULTS`; `pinned: {part_number: [s_a, s_b]}` fixes tab positions |
| `nest` | no | Shop default: `stock_size_mm: [2400,1200]`, `usable_origin_mm: [0,0]`, `usable_size_mm: [2400,1100]`, plus `gap_mm`, `margin_mm`, `strip_width_step_mm`, `etch_height_mm`, `etch_edge_clearance_mm`. Supplying both legacy `sheet_width_mm` / `sheet_height_mm` `[min,max,step]` keeps the older generic size search. |

## Plate record

```json
{"name": "R1", "part_number": "FP02", "role": "Locator rib",
 "origin": [0, -30, 0], "u": [1, 0, 0], "v": [0, 0, 1], "w": [0, -1, 0],
 "outer": [[-65, 0], [65, 0], ...], "holes": [],
 "contacts": ["A1", "A2"], "seat": "BASE"}
```

- World point = `origin + u*x + v*y` for local `[x, y]`; the solid spans `w * [-T/2, T/2]`. Keep `u, v, w` orthonormal and right-handed (`u x v = w`).
- `outer` is one closed ring without the repeated first point; `holes` is a list of rings.
- `part_number`: plates sharing it must have identical `outer` and `holes` (they get the same tabs).
- `contacts`: names from the contact schedule carried by this plate; empty for non-locating plates.
- `seat` (optional): name of the plate that receives this plate's two tabs. A seated plate must be vertical (`v = +z`) with its bottom edge on local `y = 0`. Only one seat plate is supported, and its frame must be world XY (`origin` x, y = 0, `u = +x`, `v = +y`).
- `brace_merge_exception` (optional): `{"with": "<other brace>", "reason": "<user's words>"}` keeps two parallel braces under 50 mm apart; the pair reports unknown, never pass. Default is one common brace.
- Written by the scripts: `area_mm2`, `nest_rotation_degrees`, `nest_offset`; tabs are added to `outer` and slots to the seat's `holes`.

Draw `outer` without tabs: a rectangle plus required contact lands, joint slots and clearances.

## Contact

```json
{"name": "A1", "contact": [-50, -30, 60], "normal": [0, 0, 1], "part": "Plate", "rib": "R1", "role": "Primary",
 "face": {"type":"plane", "point":[-50,-30,60], "outward_normal":[0,0,-1]}}
```

- `normal` is the inward normal on the workpiece (direction the support pushes).
- `rib` is the plate whose outline carries the contact. The normal must lie in that plate's plane (contact on the cut edge, not the plate face).
- `face` identifies the intended plane by a point and outward unit normal. Verification requires the contact to lie on one actual trimmed CAD face matching this descriptor; it checks the contact normal against the measured inward normal. Missing descriptors or unsupported curved faces remain unknown.
- `part` is a key of `workpiece.parts`. Contacts without `rib` are checked against the `reference_prefix + name` shape in the placed STEP.

## Joint (cross-halving slots)

```json
{"a": "R1", "b": "X1", "xy": [-50, -30], "lap_height_mm": 45, "slot_width_mm": 5.2, "a_slot": "bottom", "b_slot": "top"}
```

`xy` is the crossing point; each plate gets a slot of `slot_width_mm` to half `lap_height_mm`, open at the stated edge. Every seated upright needs at least one such joint with a perpendicular upright (`cross_support`); otherwise set `cross_support_exception` on the plate with a reason. The joint geometry must already be cut into both outlines; the record drives tab avoidance and width audits.

## Clamp

```json
{"tag": "T1", "hardware": "GH-201-B", "mount_plate": "P_T1", "contact": [0, 30, 66],
 "surface_normal": [0, 0, 1], "arm_direction": [0, -1, 0], "apply_hole_pattern": true}
```

- `hardware` names `references/hardware/<id lower-case>.json`.
- `surface_normal` points out of the clamped workpiece surface (force is its negative); the mount plate's `w` must be parallel to it.
- `arm_direction`: from clamp base toward pad.
- `apply_hole_pattern: true` adds the tap-drill pattern while preserving existing holes/slots; identical holes are reused and intersecting cutouts are rejected. `false` requires the actual pattern to exist and reports its fit.
- Legacy `schematic_pivot` only compares an earlier layout; it is not used to generate geometry or establish the operating pose.

## Workpiece

`placed_step` (relative to the spec file) contains the workpiece already placed in the fixture frame. Unique leaf shapes named `Part_*` are workpiece bodies and `REF_*` are hardware references; both are copied into the assembly STEP. Do not include schematic clamp shapes: actual purchased hardware is inserted automatically as `HW_<tag>_<component>`. `parts` maps a contact `part` to an exact exported occurrence name, or an unambiguous substring. Ambiguous matches fail. Add `source_files` (original source paths) and `source_to_fixture` (rigid 4x4 transform). All source bytes and hardware records are hashed independently of the spec.

## Hole/slot locators and finished dowel bores (v6)

Follow [hole-slot-locating.md](hole-slot-locating.md) for feature selection, ground dowels, separate mounting fits, release checks and the explicit CAD/constraint-analysis boundary. Retain the measured feature identities, pin definitions and finishing operations in `requirements` and the four delivery records. Additional project fields are not automatically interpreted by the bundled planar-contact scripts. Do not assume a `pin_locators` list supplies geometry or locating rank. Each pin record may name its pad plate as `pad`: that plate is then treated as a cap (two tabs from the cheeks under it) and uses the standard pin-pad ligament instead of `min_width_mm`.

Keep the DXF laser profile and finished STEP geometry tied to explicit finishing operations when an undersize pilot is reamed. Compare each export against its intended manufacturing stage; do not silently substitute a different hole size or ignore a failed roundtrip check.

## Not automated

Datum choice, rib outline and land shapes, cross-joint slots, clamp position and mount-plate support, weld access, clamp opening/motion, workpiece loading/unloading, strength and retention verification, and base etch marks. The builder renders the actual assembly STEP into the two PNGs.


## Relationships and engineering evidence

- `supports`: explicit records identifying support ID, plate, workpiece, contact and normal.
- Each clamp should name `part` and `support`; its recorded force direction is opposite `surface_normal`.
- `retention`: members, fastening/welding method, proposed dimensions, status and outstanding verification. Proposed dimensions are design inputs, not proven strength.
- `assumptions` and `requirements` are retained in the output records.
- `engineering_checks`: measured checks attached at finalization; schema in [evidence](evidence.md).

## Automation limits

The single seat must be horizontal XY; seated ribs must have `v=+Z`; one thickness applies to all custom plates. The default single-sheet nest searches 0/90-degree rotations for the minimum-width strip within the configured usable zone, preserving a right-side rectangular remnant; it is a heuristic, not proof of a globally optimal nest. The default usable zone reserves the top 100 mm of 2400 x 1200 stock for clamping. Unsupported layouts need a separate explicit CAD/CAM implementation with the same records. Discrete fixture insertion samples are recorded as screening only; successful samples leave the continuous-motion check unknown.

## Assembly strategy and auxiliary supports

Use the schema and staged example in [assembly-locating.md](assembly-locating.md). Every fixture contact declares `constraint_role: "fixed_datum"` or `"auxiliary_support"`. Auxiliary contacts additionally declare `support_mode` (`adjustable_after_seating`, `floating`, or `relieved`) and `activation_sequence`; they do not earn locating rank. Their geometry/mechanism and activation must still be verified. Legacy undeclared roles remain unknown in the staged screen.

A mount plate may include `mount_design: {"layout_reason": "...", "compact_alternative_considered": "..."}`. These explain why a large platform is necessary; text alone does not certify compactness or strength.

The default hardware exporter preserves the supplied STEP pose. `hardware_geometry` checks real asset geometry and export identity. `hardware_pose`, `hardware_clearance` and `clamp_seating` require independent engineering evidence; a correct component count or nominal reach is insufficient.

## GH-201-B mounting height (v5)

Omitting `mount_height_override` selects the shop same-level rule. For a horizontal cap, derive its centre Z as clamping-surface Z minus half the plate thickness and supporting cheek height as clamping-surface Z minus the full thickness. The builder checks the input layout and separately measures exported CAD with `mounting_height`. Planar BSpline workpiece surfaces can be evaluated by their actual surface point and normal in this check; this does not change locator-face automation limits.

A non-default height uses the following clamp field (example only, not approval):

```json
"mount_height_override": {"offset_mm": -8.0, "reason": "Alternative operating arrangement supported by measured closed-pose and spindle-travel evidence."}
```

Positive offset means the mounting face lies above the clamping surface along `surface_normal`. Both `hardware_pose` and `clamp_seating` entries in `engineering_checks` must pass, carry the current geometry fingerprint and hash-checked evidence, and include `clamp_tags: ["T1"]` identifying every clamp they actually cover. A height override alone, unrelated evidence, or a changed evidence file cannot waive the mismatch. The exported height must also match the override within the fixed CAD checking tolerance. The result is `exception`, not fabrication approval. Include spindle adjustment and locked linkage in the measured evidence.
