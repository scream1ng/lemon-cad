"""Import complete purchased hardware without inventing a closed pose or linkage."""
import json
from pathlib import Path
import numpy as np
from records import sha256

ROOT=Path(__file__).resolve().parent.parent

def definition(hardware):
    return json.loads((ROOT/'references/hardware'/f'{hardware.lower()}.json').read_text())

def asset_path(hardware):
    h=definition(hardware);p=ROOT/h['asset']['file']
    if not p.is_file() or sha256(p)!=h['asset']['sha256']:
        raise ValueError(f'{hardware}: missing or modified bundled STEP; resolve the asset before export')
    return p

def rigid(shape,matrix):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf
    a=np.asarray(matrix,float)
    if a.shape!=(4,4) or not np.allclose(a[3],[0,0,0,1]) or not np.allclose(a[:3,:3].T@a[:3,:3],np.eye(3)) or not np.isclose(np.linalg.det(a[:3,:3]),1):
        raise ValueError('hardware transform must be rigid and right-handed')
    t=gp_Trsf();t.SetValues(*a[:3,:].ravel().tolist())
    return BRepBuilderAPI_Transform(shape,t,True).Shape()

def placed_shapes(spec):
    from export_step import read_step
    from clamp_mount import place
    shapes={};reports=[];plates={d['name']:d for d in spec['plates']}
    for c in spec.get('clamps',[]):
        hw=definition(c['hardware']);p=asset_path(c['hardware']);source=read_step(p)
        expected=hw['asset']['components']
        if set(source)!=set(expected):raise ValueError(f"{c['tag']}: clamp component identities differ from the asset record")
        row,_,_=place(c,plates[c['mount_plate']],spec['thickness_mm'],spec.get('min_width_mm',10))
        f=row['frame'];world=np.eye(4);world[:3,:3]=np.array([f['x'],f['y'],f['z']]).T;world[:3,3]=f['origin']
        transform=world@np.array(hw['asset']['source_to_canonical'])
        names=[]
        for n in expected:
            name=f"HW_{c['tag']}_{n}";shapes[name]=rigid(source[n],transform);names.append(name)
        pad=world@np.r_[hw['asset']['pad_contact_canonical_mm'],1]
        reports.append({'tag':c['tag'],'hardware':c['hardware'],'asset_sha256':sha256(p),'component_names':names,
            'component_count':len(names),'source_to_fixture':transform.tolist(),'pose':'as-supplied',
            'pose_status':'unknown','saved_pad_contact_world_mm':pad[:3].tolist(),
            'saved_pad_to_target_distance_mm':float(np.linalg.norm(pad[:3]-c['contact'])),
            'status':'pass','scope':'exact supplied component geometry and rigid mounting placement only; not verified closed clamping geometry',
            'next_action':'Verify a closed operating pose and spindle adjustment from actual linkage/part geometry; never reposition only the pad or rotate the entire mounted clamp to fake closure.'})
    return shapes,reports

def verify_export(spec,shapes):
    expected,rows=placed_shapes(spec)
    from verify import bbox,volume
    for r in rows:
        failures=[]
        for n in r['component_names']:
            if n not in shapes:failures.append({'component':n,'reason':'missing'});continue
            # Bounding dimensions and volume detect missing/moved/replaced components after STEP transfer.
            be=max(abs(a-b) for a,b in zip(bbox(expected[n]),bbox(shapes[n])))
            ve=abs(volume(expected[n])-volume(shapes[n]));limit=max(.01,volume(expected[n])*1e-5)
            if be>.01 or ve>limit:failures.append({'component':n,'bbox_error_mm':be,'volume_error_mm3':ve})
        r['failures']=failures;r['status']='fail' if failures else 'pass'
    return {'status':'fail' if any(r['status']=='fail' for r in rows) else 'pass', 'clamps':rows,
            'scope':'purchased hardware asset identity and saved-pose export; no operating pose or swept-clearance approval'}
