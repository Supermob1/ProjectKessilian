"""Alderaan, the peaceful heart of the Core, as one battlefield before the Clone Wars (research: WIPGFX/research/alderaan/;
canon and Legends mixed, the user, 2026-10-21). CANON: vast bodies of water, snow-capped mountains and green grassy
hills; Aldera the capital, a picturesque city surrounded by nature with the University of Alderaan and the Royal Palace
(the Mountain Palace), which overlooked a lake among snow-capped mountains, the River Wuitho seen from its south terrace;
Appenza Peak, visible from Aldera; Crevasse City, the first and largest canyon city, built into the walls of a massive
canyon with even its heavy industry hidden; Hallyn; Sanctuary Coast, a sprawling city on enormous stilts on the border
of a large inland sea; the Isatabith rain forest, the Cloudshape Falls, the Istabith Falls and range, the Glarus
Lagoons, the Polar Sea; white synthstone architecture. LEGENDS: the cities Belleau-a-Lir, Chianar, Juranno and Terrarium
City; the Apalis Coast, the Castle Lands, the Glarus Valley, the Juran Mountains, the Kaamos Territory, King's Pass, the
Petrified Mounds of the Killiks. Owner: ALD (as before), a member of the Republic.
LAYOUT IS A DESIGN CHOICE beyond the stated relationships: Aldera in a valley under the Juran Mountains (impassable, split by King's Pass
into two states), with the Palace on its lake north of the city and King's Pass through the mountains to the Kaamos Territory (Terrarium
City, the Carida lane) in the north; the Polar Sea (impassable) north-west; the Apalis Coast west (the Anaxes lane), the
Castle Lands south-west of it with the Killik mounds, the Glarus Valley and its lagoons between them and Aldera; Crevasse
City in its canyon in the middle; Hallyn and Juranno east and north-east, Belleau-a-Lir on the eastern coast (the
Balmorra lane); the Inland Sea (impassable) in the south with Sanctuary Coast on its eastern shore running out to the
south-eastern coast (the Kuat lane); Chianar on the southern coast, the Isatabith rain forest south-west of the sea with
the Cloudshape Falls, the Istabith Range south-west with its falls and the Istabith Peaks (impassable).
Names from the sources: every state and VP name except the invented Palace Lake and Aldera Spaceport.
    python "WIPGFX/plans & scripts/alderaan_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/alderaan_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 199 province ids are kept (strategic region unchanged); only the pixels move.
Run order: alderaan_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (ald_*) ->
planet_terrain_gen.py --planet Alderaan -> military_buildings.py alderaan_atlas, models hod_ald_ -> coruscant_buildings.py
wire -> military_buildings.py place Alderaan -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
"""
import glob, math, os, re, sys
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from felucia_map import split_area
from felucia_tribes import block, place, rw
from raxus_map import mend
import planet_common as pcom
from korriban_map import shape as kshape, uncross

PLANET = "Alderaan"
ZONES_JSON = "WIPGFX/Assets/alderaan_zones.json"
ZONES_PNG = "WIPGFX/Assets/alderaan_zones.png"
KIND = {"city": 1, "palace": 2, "campus": 3, "canyon": 4, "stilts": 5, "falls": 6, "mounds": 7, "pass": 8, "hills": 9,
        "plains": 10, "forest": 11, "rainforest": 12, "tundra": 13, "coast": 14, "mountains": 15, "sea": 16, "peak": 17}
TERRAIN = {"city": "urban", "palace": "urban", "campus": "urban", "canyon": "hills", "stilts": "urban", "falls": "hills",
           "mounds": "hills", "pass": "mountain", "hills": "hills", "plains": "plains", "forest": "forest",
           "rainforest": "jungle", "tundra": "plains", "coast": "plains", "mountains": "mountain", "sea": "mountain",
           "peak": "mountain"}
