#!/usr/bin/env python3
"""Apply a small edit to spec.json instead of rewriting it.

The patch is JSON (inline or a file path). Objects merge recursively and `null` deletes a key. A list
of named items (plates, clamps, contacts, joints with an id...) is edited through an object keyed by
`name`, `tag` or `id`: `{"plates": {"R1": {"outer": [...]}, "R9": null}}` changes R1 and removes R9;
an unknown key appends a new item carrying that key. A patch list replaces the whole list.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

KEYS = ('name', 'tag', 'id')


def item_key(items):
    return next((k for k in KEYS if items and all(isinstance(x, dict) and k in x for x in items)), None)


def merge(base, patch):
    if isinstance(patch, dict) and isinstance(base, list):
        key = item_key(base)
        if key is None: raise ValueError('Patch object needs a list of items keyed by name, tag or id')
        out, index = list(base), {x[key]: i for i, x in enumerate(base)}
        drop = set()
        for k, v in patch.items():
            if k in index:
                if v is None: drop.add(index[k])
                else: out[index[k]] = merge(out[index[k]], v)
            elif v is not None:
                out.append({key: k, **v})
        return [x for i, x in enumerate(out) if i not in drop]
    if isinstance(patch, dict) and isinstance(base, dict):
        out = dict(base)
        for k, v in patch.items():
            if v is None: out.pop(k, None)
            else: out[k] = merge(out[k], v) if k in out else v
        return out
    return patch


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('spec'); ap.add_argument('patch', help='inline JSON or a path to a JSON file')
    a = ap.parse_args()
    text = Path(a.patch).read_text() if Path(a.patch).is_file() else a.patch
    spec = Path(a.spec)
    data = merge(json.loads(spec.read_text()), json.loads(text))
    spec.write_text(json.dumps(data, indent=2))
    print('revision', data.get('revision'))


if __name__ == '__main__':
    main()
