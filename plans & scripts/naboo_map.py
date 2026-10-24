"""Naboo, as one battlefield in the Clone Wars (research: WIPGFX/research/naboo/; CANON: Theed the capital on the Solleu
River, the Great Grass Plains (the Battle of Naboo, 32 BBY), the Lake Country, the Gallo Mountains with the farming
community of Dee'ja Peak, Moenia (with the hill country west of it), Keren and its Kwilaan Starport, the coastal city of
Spinnaker, the Gungan city Otoh Gunga beneath the swamp lake, the old Gungan fortress Spearhead, the Gungan Sentry Post on
a plain, Hiram Zataire's vineyard; swamps, plains, grassy hills, lakes and seas). Owners kept: RNB, the Gungans (GNG) in
their swamp.
LAYOUT IS A DESIGN CHOICE (only "the retreat west of Moenia" and "Dee'ja Peak in the Gallo Mountains" are stated): Theed in
its valley in the middle, the Great Grass Plains south of it, the Gungan swamp and Lake Paonga east, the Gallo Mountains
north-east, Keren north, the Lake Country north-west, Spinnaker on the western coast, Moenia south-west with the hill
country beyond; seas, lakes and the Gallo peaks impassable (six states).
Names from the sources: every settlement, region and VP name; Varykino is the Lake Country's canon retreat. Invented: the
seas' names (Western Sea, Southern Sea, Eastern Sea) and the Gallo Peaks / Lake Country Waters split.
    python "WIPGFX/plans & scripts/naboo_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/naboo_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Naboo"
ZONES_JSON = "WIPGFX/Assets/naboo_zones.json"
ZONES_PNG = "WIPGFX/Assets/naboo_zones.png"
KIND = {"theed": 1, "city": 2, "plains": 3, "lake": 4, "hills": 5, "gungan": 6, "swamp": 7, "sea": 8, "peak": 9, "valley": 10, "gunga": 11}
TERRAIN = {"theed": "urban", "city": "urban", "plains": "plains", "lake": "forest", "hills": "hills", "gungan": "marsh",
           "swamp": "marsh", "sea": "mountain", "peak": "mountain", "valley": "hills", "gunga": "marsh"}
SEED = 44
CAPITAL = 44
CAPITAL_VP = "Theed"
CORE = "RNB"
PORT_STATE = 475                     # Spinnaker, the coastal city
ROCK_IDS = tuple(range(1594, 1600))
OWNER = {**{s: "RNB" for s in (44, *range(470, 478), *ROCK_IDS)}, 476: "GNG"}
WARP = (0.09, 9)
TARGET_PASSABLE = 132                # user rule: passable provinces outnumber impassable
STRAIGHT = {"theed", "city", "gungan", "gunga"}
F = lambda name, kind, sid, *shapes: (name, kind, sid, 0, list(shapes))
FEATURES = [
    F("Theed", "theed", 44, ("rect", -0.12, -0.05, 0.11, 0.08, 0)),
    F("Solleu Valley", "valley", 44, ("ell", -0.12, -0.05, 0.26, 0.17, 0)),
    F("Otoh Gunga", "gunga", 476, ("rect", 0.43, 0.08, 0.07, 0.05, 0)),            # under Lake Paonga, its west edge on the swamp
    F("Spearhead", "gungan", 476, ("rect", 0.62, 0.42, 0.05, 0.05, 0)),
    F("Lake Paonga", "sea", 1597, ("ell", 0.5, 0.06, 0.12, 0.08, 0)),
    F("Keren", "city", 474, ("rect", 0.05, -0.6, 0.07, 0.06, 0)),
    F("Moenia", "city", 473, ("rect", -0.5, 0.4, 0.07, 0.06, 0)),
    F("Spinnaker", "city", 475, ("rect", -0.72, -0.18, 0.06, 0.06, 0)),
    F("Dee'ja Peak", "hills", 472, ("rect", 0.48, -0.36, 0.06, 0.05, 0)),
    F("Gungan Sentry Post", "plains", 470, ("rect", 0.12, 0.42, 0.05, 0.04, 0)),
    F("Varykino", "lake", 471, ("rect", -0.38, -0.42, 0.05, 0.04, 0)),
    F("Gallo Peaks", "peak", 1596, ("ell", 0.66, -0.56, 0.22, 0.12, 35)),
    F("Lake Country Waters", "sea", 1598, ("ell", -0.36, -0.62, 0.16, 0.09, -10)),
    F("Western Sea", "sea", 1594, ("ell", -0.92, -0.55, 0.26, 0.22, 30)),
    F("Southern Sea", "sea", 1595, ("ell", 0.05, 0.95, 0.42, 0.16, 0)),
    F("Eastern Sea", "sea", 1599, ("ell", 0.98, 0.05, 0.14, 0.3, 0)),
]
SEEDS = {470: ((0.05, 0.4), "plains"), 471: ((-0.4, -0.45), "lake"), 472: ((0.5, -0.3), "hills"), 473: ((-0.48, 0.42), "hills"),
         474: ((0.08, -0.58), "plains"), 475: ((-0.68, -0.15), "plains"), 476: ((0.5, 0.3), "swamp"),
         477: ((-0.82, 0.25), "hills")}
STATE_NAMES = {CAPITAL: "Theed", 470: "Great Grass Plains", 471: "Lake Country", 472: "Gallo Mountains", 473: "Moenia",
               474: "Keren", 475: "Spinnaker", 476: "Lianorm Swamp", 477: "Western Hill Country", 1594: "Western Sea",
               1595: "Southern Sea", 1596: "Gallo Peaks", 1597: "Lake Paonga", 1598: "Lake Country Waters",
               1599: "Eastern Sea"}
IMPASSABLE = set(ROCK_IDS)
VPS = [(CAPITAL, "Theed", CAPITAL_VP, 20), (476, "Otoh Gunga", "Otoh Gunga", 10), (476, "Spearhead", "Spearhead", 3),
       (474, "Keren", "Kwilaan Starport", 5), (473, "Moenia", "Moenia", 5), (475, "Spinnaker", "Spinnaker", 3),
       (472, "Dee'ja Peak", "Dee'ja Peak", 2), (470, "Gungan Sentry Post", "Gungan Sentry Post", 3),
       (471, "Varykino", "Varykino", 2), (477, "Western Hill Country", "Hiram Zataire's Vineyard", 1)]

TERRAIN_CFG = dict(
    seed=44, base=4, rough=2, open=(3, 4, 5, 7, 10),
    zones={
        1: dict(relief=("ramp_top", 8, 5, 4), tex=["URBAN", ("GRASSHILL", ">", 0.6)]),               # Theed on its cliffs
        2: dict(relief=("flat", 4), tex=["URBAN", ("GRASS", ">", 0.55)]),                             # the cities
        3: dict(relief=("rolling", 3, 2, 8), tex=["GRASS", ("SAVANNA", ">", 0.7), ("FARM", ">", 0.92), ("URBAN", ">", 0.975)],
                props=[(243, 0.3), (231, 0.25), (229, 0.06)]),                                        # Great Grass Plains
        4: dict(relief=("rolling", 8, 6, 5), tex=["GRASSHILL", ("FOREST", ">", 0.5)], props=[(229, 0.35), (230, 0.25), (231, 0.15)]),
        5: dict(relief=("rolling", 9, 7, 4), tex=["GRASSHILL", ("GREENMTN", ">", 0.6), ("FARM", ">", 0.92), ("URBAN", ">", 0.975)],
                props=[(230, 0.3), (229, 0.15)]),                                                     # grassy hills
        6: dict(relief=("flat", 2), tex=["JUNGLE2", ("ROCK2", ">", 0.6)], props=[(81, 0.2), (85, 0.2)]),   # Gungan sites
        7: dict(relief=("rolling", 2, 1, 7), tex=["JUNGLE", ("JUNGLE2", ">", 0.5), ("WATER", ">", 0.93)],
                props=[(81, 0.4), (85, 0.3), (126, 0.2)]),                                            # Lianorm Swamp
        8: dict(relief=("flat", 0.3), tex="WATER"),                                                   # seas and lakes
        9: dict(relief=("spires", 20, 10, 0.08, (1.5, 3.0), (24, 48)), tex=["SNOWROCK", ("GREENMTN", ">", 0.5)],
                props=[(230, 0.12)]),                                                                 # the Gallo peaks
        10: dict(relief=("rolling", 6, 4, 5), tex=["GRASSHILL", ("GRASS", ">", 0.5)], props=[(229, 0.3), (231, 0.2)]),   # the Solleu
        11: dict(relief=("flat", 0.3), tex="WATER"),                                                  # Otoh Gunga, underwater
    },
    steep=("ROCK", 6, (3, 4, 5, 10)),
    city={1: 8, 2: 8, 3: 8, 5: 8},   # map/cities.txt 8: Naboo's Theed-style domes (nab_city)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.82, 0.78, 0.66), 2: (0.78, 0.74, 0.64), 3: (0.36, 0.66, 0.22), 4: (0.16, 0.5, 0.24), 5: (0.28, 0.56, 0.22),
            6: (0.32, 0.4, 0.22), 7: (0.22, 0.38, 0.2), 8: (0.1, 0.4, 0.62), 9: (0.62, 0.66, 0.6), 10: (0.3, 0.6, 0.26),
            11: (0.1, 0.4, 0.62)},
)

# models (military_buildings.py place Naboo): big, custom (user rule 2026-10-14); hod_theed_palace retired for hod_nab_theed
PLACEMENT = dict(
    new_models={"hod_nab_theed", "hod_nab_gunga", "hod_nab_sentry"},
    items=[("hod_nab_theed", 1.0, ("at_vp", CAPITAL_VP)), ("hod_nab_gunga", 1.0, ("at_vp", "Otoh Gunga")),
           ("hod_nab_sentry", 1.0, ("at_vp", "Gungan Sentry Post"))],
    no_pad={"hod_nab_gunga"},   # it stands in the lake
    clear={"hod_nab_theed": 6.0, "hod_nab_gunga": 4.0, "hod_nab_sentry": 3.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (naboo_map.py)\n{imp}"
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
