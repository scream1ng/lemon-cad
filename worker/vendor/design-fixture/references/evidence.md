# Engineering evidence records (finalization only)

Read at finalization (step 6), not during concept. Design rules stay in their own references; this file is only the record schemas.

## Engineering checks envelope

- `engineering_checks`: optional measured checks named in `scripts/records.py`. Missing checks are generated as unknown. Required topics include original-source survey, clamp seating/motion, workpiece loading/unloading, weld access, retention, strength, tolerances, distortion and trial validation.

To supply a completed engineering check, include `name`, `status`, `measured`, `limit`, `units`, `scope`, `next_action`, `geometry_fingerprint` and `evidence`. Each evidence item must contain a local `file` and its exact `sha256`. Use the geometry fingerprint printed by the current build. The fingerprint includes the design inputs, source CAD and hardware hashes, but excludes `engineering_checks` so attaching evidence does not invalidate itself. A changed design/source invalidates prior evidence. Evidence files must exist at build time and match their hashes; retaining their underlying reports is the project owner's responsibility. The delivery JSON retains measurements and evidence identities, not extra routine files.

A check is not established by copying its target value into `measured`. Carry out and describe the actual measurement. Independent engineering review is still needed where calculations or physical trials are required.

## Construction and operation evidence (v8)

### Contract and automation boundary

`scripts/records.py` requires `rib_construction`, `fastener_access` and `pin_mechanisms`. Missing checks become unknown and prevent fabrication readiness. Known deficient construction is fail, not merely unknown. A concept review may be delivered with explicit open items, but complete foreseeable detailing within the authorized design task before delivery.

Use the standard engineering-check envelope: current `geometry_fingerprint`, `status`, `scope`, `limit`, `units`, `next_action`, hash-checked evidence files and `measured`. For these three checks, `measured` contains:

```json
{"basis":"reopened_step", "items":[]}
```

An empty inventory also needs `not_applicable_reason` describing the actual inspected design. Each item has `id` and `component_names` (an array of exact exported solid names). Reference current CAD faces/features and measured values in the evidence report. Passing evidence is a measured report, not a repeated requirement.

Each applicable item has `findings`, mapping the section names below to objects with:

```json
{"status":"pass", "method":"Describe the actual CAD inspection/calculation and stage",
 "measurements":{"description":"Actual measurements or geometric observations"},
 "acceptance":{"description":"Job-specific acceptance criteria"}}
```

Use numeric values for dimensional checks, explicit contact/joint/feature identities for geometric observations, and state units. Failed or unresolved findings cannot be summarized as pass. A valid evidence structure does not prove the measurements were performed.

| Gate | Inventory and per-item data | Required findings |
|---|---|---|
| `rib_construction` | One item per `plates[].name`; `applicable:true` for seated/nonhorizontal plates and clamp mounts. Other plates may have `applicable:false` with a reason. Include the reviewed plate, braces and connected components in `component_names`. | `load_path`, `bracing`, `joints`, `dry_fit`, `fabrication_sequence`, `handling_clearance` |
| `fastener_access` | One item per clamp `tag`, including its mount plate in `component_names`. Supply `holes`, one entry per mounting hole, each with `id`, `stage` and findings. GH-201-B uses IDs H1–H4 in hardware-record order; other hardware declares `mounting_hole_ids` on the clamp. Include hole centres in measurements. | Per hole: `screw_end`, `installation`, `tightening`, `drilling`, `tapping`, `maintenance` |
| `pin_mechanisms` | One item per `pin_locators[].id`; include mechanism-role mapping described below. | All pins: `fits`, `retention`, `relief_orientation`, `release`. Moving pins also: `guidance`, `stroke`, `operator_access` |

Declare every locator pin in the top-level input spec inventory:

```json
{"pin_locators":[{"id":"P1", "shape_name":"REF_PIN_P1",
 "mode":"sliding", "orientation_sensitive":true}]}
```

`mode` is `fixed`, `sliding` or `removable`. The inventory does not generate geometry or locating rank. Use `REF_PIN_` only for actual locating-pin solids, and different prefixes such as `REF_BUSH_` for guide bushes. Old ad-hoc pin records must be mapped to this inventory before a v8 pass.

Each pin evidence item contains `mechanism`, mapping each actual role to a nonempty array of exported CAD names, also included in `component_names`:

| Mode | Required CAD roles |
|---|---|
| `fixed` | `pin`, `carrier`, `retention` (may be the measured press-fit feature) |
| `removable` | `pin`, `carrier`, `bush`, `grip` (may be the measured exposed dowel tail) |
| `sliding` | `pin`, `carrier`, `bush`, `handle`, `retention`, `travel_stop`; `anti_rotation` when orientation-sensitive |

