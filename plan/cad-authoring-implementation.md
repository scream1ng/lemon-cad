# CAD authoring: implementation and verification plan

Status: workspace and initial native-part workflow implemented locally. CAD document extension approved by the user on 27 September 2026. Advanced modeling stages remain incomplete.
Reference: [approved UI direction](cad-design-workspace.html).

## Outcome

Turn the two-card prototype into a real mechanical CAD workspace: Chat / History on the left, a persistent 3D viewport on the right, contextual icon tools, editable features, exact previews, and durable projects. Preserve the existing viewer and measurement workflows.

“All functions work” means geometry operations change an exact CAD model, survive save/reopen, and pass tests. A tooltip, explanatory panel, animated SVG, or successful API response alone does not satisfy this requirement. Unimplemented commands must be visibly unavailable in the real app, with a short reason; enable each only after its acceptance gate passes.

## What the code actually provides

- `frontend/src/Viewer.tsx`: Three.js viewing, STEP face/edge picking, measurements, orientations, PNG/PDF export, resize handling. No sketch editor or geometric feature execution.
- `backend/main.py`: files, folders, projects, immutable revisions, optimistic revision conflict detection, sharing, import/measure/drawing jobs. Existing project save can rename a project. No parametric authoring routes.
- `backend/db.py`: `Revision.state` and `Job.input/result` are JSON. Files and job artifacts already have immutable storage keys.
- `worker/runner.py`: import, measure, drawing, and costing dispatch. No authoring operation dispatch.
- `worker/cad`: OCP import, topology indexing, mesh output, and measurement. Current numeric face/edge IDs belong to a particular shape; they are not stable parametric references.
- `backend/engineering_chat.py`: text-only, entitlement-protected assistance. No typed CAD proposals or apply action.
- Prototype: hole, fillet and mate changes are scripted illustrations; 37 added commands open selection briefs. The file drawer uses memory-only sample objects.

## Approved architecture and schema boundary

Reuse React, Three.js, the existing OCP worker, queue, file storage and project revisions. Do not add a second rendering engine or replace authentication.

A versioned CAD document is a **new persisted JSON data contract**, even if no SQL column is added. Proposed `Revision.state.cad_document` fields:

- `schema_version: 1`, `kind: part | assembly`, canonical `units: mm`.
- Stable feature IDs, feature type, validated parameters, parent dependencies, suppression and rollback position.
- A base imported STEP file reference, or native sketch definitions and their local coordinate frames.
- Revision-bound selection references: originating feature, entity role and geometric signature. Ambiguous or missing references require reselection; never silently attach to a different edge after a rebuild.
- Applied comment/request references and typed operation provenance. Display preferences remain separate from geometric parameters.

Persist generated STEP/BREP and tessellation as immutable, owner-checked artifacts. A preview cannot change the current revision. Apply checks the base revision and geometry result, then creates one revision atomically. Cancel/failure retains the previous model. Reopen must resolve the exact stored geometry and document together. Prevent expired preview artifacts from becoming dangling revision dependencies.

**No SQL migration is proposed for the first slice.** If the existing JSON size limits, artifact lifetime, or assembly needs require table/column changes, present the exact migration separately before applying it. No migration, public deployment, commit, or push is authorized by this plan alone.

## Current delivery boundary

Implemented: fluid React workspace, categorized icon tools/help/search, Chat/History switch, real files/folders/search/rename, saved versions, exact native rectangle/circle profiles, extrusion, separated through-holes, and outer-edge fillets. Manual edits and explicit text commands share the preview executor. Feature IDs and dimensions regenerate geometry; suppression and rollback are supported after the base extrusion. Undo/redo is session-local; saved revisions survive reopening. Native STEP export, source access checks, and artifact retention are integrated.

Version one supports one fixed-origin XY sketch and one +Z extrusion, then holes and an optional final fillet. Rectangle fillets target four vertical outer corners; circular profiles target their two outer rims. References use these geometric roles rather than transient face IDs. The stored contract is intentionally narrower than the future general-purpose document below. Each native revision binds `cad_document` and `cad_job_id` to a completed exact-geometry job and source STEP; mismatches are rejected.

Still incomplete: general sketch constraints and freehand sketch editing, arbitrary face/edge authoring, imported STEP feature editing, general solid/surface/sheet-metal/assembly operations, pinned notes, and natural-language AI authoring. Their toolbar controls are disabled with explanations. Quick commands parse a small explicit grammar locally; the existing paid engineering chat remains separate. No unimplemented command simulates geometry success.

