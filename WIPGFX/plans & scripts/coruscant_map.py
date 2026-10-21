"""Coruscant, capital of the Republic, as one battlefield before the Clone Wars (research: WIPGFX/research/coruscant/).
TRACED FROM THE USER'S PLAN WIPGFX/1.png (the user, 2026-10-20: follow the picture, nothing round, the neighbourhood of
the important buildings - passable round the landmarks and along the avenues, the dense city between them impassable;
all of it the Republic's): every feature below is placed by its pixel position in 1.png (2000 x 1744 view; P() maps
it onto the disc, the picture filling 85% of the radius). The buildings follow the user's renders WIPGFX/2-5.png.
In 1.png: the Senate Building (the great round roof) with the Senate Plaza south of it and the long walkway east (the
Processional Way, Legends) to the central boulevard; the Senate District's ring of avenues with its stepped round
building in the middle (the Galaxies Opera House, canon) ; the Entertainment District north-west with the Outlander Club
(Legends); Padme's apartment in 500 Republica (canon) west; the Commerce District north-east (CoCo Town, canon) with Dex's
Diner (canon) and its great arched exchange; the Jedi Temple (canon) and its precinct south-east; three flared cone
towers (top, top right, centre right; the user, 2026-10-20: no spires there - the centre right one is the
COMPOR arcology instead, the building that later houses the ISB); two diamond plazas (the one by the Senate is Monument Plaza, canon).
Design choices beyond 1.png: the Republic Executive Building (canon) in the square block east of the Senate, the Galactic
Courts (Legends) in the square block east of the Senate District, Level 1313 (canon) at the glowing shaft south-east
of it, the Works (canon) and the Southern Underground (Legends) in the plain south, the Financial District (canon)
between Commerce and the Temple; the Temple's interior as three bays (the Archives, the High Council Chamber, the Room
of a Thousand Fountains); the impassable megablocks.
The COMPOR arcology (Legends: the Commission for the Protection of the Republic, formed in the Clone Wars; canon: the
COMPNOR arcology of the Federal District houses the ISB Central Office, a complex the size of several city blocks).
The spaceports (the user, 2026-10-21: lanes that land where they point, a planet that is hard to invade): a ring of
megablocks walls the whole rim, broken only by three one-province spaceports, each facing the world its hyperlane
runs to (Esseles north, Anaxes east, Tython south) and fortified with coastal bunkers; Eastport (Legends) takes the
fleet's port.
Invented names: the Commerce Exchange, the five Megablocks, Northport, Southport.
    python "WIPGFX/plans & scripts/coruscant_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/coruscant_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 197 province ids are kept (strategic region unchanged); only the pixels move.
Run order: coruscant_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> planet_terrain_gen.py --planet
Coruscant -> military_buildings.py coruscant_atlas, models hod_cos_ -> coruscant_buildings.py wire -> military_buildings.py
place Coruscant -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Coruscant"
ZONES_JSON = "WIPGFX/Assets/coruscant_zones.json"
ZONES_PNG = "WIPGFX/Assets/coruscant_zones.png"
FIT = 0.85                           # the picture's half-width fills this share of the disc's radius


def P(x, y):
    """a point of 1.png (2000 x 1744 view) -> the disc's normalised (u, v)"""
    return (x - 1005) / 990 * FIT, (y - 862) / 990 * FIT


def Rc(x0, y0, x1, y1):
    """a rectangle of 1.png"""
    (u0, v0), (u1, v1) = P(x0, y0), P(x1, y1)
    return ("rect", (u0 + u1) / 2, (v0 + v1) / 2, abs(u1 - u0) / 2, abs(v1 - v0) / 2, 0)


def Dm(x, y, r):
    """a diamond (a square turned 45 degrees) of 1.png, r = centre to corner"""
    u, v = P(x, y)
    return ("rect", u, v, r / 990 * FIT / math.sqrt(2), r / 990 * FIT / math.sqrt(2), 45)


def Ci(x, y, r):
    """a round building of 1.png (the Senate, the Opera House, the spires: round in the picture too)"""
    u, v = P(x, y)
    return ("ell", u, v, r / 990 * FIT, r / 990 * FIT, 0)


def Oc(x, y, r):
    """an octagon of 1.png (the Senate District's ring of avenues, drawn straight-edged)"""
    u, v = P(x, y)
    h = r / 990 * FIT * math.cos(math.pi / 8)
    return [("rect", u, v, h, h, 0), ("rect", u, v, h, h, 45)]


