# Solid 3D-printed plastic construction

Create a solid block-style polymer body with integrated checking contours and deliberate access relief. Retain this construction choice; do not replace it with a thin rib cage. A watertight solid CAD model does not specify 100% physical infill. If the user requires fully dense printing, record that explicitly; otherwise specify process, walls/infill or solid fill, orientation and local reinforcement to suit stiffness and dimensional needs.

Record printer/process, material grade, build envelope, environmental range and expected usage when known. Choose material/process from dimensional stability, creep, moisture/temperature response, wear and actual achievable accuracy. Do not make all plastics equivalent or promise one material/printer meets every tolerance. A provisional material is an assumption, not a qualification.

Use metal round/diamond pins, guided moving pins, replaceable datum pads and metal working gauges as appropriate. Locate and retain bushes/inserts against pull-out and rotation. Provide enough plastic around the actual insert geometry; use supported shoulders and finish bores after printing where necessary. Account for installation-induced distortion. Raw printed holes are not assumed to provide reamed locating fits.

Use through-bolts/backing plates, compression sleeves or appropriate inserts for clamp mounting. Avoid sustained clamp/bolt stress through unsupported plastic sections. Select a stable base or backing plate where stiffness and dimensional span justify it; do not unnecessarily require a heavy steel base for every small printed fixture. If split for the printer envelope, locate sections with dowels/keys and bolts; check the assembled alignment, not each piece alone.

Offset only the intended checking surfaces, keep datum pads in contact, and provide accessible windows for GO and NO-GO tool bodies and hands. Relieve bend radii, burr zones and trapping undercuts. Use removable details when a continuous nest would capture the part. A continuous 3 mm contour does not demonstrate that an operator can inspect all of it.

Plan build orientation to control critical surface stair-stepping and distortion, avoid supports on datum/checking lands where feasible, and allow finishing stock where needed. Follow the selected process's drying/curing/conditioning steps. Inspect after conditioning and final hardware installation. Qualify checking surfaces for wear and repeatability; use replaceable finished wear faces where raw plastic cannot satisfy the error budget.

Export authoritative analytic STEP plus a print-ready 3MF or per-body STL with explicit millimetre units. Reopen the mesh, check watertight/manifold geometry, outward normals, dimensions, small-feature preservation and chordal error relative to the checking accuracy. Record print settings and post-processing. Do not deliver G-code without the target machine/process. Use a DXF only for genuinely laser-cut supplementary parts, not as a substitute for print files.

## Printed gauge layout (user-accepted practice)

Default layout for a printed checking gauge unless the user asks otherwise:

- Check the surface and flanges only; no rails around the part perimeter.
- Flat printed base plate; no feet or block under it.
- One merged surface body: net pads, clamp pedestals and flange-check posts are the same body, not separate screwed-on details.
- A flange facing out of the outline gets a post that rises only to the top of its 3 mm land, tied back low (about 15 mm below the station); do not wrap a wall around the tab.
- Locating pins: ground steel dowels pressed into plain D6 printed holes (about 25 mm deep); no pin towers.
- No 1 mm clearance between neighbouring printed bodies where it leaves thin walls; merge instead.
- Every body to base: 2 D6 dowels plus M5 heat-set insert and bolt from under the base.

A job-specific reference build is in `examples/checking-printed/gauge-reference/` (unsupported, hard-coded for one part).
