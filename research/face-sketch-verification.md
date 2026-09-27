# Planar-face sketch verification

Implemented after explicit approval of `plan/compact-tree-face-sketch.md`.

## Automated checks

- 27 frontend tests: existing measurement picking and view fit; compact history; immutable v3 upgrade; local point projection; outward/inward defaults; direct visible-face selection with occlusion and empty-space checks.
- 61 backend/worker tests: existing v1/v2 behavior; exact frames on six principal faces; an angled base and selected angled face; positive adds and inward cuts; frame validation; save/reopen and STEP round-trip; authenticated plane lookup with ownership checks.
- 11 existing drawing tests.
- Production TypeScript/Vite build passes; existing bundle-size warning remains.

## Live local API acceptance

Used the existing saved **Gusseted mounting bracket**, whose older mesh contains rounded normals and no frame. The new `/api/cad/face-plane` worker job resolved face 40 from the original STEP at full precision.

- Outward normal approximately `(0.83205, 0, 0.5547)`.
- Exact frame centered approximately `(148, 97, 88)`; U `(0.5547001962249982, 0, -0.8320502943379978)`, V `(0, 1, 0)`.
- Circle diameter 3 mm, outward extrusion 5 mm: volume increased from `200109.82291121435` to `200145.16582857273 mm³`, matching the analytic cylinder volume.
- The same circle cut inward 2 mm: volume `200095.68574427307 mm³`, matching the analytic removal.
- Saved as a separate private **Angled face sketch — verified** project in **Mechanical parts**. Reopened document matches the saved state and rebuilds to the same volume.
- Downloaded STEP reimports as one valid solid with the same volume. Original bracket revision is unchanged.
- Local artifacts: `/Users/oakky/Downloads/Face sketch verification/` (STEP, native JSON, numerical verification).

## Browser status

Native automation initially stalled, but reconnecting and navigating the app restored control. Completed on the saved acceptance copy in Chrome:

- Opened My files and the saved version-three part; face-selection mode is the default for native parts.
- Selected a face using keyboard and pointer; the context toolbar offered Sketch on face and Normal to.
- Opened a rectangle sketch on the selected face; verified Selected face, the fixed-plane note, local U/V values and normal camera orientation.
- Entered a centered 2 × 2 mm profile, previewed and applied it. Extrude picked that sketch and defaulted outward. A 3 mm extrusion preview increased volume by exactly 12 mm³ (`200145.2` → `200157.2` displayed); Apply and Undo worked.
- Extruded cut picked the same sketch and defaulted Into the face / Through all. Preview built (`199848.7 mm³` displayed), then Cancel preserved the previous body.
- Undid the temporary sketch and reopened the saved copy, discarding only this session’s unsaved test state.
- Selected the curved locating-boss wall: saw “Curved surface · choose a datum plane” and Datum sketch.
- Selected the top flange, entered face sketch mode and saw top-normal orientation. Cancel restored the previous isometric camera and left the draft saved.
- Expanded Extrude1 to expose Sketch1. Searching “circle” revealed matching nested sketches; clearing restored the compact tree.
- Switched to Smart Dimension and selected the boss bore: the existing measurement displayed Ø10.00 mm. Cleared the temporary measurement.

The final small usability adjustment rounds click-derived starting U/V coordinates to 0.001 mm (tested), while retaining the exact plane frame. Responsive automated view-fit tests pass; this turn did not repeat the earlier phone/tablet visual checks.

## Deliberate limits

- Face plane is a fixed snapshot, not an associative attachment to changing topology.
- Sketch drawing stays in the left 2D editor, with the model face for context.
- Native parts only; imported STEP history recovery and curved-surface sketches remain unavailable.
- Face sketch creation requires restoring the full history first; it does not silently attach a sketch to rolled-back geometry.
