"""Fusion 360 script: press-fit end cap for the spool cradle rods.

Run inside Fusion via scripts/run_in_fusion.py (no --variant; this script
builds exactly one part). A stem grips the bore of the 1" schedule 40 PVC
rod and a flange a couple of millimetres proud of the pipe OD stops the rod
walking axially out of the bracket saddles. Print FOUR per shelf level (two
rods x two ends), flange down, no supports.

The stem slips the bore (bore - 0.6) and four axial crush ribs (bore + 0.4)
take up the press fit, so real-world bore variation lands on sandable ribs
rather than a rigid plug. The revolve profile and the rib are fully
constrained sketches dimensioned against the user parameters, and the ribs
are a circular pattern driven by endCapRibCount — the whole part is
live-editable in Fusion, and each scripted rebuild saves a new version of
the "Rod End Cap" document in the "LAN Spool Shelf" cloud project.

This file deliberately repeats the small MCP/save/export scaffolding from
build_rod_bracket.py instead of importing a shared module: Fusion's
persistent interpreter caches imported modules across runs (see the
fusion-360-mcp skill's api-traps), so each script stays self-contained.
"""

import datetime
import math

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are centimetres

PROJECT_DIR = "/Users/mhuot/lan-spool-shelf"
FUSION_PROJECT_NAME = "LAN Spool Shelf"
DOC_NAME = "Rod End Cap"
EXPORT_NAME = "rod_end_cap"

# --- Dimensions (mm) --------------------------------------------------------
ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC, matches the bracket saddles
PIPE_INNER_DIAMETER = 26.6  # 1" schedule 40 PVC bore
END_CAP_FLANGE_PROUD = 2.0  # flange radius beyond the pipe outer radius
END_CAP_FLANGE_THICKNESS = 4.0
END_CAP_STEM_LENGTH = 14.0
END_CAP_STEM_DIAMETER = PIPE_INNER_DIAMETER - 0.6  # slip fit
END_CAP_RIB_DIAMETER = PIPE_INNER_DIAMETER + 0.4  # crush fit on the ribs
END_CAP_TIP_CHAMFER = 1.5
END_CAP_RIB_WIDTH = 2.0
END_CAP_RIB_COUNT = 4

_DRIVING = "drives the model; safe to edit live in Fusion"
PARAMETERS = {
    "rodOuterDiameter": (ROD_OUTER_DIAMETER, _DRIVING),
    "pipeInnerDiameter": (PIPE_INNER_DIAMETER, _DRIVING),
    "endCapFlangeProud": (END_CAP_FLANGE_PROUD, _DRIVING),
    "endCapFlangeThickness": (END_CAP_FLANGE_THICKNESS, _DRIVING),
    "endCapStemLength": (END_CAP_STEM_LENGTH, _DRIVING),
    "endCapStemDiameter": ("pipeInnerDiameter - 0.6 mm", _DRIVING),
    "endCapRibDiameter": ("pipeInnerDiameter + 0.4 mm", _DRIVING),
    "endCapTipChamfer": (END_CAP_TIP_CHAMFER, _DRIVING),
    "endCapRibWidth": (END_CAP_RIB_WIDTH, _DRIVING),
    "endCapRibCount": (str(END_CAP_RIB_COUNT), _DRIVING),
}
UNITLESS_PARAMETERS = {"endCapRibCount"}


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


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _dimension(sketch, point_a, point_b, orientation, expression, text_x, text_z):
    dimension = sketch.sketchDimensions.addDistanceDimension(
        point_a, point_b, orientation, _point(text_x, text_z)
    )
    dimension.parameter.expression = expression


def _ensure_parameters(design):
    user_parameters = design.userParameters
    for name, (value, comment) in PARAMETERS.items():
        expression = value if isinstance(value, str) else f"{value} mm"
        units = "" if name in UNITLESS_PARAMETERS else "mm"
        existing = user_parameters.itemByName(name)
        if existing:
            existing.expression = expression
            existing.comment = comment
        else:
            user_parameters.add(
                name,
                adsk.core.ValueInput.createByString(expression),
                units,
                comment,
            )


