# CAD canvas code review / QA — 2026-09-27

Scope: current native CAD authoring changes, especially right-canvas editing, rectangle-to-edge positioning, preview / apply / cancel, and saved-document provenance. This was a code-read and automated test pass; live browser QA could not be completed.

## Findings fixed

1. **Cut could silently reuse an additive extrusion.** When a sketch already had an extrusion, the sketch-to-extrusion transition ignored the requested operation. The transition now applies the requested operation and appropriate direction / extent while preserving the feature ID and draft isolation. Attempts to turn the base extrusion into a cut or edit a suppressed extrusion produce an error. Added a regression covering add → cut → add, no duplicate feature, original-document preservation, and base-cut rejection.
2. **Changing profile or plane could leave a stale inline dimension edit.** Reference labels were cleared but an active gap-edit ID could remain, blocking subsequent canvas clicks until Escape. Profile / plane changes now clear the edit and in-progress pointer state together. This is a code-reviewed fix; the browser regression remains unverified because GUI control is unavailable.

## Verification

- Frontend suite: 33 tests passed after correcting a missing import in the newly added regression test. No existing test was removed or skipped.
- Backend / worker suite: 62 tests passed.
- Drawing suite: 11 tests passed in the immediately preceding implementation validation; no drawing code changed in this review.
- Production build and whitespace checks passed.
- Existing bundle-size and Starlette/httpx deprecation warnings remain.

## Browser QA blocker

Direct browser connection returned “No browser is available.” Native Chrome showed the local application and eventually rendered a screenshot, but its Sign in action did not change the accessibility tree; the subsequent visible-coordinate attempt returned `noWindowsAvailable`. No working browser session was established for the changed flow. Console/network inspection and end-to-end pointer, popup, save/reopen and responsive-layout checks are therefore unverified.

Required manual smoke test before shipping: face → rectangle → size dimensions → two edge gaps → Extrude / Cut → Preview → Apply; then Cancel, Undo / Redo and save/reopen. Repeat once at a narrow width. Edge gaps position once; they are not persistent constraints.

No commit, push, merge or deployment was performed. The user retains shipping control.
