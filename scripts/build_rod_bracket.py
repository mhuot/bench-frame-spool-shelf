"""Fusion 360 script: spool cradle bracket for the Ergotron LAN Organizer 3000.

Run inside Fusion via scripts/run_in_fusion.py. Builds one printable body
into a saved, versioned document in the "LAN Spool Shelf" cloud project and
exports STL/STEP/F3D. Three variants:

- "bracket" (default): slotted-upright hooks and a cantilever arm carrying
  TWO up-open saddles. Two rods span between a pair of brackets and spools
  rest in the valley between them, so any spool lifts straight out. Print
  two per shelf level.
- "gauge": the hook plate alone. A ~20 minute print that verifies the slot
  fit on the real DuraFrame before committing to full brackets.
- "coupon": a thin slice of the two-saddle arm tip, to check rod pocket
  diameter and rod spacing against the real pipe.

EVERY dimension is parameter driven, with real units: lengths in mm, angles
in deg, counts unitless. Each variant declares only the parameters it uses,
and the build fails if any declared parameter drives no geometry or carries
the wrong unit — see _audit_parameters. That check exists because a whole
generation of these documents shipped with two thirds of their parameters
inert, including an angle Fusion had quietly stored in millimetres.

Geometry lives in the XZ plane (X forward from the upright face, Z up) and
is symmetric about Y=0, so the same bracket serves both ends of the rods.

Slot geometry measured on the desk and confirmed by gauge prints: 3/4" tall
slots on 1" pitch, ~1/8" wide, one column per upright.
"""

import datetime
import math

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are centimetres

# Assigned unconditionally: Fusion's interpreter persists globals between MCP
# executions, so globals().get(...) would reuse a PREVIOUS run's variant.
# run_in_fusion.py --variant appends a reassignment AFTER this script text.
BUILD_VARIANT = "bracket"

PROJECT_DIR = "/Users/mhuot/lan-spool-shelf"
FUSION_PROJECT_NAME = "LAN Spool Shelf"

# --- Measurements that are not model dimensions -----------------------------
# These describe the upright, not the part. SLOT_WIDTH drives hookTabWidth
# below; SLOT_HEIGHT is the insertion budget the assertion at the bottom of
# this block checks. Neither is a user parameter, because a parameter that
# drives nothing is a comment pretending to be a control.
SLOT_HEIGHT = 19.05  # 3/4", measured
SLOT_WIDTH = 3.2  # ~1/8", confirmed by the gauge print

# --- Dimensions: mm unless the name says otherwise --------------------------
SLOT_PITCH_VERTICAL = 25.4  # 1" centre-to-centre, measured
FACE_METAL_THICKNESS = 2.0
HOOK_TAB_WIDTH = SLOT_WIDTH - 0.8  # blade, 0.8 narrower than the slot
HOOK_THROAT = FACE_METAL_THICKNESS + 1.8  # widened after the first gauge
HOOK_NECK_HEIGHT = 5.0
HOOK_LIP_THICKNESS = 4.5
HOOK_LIP_DROP = 12.0
HOOK_LIP_CHAMFER = 1.5
HOOK_ROWS = 4
assert HOOK_NECK_HEIGHT + HOOK_LIP_DROP < SLOT_HEIGHT - 1.0, "hook will not enter"

PLATE_THICKNESS = 6.0
PLATE_HEIGHT = 90.0
BRACKET_WIDTH = 24.0  # fits inside the 25.4 gap between centre-upright columns
GAUGE_PLATE_THICKNESS = 5.0
COUPON_WIDTH = 8.0
TOP_HOOK_NECK_TOP = PLATE_HEIGHT - 2.0

ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC
SADDLE_CLEARANCE = 0.8
SADDLE_WALL = 6.0
REAR_ROD_STANDOFF = 70.0
ROD_SPACING = 80.0
FRONT_ROD_STANDOFF = REAR_ROD_STANDOFF + ROD_SPACING
ROD_STANDOFFS = (REAR_ROD_STANDOFF, FRONT_ROD_STANDOFF)
ROD_CENTER_Z = PLATE_HEIGHT
MEMBER_WIDTH = 14.0

