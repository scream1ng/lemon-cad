import copy
import math
import pytest
from backend.cad_document import validate_document
from worker.cad.authoring import rebuild, volume, write_step
from worker.cad.loader import load_step
from cad.icl import faced_mesh, face_sketch_plane


def angled_document():
    r=math.sqrt(.5)
    return {'schema_version':3,'rollback':2,'features':[
        {'id':'base','type':'sketch','profile':'rectangle','width':40,'height':30,'plane':'FACE',
         'frame':{'origin':[.123456789,2.345678901,3.456789012],'u':[0,1,0],'v':[-r,0,r]}},
        {'id':'base-extrusion','type':'extrude','sketch_id':'base','depth':10}]}


def test_exact_face_frame_add_cut_roundtrip_and_old_versions(tmp_path):
    doc=angled_document();base,normalized=rebuild(doc)
    assert volume(base)==pytest.approx(12000)
    path=tmp_path/'inclined.step';write_step(base,path)
    imported=load_step(str(path));mesh=faced_mesh(imported)
    r=math.sqrt(.5)
    top=next(f for f in mesh['faces'] if sum(a*b for a,b in zip(f['normal'],[r,0,r]))>.99)
    frame=face_sketch_plane(imported,top['id'])
    assert frame==top['plane_frame']
    assert any(abs(value-round(value,3))>1e-6 for value in frame['origin'])
    original=copy.deepcopy(normalized)
    normalized['features'] += [
        {'id':'boss-profile','type':'sketch','profile':'circle','diameter':4,'plane':'FACE','frame':frame},
        {'id':'boss','type':'extrude','sketch_id':'boss-profile','depth':3}]
    normalized['rollback']=4
    added,saved=rebuild(normalized)
    assert volume(added)==pytest.approx(12000+12*math.pi)
    write_step(added,path)
    assert volume(load_step(str(path)))==pytest.approx(volume(added))
    assert rebuild(saved)[1]==saved
    cut=copy.deepcopy(normalized);cut['features'][-1].update(operation='cut',direction=-1,extent='through_all')
    assert volume(rebuild(cut)[0])==pytest.approx(12000-40*math.pi)
    assert volume(rebuild(original)[0])==pytest.approx(12000)
    cut['features'][-1]['direction']=1
    with pytest.raises(ValueError,match='does not change|points away'):
        rebuild(cut)


@pytest.mark.parametrize('normal',[(-1,0,0),(1,0,0),(0,-1,0),(0,1,0),(0,0,-1),(0,0,1)])
def test_face_frames_on_all_six_sides_point_outward(normal):
    doc={'schema_version':2,'rollback':2,'features':[
        {'id':'s','type':'sketch','profile':'rectangle','width':40,'height':30},
        {'id':'e','type':'extrude','sketch_id':'s','depth':10}]}
    shape,_=rebuild(doc)
    face=next(f for f in faced_mesh(shape)['faces'] if f['normal']==list(normal))
    frame=face['plane_frame'];u,v=frame['u'],frame['v']
    cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
    assert cross==pytest.approx(normal)
    doc['schema_version']=3;doc['rollback']=4
    doc['features'] += [{'id':'s2','type':'sketch','profile':'rectangle','width':2,'height':2,'x':-1,'y':-1,'plane':'FACE','frame':frame},
        {'id':'e2','type':'extrude','sketch_id':'s2','depth':3}]
    assert volume(rebuild(doc)[0])==pytest.approx(12012)
    doc['features'][-1].update(operation='cut',direction=-1)
    assert volume(rebuild(doc)[0])==pytest.approx(11988)


@pytest.mark.parametrize('change',[
    lambda d:d.update(schema_version=2),
    lambda d:d['features'][0]['frame'].update(u=[2,0,0]),
    lambda d:d['features'][0]['frame'].update(v=[0,1,0]),
    lambda d:d['features'][0]['frame'].update(u=[float('nan'),0,0]),
    lambda d:d['features'][0].update(offset=1),
    lambda d:d['features'][0].update(plane='XY'),
    lambda d:d['features'][0].pop('frame'),
])
def test_invalid_or_ambiguous_frames_are_rejected(change):
    doc=angled_document();change(doc)
    with pytest.raises(ValueError):validate_document(doc)


def test_curved_and_missing_faces_do_not_become_flat_sketches():
    doc={'schema_version':2,'rollback':2,'features':[
        {'id':'s','type':'sketch','profile':'circle','diameter':20},
        {'id':'e','type':'extrude','sketch_id':'s','depth':10}]}
    shape,_=rebuild(doc);curved=next(f for f in faced_mesh(shape)['faces'] if f['type']=='cylinder')
    assert 'plane_frame' not in curved
    with pytest.raises(ValueError,match='planar'):face_sketch_plane(shape,curved['id'])
    with pytest.raises(ValueError,match='unavailable'):face_sketch_plane(shape,999)


def test_straight_edge_points_keep_exact_precision_for_sketch_positioning():
    from cad.icl import indexed_edges
    shape, _ = rebuild(angled_document())
    edges = indexed_edges(shape)
    points = [p for edge in edges if edge['type'] == 'line' for p in edge['points']]
    assert points
    # The arbitrary plane origin must survive the mesh metadata, not round to .001 mm.
    origin = angled_document()['features'][0]['frame']['origin']
    assert any(all(abs(a-b) < 1e-9 for a,b in zip(p, origin)) for p in points)
