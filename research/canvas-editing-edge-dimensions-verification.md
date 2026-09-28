# Canvas editing and edge dimensions — verification

Implemented 2026-09-27 from the approved [plan](../plan/canvas-editing-edge-dimensions.md).

## Behavior

- Left card remains History / Chat. Conflicting geometry actions stay disabled during a draft.
- Supported modeling properties, Preview / Apply / Cancel, and original/preview comparison now live in a compact right-canvas popover, including initial part creation and history edits.
- Sketch mode shows a compact Options / Extrude / Cut / Cancel strip. Detailed fields are collapsed initially.
- Smart Dimension lives in the left-edge canvas rail. In sketch mode select a rectangle side and a visible, coplanar, parallel model edge, in either order; place the gap label and type a value. Width / height / diameter editing remains available.
- Gap edits translate the rectangle without resizing it. Zero aligns edges. Negative, nonfinite and out-of-range input is rejected. Selection highlights and contextual hints identify the current step.
- Edge gaps position once using existing sketch x/y coordinates. No persistent constraints or saved edge references were added. Temporary gap annotations recompute from current coordinates during the edit and disappear when the sketch editor closes. Upstream changes do not maintain those gaps.
- Straight-edge geometry metadata now keeps precise coordinates. Legacy rounded meshes remain selectable with tolerance; their original precision limit remains.

## Automated evidence

- Frontend: **32 tests passed**, including placement from all four rectangle sides, both sign directions, zero gap, invalid input, incompatible edges, and plane transforms.
- Backend / worker: **62 tests passed**, including a new regression for exact straight-edge endpoints on an arbitrary angled plane.
- Existing drawing suite: **11 tests passed**.
- Production build passed. Existing large-bundle warning remains.
- `git diff --check` passed.

A separate integration check passed model-edge metadata from the exact kernel through the actual frontend `planeEdge` and `positionFromEdge` functions, then rebuilt their returned CAD documents in the kernel. Top, side and angled planes each produced 8 mm / 6 mm offsets for a 20 × 12 mm rectangle and a 5 mm extrusion. Each added exactly 1200 mm³, within numerical tolerance; exported STEP files reimported at 41200 mm³ total volume. This verifies geometry and serialization, not browser interaction.

## Browser limitation and remaining manual checks

Chrome's accessibility tree showed the local app, but page clicks produced no change and the captured web content was black. Reconnecting through the direct browser interface returned “No browser is available.” No automated DOM or alternative GUI driver was used to bypass this limitation.

Consequently popup layout, pointer selection order, keyboard/touch interaction, end-to-end Apply / Undo / save / reopen and narrow-screen behavior have not been verified live for this change. Existing backend persistence tests passed; they do not replace those UI checks.

Manual walkthrough: select a face → Sketch → draw a rectangle → Smart Dimension in the left canvas rail → rectangle side → parallel model edge → place label → Set gap → repeat for the other direction → Extrude → enter depth → Preview → Apply. Every editing control should be inside the right card. Test Cancel and Back to sketch before applying, then Undo / Redo and save/reopen afterward.
