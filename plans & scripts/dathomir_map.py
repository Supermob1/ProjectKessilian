"""Dathomir, the red world of the Nightsisters, as one battlefield before the Clone Wars (research:
WIPGFX/research/dathomir/). CANON: bathed in a blood-red mist; murky swamps, thick forests, barren rocks; the
Nightsister lair, a stone fortress built into the side of a mountain, with the Hidden Cave; the Nightbrother village
carved into the rock and its arena; the Nardithi Cluster of hexagonal spikes in the jungle; the Dreaming River, Misty
Falls, the Great Canyon, the Red Hills, the Rift Valley, the Haunted Lands. LEGENDS: the Singing Mountain clan's
fortress; Blue Desert City; coastal lakes and tar pits.
Owner: DHT (as before). User (2026-10-19): landmarks the Nightsister lair, the Nightbrother village and arena, the
Singing Mountain clan and the Nardithi Cluster.
LAYOUT IS A DESIGN CHOICE: the Haunted Lands' swamps and mountains in the middle-west with the lair, the Nightbrother
lands' rock spires north-east beyond the Great Canyon (impassable, from the northern rim), the Rift Valley north-west,
the Blue Desert far west, Singing Mountain south-west, the Dreaming River and Misty Falls south, the Nardithi Cluster's
jungle south-east, the Red Hills east, the Tar Lakes (impassable) in the centre-south-east.
Canon names: the Nightsister Lair, the Nightbrother Village and Arena, the Nardithi Cluster, the Dreaming River, Misty
Falls, the Great Canyon, the Red Hills, the Rift Valley, the Haunted Lands. Legends: Singing Mountain, Blue Desert City.
Invented: the Nightbrother Lands, the Blue Desert (as a region), the Tar Lakes (named for the Legends tar pits).
    python "WIPGFX/plans & scripts/dathomir_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/dathomir_map.py" --dry OUT.png      layout + every check, writes only OUT.png
153 province ids are kept (201 before; 48 impassable ones went to Concordia); only the pixels move.
Run order: dathomir_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (dat_*) ->
planet_terrain_gen.py --planet Dathomir -> military_buildings.py models hod_dat -> military_buildings.py place Dathomir
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

PLANET = "Dathomir"
ZONES_JSON = "WIPGFX/Assets/dathomir_zones.json"
ZONES_PNG = "WIPGFX/Assets/dathomir_zones.png"
KIND = {"lair": 1, "village": 2, "arena": 3, "fortress": 4, "cluster": 5, "swamp": 6, "forest": 7, "rocks": 8,
        "hills": 9, "desert": 10, "river": 11, "canyon": 12, "tar": 13, "jungle": 14}
TERRAIN = {"lair": "hills", "village": "hills", "arena": "hills", "fortress": "hills", "cluster": "hills",
           "swamp": "marsh", "forest": "forest", "rocks": "hills", "hills": "hills", "desert": "desert",
           "river": "marsh", "canyon": "mountain", "tar": "mountain", "jungle": "jungle"}
SEED = 95
CAPITAL = 95
CAPITAL_VP = "Nightsister Lair"
PORT_STATE = 817                     # the capital state is inland: the fleet lies off the Blue Desert
OWNER = {s: "DHT" for s in (95, 811, 812, 813, 814, 815, 816, 817, 1219, 1220)}
WARP = (0.13, 9)
TARGET_PASSABLE = 134                # user rule: passable provinces outnumber impassable (~134 / 19)
# the province limit (user, 2026-10-19): 48 of the impassable ground's ids went to Concordia (the new moon), the
# map keeps this many; free_province_ids.py then hands the unused ids on
KEEP_IDS = 153
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Nightsister Lair", "lair", CAPITAL, 2, [("ell", -0.3, -0.08, 0.13, 0.1, 15)]),
    ("Nightbrother Village", "village", 811, 2, [("ell", 0.42, -0.42, 0.12, 0.09, -20)]),
    ("Nightbrother Arena", "arena", 811, 1, [("ell", 0.62, -0.55, 0.08, 0.07, 0)]),
    ("Singing Mountain", "fortress", 812, 2, [("ell", -0.5, 0.48, 0.13, 0.1, 0)]),
    ("Nardithi Cluster", "cluster", 813, 2, [("ell", 0.5, 0.45, 0.12, 0.09, 30)]),
    ("Blue Desert City", "desert", 817, 1, [("ell", -0.78, 0.0, 0.08, 0.07, 0)]),
    ("Dreaming River", "river", 814, 3, [("cap", -0.15, 0.2, 0.0, 0.55, 0.04), ("cap", 0.0, 0.55, 0.12, 0.95, 0.04)]),
    ("Great Canyon", "canyon", 1219, 0, [("cap", 0.22, -0.98, 0.14, -0.5, 0.15), ("cap", 0.14, -0.5, 0.06, -0.16, 0.13),
                                          ("cap", 0.14, -0.6, -0.06, -0.7, 0.09)]),
    ("Tar Lakes", "tar", 1220, 0, [("ell", 0.3, 0.12, 0.3, 0.17, 25), ("ell", 0.12, 0.32, 0.14, 0.11, 0),
                                   ("cap", 0.5, 0.2, 0.76, 0.26, 0.08)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((-0.25, 0.0), "swamp"), 811: ((0.45, -0.5), "rocks"), 812: ((-0.5, 0.55), "forest"),
         813: ((0.55, 0.5), "jungle"), 814: ((0.0, 0.7), "forest"), 815: ((0.78, -0.05), "hills"),
         816: ((-0.45, -0.62), "rocks"), 817: ((-0.82, 0.05), "desert")}
STATE_NAMES = {CAPITAL: "The Haunted Lands", 811: "Nightbrother Lands", 812: "Singing Mountain", 813: "Nardithi Cluster",
               814: "Dreaming River", 815: "Red Hills", 816: "Rift Valley", 817: "Blue Desert", 1219: "Great Canyon",
               1220: "Tar Lakes"}
IMPASSABLE = {1219, 1220}
VPS = [(CAPITAL, "Nightsister Lair", CAPITAL_VP, 10), (811, "Nightbrother Village", "Nightbrother Village", 3),
       (811, "Nightbrother Arena", "Nightbrother Arena", 1), (812, "Singing Mountain", "Singing Mountain", 3),
       (813, "Nardithi Cluster", "Nardithi Cluster", 2), (814, "Dreaming River", "Misty Falls", 1),
       (815, "hills", "Red Hills", 1), (816, "rocks", "Rift Valley", 1), (817, "Blue Desert City", "Blue Desert City", 2)]

# terrain (planet_terrain_gen.py --planet Dathomir). Heights in heightmap steps above the base. The lair's mountain,
# swamps and gnarled forests (flora_props 145, 146), rock spires (147) over the Nightbrother lands and the Rift Valley,
# a few witch-clan villages (map/cities.txt 43, military_buildings.py dat_hamlet), the canyon floor, the tar lakes
TERRAIN_CFG = dict(
    seed=95, base=4, rough=2, open=(6, 7, 8, 9, 10, 14),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("ramp_top", 14, 7, 5), tex=["ROCK", ("ROCK2", ">", 0.5), (13, ">", 0.86)], props=[(147, 0.08)]),   # the lair
        2: dict(relief=("rolling", 7, 3, 5), tex=["ROCK2", ("BROWN", ">", 0.6), (13, ">", 0.84)], props=[(147, 0.12)]),    # village
        3: dict(relief=("flat", 6), tex="ROCK2"),                                                  # the arena
        4: dict(relief=("ramp_top", 16, 8, 5), tex=["GREENMTN", ("ROCK", ">", 0.5), (13, ">", 0.86)], props=[(145, 0.1)]),   # mountain
        5: dict(relief=("rolling", 5, 2, 5), tex=["JUNGLE", ("ROCK2", ">", 0.6)], props=[(145, 0.2), (146, 0.2)]),
        6: dict(relief=("rolling", 2, 1.5, 6), tex=["JUNGLE2", ("WATER", ">", 0.72)],
                props=[(146, 0.35), (145, 0.18)], clusters=[(6, 0.6, [(145, 0.6)])]),             # swamps
        7: dict(relief=("rolling", 6, 5, 5), tex=["DFOREST", ("GRASSHILL", ">", 0.68)],
                props=[(145, 0.5), (146, 0.1)]),                                                   # forests
        8: dict(relief=("spires", 6, 3, 0.05, (1.5, 2.6), (10, 24)), tex=["ROCK2", ("BROWN", ">", 0.55)],
                props=[(147, 0.18)]),                                                              # rock spires
        9: dict(relief=("rolling", 8, 6, 4), tex=["BROWN", ("ROCK2", ">", 0.6)], props=[(147, 0.05), (145, 0.05)]),
        10: dict(relief=("rolling", 4, 2, 6), tex=["SAND", ("DUNES", ">", 0.55), (13, ">", 0.86)], props=[(147, 0.03)]),   # Blue Desert
        11: dict(relief=("flat", 0.3), tex="WATER"),                                               # the river
        12: dict(relief=("flat", 0.6), tex=["ROCK2", ("BROWN", ">", 0.6)], props=[(147, 0.1)]),   # the canyon floor
        13: dict(relief=("flat", 0.3), tex="WATER"),                                               # the tar lakes
        14: dict(relief=("rolling", 4, 3, 5), tex=["JUNGLE", ("JUNGLE2", ">", 0.6)],
                 props=[(145, 0.45), (146, 0.3)]),                                                 # jungle
    },
    steep=("ROCK", 6, (2, 7, 8, 9, 14)),
    city={1: 43, 2: 43, 4: 43, 10: 43},   # map/cities.txt 43: Dathomir's clan villages (dat_hamlet)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.36, 0.26, 0.25), 2: (0.42, 0.28, 0.25), 3: (0.44, 0.3, 0.26), 4: (0.3, 0.26, 0.22),
            5: (0.26, 0.2, 0.17), 6: (0.3, 0.2, 0.18), 7: (0.32, 0.15, 0.13), 8: (0.42, 0.3, 0.28),
            9: (0.55, 0.24, 0.19), 10: (0.42, 0.44, 0.52), 11: (0.2, 0.12, 0.14), 12: (0.3, 0.2, 0.2),
            13: (0.12, 0.08, 0.09), 14: (0.24, 0.18, 0.14)},
)

# models (military_buildings.py place Dathomir): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_dat_lair", "hod_dat_village", "hod_dat_arena", "hod_dat_singing", "hod_dat_nardithi"},
    items=[("hod_dat_lair", 1.0, ("at_vp", CAPITAL_VP)), ("hod_dat_village", 1.0, ("at_vp", "Nightbrother Village")),
           ("hod_dat_arena", 0.9, ("at_vp", "Nightbrother Arena")), ("hod_dat_singing", 1.0, ("at_vp", "Singing Mountain")),
           ("hod_dat_nardithi", 1.0, ("at_vp", "Nardithi Cluster"))],
    clear={"hod_dat_lair": 5.5, "hod_dat_village": 5.0, "hod_dat_arena": 3.5, "hod_dat_singing": 5.0,
           "hod_dat_nardithi": 5.0},
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
    ids = sorted(np.unique(pid[m]).tolist())[:KEEP_IDS]   # the rest are left without pixels: free_province_ids.py
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (dathomir_map.py)\n{imp}"
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
