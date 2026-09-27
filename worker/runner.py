"""One job per subprocess; never execute user-supplied commands or paths."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def execute(kind, payload, source, out):
    if kind == 'cad':
        from cad.authoring import rebuild, write_step, volume
        shape, document = rebuild(payload['document'])
        step = out / 'part.step'
        write_step(shape, step)
        result = execute('import', {}, step, out)
        result['cad_document'] = document
        result['volume_mm3'] = volume(shape)
        result['artifacts'].append({'path': 'part.step', 'kind': 'cad_step'})
        return result
    if kind == 'import':
        if source.suffix == '.stl':
            # Validate basic STL framing here; browser performs the mesh decode.
            import struct
            data = source.read_bytes()
            binary = len(data) >= 84 and len(data) == 84 + 50 * struct.unpack_from('<I', data, 80)[0]
            ascii_stl = data.lstrip().lower().startswith(b'solid') and b'endsolid' in data.lower() and b'vertex' in data.lower()
            if not binary and not ascii_stl:
                raise ValueError('Invalid STL: expected ASCII facets or a complete binary triangle list.')
            return {'mesh_based': True}
        from cad.loader import load_step
        from cad.icl import faced_mesh, indexed_edges
        shape = load_step(str(source))
        if shape.IsNull():
            raise ValueError('STEP contains no supported geometry.')
        result = faced_mesh(shape)
        result['edges'] = indexed_edges(shape)
        from cad.smart_measure import feature, smart_measure
        result['measure_features'] = {}
        for kind, items in [('face', result['faces']), ('edge', result['edges'])]:
            for item in items:
                ref = {'kind': kind, 'id': item['id']}
                descriptor = feature(shape, ref)
                if descriptor['type'] not in ('circle', 'line'):
                    continue
                descriptor['single'] = smart_measure(shape, [ref])
                result['measure_features'][str(item['id'] if kind == 'face' else -item['id'])] = descriptor
        if not result['indices'] or len(result['indices']) > 6000000:
            raise ValueError('No mesh generated, or model exceeds the two million triangle limit.')
        (out / 'mesh.json').write_text(json.dumps(result, allow_nan=False))
        return {'face_count': result['face_count'], 'artifacts': [{'path': 'mesh.json', 'kind': 'mesh'}]}
    if kind == 'face_plane':
        from cad.loader import load_step
        from cad.icl import face_sketch_plane
        return {'frame': face_sketch_plane(load_step(str(source)), payload['face_id'])}
    if kind == 'measure':
        from cad.loader import load_step
        from cad.smart_measure import smart_measure
        shape = load_step(str(source))
        refs = payload.get('entities') or [{'kind': 'face', 'id': i} for i in payload['faces']]
        return smart_measure(shape, refs, payload.get('relation', 'centre'))
    if kind == 'drawing':
        sys.path.insert(0, str(ROOT / 'vendor/draft-drawing/scripts'))
        import measure as drawing_measure
        import sheet
        settings = {k: payload[k] for k in ('title', 'material', 'density_kg_m3', 'show_hidden', 'notes')}
        settings.update(scales={}, skip_items=[])
        measured = drawing_measure.measure(str(source), settings['density_kg_m3'])
        pages = sheet.draw(measured, settings)
        try:
            svgs = sheet.to_svgs(pages)
            for i, svg in enumerate(svgs):
                (out / f'sheet-{i + 1}.svg').write_text(svg)
            sheet.to_pdf(pages, out / 'drawing.pdf', {'Title': settings['title'], 'Creator': 'LemonCAD draft-drawing', 'Subject': 'Draft drawing; review omissions before use'})
        finally:
            sheet.close(pages)
        public = drawing_measure.public(measured)
        (out / 'measure.json').write_text(json.dumps(public))
        return {'pages': len(svgs), 'unknowns': {r['item']: [u['what'] for u in r.get('unknowns', [])] for r in measured['items'] if r.get('unknowns')}, 'mass_kg': measured['total_mass_kg'], 'settings': settings,
                'artifacts': [{'path': f'sheet-{i+1}.svg', 'kind': 'sheet'} for i in range(len(svgs))] + [{'path': 'drawing.pdf', 'kind': 'pdf'}, {'path': 'measure.json', 'kind': 'measurement_report'}]}
    if kind == 'costing':
        sys.path.insert(0, str(ROOT / 'vendor/costing/scripts'))
        from calculate import calculate
        result = calculate(payload['estimate'])
        previous = payload.get('previous')
        if previous:
            result['comparison'] = {key: {'before': previous.get(key), 'after': result.get(key)} for key in ('selling_per_assembly', 'selling_batch', 'gross_margin')}
        return result
    raise ValueError('Unsupported job type.')


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    args = json.loads((folder / 'input.json').read_text())
    try:
        result = execute(args['type'], args['input'], Path(args['source']), folder)
        result['revision_hash'] = hashlib.sha256(json.dumps(args['input'], sort_keys=True).encode() + (Path(args['source']).read_bytes() if args['source'] else b'')).hexdigest()
        (folder / 'result.json').write_text(json.dumps(result, allow_nan=False))
    except Exception as exc:
        (folder / 'error.txt').write_text(str(exc)[:1500])
        raise
