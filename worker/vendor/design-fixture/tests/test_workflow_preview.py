"""Unified routing, resumability, authorization and exact-geometry preview regression."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import workflow as wf
from preview import generate, compact_mesh, inline_html, INLINE_HTML_TARGET, INLINE_HTML_LIMIT
from export_step import read_step

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        shutil.copytree(ROOT / 'examples/flat-plate', self.path / 'input')
        self.spec = self.path / 'input/spec.json'

    def edit(self, **changes):
        data = json.loads(self.spec.read_text()); data.update(changes)
        self.spec.write_text(json.dumps(data)); return data

    def test_routing_and_complete_matrix(self):
        self.assertEqual(wf.route()['question'], 'Weld fixture or Check fixture?')
        for kind in ('weld', 'checking'):
            self.assertEqual(wf.route(kind)['construction'], 'laser_rib')
        for kind, mode in [('weld', 'laser_rib'), ('weld', 'block'), ('checking', 'laser_rib'), ('checking', 'printed_solid')]:
            self.assertFalse(wf.route(kind, mode)['concept_only'])
        for kind, mode in [('weld', 'printed_solid'), ('checking', 'block')]:
            with self.assertRaises(ValueError): wf.route(kind, mode)
            self.assertTrue(wf.route(kind, mode, 'User explicitly requested concept study')['concept_only'])

    def test_gate_and_initial_complete_request(self):
        record = wf.initialize(self.spec, 'weld')
        with self.assertRaises(ValueError): wf.finalization_allowed(self.spec, record)
        with self.assertRaises(ValueError): wf.authorize(record, 'Finalize')
        record['stage'] = 'preview'; wf.authorize(record, 'Finalize the package')
        wf.finalization_allowed(self.spec, record)
        self.assertFalse(any(record['readiness'].values()))
        early = wf.initialize(self.spec, 'weld', complete_request='Create a complete review package')
        with self.assertRaises(ValueError): wf.finalization_allowed(self.spec, early)
        early['stage'] = 'preview'; wf.finalization_allowed(self.spec, early)

    def test_spec_revision_invalidates_authorization(self):
        record = wf.initialize(self.spec, 'weld'); record['stage'] = 'preview'; wf.authorize(record, 'Finalize')
        self.edit(decisions=['Revise clamp platform'])
        with self.assertRaises(ValueError): wf.resume(self.spec, record)
        with self.assertRaises(ValueError): wf.checkpoint(self.spec, record)
        self.edit(revision='R2'); fresh = wf.checkpoint(self.spec, record)
        self.assertIsNone(fresh['authorization']); self.assertEqual(fresh['stage'], 'concept')
        self.assertEqual(record['component_ids'], fresh['component_ids'])

    def test_checkpoint_keeps_datum_review_only_while_datums_unchanged(self):
        record = wf.initialize(self.spec, 'weld')
        record['datum_review'] = {'note': 'ok', 'datum_digest': record['datum_digest']}
        self.edit(revision='R2', decisions=['Merge braces']); fresh = wf.checkpoint(self.spec, record)
        self.assertTrue(wf.datum_reviewed(fresh))
        data = json.loads(self.spec.read_text()); data['contacts'][0]['contact'][0] += 1.0
        self.edit(revision='R3', contacts=data['contacts'])
        self.assertFalse(wf.datum_reviewed(wf.checkpoint(self.spec, fresh)))

    def test_source_hash_units_and_version(self):
        record = wf.initialize(self.spec, 'weld')
        original = Path(record['sources'][0]['path']); original.write_bytes(original.read_bytes() + b'\n')
        self.edit(revision='R2')
        with self.assertRaises(ValueError): wf.resume(self.spec, record)
        with self.assertRaises(ValueError): wf.checkpoint(self.spec, record)
        fresh = wf.checkpoint(self.spec, record, resurveyed=True)
        self.assertNotEqual(record['sources'][0]['sha256'], fresh['sources'][0]['sha256'])
        path = self.path / 'project.json'; wf.save(path, fresh); wf.read_record(path)
        fresh['schema_version'] = 'future-version'; wf.save(path, fresh)
        with self.assertRaises(ValueError): wf.read_record(path)
        self.edit(units='inch')
        with self.assertRaises(ValueError): wf.snapshot(self.spec)

    def test_rebuilt_finished_body_is_not_a_resurvey(self):
        body = self.path / 'input/body.step'; body.write_text('body v1\n')
        self.edit(printed_bodies=[{'name': 'Printed_Nest', 'finished_step': 'body.step'}])
        record = wf.initialize(self.spec, 'weld')
        record['datum_review'] = {'note': 'ok', 'datum_digest': record['datum_digest']}
        record['stage'] = 'preview'; wf.authorize(record, 'Finalize')
        body.write_text('body v2\n')
        with self.assertRaises(ValueError): wf.resume(self.spec, record)      # authorized package goes stale
        self.edit(revision='R2'); fresh = wf.checkpoint(self.spec, record)     # no --resurveyed needed
        self.assertTrue(wf.datum_reviewed(fresh)); self.assertIsNone(fresh['authorization'])
        self.assertNotEqual(record['input_digest'], fresh['input_digest'])

    def test_init_prints_summary_and_preserves_full_record(self):
        import io, contextlib
        path = self.path / 'project.json'
        buf = io.StringIO()
        argv = ['workflow.py', 'init', str(self.spec), str(path), '--kind', 'weld']
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(buf):
            wf.main()
        self.assertEqual(buf.getvalue(), f'R1 ok stage=concept record={path}\n')
        record = wf.read_record(path)
        self.assertEqual(record['fixture_kind'], 'weld')
        self.assertIsNone(record['authorization'])
        self.assertFalse(any(record['readiness'].values()))

    def test_record_actions_print_one_line(self):
        import io, contextlib
        record = wf.initialize(self.spec, 'weld'); record['stage'] = 'preview'
        wf.save(self.path / 'project.json', record)
        def run(*args):
            buf = io.StringIO()
            with patch.object(sys, 'argv', ['workflow.py', *args, str(self.spec), str(self.path / 'project.json')]), \
                    contextlib.redirect_stdout(buf):
                wf.main()
            return buf.getvalue().strip()
        self.assertEqual(run('resume'), 'R1 ok stage=preview datum_reviewed=False authorized=False open_items=0')
        line = run('authorize', '--request', 'Finalize')
        self.assertNotIn('\n', line); self.assertIn('not engineering approval', line)
        self.assertTrue(wf.read_record(self.path / 'project.json')['authorization'])

    def test_revise_one_line_and_stops_on_failed_verify(self):
        import io, contextlib
        record = wf.initialize(self.spec, 'weld')
        record['datum_review'] = {'note': 'ok', 'datum_digest': record['datum_digest']}
        wf.save(self.path / 'project.json', record)
        ok = {'blocking': [], 'checks': {'unload': 'unknown'}, 'html': 'p.html', 'bytes': 1}
        py = f'"{sys.executable}" -c'
        def revise(rev, verify):
            self.edit(revision=rev)
            argv = ['workflow.py', 'revise', str(self.spec), str(self.path / 'project.json'), str(self.path / 'out'),
                    '--build', f"{py} \"print('noise'); print('built')\"", '--verify', f'{py} "{verify}"']
            buf = io.StringIO()
            with patch('preview.generate', return_value=ok), patch.object(sys, 'argv', argv), contextlib.redirect_stdout(buf):
                wf.main()
            return buf.getvalue().strip()
        self.assertEqual(revise('R2', "print('pass')"),
                         'R2 ok | build: built | concept: blocking=[] unload=unknown html=p.html bytes=1 | verify: pass')
        self.assertIn('noise', (self.path / 'out/revise.log').read_text())
        with self.assertRaisesRegex(ValueError, 'verify failed.*FAIL x'):
            revise('R3', "import sys; print('FAIL x'); sys.exit(1)")

    def test_evidence_not_circular_geometry_digest(self):
        _, before = wf.snapshot(self.spec)
        self.edit(checking_evidence=[{'name': 'test', 'status': 'unknown'}]); _, after = wf.snapshot(self.spec)
        self.assertEqual(before['geometry_digest'], after['geometry_digest'])
        self.assertNotEqual(before['input_digest'], after['input_digest'])

    def test_resource_lookup(self):
        from hardware_geometry import asset_path, definition
        from records import sha256
        self.assertEqual(sha256(asset_path('GH-201-B')), definition('GH-201-B')['asset']['sha256'])
        self.assertTrue(wf.resource('assets/preview.html').is_file())
        with self.assertRaises(ValueError): wf.resource('../escape')

    def test_concept_only_exception_never_finalizes(self):
        record = wf.initialize(self.spec, 'weld', 'printed_solid', 'User requested concept-only exception')
        record['stage'] = 'preview'
        with self.assertRaises(ValueError): wf.authorize(record, 'Finalize')

    def test_no_package_during_preview_and_exact_spec_identity(self):
        out = self.path / 'preview'
        with patch('build.build', side_effect=AssertionError('Manufacturing build called')):
            result = generate(self.spec, out, render=False)
        self.assertFalse((out / 'DELIVERY').exists()); self.assertFalse(list(out.glob('*.dxf')))
        scene = json.loads((out / 'scene.json').read_text())
        evaluated = json.loads((out / 'evaluated-spec.json').read_text())
        self.assertEqual(scene['evaluated_spec_sha256'], wf.digest(evaluated))
        ids = {c['id'] for c in scene['components']}
        step_ids = set(read_step(out / 'concept.step'))
        self.assertEqual(ids - {'HW_T1'}, {n for n in step_ids if not n.startswith('HW_T1_')})
        self.assertIn('HW_T1', ids)  # one coarse clamp mesh; the full mechanism stays in concept.step
        self.assertEqual(result['components'], len(ids))
        self.assertEqual(result['blocking'], [])
        self.assertEqual(set(result['checks']), {'cap_joints', 'material_width', 'cross_support', 'mount_compactness', 'unload', 'pin_clearance',
                                                    'flange_coverage', 'brace_merge', 'checking_geometry'})
        self.assertEqual(result['checks']['unload'], 'unknown')
        self.assertTrue(result['soft_target_met'])
        self.assertLessEqual(result['bytes'], INLINE_HTML_TARGET)
        html = (out / 'preview.html').read_text()
        self.assertNotIn('__SCENE_GZIP_BASE64__', html)
        self.assertIn('DecompressionStream', html)
        self.assertNotIn('assembled.png', html)
        self.assertEqual(Path(result['private_dir']), out.resolve())

    def test_inline_html_is_deterministic_and_strictly_budgeted(self):
        scene = {'schema_version': 'fixture-preview-1', 'components': [], 'authoritative': False}
        first, first_size = inline_html(scene)
        second, second_size = inline_html(scene)
        self.assertEqual(first, second)
        self.assertEqual(first_size, second_size)
        self.assertLess(first_size, INLINE_HTML_LIMIT)
        oversized = self.path / 'oversized-preview.html'
        oversized.write_text('__SCENE_GZIP_BASE64__' + 'x' * INLINE_HTML_LIMIT)
        with patch('preview.resource', return_value=oversized), self.assertRaisesRegex(ValueError, 'strictly below'):
            inline_html(scene)

    def test_checking_and_block_previews(self):
        for mode, construction in [('checking-rib', 'laser_rib'), ('checking-printed', 'printed_solid')]:
            record = wf.initialize(ROOT / 'examples' / mode / 'spec.json', 'checking', construction)
            self.assertEqual(record['construction'], construction)
            if mode == 'checking-rib': self.assertIn('CHECK_RIB', record['component_ids'])
            result = generate(ROOT / 'examples' / mode / 'spec.json', self.path / mode, 'checking', construction, render=False)
            self.assertGreater(result['components'], 0); self.assertEqual(result['blocking'], [])
        data = json.loads((ROOT / 'examples/checking-printed/spec.json').read_text())
        data['workpiece']['placed_step'] = str(ROOT / 'examples/checking-printed/workpiece.step')
        data['block_bodies'] = data.pop('printed_bodies'); data.pop('inspection'); data['clamps'] = []
        path = self.path / 'block.json'; path.write_text(json.dumps(data))
        result = generate(path, self.path / 'block', 'weld', 'block', render=False)
        scene = json.loads((self.path / 'block/scene.json').read_text())
        self.assertIn('BODY_MAIN', {c['id'] for c in scene['components']})

    def test_unauthorized_concept_loop_drifts_without_losing_retirement(self):
        record = wf.initialize(self.spec, 'weld')
        data = self.edit(decisions=['Taller clamp platform'])
        wf.resume(self.spec, record)
        self.assertEqual(record['decisions'], ['Taller clamp platform'])
        dropped = data['plates'].pop()['name']
        self.edit(plates=data['plates'])
        wf.resume(self.spec, record)
        self.assertNotIn(dropped, record['component_ids'])
        self.edit(revision='R2')
        fresh = wf.checkpoint(self.spec, record)
        self.assertIn(dropped, fresh['retired_ids'])
        record['authorization'] = {'input_digest': record['input_digest']}
        self.edit(decisions=['Another change'])
        with self.assertRaises(ValueError): wf.resume(self.spec, record)

    def test_block_finalization_is_recorded_as_a_manual_handoff(self):
        record = wf.initialize(self.spec, 'weld', 'block')
        record['stage'] = 'preview'; wf.authorize(record, 'Finalize the package')
        result = wf.finalize(self.spec, record, self.path / 'block')
        self.assertEqual(result['status'], 'manual_block_finalization_required')
        handoff = [h for h in record['history'] if h.get('event') == 'manual_block_finalization_required']
        self.assertEqual(len(handoff), 1)
        self.assertEqual(handoff[0]['input_digest'], record['input_digest'])
        wf.finalize(self.spec, record, self.path / 'block')
        self.assertEqual(len([h for h in record['history'] if h.get('event')]), 1)
        self.assertEqual(record['stage'], 'preview')

    def test_mesh_is_indexed_finite_nonempty(self):
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
        from render_review import triangles
        mesh = compact_mesh(triangles(BRepPrimAPI_MakeSphere(100).Shape()), target=100)
        self.assertGreater(mesh['preview_triangles'], 0)
        self.assertLessEqual(mesh['preview_triangles'], mesh['source_triangles'])
        self.assertTrue(np.isfinite(mesh['positions']).all())
        self.assertLess(max(mesh['indices']), len(mesh['positions']) // 3)

if __name__ == '__main__': unittest.main()
