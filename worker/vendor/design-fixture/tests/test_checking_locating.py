import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from assembly_locating import audit

class CheckingLocatingTests(unittest.TestCase):
 def plan(self):
  coords=[([0,0,0],[0,0,1],'Primary'),([10,0,0],[0,0,1],'Primary'),([0,10,0],[0,0,1],'Primary'),
   ([0,0,0],[0,1,0],'Secondary'),([10,0,0],[0,1,0],'Secondary'),([0,0,0],[1,0,0],'Tertiary')]
  return {'workpiece':{'parts':{'A':'Part_A','B':'Part_B'}},'contacts':[
   {'name':str(i),'part':'A' if i%2 else 'B','contact':p,'normal':n,'role':role} for i,(p,n,role) in enumerate(coords)],
   'inspection':{'rigid_assembly':{'parts':['A','B'],'basis':'finished weldment assumed rigid','seating_directions':
    {'Primary':[0,0,-1],'Secondary':[0,-1,0],'Tertiary':[-1,0,0]}}}}
 def test_two_parts_need_one_rigid_constraint_system(self):
  r=audit(self.plan());self.assertEqual(r['status'],'pass');self.assertEqual(r['stages'][0]['required_rank'],6)
 def test_redundancy_and_missing_parts_fail(self):
  p=self.plan();p['contacts'].append(copy.deepcopy(p['contacts'][0]));self.assertEqual(audit(p)['status'],'fail')
  p=self.plan();p['inspection']['rigid_assembly']['parts']=['A'];self.assertEqual(audit(p)['status'],'fail')
 def test_pin_rank_does_not_claim_fit_verified(self):
  p=self.plan();p['contacts']=p['contacts'][:3]
  p['inspection']['pin_bearings']=[{'id':'R','part':'A','pin_shape':'REF_PIN_R','point_mm':[0,0,0],'directions':[[1,0,0],[0,1,0]]},
   {'id':'D','part':'B','pin_shape':'REF_PIN_D','point_mm':[10,0,0],'directions':[[0,1,0]]}]
  r=audit(p);self.assertEqual(r['stages'][0]['rank'],6);self.assertEqual(r['status'],'unknown')
if __name__=='__main__':unittest.main()
