"""Fusion 360 script: snap-on label clip for the spool cradle rods.

Run inside Fusion via scripts/run_in_fusion.py. A C-clip snaps onto a rod
from below and slides along it to sit under its spool; a paddle hangs
down-forward carrying a label face sized for a 1" x 2-1/8" adhesive label.
Print one per spool.

Every dimension is parameter driven, with real units: lengths in mm, angles
in deg. The build refuses to finish if any user parameter drives nothing or
carries the wrong unit — that check exists because the mouth opening was
once a hardcoded sketch number sitting next to a mouthHalfAngleDeg that
Fusion had stored in millimetres.

Geometry, with the rod axis as the model Y axis through the origin:
- The ring wraps the rod: bore rodOuterDiameter + clipClearance, wall
  clipWall. The mouth is a wedge of 2 x mouthHalfAngleDeg centred straight
  up, clearing the spool's resting contact point (about 23 deg off vertical)
  so the clip snaps on from below and the spool never touches it.
- The paddle leaves the ring at paddleAngleDeg below horizontal-forward.
  At 100 deg it hangs just past plumb with its lower edge leaned back, so
  the face aims at a viewer looking up at a rod above head height (the rod
  sits about 76" up; a 72" viewer looks up at it by 10 to 20 deg). A shelf
  below eye level would want about 50 deg instead. Its radii are derived
  from the ring: the stem starts mid-wall, runs stemLength past the outer
  wall, and the face adds faceHeight beyond that. Changing the rod, the
  clearance or the wall therefore moves the stem with the ring instead of
  leaving it poking into the bore.

- The label face is flush with one side of the ring rather than centred
  on it, so the whole part has a flat side. That offsets the face's weight
  along the rod, and the ring cocks on the rod until its side edges touch
  the pipe: the tilt limit is about clipClearance / clipWidth. At 9 mm the
  label hung 3 deg off level; 20 mm halves that.

Print ON THAT SIDE (rotate 90 deg about X): ring, stem and label face all
sit on the bed, the face standing as a vertical fin. No supports, no brim.

Scaffolding is repeated rather than shared on purpose — Fusion's persistent
interpreter caches imported modules across MCP runs (fusion-360-mcp skill).
"""

import datetime
import math

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are centimetres

# Set True only to deliberately discard a hand edit in the document.
ALLOW_OVERWRITE = False

PROJECT_DIR = "/Users/mhuot/lan-spool-shelf"
FUSION_PROJECT_NAME = "LAN Spool Shelf"
DOC_NAME = "Rod Label Clip"
EXPORT_NAME = "rod_label_clip"

# --- Dimensions: mm unless the name ends in Deg -----------------------------
ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC, as on the shelf
CLIP_CLEARANCE = 0.7  # diametral: slides and spins freely on the rod
CLIP_WALL = 2.4
CLIP_WIDTH = 20.0  # ring and stem width along the rod; the lever against tilt
MOUTH_HALF_ANGLE_DEG = 60.0  # half the mouth opening, about straight up
PADDLE_ANGLE_DEG = 100.0  # paddle drop, degrees BELOW horizontal-forward
PADDLE_THICKNESS = 2.4
STEM_LENGTH = 11.5  # stem reach beyond the ring's outer wall
FACE_HEIGHT = 29.0  # label face, stem end outward; fits a 1" label
FACE_WIDTH = 58.0  # along the rod; fits a 1" x 2-1/8" label with margin

CLIP_INNER_RADIUS = (ROD_OUTER_DIAMETER + CLIP_CLEARANCE) / 2.0
CLIP_OUTER_RADIUS = CLIP_INNER_RADIUS + CLIP_WALL
# Derived: the stem starts in the middle of the ring wall so the join is
# solid and the stem can never reach the bore, whatever the ring is set to.
STEM_START_RADIUS = CLIP_INNER_RADIUS + CLIP_WALL / 2.0
STEM_END_RADIUS = CLIP_OUTER_RADIUS + STEM_LENGTH
FACE_END_RADIUS = STEM_END_RADIUS + FACE_HEIGHT

