# LemonCAD: mechanical drawing practice for useful dimensions

Researched 2026-09-25. Primary sources only. Research and proposed behavior; no application changes. This is not an ASME/ISO compliance assessment.

## Evidence from drawing instruction and CAD documentation

### 1. Locate holes from their centers and a useful reference

MIT's drawing handbook separates hole diameter from location, demonstrates centerlines, and recommends dimensioning from a common line or surface rather than accumulating a chain of dimensions. It also stresses sufficient information without duplication and selecting the view that describes the feature clearly. Figures 27–29 provide concrete datum and hole examples. [MIT Design Handbook](https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/pages/related-resources/drawing_and_sketching/)

SOLIDWORKS defaults arc/circle distances to their centers and supports minimum/center/maximum extent conditions. Therefore a hole-to-edge dimension must expose which reference is being measured: hole center or nearest/farthest circumference. These are different answers. [SOLIDWORKS: Dimensions Between Arcs or Circles](https://help.solidworks.com/2020/English/solidworks/sldworks/c_Dimensions_Between_Arcs_or_Circles.htm)

**Recommendation (product inference):** Hole → straight edge should initially produce **Center to edge**. Hole → hole should initially produce **Center to center**. Offer explicit **Nearest gap** and **Farthest extent** alternatives where geometrically valid; never silently replace location with surface clearance. An edge is a reference selection, not automatically an engineering datum designation.

### 2. Keep model geometry readable

MIT describes extension lines, offset dimension lines and leaders, and shows outside callouts for hole size. It gives physical drawing spacing guidance, which should not be mistaken for fixed CSS pixel distances. [MIT Design Handbook, Dimensioning and Where To Put Dimensions](https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/pages/related-resources/drawing_and_sketching/)

**Recommendation (product inference):** Default labels outside the projected part silhouette, with thin extension lines or leaders tied to their actual feature. Labels should avoid each other and selected geometry. Reserve a modest annotation margin around the model. Permit dragging a label, retain its chosen position, and provide **Arrange dimensions** to recover from crowding. Do not cover the hole opening with a result badge. Model-space attachment and screen-space placement are separate concerns.

### 3. Direction and reference must be explicit

Fusion distinguishes horizontal/vertical linear measurements from aligned distances. Its ordinate dimensions measure X or Y offsets from a selected origin; its dimension tools place the result after selecting geometry. [Autodesk Fusion: Dimensions](https://help.autodesk.com/view/fusion360/ENU/?contextId=DWG-DIMENSIONS)

Inventor baseline dimensions use a shared origin and orthogonal offsets to selected points/edges. Ordinate sets align their annotations and permit repositioning overlapping text. Center marks explicitly identify selected circles/arcs. [Autodesk Inventor: Types of Drawing Annotations](https://help.autodesk.com/cloudhelp/2024/ENU/Inventor-Help/files/GUID-CF762D0C-A1F0-4D2C-8727-EB84A573E10F.htm)

**Recommendation (product inference):** Offer **Normal to face** for a clear planar working view, then compact **Horizontal / Vertical / Aligned** choices when applicable. Use **From same edge** to repeat a baseline reference and **Hole table** later for many holes. Do not make chain dimensions the automatic default. A generic 3D shortest distance and a drawing-plane projected location must have different labels and persisted measurement types.

### 4. Hole size is not a complete hole specification

Inventor's hole notes obtain diameter, depth and thread dimensions from model information and remain associated with the feature. The available information depends on the modeled feature, rather than the appearance of one circle. [Autodesk Inventor: Hole and Thread Notes](https://help.autodesk.com/cloudhelp/2022/ENU/Inventor-Help/files/GUID-162B828C-D6BA-4989-AA61-C9F4516D60D7.htm)

**Recommendation (product inference):** A circle first offers **Diameter**. A full hole callout requires reliable feature evidence: through/blind status, cylindrical depth, and any counterbore or countersink dimensions. Thread designation/pitch/class requires source metadata or user confirmation; do not guess it from nominal bore diameter. Do not infer THRU simply because the viewer can see through a tessellated opening. Keep diameter/location work in the first release; add structured hole-callout recognition separately.

### 5. Nominal geometry does not supply design tolerances

NIST distinguishes geometry, semantic PMI and graphical PMI. Semantic PMI can represent dimensional/geometric tolerances and datum features; graphical PMI describes their presentation. STEP can carry such information, but it must actually be present and interpreted. [NIST STEP File Analyzer and Viewer](https://www.nist.gov/services-resources/software/step-file-analyzer-and-viewer)

**Recommendation (inference from that distinction):** A geometry-only measurement must be presented as a nominal model measurement. Decimal display precision is not a manufacturing tolerance. Do not synthesize ± values, fits, datum identities or GD&T from shape. Preserve imported PMI where supported; otherwise allow explicitly authored tolerances with provenance. A generated draft drawing needs clear review status and must not claim automatic standards compliance.

## Recommended first interaction

1. Hover: highlight the actual candidate edge/hole and show a center mark, so selection is predictable.
2. Click the hole: keep it selected and show a diameter preview outside the part. Hint: **Select an edge or another hole, or place diameter.**
3. Click an edge: replace the preview with **Center to edge** and highlight both references. Do not retain an unwanted diameter annotation.
4. Place the suggested outside label with one click, or Enter to accept. Offer small **Center / Nearest / Farthest** options only when relevant.
5. Escape cancels the pending selection; selecting a completed dimension exposes edit/delete and reveals its references. Rotation must not change the measurement's geometric meaning.

This selection state is a LemonCAD proposal, not a claim that every source product uses this exact sequence. It fixes the present conflict between instant diameter results and selecting a second reference.

## Acceptance examples (synthetic geometry)

- Ø12 hole whose center is 20 mm from a straight boundary: center distance **20**, nearest gap **14**, farthest extent **26**, in the same plane with an adequate reference edge span.
- Two equal Ø12 holes with centers 40 mm apart: center distance **40**, nearest gap **28**, farthest extent **52**.
- Counterbored hole: selecting the upper rim must identify which diameter is selected, rather than silently choosing the through bore.
- Rotation/zoom: labels stay outside the visible part where space permits; leaders track references; stored value and dimension meaning remain unchanged.
- Unrelated, noncoplanar, skew or overlapping features: explain the available measurement type instead of applying planar radius subtraction blindly.
- PNG/PDF: export the same selected dimensions, units, references and annotation arrangement shown in the review view.

Drawing examples to inspect alongside implementation: [MIT common-reference example, Figure 27](https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/8777fee773bff3fe5b267a35e2271f12_fig_27.jpg), [hole example, Figure 29](https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/eb0cbcb3c3c6cb88bc08c882ad9629d7_fig_29.jpg), [leader example, Figure 24](https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/09083d8310afd90557f5bc2f70aceb68_fig_24.jpg).
