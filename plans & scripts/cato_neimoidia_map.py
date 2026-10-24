"""Cato Neimoidia, the Trade Federation's purse world, as one battlefield in the Clone Wars (research:
WIPGFX/research/cato_neimoidia/). CANON: a fog-covered world; from its stormy, geyser-spouting acidic oceans rise massive
rock arches, cliffs and canyons with forests and grasslands; opulent, gilded bridge cities suspended above the ocean on
bridges anchored on the arches, home to the jeweled palaces of the Trade Federation; Zarra the capital; Tarko-se, with
the mountain Bride's Talon outside it; the Great Vaults (Lott Dod's palace) with Reya's palace next to them; the
University of Cato Neimoidia. LEGENDS: Zarra and Tarko-se the largest cities; At-la'o, location of Lott Dod's palace;
Jorra, split by a massive bridge; Nute Gunray's citadel on the western hemisphere; vast forests. Owner: TDF (as before).
LAYOUT, A DESIGN CHOICE (built like Empress Teta's street network, empress_teta_map.py): the land is cliff-walled
plateaus (passable) standing in the acid sea; the bridge cities are the links between them; every stretch of sea the
bridges enclose is an impassable state. Zarra's bridge spans the middle from Zarra Heights to At-la'o (the Great Vaults,
Reya's palace); Tarko-se's bridge runs south to Bride's Talon; Jorra's bridge east from there to the Arch Grasslands (the
Allanteen VI lane); the Fog Forests in the north-west (the Loronar lane), the University plateau north, Gunray's Redoubt
on the western rim; Bride's Talon reaches the south-western rim (the Atzerri lane).
Names from the sources: Zarra, Tarko-se, Bride's Talon, At-la'o, Great Vaults of Cato Neimoidia, Reya's palace, Jorra,
University of Cato Neimoidia, Nute Gunray's citadel. Invented: Zarra Heights, Fog Forests, Arch Grasslands, University
Plateau, Gunray's Redoubt, the smaller bridges and every sea name.
    python "WIPGFX/plans & scripts/cato_neimoidia_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/cato_neimoidia_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Cato Neimoidia"
ZONES_JSON = "WIPGFX/Assets/cato_neimoidia_zones.json"
ZONES_PNG = "WIPGFX/Assets/cato_neimoidia_zones.png"
KIND = {"bridge": 1, "palace": 2, "uni": 3, "citadel": 4, "peak": 5, "heights": 6, "street": 7, "forest": 8, "grass": 9,
        "blocks": 10}
TERRAIN = {"bridge": "urban", "palace": "urban", "uni": "urban", "citadel": "urban", "peak": "mountain", "heights": "hills",
           "street": "urban", "forest": "forest", "grass": "plains", "blocks": "mountain"}
SEED = 24
CAPITAL = 24
CAPITAL_VP = "Zarra"
CORE = "TDF"
PORT_STATE = 365                     # the Arch Grasslands, on the rim
WARP = (0.07, 9)
TARGET_PASSABLE = 118                # user rule: passable provinces outnumber impassable
STREET = 0.04                        # the lesser bridges' half-width (planet radii)
STRAIGHT = {"palace", "uni", "citadel"}
MIN_BLOCK = 45

DISTRICTS = {24: "Zarra", 359: "Tarko-se", 360: "At-la'o", 361: "Jorra", 362: "University Plateau", 363: "Gunray's Redoubt",
             364: "Fog Forests", 365: "Arch Grasslands"}
FEATURES = [   # (name, kind, state, provinces (0 = sized from TARGET_PASSABLE), shapes); the first shape on a pixel wins
    ("Great Vaults of Cato Neimoidia", "palace", 360, 1, [("rect", 0.44, -0.05, 0.06, 0.05, 15)]),
    ("Reya's Palace", "palace", 360, 1, [("rect", 0.32, 0.07, 0.04, 0.035, 15)]),
    ("University of Cato Neimoidia", "uni", 362, 1, [("rect", 0.18, -0.62, 0.06, 0.045, 10)]),
    ("Nute Gunray's Citadel", "citadel", 363, 1, [("rect", -0.8, 0.12, 0.06, 0.05, 0)]),
    ("Bride's Talon", "peak", 359, 1, [("ell", -0.46, 0.8, 0.055, 0.05, 0)]),
    ("Zarra", "bridge", 24, 3, [("cap", -0.2, -0.06, 0.28, -0.03, 0.07)]),
    ("Tarko-se", "bridge", 359, 2, [("cap", -0.36, 0.6, -0.3, 0.06, 0.055)]),
    ("Jorra", "bridge", 361, 2, [("cap", -0.24, 0.68, 0.42, 0.56, 0.055)]),
    ("Zarra Heights", "heights", 24, 0, [("ell", -0.32, -0.08, 0.188, 0.163, 20)]),
    ("At-la'o", "heights", 360, 0, [("ell", 0.41, -0.02, 0.213, 0.175, 15)]),
    ("Fog Forests", "forest", 364, 0, [("ell", -0.56, -0.6, 0.338, 0.213, -38)]),
    ("University Plateau", "heights", 362, 0, [("ell", 0.18, -0.62, 0.225, 0.163, 10)]),
    ("Gunray's Redoubt", "forest", 363, 0, [("ell", -0.8, 0.12, 0.175, 0.288, 0)]),
    ("Arch Grasslands", "grass", 365, 0, [("ell", 0.6, 0.56, 0.3, 0.2, -32)]),
    ("Vault Cliffs", "heights", 360, 0, [("ell", 0.8, -0.2, 0.15, 0.22, 10)]),
    ("Bride's Talon Plateau", "grass", 359, 0, [("ell", -0.4, 0.74, 0.213, 0.163, 30)]),
]
STREETS = [   # (state, points): the lesser bridges between the plateaus
    (362, [(0.2, -0.48), (0.38, -0.12)]), (364, [(-0.45, -0.46), (-0.34, -0.2)]), (364, [(-0.32, -0.62), (0.02, -0.62)]),
    (363, [(-0.44, -0.04), (-0.68, 0.06)]), (360, [(0.46, 0.12), (0.56, 0.42)]), (360, [(0.55, -0.06), (0.72, -0.14)]), (363, [(-0.74, 0.32), (-0.5, 0.64)]),
]
BLOCKS = {1401: ("South-Western Acid Sea", (-0.71, 0.56)), 1402: ("Western Acid Sea", (-0.7, -0.25)),
          1403: ("Redoubt Strait", (-0.51, 0.29)), 1404: ("Zarra Gulf", (-0.05, -0.34)), 1405: ("Geyser Sea", (0.05, 0.32)),
          1406: ("Southern Acid Sea", (0.07, 0.83)), 1407: ("Northern Acid Sea", (0.32, -0.64)),
          1408: ("Eastern Acid Sea", (0.78, 0.19))}
STATE_NAMES = {**DISTRICTS, **{k: v[0] for k, v in BLOCKS.items()}}
IMPASSABLE = set(BLOCKS)
OWNER = {s: "TDF" for s in STATE_NAMES}
VPS = [(24, "Zarra", CAPITAL_VP, 20), (360, "Great Vaults of Cato Neimoidia", "Great Vaults of Cato Neimoidia", 10),
       (360, "Reya's Palace", "Reya's Palace", 2), (360, "At-la'o", "At-la'o", 3), (359, "Tarko-se", "Tarko-se", 5),
       (359, "Bride's Talon", "Bride's Talon", 2), (361, "Jorra", "Jorra", 5),
       (362, "University of Cato Neimoidia", "University of Cato Neimoidia", 3),
       (363, "Nute Gunray's Citadel", "Nute Gunray's Citadel", 5), (364, "Fog Forests", "Fog Forests", 1),
       (365, "Arch Grasslands", "Arch Grasslands", 1)]

TERRAIN_CFG = dict(
    seed=24, base=4, rough=2, open=(6, 8, 9),
    zones={
        1: dict(relief=("flat", 13), tex=["URBAN", (13, ">", 0.4)]),                                  # the bridge cities
        2: dict(relief=("flat", 13), tex="URBAN"),                                                    # the palaces
        3: dict(relief=("flat", 13), tex="URBAN"),                                                    # the University
        4: dict(relief=("flat", 14), tex=["URBAN", ("ROCK", ">", 0.6)]),                              # Gunray's citadel
        5: dict(relief=("ramp_top", 24, 6, 3), tex=["ROCK", ("ROCK2", ">", 0.5)]),                    # Bride's Talon
        6: dict(relief=("rolling", 13, 2, 4), tex=["GRASSHILL", ("URBAN", ">", 0.6), (13, ">", 0.85)], props=[(31, 0.2)]),
        7: dict(relief=("flat", 12), tex=["URBAN", ("ROCK2", ">", 0.6)]),                             # the lesser bridges
        8: dict(relief=("rolling", 12, 3, 5), tex=["DFOREST", ("FOREST", ">", 0.5)], props=[(31, 0.65)]),   # fog forests
        9: dict(relief=("rolling", 11, 3, 6), tex=["GRASS", ("GRASSHILL", ">", 0.6)], props=[(32, 0.3), (31, 0.1)]),
        10: dict(relief=("flat", 0.3), tex="WATER"),     # the acid sea: its yellow-green colormap turns the water acid (pdxmap.shader)
    },
    steep=("ROCK", 4, (6, 8, 9)),
    city={1: 100, 6: 100, 7: 100},   # map/cities.txt 100: Cato's gilded towers (cat_town)
    prop_clear=1.5,
    shore_rise=(2, 1.0),
    landforms=dict(amp=0, hills=0, skirt_k=0),       # sheer cliffs out of the sea, no foothills
    colors={1: (0.86, 0.74, 0.4), 2: (0.92, 0.8, 0.42), 3: (0.84, 0.78, 0.6), 4: (0.6, 0.56, 0.5), 5: (0.56, 0.52, 0.5),
            6: (0.5, 0.62, 0.36), 7: (0.8, 0.7, 0.42), 8: (0.18, 0.4, 0.3), 9: (0.5, 0.66, 0.32), 10: (0.5, 0.78, 0.08)},   # gold over acid green
)

PLACEMENT = dict(
    new_models={"hod_cat_zarra", "hod_cat_bridge", "hod_cat_vaults", "hod_cat_university", "hod_cat_citadel", "hod_cat_talon"},
    items=[("hod_cat_zarra", 1.0, ("at_vp", CAPITAL_VP)), ("hod_cat_bridge", 0.9, ("at_vp", "Tarko-se")),
           ("hod_cat_bridge", 0.9, ("at_vp", "Jorra")), ("hod_cat_vaults", 1.0, ("at_vp", "Great Vaults of Cato Neimoidia")),
           ("hod_cat_university", 0.8, ("at_vp", "University of Cato Neimoidia")),
           ("hod_cat_citadel", 1.0, ("at_vp", "Nute Gunray's Citadel")), ("hod_cat_talon", 1.0, ("at_vp", "Bride's Talon"))],
    no_pad={"hod_cat_talon"},
    clear={"hod_cat_zarra": 5.0, "hod_cat_bridge": 4.0, "hod_cat_vaults": 4.0, "hod_cat_university": 3.0,
           "hod_cat_citadel": 4.0, "hod_cat_talon": 3.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (cato_neimoidia_map.py)\n{imp}"
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