See [implementation verification](../research/cad-implementation-verification.md) for evidence and remaining gaps.

## Delivery sequence — remaining stages remain in scope

| Stage | Working deliverable | Exit condition |
| --- | --- | --- |
| 0. Baseline and coverage | Install locked dependencies, run existing suites/build, inventory every prototype command. | Record actual results; existing failures are flagged before feature work. |
| 1. Workspace and files | Real two-card React layout, accessible categorized toolbars/search, Chat/History switch, My files backed by existing APIs, folders/search/open/rename/save, adaptive layouts. | File changes survive refresh; unauthorized projects remain inaccessible; pending edits cannot be silently discarded; only supported tools are enabled. |
| 2. First complete modeling workflow | Native dimensioned rectangle/circle sketch → extrude → through-hole → fillet, exact selection, common manual/comment proposal editor, preview/apply/cancel, undo/redo, editable history and regeneration. | Edit thickness and hole diameter; dependent features rebuild correctly; save/reopen/export STEP reproduces the same dimensions and valid solid. Invalid fillet preserves last valid revision. |
| 3. Solid and sketch coverage | Remaining sketch entities/constraints and solid operations from the inventory below. | Each tool passes positive, invalid-input, geometry, dependency, undo and reopen cases. Constraint feedback is driven by a solver, not status text. |
| 4. Surface coverage | Surface creation, trimming, extension, offset and joining. | Expected surface continuity/topology and open/closed status are verified; operations fail clearly on unsupported selections. |
| 5. Sheet metal coverage | Thickness/bend model, flange/hem/jog/bend/corner workflows, forms, tabs/slots, fold/unfold/flat pattern. | Bend allowance and relief rules are explicit; folded and flat geometry are cross-checked against reference fixtures. Do not substitute a bounding rectangle for an unfolded part. |
| 6. Assembly coverage | Insert versioned parts, component transforms, fixed/free state, mates, movement and interference. | Mates resolve selected component references; remaining degrees of freedom and conflicting constraints are computed; component placement survives reopen. |
| 7. Full acceptance | Browser pass across every enabled control, error states and device sizes; all regression suites plus geometry corpus. | Every inventory item has recorded evidence. No mock geometry action is labeled complete. |

Sketch constraint solving, general sheet unfolding/forming and assembly mating require feasibility work beyond individual OCP shape constructors. Evaluate a solver against these acceptance cases before adding a dependency; report any licensing or architectural decision that changes scope. These are not treated as trivial UI wiring.

## Files expected to change

- UI integration: `frontend/src/main.tsx`, `style.css`, `WorkspaceSidebar.tsx`, `WorkspaceChat.tsx`, `CadToolbar.tsx`, `api.ts`; surgical selection/preview changes in `Viewer.tsx`.
- New focused modules: CAD command definitions, authoring workspace/history/editor, file drawer, validated CAD document types and feature state.
- Backend: separate authoring API module; narrow integration in `backend/main.py` for ownership, revisions and generated geometry resolution.
- Worker: new modules under `worker/cad/` for document validation, regeneration, operations and topology references; narrow dispatch/artifact integration in `worker/runner.py` and `worker/main.py`.
- Tests: meaningful frontend state tests, backend permission/transaction tests, worker geometric fixtures and browser acceptance evidence.
- Documentation: tool coverage and user-facing supported operations.

Keep Google login, password/session behavior, pricing/entitlements, public sharing permissions, vendor fixture engines and production infrastructure intact. Additive compatibility tests protect these boundaries. No unrelated cleanup or dependency upgrades.

## Verification contract for every modeling command

1. Correct selected input types, units and parameter validation; no NaN/infinite/zero-invalid dimensions.
2. Exact geometry changes verified independently: solid/surface validity, expected topology, volume/bounds/dimensions as appropriate. Rendering is not the geometry oracle.
3. Preview does not mutate the current model; cancellation, failure and double-submit cannot create unintended revisions.
4. Apply, edit, suppression/rollback, undo/redo, regeneration and save/reopen give deterministic results.
5. Changing upstream features resolves dependent selections or reports the first broken reference.
6. Jobs expose progress, cancellation, timeout and recoverable errors; user A cannot access user B’s preview or artifacts.
7. UI verified with pointer and keyboard; hover help dismissible; touch has reachable labels; 390, 768, 1280 and 1920 px layouts do not lose commands or the viewport.
8. Chat creates only validated, allowlisted operation proposals. It never executes generated code. Manual and chat actions use the same executor and review flow. Provider calls are mocked in automated tests; a separately identified configured-provider smoke test is required before claiming live AI verification.