KIND = {"senate": 1, "temple": 2, "landmark": 3, "avenue": 4, "spire": 5, "works": 6, "underworld": 7, "district": 8,
        "towers": 9, "blocks": 10, "spaceport": 11}
TERRAIN = {"senate": "urban", "temple": "urban", "landmark": "urban", "avenue": "urban", "spire": "urban", "works": "urban",
           "underworld": "urban", "district": "urban", "towers": "urban", "blocks": "mountain", "spaceport": "urban"}
SEED = 1
CAPITAL = 1
CAPITAL_VP = "Senate Building"
CORE = "REP"
PORT_STATE = 122                     # CoCo Town, which reaches the rim (the megablocks wall the rest)
OWNER = {s: "REP" for s in (1, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 1307, 1308, 1309, 1310, 1311)}
WARP = (0.025, 9)
TARGET_PASSABLE = 125                # user rule: passable provinces outnumber impassable (~125 / 72, the blocks are big)
RIM = 0.88                           # only the spaceports reach past this share of the radius: the rest of the rim is megablocks
SPACEPORT_BUNKER = 3                 # coastal bunker level on every spaceport
STRAIGHT = {"spaceport", "senate", "temple", "landmark", "avenue", "spire", "works", "underworld", "district", "towers"}
FEATURES = [
    # the spaceports: the only landing grounds on the rim, each facing its hyperlane
    ("Northport", "spaceport", 125, 1, [Rc(760, -330, 900, -150)]),
    ("Eastport", "spaceport", 122, 1, [Rc(1800, 300, 2250, 440)]),
    ("Southport", "spaceport", 123, 1, [Rc(1140, 1850, 1280, 2150)]),
    # the landmarks, at their places in 1.png
    ("Senate Building", "senate", CAPITAL, 1, [Ci(765, 470, 115)]),
    ("Senate Plaza", "avenue", CAPITAL, 1, [Rc(690, 580, 840, 700)]),
    ("Processional Way", "avenue", CAPITAL, 3, [Rc(885, 455, 1262, 510)]),
    ("Republic Executive Building", "landmark", CAPITAL, 1, [Rc(905, 370, 995, 465)]),
    ("Monument Plaza", "landmark", CAPITAL, 1, [Dm(565, 400, 85)]),
    ("Galaxies Opera House", "landmark", 126, 2, [Ci(770, 905, 110)]),
    ("COMPOR Arcology", "landmark", CAPITAL, 2, [Rc(990, 560, 1180, 760)]),
    ("Galactic Courts", "landmark", 126, 1, [Rc(1120, 920, 1215, 1005)]),
    ("Level 1313", "underworld", 130, 2, [Rc(1130, 1075, 1240, 1185)]),
    ("Jedi Archives", "temple", 128, 1, [Rc(1350, 1175, 1440, 1440)]),
    ("Jedi High Council Chamber", "temple", 128, 1, [Rc(1440, 1175, 1530, 1440)]),
    ("Room of a Thousand Fountains", "temple", 128, 1, [Rc(1530, 1175, 1620, 1440)]),
    ("Dex's Diner", "landmark", 122, 1, [Rc(1445, 515, 1535, 580)]),
    ("Commerce Exchange", "landmark", 122, 1, [Rc(1330, 660, 1525, 745)]),
    ("Outlander Club", "landmark", 127, 1, [Rc(295, 390, 385, 450)]),
    ("500 Republica", "landmark", 131, 1, [Rc(315, 760, 405, 840)]),
    ("The Works", "works", 123, 3, [Rc(820, 1420, 1120, 1620)]),
    # the districts' open cores and avenues (provinces sized from TARGET_PASSABLE); what is left is megablocks
    ("Federal District", "district", CAPITAL, 0, [Rc(540, 330, 1270, 560), Rc(650, 560, 900, 720)]),
    ("Senate District", "district", 126, 0, Oc(770, 890, 300) + [Rc(990, 590, 1170, 745), Rc(1060, 880, 1262, 1040)]),
    ("Spaceport District", "towers", 125, 0, [Rc(760, -260, 1060, 330)]),
    ("Entertainment District", "towers", 127, 0, [Rc(130, 170, 540, 480)]),
    ("Arts District", "district", 131, 0, [Rc(250, 700, 490, 1010), Rc(395, 470, 425, 700), Dm(365, 955, 90)]),
    ("CoCo Town", "towers", 122, 0, [Rc(1262, 180, 1820, 600), Rc(1300, 600, 1545, 760), Rc(1262, 470, 1835, 515),
                                     Rc(1560, -260, 1780, 200)]),
    ("Financial District", "towers", 129, 0, [Rc(1262, 760, 1860, 960)]),
    ("Temple Precinct", "district", 128, 0, [Rc(1262, 960, 1990, 1500)]),
    ("Works District", "district", 123, 0, [Rc(700, 1180, 1300, 1900)]),
    ("Southern Underground", "district", 124, 0, [Rc(250, 1150, 700, 1450)]),
    ("Level 1313 Shaft", "underworld", 130, 0, [Rc(1110, 1040, 1262, 1240)]),
]
# the megablocks: everything else, by nearest seed
SEEDS = {1307: (P(450, 40), "blocks"), 1308: (P(40, 700), "blocks"), 1309: (P(350, 1700), "blocks"), 1310: (P(1960, 700), "blocks"),
         1311: (P(1700, -150), "blocks")}   # the rim arc between Northport and Eastport
