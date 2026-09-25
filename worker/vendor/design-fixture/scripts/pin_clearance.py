#!/usr/bin/env python3
"""Pin clearance screen: every pin_locators pin stays clear of all fixture plates but its own pad.

A pin is carried by a pad plate, either pressed through a hole in it (the pin spans the pad's full
thickness with a fit gap) or standing on its face. The pad's face must be square to the pin: a rib
standing on edge is not a pin seat, however much material sits under the base. A pad held above the
base plate stands on at least MIN_CARRIERS plates: one rib under a pad lets it rock.

Any overlap with another plate, or a gap under MIN_GAP_MM to any other plate (cap tabs through the
pad, cheeks, braces), is a fail: the pin cannot be ground, screwed or welded down. A sliding/removable pin may instead seat on its REF_BUSH_/REF_CARRIER_ solid; the plate that
solid is mounted on is then exempt from the gap.
"""
from __future__ import annotations

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

from unload_path import direction
from verify import PLATE_VOL, bbox, common_volume, gap, moved

MIN_GAP_MM, SINK_MM, FIT_MM = 5.0, 0.05, 0.5
MIN_CARRIERS = 2    # an elevated pad rocks on one rib; it stands on a cheek pair


def span(b, d):
    """Extent of a bbox along unit direction d (axis-aligned d only)."""
    lo = sum(min(b[i], b[i + 3]) * d[i] for i in range(3))
    return lo, lo + sum(abs(b[i + 3] - b[i]) * abs(d[i]) for i in range(3))


def face_square_to(b, d):
    """True when the plate's thin axis (its face normal) lies along d."""
    sizes = [b[i + 3] - b[i] for i in range(3)]
    return abs(d[sizes.index(min(sizes))]) > 0.999


def near(a, b, pad):
    return all(a[i] <= b[i + 3] + pad and b[i] <= a[i + 3] + pad for i in range(3))


def audit(spec, shapes):
    leaf = lambda n: n.split('/')[-1]
    plates = {n: s for n, s in shapes.items() if leaf(n) in {p['name'] for p in spec.get('plates', [])}}
    wanted = {p['shape_name']: p.get('id', p['shape_name']) for p in spec.get('pin_locators', []) if p.get('shape_name')}
    withdrawn = {p.get('id', p['shape_name']) for p in spec.get('pin_locators', []) if p.get('mode') in ('sliding', 'removable')}
    supports = {n: s for n, s in shapes.items() if leaf(n).startswith(('REF_BUSH_', 'REF_CARRIER_'))}
    pins = {wanted[leaf(n)]: s for n, s in shapes.items() if leaf(n) in wanted}
    parts = {n: s for n, s in shapes.items() if leaf(n).startswith('Part_')}
    _, d = direction(spec, parts) if parts else (None, None)
    d = np.array([0.0, 0.0, 1.0]) if d is None else d
    base = {'min_gap_mm': MIN_GAP_MM, 'direction': d.round(4).tolist(),
            'scope': 'nominal CAD; host pad = plate the pin is pressed through, else a square-faced plate under its base'}
    if not pins:
        return {**base, 'status': 'unknown', 'pins': [], 'violations': [],
                'next_action': 'List every pin in pin_locators with the shape_name of its REF_ solid.'}
    floor = min((span(bbox(s), d)[0] for s in plates.values()), default=0.0)
    rows, bad, weak = [], [], {}
    for pid, pin in pins.items():
        pb, sunk = bbox(pin), BRepAlgoAPI_Cut(moved(pin, -d * SINK_MM), pin).Shape()  # thin slab under the base
        seats = {**plates, **supports} if pid in withdrawn else plates
        close = {n: s for n, s in seats.items() if near(pb, bbox(s), MIN_GAP_MM)}
        seat = {n: common_volume(sunk, s) for n, s in close.items()}
        stood = max(seat, key=seat.get) if seat and max(seat.values()) > 0 else None
        # pressed through: no overlap, a fit gap, and the pin spanning the pad's whole thickness
        pressed, edge_seat = {}, None
        for name, plate in close.items():
            if name in supports or common_volume(pin, plate) > PLATE_VOL or gap(pin, plate) >= FIT_MM: continue
            plo, phi = span(pb, d); qlo, qhi = span(bbox(plate), d)
            if plo <= qlo + SINK_MM and phi >= qhi - SINK_MM: pressed[name] = round(qhi - qlo, 2)
        host = max(pressed, key=pressed.get) if pressed else None
        mode, bearing = ('pressed', pressed[host]) if host else (None, None)
        if host is None and stood is not None:
            if stood in supports or face_square_to(bbox(seats[stood]), d):
                host, mode = stood, 'bush' if stood in supports else 'seated'
            else:
                edge_seat = stood
        hosts, closest = [host] if host else [], None
        mount = {n for n, s in plates.items() if host in supports and gap(supports[host], s) < SINK_MM}
        for name, plate in close.items():
            if name == host or name in mount or name in supports: continue
            g = gap(pin, plate)
            v = common_volume(pin, plate) if g < MIN_GAP_MM else 0.0
            if v > PLATE_VOL or g < MIN_GAP_MM:
                bad.append({'pin': pid, 'plate': name, 'gap_mm': round(g, 2), 'overlap_mm3': round(v, 3)})
            if closest is None or g < closest[1]: closest = (name, round(g, 2))
        carriers = sorted(n for n, s in plates.items() if host and n != host and gap(seats[host], s) < SINK_MM)
        if host and mode != 'bush' and span(bbox(seats[host]), d)[0] > floor + SINK_MM and len(carriers) < MIN_CARRIERS:
            weak[pid] = (host, carriers)
        v = common_volume(pin, seats[host]) if host else 0.0
        if v > PLATE_VOL: bad.append({'pin': pid, 'plate': host, 'gap_mm': 0.0, 'overlap_mm3': round(v, 3)})
        rows.append({'pin': pid, 'host': hosts, 'mode': mode, 'bearing_mm': bearing, 'edge_seat': edge_seat,
                     'carriers': carriers, 'closest': closest,
                     'status': 'fail' if any(b['pin'] == pid for b in bad) or not hosts or pid in weak else 'pass'})
    orphan = [r['pin'] for r in rows if not r['host']]
    edges = {r['pin']: r['edge_seat'] for r in rows if r['edge_seat']}
    status = 'fail' if bad or orphan or weak else 'pass'
    action = None
    if status == 'fail':
        parts_ = [f"move pin or relieve/move {b['plate']} ({b['pin']} gap {b['gap_mm']} mm)" for b in bad]
        parts_ += [f'press {p} through a pad plate, or seat it on one: {edges[p]} carries it on a plate edge'
                   if p in edges else f'seat {p} on a pad plate below its base' for p in orphan]
        parts_ += [f"stand pad {h} on {MIN_CARRIERS} plates ({p} rests on {', '.join(c) or 'one rib only'})"
                   for p, (h, c) in weak.items()]
        action = f'Keep pins >= {MIN_GAP_MM:g} mm from tabs, cheeks and braces: ' + '; '.join(parts_) + '.'
    return {**base, 'status': status, 'pins': rows, 'violations': bad, 'unseated': orphan, 'unsupported': sorted(weak), 'next_action': action}
