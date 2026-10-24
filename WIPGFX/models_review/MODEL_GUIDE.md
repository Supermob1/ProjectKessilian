# 3D model refinement: workspace and rules

Everything here is generated except this file and the hand columns of `review.csv`.
All commands run from the mod root, always with `python -B`. `S` = `"WIPGFX/plans & scripts"`.

## Files

| Path | What | Made by |
|---|---|---|
| `review.csv` | one row per landmark mesh (639) + one sample per town set (128), 175 planets | `python -B "$S/model_inventory.py"` |
| `renders/<mesh>.png`, `<mesh>_top.png` | oblique and top render of each mesh | `python -B "$S/model_review_render.py"` |
| `sheets/<Planet>.png` | contact sheet per planet: landmarks, then the town sample, labelled | same (`--sheets` = sheets only) |
| `render_log.txt` | last full render run | same |

`review.csv` columns:
- **facts** (re-read on every inventory run, never edit): mesh, kind, planet, title, function, source (file:line of the geometry function), atlas, scale/clear/where (from the planet's PLACEMENT), mesh_kb, built, render, path.
- **hand** (kept by mesh name across runs, edit freely in Excel / LibreOffice): `priority`, `status`, `issues`, `plan`, `refs`.

20 meshes have no `function`. They are built by planet-specific code in `military_buildings.py`, not by a `build(...)` call:
- hod_flo_outpost_a/b;
- hod_flo_vault_r5;
- hod_kor_tomb_*_rN;
- hod_lola_chunk_*.

Grep the mesh name to find their code.

## Priority and status values

| priority | meaning |
|---|---|
| P1 | wrong or broken: does not match canon, generic box pile, floating or holed parts, black faces, reused look |
| P2 | right idea, too plain or too small at map scale, few props |
| P3 | good, polish only |
| ok | leave alone |

`status` values: `todo`, `wip`, `rebuilt`, `checked-in-game`. Only the user sets `checked-in-game`.

Hints for a first pass:
- Sort by `mesh_kb`. Small meshes (under ~40 KB) are usually the plain ones.
- Use `built` to find the old ones.
- Look at the planet sheet, not single renders, so a planet's set stays consistent.

## Rules (from the user, they override taste)

- **Canon first.** Match the canon reference stills (Clone Wars era), and put the reference link or file in `refs`. Wookieepedia material comes from `research_planet.py` (cached). Never fetch it by hand; the wiki CDN refuses image downloads, so ask the user for stills.
- **Big.** Models must read at map scale, like the Kadavo facility, the Korriban academy and the Raxus senate. Never shrink to fit; move the placement instead.
- **Custom per planet.** No camps, docks or arenas reused from another planet. Each planet's town set is its own.
- **Cities get their own building sets, ruined ones included.** Abandoned or uninhabited planets get no towns and no city models.
- **Naval = space.** Shipyards, drydocks and naval bases are orbital stations beside the disc, never on the ground or the water.
- **Generous props.** Trees, rocks, pads and pipes keep a landmark from looking like a lone box. Leave out mist and halo rings: they render as flat discs.
- **Colours.** Atlas colours below ~100 RGB render black in game. Keep the atlas swatches above that.
- **No UI restyles, no focus icons.**

## Geometry conventions

- The code lives in `arch_kit.py` (1000+ functions) and the `models()` build loops in `military_buildings.py`. Each geometry function is `def name(k):`, where `k` is the Kit.
- Units: 1 = one map pixel-ish. z = 0 is ground level. Walls run down to `-SKIRT` (2.5) so slopes never show gaps.
- **The camera looks from -y.** Put cliffs, backdrops and tall parts at +y, or they hide the model in renders and in game.
- Kit primitives:
  - `k.box`, `k.tube`, `k.lathe(profile, rects, sides, cx, cy, cap, sy, jitter)`, `k.prism`.
  - Helpers:
    - `tbox`, `prism_at`, `fin`, `legs`, `curve_tube` (negative bulge sags);
    - `dome`, `pad`, `vault`, `rock`;
    - `loft`, `banded`, `sweep`;
    - `kas_trunk` (h = absolute top);
    - `town_cell` (palette lambdas get z0 = -0.3, top = absolute h);
    - `gunship`, `shuttle`.
  - Ecumenopolis kit: `etti_*`, `arco_*`.
- Texture slots:
  - `B_*` is the landmark atlas: CONC, CONC_WIN, DARK, DUST, GIRDER, GLOW, HAZARD, HULL, PAD, PIPE, PLATE, PLATE_WIN, ROOF, RUST, SOOT, BRICK.
  - `E_*` is the city atlas.
- A planet atlas is `_atlas_generic(name, seed, {B_*: rgb})` in `military_buildings.py`, selected with `tex="hod_<planet>"` on the `build`.
- Keep the mesh name. Renaming means changing the .gfx/.asset files, `landmarks_lore.py`, PLACEMENT and ambient_object.txt.

## Rebuild loop (one model)

1. Edit the function at `source` (file:line in review.csv).
2. Build it:
   ```
   PYTHONPATH="$APPDATA/Blender Foundation/Blender/4.2/extensions/user_default" \
   "$LOCALAPPDATA/universal-modder/tools/blender-4.2.3-windows-x64/blender.exe" -b --factory-startup \
       --python "$S/military_buildings.py" -- models <mesh or prefix>
   ```
   Blender exits 0 even on a Python error, so grep its output for `Traceback`.
3. Render it: `python -B "$S/model_review_render.py" <mesh>`. This also refreshes the sheets.
   - Render one mesh per Blender. Batching meshes into one Blender mixes up their textures.
4. If an atlas colour changed: `python -B "$S/military_buildings.py" <planet>_atlas`.
5. If the footprint or size changed: `python -B "$S/military_buildings.py" place <Planet>`, then `python -B "$S/validate_planet.py" <planet>`.
6. Set `status` to `rebuilt` and note what changed in `plan`.

A plain `python -B "$S/model_review_render.py"` re-renders only meshes newer than their png. Run it after a batch.

## Review checklist (per model)

- [ ] Recognisable as the canon place from the oblique render alone.
- [ ] Silhouette has 2 or 3 height levels, nothing reads as one box.
- [ ] Big enough next to the town sample on the same sheet.
- [ ] Nothing floats, no holes, no black faces, no z-fighting stripes.
- [ ] Props: pads, pipes, trees or rocks fit the planet.
- [ ] Planet atlas used, colours above ~100 RGB.
- [ ] Nothing tall on the -y side.
- [ ] Ruined or abandoned state is right for the planet's lore (`landmarks_lore.py`, pre-war history).

Not verifiable here: how a model looks in game (lighting, snow shader, map scale). The user checks that in game.
