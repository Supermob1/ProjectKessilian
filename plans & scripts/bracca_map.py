"""Bracca, the Scrapper Guild's shipbreaking world, as one battlefield before the Clone Wars (research:
WIPGFX/research/bracca/). CANON: a poor Mid Rim world of rocky plains and junkyards; the Scrapper Guild breaks old
starships on its platforms (Platform Twenty, Thirty-Two, Thirty-Three); Worker Rail Route 213 carries the scrappers;
the Retired Control Tower; a Strike on Bracca in 22 BBY.
Owner: REP (as before). User (2026-10-19): "basically bracca is kinda like raxus prime"; landmarks the shipbreaking
yards (with the mod's existing ship models: the Old Republic Derriphan and Hammerhead hulls of Raxus Prime, rusted and
cut in two), the Retired Control Tower, Worker Rail Route 213, the scrapper towns.
LAYOUT IS A DESIGN CHOICE: the Scrapper Guild Yards in the middle with Platform Thirty-Three, the platform district
with Platform Thirty-Two to the east, the Retired Control Tower on the plains north, the rail route running west to
the scrapper town, the Scrap Heaps (impassable, piled junk) over the south and south-west.
Canon names: Platform Thirty-Two, Platform Thirty-Three, Worker Rail Route 213, the Retired Control Tower, the Scrapper
Guild. Invented: every state name, the Scrapper Guild Yards and Scrapper Town as named sites, the Scrap Heaps.
    python "WIPGFX/plans & scripts/bracca_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/bracca_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 63 province ids are kept (strategic region unchanged); only the pixels move.
Run order: bracca_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (bra_*) ->
planet_terrain_gen.py --planet Bracca -> military_buildings.py models hod_bra -> military_buildings.py place Bracca ->
planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Bracca"
ZONES_JSON = "WIPGFX/Assets/bracca_zones.json"
ZONES_PNG = "WIPGFX/Assets/bracca_zones.png"
KIND = {"yards": 1, "platform": 2, "tower": 3, "rail": 4, "town": 5, "plains": 6, "salvage": 7, "heaps": 8}
TERRAIN = {"yards": "urban", "platform": "urban", "tower": "plains", "rail": "plains", "town": "urban",
           "plains": "plains", "salvage": "hills", "heaps": "mountain"}
SEED = 197
CAPITAL = 197
CAPITAL_VP = "Scrapper Guild Yards"
PORT_STATE = 1064                    # the capital state is inland: the fleet lies off the salvage fields
OWNER = {s: "REP" for s in (197, 1059, 1060, 1061, 1062, 1063, 1064, 1233)}
WARP = (0.13, 9)
TARGET_PASSABLE = 42                 # user rule: passable provinces outnumber impassable (~42 / 21)
STRAIGHT = {"rail"}
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Scrapper Guild Yards", "yards", CAPITAL, 2, [("ell", 0.0, 0.0, 0.26, 0.17, -10)]),
    ("Platform Thirty-Two", "platform", 1059, 1, [("ell", 0.6, -0.1, 0.17, 0.12, 20)]),
    ("Retired Control Tower", "tower", 1060, 1, [("ell", 0.05, -0.6, 0.14, 0.11, 0)]),
    ("Worker Rail Route 213", "rail", 1061, 1, [("cap", -0.3, -0.05, -0.62, -0.12, 0.06)]),
    ("Scrapper Town", "town", 1062, 1, [("ell", -0.72, -0.2, 0.15, 0.12, 0)]),
    ("Scrap Heaps", "heaps", 1233, 0, [("ell", -0.25, 0.62, 0.42, 0.24, 20), ("cap", -0.85, 0.3, -0.55, 0.5, 0.14)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.0, 0.1), "salvage"), 1059: ((0.65, 0.0), "salvage"), 1060: ((0.1, -0.7), "plains"),
         1061: ((-0.45, -0.45), "plains"), 1062: ((-0.75, -0.15), "plains"), 1063: ((0.55, -0.6), "plains"),
         1064: ((0.45, 0.6), "salvage")}
STATE_NAMES = {CAPITAL: "Scrapper Guild Yards", 1059: "Platform District", 1060: "Northern Plains", 1061: "Rail Flats",
               1062: "Scrapper Town", 1063: "Eastern Plains", 1064: "Salvage Fields", 1233: "Scrap Heaps"}
IMPASSABLE = {1233}
VPS = [(CAPITAL, "Scrapper Guild Yards", CAPITAL_VP, 5), (1059, "Platform Thirty-Two", "Platform Thirty-Two", 2),
       (1060, "Retired Control Tower", "Retired Control Tower", 2),
       (1061, "Worker Rail Route 213", "Worker Rail Route 213", 1), (1062, "Scrapper Town", "Scrapper Town", 2),
       (1063, "plains", "Eastern Plains", 1), (1064, "salvage", "Salvage Fields", 1)]

# terrain (planet_terrain_gen.py --planet Bracca). Heights in heightmap steps above the base. Raxus Prime's look (the
# user, 2026-10-19: "it should be more organic more trashy and full of scrap metal"): the junk ground (terrain.bmp 28
# scrap, 29 scrap town) everywhere, lumpy relief, Raxus Prime's junk heaps, ridges and tangles (flora_props 73-78) and
# its wrecks and junk (65-72) strewn thick, Bracca's own scrap piles (154), the scrappers' salvage housing
# (map/cities.txt 52, military_buildings.py bra_city), the Scrap Heaps piled into mountains of junk
_JUNK = [(73, 0.08), (74, 0.05), (75, 0.05), (77, 0.07), (78, 0.05), (154, 0.1), (69, 0.05), (70, 0.03), (71, 0.04),
         (72, 0.03)]
TERRAIN_CFG = dict(
    seed=197, base=4, rough=3, open=(6, 7),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 4, 1.5, 6), tex=29, props=[(154, 0.05)]),                     # the yards
        2: dict(relief=("rolling", 5, 1.5, 6), tex=29, props=[(154, 0.05)]),                     # Platform 32
        3: dict(relief=("rolling", 5, 3, 5), tex=28, props=_JUNK),                                # the tower's plain
        4: dict(relief=("rolling", 4.5, 2, 6), tex=28, props=[(p, d * 0.6) for p, d in _JUNK]),  # the rail flats
        5: dict(relief=("rolling", 5, 2, 6), tex=29, props=[(154, 0.05), (70, 0.04)]),           # Scrapper Town
        6: dict(relief=("rolling", 6, 5, 4), tex=[28, ("BROWN", ">", 0.82), (29, ">", 0.9)], props=_JUNK,
                clusters=[(5, 0.5, [(76, 0.3), (73, 0.3), (74, 0.2)])]),                         # junk plains
        7: dict(relief=("rolling", 8, 8, 3), tex=[28, (29, ">", 0.88)],
                props=[(p, d * 1.4) for p, d in _JUNK] + [(76, 0.15), (65, 0.02), (66, 0.02), (67, 0.02)],
                clusters=[(6, 0.55, [(76, 0.35), (74, 0.3), (73, 0.25)])]),                     # salvage fields
        8: dict(relief=("spires", 14, 10, 0.1, (2.0, 4.0), (24, 50)), tex=[28, ("BROWN", ">", 0.6)],
                props=[(76, 0.3), (74, 0.25), (73, 0.2), (77, 0.1), (78, 0.1)]),                # the Scrap Heaps
    },
    steep=("BROWN", 7, (6, 7)),
    city={1: 52, 2: 52, 5: 52, 6: 52, 7: 52},   # map/cities.txt 52: the scrappers' housing (bra_city)
    prop_clear=1.3,
    shore_rise=(4, 2.0),
    colors={1: (0.44, 0.38, 0.32), 2: (0.44, 0.38, 0.32), 3: (0.48, 0.4, 0.32), 4: (0.46, 0.38, 0.3),
            5: (0.42, 0.37, 0.32), 6: (0.47, 0.39, 0.31), 7: (0.42, 0.34, 0.27), 8: (0.36, 0.3, 0.25)},
)

def wrecks(ctx):
    """the hulls in the yards: the Raxus Prime wreck meshes (hod_bld_rp_*: the user's choice of existing ship models),
    a Derriphan cut in two at the Guild Yards, a Hammerhead at Platform Thirty-Two; offsets in px (east, south) from
    the VP, yaw in degrees"""
    for vp, parts in (("Scrapper Guild Yards", [("hod_bld_rp_derriphan_bow", (-3.4, 0.6), 20),
                                                ("hod_bld_rp_derriphan_stern", (3.6, -0.6), 200)]),
                      ("Platform Thirty-Two", [("hod_bld_rp_hammerhead_bow", (-2.2, 0.4), 335),
                                               ("hod_bld_rp_hammerhead_stern", (2.4, -0.4), 155)])):
        r, c = ctx["vp_at"][vp]
        for mesh, (dx, dy), deg in parts:
            ctx["put"](mesh, 1.0, r + dy, c + dx, math.radians(deg))


# models (military_buildings.py place Bracca): big, custom (user rule 2026-10-14); the hulls are existing models
PLACEMENT = dict(
    new_models={"hod_bra_yards", "hod_bra_platform", "hod_bra_tower", "hod_bra_rail", "hod_bra_town"},
    items=[("hod_bra_yards", 1.0, ("at_vp", CAPITAL_VP)), ("hod_bra_platform", 1.0, ("at_vp", "Platform Thirty-Two")),
           ("hod_bra_tower", 1.0, ("at_vp", "Retired Control Tower")), ("hod_bra_rail", 1.0, ("at_vp", "Worker Rail Route 213")),
           ("hod_bra_town", 1.0, ("at_vp", "Scrapper Town"))],
    clear={"hod_bra_yards": 6.0, "hod_bra_platform": 5.0, "hod_bra_tower": 4.0, "hod_bra_rail": 4.0, "hod_bra_town": 4.5},
    hook=wrecks,
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (bracca_map.py)\n{imp}"
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
