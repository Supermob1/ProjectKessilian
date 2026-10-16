"""Jabiim, the monsoon world of the Outer Rim, as one battlefield on the eve of the Clone Wars (research:
WIPGFX/research/jabiim/). LEGENDS (user, 2026-10-16: the monsoon world): endless rain over muddy plains, seas and
rivers, rocky ground and caves; huge digging and boring machines cut ever deeper into the dying planet; grasses,
trees, bamboo; Choal the capital; the Battle of Jabiim (22 BBY): High Rock Canyon, the Jobreth Plains, the Razor Coast
(a rocky shoreline), Hyber Canyon, Monsoon Mesa with Cobalt Station "just north" of it, Shelter Base (the Republic's
command centre), Camp Aurek (the Confederacy's base), Outpost Shear (the Nationalists' defensive position).
User (2026-10-16): the bases already stand at the start (pre-positioned for the coming battle). Owner: Jabiim (JAB).
LAYOUT IS A DESIGN CHOICE except Cobalt Station north of Monsoon Mesa: the sea over the west rim with the Razor Coast,
Choal in the centre-west on a river through the plains, the vast Jobreth Plains over the south with flooded lowlands
and a mining bore, a rocky highland spine through the north-east (impassable) with High Rock Canyon cut into its
southern flank, the Republic's Monsoon Mesa and Cobalt Station in the east and Shelter Base on the northern fens, Camp
Aurek in the south-eastern badlands, Outpost Shear on the north-eastern ridges by Hyber Canyon.
Legends names: every site above. Invented: every state name, the Choal River, the Jobreth Bore (the machines are
Legends), the Razor Sea, the Jabiim Highlands.
    python "WIPGFX/plans & scripts/jabiim_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/jabiim_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 205 province ids are kept (strategic region unchanged); only the pixels move.
Run order: jabiim_map.py -> flora_props.py (jab_*) -> planet_terrain_gen.py --planet Jabiim -> military_buildings.py
models hod_jab -> military_buildings.py place Jabiim -> jabiim_fx.py (the monsoon rain) -> planet_terrain_gen.py
--globe-texture -> landmarks_lore.py.
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

PLANET = "Jabiim"
ZONES_JSON = "WIPGFX/Assets/jabiim_zones.json"
ZONES_PNG = "WIPGFX/Assets/jabiim_zones.png"
KIND = {"mud": 1, "grass": 2, "city": 3, "flood": 4, "river": 5, "mesa": 6, "canyon": 7, "base": 8, "coast": 9,
        "ridge": 10, "sea": 11, "mine": 12}
TERRAIN = {"mud": "plains", "grass": "plains", "city": "urban", "flood": "marsh", "river": "marsh", "mesa": "hills",
           "canyon": "hills", "base": "hills", "coast": "hills", "ridge": "mountain", "sea": "mountain", "mine": "hills"}
SEED = 75
CAPITAL = 75
CAPITAL_VP = "Choal"
PORT_STATE = 683
OWNER = {s: "JAB" for s in (75, 678, 679, 680, 681, 682, 683, 684, 1199, 1200)}
WARP = (0.13, 9)
TARGET_PASSABLE = 132                # user rule: passable provinces outnumber impassable (~132 / 73)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Choal", "city", CAPITAL, 4, [("ell", -0.32, 0.0, 0.17, 0.13, 10)]),
    ("Monsoon Mesa", "mesa", 679, 3, [("ell", 0.55, 0.12, 0.14, 0.1, -20)]),
    ("Cobalt Station", "base", 679, 1, [("ell", 0.55, -0.08, 0.07, 0.06, 0)]),
    ("Shelter Base", "base", 680, 1, [("ell", -0.05, -0.55, 0.08, 0.07, 0)]),
    ("Camp Aurek", "base", 681, 2, [("ell", 0.45, 0.6, 0.1, 0.08, 15)]),
    ("Outpost Shear", "base", 682, 1, [("ell", 0.62, -0.5, 0.07, 0.06, 0)]),
    ("Jobreth Bore", "mine", 678, 2, [("ell", -0.05, 0.7, 0.11, 0.09, 0)]),
    ("High Rock Canyon", "canyon", 684, 4, [("cap", 0.0, -0.08, 0.3, -0.25, 0.08), ("ell", 0.12, -0.18, 0.1, 0.07, 30)]),
    ("Hyber Canyon", "canyon", 682, 2, [("cap", 0.75, -0.3, 0.88, -0.05, 0.06)]),
    ("Razor Coast", "coast", PORT_STATE, 3, [("cap", -0.78, -0.45, -0.72, 0.45, 0.07)]),
    # the river from the highlands past Choal to the sea, and the flooded lowlands of the Jobreth Plains
    ("Choal River", "river", CAPITAL, 3, [("cap", 0.05, 0.05, -0.15, 0.08, 0.035), ("cap", -0.15, 0.08, -0.5, 0.15, 0.04),
                                          ("cap", -0.5, 0.15, -0.72, 0.1, 0.045)]),
    ("Jobreth Floods", "flood", 678, 4, [("ell", -0.32, 0.55, 0.16, 0.08, 20), ("ell", 0.12, 0.45, 0.12, 0.07, -15)]),
    # the highland spine through the north-east, never rim to rim; the sea over the west rim
    ("Jabiim Highlands", "ridge", 1199, 0, [("cap", 0.0, -0.32, 0.45, -0.3, 0.09), ("cap", 0.45, -0.3, 0.4, -0.85, 0.1),
                                            ("cap", 0.35, -0.3, 0.7, 0.0, 0.07)]),
    ("Razor Sea", "sea", 1200, 0, [("ell", -1.02, 0.0, 0.22, 0.8, 0)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((-0.3, 0.05), "mud"), 678: ((-0.1, 0.6), "mud"), 679: ((0.65, 0.2), "grass"),
         680: ((-0.15, -0.55), "grass"), 681: ((0.5, 0.65), "mud"), 682: ((0.72, -0.45), "grass"),
         683: ((-0.62, -0.3), "grass"), 684: ((0.15, -0.05), "grass")}
STATE_NAMES = {CAPITAL: "Choal Delta", 678: "Jobreth Plains", 679: "Monsoon Mesa", 680: "Northern Fens",
               681: "Aurek Badlands", 682: "Shear Ridges", 683: "Razor Coast", 684: "High Rock Canyon",
               1199: "Jabiim Highlands", 1200: "Razor Sea"}
IMPASSABLE = {1199, 1200}
# victory points: (state, feature or kind, name, value); Legends except the Jobreth Bore
VPS = [(CAPITAL, "Choal", CAPITAL_VP, 10), (679, "Cobalt Station", "Cobalt Station", 3),
       (679, "Monsoon Mesa", "Monsoon Mesa", 2), (680, "Shelter Base", "Shelter Base", 3),
       (681, "Camp Aurek", "Camp Aurek", 3), (682, "Outpost Shear", "Outpost Shear", 2),
       (682, "Hyber Canyon", "Hyber Canyon", 1), (684, "High Rock Canyon", "High Rock Canyon", 3),
       (678, "Jobreth Bore", "Jobreth Bore", 2), (678, "Jobreth Floods", "Jobreth Plains", 2),
       (PORT_STATE, "Razor Coast", "Razor Coast", 2)]

# terrain (planet_terrain_gen.py --planet Jabiim). Heights in heightmap steps above the base. Legends look: rain-
# soaked mud plains and grass, rivers and floods (the water tile, animated by gfx/FX/pdxmap.shader), rocky highlands
# and canyons, mesas, a rocky coast, mining scars; trees, bamboo and grasses
MUD = ["BROWN", ("GRASS", ">", 0.62), ("HILLS", "<", 0.15)]


def carve(ctx):
    """the canyons cut down into the ground in benches, the mining pit round the bore stepped down"""
    z, rel, rough = ctx["z"], ctx["rel"], ctx["rough"]
    for k_, step, width, floor in ((7, 2.4, 1.1, 1.5), (12, 1.6, 1.0, 1.0)):
        m = ctx["sub"] & (z == k_)
        d = ndi.distance_transform_edt(m)
        rel = np.where(m, np.maximum(floor, 9 + rough - step * np.floor(d / width)), rel)
    ctx["rel"] = rel


TERRAIN_CFG = dict(
    seed=75, base=4, rough=2, open=(1, 2),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 4, 2, 6), tex=MUD, props=[(126, 0.1), (125, 0.04)],
                clusters=[(8, 0.62, [(125, 0.4), (127, 0.2)])]),                                # mud plains
        2: dict(relief=("rolling", 5, 4, 5), tex=["GRASS", ("BROWN", ">", 0.66), ("GRASSHILL", "<", 0.2)],
                props=[(125, 0.1), (126, 0.12), (127, 0.06)], clusters=[(7, 0.6, [(125, 0.5), (127, 0.3)])]),
        3: dict(relief=("ramp_top", 6, 4, 4), tex="URBAN"),                                     # Choal
        4: dict(relief=("flat", 0.3), tex="WATER"),                                              # the floods
        5: dict(relief=("flat", 0.3), tex="WATER"),                                              # the river
        6: dict(relief=("mesa", 5, 22, 2.5, (5, 0.55)), tex=["ROCK2", ("GRASSHILL", ">", 0.6)]),  # Monsoon Mesa
        7: dict(tex=["ROCK2", ("BROWN", ">", 0.6)], props=[(127, 0.1)]),                        # canyons (carve)
        8: dict(relief=("flat", 6), tex=25),                                                     # the bases' aprons
        9: dict(relief=("spires", 6, 4, 0.07, (1.0, 2.0), (6, 14)), tex=["ROCK", ("ROCK2", ">", 0.5)]),   # Razor Coast
        10: dict(relief=("spires", 14, 8, 0.07, (1.5, 3.0), (16, 34)), tex=["ROCK2", ("GRASSHILL", ">", 0.62)],
                 props=[(125, 0.06)]),                                                           # the highlands
        11: dict(relief=("flat", 0.3), tex="WATER"),                                             # the Razor Sea
        12: dict(tex=["BROWN", ("ROCK2", ">", 0.5)]),                                            # the mining pit (carve)
    },
    steep=("ROCK", 6, (6, 7, 9, 10, 12)),
    city={3: 33},   # map/cities.txt 33: Jabiimi rain towns (military_buildings.py jab_city)
    prop_clear=1.8,
    landforms=dict(amp=0, hills=0, skirt_k=0),
    shore_rise=(5, 2.0),   # banks and the coast stand up out of the water
    hook=carve,
)

# models (military_buildings.py place Jabiim): big, custom (user rule 2026-10-14); the bases already stand (user)
PLACEMENT = dict(
    new_models={"hod_jab_choal", "hod_jab_bore", "hod_jab_shelter", "hod_jab_cobalt", "hod_jab_aurek", "hod_jab_shear"},
    items=[("hod_jab_choal", 1.0, ("at_vp", CAPITAL_VP)), ("hod_jab_bore", 1.0, ("at_vp", "Jobreth Bore")),
           ("hod_jab_shelter", 1.0, ("at_vp", "Shelter Base")), ("hod_jab_cobalt", 1.0, ("at_vp", "Cobalt Station")),
           ("hod_jab_aurek", 1.0, ("at_vp", "Camp Aurek")), ("hod_jab_shear", 1.0, ("at_vp", "Outpost Shear"))],
    clear={"hod_jab_choal": 6.0, "hod_jab_bore": 5.5, "hod_jab_shelter": 5.0, "hod_jab_cobalt": 4.5,
           "hod_jab_aurek": 5.0, "hod_jab_shear": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (jabiim_map.py)\n{imp}"
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
