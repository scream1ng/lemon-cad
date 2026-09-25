#!/usr/bin/env python3
"""Explicit, single-solid printed bodies and verified STL exports (millimetres)."""
from __future__ import annotations

from collections import Counter, defaultdict
import math
from pathlib import Path
import re
import struct

import numpy as np
from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeVertex
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.StlAPI import StlAPI_Writer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec


def _number(value, name, positive=False, nonnegative=False):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a finite number') from exc
    if not math.isfinite(value) or (positive and value <= 0) or (nonnegative and value < 0):
        raise ValueError(f'{name} has invalid value {value}')
    return value


def _vector(value, name, unit=False):
    if not isinstance(value, (list, tuple, np.ndarray)) or len(value) != 3:
        raise ValueError(f'{name} must contain three finite numbers')
    result = np.array([_number(v, name) for v in value])
    if unit and abs(np.linalg.norm(result) - 1.0) > 1e-6:
        raise ValueError(f'{name} must be a unit vector')
    if unit:
        result /= np.linalg.norm(result)
    return result


def _entities(shape, kind):
    ex = TopExp_Explorer(shape, kind)
    out = []
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    return out


def _bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return list(box.Get())


def _volume(shape):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def _checked(shape, name):
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():
        raise ValueError(f'{name}: invalid CAD shape')
    solids = _entities(shape, TopAbs_SOLID)
    if len(solids) != 1:
        raise ValueError(f'{name}: require exactly one connected solid, found {len(solids)}')
    solid = solids[0]
    for kind in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
        if len(_entities(shape, kind)) != len(_entities(solid, kind)):
            raise ValueError(f'{name}: loose geometry outside solid')
    if not math.isfinite(_volume(solid)) or not np.isfinite(_bounds(solid)).all() or _volume(solid) <= 1e-9:
        raise ValueError(f'{name}: solid must have positive volume')
    return solid


def _feature(data):
    if not isinstance(data, dict):
        raise ValueError('feature must be an object')
    kind = data.get('type', 'box')
    if kind == 'box':
        origin = _vector(data.get('origin'), 'box.origin')
        size = _vector(data.get('size'), 'box.size')
        if np.any(size <= 0):
            raise ValueError('box.size must be positive')
        return BRepPrimAPI_MakeBox(gp_Pnt(*origin), *size).Shape()
    if kind == 'cylinder':
        origin = _vector(data.get('origin'), 'cylinder.origin')
        axis = _vector(data.get('axis'), 'cylinder.axis', unit=True)
        radius = _number(data.get('radius_mm'), 'cylinder.radius_mm', positive=True)
        depth = _number(data.get('depth_mm'), 'cylinder.depth_mm', positive=True)
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*origin), gp_Dir(*axis)), radius, depth).Shape()
    if kind == 'offset_pocket':
        point = _vector(data.get('point'), 'offset_pocket.point')
        normal = _vector(data.get('normal'), 'offset_pocket.normal', unit=True)
        u = _vector(data.get('u'), 'offset_pocket.u', unit=True)
        if abs(np.dot(normal, u)) > 1e-6:
            raise ValueError('offset_pocket.u must be perpendicular to normal')
        # Remove residual rounding so the constructed plane has the specified normal.
        u = u - normal * np.dot(normal, u)
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        width = _number(data.get('width_mm'), 'offset_pocket.width_mm', positive=True)
        height = _number(data.get('height_mm'), 'offset_pocket.height_mm', positive=True)
        gap = _number(data.get('gap_mm', 3), 'offset_pocket.gap_mm', nonnegative=True)
        depth = _number(data.get('depth_mm'), 'offset_pocket.depth_mm', positive=True)
        center = point + normal * gap
        wire = BRepBuilderAPI_MakePolygon()
        for x, y in ((-1,-1), (1,-1), (1,1), (-1,1)):
            wire.Add(gp_Pnt(*(center + u*x*width/2 + v*y*height/2)))
        wire.Close()
        face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
        return BRepPrimAPI_MakePrism(face, gp_Vec(*(-normal*depth))).Shape()
    raise ValueError(f'unsupported printed feature type: {kind}')


