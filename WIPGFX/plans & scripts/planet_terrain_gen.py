"""Generate every planet's terrain from scratch: a canonical biome mix per world (PLANETS, researched on
Wookieepedia) split into zones, a heightmap built per zone archetype, and a climate model (temperature by altitude + latitude, moisture by noise + water) that picks
the terrain texture per pixel. The old hand-painted terrain.bmp is not used.

Outputs (all derived, safe to re-run any time):
  map/terrain.bmp        biome paint (vanilla 16-texture atlas, indices from common/terrain/00_terrain.txt)
  map/heightmap.bmp      per-archetype relief; coastlines stay exactly on the province outlines
  map/world_normal.bmp   normals from the new heightmap
  map/trees.bmp          trees from the painted biomes
  map/terrain/colormap_rgb_cityemissivemask_a.dds   painted planet globes (shader: hue up close, globe zoomed out) + city lights
  map/terrain/colormap_water_{0,1,2}.dds            per-planet atmosphere glow on black (galaxy is in the water shader)
  map/terrain/mud_diffuse_rgb_gloss_a_{0,1,2}.dds   sharp zoomed-out globe texture (4096 square): the painted planet
                                                     colours with the real terrain tiles' detail baked in. The game
                                                     only accepts a half-res colormap, so pdxmap.shader reads the
                                                     globe from the mud slot (mud is switched off)
  map/buildings.txt, map/unitstacks.txt              y column re-snapped to the heightmap (height = pixel / 10)

Inputs: map/provinces.bmp + definition.csv (shapes, gameplay terrain), history/states (planet names),
WIPGFX/Assets/map_base/ (original colormaps: painted planet hue hints + DDS headers, original terrain.bmp palette).

Usage (from the mod root):
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --preview OUTDIR
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --write
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --reheight   only re-snap buildings/unitstacks to heightmap.bmp
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --city-styles   only reapply the per-world city styles (cities.bmp)
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --round-coasts  only make planet coastlines round (heightmap.bmp)
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --globe-texture  only rebake the globe texture (after any
                                                         colormap / terrain.bmp / atlas change)
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --felucia      only repaint Felucia (giant flora, alien ground, amber
                                                         haze); run after --write / --world-tweaks, then --globe-texture
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --kadavo       only repaint Kadavo; run after kadavo_map.py,
                                                         then --globe-texture
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --florrum      only repaint Florrum (and its colours); run after
                                                         florrum_map.py, then --globe-texture
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --korriban     only repaint Korriban (valleys, tombs, spires); run
                                                         after korriban_map.py, then --globe-texture
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --raxus-prime  only repaint Raxus Prime (junk world); run after
                                                         raxus_prime_map.py, then --globe-texture
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --planet NAME  only repaint a planet whose map script has a
                                                         TERRAIN_CFG (Zygerria; --zygerria is the same), then --globe-texture
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --raxus        only repaint Raxus (capital, countryside); run after
                                                         raxus_map.py, then --globe-texture
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --world-tweaks  only apply city districts, red worlds, dense
                                                         forests (terrain/cities/trees.bmp + colormap); run once
"""
import argparse, collections, csv, glob, io, json, os, re, shutil, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

MAP = "map"
BASE = "WIPGFX/Assets/map_base"
SEED = 1977
NORMAL_K = 0.09          # world_normal slope scale (vanilla fits ~0.05 per half-res px)
SHORE = 97               # height right at the coast (water plane is ~95.7)
GROUND = 97              # base lowland height (~1 above the water plane); relief only rises from here
TREE_SCALE = 5632 / 1650  # vanilla map px per trees.bmp px
CLASSES = ["plains", "forest", "jungle", "marsh", "desert", "hills", "mountain", "urban"]

# terrain.bmp palette indices (common/terrain/00_terrain.txt) by look
GRASS, FARM, SNOWFARM, GRASSHILL, HILLS = 0, 5, 19, 17, 2
DFOREST, FOREST, JUNGLE, JUNGLE2 = 1, 4, 21, 22
WATER, SAVANNA, DUNES, SNOWSAND, URBAN = 9, 12, 3, 14, 13
ROCK, ROCK2, SNOWROCK, GREENMTN, SAND, BROWN, LAVA, BROWNMTN = 6, 11, 16, 20, 7, 10, 8, 31
PERM_SNOW = {SNOWSAND, SNOWROCK, SNOWFARM}

# archetype: temperature range, moisture range (0..1), share of the world under water, relief amplitude,
#            mountain share added on top of gameplay mountains, atmosphere (rgb, thickness)
ARCH = {
    "temperate":  dict(T=(0.35, 0.70), M=(0.35, 0.80), sea=0.12, relief=28, ranges=0.10, atmo=((0.45, 0.70, 1.00), 1.0)),
    "forest":     dict(T=(0.35, 0.62), M=(0.65, 1.00), sea=0.07, relief=22, ranges=0.08, atmo=((0.45, 0.72, 0.95), 1.0)),
    "jungle":     dict(T=(0.75, 1.00), M=(0.65, 1.00), sea=0.10, relief=24, ranges=0.06, atmo=((0.50, 0.80, 0.55), 1.15)),
    "swamp":      dict(T=(0.60, 0.88), M=(0.85, 1.00), sea=0.30, relief=8,  ranges=0.02, atmo=((0.50, 0.70, 0.45), 1.25)),
    "desert":     dict(T=(0.82, 1.00), M=(0.00, 0.12), sea=0.00, relief=18, ranges=0.08, atmo=((1.00, 0.80, 0.50), 0.55)),
    "reddesert":  dict(T=(0.80, 1.00), M=(0.00, 0.18), sea=0.00, relief=30, ranges=0.12, atmo=((1.00, 0.55, 0.35), 0.6)),
    "steppe":     dict(T=(0.55, 0.85), M=(0.15, 0.45), sea=0.03, relief=16, ranges=0.06, atmo=((0.75, 0.80, 0.85), 0.8)),
    "ice":        dict(T=(0.00, 0.16), M=(0.20, 0.70), sea=0.06, relief=26, ranges=0.10, atmo=((0.80, 0.95, 1.00), 0.8)),
    "lava":       dict(T=(1.00, 1.00), M=(0.00, 0.10), sea=0.00, relief=34, ranges=0.10, atmo=((1.00, 0.38, 0.10), 1.35)),
    "ocean":      dict(T=(0.50, 0.85), M=(0.60, 0.95), sea=0.68, relief=20, ranges=0.04, atmo=((0.30, 0.55, 1.00), 1.25)),
    "city":       dict(T=(0.50, 0.70), M=(0.30, 0.50), sea=0.00, relief=6,  ranges=0.03, atmo=((1.00, 0.72, 0.32), 1.0)),
    "industrial": dict(T=(0.60, 0.80), M=(0.10, 0.30), sea=0.04, relief=14, ranges=0.05, atmo=((0.75, 0.62, 0.45), 1.1)),
    "barren":     dict(T=(0.40, 0.70), M=(0.00, 0.10), sea=0.00, relief=24, ranges=0.10, atmo=((0.60, 0.62, 0.70), 0.12)),
    "alpine":     dict(T=(0.25, 0.60), M=(0.40, 0.80), sea=0.03, relief=40, ranges=0.35, atmo=((0.50, 0.72, 1.00), 1.0)),
    "grassland":  dict(T=(0.45, 0.68), M=(0.30, 0.55), sea=0.05, relief=12, ranges=0.03, atmo=((0.50, 0.75, 1.00), 1.0)),
    "sinkhole":   dict(T=(0.65, 0.90), M=(0.15, 0.40), sea=0.00, relief=16, ranges=0.05, atmo=((0.85, 0.80, 0.65), 0.8)),
}

# Biome mix per world, from the Wookieepedia climate/terrain infoboxes (canon; Legends where canon is empty).
# Raw notes cached in WIPGFX/Assets/planet_wiki.json. Key = planet part of the body's majority state name.
# Format: "[@mode] arch share arch share ...". Zones are laid out by noise (default), @lat (first entry at the
# equator, last at the poles), @x (west -> east, e.g. tidally locked Ryloth) or @y (north -> south).
# Unlisted worlds fall back to the hue of their painted planet (see fallback_archetype).
PLANETS = {
    "Abregado-Rae": "temperate .5 city .3 grassland .2",              # Core trade world
    "Aeten II": "reddesert .5 lava .5",                               # lava rivers, red deserts, volcanic
    "Agamar": "@lat steppe .5 barren .3 ice .2",                      # cold, rocky
    "Alderaan 9": "grassland .35 alpine .35 forest .15 ocean .15",    # forests, plains, grasslands, small seas, mountains
    "Allanteen VI": "temperate .5 industrial .5",                     # Imperial shipyard world
    "Alzoc III": "ice 1",                                             # frozen wastelands, mountains
    "Anoat": "industrial .6 barren .4",                               # toxic, urban
    "Arkania": "ice .8 city .2",                                      # cold, icy tundra, caverns (Adascopolis)
    "Atzerri": "city .5 swamp .5",                                    # urban, marshes
    "Axxila": "alpine .5 temperate .5",                               # cliffs
    "Bakura": "temperate .4 forest .3 alpine .2 ocean .1",            # forests, plains, mountains, small seas, rivers
    "Bastion": "temperate .6 grassland .4",                           # temperate hills
    "Batuu": "forest .6 alpine .4",                                   # forests, mountains, cenotes
    "Belsavis": "ice .75 jungle .25",                                 # glaciers + tropical rift valleys
    "Bestine IV": "ocean .85 barren .15",                             # sparse rocky islands, shallow seas
    "Bonadan": "reddesert .6 industrial .4",                          # eroded wastes, industrial centres
    "Botajef": "city 1",                                              # ecumenopolis
    "Bothawui": "grassland .35 alpine .25 forest .2 city .2",         # plains, mountains, forests, urban
    "Boz Pity": "reddesert .5 desert .3 alpine .2",                   # canyons, deserts, mountains, plains
    "Bracca": "industrial .7 steppe .3",                              # ship-breaking junkyards, plains
    "Byss Deep Oceans": "temperate .35 city .35 ocean .3",            # Byss: verdant throne world, citadel, seas
    "Cantonica": "desert .65 reddesert .25 city .1",                  # desert, mountains, Canto Bight
    "Carida 2": "@lat jungle .2 desert .2 temperate .25 forest .15 ice .2",  # every climate band, heavy gravity
    "Cato Neimoidia": "alpine .35 forest .3 grassland .2 ocean .15",  # mountains, forests, rock arches, acid seas
    "Celanon": "city .5 temperate .3 forest .2",                      # forests, plains, urban sprawl
    "Celegia": "ocean 1",                                             # raging seas, cyanogen air
    "Cerea": "grassland .5 forest .35 temperate .15",                 # farmland, forests, rolling hills
    "Chandrila": "grassland .5 temperate .3 ocean .2",                # rolling hills, Silver Sea
    "Christophsis": "barren .5 ice .3 city .2",                       # crystalline formations
    "Cioral": "city .7 temperate .3",                                 # urban
    "Ciutric": "temperate .6 city .4",                                # Ciutric Hegemony capital (no data)
    "Colla IV": "jungle .6 temperate .2 industrial .2",               # tropics, Colicoid droid works
    "Commenor": "city .3 alpine .2 ocean .2 desert .15 reddesert .15",  # cities, mountains, oceans, deserts, canyons
    "Copero": "alpine .5 ice .3 industrial .2",                       # mountains, Chiss shipyards
    "Corellia": "temperate .35 city .25 forest .15 ocean .15 jungle .1",  # forests, jungles, oceans, industrial urban
    "Corsin": "temperate .5 jungle .25 ocean .25",                    # warm, tropical regions, aquatic life
    "Corulag": "city .5 grassland .2 forest .15 ocean .15",           # urban, oceans, plains, bamboo forests
    "Csaus": "ice .5 steppe .5",                                      # Chiss world (no data)
    "Csilla": "ice 1",                                                # ice-locked
    "Dantooine": "grassland .55 temperate .15 forest .2 alpine .1",   # grasslands, forests, hills, great lakes
    "Dathomir": "swamp .4 forest .3 reddesert .3",                    # rocky, swampy, forested, red
    "Despayre": "jungle .75 ocean .25",                               # tropical jungles, rivers, seas
    "Dorin": "alpine .5 barren .5",                                   # mountains, valleys, plateaus
    "Dromund Kaas": "swamp .5 jungle .35 ocean .15",                  # stormy swamp, jungle, oceans
    "Dubrillion": "ocean .6 temperate .4",                            # oceans
    "Duro": "industrial .5 barren .3 jungle .2",                      # polluted wasteland, orbital cities
    "DynaCorp Territory": "city .5 ocean .25 temperate .25",          # Esseles: urban, ocean
    "Endor": "forest .55 alpine .2 steppe .15 desert .1",             # forests, mountains, savannas, deserts, lakes
    "Eriadu": "industrial .35 jungle .35 alpine .3",                  # jungles, mountains, polluted industry
    "Etti IV": "forest .7 temperate .3",                              # forests
    "Falleen": "temperate .4 alpine .35 ocean .25",                   # mountain valleys, seas
    "Farstine": "barren .5 steppe .5",                                # methane atmosphere
    "Felucia": "jungle .6 swamp .4",                                  # hot, humid fungal jungles and swamps
    "Florrum": "desert .6 reddesert .4",                              # hot, dry, sulfurous geysers
    "Foerost": "industrial .5 city .5",                               # Core shipyard world
    "Fondor": "city .5 desert .3 barren .2",                          # desert wasteland, urban sprawl
    "Fresia": "ocean .8 jungle .2",                                   # archipelagos, islands
    "Garqi": "grassland .45 jungle .3 ocean .25",                     # plains, rain forests, oceans
    "Gehenbar Hive": "reddesert .8 barren .2",                        # Geonosis: hot arid deserts, mesas, mountains
    "Ghorman": "grassland .4 alpine .3 forest .3",                    # mountains, valleys, plains, forests
    "Grand Arena": "city 1",                                          # Coruscant
    "Haruun Kal": "jungle .45 alpine .3 swamp .15 lava .1",           # plateaus over a toxic cloudsea, volcanoes
    "Honoghr": "reddesert .7 jungle .3",                              # poisoned desert plains, rainforest remnants
    "Hoth": "ice 1",                                                  # ice plains, glaciers, mountains
    "Hypori Eastern Mountains": "desert .4 barren .3 alpine .2 ocean .1",  # Hypori: rocky, small oceans
    "Iego": "reddesert .6 barren .25 temperate .15",                  # basalt spires, canyons, deserts
    "Ilum": "ice 1",                                                  # crystallized glaciers, ice plains
    "Ithor": "jungle .8 forest .2",                                   # rainforests (the Mother Jungle)
    "Jabiim": "swamp .6 grassland .25 barren .15",                    # endless rain, muddy plains
    "Jedha": "desert .5 reddesert .3 barren .2",                      # cold deserts, mesas, dustbowls
    "Kadavo": "barren .5 ice .3 lava .2",                             # cold, volcanic
    "Kalee": "@lat jungle .5 reddesert .2 ocean .15 ice .15",         # rainforests, canyons, seas; arctic to tropical
    "Kamino Oceans": "ocean 1",                                       # aquatic
    "Karfeddion": "steppe .6 temperate .4",                           # (no data)
    "Kashyyyk": "forest .55 jungle .2 ocean .15 swamp .1",            # wroshyr forests, jungles, oceans, swamps
    "Kato Zakar": "alpine .4 forest .3 grassland .3",                 # Tython: mountains, forests, plains
    "Kessel": "@y barren .6 jungle .4",                               # spice mines in the north, lush south
    "Korriban": "reddesert .7 barren .3",                             # hot, desolate mountains
    "Kuat": "grassland .4 forest .3 city .3",                         # plains, forests, KDY
    "Lianna": "steppe .5 city .3 temperate .2",                       # temperate and dry, urban, plains
    "Lola Sayu": "lava .5 barren .5",                                 # volcanic, caves, mountains
    "Loronar": "industrial .6 temperate .4",                          # corporate industry world
    "Malastare": "steppe .5 forest .25 barren .25",                   # forests, rocky, podracing plains
    "Manaan": "ocean 1",                                              # planet-wide ocean
    "Mandalore": "desert .55 barren .25 city .1 forest .1",           # glassed deserts, domed cities, old forests
    "Manpha": "swamp .8 jungle .2",                                   # humid swamps
    "Mechis": "industrial .8 barren .2",                              # droid foundry planetoid
    "Mimban": "swamp .7 jungle .3",                                   # mud fields, rainforests, swamps
    "Mon Calamari": "ocean 1",                                        # oceans
    "Muunilist": "temperate .4 alpine .25 forest .2 city .15",        # plains, forests, hills, mountains, cities
    "Mustafar": "lava .75 barren .25",                                # lava seas, obsidian ranges
    "Mygeeto": "ice .85 city .15",                                    # frigid, crystalline, crystal cities
    "Naboo": "grassland .4 swamp .25 alpine .2 temperate .15",        # swamps, hills, plains, cities, mountains
    "Nal Hutta": "swamp .85 jungle .15",                              # hot, humid swamps
    "Nar Shaddaa": "city .8 industrial .2",                           # decaying ecumenopolis
    "Neimodia": "swamp .4 jungle .3 desert .3",                       # humid; desert, fields, rainforest
    "Nimban": "grassland .5 swamp .5",                                # plains (Hutt world)
    "Nyriaan": "jungle .6 temperate .4",                              # tropical
    "Oba Diah": "barren .6 alpine .4",                                # jutting obsidian crags
    "Onderon": "jungle .75 alpine .15 city .1",                       # jungle, Iziz
    "Ord Cestus": "desert .5 reddesert .3 steppe .1 lava .1",         # arid mountains, volcanoes, deserts, plains
    "Ord Mantell": "alpine .3 steppe .3 reddesert .2 ocean .2",       # mountain chains, mesas, plains, islands
    "Ossus Wilderness": "forest .3 steppe .3 alpine .2 barren .2",    # Ossus: hills, gorges, forests, old ruins
    "Pammant": "barren .6 industrial .4",                             # tunneled shipbuilding world
    "Pantora": "ice .4 swamp .3 temperate .3",                        # cold moon, marshes
    "Phelarion": "temperate .6 grassland .4",                         # (no data)
    "Queyta": "temperate .4 lava .35 barren .25",                     # volcanoes
    "Quesh": "swamp .8 barren .2",                                    # toxic tropical swamps
    "Rakata Prime": "ocean .6 jungle .3 barren .1",                   # Lehon: tropical islands, rocky outcrops
    "Raxus": "temperate .5 forest .3 ocean .2",                       # forests, hills, oceans, plains
    "Raxus Prime": "industrial .8 barren .2",                         # junk world, toxic pools
    "Rendilli": "temperate .5 city .3 industrial .2",                 # Rendili: conservative Core world, StarDrive
    "Rhen Var": "ice 1",                                              # glaciers, snowy mountains
    "Ringo Vinda": "city .6 industrial .4",                           # graving-dock world
    "Rishi Human Colonies": "jungle .4 swamp .25 ocean .2 alpine .15",  # Rishi: tropical mountains, swamps, islands
    "Rodia": "jungle .5 swamp .3 ocean .2",                           # jungles, swamps, oceans
    "Rothana": "ice .7 industrial .3",                                # arctic, icy cliffs, Rothana Heavy Engineering
    "Ruuria": "jungle .8 swamp .2",                                   # warm, humid jungles, pink rivers
    "Ryloth": "@x reddesert .4 jungle .2 steppe .2 ice .2",           # tidally locked: Bright Lands .. Dark Lands
    "Saleucami": "desert .45 reddesert .2 swamp .2 lava .15",         # arid; deserts, swamps, volcanoes
    "Serenno": "forest .45 steppe .3 alpine .25",                     # forests, mountains, plains, savannah
    "Shola": "lava .6 barren .4",                                     # magma rivers, desolate flats
    "Sirpar Hills": "forest .3 jungle .2 reddesert .2 ocean .15 city .15",  # Anaxes: canyons, forests, jungles, seas
    "Sluis Van": "industrial .5 barren .5",                           # rocky, industrial shipyards
    "Sullust": "lava .6 barren .4",                                   # volcanic, molten surface
    "TUOEE Zone": "industrial .4 steppe .3 alpine .3",                # Balmorra: canyons, industry, plains, mountains
    "Takodana": "forest .5 grassland .25 ocean .25",                  # lakes, plains, temperate forest
    "Taris": "city .8 ocean .2",                                      # urban sprawl, oceans
    "Tatooine": "desert .7 reddesert .3",                             # Dune Sea, canyons, rocky bluffs
    "Telos": "@lat steppe .45 barren .3 ice .25",                     # restored plains, bombed wastes, polar ice
    "Terminus": "city .6 barren .4",                                  # urban
    "Teth": "jungle .6 reddesert .25 forest .15",                     # jungle lowlands, tall mesas
    "Tetan Depths": "city .75 industrial .25",                     # Empress Teta: Coruscant-like megacity, carbonite works
    "Thyferria": "jungle .6 forest .2 alpine .2",                     # Thyferra: tropical jungles, grassy canyons
    "Tibrin": "ocean .85 jungle .15",                                 # coral reefs, sand bars
    "Toydaria": "swamp .5 forest .3 alpine .2",                       # forests, mountains, swamps
    "Trandosha": "jungle .4 forest .35 grassland .25",                # forests, jungles, plains
    "UTISTATE": "sinkhole .7 steppe .3",                              # Utapau: grassy plains, giant sinkholes
    "Umbara": "jungle .5 swamp .25 city .25",                         # dark, overgrown plains, jungle, urban
    "Utapau": "sinkhole .7 steppe .3",
    "Vohai": "temperate .5 industrial .3 forest .2",                  # industrial gardens
    "Wayland": "forest .6 alpine .4",                                 # forests, mountains
    "Yag'Dhul": "@lat temperate .4 barren .3 ice .3",                 # habitable band, frozen poles, vacuum storms
    "Yaga Minor": "alpine .5 forest .5",                              # caves, forests, mountains
    "Yavin IV": "jungle .85 ocean .15",                               # jungles
    "Yinchorr": "desert .6 barren .3 ocean .1",                       # rocky deserts, small seas
    "Zygerria": "steppe .5 reddesert .3 alpine .2",                   # plains, mesas, highlands
}


