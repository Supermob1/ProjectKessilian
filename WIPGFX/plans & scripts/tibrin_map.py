"""Tibrin, the Ishi Tib ocean world, as one battlefield in the Clone Wars (research: WIPGFX/research/tibrin/; CANON: Tibrina
the capital on the ocean, phosphorescent seas, coral reefs tall as the sky, storm seas; LEGENDS: Ishi Tib cities built on
and out of the reefs, the Blue North Reef, sand bars, Suribran Tu's palace; the Battle of Tibrin, 22 BBY, and the Tibrin
revolution that took the world to the Confederacy). Owner: TBR (kept).
State 46 (named Nkllon by the generic state pass, owned and cored by TBR, inside Tibrin's disc) is Tibrin's
capital state.
LAYOUT IS A DESIGN CHOICE (an archipelago of reefs, the sea as many impassable states; cities in the water, the user's rule):
Tibrina on the central reef with Suribran Tu's palace, the Blue North Reef north, sand bars joining the reefs; storm seas
round them.
Names from the sources: Tibrina, Suribran Tu's palace, the Blue North Reef, the storm seas, the sand bars. Invented: the other
reefs' and seas' names.
    python "WIPGFX/plans & scripts/tibrin_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/tibrin_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Tibrin"
ZONES_JSON = "WIPGFX/Assets/tibrin_zones.json"
ZONES_PNG = "WIPGFX/Assets/tibrin_zones.png"
KIND = {"city": 1, "reef": 2, "sandbar": 3, "shallows": 4, "sea": 5}
TERRAIN = {"city": "urban", "reef": "hills", "sandbar": "plains", "shallows": "marsh", "sea": "mountain"}
SEED = 46
CAPITAL = 46
CAPITAL_VP = "Tibrina"
CORE = "TBR"
PORT_STATE = 485
SEA_IDS = tuple(range(1619, 1625))
OWNER = {s: "TBR" for s in (46, *range(485, 492), *SEA_IDS)}
WARP = (0.09, 9)
TARGET_PASSABLE = 122                # user rule: passable provinces outnumber impassable
STRAIGHT = {"city"}
F = lambda name, kind, sid, *shapes: (name, kind, sid, 0, list(shapes))
FEATURES = [
    F("Tibrina", "city", 46, ("rect", 0.0, 0.0, 0.1, 0.08, 0)),
    F("Suribran Tu's Palace", "city", 46, ("rect", 0.12, 0.16, 0.05, 0.05, 0)),
    F("Central Reef", "reef", 46, ("ell", 0.0, 0.03, 0.3, 0.24, 15)),
    F("Blue North Reef", "reef", 486, ("ell", -0.1, -0.66, 0.26, 0.14, -10), ("cap", -0.1, -0.66, -0.2, -0.99, 0.05)),   # spits to the rim: the lanes land there
    F("Eastern Reefs", "reef", 488, ("ell", 0.68, -0.1, 0.16, 0.28, 10), ("cap", 0.68, -0.1, 0.99, -0.05, 0.05)),
    F("Southern Reefs", "reef", 489, ("ell", 0.15, 0.68, 0.26, 0.14, 15), ("cap", 0.15, 0.68, 0.3, 0.97, 0.05)),
    F("Lagoon Reefs", "reef", 485, ("ell", -0.46, 0.55, 0.17, 0.12, 25)),
    F("Western Atolls", "reef", 490, ("ell", -0.66, 0.18, 0.16, 0.24, -15), ("cap", -0.66, 0.18, -0.99, 0.12, 0.05)),
    F("Phosphor Shallows", "shallows", 491, ("ell", -0.5, -0.4, 0.14, 0.1, 30), ("cap", -0.5, -0.4, -0.2, -0.2, 0.05)),
    F("Great Sand Bars", "sandbar", 487, ("cap", -0.06, -0.22, -0.1, -0.54, 0.05), ("cap", 0.28, -0.05, 0.54, -0.08, 0.05),
      ("cap", 0.06, 0.26, 0.12, 0.56, 0.05), ("cap", -0.28, 0.1, -0.52, 0.16, 0.05),
      ("cap", -0.2, 0.22, -0.4, 0.46, 0.05)),
]
SEEDS = {1619: ((-0.5, -0.75), "sea"), 1620: ((0.45, -0.6), "sea"), 1621: ((0.55, 0.5), "sea"), 1622: ((-0.15, 0.88), "sea"),
         1623: ((-0.88, -0.2), "sea"), 1624: ((0.92, 0.25), "sea")}
STATE_NAMES = {CAPITAL: "Tibrina", 485: "Lagoon Reefs", 486: "Blue North Reef", 487: "Great Sand Bars", 488: "Eastern Reefs",
               489: "Southern Reefs", 490: "Western Atolls", 491: "Phosphor Shallows", 1619: "Northern Storm Sea",
               1620: "Glowing Sea", 1621: "Eastern Storm Sea", 1622: "Southern Storm Sea", 1623: "Western Deep",
               1624: "Eastern Deep"}
IMPASSABLE = set(SEA_IDS)
VPS = [(CAPITAL, "Tibrina", CAPITAL_VP, 15), (CAPITAL, "Suribran Tu's Palace", "Suribran Tu's Palace", 5),
       (485, "Lagoon Reefs", "Lagoon Reefs", 1), (486, "Blue North Reef", "Blue North Reef", 3), (487, "Great Sand Bars", "Great Sand Bars", 1),
       (488, "Eastern Reefs", "Eastern Reefs", 2), (489, "Southern Reefs", "Southern Reefs", 2),
       (490, "Western Atolls", "Western Atolls", 1), (491, "Phosphor Shallows", "Phosphor Shallows", 1)]

TERRAIN_CFG = dict(
    seed=485, base=4, rough=2, open=(2, 3, 4),
    zones={
        1: dict(relief=("flat", 0.3), tex="WATER"),                                                   # reef cities in the water
        2: dict(relief=("rolling", 9, 7, 4), tex=["ROCK2", ("SAND", ">", 0.55), ("URBAN", ">", 0.95)],
                props=[(116, 0.45), (117, 0.15), (118, 0.08)]),                                       # coral reefs
        3: dict(relief=("flat", 1.5), tex=["SAND", ("DUNES", ">", 0.7)], props=[(117, 0.1)]),          # sand bars
        4: dict(relief=("flat", 0.8), tex=["SAND", ("WATER", ">", 0.5)], props=[(253, 0.3), (116, 0.2)]),   # shallows
        5: dict(relief=("flat", 0.3), tex="WATER"),                                                   # the seas
    },
    steep=("ROCK2", 6, (2,)),
    city={2: 142},   # map/cities.txt 142: Tibrin's reef towns (tib_town)
    prop_clear=1.5,
    shore_rise=(3, 2.0),
    colors={1: (0.06, 0.5, 0.62), 2: (0.82, 0.56, 0.5), 3: (0.92, 0.86, 0.66), 4: (0.3, 0.7, 0.72), 5: (0.04, 0.42, 0.62)},
)

# models (military_buildings.py place Tibrin): big, custom (user rule 2026-10-14); Tibrina stands in the water
PLACEMENT = dict(
    new_models={"hod_tib_city", "hod_tib_palace"},
    items=[("hod_tib_city", 1.0, ("at_vp", CAPITAL_VP)), ("hod_tib_palace", 1.0, ("at_vp", "Suribran Tu's Palace"))],
    no_pad={"hod_tib_city", "hod_tib_palace"},
    clear={"hod_tib_city": 5.0, "hod_tib_palace": 3.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (tibrin_map.py)\n{imp}"
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
