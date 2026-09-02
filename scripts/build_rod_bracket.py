"""Fusion 360 script: spool-rod bracket for the Ergotron LAN Organizer 3000.

Run inside Fusion via scripts/run_in_fusion.py. Builds one printable body in
a new unsaved parametric document and exports STL/STEP/F3D. Two variants:

- "bracket" (default): full bracket — slotted-upright hooks, triangulated
  cantilever arm, up-open saddle for the spool rod. Print two per rod.
- "gauge": just the hook plate. A ~20 minute print that verifies slot width,
  vertical pitch, column spacing, throat depth, and engagement on the real
  DuraFrame before committing to full brackets.

Geometry lives in the XZ plane (X forward from the upright face, Z up) and is
symmetric about Y=0, so every extrude is a full-length symmetric extent and
the same part serves left and right ends of the rod.

Measured on the desk (2026-09-02): slots ~3/4" tall and ~1/8" wide, on 1"
vertical pitch, two slot columns per upright ~1" apart. Slot width, column
spacing, and face metal thickness are the least certain numbers — that is
what the gauge print is for.
"""

import math

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are centimetres

# Assigned unconditionally: Fusion's interpreter persists globals between
# MCP executions, so a globals().get(...) default silently reuses the
# variant injected by a PREVIOUS run. run_in_fusion.py --variant overrides
# this by appending a reassignment AFTER the script text.
BUILD_VARIANT = "bracket"

PROJECT_DIR = "/Users/mhuot/lan-spool-shelf"

# --- Upright slot geometry (measured / to be confirmed by gauge) -----------
SLOT_HEIGHT = 19.05  # 3/4", measured
SLOT_PITCH_VERTICAL = 25.4  # 1" centre-to-centre, measured
SLOT_WIDTH = 3.2  # ~1/8", from photo — gauge print confirms
SLOT_COLUMN_SPACING = 25.4  # ~1" between the two columns — gauge confirms
FACE_METAL_THICKNESS = 2.0  # assumed — gauge confirms via throat fit

# --- Hook geometry ---------------------------------------------------------
HOOK_TAB_WIDTH = 2.4  # blade width through the slot (0.8 clearance)
HOOK_THROAT = FACE_METAL_THICKNESS + 0.8  # gap behind plate for the face metal
HOOK_NECK_HEIGHT = 5.0  # bears on the slot's bottom edge
HOOK_LIP_THICKNESS = 4.0
HOOK_LIP_DROP = 12.0  # engagement below the neck, behind the face
HOOK_ROWS = 3
# Insertion needs NECK + DROP < SLOT_HEIGHT - play; 5 + 12 = 17 < 19.05.

# --- Bracket body ----------------------------------------------------------
PLATE_THICKNESS = 6.0
PLATE_HEIGHT = 76.0
BRACKET_WIDTH = 40.0  # spans both slot columns at +/-12.7 with margin
GAUGE_PLATE_THICKNESS = 5.0
TOP_HOOK_NECK_TOP = 74.0  # top row 2 mm below the plate top

# --- Rod and saddle --------------------------------------------------------
ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC; edit for dowel etc.
SADDLE_CLEARANCE = 0.8  # diametral pocket clearance
SADDLE_WALL = 6.0
ROD_STANDOFF = 115.0  # rod axis forward of the upright face; a 200 mm
# spool hanging on the rod then clears the upright face by ~15 mm.
ROD_CENTER_Z = PLATE_HEIGHT  # rod axis level with the plate top

# --- Lightening cutout -----------------------------------------------------
MEMBER_WIDTH = 14.0  # structural border left around the triangular cutout
# There is no rod retainer: the saddle walls rise ~15 mm above the rod axis,
# the load only ever pushes down, and an open saddle is what lets the rod
# lift straight out for spool changes. Add velcro over the saddle if bumped.

EXPORT_NAME = {"bracket": "spool_rod_bracket", "gauge": "slot_gauge"}


def _value(millimetres):
    return adsk.core.ValueInput.createByReal(millimetres * MM)


def _point(x_mm, z_mm):
    """Sketch point on the XZ plane.

    On xZConstructionPlane the sketch x axis is model X but the sketch
    y axis is model MINUS Z (verified by probe failure: a +76 tall part
    landed at model z [-76, 0]). Negate v so callers think in model Z.
    """
    return adsk.core.Point3D.create(x_mm * MM, -z_mm * MM, 0)


