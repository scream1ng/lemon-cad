#!/usr/bin/env python3
"""Measured CAD checks. Unknown/missing coverage can never become a geometry pass."""
from __future__ import annotations
import argparse
import itertools
import json
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex, BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
from OCP.GProp import GProp_GProps
from export_step import read_step, solid
from fixture_common import load_spec, write_json

TOUCH, PLATE_VOL, PART_VOL = 1e-4, 1e-3, 1e-4

def aggregate(statuses):
    values = list(statuses)
    return 'fail' if 'fail' in values else 'pass' if values and all(s == 'pass' for s in values) else 'unknown'

def gap(a, b):
    q = BRepExtrema_DistShapeShape(a, b); q.Perform()
    if not q.IsDone(): raise ValueError('CAD distance calculation failed')
    return q.Value()

def volume(sh):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g)
    return abs(g.Mass())

def common_volume(a, b):
    op = BRepAlgoAPI_Common(a, b); op.Build()
    if not op.IsDone(): raise ValueError('CAD intersection failed')
    return volume(op.Shape())

def bbox(sh):
    b = Bnd_Box(); BRepBndLib.Add_s(sh, b, False)
    return b.Get()

def bbox_overlap(x, y):
    return all(x[i] <= y[i+3]+TOUCH and y[i] <= x[i+3]+TOUCH for i in range(3))

def interferes(a, b, ba, bb, limit):
    if not bbox_overlap(ba, bb) or gap(a, b) >= TOUCH: return 0.0
    v = common_volume(a, b)
    return v if v > limit else 0.0

def moved(sh, vec):
    t = gp_Trsf(); t.SetTranslation(gp_Vec(*vec))
    return BRepBuilderAPI_Transform(sh, t, True).Shape()

def resolve_part(parts, key):
    if key in parts: return key, parts[key]
    matches = [(n,s) for n,s in parts.items() if key and key in n]
    if len(matches) != 1: return None, None
    return matches[0]

FLAT_FACE_TOL_MM = 0.001                        # non-analytic face counts as planar only within this fit


def face_contact(c, target):
    """Planar descriptors + actual trimmed face + actual outward normal, scoped to this source revision."""
    point = np.array(c['contact'], float)
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    desc = c.get('face')
    candidates = []
    exp = TopExp_Explorer(target, TopAbs_FACE)
    index = 0
    while exp.More():
        index += 1
        face = TopoDS.Face_s(exp.Current()); exp.Next()
        if gap(vertex, face) > .01: continue
        surf = BRepAdaptor_Surface(face, True)
        if surf.GetType() == GeomAbs_Plane:
            plane = surf.Plane(); flat = {'surface': 'Plane'}
            normal = np.array(plane.Axis().Direction().Coord())
            if face.Orientation() == TopAbs_REVERSED: normal = -normal
            anchor = np.array(plane.Location().Coord())
        else:                                   # B-spline etc.: accepted only when measured flat
            from flange_features import planar_face
            fit = planar_face(face)
            if fit is None or fit[2] > FLAT_FACE_TOL_MM: continue
            anchor, normal = fit[0], fit[1]; flat = {'surface': fit[4], 'plane_fit_deviation_mm': fit[2]}
        if desc:
            if desc.get('type') != 'plane': continue
            dn = np.asarray(desc['outward_normal'], float)
            if not np.isclose(np.linalg.norm(dn), 1): raise ValueError('face outward_normal must be unit length')
            if normal @ dn < .9999 or abs((np.array(desc['point'])-anchor) @ normal) > .01: continue
        candidates.append({'face_index_in_export': index, 'outward_normal': normal.tolist(), **flat,
                           'inward_alignment': float(np.array(c['normal']) @ -normal), 'face_gap_mm': gap(vertex,face)})
    if len(candidates) != 1:
        return {'status': 'fail' if desc else 'unknown', 'reason': 'intended trimmed planar face is missing or ambiguous', 'candidate_count': len(candidates)}
    row = candidates[0]
    row['status'] = 'fail' if row['inward_alignment'] < .9999 else 'pass' if desc else 'unknown'
    row['reason'] = 'measured on intended face' if desc else 'face direction checked; intended-face descriptor missing'
    return row

