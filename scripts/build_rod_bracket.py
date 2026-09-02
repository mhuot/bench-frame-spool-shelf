"""Fusion 360 script: spool cradle bracket for the Ergotron LAN Organizer 3000.

Run inside Fusion via scripts/run_in_fusion.py. Builds one printable body in
a new unsaved parametric document and exports STL/STEP/F3D. Three variants:

- "bracket" (default): full cradle bracket — slotted-upright hooks and a
  cantilever arm carrying TWO up-open saddles. Two parallel rods span
  between a pair of brackets and spools rest in the valley between the
  rods, so any spool lifts straight out (and can roll as filament feeds)
  without ever touching the rods. Print two per shelf level.
- "gauge": just the hook plate. A ~20 minute print that verifies slot
  width, vertical pitch, column spacing, throat depth, and engagement on
  the real DuraFrame before committing to full brackets.
- "coupon": a thin slice of the two-saddle arm tip (no hooks). Verifies the
  rod pocket diameter, drop-in opening, and rod spacing against the real
  pipe/dowel for a few grams of plastic.

Geometry lives in the XZ plane (X forward from the upright face, Z up) and is
symmetric about Y=0, so every extrude is a full-length symmetric extent and
the same part serves left and right ends of the rods.

Measured on the desk (2026-09-02): slots ~3/4" tall and ~1/8" wide, on 1"
vertical pitch. Each upright carries ONE slot column; what looks like a
double track in photos is the two joined frames' uprights sitting side by
side at the 60" module's centre. The hooks are therefore a single column on
the bracket centreline, so the same bracket works on centre and outside
uprights alike. Slot width and face metal thickness are the least certain
numbers — that is what the gauge print is for.
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
FACE_METAL_THICKNESS = 2.0  # assumed — gauge confirms via throat fit

# --- Hook geometry ---------------------------------------------------------
# A single column of hook blades on the bracket centreline: each upright has
# only one slot column (the "double track" is just the two joined frames'
# columns meeting at the module centre), and a one-column bracket mounts on
# any of them. Four rows because that lone column carries the whole moment.
HOOK_TAB_WIDTH = 2.4  # blade width through the slot (0.8 clearance)
HOOK_THROAT = FACE_METAL_THICKNESS + 0.8  # gap behind plate for the face metal
HOOK_NECK_HEIGHT = 5.0  # bears on the slot's bottom edge
HOOK_LIP_THICKNESS = 4.5
HOOK_LIP_DROP = 12.0  # engagement below the neck, behind the face
HOOK_ROWS = 4
# Insertion needs NECK + DROP < SLOT_HEIGHT - play; 5 + 12 = 17 < 19.05.

# --- Bracket body ----------------------------------------------------------
PLATE_THICKNESS = 6.0
PLATE_HEIGHT = 90.0  # spans the 4 hook rows; also the arm/rod height
# 24 wide: seats on a single rail face and stays inside the 25.4 mm gap
# between the two columns at the module centre, so brackets can mount in
# both bays at the same height. The rod pair braces the assembled frame
# against twist, so the narrow plate costs nothing structurally.
BRACKET_WIDTH = 24.0
GAUGE_PLATE_THICKNESS = 5.0
COUPON_WIDTH = 8.0
TOP_HOOK_NECK_TOP = 88.0  # top row 2 mm below the plate top

# --- Rods and saddles ------------------------------------------------------
ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC; edit for dowel etc.
SADDLE_CLEARANCE = 0.8  # diametral pocket clearance
SADDLE_WALL = 6.0
REAR_ROD_STANDOFF = 70.0  # rear rod axis forward of the upright face
ROD_SPACING = 80.0  # centre-to-centre between the two rods
# A 200 mm spool resting on both rods sits at a ~20 degree contact
# half-angle, its centre midway between the rods, so its rearmost point
# clears the upright face by (REAR_ROD_STANDOFF + ROD_SPACING/2 - 100).
FRONT_ROD_STANDOFF = REAR_ROD_STANDOFF + ROD_SPACING
ROD_STANDOFFS = (REAR_ROD_STANDOFF, FRONT_ROD_STANDOFF)
ROD_CENTER_Z = PLATE_HEIGHT  # both rod axes level with the plate top
# No rod retainer: spools press the rods down into the saddles and are
# lifted off the rods, never with them, so nothing ever pulls a rod up.

# --- Lightening cutout -----------------------------------------------------
MEMBER_WIDTH = 14.0  # structural border left around the cutout

EXPORT_NAME = {
    "bracket": "spool_cradle_bracket",
    "gauge": "slot_gauge",
    "coupon": "saddle_coupon",
}


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


def _boss_radius():
    return ROD_OUTER_DIAMETER / 2.0 + SADDLE_WALL


def _pocket_radius():
    return (ROD_OUTER_DIAMETER + SADDLE_CLEARANCE) / 2.0


def _build_hooks(component, plane):
    """One column of hook blades on the centreline (y = 0).

    A single symmetric extrude of HOOK_TAB_WIDTH is inherently centred, so
    no extent-direction signs are involved at all.
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
        HOOK_TAB_WIDTH,
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
        "Hook column",
    )