def _build_body(
    component, plane
):  # pylint: disable=too-many-locals,too-many-statements
    """Revolved flange + stem, one constrained rib, circular-patterned."""
    horizontal = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    vertical = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

    flange_radius = ROD_OUTER_DIAMETER / 2.0 + END_CAP_FLANGE_PROUD
    stem_radius = END_CAP_STEM_DIAMETER / 2.0
    rib_radius = END_CAP_RIB_DIAMETER / 2.0
    tip_z = END_CAP_FLANGE_THICKNESS + END_CAP_STEM_LENGTH
    chamfer = END_CAP_TIP_CHAMFER

    profile = component.sketches.add(plane)
    profile.name = "End cap profile"
    lines = _polyline(
        profile,
        [
            (0.0, 0.0),
            (flange_radius, 0.0),
            (flange_radius, END_CAP_FLANGE_THICKNESS),
            (stem_radius, END_CAP_FLANGE_THICKNESS),
            (stem_radius, tip_z - chamfer),
            (stem_radius - chamfer, tip_z),
            (0.0, tip_z),
        ],
    )
    # pylint: disable-next=unbalanced-tuple-unpacking
    bottom, rim, flange_top, stem_side, tip_chamfer, top, axis = lines
    constraints = profile.geometricConstraints
    for line in (bottom, flange_top, top):
        constraints.addHorizontal(line)
    for line in (rim, stem_side, axis):
        constraints.addVertical(line)
    constraints.addCoincident(bottom.startSketchPoint, profile.originPoint)
    _dimension(
        profile,
        bottom.startSketchPoint,
        bottom.endSketchPoint,
        horizontal,
        "rodOuterDiameter / 2 + endCapFlangeProud",
        8.0,
        -4.0,
    )
    _dimension(
        profile,
        rim.startSketchPoint,
        rim.endSketchPoint,
        vertical,
        "endCapFlangeThickness",
        flange_radius + 4.0,
        2.0,
    )
    _dimension(
        profile,
        bottom.startSketchPoint,
        flange_top.endSketchPoint,
        horizontal,
        "endCapStemDiameter / 2",
        6.0,
        END_CAP_FLANGE_THICKNESS + 3.0,
    )
    _dimension(
        profile,
        bottom.startSketchPoint,
        top.endSketchPoint,
        vertical,
        "endCapFlangeThickness + endCapStemLength",
        -5.0,
        tip_z / 2.0,
    )
    _dimension(
        profile,
        tip_chamfer.startSketchPoint,
        tip_chamfer.endSketchPoint,
        horizontal,
        "endCapTipChamfer",
        stem_radius + 3.0,
        tip_z + 2.0,
    )
    _dimension(
        profile,
        tip_chamfer.startSketchPoint,
        tip_chamfer.endSketchPoint,
        vertical,
        "endCapTipChamfer",
        stem_radius + 5.0,
        tip_z - 2.0,
    )

    revolves = component.features.revolveFeatures
    revolve_input = revolves.createInput(
        profile.profiles.item(0),
        component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    revolve_input.setAngleExtent(
        False, adsk.core.ValueInput.createByReal(2.0 * math.pi)
    )
    revolves.add(revolve_input).name = "End cap revolve"

    rib_inner = stem_radius - 1.0  # embedded 1 mm into the stem
    rib_z0 = END_CAP_FLANGE_THICKNESS + 1.0
    rib_z1 = tip_z - 2.0
    rib_lead = 1.5  # slanted top so the pipe end rides onto the rib
    rib = component.sketches.add(plane)
    rib.name = "Crush rib"
    rib_lines = _polyline(
        rib,
        [
            (rib_inner, rib_z0),
            (rib_radius, rib_z0),
            (rib_radius, rib_z1 - rib_lead),
            (rib_inner, rib_z1),
        ],
    )
    # pylint: disable-next=unbalanced-tuple-unpacking
    rib_bottom, rib_outer, _rib_slant, rib_inner_line = rib_lines
    rib_constraints = rib.geometricConstraints
    rib_constraints.addHorizontal(rib_bottom)
    rib_constraints.addVertical(rib_outer)
    rib_constraints.addVertical(rib_inner_line)
    _dimension(
        rib,
        rib.originPoint,
        rib_bottom.startSketchPoint,
        horizontal,
        "endCapStemDiameter / 2 - 1 mm",
        6.0,
        rib_z0 - 3.0,
    )
    _dimension(
        rib,
        rib.originPoint,
        rib_bottom.startSketchPoint,
        vertical,
        "endCapFlangeThickness + 1 mm",
        rib_inner - 4.0,
        rib_z0 / 2.0,
    )
    _dimension(
        rib,
        rib.originPoint,
        rib_bottom.endSketchPoint,
        horizontal,
        "endCapRibDiameter / 2",
        8.0,
        rib_z0 - 6.0,
    )
    _dimension(
        rib,
        rib.originPoint,
        # the closing line runs D -> A, so its START is the top-inner corner
        rib_inner_line.startSketchPoint,
        vertical,
        "endCapFlangeThickness + endCapStemLength - 2 mm",
        rib_inner - 7.0,
        rib_z1 / 2.0,
    )
    _dimension(
        rib,
        rib.originPoint,
        rib_outer.endSketchPoint,
        vertical,
        "endCapFlangeThickness + endCapStemLength - 3.5 mm",
        rib_radius + 4.0,
        rib_z1 / 2.0,
    )

    extrudes = component.features.extrudeFeatures
    rib_profiles = adsk.core.ObjectCollection.create()
    rib_profiles.add(rib.profiles.item(0))
    rib_input = extrudes.createInput(
        rib_profiles, adsk.fusion.FeatureOperations.JoinFeatureOperation
    )
    rib_input.setSymmetricExtent(
        adsk.core.ValueInput.createByString("endCapRibWidth"), True
    )
    rib_extrude = extrudes.add(rib_input)
    rib_extrude.name = "Crush rib"

    patterns = component.features.circularPatternFeatures
    pattern_entities = adsk.core.ObjectCollection.create()
    pattern_entities.add(rib_extrude)
    pattern_input = patterns.createInput(pattern_entities, component.zConstructionAxis)
    pattern_input.quantity = adsk.core.ValueInput.createByString("endCapRibCount")
    pattern_input.totalAngle = adsk.core.ValueInput.createByString("360 deg")
    pattern_input.isSymmetric = False
    patterns.add(pattern_input).name = "Crush ribs"


def _probe(body, x_mm, y_mm, z_mm):
    point = adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z_mm * MM)
    return body.pointContainment(point)


