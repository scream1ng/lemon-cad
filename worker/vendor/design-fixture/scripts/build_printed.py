"""Printed construction backend reusing v8 STEP, hardware, evidence and rendering utilities."""
import copy,json
from pathlib import Path
import numpy as np
from records import REQUIRED_CHECKS,GEOMETRY_CHECKS,ENGINEERING_CHECKS,check,aggregate,sha256,digest
from fixture_common import write_json,spec_path
from export_step import read_step,write_step
from verify import gap,volume,common_volume,bbox,bbox_overlap,face_contact,constraint_rank
from hardware_geometry import rigid,definition,asset_path


def build(spec_file,out,render=True,log=print):
    spec=json.loads(Path(spec_file).read_text());spec['_dir']=str(Path(spec_file).resolve().parent)
    if spec.get('units')!='mm' or not spec.get('project_id') or not spec.get('revision'):raise ValueError('Printed spec needs mm, project_id and revision')
    pid=spec['project_id']
    if '/' in pid or '\\' in pid or pid in ('.','..'):raise ValueError('Invalid project_id')
    from printed_body import build_shapes,export_meshes
    bodies,body_report=build_shapes(spec)
    if not bodies:raise ValueError('At least one printed body is required')
    wp=spec.get('workpiece',{})
    if not wp.get('placed_step') or not wp.get('source_files'):raise ValueError('Original STEP sources and placed_step required')
    shapes=read_step(spec_path(spec,wp['placed_step']))
    if any(not k.split('/')[-1].startswith(('Part_','REF_')) for k in shapes):raise ValueError('Placed STEP must use Part_ or REF_ names')
    if set(shapes)&set(bodies):raise ValueError('Duplicate fixture/workpiece identities')
    shapes.update(bodies)
    sources=[{'role':'design_spec','file':str(Path(spec_file).resolve()),'sha256':sha256(spec_file)}]
    for role,paths in [('original_source',wp['source_files']),('placed_cad',[wp['placed_step']])]:
        for name in paths:
            p=spec_path(spec,name);sources.append({'role':role,'file':str(p),'sha256':sha256(p)})
    for body in spec.get('printed_bodies',[]):
        if body.get('finished_step'):
            p=spec_path(spec,body['finished_step']);sources.append({'role':'finished_body','file':str(p),'sha256':sha256(p)})
    height_rows=[];hardware=[];tags=set()
    for c in spec.get('clamps',[]):
        if c['tag'] in tags:raise ValueError('Duplicate clamp tag')
        tags.add(c['tag']);h=definition(c['hardware']);asset=asset_path(c['hardware'])
        matrix=np.array(c['mount_transform'],float)@np.array(h['asset']['source_to_canonical'],float)
        imported=read_step(asset)
        if set(imported)!=set(h['asset']['components']):raise ValueError('Hardware asset components changed')
        for name,sh in imported.items():
            key=f"HW_{c['tag']}_{name}"
            if key in shapes:raise ValueError('Duplicate hardware solid')
            shapes[key]=rigid(sh,matrix)
        sources.append({'role':'hardware_asset','file':str(asset),'sha256':sha256(asset)})
        hardware.append(h)
        height_rows.append({'tag':c['tag'],'mount_plate':c.get('mount_plate',c.get('mount_body')),'status':'unknown',
            'reason':'Printed-body mount: actual support plane, locked pose, insert retention and spindle range require measured evidence'})
    # Include original input specification identity without making engineering evidence self-referential.
    source=copy.deepcopy(spec);source.pop('_dir',None)
    fp=digest({'spec':{k:v for k,v in source.items() if k not in ('engineering_checks','checking_evidence')},'sources':[r for r in sources if r['role']!='design_spec']})
    delivery=Path(out)/'DELIVERY';work=Path(out)/'work';(delivery/'JSON').mkdir(parents=True,exist_ok=True);work.mkdir(parents=True,exist_ok=True)
    step=delivery/f'{pid}-fixture-assembly.step';write_step(step,shapes);actual=read_step(step)
    from OCP.BRepCheck import BRepCheck_Analyzer
    invalid=[k for k,s in actual.items() if not BRepCheck_Analyzer(s).IsValid()]
    contacts=[]
    for c in spec.get('contacts',[]):
        part=wp.get('parts',{}).get(c['part']);own=c.get('rib')
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
        from OCP.gp import gp_Pnt
        vertex=BRepBuilderAPI_MakeVertex(gp_Pnt(*c['contact'])).Vertex()
        d=gap(vertex,actual[own]) if own in actual else None
        face=face_contact(c,actual[part]) if part in actual else {'status':'fail','reason':'Missing part'}
        contacts.append({'id':c['name'],'own':own,'part':part,'own_geometry_gap_mm':d,'face_check':face,
            'status':'pass' if d is not None and d<.01 and face['status']=='pass' else 'fail'})
    intersections=[]
    parts={k:s for k,s in actual.items() if k.split('/')[-1].startswith('Part_')}
    for name in bodies:
        for pn,ps in parts.items():
            if bbox_overlap(bbox(actual[name]),bbox(ps)):
                cv=common_volume(actual[name],ps)
                if cv>1e-4:intersections.append({'body':name,'part':pn,'volume_mm3':cv})
    roundtrip=[]
    for n,shape in bodies.items():
        delta=max(0,volume(shape)+volume(actual[n])-2*common_volume(shape,actual[n]))
        roundtrip.append({'name':n,'symmetric_volume_error_mm3':delta,'status':'pass' if delta<.001 else 'fail'})
    ranks=constraint_rank(spec)
    measured={'solid_integrity':('fail' if invalid else 'pass',invalid),
        'contacts':(aggregate(c['status'] for c in contacts),contacts),
        'interference':('fail' if intersections else 'pass',intersections),
        'step_roundtrip':(aggregate(r['status'] for r in roundtrip),roundtrip)}
    checks=[]
    supplied={c['name']:c for c in spec.get('engineering_checks',[])}
    if set(supplied)-set(ENGINEERING_CHECKS):raise ValueError('Unsupported printed engineering check')
    for name in REQUIRED_CHECKS:
        if name in measured:
            status,value=measured[name];checks.append(check(name,status,value,'see printed CAD report','mm','Reopened printed-body CAD',['measurements.printed_cad']))
        else:
            c=copy.deepcopy(supplied.get(name,check(name,'unknown',scope='Explicit printed-fixture evidence required; inherited steel-only checks are not assumed applicable')))
            if c.get('status') not in ('pass','fail','unknown','exception'):raise ValueError('Invalid engineering status')
            if c['status'] in ('pass','exception'):
                valid=c.get('geometry_fingerprint')==fp and c.get('evidence') and c.get('scope') and c.get('limit') and c.get('measured') is not None
                if valid:
                    for e in c['evidence']:
                        if not isinstance(e,dict) or not e.get('file') or not e.get('sha256'):valid=False;break
                        p=spec_path(spec,e['file'])
                        if not p.is_file() or sha256(p)!=e['sha256']:valid=False;break
                from construction_checks import evidence_errors
                if not valid or evidence_errors(c,source,fp,set(actual)):
                    c=check(name,'unknown',scope='Missing, stale or incomplete printed-fixture engineering evidence')
            c.setdefault('units',None);c.setdefault('next_action',None if c['status']=='pass' else 'Resolve this check on final geometry')
            checks.append(c)
    # Report local rank but never claim coverage without checking every workpiece and finite pin clearances.
    cad={'invalid_solids':invalid,'contacts':contacts,'part_intersections':intersections,'export_comparison':roundtrip,'constraints':ranks,
        'mounting_height':{'status':'unknown','clamps':height_rows},'scope':'Printed-body geometry; hardware operation/whole loading not verified'}
    if render:
        from render_review import render as render_views
        render_views(step,delivery,spec['revision'],mount_heights=cad['mounting_height'])
    mesh_report=export_meshes(bodies,delivery/'PRINT',linear_deflection_mm=float(spec.get('print_settings',{}).get('linear_deflection_mm',.05)))
    files=[p for p in delivery.rglob('*') if p.is_file() and 'JSON' not in p.relative_to(delivery).parts]
    manifest={str(p.relative_to(delivery)):sha256(p) for p in files}
    head={'schema_version':'1.2','project_id':pid,'revision':spec['revision']}
    open_items=[f"{c['name']}: {c['status']}" for c in checks if c['status']!='pass']
    records={
      'project.json':head|{'units':'mm','source':{'records':sources,'files':[x['file'] for x in sources],'sha256':[x['sha256'] for x in sources]},
          'geometry_fingerprint':fp,'construction':{'mode':'printed_solid'},'requirements':spec.get('requirements',{}),
          'assumptions':spec.get('assumptions',[]),'open_items':open_items},
      'fixture-design.json':head|{'coordinate_frame':{'units':'mm','source_to_fixture':wp.get('source_to_fixture')},
          'workpieces':[{'id':k,'shape_name':v} for k,v in wp.get('parts',{}).items()], 'datums':spec.get('locating_groups',{}),
          'locators':spec.get('contacts',[]),'supports':spec.get('supports',[]),'clamps':spec.get('clamps',[]),
          'components':[{'name':k,'role':'printed body'} for k in bodies], 'tabs_slots':[],'design_spec':source,
          'geometry_fingerprint':fp,'export_files':{'step':step.name,'dxf':None},'export_sha256':manifest,'print_meshes':mesh_report},
      'hardware.json':head|{'items':hardware},
      'verification.json':head|{'geometry_revision':spec['revision'],'geometry_fingerprint':fp,'checks':checks,
          'geometry_status':aggregate(c['status'] for c in checks if c['name'] in GEOMETRY_CHECKS),
          'overall_status':aggregate(c['status'] for c in checks),'delivery_status':'unknown','fabrication_ready':False,
          'measurements':{'cad_audit':cad,'printed_cad':cad,'printed_body':body_report,'print_meshes':mesh_report},'open_items':open_items}}
    for name,data in records.items():write_json(delivery/'JSON'/name,data)
    return {'delivery':str(delivery),'geometry_fingerprint':fp,'exit_code':1 if any(c['status']=='fail' for c in checks) else 0,'plates':[],'cad':cad}
