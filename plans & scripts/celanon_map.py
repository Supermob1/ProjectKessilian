"""Celanon, the trade world of the Celanon Spur, as one battlefield before the Clone Wars (research:
WIPGFX/research/celanon/). LEGENDS (no canon article): temperate; forests, plains and urban sprawl; six continents,
among them Cekbar in the north-eastern hemisphere, home of the capital, and Arradi, Desetur, Holvi, Runnor and Jelldar;
Celanon City, a sprawling metropolitan complex of nearly two hundred square kilometres and a hub of Outer Rim commerce,
ruled by trade guilds; the rural areas tribal; in Celanon City the Celanon Spaceport with Spaceport Control, a tower of
nearly 140 storeys directing every ship in orbit, the Celanon Merchant Guild Medical Facility near the starport, and
Gularg's Libation Emporium, the Hutt's bar, the rowdiest and most dangerous in the area.
Owner: CIS. User (2026-10-19): landmarks Spaceport Control, the Merchant Guild hospital, Gularg's Emporium; tribal
villages on the rural continents.
LAYOUT IS A DESIGN CHOICE (the sources place only Cekbar in the north-east): the six continents ring an inner sea
(impassable) and touch at land bridges along the rim (straits run out from the sea between them); Cekbar in the
north-east holds Celanon City (its own state, the capital) and the Cekbar towns east of it; Arradi south-east, Desetur
south, Holvi south-west, Runnor west, Jelldar north.
Legends names: Celanon City, Celanon Spaceport (Spaceport Control), the Merchant Guild Medical Facility, Gularg's
Libation Emporium, Cekbar, Arradi, Desetur, Holvi, Runnor, Jelldar. Invented: the Inner Sea; which continent lies
where except Cekbar.
    python "WIPGFX/plans & scripts/celanon_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/celanon_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 68 province ids are kept (strategic region unchanged); only the pixels move.
Run order: celanon_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (cel_*) ->
planet_terrain_gen.py --planet Celanon -> military_buildings.py models hod_cel -> military_buildings.py place Celanon ->
planet_terrain_gen.py --globe-texture -> landmarks_lore.py.
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

PLANET = "Celanon"
ZONES_JSON = "WIPGFX/Assets/celanon_zones.json"
ZONES_PNG = "WIPGFX/Assets/celanon_zones.png"
KIND = {"metro": 1, "spaceport": 2, "hospital": 3, "emporium": 4, "town": 5, "plains": 6, "forest": 7, "sea": 8}
TERRAIN = {"metro": "urban", "spaceport": "urban", "hospital": "urban", "emporium": "urban", "town": "urban",
           "plains": "plains", "forest": "forest", "sea": "mountain"}
SEED = 190
CAPITAL = 190
CAPITAL_VP = "Celanon City"
PORT_STATE = 190
OWNER = {s: "CIS" for s in (190, 1021, 1022, 1023, 1024, 1025, 1026, 1210)}
WARP = (0.13, 9)
TARGET_PASSABLE = 46                 # user rule: passable provinces outnumber impassable (~46 / 22)
STRAIGHT = set()
# the straits: from the inner sea out between the continents, stopping short of the rim (the land bridges)
_STRAITS = [("cap", 0.0, 0.0, 0.76 * math.cos(math.radians(a)), 0.76 * math.sin(math.radians(a)), 0.06)
            for a in (17, 73, 124, 175, 228, 280)]
# features painted in order, the first to claim a pixel keeps it: (name, kind, state, provinces or 0 = by area,
# shapes); shapes as korriban_map.shape, u east, v south, planet radii
FEATURES = [
    ("Celanon Spaceport", "spaceport", CAPITAL, 1, [("ell", 0.62, -0.5, 0.09, 0.07, 0)]),
    ("Merchant Guild Medical Facility", "hospital", CAPITAL, 1, [("ell", 0.52, -0.66, 0.1, 0.08, 0)]),
    ("Gularg's Libation Emporium", "emporium", CAPITAL, 1, [("ell", 0.24, -0.6, 0.1, 0.08, 0)]),
    ("Celanon City", "metro", CAPITAL, 3, [("ell", 0.42, -0.45, 0.17, 0.12, -30)]),
    ("Inner Sea", "sea", 1210, 0, [("ell", 0.0, 0.0, 0.34, 0.28, 20)] + _STRAITS),
]
# open ground: each pixel to the nearest region seed (u, v), in warped space so the borders come out ragged
SEEDS = {CAPITAL: ((0.35, -0.6), "town"), 1021: ((0.75, -0.1), "town"), 1022: ((0.45, 0.55), "forest"),
         1023: ((-0.1, 0.72), "plains"), 1024: ((-0.62, 0.38), "forest"), 1025: ((-0.68, -0.25), "plains"),
         1026: ((-0.2, -0.7), "forest")}
STATE_NAMES = {CAPITAL: "Celanon City", 1021: "Cekbar", 1022: "Arradi", 1023: "Desetur", 1024: "Holvi", 1025: "Runnor",
               1026: "Jelldar", 1210: "Inner Sea"}
IMPASSABLE = {1210}
VPS = [(CAPITAL, "Celanon City", CAPITAL_VP, 10), (CAPITAL, "Celanon Spaceport", "Celanon Spaceport", 3),
       (CAPITAL, "Merchant Guild Medical Facility", "Merchant Guild Medical Facility", 1),
       (CAPITAL, "Gularg's Libation Emporium", "Gularg's Libation Emporium", 1),
       (1021, "town", "Cekbar", 2), (1022, "forest", "Arradi", 1), (1023, "plains", "Desetur", 1),
       (1024, "forest", "Holvi", 1), (1025, "plains", "Runnor", 1), (1026, "forest", "Jelldar", 1)]

# terrain (planet_terrain_gen.py --planet Celanon). Heights in heightmap steps above the base. Celanon City's sprawl
# (map/cities.txt 37) round the spaceport tower, Cekbar's towns, the tribal villages of the rural continents (38) among
# columnar forests (flora_props 138) and golden plains grass (139), the inner sea
TERRAIN_CFG = dict(
    seed=190, base=4, rough=2, open=(5, 6, 7),
    zones={  # order = random draw order: keep new zones at the end
        1: dict(relief=("ramp_top", 7, 5, 4), tex="URBAN"),                                       # Celanon City
        2: dict(relief=("flat", 5), tex="URBAN"),                                                  # the spaceport
        3: dict(relief=("flat", 6), tex="URBAN"),                                                  # the hospital
        4: dict(relief=("flat", 5), tex="URBAN"),                                                  # Gularg's
        5: dict(relief=("rolling", 5, 3, 5), tex=["URBAN", ("GRASS", ">", 0.62)], props=[(138, 0.06)]),   # towns
        6: dict(relief=("rolling", 4, 3, 6), tex=["GRASS", ("SAVANNA", ">", 0.55), (13, ">", 0.85)],
                props=[(139, 0.2), (138, 0.04)], clusters=[(7, 0.65, [(138, 0.7)])]),           # plains, villages
        7: dict(relief=("rolling", 7, 6, 5), tex=["FOREST", ("GRASSHILL", ">", 0.65), (13, ">", 0.88)],
                props=[(138, 0.55), (139, 0.05)], clusters=[(6, 0.5, [(138, 0.9)])]),           # forests, villages
        8: dict(relief=("flat", 0.3), tex="WATER"),                                                # the Inner Sea
    },
    steep=("ROCK", 6, (5, 6, 7)),
    city={1: 37, 2: 37, 3: 37, 4: 37, 5: 37, 6: 38, 7: 38},   # cities.txt 37: Celanon's city, 38: tribal villages
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.62, 0.6, 0.55), 2: (0.6, 0.6, 0.58), 3: (0.64, 0.62, 0.58), 4: (0.58, 0.52, 0.44),
            5: (0.5, 0.52, 0.4), 6: (0.58, 0.56, 0.32), 7: (0.27, 0.4, 0.22), 8: (0.15, 0.3, 0.4)},
)

# models (military_buildings.py place Celanon): big, custom (user rule 2026-10-14)
PLACEMENT = dict(
    new_models={"hod_cel_city", "hod_cel_control", "hod_cel_hospital", "hod_cel_gularg"},
    items=[("hod_cel_city", 1.0, ("at_vp", CAPITAL_VP)), ("hod_cel_control", 1.0, ("at_vp", "Celanon Spaceport")),
           ("hod_cel_hospital", 0.8, ("at_vp", "Merchant Guild Medical Facility")),
           ("hod_cel_gularg", 0.8, ("at_vp", "Gularg's Libation Emporium"))],
    clear={"hod_cel_city": 5.5, "hod_cel_control": 5.0, "hod_cel_hospital": 3.5, "hod_cel_gularg": 3.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (celanon_map.py)\n{imp}"
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
