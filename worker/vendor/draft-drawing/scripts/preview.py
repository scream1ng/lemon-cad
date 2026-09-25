#!/usr/bin/env python3
"""Single-file HTML review: 3D mesh with feature tags, measured tables, and the draft sheets, with comment pins."""
from __future__ import annotations

import base64
import gzip
import json

import numpy as np

from common import ROOT, compact_mesh, triangles
from sheet import placed, to_part

INLINE_HTML_TARGET, INLINE_HTML_LIMIT = 250_000, 1_000_000
MESH_TARGET = {'sheet': 6000}  # triangles per item; everything else gets 300


def fmt(v):
    return f'{v:g}' if abs(v - round(v, 1)) < 5e-3 else f'{v:.2f}'


def annotations(r, frame):
    """Drawing-style marks for one sheet item, placed in the scene frame; texts match the sheet tables."""
    F = r['frame']; R = np.vstack([F['x_model'], F['y_model'], F['z_model']]); o = np.array(F['origin_model_mm'])
    S = lambda part: np.round(to_part(frame, o + R.T @ np.asarray(part)), 2).tolist()   # item part frame -> scene
    D = lambda v: np.round(np.vstack([frame['x_model'], frame['y_model'], frame['z_model']]) @ v, 6).tolist()
    pos = lambda p: 'X {} · Y {} · Z {}'.format(*map(fmt, p))
    marks = []
    for h in r.get('holes', []): marks.append({'kind': 'hole', 'id': h['id'], 'text': f"{h['id']}  Ø{fmt(h['diameter_mm'])}", 'at': pos(h['part_mm']), 'p': S(h['part_mm'])})
    for h in r.get('slots', []): marks.append({'kind': 'hole', 'id': h['id'], 'text': f"{h['id']}  SLOT {fmt(h['width_mm'])}×{fmt(h['length_mm'])}", 'at': pos(h['part_mm']), 'p': S(h['part_mm'])})
    for h in r.get('rectangles', []): marks.append({'kind': 'hole', 'id': h['id'], 'text': f"{h['id']}  □{fmt(h['width_mm'])}×{fmt(h['length_mm'])}", 'at': pos(h['part_mm']), 'p': S(h['part_mm'])})
    for h in r.get('cutouts', []): marks.append({'kind': 'hole', 'id': h['id'], 'text': f"{h['id']}  CUTOUT ~{fmt(h['size_mm'][0])}×{fmt(h['size_mm'][1])}", 'at': pos(h['part_mm']), 'p': S(h['part_mm'])})
    for f in r['flanges']:
        if not f['narrow']: marks.append({'kind': 'flange', 'id': f['id'], 'text': f"{f['id']}  {fmt(f['span_mm'])}×{fmt(f['width_mm'])}", 'at': 'face ' + f['faces'], 'p': S(f['centre_part_mm'])})
    for b in r['bends']:
        marks.append({'kind': 'bend', 'id': b['id'], 'text': f"{b['id']}  R{fmt(b['inner_radius_mm'])} {b['angle_deg']:g}°", 'at': f"length {fmt(b['length_mm'])} · axis {b['axis']}", 'p': S(b['axis_point_part_mm'])})
    return {'origin': S([0, 0, 0]), 'axes': [D(R[i]) for i in range(3)], 'size': r['overall_mm'], 'marks': marks}


def scene(result, svgs, settings):
    """Everything in item 1's part frame, so 3D coordinates read like the hole tables of item 1."""
    main = next((r for r in result['items'] if r['role'] == 'sheet'), result['items'][0])
    frame = main.get('frame') or {'x_model': [1, 0, 0], 'y_model': [0, 1, 0], 'z_model': [0, 0, 1], 'origin_model_mm': main['model_min_mm']}
    meshes, ann = [], {}
    for r in result['items']:
        m = compact_mesh(triangles(placed(r['_shapes'], frame)), MESH_TARGET.get(r['role'], 300))
        meshes.append({'item': r['item'], 'role': r['role'], 'positions': m['positions'], 'indices': m['indices']})
        if r['role'] == 'sheet': ann[r['item']] = annotations(r, frame)
    items = [{k: v for k, v in r.items() if not k.startswith('_')} for r in result['items']]
    return {'title': settings['title'], 'source': result['source'],
            'density_kg_m3': result['density_kg_m3'], 'total_mass_kg': result['total_mass_kg'], 'mass_note': result['mass_note'],
            'items': items, 'meshes': meshes, 'annotations': ann, 'sheets': svgs}


def inline_html(data):
    """Build the deterministic single-file viewer and enforce the inline size limit."""
    payload = json.dumps(data, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c').encode()
    encoded = base64.b64encode(gzip.compress(payload, compresslevel=9, mtime=0)).decode('ascii')
    html = (ROOT / 'assets/preview.html').read_text().replace('__SCENE_GZIP_BASE64__', encoded)
    if '__SCENE_GZIP_BASE64__' in html: raise ValueError('Preview scene placeholder was not replaced')
    size = len(html.encode())
    if size >= INLINE_HTML_LIMIT: raise ValueError(f'Inline preview is {size} bytes; must be below {INLINE_HTML_LIMIT}')
    return html, size