EXPORT_NAME = {
    "bracket": "spool_cradle_bracket",
    "gauge": "slot_gauge",
    "coupon": "saddle_coupon",
}
DOC_NAME = {
    "bracket": "Spool Cradle Bracket",
    "gauge": "Slot Gauge",
    "coupon": "Saddle Coupon",
}

# --- Parameter expressions shared by the sketches ---------------------------
FRONT = "(rearRodStandoff + rodSpacing)"
BOSS_DIAMETER = "rodOuterDiameter + 2 * saddleWall"
POCKET_DIAMETER = "rodOuterDiameter + saddleClearance"
BOSS_RADIUS = ROD_OUTER_DIAMETER / 2.0 + SADDLE_WALL
POCKET_RADIUS = (ROD_OUTER_DIAMETER + SADDLE_CLEARANCE) / 2.0
DIAGONAL_LENGTH = f"sqrt({FRONT} * {FRONT} + plateHeight * plateHeight)"

# name: (value or expression, unit, comment). Order is creation order, so an
# expression may only reference names declared above it.
_HOOK_PARAMETERS = {
    "slotWidth": (SLOT_WIDTH, "mm", "measured slot width in the upright"),
    "slotPitchVertical": (SLOT_PITCH_VERTICAL, "mm", "1 inch, measured"),
    "faceMetalThickness": (FACE_METAL_THICKNESS, "mm", "upright face metal"),
    "hookTabWidth": ("slotWidth - 0.8 mm", "mm", "blade width through the slot"),
    "hookThroat": ("faceMetalThickness + 1.8 mm", "mm", "gap behind the plate"),
    "hookNeckHeight": (HOOK_NECK_HEIGHT, "mm", "bears on the slot bottom edge"),
    "hookLipThickness": (HOOK_LIP_THICKNESS, "mm", "lip thickness behind the face"),
    "hookLipDrop": (HOOK_LIP_DROP, "mm", "engagement below the neck"),
    "hookLipChamfer": (HOOK_LIP_CHAMFER, "mm", "lead-in past slot burrs"),
    "topHookNeckTop": (TOP_HOOK_NECK_TOP, "mm", "top row, below the plate top"),
    "hookRows": (str(HOOK_ROWS), "", "number of hook rows (pattern count)"),
}
_SADDLE_PARAMETERS = {
    "rodOuterDiameter": (ROD_OUTER_DIAMETER, "mm", "1 inch sch 40 PVC"),
    "saddleClearance": (SADDLE_CLEARANCE, "mm", "diametral pocket clearance"),
    "saddleWall": (SADDLE_WALL, "mm", "wall around the rod pocket"),
    "rearRodStandoff": (REAR_ROD_STANDOFF, "mm", "rear rod, from the upright"),
    "rodSpacing": (ROD_SPACING, "mm", "rod centres, front minus rear"),
}
PARAMETERS_BY_VARIANT = {
    "bracket": {
        "bracketWidth": (BRACKET_WIDTH, "mm", "bracket width along the rods"),
        "plateThickness": (PLATE_THICKNESS, "mm", "hook plate thickness"),
        "plateHeight": (PLATE_HEIGHT, "mm", "plate height, also the rod height"),
        **_HOOK_PARAMETERS,
        **_SADDLE_PARAMETERS,
        "memberWidth": (MEMBER_WIDTH, "mm", "border around the lightening cutout"),
    },
    "gauge": {
        "bracketWidth": (BRACKET_WIDTH, "mm", "gauge width, as the bracket"),
        "gaugePlateThickness": (GAUGE_PLATE_THICKNESS, "mm", "gauge plate"),
        "plateHeight": (PLATE_HEIGHT, "mm", "plate height"),
        **_HOOK_PARAMETERS,
    },
    "coupon": {
        "couponWidth": (COUPON_WIDTH, "mm", "coupon slice width"),
        "plateHeight": (PLATE_HEIGHT, "mm", "rod height, as the bracket"),
        **_SADDLE_PARAMETERS,
        "memberWidth": (MEMBER_WIDTH, "mm", "chord depth joining the saddles"),
    },
}