STATE_NAMES = {CAPITAL: "Federal District", 122: "CoCo Town", 123: "The Works", 124: "Southern Underground",
               125: "Spaceport District", 126: "Senate District", 127: "Entertainment District", 128: "Temple Precinct",
               129: "Financial District", 130: "Level 1313", 131: "Arts District", 1307: "Northern Megablocks",
               1308: "Western Megablocks", 1309: "Southern Megablocks", 1310: "Eastern Megablocks", 1311: "North-eastern Megablocks"}
IMPASSABLE = {1307, 1308, 1309, 1310, 1311}
VPS = [(CAPITAL, "Senate Building", CAPITAL_VP, 50), (CAPITAL, "Senate Plaza", "Senate Plaza", 2),
       (CAPITAL, "Processional Way", "Processional Way", 3), (CAPITAL, "Republic Executive Building", "Republic Executive Building", 10),
       (CAPITAL, "Monument Plaza", "Monument Plaza", 5), (126, "Galaxies Opera House", "Galaxies Opera House", 5),
       (CAPITAL, "COMPOR Arcology", "COMPOR Arcology", 5), (126, "Galactic Courts", "Galactic Courts", 3), (130, "Level 1313", "Level 1313", 3),
       (128, "Jedi High Council Chamber", "Jedi Temple", 20), (128, "Jedi Archives", "Jedi Archives", 5),
       (128, "Room of a Thousand Fountains", "Room of a Thousand Fountains", 2), (122, "Dex's Diner", "Dex's Diner", 2),
       (122, "Commerce Exchange", "Commerce Exchange", 3), 
       (125, "Northport", "Northport", 2), (122, "Eastport", "Eastport", 3), (123, "Southport", "Southport", 2),
       (125, "Spaceport District", "Spaceport District", 3), (127, "Outlander Club", "Outlander Club", 3), (131, "500 Republica", "500 Republica", 5),
       (123, "The Works", "The Works", 5), (129, "Financial District", "Financial District", 5),
       (124, "Southern Underground", "Southern Underground", 2), (127, "Entertainment District", "Entertainment District", 2)]

TERRAIN_CFG = dict(
    seed=1, base=4, rough=1, open=(4, 8, 9, 11),
    zones={
        1: dict(relief=("flat", 6), tex="URBAN"),                                                     # the Senate
        2: dict(relief=("flat", 6), tex="URBAN"),                                                     # the Temple
        3: dict(relief=("flat", 5), tex="URBAN"),                                                     # the landmarks
        4: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.85)]),                             # avenues, plazas
        5: dict(relief=("flat", 5), tex="URBAN"),                                                     # the spires
        11: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.85)]),                            # the spaceports
        6: dict(relief=("flat", 4), tex=["URBAN", ("BROWN", ">", 0.6)]),                              # the Works
        7: dict(relief=("flat", 3), tex=["URBAN", ("ROCK2", ">", 0.5)]),                              # Level 1313
        8: dict(relief=("flat", 5), tex=["URBAN", (13, ">", 0.4)]),                                   # the districts
        9: dict(relief=("flat", 5), tex=["URBAN", (13, ">", 0.3)]),                                   # the tower districts
        10: dict(relief=("rolling", 9, 2, 3), tex=["URBAN", (13, ">", 0.15)]),                        # the megablocks
    },
    city={8: 81, 9: 81, 10: 81, 6: 81, 7: 81},   # map/cities.txt 81: Coruscant's towers (cos_town), fewer and bigger
    prop_clear=1.5,
    lights=dict(zones=(8, 9, 10, 6, 7), rgb=(1.0, 0.56, 0.18), density=0.22, mix=0.85),   # Coruscant's orange glow
    colors={1: (0.62, 0.62, 0.64), 2: (0.66, 0.64, 0.6), 3: (0.58, 0.58, 0.6), 4: (0.64, 0.64, 0.66), 5: (0.56, 0.56, 0.58),
            6: (0.46, 0.44, 0.42), 7: (0.36, 0.36, 0.4), 8: (0.56, 0.56, 0.58), 9: (0.58, 0.58, 0.6), 10: (0.44, 0.44, 0.47),
            11: (0.64, 0.64, 0.66)},
)