def constraint_rank(spec):
    contacts = {c['name']: c for c in spec['contacts']}
    from assembly_locating import fixed
    out = {}
    for group, keys in spec.get('locating_groups', {}).items():
        keys=[k for k in keys if fixed(contacts[k])]
        if not keys:
            out[group] = {'rank':0,'status':'unknown','contacts':[]}; continue
        points = np.array([contacts[k]['contact'] for k in keys],float)
        origin = points.mean(axis=0); length = max(float(np.linalg.norm(np.ptp(points,axis=0))),1.0)
        rows = [np.r_[contacts[k]['normal'],np.cross(np.array(contacts[k]['contact'])-origin, contacts[k]['normal'])/length] for k in keys]
        sv = np.linalg.svd(rows, compute_uv=False)
        rank = int(np.linalg.matrix_rank(rows))
        ratio = float(sv[-1]/sv[0]) if len(sv) == 6 and sv[0] else 0.0
        out[group] = {'contacts':keys,'rank':rank,'scaled_singular_values':sv.tolist(),'reference_origin':origin.tolist(),
                      'characteristic_length_mm':length,'conditioning_ratio':ratio,
                      'status':'fail' if rank < 6 else 'unknown' if ratio < 1e-4 else 'pass',
                      'scope':'local independence only; unilateral seating and force closure are separate'}
    return out