def parameters():
    """The parameter table for the variant being built."""
    return PARAMETERS_BY_VARIANT[BUILD_VARIANT]


def _point(x_mm, z_mm):
    """Sketch point on the XZ plane (sketch +y is model MINUS Z)."""
    return adsk.core.Point3D.create(x_mm * MM, -z_mm * MM, 0)


def _polyline(sketch, points_mm):
    """Closed polygon whose consecutive lines share sketch points."""
    lines = sketch.sketchCurves.sketchLines
    made = [lines.addByTwoPoints(_point(*points_mm[0]), _point(*points_mm[1]))]
    for target in points_mm[2:]:
        made.append(lines.addByTwoPoints(made[-1].endSketchPoint, _point(*target)))
    made.append(lines.addByTwoPoints(made[-1].endSketchPoint, made[0].startSketchPoint))
    return made


# pylint: disable-next=too-many-locals
def _pin_corners(sketch, lines, corners):
    """Dimension each corner's X and Z off the origin, by expression.

    Unsigned distance dimensions cannot express a negative coordinate, and
    offset/angular dimensions leave the solver free to mirror a profile, so
    every corner here must sit at positive X and Z.
    """
    horizontal = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    vertical = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    dimensions = sketch.sketchDimensions
    for index, (x_mm, z_mm, x_expression, z_expression) in enumerate(corners):
        if x_mm < 0 or z_mm < 0:
            raise RuntimeError(f"corner ({x_mm}, {z_mm}) is not in the +X +Z quadrant")
        point = lines[index].startSketchPoint
        for orientation, expression, text in (
            (horizontal, x_expression, (x_mm * 0.5, z_mm - 5.0 - index * 3.0)),
            (vertical, z_expression, (x_mm + 6.0 + index * 3.0, z_mm * 0.5)),
        ):
            if expression is None:
                continue
            dimension = dimensions.addDistanceDimension(
                sketch.originPoint, point, orientation, _point(*text)
            )
            dimension.parameter.expression = expression


def _extrude(component, profiles_list, width_expression, operation, name):
    """Symmetric extrude of the given profiles, width from an expression."""
    profiles = adsk.core.ObjectCollection.create()
    for profile in profiles_list:
        profiles.add(profile)
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(profiles, operation)
    extrude_input.setSymmetricExtent(
        adsk.core.ValueInput.createByString(width_expression), True
    )
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


def _all_profiles(sketch):
    return [sketch.profiles.item(i) for i in range(sketch.profiles.count)]


def _ensure_parameters(design):
    """Create or update this variant's user parameters, with their units."""
    user_parameters = design.userParameters
    for name, (value, unit, comment) in parameters().items():
        expression = value if isinstance(value, str) else f"{value} {unit}".strip()
        if isinstance(value, str) and unit and not any(c.isalpha() for c in value):
            expression = f"{value} {unit}"
        existing = user_parameters.itemByName(name)
        if existing:
            existing.expression = expression
            existing.comment = comment
        else:
            user_parameters.add(
                name,
                adsk.core.ValueInput.createByString(expression),
                unit,
                comment,
            )


def _hook_row_tops():
    return [TOP_HOOK_NECK_TOP - row * SLOT_PITCH_VERTICAL for row in range(HOOK_ROWS)]


