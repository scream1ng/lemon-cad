# Explicitly authorized package stage

Load after user asks to finalize or explicitly requests a full package initially. This authorizes file generation, not engineering/fabrication approval. `workflow.py finalize` checks source/spec identity and rejects unsupported concept-only modes. Inspect reports/exact CAD, fix foreseeable defects, keep missing evidence unknown.

Read [evidence](evidence.md) for the `engineering_checks`, construction/pin and `checking_evidence` record schemas.

- Weld ribs: `build.py` + `validate_base_delivery.py`; read [base contract](output-contract.md).
- Checking ribs/printed: `build_check.py` + `validate_delivery.py`; read [checking delivery](verification-delivery.md). Checking validation extends the base; never substitute the base alone.
- Weld blocks: [block construction](block-construction.md), explicit exact CAD, drawings/manufacturing details and mode applicability evidence. Rib automation cannot manufacture blocks. The gate returns `manual_block_finalization_required`: continue with explicit CAD, not a completed package claim. Preserve four records, actual hardware, named assembly STEP and two PNGs; record irrelevant-DXF exception; run `validate_base_delivery.py --allow-no-dxf DELIVERY`. Required check applicability needs evidence; do not silently pass unsupported checks. Additional exports require hashes/scoped validation. Never use printed manufacturing files for metal blocks.

Rib package: one DXF, assembly STEP, two PNGs, four JSON records. Printed checking includes reopened/hash-verified print meshes and no inapplicable steel DXF. HTML/scene/project index stay separate working artifacts. Maintain distinct `cad_verified`, `fabrication_ready`, `fixture_calibrated`, `inspection_validated`. Exit 0 means complete review package; inspect status/open items. Calibration/inspection validation require physical evidence, not just files or CAD.
