#!/usr/bin/env python3
"""Checking fixtures: every sheet feature (flange, tab, wall, web) of every checked part has a disposition.

Dispositions, matched by a point lying on one of the feature's faces (<= 0.1 mm):
  station     inspection.flanges[].checks[].point_mm (any non-alternative check)
  datum       spec.contacts[].contact (the feature is a datum land)
  alternative inspection.flanges[] entry with feature_point_mm and alternative checks
  waived      inspection.flange_waivers [{point_mm, reason}] - reason quotes the user
A feature with none, or a station point not on the checked part, is a fail (blocks the concept). A narrow feature
(under 5 mm wide) with none is unknown, never pass. No checked part, or no sheet feature found, is unknown.
Each uncovered feature carries a rib proposal from flange_features.propose.
"""
from __future__ import annotations

import argparse
import json

from flange_features import _dist, _vertex, extract, on_feature, propose, public


def points(spec):
    insp = spec.get('inspection') or {}
    rows = []
    for fl in insp.get('flanges', []):
        for c in fl.get('checks', []):
            if c.get('kind') != 'alternative' and c.get('point_mm'):
                rows.append(('station', c['id'], c['point_mm']))
        if fl.get('feature_point_mm') and any(c.get('kind') == 'alternative' for c in fl.get('checks', [])):
            rows.append(('alternative', fl['id'], fl['feature_point_mm']))
    for c in spec.get('contacts', []):
        rows.append(('datum', c['name'], c['contact']))
    for i, w in enumerate(insp.get('flange_waivers', []), 1):
        if not str(w.get('reason', '')).strip():
            raise ValueError('flange_waivers need the user\'s reason')
        rows.append(('waived', w.get('id', f'W{i}'), w['point_mm']))
    return rows


def checked_parts(spec, shapes):
    leaf = {k.split('/')[-1]: v for k, v in shapes.items()}
    parts = list((spec.get('workpiece') or {}).get('parts', {}).values()) or [k for k in leaf if k.startswith('Part_')]
    return {n: leaf[n] for n in parts if n in leaf}


def audit(spec, shapes, feats=None):
    """feats: extract() rows already made for checked_parts, so a caller needing the faces extracts once."""
    if not spec.get('inspection'):
        return {'status': 'not_applicable', 'reason': 'no inspection plan (weld fixture)', 'features': []}
    solids = checked_parts(spec, shapes)
    if feats is None: feats = [f for name, s in solids.items() for f in extract(s, name)]
    if not feats:
        return {'status': 'unknown', 'features': [], 'reason': 'no sheet feature found (not a sheet part?)',
                'next_action': 'List checked features by hand in inspection.flanges.'}
    marks = points(spec)
    rows, bad, narrow = [], [], []
    for f in feats:
        by = [{'kind': k, 'id': i} for k, i, p in marks if on_feature(f, p)]
        row = {**public(f), 'covered_by': by, 'status': 'pass' if by else 'unknown' if f['narrow'] else 'fail'}
        if not by:
            row['proposal'] = propose(f); (narrow if f['narrow'] else bad).append(f['id'])
        rows.append(row)
    off = [{'station': i, 'point_mm': p, 'distance_mm': round(min(_dist(s, _vertex(p)) for s in solids.values()), 3)}
           for k, i, p in marks if k == 'station']
    off = [o for o in off if o['distance_mm'] > 0.1]
    action = []
    if bad:
        where = '; '.join(f"{r['id']} at {r['outer_point_mm']} n {r['outer_normal']}" for r in rows if r['status'] == 'fail')
        action.append('Give each sheet feature a checking station (see proposal), an alternative with feature_point_mm, '
                      'or a user-quoted inspection.flange_waivers entry: ' + where)
    if narrow:
        action.append('Narrow features (under 5 mm wide) have no check; add one or a user-quoted waiver: ' + ', '.join(narrow) + '.')
    if off:
        action.append('Move stations onto the part (cutout or edge under them): ' +
                      ', '.join(f"{o['station']} {o['distance_mm']} mm off" for o in off))
    return {'status': 'fail' if bad or off else 'unknown' if narrow else 'pass', 'features': rows, 'uncovered': bad,
            'unchecked_narrow': narrow, 'stations_off_part': off,
            'next_action': ' '.join(action) or None,
            'scope': 'feature inventory from paired planar faces at sheet thickness; curved and bend faces are not features'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('spec')
    a = ap.parse_args()
    from export_step import read_step
    from fixture_common import load_spec, spec_path
    spec = load_spec(a.spec)
    r = audit(spec, read_step(spec_path(spec, spec['workpiece']['placed_step'])))
    print(json.dumps(r, indent=1))


if __name__ == '__main__':
    main()
