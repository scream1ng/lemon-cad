"""Tab option cache: a hit gives the same layout as a fresh search, and an edited plate misses."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import tabs_slots
from cap_joints import design as cap_design
from fixture_common import validate_spec


class TabCacheTests(unittest.TestCase):
    def layout(self, spec, cache_dir):
        spec = copy.deepcopy(spec); spec['_dir'] = cache_dir
        validate_spec(spec); cap_design(spec, lambda *a: None)
        report = tabs_slots.design(spec, lambda *a: None)
        return report['tab_positions'], [p['outer'] for p in spec['plates']]

    def test_hit_matches_fresh_search_and_edit_misses(self):
        spec = json.loads((ROOT / 'examples/flat-plate/spec.json').read_text())
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / '.fixture-cache/tabs'
            fresh = self.layout(spec, None)
            self.assertEqual(self.layout(spec, d), fresh)                 # fills the cache
            n = len(list(cache.glob('*.pickle')))
            self.assertEqual(self.layout(spec, d), fresh)                 # served from it
            self.assertEqual(len(list(cache.glob('*.pickle'))), n)
            part = next(p for p in spec['plates'] if p.get('seat'))['part_number']
            for p in spec['plates']:
                if p.get('part_number') == part:
                    right = max(x for x, y in p['outer'] if abs(y) < 1e-6)
                    p['outer'] = [[x + 6 if x == right else x, y] for x, y in p['outer']]
            self.assertEqual(self.layout(spec, d), self.layout(spec, None))
            self.assertGreater(len(list(cache.glob('*.pickle'))), n)


if __name__ == '__main__':
    unittest.main()
