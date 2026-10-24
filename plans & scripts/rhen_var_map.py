"""Rhen Var, the frozen world of ruins, as one battlefield at the start (976, before the Clone Wars) (research:
WIPGFX/research/rhen_var/). LEGENDS: once "a fertile paradise", then an ice age: "a civilization flourished, building
castles, fortresses and temples; eventually it went extinct due to the advance of a planetary ice age ... and snow
engulfed the ruins"; glaciers, snow-covered mountains; Rhen Var Harbor ("an ancient location ... in use before the
planet was plunged into an ice-age") and the Rhen Var Citadel (Star Wars: Battlefront); the Jedi monument, "an old
Jedi temple" and the burial site of Ulic Qel-Droma; Darth Mekhis' fortress from the Great Galactic War; the Forgotten
Rakatan Temple; Bravo Base, a Republic military facility (it falls in the war's first month, so it stands at the
start). CANON: frigid. Owner at the start: the Republic. Out-of-universe: McQuarrie's Hoth concept art of ruins
emerging from the snow.
LAYOUT IS A DESIGN CHOICE (the sources place nothing): a frozen sea from the west rim with the Harbor on its shore, the
Rhen Var Range across the north with the Citadel below it, the Great Glacier in the east, an ice canyon cut to the south
rim, Bravo Base on a central plateau, the Jedi monument in the south-west, Mekhis' fortress in the north-east highlands,
the Rakatan temple in the south-east. Invented names: the state names, the sea, glacier, range and canyon, two VPs.
    python "WIPGFX/plans & scripts/rhen_var_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/rhen_var_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 200 province ids are kept (strategic region unchanged); only the pixels move.
Run order: rhen_var_map.py -> planet_terrain_gen.py --planet "Rhen Var" -> military_buildings.py models hod_rhen
-> military_buildings.py place "Rhen Var" -> rhen_var_fx.py -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py
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

PLANET = "Rhen Var"
ZONES_JSON = "WIPGFX/Assets/rhen_var_zones.json"
ZONES_PNG = "WIPGFX/Assets/rhen_var_zones.png"
KIND = {"tundra": 1, "highland": 2, "base": 3, "harbor": 4, "citadel": 5, "monument": 6, "fortress": 7, "rakata": 8,
        "ruins": 9, "sea": 10, "glacier": 11, "range": 12, "canyon": 13}
TERRAIN = {"tundra": "plains", "highland": "hills", "base": "urban", "harbor": "urban", "citadel": "hills",
           "monument": "hills", "fortress": "hills", "rakata": "hills", "ruins": "hills", "sea": "marsh",
           "glacier": "mountain", "range": "mountain", "canyon": "mountain"}
SEED = 82
CAPITAL = 82
CAPITAL_VP = "Bravo Base"
PORT_STATE = 727
OWNER = "REP"
WARP = (0.12, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 130                # user rule (~200-id planets): passable provinces outnumber impassable
STRAIGHT = {"base", "harbor", "citadel", "monument", "fortress", "rakata", "ruins"}   # the sites drawn unwarped
# features painted in order (the sea first among the impassable: it takes the leftover ids), the first to claim a
# pixel keeps it: (name, kind, state, provinces or 0 = by area, shapes); shapes as korriban_map.shape, u east, v south
FEATURES = [
    ("Bravo Base", "base", CAPITAL, 2, [("ell", 0.14, 0.08, 0.1, 0.09, 0)]),
    ("Rhen Var Harbor", "harbor", 727, 3, [("ell", -0.3, -0.02, 0.1, 0.13, 0)]),
    ("Rhen Var Citadel", "citadel", 728, 2, [("ell", 0.02, -0.46, 0.1, 0.08, 0)]),
    ("Jedi Monument", "monument", 729, 1, [("ell", -0.45, 0.62, 0.08, 0.07, 0)]),
    ("Mekhis' Fortress", "fortress", 730, 1, [("ell", 0.58, -0.42, 0.08, 0.07, 0)]),
    ("Forgotten Rakatan Temple", "rakata", 731, 1, [("ell", 0.42, 0.7, 0.08, 0.07, 0)]),
    ("Northern Ruins", "ruins", 732, 1, [("ell", -0.12, -0.9, 0.07, 0.05, 0)]),
    ("Glacier Watch", "ruins", 733, 1, [("ell", 0.5, 0.28, 0.07, 0.06, 0)]),
    ("Frozen Sea", "sea", 1186, 0, [("ell", -0.78, 0.15, 0.3, 0.42, 0), ("cap", -0.6, 0.0, -0.4, 0.02, 0.1),
                                    ("ell", -0.62, 0.48, 0.16, 0.12, 25)]),
    ("Great Glacier", "glacier", 1187, 0, [("ell", 0.8, 0.02, 0.2, 0.34, 0), ("cap", 0.8, 0.0, 0.62, -0.05, 0.08)]),
    ("Rhen Var Range", "range", 1188, 0, [("cap", -0.55, -0.66, 0.0, -0.7, 0.12), ("cap", 0.0, -0.7, 0.5, -0.62, 0.11),
                                         ("ell", -0.25, -0.58, 0.12, 0.08, 15), ("ell", 0.3, -0.55, 0.1, 0.07, -20)]),
    ("Ice Canyon", "canyon", 1189, 0, [("cap", 0.32, 0.46, 0.12, 0.72, 0.055), ("cap", 0.12, 0.72, 0.0, 1.05, 0.06)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.12, 0.12), "tundra"), 727: ((-0.3, -0.22), "tundra"), 728: ((0.0, -0.42), "highland"),
         729: ((-0.42, 0.62), "tundra"), 730: ((0.6, -0.4), "highland"), 731: ((0.45, 0.7), "tundra"),
         732: ((-0.1, -0.9), "tundra"), 733: ((0.5, 0.3), "tundra")}
STATE_NAMES = {CAPITAL: "Bravo Plateau", 727: "Harbor Coast", 728: "Citadel Heights", 729: "Qel-Droma's Rest",
               730: "Mekhis Highlands", 731: "Rakatan Wastes", 732: "Northern Tundra", 733: "Glacier Fields",
               1186: "Frozen Sea", 1187: "Great Glacier", 1188: "Rhen Var Range", 1189: "Ice Canyon"}
IMPASSABLE = {1186, 1187, 1188, 1189}
# victory points: (state, feature or kind, name, value). Legends: Bravo Base, the Harbor, the Citadel, the Jedi
# monument, Mekhis' fortress, the Rakatan temple; invented: the last two
VPS = [(CAPITAL, "base", CAPITAL_VP, 10), (727, "harbor", "Rhen Var Harbor", 5), (728, "citadel", "Rhen Var Citadel", 5),
       (729, "monument", "Jedi Monument", 3), (730, "fortress", "Ruins of Mekhis' Fortress", 2),
       (731, "rakata", "Forgotten Rakatan Temple", 2), (732, "ruins", "Northern Ruins", 1),
       (733, "ruins", "Glacier Watch", 1)]


# terrain (planet_terrain_gen.py --planet "Rhen Var"; operators: planet_terrain_gen.zone_repaint). Legends: frozen
# tundra, glaciers, snow-covered mountains over the ruins; the frozen sea kept level (level), the ice canyon cut deep
# (canyon hook); the far look (colors): snow white, blue-grey rock, pale blue ice


def canyon(ctx):
    """the Ice Canyon: cut down from the tundra in sheer benches to a floor just above the water plane"""
    z, rel, rough = ctx["z"], ctx["rel"], ctx["rough"]
    m = ctx["sub"] & (z == 13)
    d = ndi.distance_transform_edt(m)
    ctx["rel"] = np.where(m, np.maximum(0.5, 12 + 2 * rough - 4.0 * np.floor(d / 0.9)), rel)


TERRAIN_CFG = dict(
    seed=82, base=5, rough=2, open=(1, 2),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 4, 4, 6), tex=["SNOWSAND", ("SNOWFARM", ">", 0.6), ("SNOWROCK", "<", 0.12)],   # tundra
                props=[(113, 0.06), (114, 0.04), (115, 0.03)]),
        2: dict(relief=("rolling", 8, 7, 4), tex=["SNOWROCK", ("SNOWSAND", ">", 0.6)],                          # highlands
                props=[(113, 0.1), (115, 0.04), (114, 0.03)]),
        3: dict(relief=("flat", 7), tex="URBAN"),                                                   # Bravo Base
        4: dict(relief=("ramp_top", 5, 3, 4), tex="URBAN", props=[(114, 0.06)]),                    # the Harbor
        5: dict(relief=("ramp_top", 12, 5, 4), tex=["SNOWROCK", (25, ">", 0.5)]),                    # the Citadel's crag
        6: dict(relief=("flat", 6), tex=25, props=[(114, 0.08)]),                                   # the Jedi monument
        7: dict(relief=("ramp_top", 11, 5, 3), tex="SNOWROCK", props=[(113, 0.08)]),                # Mekhis' fortress
        8: dict(relief=("flat", 6), tex=["SNOWSAND", (25, ">", 0.5)], props=[(114, 0.06)]),          # the Rakatan temple
        9: dict(relief=("rolling", 5, 2, 5), tex="URBAN", props=[(114, 0.08)]),                     # ruin sites
        10: dict(relief=("flat", 1), tex="SNOWSAND", props=[(113, 0.04)]),                          # the frozen sea
        11: dict(relief=("mesa", 6, 18, 2.0, (4, 0.6)), tex=["SNOWSAND", ("SNOWROCK", ">", 0.6)],     # the glacier
                 props=[(113, 0.08)]),
        12: dict(relief=("spires", 16, 9, 0.08, (1.5, 3.0), (24, 48)), tex=["SNOWROCK", ("ROCK", ">", 0.7)]),
        13: dict(tex=["SNOWROCK", ("ROCK2", ">", 0.55)]),                                            # Ice Canyon (hook)
    },
    steep=("SNOWROCK", 7, (1, 2)),
    city={3: 27, 4: 26, 9: 26},   # map/cities.txt 26: frozen ruins, 27: Bravo Base (military_buildings.py rh_ruins, rh_prefab)
    prop_clear=1.8,
    hook=canyon,
    level=(10,),
    colors={1: (0.88, 0.9, 0.93), 2: (0.74, 0.77, 0.82), 3: (0.8, 0.8, 0.8), 4: (0.7, 0.72, 0.76), 5: (0.66, 0.68, 0.72),
            6: (0.8, 0.82, 0.86), 7: (0.5, 0.5, 0.55), 8: (0.6, 0.64, 0.64), 9: (0.74, 0.76, 0.8), 10: (0.7, 0.82, 0.92),
            11: (0.84, 0.92, 0.98), 12: (0.62, 0.66, 0.72), 13: (0.46, 0.5, 0.58)},
)
# models (military_buildings.py place "Rhen Var"): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_rh_citadel", "hod_rh_harbor", "hod_rh_monument", "hod_rh_bravo", "hod_rh_mekhis", "hod_rh_rakata"},
    items=[("hod_rh_bravo", 1.0, ("at_vp", CAPITAL_VP)), ("hod_rh_harbor", 1.0, ("at_vp", "Rhen Var Harbor")),
           ("hod_rh_citadel", 1.0, ("at_vp", "Rhen Var Citadel")), ("hod_rh_monument", 0.9, ("at_vp", "Jedi Monument")),
           ("hod_rh_mekhis", 0.9, ("at_vp", "Ruins of Mekhis' Fortress")),
           ("hod_rh_rakata", 0.9, ("at_vp", "Forgotten Rakatan Temple"))],
    clear={"hod_rh_bravo": 6.0, "hod_rh_harbor": 6.5, "hod_rh_citadel": 5.5, "hod_rh_monument": 4.5,
           "hod_rh_mekhis": 4.0, "hod_rh_rakata": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (rhen_var_map.py)\n{imp}"
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
