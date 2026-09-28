# CAD toolbar icon study

Date: 2026-09-27. Scope: four category tabs and clearer CAD command icons. Implemented after the user approved the visual study.

## Visual proposal

[Open the original LemonCAD icon study](assets/toolbar-icons/lemoncad-icon-study.svg). It shows the four labeled category icons, a toolbar at its intended SVG scale, and enlarged command examples. Visually checked in Chrome. Artwork is an original proposal, not copied vendor assets; the approved style is now implemented in the toolbar.

## Decision

Remove Assembly from this part workspace. Keep **Sketch, Solid, Surface, Sheet Metal**, each with an icon and its short label. Use original CAD-specific SVGs for modeling commands; retain standard utility icons for search, undo and redo. Category icons are a LemonCAD recommendation requested by the user, not a claim that SolidWorks uses this exact tab treatment.

## What the official references show

| Reference inspected | Observation | Useful for LemonCAD |
| --- | --- | --- |
| [SolidWorks simplified/default CommandManager image](https://blog-assets.solidworks.com/uploads/2025/12/simplified-interface-commandmanager-615x150-1.jpg.webp) | Line and rectangle have marked endpoints/corners; the arc shows curved geometry. The simplified toolbar exposes common tools, while the default groups more tools. | Show what a command creates. Give the primary tools stable, distinct silhouettes. |
| [SolidWorks sketch and extrusion strip](https://blog-assets.solidworks.com/uploads/2025/12/simplified-interface-sketch-tools-and-extrude-615x79-1.jpg.webp) | Smart Dimension has drafting dimension geometry; Extruded Boss/Base depicts a volume. The strip combines sketch drawing, dimensioning and extrusion. | Replace the ruler used for driving dimensions and the upload-like extrusion arrow. Keep Extrude reachable during sketching. |
| [Fusion Design toolbar image](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/images/app-example/design-toolbar-apr-2026.png) | Tabs divide modeling domains. Solid tools use small shaded geometric forms, with panel groups beneath. | Use mild face fills to distinguish volumes, skins and bent sheets; avoid photorealistic miniatures. |
| [Onshape sketch toolbar image](https://cad.onshape.com/help/Content/Resources/Images/sketch-tools/sketch-toolbar-01.png) | Sketch primitives show control points. Small arrows distinguish tool families. Utility commands, feature commands and sketch geometry have different shapes. | Endpoint marks help identify drawing tools; use flyouts only when working variants actually exist. |

All four images above were visually inspected, not merely linked. The SolidWorks images are also cached under `research/assets/solidworks/`. Fusion and Onshape images were inspected from temporary downloads; the original URLs remain the references.

The [SolidWorks article](https://blogs.solidworks.com/products/solidworks/solidworks-edu-2025-simplified-interface-for-teachers-and-students/) describes the teaching sequence as common sketch tools, dimensions/relations, then extrusion. Its simplified workspace is useful evidence for reducing visible clutter, not a mandate to copy its styling.

[Fusion documentation](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/GUID-0EEF7073-6CDE-4E31-AF1A-0811F969F031.htm) makes Sketch contextual and visually marks that temporary mode. [Onshape documentation](https://cad.onshape.com/help/Content/Sketch/sketch_tools.htm) describes flyouts and access to Extrude/Revolve directly from the sketch toolbar. These support clear mode feedback and a continuous draw → dimension → extrude flow.

## Problems in the current toolbar

Source inspected: `frontend/src/AuthoringToolbar.tsx`.

- `CornerUpRight` represents Arc, Fillet and Edge flange. A bent arrow cannot communicate three different geometric operations.
- `RotateCw` represents Revolve, surface revolve and Hem. Rotation about an axis and folding a sheet edge need different silhouettes.
- `Scissors` represents solid Cut, surface Trim and Corner relief. Scissors are reasonable for trimming sketch entities, but obscure removal of solid material.
- `Ruler` represents both Smart Dimension and Measure. One drives the sketch; the other reads model geometry.
- `Spline` represents a drawn spline, solid sweep and surface sweep. A curve alone omits the profile carried along it.
- `Shell` is a seashell symbol, rather than a hollow engineering body.
- Solid and surface extrusion share a bare arrow. Neither shows whether the result is a closed volume or an open skin.
- Categories have no icons; all commands use a uniformly thin 20 px Lucide treatment. Several unrelated operations become visually interchangeable.

## Recommended original icon vocabulary

These are LemonCAD design recommendations, not copied vendor assets.

| Category | Icon |
| --- | --- |
| Sketch | A planar outlined profile with three small editable vertices; optionally a short pencil tip |
| Solid | Closed isometric block, one lightly filled face |
| Surface | Open curved quadrilateral with one interior isocurve; no bottom/side thickness |
| Sheet Metal | Thin L-shaped folded sheet with a visible bend and parallel thickness edge |

| Command | Geometry to depict |
| --- | --- |
| Rectangle / Circle / Line | Square-corner rectangle with two corner nodes / circle with center mark / diagonal segment with endpoint nodes |
| Arc / Spline | True circular arc with center/endpoints / smooth curve with sparse control nodes |
| Smart Dimension | Two extension lines and opposing arrowheads, with a small dimension gap; no decorative ruler |
| Constraints | A recognisable perpendicular or tangent relation with a small constraint marker; no hyperlink chain |
| Extrude / Extruded cut | Profile becoming a closed prism, outward arrow / block with a visibly removed pocket, inward arrow |
| Revolve / Sweep / Loft | Profile and dashed axis with curved rotation arrow / section traveling along curved path / two differently sized sections joined by a skin |
| Hole | Block top with circular opening and a short bore wall |
| Fillet / Chamfer | Block corner with rounded transition / same block corner with flat diagonal bevel |
| Shell / Draft | Open hollow box with visible wall thickness / tapered block with neutral base |
| Linear / Circular pattern | Repeated small features along a line / repeated features around a center |
| Mirror | Matching geometry across a dashed plane |
| Surface extrude / revolve / sweep / loft | Corresponding operation, but an open edge and unclosed sheet silhouette, rather than a filled volume |
| Offset / Trim / Knit surface | Two separated skins with normal arrow / skin with removed segment / adjoining patches sharing a highlighted seam |
| Base flange / Edge flange | Flat thin plate / thin plate with an upright bent edge |
| Hem / Jog / Bend | Folded-back sheet edge / stepped sheet section / sheet folding about a marked bend line |
| Unfold / Fold / Flatten | Partly opened bend / closing bend / developed flat outline with dashed bend lines |

## Size, color and behavior

- Build on one 24 × 24 SVG grid. Use consistent optical weight (approximately 1.5–1.75 px) and equal visual bounds. Review at actual toolbar size, not just enlarged.
- Start with dark olive geometry, restrained pale face fills and one Lemon accent for the operated face or active tool. Color supplements silhouette; it must not be the only distinction between Add and Cut or Solid and Surface.
- Keep tabs icon + label. Keep command buttons icon-only by default, with name and one short action sentence on hover **and keyboard focus**. Retain the optional names toggle.
- Give controls roughly 36–40 px desktop targets; preserve larger targets for touch. Fit through overflow/scrolling rather than shrinking icons until unreadable.
- Order by workflow: **draw → dimension/relations → features**, followed by undo/redo. Separate small groups with space or a quiet divider.
- Unavailable operations stay visibly disabled with an honest reason. New icon artwork does not mean new CAD capability. Avoid misleading flyouts with no implemented variants.
- Keep recognisable utilities such as undo/redo/search from the existing set. Do not introduce detail that disappears when disabled or at normal scale.

## Scope for implementation

Touch `AuthoringToolbar.tsx`, a small CAD icon component, and toolbar-specific CSS only. Remove Assembly from both tabs and tool search. Preserve modeling callbacks, sketch state, keyboard navigation, tooltips and availability checks. No geometry, saved-document, solver or schema changes are needed.

Verify four category tabs, unique tool silhouettes at normal size, focus tooltips, keyboard tab switching, narrow-screen overflow, and unchanged rectangle → dimension → extrusion behavior. Run the existing frontend tests/build; this cosmetic revision does not require new geometry tests.

## Implementation verification

- Added `frontend/src/CadIcons.tsx`: original SVG artwork for all 45 modeling commands and the four category icons. Search, undo/redo and name-toggle utilities retain their standard icons.
- Updated `AuthoringToolbar.tsx`: four icon-and-label tabs; Assembly removed from both tabs and command search; custom icons used in toolbar and search results. Existing callbacks, availability checks, keyboard navigation and tooltips preserved.
- Toolbar CSS uses 24 px command icons, 22 px category icons and 38 px desktop controls; existing 44 px touch controls and horizontal overflow remain.
- `npm test --prefix frontend`: 30 passed. `npm run build --prefix frontend`: passed, with the existing bundle-size warning. `git diff --check`: passed.
- Live browser verification blocked: native Chrome returned black content screenshots and ignored page clicks/Tab input after repeated reconnect/reload attempts. The alternate browser connector reported no browser available. Rendering, tooltips and end-to-end drawing were not visually reverified for this cosmetic change. The prior drawing workflow's verification remains documented separately.
- No geometry, saved-data or backend changes for this icon update.
