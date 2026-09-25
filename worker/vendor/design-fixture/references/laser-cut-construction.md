# Default 5 mm laser-cut construction

Use this mode unless the user explicitly requests block construction or another process.

## Shop defaults

- All custom fixture plates are flat and laser-cut from nominal 5 mm sheet.
- Use the bundled actual purchased-clamp STEP and standard fasteners; do not create custom machined blocks or bent fixture parts unless requested.
- Prefer broad, predominantly rectangular ribs with direct load paths and few unnecessary outline turns.
- Maintain at least 10 mm nominal in-plane material (5 mm on a clamp's standard mount plate, see [clamping](clamping.md)) at structural necks, shoulders, contact fingers, webs, tab necks, and material beside or behind slots. Account for kerf and process capability before claiming a finished minimum. Tap pilots are governed cutouts: keep 10 mm from a pilot to any edge, slot or other hole. `scripts/audit_width.py` measures this and runs in both the concept preview and the delivery build, after the clamp pass so the pilots exist; a pass is screening, not a width certification.
- Choose crossing ribs or one-sided T-braces to suit structural support and available space. A one-sided T-brace is an option when space or handling clearance limits a crossing member, not the default arrangement. If selected, put tabs into matching slots in the locator rib and keep tab ends/welds flush on the workpiece side. Preserve structural ligaments and datum contacts, and check handling clearance.
- **No lone ribs.** Cross every base-seated upright (locators, braces, clamp cheeks) with a perpendicular member through a cut cross-halving joint; `scripts/cross_support.py` fails any upright without one. A genuine exception needs `cross_support_exception: "<reason>"` on the plate and stays unknown pending review. Two base tabs alone do not establish dry-fit squareness or resistance to sideways bending. Apply [construction and operation checks](construction-operation.md), including every upright and clamp mount.
- Consolidate compatible coplanar parts and reuse genuinely identical profiles.
- Give every upright seated on the base two separated integral tabs and matching through-slots. This includes locator ribs, braces, and clamp-support cheeks.
- Use single-stroke polyline-etched part IDs and station marks for assembly guidance. Etching does not replace physical location or retention.

## Profile development

1. Start each rib from a broad rectangle.
2. Add only required contact shoulders, mating joints, weld/tool clearances, loading clearances, and tabs.
3. Identify the purpose of every non-rectangular feature. Remove decorative tapers, thin slivers, acute V cuts, and unexplained notches.
4. Measure the final profile after all cuts and unions. A bounding box, corner spacing, or zero CAD interference does not establish minimum material width.
5. If a required feature leaves less than 10 mm material, widen or reposition the support, change the joint, or revise the locating approach. Do not silently waive the requirement.

## Tabs, slots, and assembly

- Use two separated tabs per base-seated upright to control dry-fit rotation.
- Make tab engagement suit the measured base thickness and underside clearance.
- Size slots using measured stock, kerf, fit allowance, and a physical coupon. Do not assume zero clearance.
- Preserve at least 10 mm at tab necks and between cutouts after process allowance.
- Widen short feet with simple rectangular material before reducing tab count.
- Derive complementary cross-slots from actual crossing angles and stock thickness.
- Record which member installs first and check intermediate insertion poses. Final-position fit alone does not establish assemblability.
- Give supported clamp and pin-carrier caps matching tab-and-slot joints with at least two separated locating tabs per cap. `scripts/cap_joints.py` generates them for every plate a clamp mounts to, before the base-tab search; name a pin-carrier or other unclamped cap in `cap_joints.extra_caps` to include it. Moving a tab is an override (`cap_joints.pinned`), not a design decision to skip: `cap_joints` in the CAD report fails a cap located by fewer than two cheeks or a tab end standing proud of a mounting face. The generator keeps its slots 10 mm from cap edges, tap pilots and each other, and clear of the clamp base footprint; it refuses a cap when no position satisfies that, so reposition or move a cheek before enlarging the cap. Cheeks sharing a part number are cut from one profile and take the same tab span.
- Tabs locate parts for assembly but do not by themselves establish vertical retention, fixture strength, or weld adequacy.

## Clamp mounting holes

For the standard GH-201-B clamp, place the four mounting positions from its hardware record. Cut nominal diameter 4.2 mm pilot holes in the fixture plate and identify them as `M5 x 0.8 TAP AFTER LASER`. Do not use the clamp body's clearance-hole diameter as the tap-drill size.

Treat 4.2 mm as the shop nominal. Confirm laser kerf, heat-affected edge, tapping practice, and actual clamp fit before production.

## DXF

- Use millimetres.
- Keep closed fabrication contours on `CUT`. Convert identifiers/instructions to joined, open, single-stroke `LWPOLYLINE` geometry on `ETCH`; do not export `TEXT` or `MTEXT`, closed etch loops, duplicate segments, or visible travel lines between disconnected strokes.
- Keep every etch stroke inside its final nested plate profile. Join connected character segments into the fewest practical continuous strokes so the laser does not perform unnecessary starts/stops.
- Default physical stock is 2400 x 1200 mm. Reserve the top 100 mm clamp band and nest inside the 2400 x 1100 mm usable zone unless the project explicitly supplies another measured zone.
- Pack all custom plates into the narrowest practical strip of the usable zone and report both strip utilization and whole-sheet utilization. Prefer leaving the largest contiguous rectangular remnant over scattering parts across the sheet. One sheet is preferred when feasible, not a fixed requirement.
- Generate part IDs and quantities from the final verified geometry.
- Reopen the DXF and compare every closed `CUT` loop with the final plate profiles. Verify that `ETCH` contains only open polylines and zero text entities. Keep stock, usable-zone, clamp-exclusion and nest-strip references off `CUT`.

Design clamp platforms from hardware and joint requirements, not broad default rectangles. Use the standard mount plate in [clamping.md](clamping.md). Keep auxiliary supports distinct from fixed datum lands; a solid fixed-height laser-cut land cannot be called floating or adjustable without the corresponding mechanism.
