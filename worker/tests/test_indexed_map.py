"""The Python stand-in for OCC's indexed maps must number sub-shapes exactly
like the real thing.

Entity IDs are 1-based positions in these maps: the frontend picks a face/edge
by ID and posts it back to /measure, so a stand-in that numbered differently
would silently move every balloon on a part that happened to be meshed by the
other code path. This test runs both paths over the same shape and compares.

Skipped where OCP isn't installed (the main Flask app's CI), runs in the
cad-service image where it is.
"""
import pytest

OCP = pytest.importorskip("OCP", reason="OCP (OpenCASCADE bindings) not installed")

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut  # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder  # noqa: E402
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE  # noqa: E402
from OCP.TopExp import TopExp  # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt  # noqa: E402

from cad.icl import (  # noqa: E402
    _PyAncestorMap,
    _PyIndexedMap,
    _occ_class,
    _shape_key,
    _static,
)


@pytest.fixture(scope="module")
def part():
    """A plate with three holes — enough faces, edges and shared edges to make
    ordering and de-duplication mean something."""
    shape = BRepPrimAPI_MakeBox(60.0, 40.0, 10.0).Shape()
    for x, y in ((15.0, 12.0), (45.0, 12.0), (30.0, 30.0)):
        cyl = BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(x, y, -5.0), gp_Dir(0.0, 0.0, 1.0)), 4.0, 20.0
        ).Shape()
        shape = BRepAlgoAPI_Cut(shape, cyl).Shape()
    return shape


def _occ_map(shape, typ):
    cls = _occ_class("TopTools", "TopTools_IndexedMapOfShape")
    if cls is None:
        pytest.skip("this OCP build has no TopTools_IndexedMapOfShape to compare against")
    m = cls()
    _static(TopExp, "MapShapes")(shape, typ, m)
    return m


def test_shape_key_is_content_based():
    """The probe must reject identity hashing. OCP 7.7's hash() is per-wrapper
    (useless for de-duplication) while 7.9 dropped HashCode() — if the probe
    ever picks the wrong one, the maps below silently gain duplicate entries."""
    key = _shape_key()
    if key is None:
        pytest.skip("no usable shape hash on this build (stand-in falls back to O(n^2))")
    box = BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape()
    from cad.icl import _explore

    first, second = _explore(box, TopAbs_FACE), _explore(box, TopAbs_FACE)
    assert [key(s) for s in first] == [key(s) for s in second]
    assert len({key(s) for s in first}) == len(first)


@pytest.mark.parametrize("typ", [TopAbs_FACE, TopAbs_EDGE])
def test_stand_in_matches_occ_map(part, typ):
    occ, py = _occ_map(part, typ), _PyIndexedMap.of(part, typ)
    assert py.Extent() == occ.Extent()
    for i in range(1, occ.Extent() + 1):
        assert occ.FindKey(i).IsSame(py.FindKey(i)), f"entity {i} differs"
        assert py.FindIndex(occ.FindKey(i)) == i


def test_stand_in_rejects_out_of_range(part):
    py = _PyIndexedMap.of(part, TopAbs_FACE)
    with pytest.raises(ValueError):
        py.FindKey(0)
    with pytest.raises(ValueError):
        py.FindKey(py.Extent() + 1)


def test_ancestor_stand_in_matches_occ(part):
    cls = _occ_class("TopTools", "TopTools_IndexedDataMapOfShapeListOfShape")
    if cls is None:
        pytest.skip("this OCP build has no ancestor map to compare against")
    occ = cls()
    _static(TopExp, "MapShapesAndAncestors")(part, TopAbs_EDGE, TopAbs_FACE, occ)
    py = _PyAncestorMap.of(part, TopAbs_EDGE, TopAbs_FACE)

    edges = _occ_map(part, TopAbs_EDGE)
    for i in range(1, edges.Extent() + 1):
        edge = edges.FindKey(i)
        want = list(occ.FindFromIndex(occ.FindIndex(edge)))
        got = list(py.FindFromIndex(py.FindIndex(edge)))
        assert len(got) == len(want)
        assert all(any(w.IsSame(g) for g in got) for w in want)
