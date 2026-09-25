# Block construction override

Read this only when the user explicitly requests blocks, machined blocks, or block-style construction.

- Preserve the same locating, support, clamping, access, and verification logic as the default workflow.
- Replace laser-cut rib geometry with practical blocks, pins, buttons, nests, risers, or welded/machined supports suited to the specified workshop processes.
- Define material, stock size, machining datums, mounting, retention, adjustment, and replaceable wear items within the requested scope.
- Do not copy the 5 mm sheet, tab-and-slot, two-tab, or 10 mm rib-profile rules into this mode.
- Do not move functional contacts merely to simplify a block. Derive the block around the measured contact and reaction path.
- Plain visual blocks remain conceptual until their fastening, tolerances, machining, access, and load path are defined.
- If a DXF is not relevant to a block fixture, explain the exception and deliver the requested manufacturing drawing or model format instead. After explicit package authorization, record the exception and validate with `scripts/validate_base_delivery.py --allow-no-dxf <DELIVERY directory>`.

For exact concept evaluation, `block_bodies` accepts named single-solid entries with `stock` box `{type: "box", origin: [x,y,z], size: [dx,dy,dz]}`, optional `add`/`subtract` box or cylinder features, or a `finished_step` path instead of primitives. These feed the shared OCP solid helper, not a printed manufacturing workflow. Clamp entries in this mode use a measured rigid `mount_transform`. Final machining/fastening/tolerance details remain explicit CAD work, not automatic rib tabs or print settings.