Additional roles are optional but, when supplied, their solids must exist. All modes still need `fits`, `retention`, `relief_orientation` and `release` findings. Moving modes additionally need `guidance`, `stroke` and `operator_access` findings. A manual method may satisfy a removable pin's retention/orientation finding only with application-specific evidence; the mode alone grants no pass.

Moving-pin `motion_mm` contains numeric `withdrawal`, `required_withdrawal`, `minimum_guide_engagement`, `required_guide_engagement`. Define the interval before the locating tip disengages for a detachable pin; do not compare its final fully removed position to required bush engagement. Actual values must meet positive job-specific requirements. For `removable`, also supply measured `grip_length` and positive `required_grip_length`, and a `manual_operation` object with nonempty `travel_reference`, `retention`, and (when orientation-sensitive) `relief_orientation` descriptions. These descriptions accompany the measured findings; they do not prove them.

For example, a real exposed pin tail can use `"grip": ["REF_PIN_P1"]`; identify its length, accessible faces and checked hand envelope in `operator_access`. Do not map that same solid to a fictional bush or handle.

V8 adds `handling_clearance` to every applicable rib's findings. Record intentional contact exclusions, measured non-locating clearance, the chosen allowance and scoped handling motion. Existing v7 passes must be reassessed against these findings and mode-specific evidence; schema version remains 1.2.

`construction_checks.py` verifies required coverage, evidence fields, fingerprint, pin travel/engagement comparisons and actual exported component names. The build downgrades incomplete pass evidence to unknown; the delivery validator rejects invalid pass claims. Both still require the existing hash-checked engineering evidence. The script does **not** infer stiffness, create joints/bushes, measure tool envelopes, confirm a named part is physically the claimed feature, or simulate a continuous release path. Supply that evidence through explicit CAD/engineering work. Never equate a schema pass with manufacturing verification.

### Spec inventory

The required `rib_construction`, `fastener_access`, and `pin_mechanisms` engineering checks use the per-item schema in the contract above. Add a top-level `pin_locators` inventory for every pin, including fixed pins; this is an evidence inventory, not automatic geometry generation. Missing gates are emitted as unknown. A proposed bush or rib in prose does not satisfy component identity or measured-evidence checks. The output schema is now 1.2; rebuild earlier delivery records.

V8 accepts a fully detailed hand-removable pin without captive hardware. Use `mode: "removable"`, the `grip` role, measured grip/travel/guidance and `manual_operation` as specified above. Use `sliding` for captive mechanisms. Applicable rib evidence additionally needs `handling_clearance`; distinguish contact patches, non-locating gaps and the scope of lateral/rocking checks. These evidence additions do not automate CAD generation or change the 1.2 output schema.

## Checking evidence and records

The base engineering evidence remains `engineering_checks` with current fingerprint and hash-checked attachments under v8 rules. Extra `checking_evidence` is a list with check names `flange_coverage`, `gauge_access`, `inspection_restraint`, `gauge_error_budget`, `rib_profile_review`. Use the same check envelope: `name`, `status`, `measured`, `limit`, `units`, `scope`, `evidence`, `geometry_fingerprint`, `next_action`. An accepted `measured` object must cover exact `flange_ids` for coverage or exact `station_ids` for the other station-based checks, with the real measurements and findings as additional data. `rib_profile_review` instead covers exact final `plate_ids`. For the required support/clamp, full-tool access and profile-detail fields, follow [practical review](practical-review.md). Legacy station-ID lists alone cannot qualify these reviews. Attachments identify actual files and SHA-256. Missing/stale/incomplete evidence remains unknown. Coverage lists alone do not prove the attached engineering work.

Run once to obtain the fingerprint, add measured evidence, then rebuild. Engineering evidence is excluded from the geometry identity; the original source spec's complete hash remains in source records. New geometry invalidates old evidence.

Four JSON files retain v8 schema 1.2 and add `fixture_kind: "checking"`, `inspection`, `checking_geometry_status`, `cad_verified`, `fixture_calibrated` and `inspection_validated`. The base `geometry_status` covers inherited geometry checks; `cad_verified` additionally requires the checking geometry audit. `overall_status` includes checking engineering gates. `fabrication_ready` requires all applicable check/delivery passes; physical calibration and inspection validation cannot be asserted by CAD. See [verification and delivery](verification-delivery.md).
