"""P2 printed checking gauge for Part_0009, laid out like an automotive checking fixture, every body printed.

BASE        flat plate (z -20..0) with hand slots, 100 mm grid grooves, 3 CMM bush bores with 40 mm scribe rings
supports    one per datum: net column + pad (flat, to the contact) tied to the GH-201-B pedestal whose clamp
            pushes straight down over that net; merged into the surface body (one printed material, user P4)
pins        P1/P2 are ground D6 dowels pushed into D6 holes in the surface body (user P5), 25 mm below the pin foot
SURFACE_n   contoured surface body + the 3 supports: region under the part outline, minus the part offset 3 mm
            swept +z (no perimeter rails); stations facing out of the outline get a local block behind the land; exact 3 mm
            station lands; gauge slots; CMM probe windows under part holes
Every detail sits on the base top (z 0) with 2 dowels + 1 M5 bolt from below into a heat-set insert.
Geometry in manifold3d (OCP offset fails on this part); faceted STEP + STL per body in geometry/.
Usage: make_gauge.py <fxp dir>
"""
import json
import os
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np

SKILL = Path(os.environ.get('DESIGN_FIXTURE_DIR', Path.home() / '.claude/skills/design-fixture'))
sys.path.insert(0, str(SKILL / 'scripts'))
from export_step import read_step, write_step
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeVertex
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.ShapeFix import ShapeFix_Shape
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Shell, TopoDS_Solid, TopoDS_Wire
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

GAP, CLEAR = 3.0, 1.0                  # check gap; clearance between printed details
DEFLECTION, SEG = 0.05, 16
BASE_Z = -20.0                          # base plate bottom (top is z 0)
BX, BY = (-180.0, 175.0), (-300.0, 300.0)
PIN_FOOT = 63.5
D = Path(sys.argv[1])
spec = json.loads((D / 'spec.json').read_text())
part = next(v for k, v in read_step(D / 'workpiece.step').items() if k.endswith('Part_0009'))
hw = json.loads((SKILL / 'references/hardware/gh-201-b.json').read_text())


def to_manifold(shape):
    BRepMesh_IncrementalMesh(shape, DEFLECTION, False, 0.2, True).Perform()
    key, tris = {}, []; ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current()); ex.Next(); loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f, loc); tr = loc.Transformation()
        ids = [key.setdefault(tuple(np.round(tri.Node(i).Transformed(tr).Coord(), 5)), len(key)) for i in range(1, tri.NbNodes() + 1)]
        for i in range(1, tri.NbTriangles() + 1):
            a, b, c = (ids[j - 1] for j in tri.Triangle(i).Get())
            tris.append((a, c, b) if f.Orientation() == TopAbs_REVERSED else (a, b, c))
    m = mf.Manifold(mf.Mesh(vert_properties=np.array(list(key), np.float32), tri_verts=np.array(tris, np.uint32)))
    assert m.status() == mf.Error.NoError, m.status()
    return m


def hull(pts): return mf.Manifold.hull_points(np.asarray(pts, float))
def box(lo, hi): return mf.Manifold.cube(np.subtract(hi, lo)).translate(lo)
def cyl(xy, z0, z1, r): return mf.Manifold.cylinder(z1 - z0, r / np.cos(np.pi / 64), circular_segments=64).translate((xy[0], xy[1], z0))


def obox(c, a, b, n, sa, sb, n0, n1):
    c, a, b, n = (np.array(x, float) for x in (c, a, b, n))
    return hull([c + n * t + a * i * sa + b * j * sb for t in (n0, n1) for i in (-1, 1) for j in (-1, 1)])


def union(ms): return mf.Manifold.batch_boolean(ms, mf.OpType.Add)


pm = to_manifold(part)
r3 = (GAP + DEFLECTION) / np.cos(np.pi / SEG) ** 2
ball = mf.Manifold.sphere(r3, SEG)
cavity = pm.minkowski_sum(mf.Manifold.batch_hull([ball, ball.translate((0, 0, 200))]))  # part + 3 mm, swept up

# ---- supports: net column + pad, rib, clamp pedestal on the 50x60 standard mount area -------------------------
clamps = {c['support']: c for c in spec['clamps']}
mount = hw['standard_mount_plate']; holes = np.array(hw['mounting']['hole_centres_canonical_mm'])[:, :2]


def pedestal_xy(cl, g=0.0):
    m = np.array(cl['mount_transform'], float); O, x, y = m[:3, 3], m[:3, 0], m[:3, 1]
    c = O + x * mount['centre_canonical_mm'][0]
    return [c + x * i * (mount['along_x_mm'] / 2 + g) + y * j * (mount['across_y_mm'] / 2 + g) for i in (-1, 1) for j in (-1, 1)], O, x, y


