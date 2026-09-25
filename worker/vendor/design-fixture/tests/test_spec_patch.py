"""Small spec edits merge by item name instead of rewriting spec.json."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from spec_patch import merge


class SpecPatchTests(unittest.TestCase):
    BASE = {'revision': 'R1', 'plates': [{'name': 'R1', 'outer': [1], 'holes': []}, {'name': 'R2', 'outer': [2]}],
            'clamps': [{'tag': 'T1', 'contact': [0, 0, 0]}], 'units': 'mm'}

    def test_named_items_change_add_and_delete(self):
        out = merge(self.BASE, {'revision': 'R2', 'plates': {'R1': {'outer': [9]}, 'R2': None, 'X1': {'outer': [3]}},
                                'clamps': {'T1': {'contact': [1, 2, 3]}}})
        self.assertEqual(out['revision'], 'R2')
        self.assertEqual(out['plates'], [{'name': 'R1', 'outer': [9], 'holes': []}, {'name': 'X1', 'outer': [3]}])
        self.assertEqual(out['clamps'][0]['contact'], [1, 2, 3])
        self.assertEqual(self.BASE['plates'][0]['outer'], [1])  # input untouched

    def test_null_deletes_and_list_replaces(self):
        out = merge(self.BASE, {'units': None, 'plates': [{'name': 'Z'}]})
        self.assertNotIn('units', out); self.assertEqual(out['plates'], [{'name': 'Z'}])

    def test_unkeyed_list_rejects_object_patch(self):
        with self.assertRaises(ValueError): merge({'a': [1, 2]}, {'a': {'x': 1}})


if __name__ == '__main__': unittest.main()
