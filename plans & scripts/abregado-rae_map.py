"""Abregado-Rae, the smugglers' Core world, as one battlefield before the Clone Wars (research: WIPGFX/research/abregado_rae/).
CANON: a rather lawless world whose main spaceport was as close to a safe dock for smugglers as the Core had; the
Abregado-Rae Spaceport and the Cantina District next to it. LEGENDS: temperate, hills, lakes and rivers; Abregado-rae
Spaceport the capital, its water canals used for transport; the LoBue Cantina near the Old Patch; the Southern Hills
close to the spaceport, home of a peaceful dissident movement; Le Yer, a popular coastal resort, with its extension
Phyrstal Island reached by hydrobikes or floatboats; the Gilt Gushers; clans in the mountains; the Gados. Owner: REP
(as before).
LAYOUT IS A DESIGN CHOICE beyond the stated relationships: the spaceport city in the middle, its canals, the Old Patch and
the Cantina District inside it; the Southern Hills south of it; Le Yer out on the Le Yer Sea in the south-west (the user, 2026-10-22: in the sea,
not on land), Phyrstal Island beyond it; the Gilt Gushers east; the Abregado Mountains and the Gado Highlands of the clans in the
north-west; the Great Lake and the Northern Lakes north (the Byss lane); the Eastern Riverlands south-east (the Fondor
lane); the Eastern Peaks north-east.
Names from the sources: Abregado-rae Spaceport, Cantina District, LoBue Cantina, Old Patch, Southern Hills, Le Yer,
Phyrstal Island, Gilt Gushers. Invented: Gado Highlands, Northern Lakes, Eastern Riverlands, Western Lowlands, Le Yer
Sea, Great Lake, Abregado Mountains, Eastern Peaks.
    python "WIPGFX/plans & scripts/abregado-rae_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/abregado-rae_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Abregado-Rae"
ZONES_JSON = "WIPGFX/Assets/abregado-rae_zones.json"
ZONES_PNG = "WIPGFX/Assets/abregado-rae_zones.png"
KIND = {"city": 1, "cantina": 2, "resort": 3, "island": 4, "gushers": 5, "hills": 6, "plains": 7, "rivers": 8,
        "forest": 9, "lake": 10, "sea": 11, "mountains": 12}
TERRAIN = {"city": "urban", "cantina": "urban", "resort": "urban", "island": "plains", "gushers": "hills", "hills": "hills",
           "plains": "plains", "rivers": "marsh", "forest": "forest", "lake": "mountain", "sea": "mountain",
           "mountains": "mountain"}
SEED = 13
CAPITAL = 13
CAPITAL_VP = "Abregado-rae Spaceport"
CORE = "REP"
PORT_STATE = 305                     # Eastern Riverlands, out to the rim (the Fondor lane)
OWNER = {s: "REP" for s in (13, *range(300, 307), 1377, 1378, 1379, 1380)}
WARP = (0.1, 9)
TARGET_PASSABLE = 122                # user rule: passable provinces outnumber impassable
STRAIGHT = {"cantina"}
FEATURES = [
    ("Abregado-rae Spaceport", "city", CAPITAL, 3, [("ell", 0.0, -0.05, 0.15, 0.1, 0)]),
    ("Old Patch", "cantina", CAPITAL, 1, [("ell", -0.13, 0.08, 0.05, 0.04, 0)]),
    ("Cantina District", "cantina", CAPITAL, 1, [("ell", 0.14, 0.08, 0.06, 0.04, 0)]),
    ("Le Yer", "resort", 301, 1, [("ell", -0.66, 0.44, 0.14, 0.06, 0)]),     # out on the sea (the user, 2026-10-22)
    ("Phyrstal Island", "island", 301, 1, [("ell", -0.83, 0.4, 0.065, 0.06, 0)]),
    ("Le Yer Sea", "sea", 1378, 0, [("ell", -0.86, 0.44, 0.3, 0.36, 20)]),
    ("Gilt Gushers", "gushers", 302, 1, [("ell", 0.55, -0.05, 0.07, 0.06, 0)]),
    ("Abregado Mountains", "mountains", 1377, 0, [("cap", -0.68, -0.32, -0.16, -0.52, 0.1)]),
    ("Eastern Peaks", "mountains", 1380, 0, [("cap", 0.6, -0.58, 0.86, -0.22, 0.09)]),
    ("Great Lake", "lake", 1379, 0, [("ell", 0.24, -0.46, 0.2, 0.11, 15)]),
]
SEEDS = {CAPITAL: ((0.0, -0.05), "city"), 300: ((0.05, 0.52), "hills"), 301: ((-0.48, 0.42), "plains"),
         302: ((0.55, 0.05), "plains"), 303: ((-0.45, -0.72), "hills"), 304: ((0.05, -0.76), "plains"),
         305: ((0.55, 0.56), "rivers"), 306: ((-0.62, -0.02), "forest")}
STATE_NAMES = {CAPITAL: "Abregado-rae Spaceport", 300: "Southern Hills", 301: "Le Yer", 302: "Gilt Gushers",
               303: "Gado Highlands", 304: "Northern Lakes", 305: "Eastern Riverlands", 306: "Western Lowlands",
               1377: "Abregado Mountains", 1378: "Le Yer Sea", 1379: "Great Lake", 1380: "Eastern Peaks"}
IMPASSABLE = {1377, 1378, 1379, 1380}
VPS = [(CAPITAL, "Abregado-rae Spaceport", CAPITAL_VP, 20), (CAPITAL, "Old Patch", "LoBue Cantina", 2),
       (CAPITAL, "Cantina District", "Cantina District", 3), (301, "Le Yer", "Le Yer", 5),
       (301, "Phyrstal Island", "Phyrstal Island", 2), (302, "Gilt Gushers", "Gilt Gushers", 3),
       (300, "hills", "Southern Hills", 3), (303, "hills", "Gado Highlands", 2), (304, "plains", "Northern Lakes", 1),
       (305, "rivers", "Eastern Riverlands", 1), (306, "forest", "Western Lowlands", 1)]

TERRAIN_CFG = dict(
    seed=13, base=4, rough=2, open=(6, 7, 8, 9),
    zones={
        1: dict(relief=("flat", 4), tex=["URBAN", ("WATER", ">", 0.92)]),                             # the spaceport and its canals
        2: dict(relief=("flat", 4), tex="URBAN"),                                                     # Old Patch, Cantina District
        3: dict(relief=("flat", 0.3), tex=30),                                                       # Le Yer, on the water
        4: dict(relief=("rolling", 4, 2, 4), tex=["SAND", ("GRASS", ">", 0.5)], props=[(36, 0.3)]),   # Phyrstal Island
        5: dict(relief=("rolling", 5, 3, 5), tex=["BROWN", ("ROCK2", ">", 0.5), ("WATER", ">", 0.9)]),   # the Gilt Gushers
        6: dict(relief=("rolling", 10, 7, 5), tex=["GRASSHILL", ("GRASS", ">", 0.5), (13, ">", 0.95)], props=[(36, 0.3), (37, 0.3)]),
        7: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("FARM", ">", 0.6), (13, ">", 0.94)], props=[(37, 0.35), (36, 0.1)]),
        8: dict(relief=("rolling", 2, 2, 8), tex=["GRASS", ("WATER", ">", 0.75), (13, ">", 0.95)], props=[(37, 0.3), (36, 0.15)]),
        9: dict(relief=("rolling", 6, 4, 6), tex=["FOREST", ("GRASS", ">", 0.6)], props=[(36, 0.6)]),
        10: dict(relief=("flat", 0.3), tex="WATER"),                                                  # the Great Lake
        11: dict(relief=("flat", 0.3), tex="WATER"),                                                  # the Le Yer Sea
        12: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["ROCK", ("SNOWROCK", ">", 0.8)], props=[(36, 0.1)]),
    },
    steep=("ROCK", 6, (6, 7, 8, 9)),
    city={1: 98, 2: 98, 3: 98, 6: 98, 7: 98},   # map/cities.txt 98: Abregado's canal towns (abr_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.72, 0.64, 0.56), 2: (0.66, 0.5, 0.42), 3: (0.82, 0.74, 0.6), 4: (0.6, 0.66, 0.4), 5: (0.78, 0.62, 0.22),
            6: (0.36, 0.6, 0.26), 7: (0.5, 0.66, 0.24), 8: (0.26, 0.56, 0.44), 9: (0.16, 0.44, 0.2), 10: (0.12, 0.44, 0.66),
            11: (0.08, 0.36, 0.62), 12: (0.56, 0.52, 0.5)},   # signature far look: lime hills, gilded gushers
)

PLACEMENT = dict(
    new_models={"hod_abr_spaceport", "hod_abr_cantina", "hod_abr_leyer", "hod_abr_gushers"},
    items=[("hod_abr_spaceport", 1.0, ("at_vp", CAPITAL_VP)), ("hod_abr_cantina", 0.8, ("at_vp", "LoBue Cantina")),
           ("hod_abr_cantina", 0.7, ("at_vp", "Cantina District")), ("hod_abr_leyer", 1.0, ("at_vp", "Le Yer")),
           ("hod_abr_gushers", 1.0, ("at_vp", "Gilt Gushers"))],
    clear={"hod_abr_spaceport": 6.0, "hod_abr_cantina": 2.5, "hod_abr_leyer": 4.5, "hod_abr_gushers": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (abregado-rae_map.py)\n{imp}"
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
