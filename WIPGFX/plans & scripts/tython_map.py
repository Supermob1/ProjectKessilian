"""Tython, the forgotten cradle of the Je'daii, as one battlefield before the Clone Wars (research: WIPGFX/research/tython/;
the user, 2026-10-21: abandoned, ruins only: no towns, no city models). CANON: forests, grasslands and mountains,
incredibly rich in the Force; a temperate region and the Meridional Ice Cap; the Jedi Temple; the Force-henge, an ancient
temple on top of a mountain with its seeing stone; the Tython Rift, a canyon; Ak trees. LEGENDS: continents separated by
oceans and seas, Thyr and Kato Zakar to its south (the Firelands, volcanic heartlands); Ban Landing at the mouth of the
Moon Channel; the nine Je'daii temple-cities round the Tho Yor; the Masters' Retreat on a rocky outcrop in a lake in the
Tythonian Gnarls; Belia Darzu's black durasteel fortress; Kalikori village; the Silent Desert, the Stark Forests, the
rolling grasslands of the Tansa Reach, the Rift and the Riftlands. By 990 BBY its hyperlanes were forgotten and the
planet storm-bound: nobody lives here in 976. Owner: REP (as before).
LAYOUT IS A DESIGN CHOICE beyond the stated relationships: Thyr in the north with the ruined Jedi Temple in the middle and
the Force-henge on its mountain, the Tythonian Gnarls north-east with the Masters' Retreat on its lake, the Stark Forests
along the north coast with Belia Darzu's fortress (the Coruscant lane), the Tansa Reach west with Kalikori village; the
Moon Channel (impassable) from the west coast and the Rift (impassable) from the east cut Thyr from Kato Zakar, meeting
at the ruins of Ban Landing, the one crossing; Kato Zakar south with the Silent Desert and a Je'daii temple ruin round a
Tho Yor, the Meridional Ice Cap (impassable) along the southern rim, the Thyr Highlands (impassable) north of the temple.
Names from the sources: every state and VP name except the invented Thyr Highlands and Kato Zakar's Firelands Shore.
    python "WIPGFX/plans & scripts/tython_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/tython_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 64 province ids are kept (strategic region unchanged); only the pixels move.
Run order: tython_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (tyt_*) ->
planet_terrain_gen.py --planet Tython -> military_buildings.py tython_atlas, models hod_tyt_ -> military_buildings.py place
Tython -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Tython"
ZONES_JSON = "WIPGFX/Assets/tython_zones.json"
ZONES_PNG = "WIPGFX/Assets/tython_zones.png"
KIND = {"temple": 1, "henge": 2, "retreat": 3, "fortress": 4, "ruins": 5, "port": 6, "thoyor": 7, "forest": 8,
        "grass": 9, "hills": 10, "desert": 11, "fire": 12, "ice": 13, "sea": 14, "rift": 15, "peaks": 16}
TERRAIN = {"temple": "hills", "henge": "mountain", "retreat": "hills", "fortress": "forest", "ruins": "plains",
           "port": "plains", "thoyor": "hills", "forest": "forest", "grass": "plains", "hills": "hills", "desert": "desert",
           "fire": "hills", "ice": "mountain", "sea": "mountain", "rift": "mountain", "peaks": "mountain"}
SEED = 8
CAPITAL = 8
CAPITAL_VP = "Jedi Temple Ruins"
CORE = "REP"
PORT_STATE = 208                     # the old landing grounds on the Stark Forests' coast (the channel is no sea)
OWNER = {s: "REP" for s in (8, 207, 208, 209, 210, 211, 1324, 1325, 1326, 1327)}
WARP = (0.12, 9)
TARGET_PASSABLE = 42                 # user rule: passable provinces outnumber impassable (~42 / 22)
STRAIGHT = set()
FEATURES = [
    ("Jedi Temple Ruins", "temple", CAPITAL, 2, [("ell", -0.05, -0.12, 0.14, 0.1, 0)]),
    ("Force-henge", "henge", CAPITAL, 1, [("ell", 0.22, -0.3, 0.08, 0.07, 0)]),
    ("Masters' Retreat", "retreat", 210, 1, [("ell", 0.5, -0.42, 0.08, 0.07, 0)]),
    ("Gnarls Lake", "sea", 1327, 0, [("ell", 0.5, -0.3, 0.13, 0.06, 15)]),
    ("Belia Darzu's Fortress", "fortress", 208, 1, [("ell", -0.12, -0.72, 0.08, 0.07, 0)]),
    ("Kalikori Village", "ruins", 207, 1, [("ell", -0.62, -0.2, 0.08, 0.07, 0)]),
    ("Ban Landing", "port", 209, 3, [("ell", 0.0, 0.27, 0.17, 0.12, 0)]),
    ("Je'daii Temple Ruins", "thoyor", 211, 1, [("ell", 0.3, 0.6, 0.09, 0.08, 0)]),
    ("Silent Desert", "desert", 211, 0, [("ell", -0.38, 0.6, 0.22, 0.13, 20)]),
    ("Moon Channel", "sea", 1325, 0, [("cap", -1.0, 0.12, -0.5, 0.24, 0.07), ("cap", -0.5, 0.24, -0.15, 0.27, 0.065)]),
    ("The Rift", "rift", 1326, 0, [("cap", 0.15, 0.27, 0.55, 0.33, 0.06), ("cap", 0.55, 0.33, 1.0, 0.18, 0.055)]),
    ("Meridional Ice Cap", "ice", 1324, 0, [("ell", 0.0, 0.98, 0.75, 0.16, 0)]),
    ("Thyr Highlands", "peaks", 1328, 0, [("cap", -0.45, -0.42, 0.05, -0.38, 0.09), ("cap", 0.05, -0.38, 0.12, -0.55, 0.07)]),
]
SEEDS = {CAPITAL: ((0.0, -0.1), "hills"), 207: ((-0.6, -0.15), "grass"), 208: ((-0.1, -0.75), "forest"),
         210: ((0.55, -0.4), "forest"), 211: ((0.05, 0.62), "fire")}
STATE_NAMES = {CAPITAL: "Thyr", 207: "Tansa Reach", 208: "Stark Forests", 209: "Ban Landing", 210: "Tythonian Gnarls",
               211: "Kato Zakar", 1324: "Meridional Ice Cap", 1325: "Moon Channel", 1326: "The Rift", 1327: "Gnarls Lake",
               1328: "Thyr Highlands"}
IMPASSABLE = {1324, 1325, 1326, 1327, 1328}
OWNER.update({1328: "REP"})
VPS = [(CAPITAL, "Jedi Temple Ruins", CAPITAL_VP, 10), (CAPITAL, "Force-henge", "Force-henge", 3),
       (210, "Masters' Retreat", "Masters' Retreat", 3), (208, "Belia Darzu's Fortress", "Belia Darzu's Fortress", 3),
       (207, "Kalikori Village", "Kalikori Village", 1), (209, "Ban Landing", "Ban Landing", 3),
       (211, "Je'daii Temple Ruins", "Je'daii Temple Ruins", 3), (211, "Silent Desert", "Silent Desert", 1),
       (207, "grass", "Tansa Reach", 1), (211, "fire", "Firelands Shore", 1)]

TERRAIN_CFG = dict(
    seed=8, base=4, rough=2, open=(8, 9, 10, 11, 12),
    zones={
        1: dict(relief=("ramp_top", 14, 8, 3), tex=["GRASSHILL", ("ROCK2", ">", 0.55)], props=[(233, 0.3), (232, 0.15)]),
        2: dict(relief=("ramp_top", 30, 12, 3), tex=["ROCK", ("GRASSHILL", ">", 0.6)]),               # the henge's mountain
        3: dict(relief=("mesa", 4, 12, 2, (5, 0.6)), tex=["ROCK2", ("GRASSHILL", ">", 0.5)], props=[(232, 0.2)]),
        4: dict(relief=("flat", 6), tex=["DFOREST", ("ROCK2", ">", 0.6)], props=[(232, 0.3)]),        # Darzu's fortress
        5: dict(relief=("flat", 5), tex=["GRASS", ("BROWN", ">", 0.6)], props=[(233, 0.3), (234, 0.3)]),   # Kalikori
        6: dict(relief=("flat", 4), tex=["GRASS", ("ROCK2", ">", 0.55)], props=[(233, 0.35), (234, 0.2)]),  # Ban Landing
        7: dict(relief=("ramp_top", 12, 6, 3), tex=["BROWN", ("ROCK2", ">", 0.5)], props=[(233, 0.25)]),   # the Je'daii temple
        8: dict(relief=("rolling", 6, 4, 6), tex=["FOREST", ("DFOREST", ">", 0.5)], props=[(232, 0.7), (234, 0.1)]),
        9: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("SAVANNA", ">", 0.6)], props=[(234, 0.45), (232, 0.08)]),
        10: dict(relief=("rolling", 10, 7, 5), tex=["GRASSHILL", ("ROCK2", ">", 0.7)], props=[(232, 0.3), (233, 0.08)]),
        11: dict(relief=("rolling", 4, 4, 6), tex=["SAND", ("DUNES", ">", 0.5)]),                     # the Silent Desert
        12: dict(relief=("rolling", 8, 8, 4), tex=["BROWN", ("ROCK", ">", 0.55), ("LAVA", ">", 0.94)], props=[(233, 0.05)]),
        13: dict(relief=("spires", 14, 8, 0.08, (1.5, 3.0), (20, 40)), tex=["SNOWROCK", ("SNOWSAND", ">", 0.5)]),
        14: dict(relief=("flat", 0.3), tex="WATER"),
        15: dict(relief=("flat", 0.2), tex=["ROCK", ("BROWNMTN", ">", 0.5)]),                          # the Rift's depths
        16: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["ROCK", ("GREENMTN", ">", 0.5), ("SNOWROCK", ">", 0.9)]),
    },
    steep=("ROCK", 6, (8, 9, 10, 11, 12)),
    city={},                          # abandoned (the user, 2026-10-21): no towns
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.42, 0.62, 0.6), 2: (0.55, 0.55, 0.62), 3: (0.4, 0.6, 0.62), 4: (0.2, 0.35, 0.5), 5: (0.45, 0.66, 0.62), 6: (0.45, 0.6, 0.62), 7: (0.55, 0.45, 0.6), 8: (0.18, 0.38, 0.5), 9: (0.42, 0.7, 0.62), 10: (0.38, 0.5, 0.58), 11: (0.78, 0.7, 0.85), 12: (0.45, 0.28, 0.4), 13: (0.9, 0.92, 0.98), 14: (0.15, 0.25, 0.58), 15: (0.2, 0.16, 0.28), 16: (0.48, 0.48, 0.6)},   # signature far look, set by hand (Tython: mystic teal-blue, Loronar: cyan-teal)
)

PLACEMENT = dict(
    new_models={"hod_tyt_temple", "hod_tyt_henge", "hod_tyt_retreat", "hod_tyt_banlanding", "hod_tyt_thoyor"},
    items=[("hod_tyt_temple", 1.0, ("at_vp", "Jedi Temple Ruins")), ("hod_tyt_henge", 0.9, ("at_vp", "Force-henge")),
           ("hod_tyt_retreat", 0.9, ("at_vp", "Masters' Retreat")),
           ("hod_tyt_banlanding", 0.9, ("at_vp", "Ban Landing")), ("hod_tyt_thoyor", 1.0, ("at_vp", "Je'daii Temple Ruins"))],
    clear={"hod_tyt_temple": 6.0, "hod_tyt_henge": 3.0, "hod_tyt_retreat": 3.5, "hod_tyt_banlanding": 4.5,
           "hod_tyt_thoyor": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (tython_map.py)\n{imp}"
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