SEED = 6
CAPITAL = 6
CAPITAL_VP = "Aldera"
CORE = "ALD"
PORT_STATE = 174                     # Sanctuary Coast, the old shipyards of the south-east
OWNER = {s: "ALD" for s in (6, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 1318, 1319, 1320, 1321, 1322, 1323)}
WARP = (0.1, 9)
TARGET_PASSABLE = 125                # user rule: passable provinces outnumber impassable (~125 / 74)
STRAIGHT = {"palace", "campus"}
FEATURES = [
    ("Royal Palace of Alderaan", "palace", CAPITAL, 1, [("rect", 0.02, -0.4, 0.07, 0.05, 0)]),
    ("Aldera", "city", CAPITAL, 3, [("ell", 0.0, -0.24, 0.13, 0.09, 10)]),
    ("University of Alderaan", "campus", CAPITAL, 1, [("rect", -0.16, -0.17, 0.06, 0.05, -8)]),
    ("Appenza Peak", "peak", CAPITAL, 1, [("ell", 0.2, -0.38, 0.06, 0.06, 0)]),
    ("King's Pass", "pass", 170, 1, [("cap", -0.12, -0.5, -0.1, -0.72, 0.045)]),
    ("Palace Lake", "sea", 1321, 0, [("ell", 0.03, -0.48, 0.1, 0.04, 5)]),
    ("Terrarium City", "city", 170, 1, [("ell", 0.22, -0.8, 0.09, 0.06, 0)]),
    ("Crevasse City", "canyon", 169, 2, [("cap", 0.02, 0.0, 0.3, 0.14, 0.05)]),
    ("Hallyn", "city", 171, 1, [("ell", 0.48, -0.18, 0.1, 0.07, 0)]),
    ("Juranno", "city", 176, 1, [("ell", 0.52, -0.55, 0.07, 0.05, 20)]),
    ("Belleau-a-Lir", "city", 166, 1, [("ell", 0.82, 0.12, 0.07, 0.06, 0)]),
    ("Sanctuary Coast", "stilts", 174, 2, [("ell", 0.48, 0.48, 0.1, 0.07, -40)]),
    ("Chianar", "city", 172, 1, [("ell", 0.18, 0.86, 0.07, 0.05, 0)]),
    ("Glarus Lagoons", "coast", 168, 1, [("ell", -0.36, -0.02, 0.08, 0.06, 20)]),
    ("Petrified Mounds of the Killiks", "mounds", 173, 1, [("ell", -0.62, 0.3, 0.07, 0.06, 0)]),
    ("Cloudshape Falls", "falls", 175, 1, [("ell", -0.18, 0.62, 0.06, 0.05, 0)]),
    ("Istabith Falls", "falls", 177, 1, [("ell", -0.46, 0.66, 0.06, 0.05, 0)]),
    ("Aldera Spaceport", "coast", 167, 1, [("rect", -0.88, -0.25, 0.1, 0.09, 15)]),
    ("Juran Mountains", "mountains", 1318, 0, [("cap", -0.06, -0.6, 0.38, -0.5, 0.1), ("cap", 0.38, -0.5, 0.36, -0.28, 0.08)]),
    ("West Juran Mountains", "mountains", 1323, 0, [("cap", -0.5, -0.42, -0.2, -0.56, 0.1), ("cap", -0.5, -0.42, -0.42, -0.2, 0.08)]),
    ("Polar Sea", "sea", 1319, 0, [("ell", -0.6, -0.78, 0.36, 0.2, 35)]),
    ("Inland Sea", "sea", 1320, 0, [("ell", 0.12, 0.48, 0.3, 0.17, -15), ("ell", 0.3, 0.38, 0.12, 0.1, 0)]),
    ("Istabith Peaks", "mountains", 1322, 0, [("cap", -0.75, 0.5, -0.5, 0.82, 0.09), ("cap", -0.5, 0.82, -0.3, 0.92, 0.07)]),
]
SEEDS = {CAPITAL: ((0.0, -0.25), "hills"), 166: ((0.82, 0.1), "coast"), 167: ((-0.82, -0.2), "coast"),
         168: ((-0.35, -0.05), "plains"), 169: ((0.15, 0.1), "hills"), 170: ((0.15, -0.82), "tundra"),
         171: ((0.5, -0.15), "plains"), 172: ((0.25, 0.85), "coast"), 173: ((-0.6, 0.25), "hills"),
         174: ((0.6, 0.55), "coast"), 175: ((-0.15, 0.7), "rainforest"), 176: ((0.55, -0.55), "forest"),
         177: ((-0.55, 0.62), "forest")}
