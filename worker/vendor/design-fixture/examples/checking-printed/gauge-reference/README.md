# Printed checking gauge — reference build (unsupported)

Job-specific scripts from one accepted printed checking gauge (Part_0009, revision P8). Not a supported
builder: base extents, hand slots, CMM windows, pin foot height and the part name are hard-coded for that part.
Copy into a job's `tools/`, adapt, and verify every station/contact with exact OCP — never reuse its numbers.

- `make_gauge.py` — manifold3d build: part offset 3 mm swept +z inside the outline, net pads and clamp
  pedestals merged into one SURFACE body, outward flange posts, D6 dowel holes for ground pins, flat BASE,
  2 D6 dowels + M5 insert/bolt joints per body; writes faceted STEP + STL and `geometry/gauge_bodies.json`.
- `verify_gauge.py` — station gap along d, datum contact, part interference, faces < 2.99 mm off the pads,
  body/body, REF pin and clamp hardware clashes.

Adapt without reading the whole script: `cp` both into `tools/`, then edit only these (find with `grep -n`):

- `make_gauge.py`: `Part_0009` (part name), `BX, BY` (base extents), `PIN_FOOT`, `BASE_Z`, hand slots (`s * 272`),
  `CMM` bush positions.
- `verify_gauge.py`: `Part_0009`.

Both find the skill at `~/.claude/skills/design-fixture`; set `DESIGN_FIXTURE_DIR` if it is installed elsewhere.

Everything else reads `spec.json` and the hardware record. Open a section only when a verify line fails there.

Needs `manifold3d` (not in `scripts/requirements.txt`).
