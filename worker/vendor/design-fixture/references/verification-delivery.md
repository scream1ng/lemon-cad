# Verification and delivery

## Required evidence

Check final reopened CAD and retain per-feature/component evidence for:

- Source preservation, units, occurrence transforms and current revision.
- Datum contact and constraint independence, all remaining stops, pin fit/relief orientation, and restraint state.
- Every flange's coverage and limitations; surface versus edge/angle scope.
- Checking-land normal offsets over finite usable areas, gauge approach/insertion and local collision. A nearest-distance sample alone does not establish uniform normal gap.
- Actual clamp asset, mounting level, closed seating/lock, opening and force/deflection; saved-pose references remain unresolved for operation.
- Structural support, fastener/tool access and actual pin mechanisms, including grip, guidance and withdrawal.
- Real loading/release order and clearance with part variation and realistic handling allowance. Samples are screening, not proof of a continuous path.
- Laser mode: tabs/slots, joint engagement, material ligaments, dry fit, retention, welding/finishing sequence and DXF-to-CAD comparison.
- Printed mode: solid structure, inserts, retention, material/process assumptions, mesh/STEP comparison and finish/conditioning plan.
- Export identities, readable files and geometry comparisons, not merely filenames or process exit codes.

Each check has `id`, `status` (`pass`, `fail`, `unknown`, `exception`), exact scope, component/feature IDs, measured values/units, acceptance criterion, method, evidence identity/hash, geometry revision and next action. Use `unknown` for unavailable evidence and `fail` for a known defect. Exceptions do not confer readiness. Explicitly justify non-applicability. Never make an empty inventory an automatic pass.

Keep independent release fields:

- `cad_verified`: all applicable final-CAD geometric checks have measured passes.
- `fabrication_ready`: CAD plus manufacturing details, gauge construction requirements and process capability are resolved. Planned post-build calibration may remain pending and must be stated.
- `fixture_calibrated`: independent physical measurements of the finished fixture and gauges are supplied and meet criteria.
- `inspection_validated`: physical loading repeatability and suitability of the inspection decision system are demonstrated.

Without physical evidence, the last two fields remain false/unknown; never infer them from CAD. A valid JSON structure is not engineering evidence. A complete concept package may have unresolved readiness; clearly report the limiting checks.

## Routine package

Deliver:

- `<project>-fixture-assembly.step`: named fixture bodies, reference workpiece, actual hardware and modelled working gauge where useful.
- `assembled.png` and `empty-fixture.png`: CAD-derived views showing datum contacts, flange/station IDs and clearly readable 3 mm gap/GO/NO-GO section insets. Distinguish saved-pose clamp references. Include a compact operator sequence in the image or design record.
- `JSON/project.json`, `JSON/fixture-design.json`, `JSON/hardware.json`, `JSON/verification.json`.
- Laser mode: one `<project>-fixture-cutting.dxf` containing all sheet parts.
- Printed mode: `<project>-check-fixture-print.3mf` or `PRINT/<body>.stl` for each printable body, with units/settings in JSON. Add a DXF only if supplementary laser-cut parts exist.

Do not add `.blend`, spreadsheets, HTML or extra audit reports by default. Keep working measurements/scripts outside the routine delivery or embed their reproducible content in the records. Produce custom gauge manufacturing dimensions/finishing notes in the records and model, not just an unmanufacturable nominal gauge solid.

## Four records

Use inherited `schema_version: "1.2"` plus `project.fixture_kind: "checking"` and checking extension fields, shared `project_id`, `revision`, units `mm`, source and final-export hashes in all records as appropriate.

`project.json`: original sources/revisions/hashes, rigid frame transform, selected mode, shop standard, drawing conflicts, source process stage (bare/coated etc.), printer/process assumptions, requirements/open items.

`fixture-design.json`: measured workpieces/flange inventory, datum/locator rationale, pin bearings/remaining stops, contacts, supports, clamps, complete components/profiles/joints, checking stations and directions, access/release sequence, integrated face identities, fabrication or print/finishing plan, reproducible design parameters/scripts. Include `inspection` and the complete `design_spec` with the checking build schema; the actual plan screen and CAD station results are stored under verification.measurements.checking_geometry.

`hardware.json`: actual stock/purchased/custom items, quantities, source assets/hashes, dowel sizes/grinding/fit, bushes, retention, gauge IDs and 2.5/3.5 working sizes, their calibration/manufacturing requirements, clamp pose/force limitations, fasteners and print inserts.

`verification.json`: current geometry identity, per-check evidence above, file manifest/hashes, delivery completeness, independent release fields and open actions. Re-read all four records, validate references and actual output identities before delivery. The full delivery validator reruns the checking CAD audit and verifies mesh geometry/hashes for printed bodies, on top of inherited record/export gates. Gap-plan screening remains only one subset. Perform the remaining engineering verification explicitly.

Resume only after verifying source bytes, transform, geometry revision and export hashes. New geometry invalidates affected evidence. Never claim compliance with a customer standard solely because its general concepts informed this skill.

## Engine compatibility

The inherited four-record structure and required base check names remain intact. Read [output contract](output-contract.md) for base fields, then apply the checking extensions in [checking build schema](checking-build.md). Filename stems from the engine remain `<project>-fixture-assembly.step` and `<project>-fixture-cutting.dxf`; these are checking fixtures when `fixture_kind` is `checking`. No extra duplicate renamed exports are needed. STL files live under `PRINT/`; the manifest covers them too. The base `geometry_status` remains the inherited check aggregate; `checking_geometry_status` is additional, and `cad_verified` requires both.

Do not edit generated reports to promote an unknown. Supply v8 engineering evidence through `engineering_checks`, checking-specific evidence through `checking_evidence`, or an explicit verified CAD extension. Physical calibration/inspection validation require genuine external measurements. Printed backend operation/strength/material qualification remains explicit engineering work even when shape/mesh checks pass.