def support(ct, g=0.0):
    p = np.array(ct['contact']); cl = clamps[ct['name']]
    corners, O, x, y = pedestal_xy(cl, g)
    ped = hull([c[:2].tolist() + [z] for c in corners for z in (0.0, O[2] + (g and 200))])
    col = cyl(p, 0.0, p[2] + (g and 200), 10.0 + g)
    pc = O + x * mount['centre_canonical_mm'][0]
    rib = hull([(q + y * s * (8 + g))[:2].tolist() + [z] for q in (p, pc) for s in (-1, 1) for z in (0.0, 40.0 + (g and 200))])
    return union([ped, col, rib])


bodies, supports = {}, []
for ct in spec['contacts']:
    p = ct['contact']; cl = clamps[ct['name']]
    b = support(ct) - cavity
    b += cyl(p, p[2] - 10.0, p[2], 5.0)                               # net pad, flat, on the contact
    _, O, x, y = pedestal_xy(cl)
    for h in holes:                                                   # M5 heat-set inserts for the clamp base
        q = O + x * h[0] + y * h[1]
        b -= cyl(q, O[2] - 10.0, O[2] + 1, 3.2)
    supports.append(b)

# ---- surface body ------------------------------------------------------------------------------------------------
disk = mf.Manifold.cylinder(1.0, 0.5, circular_segments=SEG)                     # outline only, no rails
below = pm.minkowski_sum(mf.Manifold.batch_hull([disk.translate((0, 0, -1)), disk.translate((0, 0, -300))]))
# stations whose land faces out of the outline: a post behind the land (16 wide x 12 deep, up to the land top),
# tied back to the main body by a foot that stays 15 mm below the station (does not wrap the tab)
blocks = []
for fl in spec['inspection']['flanges']:
    for c in fl['checks']:
        pt, d, p = c['patch'], np.array(c['direction'], float), np.array(c['point_mm'], float)
        if d[2] < -0.5: continue                                            # land under the part: in the main body
        u, v = np.array(pt['u'], float), np.array(pt['v'], float)
        post = [p + d * t + u * i * (pt['width_mm'] / 2 + 3) + v * j * (pt['height_mm'] / 2 + 1)
                for t in (GAP, GAP + 12) for i in (-1, 1) for j in (-1, 1)]
        blocks.append(hull(post + [q * [1, 1, 0] for q in post]))
        foot = [q * [1, 1, 0] + t * -d * [1, 1, 0] + [0, 0, z] for q in post for t in (0, 25) for z in (0, p[2] - 15)]
        blocks.append(hull(foot))
surf = ((below + union(blocks)) ^ box((BX[0], BY[0], 0.0), (BX[1], BY[1], 200.0))) - cavity
surf += union(supports)                                                 # nets + clamp pedestals, same body
# CMM probe windows (hole r + 2) under the two part slots not used by pins, through the surface body
for a, b_, r in (((33.8, -194.9), (33.8, -197.9), 3.05), ((-36.4, 190.5), (-36.4, 193.5), 2.7)):
    surf -= mf.Manifold.batch_hull([cyl(a, -1, 90, r + 2), cyl(b_, -1, 90, r + 2)])
for fl in spec['inspection']['flanges']:
    for c in fl['checks']:
        pt = c['patch']
        surf += obox(c['point_mm'], pt['u'], pt['v'], c['direction'], pt['width_mm'] / 2 + 1, pt['height_mm'] / 2 + 1, GAP, GAP + 1.5)
for fl in spec['inspection']['flanges']:
    for c in fl['checks']:
        d, a = np.array(c['direction'], float), np.array(c['gauge_envelope']['approach_direction'], float)
        u = np.cross(d, a); u /= np.linalg.norm(u); w = c['gauge_envelope']['width_mm'] / 2 + 1; p = np.array(c['point_mm'], float)
        surf -= hull([p + u * su * w + d * sd + a * t for su in (-1, 1) for sd in (-1, GAP) for t in (0, 400)])
for pin in spec['inspection']['pin_bearings']:
    surf -= cyl(pin['point_mm'], PIN_FOOT - 25.0, 90.0, 3.0)           # D6 hole for the ground dowel pin
secs = sorted(surf.decompose(), key=lambda m: -m.volume())
secs = [s for s in secs if s.volume() > 1000.0]                         # drop boolean wafers
for i, s in enumerate(sorted(secs, key=lambda m: m.bounding_box()[1]), 1):
    bodies[f'SURFACE_{i}'] = s

# ---- base -----------------------------------------------------------------------------------------------------------
base = box((BX[0], BY[0], BASE_Z), (BX[1], BY[1], 0.0))
for s in (-1, 1):                                                       # hand slots
    base -= box((-55, s * 272 - 15, BASE_Z - 1), (55, s * 272 + 15, 1))
for gx in (-100, 0, 100):                                               # 100 mm grid, 1 wide x 0.5 deep
    base -= box((gx - 0.5, BY[0] + 5, -0.5), (gx + 0.5, BY[1] - 5, 1))
for gy in (-200, -100, 0, 100, 200):
    base -= box((BX[0] + 5, gy - 0.5, -0.5), (BX[1] - 5, gy + 0.5, 1))
