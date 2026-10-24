"""Lola Sayu, the broken prison world, as one battlefield at the start (976, before the Clone Wars) (research:
WIPGFX/research/lola_sayu/). CANON: an unknown cataclysm took "nearly the entire southern hemisphere", leaving a belt
of planetary debris in orbit and a surface still slowly falling apart; volcanic, "dotted with caves, crevasses, hills
and mountains, alongside river-like cracks that spanned to where the crust ended at its destroyed southern
hemisphere, ... glowing with the heat of the lava"; lava flows from "the southern side's vast Sulfur Sea"; no plant
or animal life, little water. The Citadel, built in 522 BBY by the Republic and the Jedi to hold rogue and fallen
Jedi, stands "on the north-western side of the planet, along a bridge between two lakes of yellow lava, powered by the
geothermal" heat. Point Tarron: the strike team's extraction point near the Citadel (TCW). Owner at the start: the
Republic (it falls to the Confederacy only in the war).
The map: the planet's disc is its surviving northern half; the Sulfur Sea and the crumbling edge fill its south, the
lava cracks run into it, and the lost hemisphere floats as debris in the space south of the disc (PLACEMENT hook).
LAYOUT IS A DESIGN CHOICE beyond the Citadel's north-western place: the crags, crevasse fields, cave labyrinths, the
Sayu Spires; invented names: every state name except the Sulfur Sea, the lava lakes, the minor VPs.
    python "WIPGFX/plans & scripts/lola_sayu_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/lola_sayu_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 43 province ids are kept (strategic region unchanged); only the pixels move.
Run order: lola_sayu_map.py -> planet_terrain_gen.py --planet "Lola Sayu" -> military_buildings.py models hod_lola
-> military_buildings.py place "Lola Sayu" -> lola_sayu_fx.py -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py
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

PLANET = "Lola Sayu"
ZONES_JSON = "WIPGFX/Assets/lola_sayu_zones.json"
ZONES_PNG = "WIPGFX/Assets/lola_sayu_zones.png"
KIND = {"crags": 1, "crevasse": 2, "caves": 3, "citadel": 4, "lake": 5, "sea": 6, "spires": 7, "point": 8}
TERRAIN = {"crags": "hills", "crevasse": "hills", "caves": "hills", "citadel": "urban", "lake": "mountain",
           "sea": "mountain", "spires": "mountain", "point": "hills"}
SEED = 193
CAPITAL = 193
CAPITAL_VP = "The Citadel"
PORT_STATE = CAPITAL
OWNER = "REP"
WARP = (0.12, 6)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
TARGET_PASSABLE = 28                 # user rule: passable provinces outnumber impassable
STRAIGHT = {"citadel", "lake", "point"}   # drawn unwarped: the Citadel's bridge must stay one piece between its lakes
# features painted in order (the Sulfur Sea first among the impassable: it takes the leftover ids), the first to
# claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("The Citadel", "citadel", CAPITAL, 2, [("ell", -0.45, -0.42, 0.13, 0.16, 0)]),
    ("Point Tarron", "point", CAPITAL, 1, [("ell", -0.42, -0.8, 0.14, 0.12, 0)]),
    # the Sulfur Sea fills the south to the broken edge; the lava cracks run into it from the north
    ("Sulfur Sea", "sea", 1180, 0, [("ell", 0.0, 0.85, 1.2, 0.42, 0), ("cap", -0.48, -0.05, -0.36, 0.5, 0.06),
                                    ("cap", 0.05, 0.08, 0.1, 0.5, 0.055), ("cap", 0.48, -0.22, 0.42, 0.5, 0.06)]),
    ("Western Lava Lake", "lake", 1181, 1, [("ell", -0.7, -0.4, 0.13, 0.15, 10)]),
    ("Eastern Lava Lake", "lake", 1182, 1, [("ell", -0.2, -0.46, 0.13, 0.14, -10)]),
    ("Sayu Spires", "spires", 1183, 0, [("ell", 0.55, -0.58, 0.2, 0.15, 30), ("cap", 0.3, -0.75, 0.7, -0.45, 0.08)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((-0.45, -0.55), "crags"), 1040: ((-0.05, -0.8), "crags"), 1041: ((-0.82, 0.05), "crevasse"),
         1042: ((0.82, -0.2), "crags"), 1043: ((-0.05, -0.25), "caves"), 1044: ((0.72, 0.18), "crevasse"),
         1045: ((-0.2, 0.25), "caves")}
STATE_NAMES = {CAPITAL: "Citadel Heights", 1040: "Northern Crags", 1041: "Western Crevasses", 1042: "Eastern Highlands",
               1043: "Cave Labyrinths", 1044: "Ember Fields", 1045: "Crumbling Shelf", 1180: "Sulfur Sea",
               1181: "Western Lava Lake", 1182: "Eastern Lava Lake", 1183: "Sayu Spires"}
IMPASSABLE = {1180, 1181, 1182, 1183}
# victory points: (state, feature or kind, name, value). Canon: the Citadel, Point Tarron; invented: the rest
VPS = [(CAPITAL, "citadel", CAPITAL_VP, 10), (CAPITAL, "point", "Point Tarron", 2),
       (1040, "crags", "Northern Watchpost", 1), (1041, "crevasse", "Crevasse Pass", 1),
       (1042, "crags", "Highland Relay", 1), (1043, "caves", "Cave Mouth", 1), (1044, "crevasse", "Ember Ridge", 1),
       (1045, "caves", "Shelf Edge", 1)]


# terrain (planet_terrain_gen.py --planet "Lola Sayu"; operators: planet_terrain_gen.zone_repaint). Canon: volcanic,
# caves, crevasses, hills, mountains, lava cracks glowing to the broken edge, the Sulfur Sea; no life. The lava (sea,
# lakes) kept level (level) and tinted yellow-orange in the colormap (tint: "two lakes of yellow lava")
TERRAIN_CFG = dict(
    seed=193, base=6, rough=3, open=(1, 2, 3),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 8, 7, 4), tex=["ROCK", ("BROWNMTN", ">", 0.55), ("LAVA", ">", 0.92)],   # crags
                props=[(109, 0.18), (108, 0.06)]),
        2: dict(relief=("rolling", 5, 4, 3), tex=["ROCK2", ("LAVA", ">", 0.82), ("BROWN", "<", 0.2)],      # crevasses
                props=[(109, 0.12), (108, 0.1)]),
        3: dict(relief=("rolling", 7, 6, 4), tex=["BROWN", ("ROCK", ">", 0.55)], props=[(109, 0.1), (108, 0.04)]),  # caves
        4: dict(relief=("ramp_top", 12, 6, 3), tex=25),                                            # the Citadel's crag
        5: dict(relief=("flat", 1), tex="LAVA"),                                                   # the lava lakes
        6: dict(relief=("flat", 0.5), tex="LAVA"),                                                 # the Sulfur Sea
        7: dict(relief=("spires", 16, 8, 0.1, (1.2, 2.4), (22, 42)), tex=["ROCK", ("BROWNMTN", ">", 0.5)]),
        8: dict(relief=("ramp_top", 13, 6, 3), tex=["ROCK", (25, ">", 0.5)], props=[(109, 0.1)]),   # Point Tarron
    },
    steep=("ROCK2", 7, (1, 2, 3)),
    city={},   # no towns: the Citadel is the only building on the planet
    prop_clear=1.4,
    level=(5, 6),
    tint={5: ((1.0, 0.82, 0.25), 0.7), 6: ((1.0, 0.62, 0.2), 0.6)},
)


def debris(ctx):
    """the lost southern hemisphere: crust fragments floating in the space south of the disc, where the other half
    of the planet was (canon: "a gravitational belt of planetary debris"); big ones close to the broken edge, smaller
    ones farther out, none over land"""
    import random as _r
    zone, rng = ctx["zone"], _r.Random("lola_debris")
    land = zone > 0
    ys, xs = np.nonzero(land)
    cx, R = (xs.min() + xs.max()) / 2, (xs.max() - xs.min()) / 2           # the whole planet's disc, from its width
    cy = ys.min() + R
    off = ndi.distance_transform_edt(~land)
    placed = []
    for _ in range(4000):
        if len(placed) >= DEBRIS_N:
            break
        a = rng.uniform(0.05, math.pi - 0.05)                               # the southern half-disc (rows grow south)
        d = R * math.sqrt(rng.uniform(0.0, 1.0)) * 1.15
        r, c = cy + d * math.sin(a), cx + d * math.cos(a)
        if not (0 <= int(r) < zone.shape[0] and 0 <= int(c) < zone.shape[1]) or off[int(r), int(c)] < 3:
            continue
        near = 1 - min(off[int(r), int(c)] / R, 1)                          # 1 at the broken edge
        size = 0.45 + 0.6 * near * rng.uniform(0.6, 1.0)          # the pieces are ~6 map units across
        if any(math.hypot(r - a_, c - b_) < 4.0 * (size + s_) for a_, b_, s_ in placed):
            continue
        placed.append((r, c, size))
        kinds = "ac" if size > 0.75 else "bdc"                             # deep chunks and wedges near the edge
        ctx["put"](f"hod_lola_chunk_{rng.choice(kinds)}{rng.randrange(3)}", round(size, 2), r, c)   # 3 = LOLA_TURNS


DEBRIS_N = 22
# models (military_buildings.py place "Lola Sayu"): big, custom (user rule 2026-10-14); the planet is small (~26 px
# radius): the Citadel at 0.8
PLACEMENT = dict(
    new_models={"hod_lola_citadel"} | {f"hod_lola_chunk_{v}{t}" for v in "abcd" for t in range(3)},
    items=[("hod_lola_citadel", 0.8, ("at_vp", CAPITAL_VP))],
    clear={"hod_lola_citadel": 5.0},
    hook=debris,
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (lola_sayu_map.py)\n{imp}"
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
