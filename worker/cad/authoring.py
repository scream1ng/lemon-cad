"""Rebuild dimensioned native profiles without relying on transient face/edge IDs."""
import math
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Circle
from OCP.TopAbs import TopAbs_EDGE, TopAbs_SOLID
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from backend.cad_document import validate_document


def volume(shape):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()


def validate_solid(shape):
    solids = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_SOLID, solids)
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid() or solids.Extent() != 1 or volume(shape) <= 0:
        raise ValueError('The operation did not produce one valid solid.')


def rebuild(document):
    doc = validate_document(document)
    if doc.schema_version >= 2:
        from .profile_authoring import rebuild_profiles
        return rebuild_profiles(doc), doc.model_dump()
    sketch, extrude = doc.features[:2]
    depth = extrude.depth
    if sketch.profile == 'rectangle':
        shape = BRepPrimAPI_MakeBox(sketch.width, sketch.height, depth).Shape()
    else:
        shape = BRepPrimAPI_MakeCylinder(sketch.diameter / 2, depth).Shape()
    holes = []
    for f in doc.features[2:doc.rollback]:
        if f.suppressed:
            continue
        try:
            if f.type == 'hole':
                r = f.diameter / 2
                inside = (r < f.x < sketch.width-r and r < f.y < sketch.height-r) if sketch.profile == 'rectangle' else math.hypot(f.x, f.y)+r < sketch.diameter/2
                if not inside:
                    raise ValueError('The through-hole must stay completely inside the profile.')
                if any(math.hypot(f.x-x, f.y-y) <= r+other_r for x,y,other_r in holes):
                    raise ValueError('Through-holes must not overlap or touch.')
                cutter = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(f.x,f.y,-1),gp_Dir(0,0,1)), r, depth+2).Shape()
                cut = BRepAlgoAPI_Cut(shape, cutter)
                cut.Build()
                if not cut.IsDone():
                    raise ValueError('Unable to cut this hole.')
                shape = cut.Shape()
                holes.append((f.x, f.y, r))
            elif f.type == 'fillet':
                edges = TopTools_IndexedMapOfShape()
                TopExp.MapShapes_s(shape, TopAbs_EDGE, edges)
                fillet = BRepFilletAPI_MakeFillet(shape)
                count = 0
                for i in range(1, edges.Extent()+1):
                    edge = TopoDS.Edge_s(edges.FindKey(i))
                    curve = BRepAdaptor_Curve(edge)
                    if sketch.profile == 'rectangle':
                        a,b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
                        outer = curve.GetType() == GeomAbs_Line and abs(a.X()-b.X()) < 1e-6 and abs(a.Y()-b.Y()) < 1e-6 and abs(abs(a.Z()-b.Z())-depth) < 1e-6 and min(abs(a.X()),abs(a.X()-sketch.width)) < 1e-6 and min(abs(a.Y()),abs(a.Y()-sketch.height)) < 1e-6
                    else:
                        outer = curve.GetType() == GeomAbs_Circle and abs(curve.Circle().Radius()-sketch.diameter/2) < 1e-6
                    if outer:
                        fillet.Add(f.radius, edge)
                        count += 1
                if count != (4 if sketch.profile == 'rectangle' else 2):
                    raise ValueError('Outer edge references changed. Edit or suppress the fillet.')
                fillet.Build()
                if not fillet.IsDone():
                    raise ValueError('Radius cannot be built. Try a smaller radius.')
                shape = fillet.Shape()
            validate_solid(shape)
        except Exception as exc:
            raise ValueError(f'{f.type.title()}: {exc}') from exc
    validate_solid(shape)
    return shape, doc.model_dump()


def write_step(shape, path):
    writer = STEPControl_Writer()
    if writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone or writer.Write(str(path)) != IFSelect_RetDone:
        raise ValueError('Unable to export STEP geometry.')
