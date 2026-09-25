"""Mount height measured from CAD: HUD regression, varied heights and evidence gates."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from mount_height import audit,nominal
from export_step import solid,write_step,read_step
from hardware_geometry import definition
from records import sha256
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Pnt,gp_Trsf


def case(mount_height, contact_height, actual_mount=None):
    plate={'name':'CAP','part_number':'CAP','origin':[0,0,mount_height-2.5],
           'u':[1,0,0],'v':[0,1,0],'w':[0,0,1],
           'outer':[[-112,-30],[-44,-30],[-44,30],[-112,30]],'holes':[],'contacts':[]}
    c={'tag':'T1','hardware':'GH-201-B','mount_plate':'CAP','part':'Sheet',
       'contact':[0,0,contact_height],'surface_normal':[0,0,1],
       'arm_direction':[1,0,0],'apply_hole_pattern':True}
    spec={'thickness_mm':5,'min_width_mm':10,'plates':[plate],'clamps':[c]}
    physical=copy.deepcopy(plate)
    if actual_mount is not None:physical['origin'][2]=actual_mount-2.5
    shapes={'CAP':solid(physical,5),'Part_Sheet':BRepPrimAPI_MakeBox(gp_Pnt(-20,-20,contact_height-3),40,40,3).Shape()}
    return spec,shapes


class HeightTests(unittest.TestCase):
    def measured(self,s,sh):
        # All normal cases exercise STEP write/read, not just spec arithmetic.
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'case.step';write_step(p,sh);actual=read_step(p)
            return audit(s,actual,{'Sheet':('Part_Sheet',actual['Part_Sheet'])})
    def test_hud_low_mount_fails(self):
        s,sh=case(58,71);r=self.measured(s,sh)
        self.assertEqual(r['status'],'fail');self.assertAlmostEqual(r['clamps'][0]['offset_mm'],-13)
    def test_hud_corrected_same_level_passes(self):
        s,sh=case(71,71);r=self.measured(s,sh)
        self.assertEqual(r['status'],'pass',r)
        self.assertAlmostEqual(r['clamps'][0]['mount_face_height_mm'],71)
        self.assertAlmostEqual(r['clamps'][0]['clamping_surface_height_mm'],71)
    def test_rule_is_not_a_fixed_13_mm_correction(self):
        for height in (44.25,103.5,175):
            s,sh=case(height,height);self.assertEqual(self.measured(s,sh)['status'],'pass')
            s,sh=case(height-6,height);self.assertEqual(self.measured(s,sh)['status'],'fail')
    def test_exported_geometry_overrules_correct_spec_value(self):
        s,sh=case(71,71,actual_mount=58)
        self.assertEqual(nominal(s['clamps'][0],s['plates'][0],5,definition('GH-201-B'))['status'],'pass')
        self.assertEqual(self.measured(s,sh)['status'],'fail')
    def test_plate_top_not_centre_plane(self):
        s,sh=case(73.5,71);r=self.measured(s,sh)
        self.assertEqual(r['status'],'fail');self.assertAlmostEqual(r['clamps'][0]['offset_mm'],2.5)
    def test_measurement_follows_normal_in_rotated_frame(self):
        s,sh=case(94,94);rot=np.array([[0,0,1],[0,1,0],[-1,0,0]]);move=np.array([13,27,110])
        tf=gp_Trsf();tf.SetValues(*np.column_stack([rot,move]).ravel().tolist())
        for p in s['plates']:
            p['origin']=(rot@p['origin']+move).tolist()
            for k in ('u','v','w'):p[k]=(rot@p[k]).tolist()
        c=s['clamps'][0];c['contact']=(rot@c['contact']+move).tolist()
        for k in ('surface_normal','arm_direction'):c[k]=(rot@c[k]).tolist()
        sh={n:BRepBuilderAPI_Transform(v,tf,True).Shape() for n,v in sh.items()}
        r=self.measured(s,sh);self.assertEqual(r['status'],'pass',r)
        self.assertAlmostEqual(r['clamps'][0]['clamping_surface_height_mm'],107)
    def test_missing_or_wrong_contact_face_fails(self):
        s,sh=case(71,71);s['clamps'][0]['contact'][0]=100
        self.assertEqual(self.measured(s,sh)['status'],'fail')
        s,sh=case(71,71)
        self.assertEqual(audit(s,sh,{})['status'],'fail')
    def test_override_needs_current_clamp_specific_evidence(self):
        s,sh=case(58,71);s['clamps'][0]['mount_height_override']={'offset_mm':-13,'reason':'Synthetic evidence-gate test'}
        self.assertEqual(self.measured(s,sh)['status'],'fail')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'evidence.json';p.write_text('{"test_only":true}')
            s['_geometry_fingerprint']='f'*64
            s['engineering_checks']=[{'name':n,'status':'pass','geometry_fingerprint':'f'*64,
              'clamp_tags':['T1'],'scope':'Synthetic evidence-gate fixture, not an engineering approval',
              'measured':{'test_only':True},'limit':{'test_only':True},'evidence':[{'file':str(p),'sha256':sha256(p)}]}
              for n in ('hardware_pose','clamp_seating')]
            r=self.measured(s,sh)
            self.assertEqual(r['clamps'][0]['status'],'exception');self.assertEqual(r['status'],'unknown')
            s['engineering_checks'][0]['clamp_tags']=['T2'];self.assertEqual(self.measured(s,sh)['status'],'fail')
            s['engineering_checks'][0]['clamp_tags']=['T1'];s['_geometry_fingerprint']='e'*64
            self.assertEqual(self.measured(s,sh)['status'],'fail')
            s['_geometry_fingerprint']='f'*64;p.write_text('{"modified":true}')
            self.assertEqual(self.measured(s,sh)['status'],'fail')
    def test_declared_exception_must_match_measured_height(self):
        s,sh=case(58,71);s['clamps'][0]['mount_height_override']={'offset_mm':-8,'reason':'Deliberate offset'}
        self.assertEqual(self.measured(s,sh)['status'],'fail')
    def test_same_height_does_not_verify_operation(self):
        s,sh=case(71,71);r=self.measured(s,sh)
        self.assertEqual(r['status'],'pass');self.assertNotIn('engineering_checks',s)
        self.assertAlmostEqual(r['clamps'][0]['spindle_extension_below_arm_mm'],25.1)

if __name__=='__main__':unittest.main()
