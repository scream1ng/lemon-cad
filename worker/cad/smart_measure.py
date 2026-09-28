"""Explicit reference measurements on the source STEP topology."""
import math
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.TopoDS import TopoDS
from cad.icl import _sub_shape, _face, _cylinder_center, _cylinder_geometry, _edge_geometry, _face_map, _edge_map, measure, measure_single


def xyz(p):
    return [p.X(), p.Y(), p.Z()]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def feature(shape, ref, mapping=None):
    kind, index = ref['kind'], ref['id']
    if mapping is None:
        mapping = _face_map(shape) if kind == 'face' else _edge_map(shape)
    if index < 1 or index > mapping.Extent():
        raise ValueError('Selected feature does not exist in this model revision.')
    part = mapping.FindKey(index)
    if kind == 'face':
        face = _face(part)
        if _cylinder_geometry(face):
            center, axis, radius = _cylinder_center(face)
            return {'type': 'circle', 'center': center, 'axis': axis, 'radius': radius, 'axial': True}
        return {'type': 'face'}
    curve = BRepAdaptor_Curve(TopoDS.Edge_s(part))
    a, b = xyz(curve.Value(curve.FirstParameter())), xyz(curve.Value(curve.LastParameter()))
    geometry = _edge_geometry(TopoDS.Edge_s(part))
    if geometry and geometry[0] == 'circle':
        circle = geometry[1]
        return {'type': 'circle', 'center': xyz(circle.Location()), 'axis': xyz(circle.Axis().Direction()), 'radius': circle.Radius(), 'axial': False,
                'full': curve.IsClosed() or abs(curve.LastParameter()-curve.FirstParameter()-2*math.pi) < 1e-5}
    if geometry and geometry[0] == 'line':
        return {'type': 'line', 'a': a, 'b': b, 'axis': xyz(geometry[1].Direction())}
    return {'type': 'curve'}


