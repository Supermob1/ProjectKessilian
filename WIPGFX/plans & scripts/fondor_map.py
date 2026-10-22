"""Fondor, the shipbuilders' world of the Colonies, as one battlefield before the Clone Wars (research:
WIPGFX/research/fondor/). CANON: seen from orbit a purple surface covered by interconnected bright lines and circles;
the Fondor Shipyards above it. LEGENDS: the surface scabbed with excavations, factories, cooling towers, steam tunnels,
workers' barracks and offices, mine shafts leading deep into the planet's core; Fondor's underground steam tubes, a huge
pipeline network; Fondor City the capital, Oridin City a major city; the Fondor Academy of Engineering and Design, which
before the Clone Wars fed recruits to Kuat Drive Yards and the Techno Union. Owner: FON (as before).
THE USER, 2026-10-22: an industrial city world, built like Empress Teta (empress_teta_map.py): plazas joined by
narrow streets, every enclosed pocket an impassable megablock (here factories, foundries, cooling-tower ranges and
barracks), spaceports on the rim. The "bright lines and circles" are the streets and plazas, the purple the blocks.
LAYOUT, A DESIGN CHOICE: Fondor City's plaza in the middle; Oridin City north-east; the Academy north-west; the
Steam Tube Junction south-east of the capital; the Core Shafts round the Great Shaft (impassable) in the south-west; lift
fields on the rim for the shipyards above: the Northern Lift Fields (the Abregado-Rae lane), the Shipyard Lift Station
east (the Bestine IV lane), the Southern Launch Fields (the Ghorman lane).
Names from the sources: Fondor City, Oridin City, Fondor Academy of Engineering and Design, the steam tubes, the mine
shafts, the shipyards. Invented: Academy Quad, Steam Tube Junction, Core Shafts, Great Shaft, the lift fields and every
megablock name.
    python "WIPGFX/plans & scripts/fondor_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/fondor_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All province ids are kept (strategic region unchanged); only the pixels move.
"""
import glob, math, os, re, sys
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from felucia_map import split_area
from felucia_tribes import block, place, rw
from raxus_map import mend
import planet_common as pcom
from korriban_map import shape, uncross

PLANET = "Fondor"
ZONES_JSON = "WIPGFX/Assets/fondor_zones.json"
ZONES_PNG = "WIPGFX/Assets/fondor_zones.png"
KIND = {"plaza": 1, "core": 2, "academy": 3, "steam": 4, "port": 6, "street": 7, "mines": 8, "pit": 9, "blocks": 10}
TERRAIN = {k: "urban" for k in KIND}
TERRAIN.update(pit="mountain", blocks="mountain")
SEED = 14
CAPITAL = 14
CAPITAL_VP = "Fondor City"
CORE = "FON"
PORT_STATE = 310                     # the Shipyard Lift Station
WARP = (0.05, 9)
TARGET_PASSABLE = 116                # user rule: passable provinces outnumber impassable
STREET = 0.034                       # street half-width (planet radii)
STRAIGHT = {"academy", "steam"}
MIN_BLOCK = 45

DISTRICTS = {14: "Fondor City", 307: "Oridin City", 308: "Academy District", 309: "Southern Launch Fields",
             310: "Shipyard Lift Station", 311: "Northern Lift Fields", 312: "Steam Tube Junction", 313: "Core Shafts"}
