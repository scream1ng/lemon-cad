# Measured welding-fixture workflow

Weld branch only. Build/export wording below applies after explicit package authorization; otherwise stop at interactive concept review.

Keep three layers separate:

- **Requirements:** source CAD/drawing, datums, tolerances, welds, loads, sequence, and manufacturing constraints.
- **Design specification:** work frame, contacts, supports, clamps, components, access, and release path.
- **Evidence:** measurements performed on the actual built and exported geometry revision.

A design value copied into a check file is not independent verification.

## Stage contracts

| Stage | Required result | Acceptance evidence |
|---|---|---|
| Survey | Source hash, units, body/occurrence IDs, bounds, thicknesses, faces, holes, bends, joints | Imported geometry agrees with source dimensions and assembly placements |
| Orient | Right-handed fixture frame and source-to-fixture transform | Orthonormal rotation, determinant +1, no unintended scale or reflection |
| Locate | Selected hole/slot features, remaining contacts and loading stages for every loose workpiece | Real contacts and pin bearing directions constrain the coupled assembly; pin clearances and relief directions are checked |
| Support | Support schedule and flexible-part treatment | Loads have local reaction paths; extra supports are not confused with datums |
| Clamp | Hardware identity, contact, force direction, mounting, and opening space | Force seats the part into support; closed/open envelopes and access are checked or marked unknown |
| Build | Named manufacturable fixture components | Rib interlocks, dry-fit squaring, fastener/tool access and complete guided-pin mechanisms pass the construction/operation gates |
| Verify | Revision-linked check records | Contact, penetration, constraint, access, opening, loading, and unloading checks have honest statuses |
| Export | DXF, assembly STEP, images, and four JSON records | Reopened outputs match the verified units, revision, geometry, and required file contract |

Use `pass`, `fail`, `unknown`, or `exception` for each check. Never change an old audit's revision label and call it rerun evidence.

## Locating logic

Read [assembly locating](assembly-locating.md) before choosing supports. Select a master part and load order. Identify fixture-to-part and part-to-part contacts at each stage; each loose piece must be located before tacking, but it need not have its own independent six fixture contacts.

Separate fixed datums from auxiliary supports. Three fixed heights on both sheets plus mating overlap contacts may create redundant constraints. Extra support under a clamp can be appropriate if it is adjusted after seating, floating or relieved; merely renaming a fixed rib does not remove its constraint.

Prefer suitable existing holes/slots for secondary and tertiary location; follow [hole and slot locating](hole-slot-locating.md). Use edge stops for constraints the selected pins do not supply. When an edge-based secondary pair is needed, use two separated stops on the same side with a common seating direction by default. Opposing stops need a documented engineered exception, not a rank-six argument. Check the complete assembled constraint system, loading stages and tolerance compatibility. The coupled rank screen is local mathematics, not proof of force closure or tolerance robustness.

For a frictionless contact at position `p`, inward unit normal `n`, common reference origin `o` and characteristic length `L`, use:

`[nx, ny, nz, ((p-o) x n)x/L, ((p-o) x n)y/L, ((p-o) x n)z/L]`

A fixture contact occupies its workpiece's six matrix columns. A mating contact contributes opposite rows to the two workpiece blocks. Track both rank and redundant rows, then check actual mating faces and how clamps keep them seated.

## Clamping logic

- Put the clamp pad over a support where practical.
- Measure lateral offset between support and clamp lines; confirm the force direction pushes into the support.
- Confirm actual workpiece material lies between the pad and support.
- Keep holding capacity separate from applied clamping force.
- Check body, arm, handle, hand, torch, cable, and spatter clearance.
- Evaluate intermediate opening and unloading poses. Clear endpoints alone do not prove a clear swept path.
- Use the actual bundled purchased-clamp geometry. A user-requested schematic requires an explicit separate exception; it cannot establish hardware fit or clearance.

## Verification logic

| Check | Measure | Insufficient evidence |
|---|---|---|
| Intended contact | Distance to the intended CAD face and correct face identity | Minimum distance to any surface |
| Penetration | Robust intersections against every unintended workpiece/fixture body | A zero nearest gap |
| Constraint | Contact and pin-bearing rank/conditioning plus seating assumptions | Counting 3 + 2 + 1 or treating every slot as a complete locator |
| Hole/slot locator | Actual bore/slot size, pin profile, relief direction, engagement and withdrawal clearance | A pin centre represented as a zero-gap planar contact |
| Mounting height | Actual exported mounting face versus workpiece contact surface along the clamp normal | Nominal reach, a copied height value or saved-pose clearance |
| Clamp support | Force direction, lateral offset, material thickness, support identity | Opposed arrows in a render |
| Weld access | Joint extent and usable torch/nozzle approach | One clear point |
| Opening | Moving-body intermediate poses or conservative swept envelope | Open and closed endpoints only |
| Loading/unloading | Staged pin release and clamp opening, then swept path or refined collision samples with job-specific lateral/rocking allowance and part variation | Clear final position or exact vertical lift alone |
| Export | Reopened geometry, units, names, counts, key dimensions, and contacts | File existence |

Keep intentional contact patches separate from clearance to the rest of each rib. Choose and record handling allowances for this workpiece and loading stage; do not copy another job's clearance, offset or angle. Local SHS-to-brace samples cannot approve the complete welded-assembly path. See [construction and operation checks](construction-operation.md).

Any geometry change invalidates affected checks and exports. Correct the smallest responsible feature, rerun affected checks, and deliver the same revision that was verified.

Before export, apply [construction and operation checks](construction-operation.md). Inspect the empty fixture as well as the seated assembly; a locating-rank pass cannot waive these checks.
