"""Ossus, the ancient Jedi world, as one battlefield at the start (976, before the Clone Wars) (research:
WIPGFX/research/ossus/). Canon and Legends agree: once home of the Great Jedi Library and the First Temple (the Jedi
Praxeum, where Odan-Urr trained under Master Ooroo), devastated by the Cron Supernova some four thousand years ago;
now a world of ruins, of hills, bamboo forests, mountains, gorges and caves (canon terrain; Legends: hills, mountains,
gorges, forests, caves; temperate), where the masked Ysanna tribes live in the nitrogen-rich valleys near the Eocho
Mountains and revere the ruins, and Jedi archaeologists dig (Legends: "a planet of archaeological importance").
Stated places: Knossa (Legends capital), built of stone and bronzium, its squat domes high in the western Eocho
Mountains, far south of the equator; the Knossa Spaceport, a promenade wrapped round Agorn Mountain on its outskirts;
the Eye of Ashlanae vergence on one of its peaks; the Great Jedi Library on a hill in the Ooroo Canyon, several days'
pilgrimage from Knossa and Ossus City; Ossus City, a modest village in a tranquil valley; the Imhar Canyon, the Great
North Imhar River, the Knossos Plateau, the Trawormatt Mountains, the Gardens of T'alla. Owner: CIS (as before).
LAYOUT IS A DESIGN CHOICE beyond those: the Eocho Mountains across the south, Knossa in their western basin and its
spaceport round Agorn Mountain, the Ysanna valleys at their eastern foot; the Ooroo Canyon lands in the north, scorched
barrens round the library; the Trawormatt Mountains in the north-west; Ossus City and the Gardens in a central-east
valley; the First Temple in the bamboo forest to the north-east; the Imhar Canyon cutting in from the east rim.
Invented names: the Ysanna camps, the archaeology camp, the state names except the stated places.
    python "WIPGFX/plans & scripts/ossus_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ossus_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 63 province ids are kept (strategic region unchanged); only the pixels move.
Run order: ossus_map.py -> planet_terrain_gen.py --planet Ossus -> military_buildings.py models hod_oss
-> military_buildings.py place Ossus -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Ossus"
ZONES_JSON = "WIPGFX/Assets/ossus_zones.json"
ZONES_PNG = "WIPGFX/Assets/ossus_zones.png"
KIND = {"hills": 1, "bamboo": 2, "ruins": 3, "temple": 4, "library": 5, "valley": 6, "range": 7, "canyon": 8,
        "barrens": 9, "plateau": 10, "spaceport": 11, "camp": 12, "gardens": 13}
TERRAIN = {"hills": "hills", "bamboo": "forest", "ruins": "urban", "temple": "hills", "library": "hills",
           "valley": "plains", "range": "mountain", "canyon": "mountain", "barrens": "desert", "plateau": "hills",
           "spaceport": "hills", "camp": "plains", "gardens": "forest"}
SEED = 194
CAPITAL = 194
CAPITAL_VP = "Ruins of Knossa"
PORT_STATE = CAPITAL                 # the naval base (old Ossus file): Knossa reaches the rim
OWNER = "CIS"
WARP = (0.12, 7)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 42                 # user rule: passable provinces outnumber impassable
STRAIGHT = {"camp", "temple", "library"}   # drawn unwarped: small sites would tear apart
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Ruins of Knossa", "ruins", CAPITAL, 2, [("ell", -0.56, 0.34, 0.17, 0.14, 10)]),
    ("Agorn Mountain", "spaceport", CAPITAL, 1, [("ell", -0.3, 0.44, 0.13, 0.12, 0)]),
    ("Knossos Plateau", "plateau", CAPITAL, 2, [("ell", -0.42, -0.05, 0.16, 0.12, -20)]),
    ("Great Jedi Library", "library", 285, 1, [("ell", 0.02, -0.56, 0.1, 0.09, 0)]),
    ("Archaeology Camp", "camp", 285, 1, [("ell", 0.26, -0.64, 0.12, 0.11, 0)]),
    ("First Temple", "temple", 284, 1, [("ell", 0.6, -0.4, 0.1, 0.09, 0)]),
    ("Ossus City", "ruins", 287, 1, [("ell", 0.24, -0.06, 0.1, 0.09, 0)]),
    ("Gardens of T'alla", "gardens", 287, 1, [("ell", 0.04, 0.12, 0.13, 0.11, 15)]),
    ("Ysanna Camp", "camp", 286, 1, [("ell", 0.14, 0.42, 0.12, 0.11, 0)]),
    ("Eocho Mountains", "range", 1177, 0, [("cap", -0.8, 0.52, -0.25, 0.76, 0.13), ("cap", -0.25, 0.76, 0.42, 0.74, 0.11),
                                           ("ell", -0.62, 0.66, 0.16, 0.14, 10), ("ell", 0.05, 0.92, 0.45, 0.14, 0)]),
    ("Trawormatt Mountains", "range", 1178, 0, [("cap", -0.85, -0.25, -0.38, -0.66, 0.11),
                                                 ("ell", -0.66, -0.5, 0.14, 0.12, 30)]),
    ("Imhar Canyon", "canyon", 1179, 0, [("cap", 1.05, 0.16, 0.66, 0.12, 0.1), ("cap", 0.66, 0.12, 0.46, 0.28, 0.085)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((-0.5, 0.15), "bamboo"), 284: ((0.55, -0.42), "bamboo"), 285: ((0.0, -0.62), "barrens"),
         286: ((0.3, 0.46), "valley"), 287: ((0.25, -0.02), "valley")}
STATE_NAMES = {CAPITAL: "Knossa", 284: "First Temple Woods", 285: "Ooroo Canyon", 286: "Ysanna Valleys",
               287: "Ossus City Valley", 1177: "Eocho Mountains", 1178: "Trawormatt Mountains", 1179: "Imhar Canyon"}
IMPASSABLE = {1177, 1178, 1179}
# victory points: (state, feature or kind, name, value). Stated: Knossa and its spaceport (Agorn Mountain), the Great
# Jedi Library, the First Temple, Ossus City, the Gardens of T'alla, the Knossos Plateau; invented: the camps
VPS = [(CAPITAL, "ruins", CAPITAL_VP, 5), (CAPITAL, "spaceport", "Knossa Spaceport Ruins", 2),
       (CAPITAL, "plateau", "Knossos Plateau", 1), (285, "library", "Ruins of the Great Jedi Library", 5),
       (285, "camp", "Archaeology Camp", 1), (284, "temple", "Ruins of the First Temple", 3),
       (287, "ruins", "Ossus City", 2), (287, "gardens", "Gardens of T'alla", 1), (286, "camp", "Ysanna Camp", 2)]


# terrain (planet_terrain_gen.py --planet Ossus; operators: planet_terrain_gen.zone_repaint). Heights in heightmap
# steps above the base. Canon / Legends: hills, bamboo forests, mountains, gorges; temperate. Bamboo hills, grassy
# valleys, green mountains, scorched barrens round the Great Library (the Cron Supernova's scars, design choice), the
# Imhar Canyon cut down as a gorge (canyon hook), ruins overgrown; uneti groves in the Gardens of T'alla


def canyon(ctx):
    """the Imhar Canyon: a gorge cut down from the land in steep benches to a floor just above the water plane"""
    z, rel, rough = ctx["z"], ctx["rel"], ctx["rough"]
    m = ctx["sub"] & (z == 8)
    d = ndi.distance_transform_edt(m)
    ctx["rel"] = np.where(m, np.maximum(0.5, 10 + 2 * rough - 3.2 * np.floor(d / 0.9)), rel)


TERRAIN_CFG = dict(
    seed=194, base=5, rough=2, open=(1, 2, 6, 9, 12, 13),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 6, 5, 5), tex=["GRASSHILL", ("HILLS", ">", 0.6)], props=[(106, 0.12), (104, 0.1)]),
        2: dict(relief=("rolling", 5, 4, 5), tex=["FOREST", ("GRASSHILL", ">", 0.62)],                 # bamboo forest
                props=[(104, 0.55), (105, 0.06), (106, 0.1)], clusters=[(6, 0.5, [(104, 0.9)])]),
        3: dict(relief=("ramp_top", 8, 5, 4), tex="URBAN", props=[(107, 0.12), (106, 0.05)]),       # ruined cities
        4: dict(relief=("flat", 6), tex=25, props=[(104, 0.06)]),                                   # First Temple
        5: dict(relief=("ramp_top", 11, 4, 4), tex=["BROWN", (25, ">", 0.5)], props=[(107, 0.15)]),  # library hill
        6: dict(relief=("rolling", 3, 3, 6), tex=["GRASS", ("SAVANNA", ">", 0.65)],                  # the valleys
                props=[(106, 0.12), (105, 0.04), (107, 0.04)]),
        7: dict(relief=("spires", 16, 9, 0.08, (1.5, 3.0), (22, 45)), tex=["GREENMTN", ("ROCK", ">", 0.55)],
                props=[(104, 0.04)]),
        8: dict(tex=["ROCK2", ("BROWN", ">", 0.5)]),                                                 # Imhar Canyon
        9: dict(relief=("rolling", 4, 3, 5), tex=["BROWN", ("ROCK", ">", 0.6), ("SAND", "<", 0.2)],   # scorched barrens
                props=[(107, 0.12), (106, 0.05)]),
        10: dict(relief=("mesa", 6, 16, 2.5, (4, 0.6)), tex=["GRASSHILL", ("ROCK", ">", 0.6)],         # Knossos Plateau
                 props=[(106, 0.1), (107, 0.05)]),
        11: dict(relief=("ramp_top", 12, 5, 3), tex=["ROCK", (25, ">", 0.5)]),                        # Agorn Mountain
        12: dict(relief=("rolling", 3, 1, 6), tex=26, props=[(106, 0.06)]),                         # camps
        13: dict(relief=("rolling", 4, 2, 5), tex="GRASS", props=[(105, 0.35), (106, 0.2)]),          # the Gardens
    },
    steep=("ROCK2", 7, (1, 2, 6, 9, 10)),
    city={3: 23, 12: 24},   # map/cities.txt 23: Ossan ruins, 24: Ysanna camps (military_buildings.py oss_ruin, ysanna_camp)
    prop_clear=1.6,
    hook=canyon,
)
# models (military_buildings.py place Ossus): big, custom (user rule 2026-10-14); Knossa and Agorn Mountain stand close
# on a small planet (~35 px radius): a little smaller
PLACEMENT = dict(
    new_models={"hod_oss_library", "hod_oss_knossa", "hod_oss_agorn", "hod_oss_temple"},
    items=[("hod_oss_library", 1.0, ("at_vp", "Ruins of the Great Jedi Library")),
           ("hod_oss_knossa", 0.8, ("at_vp", CAPITAL_VP)),
           ("hod_oss_agorn", 0.8, ("at_vp", "Knossa Spaceport Ruins")),
           ("hod_oss_temple", 1.0, ("at_vp", "Ruins of the First Temple"))],
    clear={"hod_oss_library": 6.0, "hod_oss_knossa": 4.6, "hod_oss_agorn": 4.0, "hod_oss_temple": 5.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ossus_map.py)\n{imp}"
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
