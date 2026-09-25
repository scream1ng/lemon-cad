import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from fixture_common import load_spec
from cross_support import audit

class CrossSupport(unittest.TestCase):
    def setUp(self):self.spec=load_spec(ROOT/'examples/flat-plate/spec.json')
    def test_example_every_upright_crossed(self):
        r=audit(self.spec);self.assertEqual(r['status'],'pass');self.assertTrue(all(p['crossed_by'] for p in r['plates']))
    def test_lone_rib_fails(self):
        s=copy.deepcopy(self.spec);s['joints']=[j for j in s['joints'] if 'C1' not in (j['a'],j['b'])]
        r=audit(s);self.assertEqual(r['status'],'fail');self.assertEqual({p['plate'] for p in r['plates'] if p['status']=='fail'},{'C1','XC'})
    def test_exception_is_unknown_not_pass(self):
        s=copy.deepcopy(self.spec);s['joints']=[j for j in s['joints'] if 'C1' not in (j['a'],j['b'])]
        for d in s['plates']:
            if d['name'] in ('C1','XC'):d['cross_support_exception']='test reason'
        self.assertEqual(audit(s)['status'],'unknown')
    def test_joint_without_cut_slot_fails(self):
        s=copy.deepcopy(self.spec);c1=next(d for d in s['plates'] if d['name']=='C1');c1['outer']=[[-115,0],[-80,0],[-80,70],[-115,70]]
        r=audit(s);self.assertEqual(r['status'],'fail');self.assertTrue(r['bad_joints'])
    def test_cap_tab_does_not_count(self):
        s=copy.deepcopy(self.spec);s['joints']=[j for j in s['joints'] if 'XK' not in (j['a'],j['b'])]
        s['joints'].append({'a':'K1','b':'P_T1','a_slot':'tab','b_slot':'through'})
        self.assertIn('K1',{p['plate'] for p in audit(s)['plates'] if p['status']=='fail'})

if __name__=='__main__':unittest.main()
