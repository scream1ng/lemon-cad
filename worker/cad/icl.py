"""ICL module — face/edge picking + distance measurement on STEP parts.

Separate from cad/geometry (label wireframe) and cad/preview (plain STL).
Face and edge IDs are 1-based positions in OCC indexed maps, deterministic for
the same shape, so the frontend can pick an entity and the measure endpoint can
resolve it back to a sub-shape.
"""
from __future__ import annotations

import functools
import math
from typing import Optional

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GeomAbs import (
    GeomAbs_Circle,
    GeomAbs_Cylinder,
    GeomAbs_Line,
    GeomAbs_Plane,
)
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_REVERSED
from OCP.TopExp import TopExp
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

from cad.loader import load_step

# ---------------------------------------------------------------------------
# OCC binding compatibility
# Newer OCP exposes static methods with a `_s` suffix (Face_s, MapShapes_s);
# older builds (e.g. on Railway) expose them without it. Resolve per-binding.
# ---------------------------------------------------------------------------


def _static(cls, name):
    fn = getattr(cls, name + "_s", None)
    return fn if fn is not None else getattr(cls, name)


def _face(shape):
    return _static(TopoDS, "Face")(shape)


def _map_shapes(shape, typ, m):
    _static(TopExp, "MapShapes")(shape, typ, m)


def _triangulation(face, loc):
    return _static(BRep_Tool, "Triangulation")(face, loc)


def _degenerated(edge):
    return _static(BRep_Tool, "Degenerated")(edge)


def _surface_props(face, props):
    _static(BRepGProp, "SurfaceProperties")(face, props)


# ---------------------------------------------------------------------------
# Indexed maps (deterministic 1-based IDs)
#
# Same lesson as the `_s` suffix above, one level up: it is not only METHOD
# names that shift between OCP builds, the CLASSES move too. The conda build
# Railway resolves has shipped without TopTools_IndexedMapOfShape, and because
# that was a module-level import it took cad.icl, cad.repair and cad.dxf_export
# down at import time -- ICL and CAD Repair both dead, while Label (which needs
# no map) kept working. So: resolve the class at runtime, and carry a
# pure-Python stand-in for the builds that don't have it at all.
# ---------------------------------------------------------------------------


def _occ_class(module: str, name: str):
    """OCP.<module>.<name>, or None if this build doesn't expose it."""
    import importlib

    try:
        return getattr(importlib.import_module("OCP." + module), name, None)
    except ImportError:
        return None


def _explore(shape, typ) -> list:
    """Every sub-shape of `typ`, in TopExp_Explorer order, duplicates included
    (a shared edge is visited once per face). TopExp_Explorer is core OCC and
    present on every build."""
    from OCP.TopExp import TopExp_Explorer

    out, ex = [], TopExp_Explorer(shape, typ)
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    return out


@functools.lru_cache(maxsize=1)
def _shape_key():
    """A hash function that agrees for IsSame shapes, or None if this build
    has none.

    Needed only by the Python stand-in below, and it cannot be assumed: OCP
    7.7 has TopoDS_Shape.HashCode() and a Python hash() that is IDENTITY-based
    (two wrappers for the same face hash differently -- silently useless for
    de-duplication), 7.9 dropped HashCode() and made hash() content-based. So
    probe both on a box whose faces are known-distinct rather than trusting
    either, and fall back to O(n^2) IsSame scanning if neither behaves.
    """
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.TopAbs import TopAbs_FACE

    box = BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape()
    first, second = _explore(box, TopAbs_FACE), _explore(box, TopAbs_FACE)
    for fn in (lambda s: s.HashCode(0x7FFFFFFF), hash):
        try:
            keys = [fn(s) for s in first]
            # Same shape -> same key (rules out identity hashing), and distinct
            # shapes -> distinct keys (rules out a degenerate constant).
            if keys == [fn(s) for s in second] and len(set(keys)) == len(keys):
                return fn
        except Exception:
            continue
    return None


