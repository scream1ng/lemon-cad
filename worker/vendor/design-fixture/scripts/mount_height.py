"""GH-201-B shop mounting-height policy, measured on reopened CAD.

This measures stationary height alignment, not linkage closure or applied force.
Signed offset is mounting face minus workpiece surface along the clamp normal.
"""
from pathlib import Path
import numpy as np
from records import aggregate, sha256
from fixture_common import spec_path

CAD_TOLERANCE_MM = 0.01  # comparison tolerance; not a fabrication tolerance


def nominal(clamp, plate, thickness, hardware):
    policy = hardware.get('mount_height_policy')
    if not policy:
        return {'status':'unknown', 'reason':'No mounting-height policy for this hardware.'}
    n = np.asarray(clamp['surface_normal'], float)
    n /= np.linalg.norm(n)
    w = np.asarray(plate['w'], float)
    face = np.asarray(plate['origin']) + w * thickness / 2 * np.sign(w @ n)
    offset = float((face - clamp['contact']) @ n)
    expected = float(policy['default_offset_mm'])
    return {'status':'pass' if abs(offset-expected) <= CAD_TOLERANCE_MM else
            'unknown' if clamp.get('mount_height_override') else 'fail',
            'nominal_offset_mm':offset, 'default_offset_mm':expected,
            'cad_tolerance_mm':CAD_TOLERANCE_MM,
            'scope':'Design inputs only; exported mounting and workpiece faces are measured separately.'}


def _override(clamp, spec, measured, default):
    """A differing height needs current evidence for this clamp, not a prose waiver."""
    override = clamp.get('mount_height_override')
    if override is None:
        return ('pass', 'Measured faces follow the shop mounting-height rule.') if abs(measured-default) <= CAD_TOLERANCE_MM else (
            'fail', 'Mounting face does not match the required clamping-surface level.')
    if not isinstance(override, dict) or not isinstance(override.get('reason'), str) or not override['reason'].strip():
        return 'fail', 'Height override requires a reason and measured operating evidence.'
    requested = override.get('offset_mm')
    if isinstance(requested, bool) or not isinstance(requested, (int,float)) or not np.isfinite(requested):
        return 'fail', 'Height override requires a finite signed offset_mm.'
    if abs(measured-requested) > CAD_TOLERANCE_MM:
        return 'fail', 'Exported height does not match the declared override.'
    fingerprint = spec.get('_geometry_fingerprint')
    checks = {c['name']:c for c in spec.get('engineering_checks', [])}
    for name in ('hardware_pose', 'clamp_seating'):
        c = checks.get(name, {})
        if (not fingerprint or c.get('geometry_fingerprint') != fingerprint or c.get('status') != 'pass'
            or clamp['tag'] not in c.get('clamp_tags', []) or not c.get('scope') or not c.get('limit')
            or c.get('measured') is None or not c.get('evidence')):
            return 'fail', f'Height override needs current {name} evidence explicitly covering {clamp["tag"]}.'
        try:
            for e in c['evidence']:
                p = spec_path(spec, e['file'])
                if not p.is_file() or sha256(p) != e['sha256']:
                    return 'fail', f'Height override {name} evidence is missing or changed.'
        except (KeyError, TypeError, OSError):
            return 'fail', f'Height override {name} evidence is invalid.'
    return 'exception', 'Measured alternative height supported by current closed-pose and seating evidence; operating review remains separate.'


