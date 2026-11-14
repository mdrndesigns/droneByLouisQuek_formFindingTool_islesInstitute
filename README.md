# DronePendantSpeakerTool

Parametric form-finding and print-splitting tool for Louis Quek's pendant speakers
(*Constants*, WT "Drone") — Isles Institute, Probing the Southern Islands, SAW 2027.

![tests](../../actions/workflows/tests.yml/badge.svg)

## Quick start

**Double-click:** `start.command` (macOS) or `start.bat` (Windows). The first run creates a private `.venv` and
installs the dependencies; after that it opens the tool at http://127.0.0.1:8766. `START HERE.pdf` walks through it.

**Terminal** (Python 3.11+):

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt        # numpy trimesh manifold3d lxml networkx
    python3 run.py                         # http://127.0.0.1:8766
    python3 -m tests.test_engine           # engine checks
    python3 build.py drone_01_parameters.json [count]   # rebuild an export without the browser

## Layout

    drone/params.py    defaults, catalogues (drivers, boards, forms, presets) and the control schema
    drone/form.py      rock surface: superellipsoid + facets + fBm lumps, surface textures
    drone/peak.py      diffuser peak (centre cone): profile, plan shape, lumps, texture
    drone/parts.py     rocks split into printable parts, seam detail, joints, spine, hardware, checks
    drone/export.py    STL + 3MF + parameters + hardware list, zipped
    drone/server.py    local HTTP server: /defaults, /preview.bin, /export
    ui/                browser front end (controlGUI panel + three.js viewer); ui/vendor holds three.js r160
    tests/             engine checks, no browser needed

Same shape as the other LAB tools: a Python engine owns the geometry, the browser (controlGUI + three.js r160,
both vendored in `ui/`) sends the state and draws what comes back. The rocks are meshes, not B-rep, so the
engine is numpy + manifold3d rather than CadQuery; exports are STL and 3MF, no STEP.

## What it builds

| ID | Part | Prints | Role |
|----|------|--------|------|
| P1 | Dome | seam down | cover of the top rock; mic port, cable hole, rod hole |
| P2 | Crown tier | plate down | carries the hang rod; sits on the upper tubes |
| P3 | Tray tier | flat | breadboard + Nano; closes the speaker chamber; braces the tubes |
| P4 | Speaker pod | speaker face down | flat face with the PC83-8, strut bosses, joint spigot |
| P5 | Diffuser peak | base down | spreads the down-firing speaker sideways |
| P6 | Deck | deck face down | flat face of the base rock, strut bosses, joint spigot |
| P7 | Keel | seam down | closed end of the base rock, twist-locks onto the deck |

Hardware drawn at true size: H1 hang rod + eye nut, H2 upper spine tubes, H3 breadboard + Nano, H4 speaker, H5 struts.

### Spine (tiers on tiers)
The pendant hangs from metal, not from print: eye nut > threaded rod > crown plate > upper tubes > M4 studs
through the pod bosses > gap struts > deck. Each pod boss is clamped between the two tiers of tube by its stud.
The dome carries only itself and is held down by the washer and eye nut. With the spine off the tool falls back to
an eye bolt in the dome and a load-bearing twist-lock, and says so in the warnings.

### Power cable
A toggle under Hanging. On: a cable hole beside the rod through the dome and, directly under it, through the crown,
with two cable-tie slots on the crown for strain relief. Cable diameter is a slider. The cable is drawn as hardware.

### Form
Per rock: a starting form (polyhedral, conical, rocky, organic) writes the sliders — squareness, facets, facet
depth, edge sharpness, lumps, taper — which stay free. One seed gives one rock at any mesh resolution; the
bounding box is always the width, depth and height you set.

### Texture
Grain, strata, cracks, pitted, hammered: depth and scale in true mm, cut into the outside only. The inside
skin stays smooth and the full wall stays behind the deepest groove. Preview meshes are coarse (about 6 mm
edges); switch on Fine preview to see a texture as it exports, and export at Fine or Ultra.

### Seam line
A toggle under Form › Seam line makes the split between cap and pan part of the design: Reveal (square groove),
V-groove, Bead (raised), Cap proud or Pan proud (one half steps out past the other). Depth, width, 1–3 lines with
spacing, and which rock (both, top, base). It follows each rock's Seam height. Inward styles thicken the inner skin
by the same depth, so the full wall stays behind the detail and the twist-lock is unchanged.

### Diffuser peak (centre cone)
Under Form: profile (bell, cone, horn, dome, stepped + step count), height, radius, sharpness, tip rounding,
sides (0 = round, 3–12 polygon), twist, oval, lumps + lump scale, and a texture: ribs, rings, spiral (scale = spacing
in mm), any rock texture, or "As rocks". The peak never grows past the radius the strut bosses allow.

### Checks the tool makes
Strut circle inside both flat faces, clear of the speaker frame, through the joint bore and under the crown;
seam raised automatically to clear the speaker magnet; breadboard against joint bore and spine tubes; crown
room in the dome; peak clear of the speaker; sealed chamber volume with Qtc and Fc; M4 thread percentage in
the tube bore; hang point over the centre of gravity; every part against the 340 x 320 x 340 bed; overhang
area per part in its print orientation. A refused state shows one line and keeps the last good drawing.

## Sources used for the fixed numbers

- Dayton Audio. *PC83-8 3" Full-Range Poly Cone Driver.* daytonaudio.com/product/1541 — 83 mm frame, 77 mm
  cutout, 92 mm bolt circle, 50 mm depth, 4 holes.
- Parts Express. *Dayton Audio PC83-8, part 295-156.* parts-express.com — recommended sealed volume 0.07 ft3
  (about 2.0 L).
- Loudspeaker Database. *Dayton Audio PC83-8.* loudspeakerdatabase.com/Dayton/PC83-8 — Fs 82.1 Hz, Qts 0.63.
- SpeakerBoxLite. *Dayton Audio PC83-8 specifications.* speakerboxlite.com — Vas 1.7 L, magnet 70 mm.
- M4 coarse thread: pitch 0.7 mm, tap drill 3.3 mm. A 3.5 mm bore (6.5 OD, 1.5 wall) gives 66 % thread.

The square frame outline and the 70 mm magnet are modelled from the spec sheet figures, not from a measured
part: check the first print against a real driver.

## Third-party code

`ui/vendor/three.module.js` and `ui/vendor/OrbitControls.js` are three.js r160, © 2010-2023 three.js authors,
MIT licence (https://github.com/mrdoob/three.js/blob/dev/LICENSE).

## Licence

MIT, see [LICENSE](LICENSE).
# droneByLouisQuek_formFindingTool_islesInstitute
# droneByLouisQuek_formFindingTool_islesInstitute
# droneByLouisQuek_formFindingTool_islesInstitute
