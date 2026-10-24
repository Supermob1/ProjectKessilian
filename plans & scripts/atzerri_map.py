"""Atzerri, the free-trade world of the Colonies, as one battlefield before the Clone Wars (research:
WIPGFX/research/atzerri/). LEGENDS: mostly marshes and cities where almost anything, legal or illegal, could be had for a
price; Talos, a major spaceport city, with the Trader's Plaza (a gauntlet of gaudily lit stores) and the Pemblehov
District in its second-tier outer districts; Skreeka, a smaller spaceport just south-east of Talos; the Freeman Cantina.
Owner: FON (as before).
THE USER, 2026-10-22: trade cities in marshes: Talos and Skreeka as big sprawling spaceport cities rising out of
marshland.
LAYOUT IS A DESIGN CHOICE beyond Skreeka lying south-east of Talos: Talos west of the middle with the Trader's Plaza at
its heart and the Pemblehov District on its western edge (the Bestine IV lane); Skreeka south-east with the Freeman
Cantina; marsh states round them: the Northern Marshes (the Cato Neimoidia lane), the Eastern Bayous (the Allanteen VI
lane), the Western Fens, the Southern Mires, the Reed Flats; deep mires and lagoons impassable.
Names from the sources: Talos, Trader's Plaza, Pemblehov District, Skreeka, Freeman Cantina. Invented: Talos Landing
Field, every marsh, mire and lagoon name.
    python "WIPGFX/plans & scripts/atzerri_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/atzerri_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Atzerri"
ZONES_JSON = "WIPGFX/Assets/atzerri_zones.json"
ZONES_PNG = "WIPGFX/Assets/atzerri_zones.png"
KIND = {"city": 1, "plaza": 2, "port": 3, "district": 4, "cantina": 5, "marsh": 6, "bayou": 7, "fen": 8, "reeds": 9,
        "mire": 10, "lagoon": 11}
TERRAIN = {"city": "urban", "plaza": "urban", "port": "urban", "district": "urban", "cantina": "urban", "marsh": "marsh",
           "bayou": "marsh", "fen": "marsh", "reeds": "plains", "mire": "mountain", "lagoon": "mountain"}
SEED = 25
CAPITAL = 25
CAPITAL_VP = "Talos"
CORE = "FON"
PORT_STATE = 367                     # Skreeka
OWNER = {s: "FON" for s in (25, *range(366, 373), 1414, 1415, 1416, 1417)}
WARP = (0.1, 9)
TARGET_PASSABLE = 124                # user rule: passable provinces outnumber impassable
STRAIGHT = {"plaza", "cantina"}
FEATURES = [
    ("Trader's Plaza", "plaza", CAPITAL, 1, [("rect", -0.18, -0.08, 0.06, 0.05, 15)]),
    ("Talos Landing Field", "port", CAPITAL, 1, [("ell", -0.02, -0.25, 0.12, 0.08, 20)]),
    ("Talos", "city", CAPITAL, 4, [("ell", -0.2, -0.1, 0.24, 0.17, 15)]),
    ("Pemblehov District", "district", 366, 2, [("ell", -0.52, -0.22, 0.12, 0.1, -10)]),
    ("Freeman Cantina", "cantina", 367, 1, [("rect", 0.22, 0.4, 0.04, 0.035, 0)]),
    ("Skreeka", "port", 367, 3, [("ell", 0.34, 0.36, 0.2, 0.14, -20)]),
    ("Black Mire", "mire", 1414, 0, [("ell", 0.32, -0.2, 0.195, 0.156, 30)]),
    ("Atzerri Lagoon", "lagoon", 1415, 0, [("ell", -0.38, 0.44, 0.26, 0.156, 20)]),
    ("Sinking Fens", "mire", 1416, 0, [("cap", 0.5, -0.5, 0.76, -0.22, 0.128)]),
    ("Southern Deeps", "lagoon", 1417, 0, [("cap", 0.12, 0.68, 0.46, 0.8, 0.128)]),
]
SEEDS = {CAPITAL: ((-0.2, -0.1), "marsh"), 366: ((-0.6, -0.3), "fen"), 367: ((0.34, 0.36), "reeds"),
         368: ((0.1, -0.68), "marsh"), 369: ((0.78, 0.05), "bayou"), 370: ((-0.75, 0.15), "fen"),
         371: ((-0.1, 0.62), "marsh"), 372: ((0.62, 0.62), "reeds")}
STATE_NAMES = {CAPITAL: "Talos", 366: "Pemblehov District", 367: "Skreeka", 368: "Northern Marshes", 369: "Eastern Bayous",
               370: "Western Fens", 371: "Southern Mires", 372: "Reed Flats", 1414: "Black Mire", 1415: "Atzerri Lagoon",
               1416: "Sinking Fens", 1417: "Southern Deeps"}
IMPASSABLE = {1414, 1415, 1416, 1417}
VPS = [(CAPITAL, "Talos", CAPITAL_VP, 20), (CAPITAL, "Trader's Plaza", "Trader's Plaza", 5),
       (CAPITAL, "Talos Landing Field", "Talos Landing Field", 2), (366, "Pemblehov District", "Pemblehov District", 3),
       (367, "Skreeka", "Skreeka", 10), (367, "Freeman Cantina", "Freeman Cantina", 2), (368, "marsh", "Northern Marshes", 1),
       (369, "bayou", "Eastern Bayous", 1), (370, "fen", "Western Fens", 1), (371, "marsh", "Southern Mires", 1),
       (372, "reeds", "Reed Flats", 1)]

TERRAIN_CFG = dict(
    seed=25, base=4, rough=2, open=(6, 7, 8, 9),
    zones={
        1: dict(relief=("flat", 7), tex=["URBAN", (13, ">", 0.4), ("WATER", ">", 0.94)]),            # Talos, raised on its pilings
        2: dict(relief=("flat", 4), tex="URBAN"),                                                     # the Trader's Plaza
        3: dict(relief=("flat", 4), tex=["URBAN", ("ROCK2", ">", 0.6)]),                              # the spaceports
        4: dict(relief=("flat", 6), tex=["URBAN", (13, ">", 0.35), ("WATER", ">", 0.9)]),             # Pemblehov
        5: dict(relief=("flat", 4), tex="URBAN"),                                                     # the cantina
        6: dict(relief=("rolling", 4, 4, 4), tex=["JUNGLE", ("WATER", ">", 0.62), ("JUNGLE2", ">", 0.85), (26, ">", 0.96)],
                props=[(255, 0.35), (254, 0.15)]),                                                    # marshes: hummocks and pools
        7: dict(relief=("rolling", 3, 4, 4), tex=["JUNGLE2", ("WATER", ">", 0.6), (26, ">", 0.96)], props=[(254, 0.4), (255, 0.2)]),
        8: dict(relief=("rolling", 6, 5, 5), tex=["JUNGLE", ("GRASSHILL", ">", 0.6), ("WATER", ">", 0.85), (26, ">", 0.96)],
                props=[(255, 0.4), (254, 0.15)]),                                                     # fens: low wooded rises
        9: dict(relief=("rolling", 5, 4, 6), tex=["GRASS", ("WATER", ">", 0.75), (26, ">", 0.95)], props=[(255, 0.5)]),
        10: dict(relief=("flat", 0.3), tex="WATER"),                                                  # the deep mires
        11: dict(relief=("flat", 0.3), tex="WATER"),                                                  # the lagoons
    },
    city={1: 102, 2: 102, 3: 102, 4: 102, 5: 102, 6: 102, 9: 102},   # map/cities.txt 102: Atzerri's market towns (atz_town)
    prop_clear=1.5,
    shore_rise=(3, 2.0),
    lights=dict(zones=(1, 2, 3, 4, 5), rgb=(1.0, 0.45, 0.8), density=0.18, mix=0.8),   # the gaudy lights of the stores
    colors={1: (0.62, 0.56, 0.6), 2: (0.82, 0.5, 0.74), 3: (0.66, 0.64, 0.62), 4: (0.56, 0.5, 0.56), 5: (0.8, 0.46, 0.7),
            6: (0.3, 0.5, 0.36), 7: (0.22, 0.44, 0.4), 8: (0.36, 0.5, 0.3), 9: (0.56, 0.6, 0.34), 10: (0.12, 0.3, 0.3),
            11: (0.1, 0.36, 0.42)},   # teal marsh under magenta neon
)

PLACEMENT = dict(
    new_models={"hod_atz_talos", "hod_atz_plaza", "hod_atz_skreeka", "hod_atz_cantina"},
    items=[("hod_atz_talos", 1.0, ("at_vp", CAPITAL_VP)), ("hod_atz_plaza", 0.8, ("at_vp", "Trader's Plaza")),
           ("hod_atz_skreeka", 1.0, ("at_vp", "Skreeka")), ("hod_atz_cantina", 0.7, ("at_vp", "Freeman Cantina"))],
    clear={"hod_atz_talos": 5.5, "hod_atz_plaza": 2.5, "hod_atz_skreeka": 4.5, "hod_atz_cantina": 2.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (atzerri_map.py)\n{imp}"
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
