"""Telos IV, the city-world of the Kwymar sector, as one battlefield before the Clone Wars (research:
WIPGFX/research/telos_iv/). CANON: temperate; cityscape, beaches, canyons, forest, gorges, grasslands, hills, mountains,
polar region; 500 million to a billion people; bombed by Malak's fleet in 3958 BBY and brought back by the Telosian
Restoration Project (Restoration Zones, the first RZ-0031); the Park of Sacred Pools fed by an underground spring; the
Mirror Caverns, malab-lined caves in a forest glade high in snow-capped stone mountains; Ithorian blba trees and
bachani flowers; Thani the capital, seat of the Telosian Council and the Governor. LEGENDS: the Thani Terminal and the
Chodo Habat Parkway in Thani; the Telosian Jedi Academy (Telos Polar Academy) of Atris hidden in the polar ice.
Owner: CIS (Separatist space in the Clone Wars).
User (2026-10-19): Telos is almost entirely a city: every passable state is urban; the only open ground left is the
Academy's snowfield, the Caverns' glade and the RZ-0031 park round the Sacred Pools, kept as reserves inside the city.
LAYOUT IS A DESIGN CHOICE (the sources place nothing): the polar ice cap over the north rim (impassable) with the
Academy at its southern edge, the Mirror Mountains in the north-west (impassable) with the Caverns' glade cut into
their eastern flank, Thani's towers in the centre with the Terminal at their east side, industrial arcologies to the
north, lakeside districts east, RZ-0031 and the Sacred Pools on the south-east coast of the Kwymar Sea (impassable),
the docks in the south where the naval base sits.
Canon names: Thani, RZ-0031, the Park of Sacred Pools, the Mirror Caverns. Legends: the Thani Terminal, the Telos Polar
Academy. Invented: every state name, the Telosian Lakes VP, the Mirror Mountains, the Polar Ice Cap, the Kwymar Sea.
    python "WIPGFX/plans & scripts/telos_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/telos_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 198 province ids are kept (strategic region unchanged); only the pixels move.
Run order: telos_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (tel_*) ->
planet_terrain_gen.py --planet Telos -> military_buildings.py models hod_tel -> military_buildings.py place Telos ->
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

PLANET = "Telos"
ZONES_JSON = "WIPGFX/Assets/telos_zones.json"
ZONES_PNG = "WIPGFX/Assets/telos_zones.png"
KIND = {"metro": 1, "sprawl": 2, "city": 3, "port": 4, "pool": 5, "glade": 6, "academy": 7, "industry": 8,
        "park": 9, "icecap": 10, "mountains": 11, "sea": 12}
TERRAIN = {"metro": "urban", "sprawl": "urban", "city": "urban", "port": "urban", "pool": "marsh", "glade": "forest",
           "academy": "hills", "industry": "urban", "park": "forest", "icecap": "mountain", "mountains": "mountain",
           "sea": "mountain"}
SEED = 789
CAPITAL = 789
CAPITAL_VP = "Thani"
PORT_STATE = 791
OWNER = {s: "CIS" for s in (91, 786, 787, 788, 789, 790, 791, 1203, 1204, 1205)}
WARP = (0.13, 9)
TARGET_PASSABLE = 132                # user rule: passable provinces outnumber impassable (~132 / 66)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Thani", "city", CAPITAL, 5, [("ell", 0.0, 0.08, 0.17, 0.12, -10)]),
    ("Thani Terminal", "port", CAPITAL, 1, [("ell", 0.2, 0.0, 0.07, 0.06, 0)]),
    ("Telos Polar Academy", "academy", 786, 2, [("ell", 0.22, -0.68, 0.11, 0.07, 0)]),
    ("Mirror Caverns", "glade", 787, 2, [("ell", -0.42, -0.4, 0.1, 0.08, 30)]),
    ("Park of Sacred Pools", "pool", 788, 2, [("ell", 0.2, 0.66, 0.08, 0.06, 0), ("cap", 0.12, 0.6, 0.32, 0.72, 0.03)]),
    ("RZ-0031", "park", 788, 4, [("ell", 0.3, 0.5, 0.17, 0.13, 30)]),
    # deep lakes among the eastern districts (the water tile)
    ("Telosian Lakes", "pool", 790, 3, [("ell", 0.6, -0.15, 0.1, 0.06, 20), ("ell", 0.72, 0.08, 0.07, 0.05, -30),
                                         ("cap", 0.6, -0.15, 0.72, 0.08, 0.025)]),
    # the impassable rim: ice cap over the north, the Mirror Mountains in the north-west, the sea in the south-east
    ("Polar Ice Cap", "icecap", 1203, 0, [("ell", 0.0, -1.0, 0.85, 0.3, 0), ("cap", -0.3, -0.78, 0.15, -0.8, 0.05),
                                          ("cap", 0.4, -0.8, 0.6, -0.7, 0.05)]),
    ("Mirror Mountains", "mountains", 1204, 0, [("cap", -0.95, 0.0, -0.62, -0.62, 0.15), ("cap", -0.62, -0.62, -0.35, -0.85, 0.12),
                                                ("cap", -0.7, -0.3, -0.42, -0.5, 0.06), ("cap", -0.85, -0.1, -0.6, -0.08, 0.05)]),
    ("Kwymar Sea", "sea", 1205, 0, [("ell", 0.66, 0.74, 0.3, 0.17, -40), ("cap", 0.95, 0.3, 0.7, 0.7, 0.08),
                                    ("cap", 0.5, 0.82, 0.3, 0.98, 0.07)]),
]
# open ground (here: the city): each pixel to the nearest region seed (u, v), in warped space so the borders come out
# ragged
SEEDS = {CAPITAL: ((0.0, 0.05), "metro"), 786: ((0.05, -0.55), "industry"), 787: ((-0.4, -0.15), "sprawl"),
         788: ((0.4, 0.4), "sprawl"), 790: ((0.6, -0.2), "metro"), 791: ((-0.3, 0.6), "industry"),
         91: ((-0.7, 0.25), "sprawl")}
STATE_NAMES = {CAPITAL: "Thani", 786: "Northern Arcologies", 787: "Mirror Terraces", 788: "Restoration Zone 31",
               790: "Lakeside Districts", 791: "Southern Docks", 91: "Western Districts",
               1203: "Polar Ice Cap", 1204: "Mirror Mountains", 1205: "Kwymar Sea"}
IMPASSABLE = {1203, 1204, 1205}
VPS = [(CAPITAL, "Thani", CAPITAL_VP, 10), (CAPITAL, "Thani Terminal", "Thani Terminal", 3),
       (786, "Telos Polar Academy", "Telos Polar Academy", 3), (787, "Mirror Caverns", "Mirror Caverns", 2),
       (788, "RZ-0031", "RZ-0031", 2), (788, "Park of Sacred Pools", "Park of Sacred Pools", 2),
       (790, "Telosian Lakes", "Telosian Lakes", 1), (791, "industry", "Southern Docks", 2),
       (91, "sprawl", "Western Districts", 1), (786, "industry", "Northern Arcologies", 1)]

# terrain (planet_terrain_gen.py --planet Telos). Heights in heightmap steps above the base. The user's Telos: a
# city to the horizon (map/cities.txt 35, military_buildings.py tel_city); green reserves of Ithorian blba trees and
# blue-lavender bachani flowers (flora_props 131, 132); snow-capped stone mountains; the polar ice; lakes and the sea
# are the water tile and every shore rises out of it
TERRAIN_CFG = dict(
    seed=789, base=4, rough=2, open=(1, 2, 8),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 4, 1.5, 6), tex="URBAN"),                                     # Thani's districts
        2: dict(relief=("rolling", 6, 2.5, 5), tex="URBAN", props=[(131, 0.02)]),               # residential sprawl
        3: dict(relief=("ramp_top", 6, 4, 4), tex="URBAN"),                                      # Thani's towers
        4: dict(relief=("flat", 4), tex="URBAN"),                                                # the Terminal
        5: dict(relief=("flat", 0.3), tex="WATER"),                                              # lakes, the pools
        6: dict(relief=("rolling", 9, 6, 4), tex=["GRASSHILL", ("FOREST", ">", 0.45)],
                props=[(131, 0.3), (132, 0.08)]),                                                # the Caverns' glade
        7: dict(relief=("flat", 6), tex=["SNOWSAND", ("SNOWROCK", ">", 0.7)]),                   # the Academy's snowfield
        8: dict(relief=("flat", 4), tex="URBAN"),                                                # arcologies, docks
        9: dict(relief=("rolling", 4, 3, 5), tex=["GRASS", ("GRASSHILL", ">", 0.6)],
                props=[(132, 0.22), (131, 0.14)], clusters=[(7, 0.6, [(131, 0.5)])]),          # the RZ-0031 reserve
        10: dict(relief=("mesa", 6, 18, 2.0, (4, 0.6)), tex=["SNOWSAND", ("SNOWROCK", ">", 0.6)]),          # ice cap
        11: dict(relief=("spires", 16, 9, 0.08, (1.5, 3.0), (24, 48)), tex=["ROCK", ("SNOWROCK", ">", 0.45)]),
        12: dict(relief=("flat", 0.3), tex="WATER"),                                             # the Kwymar Sea
    },
    steep=("ROCK", 6, (6, 11)),
    city={1: 35, 2: 35, 3: 35, 4: 35, 8: 35},   # map/cities.txt 35: Telos's city (military_buildings.py tel_city)
    prop_clear=1.5,
    landforms=dict(amp=0, hills=0, skirt_k=0),
    shore_rise=(4, 2.0),
)

# models (military_buildings.py place Telos): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_tel_thani", "hod_tel_terminal", "hod_tel_academy", "hod_tel_caverns", "hod_tel_rz"},
    items=[("hod_tel_thani", 1.0, ("at_vp", CAPITAL_VP)), ("hod_tel_terminal", 1.0, ("at_vp", "Thani Terminal")),
           ("hod_tel_academy", 1.0, ("at_vp", "Telos Polar Academy")), ("hod_tel_caverns", 1.0, ("at_vp", "Mirror Caverns")),
           ("hod_tel_rz", 1.0, ("at_vp", "RZ-0031"))],
    clear={"hod_tel_thani": 6.5, "hod_tel_terminal": 5.0, "hod_tel_academy": 5.0, "hod_tel_caverns": 4.5, "hod_tel_rz": 5.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (telos_map.py)\n{imp}"
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
