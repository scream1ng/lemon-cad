#!/usr/bin/env python3
"""Survey placed STEP solids; emit geometry evidence, never an inferred fixture design."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Line, GeomAbs_Circle
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TColStd import TColStd_SequenceOfAsciiString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_WIRE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.gp import gp_Trsf
from fixture_common import validate_rigid


def xyz(p):
    return [float(p.X()), float(p.Y()), float(p.Z())]


def bbox(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    values = list(box.Get())
    return {"min": values[:3], "max": values[3:],
            "size": [values[i + 3] - values[i] for i in range(3)]}


def shapes_of(shape, kind):
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        yield explorer.Current()
        explorer.Next()


def label_name(label):
    attr = TDataStd_Name()
    return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), attr) else "unnamed"


def read_occurrences(path):
    """Return every leaf occurrence with assembly placements, including repeated names."""
    doc = TDocStd_Document(TCollection_ExtendedString("survey"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError(f"Cannot read STEP: {path}")
    length, angle, solid_angle = (TColStd_SequenceOfAsciiString() for _ in range(3))
    reader.Reader().FileUnits(length, angle, solid_angle)
    source_units = [length.Value(i).ToCString() for i in range(1, length.Length() + 1)]
    # OCCT expresses this setting in millimetres: 1.0 means output coordinates in mm.
    reader.Reader().SetSystemLengthUnit(1.0)
    if not reader.Transfer(doc):
        raise ValueError("STEP transfer failed")
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    leaves = []

    def visit(label, parent, path, indices, active):
        definition = label
        if st.IsReference_s(label):
            definition = TDF_Label()
            if not st.GetReferredShape_s(label, definition):
                raise ValueError("Unresolved STEP occurrence")
        # Index path disambiguates otherwise identical names and shared definitions.
        path = path + [label_name(label)]
        if st.IsAssembly_s(definition):
            if any(definition.IsEqual(ancestor) for ancestor in active):
                raise ValueError("Cyclic STEP assembly reference")
            location = parent.Multiplied(st.GetLocation_s(label))
            children = TDF_LabelSequence()
            st.GetComponents_s(definition, children)
            for j in range(1, children.Length() + 1):
                visit(children.Value(j), location, path, indices + [j], active + [definition])
        else:
            # GetShape(component) includes its own location; only add its ancestors.
            shape = st.GetShape_s(label)
            if shape.IsNull():
                raise ValueError(f"Null shape at {path}")
            leaves.append((shape.Moved(parent), {"occurrence_path": path,
                          "occurrence_index_path": indices,
                          "product_name": label_name(definition)}))

    for i in range(1, roots.Length() + 1):
        visit(roots.Value(i), TopLoc_Location(), [], [i], [])
    return leaves, source_units


def rigid_transform(value=None):
    """Validated 4x4 plus its OCP placement."""
    matrix = validate_rigid(value)
    trsf = gp_Trsf()
    trsf.SetValues(*matrix[:3].ravel().tolist())
    return matrix.tolist(), TopLoc_Location(trsf)


def boundary(face):
    """Exact line/circle descriptors plus explicitly sampled general curve evidence."""
    outer = BRepTools.OuterWire_s(face)
    wires = []
    for raw_wire in shapes_of(face, TopAbs_WIRE):
        wire = TopoDS.Wire_s(raw_wire)
        explorer = BRepTools_WireExplorer(wire, face)
        edges = []
        while explorer.More():
            edge = explorer.Current()
            curve = BRepAdaptor_Curve(edge)
            first, last = curve.FirstParameter(), curve.LastParameter()
            reverse = edge.Orientation() == TopAbs_REVERSED
            a, b = (last, first) if reverse else (first, last)
            item = {"type": str(curve.GetType()).split(".")[-1].replace("GeomAbs_", ""),
                    "start_mm": xyz(curve.Value(a)), "end_mm": xyz(curve.Value(b)),
                    "parameter_range": [a, b]}
            props = GProp_GProps()
            BRepGProp.LinearProperties_s(edge, props)
            item["length_mm"] = props.Mass()
            if curve.GetType() == GeomAbs_Circle:
                circle = curve.Circle()
                item.update(center_mm=xyz(circle.Location()), axis=xyz(circle.Axis().Direction()),
                            radius_mm=circle.Radius())
            elif curve.GetType() != GeomAbs_Line:
                item["sample_points_mm"] = [xyz(curve.Value(t)) for t in np.linspace(a, b, 17)]
                item["sample_is_exact_boundary"] = False
            edges.append(item)
            explorer.Next()
        wires.append({"is_outer": wire.IsSame(outer), "edges": edges})
    return wires


def describe_body(shape, name, origin):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    body = {"name": name, **origin, "volume_mm3": props.Mass(),
            "center_of_mass_mm": xyz(props.CentreOfMass()), "bbox_mm": bbox(shape),
            "kernel_valid": bool(BRepCheck_Analyzer(shape).IsValid()), "faces": []}
    candidates = []
    for i, raw_face in enumerate(shapes_of(shape, TopAbs_FACE), 1):
        face = TopoDS.Face_s(raw_face)
        surface = BRepAdaptor_Surface(face, True)
        kind = surface.GetType()
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        face_id = f"{name}:Face_{i:04d}"
        row = {"id": face_id, "type": str(kind).split(".")[-1].replace("GeomAbs_", ""),
               "area_mm2": props.Mass(), "center_mm": xyz(props.CentreOfMass()),
               "orientation": "reversed" if face.Orientation() == TopAbs_REVERSED else "forward"}
        if kind == GeomAbs_Plane:
            normal = np.array(xyz(surface.Plane().Axis().Direction()))
            if face.Orientation() == TopAbs_REVERSED:
                normal *= -1
            row.update(normal=normal.tolist(), plane_origin_mm=xyz(surface.Plane().Location()),
                       boundaries=boundary(face))
            candidates.append({"kind": "flange_or_datum_face", "face": face_id,
                               "status": "unverified", "basis": "planar surface only"})
        elif kind == GeomAbs_Cylinder:
            cylinder = surface.Cylinder()
            row.update(axis_origin_mm=xyz(cylinder.Location()), axis=xyz(cylinder.Axis().Direction()),
                       radius_mm=cylinder.Radius(),
                       uv_bounds=list(BRepTools.UVBounds_s(face)), boundaries=boundary(face))
            candidates.append({"kind": "hole_or_bend_or_outer_cylinder", "face": face_id,
                               "status": "unverified", "basis": "cylindrical surface only"})
        else:
            from flange_features import PLANAR_TOL_MM, planar_face
            fit = planar_face(face)  # None for cones, spheres, tori and non-flat freeform
            if fit:
                row.update(normal=fit[1].tolist(), plane_origin_mm=fit[0].tolist(), planarity_deviation_mm=fit[2])
                candidates.append({"kind": "flange_or_datum_face", "face": face_id, "status": "unverified",
                                   "basis": f"{row['type']} plane-fitted within {PLANAR_TOL_MM} mm"})
        body["faces"].append(row)
    body["feature_candidates"] = candidates
    return body


def write_placed_step(path, shapes):
    doc = TDocStd_Document(TCollection_ExtendedString("placed"))
    XCAFDoc_DocumentTool.SetLengthUnit_s(doc, 0.001)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    # Independent copied TShapes ensure coincident instances retain distinct names.
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    for name, shape in shapes:
        label = st.AddShape(BRepBuilderAPI_Copy(shape).Shape(), False)
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
        if st.IsReference_s(label):
            definition = TDF_Label()
            st.GetReferredShape_s(label, definition)
            TDataStd_Name.Set_s(definition, TCollection_ExtendedString(name))
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    previous_unit = Interface_Static.CVal_s("write.step.unit")
    try:
        if not Interface_Static.SetCVal_s("write.step.unit", "MM"):
            raise ValueError("Cannot set STEP output units to mm")
        if not writer.Transfer(doc, STEPControl_AsIs) or writer.Write(str(path)) != IFSelect_RetDone:
            raise ValueError("Cannot export placed STEP")
    finally:
        Interface_Static.SetCVal_s("write.step.unit", previous_unit)


def survey(source, out, transform=None):
    source, out = Path(source).resolve(), Path(out).resolve()
    matrix, placement = rigid_transform(transform)
    if source == out / "placed.step":
        raise ValueError("Output placed.step must not overwrite the source STEP")
    occurrences, source_units = read_occurrences(source)
    bodies, placed, warnings = [], [], []
    for leaf, origin in occurrences:
        solids = list(shapes_of(leaf, TopAbs_SOLID))
        if not solids:
            warnings.append({"kind": "non_solid_occurrence_skipped", **origin})
        for solid_index, solid in enumerate(solids, 1):
            name = f"Part_{len(bodies) + 1:04d}"
            shape = solid.Moved(placement)
            body = describe_body(shape, name, {**origin, "solid_index": solid_index})
            if not body["kernel_valid"] or body["volume_mm3"] <= 0:
                raise ValueError(f"Invalid or non-positive solid: {name} at {origin['occurrence_path']}")
            bodies.append(body)
            placed.append((name, shape))
    if not bodies:
        raise ValueError("STEP contains no valid solids; surface-only models need review")
    result = {"schema_version": "step-survey-1", "source": {"path": str(source),
              "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "length_units_detected": source_units or ["unknown"]},
              "units": "mm", "unit_normalization": "OCCT STEP transfer system length unit 1.0 mm",
              "source_to_fixture": matrix,
              "transform_convention": "fixture_mm = source_to_fixture @ [source_mm.x, source_mm.y, source_mm.z, 1]",
              "placed_step": "placed.step", "body_count": len(bodies), "bodies": bodies,
              "warnings": warnings,
              "classification_status": "geometric evidence only; candidates require designer review",
              "fixture_design_status": "not_generated"}
    out.mkdir(parents=True, exist_ok=True)
    write_placed_step(out / "placed.step", placed)
    (out / "survey.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_step")
    parser.add_argument("out")
    parser.add_argument("--transform", type=Path, help="JSON 4x4 rigid matrix, or {source_to_fixture: matrix}")
    args = parser.parse_args()
    transform = json.loads(args.transform.read_text()) if args.transform else None
    result = survey(args.input_step, args.out, transform)
    print(json.dumps({"body_count": result["body_count"], "survey": str(Path(args.out) / "survey.json"),
                      "placed_step": str(Path(args.out) / "placed.step"), "warnings": result["warnings"]}))


if __name__ == "__main__":
    main()