def build_shapes(spec):
    """Return ({unique_name: single OCP solid}, JSON-safe geometry report)."""
    entries = spec.get('printed_bodies', [])
    if not isinstance(entries, list):
        raise ValueError('printed_bodies must be a list')
    shapes, records = {}, []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('each printed body must be an object')
        name = entry.get('name')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
            raise ValueError('printed body name must be a safe nonempty identifier')
        if name.startswith(('Part_', 'REF_', 'HW_')):
            raise ValueError('printed body name cannot use reserved Part_/REF_/HW_ prefix')
        if name in shapes:
            raise ValueError(f'duplicate printed body name: {name}')
        try:
            if 'finished_step' in entry:
                if any(k in entry for k in ('stock', 'add', 'subtract')):
                    raise ValueError('finished_step cannot be combined with stock/add/subtract')
                raw = entry['finished_step']
                if not isinstance(raw, str) or not raw:
                    raise ValueError('finished_step must be a nonempty path')
                path = Path(raw)
                if not path.is_absolute():
                    path = Path(spec.get('_dir', '.')) / path
                if not path.is_file():
                    raise ValueError(f'finished STEP does not exist: {path}')
                reader = STEPControl_Reader()
                if reader.ReadFile(str(path)) != IFSelect_RetDone or reader.TransferRoots() < 1:
                    raise ValueError(f'cannot read finished STEP: {path}')
                shape = _checked(reader.OneShape(), name)
                source = {'finished_step': str(path.resolve())}
            else:
                stock = entry.get('stock')
                if not isinstance(stock, dict) or stock.get('type', 'box') != 'box':
                    raise ValueError('stock must be a box with origin and size')
                shape = _checked(_feature(stock), name)
                for operation, cls in (('add', BRepAlgoAPI_Fuse), ('subtract', BRepAlgoAPI_Cut)):
                    features = entry.get(operation, [])
                    if not isinstance(features, list):
                        raise ValueError(f'{operation} must be a list')
                    for index, feature in enumerate(features):
                        if operation == 'add' and feature.get('type') == 'offset_pocket':
                            raise ValueError('offset_pocket is only a subtractive feature')
                        before = _volume(shape)
                        boolean = cls(shape, _feature(feature))
                        boolean.Build()
                        if not boolean.IsDone():
                            raise ValueError(f'{operation}[{index}] boolean failed')
                        shape = _checked(boolean.Shape(), f'{name}.{operation}[{index}]')
                        delta = _volume(shape) - before
                        if (delta if operation == 'add' else -delta) <= max(1e-9, before*1e-12):
                            raise ValueError(f'{operation}[{index}] does not change body volume')
                source = {'parametric': True, 'add_count': len(entry.get('add', [])), 'subtract_count': len(entry.get('subtract', []))}
            shapes[name] = shape
            records.append({'name': name, 'volume_mm3': _volume(shape), 'bounds_mm': _bounds(shape), 'valid_single_solid': True, **source})
        except (KeyError, TypeError, AttributeError, RuntimeError) as exc:
            raise ValueError(f'{name}: invalid printed body: {exc}') from exc
    return shapes, {'units': 'mm', 'body_count': len(shapes), 'bodies': records, 'physical_readiness': 'not_assessed'}


def _read_stl(path):
    data = Path(path).read_bytes()
    if len(data) >= 84:
        count = struct.unpack_from('<I', data, 80)[0]
        if len(data) == 84 + count*50:
            triangles = [struct.unpack_from('<12fH', data, 84+i*50)[3:12] for i in range(count)]
            return np.asarray(triangles, float).reshape((-1,3,3))
    vertices = []
    for line in data.decode('ascii').splitlines():
        words = line.split()
        if words and words[0] == 'vertex':
            vertices.append([float(x) for x in words[1:]])
    if not vertices or len(vertices) % 3:
        raise ValueError('STL contains no complete triangles')
    return np.asarray(vertices, float).reshape((-1,3,3))


def _mesh_topology(triangles, weld_mm):
    if not np.isfinite(triangles).all() or not len(triangles):
        raise ValueError('STL contains non-finite or missing geometry')
    edges, directed, fans = Counter(), Counter(), defaultdict(list)
    ids = {}
    vertices = []
    faces = []
    for triangle in triangles:
        face = []
        for point in triangle:
            key = tuple(np.rint(point / weld_mm).astype(np.int64))
            if key not in ids:
                ids[key] = len(vertices)
                vertices.append(point)
            face.append(ids[key])
        if len(set(face)) != 3 or np.linalg.norm(np.cross(triangle[1]-triangle[0], triangle[2]-triangle[0])) <= weld_mm*weld_mm:
            raise ValueError('STL contains degenerate triangles')
        face_id = len(faces)
        faces.append(face)
        for a,b in zip(face, face[1:]+face[:1]):
            edges[tuple(sorted((a,b)))] += 1
            directed[(a,b)] += 1
            fans[a].append(face_id)
    if any(count != 2 for count in edges.values()):
        raise ValueError('STL is open or has non-manifold edges')
    if any(directed[(a,b)] != 1 or directed[(b,a)] != 1 for a,b in edges):
        raise ValueError('STL winding is inconsistent')
    # Every vertex must have one connected triangle fan (reject bow-tie vertices).
    for vertex, incident in fans.items():
        pending = set(incident)
        frontier = [pending.pop()]
        while frontier:
            current = frontier.pop()
            neighbors = set(faces[current]) - {vertex}
            connected = {f for f in pending if neighbors.intersection(faces[f])}
            pending -= connected
            frontier.extend(connected)
        if pending:
            raise ValueError('STL has a non-manifold vertex')
    volume = float(np.einsum('ij,ij->i', triangles[:,0], np.cross(triangles[:,1], triangles[:,2])).sum()/6)
    if volume <= 0:
        raise ValueError('STL has inward winding or nonpositive volume')
    return {'vertex_count': len(vertices), 'triangle_count': len(triangles), 'closed_manifold': True, 'consistent_winding': True, 'positive_signed_volume': True, 'weld_tolerance_mm': weld_mm, 'volume_mm3': volume}


