#!/usr/bin/env python3
"""Measure a STEP file for a draft drawing: bodies, weight, overall size, flanges, bends, holes and slots.

Every number comes from the OCP B-rep. A body is dimensioned only when it is recognised as sheet metal
(its back-to-back face pairs at one thickness explain its volume); fasteners, welds and anything else are
listed and weighed but never dimensioned. Unrecognised geometry is reported under `unknowns`, never guessed.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_BSplineSurface, GeomAbs_Cylinder, GeomAbs_Sphere, GeomAbs_Torus
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_SOLID, TopAbs_WIRE
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf

from common import bbox, extract, faces_of, file_sha256, read_occurrences, shapes_of

STEEL_KG_M3 = 7850.0
SHEET_VOLUME_RATIO = (0.75, 1.5)  # body volume / (flat-face area x thickness) for a sheet part
CIRCLE_TOL_MM, SLOT_TOL_MM = 0.02, 0.05


def props(shape, kind='volume'):
    g = GProp_GProps()
    (BRepGProp.VolumeProperties_s if kind == 'volume' else BRepGProp.SurfaceProperties_s)(shape, g)
    return g


def surface_counts(shape):
    counts, small_cyl = Counter(), 0
    for _, f in faces_of(shape):
        s = BRepAdaptor_Surface(f)
        k = s.GetType()
        counts[str(k).split('.')[-1].replace('GeomAbs_', '')] += 1
        if k == GeomAbs_Cylinder and s.Cylinder().Radius() < 1.5: small_cyl += 1
    return counts, small_cyl


def classify(shape, volume):
    """('sheet', features, thickness) or (role, [], None); role guesses are labelled 'probable'."""
    feats = extract(shape, 'b')
    if feats:
        t = Counter(round(f['thickness_mm'], 1) for f in feats).most_common(1)[0][0]
        flat = sum(f['area_mm2'] for f in feats) * t
        if t >= 0.5 and SHEET_VOLUME_RATIO[0] <= volume / flat <= SHEET_VOLUME_RATIO[1]:
            return 'sheet', feats, t
    counts, small_cyl = surface_counts(shape)
    if counts['Torus'] or small_cyl >= 8: return 'fastener (probable)', [], None
    if counts['Sphere'] or counts['BSplineSurface']: return 'weld (probable)', [], None
    return 'unclassified', [], None


def signature(volume, size, faces):
    return (round(volume, 0), tuple(sorted(round(s * 2) / 2 for s in size)), faces)


# ---------- part frame ----------

def part_frame(feats):
    """Z = into the part from the largest flat feature (flanges rise +Z), X = its long axis; snapped within ~3 deg."""
    base = max(feats, key=lambda f: f['area_mm2'])
    z = -np.array(base['outer_normal'], float); x = np.array(base['long_axis'], float)
    for e in np.eye(3):
        if abs(z @ e) > 0.9986: z = e * np.sign(z @ e)
    x = x - (x @ z) * z; x /= np.linalg.norm(x)
    return base['id'], x, np.cross(z, x), z


def to_frame(shape, x, y, z):
    t = gp_Trsf()
    t.SetTransformation(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(*z), gp_Dir(*x)))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()



def face_box(faces, x, y, z, origin_local):
    """[min, max] of the faces in the part frame."""
    comp = TopoDS_Compound(); b = BRep_Builder(); b.MakeCompound(comp)
    for f in faces: b.Add(comp, f)
    bb = bbox(to_frame(comp, x, y, z))
    return [np.round(np.array(bb[k]) - origin_local, 2).tolist() for k in ('min', 'max')]

# ---------- holes and slots ----------

def wire_points(wire, per_edge=64):
    pts = []
    for e in shapes_of(wire, TopAbs_EDGE):
        c = BRepAdaptor_Curve(TopoDS.Edge_s(e))
        for u in np.linspace(c.FirstParameter(), c.LastParameter(), per_edge):
            pts.append(c.Value(u).Coord())
    return np.array(pts)


def fit_circle(p):
    a = np.column_stack([2 * p[:, 0], 2 * p[:, 1], np.ones(len(p))])
    cx, cy, k = np.linalg.lstsq(a, (p ** 2).sum(1), rcond=None)[0]
    r = math.sqrt(max(k + cx * cx + cy * cy, 0))
    return np.array([cx, cy]), r, float(np.abs(np.hypot(p[:, 0] - cx, p[:, 1] - cy) - r).max())


def _box(p2, a):
    """Centre, length (along a), width and in-frame coordinates of samples for axis a."""
    b = np.array([-a[1], a[0]]); u = p2 @ a; v = p2 @ b
    centre = ((u.max() + u.min()) / 2) * a + ((v.max() + v.min()) / 2) * b
    q = p2 - centre
    return centre, float(np.ptp(u)), float(np.ptp(v)), q @ a, q @ b


def classify_opening(p2):
    """Round hole, slot (stadium), rectangle or irregular cutout from wire samples in the feature plane."""
    c, r, err = fit_circle(p2)
    if err <= CIRCLE_TOL_MM:
        return {'type': 'hole', 'diameter_mm': round(2 * r, 2), 'centre_2d': c}
    m = p2.mean(0); svd = np.linalg.svd(p2 - m, full_matrices=False)[2]
    chords = np.diff(p2, axis=0); chords = chords[np.linalg.norm(chords, axis=1) > 1e-6]
    axes = [svd[0], svd[1]] + [ch / np.linalg.norm(ch) for ch in chords[::max(1, len(chords) // 64)]]
    best = None
    for a in axes:
        centre, length, width, qu, qv = _box(p2, a)
        if length < width: continue
        half = (length - width) / 2
        slot = np.abs(np.hypot(np.clip(np.abs(qu) - half, 0, None), qv) - width / 2).max()
        rect = np.abs(np.maximum(np.abs(qu) - length / 2, np.abs(qv) - width / 2)).max()
        for kind, e in (('slot', slot), ('rectangle', rect)):
            if best is None or e < best[0]: best = (e, kind, a, centre, length, width)
    e, kind, a, centre, length, width = best
    if e <= SLOT_TOL_MM and not (kind == 'slot' and length - width < 0.05):
        return {'type': kind, 'width_mm': round(width, 2), 'length_mm': round(length, 2), 'centre_2d': centre, 'axis_2d': a}
    centre, length, width, _, _ = _box(p2, svd[0])
    return {'type': 'cutout', 'size_mm': [round(length, 2), round(width, 2)], 'centre_2d': centre, 'axis_2d': svd[0]}


def openings(feature, frame_pt):
    """Inner wires of a feature's outer faces. frame_pt maps model points to the part frame."""
    n = np.array(feature['outer_normal']); o = np.array(feature['outer_point_mm'])
    e1 = np.array(feature['long_axis']); e2 = np.cross(n, e1)
    out = []
    for face in feature['_outer']:
        outer = BRepTools.OuterWire_s(face)
        for w in shapes_of(face, TopAbs_WIRE):
            if w.IsSame(outer): continue
            p = wire_points(TopoDS.Wire_s(w))
            depth = (p - o) @ n
            p2 = np.column_stack([(p - o) @ e1, (p - o) @ e2])
            row = classify_opening(p2)
            c2 = row.pop('centre_2d')
            model = o + c2[0] * e1 + c2[1] * e2 + float(depth.mean()) * n
            row.update({'feature': feature['id'], 'model_mm': np.round(model, 3).tolist(),
                        'part_mm': np.round(frame_pt(model), 3).tolist(), 'axis_model': np.round(n, 4).tolist()})
            if 'axis_2d' in row:
                a = row.pop('axis_2d'); a3 = a[0] * e1 + a[1] * e2
                row['long_dir_model'] = np.round(a3, 4).tolist()
            out.append(row)
    return out


