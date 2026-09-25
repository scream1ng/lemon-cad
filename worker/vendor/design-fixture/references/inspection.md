# Flange checking logic

## Three distinct clearances

Datum supports intentionally touch. Locating pin clearance comes from datum simulation and feature size. Checking lands stand 3 mm from nominal part geometry. Other structural clearances come from workpiece variation, burrs, fingers, gauge envelopes and loading/rocking paths; do not limit these to 3 mm.

Use the user's 2.5 mm GO and 3.5 mm NO-GO gauge as the default. Record that this is a shop acceptance method, including on STEP-only jobs. Flag tighter, asymmetric or otherwise incompatible drawing requirements. Do not silently replace the gauges or report customer conformity based on an incompatible shop check. Continue useful concept work while keeping the conflict explicit.

## What each check establishes

- Surface gap: local displacement along a stated normal under the declared datum/restraint state.
- Separated stations along a flange: sensitivity to twist and local variation. Discrete checks do not certify the surface between stations.
- Stations separated across width: sensitivity to angular change as well as translation. A tip-only gap is not an independent angle measurement.
- Trim edge/length: a separately defined edge gap or two-limit step/flush feature where required. A surface gap does not measure flange length.

Inventory every flange, including small return flanges; `scripts/flange_features.py placed.step` lists every sheet feature with a proposed rib (station points at ±0.35 span on the base-facing side, `offset_plane` 3 mm off, YZ/XZ rib plane or a plate-face land for small vertical faces) — proposals are design suggestions, never verified stations. The concept blocks (`flange_coverage`) until each feature has a station `point_mm` on it, is a datum land (`contacts`), has an `inspection.flanges[]` entry with `feature_point_mm` and an alternative check, or an `inspection.flange_waivers` entry `{point_mm, reason}` quoting the user. Record a check for each; where inaccessible, design a removable/hinged detail or alternative measurable method. An exclusion needs a reason and remains unresolved if required coverage is lost. Do not use a datum pad itself as a GO/NO-GO gap surface; measure a separate accessible region or document the alternate datum-feature check.

Specify sufficient checking-land length/width, access opening and insertion depth for the actual gauge. Relieve adjacent edges so they cannot stop the GO end or support a NO-GO end falsely. Check both ends' full approach envelopes. For a cylindrical gauge check its diameter; for a blade check its controlled thickness and orientation. Avoid wedges/tapers on the measuring portion that make insertion depth change the result.

Before fixing rib profiles, apply [practical review](practical-review.md) and record actual full-tool/hand access in the clamped inspection state for every station. Include complete GO approach/withdrawal and NO-GO approach to its intended measuring stop. Fix known obstructions; do not claim access from local working-end fit.

## Gauges and boundaries

Use labelled metal working ends for repeated shop use. Share gauges between stations with the same limits; identify each station and provide a suitable storage location. Do not add a complicated captive mechanism without need.

Standard operating instruction: clean/deburr as specified, locate, seat gently, close only required clamps, insert GO with light pressure, then attempt NO-GO at the same station and direction. GO enters and NO-GO does not enter. Never lever, wedge, scrape away a burr or bend the part to make a reading pass. Record abnormal seating separately.

The theoretical sizes are 2.5 and 3.5 mm. Gauge manufacturing tolerance, wear allowance, actual calibrated size, decision rule, contact force and measurement uncertainty affect the physical boundary. Record these as specified or unknown; do not invent a universal gauge tolerance. At exactly the boundary, do not claim a numerical gap alone resolves actual insertion. The helper therefore returns `boundary_review` for exact numerical limit cases, while the shop operational GO/NO-GO rule remains unchanged.

Do not create a shop-standard 2.5/3.5 gauge by cutting its precision measuring thickness from nominal 5 mm steel. Use calibrated existing gauges or a specified finished/ground working size. Laser profiles and raw prints may serve as carriers; they are not automatically calibrated measuring ends.

## Error budget and validation

Budget fixture construction error, datum/pin clearance, operator seating, gauge size/wear, thermal/material movement and part deflection against the actual acceptance limits. Select the fixture build accuracy for this job; do not assign the full 1 mm gap window to fixture error. A tiny CAD numerical tolerance does not establish manufacturing accuracy.

Verify using independent metrology and repeat loading. For attribute decisions, include known acceptable and unacceptable conditions near both limits, different operators where relevant, and evidence of agreement with an independent measurement method. An assumed-good sample alone cannot calibrate the fixture. Use variable measurements where needed to assess bias/repeatability; attribute agreement and variable gauge R&R are not interchangeable.
