from copy import deepcopy
from sqlalchemy import select
from backend.tests.test_workflows import client, schema
from backend.db import DB, File, Artifact
from worker.main import run


def document():
    return {'schema_version':1, 'kind':'part', 'units':'mm', 'rollback':3, 'features':[
        {'id':'profile', 'type':'sketch', 'profile':'rectangle', 'width':80, 'height':50, 'diameter':50, 'suppressed':False},
        {'id':'extrusion', 'type':'extrude', 'depth':10, 'suppressed':False},
        {'id':'hole', 'type':'hole', 'diameter':12, 'x':40, 'y':25, 'suppressed':False}]}


def preview(c):
    queued=c.post('/api/cad/preview',json={'document':document()})
    assert queued.status_code==200, queued.text
    job=queued.json()['id']
    run(job)
    response=c.get('/api/jobs/'+job).json()
    assert response['status']=='completed', response
    return job,response['result']


def test_preview_permissions_durable_save_and_reopen():
    owner,stranger=client(True),client(True)
    assert client().post('/api/cad/preview',json={'document':document()}).status_code==401
    job,result=preview(owner)
    assert owner.get('/api/workspace').json()['projects']==[]  # preview has not saved a revision
    assert stranger.get('/api/jobs/'+job).status_code==404
    for artifact in [result['mesh'],result['cad_step']]:
        assert owner.get('/api/files/'+artifact).status_code==200
        assert stranger.get('/api/files/'+artifact).status_code==404
    state={'cad_document':result['cad_document'],'cad_job_id':job,'dimensions':[],'unit':'mm'}
    folder=owner.post('/api/folders',json={'name':'Native parts'}).json()['id']
    payload={'file_id':result['cad_step'],'name':'Drilled plate','folder_id':folder,'state':state}
    saved=owner.post('/api/projects',json=payload)
    assert saved.status_code==200,saved.text
    project=saved.json()
    reopened=owner.get('/api/revisions/'+project['revision_id']).json()
    assert reopened['state']==state and reopened['mesh']==result
    with DB() as db:
        assert db.get(File,result['cad_step']).expires_at is None
        for artifact in db.scalars(select(Artifact).where(Artifact.job_id==job)):
            assert db.get(File,artifact.file_id).expires_at is None
    assert stranger.patch('/api/projects/'+project['id'],json={'name':'stolen'}).status_code==404
    renamed=owner.patch('/api/projects/'+project['id'],json={'name':'Renamed plate'})
    assert renamed.status_code==200 and renamed.json()['name']=='Renamed plate'
    assert owner.patch('/api/projects/'+project['id'],json={'name':'  '}).status_code==422
    assert stranger.get('/api/projects/'+project['id']+'/revisions').status_code==404
    link=owner.post('/api/shares',json={'folder_id':folder}).json()['path'][1:]
    owner.post('/api/projects/'+project['id']+'/publish')
    assert stranger.get('/api/files/'+result['mesh']+link).status_code==200
    assert stranger.get('/api/projects/'+project['id']+'/revisions'+link).json()[0]['id']==project['revision_id']
    payload.update(project_id=project['id'],parent_revision_id=project['revision_id'])
    second=owner.post('/api/projects',json=payload)
    assert second.status_code==200
    assert len(owner.get('/api/projects/'+project['id']+'/revisions').json())==2
    assert len(stranger.get('/api/projects/'+project['id']+'/revisions'+link).json())==1
    assert owner.post('/api/projects',json=payload).status_code==409


def test_provenance_and_contract_cannot_be_forged():
    owner=client(True)
    job,result=preview(owner)
    state={'cad_document':deepcopy(result['cad_document']),'cad_job_id':job}
    state['cad_document']['features'][1]['depth']=99
    payload={'file_id':result['cad_step'],'name':'Forged','state':state}
    assert owner.post('/api/projects',json=payload).status_code==422
    payload['state']={}
    assert owner.post('/api/projects',json=payload).status_code==404
    bad=document();bad['features'][1]['depth']=0
    assert owner.post('/api/cad/preview',json={'document':bad}).status_code==422
    bad=document();bad['features'][2]['id']='profile'
    assert owner.post('/api/cad/preview',json={'document':bad}).status_code==422
    bad=document();bad['features'][0]['suppressed']=True
    assert owner.post('/api/cad/preview',json={'document':bad}).status_code==422


def test_v2_bracket_save_reopen_and_failed_edit_preserves_revision():
    import math
    import pytest
    from worker.tests.test_profile_authoring import bracket_document
    owner=client(True)
    doc=bracket_document()
    queued=owner.post('/api/cad/preview',json={'document':doc})
    assert queued.status_code==200,queued.text
    job=queued.json()['id'];run(job)
    response=owner.get('/api/jobs/'+job).json()
    assert response['status']=='completed',response
    result=response['result']
    assert result['volume_mm3']==pytest.approx(30000-102*math.pi)
    state={'cad_document':result['cad_document'],'cad_job_id':job,'dimensions':[]}
    saved=owner.post('/api/projects',json={'file_id':result['cad_step'],'name':'Bracket v2','state':state})
    assert saved.status_code==200,saved.text
    project=saved.json()
    opened=owner.get('/api/revisions/'+project['revision_id']).json()
    assert opened['state']==state and opened['mesh']==result
    assert owner.get('/api/files/'+result['cad_step']).content.startswith(b'ISO-10303-21;')
    doc['features'][2]['offset']=500
    bad=owner.post('/api/cad/preview',json={'document':doc})
    with pytest.raises(ValueError,match='one solid'):
        run(bad.json()['id'])
    assert owner.get('/api/revisions/'+project['revision_id']).json()['state']==state
    assert len(owner.get('/api/projects/'+project['id']+'/revisions').json())==1
    invalid=bracket_document();invalid['features'][3]['sketch_id']='future-sketch'
    assert owner.post('/api/cad/preview',json={'document':invalid}).status_code==422


def test_v3_face_plane_lookup_preview_save_and_reopen():
    import pytest
    from worker.tests.test_face_sketch import angled_document
    owner,stranger=client(True),client(True)
    doc=angled_document()
    queued=owner.post('/api/cad/preview',json={'document':doc})
    assert queued.status_code==200,queued.text
    job=queued.json()['id'];run(job)
    result=owner.get('/api/jobs/'+job).json()['result']
    mesh=owner.get('/api/files/'+result['mesh']).json()
    face=mesh['faces'][0]
    payload={'file_id':result['cad_step'],'face_id':face['id']}
    assert client().post('/api/cad/face-plane',json=payload).status_code==401
    assert stranger.post('/api/cad/face-plane',json=payload).status_code==404
    assert owner.post('/api/cad/face-plane',json={**payload,'face_id':0}).status_code==422
    plane_job=owner.post('/api/cad/face-plane',json=payload)
    assert plane_job.status_code==200,plane_job.text
    run(plane_job.json()['id'])
    frame=owner.get('/api/jobs/'+plane_job.json()['id']).json()['result']['frame']
    assert frame==face['plane_frame']
    state={'cad_document':result['cad_document'],'cad_job_id':job,'dimensions':[]}
    saved=owner.post('/api/projects',json={'file_id':result['cad_step'],'name':'Angled face v3','state':state})
    assert saved.status_code==200,saved.text
    opened=owner.get('/api/revisions/'+saved.json()['revision_id']).json()
    assert opened['state']==state
    assert opened['mesh']['volume_mm3']==pytest.approx(12000)
    assert owner.get('/api/files/'+result['cad_step']).content.startswith(b'ISO-10303-21;')
