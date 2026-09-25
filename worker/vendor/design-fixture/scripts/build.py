#!/usr/bin/env python3
"""Build a review delivery. Exit 0: complete concept package; 1: failed check; 2: incomplete package.
Unknown engineering checks remain visible and never confer fabrication approval.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import audit_width
import cap_joints
import clamp_mount
import nest_dxf
import tabs_slots
from fixture_common import load_spec,write_json,spec_path
from records import GEOMETRY_CHECKS,ENGINEERING_CHECKS,aggregate,sha256,digest,check

HERE=Path(__file__).resolve().parent

def input_records(spec_file,spec):
    rows=[{'role':'design_spec','file':str(Path(spec_file).resolve()),'sha256':sha256(spec_file)}]
    wp=spec.get('workpiece',{})
    for role,items in (('original_source',wp.get('source_files',[])),('placed_cad',[wp['placed_step']] if wp.get('placed_step') else [])):
        for item in items:
            p=spec_path(spec,item)
            if not p.is_file():raise ValueError(f'missing {role}: {p}')
            rows.append({'role':role,'file':str(p),'sha256':sha256(p)})
    for hw in sorted({c['hardware'] for c in spec.get('clamps',[])}):
        p=HERE.parent/'references/hardware'/f'{hw.lower()}.json'
        rows.append({'role':'hardware_definition','file':str(p),'sha256':sha256(p)})
        from hardware_geometry import asset_path
        asset=asset_path(hw)
        rows.append({'role':'hardware_asset','file':str(asset),'sha256':sha256(asset)})
    return rows

def build(spec_file,out,step=True,insertion=True,render=True,log=print):
    spec=load_spec(spec_file);source=copy.deepcopy(spec);source.pop('_dir',None)
    sources=input_records(spec_file,spec)
    # Manual evidence excluded to avoid a self-referential fingerprint; geometry/source content included.
    geometry_input={k:v for k,v in source.items() if k not in ('engineering_checks','checking_evidence')}
    fingerprint=digest({'spec':geometry_input,'sources':[{'role':r['role'],'sha256':r['sha256']} for r in sources if r['role']!='design_spec']})
    spec['_geometry_fingerprint']=fingerprint
    pid,rev=spec['project_id'],spec['revision'];work,delivery=Path(out)/'work',Path(out)/'DELIVERY'
    (delivery/'JSON').mkdir(parents=True,exist_ok=True);work.mkdir(parents=True,exist_ok=True)
    # Clear only this build's named outputs so skipped export/render cannot reuse stale files.
    dxf=delivery/f'{pid}-fixture-cutting.dxf';step_path=delivery/f'{pid}-fixture-assembly.step'
    for p in (dxf,step_path,delivery/'assembled.png',delivery/'empty-fixture.png'):
        if p.exists():p.unlink()
    log('cap joints');caps=cap_joints.design(spec,log)
    log('tabs/slots');tabs=tabs_slots.design(spec,log)
    log('clamp mounts');clamps=clamp_mount.mount(spec)
    import mount_compactness
    compact=mount_compactness.audit(spec)
    import cross_support
    crossing=cross_support.audit(spec)
    log('width audit');width=audit_width.audit(spec,tabs['tabs'])
    log('nest + DXF');nest=nest_dxf.nest(spec,dxf)
    cad=None
    if step:
        import export_step,verify
        log('STEP export');export_step.export(spec,step_path)
        log('CAD verification');cad=verify.verify(spec,step_path,insertion,log)
        if render:
            from render_review import render as render_views
            log('review images');render_views(step_path,delivery,rev,mount_heights=cad['mounting_height'])
    details={'cap_joints':caps,'tab_slot_design':tabs,'clamp_mounts':clamps,'width_audit':width,'cutting_audit':nest,'cad_audit':cad,'mount_compactness':compact,'cross_support':crossing}
    for name,data in details.items():write_json(work/f'{name}.json',data)
    write_json(work/'plates.json',spec['plates'])
    checks=[check('tab_slot_seat_bridge','pass' if tabs['minimum_seat_cutout_bridge_mm']>=tabs['params']['min_bridge_mm']-1e-6 else 'fail',
                  tabs['minimum_seat_cutout_bridge_mm'],tabs['params']['min_bridge_mm'],'mm','distance between seat cutouts',['measurements.tab_slot_design']),
            check('material_width',width['status'],width,{'minimum_mm':spec.get('min_width_mm',10)},'mm',width['scope'],['measurements.width_audit']),
            check('nest',nest['status'],nest,{'gap_mm':nest['gap_limit_mm']},'mm','heuristic single-sheet packing and DXF roundtrip',['measurements.cutting_audit']),
            check('clamp_mounts',aggregate(c['status'] for c in clamps),clamps,'fit, preserved cutouts, supported footprint, verified adjustment','mm',
                  'mounting geometry; clamp seating/motion/strength remain separate',['measurements.clamp_mounts'])]
    checks.append(check('cross_support',crossing['status'],crossing,'every seated upright crossed by a perpendicular member',None,crossing['scope'],['measurements.cross_support']))
    checks.append(check('mount_compactness',compact['status'],compact,'justify platform extensions and compare compact alternatives','mm','hardware and joint feature sizing screen',['measurements.mount_compactness']))
    for name in GEOMETRY_CHECKS:
        if name in {c['name'] for c in checks}:continue
        checks.append(check(name,cad['check_statuses'][name] if cad else 'unknown',
                            ({'status':cad['check_statuses'][name], 'report':'measurements.cad_audit'} if cad else None),'see measured CAD report','mm' if name in ('contacts','fixture_insertion','mounting_height') else None,
                            'reopened export; fixture insertion covers sampled poses only',['measurements.cad_audit'] if cad else []))
    supplied={c['name']:c for c in spec.get('engineering_checks',[])}
    if set(supplied)-set(ENGINEERING_CHECKS):raise ValueError('engineering_checks contains an unsupported check name')
    for name in ENGINEERING_CHECKS:
        c=copy.deepcopy(supplied.get(name,check(name,'unknown',scope='requires measured engineering evidence')))
        if c.get('status') not in ('pass','fail','unknown','exception'):raise ValueError(f'{name}: invalid status')
        if c.get('status') in ('pass','exception'):
            if c.get('geometry_fingerprint')!=fingerprint or not c.get('evidence') or not c.get('scope') or not c.get('limit') or c.get('measured') is None:
                c=check(name,'unknown',scope='evidence absent, incomplete, or stale for this geometry')
            else:
                attachments=[]
                for e in c['evidence']:
                    if not isinstance(e,dict) or not e.get('file') or not e.get('sha256'):raise ValueError(f'{name}: evidence must identify a file and sha256')
                    p=spec_path(spec,e['file'])
                    if not p.is_file() or sha256(p)!=e['sha256']:raise ValueError(f'{name}: evidence file hash mismatch')
                    attachments.append(e)
                c['evidence']=attachments
        from construction_checks import evidence_errors
        gate_errors=evidence_errors(c,source,fingerprint)
        if gate_errors:
            c=check(name,'unknown',scope='; '.join(gate_errors))
        c.setdefault('units',None);c.setdefault('next_action',None if c['status']=='pass' else 'Resolve this engineering check.')
        checks.append(c)
    if not spec.get('workpiece',{}).get('source_files') or spec.get('workpiece',{}).get('source_to_fixture') is None:
        checks=[check('source_survey','unknown',scope='original source files or source-to-fixture rigid transform missing') if c['name']=='source_survey' else c for c in checks]
    geometry=aggregate(c['status'] for c in checks if c['name'] in GEOMETRY_CHECKS)
    overall=aggregate(c['status'] for c in checks)
    head={'schema_version':'1.2','project_id':pid,'revision':rev}
    open_items=[f"{c['name']}: {c['status']} — {c.get('next_action') or c.get('scope','')}" for c in checks if c['status']!='pass']
    export_hashes={p.name:sha256(p) for p in (dxf,step_path,delivery/'assembled.png',delivery/'empty-fixture.png') if p.is_file()}
    hardware=sorted({c['hardware'] for c in spec.get('clamps',[])})
    records={
      'project.json':head|{'units':'mm','source':{'files':[r['file'] for r in sources],'sha256':[r['sha256'] for r in sources],'records':sources},
          'geometry_fingerprint':fingerprint,'construction':{'mode':'laser-cut-tab-slot','sheet_thickness_mm':spec['thickness_mm']},
          'requirements':source.get('requirements',{})|{'min_width_mm':spec.get('min_width_mm',10)},
          'assumptions':source.get('assumptions',[]),'open_items':open_items},
      'fixture-design.json':head|{'coordinate_frame':{'name':'fixture','units':'mm','source_to_fixture':spec.get('workpiece',{}).get('source_to_fixture')},
          'workpieces':[{'id':key,'shape_name':val} for key,val in spec.get('workpiece',{}).get('parts',{}).items()],
          'datums':spec.get('locating_groups',{}),'locators':source['contacts'],'supports':source.get('supports',[]),'clamps':clamps,'assembly_locating':source.get('assembly_locating',{}),
          'components':spec['plates'],'tabs_slots':tabs['tabs'],'retention':source.get('retention',[]),
          'design_spec':source,'geometry_fingerprint':fingerprint,'export_files':{'dxf':dxf.name,'step':step_path.name if step else None},'export_sha256':export_hashes},
      'hardware.json':head|{'items':[json.loads((HERE.parent/'references/hardware'/f'{h.lower()}.json').read_text()) for h in hardware]},
      'verification.json':head|{'geometry_revision':rev,'geometry_fingerprint':fingerprint,'checks':checks,'geometry_status':geometry,
          'overall_status':overall,'delivery_status':'unknown','fabrication_ready':False,'measurements':details,'open_items':open_items}
    }
    for name,data in records.items():write_json(delivery/'JSON'/name,data)
    from validate_base_delivery import validate
    errors=validate(delivery,check_delivery_status=False)
    records['verification.json']['delivery_status']='fail' if errors else 'pass'
    records['verification.json']['fabrication_ready']=overall=='pass' and not errors
    write_json(delivery/'JSON/verification.json',records['verification.json'])
    errors=validate(delivery)
    return {'overall_status':overall,'geometry_status':geometry,'geometry_fingerprint':fingerprint,'delivery_validation':errors,
            'exit_code':1 if overall=='fail' else 2 if errors else 0,'cad':cad,'plates':spec['plates'],'joints':spec['joints'],'delivery':str(delivery)}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('spec');ap.add_argument('out');ap.add_argument('--no-step',action='store_true');ap.add_argument('--no-insertion',action='store_true');ap.add_argument('--no-render',action='store_true')
    a=ap.parse_args()
    try:
        r=build(a.spec,a.out,not a.no_step,not a.no_insertion,not a.no_render)
        print(json.dumps({k:v for k,v in r.items() if k not in ('cad','plates','joints')},indent=2))
        raise SystemExit(r['exit_code'])
    except (ValueError,AssertionError,KeyError) as exc:
        print(f'BUILD FAILED: {exc}');raise SystemExit(1)
