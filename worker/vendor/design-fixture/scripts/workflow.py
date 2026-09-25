#!/usr/bin/env python3
"""Versioned, source-bound concept/revision/finalization entrypoint."""
import argparse
import subprocess
import hashlib
import json
from pathlib import Path

VERSION = 'fixture-project-1'
MODES = {'weld': {'laser_rib', 'block'}, 'checking': {'laser_rib', 'printed_solid'}}
ROOT = Path(__file__).resolve().parent.parent


def resource(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError('Missing or unsafe bundled resource: ' + relative)
    return path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


_HASHES = {}


def file_hash(path):
    """Cached on (path, mtime, size); source bytes are re-hashed whenever either moves."""
    path = Path(path)
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _HASHES:
        _HASHES[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _HASHES[key]


REF_SOLIDS = ('REF_PIN_', 'REF_BUSH_', 'REF_CARRIER_')


def geometry_fingerprint(path):
    """[all solids, datum geometry] of a STEP source, blind to header/timestamp bytes; None for other formats.

    The second drops REF_ fixture solids. A pin grown, shortened or added in the surveyed STEP is
    fixture hardware, not workpiece geometry: where it locates the part is its contacts rows, which
    datum_scheme() already watches. A pin shortened at its engagement end is the gap here -- the
    contact row still claims a touch that the solid no longer makes.
    """
    if Path(path).suffix.lower() not in ('.step', '.stp'):
        return None
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from export_step import read_step
    from verify import bbox
    rows = []
    for name, shape in sorted(read_step(path).items()):
        v, a = GProp_GProps(), GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, v); BRepGProp.SurfaceProperties_s(shape, a)
        faces, it = 0, TopExp_Explorer(shape, TopAbs_FACE)
        while it.More(): faces += 1; it.Next()
        rows.append([name, round(v.Mass(), 2), round(a.Mass(), 2), [round(x, 3) for x in v.CentreOfMass().Coord()],
                     [round(x, 3) for x in bbox(shape)], faces])
    return [digest(rows), digest([r for r in rows if not r[0].split('/')[-1].startswith(REF_SOLIDS)])]


def survey_sources(sources):
    """Surveyed workpiece inputs only: a rebuilt finished body is design output, not a re-survey."""
    return [x for x in sources if x['role'] != 'finished_body']


# Fixture-body fields (which rib carries a pad, clamp model/plate/arm) never move a datum; every other field does.
BODY_FIELDS = {'contacts': {'rib', 'source_face_note'},
               'clamps': {'hardware', 'mount_plate', 'arm_direction', 'apply_hole_pattern', 'mount_transform', 'schematic_pivot'}}


def datum_scheme(spec):
    """What the datum review showed: contacts, locating groups and clamp forces, minus fixture-body fields."""
    out = {'locating_groups': spec.get('locating_groups')}
    for key, drop in BODY_FIELDS.items():
        rows = spec.get(key)
        out[key] = rows if rows is None else [{k: v for k, v in r.items() if k not in drop} for r in rows]
    return out


REBASE_REASONS = ('bytes changed, solid geometry identical',
                  'only REF_ fixture solids changed; datum geometry identical')


def rebase_sources(spec, current, record):
    """Byte-changed sources whose datum geometry is unchanged: carry the record and datum review over.

    Level 0 is a plain re-export (every solid identical); level 1 also allows the REF_ fixture solids
    to differ, so lengthening a pin in the surveyed STEP does not cost a datum review.
    """
    old = {x['path']: x for x in record['sources']}
    if [(x['role'], x['path']) for x in current['sources']] != [(x['role'], x['path']) for x in record['sources']]:
        return False
    known = record.get('source_geometry') or {}
    changed = [x['path'] for x in current['sources'] if x['sha256'] != old[x['path']]['sha256']]
    if not changed:
        return False
    fresh = {p: geometry_fingerprint(p) for p in changed}
    # a pre-datum-level record stored the all-solids digest as a plain string
    stored = lambda p, i: [known[p], None][i] if isinstance(known.get(p), str) else (known.get(p) or [None, None])[i]
    matches = lambda i: all(isinstance(fresh[p], list) and stored(p, i) is not None
                            and fresh[p][i] == stored(p, i) for p in changed)
    level = 0 if matches(0) else 1 if matches(1) else None
    if level is None:
        return False
    kept = datum_scheme(spec) | {
        'frame': current['coordinate_frame']['source_to_fixture'], 'sources': survey_sources(record['sources'])}
    if digest(kept) == record.get('datum_digest'):
        for key in ('datum_review', 'datum_preview'):
            if (record.get(key) or {}).get('datum_digest') == record['datum_digest']:
                record[key]['datum_digest'] = current['datum_digest']
    record['source_geometry'] = {**known, **fresh}
    record.setdefault('history', []).append({'rebased_sources': changed, 'reason': REBASE_REASONS[level]})
    return True


def route(kind=None, construction=None, concept_exception=None):
    if kind is None:
        return {'question': 'Weld fixture or Check fixture?', 'choices': ['weld', 'checking']}
    kind = 'checking' if kind == 'check' else kind
    construction = construction or 'laser_rib'
    if kind not in MODES or construction not in {'laser_rib', 'block', 'printed_solid'}:
        raise ValueError('Unknown fixture kind or construction')
    supported = construction in MODES[kind]
    if not supported and not (isinstance(concept_exception, str) and concept_exception.strip()):
        raise ValueError('Unsupported mode; requires an explicit concept-only exception reason')
    return {'fixture_kind': kind, 'construction': construction, 'concept_only': not supported,
            'exception_reason': concept_exception if not supported else None}


def snapshot(spec_path):
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text())
    if spec.get('units') != 'mm' or not spec.get('project_id') or not spec.get('revision'):
        raise ValueError('Spec requires project_id, revision and mm units')
    from fixture_common import validate_rigid
    frame = spec.get('workpiece', {}).get('source_to_fixture')
    if frame is None:
        raise ValueError('Survey and record the coordinate frame first')
    validate_rigid(frame)
    wp = spec['workpiece']
    sources = []
    if not wp.get('source_files') or not wp.get('placed_step'):
        raise ValueError('Original source and placed CAD are required')
    paths = [('original', x) for x in wp['source_files']] + [('placed', wp['placed_step'])]
    for field in ('printed_bodies', 'block_bodies'):
        paths += [('finished_body', x['finished_step']) for x in spec.get(field, []) if x.get('finished_step')]
    for role, name in paths:
        path = Path(name)
        path = path if path.is_absolute() else spec_path.parent / path
        sources.append({'role': role, 'path': str(path.resolve()), 'sha256': file_hash(path)})
    ids = []
    for field in ('plates', 'printed_bodies', 'block_bodies'):
        ids += [x['name'] for x in spec.get(field, [])]
    ids += [x['plate']['name'] for x in spec.get('checking_ribs', [])]
    ids += list(wp.get('parts', {}).values())
    ids += ['CLAMP:' + x['tag'] for x in spec.get('clamps', [])]
    ids += ['CONTACT:' + x['name'] for x in spec.get('contacts', [])]
    # Contact/clamp namespaces keep identity distinct from manufactured solid names.
    geometry = {k: v for k, v in spec.items() if k not in ('engineering_checks', 'checking_evidence')}
    identity = {'spec': spec, 'sources': sources}
    return spec, {'project_id': spec['project_id'], 'revision': spec['revision'], 'units': 'mm',
        'coordinate_frame': {'name': 'fixture', 'source_to_fixture': frame}, 'sources': sources,
        'geometry_digest': digest({'spec': geometry, 'sources': sources}), 'input_digest': digest(identity),
        'datum_digest': digest(datum_scheme(spec) |
            {'frame': frame, 'sources': survey_sources(sources)}),
        'component_ids': sorted(set(ids)), 'decisions': spec.get('decisions', []),
        'open_items': spec.get('open_items', []),
        'evidence': [{k: row[k] for k in ('name', 'status', 'geometry_fingerprint', 'evidence', 'next_action') if k in row}
            for row in spec.get('engineering_checks', []) + spec.get('checking_evidence', [])]}


