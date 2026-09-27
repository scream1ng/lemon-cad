# SOLIDWORKS direct sketch and dimension workflow

Research date: 2026-09-27. Primary sources only. Recommendations below are LemonCAD design decisions, not claims that all SOLIDWORKS behavior is implemented.

## Findings

| Interaction | Official behavior | LemonCAD implication |
| --- | --- | --- |
| Start on a face | Select a **planar** model face, then Sketch or a sketch entity tool. The sketch appears directly on the face while drawing; an optional grid and editing status identify the active sketch. [Sketching on the Face of a Part](https://help.solidworks.com/2026/english/SolidWorks/sldworks/t_Sketching_on_the_Face_of_a_Part.htm?id=28.0.3) | Make the model viewport the drawing surface. Keep the left card for properties. Curved faces need a suitable planar reference. |
| Rough shape first | The documented sequence is plane/face, sketch geometry, dimensions and relations, then a feature. Approximate geometry can be dimensioned precisely afterward. [Sketching Concepts Overview](https://help.solidworks.com/2020/English/SolidWorks/acadhelp/t_Sketching_Concepts_Overview.htm) | Do not require coordinate entry before drawing. |
| Context properties | Selecting a line opens its properties: relations, status, length/angle, and optional endpoint coordinates. Rectangle properties expose shape variants, construction lines, relations and coordinates. [Line Properties](https://help.solidworks.com/2025/english/solidworks/sldworks/HIDD_DVE_SKETCH_LINE.htm), [Rectangle PropertyManager](https://help.solidworks.com/2025/english/SolidWorks/sldworks/HIDD_DVE_SKETCH_RECTANGLES.htm) | Show only the selected tool/entity settings on the left; keep precise coordinate fields secondary. |
| Smart Dimension | Activate the tool, select geometry, then place the dimension. A line gives length, circle circumference gives diameter, two lines can give distance/angle, and two points give distance. Placement can determine the dimension orientation/type. [Dimensioning a 2D Sketch](https://help.solidworks.com/2026/english/SolidWorks/sldworks/t_Dimensioning_a_2D_Sketch.htm?id=28.19.1.0) | A viewport annotation must resize supported sketch geometry, not merely measure the solid. |
| Edit a size | Instant2D allows clicking the dimension value and typing its replacement, or dragging dimension handles. [Modifying a 2D Sketch Dimension with Instant2D](https://help.solidworks.com/2017/English/solidworks/sldworks/t_Modifying_2D_Sketch_Dimension_Instant2D.htm) | Put the numeric editor near the selected dimension; update the sketch immediately. |
| Extrude | Create/select a sketch, choose an extrusion tool, set feature properties, then confirm. A graphics-area manipulator can set depth. The PropertyManager supports depth, direction, end condition and selected contours. [Creating an Extrude Feature](https://help.solidworks.com/2023/english/SolidWorks/sldworks/t_creating_an_extrude_feature.htm), [Extrude PropertyManager](https://help.solidworks.com/2018/english/solidworks/sldworks/r_extrude_propertymanager.htm) | Keep Extrude available while sketching a valid closed profile; show a 3D preview, depth field and clear accept/cancel. |

## Driving dimensions are more than measurement labels

SOLIDWORKS treats dimensions and geometric relations as constraints. Under-defined entities retain freedom; fully defined entities have their size and position fixed. Redundant driving dimensions can over-define a sketch and may instead be made driven/reference dimensions. Importantly, a sketch **does not have to be fully defined to create a feature**. [Sketch States](https://help.solidworks.com/2022/english/solidworks/acadhelp/c_Sketch_States_AcadHelp.htm), [Inserting Driven Dimensions](https://help.solidworks.com/2024/English/SolidWorks/Sldworks/t_Inserting_Reference_Dimensions.htm)

For LemonCAD's first implementation, changing a rectangle's width/height or a circle's diameter can directly update existing saved parameters. This is useful driving-size editing, but it is not a general constraint solver. Polygon length/angle constraints, coincident/tangent/equal relations, constraint conflict reporting, and fully-defined status need a separate design and persisted constraint model. Do not display a misleading “Fully defined” status or silently convert read-only measurements into driving constraints.

## Recommended first workflow

1. Select planar face → Sketch. Orient normal to the face and retain the surrounding part as context.
2. Use the top sketch toolbar to draw Rectangle (two corners), Circle (center/radius), or a connected Line profile directly in the viewport. Left card: compact properties only.
3. Choose Smart Dimension → select rectangle edge or circle → place annotation → enter size. Keep position editable using existing sketch coordinates initially.
4. Select Extrude → depth/direction and model preview → accept. Closed polygon profiles remain drawable/extrudable, but arbitrary polygon constraint solving is outside this slice.
5. Escape cancels the current drawing action; explicit Cancel restores the pre-edit document and camera. Keep sketch interaction separate from orbit and solid measurement.

These are product recommendations derived from the documented workflow. They do not require copying SOLIDWORKS's entire PropertyManager or adding all of its tool options at once.

## Official visual references

- [Introducing SOLIDWORKS PDF, pages 102–104](https://files.solidworks.com/pdf/introsw.pdf#page=102): rectangle dimensions, Modify value entry, and the extrusion sequence. The document's indexed images/text describe the graphics-area dimension placement and depth manipulation; this is a workflow reference, not evidence of the current release's visual styling.
- [SOLIDWORKS Education 2025, Introduction to Sketching](https://www.solidworks.com/sites/default/filesd10/2025-04/SOLIDWORKS_Fundamentals_3D_Design_Simulation.pdf): page 47 explains geometry-dependent Smart Dimension with sketch/relation illustrations.
- [Face sketch help illustrations](https://help.solidworks.com/2018/english/solidworks/sldworks/t_Sketching_on_the_Face_of_a_Part.htm): sketch visible on the actual part face, then a sketch on another face.

Some direct help-page opens returned the navigation shell; their primary-source search-index content supplied the cited instructions. PDF screenshot calls did not provide a usable image payload in this session, so no claim is made that a current complete SOLIDWORKS screen was visually inspected. No app code changed.
