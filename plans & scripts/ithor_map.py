"""Ithor, the Ithorians' sacred jungle world, as one battlefield before the Clone Wars (research: WIPGFX/research/ithor/;
Legends first, user 2026-10-20). LEGENDS: one of the oldest Republic members, "a planet full of lush life" whose
surface "had not a touch of civilization on it"; the Ithorians live in great floating herdship cities above it
(Tafanda Bay the capital, Tree of Tarintha, Cloud-Mother with the House of the Healers), entry to the sacred surface,
the Mother Jungle, forbidden by the Law of Life; five continents, three explored and harvested, two never touched;
the sentient bafforr forests (the Cathor Hills); the Falls of Dessiar, renowned for their beauty and peace; a humid
world of rainforest; loyal to the Republic in the Clone Wars. CANON adds the n'lor and carnivorous johinuu trees,
green and rust-hued bushes, carpets of blue and pink fungi. Owner: REP (as before).
LOOK, THE USER'S CHOICE (2026-10-20): "herdships 3d models, all over a clouds terrain": the map is a sea of clouds the
herdships float over, the jungle showing through its gaps; the two untouched continents rise as forbidden jungle
(impassable, new states 1255 and 1256). LAYOUT IS A DESIGN CHOICE: Tafanda Bay over the centre, Tree of Tarintha in
the north-east, Cloud-Mother in the south, the Cathor Hills in the east and the Falls of Dessiar in the north where the
cloud breaks, the Mother Jungle over the west, the Holy Mother's Reach in the south-east.
Legends names: Tafanda Bay, Tree of Tarintha, Cloud-Mother, the House of the Healers, the Cathor Hills, the Falls of
Dessiar, the Mother Jungle. Invented: the Holy Mother's Reach, the Herdlands, the Eastern, Northern and Western
Cloudseas as state names.
    python "WIPGFX/plans & scripts/ithor_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ithor_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 207 province ids are kept (strategic region unchanged); only the pixels move.
Run order: ithor_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (ith_*) ->
planet_terrain_gen.py --planet Ithor -> military_buildings.py models hod_ith -> military_buildings.py place Ithor ->
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

PLANET = "Ithor"
ZONES_JSON = "WIPGFX/Assets/ithor_zones.json"
ZONES_PNG = "WIPGFX/Assets/ithor_zones.png"
KIND = {"herd": 1, "lane": 2, "forest": 3, "falls": 4, "cloud": 5}
TERRAIN = {"herd": "clouds", "lane": "clouds", "forest": "forest", "falls": "hills", "cloud": "clouds"}
SEED = 102
CAPITAL = 102
CAPITAL_VP = "Tafanda Bay"
PORT_STATE = 847                     # Tafanda Bay floats inland: the fleet lies off the north
OWNER = {s: "REP" for s in (102, 844, 845, 846, 847, 848, 849, 850, 1255, 1256, 1263, 1264, 1265)}
WARP = (0.1, 9)
TARGET_PASSABLE = 110                # passable provinces outnumber impassable (~110 / 97), though the clouds cover most of
                                     # the area: the lanes' provinces are small, the cloud banks' big
STRAIGHT = set()
LANE_W = 0.06                        # sky-lane half width, planet radii


def _lane(*pts):
    return [("cap", *a, *b, LANE_W) for a, b in zip(pts, pts[1:])]


# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii. The herd stations and the cloud breaks first,
# then the sky-lanes between them; everything left is cloud (impassable)
_T, _R, _C, _H = (0.0, -0.1), (0.5, -0.5), (-0.1, 0.55), (0.72, 0.15)
_F, _S, _W = (-0.45, -0.6), (0.38, 0.48), (-0.66, 0.08)
FEATURES = [
    ("Tafanda Bay", "herd", CAPITAL, 3, [("ell", *_T, 0.13, 0.1, 10)]),
    ("Tree of Tarintha", "herd", 844, 2, [("ell", *_R, 0.1, 0.08, -20)]),
    ("Cloud-Mother", "herd", 845, 2, [("ell", *_C, 0.11, 0.08, 15)]),
    ("Cathor Hills", "forest", 846, 2, [("ell", *_H, 0.1, 0.13, 0)]),
    ("Falls of Dessiar", "falls", 847, 1, [("ell", *_F, 0.08, 0.07, 0)]),
    ("Herd Crossing", "herd", 848, 1, [("ell", *_S, 0.07, 0.06, 0)]),
    ("Western Herd Station", "herd", 850, 1, [("ell", *_W, 0.07, 0.06, 0)]),
    ("Falls Skylane", "lane", 847, 0, _lane(_T, (-0.25, -0.3), _F)),
    ("Tarintha Skylane", "lane", 844, 0, _lane(_T, (0.28, -0.22), _R)),
    ("Eastern Skylane", "lane", 849, 0, _lane(_R, (0.72, -0.2), _H)),
    ("Cathor Skylane", "lane", 846, 0, _lane(_H, (0.6, 0.38), _S)),
    ("Crossing Skylane", "lane", 848, 0, _lane(_S, (0.12, 0.62), _C)),
    ("Mother Skylane", "lane", 845, 0, _lane(_T, (-0.12, 0.22), _C)),
    ("Western Skylane", "lane", 850, 0, _lane(_C, (-0.45, 0.4), _W, (-0.65, -0.3), _F)),
    # the lanes out to space (Legends: the herds moved into the skies "and eventually out into space"): the fleet's
    # and the hyperlanes' landings on the planet's edge
    ("Northern Spacelane", "lane", 847, 0, _lane(_F, (-0.52, -0.82), (-0.56, -1.05))),
    ("Eastern Spacelane", "lane", 846, 0, _lane(_H, (0.9, 0.22), (1.08, 0.24))),
    ("Southern Spacelane", "lane", 845, 0, _lane(_C, (-0.12, 0.8), (-0.14, 1.08))),
]
# the cloud left between the lanes: each separate bank its own impassable state, named by the anchor nearest its middle
CLOUD_BANKS = {1255: (0.45, -0.75), 1264: (0.6, 0.72), 1265: (-0.8, 0.1), 1256: (0.35, 0.05), 1263: (-0.35, -0.05)}
CLOUD_STATES = list(CLOUD_BANKS)
SEEDS = {}
STATE_NAMES = {CAPITAL: "Tafanda Bay", 844: "Tree of Tarintha", 845: "Cloud-Mother", 846: "Cathor Hills",
               847: "Falls of Dessiar", 848: "Herd Crossing", 849: "Eastern Skylane", 850: "Western Herd Station",
               1255: "Northern Cloudsea", 1256: "Eastern Cloud Deck", 1263: "Western Cloud Deck",
               1264: "Southern Cloudsea", 1265: "Western Cloudsea"}
IMPASSABLE = set(CLOUD_STATES)
VPS = [(CAPITAL, "Tafanda Bay", CAPITAL_VP, 10), (844, "Tree of Tarintha", "Tree of Tarintha", 5),
       (845, "Cloud-Mother", "Cloud-Mother", 5), (846, "Cathor Hills", "Cathor Hills", 2),
       (847, "Falls of Dessiar", "Falls of Dessiar", 2), (848, "Herd Crossing", "Herd Crossing", 1),
       (849, "Eastern Skylane", "Eastern Skylane", 1), (850, "Western Herd Station", "Western Herd Station", 1)]

# terrain (planet_terrain_gen.py --planet Ithor). Heights in heightmap steps above the base. The clouds terrain (graphical
# terrain CLOUDS = 35, atlas slot 21, terrain_atlas.py clouds; the clouds category): the impassable cloud banks heaped
# high, the sky-lanes lower channels through them where the jungle shows in patches far below, the herd stations level
# decks of cloud under the herdships; the cloud breaks over the Cathor Hills (185 n'lor trees, 187 fungus) and the
# Falls of Dessiar. No 3D clouds (the user, 2026-10-20), no ground towns (the surface is sacred)
TERRAIN_CFG = dict(
    seed=102, base=4, rough=2, open=(1, 2, 3),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("flat", 6), tex="CLOUDS"),                                                 # herd stations
        2: dict(relief=("rolling", 4, 1.5, 6), tex=["CLOUDS", ("JUNGLE", ">", 0.62)]),             # the sky-lanes
        3: dict(relief=("rolling", 9, 6, 4), tex=["JUNGLE", ("JUNGLE2", ">", 0.5)],
                props=[(185, 0.55), (187, 0.2)]),                                                  # Cathor Hills
        4: dict(relief=("ramp_top", 12, 6, 3), tex=["JUNGLE", ("WATER", ">", 0.55), ("ROCK", ">", 0.85)],
                props=[(185, 0.25)]),                                                              # the falls
        5: dict(relief=("rolling", 14, 8, 5), tex="CLOUDS"),                                       # the cloud banks
    },
    steep=("CLOUDS", 99, (2,)),
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.93, 0.94, 0.97), 2: (0.78, 0.84, 0.82), 3: (0.18, 0.4, 0.2), 4: (0.22, 0.42, 0.3),
            5: (0.94, 0.95, 0.98)},
)

# models (military_buildings.py place Ithor): big, custom (user rule 2026-10-14); the herdships float over the cloud
PLACEMENT = dict(
    new_models={"hod_ith_tafanda", "hod_ith_tarintha", "hod_ith_cloudmother", "hod_ith_falls"},
    items=[("hod_ith_tafanda", 1.0, ("at_vp", CAPITAL_VP)), ("hod_ith_tarintha", 1.0, ("at_vp", "Tree of Tarintha")),
           ("hod_ith_cloudmother", 1.0, ("at_vp", "Cloud-Mother")), ("hod_ith_falls", 1.0, ("at_vp", "Falls of Dessiar"))],
    clear={"hod_ith_tafanda": 9.0, "hod_ith_tarintha": 7.5, "hod_ith_cloudmother": 7.5, "hod_ith_falls": 5.0},
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
    """feature index per pixel and features [(name, kind, state, provinces)]: FEATURES in order (the herd stations,
    cloud breaks and sky-lanes), then each cloud bank left between them a cloud state, the biggest first"""
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
    comp, n = ndi.label(sm & (fid < 0))                                 # the cloud banks the lanes leave
    sizes = np.bincount(comp.ravel())[1:]
    assert n >= len(CLOUD_STATES), f"only {n} cloud banks for {len(CLOUD_STATES)} cloud states"
    free_banks = dict(CLOUD_BANKS)
    for j, ci in enumerate(np.argsort(-sizes)):
        frag = comp == ci + 1
        if j < len(CLOUD_STATES):                                       # the bank's state: the nearest free anchor
            mu, mv = U0[frag].mean(), V0[frag].mean()
            sid = min(free_banks, key=lambda b: math.hypot(free_banks[b][0] - mu, free_banks[b][1] - mv))
            del free_banks[sid]
            feats.append((STATE_NAMES[sid], "cloud", sid, 0))
            fid[frag] = len(feats) - 1
        else:                                                           # a scrap pinched off between lanes: joins the
            ring = ndi.binary_dilation(frag) & ~frag & sm               # lane or station it borders most
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ithor_map.py)\n{imp}"
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
