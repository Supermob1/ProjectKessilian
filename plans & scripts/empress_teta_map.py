"""Empress Teta, the city-world at the gateway to the Deep Core, as one battlefield before the Clone Wars (research:
WIPGFX/research/empress_teta/). CANON: a city-world; Cinnagar, its capital, grew over millennia to cover the whole
surface; the majestic Core District in its centre, the Royal District (home of the royal Keto family), the Great Library
of Cinnagar under its bronze dome, the Hyperspace Navigator's Guildhouse, the Iron Citadel (a massive stone palace);
the Koros Trunk Line to Coruscant and the Byss Run. LEGENDS: the Iron Citadel at the heart of the Royal District; the
monument to lost navigators in front of the Guildhouse; carbonite mines dotting the cityscape; Cinnagar Control directing
the ships leaving orbit, its Koros Spaceworks interceptors; the detention facilities of Koros.
THE USER, 2026-10-22: start from zero: a futuristic Star Wars city planet, an ecumenopolis: interesting shapes, big
impassable ranges of buildings, narrow streets, plazas, spaceports. (Two earlier versions were rejected: megablock
regions, and the old canal layout painted half as wasteland.)
LAYOUT, A DESIGN CHOICE: a street network. Each passable state is a district: its PLAZA (a landmark square, a spaceport
apron, a mine works ring) and the narrow STREETS leading out of it; every pocket of city the streets enclose is a
MEGABLOCK, an impassable state of its own (ids from 1381, gapless; BLOCKS names them by nearest anchor). Cinnagar's grand
plaza in the middle; the Royal District with the Iron Citadel north-west; the Great Library east; the Navigators' plaza
with the Guildhouse and, down a short street, the monument south-west; the carbonite works round the Carbonite Pit in
the north; Cinnagar Control's spaceport on the southern rim (the Byss Run, the Byss lane), the Koros Spaceworks on the
north-eastern rim (the Koros Trunk Line, the Tython lane), the Western Skydocks on the western rim.
Names from the sources: Cinnagar, Core District, Royal District, Iron Citadel, Great Library of Cinnagar, Hyperspace
Navigator's Guildhouse, Monument to Lost Navigators, Cinnagar Control, Koros Spaceworks, the carbonite mines, Koros
Detention Halls (the detention facilities of Koros). Invented: every other district, plaza, street and megablock name.
    python "WIPGFX/plans & scripts/empress_teta_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/empress_teta_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All province ids are kept (strategic region unchanged); only the pixels move.
"""
import glob, math, os, re, sys
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from felucia_map import split_area
from felucia_tribes import block, place, rw
from raxus_map import mend
import planet_common as pcom
from korriban_map import shape, uncross

PLANET = "Empress Teta"
ZONES_JSON = "WIPGFX/Assets/empress_teta_zones.json"
ZONES_PNG = "WIPGFX/Assets/empress_teta_zones.png"
KIND = {"plaza": 1, "core": 2, "palace": 3, "library": 4, "guild": 5, "port": 6, "street": 7, "mines": 8, "pit": 9,
        "blocks": 10}
TERRAIN = {k: "urban" for k in KIND}
TERRAIN.update(pit="mountain", blocks="mountain")
SEED = 11
CAPITAL = 213
CAPITAL_VP = "Cinnagar"
CORE = "GMG"
PORT_STATE = 224                     # Cinnagar Control's spaceport on the southern rim
WARP = (0.05, 9)
TARGET_PASSABLE = 118                # user rule: passable provinces outnumber impassable
STREET = 0.032                       # street half-width (planet radii): ~4-5 px wide
STRAIGHT = {"palace", "library", "guild"}
MIN_BLOCK = 45                       # px: smaller pockets between streets are paved into the plaza beside them

# districts: state -> name; their plazas and buildings (painted first: the first shape on a pixel wins)
DISTRICTS = {213: "Core District", 217: "Keto Quarter", 216: "Royal District", 218: "Mining Guild District",
             220: "Carbonite Mines", 227: "Research District", 219: "Library District", 11: "Koros Spaceworks",
             226: "Entertainment District", 224: "Cinnagar Control", 212: "Tetan Depths", 215: "Navigators' Quarter",
             214: "Old Koros", 222: "Western Skydocks", 221: "Carbonite Refineries", 225: "Outer Carbonite Mines",
             223: "Tetan Commons"}
