"""Ord Cestus, the arid droid-making world of the X'Ting, as one battlefield before the Clone Wars (research:
WIPGFX/research/ord_cestus/). LEGENDS (the canon article tells almost nothing): red desert, mountain ranges and
volcanic craters; exports droids (Cestus Cybernetics) and fungi; ChikatLik the capital, built round the X'Ting hives;
Jantos a large city; Clandes and Barrens settlements; the Kibo Plateau south of ChikatLik and north of Barrens, holding
Kibo Lake, with the Kibo Geothermal Station and the Republic's Cestus Penitentiary near and under the lake; the Zantay
Hills east of the lake, Yal-Noy north of them; the Dashta Mountains 180 km west of the Zantay Hills and 75 km north-west
of Clandes; the Tolmea Mountains (Tolmeatek the highest peak); the Badlands, the remotest desert.
Owner: TDF (as before). User (2026-10-19): landmarks ChikatLik with Cestus Cybernetics, Kibo Lake with the
penitentiary, Jantos, the droid factories and the fungus farms.
LAYOUT IS A DESIGN CHOICE where the sources are silent: ChikatLik in the north with the Cestus Cybernetics works on
its east side, the Kibo Plateau and lake in the middle, Barrens and its fungus farms south, the Zantay Hills east,
Jantos north-east, the Dashta Mountains west of the lake (impassable) with Clandes and the droid works south-east of
them, the Tolmea Mountains over the south-west (impassable), the Badlands north-west.
Legends names: ChikatLik, Cestus Cybernetics, Jantos, Clandes, Barrens, the Kibo Plateau, Kibo Lake, Cestus
Penitentiary, the Zantay Hills, the Dashta Mountains, the Tolmea Mountains, the Badlands. Invented: the Cestus Droid
Works and the Barrens Fungus Farms as named sites.
    python "WIPGFX/plans & scripts/ord_cestus_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ord_cestus_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 63 province ids are kept (strategic region unchanged); only the pixels move.
Run order: ord_cestus_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (ces_*) ->
planet_terrain_gen.py --planet "Ord Cestus" -> military_buildings.py models hod_ces -> military_buildings.py place
"Ord Cestus" -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Ord Cestus"
ZONES_JSON = "WIPGFX/Assets/ord_cestus_zones.json"
ZONES_PNG = "WIPGFX/Assets/ord_cestus_zones.png"
KIND = {"city": 1, "works": 2, "lake": 3, "plateau": 4, "farms": 5, "hills": 6, "desert": 7, "mountains": 8,
        "town": 9}
TERRAIN = {"city": "urban", "works": "urban", "lake": "marsh", "plateau": "plains", "farms": "plains", "hills": "hills",
           "desert": "desert", "mountains": "mountain", "town": "urban"}
SEED = 189
CAPITAL = 189
CAPITAL_VP = "ChikatLik"
PORT_STATE = 189
OWNER = {s: "TDF" for s in (189, 1015, 1016, 1017, 1018, 1019, 1020, 1217, 1218)}
WARP = (0.13, 9)
TARGET_PASSABLE = 42                 # user rule: passable provinces outnumber impassable (~42 / 21)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Cestus Cybernetics", "works", CAPITAL, 1, [("ell", 0.3, -0.5, 0.12, 0.09, 10)]),
    ("ChikatLik", "city", CAPITAL, 3, [("ell", 0.0, -0.48, 0.2, 0.14, -10)]),
    ("Kibo Lake", "lake", 1015, 1, [("ell", -0.05, 0.08, 0.18, 0.13, 20)]),
    ("Jantos", "city", 1018, 2, [("ell", 0.55, -0.32, 0.18, 0.13, 30)]),
    ("Clandes", "town", 1019, 1, [("ell", -0.34, 0.4, 0.12, 0.1, 0)]),
    ("Cestus Droid Works", "works", 1019, 1, [("ell", -0.12, 0.5, 0.11, 0.08, -15)]),
    ("Barrens Fungus Farms", "farms", 1016, 1, [("ell", 0.15, 0.66, 0.16, 0.11, 0)]),
    ("Dashta Mountains", "mountains", 1217, 0, [("cap", -0.88, -0.2, -0.42, 0.12, 0.12)]),
    ("Tolmea Mountains", "mountains", 1218, 0, [("ell", -0.5, 0.72, 0.36, 0.2, -35), ("cap", -0.92, 0.3, -0.62, 0.62, 0.09)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.0, -0.6), "desert"), 1015: ((0.0, 0.1), "plateau"), 1016: ((0.25, 0.7), "desert"),
         1017: ((0.62, 0.2), "hills"), 1018: ((0.55, -0.45), "desert"), 1019: ((-0.3, 0.38), "hills"),
         1020: ((-0.5, -0.55), "desert")}
STATE_NAMES = {CAPITAL: "ChikatLik", 1015: "Kibo Plateau", 1016: "Barrens", 1017: "Zantay Hills", 1018: "Jantos",
               1019: "Clandes", 1020: "Badlands", 1217: "Dashta Mountains", 1218: "Tolmea Mountains"}
IMPASSABLE = {1217, 1218}
VPS = [(CAPITAL, "ChikatLik", CAPITAL_VP, 10), (CAPITAL, "Cestus Cybernetics", "Cestus Cybernetics", 3),
       (1015, "Kibo Lake", "Cestus Penitentiary", 2), (1018, "Jantos", "Jantos", 3), (1019, "Clandes", "Clandes", 1),
       (1019, "Cestus Droid Works", "Cestus Droid Works", 2), (1016, "Barrens Fungus Farms", "Barrens", 1),
       (1017, "hills", "Zantay Hills", 1), (1020, "desert", "Badlands", 1)]

# terrain (planet_terrain_gen.py --planet "Ord Cestus"). Heights in heightmap steps above the base. Red desert with
# buttes and craters (spires), ChikatLik's hive city (map/cities.txt 42, military_buildings.py ces_city) and the
# towns, fungus stalks on the farms (flora_props 143), red rock spikes in the desert (144), the two ranges
TERRAIN_CFG = dict(
    seed=189, base=4, rough=2, open=(4, 5, 6, 7),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 6, 2, 6), tex="URBAN"),                                        # ChikatLik, Jantos
        2: dict(relief=("flat", 5), tex="URBAN"),                                                  # the works
        3: dict(relief=("flat", 0.3), tex="WATER"),                                                # Kibo Lake
        4: dict(relief=("rolling", 4, 2, 6), tex=["BROWN", ("SAVANNA", ">", 0.6)], props=[(144, 0.05)]),   # plateau
        5: dict(relief=("rolling", 4, 1, 6), tex=["SAVANNA", ("BROWN", ">", 0.6), (13, ">", 0.85)],
                props=[(143, 0.45)]),                                                              # fungus farms
        6: dict(relief=("rolling", 9, 7, 4), tex=["BROWN", ("ROCK2", ">", 0.55)], props=[(144, 0.12)]),   # hills
        7: dict(relief=("spires", 5, 3, 0.012, (2.0, 4.0), (8, 20)), tex=["DUNES", ("BROWN", ">", 0.5)],
                props=[(144, 0.08)]),                                                              # desert, buttes
        8: dict(relief=("spires", 16, 9, 0.08, (1.5, 3.0), (24, 46)), tex=["BROWNMTN", ("ROCK2", ">", 0.5)]),
        9: dict(relief=("rolling", 5, 2, 6), tex="URBAN"),                                        # Clandes
    },
    steep=("ROCK2", 6, (4, 5, 6, 7)),
    city={1: 42, 2: 42, 9: 42, 5: 42},   # map/cities.txt 42: Ord Cestus' hive city (ces_city)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.6, 0.42, 0.32), 2: (0.56, 0.44, 0.38), 3: (0.2, 0.32, 0.36), 4: (0.66, 0.4, 0.26),
            5: (0.6, 0.46, 0.3), 6: (0.58, 0.34, 0.22), 7: (0.72, 0.42, 0.26), 8: (0.46, 0.28, 0.2),
            9: (0.6, 0.44, 0.34)},
)

# models (military_buildings.py place "Ord Cestus"): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_ces_chikatlik", "hod_ces_cybernetics", "hod_ces_penitentiary", "hod_ces_jantos",
                "hod_ces_droidworks", "hod_ces_fungus"},
    items=[("hod_ces_chikatlik", 1.0, ("at_vp", CAPITAL_VP)), ("hod_ces_cybernetics", 1.0, ("at_vp", "Cestus Cybernetics")),
           ("hod_ces_penitentiary", 0.9, ("at_vp", "Cestus Penitentiary")), ("hod_ces_jantos", 0.9, ("at_vp", "Jantos")),
           ("hod_ces_droidworks", 0.9, ("at_vp", "Cestus Droid Works")), ("hod_ces_fungus", 0.9, ("at_vp", "Barrens"))],
    clear={"hod_ces_chikatlik": 5.5, "hod_ces_cybernetics": 4.5, "hod_ces_penitentiary": 4.0, "hod_ces_jantos": 4.5,
           "hod_ces_droidworks": 4.0, "hod_ces_fungus": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ord_cestus_map.py)\n{imp}"
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