# name: (value, unit, comment). Every one must drive geometry — see _audit.
PARAMETERS = {
    "rodOuterDiameter": (ROD_OUTER_DIAMETER, "mm", "rod the clip snaps onto"),
    "clipClearance": (CLIP_CLEARANCE, "mm", "diametral, so the clip slides"),
    "clipWall": (CLIP_WALL, "mm", "ring wall thickness"),
    "clipWidth": (CLIP_WIDTH, "mm", "ring and stem width along the rod"),
    "mouthHalfAngleDeg": (MOUTH_HALF_ANGLE_DEG, "deg", "half the mouth opening"),
    "paddleAngleDeg": (PADDLE_ANGLE_DEG, "deg", "paddle drop below horizontal"),
    "paddleThickness": (PADDLE_THICKNESS, "mm", "stem and label face thickness"),
    "stemLength": (STEM_LENGTH, "mm", "stem reach beyond the ring outer wall"),
    "faceHeight": (FACE_HEIGHT, "mm", "label face, from stem end outward"),
    "faceWidth": (FACE_WIDTH, "mm", "label face width along the rod"),
}
CLIP_BORE = "rodOuterDiameter + clipClearance"
CLIP_OUTER = f"{CLIP_BORE} + 2 * clipWall"
# Derived user parameters: name: (expression, unit, comment). They sit in
# the parameter table so the radii are visible, but are driven by the
# values above; editing one of these by hand just gets overwritten.
DERIVED_PARAMETERS = {
    "stemStartRadius": (
        f"({CLIP_BORE}) / 2 + clipWall / 2",
        "mm",
        "derived: stem starts mid ring wall",
    ),
    "stemEndRadius": (
        f"({CLIP_OUTER}) / 2 + stemLength",
        "mm",
        "derived: stem ends, label face begins",
    ),
    "faceEndRadius": (
        "stemEndRadius + faceHeight",
        "mm",
        "derived: outer edge of the label face",
    ),
}
ALL_PARAMETER_UNITS = {
    name: unit
    for table in (PARAMETERS, DERIVED_PARAMETERS)
    for name, (_, unit, _) in table.items()
}
SEED_RADII = {
    "stemStartRadius": STEM_START_RADIUS,
    "stemEndRadius": STEM_END_RADIUS,
    "faceEndRadius": FACE_END_RADIUS,
}


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


def _construction_line(sketch, to_x, to_z):
    """A construction line from the sketch origin, pinned there."""
    line = sketch.sketchCurves.sketchLines.addByTwoPoints(
        _point(0.0, 0.0), _point(to_x, to_z)
    )
    line.isConstruction = True
    sketch.geometricConstraints.addCoincident(line.startSketchPoint, sketch.originPoint)
    return line


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


def _annulus_profile(sketch):
    """The profile with two loops (the ring), not the inner disc."""
    for profile in _all_profiles(sketch):
        if profile.profileLoops.count == 2:
            return profile
    raise RuntimeError("no annulus profile found")


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _set_angle(sketch, line_one, line_two, expression, text_x, text_z):
    dimension = sketch.sketchDimensions.addAngularDimension(
        line_one, line_two, _point(text_x, text_z)
    )
    dimension.parameter.expression = expression
    return dimension


