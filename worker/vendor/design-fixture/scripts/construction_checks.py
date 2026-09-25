"""Validate v8 engineering evidence coverage; not a CAD or strength solver.

Accepted records must describe actual reopened CAD and reference its named solids.
Missing/invalid evidence cannot turn the three new engineering gates into passes.
"""
import math
import re
from collections import Counter

GATES = ('rib_construction', 'fastener_access', 'pin_mechanisms')
RIB_SECTIONS = ('load_path', 'bracing', 'joints', 'dry_fit', 'fabrication_sequence', 'handling_clearance')
ACCESS_SECTIONS = ('screw_end', 'installation', 'tightening', 'drilling', 'tapping', 'maintenance')
PIN_SECTIONS = ('fits', 'retention', 'relief_orientation', 'release')
MOVING_SECTIONS = ('guidance', 'stroke', 'operator_access')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def evidence_errors(check, spec, fingerprint, shape_names=None):
    """Return errors for claimed passes. Unknown/fail/exception never certify readiness.

    Build calls without shape_names, then delivery validation supplies reopened STEP
    names. Evidence file hashes are checked by the existing build evidence workflow.
    """
    name = check.get('name')
    if name not in GATES or check.get('status') != 'pass':
        return []
    errors = []
    def err(message):
        errors.append(f'{name}: {message}')
    if check.get('geometry_fingerprint') != fingerprint:
        err('evidence is stale or lacks geometry fingerprint')
    evidence = check.get('evidence')
    if not isinstance(evidence, list) or not evidence or not all(isinstance(e, dict) and _text(e.get('file')) and re.fullmatch(r'[0-9a-f]{64}', str(e.get('sha256', ''))) for e in evidence):
        err('accepted evidence must identify report files and SHA-256 hashes')
    measured = check.get('measured')
    if not isinstance(measured, dict) or measured.get('basis') != 'reopened_step':
        err('measurements must identify basis reopened_step')
        return errors
    rows = measured.get('items')
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        err('items must be a list of per-component measurements')
        return errors
    pins = spec.get('pin_locators', [])
    if not isinstance(pins, list) or not all(isinstance(p, dict) for p in pins):
        err('pin_locators must be a list of pin records')
        return errors
    if name == 'rib_construction':
        inventory = {p['name']: p for p in spec.get('plates', [])}
    elif name == 'fastener_access':
        inventory = {c['tag']: c for c in spec.get('clamps', [])}
    else:
        inventory = {}
        for pin in pins:
            key = pin.get('id')
            if not _text(key) or key in inventory:
                err('pin inventory requires unique nonempty ids')
                continue
            inventory[key] = pin
            if pin.get('mode') not in ('fixed', 'sliding', 'removable'):
                err(f'{key}: declare fixed, sliding or removable mode')
            if not _text(pin.get('shape_name')) or not pin['shape_name'].startswith('REF_PIN_'):
                err(f'{key}: pin shape_name must begin REF_PIN_')
            if not isinstance(pin.get('orientation_sensitive'), bool):
                err(f'{key}: declare orientation_sensitive true/false')
        pin_shapes = [p.get('shape_name') for p in pins if _text(p.get('shape_name'))]
        if len(pin_shapes) != len(set(pin_shapes)):
            err('multiple pin records share the same shape_name')
        if shape_names is not None:
            actual = {n for n in shape_names if n.startswith('REF_PIN_')}
            if actual != set(pin_shapes):
                err('pin inventory disagrees with exported REF_PIN_ solids')
    ids = [row.get('id') for row in rows]
    if any(not _text(i) for i in ids):
        err('each item requires a nonempty id')
        return errors
    if set(ids) != set(inventory) or any(n != 1 for n in Counter(ids).values()):
        err('item coverage must match inventory exactly without duplicates')
    if not inventory and not _text(measured.get('not_applicable_reason')):
        err('empty inventory requires a measured applicability explanation')

    def components(value, label):
        if not isinstance(value, list) or not value or not all(_text(v) for v in value):
            err(f'{label}: identify named CAD components')
        elif shape_names is not None and not set(value) <= shape_names:
            err(f'{label}: component absent from exported STEP')

    def sections(row, required):
        findings = row.get('findings', {})
        if not isinstance(findings, dict):
            err(f"{row['id']}: findings must be an object")
            return
        for section in required:
            f = findings.get(section)
            if not isinstance(f, dict) or f.get('status') != 'pass' or not _text(f.get('method')) or not isinstance(f.get('measurements'), dict) or not f['measurements'] or not isinstance(f.get('acceptance'), dict) or not f['acceptance']:
                err(f"{row['id']}/{section}: require method, measurements, acceptance and pass status")

    for row in rows:
        key = row['id']
        target = inventory.get(key)
        if target is None:
            continue
        components(row.get('component_names'), key)
        if name == 'rib_construction':
            required = bool(target.get('seat')) or abs(target.get('w', [0, 0, 1])[2]) < 0.99 or any(c.get('mount_plate') == key for c in spec.get('clamps', []))
            if row.get('applicable') is False:
                if required or not _text(row.get('reason')):
                    err(f'{key}: support/mount cannot be exempted; other plates need a reason')
                continue
            if row.get('applicable') is not True:
                err(f'{key}: declare applicable true/false')
            if key not in (row.get('component_names') or []):
                err(f'{key}: measured component list omits the reviewed plate')
            sections(row, RIB_SECTIONS)
        elif name == 'fastener_access':
            if target.get('mount_plate') not in (row.get('component_names') or []):
                err(f'{key}: component list omits clamp mounting plate')
            holes = row.get('holes')
            # The bundled hardware is GH-201-B; other hardware needs explicit hole IDs.
            expected = target.get('mounting_hole_ids', ['H1', 'H2', 'H3', 'H4'] if target.get('hardware') == 'GH-201-B' else [])
            if not expected or not isinstance(holes, list) or not all(isinstance(h, dict) for h in holes):
                err(f'{key}: identify every mounting hole and its access findings')
                continue
            if Counter(h.get('id') for h in holes) != Counter(expected):
                err(f'{key}: mounting hole coverage mismatch')
            for hole in holes:
                if not _text(hole.get('stage')):
                    err(f'{key}: identify manufacturing/assembly stage for hole')
                sections(dict(hole, id=f"{key}/{hole.get('id')}"), ACCESS_SECTIONS)
        else:
            mechanism = row.get('mechanism', {})
            if not isinstance(mechanism, dict):
                err(f'{key}: mechanism must map roles to CAD component names')
                continue
            removable = target.get('mode') == 'removable'
            moving = target.get('mode') in ('sliding', 'removable')
            roles = ['pin', 'carrier']
            if not removable:
                roles.append('retention')
            if moving:
                roles.append('bush')
                if removable:
                    roles.append('grip')
                else:
                    roles += ['handle', 'travel_stop']
                    if target.get('orientation_sensitive'):
                        roles.append('anti_rotation')
            # Optional hardware, when claimed, must also exist in the export.
            for role in sorted(set(roles) | set(mechanism)):
                components(mechanism.get(role), f'{key}/{role}')
                names = mechanism.get(role)
                declared = row.get('component_names')
                if (isinstance(names, list) and all(_text(n) for n in names)
                        and isinstance(declared, list) and all(_text(n) for n in declared)
                        and not set(names) <= set(declared)):
                    err(f'{key}/{role}: mechanism components omitted from component_names')
            if target.get('shape_name') not in (mechanism.get('pin') or []):
                err(f'{key}: mechanism does not identify its pin solid')
            sections(row, PIN_SECTIONS + (MOVING_SECTIONS if moving else ()))
            if moving:
                dims = row.get('motion_mm', {})
                dimensions = [('withdrawal', 'required_withdrawal'), ('minimum_guide_engagement', 'required_guide_engagement')]
                if removable:
                    dimensions.append(('grip_length', 'required_grip_length'))
                    operation = row.get('manual_operation')
                    fields = ['travel_reference', 'retention']
                    if target.get('orientation_sensitive'):
                        fields.append('relief_orientation')
                    for field in fields:
                        if not isinstance(operation, dict) or not _text(operation.get(field)):
                            err(f'{key}: manual_operation must describe {field}')
                for actual, limit in dimensions:
                    if not isinstance(dims, dict) or not _number(dims.get(actual)) or not _number(dims.get(limit)) or dims[limit] <= 0 or dims[actual] < dims[limit]:
                        err(f'{key}: insufficient or unmeasured {actual}')
    return errors
