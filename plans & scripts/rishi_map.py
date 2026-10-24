"""Rishi, a tropical island world, as one battlefield in the Clone Wars (research: WIPGFX/research/rishi/). CANON: the
Republic's world (its moon held the Rishi Station of the Defense of Rishi Station, 22 BBY). LEGENDS: mountains, swamps,
islands and jungle, tropical; Raider's Cove, a beach town and trade port on Horizon Island; Sky Ridge Island, mountainous,
north of Horizon Island, home to a village of the native Rishii; Razorback Island; Tracyn Island; Ruugaria (later
Coratanni Town). Owners kept from the old map: REP (most), BKJ (the smugglers' base), CIS (the hidden Separatist base).
LAYOUT IS A DESIGN CHOICE (the user, 2026-10-23: an archipelago, the sea as many impassable states): Horizon Island in the
middle (Raider's Cove, the Human Colonies, the Smugglers' Base on its south shore); Sky Ridge Island north (the Rishii
Ancestral Territories, the Hidden Separatist Base in its western mountains); Ruugaria north-east (the Kamino lane);
Razorback Island east with the Kuati Exonium Mines; Tracyn Island south-west with the Corporate Exonium Mines (the Geonosis
lane); the Republic Listening Post on the southern island (the Hypori lane) with the Twi'lek Colonies west of Horizon;
narrow shallows join the islands; six seas between them impassable.
Names from the sources: Horizon Island, Raider's Cove, Sky Ridge Island, Razorback Island, Tracyn Island, Ruugaria.
Kept from the old map: the colonies, the bases, the exonium mines, the listening post. Invented: the sea names.
    python "WIPGFX/plans & scripts/rishi_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/rishi_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Rishi"
ZONES_JSON = "WIPGFX/Assets/rishi_zones.json"
ZONES_PNG = "WIPGFX/Assets/rishi_zones.png"
KIND = {"town": 1, "base": 2, "mine": 3, "post": 4, "jungle": 5, "beach": 6, "mountain": 7, "sea": 8}
TERRAIN = {"town": "urban", "base": "jungle", "mine": "hills", "post": "hills", "jungle": "jungle", "beach": "plains",
           "mountain": "mountain", "sea": "mountain"}
SEED = 33
CAPITAL = 33
CAPITAL_VP = "Raider's Cove"
CORE = "REP"
PORT_STATE = 263                     # the Republic Listening Post's island, out to the rim
SEA_IDS = tuple(range(1521, 1527))
OWNER = {**{s: "REP" for s in (33, 262, 263, 264, 265, 266, 267, 269, 270, 271)}, 261: "BKJ", 268: "CIS",
         **{s: "REP" for s in SEA_IDS}}
WARP = (0.09, 9)
TARGET_PASSABLE = 112                # user rule: passable provinces outnumber impassable
STRAIGHT = {"town", "base", "mine", "post"}
F = lambda name, kind, sid, *shapes: (name, kind, sid, 0, list(shapes))
FEATURES = [
    F("Raider's Cove", "town", 33, ("rect", -0.2, 0.12, 0.07, 0.05, 10)),
    F("Smugglers' Base", "base", 261, ("rect", 0.02, 0.32, 0.06, 0.04, 0)),
    F("Hidden Separatist Base", "base", 268, ("rect", -0.28, -0.68, 0.06, 0.05, 0)),
    F("Kuati Exonium Mines", "mine", 271, ("rect", 0.74, 0.55, 0.06, 0.05, 0)),
    F("Corporate Exonium Mines", "mine", 262, ("rect", -0.44, 0.74, 0.06, 0.05, 0)),
    F("Republic Listening Post", "post", 263, ("rect", 0.12, 0.76, 0.06, 0.05, 0)),
    # the islands
    F("Horizon Island", "jungle", 33, ("ell", -0.18, 0.04, 0.24, 0.2, 15)),
    F("Horizon East", "jungle", 269, ("ell", 0.22, -0.02, 0.21, 0.18, -10)),
    F("Horizon Shore", "beach", 261, ("ell", 0.02, 0.28, 0.2, 0.1, 0)),
    F("Sky Ridge Island", "mountain", 266, ("ell", 0.12, -0.64, 0.2, 0.13, 10)),
    F("Sky Ridge Peaks", "mountain", 268, ("ell", -0.24, -0.66, 0.16, 0.13, -15)),
    F("Ruugaria", "jungle", 270, ("ell", 0.6, -0.42, 0.17, 0.15, 30), ("cap", 0.6, -0.42, 0.5, -0.88, 0.08)),
    F("Razorback Island", "mountain", 264, ("ell", 0.76, 0.18, 0.11, 0.21, -20)),
    F("Kuati Shore", "beach", 271, ("ell", 0.72, 0.55, 0.13, 0.1, 0)),
    F("Tracyn Island", "jungle", 265, ("ell", -0.58, 0.4, 0.17, 0.14, 20)),
    F("Corporate Shore", "beach", 262, ("ell", -0.44, 0.72, 0.14, 0.1, -10), ("cap", -0.44, 0.72, -0.38, 0.95, 0.07)),
    F("Southern Island", "jungle", 263, ("ell", 0.12, 0.74, 0.15, 0.11, 0), ("cap", 0.12, 0.74, 0.08, 0.98, 0.07)),
    F("Twi'lek Colonies", "jungle", 267, ("ell", -0.72, -0.2, 0.16, 0.19, 0)),
    # the shallows joining them
    F("Sky Ridge Shallows", "beach", 266, ("cap", 0.02, -0.12, 0.06, -0.52, 0.045)),
    F("Ruugaria Shallows", "beach", 270, ("cap", 0.3, -0.6, 0.48, -0.45, 0.045)),
    F("Razorback Shallows", "beach", 264, ("cap", 0.4, 0.04, 0.68, 0.14, 0.045)),
    F("Kuati Shallows", "beach", 271, ("cap", 0.75, 0.38, 0.73, 0.48, 0.045)),
    F("Southern Shallows", "beach", 263, ("cap", 0.08, 0.36, 0.12, 0.64, 0.045)),
    F("Tracyn Shallows", "beach", 265, ("cap", -0.36, 0.14, -0.5, 0.3, 0.045)),
    F("Corporate Shallows", "beach", 262, ("cap", -0.55, 0.52, -0.46, 0.64, 0.045)),
    F("Twi'lek Shallows", "beach", 267, ("cap", -0.38, -0.02, -0.6, -0.14, 0.045)),
]
SEEDS = {1521: ((-0.42, -0.42), "sea"), 1522: ((0.45, -0.2), "sea"), 1523: ((0.42, 0.45), "sea"),
         1524: ((-0.3, 0.45), "sea"), 1525: ((0.0, -0.9), "sea"), 1526: ((-0.15, 0.95), "sea")}
STATE_NAMES = {CAPITAL: "Horizon Island", 261: "Smugglers' Base", 262: "Corporate Exonium Mines", 263: "Republic Listening Post",
               264: "Razorback Island", 265: "Tracyn Island", 266: "Sky Ridge Island", 267: "Twi'lek Colonies",
               268: "Hidden Separatist Base", 269: "Human Colonies", 270: "Ruugaria", 271: "Kuati Exonium Mines",
               1521: "Sky Ridge Strait", 1522: "Cove Waters", 1523: "Razorback Channel", 1524: "Tracyn Sound",
               1525: "Northern Ocean", 1526: "Southern Ocean"}
IMPASSABLE = set(SEA_IDS)
VPS = [(CAPITAL, "Raider's Cove", CAPITAL_VP, 15), (261, "Smugglers' Base", "Smugglers' Base", 5),
       (268, "Hidden Separatist Base", "Hidden Separatist Base", 5), (263, "Republic Listening Post", "Republic Listening Post", 5),
       (271, "Kuati Exonium Mines", "Kuati Exonium Mines", 3), (262, "Corporate Exonium Mines", "Corporate Exonium Mines", 3),
       (266, "Sky Ridge Island", "Sky Ridge Island", 3), (270, "Ruugaria", "Ruugaria", 5), (264, "Razorback Island", "Razorback Island", 2),
       (265, "Tracyn Island", "Tracyn Island", 2), (267, "Twi'lek Colonies", "Twi'lek Colonies", 2),
       (269, "Horizon East", "Human Colonies", 2)]

TERRAIN_CFG = dict(
    seed=33, base=4, rough=2, open=(5, 6, 7),
    zones={
        1: dict(relief=("flat", 4), tex=[30, ("URBAN", ">", 0.6)]),                                   # Raider's Cove
        2: dict(relief=("flat", 5), tex=["JUNGLE2", ("URBAN", ">", 0.5)]),                            # the bases
        3: dict(relief=("flat", 5), tex=["ROCK2", ("URBAN", ">", 0.55)], props=[(141, 0.15)]),        # exonium mines
        4: dict(relief=("ramp_top", 9, 5, 3), tex=["ROCK2", ("URBAN", ">", 0.6)]),                    # the listening post
        5: dict(relief=("rolling", 6, 4, 5), tex=["JUNGLE", ("JUNGLE2", ">", 0.45), (26, ">", 0.96)],
                props=[(161, 0.3), (201, 0.35), (162, 0.15)]),                                        # island jungle
        6: dict(relief=("rolling", 2, 1, 6), tex=["SAND", ("GRASS", ">", 0.6), (26, ">", 0.97)],
                props=[(161, 0.25)]),                                                                 # beaches, shallows
        7: dict(relief=("rolling", 22, 12, 3), tex=["GREENMTN", ("JUNGLE", ">", 0.6), ("ROCK", ">", 0.85)],
                props=[(201, 0.3)]),                                                                  # island mountains
        8: dict(relief=("flat", 0.3), tex="WATER"),                                                   # the sea
    },
    city={1: 127, 5: 127, 6: 127},   # map/cities.txt 127: Rishi island towns (ris_town)
    prop_clear=1.5,
    shore_rise=(3, 2.0),
    colors={1: (0.74, 0.68, 0.52), 2: (0.36, 0.52, 0.3), 3: (0.56, 0.5, 0.42), 4: (0.6, 0.6, 0.56), 5: (0.16, 0.56, 0.3),
            6: (0.86, 0.8, 0.56), 7: (0.3, 0.5, 0.32), 8: (0.06, 0.52, 0.64)},   # turquoise sea, white sand, jungle green
)

PLACEMENT = dict(
    new_models={"hod_ris_cove", "hod_ris_post"},
    items=[("hod_ris_cove", 1.0, ("at_vp", CAPITAL_VP)), ("hod_ris_post", 1.0, ("at_vp", "Republic Listening Post"))],
    clear={"hod_ris_cove": 4.0, "hod_ris_post": 3.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (rishi_map.py)\n{imp}"
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
