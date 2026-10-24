"""Dantooine as one KOTOR battlefield: the stretch of grassland round the Jedi Enclave (research: WIPGFX/research/
dantooine/; the user, 2026-10-20: "focus on a smaller part of the map ... like how korriban and ruusan are done", after
the KOTOR I/II area map he sent, WIPGFX/research/dantooine/references: not shipped). LEGENDS: pastel grasslands dotted
with blba trees, rivers and lakes; the settlers' family estates isolated from each other by blba forests; the Jedi
Enclave of Vodo-Siosk Baas, bombed by the Sith in the Jedi Civil War and left in ruins; the Rakatan ruins with their
Star Map (the KOTOR map's "Ancient Temple"); the Grove; the Matale and Sandral estates on their grounds; the kinrath
caves over kyber crystals; Khoonda, the settlers' government seat built from the Matale estate (KOTOR II). Owner: IBC
(as before); capital Khoonda (the user, 2026-10-20).
LAYOUT AFTER THE KOTOR MAP (its areas and trails; the map's south is the planet's south): the Enclave in the north-west
with its landing field on the planet's edge and the courtyard clearing east of it across a bridge; the Ancient Temple in
the north-east; the Matale Grounds east; a glade north of the river's bend; the Grove west; Khoonda on the great central
clearing (where KOTOR II's Khoonda plains would lie: placed here, a design choice); the Sandral Grounds south-west on the
edge; the Kinrath Caves south; the river running north to south through the middle under the trails' bridges (terrain);
everything off the clearings and trails is wild blba forest and broken hills (impassable, five banks between the trails).
Legends names: the Jedi Enclave, Khoonda, the Matale and Sandral estates and grounds, the Grove, the Rakatan ruins
(Ancient Temple), the kinrath caves. Invented: the Northern Glade, the wild banks' names.
    python "WIPGFX/plans & scripts/dantooine_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/dantooine_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 192 province ids are kept (strategic region unchanged); only the pixels move.
Run order: dantooine_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (dan_*) ->
planet_terrain_gen.py --planet Dantooine -> military_buildings.py models hod_dan -> coruscant_buildings.py wire ->
military_buildings.py place Dantooine -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Dantooine"
ZONES_JSON = "WIPGFX/Assets/dantooine_zones.json"
ZONES_PNG = "WIPGFX/Assets/dantooine_zones.png"
KIND = {"enclave": 1, "khoonda": 2, "temple": 3, "estate": 4, "grove": 5, "cave": 6, "glade": 7, "trail": 8,
        "wild": 9, "river": 10}
TERRAIN = {"enclave": "urban", "khoonda": "urban", "temple": "hills", "estate": "plains", "grove": "forest",
           "cave": "hills", "glade": "plains", "trail": "plains", "wild": "forest", "river": "marsh"}
SEED = 110
CAPITAL = 110
CAPITAL_VP = "Khoonda"
PORT_STATE = 898                     # the Enclave's landing field on the planet's edge
OWNER = {s: "IBC" for s in (110, 898, 899, 900, 901, 902, 903, 904, 1270, 1271, 1272, 1273, 1274)}
WARP = (0.08, 9)
TARGET_PASSABLE = 110                # passable provinces outnumber impassable (~110 / 82): the clearings and trails cut
                                     # small, the wild banks big
STRAIGHT = set()
LANE_W = 0.055                       # trail half width, planet radii


def _xy(x, y):
    """the KOTOR map's pixels (1810 x 2000 as shown) to planet radii"""
    return (x - 905) / 950, (y - 1035) / 950


def _trail(*pts):
    pts = [_xy(*p) for p in pts]
    return [("cap", *a, *b, LANE_W) for a, b in zip(pts, pts[1:])]


def _ell(x, y, rx, ry, a=0):
    return ("ell", *_xy(x, y), rx / 950, ry / 950, a)


# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); the clearings first, then the trails between them; everything left is wild (impassable)
FEATURES = [
    ("Jedi Enclave", "enclave", 898, 5, [_ell(440, 320, 180, 140), _ell(330, 470, 130, 100), _ell(250, 450, 110, 110)]),
    ("Enclave Courtyard", "glade", 898, 2, [_ell(920, 360, 100, 110)]),
    ("Ancient Temple", "temple", 904, 2, [_ell(1285, 450, 85, 75)]),
    ("Matale Grounds", "estate", 899, 7, [_ell(1150, 760, 300, 130), _ell(1420, 790, 110, 110)]),
    ("Northern Glade", "glade", 900, 3, [_ell(630, 700, 140, 95)]),
    ("The Grove", "grove", 901, 4, [_ell(680, 1120, 160, 130, 10)]),
    ("Khoonda", "khoonda", CAPITAL, 8, [_ell(1080, 1190, 210, 190)]),
    ("Sandral Grounds", "estate", 902, 5, [_ell(510, 1640, 140, 160), _ell(440, 1760, 120, 100)]),
    ("Kinrath Caves", "cave", 903, 4, [_ell(900, 1720, 240, 75), _ell(1200, 1720, 70, 50)]),
    ("Enclave Bridge", "trail", 898, 0, _trail((580, 310), (840, 320))),
    ("Temple Trail", "trail", 904, 0, _trail((960, 270), (1110, 280), (1200, 370), (1260, 420))),
    ("Matale Trail", "trail", 899, 0, _trail((1140, 480), (1150, 560), (1400, 580), (1400, 680))),
    ("Glade Trail", "trail", 900, 0, _trail((860, 470), (800, 520), (560, 560), (540, 640))),
    ("Glade Bridge", "trail", 899, 0, _trail((760, 710), (870, 720))),
    ("Grove Trail", "trail", 901, 0, _trail((520, 760), (560, 900), (600, 1010))),
    ("Grove Bridge", "trail", CAPITAL, 0, _trail((830, 1070), (900, 1090))),
    ("Khoonda Trail", "trail", CAPITAL, 0, _trail((1390, 880), (1160, 950), (1130, 1020))),
    ("Sandral Trail", "trail", 902, 0, _trail((600, 1250), (570, 1400), (530, 1500))),
    ("Sandral Bridge", "trail", 903, 0, _trail((630, 1660), (700, 1680))),
    ("Cave Trail", "trail", 903, 0, _trail((1000, 1380), (1060, 1550), (1060, 1660))),
]
# the wild left between the trails: each separate bank its own impassable state, named by the anchor nearest its middle
WILD_BANKS = {1270: (-0.85, 0.0), 1271: (0.75, 0.25), 1272: (0.12, -0.52), 1273: (-0.05, -0.12), 1274: (-0.1, 0.45)}
WILD_STATES = list(WILD_BANKS)
SEEDS = {}
STATE_NAMES = {CAPITAL: "Khoonda Plains", 898: "Jedi Enclave", 899: "Matale Grounds", 900: "Northern Glade",
               901: "The Grove", 902: "Sandral Grounds", 903: "Kinrath Caves", 904: "Ancient Temple",
               1270: "Western Blba Forest", 1271: "Eastern Hills", 1272: "Banir Woods", 1273: "River Wilds",
               1274: "Southern Thickets"}
IMPASSABLE = set(WILD_STATES)
VPS = [(CAPITAL, "Khoonda", CAPITAL_VP, 10), (898, "Jedi Enclave", "Jedi Enclave", 5),
       (904, "Ancient Temple", "Ancient Temple", 3), (899, "Matale Grounds", "Matale Estate", 2),
       (900, "Northern Glade", "Northern Glade", 1), (901, "The Grove", "The Grove", 3),
       (902, "Sandral Grounds", "Sandral Estate", 2), (903, "Kinrath Caves", "Kinrath Caves", 2)]
# the river, north to south through the middle (the KOTOR map), drawn by the terrain hook through the wild only, so the
# trails cross it as bridges
RIVER = [(-0.14, -1.09), (-0.12, -0.83), (-0.08, -0.46), (0.0, -0.04), (-0.19, 0.28), (-0.26, 0.6), (-0.23, 1.0)]


def river(ctx):
    """the river through the wild (zone 9 -> 10), a winding channel cut low; the trails over it stay bridges"""
    z, rel, yy, xx, sub = ctx["z"].copy(), ctx["rel"], ctx["yy"], ctx["xx"], ctx["sub"]
    (cy, cx), R = ctx["zj"]["centre"], ctx["zj"]["radius"]
    U, V = (xx + ctx["sl"][1].start - cx) / R, (yy + ctx["sl"][0].start - cy) / R
    d = np.full(z.shape, 9.0, np.float32)
    for (u0, v0), (u1, v1) in zip(RIVER, RIVER[1:]):
        du, dv = u1 - u0, v1 - v0
        t = np.clip(((U - u0) * du + (V - v0) * dv) / (du * du + dv * dv), 0, 1)
        d = np.minimum(d, np.hypot(U - u0 - t * du, V - v0 - t * dv))
    w = (0.022 + 0.012 * (V + 1) / 2) * (1 + 0.3 * ctx["rough"])                 # widening downstream
    m = sub & (z == 9) & (d < w)
    z[m] = 10
    ctx["rel"], ctx["z"] = np.where(m, 0.3, rel), z


