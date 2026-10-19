"""Botajef, the shipbuilding world of the Celanon Spur, as one battlefield before the Clone Wars (research:
WIPGFX/research/botajef/). CANON: a Governor's palace; a north-polar base; a base in the south-polar region.
LEGENDS: Botajef Shipyards (the AA-9 Coruscant freighter, the SS-54 light freighter), with construction and testing
facilities throughout the southern continent; huge elevator cables 325 kilometres long from the surface up to the
orbiting yards. The surface is not described.
Owner: CIS. User (2026-10-19): an industrial world, factories and yards almost everywhere; landmarks the space elevator
with the yards, the Governor's palace, both polar bases.
LAYOUT IS A DESIGN CHOICE: the north and south polar caps (impassable) with the two bases on their edges, the Botajef
Sea (impassable) across the middle cutting the southern continent off from the northern one except for an isthmus in
the east; the capital and the Governor's palace in the north, foundries and works round it; the southern continent all
yards: the elevator anchorage, the shipyards on the coast, the testing grounds by the southern cap.
Canon names: the Governor's Palace, the North-Polar Base, the South-Polar Base. Legends: Botajef Shipyards, the space
elevator. Invented: Botajef City, every state name, the Botajef Sea, the polar cap names.
    python "WIPGFX/plans & scripts/botajef_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/botajef_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 199 province ids are kept (strategic region unchanged); only the pixels move.
Run order: botajef_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (bot_*) ->
planet_terrain_gen.py --planet Botajef -> military_buildings.py models hod_bot -> military_buildings.py place Botajef ->
planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Botajef"
ZONES_JSON = "WIPGFX/Assets/botajef_zones.json"
ZONES_PNG = "WIPGFX/Assets/botajef_zones.png"
KIND = {"capital": 1, "palace": 2, "elevator": 3, "yards": 4, "base": 5, "industry": 6, "works": 7, "testing": 8,
        "sea": 9, "ice": 10}
TERRAIN = {"capital": "urban", "palace": "urban", "elevator": "urban", "yards": "urban", "base": "hills",
           "industry": "urban", "works": "plains", "testing": "desert", "sea": "mountain", "ice": "mountain"}
SEED = 191
CAPITAL = 191
CAPITAL_VP = "Botajef City"
PORT_STATE = 1028
OWNER = {s: "CIS" for s in (191, 1027, 1028, 1029, 1030, 1031, 1032, 1211, 1212, 1213)}
WARP = (0.13, 9)
TARGET_PASSABLE = 133                # user rule: passable provinces outnumber impassable (~133 / 66)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Governor's Palace", "palace", CAPITAL, 1, [("ell", -0.1, -0.32, 0.08, 0.06, 0)]),
    ("Botajef City", "capital", CAPITAL, 4, [("ell", -0.08, -0.28, 0.17, 0.11, 10)]),
    ("North-Polar Base", "base", 1030, 2, [("ell", 0.25, -0.66, 0.14, 0.08, 0)]),
    ("Space Elevator", "elevator", 1027, 2, [("ell", -0.25, 0.5, 0.1, 0.08, 0)]),
    ("Botajef Shipyards", "yards", 1028, 4, [("ell", 0.2, 0.32, 0.2, 0.07, -10)]),
    ("South-Polar Base", "base", 1029, 2, [("ell", 0.2, 0.76, 0.09, 0.05, 0)]),
    # the impassable ground: both polar caps, the sea across the middle (the eastern isthmus left as land)
    ("Northern Cap", "ice", 1211, 0, [("ell", 0.0, -1.02, 0.95, 0.28, 0), ("cap", -0.4, -0.8, 0.0, -0.84, 0.05)]),
    ("Southern Cap", "ice", 1212, 0, [("ell", 0.0, 1.04, 0.95, 0.22, 0)]),
    ("Botajef Sea", "sea", 1213, 0, [("cap", -0.98, 0.12, 0.5, 0.15, 0.09), ("ell", -0.5, 0.15, 0.22, 0.13, 10)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((-0.05, -0.3), "industry"), 1030: ((0.4, -0.5), "industry"), 1031: ((-0.6, -0.35), "works"),
         1032: ((0.7, -0.05), "industry"), 1027: ((-0.45, 0.5), "works"), 1028: ((0.3, 0.35), "industry"),
         1029: ((0.05, 0.7), "testing")}
STATE_NAMES = {CAPITAL: "Botajef City", 1030: "Northern Foundries", 1031: "Western Works", 1032: "Eastern Smelters",
               1027: "Elevator Anchorage", 1028: "Southern Yards", 1029: "Testing Grounds",
               1211: "Northern Cap", 1212: "Southern Cap", 1213: "Botajef Sea"}
IMPASSABLE = {1211, 1212, 1213}
VPS = [(CAPITAL, "Botajef City", CAPITAL_VP, 10), (CAPITAL, "Governor's Palace", "Governor's Palace", 3),
       (1030, "North-Polar Base", "North-Polar Base", 2), (1027, "Space Elevator", "Space Elevator", 5),
       (1028, "Botajef Shipyards", "Botajef Shipyards", 5), (1029, "South-Polar Base", "South-Polar Base", 2),
       (1031, "works", "Western Works", 1), (1032, "industry", "Eastern Smelters", 1)]

# terrain (planet_terrain_gen.py --planet Botajef). Heights in heightmap steps above the base. Factories to the horizon
# (map/cities.txt 39, military_buildings.py bot_city), tank farms (flora_props 140), the polar ice, the sea
TERRAIN_CFG = dict(
    seed=191, base=4, rough=2, open=(6, 7, 8),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("ramp_top", 7, 5, 4), tex="URBAN"),                                       # Botajef City
        2: dict(relief=("ramp_top", 10, 6, 4), tex="URBAN"),                                      # the palace
        3: dict(relief=("flat", 5), tex="URBAN"),                                                  # the elevator
        4: dict(relief=("flat", 4), tex="URBAN"),                                                  # the shipyards
        5: dict(relief=("flat", 7), tex=["SNOWSAND", ("SNOWROCK", ">", 0.7)]),                    # polar bases
        6: dict(relief=("rolling", 5, 3, 5), tex=["URBAN", ("BROWN", ">", 0.8)], props=[(140, 0.06)]),   # industry
        7: dict(relief=("rolling", 5, 4, 5), tex=["URBAN", ("ROCK2", ">", 0.6), ("BROWN", ">", 0.82)],
                props=[(140, 0.1)]),                                                               # works, slag
        8: dict(relief=("rolling", 4, 3, 6), tex=["BROWN", ("ROCK2", ">", 0.55), (13, ">", 0.8)],
                props=[(140, 0.04)]),                                                              # testing grounds
        9: dict(relief=("flat", 0.3), tex="WATER"),                                                # the Botajef Sea
        10: dict(relief=("mesa", 6, 16, 2.0, (4, 0.6)), tex=["SNOWSAND", ("SNOWROCK", ">", 0.6)]),      # polar caps
    },
    steep=("ROCK2", 6, (6, 7, 8)),
    city={1: 39, 2: 39, 3: 39, 4: 39, 6: 39, 7: 39, 8: 39},   # map/cities.txt 39: Botajef's industry (bot_city)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.5, 0.48, 0.45), 2: (0.56, 0.54, 0.5), 3: (0.48, 0.47, 0.45), 4: (0.46, 0.45, 0.43),
            5: (0.86, 0.88, 0.9), 6: (0.47, 0.44, 0.4), 7: (0.45, 0.4, 0.35), 8: (0.5, 0.42, 0.34),
            9: (0.16, 0.26, 0.32), 10: (0.88, 0.9, 0.93)},
)

def orbit(ctx):
    """the orbital shipyards in space (user, 2026-10-19: starships, not boats): military_buildings.BOT_YARD_AT
    (distance, bearing) from the planet's centre, in the open space east of the disc"""
    import military_buildings as mb
    (cy, cx), (r, b) = ctx["z"]["centre"], (mb.BOT_YARD_AT[0], math.radians(mb.BOT_YARD_AT[1]))
    ctx["put"]("hod_bot_orbital", 1.0, cy - r * math.sin(b), cx + r * math.cos(b))


# models (military_buildings.py place Botajef): big, custom (user rule 2026-10-14); the main yards float in orbit
PLACEMENT = dict(
    new_models={"hod_bot_palace", "hod_bot_elevator", "hod_bot_yards", "hod_bot_orbital", "hod_bot_northbase",
                "hod_bot_southbase"},
    items=[("hod_bot_palace", 1.0, ("at_vp", "Governor's Palace")), ("hod_bot_elevator", 1.0, ("at_vp", "Space Elevator")),
           ("hod_bot_yards", 1.0, ("at_vp", "Botajef Shipyards")), ("hod_bot_northbase", 1.0, ("at_vp", "North-Polar Base")),
           ("hod_bot_southbase", 1.0, ("at_vp", "South-Polar Base"))],
    clear={"hod_bot_palace": 5.0, "hod_bot_elevator": 5.0, "hod_bot_yards": 6.0, "hod_bot_northbase": 4.5,
           "hod_bot_southbase": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (botajef_map.py)\n{imp}"
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
