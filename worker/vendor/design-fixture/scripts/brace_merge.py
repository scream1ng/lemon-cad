#!/usr/bin/env python3
"""Laser ribs: parallel braces closer than 50 mm are one common brace.

Candidates are seated plates that are pure braces: no datum contacts, not a cap cheek (a_slot 'tab'
joint into a cap), not a generated checking rib, not an inspection fixture_shape. Two candidates fail
when their planes are parallel, the planes are < MERGE_MM apart and their spans along the plate
(u) are < MERGE_MM apart (overlap counts as 0 or less). The fix is one brace on one plane over the
union span with the crossing slots re-cut; geometry is never edited here. A plate may carry
brace_merge_exception {with, reason} (reason quotes the user): that pair is unknown, not pass.
"""
from __future__ import annotations

import itertools

import numpy as np

MERGE_MM = 50.0


def candidates(spec):
    cheeks = {j['a'] for j in spec.get('joints', []) if j.get('a_slot') == 'tab'}
    ribs = {r['plate']['name'] for r in spec.get('checking_rib_definitions', spec.get('checking_ribs', []))}
    lands = {c.get('fixture_shape') for fl in (spec.get('inspection') or {}).get('flanges', []) for c in fl.get('checks', [])}
    return [d for d in spec['plates'] if d.get('seat') and not d.get('contacts')
            and d['name'] not in cheeks | ribs | lands]


def span(d, axis):
    o, u = np.array(d['origin'], float), np.array(d['u'], float)
    s = [float((o + u * x) @ axis) for x, _ in d['outer']]
    return min(s), max(s)


def audit(spec, limit=MERGE_MM):
    rows = []
    for a, b in itertools.combinations(candidates(spec), 2):
        wa, wb = np.array(a['w'], float), np.array(b['w'], float)
        if abs(wa @ wb) <= 0.999: continue
        offset = abs(float((np.array(b['origin'], float) - np.array(a['origin'], float)) @ wa))
        axis = np.array(a['u'], float)
        (a0, a1), (b0, b1) = span(a, axis), span(b, axis)
        gap = max(a0, b0) - min(a1, b1)
        if offset >= limit or gap >= limit: continue
        exc = [d.get('brace_merge_exception') for d in (a, b)]
        exc = next((e for e, other in zip(exc, (b, a)) if e and e.get('with') == other['name'] and str(e.get('reason', '')).strip()), None)
        rows.append({'a': a['name'], 'b': b['name'], 'plane_offset_mm': round(offset, 2), 'span_gap_mm': round(gap, 2),
                     'union_span_mm': [round(min(a0, b0), 2), round(max(a1, b1), 2)],
                     'status': 'unknown' if exc else 'fail', **({'exception': exc} if exc else {})})
    bad = [r for r in rows if r['status'] == 'fail']
    status = 'fail' if bad else 'unknown' if rows else 'pass'
    action = None
    if bad:
        action = (f'Commonise braces within {limit:g} mm: one brace on one plane over the union span, crossing slots re-cut: '
                  + '; '.join(f"{r['a']}+{r['b']} ({r['plane_offset_mm']} mm apart, span {r['union_span_mm']})" for r in bad) + '.')
    return {'status': status, 'limit_mm': limit, 'pairs': rows, 'next_action': action,
            'scope': 'seated brace plates only; cheeks, datum ribs and checking lands are exempt'}
