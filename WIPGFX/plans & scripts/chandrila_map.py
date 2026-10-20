"""Chandrila, the calm blue-green Core world, as one battlefield before the Clone Wars (research:
WIPGFX/research/chandrila/; Legends first, canon where Legends is silent; the user, 2026-10-20). LEGENDS: two main
continents, Ananta and an eastern one, under grassy rolling plains, forests, hills and gentle seas; Hanna City the
capital between the Silver Sea and Lake Sah'ot; the Jhanjaari River runs from Lake Sah'ot along Hanna's southern edge
to the Silver Sea and rises in the Shashwaat Mountains; the Hanna Wild Game Reserve (tintolive and sienta forest) lies
across the river; Emita (a small city with one of the three spaceports and the only industry) and Nayli (a spaceport
city); Salline; the Crystal Canyons; the Brionelle Memorial Military Academy that trains the Defense Fleet's officers;
the Gladean State Parks. CANON: Junari Point, a seaside spot a few klicks outside Hanna City; the Mothma Estate. Loyal
to the Republic in the Clone Wars. Owner: REP (as before).
LAYOUT IS A DESIGN CHOICE beyond the stated relationships above: the Silver Sea reaches up from the south between
Ananta (west) and the eastern continent, which meet across the north; Hanna City at the sea's head with Junari Point on
the shore, Lake Sah'ot and the Shashwaat Mountains north-west of it, the Game Reserve south of it on the west shore,
Nayli and the Mothma Estate on western Ananta, the Gladean State Parks south-west, the Brionelle Academy in the north,
Salline north-east, Emita on the eastern coast, the Crystal Canyons south-east.
Names from the sources: every state, VP and feature name here. Invented: none (the Shashwaat Mountains and Lake Sah'ot
are one impassable state).
    python "WIPGFX/plans & scripts/chandrila_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/chandrila_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 201 province ids are kept (strategic region unchanged); only the pixels move.
Run order: chandrila_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (cha_*) ->
planet_terrain_gen.py --planet Chandrila -> military_buildings.py models hod_cha -> coruscant_buildings.py wire ->
military_buildings.py place Chandrila -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Chandrila"
ZONES_JSON = "WIPGFX/Assets/chandrila_zones.json"
ZONES_PNG = "WIPGFX/Assets/chandrila_zones.png"
KIND = {"city": 1, "spaceport": 2, "academy": 3, "canyons": 4, "forest": 5, "plains": 6, "hills": 7, "estate": 8,
        "sea": 9, "mountains": 10, "lake": 11}
TERRAIN = {"city": "urban", "spaceport": "urban", "academy": "plains", "canyons": "hills", "forest": "forest",
           "plains": "plains", "hills": "hills", "estate": "plains", "sea": "mountain", "mountains": "mountain",
           "lake": "mountain"}
SEED = 187
CAPITAL = 187
CAPITAL_VP = "Hanna City"
CORE = "REP"
PORT_STATE = 1002                    # Emita's spaceport on the eastern coast
OWNER = {s: "REP" for s in (187, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1297, 1298)}
WARP = (0.12, 9)
TARGET_PASSABLE = 134                # user rule: passable provinces outnumber impassable (~134 / 67)
STRAIGHT = set()
FEATURES = [
    ("Hanna City", "city", CAPITAL, 5, [("ell", -0.12, -0.12, 0.13, 0.1, -20)]),
    ("Junari Point", "city", CAPITAL, 1, [("ell", 0.12, -0.17, 0.08, 0.06, 0)]),
    ("Emita", "spaceport", 1002, 3, [("ell", 0.72, 0.12, 0.1, 0.08, 10)]),
    ("Nayli", "spaceport", 1003, 2, [("ell", -0.78, 0.02, 0.11, 0.1, 0)]),
    ("Salline", "city", 1005, 2, [("ell", 0.52, -0.5, 0.08, 0.06, 0)]),
    ("Brionelle Memorial Military Academy", "academy", 1007, 2, [("ell", 0.12, -0.72, 0.13, 0.09, 0)]),
    ("Crystal Canyons", "canyons", 1006, 2, [("ell", 0.48, 0.62, 0.11, 0.07, 40)]),
    ("Hanna Wild Game Reserve", "forest", 1004, 3, [("ell", -0.32, 0.22, 0.16, 0.12, 15)]),
    ("Mothma Estate", "estate", 1003, 1, [("ell", -0.62, 0.28, 0.08, 0.07, 0)]),
    ("Gladean State Parks", "forest", 1008, 3, [("ell", -0.45, 0.66, 0.16, 0.11, -30)]),
    ("Silver Sea", "sea", 1297, 0, [("ell", 0.08, 0.5, 0.2, 0.42, 4), ("cap", 0.08, 0.15, 0.02, -0.02, 0.11),
                                    ("ell", 0.06, 0.92, 0.3, 0.12, 0)]),
    ("Lake Sah'ot", "lake", 1298, 0, [("ell", -0.34, -0.33, 0.1, 0.07, -30)]),
    ("Shashwaat Mountains", "mountains", 1298, 0, [("ell", -0.56, -0.56, 0.26, 0.15, -40), ("cap", -0.44, -0.4, -0.7, -0.68, 0.08)]),
]
SEEDS = {CAPITAL: ((-0.05, -0.35), "plains"), 1002: ((0.72, 0.2), "plains"), 1003: ((-0.78, 0.05), "hills"),
         1004: ((-0.3, 0.3), "plains"), 1005: ((0.5, -0.45), "hills"), 1006: ((0.45, 0.68), "hills"),
         1007: ((0.12, -0.82), "plains"), 1008: ((-0.5, 0.65), "hills")}
STATE_NAMES = {CAPITAL: "Hanna City", 1002: "Emita", 1003: "Nayli", 1004: "Hanna Wild Game Reserve", 1005: "Salline",
               1006: "Crystal Canyons", 1007: "Brionelle", 1008: "Gladean State Parks", 1297: "Silver Sea",
               1298: "Shashwaat Mountains"}
IMPASSABLE = {1297, 1298}
VPS = [(CAPITAL, "Hanna City", CAPITAL_VP, 15), (CAPITAL, "Junari Point", "Junari Point", 2), (1002, "Emita", "Emita", 5),
       (1003, "Nayli", "Nayli", 5), (1003, "Mothma Estate", "Mothma Estate", 2), (1005, "Salline", "Salline", 3),
       (1007, "Brionelle Memorial Military Academy", "Brionelle Memorial Military Academy", 3),
       (1006, "Crystal Canyons", "Crystal Canyons", 2), (1004, "Hanna Wild Game Reserve", "Hanna Wild Game Reserve", 1),
       (1008, "Gladean State Parks", "Gladean State Parks", 1)]

def canyon(ctx):
    """the Crystal Canyons (the user, 2026-10-20: inside a real canyon, not standing on the plain): a rock plateau
    round the VP with a narrow trench cut west-east through it, the model's floor (cha_canyons) at the bottom"""
    rel, z, sub, yy, xx = ctx["rel"], ctx["z"].copy(), ctx["sub"], ctx["yy"], ctx["xx"]
    zj = ctx["zj"]
    p = next(q for q, n in zj["vp_names"].items() if n == "Crystal Canyons")
    r0, c0 = zj["provinces"][p]["centre"]
    r0, c0 = r0 - ctx["sl"][0].start, c0 - ctx["sl"][1].start
    d = np.hypot(yy - r0, xx - c0)
    ground = sub & np.isin(z, (4, 7))                                          # the canyon and the hills round it
    plat = np.clip((12.0 - d) / 5.0, 0, 1)
    plat = plat * plat * (3 - 2 * plat)
    rel = np.where(ground, np.maximum(rel, 30.0 * plat + rel * (1 - plat)), rel)
    along = np.clip((10.0 - np.abs(xx - c0)) / 3.0, 0, 1)                      # the trench, tapering at both ends
    wall = np.clip((np.abs(yy - r0) - 1.6) / 1.4, 0, 1)
    cut = ground & (along > 0) & (wall < 1)
    rel = np.where(cut, rel * wall - 4.0 * (1 - wall) * along + rel * (1 - along) * (1 - wall), rel)
    z[cut | (ground & (plat > 0.5))] = 4
    ctx["rel"], ctx["z"] = rel, z


