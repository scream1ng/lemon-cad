import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir, gp_Circ, gp_Pln
from cad.icl import _edge_map
from cad.smart_measure import smart_measure


def plate_references():
    shape = TopoDS_Compound(); builder = BRep_Builder(); builder.MakeCompound(shape)
    for edge in [BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(20, 20, 0), gp_Dir(0, 0, 1)), 6)).Edge(),
                 BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(0, 80, 0)).Edge(),
                 BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(60, 20, 0), gp_Dir(0, 0, 1)), 6)).Edge()]:
        builder.Add(shape, edge)
    return shape


def refs(*ids):
    return [{'kind': 'edge', 'id': i} for i in ids]


def test_hole_size_location_and_clearance_are_distinct():
    shape = plate_references()
    assert smart_measure(shape, refs(1))['value_mm'] == pytest.approx(12)
    for pair in [(1, 2), (2, 1)]:
        assert smart_measure(shape, refs(*pair))['value_mm'] == pytest.approx(20)
        assert smart_measure(shape, refs(*pair), 'clearance')['value_mm'] == pytest.approx(14)
    assert smart_measure(shape, refs(1, 3))['value_mm'] == pytest.approx(40)
    assert smart_measure(shape, refs(1, 3), 'clearance')['value_mm'] == pytest.approx(28)


def test_hole_to_short_edge_ends_on_edge_endpoint():
    shape = TopoDS_Compound(); builder = BRep_Builder(); builder.MakeCompound(shape)
    builder.Add(shape, BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(20, 20, 0), gp_Dir(0, 0, 1)), 6)).Edge())
    builder.Add(shape, BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(0, 10, 0)).Edge())
    result = smart_measure(shape, refs(1, 2), 'clearance')
    assert result['p2'] == pytest.approx([0, 10, 0])
    assert result['value_mm'] == pytest.approx((20**2+10**2)**.5-6)


def test_edge_length_and_invalid_reference():
    assert smart_measure(plate_references(), refs(2))['value_mm'] == pytest.approx(80)
    with pytest.raises(ValueError, match='revision'):
        smart_measure(plate_references(), refs(99))


def test_parallel_plane_to_edge_uses_perpendicular_gap():
    shape = TopoDS_Compound(); builder = BRep_Builder(); builder.MakeCompound(shape)
    builder.Add(shape, BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0, 20, 0, 20).Face())
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 10), gp_Pnt(20, 0, 10)).Edge()
    builder.Add(shape, edge)
    edge_id = next(i for i in range(1, _edge_map(shape).Extent()+1) if _edge_map(shape).FindKey(i).IsSame(edge))
    for pair in [({'kind':'face','id':1}, {'kind':'edge','id':edge_id}),
                 ({'kind':'edge','id':edge_id}, {'kind':'face','id':1})]:
        result = smart_measure(shape, list(pair))
        assert result['value_mm'] == pytest.approx(10)
        assert result['method'] == 'plane-to-edge'
        assert result['p1'][:2] == pytest.approx(result['p2'][:2])


def test_tilted_edge_has_no_single_perpendicular_gap():
    shape = TopoDS_Compound(); builder = BRep_Builder(); builder.MakeCompound(shape)
    builder.Add(shape, BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0, 20, 0, 20).Face())
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 10), gp_Pnt(20, 0, 20)).Edge()
    builder.Add(shape, edge)
    edge_id = next(i for i in range(1, _edge_map(shape).Extent()+1) if _edge_map(shape).FindKey(i).IsSame(edge))
    with pytest.raises(ValueError, match='parallel'):
        smart_measure(shape, [{'kind':'face','id':1}, {'kind':'edge','id':edge_id}])


def test_hole_to_base_surface_measures_from_hole_wall():
    from cad.loader import load_step
    shape = load_step('frontend/public/sample-bracket.step')
    hole, base = {'kind':'face','id':15}, {'kind':'face','id':10}
    for pair in [(hole, base), (base, hole)]:
        centre = smart_measure(shape, list(pair), 'centre')
        wall = smart_measure(shape, list(pair), 'clearance')
        assert centre['value_mm'] == pytest.approx(54)
        assert wall['value_mm'] == pytest.approx(48)
        assert wall['method'] == 'hole-wall-to-plane'
        assert wall['p1'][2] == pytest.approx(54)
        assert wall['p2'][2] == pytest.approx(6)
        assert wall['alternatives'] == ['centre', 'clearance']


def test_parallel_sample_surfaces_keep_perpendicular_distance():
    from cad.loader import load_step
    shape = load_step('frontend/public/sample-bracket.step')
    result = smart_measure(shape, [{'kind':'face','id':7}, {'kind':'face','id':9}])
    assert result['method'] == 'parallel-plane'
    assert result['value_mm'] == pytest.approx(6)


def test_import_exports_analytical_measurement_descriptors(tmp_path):
    from pathlib import Path
    import json
    from worker.runner import execute
    execute('import', {}, Path('frontend/public/sample-bracket.step'), tmp_path)
    data = json.loads((tmp_path/'mesh.json').read_text())
    holes = [f for f in data['measure_features'].values() if f['type'] == 'circle' and f.get('axial')]
    assert holes
    for hole in holes:
        assert hole['single']['value_mm'] == pytest.approx(hole['radius']*2)
        assert len(hole['axis']) == len(hole['center']) == 3
    assert any(int(key)<0 and f['type']=='line' for key,f in data['measure_features'].items())


def test_cached_import_descriptors_match_direct_measurements():
    from cad.loader import load_step
    from cad.icl import _cylinder_faces, _face_map
    from cad.smart_measure import feature
    shape = load_step('frontend/public/sample-bracket.step')
    cylinders = _cylinder_faces(shape)
    refs = ([{'kind':'face','id':i} for i in range(1, _face_map(shape).Extent()+1) if feature(shape, {'kind':'face','id':i})['type']=='circle'][:1]
            + [{'kind':'edge','id':i} for i in range(1, _edge_map(shape).Extent()+1) if feature(shape, {'kind':'edge','id':i})['type']=='line'][:1])
    assert len(refs) == 2
    for ref in refs:
        descriptor = feature(shape, ref)
        assert smart_measure(shape, [ref], known_features=[descriptor], cylinder_faces=cylinders) == smart_measure(shape, [ref])