# pylint: disable-next=too-many-locals
def _build_hooks(component, plane):
    """One constrained hook profile, extruded and patterned down the plate."""
    sketch = component.sketches.add(plane)
    sketch.name = "Hook profile"
    neck_top = TOP_HOOK_NECK_TOP
    neck_bottom = neck_top - HOOK_NECK_HEIGHT
    lip_bottom = neck_bottom - HOOK_LIP_DROP
    back = -HOOK_THROAT
    lip_back = -(HOOK_THROAT + HOOK_LIP_THICKNESS)
    lines = _polyline(
        sketch,
        [
            (0.0, neck_top),
            (lip_back, neck_top),
            (lip_back, lip_bottom),
            (back - HOOK_LIP_CHAMFER, lip_bottom),
            (back, lip_bottom + HOOK_LIP_CHAMFER),
            (back, neck_bottom),
            (0.0, neck_bottom),
        ],
    )
    # pylint: disable-next=unbalanced-tuple-unpacking
    top, rear, bottom, chamfer, inner, neck, face = lines
    constraints = sketch.geometricConstraints
    for line in (top, bottom, neck):
        constraints.addHorizontal(line)
    for line in (rear, inner, face):
        constraints.addVertical(line)
    constraints.addCoincident(sketch.originPoint, face)
    horizontal = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    vertical = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    dimensions = sketch.sketchDimensions

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def dimension(point_a, point_b, orientation, expression, text_x, text_z):
        item = dimensions.addDistanceDimension(
            point_a, point_b, orientation, _point(text_x, text_z)
        )
        item.parameter.expression = expression

    mid_neck = (neck_top + neck_bottom) / 2.0
    dimension(
        sketch.originPoint,
        top.startSketchPoint,
        vertical,
        "topHookNeckTop",
        6.0,
        neck_top / 2.0,
    )
    dimension(
        top.startSketchPoint,
        top.endSketchPoint,
        horizontal,
        "hookThroat + hookLipThickness",
        -4.0,
        neck_top + 5.0,
    )
    dimension(
        neck.endSketchPoint,
        neck.startSketchPoint,
        horizontal,
        "hookThroat",
        -2.0,
        neck_bottom - 3.0,
    )
    dimension(
        top.startSketchPoint,
        neck.endSketchPoint,
        vertical,
        "hookNeckHeight",
        3.0,
        mid_neck,
    )
    dimension(
        inner.endSketchPoint,
        inner.startSketchPoint,
        vertical,
        "hookLipDrop - hookLipChamfer",
        -10.0,
        (neck_bottom + lip_bottom) / 2.0,
    )
    dimension(
        chamfer.startSketchPoint,
        chamfer.endSketchPoint,
        horizontal,
        "hookLipChamfer",
        -4.0,
        lip_bottom - 3.0,
    )
    dimension(
        chamfer.startSketchPoint,
        chamfer.endSketchPoint,
        vertical,
        "hookLipChamfer",
        -9.0,
        lip_bottom + 3.0,
    )
    extrude = _extrude(
        component,
        _all_profiles(sketch),
        "hookTabWidth",
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
        "Hook profile",
    )
    pattern_entities = adsk.core.ObjectCollection.create()
    pattern_entities.add(extrude)
    patterns = component.features.rectangularPatternFeatures
    pattern_input = patterns.createInput(
        pattern_entities,
        component.zConstructionAxis,
        adsk.core.ValueInput.createByString("hookRows"),
        adsk.core.ValueInput.createByString("-slotPitchVertical"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType,
    )
    patterns.add(pattern_input).name = "Hook rows"


def _build_plate(component, plane, thickness_name, thickness_value, operation):
    """The flat plate the hooks hang off, dimensioned by two parameters."""
    sketch = component.sketches.add(plane)
    sketch.name = "Plate"
    # Horizontal/vertical constraints plus the origin leave exactly two
    # degrees of freedom, so exactly two dimensions may be applied.
    corners = [
        (0.0, 0.0, None, None),
        (thickness_value, 0.0, None, None),
        (thickness_value, PLATE_HEIGHT, thickness_name, "plateHeight"),
        (0.0, PLATE_HEIGHT, None, None),
    ]
    lines = _polyline(sketch, [(x, z) for x, z, _, _ in corners])
    constraints = sketch.geometricConstraints
    constraints.addCoincident(lines[0].startSketchPoint, sketch.originPoint)
    for line in (lines[0], lines[2]):
        constraints.addHorizontal(line)
    for line in (lines[1], lines[3]):
        constraints.addVertical(line)
    _pin_corners(sketch, lines, corners)
    _extrude(component, _all_profiles(sketch), "bracketWidth", operation, "Plate")


def _build_arm(component, plane):
    """The cantilever triangle, from the plate out to the front rod."""
    sketch = component.sketches.add(plane)
    sketch.name = "Arm triangle"
    corners = [
        (0.0, 0.0, None, None),
        (0.0, PLATE_HEIGHT, None, "plateHeight"),
        (FRONT_ROD_STANDOFF, PLATE_HEIGHT, FRONT, None),
    ]
    lines = _polyline(sketch, [(x, z) for x, z, _, _ in corners])
    constraints = sketch.geometricConstraints
    constraints.addCoincident(lines[0].startSketchPoint, sketch.originPoint)
    constraints.addVertical(lines[0])
    constraints.addHorizontal(lines[1])
    _pin_corners(sketch, lines, corners)
    _extrude(
        component,
        _all_profiles(sketch),
        "bracketWidth",
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        "Arm triangle",
    )


def _saddle_centre_expressions():
    return (("rearRodStandoff", REAR_ROD_STANDOFF), (FRONT, FRONT_ROD_STANDOFF))


def _dimension_circle(sketch, circle, diameter_expression, x_expression, x_mm):
    """Pin a circle's centre off the origin and drive its diameter."""
    horizontal = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    vertical = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    dimensions = sketch.sketchDimensions
    centre = circle.centerSketchPoint
    dimensions.addDistanceDimension(
        sketch.originPoint, centre, horizontal, _point(x_mm * 0.5, ROD_CENTER_Z + 8.0)
    ).parameter.expression = x_expression
    dimensions.addDistanceDimension(
        sketch.originPoint, centre, vertical, _point(x_mm + 10.0, ROD_CENTER_Z * 0.5)
    ).parameter.expression = "plateHeight"
    dimensions.addDiameterDimension(
        circle, _point(x_mm + 6.0, ROD_CENTER_Z + 14.0)
    ).parameter.expression = diameter_expression


# pylint: disable-next=too-many-locals
def _add_saddles(component, plane, width_expression):
    """Boss, pocket and drop-in opening at each rod axis."""
    join = adsk.fusion.FeatureOperations.JoinFeatureOperation
    cut = adsk.fusion.FeatureOperations.CutFeatureOperation
    for x_expression, x_mm in _saddle_centre_expressions():
        sketch = component.sketches.add(plane)
        sketch.name = f"Saddle boss x={x_mm:.0f}"
        circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
            _point(x_mm, ROD_CENTER_Z), BOSS_RADIUS * MM
        )
        _dimension_circle(sketch, circle, BOSS_DIAMETER, x_expression, x_mm)
        _extrude(component, _all_profiles(sketch), width_expression, join, sketch.name)

    for x_expression, x_mm in _saddle_centre_expressions():
        sketch = component.sketches.add(plane)
        sketch.name = f"Rod pocket x={x_mm:.0f}"
        circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
            _point(x_mm, ROD_CENTER_Z), POCKET_RADIUS * MM
        )
        _dimension_circle(sketch, circle, POCKET_DIAMETER, x_expression, x_mm)
        _extrude(
            component,
            _all_profiles(sketch),
            f"{width_expression} + 10 mm",
            cut,
            sketch.name,
        )

        opening = component.sketches.add(plane)
        opening.name = f"Drop-in opening x={x_mm:.0f}"
        top_z = ROD_CENTER_Z + BOSS_RADIUS + 5.0
        left = x_mm - POCKET_RADIUS
        right = x_mm + POCKET_RADIUS
        left_expression = f"{x_expression} - ({POCKET_DIAMETER}) / 2"
        right_expression = f"{x_expression} + ({POCKET_DIAMETER}) / 2"
        top_expression = f"plateHeight + ({BOSS_DIAMETER}) / 2 + 5 mm"
        corners = [
            (left, ROD_CENTER_Z, left_expression, "plateHeight"),
            (right, ROD_CENTER_Z, None, None),
            (right, top_z, right_expression, top_expression),
            (left, top_z, None, None),
        ]
        lines = _polyline(opening, [(x, z) for x, z, _, _ in corners])
        constraints = opening.geometricConstraints
        for line in (lines[0], lines[2]):
            constraints.addHorizontal(line)
        for line in (lines[1], lines[3]):
            constraints.addVertical(line)
        _pin_corners(opening, lines, corners)
        _extrude(
            component,
            _all_profiles(opening),
            f"{width_expression} + 10 mm",
            cut,
            opening.name,
        )