def read_record(path):
    record = json.loads(Path(path).read_text())
    if record.get('schema_version') != VERSION:
        raise ValueError('Unsupported project version; explicitly migrate or rebuild')
    return record


def save(path, record):
    Path(path).write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')


def initialize(spec_path, kind, construction=None, concept_exception=None, complete_request=None):
    mode = route(kind, construction, concept_exception)
    if 'question' in mode:
        return mode
    spec, snap = snapshot(spec_path)
    if mode['fixture_kind'] == 'checking' and spec.get('inspection', {}).get('construction') != mode['construction']:
        raise ValueError('Inspection construction must match selected mode')
    if mode['fixture_kind'] == 'weld' and spec.get('inspection'):
        raise ValueError('Weld spec must not retain a checking plan')
    record = {'schema_version': VERSION, **snap, **mode, 'stage': 'concept', 'retired_ids': [],
        'baseline_ids': snap['component_ids'],
        'authorization': None, 'datum_review': None, 'history': [], 'readiness': {k: False for k in
            ('cad_verified', 'fabrication_ready', 'fixture_calibrated', 'inspection_validated')}}
    if complete_request:
        authorize(record, complete_request, initial=True)
    return record


def resume(spec_path, record):
    """Unauthorized concept iteration may drift; anything authorized still demands a checkpoint."""
    spec, current = snapshot(spec_path)
    if record.get('schema_version') != VERSION:
        raise ValueError('Unsupported project version')
    if current['input_digest'] == record['input_digest']:
        known = record.get('source_geometry') or {}
        stale = lambda p: p not in known or isinstance(known[p], str)   # absent, or a pre-datum-level fingerprint
        if any(stale(x['path']) for x in current['sources']):
            record['source_geometry'] = {x['path']: geometry_fingerprint(x['path']) for x in current['sources']}
        return current
    if (record.get('authorization') or current['revision'] != record['revision']
            or current['project_id'] != record['project_id']):
        raise ValueError('Source/spec changed; re-survey if necessary and checkpoint before reuse')
    if ([(x['role'], x['sha256']) for x in survey_sources(current['sources'])]
            != [(x['role'], x['sha256']) for x in survey_sources(record['sources'])]
            or current['coordinate_frame'] != record['coordinate_frame']) and not (
            current['coordinate_frame'] == record['coordinate_frame'] and rebase_sources(spec, current, record)):
        raise ValueError('Source/frame changed; fresh survey required (checkpoint --resurveyed)')
    if set(current['component_ids']) & set(record['retired_ids']):
        raise ValueError('Do not recycle retired component IDs')
    record.update(current)
    record['stage'] = 'concept'
    return current