STATE_NAMES = {CAPITAL: "Aldera", 166: "Belleau-a-Lir", 167: "Apalis Coast", 168: "Glarus Valley", 169: "Crevasse City",
               170: "Kaamos Territory", 171: "Hallyn", 172: "Chianar", 173: "Castle Lands", 174: "Sanctuary Coast",
               175: "Isatabith Rain Forest", 176: "Juranno", 177: "Istabith Range", 1318: "Juran Mountains",
               1319: "Polar Sea", 1320: "Inland Sea", 1321: "Palace Lake", 1322: "Istabith Peaks", 1323: "West Juran Mountains"}
IMPASSABLE = {1318, 1319, 1320, 1321, 1322, 1323}
VPS = [(CAPITAL, "Aldera", CAPITAL_VP, 20), (CAPITAL, "Royal Palace of Alderaan", "Royal Palace of Alderaan", 10),
       (CAPITAL, "University of Alderaan", "University of Alderaan", 5), (CAPITAL, "Appenza Peak", "Appenza Peak", 2),
       (CAPITAL, "hills", "River Wuitho", 1),
       (170, "King's Pass", "King's Pass", 3), (170, "Terrarium City", "Terrarium City", 3),
       (169, "Crevasse City", "Crevasse City", 5), (171, "Hallyn", "Hallyn", 3), (176, "Juranno", "Juranno", 3),
       (166, "Belleau-a-Lir", "Belleau-a-Lir", 3), (174, "Sanctuary Coast", "Sanctuary Coast", 5), (172, "Chianar", "Chianar", 3),
       (168, "Glarus Lagoons", "Glarus Lagoons", 2), (173, "Petrified Mounds of the Killiks", "Petrified Mounds of the Killiks", 2),
       (175, "Cloudshape Falls", "Cloudshape Falls", 2), (177, "Istabith Falls", "Istabith Falls", 2),
       (167, "Aldera Spaceport", "Aldera Spaceport", 2), (175, "rainforest", "Isatabith Rain Forest", 1),
       (173, "hills", "Castle Lands", 1), (167, "coast", "Apalis Coast", 1)]

def landforms(ctx):
    """Crevasse City in the ground itself (the user, 2026-10-21: the stand-alone rock model looked out of place): a
    rock shelf round it with a gorge cut west-east through it, the city's facades set into its walls (ald_crevasse,
    floor at the VP). The falls have no model (the user, 2026-10-21: removed)."""
    rel, z, sub, yy, xx, zj = ctx["rel"], ctx["z"].copy(), ctx["sub"], ctx["yy"], ctx["xx"], ctx["zj"]
    at = {n: zj["provinces"][q]["centre"] for q, n in zj["vp_names"].items()}
    r0, c0 = at["Crevasse City"]
    r0, c0 = r0 - ctx["sl"][0].start, c0 - ctx["sl"][1].start
    d = np.hypot(yy - r0, xx - c0)
    ground = sub & np.isin(z, (4, 9, 10))                                     # the canyon zone and the hills round it
    plat = np.clip((11.0 - d) / 4.0, 0, 1)
    plat = plat * plat * (3 - 2 * plat)
    rel = np.where(ground, np.maximum(rel, 30.0 * plat + rel * (1 - plat)), rel)
    along = np.clip((9.0 - np.abs(xx - c0)) / 2.5, 0, 1)                       # the gorge, tapering at both ends
    wall = np.clip((np.abs(yy - r0) - 1.6) / 1.4, 0, 1)
    cut = ground & (along > 0) & (wall < 1)
    rel = np.where(cut, rel * wall - 4.0 * (1 - wall) * along + rel * (1 - along) * (1 - wall), rel)
    z[cut] = 4
    ctx["rel"], ctx["z"] = rel, z