def _ensure_parameters(design):
    """Create or update user parameters, each with its declared unit.

    Plain parameters get a literal value; derived ones get an expression in
    the plain ones, so they are created second.
    """
    user_parameters = design.userParameters
    declared = [
        (name, f"{value} {unit}", unit, comment)
        for name, (value, unit, comment) in PARAMETERS.items()
    ] + [
        (name, expression, unit, comment)
        for name, (expression, unit, comment) in DERIVED_PARAMETERS.items()
    ]
    for name, expression, unit, comment in declared:
        existing = user_parameters.itemByName(name)
        if existing:
            if existing.unit != unit:
                raise RuntimeError(
                    f"parameter {name!r} exists with unit {existing.unit!r}, "
                    f"expected {unit!r}; it must be deleted before rebuilding"
                )
            existing.expression = expression
            existing.comment = comment
        else:
            user_parameters.add(
                name,
                adsk.core.ValueInput.createByString(expression),
                unit,
                comment,
            )


def _build_ring(component, plane):
    """Annulus driven by rodOuterDiameter, clipClearance and clipWall."""
    sketch = component.sketches.add(plane)
    sketch.name = "Ring"
    circles = sketch.sketchCurves.sketchCircles
    inner = circles.addByCenterRadius(_point(0, 0), CLIP_INNER_RADIUS * MM)
    outer = circles.addByCenterRadius(_point(0, 0), CLIP_OUTER_RADIUS * MM)
    constraints = sketch.geometricConstraints
    constraints.addCoincident(inner.centerSketchPoint, sketch.originPoint)
    constraints.addConcentric(inner, outer)
    dimensions = sketch.sketchDimensions
    for circle, expression, text_z in (
        (inner, CLIP_BORE, 5.0),
        (outer, CLIP_OUTER, -5.0),
    ):
        dimension = dimensions.addDiameterDimension(
            circle, _point(CLIP_OUTER_RADIUS + 8.0, text_z)
        )
        dimension.parameter.expression = expression
    _extrude(
        component,
        [_annulus_profile(sketch)],
        "clipWidth",
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        "Ring",
    )


def _build_mouth(component, plane):
    """Mouth wedge: a quadrilateral apexed on the clip centre.

    This is the user's own construction, recovered from version 3 of the
    document: both legs start at the clip centre, the far side meets at a
    point carried on a vertical centre construction line, and each leg gets
    its own angular dimension to that line rather than a symmetry
    constraint. Their sketch left the leg lengths free; here all three are
    dimensioned to the same reach, so the sketch is fully constrained and
    the wedge always clears the ring wall however the angle is edited.
    """
    sketch = component.sketches.add(plane)
    sketch.name = "Mouth"
    spread = math.radians(MOUTH_HALF_ANGLE_DEG)
    reach = (CLIP_OUTER_RADIUS + 5.0) / math.cos(spread)
    # pylint: disable-next=unbalanced-tuple-unpacking
    apex_to_right, right_to_top, _top_to_left, left_to_apex = _polyline(
        sketch,
        [
            (0.0, 0.0),
            (reach * math.sin(spread), reach * math.cos(spread)),
            (0.0, reach),
            (-reach * math.sin(spread), reach * math.cos(spread)),
        ],
    )
    constraints = sketch.geometricConstraints
    constraints.addCoincident(apex_to_right.startSketchPoint, sketch.originPoint)
    centre = _construction_line(sketch, 0.0, reach)
    constraints.addVertical(centre)
    constraints.addCoincident(centre.endSketchPoint, right_to_top.endSketchPoint)

    reach_expression = f"(({CLIP_OUTER}) / 2 + 5 mm) / cos(mouthHalfAngleDeg)"
    for line, text in (
        (apex_to_right, (reach * 0.55, reach * 0.2)),
        (left_to_apex, (-reach * 0.55, reach * 0.2)),
        (centre, (3.0, reach * 0.75)),
    ):
        dimension = sketch.sketchDimensions.addDistanceDimension(
            line.startSketchPoint,
            line.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
            _point(*text),
        )
        dimension.parameter.expression = reach_expression
    _set_angle(sketch, centre, apex_to_right, "mouthHalfAngleDeg", 5.0, reach * 0.45)
    _set_angle(sketch, centre, left_to_apex, "mouthHalfAngleDeg", -5.0, reach * 0.45)
    print(f"  mouth sketch fully constrained: {sketch.isFullyConstrained}")
    _extrude(
        component,
        _all_profiles(sketch),
        "clipWidth + 10 mm",
        adsk.fusion.FeatureOperations.CutFeatureOperation,
        "Mouth",
    )


