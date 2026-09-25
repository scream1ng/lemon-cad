---
name: design-fixture
description: Design and revise welding or checking fixtures from STEP geometry or dimensioned drawings, with an interactive concept preview before an explicitly requested verified delivery package. Supports laser-cut ribs, weld blocks, and solid printed checking fixtures.
---

# Design Fixture

One self-contained CAD workflow. Measure with OCP; never infer manufactured geometry or approval from a picture. Bundled scripts, hardware and references have no dependency on another skill.

## Route once

If fixture purpose is missing (including a bare invocation or geometry upload), ask one quick question: **“Weld fixture or Check fixture?”** Do not start fixture design until answered. Infer the construction default without another question unless ambiguity materially changes the job.

| Purpose | Default | Explicit alternative |
|---|---|---|
| Weld | `laser_rib`: 5 mm laser-cut ribs | `block`: machined/welded blocks |
| Check (`checking`) | `laser_rib`: 5 mm laser-cut ribs | `printed_solid`: solid plastic |

Reject weld + printed and checking + block for delivery. Explore only if the user explicitly requests a **concept-only exception**, recorded with its reason; never finalize that exception through this skill.

## Phases and context budget

Every file read stays in context for the rest of the job. This table is the only reading list: read the active mode's files in `references/`, once, and nothing else.

| When | Read |
|---|---|
| All | project-record; step-first for STEP input; clamping when GH-201-B is used |
| Weld, laser ribs | weld-workflow, construction-operation, laser-cut-construction, spec-format |
| Weld, blocks | weld-workflow, construction-operation, block-construction |
| Check, laser ribs | checking-workflow, inspection, practical-review, checking-build, laser-ribs |
| Check, printed | checking-workflow, inspection, practical-review, checking-build, printed-solid, printed-body-spec; start from `examples/checking-printed/gauge-reference/README.md` (adapt by its list; do not read the scripts whole) |
| Feature in job | assembly-locating (more than one part), hole-slot-locating (locating from holes/slots), locating-hardware (pins, bushes, checking seating) |
| Phase | preview at concept (step 5), finalization only at step 6 |

Open `hardware/gh-201-b.json` only for a value you need (the scripts read it). Do not open script source unless a command fails and its message does not name the fix.


1. **Survey and concept:** Create the specification yourself from measured geometry, not scaled example dimensions or bounding boxes. Survey datums, units, tolerances, loads, parts and joints; choose an accessible right-handed frame and retain its transform. Identify functional faces/holes/slots from exact trimmed geometry — a cylinder is not automatically a hole, nor a plane a flange. Keep missing engineering inputs open. Checking needs every flange inventoried; welding needs a weld access/distortion strategy. Initialize with `workflow.py init spec.json project.json --kind weld|checking [--construction block|printed_solid]`.
2. **Locate/support:** Preserve 3-2-1 logic, no lone ribs (every upright crossed by a perpendicular member), suitable round/diamond pins, real bushes/manual withdrawal, practical bracing and supported clamp forces. Design so the whole workpiece lifts straight out away from the big part's primary datum with clamps open and removable pins withdrawn. For GH-201-B, start from the standard mount plate with cap tabs into its cheeks. Carry every dowel on the standard pin pad (hardware/pin-pad.json) named in `pin_locators[].pad`, on two cheeks with cap tabs, never on a rib edge. Use the actual 14-component CAD. Its supplied tilted-spindle pose is **not verified closed**. Never fake closure or equate mounting height with operating clearance.
3. **Datum scheme review (required before any concept):** run `scripts/workflow.py datum` and show the returned `datum-preview.html` — the 3-2-1 points and clamp on the bare part, no ribs, blocks or clamp bodies. Markers drag in their own face plane and hand back an exact mm patch; never read dimensions off the picture. **Comment mode** pins a numbered note to a clicked point on the part; **Copy all** combines moves and notes. If clipboard access is blocked, the complete text is selected in an inline box: press ⌘C/Ctrl+C, then paste into chat. Comments are review notes only — they never move a point or change the spec. A point reported `off_surface` is not on the placed CAD — fix the spec, not the marker. Record the user's own words with `workflow.py datum-ok --note "..."`. `concept` refuses to run until this ack exists, and it goes stale whenever contacts, locating groups, clamp contact/force, frame or sources change (rib or clamp-body edits do not stale it).
4. **Checking mode:** Checking defaults stay 3.0 mm gap, 2.5 mm GO enters / 3.5 mm NO-GO does not. Datum contact, pin fit and handling clearance are separate. Require restraint/hold-down rationale and full gauge/hand access.
5. **Interactive concept:** Run `scripts/workflow.py concept`. It **stops before any preview is shown** when a basic check fails:
   - `cross_support`: lone rib. `cap_joints`: cap without tabs. `material_width`: undersized ligament. `mount_compactness`: oversized clamp plate.
   - `unload`: a rib or fixed pin in the straight unload path.
   - `pin_clearance` (laser ribs): a pin that intersects, sits within 5 mm of, or is not carried by a pad plate — pressed through it or standing on a face square to the pin, never a rib edge — cap tabs, cheeks and braces included; an elevated pad standing on fewer than two plates fails; a sliding/removable pin may seat on its bush.
   - `brace_merge` (laser ribs): parallel braces under 50 mm apart in plane and span — commonise them into one brace.
   - `flange_coverage` (checking): a sheet feature — flange, tab, wall, web — with no station, datum, alternative or user-quoted waiver, or a station off the part. An unchecked feature under 5 mm wide is unknown, not a blocker. The datum preview shows unchecked features red.
   - `checking_geometry` (checking): the finalize station audit run early — a patch sample off the flat part face (hole, notch, bend), no land at the gap, or a GO/NO-GO misfit.

   Fix the named items and rerun; never show a concept with a blocker. Present the datum/support/clamp decisions and open items, then show Three.js inline when supported, and invite feedback through the same comment pins and Copy comments as the datum review (window capture still works). Send the single `preview.html` alone (target 250,000 bytes, strictly below 1,000,000) — it is self-contained; keep CAD files, PNGs and records private and send no concept ZIP; send `spec.json`/`project.json` only on a handoff request or at finalization. Revise with `scripts/spec_patch.py spec.json '<small JSON patch>'` (include the new `revision`) rather than rewriting the spec, preserve IDs and track changes by them, and regenerate with one `workflow.py revise spec.json project.json OUT [--build "<job build cmd>"] [--verify "<job verify cmd>"]` (build, checkpoint, concept, verify; one summary line, full output in `OUT/revise.log` and `OUT/result.json`). **Stop here by default.** Do not run nesting, manufacturing export or final package generation during concept iteration.
