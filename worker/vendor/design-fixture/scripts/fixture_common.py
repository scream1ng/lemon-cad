"""Shared plate-record helpers for the laser-cut fixture scripts.

Plate record (plate-local mm): name, part_number, role, origin, u, v, w, outer, holes,
contacts, optional seat (name of the plate whose slots receive this plate's tabs).
World point = origin + u*x + v*y; the solid spans w*[-T/2, T/2].
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely import affinity, set_precision
from shapely.geometry import Polygon


def validate_rigid(value=None):
    """4x4 column-vector transform; translations are millimetres, no scaling/mirror. Pure numpy."""
    if isinstance(value, dict):
        value = value["source_to_fixture"]
    matrix = np.eye(4) if value is None else np.asarray(value, dtype=float)
    if (matrix.shape != (4, 4) or not np.isfinite(matrix).all()
            or not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-9, rtol=0)
            or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-9, rtol=0)
            or not np.isclose(np.linalg.det(matrix[:3, :3]), 1, atol=1e-9, rtol=0)):
        raise ValueError("source_to_fixture must be a finite proper rigid 4x4 transform")
    return matrix


def load_spec(path):
    path = Path(path).resolve()
    spec = json.loads(path.read_text())
    spec["_dir"] = str(path.parent)
    return validate_spec(spec)


def spec_path(spec, value):
    p = Path(value).expanduser()
    return p if p.is_absolute() else Path(spec["_dir"]) / p


def poly(d):
    return Polygon(d["outer"], d["holes"])


def ring_lists(p):
    return list(map(list, list(p.exterior.coords)[:-1])), [list(map(list, list(h.coords)[:-1])) for h in p.interiors]


def set_profile(d, p):
    d["outer"], d["holes"] = ring_lists(p)
    d["area_mm2"] = p.area


def clean(p):
    p = set_precision(p, 1e-6)
    assert p.geom_type == "Polygon" and p.is_valid, "profile is not one valid polygon"
    return p


def world_xy(d, q):
    """Plate-local (x along u, y along w) footprint -> world XY. Valid for plates with v = +Z."""
    assert abs(abs(d["v"][2]) - 1) < 1e-6, f"{d['name']}: seated plates must be vertical"
    u, w, o = d["u"], d["w"], d["origin"]
    return affinity.affine_transform(q, [u[0], w[0], u[1], w[1], o[0], o[1]])


def local_s(d, xy):
    return float((np.array(xy) - np.array(d["origin"])[:2]) @ np.array(d["u"])[:2])


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False))


def validate_spec(spec):
    """Reject invalid frames/identities before manufacturing geometry is changed."""
    if spec.get('units') != 'mm':
        raise ValueError('spec units must be mm; convert and survey the source explicitly')
    if not isinstance(spec.get('project_id'), str) or not spec['project_id']:
        raise ValueError('project_id must be a nonempty string')
    if any(c in spec['project_id'] for c in '/\\'):
        raise ValueError('project_id must not contain path separators')
    if not isinstance(spec.get('revision'), str) or not spec['revision']:
        raise ValueError('revision must be a nonempty string')
    if not np.isfinite(spec['thickness_mm']) or spec['thickness_mm'] <= 0:
        raise ValueError('thickness_mm must be positive')
    names = [d['name'] for d in spec['plates']]
    if not names or len(set(names)) != len(names):
        raise ValueError('plates must have unique names')
    for d in spec['plates']:
        frame = np.array([d[k] for k in ('u', 'v', 'w')], float).T
        if frame.shape != (3, 3) or not np.isfinite(frame).all() or not np.allclose(frame.T @ frame, np.eye(3), atol=1e-7) or not np.isclose(np.linalg.det(frame), 1, atol=1e-7):
            raise ValueError(f"{d['name']}: frame must be orthonormal and right-handed")
        if len(d['origin']) != 3 or not np.isfinite(d['origin']).all():
            raise ValueError(f"{d['name']}: invalid origin")
        if not poly(d).is_valid or poly(d).area <= 0:
            raise ValueError(f"{d['name']}: invalid plate profile")
        d.setdefault('contacts', [])
        if d.get('seat') and (d['seat'] not in names or not np.allclose(d['v'], [0, 0, 1])):
            raise ValueError(f"{d['name']}: supported seated ribs require v=+Z and a known seat")
    contacts = spec.setdefault('contacts', [])
    cn = [c['name'] for c in contacts]
    if len(set(cn)) != len(cn):
        raise ValueError('contact names must be unique')
    for c in contacts:
        if len(c['normal']) != 3 or not np.isclose(np.linalg.norm(c['normal']), 1, atol=1e-6):
            raise ValueError(f"{c['name']}: normal must be a unit vector")
        if c.get('rib') and c['rib'] not in names:
            raise ValueError(f"{c['name']}: unknown locator")
        if c.get('rib') and abs(np.dot(c['normal'], spec['plates'][names.index(c['rib'])]['w'])) > 1e-6:
            raise ValueError(f"{c['name']}: cut-edge contact normal must lie in the rib plane")
    for keys in spec.get('locating_groups', {}).values():
        if any(k not in cn for k in keys):
            raise ValueError('locating group references an unknown contact')
    tags = [c['tag'] for c in spec.get('clamps', [])]
    if len(set(tags)) != len(tags):
        raise ValueError('clamp tags must be unique')
    tf = spec.get('workpiece', {}).get('source_to_fixture')
    if tf is not None:
        a = np.asarray(tf, float)
        if a.shape != (4, 4) or not np.isfinite(a).all() or not np.allclose(a[3], [0,0,0,1]) or not np.allclose(a[:3,:3].T @ a[:3,:3], np.eye(3)) or not np.isclose(np.linalg.det(a[:3,:3]), 1):
            raise ValueError('source_to_fixture must be a rigid right-handed 4x4 transform')
    return spec
