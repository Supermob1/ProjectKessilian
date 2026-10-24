"""Dromund Kaas, the lost capital of the old Sith Empire, as one battlefield in the Clone Wars (research:
WIPGFX/research/dromund_kaas/). Canon only mentions the planet; everything here is LEGENDS, as of 22-19 BBY (approved
by the user 2026-10-14): a forgotten world of sea and swamp under a perpetually clouded, lightning-filled sky; massive
dark-wooded trees in the swamp water; Kaas City (built on jungle the Imperial Military cleared), the Imperial Citadel,
the Sith Academy and the Dark Temple (in the "Dark Temple pass") all ruins of the Sith Empire by now; the Dark Force
Temple standing in the swamps; during the Clone Wars the Republic's 327th Star Corps fought Separatists under Asajj
Ventress here. Abandoned: no city models.
LAYOUT IS A DESIGN CHOICE except the Dark Temple standing in a pass: Kaas City's ruins on a raised central plateau
(cleared ground) with the Citadel ruin at its heart, the Academy ruins west of it, the Dark Temple in a pass through a
jagged range in the NW, the Dark Force Temple deep in the southern swamps, a flooded inland sea east of the city, the
Separatist base and the 327th's landing zone on the SE coast, storm jungle north, swamps west and south.
Invented names: Northern Storm Jungle, Western Swamps, Dark Force Swamps, Eastern Lowlands, Separatist Landing,
Separatist Base, 327th Landing Zone, the outposts / camp VPs, the impassable states (1161-1164).
    python "WIPGFX/plans & scripts/dromund_kaas_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/dromund_kaas_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 200 province ids are kept (strategic region 72 unchanged); only the pixels move.
Run order: dromund_kaas_map.py -> planet_terrain_gen.py --planet "Dromund Kaas" -> military_buildings.py models hod_dk
-> military_buildings.py place "Dromund Kaas" -> planet_terrain_gen.py --globe-texture.
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

PLANET = "Dromund Kaas"
ZONES_JSON = "WIPGFX/Assets/dromund_kaas_zones.json"
ZONES_PNG = "WIPGFX/Assets/dromund_kaas_zones.png"
KIND = {"swamp": 1, "jungle": 2, "ruins": 3, "citadel": 4, "pass": 5, "temple": 6, "academy": 7, "forcetemple": 8,
        "base": 9, "landing": 10, "range": 11, "sea": 12, "mire": 13, "seacity": 14}
TERRAIN = {"swamp": "marsh", "jungle": "jungle", "ruins": "urban", "citadel": "urban", "pass": "hills",
           "temple": "hills", "academy": "urban", "forcetemple": "marsh", "base": "plains", "landing": "plains",
           "range": "mountain", "sea": "marsh", "mire": "marsh", "seacity": "urban"}
SEED = 89
CAPITAL = 89
CAPITAL_VP = "Imperial Citadel Ruins"
PORT_STATE = 778
OWNER = "CMG"
WARP = (0.07, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 130                # user rule for ~200-id planets: passable provinces outnumber impassable
STRAIGHT = {"citadel"}               # drawn unwarped
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii. The pass is painted before the two halves of
# the range so it cuts through them.
FEATURES = [
    ("Imperial Citadel Ruins", "citadel", CAPITAL, 2, [("ell", 0.19, -0.04, 0.09, 0.09, 0)]),   # by the sea, facing
                                                                          # west into the city (user, 2026-10-14)
    ("Kaas City Ruins", "ruins", CAPITAL, 10, [("ell", 0.0, -0.02, 0.27, 0.21, 0)]),
    # the user (2026-10-14): Kaas City lies by the sea with buildings standing out over the water
    ("Kaas City Sea Quarter", "seacity", CAPITAL, 3, [("ell", 0.33, -0.04, 0.1, 0.15, 0)]),
    ("Dark Temple", "temple", 772, 2, [("ell", -0.55, -0.575, 0.08, 0.07, 0)]),
    ("Dark Temple Pass", "pass", 772, 5, [("cap", -0.73, -0.8, -0.37, -0.35, 0.065)]),
    ("Sith Academy Ruins", "academy", 773, 4, [("ell", -0.47, 0.08, 0.13, 0.1, 15)]),
    ("Dark Force Temple", "forcetemple", 776, 3, [("ell", -0.12, 0.7, 0.08, 0.07, 0)]),
    ("Separatist Base", "base", PORT_STATE, 2, [("ell", 0.46, 0.46, 0.09, 0.08, 0)]),
    ("327th Landing Zone", "landing", PORT_STATE, 5, [("ell", 0.66, 0.6, 0.19, 0.13, 40), ("rect", 0.8, 0.7, 0.2, 0.11, 40)]),
    ("Western Dark Range", "range", 1161, 0, [("cap", -0.98, -0.2, -0.63, -0.5, 0.15), ("ell", -0.8, -0.38, 0.14, 0.2, -40)]),
    ("Eastern Dark Range", "range", 1162, 0, [("cap", -0.47, -0.66, -0.12, -0.95, 0.15), ("ell", -0.3, -0.8, 0.2, 0.13, -40)]),
    ("The Sunken Sea", "sea", 1163, 0, [("ell", 0.55, -0.06, 0.25, 0.36, 10), ("cap", 0.65, 0.0, 1.0, 0.05, 0.18)]),
    ("Southern Mire", "mire", 1164, 0, [("ell", -0.55, 0.6, 0.24, 0.17, 30), ("cap", -0.6, 0.6, -0.9, 0.4, 0.1)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {774: ((0.2, -0.72), "jungle"), 775: ((-0.82, 0.15), "swamp"), 776: ((0.25, 0.76), "swamp"),
         777: ((0.42, 0.22), "swamp"), 773: ((-0.42, -0.12), "jungle")}
STATE_NAMES = {CAPITAL: "Kaas City", 772: "Dark Temple Pass", 773: "Sith Academy Ruins", 774: "Northern Storm Jungle",
               775: "Western Swamps", 776: "Dark Force Swamps", 777: "Eastern Lowlands", PORT_STATE: "Separatist Landing",
               1161: "Western Dark Range", 1162: "Eastern Dark Range", 1163: "The Sunken Sea", 1164: "Southern Mire"}
IMPASSABLE = {1161, 1162, 1163, 1164}
# victory points: (state, feature or kind, name, value). Legends places: Citadel, Kaas City, Dark Temple, Academy,
# Dark Force Temple; Legends battle (327th vs Ventress) with invented site names; invented outposts
VPS = [(CAPITAL, "citadel", CAPITAL_VP, 10), (CAPITAL, "ruins", "Kaas City Ruins", 3),
       (772, "temple", "Dark Temple", 5), (773, "academy", "Sith Academy Ruins", 3),
       (776, "forcetemple", "Dark Force Temple", 5), (PORT_STATE, "base", "Separatist Base", 3),
       (PORT_STATE, "landing", "327th Landing Zone", 2), (774, "jungle", "Storm Jungle Camp", 1),
       (775, "swamp", "Western Swamp Outpost", 1), (777, "swamp", "Lowland Outpost", 1)]
# terrain (planet_terrain_gen.py --planet "Dromund Kaas"; operators: planet_terrain_gen.zone_repaint). Heights in
# heightmap steps above the base; the sea lies under the water plane (~1.3 steps below the base)
DARKROCK = [27, ("ROCK", ">", 0.5), ("GREENMTN", "<", 0.25)]            # 27 = jungle_blend mountain
TERRAIN_CFG = dict(
    seed=89, base=2, rough=2, open=(1, 2, 9, 10),
    zones={  # order = random draw order: keep new zones at the end
        2: dict(relief=("rolling", 6, 6, 6), tex=["JUNGLE", ("JUNGLE2", ">", 0.6), ("DFOREST", "<", 0.2)],
                props=[(82, 0.5), (81, 0.12), (41, 0.08), (46, 0.1)]),   # storm jungle: dense (user, 2026-10-14)
        1: dict(relief=("rolling", 1, 2, None), tex=["WATER", ("JUNGLE2", ">", 0.55), ("JUNGLE", "<", 0.2)],
                props=[(81, 0.28), (83, 0.06), (84, 0.08), (85, 0.1), (47, 0.04), (46, 0.05)]),   # swamp: trees, snags,
                                                                          # root tangles, reeds, fallen trunks
        3: dict(relief=("ramp_top", 14, 3, 10), tex="URBAN", props=[(80, 0.06), (51, 0.02), (82, 0.06), (85, 0.05)]),  # ruins:
                                                                          # urban spawns the ruined city models
        4: dict(relief=("ramp_top", 16, 3, 10), tex=25),
        7: dict(relief=("ramp_top", 10, 3, 6), tex=25, props=[(80, 0.08), (82, 0.08), (85, 0.05)]),
        5: dict(relief=("rolling", 18, 3, None), tex=DARKROCK, props=[(82, 0.1), (51, 0.04)]),   # the pass's trees
        6: dict(relief=("flat", 20), tex=25),
        11: dict(relief=("spires", 20, 8, 0.07, (1.2, 2.8), (30, 70)), tex=DARKROCK),   # jagged dark peaks
        8: dict(relief=("flat", 4), tex=25, props=[(80, 0.1)]),
        9: dict(relief=("flat", 3), tex=25),
        10: dict(relief=("flat", 3), tex=25),
        12: dict(relief=("flat", -5), tex="WATER"),                       # the sunken sea: under the water plane
        13: dict(relief=("rolling", -2.5, 2.5, 4), tex="WATER",
                 props=[(81, 0.12), (83, 0.14), (84, 0.08), (47, 0.05)]),   # drowned forest: snags, roots
        14: dict(relief=("flat", -2), tex=30),                            # the sea quarter: sea_town_30 = marsh water
                                                                          # that spawns city models (ruins in the sea)
    },
    steep=("ROCK", 7, (1, 2, 5)),
    city={3: 16, 14: 16},       # map/cities.txt group 16: Kaas City's ruins (user: a ruined city DOES get city models)
    prop_clear=1.2,             # trees close round the unit positions, as vanilla forests do (user: "a lot of trees")
)
# models (military_buildings.py place "Dromund Kaas"): (mesh, scale, where), placed in this order. Big, custom
# (user rule 2026-10-14): the Citadel ruin over the plateau's heart, the Dark Temple filling its pass
PLACEMENT = dict(
    new_models={"hod_dk_citadel", "hod_dk_dark_temple"},
    items=[("hod_dk_citadel", 1.0, ("zone_centre", 4)),
           ("hod_dk_dark_temple", 1.0, ("zone_centre", 6))],
    clear={"hod_dk_citadel": 9.0},     # no ruined towers growing through the citadel
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (dromund_kaas_map.py)\n{imp}"
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
