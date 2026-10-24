"""Serenno, Count Dooku's homeworld in the D'Astan sector, as one battlefield before the Clone Wars (research:
WIPGFX/research/serenno/). CANON: lush forests, mountains, plains and savannah; Carannia the capital with the domed
Great Assembly House (the Planetary Council) and the Carannia Spaceport by the Trannon district; the Carannian hills
outside Carannia; Castle Serenno, Dooku's palace, on the edge of a cliff over the valley of Serenno City; Saffia over a
hundred kilometres from Carannia; Fiyaro; Borgin Castle; the Upper forest region; the Delgaldon Plains; the rocky
Aparian Wastes where the Confederacy built the Spike, an inverted-cone underground prison, just before the war.
LEGENDS: misty rivers, savannahs, the Belsallian Sea; the Great Houses of Serenno.
Owner: CIS (the Count's world). Look: old forests in autumn gold (Tales of the Jedi), dark pines on the heights.
LAYOUT IS A DESIGN CHOICE (the sources place nothing but the castle over its valley and the hills by Carannia): the
Serenno Range along the north and north-east rim (impassable) with Castle Serenno on its southern cliff and Serenno City
in the valley below, the Upper Forest and Borgin Castle in the north-west, Carannia west of centre with the hills to
its north-east and the spaceport on its west side, the Belsallian Sea in the south-west (impassable), Saffia in the
south, the Delgaldon Plains east, Fiyaro north-east, the Aparian Wastes and the Spike in the south-east.
Canon names: Carannia, Great Assembly House, Carannia Spaceport, Carannian Hills, Castle Serenno, Serenno City, Saffia,
Fiyaro, Borgin Castle, Upper Forest, Delgaldon Plains, Aparian Wastes, the Spike. Legends: the Belsallian Sea.
Invented: the Serenno Range, the Carannian Lookout VP (canon has a lookout on the hills, 42 BBY).
    python "WIPGFX/plans & scripts/serenno_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/serenno_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 201 province ids are kept (strategic region unchanged); only the pixels move.
Run order: serenno_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (ser_*) ->
planet_terrain_gen.py --planet Serenno -> military_buildings.py models hod_ser -> military_buildings.py place Serenno ->
planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Serenno"
ZONES_JSON = "WIPGFX/Assets/serenno_zones.json"
ZONES_PNG = "WIPGFX/Assets/serenno_zones.png"
KIND = {"city": 1, "assembly": 2, "spaceport": 3, "castle": 4, "town": 5, "borgin": 6, "spike": 7, "forest": 8,
        "pines": 9, "hills": 10, "plains": 11, "wastes": 12, "sea": 13, "mountains": 14}
TERRAIN = {"city": "urban", "assembly": "urban", "spaceport": "urban", "castle": "hills", "town": "urban",
           "borgin": "hills", "spike": "hills", "forest": "forest", "pines": "forest", "hills": "hills",
           "plains": "plains", "wastes": "desert", "sea": "mountain", "mountains": "mountain"}
SEED = 93
CAPITAL = 93
CAPITAL_VP = "Carannia"
PORT_STATE = 93
OWNER = {s: "CIS" for s in (93, 798, 799, 800, 801, 802, 803, 804, 1206, 1207)}
WARP = (0.13, 9)
TARGET_PASSABLE = 134                # user rule: passable provinces outnumber impassable (~134 / 67)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Great Assembly House", "assembly", CAPITAL, 1, [("ell", -0.26, 0.04, 0.06, 0.05, 0)]),
    ("Carannia", "city", CAPITAL, 5, [("ell", -0.3, 0.06, 0.17, 0.12, 15)]),
    ("Carannia Spaceport", "spaceport", CAPITAL, 1, [("ell", -0.55, 0.12, 0.08, 0.06, 0)]),
    ("Castle Serenno", "castle", 798, 1, [("ell", 0.14, -0.62, 0.08, 0.05, 0)]),
    ("Serenno City", "town", 798, 3, [("ell", 0.15, -0.44, 0.14, 0.08, 0)]),
    ("Borgin Castle", "borgin", 801, 1, [("ell", -0.52, -0.4, 0.07, 0.06, 0)]),
    ("Saffia", "town", 799, 2, [("ell", 0.04, 0.56, 0.11, 0.07, 0)]),
    ("Fiyaro", "town", 800, 2, [("ell", 0.6, -0.28, 0.1, 0.07, 20)]),
    ("The Spike", "spike", 802, 2, [("ell", 0.46, 0.6, 0.1, 0.08, 0)]),
    # the impassable rim: the Serenno Range over the north and north-east, the Belsallian Sea in the south-west
    ("Serenno Range", "mountains", 1207, 0, [("cap", -0.15, -0.8, 0.4, -0.78, 0.11), ("cap", -0.15, -0.8, -0.55, -0.95, 0.12),
                                             ("cap", 0.4, -0.78, 0.95, -0.3, 0.1), ("cap", -0.55, -0.95, -0.85, -0.6, 0.09)]),
    ("Belsallian Sea", "sea", 1206, 0, [("ell", -0.6, 0.66, 0.33, 0.2, -35), ("cap", -0.95, 0.35, -0.75, 0.6, 0.08),
                                        ("cap", -0.4, 0.85, -0.15, 0.98, 0.07)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((-0.5, 0.1), "forest"), 798: ((0.15, -0.4), "forest"), 799: ((0.0, 0.55), "plains"),
         800: ((0.65, -0.2), "forest"), 801: ((-0.45, -0.5), "pines"), 802: ((0.5, 0.55), "wastes"),
         803: ((0.5, 0.05), "plains"), 804: ((-0.05, -0.12), "hills")}
STATE_NAMES = {CAPITAL: "Carannia", 798: "Serenno City", 799: "Saffia", 800: "Fiyaro", 801: "Upper Forest",
               802: "Aparian Wastes", 803: "Delgaldon Plains", 804: "Carannian Hills",
               1206: "Belsallian Sea", 1207: "Serenno Range"}
IMPASSABLE = {1206, 1207}
VPS = [(CAPITAL, "Carannia", CAPITAL_VP, 10), (CAPITAL, "Great Assembly House", "Great Assembly House", 3),
       (CAPITAL, "Carannia Spaceport", "Carannia Spaceport", 2), (798, "Castle Serenno", "Castle Serenno", 5),
       (798, "Serenno City", "Serenno City", 3), (799, "Saffia", "Saffia", 2), (800, "Fiyaro", "Fiyaro", 2),
       (801, "Borgin Castle", "Borgin Castle", 2), (802, "The Spike", "The Spike", 2),
       (803, "plains", "Delgaldon", 1), (804, "hills", "Carannian Lookout", 1)]

# terrain (planet_terrain_gen.py --planet Serenno). Heights in heightmap steps above the base. Golden autumn forest
# (flora_props 133), dark pines on the heights (134), savannah plains with copses, rocky wastes, the range snow-capped
TERRAIN_CFG = dict(
    seed=93, base=4, rough=2, open=(8, 11),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("ramp_top", 8, 5, 4), tex="URBAN", props=[(133, 0.04)]),                 # Carannia
        2: dict(relief=("flat", 8), tex="URBAN"),                                                 # Great Assembly House
        3: dict(relief=("flat", 5), tex="URBAN"),                                                 # the spaceport
        4: dict(relief=("mesa", 8, 24, 2.0, (4, 0.6)), tex=["GREENMTN", ("ROCK", ">", 0.55)],
                props=[(134, 0.15)]),                                                             # the castle's cliff
        5: dict(relief=("rolling", 5, 2, 5), tex="URBAN", props=[(133, 0.06)]),                   # Serenno City, towns
        6: dict(relief=("ramp_top", 13, 6, 4), tex=["GRASSHILL", ("ROCK", ">", 0.6)], props=[(134, 0.2)]),   # Borgin
        7: dict(relief=("rolling", 4, 3, 4), tex=["ROCK2", ("BROWN", ">", 0.5)]),                 # the Spike's pit
        8: dict(relief=("rolling", 6, 5, 5), tex=["FOREST", ("GRASSHILL", ">", 0.65)],
                props=[(133, 0.5), (134, 0.06)], clusters=[(6, 0.5, [(133, 0.9)])]),             # the golden forest
        9: dict(relief=("rolling", 11, 7, 5), tex=["DFOREST", ("GREENMTN", ">", 0.6)],
                props=[(134, 0.5), (133, 0.1)], clusters=[(6, 0.5, [(134, 0.9)])]),              # the Upper Forest
        10: dict(relief=("rolling", 10, 8, 4), tex=["GRASSHILL", ("HILLS", ">", 0.6)],
                 props=[(133, 0.18), (134, 0.06)], clusters=[(7, 0.6, [(133, 0.7)])]),           # Carannian hills
        11: dict(relief=("rolling", 4, 2, 6), tex=["SAVANNA", ("GRASS", ">", 0.55)],
                 props=[(133, 0.05)], clusters=[(7, 0.65, [(133, 0.75)])]),                      # Delgaldon, savannah
        12: dict(relief=("rolling", 6, 6, 4), tex=["BROWN", ("ROCK2", ">", 0.55)]),               # Aparian Wastes
        13: dict(relief=("flat", 0.3), tex="WATER"),                                              # the Belsallian Sea
        14: dict(relief=("spires", 18, 10, 0.08, (1.5, 3.0), (26, 50)),
                 tex=["GREENMTN", ("ROCK", ">", 0.45), ("SNOWROCK", ">", 0.75)], props=[(134, 0.05)]),   # the range
    },
    steep=("ROCK", 6, (4, 8, 9, 10, 12)),
    city={1: 36, 2: 36, 3: 36, 5: 36},   # map/cities.txt 36: Serenno's city (military_buildings.py ser_city)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.62, 0.6, 0.56), 2: (0.66, 0.64, 0.6), 3: (0.6, 0.6, 0.58), 4: (0.4, 0.42, 0.36), 5: (0.6, 0.57, 0.5),
            6: (0.42, 0.46, 0.34), 7: (0.46, 0.4, 0.34), 8: (0.62, 0.47, 0.22), 9: (0.25, 0.35, 0.27),
            10: (0.5, 0.5, 0.3), 11: (0.62, 0.58, 0.34), 12: (0.52, 0.44, 0.34), 13: (0.16, 0.3, 0.38),
            14: (0.5, 0.5, 0.48)},
)

# models (military_buildings.py place Serenno): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_ser_carannia", "hod_ser_assembly", "hod_ser_castle", "hod_ser_borgin", "hod_ser_spike"},
    items=[("hod_ser_carannia", 1.0, ("at_vp", CAPITAL_VP)), ("hod_ser_assembly", 1.0, ("at_vp", "Great Assembly House")),
           ("hod_ser_castle", 1.0, ("at_vp", "Castle Serenno")), ("hod_ser_borgin", 1.0, ("at_vp", "Borgin Castle")),
           ("hod_ser_spike", 1.0, ("at_vp", "The Spike"))],
    clear={"hod_ser_carannia": 6.0, "hod_ser_assembly": 4.5, "hod_ser_castle": 5.0, "hod_ser_borgin": 4.5,
           "hod_ser_spike": 5.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (serenno_map.py)\n{imp}"
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
