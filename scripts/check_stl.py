"""Sanity-check exported STLs: watertight, sane bounds, volume vs Fusion.

Run locally in .venv: .venv/bin/python scripts/check_stl.py <stl> <fusion_mm3>

The Fusion volume is what build_rod_bracket.py printed. A mismatch beyond
0.1% means the mesh and the BRep disagree — re-export before trusting either.
"""

import sys

import trimesh


def main():
    """Compare one STL against the volume Fusion reported."""
    stl_path = sys.argv[1]
    fusion_volume = float(sys.argv[2])
    mesh = trimesh.load(stl_path)
    mesh_volume = mesh.volume  # STL exports are in cm; adjust below
    # Fusion STL export writes centimetre units for API exports; detect by
    # magnitude and rescale to mm if needed.
    if mesh_volume < fusion_volume / 100.0:
        mesh_volume *= 1000.0
        scale_note = " (rescaled cm->mm)"
    else:
        scale_note = ""
    difference_percent = 100.0 * abs(mesh_volume - fusion_volume) / fusion_volume
    print(f"{stl_path}: watertight={mesh.is_watertight}")
    scale = 10.0 if scale_note else 1.0
    extents = [round(float(value) * scale, 1) for value in mesh.extents]
    print(f"  extents mm: {extents}{scale_note}")
    print(
        f"  mesh volume {mesh_volume:.0f} vs fusion {fusion_volume:.0f} mm^3 "
        f"({difference_percent:.3f}% diff)"
    )
    if not mesh.is_watertight or difference_percent > 0.1:
        sys.exit(1)


if __name__ == "__main__":
    main()