PIT = 1393
FEATURES = [   # (name, kind, state, provinces (0 = sized from TARGET_PASSABLE), shapes); the first shape on a pixel wins
    ("Fondor Academy of Engineering and Design", "academy", 308, 1, [("rect", -0.46, -0.26, 0.07, 0.05, -10)]),
    ("Fondor Steam Tubes", "steam", 312, 1, [("ell", 0.3, 0.38, 0.055, 0.055, 0)]),
    ("Great Shaft", "pit", PIT, 0, [("ell", -0.58, 0.3, 0.13, 0.11, 20)]),
    ("Fondor City", "core", 14, 3, [("ell", -0.04, 0.0, 0.22, 0.15, -10), ("rect", -0.04, 0.0, 0.33, 0.045, -10),
                                     ("rect", -0.04, 0.0, 0.045, 0.24, -10)]),
    ("Oridin City", "plaza", 307, 0, [("ell", 0.46, -0.32, 0.16, 0.12, 25)]),
    ("Academy Quad", "plaza", 308, 0, [("ell", -0.46, -0.26, 0.14, 0.1, -10)]),
    ("Shipyard Lift Station", "port", 310, 0, [("ell", 0.86, 0.3, 0.22, 0.14, 25)]),
    ("Northern Lift Fields", "port", 311, 0, [("ell", -0.42, -0.84, 0.24, 0.13, -30)]),
    ("Southern Launch Fields", "port", 309, 0, [("ell", -0.16, 0.86, 0.26, 0.13, 5)]),
    ("Steam Tube Junction", "plaza", 312, 0, [("ell", 0.3, 0.38, 0.13, 0.1, 0)]),
    ("Core Shafts", "mines", 313, 0, [("ell", -0.58, 0.3, 0.23, 0.2, 20)]),
]
STREETS = [   # (state, points): narrow streets, bends at the inner points; dead ends are alleys
    (14, [(0.0, 0.0), (-0.46, -0.26)]), (14, [(0.0, 0.0), (0.46, -0.32)]), (14, [(0.0, 0.0), (0.3, 0.38)]),
    (14, [(0.0, 0.0), (-0.42, 0.18)]), (308, [(-0.46, -0.26), (-0.42, -0.8)]),
    (307, [(0.46, -0.32), (0.05, -0.58), (-0.3, -0.8)]), (307, [(0.46, -0.32), (0.8, 0.22)]),
    (312, [(0.3, 0.38), (0.75, 0.34)]), (312, [(0.3, 0.38), (-0.08, 0.8)]), (313, [(-0.52, 0.48), (-0.26, 0.82)]),
    (313, [(-0.75, 0.14), (-0.62, -0.14), (-0.46, -0.26)]), (307, [(0.46, -0.32), (0.66, -0.58)]),
    (310, [(0.86, 0.3), (0.62, 0.62)]), (308, [(-0.46, -0.26), (-0.8, -0.42)]), (14, [(0.0, 0.0), (0.14, -0.36)]),
    (309, [(-0.16, 0.86), (0.2, 0.7)]),
]
# megablocks: every enclosed pocket is one impassable state, named by the nearest anchor (ids gapless after PIT)
BLOCKS = {1394: ("Western Foundries", (-0.72, 0.02)), 1395: ("Barrack Blocks", (-0.45, -0.0)),
          1396: ("Cooling Tower Range", (-0.13, 0.42)), 1397: ("Northern Factories", (-0.11, -0.42)),
          1398: ("Southern Foundries", (0.41, 0.69)), 1399: ("Drive Works", (0.43, 0.09)),
          1400: ("Northern Cooling Towers", (0.47, -0.52))}
STATE_NAMES = {**DISTRICTS, PIT: "Great Shaft", **{k: v[0] for k, v in BLOCKS.items()}}
IMPASSABLE = {PIT, *BLOCKS}
OWNER = {s: "FON" for s in STATE_NAMES}
VPS = [(14, "Fondor City", CAPITAL_VP, 20), (307, "Oridin City", "Oridin City", 10),
       (308, "Fondor Academy of Engineering and Design", "Fondor Academy of Engineering and Design", 5),
       (312, "Fondor Steam Tubes", "Fondor Steam Tubes", 3), (313, "Core Shafts", "Core Shafts", 3),
       (310, "Shipyard Lift Station", "Shipyard Lift Station", 5), (311, "Northern Lift Fields", "Northern Lift Fields", 2),
       (309, "Southern Launch Fields", "Southern Launch Fields", 2)]

TERRAIN_CFG = dict(
    seed=14, base=4, rough=1, open=(1, 6, 7),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.8)]),                              # plazas
        2: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.8)]),                              # Fondor City
        3: dict(relief=("flat", 6), tex="URBAN"),                                                     # the Academy
        4: dict(relief=("flat", 5), tex=["URBAN", ("BROWN", ">", 0.5)]),                              # the steam tubes
        6: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.6)]),                              # lift fields
        7: dict(relief=("flat", 4), tex=["URBAN", ("BROWN", ">", 0.75)]),                             # streets / steam trenches
        8: dict(relief=("flat", 4), tex=["BROWN", ("URBAN", ">", 0.4)]),                              # the Core Shafts' works
        9: dict(relief=("flat", 0.5), tex=["ROCK", ("BROWN", ">", 0.5)]),                             # the Great Shaft
        10: dict(relief=("rolling", 11, 3, 3), tex=["URBAN", (13, ">", 0.1), ("BROWN", ">", 0.92)]),  # factory megablocks
    },
    city={1: 99, 7: 99, 8: 99, 10: 99},   # map/cities.txt 99: Fondor's factories and cooling towers (fon_town)
    prop_clear=1.5,
    lights=dict(zones=(1, 2, 4, 6, 7), rgb=(0.55, 0.85, 1.0), density=0.25, mix=0.85),   # the bright lines and circles
    colors={1: (0.8, 0.84, 0.9), 2: (0.86, 0.88, 0.94), 3: (0.7, 0.66, 0.8), 4: (0.74, 0.8, 0.9), 6: (0.78, 0.82, 0.9),
            7: (0.66, 0.78, 0.92), 8: (0.46, 0.36, 0.52), 9: (0.22, 0.16, 0.3), 10: (0.44, 0.26, 0.56)},   # purple world
)