class _PyIndexedMap:
    """Stand-in for TopTools_IndexedMapOfShape, for builds without the class.

    Same contract TopExp::MapShapes fills -- 1-based, explorer-ordered,
    de-duplicated by IsSame -- so a face/edge ID means the same sub-shape
    either way. That matters: IDs are handed to the frontend and posted back
    to /measure, so a stand-in that numbered differently would quietly move
    every balloon on a part meshed by the other code path.
    """

    def __init__(self):
        self._items = []
        self._buckets = {}  # key -> [1-based positions]

    @classmethod
    def of(cls, shape, typ) -> "_PyIndexedMap":
        m = cls()
        for sub in _explore(shape, typ):
            m.Add(sub)
        return m

    def _bucket(self, shape):
        key = _shape_key()
        return key(shape) if key else 0  # no usable hash -> one bucket, O(n^2)

    def Add(self, shape) -> int:
        found = self.FindIndex(shape)
        if found:
            return found
        self._items.append(shape)
        self._buckets.setdefault(self._bucket(shape), []).append(len(self._items))
        return len(self._items)

    def FindIndex(self, shape) -> int:
        for i in self._buckets.get(self._bucket(shape), ()):
            if self._items[i - 1].IsSame(shape):
                return i
        return 0

    def FindKey(self, i):
        if i < 1 or i > len(self._items):
            raise ValueError(f"index {i} out of range (1..{len(self._items)})")
        return self._items[i - 1]

    def Contains(self, shape) -> bool:
        return self.FindIndex(shape) != 0

    def Extent(self) -> int:
        return len(self._items)

    Size = Extent


class _PyAncestorMap:
    """Stand-in for TopTools_IndexedDataMapOfShapeListOfShape as filled by
    TopExp::MapShapesAndAncestors -- sub-shape -> the shapes that use it."""

    def __init__(self, keys: _PyIndexedMap, ancestors: dict):
        self._keys = keys
        self._ancestors = ancestors

    @classmethod
    def of(cls, shape, sub_type, anc_type) -> "_PyAncestorMap":
        keys, ancestors = _PyIndexedMap(), {}
        for anc in _explore(shape, anc_type):
            for sub in _explore(anc, sub_type):
                ancestors.setdefault(keys.Add(sub), []).append(anc)
        return cls(keys, ancestors)

    def FindIndex(self, shape) -> int:
        return self._keys.FindIndex(shape)

    def FindFromIndex(self, i) -> list:
        return self._ancestors.get(i, [])

    def FindKey(self, i):
        return self._keys.FindKey(i)

    def Extent(self) -> int:
        return self._keys.Extent()


def indexed_map(shape, typ):
    """Indexed map of every `typ` sub-shape -- the OCC class where the build
    has it, the Python stand-in where it doesn't."""
    cls = _occ_class("TopTools", "TopTools_IndexedMapOfShape")
    if cls is None:
        return _PyIndexedMap.of(shape, typ)
    m = cls()
    _map_shapes(shape, typ, m)
    return m


def ancestor_map(shape, sub_type, anc_type):
    """Sub-shape -> using-shapes map (e.g. edge -> its faces), same fallback."""
    cls = _occ_class("TopTools", "TopTools_IndexedDataMapOfShapeListOfShape")
    if cls is None:
        return _PyAncestorMap.of(shape, sub_type, anc_type)
    m = cls()
    _static(TopExp, "MapShapesAndAncestors")(shape, sub_type, anc_type, m)
    return m


def _face_map(shape):
    from OCP.TopAbs import TopAbs_FACE

    return indexed_map(shape, TopAbs_FACE)


def _edge_map(shape):
    from OCP.TopAbs import TopAbs_EDGE

    return indexed_map(shape, TopAbs_EDGE)


