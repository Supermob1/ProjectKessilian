"""Balmorra, the Techno Union's arms world, as one battlefield before the Clone Wars (research: WIPGFX/research/balmorra/;
the user, 2026-10-21: a mix of the SWTOR and the Bad Batch looks, the Techno Union keeps it). LEGENDS (SWTOR): canyons,
plains, mountains and industrial wastelands that still hold the planet's first assembly lines and refineries, polluted
air, the wind-cut rock spires; Bin Prime, the capital after it moved from Sobrik; Sobrik, the old capital and industrial
region, with the Gorinth Canyon's ravines near it; the Markaran Plains with the Jacent Valley; Bugtown (the Farnel
Research Facility, Lab 352) in the Broken Valley next to Lake Farnell; the Sundari Flatlands, fought over for the
Balmorran Arms Factory. CANON (The Bad Batch): a rocky, barren surface of mountains and gorges, droid factories, an
outpost, the Swellbottom market. Owner: TCU (as before).
LAYOUT IS A DESIGN CHOICE beyond the stated relationships: Bin Prime in the west with the Swellbottom market and its
coast (the Alderaan lane), Sobrik in the north-east with the Gorinth Canyon beside it and the outpost in the gorges, the
Sundari Flatlands south-east with the Balmorran Arms Factory (the Neimodia lane), the Markaran Plains south-west with
the Broken Valley and Lake Farnell (the Kuat lane); the Northern Spires (impassable rock spire massifs) across the north,
the Grey Crags (impassable, the Bad Batch's mountains) between Sobrik and the Flatlands, Lake Farnell (impassable).
Names from the sources: Bin Prime, Sobrik, Gorinth Canyon, Markaran Plains, Jacent Valley, Bugtown, Broken Valley, Lake
Farnell, Sundari Flatlands, Balmorran Arms Factory, Swellbottom Market, Balmorra Outpost (canon: an Imperial outpost; a
Techno Union garrison here). Invented: Bin Prime Spaceport, the Northern Spires, the Grey Crags.
    python "WIPGFX/plans & scripts/balmorra_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/balmorra_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 63 province ids are kept (strategic region unchanged); only the pixels move.
Run order: balmorra_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (bal_*) ->
planet_terrain_gen.py --planet Balmorra -> military_buildings.py balmorra_atlas, models hod_bal_ -> coruscant_buildings.py
wire -> military_buildings.py place Balmorra -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Balmorra"
ZONES_JSON = "WIPGFX/Assets/balmorra_zones.json"
ZONES_PNG = "WIPGFX/Assets/balmorra_zones.png"
KIND = {"city": 1, "factory": 2, "market": 3, "canyon": 4, "lab": 5, "outpost": 6, "plains": 7, "flats": 8,
        "wastes": 9, "valley": 10, "spires": 11, "crags": 12, "lake": 13, "port": 14}
TERRAIN = {"city": "urban", "factory": "urban", "market": "urban", "canyon": "hills", "lab": "plains", "outpost": "hills",
           "plains": "plains", "flats": "plains", "wastes": "desert", "valley": "hills", "spires": "mountain",
           "crags": "mountain", "lake": "mountain", "port": "urban"}
SEED = 16
CAPITAL = 16
CAPITAL_VP = "Bin Prime"
CORE = "TCU"
PORT_STATE = 16                      # Bin Prime's spaceport on the western coast
OWNER = {s: "TCU" for s in (16, 178, 179, 180, 1315, 1316, 1317)}
WARP = (0.12, 9)
TARGET_PASSABLE = 41                 # user rule: passable provinces outnumber impassable (~41 / 22)
STRAIGHT = {"factory", "port"}
FEATURES = [
    ("Bin Prime", "city", CAPITAL, 2, [("ell", -0.35, -0.02, 0.17, 0.12, 15)]),
    ("Swellbottom Market", "market", CAPITAL, 1, [("ell", -0.16, 0.12, 0.08, 0.06, 0)]),
    ("Bin Prime Spaceport", "port", CAPITAL, 1, [("rect", -0.86, -0.18, 0.14, 0.12, 12)]),
    ("Sobrik", "city", 179, 2, [("ell", 0.32, -0.42, 0.15, 0.11, -20)]),
    ("Gorinth Canyon", "canyon", 179, 2, [("cap", 0.08, -0.25, 0.25, 0.05, 0.06), ("cap", 0.25, 0.05, 0.4, 0.1, 0.05)]),
    ("Balmorra Outpost", "outpost", 179, 1, [("ell", 0.7, -0.32, 0.1, 0.09, 0)]),
    ("Balmorran Arms Factory", "factory", 178, 2, [("rect", 0.4, 0.5, 0.15, 0.1, -15)]),
    ("Bugtown", "lab", 180, 1, [("ell", -0.24, 0.6, 0.1, 0.09, 0)]),
    ("Lake Farnell", "lake", 1317, 0, [("ell", -0.05, 0.72, 0.12, 0.07, -25)]),
    ("Broken Valley", "valley", 180, 1, [("cap", -0.38, 0.45, -0.18, 0.6, 0.07)]),
    ("Northern Spires", "spires", 1315, 0, [("ell", -0.3, -0.74, 0.42, 0.17, 12), ("cap", -0.62, -0.42, -0.15, -0.38, 0.09), ("cap", -0.05, -0.86, 0.4, -0.82, 0.09)]),
    ("Grey Crags", "crags", 1316, 0, [("cap", 0.55, -0.05, 0.92, 0.15, 0.12), ("cap", 0.6, 0.05, 0.62, 0.28, 0.1)]),
]
SEEDS = {CAPITAL: ((-0.45, -0.1), "wastes"), 179: ((0.4, -0.45), "wastes"), 178: ((0.45, 0.55), "flats"),
         180: ((-0.45, 0.55), "plains")}
STATE_NAMES = {CAPITAL: "Bin Prime", 178: "Sundari Flatlands", 179: "Sobrik", 180: "Markaran Plains",
               1315: "Northern Spires", 1316: "Grey Crags", 1317: "Lake Farnell"}
IMPASSABLE = {1315, 1316, 1317}
VPS = [(CAPITAL, "Bin Prime", CAPITAL_VP, 10), (CAPITAL, "Swellbottom Market", "Swellbottom Market", 2),
       (CAPITAL, "Bin Prime Spaceport", "Bin Prime Spaceport", 2), (179, "Sobrik", "Sobrik", 5),
       (179, "Gorinth Canyon", "Gorinth Canyon", 2), (179, "Balmorra Outpost", "Balmorra Outpost", 2),
       (178, "Balmorran Arms Factory", "Balmorran Arms Factory", 10), (180, "Bugtown", "Bugtown", 2),
       (180, "Broken Valley", "Broken Valley", 1), (180, "plains", "Jacent Valley", 1), (178, "flats", "Sundari Flatlands", 1)]

def landforms(ctx):
    """the Balmorra outpost in the ground itself (the user, 2026-10-21: like Crevasse City): a rock shelf round it with
    a gorge cut west-east through it, the outpost set into its walls (bal_outpost, floor at the VP)"""
    rel, z, sub, yy, xx, zj = ctx["rel"], ctx["z"].copy(), ctx["sub"], ctx["yy"], ctx["xx"], ctx["zj"]
    p = next(q for q, n in zj["vp_names"].items() if n == "Balmorra Outpost")
    r0, c0 = zj["provinces"][p]["centre"]
    r0, c0 = r0 - ctx["sl"][0].start, c0 - ctx["sl"][1].start
    d = np.hypot(yy - r0, xx - c0)
    ground = sub & np.isin(z, (6, 9, 12))                                      # the outpost, the wastes, the crags
    plat = np.clip((8.0 - d) / 3.0, 0, 1)
    plat = plat * plat * (3 - 2 * plat)
    rel = np.where(ground, np.maximum(rel, 30.0 * plat + rel * (1 - plat)), rel)
    along = np.clip((6.5 - np.abs(xx - c0)) / 2.0, 0, 1)                       # the gorge, tapering at both ends
    wall = np.clip((np.abs(yy - r0) - 1.6) / 1.4, 0, 1)
    cut = ground & (along > 0) & (wall < 1)
    rel = np.where(cut, rel * wall - 4.0 * (1 - wall) * along + rel * (1 - along) * (1 - wall), rel)
    z[cut] = 6
    ctx["rel"], ctx["z"] = rel, z


TERRAIN_CFG = dict(
    hook=landforms,
    seed=16, base=4, rough=2, open=(7, 8, 9, 14),
    zones={
        1: dict(relief=("flat", 6), tex=["URBAN", ("BROWN", ">", 0.6)]),                              # Bin Prime, Sobrik
        2: dict(relief=("flat", 5), tex=["URBAN", ("BROWN", ">", 0.5)], props=[(227, 0.15)]),         # the Arms Factory
        3: dict(relief=("flat", 6), tex=["URBAN", ("SAND", ">", 0.6)]),                               # the market
        4: dict(relief=("flat", 0.5), tex=["ROCK2", ("BROWN", ">", 0.55)], props=[(226, 0.08)]),      # the canyon floor
        5: dict(relief=("flat", 4), tex=["GRASS", ("URBAN", ">", 0.6)], props=[(228, 0.2)]),          # Bugtown
        6: dict(relief=("flat", 4), tex=["ROCK", ("ROCK2", ">", 0.5)]),                               # the outpost's gorge
        7: dict(relief=("rolling", 4, 4, 7), tex=["SAVANNA", ("GRASS", ">", 0.6), ("BROWN", ">", 0.88)],
                props=[(228, 0.35), (226, 0.06)]),                                                    # the Markaran Plains
        8: dict(relief=("rolling", 3, 2, 8), tex=["BROWN", ("SAVANNA", ">", 0.6), (13, ">", 0.93)],
                props=[(227, 0.1), (228, 0.12)]),                                                     # the Sundari Flatlands
        9: dict(relief=("rolling", 6, 6, 5), tex=["BROWN", ("SAND", ">", 0.55), ("ROCK2", ">", 0.85), (13, ">", 0.95)],
                props=[(227, 0.2), (226, 0.12)]),                                                     # industrial wastes
        10: dict(relief=("rolling", 2, 3, 5), tex=["GRASS", ("SAVANNA", ">", 0.5)], props=[(228, 0.4), (226, 0.1)]),
        11: dict(relief=("spires", 14, 8, 0.14, (1.2, 2.6), (30, 55)), tex=["BROWNMTN", ("SAND", ">", 0.55), ("ROCK2", ">", 0.85)],
                props=[(226, 0.3)]),                                                                  # the spires
        12: dict(relief=("rolling", 22, 16, 4), tex=["ROCK", ("ROCK2", ">", 0.5)], props=[(226, 0.05)]),   # the Grey Crags
        13: dict(relief=("flat", 0.3), tex="WATER"),                                                  # Lake Farnell
        14: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.5)]),                             # the spaceport
    },
    steep=("ROCK", 6, (7, 8, 9, 10)),
    city={1: 83, 2: 83, 3: 83, 9: 83, 14: 83},   # map/cities.txt 83: Balmorra's factory towns (bal_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.525, 0.441, 0.347), 2: (0.462, 0.381, 0.289), 3: (0.588, 0.462, 0.304), 4: (0.525, 0.346, 0.145), 5: (0.483, 0.45, 0.241), 6: (0.483, 0.432, 0.376), 7: (0.588, 0.477, 0.237), 8: (0.63, 0.431, 0.175), 9: (0.567, 0.378, 0.15), 10: (0.504, 0.466, 0.193), 11: (0.693, 0.413, 0.098), 12: (0.525, 0.496, 0.481), 13: (0.25, 0.3, 0.25), 14: (0.546, 0.493, 0.434)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)

PLACEMENT = dict(
    new_models={"hod_bal_binprime", "hod_bal_market", "hod_bal_sobrik", "hod_bal_arms", "hod_bal_bugtown",
                "hod_bal_outpost", "hod_bal_port"},
    items=[("hod_bal_binprime", 1.0, ("at_vp", "Bin Prime")), ("hod_bal_market", 0.8, ("at_vp", "Swellbottom Market")),
           ("hod_bal_port", 0.9, ("at_vp", "Bin Prime Spaceport")), ("hod_bal_sobrik", 1.0, ("at_vp", "Sobrik")),
           ("hod_bal_arms", 1.0, ("at_vp", "Balmorran Arms Factory")), ("hod_bal_bugtown", 0.8, ("at_vp", "Bugtown")),
           ("hod_bal_outpost", 0.8, ("at_vp", "Balmorra Outpost"))],
    clear={"hod_bal_binprime": 5.5, "hod_bal_market": 3.0, "hod_bal_port": 4.0, "hod_bal_sobrik": 5.0,
           "hod_bal_arms": 6.0, "hod_bal_bugtown": 3.5, "hod_bal_outpost": 3.5},
    no_pad={"hod_bal_outpost"},   # it stands in the gorge landforms() cuts
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (balmorra_map.py)\n{imp}"
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
