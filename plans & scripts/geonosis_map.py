"""Geonosis, the Separatists' foundry world, as one battlefield in the Clone Wars (research: WIPGFX/research/geonosis/).
CANON: deserts, mesas and mountains, hot and arid, spider-sponge; the spires of the Stalgasin hive (the capital); the Trippa
hive with its droid factory, the Gehenbar hive; the Im'g'twe Hills, an elevated region holding the Petranaki Arena, the
droid factories (a massive subterranean foundry beside the arena) and the Separatist command centre, next to the
Badlands of N'g'zi where the Republic routed the Separatists; the Progate Temple; Point Rain, the Republic's staging area
in the Second Battle; caltrop fields; the catacombs and Queen Karina's lair; the Korakanni Mound; the E'Y-Akh Desert.
LEGENDS: the Ebon Sea, Golbah's Pit. Owners kept: GEO, CIS (the Droid Foundry Complex).
LAYOUT IS A DESIGN CHOICE (the user, 2026-10-23: many impassable states), canon relations kept: the Stalgasin Hive Spires
west of centre; the Im'g'twe Hills east of centre with the Petranaki Arena, the Droid Foundry Complex and the Separatist
Command Centre; the Badlands of N'g'zi beyond them (the Hypori lane, the caltrop field); the Northern Badlands (the Rishi
lane); N'rakti north with the Progate Temple; the Trippa Hive north-west (the Rodia lane); the Golbah Hive west (the
Christophsis lane); the Gehenbar Hive south-west (the Ryloth lane); the N'ge'u Valley south; the E'Y-Akh Desert south-east
with Point Rain (the Tatooine lane); the Korakanni Mound; seven mesa fields, spire forests, the Ebon Sea and Golbah's Pit
impassable.
Names from the sources: every state and VP name except the mesa/spire/canyon names, which are invented.
    python "WIPGFX/plans & scripts/geonosis_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/geonosis_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Geonosis"
ZONES_JSON = "WIPGFX/Assets/geonosis_zones.json"
ZONES_PNG = "WIPGFX/Assets/geonosis_zones.png"
KIND = {"hive": 1, "arena": 2, "foundry": 3, "temple": 4, "camp": 5, "desert": 6, "badlands": 7, "hills": 8, "mesa": 9,
        "pit": 10}
TERRAIN = {"hive": "urban", "arena": "hills", "foundry": "urban", "temple": "hills", "camp": "plains", "desert": "desert",
           "badlands": "hills", "hills": "hills", "mesa": "mountain", "pit": "mountain"}
SEED = 35
CAPITAL = 35
CAPITAL_VP = "Stalgasin Hive Spires"
CORE = "GEO"
PORT_STATE = 280                     # the Badlands of N'g'zi, out to the rim
WILD_IDS = tuple(range(1533, 1540))
OWNER = {**{s: "GEO" for s in (35, *range(272, 284), *WILD_IDS)}, 273: "CIS"}
WARP = (0.1, 9)
TARGET_PASSABLE = 120                # user rule: passable provinces outnumber impassable
STRAIGHT = {"hive", "arena", "foundry", "temple", "camp"}
F = lambda name, kind, sid, *shapes: (name, kind, sid, 0, list(shapes))
FEATURES = [
    F("Stalgasin Hive Spires", "hive", CAPITAL, ("rect", -0.22, 0.0, 0.12, 0.1, 10)),
    F("Petranaki Arena", "arena", 274, ("rect", 0.24, 0.22, 0.08, 0.08, 0)),
    F("Droid Foundry Complex", "foundry", 273, ("rect", 0.3, -0.08, 0.1, 0.07, -15)),
    F("Separatist Command Centre", "foundry", 279, ("rect", 0.55, 0.12, 0.06, 0.05, 0)),
    F("Progate Temple", "temple", 283, ("rect", -0.15, -0.6, 0.07, 0.07, 0)),
    F("Point Rain", "camp", 281, ("rect", 0.42, 0.62, 0.07, 0.05, 20)),
    F("Caltrop Field", "camp", 280, ("rect", 0.72, -0.25, 0.06, 0.05, -20)),
    F("Korakanni Mound", "temple", 272, ("rect", -0.05, 0.3, 0.06, 0.06, 0)),
    F("Trippa Hive", "hive", 276, ("rect", -0.6, -0.48, 0.07, 0.06, 30)),
    F("Golbah Hive", "hive", 277, ("rect", -0.78, 0.12, 0.06, 0.07, 0)),
    F("Gehenbar Hive", "hive", 278, ("rect", -0.42, 0.66, 0.08, 0.07, -20)),
    ("Red Mesas", "mesa", 1533, 0, [("cap", -0.45, -0.25, -0.05, -0.32, 0.08)]),
    ("Spire Forest", "mesa", 1534, 0, [("cap", 0.1, -0.35, 0.45, -0.5, 0.08)]),
    ("Ebon Sea", "pit", 1535, 0, [("ell", 0.18, 0.62, 0.15, 0.1, -20)]),
    ("Golbah's Pit", "pit", 1536, 0, [("ell", -0.62, -0.1, 0.09, 0.08, 0)]),
    ("Teeth of N'g'zi", "mesa", 1537, 0, [("cap", 0.62, 0.3, 0.85, 0.12, 0.07)]),
    ("Dust Canyons", "mesa", 1538, 0, [("cap", -0.25, 0.35, -0.6, 0.38, 0.07)]),
    ("Rust Crags", "mesa", 1539, 0, [("cap", -0.3, -0.85, -0.45, -0.68, 0.07)]),
]
SEEDS = {CAPITAL: ((-0.22, 0.05), "desert"), 272: ((-0.05, 0.3), "desert"), 273: ((0.3, -0.12), "hills"),
         274: ((0.22, 0.25), "hills"), 279: ((0.55, 0.05), "hills"), 280: ((0.75, -0.3), "badlands"),
         275: ((0.35, -0.75), "badlands"), 283: ((-0.12, -0.6), "desert"), 276: ((-0.62, -0.5), "badlands"),
         277: ((-0.8, 0.12), "desert"), 278: ((-0.42, 0.7), "desert"), 282: ((0.0, 0.78), "hills"), 281: ((0.5, 0.62), "desert")}
STATE_NAMES = {CAPITAL: "Stalgasin Hive Spires", 272: "Korakanni Mound", 273: "Droid Foundry Complex", 274: "Petranaki Arena",
               275: "Northern Badlands", 276: "Trippa Hive", 277: "Golbah Hive", 278: "Gehenbar Hive", 279: "Im'g'twe Hills",
               280: "Badlands of N'g'zi", 281: "E'Y-Akh Desert", 282: "N'ge'u Valley", 283: "N'rakti",
               1533: "Red Mesas", 1534: "Spire Forest", 1535: "Ebon Sea", 1536: "Golbah's Pit", 1537: "Teeth of N'g'zi",
               1538: "Dust Canyons", 1539: "Rust Crags"}
IMPASSABLE = set(WILD_IDS)
VPS = [(CAPITAL, "Stalgasin Hive Spires", CAPITAL_VP, 15), (274, "Petranaki Arena", "Petranaki Arena", 10),
       (273, "Droid Foundry Complex", "Droid Foundry Complex", 10), (279, "Separatist Command Centre", "Separatist Command Centre", 5),
       (283, "Progate Temple", "Progate Temple", 5), (281, "Point Rain", "Point Rain", 3), (280, "Caltrop Field", "Caltrop Field", 2),
       (272, "Korakanni Mound", "Korakanni Mound", 2), (276, "Trippa Hive", "Trippa Hive", 5), (277, "Golbah Hive", "Golbah Hive", 3),
       (278, "Gehenbar Hive", "Gehenbar Hive", 5), (275, "badlands", "Northern Badlands", 1), (282, "hills", "N'ge'u Valley", 1)]

TERRAIN_CFG = dict(
    seed=35, base=4, rough=2, open=(6, 7, 8),
    zones={
        1: dict(relief=("rolling", 6, 3, 4), tex=[32, ("BROWN", ">", 0.55)], props=[(214, 0.15)]),      # hives
        2: dict(relief=("ramp_top", 12, 6, 3), tex=["BROWN", ("ROCK2", ">", 0.6)]),                   # the arena's hill
        3: dict(relief=("ramp_top", 9, 5, 3), tex=["BROWN", (32, ">", 0.5)]),                         # the foundries
        4: dict(relief=("ramp_top", 10, 5, 3), tex=["BROWN", ("ROCK2", ">", 0.6)]),                   # temple, mound
        5: dict(relief=("flat", 4), tex=["SAND", ("BROWN", ">", 0.6)], props=[(144, 0.15)]),          # Point Rain, caltrops
        6: dict(relief=("rolling", 4, 3, 6), tex=["SAND", ("DUNES", ">", 0.6), ("BROWN", ">", 0.9)],
                props=[(214, 0.06), (144, 0.04)]),                                                    # desert
        7: dict(relief=("rolling", 9, 7, 4), tex=["BROWN", ("ROCK2", ">", 0.45), ("SAND", ">", 0.9)],
                props=[(214, 0.18), (144, 0.12)]),                                                    # badlands, spires
        8: dict(relief=("rolling", 12, 6, 4), tex=["BROWN", ("BROWNMTN", ">", 0.5)], props=[(214, 0.12)]),   # the hills
        9: dict(relief=("mesa", 6, 34, 2, (4, 0.7)), tex=["BROWNMTN", ("BROWN", ">", 0.5)], props=[(214, 0.2)]),   # mesas
        10: dict(relief=("rolling", 1, 1, 3), tex=["ROCK", ("BROWNMTN", ">", 0.6)], props=[(214, 0.1)]),   # pits, Ebon Sea
    },
    city={1: 128, 3: 128},   # map/cities.txt 128: Geonosian hive mounds (gns_town)
    prop_clear=1.5,
    colors={1: (0.74, 0.44, 0.26), 2: (0.7, 0.42, 0.26), 3: (0.62, 0.4, 0.28), 4: (0.7, 0.42, 0.26), 5: (0.82, 0.58, 0.36),
            6: (0.86, 0.56, 0.32), 7: (0.72, 0.4, 0.24), 8: (0.68, 0.38, 0.24), 9: (0.56, 0.28, 0.18), 10: (0.24, 0.16, 0.14)},
)   # Geonosis orange-red

PLACEMENT = dict(
    new_models={"hod_gns_spires", "hod_gns_arena", "hod_gns_foundry", "hod_gns_temple"},
    items=[("hod_gns_spires", 1.0, ("at_vp", CAPITAL_VP)), ("hod_gns_arena", 1.0, ("at_vp", "Petranaki Arena")),
           ("hod_gns_foundry", 1.0, ("at_vp", "Droid Foundry Complex")), ("hod_gns_temple", 1.0, ("at_vp", "Progate Temple")),
           ("hod_gns_spires", 0.6, ("at_vp", "Gehenbar Hive")), ("hod_gns_spires", 0.55, ("at_vp", "Trippa Hive"))],
    clear={"hod_gns_spires": 4.0, "hod_gns_arena": 4.0, "hod_gns_foundry": 4.0, "hod_gns_temple": 3.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (geonosis_map.py)\n{imp}"
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
