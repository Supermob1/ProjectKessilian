"""The Forest Moon of Endor as one battlefield in the Clone Wars (research: WIPGFX/research/endor/; CANON: Bright Tree Village,
redwoods over 1,000 metres tall, Lake Sui ringed by forest with Ewok villages on stilts, Lake Marudi, Mount Krana beyond the
Salma Sands (the Gorax's lair), the Campalan mountain range, forests, savannas, mountains, plains; LEGENDS: the Happy Grove
that holds Bright Tree Village, Hanging Moss Village, Terak's Keep (the Marauders' Stronghold of the Sanyassan), deserts,
lakes, rivers and small seas). Owner: COR (kept). The Imperial shield generator, Platform 4 and Research Station 9 are
Galactic Civil War sites and are left out (Clone Wars era).
LAYOUT IS A DESIGN CHOICE (stated: Bright Tree Village in the Happy Grove, Mount Krana beyond the Salma Sands, Lake Sui
ringed by forest): the Happy Grove in the middle, Lake Sui north-west, Hanging Moss west, Lake Marudi south-west, the Salma
Sands south-east with Mount Krana beyond, Terak's Keep on the eastern savanna, the Campalan range north; the range, Krana,
two lakes, a sea, a gorge and a giant-tree thicket (seven impassable states) carve the corridors.
Names from the sources: every VP, Lake Sui, Lake Marudi, the Salma Sands, Mount Krana, the Campalan range, the Happy Grove.
Invented: the Sui Lakeshore, Marudi Shore, Krana Foothills, Marauder Savanna, Hanging Moss Woods, Redwood Highlands, the
Endor Sea, Dulok Gorge and the Great Thicket.
    python "WIPGFX/plans & scripts/endor_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/endor_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Endor"
ZONES_JSON = "WIPGFX/Assets/endor_zones.json"
ZONES_PNG = "WIPGFX/Assets/endor_zones.png"
KIND = {"village": 1, "keep": 2, "forest": 3, "savanna": 4, "sands": 5, "lake": 6, "ridge": 7, "thicket": 8}
TERRAIN = {"village": "forest", "keep": "hills", "forest": "forest", "savanna": "plains", "sands": "desert",
           "lake": "mountain", "ridge": "mountain", "thicket": "mountain"}
SEED = 61
CAPITAL = 61
CAPITAL_VP = "Bright Tree Village"
CORE = "COR"
PORT_STATE = 61
ROCK_IDS = tuple(range(1646, 1653))
OWNER = {s: "COR" for s in (61, *range(584, 591), *ROCK_IDS)}
WARP = (0.11, 8)
TARGET_PASSABLE = 122                # user rule: passable provinces outnumber impassable
STRAIGHT = {"keep"}
F = lambda name, kind, sid, *shapes: (name, kind, sid, 0, list(shapes))
FEATURES = [
    F("Bright Tree Village", "village", 61, ("ell", 0.0, 0.0, 0.1, 0.08, 20)),
    F("Lake Sui Villages", "village", 585, ("ell", -0.38, -0.32, 0.07, 0.06, 0)),
    F("Hanging Moss Village", "village", 589, ("ell", -0.7, 0.05, 0.07, 0.06, 0)),
    F("Terak's Keep", "keep", 588, ("rect", 0.68, -0.1, 0.07, 0.06, 15)),
    F("Mount Krana", "sands", 587, ("ell", 0.5, 0.66, 0.08, 0.07, 0)),
    F("Lake Sui", "lake", 1648, ("ell", -0.52, -0.5, 0.22, 0.14, -25)),
    F("Lake Marudi", "lake", 1649, ("ell", -0.42, 0.52, 0.2, 0.12, 35)),
    F("Campalan Mountains", "ridge", 1646, ("cap", -0.15, -0.65, 0.55, -0.55, 0.075)),
    F("Krana Massif", "ridge", 1647, ("cap", 0.3, 0.9, 0.85, 0.48, 0.09)),
    F("Endor Sea", "lake", 1650, ("ell", 0.0, -1.0, 0.5, 0.2, 0)),
    F("Dulok Gorge", "ridge", 1651, ("cap", -0.2, 0.25, 0.15, 0.62, 0.05)),
    F("Great Thicket", "thicket", 1652, ("cap", 0.3, -0.05, 0.42, -0.42, 0.06)),
]
SEEDS = {61: ((0.0, 0.05), "forest"), 584: ((0.15, -0.4), "forest"), 585: ((-0.35, -0.25), "forest"),
         586: ((0.25, 0.45), "sands"), 587: ((0.65, 0.65), "sands"), 588: ((0.7, 0.0), "savanna"),
         589: ((-0.75, 0.0), "forest"), 590: ((-0.5, 0.65), "forest")}
STATE_NAMES = {CAPITAL: "Happy Grove", 584: "Redwood Highlands", 585: "Sui Lakeshore", 586: "Salma Sands",
               587: "Krana Foothills", 588: "Marauder Savanna", 589: "Hanging Moss Woods", 590: "Marudi Shore",
               1646: "Campalan Mountains", 1647: "Krana Massif", 1648: "Lake Sui", 1649: "Lake Marudi", 1650: "Endor Sea",
               1651: "Dulok Gorge", 1652: "Great Thicket"}
IMPASSABLE = set(ROCK_IDS)
VPS = [(CAPITAL, "Bright Tree Village", CAPITAL_VP, 15), (585, "Lake Sui Villages", "Lake Sui Villages", 3),
       (589, "Hanging Moss Village", "Hanging Moss Village", 3), (588, "Terak's Keep", "Terak's Keep", 5),
       (587, "Mount Krana", "Mount Krana", 3), (586, "Salma Sands", "Salma Sands", 1), (584, "Redwood Highlands", "Redwood Highlands", 1),
       (590, "Marudi Shore", "Lake Marudi", 1)]

TERRAIN_CFG = dict(
    seed=61, base=4, rough=2, open=(1, 2, 3, 4, 5),
    zones={
        1: dict(relief=("rolling", 4, 3, 5), tex=["DFOREST", ("FOREST", ">", 0.5), (26, ">", 0.93)], props=[(152, 0.55), (153, 0.3)]),   # villages
        2: dict(relief=("ramp_top", 9, 5, 3), tex=["ROCK2", ("GRASSHILL", ">", 0.6)]),                # Terak's Keep crag
        3: dict(relief=("rolling", 6, 4, 5), tex=["DFOREST", ("FOREST", ">", 0.5), ("GRASS", ">", 0.95), (26, ">", 0.975)],
                props=[(152, 0.6), (153, 0.3), (229, 0.2)]),                                          # the redwoods
        4: dict(relief=("rolling", 3, 2, 7), tex=["SAVANNA", ("GRASS", ">", 0.55)], props=[(231, 0.2), (152, 0.05)]),   # savanna
        5: dict(relief=("rolling", 4, 3, 6), tex=["SAND", ("DUNES", ">", 0.6), ("ROCK2", ">", 0.9)], props=[(225, 0.08)]),   # sands
        6: dict(relief=("flat", 0.3), tex="WATER"),                                                   # lakes, the sea
        7: dict(relief=("spires", 18, 10, 0.08, (1.5, 3.0), (24, 48)), tex=["GREENMTN", ("ROCK", ">", 0.55)],
                props=[(152, 0.15)]),                                                                 # Campalan, Krana
        8: dict(relief=("rolling", 8, 5, 4), tex=["DFOREST", ("JUNGLE2", ">", 0.5)], props=[(152, 0.9), (153, 0.4)]),   # thicket
    },
    steep=("ROCK", 6, (1, 2, 3, 4, 5)),
    city={1: 146, 3: 146},   # map/cities.txt 146: Ewok tree villages (end_town)
    prop_clear=1.2,
    shore_rise=(4, 2.0),
    colors={1: (0.1, 0.4, 0.2), 2: (0.46, 0.44, 0.36), 3: (0.06, 0.34, 0.16), 4: (0.66, 0.64, 0.34), 5: (0.8, 0.66, 0.42),
            6: (0.12, 0.36, 0.5), 7: (0.32, 0.38, 0.32), 8: (0.04, 0.26, 0.12)},   # deep redwood green, golden savanna, sand
)

# models (military_buildings.py place Endor): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_end_brighttree", "hod_end_keep", "hod_end_sui"},
    items=[("hod_end_brighttree", 1.0, ("at_vp", CAPITAL_VP)), ("hod_end_keep", 1.0, ("at_vp", "Terak's Keep")),
           ("hod_end_sui", 1.0, ("at_vp", "Lake Sui Villages"))],
    clear={"hod_end_brighttree": 5.0, "hod_end_keep": 4.5, "hod_end_sui": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (endor_map.py)\n{imp}"
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
