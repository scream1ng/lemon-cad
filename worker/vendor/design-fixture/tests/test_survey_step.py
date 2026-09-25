"""Kernel-backed STEP survey checks, all generated STEP files live in temp dirs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.gp import gp_Trsf, gp_Vec, gp_Pnt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from survey_step import survey, rigid_transform, read_occurrences, bbox, write_placed_step


def translation(x, y, z):
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(x, y, z))
    return TopLoc_Location(t)


def named(label, name):
    TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
    return label


def duplicate_assembly(path, coincident=False):
    doc = TDocStd_Document(TCollection_ExtendedString('test'))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    body = named(st.AddShape(BRepPrimAPI_MakeBox(10, 20, 3).Shape(), False), 'Same product')
    nested = named(st.NewShape(), 'Same assembly')
    named(st.AddComponent(nested, body, translation(2, 3, 4)), 'Same occurrence')
    named(st.AddComponent(nested, body, translation(2 if coincident else 32, 3, 4)), 'Same occurrence')
    root = named(st.NewShape(), 'Root')
    named(st.AddComponent(root, nested, translation(100, 200, 300)), 'Nested occurrence')
    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    assert writer.Transfer(doc, STEPControl_AsIs)
    assert writer.Write(str(path)) == IFSelect_RetDone


class SurveyTests(unittest.TestCase):
    def test_duplicate_nested_names_keep_each_placement_and_roundtrip_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / 'input.step'
            duplicate_assembly(src)
            data = survey(src, tmp / 'out')
            self.assertEqual(data['body_count'], 2)
            self.assertEqual(data['source']['sha256'], hashlib.sha256(src.read_bytes()).hexdigest())
            self.assertEqual(data['source']['length_units_detected'], ['millimetre'])
            self.assertEqual([b['name'] for b in data['bodies']], ['Part_0001', 'Part_0002'])
            first, second = data['bodies']
            self.assertEqual(first['occurrence_path'], second['occurrence_path'])
            self.assertNotEqual(first['occurrence_index_path'], second['occurrence_index_path'])
            np.testing.assert_allclose(first['bbox_mm']['min'], [102, 203, 304], atol=1e-7)
            np.testing.assert_allclose(second['bbox_mm']['min'], [132, 203, 304], atol=1e-7)
            for body in data['bodies']:
                self.assertAlmostEqual(body['volume_mm3'], 600)
                self.assertEqual(len(body['faces']), 6)
                self.assertTrue(all(f['type'] == 'Plane' and f['boundaries'] for f in body['faces']))
                self.assertTrue(all(f['status'] == 'unverified' for f in body['feature_candidates']))
            leaves, _ = read_occurrences(tmp / 'out' / 'placed.step')
            self.assertEqual([meta['product_name'] for _, meta in leaves], ['Part_0001', 'Part_0002'])
            np.testing.assert_allclose(bbox(leaves[1][0])['min'], [132, 203, 304], atol=1e-7)

    def test_rotated_and_translated_fixture_frame_is_applied_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            duplicate_assembly(tmp / 'input.step')
            matrix = [[0, -1, 0, 7], [1, 0, 0, -9], [0, 0, 1, 11], [0, 0, 0, 1]]
            data = survey(tmp / 'input.step', tmp / 'out', matrix)
            self.assertEqual(data['source_to_fixture'], matrix)
            np.testing.assert_allclose(data['bodies'][0]['bbox_mm']['min'], [-216, 93, 315], atol=1e-7)
            np.testing.assert_allclose(data['bodies'][0]['bbox_mm']['size'], [20, 10, 3], atol=1e-7)
            leaves, _ = read_occurrences(tmp / 'out' / 'placed.step')
            np.testing.assert_allclose(bbox(leaves[1][0])['min'], [-216, 123, 315], atol=1e-7)
            self.assertAlmostEqual(data['bodies'][0]['volume_mm3'], 600)

    def test_coincident_instances_are_not_deduplicated_on_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            duplicate_assembly(tmp / 'input.step', coincident=True)
            data = survey(tmp / 'input.step', tmp / 'out')
            self.assertEqual(data['body_count'], 2)
            leaves, _ = read_occurrences(tmp / 'out' / 'placed.step')
            self.assertEqual([m['product_name'] for _, m in leaves], ['Part_0001', 'Part_0002'])

    def test_hole_evidence_and_cli_transform(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            plate = BRepPrimAPI_MakeBox(gp_Pnt(-10, -10, 0), 20, 20, 3).Shape()
            hole = BRepPrimAPI_MakeCylinder(2, 3).Shape()
            cut = BRepAlgoAPI_Cut(plate, hole).Shape()
            write_placed_step(tmp / 'hole.step', [('drilled', cut)])
            transform = np.eye(4)
            transform[:3, 3] = [11, 13, 17]
            (tmp / 'transform.json').write_text(json.dumps({'source_to_fixture': transform.tolist()}))
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/survey_step.py'),
                                     str(tmp / 'hole.step'), str(tmp / 'out'), '--transform',
                                     str(tmp / 'transform.json')], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((tmp / 'out/survey.json').read_text())
            body = data['bodies'][0]
            cyl = [f for f in body['faces'] if f['type'] == 'Cylinder']
            self.assertEqual(len(cyl), 1)
            self.assertAlmostEqual(cyl[0]['radius_mm'], 2)
            np.testing.assert_allclose(cyl[0]['axis_origin_mm'][:2], [11, 13])
            self.assertEqual(len([f for f in body['faces'] if f.get('boundaries') and
                                 len(f['boundaries']) == 2]), 2)
            self.assertAlmostEqual(body['volume_mm3'], (400 - np.pi * 4) * 3)

    def test_inch_source_is_normalized_to_mm(self):
        from OCP.Interface import Interface_Static
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # Create native inch coordinates (1 x 2 x 0.1); the STEP declares inches.
            STEPCAFControl_Writer()  # initializes translator parameters
            previous = Interface_Static.CVal_s('write.step.unit')
            try:
                self.assertTrue(Interface_Static.SetCVal_s('write.step.unit', 'INCH'))
                from OCP.STEPControl import STEPControl_Writer
                writer = STEPControl_Writer()
                self.assertEqual(writer.Transfer(BRepPrimAPI_MakeBox(1, 2, 0.1).Shape(), STEPControl_AsIs), IFSelect_RetDone)
                self.assertEqual(writer.Write(str(tmp / 'inch.step')), IFSelect_RetDone)
            finally:
                Interface_Static.SetCVal_s('write.step.unit', previous)
            data = survey(tmp / 'inch.step', tmp / 'out')
            self.assertTrue(any('inch' in u.lower() for u in data['source']['length_units_detected']))
            np.testing.assert_allclose(data['bodies'][0]['bbox_mm']['size'], [25.4, 50.8, 2.54], atol=1e-7)
            leaves, units = read_occurrences(tmp / 'out/placed.step')
            self.assertEqual(units, ['millimetre'])
            np.testing.assert_allclose(bbox(leaves[0][0])['size'], [25.4, 50.8, 2.54], atol=1e-7)

    def test_nonrigid_transform_is_rejected(self):
        for matrix in (np.diag([2, 1, 1, 1]), np.diag([-1, 1, 1, 1]), np.eye(3),
                       [[1, 0, 0, float('nan')], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]):
            with self.assertRaises(ValueError):
                rigid_transform(matrix)


if __name__ == '__main__':
    unittest.main()
