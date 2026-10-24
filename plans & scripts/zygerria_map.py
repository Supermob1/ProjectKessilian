"""Zygerria, throne world of the Zygerrian Slave Empire, as one battlefield (research: WIPGFX/research/zygerria/).
Canon (Wookieepedia "Zygerria", The Clone Wars "Slaves of the Republic"): a temperate, rocky world of plains, mesas
and highlands; fortresses and cities built on top of mesas with slave labour; the capital's streets shaded by
colourful awnings, quarters used only to house slaves, arenas for fights and bets; the Royal Palace of Queen Miraj
Scintel (Ahsoka Tano hung in a cage over its side); allied to the Confederacy during the Clone Wars.
Legends only: the regions East Province, the Highlands and the Drukarg highlands (mountainous, sparse plants, tall
natural pillar formations). Approved by the user 2026-10-14: canon look + Legends region names, "great mesa capital".
LAYOUT IS A DESIGN CHOICE (no source places anything): the capital city on a great central mesa ringed by cliffs, the
palace at its north edge, one ramp down south to the lower city; Drukarg pillar field NW, the Highlands NE, East
Province E, invented Western Steppe / Southern Mesalands, the slavers' landing field on the ESE coast; mesa fortresses
(canon idea, invented names) on three impassable mesas, each reached by a ramp.
Invented names: The Royal Mesa, Royal Arena, Slave Quarters, The Lower City, Slavers' Landing, Western Steppe,
Southern Mesalands, the fortresses and the impassable states (1156-1160).
    python "WIPGFX/plans & scripts/zygerria_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, names, positions
    python "WIPGFX/plans & scripts/zygerria_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 203 province ids are kept (strategic region 71 unchanged); only the pixels move. Writes
WIPGFX/Assets/zygerria_zones.json + zygerria_zones.png (KIND per pixel).
Run order: zygerria_map.py -> planet_terrain_gen.py --zygerria -> military_buildings.py models hod_zyg ->
military_buildings.py zygerria_place -> planet_terrain_gen.py --globe-texture.
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

PLANET = "Zygerria"
ZONES_JSON = "WIPGFX/Assets/zygerria_zones.json"
ZONES_PNG = "WIPGFX/Assets/zygerria_zones.png"
KIND = {"plains": 1, "capital": 2, "palace": 3, "arena": 4, "lowcity": 5, "landing": 6, "fortress": 7, "cliff": 8,
        "mesa": 9, "pillars": 10, "highland": 11}
TERRAIN = {"plains": "plains", "capital": "urban", "palace": "urban", "arena": "urban", "lowcity": "urban",
           "landing": "plains", "fortress": "hills", "cliff": "mountain", "mesa": "mountain", "pillars": "mountain",
           "highland": "hills"}
SEED = 85
CAPITAL = 85
PORT_STATE = 752
OWNER = "ZGY"
WARP = (0.07, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 130                # user rule for ~200-id planets: passable provinces outnumber impassable (Kadavo 130/70)
STRAIGHT = {"capital", "palace", "arena"}   # drawn unwarped: the plateau's ramp must stay one clean lane
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes). Shapes as korriban_map.shape: ("ell", u, v, ru, rv, deg), ("rect", u, v, hu, hv, deg),
# ("cap", u0, v0, u1, v1, r); u east, v south, planet radii. Plateaus and fortresses come before the rock round them,
# so the cliffs / mesas are rings with a ramp cut through them.
FORTS = [  # (fortress name, region state, mesa state, mesa name, centre, ramp end, mesa half-size, mesa angle)
    ("Western Mesa Fortress", 750, 1158, "Great Western Mesa", (-0.66, 0.0), (-0.66, 0.32), (0.21, 0.16), 20),
    ("Southern Mesa Citadel", 751, 1159, "Southern Mesas", (-0.34, 0.7), (-0.06, 0.76), (0.24, 0.16), -15),
    ("East Province Fortress", 749, 1160, "Eastern Mesa", (0.52, -0.27), (0.78, -0.1), (0.19, 0.15), 35),
]
FEATURES = [
    ("Royal Palace of Zygerria", "palace", CAPITAL, 2, [("ell", 0.0, -0.17, 0.1, 0.06, 0)]),
    ("Royal Arena", "arena", CAPITAL, 1, [("ell", 0.11, 0.06, 0.07, 0.06, 0)]),
    ("The Royal Mesa", "capital", CAPITAL, 9, [("ell", 0.0, 0.0, 0.25, 0.21, 10),
                                              ("cap", 0.0, 0.1, 0.0, 0.42, 0.055)]),          # the one ramp, south
    ("The Lower City", "lowcity", 753, 6, [("ell", 0.0, 0.5, 0.17, 0.1, 0)]),
    ("Slavers' Landing", "landing", PORT_STATE, 6, [("ell", 0.78, 0.3, 0.17, 0.13, 20), ("rect", 0.92, 0.33, 0.12, 0.08, 20)]),
]
for _n, _st, _ms, _mn, (_u, _v), (_ru, _rv), (_a, _b), _deg in FORTS:
    FEATURES.append((_n, "fortress", _st, 2, [("ell", _u, _v, 0.07, 0.06, _deg), ("cap", _u, _v, _ru, _rv, 0.045)]))
FEATURES += [
    ("Royal Mesa Cliffs", "cliff", 1156, 0, [("ell", 0.0, 0.0, 0.42, 0.37, 10)]),
    # the Drukarg pillar field: a ragged union of ridges reaching the planet's north edge
    ("Drukarg Pillars", "pillars", 1157, 0, [("ell", -0.45, -0.52, 0.25, 0.17, -30), ("cap", -0.3, -0.6, 0.05, -0.95, 0.1),
                                            ("cap", -0.6, -0.45, -0.85, -0.6, 0.08), ("cap", -0.4, -0.45, -0.2, -0.3, 0.06)]),
]
for _n, _st, _ms, _mn, (_u, _v), _r, (_a, _b), _deg in FORTS:
    FEATURES.append((_mn, "mesa", _ms, 0, [("rect", _u, _v, _a, _b, _deg),                    # carved, not round
                                            ("ell", _u + 0.4 * _a, _v - 0.5 * _b, 0.8 * _a, 1.1 * _b, _deg + 35)]))
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {747: ((0.5, -0.65), "highland"), 748: ((-0.72, -0.2), "highland"), 749: ((0.8, -0.15), "plains"),
         750: ((-0.75, 0.38), "plains"), 751: ((0.25, 0.8), "plains")}
STATE_NAMES = {CAPITAL: "The Royal Mesa", 747: "The Highlands", 748: "Drukarg Highlands", 749: "East Province",
               750: "Western Steppe", 751: "Southern Mesalands", PORT_STATE: "Slavers' Landing", 753: "The Lower City",
               1156: "Royal Mesa Cliffs", 1157: "Drukarg Pillars", 1158: "Great Western Mesa", 1159: "Southern Mesas",
               1160: "Eastern Mesa"}
IMPASSABLE = {1156, 1157, 1158, 1159, 1160}
# victory points: (state, feature or kind, name, value); canon: the palace; canon kinds with invented names: arena,
# slave quarters, mesa fortresses; Legends regions: Highlands, Drukarg; invented: the landing field
VPS = [(CAPITAL, "palace", "Royal Palace of Zygerria", 10), (CAPITAL, "arena", "Royal Arena", 3),
       (753, "lowcity", "Slave Quarters", 3), (PORT_STATE, "landing", "Slavers' Landing", 3),
       (750, "fortress", "Western Mesa Fortress", 2), (751, "fortress", "Southern Mesa Citadel", 2),
       (749, "fortress", "East Province Fortress", 2), (747, "highland", "Highland Watch", 1),
       (748, "highland", "Drukarg Outpost", 1)]
# terrain (planet_terrain_gen.py --planet Zygerria; operators and format: planet_terrain_gen.zone_repaint). Heights in
# heightmap steps above the base: plains 4, highlands 12, the royal mesa's top 44, the fortress mesas' tops 34.
ROCKY = ["BROWNMTN", (24, ">", 0.5)]                                     # red-brown rock (24 = atlas red rock)
TERRAIN_CFG = dict(
    seed=85, base=4, rough=4, open=(1, 11, 5, 6),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 4, 4, None), tex=["SAVANNA", ("BROWN", ">", 0.66), ("GRASS", "<", 0.25)],
                props=[(52, 0.01), (50, 0.006), (44, 0.005)],             # golden steppe; boulders, a few shrubs
                clusters=[(8, 0.62, [(86, 0.6), (87, 0.2)])]),          # small copses (user, 2026-10-14)
        11: dict(relief=("rolling", 12, 10, 6), tex=["GRASSHILL", ("HILLS", ">", 0.6)],
                 props=[(48, 0.02), (49, 0.015), (44, 0.006)],            # the highlands: bare rock
                 clusters=[(7, 0.58, [(86, 0.55), (87, 0.25)])]),          # and wooded hollows
        2: dict(relief=("ramp_top", 44, 5, 12), tex="URBAN"),             # the capital: city models (style below)
        3: dict(relief=("ramp_top", 44, 5, 12), tex=25),                  # palace, arena: urban_plaza_25, no city models
        4: dict(relief=("ramp_top", 44, 5, 12), tex=25),
        7: dict(relief=("ramp_top", 34, 5, 12), tex=25),                  # the mesa fortresses
        8: dict(relief=("flank", 4, 42, (2, 3, 4), 13), tex=ROCKY),        # the royal mesa's cliffs, 13 gullies
        9: dict(relief=("mesa", 4, 34, 2.2, (3, 0.7)), tex=ROCKY),
        10: dict(relief=("spires", 12, 4, 0.05, (1.0, 2.4), (24, 60)), tex=ROCKY,   # Legends: tall natural pillars
                 props=[(48, 0.03), (49, 0.03)]),
        5: dict(relief=("flat", 5), tex="URBAN"),                         # the lower city
        6: dict(relief=("flat", 5), tex=25),                              # the landing field's pads
    },
    steep=("ROCK2", 7, (1, 11)),
    city={2: 14, 5: 14},        # map/cities.txt group 14: the Zygerrian capital (military_buildings zyg_city)
)
# models (military_buildings.py place Zygerria): (mesh, scale, where), placed in this order
PLACEMENT = dict(
    new_models={"hod_zyg_palace", "hod_zyg_arena", "hod_zyg_fortress", "hod_zyg_landing"},
    items=[("hod_zyg_palace", 1.0, ("zone_centre", 3)),
           ("hod_zyg_arena", 1.0, ("at_vp", "Royal Arena")),                  # the slave auction's courtyard
           ("hod_zyg_fortress", 1.0, ("at_vp", ["Western Mesa Fortress", "Southern Mesa Citadel", "East Province Fortress"])),
           ("hod_zyg_landing", 1.0, ("at_vp", "Slavers' Landing"))],
    clear={"hod_zyg_palace": 10.0, "hod_zyg_arena": 5.5},   # no city blocks inside the palace or the arena
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
    capital_p = next(p for p, n in vp_names.items() if n == "Royal Palace of Zygerria")
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
        if sid == PORT_STATE:                                            # the slavers' ships and yards: the landing field
            if docks:
                bld = bld.rstrip().rstrip("}") + f"\tdockyard = {docks}\n\t\t}}"
            if naval:
                bld = bld.rstrip().rstrip("}") + f"\t\t\t{port} = {{\n\t\t\t\tnaval_base = {max(naval)}\n\t\t\t}}\n\t\t}}"
        if sid in IMPASSABLE:
            imp = "\timpassable = yes\n"
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            res, man, cat = "\n\tresources={\n\t}", "1000", "wasteland_sector"
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {vps[p]}\n\t\t}}\n" for p in provs if p in vps)
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: Zygerria (zygerria_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {OWNER}\n\t\tadd_core_of = {OWNER}\n\t}}\n"
                f"\tmanpower = {man}\n\tstate_category = {cat}\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}}\n")
        if sid in old:
            os.remove(old[sid])
        open(f"history/states/{sid}-Zygerria - {STATE_NAMES[sid].replace(chr(39), '')}.txt", "w", encoding="utf-8",
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