def orbit(ctx):
    """the Fondor Shipyards IN ORBIT (canon: wheel-shaped dockyards above Fondor; the user, 2026-10-22: shipyards are
    space stations): beside the disc to the north-east, clear of the three lanes"""
    (cy, cx), R = ctx["z"]["centre"], ctx["z"]["radius"]
    ctx["put"]("hod_fon_yards", 1.0, cy - 0.8 * 1.95 * R, cx + 0.6 * 1.95 * R)


PLACEMENT = dict(
    new_models={"hod_fon_city", "hod_fon_oridin", "hod_fon_academy", "hod_fon_steam", "hod_fon_shaft", "hod_fon_lift",
                "hod_fon_yards"},
    items=[("hod_fon_city", 1.0, ("at_vp", CAPITAL_VP)), ("hod_fon_oridin", 0.9, ("at_vp", "Oridin City")),
           ("hod_fon_academy", 0.9, ("at_vp", "Fondor Academy of Engineering and Design")),
           ("hod_fon_steam", 0.8, ("at_vp", "Fondor Steam Tubes")), ("hod_fon_shaft", 1.0, ("at_vp", "Core Shafts")),
           ("hod_fon_lift", 1.0, ("at_vp", "Shipyard Lift Station")), ("hod_fon_lift", 0.8, ("at_vp", "Northern Lift Fields")),
           ("hod_fon_lift", 0.8, ("at_vp", "Southern Launch Fields"))],
    clear={"hod_fon_city": 5.0, "hod_fon_oridin": 4.5, "hod_fon_academy": 3.5, "hod_fon_steam": 3.0, "hod_fon_shaft": 4.5,
           "hod_fon_lift": 4.5},
    hook=orbit,
)

def mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    return land, pid, np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])


def layout(m, rng):
    """feature index per pixel and features [(name, kind, state, provinces)]: FEATURES, then the streets, then each
    enclosed pocket of city as a megablock (small pockets paved into the plaza or street beside them)"""
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
    for i, (sid, pts) in enumerate(STREETS):
        feats.append((f"{DISTRICTS[sid]} street {i + 1}", "street", sid, 0))
        on = np.any([shape(("cap", *a, *b, STREET), U, V) for a, b in zip(pts, pts[1:])], 0)
        fid[sm & (fid < 0) & on] = len(feats) - 1
    pockets, n = ndi.label(sm & (fid < 0))
    taken = {}
    for j in range(1, n + 1):
        pk = pockets == j
        if pk.sum() < MIN_BLOCK:                                       # a scrap between streets: paved
            ring = ndi.binary_dilation(pk) & ~pk & (fid >= 0)
            fid[pk] = np.bincount(fid[ring]).argmax()
            continue
        u, v = U0[pk].mean(), V0[pk].mean()
        sid = min(BLOCKS, key=lambda b: math.hypot(BLOCKS[b][1][0] - u, BLOCKS[b][1][1] - v))
        assert sid not in taken, f"two pockets nearest {BLOCKS[sid][0]}: ({u:.2f}, {v:.2f}) and {taken[sid]}"
        taken[sid] = (round(float(u), 2), round(float(v), 2))
        feats.append((BLOCKS[sid][0], "blocks", sid, 0))
        fid[pk] = len(feats) - 1
    unused = sorted(set(BLOCKS) - set(taken))
    assert not unused, f"no pocket for {[BLOCKS[b][0] for b in unused]}; pockets at {sorted(taken.values())}"
    full = np.full(m.shape, -1, np.int32)
    full[sl] = fid
    return full, feats


def tidy(lab, feats, m):
    """every feature in one piece: stray bits join the neighbour with the longest shared border, preferring their own
    state, then their own kind"""
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
                kin = [k for k in np.nonzero(nb)[0] if (feats[k][2] in IMPASSABLE) == (feats[i][2] in IMPASSABLE)]
                pick = same or kin or list(np.nonzero(nb)[0])
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (fondor_map.py)\n{imp}"
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
