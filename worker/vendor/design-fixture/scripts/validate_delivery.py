#!/usr/bin/env python3
"""Validate inherited fabrication package plus checking CAD and optional printed meshes."""
import argparse,json,sys
from pathlib import Path
from validate_base_delivery import validate as validate_base


def validate(root,*,allow_no_dxf=False,allow_supplementary=False,check_delivery_status=True):
    root=Path(root)
    try:
        project=json.loads((root/'JSON/project.json').read_text())
        design=json.loads((root/'JSON/fixture-design.json').read_text())
        ver=json.loads((root/'JSON/verification.json').read_text())
    except (OSError,ValueError):
        return validate_base(root,allow_no_dxf=allow_no_dxf,allow_supplementary=allow_supplementary,check_delivery_status=check_delivery_status)
    is_check=project.get('fixture_kind')=='checking'
    printed=is_check and project.get('construction',{}).get('mode')=='printed_solid'
    extra=[str(p.relative_to(root)) for p in (root/'PRINT').glob('*.stl')] if printed else []
    errors=validate_base(root,allow_no_dxf=allow_no_dxf or printed,allow_supplementary=allow_supplementary,
        check_delivery_status=check_delivery_status,additional_exports=extra)
    if not is_check:return errors
    try:
        from checking_geometry import audit
        from records import aggregate
        from export_step import read_step
        spec=design['design_spec'];plan=design['inspection']
        if spec.get('inspection')!=plan:errors.append('inspection plan differs from design specification')
        if plan.get('construction')!=project['construction']['mode']:errors.append('inspection/construction mode mismatch')
        checks={c['name']:c for c in ver['checks']}
        from checking_evidence import qualify,REQUIREMENTS
        for name in ('checking_geometry',)+REQUIREMENTS:
            if name not in checks:errors.append('missing checking requirement: '+name)
        for name in REQUIREMENTS:
            c=checks.get(name,{})
            if c.get('status') in ('pass','exception'):
                q=qualify(c,name,c.get('scope',''),ver['geometry_fingerprint'],root,plan,spec)
                if q['status']!=c['status']:errors.append(name+': engineering evidence is missing, stale or incomplete')
        for field in ('cad_verified','fixture_calibrated','inspection_validated'):
            if not isinstance(ver.get(field),bool):errors.append(field+' must be boolean')
        actual_steps=list(root.glob('*.step'))
        if len(actual_steps)==1:
            actual=audit(spec,actual_steps[0]);stored=ver['measurements'].get('checking_geometry',{})
            if stored.get('status')!=actual['status'] or stored.get('stations')!=actual['stations']:
                errors.append('checking_geometry: recorded results do not match reopened STEP')
            if checks.get('checking_geometry',{}).get('status')!=actual['status'] or ver.get('checking_geometry_status')!=actual['status']:
                errors.append('checking_geometry: summary disagrees with actual CAD')
            expected=ver['geometry_status']=='pass' and actual['status']=='pass'
            if ver.get('cad_verified')!=expected:errors.append('cad_verified disagrees with inherited and checking geometry')
            if printed:
                meshes=design.get('print_meshes',{}).get('meshes',[])
                shapes=read_step(actual_steps[0]);expected_meshes={f"PRINT/{m['filename']}" for m in meshes}
                bodies={c['name'] for c in design['components']}
                if not meshes or expected_meshes!=set(extra) or {m['source_body'] for m in meshes}!=bodies:
                    errors.append('Printed meshes do not cover exactly the declared printed bodies')
                from printed_body import inspect_mesh
                for m in meshes:
                    inspect_mesh(root/'PRINT'/m['filename'],shapes[m['source_body']],m['linear_deflection_mm'],m['source_body'])
        # Automated builds cannot manufacture/calibrate a fixture. Explicit physical evidence required for later updates.
        for field in ('fixture_calibrated','inspection_validated'):
            if ver.get(field):
                evidence=ver.get('physical_evidence',{}).get(field)
                if not isinstance(evidence,dict) or not evidence.get('measurements') or not evidence.get('source'):
                    errors.append(field+' requires independent physical measurements and source')
        if ver.get('fabrication_ready') and (not ver.get('cad_verified') or any(checks.get(n,{}).get('status')!='pass' for n in REQUIREMENTS)):
            errors.append('fabrication_ready requires complete checking-fixture evidence')
    except Exception as exc:errors.append('checking delivery cannot be verified: '+str(exc))
    return errors


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('delivery',type=Path)
    p.add_argument('--allow-no-dxf',action='store_true');p.add_argument('--allow-supplementary',action='store_true')
    a=p.parse_args();errors=validate(a.delivery,allow_no_dxf=a.allow_no_dxf,allow_supplementary=a.allow_supplementary)
    for e in errors:print('ERROR:',e,file=sys.stderr)
    if not errors:print('Delivery validated. Read engineering and physical-readiness fields separately.')
    raise SystemExit(bool(errors))