def _paddle_direction():
    """Unit vector along the paddle in model space (x forward, z up)."""
    angle = math.radians(PADDLE_ANGLE_DEG)
    return adsk.core.Vector3D.create(math.cos(angle), 0.0, -math.sin(angle))


def _build_paddle_plane(component):
    """Plane through the rod axis whose normal is the paddle direction.

    The YZ plane rotated about the rod axis by paddleAngleDeg. Fusion does
    not say which way a positive angle turns, so the normal is checked and
    the sign of the expression flipped if it came out the other way. The
    paddle cross-sections are sketched on this plane and extruded outward
    from it, which is what lets the paddle sit at any angle: the earlier
    construction pinned corners with unsigned distances from the origin,
    and past about 85 deg a corner crossed the axis and the solver was free
    to mirror the whole strip.
    """
    planes = component.constructionPlanes
    wanted = _paddle_direction()
    for expression in ("paddleAngleDeg", "-paddleAngleDeg"):
        plane_input = planes.createInput()
        plane_input.setByAngle(
            component.yConstructionAxis,
            adsk.core.ValueInput.createByString(expression),
            component.yZConstructionPlane,
        )
        plane = planes.add(plane_input)
        normal = plane.geometry.normal
        if abs(abs(normal.dotProduct(wanted)) - 1.0) < 1e-6:
            plane.name = "Paddle plane"
            print(f"  paddle plane: angle expression {expression!r}")
            return plane
        plane.deleteMe()
    raise RuntimeError("paddle plane normal never matched the paddle direction")


def _section_point(sketch, along_mm, across_mm):
    """Sketch point on the paddle plane: along the rod, across the paddle."""
    angle = math.radians(PADDLE_ANGLE_DEG)
    model = adsk.core.Point3D.create(
        across_mm * math.sin(angle) * MM,
        along_mm * MM,
        across_mm * math.cos(angle) * MM,
    )
    return sketch.modelToSketchSpace(model)


def _section_sketch(component, plane, name):
    """Sketch on the paddle plane with the rod axis projected as a line."""
    sketch = component.sketches.add(plane)
    sketch.name = name
    origin = sketch.originPoint.worldGeometry
    if origin.distanceTo(adsk.core.Point3D.create(0, 0, 0)) > 1e-6:
        raise RuntimeError(f"{name} sketch origin is off the rod axis")
    axis = sketch.project(component.yConstructionAxis).item(0)
    axis.isConstruction = True
    return sketch, axis


def _section_rectangle(sketch, axis, along_range, half_thickness):
    """Closed rectangle: long sides parallel to and symmetric about the axis.

    Returns (near, far, long_sides): the short sides at the low and high end
    of along_range, and the two long sides. Their positions along the rod
    are left to the caller.
    """
    low, high = along_range
    corners = [
        _section_point(sketch, low, half_thickness),
        _section_point(sketch, high, half_thickness),
        _section_point(sketch, high, -half_thickness),
        _section_point(sketch, low, -half_thickness),
    ]
    lines = sketch.sketchCurves.sketchLines
    made = [lines.addByTwoPoints(corners[0], corners[1])]
    for corner in corners[2:]:
        made.append(lines.addByTwoPoints(made[-1].endSketchPoint, corner))
    made.append(lines.addByTwoPoints(made[-1].endSketchPoint, made[0].startSketchPoint))
    top, far, bottom, near = made  # pylint: disable=unbalanced-tuple-unpacking
    constraints = sketch.geometricConstraints
    constraints.addParallel(top, axis)
    constraints.addParallel(bottom, axis)
    constraints.addPerpendicular(near, axis)
    constraints.addPerpendicular(far, axis)
    constraints.addSymmetry(top, bottom, axis)
    _set_offset_between(sketch, top, bottom, "paddleThickness", (high + 4.0, 0.0))
    return near, far