def _add_saddles(component, plane, width_mm):
    """Join a boss and cut a pocket plus drop-in opening at each rod axis."""
    join = adsk.fusion.FeatureOperations.JoinFeatureOperation
    cut = adsk.fusion.FeatureOperations.CutFeatureOperation
    for rod_x in ROD_STANDOFFS:
        boss = component.sketches.add(plane)
        boss.name = f"Saddle boss x={rod_x:.0f}"
        boss.sketchCurves.sketchCircles.addByCenterRadius(
            _point(rod_x, ROD_CENTER_Z), _boss_radius() * MM
        )
        _extrude_all_profiles(component, boss, width_mm, join, boss.name)
    for rod_x in ROD_STANDOFFS:
        pocket = component.sketches.add(plane)
        pocket.name = f"Rod pocket x={rod_x:.0f}"
        pocket.sketchCurves.sketchCircles.addByCenterRadius(
            _point(rod_x, ROD_CENTER_Z), _pocket_radius() * MM
        )
        _extrude_all_profiles(component, pocket, width_mm + 10.0, cut, pocket.name)
        opening = component.sketches.add(plane)
        opening.name = f"Drop-in opening x={rod_x:.0f}"
        _add_polygon(
            opening,
            [
                (rod_x - _pocket_radius(), ROD_CENTER_Z),
                (rod_x + _pocket_radius(), ROD_CENTER_Z),
                (rod_x + _pocket_radius(), ROD_CENTER_Z + _boss_radius() + 5.0),
                (rod_x - _pocket_radius(), ROD_CENTER_Z + _boss_radius() + 5.0),
            ],
        )
        _extrude_all_profiles(component, opening, width_mm + 10.0, cut, opening.name)


def _diagonal_offset_z(x_mm):
    """Z of the hypotenuse offset MEMBER_WIDTH into the part, at x_mm.

    The hypotenuse runs from (0, 0) to (FRONT_ROD_STANDOFF, PLATE_HEIGHT).
    """
    length = math.hypot(FRONT_ROD_STANDOFF, PLATE_HEIGHT)
    direction = (FRONT_ROD_STANDOFF / length, PLATE_HEIGHT / length)
    normal = (-direction[1], direction[0])  # points up-left, into the part
    base = (MEMBER_WIDTH * normal[0], MEMBER_WIDTH * normal[1])
    slope = direction[1] / direction[0]
    return slope * (x_mm - base[0]) + base[1]


def _inner_cutout_vertices():
    """Cutout inside the plate/top/diagonal members, stopping short of the
    rear saddle boss so the boss keeps MEMBER_WIDTH-ish of web around it."""
    inner_x = PLATE_THICKNESS + MEMBER_WIDTH - 6.0  # keep 14 total with plate
    inner_z = PLATE_HEIGHT - MEMBER_WIDTH
    max_x = REAR_ROD_STANDOFF - _boss_radius() - 10.0
    if max_x <= inner_x + 5.0:
        return None  # cutout would be degenerate; skip it
    z_left = _diagonal_offset_z(inner_x)
    z_right = _diagonal_offset_z(max_x)
    if z_right >= inner_z:
        return None
    return [
        (inner_x, z_left),
        (inner_x, inner_z),
        (max_x, inner_z),
        (max_x, z_right),
    ]


