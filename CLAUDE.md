# lan-spool-shelf

3D-printed brackets that hook into the slotted DuraFrame uprights of an
Ergotron LAN Organizer 3000 and carry a horizontal rod (1" schedule 40 PVC by
default; any rod up to the configured diameter) for hanging filament spools.
Print two brackets per rod; the bracket is symmetric, so there is no left or
right hand.

## Source of truth

- `scripts/build_rod_bracket.py` builds the bracket, slot gauge, and
  saddle coupon; `scripts/build_rod_end_cap.py` builds the rod end cap as
  its own part and document. Dimensions live at the top of each script —
  there is deliberately no shared params module (see the module-caching
  trap in the fusion-360-mcp skill), so the small scaffolding is repeated.
- The builds land in the Fusion cloud project **"LAN Spool Shelf"** as
  saved documents "Spool Cradle Bracket", "Slot Gauge", "Saddle Coupon";
  each scripted run saves a new version of the matching document. The
  documents are build artifacts: the script is the source of truth. The
  width parameters and the whole hook stack (constrained profile sketch +
  hookRows/slotPitchVertical pattern) are wired into features and safe to
  edit live; body-profile parameters are reference-only, as their comments
  say. dataFile.versionNumber reads stale right after
  save(), so don't trust it in-run.
- The Ergotron order guide (870-03-006) sits at `docs/03-006_obsolete.pdf`
  when present, but is gitignored rather than redistributed. It has frame
  widths and capacities but NOT slot geometry.
- Slot geometry was measured on the actual desk: **3/4" tall slots on 1"
  vertical pitch** (user measurement, 2026-09-02). Slot *width* and face
  metal thickness are still assumed values — the slot gauge print exists to
  verify them before committing to full brackets.

## Which scripts run where

- **Fusion 360 only** (`import adsk`): `scripts/build_rod_bracket.py`.
  Run it through the MCP server with `scripts/run_in_fusion.py` (local,
  stdlib only): `python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py`.
  Pass `--variant gauge` to build the slot fit gauge instead of the full
  bracket. `scripts/build_rod_end_cap.py` runs the same way (no variants).
- **Locally, in `.venv`**: `scripts/check_stl.py` (trimesh) sanity-checks an
  exported mesh against the volume the build script printed.

The Fusion MCP server listens on `http://127.0.0.1:27182/mcp` (registered in
this project's MCP config as `fusion`). Fusion must be running.

## Exports

The build script itself exports `cad/<name>.step`, `cad/<name>.f3d`, and
`exports/<name>.stl` in one run, so they cannot drift from each other. Never
hand-export. A stale F3D is worse than a missing one.

## Printing

Print brackets lying on a side face (rod axis vertical in the slicer) so
layer planes coincide with the loaded XZ plane. PETG or PLA+, 4+ perimeters,
40%+ infill. The hook lips carry ~100 N in tension at full load (8 spools);
do not print them in a weak orientation.
