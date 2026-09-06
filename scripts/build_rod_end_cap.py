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

# Set True only to deliberately discard a hand edit in the document.
ALLOW_OVERWRITE = False

PROJECT_DIR = "/Users/mhuot/lan-spool-shelf"
FUSION_PROJECT_NAME = "LAN Spool Shelf"
DOC_NAME = "Rod End Cap"
EXPORT_NAME = "rod_end_cap"

# --- Dimensions (mm) --------------------------------------------------------
ROD_OUTER_DIAMETER = 33.4  # 1" schedule 40 PVC, matches the bracket saddles
PIPE_INNER_DIAMETER = 30.0  # measured on the actual pipe 2026-09-04
# (spec-sheet 1" sch 40 bore is 26.6 — the real pipe runs larger)
END_CAP_FLANGE_PROUD = 4.3  # flange OD 42 mm; still inside the saddle
# wall's 45.4 mm face, so the flange seats flat against the bracket
END_CAP_FLANGE_THICKNESS = 4.0
END_CAP_STEM_LENGTH = 24.0  # 28 mm overall; deeper grip in the bore
END_CAP_STEM_DIAMETER = PIPE_INNER_DIAMETER - 0.6  # slip fit
END_CAP_RIB_DIAMETER = PIPE_INNER_DIAMETER + 0.4  # crush fit on the ribs
END_CAP_TIP_CHAMFER = 2.5  # generous lead-in; first caps were snug to start
END_CAP_RIB_GRIP_LENGTH = 6.0  # full-height rib band near the flange; the
# rest of each rib is a long wedge rising from flush at the tip, so
# insertion starts loose and only tightens over the last few mm
END_CAP_RIB_WIDTH = 2.0
END_CAP_RIB_COUNT = 4

# name: (value or expression, unit, comment). Every one must drive geometry.
PARAMETERS = {
    "rodOuterDiameter": (ROD_OUTER_DIAMETER, "mm", "pipe OD the flange exceeds"),
    "pipeInnerDiameter": (PIPE_INNER_DIAMETER, "mm", "MEASURED bore, not the spec"),
    "endCapFlangeProud": (END_CAP_FLANGE_PROUD, "mm", "flange beyond the pipe OD"),
    "endCapFlangeThickness": (END_CAP_FLANGE_THICKNESS, "mm", "flange thickness"),
    "endCapStemLength": (END_CAP_STEM_LENGTH, "mm", "stem depth into the bore"),
    "endCapStemDiameter": ("pipeInnerDiameter - 0.6 mm", "mm", "slip fit"),
    "endCapRibDiameter": ("pipeInnerDiameter + 0.4 mm", "mm", "crush fit on ribs"),
    "endCapTipChamfer": (END_CAP_TIP_CHAMFER, "mm", "lead-in at the stem tip"),
    "endCapRibWidth": (END_CAP_RIB_WIDTH, "mm", "rib width"),
    "endCapRibCount": (str(END_CAP_RIB_COUNT), "", "ribs around the stem"),
    "endCapRibGripLength": (END_CAP_RIB_GRIP_LENGTH, "mm", "full-height rib band"),
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


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _dimension(sketch, point_a, point_b, orientation, expression, text_x, text_z):
    dimension = sketch.sketchDimensions.addDistanceDimension(
        point_a, point_b, orientation, _point(text_x, text_z)
    )
    dimension.parameter.expression = expression


def _ensure_parameters(design):
    """Create or update user parameters, each with its declared unit."""
    user_parameters = design.userParameters
    for name, (value, unit, comment) in PARAMETERS.items():
        expression = value if isinstance(value, str) else f"{value} {unit}".strip()
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


def _drop_stale_parameters(design):
    """Delete parameters this script no longer declares, or that changed unit."""
    user_parameters = design.userParameters
    for index in range(user_parameters.count - 1, -1, -1):
        parameter = user_parameters.item(index)
        expected = PARAMETERS.get(parameter.name)
        if expected is None or parameter.unit != expected[1]:
            print(f"  dropping stale parameter {parameter.name}")
            parameter.deleteMe()


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
        if parameter.unit != PARAMETERS[parameter.name][1]:
            wrong_unit.append(f"{parameter.name}={parameter.unit!r}")
        used = any(
            other != parameter.name and _references(expression, parameter.name)
            for other, expression in expressions.items()
        )
        if not used:
            idle.append(parameter.name)
    print(f"  parameters: {user_parameters.count} declared, all driving geometry")
    if wrong_unit or idle:
        raise RuntimeError(f"audit failed: idle={idle} wrong_unit={wrong_unit}")


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
    grip_top = rib_z0 + END_CAP_RIB_GRIP_LENGTH  # full height ends here;
    # above it the outer edge tapers to flush at the tip end
    rib = component.sketches.add(plane)
    rib.name = "Crush rib"
    rib_lines = _polyline(
        rib,
        [
            (rib_inner, rib_z0),
            (rib_radius, rib_z0),
            (rib_radius, grip_top),
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
        "endCapFlangeThickness + 1 mm + endCapRibGripLength",
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
    grip_z = END_CAP_FLANGE_THICKNESS + 1.0 + END_CAP_RIB_GRIP_LENGTH / 2.0
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
        ("rib +X in grip band", rib_mid, 0.0, grip_z, inside),
        ("rib +Y in grip band", 0.0, rib_mid, grip_z, inside),
        ("no rib at 45 degrees", diagonal, diagonal, grip_z, outside),
        ("rib taper relieved near tip", rib_mid, 0.0, tip_z - 6.0, outside),
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
        f"scripted end cap build {datetime.date.today().isoformat()}: "
        f"pipe bore {PIPE_INNER_DIAMETER} mm, flange proud {END_CAP_FLANGE_PROUD} mm"
    )
    description += f" vol {body.volume / (MM ** 3):.0f} mm3"
    if data_file is None:
        document.saveAs(DOC_NAME, folder, description, "")
    else:
        document.save(description)
    print(f"saved '{DOC_NAME}' in project '{FUSION_PROJECT_NAME}': {description}")
    print("build complete")
