"""Regression cases for complete restraint, actual tool access and functional profiles."""
import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from checking_evidence import qualify
from records import sha256

class PracticalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'review.txt';self.file.write_text('Synthetic engineering attachment for schema tests only')
        self.spec={'contacts':[{'name':'A1','role':'Primary'},{'name':'A2','role':'Primary'}],
                   'clamps':[{'tag':'T1'}],'plates':[{'name':'R1'}],
                   'inspection':{'flanges':[{'id':'F1','checks':[{'id':'S1','kind':'surface_gap'}]}]}}
    def evidence(self,name,measured,status='pass'):
        return {'name':name,'status':status,'geometry_fingerprint':'current','measured':measured,
                'limit':'Documented acceptance limits','scope':'Synthetic test of evidence completeness',
                'evidence':[{'file':str(self.file),'sha256':sha256(self.file)}]}
    def qualify(self,name,m,status='pass'):
        return qualify(self.evidence(name,m,status),name,'review','current',self.tmp.name,self.spec['inspection'],self.spec)
    def restraint(self):
        return {'station_ids':['S1'],'seating_verified':True,'closed_pose_verified':True,
                'primary_supports':[{'support_id':s,'mode':'clamped','clamp_tags':['T1'],
                                     'basis':'Measured shared restraint','load_path':'Part to support to base'} for s in ('A1','A2')]}
    def access(self):
        return {'station_ids':['S1'],'stations':[{'station_id':'S1','tool_id':'G1','reach_mm':60,
                'envelopes_mm':{k:[10,12,20] for k in ('working_end','stem','handle','hand')},
                'part_clamped':True,'closed_pose_verified':True,'custom_tool':False,
                'paths':[{'end':'GO','result':'clear','method':'continuous','min_clearance_mm':2},
                         {'end':'NO_GO','result':'clear_to_stop','expected_stop':'Part/land gap',
                          'method':'continuous','min_clearance_mm':2}]}]}
    def profiles(self):
        return {'plate_ids':['R1'],'reliefs':[],'final_profiles_reviewed':True}
    def test_shared_clamp_does_not_require_one_per_support(self):
        self.assertEqual(self.qualify('inspection_restraint',self.restraint())['status'],'pass')
    def test_missing_required_clamp_fails(self):
        self.spec['clamps']=[]
        self.assertEqual(self.qualify('inspection_restraint',self.restraint())['status'],'fail')
    def test_missing_support_map_and_unmapped_clamp_unknown(self):
        m=self.restraint();m['primary_supports'].pop()
        self.assertEqual(self.qualify('inspection_restraint',m)['status'],'unknown')
        self.spec['clamps'].append({'tag':'T2'})
        self.assertEqual(self.qualify('inspection_restraint',self.restraint())['status'],'unknown')
    def test_gravity_needs_basis_and_seating_evidence(self):
        self.spec['clamps']=[];m=self.restraint()
        for row in m['primary_supports']:row.update(mode='gravity_only',clamp_tags=[])
        self.assertEqual(self.qualify('inspection_restraint',m)['status'],'pass')
        m['primary_supports'][0].pop('basis')
        self.assertEqual(self.qualify('inspection_restraint',m)['status'],'unknown')
    def test_open_pose_never_passes_but_explicit_exception_retained(self):
        m=self.restraint();m['closed_pose_verified']=False
        self.assertEqual(self.qualify('inspection_restraint',m)['status'],'unknown')
        m['limitations']='Seating/force analysis uses conservative unverified closed envelope'
        self.assertEqual(self.qualify('inspection_restraint',m,'exception')['status'],'exception')
    def test_complete_tool_routes(self):
        self.assertEqual(self.qualify('gauge_access',self.access())['status'],'pass')
    def test_tip_only_evidence_cannot_pass(self):
        self.assertEqual(self.qualify('gauge_access',{'station_ids':['S1']})['status'],'unknown')
        m=self.access();m['stations'][0]['envelopes_mm'].pop('hand')
        self.assertEqual(self.qualify('gauge_access',m)['status'],'unknown')
    def test_blocked_no_go_access_fails_including_exception(self):
        m=self.access();m['stations'][0]['paths'][1]['result']='blocked'
        for status in ('pass','exception'):
            self.assertEqual(self.qualify('gauge_access',m,status)['status'],'fail')
    def test_expected_no_go_stop_not_a_clearance_failure(self):
        m=self.access();m['stations'][0]['paths'][1].pop('expected_stop')
        self.assertEqual(self.qualify('gauge_access',m)['status'],'unknown')
    def test_sampling_and_closed_pose_are_not_continuous_proof(self):
        for key,value in [('closed_pose_verified',False),('part_clamped',False)]:
            m=self.access();m['stations'][0][key]=value
            self.assertEqual(self.qualify('gauge_access',m)['status'],'unknown')
        m=self.access();m['stations'][0]['paths'][0]['method']='sampled'
        self.assertEqual(self.qualify('gauge_access',m)['status'],'unknown')
        m['stations'][0]['limitations']='Discrete poses only'
        self.assertEqual(self.qualify('gauge_access',m,'exception')['status'],'exception')
    def test_custom_tool_requires_handling_and_stiffness(self):
        m=self.access();m['stations'][0]['custom_tool']=True
        self.assertEqual(self.qualify('gauge_access',m)['status'],'unknown')
        m['stations'][0].update(custom_tool_basis='Required measured reach',rigidity_basis='Deflection within budget',handling_basis='Supported grip')
        self.assertEqual(self.qualify('gauge_access',m)['status'],'pass')
    def test_negative_route_clearance_fails(self):
        m=self.access();m['stations'][0]['paths'][0]['min_clearance_mm']=-1
        self.assertEqual(self.qualify('gauge_access',m)['status'],'fail')
    def test_profile_review_functional_relief_and_unnecessary_cut(self):
        m=self.profiles()
        self.assertEqual(self.qualify('rib_profile_review',m)['status'],'pass')
        m['reliefs']=[{'plate_id':'R1','feature_id':'slot-1','purpose':'Actual brace interlock','required':True}]
        self.assertEqual(self.qualify('rib_profile_review',m)['status'],'pass')
        m['reliefs'][0]['required']=False
        self.assertEqual(self.qualify('rib_profile_review',m)['status'],'fail')
    def test_missing_profile_review_unknown(self):
        for key in ('plate_ids','reliefs','final_profiles_reviewed'):
            m=self.profiles();m.pop(key)
            self.assertEqual(self.qualify('rib_profile_review',m)['status'],'unknown')
    def test_printed_only_profile_nonapplicability(self):
        self.spec['plates']=[];m=self.profiles();m['plate_ids']=[]
        self.assertEqual(self.qualify('rib_profile_review',m)['status'],'pass')
    def test_stale_and_changed_attachments_rejected(self):
        c=self.evidence('gauge_access',self.access());c['geometry_fingerprint']='old'
        self.assertEqual(qualify(c,'gauge_access','review','current',self.tmp.name,self.spec['inspection'],self.spec)['status'],'unknown')
        c=self.evidence('gauge_access',self.access());self.file.write_text('changed')
        self.assertEqual(qualify(c,'gauge_access','review','current',self.tmp.name,self.spec['inspection'],self.spec)['status'],'unknown')

if __name__=='__main__':unittest.main()
