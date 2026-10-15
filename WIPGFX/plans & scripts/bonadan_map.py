"""Bonadan, the Corporate Sector's industrial world, as one battlefield in the Clone Wars (research:
WIPGFX/research/bonadan/). Canon says almost nothing about the surface; this map follows LEGENDS (user, 2026-10-15):
a yellow, parched, heavily eroded world, its topsoil destroyed by drilling and construction, "a yellow sphere covered
with rust-red strips"; the surface covered with factories, refineries, docks and shipyards in ten spaceports, the
largest Spaceport Southeast II; a massive weather-control station in the mountains north of the main cities (sweeper
storms clean the polluted air); the Bonadan shipyards (Class IB, cruisers). Owner: the Corporate Sector Authority.
LAYOUT IS A DESIGN CHOICE: the main cities in the south-east around Spaceport Southeast II, the shipyards on the east
rim, the refinery belt across the middle, a mountain wall over the north with the weather-control station on its
southern flank, rust-red strip-mine trenches cutting the western wastes, eroded canyons in the north-east.
Invented names: every state name, Spaceport Southeast I / Central / West / South / Northeast, Refinery Row,
the strip mines and canyons. Legends names: Spaceport Southeast II, Bonadan Shipyards, Weather Control Station.
    python "WIPGFX/plans & scripts/bonadan_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/bonadan_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 195 province ids are kept (strategic region unchanged); only the pixels move.
Run order: bonadan_map.py -> planet_terrain_gen.py --planet Bonadan -> military_buildings.py models hod_bon
-> military_buildings.py place Bonadan -> planet_terrain_gen.py --globe-texture.
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

PLANET = "Bonadan"
ZONES_JSON = "WIPGFX/Assets/bonadan_zones.json"
ZONES_PNG = "WIPGFX/Assets/bonadan_zones.png"
KIND = {"wastes": 1, "badlands": 2, "spaceport": 3, "city": 4, "refinery": 5, "shipyard": 6, "station": 7,
        "range": 8, "strip": 9, "canyon": 10}
TERRAIN = {"wastes": "desert", "badlands": "hills", "spaceport": "urban", "city": "urban", "refinery": "urban",
           "shipyard": "urban", "station": "hills", "range": "mountain", "strip": "mountain", "canyon": "mountain"}
SEED = 86
CAPITAL = 86
CAPITAL_VP = "Spaceport Southeast II"
PORT_STATE = 754
OWNER = "CSA"
WARP = (0.13, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 125                # user rule: passable provinces outnumber impassable (~125 / 70)
STRAIGHT = {"spaceport"}             # drawn unwarped: landing grids
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Spaceport Southeast II", "spaceport", CAPITAL, 3, [("ell", 0.42, 0.5, 0.13, 0.1, 0)]),
    ("Southeast Foundries", "city", CAPITAL, 4, [("ell", 0.22, 0.36, 0.16, 0.12, -25)]),
    ("Spaceport Southeast I", "spaceport", CAPITAL, 1, [("ell", 0.12, 0.62, 0.07, 0.06, 0)]),
    ("Bonadan Shipyards", "shipyard", PORT_STATE, 4, [("ell", 0.8, 0.1, 0.1, 0.2, 10)]),
    ("Refinery Row", "refinery", 756, 4, [("cap", -0.3, 0.05, 0.12, 0.12, 0.08)]),
    ("Weather Control Station", "station", 755, 2, [("ell", -0.02, -0.5, 0.1, 0.08, 0)]),
    ("Spaceport West", "spaceport", 757, 1, [("ell", -0.62, -0.32, 0.07, 0.06, 0)]),
    ("Spaceport South", "spaceport", 758, 1, [("ell", -0.3, 0.72, 0.07, 0.06, 0)]),
    ("Spaceport Northeast", "spaceport", 759, 1, [("ell", 0.5, -0.32, 0.07, 0.06, 0)]),
    # the mountain wall over the north, ragged spurs down towards the cities
    ("Northern Range", "range", 1168, 0, [("ell", 0.0, -0.9, 0.8, 0.28, 0), ("cap", -0.55, -0.62, -0.3, -0.42, 0.09),
                                          ("cap", 0.3, -0.64, 0.2, -0.45, 0.08), ("cap", -0.1, -0.66, -0.12, -0.56, 0.1)]),
    # the rust-red strips: two strip-mine trenches across the western wastes (never rim to rim)
    ("Western Strip Mines", "strip", 1169, 0, [("cap", -0.88, -0.05, -0.42, 0.2, 0.06),
                                               ("cap", -0.42, 0.2, -0.32, 0.18, 0.05)]),
    ("Southern Strip Mines", "strip", 1170, 0, [("cap", -0.72, 0.48, -0.2, 0.42, 0.055),
                                                ("cap", -0.2, 0.42, -0.08, 0.5, 0.045)]),
    ("Eroded Canyons", "canyon", 1171, 0, [("cap", 0.35, -0.1, 0.72, -0.48, 0.07), ("ell", 0.48, -0.18, 0.1, 0.07, 30)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.4, 0.55), "wastes"), PORT_STATE: ((0.82, 0.05), "wastes"), 755: ((0.0, -0.32), "badlands"),
         756: ((-0.05, 0.08), "wastes"), 757: ((-0.62, -0.35), "wastes"), 758: ((-0.35, 0.78), "wastes"),
         759: ((0.6, -0.3), "badlands")}
STATE_NAMES = {CAPITAL: "Southeast Spaceport District", PORT_STATE: "Shipyard Coast", 755: "Stormward Foothills",
               756: "Refinery Belt", 757: "Western Wastes", 758: "Southern Works", 759: "Northeast Badlands",
               1168: "Northern Range", 1169: "Western Strip Mines", 1170: "Southern Strip Mines", 1171: "Eroded Canyons"}
IMPASSABLE = {1168, 1169, 1170, 1171}
# victory points: (state, feature or kind, name, value). Legends: Spaceport Southeast II, the shipyards, the weather
# station; invented: the other spaceports, the foundries, Refinery Row
VPS = [(CAPITAL, "spaceport", CAPITAL_VP, 10), (CAPITAL, "city", "Southeast Foundries", 3),
       (CAPITAL, "Spaceport Southeast I", "Spaceport Southeast I", 2), (PORT_STATE, "shipyard", "Bonadan Shipyards", 5),
       (755, "station", "Weather Control Station", 3), (756, "refinery", "Refinery Row", 3),
       (757, "spaceport", "Spaceport West", 2), (758, "spaceport", "Spaceport South", 2),
       (759, "spaceport", "Spaceport Northeast", 2)]

# terrain (planet_terrain_gen.py --planet Bonadan; operators: planet_terrain_gen.zone_repaint). Heights in heightmap
# steps above the base. Legends look: yellow parched eroded ground, "rust-red strips" seen from space (here the strip
# mines and the canyons, cut down into the wastes), no flora: derricks, tanks, slag heaps and stacks instead
RUSTROCK = [24, ("BROWNMTN", ">", 0.55), ("BROWN", "<", 0.2)]


def pits(ctx):
    """the strip mines and canyons: cut down from the wastes in benches (the trenches stay above the water plane)"""
    z, rel, rough = ctx["z"], ctx["rel"], ctx["rough"]
    for k, step, width, floor in ((9, 2.0, 1.3, 1.0), (10, 2.6, 1.8, 0.5)):
        m = ctx["sub"] & (z == k)
        d = ndi.distance_transform_edt(m)
        top = 9 + 2 * rough
        ctx["rel"] = rel = np.where(m, np.maximum(floor, top - step * np.floor(d / width) - rough), rel)


TERRAIN_CFG = dict(
    seed=86, base=9, rough=2, open=(1, 2),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 8, 3, 6), tex=["SAND", ("BROWN", ">", 0.62), (24, ">", 0.85), ("DUNES", "<", 0.18)],
                props=[(94, 0.1), (92, 0.06), (93, 0.03), (50, 0.04)], clusters=[(9, 0.6, [(92, 0.35), (94, 0.3)])]),
        2: dict(relief=("rolling", 10, 7, 4), tex=["BROWN", ("SAND", "<", 0.35), (24, ">", 0.7)],
                props=[(48, 0.08), (94, 0.08), (92, 0.05)]),                                         # eroded badlands
        3: dict(relief=("flat", 9), tex=25),                                                         # landing grids
        4: dict(relief=("ramp_top", 11, 9, 5), tex="URBAN", props=[(95, 0.05)]),                     # the foundries
        5: dict(relief=("flat", 9), tex="URBAN", props=[(93, 0.12), (95, 0.08)]),                    # Refinery Row
        6: dict(relief=("flat", 9), tex="URBAN", props=[(93, 0.06)]),                                # the shipyards
        7: dict(relief=("flat", 16), tex=25),                                                        # station terrace
        8: dict(relief=("spires", 16, 8, 0.07, (1.5, 3.2), (18, 40)), tex=RUSTROCK, props=[(48, 0.06)]),
        9: dict(tex=[24, ("BROWNMTN", ">", 0.6)], props=[(92, 0.05), (94, 0.08)]),                  # strip mines (pits)
        10: dict(tex=RUSTROCK, props=[(48, 0.05)]),                                                  # canyons (pits)
    },
    steep=("ROCK2", 7, (1, 2, 8)),
    city={4: 19, 5: 19, 6: 19},   # map/cities.txt 19: Bonadan's industrial cities (military_buildings.py bon_city)
    prop_clear=1.8,
    hook=pits,
)
def orbit(ctx):
    """the orbital shipyard (user, 2026-10-15): its origin is the middle of its arc, out in space east of the planet;
    the arc itself (radius, end angles) is built into the mesh (military_buildings.BON_ORBIT_R / BON_ARC)"""
    import military_buildings as mb
    (cy, cx), mid = ctx["z"]["centre"], math.radians(sum(mb.BON_ARC) / 2)
    ctx["put"]("hod_bon_shipyard", 1.0, cy - mb.BON_ORBIT_R * math.sin(mid), cx + mb.BON_ORBIT_R * math.cos(mid))


# models (military_buildings.py place Bonadan): big, custom (user rule 2026-10-14); the shipyard floats in orbit
PLACEMENT = dict(
    new_models={"hod_bon_spaceport", "hod_bon_shipyard", "hod_bon_weather"},
    items=[("hod_bon_spaceport", 1.0, ("at_vp", CAPITAL_VP)),
           ("hod_bon_weather", 1.0, ("at_vp", "Weather Control Station"))],
    clear={"hod_bon_spaceport": 5.5, "hod_bon_weather": 4.6},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (bonadan_map.py)\n{imp}"
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