TERRAIN_CFG = dict(
    hook=landforms,
    seed=6, base=4, rough=2, open=(9, 10, 11, 12, 13, 14),
    zones={
        1: dict(relief=("flat", 6), tex=["URBAN", ("GRASS", ">", 0.55)]),                             # the cities
        2: dict(relief=("ramp_top", 14, 8, 3), tex=["URBAN", ("GRASSHILL", ">", 0.6)]),                # the Palace
        3: dict(relief=("flat", 7), tex=["URBAN", ("GRASS", ">", 0.5)], props=[(229, 0.15)]),          # the University
        4: dict(relief=("flat", 1), tex=["ROCK2", ("URBAN", ">", 0.6)]),                               # Crevasse City's canyon
        5: dict(relief=("flat", 3), tex=["URBAN", ("SAVANNA", ">", 0.7)]),                             # Sanctuary Coast
        6: dict(relief=("flat", 4), tex=["GRASSHILL", ("ROCK", ">", 0.55)], props=[(230, 0.3), (229, 0.2)]),   # the falls
        7: dict(relief=("rolling", 6, 5, 4), tex=["BROWN", ("GRASSHILL", ">", 0.5)], props=[(231, 0.2)]),   # the Killik mounds
        8: dict(relief=("flat", 10), tex=["SNOWROCK", ("ROCK", ">", 0.5)]),                            # King's Pass
        9: dict(relief=("rolling", 9, 6, 5), tex=["GRASSHILL", ("GRASS", ">", 0.5), ("ROCK2", ">", 0.9), (13, ">", 0.96)],
                props=[(229, 0.25), (231, 0.25), (230, 0.1)]),                                         # green grassy hills
        10: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("FARM", ">", 0.6), (13, ">", 0.95)], props=[(231, 0.35), (229, 0.12)]),
        11: dict(relief=("rolling", 7, 4, 6), tex=["FOREST", ("DFOREST", ">", 0.5)], props=[(230, 0.55), (229, 0.25)]),
        12: dict(relief=("rolling", 4, 3, 6), tex=["JUNGLE", ("FOREST", ">", 0.5)], props=[(229, 0.6), (230, 0.15)]),
        13: dict(relief=("rolling", 5, 3, 7), tex=["SNOWSAND", ("SNOWFARM", ">", 0.5), ("ROCK", ">", 0.9)], props=[(230, 0.15)]),
        14: dict(relief=("rolling", 3, 2, 8), tex=["GRASS", ("SAVANNA", ">", 0.6), (13, ">", 0.95)], props=[(231, 0.3), (229, 0.1)]),
        15: dict(relief=("spires", 18, 10, 0.1, (2.0, 4.0), (30, 60)), tex=["SNOWROCK", ("ROCK", ">", 0.45), ("GREENMTN", ">", 0.8)],
                props=[(230, 0.2)]),                                                                   # the snow mountains
        16: dict(relief=("flat", 0.3), tex="WATER"),                                                   # the seas, the lake
        17: dict(relief=("ramp_top", 30, 12, 3), tex=["SNOWROCK", ("ROCK", ">", 0.6)]),                # Appenza Peak
    },
    steep=("ROCK", 6, (9, 10, 11, 12, 13, 14)),
    city={1: 84, 2: 84, 3: 84, 5: 84, 9: 84, 10: 84, 14: 84},   # map/cities.txt 84: Alderaan's white synthstone towns (ald_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.74, 0.74, 0.74), 2: (0.8, 0.8, 0.8), 3: (0.637, 0.735, 0.618), 4: (0.495, 0.525, 0.36), 5: (0.692, 0.735, 0.65), 6: (0.255, 0.546, 0.254), 7: (0.441, 0.525, 0.266), 8: (0.82, 0.84, 0.86), 9: (0.166, 0.546, 0.159), 10: (0.177, 0.588, 0.135), 11: (0.106, 0.42, 0.178), 12: (0.062, 0.441, 0.145), 13: (0.74, 0.78, 0.76), 14: (0.234, 0.609, 0.186), 15: (0.86, 0.88, 0.92), 16: (0.08, 0.35, 0.62), 17: (0.9, 0.92, 0.94)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)

