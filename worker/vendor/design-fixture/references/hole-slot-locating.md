# Hole and slot locating

## Select features before designing edge stops

Prefer usable existing holes and slots for secondary and tertiary location. Respect specified drawing datums first. Measure feature size, centre/axis, slot direction, wall thickness, tilt and accessibility from the source CAD. Consider actual tolerances, nearby welds, burrs/spatter and the intended removal direction. Explain an edge-locating fallback when the available features cannot provide suitable, accessible location; do not force every opening to become a datum or alter the workpiece to suit the fixture without authorization.

Keep primary support and assembly mating logic from [assembly-locating.md](assembly-locating.md). A pin strategy replaces particular in-plane constraints, not the supports or every remaining stop.

| Available features | Preferred starting arrangement | Check before adopting |
|---|---|---|
| Two suitable round holes | One round dowel and one ground diamond/relieved dowel | Use the round pin for two in-plane directions and the relieved pin for rotation; relieve pitch variation along the line joining pin centres |
| Round hole and suitable slot | Round dowel plus a relieved locator in the slot | Establish which slot walls bear; slot orientation must allow the intended relief while controlling rotation |
| One round hole | Round dowel plus an independent rotational stop or another suitable feature | The round hole alone does not control in-plane rotation |
| One usable slot | Combine a relieved locator with only the independent contacts still required | Choose side-wall or end bearing deliberately; the slot alone does not complete location |
| Multiple slots or irregular openings | Derive bearing directions from the measured geometry and check the coupled constraint system | Do not count each opening as a full round-hole locator |
| No usable hole/slot scheme | Use conventional edge locating | Retain same-side secondary stops and a clear release path |

For a round/relieved pair, normally orient the relieved direction along the line between the pin centres and the retained bearing direction across that line. For a slot, verify the actual wall direction rather than inferring it from the presence of an elongated hole. A slot can leave rotation unconstrained if its bearing direction is unsuitable. Avoid two full round locating pins by default: hole-pitch variation can cause binding.

For the one-slot case, two same-side stops may control one translation and rotation while a ground slot-end pin controls the other translation. This is appropriate only when its measured bearing profile and release clearance support those roles. A small round pin loose along a long slot does not locate against the slot ends. A pin of slot width cannot reach the ends of a longer slot at all, so taking the slot's long direction as a datum means an obround key ground to the slot profile, bearing on the side walls across the width and on the end radii along the length. Such a key removes the separate end stop and normally keeps the stage rank-complete, but it makes a pierced feature's length a datum and leaves no relief in either direction: measure slot length, die roll and burr over real blanks before choosing key size and clearance, confirm the drawing agrees this feature is the datum, and keep the edge stop it replaced in the records as the alternative. An obround key only enters one way round, so it needs an obround guide bore rather than a round one and an orientation mark the operator cannot misread. A tilted slot needs a measured relieved profile and withdrawal check; do not copy another fixture's relief dimensions.

Remove physical edge/end stops whose constraints are replaced by pins. Include every remaining fixed contact and every mating contact in the loading-stage analysis. Do not omit a real competing stop just to obtain the desired rank.

## Prefer ground stock dowels

- Select standard round dowel stock first. Keep the mounting shank round and grind the exposed end to provide the required diamond/relieved bearing profile. Use a custom shouldered or keyed locator only when the application needs it and explain why.
- Choose stock diameter, length, bearing dimensions, relief, lead-in and engagement from the measured part and locating requirement. Do not turn the HUD example's 6/10 mm dowels or grinding dimensions into universal defaults.
- Separate **workpiece locating clearance** from **fixture mounting fit**. A ground end fits the part feature; the unground shank fits its carrier bore. Do not use an oversized shoulder/square-shank mounting hole for a plain dowel.
- Specify an undersize laser pilot and a post-weld drilled/reamed mounting bore where appropriate. Select allowance and finished fit from shop capability and actual dowel stock; a nominal laser hole does not establish a press fit.
- Define dowel projection, insertion/retention method and relief orientation. Round shanks do not key the diamond direction: mark and orient the flats and qualify retention. Do not assume an unverified press fit prevents rotation or pull-out.
- Give the carrier a supported load path and actual tab-and-slot cap joints. Keep mounting faces clear of proud tabs/welds and preserve access for finishing and installing/removing the dowel.

