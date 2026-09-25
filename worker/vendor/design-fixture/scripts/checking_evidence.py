"""Accept only current, attached engineering evidence for checking-specific decisions."""
import copy
import math
from pathlib import Path
from records import check,sha256


REQUIREMENTS=('flange_coverage','gauge_access','inspection_restraint','gauge_error_budget','rib_profile_review')


def positive(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0


def review_details(name,measured,spec,status):
    """Check evidence completeness, not independently prove the attached CAD/engineering work."""
    missing=lambda why:('unknown',why)
    failed=lambda why:('fail',why)
    def rows_for(key,id_key,expected):
        rows=measured.get(key)
        if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):return None
        ids=[r.get(id_key) for r in rows]
        if any(not isinstance(i,str) for i in ids):return None
        return rows if len(ids)==len(set(ids)) and set(ids)==expected else None
    if name=='inspection_restraint':
        supports={c['name'] for c in spec.get('contacts',[]) if c.get('role','').lower()=='primary'
                  and c.get('constraint_role','fixed_datum')=='fixed_datum'}
        rows=rows_for('primary_supports','support_id',supports)
        if not supports or rows is None:return missing('Map every primary datum support to its restraint')
        clamps={c['tag'] for c in spec.get('clamps',[])};used=set()
        for r in rows:
            tags=r.get('clamp_tags',[])
            if not isinstance(tags,list) or any(not isinstance(t,str) for t in tags):return missing('clamp_tags must be a list of tags')
            if r.get('mode')=='clamped':
                if not tags or not set(tags)<=clamps:return failed('Required hold-down is absent from clamp inventory')
                used.update(tags)
            elif r.get('mode')=='gravity_only':
                if tags:return failed('Gravity-only support also names a clamp')
            else:return missing('Declare clamped or justified gravity_only restraint')
            if not r.get('basis') or not r.get('load_path'):return missing('Restraint needs seating/load-path justification')
        if used!=clamps:return missing('Map every clamp to its supported seating region')
        if status=='pass' and (measured.get('seating_verified') is not True or
                              (clamps and measured.get('closed_pose_verified') is not True)):
            return missing('Pass requires verified seating and actual closed clamp pose')
        if status=='exception' and not measured.get('limitations'):return missing('Describe restraint exception limitations')
    elif name=='gauge_access':
        stations={s['id']:s for f in spec['inspection']['flanges'] for s in f.get('checks',[])}
        rows=rows_for('stations','station_id',set(stations))
        if rows is None:return missing('Supply full-tool access results for every station')
        if any(not isinstance(r.get('paths',[]),list) or any(not isinstance(p,dict) for p in r.get('paths',[])) for r in rows):
            return missing('Paths must be a list of GO/NO_GO route records')
        # Known blocked routes cannot be hidden by another incomplete station.
        if any(p.get('result')=='blocked' for r in rows for p in r.get('paths',[]) if isinstance(p,dict)):
            return failed('A required gauge route is physically blocked')
        for r in rows:
            if stations[r['station_id']]['kind']=='alternative':
                if not r.get('method') or not r.get('access_basis'):return missing('Alternative check needs usable access evidence')
                continue
            paths=r.get('paths',[])
            if len(paths)!=2 or {p.get('end') for p in paths}!={'GO','NO_GO'}:return missing('Check both GO and NO_GO routes')
            if not r.get('tool_id') or not positive(r.get('reach_mm')):return missing('Identify actual tool and reach')
            dims=r.get('envelopes_mm',{})
            if not isinstance(dims,dict):return missing('Supply component envelope dimensions')
            for component in ('working_end','stem','handle','hand'):
                size=dims.get(component)
                if not isinstance(size,list) or len(size)!=3 or not all(positive(x) for x in size):
                    return missing('Record full working-end, stem, handle and hand envelope dimensions')
            if r.get('part_clamped') is not True:return missing('Evaluate access in the declared inspection restraint state')
            if r.get('custom_tool') is not False and not all(r.get(k) for k in ('custom_tool_basis','rigidity_basis','handling_basis')):
                return missing('Custom/long-reach tool needs reach, rigidity and handling justification')
            for p in paths:
                expected='clear' if p['end']=='GO' else 'clear_to_stop'
                if p.get('result')!=expected or (p['end']=='NO_GO' and not p.get('expected_stop')):
                    return missing('Distinguish expected NO_GO measuring contact from blocked access')
                clearance=p.get('min_clearance_mm')
                if not isinstance(clearance,(int,float)) or isinstance(clearance,bool) or not math.isfinite(clearance):return missing('Measure route clearance')
                if clearance<0:return failed('Gauge route has negative clearance')
                if not p.get('method'):return missing('Record route checking method')
                if status=='pass' and p['method'] not in ('continuous','bounded_sampling'):
                    return missing('Unbounded discrete samples do not prove continuous access')
                if p['method']=='bounded_sampling' and not p.get('between_samples_bound'):return missing('Justify clearance between sampled poses')
            if status=='pass' and spec.get('clamps') and r.get('closed_pose_verified') is not True:
                return missing('Access pass requires actual closed clamp pose')
            if status=='exception' and not r.get('limitations'):return missing('Describe access exception limitations')
    elif name=='rib_profile_review':
        plates={p['name'] for p in spec.get('plates',[])}
        ids=measured.get('plate_ids',[])
        if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or set(ids)!=plates:return missing('Review every final plate profile')
        reliefs=measured.get('reliefs')
        if not isinstance(reliefs,list):return missing('Inventory profile reliefs, including an explicit empty list')
        for r in reliefs:
            if not isinstance(r,dict):return missing('Invalid relief record')
            if r.get('required') is False:return failed('Remove unnecessary profile relief before approval')
            if r.get('plate_id') not in plates or not r.get('feature_id') or not r.get('purpose') or r.get('required') is not True:
                return missing('Every retained relief needs an identified feature and function')
        if measured.get('final_profiles_reviewed') is not True:return missing('Inspect final CAD and fabrication profiles')
    return None