## Baseline results

Locked frontend dependencies installed with `npm ci --prefix frontend --ignore-scripts`; locked Python environment installed with `uv sync --frozen --python 3.12`. Lockfiles unchanged.

- Frontend: **17 passed, 0 failed, 0 skipped**.
- TypeScript/Vite build: **passed**. Existing bundle-size advisory: one JS bundle exceeds 500 kB.
- Backend/worker suite: **24 passed** (`uv run pytest backend/tests worker/tests -q`), including the existing isolated-database workflow tests. One pre-existing Starlette/httpx deprecation warning.
- Draft-drawing suite: **11 passed** (`uv run python -m unittest discover -s worker/vendor/draft-drawing/tests`).
- Database tests target the existing isolated `lemoncad_test` database; production migrations were not run.

**Total: 52 automated tests passed, with no skipped tests reported.** These results cover the current product, not the unimplemented modeling toolset. No live browser acceptance run of a real authoring implementation is claimed; that implementation does not yet exist.

## Complete named toolbar inventory

Source inspection, not a claim of executed CAD tests. “Existing” means an implementation exists and needs the browser/acceptance checks above.

| Group | Command | Current real implementation | Required next evidence |
| --- | --- | --- | --- |
| Sketch tools | Finish sketch | No CAD authoring executor | Full command verification contract above |
| Sketch tools | Line | No CAD authoring executor | Full command verification contract above |
| Sketch tools | Circle | No CAD authoring executor | Full command verification contract above |
| Sketch tools | Arc | No CAD authoring executor | Full command verification contract above |
| Sketch tools | Spline | No CAD authoring executor | Full command verification contract above |
| Sketch tools | Rectangle | No CAD authoring executor | Full command verification contract above |
| Sketch tools | Dimension | No CAD authoring executor | Full command verification contract above |
| Sketch tools | Constraints | No CAD authoring executor | Full command verification contract above |
| Assembly tools | Insert part | No CAD authoring executor | Full command verification contract above |
| Assembly tools | Mate | No CAD authoring executor | Full command verification contract above |
| Assembly tools | Move | No CAD authoring executor | Full command verification contract above |
| Assembly tools | Interference | No CAD authoring executor | Full command verification contract above |
| Assembly tools | Show tool names | Prototype only | Persisted preference, keyboard and touch layout |
| Modelling tools | Sketch | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Extrude | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Revolve | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Sweep | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Loft | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Extruded cut | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Hole | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Fillet | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Chamfer | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Shell | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Draft | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Linear pattern | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Circular pattern | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Mirror | No CAD authoring executor | Full command verification contract above |
| Modelling tools | Measure | Existing viewer capability | Browser, selection/units and reopen regression |
| Modelling tools | Undo | No CAD-edit undo | Feature transaction history, redo and reopen |
| Modelling tools | Show tool names | Prototype only | Persisted preference, keyboard and touch layout |
| Surface tools | Extruded surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Revolved surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Swept surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Lofted surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Boundary surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Offset surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Trim surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Knit surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Fill surface | No CAD authoring executor | Full command verification contract above |
| Surface tools | Extend surface | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Base flange | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Convert to sheet metal | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Edge flange | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Miter flange | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Hem | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Jog | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Sketched bend | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Corner relief | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Forming tool | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Tab and slot | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Unfold | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Fold | No CAD authoring executor | Full command verification contract above |
| Sheet metal tools | Flatten | No CAD authoring executor | Full command verification contract above |
| View orientation | Show dimensions | Existing viewer capability | Browser, selection/units and reopen regression |
| View orientation | Isometric view | Existing viewer capability | Browser, selection/units and reopen regression |
| View orientation | Front view | Existing viewer capability | Browser, selection/units and reopen regression |
| View orientation | Top view | Existing viewer capability | Browser, selection/units and reopen regression |
| View orientation | Fit view | Existing viewer capability | Browser, selection/units and reopen regression |

Other controls: account/auth, new/open/import, export, folder creation/search/rename, history search, feature editing, rollback, versions, selection scope, comments/notes, preview comparison, Apply/Cancel, pending-edit guards, tool search and responsive navigation. Test each golden path and failure state when integrated; prototype click handlers are not substitutes for real tests.
