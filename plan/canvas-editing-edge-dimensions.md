# Canvas editing and rectangle-to-edge dimensions

Status: user approved implementation. Canvas controls and one-time edge positioning implemented using the existing document contract. Persistent linked dimensions remain separate; no saved-data extension was made. Browser interaction verification is blocked; see [verification](../research/canvas-editing-edge-dimensions-verification.md).

## Layout

Keep the two cards. The left card remains History / Chat while editing. All inputs and confirmation controls needed to complete a modeling command live inside the right card.

- Keep Smart Dimension in the vertical rail at the left edge of the right canvas, including during sketching. In sketch mode it creates driving sketch dimensions; outside sketch mode it retains the existing measurement behavior. Give each mode an accurate tooltip.
- Leave the drawing area clear. Show a small context strip with the active command, options, Extrude / Cut, and Cancel. Open detailed properties only on request.
- Enter dimension values beside their labels. Use interactive popovers, not hover tooltips, for inputs and actions.
- Extrude opens a compact canvas popover with depth, direction, join/cut, preview, Apply, and Back to sketch. Reuse the existing exact-geometry preview and draft transaction.
- Move supported hole, fillet, initial-part and history-edit properties into the same canvas host. Do not introduce duplicate editors or another permanent card.
- Clamp popovers inside the canvas; on narrow screens use a compact bottom panel within the right card. Keep inputs and confirmation actions reachable when the keyboard is open.
- History and Chat remain readable during a draft. Guard actions that would replace or mutate the part until the draft is applied or cancelled.

## Rectangle positioning interaction

1. Draw a rectangle on a planar face.
2. Choose Smart Dimension in the canvas rail.
3. Select a rectangle side and a parallel straight model edge, in either order. Highlight the first selection and preview the second. Only coplanar, visible, eligible model edges may be selected.
4. Click to place the distance label. Enter the gap beside it; Enter accepts, Escape cancels that input.
5. Move the rectangle to satisfy the gap without changing its width or height. Preserve which side of the reference edge the rectangle occupies. Allow zero for alignment.
6. Repeat in the other direction, then choose Extrude and finish entirely in the right card.

Existing width, height and diameter edits remain available. A single rectangle edge followed by empty-space placement makes its size dimension; selecting a second parallel model edge makes a position dimension. Short contextual hints distinguish these steps.

This first edge-positioning scope is axis-aligned rectangles in their own sketch plane, including angled planar faces in 3D. Curved edges, nonparallel distances, angular constraints, polygon constraints and a general sketch solver are separate work. Unsupported targets must explain why they cannot be selected.

## Persistence decision required

**One-time positioning:** calculate and store existing sketch x/y coordinates. No saved-data extension. The resulting position survives save/reopen, but no edge relationship is saved or maintained after upstream changes. Temporary gap annotations must not masquerade as persistent constraints.

**Linked dimensions:** save the dimension value, sketch-side identity, reference identity and dependency, and recompute placement during rebuilding. Requires a new versioned CAD document contract and explicit schema approval. Existing face attachments are fixed frames and current mesh edge IDs are not stable references across rebuilds. The implementation must establish supported persistent references before enabling linked dimensions; it must never silently attach to a nearby edge after topology changes. A missing or ambiguous reference must produce an actionable broken-reference state. Supporting face movement also requires an associative plane attachment, rather than the current fixed frame. The exact supported reference types and data contract must be reviewed before implementing this option.

Do not represent one-time positioning as linked dimensions. Do not introduce a schema extension before approval.

## Implementation boundaries

| Area | Change |
| --- | --- |
| `frontend/src/main.tsx`, `CadEditor.tsx`, `WorkspaceSidebar.tsx` | Move the existing controlled editor to a canvas popover; retain one draft; leave left tabs available and guard conflicting actions. |
| `frontend/src/SketchViewport.tsx`, `sketchGeometry.ts` | Two-entity selection, distance preview, position calculation, inline input, selection cancellation and clear contextual hints. |
| `frontend/src/Viewer.tsx`, edge-picking helpers | Expose eligible model edges to sketch interaction with visibility and plane checks; preserve camera and existing measurement behavior. |
| `frontend/src/AuthoringToolbar.tsx`, `style.css` | Persistent canvas dimension rail, active mode indication, compact responsive editing controls and focus behavior. |
| Focused tests and verification report | Geometry math, interaction state, preview/cancel/save behavior and actual browser checks. |

If linked dimensions are selected, extend this file with the reviewed frontend/backend document contract, worker rebuild behavior and reference-resolution tests before implementation. That option also touches `cadDocument.ts`, `backend/cad_document.py`, worker authoring and geometry metadata.

Preserve authentication, project permissions, export, file management, unrelated styling and unsupported modeling categories. Do not commit or push.

## Acceptance checks

- On an 80 × 50 mm top face, draw a 20 × 12 mm rectangle, place it 8 mm from one boundary and 6 mm from an orthogonal boundary, and extrude 5 mm using only the right card. Verify exact gaps and an added volume of 1200 mm³ on an unobstructed face.
- Repeat on side and angled planar faces; zoom, pan and resize must not change selected geometry or distances. Hidden and out-of-plane edges must not be eligible.
- Accept zero gap; reject blank, nonfinite and out-of-range input without losing the valid draft. Display sensible precision rather than floating-point noise.
- Verify both selection orders, single-edge size dimensions, overlapping targets, Escape, tool switching, popup focus and cancellation.
- Changing width/height must follow the chosen positioning semantics. Linked mode must preserve a constrained gap, flag conflicts and handle upstream changes or missing references explicitly.
- Sketch → dimension → extrude → preview → apply; Back to sketch; Cancel; Undo/Redo; save/reopen; export. Verify new-part creation and existing feature edits also finish on the right.
- Check popovers at desktop and narrow widths, keyboard navigation and touch target sizes.
- Run existing frontend tests, backend/worker tests and production build. Drive the real browser; report any browser verification limitation explicitly.
