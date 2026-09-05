"""Assemble the Pages viewer GLB from the exported part STLs.

Runs locally in .venv (trimesh, numpy):

    .venv/bin/python scripts/build_web_assets.py

Loads the parts this repo already ships in exports/, places them the way a
real shelf level goes together (two brackets, two rods, four end caps, a
few spools resting in the cradle, a label clip under one), and writes
docs/models/spool-shelf.glb for model-viewer.

Colour note: the palette is authored in sRGB to match the printed parts,
but glTF baseColorFactor is linear, so every colour is converted with the
sRGB EOTF before export. Skipping that step washes the whole scene out.

The assembly maths lives here rather than in the Fusion scripts on purpose:
this is a picture, not a part, and nothing printable should depend on it.
"""

import math
from pathlib import Path

import trimesh

EXPORTS = Path("exports")
GLB_PATH = Path("docs/models/spool-shelf.glb")

# --- Shelf geometry (mirrors the build scripts; see README) ----------------
BRACKET_SPACING = 711.0  # upright centres, ~28"
ROD_LENGTH = 750.0  # ~29.5" cut
REAR_ROD_X = 70.0
FRONT_ROD_X = 150.0
ROD_RADIUS = 33.4 / 2.0
ROD_CENTER_Z = 90.0
ROD_Y0 = -(ROD_LENGTH - BRACKET_SPACING) / 2.0  # rod overhangs each bracket

SPOOL_RADIUS = 100.0
SPOOL_WIDTH = 68.0
SPOOL_FLANGE_THICKNESS = 3.5
SPOOL_HUB_RADIUS = 32.0
SPOOL_WOUND_RADIUS = 92.0
SPOOL_X = (REAR_ROD_X + FRONT_ROD_X) / 2.0
# A spool rests on both rods: its axis sits where it touches each of them.
SPOOL_Z = ROD_CENTER_Z + math.sqrt(
    (SPOOL_RADIUS + ROD_RADIUS) ** 2 - ((FRONT_ROD_X - REAR_ROD_X) / 2.0) ** 2
)

# sRGB, roughly the filaments in the photos
PALETTE = {
    "printed": (198, 42, 34, 255),  # the red ASA the real brackets are in
    "rod": (236, 236, 232, 255),  # white PVC
    "spool_a": (32, 34, 38, 255),
    "spool_b": (222, 178, 40, 255),
    "spool_c": (58, 96, 176, 255),
    "spool_hub": (44, 46, 50, 255),
}
METALLIC = {"rod": 0.0}
ROUGHNESS = {"rod": 0.55, "printed": 0.75}


def srgb_to_linear(channel):
    """glTF baseColorFactor is linear; the palette above is sRGB."""
    ratio = channel / 255.0
    if ratio <= 0.04045:
        return ratio / 12.92
    return ((ratio + 0.055) / 1.055) ** 2.4


def material(group):
    """PBR material for a palette group, converted to linear."""
    red, green, blue, alpha = PALETTE[group]
    return trimesh.visual.material.PBRMaterial(
        baseColorFactor=[
            srgb_to_linear(red),
            srgb_to_linear(green),
            srgb_to_linear(blue),
            alpha / 255.0,
        ],
        metallicFactor=METALLIC.get(group, 0.0),
        roughnessFactor=ROUGHNESS.get(group, 0.6),
    )


def load_part(name):
    """Load one exported part STL as a single mesh."""
    mesh = trimesh.load(EXPORTS / f"{name}.stl")
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(mesh.geometry.values()))
    return mesh


def placed(mesh, transform, group):
    """A transformed, coloured copy of a part."""
    part = mesh.copy()
    part.apply_transform(transform)
    part.visual = trimesh.visual.TextureVisuals(material=material(group))
    return part


def rotation(angle_degrees, axis):
    """Rotation matrix, degrees about an axis through the origin."""
    return trimesh.transformations.rotation_matrix(math.radians(angle_degrees), axis)


def translation(x_mm, y_mm, z_mm):
    """Translation matrix in millimetres."""
    return trimesh.transformations.translation_matrix([x_mm, y_mm, z_mm])