def qualify(supplied,name,scope,fingerprint,base,plan,spec=None):
    unknown=lambda why:check(name,'unknown',scope=scope+'; '+why)
    if not supplied:return unknown('Measured engineering evidence not supplied')
    c=copy.deepcopy(supplied)
    if c.get('status') not in ('pass','fail','unknown','exception'):raise ValueError(name+': invalid evidence status')
    if c['status'] in ('pass','exception'):
        if c.get('geometry_fingerprint')!=fingerprint:return unknown('Evidence is stale for this geometry')
        if not isinstance(c.get('measured'),dict) or not c['measured'] or not c.get('limit') or not c.get('scope') or not c.get('evidence'):return unknown('Evidence lacks measurements, limits or attachments')
        for e in c['evidence']:
            if not isinstance(e,dict) or not e.get('file') or not e.get('sha256'):return unknown('Attachment lacks file/hash')
            p=Path(e['file']);p=p if p.is_absolute() else Path(base)/p
            if not p.is_file() or sha256(p)!=e['sha256']:return unknown('Evidence attachment absent or changed')
            e['file']=str(p.resolve())
        if name!='rib_profile_review':
            required={f['id'] for f in plan['flanges']} if name=='flange_coverage' else {s['id'] for f in plan['flanges'] for s in f.get('checks',[])}
            field='flange_ids' if name=='flange_coverage' else 'station_ids'
            if set(c['measured'].get(field,[]))!=required:return unknown('Evidence must cover exact '+field)
        if name in ('gauge_access','inspection_restraint','rib_profile_review'):
            if spec is None:return unknown('Current design specification required for review')
            detail=review_details(name,c['measured'],spec,c['status'])
            if detail:
                c['status']=detail[0];c['scope']+='; '+detail[1]
                c['next_action']=detail[1]
    c.setdefault('measured',None);c.setdefault('limit',None);c.setdefault('scope',scope);c.setdefault('evidence',[])
    c.setdefault('units',None);c.setdefault('next_action',None if c['status']=='pass' else 'Resolve this check on the current geometry')
    return c
