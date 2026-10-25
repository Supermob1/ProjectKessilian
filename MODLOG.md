# MODLOG — Hearts of Durasteel map overhaul

## Goal
Space-looking map: galaxy background + stars instead of water; planets as flat "biomes to fight in"
(individual heightmaps, biomes, trees, atmospheres); Star Wars terrain textures.
Done = verified in game (screenshots + clean error.log) for each part.

## Recon (2026-10-03)
- Game: F:\SteamLibrary\steamapps\common\Hearts of Iron IV (Steam), Clausewitz, no anti-cheat, no loaders.
- Route: data/asset overrides only (map/*.bmp, map/terrain/*.dds, gfx/FX/*.shader). No code injection needed.
- Oracle: Documents/Paradox Interactive/Hearts of Iron IV/logs/error.log + in-game screenshots.
- `um` CLI: no uv, `python3` is the MS Store stub -> run as
  `PYTHONPATH=<plugin root> python -m um ...` (plugin root: ~/.claude/plugins/cache/universal-modder/universal-modder/0.1.0).
- fal: MCP server token rejected (401); no FAL_KEY in env or .env -> texture generation blocked on a key.

## Map facts
- Map 3072x3328. 147 land bodies (planets/moons), 21.9k provinces. Sea level: heightmap ~95.7/255.
- terrain.bmp palette index -> atlas texture via common/terrain/00_terrain.txt (4x4 atlas, 512px tiles).
  tex 6 = water, 10 = urban grid, 14 = lava; perm_snow on indices 14/16/19.
- world_normal.bmp (half res): R = -k*dh/dx, G = +k*dh/dy, B = up (fit from vanilla, k~0.05/half-px).
  The original mod file was fully flat (127,127,253).
- trees.bmp: vanilla ratio 3.413 map px per tree px -> 900x975. Indices from gfx/entities/trees.gfx:
  2 palmer, 3 palms_blend, 5 forest_blend, 6 forest, 11/28/29 beech.
- Galaxy background = map/terrain/colormap_water_{0,1,2}.dds (uncompressed BGRA, 1 mip). Visible only through
  the water shader's refraction pass (absent on low graphics: NO_REFRACTIONS).
- colormap_rgb_cityemissivemask_a.dds = painted planet images (had sphere lighting baked in), overlay-blended on the atlas.
- PIL mmaps BMPs: open via BytesIO or Windows refuses to overwrite the file (Errno 22).

## Work done
- gfx/FX/pdxwater.shader: vanilla copy, pixel shader replaced: galaxy via undistorted refraction + 3 parallax
  star layers; kept borders/map modes/FOW/dominance. Knob: GALAXY_BRIGHTNESS.
- WIPGFX/plans & scripts/planet_terrain_gen.py (--preview DIR / --write): regenerates terrain.bmp, heightmap.bmp,
  world_normal.bmp, trees.bmp, both colormaps. Pristine inputs in WIPGFX/Assets/map_base/.
  Worlds: 20 temperate, 37 ocean, 12 swamp/jungle, 29 desert, 6 ice, 14 lava, 9 ecumenopolis, 20 barren.

## Restore path
All map outputs are git-tracked: `git checkout -- map/` restores the originals. Script inputs in WIPGFX/Assets/map_base/.

## In-game test 2026-10-03 (hoi4.exe direct launch, borderless 2048x1152, mod via dlc_load.json)
- `um win launch "<install>/hoi4.exe"`; the game drops straight into a running 976 campaign (continue_game).
- Startup ~45 s. error.log: no shader/map/tree/colormap errors (only pre-existing missing leader portraits).
- Verified on screen: galaxy background back (grid + arms), parallax stars, flat textured planets (no sphere look),
  per-planet atmosphere rims, mountain relief with shadows up close.
- Known: galaxy art is 1536px wide -> blurry at close zoom, its grid line becomes a wide dark band.
  Stars are dense at max zoom-out ("snow"); tune the StarLayer densities in pdxwater.shader if needed.
- Zoom by `wheel` is unreliable (momentum: same sign zoomed in once, out twice). Use keyboard/other means next time.
- Trees not yet seen on screen (only draw within camera ~350).

## Atlas textures via local ComfyUI (2026-10-03)
- ComfyUI Desktop API: http://127.0.0.1:8188 (RTX 5080 16 GB). Output dir F:\Comfy-Desktop\ComfyUI-Shared\output.
- Model chain copied from the official template image_krea2_turbo_t2i.json: UNETLoader krea2_turbo_fp8_scaled +
  CLIPLoader qwen3vl_4b_fp8_scaled (type krea2) + VAELoader qwen_image_vae, KSampler 8 steps cfg 1 euler/simple,
  negative = ConditioningZeroOut. ~65 s for the first image (model load), 1024x1024.
- Atlas format: atlas{0,1,2}.dds = 2048/1024/512, DXT5, full mips, 4x4 tiles (slot = `texture =` in 00_terrain.txt).
  Diffuse RGB + A = gloss; atlas_normal RGB = tangent normal, A = spec. Pillow 12 writes DXT5 (1 level);
  atlas_gen.py concatenates mip levels and patches the header (mipcount + caps).
- Script: WIPGFX/plans & scripts/atlas_gen.py (--generate / --regen N / --preview / --write). Sources cached in
  WIPGFX/Assets/atlas_src/ with manifest.jsonl (seed + prompt per slot). Originals: git (map/terrain/atlas*.dds).

## Status / next
- [x] In-game verification of shader, galaxy, atmospheres, relief.
- [ ] Trees on screen (needs a close zoom).
- [x] Star Wars atlas textures generated in ComfyUI and packed (atlas0-2 + atlas_normal0-2, sizes/mips identical to originals).
  Lessons: don't say "seamless tileable" in the prompt (Krea draws a 2x2 grid); tile in post, one axis at a time
  (a 2-axis half-offset blend leaves the shifted copy's seam lines visible). Redone slots: 6 water, 10 city, 14 lava.
- [x] Trees confirmed in game by the user.
- User feedback (round 3): textures too low-res + uncanny, terrain.bmp too uneven (single-texture planets repeat),
  stars too visible, wants the galaxy drawn by the shader. Chose: aerial landscapes, 8x8 atlas @ 1024px.

## Round 3 (2026-10-03)
- Stars: STAR_INTENSITY 0.3, fade to ~0.1 when zoomed out; denser along galaxy arms.
- Galaxy: procedural in pdxwater.shader (GalaxyColor: log-spiral arms + spurs, bar/bulge, dust lanes, nebula knots,
  faint grid at the old 297.6-unit spacing). Centre (1374,1726), radius 1700 = old art. Own atan2 (vanilla GLSL
  atan2 wrapper swaps args). colormap_water now = atmospheres on black, added on top via refraction.
- Engine limits: constants.fxh TERRAIN_TILE_FREQ 128 (tile = ~26 map px), MAP_NUM_TILES 4, TEXELS_PER_TILE 512,
  ATLAS_TEXEL_POW2_EXPONENT 11. Index decode allows 8x8. Override prepared in
  `WIPGFX/plans & scripts/pending/constants.fxh` (8 / 1024 / 13) -> move to gfx/FX/ ONLY together with the 8x8 atlas.
- gfx/FX/pdxmap.shader: vanilla + anti-tiling (two rotated/rescaled samples swapped by noise, macro brightness).
  Rebuild from vanilla with `WIPGFX/plans & scripts/make_pdxmap_shader.py`.
- 00_terrain.txt: hod_tex_00..63 = terrain.bmp index 32+N -> texture N. ocean_15 -> texture 45.
- planet_terrain_gen.py painter: RECIPES per planet type x roles (low/mid/high/steep/wet/forest/jungle/accent),
  each planet picks its own subset; trees follow painted slot (TREES_OF_SLOT). Not yet --written (needs new atlas).
- ComfyUI was closed mid-run -> 64-slot generation not started. Old 16 sources in WIPGFX/Assets/atlas_src/v1_4x4/.

## Next (in order, once ComfyUI is back)
1. atlas_gen.py --generate (64 slots), review contact sheet, --regen bad ones, --write.
2. Move pending/constants.fxh -> gfx/FX/. 3. planet_terrain_gen.py --write. 4. In-game check.

## Texture work abandoned (2026-10-03, user decision)
- Stopped at 37/64 seam-inpainted tiles (system low on RAM). Restored from git: map/terrain/atlas*.dds and
  common/terrain/00_terrain.txt; deleted the pending 8x8 constants.fxh. planet_terrain_gen.py paints with the
  vanilla 16-slot PAINT tables again (its output matches the files on disk).
- Kept: gfx/FX/pdxmap.shader anti-tiling (works with any atlas; untested in game), atlas_gen.py + sources
  (WIPGFX/Assets/atlas_src) in case the idea is revisited. Seam-inpaint (roll + repaint centre cross) beat the
  cross-fade clearly; prompts: 'satellite map tile ... orthographic' avoided perspective/fisheye.

## Round 4 (2026-10-03): SW galaxy chart, per-planet biomes, Coruscant buildings + globe
- Galaxy: pdxwater.shader GalaxyColor rebuilt after the canonical coordinate galaxy map
  (starwars.fandom 'Coordinate_galaxy_map.jpg'). Affine fit chart->map on 19 planets (median err ~180 units):
  Deep Core at (880,1700) next to Coruscant (813,1797); region rings 185/320/460/640/850/1200/1600, centres drift
  east/south; grid 191.3 x 187.5 from origin (-847,3499). Fades out between camera y 1000 and 400
  (GALAXY_FADE_NEAR/FAR): up close only stars + planets + atmospheres. Numpy twin: swgalaxy_sim.py.
- planet_terrain_gen.py v3: old terrain.bmp ignored. 13 archetypes, canon by state name (CANON / CANON_FULL), all
  147 bodies matched. Per-archetype relief (ranges, river valleys, dunes, mesas, canyons, glaciers, volcano cones,
  archipelagos, city terraces, craters); climate T (altitude + latitude) x M (noise + near water) -> 16 vanilla
  textures; colormap now near-neutral (0.5) + 20% painted hue, city lights in alpha on urban paint.
  Bug fixed on the way: mesa formula scaled absolute height -> worlds clamped to sea level.
- Tools: portable Blender 4.2.3 + io_pdx_mesh 0.91 in %LOCALAPPDATA%/universal-modder/tools. Import the add-on
  by sys.path (scripts/addons) - addon_utils.enable fails headless. import_meshfile needs join_materials=False on 4.2.
- Coruscant buildings: coruscant_buildings.py (textures | meshes). 13 towers, decimated to ~3k tris, 3 materials
  (facade/metal/lights) on PdxMeshAdvanced (normal G/A = xy, B = night emission; properties G spec, B metal,
  A gloss). Must transform_apply(location=True) before centring or the FBX offset survives export.
  map/cities.txt (mod override): every style -> towers, outskirts short, downtown tall. cities.bmp unchanged
  (style map only; amount of city comes from the game).
- Coruscant globe: coruscant_globe.py (clouds baked in, city lights as emission). gfx/FX/pdxmesh.shader = vanilla +
  HOD_ZOOM_FADE clip + effects HodPlanetGlobe / HodPlanetGlobeShadow (no shadow). Placed in map/ambient_object.txt
  at (812.9, 71, 1797.5), entity scale 60 = planet radius.
- NOT yet verified in game: all of round 4.

## UI restyle (2026-10-05)
- Reference style = KOTOR 'Remastered UI 1.3' (C:/Users/steve/Desktop/Remastered UI 1.3/Override, .tga + binary .gui).
  The mod's settings menu already reuses it (generic_checkbox = i_checkbox rings). Palette: navy (0,1,22), row navy
  (16,18,45), steel line (0,88,137), cyan (0,172,248), hover yellow (248,252,0), active green (69,232,26).
- First attempt (plain black boxes with blue borders, ui_restyle.py) REJECTED by the user and deleted.
- `WIPGFX/plans & scripts/kotor_ui.py`: rebuilds every vanilla chrome texture the mod doesn't override yet out of KOTOR pieces.
  It keeps each texture's path, size and frame count, so no .gfx/.gui edits are needed.
  window tiles = 9-slice from lbl_cg_mcgtopl (drawn by KOTOR as an overlay: navy outside the arc, so it's inverted).
  Buttons = 3-slice SCR_DEF_NN/NC/SC (normal, yellow hover, pressed); disabled = dimmed NN.
  Flat panels = rounded corners; thin strips = ( ) bracket bar; plain checkboxes = i_checkbox01/02.
  Draggers = lbl_miscroll_f; select/highlight/hover frames = yellow corners; glyph textures = tint onto the palette.
  --mockup/--preview/--list/--write. WRITTEN 1327 textures; undo list in kotor_ui_written.txt (delete those paths).
- PERSONAL USE ONLY (user's choice): these files contain KOTOR / Remastered UI art. Don't publish or push them to
  the public GitHub repo without the Remastered UI author's permission.
- Not covered: icons (tech/ideas/equipment/units), the KOTOR green title arc on windows, and 1920x1080 screen backgrounds.

## Coruscant towers / floating buildings (2026-10-05)
- Root cause of the missing towers: common/terrain/00_terrain.txt forest_13 (urban) had lost `spawn_city = yes`
  (removed 2023 in commit 11a8ac90 "trying more fixes"), so no city meshes spawned anywhere. Re-added.
  IF THE GAME CRASHES on map load, remove it again (that commit may have been a crash workaround).
- Tower meshes re-exported with shader PdxMeshSnow (all vanilla city meshes use it; same texture layout as Advanced).
- cities.txt: `1e-05` -> `0.00001`. cities.bmp is all palette index 1 now (HEAD had all 15); every group = towers anyway.
- Floating buildings: map/buildings.txt still had heights from the old heightmap. planet_terrain_gen.py `reheight()`
  (also its own flag `--reheight`, and it now runs in --write) re-snaps buildings.txt + unitstacks.txt: y = heightmap px / 10.
- NOT yet verified in game (user tests).

## Round 2 (2026-10-05, after the user's first in-game test)
- Towers spawned (spawn_city fix confirmed) but rendered as black mirrors in a dense grid of identical towers.
  Cause: properties B = metalness, and the shader zeroes diffuse when metalness is near 1. Facade B was met.jpg
  (near 255) and metal B was 210. Now facade B = met*0.15 and metal B = 70. The facade diffuse was dark glass
  (mean ~37), lifted with *2.2+45 (now mean ~108).
  Size: entity scale 0.7 -> 0.3 (towers were ~20x vanilla city mesh height). Density: the ACTIVE group is
  color_index 1 (cities.bmp is all 1): 1.0 -> 0.35 (index 15 group 0.9 -> 0.35 as well).
- UI only partly converted. Reasons: (a) 520 big textures were only tinted, (b) the mod's own 118 older chrome
  textures (tiled_window*, buttons) were skipped, (c) .gui layouts still decide placement.
  kotor_ui.py now: big textures -> "screen" (navy panel + the vanilla layout traced as steel lines). The mod's own
  flat chrome is converted too, with its original backed up in WIPGFX/Assets/ui_backup/ (88 files). The mod's own
  detailed art is never touched. SKIP adds techtree_bg, lines, anim, progress, arrow, fill, meter, gauge, propaganda.
  A re-run restores paths the rules now exclude (backup or vanilla). 1330 textures written.

## Round 3 (2026-10-05, user feedback: "mod textures looked fine before", cities "not pretty enough", UI "too dark")
- Restored all 88 of the mod's own UI textures from WIPGFX/Assets/ui_backup (byte-identical). kotor_ui.py now
  NEVER touches mod-owned files. The vanilla conversions (1246, kotor_ui_written.txt) are still in place:
  the user called them too dark / not what they had in mind -> waiting for direction (or revert them).
- Cities: single towers on HOI4's spawn grid read as rows of needles. WIP: `coruscant_buildings.py blocks` builds
  12 city-block meshes (hod_cor_block_{band}{variant}), up to 4 towers + low-rise filler boxes each.
  Bugs found by rendering (WIPGFX/coruscant_blocks_wip.png): re-decimating the towers shreds them (removed); each
  .mesh imports as 3 objects (one per material), so all 3 must be transformed. Filler boxes still render black and
  are missing in some blocks. NOT wired into cities.txt yet (the game still uses single towers, scale 0.3, density 0.35).

## Round 5 (2026-10-09): painted globes at zoom-out, researched biome mixes
- fow_rgb_waterspec_a.dds RGB == the original painted colormap (planet spheres). It is not bound to the land
  shader, so the colormap RGB is the painting again (planet_terrain_gen.py writes WIPGFX/Assets/map_base's RGB).
  gfx/FX/pdxmap.shader (via make_pdxmap_shader.py): up close the tint = hue only (0.4 + 0.1*c/lum, same look
  as the old neutral colormap); between camera y PLANET_PAINT_NEAR 450 and FAR 1100 the diffuse fades to the
  painting (before borders, so map modes stay visible). Knob PLANET_PAINT_GAIN.
  gfx/FX/tree.shader = vanilla + the same hue-only tint (trees also read the colormap).
- Biomes: CANON tables replaced by PLANETS (biome mix per world, "[@lat|@x|@y] arch share ..."), from the
  Wookieepedia infobox climate/terrain (cached: WIPGFX/Assets/planet_wiki.json). Zones per world; relief per zone,
  blended across borders (soft()); sea share + climate per zone. New archetypes: alpine, grassland, sinkhole
  (Utapau: raised plateau + sheer pits). Ryloth @x (tidally locked), Kessel @y, Telos/Kalee/Carida/Yag'Dhul @lat.
  Fixed vs wiki: Boz Pity, Cato Neimoidia, Colla IV, Byss, Anoat, Pammant/Copero (were ocean).
- --preview now also writes preview_big.png / height_big.png and centroids in archetypes.txt.
- Written to map/. NOT yet verified in game.

## Round 6 (2026-10-09): low base heights, country colours fade when zoomed out
- planet_terrain_gen.py: GROUND 104 -> 97 (= SHORE, ~1 above the 95.7 water plane). Relief only rises from the base:
  rel = GROUND + amp*1.6*smoothstep((low-0.3)/0.7)^1.5, low ranked per world (~30% of each world at the base).
  City terraces 98..105, lakes flat at SHORE, sea/elevation ranks tie-broken by `low` on the flat base.
  Sinkhole plateau: +18 with a tight blur (soft() smeared it on small Utapau), no canyon cuts.
- pdxmap.shader: gradient borders + occupation stripes fade with vPlanetFade down to PLANET_BORDER_KEEP (0.2);
  vBloomAlpha scaled the same way.
- Written to map/. NOT yet verified in game.

## Round 7 (2026-10-09): organic cities, giant trees, props, sandcrawlers
- Cities: coruscant_buildings.py `meshes 400 hod_cor_tower_lp` (13 towers ~800 tris, from source) -> `clusters`
  (16 meshes hod_cor_cluster_{band}{variant}: 3-7 towers Poisson-scattered in a lobed blob, tall core, any heading,
  2.4-5.7k tris) -> `wire` (writes gfx/entities/hod_coruscant_buildings.{gfx,asset} + map/cities.txt, scale 1,
  same densities). Old single-tower meshes and WIP blocks deleted. Bug fixed: meshes() now drops unused material
  slots (empty sub-mesh broke re-import).
- Flora/props: flora_props.py (download | textures | meshes | procedural | wire). Poly Haven CC0 models in
  WIPGFX/3d/polyhaven (168 MB, glTF 1k + leaf alpha maps). trees.bmp index -> mapobject_N in gfx/entities/trees.gfx
  (vanilla entries + ours). 42/43 quiver trees, 44 shrub-tree, 45 succulent, 46 fern, 47 fallen trunk, 48/49 moon
  rocks, 50 desert boulder, 51 mossy rock, 52 boulder (leaf cards thinned + enlarged, solids decimated per material).
  Procedural (Blender): 40 wroshyr giant, 41 jungle giant (trunk + roots + branches + leaf-card clumps using a
  foliage-clump texture composed from Poly Haven leaves), 53 Jawa sandcrawler (100 tris, procedural rust texture).
  Photo-scanned island trees were dropped: at 2k tris their trunks shred and canopies become confetti.
  Gotcha: Mesh.materials.clear() resets face material indices -> replace slots in place.
- planet_terrain_gen.py: GIANT_WORLDS (Kashyyyk 85% of trees giant, Endor/Yavin/Ithor 50%, ...), PROPS per zone
  archetype on empty ground. 16 sandcrawlers on desert zones.
- Unverified in game: multi-material meshes in the tree renderer (vanilla trees use one material), cities perf.

## Round 8 (2026-10-09): tree leaves fixed, towns for non-ecumenopolis worlds
- User: giant trees showed no leaves. The tree renderer draws only a mesh's first material (vanilla trees all have
  one). flora_props.py now writes one atlas per multi-material model (hod_flora_<idx>_atlas_{diffuse,normal}.dds,
  one vertical slot per material, atlas.json = slot order) and single_material() remaps UVs into the slots.
  Procedural trunks no longer wrap v (vrep 1). All 14 flora meshes have 1 material now.
- User: cities look great; wants smaller towns elsewhere. coruscant_buildings.py `towns` (16 meshes hod_town_*:
  stucco domes + flat-roofed blocks, 1-2 short low-poly towers in bands 3-4, 86-2070 tris, height 0.2-0.5) with
  hod_town_plaster textures (lit windows in normal B). `wire` writes CITY_GROUPS: cities.bmp 1 = tower clusters,
  2 = towns (density 0.3). planet_terrain_gen.py --write paints cities.bmp: 1 in "city" biome zones, 2 elsewhere.
  Densities written as plain decimals (0.00001, not 1e-05).

## Round 9 (2026-10-09): white squares, Teta megacity, treeless deserts, desert props
- "White squares near towns": town houses were built with no UV layer -> every face sampled one bright texel.
  towns() now creates the UV layer and maps each building into one of 4 darker plaster variants; roofs (normal
  z > 0.6) use the right half (no windows, no night glow), walls the left half. NOT verified in game: if squares
  remain, suspect PdxMeshSnow snow on flat roofs.
- Empress Teta ("Tetan Depths") = city .75 industrial .25 -> tower clusters.
- planet_terrain_gen.py: TREELESS zones (desert, reddesert, sinkhole, barren, lava) get no trees at all.
  Desert props: 53 sandcrawler (now 0.008/cell, ~80), 54 moisture vaporators x3, 55 homestead (adobe domes +
  vaporator), 56 half-buried Star Destroyer (rare, ~3), boulders, bare rocks, rare succulents.
- flora_props.py procedural: vaporators/homestead/wreck + hod_metal_grey / hod_adobe textures (surface()).
- Terrain atlas textures: still to do (user wants it; approach to decide together).

## Round 10 (2026-10-09): Sketchfab models (CC BY), speeder trains
- User downloaded 6 Sketchfab models to WIPGFX/3d/sketchfab/ (credits in CREDITS.md + sketchfab_props.py docstring).
- sketchfab_props.py: `bake [names]` (Blender: normalise size, octree remesh for big hard-surface models, decimate,
  smart-UV, Cycles diffuse-colour bake of the original onto 1024 px, metallic/transmission zeroed first) ->
  `textures` (512 DDS + writes texture names into the .mesh: exporting before the DDS exist leaves them empty) ->
  `wire` (trains). Props: 53 sandcrawler (~3.1k tris), 54 vaporators x3 (930), 56 Harrower wreck (~1.5k),
  57 Foray-class wreck (~10.6k; rare, 13 on the map). flora_props.py EXTERNAL registers them in trees.gfx;
  its procedural sandcrawler/vaporators/Star Destroyer were deleted (homestead + giants stay procedural).
  Lessons: decimating 400-900k-tri models straight to 1.5k shreds them -> remesh first; Blender's
  separate-by-loose takes many minutes on 100k+ pieces -> numpy island labelling instead.
- Trains: gfx/train_gfx_database/generic.txt (replaces vanilla) = XJ-6 airspeeder (wagon_0) + X-34 landspeeders,
  shift y 0.9, entities in gfx/entities/hod_trains.{gfx,asset}, shader PdxMeshTrain. Nose at Blender -Y (PDX -Z
  forward), back at y = 0 like vanilla cars. NOT verified in game (orientation/height/scale).
- Wrecks are Old Republic era (Clone Wars setting): no Imperial Star Destroyer.

## Round 11 (2026-10-09): speeder paint jobs, burnt wrecks, B1 normals, gun turret AA, launch pads
- sketchfab_props.py: PAINT = 6 paint jobs per speeder (hue rotation of saturated pixels; metal untouched) as extra
  pdxmesh entries with meshsettings texture_diffuse on the same .mesh; each train equipment level has its own lead
  colour, cars pick from all 12. Wrecks: burnt() (soot darkening, scorch blotches) applied in `textures`.
- B1 droids dark: CIS_infantry_normal.dds had G/A centred at 72/60 instead of 128 (PdxMeshAdvanced/Standard read
  normal x/y from G/A, see UnpackRRxGNormal) -> every pixel tilted away from the light. Re-centred to 128 keeping
  detail; original in WIPGFX/Assets/model_backup/.
- military_buildings.py: `textures` + `launchpad` (procedural, 552 tris: 3 pads on pillars with landing markings +
  rim lights, control tower, walkway) + `wire`: gfx/entities/buildings.asset = vanilla copy with building_air_base ->
  hod_launchpad_mesh and building_anti_air_building -> hod_gunturret_mesh (gfx/models/buildings/gunturret.mesh, from
  Ireheart/hoi4-models, static: no animations, 'barrel' locator for the attack particle, scale 1.6).
- Terrain atlas: NOT changed. The current atlas is km-scale aerial imagery (right for HOI4); Poly Haven ground
  textures are m-scale close-ups and would read as noise. Proposed public-domain satellite imagery instead (pending).
- NOT verified in game: all of round 11.

## Round 12 (2026-10-09): terrain atlas -> Poly Haven (user choice)
- terrain_atlas.py polyhaven: 14 of 16 slots replaced with Poly Haven CC0 ground photos (1k diffuse/nor_gl/rough,
  cached in WIPGFX/3d/polyhaven_terrain), brightness-matched to the old tile; slots 6 (water) and 14 (lava) kept.
  Diffuse A = gloss from roughness, normal A = spec 40.
- Backups kept as the user asked: `restore` -> pre-existing atlas (WIPGFX/Assets/atlas_backup/), `satellite` ->
  Sentinel-2 cloudless 2016 (CC BY 4.0, credit EOX) with per-slot locations in SATELLITE. Comparison sheets:
  WIPGFX/terrain_compare.png, WIPGFX/terrain_compare_satellite.png (good satellite picks noted in chat: farmland
  Beauce, grass Pampas, forest Black Forest, jungle Amazon foothills, swamp Okavango delta, dunes Namib, red rock
  Utah, mountains Alps, ice Malaspina, city Cairo/Mexico City).
- NOT verified in game.

## Round 13 (2026-10-09): Revolution_Realized terrain, mipmaps, new Sketchfab buildings
- User: Poly Haven terrain too pixelated -> terrain_atlas.py `revolution`: Revolution_Realized's 5x5 aerial atlas
  (friend's mod, permission given) + our water (slot 6) and lava (slot 14); their slot 20 is a joke photo (unused)
  -> copy of 18. Needs gfx/FX/constants.fxh = vanilla + TERRAIN_TILE_FREQ 228, MAP_NUM_TILES 5, TEXELS_PER_TILE 312
  (written by the script; `polyhaven`/`satellite`/`restore` delete it again). sample_terrain uses the whole cell;
  TEXELS_PER_TILE only affects mip choice. planet_terrain_gen preview reads 4x4 or 5x5.
- "Pixelated / uncanny" droids: every unit texture had NO mipmaps (1 level) -> heavy aliasing when small.
  Regenerated with full DXT5 mip chains: 32 unit textures (B1, droideka, clones, wookiees) + AAT, AT-AT, DC-15,
  E-5. Originals in WIPGFX/Assets/model_backup/.
- Gun turret AA removed (user): anti-air is vanilla again.
- New Sketchfab models (CC BY, CREDITS.md) in WIPGFX/3d/sketchfab/Nouveau dossier, baked by sketchfab_props.py
  (new kind `building`: PdxMeshSnow, Advanced layout, windows() -> night emission, out gfx/models/buildings/hod_sw):
  jasperio (treehouse village), jedi_temple, shield_gen (file = row of 6 copies -> crop_x keeps one; untextured ->
  AO bake x grey), chr_00..07 (Christophsis towers cut out of the battleground level by christophsis_extract.py;
  sites 00-04, 07 picked from its contact sheet; 00/02/03 are single-sided panels -> `double`).
- Cities: coruscant_buildings.py clusters(kind) cor|chr; CITY_GROUPS 1 megacity (cor + 1/3 chr clusters),
  2 towns, 3 Christophsis, 4 treehouse villages (jasperio, density 0.15). planet_terrain_gen.py paints cities.bmp
  per planet: Christophsis -> 3, TREE_VILLAGE_WORLDS or forest/jungle-dominant worlds -> 4, city zones -> 1, else 2.
- Factories (industrial complex + arms factory) -> shield generator mesh (no chimney smoke). Jedi Temple on Coruscant:
  military_buildings.py `landmarks` places hod_jedi_temple at the Jedi Sector's centre in map/ambient_object.txt.
- NOT verified in game.
- CRASH (user, 2026-10-09 20:37): constants.fxh had a `//` note before `Code [[` -> the file is parsed as script
  ("Unexpected token" on every line), every constant undeclared (FOW_CAMERA_MIN, WATER_HEIGHT), shaders fail
  (pdxmesh, tree, restorescene, maparrow...) -> crash. Fixed: note moved inside the Code block (terrain_atlas.py too).
  Lesson: .fxh/.shader files take nothing outside their blocks except `#` comments.
- Factories: shield generator rejected by the user ("pretty bad"). military_buildings.py FACTORIES:
  industrial complex -> hod_bld_chr_07 (striped Christophsis block, scale 1.1), arms factory -> hod_bld_chr_04
  (octagonal towers, scale 1.0); factory smoke removed. shield_gen spec/mesh kept in sketchfab_props.py but unused.
- UI: user called the KOTOR interface "terrible" -> all 1246 textures in kotor_ui_written.txt deleted (all
  untracked, i.e. ours; vanilla UI is back). gfx/interface == git again. The mod's own 88 UI textures untouched.
- Jedi Temple "floating": y = heightmap/10 = 10.1, same rule as buildings.txt (factories there sit at 10.0-10.1) and
  vanilla. Cause not found yet; waiting for an in-game capture of it (PrintWindow capture of hoi4 works while occluded).

## Round 14 (2026-10-09): clean planet maps + round animated globes when zoomed out
- planet_clean.py: deshade() output -> clouds (bright, desaturated vs the planet median) and painted night side
  (much darker) filled from the surroundings. planet_terrain_gen.py: colormap RGB = these clean flat maps,
  colormap A = distance from the planet centre (0 centre .. 1 rim, 1 in space; R = 99th percentile of the body).
- make_pdxmap_shader.py: zoomed out, diffuse = vGlobe: sphere normal from r and its gradient (2 extra colormap taps
  each axis), lit by PLANET_SUN_DIR (+ PLANET_AMBIENT), two layers of ATNoise clouds drifting with
  vFoWOpacity_FoWTime_SnowMudFade_MaxGameSpeed.y (PLANET_CLOUD_AMOUNT/SCALE/SPEED), rim haze PLANET_RIM_COLOR.
  No dynamic branch (texture taps inside it would need gradients). City lights now = share of the 4 terrain-tile
  corners that are CITY_TILE_SLOT 10 (alpha no longer holds the light mask). Numpy simulation looked right.
- NOT verified in game (watch error.log for pdxmap.shader compile errors first).
- User feedback: clouds all look the same -> removed. Globes too dark -> PLANET_AMBIENT 0.12 -> 0.5,
  PLANET_PAINT_GAIN 1.0 -> 1.15. Sphere shading kept (user: "works").
- User: white outline (rim haze) disliked -> removed. Clouds wanted back but varied / moving around the planet:
  clouds now sampled in latitude/longitude on the rebuilt sphere normal, longitude + time * PLANET_CLOUD_SPEED
  (0.5-1.5x per planet) -> they rotate across the face and over the limb; per-planet seed from the planet centre
  (prepos - rim dir * r * radius, radius = 4/|grad r|) varies cover (0.22-0.50), band stretch and speed. Numpy
  twin of the shader (same hash noise) checked at two times.
- Galaxy centre dimmer: pdxwater.shader Deep Core 1.6 -> 1.15, Core glow 0.45 -> 0.35 (swgalaxy_sim.py too).
- User: clouds out for good; globes "not 3D". Now: the flat map is wrapped onto the sphere (sampled at
  asin(r)/(pi/2) of the radius along the rim direction -> features squeeze to the limb), light =
  lerp(PLANET_AMBIENT 0.28, PLANET_DAY 1.3, lambert^0.8) x limb darkening (PLANET_LIMB 0.3) + sun glint
  (PLANET_SPECULAR 0.18). Cloud code deleted. Numpy sim reads as lit 3D spheres.

## Space sectors, nebulae, rings (2026-10-25)
- User: space strategic regions redrawn as the canon sector map. `WIPGFX/plans & scripts/space_sectors.py`
  (plan/write): planet sector from the cached infobox (research/<planet>/facts.json, SECTOR_FIX for gaps), each
  sea province to the nearest planet's sector, split pieces merged into the neighbour they touch most, squeezed-out
  sectors keep their nearest province. 60 old space regions -> 111 sector regions (ids 1..288, contiguous; old ids
  reused). Land regions untouched (Haruun Kal / Wild Space lost their stray sea province). Preview
  WIPGFX/Assets/space_sectors_preview.png. 23 planets have no canon sector found: their space joins neighbours.
- pdxwater.shader: NebulaColor (domain-warped fbm drifting with time, zoomed-out only): Ghost Nebula (Umbara), the
  Maw (Kessel), Rishi Maze, Unknown Regions + faint wisps everywhere. PlanetRing: tilted banded ring with a gap on
  Yavin IV, Endor, Iego, Nal Hutta, Saleucami (drawn in the space pass, so it shows behind the globe on both sides).
  Numpy twin previews: WIPGFX/Assets/space_fx_preview.png, space_ring_preview.png.
- NOT verified in game: watch error.log for pdxwater.shader compile errors and the strategic region load.
- User: space provinces redrawn smooth and fitted to the galaxy chart. galaxy_regions.py chart now also saves the
  region raster (WIPGFX/Assets/galaxy_region_labels.npy; the run here stopped at the Windows label font, after the
  raster; chart alpha unchanged). `space_provinces.py` (preview/write): shore band (6 px) keeps old provinces, orbit
  zone (45 px, clipped to the planet's chart region) goes to the nearest shore province, deep space = Lloyd-relaxed
  Voronoi cells per chart region (the 151 open provinces shared out by area). Same 365 ids/colours; every coastal
  land province still coastal; 142 land-sea pairs moved to a neighbour -> 147 naval_base_spawn re-pointed; sea
  unitstacks rebuilt (vanilla layout, 0/21 at the inner point, 1-8 / 11-18 toward neighbours). Lanes whose Through
  province doesn't touch both ends: 128 of 249 (was 116; the game accepted those). space_sectors.py rerun, sectors
  now stay inside their chart region. NOT verified in game: check error.log for province/unitstack warnings.
- User approved the 6 extras. pdxwater.shader: AsteroidBelt (Hoth, Kessel, Geonosis), LaneGlow (Perlemian Trade Route,
  Hydian Way, Corellian Run, Rimma Trade Route through the canon stops on this map, pulses running along them,
  zoomed out), StarPulse (Mustafar's star, 6 s beat), 3 Comets on slow orbits round the galactic core. The per-planet
  calls (rings too) are written by `space_fx.py` between the "space_fx near/far" markers from galaxy_planets.json.
  Sector names baked faintly into the chart: `space_sectors.py labels` (additive, clear of planets and region names;
  base copy WIPGFX/Assets/galaxy_chart_alpha_base.npy, deleted by galaxy_regions.py chart). Sluis Van Shipyards:
  new ak.slv_yards + sluis_van_map orbit hook (needs Blender build + `military_buildings.py place Sluis Van` on the
  user's machine). Malachor is not on the map, so no green glow. Previews space_fx_preview.png, space_belt_preview.png,
  galaxy_chart_sectors_preview.png. NOT verified in game.
- User review: only the moving nebulae are good. Reverted everything else from 2026-10-25 to the state before it:
  space provinces (provinces.bmp), space strategic regions + names, weather points, unitstacks, naval base spawns,
  chart (ice_diffuse.dds), rings/belts/lanes/comets/star glow, sector labels, Sluis Van yards and the three new
  scripts. Kept: NebulaColor in pdxwater.shader, and the review_notes correction (most shipyards were already in orbit).
- Space territory TEST (user asked): pdxwater.shader SpaceTerritory, visual only. Owner colour from the gradient
  border texture (as the globes read it) at 3 rings x 12 taps round each space pixel, fill out to 80 map px, an
  outline where the fill ends and a light line where two owners' space meets; faded in from camera 250-700.
  Numpy twin with the bookmark owners: WIPGFX/Assets/space_territory_preview.png (country-country lines come out
  lacy). Unknown until tested: what the texture holds over space and in other map modes. To remove: delete the
  SpaceTerritory function and the 6 lines after the stars in main.
- Space territory test removed (user: only shows in some map modes, and ugly: pale washed-out halos with lacy
  edges in game). pdxwater.shader back to nebulae only.