def checkpoint(spec_path, record, resurveyed=False):
    spec, snap = snapshot(spec_path)
    if snap['project_id'] != record['project_id']:
        raise ValueError('Cannot change project identity')
    old_sources = [(x['role'], x['sha256']) for x in survey_sources(record['sources'])]
    new_sources = [(x['role'], x['sha256']) for x in survey_sources(snap['sources'])]
    if old_sources != new_sources or snap['coordinate_frame'] != record['coordinate_frame']:
        if snap['coordinate_frame'] == record['coordinate_frame'] and rebase_sources(spec, snap, record):
            record['datum_digest'] = snap['datum_digest']   # rebase restamped the review to it
        elif not resurveyed:
            raise ValueError('Source/frame changed; fresh survey required (--resurveyed only after surveying)')
    if snap['input_digest'] == record['input_digest']:
        return record
    if snap['revision'] == record['revision']:
        raise ValueError('Changed spec requires a new revision')
    if set(snap['component_ids']) & set(record['retired_ids']):
        raise ValueError('Do not recycle retired component IDs')
    fresh = initialize(spec_path, record['fixture_kind'], record['construction'], record.get('exception_reason'))
    fresh['retired_ids'] = sorted(set(record['retired_ids']) |
        (set(record.get('baseline_ids', record['component_ids'])) - set(snap['component_ids'])))
    fresh['history'] = record['history'] + [{'revision': record['revision'], 'input_digest': record['input_digest'], 'stage': record['stage']}]
    if not resurveyed and fresh['datum_digest'] == record.get('datum_digest'):
        for key in ('datum_review', 'datum_preview'):
            if (record.get(key) or {}).get('datum_digest') == fresh['datum_digest']:
                fresh[key] = record[key]
    return fresh


