"""Regression checks for shop-stock nesting and laser-compatible etch geometry."""
from pathlib import Path
import sys
import tempfile
import unittest

import ezdxf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nest_dxf import nest, stroke_text


def plate(name, width, height):
    return {
        "name": name,
        "outer": [[0, 0], [width, 0], [width, height], [0, height]],
        "holes": [],
    }


class NestDxfTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "nested.dxf"
        self.spec = {
            "thickness_mm": 5.0,
            "plates": [
                plate("BASE_A1", 250, 180),
                plate("RIB-B2", 220, 110),
                plate("CAP_3.0", 160, 90),
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_shop_sheet_preserves_rectangular_remnant(self):
        report = nest(self.spec, self.path)
        self.assertEqual(report["physical_sheet_mm"], [2400.0, 1200.0])
        self.assertEqual(report["usable_size_mm"], [2400.0, 1100.0])
        self.assertEqual(report["clamp_exclusion_area_mm2"], 240000.0)
        self.assertLess(report["used_strip_mm"][0], 2400.0)
        self.assertEqual(
            report["largest_rectangular_remnant_mm"],
            [2400.0 - report["used_strip_mm"][0], 1100.0],
        )
        self.assertEqual(report["status"], "pass")

    def test_etch_is_joined_open_polyline_geometry(self):
        report = nest(self.spec, self.path)
        doc = ezdxf.readfile(self.path)
        modelspace = doc.modelspace()
        self.assertFalse(list(modelspace.query('TEXT[layer=="ETCH"]')))
        self.assertFalse(list(modelspace.query('MTEXT[layer=="ETCH"]')))
        etch = list(modelspace.query('LWPOLYLINE[layer=="ETCH"]'))
        self.assertTrue(etch)
        self.assertTrue(all(not entity.closed for entity in etch))
        self.assertTrue(any(len(list(entity.get_points())) > 2 for entity in etch))
        self.assertLess(report["etch_polylines"], report["etch_source_segments"])
        self.assertEqual(report["etch_text_entities"], 0)
        self.assertTrue(report["etch_labels_inside_profiles"])

    def test_reference_boundaries_never_enter_cut_layer(self):
        nest(self.spec, self.path)
        doc = ezdxf.readfile(self.path)
        modelspace = doc.modelspace()
        for layer in (
            "STOCK_REFERENCE", "USABLE_REFERENCE", "CLAMP_EXCLUSION_REFERENCE", "NEST_REFERENCE"
        ):
            self.assertTrue(list(modelspace.query(f'LWPOLYLINE[layer=="{layer}"]')))
        cuts = list(modelspace.query('LWPOLYLINE[layer=="CUT"]'))
        self.assertTrue(cuts)
        self.assertTrue(all(entity.closed for entity in cuts))

    def test_supported_shop_label_characters(self):
        paths, source_segments = stroke_text("A1_TEST-2.0", 3.5, (0, 0))
        self.assertTrue(paths)
        self.assertGreater(source_segments, len(paths))


if __name__ == "__main__":
    unittest.main()