# trees.bmp objects from flora_props.py: 40 wroshyr giant, 41 jungle giant, 42/43 quiver trees, 44 shrub-tree,
# 45 succulent, 46 fern, 47 fallen trunk, 48/49 bare rock, 50 desert boulder, 51 mossy rock, 52 boulder,
# 53 Jawa sandcrawler, 54 moisture vaporators, 55 desert homestead, 56 crashed Sith Harrower, 57 crashed Foray-class
# blockade runner (53/54/56/57: Sketchfab CC BY, sketchfab_props.py). Share of tree cells turned into giants on these
# worlds (others: 20% / 25%).
TREE_VILLAGE_WORLDS = {"Kashyyyk", "Endor", "Trandosha", "Wayland", "Takodana", "Yavin IV", "Ithor", "Felucia",
                       "Batuu", "Rodia"}   # + every world whose dominant biome is forest or jungle
TREELESS = {"desert", "reddesert", "sinkhole", "barren", "lava"}
GIANT_WORLDS = {"Kashyyyk": 0.85, "Endor": 0.5, "Yavin IV": 0.5, "Wayland": 0.4, "Takodana": 0.35, "Ithor": 0.5,
                "Felucia": 0.4, "Rodia": 0.3, "Batuu": 0.4}
# zone archetypes -> [(trees.bmp index, chance per empty cell)]
PROPS = {
    "desert reddesert sinkhole": [(53, 0.008), (54, 0.025), (55, 0.008), (56, 0.0006), (57, 0.0006), (50, 0.03),
                                  (48, 0.012), (45, 0.006)],
    "steppe grassland": [(44, 0.03), (43, 0.008), (52, 0.012)],
    "barren lava ice industrial": [(48, 0.03), (49, 0.03), (56, 0.0003), (57, 0.0003)],
    "alpine": [(51, 0.03), (52, 0.03)],
    "swamp": [(46, 0.06), (47, 0.03)],
    "jungle": [(46, 0.05), (47, 0.01)],
    "forest temperate": [(51, 0.015), (47, 0.006)],
}


def load(path):
    """Open via a memory buffer: PIL mmaps BMPs, which blocks overwriting them later on Windows."""
    with open(path, "rb") as f:
        return Image.open(io.BytesIO(f.read()))


def save_bgra_dds(template_path, rgba, out_path):
    """Write an uncompressed single-level A8R8G8B8 DDS reusing the template's 128-byte header."""
    with open(template_path, "rb") as f:
        hdr = f.read(128)
    with open(out_path, "wb") as f:
        f.write(hdr + np.ascontiguousarray(rgba[..., [2, 1, 0, 3]]).astype(np.uint8).tobytes())


def noise(shape, cell, rng, octaves=4, gain=0.5):
    """fbm value noise in [0,1]."""
    h, w = shape
    out = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    for _ in range(octaves):
        g = rng.random((h // cell + 4, w // cell + 4)).astype(np.float32)
        z = ndi.zoom(g, cell, order=3, prefilter=False)
        oy, ox = rng.integers(0, cell, 2)
        out += amp * z[oy:oy + h, ox:ox + w]
        tot += amp
        amp *= gain
        cell = max(2, cell // 2)
    out /= tot
    lo, hi = np.percentile(out[::7, ::7], [1, 99])
    return np.clip((out - lo) / (hi - lo), 0, 1)


def paint_tint(rgb):
    """Close-up colormap tint from the painted globe, as gfx/FX/pdxmap.shader and tree.shader compute it: the
    planet's hue at 0.3 around neutral 0.5 (the shading baked into the painting is brightness, so it drops out)."""
    lum = rgb.mean(-1, keepdims=True)
    return 0.5 + (np.clip(0.5 + 0.3 * (rgb / np.maximum(lum, 0.05) - 1), 0, 1) - 0.5) * np.clip(lum * 10, 0, 1)


def rank(v):
    """Rank of each value scaled to 0..1."""
    r = np.empty(v.size, np.float32)
    r[np.argsort(v, kind="stable")] = np.linspace(0, 1, v.size)
    return r


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def load_provinces():
    rgb = np.array(load(f"{MAP}/provinces.bmp").convert("RGB")).astype(np.int32)
    key = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    lut_k, lut_land, lut_cls, lut_id = [], [], [], []
    with open(f"{MAP}/definition.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) < 7 or not row[0].isdigit():
                continue
            lut_k.append((int(row[1]) << 16) | (int(row[2]) << 8) | int(row[3]))
            lut_land.append(row[4] == "land")
            lut_cls.append(CLASSES.index(row[6]) if row[6] in CLASSES else 0)
            lut_id.append(int(row[0]))
    order = np.argsort(lut_k)
    k = np.array(lut_k)[order]
    pos = np.clip(np.searchsorted(k, key), 0, len(k) - 1)
    land = np.array(lut_land)[order][pos] & (k[pos] == key)
    cls = np.array(lut_cls, np.uint8)[order][pos]
    pid = np.array(lut_id)[order][pos]
    return land, cls, pid


def per_label(labels, n, values):
    """Mean of `values` per label (index 0 = sea)."""
    idx = labels.ravel()
    area = np.bincount(idx, minlength=n + 1).astype(np.float32) + 1
    return np.bincount(idx, values.ravel().astype(np.float32), n + 1) / area


def planet_names(labels, n, pid):
    """Majority state/planet name per land body, from history/states file names ('NNN-Planet - Region.txt')."""
    prov2name = {}
    for f in glob.glob("history/states/*.txt"):
        base = os.path.basename(f)[:-4]
        name = base.split("-", 1)[1].strip() if "-" in base else base
        txt = open(f, encoding="utf-8-sig", errors="ignore").read()
        m = re.search(r"provinces\s*=\s*\{([^}]*)\}", txt)
        if m:
            for x in m.group(1).split():
                prov2name[int(x)] = name
    ys, xs = np.nonzero(labels)
    sel = np.arange(0, len(ys), 5)
    votes = collections.defaultdict(collections.Counter)
    for y, x in zip(ys[sel], xs[sel]):
        votes[int(labels[y, x])][prov2name.get(int(pid[y, x]), "?")] += 1
    return {lab: (votes[lab].most_common(1)[0][0] if votes[lab] else "?") for lab in range(1, n + 1)}


def planet_mix(state_name):
    """(zone mode, [(archetype, share), ...]) for a body's majority state name, or None."""
    spec = PLANETS.get(state_name.split(" - ")[0].strip())
    if not spec:
        return None
    toks = spec.split()
    mode = toks.pop(0)[1:] if toks[0].startswith("@") else "noise"
    return mode, [(k, float(w)) for k, w in zip(toks[::2], toks[1::2])]


def fallback_archetype(rgb):
    """Archetype from a painted planet's mean colour."""
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    sat = (mx - mn) / max(mx, 1e-3)
    if mx > 0.7 and sat < 0.2:
        return "ice"
    if b > r and b > g and sat > 0.2:
        return "ocean"
    if g >= r and g >= b and sat > 0.15:
        return "temperate"
    if r > g * 1.3 and sat > 0.4:
        return "reddesert"
    if r >= g >= b and sat > 0.2:
        return "desert"
    return "barren"


def deshade(cm, land, labels, n):
    """Turn each painted sphere into flat ground: sample the painting radially compressed, divide out its lighting."""
    out = cm.copy()
    for lab, sl in enumerate(ndi.find_objects(labels), 1):
        if sl is None:
            continue
        m = labels[sl] == lab
        ys, xs = np.nonzero(m)
        if len(ys) < 40:
            continue
        cy, cx = ys.mean(), xs.mean()
        R = np.sqrt(len(ys) / np.pi)
        rho = np.clip(np.hypot(ys - cy, xs - cx) / R, 0, 1)
        src = 0.86 * np.sin(rho * np.pi / 2 * 0.8) / np.sin(np.pi / 2 * 0.8)
        k = np.where(rho > 1e-6, src / np.maximum(rho, 1e-6), 0.86 * (np.pi / 2 * 0.8) / np.sin(np.pi / 2 * 0.8))
        sy = sl[0].start + cy + (ys - cy) * k
        sx = sl[1].start + cx + (xs - cx) * k
        smp = np.stack([ndi.map_coordinates(cm[..., c], [sy, sx], order=1) for c in range(4)], -1)
        L = np.zeros(m.shape, np.float32); L[ys, xs] = smp[:, :3].mean(-1)
        sig = max(R / 3, 2)
        low = ndi.gaussian_filter(L, sig) / np.maximum(ndi.gaussian_filter(m.astype(np.float32), sig), 1e-3)
        gain = np.clip(np.percentile(L[m], 65) / np.maximum(low[ys, xs], 1e-3), 0.6, 3.0)
        smp[:, :3] = np.clip(smp[:, :3] * gain[:, None], 0, 1)
        block = out[sl]
        block[m] = smp
        out[sl] = block
    return out


def reheight(h):
    """Re-snap the y of every placed building / unit stack to the heightmap; the game doesn't, so they float or sink."""
    rows = h.shape[0]
    for fn in (f"{MAP}/buildings.txt", f"{MAP}/unitstacks.txt"):
        out = []
        for line in open(fn, encoding="utf-8-sig", newline=""):   # keep each line's own CRLF/LF
            body, end = line.rstrip("\r\n"), line[len(line.rstrip("\r\n")):]
            p = body.split(";")
            if len(p) >= 5 and p[2]:
                x, z = float(p[2]), float(p[4])
                r, c = min(max(rows - 1 - int(round(z)), 0), rows - 1), min(max(int(round(x)), 0), h.shape[1] - 1)
                p[3] = f"{h[r, c] / 10:.2f}"
            out.append(";".join(p) + end)
        with open(fn, "w", encoding="utf-8", newline="") as f:
            f.write("".join(out))
        print("re-snapped", fn)


# per-world city styles (map/cities.txt groups, coruscant_buildings.py wire)
WATER_CITY_WORLDS = {"Kamino Oceans", "Manaan", "Mon Calamari", "Celegia", "Bestine IV", "Fresia", "Tibrin"}
STYLE_WORLDS = {5: WATER_CITY_WORLDS, 6: {"Mandalore"}, 7: {"Gehenbar Hive"},     # Gehenbar Hive = Geonosis' land body
                8: {"Naboo"}}
# hand-picked world tweaks (applied on --write, or alone with --world-tweaks)
CITY_DISTRICTS = {8479: 8}                # province -> radius px of urban terrain + megacity buildings (Serenno;
                                          # Raxus has its own capital: --raxus)
RED_WORLDS = {"Korriban"}
RED_TERRAIN = {6: 24, 10: 24, 11: 24, 7: 31}   # grey rock / sand -> red rock (index 24 = atlas slot 17), red-brown sand
RED_TINT = (1.5, 0.72, 0.58)                   # colormap paint (globe zoomed out, hue up close) pulled toward this
DENSE_TREE_WORLDS = {"Kashyyyk": 0.7}          # chance to fill each empty land tree cell; half of them wroshyr giants


def world_tweaks(t, cmap, trees, cm, labels, names, pid, rng):
    """City districts round chosen provinces, red Korriban (terrain + colormap tint), denser forests on tree worlds.
    cm is the half-res colormap (0..1 RGBA). Re-running pulls the red tint a bit further."""
    t, cmap, trees, cm = t.copy(), cmap.copy(), trees.copy(), cm.copy()
    H, W = labels.shape
    planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
    yy, xx = np.mgrid[0:H, 0:W]
    for prov, rad in CITY_DISTRICTS.items():
        ys, xs = np.nonzero(pid == prov)
        zone = (np.hypot(yy - ys.mean(), xx - xs.mean()) <= rad) & (labels == labels[ys[0], xs[0]])
        t[zone], cmap[zone] = URBAN, 1
    cmap = carve_city_borders(cmap, pid)
    red = np.isin(planet, list(RED_WORLDS))
    for a, b in RED_TERRAIN.items():
        t[red & (t == a)] = b
    rh = red[::2, ::2][:cm.shape[0], :cm.shape[1]]
    lum = cm[..., :3].mean(-1, keepdims=True)
    cm[..., :3] = np.where(rh[..., None], cm[..., :3] * 0.35 + np.clip(lum * np.array(RED_TINT), 0, 1) * 0.65, cm[..., :3])
    TH, TW = trees.shape
    gi = np.ix_(np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1),
                np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1))
    tland = (labels[gi] > 0) & (t[gi] != URBAN)
    for world, fill in DENSE_TREE_WORLDS.items():
        sel = (planet[gi] == world) & tland & (trees == 0) & (rng.random((TH, TW)) < fill)
        pick = rng.random((TH, TW))
        trees[sel] = np.where(pick < 0.5, 40, np.where(pick < 0.75, 6, 29))[sel]
    return t, cmap, trees, cm


# Felucia: a fungal jungle "teeming with immense primitive plants" in "colour-saturated" hues under hazy canopies
# (Star Wars Databank); giant purple mushrooms form the upper canopy, enormous pitcher plants and leafy growths below,
# translucent life-forms colour the sunlight (Wookieepedia); bright plants against a dim, hazy sky (Revenge of the
# Sith). The ground goes to dark violet loam and teal moss, the jungle is replaced by Felucian giants
# (flora_props.py 58-61) and the sky glows amber.
FELUCIA = "Felucia"
FELUCIA_FLORA = [(58, 0.34), (59, 0.26), (60, 0.14), (61, 0.26)]   # giant mushroom, bulb stalks, pitcher, fronds
FELUCIA_FILL = 0.6                                                 # chance to give each free land tree cell a giant
FELUCIA_UNDERGROWTH = [(60, 0.3), (61, 0.7)]                      # lower pitchers / fronds in the cells left over
FELUCIA_UNDER_FILL = 0.5
FELUCIA_UNIT_CLEAR = 2      # map px around each province's standing unit position kept free of flora (provinces are ~8 px)
FELUCIA_TOWN_R = 5          # map px radius of the farm-village clearing around each state's victory point
FELUCIA_CITY_STYLE = 9      # map/cities.txt group: Felucian mushroom villages (coruscant_buildings.py)
OUTPOST_CITY_STYLE = 10     # ... and the Commerce Guild's prefab outposts on the lowlands
TOWN = 26                   # terrain.bmp farmland_town_26: farmland look that still spawns city models
FELUCIA_GROUND = [(0.0, (0.16, 0.07, 0.22)), (0.35, (0.36, 0.16, 0.42)), (0.6, (0.14, 0.46, 0.42)),
                  (0.85, (0.55, 0.66, 0.30)), (1.0, (0.85, 0.70, 0.40))]   # by brightness: violet loam -> teal moss -> ochre
FELUCIA_ATMO = (1.0, 0.72, 0.30)                                   # hazy amber


# Felucia's relief, by zone (felucia_map.py: 1 red lowland, 2 blue native jungle, 3 passage, 4 impassable jungle):
# the natives' jungles are great karst massifs, the impassable jungle a high karst plateau, the passages narrow canyon
# floors between them and the lowlands flat valleys. Heightmap steps: 10 = 1 map unit; the ground is at 97.
FELUCIA_ZONES = "WIPGFX/Assets/felucia_zones.png"
FELUCIA_BASE, FELUCIA_BASE_AT = "WIPGFX/Assets/felucia_heightmap_base.png", (590, 2270)
MASSIF = np.array([0, 0, 92, 0, 62], np.float32)     # broad lift per zone, reached ~12 px from the lowlands
MASSIF_RISE = 12.0                                   # px over which the slopes climb from the valleys
KARST_TOWERS = 520                                   # limestone towers on the massifs (the planet is ~120 px across)
KARST_HEIGHT = (18, 46)
RIDGES = 22                                          # ridged-noise relief on the massifs
ZONE_FLORA = np.array([0, 0.35, 1.65, 0.0, 1.65], np.float32)
PASSAGE = GRASSHILL          # terrain.bmp on the passages: a cleared track through the jungle


def felucia_relief(h, t, fel, town, units, rng, zone=None):
    """Massifs rising from the lowlands and passages, ridges and karst towers on top, ramped down to the coast; towers
    kept off unit positions and villages (plateaus there). Built on the saved pre-karst heightmap: re-runnable.
    Returns (new heightmap, relief above the base)."""
    H, W = h.shape
    ys, xs = np.nonzero(fel)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
    sub = fel[y0:y1, x0:x1]
    shp = sub.shape
    z = zone[y0:y1, x0:x1] if zone is not None else np.where(sub, 4, 0)
    yy, xx = np.mgrid[0:shp[0], 0:shp[1]].astype(np.float32)
    low = sub & np.isin(z, (1, 3))
    dlow = ndi.distance_transform_edt(~low) if low.any() else np.full(shp, 99.0)
    rim = smoothstep(np.clip((ndi.distance_transform_edt(sub) - 3) / 12, 0, 1))          # down to the coast
    rise = smoothstep(np.clip(dlow / MASSIF_RISE, 0, 1))                                 # valley walls
    lift = ndi.gaussian_filter(MASSIF[z], 4) * rise
    ridge = (1 - np.abs(2 * noise(shp, 9, rng, 3) - 1)) ** 2 * RIDGES * rise
    mtn = sub & np.isin(z, (2, 4))
    towers = np.zeros(shp, np.float32)
    cand = np.argwhere(mtn & (dlow > 2))
    for cy, cx in cand[rng.permutation(len(cand))[:KARST_TOWERS]]:
        r, a = rng.uniform(1.8, 4.5), rng.uniform(*KARST_HEIGHT) * rise[cy, cx]
        sl = np.s_[max(int(cy - r - 1), 0):int(cy + r + 2), max(int(cx - r - 1), 0):int(cx + r + 2)]
        d = np.hypot(yy[sl] - cy, xx[sl] - cx)
        towers[sl] = np.maximum(towers[sl], a * np.clip(1 - d / r, 0, 1) ** 0.45)      # steep sides, rounded top
    keep = np.ones(shp, np.float32)
    for uy, ux in units:
        uy, ux = uy - y0, ux - x0
        sl = np.s_[max(uy - 4, 0):uy + 5, max(ux - 4, 0):ux + 5]
        keep[sl] = np.minimum(keep[sl], np.clip(np.hypot(yy[sl] - uy, xx[sl] - ux) / 3.5, 0.0, 1))
    tw = town[y0:y1, x0:x1]
    keep = np.where(ndi.binary_dilation(tw, iterations=2), 0.0, keep)
    rel = lift + ridge * keep + towers * keep
    if tw.any():                                                                         # villages on a level plateau
        lab, n = ndi.label(ndi.binary_dilation(tw, iterations=1))
        for i in range(1, n + 1):
            m = lab == i
            rel[m] = (lift * m).sum() / m.sum()
    rel = ndi.gaussian_filter(rel, 0.6) * rim * sub
    full = np.zeros((H, W), np.float32)
    full[y0:y1, x0:x1] = rel
    base = h.copy()
    if os.path.exists(FELUCIA_BASE):
        b = np.asarray(Image.open(FELUCIA_BASE).convert("L")).astype(np.float32)
        by, bx = FELUCIA_BASE_AT
        base[by:by + b.shape[0], bx:bx + b.shape[1]] = b
    flat = np.minimum(base, GROUND + 3)                    # the old relief goes: the zones decide where the land rises
    return np.where(fel, np.clip(flat + full, 0, 252), h), full


def felucia_points(pid, fel):
    """Felucia's standing unit positions (map/unitstacks.txt type 0) and its victory point provinces."""
    H = pid.shape[0]
    provs = set(np.unique(pid[fel]).tolist())
    units = []
    for line in open(f"{MAP}/unitstacks.txt", encoding="utf-8-sig"):
        q = line.strip().split(";")
        if len(q) >= 5 and q[0].isdigit() and int(q[0]) in provs and q[1] == "0":
            units.append((H - 1 - int(round(float(q[4]))), int(round(float(q[2])))))
    vps = []
    for f in glob.glob("history/states/*.txt"):
        st = re.sub(r"#[^\n]*", "", open(f, encoding="utf-8-sig", errors="replace").read())
        own = [int(x) for x in re.search(r"provinces\s*=\s*\{([^}]*)\}", st).group(1).split()]
        if not provs.intersection(own) or re.search(r"impassable\s*=\s*yes", st):
            continue
        # a settlement at every victory point: Guild outposts and native strongholds (felucia_tribes.py)
        owner = re.search(r"owner\s*=\s*(\w+)", st).group(1)
        vps += [(int(pr), owner) for pr, _v in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)", st) if int(pr) in own]
    return units, vps


def felucia(t, trees, cm, water, city, h, labels, names, pid, rng):
    """Repaint Felucia only: giant flora (thinned, and cleared where units stand), farm-village clearings with
    Felucian village models at each state's victory point, its colormap (hue up close + globe) and its atmosphere
    glow. Brightness is kept and colour is a function of it, so re-running gives the same result."""
    t, trees, cm, city = t.copy(), trees.copy(), cm.copy(), city.copy()
    H, W = labels.shape
    planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
    fel = planet == FELUCIA
    units, vps = felucia_points(pid, fel)
    # villages: farmland that spawns city models, only in the clearing; no city models anywhere else on Felucia
    yy, xx = np.mgrid[0:H, 0:W]
    town = np.zeros((H, W), bool)
    native = np.zeros((H, W), bool)
    for prov, owner in vps:
        ys, xs = np.nonzero(pid == prov)
        k = np.argmin(np.hypot(ys - ys.mean(), xs - xs.mean()))          # a pixel of the province near its middle
        y0, x0 = ys[k], xs[k]
        sl = np.s_[max(y0 - FELUCIA_TOWN_R, 0):y0 + FELUCIA_TOWN_R + 1, max(x0 - FELUCIA_TOWN_R, 0):x0 + FELUCIA_TOWN_R + 1]
        disc = np.hypot(yy[sl] - y0, xx[sl] - x0) <= FELUCIA_TOWN_R
        town[sl] |= disc
        if owner == "FLT":
            native[sl] |= disc
    town &= fel
    zone = np.asarray(Image.open(FELUCIA_ZONES)) if os.path.exists(FELUCIA_ZONES) else np.where(fel, 4, 0).astype(np.uint8)
    t[fel & np.isin(t, (TOWN, GREENMTN, ROCK, PASSAGE)) & ~town] = JUNGLE     # repainted below
    t[town] = TOWN
    h, kar = felucia_relief(h, t, fel, town, units, np.random.default_rng(SEED + 59), zone)
    gy, gx = np.gradient(h)
    slope = np.hypot(gx, gy)
    t[fel & ~town & (kar > 15) & (slope > 2.5)] = GREENMTN         # jungle-clad massifs and karst flanks
    t[fel & ~town & (kar > 40) & (slope > 11)] = ROCK             # bare limestone cliffs
    t[fel & ~town & (zone == 3)] = PASSAGE
    city[fel] = 0
    city[town] = OUTPOST_CITY_STYLE
    city[town & native] = FELUCIA_CITY_STYLE
    # flora: thinner jungle, nothing on the village clearings or where units stand
    TH, TW = trees.shape
    rows = np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1)
    cols = np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1)
    gi = np.ix_(rows, cols)
    clear = town.copy()
    for y0, x0 in units:
        if zone[y0, x0] == 4:                                      # nobody stands in the impassable jungle
            continue
        sl = np.s_[max(y0 - FELUCIA_UNIT_CLEAR, 0):y0 + FELUCIA_UNIT_CLEAR + 1, max(x0 - FELUCIA_UNIT_CLEAR, 0):x0 + FELUCIA_UNIT_CLEAR + 1]
        clear[sl] |= np.hypot(yy[sl] - y0, xx[sl] - x0) <= FELUCIA_UNIT_CLEAR
    trees[fel[gi]] = 0
    clear |= ndi.binary_dilation(zone == 3, iterations=2)          # passages stay open
    dens = ZONE_FLORA[zone[gi]]
    cells = fel[gi] & (t[gi] != URBAN) & ~clear[gi] & (rng.random((TH, TW)) < FELUCIA_FILL * dens)
    idx, share = zip(*FELUCIA_FLORA)
    trees[cells] = rng.choice(idx, size=int(cells.sum()), p=np.array(share) / sum(share))
    under = fel[gi] & (t[gi] != URBAN) & ~clear[gi] & (trees == 0) & (rng.random((TH, TW)) < FELUCIA_UNDER_FILL * np.minimum(dens, 1))
    uidx, ushare = zip(*FELUCIA_UNDERGROWTH)
    trees[under] = rng.choice(uidx, size=int(under.sum()), p=np.array(ushare) / sum(ushare))
    cells |= under
    fh = fel[::2, ::2][:cm.shape[0], :cm.shape[1]]
    lum = cm[..., :3].mean(-1)
    stops, cols = zip(*FELUCIA_GROUND)
    lo, hi = np.percentile(lum[fh], (2, 98)) if fh.any() else (0, 1)
    k = np.clip((ndi.gaussian_filter(lum, 2.5) - lo) / max(hi - lo, 1e-3), 0, 1)   # smooth: the colormap is half-res
    pal = np.stack([np.interp(k, stops, [c[i] for c in cols]) for i in range(3)], -1)
    pal *= (lum / np.maximum(pal.mean(-1), 1e-3))[..., None]
    cm[..., :3] = np.where(fh[..., None], np.clip(pal, 0, 1), cm[..., :3])
    # glow: the space pixels nearest to Felucia take its haze colour at their own intensity
    for lvl, w in enumerate(water):
        wh, ww = w.shape[:2]
        sy, sx = H / wh, W / ww
        lab = labels[(np.arange(wh) * sy).astype(int)[:, None], (np.arange(ww) * sx).astype(int)[None, :]]
        _, (iy, ix) = ndi.distance_transform_edt(lab == 0, return_indices=True)
        own = fel[(iy * sy).astype(int), (ix * sx).astype(int)] & (lab == 0)
        amt = w[..., :3].max(-1, keepdims=True)
        w[..., :3] = np.where(own[..., None], amt * np.array(FELUCIA_ATMO), w[..., :3])
    print(f"Felucia: {int(cells.sum())} flora cells,", {int(i): int((trees[cells] == i).sum()) for i in idx},
          f"{len(vps)} villages ({int(town.sum())} px), {len(units)} unit positions kept clear")
    return t, trees, cm, water, city, h, kar


