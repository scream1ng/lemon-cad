# Restraint, access and profile review

Apply this review before committing to rib outlines and repeat it on the final exported CAD. Use the same datum and 3-2-1 discipline as the weld-fixture foundation; adapt restraint forces to inspection so they cannot hide part error. Never substitute a good-looking render or constraint-rank result for a seated, operable fixture.

## Primary seating and hold-down completeness

Inventory every fixed primary contact by its `contacts[].name`. Map each to an actual clamp tag or a justified gravity-only seating region. Put required hold-downs over or close to supported seating regions, with a direct load path through the part to the datum and fixture. Check the entire part remains seated under the expected gauge forces, including lift and rocking. Use only the required restraint; one clamp may serve more than one support if the load path and seating are demonstrated. Do not silently omit clamps because this is a checking fixture or because the clamp list is optional in the inherited schema.

Verify secondary/tertiary seating, round/relieved pin roles, loading, clamp closure, hand access and release without overconstraint. Actual GH-201-B geometry and a mounting-height pass do not establish its closed pose. Use measured operating geometry or explicitly conservative envelopes and retain their limitations. Keep pads off unsupported measured flanges; check seating force and resulting distortion. Do not move established datums to solve access problems without a functional reason.

In `inspection_restraint.measured`, retain exact `station_ids` and add:

- `primary_supports`: one row per fixed primary contact, with `support_id`, `mode` (`clamped` or `gravity_only`), `clamp_tags` (empty for gravity-only), `basis` and `load_path`. Identify actual tags from top-level `clamps`; account for every clamp.
- `seating_verified`: true only with attached evidence of stable seating and acceptable distortion under the stated forces. Record forces, directions and displacement/limits in the attached analysis.
- `closed_pose_verified`: true only when the actual closed clamp geometry is verified; required for a pass when clamps exist.
- `limitations`: required for an exception. Gravity-only justification must address expected gauge forces, stability and repeatable seating; it is not an automatic pass.

A declared required clamp absent from the inventory fails. Missing maps or operating evidence stay unknown. A known omitted hold-down must be designed and rebuilt, not relabelled gravity-only to clear a report.

## Full gauge and operator access

Route the tool before freezing checking lands, ribs, braces, pins and clamp mounts. Check the entire GO and NO-GO tool, stem, handle and hand from an accessible start through approach, measuring position and withdrawal. Include the part, all fixture solids, pins and clamps in their inspection state. A 3 mm gap, 4 mm working tip, or isolated collision-free pose cannot establish usability. The expected NO-GO measuring stop is legitimate; an earlier collision is blocked access.

Prefer ordinary shop gauges and direct routes. Move an obstructing brace, open the layout or provide a removable/hinged checking detail or a justified alternative method. Custom or long-reach tools require reach, stiffness, handling and calibration justification. Do not solve access merely by making a fictitious tip smaller or making its stem arbitrarily long. Select dimensions from the actual intended tool; no universal reach limit is imposed.

In `gauge_access.measured`, retain exact `station_ids` and add `stations`, exactly one row per station:

- `station_id`, `tool_id`, positive `reach_mm`, and `envelopes_mm` with positive three-dimensional bounding sizes for `working_end`, `stem`, `handle`, and `hand`. These dimensions index the attached positioned CAD/envelope analysis; dimensions alone do not prove clearance. Model both actual working-end thicknesses and all other tool features in the analysis.
- `part_clamped: true` means the part is in its declared inspection restraint state, including justified gravity-only cases. Include `closed_pose_verified` for actual clamp geometry.
- `custom_tool: false` for an identified ordinary tool. For a custom/long-reach tool, use true and supply `custom_tool_basis`, `rigidity_basis`, `handling_basis` and supporting evidence.
- `paths`: two rows, one with `end: "GO"`, one `end: "NO_GO"`. Each includes `method`, measured `min_clearance_mm` to unintended obstructions, and `result`. Use `clear` for a clear GO path, `clear_to_stop` plus `expected_stop` identifying the measuring contact for a reachable NO-GO stop, `blocked` for an obstructed route, or `unknown` for unresolved access.
- A pass requires `method: "continuous"` or `"bounded_sampling"`; the latter also requires `between_samples_bound` explaining why intervening poses remain clear. Unbounded samples or conservative unverified clamp poses can support an explicitly limited exception, not a pass. Every exception station requires `limitations`.
- For `kind: "alternative"`, provide `station_id`, `method` and `access_basis` explaining usable access to that measurement; retain supporting analysis.

Attach current CAD measurements, tool placements, route/hand envelopes and review views. Sweep a conservative full assembly envelope or use an adequately justified continuous clearance method. Known blocked access fails and must be corrected. Missing evidence remains unknown. The qualifier checks record completeness and contradictions; it does not itself calculate a full-tool sweep or validate the numerical claims in attachments.

## Simple final profiles

Start with continuous, broad rib transitions. Inspect all final plates in STEP and DXF after offsets, tabs, slots and Boolean operations. Inventory every intentional notch/relief with a feature identity, location and function: real interlock, tool/manufacturing clearance, part clearance, or demonstrable gauge access. Delete unused construction cuts and narrow slits at horizontal-to-sloping transitions when the actual insertion direction does not need them. Retain adequate ligaments and load paths under the inherited material-width checks; do not apply a blanket ban to functional joints or access cuts.

Add a `rib_profile_review` entry to `checking_evidence`, using the usual current fingerprint, measurements, limits, scope and hashed attachments. Its `measured` contains:

- `plate_ids`: exact names of all final `plates`, including generated checking ribs.
- `reliefs`: rows with `plate_id`, `feature_id`, `purpose`, and `required: true` for every retained relief. Include locations and measured ligament/clearance checks in the attached analysis. Use an explicit empty list only after confirming there are none. A known unnecessary retained relief (`required: false`) fails approval.
- `final_profiles_reviewed: true` only after reviewing actual exported geometry and fabrication profiles. A printed-only design with no plates uses `plate_ids: []`, `reliefs: []`, and an attached explanation of non-applicability; its body access remains subject to the other checks.

These checks affect overall readiness, separately from local CAD gap verification. Missing evidence can accompany a complete concept review package but cannot establish fabrication readiness. Do not reopen or alter a previously accepted fixture merely because the skill rules were updated; apply changes to that fixture only when requested.