def verify(spec, step_path, insertion=True, log=print):
    shapes = read_step(step_path)
    names = {d['name'] for d in spec['plates']}
    plates = {k:s for k,s in shapes.items() if k in names}
    parts = {k:s for k,s in shapes.items() if k.split('/')[-1].startswith('Part_')}
    bounds = {k:bbox(s) for k,s in shapes.items()}
    wp = spec.get('workpiece', {})
    rep = {'step':str(step_path),'invalid_solids':[k for k,s in shapes.items() if not BRepCheck_Analyzer(s).IsValid()],
           'missing_plates':sorted(names-set(plates)), 'contacts':[], 'part_intersections':[], 'plate_intersections':[]}
    resolved = {key:resolve_part(parts,val) for key,val in wp.get('parts',{}).items()}
    rep['missing_or_ambiguous_workpieces'] = [key for key,(_,s) in resolved.items() if s is None]
    for c in spec['contacts']:
        pn, target = resolved.get(c['part'], (None,None))
        own = c.get('rib') or wp.get('reference_prefix','REF_')+c['name']
        p = BRepBuilderAPI_MakeVertex(gp_Pnt(*c['contact'])).Vertex()
        row = {'id':c['name'],'own':own,'part':pn,'part_gap_mm':gap(p,target) if target is not None else None,
               'own_geometry_gap_mm':gap(p,shapes[own]) if own in shapes else None}
        near = all(row[k] is not None and row[k] < .01 for k in ('part_gap_mm','own_geometry_gap_mm'))
        row['face_check'] = face_contact(c,target) if target is not None else {'status':'fail','reason':'missing target'}
        row['status'] = aggregate(['pass' if near else 'fail', row['face_check']['status']])
        rep['contacts'].append(row)
    for k,s in plates.items():
        for pn,ps in parts.items():
            v = interferes(s,ps,bounds[k],bounds[pn],PART_VOL)
            if v: rep['part_intersections'].append({'plate':k,'part':pn,'volume_mm3':v})
    for (a,sa),(b,sb) in itertools.combinations(plates.items(),2):
        v = interferes(sa,sb,bounds[a],bounds[b],PLATE_VOL)
        if v: rep['plate_intersections'].append({'a':a,'b':b,'volume_mm3':v})
    # Compare reopened STEP solids against the final spec, not just names/file existence.
    rep['export_comparison'] = []
    for d in spec['plates']:
        if d['name'] not in plates: continue
        expected,actual = solid(d,spec['thickness_mm']),plates[d['name']]
        err = max(0.0, volume(expected)+volume(actual)-2*common_volume(expected,actual))
        rep['export_comparison'].append({'plate':d['name'],'symmetric_volume_error_mm3':err,'status':'pass' if err < 1e-3 else 'fail'})
    rep['constraints'] = constraint_rank(spec)
    import assembly_locating
    from hardware_geometry import verify_export
    rep['assembly_locating'] = assembly_locating.audit(spec)
    rep['secondary_sides'] = assembly_locating.secondary_sides(spec)
    rep['mating_geometry'] = assembly_locating.mating_geometry(spec,resolved)
    rep['hardware_geometry'] = verify_export(spec,shapes)
    import cap_joints
    rep['cap_joints'] = cap_joints.audit(spec)
    from mount_height import audit as height_audit
    rep['mounting_height'] = height_audit(spec,shapes,resolved)
    covered = set()
    by_contact = {c['name']:c for c in spec['contacts']}
    for g in rep['constraints'].values():
        targets = {by_contact[k]['part'] for k in g['contacts']}
        if len(targets) == 1 and g['status'] == 'pass': covered |= targets
    rep['unlocated_workpieces'] = sorted(set(resolved)-covered)
    if spec.get('assembly_locating') and rep['assembly_locating']['status']=='pass':
        rep['unlocated_workpieces']=[]
    rep['unmapped_workpieces'] = sorted(set(parts)-{name for name,shape in resolved.values() if shape is not None})
    rep['insertion'] = {'status':'unknown','reason':'fixture insertion not requested or not specified','collisions':[],
                        'scope':'fixture construction only; excludes workpiece loading and unloading'}
    if insertion and spec.get('insertion') and not rep['missing_plates']:
        ins = spec['insertion']; seat = next(d['seat'] for d in spec['plates'] if d.get('seat'))
        by = {d['name']:d for d in spec['plates']}
        layered = [n for layer in spec.get('assembly_layers',[]) for n in layer]
        if len(set(layered)) != len(layered) or any(n not in names or n == seat for n in layered):
            raise ValueError('assembly_layers must contain each non-seat plate at most once')
        order = layered+[d['name'] for d in spec['plates'] if d['name'] not in layered and d['name'] != seat]
        offsets = sorted(set(float(o) for o in ins['offsets_mm']))
        if not offsets or offsets[0] < 0: raise ValueError('insertion offsets must be nonnegative and nonempty')
        fixed,hits,rows = [seat],[],[]
        for name in order:
            axis = np.array(by[name]['w'] if name in ins.get('along_w',[]) else ins['default_axis'],float)
            if not np.isclose(np.linalg.norm(axis),1): raise ValueError('insertion axis must be unit length')
            for off in offsets:
                sh = moved(plates[name],axis*off); bb = bbox(sh)
                for f in fixed:
                    if interferes(sh,plates[f],bb,bounds[f],PLATE_VOL): hits.append({'moving':name,'fixed':f,'offset_mm':off})
            rows.append({'plate':name,'axis':axis.tolist()}); fixed.append(name)
        rep['insertion'] = {'order':rows,'offsets_mm':offsets,'collisions':hits,'sample_status':'fail' if hits else 'pass',
                            'status':'fail' if hits else 'unknown', 'method':'discrete common-volume samples',
                            'scope':'samples do not establish a continuous swept path; fixture construction only'}
    rep['coverage'] = {'workpieces':len(parts),'contacts':len(rep['contacts']),'groups':len(rep['constraints']),
                       'status':'pass' if parts and resolved and rep['contacts'] and rep['constraints'] and not rep['unlocated_workpieces'] and not rep['unmapped_workpieces'] else 'unknown'}
    rep['check_statuses'] = {
        'solid_integrity':'fail' if rep['invalid_solids'] or rep['missing_plates'] or rep['missing_or_ambiguous_workpieces'] else 'pass',
        'contacts':aggregate(c['status'] for c in rep['contacts']),
        'constraint_independence':aggregate([rep['coverage']['status']]+[g['status'] for g in rep['constraints'].values()]),
        'interference':'fail' if rep['part_intersections'] or rep['plate_intersections'] else 'pass' if parts else 'unknown',
        'step_roundtrip':aggregate(c['status'] for c in rep['export_comparison']),
        'fixture_insertion':rep['insertion']['status']}
    rep['check_statuses']['same_side_secondary'] = rep['secondary_sides']['status']
    rep['check_statuses']['assembly_locating'] = aggregate([rep['assembly_locating']['status'],rep['mating_geometry']['status']])
    rep['check_statuses']['hardware_geometry'] = rep['hardware_geometry']['status']
    rep['check_statuses']['mounting_height'] = rep['mounting_height']['status']
    rep['check_statuses']['cap_joints'] = rep['cap_joints']['status']
    if spec.get('assembly_locating'):
        rep['check_statuses']['constraint_independence'] = aggregate([rep['check_statuses']['assembly_locating'], 'unknown' if rep['unmapped_workpieces'] else 'pass'])
    rep['status'] = aggregate(rep['check_statuses'].values())
    return rep

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('spec');ap.add_argument('step');ap.add_argument('out');ap.add_argument('--no-insertion',action='store_true')
    a=ap.parse_args();r=verify(load_spec(a.spec),a.step,not a.no_insertion);write_json(a.out,r);print(r['status'])
    raise SystemExit(1 if r['status']=='fail' else 0)
