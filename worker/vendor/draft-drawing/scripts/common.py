"""Shared OCP helpers. Adapted from design-fixture (survey_step, flange_features, render_review, preview)
so this skill has no dependency on it."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere, GeomAbs_Torus
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TColStd import TColStd_SequenceOfAsciiString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.gp import gp_Pnt

ROOT = Path(__file__).resolve().parents[1]
PLANAR_TOL_MM, MAX_THICKNESS_MM, MIN_AREA_MM2, MIN_WIDTH_MM = 0.05, 6.0, 20.0, 5.0
CURVED = {GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus}


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bbox(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    values = list(box.Get())
    return {"min": values[:3], "max": values[3:],
            "size": [values[i + 3] - values[i] for i in range(3)]}


def shapes_of(shape, kind):
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        yield explorer.Current()
        explorer.Next()


def label_name(label):
    attr = TDataStd_Name()
    return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), attr) else "unnamed"


def read_occurrences(path):
    """Return every leaf occurrence with assembly placements, including repeated names."""
    doc = TDocStd_Document(TCollection_ExtendedString("survey"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError(f"Cannot read STEP: {path}")
    length, angle, solid_angle = (TColStd_SequenceOfAsciiString() for _ in range(3))
    reader.Reader().FileUnits(length, angle, solid_angle)
    source_units = [length.Value(i).ToCString() for i in range(1, length.Length() + 1)]
    # OCCT expresses this setting in millimetres: 1.0 means output coordinates in mm.
    reader.Reader().SetSystemLengthUnit(1.0)
    if not reader.Transfer(doc):
        raise ValueError("STEP transfer failed")
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    leaves = []

    def visit(label, parent, path, indices, active):
        definition = label
        if st.IsReference_s(label):
            definition = TDF_Label()
            if not st.GetReferredShape_s(label, definition):
                raise ValueError("Unresolved STEP occurrence")
        # Index path disambiguates otherwise identical names and shared definitions.
        path = path + [label_name(label)]
        if st.IsAssembly_s(definition):
            if any(definition.IsEqual(ancestor) for ancestor in active):
                raise ValueError("Cyclic STEP assembly reference")
            location = parent.Multiplied(st.GetLocation_s(label))
            children = TDF_LabelSequence()
            st.GetComponents_s(definition, children)
            for j in range(1, children.Length() + 1):
                visit(children.Value(j), location, path, indices + [j], active + [definition])
        else:
            # GetShape(component) includes its own location; only add its ancestors.
            shape = st.GetShape_s(label)
            if shape.IsNull():
                raise ValueError(f"Null shape at {path}")
            leaves.append((shape.Moved(parent), {"occurrence_path": path,
                          "occurrence_index_path": indices,
                          "product_name": label_name(definition)}))

    for i in range(1, roots.Length() + 1):
        visit(roots.Value(i), TopLoc_Location(), [], [i], [])
    return leaves, source_units


def _dist(a, b):
    m = BRepExtrema_DistShapeShape(a, b)
    if not m.IsDone(): raise ValueError('distance query failed')
    return m.Value()


def _vertex(p):
    return BRepBuilderAPI_MakeVertex(gp_Pnt(*[float(x) for x in p])).Vertex()


def _snap(face, p):
    """Nearest point on the trimmed face."""
    m = BRepExtrema_DistShapeShape(face, _vertex(p))
    m.Perform()
    q = m.PointOnShape1(1)
    return np.array([q.X(), q.Y(), q.Z()])


def planar_face(face):
    """(point, outward unit normal, deviation_mm, samples, type) for a near-planar face, else None."""
    s = BRepAdaptor_Surface(face, True)
    kind = s.GetType()
    if kind in CURVED: return None
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    pts = []
    for u in np.linspace(u0, u1, 9):
        for v in np.linspace(v0, v1, 9):
            q = BRepLProp_SLProps(s, u, v, 0, 1e-6).Value()
            pts.append([q.X(), q.Y(), q.Z()])
    pts = np.array(pts)
    if kind == GeomAbs_Plane:
        pl = s.Plane(); o = np.array(pl.Location().Coord()); n = np.array(pl.Axis().Direction().Coord()); dev = 0.0
    else:
        o = pts.mean(0); n = np.linalg.svd(pts - o)[2][2]
        dev = float(np.abs((pts - o) @ n).max())
        if dev > PLANAR_TOL_MM: return None
        pr = BRepLProp_SLProps(s, (u0 + u1) / 2, (v0 + v1) / 2, 1, 1e-6)
        if pr.IsNormalDefined() and np.dot(np.array(pr.Normal().Coord()), n) < 0: n = -n
    if face.Orientation() == TopAbs_REVERSED: n = -n
    return o, n / np.linalg.norm(n), dev, pts, str(kind).split('.')[-1].replace('GeomAbs_', '')


def faces_of(shape):
    it = TopExp_Explorer(shape, TopAbs_FACE); i = 0
    while it.More():
        i += 1; yield i, TopoDS.Face_s(it.Current()); it.Next()


def extract(shape, name, max_thickness=MAX_THICKNESS_MM):
    rows = []
    for i, f in faces_of(shape):
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        if g.Mass() < MIN_AREA_MM2: continue
        pf = planar_face(f)
        if pf: rows.append({'index': i, 'face': f, 'area': g.Mass(), 'centroid': np.array(g.CentreOfMass().Coord()),
                            'o': pf[0], 'n': pf[1], 'dev': pf[2], 'pts': pf[3], 'type': pf[4]})
    parent = list(range(len(rows)))
    def root(k):
        while parent[k] != k: parent[k] = parent[parent[k]]; k = parent[k]
        return k
    thick = {}
    for a in range(len(rows)):
        for b in range(a + 1, len(rows)):
            A, B = rows[a], rows[b]
            if A['n'] @ B['n'] > -0.999: continue
            d = float((A['o'] - B['o']) @ A['n'])  # B lies behind A (inside the material) when d > 0
            if not 0.2 < d <= max_thickness or abs(float((B['o'] - A['o']) @ B['n']) - d) > 0.05: continue
            if _dist(A['face'], B['face']) > d + 0.05: continue
            thick[(a, b)] = d
    if thick:  # sheet parts have one thickness: keep only pairs at the dominant separation
        vals = np.round(list(thick.values()), 1)
        mode = max(set(vals.tolist()), key=lambda t: sum(abs(vals - t) <= 0.1))
        thick = {k: v for k, v in thick.items() if abs(v - mode) <= 0.1}
    for a, b in thick:
        parent[root(a)] = root(b)
    groups = {}
    for a, b in thick:
        groups.setdefault(root(a), set()).update((a, b))
    center = np.mean([r['centroid'] for r in rows], 0) if rows else np.zeros(3)
    out = []
    for members in sorted(groups.values(), key=lambda m: min(rows[k]['index'] for k in m)):
        fs = [rows[k] for k in sorted(members)]
        by_n = {}
        for r in fs: by_n.setdefault(tuple(np.round(r['n'], 3)), []).append(r)
        # Outer side: the face set whose normal points away from the part's face centroid.
        side = max(by_n.values(), key=lambda s: float(np.dot(s[0]['n'], s[0]['centroid'] - center)))
        outer = max(side, key=lambda r: r['area'])
        n = outer['n']; pts = np.vstack([r['pts'] for r in side]); c = outer['centroid']
        flat = (pts - c) - np.outer((pts - c) @ n, n)
        axes = np.linalg.svd(flat, full_matrices=False)[2][:2]
        long = axes[0] / np.linalg.norm(axes[0])
        for e in np.eye(3):  # snap a sampled axis within ~3 deg of a fixture axis
            if abs(long @ e) > 0.9986: long = e * np.sign(long @ e)
        span = float(np.ptp(flat @ long)); width = float(np.ptp(flat @ axes[1]))
        out.append({'id': f'{name}:F{len(out) + 1:02d}', 'part_shape': name, 'faces': [r['index'] for r in fs],
                    'outer_faces': [r['index'] for r in side], 'surface_types': sorted({r['type'] for r in fs}),
                    'thickness_mm': round(min(v for (a, b), v in thick.items() if a in members), 3),
                    'planarity_deviation_mm': round(max(r['dev'] for r in fs), 4),
                    'outer_normal': np.round(n, 6).tolist(), 'outer_point_mm': np.round(_snap(outer['face'], c), 4).tolist(),
                    'long_axis': np.round(long, 6).tolist(), 'span_mm': round(span, 2), 'width_mm': round(width, 2), 'narrow': width < MIN_WIDTH_MM,
                    'area_mm2': round(sum(r['area'] for r in side), 1), '_faces': [r['face'] for r in fs],
                    '_outer': [r['face'] for r in side], '_inner': [r['face'] for r in fs if r not in side]})
    return out


def triangles(shape):
    BRepMesh_IncrementalMesh(shape, .35, False, .3, True).Perform()
    out = []
    for _, f in faces_of(shape):
        loc = TopLoc_Location(); tri = BRep_Tool.Triangulation_s(f, loc)
        if tri is None: continue
        for i in range(1, tri.NbTriangles() + 1):
            out.append([tri.Node(j).Transformed(loc.Transformation()).Coord() for j in tri.Triangle(i).Get()])
    if not out: raise ValueError('STEP shape could not be tessellated')
    return np.array(out)


def compact_mesh(triangles, target=1800):
    """Vertex clustering, preserving connected triangles; never stride/drop arbitrary facets."""
    raw = np.asarray(triangles, dtype=float).reshape(-1, 3, 3)
    points = raw.reshape(-1, 3)
    if not np.isfinite(points).all() or len(raw) == 0: raise ValueError('Invalid preview mesh')
    vertices, inverse = np.unique(np.round(points, 4), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    span = max(float(np.ptp(points, axis=0).max()), 1e-6)
    cell = span / 700
    for _ in range(24):
        if len(faces) <= target: break
        keys = np.floor((vertices - points.min(axis=0)) / cell).astype(np.int64)
        _, mapping = np.unique(keys, axis=0, return_inverse=True)
        count = np.bincount(mapping)
        clustered = np.column_stack([np.bincount(mapping, weights=vertices[:, i]) / count for i in range(3)])
        remapped = mapping[faces]
        valid = (remapped[:, 0] != remapped[:, 1]) & (remapped[:, 1] != remapped[:, 2]) & (remapped[:, 0] != remapped[:, 2])
        candidate = remapped[valid]
        if len(candidate):
            _, keep = np.unique(np.sort(candidate, axis=1), axis=0, return_index=True)
            vertices, faces = clustered, candidate[np.sort(keep)]
        cell *= 1.6
    used, mapping = np.unique(faces, return_inverse=True)
    return {'positions': np.round(vertices[used], 3).ravel().tolist(), 'indices': mapping.ravel().tolist(),
            'source_triangles': len(raw), 'preview_triangles': len(faces), 'approximate': True}