def _centroid(face) -> tuple[float, float, float]:
    props = GProp_GProps()
    _surface_props(face, props)
    c = props.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def _cylinder_geometry(face):
    """Return a native or exactly recoverable NURBS cylinder and its face sweep."""
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() == GeomAbs_Cylinder:
        return surf.Cylinder(), math.degrees(surf.LastUParameter() - surf.FirstUParameter())
    from OCP.GeomAbs import GeomAbs_BSplineSurface
    if surf.GetType() != GeomAbs_BSplineSurface:
        return None
    from OCP.Geom import Geom_CylindricalSurface
    from OCP.GeomConvert import GeomConvert_SurfToAnaSurf
    try:
        analytic = GeomConvert_SurfToAnaSurf(_static(BRep_Tool, "Surface")(face)).ConvertToAnalytical(1e-6)
    except Exception:
        return None
    if not isinstance(analytic, Geom_CylindricalSurface):
        return None
    cyl = analytic.Cylinder()
    axis = cyl.Axis().Direction()
    direction = (axis.X(), axis.Y(), axis.Z())
    from OCP.TopAbs import TopAbs_VERTEX
    vertices = []
    for vertex in _explore(face, TopAbs_VERTEX):
        p = _static(BRep_Tool, "Pnt")(_static(TopoDS, "Vertex")(vertex))
        vertices.append(_dot((p.X(), p.Y(), p.Z()), direction))
    height = max(vertices) - min(vertices) if vertices else 0
    if height <= 1e-6:
        return None
    props = GProp_GProps()
    _surface_props(face, props)
    sweep = math.degrees(props.Mass() / (cyl.Radius() * height))
    return cyl, sweep if sweep <= 360.5 else 360.0


def _cylinder_faces(shape, fmap=None):
    """Join adjacent faces on the same cylinder (common in NURBS STEP exports)."""
    fmap = fmap or _face_map(shape)
    found = {}
    for i in range(1, fmap.Extent() + 1):
        geometry = _cylinder_geometry(_face(fmap.FindKey(i)))
        if geometry:
            found[i] = {"cylinder": geometry[0], "sweep": geometry[1], "group": i}
    if not found:
        return found
    emap = _edge_map(shape)
    users = {}
    for i in found:
        for edge in _explore(_face(fmap.FindKey(i)), TopAbs_EDGE):
            users.setdefault(emap.FindIndex(edge), []).append(i)
    parent = {i: i for i in found}
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for adjacent in users.values():
        for a in adjacent:
            for b in adjacent:
                if a >= b:
                    continue
                ca, cb = found[a]["cylinder"], found[b]["cylinder"]
                da, db = ca.Axis().Direction(), cb.Axis().Direction()
                va, vb = (da.X(), da.Y(), da.Z()), (db.X(), db.Y(), db.Z())
                pa, pb = ca.Axis().Location(), cb.Axis().Location()
                offset = (pa.X() - pb.X(), pa.Y() - pb.Y(), pa.Z() - pb.Z())
                if abs(ca.Radius() - cb.Radius()) < 1e-5 and abs(_dot(va, vb)) > 1 - 1e-8 and math.sqrt(_dot(_cross(offset, va), _cross(offset, va))) < 1e-5:
                    parent[root(b)] = root(a)
    totals = {}
    for i, info in found.items():
        info["group"] = root(i)
        totals[info["group"]] = totals.get(info["group"], 0) + info["sweep"]
    for info in found.values():
        info["group_sweep"] = totals[info["group"]]
    return found


def planar_frame(face):
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Plane:
        raise ValueError('Select a planar face. Curved surfaces need a datum-plane sketch.')
    plane = surf.Plane()
    n = list(plane.Axis().Direction().Coord())
    if face.Orientation() == TopAbs_REVERSED:
        n = [-value for value in n]
    center, location = _centroid(face), plane.Location().Coord()
    distance = sum((center[k]-location[k])*n[k] for k in range(3))
    origin = [center[k]-distance*n[k] for k in range(3)]
    reference = [1,0,0] if abs(n[0]) < .9 else [0,1,0]
    projection = sum(a*b for a,b in zip(reference,n))
    u = [reference[k]-projection*n[k] for k in range(3)]
    length = math.sqrt(sum(value*value for value in u))
    u = [value/length for value in u]
    v = [n[1]*u[2]-n[2]*u[1],n[2]*u[0]-n[0]*u[2],n[0]*u[1]-n[1]*u[0]]
    return {'origin':origin,'u':u,'v':v}


def face_sketch_plane(shape, face_id):
    faces = _face_map(shape)
    if face_id < 1 or face_id > faces.Extent():
        raise ValueError('Face is unavailable. Select a face on the current model.')
    return planar_frame(_face(faces.FindKey(face_id)))


