"""Mon Cala (the map's "Mon Calamari"), the ocean homeworld of the Mon Calamari and the Quarren, as one battlefield in
the Clone Wars (research: WIPGFX/research/mon_cala/). CANON: a temperate world of oceans; coral reefs in the light of
the twin suns, bioluminescent plants in the deep; island chains of rocky cliffs, sandy beaches and dense jungle; both
peoples build their cities mostly underwater, some on the surface: Coral City (the capital), New Coral City, Dac City
(above the oceans), Bel City, Nystullum (under the northern ice floes), Quarren Town (in the depths, the Quarren
headquarters in it), Zeran Town (in the north), the Moncaladrome opera house, The Regency, the Great Ungeness Trench.
The Clone Wars split them: the Quarren sided with the Confederacy (Battle of Mon Cala).
User (2026-10-16): the ocean is passable shallow sea (an underwater battlefield, marsh terrain); the MNC / QUA split
is kept (Mon Calamari reefs, Quarren deeps).
LAYOUT IS A DESIGN CHOICE: the polar ice shelf over the north (impassable) with the floes below it (Nystullum MNC,
Zeran Town QUA); the sunlit Mon Calamari reefs and atolls in the centre and east (Coral City and the Moncaladrome,
Dac City among jungle islands, New Coral City, Bel City); the dark Quarren deeps in the west and south (Quarren Town
and the Quarren headquarters, The Regency); the Great Ungeness Trench between them (impassable), the fault line.
Canon names: every city and site above. Invented: every state name, Ungeness Watch, the islands, the Northern Ice
Shelf (the ice floes are canon, the name is not).
    python "WIPGFX/plans & scripts/mon_calamari_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/mon_calamari_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 207 province ids are kept (strategic region unchanged); only the pixels move.
Run order: mon_calamari_map.py -> flora_props.py (mcl_*) -> planet_terrain_gen.py --planet "Mon Calamari"
-> military_buildings.py models hod_mcl -> military_buildings.py place "Mon Calamari" -> planet_terrain_gen.py
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

PLANET = "Mon Calamari"
ZONES_JSON = "WIPGFX/Assets/moncala_zones.json"
ZONES_PNG = "WIPGFX/Assets/moncala_zones.png"
KIND = {"reef": 1, "deep": 2, "floes": 3, "city": 4, "qcity": 5, "surface": 6, "isles": 7, "trench": 8, "ice": 9}
TERRAIN = {"reef": "marsh", "deep": "marsh", "floes": "plains", "city": "urban", "qcity": "urban", "surface": "urban",
           "isles": "jungle", "trench": "mountain", "ice": "mountain"}
SEED = 77
CAPITAL = 77
CAPITAL_VP = "Coral City"
PORT_STATE = 692
# the Mon Calamari (MNC) hold the reefs and Nystullum, the Quarren (QUA) the deeps and Zeran Town
OWNER = {77: "MNC", 692: "MNC", 693: "MNC", 694: "MNC", 696: "MNC", 695: "QUA", 697: "QUA", 698: "QUA", 699: "QUA",
         1193: "MNC", 1194: "MNC"}
WARP = (0.13, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 132                # user rule: passable provinces outnumber impassable (~132 / 75)
STRAIGHT = set()                     # nothing drawn unwarped: no straight shapes on a sea world
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Coral City", "city", CAPITAL, 4, [("ell", 0.2, 0.02, 0.15, 0.11, 20)]),
    ("Moncaladrome", "city", CAPITAL, 1, [("ell", 0.44, -0.12, 0.06, 0.05, 0)]),
    ("Dac City", "surface", PORT_STATE, 2, [("ell", 0.72, 0.12, 0.08, 0.06, -20)]),
    ("New Coral City", "city", 693, 2, [("ell", 0.5, 0.52, 0.09, 0.07, 30)]),
    ("Bel City", "city", 694, 1, [("ell", -0.18, -0.3, 0.07, 0.06, 0)]),
    ("Nystullum", "city", 696, 1, [("ell", -0.35, -0.55, 0.07, 0.05, 0)]),
    ("Zeran Town", "qcity", 697, 1, [("ell", 0.38, -0.52, 0.07, 0.05, 0)]),
    ("Quarren Town", "qcity", 695, 3, [("ell", -0.52, 0.46, 0.14, 0.1, -20)]),
    ("Quarren Headquarters", "qcity", 695, 1, [("ell", -0.33, 0.62, 0.06, 0.05, 0)]),
    ("The Regency", "qcity", 698, 1, [("ell", 0.1, 0.8, 0.07, 0.05, 0)]),
    ("Ungeness Watch", "qcity", 699, 1, [("ell", -0.72, -0.08, 0.06, 0.05, 0)]),
    # the island chains: rocky cliffs, beaches, dense jungle
    ("Dac Isles", "isles", PORT_STATE, 3, [("cap", 0.62, -0.32, 0.86, -0.18, 0.05)]),
    ("Coral Isles", "isles", CAPITAL, 2, [("cap", 0.0, -0.16, 0.18, -0.28, 0.045)]),
    ("Sunward Atoll", "isles", 693, 2, [("cap", 0.24, 0.4, 0.3, 0.68, 0.045)]),
    ("Bel Isle", "isles", 694, 1, [("ell", 0.06, -0.46, 0.06, 0.04, 40)]),
    # the polar ice shelf over the north rim, tongues reaching south
    ("Northern Ice Shelf", "ice", 1194, 0, [("ell", 0.0, -0.97, 0.75, 0.2, 0), ("cap", -0.55, -0.75, -0.45, -0.62, 0.07),
                                            ("cap", 0.6, -0.72, 0.52, -0.62, 0.06), ("cap", 0.05, -0.8, 0.1, -0.68, 0.07)]),
    # the Great Ungeness Trench: from the west rim between the Quarren deeps and the reefs (never rim to rim)
    ("Great Ungeness Trench", "trench", 1193, 0, [("cap", -0.9, 0.12, -0.55, 0.15, 0.06),
                                                  ("cap", -0.55, 0.15, -0.2, 0.3, 0.055),
                                                  ("cap", -0.2, 0.3, 0.0, 0.55, 0.05)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.2, 0.05), "reef"), PORT_STATE: ((0.75, 0.0), "reef"), 693: ((0.5, 0.55), "reef"),
         694: ((-0.15, -0.25), "reef"), 696: ((-0.4, -0.62), "floes"), 697: ((0.4, -0.6), "floes"),
         699: ((-0.72, -0.2), "deep"), 695: ((-0.5, 0.5), "deep"), 698: ((0.05, 0.8), "deep")}
STATE_NAMES = {CAPITAL: "Coral City Reefs", PORT_STATE: "Dac Shallows", 693: "Sunward Reefs", 694: "Bel Reefs",
               696: "Nystullum Floes", 697: "Zeran Floes", 699: "Western Deeps", 695: "Quarren Deeps",
               698: "Regency Deeps", 1193: "Great Ungeness Trench", 1194: "Northern Ice Shelf"}
IMPASSABLE = {1193, 1194}
# victory points: (state, feature or kind, name, value); all canon except Ungeness Watch
VPS = [(CAPITAL, "Coral City", CAPITAL_VP, 10), (CAPITAL, "Moncaladrome", "Moncaladrome", 3),
       (PORT_STATE, "Dac City", "Dac City", 3), (693, "New Coral City", "New Coral City", 3),
       (694, "Bel City", "Bel City", 2), (696, "Nystullum", "Nystullum", 2), (697, "Zeran Town", "Zeran Town", 2),
       (695, "Quarren Town", "Quarren Town", 5), (695, "Quarren Headquarters", "Quarren Headquarters", 3),
       (698, "The Regency", "The Regency", 2), (699, "Ungeness Watch", "Ungeness Watch", 1)]

# terrain (planet_terrain_gen.py --planet "Mon Calamari"; operators: planet_terrain_gen.zone_repaint). Heights in
# heightmap steps above the base. Everything stays ABOVE the water plane (~1.3 below the base): in this mod the water
# plane draws space, so the seas are the water tile (slot 6) that gfx/FX/pdxmap.shader paints as animated water. Canon look: open ocean, coral reefs breaking
# the surface as atolls in the sunlit shallows, island chains of cliffs, beaches and jungle, ice floes in the north
TERRAIN_CFG = dict(
    seed=77, base=0, rough=2, open=(1, 2, 3),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 0.3, 1.6, 5), tex=["WATER", ("SAND", ">", 0.7)],
                props=[(116, 0.1), (118, 0.03)]),                                        # reefs, atolls breaking through
        2: dict(relief=("flat", 0.3), tex="WATER"),                                              # the deeps
        3: dict(relief=("rolling", -0.5, 2.5, 4), tex=["SNOWSAND", ("SNOWROCK", ">", 0.7), ("WATER", "<", 0.25)],
                props=[(113, 0.06)]),                                                            # ice floes
        4: dict(relief=("flat", 0.3), tex=30),           # Mon Calamari cities: on the seabed (sea_town_30 = water, spawns cities)
        5: dict(relief=("flat", 0.3), tex=30),                                                   # Quarren cities, the same
        6: dict(relief=("flat", 2), tex="URBAN"),                                                # Dac City, on the surface
        7: dict(relief=("rolling", 3, 6, 4), tex=["JUNGLE", ("SAND", "<", 0.25), ("ROCK2", ">", 0.78)],
                props=[(117, 0.35), (82, 0.1)], clusters=[(6, 0.5, [(117, 0.7)])]),             # jungle islands
        8: dict(relief=("spires", 0.5, 2, 0.08, (1.2, 2.4), (5, 11)), tex=["ROCK", ("ROCK2", ">", 0.6)],
                props=[(118, 0.08)]),                                                            # trench rims, sea stacks
        9: dict(relief=("rolling", 9, 6, 4), tex=["SNOWROCK", ("SNOWSAND", ">", 0.6)], props=[(113, 0.08)]),   # ice shelf
    },
    steep=("ROCK2", 7, (7, 9)),
    city={4: 29, 6: 29, 5: 30},   # map/cities.txt 29: Mon Calamari coral cities, 30: Quarren towers (military_buildings.py)
    prop_clear=1.8,
    landforms=dict(amp=0, hills=0, skirt_k=0),   # a sea world: no uplands raised out of the water
    shore_rise=(9, 2.5),   # land climbs 9 steps within 2.5 px of the sea: cliffs, raised atolls and shores
)


# models (military_buildings.py place "Mon Calamari"): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_mcl_coral_city", "hod_mcl_drome", "hod_mcl_quarren_hq"},
    items=[("hod_mcl_coral_city", 1.0, ("at_vp", CAPITAL_VP)), ("hod_mcl_drome", 1.0, ("at_vp", "Moncaladrome")),
           ("hod_mcl_quarren_hq", 1.0, ("at_vp", "Quarren Headquarters"))],
    clear={"hod_mcl_coral_city": 6.5, "hod_mcl_drome": 4.8, "hod_mcl_quarren_hq": 5.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (mon_calamari_map.py)\n{imp}"
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
