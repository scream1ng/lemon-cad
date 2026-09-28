# Direct viewport sketch verification

Implemented 2026-09-27 against `plan/direct-viewport-sketch.md`.

## Delivered

- Main viewport draws directly on the selected exact face plane. Rectangle: two corners; Circle: centre/radius; Line: connected segments, closed at the first vertex.
- Left card contains properties and confirmation, without the duplicate drawing canvas for existing native models. Starting a part without a model retains the initial profile editor.
- Sketch toolbar stays available, shows the active tool, and disables extrusion until a valid closed profile exists.
- Smart Dimension selects rectangle edges or circles, places a label, and opens an inline size editor. Width, height and diameter update the same draft as the property fields. Invalid inline input retains the previous size.
- Extrude uses the active sketch ID and immediately builds an exact preview. Back to sketch, Cancel, Apply, Undo/Redo, save and reopen preserve the intended draft/committed boundary.
- Drawing uses a face-normal view with origin axes, live outline, zoom and right/middle-button pan. Drawing clicks do not reach orbit/measurement handling. Existing solid dimensions are hidden while editing the sketch.
- No contract, database, kernel or dependency changes.

## Browser evidence

Native Chrome at `http://127.0.0.1:5178`, using the existing local CAD test account:

| Check | Observed result |
| --- | --- |
| Top face, rectangle | Mouse-drew the rough rectangle on Drilled plate. Smart Dimension selected its upper horizontal edge, placed its label, and changed width to 20 mm. Edited height through its viewport label to 12 mm. |
| Invalid dimension | Height 0 showed an inline error; old geometry/height remained intact. Entering 12 then succeeded. |
| Extrude | Active rectangle went directly to exact preview. Changed depth to 5 mm, rebuilt and applied. History showed Extrude2 with a nested sketch. One Undo removed both. |
| Circle | Mouse-drew centre/radius on the saved plate, edited diameter to 10 mm, zoomed and fitted without losing alignment, and built a circular boss preview. |
| Back to sketch | Returned from the circular extrusion preview with the Ø10 profile intact and camera normal to the original face. |
| Connected lines | Drew three vertices. Extrude stayed disabled while open; clicking the first vertex closed the polygon and enabled extrusion. Exact solid preview succeeded. Cancel returned to the saved model. |
| Vertical face | Selected the plate side, drew an 8.485 × 4.455 mm rectangle directly on it, and built a 10 mm outward extrusion preview. Cancel restored the saved part. |
| Angled face | Opened an API-created 45° test plate, selected its large angled face, and mouse-drew a circle. Changed its diameter to 10 mm through the viewport label and extruded 5 mm. Preview, Apply, Undo, Redo and browser Save all succeeded. The base fixture was API-created; the added circle and extrusion were drawn through the UI. |
| Existing measurement | Outside sketch mode, selected the new boss's cylindrical wall. The original measurement flow reported Ø10.00 mm. Cleared the temporary measurement and left the saved model in face-selection mode. |

Pan and resized projection math are covered by focused automated tests. A physical native-window resize and right-button drag were not exercised in this browser run.

## Exact geometry and durable saves

`Viewport sketch — 20 × 12 × 5` is a separate private project saved from the browser-generated preview using the existing API, then opened through My files. Original Drilled plate was not overwritten.

- Project: `507d6b2b-b49f-4be7-bc90-e2bc706bfdf3`
- Revision: `0b5db1be-f2cc-462e-adc5-ff25778050a2`
- Base volume: 38834.690350851255 mm³
- STEP volume: 40034.69035085127 mm³
- Added volume: 1200 mm³, matching 20 × 12 × 5.
- API reopening preserved the exact CAD document; downloaded STEP passed the one-valid-solid check.

`Angled plane — viewport test` was saved through the browser after drawing the boss.

- Project: `27f77da5-b698-4be3-bcc9-89fa3e1f2dcc`
- Saved revision: `42dac4f3-75d7-4935-8e6b-810e61dccea7`
- Base volume: 40000 mm³
- STEP volume: 40392.699081697596 mm³
- Added volume: 392.699081697596 mm³, matching π × 5² × 5 within 1e-6 mm³.
- Reopened saved document contains diameter 10 and depth 5; downloaded STEP is one valid solid.

Artifacts: `/Users/oakky/Downloads/Direct sketch verification/` contains both STEP files and CAD documents, plus rectangle verification metadata.

## Automated checks

- `npm test --prefix frontend`: 30 passed, including new top/side/angled ray projection, pan/zoom/viewport-size round trips, degenerate profile rejection and explicit active-sketch extrusion reference checks.
- `uv run pytest backend/tests worker/tests -q`: 61 passed.
- `uv run python -m unittest discover -s worker/vendor/draft-drawing/tests`: 11 passed.
- `npm run build --prefix frontend`: passed. Existing bundle-size warning remains.
- `git diff --check`: passed.
- Existing Starlette/httpx deprecation warning remains.

## Limits

One closed profile per sketch; Smart Dimension drives rectangle width/height and circle diameter. Polygon points have coordinate editing but no persistent general length/angle constraint solver. Dimension label placement is temporary UI state; values persist in the existing sketch parameters. Face attachment remains a fixed plane snapshot. Imported STEP history reconstruction, general surface sketches, arcs, splines and full constraint relations remain unavailable.