def _set_offset_between(sketch, line_one, line_two, expression, text_at):
    """Dimension the distance between two parallel lines on the paddle plane.

    text_at is (along, across) in mm for the dimension text.
    """
    dimension = sketch.sketchDimensions.addOffsetDimension(
        line_one, line_two, _section_point(sketch, *text_at)
    )
    dimension.parameter.expression = expression
    return dimension


def _extrude_outward(component, sketch, start_expression, length_expression, name):
    """Join-extrude every profile of the sketch away from the rod axis.

    Starts start_expression from the sketch plane and runs length_expression
    further, both along the paddle direction. The sketch normal may point
    either way along that direction, so the offset and the extent direction
    are flipped together when it points inward.
    """
    normal = sketch.xDirection.crossProduct(sketch.yDirection)
    outward = normal.dotProduct(_paddle_direction())
    if abs(abs(outward) - 1.0) > 1e-6:
        raise RuntimeError(f"{name}: sketch normal is not along the paddle")
    if outward > 0:
        offset = start_expression
        direction = adsk.fusion.ExtentDirections.PositiveExtentDirection
    else:
        offset = f"-({start_expression})"
        direction = adsk.fusion.ExtentDirections.NegativeExtentDirection
    profiles = adsk.core.ObjectCollection.create()
    for profile in _all_profiles(sketch):
        profiles.add(profile)
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profiles, adsk.fusion.FeatureOperations.JoinFeatureOperation
    )
    extrude_input.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByString(offset)
    )
    extrude_input.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString(length_expression)
        ),
        direction,
    )
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


def _require_constrained(sketch):
    print(f"  {sketch.name} sketch fully constrained: {sketch.isFullyConstrained}")
    if not sketch.isFullyConstrained:
        raise RuntimeError(f"{sketch.name} sketch is not fully constrained")


def _build_stem(component, plane):
    """Stem cross-section centred on the rod axis; returns its near edge.

    clipWidth along the rod, paddleThickness across, symmetric both ways so
    nothing can mirror. Extruded from mid ring wall to stemEndRadius.
    """
    sketch, axis = _section_sketch(component, plane, "Stem section")
    half_width = CLIP_WIDTH / 2.0
    near, far = _section_rectangle(
        sketch, axis, (-half_width, half_width), PADDLE_THICKNESS / 2.0
    )
    centre = sketch.sketchCurves.sketchLines.addByTwoPoints(
        _section_point(sketch, 0.0, 0.0), _section_point(sketch, 0.0, 6.0)
    )
    centre.isConstruction = True
    constraints = sketch.geometricConstraints
    constraints.addCoincident(centre.startSketchPoint, sketch.originPoint)
    constraints.addPerpendicular(centre, axis)
    length = sketch.sketchDimensions.addDistanceDimension(
        centre.startSketchPoint,
        centre.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        _section_point(sketch, 2.0, 5.0),
    )
    length.parameter.expression = "paddleThickness * 2"
    constraints.addSymmetry(near, far, centre)
    _set_offset_between(sketch, near, far, "clipWidth", (0.0, -PADDLE_THICKNESS - 2.0))
    _require_constrained(sketch)
    _extrude_outward(
        component, sketch, "stemStartRadius", "stemEndRadius - stemStartRadius", "Stem"
    )
    if near.startSketchPoint.worldGeometry.y > 0:
        raise RuntimeError("stem near edge solved onto the far side")
    return near


