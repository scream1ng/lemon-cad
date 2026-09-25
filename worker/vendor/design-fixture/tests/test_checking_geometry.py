import copy,sys,tempfile,unittest
from pathlib import Path
import numpy as np
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from checking_geometry import station_audit,station_shapes
from checking_offsets import generate
from verify import moved

class CheckingGeometryTests(unittest.TestCase):
 def setUp(self):
  self.shapes={'Part_Test':BRepPrimAPI_MakeBox(gp_Pnt(-20,-20,10),40,40,2).Shape(),
   'LAND':BRepPrimAPI_MakeBox(gp_Pnt(-20,-20,0),40,40,7).Shape()}
  self.s={'id':'F01-S1','kind':'surface_gap','part_shape':'Part_Test','fixture_shape':'LAND','point_mm':[0,0,10],
   'direction':[0,0,-1],'patch':{'u':[1,0,0],'v':[0,1,0],'width_mm':10,'height_mm':10},
   'gauge_envelope':{'u':[1,0,0],'width_mm':10,'length_mm':4}}
 def test_actual_gap_and_gauges(self):
  r=station_audit(self.s,self.shapes,{})
  self.assertEqual(r['status'],'pass');self.assertTrue(all(abs(x['land']['distance_mm']-3)<1e-8 for x in r['samples']))
  self.assertEqual(r['gauge_envelope']['status'],'pass')
 def test_wrong_gap_and_outside_trim_fail(self):
  self.shapes['LAND']=moved(self.shapes['LAND'],[0,0,1])
  self.assertEqual(station_audit(self.s,self.shapes,{})['status'],'fail')
  self.s['point_mm']=[100,0,10]
  self.assertEqual(station_audit(self.s,self.shapes,{})['status'],'fail')
 def test_missing_patch_or_gauge_does_not_pass(self):
  for key in ('patch','gauge_envelope'):
   s=copy.deepcopy(self.s);s.pop(key)
   self.assertEqual(station_audit(s,self.shapes,{})['status'],'unknown')
 def test_blocked_gauge_approach_fails(self):
  self.shapes['OBSTRUCTION']=BRepPrimAPI_MakeBox(gp_Pnt(7,-5,7.5),3,10,2).Shape()
  self.s['gauge_envelope'].update(approach_direction=[1,0,0],offsets_mm=[0,10,30])
  self.assertEqual(station_audit(self.s,self.shapes,{})['status'],'fail')
 def test_movable_body_closed_for_its_own_station(self):
  from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
  from OCP.gp import gp_Trsf,gp_Ax1,gp_Dir,gp_Vec
  closed=self.shapes['LAND'];self.s['fixture_shape']='ARM'
  t=gp_Trsf();t.SetRotation(gp_Ax1(gp_Pnt(0,-30,0),gp_Dir(1,0,0)),np.radians(90))
  arm={**self.shapes,'ARM':BRepBuilderAPI_Transform(closed,t,True).Shape()}           # exported open
  hinge={'movable_details':[{'body':'ARM','kind':'hinged','axis_point_mm':[0,-30,0],'axis_direction':[1,0,0],'open_angle_deg':90}]}
  self.assertEqual(station_audit(self.s,arm,{})['status'],'fail')
  self.assertEqual(station_audit(self.s,station_shapes(arm,hinge,self.s),{})['status'],'pass')
  slide={**self.shapes,'ARM':moved(closed,[0,6,8])}
  plan={'movable_details':[{'body':'ARM','kind':'slide','direction':[0,3,4],'stroke_mm':10}]}
  self.assertEqual(station_audit(self.s,station_shapes(slide,plan,self.s),{})['status'],'pass')
  self.assertIs(station_shapes(self.shapes,{},self.s),self.shapes)                       # no movable_details: no-op
  other=dict(self.s,fixture_shape='LAND');self.assertIs(station_shapes(arm,hinge,other),arm)  # other stations leave it open
 def test_rib_offset_uses_normal_not_sketch_distance(self):
  spec={'plates':[],'checking_ribs':[{'plate':{'name':'R','origin':[0,0,0],'u':[1,0,0],'v':[0,0,1],
   'w':[0,-1,0],'outer':[[-10,0],[10,0],[10,20],[-10,20]]},
   'offset_planes':[{'point_mm':[0,0,10],'direction':[0,0,-1],'gap_mm':3}]}]}
  generate(spec);self.assertAlmostEqual(max(p[1] for p in spec['plates'][0]['outer']),7)
  bad=copy.deepcopy(spec);bad['plates']=[];bad['checking_ribs'][0]['offset_planes'][0]['direction']=[0,1,0]
  with self.assertRaises(ValueError):generate(bad)

if __name__=='__main__':unittest.main()
