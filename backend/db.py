import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, DateTime, ForeignKey, JSON, Integer, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Record, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str]


class GoogleIdentity(Record, Base):
    __tablename__ = 'google_identities'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), unique=True)
    subject: Mapped[str] = mapped_column(String(255), unique=True)


class Session(Base):
    __tablename__ = 'sessions'
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Folder(Record, Base):
    __tablename__ = 'folders'
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey('folders.id'))
    name: Mapped[str] = mapped_column(String(100))


class FolderMember(Record, Base):
    __tablename__ = 'folder_members'
    __table_args__ = (UniqueConstraint('folder_id', 'user_id'),)
    folder_id: Mapped[str] = mapped_column(ForeignKey('folders.id'))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    role: Mapped[str] = mapped_column(default='viewer')


class FolderInvite(Record, Base):
    __tablename__ = 'folder_invites'
    folder_id: Mapped[str] = mapped_column(ForeignKey('folders.id'))
    email: Mapped[str]
    token: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class File(Record, Base):
    __tablename__ = 'files'
    owner_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    anonymous_session_hash: Mapped[str | None]
    storage_key: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    format: Mapped[str]
    size: Mapped[int]
    sha256: Mapped[str]
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(Record, Base):
    __tablename__ = 'projects'
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    folder_id: Mapped[str | None] = mapped_column(ForeignKey('folders.id'))
    name: Mapped[str]
    current_revision_id: Mapped[str | None] = mapped_column(ForeignKey('project_revisions.id', use_alter=True, name='project_current_fk'))
    published_revision_id: Mapped[str | None] = mapped_column(ForeignKey('project_revisions.id', use_alter=True, name='project_published_fk'))


class Revision(Record, Base):
    __tablename__ = 'project_revisions'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'))
    source_file_id: Mapped[str] = mapped_column(ForeignKey('files.id'))
    parent_revision_id: Mapped[str | None] = mapped_column(ForeignKey('project_revisions.id'))
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class Share(Record, Base):
    __tablename__ = 'shares'
    __table_args__ = (CheckConstraint('(folder_id IS NULL) <> (project_revision_id IS NULL)', name='share_one_target'),)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    folder_id: Mapped[str | None] = mapped_column(ForeignKey('folders.id'))
    project_revision_id: Mapped[str | None] = mapped_column(ForeignKey('project_revisions.id'))
    token: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(Record, Base):
    __tablename__ = 'jobs'
    owner_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    anonymous_session_hash: Mapped[str | None]
    project_revision_id: Mapped[str | None] = mapped_column(ForeignKey('project_revisions.id'))
    type: Mapped[str]
    status: Mapped[str] = mapped_column(default='queued', index=True)
    input: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None]
    lease: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0)


class Artifact(Record, Base):
    __tablename__ = 'artifacts'
    job_id: Mapped[str] = mapped_column(ForeignKey('jobs.id'))
    file_id: Mapped[str] = mapped_column(ForeignKey('files.id'))
    kind: Mapped[str]
    revision_hash: Mapped[str]


class Entitlement(Record, Base):
    __tablename__ = 'entitlements'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    capability: Mapped[str]
    grant: Mapped[str]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(Record, Base):
    __tablename__ = 'job_reviews'
    job_id: Mapped[str] = mapped_column(ForeignKey('jobs.id'))
    revision_hash: Mapped[str]
    stage: Mapped[str]
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    decision: Mapped[str]
    note: Mapped[str]


url = os.environ.get('DATABASE_URL', 'postgresql+psycopg://lemon:lemon@127.0.0.1:55438/lemoncad')
if url.startswith('postgres://') or url.startswith('postgresql://'):
    url = 'postgresql+psycopg://' + url.split('://', 1)[1]
engine = create_engine(url, pool_pre_ping=True)
DB = sessionmaker(engine, expire_on_commit=False)
