# Bench Frame Spool Shelf

**[Project site &rarr; mhuot.github.io/bench-frame-spool-shelf](https://mhuot.github.io/bench-frame-spool-shelf/)**

Filament spool storage that hangs on the slotted uprights of a steel bench
frame. Mine is an Ergotron LAN Organizer 3000. Two printed brackets hook
into the slotted DuraFrame uprights and carry two parallel rods. Spools rest in the valley between the rods. Lift one straight out,
drop the next one in, nothing else moves. A spool in the cradle rolls
freely, so it feeds without a fight. No drilling and no hardware. The
brackets hook in the same way Ergotron's own shelves do.

The rods are 1" schedule 40 PVC by default. Wooden dowels, aluminium pipe
and conduit all work too. More on that below.

![Spool cradle bracket](docs/images/spool_cradle_bracket_iso.png)

## The desk

In the 1990s it felt like every NOC and data center, at least the ones near
me, had furniture from [Ergotron](https://www.ergotron.com/) in
[Eagan, Minnesota](https://en.wikipedia.org/wiki/Eagan,_Minnesota). The desks
matched the look those rooms had and the job they did.

The one I have sat in a data center with a row of computers on it. They ran
the small ISP my employer operated. I picked it up when the company
liquidated, after they were no more. The slotted uprights are the same ones
that held their shelves, which is why nothing here needs a drill.

## Parts

| File | What it is |
|---|---|
| `exports/slot_gauge.stl` | **Print this first.** Just the hook plate. It tells you whether the hooks fit your upright before you spend four hours on a bracket. |
| `exports/saddle_coupon.stl` | **Print this second.** An 8 mm slice of the arm tip with both rod pockets. Drop your actual rod in and see if it seats. About 12 cm³. |
| `exports/spool_cradle_bracket.stl` | The bracket. Two per shelf level. It is symmetric, so there is no left or right. |
| `exports/rod_end_cap.stl` | Press-fit cap for the rod ends. The 42 mm flange stops a rod walking out of its saddle, and four crush ribs on the 24 mm stem grip the pipe bore. Sized for a bore I measured at 30 mm. The schedule 40 spec says 26.6 and was wrong for my pipe. Measure yours, set `PIPE_INNER_DIAMETER` in `scripts/build_rod_end_cap.py`, and print one before printing four per level. Flange down, no supports. |
| `exports/rod_label_clip.stl` | Snap-on label clip. A C-ring snaps onto a rod from below and slides along to sit under its spool. The 58 x 29 mm face takes a 1" x 2-1/8" adhesive label and hangs just past plumb, aimed at someone looking up at a rod above their head. That is `PADDLE_ANGLE_DEG = 100`. A shelf below eye level wants about 50. The face is flush with one side of the 20 mm ring, and the ring is that wide so the offset label does not cock the clip on the rod. One per spool, printed on the flat side (rotate 90° about X), no supports. Eight fit a MINI bed. |
| `cad/*.step`, `cad/*.f3d` | The same parts as CAD, written by the same build run as the STLs. |

## Check the fit before printing brackets

I measured the slots by hand. 3/4" tall, 1" vertical pitch, about 1/8"
wide. Each upright has one column of slots. The double track at the
middle of a 60" module is just the two joined frames' columns sitting side
by side. So the bracket hooks one column with a single centred blade
column, four rows tall, and mounts on any upright.

The first gauge pinched before it seated. Paint and the burr on a punched
slot are worth a millimetre no drawing mentions. The throat went from 2.8
to 3.8 mm, the lips got lead-in chamfers, and the second gauge sat flush.
Your uprights may differ from mine, so the gauge is still the first thing
to print.

1. Print `slot_gauge.stl` flat on its side and hook it into the upright.
   The blades should enter the slots, drop about 14 mm and sit flush with
   no rock. If it binds or rattles, edit `SLOT_WIDTH` or
   `FACE_METAL_THICKNESS` at the top of `scripts/build_rod_bracket.py`,
   rebuild, print again.
2. Print `saddle_coupon.stl` and drop your rod stock into both pockets. It
   should seat fully and lift out without force. If not, adjust
   `ROD_OUTER_DIAMETER` or `SADDLE_CLEARANCE`.
3. When both pass, print two brackets.

## Geometry

- The rod axes sit 70 mm and 150 mm out from the upright face, at the same
  height. A 200 mm spool resting on both rods touches them about 20°
  either side of plumb. Deep enough that it stays put, shallow enough to
  lift out one-handed. The back of the spool clears the upright by about
  10 mm.
- A resting spool's top sits about 285 mm above the bracket's bottom edge.
  Leave 12" of frame above the mounting slots.
- On the 30" DuraFrame (10-063-100) the upright centres are about 28"
  apart. Cut rods to 29.5" (750 mm) so they span both saddles fully.
- Nothing holds the rods down, because nothing ever pulls them up. Spools
  press them into the saddles and get lifted off, never with them.
  Sideways is a different story. That is what the end caps are for. Their
  crush ribs grip the bore and the flange is wider than the saddle, so a
  rod cannot walk out while you shove spools around. No glue.
- The bracket is 24 mm wide, narrower than the 1" gap between the two
  slot columns at the module centre, so both bays can carry cradles at the
  same height without the middle brackets colliding.

## Rods, sag and cost

One level holds about 12 kg. That is two brackets at about 6 kg each with
roughly 2x structural margin, so a full row of nine 1 kg spools, or count
3 kg spools by weight. Rod strength is never the limit. PVC runs at about
2 MPa against a 50 MPa allowable. Stiffness is the limit, because a rod
that sags forms a shallow valley and the spools slowly roll toward the
middle of it.

Sag below is per rod at full load, about 5.6 kg over the 711 mm span. Cost
is per level, two 29.5" rods, Home Depot, September 2026.

| Rod | Sag | Fits the stock 34.2 mm pocket? | Cost per level |
|---|---|---|---|
| 1" sch 40 PVC (default) | ~2.4 mm, creeping to 4-6 mm over months | yes | ~$5 (10 ft makes 4 rods) |
| 1" sch 40 aluminium pipe | ~0.1 mm, no creep | yes, same 33.4 mm OD as PVC | ~$32 ($48 for 8 ft, 3 rods) |
| 1-1/4" hardwood dowel | ~0.4 mm | close, 2.5 mm of play, fine | ~$10 |
| 1" hardwood dowel | ~1.0 mm | no, set `ROD_OUTER_DIAMETER = 25.4` | ~$6 |
| 3/4" EMT steel conduit | ~0.25 mm | no, set `ROD_OUTER_DIAMETER = 23.4` | ~$5 (10 ft makes 4 rods) |
| 1" EMT steel conduit | ~0.1 mm | no, set `ROD_OUTER_DIAMETER = 29.5` | ~$7 |

Start with PVC. It is fine, and the saddles are open, so you can swap rods
later without reprinting anything. Aluminium pipe is the nicest upgrade
because it drops straight in, but it costs six times what EMT does for a
sag difference of 0.15 mm that nobody will ever see. EMT is the stiffness
per dollar winner and only costs a pocket rebuild, which is one constant
and a saddle coupon reprint. Whatever you pick, deburr the cut ends. Spool
flanges bump the rod ends now and then while loading.

## Printing

- Brackets lie on their flat side, rod axes vertical in the slicer, so the
  layer planes line up with the load. Do not print one standing up. That
  puts a layer seam across every hook lip.
- ASA if your printer is enclosed. PETG otherwise, and it is completely
  adequate. The hooks live under constant tension, so what matters is
  creep and brittle fracture. ASA creeps less than PETG over months and
  stays ductile. PLA creeps too much. Carbon fibre blends are stiff but
  brittle in exactly the thin blade sections that must not snap. The
  180 mm bracket fits a 250 x 220 bed on its side with room to spare.
- Four or more perimeters, 40% infill or more.
- Load rating is about 6 kg per bracket. A full level is about 10 kg
  across two brackets. At that load the top hook row sees about 90 N of
  tension, roughly a 2x margin in PETG.
- End caps in ASA or PETG, flange down, no supports. The ribs are the
  press fit, so give them three or more walls rather than trusting infill.
- Label clips in PETG. They carry a label, not a load. 0.2 mm layers and
  three perimeters, so the 2.4 mm ring wall is solid and the snap cannot
  split along a gap-fill seam. Flat side down, no supports, brim optional.
  They snap over the rod from below with a few newtons of push and slide
  freely. Mine came off a MINI and a Core One, both in Prusament PETG.

## Rebuilding

Fusion 360 has to be running with its MCP server on `127.0.0.1:27182`.
Then

```sh
python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py                  # bracket
python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py --variant gauge
python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py --variant coupon
python3 scripts/run_in_fusion.py scripts/build_rod_end_cap.py             # rod end cap
python3 scripts/run_in_fusion.py scripts/build_rod_label_clip.py          # label clip
```

Each run rebuilds the part inside its saved document in the "LAN Spool
Shelf" Fusion cloud project, which it creates if needed. It probes the
geometry numerically and fails loudly if any probe misses. Then it writes
the STL, STEP and F3D in the same run, so they cannot drift apart, and
saves a new version of the Fusion document with the key dimensions in the
description. The model's history lives in Fusion's version list as well
as in git.

Every document carries a user parameter table that mirrors the script
constants, and every one of those parameters drives geometry. The build
fails if one stops doing so. That makes them safe to edit live in Fusion.
The hook profile sketch is fully constrained against `hookThroat`, which
is the expression `faceMetalThickness + 1.8 mm`, plus `hookNeckHeight`,
`hookLipThickness`, `hookLipDrop`, `hookLipChamfer` and `topHookNeckTop`.
The rows are a rectangular pattern driven by `hookRows` times
`slotPitchVertical`.

A scripted rebuild regenerates the document from the script, so a hand
edit you want to keep has to go back into the script. The build refuses to
overwrite a document whose latest save is a hand edit with changed
geometry, so you cannot lose one by accident. Sanity-check a mesh
afterwards with

```sh
.venv/bin/python scripts/check_stl.py exports/spool_cradle_bracket.stl <mm3 from build output>
```

The Ergotron order guide (870-03-006) has frame widths and capacities but
no slot geometry, hence the ruler. It is Ergotron's document, so it is
not in this repo. If you have a copy, keep it at
`docs/03-006_obsolete.pdf`, which is gitignored.

## License

MIT, see `LICENSE`. Print them, sell them, remix them. A link back is
appreciated.