TERRAIN_CFG = dict(
    hook=canyon,
    seed=187, base=4, rough=2, open=(5, 6, 7),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("GRASS", ">", 0.6)]),                              # Hanna, Salline
        2: dict(relief=("flat", 5), tex=["URBAN", ("FARM", ">", 0.6)]),                               # the spaceports
        3: dict(relief=("flat", 5), tex=["GRASS", ("FARM", ">", 0.6)]),                               # the Academy
        4: dict(relief=("mesa", 2, 10, 3, (6, 0.6)), tex=["ROCK2", ("ROCK", ">", 0.55)], props=[(216, 0.05)]),   # canyons
        5: dict(relief=("rolling", 5, 3, 6), tex=["FOREST", ("GRASS", ">", 0.7), (13, ">", 0.95)],
                props=[(216, 0.75), (217, 0.15)]),                                                    # the forests
        6: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("FARM", ">", 0.6), (13, ">", 0.92)],
                props=[(217, 0.3), (216, 0.06)]),                                                     # rolling plains
        7: dict(relief=("rolling", 9, 5, 5), tex=["GRASSHILL", ("GRASS", ">", 0.6), (13, ">", 0.94)],
                props=[(217, 0.2), (216, 0.15)]),                                                     # the hills
        8: dict(relief=("flat", 5), tex=["GRASS", ("FARM", ">", 0.5)], props=[(216, 0.1)]),          # the Mothma Estate
        9: dict(relief=("flat", 0.3), tex="WATER"),                                                   # the Silver Sea
        10: dict(relief=("spires", 16, 9, 0.08, (1.5, 3.0), (24, 46)), tex=["GREENMTN", ("ROCK", ">", 0.6)]),
        11: dict(relief=("flat", 0.3), tex="WATER"),                                                  # Lake Sah'ot
    },
    steep=("ROCK", 6, (5, 6, 7)),
    city={1: 76, 2: 76, 5: 76, 6: 76, 7: 76},   # map/cities.txt 76: Chandrilan towns (cha_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.6, 0.6, 0.54), 2: (0.56, 0.56, 0.5), 3: (0.42, 0.52, 0.3), 4: (0.5, 0.46, 0.44), 5: (0.24, 0.4, 0.2),
            6: (0.36, 0.52, 0.26), 7: (0.34, 0.46, 0.26), 8: (0.4, 0.54, 0.3), 9: (0.14, 0.32, 0.4), 10: (0.32, 0.36, 0.3),
            11: (0.14, 0.3, 0.38)},
)

PLACEMENT = dict(
    new_models={"hod_cha_hanna", "hod_cha_emita", "hod_cha_nayli", "hod_cha_brionelle", "hod_cha_canyons"},
    items=[("hod_cha_hanna", 1.0, ("at_vp", CAPITAL_VP)), ("hod_cha_emita", 1.0, ("at_vp", "Emita")),
           ("hod_cha_nayli", 0.9, ("at_vp", "Nayli")), ("hod_cha_brionelle", 1.0, ("at_vp", "Brionelle Memorial Military Academy")),
           ("hod_cha_canyons", 1.0, ("at_vp", "Crystal Canyons"))],
    clear={"hod_cha_hanna": 7.0, "hod_cha_emita": 6.0, "hod_cha_nayli": 5.0, "hod_cha_brionelle": 5.0, "hod_cha_canyons": 5.0},
    no_pad={"hod_cha_canyons"},                      # it stands in the canyon the terrain hook cuts
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (chandrila_map.py)\n{imp}"
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
