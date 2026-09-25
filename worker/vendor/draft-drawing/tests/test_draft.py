"""Regression tests on parts built with OCP primitives; no fixture files."""
import math
import sys
import tempfile
import unittest
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
# L-bracket: 3 mm, inner bend R3, base 100(x) x 60(y) along y-depth 80, upright 50 high. Holes + slot.
from OCP.gp import gp_Pnt, gp_Vec, gp_Ax2, gp_Dir
from OCP.GC import GC_MakeArcOfCircle, GC_MakeSegment
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs


def l_bracket(path, extra=None):
    """3 mm L-bracket, inner R3 bend, 100 x 80 x 50; three Z holes, two X holes, one 10x30 slot. `extra` adds a separate solid."""
    t, ri = 3.0, 3.0; ro = ri + t
    L, H, D = 100.0, 50.0, 80.0   # base length (x), upright height (z), depth (y)
    # profile in XZ; bend at x=0 corner; base extends +x, upright goes +z at x=0
    cx, cz = ro, ro  # bend centre
    P = lambda x, z: gp_Pnt(x, 0, z)
    s = math.sqrt(0.5)
    edges = [
      GC_MakeSegment(P(ro, 0), P(L, 0)).Value(),
      GC_MakeSegment(P(L, 0), P(L, t)).Value(),
      GC_MakeSegment(P(L, t), P(ro, t)).Value(),
      GC_MakeArcOfCircle(P(ro, t), P(cx - ri*s, cz - ri*s), P(t, ro)).Value(),
      GC_MakeSegment(P(t, ro), P(t, H)).Value(),
      GC_MakeSegment(P(t, H), P(0, H)).Value(),
      GC_MakeSegment(P(0, H), P(0, ro)).Value(),
      GC_MakeArcOfCircle(P(0, ro), P(cx - ro*s, cz - ro*s), P(ro, 0)).Value(),
    ]
    w = BRepBuilderAPI_MakeWire()
    for e in edges: w.Add(BRepBuilderAPI_MakeEdge(e).Edge())
    body = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(w.Wire()).Face(), gp_Vec(0, D, 0)).Shape()
    def cut(a, b): return BRepAlgoAPI_Cut(a, b).Shape()
    zc = lambda x, y, d: BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0,0,1)), d/2, t+2).Shape()
    xc = lambda y, z, d: BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(-1, y, z), gp_Dir(1,0,0)), d/2, t+2).Shape()
    body = cut(body, zc(40, 20, 9.0)); body = cut(body, zc(40, 60, 9.0)); body = cut(body, zc(80, 40, 6.5))
    # slot in base: 10 wide x 30 long along x, centred (75,15)
    slot = BRepAlgoAPI_Fuse(BRepPrimAPI_MakeBox(gp_Pnt(65, 10, -1), 20, 10, t+2).Shape(),
            BRepAlgoAPI_Fuse(zc(65, 15, 10), zc(85, 15, 10)).Shape()).Shape()
    body = cut(body, slot)
    body = cut(body, xc(25, 30, 11.0)); body = cut(body, xc(55, 30, 11.0))  # upright holes
    shapes = [body] + ([extra] if extra is not None else [])
    wr = STEPControl_Writer()
    for s in shapes: wr.Transfer(s, STEPControl_AsIs)
    wr.Write(str(path))


