# Resumable record: fixture-project-1

`spec.json` is the single executable design authority using the inherited mode schema. Generated `project.json` is an index, not a second geometry definition. It stores version, project/revision, fixture kind, construction, mm units, frame, source paths/SHA-256, placed CAD hash, geometry digest, stable IDs, decisions, open items, evidence, workflow stage and separate readiness states.

Use `spec.decisions`, `spec.open_items`, `engineering_checks`, and checking-only `checking_evidence`. Preserve plate/body names, clamp tags, contact/workpiece IDs across revisions; new IDs are added and retired IDs retained, not recycled. Source occurrence IDs are stable for unchanged imports, not promised across re-exports; reconcile on re-survey.

```bash
python scripts/workflow.py init spec.json project.json --kind checking
python scripts/workflow.py resume spec.json project.json
python scripts/spec_patch.py spec.json '{"revision":"R2","plates":{"R1":{"outer":[[0,0],[80,0],[80,40],[0,40]]}}}'
python scripts/workflow.py checkpoint spec.json project.json
python scripts/workflow.py concept spec.json project.json WORK/concept
python scripts/workflow.py revise spec.json project.json WORK/concept --build "python tools/make.py ." --verify "python tools/verify.py"
python scripts/workflow.py authorize spec.json project.json --request "Please finalize the full package"
python scripts/workflow.py finalize spec.json project.json WORK/final
```

The agent interprets actual user intent; this is not a keyword authorization classifier. `authorize` stores the actual request against current spec/source fingerprint. Never invent consent. Any spec revision invalidates authorization. `--complete-package-request` on init records an explicit initial full-package request and permits end-to-end after concept. Changed source requires re-survey; `checkpoint --resurveyed` attests that work. A `checkpoint` to a new revision keeps the datum review while contacts, locating groups, clamps, frame and sources are unchanged (fixture-body fields — contact `rib`, clamp `hardware`/`mount_plate`/`arm_direction`/hole pattern — are ignored, see `workflow.BODY_FIELDS`); any datum change (or `--resurveyed`) needs a fresh review. Exception: `source_geometry` (per-source STEP solid fingerprint — names, volume, area, centroid, bbox, face count — backfilled on the first matching resume) lets an unauthorized resume rebase a byte-only change (re-export) with identical solids; sources and digests update, a current datum review carries over, and `history` logs `rebased_sources`. Version mismatch fails closed, requiring explicit migration/rebuild.

Geometry digest excludes manual engineering/checking evidence to avoid circular hashes; authorization still binds the whole spec/evidence state. Readiness remains false until final reports justify it. Physical calibration/inspection status is never inferred from CAD.
