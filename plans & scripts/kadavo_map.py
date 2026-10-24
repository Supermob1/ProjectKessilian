"""Kadavo, the Zygerrian slave world (Wookieepedia; The Clone Wars "Slaves of the Republic", "Escape from Kadavo"):
a cold volcanic world under smog, grey ash plains pocked with small volcanic cones and craters, a few great dormant
volcanoes, and at the heart of it the slave processing facility built over a deep crater "as a deterrent towards
rebellious slaves" (Keeper Agruss; destroyed by Plo Koon's Wolfpack in 20 BBY). The planet is that battlefield: the
facility's decks ring the crater, the slavers' landing field lies east of it, the ore pits west (Kadavo ore, TCW
asset), ash plains between the volcanoes. No towns: the bases are models (military_buildings.py kadavo_place).

    python "WIPGFX/plans & scripts/kadavo_map.py"     provinces.bmp, definition.csv, states, names, positions

All 200 province ids are kept (strategic region unchanged); only the pixels move. The crater and the volcanoes are
impassable states (1150-1155). Writes WIPGFX/Assets/kadavo_zones.json + kadavo_zones.png (KIND per pixel).
Run order: kadavo_map.py -> planet_terrain_gen.py --kadavo -> military_buildings.py kadavo_place -> kadavo_fx.py ->
planet_terrain_gen.py --globe-texture.
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

PLANET = "Kadavo"
ZONES_JSON = "WIPGFX/Assets/kadavo_zones.json"
ZONES_PNG = "WIPGFX/Assets/kadavo_zones.png"
KIND = {"plains": 1, "facility": 2, "crater": 3, "volcano": 4, "dock": 5, "mine": 6, "prison": 7, "bridge": 8}
TERRAIN = {"plains": "hills", "facility": "hills", "crater": "mountain", "volcano": "mountain", "dock": "plains",
           "mine": "hills", "prison": "urban", "bridge": "urban"}
SEED = 83
CAPITAL = 83
OWNER = "ZGY"
WARP = (0.07, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
PLAINS_PX = 52                       # px per province of ash plains (user: on a big planet the passable
                                     # provinces outnumber the impassable ones: ~130 of 200 here)
# the processing facility ("Escape from Kadavo"): a triangular hub hung in the middle of the Great Crater on the top
# of the great dome, joined to the crater's rim only by three girder arms; the hub and the arms are passable (the
# user: "the triangular prison should be passable with thin links to the sides of the volcano")
HUB = (0.03, 0.02, 0.3)              # the hub: centre (u, v) and circumradius
ARMS = (90, 210, 330)                # the arms' bearings from the hub (degrees, counter-clockwise from east)
ARM_W, RIM = 0.03, 0.44             # arm half-width; how far out they reach (past the crater's rim)
tri = lambda r: [(HUB[0] + r * math.cos(math.radians(a)), HUB[1] - r * math.sin(math.radians(a))) for a in ARMS]
# features painted in this order: (name, kind, state, provinces or 0 = the leftover ids by area, shapes); a shape is
# ("ell", u, v, ru, rv, deg), ("rect", u, v, hu, hv, deg), ("cap", u0, v0, u1, v1, r) or ("poly", [(u, v), ...]);
# u east, v south, planet radii. The crater is cut into pieces by the arms: each piece its own state (CRATER_STATES).
FEATURES = [
    ("Kadavo Processing Facility", "prison", CAPITAL, 5,
     [("poly", tri(HUB[2]))] + [("cap", HUB[0], HUB[1], u, v, ARM_W) for u, v in tri(RIM)]),
    ("The Great Crater", "crater", 1150, 0, [("ell", HUB[0], HUB[1], 0.38, 0.35, 15)]),
    ("Kadavo Processing Facility", "facility", CAPITAL, 12,
     [("ell", 0.03, 0.02, 0.52, 0.48, 10)]),
    ("Slaver Landing Field", "dock", 734, 7, [("ell", 0.7, 0.12, 0.17, 0.14, 20), ("rect", 0.88, 0.14, 0.14, 0.07, 5)]),
    ("Ore Pits", "mine", 736, 10, [("ell", -0.62, 0.28, 0.2, 0.15, -30), ("ell", -0.45, 0.45, 0.13, 0.1, 10)]),
    # the volcanoes and their old lava flows (impassable tongues reaching across the plains)
    ("Mount Vorsk", "volcano", 1151, 0, [("ell", -0.52, -0.48, 0.27, 0.23, 30), ("cap", -0.5, -0.45, -0.95, -0.25, 0.09),
                                         ("cap", -0.45, -0.4, -0.3, 0.0, 0.07), ("cap", -0.55, -0.5, -0.35, -0.95, 0.08)]),
    ("The Ashen Cones", "volcano", 1152, 0, [("ell", 0.1, 0.7, 0.3, 0.18, -10), ("ell", 0.34, 0.6, 0.13, 0.11, 0),
                                             ("cap", 0.0, 0.66, -0.28, 0.55, 0.08), ("cap", 0.25, 0.65, 0.55, 0.85, 0.08)]),
    ("Mount Khesh", "volcano", 1153, 0, [("ell", 0.52, -0.6, 0.22, 0.19, -25), ("cap", 0.5, -0.55, 0.3, -0.3, 0.07),
                                         ("cap", 0.5, -0.62, 0.25, -0.98, 0.07)]),
]
# the ash plains states: each takes the big natural pocket of plains nearest its seed (u, v)
SEEDS = {735: (0.0, -0.8), 737: (0.75, -0.4), 738: (0.5, 0.7), 739: (-0.7, 0.4)}
CRATER_STATES = [1150, 1154, 1155]
STATE_NAMES = {CAPITAL: "Kadavo Processing Facility", 734: "Slaver Landing Field", 735: "Northern Ash Fields",
               736: "Kadavo Ore Pits", 737: "Eastern Cinder Wastes", 738: "Southern Crater Fields",
               739: "Western Smog Flats", 1150: "The Great Crater", 1151: "Mount Vorsk", 1152: "The Ashen Cones",
               1153: "Mount Khesh", 1154: "The Great Crater East", 1155: "The Great Crater West"}
IMPASSABLE = {1150, 1151, 1152, 1153, 1154, 1155}
# victory points: (state, feature or kind, name, value)
VPS = [(CAPITAL, "prison", "Kadavo Processing Facility", 10), (CAPITAL, "facility", "Keeper's Landing", 3),
       (734, "Slaver Landing Field", "Slaver Landing Field", 3), (736, "Ore Pits", "Kadavo Ore Pits", 3),
       (735, "plains", "Northern Slave Camp", 1), (737, "plains", "Cinder Outpost", 1),
       (738, "plains", "Crater Field Watchpost", 1), (739, "plains", "Smog Flats Camp", 1)]


def mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    return land, pid, np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])


def shape(s_, U, V):
    """korriban_map.shape plus ("poly", [(u, v), ...]): a convex polygon"""
    if s_[0] != "poly":
        return kshape(s_, U, V)
    pts = s_[1]
    crs = [(u1 - u0) * (V - v0) - (v1 - v0) * (U - u0) for (u0, v0), (u1, v1) in zip(pts, pts[1:] + pts[:1])]
    inside = np.all([c_ >= 0 for c_ in crs], 0) | np.all([c_ <= 0 for c_ in crs], 0)   # either winding
    return inside


def layout(m, rng):
    """feature index per pixel and features [(name, kind, state, provinces)]: FEATURES in order, then the plains by
    nearest seed"""
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
        u_, v_ = (U0, V0) if k == "prison" else (U, V)                    # straight: the model's girder arms lie on them
        fid[sm & (fid < 0) & np.any([shape(s_, u_, v_) for s_ in shapes], 0)] = len(feats) - 1
    # the crater, cut by the arms: one feature (state) per piece, the biggest first
    ci = next(i for i, f in enumerate(feats) if f[1] == "crater")
    pieces, n = ndi.label(fid == ci)
    order = np.argsort(-np.bincount(pieces.ravel())[1:])[:len(CRATER_STATES)] + 1
    for k, lab_ in enumerate(order):
        if k == 0:
            continue
        feats.append((STATE_NAMES[CRATER_STATES[k]], "crater", CRATER_STATES[k], 0))
        fid[pieces == lab_] = len(feats) - 1
    # the plains: the lava flows and the volcanoes cut them into natural pockets; the biggest pockets are the plains
    # states (each to the seed nearest its middle, the biggest first), the small ones join whatever they touch (tidy)
    free = sm & (fid < 0)
    pockets, npk = ndi.label(free)
    sizes = np.bincount(pockets.ravel())[1:]
    left = dict(SEEDS)
    first = len(feats)
    for lab_ in np.argsort(-sizes)[:len(SEEDS)] + 1:
        cv, cu = V[pockets == lab_].mean(), U[pockets == lab_].mean()
        sid = min(left, key=lambda q: math.hypot(left[q][0] - cu, left[q][1] - cv))
        del left[sid]
        feats.append((STATE_NAMES[sid], "plains", sid, 0))
        fid[pockets == lab_] = len(feats) - 1
    rest = free & (fid < 0)                                               # small pockets: to the nearest plains state
    if rest.any():
        _, (iy, ix) = ndi.distance_transform_edt(~((fid >= first) & sm), return_indices=True)
        fid[rest] = fid[iy[rest], ix[rest]]
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
    for g_ in groups:
        if not g_["n"] and g_["state"] not in IMPASSABLE:
            g_["n"] = max(1, round(g_["mask"].sum() / PLAINS_PX))
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
    capital_p = next(p for p, n in vp_names.items() if n == "Kadavo Processing Facility")
    dock = [p for p in by_state[734] if prov[p]["coastal"]]
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
        if sid == 734:                                                   # the slavers' ships and yards: the landing field
            if docks:
                bld = bld.rstrip().rstrip("}") + f"\tdockyard = {docks}\n\t\t}}"
            if naval:
                bld = bld.rstrip().rstrip("}") + f"\t\t\t{port} = {{\n\t\t\t\tnaval_base = {max(naval)}\n\t\t\t}}\n\t\t}}"
        if sid in IMPASSABLE:
            imp = "\timpassable = yes\n"
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            res, man, cat = "\n\tresources={\n\t}", "1000", "wasteland_sector"
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {vps[p]}\n\t\t}}\n" for p in provs if p in vps)
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: Kadavo (kadavo_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {OWNER}\n\t\tadd_core_of = {OWNER}\n\t}}\n"
                f"\tmanpower = {man}\n\tstate_category = {cat}\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}}\n")
        if sid in old:
            os.remove(old[sid])
        open(f"history/states/{sid}-Kadavo - {STATE_NAMES[sid].replace(chr(39), '')}.txt", "w", encoding="utf-8",
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


if __name__ == "__main__":
    pcom.run(main)
