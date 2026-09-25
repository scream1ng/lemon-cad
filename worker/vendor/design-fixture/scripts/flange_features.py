#!/usr/bin/env python3
"""Sheet features of a placed part: flanges, tabs, walls and webs, each with a proposed checking rib.

A feature is a group of near-planar faces paired back-to-back at sheet thickness (outward normals opposed,
planes <= max_thickness apart, faces overlapping). Edge and bend faces have no such partner and drop out.
A feature under MIN_WIDTH_MM wide is kept and marked narrow (small return flanges still need a check).
B-spline/Bezier/other faces are plane-fitted on a UV sample grid and count as planar only within
PLANAR_TOL_MM; the measured deviation is always reported. Cylinders, cones, spheres and tori never count.
Proposals are design suggestions, never verified stations.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere, GeomAbs_Torus
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt

PLANAR_TOL_MM, MAX_THICKNESS_MM, MIN_AREA_MM2, ON_FEATURE_MM, MIN_WIDTH_MM = 0.05, 6.0, 20.0, 0.1, 5.0
CURVED = {GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus}
GAP_MM, T_MM = 3.0, 5.0


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


def on_feature(feature, point, tol=ON_FEATURE_MM):
    v = _vertex(point)
    return any(_dist(f, v) <= tol for f in feature['_faces'])


def propose(feature, gap=GAP_MM, thickness=T_MM):
    """Rib-edge land(s) clipped 3 mm off the base-facing face; a plate-face land for small vertical faces.

    Ribs rise from the base, so an up-facing outer face is gauged on its back (inner) face instead.
    """
    n, long = np.array(feature['outer_normal']), np.array(feature['long_axis'])
    z = np.array([0.0, 0.0, 1.0])
    faces = feature['_outer']
    if n @ z > 0.1 and feature['_inner']:
        n, faces = -n, feature['_inner']
    if abs(long @ z) < 0.1: w = long
    elif abs(n @ z) < 0.9: w = np.cross(z, n); w /= np.linalg.norm(w)
    else: w = None
    c = np.array(feature['outer_point_mm'])
    offs = [-0.35 * feature['span_mm'], 0.35 * feature['span_mm']] if feature['span_mm'] >= 60 else [0.0]
    stations = []
    for k, off in enumerate(offs, 1):
        p = _snap(min(faces, key=lambda f: _dist(f, _vertex(c + long * off))), c + long * off)
        row = {'station': k, 'point_mm': np.round(p, 3).tolist(), 'direction': n.round(6).tolist(),
               'offset_plane': {'point_mm': np.round(p, 3).tolist(), 'direction': n.round(6).tolist(), 'gap_mm': gap}}
        if w is None:
            row['rib'] = 'none: normal is vertical along a vertical long axis; needs explicit CAD'
        else:
            ax = int(np.argmax(np.abs(w)))
            if abs(abs(w[ax]) - 1) < 1e-6 and ax < 2:
                row['rib'] = {'plane': 'YZ' if ax == 0 else 'XZ', 'at_mm': round(float(p[ax]), 3),
                              'note': 'rib edge clipped by offset_plane (checking_ribs)'}
            else:
                row['rib'] = {'plane': 'oblique', 'normal': w.round(6).tolist(), 'note': 'oblique rib: explicit CAD'}
        stations.append(row)
    out = {'feature': feature['id'], 'stations': stations}
    if abs(n @ z) < 0.1 and max(feature['span_mm'], feature['width_mm']) < 25:
        mid = c + n * (gap + thickness / 2)
        out['plate_face_land'] = {'plate_mid_plane_point_mm': mid.round(3).tolist(), 'plate_normal': n.round(6).tolist(),
                                  'note': f'plate parallel to the face, its face {gap} mm off; neck it past neighbours'}
    return out


def public(feature):
    return {k: v for k, v in feature.items() if not k.startswith('_')}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('step'); ap.add_argument('--parts', nargs='*', help='Part_ shape names (default all Part_*)')
    a = ap.parse_args()
    from export_step import read_step
    shapes = read_step(a.step)
    names = a.parts or [k for k in shapes if k.split('/')[-1].startswith('Part_')]
    rows = []
    for name in names:
        for f in extract(shapes[name], name.split('/')[-1]):
            rows.append({**public(f), 'proposal': propose(f)})
    print(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main()
