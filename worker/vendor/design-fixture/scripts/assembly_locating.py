"""Staged coupled-body constraint screening; rank alone never proves force closure."""
import numpy as np
from records import aggregate


def fixed(c):
    return c.get('constraint_role','fixed_datum')=='fixed_datum'


def secondary_sides(spec):
    if spec.get('inspection',{}).get('rigid_assembly'):
        from checking_locating import secondary_sides as checking_sides
        return checking_sides(spec)
    rows=[]
    for part in spec.get('workpiece',{}).get('parts',{}):
        cs=[c for c in spec.get('contacts',[]) if c['part']==part and c.get('role','').lower()=='secondary' and fixed(c)]
        if len(cs)<2:continue
        alignment=min(float(np.dot(a['normal'],b['normal'])) for i,a in enumerate(cs) for b in cs[i+1:])
        exception=spec.get('assembly_locating',{}).get('secondary_exceptions',{}).get(part,{})
        status='pass' if alignment>.999 else 'exception' if exception.get('reason') and exception.get('seating_method') else 'fail'
        rows.append({'part':part,'contacts':[c['name'] for c in cs],'minimum_normal_alignment':alignment,'status':status,
           'exception':exception,'scope':'same-side, common-direction secondary datum default; stepped edges need not share the same plane',
           'next_action':None if status=='pass' else 'Use two same-side stops and define how the part seats; an exception needs an engineered seating method.'})
    return {'status':aggregate(r['status'] for r in rows) if rows else 'unknown','parts':rows}


