# Research basis and precedence

Derived from the user's Design Weld Fixture v8 practical rules and the checking-fixture proposal accepted in this conversation. The user explicitly established a 3 mm nominal gap with a 2.5 mm GO end and 3.5 mm NO-GO end. This is the controlling shop default. The bundled GH-201-B geometry and measured record are inherited from v8.

Public references consulted 2026-09-16 (not universal or current customer release specifications):

- Matcor-Matsu, Fixture Specification (2020): https://www.matcor-matsu.com/wp-content/uploads/2020/08/Matcor-Matsu-Fixture-Specification.pdf — includes 3 mm trim/surface gap practice and other gaps for some conditions.
- ABC Technologies, Checking Fixture/Gauge Standard (2020): https://abctechnologies.com/wp-content/uploads/80-ENG-D-413-Checking-Fixture_Gauge-Standard-0-10Jul2020.pdf — datum-based gauge intent, tolerance-based feelers, non-distorting clamps, physical certification and measurement-system evaluation. Its default gap and construction prescriptions differ from this shop; do not adopt them automatically.
- Formlabs, Jigs and Fixtures: https://formlabs.com/blog/jigs-and-fixtures/ — printed-tool construction and durable inserts.
- Formlabs, Accuracy/Precision/Tolerance: https://formlabs.com/blog/understanding-accuracy-precision-tolerance-in-3d-printing/ — resolution alone does not establish dimensional accuracy.
- ESI, printed inspection fixture example: https://www.esict.com/blog/watch-3d-printer-create-inspection-fixture/ — stamped-part locating fixtures, not proof of arbitrary printed gauge accuracy.

Follow explicit job/customer inspection requirements when supplied. Flag conflicts with shop defaults and distinguish shop screening from drawing acceptance. Do not silently invent or override tolerance/decision rules. Fetch the applicable current customer requirement when a job needs formal compliance; these background sources do not establish it.
