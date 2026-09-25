"""Initial approved schema migration. Run explicitly before starting services."""
from sqlalchemy import text
from backend.db import Base, engine, GoogleIdentity

with engine.begin() as connection:
    connection.execute(text('SELECT pg_advisory_xact_lock(718924)'))
    connection.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamptz DEFAULT now())'))
    if not connection.execute(text('SELECT 1 FROM schema_migrations WHERE version = 1')).scalar():
        Base.metadata.create_all(connection)
        connection.execute(text('INSERT INTO schema_migrations(version) VALUES (1)'))
    if not connection.execute(text('SELECT 1 FROM schema_migrations WHERE version = 2')).scalar():
        GoogleIdentity.__table__.create(connection, checkfirst=True)
        connection.execute(text('INSERT INTO schema_migrations(version) VALUES (2)'))
print('Schema version 2 ready')