def _add_polygon(sketch, points_mm):
    lines = sketch.sketchCurves.sketchLines
    count = len(points_mm)
    for index in range(count):
        start = _point(*points_mm[index])
        end = _point(*points_mm[(index + 1) % count])
        lines.addByTwoPoints(start, end)


def _extrude_all_profiles(component, sketch, width_mm, operation, name):
    """Symmetric full-length extrude of every profile in the sketch."""
    profiles = adsk.core.ObjectCollection.create()
    for index in range(sketch.profiles.count):
        profiles.add(sketch.profiles.item(index))
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(profiles, operation)
    extrude_input.setSymmetricExtent(_value(width_mm), True)
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


def _hook_row_tops():
    return [TOP_HOOK_NECK_TOP - row * SLOT_PITCH_VERTICAL for row in range(HOOK_ROWS)]


def _build_hooks(component, plane):
    """Two hook columns at +/- SLOT_COLUMN_SPACING/2, built sign-proof.

    Extrude direction signs on offset extents depend on the sketch plane's
    normal, so instead: join one symmetric slab spanning both columns, then
    cut the symmetric middle back out. What remains is exactly one tab per
    column, HOOK_TAB_WIDTH wide, centred at +/- SLOT_COLUMN_SPACING/2.
    """
    sketch = component.sketches.add(plane)
    sketch.name = "Hook profiles"
    back = -HOOK_THROAT
    lip_back = -(HOOK_THROAT + HOOK_LIP_THICKNESS)
    for neck_top in _hook_row_tops():
        neck_bottom = neck_top - HOOK_NECK_HEIGHT
        lip_bottom = neck_bottom - HOOK_LIP_DROP
        _add_polygon(
            sketch,
            [
                (0.0, neck_top),
                (lip_back, neck_top),
                (lip_back, lip_bottom),
                (back, lip_bottom),
                (back, neck_bottom),
                (0.0, neck_bottom),
            ],
        )
    _extrude_all_profiles(
        component,
        sketch,
        SLOT_COLUMN_SPACING + HOOK_TAB_WIDTH,
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
        "Hook slab",
    )
    _extrude_all_profiles(
        component,
        sketch,
        SLOT_COLUMN_SPACING - HOOK_TAB_WIDTH,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
        "Hook column split",
    )


def _inner_cutout_vertices():
    """Triangle cutout offset MEMBER_WIDTH inside plate/top/diagonal members."""
    inner_x = PLATE_THICKNESS + MEMBER_WIDTH - 6.0  # keep 14 total with plate
    inner_z = PLATE_HEIGHT - MEMBER_WIDTH
    # Hypotenuse runs from (0, 0) to (ROD_STANDOFF, PLATE_HEIGHT).
    length = math.hypot(ROD_STANDOFF, PLATE_HEIGHT)
    direction = (ROD_STANDOFF / length, PLATE_HEIGHT / length)
    normal = (-direction[1], direction[0])  # points up-left, into the part
    base = (MEMBER_WIDTH * normal[0], MEMBER_WIDTH * normal[1])
    slope = direction[1] / direction[0]
    # Offset hypotenuse as z = slope * (x - base_x) + base_z.
    z_at_inner_x = slope * (inner_x - base[0]) + base[1]
    x_at_inner_z = base[0] + (inner_z - base[1]) / slope
    if x_at_inner_z <= inner_x + 5.0:
        return None  # cutout would be degenerate; skip it
    return [
        (inner_x, z_at_inner_x),
        (inner_x, inner_z),
        (x_at_inner_z, inner_z),
    ]