PLACEMENT = dict(
    new_models={"hod_cos_senate", "hod_cos_temple", "hod_cos_executive", "hod_cos_courts", "hod_cos_processional",
                "hod_cos_monument", "hod_cos_republica", "hod_cos_opera", "hod_cos_outlander", "hod_cos_compor", "hod_cos_works",
                "hod_cos_level1313", "hod_cos_diner", "hod_cos_exchange"},
    items=[("hod_cos_senate", 1.0, ("at_vp", CAPITAL_VP)), ("hod_cos_temple", 1.0, ("at_vp", "Jedi Temple")),
           ("hod_cos_executive", 0.8, ("at_vp", "Republic Executive Building")), ("hod_cos_courts", 0.8, ("at_vp", "Galactic Courts")),
           ("hod_cos_processional", 1.0, ("at_vp", "Processional Way")), ("hod_cos_monument", 0.8, ("at_vp", "Monument Plaza")),
           ("hod_cos_republica", 0.8, ("at_vp", "500 Republica")), ("hod_cos_opera", 1.0, ("at_vp", "Galaxies Opera House")),
           ("hod_cos_outlander", 0.8, ("at_vp", "Outlander Club")),
           ("hod_cos_compor", 1.0, ("at_vp", "COMPOR Arcology")),
           ("hod_cos_works", 1.0, ("at_vp", "The Works")), ("hod_cos_level1313", 0.8, ("at_vp", "Level 1313")),
           ("hod_cos_diner", 0.6, ("at_vp", "Dex's Diner")), ("hod_cos_exchange", 0.9, ("at_vp", "Commerce Exchange"))],
    clear={"hod_cos_senate": 7.0, "hod_cos_temple": 7.5, "hod_cos_executive": 3.0, "hod_cos_courts": 3.0,
           "hod_cos_processional": 4.0, "hod_cos_monument": 3.5, "hod_cos_republica": 3.0, "hod_cos_opera": 6.0,
           "hod_cos_outlander": 3.0, "hod_cos_compor": 5.5, "hod_cos_works": 6.0, "hod_cos_level1313": 3.0, "hod_cos_diner": 2.0,
           "hod_cos_exchange": 4.0},
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
    inner = np.hypot(U0, V0) < RIM
    fid = np.full(sm.shape, -1, np.int32)
    feats = []
    for name, k, sid, n, shapes in FEATURES:
        feats.append((name, k, sid, n))
        u_, v_ = (U0, V0) if k in STRAIGHT else (U, V)
        fid[sm & (fid < 0) & (inner | (k == "spaceport")) & np.any([shape(s_, u_, v_) for s_ in shapes], 0)] = len(feats) - 1
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
        pb = {p: {"coastal_bunker": SPACEPORT_BUNKER} for p in provs if prov[p]["zone"] == "spaceport"}
        if sid == PORT_STATE:                                            # the fleet's port and yards: the landing zone
            if docks:
                bld = bld.rstrip().rstrip("}") + f"\tdockyard = {docks}\n\t\t}}"
            if naval:
                pb.setdefault(port, {})["naval_base"] = max(naval)
        for p, b in sorted(pb.items()):
            bld = (bld.rstrip().rstrip("}") + f"\t\t\t{p} = {{\n" + "".join(f"\t\t\t\t{k} = {v}\n" for k, v in b.items())
                   + "\t\t\t}\n\t\t}")
        if sid in IMPASSABLE:
            imp = "\timpassable = yes\n"
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            res, man, cat = "\n\tresources={\n\t}", "1000", "wasteland_sector"
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {vps[p]}\n\t\t}}\n" for p in provs if p in vps)
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (coruscant_map.py)\n{imp}"
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