def _diagonal_offset(x_mm):
    """Z of the hypotenuse offset memberWidth into the part, at x_mm."""
    length = math.hypot(FRONT_ROD_STANDOFF, PLATE_HEIGHT)
    base_x = -MEMBER_WIDTH * PLATE_HEIGHT / length
    base_z = MEMBER_WIDTH * FRONT_ROD_STANDOFF / length
    slope = PLATE_HEIGHT / FRONT_ROD_STANDOFF
    return slope * (x_mm - base_x) + base_z


def _diagonal_offset_expression(x_expression):
    base_x = f"(-memberWidth * plateHeight / {DIAGONAL_LENGTH})"
    base_z = f"(memberWidth * {FRONT} / {DIAGONAL_LENGTH})"
    return f"plateHeight / {FRONT} * (({x_expression}) - {base_x}) + {base_z}"


def _build_cutout(component, plane):
    """Lightening cutout: inset from plate, top member and the diagonal."""
    inner_x_expression = "memberWidth"
    inner_x = MEMBER_WIDTH
    top_z_expression = "plateHeight - memberWidth"
    top_z = PLATE_HEIGHT - MEMBER_WIDTH
    outer_x_expression = f"rearRodStandoff - ({BOSS_DIAMETER}) / 2 - 10 mm"
    outer_x = REAR_ROD_STANDOFF - BOSS_RADIUS - 10.0
    corners = [
        (
            inner_x,
            _diagonal_offset(inner_x),
            inner_x_expression,
            _diagonal_offset_expression(inner_x_expression),
        ),
        (inner_x, top_z, None, top_z_expression),
        (outer_x, top_z, outer_x_expression, None),
        (
            outer_x,
            _diagonal_offset(outer_x),
            None,
            _diagonal_offset_expression(outer_x_expression),
        ),
    ]
    if outer_x <= inner_x + 5.0 or _diagonal_offset(outer_x) >= top_z:
        raise RuntimeError("lightening cutout would be degenerate")
    sketch = component.sketches.add(plane)
    sketch.name = "Lightening cutout"
    lines = _polyline(sketch, [(x, z) for x, z, _, _ in corners])
    sketch.geometricConstraints.addVertical(lines[0])
    sketch.geometricConstraints.addHorizontal(lines[1])
    sketch.geometricConstraints.addVertical(lines[2])
    _pin_corners(sketch, lines, corners)
    _extrude(
        component,
        _all_profiles(sketch),
        "bracketWidth + 10 mm",
        adsk.fusion.FeatureOperations.CutFeatureOperation,
        "Lightening cutout",
    )


