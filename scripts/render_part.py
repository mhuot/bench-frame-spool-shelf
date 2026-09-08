"""Render an exported STL to a PNG for the docs page.

Runs locally in .venv (trimesh, numpy, pillow):

    .venv/bin/python scripts/render_part.py exports/skadis_nut_left.stl \
        docs/images/nut_bracket_front.png --azimuth 35

A painter's-algorithm rasteriser rather than a real renderer: no GPU, no
headless GL, nothing to install beyond what check_stl.py already needs. It
is enough to prove a part looks like what the build script says it is, and
to put an honest picture on the page.
"""

import argparse

import numpy as np
import trimesh
from PIL import Image

WIDTH, HEIGHT = 1100, 900
BACKGROUND = np.array([0.965, 0.969, 0.976])  # matches the page's --bg
PART_COLOUR = np.array([0.776, 0.165, 0.133])  # the red ASA, sRGB
CAP_COLOUR = np.array([0.93, 0.62, 0.58])  # cut faces of a section, so voids read
LIGHT = np.array([0.35, 0.5, 0.79])
# Surfaces further from the camera are darkened by up to this fraction. Flat
# orthographic shading gives a hole whose floor is parallel to the surface
# around it exactly the same tone as that surface, which made a 20 mm deep
# entry slot vanish entirely; a depth cue is the difference between a
# drawing of a solid block and a drawing of the part.
DEPTH_FOG = 0.35


def oriented(mesh, azimuth_deg, elevation_deg):
    """A copy of the mesh turned to the requested view."""
    working = mesh.copy()
    for angle, axis in ((-elevation_deg, [1, 0, 0]), (azimuth_deg, [0, 0, 1])):
        working.apply_transform(
            trimesh.transformations.rotation_matrix(
                np.radians(angle), axis, working.centroid
            )
        )
    return working


def shaded(mesh):
    """Per-face brightness from a single key light plus ambient."""
    triangles = mesh.vertices[:, [0, 2, 1]][mesh.faces]
    normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.where(lengths == 0, 1, lengths)
    key = LIGHT / np.linalg.norm(LIGHT)
    return np.clip(np.abs(normals @ key), 0, 1) * 0.62 + 0.38, triangles


# pylint: disable-next=too-many-locals
def render(mesh, azimuth_deg, elevation_deg, is_cap=None):
    """Rasterise the mesh to an RGB array."""
    brightness, triangles = shaded(oriented(mesh, azimuth_deg, elevation_deg))
    colours = np.tile(PART_COLOUR, (len(triangles), 1))
    if is_cap is not None:
        colours[is_cap] = CAP_COLOUR
    flat = triangles.reshape(-1, 3)
    low, high = flat.min(0), flat.max(0)
    span = max(high[0] - low[0], high[1] - low[1]) or 1.0
    scale = min(WIDTH, HEIGHT) * 0.80 / span
    centre = (low + high) / 2.0
    screen = triangles.copy()
    screen[:, :, 0] = (triangles[:, :, 0] - centre[0]) * scale + WIDTH / 2.0
    screen[:, :, 1] = HEIGHT / 2.0 - (triangles[:, :, 1] - centre[1]) * scale

    image = np.tile(BACKGROUND.astype(np.float32), (HEIGHT, WIDTH, 1))
    depth = np.full((HEIGHT, WIDTH), -np.inf)
    grid_x, grid_y = np.meshgrid(np.arange(WIDTH), np.arange(HEIGHT))
    for index in np.argsort(triangles[:, :, 2].mean(axis=1)):
        tri = screen[index]
        min_x, max_x = max(int(tri[:, 0].min()), 0), min(
            int(tri[:, 0].max()) + 2, WIDTH
        )
        min_y, max_y = max(int(tri[:, 1].min()), 0), min(
            int(tri[:, 1].max()) + 2, HEIGHT
        )
        if min_x >= max_x or min_y >= max_y:
            continue
        px, py = grid_x[min_y:max_y, min_x:max_x], grid_y[min_y:max_y, min_x:max_x]
        (x0, y0), (x1, y1), (x2, y2) = tri[:, :2]
        denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denominator) < 1e-9:
            continue
        weight_a = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / denominator
        weight_b = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / denominator
        weight_c = 1.0 - weight_a - weight_b
        inside = (weight_a >= 0) & (weight_b >= 0) & (weight_c >= 0)
        if not inside.any():
            continue
        z = weight_a * tri[0, 2] + weight_b * tri[1, 2] + weight_c * tri[2, 2]
        closer = inside & (z > depth[min_y:max_y, min_x:max_x])
        if not closer.any():
            continue
        depth[min_y:max_y, min_x:max_x][closer] = z[closer]
        image[min_y:max_y, min_x:max_x][closer] = colours[index] * brightness[index]
    drawn = np.isfinite(depth)
    if drawn.any():
        near, far = depth[drawn].max(), depth[drawn].min()
        fog = 1.0 - DEPTH_FOG * (near - depth[drawn]) / max(near - far, 1e-6)
        image[drawn] *= fog[:, None]
    return (np.clip(image, 0, 1) * 255).astype(np.uint8)


def cap_faces(mesh, axis, at_mm):
    """Mask of faces lying in the section plane -- the cap, not the part."""
    column = "xyz".index(axis)
    on_plane = np.abs(mesh.vertices[:, column] - at_mm) < 1e-4
    return on_plane[mesh.faces].all(axis=1)


def sectioned(mesh, axis, at_mm):
    """Cut the mesh with a plane and cap it, so internal voids are visible.

    A captured cavity is invisible from outside by definition, which is the
    whole point of it and also the whole problem with rendering it.
    """
    normal = {"x": [1.0, 0, 0], "y": [0, 1.0, 0], "z": [0, 0, 1.0]}[axis]
    origin = [value * at_mm for value in normal]
    half = mesh.slice_plane(
        plane_origin=origin, plane_normal=[-value for value in normal], cap=True
    )
    if half is None or half.is_empty:
        raise SystemExit(f"section at {axis}={at_mm} removed the whole part")
    return half


def main():
    """Render one STL from one viewpoint, optionally cut open."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stl")
    parser.add_argument("png")
    parser.add_argument("--azimuth", type=float, default=35.0)
    parser.add_argument("--elevation", type=float, default=20.0)
    parser.add_argument("--section-axis", choices=("x", "y", "z"))
    parser.add_argument("--section-at", type=float, default=0.0)
    arguments = parser.parse_args()
    mesh = trimesh.load(arguments.stl, force="mesh")
    is_cap = None
    if arguments.section_axis:
        mesh = sectioned(mesh, arguments.section_axis, arguments.section_at)
        is_cap = cap_faces(mesh, arguments.section_axis, arguments.section_at)
    Image.fromarray(render(mesh, arguments.azimuth, arguments.elevation, is_cap)).save(
        arguments.png
    )
    print(f"wrote {arguments.png}  extents mm {mesh.extents.round(2)}")


if __name__ == "__main__":
    main()
