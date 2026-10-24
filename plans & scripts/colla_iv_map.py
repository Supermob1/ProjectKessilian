"""Colla IV, the Colicoid spawnworld, as one battlefield before the Clone Wars (research: WIPGFX/research/colla_iv/).
LEGENDS (all there is): the tropical spawnworld of the Colicoids, the insectoid species of the Colicoid Creation Nest;
on it the factory that was the main manufacturing facility for the droidekas; a Battle of Colla IV in the Clone Wars,
won by the Confederacy.
Owner: TDF (as before; the capital's file was "118- Colla IV.txt", renamed so the planet tools find it). User
(2026-10-19): landmarks the Colicoid Creation Nest (the droideka factory), a Colicoid hive
capital, the spawning grounds.
LAYOUT IS A DESIGN CHOICE: the hive capital in the middle with the Creation Nest beside it to the east, the spawning
grounds in the southern swamps, tropical jungle and hive-mound plains round them, the Spire Fields (impassable: dense
fields of towering hive spires) over the north and the Brood Marsh (impassable) in the south-west.
Legends names: the Colicoid Creation Nest. Invented: the hive capital (Colla Hive), the Spawning Grounds as named
sites, every state name, the Spire Fields, the Brood Marsh.
    python "WIPGFX/plans & scripts/colla_iv_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/colla_iv_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 203 province ids are kept (strategic region unchanged); only the pixels move.
Run order: colla_iv_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (col_*) ->
planet_terrain_gen.py --planet "Colla IV" -> military_buildings.py models hod_col -> military_buildings.py place
"Colla IV" -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Colla IV"
ZONES_JSON = "WIPGFX/Assets/colla_iv_zones.json"
ZONES_PNG = "WIPGFX/Assets/colla_iv_zones.png"
KIND = {"hive": 1, "nest": 2, "spawn": 3, "mounds": 4, "jungle": 5, "swamp": 6, "spires": 7, "marsh": 8}
TERRAIN = {"hive": "urban", "nest": "urban", "spawn": "marsh", "mounds": "hills", "jungle": "jungle", "swamp": "marsh",
           "spires": "mountain", "marsh": "marsh"}
SEED = 118
CAPITAL = 118
CAPITAL_VP = "Colla Hive"
PORT_STATE = 947                     # the hive lies inland: the fleet lies off the spawning swamps
OWNER = {s: "TDF" for s in (118, 946, 947, 948, 949, 950, 951, 1248, 1249)}
WARP = (0.13, 9)
TARGET_PASSABLE = 135                # user rule: passable provinces outnumber impassable (~135 / 68)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Colla Hive", "hive", CAPITAL, 4, [("ell", -0.05, 0.0, 0.22, 0.16, 0)]),
    ("Colicoid Creation Nest", "nest", 946, 2, [("ell", 0.42, 0.02, 0.15, 0.11, 0)]),
    ("Spawning Grounds", "spawn", 947, 2, [("ell", 0.05, 0.6, 0.16, 0.11, 0)]),
    ("Spire Fields", "spires", 1248, 0, [("ell", 0.0, -0.66, 0.5, 0.2, 0), ("cap", -0.5, -0.65, -0.75, -0.3, 0.1)]),
    ("Brood Marsh", "marsh", 1249, 0, [("ell", -0.6, 0.48, 0.28, 0.22, -35), ("cap", -0.9, 0.2, -0.6, 0.72, 0.1)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.0, 0.05), "mounds"), 946: ((0.5, 0.0), "mounds"), 947: ((0.15, 0.65), "swamp"),
         948: ((-0.6, -0.1), "jungle"), 949: ((0.6, -0.45), "jungle"), 950: ((0.6, 0.45), "jungle"),
         951: ((-0.3, -0.4), "mounds")}
STATE_NAMES = {CAPITAL: "Colla Hive", 946: "Creation Nest", 947: "Spawning Swamps", 948: "Western Jungles",
               949: "Northern Jungles", 950: "Southern Jungles", 951: "Mound Plains", 1248: "Spire Fields",
               1249: "Brood Marsh"}
IMPASSABLE = {1248, 1249}
VPS = [(CAPITAL, "Colla Hive", CAPITAL_VP, 10), (946, "Colicoid Creation Nest", "Colicoid Creation Nest", 5),
       (947, "Spawning Grounds", "Spawning Grounds", 2), (948, "jungle", "Western Jungles", 1),
       (949, "jungle", "Northern Jungles", 1), (950, "jungle", "Southern Jungles", 1), (951, "mounds", "Mound Plains", 1)]

# terrain (planet_terrain_gen.py --planet "Colla IV"). Heights in heightmap steps above the base. Tropical jungle
# (flora_props 170 broad tropical trees), hive mounds rising out of the plains (171), egg clusters in the swamps
# (172), the Colicoid hive towns (map/cities.txt 59, military_buildings.py col_city), the spire fields
TERRAIN_CFG = dict(
    seed=118, base=4, rough=2, open=(4, 5, 6),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 6, 2, 6), tex=["URBAN", ("BROWN", ">", 0.6)]),                # the hive capital
        2: dict(relief=("flat", 5), tex="URBAN"),                                                  # the Creation Nest
        3: dict(relief=("rolling", 2, 1, 6), tex=["JUNGLE2", ("WATER", ">", 0.6)], props=[(172, 0.4)]),   # spawning
        4: dict(relief=("rolling", 6, 4, 5), tex=["BROWN", ("GRASS", ">", 0.5), (13, ">", 0.86)],
                props=[(171, 0.18), (170, 0.1)]),                                                  # mound plains
        5: dict(relief=("rolling", 6, 4, 5), tex=["JUNGLE", ("JUNGLE2", ">", 0.55), (13, ">", 0.9)],
                props=[(170, 0.6), (171, 0.05)]),                                                  # jungle
        6: dict(relief=("rolling", 2, 1.5, 6), tex=["JUNGLE2", ("WATER", ">", 0.68), (13, ">", 0.9)],
                props=[(170, 0.25), (172, 0.15)]),                                                 # swamps
        7: dict(relief=("spires", 10, 6, 0.12, (1.2, 2.2), (20, 40)), tex=["BROWN", ("ROCK2", ">", 0.5)],
                props=[(171, 0.4)]),                                                               # the Spire Fields
        8: dict(relief=("rolling", 1.5, 1, 6), tex=["WATER", ("JUNGLE2", ">", 0.55)], props=[(172, 0.2)]),   # marsh
    },
    steep=("BROWN", 6, (4, 5, 6)),
    city={1: 59, 2: 59, 4: 59, 5: 59},   # map/cities.txt 59: the Colicoid hive towns (col_city)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.5, 0.42, 0.32), 2: (0.48, 0.44, 0.38), 3: (0.24, 0.34, 0.24), 4: (0.5, 0.44, 0.3),
            5: (0.2, 0.38, 0.18), 6: (0.22, 0.34, 0.22), 7: (0.48, 0.4, 0.3), 8: (0.18, 0.3, 0.26)},
)

# models (military_buildings.py place "Colla IV"): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_col_hive", "hod_col_nest", "hod_col_spawn"},
    items=[("hod_col_hive", 1.0, ("at_vp", CAPITAL_VP)), ("hod_col_nest", 1.0, ("at_vp", "Colicoid Creation Nest")),
           ("hod_col_spawn", 1.0, ("at_vp", "Spawning Grounds"))],
    clear={"hod_col_hive": 6.0, "hod_col_nest": 5.5, "hod_col_spawn": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (colla_iv_map.py)\n{imp}"
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
