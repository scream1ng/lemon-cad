# Explicit printed-body CAD schema

`scripts/printed_body.py` requires OCP and NumPy, with standard-library STL parsing. All coordinates and lengths are millimetres in the final assembly coordinate system. No workpiece offset, uniform envelope subtraction, imported hardware dependency, or inferred datum contact is performed.

## API

- `build_shapes(spec) -> (dict[str, TopoDS_Shape], report)`: builds `spec["printed_bodies"]`, returning one valid connected solid per unique name. Missing `printed_bodies` gives an empty result. Report contains `units`, `body_count`, `bodies`, and `physical_readiness: "not_assessed"`.
- `export_meshes(shapes, out_dir, linear_deflection_mm=0.05) -> report`: OCP tessellation to one `<name>.stl` per solid; reopens and verifies each file. Report contains `units`, `mesh_count`, `meshes`, and `physical_readiness`. Failed verification removes the affected newly written STL and raises `ValueError`.
- `inspect_mesh(path, shape, linear_deflection_mm=0.05, name=None) -> mesh_record`: independently reopens an existing STL and compares it with a supplied CAD solid. This does not modify the STL. Pass the body name explicitly when filenames differ from CAD names. Here deflection is the comparison tolerance; original mesher settings cannot be inferred from an STL.

Names match `[A-Za-z0-9][A-Za-z0-9_.-]*`, are unique within printed bodies, and may not start with reserved `Part_`, `REF_`, or `HW_`. The assembly caller must also reject collisions with other assembly objects. The caller handles assembly STEP writing using the returned shapes.

## Parametric body

```json
{
  "printed_bodies": [{
    "name": "Printed_Nest",
    "stock": {"origin": [0, 0, 0], "size": [80, 60, 20]},
    "add": [
      {"type": "box", "origin": [75, 0, 0], "size": [15, 60, 20]}
    ],
    "subtract": [
      {"type": "box", "origin": [-1, -1, 8], "size": [16, 20, 13]},
      {"type": "cylinder", "origin": [25, 25, -1], "axis": [0, 0, 1], "radius_mm": 3, "depth_mm": 22},
      {"type": "offset_pocket", "point": [55, 30, 0], "normal": [0, 0, 1], "u": [1, 0, 0], "width_mm": 20, "height_mm": 20, "gap_mm": 3, "depth_mm": 4}
    ]
  }]
}
```

`stock` must be an axis-aligned box. Optional `add` and `subtract` arrays run in that order and preserve their individual order. Each operation must change volume and leave exactly one valid solid. Disconnected additions, cuts that split/remove the body, and misses are rejected. Box sizes, radii and depths must be positive finite numbers; booleans are rejected as numbers.

Features:

| Type | Required fields | Geometry |
|---|---|---|
| `box` (default) | `origin`, `size` | Axis-aligned box extending in positive world X/Y/Z. |
| `cylinder` | `origin`, unit `axis`, `radius_mm`, `depth_mm` | Cylinder begins at origin and extends along positive axis. |
| `offset_pocket` | `point`, unit `normal`, unit perpendicular `u`, `width_mm`, `height_mm`, `depth_mm`; optional `gap_mm` (3) | Subtractive-only rectangular prism described below. |

Every vector has three finite numeric components. Unit-vector tolerance is 1e-6; accepted directions are normalized before construction. Arbitrary oriented pockets use a constructed planar wire and kernel extrusion. There are no rotations or implicit placement transforms on a body: provide final placed geometry or coordinates.

## Offset checking land direction

`point` is a point on the surveyed workpiece surface. `normal` points from that surface toward the intended checking land/body. The center of the cut's starting face is `point + gap_mm * normal`; its local axes are `u` and `normal × u`. Width and height are centered about that point. The cut extends `depth_mm` in **negative normal**, toward and potentially past the workpiece. Thus material on the positive-normal side remains and its local exposed land is at the specified gap. The default 3 mm is a nominal design value, not a measured acceptance result.