def _build_face(component, plane, stem_near_edge):
    """Label face, flush with one side of the ring so it prints unsupported.

    The face used to be centred on the ring, which in the side-on print
    orientation left the ring and stem floating 24.5 mm above the bed on
    support. Its near edge is now collinear with the stem's, so ring, stem
    and face all sit on the bed. Extruded from stemEndRadius by faceHeight.
    """
    sketch, axis = _section_sketch(component, plane, "Face section")
    half_width = CLIP_WIDTH / 2.0
    near, far = _section_rectangle(
        sketch, axis, (-half_width, FACE_WIDTH - half_width), PADDLE_THICKNESS / 2.0
    )
    stem_edge = sketch.project(stem_near_edge).item(0)
    stem_edge.isConstruction = True
    sketch.geometricConstraints.addCollinear(near, stem_edge)
    _set_offset_between(
        sketch, near, far, "faceWidth", (FACE_WIDTH / 2.0, -PADDLE_THICKNESS - 2.0)
    )
    _require_constrained(sketch)
    _extrude_outward(
        component,
        sketch,
        "stemEndRadius",
        "faceEndRadius - stemEndRadius",
        "Label face",
    )


def _build_body(component, plane):
    _build_ring(component, plane)
    _build_mouth(component, plane)
    paddle_plane = _build_paddle_plane(component)
    stem_near_edge = _build_stem(component, paddle_plane)
    _build_face(component, paddle_plane, stem_near_edge)


def _probe(body, x_mm, y_mm, z_mm):
    point = adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z_mm * MM)
    return body.pointContainment(point)


def _ring_point(angle_deg, radius):
    angle = math.radians(angle_deg)
    return (radius * math.cos(angle), radius * math.sin(angle))


