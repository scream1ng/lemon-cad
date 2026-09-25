# LemonCAD on Railway

Researched 2026-09-25. Documentation research only: no account changes, deployment, CAD benchmark or Bixl implementation audit performed in this investigation.

## Decision

**Railway can host the proposed application, PostgreSQL, CAD workers and object storage.** File-format coverage and measurement quality are determined by the CAD software we integrate, not Railway. Reuse Bixl's OCP backend in an isolated LemonCAD deployment; verify builds and real-file performance before committing capacity.

Local evidence supplied by the parallel repository inspection: `/Users/oakky/Projects/bixl-studio/cad-service/Dockerfile` already uses Miniforge, Python 3.11, OCP and FastAPI/Uvicorn. Current mesh/measure endpoints receive a complete STEP file per request and delete temporary files afterward. This provides a deployable foundation, but repeated uploads/parsing should be replaced by bounded jobs and revision-based geometry reuse for LemonCAD. The existing Bixl production service should remain separate.

## Recommended launch architecture

| Component | Responsibility |
|---|---|
| Public web/API service | Built React/Vite assets plus FastAPI; login, project/folder APIs, access checks and job submission |
| Private CAD worker | Docker-packaged Python/OCP; STEP import, tessellation, geometry queries, draft drawings, later fixtures and costing |
| PostgreSQL | Accounts, folder hierarchy, membership, share tokens, projects, revisions, measurements and durable job state |
| Railway Bucket | Original files, generated meshes, drawing PDFs, previews and paid outputs |
| Scheduled cleanup | Expire anonymous uploads and abandoned temporary files; reconcile failed jobs |

