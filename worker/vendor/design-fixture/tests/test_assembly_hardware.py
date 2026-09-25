"""Behavioral regression: coupled location, real clamp identity and oversized mounts."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from assembly_locating import audit,secondary_sides,mating_geometry
from fixture_common import load_spec
from mount_compactness import audit as mount_audit
from hardware_geometry import placed_shapes,definition,asset_path,verify_export
from export_step import read_step,write_step


def stacked():
    cs=[]
    def c(name,p,n,part,role):cs.append(dict(name=name,contact=p,normal=n,part=part,role=role,constraint_role='fixed_datum'))
    for tag,p in [('A1',[-30,-20,60]),('A2',[30,-20,60]),('A3',[0,20,60])]:c('L'+tag,p,[0,0,1],'Lower','Primary')
    for part,z,pr in [('Lower',61.5,'L'),('Upper',64.5,'U')]:
        c(pr+'B1',[-30,-40,z],[0,1,0],part,'Secondary');c(pr+'B2',[30,-40,z],[0,1,0],part,'Secondary');c(pr+'C1',[-50,0,z],[1,0,0],part,'Tertiary')
    mates=[dict(name='M'+str(i+1),part_a='Upper',part_b='Lower',contact=p,normal_on_a=[0,0,1]) for i,p in enumerate([[-30,-20,63],[30,-20,63],[0,20,63]])]
    seat={'Primary':[0,0,-1],'Secondary':[0,-1,0],'Tertiary':[-1,0,0]}
    return dict(workpiece={'parts':{'Lower':'Part_Lower','Upper':'Part_Upper'}},contacts=cs,assembly_locating=dict(master_part='Lower',datum_rationale='Lower datum transfers through overlap contacts.',mating_contacts=mates,loading_stages=[dict(id='lower',parts=['Lower'],fixture_contacts=[c['name'] for c in cs if c['part']=='Lower'],mating_contacts=[],seating_directions={'Lower':seat}),dict(id='both',parts=['Lower','Upper'],fixture_contacts=[c['name'] for c in cs],mating_contacts=['M1','M2','M3'],seating_directions={'Lower':seat,'Upper':seat})]))

class AssemblyTests(unittest.TestCase):
    def test_shared_datums_locate_two_loose_parts(self):
        r=audit(stacked());self.assertEqual(r['status'],'pass',r)
        self.assertEqual([(x['rank'],x['constraint_rows']) for x in r['stages']],[(6,6),(12,12)])
    def test_two_independent_primary_sets_plus_mates_are_redundant(self):
        s=stacked()
        for i,p in enumerate([[-30,-20,63],[30,-20,63],[0,20,63]]):
            name='UA'+str(i+1);s['contacts'].append(dict(name=name,contact=p,normal=[0,0,1],part='Upper',role='Primary',constraint_role='fixed_datum'));s['assembly_locating']['loading_stages'][-1]['fixture_contacts'].append(name)
        r=audit(s);self.assertEqual(r['status'],'fail');self.assertEqual(r['stages'][-1]['redundant_rows'],3)
    def test_hud_opposing_secondary_pair_rejected(self):
        s={'workpiece':{'parts':{'Main':'Part_Main','Reinforcement':'Part_Reinforcement'}},'contacts':[
            dict(name='MB1',part='Main',role='Secondary',normal=[-1,0,0]),dict(name='MB2',part='Main',role='Secondary',normal=[-1,0,0]),
            dict(name='RB1',part='Reinforcement',role='Secondary',normal=[1,0,0]),dict(name='RB2',part='Reinforcement',role='Secondary',normal=[-1,0,0])]}
        r=secondary_sides(s);self.assertEqual(r['status'],'fail');self.assertEqual([x['status'] for x in r['parts']],['pass','fail'])
    def test_actual_hud_contact_schedule_exposes_redundancy(self):
        s=json.loads((ROOT/'tests/data/hud-original-locating.json').read_text())
        r=audit(s);self.assertEqual(r['status'],'fail');self.assertEqual(r['stages'][-1]['redundant_rows'],3)
        self.assertEqual(secondary_sides(s)['status'],'fail')
    def test_stale_stage_contact_ids_rejected(self):
        s=stacked();s['contacts']=[];self.assertEqual(audit(s)['status'],'fail')
    def test_opposed_stop_exception_does_not_pass(self):
        s=stacked();next(c for c in s['contacts'] if c['name']=='UB2')['normal']=[0,-1,0]
        s['assembly_locating']['secondary_exceptions']={'Upper':{'reason':'Special arrangement','seating_method':'Separately actuated stops'}}
        self.assertEqual(secondary_sides(s)['status'],'unknown') # aggregate includes exception
        self.assertEqual(secondary_sides(s)['parts'][1]['status'],'exception')
        self.assertEqual(audit(s)['status'],'fail') # original common seating direction remains impossible
    def test_auxiliary_support_does_not_earn_locating_rank(self):
        s=stacked();next(c for c in s['contacts'] if c['name']=='LA3').update(constraint_role='auxiliary_support',support_mode='floating',activation_sequence='After seating')
        self.assertEqual(audit(s)['status'],'fail')
    def test_extra_adjustable_support_is_not_a_fourth_datum(self):
        s=stacked();s['contacts'].append(dict(name='S1',part='Upper',role='Support',contact=[40,20,63],normal=[0,0,1],constraint_role='auxiliary_support',support_mode='adjustable_after_seating',activation_sequence='After both sheets seat'))
        s['assembly_locating']['loading_stages'][-1]['fixture_contacts'].append('S1');self.assertEqual(audit(s)['status'],'pass')
        s['contacts'][-1].pop('activation_sequence');self.assertEqual(audit(s)['status'],'fail')
    def test_missing_mate_and_missing_stage_do_not_pass(self):
        s=stacked();s.pop('assembly_locating');self.assertEqual(audit(s)['status'],'unknown')
        s=stacked();s['assembly_locating']['loading_stages'][-1]['mating_contacts'].pop();self.assertEqual(audit(s)['status'],'fail')
    def test_omitted_physical_fixed_contact_not_hidden(self):
        s=stacked();s['contacts'].append(dict(name='Extra',part='Upper',role='Primary',contact=[5,5,63],normal=[0,0,1],constraint_role='fixed_datum'))
        self.assertEqual(audit(s)['status'],'unknown')
    def test_mating_faces_checked_on_both_bodies(self):
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt
        s=stacked();resolved={'Lower':('Part_Lower',BRepPrimAPI_MakeBox(gp_Pnt(-50,-40,60),100,80,3).Shape()),'Upper':('Part_Upper',BRepPrimAPI_MakeBox(gp_Pnt(-50,-40,63),100,80,3).Shape())}
        for m in s['assembly_locating']['mating_contacts']:
            m['face_a']={'type':'plane','point':m['contact'],'outward_normal':[0,0,-1]};m['face_b']={'type':'plane','point':m['contact'],'outward_normal':[0,0,1]}
        self.assertEqual(mating_geometry(s,resolved)['status'],'pass')
        s['assembly_locating']['mating_contacts'][0]['contact'][2]=64
        self.assertEqual(mating_geometry(s,resolved)['status'],'fail')

class HardwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=load_spec(ROOT/'examples/flat-plate/spec.json');cls.shapes,cls.rows=placed_shapes(cls.spec)
    def test_actual_asset_has_fourteen_components(self):
        self.assertEqual(len(read_step(asset_path('GH-201-B'))),14);self.assertEqual(len(self.shapes),14)
        self.assertFalse(any('schematic' in n for n in self.shapes))
        self.assertEqual(self.rows[0]['pose_status'],'unknown');self.assertGreater(self.rows[0]['saved_pad_to_target_distance_mm'],1)
    def test_mounting_frame_and_source_slot_centres(self):
        h=definition('GH-201-B');a=np.array(h['asset']['source_to_canonical'])
        self.assertAlmostEqual(np.linalg.det(a[:3,:3]),1)
        raw_slots=[(5.15,-2,-6.5),(5.15,-2,-28.540202025355),(31.85,-2,-6.5),(31.85,-2,-28.540202025355)]
        actual=sorted(tuple(np.round((a@np.r_[p,1])[:3],6)) for p in raw_slots)
        self.assertEqual(actual,sorted(tuple(np.round(p,6)) for p in h['mounting']['hole_centres_canonical_mm']))
    def test_missing_hardware_component_rejected(self):
        shapes=dict(self.shapes);shapes.pop(next(iter(shapes)));self.assertEqual(verify_export(self.spec,shapes)['status'],'fail')
    def test_hardware_roundtrip(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'real.step';write_step(f,self.shapes);self.assertEqual(verify_export(self.spec,read_step(f))['status'],'pass')
    def test_unexplained_large_platform_rejected(self):
        s=copy.deepcopy(self.spec);p=next(p for p in s['plates'] if p['name']=='P_T1');p.pop('mount_design',None);p['outer']=[[-45,55],[45,55],[45,140],[-45,140]]
        r=mount_audit(s);self.assertEqual(r['status'],'fail');self.assertTrue(r['mounts'][0]['unexplained_large_platform'])
    def test_justification_requires_review_not_automatic_approval(self):
        s=copy.deepcopy(self.spec);p=next(p for p in s['plates'] if p['name']=='P_T1');p['outer']=[[-45,55],[45,55],[45,140],[-45,140]]
        p['mount_design']={'layout_reason':'test','compact_alternative_considered':'test'}
        self.assertEqual(mount_audit(s)['status'],'unknown')
    def test_standard_plate_passes_size_screen(self):
        s=copy.deepcopy(self.spec);p=next(p for p in s['plates'] if p['name']=='P_T1');p['outer']=[[-30,80.4],[30,80.4],[30,130.4],[-30,130.4]]
        self.assertEqual(mount_audit(s)['status'],'pass')
    def test_non_standard_small_plate_needs_reason(self):
        s=copy.deepcopy(self.spec);p=next(p for p in s['plates'] if p['name']=='P_T1');p.pop('mount_design',None);p['outer']=[[-26,78],[26,78],[26,132],[-26,132]];p['holes']=[]
        self.assertEqual(mount_audit(s)['status'],'fail')
    def test_standard_cap_uses_hardware_ligament(self):
        from clamp_mount import min_width_for
        self.assertEqual(min_width_for(self.spec,'P_T1'),5.0);self.assertEqual(min_width_for(self.spec,'K1'),self.spec.get('min_width_mm',10.0))
    def test_pin_pad_is_a_cap_on_the_standard_pad_ligament(self):
        import cap_joints
        from clamp_mount import min_width_for,pin_pads
        s=copy.deepcopy(self.spec);s['pin_locators']=[{'id':'P1','shape_name':'REF_PIN_P1','mode':'fixed','orientation_sensitive':False,'pad':'PP1'}]
        self.assertEqual(pin_pads(s),{'PP1'});self.assertEqual(min_width_for(s,'PP1'),5.0)
        s['plates'].append({'name':'PP1','origin':[0.0,0.0,60.0],'u':[1.0,0.0,0.0],'v':[0.0,1.0,0.0],'w':[0.0,0.0,1.0],
                            'outer':[[-20,-20],[20,-20],[20,20],[-20,20]],'holes':[],'contacts':[]})
        self.assertIn('PP1',[r['cap'] for r in cap_joints.audit(s)['caps']])

if __name__=='__main__':unittest.main()