PIT = 1381
FEATURES = [   # (name, kind, state, provinces (0 = sized from TARGET_PASSABLE), shapes)
    ("Iron Citadel", "palace", 216, 1, [("rect", -0.42, -0.3, 0.07, 0.055, 10)]),
    ("Great Library of Cinnagar", "library", 219, 1, [("ell", 0.44, -0.16, 0.06, 0.06, 0)]),
    ("Hyperspace Navigator's Guildhouse", "guild", 215, 1, [("rect", -0.44, 0.2, 0.05, 0.04, 0)]),
    ("Monument to Lost Navigators", "guild", 215, 1, [("ell", -0.3, 0.35, 0.045, 0.045, 0)]),
    ("Koros Detention Halls", "plaza", 214, 1, [("rect", -0.7, 0.1, 0.047, 0.047, 0)]),
    ("Carbonite Pit", "pit", PIT, 0, [("ell", -0.06, -0.74, 0.135, 0.088, 5)]),
    ("Cinnagar", "core", 213, 3, [("ell", 0.0, 0.0, 0.216, 0.149, 15), ("rect", 0.0, 0.0, 0.324, 0.047, 15),
                                  ("rect", 0.0, 0.0, 0.047, 0.23, 15)]),
    ("Keto Quarter", "plaza", 217, 0, [("ell", -0.17, -0.3, 0.095, 0.074, 30)]),
    ("Royal Court", "plaza", 216, 0, [("ell", -0.42, -0.3, 0.162, 0.121, 10)]),
    ("Mining Guild Hall", "plaza", 218, 0, [("rect", -0.55, -0.6, 0.095, 0.074, -20)]),
    ("Tetan Carbonite Mines", "mines", 220, 0, [("ell", -0.06, -0.74, 0.257, 0.162, 5)]),
    ("Research Plaza", "plaza", 227, 0, [("ell", 0.22, -0.45, 0.095, 0.074, 30)]),
    ("Library Plaza", "plaza", 219, 0, [("ell", 0.44, -0.16, 0.149, 0.121, 0)]),
    ("Koros Spaceworks", "port", 11, 0, [("ell", 0.68, -0.6, 0.23, 0.135, -35)]),
    ("Entertainment Plaza", "plaza", 226, 0, [("ell", 0.64, 0.22, 0.121, 0.088, -20), ("rect", 0.64, 0.22, 0.176, 0.034, -20)]),
    ("Cinnagar Control", "port", 224, 0, [("ell", 0.34, 0.83, 0.284, 0.149, 20)]),
    ("Depths Market", "plaza", 212, 0, [("ell", -0.04, 0.46, 0.108, 0.081, 0)]),
    ("Navigators' Plaza", "plaza", 215, 0, [("ell", -0.44, 0.2, 0.135, 0.101, 0)]),
    ("Old Koros", "plaza", 214, 0, [("ell", -0.76, -0.06, 0.095, 0.121, 0)]),
    ("Western Skydocks", "port", 222, 0, [("ell", -0.86, 0.42, 0.176, 0.121, 40)]),
    ("Carbonite Refineries", "plaza", 221, 0, [("rect", -0.8, -0.38, 0.081, 0.068, 25)]),
    ("Outer Carbonite Mines", "mines", 225, 0, [("ell", 0.4, -0.82, 0.135, 0.081, -10)]),
    ("Tetan Commons", "plaza", 223, 0, [("ell", 0.22, 0.42, 0.101, 0.081, 0)]),
]
STREETS = [   # (state, points): narrow streets, bends at the inner points; dead ends are alleys
    (213, [(0.0, 0.0), (-0.17, -0.3)]), (217, [(-0.17, -0.3), (-0.42, -0.3)]), (216, [(-0.42, -0.3), (-0.55, -0.6)]),
    (218, [(-0.55, -0.6), (-0.25, -0.74)]), (220, [(0.12, -0.74), (0.22, -0.45)]), (227, [(0.22, -0.45), (0.06, -0.08)]),
    (227, [(0.22, -0.45), (0.44, -0.16)]), (11, [(0.6, -0.52), (0.44, -0.16)]), (219, [(0.44, -0.16), (0.64, 0.22)]),
    (213, [(0.0, 0.0), (0.08, 0.25), (-0.04, 0.46)]), (212, [(-0.04, 0.46), (0.25, 0.76)]), (226, [(0.64, 0.22), (0.42, 0.74)]),
    (213, [(0.0, 0.0), (-0.44, 0.2)]), (215, [(-0.44, 0.2), (-0.76, -0.06)]), (214, [(-0.76, -0.06), (-0.42, -0.3)]),
    (215, [(-0.44, 0.2), (-0.8, 0.4)]), (215, [(-0.44, 0.2), (-0.3, 0.35)]), (212, [(-0.04, 0.46), (-0.3, 0.35)]),
    (214, [(-0.76, -0.06), (-0.8, -0.38)]), (221, [(-0.8, -0.38), (-0.55, -0.6)]), (220, [(0.12, -0.74), (0.4, -0.82)]),
    (225, [(0.4, -0.82), (0.62, -0.62)]), (223, [(0.22, 0.42), (0.64, 0.22)]), (223, [(0.22, 0.42), (-0.04, 0.46)]),
    (213, [(0.1, 0.05), (0.36, 0.1)]), (226, [(0.64, 0.22), (0.82, 0.32)]), (216, [(-0.42, -0.3), (-0.3, -0.52)]),
    (224, [(0.34, 0.83), (0.06, 0.82)]), (219, [(0.44, -0.16), (0.7, -0.2)]),
]
# megablocks: every enclosed pocket of city is one impassable state, named by the nearest anchor (ids 1382.., gapless)
BLOCKS = {1382: ("Royal Spires", (-0.6, -0.34)), 1383: ("Guild Towers", (-0.53, -0.4)),
          1384: ("Western Megablocks", (-0.37, -0.06)), 1385: ("Skydock Arcologies", (-0.3, 0.68)),
          1386: ("Navigators' Towers", (-0.15, 0.25)), 1387: ("Northern Megablocks", (-0.11, -0.44)),
          1388: ("Core Spires", (0.28, 0.08)), 1389: ("Southern Megablocks", (0.3, 0.54)),
          1390: ("Library Megablocks", (0.38, -0.55)), 1391: ("Spaceworks Gantries", (0.55, -0.77)),
          1392: ("Eastern Arcologies", (0.75, 0.09))}
