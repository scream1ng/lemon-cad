"""Measure planar flange checking lands on reopened STEP. Samples never certify whole surfaces."""
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.GeomAbs import GeomAbs_Plane
from OCP.TopAbs import TopAbs_FACE,TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt,gp_Ax2,gp_Dir
from checking_offsets import vector
from export_step import read_step
from verify import gap,common_volume,face_contact,moved
from records import aggregate
from check_gap_plan import screen


def station_shapes(shapes,plan,station):
    """Movable checking bodies (inspection.movable_details) are exported open; close only this station's own body. No-op otherwise."""
    m=next((m for m in plan.get('movable_details',[]) if m.get('body')==station.get('fixture_shape')),None)
    if m is None or m['body'] not in shapes:return shapes
    from OCP.gp import gp_Trsf,gp_Vec,gp_Ax1
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    t=gp_Trsf()
    if m['kind']=='slide':
        d=vector(m['direction']);t.SetTranslation(gp_Vec(*(-d/np.linalg.norm(d)*float(m['stroke_mm']))))
    else:t.SetRotation(gp_Ax1(gp_Pnt(*m['axis_point_mm']),gp_Dir(*m['axis_direction'])),-np.radians(float(m['open_angle_deg'])))
    out=dict(shapes);out[m['body']]=BRepBuilderAPI_Transform(shapes[m['body']],t,True).Shape();return out


def land_ray(shape,p,n):
    """Nearest forward trimmed planar face facing the part on the exact checking normal."""
    rows=[];it=TopExp_Explorer(shape,TopAbs_FACE);i=0
    while it.More():
        face=TopoDS.Face_s(it.Current());it.Next();i+=1
        surf=BRepAdaptor_Surface(face,True)
        if surf.GetType()!=GeomAbs_Plane:continue
        plane=surf.Plane();normal=np.array(plane.Axis().Direction().Coord())
        if face.Orientation()==TopAbs_REVERSED:normal=-normal
        if normal@(-n)<.99999:continue
        d=float((np.array(plane.Location().Coord())-p)@n)
        if d < -1e-7:continue
        q=p+n*d;vertex=BRepBuilderAPI_MakeVertex(gp_Pnt(*q)).Vertex()
        if gap(vertex,face)>.0001:continue
        rows.append({'distance_mm':d,'point_mm':q.tolist(),'face_index_in_export':i,'outward_normal':normal.tolist()})
    return min(rows,key=lambda r:r['distance_mm']) if rows else None


def gauge_block(p,n,u,width,length,thickness,nominal_gap):
    v=np.cross(n,u);o=p-u*width/2-v*length/2+n*(nominal_gap-thickness)/2
    return BRepPrimAPI_MakeBox(gp_Ax2(gp_Pnt(*o),gp_Dir(*n),gp_Dir(*u)),width,length,thickness).Shape()


