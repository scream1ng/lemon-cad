# Compact history and face sketching

## Ready to implement: history presentation

- One line per operation; numbered Extrude, Cut, Hole and Fillet labels.
- Collapse consumed sketches below their operations. Keep unused sketches visible.
- Search includes hidden sketch children; matching children become visible.
- Plane, offset and profile details move into tooltips. Suppress and rollback remain keyboard accessible and appear on hover/focus; touch keeps actions visible.
- Scope: CadHistory.tsx, featureTree.ts, history CSS, focused frontend tests. No saved-data changes.
- Verify the 48-entry bracket, shared/orphan sketches, search, expansion, suppression/rollback availability, responsive layout and existing tests.

## Approved and implemented: general planar-face sketches

User approved this extension with “implement it”. Version 3 now stores face frames; versions 1 and 2 remain supported.

Selecting a planar face should offer Sketch, face-normal view and Clear. Sketch uses that face's position/orientation instead of asking the user to copy a datum offset. Measurement stays an explicit mode.

The current saved contract supports only XY/XZ/YZ plus an offset. Arbitrary angled faces require a versioned document extension holding an exact local plane frame (origin, U axis, V axis). Existing documents must remain readable without changing their geometry.

Proposed scope: document contract and validation, exact face-frame metadata from the CAD kernel, profile/extrusion transforms, viewer selection/context controls, camera normal-to orientation, editor and regression tests. Preserve the existing measurement flow and preview/apply/cancel lifecycle.

Expected files: `backend/cad_document.py`, `worker/cad/icl.py`, `worker/cad/profile_authoring.py`, `frontend/src/cadDocument.ts`, `Viewer.tsx`, `main.tsx`, `CadEditor.tsx`, `PlanarSketch.tsx`, and focused frontend/worker/backend tests. A versioned frame must use full-precision kernel data, not the rounded measurement metadata currently sent to the viewer.

The initial face plane is a fixed snapshot, not an associative attachment that follows future edits to its source face. Explain that in the editor. Stable face references and automatic reattachment need a separate topology design. Curved faces cannot directly host a 2D sketch; offer a datum plane instead.

Implementation includes precise plane metadata and an authenticated worker lookup for older mesh artifacts, native face-selection mode, contextual Sketch/Normal to/Clear, toolbar selection reuse, camera restoration on cancel, outward add/inward cut defaults, and the fixed-plane notice. The profile is edited in the existing left 2D panel; this does not add in-viewport sketch drawing or an associative topology system.

Success: top/side/angled planar faces create correctly located sketches; extrusion joins outward and cuts inward; exact STEP round-trip and saved revisions rebuild; curved faces show a clear reason; cancelled/failed operations preserve the previous part.

No database tables, authentication, sharing, billing, assemblies or sheet-metal changes.

## History implementation status

Implemented compact rows, nested sketches (including shared-sketch access under each consuming operation), derived numbered labels, tooltip details, hover/focus actions and search that reveals hidden sketch children. Existing saved documents remain unchanged.

Validation: 27 frontend, 61 backend/worker and 11 drawing tests pass; production build passes (existing bundle-size warning). Browser checks now pass for face selection, sketch preview/apply, extrusion, cut preview/cancel, camera restoration, curved-face guidance, compact-tree expansion/search and existing measurement. Earlier native-automation stalls were resolved by reconnecting and navigating the app.

Latest face-workflow evidence and limitations: [verification report](../research/face-sketch-verification.md).