# Raxus Secundus: "a pastoral world" of meadows, farms, golden woods and villages among scattered mountains, and its
# capital Raxulon (Wookieepedia; The Clone Wars / The Bad Batch stills, Presley's concept art). Zones from
# raxus_map.py: 1 Senate hall, 2 city, 3 street, 4 countryside, 5 Senate Plaza, 6 Great Alley, 7 massif, 9 lake; the
# countryside provinces' gameplay terrain (plains / forest / hills / mountain foothills) decides fields, woods and
# downs. Woods are Raxus' own golden trees and crimson shrubs (flora_props.py 62-64).
RAXUS = "Raxus"
RAXUS_ZONES, RAXUS_JSON = "WIPGFX/Assets/raxus_zones.png", "WIPGFX/Assets/raxus_zones.json"
RAXUS_CITY_STYLE = 11        # map/cities.txt group: Raxus sandstone blocks and spires (military_buildings.py rax_city)
RAXUS_VILLAGE_R = (3, 2)     # map px radius of the market towns (victory points) and of the villages
RAXUS_PLATEAU = 4            # the capital stands this far above the base ground (heightmap steps, 10 = 1 map unit)
RAXUS_DOWNS, RAXUS_ROLL = 22, 7   # lift of the downs (hills provinces) and of the rolling countryside
RAXUS_PEAKS = (10, 80)       # massifs: lift above their foothills, plus jagged ridges and summits toward the core
RAXUS_LONE = (45, 75, 4.5)   # lone peaks (passable): height range, radius (px)
RAXUS_SNOW = 205             # heightmap value above which the peaks are snow-capped
RAXUS_FOOTHILLS = (5.0, 38)  # the countryside climbs into each massif over this many px, up to this lift
RAXUS_FIELD = 3              # px: size of a field in the patchwork
RAXUS_TREES = {2: (0.85, (62, 62, 63, 6)), 1: (0.07, (62, 63, 64)), 3: (0.12, (63, 64, 62)),
               5: (0.3, (63, 62, 64))}   # province terrain (5 = foothills) -> cover, tree picks (trees.bmp index)


def raxus(t, trees, cm, city, h, labels, names, pid, rng):
    """Repaint Raxus only: Raxulon on a level plateau (paved plaza and alley, streets free of city models), scattered
    massifs rising out of foothills, rolling countryside of field patchwork, golden woods and downs, a lake, market
    towns at the countryside victory points and villages round the land."""
    import json
    t, trees, cm, city = t.copy(), trees.copy(), cm.copy(), city.copy()
    H, W = labels.shape
    planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
    rax = planet == RAXUS
    zone = np.asarray(Image.open(RAXUS_ZONES))
    zj = json.load(open(RAXUS_JSON))
    prov = {int(p): v for p, v in zj["provinces"].items()}
    ptype = np.zeros(int(pid.max()) + 1, np.uint8)               # 1 plains 2 forest 3 hills 5 foothills
    for p, v in prov.items():
        ptype[p] = {"plains": 1, "forest": 2, "hills": 3, "mountain": 5}.get(v["terrain"], 0)
    ctry = ptype[pid] * (zone == 4)
    ys, xs = np.nonzero(rax)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
    sl = np.s_[y0:y1, x0:x1]
    sub, z, ct = rax[sl], zone[sl], ctry[sl]
    # market towns at the countryside victory points, villages round the land
    town = np.zeros((H, W), bool)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    spots = []
    for f in glob.glob("history/states/*Raxus - *.txt"):
        st = open(f, encoding="utf-8-sig").read()
        spots += [(int(vp), RAXUS_VILLAGE_R[0]) for vp in re.findall(r"victory_points\s*=\s*\{\s*(\d+)", st)
                  if prov.get(int(vp), {}).get("kind") == 4]
    spots += [(p, RAXUS_VILLAGE_R[1]) for p in zj.get("villages", [])]
    for p, rad in spots:
        cy, cx = prov[p]["centre"]
        town[sl] |= np.hypot(yy - cy, xx - cx) <= rad
    town &= rax & (zone == 4)
    # relief: level capital, massifs (lift + ridges + summits toward the core) out of foothills, rolling countryside
    rim = smoothstep(np.clip((ndi.distance_transform_edt(sub) - 2) / 10, 0, 1))
    mass = z == 7
    core = ndi.distance_transform_edt(mass)
    lab, n = ndi.label(mass)
    depth = np.zeros(sub.shape, np.float32)
    for i in range(1, n + 1):
        m_ = lab == i
        depth[m_] = core[m_] / max(core[m_].max(), 1)                       # 0 at the foot .. 1 at the core
    ridge = (1 - np.abs(2 * noise(sub.shape, 4, rng, 3) - 1)) ** 2
    peaks = smoothstep(np.clip(core / 2.5, 0, 1)) * (RAXUS_PEAKS[0] + RAXUS_PEAKS[1] * depth ** 0.8 * (0.45 + 0.75 * ridge))
    peaks = ndi.gaussian_filter(peaks, 0.7)
    foot = np.exp(-ndi.distance_transform_edt(~mass) / RAXUS_FOOTHILLS[0]) * RAXUS_FOOTHILLS[1] * (z == 4)
    roll = noise(sub.shape, 10, rng, 3) * RAXUS_ROLL
    downs = ndi.gaussian_filter((ct == 3).astype(np.float32), 2.5) * RAXUS_DOWNS * (0.6 + 0.8 * noise(sub.shape, 5, rng, 2))
    wood = ndi.gaussian_filter((ct == 2).astype(np.float32), 2) * 4
    country = (z == 4).astype(np.float32)
    lone = np.zeros(sub.shape, np.float32)
    for p, v in prov.items():                                              # lone peaks: a rocky cone each
        if v.get("peak"):
            d = np.hypot(yy - v["centre"][0], xx - v["centre"][1]) / RAXUS_LONE[2]
            lone = np.maximum(lone, rng.uniform(*RAXUS_LONE[:2]) * np.clip(1 - d, 0, 1) ** 1.6 * (0.8 + 0.4 * ridge))
    # the massifs start from the foothills' height at their foot (no moat round them)
    rel = RAXUS_PLATEAU + country * (roll + downs + wood + foot + lone) + peaks + (z == 7) * RAXUS_FOOTHILLS[1]
    rel = np.where(z == 9, 1.0, rel)                                         # the lake: a level sheet
    rel = np.where(town[sl], ndi.gaussian_filter(rel, 3), rel)              # towns on gentle ground
    rel = np.where(np.isin(z, (1, 2, 3, 5, 6)), RAXUS_PLATEAU, rel)         # the capital stays level
    hn = h.copy()
    rel = landforms(rel, sub)
    hn[sl] = np.where(sub, np.clip(GROUND + rel * rim, 0, 252), h[sl])
    gy, gx = np.gradient(hn[sl])
    slope = np.hypot(gx, gy)
    # terrain.bmp
    field = np.zeros((H, W), np.float32)
    field[sl] = noise(sub.shape, RAXUS_FIELD, rng, 1)
    tz = np.full((H, W), -1, np.int16)
    tz[rax & np.isin(zone, (1, 3, 5, 6))] = 25                             # urban_plaza_25: no city models
    tz[rax & (zone == 2)] = URBAN
    tz[rax & (ctry == 1)] = np.where(field > 0.55, GRASS, FARM)[rax & (ctry == 1)]
    tz[rax & (ctry == 2)] = np.where(field > 0.7, DFOREST, FOREST)[rax & (ctry == 2)]
    tz[rax & (ctry == 3)] = np.where(field > 0.6, GRASS, GRASSHILL)[rax & (ctry == 3)]
    tz[rax & (ctry == 5)] = np.where(field > 0.5, GRASSHILL, HILLS)[rax & (ctry == 5)]
    hs, sls = np.zeros((H, W), np.float32), np.zeros((H, W), np.float32)
    hs[sl], sls[sl] = hn[sl], slope
    lone_px = np.zeros((H, W), bool)
    lone_px[sl] = lone > 18
    mtn = rax & ((zone == 7) | lone_px)
    tz[mtn] = np.where(hs > RAXUS_SNOW, SNOWROCK, np.where(sls > 6, ROCK, GREENMTN))[mtn]
    tz[rax & (zone == 9)] = WATER
    tz[town] = TOWN
    t = np.where(tz >= 0, tz, t).astype(t.dtype)
    city[rax] = 0
    city[rax & np.isin(zone, (2, 3))] = RAXUS_CITY_STYLE                   # streets keep the blocks one urban area
    city[town] = RAXUS_CITY_STYLE
    # trees: Raxus' golden trees and crimson shrubs; woods dense, copses on fields and downs, scattered on the
    # foothills and the massifs' lower slopes; nothing in the city, towns or lake
    TH, TW = trees.shape
    gi = np.ix_(np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1),
                np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1))
    trees[rax[gi]] = 0
    r = rng.random((TH, TW))
    ok = rax[gi] & (zone[gi] == 4) & ~ndi.binary_dilation(town, iterations=2)[gi]
    for kind, (cover, pick) in RAXUS_TREES.items():
        sel = ok & (ctry[gi] == kind) & (r < cover)
        trees[sel] = rng.choice(pick, size=int(sel.sum()))
    slopes = rax[gi] & (zone[gi] == 7) & (hs[gi] < RAXUS_SNOW - 40) & (r < 0.3)
    trees[slopes] = rng.choice((63, 6), size=int(slopes.sum()))
    # the colormap (painted globe zoomed out, hue up close) stays the original painting: the user prefers it
    print(f"Raxus: {int((tz == URBAN).sum())} px city, {int(mtn.sum())} px massifs (top {int(hs[sl].max())}), "
          f"{len(spots)} towns and villages, {int((trees[rax[gi]] > 0).sum())} tree cells")
    return t, trees, cm, city, hn


# Raxus Prime: "a planet covered in junk" (Wookieepedia), the galaxy's dump, a maze of junk yards. Zones from
# raxus_prime_map.py: 1 the Sienar Refinery, 2 the capital's junk town, 4 yards (passable, on the ground or the upper
# level of junk plateau), 5 the maze's walls (impassable strips), 7 scrap mountains, 9 the toxic waste pools. Yards are
# level, ramps only where an opening joins yards of different levels (elsewhere the walls hide the cliffs); the walls
# are flat-topped ridges of junk a step above their yards, crowned with junk heaps; props only stand on flat ground (a
# prop on a slope tilts with it). Ground: our junk tile (atlas slot 19: scrap_28 / scrap_town_29); heaps and wrecks:
# flora_props.py 65-78; scrap towns (city style 12) at the capital and every state's victory point. The painted globe
# (colormap) stays as it was.
RP = "Raxus Prime"
RP_ZONES, RP_JSON = "WIPGFX/Assets/raxus_prime_zones.png", "WIPGFX/Assets/raxus_prime_zones.json"
SCRAP, SCRAP_TOWN = 28, 29          # terrain.bmp indices (common/terrain/00_terrain.txt)
RP_CITY_STYLE = 12                  # map/cities.txt group: scrap towns (coruscant_buildings.py)
RP_TOWN_R = 2.5                     # px radius of each outer scrap town
RP_SPRAWL_W = 1.2                   # px half-width of the passageways the city sprawls along (raxus_prime_map.py)
RP_PLATEAU = 3                      # the ground level above the base (heightmap steps, 10 = 1 map unit)
RP_UPPER = 30                       # height of the upper level of junk plateau
RP_RAMP = 1.3                       # px of blur that turns an opening between two levels into a ramp
RP_WALL_H = 0                       # the walls: level with the higher yard beside them; their heaps make the wall
RP_PEAKS = (25, 70)                 # scrap mountains: lift above their level + heaped peaks toward the core
RP_RIM = 4.0                        # px from the coast kept bare (no junk spilling into space)
RP_FLAT = 6.0                       # max slope (heightmap steps per px) a prop may stand on
# heaps on the walls (every cell) and the mountains' flat tops; on yard floors three cells in four get a wreck or junk
RP_WALL_PROPS = [(76, 0.26), (73, 0.16), (74, 0.16), (75, 0.12), (77, 0.15), (78, 0.15)]
RP_YARD_PROPS = [(69, 0.16), (70, 0.08), (71, 0.09), (72, 0.07), (65, 0.045), (66, 0.045), (67, 0.04), (68, 0.02),
                 (77, 0.1), (73, 0.08), (78, 0.04)]
RP_SITE_CLEAR = 3.5                 # px kept free of props round the big wrecks (raxus_prime_map.py WRECKS)
RP_SITE_PAD = 6.0                   # px of level ground round each big wreck: no plateau or wall may bury the hulls
RP_WALL_FLAT = 9.0                  # wall heaps may stand on steeper ground (a wall above a cliff)


