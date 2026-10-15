"""Ruuria, homeworld of the Ruurians in the Xappyh sector, as one battlefield in the Clone Wars (research:
WIPGFX/research/ruuria/). Canon and Legends agree where both speak: CANON: pink rivers; the University of Ruuria.
LEGENDS: a warm and humid jungle world; the caterpillar-like Ruurians' society "made up of 143 colonies, and every
Ruurian belonged to a single colony for life"; the University of Ruuria (its historian S. Kiprian... in the sources).
Owner: the CSA (as before; the sources give no Clone Wars owner).
LAYOUT IS A DESIGN CHOICE: jungle over most of the planet, the Chrysalis Mountains across the north, two pink rivers
rising well south of them (fords round their springs) and winding out to the planet's rim (the Great Pink River east through a delta, the Western
Pink River west), the University of Ruuria on the Great River's west bank with the First Colony's great hive beside
it, a colony in every other region. The rivers start inland so they never cut the planet in two.
Invented names: every state name, the rivers' names, the Chrysalis Mountains, the First Colony and the numbered
colonies (the 143 colonies are Legends; their names and numbers are not in the sources).
    python "WIPGFX/plans & scripts/ruuria_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ruuria_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 196 province ids are kept (strategic region unchanged); only the pixels move.
Run order: ruuria_map.py -> planet_terrain_gen.py --planet Ruuria -> military_buildings.py models hod_ruu
-> military_buildings.py place Ruuria -> ruuria_fx.py -> planet_terrain_gen.py --globe-texture.
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

PLANET = "Ruuria"
ZONES_JSON = "WIPGFX/Assets/ruuria_zones.json"
ZONES_PNG = "WIPGFX/Assets/ruuria_zones.png"
KIND = {"jungle": 1, "hills": 2, "university": 3, "colony": 4, "river": 5, "range": 6, "delta": 7}
TERRAIN = {"jungle": "jungle", "hills": "hills", "university": "urban", "colony": "urban", "river": "marsh",
           "range": "mountain", "delta": "marsh"}
SEED = 88
CAPITAL = 88
CAPITAL_VP = "University of Ruuria"
PORT_STATE = 766
OWNER = "CSA"
WARP = (0.12, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 140                # user rule: passable provinces outnumber impassable
STRAIGHT = {"colony"}               # drawn unwarped: small hives would tear apart
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("University of Ruuria", "university", CAPITAL, 4, [("ell", -0.08, 0.05, 0.14, 0.13, 10)]),
    ("First Colony", "colony", CAPITAL, 3, [("ell", -0.05, 0.33, 0.11, 0.1, -15)]),
    ("Colony 17", "colony", 767, 1, [("ell", -0.72, -0.18, 0.085, 0.085, 0)]),
    ("Colony 42", "colony", 768, 1, [("ell", 0.05, -0.86, 0.085, 0.07, 0)]),
    ("Colony 88", "colony", 769, 1, [("ell", -0.22, 0.74, 0.085, 0.085, 0)]),
    ("Colony 113", "colony", 770, 1, [("ell", 0.55, -0.32, 0.085, 0.085, 0)]),
    ("Colony 143", "colony", 771, 1, [("ell", 0.78, 0.05, 0.085, 0.085, 0)]),
    ("Delta Colony", "colony", PORT_STATE, 1, [("ell", 0.55, 0.78, 0.085, 0.075, 0)]),
    ("Chrysalis Mountains", "range", 1176, 0, [("cap", -0.58, -0.58, -0.15, -0.66, 0.12), ("cap", -0.15, -0.66, 0.45, -0.66, 0.13),
                                                ("ell", 0.22, -0.6, 0.1, 0.06, 30)]),
    # the pink rivers: chains of short reaches from a spring south of the mountains out to the rim
    ("Great Pink River", "river", 1174, 0, [("cap", 0.14, -0.28, 0.24, -0.12, 0.045), ("cap", 0.24, -0.12, 0.14, 0.12, 0.05),
                                            ("cap", 0.14, 0.12, 0.36, 0.42, 0.055), ("cap", 0.36, 0.42, 0.72, 0.56, 0.06),
                                            ("cap", 0.72, 0.56, 1.05, 0.62, 0.07)]),
    ("Western Pink River", "river", 1175, 0, [("cap", -0.36, -0.16, -0.52, 0.02, 0.04), ("cap", -0.52, 0.02, -0.47, 0.34, 0.045),
                                              ("cap", -0.47, 0.34, -0.78, 0.52, 0.05), ("cap", -0.78, 0.52, -1.05, 0.56, 0.055)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((-0.1, 0.12), "jungle"), PORT_STATE: ((0.62, 0.72), "delta"), 767: ((-0.72, -0.2), "jungle"),
         768: ((0.0, -0.86), "jungle"), 769: ((-0.25, 0.68), "jungle"), 770: ((0.5, -0.38), "hills"),
         771: ((0.78, 0.05), "jungle")}
STATE_NAMES = {CAPITAL: "University Reach", PORT_STATE: "Pinkwater Delta", 767: "Western Jungles",
               768: "Northern Jungles", 769: "Southern Jungles", 770: "Chrysalis Foothills", 771: "Eastern Jungles",
               1174: "Great Pink River", 1175: "Western Pink River", 1176: "Chrysalis Mountains"}
IMPASSABLE = {1174, 1175, 1176}
# victory points: (state, feature or kind, name, value). Canon + Legends: the University of Ruuria; invented: the
# colonies (Legends: 143 of them)
VPS = [(CAPITAL, "university", CAPITAL_VP, 10), (CAPITAL, "First Colony", "First Colony", 4),
       (767, "colony", "Colony 17", 2), (768, "colony", "Colony 42", 2), (769, "colony", "Colony 88", 2),
       (770, "colony", "Colony 113", 2), (771, "colony", "Colony 143", 2), (PORT_STATE, "colony", "Delta Colony", 2)]


# terrain (planet_terrain_gen.py --planet Ruuria; operators: planet_terrain_gen.zone_repaint). Heights in heightmap
# steps above the base. Humid jungle (Legends), the pink rivers (canon) as water at ground level tinted pink in the
# colormap (tint), a wet jungle delta, green mountains with tree ferns; the colonies and the university are urban
TERRAIN_CFG = dict(
    seed=88, base=4, rough=2, open=(1, 2, 7),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 4, 4, 5), tex=["JUNGLE", ("JUNGLE2", ">", 0.55), ("FOREST", "<", 0.2)],
                props=[(100, 0.55), (101, 0.15), (102, 0.05)], clusters=[(6, 0.5, [(100, 0.9)])]),
        2: dict(relief=("rolling", 7, 7, 4), tex=["GRASSHILL", ("JUNGLE", ">", 0.6), ("HILLS", "<", 0.2)],
                props=[(101, 0.2), (100, 0.15), (102, 0.08)]),
        3: dict(relief=("ramp_top", 7, 4, 5), tex="URBAN", props=[(100, 0.03)]),                # the university
        4: dict(relief=("ramp_top", 6, 4, 4), tex="URBAN", props=[(102, 0.06)]),                # colony hives
        5: dict(relief=("flat", 1), tex="WATER", props=[(103, 0.1)]),                           # the pink rivers
        6: dict(relief=("spires", 14, 8, 0.07, (1.5, 3.0), (20, 40)), tex=["GREENMTN", ("ROCK", ">", 0.6)],
                props=[(101, 0.08)]),
        7: dict(relief=("rolling", 2, 1, 6), tex=["JUNGLE2", ("WATER", ">", 0.55)],               # the wet delta
                props=[(103, 0.2), (101, 0.15), (100, 0.1)]),
    },
    steep=("ROCK2", 7, (1, 2, 6)),
    city={3: 22, 4: 22},   # map/cities.txt 22: Ruurian colony hives (military_buildings.py ruu_city)
    prop_clear=2.0,
    tint={5: ((0.88, 0.46, 0.62), 0.8), 7: ((0.72, 0.52, 0.56), 0.25)},   # canon: pink rivers
)
# models (military_buildings.py place Ruuria): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_ruu_university", "hod_ruu_great_hive"},
    items=[("hod_ruu_university", 1.0, ("at_vp", CAPITAL_VP)), ("hod_ruu_great_hive", 1.0, ("at_vp", "First Colony"))],
    clear={"hod_ruu_university": 5.8, "hod_ruu_great_hive": 5.2},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ruuria_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {OWNER}\n\t\tadd_core_of = {OWNER}\n\t}}\n"
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