def export_meshes(shapes, out_dir, linear_deflection_mm=0.05):
    """Mesh OCP solids, reopen each STL, and reject failed dimensional/topology checks."""
    tolerance = _number(linear_deflection_mm, 'linear_deflection_mm', positive=True)
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    reports = []
    for name, original in shapes.items():
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
            raise ValueError('unsafe mesh body name')
        shape = _checked(original, name)
        # Discard prior triangulation: the requested absolute tolerance must take effect.
        BRepTools.Clean_s(shape)
        mesher = BRepMesh_IncrementalMesh(shape, tolerance, False, 0.1, False)
        mesher.Perform()
        if not mesher.IsDone():
            raise ValueError(f'{name}: OCP meshing failed')
        path = directory / f'{name}.stl'
        writer = StlAPI_Writer()
        writer.ASCIIMode = True  # Avoid binary float32 quantization for off-origin parts.
        if not writer.Write(shape, str(path)):
            raise ValueError(f'{name}: STL write failed')
        try:
            record = inspect_mesh(path, shape, tolerance, name)
            record.update(mesher='OCP BRepMesh_IncrementalMesh', relative_deflection=False, angular_deflection_rad=0.1)
            reports.append(record)
        except Exception:
            path.unlink(missing_ok=True)
            raise
    return {'units':'mm', 'mesh_count':len(reports), 'meshes':reports, 'physical_readiness':'not_assessed'}


def inspect_mesh(path, shape, linear_deflection_mm=0.05, name=None):
    """Reopen and validate an existing STL against one CAD solid; never modify it.

    Deflection is the comparison tolerance, not proof of the file's meshing settings.
    """
    tolerance = _number(linear_deflection_mm, 'linear_deflection_mm', positive=True)
    name = str(name) if name is not None else Path(path).stem
    shape = _checked(shape, name)
    triangles = _read_stl(path)
    bounds = np.asarray(_bounds(shape))
    magnitude = max(1.0, float(np.max(np.abs(bounds))))
    weld = max(1e-8, magnitude*1e-12)
    topology = _mesh_topology(triangles, weld)
    mesh_bounds = np.r_[triangles.min(axis=(0,1)), triangles.max(axis=(0,1))]
    bbox_error = float(np.max(np.abs(mesh_bounds - bounds)))
    if bbox_error > tolerance + weld*10:
        raise ValueError(f'{name}: STL bounds differ from CAD by {bbox_error:g} mm')
    # Sample all triangles for small meshes, evenly spaced up to 256 for large meshes.
    indices = np.unique(np.linspace(0, len(triangles)-1, min(256,len(triangles)), dtype=int))
    surface = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(surface)
    for face in _entities(shape, TopAbs_FACE):
        builder.Add(surface, face)
    max_deviation = 0.0
    for triangle in triangles[indices]:
        points = [triangle.mean(axis=0), *(0.5*(triangle[i]+triangle[(i+1)%3]) for i in range(3))]
        for point in points:
            distance = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Shape(), surface)
            distance.Perform()
            if not distance.IsDone():
                raise ValueError(f'{name}: mesh distance check failed')
            max_deviation = max(max_deviation, float(distance.Value()))
    if max_deviation > tolerance + weld*10:
        raise ValueError(f'{name}: sampled STL chordal deviation exceeds requested tolerance')
    return {'name':name, 'source_body': name, 'filename': Path(path).name, 'file':str(path), **topology, 'cad_volume_mm3': _volume(shape), 'cad_bounds_mm': bounds.tolist(), 'mesh_bounds_mm':mesh_bounds.tolist(), 'max_bounds_error_mm':bbox_error, 'linear_deflection_mm':tolerance, 'sampled_triangle_count':len(indices), 'sampled_point_count':len(indices)*4, 'max_sampled_surface_distance_mm':max_deviation, 'chordal_scope':'Requested absolute deflection tolerance; centroid and three edge midpoints on up to 256 evenly spaced triangles checked against CAD; not a global Hausdorff proof'}