def _build_bracket(component, plane):
    _build_arm(component, plane)
    _build_plate(
        component,
        plane,
        "plateThickness",
        PLATE_THICKNESS,
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
    )
    _build_cutout(component, plane)
    _add_saddles(component, plane, "bracketWidth")
    _build_hooks(component, plane)


def _build_gauge(component, plane):
    _build_plate(
        component,
        plane,
        "gaugePlateThickness",
        GAUGE_PLATE_THICKNESS,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    _build_hooks(component, plane)


def _build_coupon(component, plane):
    """Thin slice of the arm tip: a chord joining both saddle bosses."""
    sketch = component.sketches.add(plane)
    sketch.name = "Coupon chord"
    bottom_z = PLATE_HEIGHT - MEMBER_WIDTH
    bottom_expression = "plateHeight - memberWidth"
    corners = [
        (REAR_ROD_STANDOFF, bottom_z, "rearRodStandoff", bottom_expression),
        (FRONT_ROD_STANDOFF, bottom_z, None, None),
        (FRONT_ROD_STANDOFF, PLATE_HEIGHT, FRONT, "plateHeight"),
        (REAR_ROD_STANDOFF, PLATE_HEIGHT, None, None),
    ]
    lines = _polyline(sketch, [(x, z) for x, z, _, _ in corners])
    constraints = sketch.geometricConstraints
    for line in (lines[0], lines[2]):
        constraints.addHorizontal(line)
    for line in (lines[1], lines[3]):
        constraints.addVertical(line)
    _pin_corners(sketch, lines, corners)
    _extrude(
        component,
        _all_profiles(sketch),
        "couponWidth",
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        "Coupon chord",
    )
    _add_saddles(component, plane, "couponWidth")


def _probe(body, x_mm, y_mm, z_mm):
    point = adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z_mm * MM)
    return body.pointContainment(point)


