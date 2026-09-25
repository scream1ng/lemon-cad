#!/usr/bin/env python3
"""Extrude plate records to named solids and write one assembly STEP.

The assembly contains every plate, plus workpiece (Part_*) and hardware reference (REF_*) shapes
copied from spec.workpiece.placed_step when given. Requires cadquery-ocp 7.8.x.
"""
from __future__ import annotations

import argparse

import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Pnt, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Message import Message, Message_Gravity
from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from shapely.geometry.polygon import orient

from fixture_common import load_spec, poly, spec_path

for _p in Message.DefaultMessenger_s().Printers():  # silence STEP transfer statistics
    _p.SetTraceLevel(Message_Gravity.Message_Fail)


def _wire(points, world):
    m = BRepBuilderAPI_MakePolygon()
    for p in points:
        m.Add(gp_Pnt(*world(p)))
    m.Close()
    return m.Wire()


def solid(d, T):
    o, U, V, W = (np.array(d[k], float) for k in ("origin", "u", "v", "w"))
    world = lambda q: o + U * q[0] + V * q[1] - W * T / 2
    p = orient(poly(d), sign=1)
    face = BRepBuilderAPI_MakeFace(_wire(list(p.exterior.coords)[:-1], world))
    for h in p.interiors:
        face.Add(_wire(list(h.coords)[:-1], world))
    sh = BRepPrimAPI_MakePrism(face.Face(), gp_Vec(*(W * T))).Shape()
    assert BRepCheck_Analyzer(sh).IsValid(), d["name"]
    return sh


def read_step(path):
    """Named free shapes of a STEP file, in file order."""
    doc = TDocStd_Document(TCollection_ExtendedString("in"))
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    assert r.ReadFile(str(path)) == IFSelect_RetDone, path
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labs = TDF_LabelSequence()
    st.GetFreeShapes(labs)
    out = {}
    def label_name(label):
        n = TDataStd_Name()
        return n.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), n) else "unnamed"
    # Preserve assembly placements; duplicate labels must never overwrite bodies silently.
    from OCP.TDF import TDF_Label
    from OCP.TopLoc import TopLoc_Location
    def visit(label, parent, path):
        name = label_name(label)
        definition = label
        loc = parent.Multiplied(st.GetLocation_s(label))
        if st.IsReference_s(label):
            definition = TDF_Label()
            if not st.GetReferredShape_s(label, definition):
                raise ValueError("unresolved STEP component reference")
            if name == "unnamed":
                name = label_name(definition)
        if st.IsAssembly_s(definition):
            children = TDF_LabelSequence()
            st.GetComponents_s(definition, children)
            for j in range(1, children.Length()+1):
                visit(children.Value(j), loc, path + [name])
        else:
            shape = st.GetShape_s(definition)
            # loc already includes this occurrence's location.
            shape = shape.Located(loc)
            key = name
            if key in out:
                key = "/".join(path + [name])
            if key in out:
                raise ValueError(f"duplicate STEP occurrence name: {key}; assign stable unique names")
            out[key] = shape
    for i in range(1, labs.Length()+1):
        visit(labs.Value(i), TopLoc_Location(), [])
    return out


def write_step(path, shapes):
    doc = TDocStd_Document(TCollection_ExtendedString("out"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for name, sh in shapes.items():
        TDataStd_Name.Set_s(st.AddShape(sh, False), TCollection_ExtendedString(name))
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    assert w.Write(str(path)) == IFSelect_RetDone


def export(spec, path):
    shapes = {d["name"]: solid(d, spec["thickness_mm"]) for d in spec["plates"]}
    wp = spec.get("workpiece", {})
    if wp.get("placed_step"):
        prefix = wp.get("reference_prefix", "REF_")
        for name, sh in read_step(spec_path(spec, wp["placed_step"])).items():
            if name.split("/")[-1].startswith(("Part_", prefix)):
                if name in shapes:
                    raise ValueError(f"source shape conflicts with fixture plate name: {name}")
                shapes[name] = sh
    from hardware_geometry import placed_shapes
    hardware,_ = placed_shapes(spec)
    # Do not silently deliver a block placeholder alongside the purchased assembly.
    bad=[n for n in shapes if 'schematic' in n.lower() and spec.get('clamps')]
    if bad:raise ValueError('Remove schematic clamp references from placed_step; bundled hardware is inserted automatically: '+', '.join(bad))
    if set(hardware)&set(shapes):raise ValueError('duplicate purchased hardware identity')
    shapes.update(hardware)
    write_step(path, shapes)
    return {"file": str(path), "plates": len(spec["plates"]), "shapes": len(shapes)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec")
    ap.add_argument("step")
    a = ap.parse_args()
    print(export(load_spec(a.spec), a.step))


if __name__ == "__main__":
    main()
