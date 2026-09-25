# Assembly locating and support roles

## Choose the strategy before drawing ribs

1. Identify loose workpieces, already joined subassemblies, weld references and purchased parts. Choose the functional master part and drawing datums; record assumptions when no drawing is supplied.
2. Describe the loading order. Determine which movements the fixture stops and which are stopped by a previously seated mating part. Common fixture ribs can carry different lands; their common construction does not itself make their contacts a common datum.
3. Use three non-collinear primary datum contacts where suitable. Treat extra contacts as additional constraints unless an actual adjustable/floating/relieved support makes them non-competing.
4. Prefer suitable existing holes and slots for in-plane secondary/tertiary location using [hole and slot locating](hole-slot-locating.md). Remove edge stops that duplicate the selected pin constraints. Where edge stops supply remaining constraints, default each secondary pair to the same side with inward normals in a common direction; stepped edges may require different offsets. Explain how the part seats into those stops.
5. Model the coupled assembly at each loading stage. Do not assume that six rows per part prove the assembly is neither overconstrained nor free to move. Mating contacts also constrain relative motion.
6. Check stock thickness, form variation, thermal movement and clamp seating. Never remove real contacts from the calculation merely to obtain full rank. Review contact area, friction assumptions, stiffness and actual mechanism separately.

The HUD failure pattern is a useful regression: three fixed primary supports on each of two overlapping sheets, plus their mating faces, can compete; opposing secondary stops can pass a per-part rank check yet have no common seating direction. The correction is a deliberate shared datum strategy, not a universal rule that all assemblies must have only three supports.

A round pin normally supplies two in-plane bearing directions, and a correctly oriented relieved pin supplies one. Do not count each pin as a single constraint or add a full edge-stop scheme alongside it. Verify these directions in the coupled loading-stage model; primary support and mating contacts still supply the remaining constraints.

## Spec fields

Fixture contacts retain their existing `part`, `rib`, `contact`, `normal`, `role` and intended-face descriptor. Add:

```json
{"constraint_role":"fixed_datum"}
```

For a genuine auxiliary support:

```json
{"constraint_role":"auxiliary_support", "support_mode":"adjustable_after_seating",
 "activation_sequence":"Seat both pieces on their datums; advance support to light contact and lock before applying the local clamp."}
```

Describe and model the adjustment or compliance. A permanently welded fixed-height land cannot satisfy this declaration by wording alone. A relieved land should have a measured clearance rather than a false zero-gap contact assertion; use the explicit CAD workflow for that support's clearance check.

Define the assembly plan:

```json
{
  "assembly_locating": {
    "master_part":"Lower",
    "datum_rationale":"Lower sheet establishes height; upper sheet seats on its overlap lands.",
    "mating_contacts":[
      {"name":"M1","part_a":"Upper","part_b":"Lower","contact":[-30,-20,63],
       "normal_on_a":[0,0,1],
       "face_a":{"type":"plane","point":[-30,-20,63],"outward_normal":[0,0,-1]},
       "face_b":{"type":"plane","point":[-30,-20,63],"outward_normal":[0,0,1]}}
    ],
    "loading_stages":[
      {"id":"load-lower","parts":["Lower"],
       "fixture_contacts":["LA1","LA2","LA3","LB1","LB2","LC1"],"mating_contacts":[],
       "seating_directions":{"Lower":{"Primary":[0,0,-1],"Secondary":[0,-1,0],"Tertiary":[-1,0,0]}}},
      {"id":"load-upper","parts":["Lower","Upper"],
       "fixture_contacts":["LA1","LA2","LA3","LB1","LB2","LC1","UB1","UB2","UC1"],
       "mating_contacts":["M1","M2","M3"],
       "seating_directions":{"Lower":{"Primary":[0,0,-1],"Secondary":[0,-1,0],"Tertiary":[-1,0,0]},
                             "Upper":{"Secondary":[0,-1,0],"Tertiary":[-1,0,0]}}}
    ]
  }
}
```

This is a schema excerpt, not a runnable design: define all fixture contacts and three actual non-collinear mating contacts M1–M3 on measured overlap material. Supply geometry, support loads and seating evidence for the selected design. Do not copy these coordinates into a different part.

Stage `parts` lists are cumulative. The final stage must include every loose workpiece and every declared fixed and mating contact. Stage contact IDs must be unique. `normal_on_a` is the inward contact normal on part A; B receives the opposite normal at the same nominal contact point. A clearance fit or curved/angled contact needs the appropriate explicit CAD verification; do not substitute a planar face descriptor to force approval.

A justified opposing-secondary arrangement requires `secondary_exceptions: {"PartId":{"reason":"...","seating_method":"..."}}`. This yields an exception, not a pass. Its staged seating model must remain mechanically valid; the default common-direction screen may be unsuitable, in which case use an explicit engineered workflow with honest unresolved status.

## Verification boundaries

The staged matrix has six columns per loaded body. Fixed fixture contacts affect one body; mating contacts couple two bodies. Report rank, required rank, redundant rows and contact IDs involved in dependencies. Independent per-part rank is only a diagnostic.

The script rejects redundant declared fixed rows conservatively: replace genuinely auxiliary constraints with a modeled support mechanism, or document a separate engineering analysis for deliberate overconstraint. A rank pass is not force closure or tolerance approval. Declared mating points must lie on both intended CAD faces. Missing mating-face evidence remains unknown. Undeclared physical contacts are not discovered automatically; survey them and resolve `assembly_tolerances` before fabrication approval.
