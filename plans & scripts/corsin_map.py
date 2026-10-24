"""Corsin, the tropical island world of the Republic, as one battlefield before the Clone Wars (research:
WIPGFX/research/corsin/). LEGENDS (all there is): a beautiful world of landmasses and oceans, warm in its tropics, its
dry land home to plants; the Tinn'lyi Islands; the Corsin Retreat, where Republic commanders gathered in 738 BBY; the
selligore, aquatic mammals more than twenty metres long feeding in its temperate and tropical waters.
Owner: REP (as before). User (2026-10-19): an island archipelago; landmarks the Corsin Retreat, a capital port city,
a Tinn'lyi Islands resort, a selligore watching station.
LAYOUT IS A DESIGN CHOICE: a central island with the capital's port on the inner sea, the Corsin Sea (impassable) round
it as a ring broken by one causeway, three straits cutting the outer land into great islands that meet only at
the rim; the Retreat on the northern island's heights, the selligore station on the western banks, the Tinn'lyi
resort in the south-east.
Legends names: the Tinn'lyi Islands, the Corsin Retreat. Invented: Corsin Port, the Selligore Station, the Tinn'lyi
Resort as named sites, every other state name, the Corsin Sea.
    python "WIPGFX/plans & scripts/corsin_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/corsin_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 200 province ids are kept (strategic region unchanged); only the pixels move.
Run order: corsin_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (crs_*) ->
planet_terrain_gen.py --planet Corsin -> military_buildings.py models hod_crs -> military_buildings.py place Corsin
-> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Corsin"
ZONES_JSON = "WIPGFX/Assets/corsin_zones.json"
ZONES_PNG = "WIPGFX/Assets/corsin_zones.png"
KIND = {"port": 1, "retreat": 2, "resort": 3, "station": 4, "beach": 5, "forest": 6, "hills": 7, "sea": 8}
TERRAIN = {"port": "urban", "retreat": "hills", "resort": "urban", "station": "plains", "beach": "plains",
           "forest": "jungle", "hills": "hills", "sea": "mountain"}
SEED = 100
CAPITAL = 100
CAPITAL_VP = "Corsin Port"
PORT_STATE = 842                     # the capital lies on the inner sea, not on space: the fleet lies off the east
OWNER = {s: "REP" for s in (100, 838, 839, 840, 841, 842, 843, 1237)}
WARP = (0.1, 9)
TARGET_PASSABLE = 134                # user rule: passable provinces outnumber impassable (~134 / 66)
STRAIGHT = set()
_GAPS = (300,)                       # the causeway across the ring (degrees, east 0, south 90): one, so the sea stays whole
_RING = [("cap", 0.41 * math.cos(math.radians(a0)), 0.41 * math.sin(math.radians(a0)),
          0.41 * math.cos(math.radians(a0 + 15)), 0.41 * math.sin(math.radians(a0 + 15)), 0.17)
         for a0 in range(0, 360, 15) if all(min(abs(a0 + 7.5 - g), 360 - abs(a0 + 7.5 - g)) > 24 for g in _GAPS)]
_STRAITS = [("cap", 0.5 * math.cos(math.radians(a)), 0.5 * math.sin(math.radians(a)),
             0.74 * math.cos(math.radians(a)), 0.74 * math.sin(math.radians(a)), 0.11) for a in (0, 120, 240)]
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Corsin Port", "port", CAPITAL, 3, [("ell", 0.06, 0.12, 0.16, 0.12, 0)]),
    ("Corsin Retreat", "retreat", 839, 1, [("ell", -0.25, -0.7, 0.13, 0.1, 0)]),
    ("Tinn'lyi Resort", "resort", 838, 1, [("ell", 0.62, 0.5, 0.13, 0.1, 30)]),
    ("Selligore Station", "station", 840, 1, [("ell", -0.62, 0.22, 0.12, 0.1, 0)]),
    ("Corsin Sea", "sea", 1237, 0, _RING + _STRAITS),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.0, 0.0), "forest"), 838: ((0.62, 0.58), "beach"), 839: ((-0.3, -0.75), "hills"),
         840: ((-0.72, 0.3), "beach"), 841: ((0.45, -0.72), "forest"), 842: ((0.82, -0.05), "beach"),
         843: ((-0.1, 0.8), "forest")}
STATE_NAMES = {CAPITAL: "Central Island", 838: "Tinn'lyi Islands", 839: "Retreat Heights", 840: "Selligore Banks",
               841: "Northern Isle", 842: "Eastern Shores", 843: "Southern Isle", 1237: "Corsin Sea"}
IMPASSABLE = {1237}
VPS = [(CAPITAL, "Corsin Port", CAPITAL_VP, 10), (839, "Corsin Retreat", "Corsin Retreat", 3),
       (838, "Tinn'lyi Resort", "Tinn'lyi Islands", 2), (840, "Selligore Station", "Selligore Station", 2),
       (841, "forest", "Northern Isle", 1), (842, "beach", "Eastern Shores", 1), (843, "forest", "Southern Isle", 1)]

# terrain (planet_terrain_gen.py --planet Corsin). Heights in heightmap steps above the base. Palm-lined beaches and
# tropical forests (flora_props 161 palms, 162 flowering shrubs), the island towns (map/cities.txt 55,
# military_buildings.py crs_town), the Corsin Sea level with the water plane
TERRAIN_CFG = dict(
    seed=100, base=4, rough=2, open=(5, 6, 7),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 4, 1.5, 6), tex="URBAN"),                                      # Corsin Port
        2: dict(relief=("ramp_top", 12, 6, 4), tex=["GRASSHILL", ("FOREST", ">", 0.6)], props=[(161, 0.1)]),
        3: dict(relief=("flat", 3), tex=["SAND", ("URBAN", ">", 0.5)], props=[(161, 0.2)]),     # the resort
        4: dict(relief=("flat", 3), tex=["SAND", ("GRASS", ">", 0.6)]),                          # the station
        5: dict(relief=("rolling", 3, 1.5, 6), tex=["SAND", ("GRASS", ">", 0.5), (13, ">", 0.86)],
                props=[(161, 0.25), (162, 0.05)]),                                                 # beaches
        6: dict(relief=("rolling", 6, 4, 5), tex=["JUNGLE", ("FOREST", ">", 0.55), (13, ">", 0.9)],
                props=[(161, 0.3), (162, 0.25)]),                                                  # tropical forest
        7: dict(relief=("rolling", 10, 7, 4), tex=["GRASSHILL", ("JUNGLE", ">", 0.55), (13, ">", 0.9)],
                props=[(162, 0.2), (161, 0.1)]),                                                   # hills
        8: dict(relief=("flat", 0.3), tex="WATER"),                                                # the Corsin Sea
    },
    steep=("ROCK", 6, (5, 6, 7)),
    city={1: 55, 3: 55, 5: 55, 6: 55},   # map/cities.txt 55: Corsin's island towns (crs_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.62, 0.6, 0.54), 2: (0.36, 0.5, 0.3), 3: (0.74, 0.68, 0.5), 4: (0.72, 0.66, 0.5),
            5: (0.7, 0.64, 0.46), 6: (0.22, 0.44, 0.24), 7: (0.32, 0.48, 0.28), 8: (0.14, 0.4, 0.5)},
)

# models (military_buildings.py place Corsin): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_crs_port", "hod_crs_retreat", "hod_crs_resort", "hod_crs_station"},
    items=[("hod_crs_port", 1.0, ("at_vp", CAPITAL_VP)), ("hod_crs_retreat", 1.0, ("at_vp", "Corsin Retreat")),
           ("hod_crs_resort", 1.0, ("at_vp", "Tinn'lyi Islands")), ("hod_crs_station", 1.0, ("at_vp", "Selligore Station"))],
    clear={"hod_crs_port": 5.5, "hod_crs_retreat": 4.5, "hod_crs_resort": 4.5, "hod_crs_station": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (corsin_map.py)\n{imp}"
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