def _face_meta(face, idx: int, cylinders=None) -> dict:
    surf = BRepAdaptor_Surface(face)
    t = surf.GetType()
    meta: dict = {"id": idx, "type": "other"}
    try:
        cx, cy, cz = _centroid(face)
        meta["centroid"] = [round(cx, 3), round(cy, 3), round(cz, 3)]
    except Exception:
        pass
    if t == GeomAbs_Plane:
        meta["type"] = "plane"
        ax = surf.Plane().Axis().Direction()
        n = [ax.X(), ax.Y(), ax.Z()]
        if face.Orientation() == TopAbs_REVERSED:
            n = [-v for v in n]
        meta["normal"] = [round(v, 5) for v in n]
        meta['plane_frame'] = planar_frame(face)
    elif idx in (cylinders or {}) or t == GeomAbs_Cylinder:
        meta["type"] = "cylinder"
        info = cylinders[idx] if cylinders else None
        cyl = info["cylinder"] if info else surf.Cylinder()
        meta["radius"] = round(cyl.Radius(), 3)
        sweep = info["group_sweep"] if info else math.degrees(surf.LastUParameter() - surf.FirstUParameter())
        meta["sweep_deg"] = round(sweep, 1)
        if info:
            meta["cylinder_group"] = info["group"]
        ax = cyl.Axis().Direction()
        meta["axis"] = [round(ax.X(), 5), round(ax.Y(), 5), round(ax.Z(), 5)]
    return meta


# ---------------------------------------------------------------------------
# Face-tagged mesh
# ---------------------------------------------------------------------------


def _tri_node(tri, k):
    """Triangulation node access across OCC versions (Node(i) vs Nodes().Value(i))."""
    try:
        return tri.Node(k)
    except (AttributeError, TypeError):
        return tri.Nodes().Value(k)


def _tri_indices(triangle):
    """Triangle vertex indices across OCC versions."""
    try:
        g = triangle.Get()
        if g is not None:
            return g
    except TypeError:
        # Same trap as _box_limits in cad/repair.py: a build that hasn't bound
        # the struct this returns raises rather than returning None.
        pass
    return (triangle.Value(1), triangle.Value(2), triangle.Value(3))


def faced_mesh(shape) -> dict:
    """Tessellate the shape, returning vertices + triangles tagged by face id.

    positions: flat [x,y,z, ...] float list
    indices:   flat triangle vertex indices into positions
    tri_face:  face id (1-based) for each triangle (len == indices/3)
    faces:     per-face metadata (type/normal/axis/centroid/radius/sweep)
    """
    # 4-arg form matches the proven cad.preview meshing — the 5-arg
    # (parallel) overload is missing on some OCC builds.
    BRepMesh_IncrementalMesh(shape, 0.3, False, 0.5).Perform()
    fmap = _face_map(shape)
    cylinders = _cylinder_faces(shape, fmap)
    positions: list[float] = []
    indices: list[int] = []
    tri_face: list[int] = []
    faces: list[dict] = []
    vbase = 0
    for i in range(1, fmap.Extent() + 1):
        face = _face(fmap.FindKey(i))
        faces.append(_face_meta(face, i, cylinders))
        loc = TopLoc_Location()
        tri = _triangulation(face, loc)
        if tri is None:
            continue
        trsf = loc.Transformation()
        n = tri.NbNodes()
        for k in range(1, n + 1):
            p = _tri_node(tri, k).Transformed(trsf)
            positions.extend((round(p.X(), 3), round(p.Y(), 3), round(p.Z(), 3)))
        reversed_ = face.Orientation() == TopAbs_REVERSED
        for t in range(1, tri.NbTriangles() + 1):
            a, b, c = _tri_indices(tri.Triangle(t))
            if reversed_:
                b, c = c, b
            indices.extend((vbase + a - 1, vbase + b - 1, vbase + c - 1))
            tri_face.append(i)
        vbase += n
    return {
        "positions": positions,
        "indices": indices,
        "tri_face": tri_face,
        "faces": faces,
        "face_count": fmap.Extent(),
    }


