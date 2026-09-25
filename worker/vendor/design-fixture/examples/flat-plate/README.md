# Worked example: flat plate

A 160 × 100 × 6 mm demonstration plate located on 3-2-1 laser-cut ribs with one GH-201-B hold-down clamp. Run from the skill folder:

```bash
python examples/flat-plate/make_example.py
python scripts/build.py examples/flat-plate/spec.json OUT
python scripts/validate_delivery.py OUT/DELIVERY
```

The generator writes a measured example spec and workpiece STEP; the builder inserts the bundled fourteen-component GH-201-B in its supplied pose. The builder makes the complete review package, including CAD-derived assembled and empty views. Every upright is crossed by a 40 mm cross-halving brace (X1/X2, XS, XC, XK). The standard 60 × 50 mm mount cap has four M5 tap-drill holes and two cheek tabs. Its top is z=66 mm, level with the clamping surface; the 5 mm cap rests on 61 mm cheeks. The spec records proposed welded retention for the base ribs and upper mount joints, supports, the source transform, and intended planar face descriptors.

Expected: six contact checks pass, constraint rank six, no unintended plate/part penetration, reopened geometry matches the final plate profiles, and the delivery validates. Engineering status remains `unknown` and `fabrication_ready` remains false. Successful sampled fixture insertion does not certify a swept path.

Unresolved: verified spindle adjustment and clamp opening, positive lateral seating during welding, continuous fixture insertion, workpiece loading/unloading, actual weld access, weld strength, tolerances, distortion and trial validation. Proposed fixture weld sizes are example design inputs. The red clamp is actual supplied CAD in an unverified operating pose. The assembled view includes a side projection and measured mounting-height difference. A single flat plate does not exercise multi-piece weldment interaction; carry out a fresh survey for a different source.

The `preview/` folder contains the verified example review views. Rebuild them when changing the example.
