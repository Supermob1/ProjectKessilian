"""Rendilli (Wookieepedia: Rendili), Rendili StarDrive's homeworld, as one battlefield before the Clone Wars (research:
WIPGFX/research/rendili/; the user, 2026-10-21: the StarDrive homeworld). LEGENDS: home of Rendili StarDrive, the
builders of the Dreadnaught heavy cruisers; the Battle of Rendili (22 BBY), when the Rendili Home Defense Fleet was meant
to defect to the Separatists and the Republic stopped it. The sources say nothing about the surface: everything below is
a design choice, and nearly every name is invented. Owner: REN (as before).
LAYOUT IS A DESIGN CHOICE: a temperate Core world; Rendili Prime in the middle with Rendili City and the headquarters of
Rendili StarDrive, the Home Fleet Base on the eastern coast (the Commenor lane), the Drive Works north-east where the
Dreadnaughts' engines are test-fired (the Kuat lane), the Southern Coast (the Corellia lane), the farmlands of the
Rendili Plains west, the Rendili Highlands south-west, the Northern Tundra under the Polar Ice (impassable); the Rendili
Mountains (impassable) between the highlands and the capital, the Western Sea (impassable) off the west; the Rendili
yards in orbit beside the disc.
Names from the sources: Rendili StarDrive, the Home Defense Fleet. Invented: every state and VP name.
    python "WIPGFX/plans & scripts/rendilli_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/rendilli_map.py" --dry OUT.png      layout + every check, writes only OUT.png
All 63 province ids are kept (strategic region unchanged); only the pixels move.
Run order: rendilli_map.py -> fix_small_provinces / fix_building_positions / fix_ports -> flora_props.py (ren_*) ->
planet_terrain_gen.py --planet Rendilli -> military_buildings.py rendilli_atlas, models hod_ren_ -> coruscant_buildings.py
wire -> military_buildings.py place Rendilli -> planet_terrain_gen.py --globe-texture -> landmarks_lore.py -> gen_hyperlanes.py
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

PLANET = "Rendilli"
ZONES_JSON = "WIPGFX/Assets/rendilli_zones.json"
ZONES_PNG = "WIPGFX/Assets/rendilli_zones.png"
KIND = {"city": 1, "hq": 2, "base": 3, "works": 4, "plains": 5, "forest": 6, "hills": 7, "coast": 8, "tundra": 9,
        "sea": 10, "mountains": 11, "ice": 12}
TERRAIN = {"city": "urban", "hq": "urban", "base": "urban", "works": "urban", "plains": "plains", "forest": "forest",
           "hills": "hills", "coast": "plains", "tundra": "plains", "sea": "mountain", "mountains": "mountain", "ice": "mountain"}
SEED = 23
CAPITAL = 23
CAPITAL_VP = "Rendili City"
CORE = "REN"
PORT_STATE = 353                     # the Home Fleet Base
OWNER = {s: "REN" for s in (23, 353, 354, 355, 356, 357, 358, 1348, 1349, 1350)}
WARP = (0.12, 9)
TARGET_PASSABLE = 41                 # user rule: passable provinces outnumber impassable (~41 / 22)
STRAIGHT = {"hq", "base", "works"}
FEATURES = [
    ("Rendili City", "city", CAPITAL, 2, [("ell", 0.0, -0.05, 0.18, 0.13, 10)]),
    ("Rendili StarDrive Headquarters", "hq", CAPITAL, 1, [("rect", 0.2, 0.08, 0.08, 0.07, 0)]),
    ("Home Fleet Base", "base", 353, 1, [("rect", 0.72, 0.02, 0.12, 0.1, 0)]),
    ("Drive Works", "works", 355, 1, [("rect", 0.45, -0.55, 0.12, 0.09, -20)]),
    ("Rendili Mountains", "mountains", 1348, 0, [("cap", -0.6, 0.12, -0.15, 0.32, 0.14), ("cap", -0.15, 0.32, 0.12, 0.58, 0.11)]),
    ("Western Sea", "sea", 1349, 0, [("cap", -0.98, -0.25, -0.75, 0.1, 0.13), ("cap", -0.75, 0.1, -0.82, 0.45, 0.1)]),
    ("Polar Ice", "ice", 1350, 0, [("ell", -0.15, -0.97, 0.6, 0.17, 5), ("cap", -0.55, -0.75, -0.75, -0.6, 0.08)]),
]
SEEDS = {CAPITAL: ((0.0, -0.05), "plains"), 353: ((0.75, 0.0), "coast"), 354: ((-0.5, -0.25), "plains"),
         355: ((0.45, -0.55), "forest"), 356: ((0.3, 0.7), "coast"), 357: ((-0.4, 0.6), "hills"), 358: ((-0.1, -0.65), "tundra")}
STATE_NAMES = {CAPITAL: "Rendili Prime", 353: "Home Fleet Base", 354: "Rendili Plains", 355: "Drive Works",
               356: "Southern Coast", 357: "Rendili Highlands", 358: "Northern Tundra", 1348: "Rendili Mountains",
               1349: "Western Sea", 1350: "Polar Ice"}
IMPASSABLE = {1348, 1349, 1350}
VPS = [(CAPITAL, "Rendili City", CAPITAL_VP, 10), (CAPITAL, "Rendili StarDrive Headquarters", "Rendili StarDrive Headquarters", 5),
       (353, "Home Fleet Base", "Home Fleet Base", 5), (355, "Drive Works", "Drive Works", 3),
       (354, "plains", "Rendili Plains", 1), (356, "coast", "Southern Coast", 2), (357, "hills", "Rendili Highlands", 1),
       (358, "tundra", "Northern Tundra", 1)]

TERRAIN_CFG = dict(
    seed=23, base=4, rough=2, open=(5, 6, 7, 8, 9),
    zones={
        1: dict(relief=("flat", 5), tex=["URBAN", ("GRASS", ">", 0.6)]),                              # Rendili City
        2: dict(relief=("flat", 5), tex=["URBAN", ("ROCK2", ">", 0.6)]),                              # the headquarters
        3: dict(relief=("flat", 4), tex=["URBAN", ("ROCK2", ">", 0.5)]),                              # the fleet base
        4: dict(relief=("flat", 4), tex=["URBAN", ("BROWN", ">", 0.5)]),                              # the drive works
        5: dict(relief=("rolling", 4, 3, 7), tex=["GRASS", ("FARM", ">", 0.55), (13, ">", 0.94)], props=[(245, 0.3), (244, 0.1)]),
        6: dict(relief=("rolling", 6, 4, 6), tex=["FOREST", ("DFOREST", ">", 0.5)], props=[(244, 0.65)]),
        7: dict(relief=("rolling", 10, 7, 5), tex=["GRASSHILL", ("ROCK2", ">", 0.6), (13, ">", 0.95)], props=[(244, 0.3)]),
        8: dict(relief=("rolling", 3, 2, 8), tex=["GRASS", ("SAVANNA", ">", 0.6), (13, ">", 0.94)], props=[(245, 0.2)]),
        9: dict(relief=("rolling", 5, 3, 7), tex=["SNOWSAND", ("SNOWFARM", ">", 0.5)], props=[(244, 0.08)]),
        10: dict(relief=("flat", 0.3), tex="WATER"),
        11: dict(relief=("spires", 18, 10, 0.12, (1.5, 3.0), (25, 50)), tex=["ROCK", ("GREENMTN", ">", 0.5), ("SNOWROCK", ">", 0.9)]),
        12: dict(relief=("spires", 14, 8, 0.08, (1.5, 3.0), (20, 40)), tex=["SNOWROCK", ("SNOWSAND", ">", 0.5)]),
    },
    steep=("ROCK", 6, (5, 6, 7, 8, 9)),
    city={1: 89, 2: 89, 3: 89, 4: 89, 5: 89, 8: 89},   # map/cities.txt 89: Rendili's towns (ren_town)
    prop_clear=1.5,
    shore_rise=(4, 2.0),
    colors={1: (0.539, 0.55, 0.609), 2: (0.559, 0.57, 0.63), 3: (0.5, 0.511, 0.567), 4: (0.525, 0.432, 0.504), 5: (0.177, 0.567, 0.36), 6: (0.128, 0.42, 0.345), 7: (0.216, 0.483, 0.323), 8: (0.236, 0.567, 0.391), 9: (0.72, 0.74, 0.72), 10: (0.1, 0.25, 0.5), 11: (0.392, 0.483, 0.435), 12: (0.86, 0.88, 0.92)},   # signature far look (recolor.py, the user 2026-10-21: colourful planets)
)


def orbit(ctx):
    """the Rendili yards (design choice: where StarDrive's Dreadnaughts are built), beside the disc"""
    (cy, cx), R = ctx["z"]["centre"], ctx["z"]["radius"]
    ctx["put"]("hod_ren_yards", 1.0, cy + 0.2 * R, cx + R + 0.95 * R)


PLACEMENT = dict(
    new_models={"hod_ren_city", "hod_ren_hq", "hod_ren_base", "hod_ren_works", "hod_ren_yards"},
    items=[("hod_ren_city", 1.0, ("at_vp", "Rendili City")), ("hod_ren_hq", 0.9, ("at_vp", "Rendili StarDrive Headquarters")),
           ("hod_ren_base", 1.0, ("at_vp", "Home Fleet Base")), ("hod_ren_works", 0.9, ("at_vp", "Drive Works"))],
    clear={"hod_ren_city": 5.5, "hod_ren_hq": 3.0, "hod_ren_base": 4.5, "hod_ren_works": 4.0},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (rendilli_map.py)\n{imp}"
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
