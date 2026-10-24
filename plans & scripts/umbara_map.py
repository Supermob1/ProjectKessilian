"""Umbara, the shadow world, as one battlefield before the Clone Wars (research: WIPGFX/research/umbara/). CANON: a
dark world of permanent dusk, plains with overgrown plant life and jungles, carnivorous and aggressive plants, much of
it bioluminescent (death's embrace, Zabrak spines); the Umbaran capital city; the Umbaran airbase and Sector Delta near
it, taken by the 501st in the Battle of Umbara (20 BBY). LEGENDS: the Void forest; the underground bunkers Grek, Krill
and Usk; the Sith Academy founded by the Brotherhood of Darkness at the end of the New Sith Wars.
Owner: UMB, the Umbaran tag (user, 2026-10-19; REP before). User (2026-10-19): landmarks the capital city, the airbase, the three bunkers, the Sith
Academy ruins.
LAYOUT IS A DESIGN CHOICE except Sector Delta beside the airbase: the capital in the middle, Sector Delta with the
airbase west, the Void Forest north, the three bunker regions east, south-east and south, the Sith Academy's barrens
south-west, the Thornwilds (impassable carnivorous jungle) in the north-east and the Umbaran Crags (impassable) in the
south-west.
Canon names: the Umbaran capital city, the Umbaran airbase, Sector Delta. Legends: the Void Forest, Bunkers Grek, Krill
and Usk, the Sith Academy. Invented: the capital's districts as a state name (Umbaran Capital), the Grek / Krill / Usk
regions, the Academy Barrens, the Glow Plains, the Thornwilds, the Umbaran Crags.
    python "WIPGFX/plans & scripts/umbara_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/umbara_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 200 province ids are kept (strategic region unchanged); only the pixels move.
Run order: umbara_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (umb_*) ->
planet_terrain_gen.py --planet Umbara -> military_buildings.py models hod_umb -> military_buildings.py place Umbara
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

PLANET = "Umbara"
ZONES_JSON = "WIPGFX/Assets/umbara_zones.json"
ZONES_PNG = "WIPGFX/Assets/umbara_zones.png"
KIND = {"capital": 1, "airbase": 2, "bunker": 3, "academy": 4, "plains": 5, "jungle": 6, "void": 7, "barrens": 8,
        "thorns": 9, "crags": 10}
TERRAIN = {"capital": "urban", "airbase": "urban", "bunker": "hills", "academy": "hills", "plains": "plains",
           "jungle": "jungle", "void": "forest", "barrens": "hills", "thorns": "mountain", "crags": "mountain"}
SEED = 120
CAPITAL = 120
CAPITAL_VP = "Umbaran Capital City"
PORT_STATE = 963                     # the capital lies inland: the fleet lies off the Usk plains
OWNER = {s: "UMB" for s in (120, 959, 960, 961, 962, 963, 964, 965, 1246, 1247)}   # the Umbaran tag (user, 2026-10-19)
WARP = (0.13, 9)
TARGET_PASSABLE = 134                # user rule: passable provinces outnumber impassable (~134 / 66)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Umbaran Capital City", "capital", CAPITAL, 4, [("ell", 0.0, 0.0, 0.22, 0.16, 0)]),
    ("Umbaran Airbase", "airbase", 959, 2, [("ell", -0.55, -0.05, 0.15, 0.11, 0)]),
    ("Bunker Grek", "bunker", 961, 1, [("ell", 0.62, -0.1, 0.1, 0.08, 0)]),
    ("Bunker Krill", "bunker", 962, 1, [("ell", 0.42, 0.55, 0.1, 0.08, 0)]),
    ("Bunker Usk", "bunker", 963, 1, [("ell", -0.05, 0.7, 0.1, 0.08, 0)]),
    ("Sith Academy", "academy", 964, 1, [("ell", -0.5, 0.45, 0.13, 0.1, 0)]),
    ("Thornwilds", "thorns", 1246, 0, [("ell", 0.45, -0.6, 0.38, 0.22, 35), ("cap", 0.15, -0.95, 0.75, -0.4, 0.12)]),
    ("Umbaran Crags", "crags", 1247, 0, [("ell", -0.62, 0.68, 0.3, 0.18, -40), ("cap", -0.92, 0.3, -0.5, 0.86, 0.1)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.0, 0.05), "plains"), 959: ((-0.6, -0.1), "plains"), 960: ((-0.2, -0.65), "void"),
         961: ((0.7, 0.0), "jungle"), 962: ((0.45, 0.55), "jungle"), 963: ((0.0, 0.75), "plains"),
         964: ((-0.5, 0.4), "barrens"), 965: ((0.25, -0.3), "jungle")}
STATE_NAMES = {CAPITAL: "Umbaran Capital", 959: "Sector Delta", 960: "Void Forest", 961: "Grek Jungles",
               962: "Krill Lowlands", 963: "Usk Plains", 964: "Academy Barrens", 965: "Glow Plains",
               1246: "Thornwilds", 1247: "Umbaran Crags"}
IMPASSABLE = {1246, 1247}
VPS = [(CAPITAL, "Umbaran Capital City", CAPITAL_VP, 10), (959, "Umbaran Airbase", "Umbaran Airbase", 3),
       (961, "Bunker Grek", "Bunker Grek", 2), (962, "Bunker Krill", "Bunker Krill", 2), (963, "Bunker Usk", "Bunker Usk", 2),
       (964, "Sith Academy", "Sith Academy", 2), (960, "void", "Void Forest", 1), (965, "jungle", "Glow Plains", 1)]

# terrain (planet_terrain_gen.py --planet Umbara). Heights in heightmap steps above the base. A dark world (the user,
# 2026-10-19: "always in the dark and everything is bioluminescent", "the forest much more dense like how felucia is"):
# every zone on Umbara's own ground (terrain.bmp 33, 34 where towns grow: atlas slot 20, which pdxmap.shader dims to
# dusk and lights with glowing specks); jungle as thick as Felucia's - Umbaran giants with glowing crowns (flora_props
# 173), dark trees (169), glowing Zabrak spines (167) and death's embrace (168) - the Umbaran towns (map/cities.txt 58,
# military_buildings.py umb_city), glowing spores drifting over it all (umbara_fx.py)
_JUNGLE = [(173, 0.3), (169, 0.3), (167, 0.2), (168, 0.15)]
TERRAIN_CFG = dict(
    seed=120, base=4, rough=2, open=(5, 6, 7, 8),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 5, 1.5, 6), tex=34),                                           # the capital
        2: dict(relief=("flat", 5), tex=34),                                                       # the airbase
        3: dict(relief=("ramp_top", 10, 5, 4), tex=33, props=[(167, 0.3), (169, 0.3), (168, 0.2)]),   # bunkers
        4: dict(relief=("ramp_top", 11, 6, 4), tex=33, props=[(167, 0.2), (168, 0.2)]),          # the academy
        5: dict(relief=("rolling", 4, 2, 6), tex=[33, (34, ">", 0.86)],
                props=[(167, 0.3), (168, 0.2), (169, 0.2), (173, 0.1)],
                clusters=[(6, 0.5, [(173, 0.45), (169, 0.4), (167, 0.1)])]),                     # glow plains
        6: dict(relief=("rolling", 6, 4, 5), tex=[33, (34, ">", 0.9)], props=_JUNGLE),           # dark jungle
        7: dict(relief=("rolling", 7, 5, 5), tex=[33, (34, ">", 0.92)],
                props=[(173, 0.45), (169, 0.35), (168, 0.15)]),                                   # the Void Forest
        8: dict(relief=("rolling", 7, 6, 4), tex=[33, (34, ">", 0.92)], props=[(167, 0.35), (168, 0.3)]),   # barrens
        9: dict(relief=("rolling", 9, 7, 3), tex=33, props=[(168, 0.35), (173, 0.3), (167, 0.2), (169, 0.1)]),
        10: dict(relief=("spires", 16, 9, 0.08, (1.5, 3.0), (24, 46)), tex=33, props=[(167, 0.3), (169, 0.2)]),
    },
    steep=(33, 6, (5, 6, 7, 8)),
    city={1: 58, 2: 58, 5: 58, 6: 58},   # map/cities.txt 58: the Umbaran towns (umb_city)
    prop_clear=1.2,
    shore_rise=(4, 2.0),
    colors={1: (0.16, 0.18, 0.24), 2: (0.17, 0.18, 0.22), 3: (0.12, 0.15, 0.16), 4: (0.14, 0.12, 0.15),
            5: (0.09, 0.15, 0.16), 6: (0.06, 0.12, 0.13), 7: (0.05, 0.09, 0.1), 8: (0.14, 0.12, 0.13),
            9: (0.06, 0.1, 0.12), 10: (0.12, 0.12, 0.14)},
)

# models (military_buildings.py place Umbara): big, custom (user rule 2026-10-14); one bunker model at the three bunkers
PLACEMENT = dict(
    new_models={"hod_umb_capital", "hod_umb_airbase", "hod_umb_bunker", "hod_umb_academy"},
    items=[("hod_umb_capital", 1.0, ("at_vp", CAPITAL_VP)), ("hod_umb_airbase", 1.0, ("at_vp", "Umbaran Airbase")),
           ("hod_umb_bunker", 0.9, ("at_vp", ["Bunker Grek", "Bunker Krill", "Bunker Usk"])),
           ("hod_umb_academy", 1.0, ("at_vp", "Sith Academy"))],
    clear={"hod_umb_capital": 6.0, "hod_umb_airbase": 5.0, "hod_umb_bunker": 3.5, "hod_umb_academy": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (umbara_map.py)\n{imp}"
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
