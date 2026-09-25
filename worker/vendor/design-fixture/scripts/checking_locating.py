"""Local rank of a completed rigid inspection assembly, including explicit ideal pin bearings."""
import numpy as np
from checking_offsets import vector


def applies(spec):
    return bool(spec.get('inspection',{}).get('rigid_assembly'))


def audit(spec):
    plan=spec['inspection'];rigid=plan['rigid_assembly'];known=set(spec.get('workpiece',{}).get('parts',{}))
    parts=rigid.get('parts',[]);issues=[];unknown=[]
    if len(set(parts))!=len(parts) or set(parts)!=known or not known:issues.append('Rigid inspection group must cover every workpiece exactly once')
    if not rigid.get('basis'):unknown.append('Missing basis for treating the completed assembly as rigid')
    rows=[];names=[];points=[]
    for c in spec.get('contacts',[]):
        if c['part'] not in known:issues.append('Unknown contact body '+c['name']);continue
        role=c.get('constraint_role','fixed_datum')
        if role=='auxiliary_support':
            if c.get('support_mode') not in ('adjustable_after_seating','floating','relieved') or not c.get('activation_sequence'):issues.append('Unqualified auxiliary support '+c['name'])
            continue
        if role!='fixed_datum':issues.append('Unknown constraint role '+c['name']);continue
        points.append(vector(c['contact']));rows.append((points[-1],vector(c['normal'],True)));names.append(c['name'])
    pins=plan.get('pin_bearings',[])
    pin_ids=set()
    for pin in pins:
        if pin.get('id') in pin_ids or not pin.get('id'):issues.append('Pin bearing IDs must be unique and nonempty')
        pin_ids.add(pin.get('id'))
        if pin.get('part') not in known or not pin.get('pin_shape'):issues.append('Pin bearing requires known part and real pin solid identity')
        ds=pin.get('directions',[])
        if len(ds) not in (1,2):issues.append('Round/relieved bearing has one or two explicit independent directions')
        p=vector(pin['point_mm']);points.append(p)
        for i,d in enumerate(ds):rows.append((p,vector(d,True)));names.append(f"{pin.get('id')}-{i+1}")
    if pins:unknown.append('Pin-bearing rank is a finite-clearance idealization; actual pin/hole fit, orientation and engagement require CAD evidence')
    origin=np.mean(points,axis=0) if points else np.zeros(3)
    length=max(float(np.linalg.norm(np.ptp(points,axis=0))),1) if points else 1
    matrix=np.array([np.r_[n,np.cross(p-origin,n)/length] for p,n in rows]) if rows else np.zeros((0,6))
    rank=int(np.linalg.matrix_rank(matrix)) if rows else 0
    redundancy=len(rows)-rank
    if rank<6:issues.append('Completed assembly retains local unconstrained motion')
    if redundancy:issues.append('Redundant fixed contacts/bearings; review all actual constraints')
    singular=np.linalg.svd(matrix,compute_uv=False).tolist() if rows else []
    if rank==6 and singular[-1]/singular[0]<1e-4:unknown.append('Poor constraint conditioning')
    seating=rigid.get('seating_directions',{})
    for role in ('Primary','Secondary','Tertiary'):
        contacts=[c for c in spec.get('contacts',[]) if c.get('constraint_role','fixed_datum')=='fixed_datum' and c.get('role','').lower()==role.lower()]
        if not contacts:continue
        if role not in seating:unknown.append(role+': missing common seating direction');continue
        d=vector(seating[role],True)
        if any(float(d@vector(c['normal'],True))>=-1e-6 for c in contacts):issues.append(role+': seating does not close every fixed contact')
    status='fail' if issues else 'unknown' if unknown else 'pass'
    stage={'id':'inspect-completed-assembly','parts':parts,'required_rank':6,'rank':rank,'constraint_rows':len(rows),
        'redundant_rows':redundancy,'row_ids':names,'singular_values':singular,'status':status,'issues':issues,'unknowns':unknown}
    return {'status':status,'stages':[stage],'issues':issues,'scope':'Declared completed assembly treated as one rigid body; local rank only, not joint stiffness, force closure or physical pin-fit approval'}


def secondary_sides(spec):
    import copy
    from assembly_locating import secondary_sides
    s=copy.deepcopy(spec);s.pop('inspection',None)
    s['workpiece']['parts']={'CheckedAssembly':'Part_CheckedAssembly'}
    for c in s.get('contacts',[]):c['part']='CheckedAssembly'
    return secondary_sides(s)
