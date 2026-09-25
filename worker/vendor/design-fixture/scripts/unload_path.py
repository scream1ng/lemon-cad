#!/usr/bin/env python3
"""Straight unload screen: lift the whole workpiece away from the master part's primary datum.

Clamps count as open (HW_* ignored) and sliding/removable pins as withdrawn; ribs, bodies, bushes and
fixed pins stay. Any sampled overlap is a fail naming the obstacle. A clear path stays unknown: a
straight lift of nominal CAD does not prove loading/unloading (construction-operation.md).
"""
from __future__ import annotations

import argparse

import numpy as np
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound

from export_step import read_step
from fixture_common import load_spec, write_json
from verify import PLATE_VOL, bbox, interferes, moved, volume

START_MM, STEP_MM, CLEAR_MM = 0.5, 2.0, 1.0


def compound(shapes):
    c = TopoDS_Compound(); b = BRep_Builder(); b.MakeCompound(c)
    for s in shapes: b.Add(c, s)
    return c


def direction(spec, parts):
    master = spec.get('assembly_locating', {}).get('master_part')
    if master not in spec.get('workpiece', {}).get('parts', {}):
        by_shape = {v: k for k, v in spec.get('workpiece', {}).get('parts', {}).items()}
        sized = [(volume(s), by_shape.get(n.split('/')[-1])) for n, s in parts.items()]
        master = max((v, p) for v, p in sized if p)[1] if any(p for _, p in sized) else None
    normals = [c['normal'] for c in spec.get('contacts', []) if c.get('part') == master
               and str(c.get('role', '')).lower() == 'primary' and c.get('constraint_role', 'fixed_datum') == 'fixed_datum']
    if not normals: return master, None
    d = np.mean(np.array(normals, float), axis=0); n = np.linalg.norm(d)
    return master, (d / n if n > 1e-9 else None)


def audit(spec, shapes):
    leaf = lambda n: n.split('/')[-1]
    parts = {n: s for n, s in shapes.items() if leaf(n).startswith('Part_')}
    withdrawn = {p['shape_name'] for p in spec.get('pin_locators', []) if p.get('mode') in ('sliding', 'removable')}
    obstacles = {n: s for n, s in shapes.items() if not leaf(n).startswith(('Part_', 'HW_', 'REF_source_'))
                 and leaf(n) not in withdrawn}
    master, d = direction(spec, parts) if parts else (None, None)
    base = {'master_part': master, 'direction': None if d is None else d.round(4).tolist(),
            'assumes': 'clamps open, sliding/removable pins withdrawn, whole workpiece moves as one',
            'scope': 'straight-lift samples only; a clear path stays unknown, never pass'}
    if d is None or not obstacles:
        return {**base, 'status': 'unknown', 'collisions': [],
                'next_action': 'Declare primary fixed_datum contacts on the master part so the unload direction is defined.'}
    work = compound(parts.values())
    lo, hi = np.array(bbox(work)[:3]), np.array(bbox(work)[3:])
    corners = lambda a, b: np.array([[x, y, z] for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])])
    fixture = np.vstack([corners(np.array(bbox(s)[:3]), np.array(bbox(s)[3:])) for s in obstacles.values()])
    travel = float((fixture @ d).max() - (corners(lo, hi) @ d).min()) + CLEAR_MM
    offsets = [START_MM] + list(np.arange(STEP_MM, travel + STEP_MM, STEP_MM))
    bounds = {n: bbox(s) for n, s in obstacles.items()}
    hits = {}
    for off in offsets:
        sh = moved(work, d * off); bb = bbox(sh)
        for n, s in obstacles.items():
            if n not in hits and interferes(sh, s, bb, bounds[n], PLATE_VOL):
                hits[n] = round(float(off), 2)
    collisions = [{'obstacle': n, 'first_offset_mm': o} for n, o in sorted(hits.items(), key=lambda x: x[1])]
    return {**base, 'status': 'fail' if collisions else 'unknown', 'collisions': collisions,
            'travel_mm': round(travel, 2), 'samples': len(offsets),
            'next_action': None if not collisions else
            'Workpiece cannot lift out: move, shorten or relieve ' + ', '.join(c['obstacle'] for c in collisions)
            + ', or make the pin sliding/removable in pin_locators.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('spec'); ap.add_argument('step'); ap.add_argument('out')
    a = ap.parse_args()
    r = audit(load_spec(a.spec), read_step(a.step))
    write_json(a.out, r)
    print(r['status'], ','.join(c['obstacle'] for c in r['collisions']) or '-')


if __name__ == '__main__':
    main()