CMM = [(BX[0] + 65, BY[0] + 65), (BX[1] - 65, BY[0] + 65), (BX[0] + 65, BY[1] - 65)]
for q in CMM:                                                           # D12 bush bore + 40 mm scribe ring
    base -= cyl(q, BASE_Z - 1, 1, 6.0)
    base -= cyl(q, -0.5, 1, 20.5) - cyl(q, -1, 2, 19.5)

# ---- joints: 2 D6 dowels + 1 M5 bolt per detail (4 bolts on the big surface body), picked inside each footprint -------------------------------------
joints = {}
for name, b in list(bodies.items()):
    foot = b.slice(1.0) - (b.slice(1.0) - b.slice(11.0))                # footprint solid from z 0 to z 11
    for rj in (7.0, 5.0):                                               # 5 mm edge distance on small blocks
        pts = np.array([v for poly in foot.offset(-rj, mf.JoinType.Round).to_polygons() for v in poly])
        if len(pts) >= 3: break
    assert len(pts) >= 3, f'{name}: no room for dowels'
    pick = [pts[np.argmax(np.linalg.norm(pts - pts.mean(0), axis=1))]]
    for _ in range(2 if foot.area() < 20000 else 5):
        pick.append(pts[np.argmax(np.min([np.linalg.norm(pts - q, axis=1) for q in pick], axis=0))])
    (d1, d2), bolts = pick[:2], pick[2:]
    for q in (d1, d2):
        b -= cyl(q, -1, 8, 3.0); base -= cyl(q, -8, 1, 3.0)
    for bolt in bolts:
        b -= cyl(bolt, -1, 10, 3.2)                                     # heat-set insert
        base -= cyl(bolt, BASE_Z - 1, 1, 2.75) + cyl(bolt, BASE_Z - 1, BASE_Z + 6, 5.0)
    bodies[name] = b; joints[name] = {'dowels': [d1.round(1).tolist(), d2.round(1).tolist()], 'bolts': [q.round(1).tolist() for q in bolts]}
bodies = {'BASE': base, **bodies}


def export(name, body):
    assert body.status() == mf.Error.NoError and len(body.decompose()) == 1, f'{name}: {len(body.decompose())} lumps'
    body = body.simplify(5e-3)
    mesh = body.to_mesh64(); V, T = np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts)
    V, inv = np.unique(np.round(V, 4), axis=0, return_inverse=True); T = inv.reshape(-1)[T]  # weld near-coincident verts
    T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]
    tri = V[T]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1)[:, None]
    rec = np.zeros(len(T), [('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]); rec['n'], rec['v'] = nrm, tri
    stem = name.lower()
    with open(D / f'geometry/{stem}.stl', 'wb') as fh:
        fh.write(name.encode().ljust(80, b' ')); fh.write(np.uint32(len(T)).tobytes()); fh.write(rec.tobytes())
    bb = BRep_Builder(); vx = [BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex() for p in V]; ed = {}
    def edge(i, j):
        if (j, i) in ed: return ed[(j, i)].Reversed()
        ed[(i, j)] = BRepBuilderAPI_MakeEdge(vx[i], vx[j]).Edge(); return ed[(i, j)]
    shell = TopoDS_Shell(); bb.MakeShell(shell)
    for (i, j, k), n in zip(T, nrm):
        w = TopoDS_Wire(); bb.MakeWire(w)
        for e in (edge(i, j), edge(j, k), edge(k, i)): bb.Add(w, e)
        bb.Add(shell, BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(*V[i]), gp_Dir(*n)), w, True).Face())
    shell.Closed(True); solid = TopoDS_Solid(); bb.MakeSolid(solid); bb.Add(solid, shell)
    fx = ShapeFix_Shape(solid); fx.SetPrecision(1e-3); fx.SetMaxTolerance(1e-2); fx.Perform(); solid = fx.Shape()
    u = ShapeUpgrade_UnifySameDomain(solid, True, True, True); u.Build(); solid = u.Shape()
    assert BRepCheck_Analyzer(solid).IsValid(), f'{name}: faceted solid invalid'
    write_step(D / f'geometry/{stem}.step', {name: solid})
    lo, hi = np.round(body.bounding_box()[:3], 1), np.round(body.bounding_box()[3:], 1)
    print(f'{name:11s} {len(T):7d} tri  {body.volume() / 1e3:8.0f} cm3  bbox {lo.tolist()} {hi.tolist()}')
    return {'name': name, 'finished_step': f'geometry/{stem}.step'}


(D / 'geometry').mkdir(exist_ok=True)
out = [export(n, b) for n, b in bodies.items()]
(D / 'geometry/gauge_bodies.json').write_text(json.dumps({'printed_bodies': out, 'joints': joints}, indent=1))
print('total solid volume', round(sum(b.volume() for b in bodies.values()) / 1e3), 'cm3')
