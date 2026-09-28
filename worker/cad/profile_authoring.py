"""Datum-plane profiles and ordered, single-body boolean features."""
from itertools import product
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.gp import gp_Pnt, gp_Dir, gp_Vec, gp_Ax2, gp_Circ


AXIS = {'XY': (0, 0, 1), 'XZ': (0, 1, 0), 'YZ': (1, 0, 0)}


def normal(sketch):
    if sketch.plane != 'FACE':
        return AXIS[sketch.plane]
    u,v = sketch.frame.u, sketch.frame.v
    return (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])


def point(sketch, u, v):
    u, v = u + sketch.x, v + sketch.y
    if sketch.plane == 'FACE':
        frame = sketch.frame
        return gp_Pnt(*(frame.origin[k]+u*frame.u[k]+v*frame.v[k] for k in range(3)))
    return gp_Pnt(*({'XY': (u, v, sketch.offset), 'XZ': (u, sketch.offset, v), 'YZ': (sketch.offset, u, v)}[sketch.plane]))


def validate_polygon(points):
    if len(points) < 3:
        raise ValueError('A closed profile needs at least three points.')
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on(a, b, p):
        return abs(cross(a, b, p)) < 1e-8 and all(min(a[k], b[k])-1e-8 <= p[k] <= max(a[k], b[k])+1e-8 for k in (0, 1))
    edges = list(zip(points, points[1:]+points[:1]))
    for i, (a, b) in enumerate(edges):
        if sum((a[k]-b[k])**2 for k in (0, 1)) < 1e-12:
            raise ValueError('Remove duplicate profile points.')
        for j, (c, d) in enumerate(edges[:i]):
            if i-j == 1 or (j == 0 and i == len(edges)-1):
                continue
            if (cross(a,b,c)*cross(a,b,d) < 0 and cross(c,d,a)*cross(c,d,b) < 0) or any((on(a,b,c), on(a,b,d), on(c,d,a), on(c,d,b))):
                raise ValueError('The profile intersects itself.')
    if abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in edges)) < 1e-6:
        raise ValueError('The profile has no area.')


def profile_face(sketch):
    if not sketch.closed:
        raise ValueError('Close the profile before previewing.')
    if sketch.profile == 'circle':
        circle = gp_Circ(gp_Ax2(point(sketch, 0, 0), gp_Dir(*normal(sketch))), sketch.diameter/2)
        wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
    else:
        points = sketch.points if sketch.profile == 'polygon' else [(0,0), (sketch.width,0), (sketch.width,sketch.height), (0,sketch.height)]
        validate_polygon(points)
        polygon = BRepBuilderAPI_MakePolygon()
        for u,v in points:
            polygon.Add(point(sketch, u, v))
        polygon.Close()
        if not polygon.IsDone():
            raise ValueError('Unable to close this profile.')
        wire = polygon.Wire()
    face = BRepBuilderAPI_MakeFace(wire, True)
    if not face.IsDone() or not BRepCheck_Analyzer(face.Face()).IsValid():
        raise ValueError('The profile must be a simple, closed planar region.')
    return face.Face()


def rebuild_profiles(doc):
    from .authoring import rebuild, validate_solid, volume
    shape = None
    sketches = {}
    legacy_end = max((i for i,f in enumerate(doc.features[:doc.rollback]) if f.type in ('hole','fillet')), default=-1)
    if legacy_end >= 0:
        prefix = []
        for f in doc.features[:legacy_end+1]:
            values = f.model_dump()
            if f.type == 'sketch':
                values = {k:v for k,v in values.items() if k in ('id','type','suppressed','profile','width','height','diameter')}
            elif f.type == 'extrude':
                values = {k:v for k,v in values.items() if k in ('id','type','suppressed','depth')}
            prefix.append(values)
        shape, _ = rebuild({'schema_version':1,'features':prefix,'rollback':len(prefix)})
    for i,f in enumerate(doc.features[:doc.rollback]):
        if f.suppressed:
            continue
        try:
            if f.type == 'sketch':
                sketches[f.id] = (f, profile_face(f))
                continue
            if i <= legacy_end:
                continue
            if f.sketch_id not in sketches:
                raise ValueError('The source sketch is suppressed or unavailable. Restore it or suppress this extrusion.')
            sketch, face = sketches[f.sketch_id]
            axis = normal(sketch)
            depth = f.depth
            if f.extent == 'through_all':
                bounds = Bnd_Box(); BRepBndLib.Add_s(shape, bounds)
                values = bounds.Get()
                origin = point(sketch, 0, 0).Coord()
                corners = product(*[(values[k],values[k+3]) for k in range(3)])
                depth = max(sum((corner[k]-origin[k])*axis[k]*f.direction for k in range(3)) for corner in corners)+1
                if depth <= 0:
                    raise ValueError('The cut points away from the body. Reverse its direction.')
            tool = BRepPrimAPI_MakePrism(face, gp_Vec(*(v*depth*f.direction for v in axis))).Shape()
            validate_solid(tool)
            if shape is None:
                shape = tool
            else:
                before = volume(shape)
                boolean = (BRepAlgoAPI_Fuse if f.operation == 'add' else BRepAlgoAPI_Cut)(shape, tool)
                boolean.Build()
                if not boolean.IsDone():
                    raise ValueError('Unable to build this extrusion.')
                boolean.SimplifyResult()
                result = boolean.Shape()
                try:
                    validate_solid(result)
                except ValueError as exc:
                    raise ValueError('The result must be one solid. Join additions to the body; cuts must not split or remove it entirely.') from exc
                delta = volume(result)-before
                if (f.operation == 'add' and delta <= 1e-7) or (f.operation == 'cut' and delta >= -1e-7):
                    raise ValueError('This extrusion does not change the body. Check the profile, depth and direction.')
                shape = result
        except Exception as exc:
            raise ValueError(f'{"Sketch" if f.type == "sketch" else "Extruded cut" if f.operation == "cut" else "Extrusion"} at history position {i+1}: {exc}') from exc
    validate_solid(shape)
    return shape
