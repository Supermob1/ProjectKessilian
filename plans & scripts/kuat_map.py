"""Kuat, the garden world of Kuat Drive Yards, as one battlefield before the Clone Wars (research: WIPGFX/research/kuat/;
the user, 2026-10-21: the Legends garden world with the KDY ring in orbit, split into states). LEGENDS: a green,
temperate world of three continents and scattered islands, lush forests and rolling green plains, landscaped by its
noble houses; Kuat City, the capital, whose elegant towers and spires echo the famous orbital shipyards; Tekshar Falls,
a five-hundred-metre man-made waterfall through the city's entertainment centre (a VP only: no waterfall model, the
user, 2026-10-21); the Gardens of Tralala; Kuat Drive Yards in orbit. Owner: KUA (as before).
LAYOUT IS A DESIGN CHOICE: three continents parted by the Inner Sea, the Southern Sea and the Western Gulf (impassable) but touching at
narrow land bridges; Kuat City in the middle of the main continent with the Kuati Range (impassable) behind it, the Gardens
of Tralala west of it, the noble estates in the north (the Balmorra lane), the Drive Works coast east where KDY's ground
works send crews and parts to the ring (the Neimodia lane), the western continent's forests (the Alderaan lane), the
southern continent's plains (the Commenor lane) and the Kuati Isles off its coast; the Kuat Drive Yards as a great arc
of the orbital ring beside the disc.
Names from the sources: Kuat City, Tekshar Falls, Gardens of Tralala, Kuat Drive Yards. Invented: every other state and VP.
    python "WIPGFX/plans & scripts/kuat_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/kuat_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 61 province ids are kept (strategic region unchanged); only the pixels move. The old single state 15 keeps the
capital; the new states 1335-1340 get the old state's manpower shared out (kuat_map.split_manpower, run after the map).
Run order: kuat_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (kua_*) ->
planet_terrain_gen.py --planet Kuat -> military_buildings.py kuat_atlas, models hod_kua_ -> coruscant_buildings.py wire ->
military_buildings.py place Kuat -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Kuat"
ZONES_JSON = "WIPGFX/Assets/kuat_zones.json"
ZONES_PNG = "WIPGFX/Assets/kuat_zones.png"
KIND = {"city": 1, "estate": 2, "gardens": 3, "works": 4, "plains": 5, "forest": 6, "hills": 7, "coast": 8, "sea": 9,
        "mountains": 10}
TERRAIN = {"city": "urban", "estate": "plains", "gardens": "plains", "works": "urban", "plains": "plains",
           "forest": "forest", "hills": "hills", "coast": "plains", "sea": "mountain", "mountains": "mountain"}
SEED = 15
CAPITAL = 15
CAPITAL_VP = "Kuat City"
CORE = "KUA"
PORT_STATE = 1339                    # the Drive Works coast
OWNER = {s: "KUA" for s in (15, 1335, 1336, 1337, 1338, 1339, 1340, 1341, 1342, 1343, 1344)}
WARP = (0.12, 9)
TARGET_PASSABLE = 40                 # user rule: passable provinces outnumber impassable (~40 / 21)
STRAIGHT = {"works"}
FEATURES = [
    ("Kuat City", "city", CAPITAL, 3, [("ell", 0.08, -0.08, 0.17, 0.12, 0)]),
    ("Tekshar Falls", "city", CAPITAL, 1, [("ell", 0.26, 0.02, 0.06, 0.05, 0)]),
    ("Gardens of Tralala", "gardens", 1335, 1, [("ell", -0.28, 0.02, 0.1, 0.08, 0)]),
    ("Kuati Estates", "estate", 1336, 1, [("ell", 0.12, -0.6, 0.1, 0.08, 0)]),
    ("KDY Ground Works", "works", 1339, 1, [("rect", 0.68, 0.08, 0.12, 0.1, 10)]),
    ("Inner Sea", "sea", 1341, 0, [("cap", -0.45, -0.98, -0.42, -0.3, 0.1), ("cap", -0.42, -0.3, -0.5, 0.12, 0.09)]),
    ("Southern Sea", "sea", 1342, 0, [("cap", 0.0, 0.48, 1.0, 0.52, 0.09)]),
    ("Western Gulf", "sea", 1344, 0, [("cap", -1.0, 0.52, -0.3, 0.5, 0.09)]),
    ("Kuati Range", "mountains", 1343, 0, [("cap", 0.0, -0.32, 0.42, -0.26, 0.08), ("cap", 0.42, -0.26, 0.52, -0.05, 0.07)]),
]
SEEDS = {CAPITAL: ((0.05, -0.05), "plains"), 1335: ((-0.25, 0.05), "plains"), 1336: ((0.1, -0.65), "hills"),
         1337: ((-0.75, -0.2), "forest"), 1338: ((0.0, 0.75), "plains"), 1339: ((0.75, 0.05), "coast"),
         1340: ((0.65, 0.75), "coast")}
STATE_NAMES = {CAPITAL: "Kuat City", 1335: "Tralala", 1336: "Kuati Estates", 1337: "Western Continent",
               1338: "Southern Continent", 1339: "Drive Works Coast", 1340: "Kuati Isles", 1341: "Inner Sea",
               1342: "Southern Sea", 1343: "Kuati Range", 1344: "Western Gulf"}
IMPASSABLE = {1341, 1342, 1343, 1344}
VPS = [(CAPITAL, "Kuat City", CAPITAL_VP, 15), (CAPITAL, "Tekshar Falls", "Tekshar Falls", 2),
       (1335, "Gardens of Tralala", "Gardens of Tralala", 3), (1336, "Kuati Estates", "Kuati Estates", 3),
       (1339, "KDY Ground Works", "KDY Ground Works", 5), (1337, "forest", "Western Continent", 1),
       (1338, "plains", "Southern Continent", 1), (1340, "coast", "Kuati Isles", 1)]

TERRAIN_CFG = dict(
    seed=15, base=4, rough=2, open=(5, 6, 7, 8),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("GRASS", ">", 0.55)]),                             # Kuat City
        2: dict(relief=("rolling", 6, 2, 6), tex=["GRASS", ("FARM", ">", 0.6), (13, ">", 0.95)], props=[(240, 0.3), (241, 0.3)]),   # estates
        3: dict(relief=("rolling", 4, 2, 6), tex=["GRASS", ("FARM", ">", 0.5)], props=[(241, 0.55), (240, 0.25)]),  # Tralala
        4: dict(relief=("flat", 4), tex=["URBAN", ("ROCK2", ">", 0.6)]),                              # the ground works
        5: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("FARM", ">", 0.6), (13, ">", 0.94)], props=[(240, 0.2), (241, 0.15)]),
        6: dict(relief=("rolling", 6, 4, 6), tex=["FOREST", ("DFOREST", ">", 0.5)], props=[(240, 0.7)]),
        7: dict(relief=("rolling", 10, 6, 5), tex=["GRASSHILL", ("GRASS", ">", 0.5), (13, ">", 0.95)], props=[(240, 0.35)]),
        8: dict(relief=("rolling", 3, 2, 8), tex=["GRASS", ("SAVANNA", ">", 0.6), (13, ">", 0.94)], props=[(241, 0.2)]),
        9: dict(relief=("flat", 0.3), tex="WATER"),
        10: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["GREENMTN", ("ROCK", ">", 0.5), ("SNOWROCK", ">", 0.9)]),
    },
    steep=("ROCK", 6, (5, 6, 7, 8)),
    city={1: 88, 2: 88, 4: 88, 5: 88, 8: 88},   # map/cities.txt 88: Kuat's elegant spire towns (kua_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.601, 0.66, 0.693), 2: (0.13, 0.588, 0.112), 3: (0.149, 0.609, 0.131), 4: (0.504, 0.558, 0.588), 5: (0.135, 0.588, 0.076), 6: (0.064, 0.42, 0.122), 7: (0.157, 0.525, 0.125), 8: (0.196, 0.588, 0.147), 9: (0.05, 0.52, 0.62), 10: (0.301, 0.483, 0.303)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)


def orbit(ctx):
    """the Kuat Drive Yards (Legends: the famous orbital shipyards), an arc of the ring beside the disc"""
    (cy, cx), R = ctx["z"]["centre"], ctx["z"]["radius"]
    ctx["put"]("hod_kua_yards", 1.0, cy - 0.3 * R, cx + R + 0.95 * R)


PLACEMENT = dict(
    new_models={"hod_kua_city", "hod_kua_gardens", "hod_kua_estate", "hod_kua_works", "hod_kua_yards"},
    items=[("hod_kua_city", 1.0, ("at_vp", "Kuat City")), ("hod_kua_gardens", 0.9, ("at_vp", "Gardens of Tralala")),
           ("hod_kua_estate", 0.9, ("at_vp", "Kuati Estates")), ("hod_kua_works", 1.0, ("at_vp", "KDY Ground Works"))],
    clear={"hod_kua_city": 6.0, "hod_kua_gardens": 3.5, "hod_kua_estate": 3.5, "hod_kua_works": 4.5},
    hook=orbit,
)


def split_manpower():
    """after the map: the old single state's manpower and category shared out over the new passable states (the map
    script gives brand-new states 1000 manpower and wasteland_sector)"""
    files = {int(re.match(r"(\d+)-", os.path.basename(f)).group(1)): f for f in glob.glob(f"history/states/*-{PLANET} - *.txt")}
    files[CAPITAL] = next(f for f in glob.glob(f"history/states/{CAPITAL}-{PLANET}*.txt"))
    new = [s for s in SEEDS if s != CAPITAL]
    cap = open(files[CAPITAL], encoding="utf-8").read()
    total = int(re.search(r"manpower = (\d+)", cap).group(1))
    if total < 500000:
        return print("manpower already split")
    share = total // (len(new) + 2)                                            # the capital keeps three shares
    open(files[CAPITAL], "w", encoding="utf-8", newline="\n").write(re.sub(r"manpower = \d+", f"manpower = {total - share * len(new)}", cap))
    for s in new:
        t = open(files[s], encoding="utf-8").read()
        t = re.sub(r"manpower = \d+", f"manpower = {share}", t)
        t = re.sub(r"state_category = \w+", "state_category = large_planet", t)
        open(files[s], "w", encoding="utf-8", newline="\n").write(t)
    print("manpower split:", total, "->", share, "each over", new)


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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (kuat_map.py)\n{imp}"
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
