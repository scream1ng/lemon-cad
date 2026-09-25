# Locators, supports and clamps

## Retained v8 locating principles

Respect the drawing datum reference frame, datum targets and material-boundary modifiers. Prefer accessible existing holes/slots where appropriate. For two suitable round holes, begin with one round pin (two in-plane constraints) and one ground diamond/relieved pin (rotation control). Relieve pitch variation along the line between centres; retain bearing across that line. For a hole and slot, analyse actual slot wall directions; a slot may fail to constrain rotation. Do not substitute a round/diamond pair when the specified datum simulation requires another arrangement.

Carry every dowel on a pad plate whose face is square to the pin, on the shop standard pad in hardware/pin-pad.json (40 x 40, cheeks at +-12, 5 mm ligament; never a plate grown to suit): press the shank through a reamed hole so the pad thickness is the bearing length, or stand it on the pad face. A rib edge is not a pin seat, however much material sits under the base; relieve the rib under the dowel and let the pad carry it. A pad held above the base stands on at least two plates - one rib lets it rock - and is located by two cap tabs like a clamp cap: name it in pin_locators[].pad so the tabs and its ligament are generated.

Keep the dowel shank round; grind the exposed locating end for relief. Separate workpiece locating fit, pin shank mounting fit and bush fit. Record stock, finished bearing sizes, projection, lead-in, engagement, retention and diamond orientation. A round shank does not key a relieved end. Use witness marks only where manual orientation is sufficiently repeatable; use mechanical orientation when required. Remove redundant fixed stops whose constraints are replaced by pins.

Use primary datum pads and only the remaining independent locating contacts. Inspect the finished assembly as a whole. Hole-location inspection pins are distinct from locating pins: they must not reposition the part or mask the error being inspected. Derive any functional check pin from the actual drawing requirement; never apply the flange 2.5/3.5 standard to holes.

Prefer common pin release directions. For suitable manual release, use a hand-removable dowel in a machined bush carried by a braced support. In steel construction, use weldable bush material, align/weld/cool then finish the bore. Do not weld a hardened purchased bush without a qualified method. In plastic, use supported mechanically retained bushes and finish the mounting seats as needed. A bare hole in one thin rib or raw printed bore is not a qualified moving-pin guide.

Measure bush ID/OD/length, required travel, engagement until the tip disengages, grip and hand access, and complete extraction. A fully removed pin need not retain bush engagement. Provide adequate support to the carrier; use two backing gussets as a starting layout only where appropriate. Do not add sliding carriages, locks or handles without a practical need. Check the complete removal sequence with the part present and clamps open.

## Actual GH-201-B asset

Read [hardware/gh-201-b.json](hardware/gh-201-b.json). Verify the bundled STEP SHA-256 before use. Preserve all 14 component occurrence placements and use one rigid mounting transform; do not replace the mechanism with blocks. Use the recorded `source_to_canonical` transform and measured CAD mounting-slot centres, not the differing nominal drawing pattern.

The saved spindle is tilted about 24.5 degrees and is not a verified closed pose. Its 56.9 mm nominal reach is a planning value. Either derive and verify physically connected closed/open linkage poses or label the hardware as a saved-pose reference and keep operating checks unknown. Never rotate the entire mounted clamp or shift only its pad to fake closure. Preserve source geometry and record any legitimate mechanism articulation.

Default the mounting face to the level of the part's intended clamping surface, measured along the contact normal. For a horizontal 5 mm cap, cap centre is H-2.5 and supporting cheek tops H-5. Measure these on reopened CAD. A deliberate alternative requires explicit operating-geometry evidence. Equal levels do not prove toggle lock, pad seating or spindle range.

For steel mounts, use the four measured mounting centres and nominal 4.2 mm pilots for M5 x 0.8 tapping; distinguish pilot DXF from finished STEP thread/bore representation. For plastic, use through-bolts, compression sleeves/backing washers or suitable inserts; do not blindly transfer the steel tapping practice. Record the actual retention and access.

Keep platforms compact using actual base footprint, fasteners, tool access and joint ligaments. Prefer two spaced supporting cheeks for broad offset-loaded caps where useful. Keep ribs out of screw-end, drill/tap and driver/socket paths; model these envelopes rather than assuming hole placement establishes access.

## Inspection seating

Clamp onto nearby datum supports with the minimum suitable seating force. Do not support or clamp a measured flange in a way that forces nominal shape. The 90 kgf hardware rating is holding capacity, not applied force. Treat unmeasured force and deflection as unknown. Use appropriate non-marring pads and verify their compression/repeatability. Respect drawing-defined restrained inspection when specified; otherwise record the proposed seating method and check that it does not conceal flange error.