def raxus_prime(t, trees, city, h, labels, names, pid, rng):
    """Repaint Raxus Prime only (terrain.bmp, heightmap, cities.bmp, trees.bmp); the colormap is left alone."""
    import json
    t, trees, city = t.copy(), trees.copy(), city.copy()
    H, W = labels.shape
    planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
    rp = planet == RP
    zone = np.asarray(Image.open(RP_ZONES))
    zj = json.load(open(RP_JSON))
    prov = {int(p): v for p, v in zj["provinces"].items()}
    ys, xs = np.nonzero(rp)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
    sl = np.s_[y0:y1, x0:x1]
    sub, z, ps = rp[sl], zone[sl], pid[sl]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    town = np.zeros((H, W), bool)
    for p in zj["towns"]:
        if prov[p]["kind"] == 4:
            cy, cx = prov[p]["centre"]
            town[sl] |= np.hypot(yy - cy, xx - cx) <= RP_TOWN_R
    town |= rp & (zone == 2)
    town &= rp & np.isin(zone, (2, 4))
    # the city's sprawl: scrap-town ground (city models) along the passageways from the capital to the outer towns
    sprawl = np.zeros(sub.shape, bool)
    for line in zj.get("passages", []):
        for (ay, ax), (by, bx) in zip(line[:-1], line[1:]):
            dy, dx = by - ay, bx - ax
            t_ = np.clip(((yy - ay) * dy + (xx - ax) * dx) / max(dy * dy + dx * dx, 1e-6), 0, 1)
            sprawl |= np.hypot(yy - ay - t_ * dy, xx - ax - t_ * dx) <= RP_SPRAWL_W
    sprawl &= sub & (z == 4)
    # relief: level yards (ramps through openings only), walls a step above, mountains on their yard, sunken pools
    coast = ndi.distance_transform_edt(sub)
    rim = smoothstep(np.clip((coast - 2) / 8, 0, 1))
    lvl = np.zeros(int(pid.max()) + 1, np.float32)
    for p, v in prov.items():
        lvl[p] = v.get("level", 0)
    yard = sub & np.isin(z, (1, 2, 4))
    base = np.where(yard, lvl[ps] * RP_UPPER, 0).astype(np.float32)
    wsum = ndi.gaussian_filter(base * yard, RP_RAMP)
    wcnt = ndi.gaussian_filter(yard.astype(np.float32), RP_RAMP)
    ground = np.where(yard, wsum / np.maximum(wcnt, 1e-3), 0)                # blurred only among touching yards
    near = ndi.grey_dilation(np.where(yard, ground, 0), size=5)             # the higher yard beside each wall
    wall = sub & (z == 5)
    mass = sub & (z == 7)
    core = ndi.distance_transform_edt(mass)
    lab, n = ndi.label(mass)
    depth = np.zeros(sub.shape, np.float32)
    for i in range(1, n + 1):
        m_ = lab == i
        depth[m_] = core[m_] / max(core[m_].max(), 1)
    heap = (1 - np.abs(2 * noise(sub.shape, 3, rng, 3) - 1)) ** 1.5
    peaks = smoothstep(np.clip(core / 2.0, 0, 1)) * (RP_PEAKS[0] + RP_PEAKS[1] * depth ** 0.7 * (0.4 + 0.8 * heap))
    rel = RP_PLATEAU + ground + noise(sub.shape, 5, rng, 2) * 2 * yard
    rel = np.where(wall, RP_PLATEAU + near + RP_WALL_H, rel)
    rel = np.where(mass, RP_PLATEAU + near + ndi.gaussian_filter(peaks, 0.6), rel)
    rel = np.where(z == 9, 0.5, rel)
    for sy, sx in zj["sites"].values():                                       # the wrecks lie on a level pad, the
        pad = (np.hypot(yy - sy, xx - sx) <= RP_SITE_PAD) & sub & (z != 9)   # walls and plateaus stepping back
        rel = np.where(pad, np.minimum(rel, rel[pad].min() + 0.5), rel)
    flat = town[sl] | (z == 1)                                               # towns / the refinery: level ground
    fl, nf = ndi.label(flat)
    for i in range(1, nf + 1):
        m_ = fl == i
        rel[m_] = np.median(rel[m_])
    hn = h.copy()
    rel = landforms(rel, sub)
    hn[sl] = np.where(sub, np.clip(GROUND + rel * rim, 0, 252), h[sl])
    gy, gx = np.gradient(hn[sl])
    slope = np.zeros((H, W), np.float32)
    slope[sl] = np.hypot(gx, gy)
    # terrain.bmp: junk everywhere, bare brown faces on the steepest cliffs, the pools marsh
    tz = np.full((H, W), -1, np.int16)
    tz[rp] = SCRAP
    tz[rp & (slope > 10)] = BROWN
    tz[rp & (zone == 9)] = WATER
    tz[rp & (zone == 1)] = 25                                                # under the refinery: no city models
    tz[sl][sprawl] = SCRAP_TOWN
    tz[town] = SCRAP_TOWN
    t = np.where(tz >= 0, tz, t).astype(t.dtype)
    city[rp] = 0
    city[sl][sprawl] = RP_CITY_STYLE
    city[town] = RP_CITY_STYLE
    # props: heaps along every wall and on the mountains' flat tops, half the yard floors strewn with wrecks and
    # junk; only on flat ground, yard junk not on the coast, nothing in the towns, the pools or by the big wrecks
    TH, TW = trees.shape
    gi = np.ix_(np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1),
                np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1))
    trees[rp[gi]] = 0
    clear = ndi.binary_dilation(town, iterations=1) | (rp & np.isin(zone, (1, 9)))
    lane = np.zeros((H, W), bool)
    lane[sl] = sprawl                                                         # yard junk off the passageways
    for sy, sx in zj["sites"].values():
        clear[sl] |= np.hypot(yy - sy, xx - sx) <= RP_SITE_CLEAR
    inland = np.zeros((H, W), bool)
    inland[sl] = coast > RP_RIM
    on_wall = np.zeros((H, W), bool)
    on_wall[sl] = ndi.binary_dilation(wall, iterations=2)
    level_ok = slope <= RP_FLAT
    ok = rp[gi] & ~clear[gi]
    ashore = np.zeros((H, W), bool)
    ashore[sl] = coast > 2.5                                                 # wall heaps: not hanging over space
    ok &= ashore[gi]
    r = rng.random((TH, TW))
    for cells, props in ((ok & on_wall[gi] & (slope <= RP_WALL_FLAT)[gi], RP_WALL_PROPS),
                         (ok & ~on_wall[gi] & (zone[gi] == 7) & level_ok[gi], RP_WALL_PROPS),
                         (ok & inland[gi] & ~on_wall[gi] & ~lane[gi] & (zone[gi] == 4) & level_ok[gi], RP_YARD_PROPS)):
        lo = 0.0
        for idx, share in props:
            sel = cells & (r >= lo) & (r < lo + share)
            trees[sel] = idx
            lo += share
    print(f"Raxus Prime: {int(wall.sum())} px walls, {int(mass.sum())} px scrap mountains (top {int(hn[sl].max())}), "
          f"{int(town.sum())} px towns, {int(sprawl.sum())} px sprawl, {int((trees[rp[gi]] > 0).sum())} prop cells")
    return t, trees, city, hn


# Korriban (korriban_map.py, after the user's references 2026-10-13: Moraband fan maps, Tom Cartos' Valley of Tombs,
# KOTOR/TOR/TCW art). Zones: 1 tomb niches, 2 the Valley of the Dark Lords and its entrance, 3 the ruined Sith
# Academy, 4 mountain massifs (impassable), 5 the open wastes, 6 the Dead Lake (impassable), 7 the ruins of Dreshdae, 8 the
# ziggurat (Sith Citadel), 9 the crypts behind the tombs (zones 5, 6, 8 are from an earlier layout). Open dune wastes with a few lone buttes; massifs with one crest line down their middle and
# gullies off it; a flat valley floor walled in by its range, the tombs cut into the walls at floor level; the academy
# ruins on a terrace at the valley's head; Dreshdae a ruin too (the planet is abandoned: no city models). The painted globe (colormap) stays.
KORRIBAN = "Korriban"
KOR_ZONES, KOR_JSON = "WIPGFX/Assets/korriban_zones.png", "WIPGFX/Assets/korriban_zones.json"
KOR_LEVEL = {1: 2, 2: 2, 3: 12, 5: 4, 6: 0.5, 7: 4, 8: 5, 9: 1}   # heightmap steps above the base, by zone
KOR_DUNES = 5                       # dune relief on the wastes
KOR_RAMP = 2.5                      # px over which the academy terrace climbs from the valley floor
KOR_WALL = (14, 1.5)                # cliff at the foot of the ranges: height, px it takes to climb it
KOR_RANGE = (40, 110)               # range height above the cliff: thinnest and broadest massifs (crest)
KOR_BUTTES = (7, 0.76, 2.0, 24)     # rock outcrops on the wastes: noise cell, threshold, px to full height, height
KOR_TERRAIN = {1: 25, 2: BROWN, 3: 25, 5: DUNES, 6: ROCK2, 7: 25, 8: 25, 9: ROCK}  # urban_plaza_25: stone, no city models
KOR_PROPS = {4: [(50, 0.05), (48, 0.03)],                               # boulders at the range feet only
             5: [(48, 0.015), (49, 0.015), (80, 0.008)],                   # the wastes: rocks, a ruin here and there
             2: [(80, 0.04), (48, 0.02)],                                  # valley floor: ruins and rocks
             3: [(80, 0.2)],                                               # the academy grounds: rubble and ruins
             7: [(80, 0.15), (48, 0.03)],                                  # the ruins of Dreshdae
             9: [(80, 0.12), (50, 0.06)]}                                  # the crypts: bones of ruins, boulders


def korriban(t, trees, city, h, labels, names, pid, rng):
    """Repaint Korriban only (terrain.bmp, heightmap, cities.bmp, trees.bmp); the colormap is left alone."""
    t, trees, city = t.copy(), trees.copy(), city.copy()
    H, W = labels.shape
    planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
    kor = planet == KORRIBAN
    zone = np.asarray(Image.open(KOR_ZONES))
    ys, xs = np.nonzero(kor)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
    sl = np.s_[y0:y1, x0:x1]
    sub, z = kor[sl], zone[sl]
    yy, xx = np.mgrid[0:sub.shape[0], 0:sub.shape[1]].astype(np.float32)
    rim = smoothstep(np.clip((ndi.distance_transform_edt(sub) - 2) / 5, 0, 1))
    mtn = z == 4
    # px into the massifs, from a signed distance smoothed so their feet curve instead of following pixel steps;
    # height follows it, scaled so every massif peaks on its own middle line; broader massifs stand taller; warped
    # ridged noise cuts spurs and gullies down the flanks
    into = np.maximum(ndi.gaussian_filter(ndi.distance_transform_edt(mtn) - ndi.distance_transform_edt(~mtn), 1.4), 0)
    crest = ndi.grey_dilation(into, size=(13, 13))
    u = np.clip(into / np.maximum(crest, 1), 0, 1)
    tall = np.clip((crest - 3) / 9, 0, 1)
    wy, wx = (noise(sub.shape, 10, rng, 2) - 0.5) * 5, (noise(sub.shape, 10, rng, 2) - 0.5) * 5
    wyi = np.clip(np.rint(yy + wy).astype(int), 0, sub.shape[0] - 1)
    wxi = np.clip(np.rint(xx + wx).astype(int), 0, sub.shape[1] - 1)
    gully = np.zeros(sub.shape, np.float32)
    for cell, amp in ((6, 0.6), (3, 0.4)):
        gully += amp * (1 - np.abs(2 * noise(sub.shape, cell, rng, 1)[wyi, wxi] - 1)) ** 3
    cliff = smoothstep(np.clip(into / KOR_WALL[1], 0, 1)) * KOR_WALL[0]
    peak = (KOR_RANGE[0] + (KOR_RANGE[1] - KOR_RANGE[0]) * tall) * u * (0.45 + 0.85 * gully)
    # the open ground: each zone at its level, dunes on the wastes, lone buttes away from the province centres
    lvl = np.zeros(sub.shape, np.float32)
    for zk, v in KOR_LEVEL.items():
        lvl[z == zk] = v
    lvl = np.where(z == 3, KOR_LEVEL[2] + (KOR_LEVEL[3] - KOR_LEVEL[2])
                   * smoothstep(np.clip(ndi.distance_transform_edt(z == 3) / KOR_RAMP, 0, 1)), lvl)
    wastes = z == 5
    dunes = noise(sub.shape, 5, rng, 3) * KOR_DUNES * smoothstep(np.clip(ndi.distance_transform_edt(wastes) / 3, 0, 1))
    zj = json.load(open(KOR_JSON))
    cen = np.array([v["centre"] for v in zj["provinces"].values()]) - [y0, x0]
    far = (ndi.distance_transform_edt(wastes) > 2.5) & (np.min([np.hypot(yy - a, xx - b) for a, b in cen], 0) > 4)
    blob = far & (noise(sub.shape, KOR_BUTTES[0], rng, 3) > KOR_BUTTES[1])
    sizes = ndi.sum(blob, ndi.label(blob)[0], range(ndi.label(blob)[1] + 1))
    blob &= sizes[ndi.label(blob)[0]] >= 5                                   # no single-pixel pimples
    buttes = KOR_BUTTES[3] * smoothstep(np.clip(ndi.gaussian_filter(ndi.distance_transform_edt(blob), 0.7) / KOR_BUTTES[2], 0, 1))         * (0.5 + 0.7 * gully)
    open_ = (~mtn).astype(np.float32)
    flat = ndi.gaussian_filter(lvl * open_, 1.2) / np.maximum(ndi.gaussian_filter(open_, 1.2), 1e-3)
    rel = np.where(mtn, KOR_LEVEL[5] + cliff + peak, flat + np.where(wastes, dunes + buttes, 0))
    rel = np.where(z == 6, KOR_LEVEL[6], rel)                               # the Dead Lake: dead flat
    hn = h.copy()
    rel = landforms(rel, sub)
    hn[sl] = np.where(sub, np.clip(GROUND + rel * rim, 0, 252), h[sl])
    gy, gx = np.gradient(hn[sl])
    slope = np.hypot(gx, gy)
    # terrain.bmp: rock by slope on the massifs and buttes, dunes on the wastes, stone at the tombs, academy, citadel
    tz = np.full(sub.shape, -1, np.int16)
    for zk, tt in KOR_TERRAIN.items():
        tz[sub & (z == zk)] = tt
    rock = sub & (mtn | (wastes & (buttes > 4)))
    tz[rock] = np.where(slope > 9, 24, np.where(slope > 4, BROWNMTN, BROWN))[rock]
    t[sl] = np.where(tz >= 0, tz, t[sl]).astype(t.dtype)
    city[kor] = 0
                                                                            # an abandoned planet: no city models
    TH, TW = trees.shape
    gi = np.ix_(np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1),
                np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1))
    trees[kor[gi]] = 0
    r = rng.random((TH, TW))
    ashore = np.zeros((H, W), bool)
    ashore[sl] = ndi.distance_transform_edt(sub) > 2.5
    feet = np.zeros((H, W), bool)
    feet[sl] = mtn & (into < 3)
    level = np.zeros((H, W), bool)
    level[sl] = slope < 4
    for zk, props in KOR_PROPS.items():
        ok = kor[gi] & ashore[gi] & (zone[gi] == zk) & (feet[gi] if zk == 4 else level[gi])
        lo = 0.0
        for idx, share in props:
            trees[ok & (r >= lo) & (r < lo + share)] = idx
            lo += share
    print(f"Korriban: zones {dict(zip(*np.unique(z[sub], return_counts=True)))}, top {int(hn[sl].max())}")
    return t, trees, city, hn


# Florrum (florrum_map.py; The Clone Wars stills: "Dooku Captured", "The Gungan General", "A Necessary Bond"): olive
# and ochre dust plains broken by flat-topped rock shelves stacked in tiers, a canyon with sandstone walls down the
# middle, acid flats with sulfur pools and geysers (florrum_fx.py), the Ohnaka Gang's bases on level pads. Zones:
# 1 plains, 2 canyon, 3 acid flats, 4 shelves (impassable), 5 bases, 6 the junk market. The painted globe is pushed
# toward olive green and sulfur yellow (user: "a greenish look"), brightness kept.
FLORRUM = "Florrum"
FLO_ZONES, FLO_JSON = "WIPGFX/Assets/florrum_zones.png", "WIPGFX/Assets/florrum_zones.json"
FLO_PLAIN, FLO_FLOOR, FLO_PAD = 16, 2, 17      # heightmap steps above the base: plains, canyon floor, base pads
FLO_TIER = (16, 3.6, 3)                        # shelves: height of a tier, px of ground per tier, tiers at most
FLO_OUTCROP = (8, 0.8, 1.5, 9)                 # little passable shelves on the plains: noise cell, threshold, px/tier, tier
FLO_POOLS = (5, 0.78, 3)                       # sulfur pools on the acid flats: noise cell, threshold, depth
FLO_PUDDLES = (4, 0.86)                        # a few puddles on the plains too
WET = 9                                        # terrain.bmp marsh (atlas slot 6: water)
FLO_GROUND = [(0.0, (0.20, 0.21, 0.09)), (0.45, (0.40, 0.42, 0.17)), (0.8, (0.55, 0.52, 0.24)), (1.0, (0.66, 0.60, 0.30))]
FLO_ZONE_TINT = {3: (1.0, 1.08, 0.8), 4: (1.1, 0.95, 0.85), 2: (1.08, 0.97, 0.88)}   # acid flats greener, rock ochre
FLO_PROPS = {1: [(48, 0.012), (49, 0.012), (50, 0.008)], 2: [(50, 0.04), (48, 0.03)], 4: [(50, 0.03)],
             3: [(49, 0.01)]}


