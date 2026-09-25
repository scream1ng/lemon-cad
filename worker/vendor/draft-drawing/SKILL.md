---
name: draft-drawing
description: Turn a STEP file (sheet-metal part or weldment) into a draft drawing — overall size, flanges, bends, hole/slot positions and total steel weight — with an interactive HTML review before an explicitly requested A3 PDF.
---

# Draft Drawing

Drop a STEP file → measured numbers → HTML review with comment pins → PDF when the user asks. Every number comes from exact OCP geometry (`measure.py`); never read a dimension off a picture, mesh or SVG. Self-contained: no dependency on design-fixture.

## Setup

Needs Python 3.10+ with `scripts/requirements.txt` (cadquery-ocp 7.8.x, numpy, matplotlib, pillow). System python usually lacks OCP, so run every command below through
`uv run --no-project --python 3.12 --with-requirements scripts/requirements.txt python …` (below: `python …`). Tests: `python -m unittest discover -s tests`.

## Workflow

1. `python scripts/workflow.py preview STEP OUT` → `OUT/measure.json`, `OUT/drawing.json` (settings, created once with defaults), `OUT/preview.html`, and a JSON summary on stdout. Report to the user: total kg, the items list, anything NOT DIMENSIONED, and the preview path. Do not ask setup questions first; defaults are stated below and editable.
2. The user reviews `preview.html` (3D + one tab per sheet) and pastes back comments from **Copy all**. Sheet pins give the nearest sheet text and view (`near “SLOT 10.0×30.0” · top view`) plus paper mm (A3, origin bottom-left); 3D pins give mm in item 1's part frame and the nearest feature ID.
3. Apply comments by editing `OUT/drawing.json` only, then re-run `preview`. Never hand-edit measure.json, the SVG or the PDF. A comment `drawing.json` cannot express (move, add or drop a dimension, a misplaced label) is a drafting-rule bug in the skill: tell the user so and fix `sheet.py` for every job, with a test, only if they ask. Never patch `sheet.py` just for one job.
4. Only when the user explicitly asks for the PDF: `python scripts/workflow.py finalize OUT --request "<the user's words>"`. It refuses if the STEP or drawing.json changed since the last preview.

## drawing.json

`title` (label and PDF name), `material`, `density_kg_m3` (7850 steel), `show_hidden`, `scales` (`{"1": [1, 2], "assembly": [1, 5]}` forces a scale; otherwise the largest standard scale that fits), `notes` (extra sheet notes), `skip_items` (item numbers with no detail sheet).

Defaults: third-angle projection, A3 landscape, mm. The sheet is a quick sketch for a supplier (sizes and weight), not a formal drawing: no title block, drawing number, date, tolerance or revision. Do not add them.

## What is measured

- **Mass**: every solid × density, summed; identical bodies grouped with a quantity. Overlapping solids (welds modelled into parents) count twice — said in the mass note.
- **Items**: a body is `sheet` when its flat face pairs explain its volume; otherwise `weld (probable)`, `fastener (probable)` or `unclassified`. "Probable" is a geometric guess — ask the user to confirm, never present it as fact. Descriptions are generated when STEP product names are not unique.
- **Per sheet item** (part frame: Z = inward normal of the largest flange, X its long axis, origin = part-box min corner): overall size, thickness, flanges (span × width, face direction), bends (inner R, angle, length, axis), holes (Ø), slots (width × length, direction), rectangular holes, other cutouts — positions X/Y/Z from the datum.
- **Sheets**: assembly sheet with parts list and balloons (more than one item), then one detail sheet per sheet item: top/front/right views (third angle), iso with bend lines, notes, and a small label: part × qty, material, thickness and mass (page number only when there is more than one). Drawn to the rules below.

## Drafting rules (shop drawing: what a fabricator measures with a tape, vernier and protractor)

- Basic dims only: overall, flange lengths, hole/slot size, hole-to-hole. Nothing a fabricator would not measure.
- Every annotation sits off the part (holes and slots count as part); extension lines start at the part edge; size callouts are grouped (`4-□8.7×8.7`) with a leader into clear space.
- Hole chains run per flange and tie to the nearer real edge of the outline; square/rectangular holes are dimensioned to their edges (vernier), round holes to centres.
- A flange on the right of a view gets its dims on the right (same for left/top/bottom).
- Heights on the front view are measured off the primary flange (largest, datum), outside to outside (e.g. underside of the primary to top of a raised flange), not from the bottom of the part.
- Tabs and upstanding flanges are measured to the outside of the material at their bend (the virtual sharp), plus their length and position along the part. Each tab gets its own dims, even when sizes repeat (no `2×`).
- Flange lengths along the front profile go between the bends' virtual sharps (skipped when any bend is oblique, as the profile is then not true in that view).
- Non-90° bends seen end-on get a protractor arc and angle; all bends also appear in one note.
- Dim labels sit on top of their line (vertical: to its left); a label too long for its gap moves out past the arrows. No two labels overlap, and no size callout sits on the part (tested). A lone dimension that repeats another on the same axis is drawn once.
- No tables on detail sheets; the HTML review has no side panel (3D, sheets, total mass only).

## Not measured (listed as NOT DIMENSIONED, never passed off as checked)

Curved faces that are not flanges or cylindrical bends (B-spline forming, embosses), narrow flats under 5 mm, flat pattern / K-factor, tolerances, GD&T, surface finish, weld symbols, threads. Holes on oblique flanges and irregular cutouts are listed as NOT DIMENSIONED on the sheet.

## Rules

- Unknowns stay unknown. If something the user asked for is not measured, say so plainly.
- The HTML must stay a single file below 1 MB (target 250 KB); preview fails otherwise.
- Finalize only on an explicit user request, quoting their words in `--request`.
