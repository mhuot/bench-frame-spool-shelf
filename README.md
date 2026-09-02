# LAN Spool Shelf

Filament spool storage for an Ergotron LAN Organizer 3000. Two 3D-printed
brackets hook into the slotted DuraFrame uprights and carry **two parallel
rods** — 1" schedule 40 PVC by default, or wooden dowels — and spools rest
in the valley between the rods. Any spool lifts straight out (and rolls
freely as filament feeds) without touching the rods. No drilling, no
hardware; the brackets hook in like Ergotron's own shelves.

![Spool cradle bracket](docs/images/spool_cradle_bracket_iso.png)

## Parts

| File | What it is |
|---|---|
| `exports/slot_gauge.stl` | **Print first.** Hook plate only — verifies the slot fit against the real upright. |
| `exports/saddle_coupon.stl` | **Print second.** Thin slice of the two-saddle arm tip — verifies rod pocket diameter and drop-in fit against the real pipe/dowel. ~12 cm³. |
| `exports/spool_cradle_bracket.stl` | The bracket. Print **two per shelf level**; it is symmetric, no left/right hand. |
| `cad/*.step`, `cad/*.f3d` | The same parts as CAD, exported by the same build run as the STLs. |

## Fit check workflow

The upright slot geometry was measured by hand (3/4" tall slots, 1" vertical
pitch, ~1/8" wide). Each upright carries a single slot column — the "double
track" at the middle of the 60" module is just the two joined frames'
columns sitting side by side — so the bracket hooks one column with a
single centred blade column, four rows tall, and mounts on any upright.
Two numbers are still assumptions: slot width and face metal thickness.

1. Print `slot_gauge.stl` flat on its side and hook it into the upright:
   the blade column should enter its slots, drop ~14 mm, and sit flush
   with no rock. If it binds or rattles, edit `SLOT_WIDTH` or
   `FACE_METAL_THICKNESS` at the top of `scripts/build_rod_bracket.py`,
   rebuild, re-print.
2. Print `saddle_coupon.stl` and drop your actual rod stock into both
   pockets: it should seat fully and lift out without force. Adjust
   `ROD_OUTER_DIAMETER` / `SADDLE_CLEARANCE` if not.
3. When both coupons pass, print two brackets.

## Geometry

- Rod axes sit 70 mm and 150 mm out from the upright face (80 mm apart), at
  the same height. A 200 mm spool rests on both rods at a ~20° contact
  half-angle — stable, but light enough to lift straight out — and its
  rearmost point clears the upright face by ~10 mm.
- A resting spool's top sits ~285 mm above the bracket's bottom edge, so
  leave ~12" of frame space above the mounting slots.
- For the 30" DuraFrame (10-063-100): upright centres are ~28" apart; cut
  rods to ~29.5" (750 mm) to span both saddles fully. Each of the two rods
  carries half the load, so sag on 1" PVC is ~1.5 mm with eight 1 kg
  spools; hardwood dowel is stiffer still.
- Nothing retains the rods because nothing pulls them up: spools press them
  into the saddles and are lifted off the rods, never with them.
- The bracket is 24 mm wide — narrower than the 1" gap between the two
  slot columns at the module centre, so both bays can carry cradles at the
  same height without the centre brackets colliding.

## Printing

- Lie the bracket on its flat side (rod axes vertical in the slicer), so
  the layer planes coincide with the loaded plane. **Do not print it
  upright** — that puts every layer seam across the hook lips.
- **Material: ASA on the Core One Plus** (enclosed, so warp is handled);
  PETG is the runner-up and completely adequate. The hooks live under
  constant tension, so the failure modes that matter are creep and brittle
  fracture: ASA creeps less than PETG over months under load and stays
  ductile; PLA/PLA+ creeps too much; CF blends are stiff but brittle in
  exactly the thin blade sections that must not snap. The 180 mm part fits
  the 250 x 220 bed lying on its side with room to spare.
- 4+ perimeters, 40 % infill or more.
- Load rating: sized for ~6 kg per bracket (a full level of spools is
  ~10 kg across two brackets; the single hook column sees ~90 N of tension
  at the top row at that load, about a 2x margin in PETG).

## Rebuilding

Fusion 360 must be running with its MCP server on `127.0.0.1:27182`. Then:

```sh
python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py                  # bracket
python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py --variant gauge
python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py --variant coupon
```

Each run rebuilds the part inside its saved document in the **"LAN Spool
Shelf" Fusion cloud project** (created automatically), probes the geometry
numerically (the run fails loudly if any probe misses), exports the STL,
STEP, and F3D together, and saves a **new Fusion version** of the document
with a description recording the key dimensions — so the model's history
lives in Fusion's version list as well as in git. Every document carries a
user-parameter table mirroring the script constants: the extrude widths
(`bracketWidth`, `couponWidth`, `hookTabWidth`) actually drive the model
and are safe to edit live; the rest are marked reference-only because the
sketch profiles are computed by the script — change those in
`scripts/build_rod_bracket.py` and rebuild. Sanity-check a mesh afterwards with:

```sh
.venv/bin/python scripts/check_stl.py exports/spool_cradle_bracket.stl <mm3 from build output>
```

The Ergotron order guide lives in `docs/03-006_obsolete.pdf`; it documents
frame widths and capacities but not slot geometry, hence the hand
measurements above.
