import copy
import math
import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from worker.cad.authoring import rebuild, volume, write_step
from worker.cad.loader import load_step
from worker.tests.test_authoring import document, add


def sketch(id, **values):
    return {'id':id,'type':'sketch','profile':'rectangle',**values}


def extrusion(id, source, **values):
    return {'id':id,'type':'extrude','sketch_id':source,**values}


def bracket_document():
    features = [sketch('base',width=100,height=60), extrusion('plate','base',depth=3),
        sketch('wall',plane='XZ',offset=57,y=3,width=100,height=40), extrusion('upright','wall',depth=3)]
    for id,x in [('left',20),('right',80)]:
        features += [sketch(id,profile='circle',diameter=6,x=x,y=30),extrusion(id+'-cut',id,operation='cut',extent='through_all')]
    features += [sketch('wall-hole',profile='circle',plane='XZ',offset=57,x=50,y=23,diameter=8),extrusion('wall-cut','wall-hole',operation='cut',extent='through_all')]
    return {'schema_version':2,'features':features,'rollback':len(features)}


def test_bracket_exact_geometry_export_and_upstream_edit(tmp_path):
    doc=bracket_document(); original=copy.deepcopy(doc)
    shape, normalized=rebuild(doc)
    assert doc==original
    assert volume(shape)==pytest.approx(30000-102*math.pi)
    box=Bnd_Box();BRepBndLib.Add_s(shape,box)
    assert box.Get()==pytest.approx((0,0,0,100,60,43),abs=1e-6)
    path=tmp_path/'bracket.step';write_step(shape,path)
    assert volume(load_step(str(path)))==pytest.approx(volume(shape),rel=1e-7)
    assert rebuild(normalized)[1]==normalized
    doc['features'][2]['height']=50
    assert volume(rebuild(doc)[0])==pytest.approx(volume(shape)+3000)
    doc['rollback']=4
    assert volume(rebuild(doc)[0])==pytest.approx(33000)
    doc['rollback']=10;doc['features'][-1]['suppressed']=True
    assert volume(rebuild(doc)[0])==pytest.approx(33000-54*math.pi)


@pytest.mark.parametrize('points,closed',[
    ([(0,0),(10,10),(0,10),(10,0)],True),
    ([(0,0),(10,0),(20,0)],True),
    ([(0,0),(10,0),(10,10)],False),
    ([(0,0),(10,0),(10,0),(0,10)],True),
])
def test_invalid_profiles(points,closed):
    doc={'schema_version':2,'features':[sketch('p',profile='polygon',points=points,closed=closed),extrusion('e','p')],'rollback':2}
    with pytest.raises(ValueError,match='Sketch at history position 1'):
        rebuild(doc)


def test_polygon_and_negative_yz_extrusion():
    doc={'schema_version':2,'features':[sketch('p',profile='polygon',plane='YZ',offset=5,points=[(0,0),(10,0),(0,10)]),extrusion('e','p',depth=2,direction=-1)],'rollback':2}
    shape,_=rebuild(doc)
    assert volume(shape)==pytest.approx(100)
    b=Bnd_Box();BRepBndLib.Add_s(shape,b)
    assert b.Get()==pytest.approx((3,0,0,5,10,10),abs=1e-6)


@pytest.mark.parametrize('change,match',[
    (lambda d:d['features'][2].update(offset=70),'one solid'),
    (lambda d:d['features'][4].update(x=200),'does not change'),
    (lambda d:d['features'][2].update(suppressed=True),'source sketch'),
    (lambda d:d['features'][3].update(sketch_id='missing'),'earlier sketch'),
    (lambda d:d['features'][5].update(direction=-1),'does not change'),
    (lambda d:d['features'][4].update(diameter=1000),'one solid'),
])
def test_invalid_operations_preserve_document(change,match):
    doc=bracket_document();change(doc);before=copy.deepcopy(doc)
    with pytest.raises(ValueError,match=match):rebuild(doc)
    assert doc==before


def test_migrated_drilled_filleted_plate_keeps_exact_geometry():
    old=add(add(document(),{'id':'h','type':'hole','diameter':12,'x':40,'y':25}),{'id':'f','type':'fillet','radius':2})
    expected,normalized=rebuild(old)
    migrated=copy.deepcopy(normalized);migrated['schema_version']=2
    migrated['features'][1].update(sketch_id='sketch')
    actual,_=rebuild(migrated)
    assert volume(actual)==pytest.approx(volume(expected))
    migrated['features'] += [sketch('new',profile='circle',diameter=4,x=20,y=20),extrusion('cut','new',operation='cut',extent='through_all')]
    migrated['rollback']=6
    assert volume(rebuild(migrated)[0])==pytest.approx(volume(expected)-math.pi*4*10)
    assert old['schema_version']==1
