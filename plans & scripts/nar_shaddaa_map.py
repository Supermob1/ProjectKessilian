"""Nar Shaddaa, the Smugglers' Moon of Nal Hutta, as one battlefield before the Clone Wars (research:
WIPGFX/research/nar_shaddaa/). CANON: an ecumenopolis, its whole surface urban sprawl, its lights visible from space;
Hutta Town the capital, huge tower blocks with shanty skyslums filling every gap; Wormstew Town, the Corellian Sector, New
Vertica; the Nar Shaddaa spaceport; the Palace of Grakkus the Hutt; the Slag Pit. LEGENDS: the Vertical City, layer on
layer like Coruscant but filthy and dangerous top to bottom; the Duros Sector, the Red Light Sector, the Refugee Sector,
the industrial sectors, the Undercity. Owner: HTT.
LAYOUT, A DESIGN CHOICE (the street network of empress_teta_map.py, scaled to the moon's small disc): Hutta Town's plaza
in the middle with the Palace of Grakkus; the sectors round it, each a plaza with its streets; the spaceport on the
southern rim (the Nal Hutta lane), the Upper Industrial Sector with the Slag Pit on the western rim (the Toydaria lane);
every enclosed pocket an impassable stack of tower blocks.
Names from the sources: every district name, the Palace of Grakkus the Hutt, the Slag Pit, the spaceport. Invented: the
megablock names.
    python "WIPGFX/plans & scripts/nar_shaddaa_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/nar_shaddaa_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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
from korriban_map import shape, uncross

PLANET = "Nar Shaddaa"
ZONES_JSON = "WIPGFX/Assets/nar_shaddaa_zones.json"
ZONES_PNG = "WIPGFX/Assets/nar_shaddaa_zones.png"
KIND = {"plaza": 1, "core": 2, "palace": 3, "pit": 4, "port": 6, "street": 7, "blocks": 10}
TERRAIN = {k: "urban" for k in KIND}
TERRAIN.update(blocks="mountain")
SEED = 66
CAPITAL = 66
CAPITAL_VP = "Hutta Town"
CORE = "HTT"
PORT_STATE = 621                     # the Nar Shaddaa spaceport
WARP = (0.04, 9)
TARGET_PASSABLE = 37                 # 60 ids on this small moon
STREET = 0.06                        # street half-width (moon radii): ~4 px wide on the 32 px disc
STRAIGHT = {"palace"}
MIN_BLOCK = 25

DISTRICTS = {66: "Hutta Town", 618: "Corellian Sector", 619: "Wormstew Town", 620: "New Vertica", 621: "Nar Shaddaa Spaceport",
             622: "Duros Sector", 623: "Red Light Sector", 624: "Refugee Sector", 625: "Upper Industrial Sector"}
FEATURES = [
    ("Palace of Grakkus the Hutt", "palace", 66, 1, [("rect", 0.1, -0.08, 0.1, 0.08, 0)]),
    ("Slag Pit", "pit", 625, 1, [("ell", -0.74, 0.0, 0.1, 0.1, 0)]),
    ("Hutta Town", "core", 66, 2, [("ell", 0.0, 0.0, 0.24, 0.18, 10), ("rect", 0.0, 0.0, 0.34, 0.07, 10)]),
    ("Nar Shaddaa Spaceport", "port", 621, 0, [("ell", -0.22, 0.84, 0.3, 0.18, 10)]),
    ("Upper Industrial Sector", "plaza", 625, 0, [("ell", -0.8, 0.0, 0.18, 0.26, 0)]),
    ("Corellian Sector", "plaza", 618, 0, [("ell", 0.48, -0.46, 0.15, 0.12, 30)]),
    ("Wormstew Town", "plaza", 619, 0, [("ell", 0.5, 0.42, 0.15, 0.12, -20)]),
    ("New Vertica", "plaza", 620, 0, [("ell", -0.02, -0.72, 0.16, 0.12, 0)]),
    ("Duros Sector", "plaza", 622, 0, [("ell", -0.5, -0.46, 0.14, 0.12, -30)]),
    ("Red Light Sector", "plaza", 623, 0, [("ell", 0.82, 0.0, 0.14, 0.18, 0)]),
    ("Refugee Sector", "plaza", 624, 0, [("ell", -0.52, 0.5, 0.14, 0.12, 20)]),
]
STREETS = [   # (state, points)
    (66, [(0.0, 0.0), (0.48, -0.46)]), (66, [(0.0, 0.0), (0.5, 0.42)]), (66, [(0.0, 0.0), (-0.02, -0.72)]),
    (66, [(0.0, 0.0), (-0.5, -0.46)]), (66, [(0.0, 0.0), (-0.52, 0.5)]), (66, [(0.0, 0.0), (-0.8, 0.0)]),
    (66, [(0.0, 0.0), (0.82, 0.0)]), (621, [(-0.22, 0.84), (-0.52, 0.5)]), (621, [(-0.22, 0.84), (0.5, 0.42)]),
    (620, [(-0.02, -0.72), (0.48, -0.46)]), (620, [(-0.02, -0.72), (-0.5, -0.46)]),
]
BLOCKS = {1449: ("Vertical Stacks", (-0.21, -0.4)), 1450: ("Undercity Stacks", (-0.03, 0.42)),
          1451: ("Outer Tower Blocks", (0.06, -0.09)), 1452: ("Skyslums", (0.13, -0.38))}
STATE_NAMES = {**DISTRICTS, **{k: v[0] for k, v in BLOCKS.items()}}
IMPASSABLE = set(BLOCKS)
OWNER = {s: "HTT" for s in STATE_NAMES}
VPS = [(66, "Hutta Town", CAPITAL_VP, 15), (66, "Palace of Grakkus the Hutt", "Palace of Grakkus the Hutt", 5),
       (621, "Nar Shaddaa Spaceport", "Nar Shaddaa Spaceport", 5), (625, "Slag Pit", "Slag Pit", 2),
       (618, "Corellian Sector", "Corellian Sector", 3), (619, "Wormstew Town", "Wormstew Town", 2),
       (620, "New Vertica", "New Vertica", 3), (622, "Duros Sector", "Duros Sector", 2), (623, "Red Light Sector", "Red Light Sector", 2),
       (624, "Refugee Sector", "Refugee Sector", 1), (625, "Upper Industrial Sector", "Upper Industrial Sector", 2)]

TERRAIN_CFG = dict(
    seed=66, base=4, rough=1, open=(1, 6, 7),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", (13, ">", 0.5)]),                                   # sector plazas
        2: dict(relief=("flat", 5), tex=["URBAN", (13, ">", 0.6)]),                                   # Hutta Town
        3: dict(relief=("flat", 6), tex="URBAN"),                                                     # Grakkus' palace
        4: dict(relief=("flat", 1), tex=["ROCK2", ("BROWN", ">", 0.5)]),                              # the Slag Pit
        6: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.7)]),                              # the spaceport
        7: dict(relief=("flat", 4), tex=["URBAN", (13, ">", 0.5)]),                                   # streets
        10: dict(relief=("rolling", 11, 3, 3), tex=["URBAN", (13, ">", 0.1)]),                        # tower-block stacks
    },
    city={1: 110, 2: 110, 7: 110, 10: 110},   # map/cities.txt 110: Nar Shaddaa's grimy tower blocks (nsh_town)
    prop_clear=1.5,
    lights=dict(zones=(1, 2, 6, 7, 10), rgb=(1.0, 0.4, 0.75), density=0.3, mix=0.85),   # the Smugglers' Moon neon
    colors={1: (0.5, 0.46, 0.5), 2: (0.56, 0.5, 0.52), 3: (0.6, 0.52, 0.42), 4: (0.34, 0.3, 0.28), 6: (0.54, 0.52, 0.54),
            7: (0.62, 0.36, 0.56), 10: (0.32, 0.28, 0.34)},   # dark grime under magenta neon
)

PLACEMENT = dict(
    new_models={"hod_nsh_hutta", "hod_nsh_palace", "hod_nsh_port"},
    items=[("hod_nsh_hutta", 0.7, ("at_vp", CAPITAL_VP)), ("hod_nsh_palace", 0.6, ("at_vp", "Palace of Grakkus the Hutt")),
           ("hod_nsh_port", 0.7, ("at_vp", "Nar Shaddaa Spaceport"))],
    clear={"hod_nsh_hutta": 3.0, "hod_nsh_palace": 2.0, "hod_nsh_port": 3.0},
)

def mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    return land, pid, np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])


def layout(m, rng):
    """feature index per pixel and features [(name, kind, state, provinces)]: FEATURES, then the streets, then each
    enclosed pocket of city as a megablock (small pockets paved into the plaza or street beside them)"""
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
    for i, (sid, pts) in enumerate(STREETS):
        feats.append((f"{DISTRICTS[sid]} street {i + 1}", "street", sid, 0))
        on = np.any([shape(("cap", *a, *b, STREET), U, V) for a, b in zip(pts, pts[1:])], 0)
        fid[sm & (fid < 0) & on] = len(feats) - 1
    pockets, n = ndi.label(sm & (fid < 0))
    taken = {}
    for j in range(1, n + 1):
        pk = pockets == j
        if pk.sum() < MIN_BLOCK:                                       # a scrap between streets: paved
            ring = ndi.binary_dilation(pk) & ~pk & (fid >= 0)
            fid[pk] = np.bincount(fid[ring]).argmax()
            continue
        u, v = U0[pk].mean(), V0[pk].mean()
        sid = min(BLOCKS, key=lambda b: math.hypot(BLOCKS[b][1][0] - u, BLOCKS[b][1][1] - v))
        assert sid not in taken, f"two pockets nearest {BLOCKS[sid][0]}: ({u:.2f}, {v:.2f}) and {taken[sid]}"
        taken[sid] = (round(float(u), 2), round(float(v), 2))
        feats.append((BLOCKS[sid][0], "blocks", sid, 0))
        fid[pk] = len(feats) - 1
    unused = sorted(set(BLOCKS) - set(taken))
    assert not unused, f"no pocket for {[BLOCKS[b][0] for b in unused]}; pockets at {sorted(taken.values())}"
    full = np.full(m.shape, -1, np.int32)
    full[sl] = fid
    return full, feats


def tidy(lab, feats, m):
    """every feature in one piece: stray bits join the neighbour with the longest shared border, preferring their own
    state, then their own kind"""
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
                kin = [k for k in np.nonzero(nb)[0] if (feats[k][2] in IMPASSABLE) == (feats[i][2] in IMPASSABLE)]
                pick = same or kin or list(np.nonzero(nb)[0])
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (nar_shaddaa_map.py)\n{imp}"
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
