"""Fusion 360 script: retrofit collar that widens an existing 9 mm label clip.

Run inside Fusion via scripts/run_in_fusion.py. The first label clips had a
9 mm ring; with the label face flush to one side, the ring cocks on the rod
until its edges touch the pipe, and the label hangs about 3 deg off level
(tilt limit is roughly clipClearance / ring width). New clips have a 20 mm
ring. This collar brings an old clip to the same width without reprinting
it: it snaps over the rod from below like the clip does, with a pocket in
its middle that swallows the clip's ring and a slot the stem passes
through. It bears on the rod at both ends, collarWidth apart, which is
the lever that holds the label level.

The collar is one-sided on purpose. The clip sits under its spool with the
label toward the spool's centre, so anything added on the label side of
the ring is under the spool, while anything added on the other side
reaches toward the neighbouring spool. The pocket therefore has a full lip
on the label side (+y) and only the 45 deg ledge plus a farLip bearing land
on the far side: 3.7 mm beyond the ring instead of 5.5.

Every dimension is parameter driven, lengths in mm and angles in deg, and
the build refuses to finish if a user parameter drives nothing or carries
the wrong unit. The clip it retrofits is described by ringOuterDiameter,
ringWidth, stemThickness and stemAngleDeg; those must match the printed
clip, not the current script, and the build checks the clip fits.

Geometry, with the rod axis as the model Y axis through the origin:
- Lips: an annulus on the rod bore (rodOuterDiameter + collarClearance),
  wall collarWall, collarWidth along the rod, running from farExtent on
  the far side of the ring's centre to collarWidth - farExtent on the
  label side.
- Band: a thicker annulus over the pocket, joined to the lips.
- Pocket: a revolved cut whose bore clears the clip's ring and whose
  ledges are 45 deg chamfers, so the pocket ceiling prints without support
  in either orientation.
- Mouth: the same 2 x mouthHalfAngleDeg wedge as the clip, so the collar
  snaps on from below and never meets the spool.
- Stem slot: cut through the band at stemAngleDeg, stemThickness +
  slotClearance wide, so the clip's stem passes through it. The slot walls
  also capture the stem, which is what stops the clip tilting inside the
  collar.

Print with the label-side lip on the bed (rotate -90 deg about X). The
band's outer step on that side is a 45 deg cone (a revolved cut, shifted
by chamferShift so the wall between it and the pocket ledge stays
collarWall thick), both pocket ledges are 45 deg, and the far land is
narrower than the band, so nothing overhangs. No supports.

Scaffolding is repeated rather than shared on purpose: Fusion's persistent
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
DOC_NAME = "Rod Label Collar"
EXPORT_NAME = "rod_label_collar"

# --- Dimensions: mm unless the name ends in Deg -----------------------------
ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC, as on the shelf
COLLAR_CLEARANCE = 0.7  # diametral on the rod, same as the clip that slides
COLLAR_WALL = 2.4
COLLAR_WIDTH = 20.0  # along the rod; matches the new clip's ring
MOUTH_HALF_ANGLE_DEG = 60.0  # half the mouth opening, about straight up
# The clip being retrofitted (first print run, 2026-09-06): 9 mm ring on the
# same rod and clearance, 2.4 mm wall, stem 2.4 mm thick at 100 deg.
RING_OUTER_DIAMETER = 38.9  # 33.4 + 0.7 + 2 x 2.4
RING_WIDTH = 9.0
STEM_THICKNESS = 2.4
STEM_ANGLE_DEG = 100.0  # the clip's paddleAngleDeg, below horizontal-forward
POCKET_CLEARANCE = 0.3  # diametral over the ring and total along the rod
SLOT_CLEARANCE = 0.6  # total across the stem
FAR_LIP = 1.0  # bearing land on the rod beyond the far ledge

COLLAR_BORE_RADIUS = (ROD_OUTER_DIAMETER + COLLAR_CLEARANCE) / 2.0
LIP_OUTER_RADIUS = COLLAR_BORE_RADIUS + COLLAR_WALL
POCKET_BORE_RADIUS = (RING_OUTER_DIAMETER + POCKET_CLEARANCE) / 2.0
BAND_OUTER_RADIUS = POCKET_BORE_RADIUS + COLLAR_WALL
POCKET_WIDTH = RING_WIDTH + POCKET_CLEARANCE
CHAMFER = POCKET_BORE_RADIUS - COLLAR_BORE_RADIUS  # 45 deg ledge
BAND_WIDTH = POCKET_WIDTH + 2.0 * CHAMFER
SLOT_WIDTH = STEM_THICKNESS + SLOT_CLEARANCE
CHAMFER_SHIFT = COLLAR_WALL * (math.sqrt(2.0) - 1.0)  # keeps the wall full
FAR_EXTENT = BAND_WIDTH / 2.0 + FAR_LIP  # collar's -y end, from ring centre
NEAR_EXTENT = COLLAR_WIDTH - FAR_EXTENT  # collar's +y end, label side

# name: (value, unit, comment). Every one must drive geometry — see _audit.
PARAMETERS = {
    "rodOuterDiameter": (ROD_OUTER_DIAMETER, "mm", "rod the collar snaps onto"),
    "collarClearance": (COLLAR_CLEARANCE, "mm", "diametral, so it slides"),
    "collarWall": (COLLAR_WALL, "mm", "wall thickness everywhere"),
    "collarWidth": (COLLAR_WIDTH, "mm", "total width along the rod"),
    "mouthHalfAngleDeg": (MOUTH_HALF_ANGLE_DEG, "deg", "half the mouth opening"),
    "ringOuterDiameter": (RING_OUTER_DIAMETER, "mm", "clip ring OD retrofitted"),
    "ringWidth": (RING_WIDTH, "mm", "clip ring width retrofitted"),
    "stemThickness": (STEM_THICKNESS, "mm", "clip stem thickness"),
    "stemAngleDeg": (STEM_ANGLE_DEG, "deg", "clip stem angle below horizontal"),
    "pocketClearance": (POCKET_CLEARANCE, "mm", "over the ring, dia and width"),
    "slotClearance": (SLOT_CLEARANCE, "mm", "total across the stem"),
    "farLip": (FAR_LIP, "mm", "bearing land beyond the far ledge"),
}
COLLAR_BORE = "rodOuterDiameter + collarClearance"
LIP_OUTER = f"{COLLAR_BORE} + 2 * collarWall"
POCKET_BORE = "ringOuterDiameter + pocketClearance"
BAND_OUTER = f"{POCKET_BORE} + 2 * collarWall"
# Derived user parameters: name: (expression, unit, comment).
DERIVED_PARAMETERS = {
    "pocketWidth": ("ringWidth + pocketClearance", "mm", "derived: pocket width"),
    "pocketChamfer": (
        f"({POCKET_BORE}) / 2 - ({COLLAR_BORE}) / 2",
        "mm",
        "derived: 45 deg ledge, pocket bore to rod bore",
    ),
    "bandWidth": (
        "pocketWidth + 2 * pocketChamfer",
        "mm",
        "derived: band over the pocket and its chamfers",
    ),
    "farExtent": (
        "bandWidth / 2 + farLip",
        "mm",
        "derived: far end of the collar from the ring centre",
    ),
    "chamferShift": (
        "collarWall * (sqrt(2) - 1)",
        "mm",
        "derived: outer cone offset that keeps the wall full thickness",
    ),
}
ALL_PARAMETER_UNITS = {
    name: unit
    for table in (PARAMETERS, DERIVED_PARAMETERS)
    for name, (_, unit, _) in table.items()
}


def _point(x_mm, z_mm):
    """Sketch point on the XZ plane (sketch +y is model MINUS Z)."""
    return adsk.core.Point3D.create(x_mm * MM, -z_mm * MM, 0)


def _polyline(sketch, points):
    """Closed polygon through sketch-space points; consecutive lines share ends."""
    lines = sketch.sketchCurves.sketchLines
    made = [lines.addByTwoPoints(points[0], points[1])]
    for target in points[2:]:
        made.append(lines.addByTwoPoints(made[-1].endSketchPoint, target))
    made.append(lines.addByTwoPoints(made[-1].endSketchPoint, made[0].startSketchPoint))
    return made


def _construction_line(sketch, to_x, to_z):
    """A construction line from the sketch origin, pinned there (XZ sketch)."""
    line = sketch.sketchCurves.sketchLines.addByTwoPoints(
        _point(0.0, 0.0), _point(to_x, to_z)
    )
    line.isConstruction = True
    sketch.geometricConstraints.addCoincident(line.startSketchPoint, sketch.originPoint)
    return line


def _collect(profiles_list):
    profiles = adsk.core.ObjectCollection.create()
    for profile in profiles_list:
        profiles.add(profile)
    return profiles


def _extrude(component, profiles_list, width_expression, operation, name):
    """Symmetric extrude of the given profiles, width from an expression."""
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(_collect(profiles_list), operation)
    extrude_input.setSymmetricExtent(
        adsk.core.ValueInput.createByString(width_expression), True
    )
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _extrude_along_rod(component, sketch, profiles_list, extents, operation, name):
    """Two-sided extrude from an XZ sketch: extents = (toward -y, toward +y).

    The sketch normal may point either way along the rod, so the two
    expressions are assigned to Fusion's side one (along the normal) and
    side two by checking which way the normal actually points.
    """
    toward_negative, toward_positive = extents
    normal = sketch.xDirection.crossProduct(sketch.yDirection)
    if abs(abs(normal.y) - 1.0) > 1e-6:
        raise RuntimeError(f"{name}: sketch normal is not along the rod")
    if normal.y > 0:
        side_one, side_two = toward_positive, toward_negative
    else:
        side_one, side_two = toward_negative, toward_positive
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(_collect(profiles_list), operation)
    extrude_input.setTwoSidesExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString(side_one)
        ),
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString(side_two)
        ),
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


def _require_constrained(sketch):
    print(f"  {sketch.name} sketch fully constrained: {sketch.isFullyConstrained}")
    if not sketch.isFullyConstrained:
        raise RuntimeError(f"{sketch.name} sketch is not fully constrained")


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


# pylint: disable-next=too-many-arguments,too-many-positional-arguments,too-many-locals
def _build_annulus(component, plane, name, bore, outer, extents, operation):
    """Annulus about the rod axis; diameters and (-y, +y) extents from expressions."""
    sketch = component.sketches.add(plane)
    sketch.name = name
    circles = sketch.sketchCurves.sketchCircles
    inner = circles.addByCenterRadius(_point(0, 0), 10.0 * MM)
    outer_circle = circles.addByCenterRadius(_point(0, 0), 12.0 * MM)
    constraints = sketch.geometricConstraints
    constraints.addCoincident(inner.centerSketchPoint, sketch.originPoint)
    constraints.addConcentric(inner, outer_circle)
    dimensions = sketch.sketchDimensions
    for circle, expression, text_z in ((inner, bore, 5.0), (outer_circle, outer, -5.0)):
        dimension = dimensions.addDiameterDimension(circle, _point(30.0, text_z))
        dimension.parameter.expression = expression
    _require_constrained(sketch)
    _extrude_along_rod(
        component, sketch, [_annulus_profile(sketch)], extents, operation, name
    )


# pylint: disable-next=too-many-locals
def _build_pocket(component):
    """Revolved cut: the ring's pocket with 45 deg ledges, closed on the axis.

    Sketched on the XY plane, x is radius and y runs along the rod. The
    profile is a trapezoid from the pocket bore at +/- pocketWidth/2 out to
    the rod bore at +/- (pocketWidth/2 + pocketChamfer), extended in to the
    axis so the revolve is a solid. Each pair of corners is symmetric about
    the projected X axis, so the only dimensions are two radii and two
    half-widths and nothing can mirror.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = "Pocket profile"
    rod_axis = sketch.project(component.yConstructionAxis).item(0)
    radial_axis = sketch.project(component.xConstructionAxis).item(0)
    rod_axis.isConstruction = True
    radial_axis.isConstruction = True

    def at(radius_mm, along_mm):
        return sketch.modelToSketchSpace(
            adsk.core.Point3D.create(radius_mm * MM, along_mm * MM, 0)
        )

    half_band = BAND_WIDTH / 2.0
    half_pocket = POCKET_WIDTH / 2.0
    corners = [
        at(0.0, -half_band),
        at(COLLAR_BORE_RADIUS, -half_band),
        at(POCKET_BORE_RADIUS, -half_pocket),
        at(POCKET_BORE_RADIUS, half_pocket),
        at(COLLAR_BORE_RADIUS, half_band),
        at(0.0, half_band),
    ]
    lines = _polyline(sketch, corners)
    points = [line.startSketchPoint for line in lines]
    constraints = sketch.geometricConstraints
    constraints.addCoincident(points[0], rod_axis)
    constraints.addParallel(lines[0], radial_axis)
    for low, high in ((0, 5), (1, 4), (2, 3)):
        constraints.addSymmetry(points[low], points[high], radial_axis)
    dimensions = sketch.sketchDimensions
    for point, line, expression, text in (
        (points[1], rod_axis, f"({COLLAR_BORE}) / 2", (8.0, -half_band - 3.0)),
        (points[2], rod_axis, f"({POCKET_BORE}) / 2", (8.0, half_pocket + 3.0)),
        (points[1], radial_axis, "bandWidth / 2", (COLLAR_BORE_RADIUS + 3.0, -4.0)),
        (points[2], radial_axis, "pocketWidth / 2", (POCKET_BORE_RADIUS + 3.0, 2.0)),
    ):
        dimension = dimensions.addOffsetDimension(line, point, at(*text))
        dimension.parameter.expression = expression
    _require_constrained(sketch)
    revolves = component.features.revolveFeatures
    revolve_input = revolves.createInput(
        _collect(_all_profiles(sketch)),
        component.yConstructionAxis,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    revolve_input.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
    feature = revolves.add(revolve_input)
    feature.name = "Pocket"


# pylint: disable-next=too-many-locals
def _build_outer_cone(component):
    """Revolved cut turning the band's label-side outer step into a 45 deg cone.

    The triangle's hypotenuse runs from the band's outer radius at
    pocketWidth/2 + chamferShift to the lip's outer radius at
    bandWidth/2 + chamferShift, parallel to the pocket's own ledge and
    collarWall away from it. With that side of the collar on the bed the
    step would otherwise be a flat overhang.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = "Outer cone profile"
    rod_axis = sketch.project(component.yConstructionAxis).item(0)
    radial_axis = sketch.project(component.xConstructionAxis).item(0)
    rod_axis.isConstruction = True
    radial_axis.isConstruction = True

    def at(radius_mm, along_mm):
        return sketch.modelToSketchSpace(
            adsk.core.Point3D.create(radius_mm * MM, along_mm * MM, 0)
        )

    tip_y = POCKET_WIDTH / 2.0 + CHAMFER_SHIFT
    base_y = BAND_WIDTH / 2.0 + CHAMFER_SHIFT
    lines = _polyline(
        sketch,
        [
            at(BAND_OUTER_RADIUS, tip_y),
            at(BAND_OUTER_RADIUS, base_y),
            at(LIP_OUTER_RADIUS, base_y),
        ],
    )
    tip, corner, foot = (line.startSketchPoint for line in lines)
    constraints = sketch.geometricConstraints
    constraints.addParallel(lines[0], rod_axis)
    constraints.addParallel(lines[1], radial_axis)
    dimensions = sketch.sketchDimensions
    for point, line, expression, text in (
        (tip, rod_axis, f"({BAND_OUTER}) / 2", (BAND_OUTER_RADIUS / 2.0, tip_y - 2.0)),
        (foot, rod_axis, f"({LIP_OUTER}) / 2", (LIP_OUTER_RADIUS / 2.0, base_y + 2.0)),
        (
            tip,
            radial_axis,
            "pocketWidth / 2 + chamferShift",
            (BAND_OUTER_RADIUS + 3.0, tip_y / 2.0),
        ),
        (
            foot,
            radial_axis,
            "bandWidth / 2 + chamferShift",
            (LIP_OUTER_RADIUS - 3.0, base_y / 2.0),
        ),
    ):
        dimension = dimensions.addOffsetDimension(line, point, at(*text))
        dimension.parameter.expression = expression
    del corner
    _require_constrained(sketch)
    revolves = component.features.revolveFeatures
    revolve_input = revolves.createInput(
        _collect(_all_profiles(sketch)),
        component.yConstructionAxis,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    revolve_input.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
    feature = revolves.add(revolve_input)
    feature.name = "Outer cone"


def _build_mouth(component, plane):
    """Mouth wedge apexed on the axis: the clip's construction, reused."""
    sketch = component.sketches.add(plane)
    sketch.name = "Mouth"
    spread = math.radians(MOUTH_HALF_ANGLE_DEG)
    reach = (BAND_OUTER_RADIUS + 5.0) / math.cos(spread)
    # pylint: disable-next=unbalanced-tuple-unpacking
    apex_to_right, right_to_top, _top_to_left, left_to_apex = _polyline(
        sketch,
        [
            _point(0.0, 0.0),
            _point(reach * math.sin(spread), reach * math.cos(spread)),
            _point(0.0, reach),
            _point(-reach * math.sin(spread), reach * math.cos(spread)),
        ],
    )
    constraints = sketch.geometricConstraints
    constraints.addCoincident(apex_to_right.startSketchPoint, sketch.originPoint)
    centre = _construction_line(sketch, 0.0, reach)
    constraints.addVertical(centre)
    constraints.addCoincident(centre.endSketchPoint, right_to_top.endSketchPoint)
    reach_expression = f"(({BAND_OUTER}) / 2 + 5 mm) / cos(mouthHalfAngleDeg)"
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
    _require_constrained(sketch)
    _extrude(
        component,
        _all_profiles(sketch),
        "collarWidth + 10 mm",
        adsk.fusion.FeatureOperations.CutFeatureOperation,
        "Mouth",
    )


def _stem_direction():
    """Unit vector along the clip's stem in model space (x forward, z up)."""
    angle = math.radians(STEM_ANGLE_DEG)
    return adsk.core.Vector3D.create(math.cos(angle), 0.0, -math.sin(angle))


def _build_stem_plane(component):
    """Plane through the rod axis whose normal is the stem direction."""
    planes = component.constructionPlanes
    wanted = _stem_direction()
    for expression in ("stemAngleDeg", "-stemAngleDeg"):
        plane_input = planes.createInput()
        plane_input.setByAngle(
            component.yConstructionAxis,
            adsk.core.ValueInput.createByString(expression),
            component.yZConstructionPlane,
        )
        plane = planes.add(plane_input)
        normal = plane.geometry.normal
        if abs(abs(normal.dotProduct(wanted)) - 1.0) < 1e-6:
            plane.name = "Stem plane"
            return plane
        plane.deleteMe()
    raise RuntimeError("stem plane normal never matched the stem direction")


def _section_point(sketch, along_mm, across_mm):
    """Sketch point on the stem plane: along the rod, across the stem."""
    angle = math.radians(STEM_ANGLE_DEG)
    model = adsk.core.Point3D.create(
        across_mm * math.sin(angle) * MM,
        along_mm * MM,
        across_mm * math.cos(angle) * MM,
    )
    return sketch.modelToSketchSpace(model)


# pylint: disable-next=too-many-locals
def _build_stem_slot(component, plane):
    """Cut the band at the stem angle so the clip's stem passes through.

    Cross-section pocketWidth along the rod by stemThickness +
    slotClearance across, symmetric both ways about the axis, cut outward
    from just inside the pocket bore to beyond the band.
    """
    sketch = component.sketches.add(plane)
    sketch.name = "Stem slot section"
    axis = sketch.project(component.yConstructionAxis).item(0)
    axis.isConstruction = True
    half_along = POCKET_WIDTH / 2.0
    half_across = SLOT_WIDTH / 2.0
    lines = _polyline(
        sketch,
        [
            _section_point(sketch, -half_along, half_across),
            _section_point(sketch, half_along, half_across),
            _section_point(sketch, half_along, -half_across),
            _section_point(sketch, -half_along, -half_across),
        ],
    )
    top, far, bottom, near = lines  # pylint: disable=unbalanced-tuple-unpacking
    constraints = sketch.geometricConstraints
    constraints.addParallel(top, axis)
    constraints.addParallel(bottom, axis)
    constraints.addPerpendicular(near, axis)
    constraints.addPerpendicular(far, axis)
    constraints.addSymmetry(top, bottom, axis)
    centre = sketch.sketchCurves.sketchLines.addByTwoPoints(
        _section_point(sketch, 0.0, 0.0), _section_point(sketch, 0.0, 6.0)
    )
    centre.isConstruction = True
    constraints.addCoincident(centre.startSketchPoint, sketch.originPoint)
    constraints.addPerpendicular(centre, axis)
    length = sketch.sketchDimensions.addDistanceDimension(
        centre.startSketchPoint,
        centre.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        _section_point(sketch, 2.0, 5.0),
    )
    length.parameter.expression = "stemThickness * 2"
    constraints.addSymmetry(near, far, centre)
    for line_one, line_two, expression, text in (
        (top, bottom, "stemThickness + slotClearance", (half_along + 4.0, 0.0)),
        (near, far, "pocketWidth", (0.0, -half_across - 3.0)),
    ):
        dimension = sketch.sketchDimensions.addOffsetDimension(
            line_one, line_two, _section_point(sketch, *text)
        )
        dimension.parameter.expression = expression
    _require_constrained(sketch)

    normal = sketch.xDirection.crossProduct(sketch.yDirection)
    outward = normal.dotProduct(_stem_direction())
    if abs(abs(outward) - 1.0) > 1e-6:
        raise RuntimeError("stem slot sketch normal is not along the stem")
    start = f"({POCKET_BORE}) / 2 - 1 mm"
    length_expression = f"({BAND_OUTER}) / 2 - ({POCKET_BORE}) / 2 + 4 mm"
    if outward > 0:
        offset = start
        direction = adsk.fusion.ExtentDirections.PositiveExtentDirection
    else:
        offset = f"-({start})"
        direction = adsk.fusion.ExtentDirections.NegativeExtentDirection
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        _collect(_all_profiles(sketch)),
        adsk.fusion.FeatureOperations.CutFeatureOperation,
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
    feature.name = "Stem slot"


def _build_body(component):
    plane = component.xZConstructionPlane
    _build_annulus(
        component,
        plane,
        "Lips",
        COLLAR_BORE,
        LIP_OUTER,
        ("farExtent", "collarWidth - farExtent"),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    _build_annulus(
        component,
        plane,
        "Band",
        COLLAR_BORE,
        BAND_OUTER,
        ("bandWidth / 2", "bandWidth / 2 + chamferShift"),
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
    )
    _build_outer_cone(component)
    _build_pocket(component)
    _build_mouth(component, plane)
    _build_stem_slot(component, _build_stem_plane(component))


def _check_fit():
    """The clip must drop into the pocket; fail before building otherwise."""
    problems = []
    if RING_OUTER_DIAMETER >= 2.0 * POCKET_BORE_RADIUS:
        problems.append("ring OD does not clear the pocket bore")
    if RING_WIDTH >= POCKET_WIDTH:
        problems.append("ring width does not clear the pocket width")
    if STEM_THICKNESS >= SLOT_WIDTH:
        problems.append("stem does not clear the slot")
    near_lip = NEAR_EXTENT - BAND_WIDTH / 2.0
    if near_lip < 2.0:
        problems.append(f"label-side lip only {near_lip:.1f} mm; widen collarWidth")
    if problems:
        raise RuntimeError(f"clip will not fit the collar: {problems}")
    print(
        f"  fit: pocket {2 * POCKET_BORE_RADIUS:.1f} x {POCKET_WIDTH:.1f} over ring "
        f"{RING_OUTER_DIAMETER} x {RING_WIDTH}; slot {SLOT_WIDTH:.1f} over stem "
        f"{STEM_THICKNESS}; label-side lip {near_lip:.1f} mm, far land "
        f"{FAR_LIP:.1f} mm; collar spans y {-FAR_EXTENT:.1f} to {NEAR_EXTENT:.1f}"
    )


def _probe(body, x_mm, y_mm, z_mm):
    point = adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z_mm * MM)
    return body.pointContainment(point)


def _verify(body):  # pylint: disable=too-many-locals,too-many-statements
    """Numeric probes; raise on any surprise so the failure is loud."""
    inside = adsk.fusion.PointContainment.PointInsidePointContainment
    outside = adsk.fusion.PointContainment.PointOutsidePointContainment
    lip_mid = COLLAR_BORE_RADIUS + COLLAR_WALL / 2.0
    band_mid = POCKET_BORE_RADIUS + COLLAR_WALL / 2.0
    pocket_mid = (COLLAR_BORE_RADIUS + POCKET_BORE_RADIUS) / 2.0
    near_y = NEAR_EXTENT - 1.0
    far_y = -(FAR_EXTENT - FAR_LIP / 2.0)
    half_pocket = POCKET_WIDTH / 2.0
    stem = math.radians(-STEM_ANGLE_DEG)
    flank = math.radians(math.degrees(math.atan((SLOT_WIDTH / 2.0 + 1.5) / band_mid)))

    def polar(angle, radius, y_mm):
        return (radius * math.cos(angle), y_mm, radius * math.sin(angle))

    down, back, up = math.radians(270.0), math.radians(180.0), math.radians(90.0)
    open_at = math.radians(90.0 - MOUTH_HALF_ANGLE_DEG / 2.0)
    closed_at = math.radians(90.0 - MOUTH_HALF_ANGLE_DEG - 12.0)
    checks = [
        ("lip bears on rod, +y", polar(down, lip_mid, near_y), inside),
        ("far land bears on rod, -y", polar(down, lip_mid, far_y), inside),
        ("lip bears on rod, back", polar(back, lip_mid, near_y), inside),
        ("nothing past far land", polar(down, lip_mid, -FAR_EXTENT - 1.0), outside),
        (
            "bore clear under lip",
            polar(down, COLLAR_BORE_RADIUS - 0.3, near_y),
            outside,
        ),
        ("pocket empty, centre", polar(back, pocket_mid, 0.0), outside),
        ("pocket empty, edge", polar(down, pocket_mid, half_pocket - 0.3), outside),
        ("band over pocket", polar(back, band_mid, 0.0), inside),
        ("band over pocket, bottom", polar(down, band_mid, 0.0), inside),
        (
            "chamfer void",
            polar(back, COLLAR_BORE_RADIUS + 0.4, half_pocket + 0.6),
            outside,
        ),
        (
            "solid past chamfer",
            polar(back, COLLAR_BORE_RADIUS + 0.4, half_pocket + CHAMFER + 0.4),
            inside,
        ),
        (
            "outer cone removed the step",
            polar(back, BAND_OUTER_RADIUS - 0.4, half_pocket + CHAMFER - 0.2),
            outside,
        ),
        (
            "wall full under outer cone",
            polar(back, POCKET_BORE_RADIUS - 0.6, half_pocket + CHAMFER - 0.2),
            inside,
        ),
        (
            "no step left at lip",
            polar(
                back,
                LIP_OUTER_RADIUS + 0.3,
                half_pocket + CHAMFER + CHAMFER_SHIFT + 0.3,
            ),
            outside,
        ),
        ("mouth at top", polar(up, lip_mid, near_y), outside),
        ("mouth open", polar(open_at, band_mid, 0.0), outside),
        ("closed below mouth", polar(closed_at, lip_mid, near_y), inside),
        ("slot clear for stem", polar(stem, band_mid, 0.0), outside),
        (
            "slot clear, stem edge",
            polar(stem, band_mid, RING_WIDTH / 2.0 - 0.3),
            outside,
        ),
        ("slot wall, one side", polar(stem + flank, band_mid, 0.0), inside),
        ("slot wall, other side", polar(stem - flank, band_mid, 0.0), inside),
        ("lip continuous at stem", polar(stem, lip_mid, near_y), inside),
        ("beyond band", polar(back, BAND_OUTER_RADIUS + 1.0, 0.0), outside),
    ]
    failures = []
    for label, (x_mm, y_mm, z_mm), expected in checks:
        actual = _probe(body, x_mm, y_mm, z_mm)
        state = "ok" if actual == expected else f"FAIL (got {actual})"
        print(f"  probe {label:26s} ({x_mm:6.1f},{y_mm:6.1f},{z_mm:6.1f}) {state}")
        if actual != expected:
            failures.append(label)
    bounding = body.boundingBox
    for label, value, expected in (
        ("min y", bounding.minPoint.y / MM, -FAR_EXTENT),
        ("max y", bounding.maxPoint.y / MM, NEAR_EXTENT),
        ("min z", bounding.minPoint.z / MM, -BAND_OUTER_RADIUS),
    ):
        if abs(value - expected) > 0.01:
            failures.append(f"bbox {label} {value:.2f}, expected {expected:.2f}")
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
    edit, so compare the geometry against the volume recorded by the last
    scripted save. Same volume, benign save, carry on. Different, stop: an
    edit is sitting there and rebuilding would discard it.
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
    """Delete user parameters this script no longer declares."""
    user_parameters = design.userParameters
    for index in range(user_parameters.count - 1, -1, -1):
        parameter = user_parameters.item(index)
        if parameter.unit != ALL_PARAMETER_UNITS.get(parameter.name):
            print(f"  dropping stale parameter {parameter.name}")
            parameter.deleteMe()


def run(_context: str):
    """Build the collar into its saved document, verify, export, version."""
    _check_fit()
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
    _build_body(component)

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
        f"scripted label collar build {datetime.date.today().isoformat()}: "
        f"rod {ROD_OUTER_DIAMETER} mm, width {COLLAR_WIDTH:.0f} mm one-sided, over ring "
        f"{RING_OUTER_DIAMETER} x {RING_WIDTH:.0f} mm, stem {STEM_ANGLE_DEG:.0f} deg"
    )
    description += f" vol {body.volume / (MM ** 3):.0f} mm3"
    if data_file is None:
        document.saveAs(DOC_NAME, folder, description, "")
    else:
        document.save(description)
    print(f"saved '{DOC_NAME}' in project '{FUSION_PROJECT_NAME}': {description}")
    print("build complete")