def smart_measure(shape, refs, relation='centre', known_features=None, cylinder_faces=None, face_map=None):
    features = list(known_features) if known_features is not None else [feature(shape, r) for r in refs]
    def result(label, p1, p2, **extra):
        return {'label': label, 'value_mm': math.dist(p1, p2), 'p1': p1, 'p2': p2,
                'method': label.lower(), 'relation': relation, 'entities': refs, 'basis': 'STEP geometry · nominal', **extra}
    if len(refs) == 1:
        f, ref = features[0], refs[0]
        if ref['kind'] == 'face':
            return {**measure_single(shape, 'face', ref['id'], cylinder_faces, face_map), 'entities': refs, 'basis': 'STEP geometry · nominal'}
        if f['type'] == 'line':
            return result('Edge length', f['a'], f['b'])
        if f['type'] == 'circle':
            c, n, r = f['center'], f['axis'], f['radius']
            axis = [1, 0, 0] if abs(n[0]) < .9 else [0, 1, 0]
            v = sub(axis, [dot(axis, n)*x for x in n]); length = math.sqrt(dot(v, v)); v = [x/length for x in v]
            full = f['full']
            return result('Diameter' if full else 'Radius', [c[i]-v[i]*r for i in range(3)] if full else c,
                          [c[i]+v[i]*r for i in range(3)], type='dia' if full else 'rad')
        raise ValueError('Select a straight edge, circular rim or cylindrical face.')
    ordered_refs = list(refs)
    if features[1]['type'] == 'circle' and features[0]['type'] != 'circle':
        features.reverse()
        ordered_refs.reverse()
    a, b = features
    if a['type'] == 'circle' and b['type'] in ('circle', 'line'):
        c, n, r = a['center'][:], a['axis'], a['radius']
        if b['type'] == 'line':
            edge_length = math.dist(b['a'], b['b'])
            if edge_length <= 1e-6:
                raise ValueError('Select a nonzero edge.')
            edge_axis = [v/edge_length for v in sub(b['b'], b['a'])]
            if abs(dot(n, edge_axis)) > 1e-6:
                raise ValueError('Select an edge perpendicular to the hole axis.')
            offset = dot(sub(b['a'], c), n)
            if not a['axial'] and abs(offset) > 1e-5:
                raise ValueError('Select a hole rim and edge in the same plane.')
            c = [c[i]+offset*n[i] for i in range(3)]
            t = max(0, min(edge_length, dot(sub(c, b['a']), edge_axis)))
            target = [b['a'][i]+t*edge_axis[i] for i in range(3)]
            label = 'Centre to edge'
            radii = r
        else:
            if abs(abs(dot(n, b['axis']))-1) > 1e-6:
                raise ValueError('Hole axes are not parallel. Select coplanar circular rims.')
            offset = dot(sub(b['center'], c), n)
            if not a['axial'] and not b['axial'] and abs(offset) > 1e-5:
                raise ValueError('Select two hole rims in the same plane.')
            c = [c[i]+offset*n[i] for i in range(3)]
            target = b['center'][:]; radii = r+b['radius']; label = 'Centre to centre'
        distance = math.dist(c, target)
        p1, p2 = c[:], target[:]
        if relation == 'clearance':
            if distance < radii+1e-6:
                raise ValueError('These features overlap or touch; a positive wall clearance is not available.')
            direction = [(target[i]-c[i])/distance for i in range(3)]
            p1 = [c[i]+direction[i]*r for i in range(3)]
            if b['type'] == 'circle':
                p2 = [target[i]-direction[i]*b['radius'] for i in range(3)]
            label = 'Nearest wall clearance'
        return result(label, p1, p2, alternatives=['centre', 'clearance'], reference_plane={'origin': c, 'normal': n})
    if a['type'] == 'circle' and b['type'] == 'face':
        raw = measure(shape, refs[0]['kind'], refs[0]['id'], refs[1]['kind'], refs[1]['id'])
        if raw['method'] != 'center-to-plane':
            if relation == 'centre':
                return {**raw, 'entities': refs, 'basis': 'STEP geometry · nominal'}
            raise ValueError('Wall clearance needs a planar surface.')
        extra = {'entities': refs, 'basis': 'STEP geometry · nominal', 'relation': relation,
                 'alternatives': ['centre', 'clearance'], 'reference_plane': {'origin': a['center'], 'normal': a['axis']}}
        if relation == 'centre':
            return {**raw, **extra, 'label': 'Centre to plane'}
        if relation != 'clearance':
            raise ValueError('Unsupported measurement relation.')
        plane_ref = ordered_refs[1]
        surface = BRepAdaptor_Surface(_face(_sub_shape(shape, 'face', plane_ref['id'])))
        if surface.GetType() != GeomAbs_Plane:
            raise ValueError('Wall clearance needs a planar surface.')
        plane = surface.Plane()
        n = xyz(plane.Axis().Direction())
        if abs(dot(n, a['axis'])) > 1e-6:
            raise ValueError('Select a surface parallel to the hole axis for wall clearance.')
        c, r = a['center'], a['radius']
        signed = dot(sub(c, xyz(plane.Location())), n)
        if abs(signed) <= r + 1e-6:
            raise ValueError('The hole touches or crosses this surface; a positive wall clearance is not available.')
        wall = [c[i] - math.copysign(r, signed)*n[i] for i in range(3)]
        wall_signed = dot(sub(wall, xyz(plane.Location())), n)
        foot = [wall[i] - wall_signed*n[i] for i in range(3)]
        return {**raw, **extra, 'label': 'Hole wall to plane', 'method': 'hole-wall-to-plane',
                'value_mm': round(abs(wall_signed), 3), 'p1': wall, 'p2': foot}
    if relation != 'centre':
        raise ValueError('Wall clearance is not available for this selection.')
    return {**measure(shape, refs[0]['kind'], refs[0]['id'], refs[1]['kind'], refs[1]['id']), 'entities': refs, 'basis': 'STEP geometry · nominal'}