def audit(spec):
    if spec.get('inspection',{}).get('rigid_assembly'):
        from checking_locating import audit as checking_audit
        return checking_audit(spec)
    plan=spec.get('assembly_locating');parts=set(spec.get('workpiece',{}).get('parts',{}))
    result={'status':'unknown','stages':[],'issues':[],'scope':'declared frictionless contacts in a coupled 6-DOF-per-body model; local rank and redundancy only, excludes preload, compliance and physical tolerance robustness'}
    if not plan:
        result['issues']=['Missing assembly locating plan: select master part, loading stages, fixture/mating contacts and seating directions.'];return result
    contacts={c['name']:c for c in spec.get('contacts',[])}
    mates={c['name']:c for c in plan.get('mating_contacts',[])}
    if len(mates)!=len(plan.get('mating_contacts',[])) or set(mates)&set(contacts):
        result['status']='fail';result['issues'].append('Contact identities must be unique across fixture and mating contacts.');return result
    if plan.get('master_part') not in parts or not plan.get('datum_rationale'):
        result['issues'].append('Known master part and datum rationale are required.')
    stages=plan.get('loading_stages',[])
    if not stages:result['issues'].append('No loading stages defined.');return result
    prior=set();stage_ids=set()
    for stage in stages:
        ids=stage.get('parts',[]);active=set(ids);issues=[];unknown=[]
        if not stage.get('id') or stage['id'] in stage_ids:issues.append('Stage IDs must be unique and nonempty.')
        stage_ids.add(stage.get('id'))
        if len(active)!=len(ids) or not active or not active<=parts or not prior<=active:issues.append('Stage parts must be known, unique, nonempty and cumulative.')
        if not prior and plan.get('master_part') not in active:issues.append('First stage must include the master part.')
        keys=stage.get('fixture_contacts',[]);mk=stage.get('mating_contacts',[])
        if len(set(keys))!=len(keys) or len(set(mk))!=len(mk) or set(keys)-set(contacts) or set(mk)-set(mates):issues.append('Stage contains duplicate or unknown contacts.')
        if issues:
            result['stages'].append({'id':stage.get('id'),'status':'fail','issues':issues});prior=active;continue
        fs=[contacts[k] for k in keys];ms=[mates[k] for k in mk]
        if any(c['part'] not in active for c in fs) or any(c.get('part_a') not in active or c.get('part_b') not in active or c.get('part_a')==c.get('part_b') for c in ms):
            result['stages'].append({'id':stage['id'],'status':'fail','issues':['Contact references an absent or identical mating body.']});prior=active;continue
        for c in fs:
            role=c.get('constraint_role')
            if role not in ('fixed_datum','auxiliary_support'):unknown.append(f"{c['name']}: declare fixed_datum or auxiliary_support")
            if role=='auxiliary_support':
                if c.get('support_mode') not in ('adjustable_after_seating','floating','relieved') or not c.get('activation_sequence'):
                    issues.append(f"{c['name']}: extra support needs a non-competing mode and activation sequence")
        pts=[c['contact'] for c in fs+ms]
        origin=np.mean(pts,axis=0) if pts else np.zeros(3);length=max(float(np.linalg.norm(np.ptp(pts,axis=0))),1) if pts else 1
        order=sorted(active);index={p:i for i,p in enumerate(order)};matrix=[];row_names=[];used=[]
        def row(p,n,part):
            n=np.asarray(n,float);p=np.asarray(p,float)
            if n.shape!=(3,) or not np.isfinite(n).all() or not np.isclose(np.linalg.norm(n),1) or p.shape!=(3,) or not np.isfinite(p).all():raise ValueError('Contact point and unit normal must be finite 3-vectors')
            r=np.zeros(6*len(order));j=index[part]*6;r[j:j+6]=np.r_[n,np.cross(p-origin,n)/length];return r
        for c in fs:
            if not fixed(c):continue
            matrix.append(row(c['contact'],c['normal'],c['part']));row_names.append(c['name']);used.append(c)
        for c in ms:
            n=c['normal_on_a'];matrix.append(row(c['contact'],n,c['part_a'])-row(c['contact'],n,c['part_b']));row_names.append(c['name'])
        a=np.array(matrix) if matrix else np.zeros((0,6*len(order)));rank=int(np.linalg.matrix_rank(a)) if len(a) else 0;required=6*len(order);redundant=len(a)-rank
        sv=np.linalg.svd(a,compute_uv=False).tolist() if len(a) else []
        dependencies=[]
        if redundant:
            for i,name in enumerate(row_names):
                if np.linalg.matrix_rank(np.delete(a,i,axis=0))==rank:dependencies.append(name)
            issues.append('Redundant fixed constraints: review mating contacts and convert genuinely auxiliary supports to an appropriate support mode.')
        if rank<required:issues.append('At least one loaded body retains unconstrained local motion.')
        if rank==required and sv[-1]/sv[0]<1e-4:unknown.append('Poor constraint conditioning; review contact spacing.')
        # Each declared fixture datum family has a common direction for seating into its stops.
        for part in order:
            for role in ('Primary','Secondary','Tertiary'):
                group=[c for c in used if c['part']==part and c.get('role','').lower()==role.lower()]
                if not group:continue
                direction=stage.get('seating_directions',{}).get(part,{}).get(role)
                if direction is None:unknown.append(f'{part} {role}: missing seating direction');continue
                v=np.asarray(direction,float)
                if v.shape!=(3,) or not np.isfinite(v).all() or not np.isclose(np.linalg.norm(v),1):issues.append(f'{part} {role}: seating direction must be a unit vector');continue
                if any(np.dot(v,c['normal'])>=-1e-6 for c in group):issues.append(f'{part} {role}: declared seating direction does not drive every stop contact closed')
        state='fail' if issues else 'unknown' if unknown else 'pass'
        result['stages'].append({'id':stage['id'],'parts':order,'constraint_rows':len(a),'required_rank':required,'rank':rank,'redundant_rows':redundant,'dependent_contacts':dependencies,'singular_values':sv,'origin':origin.tolist(),'characteristic_length_mm':length,'fixture_contacts':keys,'mating_contacts':mk,'status':state,'issues':issues,'unknowns':unknown})
        prior=active
    if prior!=parts:result['issues'].append('Final loading stage does not cover every workpiece.')
    # Omitted physical fixed contacts must not silently disappear from the staged model.
    last=stages[-1];omitted=[c['name'] for c in contacts.values() if fixed(c) and c['name'] not in last.get('fixture_contacts',[])]
    omitted_mates=set(mates)-set(last.get('mating_contacts',[]))
    if omitted or omitted_mates:result['issues'].append('Final stage omits declared fixed/mating contacts: '+', '.join(omitted+sorted(omitted_mates)))
    stage_status=aggregate(s['status'] for s in result['stages'])
    result['status']='fail' if stage_status=='fail' else 'unknown' if result['issues'] else stage_status
    return result


def mating_geometry(spec,resolved):
    from verify import face_contact
    rows=[]
    for m in spec.get('assembly_locating',{}).get('mating_contacts',[]):
        checks=[]
        for side,sign in [('a',1),('b',-1)]:
            _,target=resolved.get(m['part_'+side],(None,None))
            c={'contact':m['contact'],'normal':[sign*x for x in m['normal_on_a']]}
            if m.get('face_'+side):c['face']=m['face_'+side]
            checks.append(face_contact(c,target) if target is not None else {'status':'fail','reason':'missing mating body'})
        rows.append({'name':m['name'],'part_a':m['part_a'],'part_b':m['part_b'],'faces':checks,'status':aggregate(c['status'] for c in checks)})
    return {'status':aggregate(r['status'] for r in rows) if rows else 'pass','contacts':rows,'scope':'declared nominal mating contacts checked on both trimmed faces; does not detect all undeclared mating contacts or prove tolerance compatibility'}
