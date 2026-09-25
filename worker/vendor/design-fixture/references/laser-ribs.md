# Laser-cut rib construction

Use nominal 5 mm flat steel for custom plates by default. Preserve suitable standard pins, bushes and bought hardware as separate non-sheet components. Do not introduce machined blocks in place of the requested ribs without a reason tied to accuracy or function.

Start with broad simple rib outlines and direct load paths. Retain at least 10 mm nominal in-plane structural material at webs, shoulders, necks, tab roots and around slots, allowing for process capability. Measure the final cut geometry rather than bounding boxes. Keep precision checking details distinguishable from structural ligaments.

Review final cut profiles using [practical review](practical-review.md). Justify every retained notch or relief by an actual joint, manufacturing, clearance or access function. Remove unneeded narrow slits at profile transitions; do not generate them automatically between checking lands.

Give every base-seated upright two separated integral tabs and matching base slots. Size fit from measured thickness, kerf and a coupon. Include actual interlocking perpendicular braces and cap joints where required: touching rectangles and JSON joint descriptions are not cut geometry. Preserve adequate engagement, insertion order and ligaments. Two base tabs alone do not establish lateral stiffness or dry-fit squareness.

Choose cross-bracing or one-sided T-bracing from space, handling and loads; neither is universally preferred. Parallel braces within 50 mm of each other (plane and span) are one common brace: fewer loose plates to confuse at assembly (`brace_merge` blocks the concept). Keep bottom-slot lap height at least twice the tab foot height, or the feet refill the slot. When a crossing brace interferes with loading or gauge access, move/shorten it or put a supported one-sided brace into available space. Keep tab ends and welds clear of measuring surfaces and flush where required. Do not move a datum merely to conceal a structural clearance problem.

Support checking ribs against hand/gauge forces and torsion. Keep non-checking parts of each rib farther from the part as needed for realistic load/unload motion. Check lateral drift and slight rocking after locator disengagement; do not demand sideways motion while the part is still pinned.

Define tacking, squaring, retention and welding sequence. Tabs locate during assembly; they do not provide all required retention. Measure after welding and cooling. Finish critical bores and datum/checking details as needed. Do not claim raw laser edges or welded tab fits meet gauge accuracy without evidence. Prefer replaceable located-and-fastened checking details when finishing/service needs justify them; do not enlarge every rib into a machined block.

Check every screw head/washer, end protrusion, tightening tool, drill/tap approach and maintenance removal. Position backing ribs around these envelopes. Avoid needless base machining when a simple layout change solves access.

Export all plate profiles into one millimetre DXF, with `CUT` closed loops and joined open single-stroke `LWPOLYLINE` IDs/instructions on `ETCH`; never export DXF `TEXT` or `MTEXT`. Keep physical-stock, usable-zone, clamp-exclusion and nest-strip boundaries off CUT. Default to 2400 x 1200 stock with a 2400 x 1100 usable zone, pack into the minimum-width practical strip and preserve the largest right-side rectangular remnant. Include matching slots, holes and quantities. Multiple sheets can be separately labelled in the same DXF. Reopen and compare profiles/quantities with the source CAD, and verify all etch strokes stay inside their plates. Keep laser pilots and final bore stages explicitly mapped; never call their legitimate difference an export error or conceal it by weakening checks.