def datum_reviewed(record):
    """The ack follows the datum scheme itself, not every unrelated spec edit in the concept loop."""
    review = record.get('datum_review') or {}
    return bool(record.get('datum_digest')) and review.get('datum_digest') == record['datum_digest']


def datum_ok(record, note):
    if not isinstance(note, str) or not note.strip():
        raise ValueError('Record the actual datum-scheme review words')
    shown = (record.get('datum_preview') or {}).get('datum_digest')
    if not shown or shown != record.get('datum_digest'):
        raise ValueError('Generate a current datum scheme preview before reviewing it')
    record['datum_review'] = {'note': note.strip(), 'datum_digest': record['datum_digest'],
        'input_digest': record['input_digest']}
    return record['datum_review']


def authorize(record, request, initial=False):
    if record['concept_only']:
        raise ValueError('Concept-only exception cannot be finalized')
    if not isinstance(request, str) or not request.strip():
        raise ValueError('Record the actual explicit user request')
    if not initial and record['stage'] not in ('preview', 'finalized', 'finalization_needs_review'):
        raise ValueError('Generate/review concept before requesting finalization')
    record['authorization'] = {'user_request': request.strip(), 'input_digest': record['input_digest'],
        'scope': 'package generation only; not engineering approval', 'initial_complete_request': initial}
    return record


def finalization_allowed(spec_path, record):
    resume(spec_path, record)
    auth = record.get('authorization')
    if record['concept_only'] or not auth or auth['input_digest'] != record['input_digest']:
        raise ValueError('Explicit current user package authorization required')
    if record['stage'] not in ('preview', 'finalized', 'finalization_needs_review'):
        raise ValueError('Concept preview must be generated before finalization')


def finalize(spec_path, record, out):
    finalization_allowed(spec_path, record)
    if record['construction'] == 'block':
        handoff = {'revision': record['revision'], 'input_digest': record['input_digest'],
            'stage': record['stage'], 'event': 'manual_block_finalization_required'}
        if handoff not in record['history']:
            record['history'].append(handoff)
        return {'status': 'manual_block_finalization_required', 'reference': 'references/finalization.md',
            'recorded_in_history': True}
    if record['fixture_kind'] == 'checking':
        from build_check import build
    else:
        from build import build
    result = build(spec_path, out)
    ver = json.loads((Path(result['delivery']) / 'JSON/verification.json').read_text())
    record['readiness'] = {k: ver.get(k, ver.get('geometry_status') == 'pass' if k == 'cad_verified' else False)
        for k in record['readiness']}
    record['stage'] = 'finalized' if result['exit_code'] == 0 else 'finalization_needs_review'
    record['open_items'] = ver.get('open_items', [])
    return {k: v for k, v in result.items() if k not in ('cad', 'plates', 'joints')}


def run_concept(spec_path, out, record, png=False):
    if not datum_reviewed(record):
        raise ValueError('Review the datum scheme first: workflow.py datum, then datum-ok --note')
    from preview import generate
    result = generate(spec_path, out, record['fixture_kind'], record['construction'], render=png)
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    if result['blocking']:
        raise ValueError('no preview until fixed: ' + json.dumps(result['blocking'], separators=(',', ':')))
    record['stage'] = 'preview'; record['preview'] = result
    return result


def concept_line(result):
    """One line for the chat; the full result stays in OUT/result.json."""
    checks = ' '.join(f'{k}={v}' for k, v in sorted(result.get('checks', {}).items()))
    return f"blocking=[] {checks} html={result.get('html')} bytes={result.get('bytes')}"