def joggle(path):
    """3 mm profile, 60 deep: 16 mm down-tab at x=0 (R3/R6), 100 mm base, 45° joggle up to a top flange; outer skin 13 -> 36."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    pts = [(3, 0), (3, 13), (100, 13), (120, 33), (160, 33), (160, 36), (118.757, 36), (98.757, 16), (0, 16), (0, 0)]
    poly = BRepBuilderAPI_MakePolygon()
    for x, z in pts: poly.Add(gp_Pnt(x, 0, z))
    poly.Close()
    body = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(), gp_Vec(0, 60, 0)).Shape()
    radius = {(3, 13): 3, (0, 16): 6, (100, 13): 6, (98.757, 16): 3, (120, 33): 3, (118.757, 36): 6}  # inner R3, outer R6
    fillet, ex = BRepFilletAPI_MakeFillet(body), TopExp_Explorer(body, TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge_s(ex.Current()); a, b = BRep_Tool.Pnt_s(TopExp.FirstVertex_s(e)), BRep_Tool.Pnt_s(TopExp.LastVertex_s(e))
        r = radius.get((round(a.X(), 3), round(a.Z(), 3)))
        if r and abs(a.X() - b.X()) < 1e-6 and abs(a.Z() - b.Z()) < 1e-6: fillet.Add(r, e)  # the bend edges run along y
        ex.Next()
    wr = STEPControl_Writer(); wr.Transfer(fillet.Shape(), STEPControl_AsIs); wr.Write(str(path))


import measure  # noqa: E402
import sheet  # noqa: E402
import workflow  # noqa: E402


class BracketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.step = Path(cls.tmp.name) / 'bracket.step'
        l_bracket(cls.step)
        cls.r = measure.measure(cls.step)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_mass_and_overall(self):
        self.assertAlmostEqual(self.r['total_mass_kg'], 0.259, places=3)
        item = self.r['items'][0]
        self.assertEqual(item['role'], 'sheet'); self.assertEqual(item['thickness_mm'], 3.0)
        self.assertEqual(item['overall_mm'], [100.0, 80.0, 50.0])

    def test_holes_slot_bend(self):
        item = self.r['items'][0]
        holes = {(h['diameter_mm'], tuple(round(v, 1) for v in h['part_mm'])) for h in item['holes']}
        self.assertEqual(holes, {(9.0, (40.0, 20.0, 0.0)), (9.0, (40.0, 60.0, 0.0)), (6.5, (80.0, 40.0, 0.0)),
                                 (11.0, (0.0, 25.0, 30.0)), (11.0, (0.0, 55.0, 30.0))})
        (slot,) = item['slots']
        self.assertEqual((slot['width_mm'], slot['length_mm']), (10.0, 30.0))
        self.assertEqual([round(v, 1) for v in slot['part_mm']], [75.0, 15.0, 0.0])
        (bend,) = item['bends']
        self.assertEqual((bend['inner_radius_mm'], bend['angle_deg']), (3.0, 90.0))
        self.assertEqual(item['unknowns'], [])

    def test_sheet_dims_once_and_one_decimal(self):
        item = self.r['items'][0]
        tiers, _ = sheet.plan(item, item['overall_mm'], sheet.placed(item['_shapes'][:1], item['frame']))
        self.assertEqual(len(tiers['right']['B']), 1)  # the 80.0 width once, not twice
        self.assertEqual((sheet.fmt(35.001), sheet.fmt(4.999), sheet.fmt(18.757)), ('35.0', '5.0', '18.76'))
        self.assertEqual(sheet.bend_note(item), ['1 bend, inside R3.0 (1× 90°).'])

    def test_callouts_sit_off_the_part(self):
        item = self.r['items'][0]
        tiers, _ = sheet.plan(item, item['overall_mm'], sheet.placed(item['_shapes'][:1], item['frame']))
        _, _, _, boxes = sheet.layout(item['overall_mm'], tiers)
        views = [boxes[1], boxes[2]]  # top and right views of the bracket are full rectangles of material
        pages = sheet.draw(self.r, {**workflow.DEFAULTS, 'title': 'B'})
        try:
            fig, ax, _ = pages[0]; fig.canvas.draw(); rnd = fig.canvas.get_renderer(); inv = ax.transData.inverted()
            calls = [t for t in ax.texts if any(c in t.get_text() for c in 'Ø□') or t.get_text().startswith('SLOT')]
            self.assertEqual(len(calls), 4)
            for t in calls:
                (x0, y0), (x1, y1) = inv.transform(t.get_window_extent(rnd).get_points())
                self.assertEqual([v for v in views if x0 < v[0] + v[2] and v[0] < x1 and y0 < v[1] + v[3] and v[1] < y1], [], t.get_text())
        finally:
            sheet.close(pages)


class AssemblyTest(unittest.TestCase):
    def test_second_body_is_separate_item_and_summed(self):
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        with tempfile.TemporaryDirectory() as d:
            step = Path(d) / 'asm.step'
            l_bracket(step, BRepPrimAPI_MakeBox(gp_Pnt(200, 0, 0), 20, 20, 20).Shape())
            r = measure.measure(step)
        self.assertEqual(len(r['items']), 2)
        block = r['items'][1]
        self.assertNotEqual(block['role'], 'sheet')
        self.assertAlmostEqual(block['mass_each_kg'], 8000 * 7850e-9, places=4)
        self.assertAlmostEqual(r['items'][0]['mass_each_kg'], 0.2585, delta=1e-4)
        self.assertAlmostEqual(r['total_mass_kg'], sum(i['mass_total_kg'] for i in r['items']), places=3)
        self.assertEqual(len({i['description'] for i in r['items']}), 2)


class DraftingRulesTest(unittest.TestCase):
    """The shop-drawing rules on a joggle with a tab: heights off the primary flange, tabs to the outside of the material,
    flange lengths to the virtual sharps, and no label on top of another."""
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            step = Path(d) / 'joggle.step'; joggle(step); cls.r = measure.measure(step)
        cls.item = cls.r['items'][0]
        tiers, _ = sheet.plan(cls.item, cls.item['overall_mm'], sheet.placed(cls.item['_shapes'][:1], cls.item['frame']))
        cls.dims = {(v, s): [[round(abs(q[0 if s in 'TB' else 1] - p[0 if s in 'TB' else 1]), 2) for p, q in segs] for segs in rows]
                    for v, sides in tiers.items() for s, rows in sides.items()}

    def test_measured(self):
        self.assertEqual(self.item['overall_mm'], [160.0, 60.0, 36.0])
        self.assertEqual(sorted(b['angle_deg'] for b in self.item['bends']), [45.0, 45.0, 90.0])

    def test_flange_lengths_to_virtual_sharps(self):
        self.assertIn([100.0, 18.76, 41.24], self.dims['front', 'T'])

    def test_height_off_primary_flange(self):
        self.assertIn([23.0], self.dims['front', 'R'])   # 13 -> 36 outer skins, not 36 from the bottom
        self.assertNotIn([13.0], self.dims['front', 'L'])  # the primary flange is the datum, not dimensioned from the tab end

    def test_tab_to_outside_of_material(self):
        self.assertIn([16.0], self.dims['right', 'L'])  # flat is 10; the outside of the bend is at 16

    def test_labels_do_not_overlap(self):
        pages = sheet.draw(self.r, {**workflow.DEFAULTS, 'title': 'J', 'drawing_no': 'J'})
        try:
            for fig, ax, _ in pages:
                fig.canvas.draw(); rnd = fig.canvas.get_renderer()
                boxes = [(t.get_text(), t.get_window_extent(rnd)) for t in ax.texts if t.get_text().strip()]
                self.assertEqual([(a, b) for i, (a, x) in enumerate(boxes) for b, y in boxes[i + 1:] if x.overlaps(y)], [])
                self.assertIn('45°', [t for t, _ in boxes])  # protractor arc label on the non-90° bends
        finally:
            sheet.close(pages)


class WorkflowTest(unittest.TestCase):
    def run_wf(self, *args):
        return subprocess.run([sys.executable, str(HERE.parent / 'scripts' / 'workflow.py'), *map(str, args)], capture_output=True, text=True)

    def test_preview_then_finalize_and_staleness(self):
        with tempfile.TemporaryDirectory() as d:
            step, out = Path(d) / 'bracket.step', Path(d) / 'out'
            l_bracket(step)
            p = self.run_wf('preview', step, out); self.assertEqual(p.returncode, 0, p.stderr)
            summary = json.loads(p.stdout)
            self.assertTrue(summary['soft_target_met'])
            self.assertIn('__SCENE_GZIP_BASE64__', (HERE.parent / 'assets/preview.html').read_text())
            self.assertNotIn('__SCENE_GZIP_BASE64__', (out / 'preview.html').read_text())
            f = self.run_wf('finalize', out, '--request', 'make the pdf'); self.assertEqual(f.returncode, 0, f.stderr)
            self.assertTrue((out / 'bracket.pdf').read_bytes().startswith(b'%PDF'))
            s = json.loads((out / 'drawing.json').read_text()); s['title'] = 'CHANGED'
            (out / 'drawing.json').write_text(json.dumps(s))
            f = self.run_wf('finalize', out, '--request', 'make the pdf')
            self.assertNotEqual(f.returncode, 0); self.assertIn('changed since the preview', f.stderr)


if __name__ == '__main__':
    unittest.main()