PLACEMENT = dict(
    new_models={"hod_ald_palace", "hod_ald_aldera", "hod_ald_university", "hod_ald_crevasse", "hod_ald_sanctuary",
                "hod_ald_killik"},
    items=[("hod_ald_palace", 1.0, ("at_vp", "Royal Palace of Alderaan")), ("hod_ald_aldera", 1.0, ("at_vp", "Aldera")),
           ("hod_ald_university", 0.9, ("at_vp", "University of Alderaan")), ("hod_ald_crevasse", 1.0, ("at_vp", "Crevasse City")),
           ("hod_ald_sanctuary", 1.0, ("at_vp", "Sanctuary Coast")),
           ("hod_ald_killik", 0.9, ("at_vp", "Petrified Mounds of the Killiks"))],
    no_pad={"hod_ald_crevasse"},   # it stands in the gorge landforms() cuts
    clear={"hod_ald_palace": 5.0, "hod_ald_aldera": 6.0, "hod_ald_university": 4.0, "hod_ald_crevasse": 5.0,
           "hod_ald_sanctuary": 5.5, "hod_ald_killik": 4.0},
)


def mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    return land, pid, np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])


def shape(s_, U, V):
    return kshape(s_, U, V)


def layout(m, rng):
    """feature index per pixel and features [(name, kind, state, provinces)]: FEATURES in order, then the open
    ground by nearest region seed"""
    import planet_terrain_gen as g
    ys, xs = np.nonzero(m)
    cy, cx, R = ys.mean(), xs.mean(), math.sqrt(m.sum() / math.pi)
    sl = np.s_[ys.min() - 2:ys.max() + 3, xs.min() - 2:xs.max() + 3]
    yy, xx = np.mgrid[sl].astype(np.float32)
    U0, V0 = (xx - cx) / R, (yy - cy) / R
    U = U0 + (g.noise(U0.shape, WARP[1], rng, 2) - 0.5) * 2 * WARP[0]
    V = V0 + (g.noise(U0.shape, WARP[1], rng, 2) - 0.5) * 2 * WARP[0]
    sm = m[sl]
    fid = np.full(sm.shape, -1, np.int32)
    feats = []
    for name, k, sid, n, shapes in FEATURES:
        feats.append((name, k, sid, n))
        u_, v_ = (U0, V0) if k in STRAIGHT else (U, V)
        fid[sm & (fid < 0) & np.any([shape(s_, u_, v_) for s_ in shapes], 0)] = len(feats) - 1
    free = sm & (fid < 0)
    sids = list(SEEDS)
    d = np.stack([np.hypot(U - SEEDS[s][0][0], V - SEEDS[s][0][1]) for s in sids])
    near = np.argmin(d, 0)
    for i, sid in enumerate(sids):
        feats.append((STATE_NAMES[sid], SEEDS[sid][1], sid, 0))
        fid[free & (near == i)] = len(feats) - 1
    full = np.full(m.shape, -1, np.int32)
    full[sl] = fid
    return full, feats


