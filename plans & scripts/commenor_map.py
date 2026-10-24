"""Commenor, the trader world of the Commenor Run, as one battlefield before the Clone Wars (research:
WIPGFX/research/commenor/; the user, 2026-10-21: Chasin City the capital). LEGENDS: cities, mountains, oceans, deserts and
canyons; Chasin City, one of the largest cities, famous for its restaurants; Anteluma, the sporting centre, home of
many major leagues; Munto, a large city built in the Munto valley with its houses on the terraces, and Kliffen near it;
the University of Commenor, where Senator Amidala spoke to a great peace rally in the last days of the Separatist
Crisis. Owner: REP (as before).
LAYOUT IS A DESIGN CHOICE: Chasin City in the middle; Anteluma north-east; the University in the north (the Kuat lane);
Munto in its valley west of the capital (the valley carved into the terrain, landforms()) with Kliffen beside it to the
south-west; the Commenor Run Spaceport on the eastern coast (the Neimodia lane); the deserts south-east, the canyonlands
south (the Duro lane); the Commenor Mountains (impassable) east of the capital, the Northern Ocean (impassable)
north-west, the Southern Ocean (impassable) south-west; the western coast faces the Rendilli lane.
Names from the sources: Chasin City, Anteluma, Munto, Munto Valley, Kliffen, University of Commenor. Invented: Northern
Commenor, Commenor Desert, the Canyonlands, the Eastern Coast, the Commenor Run Spaceport, the mountains and oceans.
    python "WIPGFX/plans & scripts/commenor_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/commenor_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 62 province ids are kept (strategic region unchanged); only the pixels move.
Run order: commenor_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> planet_terrain_gen.py --planet
Commenor -> military_buildings.py commenor_atlas, models hod_com_ -> coruscant_buildings.py wire -> military_buildings.py
place Commenor -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Commenor"
ZONES_JSON = "WIPGFX/Assets/commenor_zones.json"
ZONES_PNG = "WIPGFX/Assets/commenor_zones.png"
KIND = {"city": 1, "arena": 2, "university": 3, "valley": 4, "port": 5, "plains": 6, "hills": 7, "desert": 8, "canyon": 9,
        "coast": 10, "sea": 11, "mountains": 12}
TERRAIN = {"city": "urban", "arena": "urban", "university": "urban", "valley": "hills", "port": "urban", "plains": "plains",
           "hills": "hills", "desert": "desert", "canyon": "hills", "coast": "plains", "sea": "mountain", "mountains": "mountain"}
SEED = 17
CAPITAL = 17
CAPITAL_VP = "Chasin City"
CORE = "REP"
PORT_STATE = 320                     # the Commenor Run Spaceport
OWNER = {s: "REP" for s in (17, 314, 315, 316, 317, 318, 319, 320, 1351, 1352, 1353)}
WARP = (0.12, 9)
TARGET_PASSABLE = 40                 # user rule: passable provinces outnumber impassable (~40 / 22)
STRAIGHT = {"arena", "university", "port"}
FEATURES = [
    ("Chasin City", "city", CAPITAL, 2, [("ell", 0.0, 0.0, 0.18, 0.13, 10)]),
    ("Anteluma", "arena", 314, 1, [("ell", 0.42, -0.42, 0.1, 0.08, 0)]),
    ("University of Commenor", "university", 315, 1, [("rect", -0.05, -0.6, 0.1, 0.08, 0)]),
    ("Munto", "valley", 316, 2, [("rect", -0.45, -0.08, 0.17, 0.08, 0)]),
    ("Kliffen", "city", 317, 1, [("ell", -0.48, 0.24, 0.08, 0.07, 0)]),
    ("Commenor Run Spaceport", "port", 320, 1, [("rect", 0.78, 0.0, 0.12, 0.1, 0)]),
    ("Commenor Mountains", "mountains", 1351, 0, [("cap", 0.35, -0.12, 0.45, 0.32, 0.11), ("cap", 0.45, 0.32, 0.3, 0.5, 0.09)]),
    ("Northern Ocean", "sea", 1352, 0, [("ell", -0.6, -0.68, 0.36, 0.2, 40), ("cap", -0.95, -0.2, -0.75, -0.45, 0.1)]),
    ("Southern Ocean", "sea", 1353, 0, [("cap", -0.95, 0.5, -0.4, 0.75, 0.13), ("cap", -0.4, 0.75, -0.3, 0.95, 0.1)]),
]
SEEDS = {CAPITAL: ((0.0, 0.0), "plains"), 314: ((0.5, -0.45), "hills"), 315: ((-0.05, -0.65), "hills"),
         316: ((-0.45, -0.1), "hills"), 317: ((-0.55, 0.3), "plains"), 318: ((0.5, 0.6), "desert"), 319: ((0.0, 0.7), "canyon"),
         320: ((0.8, 0.0), "coast")}
STATE_NAMES = {CAPITAL: "Chasin City", 314: "Anteluma", 315: "Northern Commenor", 316: "Munto Valley", 317: "Kliffen",
               318: "Commenor Desert", 319: "Canyonlands", 320: "Eastern Coast", 1351: "Commenor Mountains",
               1352: "Northern Ocean", 1353: "Southern Ocean"}
IMPASSABLE = {1351, 1352, 1353}
VPS = [(CAPITAL, "Chasin City", CAPITAL_VP, 10), (314, "Anteluma", "Anteluma", 3), (315, "University of Commenor", "University of Commenor", 5),
       (316, "Munto", "Munto", 3), (317, "Kliffen", "Kliffen", 2), (320, "Commenor Run Spaceport", "Commenor Run Spaceport", 3),
       (318, "desert", "Commenor Desert", 1), (319, "canyon", "Canyonlands", 1)]

def landforms(ctx):
    """Munto in the ground itself (the user, 2026-10-21: landforms in the terrain, not stand-alone rock models): a
    shelf round it with a valley cut west-east through it, the model set into its walls (floor at the VP)"""
    rel, z, sub, yy, xx, zj = ctx["rel"], ctx["z"].copy(), ctx["sub"], ctx["yy"], ctx["xx"], ctx["zj"]
    p = next(q for q, n in zj["vp_names"].items() if n == "Munto")
    r0, c0 = zj["provinces"][p]["centre"]
    r0, c0 = r0 - ctx["sl"][0].start, c0 - ctx["sl"][1].start
    d = np.hypot(yy - r0, xx - c0)
    ground = sub & np.isin(z, (4, 7, 6))
    plat = np.clip((11.0 - d) / 3.5, 0, 1)
    plat = plat * plat * (3 - 2 * plat)
    rel = np.where(ground, np.maximum(rel, 30.0 * plat + rel * (1 - plat)), rel)
    along = np.clip((9.0 - np.abs(xx - c0)) / 2.5, 0, 1)
    wall = np.clip((np.abs(yy - r0) - 1.8) / 2.4, 0, 1)
    cut = ground & (along > 0) & (wall < 1)
    rel = np.where(cut, rel * wall - 3.0 * (1 - wall) * along + rel * (1 - along) * (1 - wall), rel)
    ctx["rel"], ctx["z"] = rel, z


TERRAIN_CFG = dict(
    hook=landforms,
    seed=17, base=4, rough=2, open=(6, 7, 8, 9, 10),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("GRASS", ">", 0.6)]),
        2: dict(relief=("flat", 5), tex=["URBAN", ("GRASS", ">", 0.6)]),
        3: dict(relief=("flat", 6), tex=["URBAN", ("GRASS", ">", 0.5)], props=[(246, 0.2)]),
        4: dict(relief=("flat", 2), tex=["GRASSHILL", ("URBAN", ">", 0.6)], props=[(246, 0.15)]),       # Munto's valley
        5: dict(relief=("flat", 4), tex=["URBAN", ("ROCK2", ">", 0.5)]),
        6: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("FARM", ">", 0.6), (13, ">", 0.94)], props=[(246, 0.25), (247, 0.2)]),
        7: dict(relief=("rolling", 10, 7, 5), tex=["GRASSHILL", ("ROCK2", ">", 0.6), (13, ">", 0.95)], props=[(246, 0.3)]),
        8: dict(relief=("rolling", 4, 4, 6), tex=["DUNES", ("SAND", ">", 0.5), ("BROWN", ">", 0.85)], props=[(247, 0.1)]),
        9: dict(relief=("mesa", 2, 12, 3, (5, 0.55)), tex=["BROWN", ("ROCK2", ">", 0.5)], props=[(247, 0.08)]),   # canyonlands
        10: dict(relief=("rolling", 3, 2, 8), tex=["GRASS", ("SAND", ">", 0.6), (13, ">", 0.94)], props=[(247, 0.15)]),
        11: dict(relief=("flat", 0.3), tex="WATER"),
        12: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["ROCK", ("SNOWROCK", ">", 0.85)]),
    },
    steep=("ROCK", 6, (6, 7, 8, 10)),
    city={1: 90, 2: 90, 3: 90, 5: 90, 6: 90, 10: 90},   # map/cities.txt 90: Commenor's towns (com_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.63, 0.559, 0.496), 2: (0.609, 0.538, 0.477), 3: (0.609, 0.582, 0.477), 4: (0.525, 0.468, 0.272), 5: (0.588, 0.563, 0.52), 6: (0.567, 0.518, 0.154), 7: (0.483, 0.432, 0.201), 8: (0.777, 0.47, 0.225), 9: (0.63, 0.288, 0.118), 10: (0.588, 0.534, 0.205), 11: (0.1, 0.42, 0.62), 12: (0.525, 0.497, 0.492)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)

PLACEMENT = dict(
    new_models={"hod_com_chasin", "hod_com_arena", "hod_com_university", "hod_com_munto", "hod_com_port"},
    items=[("hod_com_chasin", 1.0, ("at_vp", "Chasin City")), ("hod_com_arena", 1.0, ("at_vp", "Anteluma")),
           ("hod_com_university", 0.9, ("at_vp", "University of Commenor")), ("hod_com_munto", 1.0, ("at_vp", "Munto")),
           ("hod_com_port", 0.9, ("at_vp", "Commenor Run Spaceport"))],
    no_pad={"hod_com_munto"},   # it stands in the valley landforms() cuts
    clear={"hod_com_chasin": 5.5, "hod_com_arena": 4.5, "hod_com_university": 3.5, "hod_com_munto": 5.0, "hod_com_port": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (commenor_map.py)\n{imp}"
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
