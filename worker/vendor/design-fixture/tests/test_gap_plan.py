import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_gap_plan import classify_gap, screen

class GapPlanTests(unittest.TestCase):
    def plan(self, mode='laser_rib'):
        return {'units':'mm','construction':mode,'datum_scheme':'A/B/C proposed', 'flanges':[
            {'id':'F01','source_feature':'test surface','checks':[{'id':'F01-S1','kind':'surface_gap',
             'point_mm':[0,0,0],'direction':[0,0,1],'scope':'local position','approach':'from side',
             'drawing_conflict':False}]}]}
    def test_both_modes_step_only_use_shop_standard(self):
        for mode in ('laser_rib','printed_solid'):
            r=screen(self.plan(mode));self.assertEqual(r['status'],'plan_screen_pass')
            self.assertEqual([r['stations'][0][k] for k in ('nominal_gap_mm','go_mm','no_go_mm')],[3,2.5,3.5])
    def test_boundaries_and_rejects(self):
        self.assertEqual(classify_gap(2.49),'outside_ideal_window')
        self.assertEqual(classify_gap(3.51),'outside_ideal_window')
        self.assertEqual(classify_gap(3),'inside_ideal_window')
        for v in (2.5,3.5):self.assertEqual(classify_gap(v),'boundary_review')
        for v in (float('nan'),float('inf'),True,-1):
            with self.assertRaises(ValueError): classify_gap(v)
    def test_coverage_conflict_and_override(self):
        p=self.plan();p['flanges'].append({'id':'F02','source_feature':'return','checks':[]})
        self.assertEqual(screen(p)['status'],'unresolved')
        p=self.plan();s=p['flanges'][0]['checks'][0];s['drawing_conflict']=True
        self.assertEqual(screen(p)['status'],'unresolved')
        s['drawing_conflict']=False;s['go_mm']=2.8
        self.assertEqual(screen(p)['status'],'invalid')
        s['basis']='job_override';self.assertEqual(screen(p)['status'],'unresolved')
        s['override_source']='Explicit job requirement';self.assertEqual(screen(p)['status'],'plan_screen_pass')
    def test_directions_ids_and_bad_values(self):
        for bad in ([0,0,0],[0,0,2],[0,0,float('nan')],[False,0,1]):
            p=self.plan();p['flanges'][0]['checks'][0]['direction']=bad
            self.assertEqual(screen(p)['status'],'invalid')
        p=self.plan();p['flanges'].append(copy.deepcopy(p['flanges'][0]))
        self.assertEqual(screen(p)['status'],'invalid')
        p=self.plan();p['flanges'][0]['checks'][0]['no_go_mm']=2
        self.assertEqual(screen(p)['status'],'invalid')
        for p in (None,[],{}, {'flanges':None}):self.assertEqual(screen(p)['status'],'invalid')

if __name__=='__main__':unittest.main()
