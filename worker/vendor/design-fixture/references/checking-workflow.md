# Measured design workflow

Checking branch only. Build/export wording below applies after explicit package authorization; otherwise stop at the interactive concept and invite feedback.

## Survey and source control

Read the original STEP/drawing; preserve source filename, SHA-256, units, revision and assembly occurrence placements. Never infer manufacturing dimensions from screenshots. Assign unique component names. Distinguish actual workpieces from weld representations, fasteners and reference bodies. For a changed part or source hash, survey again; do not reuse earlier fixture dimensions.

Measure bounding boxes, sheet thickness, candidate datum faces, holes/slots, bend axes/radii, flange faces/trim edges and obstructions. Record each flange F01, F02, etc. with source body and face/edge descriptors, area/extents, local normal and proposed checks. CAD topology indices alone may change after reimport: retain geometric descriptors and source identity.

Choose a stable loading orientation and save the right-handed source-to-fixture rigid transform. Plan complete-part loading, locating-pin engagement and release before placing checking details. For an assembly, inspect the completed assembly unless the user requests process-stage checks; do not relocate every constituent independently as if still welding it.

## Datums and inspection plan

Use specified drawing datums and restraint conditions. When absent, propose a functional datum scheme and label it as a design assumption; proceed with the known shop gap standard. Keep proposed datums distinct from certified drawing compliance. Analyse the constraints of the complete inspection state, including pins, fixed stops and supports. Add auxiliary supports only with a mechanism/sequence that avoids competing datum contacts.

Create each station from measured source geometry: source flange, point, unit checking direction, nominal gap, datum reference, gauge ID, tool approach and scope of the characteristic inspected. List full flange coverage and explicit exclusions. Check more than one station where necessary to detect twist/angle; choose station spacing from usable flange dimensions and expected error modes, not a universal count or interval.

Check the plan before detailed CAD. Missing printer information does not prevent a concept: record an explicit process assumption and leave print-production readiness unresolved. Do not invent material qualification or printer accuracy.

## CAD execution

Use CadQuery/OCP, FreeCAD or another available solid-modelling kernel. Record package versions and actual measurement script. Use the bundled STEP survey and build_check pipeline for reusable construction, CAD checks and exports. The agent prepares the measured specification; the engine does not infer arbitrary datum intent or functional flanges. Use explicit kernel extensions for geometry outside the documented backend limits.

For planar flanges, construct an offset plane and a finite checking land at the specified normal distance. For curved regions, use validated local offsets/sections and measure normal gap across the usable land. Select the side deliberately; automatic face normal orientation can be reversed. Maintain separate datum contact pads. For rib sections, measure the final 3D surface-to-land distance: a 3 mm offset in an oblique sketch is not necessarily a 3 mm normal gap.

Do not blindly subtract a uniformly enlarged workpiece from a block: this can remove necessary datum contact, create trapped undercuts or leave inaccessible checking gaps. Provide access windows, removable details or alternate stations where necessary. Keep structure away from part loading and gauge approach paths.

Name solids `Part_*`, `BASE_*`, `RIB_*` or `BODY_*`, `DATUM_*`, `REF_PIN_*`, `REF_BUSH_*`, `CHECK_*`, `GAUGE_*`, `HW_*`. Record integrated checking lands as measured faces of their parent solids. Avoid duplicated coincident solids at integrated features.

Iterate the responsible design parameters and rebuild all affected outputs when geometry changes. Preserve job-specific source scripts with the work; include their content or a durable reference/hash in the four design records so the delivered design is reconstructable.

For a completed multi-solid assembly, declare `inspection.rigid_assembly` per checking-build.md so the local constraint calculation uses six rigid-body freedoms for the assembled workpiece. Do not require a separate fixed 3-2-1 system on every welded child part. Preserve each source solid and its contact identity; the rigidity declaration changes analysis, not the source geometry.
