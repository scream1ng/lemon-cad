# Draw on the face → dimension → extrude

Status: approved by the user with “implement it” and implemented. Browser and exact-geometry evidence: [verification report](../research/direct-viewport-sketch-verification.md).

## Intended experience

Assumption: the main viewport is the drawing area; the left card contains compact properties and confirmation controls. Keep the existing two-card layout.

1. Select a planar face and choose Sketch. Rotate normal to that face, activate the Sketch toolbar, and show a subtle plane origin and axes over the model. Start a new sketch empty, without a pre-created rectangle.
2. Draw directly over the face: Rectangle uses two corners; Circle uses centre then radius; Line adds connected segments and closes by clicking the first point. Show the next segment or shape as the pointer moves. Keep pan and zoom available without allowing an ordinary drawing click to orbit the model.
3. Choose Smart Dimension, select a rectangle edge or circle, place its label, and enter a value beside that label. Width, height and diameter edits immediately resize the profile. A rectangle corner or circle centre can also be positioned relative to the sketch origin using U/V values. Keep numeric fields accessible in the left card as an alternative.
4. Choose Extrude directly from the active closed sketch. Show the depth control and exact solid preview, then confirm. The sketch and extrusion appear together as one undoable edit, with the sketch nested under Extrude in History. Allow return to the sketch before committing.
5. Cancel discards the draft and restores the previous camera and geometry. Escape ends the current drawing command first; cancelling the entire sketch remains explicit.

Left card: compact Sketch heading, selected tool properties, then confirmation controls. Remove the duplicate drawing grid from this workflow. Use short cursor/status hints such as “First corner”, “Opposite corner”, and “Select an edge”. Keep toolbar icons with tooltips.

## Scope and honest limits

- Existing v3 face frames, rectangle width/height, circle diameter, sketch coordinates and polygon points can store the first implementation. No saved-data extension or SQL migration is required.
- Smart Dimension initially drives rectangle width/height and circle diameter. These are actual parameter edits, separate from existing read-only solid measurements. Store the values in the existing sketch fields; regenerate their labels on reopen. Label positions can remain temporary UI state.
- Closed line profiles can be drawn and edited through their points. General persistent segment-length/angle constraints, equal/tangent/concentric relations and a constraint solver are a separate feature requiring a document design and explicit schema approval. Do not label polygon coordinate editing as a full Smart Dimension system.
- One closed profile per sketch remains the existing contract. Multiple independent contours, inner loops and mixed lines/arcs within a sketch are outside this first change.
- A valid closed profile may extrude without being fully constrained. Do not show a fabricated “Fully defined” status or block extrusion merely because positioning is still editable.
- Face planes remain fixed snapshots. They do not track a source face after upstream topology changes. Curved faces still need a datum-plane workflow.
- Preserve existing version-one edits and native-part restrictions. This does not enable imported STEP history reconstruction.

## Implementation boundaries

| Files | Planned change |
| --- | --- |
| `frontend/src/main.tsx`, `CadEditor.tsx` | Share one authoritative draft between properties, viewport and toolbar. Explicit sketch/extrude stages; keep draft edits separate from committed geometry. Selecting Extrude must use the active sketch ID, not implicitly the last sketch in the document. |
| `frontend/src/Viewer.tsx` | Integrate drawing/selection overlays with the existing camera. Intersect pointer rays with the exact work plane, convert to local U/V, project the profile and dimension labels back to the viewport. Route pointer and keyboard events by mode. |
| New focused sketch interaction module/component | Profile drawing state, transient first point, hover preview, closure, hit testing and inline dimension input. Keep geometry math independently testable. |
| `frontend/src/AuthoringToolbar.tsx` | Activate Sketch category on entry; enable supported drawing and dimension tools during sketch editing; keep unavailable tools honest. Extrude uses the current completed profile. |
| `frontend/src/cadDocument.ts`, `useCadAuthoring.ts` only as needed | Explicit sketch-to-extrusion linkage and transactional preview/cancel/apply. Prevent late preview responses from replacing a newer draft. |
| `frontend/src/PlanarSketch.tsx`, `style.css` | Retire the duplicate canvas where viewport editing replaces it; preserve coordinate editing if needed. Responsive compact properties, accessible controls and dimension input. |
| Focused frontend tests, verification report, README | Verify the interactions and document actual supported behavior. |

Stable areas touched: viewer selection/camera handling, editor draft state, toolbar command gating and preview lifecycle. Preserve solid measurement, saved revision loading, undo/redo, existing dimensions, face selection and camera restoration.

Do not change backend contracts, kernel operations, database tables, authentication, sharing, billing, assemblies, surface or sheet-metal tools.

## Verifiable acceptance

- Use the real browser to draw a rectangle and circle on top, side and angled planar faces. The outline must follow the pointer on the actual work plane at different zoom levels and viewport sizes.
- Draw a rough rectangle, set width 20 mm and height 12 mm through dimension labels, then extrude 5 mm. On an unobstructed face with full contact, the exact added volume is 1200 mm³.
- Draw a circle, set diameter 10 mm, extrude 5 mm; verify exact geometry and placement, not just the rendered mesh.
- Close a polygon; an open or self-intersecting profile cannot be committed as a solid. Invalid numeric dimensions retain the prior valid draft and show an inline error.
- Switching tools, pressing Escape, resizing, panning and zooming must not create accidental geometry. Typing in a numeric field must not trigger viewport shortcuts.
- Cancelling a sketch or extrusion preserves the original part; undo/redo and save/reopen retain the dimensioned result. Export STEP and validate the exact solid.
- Recheck existing outside-sketch measurements, face selection, history editing, preview failures and camera restoration. Run existing frontend/backend/worker tests and production build; flag failures without skipping tests.

Research: [SOLIDWORKS direct sketch and dimensions](../research/solidworks-direct-sketch-dimensions.md).