def _build_bracket_body(component, plane):
    join = adsk.fusion.FeatureOperations.JoinFeatureOperation
    cut = adsk.fusion.FeatureOperations.CutFeatureOperation
    new_body = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    triangle = component.sketches.add(plane)
    triangle.name = "Arm triangle"
    _add_polygon(
        triangle,
        [(0.0, 0.0), (0.0, PLATE_HEIGHT), (FRONT_ROD_STANDOFF, PLATE_HEIGHT)],
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

    _add_saddles(component, plane, BRACKET_WIDTH)


def _build_coupon_body(component, plane):
    """Thin slice of the two-saddle arm tip: a chord joining both bosses."""
    chord = component.sketches.add(plane)
    chord.name = "Coupon chord"
    _add_polygon(
        chord,
        [
            (REAR_ROD_STANDOFF, PLATE_HEIGHT - MEMBER_WIDTH),
            (FRONT_ROD_STANDOFF, PLATE_HEIGHT - MEMBER_WIDTH),
            (FRONT_ROD_STANDOFF, PLATE_HEIGHT),
            (REAR_ROD_STANDOFF, PLATE_HEIGHT),
        ],
    )
    _extrude_all_profiles(
        component,
        chord,
        COUPON_WIDTH,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        "Coupon chord",
    )
    _add_saddles(component, plane, COUPON_WIDTH)


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


def _hook_checks(inside, outside):
    lip_mid_z_rows = [
        top - HOOK_NECK_HEIGHT - HOOK_LIP_DROP / 2.0 for top in _hook_row_tops()
    ]
    lip_mid_x = -(HOOK_THROAT + HOOK_LIP_THICKNESS / 2.0)
    beside_tab = HOOK_TAB_WIDTH  # clear of the +/- HOOK_TAB_WIDTH/2 blade
    checks = [("plate interior", 3.0, 0.0, 38.0, inside)]
    for row, lip_mid_z in enumerate(lip_mid_z_rows):
        checks.append((f"row {row} lip", lip_mid_x, 0.0, lip_mid_z, inside))
    top_lip_z = lip_mid_z_rows[0]
    checks += [
        ("throat gap is open", -HOOK_THROAT / 2.0, 0.0, top_lip_z, outside),
        ("no hook beside blade +Y", lip_mid_x, beside_tab, top_lip_z, outside),
        ("no hook beside blade -Y", lip_mid_x, -beside_tab, top_lip_z, outside),
    ]
    return checks


def _saddle_checks(inside, outside):
    wall_mid = (_pocket_radius() + _boss_radius()) / 2.0
    floor_mid_z = ROD_CENTER_Z - (_pocket_radius() + _boss_radius()) / 2.0
    checks = []
    for label, rod_x in (("rear", REAR_ROD_STANDOFF), ("front", FRONT_ROD_STANDOFF)):
        checks += [
            (f"{label} pocket is empty", rod_x, 0.0, ROD_CENTER_Z, outside),
            (
                f"{label} opening is open",
                rod_x,
                0.0,
                ROD_CENTER_Z + _boss_radius(),
                outside,
            ),
            (f"{label} fore wall", rod_x + wall_mid, 0.0, ROD_CENTER_Z, inside),
            (f"{label} aft wall", rod_x - wall_mid, 0.0, ROD_CENTER_Z, inside),
            (f"{label} pocket floor", rod_x, 0.0, floor_mid_z, inside),
        ]
    between_bays = (REAR_ROD_STANDOFF + FRONT_ROD_STANDOFF) / 2.0
    checks.append(
        ("chord between saddles", between_bays, 0.0, PLATE_HEIGHT - 6.0, inside)
    )
    return checks


def _verify(body):
    """Numeric probes; raise on any surprise so the failure is loud."""
    inside = adsk.fusion.PointContainment.PointInsidePointContainment
    outside = adsk.fusion.PointContainment.PointOutsidePointContainment
    checks = []
    if BUILD_VARIANT in ("bracket", "gauge"):
        checks += _hook_checks(inside, outside)
    if BUILD_VARIANT in ("bracket", "coupon"):
        checks += _saddle_checks(inside, outside)
    if BUILD_VARIANT == "bracket":
        checks += [
            ("lightening cutout", 25.0, 0.0, 45.0, outside),
            ("diagonal member", 30.0, 0.0, 22.0, inside),
            ("top member near plate", 25.0, 0.0, PLATE_HEIGHT - 4.0, inside),
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
        _build_hooks(component, plane)
    elif BUILD_VARIANT == "coupon":
        _build_coupon_body(component, plane)
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
