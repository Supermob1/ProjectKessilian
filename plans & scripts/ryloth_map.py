"""Ryloth, the Twi'lek homeworld, as one battlefield in the Clone Wars (research: WIPGFX/research/ryloth/). CANON: deserts,
dense jungles, mesas, valleys, volcanoes; a forest full of predators across the equator; Lessu City, the capital, on its
rock; Nabat, a Twi'lek town; Kala'uun, a starport; Rhovari, west of Lessu; the Jixuan desert in the southern hemisphere;
the barren northern continent; the Bypass Notch; the Tann Province; the Tulara Ravine; the western outskirts; the Battle
of Ryloth (Twi'lek resistance and Republic against the Separatists). Owner: RYL (kept).
LAYOUT IS A DESIGN CHOICE (the user, 2026-10-23: canon Clone Wars, many impassable states): Lessu City on its rock in the
middle-north; Rhovari west of it (the Christophsis lane) and the Western Outskirts beyond (the Farstine lane); Nabat on the
plains east of centre; Kala'uun east (the Tatooine lane); the Northern Barrens north (the Geonosis lane) with the Bypass
Notch; the Whiptree Forest across the middle; the Tann Province south-west; the Jixuan Desert south; seven mesas,
ravines, pinnacles and a volcanic rift impassable.
Names from the sources: Lessu City, Rhovari, Nabat, Kala'uun, the Jixuan Desert, the Tann Province, the Tulara Ravine, the
Bypass Notch, the western outskirts, the northern continent, the whiptree. Invented: the other mesa and rift names.
    python "WIPGFX/plans & scripts/ryloth_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/ryloth_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Ryloth"
ZONES_JSON = "WIPGFX/Assets/ryloth_zones.json"
ZONES_PNG = "WIPGFX/Assets/ryloth_zones.png"
KIND = {"city": 1, "town": 2, "port": 3, "plains": 4, "forest": 5, "desert": 6, "barrens": 7, "mesa": 8, "rift": 9}
TERRAIN = {"city": "urban", "town": "urban", "port": "urban", "plains": "plains", "forest": "jungle", "desert": "desert",
           "barrens": "hills", "mesa": "mountain", "rift": "mountain"}
SEED = 37
CAPITAL = 37
CAPITAL_VP = "Lessu City"
CORE = "RYL"
PORT_STATE = 426                     # Kala'uun, out to the rim
WILD_IDS = tuple(range(1545, 1552))
OWNER = {s: "RYL" for s in (37, *range(424, 432), *WILD_IDS)}
WARP = (0.1, 9)
TARGET_PASSABLE = 128                # user rule: passable provinces outnumber impassable
STRAIGHT = {"city", "town", "port"}
F = lambda name, kind, sid, *shapes: (name, kind, sid, 0, list(shapes))
FEATURES = [
    F("Lessu City", "city", CAPITAL, ("rect", 0.0, -0.22, 0.1, 0.09, 10)),
    F("Rhovari", "town", 424, ("rect", -0.5, -0.4, 0.07, 0.06, 0)),
    F("Nabat", "town", 425, ("rect", 0.35, 0.2, 0.07, 0.06, -10)),
    F("Kala'uun", "port", 426, ("rect", 0.72, -0.15, 0.08, 0.07, 15)),
    F("Bypass Notch", "town", 428, ("rect", 0.32, -0.7, 0.05, 0.04, 0)),
    ("Tulara Ravine", "rift", 1545, 0, [("cap", 0.12, -0.02, 0.55, -0.08, 0.08)]),
    ("Lessu Pinnacles", "mesa", 1546, 0, [("cap", -0.28, -0.42, 0.02, -0.52, 0.08)]),
    ("Great Mesas", "mesa", 1547, 0, [("cap", 0.48, 0.4, 0.62, 0.62, 0.09)]),
    ("Red Canyons", "rift", 1548, 0, [("cap", -0.3, 0.05, -0.72, 0.18, 0.06)]),
    ("Volcanic Rift", "rift", 1549, 0, [("cap", 0.18, 0.52, 0.35, 0.88, 0.07)]),
    ("Northern Mesas", "mesa", 1550, 0, [("cap", -0.15, -0.88, 0.05, -0.68, 0.08)]),
    ("Southern Crags", "mesa", 1551, 0, [("cap", -0.48, 0.68, -0.2, 0.86, 0.08)]),
]
SEEDS = {CAPITAL: ((0.0, -0.2), "plains"), 424: ((-0.5, -0.42), "plains"), 425: ((0.35, 0.22), "plains"),
         426: ((0.75, -0.12), "plains"), 427: ((-0.6, 0.45), "forest"), 428: ((0.35, -0.75), "barrens"),
         429: ((0.05, 0.8), "desert"), 430: ((-0.05, 0.35), "forest"), 431: ((-0.85, -0.05), "barrens")}
STATE_NAMES = {CAPITAL: "Lessu City", 424: "Rhovari", 425: "Nabat", 426: "Kala'uun", 427: "Tann Province",
               428: "Northern Barrens", 429: "Jixuan Desert", 430: "Whiptree Forest", 431: "Western Outskirts",
               1545: "Tulara Ravine", 1546: "Lessu Pinnacles", 1547: "Great Mesas", 1548: "Red Canyons",
               1549: "Volcanic Rift", 1550: "Northern Mesas", 1551: "Southern Crags"}
IMPASSABLE = set(WILD_IDS)
VPS = [(CAPITAL, "Lessu City", CAPITAL_VP, 15), (424, "Rhovari", "Rhovari", 5), (425, "Nabat", "Nabat", 5),
       (426, "Kala'uun", "Kala'uun", 10), (428, "Bypass Notch", "Bypass Notch", 2), (427, "forest", "Tann Province", 2),
       (429, "desert", "Jixuan Desert", 2), (430, "forest", "Whiptree Forest", 1), (431, "barrens", "Western Outskirts", 1)]

TERRAIN_CFG = dict(
    seed=37, base=4, rough=2, open=(4, 5, 6, 7),
    zones={
        1: dict(relief=("mesa", 6, 28, 3, (4, 0.7)), tex=[32, ("BROWN", ">", 0.6)]),                   # Lessu on its rock
        2: dict(relief=("flat", 5), tex=[32, ("GRASS", ">", 0.6)]),                                   # towns
        3: dict(relief=("flat", 5), tex=[32, ("ROCK2", ">", 0.6)]),                                   # Kala'uun starport
        4: dict(relief=("rolling", 5, 4, 5), tex=["SAVANNA", ("GRASS", ">", 0.5), ("BROWN", ">", 0.85)],
                props=[(157, 0.08), (226, 0.05)]),                                                    # plains
        5: dict(relief=("rolling", 6, 4, 5), tex=["JUNGLE", ("FOREST", ">", 0.5), (26, ">", 0.97)],
                props=[(156, 0.45), (157, 0.2)]),                                                     # the whiptree forest
        6: dict(relief=("rolling", 4, 4, 5), tex=["SAND", ("DUNES", ">", 0.55)], props=[(214, 0.05)]),  # the Jixuan
        7: dict(relief=("rolling", 9, 6, 4), tex=["BROWN", ("ROCK2", ">", 0.5)], props=[(214, 0.12), (155, 0.08)]),
        8: dict(relief=("mesa", 6, 34, 2, (4, 0.7)), tex=["BROWNMTN", ("BROWN", ">", 0.5)], props=[(226, 0.12)]),
        9: dict(relief=("rolling", 1, 1, 3), tex=["ROCK", ("LAVA", ">", 0.85)], props=[(108, 0.12)]),     # ravines, rift
    },
    city={1: 130, 2: 130, 3: 130},   # map/cities.txt 130: Twi'lek sandstone towns (ryl_town)
    prop_clear=1.5,
    colors={1: (0.76, 0.58, 0.42), 2: (0.74, 0.62, 0.44), 3: (0.7, 0.62, 0.5), 4: (0.66, 0.62, 0.34), 5: (0.32, 0.46, 0.22),
            6: (0.86, 0.68, 0.42), 7: (0.66, 0.5, 0.36), 8: (0.62, 0.38, 0.26), 9: (0.34, 0.22, 0.18)},   # amber, olive
)

PLACEMENT = dict(
    new_models={"hod_ryl_lessu", "hod_ryl_port"},
    items=[("hod_ryl_lessu", 1.0, ("at_vp", CAPITAL_VP)), ("hod_ryl_port", 1.0, ("at_vp", "Kala'uun"))],
    clear={"hod_ryl_lessu": 4.5, "hod_ryl_port": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (ryloth_map.py)\n{imp}"
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