def _hook_checks(inside, outside):
    lip_mid_zs = [
        top - HOOK_NECK_HEIGHT - HOOK_LIP_DROP / 2.0 for top in _hook_row_tops()
    ]
    lip_mid_x = -(HOOK_THROAT + HOOK_LIP_THICKNESS / 2.0)
    checks = [("plate interior", 3.0, 0.0, 38.0, inside)]
    for row, lip_mid_z in enumerate(lip_mid_zs):
        checks.append((f"row {row} lip", lip_mid_x, 0.0, lip_mid_z, inside))
    top_lip_z = lip_mid_zs[0]
    checks += [
        ("throat gap is open", -HOOK_THROAT / 2.0, 0.0, top_lip_z, outside),
        ("no hook beside blade", lip_mid_x, HOOK_TAB_WIDTH, top_lip_z, outside),
    ]
    return checks


def _saddle_checks(inside, outside):
    wall_mid = (POCKET_RADIUS + BOSS_RADIUS) / 2.0
    floor_mid_z = ROD_CENTER_Z - (POCKET_RADIUS + BOSS_RADIUS) / 2.0
    checks = []
    for label, rod_x in (("rear", REAR_ROD_STANDOFF), ("front", FRONT_ROD_STANDOFF)):
        checks += [
            (f"{label} pocket is empty", rod_x, 0.0, ROD_CENTER_Z, outside),
            (
                f"{label} opening is open",
                rod_x,
                0.0,
                ROD_CENTER_Z + BOSS_RADIUS,
                outside,
            ),
            (f"{label} fore wall", rod_x + wall_mid, 0.0, ROD_CENTER_Z, inside),
            (f"{label} aft wall", rod_x - wall_mid, 0.0, ROD_CENTER_Z, inside),
            (f"{label} pocket floor", rod_x, 0.0, floor_mid_z, inside),
        ]
    between = (REAR_ROD_STANDOFF + FRONT_ROD_STANDOFF) / 2.0
    checks.append(("chord between saddles", between, 0.0, PLATE_HEIGHT - 6.0, inside))
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
        print(f"  probe {label:30s} ({x_mm:7.1f},{y_mm:6.1f},{z_mm:6.1f}) {state}")
        if actual != expected:
            failures.append(label)
    if failures:
        raise RuntimeError(f"geometry probes failed: {failures}")


def _references(expression, name):
    """True if a parameter expression references the given name."""
    index = expression.find(name)
    while index != -1:
        before = expression[index - 1] if index else " "
        after_index = index + len(name)
        after = expression[after_index] if after_index < len(expression) else " "
        if not (before.isalnum() or before == "_") and not (
            after.isalnum() or after == "_"
        ):
            return True
        index = expression.find(name, index + 1)
    return False


