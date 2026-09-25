#!/usr/bin/env python3
"""Draw A3 draft sheets from measure() output: hidden-line views, overall dimensions, ID bubbles, tables, title block.

Views are exact OCP hidden-line projections of the part in its part frame. Numbers on the sheet are the
measured values from measure.py, never read back off the projection. The same figures render the preview SVG
and the final PDF, so the PDF matches what was reviewed.
"""
from __future__ import annotations

import io
import math
import re
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Arc, Circle, Polygon, Rectangle
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GeomAbs import GeomAbs_Line
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRep import BRep_Builder
from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

from PIL import Image, ImageDraw

from common import bbox, shapes_of, triangles

matplotlib.rcParams.update({'pdf.fonttype': 42, 'svg.fonttype': 'none', 'font.family': 'DejaVu Sans'})
A3 = (420.0, 297.0)
MARGIN, TABLE_W, GAP = 10.0, 128.0, 24.0
SCALES = [(5, 1), (2, 1), (1, 1), (1, 2), (1, 5), (1, 10), (1, 20)]
LW_THICK, LW_THIN = 0.35 * 72 / 25.4, 0.18 * 72 / 25.4
INK, BLUE, RED = '#111', '#1f5f99', '#b3261e'
# (direction toward the viewer, screen-right) in the part frame; third-angle placement
VIEWS = {'top': ((0, 0, 1), (1, 0, 0)), 'front': ((0, -1, 0), (1, 0, 0)), 'right': ((1, 0, 0), (0, 1, 0)),
         'iso': ((1, -1, 1), (1, 1, 0))}
AXIS_VIEW = {'Z': 'top', 'Y': 'front', 'X': 'right'}


# ---------- geometry ----------

def placed(shapes, frame):
    """Compound of shapes moved into the part frame (origin at the part-box min corner)."""
    x, z, o = (np.array(frame[k]) for k in ('x_model', 'z_model', 'origin_model_mm'))
    t = gp_Trsf(); t.SetTransformation(gp_Ax3(gp_Pnt(*o), gp_Dir(*z), gp_Dir(*x)))
    comp = TopoDS_Compound(); b = BRep_Builder(); b.MakeCompound(comp)
    for s in shapes: b.Add(comp, BRepBuilderAPI_Transform(s, t, True).Shape())
    return comp


def to_part(frame, p):
    R = np.vstack([frame['x_model'], frame['y_model'], frame['z_model']])
    return R @ (np.asarray(p) - np.array(frame['origin_model_mm']))


def basis(view):
    n, x = (np.array(v, float) for v in VIEWS[view])
    n /= np.linalg.norm(n); x /= np.linalg.norm(x)
    return n, x, np.cross(n, x)


def project(view, p):
    _, x, y = basis(view)
    return np.array([np.asarray(p) @ x, np.asarray(p) @ y])


def polylines(compound):
    out = []
    if compound is None or compound.IsNull(): return out
    for e in shapes_of(compound, TopAbs_EDGE):
        c = BRepAdaptor_Curve(TopoDS.Edge_s(e))
        if c.GetType() == GeomAbs_Line:
            pts = [c.Value(c.FirstParameter()), c.Value(c.LastParameter())]
        else:
            d = GCPnts_QuasiUniformDeflection(c, 0.02)
            pts = [d.Value(i) for i in range(1, d.NbPoints() + 1)] if d.IsDone() else []
        if len(pts) >= 2: out.append(np.array([[p.X(), p.Y()] for p in pts]))
    return out


_HLR = {}


def hlr(shape, view):
    key = (id(shape), view)
    if key not in _HLR: _HLR[key] = (shape, _hlr(shape, view))  # keep shape alive so its id stays unique
    return _HLR[key][1]


def _hlr(shape, view):
    n, x, _ = basis(view)
    algo = HLRBRep_Algo(); algo.Add(shape)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*n), gp_Dir(*x))))
    algo.Update(); algo.Hide()
    h = HLRBRep_HLRToShape(algo)
    return {'visible': polylines(h.VCompound()) + polylines(h.OutLineVCompound()),
            'tangent': polylines(h.Rg1LineVCompound()),
            'hidden': polylines(h.HCompound()) + polylines(h.OutLineHCompound())}


# ---------- drawing primitives (paper mm) ----------

