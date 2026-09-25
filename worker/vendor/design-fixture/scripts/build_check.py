#!/usr/bin/env python3
"""Build v8 construction plus checking geometry. Exit 0 complete concept, 1 failed, 2 incomplete."""
import argparse,copy,json
from pathlib import Path
from records import check,aggregate,sha256,digest,GEOMETRY_CHECKS
from fixture_common import write_json
from checking_offsets import generate
from check_gap_plan import screen


def build(spec_file,out,step=True,insertion=True,render=True,log=print):
    spec_file=Path(spec_file).resolve();out=Path(out).resolve()
    spec=json.loads(spec_file.read_text());original_spec=copy.deepcopy(spec);base=spec_file.parent
    input_geometry_digest=digest({k:v for k,v in spec.items() if k not in ('engineering_checks','checking_evidence')})
    plan=spec.get('inspection')
    result=screen(plan)
    if result['status']=='invalid':raise ValueError('Invalid checking plan: '+'; '.join(result['errors']))
    mode=plan['construction']
    if not spec.get('workpiece',{}).get('placed_step'):raise ValueError('Survey the STEP and supply placed_step before building')
    def absolute(name):return str((base/name).resolve()) if not Path(name).is_absolute() else name
    wp=spec['workpiece'];wp['placed_step']=absolute(wp['placed_step']);wp['source_files']=[absolute(x) for x in wp.get('source_files',[])]
    for c in spec.get('engineering_checks',[]):
        for e in c.get('evidence',[]):
            if isinstance(e,dict) and e.get('file'):e['file']=absolute(e['file'])
    for d in spec.get('printed_bodies',[]):
        if d.get('finished_step'):d['finished_step']=absolute(d['finished_step'])
    spec['checking_input']={'file':str(spec_file),'geometry_sha256':input_geometry_digest}
    work=out/'work';work.mkdir(parents=True,exist_ok=True)
    delivery=out/'DELIVERY'
    # Remove only previously manifested exports belonging to this project, including old print bodies.
    old=delivery/'JSON/fixture-design.json'
    if old.exists():
        previous=json.loads(old.read_text())
        if previous.get('project_id')!=spec.get('project_id'):raise ValueError('Output directory belongs to another project')
        for name in previous.get('export_sha256',{}):
            p=(delivery/name).resolve()
            if p.is_relative_to(delivery.resolve()) and p.is_file():p.unlink()
    generated=generate(spec) if mode=='laser_rib' else []
    if 'checking_ribs' in spec:spec['checking_rib_definitions']=spec.pop('checking_ribs')
    prepared=work/'prepared-spec.json';write_json(prepared,spec)
    if mode=='laser_rib':
        from build import build as base_build
        built=base_build(prepared,out,step,insertion,render,log)
    else:
        if not step:raise ValueError('Printed mode requires STEP export')
        from build_printed import build as printed_build
        built=printed_build(prepared,out,render,log)
    records={n:json.loads((delivery/'JSON'/n).read_text()) for n in ('project.json','fixture-design.json','hardware.json','verification.json')}
    project,design,hardware,ver=[records[k] for k in ('project.json','fixture-design.json','hardware.json','verification.json')]
    project['fixture_kind']='checking';project['construction']['mode']=mode
    project['requirements']['inspection_standard']={'nominal_gap_mm':3,'go_mm':2.5,'no_go_mm':3.5,'basis':'shop_standard; explicit station overrides retained'}
    original={'role':'checking_input','file':str(spec_file),'sha256':sha256(spec_file)}
    project['source']['records'].append(original);project['source']['files'].append(original['file']);project['source']['sha256'].append(original['sha256'])
    paths=list(delivery.glob('*.step'))
    if step and len(paths)==1:
        from checking_geometry import audit
        log('Checking-land and gauge-envelope CAD verification');audit_result=audit(spec,paths[0])
    else:
        audit_result={'status':'unknown','stations':[],'scope':'STEP unavailable for checking audit'}
    ver['measurements']['checking_geometry']=audit_result
    ver['measurements']['generated_checking_ribs']=generated
    ver['checks'].append(check('checking_geometry',audit_result['status'],audit_result,
        'nominal normal offsets at sampled lands; declared GO fits and NO-GO interferes at nominal part','mm',
        'Reopened CAD samples, not physical gauge calibration or continuous tool motion',['measurements.checking_geometry']))
    for name,scope in [('flange_coverage','Confirm measured source inventory covers every flange, including returns'),
        ('gauge_access','Verify full tools/hands and continuous approaches; working-end samples alone insufficient'),
        ('inspection_restraint','Verify seating does not conceal flange error'),
        ('gauge_error_budget','Qualify gauge manufacture, fixture error, wear and repeatability'),
        ('rib_profile_review','Review final plate profiles and justify every retained notch or relief')]:
        supplied=next((c for c in spec.get('checking_evidence',[]) if c.get('name')==name),None)
        from checking_evidence import qualify
        ver['checks'].append(qualify(supplied,name,scope,built['geometry_fingerprint'],base,plan,spec))
    design['inspection']=plan;design['checking_mode']=mode;design['checking_source_spec']=original_spec
    design['operator_sequence']=spec.get('operator_sequence',['Clean and locate','Seat gently on datums','GO must enter; NO-GO must not enter at every station','Release clamps and obstructing pins/details before unloading'])
    gauges={}
    for f in plan['flanges']:
        for s in f.get('checks',[]):
            if s['kind']!='alternative':
                pair=(s.get('go_mm',2.5),s.get('no_go_mm',3.5));gauges.setdefault(pair,[]).append(s['id'])
    hardware['items']+=spec.get('hardware_items',[])
    for i,((go,no_go),stations) in enumerate(gauges.items(),1):
        hardware['items'].append({'id':f'GAP-GAUGE-{i}','type':'metal GO/NO-GO working gauge','go_mm':go,'no_go_mm':no_go,
            'stations':stations,'manufacturing_tolerance':None,'calibration_status':'unknown','operation':'GO enters; NO-GO does not enter with light pressure'})
    if render and step:
        from checking_review import append_insets
        append_insets(paths[0],delivery,audit_result,plan)
    # Refresh image/mesh hashes after checking annotations and include only real exports.
    files=[p for p in delivery.rglob('*') if p.is_file() and 'JSON' not in p.relative_to(delivery).parts]
    design['export_sha256']={str(p.relative_to(delivery)):sha256(p) for p in files}
    ver['overall_status']=aggregate(c['status'] for c in ver['checks'])
    ver['geometry_status']=aggregate(c['status'] for c in ver['checks'] if c['name'] in GEOMETRY_CHECKS)
    ver['checking_geometry_status']=audit_result['status']
    ver['cad_verified']=ver['geometry_status']=='pass' and audit_result['status']=='pass'
    ver['fixture_calibrated']=False;ver['inspection_validated']=False;ver['fabrication_ready']=False
    ver['open_items']=[f"{c['name']}: {c['status']} — {c['scope']}" for c in ver['checks'] if c['status']!='pass']
    project['open_items']=ver['open_items'];ver['delivery_status']='unknown'
    for n,d in records.items():write_json(delivery/'JSON'/n,d)
    from validate_delivery import validate
    errors=validate(delivery,check_delivery_status=False)
    ver['delivery_status']='fail' if errors else 'pass'
    ver['fabrication_ready']=not errors and ver['overall_status']=='pass' and ver['cad_verified']
    write_json(delivery/'JSON/verification.json',ver)
    errors=validate(delivery)
    return {'delivery':str(delivery),'geometry_fingerprint':built['geometry_fingerprint'],
        'geometry_status':ver['geometry_status'],'checking_geometry_status':audit_result['status'],
        'overall_status':ver['overall_status'],'delivery_validation':errors,
        'exit_code':1 if ver['overall_status']=='fail' else 2 if errors else 0,'plates':built['plates']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('spec');p.add_argument('out')
    p.add_argument('--no-step',action='store_true');p.add_argument('--no-render',action='store_true');p.add_argument('--no-insertion',action='store_true')
    a=p.parse_args()
    try:
        r=build(a.spec,a.out,not a.no_step,not a.no_insertion,not a.no_render)
        print(json.dumps({k:v for k,v in r.items() if k!='plates'},indent=2));raise SystemExit(r['exit_code'])
    except (ValueError,AssertionError,KeyError,OSError) as e:print('BUILD FAILED:',e);raise SystemExit(1)
