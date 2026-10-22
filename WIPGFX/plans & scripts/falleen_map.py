"""Falleen, the homeworld of the Falleen, as one battlefield before the Clone Wars (research: WIPGFX/research/falleen_planet/,
WIPGFX/research/falleen/). CANON: the Hocekureem Sea. LEGENDS: jungles, vast plains and icy mountains, industry; Falleen
Throne the capital, with the Yellow District; the royal House Sizhran; the Falleen held their world, not Coruscant, to be
the galaxy's civilized and cultural capital. (Vader's bacteriological outpost and the razed city come later.) Owner: FAL.
LAYOUT IS A DESIGN CHOICE: Falleen Throne in the middle-west of the plains, the palace of House Sizhran above it and the
Yellow District beside it; the Hocekureem Sea south-east of the capital with its harbour coast; the Ice Crown Mountains
across the north with the highlands beyond them; the Foundry Belt north-west (the Mimban lane); the Western Jungles (the
Allanteen VI lane), the Falleen Plains east (the Bothawui lane), the Eastern Jungles south-east, the Southern Plains
(the Farstine lane); the Western Ice Peaks impassable.
Names from the sources: Falleen Throne, Yellow District, House Sizhran, the Hocekureem Sea. Invented: Palace of House
Sizhran, Hocekureem Coast and Spaceport, Ice Crown Mountains / Highlands, Foundry Belt, Throne Foundries, Falleen Plains,
Eastern / Western Jungles, Southern Plains, Western Ice Peaks.
    python "WIPGFX/plans & scripts/falleen_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/falleen_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All province ids are kept (strategic region unchanged); only the pixels move.
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

PLANET = "Falleen"
ZONES_JSON = "WIPGFX/Assets/falleen_zones.json"
ZONES_PNG = "WIPGFX/Assets/falleen_zones.png"
KIND = {"city": 1, "palace": 2, "yellow": 3, "harbour": 4, "foundry": 5, "plains": 6, "jungle": 7, "highland": 8,
        "sea": 9, "ice": 10}
TERRAIN = {"city": "urban", "palace": "urban", "yellow": "urban", "harbour": "urban", "foundry": "urban", "plains": "plains",
           "jungle": "jungle", "highland": "hills", "sea": "mountain", "ice": "mountain"}
SEED = 29
CAPITAL = 29
CAPITAL_VP = "Falleen Throne"
CORE = "FAL"
PORT_STATE = 395                     # the Falleen Plains, out to the rim (the Hocekureem Coast faces only the inner sea)
OWNER = {s: "FAL" for s in (29, *range(393, 400), 1427, 1428, 1429)}
WARP = (0.1, 9)
TARGET_PASSABLE = 126                # user rule: passable provinces outnumber impassable
STRAIGHT = {"palace", "yellow"}
FEATURES = [
    ("Palace of House Sizhran", "palace", CAPITAL, 1, [("rect", -0.24, -0.16, 0.07, 0.05, 0)]),
    ("Yellow District", "yellow", CAPITAL, 1, [("rect", -0.04, 0.04, 0.06, 0.045, 10)]),
    ("Falleen Throne", "city", CAPITAL, 3, [("ell", -0.16, -0.04, 0.17, 0.12, 10)]),
    ("Hocekureem Spaceport", "harbour", 393, 1, [("ell", 0.06, 0.3, 0.08, 0.05, 30)]),
    ("Throne Foundries", "foundry", 399, 2, [("ell", -0.52, -0.46, 0.12, 0.09, -30)]),
    ("Hocekureem Sea", "sea", 1427, 0, [("ell", 0.3, 0.45, 0.32, 0.19, 15)]),
    ("Ice Crown Mountains", "ice", 1428, 0, [("cap", -0.15, -0.6, 0.5, -0.52, 0.1), ("cap", 0.5, -0.52, 0.68, -0.24, 0.09)]),
    ("Western Ice Peaks", "ice", 1429, 0, [("cap", -0.82, 0.22, -0.58, 0.52, 0.1)]),
]
SEEDS = {CAPITAL: ((-0.18, -0.05), "plains"), 393: ((0.0, 0.36), "plains"), 394: ((0.2, -0.82), "highland"),
         395: ((0.68, 0.0), "plains"), 396: ((0.62, 0.7), "jungle"), 397: ((-0.78, -0.05), "jungle"),
         398: ((-0.15, 0.8), "plains"), 399: ((-0.5, -0.5), "plains")}
STATE_NAMES = {CAPITAL: "Falleen Throne", 393: "Hocekureem Coast", 394: "Ice Crown Highlands", 395: "Falleen Plains",
               396: "Eastern Jungles", 397: "Western Jungles", 398: "Southern Plains", 399: "Foundry Belt",
               1427: "Hocekureem Sea", 1428: "Ice Crown Mountains", 1429: "Western Ice Peaks"}
IMPASSABLE = {1427, 1428, 1429}
VPS = [(CAPITAL, "Falleen Throne", CAPITAL_VP, 20), (CAPITAL, "Palace of House Sizhran", "Palace of House Sizhran", 10),
       (CAPITAL, "Yellow District", "Yellow District", 3), (393, "Hocekureem Spaceport", "Hocekureem Spaceport", 3),
       (399, "Throne Foundries", "Throne Foundries", 3), (394, "highland", "Ice Crown Highlands", 1),
       (395, "plains", "Falleen Plains", 1), (396, "jungle", "Eastern Jungles", 1), (397, "jungle", "Western Jungles", 1),
       (398, "plains", "Southern Plains", 1)]

TERRAIN_CFG = dict(
    seed=29, base=4, rough=2, open=(6, 7, 8),
    zones={
        1: dict(relief=("flat", 6), tex=["URBAN", ("GRASS", ">", 0.6)]),                              # Falleen Throne
        2: dict(relief=("ramp_top", 12, 6, 3), tex="URBAN"),                                          # the palace, raised
        3: dict(relief=("flat", 6), tex="URBAN"),                                                     # the Yellow District
        4: dict(relief=("flat", 4), tex=["URBAN", ("SAND", ">", 0.6)]),                               # the spaceport
        5: dict(relief=("flat", 5), tex=["URBAN", ("BROWN", ">", 0.5)]),                              # the foundries
        6: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("SAVANNA", ">", 0.55), ("FARM", ">", 0.85), (13, ">", 0.95)],
                props=[(245, 0.3), (31, 0.05)]),                                                      # the vast plains
        7: dict(relief=("rolling", 7, 4, 6), tex=["JUNGLE", ("JUNGLE2", ">", 0.5)], props=[(41, 0.35), (31, 0.45)]),   # jungles
        8: dict(relief=("rolling", 14, 8, 5), tex=["SNOWROCK", ("ROCK", ">", 0.5), ("GRASSHILL", ">", 0.85)]),   # icy highlands
        9: dict(relief=("flat", 0.3), tex="WATER"),                                                   # the Hocekureem Sea
        10: dict(relief=("spires", 22, 12, 0.12, (1.5, 3.0), (25, 50)), tex=["SNOWROCK", ("ROCK", ">", 0.55)]),   # ice mountains
    },
    steep=("ROCK", 6, (6, 7, 8)),
    city={1: 104, 2: 104, 3: 104, 4: 104, 5: 104, 6: 104},   # map/cities.txt 104: Falleen's tiered jade towns (fal_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.74, 0.7, 0.62), 2: (0.82, 0.74, 0.5), 3: (0.86, 0.76, 0.3), 4: (0.72, 0.7, 0.62), 5: (0.56, 0.48, 0.44),
            6: (0.66, 0.68, 0.28), 7: (0.06, 0.46, 0.34), 8: (0.82, 0.86, 0.9), 9: (0.1, 0.4, 0.6), 10: (0.92, 0.94, 0.98)},   # jade jungle, gold plains, ice
)

PLACEMENT = dict(
    new_models={"hod_fal_throne", "hod_fal_palace", "hod_fal_yellow", "hod_fal_spaceport", "hod_fal_foundry"},
    items=[("hod_fal_throne", 1.0, ("at_vp", CAPITAL_VP)), ("hod_fal_palace", 1.0, ("at_vp", "Palace of House Sizhran")),
           ("hod_fal_yellow", 0.8, ("at_vp", "Yellow District")), ("hod_fal_spaceport", 0.9, ("at_vp", "Hocekureem Spaceport")),
           ("hod_fal_foundry", 0.9, ("at_vp", "Throne Foundries"))],
    clear={"hod_fal_throne": 5.0, "hod_fal_palace": 4.0, "hod_fal_yellow": 2.5, "hod_fal_spaceport": 3.5, "hod_fal_foundry": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (falleen_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {OWNER[sid]}\n\t\tadd_core_of = {CORE}\n\t}}\n"
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