def new_page():
    fig = plt.figure(figsize=(A3[0] / 25.4, A3[1] / 25.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, A3[0]); ax.set_ylim(0, A3[1]); ax.set_aspect('equal'); ax.axis('off')
    ax.add_patch(Rectangle((MARGIN, MARGIN), A3[0] - 2 * MARGIN, A3[1] - 2 * MARGIN, fill=False, lw=LW_THICK * 1.4, color=INK))
    return fig, ax


def text(ax, x, y, s, size=2.5, ha='left', va='baseline', color=INK, weight='normal', rot=0):
    ax.text(x, y, s, fontsize=size * 72 / 25.4 / 0.7, ha=ha, va=va, color=color, fontweight=weight, rotation=rot)


def lines(ax, polys, origin, scale, lw, color=INK, style='-'):
    for p in polys:
        q = origin + p * scale
        ax.plot(q[:, 0], q[:, 1], lw=lw, color=color, ls=style, solid_capstyle='round')


def arrow(ax, tip, back):
    d = np.asarray(back, float) - tip; d /= np.linalg.norm(d); nrm = np.array([-d[1], d[0]])
    ax.add_patch(Polygon([tip, tip + d * 2.5 + nrm * 0.6, tip + d * 2.5 - nrm * 0.6], closed=True, color=INK, lw=0))


def dim(ax, a, b, offset, label, horizontal, beyond=0):
    """Linear dimension between paper points a and b, its line `offset` mm beyond them (sign = side).
    A label too long for its gap goes past the end on the `beyond` side (+1 high end, -1 low end), or, when 0, half a tier outward."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    k = 1 if horizontal else 0  # coordinate across the dimension line
    base = (max if offset > 0 else min)(a[k], b[k]) + offset
    ends = []
    for p in (a, b):
        q = p.copy(); q[k] = base; ends.append(q)
        s0, s1 = p.copy(), q.copy(); s0[k] += math.copysign(1, offset); s1[k] += math.copysign(1.5, offset)
        ax.plot([s0[0], s1[0]], [s0[1], s1[1]], lw=LW_THIN, color=INK)
    p, q = ends
    n = np.linalg.norm(q - p); u = (q - p) / (n or 1); tw = 2.0 * len(label) + 5  # text plus both arrowheads
    if n < 6:  # too short for arrows inside: arrows point in from outside
        ax.plot([p[0] - 4 * u[0], q[0] + 4 * u[0]], [p[1] - 4 * u[1], q[1] + 4 * u[1]], lw=LW_THIN, color=INK)
        arrow(ax, p, p - u); arrow(ax, q, q + u)
    else:
        ax.plot([p[0], q[0]], [p[1], q[1]], lw=LW_THIN, color=INK)
        arrow(ax, p, q); arrow(ax, q, p)
    m = (p + q) / 2
    if n < tw and beyond: m = m + np.sign(beyond) * np.abs(u) * (n / 2 + tw / 2 + 1)
    if horizontal: text(ax, m[0], m[1] + 0.8, label, 2.5, ha='center', va='bottom')  # label always on top of its line
    else: text(ax, m[0] - 0.8, m[1], label, 2.5, ha='right', va='center', rot=90)


def bubble(ax, at, where, label, color=BLUE):
    ax.plot([at[0], where[0]], [at[1], where[1]], lw=LW_THIN, color=color)
    ax.add_patch(Circle(at, 0.5, color=color, lw=0))
    r = 1.6 + 0.55 * max(0, len(label) - 2)
    ax.add_patch(Circle(where, r, fill=True, facecolor='white', edgecolor=color, lw=LW_THIN * 1.3, zorder=5))
    ax.text(where[0], where[1], label, fontsize=2.1 * 72 / 25.4 / 0.7, ha='center', va='center', color=color, zorder=6)


def fmt(v):
    return f'{v:.1f}' if abs(v - round(v, 1)) < 5e-3 else f'{v:.2f}'


# ---------- layout ----------

TITLE_H = 44.0
TABLE_X = A3[0] - MARGIN - TABLE_W
TIER = 7.0  # paper mm between stacked dimension lines
EXT = {'top': (0, 1), 'front': (0, 2), 'right': (1, 2)}  # size indices across and up each view


def pad(tiers, view, side):
    return 6 + TIER * len(tiers[view][side])


def layout(size, tiers, forced=None):
    """Largest standard scale whose front/top/right views and their dimension tiers fit above the title block."""
    L, W, H = size
    P = lambda v, s: pad(tiers, v, s)
    x0 = MARGIN + max(P('top', 'L'), P('front', 'L')) + 2
    y0 = MARGIN + TITLE_H + max(P('front', 'B'), P('right', 'B')) + 6
    for s in ([forced] if forced else SCALES):
        k = s[0] / s[1]
        top_y = y0 + k * H + P('front', 'T') + P('top', 'B') + 6
        right_x = x0 + k * L + P('front', 'R') + P('right', 'L') + 4
        if (top_y + k * W + P('top', 'T') + 6 <= A3[1] - MARGIN and right_x + k * W + P('right', 'R') <= A3[0] - MARGIN
                and x0 + k * L + P('top', 'R') <= A3[0] - MARGIN) or forced:
            origin = {'front': np.array([x0, y0]), 'top': np.array([x0, top_y]), 'right': np.array([right_x, y0])}
            boxes = [(x0, y0, k * L, k * H), (x0, top_y, k * L, k * W), (right_x, y0, k * W, k * H)]
            return s, k, origin, boxes
    raise AssertionError('unreachable')


def table_floor(boxes):
    """Lowest y the right-hand table column may use without covering a view or the title block."""
    floor = MARGIN + TITLE_H + 4
    for x, y, w, h in boxes:
        if x + w + 12 > TABLE_X: floor = max(floor, y + h + 14)
    return floor


def clip(polys, lo, hi):
    """Drop HLR debris outside the view's known extent."""
    return [p for p in polys if (p >= lo - 1).all() and (p <= hi + 1).all()]


def draw_views(ax, shape, size, origin, k, show_hidden, tiers):
    L, W, H = size
    ext = {'front': (L, H), 'top': (L, W), 'right': (W, H)}; outline = {}
    for view, o in origin.items():
        h = hlr(shape, view); hi = np.array(ext[view]); vis = clip(h['visible'], 0, hi)
        outline[view] = np.vstack(vis) if vis else np.zeros((0, 2))
        lines(ax, vis, o, k, LW_THICK)
        lines(ax, clip(h['tangent'], 0, hi), o, k, LW_THIN, '#666')
        if show_hidden: lines(ax, clip(h['hidden'], 0, hi), o, k, LW_THIN, '#555', (0, (3, 2)))
        text(ax, o[0], o[1] - pad(tiers, view, 'B') - 3, view.upper() + ' VIEW', 2.2, color='#444')
    return outline


def draw_iso(ax, shape, size, boxes_free, k):
    """Isometric in the largest free box (x, y, w, h); skipped when none is at least 45 mm square. Returns the paper it uses."""
    box = max(boxes_free, key=lambda b: min(b[2], b[3]), default=None)
    if box is None or min(box[2], box[3]) < 45: return None
    corners = np.array([project('iso', np.array(size) * c) for c in np.ndindex(2, 2, 2)])
    lo, hi = corners.min(0), corners.max(0)
    vis = clip(hlr(shape, 'iso')['visible'], lo, hi)
    ki = min((box[2] - 8) / (hi - lo)[0], (box[3] - 12) / (hi - lo)[1], k)
    o = np.array([box[0] + 4, box[1] + 8]) - lo * ki
    lines(ax, vis, o, ki, LW_THIN * 1.4)
    lines(ax, clip(hlr(shape, 'iso')['tangent'], lo, hi), o, ki, LW_THIN, '#666')  # bend lines
    text(ax, box[0] + 4, box[1] + 2, 'ISOMETRIC (not to scale)', 2.2, color='#444')
    return (box[0], box[1], 8 + (hi - lo)[0] * ki, 12 + (hi - lo)[1] * ki)


def new_tiers():
    return {v: {s: [] for s in 'TBLR'} for v in EXT}


def add_overall(tiers, size):
    """Overall dims go on last, so they sit outermost."""
    L, W, H = size
    tiers['top']['T'].append([((0, W), (L, W))]); tiers['top']['L'].append([((0, 0), (0, W))])
    tiers['front']['L'].append([((0, 0), (0, H))]); tiers['right']['B'].append([((0, 0), (W, 0))])
    for sides in tiers.values():  # a lone dim repeating another's span on the same axis is dropped; the outer one stays
        for pair, a in (('TB', 0), ('LR', 1)):
            seen = set()
            for s in pair:
                for r in reversed(list(sides[s])):
                    if len(r) != 1: continue
                    span = tuple(sorted(round(c[a], 1) for c in r[0]))
                    if span in seen: sides[s].remove(r)
                    seen.add(span)
    return tiers


def opening_label(kind, h):
    if kind == 'holes': return f"Ø{fmt(h['diameter_mm'])}", h['diameter_mm'] / 2
    if kind == 'slots': return f"SLOT {fmt(h['width_mm'])}×{fmt(h['length_mm'])}", h['width_mm'] / 2
    return f"□{fmt(h['width_mm'])}×{fmt(h['length_mm'])}", min(h['width_mm'], h['length_mm']) / 2


def nearest_edge(polys, p, a, sign, reach):
    """Distance from p along axis a (direction sign) to the first outline line beyond `reach` (the opening itself)."""
    b, best = 1 - a, None
    for q in polys:
        for s0, s1 in zip(q[:-1], q[1:]):
            if s0[b] == s1[b] or (s0[b] - p[b]) * (s1[b] - p[b]) > 0: continue
            d = (s0[a] + (p[b] - s0[b]) / (s1[b] - s0[b]) * (s1[a] - s0[a]) - p[a]) * sign
            if d > reach and (best is None or d < best): best = d
    return best


def to_sharp(f, bends):
    """Flange box stretched to the outside of the material at its bend (the virtual sharp), as a tab is measured."""
    box = np.array(f['box_part_mm'], float); i = 'XYZ'.index(f['faces'][-1])
    for b in bends:
        legs = b.get('legs_part', [])
        if len(legs) != 2: continue
        (p1, d1), (p2, d2) = ((np.array(l['outer_point_mm']), np.array(l['dir'])) for l in legs)
        if not any(abs(p[i] - box[0][i]) < f['thickness_mm'] + 0.1 and np.all(p > box[0] - 1) and np.all(p < box[1] + 1) for p in (p1, p2)): continue
        t = np.linalg.lstsq(np.column_stack([d1, -d2]), p2 - p1, rcond=None)[0][0]; c = p1 + t * d1; c[i] = box[0][i]
        box = np.array([np.minimum(box[0], c), np.maximum(box[1], c)])
    return box


def plan(item, size, shape):
    """Dimension tiers and size callouts per view, in view mm. Openings chain hole-to-hole within one flange,
    tied to the nearest real edge of the outline; flange widths on the face-on view; flange heights on the front view."""
    ext = {v: (size[a], size[b]) for v, (a, b) in EXT.items()}
    tiers, calls, groups = new_tiers(), {v: {} for v in EXT}, {}
    for kind in ('holes', 'slots', 'rectangles'):
        for h in item.get(kind, []):
            view = AXIS_VIEW.get(h['axis'][-1]) if h['axis'] != 'oblique' else None
            if not view: continue
            uv = project(view, h['part_mm']); label, r = opening_label(kind, h)
            reach = max(h.get('diameter_mm', 0), h.get('width_mm', 0), h.get('length_mm', 0)) / 2 + 0.05
            half = np.zeros(2)
            if kind == 'rectangles':  # half size along each view axis; the long side follows long_dir
                half = np.array([(h['length_mm'] if i == 'XYZ'.index(h['long_dir'][-1]) else h['width_mm']) / 2 for i in EXT[view]])
            groups.setdefault((view, h['feature']), []).append((uv, reach, half)); calls[view].setdefault(label, []).append((uv, r))
    outline = {v: clip(hlr(shape, v)['visible'], 0, np.array(e)) for v, e in ext.items()}
    for (view, _), group in sorted(groups.items(), key=lambda g: g[0]):
        e, pts = ext[view], [uv for uv, _, _ in group]
        for a in (0, 1):
            stops = {}
            for p, r, hf in sorted(group, key=lambda g: (g[0][a], not g[2].any())): stops.setdefault(round(p[a], 2), (p, r, hf))  # a rectangle wins a tie
            (lo, rlo, _), (hi, rhi, _) = stops[min(stops)], stops[max(stops)]
            # tie the chain to the nearest real edge of the part outline, on whichever side is closer
            dl, dh = nearest_edge(outline[view], lo, a, -1, rlo), nearest_edge(outline[view], hi, a, 1, rhi)
            up = dl is None or (dh is not None and dh < dl); sign = 0 if dl is None and dh is None else 1 if up else -1
            feats, stops = stops.values(), {}
            for p, _, hf in feats:  # rectangles are measured to the edge facing the reference, as a caliper would
                q = p.copy(); q[a] += sign * hf[a]; stops[round(q[a], 2)] = q
            if sign:
                ref = (hi if up else lo).copy(); ref[a] += dh if up else -dl
                stops[round(ref[a], 2)] = ref
            across = np.mean([p[1 - a] for p in pts]) > e[1 - a] / 2
            side = ('T' if across else 'B') if a == 0 else ('R' if across else 'L')
            seq = [stops[c] for c in sorted(stops)]
            segs = [(tuple(p), tuple(q)) for p, q in zip(seq, seq[1:]) if q[a] - p[a] > 0.05]
            if segs: tiers[view][side].append(segs)
    for f in item['flanges']:
        if f['narrow'] or f['faces'] == 'oblique' or f['id'] == item['frame']['base_flange']: continue
        view = AXIS_VIEW[f['faces'][-1]]; e = ext[view]
        lo, hi = (project(view, c) for c in (to_sharp(f, item['bends']) if f['faces'][-1] != 'Z' else np.array(f['box_part_mm'])))  # tabs to the outside of the material
        lo, hi = np.minimum(lo, hi), np.maximum(lo, hi); a = int(np.argmin(hi - lo))
        p, q = lo.copy(), lo.copy(); q[a] = hi[a]
        across = (lo[1 - a] + hi[1 - a]) / 2 > e[1 - a] / 2
        if across: p[1 - a] = q[1 - a] = hi[1 - a]
        tiers[view][('T' if across else 'B') if a == 0 else ('R' if across else 'L')].append([(tuple(p), tuple(q))])
        if f['faces'][-1] != 'Z':  # upstanding flange, hidden in the top view: its length and where it starts, from the nearer part edge
            b = 1 - a; lo_b, hi_b = lo.copy(), lo.copy(); hi_b[b] = hi[b]
            ref = lo_b.copy(); ref[b] = 0 if lo[b] <= e[b] - hi[b] else e[b]
            seq = sorted([ref, lo_b, hi_b], key=lambda c: c[b])
            segs = [(tuple(u), tuple(w)) for u, w in zip(seq, seq[1:]) if w[b] - u[b] > 0.05]
            far = (lo[a] + hi[a]) / 2 > e[a] / 2
            if segs: tiers[view][('T' if far else 'B') if b == 0 else ('R' if far else 'L')].append(segs)
    levels, primary = {}, next(f for f in item['flanges'] if f['id'] == item['frame']['base_flange'])
    for f in item['flanges']:
        if f['faces'][-1] == 'Z' and not f['narrow']: levels.setdefault(round(f['centre_part_mm'][2], 2), []).append(f)
    z0 = primary['centre_part_mm'][2]; (x0, _, _), (x1, _, _) = primary['box_part_mm']
    for z, fs in sorted(levels.items()):  # flange heights off the primary flange, on the side the flange is on
        if abs(z - z0) < 0.05: continue
        right = np.mean([f['centre_part_mm'][0] for f in fs]) > size[0] / 2
        x = max(f['box_part_mm'][1][0] for f in fs) if right else min(f['box_part_mm'][0][0] for f in fs)
        tiers['front']['R' if right else 'L'].append([((x1 if right else x0, z0), (x, z))])
    sharps = []  # flange lengths along the front profile, between virtual sharps of the bends seen end-on
    for b in item['bends'] if all(b['axis'] != 'oblique' for b in item['bends']) else []:  # an oblique bend breaks the profile
        legs = b.get('legs_part', [])
        if AXIS_VIEW.get(b['axis'][-1]) != 'front' or len(legs) != 2 or any(abs(l['dir'][0]) < 0.01 for l in legs): continue
        (p1, d1), (p2, d2) = ((np.array(l['outer_point_mm'])[[0, 2]], np.array(l['dir'])[[0, 2]]) for l in legs)
        t = np.linalg.solve(np.column_stack([d1, -d2]), p2 - p1)[0]; sharps.append(tuple(p1 + t * d1))
    if sharps:
        sharps.sort(); seq = [(0, sharps[0][1]), *sharps, (size[0], sharps[-1][1])]
        segs = [(p, q) for p, q in zip(seq, seq[1:]) if q[0] - p[0] > 0.05]
        if segs: tiers['front']['T'].append(segs)
    return add_overall(tiers, size), calls


def edge(a, b, e):
    """Which way a cramped label can escape: past the view edge the dimension touches, else 0."""
    return -1 if min(a, b) < 0.1 else 1 if max(a, b) > e - 0.1 else 0


def on_edge(p, pts, ext, side):
    """A point on the view's edge moves along that edge to the outline point nearest the dimension line,
    so its extension line starts at the part instead of an empty box corner."""
    p = np.array(p, float); a = 0 if side in 'TB' else 1; b = 1 - a
    if not (abs(p[a]) < 1e-6 or abs(p[a] - ext[a]) < 1e-6): return p
    hit = pts[np.abs(pts[:, a] - p[a]) < 0.3]
    if len(hit): p[b] = hit[:, b].max() if side in 'TR' else hit[:, b].min()
    return p


def draw_tiers(ax, tiers, origin, k, size, outline):
    """Draw every tier; returns the extension lines as thin boxes (x, y, w, h) for label placement."""
    ext_lines = []
    for view, sides in tiers.items():
        o = origin[view]; e = np.array([size[i] for i in EXT[view]]) * k
        for side, rows in sides.items():
            for i, segs in enumerate(rows):
                d = 6 + TIER * i
                for j, (p, q) in enumerate(segs):
                    along = 0 if side in 'TB' else 1
                    if len(segs) == 1: end = -1 if p[along] + q[along] > e[along] / k else 1  # a lone dim off the view edge escapes toward the view centre
                    else: end = -1 if j == 0 else 1 if j == len(segs) - 1 else 0  # chain ends escape outward
                    p, q = (on_edge(c, outline[view], e / k, side) for c in (p, q))
                    a, b = o + np.array(p) * k, o + np.array(q) * k
                    c = 1 if side in 'TB' else 0; base = (o[1] + e[1] + d if side == 'T' else o[1] - d) if c else (o[0] + e[0] + d if side == 'R' else o[0] - d)
                    for m in (a, b):
                        lo, hi = sorted((m[c], base)); ext_lines.append((m[0], lo, 0, hi - lo) if c else (lo, m[1], hi - lo, 0))
                    if side in 'TB':
                        base = o[1] + e[1] + d if side == 'T' else o[1] - d
                        dim(ax, a, b, base - (max if side == 'T' else min)(a[1], b[1]), fmt(abs(q[0] - p[0])), True, edge(p[0], q[0], e[0] / k) or end)
                    else:
                        base = o[0] + e[0] + d if side == 'R' else o[0] - d
                        dim(ax, a, b, base - (max if side == 'R' else min)(a[0], b[0]), fmt(abs(q[1] - p[1])), False, edge(p[1], q[1], e[1] / k) or end)
    return ext_lines


_TRI, _MASK = {}, {}


def silhouette(shape, view, res=0.5):
    """Where the part is in a view, holes and slots included: boolean grid of res-mm cells, indexed [v, u] from the view origin."""
    key = (id(shape), view)
    if key not in _MASK:
        if id(shape) not in _TRI: _TRI[id(shape)] = (shape, triangles(shape))
        _, x, y = basis(view); t = _TRI[id(shape)][1]
        uv = np.stack([t @ x, t @ y], -1) / res + 2  # 2-cell margin all round, so the outside is one connected region
        img = Image.new('L', tuple(int(c) + 3 for c in np.ceil(uv.reshape(-1, 2).max(0)))); d = ImageDraw.Draw(img)
        for tri in uv: d.polygon([tuple(q) for q in tri], fill=1)
        ImageDraw.floodfill(img, (0, 0), 2)  # everything the outside can't reach is part: openings count as occupied
        _MASK[key] = (shape, (np.array(img) != 2)[2:, 2:])
    return _MASK[key][1], res


def overlaps(a, b):
    return not (a[0] + a[2] < b[0] or b[0] + b[2] < a[0] or a[1] + a[3] < b[1] or b[1] + b[3] < a[1])


class Space:
    """Free paper for labels: on the page, off the part (openings included), the dimension bands and extension lines,
    the other views, the view names and whatever is already placed."""
    DIRS = [45, 135, 225, 315, 0, 180, 90, 270, 22.5, 157.5, 202.5, 337.5, 67.5, 112.5, 247.5, 292.5]

    def __init__(self, origin, k, size, tiers, shape, ext_lines):
        self.origin, self.k, self.shape, self.region = origin, k, shape, {}
        for v, o in origin.items():
            e = np.array([size[i] for i in EXT[v]]) * k; P = {s: pad(tiers, v, s) for s in 'TBLR'}
            self.region[v] = ((o[0] - P['L'], o[1] - P['B'], e[0] + P['L'] + P['R'], e[1] + P['B'] + P['T']),
                              [(o[0] - P['L'], o[1] + e[1], e[0] + P['L'] + P['R'], P['T']), (o[0] - P['L'], o[1] - P['B'], e[0] + P['L'] + P['R'], P['B']),
                               (o[0] - P['L'], o[1] - P['B'], P['L'], e[1] + P['B'] + P['T']), (o[0] + e[0], o[1] - P['B'], P['R'], e[1] + P['B'] + P['T'])])
        self.taken = list(ext_lines) + [b for r in self.region.values() for b in r[1]]
        self.taken += [(r[0][0], r[0][1] - 4, 30, 4) for r in self.region.values()]  # view names under each view

    def clear(self, view, box):
        if box[0] < MARGIN + 2 or box[0] + box[2] > A3[0] - MARGIN - 2 or box[1] < MARGIN + TITLE_H or box[1] + box[3] > A3[1] - MARGIN - 8: return False
        if any(overlaps(box, b) for b in self.taken + [r[0] for v, r in self.region.items() if v != view]): return False
        mask, res = silhouette(self.shape, view); o, k = self.origin[view], self.k
        u0, v0 = ((np.array(box[:2]) - 1 - o) / k / res).astype(int); u1, v1 = np.ceil((np.array(box[:2]) + box[2:] + 1 - o) / k / res).astype(int)
        return not mask[max(v0, 0):max(v1, 0), max(u0, 0):max(u1, 0)].any()

    def spot(self, view, p, w, start=6):
        """Nearest clear place for a w-wide label led from p: (knee, side, box), reserved; None when there is none."""
        for d in np.arange(start, 60, 2):
            for t in self.DIRS:
                u = np.array([math.cos(math.radians(t)), math.sin(math.radians(t))]); q = p + d * u; s = 1 if u[0] > -1e-9 else -1
                box = (q[0] if s > 0 else q[0] - w, q[1] - 0.5, w, 4)
                if self.clear(view, box): self.taken.append(box); return q, s, box
        return None


def callouts(ax, calls, origin, k, size, space):
    """One leader per size group, reference style '4-□8.7×8.7', its label in the nearest clear space."""
    for view, groups in calls.items():
        o, c = origin[view], origin[view] + np.array([size[i] for i in EXT[view]]) * k / 2
        for label, pts in groups.items():
            uv, r = pts[0]; p = o + uv * k
            label = f'{len(pts)}-{label}' if len(pts) > 1 else label; w = 1.6 * len(label) + 1
            found = space.spot(view, p, w)
            if found: q, s, _ = found
            else: s = (np.sign(c - p) + (p == c))[0]; q = p + s * np.array([7, 7])  # nowhere clear: point into the view
            u = (q - p) / np.linalg.norm(q - p); tip = p + u * r * k
            ax.plot([tip[0], q[0], q[0] + s * w], [tip[1], q[1], q[1]], lw=LW_THIN, color=INK); arrow(ax, tip, q)
            text(ax, q[0] + s * 0.5, q[1] + 0.6, label, 2.4, ha='left' if s > 0 else 'right')


def angles(ax, item, origin, k, space):
    """Bends other than 90°, protractor style: an arc on the outside of the bend, from the flat leg's extension to the bent leg."""
    done = set()
    for b in item['bends']:
        view = AXIS_VIEW.get(b['axis'][-1])
        if not view or b['axis'] == 'oblique' or abs(b['angle_deg'] - 90) < 0.5: continue
        (pa, da), (pb, db) = ((project(view, l['outer_point_mm']), project(view, l['dir'])) for l in b['legs_part'])
        if np.abs(db).max() > np.abs(da).max(): (pa, da), (pb, db) = (pb, db), (pa, da)  # A = the leg more square to the view
        try: t = np.linalg.solve(np.column_stack([da, -db]), pb - pa)
        except np.linalg.LinAlgError: continue
        v = origin[view] + (pa + t[0] * da) * k; key = tuple(np.round(v, 1))
        if key in done: continue
        done.add(key); r = 9.0
        ax.plot(*zip(origin[view] + pa * k, v - da * (r + 2)), lw=LW_THIN, color=INK)
        ax.plot(*zip(origin[view] + pb * k, v + db * (r + 2)), lw=LW_THIN, color=INK)
        a0, a1 = math.degrees(math.atan2(-da[1], -da[0])), math.degrees(math.atan2(db[1], db[0]))
        if (a1 - a0) % 360 > 180: a0, a1 = a1, a0
        ax.add_patch(Arc(v, 2 * r, 2 * r, theta1=a0, theta2=a1, lw=LW_THIN, color=INK))
        at = lambda g, rr=r: v + rr * np.array([math.cos(math.radians(g)), math.sin(math.radians(g))])
        for th, back in ((a0, a0 + 8), (a1, a1 - 8)): arrow(ax, at(th), at(back))
        mid = a0 + ((a1 - a0) % 360) / 2; label = f"{b['angle_deg']:g}°"; w = 1.6 * len(label) + 1
        found = space.spot(view, at(mid), w, start=2)
        if not found: continue
        q, s, _ = found
        if np.linalg.norm(q - at(mid)) > 3: ax.plot(*zip(at(mid), q), lw=LW_THIN, color=INK)
        text(ax, q[0] + s * 0.5, q[1] + 0.2, label, 2.5, ha='left' if s > 0 else 'right')


# ---------- tables ----------

class Column:
    """Right-hand table column that flows onto continuation pages."""
    def __init__(self, pages, floor):
        self.pages, self.floor = pages, floor; self.ax = pages[-1][1]; self.y = A3[1] - MARGIN - 4

    def table(self, title, header, rows, widths):
        x0 = TABLE_X; rh = 3.6
        def head():
            text(self.ax, x0, self.y, title, 2.6, weight='bold'); self.y -= 2
            self.row(header, widths, x0, rh, bold=True)
        if self.y - 3 * rh < self.floor: self.more()
        head()
        for r in rows:
            if self.y - rh < self.floor: self.more(); head()
            self.row(r, widths, x0, rh)
        self.y -= 5

    def row(self, cells, widths, x0, rh, bold=False):
        x = x0
        for c, w in zip(cells, widths):
            self.ax.add_patch(Rectangle((x, self.y - rh), w, rh, fill=bold, fc='#eef2f5', ec='#888', lw=LW_THIN * .7))
            text(self.ax, x + 0.8, self.y - rh + 1.0, str(c), 2.0, weight='bold' if bold else 'normal')
            x += w
        self.y -= rh

    def more(self):
        fig, ax = new_page(); self.pages.append((fig, ax, 'continued')); self.ax = ax
        self.y = A3[1] - MARGIN - 4; self.floor = MARGIN + 4


LABEL_W, LABEL_H = 75.0, 13.0


def title_block(ax, fields):
    """Plain label for the supplier: part × qty, then material, thickness and mass. draw() adds a page number when there is more than one."""
    x0, y0 = A3[0] - MARGIN - LABEL_W, MARGIN
    ax.plot([x0, x0, A3[0] - MARGIN], [y0, y0 + LABEL_H, y0 + LABEL_H], lw=LW_THIN * 1.4, color=INK)
    text(ax, x0 + 3, y0 + LABEL_H - 6, fields['title'], min(3.0, (LABEL_W - 6) / (0.75 * max(len(fields['title']), 1))), weight='bold')
    text(ax, x0 + 3, y0 + LABEL_H - 11, f"{fields['material']}  ·  {fields['mass']}", 2.4)


def notes(ax, items, y):
    x = MARGIN + 3
    for i, s in enumerate(items):
        text(ax, x, y - i * 3.4, f'{i + 1}. {s}', 2.0, color='#333')


# ---------- sheets ----------

def page(ax, pages, shape, size, settings, key, title_fields, tables, note_lines, mark=None, tiers=None, calls=None, item=None):
    """One sheet: views, dimensions, optional marks, tables flowing down the right column, iso, notes."""
    tiers = tiers or add_overall(new_tiers(), size)
    _, k, origin, boxes = layout(size, tiers, settings.get('scales', {}).get(key))
    outline = draw_views(ax, shape, size, origin, k, settings.get('show_hidden', False), tiers)
    ext_lines = draw_tiers(ax, tiers, origin, k, size, outline)
    title_block(ax, title_fields)
    x = max(boxes[1][0] + boxes[1][2] + pad(tiers, 'top', 'R'), boxes[2][0]) + 4
    y = boxes[2][1] + boxes[2][3] + pad(tiers, 'right', 'T') + 4
    free = [(x, y, A3[0] - MARGIN - 4 - x, A3[1] - MARGIN - 8 - y)]
    if tables:
        col = Column(pages, table_floor(boxes))
        for t in tables: col.table(*t)
        free = [(boxes[2][0], y, TABLE_X - 6 - boxes[2][0], free[0][3])] + ([(TABLE_X, col.floor, TABLE_W, col.y - col.floor)] if col.ax is ax else [])
    iso = draw_iso(ax, shape, size, [b for b in free if b[2] > 0 and b[3] > 0], k)
    space = Space(origin, k, size, tiers, shape, ext_lines)
    if iso: space.taken.append(iso)
    if item: angles(ax, item, origin, k, space)
    if calls: callouts(ax, calls, origin, k, size, space)
    if mark: mark(ax, origin, k)
    notes(ax, note_lines, MARGIN + 3 + 3.4 * (len(note_lines) - 1))


def bend_note(item):
    if not item['bends']: return []
    r = sorted({fmt(b['inner_radius_mm']) for b in item['bends']}); a = Counter(f"{b['angle_deg']:g}°" for b in item['bends'])
    n = len(item['bends'])
    return [f"{n} bend{'s' * (n > 1)}, inside R{'/R'.join(r)} ({', '.join(f'{n}× {v}' for v, n in a.items())})."]


def draw(result, settings):
    items = [r for r in result['items'] if r['role'] == 'sheet' and r['item'] not in settings.get('skip_items', [])]
    multi = len(result['items']) > 1
    pages = []
    if multi and items:
        main = items[0]
        shape = placed([sh for r in result['items'] for sh in r['_shapes']], main['frame'])
        bb = bbox(shape); size = bb['size']; shift = -np.array(bb['min'])
        t = gp_Trsf(); t.SetTranslation(gp_Vec(*shift)); shape = BRepBuilderAPI_Transform(shape, t, True).Shape()
        fig, ax = new_page(); pages.append((fig, ax, 'assembly'))
        def balloons(ax, origin, k):
            taken = []
            for r in result['items']:
                for sh in r['_shapes']:
                    g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g)
                    p = origin['top'] + project('top', to_part(main['frame'], np.array(g.CentreOfMass().Coord())) + shift) * k
                    d = np.array([9.0, 7.0])
                    while any(np.linalg.norm(p + d - q) < 4.5 for q in taken): d = d + [0, 4.5]
                    taken.append(p + d); bubble(ax, p, p + d, str(r['item']), RED)
        bom = [[r['item'], r['description'][:24], r['role'].replace(' (probable)', '?'), r['qty'],
                f"{r['mass_each_kg']:.3f}", f"{r['mass_total_kg']:.3f}"] for r in result['items']]
        bom.append(['', 'TOTAL', '', sum(r['qty'] for r in result['items']), '', f"{result['total_mass_kg']:.3f}"])
        page(ax, pages, shape, size, settings, 'assembly',
             {'title': settings['title'] + ' — WELDMENT', 'material': settings['material'], 'mass': f"{result['total_mass_kg']:.3f} kg total"},
             [('PARTS LIST', ['ITEM', 'DESCRIPTION', 'TYPE', 'QTY', 'kg EA', 'kg TOT'], bom, [9, 45, 20, 10, 22, 22])],
             ["'?' = type guessed from the shape, please confirm."] * any('probable' in r['role'] for r in result['items']) + settings.get('notes', []),
             balloons)
    for item in items:
        shape = placed(item['_shapes'][:1], item['frame'])
        fig, ax = new_page(); pages.append((fig, ax, f"item {item['item']}"))
        tiers, calls = plan(item, item['overall_mm'], shape)
        oblique = [h['id'] for g in ('holes', 'slots', 'rectangles', 'cutouts') for h in item.get(g, []) if h['axis'] == 'oblique' or g == 'cutouts']
        unk = [u['what'] + (f": {u['counts']}" if 'counts' in u else '') + (f": {', '.join(u['ids'])}" if 'ids' in u else '') for u in item['unknowns']]
        if oblique: unk.append('openings on oblique faces or irregular cutouts: ' + ', '.join(oblique))
        page(ax, pages, shape, item['overall_mm'], settings, str(item['item']),
             {'title': settings['title'] + (f" — ITEM {item['item']}" if multi else '') + f"  ×{item['qty']}",
              'material': f"{settings['material']} {fmt(item['thickness_mm'])} mm", 'mass': f"{item['mass_each_kg']:.3f} kg each"},
             [], bend_note(item) + [f'NOT DIMENSIONED: {u}' for u in unk] + settings.get('notes', []),
             tiers=tiers, calls=calls, item=item)
    n = len(pages)
    for i, (fig, ax, what) in enumerate(pages, 1):
        if n > 1: text(ax, A3[0] - MARGIN - 18, MARGIN + 2, f'page {i} / {n}', 2.2, color='#444')
    return pages


def to_svgs(pages):
    out = []
    for fig, _, _ in pages:
        buf = io.StringIO(); fig.savefig(buf, format='svg')
        out.append(re.sub(r'<[^>]*>', lambda m: re.sub(r'(\d+\.\d{2})\d+', r'\1', m.group()), buf.getvalue()))  # geometry only, never label text
    return out


def to_pdf(pages, path, meta):
    with PdfPages(path, metadata=meta) as pdf:
        for fig, _, _ in pages: pdf.savefig(fig)


def close(pages):
    for fig, _, _ in pages: plt.close(fig)