# ---------- bends ----------

def cylinder_of(face):
    """(radius, axis, point on axis, sweep_deg, axial span, radial unit vectors at the two arc ends) for an analytic or B-spline cylinder face, else None."""
    s = BRepAdaptor_Surface(face)
    k = s.GetType()
    if k not in (GeomAbs_Cylinder, GeomAbs_BSplineSurface): return None
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    pts, nrm = [], []
    for u in np.linspace(u0, u1, 7):
        for v in np.linspace(v0, v1, 7):
            pr = BRepLProp_SLProps(s, u, v, 1, 1e-6)
            pts.append(pr.Value().Coord())
            if pr.IsNormalDefined(): nrm.append(pr.Normal().Coord())
    pts, nrm = np.array(pts), np.array(nrm)
    if k == GeomAbs_Cylinder:
        c = s.Cylinder(); ax = np.array(c.Axis().Direction().Coord()); loc = np.array(c.Location().Coord()); r = c.Radius()
    else:
        if len(nrm) < 20: return None
        ax = np.linalg.svd(nrm, full_matrices=False)[2][2]
        if np.abs(nrm @ ax).max() > 0.01: return None
        e1 = np.cross(ax, [1, 0, 0] if abs(ax[0]) < 0.9 else [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
        c2, r, err = fit_circle(np.column_stack([pts @ e1, pts @ e2]))
        if err > CIRCLE_TOL_MM or r > 500: return None
        loc = c2[0] * e1 + c2[1] * e2
    d = pts - loc; d -= np.outer(d @ ax, ax)
    ref = d[0] / np.linalg.norm(d[0]); ang = np.degrees(np.arctan2(d @ np.cross(ax, ref), d @ ref))
    along = pts @ ax; ends = [np.cos(a) * ref + np.sin(a) * np.cross(ax, ref) for a in np.radians([ang.min(), ang.max()])]
    return r, ax, loc, float(np.ptp(ang)), (float(along.min()), float(along.max())), ends


def bends(shape, t):
    """Coaxial cylinder pairs (analytic or B-spline fitted) whose radii differ by the sheet thickness."""
    cyl = []
    for i, f in faces_of(shape):
        fit = cylinder_of(f)
        if fit is None: continue
        r, ax, loc, sweep, span, ends = fit
        cyl.append({'i': i, 'r': r, 'ax': ax, 'loc': loc, 'sweep': sweep, 'span': span, 'ends': ends})
    def coaxial(a, b):
        if abs(abs(a['ax'] @ b['ax']) - 1) > 1e-4: return False
        d = b['loc'] - a['loc']; return np.linalg.norm(d - (d @ a['ax']) * a['ax']) < 0.05
    out, used = [], set()
    for a in sorted(cyl, key=lambda c: c['r']):
        if a['i'] in used: continue
        outer = [b for b in cyl if b['i'] not in used and b is not a and abs(b['r'] - a['r'] - t) < 0.1 and coaxial(a, b)]
        if not outer: continue
        group = [c for c in cyl if c['i'] not in used and abs(c['r'] - a['r']) < 0.01 and coaxial(a, c)]
        used.update(c['i'] for c in group + outer)
        lo = min(c['span'][0] for c in group); hi = max(c['span'][1] for c in group)
        mid = a['loc'] + a['ax'] * ((lo + hi) / 2 - a['loc'] @ a['ax'])
        e0, e1 = max(group, key=lambda c: c['sweep'])['ends']; ax = max(group, key=lambda c: c['sweep'])['ax']
        # outer-surface tangent points and the leg directions leaving the bend there (model frame)
        legs = [(mid + (a['r'] + t) * e0, -np.cross(ax, e0)), (mid + (a['r'] + t) * e1, np.cross(ax, e1))]
        out.append({'inner_radius_mm': round(a['r'], 2), 'angle_deg': round(max(c['sweep'] for c in group), 1),
                    'length_mm': round(hi - lo, 2), 'axis_model': np.round(a['ax'], 4).tolist(),
                    'axis_point_model': np.round(mid, 3).tolist(), 'faces': sorted(c['i'] for c in group + outer), '_legs': legs})
    return out, used


def unrecognised_curved(shape, feats, bend_faces):
    known = {i for f in feats for i in f['faces']} | set(bend_faces)
    c = Counter()
    for i, f in faces_of(shape):
        if i in known: continue
        k = BRepAdaptor_Surface(f).GetType()
        if k in (GeomAbs_BSplineSurface, GeomAbs_Torus, GeomAbs_Sphere): c[str(k).split('.')[-1].replace('GeomAbs_', '')] += 1
    return dict(c)


# ---------- driver ----------

def axis_name(v, x, y, z):
    loc = np.array([v @ x, v @ y, v @ z])
    k = int(np.argmax(np.abs(loc)))
    return ('+' if loc[k] > 0 else '-') + 'XYZ'[k] if abs(loc[k]) > 0.9986 else 'oblique'


def measure_sheet(shape, feats, t, name):
    base_id, x, y, z = part_frame(feats)
    local = to_frame(shape, x, y, z)
    lb = bbox(local)
    R = np.vstack([x, y, z]); origin_local = np.array(lb['min'])
    frame_pt = lambda p: R @ np.asarray(p) - origin_local
    model_origin = R.T @ origin_local
    flanges = []
    for k, f in enumerate(sorted(feats, key=lambda f: -f['area_mm2']), 1):
        n = np.array(f['outer_normal'])
        flanges.append({'id': f'F{k}', 'span_mm': f['span_mm'], 'width_mm': f['width_mm'], 'thickness_mm': f['thickness_mm'],
                        'faces': axis_name(n, x, y, z), 'narrow': f['narrow'], 'area_mm2': f['area_mm2'],
                        'centre_part_mm': np.round(frame_pt(f['outer_point_mm']), 2).tolist(),
                        'box_part_mm': face_box(f['_outer'], x, y, z, origin_local), '_src': f})
    holes, slots, rects, cutouts = [], [], [], []
    for fl in flanges:
        for o in openings(fl['_src'], frame_pt):
            o['feature'] = fl['id']; o['axis'] = axis_name(np.array(o['axis_model']), x, y, z)
            if 'long_dir_model' in o: o['long_dir'] = axis_name(np.array(o['long_dir_model']), x, y, z)
            {'hole': holes, 'slot': slots, 'rectangle': rects, 'cutout': cutouts}[o['type']].append(o)
    for prefix, rows in (('H', holes), ('S', slots), ('R', rects), ('C', cutouts)):
        rows.sort(key=lambda r: (r['feature'], r['part_mm'][0], r['part_mm'][1], r['part_mm'][2]))
        for k, r in enumerate(rows, 1): r['id'] = f'{prefix}{k}'
    bend_rows, bend_faces = bends(shape, t)
    for k, b in enumerate(bend_rows, 1):
        b['id'] = f'B{k}'; b['axis'] = axis_name(np.array(b['axis_model']), x, y, z)
        b['axis_point_part_mm'] = np.round(frame_pt(b['axis_point_model']), 2).tolist()
        b['legs_part'] = [{'outer_point_mm': np.round(frame_pt(p), 3).tolist(), 'dir': np.round(R @ d, 6).tolist()} for p, d in b.pop('_legs')]
    unknowns = []
    curved = unrecognised_curved(shape, feats, bend_faces)
    if curved: unknowns.append({'what': 'curved faces not in a flange or cylindrical bend', 'counts': curved})
    if cutouts: unknowns.append({'what': f'{len(cutouts)} irregular cutout(s): size and centre only, profile not dimensioned'})
    narrow = [f['id'] for f in flanges if f['narrow']]
    if narrow: unknowns.append({'what': 'narrow flat features under 5 mm wide', 'ids': narrow})
    for f in flanges: del f['_src']
    return {'frame': {'base_flange': 'F1', 'x_model': x.round(6).tolist(), 'y_model': y.round(6).tolist(),
                      'z_model': z.round(6).tolist(), 'origin_model_mm': np.round(model_origin, 3).tolist(),
                      'note': 'Part frame: Z = inward normal of the largest flange (F1), X = its long axis, origin = min corner of the part box.'},
            'overall_mm': [round(s, 2) for s in lb['size']], 'thickness_mm': t,
            'flanges': flanges, 'bends': bend_rows, 'holes': holes, 'slots': slots, 'rectangles': rects, 'cutouts': cutouts, 'unknowns': unknowns}


def measure(step, density=STEEL_KG_M3):
    step = Path(step).resolve()
    leaves, units = read_occurrences(step)
    bodies = []
    for shape, meta in leaves:
        for k, s in enumerate(shapes_of(shape, TopAbs_SOLID), 1):
            bodies.append((meta['product_name'], TopoDS.Solid_s(s)))
    rows, groups = [], {}
    for name, s in bodies:
        v = props(s).Mass()
        if v <= 0: raise ValueError(f'Non-positive solid volume in {name}: inverted or open body')
        bb = bbox(s); nfaces = sum(1 for _ in faces_of(s))
        sig = signature(v, bb['size'], nfaces)
        if sig in groups: groups[sig]['qty'] += 1; groups[sig]['_shapes'].append(s); continue
        role, feats, t = classify(s, v)
        row = {'name': name, 'role': role, 'qty': 1, 'volume_mm3': round(v, 1), 'mass_each_kg': round(v * density * 1e-9, 4),
               'model_box_mm': [round(a, 2) for a in bb['size']], 'model_min_mm': [round(a, 3) for a in bb['min']],
               '_shapes': [s]}
        if role == 'sheet': row.update(measure_sheet(s, feats, t, name))
        groups[sig] = row; rows.append(row)
    rows.sort(key=lambda r: (r['role'] != 'sheet', -r['volume_mm3']))
    for k, r in enumerate(rows, 1):
        r['item'] = k; r['mass_total_kg'] = round(r['mass_each_kg'] * r['qty'], 4)
    unique = len({r['name'] for r in rows}) == len(rows)
    for r in rows:
        box = '×'.join(f'{a:.0f}' for a in (r['overall_mm'] if r['role'] == 'sheet' else sorted(r['model_box_mm'], reverse=True)))
        r['description'] = r['name'] if unique else (f"SHEET t{r['thickness_mm']:g} {box}" if r['role'] == 'sheet' else f"{r['role'].split()[0].upper()} {box}")
    all_box = bbox(leaves[0][0]) if len(leaves) == 1 else None
    total = sum(r['mass_total_kg'] for r in rows)
    return {'schema': 'draft-measure-1', 'source': {'path': str(step), 'sha256': file_sha256(step),
            'units_detected': units or ['unknown'], 'units': 'mm'},
            'density_kg_m3': density, 'total_mass_kg': round(total, 3),
            'mass_note': f'Sum of every solid at {density:g} kg/m3; overlapping solids (e.g. welds modelled into parents) count twice.',
            'model_box_mm': [round(a, 2) for a in all_box['size']] if all_box else None,
            'items': rows}


def public(result):
    return {**result, 'items': [{k: v for k, v in r.items() if not k.startswith('_')} for r in result['items']]}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('step'); ap.add_argument('--density', type=float, default=STEEL_KG_M3)
    ap.add_argument('-o', '--out')
    a = ap.parse_args()
    text = json.dumps(public(measure(a.step, a.density)), indent=1)
    Path(a.out).write_text(text) if a.out else print(text)
