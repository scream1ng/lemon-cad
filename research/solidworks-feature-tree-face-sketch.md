# Compact feature tree and sketching from a face

Researched 2026-09-27. Primary SOLIDWORKS documentation only. Recommendations below are Lemon CAD design decisions, not claims that SOLIDWORKS uses a particular web layout or row height.

## Findings

| Topic | Documented SOLIDWORKS behavior | Source |
| --- | --- | --- |
| Hierarchy | Normal tree view nests sketches under the features that use them. Flat Tree View exposes sketches and curves in creation order instead. The documentation includes side-by-side images of these two trees. | [FeatureManager Design Tree Views](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_fmdt_views.htm) |
| Expand/collapse | An indicator before an item means it contains associated items. Users expand it individually or collapse the whole tree. | [Tree Conventions](https://help.solidworks.com/2023/english/Solidworks/sldworks/c_FeatureManager_Design_Tree_Conventions.htm) |
| Names and details | Features can display their names. Descriptions are optional and hidden by default when identical to the name. | [Tree Display Options](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_featureManager_tree_display_options.htm?id=2.8.3) |
| Context actions | Selecting graphics or tree items can display a context toolbar of commonly used actions. Right-click adds the remaining relevant commands. | [Context Toolbars](https://help.solidworks.com/2022/english/Solidworks/sldworks/c_context_toolbars.htm) |
| Tooltips | Toolbar hover can show only the tool name or an expanded description, optionally with an image or animation. | [Enhanced Tooltips](https://help.solidworks.com/2020/english/WhatsNew/r_enhanced_tooltips_wn.htm) |
| Face-first sketch | Select a sketch plane or planar face, then enter Sketch mode. Plane selection may also follow the sketch command. Clicking a sketch tool such as Rectangle is another way to enter sketch mode. | [Sketching Concepts](https://help.solidworks.com/2024/English/SolidWorks/acadhelp/t_Sketching_Concepts_Overview.htm?id=7d682a4fdecf470e8a34d42e54f1de8f) |
| View orientation | An option rotates the view normal to the plane on sketch creation or editing. Cancelling restores the preceding orientation; accepting keeps the normal view. | [Auto-Rotate View on Sketch Edit](https://help.solidworks.com/2018/english/WhatsNew/c_auto_rotate_view_sketch_edit.htm) |
| Curved faces | Ordinary planar sketch creation is distinct from surface workflows. Wrap maps a sketch onto nonplanar faces; surface splines constrain their points to the surface. Hole Wizard uses 3D sketches when selecting nonplanar faces. | [Wrap](https://help.solidworks.com/2023/english/SolidWorks/sldworks/HIDD_DVE_SURF_WRAPPING_SKETCH.htm?id=23.6.39), [Splines on Surfaces](https://help.solidworks.com/2019/english/SolidWorks/sldworks/c_Splines_on_Surfaces.htm?id=f22538ec3b7c41b7b0d073f42ba7e9a0), [Hole Wizard](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_Hole_Wizard_Overview.htm?id=23.6.25.4.0) |

## Recommended Lemon CAD behavior

### Compact history

- Use one 30–32 px desktop row per feature: disclosure arrow, small icon, numbered name, optional short value. Keep touch rows larger through coarse-pointer styling.
- Nest a consumed sketch under its extrusion or cut, collapsed initially. A typical 48-entry sequence of 24 sketch/operation pairs becomes 24 visible feature rows. Unconsumed sketches remain visible.
- Use distinct labels such as `Extrude 1`, `Cut 1`, and `Sketch 1`; derived labels avoid a saved-data change. Keep the stable feature ID as the edit target.
- Move plane, offset, and source-sketch details into hover/focus help and the editor. Remove the permanent second line.
- Reveal secondary actions on hover, keyboard focus, or selection. Preserve accessible names and touch access. Suppression must remain labelled as suppression, not visibility: those operations differ.
- Search includes hidden sketch children and temporarily reveals matching descendants with their parent. Collapsing is presentation only: never reorder or delete the saved feature list.
- For reused sketches, do not hide every route to the shared sketch. Nest only unambiguous single-consumer sketches or show an explicit shared reference.

### Select face → Sketch

- Highlight the exact hovered/selected face, not the whole body. A click selects; a nearby `Sketch` action starts editing. This leaves orbit and ordinary selection predictable.
- Prepopulate the selected face's plane and offset, center the initial profile on the selected location, and orient normal to that plane. Do not ask users to type offsets they have already chosen geometrically.
- Keep the toolbar Sketch/Rectangle/Circle commands compatible with the current selection. Without a selection, retain the existing explicit plane choice.
- Show the selected face as context in the sketch workflow. Do not imply that a separate blank 2D canvas is drawing directly over the 3D model unless an in-viewport overlay is actually implemented.
- Explicitly distinguish unsupported curved faces and angled planar faces from supported faces. Never silently flatten a curved face or choose a nearby principal plane.

## Current contract boundary

Local inspection: `backend/cad_document.py` defines only XY/XZ/YZ planes plus a scalar offset; `frontend/src/CadHistory.tsx` renders each sketch and operation separately with persistent detail lines.

The compact hierarchy needs no document change. Principal-plane-aligned face selection can reuse the existing plane/offset contract if the viewer can identify a complete planar face reliably. This is a fixed work plane, not an associative attachment that follows subsequent face changes. Arbitrary angled planes and persistent face attachment require an additional modeling design and saved-data approval; do not present the restricted version as equivalent to the full SOLIDWORKS workflow.

## Verification targets

- All existing features remain editable after collapse, expand, search, rollback, and suppression; duplicate labels do not change the wrong feature.
- The long bracket shows approximately half as many top-level rows without second-line details.
- Sketch creation from supported top, side, and bottom faces uses the correct plane/offset; outward add and inward cut directions are checked separately.
- Camera orbit is not mistaken for selection; cancelling sketch creation restores the previous model and camera.
- Curved/angled unsupported selections explain the limitation; saved/reopened sketches retain their actual position.
