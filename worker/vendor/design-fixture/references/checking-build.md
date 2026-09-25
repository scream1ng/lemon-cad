# Checking layer on the v8 build specification

## Entry point and flow

Create a measured spec from the STEP survey; the user is not expected to supply JSON. For steel, retain v8 `schema_version: "1.2"`, project/revision/units, plates, contacts, locating groups, clamps, workpiece sources/frame and fabrication settings. Add `inspection` below and optionally generated `checking_ribs`. Run:

```bash
python scripts/build_check.py WORK/spec.json WORK/build
python scripts/validate_delivery.py WORK/build/DELIVERY
```

The driver normalizes input paths, writes `WORK/build/work/prepared-spec.json`, invokes v8 construction or the printed backend, reopens STEP, measures checking lands, appends CAD section views and validates the package. Edit the original spec and rebuild; do not edit generated prepared specs/reports to change acceptance. Existing manifested exports belonging to this project are cleared before rebuilding, so a mode change cannot reuse stale meshes/DXF. Do not share one build directory across projects.

## Inspection plan and measured stations

Use the base [gap-plan format](gap-plan-format.md) as top-level `inspection`. The plan's `construction` is `laser_rib` or `printed_solid`. Extend each gap station with exact solid identity and usable-area/tool information:

```json
{
  "id": "F01-S1",
  "kind": "surface_gap",
  "part": "Bracket",
  "fixture_shape": "CHECK_RIB_1",
  "point_mm": [0, 0, 60],
  "direction": [0, 0, -1],
  "scope": "Local lower flange position; separate trim check if required",
  "approach": "From positive X, under flange; operator hand envelope separately checked",
  "basis": "shop_standard",
  "drawing_conflict": false,
  "patch": {"u": [1, 0, 0], "v": [0, 1, 0], "width_mm": 10, "height_mm": 2},
  "gauge_envelope": {
    "u": [1, 0, 0], "width_mm": 10, "length_mm": 4,
    "approach_direction": [1, 0, 0], "offsets_mm": [0, 10, 30, 100]
  }
}
```

`part` resolves through `workpiece.parts`; alternatively supply an exact `part_shape`. `fixture_shape` is the exact exported rib/body solid containing the checking land. `point_mm` lies on the actual nominal part surface; `direction` is the outward unit normal from that surface toward the checking land. Nominal land target is `point_mm + direction * nominal_gap_mm`.

Every `point_mm` must lie on the checked part (<= 0.1 mm) or the concept blocks (`flange_coverage`: a notch or cutout under the station). A flange checked only by an alternative method carries `feature_point_mm` (a point on that feature) on its `inspection.flanges[]` entry. An unchecked feature the user accepts goes in `inspection.flange_waivers`: `[{"point_mm": [x, y, z], "reason": "<user's words>"}]`; an empty reason is rejected.

The station defaults to nominal 3 mm, GO 2.5 mm and NO-GO 3.5 mm, as in the plan checker. A drawing conflict makes the plan unresolved; known geometry failures remain failures. The legacy export naming is `Part_*` (case-sensitive), not `PART_*`.

`patch` axes are mutually orthogonal unit vectors tangent to the part plane. The CAD checker evaluates nine source/land normal rays across the rectangular patch, verifies points lie on actual trimmed planar faces (a B-spline face counts as planar only when its plane fit deviates ≤0.001 mm) and records exported face IDs/distances. Missing patch coverage remains unknown. The `1e-4 mm` numeric comparison is for ideal CAD, not an achievable manufacturing tolerance. This sampling is not proof of all surface points or full flange coverage. Curved faces and alternate techniques require explicit CAD verification; do not label their unsupported checks passed.

`gauge_envelope` defines a rectangular working end at each actual GO/NO-GO thickness. Its u direction is across width; the other tangent is `direction × u`. The tool is centered within the nominal gap. The checker verifies nominal GO non-penetration and expected nominal NO-GO obstruction by the local part/land. It optionally checks the GO end against all assembly solids at nonnegative `offsets_mm` along `approach_direction`; include zero and an adequately clear starting offset. A collision is failure; collision-free discrete samples leave continuous access unknown. Specify the actual gauge width/length, rather than selecting a tiny fictitious tool merely to pass. Full handles, hands, force and a usable insertion path require the `gauge_access` engineering check.

## Automatically generated checking ribs

Use existing v8 plates for datum supports, braces, caps and base. Optional `checking_ribs` constructs checking profiles from deliberately selected stock and measured offset half-planes:

