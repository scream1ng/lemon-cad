import time
import uuid
from datetime import timedelta
import pytest
from sqlalchemy import select
from backend.tests.test_workflows import client, schema
from backend.db import DB, Entitlement, Job, now
from backend import google_login, engineering_chat

ORIGIN = {'origin': 'http://127.0.0.1:5178'}


def google_request(c, monkeypatch, email=None, subject=None, **overrides):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test-client')
    nonce = c.get('/api/google/nonce').json()['nonce']
    claims = {'iss': 'https://accounts.google.com', 'aud': 'test-client', 'nonce': nonce, 'iat': time.time(), 'sub': subject or uuid.uuid4().hex, 'email': email or uuid.uuid4().hex+'@gmail.com', 'email_verified': True, **overrides}
    monkeypatch.setattr(google_login, 'verify_google', lambda credential, audience: claims)
    return c.post('/api/google/sign-in', json={'credential': 'fake-token-for-test-only', 'nonce': nonce}, headers=ORIGIN), claims


def test_google_new_user_returning_user_and_logout(monkeypatch):
    c = client()
    response, claims = google_request(c, monkeypatch)
    assert response.status_code == 200, response.text
    uid = response.json()['id']
    assert c.get('/api/me').json()['user']['google_connected'] is True
    assert 'HttpOnly' in response.headers['set-cookie']
    c.post('/api/logout')
    assert c.get('/api/me').json()['user'] is None
    response, _ = google_request(c, monkeypatch, email='changed-'+claims['email'], subject=claims['sub'])
    assert response.status_code == 200 and response.json()['id'] == uid


def test_google_requires_password_before_linking_existing_account(monkeypatch):
    owner, stranger = client(True), client()
    account = owner.get('/api/me').json()['user']
    subject = uuid.uuid4().hex
    response, _ = google_request(stranger, monkeypatch, email=account['email'], subject=subject)
    assert response.status_code == 409
    response, _ = google_request(owner, monkeypatch, email=account['email'], subject=subject)
    assert response.status_code == 200 and response.json()['id'] == account['id']
    response, _ = google_request(owner, monkeypatch, email=account['email'])
    assert response.status_code == 409, 'cannot replace an existing Google identity'


@pytest.mark.parametrize('claims', [{'aud': 'other-app'}, {'iss': 'https://attacker.test'}, {'iat': time.time()-1000}, {'email_verified': False}, {'nonce': 'different-nonce'}])
def test_google_rejects_invalid_claims(monkeypatch, claims):
    response, _ = google_request(client(), monkeypatch, **claims)
    assert response.status_code == 401


def test_google_rejects_missing_nonce_and_cross_origin(monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test-client')
    c = client()
    payload = {'credential': 'fake-token-for-test-only', 'nonce': 'missing-nonce-1234567890'}
    assert c.post('/api/google/sign-in', json=payload, headers=ORIGIN).status_code == 401
    assert c.post('/api/google/sign-in', json=payload, headers={'origin':'https://attacker.test'}).status_code == 403
    assert c.post('/api/google/sign-in', json=payload).status_code == 403


def test_google_unconfigured(monkeypatch):
    monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
    c = client()
    assert c.get('/api/auth/options').json()['google_client_id'] is None
    assert c.get('/api/google/nonce').status_code == 503


def grant(c):
    uid = c.get('/api/me').json()['user']['id']
    with DB.begin() as db:
        db.add(Entitlement(user_id=uid, capability='costing', grant='test', expires_at=now()+timedelta(days=1)))
    return uid


def test_chat_access_config_and_usage(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    body = {'service':'costing', 'messages':[{'role':'user','content':'Help me estimate cost.'}]}
    anonymous, signed = client(), client(True)
    assert anonymous.post('/api/engineering/chat', json=body).status_code == 401
    assert signed.post('/api/engineering/chat', json=body).status_code == 402
    uid = grant(signed)
    assert signed.get('/api/engineering/chat/config').json()['available'] is False
    assert signed.post('/api/engineering/chat', json=body).status_code == 503
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-only')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'configured-model')
    captured = []
    def provider(payload):
        captured.append(payload)
        return {'content':[{'type':'text','text':'What material and batch quantity?'}], 'usage':{'input_tokens':10,'output_tokens':8},'model':'configured-model'}
    monkeypatch.setattr(engineering_chat, 'call_claude', provider)
    assert signed.post('/api/engineering/chat', json={**body,'file_id':'not-owned'}).status_code == 404
    response = signed.post('/api/engineering/chat', json=body)
    assert response.status_code == 200, response.text
    assert response.json()['content'] == 'What material and batch quantity?'
    assert captured[0]['max_tokens'] == 1600
    with DB() as db:
        job = db.get(Job, response.json()['id'])
        assert job.owner_id == uid and job.result['usage']['output_tokens'] == 8