def tidy(lab, feats, m):
    """every feature in one piece: stray bits join the neighbour with the longest shared border, preferring their own
    state, then their own kind, then open ground"""
    for _ in range(3):
        for i in range(len(feats)):
            pieces, n = ndi.label(lab == i)
            if n < 2:
                continue
            keep = np.argmax(np.bincount(pieces.ravel())[1:]) + 1
            for j in range(1, n + 1):
                if j == keep:
                    continue
                frag = pieces == j
                ring = ndi.binary_dilation(frag) & ~frag & m
                nb = np.bincount(lab[ring][lab[ring] >= 0], minlength=len(feats))
                same = [k for k in np.nonzero(nb)[0] if feats[k][2] == feats[i][2]]
                kin = [k for k in np.nonzero(nb)[0] if feats[k][1] == feats[i][1]]       # plain to plain, rock to rock
                opn = [k for k in np.nonzero(nb)[0] if feats[k][2] not in IMPASSABLE]
                pick = same or kin or opn or list(np.nonzero(nb)[0])
                lab[frag] = max(pick, key=lambda k: nb[k])
    return lab


def main():
    dry = sys.argv[sys.argv.index("--dry") + 1] if "--dry" in sys.argv else None
    if not dry:
        pcom.guard(PLANET, STATE_NAMES, [f[2] for f in FEATURES])
    land, pid, m = mask()
    ids = sorted(np.unique(pid[m]).tolist())
    rng = np.random.default_rng(SEED)
    lab, feats = layout(m, rng)
    lab = tidy(lab, feats, m)
    for i, f in enumerate(feats):
        assert ndi.label(lab == i)[1] <= 1, f"{f[0]} in pieces"
    passable = m & np.isin(lab, [i for i, f in enumerate(feats) if f[2] not in IMPASSABLE])
    assert ndi.label(passable)[1] == 1, "the open ground is cut in two"
    groups = [dict(name=f[0], kind=f[1], state=f[2], mask=lab == i, n=f[3]) for i, f in enumerate(feats) if (lab == i).any()]
    open_ = [g_ for g_ in groups if not g_["n"] and g_["state"] not in IMPASSABLE]
    px = sum(g_["mask"].sum() for g_ in open_) / (TARGET_PASSABLE - sum(g_["n"] for g_ in groups))
    for g_ in open_:                                                   # province size so the passable total hits the target
        g_["n"] = max(1, round(g_["mask"].sum() / px))
    rocks = [g_ for g_ in groups if g_["state"] in IMPASSABLE]           # the leftover ids, by area
    left = len(ids) - sum(g_["n"] for g_ in groups)
    area = sum(g_["mask"].sum() for g_ in rocks)
    for g_ in rocks:
        g_["n"] = max(1, int(left * g_["mask"].sum() / area))
    rocks[0]["n"] += len(ids) - sum(g_["n"] for g_ in groups)
    assert sum(g_["n"] for g_ in groups) == len(ids) and min(g_["n"] for g_ in groups) >= 1, [g_["n"] for g_ in groups]
    newpid = pid.copy()
    it = iter(ids)
    prov = {}
    for gi, gr in enumerate(groups):
        part = split_area(gr["mask"], gr["n"], rng) if gr["n"] > 1 else np.zeros(int(gr["mask"].sum()), int)
        ys, xs = np.nonzero(gr["mask"])
        for i in range(gr["n"]):
            p = next(it)
            newpid[ys[part == i], xs[part == i]] = p
            prov[p] = dict(zone=gr["kind"], kind=KIND[gr["kind"]], feature=gr["name"], state=gr["state"], group=gi)
    mend(newpid, m, {p: dict(v, state=v["group"]) for p, v in prov.items()})
    uncross(newpid, m)
    for sid in {v["state"] for v in prov.values()}:
        assert ndi.label(np.isin(newpid, [p for p, v in prov.items() if v["state"] == sid]))[1] == 1, f"state {sid} in pieces"
    if dry:
        return preview(dry, newpid, m, prov, groups)
    rows = pcom.definition_rows()
    pcom.measure(prov, newpid, pid, rows, TERRAIN)
    pcom.write_map(newpid, m, rows, prov)
    vp_names = states(prov, land, m, newpid, rng)
    kind = np.zeros(m.shape, np.uint8)
    for p, v in prov.items():
        kind[newpid == p] = v["kind"]
    pcom.write_zones(ZONES_JSON, ZONES_PNG, m, kind, vp_names, prov)


