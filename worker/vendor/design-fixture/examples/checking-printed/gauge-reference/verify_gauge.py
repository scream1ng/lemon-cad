"""Measure the P2 printed bodies (exact OCP on the faceted STEPs): station gaps, datum contact, part clearance,
body-body and REF pin / clamp hardware interference. Run from the fxp dir after make_gauge.py."""
import itertools, json, os, sys; from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('DESIGN_FIXTURE_DIR', Path.home() / '.claude/skills/design-fixture')) / 'scripts'))
import numpy as np
from export_step import read_step
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.GProp import GProp_GProps; from OCP.BRepGProp import BRepGProp
from OCP.TopExp import TopExp_Explorer; from OCP.TopAbs import TopAbs_FACE
from OCP.gp import gp_Pnt
spec = json.load(open('spec.json')); w = read_step('workpiece.step')
part = next(v for k, v in w.items() if k.endswith('Part_0009'))
B = {k: v for e in json.load(open('geometry/gauge_bodies.json'))['printed_bodies'] for k, v in read_step(e['finished_step']).items()}
def dist(a, b): d = BRepExtrema_DistShapeShape(a, b); d.Perform(); return d.Value(), d
def inter(a, b): g = GProp_GProps(); BRepGProp.VolumeProperties_s(BRepAlgoAPI_Common(a, b).Shape(), g); return g.Mass()
vert = lambda p: BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
fails = []
surf = [v for k, v in B.items() if k.startswith(('SURFACE', 'POST'))]
for fl in spec['inspection']['flanges']:
    for c in fl['checks']:
        p, d = np.array(c['point_mm']), np.array(c['direction'])
        v, x = min((dist(vert(p), s) for s in surf), key=lambda t: t[0]); q = np.array(x.PointOnShape2(1).Coord())
        print(c['id'], 'station->surface', round(v, 4), 'along d', round(float((q - p) @ d), 4))
        if abs(v - 3.0) > 0.01: fails.append(c['id'])
        on = dist(vert(p), part)[0]                                  # station must sit on the part face
        if on > 1e-3: print(c['id'], 'station OFF PART by', round(on, 4)); fails.append(c['id'] + ' off part')
for ct in spec['contacts']:
    v = dist(vert(ct['contact']), B[ct['rib']])[0]; print(ct['name'], 'contact->', ct['rib'], round(v, 4))
    if v > 0.01: fails.append(ct['name'])
A = [np.array(c['contact'][:2]) for c in spec['contacts']]
for k, b in B.items():
    ex = TopExp_Explorer(b, TopAbs_FACE); close = []
    while ex.More():
        f = ex.Current(); ex.Next(); v, x = dist(f, part)
        if v < 2.99:
            p = np.array(x.PointOnShape1(1).Coord())
            if min(np.linalg.norm(p[:2] - a) for a in A) > 5.5: close.append((round(v, 3), p.round(1).tolist()))
    if inter(part, b) > 1e-3 or close: fails.append(k)
    print(f'{k:11s} part interference {inter(part, b):.4f}  min {dist(part, b)[0]:.3f}  faces <2.99 off pads {len(close)}', sorted(close)[:3])
for a, b in itertools.combinations(B, 2):
    v = inter(B[a], B[b])
    if v > 1e-3: print('BODY CLASH', a, b, round(v, 3)); fails.append(f'{a}/{b}')
hw = read_step('WORK/concept/concept.step')
for k, s in list(w.items()) + [(k, v) for k, v in hw.items() if k.startswith('HW_')]:
    if k.startswith(('REF_', 'HW_')):
        for n, b in B.items():
            v = inter(s, b)
            if v > 1e-3: print('HW CLASH', k, n, round(v, 3)); fails.append(f'{k}/{n}')
print(f'FAIL {fails}' if fails else f'pass: {sum(len(f["checks"]) for f in spec["inspection"]["flanges"])} stations @3.0, datums on pads, no interference or clashes')
sys.exit(1 if fails else 0)