def _verify(body):  # pylint: disable=too-many-locals
    """Numeric probes; raise on any surprise so the failure is loud."""
    inside = adsk.fusion.PointContainment.PointInsidePointContainment
    outside = adsk.fusion.PointContainment.PointOutsidePointContainment
    wall_mid = (CLIP_INNER_RADIUS + CLIP_OUTER_RADIUS) / 2.0
    angle = math.radians(-PADDLE_ANGLE_DEG)
    stem_mid = (STEM_END_RADIUS + CLIP_OUTER_RADIUS) / 2.0
    face_mid = (STEM_END_RADIUS + FACE_END_RADIUS) / 2.0
    open_at = 90.0 - MOUTH_HALF_ANGLE_DEG / 2.0
    closed_at = 90.0 - MOUTH_HALF_ANGLE_DEG - 12.0
    checks = []
    for label, angle_deg, expected in (
        ("ring bottom", 270.0, inside),
        ("mouth at top", 90.0, outside),
        (f"mouth open at {open_at:.0f} deg", open_at, outside),
        (f"ring closed at {closed_at:.0f} deg", closed_at, inside),
        ("ring closed at 180 deg", 180.0, inside),
    ):
        x_mm, z_mm = _ring_point(angle_deg, wall_mid)
        checks.append((label, x_mm, 0.0, z_mm, expected))
    checks += [
        ("bore is clear", 0.0, 0.0, -(CLIP_INNER_RADIUS - 0.3), outside),
        (
            "bore clear under stem",
            (CLIP_INNER_RADIUS - 0.3) * math.cos(angle),
            0.0,
            (CLIP_INNER_RADIUS - 0.3) * math.sin(angle),
            outside,
        ),
        (
            "stem joins ring wall",
            wall_mid * math.cos(angle),
            0.0,
            wall_mid * math.sin(angle),
            inside,
        ),
        (
            "stem mid",
            stem_mid * math.cos(angle),
            0.0,
            stem_mid * math.sin(angle),
            inside,
        ),
        (
            "stem stays clip-width",
            stem_mid * math.cos(angle),
            CLIP_WIDTH / 2.0 + 1.0,
            stem_mid * math.sin(angle),
            outside,
        ),
        (
            "face mid",
            face_mid * math.cos(angle),
            0.0,
            face_mid * math.sin(angle),
            inside,
        ),
        (
            "face full width",
            face_mid * math.cos(angle),
            FACE_WIDTH / 2.0 - 2.0,
            face_mid * math.sin(angle),
            inside,
        ),
        (
            "beyond face outer edge",
            (FACE_END_RADIUS + 4.0) * math.cos(angle),
            0.0,
            (FACE_END_RADIUS + 4.0) * math.sin(angle),
            outside,
        ),
    ]
    # The face is flush with the ring's -y side and extends past its +y side.
    for label, y_mm, expected in (
        ("face flush at ring -y side", -CLIP_WIDTH / 2.0 - 1.0, outside),
        ("face covers ring +y side", CLIP_WIDTH / 2.0 + 1.0, inside),
        ("face reaches full width", FACE_WIDTH - CLIP_WIDTH / 2.0 - 1.0, inside),
        ("face stops at full width", FACE_WIDTH - CLIP_WIDTH / 2.0 + 1.0, outside),
    ):
        checks.append(
            (
                label,
                face_mid * math.cos(angle),
                y_mm,
                face_mid * math.sin(angle),
                expected,
            )
        )
    failures = []
    for label, x_mm, y_mm, z_mm, expected in checks:
        actual = _probe(body, x_mm, y_mm, z_mm)
        state = "ok" if actual == expected else f"FAIL (got {actual})"
        print(f"  probe {label:26s} ({x_mm:6.1f},{y_mm:6.1f},{z_mm:6.1f}) {state}")
        if actual != expected:
            failures.append(label)
    bounding = body.boundingBox
    flat_side = bounding.minPoint.y / MM
    if abs(flat_side + CLIP_WIDTH / 2.0) > 0.01:
        failures.append(f"flat side at y={flat_side:.2f}, expected {-CLIP_WIDTH / 2.0}")
    else:
        print(f"  flat side at y={flat_side:.2f} mm: prints on the bed unsupported")
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
    """Fail the build if a parameter drives nothing or has the wrong unit.

    A parameter earns its place only by appearing in another parameter's
    expression — a sketch dimension or a feature extent. Anything else is a
    comment pretending to be a control.
    """
    user_parameters = design.userParameters
    all_parameters = design.allParameters
    expressions = {}
    for index in range(all_parameters.count):
        parameter = all_parameters.item(index)
        expressions[parameter.name] = parameter.expression or ""
    idle, wrong_unit = [], []
    for index in range(user_parameters.count):
        parameter = user_parameters.item(index)
        expected_unit = ALL_PARAMETER_UNITS[parameter.name]
        if parameter.unit != expected_unit:
            wrong_unit.append(f"{parameter.name}={parameter.unit!r}")
        used = any(
            other != parameter.name and _references(expression, parameter.name)
            for other, expression in expressions.items()
        )
        if not used:
            idle.append(parameter.name)
    print(f"  parameters: {user_parameters.count} declared, all driving geometry")
    if wrong_unit:
        raise RuntimeError(f"wrong units: {wrong_unit}")
    if idle:
        raise RuntimeError(f"parameters drive nothing: {idle}")


def _export(design):
    root = design.rootComponent
    export_manager = design.exportManager
    step_path = f"{PROJECT_DIR}/cad/{EXPORT_NAME}.step"
    archive_path = f"{PROJECT_DIR}/cad/{EXPORT_NAME}.f3d"
    stl_path = f"{PROJECT_DIR}/exports/{EXPORT_NAME}.stl"
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


def _recorded_volume(data_file):
    """Body volume in mm^3 recorded by the most recent scripted save."""
    versions = data_file.versions
    for index in range(versions.count):  # newest first
        text = versions.item(index).description or ""
        if text.startswith("scripted") and " vol " in text:
            try:
                return float(text.split(" vol ")[1].split()[0])
            except (IndexError, ValueError):
                return None
    return None


