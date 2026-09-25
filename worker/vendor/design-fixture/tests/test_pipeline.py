"""Regression checks for missing evidence, source identity and geometry preservation."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build import build,input_records
from clamp_mount import mount
from fixture_common import load_spec,validate_spec
from records import sha256
from verify import verify,face_contact,resolve_part
from export_step import read_step,write_step
from validate_delivery import validate

class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.spec_file=ROOT/'examples/flat-plate/spec.json'
        cls.result=build(cls.spec_file,cls.root/'baseline',log=lambda *x:None)
        cls.delivery=Path(cls.result['delivery'])
        cls.spec=load_spec(cls.spec_file);cls.spec['plates']=cls.result['plates'];cls.spec['joints']=cls.result['joints']
        cls.step=next(cls.delivery.glob('*.step'))
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def delivery_copy(self,name):
        p=self.root/name;shutil.copytree(self.delivery,p);return p
    def test_example_complete_but_not_fabrication_approved(self):
        self.assertEqual(self.result['exit_code'],0)
        self.assertEqual(validate(self.delivery),[])
        v=json.loads((self.delivery/'JSON/verification.json').read_text())
        self.assertEqual(v['overall_status'],'unknown');self.assertEqual(v['delivery_status'],'pass')
        self.assertFalse(v['fabrication_ready'])
        self.assertEqual(v['measurements']['cad_audit']['mounting_height']['status'],'pass')
        self.assertEqual(next(c for c in v['checks'] if c['name']=='clamp_seating')['status'],'unknown')
        from PIL import Image
        self.assertGreater(Image.open(self.delivery/'assembled.png').height,1120)
        self.assertEqual(v['measurements']['cad_audit']['check_statuses']['contacts'],'pass')
        self.assertEqual(v['measurements']['cad_audit']['insertion']['status'],'unknown')
    def test_v7_gates_are_emitted_unknown_until_evidenced(self):
        v=json.loads((self.delivery/'JSON/verification.json').read_text())
        self.assertEqual(v['schema_version'],'1.2')
        by={c['name']:c for c in v['checks']}
        for name in ('rib_construction','fastener_access','pin_mechanisms'):
            self.assertEqual(by[name]['status'],'unknown')
            self.assertTrue(any(name in item for item in v['open_items']))
        self.assertFalse(v['fabrication_ready'])
    def test_v7_validator_rejects_unmeasured_pass_claim(self):
        p=self.delivery_copy('invalid-v7-pass');f=p/'JSON/verification.json';v=json.loads(f.read_text())
        c=next(c for c in v['checks'] if c['name']=='rib_construction')
        c.update(status='pass',measured={'checked':True},limit='All supported',evidence=['CAD checked'],geometry_fingerprint=v['geometry_fingerprint'])
        f.write_text(json.dumps(v))
        self.assertTrue(any('rib_construction' in e and 'reopened_step' in e for e in validate(p)))
    def test_upper_slots_survive_clamp_mounting(self):
        spec=load_spec(self.spec_file);plate=next(p for p in spec['plates'] if p['name']=='P_T1')
        plate['outer']=[[-45,55],[45,55],[45,140],[-45,140]]
        plate['holes']=[[[x-2.6,y-6.1],[x+2.6,y-6.1],[x+2.6,y+6.1],[x-2.6,y+6.1]] for x in (-30,30) for y in (75,120)]
        original=copy.deepcopy(plate['holes']);mount(spec)
        self.assertEqual(len(plate['holes']),8)
        from shapely.geometry import Polygon
        for h in original:self.assertTrue(any(Polygon(h).symmetric_difference(Polygon(q)).area<1e-6 for q in plate['holes']))
        mount(spec);self.assertEqual(len(plate['holes']),8) # idempotent
    def test_multiple_clamps_preserve_both_patterns(self):
        s=load_spec(self.spec_file);s['plates']=[{'name':'M','part_number':'M','role':'mount','origin':[0,0,42.5],
         'u':[1,0,0],'v':[0,1,0],'w':[0,0,1],'outer':[[-200,-200],[200,-200],[200,200],[-200,200]],'holes':[],'contacts':[]}]
        c=copy.deepcopy(s['clamps'][0]);c['mount_plate']='M';c['contact']=[-70,0,66]
        d=copy.deepcopy(c);d['tag']='T2';d['contact']=[70,0,66];s['clamps']=[c,d]
        mount(s);self.assertEqual(len(s['plates'][0]['holes']),8)
    def test_hole_conflict_rejected(self):
        s=load_spec(self.spec_file);p=next(p for p in s['plates'] if p['name']=='P_T1')
        p['holes'].append([[-15,89],[-7,89],[-7,97],[-15,97]])
        with self.assertRaisesRegex(ValueError,'conflicts'):mount(s)
    def test_wrong_contact_direction_rejected(self):
        shapes=read_step(self.step);_,target=resolve_part(shapes,'Part_Plate')
        for c in self.spec['contacts']:
            c=copy.deepcopy(c);c['normal']=[-x for x in c['normal']]
            self.assertEqual(face_contact(c,target)['status'],'fail')
    def test_missing_face_descriptor_unknown(self):
        c=copy.deepcopy(self.spec['contacts'][0]);c.pop('face')
        _,target=resolve_part(read_step(self.step),'Part_Plate')
        self.assertEqual(face_contact(c,target)['status'],'unknown')
    def test_missing_contact_coverage_never_passes(self):
        s=copy.deepcopy(self.spec);s['contacts']=[];s['locating_groups']={};s.pop('assembly_locating',None)
        r=verify(s,self.step,insertion=False,log=lambda *x:None)
        self.assertEqual(r['status'],'unknown');self.assertEqual(r['check_statuses']['constraint_independence'],'unknown')
    def test_invalid_frame_rejected(self):
        s=load_spec(self.spec_file);s['plates'][0]['w']=[0,0,-1]
        with self.assertRaisesRegex(ValueError,'right-handed'):validate_spec(s)
    def test_source_hash_changes_without_spec_change(self):
        s=load_spec(self.spec_file);f=self.root/'source.step';shutil.copyfile(ROOT/'examples/flat-plate/workpiece.step',f)
        s['workpiece']['source_files']=[str(f)]
        before=input_records(self.spec_file,s)
        f.write_bytes(f.read_bytes()+b'\n')
        after=input_records(self.spec_file,s)
        self.assertEqual(before[0]['sha256'],after[0]['sha256'])
        self.assertNotEqual(before[1]['sha256'],after[1]['sha256'])
    def test_missing_check_invalid(self):
        p=self.delivery_copy('missing-check');f=p/'JSON/verification.json';v=json.loads(f.read_text());v['checks']=v['checks'][1:];f.write_text(json.dumps(v))
        self.assertTrue(any('missing required check' in e for e in validate(p)))
    def test_missing_height_measurement_invalid(self):
        p=self.delivery_copy('missing-height');f=p/'JSON/verification.json';v=json.loads(f.read_text())
        v['measurements']['cad_audit'].pop('mounting_height');f.write_text(json.dumps(v))
        self.assertTrue(any('mounting_height' in e for e in validate(p)))
    def test_wrong_revision_and_status_invalid(self):
        p=self.delivery_copy('wrong-status');f=p/'JSON/verification.json';v=json.loads(f.read_text());v.update(geometry_revision='OLD',overall_status='banana');f.write_text(json.dumps(v))
        errors=validate(p)
        self.assertTrue(any('geometry_revision' in e for e in errors));self.assertTrue(any('invalid check status' in e for e in errors))
    def test_empty_export_and_modified_export_invalid(self):
        p=self.delivery_copy('bad-export');next(p.glob('*.step')).write_bytes(b'')
        (p/'assembled.png').write_bytes(b'not a PNG')
        errors=validate(p);self.assertTrue(any('empty file' in e for e in errors));self.assertTrue(any('hash mismatch' in e for e in errors))
    def test_skipped_export_returns_nonzero(self):
        p=subprocess.run([sys.executable,str(ROOT/'scripts/build.py'),str(self.spec_file),str(self.root/'skipped'),'--no-step'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2,p.stdout+p.stderr)
        v=json.loads((self.root/'skipped/DELIVERY/JSON/verification.json').read_text());self.assertEqual(v['delivery_status'],'fail')
    def test_resume_records_retain_geometry_and_evidence(self):
        d=json.loads((self.delivery/'JSON/fixture-design.json').read_text());v=json.loads((self.delivery/'JSON/verification.json').read_text())
        self.assertTrue(d['supports']);self.assertTrue(d['retention'])
        self.assertIn('outer',d['components'][0]);self.assertIn('origin',d['components'][0])
        self.assertEqual(len(v['measurements']['cad_audit']['contacts']),6)
        self.assertEqual(len(d['design_spec']['plates'][0]['holes']),0)
    def test_all_custom_plates_receive_width_screening(self):
        v=json.loads((self.delivery/'JSON/verification.json').read_text())
        checked=set(v['measurements']['width_audit']['edge_pair']['plates'])
        self.assertEqual(checked,{p['name'] for p in self.spec['plates']})
    def test_wrong_intended_face_rejected(self):
        c=copy.deepcopy(self.spec['contacts'][0]);c['face']['point']=[0,0,66]
        _,target=resolve_part(read_step(self.step),'Part_Plate')
        self.assertEqual(face_contact(c,target)['status'],'fail')
    def test_bspline_face_accepted_only_when_flat(self):
        from OCP.TColgp import TColgp_Array2OfPnt
        from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCP.gp import gp_Pnt
        def face(sag):
            a=TColgp_Array2OfPnt(1,5,1,5)
            for i in range(5):
                for j in range(5):x,y=-20+10*i,-20+10*j;a.SetValue(i+1,j+1,gp_Pnt(x,y,sag*(x*x+y*y)/400))
            return BRepBuilderAPI_MakeFace(GeomAPI_PointsToBSplineSurface(a).Surface(),1e-6).Face()
        c={'contact':[0,0,0],'normal':[0,0,-1],'face':{'type':'plane','point':[0,0,0],'outward_normal':[0,0,1]}}
        flat=face(0)
        if face_contact(c,flat).get('outward_normal',[0,0,1])[2]<0:c['normal']=[0,0,1];c['face']['outward_normal']=[0,0,-1]
        r=face_contact(c,flat);self.assertEqual(r['status'],'pass');self.assertNotEqual(r['surface'],'Plane')
        self.assertEqual(face_contact(c,face(.5))['status'],'fail')
    def test_nested_step_occurrence_placement(self):
        from OCP.TDocStd import TDocStd_Document
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.XCAFDoc import XCAFDoc_DocumentTool
        from OCP.TDataStd import TDataStd_Name
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.TopoDS import TopoDS_Compound
        from OCP.BRep import BRep_Builder
        from OCP.gp import gp_Trsf,gp_Vec
        from OCP.TopLoc import TopLoc_Location
        from OCP.STEPCAFControl import STEPCAFControl_Writer
        from OCP.STEPControl import STEPControl_AsIs
        from OCP.IFSelect import IFSelect_RetDone
        from verify import bbox
        doc=TDocStd_Document(TCollection_ExtendedString('nested'));st=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        compound=TopoDS_Compound();BRep_Builder().MakeCompound(compound)
        root=st.AddShape(compound,True);TDataStd_Name.Set_s(root,TCollection_ExtendedString('Assembly'))
        leaf=st.AddShape(BRepPrimAPI_MakeBox(10,20,30).Shape(),False);TDataStd_Name.Set_s(leaf,TCollection_ExtendedString('Part_Test'))
        transform=gp_Trsf();transform.SetTranslation(gp_Vec(80,40,20))
        occ=st.AddComponent(root,leaf,TopLoc_Location(transform));TDataStd_Name.Set_s(occ,TCollection_ExtendedString('Part_Test'))
        st.UpdateAssemblies();w=STEPCAFControl_Writer();w.SetNameMode(True);w.Transfer(doc,STEPControl_AsIs)
        file=self.root/'nested.step';self.assertEqual(w.Write(str(file)),IFSelect_RetDone)
        shapes=read_step(file);self.assertIn('Part_Test',shapes)
        for actual,expected in zip(bbox(shapes['Part_Test']),(80,40,20,90,60,50)):self.assertAlmostEqual(actual,expected,places=5)

if __name__=='__main__':unittest.main()
