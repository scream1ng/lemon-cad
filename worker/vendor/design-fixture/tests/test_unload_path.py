"""Straight unload screen from the master part's primary datum, and the concept gate on blockers."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
import unload_path
import preview
import workflow as wf


def box(x0, y0, z0, x1, y1, z1):
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), gp_Pnt(x1, y1, z1)).Shape()


SPEC = {'workpiece': {'parts': {'Plate': 'Part_Plate'}}, 'assembly_locating': {'master_part': 'Plate'},
        'contacts': [{'part': 'Plate', 'role': 'Primary', 'normal': [0, 0, 1], 'constraint_role': 'fixed_datum'}]}
PART = box(0, 0, 10, 100, 60, 13)
SEAT = box(0, 0, 0, 100, 60, 10)


class UnloadTests(unittest.TestCase):
    def test_clear_lift_stays_unknown(self):
        r = unload_path.audit(SPEC, {'Part_Plate': PART, 'BASE': SEAT, 'STOP': box(-5, 0, 0, 0, 60, 20)})
        self.assertEqual(r['status'], 'unknown'); self.assertEqual(r['collisions'], [])
        self.assertEqual(r['direction'], [0.0, 0.0, 1.0])

    def test_rib_over_the_part_fails(self):
        r = unload_path.audit(SPEC, {'Part_Plate': PART, 'BASE': SEAT, 'R9': box(40, 0, 20, 45, 60, 40)})
        self.assertEqual(r['status'], 'fail')
        self.assertEqual([c['obstacle'] for c in r['collisions']], ['R9'])
        self.assertIn('R9', r['next_action'])

    def test_open_clamps_and_withdrawn_pins_are_ignored(self):
        spec = {**SPEC, 'pin_locators': [{'id': 'P1', 'shape_name': 'REF_PIN_P1', 'mode': 'removable'},
                                         {'id': 'P2', 'shape_name': 'REF_PIN_P2', 'mode': 'fixed'}]}
        over = box(40, 20, 20, 50, 30, 40)
        r = unload_path.audit(spec, {'Part_Plate': PART, 'BASE': SEAT, 'HW_T1_arm': over, 'REF_PIN_P1': over})
        self.assertEqual(r['status'], 'unknown')
        r = unload_path.audit(spec, {'Part_Plate': PART, 'BASE': SEAT, 'REF_PIN_P2': over})
        self.assertEqual([c['obstacle'] for c in r['collisions']], ['REF_PIN_P2'])

    def test_direction_follows_primary_datum_of_master(self):
        spec = {**SPEC, 'contacts': [{'part': 'Plate', 'role': 'Primary', 'normal': [0, 1, 0]}]}
        r = unload_path.audit(spec, {'Part_Plate': PART, 'BASE': SEAT, 'WALL': box(0, 70, 10, 100, 75, 13)})
        self.assertEqual(r['direction'], [0.0, 1.0, 0.0]); self.assertEqual(r['status'], 'fail')

    def test_no_primary_datum_is_unknown(self):
        r = unload_path.audit({**SPEC, 'contacts': []}, {'Part_Plate': PART, 'BASE': SEAT})
        self.assertEqual(r['status'], 'unknown'); self.assertIsNone(r['direction'])


class ConceptGateTests(unittest.TestCase):
    def test_blockers_list_failing_checks_only(self):
        audit = {'cross_support': {'status': 'fail', 'plates': [{'plate': 'R1', 'status': 'fail'}], 'bad_joints': [],
                                   'next_action': 'Add a cross member'},
                 'unload': {'status': 'unknown', 'collisions': []}}
        self.assertEqual(preview.blockers(audit), [{'check': 'cross_support', 'items': ['R1'], 'next_action': 'Add a cross member'}])

    def test_concept_stops_and_keeps_stage_on_blocker(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); path = Path(tmp.name)
        shutil.copytree(ROOT / 'examples/flat-plate', path / 'input'); spec = path / 'input/spec.json'
        record = wf.initialize(spec, 'weld'); record['datum_digest'] = 'd'
        record['datum_review'] = {'datum_digest': 'd'}; wf.save(path / 'project.json', record)
        blocked = {'blocking': [{'check': 'unload', 'items': ['R9'], 'next_action': 'move R9'}]}
        argv = ['workflow.py', 'concept', str(spec), str(path / 'project.json'), str(path / 'out')]
        with patch('preview.generate', return_value=blocked), patch.object(sys, 'argv', argv):
            with self.assertRaisesRegex(ValueError, 'no preview until fixed.*R9'): wf.main()
        self.assertNotEqual(wf.read_record(path / 'project.json')['stage'], 'preview')

    def test_real_geometry_blockers_write_no_preview(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); path = Path(tmp.name)
        shutil.copytree(ROOT / 'examples/flat-plate', path / 'input'); spec_path = path / 'input/spec.json'
        out = path / 'out'; out.mkdir(); (out / 'preview.html').write_text('stale')
        spec = json.loads(spec_path.read_text())
        rib = next(p for p in spec['plates'] if p['name'] == 'R1')
        # an unseated copy of R1 lifted over the part blocks the straight unload
        over = {**rib, 'name': 'R9', 'part_number': 'R9', 'origin': [rib['origin'][0], rib['origin'][1], rib['origin'][2] + 70]}
        over.pop('seat', None); over['contacts'] = []
        spec['plates'].append(over)
        spec_path.write_text(json.dumps(spec))
        result = preview.generate(spec_path, out, render=False)
        self.assertIsNone(result['html']); self.assertFalse((out / 'preview.html').exists())
        self.assertIn('R9', [i for b in result['blocking'] if b['check'] == 'unload' for i in b['items']])
        self.assertTrue((out / 'audit.json').is_file())


if __name__ == '__main__': unittest.main()