For a stock spanning Z=0…20, workpiece point Z=0, normal +Z, gap 3 and depth 4, the cutter spans Z=-1…3. The remaining local land is Z=3. The surrounding uncut stock remains: widths and heights must cover the actual region requiring clearance, with deliberate gauge approach and extraction relief. An offset-pocket entry alone does not prove that it created a usable land; overlap, local boundaries, accessible contact, actual workpiece geometry, and station/gauge checks must be verified separately. No datum contacts are synthesized or certified by this module.

## Supplied finished body

```json
{
  "_dir": "/absolute/path/to/spec-directory",
  "printed_bodies": [{"name": "Printed_Nest", "finished_step": "geometry/nest.step"}]
}
```

`finished_step` is resolved from `spec["_dir"]` when relative (current directory if `_dir` is absent). It is mutually exclusive with `stock`, `add`, and `subtract`. Each file must contain exactly one valid positive-volume solid and no loose geometry. Multiple printed bodies use multiple named entries. CAD position and file units must already represent the intended millimetre assembly; no automatic placement is applied.

## Movable checking details

A land that would block loading or gauge access may sit on a hinged or sliding printed body. Export that body in its **open** pose (the unload gate sees it open) and declare it in `inspection.movable_details`:

```json
{"id": "SW1", "body": "SWING_1", "kind": "hinged", "stations": ["F01-S1"],
 "axis_point_mm": [-56, -84, 145], "axis_direction": [1, 0, 0], "open_angle_deg": 140}
{"id": "SL1", "body": "SLIDE_1", "kind": "slide", "stations": ["F04-S1"], "direction": [0.18, 0.97, 0], "stroke_mm": 10}
```

Closed = rotate by `-open_angle_deg` about the axis (right hand), or translate by `-stroke_mm` along `direction`. The station audit (concept `checking_geometry` and finalize) closes only the station's own `fixture_shape`; other movable bodies stay open, so a station gauged "with the slide open" is measured that way. This is pose bookkeeping only: closed stop, hinge/guide play, latching, open rest and swept clearance through the motion are job evidence (for example a job motion check), not proved by the audit.

## CAD and mesh checks and limits

Each body is checked with OCP validity analysis, single-solid topology, finite bounds, and positive volume after every boolean. A body report records name, CAD volume, bounds `[xmin,ymin,zmin,xmax,ymax,zmax]`, source, and operation counts.

Mesh export clears previous triangulation and uses OCP absolute linear deflection (default 0.05 mm) and angular deflection 0.1 radian. ASCII STL preserves more coordinate precision than binary float32; STL itself does not encode units, so the report declares millimetres. Reopened meshes are checked for finite/nondegenerate triangles, exactly two opposite uses of every welded edge, a connected triangle fan at every vertex, consistent winding, and positive total signed volume. Weld tolerance is `max(1e-8, largest_absolute_CAD_coordinate * 1e-12)` mm. These are combinatorial manifold checks; they do not independently prove absence of all geometric self-intersections.

CAD/mesh bounding coordinates must match within requested linear tolerance plus ten weld tolerances. Up to 256 evenly spaced triangles are checked at their centroid and three edge midpoints against the CAD **surface faces** using kernel distance (not distance to the filled volume). The maximum sampled distance must meet the same tolerance. This is a scoped chordal check and is **not** a global Hausdorff proof or exhaustive comparison of every facet. Mesh and CAD volume are reported independently; volume equality is not an acceptance gate.

Mesh records include `name`, `source_body`, `filename`, `file`, counts, mesh/CAD bounds and volumes, `closed_manifold`, `consistent_winding`, `positive_signed_volume`, weld tolerance, requested linear tolerance, maximum bounds error, sampled point/triangle counts, maximum sampled surface distance, and the explicit chordal scope. Export additionally records the mesher and its actual relative/angular settings.

No print process, shrinkage, build orientation, bed size, material stiffness, durability, contact accessibility, gauge travel, clamp performance, or physical readiness is asserted by these CAD/mesh checks. Those require job-specific verification and measured hardware/workpiece evidence.
