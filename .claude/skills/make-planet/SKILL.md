---
name: make-planet
description: Redraw one Hearts of Durasteel planet as a battlefield map (provinces, states, VPs, terrain, landmarks, FX) with the existing generators in "WIPGFX/plans & scripts", validate it, and show the preview. Use when the user asks to make, redraw or regenerate a planet map.
---

# /make-planet <Planet> [template]

Redraw one planet with the existing pipeline. All commands run from the mod root
(`F:\Documents\Paradox Interactive\Hearts of Iron IV\mod\ProjectKessilian`), with `python -B` (the `__pycache__`
is tracked in git: plain `python` dirties it). `S` below = `"WIPGFX/plans & scripts"`.

Token rules: never open provinces.bmp, definition.csv, ambient_object.txt, the zones JSON or whole state/loc files in
context; read only the lines a validator or assert names. Read a script by section (`grep -n "^def "`, then
`sed -n`). Look at the preview PNG once per run. Do not scan unrelated assets.

## Design rules (from the user; they override defaults)
- Keep all of the planet's province ids; the strategic region stays; only pixels move.
- Big planets: passable provinces outnumber impassable ones. Every state in one piece. Ragged shapes, nothing round.
- Follow canon stills; state / VP names from the research dossier (step 0b), canon first; say which names are
  invented. Never fetch wiki pages by hand (WebFetch returns 402; the research script does it, cached).
- Abandoned planets: no towns, no city models.
- Do not restyle UI, do not add custom tech, do not make focus icons.

## 0. Preflight (always, stop on any failure)
1. `git status --short -- map history localisation` must be empty. If not: stop, show it, ask the user
   (commit, stash, or run with `--allow-dirty`). Never stash, reset or checkout yourself.
2. `python -B "$S/validate_planet.py" <planet>` on the current state: note the state ids, province count and any
   errors that already exist (pre-existing errors are not yours to fix unless asked; report them).
3. If `$S/<planet>_map.py` exists, this is a re-run: skip to step 2 unless the user asked for design changes.

## 0b. Research (read the brief first; go deeper only for a decision that needs it)
1. Read `WIPGFX/research/<slug>/design_brief.md` (~2k tokens) and nothing else yet: candidate states (anchors),
   VPs by type (settlement / military / battle / landmark), visual identity, the geography the sources state,
   SUGGESTIONS (labelled inference) and the layout questions. If it does not exist:
   `python -B "$S/research_planet.py" <Planet>` (Wookieepedia title, e.g. `"Raxus Prime"`; ~1 min the first time,
   0 requests afterwards; it rewrites the brief from cache, so re-running after a script update is free).
2. Go deeper only when a design decision needs evidence the brief does not show, cheapest first:
   a. one fact query, e.g. everything about one place:
      `python -B -c "import json;[print(f['continuity'],f['era'],f['text']) for f in json.load(open('WIPGFX/research/<slug>/facts.json',encoding='utf-8'))['facts'] if f.get('place')=='Kway Teow']"`
      (filter on `category`, `continuity`, `era`, `site`, `field`; skip facts whose `review` is not empty unless
      checking them on purpose: fragment / narrative / weak-category / off-surface / not-in-clone-wars);
   b. the matching section of `dossier.md` (~3.4k tokens whole: read only the section you need);
   c. a source page: its URL is in the fact's `evidence`; never fetch it by hand, run `--gaps` / `--refresh`.
   Never open `facts.json` / `sources.json` whole.
3. Only if the design needs an open / partial gap: `python -B "$S/research_planet.py" <Planet> --gaps` (each
   search runs once). `--refresh` only when the user says the wiki changed or a source was unavailable.
4. Questions: before designing, ask the user ONE batched question covering the brief's "Questions that change
   the layout" that actually change this map (e.g. which capital, which points of interest exist, which
   affiliation owns which part). Skip conflicts that change no state, VP or terrain (moons, imports, ...). The
   default when the user has no preference: canon, Clone Wars era.
5. Layout (where things are on the planet) is almost never in the sources: the brief lists what is stated;
   everything else is a design choice and is named as such in the script docstring.
6. Images: `references/index.json` lists every candidate with its file page; the wiki CDN refuses automated
   downloads (respected, not worked around), so ask the user for stills or open a file page link only when a
   shape really matters. Licensing is not cleared: reference only, never ship them in the mod.

## 1. Design (the only step that needs reasoning)
Copy the closest template (default by look: open ground with features → `kadavo_map.py`; desert with mesas, several
owners, pinned lane ends → `florrum_map.py`; valley walled by mountains, spare ids → `korriban_map.py`). Raxus,
Raxus Prime and Felucia are not templates (Felucia is driven by a hand-drawn plan image, `felucia_map.py`).
Edit only: the docstring, `PLANET`, `ZONES_*`, `KIND`, `TERRAIN`, `SEED`, `CAPITAL`, `OWNER`, `FEATURES`, `SEEDS`,
`STATE_NAMES`, `IMPASSABLE`, `VPS`, sizes like `PLAINS_PX`, and `layout()` / `tidy()` if the shapes need it.
State ids must be the planet's own (from preflight) or unused ids for new states. The shared write path lives in
`$S/planet_common.py` (guard, measure, write_map, write_zones, old_states, state_names_loc): reuse it, do not copy it.

## 1b. Iterate the layout without writing (copy this from zygerria_map.py)
A new map script gets `--dry OUT.png`: layout + every assert, writes only the PNG (zygerria_map.py `preview`). Iterate
shapes there (Zygerria: 3 dry runs); size provinces from a passable target (`TARGET_PASSABLE`), not a px constant.
Shapes painted first win: draw plateaus / fortresses / ramps BEFORE the rock round them, and keep ramps short.

