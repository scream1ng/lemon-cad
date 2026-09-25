# Inherited fabrication output contract

This is the v8 fabrication foundation. For checking fixtures, apply [checking verification/delivery](verification-delivery.md) and [checking build schema](checking-build.md) on top.

# Delivery output contract

The routine package contains exactly one cutting DXF, one assembly STEP, two review PNGs and four UTF-8 JSON records:

```
DELIVERY/
  <project>-fixture-cutting.dxf
  <project>-fixture-assembly.step
  assembled.png
  empty-fixture.png
  JSON/
    project.json
    fixture-design.json
    hardware.json
    verification.json
```

Do not add .blend, HTML, spreadsheets, CSV schedules or extra audit files unless requested. Multiple sheets may be represented in one clearly separated, labelled DXF using a separate nesting workflow. Blocks may omit DXF when the requested construction makes it inapplicable; record the exception and use `--allow-no-dxf`.

## Shared identity and statuses

Use `schema_version: "1.2"`, a shared nonempty `project_id` and `revision`, millimetres and explicit coordinate frames. Rebuild older records; they lack the evidence needed by this version. Check statuses are `pass`, `fail`, `unknown`, or `exception`. An exception does not confer fabrication approval.

Three status fields serve different purposes:

- `geometry_status`: aggregates required automated geometry checks, including unknown coverage.
- `overall_status`: aggregates geometry and required engineering checks.
- `delivery_status`: records whether files and record semantics validate.
- `fabrication_ready`: true only when all engineering/geometry checks and the delivery pass.

A complete review package can have `delivery_status: pass` and `overall_status: unknown`. State this plainly. Empty check lists, omitted required checks, and successful motion samples must never imply an overall pass.

## Records

### project.json

Include shared identity, `units`, `geometry_fingerprint`, `source`, `construction`, `requirements`, `assumptions` and `open_items`. `source.records` identifies the design spec, each original source, placed CAD and hardware definitions using `role`, `file` and `sha256`. The parallel `source.files` and `source.sha256` arrays must agree with these records. Never substitute the spec hash for a CAD hash.

### fixture-design.json

Include shared identity, `coordinate_frame` including the source-to-fixture transform, `workpieces`, `datums`, `locators`, `supports`, `clamps`, full final `components`, `tabs_slots`, `retention`, original `design_spec`, `geometry_fingerprint`, `export_files` and `export_sha256`.

Each final plate retains its name, part number, role, origin, orthonormal axes, outer profile, holes, contacts, seating relationship and nest placement. Each clamp retains hardware ID, target workpiece, supporting locator, contact, force direction, rigid frame, hole centres, preparation and known limitations. Keep original design inputs separate from generated profiles so rebuilding does not add tabs twice.

### hardware.json

Include shared identity and only the hardware `items` used. Preserve sources, mounting geometry, force/capacity distinctions, known motion and unknown dimensions. Include the actual purchased-hardware asset identity and saved-pose limitations. A hash-checked actual STEP is required by the default builder; it does not establish closed-pose or motion verification.

### verification.json

Include shared identity, `geometry_revision`, `geometry_fingerprint`, `checks`, `geometry_status`, `overall_status`, `delivery_status`, `fabrication_ready`, `measurements` and `open_items`.

Required check names live in `scripts/records.py`. Every check records name, status, measured result, acceptance limit, units, evidence identity, scope/limitations and next action. Retain the detailed tab, mount, width, nest and CAD reports under `measurements`, including individual contact gaps, face normals, constraint conditioning, collisions and export comparison results. Use pointers from summary checks to these measurements rather than duplicating whole reports.

Manual engineering evidence is supplied through the input spec; see [evidence](evidence.md). Do not relabel an old result after changing geometry. Unknowns remain null with explanations; no fabricated measurements.

## Exports and review images

The STEP preserves named fixture solids, workpiece references and any hardware references. The DXF uses millimetres with closed fabrication contours on CUT and joined open single-stroke `LWPOLYLINE` geometry on ETCH; `TEXT` and `MTEXT` are forbidden. Physical-stock, usable-zone, clamp-exclusion and nest-strip boundaries stay off CUT. Hash the exact exported files.

`assembled.png` shows the workpiece seated with visible fixture details; `empty-fixture.png` removes the workpiece and identifies fixture components. The bundled renderer uses the exported STEP and identifies hardware as saved-pose references. Empty views hide the workpiece and its source weld/clip references. The assembled image includes CAD side-view insets with mounting-face height, clamping-surface height and signed difference for each clamp; keep these inside the existing PNG rather than adding routine files. Both are review views, not proof of clearance or manufacturability.

## Resume and validation

Read all four records, map recorded source paths to available files and verify source bytes, units, frame and geometry fingerprint. Resume from `design_spec`; source CAD must still be available. The assembly STEP is a review fallback, not a substitute for the original source survey. Any changed geometry/source invalidates affected evidence and exports.

Run `python scripts/validate_base_delivery.py DELIVERY` for weld output; checking uses `validate_delivery.py` as an extension. These check types, required checks, status consistency, revision/fingerprint agreement, actual file readability, closed DXF loops, STEP presence, PNG validity and export hashes. Structural validation is not physical readiness. Exit 0 means a complete review package; inspect engineering status. This contract applies only after explicit package authorization; concept HTML stays outside DELIVERY.

## Assembly and hardware records

Retain `assembly_locating` in fixture-design.json and the input spec: master part, datum rationale, loading stages, mating contacts, seating directions, and any secondary-stop exception. Contacts identify `constraint_role`; auxiliary supports identify their mode and activation sequence. Preserve compactness metrics and mount design rationale.

Required automatic checks now include `hardware_geometry`, `mount_compactness`, `cross_support`, `same_side_secondary`, `assembly_locating` and `mounting_height`. Required engineering topics also include `assembly_tolerances`, `hardware_pose` and `hardware_clearance`. Old reports missing these checks must be rebuilt; do not relabel them. Asset STEP bytes participate in the geometry fingerprint. Validate that every declared clamp has all its named `HW_<tag>_<component>` solids in the exported STEP.

The required `mounting_height` check retains per-clamp measured values under `measurements.cad_audit.mounting_height`. Rebuild pre-v5 reports lacking this check. A mounting-height pass must never promote `hardware_pose`, `clamp_seating` or `clamp_motion`.

## Construction and operation gates (v8)

Require `rib_construction`, `fastener_access`, and `pin_mechanisms` in every verification record. Retain their per-item measurements in the check's `measured` object and the input `pin_locators` inventory in `design_spec`. The validator checks coverage and named STEP components for accepted results; it does not independently solve stiffness or motion. Unknown/fail/exception results prevent fabrication readiness. Empty inventories require a measured applicability explanation. Bushes, operating pin components and related fasteners must be recorded in hardware.json and named in STEP, with purchased/custom origin and finishing requirements. Keep the same four JSON files and two PNGs; use detail insets in those images when needed.

For v8, retain the rib `handling_clearance` findings and mode-specific pin-operation evidence defined in [evidence](evidence.md). Record exact bodies, contact exclusions, job-specific allowances, tested transforms and remaining path limitations. A local clearance pass must not promote whole-fixture loading/unloading. Do not carry forward a v7 pass without checking the added evidence requirements.
