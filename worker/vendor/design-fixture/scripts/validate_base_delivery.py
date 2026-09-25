#!/usr/bin/env python3
"""Validate delivery structure, record semantics, real exports and revision/hash consistency.
A valid concept delivery can contain unknown engineering checks; inspect fabrication_ready separately.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from records import REQUIRED_CHECKS,GEOMETRY_CHECKS,STATUSES,aggregate,sha256

TYPES={
 'project.json':{'units':str,'source':dict,'construction':dict,'requirements':dict,'assumptions':list,'open_items':list,'geometry_fingerprint':str},
 'fixture-design.json':{'coordinate_frame':dict,'workpieces':list,'datums':dict,'locators':list,'supports':list,'clamps':list,'components':list,'tabs_slots':list,'export_files':dict,'export_sha256':dict,'design_spec':dict,'geometry_fingerprint':str},
 'hardware.json':{'items':list},
 'verification.json':{'geometry_revision':str,'checks':list,'overall_status':str,'geometry_status':str,'delivery_status':str,'fabrication_ready':bool,'measurements':dict,'open_items':list,'geometry_fingerprint':str}
}
REQUIRED_JSON_KEYS={k:set(v)|{'schema_version','project_id','revision'} for k,v in TYPES.items()}
FORBIDDEN_SUFFIXES={'.blend','.html','.htm','.csv','.xlsx','.xls'}

def status_errors(value,path='$'):
    errors=[]
    if isinstance(value,dict):
        for key,child in value.items():
            if key in ('status','overall_status','geometry_status','delivery_status','sample_status') and (not isinstance(child,str) or child not in STATUSES):
                errors.append(f'{path}.{key}: invalid check status')
            errors+=status_errors(child,f'{path}.{key}')
    elif isinstance(value,list):
        for i,child in enumerate(value):errors+=status_errors(child,f'{path}[{i}]')
    return errors

def validate(root,*,allow_no_dxf=False,allow_supplementary=False,check_delivery_status=True,additional_exports=()):
    root=Path(root);errors=[]
    if not root.is_dir():return ['delivery directory does not exist']
    dxfs=[p for p in root.iterdir() if p.suffix.lower()=='.dxf' and p.is_file()]
    steps=[p for p in root.iterdir() if p.suffix.lower() in ('.step','.stp') and p.is_file()]
    pngs=[p for p in root.iterdir() if p.suffix.lower()=='.png' and p.is_file()]
    if len(dxfs)!=1 and not (allow_no_dxf and not dxfs):errors.append('expected exactly one DXF')
    if len(steps)!=1:errors.append('expected exactly one STEP')
    if {p.name for p in pngs}!={'assembled.png','empty-fixture.png'}:errors.append('expected assembled.png and empty-fixture.png')
    if not allow_supplementary:
        forbidden=[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.suffix.lower() in FORBIDDEN_SUFFIXES]
        if forbidden:errors.append('forbidden routine files: '+', '.join(forbidden))
    if {p.name for p in (root/'JSON').glob('*.json')}!=set(TYPES):errors.append('expected exactly the four contract JSON files')
    records={}
    for name,fields in TYPES.items():
        try:
            data=json.loads((root/'JSON'/name).read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON number')))
            if not isinstance(data,dict):raise ValueError('root must be an object')
        except (OSError,ValueError) as exc:
            errors.append(f'{name}: {exc}');continue
        records[name]=data
        for field,typ in fields.items():
            if not isinstance(data.get(field),typ):errors.append(f'{name}: {field} must be {typ.__name__}')
        for field in ('project_id','revision'):
            if not isinstance(data.get(field),str) or not data[field].strip():errors.append(f'{name}: {field} must be nonempty')
        if data.get('schema_version')!='1.2':errors.append(f'{name}: schema_version must be 1.2; rebuild older records')
        errors+=status_errors(data,name)
    # Invalid field types must yield errors rather than crashing later validation.
    if len(records)!=4 or any(not isinstance(d.get(k),t) for n,d in records.items() for k,t in TYPES[n].items()):return errors
    for field in ('project_id','revision'):
        if len({str(d.get(field)) for d in records.values()})!=1:errors.append(f'inconsistent {field}')
    project,design,ver=records['project.json'],records['fixture-design.json'],records['verification.json']
    if project['units']!='mm':errors.append('units must be mm')
    if ver['geometry_revision']!=ver['revision']:errors.append('geometry_revision differs from revision')
    fp=project['geometry_fingerprint']
    if not re.fullmatch('[0-9a-f]{64}',fp) or any(d.get('geometry_fingerprint')!=fp for d in (design,ver)):errors.append('invalid/inconsistent geometry fingerprint')
    source=project['source']
    rows=source.get('records')
    if not isinstance(rows,list) or not rows:errors.append('source.records must be a nonempty list')
    else:
        for row in rows:
            if not isinstance(row,dict) or not row.get('file') or not row.get('role') or not re.fullmatch('[0-9a-f]{64}',str(row.get('sha256',''))):errors.append('invalid source record')
        if source.get('files')!=[r.get('file') for r in rows if isinstance(r,dict)] or source.get('sha256')!=[r.get('sha256') for r in rows if isinstance(r,dict)]:errors.append('source lists disagree with source records')
    checks=ver['checks'];by={}
    for c in checks:
        if not isinstance(c,dict):errors.append('check must be an object');continue
        name=c.get('name')
        if not isinstance(name,str):errors.append('check name must be a string');continue
        if name in by:errors.append(f'duplicate check: {name}')
        by[name]=c
        for field in ('status','measured','limit','units','scope','evidence','next_action'):
            if field not in c:errors.append(f'{name}: missing {field}')
        if not isinstance(c.get('evidence'),list) or not isinstance(c.get('scope'),str):errors.append(f'{name}: invalid evidence/scope')
        if c.get('status')=='pass' and (not c.get('evidence') or c.get('measured') is None or c.get('limit') is None):errors.append(f'{name}: pass requires measurements, acceptance limit and evidence')
    from construction_checks import evidence_errors
    for c in by.values():
        errors.extend(evidence_errors(c,design['design_spec'],fp))
    for name in REQUIRED_CHECKS:
        if name not in by:errors.append(f'missing required check: {name}')
    if ver['overall_status']!=aggregate(c.get('status') for c in by.values()):errors.append('overall_status disagrees with check statuses')
    if ver['geometry_status']!=aggregate(by.get(k,{}).get('status','unknown') for k in GEOMETRY_CHECKS):errors.append('geometry_status disagrees with geometry checks')
    if ver['overall_status']=='pass' and ver['open_items']:errors.append('overall pass cannot have unresolved open items')
    if ver['fabrication_ready'] and (ver['overall_status']!='pass' or ver['delivery_status']!='pass'):errors.append('fabrication_ready requires all checks and delivery to pass')
    if check_delivery_status and ver['delivery_status']!='pass':errors.append('delivery_status is not pass')
    declared=design['design_spec'].get('clamps',[])
    height=ver['measurements'].get('cad_audit',{}) or {}
    height=height.get('mounting_height',{})
    if steps and declared:
        measured=height.get('clamps')
        if not isinstance(measured,list) or sorted(r.get('tag','') for r in measured if isinstance(r,dict))!=sorted(c['tag'] for c in declared):
            errors.append('mounting_height: missing per-clamp exported-CAD measurements')
        elif height.get('status')!=by.get('mounting_height',{}).get('status') or height.get('status')!=aggregate(r.get('status') for r in measured):
            errors.append('mounting_height: summary disagrees with measurements')
        else:
            for row in measured:
                if row.get('status') in ('pass','exception'):
                    import math
                    values=[row.get(k) for k in ('mount_face_height_mm','clamping_surface_height_mm','offset_mm')]
                    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
                        errors.append('mounting_height: accepted result requires numeric CAD heights')
                    elif abs(values[0]-values[1]-values[2])>1e-7:
                        errors.append('mounting_height: reported difference does not match measured heights')
    expected_files={p.name for p in dxfs+steps+pngs}|set(additional_exports)
    for name in additional_exports:
        p=root/name
        if not p.is_file() or design['export_sha256'].get(name)!=sha256(p):errors.append(f'{name}: missing additional export or hash mismatch')
    if set(design['export_sha256'])!=expected_files:errors.append('export hash manifest must cover exactly the DXF/STEP/PNGs')
    for p in dxfs+steps+pngs:
        if not p.stat().st_size:errors.append(f'{p.name}: empty file');continue
        if design['export_sha256'].get(p.name)!=sha256(p):errors.append(f'{p.name}: export hash mismatch')
        try:
            if p in dxfs:
                import ezdxf
                doc=ezdxf.readfile(p)
                if doc.units!=4 or doc.audit().has_errors:raise ValueError('invalid DXF or units')
                cuts=list(doc.modelspace().query('LWPOLYLINE[layer=="CUT"]'))
                if not cuts or not all(e.closed for e in cuts):raise ValueError('missing/open cutting contours')
            elif p in steps:
                from export_step import read_step
                from OCP.BRepCheck import BRepCheck_Analyzer
                shapes=read_step(p)
                if not shapes or not all(BRepCheck_Analyzer(s).IsValid() for s in shapes.values()):raise ValueError('invalid/empty STEP shapes')
                if any(c.get('name') not in shapes for c in design['components'] if isinstance(c,dict)):raise ValueError('missing exported fixture components')
                from hardware_geometry import definition
                for clamp in design['design_spec'].get('clamps',[]):
                    expected=definition(clamp['hardware'])['asset']['components']
                    if any(f"HW_{clamp['tag']}_{n}" not in shapes for n in expected):raise ValueError('missing purchased clamp component')
                if design['design_spec'].get('clamps') and any('schematic' in n.lower() for n in shapes):raise ValueError('schematic clamp in purchased-hardware export')
                for c in by.values():
                    errors.extend(evidence_errors(c,design['design_spec'],fp,set(shapes)))
            else:
                from PIL import Image
                with Image.open(p) as im:
                    if im.format!='PNG' or min(im.size)<32:raise ValueError('invalid review PNG')
                    im.verify()
        except Exception as exc:errors.append(f'{p.name}: cannot validate export: {exc}')
    for typ,files in (('dxf',dxfs),('step',steps)):
        if files and design['export_files'].get(typ)!=files[0].name:errors.append(f'{typ}: export filename does not match manifest')
    return errors

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('delivery',type=Path);p.add_argument('--allow-no-dxf',action='store_true');p.add_argument('--allow-supplementary',action='store_true')
    a=p.parse_args();errors=validate(a.delivery,allow_no_dxf=a.allow_no_dxf,allow_supplementary=a.allow_supplementary)
    for e in errors:print('ERROR:',e,file=sys.stderr)
    if not errors:print('Delivery validated. Read verification.json for engineering readiness.')
    raise SystemExit(bool(errors))
