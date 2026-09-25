"""Integration tests against disposable lemoncad_test, never the application database.
Setup: docker exec lemoncad-postgres-1 createdb -U lemon lemoncad_test
"""
import os
import uuid
from datetime import timedelta
from pathlib import Path
os.environ['DATABASE_URL'] = os.environ.get('TEST_DATABASE_URL', 'postgresql+psycopg://lemon:lemon@127.0.0.1:55438/lemoncad_test')
os.environ['STORAGE_DIR'] = '.data/test-objects'
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.db import Base, engine, DB, User, Job, File, Entitlement, now
from backend.main import app
from worker.main import run


@pytest.fixture(scope='session', autouse=True)
def schema():
    assert engine.url.database.endswith('_test'), 'Tests must use a dedicated _test database'
    Base.metadata.create_all(engine)


def client(signup=False):
    c = TestClient(app)
    c.get('/api/me')
    if signup:
        email = uuid.uuid4().hex + '@example.test'
        r = c.post('/api/auth/signup', json={'email': email, 'password': 'LemonTestPassword123!'})
        assert r.status_code == 200, r.text
    return c


def upload(c):
    r = c.post('/api/uploads', files={'file': ('reference.step', Path('frontend/public/sample-bracket.step').read_bytes(), 'application/octet-stream')})
    assert r.status_code == 200, r.text
    job = r.json()
    run(job['id'])
    result = c.get('/api/jobs/' + job['id']).json()
    assert result['status'] == 'completed', result
    return job, result['result']


def test_anonymous_exact_geometry_and_access():
    c, stranger = client(), client()
    job, result = upload(c)
    mesh = c.get('/api/files/' + result['mesh']).json()
    cylinder = next(f for f in mesh['faces'] if f['type'] == 'cylinder')
    measure = c.post('/api/measure', json={'file_id': job['file_id'], 'faces': [cylinder['id']]})
    assert measure.status_code == 200
    run(measure.json()['id'])
    value = c.get('/api/jobs/' + measure.json()['id']).json()['result']
    assert value['type'] == 'dia' and value['value_mm'] == 12
    assert stranger.get('/api/files/' + job['file_id']).status_code == 404
    assert stranger.get('/api/files/' + result['mesh']).status_code == 404
    assert stranger.get('/api/jobs/' + job['id']).status_code == 404
    assert c.post('/api/uploads', files={'file': ('part.sldprt', b'bad')}).status_code == 415
    assert c.post('/api/measure', json={'file_id': job['file_id'], 'faces': [1, 1]}).status_code == 422
    assert c.post('/api/costing', json={'estimate': {}}).status_code == 401


def test_save_publish_revoke_and_invitation():
    owner, stranger = client(True), client(True)
    job, mesh = upload(owner)
    folder = owner.post('/api/folders', json={'name': 'Assembly'}).json()['id']
    child = owner.post('/api/folders', json={'name': 'Parts', 'parent_id': folder}).json()['id']
    body = {'file_id': job['file_id'], 'name': 'Bracket', 'folder_id': child, 'state': {'unit': 'mm', 'dimensions': [], 'camera': {'zoom': 1}}}
    saved = owner.post('/api/projects', json=body)
    assert saved.status_code == 200, saved.text
    project = saved.json()
    rid = project['revision_id']
    assert stranger.get('/api/revisions/' + rid).status_code == 404
    link = owner.post('/api/shares', json={'folder_id': folder}).json()
    query = link['path'][1:]
    assert stranger.get('/api/shared' + query).json()['projects'] == []
    owner.post('/api/projects/' + project['id'] + '/publish')
    assert stranger.get('/api/shared' + query).json()['projects'][0]['revision_id'] == rid
    assert stranger.get('/api/files/' + mesh['mesh'] + query).status_code == 200
    body.update(project_id=project['id'], parent_revision_id=rid, state={'unit': 'in'})
    newer = owner.post('/api/projects', json=body).json()
    assert stranger.get('/api/revisions/' + newer['revision_id'] + query).status_code == 404
    assert stranger.get('/api/revisions/' + rid + query).status_code == 200
    assert owner.post('/api/projects', json=body).status_code == 409
    owner.delete('/api/shares/' + link['id'])
    assert stranger.get('/api/revisions/' + rid + query).status_code == 404
    email = stranger.get('/api/me').json()['user']['email']
    invitation = owner.post(f'/api/folders/{folder}/invites', json={'email': email}).json()['path'].split('invite=')[1]
    assert stranger.post(f'/api/invites/{invitation}/accept').status_code == 200
    assert stranger.get('/api/revisions/' + rid).status_code == 200
    member = owner.get(f'/api/folders/{folder}/access').json()['members'][0]['id']
    owner.delete(f'/api/folders/{folder}/access/{member}')
    assert stranger.get('/api/revisions/' + rid).status_code == 404
    owner.post('/api/logout')
    assert owner.get('/api/revisions/' + newer['revision_id']).status_code == 404


