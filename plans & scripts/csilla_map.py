"""Csilla, the Chiss homeworld, as one battlefield in the Clone Wars (research: WIPGFX/research/csilla/). CANON: ice-locked
and cold; Csaplar, the capital of the planet and of the Chiss Ascendancy, with the Assembly Cupola (the Syndicure), the
Convocate Hall and the headquarters of the Expansionary Defense Fleet; the Defense Force headquarters just outside
Csaplar. LEGENDS: glaciers and caves; the Chiss cities lie under the ice; Ac'siel; the Expeditionary Library, a massive
underground library. Owner: CHS.
LAYOUT IS A DESIGN CHOICE (the user, 2026-10-23: many impassable states, corridors): Csaplar in a basin in the middle-north
with the Assembly Cupola and the Fleet headquarters, the Defense Force headquarters east of it; Ac'siel south-west (the
Csaus lane); the Expeditionary Library south-east (the Copero lane); the Eastern Ice Plain north-east (the Cioral lane); the
Northern Ice Fields, the Western Glacier and the Southern Ice Shelf; seven glacier ridges, icefalls and crevasse fields
impassable between them, so the ice is crossed by a few long corridors.
Names from the sources: Csaplar, the Assembly Cupola, the Expansionary Defense Fleet headquarters, the Defense Force
headquarters, Ac'siel, the Expeditionary Library. Invented: the ice-field and ridge names.
    python "WIPGFX/plans & scripts/csilla_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/csilla_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Csilla"
ZONES_JSON = "WIPGFX/Assets/csilla_zones.json"
ZONES_PNG = "WIPGFX/Assets/csilla_zones.png"
KIND = {"city": 1, "cupola": 2, "hq": 3, "library": 4, "icefield": 5, "rockice": 6, "ridge": 7, "crevasse": 8}
TERRAIN = {"city": "urban", "cupola": "urban", "hq": "urban", "library": "hills", "icefield": "plains", "rockice": "hills",
           "ridge": "mountain", "crevasse": "mountain"}
SEED = 183
CAPITAL = 183
CAPITAL_VP = "Csaplar"
CORE = "CHS"
PORT_STATE = 983                     # the Eastern Ice Plain, out to the rim
ICE_IDS = tuple(range(1482, 1489))
OWNER = {s: "CHS" for s in (183, *range(977, 984), *ICE_IDS)}
WARP = (0.1, 9)
TARGET_PASSABLE = 120                # user rule: passable provinces outnumber impassable
STRAIGHT = {"city", "cupola", "hq", "library"}
FEATURES = [
    ("Csaplar", "city", CAPITAL, 4, [("rect", -0.05, -0.2, 0.15, 0.1, 5)]),
    ("Assembly Cupola", "cupola", CAPITAL, 1, [("rect", 0.0, -0.42, 0.06, 0.06, 0)]),
    ("Expansionary Fleet Headquarters", "hq", CAPITAL, 1, [("rect", -0.28, -0.32, 0.06, 0.05, 20)]),
    ("Defense Force Headquarters", "hq", 977, 2, [("rect", 0.36, -0.12, 0.08, 0.06, -15)]),
    ("Ac'siel", "city", 978, 2, [("rect", -0.48, 0.52, 0.1, 0.07, 30)]),
    ("Expeditionary Library", "library", 979, 1, [("rect", 0.42, 0.56, 0.07, 0.06, -25)]),
    ("Frostspine Ridge", "ridge", 1482, 0, [("cap", -0.62, -0.6, -0.3, -0.48, 0.08), ("cap", -0.3, -0.48, -0.2, -0.75, 0.07)]),
    ("Great Crevasse", "crevasse", 1483, 0, [("cap", 0.08, 0.12, 0.62, 0.3, 0.065)]),
    ("Shatter Glacier", "ridge", 1484, 0, [("cap", -0.3, 0.08, -0.12, 0.62, 0.08)]),
    ("Pale Escarpment", "ridge", 1485, 0, [("cap", 0.32, -0.8, 0.5, -0.32, 0.07)]),
    ("Rimeholt Crevasses", "crevasse", 1486, 0, [("cap", -0.95, 0.22, -0.55, 0.12, 0.08)]),
    ("Csaplar Icefall", "ridge", 1487, 0, [("cap", 0.08, 0.5, 0.18, 0.92, 0.07)]),
    ("Deep Ice", "crevasse", 1488, 0, [("cap", 0.68, -0.05, 0.92, 0.25, 0.08)]),
]
SEEDS = {CAPITAL: ((-0.05, -0.15), "icefield"), 977: ((0.35, -0.1), "rockice"), 978: ((-0.5, 0.5), "icefield"),
         979: ((0.42, 0.6), "rockice"), 980: ((0.0, -0.8), "icefield"), 981: ((-0.8, -0.15), "rockice"),
         982: ((-0.15, 0.85), "icefield"), 983: ((0.75, -0.45), "icefield")}
STATE_NAMES = {CAPITAL: "Csaplar", 977: "Defense Force Headquarters", 978: "Ac'siel", 979: "Expeditionary Library",
               980: "Northern Ice Fields", 981: "Western Glacier", 982: "Southern Ice Shelf", 983: "Eastern Ice Plain",
               1482: "Frostspine Ridge", 1483: "Great Crevasse", 1484: "Shatter Glacier", 1485: "Pale Escarpment",
               1486: "Rimeholt Crevasses", 1487: "Csaplar Icefall", 1488: "Deep Ice"}
IMPASSABLE = set(ICE_IDS)
VPS = [(CAPITAL, "Csaplar", CAPITAL_VP, 15), (CAPITAL, "Assembly Cupola", "Assembly Cupola", 5),
       (CAPITAL, "Expansionary Fleet Headquarters", "Expansionary Fleet Headquarters", 3),
       (977, "Defense Force Headquarters", "Defense Force Headquarters", 5), (978, "Ac'siel", "Ac'siel", 5),
       (979, "Expeditionary Library", "Expeditionary Library", 5), (980, "icefield", "Northern Ice Fields", 1),
       (981, "rockice", "Western Glacier", 1), (982, "icefield", "Southern Ice Shelf", 1), (983, "icefield", "Eastern Ice Plain", 1)]

TERRAIN_CFG = dict(
    seed=183, base=4, rough=2, open=(5, 6),
    zones={
        1: dict(relief=("flat", 3), tex=["URBAN", ("SNOWSAND", ">", 0.55)]),                          # sunken cities
        2: dict(relief=("flat", 3), tex=["URBAN", ("SNOWSAND", ">", 0.7)]),                           # the Cupola
        3: dict(relief=("flat", 4), tex=["URBAN", ("SNOWROCK", ">", 0.6)]),                           # headquarters
        4: dict(relief=("flat", 4), tex=["SNOWROCK", ("SNOWSAND", ">", 0.5)]),                        # the library gate
        5: dict(relief=("rolling", 5, 3, 6), tex=["SNOWSAND", ("SNOWFARM", ">", 0.6), ("SNOWROCK", ">", 0.9)],
                props=[(210, 0.08)]),                                                                 # ice fields
        6: dict(relief=("rolling", 9, 6, 4), tex=["SNOWROCK", ("SNOWSAND", ">", 0.5), ("ROCK", ">", 0.9)],
                props=[(210, 0.12), (219, 0.1)]),                                                     # rocky ice
        7: dict(relief=("rolling", 30, 14, 3), tex=["SNOWROCK", ("SNOWSAND", ">", 0.6)], props=[(219, 0.15)]),
        8: dict(relief=("rolling", 1, 1, 3), tex=["SNOWROCK", ("ROCK", ">", 0.6)], props=[(210, 0.2)]),   # crevasses
    },
    city={1: 120, 2: 120, 3: 120},   # map/cities.txt 120: Chiss sunken towers (csi_town)
    prop_clear=1.5,
    colors={1: (0.6, 0.66, 0.78), 2: (0.62, 0.68, 0.8), 3: (0.58, 0.64, 0.74), 4: (0.66, 0.74, 0.86), 5: (0.84, 0.91, 0.97),
            6: (0.7, 0.8, 0.9), 7: (0.6, 0.72, 0.86), 8: (0.26, 0.42, 0.66)},   # ice white, glacier cyan, deep-blue crevasses
)

PLACEMENT = dict(
    new_models={"hod_csi_csaplar", "hod_csi_cupola", "hod_csi_hq", "hod_csi_library"},
    items=[("hod_csi_csaplar", 1.0, ("at_vp", CAPITAL_VP)), ("hod_csi_cupola", 1.0, ("at_vp", "Assembly Cupola")),
           ("hod_csi_hq", 1.0, ("at_vp", "Defense Force Headquarters")), ("hod_csi_hq", 0.7, ("at_vp", "Expansionary Fleet Headquarters")),
           ("hod_csi_library", 1.0, ("at_vp", "Expeditionary Library"))],
    clear={"hod_csi_csaplar": 4.5, "hod_csi_cupola": 3.0, "hod_csi_hq": 3.0, "hod_csi_library": 3.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (csilla_map.py)\n{imp}"
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
