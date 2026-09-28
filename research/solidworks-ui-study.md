# SOLIDWORKS UI study for LemonCAD

Researched 2026-09-27. Scope: mechanical parts and assemblies, desktop SOLIDWORKS interaction patterns, and the separate browser-based xDesign product. Official Dassault Systèmes/SOLIDWORKS sources only. This study supplements [workspace research](cad-workspace-research.md) and [toolbar research](cad-authoring-toolbar.md).

**Visual companion:** [Open the annotated picture board](../plan/solidworks-ui-reference.html) — 11 inspected official images, source captions, topic filters and enlarged views. [Image source manifest](assets/solidworks/sources.json).

**Design conclusion:** keep LemonCAD's spacious model canvas and targeted comments, then add the precision of a CAD command editor: explicit selections, dimensions, preview, acceptance, and visible dependency/failure feedback. A row of icons alone does not supply that workflow.

Evidence below distinguishes documented behavior from proposed LemonCAD decisions. Help years identify the documentation edition, not necessarily when an illustration was captured; publication dates are stated only when available. No desktop installation was operated in this study.

## 1. The strongest visual reference: SOLIDWORKS already has a simpler workspace

The official **Simplified Interface, 2025 FD04** documentation shows paired simplified/default pictures. It introduces Basic Modeling, Basic Assembly, and Basic Drawing tabs, reduces view controls, collapses some PropertyManager sections, and hides the MotionManager. It retains the engineering structure while reducing the initial command surface. [Official comparison pictures and behavior](https://help.solidworks.com/2025/english/WhatsNew/c_wn2025_ui_simplified_interface.htm?id=5.2).

**LemonCAD implication:** begin with a small Basic tools set and an obvious All tools/search route. Preserve access to precision settings through expandable sections. Do not present every specialist command at first login.

## 2. Screen anatomy and why each region exists

The official **2025 UI overview** identifies the menu bar, CommandManager, tree and its filter, PropertyManager, ConfigurationManager, breadcrumbs, viewport toolbar, graphics area, search, and task pane. [Annotated official UI illustrations](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_user_interface_overview.htm?id=3.0).

| Region | What the documentation establishes | Proposed LemonCAD treatment |
| --- | --- | --- |
| CommandManager | Its default toolbars follow document type; tabs expose tool groups. Button text is configurable. [2025 CommandManager](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_commandmanager.htm?id=3.13.4.2) | Separate **Part / Sketch / Assembly** contexts. Keep common groups stable; show the current context in text. |
| Heads-up toolbar | Common view manipulation sits inside each viewport. [2025 Heads-up View Toolbar](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_heads_up_view_toolbar.htm?id=3.5.4) | Put orientation, fit, section, display mode and isolate near the canvas. Keep these apart from shape-changing commands. |
| Tree and command editor | Tree structure, command properties, and configurations have distinct tabs in the documented anatomy. | Left: searchable model structure. When a command begins, expose a focused editor while retaining a way to inspect its references. |
| Right-side auxiliary space | The anatomy identifies a separate Task Pane. | Use this space for Lemon's comments/change requests. The February 2026 assistant examples below also use a side panel; LemonCAD's exact edit transaction remains our proposal. |

Recommended initial command groups, as a **LemonCAD proposal**:

- **Part:** Sketch; Extrude/Cut; Revolve; Hole; Fillet/Chamfer; Pattern/Mirror. Move advanced surfaces, sweeps and lofts into All tools initially.
- **Sketch:** Line, Rectangle, Circle, Arc; Dimension; Trim; Relations; Finish sketch.
- **Assembly:** Insert part; Mate; Move; Isolate; Explode; Measure/Interference.
- **Persistent:** Undo/Redo, tool search, view navigation, units, save/rebuild status. Do not confuse Undo with rolling back the feature sequence.

## 3. Icons need more than hover labels

Desktop SOLIDWORKS **2025** offers small name-only tooltips, larger descriptive tooltips, and larger tooltips that may contain a picture or animation. Icon size, text and context-toolbar visibility are configurable. It is not universally icon-only. [Customize Toolbars](https://help.solidworks.com/2025/english/Solidworks/sldworks/HIDD_CUSTOMIZE_TOOLBARS.htm).

**Proposed hover card:** command name → small before/after illustration → one-sentence result → required selection → shortcut, only if implemented. Example: **Fillet — Round selected edges. Select one or more edges, then set a radius.** Keep names available on focus and in the labeled mode; hover cannot be the only teaching route.

The **2025 S-key shortcut bars** are separately customizable for Part, Assembly, Drawing and Sketch and include search; arrows, Enter and Escape support keyboard use. These mode-specific bars are distinct from selection-specific context toolbars. [Shortcut Bars](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_shortcut_bars.htm?id=4.4.1.3).

Search can both execute a command and reveal its UI location; unavailable commands remain identifiable in the results. [2025 Searching for Tools](https://help.solidworks.com/2025/English/SolidWorks/sldworks/t_searching_commands.htm?id=9be0efb2c7724e5b846b3acd042e0d1b).

**Proposal:** add a visible Find a tool entry before adding a configurable shortcut palette. Search synonyms such as “round edge” → Fillet can teach CAD terminology. Show the reason an action is unavailable.

## 4. Selection is an explicit part of the command

Selection breadcrumbs connect a picked entity to its feature, sketch, component or assembly context. They also expose related mates and failures. This detailed source is **2024 Help**, not evidence of a new 2026 feature. [Selection Breadcrumbs](https://help.solidworks.com/2024/English/SolidWorks/sldworks/c_selection_breadcrumbs.htm?id=fcf8594c12024b96aac5243d6e7c148e).

Selection filters constrain picking to entity types such as edges, faces, features or components; **2026 Help** lists these separately. [Selection Filter Toolbar](https://help.solidworks.com/2026/english/SolidWorks/sldworks/r_selection_filter.htm?id=2.12.4.1.26).

**Proposal:** show a compact path such as `Bracket / Mounting holes / Hole 2 / Cylindrical face`. Allow choosing the intended scope before a comment changes geometry. A request about “this hole” must not silently become a change to all holes in its feature. Add visible Face / Edge / Body / Component picking modes as selection complexity grows. Keep the current filter visible and easily cleared.

## 5. PropertyManager: the missing bridge between icons and accurate work

The **2026 Japanese PropertyManager overview** documents grouped options, active selection boxes, linked viewport highlighting, guidance messages, and OK/Cancel/preview controls. The Japanese edition was readable where the corresponding English URL did not reliably return topic content. [PropertyManager overview, 2026](https://help.solidworks.com/2026/japanese/solidworks/sldworks/r_pm_overview.htm).

Detailed previews can distinguish new/modified faces or bodies for extrudes, ribs and drafts; this is a documented subset, not a promise for every tool. [Feature Previews, 2026](https://help.solidworks.com/2026/english/SolidWorks/Sldworks/hidd_dve_feat_preview_dlg.htm).

**Proposed LemonCAD command editor:**

1. Tool title and plain-language purpose.
2. Required selection fields, with named selected entities and remove buttons.
3. Key dimensions with units and validity feedback; advanced options collapsed.
4. Visible preview state and highlighted affected geometry.
5. **Apply / Cancel** with consistent placement; retain entered values when validation fails.

Manual commands and comment-driven proposals should populate the same editor and produce the same editable feature. A comment can suggest a radius; the user can still type its exact value. Preview is provisional; applying creates or edits a feature. This shared behavior is a design proposal, not a researched claim about SOLIDWORKS AI.

## 6. Feature history is a model recipe, not a list of saved snapshots

The **2025 tree filter** searches names, feature types, sketches, folders, mates and tags. [Filtering the FeatureManager](https://help.solidworks.com/2025/English/SolidWorks/sldworks/t_filtering_the_featuremanager_design_tree.htm?id=43eeef300f5a4c13a64682917f09e5f1).

Rollback temporarily changes the point reached in the regeneration sequence; features below it become unavailable. Users can edit or add features while rolled back and then roll forward. [Rollback Bar, 2025](https://help.solidworks.com/2025/English/SolidWorks/Sldworks/c_rollback_bar.htm).

Parent/child visualization can show the references that connect features; the documented arrows are optional and disabled by default. [Viewing Feature Relationships, 2025](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_viewing_feature_relationships.htm?id=b091a6ac73cc4c48b383263580325e7c).

**Proposal:** keep four concepts distinct in LemonCAD:

| Concept | User question | UI |
| --- | --- | --- |
| Feature tree | How was this shape made? | Ordered features, nested sketches, dependencies, suppression/error states. |
| Rollback position | What did the model look like before this operation? | Visible insertion/rebuild position, muted later features, Return to end. |
| Saved versions | What did we save or approve previously? | Named snapshots, time/author and comparison. Proposed cloud document behavior. |
| Comment/change record | Why was this changed? | Geometry-linked request plus link to affected feature and resulting version. |

Do not use a single gray style for hidden, suppressed, failed and rolled-back items. Use distinct icons and plain-text status on inspection. Show the downstream impact before suppressing or deleting a referenced feature. Keep imported geometry labeled as imported unless editable construction history has actually been recovered.

## 7. Sketch feedback must explain remaining freedom

SOLIDWORKS **2026** distinguishes under-defined, fully defined, over-defined, unsolved and invalid sketch states. Full definition is not mandatory before creating a feature unless the relevant setting requires it. [Sketch Status Conventions](https://help.solidworks.com/2026/English/SolidWorks/sldworks/c_Sketch_Status_Conventions.htm?format=P&value=).

Relations may be inferred while drawing or added/edited afterward; they capture relationships such as parallelism and equality. [Sketch Relations Overview, 2025](https://help.solidworks.com/2025/english/Solidworks/sldworks/c_Sketch_Relations_Overview.htm).

**Proposal:** retain exact editable dimensions, show relation symbols near selected geometry, and pair colors with text. “Under constrained — centre can move horizontally” is more useful than a status dot. Provide a Show remaining movement action once a solver can support it. When constraints conflict, identify the offending relations and let the user choose a repair; do not silently remove design intent to satisfy an AI request.

## 8. Assemblies need constraint feedback, not just an exploded picture

The **2025 Mate PropertyManager advanced tab** filters mate types by the selection, offers previews and alignment changes, and can make the first component transparent to aid the second pick. [Mate PropertyManager](https://help.solidworks.com/2025/english/Solidworks/sldworks/r_mate_pm_advanced.htm).

SOLIDWORKS **2026 mate guidance** recommends checking remaining freedom by dragging components, avoiding redundant constraints and circular chains, and fixing mate errors promptly. A component intentionally allowed to move need not be fully fixed. [Best Practices for Mates](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_Best_Practices_for_Mates_SWassy.htm?id=7.7.1).

**Proposal:** guide users through two named selections, show the proposed mate, preview alignment, and explain remaining movement: “Sliding stopped; rotation remains free.” Keep a Mates group and mark fixed/floating components. Distinguish moving the camera from moving a component. Diagnose conflicts against existing mates instead of presenting an unexplained failed operation.

Configurations are design variations of parts or assemblies. [Creating Configurations Manually, 2025](https://help.solidworks.com/2025/English/SolidWorks/sldworks/t_Creating_a_Configuration_Manually.htm). **Proposal:** place variants such as Short / Long in a separate selector when needed; a variant is not a prior saved version. Do not add configuration complexity to the first simple-part workflow.

## 9. Recovery belongs in the workspace

SOLIDWORKS **2026** lists distinct diagnostic tools: feature warnings/errors, sketch-relation inspection, SketchXpert, sketch repair, import diagnostics and MateXpert. These address different problem classes. [Troubleshooting Resources](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_SOLIDWORKS_Troubleshooting_Resources.htm).

Some long regenerations/previews can be interrupted. The documented behavior may complete the current feature before stopping; certain command cancellations return to the PropertyManager with settings retained. [Interrupt Regeneration of Parts, 2026](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_Interrupt_Regeneration_of_Parts.htm).

**Proposal:** attach a failed rebuild to the first failing feature, retain the last valid model, highlight the troublesome geometry and offer a specific correction. Example: “Fillet cannot rebuild after this hole grows. Review the highlighted edge or reduce the radius.” Show Calculating / Valid / Failed distinctly and support cancellation where the modeling engine allows it. Do not report manufacturability or solver success from a visual mockup.

## 10. Browser xDesign is a separate reference

SOLIDWORKS xDesign is browser-based; desktop CommandManager/PropertyManager observations above should not be attributed to it. The **2026x FD01** release, dated **6 February 2026** in the official [xApps index](https://blogs.solidworks.com/tags/solidworks-xapps/), discusses Action Bar refinements, clearer tooltips and command labels enabled by default for makers. [2026x FD01 announcement](https://blogs.solidworks.com/products/solidworks/whats-new-in-solidworks-xdesign-2026x-fd01/).

The **R2026x FD03** release, dated **10 July 2026** in that same official index, documents design tables and part families: parameter rows generate variations, and family members are separate physical products linked to the table. It also preserves visual preferences between sessions. [R2026x FD03 announcement](https://blogs.solidworks.com/products/solidworks/whats-new-in-solidworks-xdesign-r2026x-fd03-how-to-create-part-families-with-design-tables/).

**Implications:** browser delivery does not eliminate precise parametric structure. Keep the compact icon mode the user requested, but preserve an easy labeled mode. Borrow browser-oriented onboarding and persistent preferences without assuming xDesign and desktop SOLIDWORKS share identical controls or data models. These are selected verified releases, not a claim that every latest release or feature was audited.

## 11. Current prototype gaps and staged priorities

Inspection of [cad-design-workspace.html](../plan/cad-design-workspace.html) on 2026-09-27 found an illustrative SVG model, icon tooltips, tool-name toggle, basic feature/version tabs, scripted rollback, a constrained-sketch example, a targeted-hole preview and a scripted mate example. Its own disclosure says no AI or CAD execution. The source was inspected; no new browser regression run was performed for this research.

| Priority | Next design work | Reviewable success criterion |
| --- | --- | --- |
| P0: precise command editing | One complete Extrude or Fillet editor with selection fields, dimensions, preview, Apply and Cancel. | Manual action and comment request open the same inspectable proposal. Cancel preserves the prior model. |
| P0: selection scope | Named Face / Feature / Component target and linked tree highlighting. | The user can distinguish one hole from the whole hole feature before requesting a change. |
| P0: history clarity | Search, explicit rollback position, feature status and affected dependencies. | An earlier feature can be inspected without presenting that state as a saved version. |
| P0: recoverable failure | Failed feature and repair action, with last valid result visible. | A scripted invalid fillet explains the failing geometry and can be corrected without losing the request. |
| P1: learnable tools | Part/Sketch/Assembly contexts, Find a tool, illustrated hover cards and optional names. | A beginner can discover Fillet by its purpose and see required selections. |
| P1: sketch/mate feedback | Under/over-constrained examples and two-selection mate editor. | Users can tell what still moves and which relation conflicts. |
| P2: larger projects | Isolate, section, saved variants, reusable parts and deeper tree organization. | A multi-component example remains navigable without expanding every tool panel. |

P0/P1 can first be reviewed as interaction concepts. Production behavior additionally requires exact geometry, persistent entity references, feature regeneration, sketch/mate solving and transactional document storage. This research makes no implementation claim about those systems.

## Picture-review checklist

Use the official full-screen anatomy and Simplified Interface comparison first, then close-ups of CommandManager, PropertyManager, tree relationships, rollback, sketch diagnostics and mates. Every image needs its product/edition and direct source caption. A 2025/2026 documentation page may reuse older illustrations; do not relabel its image as a fresh screenshot of the newest release. Review images for workflow meaning, not simply visual density or icon color.

## 12. Recent assistant UI: explanation and review before generation

The official 25 February 2026 FD01 article presents beta workflows for error analysis, drawing generation and assembly structure generation. Its error-analysis screenshot places the assistant beside the feature tree, model and failure list. Its assembly example previews component hierarchy before generating part/assembly files. These are documented vendor workflows, not independent performance tests or proof that arbitrary conversational edits are reliable. [Official article and images](https://blogs.solidworks.com/solidworksblog/2026/02/whats-new-in-solidworks-2026x-fd01-design-and-modeling.html).

**LemonCAD implication:** a chat reply should point to the affected feature or proposed structure. For failed regeneration, explain the likely originating feature rather than repeating every downstream error. For new assemblies, review components and relationships before applying the change. Keep AI explanation, proposed action and verified result distinct.

## Visual artifact verification and limits

All 11 downloaded source images were opened and visually inspected before inclusion in the board. The PropertyManager screenshot is correctly described as Break Corner: its source filename mentions base flange, but its visible command is Break Corner. The 2025 overview visibly identifies SP1.0 while the education article discusses SP2; captions identify the article and flag this difference. Images retain original resolution and have not been generated or retouched. The board's highlighted regions are separate HTML annotations.

The board uses local image assets and a relative project stylesheet; it can be opened directly or served with the repository. Structural checks verify local image paths, unique IDs and JavaScript syntax. Research-only work does not change application behavior or resolve the previously reported missing frontend test dependency.

Browser review passed for the board layout, topic filtering, enlarged-image dialog and source captions. All reference images were inspected individually; no screenshot is an AI-generated reconstruction.