def test_drawing_review_and_saved_artifacts():
    c = client(True)
    job, _ = upload(c)
    drawing = c.post('/api/drawings', json={'file_id': job['file_id'], 'title': 'Reference bracket', 'material': 'Steel', 'density_kg_m3': 7850}).json()
    run(drawing['id'])
    result = c.get('/api/jobs/' + drawing['id']).json()
    assert result['status'] == 'completed', result
    r = result['result']
    assert r['sheets'] and c.get('/api/files/' + r['sheets'][0]).status_code == 200
    assert c.get('/api/files/' + r['pdf']).status_code == 409
    assert c.post('/api/jobs/' + drawing['id'] + '/review', json={'revision_hash': 'stale', 'decision': 'approved', 'note': 'Review'}).status_code == 409
    assert c.post('/api/jobs/' + drawing['id'] + '/review', json={'revision_hash': r['revision_hash'], 'decision': 'approved', 'note': 'Reviewed, export PDF'}).status_code == 200
    assert c.get('/api/files/' + r['pdf']).content.startswith(b'%PDF')
    saved = c.post('/api/projects', json={'file_id': job['file_id'], 'name': 'Drawing project', 'state': {'drawing_job_id': drawing['id']}})
    assert saved.status_code == 200, saved.text
    with DB() as db:
        assert db.get(File, r['pdf']).expires_at is None
    share = c.post('/api/shares', json={'revision_id': saved.json()['revision_id']}).json()['path'][1:]
    assert client().get('/api/files/' + r['pdf'] + share).status_code == 200


def test_entitlements_costing_and_cancellation():
    c = client(True)
    estimate = {'schema_version': 2, 'quantity': 10, 'gross_margin': .2, 'components': [{'id': 'part', 'name': 'Part', 'parent_id': None, 'quantity_per_parent': 1, 'make_buy': 'make'}], 'rows': [{'id': 'material', 'name': 'Material', 'kind': 'fixed', 'category': 'material', 'basis': 'per part', 'component_id': 'part', 'unit_price': 20}, {'id': 'operation', 'name': 'Operation', 'kind': 'process', 'category': 'component_processing', 'basis': 'per part', 'component_id': 'part', 'setup_h': 1, 'setup_count': 1, 'pcs_per_h': 60, 'hourly_rate': 60, 'rate_basis': 'Test rate', 'cycle_seconds': {'operation': 60}, 'cycle_basis': 'Test cycle'}]}
    assert c.post('/api/costing', json={'estimate': estimate}).status_code == 402
    user_id = c.get('/api/me').json()['user']['id']
    with DB.begin() as db:
        db.add(Entitlement(user_id=user_id, capability='costing', grant='test', expires_at=now()+timedelta(days=1)))
    job = c.post('/api/costing', json={'estimate': estimate}).json()
    run(job['id'])
    result = c.get('/api/jobs/' + job['id']).json()['result']
    assert result['selling_batch'] == pytest.approx(337.5)
    cancelled = c.post('/api/costing', json={'estimate': estimate}).json()
    assert c.post('/api/jobs/' + cancelled['id'] + '/cancel').json()['status'] == 'cancelled'
    assert c.post('/api/costing', json={'estimate': estimate}, headers={'origin': 'https://evil.example'}).status_code == 403
