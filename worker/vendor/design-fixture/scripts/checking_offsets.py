"""Generate flat checking-rib profiles by clipping stock against measured offset planes."""
import copy
import numpy as np
from shapely.geometry import Polygon


def vector(value, unit=False):
    a=np.asarray(value,dtype=float)
    if a.shape!=(3,) or not np.isfinite(a).all() or (unit and not np.isclose(np.linalg.norm(a),1,atol=1e-7)):
        raise ValueError('Expected finite 3-vector'+(' of unit length' if unit else ''))
    return a


def clip_polygon(points,a,b,c):
    """Keep a*x+b*y >= c; no approximate polygon offset or bounding-box substitution."""
    out=[]
    for p,q in zip(points,points[1:]+points[:1]):
        dp=a*p[0]+b*p[1]-c;dq=a*q[0]+b*q[1]-c
        if dp>=-1e-9:out.append(list(p))
        if (dp>=0)!=(dq>=0):
            t=dp/(dp-dq);out.append([p[i]+t*(q[i]-p[i]) for i in (0,1)])
    return out


def generate(spec):
    """Add explicit checking_ribs to spec['plates']; returns measured construction definitions."""
    report=[];existing={p['name'] for p in spec.get('plates',[])}
    for entry in spec.get('checking_ribs',[]):
        d=copy.deepcopy(entry['plate'])
        if d['name'] in existing:raise ValueError('Duplicate generated checking rib '+d['name'])
        o,u,v,w=(vector(d[k],k!='origin') for k in ('origin','u','v','w'))
        frame=np.array([u,v,w]).T
        if not np.allclose(frame.T@frame,np.eye(3)) or not np.isclose(np.linalg.det(frame),1):raise ValueError('Invalid checking rib frame')
        points=d['outer'];rows=[]
        if not entry.get('offset_planes'):raise ValueError('Checking rib requires offset_planes')
        for plane in entry['offset_planes']:
            p=vector(plane['point_mm']);n=vector(plane['direction'],True);g=float(plane.get('gap_mm',3))
            if not np.isfinite(g) or g<=0:raise ValueError('Checking gap must be positive')
            if abs(n@w)>1e-7:raise ValueError('Offset normal must lie in rib plane; use explicit CAD for oblique cut lands')
            a,b=float(n@u),float(n@v);c=float(n@(p-o)+g)
            points=clip_polygon(points,a,b,c)
            if len(points)<3:raise ValueError('Offset planes remove entire checking rib')
            rows.append({'point_mm':p.tolist(),'direction':n.tolist(),'gap_mm':g,'local_halfplane':[a,b,c]})
        d['outer']=points;d.setdefault('holes',[]);d.setdefault('contacts',[])
        shape=Polygon(points,d['holes'])
        if not shape.is_valid or shape.area<=0:raise ValueError('Generated checking rib is invalid')
        spec.setdefault('plates',[]).append(d);existing.add(d['name'])
        report.append({'name':d['name'],'offset_planes':rows,'area_mm2':shape.area})
    return report
