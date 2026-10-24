"""Lianna, Sienar's corporate world in the Tion Cluster, as one battlefield before the Clone Wars (research:
WIPGFX/research/lianna/). LEGENDS (canon says almost nothing): temperate and dry, urban and plains; two continents,
Anai (the larger) and Landra (the smaller); Lianna City the capital with the Santhe/Sienar Technologies Corporate
Headquarters; Sesswe south of the capital and Portharton west of it, both on Anai; Anxarta and Melford on Anai's
northern coast, the Melford Star Academy; Northwest, a city and spaceport on Landra; Sky City, Lola Curich, Lianna
Metro; Sienar's plants (Santheship 23, Plutrefin 734, Lasarcompfac 5); the Class IB Lianna shipyards; ruled by the
Santhe family (Valles Santhe), independent, siding with the Republic in the Clone Wars. Owner: Sienar (SIE).
User (2026-10-16): a passable shallow strait between the continents (the water tile, animated by
gfx/FX/pdxmap.shader); the shipyards' ships are pre-Clone Wars Sienar designs (no TIEs), the yard in orbit.
LAYOUT IS A DESIGN CHOICE except the stated relations above: Anai over the west and centre, Landra east across the
strait, the ocean over the north rim (impassable), Landra's heights inland, Sky City floating over the strait (the
cover of "Mission to Lianna" is McQuarrie's Bespin painting), the Sienar works in Anai's south-west.
User (2026-10-16): the cities a megalopolis: the capital state is one sprawl (Lianna Metro), the other cities
large, dense and tall.
Legends names: every city and site above. Invented: every state name, the Shaltin Strait (the Shaltin Tunnels are a
hyperlane), the Northern Ocean, the Landra Heights.
    python "WIPGFX/plans & scripts/lianna_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/lianna_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 54 province ids are kept (strategic region unchanged); only the pixels move.
Run order: lianna_map.py -> flora_props.py (lia_*) -> planet_terrain_gen.py --planet Lianna -> military_buildings.py
models hod_lia -> military_buildings.py place Lianna -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Lianna"
ZONES_JSON = "WIPGFX/Assets/lianna_zones.json"
ZONES_PNG = "WIPGFX/Assets/lianna_zones.png"
KIND = {"plains": 1, "steppe": 2, "city": 3, "works": 4, "strait": 5, "ocean": 6, "heights": 7, "skycity": 8, "metro": 9}
TERRAIN = {"plains": "plains", "steppe": "plains", "city": "urban", "works": "urban", "strait": "marsh",
           "ocean": "mountain", "heights": "mountain", "skycity": "urban",
           "metro": "urban"}
SEED = 195
CAPITAL = 195
CAPITAL_VP = "Lianna City"
PORT_STATE = 1049
OWNER = {s: "SIE" for s in (195, 1046, 1047, 1048, 1049, 1050, 1051, 1197, 1198)}
WARP = (0.12, 6)                     # ragged edges: warp amplitude (planet radii) and noise cell (px): a small planet
TARGET_PASSABLE = 36                 # user rule: passable provinces outnumber impassable (~36 / 18)
STRAIGHT = set()
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Lianna City", "city", CAPITAL, 3, [("ell", -0.12, 0.0, 0.3, 0.24, 15)]),
    ("Sienar Headquarters", "city", CAPITAL, 1, [("ell", 0.1, 0.1, 0.08, 0.07, 0)]),
    ("Sesswe", "city", 1046, 1, [("ell", -0.08, 0.62, 0.17, 0.12, 0)]),
    ("Portharton", "city", 1047, 1, [("ell", -0.68, 0.08, 0.16, 0.15, 0)]),
    ("Anxarta", "city", 1048, 1, [("ell", -0.45, -0.55, 0.14, 0.1, 0)]),
    ("Melford", "city", 1048, 1, [("ell", -0.1, -0.6, 0.13, 0.1, 0)]),
    ("Melford Star Academy", "city", 1048, 1, [("ell", 0.12, -0.52, 0.08, 0.07, 0)]),
    ("Santheship 23", "works", 1050, 2, [("ell", -0.52, 0.5, 0.14, 0.1, -30)]),
    ("Lola Curich", "city", 1050, 1, [("ell", -0.3, 0.74, 0.12, 0.1, 0)]),
    ("Northwest", "city", PORT_STATE, 1, [("ell", 0.68, -0.38, 0.15, 0.13, 0)]),
    ("Sky City", "skycity", 1051, 1, [("ell", 0.42, 0.3, 0.08, 0.08, 0)]),
    # the strait between Anai and Landra: from the northern ocean down to the south rim
    ("Shaltin Strait", "strait", 1051, 0, [("cap", 0.4, -0.75, 0.36, 0.05, 0.1), ("cap", 0.36, 0.05, 0.48, 0.9, 0.09)]),
    # the northern ocean over Anai's coast; Landra's heights inland
    ("Northern Ocean", "ocean", 1197, 0, [("ell", -0.15, -0.98, 0.75, 0.24, 0), ("cap", -0.7, -0.78, -0.55, -0.7, 0.07)]),
    ("Landra Heights", "heights", 1198, 0, [("ell", 0.82, 0.12, 0.13, 0.26, 10), ("cap", 0.75, 0.3, 0.62, 0.5, 0.06)]),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((-0.1, 0.0), "metro"),   # Lianna Metro (Legends): the capital state is one urban sprawl
          1046: ((-0.05, 0.65), "steppe"), 1047: ((-0.72, 0.05), "steppe"),
         1048: ((-0.2, -0.5), "plains"), 1049: ((0.72, -0.15), "plains"), 1050: ((-0.5, 0.55), "steppe")}
STATE_NAMES = {CAPITAL: "Lianna City", 1046: "Sesswe Plains", 1047: "Portharton Reaches", 1048: "Anai North Coast",
               1049: "Landra", 1050: "Sienar Works", 1051: "Shaltin Strait", 1197: "Northern Ocean",
               1198: "Landra Heights"}
IMPASSABLE = {1197, 1198}
# victory points: (state, feature or kind, name, value); all Legends
VPS = [(CAPITAL, "Lianna City", CAPITAL_VP, 10), (CAPITAL, "Sienar Headquarters", "Santhe/Sienar Headquarters", 3),
       (1046, "Sesswe", "Sesswe", 3), (1047, "Portharton", "Portharton", 3), (1048, "Anxarta", "Anxarta", 2),
       (1048, "Melford", "Melford", 2), (1048, "Melford Star Academy", "Melford Star Academy", 3),
       (1050, "Santheship 23", "Santheship 23", 3), (1050, "Lola Curich", "Lola Curich", 2),
       (PORT_STATE, "Northwest", "Northwest", 3), (1051, "Sky City", "Sky City", 2)]

# terrain (planet_terrain_gen.py --planet Lianna). Heights in heightmap steps above the base. Legends look: temperate
# and dry, urban and plains: dry grass and farmland, lone trees, sprawling corporate cities; the sea is the water
# tile (slot 6) the terrain shader animates, and every shore rises out of it (shore_rise)
TERRAIN_CFG = dict(
    seed=195, base=4, rough=2, open=(1, 2),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("rolling", 4, 3, 5), tex=["SAVANNA", ("FARM", ">", 0.58), ("GRASS", "<", 0.2)],
                props=[(122, 0.06), (123, 0.12)], clusters=[(7, 0.62, [(122, 0.35)])]),          # plains and farms
        2: dict(relief=("rolling", 4, 4, 4), tex=["SAVANNA", ("SAND", ">", 0.62), ("BROWN", "<", 0.15)],
                props=[(123, 0.16), (122, 0.03)]),                                               # dry steppe
        3: dict(relief=("ramp_top", 6, 4, 4), tex="URBAN"),                                      # the cities
        4: dict(relief=("flat", 4), tex="URBAN", props=[(124, 0.12)]),                           # Sienar's plants
        5: dict(relief=("flat", 0.3), tex="WATER"),                                              # the strait
        6: dict(relief=("flat", 0.3), tex="WATER"),                                              # the northern ocean
        7: dict(relief=("rolling", 14, 10, 4), tex=["GRASSHILL", ("ROCK2", ">", 0.55)], props=[(122, 0.08)]),
        8: dict(relief=("flat", 0.3), tex="WATER"),                                              # under Sky City
        9: dict(relief=("rolling", 4, 1.5, 6), tex="URBAN", props=[(124, 0.04)]),               # Lianna Metro sprawl
    },
    steep=("ROCK2", 6, (1, 2, 7)),
    city={3: 32, 4: 32, 9: 32},   # map/cities.txt 32: Lianna's megalopolis (military_buildings.py lia_city)
    prop_clear=1.5,
    landforms=dict(amp=0, hills=0, skirt_k=0),
    shore_rise=(6, 2.0),   # the coasts stand up out of the strait and the ocean
)


def orbit(ctx):
    """the Lianna shipyards in space (user, 2026-10-16): the hub military_buildings.LIA_YARD_AT (distance, bearing)
    from the planet's centre, in the open space east of the disc"""
    import military_buildings as mb
    (cy, cx), (r, b) = ctx["z"]["centre"], (mb.LIA_YARD_AT[0], math.radians(mb.LIA_YARD_AT[1]))
    ctx["put"]("hod_lia_shipyard", 1.0, cy - r * math.sin(b), cx + r * math.cos(b))


# models (military_buildings.py place Lianna): big, custom (user rule 2026-10-14); the shipyards float in orbit
PLACEMENT = dict(
    new_models={"hod_lia_hq", "hod_lia_academy", "hod_lia_skycity", "hod_lia_shipyard"},
    items=[("hod_lia_hq", 1.0, ("at_vp", "Santhe/Sienar Headquarters")),
           ("hod_lia_academy", 1.0, ("at_vp", "Melford Star Academy")), ("hod_lia_skycity", 1.0, ("at_vp", "Sky City"))],
    clear={"hod_lia_hq": 6.0, "hod_lia_academy": 6.0, "hod_lia_skycity": 5.0},
    hook=orbit,
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (lianna_map.py)\n{imp}"
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