def _build_bracket_body(component, plane):
    boss_radius = ROD_OUTER_DIAMETER / 2.0 + SADDLE_WALL
    pocket_radius = (ROD_OUTER_DIAMETER + SADDLE_CLEARANCE) / 2.0
    join = adsk.fusion.FeatureOperations.JoinFeatureOperation
    cut = adsk.fusion.FeatureOperations.CutFeatureOperation
    new_body = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    triangle = component.sketches.add(plane)
    triangle.name = "Arm triangle"
    _add_polygon(
        triangle,
        [(0.0, 0.0), (0.0, PLATE_HEIGHT), (ROD_STANDOFF, PLATE_HEIGHT)],
    )
    _extrude_all_profiles(component, triangle, BRACKET_WIDTH, new_body, "Arm triangle")

    plate = component.sketches.add(plane)
    plate.name = "Hook plate"
    _add_polygon(
        plate,
        [
            (0.0, 0.0),
            (PLATE_THICKNESS, 0.0),
            (PLATE_THICKNESS, PLATE_HEIGHT),
            (0.0, PLATE_HEIGHT),
        ],
    )
    _extrude_all_profiles(component, plate, BRACKET_WIDTH, join, "Hook plate")

    boss = component.sketches.add(plane)
    boss.name = "Saddle boss"
    boss.sketchCurves.sketchCircles.addByCenterRadius(
        _point(ROD_STANDOFF, ROD_CENTER_Z), boss_radius * MM
    )
    _extrude_all_profiles(component, boss, BRACKET_WIDTH, join, "Saddle boss")

    cutout_vertices = _inner_cutout_vertices()
    if cutout_vertices:
        cutout = component.sketches.add(plane)
        cutout.name = "Lightening cutout"
        _add_polygon(cutout, cutout_vertices)
        _extrude_all_profiles(
            component,
            cutout,
            BRACKET_WIDTH + 10.0,
            cut,
            "Lightening cutout",
        )

    pocket = component.sketches.add(plane)
    pocket.name = "Rod pocket"
    pocket.sketchCurves.sketchCircles.addByCenterRadius(
        _point(ROD_STANDOFF, ROD_CENTER_Z), pocket_radius * MM
    )
    _extrude_all_profiles(component, pocket, BRACKET_WIDTH + 10.0, cut, "Rod pocket")

    opening = component.sketches.add(plane)
    opening.name = "Rod drop-in opening"
    _add_polygon(
        opening,
        [
            (ROD_STANDOFF - pocket_radius, ROD_CENTER_Z),
            (ROD_STANDOFF + pocket_radius, ROD_CENTER_Z),
            (ROD_STANDOFF + pocket_radius, ROD_CENTER_Z + boss_radius + 5.0),
            (ROD_STANDOFF - pocket_radius, ROD_CENTER_Z + boss_radius + 5.0),
        ],
    )
    _extrude_all_profiles(
        component,
        opening,
        BRACKET_WIDTH + 10.0,
        cut,
        "Rod drop-in opening",
    )


def _build_gauge_body(component, plane):
    plate = component.sketches.add(plane)
    plate.name = "Gauge plate"
    _add_polygon(
        plate,
        [
            (0.0, 0.0),
            (GAUGE_PLATE_THICKNESS, 0.0),
            (GAUGE_PLATE_THICKNESS, PLATE_HEIGHT),
            (0.0, PLATE_HEIGHT),
        ],
    )
    _extrude_all_profiles(
        component,
        plate,
        BRACKET_WIDTH,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        "Gauge plate",
    )


def _probe(body, x_mm, y_mm, z_mm):
    point = adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z_mm * MM)
    return body.pointContainment(point)


