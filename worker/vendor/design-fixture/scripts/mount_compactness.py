"""Screen mount size against actual hardware and required cutout ligaments."""
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union
from clamp_mount import place
from hardware_geometry import definition

def audit(spec):
    by={p['name']:p for p in spec['plates']};rows=[]
    for c in spec.get('clamps',[]):
        p=by[c['mount_plate']];r,holes,_=place(c,p,spec['thickness_mm'],spec.get('min_width_mm',10))
        hw=definition(c['hardware']);gap=spec.get('min_width_mm',10);f=r['frame']
        import numpy as np
        o,U,V=(np.array(p[k],float) for k in ('origin','u','v'))
        O,x,y=(np.array(f[k],float) for k in ('origin','x','y'))
        def q(a,b):
            v=O+x*a+y*b-o;return [float(v@U),float(v@V)]
        e=hw['base']['extent_in_canonical_frame']
        foot=Polygon([q(a,b) for a,b in [(e['x_min_mm'],e['y_min_mm']),(e['x_max_mm'],e['y_min_mm']),(e['x_max_mm'],e['y_max_mm']),(e['x_min_mm'],e['y_max_mm'])]])
        hardware=unary_union([foot]+[h.buffer(gap) for h in holes]);envelope=box(*hardware.bounds)
        outer=Polygon(p['outer']);ratio=outer.area/envelope.area
        extra=[Polygon(h) for h in p['holes'] if not any(Polygon(h).symmetric_difference(x).area<1e-6 for x in holes)]
        required=unary_union([hardware]+[h.buffer(gap) for h in extra])
        rationale=p.get('mount_design',{})
        explained=bool(rationale.get('layout_reason') and rationale.get('compact_alternative_considered'))
        std=r['standard_outline_local']
        if std:  # shop standard plate: match it, or record why this job differs
            standard=outer.symmetric_difference(Polygon(std)).area<1.0
            status='pass' if standard else 'unknown' if explained else 'fail'
            oversized=not standard
            scope='hardware standard mount plate; a different outline needs mount_design.layout_reason and compact_alternative_considered, then engineering review'
            action=None if standard else f"Use the standard {hw['standard_mount_plate']['along_x_mm']:g} x {hw['standard_mount_plate']['across_y_mm']:g} mm plate (standard_outline_local) or record why this job differs."
        else:
            oversized=ratio>2.0 # review trigger, not a universal maximum footprint
            status='fail' if oversized and not explained else 'unknown' if oversized else 'pass'
            scope='ratio above 2 triggers layout review, not automatic enlargement or an absolute size limit; slot/brace layout must be reconsidered'
            action=None if status=='pass' else 'Reduce mount or record comparison with a compact support/tab layout; engineering review must resolve justified large mounts.'
        rows.append({'mount_plate':p['name'],'clamp':c['tag'],'outer_size_mm':[outer.bounds[2]-outer.bounds[0],outer.bounds[3]-outer.bounds[1]],
          'hardware_minimum_envelope_mm':list(envelope.bounds),'hardware_minimum_area_mm2':envelope.area,
          'platform_area_ratio':ratio,'standard_outline_local':std,'other_cutouts':len(extra),'required_feature_envelope_mm':list(required.bounds),
          'unexplained_large_platform':oversized and not explained,'mount_design':rationale,'status':status,
          'scope':scope,'next_action':action})
    return {'status':'fail' if any(r['status']=='fail' for r in rows) else 'unknown' if any(r['status']=='unknown' for r in rows) else 'pass','mounts':rows}
