"""Ord Mantell, the lawless Mid Rim world of casinos, junkyards and bounty hunters, as one battlefield before the Clone
Wars (research: WIPGFX/research/ord_mantell/; Legends first, user 2026-10-20). LEGENDS: a temperate world of plains,
jungles, seas, mesas and volcanic islands under pink-tinged clouds; the population clustered in the low mesas and flat
plains of the arid equatorial region; plateaus peppering the surface (the Ten Mile Plateau); polar tundra of fjords,
glaciers and mountains; huge robotic coal yards and immense junkyard fields - the Scraplands, north of Worlport, with
Jawa squats; Worlport, on the coast of the Worlport continent, the capital in Legends, Corellian in architecture, its
Casino District, Morro Spaceport; casino cities along the southern coast (Savroia, canon); Great Rock a frontier
settlement, Trader's Quarter a city; Avilatan, a volcanic island with lava pools, Mount Avilatan and Fort Garnik.
CANON: Ord Mantell City the capital (the user's choice, 2026-10-20), its old mining tunnels, its junkyards; Freelonn;
Old Ord Mantell City in ruins "on the far side of the planet from Ord Mantell City"; every landmass dotted with
mountain chains; a Republic military world (Legends: founded as an ordnance depot). Owner: REP (as before).
LAYOUT IS A DESIGN CHOICE where the sources are silent: the polar glaciers and fjords along the north edge
(impassable), Ord Mantell City on the eastern plains, Freelonn in the north-eastern foothills, the Mantell Range
(impassable) across the middle, the Scraplands and the Ten Mile Plateau south of it and north of Worlport on the
southern coast with Savroia east along it, Great Rock in the north-western mesas, Old Ord Mantell City far to the west
(the far side from the capital) with Trader's Quarter, the Bright Sea (impassable) in the south-west with Avilatan in
it, joined to the mainland by a chain of shoals.
Canon names: Ord Mantell City, Freelonn, Savroia, Old Ord Mantell City. Legends: Worlport, the Casino District, the
Scraplands, the Ten Mile Plateau, Great Rock, Trader's Quarter, Avilatan, Mount Avilatan, Fort Garnik. Invented: the
Northern Glaciers, the Mantell Range, the Bright Sea, the Avilatan Shoals, the Eastern Plains, the Western Reaches,
the Southern Coast, the North-Eastern Foothills as state names.
    python "WIPGFX/plans & scripts/ord_mantell_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ord_mantell_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 200 province ids are kept (strategic region unchanged); only the pixels move.
Run order: ord_mantell_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (om_*) ->
planet_terrain_gen.py --planet "Ord Mantell" -> military_buildings.py models hod_om -> coruscant_buildings.py wire ->
military_buildings.py place "Ord Mantell" -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Ord Mantell"
ZONES_JSON = "WIPGFX/Assets/ord_mantell_zones.json"
ZONES_PNG = "WIPGFX/Assets/ord_mantell_zones.png"
KIND = {"city": 1, "port": 2, "casino": 3, "town": 4, "ruins": 5, "junk": 6, "mesa": 7, "volcano": 8, "fort": 9,
        "shoals": 10, "plains": 11, "foothills": 12, "scrap": 13, "mesas": 14, "glacier": 15, "mountains": 16, "sea": 17,
        "forest": 18, "crater": 19}
TERRAIN = {"city": "urban", "port": "urban", "casino": "urban", "town": "urban", "ruins": "urban", "junk": "hills",
           "mesa": "hills", "volcano": "mountain", "fort": "hills", "shoals": "marsh", "plains": "plains",
           "foothills": "hills", "scrap": "hills", "mesas": "desert", "glacier": "mountain", "mountains": "mountain",
           "sea": "marsh", "forest": "forest", "crater": "plains"}
SEED = 103
CAPITAL = 103
CAPITAL_VP = "Ord Mantell City"
PORT_STATE = 851                     # Worlport's Morro Spaceport and the southern coast
OWNER = {s: "REP" for s in (103, 851, 852, 853, 854, 855, 856, 857, 1257, 1258, 1259)}
WARP = (0.13, 9)
TARGET_PASSABLE = 132                # user rule: passable provinces outnumber impassable (~132 / 68)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Ord Mantell City", "city", CAPITAL, 4, [("ell", 0.55, -0.08, 0.17, 0.13, -10)]),
    ("Worlport", "port", 851, 3, [("ell", -0.02, 0.66, 0.16, 0.1, 5)]),
    ("Casino District", "casino", 851, 1, [("ell", 0.17, 0.72, 0.07, 0.06, 0)]),
    ("Savroia", "casino", 852, 1, [("ell", 0.46, 0.6, 0.08, 0.07, 20)]),
    ("Scraplands", "junk", 853, 4, [("ell", 0.05, 0.32, 0.22, 0.13, 10)]),
    ("Ten Mile Plateau", "mesa", 853, 1, [("ell", -0.2, 0.22, 0.08, 0.07, 0)]),
    ("Freelonn", "town", 854, 1, [("ell", 0.45, -0.52, 0.08, 0.07, 0)]),
    ("Great Rock", "town", 855, 1, [("ell", -0.42, -0.36, 0.07, 0.06, 0)]),
    ("Old Ord Mantell City", "ruins", 856, 2, [("ell", -0.8, 0.0, 0.1, 0.13, 0)]),
    ("Trader's Quarter", "town", 856, 1, [("ell", -0.52, 0.06, 0.07, 0.06, 0)]),
    ("Mount Avilatan", "volcano", 857, 2, [("ell", -0.58, 0.62, 0.13, 0.09, 10)]),
    ("Fort Garnik", "fort", 857, 1, [("ell", -0.45, 0.6, 0.06, 0.05, 0)]),
    ("Avilatan Shoals", "shoals", 857, 1, [("cap", -0.42, 0.56, -0.32, 0.44, 0.035), ("cap", -0.32, 0.44, -0.2, 0.36, 0.035)]),
    ("Northern Glaciers", "glacier", 1258, 0, [("cap", -0.7, -0.88, 0.7, -0.88, 0.14), ("ell", 0.0, -0.94, 0.5, 0.12, 0)]),
    ("Mantell Range", "mountains", 1259, 0, [("cap", -0.3, -0.5, 0.05, -0.12, 0.1), ("cap", 0.05, -0.12, 0.3, 0.12, 0.08)]),
    ("Bright Sea", "sea", 1257, 0, [("ell", -0.52, 0.58, 0.3, 0.2, -20), ("ell", -0.32, 0.78, 0.14, 0.1, 0)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
# (Avilatan, 857, is its features only: an island has no open ground of its own)
SEEDS = {CAPITAL: ((0.62, 0.0), "plains"), 851: ((0.0, 0.62), "plains"), 852: ((0.6, 0.5), "plains"),
         853: ((0.0, 0.3), "scrap"), 854: ((0.42, -0.6), "foothills"), 855: ((-0.5, -0.42), "mesas"),
         856: ((-0.72, 0.05), "forest")}
STATE_NAMES = {CAPITAL: "Ord Mantell City", 851: "Worlport", 852: "Southern Coast", 853: "Scraplands",
               854: "Freelonn", 855: "Great Rock", 856: "Western Reaches", 857: "Avilatan",
               1257: "Bright Sea", 1258: "Northern Glaciers", 1259: "Mantell Range"}
IMPASSABLE = {1257, 1258, 1259}
VPS = [(CAPITAL, "Ord Mantell City", CAPITAL_VP, 10), (851, "Worlport", "Worlport", 8),
       (851, "Casino District", "Casino District", 2), (852, "Savroia", "Savroia", 3),
       (853, "Scraplands", "Scraplands", 2), (853, "Ten Mile Plateau", "Ten Mile Plateau", 1),
       (854, "Freelonn", "Freelonn", 3), (855, "Great Rock", "Great Rock", 1),
       (856, "Old Ord Mantell City", "Old Ord Mantell City", 2), (856, "Trader's Quarter", "Trader's Quarter", 2),
       (857, "Fort Garnik", "Fort Garnik", 2), (857, "Mount Avilatan", "Mount Avilatan", 1)]

def scars(ctx):
    """war scars on the southern coast (the user, 2026-10-20; Ord Mantell an old military depot fought over since the
    Pius Dea Crusades, Legends): blast craters with raised rims and long scorched trenches across the arid plains
    east of Worlport, re-zoned to the crater ground (zone 19: dark scorched rock, snags, wreckage)"""
    z, rel, rng, yy, xx, sub = ctx["z"].copy(), ctx["rel"], ctx["rng"], ctx["yy"], ctx["xx"], ctx["sub"]
    (cy, cx), R = ctx["zj"]["centre"], ctx["zj"]["radius"]
    U, V = (xx + ctx["sl"][1].start - cx) / R, (yy + ctx["sl"][0].start - cy) / R
    coast = sub & np.isin(z, (11, 13, 12)) & (V > 0.32) & (U > 0.08)              # the southern coast's open ground
    cand = np.argwhere(coast & (ctx["unit_d"] > 2.5))
    hit = np.zeros(z.shape, bool)
    for r, c in cand[rng.choice(len(cand), size=min(16, len(cand)), replace=False)]:     # blast craters
        rad = rng.uniform(1.6, 4.2)
        d = np.hypot(yy - r, xx - c) / rad
        bowl = np.clip(1 - d ** 2, 0, None) * rng.uniform(3, 6)
        rim = np.exp(-((d - 1.05) / 0.25) ** 2) * rng.uniform(1.5, 2.5)
        m = coast & (d < 1.4)
        rel = np.where(m, rel - bowl + rim, rel)
        hit |= m
    for _ in range(5):                                                         # scorched trenches
        r, c = cand[rng.integers(len(cand))]
        a, L = rng.uniform(0, math.pi), rng.uniform(10, 22)
        for t in np.linspace(-L / 2, L / 2, int(L * 2)):
            rr, cc = r + t * math.sin(a), c + t * math.cos(a)
            m = coast & (np.hypot(yy - rr, xx - cc) < 1.0)
            rel = np.where(m, np.minimum(rel, rel - 2.0), rel)
            hit |= m
    z[hit] = 19
    ctx["rel"], ctx["z"] = rel, z


# terrain (planet_terrain_gen.py --planet "Ord Mantell"). Heights in heightmap steps above the base. Arid equatorial
# plains and low mesas, the Scraplands' junk ground (graphical terrain SCRAP / SCRAP_TOWN, Raxus Prime's junk props
# 69-72), green foothills and western forests (188 conifers), scrub (189) on the plains, the polar glaciers, the
# volcanic island with lava; Ord Mantell's towns (map/cities.txt 61, om_city) on the plains and coasts
TERRAIN_CFG = dict(
    seed=103, base=4, rough=2, open=(10, 11, 12, 13, 14, 18),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("flat", 5), tex="URBAN"),                                                  # Ord Mantell City
        2: dict(relief=("flat", 4), tex="URBAN"),                                                  # Worlport
        3: dict(relief=("flat", 4), tex="URBAN"),                                                  # casino cities
        4: dict(relief=("rolling", 5, 2, 6), tex=["URBAN", ("SAVANNA", ">", 0.6)]),                # towns
        5: dict(relief=("rolling", 5, 2, 6), tex=["ROCK2", ("URBAN", ">", 0.5)], props=[(189, 0.1)]),   # the old city
        6: dict(relief=("rolling", 5, 3, 5), tex=["SCRAP", ("SCRAP_TOWN", ">", 0.75)],
                props=[(69, 0.12), (70, 0.08), (71, 0.06), (72, 0.05)]),                         # the junkyards
        7: dict(relief=("ramp_top", 13, 5, 3), tex=["BROWN", ("ROCK2", ">", 0.6)]),             # Ten Mile Plateau
        8: dict(relief=("ramp_top", 16, 7, 3), tex=["ROCK", ("LAVA", ">", 0.62)]),              # Mount Avilatan
        9: dict(relief=("rolling", 6, 3, 5), tex=["ROCK2", ("BROWN", ">", 0.5)]),               # Fort Garnik
        10: dict(relief=("flat", 0.6), tex=["WATER", ("SAND", ">", 0.6)]),                        # the shoals
        11: dict(relief=("rolling", 4, 2, 6), tex=["SAVANNA", ("BROWN", ">", 0.55), (13, ">", 0.9)],
                 props=[(189, 0.1)]),                                                              # arid plains
        12: dict(relief=("rolling", 9, 6, 4), tex=["GRASSHILL", ("ROCK", ">", 0.6), (13, ">", 0.92)],
                 props=[(188, 0.2), (189, 0.05)]),                                                 # foothills
        13: dict(relief=("rolling", 4, 3, 5), tex=["SCRAP", ("BROWN", ">", 0.55), ("SCRAP_TOWN", ">", 0.9)],
                 props=[(69, 0.05), (71, 0.03), (189, 0.04)]),                                    # scrap plains
        14: dict(relief=("spires", 5, 3, 0.03, (2.0, 4.0), (10, 22)), tex=["BROWN", ("SAND", ">", 0.55), (13, ">", 0.93)],
                 props=[(189, 0.06)]),                                                             # the mesas
        15: dict(relief=("mesa", 6, 16, 2.0, (4, 0.6)), tex=["SNOWROCK", ("SNOWSAND", ">", 0.5)]),   # glaciers
        16: dict(relief=("spires", 16, 9, 0.08, (1.5, 3.0), (24, 46)), tex=["ROCK", ("BROWNMTN", ">", 0.55)],
                 props=[(188, 0.04)]),                                                             # the range
        17: dict(relief=("flat", 0.3), tex="WATER"),                                               # the Bright Sea
        18: dict(relief=("rolling", 6, 4, 5), tex=["FOREST", ("GRASS", ">", 0.65), (13, ">", 0.92)],
                 props=[(188, 0.5)]),                                                              # western forests
        19: dict(tex=["ROCK2", ("BROWN", ">", 0.6)], props=[(176, 0.15), (71, 0.05), (72, 0.04)]),   # war scars (hook)
    },
    hook=scars,
    steep=("ROCK", 6, (11, 12, 13, 14, 18)),
    city={1: 61, 2: 61, 3: 61, 4: 61, 11: 61, 12: 61, 14: 61, 18: 61},   # cities.txt 61 Ord Mantell towns
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.62, 0.52, 0.48), 2: (0.6, 0.5, 0.46), 3: (0.62, 0.5, 0.5), 4: (0.6, 0.52, 0.44), 5: (0.5, 0.46, 0.42),
            6: (0.42, 0.36, 0.32), 7: (0.62, 0.46, 0.34), 8: (0.36, 0.3, 0.28), 9: (0.5, 0.44, 0.38),
            10: (0.3, 0.44, 0.48), 11: (0.7, 0.58, 0.42), 12: (0.44, 0.5, 0.34), 13: (0.5, 0.44, 0.38),
            14: (0.7, 0.52, 0.38), 15: (0.9, 0.9, 0.94), 16: (0.5, 0.44, 0.4), 17: (0.2, 0.34, 0.42),
            18: (0.26, 0.42, 0.26), 19: (0.36, 0.3, 0.26)},
)

# models (military_buildings.py place "Ord Mantell"): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_om_city", "hod_om_worlport", "hod_om_junkyard", "hod_om_oldcity", "hod_om_garnik"},
    items=[("hod_om_city", 1.0, ("at_vp", CAPITAL_VP)), ("hod_om_worlport", 1.0, ("at_vp", "Worlport")),
           ("hod_om_junkyard", 1.0, ("at_vp", "Scraplands")), ("hod_om_oldcity", 1.0, ("at_vp", "Old Ord Mantell City")),
           ("hod_om_garnik", 0.9, ("at_vp", "Fort Garnik"))],
    clear={"hod_om_city": 8.0, "hod_om_worlport": 8.0, "hod_om_junkyard": 7.0, "hod_om_oldcity": 6.5, "hod_om_garnik": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ord_mantell_map.py)\n{imp}"
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