# ---------------------------------------------------------------------------
# Indexed edges
# ---------------------------------------------------------------------------

_EDGE_TYPE = {GeomAbs_Line: "line", GeomAbs_Circle: "circle"}


def _edge_geometry(edge):
    curve = BRepAdaptor_Curve(edge)
    kind = _EDGE_TYPE.get(curve.GetType())
    if kind:
        return kind, curve.Line() if kind == "line" else curve.Circle()
    from OCP.GeomAbs import GeomAbs_BSplineCurve
    if curve.GetType() != GeomAbs_BSplineCurve:
        return None
    from OCP.Geom import Geom_Circle, Geom_Line
    from OCP.GeomConvert import GeomConvert_CurveToAnaCurve
    try:
        analytic = GeomConvert_CurveToAnaCurve.ComputeCurve_s(
            _static(BRep_Tool, "Curve")(edge, 0.0, 0.0), 1e-6,
            curve.FirstParameter(), curve.LastParameter(), 0.0, 0.0, 0.0
        )
    except Exception:
        return None
    if isinstance(analytic, Geom_Line):
        return "line", analytic.Lin()
    if isinstance(analytic, Geom_Circle):
        return "circle", analytic.Circ()
    return None


def indexed_edges(shape) -> list:
    """Return edges as 3D polylines with a stable id and curve type."""
    from OCP.GCPnts import GCPnts_TangentialDeflection

    from cad.loader import as_edge, finite

    emap = _edge_map(shape)
    out = []
    for i in range(1, emap.Extent() + 1):
        sub = emap.FindKey(i)
        if sub.IsNull():
            continue
        try:
            edge = as_edge(sub)
            if _degenerated(edge):
                continue
            curve = BRepAdaptor_Curve(edge)
            first, last = curve.FirstParameter(), curve.LastParameter()
            if not (finite(first) and finite(last) and last > first):
                continue
            disc = GCPnts_TangentialDeflection()
            disc.Initialize(curve, 0.3, 0.04)
            if disc.NbPoints() < 2:
                continue
            curve_type = (_edge_geometry(edge) or ("curve", None))[0]
            pts = []
            for j in range(1, disc.NbPoints() + 1):
                p = disc.Value(j)
                if finite(p.X()) and finite(p.Y()) and finite(p.Z()):
                    pts.append([p.X(), p.Y(), p.Z()] if curve_type == "line" else [round(p.X(), 3), round(p.Y(), 3), round(p.Z(), 3)])
            if len(pts) < 2:
                continue
            out.append(
                {
                    "id": i,
                    "type": curve_type,
                    "points": pts,
                }
            )
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# Measure
# ---------------------------------------------------------------------------


def _sub_shape(shape, kind: str, ent_id: int):
    m = _face_map(shape) if kind == "face" else _edge_map(shape)
    if ent_id < 1 or ent_id > m.Extent():
        raise ValueError(f"{kind} id {ent_id} out of range (1..{m.Extent()})")
    return m.FindKey(ent_id)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    m = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / m, a[1] / m, a[2] / m)


def _rnd3(p):
    return [round(p[0], 3), round(p[1], 3), round(p[2], 3)]


def _solve3(rows, b):
    """Solve 3x3 linear system via Cramer's rule. rows = 3 vectors, b = 3-tuple."""
    (a, c, d), (e, f, g), (h, i, j) = rows
    det = a * (f * j - g * i) - c * (e * j - g * h) + d * (e * i - f * h)
    if abs(det) < 1e-9:
        return None
    bx, by, bz = b
    dx = bx * (f * j - g * i) - c * (by * j - g * bz) + d * (by * i - f * bz)
    dy = a * (by * j - g * bz) - bx * (e * j - g * h) + d * (e * bz - by * h)
    dz = a * (f * bz - by * i) - c * (e * bz - by * h) + bx * (e * i - f * h)
    return (dx / det, dy / det, dz / det)


