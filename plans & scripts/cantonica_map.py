"""Cantonica, the Corporate Sector's desert world, as one battlefield in the Clone Wars (research:
WIPGFX/research/cantonica/). Canon: a desert and mountain world, "once a quiet, dusty world dotted with ancient cities
and ruins from a civilization that few remembered", then Canto Bight was built, a coastal casino city on the shore of
the artificial Sea of Cantonica (the galaxy's largest, kept alive by sump pumps near the coast); the Casino District,
Old Town, the South Stretch Worker's District and the Westhill cliffs / Westhill Palace. Flora: Cantonican cactus,
Chinar tree. The user (2026-10-14): Canto Bight stands in the Clone Wars (a design choice: canon gives no founding
date) and the ancient ruins are SITH ruins (design choice, not lore).
LAYOUT IS A DESIGN CHOICE (approved 2026-10-14): Canto Bight in a bay between two ridges on the east shore of the
inland sea (Star Wars Outlaws view: a lower town down to a quay, the casino town above it), Westhill's cliffs on the
north shore, the South Stretch and the sump pumps on the south shore, desert, dunes and badland mesas inland, a
mountain chain in the NE, Sith ruins in the east and south.
Invented names: Canto Valley, Great Dunes, Red Wastes, Sith Necropolis, Sith Temple Ruins, Cantonican Highlands,
Southern Badlands, Sump Pump Works, the outposts / camp VPs.
    python "WIPGFX/plans & scripts/cantonica_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/cantonica_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 64 province ids are kept (strategic region 69 unchanged); only the pixels move.
Run order: cantonica_map.py -> planet_terrain_gen.py --planet Cantonica -> military_buildings.py models hod_cant
-> military_buildings.py place Cantonica -> planet_terrain_gen.py --globe-texture.
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

PLANET = "Cantonica"
ZONES_JSON = "WIPGFX/Assets/cantonica_zones.json"
ZONES_PNG = "WIPGFX/Assets/cantonica_zones.png"
KIND = {"desert": 1, "dunes": 2, "city": 3, "casino": 4, "cliffs": 5, "palace": 6, "workers": 7, "pumps": 8,
        "ruins": 9, "sithtemple": 10, "range": 11, "sea": 12, "mesa": 13, "shore": 14}
TERRAIN = {"desert": "desert", "dunes": "desert", "city": "urban", "casino": "urban", "cliffs": "hills",
           "palace": "urban", "workers": "urban", "pumps": "plains", "ruins": "hills", "sithtemple": "hills",
           "range": "mountain", "sea": "marsh", "mesa": "mountain", "shore": "plains"}
SEED = 84
CAPITAL = 84
CAPITAL_VP = "Canto Bight"
PORT_STATE = 741
OWNER = "CSA"
WARP = (0.07, 7)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 45                 # user rule: passable provinces outnumber impassable (~45 / 19, approved)
STRAIGHT = {"casino", "palace"}      # drawn unwarped
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Casino District", "casino", CAPITAL, 2, [("ell", 0.04, 0.0, 0.1, 0.11, 0)]),           # the upper town
    ("Old Town", "city", CAPITAL, 3, [("ell", -0.12, 0.0, 0.11, 0.17, 0)]),                  # down to the quay
    ("Westhill Palace", "palace", 740, 1, [("ell", -0.24, -0.47, 0.08, 0.07, 0)]),
    ("Westhill Cliffs", "cliffs", 740, 2, [("cap", -0.5, -0.5, -0.12, -0.36, 0.1)]),
    ("South Stretch", "workers", PORT_STATE, 2, [("ell", -0.24, 0.5, 0.12, 0.09, 20)]),
    ("Sump Pump Works", "pumps", PORT_STATE, 1, [("ell", -0.47, 0.52, 0.08, 0.07, 0)]),
    ("Sith Necropolis", "ruins", 745, 4, [("ell", 0.6, 0.08, 0.15, 0.13, 20)]),
    ("Sith Temple Ruins", "sithtemple", 746, 2, [("ell", 0.12, 0.8, 0.1, 0.08, 0)]),
    # no round shapes (user rule): a ragged sea of lobes, a bay reaching in to the city's quay
    ("Sea of Cantonica", "sea", 1165, 0, [("ell", -0.62, 0.04, 0.26, 0.3, 25), ("cap", -0.5, 0.0, -0.24, -0.02, 0.1),
                                          ("ell", -0.74, -0.28, 0.14, 0.2, -30), ("ell", -0.66, 0.36, 0.2, 0.12, 35),
                                          ("cap", -0.45, -0.15, -0.36, -0.24, 0.07)]),
    # the bay's two ridges run inland into the NE chain and the southern badlands
    ("Cantonican Highlands", "range", 1166, 0, [("cap", -0.12, -0.2, 0.25, -0.48, 0.08),
                                                ("cap", 0.25, -0.48, 0.4, -0.88, 0.14)]),
    ("Southern Badlands", "mesa", 1167, 0, [("cap", -0.12, 0.2, 0.15, 0.44, 0.08),
                                            ("ell", 0.3, 0.55, 0.2, 0.12, -15)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {740: ((-0.25, -0.75), "shore"), PORT_STATE: ((-0.4, 0.72), "shore"), 742: ((0.22, -0.08), "desert"),
         743: ((0.65, -0.4), "dunes"), 744: ((0.62, 0.55), "desert"), 745: ((0.85, 0.12), "desert"),
         746: ((-0.05, 0.88), "desert")}
STATE_NAMES = {CAPITAL: "Canto Bight", 740: "Westhill Cliffs", PORT_STATE: "South Stretch", 742: "Canto Valley",
               743: "Great Dunes", 744: "Red Wastes", 745: "Sith Necropolis", 746: "Sith Temple Ruins",
               1165: "Sea of Cantonica", 1166: "Cantonican Highlands", 1167: "Southern Badlands"}
IMPASSABLE = {1165, 1166, 1167}
# victory points: (state, feature or kind, name, value). Canon places: Canto Bight (Casino District), Old Town,
# Westhill Palace, the South Stretch; invented: the pump works, the Sith ruins, the outposts
VPS = [(CAPITAL, "casino", CAPITAL_VP, 10), (CAPITAL, "city", "Old Town", 3), (740, "palace", "Westhill Palace", 3),
       (PORT_STATE, "workers", "South Stretch", 2), (PORT_STATE, "pumps", "Sump Pump Works", 1),
       (745, "ruins", "Sith Necropolis", 3), (746, "sithtemple", "Sith Temple Ruins", 2),
       (742, "desert", "Canto Valley Outpost", 1), (743, "dunes", "Dune Camp", 1), (744, "desert", "Red Wastes Outpost", 1)]
# terrain (planet_terrain_gen.py --planet Cantonica; operators: planet_terrain_gen.zone_repaint). Heights in
# heightmap steps above the base; the sea lies under the water plane (~1.3 steps below the base)
REDROCK = [24, ("BROWNMTN", ">", 0.55), ("ROCK2", "<", 0.2)]
TERRAIN_CFG = dict(
    seed=84, base=2, rough=2, open=(1, 2, 8, 14),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 2, 3, 6), tex=["SAND", ("BROWN", ">", 0.62), ("DUNES", "<", 0.25)],
                props=[(89, 0.35), (91, 0.07)], clusters=[(9, 0.55, [(89, 0.8)])]),   # cactus stands, Sith rubble
        2: dict(relief=("rolling", 2, 5, 4), tex=["DUNES", ("SAND", "<", 0.25)], props=[(89, 0.2), (91, 0.05)]),
        3: dict(relief=("ramp_top", 5, 1, 6), tex="URBAN", props=[(88, 0.06)]),   # the lower town, up from the quay;
                                                                          # chinars in its gardens
        4: dict(relief=("ramp_top", 9, 5, 4), tex="URBAN"),                # the casino town, above the old town
        5: dict(relief=("flank", 3, 14, (6,), 5), tex=REDROCK, props=[(90, 0.3), (88, 0.2)]),   # the cliffs up
                                                                          # to the palace, scrub and chinars
        6: dict(relief=("flat", 14), tex=25, props=[(88, 0.2)]),
        7: dict(relief=("flat", 2), tex="URBAN"),
        8: dict(relief=("flat", 1), tex=25, props=[(90, 0.1)]),
        9: dict(relief=("ramp_top", 6, 2, 5), tex=32, props=[(91, 0.12), (89, 0.04)]),   # desert_town_32: sand
                                                                          # that spawns the Sith ruin city models
        10: dict(relief=("flat", 5), tex=32, props=[(91, 0.15)]),
        11: dict(relief=("spires", 14, 6, 0.06, (1.5, 3.0), (20, 45)), tex=REDROCK, props=[(89, 0.03)]),
        12: dict(relief=("flat", -5), tex="WATER"),
        13: dict(relief=("mesa", 2, 20, 2.5, (4, 0.6)), tex=REDROCK, props=[(89, 0.15), (91, 0.06)]),
        14: dict(relief=("rolling", 1, 2, 5), tex=["SAVANNA", ("SAND", ">", 0.6)],    # the green-scrub coast
                 props=[(90, 0.45), (88, 0.25), (89, 0.08)], clusters=[(8, 0.6, [(88, 0.6), (90, 0.3)])]),   # chinar groves
    },
    steep=("ROCK2", 7, (1, 2, 5, 14)),
    city={3: 17, 4: 17, 7: 17, 9: 18, 10: 18},   # map/cities.txt 17: Canto Bight (also the South Stretch), 18: the
                                                 # Sith ruins (user: a ruined city gets its own ruined building set)
    prop_clear=1.6,
)
# models (military_buildings.py place Cantonica): (mesh, scale, where). Big, custom (user rule 2026-10-14): Westhill
# Palace on its cliff top, facing out to sea (built turned, rot in military_buildings.models)
PLACEMENT = dict(
    new_models={"hod_cant_westhill"},
    items=[("hod_cant_westhill", 1.0, ("zone_centre", 6))],
    clear={"hod_cant_westhill": 6.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (cantonica_map.py)\n{imp}"
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