```json
{
  "checking_ribs": [{
    "plate": {
      "name": "CHECK_RIB_1", "part_number": "CK01", "role": "Checking rib",
      "origin": [0, 0, 0], "u": [1, 0, 0], "v": [0, 0, 1], "w": [0, -1, 0],
      "outer": [[-30, 0], [30, 0], [30, 65], [-30, 65]],
      "holes": [], "contacts": [], "seat": "BASE"
    },
    "offset_planes": [{"point_mm": [0, 0, 60], "direction": [0, 0, -1], "gap_mm": 3}]
  }]
}
```

This retains material on the fixture side of `normal · (X - part_point) >= gap`, in the actual rib frame. The example's top becomes Z=57. The checking normal must lie in the rib plane so that an extruded cut edge forms the correct checking plane; an oblique sketch offset is rejected. Each generated rib enters the normal v8 tab/slot, material-width, nesting and STEP pipeline. It must not duplicate a declared plate name. The model still designs stock extent, structural load path, braces, cap joints, clearance and assembly sequence. Do not choose clipping planes that disconnect a checking land from its support and assume tabs will repair the design.

For complex sections, generate an explicit measured polygon or imported verified geometry and use the normal station audit. Use the documented CAD/CAM fallback for shapes outside v8's flat vertical-rib model. Generated offset planes alone do not prove a usable finite land; the reopened station audit checks it.

## Printed construction

Keep project, sources, workpiece map, contacts, proposed datums, inspection and applicable engineering metadata. Replace sheet fabrication with `printed_bodies` from [printed-body schema](printed-body-spec.md); at least one valid connected body is required. Use `plates: []` and no fake sheet construction to satisfy a validator. Contacts use `rib` as the owning printed body name, despite that inherited field name. Print settings record material/process/orientation/postprocessing and `linear_deflection_mm` (0.05 mm default for mesh generation, choose to suit accuracy).

For a GH-201-B on a printed body, a clamp record uses `tag`, `hardware: "GH-201-B"`, `mount_body`, `mount_plate` (same owning body), and a rigid 4x4 `mount_transform` from the hardware canonical mounting frame to the fixture frame. Retain contact/force/support rationale. The backend inserts all 14 original components. Body bores, inserts, metal backing and real load paths must be modelled explicitly; a transform alone does not create a mount. The printed backend leaves mounting level, locked operating pose and seating as unknown pending explicit measured evidence, instead of applying a sheet-plate height calculation to an arbitrary solid.

The backend reuses v8 STEP reading/writing, hardware identity/transforms, contact-face and intersection helpers, evidence records and rendering. It adds analytic printed features, STL export and reopened mesh checks. Inherited steel-specific or unsupported operation checks remain unknown with explicit scope, rather than becoming automatic passes. Source geometry and final STEP/mesh comparisons are still required.

## Evidence, records and release

`checking_evidence` and the checking record fields are in [evidence](evidence.md); read it only at finalization.

## Reproducible examples

`examples/checking-rib/spec.json` builds a planar checking coupon with inherited supports/clamp plus a generated 3 mm checking rib. `examples/checking-printed/spec.json` builds the same coupon on an explicit printed body with datum lands. Both produce real STEP, review images, records, and DXF or STL. Both intentionally retain unresolved engineering/physical checks. They test the build path; they are not ready-made manufacturing fixtures for new parts.

## Completed assembly and pin-bearing rank

For an inspected finished assembly (or one part), declare `inspection.rigid_assembly` with `parts` listing every `workpiece.parts` key, a nonempty `basis` identifying the completed assembly/rigidity assumption, and `seating_directions` for used Primary/Secondary/Tertiary families. Keep an `assembly_locating` plan to identify the inspection stage and no invented loose-part mating contacts. The checking extension treats the completed assembly as one six-DOF body while preserving all source-solid identities and measured contacts. It does not certify joint stiffness from STEP.

Optional `inspection.pin_bearings` supplies independent ideal bearing rows for pins that actually exist in CAD: each has `id`, `part`, `pin_shape`, measured `point_mm` and one or two unit `directions`. A round pin normally contributes two in-plane directions and a relieved pin one. Do not duplicate these as planar contact points at empty hole centres. The rank is reported, but accepted rank with pins remains unknown for operating constraint approval until explicit pin fit/orientation/engagement evidence exists. Contacts at real datum lands still undergo physical-face checks. Wrong or redundant directions fail rather than being silently removed.