def _verify(body):  # pylint: disable=too-many-locals
    """Numeric probes; raise on any surprise so the failure is loud."""
    inside = adsk.fusion.PointContainment.PointInsidePointContainment
    outside = adsk.fusion.PointContainment.PointOutsidePointContainment
    column = SLOT_COLUMN_SPACING / 2.0
    neck_top = _hook_row_tops()[0]
    lip_mid_z = neck_top - HOOK_NECK_HEIGHT - HOOK_LIP_DROP / 2.0
    lip_mid_x = -(HOOK_THROAT + HOOK_LIP_THICKNESS / 2.0)
    inner_tab_edge = column - HOOK_TAB_WIDTH
    outer_tab_edge = column + HOOK_TAB_WIDTH
    checks = [
        ("plate interior", 3.0, 0.0, 38.0, inside),
        ("top lip, +Y column", lip_mid_x, column, lip_mid_z, inside),
        ("top lip, -Y column", lip_mid_x, -column, lip_mid_z, inside),
        ("throat gap is open", -HOOK_THROAT / 2.0, column, lip_mid_z, outside),
        ("no hook between columns", lip_mid_x, 0.0, lip_mid_z, outside),
        ("no hook inboard of tab", lip_mid_x, inner_tab_edge, lip_mid_z, outside),
        ("no hook outboard of tab", lip_mid_x, outer_tab_edge, lip_mid_z, outside),
    ]
    if BUILD_VARIANT == "bracket":
        pocket_radius = (ROD_OUTER_DIAMETER + SADDLE_CLEARANCE) / 2.0
        boss_radius = ROD_OUTER_DIAMETER / 2.0 + SADDLE_WALL
        wall_mid = (pocket_radius + boss_radius) / 2.0
        checks += [
            ("rod pocket is empty", ROD_STANDOFF, 0.0, ROD_CENTER_Z, outside),
            (
                "drop-in opening is open",
                ROD_STANDOFF,
                0.0,
                ROD_CENTER_Z + boss_radius,
                outside,
            ),
            (
                "front saddle wall",
                ROD_STANDOFF + wall_mid,
                0.0,
                ROD_CENTER_Z,
                inside,
            ),
            (
                "rear saddle wall",
                ROD_STANDOFF - wall_mid,
                0.0,
                ROD_CENTER_Z,
                inside,
            ),
            ("lightening cutout", 45.0, 0.0, 55.0, outside),
            ("diagonal member", 30.0, 0.0, 25.0, inside),
            ("top member", 60.0, 0.0, PLATE_HEIGHT - 4.0, inside),
        ]
    failures = []
    for label, x_mm, y_mm, z_mm, expected in checks:
        actual = _probe(body, x_mm, y_mm, z_mm)
        state = "ok" if actual == expected else f"FAIL (got {actual})"
        print(f"  probe {label:34s} ({x_mm:7.1f},{y_mm:6.1f},{z_mm:6.1f}) {state}")
        if actual != expected:
            failures.append(label)
    if failures:
        raise RuntimeError(f"geometry probes failed: {failures}")


def _export(design, name):
    root = design.rootComponent
    export_manager = design.exportManager
    step_path = f"{PROJECT_DIR}/cad/{name}.step"
    archive_path = f"{PROJECT_DIR}/cad/{name}.f3d"
    stl_path = f"{PROJECT_DIR}/exports/{name}.stl"
    export_manager.execute(export_manager.createSTEPExportOptions(step_path, root))
    export_manager.execute(
        export_manager.createFusionArchiveExportOptions(archive_path, root)
    )
    stl_options = export_manager.createSTLExportOptions(root, stl_path)
    stl_options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    export_manager.execute(stl_options)
    print(f"exported {step_path}")
    print(f"exported {archive_path}")
    print(f"exported {stl_path}")


def run(_context: str):
    """Build the selected variant in a new document, verify, and export."""
    if BUILD_VARIANT not in EXPORT_NAME:
        raise ValueError(f"unknown BUILD_VARIANT {BUILD_VARIANT!r}")
    app = adsk.core.Application.get()
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    component = design.rootComponent
    plane = component.xZConstructionPlane

    if BUILD_VARIANT == "bracket":
        _build_bracket_body(component, plane)
    else:
        _build_gauge_body(component, plane)
    _build_hooks(component, plane)

    if component.bRepBodies.count != 1:
        names = [
            component.bRepBodies.item(i).name for i in range(component.bRepBodies.count)
        ]
        raise RuntimeError(f"expected one body, got {names}")
    body = component.bRepBodies.item(0)
    body.name = EXPORT_NAME[BUILD_VARIANT]

    bounding = body.boundingBox
    print(f"variant: {BUILD_VARIANT}")
    print(f"document: {document.name}")
    print(f"volume: {body.volume / (MM ** 3):.0f} mm^3")
    print(
        "bbox mm: "
        f"x [{bounding.minPoint.x / MM:.1f}, {bounding.maxPoint.x / MM:.1f}] "
        f"y [{bounding.minPoint.y / MM:.1f}, {bounding.maxPoint.y / MM:.1f}] "
        f"z [{bounding.minPoint.z / MM:.1f}, {bounding.maxPoint.z / MM:.1f}]"
    )
    _verify(body)
    _export(design, EXPORT_NAME[BUILD_VARIANT])
    print("build complete")
