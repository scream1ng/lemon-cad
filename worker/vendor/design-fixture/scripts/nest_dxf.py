#!/usr/bin/env python3
"""Nest laser-cut plates on shop stock and write a verified cutting DXF.

Default shop stock is 2400 x 1200 mm with a 2400 x 1100 mm usable zone. Parts
are packed into the narrowest left-hand strip that fits, preserving a large,
rectangular remnant. Plate IDs are single-stroke open LWPOLYLINE geometry; DXF
TEXT/MTEXT entities are deliberately not used.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import ezdxf
from shapely import affinity
from shapely.geometry import MultiLineString, Polygon, box
from shapely.ops import polylabel

from fixture_common import load_spec, poly, write_json

DEFAULTS = {
    "gap_mm": 8.0,
    "margin_mm": 15.0,
    "stock_size_mm": [2400.0, 1200.0],
    "usable_origin_mm": [0.0, 0.0],
    "usable_size_mm": [2400.0, 1100.0],
    "strip_width_step_mm": 10.0,
    "etch_height_mm": 3.5,
    "etch_edge_clearance_mm": 0.8,
}

# Compact 16-segment-style, single-line industrial alphabet. Each token names
# one line segment; connected tokens are joined into the fewest open polylines.
SEGMENTS = {
    "a": ((0.18, 1.00), (0.82, 1.00)),
    "b": ((0.82, 1.00), (0.82, 0.52)),
    "c": ((0.82, 0.48), (0.82, 0.00)),
    "d": ((0.18, 0.00), (0.82, 0.00)),
    "e": ((0.18, 0.00), (0.18, 0.48)),
    "f": ((0.18, 0.52), (0.18, 1.00)),
    "g1": ((0.18, 0.50), (0.50, 0.50)),
    "g2": ((0.50, 0.50), (0.82, 0.50)),
    "h": ((0.18, 1.00), (0.50, 0.50)),
    "i": ((0.82, 1.00), (0.50, 0.50)),
    "j": ((0.50, 0.50), (0.18, 0.00)),
    "k": ((0.50, 0.50), (0.82, 0.00)),
    "l": ((0.50, 1.00), (0.50, 0.50)),
    "m": ((0.50, 0.50), (0.50, 0.00)),
    "n": ((0.18, 1.00), (0.82, 0.00)),
    "o": ((0.82, 1.00), (0.18, 0.00)),
}

GLYPHS = {
    "0": "abcdef", "1": "bc", "2": "abdeg1g2", "3": "abcdg1g2",
    "4": "bcfg1g2", "5": "acdfg1g2", "6": "acdefg1g2", "7": "abc",
    "8": "abcdefg1g2", "9": "abcdfg1g2",
    "A": "abcefg1g2", "B": "abcdefg1g2", "C": "adef", "D": "abcdef",
    "E": "adefg1g2", "F": "aefg1g2", "G": "acdefg2", "H": "bcefg1g2",
    "I": "adlm", "J": "bcde", "K": "efg1ik", "L": "def", "M": "bcefhi",
    "N": "bcefn", "O": "abcdef", "P": "abefg1g2", "Q": "abcdefk",
    "R": "abefg1g2k", "S": "acdfg1g2", "T": "alm", "U": "bcdef",
    "V": "efik", "W": "bcefjk", "X": "hijk", "Y": "him", "Z": "adjk",
    "-": "g1g2", "_": "d",
}


def fits(a, b):
    return a[0] >= b[0] - 1e-7 and a[1] >= b[1] - 1e-7 and a[2] <= b[2] + 1e-7 and a[3] <= b[3] + 1e-7


def pack(plates, width, height, gap, margin):
    """Largest-first, 0/90-degree, best-short-side-fit rectangle packing."""
    free = [(margin, margin, width - margin + gap, height - margin + gap)]
    out = []
    for data in sorted(plates, key=lambda item: -Polygon(item["outer"]).area):
        profile = poly(data)
        candidates = []
        for angle in (0, 90):
            rotated = affinity.rotate(profile, angle, origin=(0, 0))
            bounds = rotated.bounds
            part_w = bounds[2] - bounds[0] + gap
            part_h = bounds[3] - bounds[1] + gap
            for free_rect in free:
                dw = free_rect[2] - free_rect[0] - part_w
                dh = free_rect[3] - free_rect[1] - part_h
                if min(dw, dh) >= -1e-6:
                    score = (min(dw, dh), max(dw, dh), free_rect[1], free_rect[0])
                    candidates.append((score, rotated, bounds, part_w, part_h, angle, free_rect))
        if not candidates:
            return None
        _, rotated, bounds, part_w, part_h, angle, free_rect = min(candidates, key=lambda candidate: candidate[0])
        x, y = free_rect[:2]
        used = (x, y, x + part_w, y + part_h)
        offset = [x - bounds[0], y - bounds[1]]
        out.append((data, affinity.translate(rotated, xoff=offset[0], yoff=offset[1]), angle, offset))
        new = []
        for rect in free:
            if rect[2] <= used[0] or rect[0] >= used[2] or rect[3] <= used[1] or rect[1] >= used[3]:
                new.append(rect)
                continue
            if rect[0] < used[0]:
                new.append((rect[0], rect[1], used[0], rect[3]))
            if rect[2] > used[2]:
                new.append((used[2], rect[1], rect[2], rect[3]))
            if rect[1] < used[1]:
                new.append((rect[0], rect[1], rect[2], used[1]))
            if rect[3] > used[3]:
                new.append((rect[0], used[3], rect[2], rect[3]))
        free = [
            rect for index, rect in enumerate(new)
            if rect[2] - rect[0] > 0.01 and rect[3] - rect[1] > 0.01
            and not any(index != other and fits(rect, parent) and (rect != parent or other < index) for other, parent in enumerate(new))
        ]
    return out


def _tokens(code):
    tokens = []
    index = 0
    while index < len(code):
        token = code[index:index + 2]
        if token in SEGMENTS:
            tokens.append(token)
            index += 2
        elif code[index] in SEGMENTS:
            tokens.append(code[index])
            index += 1
        else:
            raise ValueError(f"Unknown stroke token in {code!r} at {index}")
    return tokens


def _same(a, b):
    return abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9


def _join_segments(segments):
    remaining = list(segments)
    paths = []
    while remaining:
        start, end = remaining.pop(0)
        path = [start, end]
        changed = True
        while changed:
            changed = False
            for index, (a, b) in enumerate(remaining):
                if _same(path[-1], a):
                    path.append(b)
                elif _same(path[-1], b):
                    path.append(a)
                elif _same(path[0], b):
                    path.insert(0, a)
                elif _same(path[0], a):
                    path.insert(0, b)
                else:
                    continue
                remaining.pop(index)
                changed = True
                break
        # A cycle is split into two open polylines so etch geometry never forms
        # a closed contour, while retaining every intended stroke segment.
        if len(path) > 3 and _same(path[0], path[-1]):
            midpoint = (len(path) - 1) // 2
            paths.extend((path[:midpoint + 1], path[midpoint:]))
        else:
            paths.append(path)
    return paths


def stroke_text(text, height, center, angle=0):
    """Return joined open stroke paths and their unjoined source segment count."""
    label = text.upper()
    unsupported = sorted(set(label) - set(GLYPHS) - {" ", "."})
    if unsupported:
        raise ValueError(f"Unsupported etch characters in {text!r}: {''.join(unsupported)}")
    advance = 0.92 * height
    glyph_width = 0.72 * height
    paths = []
    source_segments = 0
    cursor = 0.0
    for char in label:
        if char == " ":
            cursor += 0.60 * height
            continue
        if char == ".":
            size = 0.10 * height
            paths.append([(cursor + glyph_width / 2 - size, 0.0), (cursor + glyph_width / 2 + size, 0.0)])
            source_segments += 1
            cursor += advance
            continue
        segments = []
        for token in _tokens(GLYPHS[char]):
            a, b = SEGMENTS[token]
            segments.append(((cursor + a[0] * glyph_width, a[1] * height), (cursor + b[0] * glyph_width, b[1] * height)))
        source_segments += len(segments)
        paths.extend(_join_segments(segments))
        cursor += advance
    width = max(cursor - (advance - glyph_width), glyph_width)
    translated = []
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    for path in paths:
        transformed = []
        for x, y in path:
            x -= width / 2
            y -= height / 2
            transformed.append((center[0] + x * cosine - y * sine, center[1] + x * sine + y * cosine))
        translated.append(transformed)
    return translated, source_segments


def place_label(text, profile, nominal_height, edge_clearance):
    safe = profile.buffer(-edge_clearance)
    if safe.is_empty:
        safe = profile
    centers = []
    try:
        point = polylabel(safe, tolerance=0.1)
        centers.append((point.x, point.y))
    except Exception:
        pass
    point = safe.representative_point()
    centers.append((point.x, point.y))
    height = nominal_height
    while height >= 1.0 - 1e-8:
        for center in centers:
            for angle in (0, 90):
                paths, source_segments = stroke_text(text, height, center, angle)
                geometry = MultiLineString(paths)
                if safe.buffer(1e-7).covers(geometry):
                    return paths, source_segments, height, angle
        height = round(height - 0.25, 6)
    raise ValueError(f"Etch label {text!r} cannot fit inside its nested plate profile")


def _outline(modelspace, geometry, layer):
    polygons = [geometry] if isinstance(geometry, Polygon) else list(getattr(geometry, "geoms", []))
    for polygon in polygons:
        if polygon.is_empty:
            continue
        modelspace.add_lwpolyline(list(polygon.exterior.coords)[:-1], close=True, dxfattribs={"layer": layer})
        for ring in polygon.interiors:
            modelspace.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": layer})


def _shop_nest(plates, parameters):
    stock_w, stock_h = map(float, parameters["stock_size_mm"])
    origin_x, origin_y = map(float, parameters["usable_origin_mm"])
    usable_w, usable_h = map(float, parameters["usable_size_mm"])
    gap, margin = float(parameters["gap_mm"]), float(parameters["margin_mm"])
    step = float(parameters["strip_width_step_mm"])
    if step <= 0:
        raise ValueError("strip_width_step_mm must be positive")
    stock = box(0, 0, stock_w, stock_h)
    usable = box(origin_x, origin_y, origin_x + usable_w, origin_y + usable_h)
    if not stock.covers(usable):
        raise ValueError("The configured usable nesting zone must lie inside the physical stock")
    minimum = max(min(profile.bounds[2] - profile.bounds[0], profile.bounds[3] - profile.bounds[1]) + 2 * margin for profile in map(poly, plates))
    width = max(2 * margin, math.ceil(minimum / step) * step)
    nested = None
    while width <= usable_w + 1e-7:
        nested = pack(plates, width, usable_h, gap, margin)
        if nested:
            break
        width += step
    if not nested:
        raise ValueError("No single-sheet solution fits the configured usable zone. Use a documented multi-sheet workflow; do not omit plates or enlarge stock silently.")
    if origin_x or origin_y:
        nested = [(data, affinity.translate(profile, xoff=origin_x, yoff=origin_y), angle, [offset[0] + origin_x, offset[1] + origin_y]) for data, profile, angle, offset in nested]
    return nested, (stock_w, stock_h), (origin_x, origin_y, usable_w, usable_h), width


def _legacy_nest(plates, parameters):
    w0, w1, width_step = parameters["sheet_width_mm"]
    h0, h1, height_step = parameters["sheet_height_mm"]
    for _, width, height in sorted((w * h, w, h) for w in range(w0, w1 + 1, width_step) for h in range(h0, h1 + 1, height_step)):
        nested = pack(plates, width, height, parameters["gap_mm"], parameters["margin_mm"])
        if nested:
            return nested, (float(width), float(height)), (0.0, 0.0, float(width), float(height)), float(width)
    raise ValueError("No single-sheet solution found in the configured legacy sizes. Use a documented multi-sheet workflow; do not omit plates or enlarge stock silently.")


def nest(spec, dxf_path):
    user_parameters = spec.get("nest", {})
    parameters = {**DEFAULTS, **user_parameters}
    plates = spec["plates"]
    if "sheet_width_mm" in user_parameters and "sheet_height_mm" in user_parameters:
        nested, stock_size, usable_data, strip_width = _legacy_nest(plates, parameters)
        legacy = True
    else:
        nested, stock_size, usable_data, strip_width = _shop_nest(plates, parameters)
        legacy = False
    stock_w, stock_h = stock_size
    origin_x, origin_y, usable_w, usable_h = usable_data
    stock = box(0, 0, stock_w, stock_h)
    usable = box(origin_x, origin_y, origin_x + usable_w, origin_y + usable_h)
    used_strip = box(origin_x, origin_y, origin_x + strip_width, origin_y + usable_h)
    clamp_exclusion = stock.difference(usable)

    doc = ezdxf.new("R2010")
    doc.units = 4
    for layer, color in (
        ("CUT", 7), ("ETCH", 3), ("STOCK_REFERENCE", 8), ("USABLE_REFERENCE", 4),
        ("CLAMP_EXCLUSION_REFERENCE", 1), ("NEST_REFERENCE", 6),
    ):
        doc.layers.new(layer, dxfattribs={"color": color})
    modelspace = doc.modelspace()
    _outline(modelspace, stock, "STOCK_REFERENCE")
    _outline(modelspace, usable, "USABLE_REFERENCE")
    if not clamp_exclusion.is_empty:
        _outline(modelspace, clamp_exclusion, "CLAMP_EXCLUSION_REFERENCE")
    _outline(modelspace, used_strip, "NEST_REFERENCE")

    expected = []
    etch_source_segments = 0
    etch_polylines = 0
    labels_inside = True
    for data, profile, angle, offset in nested:
        data["nest_rotation_degrees"], data["nest_offset"] = angle, offset
        for ring in [profile.exterior] + list(profile.interiors):
            coords = list(ring.coords)[:-1]
            modelspace.add_lwpolyline(coords, close=True, dxfattribs={"layer": "CUT"})
            expected.append(Polygon(coords))
        paths, source_segments, label_height, label_angle = place_label(
            data["name"], profile, float(parameters["etch_height_mm"]), float(parameters["etch_edge_clearance_mm"])
        )
        label_geometry = MultiLineString(paths)
        labels_inside = labels_inside and profile.buffer(1e-7).covers(label_geometry)
        for path in paths:
            modelspace.add_lwpolyline(path, close=False, dxfattribs={"layer": "ETCH"})
        data["etch_height_mm"] = label_height
        data["etch_rotation_degrees"] = label_angle
        etch_source_segments += source_segments
        etch_polylines += len(paths)
    doc.saveas(dxf_path)

    back = ezdxf.readfile(dxf_path)
    cuts = list(back.modelspace().query('LWPOLYLINE[layer=="CUT"]'))
    etch = list(back.modelspace().query('LWPOLYLINE[layer=="ETCH"]'))
    text_entities = list(back.modelspace().query('TEXT[layer=="ETCH"]')) + list(back.modelspace().query('MTEXT[layer=="ETCH"]'))
    assert len(cuts) == len(expected) and all(entity.closed for entity in cuts)
    assert len(etch) == etch_polylines and all(not entity.closed for entity in etch) and not text_entities
    error = max(Polygon([(vertex[0], vertex[1]) for vertex in entity.get_points()]).symmetric_difference(profile).area for entity, profile in zip(cuts, expected))
    assert error < 1e-5 and back.units == 4
    inside = all(usable.buffer(1e-4).covers(profile) for _, profile, _, _ in nested)
    distances = [a.distance(b) for index, (_, a, _, _) in enumerate(nested) for _, b, _, _ in nested[index + 1:]]
    min_gap = min(distances) if distances else float("inf")
    plate_area = sum(poly(data).area for data in plates)
    remnant_width = max(0.0, usable_w - strip_width)
    strip_area = strip_width * usable_h
    status = "pass" if inside and labels_inside and min_gap >= float(parameters["gap_mm"]) - 1e-3 else "fail"
    return {
        "plate_count": len(plates),
        "sheet_mm": [stock_w, stock_h],
        "physical_sheet_mm": [stock_w, stock_h],
        "usable_origin_mm": [origin_x, origin_y],
        "usable_size_mm": [usable_w, usable_h],
        "used_strip_mm": [strip_width, usable_h],
        "clamp_exclusion_area_mm2": round(clamp_exclusion.area, 3),
        "largest_rectangular_remnant_mm": [remnant_width, usable_h],
        "thickness_mm": spec["thickness_mm"],
        "area_utilization_percent": round(100 * plate_area / strip_area, 1),
        "strip_utilization_percent": round(100 * plate_area / strip_area, 1),
        "usable_sheet_utilization_percent": round(100 * plate_area / usable.area, 1),
        "physical_sheet_utilization_percent": round(100 * plate_area / stock.area, 1),
        "min_gap_mm": min_gap,
        "gap_limit_mm": float(parameters["gap_mm"]),
        "margin_mm": float(parameters["margin_mm"]),
        "inside_margin": inside,
        "closed_cut_contours": len(cuts),
        "etch_labels": len(plates),
        "etch_polylines": len(etch),
        "etch_source_segments": etch_source_segments,
        "etch_text_entities": len(text_entities),
        "etch_labels_inside_profiles": labels_inside,
        "legacy_stock_search": legacy,
        "dxf_units": "mm",
        "dxf_roundtrip_max_area_error_mm2": error,
        "status": status,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", help="spec whose plates are final (for example, build.py output)")
    parser.add_argument("dxf")
    parser.add_argument("report")
    args = parser.parse_args()
    report = nest(load_spec(args.spec), Path(args.dxf))
    write_json(args.report, report)
    print(report)


if __name__ == "__main__":
    main()
