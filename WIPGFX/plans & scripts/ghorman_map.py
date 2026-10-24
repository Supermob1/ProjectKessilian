"""Ghorman, the Colonies' silk world, as one battlefield in the Clone Wars (research: WIPGFX/research/ghorman/). CANON:
mountains, valleys, plains and forests; Palmo, the capital, peaceful and elegant, its showrooms, brokerages and twilleries,
its capital square; the primary spaceport; the Great Valleys; the Beldoni Valley with its co-op of webberie estates (the
silk of the Ghorlectipods); a fiber hive at Kescrat; Leequa, Navishare, Corei, Jel-Novi; the South Depot (most of these
named in Andor, 3-2 BBY: used here by the user's choice, 2026-10-23). Owner: FON (kept).
THIRD VERSION, FROM THE USER'S STILLS (Andor's Palmo; Saint-Martin-de-Re; 2026-10-23: "Ghorman is heavily inspired by
France and its main city is a Vauban fortress near the coast"): Palmo is a star-shaped bastioned fortress city on a
coastal plain, the sea along its west side, big Alpine mountains standing right behind it; inland the French countryside,
farmland and bocage, runs east through the Great Valleys between further ranges.
LAYOUT IS A DESIGN CHOICE: the Ghorman Sea and the Gulf of Leequa on the west coast; Palmo on the coast in the middle of
it, the spaceport and the South Depot beside it; the Ghor Alps and the Palmo Heights behind Palmo with the Great Valleys
opening east between them (Jel-Novi, the Thyferria lane); Leequa on the gulf to the north-west; the Beldoni Valley with
its webberies north-east of the Alps; Navishare north (the Fondor lane), Kescrat south (the Takodana lane), Corei
south-east (the Yag'Dhul lane); the Loom Ridge, the Spinner's Spine, the Twillery Heights and the Greycliff Range further
inland.
Names from the sources: Palmo, the spaceport, the South Depot, the Great Valleys, Beldoni Valley, Kescrat, Leequa,
Navishare, Corei, Jel-Novi. Invented: the seas' and ranges' names.
    python "WIPGFX/plans & scripts/ghorman_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ghorman_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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
from korriban_map import shape as kshape, uncross

PLANET = "Ghorman"
ZONES_JSON = "WIPGFX/Assets/ghorman_zones.json"
ZONES_PNG = "WIPGFX/Assets/ghorman_zones.png"
KIND = {"city": 1, "port": 2, "depot": 3, "farm": 4, "town": 5, "coast": 6, "bocage": 7, "forest": 8, "sea": 9,
        "mountain": 10}
TERRAIN = {"city": "urban", "port": "urban", "depot": "urban", "farm": "plains", "town": "urban", "coast": "plains",
           "bocage": "plains", "forest": "forest", "sea": "mountain", "mountain": "mountain"}
SEED = 206
CAPITAL = 206
CAPITAL_VP = "Palmo"
CORE = "FON"
PORT_STATE = 1119                    # Leequa, on the gulf, out to the rim
WILD_IDS = (1465, 1466, 1467, 1477, 1478, 1479, 1480, 1481)
OWNER = {s: "FON" for s in (206, *range(1117, 1123), *WILD_IDS)}
WARP = (0.08, 9)
TARGET_PASSABLE = 122                # user rule: passable provinces outnumber impassable
STRAIGHT = {"city", "port", "depot", "farm", "town"}
PALMO = (-0.5, 0.05, 0.12)           # the star fort: centre and half size (radii)
FEATURES = [
    ("Palmo", "city", CAPITAL, 5, [("rect", PALMO[0], PALMO[1], PALMO[2], PALMO[2], 0),
                                   ("rect", PALMO[0], PALMO[1], PALMO[2], PALMO[2], 45)]),
    ("Palmo Spaceport", "port", CAPITAL, 1, [("rect", -0.3, -0.18, 0.06, 0.05, 20)]),
    ("South Depot", "depot", CAPITAL, 1, [("rect", -0.3, 0.17, 0.05, 0.04, -10)]),
    ("Beldoni Webberies", "farm", 1117, 2, [("rect", 0.12, -0.42, 0.11, 0.06, 15)]),
    ("Kescrat Fiber Hive", "town", 1118, 1, [("rect", 0.12, 0.72, 0.06, 0.05, 0)]),
    ("Navishare", "town", 1120, 1, [("rect", 0.15, -0.8, 0.06, 0.05, 0)]),
    ("Jel-Novi", "town", 1122, 1, [("rect", 0.6, -0.1, 0.06, 0.05, 0)]),
    ("Corei", "town", 1121, 1, [("rect", 0.6, 0.55, 0.06, 0.05, 0)]),
    ("Leequa", "town", 1119, 1, [("rect", -0.42, -0.62, 0.06, 0.05, 30)]),
    ("Ghorman Sea", "sea", 1465, 0, [("ell", -0.98, 0.32, 0.32, 0.52, 0)]),
    ("Gulf of Leequa", "sea", 1466, 0, [("ell", -0.88, -0.5, 0.26, 0.28, 25)]),
    ("Ghor Alps", "mountain", 1467, 0, [("cap", -0.3, -0.42, 0.0, -0.12, 0.13), ("cap", -0.15, -0.6, -0.3, -0.42, 0.1)]),
    ("Palmo Heights", "mountain", 1477, 0, [("cap", -0.22, 0.38, 0.08, 0.62, 0.12), ("cap", -0.22, 0.38, -0.12, 0.2, 0.09)]),
    ("Loom Ridge", "mountain", 1478, 0, [("cap", 0.38, -0.72, 0.42, -0.3, 0.09)]),
    ("Spinner's Spine", "mountain", 1479, 0, [("cap", 0.28, 0.08, 0.5, 0.32, 0.09)]),
    ("Twillery Heights", "mountain", 1480, 0, [("cap", 0.55, -0.52, 0.78, -0.62, 0.08)]),
    ("Greycliff Range", "mountain", 1481, 0, [("cap", -0.48, 0.62, -0.22, 0.85, 0.08)]),
]
SEEDS = {CAPITAL: ((-0.45, 0.05), "coast"), 1117: ((0.12, -0.4), "bocage"), 1118: ((0.12, 0.75), "forest"),
         1119: ((-0.42, -0.65), "coast"), 1120: ((0.12, -0.85), "forest"), 1121: ((0.62, 0.55), "bocage"),
         1122: ((0.45, -0.05), "bocage")}
STATE_NAMES = {CAPITAL: "Palmo", 1117: "Beldoni Valley", 1118: "Kescrat", 1119: "Leequa", 1120: "Navishare",
               1121: "Corei", 1122: "Great Valleys", 1465: "Ghorman Sea", 1466: "Gulf of Leequa", 1467: "Ghor Alps",
               1477: "Palmo Heights", 1478: "Loom Ridge", 1479: "Spinner's Spine", 1480: "Twillery Heights",
               1481: "Greycliff Range"}
IMPASSABLE = set(WILD_IDS)
VPS = [(CAPITAL, "Palmo", CAPITAL_VP, 15), (CAPITAL, "Palmo Spaceport", "Palmo Spaceport", 5),
       (CAPITAL, "South Depot", "South Depot", 2), (1117, "Beldoni Webberies", "Beldoni Webberies", 5),
       (1118, "Kescrat Fiber Hive", "Kescrat", 3), (1122, "Jel-Novi", "Jel-Novi", 3), (1120, "Navishare", "Navishare", 3),
       (1121, "Corei", "Corei", 3), (1119, "Leequa", "Leequa", 3)]

TERRAIN_CFG = dict(
    seed=206, base=4, rough=2, open=(6, 7, 8),
    zones={
        1: dict(relief=("flat", 4), tex=["URBAN", (13, ">", 0.3)]),                                   # Palmo's fortress
        2: dict(relief=("flat", 4), tex=["URBAN", ("ROCK2", ">", 0.6)]),                              # the spaceport
        3: dict(relief=("flat", 4), tex=["URBAN", ("FARM", ">", 0.6)]),                               # the depot
        4: dict(relief=("rolling", 4, 2, 5), tex=["FARM", (26, ">", 0.55)], props=[(231, 0.12)]),     # the webberies
        5: dict(relief=("flat", 5), tex=["URBAN", ("FARM", ">", 0.55)]),                              # the towns
        6: dict(relief=("rolling", 3, 2, 6), tex=["FARM", ("GRASS", ">", 0.5), (26, ">", 0.95)],
                props=[(229, 0.06), (231, 0.1)]),                                                     # coastal plain
        7: dict(relief=("rolling", 5, 4, 5), tex=["FARM", ("GRASS", ">", 0.45), ("FOREST", ">", 0.8), (26, ">", 0.96)],
                props=[(229, 0.22), (231, 0.1)]),                                                     # bocage: fields, hedges
        8: dict(relief=("rolling", 8, 5, 5), tex=["FOREST", ("DFOREST", ">", 0.55), (26, ">", 0.97)],
                props=[(229, 0.45), (230, 0.3)]),                                                     # forests
        9: dict(relief=("flat", 0.3), tex="WATER"),                                                   # the sea
        10: dict(relief=("rolling", 36, 18, 3), tex=["GREENMTN", ("ROCK", ">", 0.45), ("SNOWROCK", ">", 0.72)],
                 props=[(230, 0.25)]),                                                                # Alpine massifs
    },
    city={1: 115, 2: 115, 3: 115, 5: 115, 4: 115},   # map/cities.txt 115: Ghorman's stone houses (gho_town)
    prop_clear=1.5,
    shore_rise=(3, 2.0),
    colors={1: (0.74, 0.72, 0.68), 2: (0.66, 0.66, 0.62), 3: (0.62, 0.6, 0.52), 4: (0.56, 0.6, 0.34), 5: (0.7, 0.66, 0.58),
            6: (0.5, 0.62, 0.32), 7: (0.4, 0.56, 0.28), 8: (0.18, 0.4, 0.24), 9: (0.22, 0.46, 0.58),
            10: (0.44, 0.48, 0.46)},   # green France, slate-blue sea, grey Alpine rock
)

PLACEMENT = dict(
    new_models={"hod_gho_palmo", "hod_gho_webbery", "hod_gho_port"},
    items=[("hod_gho_palmo", 1.0, ("at_vp", CAPITAL_VP)), ("hod_gho_webbery", 1.0, ("at_vp", "Beldoni Webberies")),
           ("hod_gho_port", 1.0, ("at_vp", "Palmo Spaceport"))],
    clear={"hod_gho_palmo": 7.0, "hod_gho_webbery": 4.0, "hod_gho_port": 3.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ghorman_map.py)\n{imp}"
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
