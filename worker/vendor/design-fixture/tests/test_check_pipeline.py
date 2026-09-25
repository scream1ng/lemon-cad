"""End-to-end printed/steel checking deliveries and corrupted-export rejection."""
import json,os,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_check import build
from validate_delivery import validate
from records import sha256
from export_step import read_step,write_step
from verify import moved

class CheckingPipelineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.deliveries={}
  for mode in ('checking-rib','checking-printed'):
   result=build(ROOT/'examples'/mode/'spec.json',cls.root/mode,log=lambda *a:None)
   if result['exit_code']!=0:raise AssertionError(result)
   cls.deliveries[mode]=Path(result['delivery'])
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def clone(self,name):
  out=self.root/name;shutil.copytree(self.deliveries['checking-printed'],out);return out
 def test_both_real_packages_and_readiness(self):
  for mode,p in self.deliveries.items():
   self.assertEqual(validate(p),[])
   v=json.loads((p/'JSON/verification.json').read_text())
   self.assertEqual(v['checking_geometry_status'],'pass');self.assertFalse(v['fixture_calibrated'])
   self.assertFalse(v['inspection_validated']);self.assertFalse(v['fabrication_ready'])
   self.assertTrue(list(p.glob('*.dxf')) if mode=='checking-rib' else list((p/'PRINT').glob('*.stl')))
 def test_changed_land_rejected_even_after_hash_refresh(self):
  p=self.clone('wrong-land');step=next(p.glob('*.step'));shapes=read_step(step)
  shapes['BODY_MAIN']=moved(shapes['BODY_MAIN'],[0,0,1]);write_step(step,shapes)
  f=p/'JSON/fixture-design.json';d=json.loads(f.read_text());d['export_sha256'][step.name]=sha256(step);f.write_text(json.dumps(d))
  self.assertTrue(any('checking_geometry' in e for e in validate(p)))
 def test_false_cad_approval_rejected(self):
  p=self.clone('fake-cad');f=p/'JSON/verification.json';d=json.loads(f.read_text());d['cad_verified']=True;f.write_text(json.dumps(d))
  self.assertTrue(any('cad_verified' in e for e in validate(p)))
 def test_missing_print_body_rejected(self):
  p=self.clone('missing-mesh');next((p/'PRINT').glob('*.stl')).unlink()
  self.assertTrue(validate(p))
 def test_resumable_spec_not_double_generated(self):
  p=self.deliveries['checking-rib'];d=json.loads((p/'JSON/fixture-design.json').read_text())
  self.assertNotIn('checking_ribs',d['design_spec'])
  self.assertTrue(d['design_spec']['checking_rib_definitions'])
  self.assertTrue(d['checking_source_spec']['checking_ribs'])

if __name__=='__main__':unittest.main()