def audit(spec, shapes, resolved):
    """Measure actual top mounting face and actual trimmed workpiece contact surface."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt, gp_Vec
    from hardware_geometry import definition
    from clamp_mount import place
    from verify import gap
    by = {d['name']:d for d in spec['plates']}
    rows = []
    for clamp in spec.get('clamps', []):
        row = {'tag':clamp['tag'], 'hardware':clamp['hardware'], 'mount_plate':clamp['mount_plate'],
               'status':'unknown', 'mount_face_height_mm':None, 'clamping_surface_height_mm':None,
               'offset_mm':None, 'cad_tolerance_mm':CAD_TOLERANCE_MM,
               'scope':'Stationary CAD surface heights along clamp normal; excludes closed mechanism, spindle adjustment and force.'}
        rows.append(row)
        hw = definition(clamp['hardware']); policy = hw.get('mount_height_policy')
        if not policy:
            row['reason'] = 'Hardware has no defined mounting-height policy.'; continue
        row['default_offset_mm'] = float(policy['default_offset_mm'])
        mount = shapes.get(clamp['mount_plate'])
        part_name, part = resolved.get(clamp.get('part'), (None,None)); row['part'] = part_name
        if mount is None or part is None:
            row.update(status='fail', reason='Missing mount plate or mapped target workpiece.'); continue
        placement, _, _ = place(clamp, by[clamp['mount_plate']], spec['thickness_mm'], spec.get('min_width_mm',10))
        frame = placement['frame']; n = np.array(frame['z']); x = np.array(frame['x']); origin = np.array(frame['origin'])
        row['frame'] = frame; row['target_contact'] = clamp['contact']
        # Probe within the actual clamp base footprint rather than assuming the spec's face elevation.
        ext = hw['base']['extent_in_canonical_frame']
        probe = origin + x * (ext['x_min_mm'] + ext['x_max_mm']) / 2
        candidates = []; ex = TopExp_Explorer(mount, TopAbs_FACE); index = 0
        while ex.More():
            face = TopoDS.Face_s(ex.Current()); ex.Next(); index += 1
            surface = BRepAdaptor_Surface(face)
            if surface.GetType() != GeomAbs_Plane: continue
            plane = surface.Plane(); normal = np.array(plane.Axis().Direction().Coord())
            if face.Orientation() == TopAbs_REVERSED: normal = -normal
            if normal @ n < .9999: continue
            anchor = np.array(plane.Location().Coord()); point = probe + n * ((anchor-probe) @ n)
            vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
            if gap(vertex,face) <= CAD_TOLERANCE_MM:
                candidates.append({'face_index':index, 'point':point.tolist(), 'normal':normal.tolist()})
        if len(candidates) != 1:
            row.update(status='fail', reason='Actual mounting face is missing or ambiguous at the base-centre probe.'); continue
        mount_face = candidates[0]
        # Evaluate the actual closest surface point and normal, including planar BSpline faces.
        vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*clamp['contact'])).Vertex()
        candidates = []; ex = TopExp_Explorer(part, TopAbs_FACE); index = 0
        while ex.More():
            face = TopoDS.Face_s(ex.Current()); ex.Next(); index += 1
            distance = BRepExtrema_DistShapeShape(vertex,face); distance.Perform()
            if not distance.IsDone() or distance.Value() > CAD_TOLERANCE_MM: continue
            try:
                u,v = distance.ParOnFaceS2(1)
                p = gp_Pnt(); du = gp_Vec(); dv = gp_Vec(); surface = BRepAdaptor_Surface(face)
                surface.D1(u,v,p,du,dv); normal = du.Crossed(dv).Normalized()
                if face.Orientation() == TopAbs_REVERSED: normal.Reverse()
                normal = np.array(normal.Coord())
            except Exception:
                continue  # Unsupported/boundary surface cannot confer a pass.
            if normal @ n < .9999: continue
            candidates.append({'face_index':index, 'point':list(p.Coord()), 'normal':normal.tolist(),
                               'contact_gap_mm':distance.Value(), 'surface_type':str(surface.GetType())})
        if len(candidates) != 1:
            row.update(status='fail', reason='Intended contact surface is missing, ambiguous or has the wrong normal.'); continue
        target = candidates[0]
        mh = float(np.array(mount_face['point']) @ n); ch = float(np.array(target['point']) @ n)
        row.update(mount_face=mount_face, contact_face=target, mount_face_height_mm=mh,
                   clamping_surface_height_mm=ch, offset_mm=mh-ch,
                   spindle_extension_below_arm_mm=hw['closed_geometry']['underarm_height_mm'] + mh-ch)
        row['status'], row['reason'] = _override(clamp, spec, mh-ch, row['default_offset_mm'])
        row['next_action'] = None if row['status']=='pass' else 'Correct support/cap height and rebuild, or verify the explicit operating-height exception.'
    return {'status':aggregate(r['status'] for r in rows) if rows else 'unknown', 'clamps':rows,
            'scope':'Reopened mount and target faces. Height alignment is independent of closed-and-locked clamp operation.'}
