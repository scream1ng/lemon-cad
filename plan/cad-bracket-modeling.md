# Build real bracket modeling

Status: first milestone approved and implemented locally on 27 September 2026. Verified through automated geometry/persistence checks and live UI construction. See [verification evidence](../research/cad-bracket-verification.md). Subsequent milestones remain unimplemented.

## Outcome and assumptions

Keep the approved workspace: chat/history left, viewport right, icon tools with tooltips. Extend the actual geometry engine so a user can construct and edit a mechanical bracket from a blank document.

First acceptance part: a dimensioned right-angle bracket, constructed through the UI. This proves the missing modeling workflow; it is not a claim to duplicate the downloaded fuse-box support assembly. That reference contains 16 solids, and the HUD bracket contains 10. Reproducing complete references needs subsequent sheet-metal and assembly work. The surge tank requires a separate surface/solid modeling scope.

## First implementation milestone

1. **Multiple sketches and work planes.** XY, XZ and YZ planes with explicit offsets; rectangle, circle and closed line profiles. Click to place profile points in a planar editor; enter dimensions/coordinates to adjust them. Reject open, self-intersecting or degenerate profiles. Do not label sketches fully constrained without a constraint solver.
2. **Repeated additive extrusion.** Select a sketch, depth and direction. The first extrusion creates the body; later extrusions must join it. Disconnected results fail with a clear message. Each extrusion retains its source sketch dependency.
3. **Extruded cut.** Select a profile and direction; support a specified depth or through-all. Build holes on different planes using circular cut profiles. Reject cuts that miss the body or remove it entirely.
4. **Editable history.** Rebuild downstream features after dimension changes. Identify the first failing feature, preserve the last valid model, and support preview/cancel/apply, suppression, rollback and undo/redo. Show sketch dependencies in the existing history card.
5. **Save/reopen/export.** Persist the editable document and the exact STEP result together through the existing revision workflow. Reopen must preserve dimensions, dependencies and feature order.

Existing native fillets remain supported for version-one documents. General edge-selected fillets and chamfers follow with stable selection references; they are not silently approximated by rounding unrelated edges.

## Saved-data change requiring approval

Add `schema_version: 2` alongside the existing version-one reader. Version two retains part kind, millimetres, stable feature IDs, ordered features, suppression and rollback, and adds:

- Sketch work plane (`XY`, `XZ`, `YZ`), plane offset and dimensioned profile data (rectangle, circle or ordered closed line points).
- Extrusion source-sketch ID, add/cut operation, direction and extent (depth or through-all for cuts).
- Explicit dependency validation: a feature can reference only an earlier supported sketch; missing, suppressed or invalid dependencies fail visibly.

Use explicit datum planes for this milestone. Do not persist transient imported face/edge indices as parametric references. Imported STEP remains a reference/viewing format, not recovered source history.

Read existing saved documents without modifying them. An explicit edit that requires new capabilities converts a copy to version two; preview/cancel does not overwrite the version-one revision. Saving creates a new immutable revision. Retain a compatibility fixture for the existing drilled plate.

No SQL migration, new CAD dependency or production deployment is proposed. Provider-backed AI, billing and new external services are outside this milestone.

## Files and stable boundaries

- Contract: `backend/cad_document.py`, `frontend/src/cadDocument.ts`.
- Geometry: `worker/cad/authoring.py`, with a focused sketch/profile helper if needed.
- UI: `CadEditor.tsx`, `CadHistory.tsx`, `AuthoringToolbar.tsx`, `useCadAuthoring.ts`, a planar sketch editor, and narrow integration in `main.tsx`/`style.css`.
- Persistence: adjust only CAD validation/provenance paths in `backend/main.py` and worker dispatch if required for both document versions.
- Verification: existing frontend/backend/worker tests plus new geometry, dependency and compatibility cases; update capability documentation after verification.

Flagged stable areas being extended: version-one document validation, geometry rebuilding and saved-revision loading. Protect them with compatibility tests. Preserve measurement picking, authentication, pricing, sharing, file permissions, vendor engines and deployment configuration. No unrelated refactoring, commits or pushes.

## Verifiable completion gate

Construct this part from a blank document using the live UI:

- Base: 100 × 60 × 3 mm, occupying x=0..100, y=0..60, z=0..3.
- Upright: 100 × 3 × 40 mm, occupying x=0..100, y=57..60, z=3..43; joined to the base.
- Two Ø6 base holes at (20,30) and (80,30), through the 3 mm base.
- One Ø8 upright hole at x=50, z=23, through the 3 mm upright.

Independently verify one valid solid, bounds 100 × 60 × 43 mm, and volume `30000 - 102π` mm³ within numerical tolerance. Check STEP export by reimporting it and repeating geometry checks. A rendered resemblance is insufficient.

Edit an upstream sketch dimension and verify deterministic downstream rebuilding. Exercise invalid profile, missing dependency, disconnected addition, nonintersecting cut, cancellation, undo/redo, suppression and rollback. Save, reload and compare document parameters and exact geometry. Confirm existing version-one projects still open and edit.

Run existing tests before changes; stop and flag baseline failures. Run affected and existing suites/build after changes. Verify the workflow through actual browser controls and inspect desktop/mobile layout. If browser control remains unavailable, report that gate incomplete rather than claiming end-to-end success.

## Subsequent milestones

| Milestone | Concrete deliverable | Separate design decision |
| --- | --- | --- |
| Sheet-metal brackets | Base flange, edge flange with thickness/angle/inside radius, bend relief, holes/slots, verified flat pattern | Bend allowance/K-factor and unfolding scope; prove on one selected reference component before promising the full support |
| Assemblies | Insert saved part revisions, transforms, fixed components, defined mate types, interference | Constraint solution and reference stability; reproduce the remaining reference components explicitly |
| General solid/surface work | Edge-selected fillet/chamfer, revolve/shell, then needed loft/surface tools | Select a tank/reference feature and establish geometric acceptance before enabling tools |
| Comments and AI modification | Select geometry, attach a request, propose typed parameter/feature changes, preview and apply through the same executor | Provider configuration and selection persistence; never execute generated code |

These milestones are not represented as already working. Deliver and verify tools individually; keep unsupported toolbar controls unavailable.