6. **Finalize only on explicit user request:** “finalize”, “approve”, or “complete the package” authorizes package generation, **not engineering/fabrication approval**; “design a fixture”, invocation, upload or a screenshot revision alone does not. An initial explicit complete-package request may run end-to-end after survey/concept and validation. Record authorization and run the appropriate pipeline. For laser ribs, emit joined open single-stroke etch polylines (never DXF text) and use the configured shop-stock usable zone while preserving a practical rectangular remnant. Fix known defects; retain genuine unknowns.

Astra is recommended for initial concept; Sol for revisions/finalization. This is guidance, not automatic switching. Persist `spec.json` plus `project.json` for a fresh chat/model; resume with `workflow.py resume spec.json project.json`, mapping relocated source paths. Validate source hashes, units, frame and version before reuse; changed source requires a fresh survey and invalidates evidence/approval. A byte-only change (re-export, identical solids by `source_geometry` fingerprint) is rebased automatically before authorization, as is a change confined to the `REF_` fixture solids in a surveyed STEP (a pin lengthened to press through its pad): where a pin locates the part is its `contacts` rows, so the datum ack survives it. Never relabel measurements. A handoff carries both records, the original sources and evidence, not only HTML.

## Invariants and boundaries

Keep `cad_verified`, `fabrication_ready`, `fixture_calibrated`, and `inspection_validated` distinct. Unknown/fail/exception never becomes pass. A complete package is not a production release. Preserve construction, fastener and pin evidence; continuous loading/release, clamp motion, weld access, stiffness, calibration and inspection qualification are not proved by sample clearance tests.

Rib automation supports one thickness, horizontal seat and vertical seated polygonal ribs. Blocks use an explicit OCP/CAD workflow, not rib fabrication automation. Curved/oblique checking, complex printed forms and unsupported arrangements need explicit measured CAD work. Three.js meshes are approximate and non-authoritative; exact OCP CAD owns measurements/verification.

Setup: install `scripts/requirements.txt` in a task environment (tested OCP 7.8.1.1; supported 7.8.x). Run `python -m unittest discover -s tests -v` after code changes (without a prepared env: `uv run --no-project --python 3.12 --with-requirements scripts/requirements.txt python -m unittest discover -s tests`). Low-level builders remain for regression tests; use the workflow gate for real projects.
