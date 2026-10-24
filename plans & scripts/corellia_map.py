"""Corellia, the shipbuilders' world, as one battlefield before the Clone Wars (research: WIPGFX/research/corellia/; canon
and Legends mixed, the user, 2026-10-21). CANON: forests, jungles, oceans and industrial cities; Coronet City, the
capital, the Golden City; the Bottoms, a Coronet district on drained swamp where shipbuilders put their factories; the
Santhe (Corellian) Shipyards; Kor Vella, Tyrena, Bela Vistal, and Doaba Guerfel, a mountain town a short way from the
capital. LEGENDS: plains, hills, forests, mesas, mountains, islands and jungles, snow-covered mountains over part of the
land; CorSec, Treasure Ship Row, the Agrilat swamps, the Gold Beaches, the Kor Vella mesa, the Nomad Mountains; Selonians
(their dens, Hunchuzuc Den) and Drall. Owner: COR (as before).
LAYOUT IS A DESIGN CHOICE beyond the stated relationships: Coronet City in the north-east with the Bottoms, Treasure Ship
Row and CorSec's headquarters; the Santhe Shipyards in ORBIT above it (the user, 2026-10-21: shipyards are space
shipyards, though canon puts the Santhe yards in the city); Doaba Guerfel in the Nomad Mountains west of the capital
under the Nomad Peaks (impassable, snow); Bela Vistal on the northern coast (the Rendili lane); Kor Vella on its mesa in
the west (the Fresia lane); Tyrena in the south, the Agrilat swamps south-west by the Corellian Sea (impassable); the
Selonian hills east with Hunchuzuc Den (the Loronar lane), the Gold Beaches on the south-eastern coast, the Selonian Sea
(impassable) off the east.
Names from the sources: every state and VP name except the invented Selonian Hills, Corellian Sea, Selonian Sea and
Nomad Peaks.
    python "WIPGFX/plans & scripts/corellia_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/corellia_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 63 province ids are kept (strategic region unchanged); only the pixels move.
Run order: corellia_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (crl_*) ->
planet_terrain_gen.py --planet Corellia -> military_buildings.py corellia_atlas, models hod_crl_ -> coruscant_buildings.py
wire -> military_buildings.py place Corellia -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Corellia"
ZONES_JSON = "WIPGFX/Assets/corellia_zones.json"
ZONES_PNG = "WIPGFX/Assets/corellia_zones.png"
KIND = {"city": 1, "industry": 2, "shiprow": 3, "corsec": 4, "mesa": 5, "den": 6, "plains": 7, "forest": 8, "hills": 9,
        "swamp": 10, "coast": 11, "sea": 12, "peaks": 13, "mountains": 14}
TERRAIN = {"city": "urban", "industry": "urban", "shiprow": "urban", "corsec": "urban", "mesa": "hills", "den": "hills",
           "plains": "plains", "forest": "forest", "hills": "hills", "swamp": "marsh", "coast": "plains", "sea": "mountain",
           "peaks": "mountain", "mountains": "mountain"}
SEED = 22
CAPITAL = 22
CAPITAL_VP = "Coronet City"
CORE = "COR"
PORT_STATE = 352                     # the Gold Beaches coast
OWNER = {s: "COR" for s in (22, 346, 347, 348, 349, 350, 351, 352, 1345, 1346, 1347)}
WARP = (0.12, 9)
TARGET_PASSABLE = 41                 # user rule: passable provinces outnumber impassable (~41 / 22)
STRAIGHT = {"shiprow", "corsec"}
FEATURES = [
    ("Coronet City", "city", CAPITAL, 2, [("ell", 0.22, -0.3, 0.22, 0.15, -15)]),
    ("The Bottoms", "industry", CAPITAL, 1, [("ell", 0.32, -0.04, 0.12, 0.09, 0)]),
    ("Treasure Ship Row", "shiprow", CAPITAL, 1, [("rect", 0.5, -0.3, 0.1, 0.05, -15)]),
    ("CorSec Headquarters", "corsec", CAPITAL, 1, [("rect", -0.04, -0.16, 0.08, 0.08, 0)]),
    ("Doaba Guerfel", "city", 346, 1, [("ell", -0.2, -0.4, 0.11, 0.09, 0)]),
    ("Bela Vistal", "city", 351, 1, [("ell", 0.3, -0.78, 0.07, 0.06, 0)]),
    ("Kor Vella", "mesa", 347, 1, [("ell", -0.6, 0.0, 0.1, 0.09, 0)]),
    ("Tyrena", "city", 350, 1, [("ell", 0.05, 0.42, 0.08, 0.06, 0)]),
    ("Agrilat Swamps", "swamp", 348, 0, [("ell", -0.45, 0.48, 0.2, 0.12, 25)]),
    ("Hunchuzuc Den", "den", 349, 1, [("ell", 0.62, 0.15, 0.08, 0.07, 0)]),
    ("Gold Beaches", "coast", 352, 1, [("ell", 0.55, 0.62, 0.15, 0.09, -40)]),
    ("Nomad Peaks", "peaks", 1345, 0, [("cap", -0.6, -0.62, -0.1, -0.68, 0.11), ("cap", -0.6, -0.62, -0.75, -0.3, 0.09)]),
    ("Corellian Sea", "sea", 1346, 0, [("ell", -0.3, 0.88, 0.45, 0.16, -10), ("cap", -0.85, 0.55, -0.6, 0.8, 0.09)]),
    ("Selonian Sea", "sea", 1347, 0, [("cap", 0.95, -0.3, 0.82, 0.3, 0.12)]),
]
SEEDS = {CAPITAL: ((0.25, -0.25), "city"), 346: ((-0.25, -0.4), "hills"), 347: ((-0.6, 0.0), "plains"),
         348: ((-0.45, 0.5), "swamp"), 349: ((0.6, 0.15), "hills"), 350: ((0.05, 0.4), "forest"), 351: ((0.3, -0.75), "coast"),
         352: ((0.5, 0.6), "coast")}
STATE_NAMES = {CAPITAL: "Coronet City", 346: "Nomad Mountains", 347: "Kor Vella", 348: "Agrilat", 349: "Selonian Hills",
               350: "Tyrena", 351: "Bela Vistal", 352: "Gold Beaches", 1345: "Nomad Peaks", 1346: "Corellian Sea",
               1347: "Selonian Sea"}
IMPASSABLE = {1345, 1346, 1347}
VPS = [(CAPITAL, "Coronet City", CAPITAL_VP, 15), (CAPITAL, "The Bottoms", "The Bottoms", 3),
       (CAPITAL, "Treasure Ship Row", "Treasure Ship Row", 3), (CAPITAL, "CorSec Headquarters", "CorSec Headquarters", 3),
       (346, "Doaba Guerfel", "Doaba Guerfel", 2), (351, "Bela Vistal", "Bela Vistal", 2), (347, "Kor Vella", "Kor Vella", 5),
       (350, "Tyrena", "Tyrena", 3), (348, "Agrilat Swamps", "Agrilat Swamps", 1), (349, "Hunchuzuc Den", "Hunchuzuc Den", 2),
       (352, "Gold Beaches", "Gold Beaches", 2)]

TERRAIN_CFG = dict(
    seed=22, base=4, rough=2, open=(7, 8, 9, 10, 11),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("BROWN", ">", 0.6)]),                              # the cities
        2: dict(relief=("flat", 3), tex=["URBAN", ("BROWN", ">", 0.45)]),                             # the Bottoms
        3: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.6)]),                              # Treasure Ship Row
        4: dict(relief=("flat", 6), tex=["URBAN", ("ROCK2", ">", 0.6)]),                              # CorSec
        5: dict(relief=("mesa", 4, 16, 3, (5, 0.6)), tex=["URBAN", ("BROWN", ">", 0.5)]),             # the Kor Vella mesa
        6: dict(relief=("rolling", 8, 6, 4), tex=["GRASSHILL", ("BROWN", ">", 0.55)], props=[(243, 0.3)]),   # the den
        7: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("FARM", ">", 0.6), (13, ">", 0.94)], props=[(243, 0.3), (242, 0.12)]),
        8: dict(relief=("rolling", 5, 4, 6), tex=["FOREST", ("JUNGLE", ">", 0.6)], props=[(242, 0.65)]),
        9: dict(relief=("rolling", 10, 7, 5), tex=["GRASSHILL", ("ROCK2", ">", 0.6), (13, ">", 0.95)], props=[(242, 0.3), (243, 0.2)]),
        10: dict(relief=("rolling", 1, 1, 6), tex=["WATER", ("JUNGLE", ">", 0.45)], props=[(242, 0.3)]),   # the Agrilat swamps
        11: dict(relief=("rolling", 3, 2, 8), tex=["SAND", ("GRASS", ">", 0.55), (13, ">", 0.94)], props=[(243, 0.15)]),
        12: dict(relief=("flat", 0.3), tex="WATER"),
        13: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["SNOWROCK", ("ROCK", ">", 0.5)]),
        14: dict(relief=("spires", 16, 9, 0.1, (1.5, 3.0), (20, 45)), tex=["ROCK", ("SNOWROCK", ">", 0.7)]),
    },
    steep=("ROCK", 6, (7, 8, 9, 11)),
    city={1: 87, 2: 87, 3: 87, 4: 87, 5: 87, 7: 87, 11: 87},   # map/cities.txt 87: Corellia's towns (crl_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.609, 0.535, 0.407), 2: (0.441, 0.402, 0.346), 3: (0.588, 0.543, 0.451), 4: (0.567, 0.494, 0.543), 5: (0.588, 0.462, 0.262), 6: (0.504, 0.493, 0.215), 7: (0.531, 0.567, 0.148), 8: (0.315, 0.42, 0.106), 9: (0.476, 0.483, 0.196), 10: (0.295, 0.357, 0.174), 11: (0.756, 0.604, 0.26), 12: (0.08, 0.38, 0.58), 13: (0.86, 0.88, 0.92), 14: (0.525, 0.5, 0.487)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)


def orbit(ctx):
    """the Santhe / Corellian Shipyards in orbit above Coronet City (the user, 2026-10-21: shipyards are in space)"""
    (cy, cx), R = ctx["z"]["centre"], ctx["z"]["radius"]
    ctx["put"]("hod_crl_yards", 1.0, cy - 0.6 * R, cx + R + 0.9 * R)


PLACEMENT = dict(
    new_models={"hod_crl_coronet", "hod_crl_bottoms", "hod_crl_shiprow", "hod_crl_corsec", "hod_crl_korvella",
                "hod_crl_den", "hod_crl_yards"},
    items=[("hod_crl_coronet", 1.0, ("at_vp", "Coronet City")), ("hod_crl_bottoms", 0.9, ("at_vp", "The Bottoms")),
           ("hod_crl_shiprow", 0.9, ("at_vp", "Treasure Ship Row")), ("hod_crl_corsec", 0.8, ("at_vp", "CorSec Headquarters")),
           ("hod_crl_korvella", 0.9, ("at_vp", "Kor Vella")), ("hod_crl_den", 0.8, ("at_vp", "Hunchuzuc Den"))],
    clear={"hod_crl_coronet": 5.5, "hod_crl_bottoms": 3.5, "hod_crl_shiprow": 3.5, "hod_crl_corsec": 2.5,
           "hod_crl_korvella": 4.0, "hod_crl_den": 3.0},
    hook=orbit,
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (corellia_map.py)\n{imp}"
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