def florrum(t, trees, city, h, labels, names, pid, rng, cm):
    """Repaint Florrum only (terrain.bmp, heightmap, cities.bmp, trees.bmp, and its colours in the colormap)."""
    t, trees, city, cm = t.copy(), trees.copy(), city.copy(), cm.copy()
    H, W = labels.shape
    planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
    flo = planet == FLORRUM
    zone = np.asarray(Image.open(FLO_ZONES))
    ys, xs = np.nonzero(flo)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
    sl = np.s_[y0:y1, x0:x1]
    sub, z = flo[sl], zone[sl]
    rim = smoothstep(np.clip((ndi.distance_transform_edt(sub) - 1.5) / 3, 0, 1))
    zj = json.load(open(FLO_JSON))
    cen = np.array([v["centre"] for v in zj["provinces"].values()]) - [y0, x0]
    yy, xx = np.mgrid[0:sub.shape[0], 0:sub.shape[1]].astype(np.float32)
    near_unit = np.min([np.hypot(yy - a, xx - b) for a, b in cen], 0) < 2.5
    # shelves: tiers stepping up toward the middle of each (flat tops, sheer steps, ragged edges)
    shelf = z == 4
    into = ndi.distance_transform_edt(shelf) + (noise(sub.shape, 5, rng, 2) - 0.5) * 2.4
    tiers = np.clip(np.floor(into / FLO_TIER[1]) + 1, 0, FLO_TIER[2])
    edge = np.clip((into / FLO_TIER[1]) % 1 * 4, 0, 1)                      # the step climbs over a quarter tier
    rel = np.where(shelf, FLO_PLAIN + (tiers - 1 + smoothstep(edge)) * FLO_TIER[0], FLO_PLAIN)
    # plains: soft dust, a few small stacked outcrops away from the unit positions
    plains = np.isin(z, (1, 3))
    rel = np.where(plains, FLO_PLAIN + noise(sub.shape, 9, rng, 3) * 3, rel)
    crop = plains & (noise(sub.shape, FLO_OUTCROP[0], rng, 3) > FLO_OUTCROP[1]) & ~near_unit & (ndi.distance_transform_edt(sub) > 3)
    cd = ndi.distance_transform_edt(crop)
    rel = np.where(crop, rel + np.clip(np.ceil(cd / FLO_OUTCROP[2]), 0, 2) * FLO_OUTCROP[3], rel)
    # canyon: sunk below the plains, sheer sandstone walls
    can = z == 2
    cin = ndi.gaussian_filter(ndi.distance_transform_edt(can), 0.6)
    rel = np.where(can, FLO_PLAIN - (FLO_PLAIN - FLO_FLOOR) * smoothstep(np.clip(cin / 1.2, 0, 1)), rel)
    # bases and the market: level pads
    rel = np.where(np.isin(z, (5, 6)), FLO_PAD, rel)
    # sulfur pools on the acid flats, puddles here and there on the plains: shallow and dead flat
    pools = (z == 3) & (noise(sub.shape, FLO_POOLS[0], rng, 2) > FLO_POOLS[1]) & ~near_unit
    pools |= (z == 1) & (noise(sub.shape, FLO_PUDDLES[0], rng, 2) > FLO_PUDDLES[1]) & ~near_unit & ~crop
    pools &= ndi.distance_transform_edt(sub) > 3                           # none on the planet's rim
    rel = np.where(pools, FLO_PLAIN - FLO_POOLS[2], rel)
    hn = h.copy()
    rel = landforms(rel, sub)
    hn[sl] = np.where(sub, np.clip(GROUND + rel * rim, 0, 252), h[sl])
    gy, gx = np.gradient(hn[sl])
    slope = np.hypot(gx, gy)
    # terrain.bmp: sand and olive scrub on the plains, scrubland on the acid flats, water in the pools, rock by slope
    tz = np.full(sub.shape, -1, np.int16)
    mix = noise(sub.shape, 6, rng, 2)
    tz[sub & plains] = np.where(mix > 0.55, BROWN, DUNES)[sub & plains]
    tz[sub & (z == 3)] = np.where(mix > 0.4, SAVANNA, BROWN)[sub & (z == 3)]
    tz[sub & can] = SAND
    tz[sub & shelf] = BROWNMTN
    tz[sub & np.isin(z, (5, 6))] = 25                                      # urban_plaza_25: pads, no city models
    steep = sub & (slope > 4) & ~np.isin(z, (5, 6))
    tz[steep] = np.where(slope > 8, ROCK, BROWNMTN)[steep]
    tz[sub & pools] = WET
    t[sl] = np.where(tz >= 0, tz, t[sl]).astype(t.dtype)
    city[flo] = 0                                                          # bases are models (military_buildings.py)
    # props: rocks on the plains and at the canyon walls, none on pools, pads or where units stand
    TH, TW = trees.shape
    gi = np.ix_(np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1),
                np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1))
    trees[flo[gi]] = 0
    r = rng.random((TH, TW))
    ok = np.zeros((H, W), bool)
    ok[sl] = sub & ~pools & ~near_unit & (ndi.distance_transform_edt(sub) > 2)
    for zk, props in FLO_PROPS.items():
        cells = ok[gi] & (zone[gi] == zk)
        lo = 0.0
        for idx, share in props:
            trees[cells & (r >= lo) & (r < lo + share)] = idx
            lo += share
    # colours: the painting's brightness through an olive -> sulfur-yellow ramp, zones nudged (half-res colormap)
    fh = flo[::2, ::2][:cm.shape[0], :cm.shape[1]]
    lum = cm[..., :3].mean(-1)
    lo_, hi_ = np.percentile(lum[fh], (2, 98))
    k = np.clip((ndi.gaussian_filter(lum, 1.5) - lo_) / max(hi_ - lo_, 1e-3), 0, 1)
    stops, cols = zip(*FLO_GROUND)
    pal = np.stack([np.interp(k, stops, [c[i] for c in cols]) for i in range(3)], -1)
    zh = zone[::2, ::2][:cm.shape[0], :cm.shape[1]]
    for zk, tint in FLO_ZONE_TINT.items():
        pal = np.where((zh == zk)[..., None], pal * np.array(tint), pal)
    pal *= (np.maximum(lum, 0.12) / np.maximum(pal.mean(-1), 1e-3))[..., None]
    cm[..., :3] = np.where(fh[..., None], np.clip(pal, 0, 1), cm[..., :3])
    print(f"Florrum: zones {dict(zip(*np.unique(z[sub], return_counts=True)))}, top {int(hn[sl].max())}, "
          f"{int(pools.sum())} px pools, {int(crop.sum())} px outcrops")
    return t, trees, city, hn, cm


# Kadavo (kadavo_map.py; The Clone Wars "Slaves of the Republic" / "Escape from Kadavo" stills): grey ash plains
# crowded with stone domes with crater openings, and pit craters, under smog, great dormant volcanoes with summit craters and long
# low lava flows, the Great Crater on top of the largest dome with lava glowing in it (the facility hangs over it),
# terraced ore pits. Zones: 1 plains, 2 facility, 3 crater, 4 volcano (+ flows), 5 landing field, 6 ore pits. The
# painted globe (dark grey-brown with orange lava, like the show's planet) stays.
KADAVO = "Kadavo"
KAD_ZONES, KAD_JSON = "WIPGFX/Assets/kadavo_zones.png", "WIPGFX/Assets/kadavo_zones.json"
KAD_PLAIN, KAD_DECK, KAD_FLOOR, KAD_PAD = 8, 70, 1, 9     # heightmap steps above the base (KAD_DECK: the dome's rim;
                                                          # military_buildings.py KAD_RIM = (KAD_DECK - KAD_FLOOR - 1) / 10)
KAD_CONES = (0.014, (1.8, 6.5), (2, 6))   # stone-rimmed craters on the plains ("Escape from Kadavo": everywhere, every
                                     # size, overlapping): per px density, radius range, rim height range
KAD_HOLE = 0.6                       # their crater openings: share of the radius
KAD_PITS = (0.006, (1.2, 2.4), 3)    # pit craters: density, radius range, depth
KAD_VOLCANO = (95, 0.18)             # great volcanoes: summit height above the plains, summit crater (share of radius)
KAD_FLOW = 5                         # lava flows: a low rough sheet this high
KAD_PIT_STEPS = (3, 2.2)             # ore pits: terraces, px per terrace
KAD_PROPS = {1: [(48, 0.012), (49, 0.012), (50, 0.008)], 4: [(50, 0.02)], 6: [(48, 0.04)]}


def kadavo(t, trees, city, h, labels, names, pid, rng):
    """Repaint Kadavo only (terrain.bmp, heightmap, cities.bmp, trees.bmp); the colormap is left alone."""
    import kadavo_map as km
    t, trees, city = t.copy(), trees.copy(), city.copy()
    H, W = labels.shape
    planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
    kad = planet == KADAVO
    zone = np.asarray(Image.open(KAD_ZONES))
    zj = json.load(open(KAD_JSON))
    (pcy, pcx), R = zj["centre"], zj["radius"]
    ys, xs = np.nonzero(kad)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
    sl = np.s_[y0:y1, x0:x1]
    sub, z = kad[sl], zone[sl]
    yy, xx = np.mgrid[0:sub.shape[0], 0:sub.shape[1]].astype(np.float32)
    rim = smoothstep(np.clip((ndi.distance_transform_edt(sub) - 1.5) / 4, 0, 1))
    cen = np.array([v["centre"] for v in zj["provinces"].values()]) - [y0, x0]
    near_unit = np.min([np.hypot(yy - a, xx - b) for a, b in cen], 0) < 2.6
    rough = noise(sub.shape, 5, rng, 3)
    rel = np.full(sub.shape, float(KAD_PLAIN)) + rough * 2
    # the plains: domes of stacked stone blocks with wide crater openings ("Slaves of the Republic"), and pit craters,
    # kept off the unit positions
    plains = z == 1
    free = plains & (ndi.distance_transform_edt(plains) > 1.5)
    unit_d = np.min([np.hypot(yy - a, xx - b) for a, b in cen], 0)
    cones = np.zeros(sub.shape, np.float32)
    cand = np.argwhere(free)
    for r, c in cand[rng.random(len(cand)) < KAD_CONES[0]]:
        rad = KAD_CONES[1][0] + (KAD_CONES[1][1] - KAD_CONES[1][0]) * rng.random() ** 2   # many small, a few wide
        hgt = rng.uniform(*KAD_CONES[2]) * (0.6 + 0.4 * rad / KAD_CONES[1][1])
        if unit_d[r, c] < 1.2:                                             # a unit may stand in a crater, not on its rim
            continue
        d = np.hypot(yy - r, xx - c) / rad
        # a real impact/collapse crater: a bowl below the plain, a raised rim, an apron sloping away outside
        bowl = -min(KAD_PLAIN - 2, 0.9 * rad + 1) * np.clip(1 - d ** 2, 0, 1)
        rimz = hgt * (0.6 + 0.25 * rad) * np.exp(-((d - 1.0) / 0.28) ** 2)
        apron = hgt * 0.35 * np.clip(1.9 - d, 0, 0.9) * (d > 1)
        crat = bowl + rimz + apron
        cones = np.where(np.abs(crat) > np.abs(cones), crat, cones)
    for r, c in cand[rng.random(len(cand)) < KAD_PITS[0]]:
        rad = rng.uniform(*KAD_PITS[1])
        d = np.hypot(yy - r, xx - c) / rad
        cones += np.where(d < 1, -KAD_PITS[2] * (1 - d ** 2), 1.5 * np.clip(1 - abs(d - 1.15) / 0.3, 0, 1))
    rel = np.where(plains, np.maximum(rel + cones, 2), rel)
    # the great volcanoes: a cone round each one's main shape, a summit crater; their flows a low rough sheet
    vol = z == 4
    vh = np.zeros(sub.shape, np.float32)
    for name, kind, sid, n, shapes in km.FEATURES:
        if kind != "volcano":
            continue
        _, u, v, ru, rv, deg = shapes[0]
        cy, cx = pcy + v * R - y0, pcx + u * R - x0
        d = np.hypot((yy - cy) / (rv * R), (xx - cx) / (ru * R))
        ang = np.arctan2(yy - cy, xx - cx)                                 # gullies running down the flanks
        gully = 1 - np.abs(np.sin(ang * rng.integers(9, 14) + 3 * rough)) ** 0.6
        cone = KAD_VOLCANO[0] * np.clip(1 - d, 0, 1) ** 1.4 * (0.82 + 0.25 * rough) * (1 - 0.22 * gully * np.clip(d * 2, 0, 1))
        cone -= KAD_VOLCANO[0] * 0.35 * smoothstep(np.clip(1 - d / KAD_VOLCANO[1], 0, 1))
        vh = np.maximum(vh, cone)
    rel = np.where(vol, KAD_PLAIN + KAD_FLOW * (0.6 + 0.8 * noise(sub.shape, 3, rng, 2)) + vh, rel)
    # the great dome: its flank (the facility's decks, and the causeways where they run over it) rises smoothly from
    # the plains to the crater's rim; inside the rim (the crater's hull) is the bowl
    from skimage.morphology import convex_hull_image
    hull = convex_hull_image(z == 3)
    fac = (z == 2) | ((z == 7) & ~hull)
    inbowl = (z == 3) | ((z == 7) & hull)
    out_d, in_d = ndi.distance_transform_edt(fac | inbowl), ndi.distance_transform_edt(~inbowl)
    k = np.clip(out_d / np.maximum(out_d + in_d, 1e-3), 0, 1)              # 0 at the dome's foot, 1 at the rim
    rel = np.where(fac, KAD_PLAIN + (KAD_DECK - KAD_PLAIN) * (1 - (1 - k) ** 1.8), rel)
    # the crater: a deep U-shaped bowl from the rim down (the user's side-view sketch), the prison's ground and links at
    # its bottom under the hub that hangs over it (military_buildings.py kadavo_facility); lava only in the deepest parts
    bowl = inbowl
    bd = ndi.gaussian_filter(ndi.distance_transform_edt(bowl), 1.0)
    kb = np.clip(bd / max(bd.max() * 0.55, 1e-3), 0, 1)
    rel = np.where(bowl, KAD_DECK - (KAD_DECK - KAD_FLOOR) * np.sqrt(np.clip(1 - (1 - kb) ** 2, 0, 1)), rel)
    rel = np.where((z == 7) & hull, np.minimum(rel, KAD_FLOOR + 1), rel)
    cra = z == 3
    cin = kb * 3
    # the landing field: level pads; the ore pits: terraces stepping down into the ground
    rel = np.where(z == 5, KAD_PAD, rel)
    mine = z == 6
    step = np.clip(np.floor(ndi.distance_transform_edt(mine) / KAD_PIT_STEPS[1]), 0, KAD_PIT_STEPS[0])
    rel = np.where(mine, KAD_PLAIN - step * (KAD_PLAIN - 1) / KAD_PIT_STEPS[0], rel)
    hn = h.copy()
    rel = landforms(rel, sub)
    hn[sl] = np.where(sub, np.clip(GROUND + rel * rim, 0, 252), h[sl])
    gy, gx = np.gradient(hn[sl])
    slope = np.hypot(gx, gy)
    # terrain.bmp: grey ash and dark scoria, red-brown ore rock in the pits, lava on the crater floor, stone decks
    tz = np.full(sub.shape, -1, np.int16)
    mix = noise(sub.shape, 7, rng, 2)
    tz[sub & plains] = np.where(mix > 0.62, BROWNMTN, ROCK2)[sub & plains]
    tz[sub & vol] = np.where(vh > 8, ROCK2, BROWNMTN)[sub & vol]
    steep = sub & (slope > 6) & (plains | vol)
    tz[steep] = ROCK
    tz[sub & cra] = np.where(kb > 0.3, LAVA, ROCK)[sub & cra]                  # a lava lake over the whole floor
    tz[sub & fac] = ROCK2                                                 # the dome's stone
    tz[sub & (z == 5)] = 25                                               # urban_plaza_25: the landing pads
    tz[sub & (z == 7) & hull] = LAVA                                          # lava under the hanging prison (user)
    tz[sub & (z == 7) & ~hull] = ROCK2                                        # the causeways over the dome
    tz[sub & mine] = 24                                                   # red rock: the Kadavo ore
    t[sl] = np.where(tz >= 0, tz, t[sl]).astype(t.dtype)
    city[kad] = 0                                                         # no towns: the bases are models
    TH, TW = trees.shape
    gi = np.ix_(np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1),
                np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1))
    trees[kad[gi]] = 0
    r = rng.random((TH, TW))
    ok = np.zeros((H, W), bool)
    ok[sl] = sub & ~near_unit & (ndi.distance_transform_edt(sub) > 2) & (slope < 6)
    for zk, props in KAD_PROPS.items():
        cells = ok[gi] & (zone[gi] == zk)
        lo = 0.0
        for idx, share in props:
            trees[cells & (r >= lo) & (r < lo + share)] = idx
            lo += share
    print(f"Kadavo: zones {dict(zip(*np.unique(z[sub], return_counts=True)))}, top {int(hn[sl].max())}")
    return t, trees, city, hn


# ---------------------------------------------------------------- data-driven repaint (TERRAIN_CFG in <planet>_map.py)
# A planet's map script describes its terrain as data; zone_repaint() does the rest. Zones are the map script's KIND
# values (the <planet>_zones.png pixels). Heights are heightmap steps above GROUND; random draws happen in a fixed
# order (rough, then each zone's operator in TERRAIN_CFG order, then the texture mix, then the props), so the same
# config and seed always give the same map.
#   TERRAIN_CFG = dict(
#       seed=85,                     # added to SEED for this planet's generator
#       base=4, rough=4,             # every zone starts at base + rough * noise(cell 5) ("rough", reused by operators)
#       open=(1, 11, 5, 6),          # open ground: where ramps lead down to
#       zones={kind: dict(relief=(operator, ...), tex=..., props=[(trees index, share), ...],
#                         clusters=[(noise cell, threshold, props), ...]), ...},   # clusters: forest patches
#       steep=(texture, slope, kinds),   # rock texture on slopes steeper than slope, in these zones
#       city={kind: style, ...},     # map/cities.txt group per zone (0 elsewhere on the planet)
#       prop_clear=2.6,              # props keep this far (px) from unit positions
#       tint={zone: ((r, g, b), s)}, # optional: blend these zones' colormap colour toward rgb (0..1) by s
#       level=(zone, ...),           # optional: zones the landforms leave level like water (lava seas)
#       colors={zone: (r, g, b)},    # optional: repaint the planet's colormap (its look from afar) from these, shaded
#       hook=None)                   # fn(ctx) -> None: a planet's own extra shaping (ctx: rel, z, sub, rng, rough, ...)
# relief operators:
#   ("rolling", level, amp, cell)            level + amp * noise (cell None: the shared rough noise)
#   ("flat", level)
#   ("ramp_top", top, foot, ramp_px)         a flat top falling to `foot` over ramp_px px towards the open ground
#   ("flank", low, high, inner, gullies)     rises from the open side (low) to the inner zones' rim (high), gullied
#   ("mesa", low, top, edge_px, notch)       sheer sides, flat top; notch = (noise cell, threshold) nicks in the edge
#   ("spires", floor, floor_rough, density, (r0, r1), (h0, h1))   flat-topped pillars on a floor
# tex: a texture (name from this module, e.g. "SAVANNA", or index) or [default, (texture, ">"|"<", threshold), ...]
# over the shared texture mix (noise cell 7); later bands win.
TERRAIN_TEXTURES = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27,
                    28, 29, 30, 31, 32}           # graphical terrain indices of common/terrain/00_terrain.txt
CITY_TEXTURES = {13, 26, 29, 30, 32}                # ... the ones with spawn_city = yes: city models only grow on these
RELIEF_OPS = {"rolling": 4, "flat": 2, "ramp_top": 4, "flank": 5, "mesa": 5, "spires": 6}   # operator -> tuple length


def _tex(v):
    return globals()[v] if isinstance(v, str) else v


def check_terrain_cfg(mod):
    """problems with a planet's TERRAIN_CFG (empty list = fine); nothing is read from the map"""
    cfg, errs = getattr(mod, "TERRAIN_CFG", None), []
    if cfg is None:
        return [f"{mod.__name__}: no TERRAIN_CFG"]
    kinds = set(mod.KIND.values())
    for k, zc in cfg["zones"].items():
        if k not in kinds:
            errs.append(f"zone {k}: not a KIND value of {mod.__name__} ({sorted(kinds)})")
        op = zc.get("relief")
        if op and (op[0] not in RELIEF_OPS or len(op) != RELIEF_OPS[op[0]]):
            errs.append(f"zone {k}: relief {op!r}: unknown operator or wrong arity ({RELIEF_OPS})")
        if op and op[0] == "flank" and not set(op[3]) <= kinds:
            errs.append(f"zone {k}: flank inner zones {op[3]} not all KIND values")
        tex = zc.get("tex")
        for t_ in ([tex] if not isinstance(tex, list) else [tex[0]] + [b[0] for b in tex[1:]]) if tex is not None else []:
            if isinstance(t_, str) and not isinstance(globals().get(t_), int):
                errs.append(f"zone {k}: texture name {t_!r} unknown")
            elif _tex(t_) not in TERRAIN_TEXTURES:
                errs.append(f"zone {k}: texture {t_!r} is not a graphical terrain index")
        for idx, share in zc.get("props", []) + [x for c in zc.get("clusters", []) for x in c[2]]:
            if not (0 < idx < 256 and 0 < share < 1):
                errs.append(f"zone {k}: prop {(idx, share)} out of range")
    groups = len(re.findall(r"^city_group", open(f"{MAP}/cities.txt", encoding="utf-8").read(), re.M))
    for k, style in cfg.get("city", {}).items():
        if k not in kinds or not 0 <= style <= groups:
            errs.append(f"city: zone {k} style {style} (zones {sorted(kinds)}, styles 0..{groups})")
        tex = cfg["zones"].get(k, {}).get("tex")
        texs = {_tex(t_) for t_ in ([tex] if not isinstance(tex, list) else [tex[0]] + [b[0] for b in tex[1:]])} if tex is not None else set()
        if style and not texs & CITY_TEXTURES:          # the city style is painted but no building would spawn
            errs.append(f"city: zone {k} has style {style} but texture {tex!r} has no spawn_city ({sorted(CITY_TEXTURES)})")
    for k, tn in cfg.get("tint", {}).items():
        if k not in kinds or len(tn) != 2 or len(tn[0]) != 3 or not all(0 <= c <= 1 for c in (*tn[0], tn[1])):
            errs.append(f"tint: zone {k} {tn!r} (a KIND value: ((r, g, b) 0..1, strength 0..1))")
    for k, rgb in cfg.get("colors", {}).items():
        if k not in kinds or len(rgb) != 3 or not all(0 <= c <= 1 for c in rgb):
            errs.append(f"colors: zone {k} {rgb!r} (a KIND value: (r, g, b) 0..1)")
    if not set(cfg.get("level", ())) <= kinds:
        errs.append(f"level: zones {cfg['level']} are not all KIND values")
    if not set(cfg.get("open", ())) <= kinds or not set(cfg.get("steep", (0, 0, ()))[2]) <= kinds:
        errs.append("open / steep zones are not all KIND values")
    for path in (mod.ZONES_PNG, mod.ZONES_JSON):
        if not os.path.exists(path):
            errs.append(f"{path} missing: run {mod.__name__}.py first")
    return errs


