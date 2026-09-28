import hashlib
import json
import os
import re
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, Depends
from fastapi.responses import Response as BytesResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from backend.db import DB, User, GoogleIdentity, Session, Folder, FolderMember, FolderInvite, File, Project, Revision, Share, Job, Artifact, Entitlement, Review, now, uid
from backend import storage
from backend.cad_document import CadDocument

app = FastAPI(title='LemonCAD')
passwords = PasswordHasher()
SECURE = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'
MAX_UPLOAD = 50 * 1024 * 1024


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def fail(code, message):
    raise HTTPException(code, message)


def db_session():
    with DB() as db:
        yield db


def user_of(request, db, required=False):
    token = request.cookies.get('lemon_session', '')
    session = db.get(Session, digest(token))
    user = db.get(User, session.user_id) if session and session.expires_at > now() and not session.revoked_at else None
    if required and not user:
        fail(401, 'Sign in to save, share and generate drawings.')
    return user


def anon(request):
    return digest(request.cookies.get('lemon_anon', ''))


@app.middleware('http')
async def protections(request, call_next):
    origin = request.headers.get('origin')
    allowed = os.environ.get('APP_ORIGIN', 'http://127.0.0.1:5178').rstrip('/')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin != allowed:
        return BytesResponse('Origin rejected', status_code=403)
    response = await call_next(request)
    if not request.cookies.get('lemon_anon'):
        response.set_cookie('lemon_anon', secrets.token_urlsafe(32), httponly=True, secure=SECURE, samesite='lax', max_age=86400)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Auth(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


@app.get('/api/health')
def health(db=Depends(db_session)):
    db.execute(select(1))
    return {'ok': True}


@app.get('/api/me')
def me(request: Request, db=Depends(db_session)):
    user = user_of(request, db)
    caps = [] if not user else list(db.scalars(select(Entitlement.capability).where(Entitlement.user_id == user.id, Entitlement.expires_at > now(), Entitlement.revoked_at.is_(None))))
    return {'user': {'id': user.id, 'email': user.email, 'google_connected': bool(db.scalar(select(GoogleIdentity.id).where(GoogleIdentity.user_id == user.id)))} if user else None, 'capabilities': caps}


@app.post('/api/auth/{action}')
def auth(action: Literal['signup', 'login'], data: Auth, request: Request, response: Response, db=Depends(db_session)):
    email = data.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        fail(422, 'Enter a valid email address.')
    user = db.scalar(select(User).where(User.email == email))
    if action == 'signup':
        if user:
            fail(409, 'An account already exists. Sign in instead.')
        user = User(email=email, password_hash=passwords.hash(data.password))
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            fail(409, 'An account already exists.')
    else:
        try:
            if not user:
                passwords.verify(passwords.hash('invalid-password'), data.password)
                fail(401, 'Email or password is incorrect.')
            passwords.verify(user.password_hash, data.password)
        except VerificationError:
            fail(401, 'Email or password is incorrect.')
    token = secrets.token_urlsafe(32)
    db.add(Session(token=digest(token), user_id=user.id, expires_at=now() + timedelta(days=30)))
    db.commit()
    response.set_cookie('lemon_session', token, httponly=True, secure=SECURE, samesite='lax', max_age=2592000)
    return {'id': user.id, 'email': user.email}


@app.post('/api/logout')
def logout(request: Request, response: Response, db=Depends(db_session)):
    session = db.get(Session, digest(request.cookies.get('lemon_session', '')))
    if session:
        session.revoked_at = now()
        db.commit()
    response.delete_cookie('lemon_session', secure=SECURE, httponly=True, samesite='lax')
    return {'ok': True}


def ancestors(db, folder_id):
    chain = []
    while folder_id and folder_id not in chain:
        folder = db.get(Folder, folder_id)
        if not folder:
            break
        chain.append(folder.id)
        folder_id = folder.parent_id
    return chain


def share_of(request, db):
    token = request.query_params.get('share')
    if not token:
        return None
    return db.scalar(select(Share).where(Share.token == digest(token), Share.revoked_at.is_(None), Share.expires_at > now()))


def can_revision(request, db, revision):
    if not revision:
        return False
    project = db.get(Project, revision.project_id)
    user = user_of(request, db)
    if user and project.owner_id == user.id:
        return True
    share = share_of(request, db)
    if share and share.project_revision_id == revision.id:
        return True
    if project.published_revision_id != revision.id:
        return False
    chain = ancestors(db, project.folder_id)
    if share and share.folder_id in chain:
        return True
    return bool(user and chain and db.scalar(select(FolderMember.id).where(FolderMember.user_id == user.id, FolderMember.folder_id.in_(chain))))


def own_file(request, db, file):
    user = user_of(request, db)
    return bool(file and (not file.expires_at or file.expires_at > now()) and ((user and file.owner_id == user.id) or (not file.owner_id and file.anonymous_session_hash == anon(request))))


def read_file(request, db, file_id):
    file = db.get(File, file_id)
    if not file or (file.expires_at and file.expires_at <= now()):
        fail(404, 'File not found or expired.')
    if own_file(request, db, file):
        return file
    for revision in db.scalars(select(Revision).where(Revision.source_file_id == file.id)):
        if can_revision(request, db, revision):
            return file
    for artifact in db.scalars(select(Artifact).where(Artifact.file_id == file.id)):
        job = db.get(Job, artifact.job_id)
        # Imports follow source permissions; drawings must be explicitly attached to a published revision.
        if job.type == 'import':
            source = db.get(File, job.input['file_id'])
            for revision in db.scalars(select(Revision).where(Revision.source_file_id == source.id)):
                if can_revision(request, db, revision):
                    return file
        else:
            for revision in db.scalars(select(Revision)):
                if job.id in (revision.state.get('drawing_job_id'), revision.state.get('cad_job_id')) and can_revision(request, db, revision):
                    return file
    fail(404, 'File not found.')


@app.get('/api/files/{file_id}')
def download(file_id: str, request: Request, db=Depends(db_session)):
    file = read_file(request, db, file_id)
    if file.format == 'pdf':
        artifact = db.scalar(select(Artifact).where(Artifact.file_id == file.id, Artifact.kind == 'pdf'))
        if artifact and not db.scalar(select(Review.id).where(Review.job_id == artifact.job_id, Review.revision_hash == artifact.revision_hash, Review.decision == 'approved')):
            fail(409, 'Review the generated drawing before downloading its PDF.')
    mime = {'json': 'application/json', 'pdf': 'application/pdf', 'svg': 'image/svg+xml', 'stl': 'application/octet-stream'}.get(file.format, 'application/octet-stream')
    return BytesResponse(storage.get(file.storage_key), media_type=mime, headers={'Content-Disposition': f"inline; filename*=UTF-8''{quote(file.name)}", 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; sandbox"})


def new_job(db, request, kind, payload, revision_id=None):
    user = user_of(request, db)
    owner_filter = Job.owner_id == user.id if user else Job.anonymous_session_hash == anon(request)
    if db.scalar(select(func.count()).select_from(Job).where(owner_filter, Job.status.in_(['queued', 'running']))) >= 3:
        fail(429, 'Three jobs are already in progress. Wait or cancel one.')
    job = Job(owner_id=user.id if user else None, anonymous_session_hash=anon(request), type=kind, input=payload, project_revision_id=revision_id)
    db.add(job)
    db.commit()
    return {'id': job.id, 'status': job.status}


@app.post('/api/uploads')
async def upload(request: Request, file: UploadFile, db=Depends(db_session)):
    if not request.cookies.get('lemon_anon'):
        fail(409, 'Reload the page before uploading.')
    name = Path(file.filename or '').name[:160]
    extension = name.rsplit('.', 1)[-1].lower()
    if extension not in ('step', 'stp', 'stl'):
        fail(415, 'Choose STEP, STP or STL. Export native CAD to STEP first.')
    data = await file.read(MAX_UPLOAD + 1)
    await file.close()
    if not data or len(data) > MAX_UPLOAD:
        fail(413, 'Choose a non-empty file smaller than 50 MB.')
    user = user_of(request, db)
    owner_filter = File.owner_id == user.id if user else File.anonymous_session_hash == anon(request)
    if db.scalar(select(func.count()).select_from(File).where(owner_filter, File.created_at > now() - timedelta(hours=24))) >= 100:
        fail(429, 'Daily upload limit reached. Try again tomorrow.')
    key = uid()
    storage.put(key, data)
    record = File(owner_id=user.id if user else None, anonymous_session_hash=anon(request), storage_key=key, name=name, format=extension, size=len(data), sha256=hashlib.sha256(data).hexdigest(), expires_at=now() + timedelta(hours=24))
    db.add(record)
    db.flush()
    result = new_job(db, request, 'import', {'file_id': record.id})
    return {**result, 'file_id': record.id, 'name': name, 'format': extension}


def own_job(request, db, job_id):
    job = db.get(Job, job_id)
    user = user_of(request, db)
    if not job or not ((user and job.owner_id == user.id) or (not job.owner_id and job.anonymous_session_hash == anon(request))):
        fail(404, 'Job not found.')
    return job


@app.get('/api/jobs/{job_id}')
def job_status(job_id: str, request: Request, db=Depends(db_session)):
    job = own_job(request, db, job_id)
    return {'id': job.id, 'type': job.type, 'status': job.status, 'result': job.result, 'error': job.error}


@app.post('/api/jobs/{job_id}/cancel')
def cancel(job_id: str, request: Request, db=Depends(db_session)):
    job = own_job(request, db, job_id)
    if job.status in ('queued', 'running'):
        job.status = 'cancelled'
        db.commit()
    return {'status': job.status}


class MeasureEntity(Input):
    kind: Literal['face', 'edge']
    id: int = Field(gt=0)


class Measure(Input):
    file_id: str
    faces: list[int] = Field(default_factory=list, max_length=2)
    entities: list[MeasureEntity] = Field(default_factory=list, max_length=2)
    relation: Literal['centre', 'clearance'] = 'centre'


@app.post('/api/measure')
def measure(data: Measure, request: Request, db=Depends(db_session)):
    file = read_file(request, db, data.file_id)
    refs = [(r.kind, r.id) for r in data.entities] or [('face', i) for i in data.faces]
    if file.format not in ('step', 'stp') or not refs or (data.entities and data.faces) or any(i <= 0 for _, i in refs) or len(set(refs)) != len(refs):
        fail(422, 'Select one cylindrical face or two different STEP faces.')
    return new_job(db, request, 'measure', data.model_dump())


class FolderInput(Input):
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None


def owned(db, model, id, user):
    obj = db.get(model, id)
    if not obj or obj.owner_id != user.id:
        fail(404, 'Not found.')
    return obj


@app.post('/api/folders')
def folder_create(data: FolderInput, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    if not data.name.strip():
        fail(422, 'Enter a folder name.')
    if data.parent_id:
        owned(db, Folder, data.parent_id, user)
    obj = Folder(owner_id=user.id, name=data.name.strip(), parent_id=data.parent_id)
    db.add(obj)
    db.commit()
    return {'id': obj.id}


def project_summary(p, revision_id=None):
    return {'id': p.id, 'name': p.name, 'folder_id': p.folder_id, 'revision_id': revision_id or p.current_revision_id, 'published': bool(p.published_revision_id)}


@app.get('/api/workspace')
def workspace(request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    folders = list(db.scalars(select(Folder).where(Folder.owner_id == user.id)))
    projects = list(db.scalars(select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc())))
    shared = []
    for p in db.scalars(select(Project).where(Project.owner_id != user.id, Project.published_revision_id.is_not(None))):
        if can_revision(request, db, db.get(Revision, p.published_revision_id)):
            shared.append(project_summary(p, p.published_revision_id))
    return {'folders': [{'id': f.id, 'name': f.name, 'parent_id': f.parent_id} for f in folders], 'projects': [project_summary(p) for p in projects], 'shared': shared}


class CadPreview(Input):
    document: CadDocument


@app.post('/api/cad/preview')
def cad_preview(data: CadPreview, request: Request, db=Depends(db_session)):
    user_of(request, db, True)
    return new_job(db, request, 'cad', {'document': data.document.model_dump()})


class FacePlane(Input):
    file_id: str
    face_id: int = Field(gt=0)


@app.post('/api/cad/face-plane')
def cad_face_plane(data: FacePlane, request: Request, db=Depends(db_session)):
    user_of(request, db, True)
    file = read_file(request, db, data.file_id)
    if file.format not in ('step', 'stp'):
        fail(422, 'Face sketches require STEP geometry.')
    return new_job(db, request, 'face_plane', data.model_dump())


class RenameProject(Input):
    name: str = Field(min_length=1, max_length=120)


@app.patch('/api/projects/{project_id}')
def rename_project(project_id: str, data: RenameProject, request: Request, db=Depends(db_session)):
    project = owned(db, Project, project_id, user_of(request, db, True))
    if not data.name.strip():
        fail(422, 'Enter a project name.')
    project.name = data.name.strip()
    db.commit()
    return project_summary(project)


@app.get('/api/projects/{project_id}/revisions')
def project_revisions(project_id: str, request: Request, db=Depends(db_session)):
    project = db.get(Project, project_id)
    if not project:
        fail(404, 'Project not found.')
    revisions = list(db.scalars(select(Revision).where(Revision.project_id == project_id).order_by(Revision.created_at.desc())))
    visible = [r for r in revisions if can_revision(request, db, r)]
    if not visible:
        fail(404, 'Project not found.')
    return [{'id': r.id, 'created_at': r.created_at, 'current': r.id == project.current_revision_id,
             'published': r.id == project.published_revision_id} for r in visible]


class Save(Input):
    name: str = Field(min_length=1, max_length=120)
    file_id: str
    folder_id: str | None = None
    project_id: str | None = None
    parent_revision_id: str | None = None
    state: dict = Field(default_factory=dict)


@app.post('/api/projects')
def save(data: Save, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    file = db.get(File, data.file_id)
    if not own_file(request, db, file):
        fail(404, 'Source file not found.')
    if len(json.dumps(data.state, allow_nan=False)) > 200000:
        fail(413, 'Too many annotations.')
    if data.folder_id:
        owned(db, Folder, data.folder_id, user)
    if data.project_id:
        project = owned(db, Project, data.project_id, user)
        db.refresh(project, with_for_update=True)
        if project.current_revision_id != data.parent_revision_id:
            fail(409, 'This project has a newer draft. Reopen it before saving.')
        if project.folder_id != data.folder_id:
            fail(422, 'Save a copy to change folders; existing sharing stays unchanged.')
    else:
        project = Project(owner_id=user.id, name=data.name, folder_id=data.folder_id)
        db.add(project)
        db.flush()
    cad_id = data.state.get('cad_job_id')
    cad_document = data.state.get('cad_document')
    generated = db.scalar(select(Artifact).where(Artifact.file_id == file.id, Artifact.kind == 'cad_step'))
    if cad_id or cad_document or generated:
        job = own_job(request, db, cad_id or '')
        if job.type != 'cad' or job.status != 'completed' or job.result.get('cad_step') != file.id or job.input.get('document') != cad_document:
            fail(422, 'CAD document and generated geometry must come from the same completed preview.')
    drawing_id = data.state.get('drawing_job_id')
    if drawing_id:
        job = own_job(request, db, drawing_id)
        if job.type != 'drawing' or job.status != 'completed' or job.input['file_id'] != file.id:
            fail(422, 'Drawing must be completed for this exact source file.')
        if not db.scalar(select(Review.id).where(Review.job_id == job.id, Review.decision == 'approved')):
            fail(422, 'Review the drawing before attaching it.')
    revision = Revision(project_id=project.id, source_file_id=file.id, parent_revision_id=project.current_revision_id, state=data.state)
    db.add(revision)
    db.flush()
    project.current_revision_id = revision.id
    project.name = data.name.strip()
    file.owner_id, file.expires_at = user.id, None
    for job in db.scalars(select(Job)):
        if (job.input.get('file_id') == file.id and (job.type == 'import' or job.id == drawing_id)) or job.id == cad_id:
            job.owner_id = user.id
            for artifact in db.scalars(select(Artifact).where(Artifact.job_id == job.id)):
                af = db.get(File, artifact.file_id)
                af.owner_id, af.expires_at = user.id, None
    db.commit()
    return project_summary(project)


@app.get('/api/revisions/{revision_id}')
def revision_read(revision_id: str, request: Request, db=Depends(db_session)):
    rev = db.get(Revision, revision_id)
    if not can_revision(request, db, rev):
        fail(404, 'Project not found or sharing was revoked.')
    project = db.get(Project, rev.project_id)
    file = db.get(File, rev.source_file_id)
    imported = db.get(Job, rev.state['cad_job_id']) if rev.state.get('cad_job_id') else next((j for j in db.scalars(select(Job).where(Job.type == 'import', Job.status == 'completed')) if j.input.get('file_id') == file.id), None)
    user = user_of(request, db)
    drawing = db.get(Job, rev.state.get('drawing_job_id', ''))
    return {'project': project_summary(project, rev.id), 'file': {'id': file.id, 'name': file.name, 'format': file.format}, 'state': rev.state, 'mesh': imported.result if imported else None, 'drawing': drawing.result if drawing else None, 'editable': bool(user and user.id == project.owner_id)}


@app.post('/api/projects/{project_id}/publish')
def publish(project_id: str, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    project = owned(db, Project, project_id, user)
    project.published_revision_id = project.current_revision_id
    db.commit()
    return {'revision_id': project.published_revision_id}


class ShareInput(Input):
    folder_id: str | None = None
    revision_id: str | None = None


@app.post('/api/shares')
def share_create(data: ShareInput, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    if bool(data.folder_id) == bool(data.revision_id):
        fail(422, 'Choose one folder or revision.')
    if data.folder_id:
        owned(db, Folder, data.folder_id, user)
    else:
        rev = db.get(Revision, data.revision_id)
        if not rev:
            fail(404, 'Revision not found.')
        owned(db, Project, rev.project_id, user)
    token = secrets.token_urlsafe(32)
    share = Share(owner_id=user.id, folder_id=data.folder_id, project_revision_id=data.revision_id, token=digest(token), expires_at=now() + timedelta(days=30))
    db.add(share)
    db.commit()
    return {'id': share.id, 'path': '/?share=' + token, 'expires_at': share.expires_at}


@app.get('/api/shares')
def shares(request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    return [{'id': s.id, 'folder_id': s.folder_id, 'revision_id': s.project_revision_id, 'expires_at': s.expires_at} for s in db.scalars(select(Share).where(Share.owner_id == user.id, Share.revoked_at.is_(None), Share.expires_at > now()))]


@app.delete('/api/shares/{share_id}')
def revoke(share_id: str, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    owned(db, Share, share_id, user).revoked_at = now()
    db.commit()
    return {'ok': True}


@app.get('/api/shared')
def shared(request: Request, db=Depends(db_session)):
    share = share_of(request, db)
    if not share:
        fail(404, 'This link has expired or was revoked.')
    if share.project_revision_id:
        rev = db.get(Revision, share.project_revision_id)
        return {'name': 'Shared project', 'folders': [], 'projects': [project_summary(db.get(Project, rev.project_id), rev.id)]}
    folders = list(db.scalars(select(Folder)))
    ids = [f.id for f in folders if share.folder_id in ancestors(db, f.id)]
    projects = db.scalars(select(Project).where(Project.folder_id.in_(ids), Project.published_revision_id.is_not(None)))
    return {'name': db.get(Folder, share.folder_id).name, 'folders': [{'id': f.id, 'name': f.name, 'parent_id': f.parent_id} for f in folders if f.id in ids], 'projects': [project_summary(p, p.published_revision_id) for p in projects]}


class Invite(Input):
    email: str = Field(min_length=3, max_length=254)


@app.post('/api/folders/{folder_id}/invites')
def invite(folder_id: str, data: Invite, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    owned(db, Folder, folder_id, user)
    token = secrets.token_urlsafe(32)
    obj = FolderInvite(folder_id=folder_id, email=data.email.lower().strip(), token=digest(token), expires_at=now() + timedelta(days=7))
    db.add(obj)
    db.commit()
    return {'path': '/?invite=' + token, 'id': obj.id}


@app.post('/api/invites/{token}/accept')
def accept(token: str, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    inv = db.scalar(select(FolderInvite).where(FolderInvite.token == digest(token), FolderInvite.email == user.email, FolderInvite.accepted_at.is_(None), FolderInvite.revoked_at.is_(None), FolderInvite.expires_at > now()))
    if not inv:
        fail(404, 'Invitation not found, expired, or for another email.')
    if not db.scalar(select(FolderMember.id).where(FolderMember.folder_id == inv.folder_id, FolderMember.user_id == user.id)):
        db.add(FolderMember(folder_id=inv.folder_id, user_id=user.id))
    inv.accepted_at = now()
    db.commit()
    return {'ok': True}


@app.get('/api/folders/{folder_id}/access')
def folder_access(folder_id: str, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    owned(db, Folder, folder_id, user)
    return {'members': [{'id': m.id, 'email': db.get(User, m.user_id).email} for m in db.scalars(select(FolderMember).where(FolderMember.folder_id == folder_id))], 'invites': [{'id': i.id, 'email': i.email} for i in db.scalars(select(FolderInvite).where(FolderInvite.folder_id == folder_id, FolderInvite.accepted_at.is_(None), FolderInvite.revoked_at.is_(None)))]}


@app.delete('/api/folders/{folder_id}/access/{access_id}')
def remove_access(folder_id: str, access_id: str, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    owned(db, Folder, folder_id, user)
    member, inv = db.get(FolderMember, access_id), db.get(FolderInvite, access_id)
    if member and member.folder_id == folder_id:
        db.delete(member)
    elif inv and inv.folder_id == folder_id:
        inv.revoked_at = now()
    else:
        fail(404, 'Access entry not found.')
    db.commit()
    return {'ok': True}


class Drawing(Input):
    file_id: str
    title: str = Field(min_length=1, max_length=80)
    material: str = Field(default='Unspecified', max_length=80)
    density_kg_m3: float = Field(gt=0, le=30000)
    show_hidden: bool = False
    notes: list[str] = Field(default_factory=list, max_length=10)


@app.post('/api/drawings')
def drawing(data: Drawing, request: Request, db=Depends(db_session)):
    user_of(request, db, True)
    file = read_file(request, db, data.file_id)
    if not own_file(request, db, file) or file.format not in ('step', 'stp'):
        fail(422, 'Open your own STEP file to generate a drawing.')
    if any(len(n) > 300 for n in data.notes):
        fail(422, 'Keep each drawing note under 300 characters.')
    return new_job(db, request, 'drawing', data.model_dump())


class ReviewInput(Input):
    revision_hash: str
    decision: Literal['approved', 'rejected']
    note: str = Field(min_length=1, max_length=1000)


@app.post('/api/jobs/{job_id}/review')
def review(job_id: str, data: ReviewInput, request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    job = own_job(request, db, job_id)
    if job.status != 'completed' or data.revision_hash != job.result.get('revision_hash'):
        fail(409, 'Review the current completed result first.')
    db.add(Review(job_id=job.id, revision_hash=data.revision_hash, stage=job.type, user_id=user.id, decision=data.decision, note=data.note))
    db.commit()
    return {'ok': True, 'pdf': job.result.get('pdf') if data.decision == 'approved' else None}


def entitled(request, db, capability):
    user = user_of(request, db, True)
    if not db.scalar(select(Entitlement.id).where(Entitlement.user_id == user.id, Entitlement.capability == capability, Entitlement.expires_at > now(), Entitlement.revoked_at.is_(None))):
        fail(402, 'This engineering service needs an active plan. Checkout is not available yet.')
    return user


class Cost(Input):
    estimate: dict
    previous_job_id: str | None = None


@app.post('/api/costing')
def costing(data: Cost, request: Request, db=Depends(db_session)):
    entitled(request, db, 'costing')
    if len(json.dumps(data.estimate)) > 100000 or 'gross_margin' not in data.estimate:
        fail(422, 'Provide explicit pricing assumptions and gross margin.')
    previous = None
    if data.previous_job_id:
        previous = own_job(request, db, data.previous_job_id)
        if previous.type != 'costing' or previous.status != 'completed':
            fail(422, 'Choose a completed estimate for comparison.')
    return new_job(db, request, 'costing', {'estimate': data.estimate, 'previous': previous.result if previous else None})


class Fixture(Input):
    file_id: str
    kind: Literal['weld', 'checking']
    construction: Literal['laser_rib', 'block', 'printed_solid']
    brief: str = Field(min_length=20, max_length=5000)


@app.post('/api/fixtures')
def fixture(data: Fixture, request: Request, db=Depends(db_session)):
    user = entitled(request, db, 'fixture')
    file = read_file(request, db, data.file_id)
    if not own_file(request, db, file) or file.format not in ('step', 'stp'):
        fail(422, 'A fixture needs your own STEP source.')
    if (data.kind == 'weld' and data.construction == 'printed_solid') or (data.kind == 'checking' and data.construction == 'block'):
        fail(422, 'That construction is not supported for this fixture type.')
    # A brief is not an engineered datum/spec. No automatic geometry is claimed here.
    job = Job(owner_id=user.id, type='fixture', status='awaiting_engineer', input=data.model_dump(), result={'stage': 'brief', 'message': 'Brief saved. Engineer-authored datum plan required before concept generation.'})
    db.add(job)
    db.commit()
    file.owner_id, file.expires_at = user.id, None
    db.commit()
    return {'id': job.id, 'status': job.status}


@app.get('/api/engineering')
def engineering(request: Request, db=Depends(db_session)):
    user = user_of(request, db, True)
    return [{'id': j.id, 'type': j.type, 'status': j.status, 'input': j.input, 'result': j.result} for j in db.scalars(select(Job).where(Job.owner_id == user.id, Job.type.in_(['fixture', 'costing'])).order_by(Job.created_at.desc()))]


from backend.google_login import router as google_router
app.include_router(google_router)
from backend.engineering_chat import router as chat_router
app.include_router(chat_router)


if Path('frontend/dist').exists():
    app.mount('/', StaticFiles(directory='frontend/dist', html=True), name='web')
