# Bracket modeling verification — 27 September 2026

## Delivered scope

Version-two native CAD documents, multiple XY/XZ/YZ datum sketches with offsets,
rectangle/circle/closed line profiles, pointer placement and numeric coordinates,
joined additive extrusions, depth and directional through-all cuts, and explicit
sketch dependencies. Existing preview/apply/cancel, history, suppression, rollback,
undo/redo, saved revisions, and STEP export operate on the extended geometry.

Existing version-one documents are still read and edited. Upgrading creates a copy
with the same feature IDs; drilled/filleted version-one geometry is preserved before
subsequent general operations. Old revisions are not rewritten. No SQL migration,
new dependency, public deployment, commit or push was performed.

## Automated checks

- Frontend: 22 passing tests.
- Backend and worker: 45 passing tests.
- Vendor draft-drawing: 11 passing tests.
- Total: 78 passing, no skipped tests.
- TypeScript/Vite production build passes. Existing large-bundle advisory remains.
- Existing Starlette/httpx deprecation warning remains.

New checks cover exact bracket volume and bounds, STEP reimport, normalized-document
rebuild, upstream edits, rollback and suppression, invalid/open/self-intersecting
profiles, negative YZ extrusion, disconnected additions, missing/suppressed sketch
dependencies, missed/destructive cuts, legacy geometry preservation, copy-on-upgrade,
and version-two preview/save/reopen/artifact access. A failed geometry edit leaves the
saved revision unchanged. One new integration test initially misused the worker's
`run` entry point: it expected queue-loop error recording instead of its raised
exception. The harness now asserts the rejection and unchanged revision; no test was
removed or skipped.

## Live UI evidence

Used the running app at http://127.0.0.1:5178 with the existing local acceptance
account. Constructed **Bracket from scratch** using only visible UI controls:

1. New 100 × 60 mm XY rectangle; initial extrusion edited to 3 mm in History.
2. New XZ rectangle, plane offset 57 mm, local origin (0,3), size 100 × 40 mm.
3. Additive extrusion of the second sketch by 3 mm in +Y, producing one joined body.
4. Two Ø6 circle/through-cut pairs at XY (20,30) and (80,30).
5. One Ø8 circle/through-cut pair on XZ, offset 57, centre (50,23).
6. Saved the project, exported STEP through Export → Download CAD file, then reopened
   it from My files. Repeated reopening after the development reload. All ten history
   entries and dimensions were restored.

The actual browser-downloaded `/Users/oakky/Downloads/part.step` was read independently
with OCP: **one valid solid**, bounds **100 × 60 × 43 mm**, volume
**29679.557549333815 mm³**, matching `30000 - 102π`. The source STEP references in
Downloads were not imported to construct this part.

Additional live checks:

- Moving the upright sketch to offset 500 is rejected as disconnected; saved geometry
  remains intact. Correcting the offset permits a successful preview.
- Increasing upright height from 40 to 50 rebuilds all cuts and changes preview volume
  to 32679.6 mm³. Apply, Undo, Redo and Undo restore the corresponding history values.
- Drew three points with the pointer, closed the line profile, applied its sketch and
  previewed a triangular through-cut. Volume drops by exactly 300 mm³. Cancel and Undo
  remove this temporary test; the saved acceptance part has only the three round holes.
- Fractional width 100.25 and fractional sketch-view width 120.3 successfully preview;
  manually typing 140.35 into the view field is retained. Cancel preserves the saved part.
- Desktop, 390 × 844 phone, and 768 × 844 tablet layouts visually inspected. Phone
  canvas remains visible and editor scrolling reaches numeric fields and action buttons.
  Device emulation was turned off and DevTools closed afterward.

UI fixes discovered during verification: prevent the sketch canvas shrinking to zero
inside the mobile panel; permit fractional view sizes and normal numeric typing; add
Fit sketch for profiles outside the current view; retain readable feature dependencies.
The final browser view shows the saved bracket and its feature history.

## Remaining limits

Datum planes are explicit, not attached to picked faces. Profiles are dimensioned,
not solved by a general constraint solver. This milestone produces single joined
solids; disconnected multi-body modeling and assemblies are not supported. New
version-two parts do not yet have general edge-selected fillets/chamfers. Legacy
version-one fillets remain editable. Sheet-metal bends, bend relief/unfolding, surface
tools, assembly mates, pinned comments and free-form AI geometry proposals remain
future work. The acceptance bracket is a demonstrator, not a recreation of the full
16-solid downloaded fuse-box support assembly.