def _cylinder_center(face):
    """Axis-projected centre, unit axis, radius of a cylindrical face."""
    cyl = _cylinder_geometry(face)[0]
    base = (cyl.Axis().Location().X(), cyl.Axis().Location().Y(), cyl.Axis().Location().Z())
    axis = _unit((cyl.Axis().Direction().X(), cyl.Axis().Direction().Y(), cyl.Axis().Direction().Z()))
    c = _centroid(face)
    t = _dot((c[0] - base[0], c[1] - base[1], c[2] - base[2]), axis)
    center = [base[i] + axis[i] * t for i in range(3)]
    return center, axis, cyl.Radius()


def measure_single(shape, kind: str, ent_id: int, cylinder_faces=None, face_map=None) -> dict:
    """Smart single-entity dimension: cylinder face -> Ø (full hole) or R (arc/bend)."""
    if kind != "face":
        raise ValueError("single-entity dimension needs a cylindrical face")
    f = _face(face_map.FindKey(ent_id) if face_map is not None else _sub_shape(shape, "face", ent_id))
    info = (cylinder_faces if cylinder_faces is not None else _cylinder_faces(shape)).get(ent_id)
    if not info:
        raise ValueError("pick a hole or cylindrical face for Ø / R")
    cyl = info["cylinder"]
    r = cyl.Radius()
    ax = cyl.Axis()
    base = (ax.Location().X(), ax.Location().Y(), ax.Location().Z())
    axis = _unit((ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()))
    c = _centroid(f)
    t = _dot((c[0] - base[0], c[1] - base[1], c[2] - base[2]), axis)
    center = [base[i] + axis[i] * t for i in range(3)]
    perp = _cross(axis, (1.0, 0.0, 0.0))
    if math.sqrt(_dot(perp, perp)) < 1e-6:
        perp = _cross(axis, (0.0, 1.0, 0.0))
    perp = _unit(perp)
    sweep = info["group_sweep"]
    if sweep >= 350:
        p1 = [center[i] + perp[i] * r for i in range(3)]
        p2 = [center[i] - perp[i] * r for i in range(3)]
        return {"type": "dia", "value_mm": round(2 * r, 3), "p1": _rnd3(p1), "p2": _rnd3(p2),
                "center": _rnd3(center), "suggested_gauge": "Vernier"}
    p2 = [center[i] + perp[i] * r for i in range(3)]
    return {"type": "rad", "value_mm": round(r, 3), "p1": _rnd3(center), "p2": _rnd3(p2),
            "center": _rnd3(center), "suggested_gauge": "Radius Gauge"}


def measure_single_from_file(path: str, kind, ent_id) -> dict:
    return measure_single(load_step(path), kind, ent_id)


