"""Pin clearance screen: pins stay clear of every plate but their own pad."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
import pin_clearance
import preview


def box(x0, y0, z0, x1, y1, z1):
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), gp_Pnt(x1, y1, z1)).Shape()


SPEC = {'plates': [{'name': 'PAD'}, {'name': 'CHEEK'}, {'name': 'RAIL1'}, {'name': 'RAIL2'}],
        'pin_locators': [{'id': 'P1', 'shape_name': 'REF_PIN_P1', 'mode': 'fixed'}]}
PAD = box(0, 0, 0, 40, 40, 5)
PIN = box(17, 17, 5, 23, 23, 15)
RAILS = {'RAIL1': box(0, 0, -20, 40, 5, 0), 'RAIL2': box(0, 35, -20, 40, 40, 0)}  # the pad's cheek pair
REAMED = BRepAlgoAPI_Cut(PAD, box(16.7, 16.7, -1, 23.3, 23.3, 6)).Shape()  # 6.6 hole for a 6.0 dowel


class PinClearanceTests(unittest.TestCase):
    def run_with(self, cheek):
        return pin_clearance.audit(SPEC, {'PAD': PAD, 'CHEEK': cheek, **RAILS, 'REF_PIN_P1': PIN})

    def test_clear_pin_on_its_pad_passes(self):
        r = self.run_with(box(30, 0, -20, 35, 40, 5))
        self.assertEqual(r['status'], 'pass'); self.assertEqual(r['pins'][0]['host'], ['PAD'])

    def test_dowel_pressed_through_its_pad_passes_with_the_pad_thickness_as_bearing(self):
        r = pin_clearance.audit(SPEC, {'PAD': REAMED, **RAILS, 'REF_PIN_P1': box(17, 17, 0, 23, 23, 15)})
        self.assertEqual(r['status'], 'pass')
        self.assertEqual((r['pins'][0]['host'], r['pins'][0]['mode'], r['pins'][0]['bearing_mm']), (['PAD'], 'pressed', 5.0))

    def test_dowel_part_way_into_the_hole_has_no_bearing_and_fails(self):
        r = pin_clearance.audit(SPEC, {'PAD': REAMED, **RAILS, 'REF_PIN_P1': box(17, 17, 2, 23, 23, 15)})
        self.assertEqual(r['status'], 'fail'); self.assertEqual(r['unseated'], ['P1'])

    def test_dowel_standing_on_a_rib_edge_is_not_seated(self):
        r = pin_clearance.audit(SPEC, {'CHEEK': box(15, 17.5, -30, 25, 22.5, 5), 'REF_PIN_P1': PIN})
        self.assertEqual(r['status'], 'fail'); self.assertEqual(r['unseated'], ['P1'])
        self.assertEqual(r['pins'][0]['edge_seat'], 'CHEEK')
        self.assertIn('CHEEK carries it on a plate edge', r['next_action'])

    def test_tab_close_to_pin_fails(self):
        r = self.run_with(box(25, 0, -20, 30, 40, 5))
        self.assertEqual(r['status'], 'fail')
        self.assertEqual(preview.failing_items('pin_clearance', r), ['P1~CHEEK 2.0mm'])

    def test_tab_under_pin_base_fails(self):
        r = self.run_with(box(20, 0, -20, 25, 40, 5))
        self.assertEqual(r['status'], 'fail'); self.assertEqual(r['pins'][0]['host'], ['PAD'])
        self.assertEqual(preview.failing_items('pin_clearance', r), ['P1~CHEEK 0.0mm'])

    def test_plate_through_pin_fails(self):
        r = self.run_with(box(20, 0, -20, 25, 40, 10))
        self.assertEqual(r['status'], 'fail'); self.assertGreater(r['violations'][0]['overlap_mm3'], 0)

    def test_pin_without_pad_fails(self):
        r = pin_clearance.audit(SPEC, {'CHEEK': box(60, 0, 0, 65, 40, 5), 'REF_PIN_P1': PIN})
        self.assertEqual(r['status'], 'fail'); self.assertEqual(r['unseated'], ['P1'])

    def test_removable_pin_in_bush_passes_fixed_pin_does_not(self):
        bush, pin = box(15, 15, 5, 25, 25, 8), box(17, 17, 8, 23, 23, 18)
        shapes = {'PAD': PAD, **RAILS, 'REF_BUSH_P1': bush, 'REF_PIN_P1': pin}
        spec = {**SPEC, 'pin_locators': [{**SPEC['pin_locators'][0], 'mode': 'removable'}]}
        r = pin_clearance.audit(spec, shapes)
        self.assertEqual(r['status'], 'pass'); self.assertEqual(r['pins'][0]['host'], ['REF_BUSH_P1'])
        r = pin_clearance.audit(SPEC, shapes)
        self.assertEqual(r['status'], 'fail'); self.assertEqual(r['unseated'], ['P1'])

    def test_pad_on_a_single_rib_rocks_and_fails(self):
        r = pin_clearance.audit(SPEC, {'PAD': PAD, 'RAIL1': RAILS['RAIL1'], 'REF_PIN_P1': PIN})
        self.assertEqual(r['status'], 'fail'); self.assertEqual(r['unsupported'], ['P1'])
        self.assertEqual(r['pins'][0]['carriers'], ['RAIL1'])
        self.assertIn('stand pad PAD on 2 plates', r['next_action'])

    def test_no_pins_is_unknown(self):
        self.assertEqual(pin_clearance.audit({'plates': []}, {'PAD': PAD})['status'], 'unknown')


class PinClearanceConceptTests(unittest.TestCase):
    def concept(self, pin):
        from export_step import read_step, write_step
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); path = Path(tmp.name)
        shutil.copytree(ROOT / 'examples/flat-plate', path / 'input'); spec_path = path / 'input/spec.json'
        step = path / 'input/workpiece.step'
        write_step(step, {**read_step(step), 'REF_PIN_P1': pin})
        spec = json.loads(spec_path.read_text())
        spec['pin_locators'] = [{'id': 'P1', 'shape_name': 'REF_PIN_P1', 'mode': 'fixed', 'orientation_sensitive': False}]
        spec_path.write_text(json.dumps(spec))
        return preview.generate(spec_path, path / 'out', render=False)

    def test_clear_pin_on_base_passes(self):
        r = self.concept(box(-130, 100, 0, -124, 106, 12))
        self.assertEqual(r['checks']['pin_clearance'], 'pass'); self.assertEqual(r['blocking'], [])

    def test_pin_beside_clamp_cheek_blocks_concept(self):
        r = self.concept(box(-32, 110, 0, -27, 115, 12))
        self.assertIsNone(r['html'])
        self.assertEqual([b['items'] for b in r['blocking'] if b['check'] == 'pin_clearance'], [['P1~K1 2.5mm']])


if __name__ == '__main__': unittest.main()
