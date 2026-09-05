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
- The paddle leaves the ring at paddleAngleDeg below horizontal-forward, so
  the label face tilts up toward a standing viewer.

Print ON ITS SIDE (rotate 90 deg about X): ring and stem lie flat as a C and
the label face stands as a vertical fin. Supports on build plate only.

Scaffolding is repeated rather than shared on purpose — Fusion's persistent
interpreter caches imported modules across MCP runs (fusion-360-mcp skill).
"""

import datetime
import math

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are centimetres

PROJECT_DIR = "/Users/mhuot/lan-spool-shelf"
FUSION_PROJECT_NAME = "LAN Spool Shelf"
DOC_NAME = "Rod Label Clip"
EXPORT_NAME = "rod_label_clip"

# --- Dimensions: mm unless the name ends in Deg -----------------------------
ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC, as on the shelf
CLIP_CLEARANCE = 0.7  # diametral: slides and spins freely on the rod
CLIP_WALL = 2.4
CLIP_WIDTH = 9.0  # ring and stem width, along the rod
MOUTH_HALF_ANGLE_DEG = 60.0  # half the mouth opening, about straight up
PADDLE_ANGLE_DEG = 50.0  # paddle drop, degrees BELOW horizontal-forward
PADDLE_THICKNESS = 2.4
STEM_START_RADIUS = 16.0  # inside the ring wall, so the join is solid
STEM_END_RADIUS = 31.0  # stem ends, label face begins
FACE_END_RADIUS = 60.0  # outer edge of the label face (29 mm of face)
FACE_WIDTH = 58.0  # along the rod; fits a 1" x 2-1/8" label with margin

CLIP_INNER_RADIUS = (ROD_OUTER_DIAMETER + CLIP_CLEARANCE) / 2.0
CLIP_OUTER_RADIUS = CLIP_INNER_RADIUS + CLIP_WALL

# name: (value, unit, comment). Every one must drive geometry — see _audit.
PARAMETERS = {
    "rodOuterDiameter": (ROD_OUTER_DIAMETER, "mm", "rod the clip snaps onto"),
    "clipClearance": (CLIP_CLEARANCE, "mm", "diametral, so the clip slides"),
    "clipWall": (CLIP_WALL, "mm", "ring wall thickness"),
    "clipWidth": (CLIP_WIDTH, "mm", "ring and stem width along the rod"),
    "mouthHalfAngleDeg": (MOUTH_HALF_ANGLE_DEG, "deg", "half the mouth opening"),
    "paddleAngleDeg": (PADDLE_ANGLE_DEG, "deg", "paddle drop below horizontal"),
    "paddleThickness": (PADDLE_THICKNESS, "mm", "stem and label face thickness"),
    "stemStartRadius": (STEM_START_RADIUS, "mm", "stem starts inside the ring"),
    "stemEndRadius": (STEM_END_RADIUS, "mm", "stem ends, label face begins"),
    "faceEndRadius": (FACE_END_RADIUS, "mm", "outer edge of the label face"),
    "faceWidth": (FACE_WIDTH, "mm", "label face width along the rod"),
}
SEED_RADII = {
    "stemStartRadius": STEM_START_RADIUS,
    "stemEndRadius": STEM_END_RADIUS,
    "faceEndRadius": FACE_END_RADIUS,
}
CLIP_BORE = "rodOuterDiameter + clipClearance"
CLIP_OUTER = f"{CLIP_BORE} + 2 * clipWall"


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
def _set_offset(sketch, line, entity, expression, text_x, text_z):
    """Dimension the perpendicular distance from a line to a point or line."""
    dimension = sketch.sketchDimensions.addOffsetDimension(
        line, entity, _point(text_x, text_z)
    )
    dimension.parameter.expression = expression
    return dimension


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _set_angle(sketch, line_one, line_two, expression, text_x, text_z):
    dimension = sketch.sketchDimensions.addAngularDimension(
        line_one, line_two, _point(text_x, text_z)
    )
    dimension.parameter.expression = expression
    return dimension


def _ensure_parameters(design):
    """Create or update user parameters, each with its declared unit."""
    user_parameters = design.userParameters
    for name, (value, unit, comment) in PARAMETERS.items():
        expression = f"{value} {unit}".strip() if unit else str(value)
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
    """Wedge cut of 2 x mouthHalfAngleDeg, centred straight up.

    The legs are dimensioned as (outer radius + 5) / cos(half angle), so the
    wedge always reaches past the ring wall however the angle is edited.
    """
    sketch = component.sketches.add(plane)
    sketch.name = "Mouth"
    spread = math.radians(MOUTH_HALF_ANGLE_DEG)
    reach = (CLIP_OUTER_RADIUS + 5.0) / math.cos(spread)
    # pylint: disable-next=unbalanced-tuple-unpacking
    leg_right, _base, leg_left = _polyline(
        sketch,
        [
            (0.0, 0.0),
            (reach * math.sin(spread), reach * math.cos(spread)),
            (-reach * math.sin(spread), reach * math.cos(spread)),
        ],
    )
    constraints = sketch.geometricConstraints
    constraints.addCoincident(leg_right.startSketchPoint, sketch.originPoint)
    # No horizontal constraint on the base: symmetry about the vertical axis
    # already implies it, and adding both over-constrains the sketch.
    axis = _construction_line(sketch, 0.0, reach)
    constraints.addVertical(axis)
    constraints.addSymmetry(leg_right, leg_left, axis)
    dimension = sketch.sketchDimensions.addDistanceDimension(
        leg_right.startSketchPoint,
        leg_right.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        _point(reach * 0.6, reach * 0.35),
    )
    dimension.parameter.expression = (
        f"(({CLIP_OUTER}) / 2 + 5 mm) / cos(mouthHalfAngleDeg)"
    )
    _set_angle(sketch, axis, leg_right, "mouthHalfAngleDeg", 4.0, reach * 0.5)
    _extrude(
        component,
        _all_profiles(sketch),
        "clipWidth + 10 mm",
        adsk.fusion.FeatureOperations.CutFeatureOperation,
        "Mouth",
    )


# pylint: disable-next=too-many-arguments,too-many-positional-arguments,too-many-locals
def _build_strip(component, plane, name, start_name, end_name, width_expression):
    """A paddle strip at paddleAngleDeg below horizontal, fully constrained.

    Each of the four corners is pinned by a horizontal and a vertical
    dimension off the origin, written as expressions in the radii,
    paddleThickness and paddleAngleDeg. Offset and angular dimensions were
    tried first and are a trap here: they are unsigned, so the solver is
    free to mirror the strip through the origin — which it silently did,
    landing the stem up and behind the ring instead of down in front.
    """
    sketch = component.sketches.add(plane)
    sketch.name = name
    angle = math.radians(PADDLE_ANGLE_DEG)
    half = PADDLE_THICKNESS / 2.0
    corners = []
    for radius_name, side in (
        (start_name, 1.0),
        (end_name, 1.0),
        (end_name, -1.0),
        (start_name, -1.0),
    ):
        radius = SEED_RADII[radius_name]
        x_mm = radius * math.cos(angle) + side * half * math.sin(angle)
        z_mm = -(radius * math.sin(angle)) + side * half * math.cos(angle)
        sign = "+" if side > 0 else "-"
        x_expression = (
            f"{radius_name} * cos(paddleAngleDeg) "
            f"{sign} paddleThickness / 2 * sin(paddleAngleDeg)"
        )
        # z is below the axis, so dimension its magnitude.
        z_expression = (
            f"{radius_name} * sin(paddleAngleDeg) "
            f"{'-' if side > 0 else '+'} paddleThickness / 2 * cos(paddleAngleDeg)"
        )
        if x_mm <= 0 or z_mm >= 0:
            raise RuntimeError(
                f"{name} corner at ({x_mm:.1f}, {z_mm:.1f}) is not down-forward; "
                "the unsigned dimensions below would mirror it"
            )
        corners.append((x_mm, z_mm, x_expression, z_expression))

    lines = _polyline(sketch, [(x, z) for x, z, _, _ in corners])
    horizontal = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    vertical = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    dimensions = sketch.sketchDimensions
    for index, (x_mm, z_mm, x_expression, z_expression) in enumerate(corners):
        corner_point = lines[index].startSketchPoint
        for orientation, expression, text in (
            (horizontal, x_expression, (x_mm * 0.5, z_mm - 4.0 - index * 3.0)),
            (vertical, z_expression, (x_mm + 5.0 + index * 3.0, z_mm * 0.5)),
        ):
            dimension = dimensions.addDistanceDimension(
                sketch.originPoint, corner_point, orientation, _point(*text)
            )
            dimension.parameter.expression = expression
    _extrude(
        component,
        _all_profiles(sketch),
        width_expression,
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
        name,
    )


def _build_body(component, plane):
    _build_ring(component, plane)
    _build_mouth(component, plane)
    _build_strip(
        component, plane, "Stem", "stemStartRadius", "stemEndRadius", "clipWidth"
    )
    _build_strip(
        component, plane, "Label face", "stemEndRadius", "faceEndRadius", "faceWidth"
    )


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
    failures = []
    for label, x_mm, y_mm, z_mm, expected in checks:
        actual = _probe(body, x_mm, y_mm, z_mm)
        state = "ok" if actual == expected else f"FAIL (got {actual})"
        print(f"  probe {label:26s} ({x_mm:6.1f},{y_mm:6.1f},{z_mm:6.1f}) {state}")
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
        expected_unit = PARAMETERS[parameter.name][1]
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
        if (
            parameter.name not in PARAMETERS
            or parameter.unit != PARAMETERS[parameter.name][1]
        ):
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
        f"face {FACE_WIDTH:.0f} mm"
    )
    if data_file is None:
        document.saveAs(DOC_NAME, folder, description, "")
    else:
        document.save(description)
    print(f"saved '{DOC_NAME}' in project '{FUSION_PROJECT_NAME}': {description}")
    print("build complete")
