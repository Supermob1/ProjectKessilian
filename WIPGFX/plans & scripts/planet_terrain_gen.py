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
  map/buildings.txt, map/unitstacks.txt              y column re-snapped to the heightmap (height = pixel / 10)

Inputs: map/provinces.bmp + definition.csv (shapes, gameplay terrain), history/states (planet names),
WIPGFX/Assets/map_base/ (original colormaps: painted planet hue hints + DDS headers, original terrain.bmp palette).

Usage (from the mod root):
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --preview OUTDIR
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --write
  python "WIPGFX/plans & scripts/planet_terrain_gen.py" --reheight   only re-snap buildings/unitstacks to heightmap.bmp
"""
import argparse, collections, csv, glob, io, os, re
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
    """Close-up colormap tint from the painted globe, as gfx/FX/pdxmap.shader computes it: hue only at 20%
    around neutral 0.5 (the shading baked into the painting is brightness, so it drops out)."""
    lum = rgb.mean(-1, keepdims=True)
    return 0.5 + (np.clip(0.4 + 0.1 * rgb / np.maximum(lum, 0.05), 0, 1) - 0.5) * np.clip(lum * 10, 0, 1)


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="write preview PNGs to this dir")
    ap.add_argument("--write", action="store_true", help="overwrite the map files listed in the docstring")
    ap.add_argument("--reheight", action="store_true", help="only re-snap buildings.txt/unitstacks.txt to heightmap.bmp")
    a = ap.parse_args()
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
        out_t = Image.fromarray(t, "P"); out_t.putpalette(palette); out_t.save(f"{MAP}/terrain.bmp")
        Image.fromarray(np.rint(h).astype(np.uint8), "L").save(f"{MAP}/heightmap.bmp")
        Image.fromarray(nrm, "RGB").save(f"{MAP}/world_normal.bmp")
        # city style (map/cities.txt, coruscant_buildings.py wire): 1 megacity clusters in city zones, 2 towns,
        # 3 Christophsis towers (whole planet), 4 treehouse villages on tree worlds
        city = load(f"{MAP}/cities.bmp")
        planet = lambda l: names[l].split(" - ")[0]
        style = np.array([2] + [3 if planet(l) == "Christophsis" else
                                4 if planet(l) in TREE_VILLAGE_WORLDS or arch[l] in ("forest", "jungle") else 2
                                for l in range(1, n + 1)], np.uint8)
        cmap = np.where(is_["city"] & (style[labels] != 3), 1, style[labels])
        cb = Image.fromarray(cmap.astype(np.uint8), "P")
        cb.putpalette(city.getpalette())
        cb.save(f"{MAP}/cities.bmp")
        tree_pal = load(f"{MAP}/trees.bmp").getpalette()
        tr = Image.fromarray(trees, "P"); tr.putpalette(tree_pal); tr.save(f"{MAP}/trees.bmp")
        save_bgra_dds(f"{BASE}/colormap_rgb_cityemissivemask_a.dds", np.rint(np.clip(cm, 0, 1) * 255).astype(np.uint8),
                      f"{MAP}/terrain/colormap_rgb_cityemissivemask_a.dds")
        for lvl in range(3):
            save_bgra_dds(f"{BASE}/colormap_water_{lvl}.dds", water_out[lvl], f"{MAP}/terrain/colormap_water_{lvl}.dds")
        reheight(np.rint(h))
        print("map files written")


if __name__ == "__main__":
    main()
