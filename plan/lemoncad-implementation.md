# LemonCAD implementation plan

## Scope and assumptions

- Build the agreed `lemoncad-product.html` design in this empty application workspace: centred 1280 px shell, drop-first home, approved lemon identity.
- New independent product. Reuse copies of the necessary Bixl geometry modules and skill resources; do not edit Bixl Studio, its database, or its running services.
- React + TypeScript + Vite + Three.js frontend; Python FastAPI API and OCP worker; PostgreSQL and S3-compatible storage. Railway deployment configuration for all services. Local development uses the same service contracts.
- STEP/STP and STL first. CAD measurements and draft drawings require validated CAD geometry. STL remains mesh-based with explicit unit selection.
- This approval covers creating and testing the initial application schema locally. Production provisioning, production migrations, billing activation and deployment are separate actions.

## Delivery sequence

1. **Anonymous vertical slice:** real file drop, STEP parsing/mesh generation, STL loading, camera controls, feature selection, dimensions and PNG/PDF export. Test before expanding.
2. **Free account workspace:** signup/login, private folders, save/reopen projects and model annotations, read-only folder sharing and revocation.
3. **Draft drawings:** adapt `draft-drawing` into queued jobs, review generated sheets, save settings, export the reviewed PDF, include drawings in shared projects.
4. **Engineering services:** paid entitlement checks, weld/check fixture job briefs and required datum/concept review stages; costing inputs, explicit rates/assumptions, calculator outputs and revision comparison. Preserve skill limits and review requirements.
5. **Deployment readiness:** separate Docker services, Railway configuration, cleanup, upload/job limits, backup instructions and operational documentation. Leave a tested local app running for review.

Paid pricing and checkout credentials are not decided. Build service interfaces and entitlement boundaries without inventing prices, charging users, exposing private IXL rates, or representing an unimplemented engineering workflow as complete. Report remaining commercial/configuration dependencies explicitly.

## Initial schema requiring approval

All IDs are UUIDs unless noted. Timestamps are timezone-aware. JSON columns hold revision-scoped CAD annotations/settings, not authorization rules.

| Table | Main fields / relationships |
|---|---|
| users | id, normalized unique email, password hash, created_at |
| sessions | hashed token, user_id, expires_at, revoked_at |
| folders | id, owner_id, parent_id nullable, name, timestamps |
| folder_members | folder_id, user_id, viewer role; unique membership |
| folder_invites | folder_id, normalized recipient email, hashed token, expiry, accepted_at, revoked_at |
| projects | id, owner_id, folder_id nullable, name, current_revision_id, published_revision_id, timestamps |
| project_revisions | id, project_id, source_file_id, parent_revision_id, camera/units/measurements/settings JSON, created_at |
| files | id, owner_id nullable, anonymous_session_hash nullable, opaque storage key, original name, format, size, source hash, expiry |
| shares | id, owner_id, folder_id or project_revision_id, hashed link token, expiry, revoked_at |
| jobs | id, owner/session reference, project_revision_id nullable, job type, status, input/result JSON, lease, attempts, cancellation, error, timestamps |
| artifacts | id, job_id, file_id, kind, source/settings revision reference |
| entitlements | id, user_id, fixture/costing capability, grant source, expiry/revocation |
| job_reviews | id, job_id, revision hash, review stage, user_id, decision, note, created_at |

Use migrations, foreign keys and ownership constraints. Anonymous files expire unless explicitly promoted to a saved project. Folder membership is checked through ancestry; moves cannot silently widen access. Shared folders expose published revisions; existing downloads cannot be recalled. Store CAD bytes in object storage, not Postgres.

## Files to create

- `frontend/`: real application, components, Three.js viewer, design CSS, logo assets, browser verification.
- `backend/`: API, models/migrations, auth/access checks, storage, job lifecycle and integration tests.
- `worker/`: isolated CAD and skill adapters, copied required resources with provenance, geometry and job tests.
- Root local service configuration, Dockerfiles/Railway configuration, dependency locks, environment example and README.
- Preserve `plan/`, `research/` and `DESIGN.md` as references; update only when implementation reveals a necessary documented decision.

## Verification / definition of done

- Known reference STEP parts produce expected diameters and distances; changing camera/tessellation does not change values.
- Invalid files, unknown STL units, import failures, cancellation and limits give actionable errors.
- PNG/PDF values and labels match the current viewer; no clipped annotations.
- Save → logout → login → reopen restores the actual part and dimensions.
- A second account cannot read private projects; folder viewer access works; revocation and source revision changes are enforced.
- Drawing preview/export use the same source and settings revision and list unsupported features.
- Engineering jobs preserve review gates, isolate failures and reject missing entitlements.
- Run existing tests accompanying reused modules and meaningful new integration tests. Stop and report a broken test; never skip it to pass.
- Exercise actual browser flows and leave the local development server running. Mockup interactions are not evidence that the real flow works.

## Approval basis

The user-provided AGENTS.md says: **“Large or risky → show plan, wait for approval”** and **“Schema changes: flag and ask, never silent.”** This is a new application with persistent accounts, shared folders and an initial database schema, so approval is requested for this concrete plan before implementation.
