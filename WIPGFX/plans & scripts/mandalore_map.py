"""Mandalore, the homeworld of the Mandalorians, as one battlefield before the Clone Wars, after the LEGENDS article
(user, 2026-10-20: "redo the planet to follow the legends version"; research: WIPGFX/research/mandalore/, the
Mandalore/Legends, Keldabe/Legends and Sundari/Legends pages). LEGENDS: "lush veshok tree forests, dense jungle,
sprawling hills and grassland well suited to farming, inhospitable deserts of white sand, and numerous rivers, lakes,
and seas"; veshok forest over the northern hemisphere (the Olankur region) nearly to the polar ice caps; galek trees
with silver leaves and golden amber ferns; the tropics further south (varos fruit); mythosaur skeletons left to bleach;
the white deserts made by the Mandalorian Excision (738 BBY). Keldabe, the clans' capital, 45 degrees north on a flat
granite hill nearly encircled by a bend of the Kelita River (a natural moat crossed by bridges, a stone balustrade
over the drop), packed streets of every style, the hundred-metre MandalMotors tower with its mythosaur skull logo, the
Oyu'baat tapcaf on the ancient square, the spaceport; Bralsin a suburb on a hill at the edge of the broad, shallow
Kelita valley of farms and woods; Shuror a small town; Norg Bral a hill-fort town of Clan Bralor; Enceri a remote
trading post; Sundari, the New Mandalorian capital recognised by the Republic, a black-domed bio-cube city out on the
flat white desert over one of the largest beskar mines, ringed by smaller cube cities; the Tokursh region rich in
beskar; the City of Bone, a failed amusement park shaped like a mythosaur skeleton near Keldabe. Owner: MAN (as
before); the game capital stays Sundari (user, 2026-10-20). User: keep the Death Watch camp (in Legends their base was
on Concordia: here a camp in the wastes, a design choice); no shipyards, no Kyrimorut (built in the war).
LAYOUT IS A DESIGN CHOICE where the sources are silent: the polar ice cap along the north edge (impassable), the
Olankur forest below it, Keldabe in the Kelita's bend in the north-centre with the river running west through the
Kelita valley's farms, the City of Bone beside Enceri (user, 2026-10-20), the downs east of Keldabe, Norg Bral in the north-eastern hills, Shuror on the
central hills, Sundari on the southern white desert with the White Wastes (impassable dunes) east of it, the Tokursh
beskar badlands in the east, the Death Watch camp in the south-eastern wastes, Enceri on the western frontier, the
tropical jungle in the south-west round the Varos Sea (impassable).
Legends names: Keldabe, the Kelita River, MandalMotors, the Oyu'baat, Bralsin, Shuror, Norg Bral, Enceri, Sundari, the
Olankur region, Tokursh, the City of Bone. Invented: Bralsin Downs, Keldabe Downs, Shuror Hills, the Eastern Wastes,
the Western Jungle, the Varos Coast, the Varos Sea, the White Wastes, the Northern Ice Cap, the Death Watch Camp.
    python "WIPGFX/plans & scripts/mandalore_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/mandalore_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 203 province ids are kept (strategic region unchanged); only the pixels move.
Run order: mandalore_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (man_*) ->
planet_terrain_gen.py --planet Mandalore -> military_buildings.py models hod_man -> military_buildings.py place
Mandalore -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Mandalore"
ZONES_JSON = "WIPGFX/Assets/mandalore_zones.json"
ZONES_PNG = "WIPGFX/Assets/mandalore_zones.png"
KIND = {"dome": 1, "city": 2, "fort": 3, "mine": 4, "camp": 5, "town": 6, "river": 7, "wastes": 8, "badlands": 9,
        "forest": 10, "farms": 11, "hills": 12, "dunes": 13, "ice": 14, "bone": 15, "grass": 16, "jungle": 17, "sea": 18}
TERRAIN = {"dome": "urban", "city": "urban", "fort": "urban", "mine": "hills", "camp": "hills", "town": "urban",
           "river": "marsh", "wastes": "desert", "badlands": "hills", "forest": "forest", "farms": "plains",
           "hills": "hills", "dunes": "desert", "ice": "mountain", "bone": "plains", "grass": "plains",
           "jungle": "jungle", "sea": "marsh"}
SEED = 96
CAPITAL = 240
CAPITAL_VP = "Sundari"
PORT_STATE = 96
OWNER = {s: "MAN" for s in (96, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 1221, 1222, 1254)}
WARP = (0.13, 9)
TARGET_PASSABLE = 135                # user rule: passable provinces outnumber impassable (~135 / 68)
STRAIGHT = {"city", "river"}         # Keldabe and the Kelita's bend round it: unwarped, so the moat fits the hill
# the Kelita's bend round Keldabe (centre -0.15, -0.45), open to the north where the hill meets the forest
_BEND = [(-0.29, -0.6), (-0.36, -0.46), (-0.31, -0.31), (-0.15, -0.25), (0.01, -0.31), (0.06, -0.46), (0.0, -0.6)]
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Sundari", "dome", CAPITAL, 4, [("ell", 0.06, 0.3, 0.2, 0.16, 0)]),
    ("Keldabe", "city", 241, 3, [("ell", -0.15, -0.45, 0.17, 0.15, 0)]),
    ("Kelita Bend", "river", 241, 2, [("cap", *a, *b, 0.03) for a, b in zip(_BEND, _BEND[1:])]),
    ("Lower Kelita", "river", 244, 2, [("cap", -0.36, -0.46, -0.6, -0.38, 0.03), ("cap", -0.6, -0.38, -0.88, -0.26, 0.03)]),
    ("Bralsin", "town", 250, 1, [("ell", -0.47, -0.2, 0.07, 0.06, 0)]),
    ("City of Bone", "bone", 246, 1, [("ell", -0.6, -0.04, 0.1, 0.08, 15)]),   # beside Enceri (user, 2026-10-20)
    ("Norg Bral", "fort", 245, 1, [("ell", 0.58, -0.36, 0.08, 0.07, 0)]),
    ("Shuror", "town", 247, 1, [("ell", 0.3, -0.06, 0.08, 0.07, 0)]),
    ("Enceri", "town", 246, 1, [("ell", -0.72, 0.1, 0.07, 0.06, 0)]),
    ("Beskar Mines", "mine", 242, 2, [("ell", 0.74, 0.12, 0.12, 0.09, 20)]),
    ("Death Watch Camp", "camp", 248, 1, [("ell", 0.44, 0.68, 0.11, 0.09, 0)]),
    ("White Wastes", "dunes", 1221, 0, [("ell", 0.44, 0.32, 0.2, 0.14, 20), ("ell", 0.28, 0.52, 0.12, 0.09, 0)]),
    ("Northern Ice Cap", "ice", 1222, 0, [("cap", -0.7, -0.88, 0.7, -0.88, 0.13), ("ell", 0.05, -0.93, 0.5, 0.13, 0)]),
    ("Varos Sea", "sea", 1254, 0, [("ell", -0.46, 0.6, 0.24, 0.15, -25), ("ell", -0.62, 0.4, 0.1, 0.08, 0)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.04, 0.38), "wastes"), 241: ((-0.08, -0.68), "forest"), 244: ((-0.68, -0.4), "farms"),
         250: ((-0.45, -0.16), "farms"), 243: ((0.3, -0.56), "grass"), 245: ((0.62, -0.44), "hills"),
         247: ((0.25, -0.1), "hills"), 249: ((-0.48, -0.7), "forest"), 246: ((-0.78, 0.12), "grass"),
         242: ((0.82, 0.08), "badlands"), 248: ((0.55, 0.62), "badlands"), 251: ((-0.78, 0.42), "jungle"),
         96: ((-0.12, 0.76), "jungle")}
STATE_NAMES = {CAPITAL: "Sundari", 241: "Keldabe", 244: "Kelita Valley", 250: "Bralsin Downs", 243: "Keldabe Downs",
               245: "Norg Bral", 247: "Shuror Hills", 249: "Olankur", 246: "Enceri", 242: "Tokursh",
               248: "Eastern Wastes", 251: "Western Jungle", 96: "Varos Coast", 1221: "White Wastes",
               1222: "Northern Ice Cap", 1254: "Varos Sea"}
IMPASSABLE = {1221, 1222, 1254}
VPS = [(CAPITAL, "Sundari", CAPITAL_VP, 10), (241, "Keldabe", "Keldabe", 8), (250, "Bralsin", "Bralsin", 1),
       (246, "City of Bone", "City of Bone", 2), (243, "grass", "Keldabe Downs", 1), (245, "Norg Bral", "Norg Bral", 2), (247, "Shuror", "Shuror", 1),
       (246, "Enceri", "Enceri", 1), (242, "Beskar Mines", "Tokursh Beskar Mines", 3),
       (248, "Death Watch Camp", "Death Watch Camp", 2), (244, "farms", "Kelita Valley", 1),
       (249, "forest", "Olankur", 1), (251, "jungle", "Western Jungle", 1), (96, "jungle", "Varos Coast", 1)]

# terrain (planet_terrain_gen.py --planet Mandalore). Heights in heightmap steps above the base. The Legends world:
# veshok forest (flora 148) with galek groves (181) and amber ferns (182) in the north, farms and grassland in the
# Kelita valley, jungle of varos trees (183) in the south-west, the Excision's white desert with glassy shards (149)
# and bleached mythosaur bones (178); the cube cities (map/cities.txt 44, man_dome) round Sundari, the clan towns (45,
# man_town) in the green north; Keldabe on its granite hill in the river's bend
TERRAIN_CFG = dict(
    seed=96, base=4, rough=2, open=(8, 9, 10, 11, 12, 16, 17),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("flat", 5), tex=["SNOWSAND", ("SAND", ">", 0.7), (13, ">", 0.45)]),                       # Sundari
        2: dict(relief=("ramp_top", 13, 7, 3), tex=["ROCK", ("GRASSHILL", ">", 0.7)]),           # Keldabe's granite hill
        3: dict(relief=("ramp_top", 11, 6, 4), tex=["GRASSHILL", ("ROCK", ">", 0.6), (13, ">", 0.6)], props=[(148, 0.08)]),   # Norg Bral
        4: dict(relief=("rolling", 5, 2, 5), tex=["ROCK2", ("SAND", ">", 0.6)]),                  # beskar mines
        5: dict(relief=("rolling", 6, 2, 5), tex=["ROCK2", ("SNOWSAND", ">", 0.55)], props=[(149, 0.1)]),   # the camp
        6: dict(relief=("rolling", 6, 2, 6), tex=["GRASS", (13, ">", 0.3)], props=[(181, 0.05)]),   # clan towns
        7: dict(relief=("flat", 0.3), tex="WATER"),                                                # the Kelita
        8: dict(relief=("rolling", 4, 2.5, 6), tex=["SNOWSAND", ("SAND", ">", 0.6), (13, ">", 0.9)],
                props=[(149, 0.08), (178, 0.03)]),                                                 # the white wastes
        9: dict(relief=("spires", 6, 3, 0.03, (2.0, 3.5), (8, 18)), tex=["ROCK2", ("SAND", ">", 0.55), (13, ">", 0.92)],
                props=[(149, 0.05), (178, 0.03)]),                                                 # badlands
        10: dict(relief=("rolling", 7, 5, 5), tex=["FOREST", ("DFOREST", ">", 0.55), ("GRASSHILL", ">", 0.85), (13, ">", 0.93)],
                 props=[(148, 0.55), (182, 0.15)], clusters=[(5, 0.55, [(181, 0.8), (182, 0.3)])]),   # veshok forest
        11: dict(relief=("rolling", 4, 2, 6), tex=["FARM", ("GRASS", ">", 0.55), (13, ">", 0.85)],
                 props=[(148, 0.05)], clusters=[(6, 0.6, [(148, 0.8)])]),                         # Kelita farms
        12: dict(relief=("rolling", 9, 6, 4), tex=["GRASSHILL", ("ROCK", ">", 0.62), (13, ">", 0.88)],
                 props=[(148, 0.12), (181, 0.06)]),                                                # hills
        13: dict(relief=("rolling", 5, 4, 4), tex=["SNOWSAND", ("DUNES", ">", 0.5)], props=[(149, 0.04), (178, 0.04)]),
        14: dict(relief=("mesa", 6, 16, 2.0, (4, 0.6)), tex=["SNOWSAND", ("SNOWROCK", ">", 0.55)]),   # the ice cap
        15: dict(relief=("rolling", 4, 2, 6), tex=["GRASS", ("SAVANNA", ">", 0.6)], props=[(182, 0.05)]),   # City of Bone
        16: dict(relief=("rolling", 5, 3, 6), tex=["GRASS", ("SAVANNA", ">", 0.6), ("GRASSHILL", ">", 0.85), (13, ">", 0.9)],
                 props=[(182, 0.12)], clusters=[(4, 0.5, [(181, 0.7)])]),                         # grassland, downs
        17: dict(relief=("rolling", 5, 3, 5), tex=["JUNGLE", ("JUNGLE2", ">", 0.5)], props=[(183, 0.6), (182, 0.15)]),
        18: dict(relief=("flat", 0.3), tex="WATER"),                                               # the Varos Sea
    },
    steep=("ROCK", 6, (8, 9, 10, 11, 12, 16, 17)),
    city={1: 44, 8: 44, 9: 44, 6: 45, 3: 45, 10: 45, 11: 45, 12: 45, 16: 45},   # cities.txt 44 cubes, 45 towns
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.84, 0.82, 0.78), 2: (0.5, 0.5, 0.46), 3: (0.46, 0.5, 0.36), 4: (0.6, 0.58, 0.54),
            5: (0.7, 0.68, 0.64), 6: (0.42, 0.5, 0.32), 7: (0.2, 0.32, 0.38), 8: (0.86, 0.84, 0.78),
            9: (0.66, 0.62, 0.56), 10: (0.2, 0.34, 0.2), 11: (0.48, 0.56, 0.3), 12: (0.42, 0.48, 0.32),
            13: (0.9, 0.88, 0.82), 14: (0.9, 0.92, 0.94), 15: (0.5, 0.54, 0.34), 16: (0.46, 0.56, 0.3),
            17: (0.16, 0.34, 0.16), 18: (0.16, 0.3, 0.38)},
)

# models (military_buildings.py place Mandalore): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_man_sundari", "hod_man_keldabe", "hod_man_beskar", "hod_man_dwcamp", "hod_man_cityofbone",
                "hod_man_norgbral"},
    items=[("hod_man_sundari", 1.0, ("at_vp", CAPITAL_VP)), ("hod_man_keldabe", 1.6, ("zone_centre", 2)),
           ("hod_man_beskar", 1.0, ("at_vp", "Tokursh Beskar Mines")), ("hod_man_dwcamp", 0.9, ("at_vp", "Death Watch Camp")),
           ("hod_man_cityofbone", 1.0, ("at_vp", "City of Bone")), ("hod_man_norgbral", 0.9, ("at_vp", "Norg Bral"))],
    clear={"hod_man_sundari": 9.0, "hod_man_keldabe": 10.5, "hod_man_beskar": 5.0, "hod_man_dwcamp": 4.0,
           "hod_man_cityofbone": 6.0, "hod_man_norgbral": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (mandalore_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {OWNER[sid]}\n\t\tadd_core_of = {OWNER[sid]}\n\t}}\n"
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