## 2. Generate
`python -B "$S/<planet>_map.py"`
- `planet_common.guard` refuses dirty files and foreign state ids before anything is written. On refusal: report it.
- On an assertion (`"<feature> in pieces"`, `"the open ground is cut in two"`, `"state N in pieces"`, X crossing),
  nothing useful was written only if it failed before `write_map`; either way run
  `git status --short -- map history localisation`, report the assertion line and what changed, and ask the user
  before restoring anything. Adjust shapes at most once per user go-ahead; do not loop retries.
- If the planet now has fewer province ids than before: `python -B "$S/free_province_ids.py"` (it refuses on
  script references; report a refusal).

## 3. Validate (always after 2)
`python -B "$S/validate_planet.py" <planet>` → exit 1 = errors: stop and report the ERROR lines (file:line).
Then Read `WIPGFX/Assets/<planet>_check.png` once and show it to the user: states coloured (impassable dark, ids in
the legend with X), victory points ringed in gold. Wait for the user's OK before the art stages.

## 4. Art stages: only those the user asked for, or that the planet already has. Never re-run a finished stage
   unless its inputs changed (the map changed → terrain, placement and globe must follow; nothing else does).
| Stage | Command | When |
|---|---|---|
| Terrain | `python -B "$S/planet_terrain_gen.py" --<planet>` | planet has a repaint fn + flag (`--kadavo`, `--florrum`, `--korriban`, `--raxus`, `--raxus-prime`, `--felucia`). New planet: add `def <planet>(t, trees, city, h, labels, names, pid, rng)` + flag by copying the nearest one, `repaint_planet()` does the writing |
| Models | `"F:/blender-4.2.23-windows-x64/blender.exe" -b --factory-startup --python "$S/military_buildings.py" -- models <prefix>` then `python -B "$S/military_buildings.py" <planet>_atlas` if one exists | only for new or changed landmark models; preview with `blender ... --python "$S/render_mesh.py" -- OUT.png a.mesh` |
| Placement | `python -B "$S/military_buildings.py" <planet>_place` | the planet has one (korriban, florrum, kadavo) and the map changed |
| FX | `python -B "$S/<planet>_fx.py"` (`kadavo_fx.py`, `florrum_fx.py`, `felucia_mist.py`) | exists and the map changed |
| Globe | `python -B "$S/planet_terrain_gen.py" --globe-texture` | once, last, after any terrain/colour change |

Blender gotchas: `export PYTHONPATH="$APPDATA/Blender Foundation/Blender/4.2/extensions/user_default"` (io_pdx_mesh),
and Blender exits 0 even on a Python traceback: grep its output for `Traceback`. `render_mesh.py -- OUT.png a.mesh`
writes OUT_oblique.png and OUT_top.png. Reused models (another planet's entities) must not be defined again: the
planet's own .gfx/.asset list only its new meshes (PLACEMENT new_models).
New planets are configured, not coded: copy `TERRAIN_CFG` and `PLACEMENT` from zygerria_map.py into the new map
script and edit the values (zone -> relief operator / textures / props / city style; models with scale and where).
Run `planet_terrain_gen.py --planet <Planet>` and `military_buildings.py place <Planet>`; both validate the tables
first (missing meshes, entities defined twice or nowhere, unknown VPs / zones / textures) and write nothing on error.
Only a genuinely new shape needs code: a `hook(ctx)` in the table, or a new operator in planet_terrain_gen.zone_repaint.
Models (user, 2026-10-14): every planet gets its OWN custom landmark models, BIG at map scale (like the Kadavo facility,
Korriban academy, Raxus senate); no reused camps / docks / arenas from other planets and no shrinking to fit; ask first.
Model code: `military_buildings.models()` with the Kit (box / tube / lathe / prism), e.g. `zygerria_palace`.

Run order: map → (free_province_ids) → validate → terrain → models → placement → FX → globe → validate again.

Files each stage writes (all tracked; preflight = `git status --short -- <these>` must be empty):
- map: `planet_common.WRITES` (provinces.bmp, definition.csv, adjacencies, buildings, railways, airports,
  rocketsites, supply_nodes, unitstacks, history/states, history/units, state/VP loc) + `WIPGFX/Assets/<planet>_zones.*`
- terrain: map/heightmap, world_normal, terrain, trees, cities .bmp, buildings/unitstacks (heights);
  `--florrum` also map/terrain/colormap_rgb_cityemissivemask_a.dds
- placement: map/ambient_object.txt, gfx/entities/hod_<planet>.{gfx,asset}, the zones files
- FX: map/ambient_object.txt, gfx/entities + gfx/particles/hod_<planet>_*.asset, map/strategicregions/<id>-<Planet>.txt
- globe: map/terrain/mud_diffuse_rgb_gloss_a_{0,1,2}.dds

Expected, harmless diffs after re-running an existing planet (Florrum trial 2026-10-14: everything else came out
byte-identical to HEAD): the planet's lines move to the end of the loc files, supply_nodes.txt, buildings.txt,
unitstacks.txt and ambient_object.txt (same lines, other order). Do not investigate those; anything else is real.
Timings: Florrum/small planets map ~2 min, terrain ~10 s, place/FX ~2 s, globe ~8 s; Korriban-size maps ~5 min
(uncross is slow), not a hang.

## 5. Finish
Run the validator once more, then report: stages run, validator summary, files changed
(`git status --short`), and anything left for the in-game check (the user does that). Never commit unless the user
asks; never run destructive git commands.
