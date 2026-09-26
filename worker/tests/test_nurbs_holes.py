"""A STEP exporter may encode an exact cylindrical hole as a NURBS surface."""
import pytest

pytest.importorskip("OCP")

from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

from cad.icl import faced_mesh, indexed_edges
from cad.smart_measure import feature, smart_measure


def test_nurbs_cylinder_is_a_selectable_diameter():
    shape = BRepBuilderAPI_NurbsConvert(
        BRepPrimAPI_MakeCylinder(4.05, 2.0).Shape()
    ).Shape()
    faces = faced_mesh(shape)["faces"]
    cylinders = [face for face in faces if face["type"] == "cylinder"]
    assert len(cylinders) == 1
    ref = {"kind": "face", "id": cylinders[0]["id"]}
    assert feature(shape, ref)["type"] == "circle"
    dimension = smart_measure(shape, [ref])
    assert dimension["type"] == "dia"
    assert dimension["value_mm"] == pytest.approx(8.1, abs=0.001)


def test_nurbs_hole_rim_and_straight_edge_are_selectable():
    shape = BRepBuilderAPI_NurbsConvert(
        BRepPrimAPI_MakeCylinder(4.05, 2.0).Shape()
    ).Shape()
    edges = indexed_edges(shape)
    assert any(edge["type"] == "circle" for edge in edges)
    assert any(edge["type"] == "line" for edge in edges)
    for kind in ("circle", "line"):
        edge = next(edge for edge in edges if edge["type"] == kind)
        assert feature(shape, {"kind": "edge", "id": edge["id"]})["type"] == kind