STATE_NAMES = {**DISTRICTS, PIT: "Carbonite Pit", **{k: v[0] for k, v in BLOCKS.items()}}
IMPASSABLE = {PIT, *BLOCKS}
OWNER = {s: "GMG" for s in STATE_NAMES}
VPS = [(213, "Cinnagar", CAPITAL_VP, 25), (216, "Iron Citadel", "Iron Citadel", 10),
       (219, "Great Library of Cinnagar", "Great Library of Cinnagar", 5),
       (215, "Hyperspace Navigator's Guildhouse", "Hyperspace Navigator's Guildhouse", 3),
       (215, "Monument to Lost Navigators", "Monument to Lost Navigators", 1),
       (224, "Cinnagar Control", "Cinnagar Control", 5), (11, "Koros Spaceworks", "Koros Spaceworks", 3),
       (222, "Western Skydocks", "Western Skydocks", 2), (220, "Tetan Carbonite Mines", "Tetan Carbonite Mines", 5),
       (225, "Outer Carbonite Mines", "Outer Carbonite Mines", 2), (221, "Carbonite Refineries", "Carbonite Refineries", 2),
       (218, "Mining Guild Hall", "Mining Guild Hall", 3), (214, "Old Koros", "Old Koros", 2),
       (214, "Koros Detention Halls", "Koros Detention Halls", 1), (217, "Keto Quarter", "Keto Quarter", 2),
       (212, "Depths Market", "Depths Market", 1), (223, "Tetan Commons", "Tetan Commons", 1),
       (226, "Entertainment Plaza", "Entertainment Plaza", 2), (227, "Research Plaza", "Research Plaza", 2)]

TERRAIN_CFG = dict(
    seed=11, base=4, rough=1, open=(1, 6, 7),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.85)]),                             # plazas
        2: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.8)]),                              # Cinnagar's grand plaza
        3: dict(relief=("flat", 6), tex="URBAN"),                                                     # the Iron Citadel
        4: dict(relief=("flat", 6), tex="URBAN"),                                                     # the Great Library
        5: dict(relief=("flat", 6), tex="URBAN"),                                                     # Guildhouse, monument
        6: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.7)]),                              # spaceports
        7: dict(relief=("flat", 5), tex=["URBAN", (13, ">", 0.55)]),                                  # streets
        8: dict(relief=("flat", 5), tex=["URBAN", ("BROWN", ">", 0.6)]),                              # mine works
        9: dict(relief=("flat", 0.5), tex=["ROCK", ("BROWN", ">", 0.5)]),                             # the Carbonite Pit
        10: dict(relief=("rolling", 11, 3, 3), tex=["URBAN", (13, ">", 0.1)]),                        # megablocks: raised city
    },
    city={1: 96, 7: 96, 8: 96, 10: 96},   # map/cities.txt 96: Cinnagar's bronze towers (tet_town), densest on the blocks
    prop_clear=1.5,
    lights=dict(zones=(1, 2, 6, 7, 8, 10), rgb=(1.0, 0.78, 0.36), density=0.22, mix=0.85),   # Cinnagar's golden glow
    colors={1: (0.74, 0.62, 0.42), 2: (0.82, 0.66, 0.36), 3: (0.46, 0.44, 0.46), 4: (0.82, 0.62, 0.3), 5: (0.74, 0.58, 0.36),
            6: (0.7, 0.66, 0.58), 7: (0.66, 0.5, 0.3), 8: (0.6, 0.5, 0.38), 9: (0.3, 0.34, 0.44), 10: (0.56, 0.4, 0.22)},
)