def measure(
    shape,
    kind1: str,
    id1: int,
    kind2: str,
    id2: int,
) -> dict:
    """Distance between two sub-shapes.

    Default = BRepExtrema minimum distance + the two closest points.
    Special case: two parallel planar faces -> perpendicular gap (the
    QA-intended dimension), drawn centroid-to-projection.
    """
    s1 = _sub_shape(shape, kind1, id1)
    s2 = _sub_shape(shape, kind2, id2)

    # Parallel-plane perpendicular distance
    if kind1 == "face" and kind2 == "face":
        f1, f2 = _face(s1), _face(s2)
        a1, a2 = BRepAdaptor_Surface(f1), BRepAdaptor_Surface(f2)
        if a1.GetType() == GeomAbs_Plane and a2.GetType() == GeomAbs_Plane:
            pln1 = a1.Plane()
            d1 = pln1.Axis().Direction()
            d2 = a2.Plane().Axis().Direction()
            n1 = (d1.X(), d1.Y(), d1.Z())
            n2 = (d2.X(), d2.Y(), d2.Z())
            if abs(_dot(n1, n2)) > 0.999:
                from OCP.gp import gp_Pnt

                c2 = _centroid(f2)
                gap = pln1.Distance(gp_Pnt(*c2))
                # project c2 onto plane1 along n1
                loc = pln1.Location()
                p0 = (loc.X(), loc.Y(), loc.Z())
                signed = _dot((c2[0] - p0[0], c2[1] - p0[1], c2[2] - p0[2]), n1)
                p1 = [c2[i] - n1[i] * signed for i in range(3)]
                return {
                    "value_mm": round(gap, 3),
                    "p1": [round(v, 3) for v in p1],
                    "p2": [round(v, 3) for v in c2],
                    "mode": "surface-to-surface",
                    "method": "parallel-plane",
                    "suggested_gauge": "Vernier",
                }
            # non-parallel planes -> angle, drawn at the shared (dihedral) edge
            n1u, n2u = _unit(n1), _unit(n2)
            c1, c2 = _centroid(f1), _centroid(f2)
            P1 = (pln1.Location().X(), pln1.Location().Y(), pln1.Location().Z())
            pln2 = a2.Plane()
            P2 = (pln2.Location().X(), pln2.Location().Y(), pln2.Location().Z())
            e = _cross(n1u, n2u)
            # Fallback angle from normals (orientation-independent): the dihedral
            # between two planes is acos(|n1.n2|)'s supplement, but face normals can
            # point either way, so the normals alone are ambiguous. Keep this only as
            # a fallback; the true surface-to-surface angle is measured below from the
            # in-plane stub directions (what a protractor actually reads).
            ang = math.degrees(math.acos(min(1.0, max(-1.0, abs(_dot(n1u, n2u))))))
            res = {
                "type": "angle", "value_mm": round(ang, 1),
                "mode": "angle", "method": "face-angle", "suggested_gauge": "Protractor",
                "p1": _rnd3(c1), "p2": _rnd3(c2),
            }
            if _dot(e, e) > 1e-9:
                e = _unit(e)
                p0 = _solve3((n1u, n2u, e), (_dot(n1u, P1), _dot(n2u, P2), 0.0))
                if p0 is not None:
                    mid = [(c1[i] + c2[i]) / 2 for i in range(3)]
                    t = _dot((mid[0] - p0[0], mid[1] - p0[1], mid[2] - p0[2]), e)
                    vtx = [p0[i] + e[i] * t for i in range(3)]
                    def _stub(c):
                        w = [c[i] - vtx[i] for i in range(3)]
                        w = [w[i] - e[i] * _dot(w, e) for i in range(3)]
                        return _unit(w)
                    d1, d2 = _stub(c1), _stub(c2)
                    res["vertex"] = _rnd3(vtx)
                    res["dir1"] = _rnd3(d1)
                    res["dir2"] = _rnd3(d2)
                    # True surface-to-surface angle: the angle subtended at the shared
                    # edge between the two faces, measured from the edge toward each
                    # face centroid. This reports the real opening angle (e.g. 135deg),
                    # not just the acute one.
                    res["value_mm"] = round(
                        math.degrees(math.acos(min(1.0, max(-1.0, _dot(d1, d2))))), 1
                    )
            return res

        # cylinder (hole) + plane -> centre-to-surface distance
        c1, c2 = _cylinder_geometry(f1), _cylinder_geometry(f2)
        if (c1 and a2.GetType() == GeomAbs_Plane) or (c2 and a1.GetType() == GeomAbs_Plane):
            fcyl, fpln = (f1, f2) if c1 else (f2, f1)
            apln = BRepAdaptor_Surface(fpln)
            center, _axis, _r = _cylinder_center(fcyl)
            pln = apln.Plane()
            nn = _unit((pln.Axis().Direction().X(), pln.Axis().Direction().Y(), pln.Axis().Direction().Z()))
            lp = (pln.Location().X(), pln.Location().Y(), pln.Location().Z())
            signed = _dot((center[0] - lp[0], center[1] - lp[1], center[2] - lp[2]), nn)
            foot = [center[i] - nn[i] * signed for i in range(3)]
            return {
                "value_mm": round(abs(signed), 3),
                "p1": _rnd3(center), "p2": _rnd3(foot),
                "mode": "surface-to-surface", "method": "center-to-plane",
                "suggested_gauge": "Vernier",
            }

    if {kind1, kind2} == {"face", "edge"}:
        face = _face(s1 if kind1 == "face" else s2)
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() == GeomAbs_Plane:
            edge = _static(TopoDS, "Edge")(s1 if kind1 == "edge" else s2)
            geometry = _edge_geometry(edge)
            if geometry and geometry[0] == "line":
                curve = BRepAdaptor_Curve(edge)
                a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
                midpoint = [(a.X()+b.X())/2, (a.Y()+b.Y())/2, (a.Z()+b.Z())/2]
                pln = surface.Plane()
                direction = pln.Axis().Direction()
                normal = (direction.X(), direction.Y(), direction.Z())
                axis = geometry[1].Direction()
                if abs(_dot(normal, (axis.X(), axis.Y(), axis.Z()))) > 1e-6:
                    raise ValueError("Select a straight edge parallel to the surface for a perpendicular gap.")
                origin = pln.Location()
                signed = _dot(tuple(midpoint[i]-v for i, v in enumerate((origin.X(), origin.Y(), origin.Z()))), normal)
                foot = [midpoint[i]-signed*normal[i] for i in range(3)]
                p1, p2 = (foot, midpoint) if kind1 == "face" else (midpoint, foot)
                return {"label": "Plane to edge", "value_mm": round(abs(signed), 3),
                        "p1": _rnd3(p1), "p2": _rnd3(p2), "mode": "surface-to-edge",
                        "method": "plane-to-edge", "suggested_gauge": "Vernier"}

    dss = BRepExtrema_DistShapeShape(s1, s2)
    if not dss.IsDone():
        raise ValueError("distance computation failed")
    val = dss.Value()
    pa = dss.PointOnShape1(1)
    pb = dss.PointOnShape2(1)
    mode = "surface-to-surface" if kind1 == kind2 == "face" else (
        "edge-to-edge" if kind1 == kind2 == "edge" else "surface-to-edge"
    )
    return {
        "value_mm": round(val, 3),
        "p1": [round(pa.X(), 3), round(pa.Y(), 3), round(pa.Z(), 3)],
        "p2": [round(pb.X(), 3), round(pb.Y(), 3), round(pb.Z(), 3)],
        "mode": mode,
        "method": "min-distance",
        "suggested_gauge": "Vernier",
    }


