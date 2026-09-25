# STEP-first geometry survey

Unified workflow: survey is used in both weld and checking modes. Checking-flange guidance below applies only to checking. Stop after concept preview by default; the build/validation commands at the end are finalization-stage diagnostics, not permission to create a package.

Start with the actual supplied STEP, including assembly occurrences and their placements. Use this survey when the user supplies CAD without a measured fixture specification. It prepares evidence for design; it does not select datums, classify functional flanges, or generate a fixture from a bounding box.

```bash
python scripts/survey_step.py input.step WORK/survey
python scripts/survey_step.py input.step WORK/survey --transform WORK/source-to-fixture.json
```

Requires `numpy` and `cadquery-ocp` (the same OCP kernel used by the build pipeline). No network or other services are needed. Keep `WORK/survey` as a working input, outside the routine delivery package.

## Placement and identity

The survey transfers source geometry through OCCT into millimetres, then applies one proper rigid source-to-fixture transform. Default is identity. The transform file is either a 4 × 4 JSON array or an object with a `source_to_fixture` array. Coordinates are column vectors:

`fixture_mm = source_to_fixture @ [source_mm.x, source_mm.y, source_mm.z, 1]`

Translation is in millimetres after source-unit normalization. Scale, shear, reflection, non-finite values and malformed matrices are rejected. Rotation must be orthonormal with determinant +1. Re-survey the original source when changing the frame; do not apply the recorded transform again to `placed.step`.

Nested assembly locations compose in parent-to-child order. Every leaf occurrence is retained even when product names, occurrence names, or complete textual paths repeat. Each solid receives a deterministic `Part_0001`, `Part_0002`, … name in imported free-shape/component/solid order. This identity is stable for the same STEP import, not promised across re-exported or revised CAD. Multi-solid leaf occurrences are split into separately named bodies. Coincident occurrences remain separate. Original product names, textual occurrence paths, indexed occurrence paths, and solid indices are retained for tracing the source.

Surface-only leaf occurrences are listed in `warnings`; no-solid inputs and invalid/non-positive solids fail. Resolve skipped source geometry before treating the survey as complete. The tool does not establish source completeness against a drawing or BOM.

## Outputs and schema

`placed.step` contains the uniquely named workpiece solids in the fixture frame with explicit millimetre output units. It can be consumed as `workpiece.placed_step` by the existing build/export pipeline. Geometry is preserved, not tessellated.

`survey.json` has `schema_version: "step-survey-1"`:

| Field | Meaning |
| --- | --- |
| `source.path`, `source.sha256` | Absolute input path and SHA-256 of actual source bytes |
| `source.length_units_detected` | OCCT-reported source length-unit names, or `unknown` |
| `units`, `unit_normalization` | Millimetres and explicit OCCT normalization method |
| `source_to_fixture`, `transform_convention` | Rigid placement and multiplication convention |
| `placed_step` | Relative path `placed.step` |
| `body_count`, `bodies` | Count and ordered measured body records |
| `warnings` | Skipped non-solid leaf occurrences with provenance |
| `classification_status` | Geometric evidence only; candidates require review |
| `fixture_design_status` | Always `not_generated` |

Each body records `name`, `product_name`, `occurrence_path`, `occurrence_index_path`, `solid_index`, `volume_mm3`, `center_of_mass_mm`, `bbox_mm` (`min`, `max`, `size`), `kernel_valid`, `faces`, and `feature_candidates`.

Every face records a body-qualified deterministic face ID, analytic surface type, area, area centroid, and topological orientation. Planes also include outward `normal`, `plane_origin_mm`, and trimmed `boundaries`. Cylinders include `axis_origin_mm`, unit `axis`, `radius_mm`, parameter `uv_bounds`, and boundaries. An axis origin is an arbitrary point on the analytic cylinder axis, not necessarily a hole centre or midpoint. Cylinder orientation is recorded; the tool does not infer inside/outside function from it.

Boundaries contain wires with `is_outer` and ordered edges. Edges record curve type, oriented endpoints, parameter range, and length. Circular edges additionally give exact centre, axis, and radius. Other nonlinear edges include 17 explicitly approximate sample points; these samples are evidence for review, never fabrication contours or clearance certification. Line/circle descriptors and the exact placed STEP remain available for further kernel analysis. Face centroids can lie outside a trimmed face or in a hole; do not use them directly as locator contact points without an inside-face check.

`feature_candidates` deliberately labels every planar face `flange_or_datum_face` and every cylindrical face `hole_or_bend_or_outer_cylinder`, with `status: "unverified"` and a geometric basis. These are candidate search sets. A plane is not automatically a functional flange; a cylinder may be a bend, pin, boss, partial arc, or hole. Through/blind status, slot pairing, sheet thickness, opposed sheet faces, functional tolerances, accessibility and datum intent require explicit review.

## Continue into measured fixture design

1. Review the exact placed solids and original drawing requirements. Confirm which occurrences constitute the inspected assembly and resolve missing/surface-only geometry. Check source units and frame against known dimensions.
2. Use measured planar/cylindrical faces and exact boundaries to choose stable primary, secondary and tertiary references, suitable hole/slot locators, flange checking surfaces and loading directions. Record rationale and candidate rejection. Confirm material sides and fixture contact locations on trimmed faces. A body bounding box is useful for locating geometry, not for inventing checking profiles or deciding functional faces.
3. Choose the construction requested in the task. For laser ribs, section the actual checked geometry in chosen rib planes and offset the appropriate checked flange boundaries by the specified checking gap. Resolve loading/removal access, gauge paths, rib bracing and retention. Do not extrapolate a fixed fixture from the overall length/width/height.
4. Create the measured specification using `spec-format.md`, `gap-plan-format.md`, and the construction-specific references. Set `workpiece.source_files` to the actual original input, `workpiece.placed_step` to this survey's placed STEP, `workpiece.source_to_fixture` to the recorded matrix, and `workpiece.parts` to the selected `Part_*` identities. Retain the survey as design evidence; it is not a substitute for a specification or a certified `source_survey` check.
5. Run the existing build and verification pipeline against that specification. Preserve its geometry checks, assembly locating checks, purchased hardware, mounting geometry, mating tabs/slots and output records. Use the checking-specific gap validation and delivery gate as required by the main skill. Unknown engineering checks remain unknown until evidence supports them.

```bash
python scripts/build_check.py WORK/spec.json WORK/build
python scripts/validate_delivery.py WORK/build/DELIVERY
```

Changing the source or placement invalidates dependent contacts, profiles, gap targets and prior verification. Re-survey and rebuild the affected design.

## Kernel regression checks

```bash
python -m unittest discover -s tests -p test_survey_step.py -v
```

The synthetic cases cover duplicate named components within a translated nested assembly, source-to-fixture rotation plus translation, coincident occurrences retained through export, a drilled plate's planar wires/cylinder evidence, inch-source normalization and millimetre export, CLI transform loading, and rejection of non-rigid transforms. All generated inputs/outputs use temporary directories.