PLACEMENT = dict(
    new_models={"hod_tet_citadel", "hod_tet_core", "hod_tet_library", "hod_tet_guild", "hod_tet_monument",
                "hod_tet_control", "hod_tet_spaceworks", "hod_tet_mine"},
    items=[("hod_tet_citadel", 1.0, ("at_vp", "Iron Citadel")), ("hod_tet_core", 0.9, ("at_vp", CAPITAL_VP)),
           ("hod_tet_library", 0.9, ("at_vp", "Great Library of Cinnagar")),
           ("hod_tet_guild", 0.8, ("at_vp", "Hyperspace Navigator's Guildhouse")),
           ("hod_tet_monument", 0.6, ("at_vp", "Monument to Lost Navigators")),
           ("hod_tet_control", 1.0, ("at_vp", "Cinnagar Control")), ("hod_tet_spaceworks", 1.0, ("at_vp", "Koros Spaceworks")),
           ("hod_tet_mine", 0.9, ("at_vp", "Tetan Carbonite Mines")), ("hod_tet_mine", 0.7, ("at_vp", "Outer Carbonite Mines"))],
    clear={"hod_tet_citadel": 4.0, "hod_tet_core": 4.5, "hod_tet_library": 3.5, "hod_tet_guild": 3.0, "hod_tet_monument": 2.0,
           "hod_tet_control": 5.0, "hod_tet_spaceworks": 5.0, "hod_tet_mine": 4.5},
)


def mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    return land, pid, np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])


def layout(m, rng):
    """feature index per pixel and features [(name, kind, state, provinces)]: FEATURES, then the streets, then each
    enclosed pocket of city as a megablock (small pockets paved into the plaza or street beside them)"""
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
    for i, (sid, pts) in enumerate(STREETS):
        feats.append((f"{DISTRICTS[sid]} street {i + 1}", "street", sid, 0))
        on = np.any([shape(("cap", *a, *b, STREET), U, V) for a, b in zip(pts, pts[1:])], 0)
        fid[sm & (fid < 0) & on] = len(feats) - 1
    pockets, n = ndi.label(sm & (fid < 0))
    taken = {}
    for j in range(1, n + 1):
        pk = pockets == j
        if pk.sum() < MIN_BLOCK:                                       # a scrap between streets: paved
            ring = ndi.binary_dilation(pk) & ~pk & (fid >= 0)
            fid[pk] = np.bincount(fid[ring]).argmax()
            continue
        u, v = U0[pk].mean(), V0[pk].mean()
        sid = min(BLOCKS, key=lambda b: math.hypot(BLOCKS[b][1][0] - u, BLOCKS[b][1][1] - v))
        assert sid not in taken, f"two pockets nearest {BLOCKS[sid][0]}: ({u:.2f}, {v:.2f}) and {taken[sid]}"
        taken[sid] = (round(float(u), 2), round(float(v), 2))
        feats.append((BLOCKS[sid][0], "blocks", sid, 0))
        fid[pk] = len(feats) - 1
    unused = sorted(set(BLOCKS) - set(taken))
    assert not unused, f"no pocket for {[BLOCKS[b][0] for b in unused]}; pockets at {sorted(taken.values())}"
    full = np.full(m.shape, -1, np.int32)
    full[sl] = fid
    return full, feats


def tidy(lab, feats, m):
    """every feature in one piece: stray bits join the neighbour with the longest shared border, preferring their own
    state, then their own kind"""
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
                kin = [k for k in np.nonzero(nb)[0] if (feats[k][2] in IMPASSABLE) == (feats[i][2] in IMPASSABLE)]
                pick = same or kin or list(np.nonzero(nb)[0])
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (empress_teta_map.py)\n{imp}"
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
