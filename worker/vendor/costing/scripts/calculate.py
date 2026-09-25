#!/usr/bin/env python3
"""Strict BOM batch costing. All monetary calculations retain unrounded precision."""
import json
import copy
import math
import sys
from pathlib import Path


def number(value, name, positive=False, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if value < 0 or (positive and value == 0) or (integer and value != int(value)):
        raise ValueError(f'Invalid {name}: {value}')
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be nonempty text')
    return value


def fields(obj, required, optional=()):
    if not isinstance(obj, dict):
        raise ValueError('Expected an object')
    missing, extra = set(required) - obj.keys(), obj.keys() - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f'Missing fields: {sorted(missing)}; unknown fields: {sorted(extra)}')


def boolean(obj, key, default=False):
    v = obj.get(key, default)
    if type(v) is not bool:
        raise ValueError(f'{key} must be true or false, not text or numbers')
    return v


def nonempty_list(value, name):
    if not isinstance(value, list) or not value:
        raise ValueError(f'{name} must be a nonempty list')
    return value


def calculate(data):
    fields(data, ('schema_version', 'quantity', 'components', 'rows'), ('gross_margin', 'job', 'revision'))
    if type(data['schema_version']) is not int or data['schema_version'] != 2:
        raise ValueError('Use schema_version 2; migrate legacy rows using the calculator contract')
    q = number(data['quantity'], 'quantity', positive=True, integer=True)
    config = json.loads((Path(__file__).resolve().parent.parent / 'references/rates.json').read_text())
    margin = number(data.get('gross_margin', config['default_gross_margin']), 'gross_margin')
    if margin >= 1:
        raise ValueError('gross_margin must be less than 1')
    nodes = {}
    for c in nonempty_list(data['components'], 'components'):
        fields(c, ('id', 'name', 'parent_id', 'quantity_per_parent', 'make_buy'))
        cid = text(c['id'], 'component id')
        text(c['name'], 'component name')
        if cid in nodes or c['make_buy'] not in ('make', 'buy'):
            raise ValueError('Duplicate component id or invalid make_buy')
        number(c['quantity_per_parent'], 'quantity_per_parent', positive=True, integer=True)
        nodes[cid] = dict(c)
    roots = [c['id'] for c in nodes.values() if c['parent_id'] is None]
    if len(roots) != 1 or nodes[roots[0]]['quantity_per_parent'] != 1:
        raise ValueError('Exactly one root is required with quantity_per_parent 1')
    root = roots[0]
    quantities = {}
    def quantity(cid, trail=()):
        if cid in trail:
            raise ValueError('BOM cycle')
        if cid in quantities:
            return quantities[cid]
        c = nodes[cid]
        parent = c['parent_id']
        if parent is None:
            n = 1
        else:
            if not isinstance(parent, str) or parent not in nodes:
                raise ValueError(f'Unknown parent for {cid}')
            if nodes[parent]['make_buy'] == 'buy':
                raise ValueError('Bought components cannot have costed children; omit supplier internal BOM')
            n = quantity(parent, trail + (cid,)) * c['quantity_per_parent']
        quantities[cid] = n
        return n
    for cid in nodes:
        quantity(cid)
    rows, ids, unknown, procurement = [], set(), [], []
    charge_scopes = set()
    own = {cid: 0.0 for cid in nodes}
    categories = {}
    setup_total = one_off_total = absorbed_total = 0.0
    buy_rows = {cid: [] for cid, c in nodes.items() if c['make_buy'] == 'buy'}
    covered = set()
    supplier_units = {}
    common = {'id', 'name', 'kind', 'category', 'basis', 'component_id', 'allocations', 'unpriced',
              'one_off', 'extra_quantity', 'extra_quantity_basis', 'absorbed_in_margin'}
    kind_fields = {
        'process': {'setup_h', 'setup_count', 'pcs_per_h', 'resource', 'hourly_rate', 'rate_basis',
                    'setup_hourly_rate', 'cycle_seconds', 'cycle_basis'},
        'material': {'sheet_price', 'parts_per_sheet', 'sheet_size_mm', 'procurement', 'stock_moq_sheets'},
        'fixed': {'unit_price'},
        'supplier_batch': {'charge_scope', 'lines', 'minimum_batch_charge', 'batch_fee'},
        'shared_batch': {'charge_scope', 'batch_cost', 'setup_batch_cost', 'procurement'},
    }
    for row in nonempty_list(data['rows'], 'rows'):
        if not isinstance(row, dict) or row.get('kind') not in kind_fields:
            raise ValueError('Invalid row kind')
        kind = row['kind']
        fields(row, ('id', 'name', 'kind', 'category', 'basis'), common | kind_fields[kind])
        rid = text(row['id'], 'row id')
        text(row['name'], 'row name'); text(row['basis'], 'row basis')
        if rid in ids:
            raise ValueError('Duplicate row id')
        ids.add(rid)
        category = row['category']
        if category not in ('material', 'component_processing', 'assembly_finish', 'other'):
            raise ValueError('Invalid category')
        if (kind == 'material') != (category == 'material') and kind in ('material', 'process'):
            raise ValueError('Material rows use category material; process rows cannot')
        unpriced, one_off = boolean(row, 'unpriced'), boolean(row, 'one_off')
        absorbed = boolean(row, 'absorbed_in_margin')
        if absorbed and (kind != 'process' or unpriced or one_off):
            raise ValueError('absorbed_in_margin is only valid on priced recurring process rows')
        if ('component_id' in row) == ('allocations' in row):
            raise ValueError('Provide exactly one of component_id or allocations')
        shared = 'allocations' in row
        if shared:
            if kind not in ('supplier_batch', 'shared_batch'):
                raise ValueError('Allocations require a supplier_batch or shared_batch row')
            alloc = row['allocations']
            if not isinstance(alloc, dict) or not alloc:
                raise ValueError('Allocations must map component IDs to positive shares')
            for cid, share in alloc.items():
                if cid not in nodes: raise ValueError('Unknown allocation component')
                number(share, 'allocation share', positive=True)
            if not math.isclose(sum(alloc.values()), 1, abs_tol=1e-9, rel_tol=0):
                raise ValueError('Allocation shares must sum to 1')
            n = q
        else:
            cid = row['component_id']
            if not isinstance(cid, str) or cid not in nodes:
                raise ValueError('Unknown component_id')
            alloc = {cid: 1}
            n = q * quantities[cid]
        if any(cid in buy_rows for cid in alloc):
            if shared or kind != 'fixed' or one_off:
                raise ValueError('Bought components require one fixed purchase row; put later conversion on a make parent')
            buy_rows[row['component_id']].append(rid)
        if not one_off and not absorbed:
            covered.update(alloc)
        if kind in ('supplier_batch', 'shared_batch') and not unpriced:
            scope = text(row.get('charge_scope'), 'charge_scope')
            if scope in charge_scopes: raise ValueError('Duplicate shared charge scope; merge rows before allocation')
            charge_scopes.add(scope)
        if unpriced:
            if set(row) & kind_fields[kind] or 'extra_quantity' in row:
                raise ValueError('Unpriced rows must omit all pricing/cycle/procurement fields')
            unknown.append(rid)
            rows.append(dict(row, batch_cost=None, per_assembly=None, setup_batch_cost=None))
            continue
        extra = number(row.get('extra_quantity', 0), 'extra_quantity', integer=True)
        if extra:
            text(row.get('extra_quantity_basis'), 'extra_quantity_basis')
        if (shared or one_off or kind in ('supplier_batch', 'shared_batch')) and extra:
            raise ValueError('Model extra quantities within batch basis/lines for shared and one-off costs')
        run_n = (1 if one_off else n) + extra
        setup = 0.0
        if kind == 'process':
            if ('resource' in row) == ('hourly_rate' in row):
                raise ValueError('Use exactly one of resource or hourly_rate')
            if 'resource' in row:
                if row['resource'] not in config['resources']: raise ValueError('Unknown resource')
                resource = config['resources'][row['resource']]
                rate = resource['labour_per_hour'] + resource['machine_per_hour']
            else:
                rate = number(row['hourly_rate'], 'hourly_rate')
                text(row.get('rate_basis'), 'rate_basis')
            setup = number(row['setup_h'], 'setup_h') * number(row['setup_count'], 'setup_count', integer=True) * number(row.get('setup_hourly_rate', rate), 'setup_hourly_rate')
            pph = number(row['pcs_per_h'], 'pcs_per_h', positive=True)
            text(row['cycle_basis'], 'cycle_basis')
            seconds = row['cycle_seconds']
            if not isinstance(seconds, dict) or not seconds:
                raise ValueError('cycle_seconds must give named total-cycle elements')
            for label, value in seconds.items():
                text(label, 'cycle element'); number(value, 'cycle seconds')
            if not math.isclose(sum(seconds.values()), 3600 / pph, rel_tol=.01):
                raise ValueError('Cycle breakdown must reconcile to pcs_per_h within 1%')
            cost = setup + run_n / pph * rate
        elif kind == 'material':
            price = number(row['sheet_price'], 'sheet_price')
            yield_n = number(row['parts_per_sheet'], 'parts_per_sheet', positive=True, integer=True)
            dims = row['sheet_size_mm']
            if not isinstance(dims, list) or len(dims) != 2: raise ValueError('sheet_size_mm needs width and length')
            for dim in dims: number(dim, 'sheet dimension', positive=True)
            cost = run_n * price / yield_n
            if row.get('procurement') not in ('fresh', 'inventory', 'unknown'):
                raise ValueError('State procurement as fresh, inventory or unknown')
            moq = number(row['stock_moq_sheets'], 'stock_moq_sheets', integer=True)
            sheets = max(math.ceil(run_n / yield_n), moq)
            if not one_off:
                procurement.append({'row_id': rid, 'status': row['procurement'], 'whole_sheets_required': math.ceil(run_n / yield_n),
                                    'fresh_purchase_sheets': sheets, 'fresh_purchase_outlay': sheets * price,
                                    'remaining_capacity_parts': sheets * yield_n - run_n,
                                    'note': 'Fresh-purchase scenario; not added to allocated production cost.'})
        elif kind == 'fixed':
            cost = run_n * number(row['unit_price'], 'unit_price')
        elif kind == 'supplier_batch':
            raw = 0
            seen = set()
            for line in nonempty_list(row['lines'], 'supplier lines'):
                fields(line, ('component_id', 'quantity', 'unit_price', 'basis'))
                cid = line['component_id']
                if cid not in alloc or cid in seen: raise ValueError('Supplier line component must be a unique owner of this row')
                seen.add(cid)
                text(line['basis'], 'supplier line basis')
                units = number(line['quantity'], 'supplier quantity', positive=True, integer=True)
                if not one_off: supplier_units[cid] = supplier_units.get(cid, 0) + units
                raw += units * number(line['unit_price'], 'supplier unit price')
            cost = max(raw, number(row['minimum_batch_charge'], 'minimum_batch_charge')) + number(row['batch_fee'], 'batch_fee')
        else:
            cost = number(row['batch_cost'], 'batch_cost')
            setup = number(row.get('setup_batch_cost', 0), 'setup_batch_cost')
            if setup > cost: raise ValueError('Shared setup cannot exceed shared batch cost')
            if 'procurement' in row:
                p = row['procurement']
                fields(p, ('sheet_price', 'consumed_sheet_equivalents', 'purchase_sheets', 'basis'))
                text(p['basis'], 'procurement basis')
                price = number(p['sheet_price'], 'sheet_price')
                consumed = number(p['consumed_sheet_equivalents'], 'consumed sheets')
                purchased = number(p['purchase_sheets'], 'purchase sheets', integer=True)
                if purchased < math.ceil(consumed): raise ValueError('Purchase sheets below consumption')
                if category != 'material' or not math.isclose(cost, price * consumed, abs_tol=1e-8):
                    raise ValueError('Shared material cost must equal price times consumed sheet equivalents')
                procurement.append(dict(p, row_id=rid, purchase_outlay=price*purchased, remaining_sheet_equivalents=purchased-consumed))
        if not math.isfinite(cost): raise ValueError('Cost overflow')
        contributions = {cid: cost * share for cid, share in alloc.items()}
        if one_off:
            one_off_total += cost
        elif absorbed:
            absorbed_total += cost
        else:
            for cid, value in contributions.items(): own[cid] += value
            categories[category] = categories.get(category, 0) + cost
            setup_total += setup
        rows.append(dict(row, batch_cost=cost, per_assembly=None if one_off else cost/q,
                         per_component=None if shared or one_off else cost/n,
                         setup_batch_cost=setup, run_batch_cost=cost-setup,
                         allocated_batch_costs=contributions))
    for cid, units in supplier_units.items():
        if units < q * quantities[cid]:
            raise ValueError(f'Supplier lines for {cid} cover {units} units; batch needs {q * quantities[cid]}')
    for cid, purchases in buy_rows.items():
        if len(purchases) != 1: raise ValueError(f'Bought component {cid} requires exactly one purchase row')
    for cid in nodes:
        if cid not in covered and not any(c['parent_id'] == cid for c in nodes.values()):
            raise ValueError(f'Leaf component {cid} has no recurring cost or explicit unpriced row')
    children = {cid: [c['id'] for c in nodes.values() if c['parent_id'] == cid] for cid in nodes}
    rollup = {}
    def roll(cid):
        v = own[cid] + sum(roll(k) for k in children[cid])
        rollup[cid] = dict(nodes[cid], units_per_assembly=quantities[cid], own_batch_cost=own[cid],
                          rolled_batch_cost=v, unit_cost=v/(q*quantities[cid]), per_assembly=v/q)
        return v
    total = roll(root)
    if not math.isclose(total, sum(categories.values()), abs_tol=1e-8): raise ValueError('BOM reconciliation failed')
    unknown_recurring = [r['id'] for r in rows if r.get('unpriced') and not r.get('one_off', False)]
    selling = total / (1 - margin)
    snapshot = copy.deepcopy(data)
    snapshot['gross_margin'] = margin
    for row in snapshot['rows']:
        if row['kind'] == 'process' and not row.get('unpriced') and 'resource' in row:
            key = row.pop('resource')
            resource = config['resources'][key]
            row['hourly_rate'] = resource['labour_per_hour'] + resource['machine_per_hour']
            row['rate_basis'] = f'Saved resource {key}: labour {resource["labour_per_hour"]} + machine {resource["machine_per_hour"]}; AUD/h ex GST'
    return {'schema_version': 2, 'job': data.get('job'), 'revision': data.get('revision'), 'quantity': q,
            'input_snapshot': snapshot, 'status': 'known-cost subtotal' if unknown_recurring else 'estimated total',
            'rows': rows, 'bom': list(rollup.values()), 'root_id': root,
            'batch_cost': total, 'per_assembly': total/q, 'setup_batch_cost_included': setup_total,
            'category_batch_costs': categories, 'procurement': procurement, 'unpriced_items': unknown,
            'one_off_batch_cost': one_off_total, 'one_off_selling_price': one_off_total/(1-margin),
            'one_off_status': 'known-cost subtotal' if any(r.get('unpriced') and r.get('one_off') for r in rows) else 'estimated total',
            'gross_margin': margin, 'selling_per_assembly': total/q/(1-margin), 'selling_batch': total/(1-margin),
            'profit_per_assembly': total/q/(1-margin)-total/q, 'profit_batch': total/(1-margin)-total,
            'absorbed_batch_cost': absorbed_total, 'absorbed_per_assembly': absorbed_total/q,
            'effective_margin': (selling - total - absorbed_total)/selling if selling else None,
            'effective_margin_status': 'provisional: known recurring costs only' if unknown_recurring else 'after absorbed routine work',
            'selling_status': 'provisional: known recurring costs only; unpriced items additional' if unknown_recurring else 'estimated recurring selling price; one-offs separate'}


if __name__ == '__main__':
    try:
        with open(sys.argv[1], encoding='utf-8') as f:
            result = calculate(json.load(f))
        print(json.dumps(result, indent=2, allow_nan=False))
    except (KeyError, ValueError, TypeError, IndexError, OSError) as error:
        sys.exit(f'Input error: {error}')
