#!/usr/bin/env python3
"""Stage 3.5: the 3-2-1 datum scheme on the bare part, before any rib, block or clamp body exists."""
import argparse
import json
from pathlib import Path
from workflow import resource, digest

ROLES = {'Primary': ('cone', '#1b6ec2'), 'Secondary': ('puck', '#e07a1f'),
         'Tertiary': ('cube', '#8e44c9'), 'Auxiliary': ('disc', '#7d8b93')}
ON_SURFACE_TOL_MM = 0.05


def distance_to(shape, point):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*[float(x) for x in point])).Vertex()
    measure = BRepExtrema_DistShapeShape(shape, vertex)
    if not measure.IsDone():
        raise ValueError('Could not measure datum point against the placed CAD')
    return measure.Value()


def markers(spec, shapes):
    """Datum/clamp points measured against the placed CAD; a point off the part is reported, never moved."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    compound = TopoDS_Compound()
    builder = BRep_Builder(); builder.MakeCompound(compound)
    for name, shape in shapes.items():
        if name.split('/')[-1].startswith(('Part_', 'REF_source_')):
            builder.Add(compound, shape)
    if compound.NbChildren() == 0:
        raise ValueError('Placed CAD has no Part_/REF_source_ bodies to measure datum points against')
    out = []
    for contact in spec.get('contacts', []):
        role = contact.get('role', 'Auxiliary')
        marker, color = ROLES.get(role, ROLES['Auxiliary'])
        out.append({'name': contact['name'], 'kind': 'contact', 'role': role, 'marker': marker, 'color': color,
            'point': list(contact['contact']), 'normal': list(contact['normal']), 'part': contact.get('part'),
            'constraint_role': contact.get('constraint_role'), 'rib': contact.get('rib'),
            'distance_mm': round(distance_to(compound, contact['contact']), 4)})
    for clamp in spec.get('clamps', []):
        out.append({'name': 'CLAMP:' + clamp['tag'], 'kind': 'clamp', 'role': 'Clamp', 'marker': 'arrow',
            'color': '#c0392b', 'point': list(clamp['contact']), 'normal': list(clamp['surface_normal']),
            'part': clamp.get('part'), 'constraint_role': 'applied_force', 'support': clamp.get('support'),
            'distance_mm': round(distance_to(compound, clamp['contact']), 4)})
    for row in out:
        row['off_surface'] = row['distance_mm'] > ON_SURFACE_TOL_MM
    return out


def generate(spec_path, out):
    from fixture_common import spec_path as resolve
    from export_step import read_step
    from render_review import triangles
    from preview import compact_mesh
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text()); spec['_dir'] = str(spec_path.parent)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    shapes = read_step(resolve(spec, spec['workpiece']['placed_step']))
    pin_prefixes = ('REF_PIN_', 'REF_BUSH_', 'REF_CARRIER_')
    components = [{'id': name, 'group': 'pin' if name.split('/')[-1].startswith(pin_prefixes) else 'workpiece',
                   **compact_mesh(triangles(shape), 1800)}
                  for name, shape in shapes.items()]
    points = markers(spec, shapes)
    if not points:
        raise ValueError('Decide and record datum contacts before the datum scheme review')
    features = []
    if spec.get('inspection'):  # checking fixtures: every sheet feature shown checked (green) or not (red)
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound
        from flange_coverage import audit as coverage, checked_parts
        from flange_features import extract
        feats = [f for name, s in checked_parts(spec, shapes).items() for f in extract(s, name)]
        report = coverage(spec, shapes, feats)
        status = {f['id']: f for f in report['features']}
        for f in feats:
            row = status[f['id']]
            box = TopoDS_Compound(); b = BRep_Builder(); b.MakeCompound(box)
            for face in f['_outer']: b.Add(box, face)
            ok = row['status'] == 'pass'
            components.append({'id': f['id'], 'group': 'feature_ok' if ok else 'feature_missing',
                               **compact_mesh(triangles(box), 400)})
            features.append({'id': f['id'], 'status': row['status'], 'point': row['outer_point_mm'],
                             'covered_by': [c['kind'] + ' ' + c['id'] for c in row['covered_by']]})
    scene = {'schema_version': 'fixture-datum-preview-1', 'project_id': spec['project_id'],
        'revision': spec['revision'], 'units': 'mm', 'authoritative': False, 'components': components,
        'markers': points, 'features': features, 'locating_groups': spec.get('locating_groups', []),
        'counts': {role: sum(1 for p in points if p['role'] == role) for role in list(ROLES) + ['Clamp']}}
    payload = json.dumps(scene, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    (out / 'datum-scene.json').write_text(payload)
    html = resource('assets/datum-preview.html').read_text().replace('__SCENE_JSON__', payload)
    (out / 'datum-preview.html').write_text(html)
    return {'html': str((out / 'datum-preview.html').resolve()), 'scene': str((out / 'datum-scene.json').resolve()),
        'bytes': len(html.encode()), 'inline_eligible': len(html.encode()) < 1_000_000,
        'marker_ids': [p['name'] for p in points], 'counts': scene['counts'],
        'off_surface': [p['name'] for p in points if p['off_surface']],
        'features_without_check': [f['id'] for f in features if f['status'] != 'pass'],
        'scene_sha256': digest(scene), 'authoritative': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('spec'); p.add_argument('out')
    a = p.parse_args(); print(json.dumps(generate(a.spec, a.out), indent=2))
