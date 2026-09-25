#!/usr/bin/env python3
"""Screen declared flange coverage and gap arithmetic, never CAD or physical conformity."""
import argparse
import json
import math
from pathlib import Path

STANDARD = {'nominal_gap_mm': 3.0, 'go_mm': 2.5, 'no_go_mm': 3.5}


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def classify_gap(gap, go=2.5, no_go=3.5):
    """Ideal numeric screen; actual calibrated gauge insertion is a separate observation."""
    if not all(number(v) for v in (gap, go, no_go)) or not 0 < go < no_go or gap < 0:
        raise ValueError('Expected finite nonnegative gap and 0 < GO < NO-GO')
    if math.isclose(gap, go, rel_tol=0, abs_tol=1e-9) or math.isclose(gap, no_go, rel_tol=0, abs_tol=1e-9):
        return 'boundary_review'
    return 'inside_ideal_window' if go < gap < no_go else 'outside_ideal_window'


def screen(plan):
    errors, unresolved, results = [], [], []
    if not isinstance(plan, dict):
        return {'status': 'invalid', 'errors': ['Plan must be an object'], 'unresolved': [], 'stations': []}
    if plan.get('units') != 'mm':
        errors.append('units must be mm')
    if plan.get('construction') not in ('laser_rib', 'printed_solid'):
        errors.append('construction must be laser_rib or printed_solid')
    if not plan.get('datum_scheme'):
        unresolved.append('Missing datum scheme')
    flanges = plan.get('flanges')
    if not isinstance(flanges, list) or not flanges:
        errors.append('A nonempty measured flange inventory is required')
        flanges = []
    flange_ids, station_ids = set(), set()
    for flange in flanges:
        if not isinstance(flange, dict):
            errors.append('Each flange must be an object'); continue
        fid = flange.get('id')
        if not isinstance(fid, str) or not fid.strip() or fid in flange_ids:
            errors.append('Missing or duplicate flange id'); continue
        flange_ids.add(fid)
        if not flange.get('source_feature'):
            unresolved.append(f'{fid}: missing source feature identity')
        if flange.get('limitation'):
            unresolved.append(f'{fid}: {flange["limitation"]}')
        checks = flange.get('checks', [])
        if not isinstance(checks, list):
            errors.append(f'{fid}: checks must be a list'); continue
        if not checks:
            unresolved.append(f'{fid}: no checking method recorded')
        for station in checks:
            if not isinstance(station, dict):
                errors.append(f'{fid}: check must be an object'); continue
            sid = station.get('id')
            if not isinstance(sid, str) or not sid.strip() or sid in station_ids:
                errors.append(f'{fid}: missing or duplicate station id'); continue
            station_ids.add(sid)
            kind = station.get('kind')
            if kind not in ('surface_gap', 'edge_gap', 'alternative'):
                errors.append(f'{sid}: invalid checking kind'); continue
            if not station.get('scope') or not station.get('approach'):
                unresolved.append(f'{sid}: specify characteristic scope and gauge approach')
            conflict = station.get('drawing_conflict')
            if not isinstance(conflict, bool):
                unresolved.append(f'{sid}: drawing_conflict must be true/false (false also allowed when no drawing exists)')
            if conflict is True:
                unresolved.append(f'{sid}: drawing/shop-standard conflict: {station.get("conflict_note", "explanation needed")}')
            if kind == 'alternative':
                if not station.get('method') or not station.get('acceptance'):
                    unresolved.append(f'{sid}: alternative requires method and acceptance basis')
                results.append({'id': sid, 'kind': kind, 'scope': 'Declared alternative only; not independently validated'})
                continue
            point, direction = station.get('point_mm'), station.get('direction')
            if not isinstance(point, list) or len(point) != 3 or not all(number(v) for v in point):
                errors.append(f'{sid}: point_mm must be three finite numbers')
            if not isinstance(direction, list) or len(direction) != 3 or not all(number(v) for v in direction) or not math.isclose(sum(v*v for v in direction), 1, abs_tol=1e-6):
                errors.append(f'{sid}: direction must be a finite unit vector')
            values = {key: station.get(key, default) for key, default in STANDARD.items()}
            if not all(number(v) for v in values.values()) or not 0 < values['go_mm'] < values['nominal_gap_mm'] < values['no_go_mm']:
                errors.append(f'{sid}: require 0 < GO < nominal gap < NO-GO'); continue
            basis = station.get('basis', 'shop_standard')
            if basis not in ('shop_standard', 'job_override'):
                errors.append(f'{sid}: basis must be shop_standard or job_override')
            changed = any(not math.isclose(values[k], v, rel_tol=0, abs_tol=1e-9) for k, v in STANDARD.items())
            if basis == 'shop_standard' and changed:
                errors.append(f'{sid}: shop_standard requires 3.0 nominal, 2.5 GO, 3.5 NO-GO')
            if basis == 'job_override' and not station.get('override_source'):
                unresolved.append(f'{sid}: job override needs explicit requirement/source')
            row = {'id': sid, 'kind': kind, 'basis': basis, **values,
                   'go_rule': 'must_enter', 'no_go_rule': 'must_not_enter'}
            if 'observed_gap_mm' in station:
                try:
                    row['numeric_screen'] = classify_gap(station['observed_gap_mm'], values['go_mm'], values['no_go_mm'])
                except ValueError as exc:
                    errors.append(f'{sid}: {exc}')
            results.append(row)
    return {'status': 'invalid' if errors else 'unresolved' if unresolved else 'plan_screen_pass',
            'scope': 'Declared coverage and gauge arithmetic only; no CAD, manufacturing or calibration verification',
            'flange_count': len(flange_ids), 'station_count': len(station_ids),
            'errors': errors, 'unresolved': unresolved, 'stations': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    args = parser.parse_args()
    try:
        result = screen(json.loads(args.plan.read_text()))
    except (OSError, ValueError) as exc:
        result = {'status': 'invalid', 'errors': [str(exc)], 'unresolved': []}
    print(json.dumps(result, indent=2, allow_nan=False))
    return {'plan_screen_pass': 0, 'unresolved': 2, 'invalid': 1}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