# landforms(): the broad shape of a planet's ground under its zones' own relief (user, 2026-10-15: "the heightmap is
# underutilised, no hills, no curve; a hill or a mountain is treated as a unique thing"). Heightmap steps (10 = 1 map
# unit); cells in map px (planets are ~120 px across)
LANDFORM = dict(amp=20.0, cell=24,          # uplands and basins over the whole planet
                terrace=0.6, steps=3,       # the uplands broken into steps with escarpments between them
                hills=13.0, hill_cell=9,    # ridged hills (ridgelines, spurs), strongest where hilly (hill_area)
                hill_area=30,               # cell of the field that makes some regions hilly and others gentle
                valleys=9.0, valley_cell=14,   # winding valleys cut into the uplands (never below the base)
                skirt=5.0, skirt_k=0.65,    # foothills: every high zone spreads a skirt this wide (px) and high
                skirt_from=12.0,            # ... high = zones above this (mountains, plateaus): pits and gorges stay open
                shore=3.0)                  # px over which the land rises from seas and rivers


def landforms(rel, sub, water=None, opts=None):
    """rel (steps above GROUND, the zones' own relief) with the planet's landforms added: uplands and basins,
    ridged hills, foothill skirts round every high zone so mountains and plateaus rise out of the land instead of
    standing alone. Water (default: ground sunk below the base, i.e. under the water plane) stays level and the
    land rises from it.
    Only ever raises the ground, so nothing new sinks below the water plane. Deterministic per planet (its own
    random stream: the props and textures drawn after it are unchanged)."""
    o = {**LANDFORM, **(opts or {})}
    if not o.get("amp") and not o.get("hills") and not o.get("skirt_k"):
        return rel
    water = (rel < -0.5) & sub if water is None else water
    lrng = np.random.default_rng(int(sub.sum()) * 7919 + sub.shape[0])
    calm = smoothstep(np.clip(ndi.distance_transform_edt(~water) / max(o["shore"], 1e-3), 0, 1))
    big = noise(sub.shape, o["cell"], lrng, 3)
    q = big * o["steps"]                                                       # terraces: flat steps, steep risers
    stepped = (np.floor(q) + smoothstep(np.clip((q - np.floor(q) - 0.35) / 0.3, 0, 1))) / o["steps"]
    big = big + o["terrace"] * (stepped - big)
    ridge = (1 - np.abs(2 * noise(sub.shape, o["hill_cell"], lrng, 3) - 1)) ** 2
    area = smoothstep(np.clip(noise(sub.shape, o["hill_area"], lrng, 2) * 1.6 - 0.3, 0, 1))
    valley = (1 - np.abs(2 * noise(sub.shape, o["valley_cell"], lrng, 2) - 1)) ** 6   # thin winding lines
    land = np.where(sub & ~water & (rel > o["skirt_from"]), rel, 0).astype(np.float32)
    skirt = ndi.gaussian_filter(land, o["skirt"]) * o["skirt_k"]               # foothills round high zones
    lift = np.maximum(o["amp"] * big + o["hills"] * ridge * area - o["valleys"] * valley, 0)
    out = np.maximum(rel, skirt) + calm * lift
    return np.where(water | ~sub, rel, out).astype(np.float32)

def zone_repaint(mod):
    """repaint_planet() fn for a planet whose map script has a TERRAIN_CFG"""
    cfg = mod.TERRAIN_CFG

    def fn(t, trees, city, h, labels, names, pid, rng, cm=None):
        t, trees, city = t.copy(), trees.copy(), city.copy()
        H, W = labels.shape
        planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
        on = planet == mod.PLANET
        zone = np.asarray(Image.open(mod.ZONES_PNG))
        zj = json.load(open(mod.ZONES_JSON))
        ys, xs = np.nonzero(on)
        y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
        sl = np.s_[y0:y1, x0:x1]
        sub, z = on[sl], zone[sl]
        yy, xx = np.mgrid[0:sub.shape[0], 0:sub.shape[1]].astype(np.float32)
        rim = smoothstep(np.clip((ndi.distance_transform_edt(sub) - 1.5) / 4, 0, 1))
        cen = np.array([v["centre"] for v in zj["provinces"].values()]) - [y0, x0]
        unit_d = np.min([np.hypot(yy - a, xx - b) for a, b in cen], 0)
        rough = noise(sub.shape, 5, rng, 3)
        rel = (cfg["base"] + cfg["rough"] * rough).astype(np.float32)
        open_ = sub & np.isin(z, cfg["open"])
        d_open = ndi.distance_transform_edt(~open_)                       # px to the nearest open ground
        for k, zc in cfg["zones"].items():
            op, m = zc.get("relief"), z == k
            if not op:
                continue
            if op[0] == "rolling":
                rel = np.where(m, op[1] + op[2] * (rough if op[3] is None else noise(sub.shape, op[3], rng, 3)), rel)
            elif op[0] == "flat":
                rel = np.where(m, op[1], rel)
            elif op[0] == "ramp_top":
                rel = np.where(m, op[2] + (op[1] - op[2]) * smoothstep(np.clip(d_open / op[3], 0, 1)), rel)
            elif op[0] == "flank":
                din, dout = ndi.distance_transform_edt(~np.isin(z, op[3])), ndi.distance_transform_edt(m)
                kk = np.clip(dout / np.maximum(dout + din, 1e-3), 0, 1)     # 0 at the foot, 1 at the rim
                gully = 1 - np.abs(np.sin(np.arctan2(yy - yy[m].mean(), xx - xx[m].mean()) * op[4] + 3 * rough)) ** 0.5
                rel = np.where(m, op[1] + (op[2] - op[1]) * np.clip(kk * 1.35, 0, 1) ** 0.55 * (1 - 0.15 * gully * (1 - kk)), rel)
            elif op[0] == "mesa":
                dm = ndi.distance_transform_edt(m)
                notch = noise(sub.shape, op[4][0], rng, 2) > op[4][1]
                rel = np.where(m, op[1] + (op[2] - op[1]) * smoothstep(np.clip((dm - 0.5 * notch) / op[3], 0, 1)), rel)
            elif op[0] == "spires":
                pf = np.full(sub.shape, op[1] + op[2] * rough, np.float32)
                cand = np.argwhere(m & (ndi.distance_transform_edt(m) > 1))
                for r, c in cand[rng.random(len(cand)) < op[3]]:
                    rad = rng.uniform(*op[4])
                    d = np.hypot(yy - r, xx - c) / rad
                    pf = np.maximum(pf, op[1] + rng.uniform(*op[5]) * np.clip(1 - d ** 6, 0, 1))
                rel = np.where(m, pf, rel)
        ctx = dict(rel=rel, z=z, sub=sub, rng=rng, rough=rough, yy=yy, xx=xx, unit_d=unit_d, zj=zj, sl=sl)
        wet = [k for k, zc in cfg["zones"].items() if zc.get("tex") is not None and _tex(
            zc["tex"] if not isinstance(zc["tex"], list) else zc["tex"][0]) == WATER]   # seas, rivers: kept level
        wet += list(cfg.get("level", ()))                                    # lava seas etc.: kept level too
        if cfg.get("hook"):
            cfg["hook"](ctx)                                               # a planet's own shaping, in place on ctx["rel"]
            rel = ctx["rel"]
        hn = h.copy()
        rel = landforms(rel, sub, water=np.isin(z, wet) & sub, opts=cfg.get("landforms"))
        hn[sl] = np.where(sub, np.clip(GROUND + rel * rim, 0, 252), h[sl])
        gy, gx = np.gradient(hn[sl])
        slope = np.hypot(gx, gy)
        tz = np.full(sub.shape, -1, np.int16)
        mix = noise(sub.shape, 7, rng, 2)
        for k, zc in cfg["zones"].items():
            tex = zc.get("tex")
            if tex is None:
                continue
            m = sub & (z == k)
            if not isinstance(tex, list):
                tz[m] = _tex(tex)
                continue
            v = np.full(sub.shape, _tex(tex[0]), np.int16)
            for band in tex[1:]:
                v = np.where(mix > band[2] if band[1] == ">" else mix < band[2], _tex(band[0]), v)
            tz[m] = v[m]
        if cfg.get("steep"):
            st_tex, st_slope, st_zones = cfg["steep"]
            tz[sub & (slope > st_slope) & np.isin(z, st_zones)] = _tex(st_tex)
        if cfg.get("shore_rise"):
            # the seas are painted water at ground level (the water plane draws space): every pixel whose final
            # texture is not water climbs `height` steps within `width` px of the nearest water pixel, so shores,
            # islands and atolls stand up out of the sea as cliffs instead of lying flush with it
            rise_h, rise_w = cfg["shore_rise"]
            sea = sub & np.isin(tz, [WATER, 30])                            # marsh water, sea_town_30
            if sea.any():
                d_sea = ndi.distance_transform_edt(~sea)
                lift = rise_h * smoothstep(np.clip((d_sea - 0.5) / rise_w, 0, 1))
                hn[sl] = np.where(sub & ~sea, np.clip(hn[sl] + lift * rim, 0, 252), hn[sl])
        t[sl] = np.where(tz >= 0, tz, t[sl]).astype(t.dtype)
        city[on] = 0
        for k, style in cfg.get("city", {}).items():
            city[sl] = np.where(sub & (z == k), style, city[sl])
        TH, TW = trees.shape
        gi = np.ix_(np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1),
                    np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1))
        trees[on[gi]] = 0
        r = rng.random((TH, TW))
        ok = np.zeros((H, W), bool)
        ok[sl] = sub & (unit_d >= cfg.get("prop_clear", 2.6)) & (ndi.distance_transform_edt(sub) > 2) & (slope < 6)
        for k, zc in cfg["zones"].items():
            cells = ok[gi] & (zone[gi] == k)
            lo = 0.0
            for idx, share in zc.get("props", []):
                trees[cells & (r >= lo) & (r < lo + share)] = idx
                lo += share
        for k, zc in cfg["zones"].items():                                 # forest patches: drawn last, only if used
            for cell, thr, props in zc.get("clusters", []):
                patch = np.zeros((H, W), bool)
                patch[sl] = noise(sub.shape, cell, rng, 3) > thr
                cells = ok[gi] & (zone[gi] == k) & patch[gi]
                lo = 0.0
                for idx, share in props:
                    trees[cells & (r >= lo) & (r < lo + share)] = idx
                    lo += share
        print(f"{mod.PLANET}: zones {dict(zip(*np.unique(z[sub], return_counts=True)))}, top {int(hn[sl].max())}")
        if cm is None:
            return t, trees, city, hn
        # shortcut: the tint blends into the current colormap, so each re-run pushes those zones further toward rgb
        # (converges, but not idempotent); keep a copy of the colormap from before the first run if that matters
        cm = cm.copy()                                                     # tint={zone: ((r, g, b) 0..1, strength)}
        if cfg.get("colors"):                                              # colors={zone: (r, g, b)}: the far look
            crng = np.random.default_rng(int(sub.sum()) * 31 + 7)
            col = np.zeros(sub.shape + (3,), np.float32)
            for k, rgb in cfg["colors"].items():
                col[sub & (z == k)] = rgb
            w = ndi.gaussian_filter(sub.astype(np.float32), 1.2)
            col = np.stack([ndi.gaussian_filter(col[..., c], 1.2) for c in range(3)], -1) / np.maximum(w, 1e-3)[..., None]
            gy, gx = np.gradient(ndi.gaussian_filter(hn[sl], 1.0))
            shade = np.clip(1 + 0.035 * (gx - gy), 0.72, 1.22)              # lit from the north-west, as the relief
            col *= (shade * (0.9 + 0.2 * noise(sub.shape, 6, crng, 3)))[..., None]
            y0, x0 = sl[0].start, sl[1].start
            hy = np.arange((y0 + 1) // 2, (sl[0].stop + 1) // 2)              # half-res rows / cols inside the box
            hx = np.arange((x0 + 1) // 2, (sl[1].stop + 1) // 2)
            hy, hx = hy[(2 * hy - y0) < sub.shape[0]], hx[(2 * hx - x0) < sub.shape[1]]
            yy_, xx_ = np.meshgrid(2 * hy - y0, 2 * hx - x0, indexing="ij")
            on_ = sub[yy_, xx_]
            hy_, hx_ = np.meshgrid(hy, hx, indexing="ij")
            cm[hy_[on_], hx_[on_], :3] = np.clip(col[yy_[on_], xx_[on_]], 0, 1)
        zh = np.zeros(labels.shape, np.uint8)
        zh[sl] = np.where(sub, z, 0)
        zh = zh[::2, ::2][:cm.shape[0], :cm.shape[1]]                       # the colormap is half resolution
        for k, (rgb, st) in cfg.get("tint", {}).items():
            m = ndi.gaussian_filter((zh == k).astype(np.float32), 0.8)[..., None] * st
            cm[..., :3] = cm[..., :3] * (1 - m) + np.array(rgb, np.float32) * m
        return t, trees, city, hn, cm
    return fn


def planet_module(name):
    """the map script module of a planet ('Zygerria', 'Raxus Prime' -> zygerria_map, raxus_prime_map)"""
    import importlib
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    return importlib.import_module(name.lower().replace(" ", "_") + "_map")


def repaint_planet(fn, planet, seed, with_cm=False):
    """Run one planet's repaint fn(t, trees, city, h, labels, names, pid, rng) -> (t, trees, city, h) and write
    heightmap.bmp, world_normal.bmp (around that planet only), terrain/trees/cities.bmp and the re-snapped positions.
    The colormap is not touched."""
    land, _, pid = load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = planet_names(labels, n, pid)
    tr, terr, cty = load(f"{MAP}/trees.bmp"), load(f"{MAP}/terrain.bmp"), load(f"{MAP}/cities.bmp")
    h0 = np.asarray(load(f"{MAP}/heightmap.bmp").convert("L")).astype(np.float32)
    cmp = f"{MAP}/terrain/colormap_rgb_cityemissivemask_a.dds"
    if with_cm:                                                            # the planet repaints its colours too
        cm = np.array(load(cmp).convert("RGBA")).astype(np.float32) / 255
        t, trees, city, h, cm = fn(np.array(terr), np.array(tr), np.array(cty), h0, labels, names, pid,
                                   np.random.default_rng(seed), cm)
        save_bgra_dds(cmp, np.rint(np.clip(cm, 0, 1) * 255).astype(np.uint8), cmp)
    else:
        t, trees, city, h = fn(np.array(terr), np.array(tr), np.array(cty), h0, labels, names, pid, np.random.default_rng(seed))
    mask = np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == planet])
    Image.fromarray(np.rint(h).astype(np.uint8), "L").save(f"{MAP}/heightmap.bmp")
    gy, gx = np.gradient(ndi.gaussian_filter(h, 1.0)[::2, ::2])
    nv = np.stack([-NORMAL_K * gx, NORMAL_K * gy, np.ones_like(gx)], -1)
    nv /= np.linalg.norm(nv, axis=-1, keepdims=True)
    wn = np.array(load(f"{MAP}/world_normal.bmp").convert("RGB"))
    ys, xs = np.nonzero(mask[::2, ::2][:wn.shape[0], :wn.shape[1]])
    sl = np.s_[max(ys.min() - 4, 0):ys.max() + 5, max(xs.min() - 4, 0):xs.max() + 5]
    wn[sl] = np.clip(np.rint(nv[sl] * 127.5 + 127.5), 0, 255).astype(np.uint8)
    Image.fromarray(wn, "RGB").save(f"{MAP}/world_normal.bmp")
    reheight(np.rint(h))
    for arr, img, path in ((t, terr, "terrain.bmp"), (trees, tr, "trees.bmp"), (city, cty, "cities.bmp")):
        out = Image.fromarray(arr.astype(np.uint8), "P")
        out.putpalette(img.getpalette())
        out.save(f"{MAP}/{path}")

def world_styles(cmap, labels, names):
    """Ocean worlds, Mandalore and Geonosis get their own city style wherever the map has buildings (0 stays 0)."""
    planet = np.array([""] + [names[l].split(" - ")[0] for l in range(1, labels.max() + 1)])[labels]
    for style, worlds in STYLE_WORLDS.items():
        cmap = np.where(np.isin(planet, list(worlds)) & (cmap > 0), style, cmap)
    return cmap.astype(np.uint8)


GLOBE_SIZE = 4096             # globe texture is GLOBE_SIZE square: the engine refuses textures over MAX_TEXTURE_SIZE
                              # (6144 failed, error.log); the shader samples it by map uv, so it needn't match the map shape
TILE_PERIOD = 3328 / 228.0    # map px per terrain tile repeat (pdxmap.shader: uv2 * TERRAIN_TILE_FREQ, x scaled by W/H)
GLOBE_DETAIL = 0.6            # how much of the terrain tiles' light/dark pattern goes onto the painted colours
# Raxus, Raxus Prime, Korriban: the zoomed-out globe keeps the original painting and terrain pattern (the user prefers it)
GLOBE_TERRAIN_KEEP = [("WIPGFX/Assets/raxus_globe_terrain.png", "WIPGFX/Assets/raxus_globe_terrain.json"),
                      ("WIPGFX/Assets/raxus_prime_globe_terrain.png", "WIPGFX/Assets/raxus_prime_globe_terrain.json"),
                      ("WIPGFX/Assets/korriban_globe_terrain.png", "WIPGFX/Assets/korriban_globe_terrain.json")]