# terrain (planet_terrain_gen.py --planet Dantooine). Heights in heightmap steps above the base. KOTOR's Dantooine:
# pastel grass clearings with tall grass (flora 198) and lone blba trees (197), the trails beaten earth and grass, the
# wild between them dense blba forest on broken hills, the river through it; the estates (map/cities.txt 66) thin on the
# clearings
TERRAIN_CFG = dict(
    seed=110, base=4, rough=2, open=(4, 5, 7, 8),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("flat", 6), tex=["GRASS", ("ROCK2", ">", 0.6)], props=[(198, 0.05)]),     # the Enclave
        2: dict(relief=("rolling", 5, 1.5, 6), tex=["GRASS", ("SAVANNA", ">", 0.6), (13, ">", 0.94)], props=[(198, 0.12)]),   # Khoonda
        3: dict(relief=("ramp_top", 9, 5, 3), tex=["GRASS", ("ROCK2", ">", 0.55)], props=[(197, 0.1)]),     # temple
        4: dict(relief=("rolling", 5, 2, 6), tex=["GRASS", ("SAVANNA", ">", 0.55), (13, ">", 0.93)],
                props=[(198, 0.2), (197, 0.04)]),                                                  # the estates
        5: dict(relief=("rolling", 6, 3, 5), tex=["FOREST", ("GRASS", ">", 0.55)], props=[(197, 0.4), (198, 0.15)]),
        6: dict(relief=("ramp_top", 9, 6, 3), tex=["ROCK2", ("GRASSHILL", ">", 0.5)], props=[(197, 0.06)]),   # caves
        7: dict(relief=("rolling", 5, 2, 6), tex=["GRASS", ("SAVANNA", ">", 0.6), (13, ">", 0.95)], props=[(198, 0.25), (197, 0.04)]),
        8: dict(relief=("rolling", 5, 1, 6), tex=["SAVANNA", ("GRASS", ">", 0.5)], props=[(198, 0.06)]),     # trails
        9: dict(relief=("rolling", 12, 8, 4), tex=["FOREST", ("DFOREST", ">", 0.45), ("GRASSHILL", ">", 0.85)],
                props=[(197, 0.75), (198, 0.1)]),                                                  # the wild
        10: dict(tex="WATER"),                                                                     # the river (hook)
    },
    steep=("ROCK2", 6, (4, 5, 7, 8)),
    city={2: 66, 4: 66, 7: 66},   # map/cities.txt 66: the settlers' estates (dan_estate), thin on the clearings
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    level=(10,),
    hook=river,
    colors={1: (0.58, 0.6, 0.46), 2: (0.6, 0.64, 0.46), 3: (0.52, 0.56, 0.42), 4: (0.62, 0.66, 0.46),
            5: (0.36, 0.5, 0.32), 6: (0.5, 0.5, 0.42), 7: (0.62, 0.66, 0.48), 8: (0.6, 0.6, 0.44), 9: (0.26, 0.38, 0.24),
            10: (0.22, 0.36, 0.42)},
)

# models (military_buildings.py place Dantooine): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_dan_khoonda", "hod_dan_enclave", "hod_dan_rakatan", "hod_dan_cave", "hod_dan_matale",
                "hod_dan_sandral", "hod_dan_grove"},
    items=[("hod_dan_khoonda", 1.0, ("at_vp", CAPITAL_VP)), ("hod_dan_enclave", 1.0, ("at_vp", "Jedi Enclave")),
           ("hod_dan_rakatan", 0.9, ("at_vp", "Ancient Temple")), ("hod_dan_cave", 1.0, ("at_vp", "Kinrath Caves")),
           ("hod_dan_matale", 1.0, ("at_vp", "Matale Estate")), ("hod_dan_sandral", 1.0, ("at_vp", "Sandral Estate")),
           ("hod_dan_grove", 1.0, ("at_vp", "The Grove"))],
    clear={"hod_dan_khoonda": 6.0, "hod_dan_enclave": 8.0, "hod_dan_rakatan": 5.5, "hod_dan_cave": 4.5,
           "hod_dan_matale": 5.0, "hod_dan_sandral": 5.5, "hod_dan_grove": 5.5},
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
    """feature index per pixel and features [(name, kind, state, provinces)]: FEATURES in order (the clearings and
    trails), then each wild bank left between them a wild state, the biggest first"""
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
    comp, n = ndi.label(sm & (fid < 0))                                 # the wild banks the trails leave
    sizes = np.bincount(comp.ravel())[1:]
    assert n >= len(WILD_STATES), f"only {n} wild banks for {len(WILD_STATES)} wild states"
    free_banks = dict(WILD_BANKS)
    for j, ci in enumerate(np.argsort(-sizes)):
        frag = comp == ci + 1
        if j < len(WILD_STATES):                                       # the bank's state: the nearest free anchor
            mu, mv = U0[frag].mean(), V0[frag].mean()
            sid = min(free_banks, key=lambda b: math.hypot(free_banks[b][0] - mu, free_banks[b][1] - mv))
            del free_banks[sid]
            feats.append((STATE_NAMES[sid], "wild", sid, 0))
            fid[frag] = len(feats) - 1
        else:                                                           # a scrap pinched off between lanes: joins the
            ring = ndi.binary_dilation(frag) & ~frag & sm               # trail or clearing it borders most
            fid[frag] = int(np.argmax(np.bincount(fid[ring][fid[ring] >= 0], minlength=len(feats))))
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (dantooine_map.py)\n{imp}"
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
