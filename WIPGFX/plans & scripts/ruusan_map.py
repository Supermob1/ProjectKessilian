"""Ruusan (was Celegia), the world of the last battles of the New Sith Wars, as one battlefield before the Clone Wars
(research: WIPGFX/research/ruusan/). The user (2026-10-19): Ruusan in Celegia's place, laid out as the light-side
mirror of Korriban ("light" as in the light side, not small): a scarred desert valley inside a healed green planet, to
show what the Sith did to the region. LEGENDS: once temperate with rivers and forests, burnt to desert and canyons in
the Seven Battles of Ruusan; the Valley of the Jedi, where Kaan's thought bomb took the Brotherhood of Darkness and
the Army of Light, and the mausoleum Johun Othone had raised over it; Lord Hoth and Valenthyne Farfalla's Army of
Light; Olmondo, the old capital; Fort Nowhere and Katarn's Hill beside it; low scented bushes. CANON: canyons, caves,
desert, lakes, rivers; affiliation Confederacy of Independent Systems (owner CIS, the user 2026-10-19; REP before).
LAYOUT IS A DESIGN CHOICE (the sources place only Katarn's Hill near Fort Nowhere), mirroring korriban_map.py: the
Valley of the Jedi across the middle, walled in by ridges (where Korriban's valley has its tombs and crypts, the
thought-bomb cave in the north wall); the Jedi Mausoleum at the valley's west head (Korriban: the Sith Academy); Lord
Hoth's camp on the heights north-west of it; the valley's east mouth opening on Olmondo (Korriban: the ruins of
Dreshdae, here alive); the healed green lands all round: lakes north, forests west with Farfalla's camp, the downs of
Fort Nowhere south.
Legends names: Olmondo, the Valley of the Jedi, Fort Nowhere, Katarn's Hill. Invented: the Jedi Mausoleum (Legends:
a mausoleum, unnamed), the Thought-bomb Cave, Lord Hoth's Encampment and Farfalla's Camp (Legends: the Army of Light,
its camps unnamed), the Sisters' Lakes (after the Three Sisters, the moons), the Brand Forests (after the sun Hoth's
Brand), the Nowhere Downs, the North and South Ridges.
    python "WIPGFX/plans & scripts/ruusan_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ruusan_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 195 province ids are kept (strategic region 76 unchanged); only the pixels move.
Run order: ruusan_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (rus_*) ->
planet_terrain_gen.py --planet Ruusan -> military_buildings.py models hod_rus -> military_buildings.py place Ruusan
-> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Ruusan"
ZONES_JSON = "WIPGFX/Assets/ruusan_zones.json"
ZONES_PNG = "WIPGFX/Assets/ruusan_zones.png"
KIND = {"capital": 1, "valley": 2, "mausoleum": 3, "cave": 4, "camp": 5, "downs": 6, "forest": 7, "lakes": 8,
        "ridge": 9, "town": 10, "hill": 11}
TERRAIN = {"capital": "urban", "valley": "desert", "mausoleum": "hills", "cave": "hills", "camp": "hills",
           "downs": "plains", "forest": "forest", "lakes": "plains", "ridge": "mountain", "town": "plains",
           "hill": "hills"}
SEED = 65
CAPITAL = 65
CAPITAL_VP = "Olmondo"
PORT_STATE = 65
OWNER = {s: "CIS" for s in (65, 612, 613, 614, 615, 616, 617, 1250, 1251)}   # canon: Separatist (user, 2026-10-19)
WARP = (0.1, 9)
TARGET_PASSABLE = 128                # user rule: passable provinces outnumber impassable (~128 / 67)
STRAIGHT = {"mausoleum"}
# features painted in order, the first to claim a pixel keeps it (the ridges before the valley, so they wall it): (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Olmondo", "capital", CAPITAL, 4, [("ell", 0.74, 0.04, 0.17, 0.14, 15)]),
    ("Jedi Mausoleum", "mausoleum", 613, 4, [("rect", -0.5, 0.0, 0.13, 0.17, 0), ("rect", -0.36, 0.0, 0.06, 0.07, 0)]),
    ("Thought-bomb Cave", "cave", 612, 2, [("ell", 0.08, -0.27, 0.09, 0.06, 0), ("cap", 0.08, -0.27, 0.08, -0.06, 0.05)]),
    ("Lord Hoth's Encampment", "camp", 614, 0, [("ell", -0.4, -0.35, 0.24, 0.15, 20)]),
    ("Fort Nowhere", "town", 615, 1, [("ell", 0.2, 0.64, 0.09, 0.07, 0)]),
    ("Katarn's Hill", "hill", 615, 1, [("ell", 0.36, 0.7, 0.08, 0.07, 0)]),
    ("Farfalla's Camp", "camp", 617, 1, [("ell", -0.66, 0.42, 0.09, 0.07, 0)]),
    ("North Ridges", "ridge", 1250, 0, [("cap", -0.28, -0.3, 0.66, -0.24, 0.14), ("cap", 0.2, -0.28, 0.42, -0.38, 0.08)]),
    ("South Ridges", "ridge", 1251, 0, [("cap", -0.7, -0.16, -0.66, 0.24, 0.09), ("cap", -0.66, 0.24, 0.64, 0.22, 0.09)]),
    ("Valley of the Jedi", "valley", 612, 0, [("ell", 0.06, 0.0, 0.58, 0.15, -4), ("ell", -0.12, -0.04, 0.26, 0.17, 10),
                                               ("ell", 0.34, 0.03, 0.26, 0.16, -14)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.78, 0.0), "downs"), 615: ((0.15, 0.75), "downs"), 616: ((0.0, -0.72), "lakes"),
         617: ((-0.72, 0.45), "forest")}
STATE_NAMES = {CAPITAL: "Olmondo", 612: "Valley of the Jedi", 613: "Jedi Mausoleum", 614: "Lord Hoth's Encampment",
               615: "Nowhere Downs", 616: "Sisters' Lakes", 617: "Brand Forests", 1250: "North Ridges",
               1251: "South Ridges"}
IMPASSABLE = {1250, 1251}
VPS = [(CAPITAL, "Olmondo", CAPITAL_VP, 10), (612, "Valley of the Jedi", "Valley of the Jedi", 5),
       (612, "Thought-bomb Cave", "Thought-bomb Cave", 3), (613, "Jedi Mausoleum", "Jedi Mausoleum", 5),
       (614, "Lord Hoth's Encampment", "Lord Hoth's Encampment", 3), (615, "Fort Nowhere", "Fort Nowhere", 3),
       (615, "Katarn's Hill", "Katarn's Hill", 1), (616, "lakes", "Sisters' Lakes", 1),
       (617, "Farfalla's Camp", "Farfalla's Camp", 2)]

# terrain (planet_terrain_gen.py --planet Ruusan). Heights in heightmap steps above the base. The valley a burnt desert
# of sand and cracked brown ground among scorched snags and fallen stones (flora_props 176); round it pale ridges;
# outside them the healed planet (the user, 2026-10-19): green downs and farms, lakes, forests of golden-green
# broadleaves (174) and the scented bushes (175); the Ruusanian towns (map/cities.txt 60, military_buildings.py rus_city)
_GREEN = [(174, 0.2), (175, 0.15)]
TERRAIN_CFG = dict(
    seed=65, base=4, rough=2, open=(2, 6, 7, 8),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 5, 1.5, 6), tex=["GRASS", (13, ">", 0.3)], props=[(174, 0.05)]),   # Olmondo
        2: dict(relief=("mesa", 2, 9, 3, (5, 0.62)), tex=["SAND", ("BROWN", ">", 0.5), ("DUNES", ">", 0.82)],
                props=[(176, 0.1)]),                                                              # the valley
        3: dict(relief=("ramp_top", 12, 5, 4), tex=["ROCK2", ("SAND", ">", 0.6)]),               # the mausoleum
        4: dict(relief=("ramp_top", 14, 8, 3), tex=["ROCK", ("BROWN", ">", 0.55)], props=[(176, 0.1)]),   # the cave
        5: dict(relief=("ramp_top", 11, 6, 4), tex=["GRASSHILL", ("BROWN", ">", 0.6)],
                props=[(174, 0.1), (175, 0.15), (176, 0.06)]),                                   # the camps
        6: dict(relief=("rolling", 4, 2, 6), tex=["GRASS", ("FARM", ">", 0.55), (13, ">", 0.88)],
                props=_GREEN, clusters=[(6, 0.55, [(174, 0.7)])]),                               # the downs
        7: dict(relief=("rolling", 6, 4, 5), tex=["FOREST", ("GRASS", ">", 0.7), (13, ">", 0.93)],
                props=[(174, 0.65), (175, 0.25)]),                                                # the forests
        8: dict(relief=("rolling", 3, 2, 6), tex=["GRASS", ("WATER", ">", 0.68), (13, ">", 0.92)],
                props=_GREEN, clusters=[(5, 0.6, [(174, 0.6)])]),                                # the lakes
        9: dict(relief=("spires", 18, 10, 0.08, (1.5, 3.0), (26, 48)), tex=["ROCK2", ("GREENMTN", ">", 0.55)],
                props=[(175, 0.05)]),                                                              # the ridges
        10: dict(relief=("rolling", 5, 1.5, 6), tex=["GRASS", (13, ">", 0.35)], props=[(175, 0.1)]),   # Fort Nowhere
        11: dict(relief=("ramp_top", 13, 6, 3), tex=["GRASSHILL", ("ROCK2", ">", 0.6)], props=[(175, 0.2)]),   # the hill
    },
    steep=("ROCK2", 6, (2, 6, 7, 8)),
    city={1: 60, 6: 60, 8: 60, 10: 60},   # map/cities.txt 60: the Ruusanian towns (rus_city)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.5, 0.52, 0.4), 2: (0.62, 0.5, 0.34), 3: (0.6, 0.56, 0.46), 4: (0.46, 0.4, 0.34),
            5: (0.42, 0.46, 0.3), 6: (0.42, 0.56, 0.3), 7: (0.24, 0.42, 0.22), 8: (0.36, 0.52, 0.34),
            9: (0.56, 0.54, 0.48), 10: (0.46, 0.54, 0.34), 11: (0.42, 0.48, 0.32)},
)

# models (military_buildings.py place Ruusan): big, custom (user rule 2026-10-14); one Army of Light camp model at both
# camps
PLACEMENT = dict(
    new_models={"hod_rus_olmondo", "hod_rus_mausoleum", "hod_rus_cave", "hod_rus_camp", "hod_rus_fort"},
    items=[("hod_rus_olmondo", 1.0, ("at_vp", CAPITAL_VP)), ("hod_rus_mausoleum", 1.0, ("at_vp", "Jedi Mausoleum")),
           ("hod_rus_cave", 1.0, ("at_vp", "Thought-bomb Cave")),
           ("hod_rus_camp", 0.9, ("at_vp", ["Lord Hoth's Encampment", "Farfalla's Camp"])),
           ("hod_rus_fort", 1.0, ("at_vp", "Fort Nowhere"))],
    clear={"hod_rus_olmondo": 8.5, "hod_rus_mausoleum": 7.0, "hod_rus_cave": 5.0, "hod_rus_camp": 6.5,
           "hod_rus_fort": 5.5},   # the models' own radii: no trees or towns grow through them
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ruusan_map.py)\n{imp}"
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
