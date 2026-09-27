# CAD implementation verification — 27 September 2026

For the later version-two bracket-modeling milestone, see [bracket verification](cad-bracket-verification.md). The results below record the earlier version-one delivery.

## Delivered locally

The approved two-card workspace is implemented in React at http://127.0.0.1:5178.
It uses the existing Three.js viewport, OCP worker, authentication, storage, and revisions.
The user explicitly approved the new CAD document data contract. No SQL migration,
dependency upgrade, commit, push, or deployment was performed.

Native parts support a dimensioned rectangle or circle on a fixed XY plane, a +Z
extrusion, separated through-holes, and a final outer-edge fillet. Features can be
edited, suppressed, and rolled back with exact regeneration. The initial sketch
creates a 10 mm extrusion; its depth is editable in History. Rectangle fillets round
the four vertical outside corners; circular fillets round the two outside rims.

Manual edits and a small text-command grammar share the same exact preview executor.
Preview and Cancel preserve the applied model. Apply updates the local draft;
**Save** creates an immutable revision. Undo/redo is session-local. Geometry edits
clear measurements rather than silently reattaching annotations to different topology.

My files uses real folder/project APIs; it supports folder creation, navigation,
search, opening, renaming and existing sharing/publishing actions. Saved versions
are separate from feature history. Shared viewers can see only permitted versions.

## Automated evidence

- `npm test --prefix frontend`: **21 passed**.
- `uv run pytest backend/tests worker/tests -q`: **31 passed**.
- `uv run python -m unittest discover -s worker/vendor/draft-drawing/tests`: **11 passed**.
- `npm run build --prefix frontend`: passed (existing large-bundle advisory).
- `git diff --check`: passed.
- Total: **63 passing tests**, no skipped tests reported.

New checks cover exact volumes for both profiles, hole removal, fillet validity,
upstream changes, suppression/rollback, exported STEP round-trips, invalid dimensions,
overlapping holes, authorization, preview isolation, generated-document provenance,
artifact retention, save/reopen, rename ownership, revision conflicts, and published
revision access. Frontend tests cover safe command parsing and viewport/label fitting.

The only suite warning is the existing Starlette/httpx TestClient deprecation.

## Real browser evidence

Used native Chrome through the computer-use interface and a local test account.

- Created and previewed an 80 × 50 × 10 mm native rectangular part, then applied it.
- An oversized hole was rejected with the original geometry still visible.
- A corrected Ø12 mm through-hole previewed and applied successfully.
- Text commands generated real through-hole and R2 outside-corner fillet previews.
- Undo removed the fillet; redo restored both the feature row and rounded geometry.
- The viewer measured the actual generated hole at **Ø12.00 mm**.
- Saved the geometry and measurement, renamed the project to **Drilled plate**,
  created **Mechanical parts**, and reopened the saved project through My files.
- Reopened history contained sketch, extrusion, hole, and fillet; its saved Ø12
  measurement survived. Versions listed the initial and revised drafts.
- Visually checked normal desktop, 430 px phone, **390 × 844 phone**, and
  **768 × 844 tablet** layouts. Chat composer remained reachable by page scrolling.
- Fixed portrait camera clipping and offscreen saved measurement labels discovered
  during those checks. Added regression tests for both.

The final browser console at its default levels showed the React DevTools notice
and a browser-extension session message, with no application error shown. Native UI
control intermittently failed during testing; desktop mode was restored and visually
verified afterward. No completed browser sweep of every enabled action or live
AI-provider smoke test is claimed. STEP export/round-trip and circle geometry were
verified automatically; a browser download and circle-creation flow were not
separately exercised.

## Remaining gaps

This is the first native modeling workflow, not the complete SolidWorks-like engine.
General sketch constraint solving/freehand sketching, arbitrary face/edge authoring,
imported STEP feature editing, remaining solids, surfaces, sheet metal, assemblies,
pinned notes, and AI natural-language CAD proposals are not implemented. Their
modeling toolbar controls remain disabled with reasons; there are no fake successes.
The quick command parser does not call an AI provider. Existing entitlement-gated
engineering chat is retained for imported-part workflows.

General authoring/solver work remains in the implementation plan. The current
persisted v1 contract intentionally admits only operations the exact executor supports.

## Technical reference

Geometry construction uses the existing OCP 7.8 installation. Method signatures
were checked against the installed bindings and the primary Open CASCADE reference:
[BRepPrimAPI 7.8](https://dev.opencascade.org/doc/occt-7.8.0/refman/html/dir_704a7e5560a6c9295599ba6d2166c65b.html),
[BRepFilletAPI_MakeFillet](https://occt3d.com/dev/doc/refman/html/class_b_rep_fillet_a_p_i___make_fillet.html).
