import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from printed_body import build_shapes, export_meshes, inspect_mesh, _mesh_topology, _read_stl


class PrintedBodyTests(unittest.TestCase):
    def spec(self):
        return {'printed_bodies':[{'name':'body', 'stock':{'origin':[0,0,0], 'size':[20,20,10]}}]}

    def test_bore_relief_and_connected_addition(self):
        spec = self.spec()
        body = spec['printed_bodies'][0]
        body['add'] = [{'type':'box', 'origin':[18,0,0], 'size':[4,20,10]}]
        body['subtract'] = [
            {'type':'cylinder', 'origin':[10,10,-1], 'axis':[0,0,1], 'radius_mm':2, 'depth_mm':12},
            {'type':'box', 'origin':[-1,-1,-1], 'size':[3,3,12]}]
        shapes, report = build_shapes(spec)
        self.assertEqual(list(shapes), ['body'])
        self.assertAlmostEqual(report['bodies'][0]['volume_mm3'], 4400-40-math.pi*4*10, places=6)
        self.assertEqual(report['bodies'][0]['bounds_mm'], [0,0,0,22,20,10])

    def test_offset_land_measured_by_kernel(self):
        spec = self.spec()
        spec['printed_bodies'][0]['subtract'] = [{'type':'offset_pocket', 'point':[10,10,0], 'normal':[0,0,1], 'u':[1,0,0], 'width_mm':12, 'height_mm':12, 'depth_mm':4}]
        shapes, report = build_shapes(spec)
        distance = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(10,10,0)).Shape(), shapes['body'])
        distance.Perform()
        self.assertTrue(distance.IsDone())
        self.assertAlmostEqual(distance.Value(), 3, places=7)
        self.assertAlmostEqual(report['bodies'][0]['volume_mm3'], 4000-12*12*3, places=6)
        # A second orientation ensures the gap isn't hardcoded to world Z.
        spec['printed_bodies'][0]['subtract'][0].update(point=[0,10,5], normal=[1,0,0], u=[0,1,0], width_mm=12, height_mm=6)
        shapes, _ = build_shapes(spec)
        distance = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(0,10,5)).Shape(), shapes['body'])
        distance.Perform()
        self.assertAlmostEqual(distance.Value(), 3, places=7)

    def test_stl_reopened_manifold_and_dimensions(self):
        spec = self.spec()
        spec['printed_bodies'][0]['subtract'] = [{'type':'cylinder','origin':[10,10,-1],'axis':[0,0,1],'radius_mm':3,'depth_mm':12}]
        shapes, _ = build_shapes(spec)
        with tempfile.TemporaryDirectory() as folder:
            result = export_meshes(shapes, folder, 0.03)['meshes'][0]
            self.assertTrue(result['closed_manifold'])
            self.assertTrue(result['consistent_winding'])
            self.assertLessEqual(result['max_bounds_error_mm'], 0.03)
            self.assertGreater(result['max_sampled_surface_distance_mm'], 0)
            self.assertLessEqual(result['max_sampled_surface_distance_mm'], 0.03)
            checked = inspect_mesh(result['file'], shapes['body'], 0.03, 'body')
            self.assertEqual(checked['filename'], 'body.stl')
            self.assertEqual(checked['source_body'], 'body')
            other_spec = self.spec()
            other_spec['printed_bodies'][0]['stock']['origin'] = [1,0,0]
            other_shapes, _ = build_shapes(other_spec)
            with self.assertRaisesRegex(ValueError, 'bounds'):
                inspect_mesh(result['file'], other_shapes['body'], 0.03)
            triangles = _read_stl(result['file'])
            self.assertEqual(len(triangles), result['triangle_count'])
            with self.assertRaisesRegex(ValueError, 'open|non-manifold'):
                _mesh_topology(triangles[:-1], 1e-8)
            flipped = triangles.copy()
            flipped[0] = flipped[0, ::-1]
            with self.assertRaisesRegex(ValueError, 'winding'):
                _mesh_topology(flipped, 1e-8)

    def test_finished_step_relative_path(self):
        shapes, _ = build_shapes(self.spec())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'finished.step'
            writer = STEPControl_Writer()
            writer.Transfer(shapes['body'], STEPControl_AsIs)
            self.assertEqual(writer.Write(str(path)), IFSelect_RetDone)
            imported, report = build_shapes({'_dir':folder, 'printed_bodies':[{'name':'imported','finished_step':'finished.step'}]})
            self.assertEqual(list(imported), ['imported'])
            self.assertAlmostEqual(report['bodies'][0]['volume_mm3'], 4000, places=5)

    def test_reject_malformed_duplicate_and_noop_features(self):
        cases = []
        for bad in (0, -1, float('nan'), float('inf'), True):
            spec = self.spec()
            spec['printed_bodies'][0]['stock']['size'][0] = bad
            cases.append(spec)
        spec = self.spec(); spec['printed_bodies'].append(copy.deepcopy(spec['printed_bodies'][0])); cases.append(spec)
        for bad_name in ('../escape', 'Part_body', 'REF_body', 'HW_body'):
            spec = self.spec(); spec['printed_bodies'][0]['name'] = bad_name; cases.append(spec)
        for feature in (
            {'type':'unknown'},
            {'type':'box','origin':[100,100,100],'size':[1,1,1]},
            {'type':'box','origin':[-1,-1,-1],'size':[22,22,12]},
            {'type':'cylinder','origin':[10,10,0],'axis':[0,0,2],'radius_mm':2,'depth_mm':10},
            {'type':'offset_pocket','point':[10,10,0],'normal':[0,0,1],'u':[0,0,1],'width_mm':5,'height_mm':5,'depth_mm':4},
            None,
        ):
            spec = self.spec(); spec['printed_bodies'][0]['subtract'] = [feature]; cases.append(spec)
        spec = self.spec(); spec['printed_bodies'][0]['add'] = [{'type':'box','origin':[100,100,100],'size':[1,1,1]}]; cases.append(spec)
        spec = self.spec(); spec['printed_bodies'][0]['finished_step'] = 'missing.step'; cases.append(spec)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                build_shapes(case)
        shapes, _ = build_shapes(self.spec())
        for bad in (0, -1, float('nan'), True):
            with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
                export_meshes(shapes, folder, bad)


if __name__ == '__main__':
    unittest.main()
