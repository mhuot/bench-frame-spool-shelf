"""Fusion 360 script: snap-on label clip for the spool cradle rods.

Run inside Fusion via scripts/run_in_fusion.py. A C-clip snaps onto a rod
from below and slides along it to sit under its spool; a paddle hangs
down-forward carrying a label face (fits 12 mm label-maker tape) tilted up
toward the viewer. Print one per spool.

Geometry, with the rod axis as the model Y axis through the origin:
- The ring wraps the bottom 220 degrees of the rod. The 140-degree mouth at
  the top leaves the spool's resting contact point (~23 degrees off
  vertical) untouched, and its 32 mm opening snaps over the 33.4 mm rod
  with ~1.4 mm of interference — an easy spring for a 2.4 mm wall.
- The paddle leaves the ring at 50 degrees below horizontal-forward, so the
  label face's normal points 40 degrees above horizontal: readable from a
  standing position, clear of the spool's surface.

Print label-face-down (rotate so the face sits on the plate — glossy face
off smooth PEI) with supports on build plate only under the hovering ring.

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

# --- Dimensions (mm) --------------------------------------------------------
ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC, as on the shelf
CLIP_CLEARANCE = 0.7  # diametral: slides and spins freely on the rod
CLIP_WALL = 2.4
CLIP_WIDTH = 9.0  # along the rod
MOUTH_HALF_ANGLE_DEG = 70.0  # mouth spans +/-70 deg about straight up
PADDLE_ANGLE_DEG = -50.0  # paddle direction below horizontal-forward
PADDLE_THICKNESS = 2.4
STEM_END_RADIUS = 31.0  # stem runs from inside the ring wall out to here
FACE_END_RADIUS = 48.0  # label face occupies stem end .. here (17 mm)
FACE_WIDTH = 55.0  # along the rod; fits under one 70 mm spool slot

CLIP_INNER_RADIUS = (ROD_OUTER_DIAMETER + CLIP_CLEARANCE) / 2.0
CLIP_OUTER_RADIUS = CLIP_INNER_RADIUS + CLIP_WALL

_DRIVING = "drives the model; safe to edit live in Fusion"
_REFERENCE = "reference only — edit scripts/build_rod_label_clip.py and rebuild"
PARAMETERS = {
    "clipWidth": (CLIP_WIDTH, _DRIVING),
    "faceWidth": (FACE_WIDTH, _DRIVING),
    "rodOuterDiameter": (ROD_OUTER_DIAMETER, _REFERENCE),
    "clipClearance": (CLIP_CLEARANCE, _REFERENCE),
    "clipWall": (CLIP_WALL, _REFERENCE),
    "mouthHalfAngleDeg": (MOUTH_HALF_ANGLE_DEG, _REFERENCE),
    "paddleAngleDeg": (PADDLE_ANGLE_DEG, _REFERENCE),
    "paddleThickness": (PADDLE_THICKNESS, _REFERENCE),
    "stemEndRadius": (STEM_END_RADIUS, _REFERENCE),
    "faceEndRadius": (FACE_END_RADIUS, _REFERENCE),
}


def _point(x_mm, z_mm):
    """Sketch point on the XZ plane (sketch +y is model MINUS Z)."""
    return adsk.core.Point3D.create(x_mm * MM, -z_mm * MM, 0)


def _add_polygon(sketch, points_mm):
    lines = sketch.sketchCurves.sketchLines
    count = len(points_mm)
    for index in range(count):
        start = _point(*points_mm[index])
        end = _point(*points_mm[(index + 1) % count])
        lines.addByTwoPoints(start, end)


def _extrude_profiles(component, profiles_list, width, operation, name):
    profiles = adsk.core.ObjectCollection.create()
    for profile in profiles_list:
        profiles.add(profile)
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(profiles, operation)
    if isinstance(width, str):
        width_input = adsk.core.ValueInput.createByString(width)
    else:
        width_input = adsk.core.ValueInput.createByReal(width * MM)
    extrude_input.setSymmetricExtent(width_input, True)
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


def _all_profiles(sketch):
    return [sketch.profiles.item(i) for i in range(sketch.profiles.count)]


def _annulus_profile(sketch):
    """The profile with two loops (ring), not the inner disc."""
    for profile in _all_profiles(sketch):
        if profile.profileLoops.count == 2:
            return profile
    raise RuntimeError("no annulus profile found")


def _ensure_parameters(design):
    user_parameters = design.userParameters
    for name, (value, comment) in PARAMETERS.items():
        expression = value if isinstance(value, str) else f"{value} mm"
        existing = user_parameters.itemByName(name)
        if existing:
            existing.expression = expression
            existing.comment = comment
        else:
            user_parameters.add(
                name,
                adsk.core.ValueInput.createByString(expression),
                "mm",
                comment,
            )


def _paddle_rectangle(radius_from, radius_to):
    """Corners of a paddle-plane strip between two radii from the rod axis."""
    angle = math.radians(PADDLE_ANGLE_DEG)
    along = (math.cos(angle), math.sin(angle))
    perpendicular = (-math.sin(angle), math.cos(angle))
    half = PADDLE_THICKNESS / 2.0
    corners = []
    for radius, side in (
        (radius_from, 1.0),
        (radius_to, 1.0),
        (radius_to, -1.0),
        (radius_from, -1.0),
    ):
        corners.append(
            (
                radius * along[0] + side * half * perpendicular[0],
                radius * along[1] + side * half * perpendicular[1],
            )
        )
    return corners


def _build_body(component, plane):
    join = adsk.fusion.FeatureOperations.JoinFeatureOperation
    cut = adsk.fusion.FeatureOperations.CutFeatureOperation
    new_body = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    ring = component.sketches.add(plane)
    ring.name = "Ring"
    for radius in (CLIP_INNER_RADIUS, CLIP_OUTER_RADIUS):
        ring.sketchCurves.sketchCircles.addByCenterRadius(_point(0, 0), radius * MM)
    _extrude_profiles(
        component, [_annulus_profile(ring)], "clipWidth", new_body, "Ring"
    )

    # Mouth: a fan-shaped cut about straight-up (+Z), symmetric in X, so no
    # arc sweep-direction signs are involved anywhere in this part.
    mouth = component.sketches.add(plane)
    mouth.name = "Mouth"
    reach = CLIP_OUTER_RADIUS + 10.0
    spread = math.radians(MOUTH_HALF_ANGLE_DEG)
    _add_polygon(
        mouth,
        [
            (0.0, 0.0),
            (reach * math.sin(spread), reach * math.cos(spread)),
            (0.0, reach),
            (-reach * math.sin(spread), reach * math.cos(spread)),
        ],
    )
    _extrude_profiles(
        component, _all_profiles(mouth), "clipWidth + 10 mm", cut, "Mouth"
    )

    stem = component.sketches.add(plane)
    stem.name = "Stem"
    _add_polygon(stem, _paddle_rectangle(CLIP_INNER_RADIUS + 0.5, STEM_END_RADIUS))
    _extrude_profiles(component, _all_profiles(stem), "clipWidth", join, "Stem")

    face = component.sketches.add(plane)
    face.name = "Label face"
    _add_polygon(face, _paddle_rectangle(STEM_END_RADIUS, FACE_END_RADIUS))
    _extrude_profiles(component, _all_profiles(face), "faceWidth", join, "Label face")


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
    angle = math.radians(PADDLE_ANGLE_DEG)
    stem_mid = (CLIP_INNER_RADIUS + STEM_END_RADIUS) / 2.0
    face_mid = (STEM_END_RADIUS + FACE_END_RADIUS) / 2.0
    checks = []
    for label, angle_deg, expected in (
        ("ring bottom", 270.0, inside),
        ("mouth at top", 90.0, outside),
        ("mouth at 45 deg", 45.0, outside),
        ("mouth at 135 deg", 135.0, outside),
        ("ring tip front", 10.0, inside),
        ("ring tip rear", 170.0, inside),
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
    ]
    failures = []
    for label, x_mm, y_mm, z_mm, expected in checks:
        actual = _probe(body, x_mm, y_mm, z_mm)
        state = "ok" if actual == expected else f"FAIL (got {actual})"
        print(f"  probe {label:22s} ({x_mm:6.1f},{y_mm:6.1f},{z_mm:6.1f}) {state}")
        if actual != expected:
            failures.append(label)
    if failures:
        raise RuntimeError(f"geometry probes failed: {failures}")


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
