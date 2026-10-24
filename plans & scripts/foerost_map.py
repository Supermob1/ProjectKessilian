"""Foerost, the Techno Union's ancient shipyard world, as one battlefield before the Clone Wars (research:
WIPGFX/research/foerost/; the user, 2026-10-21: the Techno Union keeps it, the orbital yards with ships in their slips).
LEGENDS: renowned for its vast, ancient shipyards in high orbit; the city of Hajibar; the Foerost Siege, the two-year
blockade the Republic laid on the Techno Union's Foerost Shipyards in the Clone Wars. CANON: a communications tower.
The sources say nothing about the surface: everything below the yards is a design choice.
LAYOUT IS A DESIGN CHOICE: a temperate industrial world serving the yards; Hajibar in the middle, the Launch Fields
south-west lifting hulls and crews to orbit (the Fresia lane), the Hull Works south-east, where hull sections are fabricated and lifted to
the yards, the Refinery Coast east beyond the Foerost Mountains (impassable), the Western Foundries on the west
coast, the Foerost Wilds forests in the north under the polar ice (impassable), the Signal Heights north-east with the
communications tower, the Hajibar Sea (impassable) north-west; the Foerost Shipyards in orbit east of the disc.
Names from the sources: Hajibar, Foerost Shipyards, Foerost Communications Tower. Invented: every other state and VP.
    python "WIPGFX/plans & scripts/foerost_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/foerost_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 63 province ids are kept (strategic region unchanged); only the pixels move.
Run order: foerost_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (foe_*) ->
planet_terrain_gen.py --planet Foerost -> military_buildings.py foerost_atlas, models hod_foe_ -> coruscant_buildings.py
wire -> military_buildings.py place Foerost -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Foerost"
ZONES_JSON = "WIPGFX/Assets/foerost_zones.json"
ZONES_PNG = "WIPGFX/Assets/foerost_zones.png"
KIND = {"city": 1, "launch": 2, "slips": 3, "refinery": 4, "tower": 5, "foundry": 6, "plains": 7, "forest": 8,
        "hills": 9, "works": 10, "sea": 11, "mountains": 12, "ice": 13}
TERRAIN = {"city": "urban", "launch": "urban", "slips": "urban", "refinery": "urban", "tower": "hills", "foundry": "urban",
           "plains": "plains", "forest": "forest", "hills": "hills", "works": "plains", "sea": "mountain",
           "mountains": "mountain", "ice": "mountain"}
SEED = 10
CAPITAL = 10
CAPITAL_VP = "Hajibar"
CORE = "TCU"
PORT_STATE = 294                     # the Launch Fields
OWNER = {s: "TCU" for s in (10, 294, 295, 296, 297, 298, 299, 1332, 1333, 1334)}
WARP = (0.12, 9)
TARGET_PASSABLE = 41                 # user rule: passable provinces outnumber impassable (~41 / 22)
STRAIGHT = {"launch", "slips", "foundry"}
FEATURES = [
    ("Hajibar", "city", CAPITAL, 2, [("ell", -0.15, 0.02, 0.17, 0.12, 10)]),
    ("Hajibar Launch Fields", "launch", 294, 1, [("rect", -0.42, 0.58, 0.13, 0.1, 20)]),
    ("Hull Works", "slips", 295, 1, [("rect", 0.35, 0.5, 0.14, 0.08, -25)]),
    ("Refineries", "refinery", 297, 1, [("ell", 0.8, 0.05, 0.09, 0.08, 0)]),
    ("Foerost Communications Tower", "tower", 299, 1, [("ell", 0.45, -0.5, 0.08, 0.07, 0)]),
    ("Western Foundries", "foundry", 298, 1, [("rect", -0.78, 0.15, 0.1, 0.09, 0)]),
    ("Foerost Mountains", "mountains", 1332, 0, [("cap", 0.58, -0.28, 0.6, 0.2, 0.14), ("cap", 0.6, 0.2, 0.5, 0.36, 0.1),
                                                 ("cap", 0.58, -0.28, 0.75, -0.5, 0.1)]),
    ("Hajibar Sea", "sea", 1333, 0, [("ell", -0.5, -0.38, 0.36, 0.2, 30), ("cap", -0.72, -0.55, -0.98, -0.3, 0.14),
                                     ("cap", -0.35, -0.2, -0.45, 0.0, 0.08)]),
    ("Polar Ice", "ice", 1334, 0, [("ell", 0.15, -0.95, 0.7, 0.2, -5), ("cap", -0.3, -0.82, -0.1, -0.74, 0.07)]),
]
SEEDS = {CAPITAL: ((-0.15, 0.0), "works"), 294: ((-0.45, 0.6), "plains"), 295: ((0.3, 0.55), "works"),
         296: ((0.0, -0.6), "forest"), 297: ((0.8, 0.0), "works"), 298: ((-0.75, 0.15), "hills"), 299: ((0.45, -0.5), "hills")}
STATE_NAMES = {CAPITAL: "Hajibar", 294: "Launch Fields", 295: "Hull Works", 296: "Foerost Wilds", 297: "Refinery Coast",
               298: "Western Foundries", 299: "Signal Heights", 1332: "Foerost Mountains", 1333: "Hajibar Sea",
               1334: "Polar Ice"}
IMPASSABLE = {1332, 1333, 1334}
VPS = [(CAPITAL, "Hajibar", CAPITAL_VP, 10), (294, "Hajibar Launch Fields", "Hajibar Launch Fields", 5),
       (295, "Hull Works", "Hull Works", 3), (297, "Refineries", "Refineries", 3),
       (299, "Foerost Communications Tower", "Foerost Communications Tower", 2), (298, "Western Foundries", "Western Foundries", 3),
       (296, "forest", "Foerost Wilds", 1), (297, "works", "Refinery Coast", 1)]

TERRAIN_CFG = dict(
    seed=10, base=4, rough=2, open=(7, 8, 9, 10),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("BROWN", ">", 0.6)]),                              # Hajibar
        2: dict(relief=("flat", 4), tex=["URBAN", ("ROCK2", ">", 0.5)]),                              # the Launch Fields
        3: dict(relief=("flat", 3), tex=["URBAN", ("BROWN", ">", 0.5)], props=[(239, 0.1)]),          # the Hull Works
        4: dict(relief=("flat", 4), tex=["URBAN", ("BROWN", ">", 0.5)], props=[(239, 0.2)]),          # the refineries
        5: dict(relief=("ramp_top", 16, 8, 3), tex=["ROCK2", ("GRASSHILL", ">", 0.5)]),               # the tower's height
        6: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.6)], props=[(239, 0.1)]),          # the foundries
        7: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("FARM", ">", 0.55), (13, ">", 0.94)], props=[(238, 0.2)]),
        8: dict(relief=("rolling", 6, 4, 6), tex=["FOREST", ("DFOREST", ">", 0.5)], props=[(238, 0.65)]),
        9: dict(relief=("rolling", 10, 7, 5), tex=["GRASSHILL", ("ROCK2", ">", 0.6), (13, ">", 0.95)], props=[(238, 0.25)]),
        10: dict(relief=("rolling", 4, 3, 6), tex=["BROWN", ("GRASS", ">", 0.55), (13, ">", 0.9)], props=[(239, 0.25), (238, 0.1)]),
        11: dict(relief=("flat", 0.3), tex="WATER"),
        12: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["ROCK", ("BROWNMTN", ">", 0.5)]),
        13: dict(relief=("spires", 14, 8, 0.08, (1.5, 3.0), (20, 40)), tex=["SNOWROCK", ("SNOWSAND", ">", 0.5)]),
    },
    steep=("ROCK", 6, (7, 8, 9, 10)),
    city={1: 86, 2: 86, 3: 86, 4: 86, 6: 86, 7: 86, 10: 86},   # map/cities.txt 86: Foerost's Techno Union towns (foe_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.546, 0.476, 0.532), 2: (0.567, 0.529, 0.525), 3: (0.483, 0.419, 0.388), 4: (0.483, 0.379, 0.329), 5: (0.483, 0.427, 0.359), 6: (0.525, 0.458, 0.427), 7: (0.546, 0.469, 0.211), 8: (0.385, 0.399, 0.134), 9: (0.483, 0.404, 0.241), 10: (0.504, 0.375, 0.29), 11: (0.18, 0.25, 0.32), 12: (0.483, 0.389, 0.359), 13: (0.86, 0.88, 0.92)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)


def orbit(ctx):
    """the Foerost Shipyards (Legends: vast and ancient, in high orbit), floated east of the disc"""
    (cy, cx), R = ctx["z"]["centre"], ctx["z"]["radius"]
    ctx["put"]("hod_foe_yards", 1.0, cy, cx + R + 0.9 * R)
    ctx["put"]("hod_foe_oldyards", 1.0, cy + 1.1 * R, cx + R + 0.5 * R)          # the Old Yards, south of them


PLACEMENT = dict(
    new_models={"hod_foe_hajibar", "hod_foe_launch", "hod_foe_hullworks", "hod_foe_refinery", "hod_foe_tower", "hod_foe_foundry",
                "hod_foe_yards", "hod_foe_oldyards"},
    items=[("hod_foe_hajibar", 1.0, ("at_vp", "Hajibar")), ("hod_foe_launch", 1.0, ("at_vp", "Hajibar Launch Fields")),
           ("hod_foe_hullworks", 1.0, ("at_vp", "Hull Works")), ("hod_foe_refinery", 0.9, ("at_vp", "Refineries")),
           ("hod_foe_tower", 0.9, ("at_vp", "Foerost Communications Tower")),
           ("hod_foe_foundry", 0.9, ("at_vp", "Western Foundries"))],
    clear={"hod_foe_hajibar": 5.5, "hod_foe_launch": 4.5, "hod_foe_hullworks": 5.0, "hod_foe_refinery": 3.5, "hod_foe_tower": 3.0,
           "hod_foe_foundry": 3.5},
    hook=orbit,
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (foerost_map.py)\n{imp}"
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