def _refuse_if_hand_edited(data_file, design):
    """Never clear a timeline carrying geometry this script did not build.

    Fusion labels a human's save "User Saved". That alone is not proof of an
    edit — opening a document and pressing save is common and harmless — so
    compare the geometry against the volume recorded by the last scripted
    save. Same volume, benign save, carry on. Different, stop: an edit is
    sitting there and rebuilding would discard it. That has already cost the
    label clip's mouth construction and the SKADIS peg fillet, both of which
    had to be reverse-engineered out of version history.
    """
    description = data_file.description or ""
    if ALLOW_OVERWRITE or description.startswith("scripted"):
        return
    recorded = _recorded_volume(data_file)
    bodies = design.rootComponent.bRepBodies
    current = bodies.item(0).volume / (MM**3) if bodies.count else None
    if recorded is not None and current is not None and abs(current - recorded) < 1.0:
        print(
            f"  note: last save was {description!r}, but the geometry still "
            f"matches the last scripted build ({current:.0f} mm^3) — proceeding"
        )
        return
    difference = (
        f"{current:.0f} vs {recorded:.0f} mm^3"
        if recorded is not None and current is not None
        else "no recorded volume to compare"
    )
    raise RuntimeError(
        f"{data_file.name!r} v{data_file.versionNumber} was last saved by hand "
        f"({description!r}) and its geometry differs: {difference}. Rebuilding "
        "would discard that edit. Inspect the document, fold the change into "
        "this script, then rebuild — or set ALLOW_OVERWRITE = True if the edit "
        "is genuinely disposable."
    )


def _clear_timeline(design):
    timeline = design.timeline
    while timeline.count:
        before = timeline.count
        timeline.item(timeline.count - 1).entity.deleteMe()
        if timeline.count >= before:
            raise RuntimeError("timeline item refused to delete")


def _drop_stale_parameters(design):
    """Delete user parameters this script no longer declares.

    Renaming or retyping one otherwise leaves the old parameter behind
    driving nothing — which is exactly what the audit is meant to catch.
    """
    user_parameters = design.userParameters
    for index in range(user_parameters.count - 1, -1, -1):
        parameter = user_parameters.item(index)
        if parameter.unit != ALL_PARAMETER_UNITS.get(parameter.name):
            print(f"  dropping stale parameter {parameter.name}")
            parameter.deleteMe()


def run(_context: str):
    """Build the clip into its saved document, verify, export, version."""
    app = adsk.core.Application.get()
    folder = _fusion_project(app).rootFolder
    data_file = _existing_data_file(folder, DOC_NAME)
    if data_file is None:
        document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    else:
        document = app.documents.open(data_file, True)
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("active document is not a design")
    if data_file is not None:
        _refuse_if_hand_edited(data_file, design)
        _clear_timeline(design)
        _drop_stale_parameters(design)
    _ensure_parameters(design)
    component = design.rootComponent
    _build_body(component, component.xZConstructionPlane)

    if component.bRepBodies.count != 1:
        raise RuntimeError(f"expected one body, got {component.bRepBodies.count}")
    body = component.bRepBodies.item(0)
    body.name = EXPORT_NAME

    bounding = body.boundingBox
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
    _export(design)
    description = (
        f"scripted label clip build {datetime.date.today().isoformat()}: "
        f"rod {ROD_OUTER_DIAMETER} mm, mouth +/-{MOUTH_HALF_ANGLE_DEG:.0f} deg, "
        f"paddle {PADDLE_ANGLE_DEG:.0f} deg, face {FACE_WIDTH:.0f} mm"
    )
    description += f" vol {body.volume / (MM ** 3):.0f} mm3"
    if data_file is None:
        document.saveAs(DOC_NAME, folder, description, "")
    else:
        document.save(description)
    print(f"saved '{DOC_NAME}' in project '{FUSION_PROJECT_NAME}': {description}")
    print("build complete")
