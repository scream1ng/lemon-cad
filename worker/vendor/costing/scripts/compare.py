#!/usr/bin/env python3
"""Compare calculator result snapshots; report all changes without inventing reasons."""
import json
import math
import sys
from calculate import calculate


def compare(old, new):
    # Recalculate snapshots, rather than trusting possibly stale/edited totals.
    old, new = calculate(old['input_snapshot']), calculate(new['input_snapshot'])
    old_rows, new_rows = ({r['id']: r for r in x['rows']} for x in (old, new))
    old_inputs, new_inputs = ({r['id']: r for r in x['input_snapshot']['rows']} for x in (old, new))
    changes = []
    for rid in sorted(old_rows.keys() | new_rows.keys()):
        a, b = old_rows.get(rid), new_rows.get(rid)
        def amounts(row, q):
            if not row or row.get('unpriced'): return 0, 0, 0
            if row.get('one_off'): return 0, row['batch_cost'], 0
            return (0, 0, row['batch_cost']/q) if row.get('absorbed_in_margin') else (row['batch_cost']/q, 0, 0)
        av, ao, aa = amounts(a, old['quantity']); bv, bo, ba = amounts(b, new['quantity'])
        ia, ib = old_inputs.get(rid, {}), new_inputs.get(rid, {})
        changed = {k: {'previous': ia.get(k), 'revised': ib.get(k)} for k in sorted(ia.keys() | ib.keys()) if ia.get(k) != ib.get(k)}
        if changed or any(not math.isclose(x, y, abs_tol=1e-10) for x, y in ((av, bv), (ao, bo), (aa, ba))):
            changes.append({'id': rid, 'input_changes': changed, 'previous_known_cost_per_assembly': av,
                            'revised_known_cost_per_assembly': bv, 'cost_delta_per_assembly': bv-av,
                            'one_off_cost_delta': bo-ao, 'absorbed_cost_delta_per_assembly': ba-aa,
                            'previous_unpriced': bool(a and a.get('unpriced')),
                            'revised_unpriced': bool(b and b.get('unpriced'))})
    delta = new['per_assembly']-old['per_assembly']
    if not math.isclose(sum(c['cost_delta_per_assembly'] for c in changes), delta, abs_tol=1e-8):
        raise ValueError('Comparison does not reconcile')
    absorbed_delta = new['absorbed_per_assembly']-old['absorbed_per_assembly']
    if not math.isclose(sum(c['absorbed_cost_delta_per_assembly'] for c in changes), absorbed_delta, abs_tol=1e-8):
        raise ValueError('Absorbed cost comparison does not reconcile')
    top_changes = {k: {'previous':old['input_snapshot'].get(k), 'revised':new['input_snapshot'].get(k)}
                   for k in ('quantity', 'components', 'gross_margin', 'job', 'revision')
                   if old['input_snapshot'].get(k) != new['input_snapshot'].get(k)}
    return {'changes': changes, 'context_changes':top_changes, 'cost_delta_per_assembly':delta,
            'selling_delta_per_assembly':new['selling_per_assembly']-old['selling_per_assembly'],
            'one_off_cost_delta':new['one_off_batch_cost']-old['one_off_batch_cost'],
            'absorbed_cost_delta_per_assembly':absorbed_delta,
            'note':'Explain every changed basis in the report. Unpriced amounts are absent from known-cost deltas, not free. Saved snapshots freeze the effective margin and resource rates.'}


if __name__ == '__main__':
    try:
        with open(sys.argv[1]) as f: old=json.load(f)
        with open(sys.argv[2]) as f: new=json.load(f)
        print(json.dumps(compare(old,new),indent=2,allow_nan=False))
    except (KeyError, ValueError, TypeError, IndexError, OSError) as e:
        sys.exit(f'Input error: {e}')