def rod(x_mm):
    """A rod lying along Y at the given standoff."""
    tube = trimesh.creation.cylinder(radius=ROD_RADIUS, height=ROD_LENGTH, sections=64)
    transform = translation(x_mm, ROD_Y0 + ROD_LENGTH / 2.0, ROD_CENTER_Z) @ rotation(
        90, [1, 0, 0]
    )
    tube.apply_transform(transform)
    tube.visual = trimesh.visual.TextureVisuals(material=material("rod"))
    return tube


def spool(y_center, group):
    """Flanges plus wound filament plus hub, resting in the cradle."""
    pieces = []
    for side in (-1.0, 1.0):
        flange = trimesh.creation.cylinder(
            radius=SPOOL_RADIUS, height=SPOOL_FLANGE_THICKNESS, sections=64
        )
        offset = side * (SPOOL_WIDTH - SPOOL_FLANGE_THICKNESS) / 2.0
        flange.apply_transform(translation(0, offset, 0))
        pieces.append(flange)
    wound = trimesh.creation.cylinder(
        radius=SPOOL_WOUND_RADIUS,
        height=SPOOL_WIDTH - 2 * SPOOL_FLANGE_THICKNESS - 1.0,
        sections=64,
    )
    pieces.append(wound)
    body = trimesh.util.concatenate(pieces)
    hub = trimesh.creation.cylinder(
        radius=SPOOL_HUB_RADIUS, height=SPOOL_WIDTH + 2.0, sections=48
    )
    transform = translation(SPOOL_X, y_center, SPOOL_Z) @ rotation(90, [1, 0, 0])
    body.apply_transform(transform)
    hub.apply_transform(transform)
    body.visual = trimesh.visual.TextureVisuals(material=material(group))
    hub.visual = trimesh.visual.TextureVisuals(material=material("spool_hub"))
    return [body, hub]


def build_scene():
    """Place every part of one shelf level; return the mesh list."""
    bracket = load_part("spool_cradle_bracket")
    end_cap = load_part("rod_end_cap")
    label_clip = load_part("rod_label_clip")

    parts = []
    for bracket_y in (0.0, BRACKET_SPACING):
        parts.append(placed(bracket, translation(0, bracket_y, 0), "printed"))
    for rod_x in (REAR_ROD_X, FRONT_ROD_X):
        parts.append(rod(rod_x))
        # Caps: the model is built about +Z, so swing it onto the rod axis.
        # Near end points +Y into the pipe, far end points -Y.
        near = translation(rod_x, ROD_Y0 - 4.0, ROD_CENTER_Z) @ rotation(-90, [1, 0, 0])
        far = translation(rod_x, ROD_Y0 + ROD_LENGTH + 4.0, ROD_CENTER_Z) @ rotation(
            90, [1, 0, 0]
        )
        parts.append(placed(end_cap, near, "printed"))
        parts.append(placed(end_cap, far, "printed"))

    for offset, group in ((150.0, "spool_a"), (250.0, "spool_b"), (350.0, "spool_c")):
        parts.extend(spool(offset, group))

    parts.append(
        placed(
            label_clip,
            translation(FRONT_ROD_X, 250.0, ROD_CENTER_Z),
            "printed",
        )
    )
    return parts


def main():
    """Write the GLB the docs page loads."""
    parts = build_scene()
    scene = trimesh.Scene()
    for index, part in enumerate(parts):
        scene.add_geometry(part, node_name=f"part_{index:02d}")
    # Centre the assembly on the origin so model-viewer orbits its middle.
    bounds = scene.bounds
    centre = (bounds[0] + bounds[1]) / 2.0
    scene.apply_transform(trimesh.transformations.translation_matrix(-centre))
    GLB_PATH.parent.mkdir(parents=True, exist_ok=True)
    GLB_PATH.write_bytes(trimesh.exchange.gltf.export_glb(scene))
    size_kb = GLB_PATH.stat().st_size / 1024.0
    extents = [round(float(value), 1) for value in (bounds[1] - bounds[0])]
    print(f"wrote {GLB_PATH} ({size_kb:.0f} kB), {len(parts)} parts")
    print(f"assembly extents mm: {extents}")
    print(f"spool axis height above rods: {SPOOL_Z - ROD_CENTER_Z:.1f} mm")


if __name__ == "__main__":
    main()