## Check loading and release

Choose the loading and removal directions before detailing carriers. Prefer a common withdrawal direction for the pins locating the completed weldment. Limit protrusion to the locating engagement and lead-in needed; avoid capturing the part with shoulders or overhanging stops.

Check the actual source geometry against pin heads, unground shanks, carriers and remaining stops at seating and during withdrawal. For tilted slots, include the changing wall clearance while lifting. Check the complete welded assembly, including relevant source reference bodies, and the opened clamp envelope. Separate nominal CAD clearance from hole tolerance, weld shrinkage and physical trial evidence. Record the scope of sampled checks; clear samples do not establish a continuous sweep. If open clamp geometry is unavailable, keep that portion unknown.

## Use an explicit CAD and analysis workflow for pins

The bundled plate builder handles planar physical contact rows; it does not automatically generate pins, interpret a `pin_locators` field, or grant locating rank for hole/slot bearings. Continue using its plate, clamp and export checks, with an explicit project CAD/analysis extension for the pin arrangement. Keep unsupported checks unknown until that extension supplies evidence; do not relabel missing or failed results as passes.

1. Preserve feature identity and measurements, selected bearing directions, remaining stops and the reason for any fallback in the design records.
2. Model the dowels as named `REF_PIN_*` solids in the placed STEP or an explicit exporter. Verify their geometry and fit on the reopened assembly, including collisions with carriers and nearby bodies.
3. Keep physical surface contacts separate from idealized pin-bearing rows. A hole centre lies in empty space; it is not a zero-gap planar contact. For local rank analysis only, a round pin normally contributes two independent in-plane bearing rows and a relieved pin one, at measured feature locations. Include these analysis rows in each applicable coupled loading stage and identify them as finite-clearance idealizations.
4. Retain the original physical-contact, interference and source-preservation checks. Report bearing directions, rank, redundancy and remaining freedoms together with actual pin-clearance measurements. Full rank alone is not seating, tolerance or force-closure approval.
5. If the DXF contains undersize pilots while the STEP represents finished bores, retain both definitions and an explicit pilot-to-finished-bore operation for each carrier. Label manufacturing stages and compare each reopened export with its intended stage. Do not hide the difference by weakening export checks.
6. Keep the same delivery contract: plate cutting DXF, finished assembly STEP, assembled/empty review views and four JSON records. Include dowel stock/grinding/retention in hardware records and pin/finishing evidence in design and verification records. Do not place solid pins on the 5 mm plate cutting contours.

## Guided sliding and removable pins

For a suitable manually operated fixture, start with a plain hand-removable dowel guided by a machined weldable-steel bush on a braced rib. Choose the grip, bush dimensions and release travel from this job. Keep the carrier mounting opening, bush ID and part-locating fit distinct. A bare hole in one 5 mm rib is not equivalent to a guide bush. Ordinary fixed dowels do not automatically need bushes.

Read [construction and operation checks](construction-operation.md) for mode selection, orientation/travel references and evidence. Model the bush and actual operating components in STEP; put the carrier opening and brace joints in DXF. For a welded steel bush, align and weld it, allow it to cool, then finish its bore to suit the actual dowel. Use a retained replaceable bush when wear, heat treatment or servicing warrants it. Do not assume a hardened purchased bush is weldable.

Add handles, positive stops, captive retention or keyed guidance only for a demonstrated operating need. A suitable plain removable dowel with measured grip access and a defined operating method is a complete manual concept; it does not need fictional handle or retainer solids. Directional relief needs verified orientation: manual marks may suit a low-demand operation, while applications needing assured orientation require mechanical control.

Opposed locating axes require an explicit release sequence. Check withdrawal with the workpiece present, guidance until the locating tip disengages, free extraction, grip access, and subsequent part removal with clamps open. A fully removed pin has zero final bush engagement; measure required guidance over the interval that still constrains the part. Keep it in the scene until it is actually withdrawn. Record the limits of local samples and missing clamp-motion evidence.
