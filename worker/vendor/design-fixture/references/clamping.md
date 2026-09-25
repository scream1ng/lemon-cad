# Clamp selection and placement

## Select hardware

Use GH-201-B as the preferred available manual hold-down clamp when its geometry and holding capacity suit the job. Read `hardware/gh-201-b.json` before placing it.

Do not infer applied clamping force from holding capacity. If the actual seating force, spindle adjustment, pad material, or clamp variant is unknown, record it as unknown and preserve a reasonable adjustment allowance.

## Place a clamp

1. Choose a workpiece contact that drives the part into a nearby support without distorting a thin or unsupported region.
2. Define the target clamp contact and force direction in the fixture work frame.
3. Align the clamp record's closed spindle axis with the target force line.
4. Position the spindle axis using the stored 56.9 mm reach from the base front. Set the mounting face level with the clamping surface using the shop rule below. Adjust the spindle within verified limits only; if limits are unknown, flag the selection for physical confirmation.
5. Transform the four mounting-hole centres from the clamp frame into the clamp-support plate frame.
6. On the default 5 mm plate, create nominal diameter 4.2 mm pilot holes and identify them for M5 x 0.8 tapping after laser cutting.
7. Ensure the complete base footprint lies on supported plate material with adequate edge distance and local stiffness.
8. Check the closed body and conservative opening envelope against workpieces, fixture parts, weld access, and operator hand space.

## GH-201-B coordinate convention

The canonical frame in `hardware/gh-201-b.json` has its origin at the centre of the base's front edge on the mounting plane:

- `+X`: from the base toward the clamp pad/spindle.
- `+Y`: across the clamp base when viewed from above.
- `+Z`: away from the mounting plane toward the mechanism.

The base extends in negative X from the origin. The four mounting holes, arm pivot, and spindle axis are stored in this frame. Apply one rigid transform from this frame to the fixture; do not independently move its hole pattern and clamping geometry.

The manufacturer supplies opening angles but not a complete machine-readable linkage model. Use the angles for planning and a conservative envelope for verification unless intermediate linkage poses have been derived and checked.

## Actual CAD and pose

Use the bundled original STEP through `hardware_geometry.py`; all 14 components are retained. `source_to_canonical` was measured from the mounting plane, base front and base centre. Its source hash is mandatory. The saved spindle is tilted approximately 24.5 degrees from the mounting normal, so the automatic export is a saved-pose hardware reference, not a closed clamping solution.

The measured slot centres are at canonical X=-5.15/-31.85 and Y=+/-11.020101 mm; slots are approximately 6.3 x 5.1 mm. The JSON retains the differing drawing dimensions as separately labelled evidence. Use the CAD-centre pattern for this asset; confirm the shop clamp variant before release.

The nominal 56.9 mm reach and 25.1 mm underarm height remain planning dimensions. The imported saved pad position is reported separately and must not be asserted to equal the intended clamp contact. Complete a measured closed-pose CAD adjustment, including connected linkage parts and spindle/nuts, through the explicit CAD workflow if closed geometry is required. Preserve component identity and validate mounting, pivots, contact, intersections and intermediate motion. Do not infer a closed linkage from opening angles alone.

## Standard mount plate

GH-201-B uses one shop-standard cap: **50 mm along the arm × 60 mm across, centred on the hole pattern** (`standard_mount_plate` in the hardware record). `clamp_mount.py` reports it in plate coordinates as `standard_outline_local`; set the mount plate `outer` to exactly that rectangle. Do not size the cap from the job.

1. The 10 mm structural-width rule is relaxed to **5 mm (1 × plate thickness) on this cap only**, for pilots, tab slots and edges. Every other plate keeps `min_width_mm`.
2. Place the two support cheeks about ±22 mm across from the hole-pattern centre, running along the arm, so their cap tab slots sit beside the base footprint and 5 mm clear of pilots and edges. `scripts/cap_joints.py` generates the cap tabs by default and `verify.py` fails a cap without two separated tabs; move a cheek or pin the tabs rather than removing them. Base-seated uprights still require two tabs.
3. A different outline is a job exception: store `mount_design.layout_reason` and `compact_alternative_considered` on the mount plate. `mount_compactness.py` passes the standard outline, fails an unexplained different one and leaves an explained one unknown pending review. Hardware without a standard plate keeps the older area-ratio screen (above 2 × the hardware envelope triggers review).

## Mounting-height rule and verification

For GH-201-B, use the workshop default **mounting face level with the pad's workpiece contact surface**. This is a user shop convention, not a universal clamp requirement. Measure the signed difference along `surface_normal`: mounting face minus actual clamping surface. Do not use an arbitrary platform offset or copy the HUD job's 13 mm correction into other designs.

For a horizontal 5 mm cap with top at clamping height H, its centre plane is H - 2.5 mm and directly supporting cheek tops are H - 5 mm. For other orientations or stock thicknesses, derive these offsets along the plate normal. Adjust the support geometry before export; do not move hardware independently from its mounting-hole frame.

`mount_height.py` probes the actual exported cap face inside the clamp base footprint and evaluates the actual trimmed workpiece surface at the intended pad contact. It records mounting height, contact height, normals, face identities, signed difference and nominal spindle extension. Its 0.01 mm comparison threshold is a CAD checking tolerance, not a manufacturing tolerance. A default mismatch fails. Do not enlarge that threshold to accept a different operating height.

A deliberately different operating height needs `mount_height_override` with `offset_mm` and `reason`, plus current `hardware_pose` and `clamp_seating` engineering evidence explicitly covering the clamp tag, as specified in [spec format](spec-format.md). Verified alternatives remain an `exception`; missing, stale or unrelated evidence fails the height check. Include verified spindle adjustment and fully locked linkage in that engineering work.

Never choose a platform height solely to clear the tilted saved pose. A height pass establishes only the mounting-level relationship. Keep closed seating, spindle range, opening motion and force checks separate and unresolved until measured. The assembled review image includes one CAD side projection per clamp showing both levels and their difference.

## Fastener and backing-rib access

Apply [construction and operation checks](construction-operation.md) to every clamp mount. Prefer two spaced backing ribs for a broad mount carrying an offset load; justify other arrangements from the load path and torsional support. Keep ribs, joint tabs and welds outside screw-end and drilling/tapping/tool envelopes. Hole edge distance and zero fixture interference do not verify fastener access. Model fasteners or conservative tool/screw envelopes and state the assembly stage checked.
