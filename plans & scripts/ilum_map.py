"""Ilum, the ice world of the Jedi's crystal caves, as one battlefield before the Clone Wars (research:
WIPGFX/research/ilum/; Legends first, canon where Legends is silent; the user, 2026-10-20). CANON: the Jedi Temple on
Ilum, one of the Order's earliest, over the Crystal Caves where younglings find their kyber crystals in the Gathering;
Holenesh Canyon, a kilometre deep, centre of a Force anomaly; crystallized glaciers, ice plains, mountains, forests.
LEGENDS: 90% ice, caverns, ice flows; the Western Ice Shelf with the Circle at its centre and the Icefall Cavern; Fort
Tonvarr (Fray Landing Base) at the shelf's south end, a Republic base of the Galactic War, here an old ruin; the
Cross-Shelf Corridor carved through the ice to the Western Jedi ruins; the Separatist ambush on Luminara Unduli and
Barriss Offee at the Temple (21 BBY). Uninhabited: no towns. Owner: REP (as before).
LAYOUT IS A DESIGN CHOICE (the sources place only the Circle in the shelf's centre, Fort Tonvarr at its south end and
the corridor between the shelf and the ruins): the Temple in the north under the Crystal Peaks, the Western Ice Shelf in
the west, the corridor and the ruins in the middle, Holenesh Canyon in the east, the crystal forests in the north-east,
the Glacier Fields (impassable) in the south-east.
Names from the sources: Jedi Temple, Holenesh Canyon, Western Ice Shelf, the Circle, Fort Tonvarr, Fray Landing,
Cross-Shelf Corridor, Western Jedi Ruins. Invented: the Crystal Peaks, the Crystal Forests, the Glacier Fields.
    python "WIPGFX/plans & scripts/ilum_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ilum_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 63 province ids are kept (strategic region unchanged); only the pixels move.
Run order: ilum_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (ilu_*) ->
planet_terrain_gen.py --planet Ilum -> military_buildings.py models hod_ilu -> coruscant_buildings.py wire ->
military_buildings.py place Ilum -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Ilum"
ZONES_JSON = "WIPGFX/Assets/ilum_zones.json"
ZONES_PNG = "WIPGFX/Assets/ilum_zones.png"
KIND = {"temple": 1, "canyon": 2, "fort": 3, "circle": 4, "ruins": 5, "corridor": 6, "ice": 7, "shelf": 8, "forest": 9,
        "peaks": 10, "glacier": 11}
TERRAIN = {"temple": "hills", "canyon": "hills", "fort": "hills", "circle": "plains", "ruins": "hills", "corridor": "plains",
           "ice": "plains", "shelf": "plains", "forest": "forest", "peaks": "mountain", "glacier": "mountain"}
SEED = 181
CAPITAL = 181
CAPITAL_VP = "Jedi Temple"
PORT_STATE = 971                     # Fray Landing, the old base's landing field
OWNER = {s: "REP" for s in (181, 966, 967, 968, 969, 970, 971, 1291, 1292)}
WARP = (0.13, 9)
TARGET_PASSABLE = 41                 # user rule: passable provinces outnumber impassable (~41 / 22)
STRAIGHT = set()
FEATURES = [
    ("Jedi Temple", "temple", CAPITAL, 2, [("ell", 0.05, -0.42, 0.11, 0.08, 0)]),
    ("Crystal Peaks", "peaks", 1291, 0, [("ell", 0.05, -0.78, 0.42, 0.16, 0), ("cap", -0.62, -0.45, -0.28, -0.62, 0.08)]),
    ("Holenesh Canyon", "canyon", 969, 2, [("cap", 0.45, -0.2, 0.72, 0.3, 0.07)]),
    ("Fort Tonvarr", "fort", 971, 1, [("ell", -0.45, 0.62, 0.08, 0.07, 0)]),
    ("The Circle", "circle", 966, 1, [("ell", -0.6, 0.05, 0.08, 0.07, 0)]),
    ("Cross-Shelf Corridor", "corridor", 967, 2, [("cap", -0.45, -0.05, -0.05, 0.12, 0.06)]),
    ("Western Jedi Ruins", "ruins", 968, 1, [("ell", 0.05, 0.18, 0.08, 0.07, 0)]),
    ("Glacier Fields", "glacier", 1292, 0, [("ell", 0.45, 0.62, 0.26, 0.17, 25)]),
]
SEEDS = {CAPITAL: ((0.05, -0.28), "ice"), 966: ((-0.72, 0.0), "shelf"), 967: ((-0.25, -0.15), "shelf"),
         968: ((0.05, 0.4), "ice"), 969: ((0.7, -0.05), "ice"), 970: ((0.35, -0.42), "forest"),
         971: ((-0.3, 0.78), "shelf")}
STATE_NAMES = {CAPITAL: "Jedi Temple", 966: "Western Ice Shelf", 967: "Cross-Shelf Corridor", 968: "Western Jedi Ruins",
               969: "Holenesh Canyon", 970: "Crystal Forests", 971: "Fray Landing", 1291: "Crystal Peaks",
               1292: "Glacier Fields"}
IMPASSABLE = {1291, 1292}
VPS = [(CAPITAL, "Jedi Temple", CAPITAL_VP, 10), (969, "Holenesh Canyon", "Holenesh Canyon", 3),
       (971, "Fort Tonvarr", "Fort Tonvarr", 3), (966, "The Circle", "The Circle", 2),
       (968, "Western Jedi Ruins", "Western Jedi Ruins", 2), (967, "Cross-Shelf Corridor", "Cross-Shelf Corridor", 1),
       (970, "forest", "Crystal Forests", 1)]

TERRAIN_CFG = dict(
    seed=181, base=4, rough=2, open=(6, 7, 8, 9),
    zones={
        1: dict(relief=("ramp_top", 12, 5, 3), tex=["SNOWROCK", ("ROCK", ">", 0.7)], props=[(210, 0.1)]),     # the Temple
        2: dict(relief=("mesa", 2, 14, 3, (5, 0.6)), tex=["SNOWROCK", ("ROCK2", ">", 0.55)], props=[(210, 0.15)]),
        3: dict(relief=("flat", 5), tex=["SNOWSAND", ("SNOWROCK", ">", 0.5)]),                        # the fort
        4: dict(relief=("flat", 4), tex="SNOWSAND"),                                                   # the Circle
        5: dict(relief=("rolling", 6, 3, 5), tex=["SNOWROCK", ("SNOWSAND", ">", 0.5)]),
        6: dict(relief=("flat", 3), tex=["SNOWSAND", ("SNOWROCK", ">", 0.7)]),                         # the corridor
        7: dict(relief=("rolling", 5, 4, 5), tex=["SNOWSAND", ("SNOWROCK", ">", 0.7)], props=[(210, 0.05)]),
        8: dict(relief=("rolling", 3, 2, 7), tex=["SNOWSAND", ("SNOWFARM", ">", 0.6)]),                # the ice shelf
        9: dict(relief=("rolling", 6, 4, 5), tex=["SNOWFARM", ("SNOWROCK", ">", 0.7)], props=[(211, 0.7), (210, 0.1)]),
        10: dict(relief=("spires", 20, 11, 0.1, (1.4, 2.8), (28, 52)), tex=["SNOWROCK", ("ROCK", ">", 0.75)], props=[(210, 0.1)]),
        11: dict(relief=("spires", 10, 6, 0.06, (2.0, 3.5), (16, 30)), tex=["SNOWSAND", ("SNOWROCK", ">", 0.5)]),
    },
    steep=("SNOWROCK", 6, (6, 7, 8, 9)),
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.7, 0.74, 0.8), 2: (0.66, 0.72, 0.8), 3: (0.84, 0.88, 0.92), 4: (0.86, 0.9, 0.94), 5: (0.76, 0.8, 0.86),
            6: (0.82, 0.86, 0.92), 7: (0.86, 0.9, 0.95), 8: (0.9, 0.93, 0.97), 9: (0.6, 0.7, 0.72), 10: (0.66, 0.7, 0.76),
            11: (0.8, 0.86, 0.94)},
)

PLACEMENT = dict(
    new_models={"hod_ilu_temple", "hod_ilu_tonvarr", "hod_ilu_circle", "hod_ilu_ruins"},
    items=[("hod_ilu_temple", 1.0, ("at_vp", CAPITAL_VP)), ("hod_ilu_tonvarr", 1.0, ("at_vp", "Fort Tonvarr")),
           ("hod_ilu_circle", 1.0, ("at_vp", "The Circle")), ("hod_ilu_ruins", 1.0, ("at_vp", "Western Jedi Ruins"))],
    clear={"hod_ilu_temple": 6.0, "hod_ilu_tonvarr": 5.0, "hod_ilu_circle": 4.5, "hod_ilu_ruins": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ilum_map.py)\n{imp}"
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
