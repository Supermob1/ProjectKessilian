"""Allanteen VI, the Republic's old naval shipyard world, as one battlefield in the Clone Wars (research:
WIPGFX/research/allanteen_vi/). CANON: a major shipyard of the Empire. LEGENDS: the Allanteen Six shipyards, among the
oldest of the Republic, where the restoration of the Republic Navy began circa 15,000 BBY; a major naval hub ever since;
in the Clone Wars a major Republic shipyard building Venator-class Star Destroyers, though inside Separatist space;
100 to 500 billion people. Owner: REP (as before).
THE USER, 2026-10-22: a shipyard city world, built like Empress Teta and Fondor (empress_teta_map.py): plazas joined by
narrow streets, every enclosed pocket an impassable megablock, ground-side yards and lift fields on the rim.
LAYOUT, A DESIGN CHOICE: the Admiralty plaza in the middle; the Venator Ground Works east of it (assembly halls round the
impassable Foundry Pit, feeding the yards); the Allanteen Six Shipyards themselves IN ORBIT south of the disc
(the user, 2026-10-22: shipyards are space stations), Venators in their slips; the Old Navy Quarter west, the Shipwrights' Quarter south; four lift fields on the rim facing
the lanes: north (Mimban), north-west (Cato Neimoidia), west (Atzerri), east (Falleen).
Names from the sources: the Allanteen Six shipyards, the Venators, the Navy's restoration, Shipwrights' Trace (a route
through the system). Invented: Allanteen Admiralty, Venator Ground Works, Foundry Pit, Shipyards Ground Command, Old Navy Quarter, Navy Restoration
Memorial, Shipwrights' Quarter, the lift fields and every megablock name.
    python "WIPGFX/plans & scripts/allanteen_vi_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/allanteen_vi_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Allanteen VI"
ZONES_JSON = "WIPGFX/Assets/allanteen_vi_zones.json"
ZONES_PNG = "WIPGFX/Assets/allanteen_vi_zones.png"
KIND = {"plaza": 1, "core": 2, "memorial": 3, "dock": 4, "port": 6, "street": 7, "works": 8, "pit": 9, "blocks": 10}
TERRAIN = {k: "urban" for k in KIND}
TERRAIN.update(pit="mountain", blocks="mountain")
SEED = 27
CAPITAL = 27
CAPITAL_VP = "Allanteen Admiralty"
CORE = "REP"
PORT_STATE = 384                     # the Eastern Lift Fields
WARP = (0.05, 9)
TARGET_PASSABLE = 116                # user rule: passable provinces outnumber impassable
STREET = 0.034                       # street half-width (planet radii)
STRAIGHT = {"memorial", "dock"}
MIN_BLOCK = 45

DISTRICTS = {27: "Allanteen Admiralty", 380: "Venator Ground Works", 381: "Northern Lift Fields", 382: "Western Lift Fields",
             383: "North-Western Lift Fields", 384: "Eastern Lift Fields", 385: "Old Navy Quarter", 386: "Shipwrights' Quarter"}
PIT = 1418
FEATURES = [   # (name, kind, state, provinces (0 = sized from TARGET_PASSABLE), shapes); the first shape on a pixel wins
    ("Navy Restoration Memorial", "memorial", 385, 1, [("ell", -0.5, 0.02, 0.055, 0.055, 0)]),
    ("Shipyards Ground Command", "dock", 380, 1, [("rect", 0.32, -0.08, 0.07, 0.05, 0)]),
    ("Foundry Pit", "pit", PIT, 0, [("rect", 0.5, 0.08, 0.2, 0.06, -25)]),
    ("Allanteen Admiralty", "core", 27, 3, [("ell", -0.06, 0.0, 0.2, 0.14, 10), ("rect", -0.06, 0.0, 0.3, 0.045, 10),
                                             ("rect", -0.06, 0.0, 0.045, 0.22, 10)]),
    ("Venator Ground Works", "works", 380, 0, [("rect", 0.48, 0.04, 0.3, 0.16, -25)]),
    ("Old Navy Quarter", "plaza", 385, 0, [("ell", -0.5, 0.02, 0.13, 0.11, 0)]),
    ("Shipwrights' Quarter", "plaza", 386, 0, [("ell", 0.08, 0.5, 0.14, 0.1, -15)]),
    ("Northern Lift Fields", "port", 381, 0, [("ell", 0.16, -0.86, 0.24, 0.13, 10)]),
    ("North-Western Lift Fields", "port", 383, 0, [("ell", -0.6, -0.68, 0.22, 0.13, 45)]),
    ("Western Lift Fields", "port", 382, 0, [("ell", -0.88, 0.1, 0.13, 0.24, 0)]),
    ("Eastern Lift Fields", "port", 384, 0, [("ell", 0.84, 0.38, 0.22, 0.14, 25)]),
]
STREETS = [   # (state, points): narrow streets, bends at the inner points; dead ends are alleys
    (27, [(-0.06, 0.0), (0.32, -0.08)]), (27, [(-0.06, 0.0), (-0.5, 0.02)]), (27, [(-0.06, 0.0), (0.08, 0.5)]),
    (27, [(-0.06, 0.0), (0.04, -0.45), (0.16, -0.8)]), (385, [(-0.5, 0.02), (-0.84, 0.08)]),
    (385, [(-0.5, 0.02), (-0.55, -0.35), (-0.6, -0.62)]), (383, [(-0.6, -0.68), (-0.15, -0.6), (0.1, -0.78)]),
    (380, [(0.32, -0.08), (0.45, -0.5), (0.25, -0.8)]), (380, [(0.62, 0.15), (0.8, 0.34)]),
    (386, [(0.08, 0.5), (0.7, 0.42)]), (386, [(0.08, 0.5), (-0.4, 0.55), (-0.8, 0.2)]), (386, [(0.08, 0.5), (0.0, 0.85)]),
    (385, [(-0.5, 0.02), (-0.3, 0.3)]), (27, [(-0.06, 0.0), (0.2, 0.22)]),
]
BLOCKS = {1419: ("Western Hab Blocks", (-0.75, -0.28)), 1420: ("Navy Barracks", (-0.36, 0.28)),
          1421: ("Northern Rim Blocks", (-0.25, -0.83)), 1422: ("Admiralty Towers", (-0.24, -0.39)),
          1423: ("Southern Hab Blocks", (-0.06, 0.69)), 1424: ("Fleet Depots", (0.19, -0.36)),
          1425: ("Hull Foundries", (0.33, 0.3)), 1426: ("Eastern Foundries", (0.68, -0.35))}
STATE_NAMES = {**DISTRICTS, PIT: "Foundry Pit", **{k: v[0] for k, v in BLOCKS.items()}}
IMPASSABLE = {PIT, *BLOCKS}
OWNER = {s: "REP" for s in STATE_NAMES}
VPS = [(27, "Allanteen Admiralty", CAPITAL_VP, 20), (380, "Shipyards Ground Command", "Shipyards Ground Command", 10),
       (380, "Venator Ground Works", "Venator Ground Works", 3), (385, "Navy Restoration Memorial", "Navy Restoration Memorial", 3),
       (386, "Shipwrights' Quarter", "Shipwrights' Quarter", 2), (384, "Eastern Lift Fields", "Eastern Lift Fields", 3),
       (381, "Northern Lift Fields", "Northern Lift Fields", 2), (382, "Western Lift Fields", "Western Lift Fields", 2),
       (383, "North-Western Lift Fields", "North-Western Lift Fields", 2)]

TERRAIN_CFG = dict(
    seed=27, base=4, rough=1, open=(1, 6, 7),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.8)]),                              # plazas
        2: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.8)]),                              # the Admiralty
        3: dict(relief=("flat", 6), tex="URBAN"),                                                     # the memorial
        4: dict(relief=("flat", 5), tex="URBAN"),                                                     # the shipyard offices
        6: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.6)]),                              # lift fields
        7: dict(relief=("flat", 5), tex=["URBAN", (13, ">", 0.55)]),                                  # streets
        8: dict(relief=("flat", 4), tex=["URBAN", ("ROCK2", ">", 0.5)]),                              # the drydock works
        9: dict(relief=("flat", 0.5), tex=["ROCK2", ("URBAN", ">", 0.5)]),                            # the Venator Slip
        10: dict(relief=("rolling", 11, 3, 3), tex=["URBAN", (13, ">", 0.1)]),                        # megablocks
    },
    city={1: 103, 7: 103, 8: 103, 10: 103},   # map/cities.txt 103: Allanteen's Republic grey blocks (aln_town)
    prop_clear=1.5,
    lights=dict(zones=(1, 2, 6, 7, 8), rgb=(1.0, 0.92, 0.8), density=0.22, mix=0.85),
    colors={1: (0.78, 0.78, 0.8), 2: (0.84, 0.82, 0.82), 3: (0.8, 0.76, 0.74), 4: (0.74, 0.74, 0.78), 6: (0.76, 0.78, 0.8),
            7: (0.7, 0.7, 0.74), 8: (0.62, 0.62, 0.68), 9: (0.36, 0.38, 0.46), 10: (0.52, 0.5, 0.56)},   # Republic grey
    tint={10: ((0.62, 0.22, 0.2), 0.15)},                                                             # a touch of Republic red
)


def orbit(ctx):
    """the Allanteen Six Shipyards IN ORBIT (the user, 2026-10-22: shipyards are space stations): the slips beside the disc,
    south of it, clear of the four lanes"""
    (cy, cx), R = ctx["z"]["centre"], ctx["z"]["radius"]
    ctx["put"]("hod_aln_yards", 1.0, cy + 1.95 * R, cx)


PLACEMENT = dict(
    new_models={"hod_aln_admiralty", "hod_aln_works", "hod_aln_memorial", "hod_aln_lift", "hod_aln_yards"},
    items=[("hod_aln_admiralty", 1.0, ("at_vp", CAPITAL_VP)), ("hod_aln_works", 1.0, ("at_vp", "Venator Ground Works")),
           ("hod_aln_memorial", 0.8, ("at_vp", "Navy Restoration Memorial")),
           ("hod_aln_lift", 1.0, ("at_vp", "Eastern Lift Fields")), ("hod_aln_lift", 0.8, ("at_vp", "Northern Lift Fields")),
           ("hod_aln_lift", 0.8, ("at_vp", "Western Lift Fields")), ("hod_aln_lift", 0.8, ("at_vp", "North-Western Lift Fields"))],
    clear={"hod_aln_admiralty": 5.0, "hod_aln_works": 6.0, "hod_aln_memorial": 2.5, "hod_aln_lift": 4.5},
    hook=orbit,
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (allanteen_vi_map.py)\n{imp}"
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