def station_audit(station,shapes,parts):
    sid=station['id'];row={'id':sid,'kind':station['kind'],'status':'unknown'}
    if station['kind']=='alternative':
        row['reason']='Alternative method requires explicit CAD/engineering evidence';return row
    pn=parts.get(station.get('part'),station.get('part_shape',station.get('part')))
    own=station.get('fixture_shape');row.update(part_shape=pn,fixture_shape=own)
    if pn not in shapes or own not in shapes:
        row.update(status='fail',reason='Missing exact workpiece or checking-solid identity');return row
    p=vector(station['point_mm']);n=vector(station['direction'],True)
    nominal=float(station.get('nominal_gap_mm',3));epsilon=1e-4
    patch=station.get('patch');points=[p];u=None
    if patch:
        u=vector(patch['u'],True);v=vector(patch['v'],True)
        if abs(n@u)>1e-7 or abs(n@v)>1e-7 or abs(u@v)>1e-7:raise ValueError(f'{sid}: patch axes must be orthogonal and tangent to the checking plane')
        w,h=float(patch['width_mm']),float(patch['height_mm'])
        if not np.isfinite([w,h]).all() or min(w,h)<=0:raise ValueError('Patch sizes must be positive finite')
        points=[p+u*x+v*y for x in (-w/2,0,w/2) for y in (-h/2,0,h/2)]
    measured=[]
    for point in points:
        source=face_contact({'contact':point.tolist(),'normal':(-n).tolist(),
            'face':{'type':'plane','point':p.tolist(),'outward_normal':n.tolist()}},shapes[pn])
        land=land_ray(shapes[own],point,n)
        passed=source['status']=='pass' and land is not None and abs(land['distance_mm']-nominal)<=epsilon
        measured.append({'source_point_mm':point.tolist(),'source_face':source,'land':land,'status':'pass' if passed else 'fail'})
    row.update(samples=measured,nominal_gap_mm=nominal,cad_comparison_tolerance_mm=epsilon,
        status=aggregate(x['status'] for x in measured),
        scope='Reopened planar-face normal distances at specified samples only; CAD epsilon is not build tolerance')
    if not patch and row['status']=='pass':row.update(status='unknown',reason='Only one sample; supply finite patch coverage')
    gspec=station.get('gauge_envelope');gauge={'status':'unknown','reason':'Full working-end envelope not specified'}
    if gspec:
        gu=vector(gspec['u'],True)
        if abs(gu@n)>1e-7:raise ValueError('Gauge u must be tangent to checking plane')
        width,length=float(gspec['width_mm']),float(gspec['length_mm'])
        if not np.isfinite([width,length]).all() or min(width,length)<=0:raise ValueError('Invalid gauge dimensions')
        gvals={k:float(station.get(k,d)) for k,d in [('go_mm',2.5),('no_go_mm',3.5)]}
        bodies={k:gauge_block(p,n,gu,width,length,t,nominal) for k,t in gvals.items()}
        local={k:{name:common_volume(sh,shapes[name]) for name in (pn,own)} for k,sh in bodies.items()}
        fits=max(local['go_mm'].values())<1e-4 and max(local['no_go_mm'].values())>1e-4
        gauge={'status':'pass' if fits else 'fail','nominal_fit_intersections_mm3':local,
            'scope':'Working-end nominal GO fit / NO-GO interference only; not part acceptance or full tool/hand access'}
        approach=gspec.get('approach_direction');offsets=gspec.get('offsets_mm')
        if approach is not None and offsets:
            a=vector(approach,True)
            if abs(a@n)>1e-7:raise ValueError('Gauge approach must be tangent to the checking plane')
            distances=[float(x) for x in offsets]
            if not np.isfinite(distances).all() or min(distances)<0 or 0 not in distances:raise ValueError('Approach offsets must include zero and be nonnegative finite')
            hits=[]
            for dist in distances:
                sh=moved(bodies['go_mm'],a*dist)
                for name,target in shapes.items():
                    vol=common_volume(sh,target)
                    if vol>1e-4:hits.append({'offset_mm':dist,'solid':name,'volume_mm3':vol})
            gauge['approach_samples']={'status':'fail' if hits else 'unknown','sample_status':'fail' if hits else 'pass',
                'offsets_mm':distances,'collisions':hits,'scope':'Discrete working-end samples only; no continuous-path or hand/handle proof'}
            if hits:gauge['status']='fail'
    row['gauge_envelope']=gauge
    row['status']=aggregate([row['status'],gauge['status']])
    return row


def audit(spec,step_path):
    plan=spec.get('inspection',{});plan_result=screen(plan)
    shapes=read_step(step_path);rows=[]
    if plan_result['status']!='invalid':
        for flange in plan.get('flanges',[]):
            for station in flange.get('checks',[]):rows.append(station_audit(station,station_shapes(shapes,plan,station),spec.get('workpiece',{}).get('parts',{})))
    plan_status={'invalid':'fail','unresolved':'unknown','plan_screen_pass':'pass'}[plan_result['status']]
    plan_result['outcome']=plan_result.pop('status')
    return {'status':aggregate([plan_status]+[r['status'] for r in rows]),'plan_status':plan_status,
        'plan_screen':plan_result,'stations':rows,'step':str(step_path),
        'scope':'Flange inventory and finite planar checking-land/gauge-envelope samples; curved/alternative checks require explicit evidence'}
