"""Flange coverage, brace commonising, tab/slot diagnostics and geometry-only source rebase."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import brace_merge
import cap_joints
import tabs_slots
import workflow as wf
from export_step import read_step, write_step
from fixture_common import load_spec
from flange_coverage import audit as coverage


class FlangeCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_spec(ROOT / 'examples/checking-rib/spec.json')
        cls.shapes = read_step(ROOT / 'examples/checking-rib/workpiece.step')

    def test_example_feature_is_covered(self):
        r = coverage(self.spec, self.shapes)
        self.assertEqual(r['status'], 'pass'); self.assertEqual(r['uncovered'], [])
        self.assertTrue(all(f['covered_by'] for f in r['features']))

    def test_uncovered_feature_fails_with_proposal_and_waiver_needs_reason(self):
        s = copy.deepcopy(self.spec); s['inspection']['flanges'] = []; s['contacts'] = []
        r = coverage(s, self.shapes)
        self.assertEqual(r['status'], 'fail'); self.assertTrue(r['uncovered'])
        self.assertTrue(all(f['proposal']['stations'] for f in r['features'] if f['status'] == 'fail'))
        s['inspection']['flange_waivers'] = [{'point_mm': r['features'][0]['outer_point_mm'], 'reason': ' '}]
        with self.assertRaises(ValueError): coverage(s, self.shapes)

    def test_unchecked_narrow_feature_is_unknown_not_dropped(self):
        s = copy.deepcopy(self.spec); s['inspection']['flanges'] = []; s['contacts'] = []
        with patch('flange_features.MIN_WIDTH_MM', 1e6):  # every feature counts as narrow
            r = coverage(s, self.shapes)
        self.assertEqual(r['status'], 'unknown'); self.assertEqual(r['uncovered'], [])
        self.assertTrue(r['unchecked_narrow']); self.assertIn('Narrow features', r['next_action'])

    def test_station_off_part_fails(self):
        s = copy.deepcopy(self.spec)
        s['inspection']['flanges'][0]['checks'].append({'id': 'AIR', 'kind': 'surface_gap', 'point_mm': [0, 0, 70]})
        r = coverage(s, self.shapes)
        self.assertEqual(r['status'], 'fail'); self.assertEqual([o['station'] for o in r['stations_off_part']], ['AIR'])

    def test_weld_is_not_applicable(self):
        s = copy.deepcopy(self.spec); s.pop('inspection')
        self.assertEqual(coverage(s, self.shapes)['status'], 'not_applicable')


class BraceMergeTests(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(ROOT / 'examples/flat-plate/spec.json')
        cap_joints.design(self.spec, lambda *a: None)
        self.by = {d['name']: d for d in self.spec['plates']}

    def test_example_twin_is_an_exception_not_a_pass(self):
        r = brace_merge.audit(self.spec)
        self.assertEqual(r['status'], 'unknown'); self.assertEqual([(p['a'], p['b']) for p in r['pairs']], [('X1', 'X2')])

    def test_close_parallel_braces_must_merge(self):
        self.by['X1'].pop('brace_merge_exception')
        r = brace_merge.audit(self.spec)
        self.assertEqual(r['status'], 'fail'); self.assertIn('X1+X2', r['next_action'])
        self.assertEqual(r['pairs'][0]['plane_offset_mm'], 24.0)

    def test_braces_50mm_apart_pass_and_cheeks_are_exempt(self):
        self.by['X1'].pop('brace_merge_exception'); self.by['X1']['origin'][0] = -38.0
        self.assertEqual(brace_merge.audit(self.spec)['status'], 'pass')
        self.assertNotIn('K1', [d['name'] for d in brace_merge.candidates(self.spec)])


class TabSlotDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(ROOT / 'examples/flat-plate/spec.json')

    def test_short_lap_under_foot_height_is_named(self):
        for j in self.spec['joints']:
            if 'lap_height_mm' in j: j['lap_height_mm'] = 10.0
        with self.assertRaisesRegex(ValueError, 'feet would fill the slot.*>= 24'):
            tabs_slots.design(self.spec, lambda *a: None)

    def test_no_tab_options_says_why(self):
        self.spec['tab_slot'] = {'min_bridge_mm': 400}
        with self.assertRaisesRegex(ValueError, 'no two-tab options for .*too close to the seat edge.*grow the seat'):
            tabs_slots.design(self.spec, lambda *a: None)

    def test_pinned_cap_tab_names_nearest_feasible(self):
        self.spec['cap_joints'] = {'pinned': {'P_T1': [['K1', 60.0, 72.0], ['K2', 99.0, 111.0]]}}
        r = cap_joints.design(self.spec, lambda *a: None)
        self.assertEqual(r['status'], 'fail'); self.assertIn('nearest feasible K1 tab is', r['caps'][0]['reason'])


class SourceRebaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        shutil.copytree(ROOT / 'examples/flat-plate', Path(self.tmp.name) / 'in')
        self.spec = Path(self.tmp.name) / 'in/spec.json'
        self.step = Path(self.tmp.name) / 'in/workpiece.step'
        self.record = wf.initialize(self.spec, 'weld', 'laser_rib')
        self.record['datum_review'] = {'note': 'ok', 'datum_digest': self.record['datum_digest']}
        wf.resume(self.spec, self.record)
        self.assertIn('source_geometry', self.record)

    def test_reexport_with_same_geometry_keeps_review(self):
        write_step(self.step, read_step(self.step))
        wf.resume(self.spec, self.record)
        self.assertTrue(wf.datum_reviewed(self.record))
        self.assertIn('rebased_sources', self.record['history'][-1])

    def test_reexport_rebases_a_record_with_an_old_string_fingerprint(self):
        self.record['source_geometry'] = {p: v[0] for p, v in self.record['source_geometry'].items()}
        write_step(self.step, read_step(self.step))
        wf.resume(self.spec, self.record)
        self.assertTrue(wf.datum_reviewed(self.record))
        self.assertIn('rebased_sources', self.record['history'][-1])

    def test_changed_geometry_still_needs_survey(self):
        shapes = read_step(self.step); shapes['EXTRA'] = next(iter(shapes.values()))
        write_step(self.step, shapes)
        with self.assertRaisesRegex(ValueError, 'fresh survey'): wf.resume(self.spec, self.record)

    def pin(self, top):
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt
        write_step(self.step, {**read_step(self.step),
                               'REF_PIN_P1': BRepPrimAPI_MakeBox(gp_Pnt(-130, 100, 0), gp_Pnt(-124, 106, top)).Shape()})

    def edit(self, **changes):
        data = json.loads(self.spec.read_text()); data.update(changes)
        self.spec.write_text(json.dumps(data)); return data

    def pinned_record(self):
        self.pin(12)
        record = wf.initialize(self.spec, 'weld', 'laser_rib')
        record['datum_review'] = {'note': 'ok', 'datum_digest': record['datum_digest']}
        wf.resume(self.spec, record)
        return record

    def test_a_longer_pin_in_the_surveyed_step_keeps_the_datum_review(self):
        record = self.pinned_record()
        self.pin(20); self.edit(revision='R2')
        record = wf.checkpoint(self.spec, record)
        self.assertTrue(wf.datum_reviewed(record))
        self.assertIn(wf.REBASE_REASONS[1], [h.get('reason') for h in record['history']])

    def test_a_pin_change_beside_a_workpiece_change_still_needs_survey(self):
        record = self.pinned_record()
        self.pin(20)
        shapes = read_step(self.step); shapes['EXTRA'] = next(iter(shapes.values()))
        write_step(self.step, shapes); self.edit(revision='R2')
        with self.assertRaisesRegex(ValueError, 'fresh survey'): wf.checkpoint(self.spec, record)

    def test_a_moved_datum_beside_a_longer_pin_still_stales_the_review(self):
        record = self.pinned_record()
        self.pin(20)
        data = json.loads(self.spec.read_text())
        data['contacts'][0]['contact'] = [-45.0, -30.0, 60.0]
        data['revision'] = 'R2'
        self.spec.write_text(json.dumps(data))
        record = wf.checkpoint(self.spec, record)
        self.assertFalse(wf.datum_reviewed(record))


if __name__ == '__main__':
    unittest.main()
