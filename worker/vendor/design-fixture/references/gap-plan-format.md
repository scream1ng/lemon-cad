# Gap-plan checker input

Run `python3 scripts/check_gap_plan.py PLAN.json`. Exit 0 means only the declared plan screen passed, 1 means malformed/inconsistent input, 2 means unresolved coverage or a requirement conflict. No status grants CAD or production approval.

Use this minimal example as a format illustration, not actual geometry or a sufficient station count for every flange:

```json
{
  "units": "mm",
  "construction": "laser_rib",
  "datum_scheme": "Proposed A support plane, B round hole, C relieved locator; no drawing supplied",
  "flanges": [{
    "id": "F01",
    "source_feature": "Measured body/face descriptor",
    "checks": [{
      "id": "F01-S1",
      "kind": "surface_gap",
      "scope": "Local surface position at this station only",
      "point_mm": [25, 10, 30],
      "direction": [1, 0, 0],
      "approach": "Gauge enters from above through the designed access window",
      "basis": "shop_standard",
      "drawing_conflict": false
    }]
  }]
}
```

Populate the inventory from the actual source. `construction` is `laser_rib` or `printed_solid`. Flange and station IDs must be unique. A flange may have `limitation`; that makes the screen unresolved. A flange without checks remains unresolved even if an exclusion is explained.

Gap kinds are `surface_gap` and `edge_gap`. Both need the nominal part `point_mm`, a unit `direction` from the part toward its checking land, `scope` and gauge `approach`. Omitted `nominal_gap_mm`, `go_mm`, `no_go_mm` use 3.0, 2.5, 3.5 respectively. Basis defaults to `shop_standard`; changed sizes require `job_override` and `override_source` identifying the actual customer/job instruction, not model preference. `drawing_conflict: true` and `conflict_note` preserve unresolved conflicts. Set false when no drawing exists, retaining the shop-standard basis rather than inventing drawing compliance.

For another technique, use `kind: "alternative"`, with `method`, `acceptance`, `scope`, `approach` and `drawing_conflict`. This records a proposed method only; the checker does not evaluate its technical validity.

Optional `observed_gap_mm` produces an ideal numerical screen, never an operator observation. Exact limits within a 1e-9 numerical comparison return `boundary_review`; this is a floating-point comparison convention, not a gauge manufacturing tolerance. Gauge calibration and the physical light-pressure insertion rule remain separate.

Store this input as top-level `inspection` in the build spec. `build_check.py` retains it in fixture-design.json and stores the screen outcome alongside measured stations in verification.json. Retain complete component and geometry evidence separately according to the delivery contract.