Railway supports Dockerfile builds and persistent worker services. This makes native Python dependencies feasible without forcing CAD work into a browser or short-lived function. Deployment feasibility is not proof that the existing Bixl image works unchanged. [Dockerfiles](https://docs.railway.com/builds/dockerfiles), [compute types](https://docs.railway.com/build-deploy).

Keep API, worker and Postgres in one project/environment and use internal networking; services communicate through encrypted tunnels without public database/worker endpoints. Stage and production have isolated networks. [Private networking](https://docs.railway.com/networking/private-networking).

Three.js renders on the user's device; Railway delivers assets and geometry. A GPU server is not required for this proposed interactive viewer. Server-side PNG generation would be a separate implementation decision; browser PNG/PDF downloads can stay client-side.

## Uploads, saved folders and sharing

Railway Buckets are private S3-compatible storage supporting presigned URLs and multipart uploads. Recommend direct browser uploads with short-lived signed URLs, followed by server validation and queued processing. Bucket credentials must remain server-side. Do not route large downloads through the API unnecessarily. [Storage buckets](https://docs.railway.com/storage-buckets).

Folders are application records, not one bucket per folder. Store opaque object keys and revision metadata in Postgres. LemonCAD must implement account sessions, owner/viewer permissions, inherited folder access, invitation acceptance, revocable share links and checks before issuing each download URL. Railway infrastructure permissions do not implement LemonCAD customer permissions.

Short-lived download URLs can remain valid until expiry after folder access is removed. Immediate revocation requires an authenticated proxy; previously downloaded files cannot be recalled. Use immutable object keys for every revision and a database pointer to the published revision.

For anonymous STEP processing, the file reaches Railway. The UI must not claim that all files remain on the device. Recommend an explicit short retention period with scheduled deletion; only signed-in save actions create lasting project records.

## Jobs, limits and resilience

Use a durable queue: a Postgres-backed queue is a reasonable minimal option; Redis plus Celery is an alternative if workload demands it. Railway documents both queue patterns. Start with one CAD task per worker process, then measure memory and CPU before increasing concurrency. Add job leases, cancellation, bounded retries, deadlines and idempotent output writes. These are application responsibilities. [Workers and queues](https://docs.railway.com/guides/cron-workers-queues).

The public HTTP proxy closes requests after five idle minutes; actively transferring requests can run for up to 15 minutes. Upload bodies must finish within five minutes. Therefore return a job ID promptly and poll/subscribe for progress; do not hold a request open while generating a fixture. These are HTTP limits, not a blanket 15-minute worker-process limit. [Network limits](https://docs.railway.com/networking/public-networking/specs-and-limits).

Use per-job temporary directories and durable bucket outputs. Design for worker restarts and failed CAD imports. Maximum accepted STEP size, assembly count, processing time, tessellation density and simultaneous users remain **unbenchmarked**. Do not advertise a file-size guarantee from Railway's memory ceiling.

The plan page aggregates resource ceilings across replicas; the right-sizing guide describes per-replica limits. Verify the chosen service's actual replica controls before sizing. [Plan limits](https://docs.railway.com/pricing/plans), [right-sizing](https://docs.railway.com/guides/right-size-cpu-memory).

## Backups and production caveats

Railway's Postgres template is deployable with connection variables, but its documentation calls database templates unmanaged: configuration and maintenance remain our responsibility. Enable backups and test restores before storing customer projects. [PostgreSQL](https://docs.railway.com/databases/postgresql).

Railway documents volume snapshots, logical dumps and optional Postgres point-in-time recovery using WAL archiving to a Railway Bucket. PITR must be enabled and verified, not assumed present. [Backup/restore guide](https://docs.railway.com/guides/postgres-backups-restores).

Buckets currently list object versioning, object locks, lifecycle configuration and server-side encryption as unsupported. This is a meaningful consideration for confidential manufacturing files. Confirm the provider's exact at-rest protection before making security promises; application encryption is a separate option. Implement revision retention and deletion in LemonCAD. A Postgres backup alone does not back up CAD objects. [Bucket limitations](https://docs.railway.com/storage-buckets).

## Verified pricing, not a project quote

USD prices in the reviewed documentation:

| Item | Rate |
|---|---|
| Hobby / Pro monthly minimum | $5 / $20; credited toward usage |
| RAM | $10 per GB-month of consumption |
| CPU | $20 per vCPU-month of consumption |
| Service egress | $0.05 per GB |
| Persistent volumes | $0.15 per GB-month |
| Bucket storage | $0.015 per GB-month; bucket API operations and egress free |

Sources: [pricing](https://docs.railway.com/pricing), [bucket pricing](https://docs.railway.com/storage-buckets). Service-to-bucket uploads count as service egress. Idle worker memory still contributes to usage; exact monthly cost needs representative-file benchmarks and traffic assumptions. For example, 100 GB of bucket storage alone is $1.50/month, excluding compute, database, backups and service transfer.

Recommend Pro for a public production launch; Hobby can support evaluation. Set spend alerts and task quotas. Railway hard spending limits stop workloads, so they are a last-resort spend cap, not graceful application throttling. [Cost control](https://docs.railway.com/pricing/cost-control).

## File-format roadmap

| Scope | Candidate formats | Boundary |
|---|---|---|
| Launch | STEP/STP and STL | STEP geometry-based measurements; STL mesh measurements with explicit units |
| Next CAD formats | IGES/IGS, BREP | Existing OpenCascade import paths are available; validate our actual OCP implementation and files |
| Additional viewer formats | OBJ, GLTF/GLB, PLY, 3MF | Add and test appropriate loaders; viewing does not supply analytic CAD surfaces |
| Native commercial CAD | SLDPRT/SLDASM, IPT/IAM | Evaluate a licensed translator and Linux deployment support; not unlocked by Railway hosting |

The referenced occt-import-js project exposes STEP, IGES and BREP readers. Online3DViewer supports a broader mesh/viewer set; its list is not LemonCAD's implemented coverage. [occt-import-js](https://github.com/kovacsv/occt-import-js/blob/main/README.md), [Online3DViewer](https://github.com/kovacsv/Online3DViewer).

HOOPS Exchange is one potential native-file route: its documentation lists SolidWorks and Inventor readers and Linux runtimes. A commercial license, allowed hosted deployment terms, format/platform combinations and translation quality need separate validation. [Formats](https://docs.techsoft3d.com/hoops/exchange/start/supported-formats.html), [platforms](https://docs.techsoft3d.com/hoops/exchange/start/supported-platforms.html), [license requirement](https://docs.techsoft3d.com/hoops/access/topics/dataproviders/plugins/exchange.html).

## Next proof before implementation commitments

1. Containerize the existing STEP/OCP path and test representative simple, large, assembly and malformed inputs.
2. Record import duration, peak memory, tessellation size and dimension accuracy against reference CAD values.
3. Prove upload → job → mesh → selected-face measurement → PNG/PDF locally using the proposed service boundaries.
4. Verify folder inheritance/revocation and restore both metadata and objects in a test environment.
5. Use results to choose upload quotas, worker concurrency and initial operating budget.