def _audit_parameters(design):
    """Fail the build if a parameter drives nothing or has the wrong unit."""
    declared = parameters()
    user_parameters = design.userParameters
    all_parameters = design.allParameters
    expressions = {}
    for index in range(all_parameters.count):
        parameter = all_parameters.item(index)
        expressions[parameter.name] = parameter.expression or ""
    idle, wrong_unit, undeclared = [], [], []
    for index in range(user_parameters.count):
        parameter = user_parameters.item(index)
        if parameter.name not in declared:
            undeclared.append(parameter.name)
            continue
        if parameter.unit != declared[parameter.name][1]:
            wrong_unit.append(f"{parameter.name}={parameter.unit!r}")
        used = any(
            other != parameter.name and _references(expression, parameter.name)
            for other, expression in expressions.items()
        )
        if not used:
            idle.append(parameter.name)
    print(f"  parameters: {len(declared)} declared, all driving geometry")
    if undeclared or wrong_unit or idle:
        raise RuntimeError(
            f"parameter audit failed: idle={idle} wrong_unit={wrong_unit} "
            f"undeclared={undeclared}"
        )


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


def _fusion_project(app):
    projects = app.data.dataProjects
    for index in range(projects.count):
        if projects.item(index).name == FUSION_PROJECT_NAME:
            return projects.item(index)
    return projects.add(FUSION_PROJECT_NAME)


def _existing_data_file(folder, name):
    files = folder.dataFiles
    hits = [files.item(i) for i in range(files.count) if files.item(i).name == name]
    if len(hits) > 1:
        raise RuntimeError(f"{len(hits)} documents named {name!r} in the project")
    return hits[0] if hits else None


def _clear_timeline(design):
    timeline = design.timeline
    while timeline.count:
        before = timeline.count
        timeline.item(timeline.count - 1).entity.deleteMe()
        if timeline.count >= before:
            raise RuntimeError("timeline item refused to delete")


def _drop_stale_parameters(design):
    """Delete parameters this variant no longer declares, or that changed unit."""
    declared = parameters()
    user_parameters = design.userParameters
    for index in range(user_parameters.count - 1, -1, -1):
        parameter = user_parameters.item(index)
        expected = declared.get(parameter.name)
        if expected is None or parameter.unit != expected[1]:
            print(f"  dropping stale parameter {parameter.name}")
            parameter.deleteMe()


def run(_context: str):
    """Build the variant into its saved document, verify, export, version."""
    if BUILD_VARIANT not in EXPORT_NAME:
        raise ValueError(f"unknown BUILD_VARIANT {BUILD_VARIANT!r}")
    app = adsk.core.Application.get()
    doc_name = DOC_NAME[BUILD_VARIANT]
    folder = _fusion_project(app).rootFolder
    data_file = _existing_data_file(folder, doc_name)
    if data_file is None:
        document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    else:
        document = app.documents.open(data_file, True)
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("active document is not a design")
    if data_file is not None:
        _clear_timeline(design)
        _drop_stale_parameters(design)
    _ensure_parameters(design)
    component = design.rootComponent
    plane = component.xZConstructionPlane

    if BUILD_VARIANT == "bracket":
        _build_bracket(component, plane)
    elif BUILD_VARIANT == "coupon":
        _build_coupon(component, plane)
    else:
        _build_gauge(component, plane)

    if component.bRepBodies.count != 1:
        raise RuntimeError(f"expected one body, got {component.bRepBodies.count}")
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
    _audit_parameters(design)
    _export(design, EXPORT_NAME[BUILD_VARIANT])
    description = (
        f"scripted {BUILD_VARIANT} build {datetime.date.today().isoformat()}: "
        f"slot {SLOT_WIDTH} mm, rod {ROD_OUTER_DIAMETER} mm, "
        f"width {BRACKET_WIDTH} mm"
    )
    if data_file is None:
        document.saveAs(doc_name, folder, description, "")
    else:
        document.save(description)
    print(f"saved '{doc_name}' in project '{FUSION_PROJECT_NAME}': {description}")
    print("build complete")