def action_line(action, result, record):
    """One line for the chat; the full result stays in project.json."""
    head = f"{record['revision']} ok stage={record['stage']}"
    if action == 'resume':
        return (f"{head} datum_reviewed={datum_reviewed(record)} authorized={bool(record.get('authorization'))}"
                f" open_items={len(record.get('open_items') or [])}")
    if action == 'datum':
        return (f"{head} html={result['html']} bytes={result['bytes']} off_surface={result['off_surface']}"
                f" features_without_check={result['features_without_check']}")
    if action == 'datum-ok':
        return f"{head} datum_reviewed={datum_reviewed(record)}"
    if action == 'authorize':
        return f"{head} authorized: {record['authorization']['scope']}"
    if 'status' in result:   # block construction hands off to references/finalization.md
        return f"{head} status={result['status']} see={result['reference']}"
    return (f"{head} overall={result['overall_status']} geometry={result['geometry_status']}"
            f" exit_code={result['exit_code']} delivery={result['delivery']}"
            f" delivery_validation={json.dumps(result['delivery_validation'], separators=(',', ':'))}")


def run_job(cmd, cwd, tag, log):
    """Run a job script; the log keeps full output, the chat gets its last line."""
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()
    with open(log, 'a') as f:
        f.write(f'$ {cmd}\n{out}\n')
    tail = out.splitlines()[-1] if out else ''
    if p.returncode:
        raise ValueError(f'{tag} failed (exit {p.returncode}, full output in {log}): {tail}')
    return tail


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['route', 'init', 'resume', 'checkpoint', 'datum', 'datum-ok', 'concept', 'revise',
                                      'authorize', 'finalize'])
    p.add_argument('spec', nargs='?'); p.add_argument('record', nargs='?'); p.add_argument('out', nargs='?')
    p.add_argument('--kind', choices=['weld', 'checking', 'check']); p.add_argument('--construction')
    p.add_argument('--concept-exception'); p.add_argument('--complete-package-request'); p.add_argument('--request')
    p.add_argument('--note')
    p.add_argument('--resurveyed', action='store_true')
    p.add_argument('--build'); p.add_argument('--verify')
    p.add_argument('--png', action='store_true', help='also render review PNGs at concept')
    a = p.parse_args()
    if a.action == 'route':
        result = route(a.kind, a.construction, a.concept_exception)
    elif a.action == 'init':
        result = initialize(a.spec, a.kind, a.construction, a.concept_exception, a.complete_package_request)
        if 'question' not in result:
            if Path(a.record).exists():
                raise ValueError('Project exists; resume or checkpoint instead of overwriting')
            save(a.record, result)
            result = f"{result['revision']} ok stage={result['stage']} record={a.record}"
    elif a.action == 'revise':
        # build -> checkpoint -> concept -> verify, one summary line
        cwd, log = Path(a.spec).resolve().parent, Path(a.out) / 'revise.log'
        Path(a.out).mkdir(parents=True, exist_ok=True); log.write_text('')
        lines = ['build: ' + run_job(a.build, cwd, 'build', log)] if a.build else []
        record = checkpoint(a.spec, read_record(a.record), a.resurveyed); save(a.record, record)
        resume(a.spec, record)
        lines.append('concept: ' + concept_line(run_concept(a.spec, a.out, record, a.png))); save(a.record, record)
        if a.verify:
            lines.append('verify: ' + run_job(a.verify, cwd, 'verify', log))
        print(f"{record['revision']} ok | " + ' | '.join(lines))
        return
    else:
        record = read_record(a.record)
        if a.action == 'checkpoint':
            record = checkpoint(a.spec, record, a.resurveyed)
            result = f"{record['revision']} ok stage={record['stage']} datum_reviewed={datum_reviewed(record)}"
        else:
            resume(a.spec, record)
            if a.action == 'resume': result = record
            elif a.action == 'authorize': result = authorize(record, a.request)
            elif a.action == 'datum':
                from datum_preview import generate
                result = generate(a.spec, a.out)
                record['stage'] = 'datum_preview'
                record['datum_preview'] = {**result, 'datum_digest': record['datum_digest']}
            elif a.action == 'datum-ok': result = datum_ok(record, a.note)
            elif a.action == 'concept': result = concept_line(run_concept(a.spec, a.out, record, a.png))
            else: result = finalize(a.spec, record, a.out)
            if not isinstance(result, str): result = action_line(a.action, result, record)
        save(a.record, record)
    print(result if isinstance(result, str) else json.dumps(result, indent=2))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise SystemExit('WORKFLOW STOPPED: ' + str(exc))