def measure_from_file(path: str, kind1, id1, kind2, id2) -> dict:
    return measure(load_step(path), kind1, id1, kind2, id2)


# ---------------------------------------------------------------------------
# Auto-suggest checks
# ---------------------------------------------------------------------------


def _bend_angles(shape) -> list:
    """Bend angle = sweep of partial-cylinder bend faces (holes sweep ~360).

    Dedupe near-equal angles (inner/outer faces of one bend share an angle).
    """
    fmap = _face_map(shape)
    angles: list[float] = []
    for i in range(1, fmap.Extent() + 1):
        surf = BRepAdaptor_Surface(_face(fmap.FindKey(i)))
        if surf.GetType() != GeomAbs_Cylinder:
            continue
        sweep = math.degrees(surf.LastUParameter() - surf.FirstUParameter())
        if sweep >= 350 or sweep < 5:
            continue  # full hole or sliver
        angles.append(round(sweep))
    # merge within 2 deg
    uniq: list[int] = []
    for a in sorted(angles):
        if not any(abs(a - u) <= 2 for u in uniq):
            uniq.append(a)
    return uniq


def suggest(path: str) -> dict:
    """Candidate inspection checks from auto-extracted geometry."""
    from analysis.part_analyser import analyse_part

    shape = load_step(path)
    info = analyse_part(path)
    checks: list[dict] = []

    bbox = info.get("bbox_mm") or []
    for label, val in zip(("Length", "Width", "Height"), bbox):
        checks.append(
            {
                "desc": f"Check overall {label.lower()}",
                "value_mm": round(val, 2),
                "tol": "+/- 0.5mm",
                "gauge": "Vernier",
                "source": "bbox",
            }
        )

    for d in info.get("holes_mm") or []:
        checks.append(
            {
                "desc": "Check hole diameter",
                "value_mm": round(d, 2),
                "tol": "+/- 0.1mm",
                "gauge": "Vernier",
                "source": "hole",
            }
        )

    for ang in _bend_angles(shape):
        checks.append(
            {
                "desc": "Ensure bend angle",
                "value_mm": ang,
                "tol": "+/- 1 deg",
                "gauge": "Protractor",
                "source": "bend",
            }
        )

    return {"checks": checks, "part": info.get("components", [{}])[0]}
