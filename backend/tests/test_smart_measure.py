import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir, gp_Circ
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


def test_edge_length_and_invalid_reference():
    assert smart_measure(plate_references(), refs(2))['value_mm'] == pytest.approx(80)
    with pytest.raises(ValueError, match='revision'):
        smart_measure(plate_references(), refs(99))


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
