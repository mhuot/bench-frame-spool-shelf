"""Audit every saved Fusion document: parameters, units, and constraint state.

Run inside Fusion via scripts/run_in_fusion.py:

    python3 scripts/run_in_fusion.py scripts/audit_parameters.py

The build scripts each audit themselves before exporting, so a scripted
rebuild cannot ship an inert parameter. This script is for the other half of
the problem: documents as they stand right now, including after somebody has
edited one by hand, and documents built before the audit existed.

It reports, and fails, on three things:

1. A user parameter that drives nothing. Nothing in Fusion ties a parameter
   to geometry — a sketch can hold a hardcoded number beside a well named
   parameter that no feature consumes. A parameter earns its place only by
   appearing in some other parameter's expression.
2. A parameter whose unit contradicts its name: an angle stored in mm, a
   count stored as a length. userParameters.add takes the unit as a string
   and validates nothing.
3. A sketch that is not fully constrained. It solves today; it drifts the
   moment someone drags a point, and it is where an unnoticed hand edit
   lands.

Point 3 is a warning rather than an error by default, because a cut sketch
that reaches past the body it cuts does not always need pinning. Pass
STRICT_SKETCHES = True to make it fail too.
"""

import adsk.core
import adsk.fusion

PROJECT_NAMES = ("LAN Spool Shelf", "LAN Pegboard Mount")
STRICT_SKETCHES = False

# A parameter whose name matches one of these must carry the matching unit.
UNIT_BY_NAME_HINT = (
    ("deg", "deg"),
    ("angle", "deg"),
    ("count", ""),
    ("rows", ""),
)


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


def _expected_unit(name):
    """The unit a parameter's name implies, or None if it implies nothing."""
    lowered = name.lower()
    for hint, unit in UNIT_BY_NAME_HINT:
        if hint in lowered:
            return unit
    return None


def _audit_design(design):
    """Return (idle, wrong_unit, loose_sketches) for one open design."""
    user_parameters = design.userParameters
    all_parameters = design.allParameters
    expressions = {}
    for index in range(all_parameters.count):
        parameter = all_parameters.item(index)
        expressions[parameter.name] = parameter.expression or ""

    idle, wrong_unit = [], []
    for index in range(user_parameters.count):
        parameter = user_parameters.item(index)
        users = sum(
            1
            for other, expression in expressions.items()
            if other != parameter.name and _references(expression, parameter.name)
        )
        expected = _expected_unit(parameter.name)
        unit = parameter.unit or ""
        if expected is not None and unit != expected:
            wrong_unit.append(f"{parameter.name} is {unit or 'unitless'!r}")
        if not users:
            idle.append(parameter.name)
        marker = "" if users else "   <-- DRIVES NOTHING"
        if expected is not None and unit != expected:
            marker = f"   <-- EXPECTED {expected or 'unitless'}"
        print(
            f"    {parameter.name:24s} {parameter.expression:22s} "
            f"unit={unit or '-':4s} drives {users}{marker}"
        )

    loose = []
    root = design.rootComponent
    for index in range(root.sketches.count):
        sketch = root.sketches.item(index)
        if not sketch.isFullyConstrained:
            loose.append(sketch.name)
    return idle, wrong_unit, loose


# pylint: disable-next=too-many-locals
def run(_context: str):
    """Audit every document in the configured Fusion projects."""
    app = adsk.core.Application.get()
    projects = app.data.dataProjects
    failures = []
    warnings = []
    for index in range(projects.count):
        project = projects.item(index)
        if project.name not in PROJECT_NAMES:
            continue
        files = project.rootFolder.dataFiles
        for position in range(files.count):
            data_file = files.item(position)
            document = app.documents.open(data_file, True)
            design = adsk.fusion.Design.cast(app.activeProduct)
            print(f"\n=== {project.name} / {data_file.name} v{data_file.versionNumber}")
            idle, wrong_unit, loose = _audit_design(design)
            if loose:
                print(f"    sketches not fully constrained: {loose}")
            if idle:
                failures.append(f"{data_file.name}: idle parameters {idle}")
            if wrong_unit:
                failures.append(f"{data_file.name}: wrong units {wrong_unit}")
            if loose:
                (failures if STRICT_SKETCHES else warnings).append(
                    f"{data_file.name}: loose sketches {loose}"
                )
            document.close(False)

    print("\n--- audit summary ---")
    for warning in warnings:
        print(f"  warning: {warning}")
    if failures:
        for failure in failures:
            print(f"  FAIL: {failure}")
        raise RuntimeError(f"{len(failures)} audit failure(s)")
    print(f"  all documents clean ({len(warnings)} warning(s))")
