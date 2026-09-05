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
  documents are build artifacts: the script is the source of truth. EVERY
  user parameter drives geometry — there are no reference-only parameters
  any more — with lengths in mm, angles in deg and counts unitless, and the
  build fails if that stops being true. dataFile.versionNumber reads stale
  right after save(), so don't trust it in-run. A scripted rebuild discards
  hand edits: they survive as the previous version, so recover them from
  `dataFile.versions` (Fusion labels them 'User Saved') and fold them into
  the script rather than re-doing them in the document.
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
- **Fusion, any time**: `scripts/audit_parameters.py` checks every saved
  document for parameters that drive nothing, units that contradict their
  name, and sketches that are not fully constrained. Each build script also
  runs this audit on itself before exporting, so a scripted rebuild cannot
  ship an inert parameter; run the standalone one after editing a document
  by hand, or before trusting a document built by an older script.

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
