import math
import pytest
from pydantic import ValidationError
from worker.cad.authoring import rebuild, volume, write_step
from worker.cad.loader import load_step


def document(profile='rectangle'):
    return {'schema_version': 1, 'kind': 'part', 'units': 'mm', 'rollback': 2, 'features': [
        {'id': 'sketch', 'type': 'sketch', 'profile': profile, 'width': 80, 'height': 50, 'diameter': 50},
        {'id': 'extrude', 'type': 'extrude', 'depth': 10}]}


def add(doc, feature):
    doc['features'].append(feature)
    doc['rollback'] = len(doc['features'])
    return doc


@pytest.mark.parametrize('profile', ['rectangle', 'circle'])
def test_exact_profile_hole_fillet_rebuild_export(profile, tmp_path):
    doc = document(profile)
    before, _ = rebuild(doc)
    base = 80*50*10 if profile == 'rectangle' else math.pi*25**2*10
    assert volume(before) == pytest.approx(base)
    hole = {'id': 'hole', 'type': 'hole', 'diameter': 12, 'x': 40 if profile == 'rectangle' else 0, 'y': 25 if profile == 'rectangle' else 0}
    add(doc, hole)
    drilled, _ = rebuild(doc)
    assert volume(drilled) == pytest.approx(base-math.pi*6**2*10)
    add(doc, {'id': 'fillet', 'type': 'fillet', 'radius': 2})
    rounded, normalized = rebuild(doc)
    assert 0 < volume(rounded) < volume(drilled)
    path = tmp_path / 'part.step'
    write_step(rounded, path)
    assert volume(load_step(str(path))) == pytest.approx(volume(rounded), rel=1e-7)
    doc['features'][1]['depth'] = 16
    changed, _ = rebuild(doc)
    assert volume(changed) > volume(rounded)
    assert normalized['features'][1]['depth'] == 10  # earlier document untouched
    doc['rollback'] = 2
    rolled, _ = rebuild(doc)
    assert volume(rolled) == pytest.approx(base*1.6)
    doc['rollback'] = 4
    doc['features'][2]['suppressed'] = True
    suppressed, _ = rebuild(doc)
    assert volume(suppressed) > volume(changed)


@pytest.mark.parametrize('feature', [
    {'id': 'bad', 'type': 'hole', 'diameter': 20, 'x': 0, 'y': 0},
    {'id': 'bad', 'type': 'fillet', 'radius': 100},
])
def test_invalid_features_preserve_input(feature):
    doc = document()
    before, _ = rebuild(doc)
    with pytest.raises(ValueError):
        rebuild(add(doc, feature))
    assert volume(before) == pytest.approx(40000)


def test_overlapping_holes_and_invalid_contract():
    doc = add(document(), {'id': 'h1', 'type': 'hole', 'diameter': 10, 'x': 30, 'y': 25})
    with pytest.raises(ValueError, match='overlap'):
        rebuild(add(doc, {'id': 'h2', 'type': 'hole', 'diameter': 10, 'x': 35, 'y': 25}))
    for depth in [0, -1, float('nan'), float('inf'), 5000]:
        doc = document()
        doc['features'][1]['depth'] = depth
        with pytest.raises(ValidationError):
            rebuild(doc)