def states(prov, land, m, newpid, rng):
    """state files keeping resources, industry and manpower (owner kept); victory points, names, map positions,
    units (off the impassable ground), the port on the landing field"""
    old = pcom.old_states(STATE_NAMES)
    pc = lambda p: np.array(prov[p]["centre"])
    by_state = {}
    for p, v in prov.items():
        by_state.setdefault(v["state"], []).append(p)
    vp_names, vps = {}, {}
    for sid, feat, name, val in VPS:
        cand = [p for p in by_state[sid] if (prov[p]["feature"] == feat or prov[p]["zone"] == feat) and p not in vp_names]
        cen = np.mean([pc(p) for p in prov if prov[p]["feature"] == prov[cand[0]]["feature"]], 0)
        p = min(cand, key=lambda q: np.hypot(*(pc(q) - cen)))
        vp_names[p], vps[p] = name, val
    capital_p = next(p for p, n in vp_names.items() if n == CAPITAL_VP)
    dock = [p for p in by_state[PORT_STATE] if prov[p]["coastal"]]
    port = max(dock, key=lambda p: pc(p)[1]) if dock else capital_p
    naval, docks = [], 0
    for sid in old:
        b = block(block(open(old[sid], encoding="utf-8-sig").read(), "history"), "buildings")
        naval += [int(x) for x in re.findall(r"naval_base\s*=\s*(\d+)", b)]
        docks += sum(int(x) for x in re.findall(r"\bdockyard\s*=\s*(\d+)", b))
    sts = {}
    for sid, provs in sorted(by_state.items()):
        provs = sorted(provs)
        src = open(old[sid], encoding="utf-8-sig").read() if sid in old else ""
        res = block(src, "resources") or "\n\tresources={\n\t}"
        bld = block(block(src, "history"), "buildings") or "\n\t\tbuildings = {\n\t\t\tinfrastructure = 1\n\t\t}"
        bld = re.sub(r"\n\s*\d+\s*=\s*\{[^{}]*\}", "", bld)
        bld = re.sub(r"\n\s*dockyard\s*=\s*\d+", "", bld)
        man = re.search(r"manpower\s*=\s*(\d+)", src).group(1) if src else "1000"
        cat = re.search(r"state_category\s*=\s*(\w+)", src).group(1) if src else "wasteland_sector"
        imp = ""
        if sid == PORT_STATE:                                            # the fleet's port and yards: the landing zone
            if docks:
                bld = bld.rstrip().rstrip("}") + f"\tdockyard = {docks}\n\t\t}}"
            if naval:
                bld = bld.rstrip().rstrip("}") + f"\t\t\t{port} = {{\n\t\t\t\tnaval_base = {max(naval)}\n\t\t\t}}\n\t\t}}"
        if sid in IMPASSABLE:
            imp = "\timpassable = yes\n"
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            res, man, cat = "\n\tresources={\n\t}", "1000", "wasteland_sector"
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {vps[p]}\n\t\t}}\n" for p in provs if p in vps)
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (alderaan_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {OWNER[sid]}\n\t\tadd_core_of = {CORE}\n\t}}\n"
                f"\tmanpower = {man}\n\tstate_category = {cat}\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}}\n")
        if sid in old:
            os.remove(old[sid])
        open(f"history/states/{sid}-{PLANET} - {STATE_NAMES[sid].replace(chr(39), '')}.txt", "w", encoding="utf-8",
             newline="\n").write(text)
        cen = np.mean([pc(p) for p in provs], 0)
        main_p = capital_p if sid == CAPITAL else next((p for p in provs if p in vps),
                                                      min(provs, key=lambda p: np.hypot(*(pc(p) - cen))))
        sts[sid] = dict(kind="white" if sid in IMPASSABLE else "open", provinces=provs,
                        coastal=[p for p in provs if prov[p]["coastal"]], main=main_p)
    for sid in set(old) - set(sts):
        os.remove(old[sid])
    place(sts, {p: dict(v, zone="white" if v["state"] in IMPASSABLE else v["zone"]) for p, v in prov.items()},
          newpid, land, m, set(sts) | set(old), port, CAPITAL, rng)
    fprov = set(prov)
    open_p = sorted(p for p, v in prov.items() if v["state"] not in IMPASSABLE)
    for f in glob.glob("history/units/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        if any(int(x) in fprov for x in re.findall(r"naval_base\s*=\s*(\d+)", s)):   # fleets: to the landing field
            rw(f, lambda s_: re.sub(r"\b(naval_base|location)(\s*=\s*)(\d+)\b",
                                    lambda q: q.group(1) + q.group(2) + (str(port) if int(q.group(3)) in fprov else q.group(3)), s_))
        elif any(int(x) in fprov for x in re.findall(r"\blocation\s*=\s*(\d+)", s)):  # armies: on open ground
            rw(f, lambda s_: re.sub(r"\blocation(\s*=\s*)(\d+)\b",
                                    lambda q: "location" + q.group(1) + (str(open_p[int(q.group(2)) % len(open_p)])
                                                                         if int(q.group(2)) in fprov and prov[int(q.group(2))]["state"] in IMPASSABLE
                                                                         else q.group(2)), s_))

    pcom.state_names_loc(STATE_NAMES)

    def fv(s):
        s = re.sub(r'\n ?VICTORY_POINTS_(\d+):\d* "[^"]*"', lambda q: "" if int(q.group(1)) in fprov else q.group(0), s)
        return s.rstrip("\n") + "\n" + "".join(f' VICTORY_POINTS_{p}:0 "{n}"\n' for p, n in vp_names.items())
    rw("localisation/english/victory_points_l_english.yml", fv)
    for sid, st in sorted(sts.items()):
        print(f"{sid:5} {st['kind']:5} {len(st['provinces']):3} provinces  {STATE_NAMES[sid]}")
    return vp_names


def preview(path, newpid, m, prov, groups):
    """--dry: the layout as a PNG (states coloured, impassable dark, province borders) and the counts"""
    from PIL import Image
    ys, xs = np.nonzero(m)
    sl = np.s_[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    sub, k = newpid[sl], 6
    st = np.vectorize(lambda p: prov[p]["state"] if p in prov else 0)(sub)
    img = np.zeros(sub.shape + (3,), np.uint8)
    for sid in np.unique(st[m[sl]]):
        c = np.random.default_rng(int(sid)).integers(70, 230, 3)
        img[(st == sid) & m[sl]] = c // 3 + 20 if sid in IMPASSABLE else c
    big = np.repeat(np.repeat(img, k, 0), k, 1)
    bp = np.repeat(np.repeat(sub, k, 0), k, 1)
    bs = np.repeat(np.repeat(st, k, 0), k, 1)
    edge = np.zeros(bp.shape, bool)
    edge[:-1] |= bp[:-1] != bp[1:]
    edge[:, :-1] |= bp[:, :-1] != bp[:, 1:]
    sedge = np.zeros(bp.shape, bool)
    sedge[:-1] |= bs[:-1] != bs[1:]
    sedge[:, :-1] |= bs[:, :-1] != bs[:, 1:]
    big[edge] = big[edge] * 3 // 4
    big[ndi.binary_dilation(sedge)] = 0
    Image.fromarray(big).save(path)
    imp = sum(1 for v in prov.values() if v["state"] in IMPASSABLE)
    print(f"dry run: {len(prov)} provinces, {len(prov) - imp} passable / {imp} impassable -> {path}")
    for g_ in groups:
        print(f"  {g_['state']:5} {g_['kind']:9} {g_['n']:3} prov {int(g_['mask'].sum()):5} px  {g_['name']}")


if __name__ == "__main__":
    pcom.run(main)
