"""Pammant, the Quarren shipbuilding colony of the Calamari sector, as one battlefield in the Clone Wars (research:
WIPGFX/research/pammant/). CANON (user, 2026-10-16: intact, Clone Wars, Confederacy): a colony world of Quarren
engineers whose factories build the Separatist navy (the Providence-class Invisible Hand, Colicoid Swarm and Lucid
Voice, the Subjugator-class Malevolence, built there in secret); exports starships. LEGENDS
adds: "tunneled" terrain, the shipyards in the world's underground tunnels, at least two billion inhabitants, and the
Pammant Docks, a ring-shaped shipyard in orbit (Free Dac Volunteers Engineering Corps). Its 19 BBY destruction is
ignored. The orbital Pammant Docks (user, 2026-10-16: "shipyard should be in space") hold the Separatist ships of
WIPGFX/separatists ships 3d (Invisible Hand, Malevolence): PLACEMENT hook, military_buildings.py pam_docks.
LAYOUT IS A DESIGN CHOICE: a dark crust honeycombed with tunnels; the Quarren capital and the QFD foundries in the
south-centre, the QFD heavy-lift spaceport in the east (hull sections lifted to the orbital docks), a ridge of shattered
rock over the north, a great sinkhole (a collapsed cavern) north of the centre, a chain of collapsed galleries in the
west, shaft fields round the sinkhole, brine lakes in the south-west (Quarren are amphibious), the Mon Calamari
enclave in the west (the old owners MNC keep their two states).
Canon names: the QFD (Free Dac Volunteers Engineering Corps) foundries. Invented (Quarren-style): every state
name, the QFD Lift Port, Tessar Deep, Dac Landing, Nosser Shafts, Ri'kel Vents, Brinewater Hold, QFD Droid Works, the
sinkhole, ridge and galleries.
    python "WIPGFX/plans & scripts/pammant_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/pammant_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 199 province ids are kept (strategic region unchanged); only the pixels move.
Run order: pammant_map.py -> planet_terrain_gen.py --planet Pammant -> military_buildings.py models hod_pam
-> military_buildings.py place Pammant -> planet_terrain_gen.py --globe-texture.
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

PLANET = "Pammant"
ZONES_JSON = "WIPGFX/Assets/pammant_zones.json"
ZONES_PNG = "WIPGFX/Assets/pammant_zones.png"
KIND = {"crust": 1, "flats": 2, "city": 3, "foundry": 4, "liftport": 5, "shafts": 6, "brine": 7, "sinkhole": 8,
        "ridge": 9, "galleries": 10}
TERRAIN = {"crust": "hills", "flats": "plains", "city": "urban", "foundry": "urban", "liftport": "urban",
           "shafts": "hills", "brine": "marsh", "sinkhole": "mountain", "ridge": "mountain", "galleries": "mountain"}
SEED = 78
CAPITAL = 78
CAPITAL_VP = "Tessar Deep"
PORT_STATE = 700
OWNER = {701: "MNC", 705: "MNC"}     # the Mon Calamari enclave keeps its old owner; everything else Quarren (QUA)
WARP = (0.13, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 128                # user rule: passable provinces outnumber impassable (~128 / 71)
STRAIGHT = {"liftport"}              # drawn unwarped: the port's straight apron
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Tessar Deep", "city", CAPITAL, 4, [("ell", -0.12, 0.22, 0.17, 0.12, -15)]),
    ("QFD Foundries", "foundry", CAPITAL, 3, [("ell", 0.14, 0.36, 0.13, 0.09, 20)]),
    ("QFD Lift Port", "liftport", PORT_STATE, 3, [("rect", 0.55, -0.12, 0.17, 0.07, -35)]),
    ("Dac Landing", "city", 701, 1, [("ell", -0.62, -0.28, 0.08, 0.06, 10)]),
    ("QFD Droid Works", "foundry", 703, 2, [("ell", 0.42, 0.55, 0.1, 0.07, -30)]),
    ("Ri'kel Vents", "foundry", 704, 1, [("ell", -0.05, 0.78, 0.08, 0.06, 0)]),
    ("Brinewater Hold", "city", 705, 1, [("ell", -0.5, 0.42, 0.07, 0.06, 0)]),
    ("Brine Lakes", "brine", 705, 4, [("ell", -0.66, 0.2, 0.12, 0.08, 40), ("ell", -0.38, 0.62, 0.13, 0.07, -20),
                                      ("cap", -0.66, 0.2, -0.45, 0.55, 0.05)]),
    ("Nosser Shafts", "shafts", 702, 4, [("ell", -0.28, -0.3, 0.17, 0.12, 25), ("ell", 0.35, -0.42, 0.12, 0.09, -20)]),
    # the great sinkhole: a collapsed cavern north of the centre, ragged lobes
    ("Great Sinkhole", "sinkhole", 1190, 0, [("ell", 0.05, -0.18, 0.2, 0.14, 20), ("ell", 0.2, -0.3, 0.1, 0.08, -10),
                                             ("cap", -0.08, -0.12, -0.18, -0.02, 0.06)]),
    # the shattered ridge over the north rim, spurs reaching south
    ("Shattered Ridge", "ridge", 1191, 0, [("ell", 0.0, -0.95, 0.7, 0.19, 0), ("cap", -0.5, -0.7, -0.4, -0.5, 0.08),
                                           ("cap", 0.45, -0.7, 0.58, -0.52, 0.07), ("cap", 0.05, -0.7, 0.08, -0.55, 0.08)]),
    # collapsed galleries: a broken chain across the west (never rim to rim)
    ("Collapsed Galleries", "galleries", 1192, 0, [("cap", -0.8, -0.04, -0.48, 0.02, 0.055),
                                                   ("cap", -0.48, 0.02, -0.2, 0.1, 0.05),
                                                   ("ell", -0.62, 0.0, 0.07, 0.05, 30)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.0, 0.3), "flats"), PORT_STATE: ((0.62, -0.1), "crust"), 701: ((-0.62, -0.3), "crust"),
         702: ((-0.15, -0.42), "crust"), 703: ((0.45, 0.5), "flats"), 704: ((0.0, 0.8), "flats"),
         705: ((-0.55, 0.42), "flats")}
STATE_NAMES = {CAPITAL: "Colony Deeps", PORT_STATE: "Liftport Basin", 701: "Calamari Enclave", 702: "Nosser Shafts",
               703: "Foundry Reach", 704: "Southern Vents", 705: "Brine Lakes", 1190: "Great Sinkhole",
               1191: "Shattered Ridge", 1192: "Collapsed Galleries"}
IMPASSABLE = {1190, 1191, 1192}
# victory points: (state, feature or kind, name, value). Canon: the QFD foundries; the rest invented
VPS = [(CAPITAL, "Tessar Deep", CAPITAL_VP, 10), (CAPITAL, "QFD Foundries", "QFD Foundries", 3),
       (PORT_STATE, "liftport", "QFD Lift Port", 5), (701, "city", "Dac Landing", 2),
       (702, "shafts", "Nosser Shafts", 2), (703, "foundry", "QFD Droid Works", 3), (704, "foundry", "Ri'kel Vents", 2),
       (705, "city", "Brinewater Hold", 2)]

# terrain (planet_terrain_gen.py --planet Pammant; operators: planet_terrain_gen.zone_repaint). Heights in heightmap
# steps above the base. Legends: "tunneled": dark grey crust, shaft mouths and collapsed caverns cut down into it,
# industry (tanks, stacks, slag) instead of flora, still brine lakes
CRUST = ["ROCK2", ("HILLS", ">", 0.62), ("BROWN", "<", 0.18)]


def holes(ctx):
    """the sinkhole and the galleries cut down in benches; the shaft fields pocked with shaft mouths"""
    z, rel, rough, rng = ctx["z"], ctx["rel"], ctx["rough"], ctx["rng"]
    for k, step, width, floor in ((8, 2.4, 1.2, 0.5), (10, 2.0, 1.0, 1.0)):
        m = ctx["sub"] & (z == k)
        d = ndi.distance_transform_edt(m)
        rel = np.where(m, np.maximum(floor, 9 + 2 * rough - step * np.floor(d / width) - rough), rel)
    m = ctx["sub"] & (z == 6)
    for r, c in np.argwhere(m)[rng.random(int(m.sum())) < 0.05]:
        d = np.hypot(ctx["yy"] - r, ctx["xx"] - c)
        rel = np.where(m & (d < 1.6), np.minimum(rel, 2.0 + d), rel)
    ctx["rel"] = rel


TERRAIN_CFG = dict(
    seed=78, base=5, rough=2, open=(1, 2),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 7, 6, 4), tex=CRUST, props=[(48, 0.08), (94, 0.06), (92, 0.04)]),   # tunneled crust
        2: dict(relief=("rolling", 5, 2, 6), tex=["BROWN", ("ROCK2", ">", 0.6), (24, "<", 0.15)],
                props=[(94, 0.08), (93, 0.04), (95, 0.03)], clusters=[(9, 0.62, [(93, 0.3), (95, 0.25)])]),  # flats
        3: dict(relief=("ramp_top", 8, 5, 5), tex="URBAN", props=[(95, 0.04)]),                      # the cities
        4: dict(relief=("flat", 5), tex="URBAN", props=[(93, 0.12), (95, 0.1)]),                     # foundries
        5: dict(relief=("flat", 5), tex=25),                                                         # lift port apron
        6: dict(relief=("rolling", 6, 3, 5), tex=["ROCK2", (24, ">", 0.55)], props=[(92, 0.08), (48, 0.05)]),
        7: dict(relief=("flat", -3), tex="WATER"),                                                   # brine lakes
        8: dict(tex=["ROCK", ("ROCK2", ">", 0.5)], props=[(48, 0.04)]),                             # sinkhole (holes)
        9: dict(relief=("spires", 14, 7, 0.07, (1.5, 3.0), (16, 34)), tex=["ROCK", ("ROCK2", ">", 0.55)],
                props=[(48, 0.06)]),                                                                 # shattered ridge
        10: dict(tex=["ROCK2", (24, ">", 0.6)], props=[(48, 0.05), (92, 0.04)]),                     # galleries (holes)
    },
    steep=("ROCK", 7, (1, 6, 9)),
    city={3: 28, 4: 28},   # map/cities.txt 28: Pammant's Quarren foundry towns (military_buildings.py pam_city)
    prop_clear=1.8,
    hook=holes,
)



def orbit(ctx):
    """the Pammant Docks in space (user, 2026-10-16): the ring's centre military_buildings.PAM_AT (distance, bearing)
    from the planet's centre, out in the open space north-east of the disc"""
    import military_buildings as mb
    (cy, cx), (r, b) = ctx["z"]["centre"], (mb.PAM_AT[0], math.radians(mb.PAM_AT[1]))
    ctx["put"]("hod_pam_docks", 1.0, cy - r * math.sin(b), cx + r * math.cos(b))


# models (military_buildings.py place Pammant): big, custom (user rule 2026-10-14); the docks float in orbit
PLACEMENT = dict(
    new_models={"hod_pam_docks", "hod_pam_liftport", "hod_pam_colony"},
    items=[("hod_pam_colony", 1.0, ("at_vp", CAPITAL_VP)),
           ("hod_pam_liftport", 1.0, ("at_vp", "QFD Lift Port"))],
    clear={"hod_pam_colony": 5.5, "hod_pam_liftport": 7.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (pammant_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {OWNER.get(sid, 'QUA')}\n\t\tadd_core_of = {OWNER.get(sid, 'QUA')}\n\t}}\n"
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
