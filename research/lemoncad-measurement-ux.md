# LemonCAD: measurement that understands the user's selection

Research and proposed product specification · 25 September 2026 · No application changes.

## Decision

Make the core promise: **Drop a part, select features, get a clearly referenced dimension, export a readable view.** One canvas; no permanent measurement sidebars. Instant measurement is a preview. Keeping an annotation is a separate, explicit action so the first click remains available for a second reference.

## What the research supports

| Evidence | Consequence for LemonCAD |
|---|---|
| [SOLIDWORKS circle dimensions](https://help.solidworks.com/2020/English/solidworks/sldworks/c_Dimensions_Between_Arcs_or_Circles.htm) distinguish centre and minimum/maximum extents. | Hole location and wall clearance must be named alternatives, not an ambiguous distance. |
| [Onshape Measure](https://cad.onshape.com/help/Content/View/measure_tool.htm) reports measurements as entities are selected, distinguishes centre/minimum distances and coordinate components, and visualizes references. | Provide immediate preview, show the anchors, and identify the measurement's direction. |
| [Fusion dimensions](https://help.autodesk.com/view/fusion360/ENU/?contextId=DWG-DIMENSIONS) distinguish aligned, horizontal/vertical, baseline and ordinate dimensions. | Keep 3D distance separate from a dimension in a chosen drawing plane. Repeated hole locations should share a reference. |
| [Fusion dimension creation](https://help.autodesk.com/cloudhelp/ENU/Fusion-Drawing/files/DWG-CREATE-DIMENSION.htm) infers types from selected geometry and supports reassociating detached dimensions. | Infer the common case; preserve geometry references and flag invalid references after model replacement. |
| [MIT engineering drawing examples](https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/pages/related-resources/drawing_and_sketching/) demonstrate hole centres, common references, extension lines and leaders. | Separate hole size from location. Place annotations with clear connections to the feature. |

These are product inferences, not a claim that these tools share one interaction or that the proposal complies with a drawing standard. See [drawing-practice research](lemoncad-drawing-practice.md) for actual drawing examples, annotation practice and PMI limitations.

## Why the current interaction fails

- `frontend/src/main.tsx`: the first cylinder click immediately commits a diameter; `measure()` then clears selection. The user cannot continue that selection into a hole-to-edge pair.
- `backend/main.py`: the public measurement request accepts face IDs only. Clicking a visible boundary is not selecting its actual geometric edge.
- `worker/cad/icl.py`: indexed edges already exist but are not connected to the viewer measurement flow. Generic minimum surface distance is not hole-centre pitch. The cylinder-to-plane special case is not a general hole-to-edge operation.
- `frontend/src/Viewer.tsx`: projected midpoint labels lack automatic outside placement and collision handling.

Changing the toolbar alone cannot fix these issues.

## Selection and result contract

| Selection | Default preview | Relevant alternatives |
|---|---|---|
| One circular hole rim / identified cylindrical hole | Diameter | Choose another rim for a counterbore; do not conflate concentric features |
| Hole + straight coplanar edge | Centre to edge, perpendicular to the edge's supporting line | Nearest wall; explicitly show an extended reference if the perpendicular foot falls beyond the finite edge |
| Two coplanar hole centres | Centre-to-centre aligned distance | Horizontal / vertical in the selected plane; nearest wall when valid |
| One straight edge | Edge length | — |
| Two parallel planar faces | Perpendicular separation | — |
| Two nonparallel planes / appropriate straight edges | Angle | Clearly identify orientation and angle choice |

For a Ø12 hole with its centre 20 mm from a straight boundary, **centre-to-edge is 20 mm; nearest-wall clearance is 14 mm**. Both are useful; they answer different questions. Radius subtraction is valid here because the circle and reference lie in the same plane. Do not generalize it to skew axes, arbitrary curves or noncoplanar features.

For a straight boundary use its supporting line only when that relation is shown clearly. A shortest distance to a finite edge, a distance to an infinite line, and a distance to a face plane are distinct operations.

## Interaction

1. Hover highlights one actual feature, with a centre cross for a hole and an edge highlight for a line. Increase the screen-space hit target without changing the geometric reference. Resolve overlapping rims using a small candidate chooser.
2. Click a hole: show its diameter outside the part and retain selection. Hint: **Select an edge or another hole · Keep diameter**.
3. Click the edge: replace the transient diameter with **Centre to edge**. Highlight both anchors and the perpendicular construction. Edge-first selection produces the same result.
4. **Keep** or Enter saves the annotation and clears the selection. No manual label placement is required. A small context strip offers only valid alternatives. Dragging the suggested label is optional.
5. Escape cancels a preview. After two references, clicking a new feature starts a new preview; an unkept preview is replaced. Existing saved annotations remain unchanged. Show Keep clearly so this is predictable.
6. Clicking a saved annotation reveals its references and edit/delete actions. It must not intercept clicks inside the model silhouette.

When there is no unambiguous common measurement plane, ask the user to select a planar face / use **Normal to face**. Do not silently turn a 3D distance into a screen projection. Camera rotation never changes the stored measurement definition.

## Annotation placement

- Reserve an outer margin by fitting the part inside a smaller canvas region. Put text boxes outside the projected silhouette; dimension and extension lines may cross the view where needed.
- Use thin extension lines for linear dimensions and elbow leaders for diameter/radius. Show centre marks. Avoid covering selectable holes with badges.
- Pack labels into stable outer lanes; prevent label overlap and minimize leader crossings. Prefer short leaders without moving labels to a different side during every small rotation.
- Permit manual dragging and **Arrange dimensions**. Keep readable text size. At high density, use another saved view or selected annotations rather than piling text over the part.
- Maintain geometry anchors independently of label position. Distinguish hidden references visually. Exports use the same arrangement with print-appropriate sizing and no clipped labels.

## Implementation boundaries for the next change

**First release:** retained selection/preview; real STEP edge references; diameter, centre-to-edge and centre-to-centre semantics; exterior label layout; PNG/PDF parity. Touch viewer, measurement state/types, import geometry metadata and measurement API/worker. Do not change pricing, auth, folders or branding.

Persist relation, geometry references, reference plane, units, anchors and label placement—not just a number or a face pair. The same entities can have several valid dimensions, so deduplication must include relation and plane. Scope IDs to the imported model revision; do not assume topology IDs survive reimport. This changes the saved annotation payload; inspect compatibility before implementation and obtain approval for any database schema migration.

**Next:** repeated baseline dimensions, ordinate coordinates and hole tables, slots and structured hole depth/counterbore callouts. Thread information, tolerances and GD&T require source metadata or explicit authoring. Geometry alone cannot supply design intent; see [NIST PMI overview](https://www.nist.gov/services-resources/software/step-file-analyzer-and-viewer).

STEP measurements use analytical geometry where available. STL remains a separate, clearly marked approximate mesh-measurement flow. Decimal display precision is not a tolerance or a guarantee of source-model accuracy.

## Acceptance checks

- A Ø12 hole 20 mm from an edge returns 12 on the first click, then 20 after selecting the edge; Keep stores only the chosen result. Selecting the edge first gives 20 too. Clearance explicitly returns 14.
- Two coplanar Ø12 holes 40 mm apart return a centre distance of 40, not the surface gap of 28. Alternative measurements can coexist without being mistaken for duplicates.
- Counterbore rims, small holes, split cylinder faces and partially hidden edges have predictable selection; ambiguous cases do not silently select another feature.
- Horizontal/vertical results follow a stored reference plane, not the current camera. Noncoplanar cases require an explicit valid relation.
- Rotation, zoom and resize preserve values and references. Labels stay outside the part and avoid overlap at the supported annotation density; crowding has an explicit recovery action.
- PNG and PDF include every kept visible annotation without clipping. Existing saved drafts remain readable; invalid references are identified.
- Usability trial: five target users, no coaching, each measures diameter, hole-to-edge and hole pitch, then exports. Proposed gate: at least four complete all tasks within two minutes and can explain centre distance versus clearance. This is a proposed target, not a measured result.
