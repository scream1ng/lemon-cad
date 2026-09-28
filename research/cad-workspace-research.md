# LemonCAD: conversational browser CAD workspace

Researched 27 September 2026. Primary sources only; all linked web sources accessed on this date. Vendor capabilities below are documented claims, not independent product tests. UI recommendations and implementation stages are our synthesis.

## Recommendation

Build a CAD workspace with conversation beside the model, explicit selection targets, and an editable feature tree. A user should be able to select a hole, write “make this 8 mm,” inspect a proposed change, and apply it; the same dimension must remain editable without conversation. Keep three different histories distinct: model construction, document versions, and discussion.

For the mechanical authoring concept, put the feature tree and properties on the left, give the center to 3D, and put conversation on the right. This deliberately revises the existing chat-left viewer layout; both side panels collapse. The user confirmed mechanical parts and assemblies as the priority. SOLIDWORKS supplies the feature-tree behavior; Onshape supplies browser collaboration; Shapr3D supplies selection-led simplicity; Claude Design supplies feedback on a specific visual element. This is a proposed combination, not a claim that any one product already supplies the whole workflow.

## Product comparison

| Product | Verified behavior | What LemonCAD should borrow | Boundary |
| --- | --- | --- | --- |
| SOLIDWORKS Design | Its left FeatureManager outlines construction of a part, assembly or drawing. Rollback temporarily returns to an earlier feature state and permits edits or inserted features. [Tree](https://help.solidworks.com/2026/English/SolidWorks/sldworks/c_featuremanager_design_tree.htm), [rollback](https://help.solidworks.com/2025/English/SolidWorks/sldworks/c_rollback_bar.htm) | Meaningful feature names, nested sketches, editable dimensions, rollback marker, clear downstream effects. | Reproduce the behavior, not the full ribbon or desktop density. |
| SOLIDWORKS xDesign | A separate browser-based design suite, usable without local installation; vendor explicitly distinguishes it from desktop SOLIDWORKS. [Product](https://www.solidworks.com/product/solidworks-xdesign) | Browser-first opening and cross-device access. | Do not equate a cloud-connected desktop product with an in-browser editor. |
| Onshape | Full-cloud CAD automatically saves actions. Feature and part lists, rollback, selection cross-highlighting, comments on entities, and immutable named versions are documented separately. [Getting started](https://cad.onshape.com/help/Content/Home/getting_started_with_onshape.htm), [features](https://cad.onshape.com/help/Content/PartStudio/features_and_parts_lists.htm), [comments](https://cad.onshape.com/help/Content/Collaboration/comments_on_workspaces.htm), [versions](https://cad.onshape.com/help/Content/Document/versions_and_history.htm) | Persistent document context; comments attached to geometry; separate model tree and versions; clear saved state. | Commenting is collaboration, not evidence of AI-driven geometry changes. |
| Autodesk Fusion | Parametric mode records features and relationships in a timeline; modifying referenced parameters recomputes downstream features. Direct modeling has different history semantics. [Modeling modes](https://help.autodesk.com/cloudhelp/ENU/Fusion-Designs/files/ASM-DESIGN-MODELING-MODES.htm) | Ordered construction history and parameter relationships. | A second permanent bottom timeline would duplicate a side feature tree in a compact workspace. |
| Shapr3D | History steps expose editable parameters, breakpoints, and filtering to the current selection. Direct editing and history are presented through selection-based modeling. [History](https://support.shapr3d.com/hc/en-us/articles/11567903089180-History), [direct versus parametric](https://support.shapr3d.com/hc/en-us/articles/14030415438748-Direct-vs-Parametric) | Select geometry first; reveal relevant tools and history; make panels optional. | Hiding the tree should not discard or flatten history. |
| FreeCAD | Parametric objects, constraint-based sketches and Open CASCADE BRep geometry; properties can depend on other objects. [Features](https://www.freecad.org/features.php) | An explicit model with dependencies and units; a useful reference for a future execution layer. | A kernel or desktop CAD engine alone does not provide a collaborative browser product. |
| VibeCAD browser beta | `vibecadstudio.com` describes cloud/browser natural-language parts and assemblies, booleans, chamfers, fillets, and STL/STEP/3MF export. It explicitly identifies itself as concept assistance rather than precision engineering software. [Official site](https://www.vibecadstudio.com/) | Low-friction prompt-to-part onboarding and iterative instructions. | Vendor beta claims were not tested. Do not infer manufacturing validity. |
| VibeCAD native platform | `vibecad.studio` describes conversation, editable parametric history and native builds. Its linked repository identifies its FreeCAD foundation and assistant context/selection behavior. [Site](https://vibecad.studio/), [repository](https://github.com/10-X-eng/vibecad) | AI edits should create inspectable model operations; pass explicit selection and current model context. | This is a different product from the browser beta. User's intended VibeCAD is not established. |
| Claude Design | Anthropic's April 2026 launch describes conversation, inline comments on elements, direct edits and adjustment controls; supported work includes prototypes with 3D. The September update places Design within Claude conversations. [Launch](https://www.anthropic.com/news/claude-design-anthropic-labs), [update](https://claude.com/blog/claude-design-stays-on-brand-for-daily-work) | Point to an element, describe an adjustment, refine visually. | These sources do not establish a mechanical CAD kernel, sketch solver, STEP authoring or parametric CAD feature tree. |

There are additional unrelated projects called VibeCAD, including an agent package and CAD skills library. The two products above are distinguished by domain rather than silently treating their claims as one product. [Agent package](https://pypi.org/project/vibecad/), [skills library](https://github.com/rawwerks/VibeCAD).

## Interaction decisions

### Start after login

Open a recent project or start with three clear actions: Describe a part, Import CAD, New sketch. A new user gets one editable sample bracket and a short task: select a hole and change its diameter. Returning users resume the same document, view, units and panel state. Avoid another marketing page after login.

Suggested desktop structure:

```text
Project / saved state                              New / Open   Export
Model / Versions       Sketch · Extrude · Hole · Fillet       Design with Lemon
Features               ┌────────────────────────────┐        Selected: Hole 2
  Base sketch          │                            │
  Base extrusion       │          3D canvas         │        Make it 16 mm
  Upright              │                            │
  Mounting holes       │  selection / comment pins  │        Change preview
  Edge fillet          └────────────────────────────┘        Apply / Discard
── rollback ──          mm · selection · view controls         Request / Note
Properties
```

Panels collapse independently. Preserve canvas space as width decreases; on tablet use one side sheet at a time. Small screens prioritize viewing, comments and parameter changes rather than pretending the full desktop sketch workflow fits.

### Comment to modify

1. Select a face, edge, body, sketch dimension or tree feature. Highlight it in both tree and canvas.
2. Choose **Modify with AI** or **Add comment**. Keep these separate so a review note cannot accidentally change geometry.
3. Show a target chip, such as `Hole pattern · 4 holes`, plus the current document version. “Make it larger” without a clear target or dimension requests clarification.
4. Produce a change card: `Diameter: 6 → 8 mm`, `4 holes affected`, and any dependency failures. Preview the proposed model with an obvious draft state.
5. **Apply** commits one transaction; **Discard** keeps the current model. Revalidate against the current document version before applying.
6. Link the applied response to affected tree nodes. Undo restores the complete previous transaction, not a partial collection of features.

The targeting pattern builds on Onshape's documented comments for features, faces, edges and dimensions; the AI proposal/transaction behavior is our recommendation. Onshape also documents that comments are not recorded in workspace history, reinforcing that discussion and geometry history should have separate meanings. [Commenting](https://cad.onshape.com/help/Content/Collaboration/comments_on_workspaces.htm).

### Feature history and precision

The feature tree is the construction recipe: sketches, extrudes, cuts, holes, patterns, fillets. Give each node an icon, descriptive name, state and editable parameters. Offer Edit, Rename, Suppress and Roll back here. Keep delete and reorder behind explicit dependency checks. The rollback state needs “Viewing through Hole pattern” and **Return to latest**; suppressed downstream steps remain visible and muted. SOLIDWORKS and Onshape both document this temporary rollback behavior. [SOLIDWORKS rollback](https://help.solidworks.com/2025/English/SolidWorks/sldworks/c_rollback_bar.htm), [Onshape feature list](https://cad.onshape.com/help/Content/PartStudio/features_and_parts_lists.htm).

A separate Versions panel holds saved document checkpoints, author and time. Undo means reverse an edit; rollback means evaluate part of the feature sequence; restore version means recover a saved document state. Onshape explicitly distinguishes immutable versions from editable workspaces. [Versions](https://cad.onshape.com/help/Content/Document/versions_and_history.htm).

Keep dimensions and units visible. Show sketch status with text as well as color: Under constrained, Fully constrained, Conflicting constraints. Explain the offending dimension when an edit cannot solve. SOLIDWORKS documents under-, fully-, and over-defined sketches and distinguishes unsolved or invalid geometry. [Sketch states](https://help.solidworks.com/2013/English/SolidWorks/sldworks/c_Sketch_Status_Conventions.htm). This is a long-established concept; the cited help edition is 2013, not a claim about new 2026 UI.

Selection should filter relevant history rather than make users search every operation. Shapr3D explicitly documents this selection filtering. [History](https://support.shapr3d.com/hc/en-us/articles/11567903089180-History). Always retain an obvious “Show all features” control.

### Mechanical assemblies — confirmed priority

Use a components tree at assembly level and the feature tree within each part. Show the fixed component, mate references, suppress/resolve state, and remaining movement in plain language. SOLIDWORKS documents movement within remaining degrees of freedom and mate-error diagnosis. Onshape packages allowed movement into mate types: Fastened removes movement; Revolute permits rotation; Slider permits translation. [SOLIDWORKS mates](https://help.solidworks.com/2026/english/SolidWorks/sldworks/t_Adding_Mates_SWassy.htm), [Onshape mates](https://cad.onshape.com/help/Content/Assembly/mates.htm).

The prototype uses a familiar mechanical example: a fixed bracket, seated spacer and concentric screw. A face-linked request adds a coincident head-to-spacer mate at zero offset. Preview shows the proposed seating; Apply adds a mate node and changes the remaining movement from slide + rotation to rotation only. This is an illustrative UI sequence, not a solved assembly. A production alternative is an outcome-based control such as **Allow rotation only**, translated into the chosen solver's mate representation.

Minimum assembly delivery: insert versioned part instances, fix the reference component, move unconstrained components, select face/axis pairs, create rigid/concentric/coincident mates, preview motion, undo, and explain conflicting constraints. Add exact interference checks before claiming fit validation. Keep per-part feature edits separate from assembly placement. Each mate/comment must reference a component instance and revision, not just the source part's face ID.

The user priority puts simple assemblies directly after the first dependable part-editing workflow. Advanced mechanisms, flexible subassemblies, drawings/BOM generation and multi-user concurrent editing can follow. No schedule or solver choice is established by this UI concept.

### Imports and failure states

Imported geometry starts as `Imported body · filename.step` unless native feature history has actually been recovered. Do not fabricate sketches and extrudes from a mesh or static import. Fusion documents that direct-mode geometry does not later become individual parametric features simply by enabling history; a base feature represents the prior geometry. [Modeling modes](https://help.autodesk.com/cloudhelp/ENU/Fusion-Designs/files/ASM-DESIGN-MODELING-MODES.htm).

Display Building preview, Preview ready, Could not rebuild, Saving, Saved and Connection lost as distinct states. Preserve the last good shape after rebuild failure and identify the first failing feature; never replace a valid model with a blank canvas. Onshape documents connection-lag indicators and recovery by rolling back the feature list. [Performance and recovery](https://cad.onshape.com/help/Content/Home/performance_considerations.htm).

## Existing LemonCAD boundary

The current browser renderer uses Three.js meshes and face metadata; STEP is read in the worker. Existing engineering chat explicitly receives file metadata and says it is text-only assistance, not a CAD execution tool. These are repository observations, not competitor claims: [Viewer](../frontend/src/Viewer.tsx), [loader](../worker/cad/loader.py), [engineering chat](../backend/engineering_chat.py).

A viewable mesh and a parametric model are different artifacts. Three.js documents BufferGeometry as vertex/index/normal buffers, whereas FreeCAD documents BRep solids, a constraint solver and parameter dependencies. Therefore a functional feature tree requires a modeling/document layer beyond rearranging viewer components. [Three.js](https://threejs.org/docs/pages/BufferGeometry.html), [FreeCAD](https://www.freecad.org/features.php). This is an engineering inference from those representations.

## Staged implementation proposal

| Stage | Deliverable | Acceptance gate |
| --- | --- | --- |
| 0 — design | Interactive workspace prototype: target selection, comments, proposal preview/apply/discard, feature tree and rollback demonstrations. | User can understand and complete the sample edit; all simulated CAD behavior is identified as prototype behavior. |
| 1 — online review | Existing real viewer plus persistent selections/comments, project restore, measurement and clear import state. | Reopen a project with the correct model, annotations and camera; selection never points to the wrong body. |
| 2 — real parametric core | One bounded part workflow: constrained sketch, extrusion, holes, fillet; document parameters, dependencies, rebuild, suppression, rollback and undo. | A saved bracket rebuilds deterministically after dimension edits; invalid changes retain the last valid result; export and reimport preserve expected geometry and units. |
| 3 — conversational edits | AI returns typed, allowed model operations against explicit targets and base version; isolated preview then atomic apply. | Same edit through UI and AI produces equivalent document state; stale proposals cannot overwrite newer work; failed/cancelled requests do not partially commit. |
| 4 — simple assemblies | Versioned component instances, fixed base, mates, remaining motion and conflict recovery. | The sample bracket/spacer/screw assembly rebuilds, moves only as constrained, saves and reopens; failed mates preserve the prior assembly. |
| 5 — expansion | Patterns, richer sketching, advanced assemblies and collaboration. | Add functionality against representative real models rather than promising an entire SOLIDWORKS replacement. |

These stages are sequencing recommendations, not time estimates. Persistence for features, versions, comments or proposals will likely require schema changes; those must be separately proposed and approved under the repository instructions before implementation.

## Material engineering risks

- **Geometry identity:** a comment or edit must reference a stable semantic entity, not only a transient triangle index. Topology can change after rebuild; unresolved targets must require reselection. Open CASCADE provides named-shape mechanisms for maintaining topological attributes, but choosing a robust mapping strategy remains implementation work. [TNaming](https://dev.opencascade.org/doc/occt-7.2.0/refman/html/class_t_naming___builder.html).
- **Preview versus valid geometry:** use kernel validation, numerical checks and export/reimport checks for supported operations. A convincing render alone is insufficient. Open CASCADE exposes shape-integrity checks; these do not by themselves establish manufacturability. [TransferBRep checks](https://dev.opencascade.org/doc/occt-7.9.0/refman/html/class_transfer_b_rep.html).
- **Solver and dependency failures:** edits to early sketches can invalidate later features. AI needs bounded operations and structured failure responses; the UI needs recoverable error states. The behavior should be proven on the actual chosen kernel and solver.
- **Concurrent work and latency:** proposals must carry a base version, cancellation must avoid partial commits, and saved state must distinguish local edits from server acknowledgement. Do not show collaborator avatars or saved status unless they reflect real state.
- **Scope:** a real browser CAD editor is a modeling product, not a chat redesign. The prototype can settle usability first; production editing requires the staged document and geometry work above.

No pricing recommendation, comparative speed ranking, or vendor reliability ranking is made: those would require additional plan-specific checks and hands-on tests.

## Delivered concept and verification

- Open [the interactive workspace](../plan/cad-design-workspace.html) directly, or serve the repository root and visit `/plan/cad-design-workspace.html`.
- Six sample states: part editing, change review, constrained sketch, STEP import, assembly, and rebuild failure. Local sample interactions only; no CAD execution, AI calls or saving.
- Browser checked: desktop and compact layout, part preview/apply/undo, assembly preview/apply and mate-tree update, sketch illustration. Browser review caught an SVG visibility issue, which was corrected and rechecked.
- JavaScript syntax, unique HTML IDs, script element references, and `git diff --check` passed. Existing frontend tests stopped at missing dependency `three`; no tests were changed or skipped. The chained build did not run. Backend tests are outside this static concept change.
- App source, schema, dependencies and existing design files remain untouched. Only this research and the new concept file were added.
