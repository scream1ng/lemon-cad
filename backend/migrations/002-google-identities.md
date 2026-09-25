# 002 — Google account identities

Approved by the user on 2026-09-25. Adds `google_identities` only: UUID record ID, creation timestamp, unique `user_id` foreign key and unique Google `subject` string. Existing users, password hashes, sessions and files are unchanged.

Apply with `uv run python -m backend.migrate`. The migration holds the existing advisory lock and records version 2. Safe to rerun. No automatic account linking by email: existing users must sign in with their password and explicitly connect the Google identity.
