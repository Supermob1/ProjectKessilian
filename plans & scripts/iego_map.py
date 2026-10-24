"""Iego, the world of a thousand moons in the Ash Worlds, as one battlefield in the Clone Wars (research:
WIPGFX/research/iego/). CANON: a hot desert surface covered in basaltic spires and canyons, where the reeksa
(enormous carnivorous plants) grow; xandu in the skies; Cliffhold, a spaceport city built directly into the face of
a basalt cliff, quiet since the spice convoys stopped; in the Clone Wars the Separatists' LaserWeb Defense Station
kept anyone from leaving (TCW "Mystery of a Thousand Moons"; in orbit, user 2026-10-16). LEGENDS (user, 2026-10-16: use them): The Scatter; the
Choir Alignment, an artificial valley shaped like a nine-pointed star, between the Scatter and the Boneyard; the
Boneyard, the largest of Iego's bone piles, giant skeletons of unknown creatures, north of the Scatter; Rawk's Nest.
User (2026-10-16): the LaserWeb station already stands, in space east of the planet (PLACEMENT hook); the planet
stays IEG. Cliffhold's city (the first design, scaled down) sits on the high escarpment's face; the terrain is the mountain.
LAYOUT IS A DESIGN CHOICE except the Legends order (Boneyard north of the Scatter, the Choir Alignment between them):
Cliffhold at the foot of a long basalt escarpment in the centre-east (impassable), the Legends chain north to south
down the west, the reeksa canyons in the centre-south, the old spice convoy depot on heights in the north-east by a forest of
basalt spires (impassable), Rawk's Nest in the south-eastern hills, open desert between.
Canon names: Cliffhold, the LaserWeb Defense Station, the reeksa. Legends: The Scatter, the Choir Alignment, the
Boneyard, Rawk's Nest. Invented: every state name, the Reeksa Canyons VP, the Spice Wells, the Spice Convoy Depot
(the convoys are canon), the Xandu Roost, the
Basalt Escarpment, the Spire Forest.
    python "WIPGFX/plans & scripts/iego_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/iego_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 202 province ids are kept (strategic region unchanged); only the pixels move.
Run order: iego_map.py -> flora_props.py (ieg_*) -> planet_terrain_gen.py --planet Iego -> military_buildings.py
models hod_ieg -> military_buildings.py place Iego -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Iego"
ZONES_JSON = "WIPGFX/Assets/iego_zones.json"
ZONES_PNG = "WIPGFX/Assets/iego_zones.png"
KIND = {"desert": 1, "canyons": 2, "city": 3, "station": 4, "boneyard": 5, "scatter": 6, "choir": 7, "badlands": 8,
        "escarpment": 9, "spires": 10}
TERRAIN = {"desert": "desert", "canyons": "hills", "city": "urban", "station": "hills", "boneyard": "desert",
           "scatter": "hills", "choir": "hills", "badlands": "hills", "escarpment": "mountain", "spires": "mountain"}
SEED = 76
CAPITAL = 76
CAPITAL_VP = "Cliffhold"
PORT_STATE = 76
OWNER = {s: "IEG" for s in (76, 685, 686, 687, 688, 689, 690, 691, 1195, 1196)}
WARP = (0.13, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 128                # user rule: passable provinces outnumber impassable (~128 / 74)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Cliffhold", "city", CAPITAL, 4, [("ell", 0.18, 0.12, 0.15, 0.09, -30)]),
    ("Spice Convoy Depot", "station", 686, 2, [("ell", 0.42, -0.5, 0.09, 0.07, 0)]),
    ("Choir Alignment", "choir", 689, 1, [("ell", -0.42, -0.08, 0.07, 0.07, 0)]),
    ("The Boneyard", "boneyard", 689, 3, [("ell", -0.45, -0.42, 0.14, 0.1, 15)]),
    ("The Scatter", "scatter", 688, 4, [("ell", -0.45, 0.32, 0.17, 0.12, -10)]),
    ("Reeksa Canyons", "canyons", 687, 5, [("cap", -0.15, 0.45, 0.2, 0.68, 0.09), ("ell", 0.0, 0.55, 0.12, 0.08, 40)]),
    ("Rawk's Nest", "badlands", 690, 1, [("ell", 0.6, 0.48, 0.06, 0.05, 0)]),
    ("Spice Wells", "city", 691, 1, [("ell", -0.05, 0.84, 0.07, 0.05, 0)]),
    ("Xandu Roost", "badlands", 685, 1, [("ell", -0.05, -0.62, 0.07, 0.05, 0)]),
    # the basalt escarpment Cliffhold is cut into: a long wall behind the city (its north-east), never rim to rim
    ("Basalt Escarpment", "escarpment", 1195, 0, [("cap", -0.05, -0.12, 0.45, 0.02, 0.07),
                                                  ("cap", 0.45, 0.02, 0.72, 0.22, 0.06)]),
    # the spire forest over the north-east rim
    ("Spire Forest", "spires", 1196, 0, [("ell", 0.55, -0.85, 0.42, 0.2, -25), ("cap", 0.75, -0.5, 0.92, -0.2, 0.08),
                                         ("cap", 0.2, -0.75, 0.15, -0.6, 0.06)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.25, 0.25), "desert"), 685: ((-0.05, -0.6), "desert"), 686: ((0.45, -0.3), "badlands"),
         687: ((0.05, 0.5), "badlands"), 688: ((-0.55, 0.35), "desert"), 689: ((-0.5, -0.3), "desert"),
         690: ((0.65, 0.45), "badlands"), 691: ((-0.05, 0.85), "desert")}
STATE_NAMES = {CAPITAL: "Cliffhold Reaches", 685: "Xandu Flats", 686: "Convoy Heights", 687: "Reeksa Canyons",
               688: "The Scatter", 689: "Boneyard Wastes", 690: "Rawk's Hills", 691: "Southern Spice Wells",
               1195: "Basalt Escarpment", 1196: "Spire Forest"}
IMPASSABLE = {1195, 1196}
# victory points: (state, feature or kind, name, value)
VPS = [(CAPITAL, "Cliffhold", CAPITAL_VP, 10), (686, "Spice Convoy Depot", "Spice Convoy Depot", 2),
       (689, "The Boneyard", "The Boneyard", 3), (689, "Choir Alignment", "Choir Alignment", 2),
       (688, "The Scatter", "The Scatter", 2), (687, "Reeksa Canyons", "Reeksa Canyons", 2),
       (690, "Rawk's Nest", "Rawk's Nest", 1), (691, "Spice Wells", "Spice Wells", 2), (685, "Xandu Roost", "Xandu Roost", 1)]

# terrain (planet_terrain_gen.py --planet Iego). Heights in heightmap steps above the base. Canon look (TCW): hot
# orange-tan desert, dark basalt spires and canyon walls, the reeksa in the canyons
BASALT = ["ROCK", ("ROCK2", ">", 0.55), ("BROWNMTN", "<", 0.15)]


def carve(ctx):
    """the reeksa canyons cut down into the ground in benches, the Choir Alignment a sunken nine-pointed star"""
    z, rel, rough = ctx["z"], ctx["rel"], ctx["rough"]
    m = ctx["sub"] & (z == 2)
    d = ndi.distance_transform_edt(m)
    rel = np.where(m, np.maximum(1.0, 8 + rough - 2.2 * np.floor(d / 1.1)), rel)
    m = ctx["sub"] & (z == 7)
    if m.any():
        yy, xx = ctx["yy"], ctx["xx"]
        cy, cx = yy[m].mean(), xx[m].mean()
        a, r = np.arctan2(yy - cy, xx - cx), np.hypot(yy - cy, xx - cx)
        star = r < 2.2 + 1.6 * (0.5 + 0.5 * np.cos(9 * a))              # nine points
        rel = np.where(m, np.where(star, 2.0, 7.0), rel)
    ctx["rel"] = rel


TERRAIN_CFG = dict(
    seed=76, base=5, rough=2, open=(1, 6, 8),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 5, 3, 5), tex=["SAND", ("BROWN", ">", 0.6), ("DUNES", "<", 0.2)],
                props=[(120, 0.04), (119, 0.02)]),                                          # open desert, lone spires
        2: dict(tex=["BROWN", ("ROCK2", ">", 0.6)], props=[(119, 0.3), (120, 0.06)]),        # reeksa canyons (carve)
        3: dict(relief=("ramp_top", 7, 5, 4), tex="URBAN"),                                  # Cliffhold, the spice wells
        4: dict(relief=("mesa", 6, 14, 3, (4, 0.6)), tex=["ROCK2", ("BROWN", ">", 0.6)]),     # the convoy depot heights
        5: dict(relief=("rolling", 5, 2, 5), tex=["SAND", ("BROWN", ">", 0.55)], props=[(121, 0.22)]),   # the Boneyard
        6: dict(relief=("rolling", 6, 4, 3), tex=["BROWN", ("ROCK", ">", 0.6), ("SAND", "<", 0.25)],
                props=[(120, 0.12)]),                                                         # The Scatter: strewn rock
        7: dict(tex=["ROCK2", ("SAND", ">", 0.6)]),                                           # the Choir Alignment (carve)
        8: dict(relief=("rolling", 7, 6, 4), tex=["BROWN", ("ROCK2", ">", 0.6), ("SAND", "<", 0.2)],
                props=[(120, 0.08), (119, 0.03)]),                                            # badlands
        9: dict(relief=("mesa", 10, 58, 2.0, (5, 0.55)), tex=BASALT, props=[(120, 0.08)]),   # the basalt escarpment: sheer, high
        10: dict(relief=("spires", 10, 6, 0.09, (1.2, 2.6), (14, 32)), tex=BASALT),          # the spire forest
    },
    steep=("ROCK", 6, (2, 4, 8, 9, 10)),
    city={3: 31},   # map/cities.txt 31: Iegoan basalt towns (military_buildings.py ieg_city)
    prop_clear=1.8,
    hook=carve,
)

def orbit(ctx):
    """the LaserWeb Defense Station in space (user, 2026-10-16): its centre military_buildings.IEG_WEB_AT
    (distance, bearing) from the planet's centre, in the open space east of the disc; Cliffhold on the cliff face"""
    import military_buildings as mb
    (cy, cx), (r, b) = ctx["z"]["centre"], (mb.IEG_WEB_AT[0], math.radians(mb.IEG_WEB_AT[1]))
    ctx["put"]("hod_ieg_laserweb", 1.0, cy - r * math.sin(b), cx + r * math.cos(b))
    # Cliffhold on the escarpment's face (user, 2026-10-16: smaller, fitted into the mountain): the escarpment pixel
    # nearest the city's VP, the model's origin out in front of it so its face (0.85 model units behind the origin)
    # meets the terrain wall's edge and its back sinks into the rock
    vy, vx = ctx["vp_at"][CAPITAL_VP]
    ys, xs = np.nonzero(ctx["zone"] == KIND["escarpment"])
    i = int(np.argmin(np.hypot(ys - vy, xs - vx)))
    ny, nx = vy - ys[i], vx - xs[i]
    d = max(math.hypot(ny, nx), 1e-6)
    off = 0.5 + 0.85 * mb.IEG_CLIFF_SCALE
    ctx["put"]("hod_ieg_cliffhold", mb.IEG_CLIFF_SCALE, ys[i] + ny / d * off, xs[i] + nx / d * off)


# models (military_buildings.py place Iego): big, custom (user rule 2026-10-14); the LaserWeb station floats in orbit
PLACEMENT = dict(
    new_models={"hod_ieg_cliffhold", "hod_ieg_laserweb", "hod_ieg_choir", "hod_ieg_boneyard"},
    items=[("hod_ieg_choir", 1.0, ("at_vp", "Choir Alignment")),
           ("hod_ieg_boneyard", 1.0, ("at_vp", "The Boneyard"))],
    clear={"hod_ieg_choir": 5.5, "hod_ieg_boneyard": 7.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (iego_map.py)\n{imp}"
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