def save_dxt1_mips(rgb, path):
    """DXT1 DDS with a full mip chain (as flora_props.save_dxt5_mips, without alpha: half the size)."""
    import struct
    levels, im = [], Image.fromarray(np.asarray(rgb, np.uint8), "RGB")
    while True:
        buf = io.BytesIO()
        im.save(buf, format="DDS", pixel_format="DXT1")
        levels.append(buf.getvalue())
        if im.size == (1, 1):
            break
        im = im.resize((max(1, im.size[0] // 2), max(1, im.size[1] // 2)), Image.BOX)
    hdr = bytearray(levels[0][:128])
    struct.pack_into("<I", hdr, 8, struct.unpack_from("<I", hdr, 8)[0] | 0x20000)
    struct.pack_into("<I", hdr, 28, len(levels))
    struct.pack_into("<I", hdr, 108, struct.unpack_from("<I", hdr, 108)[0] | 0x400008)
    with open(path, "wb") as f:
        f.write(bytes(hdr) + b"".join(l[128:] for l in levels))


def globe_texture():
    """map/terrain/mud_diffuse_rgb_gloss_a_{0,1,2}.dds: painted planet colours (written colormap, Lanczos upscaled)
    times the luminance pattern of the terrain tile under each pixel, at the scale the close-up terrain uses."""
    cmap = np.array(load(f"{MAP}/terrain/colormap_rgb_cityemissivemask_a.dds").convert("RGB"))
    terr = np.array(load(f"{MAP}/terrain.bmp"))
    H, W = terr.shape
    for path, at in GLOBE_TERRAIN_KEEP:            # planets repainted up close whose old globe look is kept
        keep = np.array(Image.open(path))
        y0, x0 = json.load(open(at))["at"]
        terr[y0:y0 + keep.shape[0], x0:x0 + keep.shape[1]] = keep
    GH = GW = GLOBE_SIZE
    slot_of = {int(m.group(1)): int(m.group(2)) for m in re.finditer(
        r"color\s*=\s*\{\s*(\d+)\s*\}\s*texture\s*=\s*(\d+)",
        open("common/terrain/00_terrain.txt", encoding="utf-8").read().split("\nterrain = {", 1)[1])}
    atlas = np.array(load(f"{MAP}/terrain/atlas0.dds").convert("RGB")).astype(np.float32)
    T = atlas.shape[0] // 5
    PX, PY = int(round(TILE_PERIOD * GW / W)), int(round(TILE_PERIOD * GH / H))   # tile repeat in globe px per axis
    detail = np.ones((25, PY, PX), np.float32)
    for slot in range(25):                         # each tile's light/dark pattern at its on-map size, mean 1
        r, c = divmod(slot, 5)
        tile = Image.fromarray(atlas[r * T:(r + 1) * T, c * T:(c + 1) * T].mean(-1).astype(np.uint8)).resize((PX, PY), Image.LANCZOS)
        d = np.asarray(tile, np.float32)
        detail[slot] = np.clip(d / max(d.mean(), 1.0), 0.5, 1.6)
    slot_lut = np.zeros(256, np.int32)
    for idx, sl in slot_of.items():
        slot_lut[idx] = sl
    paint = Image.fromarray(cmap).resize((GW, GH), Image.LANCZOS)
    out = np.empty((GH, GW, 3), np.uint8)
    for y0 in range(0, GH, 512):                   # strips: the full float image would not fit comfortably
        y1 = min(GH, y0 + 512)
        rgb = np.asarray(paint.crop((0, y0, GW, y1)), np.float32)
        yy, xx = np.mgrid[y0:y1, 0:GW]
        slot = slot_lut[terr[yy * H // GH, xx * W // GW]]
        d = detail[slot, yy % PY, xx % PX]
        out[y0:y1] = np.clip(rgb * (1 + GLOBE_DETAIL * (d[..., None] - 1)), 0, 255).astype(np.uint8)
    for lvl in range(3):                           # every quality level gets the full texture
        save_dxt1_mips(out, f"{MAP}/terrain/mud_diffuse_rgb_gloss_a_{lvl}.dds")
    print(f"globe texture {GW}x{GH} written to the mud slot")


SEA_H, COAST_H, LAND_H = 85, 95, 97   # heightmap: space floor, water level (9.5), rim land
COAST_SLOPE = 6.0                     # heightmap steps per px across the rim: the water line lands at sub-pixel precision


def round_coasts(h, land, labels):
    """Circular, anti-aliased coastline for every round land body: the province map coast is a 1 px staircase
    (97 -> 85), and the water line at 95 follows it, so zoomed-out planets look pixelated. A steep ramp centred on
    the body's true circle (radius from its area) puts the water line on the circle. Idempotent."""
    h = h.astype(np.float32).copy()
    H, W = h.shape
    for lab, sl in enumerate(ndi.find_objects(labels), 1):
        if sl is None:
            continue
        m = labels[sl] == lab
        ys, xs = np.nonzero(m)
        cy, cx = ys.mean() + sl[0].start, xs.mean() + sl[1].start
        R = np.sqrt(m.sum() / np.pi)
        if m.sum() < 200 or m.sum() < 0.8 * np.pi * np.hypot(ys - ys.mean(), xs - xs.mean()).max() ** 2:
            continue                                                   # not a round planet: leave it
        y0, y1 = max(0, int(cy - R - 4)), min(H, int(cy + R + 5))
        x0, x1 = max(0, int(cx - R - 4)), min(W, int(cx + R + 5))
        yy, xx = np.mgrid[y0:y1, x0:x1]
        ramp = COAST_H + (R - np.hypot(yy + 0.5 - (cy + 0.5), xx + 0.5 - (cx + 0.5))) * COAST_SLOPE
        sub, own = h[y0:y1, x0:x1], (labels[y0:y1, x0:x1] == lab)
        near = ramp > SEA_H - COAST_SLOPE                                # only the rim band and the inside
        sea = ~land[y0:y1, x0:x1] & near
        sub[own] = np.minimum(sub[own], np.maximum(ramp[own], SEA_H))   # land past the circle sinks below water
        sub[sea] = np.clip(ramp[sea], SEA_H, LAND_H)                    # space inside the circle rises above it
    return h


CITY_BORDER_GAP = 0   # extra map px cleared past the 2 px border street; megacity provinces are only ~7x7 px


def carve_city_borders(cmap, pid):
    """Style 0 (no buildings, map/cities.txt) on both pixels of every province border, so borders stay readable in
    planet-wide cities. Buildings next to the street become the low outskirts ones (cities.txt sorts by urban edge)."""
    edge = np.zeros(pid.shape, bool)
    d = pid[:, 1:] != pid[:, :-1]
    edge[:, 1:] |= d
    edge[:, :-1] |= d
    d = pid[1:, :] != pid[:-1, :]
    edge[1:, :] |= d
    edge[:-1, :] |= d
    if CITY_BORDER_GAP:
        edge = ndi.binary_dilation(edge, iterations=CITY_BORDER_GAP)
    return np.where(edge, 0, cmap).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="write preview PNGs to this dir")
    ap.add_argument("--write", action="store_true", help="overwrite the map files listed in the docstring")
    ap.add_argument("--reheight", action="store_true", help="only re-snap buildings.txt/unitstacks.txt to heightmap.bmp")
    ap.add_argument("--carve-cities", action="store_true", help="only clear map/cities.bmp along province borders")
    ap.add_argument("--city-styles", action="store_true", help="only reapply per-world city styles (cities.bmp)")
    ap.add_argument("--globe-texture", action="store_true", help="only rebake the sharp globe texture (mud slot)")
    ap.add_argument("--round-coasts", action="store_true", help="only round the planet coastlines in heightmap.bmp")
    ap.add_argument("--world-tweaks", action="store_true", help="only apply CITY_DISTRICTS, RED_WORLDS, DENSE_TREE_WORLDS")
    ap.add_argument("--felucia", action="store_true", help="only repaint Felucia (flora, ground, atmosphere); then --globe-texture")
    ap.add_argument("--raxus", action="store_true", help="only repaint Raxus (capital, countryside); then --globe-texture")
    ap.add_argument("--raxus-prime", action="store_true", help="only repaint Raxus Prime (junk world); then --globe-texture")
    ap.add_argument("--korriban", action="store_true", help="only repaint Korriban (valleys, tombs, spires); then --globe-texture")
    ap.add_argument("--kadavo", action="store_true", help="only repaint Kadavo (ash plains, volcanoes, crater); then --globe-texture")
    ap.add_argument("--planet", help="only repaint this planet from its map script's TERRAIN_CFG; then --globe-texture")
    ap.add_argument("--zygerria", action="store_true", help="same as --planet Zygerria")
    ap.add_argument("--florrum", action="store_true", help="only repaint Florrum (sulfur desert, shelves, canyon); then --globe-texture")
    a = ap.parse_args()
    if a.raxus_prime:
        return repaint_planet(raxus_prime, RP, SEED + 196)
    if a.korriban:
        return repaint_planet(korriban, KORRIBAN, SEED + 90)
    if a.kadavo:
        return repaint_planet(kadavo, KADAVO, SEED + 83)
    if a.zygerria or a.planet:
        mod = planet_module(a.planet or "Zygerria")
        errs = check_terrain_cfg(mod)
        if errs:                                                           # nothing written
            sys.exit(f"{mod.__name__}.TERRAIN_CFG:\n  " + "\n  ".join(errs))
        return repaint_planet(zone_repaint(mod), mod.PLANET, SEED + mod.TERRAIN_CFG["seed"],
                              with_cm=bool(mod.TERRAIN_CFG.get("tint") or mod.TERRAIN_CFG.get("colors")))
    if a.florrum:
        return repaint_planet(florrum, FLORRUM, SEED + 192, with_cm=True)
    if a.raxus:
        land, _, pid = load_provinces()
        labels, n = ndi.label(land, np.ones((3, 3)))
        names = planet_names(labels, n, pid)
        tr, terr, cty = load(f"{MAP}/trees.bmp"), load(f"{MAP}/terrain.bmp"), load(f"{MAP}/cities.bmp")
        cmp = f"{MAP}/terrain/colormap_rgb_cityemissivemask_a.dds"
        cm = np.array(load(cmp).convert("RGBA")).astype(np.float32) / 255
        h0 = np.asarray(load(f"{MAP}/heightmap.bmp").convert("L")).astype(np.float32)
        t, trees, cm, city, h = raxus(np.array(terr), np.array(tr), cm, np.array(cty), h0, labels, names, pid,
                                      np.random.default_rng(SEED + 79))
        rax = np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == RAXUS])
        Image.fromarray(np.rint(h).astype(np.uint8), "L").save(f"{MAP}/heightmap.bmp")
        # world_normal.bmp (half res) redone around Raxus only
        gy, gx = np.gradient(ndi.gaussian_filter(h, 1.0)[::2, ::2])
        nv = np.stack([-NORMAL_K * gx, NORMAL_K * gy, np.ones_like(gx)], -1)
        nv /= np.linalg.norm(nv, axis=-1, keepdims=True)
        wn = np.array(load(f"{MAP}/world_normal.bmp").convert("RGB"))
        ys, xs = np.nonzero(rax[::2, ::2][:wn.shape[0], :wn.shape[1]])
        sl = np.s_[max(ys.min() - 4, 0):ys.max() + 5, max(xs.min() - 4, 0):xs.max() + 5]
        wn[sl] = np.clip(np.rint(nv[sl] * 127.5 + 127.5), 0, 255).astype(np.uint8)
        Image.fromarray(wn, "RGB").save(f"{MAP}/world_normal.bmp")
        reheight(np.rint(h))
        for arr, img, path in ((t, terr, "terrain.bmp"), (trees, tr, "trees.bmp"), (city, cty, "cities.bmp")):
            out = Image.fromarray(arr.astype(np.uint8), "P")
            out.putpalette(img.getpalette())
            out.save(f"{MAP}/{path}")
        return save_bgra_dds(cmp, np.rint(np.clip(cm, 0, 1) * 255).astype(np.uint8), cmp)
    if a.felucia:
        land, _, pid = load_provinces()
        labels, n = ndi.label(land, np.ones((3, 3)))
        names = planet_names(labels, n, pid)
        tr, terr, cty = load(f"{MAP}/trees.bmp"), load(f"{MAP}/terrain.bmp"), load(f"{MAP}/cities.bmp")
        cmp = f"{MAP}/terrain/colormap_rgb_cityemissivemask_a.dds"
        cm = np.array(load(cmp).convert("RGBA")).astype(np.float32) / 255
        wps = [f"{MAP}/terrain/colormap_water_{lvl}.dds" for lvl in range(3)]
        water = [np.array(load(w).convert("RGBA")).astype(np.float32) / 255 for w in wps]
        h0 = np.asarray(load(f"{MAP}/heightmap.bmp").convert("L")).astype(np.float32)
        t, trees, cm, water, city, h, kar = felucia(np.array(terr), np.array(tr), cm, water, np.array(cty), h0, labels,
                                                    names, pid, np.random.default_rng(SEED + 58))
        fel = np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == FELUCIA])
        # gameplay terrain (definition.csv) now comes from the zones: felucia_map.py
        Image.fromarray(np.rint(h).astype(np.uint8), "L").save(f"{MAP}/heightmap.bmp")
        # world_normal.bmp (half res) redone around Felucia only: elsewhere it stays as --write made it
        gy, gx = np.gradient(ndi.gaussian_filter(h, 1.0)[::2, ::2])
        nv = np.stack([-NORMAL_K * gx, NORMAL_K * gy, np.ones_like(gx)], -1)
        nv /= np.linalg.norm(nv, axis=-1, keepdims=True)
        wn = np.array(load(f"{MAP}/world_normal.bmp").convert("RGB"))
        ys, xs = np.nonzero(fel[::2, ::2][:wn.shape[0], :wn.shape[1]])
        sl = np.s_[max(ys.min() - 4, 0):ys.max() + 5, max(xs.min() - 4, 0):xs.max() + 5]
        wn[sl] = np.clip(np.rint(nv[sl] * 127.5 + 127.5), 0, 255).astype(np.uint8)
        Image.fromarray(wn, "RGB").save(f"{MAP}/world_normal.bmp")
        reheight(np.rint(h))
        for arr, img, path in ((t, terr, "terrain.bmp"), (trees, tr, "trees.bmp"), (city, cty, "cities.bmp")):
            out = Image.fromarray(arr.astype(np.uint8), "P")
            out.putpalette(img.getpalette())
            out.save(f"{MAP}/{path}")
        for w, path in zip(water, wps):
            save_bgra_dds(path, np.rint(np.clip(w, 0, 1) * 255).astype(np.uint8), path)
        return save_bgra_dds(cmp, np.rint(np.clip(cm, 0, 1) * 255).astype(np.uint8), cmp)
    if a.globe_texture:
        return globe_texture()
    if a.round_coasts:
        land, _, pid = load_provinces()
        labels, n = ndi.label(land, np.ones((3, 3)))
        hm = round_coasts(np.asarray(load(f"{MAP}/heightmap.bmp").convert("L")), land, labels)
        Image.fromarray(np.rint(hm).astype(np.uint8), "L").save(f"{MAP}/heightmap.bmp")
        return reheight(np.rint(hm))
    if a.world_tweaks:
        land, _, pid = load_provinces()
        labels, n = ndi.label(land, np.ones((3, 3)))
        names = planet_names(labels, n, pid)
        terr, city, tr = load(f"{MAP}/terrain.bmp"), load(f"{MAP}/cities.bmp"), load(f"{MAP}/trees.bmp")
        cmp = f"{MAP}/terrain/colormap_rgb_cityemissivemask_a.dds"
        cm = np.array(load(cmp).convert("RGBA")).astype(np.float32) / 255
        t, cmap, trees, cm = world_tweaks(np.array(terr), np.array(city), np.array(tr), cm, labels, names, pid,
                                          np.random.default_rng(SEED))
        for arr, img, path in ((t, terr, "terrain.bmp"), (cmap, city, "cities.bmp"), (trees, tr, "trees.bmp")):
            out = Image.fromarray(arr.astype(np.uint8), "P")
            out.putpalette(img.getpalette())
            out.save(f"{MAP}/{path}")
        return save_bgra_dds(cmp, np.rint(np.clip(cm, 0, 1) * 255).astype(np.uint8), cmp)
    if a.city_styles:
        land, _, pid = load_provinces()
        labels, n = ndi.label(land, np.ones((3, 3)))
        names = planet_names(labels, n, pid)
        city = load(f"{MAP}/cities.bmp")
        cb = Image.fromarray(world_styles(np.array(city), labels, names), "P")
        cb.putpalette(city.getpalette())
        cb.save(f"{MAP}/cities.bmp")
        return
    if a.carve_cities:
        city = load(f"{MAP}/cities.bmp")
        cb = Image.fromarray(carve_city_borders(np.array(city), load_provinces()[2]), "P")
        cb.putpalette(city.getpalette())
        return cb.save(f"{MAP}/cities.bmp")
    if a.reheight:
        return reheight(np.asarray(load(f"{MAP}/heightmap.bmp").convert("L"), float))
    rng = np.random.default_rng(SEED)

    palette = load(f"{BASE}/terrain.bmp").getpalette()
    land, cls, pid = load_provinces()
    H, W = shape = land.shape
    labels, n = ndi.label(land, np.ones((3, 3)))
    radius = np.sqrt(np.bincount(labels.ravel()) / np.pi)
    objs = ndi.find_objects(labels)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # --- archetype per world: canon name first, painted colour as fallback
    cm_half = np.array(load(f"{BASE}/colormap_rgb_cityemissivemask_a.dds").convert("RGBA")).astype(np.float32) / 255
    land_h, lab_h = land[::2, ::2], labels[::2, ::2]
    cm_flat = deshade(cm_half, land_h, lab_h, n)
    planet_rgb = np.stack([per_label(lab_h, n, cm_flat[..., c] * land_h) for c in range(3)], -1)
    names = planet_names(labels, n, pid)
    mixes = {lab: planet_mix(names[lab]) or ("noise", [(fallback_archetype(planet_rgb[lab]), 1.0)]) for lab in range(1, n + 1)}
    arch = {lab: mixes[lab][1][0][0] for lab in mixes}     # dominant biome (atmosphere colour)
    print(f"{n} worlds, biome zones:", dict(collections.Counter(k for _, mix in mixes.values() for k, _ in mix)))
    print("from painted colour:", [names[l] for l in mixes if planet_mix(names[l]) is None])

    # gameplay terrain, edges noise-warped so features aren't province-shaped
    sy = np.clip(np.rint(yy + (noise(shape, 64, rng, 3) - 0.5) * 22), 0, H - 1).astype(np.int32)
    sx = np.clip(np.rint(xx + (noise(shape, 64, rng, 3) - 0.5) * 22), 0, W - 1).astype(np.int32)
    gcls = np.where(labels[sy, sx] == labels, cls[sy, sx], cls)
    C = {name: (gcls == i) & land for i, name in enumerate(CLASSES)}

    # --- shared noise fields
    big = noise(shape, 110, rng, 4)          # continents / basins
    mid = noise(shape, 45, rng, 4)
    mtn_n = noise(shape, 70, rng, 4)          # where each world's own mountain zones sit
    fine = noise(shape, 10, rng, 2)
    moist_n = noise(shape, 70, rng, 3)
    blocks = np.floor(noise(shape, 6, rng, 1) * 4) / 3
    tex = noise((1024, 1024), 16, rng, 5)
    ridge_src = (1 - np.abs(tex * 2 - 1)) ** 2
    river_src = noise((1024, 1024), 40, rng, 4)

    # per-world frame: orientation of ranges/dunes, local polar coordinate for latitude
    theta = np.zeros(shape, np.float32)
    stretch = np.ones(shape, np.float32)
    lat = np.zeros(shape, np.float32)
    for lab, sl in enumerate(objs, 1):
        m = labels[sl] == lab
        ys, xs = np.nonzero(m)
        theta[sl][m] = rng.uniform(0, np.pi)
        stretch[sl][m] = rng.uniform(0.25, 0.7)
        cy = ys.mean() + sl[0].start
        lat[sl][m] = np.abs((yy[sl][m] - cy) / max(radius[lab], 1))     # 0 equator .. ~1 poles

    # biome zones: each world split into its mix by share, along noise / latitude / west-east / north-south
    zone_n = noise(shape, 90, rng, 3)
    AK = list(ARCH)
    aid = np.zeros(shape, np.int8)
    for lab, sl in enumerate(objs, 1):
        m = labels[sl] == lab
        mode, mix = mixes[lab]
        warp = zone_n[sl][m] - 0.5
        f = {"lat": lat[sl][m] + warp * 0.5, "x": xx[sl][m] / radius[lab] + warp * 1.2,
             "y": yy[sl][m] / radius[lab] + warp * 1.2}.get(mode, zone_n[sl][m])
        cum = np.cumsum([w for _, w in mix])
        z = np.minimum(np.searchsorted(cum / cum[-1], rank(f), side="right"), len(mix) - 1)
        aid[sl][m] = np.array([AK.index(k) for k, _ in mix])[z]
    is_ = {k: (aid == i) & land for i, k in enumerate(AK)}

    def soft(*keys):
        """Zone weight with blurred edges, so archetype relief blends across zone borders."""
        return ndi.gaussian_filter(sum(is_[k] for k in keys).astype(np.float32), 4)

    def oriented(field, scale):
        c, s = np.cos(theta), np.sin(theta)
        u = (xx * c + yy * s) / scale
        v = (-xx * s + yy * c) * stretch / scale
        return ndi.map_coordinates(field, [v % field.shape[0], u % field.shape[1]], order=1, mode="wrap")

    ranges = oriented(ridge_src, 0.9)
    dunes_f = oriented(tex, 0.35)
    canyon_f = oriented(ridge_src, 2.5)
    river = np.abs(oriented(river_src, 1.2) - 0.5)       # ~0 along river lines

    # --- relief, per archetype
    lab_amp = rng.uniform(0.8, 1.25, n + 1).astype(np.float32)
    lw = ndi.gaussian_filter(land.astype(np.float32), 6) + 1e-6
    amp = ndi.gaussian_filter(np.array([ARCH[k]["relief"] for k in AK], np.float32)[aid] * lab_amp[labels] * land, 6) / lw
    rng_share = ndi.gaussian_filter(np.array([ARCH[k]["ranges"] for k in AK], np.float32)[aid] * land, 6) / lw

    low = big * 0.75 + mid * 0.25
    for lab, sl in enumerate(objs, 1):       # rank per world, so no world lands entirely in a low patch
        m = labels[sl] == lab
        low[sl][m] = rank(low[sl][m])
    rel = GROUND + amp * 1.6 * smoothstep((low - 0.3) / 0.7) ** 1.5   # ~a third of each world stays at the base
    # mountains: gameplay mountain provinces as massifs, plus each world's own extra ranges
    m_mtn = 1 - np.exp(-ndi.distance_transform_edt(C["mountain"]) / 7)
    extra = ndi.gaussian_filter(smoothstep((mtn_n - (1 - rng_share * 2.5)) / 0.12), 3)   # broad zones, not walls
    rel += np.maximum(m_mtn, extra) * (22 + ranges * 60 + fine * 6)
    rel += (1 - np.exp(-ndi.distance_transform_edt(C["hills"]) / 5)) * (8 + mid * 12)
    # river valleys on wet / temperate worlds
    rel -= soft("temperate", "forest", "jungle", "swamp", "steppe", "ocean", "alpine", "grassland") \
        * smoothstep(1 - river / 0.035) * 9
    # deserts: dune seas in the low ground, mesas / canyons on red deserts and barren zones
    dunes = (np.sin(dunes_f * 40) * 0.5 + 0.5) * 8 * (big < 0.55)
    rel += soft("desert", "reddesert") * dunes
    mesa = np.floor(mid * 5) / 5 * 30
    rel += (GROUND + (rel - GROUND) * 0.6 + mesa * 0.9 - rel) * soft("reddesert", "barren")
    rel -= soft("reddesert", "desert", "barren") * smoothstep((canyon_f - 0.6) / 0.3) * 14
    # ice: smoothed glaciers + crevasses
    rel += (ndi.gaussian_filter(rel, 3) - (1 - np.abs(fine * 2 - 1)) ** 8 * 7 - rel) * soft("ice")
    # cities: flattened terraces
    terraces = GROUND + 1 + np.floor(big * 4) * 2 + blocks
    rel += (terraces - rel) * soft("city", "industrial")
    rel = np.where(C["urban"], terraces, rel)
    rel += ndi.gaussian_filter(is_["sinkhole"].astype(np.float32), 1.5) * 18     # Utapau: high plateau, the sinkholes are cut into it below
    rel -= C["marsh"] * 4

    # volcano cones in lava zones, craters in barren ones, Utapau-style sinkholes
    made = collections.Counter()
    per_r = {"lava": 12, "barren": 7, "sinkhole": 9}
    for lab, sl in enumerate(objs, 1):
        for kind in per_r:
            zone = (labels[sl] == lab) & is_[kind][sl]
            zr = np.sqrt(zone.sum() / np.pi)
            if zr < 8:
                continue
            ys, xs = np.nonzero(zone)
            for _ in range(int(rng.integers(3, 5 + zr // per_r[kind]))):
                i = rng.integers(len(ys))
                cy, cx = ys[i] + sl[0].start, xs[i] + sl[1].start
                cr = radius[lab] * (rng.uniform(0.07, 0.14) if kind == "sinkhole" else rng.uniform(0.06, 0.2))
                y0, y1 = int(max(cy - 2.5 * cr, 0)), int(min(cy + 2.5 * cr + 1, H))
                x0, x1 = int(max(cx - 2.5 * cr, 0)), int(min(cx + 2.5 * cr + 1, W))
                dd = np.hypot(yy[y0:y1, x0:x1] - cy, xx[y0:y1, x0:x1] - cx) / cr
                if kind == "lava":   # cone with a summit crater
                    prof = 45 * np.exp(-(dd / 1.4) ** 2) - 18 * np.exp(-(dd / 0.35) ** 2)
                elif kind == "sinkhole":   # sheer-walled pit, no rim
                    prof = -40 * smoothstep((1 - dd) / 0.2)
                else:
                    depth = min(cr * 0.9, 22)
                    prof = np.where(dd < 1, -depth * (1 - dd ** 2), 0) + 0.45 * depth * np.exp(-((dd - 1) / 0.3) ** 2)
                made[kind] += 1
                rel[y0:y1, x0:x1] += np.where(labels[y0:y1, x0:x1] == lab, prof, 0)
    print("volcanoes / craters / sinkholes:", dict(made))
    rel = ndi.gaussian_filter(rel, 0.8)

    # --- per-world elevation rank, sea, climate
    e = np.zeros(shape, np.float32)
    sea_mask = np.zeros(shape, bool)
    T = np.zeros(shape, np.float32)
    M = np.zeros(shape, np.float32)
    key = rel + low * 1e-3     # breaks ties on the flat base, so seas follow the noise, not the row order
    for lab, sl in enumerate(objs, 1):
        lm = labels[sl] == lab
        e[sl][lm] = rank(key[sl][lm])
        for i in np.unique(aid[sl][lm]):     # each zone: its own sea share and climate range
            m = lm & (aid[sl] == i)
            p = ARCH[AK[i]]
            er = e[sl][m]
            sea_mask[sl][m] = (rank(key[sl][m]) < p["sea"]) & ~C["urban"][sl][m] & ~C["mountain"][sl][m]
            t0, t1 = p["T"]
            T[sl][m] = t0 + (t1 - t0) * (1 - 0.55 * np.clip(er - 0.3, 0, 1) - 0.35 * lat[sl][m] ** 2)
            m0, m1 = p["M"]
            M[sl][m] = m0 + (m1 - m0) * moist_n[sl][m]
    near_water = np.exp(-ndi.distance_transform_edt(~sea_mask) / 30)
    M = np.clip(M + 0.25 * near_water * (M > 0.12), 0, 1)
    T = np.clip(T - 0.08 * C["mountain"], 0, 1)
    # seas sit flat just above the space plane so the coast never moves
    basin = smoothstep(ndi.distance_transform_edt(sea_mask) / 5)
    rel = rel * (1 - basin) + SHORE * basin
    coast = ndi.distance_transform_edt(land)
    h = np.where(land, np.clip(SHORE + (rel - SHORE) * smoothstep(coast / 3), SHORE, 255), 85).astype(np.float32)

    if os.environ.get("HOD_RELIEF_STATS"):
        for k in ARCH:
            v = h[is_[k] & land]
            if v.size:
                print(f"  {k:10s} height p5/p50/p95/max: " + " ".join(str(int(x)) for x in np.percentile(v, [5, 50, 95, 100])))
    # --- biome paint (Whittaker-style: temperature x moisture, then altitude, slope and water)
    gy_, gx_ = np.gradient(ndi.gaussian_filter(h, 2.0))
    slope = np.hypot(gx_, gy_)
    var = noise(shape, 35, rng, 3)                     # picks between sibling textures in large patches
    pick = lambda a, b: np.where(var > 0.5, a, b)
    t = np.full(shape, GRASS, np.uint8)
    # base climate table
    t = np.where(T < 0.18, np.where(M > 0.45, SNOWFARM, SNOWSAND), t)
    t = np.where((T >= 0.18) & (T < 0.40), np.where(M > 0.6, FOREST, np.where(M > 0.35, GRASSHILL, HILLS)), t)
    t = np.where((T >= 0.40) & (T < 0.72), np.where(M > 0.7, pick(DFOREST, FOREST),
                 np.where(M > 0.4, pick(GRASS, FARM), np.where(M > 0.2, SAVANNA, SAND))), t)
    t = np.where(T >= 0.72, np.where(M > 0.7, pick(JUNGLE, JUNGLE2), np.where(M > 0.45, SAVANNA,
                 np.where(M > 0.2, SAND, pick(DUNES, SAND)))), t)
    # archetype overrides
    t = np.where(is_["reddesert"], np.where(e > 0.6, BROWNMTN, pick(BROWN, SAND)), t)
    t = np.where(is_["desert"] & (e > 0.75), pick(BROWN, HILLS), t)
    t = np.where(is_["swamp"] & (t != WATER), np.where(M > 0.92, pick(JUNGLE2, DFOREST), pick(JUNGLE, GRASSHILL)), t)
    t = np.where(is_["barren"], np.where(slope > 1.2, ROCK2, pick(ROCK, BROWN)), t)
    t = np.where(is_["lava"], np.where(e < 0.35, LAVA, np.where(e < 0.7, pick(BROWNMTN, ROCK), ROCK2)), t)
    t = np.where(is_["city"], np.where(e > 0.92, ROCK, URBAN), t)
    t = np.where(is_["industrial"], np.where(var > 0.62, URBAN, np.where(var > 0.35, BROWN, ROCK)), t)
    # mountains and high ground: rock, snow on top when cold enough
    high = (C["mountain"] & (m_mtn > 0.45)) | (e > 0.9)
    rocky = np.where(M > 0.55, GREENMTN, np.where(is_["reddesert"] | is_["desert"], BROWNMTN, ROCK))
    t = np.where(high & ~is_["city"] & ~is_["lava"], np.where(T < 0.3, SNOWROCK, rocky), t)
    t = np.where((slope > np.quantile(slope[land], 0.95)) & ~is_["city"] & ~is_["lava"] & (coast > 5), np.where(T < 0.25, SNOWROCK, ROCK2), t)
    # beaches, seas, cities on any world
    beach = ~sea_mask & (ndi.distance_transform_edt(~sea_mask) < 4) & (T > 0.4) & land
    t = np.where(beach & ~is_["lava"], DUNES, t)
    t = np.where(sea_mask, np.where(is_["ice"], SNOWSAND, WATER), t)
    t = np.where(C["urban"], URBAN, t)
    t = np.where(land, t, 15).astype(np.uint8)
    print("texture share:", {int(k): round(float(v), 3) for k, v in zip(*np.unique(t[land], return_counts=True)) if v / land.sum() > 0.01})

    # --- world_normal.bmp (half res); R = -k*dh/dx, G = +k*dh/dy, B = up
    gy, gx = np.gradient(ndi.gaussian_filter(h, 1.0)[::2, ::2])
    nv = np.stack([-NORMAL_K * gx, NORMAL_K * gy, np.ones_like(gx)], -1)
    nv /= np.linalg.norm(nv, axis=-1, keepdims=True)
    nrm = np.clip(np.rint(nv * 127.5 + 127.5), 0, 255).astype(np.uint8)

    # --- trees.bmp from the painted biome (gfx/entities/trees.gfx: 2 palmer 3 palms_blend 5 forest_blend
    #     6 forest 11 beech_big 28 beech_blend 29 beech)
    TW, TH = round(W / TREE_SCALE), round(H / TREE_SCALE)
    gi = np.ix_(np.minimum(((np.arange(TH) + 0.5) * H / TH).astype(int), H - 1),
                np.minimum(((np.arange(TW) + 0.5) * W / TW).astype(int), W - 1))
    tt, tT = t[gi], T[gi]
    tland = land[gi] & (coast[gi] > 4) & ~sea_mask[gi]
    dens = noise((TH, TW), 6, rng, 3)
    r = rng.random((TH, TW))
    trees = np.zeros((TH, TW), np.uint8)
    for idx, (hot, cold, cover) in {DFOREST: ((2, 3), (6, 5), 0.95), FOREST: ((29, 28), (6, 5), 0.9),
                                    JUNGLE: ((2, 3), (2, 3), 0.95), JUNGLE2: ((3, 28), (3, 28), 0.8),
                                    GRASS: ((29, 28), (29, 28), 0.07), FARM: ((29, 28), (29, 28), 0.04),
                                    SAVANNA: ((11, 29), (11, 29), 0.06), GRASSHILL: ((28, 29), (6, 5), 0.12),
                                    SNOWFARM: ((6, 5), (6, 5), 0.08)}.items():
        sel = tland & (tt == idx) & (r < cover * (0.4 + 0.8 * dens))
        warm = tT[sel] > 0.6
        dense = dens[sel] > 0.45
        trees[sel] = np.where(warm, np.where(dense, hot[0], hot[1]), np.where(dense, cold[0], cold[1]))
    # HOD flora + props (WIPGFX/plans & scripts/flora_props.py, indices = mapobject_N in gfx/entities/trees.gfx):
    # giants replace part of the forest/jungle trees, props go on otherwise empty ground, a few per world
    zone = np.array(AK)[aid[gi]]
    trees[np.isin(zone, list(TREELESS))] = 0          # no trees on deserts, lava or barren ground
    giant_share = np.array([GIANT_WORLDS.get(names[l].split(" - ")[0], 0.0) if l else 0.0
                            for l in range(n + 1)], np.float32)[labels[gi]]
    for kind, idx, base in (("forest", 40, 0.2), ("jungle", 41, 0.25)):
        sel = (trees > 0) & (zone == kind) & (rng.random((TH, TW)) < np.maximum(base, giant_share))
        trees[sel] = idx
    empty = tland & (trees == 0) & (tt != URBAN)
    for kinds, props in PROPS.items():
        inzone = empty & np.isin(zone, kinds.split())
        for idx, p in props:
            sel = inzone & (trees == 0) & (rng.random((TH, TW)) < p)
            trees[sel] = idx
    print(f"trees.bmp {TW}x{TH}, {int((trees > 0).sum())} tree cells,",
          {int(k): int(v) for k, v in zip(*np.unique(trees[trees >= 40], return_counts=True))})

    # --- colormap RGB = clean flat planet maps (painted spheres flattened, clouds / night side removed:
    #     planet_clean.py). pdxmap.shader / tree.shader use only their hue up close (paint_tint); zoomed out pdxmap
    #     draws them as lit globes with drifting clouds. Alpha = distance from the planet's centre (0 .. 1 at the rim,
    #     1 in space): the shader rebuilds the sphere normal from it. City lights come from the city tile instead.
    from planet_clean import clean_planets
    cm = cm_half.copy()
    cm[..., :3] = clean_planets(cm_flat, lab_h)[..., :3]
    rr = np.ones(land_h.shape, np.float32)
    for lab, sl in enumerate(ndi.find_objects(lab_h), 1):
        if sl is None:
            continue
        m = lab_h[sl] == lab
        ys, xs = np.nonzero(m)
        d = np.hypot(ys - ys.mean(), xs - xs.mean())
        rr[sl][m] = np.clip(d / max(np.percentile(d, 99), 1), 0, 1)
    cm[..., 3] = rr

    # --- atmospheres on black (galaxy itself is procedural in gfx/FX/pdxwater.shader)
    dist_h, (iy, ix) = ndi.distance_transform_edt(~land_h, return_indices=True)
    owner = lab_h[iy, ix]
    col = np.zeros((n + 1, 3), np.float32)
    thick = np.zeros(n + 1, np.float32)
    for lab in range(1, n + 1):
        base_c, th = ARCH[arch[lab]]["atmo"]
        if names[lab].split(" - ")[0] == FELUCIA:
            base_c, th = FELUCIA_ATMO, th * 1.3
        col[lab] = np.array(base_c) * 0.8 + planet_rgb[lab] / max(planet_rgb[lab].max(), 1e-3) * 0.2
        thick[lab] = th * np.clip(radius[lab] / 45, 0.35, 1.2)
    d = dist_h / np.clip(radius[owner] / 120, 0.5, 1.4)
    wisp = noise(land_h.shape, 12, rng, 3)
    amt = thick[owner] * (0.6 * np.exp(-d / 1.5) + 0.4 * np.exp(-d / 5.0)) * (0.65 + 0.7 * wisp) * (owner > 0) * ~land_h
    glow = np.clip(col[owner] * amt[..., None], 0, 1)
    water_out = []
    for lvl in range(3):
        src = np.array(load(f"{BASE}/colormap_water_{lvl}.dds").convert("RGBA")).astype(np.float32) / 255
        g = glow if lvl == 0 else np.array(Image.fromarray((glow * 255).astype(np.uint8)).resize(
            (src.shape[1], src.shape[0]), Image.BILINEAR)) / 255.0
        out = src.copy()
        out[..., :3] = g
        water_out.append(np.rint(out * 255).astype(np.uint8))

    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        atlas = np.array(load(f"{MAP}/terrain/atlas0.dds").convert("RGB")).astype(np.float32)
        g = 5 if atlas.shape[0] % 5 == 0 else 4             # 5x5 = Revolution_Realized atlas (terrain_atlas.py)
        ts = atlas.shape[0] // g
        tex_mean = np.array([atlas[(i // g) * ts:(i // g + 1) * ts, (i % g) * ts:(i % g + 1) * ts].mean((0, 1)) for i in range(g * g)]) / 255
        tex_of = np.zeros(256, int)
        for line in open("common/terrain/00_terrain.txt", encoding="utf-8-sig"):
            if "color = {" in line and "texture =" in line:
                tex_of[int(line.split("color = {")[1].split("}")[0])] = int(line.split("texture =")[1].split()[0])
        c = tex_mean[tex_of[t]]
        snow = np.isin(t, list(PERM_SNOW))
        c[snow] = c[snow] * 0.3 + 0.7 * 0.93
        cmf = np.repeat(np.repeat(paint_tint(cm[..., :3]), 2, 0), 2, 1)[:H, :W]
        c = np.where(cmf < 0.5, 2 * c * cmf, 1 - 2 * (1 - c) * (1 - cmf))
        sun = np.array([-0.5, -0.5, 0.7]); sun /= np.linalg.norm(sun)
        nf = (np.repeat(np.repeat(nrm, 2, 0), 2, 1)[:H, :W].astype(np.float32) - 127.5) / 127.5
        c = c * (np.clip(nf @ sun, 0, 1) * 1.2 + 0.1)[..., None]
        tm = np.array(Image.fromarray((trees > 0).astype(np.uint8) * 255).resize((W, H), Image.NEAREST)) > 0
        c[tm & land] = c[tm & land] * 0.6 + np.array([0.05, 0.16, 0.06]) * 0.4
        space = np.repeat(np.repeat(water_out[0][..., :3], 2, 0), 2, 1)[:H, :W] / 255 + 0.02
        img = (np.where(land[..., None], np.clip(c, 0, 1), space) * 255).astype(np.uint8)
        Image.fromarray(img).resize((W // 4, H // 4), Image.LANCZOS).save(f"{a.preview}/preview_full.png")
        Image.fromarray(img).crop((1150, 1000, 2250, 2000)).save(f"{a.preview}/preview_crop.png")
        Image.fromarray(img).save(f"{a.preview}/preview_big.png")
        Image.fromarray(np.clip((h - 85) * 1.5, 0, 255).astype(np.uint8)).save(f"{a.preview}/height_big.png")
        Image.fromarray(np.clip((h - 85) * 1.5, 0, 255).astype(np.uint8)).crop((1150, 1000, 2250, 2000)).save(f"{a.preview}/height_crop.png")
        with open(f"{a.preview}/archetypes.txt", "w", encoding="utf-8") as f:
            for lab in range(1, n + 1):
                mode, mix = mixes[lab]
                cy, cx = [(v.start + v.stop) // 2 for v in objs[lab - 1]]
                f.write(f"{lab}\t{names[lab]}\t{cx},{cy},{int(radius[lab])}\t{mode}\t" + " ".join(f"{k} {w:g}" for k, w in mix) + "\n")
        print("previews written to", a.preview)

    if a.write:
        city = load(f"{MAP}/cities.bmp")
        planet = lambda l: names[l].split(" - ")[0]
        style = np.array([2] + [3 if planet(l) == "Christophsis" else
                                4 if planet(l) in TREE_VILLAGE_WORLDS or arch[l] in ("forest", "jungle") else 2
                                for l in range(1, n + 1)], np.uint8)
        cmap = np.where(is_["city"] & (style[labels] != 3), 1, style[labels])
        cmap = carve_city_borders(world_styles(cmap, labels, names), pid)
        t, cmap, trees, cm = world_tweaks(t, cmap, trees, cm, labels, names, pid, rng)
        out_t = Image.fromarray(t, "P"); out_t.putpalette(palette); out_t.save(f"{MAP}/terrain.bmp")
        h = round_coasts(h, land, labels)
        Image.fromarray(np.rint(h).astype(np.uint8), "L").save(f"{MAP}/heightmap.bmp")
        Image.fromarray(nrm, "RGB").save(f"{MAP}/world_normal.bmp")
        # city style (map/cities.txt, coruscant_buildings.py wire): 1 megacity clusters in city zones, 2 towns,
        # 3 Christophsis towers (whole planet), 4 treehouse villages on tree worlds, 5-8 per world (STYLE_WORLDS)
        cb = Image.fromarray(cmap.astype(np.uint8), "P")
        cb.putpalette(city.getpalette())
        cb.save(f"{MAP}/cities.bmp")
        tree_pal = load(f"{MAP}/trees.bmp").getpalette()
        tr = Image.fromarray(trees, "P"); tr.putpalette(tree_pal); tr.save(f"{MAP}/trees.bmp")
        save_bgra_dds(f"{BASE}/colormap_rgb_cityemissivemask_a.dds", np.rint(np.clip(cm, 0, 1) * 255).astype(np.uint8),
                      f"{MAP}/terrain/colormap_rgb_cityemissivemask_a.dds")
        for lvl in range(3):
            save_bgra_dds(f"{BASE}/colormap_water_{lvl}.dds", water_out[lvl], f"{MAP}/terrain/colormap_water_{lvl}.dds")
        # the water shader reads the atmospheres from the (otherwise unused) ice slot, not through the refraction pass
        shutil.copyfile(f"{MAP}/terrain/colormap_water_0.dds", f"{MAP}/terrain/ice_diffuse.dds")
        reheight(np.rint(h))
        globe_texture()
        print("map files written")


if __name__ == "__main__":
    main()
