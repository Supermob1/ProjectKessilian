"""Mimban, the mist-drowned swamp world, as one battlefield before the Clone Wars (research: WIPGFX/research/mimban/).
CANON: a humid world of rainforests, swamps and mud fields under a dense, ionized, storm-wracked sky, its marshlands
always draped in mist; the Nanth flatlands, where Iasento led a Mimbanese tribe before the Clone Wars; the Southern
Marshlands. LEGENDS: jungles, swamps and quickclay; the Temple of Pomojema, a great ziggurat of volcanic rock holding the
Kaiburr crystal in its statue; the Thrella wells, age-old shafts the Coway later joined to their tunnels; Dreypa's
Oubliette (fought over in 19 BBY). Owner: MIM (as before).
LAYOUT IS A DESIGN CHOICE: the Nanth flatlands in the middle with the Mimbanese stilt village; the Temple of Pomojema in
the volcanic highlands north-east (the Ruusan lane); the Thrella Barrens north-west (the Manaan lane); the deep
rainforest west with Dreypa's Oubliette; the Coway lands south-west; the mud fields south with a mining camp (the
Allanteen VI lane); the Southern Marshlands south-east (the Falleen lane); the Quickclay Bogs, the Mist Lakes, the Black
Peaks and the Northern Mire impassable.
Names from the sources: Nanth Flatlands, Southern Marshlands, Temple of Pomojema, Thrella Wells, Dreypa's Oubliette,
the Coway. Invented: Nanth Village, the mining camp, the Pomojema Highlands, the Thrella Barrens, the Deep Rainforest,
the Coway Warrens, the Mud Fields and the impassable regions.
    python "WIPGFX/plans & scripts/mimban_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/mimban_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Mimban"
ZONES_JSON = "WIPGFX/Assets/mimban_zones.json"
ZONES_PNG = "WIPGFX/Assets/mimban_zones.png"
KIND = {"village": 1, "temple": 2, "wells": 3, "oubliette": 4, "warrens": 5, "mine": 6, "swamp": 7, "jungle": 8,
        "mud": 9, "highlands": 10, "bog": 11, "lake": 12, "peaks": 13}
TERRAIN = {"village": "marsh", "temple": "hills", "wells": "hills", "oubliette": "jungle", "warrens": "hills", "mine": "plains",
           "swamp": "marsh", "jungle": "jungle", "mud": "marsh", "highlands": "hills", "bog": "mountain", "lake": "mountain",
           "peaks": "mountain"}
SEED = 28
CAPITAL = 28
CAPITAL_VP = "Nanth Village"
CORE = "MIM"
PORT_STATE = 392                     # the mud fields' camp
OWNER = {s: "MIM" for s in (28, 387, 388, 389, 390, 391, 392, 1363, 1364, 1365, 1366)}
WARP = (0.1, 9)
TARGET_PASSABLE = 128
STRAIGHT = {"mine"}
FEATURES = [
    ("Nanth Village", "village", CAPITAL, 2, [("ell", 0.0, 0.0, 0.12, 0.09, 0)]),
    ("Temple of Pomojema", "temple", 388, 1, [("ell", 0.5, -0.45, 0.07, 0.07, 0)]),
    ("Thrella Wells", "wells", 389, 1, [("ell", -0.45, -0.5, 0.07, 0.06, 0)]),
    ("Dreypa's Oubliette", "oubliette", 390, 1, [("ell", -0.62, 0.05, 0.06, 0.06, 0)]),
    ("Coway Warrens", "warrens", 391, 1, [("ell", -0.4, 0.55, 0.07, 0.06, 0)]),
    ("Mimban Mining Camp", "mine", 392, 1, [("rect", 0.05, 0.62, 0.08, 0.06, 0)]),
    ("Black Peaks", "peaks", 1365, 0, [("cap", 0.32, -0.62, 0.72, -0.55, 0.1), ("cap", 0.72, -0.55, 0.78, -0.2, 0.08)]),
    ("Quickclay Bogs", "bog", 1363, 0, [("cap", -0.25, 0.18, 0.25, 0.32, 0.08), ("cap", 0.25, 0.32, 0.5, 0.15, 0.07)]),
    ("Mist Lakes", "lake", 1364, 0, [("ell", -0.25, -0.3, 0.14, 0.08, 20), ("cap", -0.85, -0.15, -0.7, 0.25, 0.09)]),
    ("Northern Mire", "bog", 1366, 0, [("ell", 0.0, -0.9, 0.5, 0.15, 0)]),
]
SEEDS = {CAPITAL: ((0.0, 0.0), "swamp"), 387: ((0.55, 0.5), "swamp"), 388: ((0.5, -0.4), "highlands"),
         389: ((-0.45, -0.55), "mud"), 390: ((-0.6, 0.0), "jungle"), 391: ((-0.4, 0.6), "jungle"), 392: ((0.05, 0.7), "mud")}
STATE_NAMES = {CAPITAL: "Nanth Flatlands", 387: "Southern Marshlands", 388: "Pomojema Highlands", 389: "Thrella Barrens",
               390: "Deep Rainforest", 391: "Coway Lands", 392: "Mud Fields", 1363: "Quickclay Bogs", 1364: "Mist Lakes",
               1365: "Black Peaks", 1366: "Northern Mire"}
IMPASSABLE = {1363, 1364, 1365, 1366}
VPS = [(CAPITAL, "Nanth Village", CAPITAL_VP, 10), (388, "Temple of Pomojema", "Temple of Pomojema", 5),
       (389, "Thrella Wells", "Thrella Wells", 3), (390, "Dreypa's Oubliette", "Dreypa's Oubliette", 3),
       (391, "Coway Warrens", "Coway Warrens", 2), (392, "Mimban Mining Camp", "Mimban Mining Camp", 3),
       (387, "swamp", "Southern Marshlands", 2), (CAPITAL, "swamp", "Nanth Flatlands", 1)]

TERRAIN_CFG = dict(
    seed=28, base=3, rough=2, open=(7, 8, 9, 10),
    zones={
        1: dict(relief=("flat", 2), tex=["WATER", ("JUNGLE", ">", 0.5), (26, ">", 0.7)], props=[(255, 0.3)]),        # the stilt village
        2: dict(relief=("ramp_top", 14, 8, 3), tex=["ROCK", ("BROWNMTN", ">", 0.5)]),                 # Pomojema
        3: dict(relief=("flat", 5), tex=["BROWN", ("ROCK2", ">", 0.5)], props=[(30, 0.1)]),          # the wells
        4: dict(relief=("flat", 3), tex=["JUNGLE", ("ROCK2", ">", 0.5)], props=[(254, 0.4)]),         # the oubliette
        5: dict(relief=("rolling", 6, 4, 4), tex=["JUNGLE", ("BROWN", ">", 0.5)], props=[(254, 0.4)]),
        6: dict(relief=("flat", 3), tex=["BROWN", ("URBAN", ">", 0.6)]),                              # the mining camp
        7: dict(relief=("rolling", 1, 1, 6), tex=["WATER", ("JUNGLE", ">", 0.45), ("JUNGLE2", ">", 0.8), (26, ">", 0.96)],
                props=[(254, 0.35), (255, 0.4), (30, 0.15)]),                                        # swamps
        8: dict(relief=("rolling", 4, 3, 6), tex=["JUNGLE2", ("JUNGLE", ">", 0.5)], props=[(254, 0.75), (30, 0.2)]),
        9: dict(relief=("rolling", 2, 2, 6), tex=["BROWN", ("WATER", "<", 0.3), ("JUNGLE", ">", 0.85)], props=[(255, 0.2), (30, 0.1)]),
        10: dict(relief=("rolling", 9, 6, 5), tex=["ROCK2", ("JUNGLE", ">", 0.5)], props=[(254, 0.3)]),
        11: dict(relief=("flat", 0.5), tex=["BROWN", ("WATER", ">", 0.5)], props=[(255, 0.2)]),       # quickclay, mire
        12: dict(relief=("flat", 0.3), tex="WATER"),
        13: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["ROCK", ("BROWNMTN", ">", 0.6)]),
    },
    steep=("ROCK", 6, (7, 8, 9, 10)),
    city={1: 94, 6: 94, 7: 94},
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.378, 0.265, 0.223), 2: (0.252, 0.213, 0.237), 3: (0.42, 0.236, 0.298), 4: (0.156, 0.318, 0.336), 5: (0.357, 0.201, 0.149), 6: (0.42, 0.236, 0.298), 7: (0.231, 0.333, 0.357), 8: (0.109, 0.292, 0.315), 9: (0.399, 0.189, 0.251), 10: (0.357, 0.24, 0.231), 11: (0.378, 0.169, 0.231), 12: (0.22, 0.24, 0.3), 13: (0.21, 0.173, 0.195)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)

PLACEMENT = dict(
    new_models={"hod_mim_village", "hod_mim_temple", "hod_mim_wells", "hod_mim_oubliette", "hod_mim_mine"},
    items=[("hod_mim_village", 1.0, ("at_vp", "Nanth Village")), ("hod_mim_temple", 1.0, ("at_vp", "Temple of Pomojema")),
           ("hod_mim_wells", 0.9, ("at_vp", "Thrella Wells")), ("hod_mim_oubliette", 0.9, ("at_vp", "Dreypa's Oubliette")),
           ("hod_mim_mine", 0.9, ("at_vp", "Mimban Mining Camp"))],
    clear={"hod_mim_village": 5.0, "hod_mim_temple": 4.5, "hod_mim_wells": 3.0, "hod_mim_oubliette": 3.0, "hod_mim_mine": 3.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (mimban_map.py)\n{imp}"
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