def _verify(body):  # pylint: disable=too-many-locals
    """Numeric probes; raise on any surprise so the failure is loud."""
    inside = adsk.fusion.PointContainment.PointInsidePointContainment
    outside = adsk.fusion.PointContainment.PointOutsidePointContainment
    flange_radius = ROD_OUTER_DIAMETER / 2.0 + END_CAP_FLANGE_PROUD
    stem_radius = END_CAP_STEM_DIAMETER / 2.0
    rib_radius = END_CAP_RIB_DIAMETER / 2.0
    tip_z = END_CAP_FLANGE_THICKNESS + END_CAP_STEM_LENGTH
    rib_mid = (stem_radius + rib_radius) / 2.0
    diagonal = rib_mid / math.sqrt(2.0)
    mid_stem = (END_CAP_FLANGE_THICKNESS + tip_z) / 2.0
    checks = [
        (
            "flange rim",
            flange_radius - 1.5,
            0.0,
            END_CAP_FLANGE_THICKNESS / 2.0,
            inside,
        ),
        ("above flange, off stem", flange_radius - 1.5, 0.0, mid_stem, outside),
        ("stem core", 0.0, 0.0, mid_stem, inside),
        ("stem surface", stem_radius - 0.5, 0.0, mid_stem, inside),
        ("rib +X", rib_mid, 0.0, mid_stem, inside),
        ("rib +Y", 0.0, rib_mid, mid_stem, inside),
        ("no rib at 45 degrees", diagonal, diagonal, mid_stem, outside),
        ("tip chamfer relieved", stem_radius - 0.3, 0.0, tip_z - 0.3, outside),
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


# pylint: disable-next=too-many-locals
def run(_context: str):
    """Build the end cap into its saved document, verify, export, version."""
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
        f"scripted end cap build {datetime.date.today().isoformat()}: "
        f"pipe bore {PIPE_INNER_DIAMETER} mm, flange proud {END_CAP_FLANGE_PROUD} mm"
    )
    if data_file is None:
        document.saveAs(DOC_NAME, folder, description, "")
    else:
        document.save(description)
    print(f"saved '{DOC_NAME}' in project '{FUSION_PROJECT_NAME}': {description}")
    print("build complete")
