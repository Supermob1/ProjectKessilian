"""Carida, the Republic's military academy world, as one battlefield before the Clone Wars (research: WIPGFX/research/carida/;
Legends first, canon where Legends is silent; the user, 2026-10-21: the Legends academy world). LEGENDS: forests, deserts,
a glacier, jungles and arctic tundra, a temperate high-gravity world, the perfect training ground for combat in
difficult terrain; the Academy of Carida on the Spinara Plateau, the Caridan district just outside it with its booming
nightlife, the Dean's Residence; Tarkin's Teeth, mountainous and desolate, a training ground for centuries; the
Forgofshar Desert used for survival training; the Ressl River; the Carida Corsairs' old base (raided the Perlemian, found
out before the Galactic War). CANON: two suns over mostly barren mountains; the Republic space station Valor in orbit
during the Clone Wars. Owner: REP (as before).
LAYOUT IS A DESIGN CHOICE beyond the stated relationships: the Spinara Plateau in the middle with the Academy on it and
the Caridan district at its southern foot, the Academy's landing field on the northern coast (the Yinchorr lane); the
Teeth east, the Forgofshar Desert south-west (the Alderaan lane), the Ressl River valley south-east, the tundra north-west
with the Corsairs' ruined base; the Ice Cap (impassable glacier) across the north-west, the Teeth peaks (impassable) in
the east, the Southern Ranges (impassable) between the desert and the river; Valor in orbit north-east of the disc.
Names from the sources: Academy of Carida, Spinara Plateau, Caridan District, Tarkin's Teeth, Forgofshar Desert, Ressl
River, Carida Corsairs' Base, Valor. Invented: Academy Landing Field, Forgofshar Survival Camp, Teeth Training Ground,
Ressl Valley, Caridan Tundra, the Ice Cap, the Teeth Peaks, the Southern Ranges.
    python "WIPGFX/plans & scripts/carida_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/carida_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 62 province ids are kept (strategic region unchanged); only the pixels move.
Run order: carida_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (car_*) ->
planet_terrain_gen.py --planet Carida -> military_buildings.py carida_atlas, models hod_car_ -> coruscant_buildings.py wire ->
military_buildings.py place Carida -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Carida"
ZONES_JSON = "WIPGFX/Assets/carida_zones.json"
ZONES_PNG = "WIPGFX/Assets/carida_zones.png"
KIND = {"academy": 1, "district": 2, "camp": 3, "ruins": 4, "plateau": 5, "desert": 6, "tundra": 7, "teeth": 8,
        "valley": 9, "glacier": 10, "peaks": 11, "ranges": 12, "field": 13}
TERRAIN = {"academy": "urban", "district": "urban", "camp": "hills", "ruins": "plains", "plateau": "hills",
           "desert": "desert", "tundra": "plains", "teeth": "mountain", "valley": "forest", "glacier": "mountain",
           "peaks": "mountain", "ranges": "mountain", "field": "plains"}
SEED = 164
CAPITAL = 164
CAPITAL_VP = "Academy of Carida"
CORE = "REP"
PORT_STATE = 164                     # the Academy's landing field on the northern coast
OWNER = {s: "REP" for s in (7, 162, 163, 164, 165, 1312, 1313, 1314)}
WARP = (0.12, 9)
TARGET_PASSABLE = 40                 # user rule: passable provinces outnumber impassable (~40 / 22)
STRAIGHT = {"academy", "field"}
FEATURES = [
    ("Academy of Carida", "academy", CAPITAL, 2, [("rect", 0.0, -0.18, 0.16, 0.12, 8)]),
    ("Caridan District", "district", CAPITAL, 1, [("ell", 0.04, 0.05, 0.11, 0.07, -10)]),
    ("Academy Landing Field", "field", CAPITAL, 1, [("rect", -0.1, -0.86, 0.13, 0.16, 0)]),
    ("Teeth Training Ground", "camp", 162, 1, [("ell", 0.45, 0.02, 0.09, 0.08, 20)]),
    ("Forgofshar Survival Camp", "camp", 7, 1, [("ell", -0.42, 0.42, 0.08, 0.07, 0)]),
    ("Carida Corsairs' Base", "ruins", 165, 1, [("ell", -0.42, -0.2, 0.08, 0.07, 30)]),
    ("Ressl River", "valley", 163, 2, [("cap", 0.12, 0.25, 0.42, 0.75, 0.08), ("cap", 0.42, 0.75, 0.55, 0.85, 0.06)]),
    ("Ice Cap", "glacier", 1313, 0, [("ell", -0.55, -0.62, 0.42, 0.3, 35), ("rect", -0.85, -0.25, 0.14, 0.2, 10)]),
    ("Teeth Peaks", "peaks", 1312, 0, [("cap", 0.8, -0.5, 0.95, 0.3, 0.14), ("cap", 0.6, -0.1, 0.72, 0.05, 0.1)]),
    ("Southern Ranges", "ranges", 1314, 0, [("cap", -0.08, 0.38, 0.05, 0.92, 0.1), ("cap", -0.2, 0.55, 0.05, 0.6, 0.08)]),
]
SEEDS = {CAPITAL: ((0.0, -0.3), "plateau"), 7: ((-0.5, 0.55), "desert"), 162: ((0.5, -0.2), "teeth"),
         163: ((0.45, 0.5), "valley"), 165: ((-0.55, -0.05), "tundra")}
STATE_NAMES = {CAPITAL: "Spinara Plateau", 7: "Forgofshar Desert", 162: "Tarkin's Teeth", 163: "Ressl Valley",
               165: "Caridan Tundra", 1312: "Teeth Peaks", 1313: "Ice Cap", 1314: "Southern Ranges"}
IMPASSABLE = {1312, 1313, 1314}
VPS = [(CAPITAL, "Academy of Carida", CAPITAL_VP, 10), (CAPITAL, "Caridan District", "Caridan District", 3),
       (CAPITAL, "Academy Landing Field", "Academy Landing Field", 2), (162, "Teeth Training Ground", "Teeth Training Ground", 3),
       (7, "Forgofshar Survival Camp", "Forgofshar Survival Camp", 2), (163, "Ressl River", "Ressl River", 2),
       (165, "Carida Corsairs' Base", "Carida Corsairs' Base", 1), (7, "desert", "Forgofshar Desert", 1),
       (162, "teeth", "Tarkin's Teeth", 1)]

TERRAIN_CFG = dict(
    seed=164, base=5, rough=2, open=(5, 6, 7, 9, 13),
    zones={
        1: dict(relief=("ramp_top", 16, 9, 3), tex=["URBAN", ("ROCK2", ">", 0.7)]),                   # the Academy
        2: dict(relief=("flat", 7), tex=["URBAN", ("BROWN", ">", 0.65)]),                             # the Caridan district
        3: dict(relief=("flat", 6), tex=["BROWN", ("ROCK2", ">", 0.6)], props=[(225, 0.05)]),          # training camps
        4: dict(relief=("flat", 5), tex=["SNOWSAND", ("BROWN", ">", 0.5)], props=[(225, 0.15)]),       # the Corsairs' ruins
        5: dict(relief=("mesa", 6, 14, 4, (5, 0.6)), tex=["GRASSHILL", ("ROCK2", ">", 0.6), (13, ">", 0.95)],
                props=[(223, 0.2), (225, 0.05)]),                                                     # the Spinara Plateau
        6: dict(relief=("rolling", 4, 4, 6), tex=["DUNES", ("SAND", ">", 0.55), ("BROWN", ">", 0.85)], props=[(224, 0.12)]),
        7: dict(relief=("rolling", 5, 3, 7), tex=["SNOWSAND", ("SNOWFARM", ">", 0.55), ("ROCK", ">", 0.9)],
                props=[(223, 0.08), (225, 0.08)]),                                                    # the tundra
        8: dict(relief=("rolling", 12, 10, 4), tex=["ROCK", ("BROWNMTN", ">", 0.5)], props=[(225, 0.2), (223, 0.05)]),
        9: dict(relief=("rolling", 3, 3, 6), tex=["FOREST", ("JUNGLE", ">", 0.6), ("GRASS", ">", 0.9)],
                props=[(223, 0.55), (224, 0.1)]),                                                     # the Ressl valley
        10: dict(relief=("spires", 14, 8, 0.08, (1.5, 3.0), (20, 40)), tex=["SNOWROCK", ("SNOWSAND", ">", 0.6)]),
        11: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["BROWNMTN", ("ROCK", ">", 0.5), ("SNOWROCK", ">", 0.92)]),
        12: dict(relief=("spires", 14, 8, 0.1, (1.5, 3.0), (20, 40)), tex=["ROCK2", ("BROWNMTN", ">", 0.5)]),
        13: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.5)]),                             # the landing field
    },
    steep=("ROCK", 6, (5, 6, 7, 8, 9)),
    city={1: 82, 2: 82, 5: 82, 13: 82},   # map/cities.txt 82: Carida's academy towns (car_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.609, 0.54, 0.468), 2: (0.567, 0.472, 0.398), 3: (0.525, 0.387, 0.264), 4: (0.693, 0.664, 0.609), 5: (0.504, 0.438, 0.213), 6: (0.735, 0.461, 0.206), 7: (0.72, 0.74, 0.72), 8: (0.483, 0.356, 0.257), 9: (0.421, 0.441, 0.124), 10: (0.88, 0.9, 0.94), 11: (0.441, 0.325, 0.25), 12: (0.504, 0.376, 0.276), 13: (0.588, 0.562, 0.512)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)


def orbit(ctx):
    """the Republic station Valor (canon: in orbit over Carida in the Clone Wars), north-east of the disc"""
    (cy, cx), R = ctx["z"]["centre"], ctx["z"]["radius"]
    ctx["put"]("hod_car_valor", 1.0, cy - 0.9 * R, cx + 1.25 * R)


PLACEMENT = dict(
    new_models={"hod_car_academy", "hod_car_district", "hod_car_field", "hod_car_teeth", "hod_car_survival",
                "hod_car_corsairs", "hod_car_valor"},
    items=[("hod_car_academy", 1.0, ("at_vp", "Academy of Carida")), ("hod_car_district", 0.9, ("at_vp", "Caridan District")),
           ("hod_car_field", 0.9, ("at_vp", "Academy Landing Field")), ("hod_car_teeth", 0.9, ("at_vp", "Teeth Training Ground")),
           ("hod_car_survival", 0.8, ("at_vp", "Forgofshar Survival Camp")),
           ("hod_car_corsairs", 0.8, ("at_vp", "Carida Corsairs' Base"))],
    clear={"hod_car_academy": 6.0, "hod_car_district": 4.0, "hod_car_field": 4.0, "hod_car_teeth": 4.0,
           "hod_car_survival": 3.5, "hod_car_corsairs": 3.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (carida_map.py)\n{imp}"
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
