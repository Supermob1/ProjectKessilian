"""Rothana, Rothana Heavy Engineering's arctic world, as one battlefield in the Clone Wars (research:
WIPGFX/research/rothana/). CANON: arctic, icy cliffs; the Rothana shipyards in orbit, run by Rothana Heavy Engineering, a
subsidiary of Kuat Drive Yards; honeycombed orbital yards and underground factories. LEGENDS: snow and ice, wildlife
adapted to the cold; Rothana Heavy Engineering built the Republic's Acclamators and AT-TEs. Owner: KUA (kept).
LAYOUT IS A DESIGN CHOICE (the user, 2026-10-23: many impassable states): the Rothana Heavy Engineering works, the gates of
the underground factories, in the middle; the Acclamator Foundries north-east; the Walker Proving Grounds south; the
Northern Ice Cliffs (the Shola lane); the Western Landing Fields (the Hypori lane); the Southern Ice Shelf and the Eastern
Snowfields; six ice cliffs, icefalls and crevasse fields impassable; the shipyards float in orbit beside the disc (the
user, 2026-10-22: shipyards are space stations).
Names from the sources: Rothana Heavy Engineering, its underground factories, the shipyards, the Acclamator and AT-TE.
Invented: every place name.
    python "WIPGFX/plans & scripts/rothana_map.py" [--allow-dirty]   provinces.bmp, definition.csv, states, ...
    python "WIPGFX/plans & scripts/rothana_map.py" --dry OUT.png      layout + every check, writes only OUT.png
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

PLANET = "Rothana"
ZONES_JSON = "WIPGFX/Assets/rothana_zones.json"
ZONES_PNG = "WIPGFX/Assets/rothana_zones.png"
KIND = {"works": 1, "foundry": 2, "proving": 3, "field": 4, "snow": 5, "rockice": 6, "cliff": 7, "crevasse": 8}
TERRAIN = {"works": "urban", "foundry": "urban", "proving": "plains", "field": "urban", "snow": "plains", "rockice": "hills",
           "cliff": "mountain", "crevasse": "mountain"}
SEED = 43
CAPITAL = 43
CAPITAL_VP = "Rothana Heavy Engineering"
CORE = "KUA"
PORT_STATE = 467                     # the Western Landing Fields, out to the rim
ICE_IDS = tuple(range(1510, 1516))
OWNER = {s: "KUA" for s in (43, *range(464, 470), *ICE_IDS)}
WARP = (0.1, 9)
TARGET_PASSABLE = 124                # user rule: passable provinces outnumber impassable
STRAIGHT = {"works", "foundry", "proving", "field"}
YARD_AT = (92.0, 20.0)               # the orbital shipyards: (distance px, bearing deg) from the planet's centre
FEATURES = [
    ("Rothana Heavy Engineering", "works", CAPITAL, 3, [("rect", 0.0, 0.0, 0.13, 0.1, 0)]),
    ("Acclamator Foundries", "foundry", 464, 2, [("rect", 0.5, -0.35, 0.1, 0.08, 25)]),
    ("Walker Proving Grounds", "proving", 465, 3, [("rect", 0.05, 0.55, 0.16, 0.08, 0)]),
    ("Western Landing Fields", "field", 467, 2, [("rect", -0.62, 0.3, 0.09, 0.07, -20)]),
    ("Great Ice Cliffs", "cliff", 1510, 0, [("cap", -0.6, -0.5, -0.1, -0.35, 0.07)]),
    ("Frozen Escarpment", "cliff", 1511, 0, [("cap", 0.25, -0.05, 0.28, 0.35, 0.07)]),
    ("Shattered Icefall", "cliff", 1512, 0, [("cap", -0.3, 0.12, -0.42, 0.55, 0.07)]),
    ("Rothana Crevasses", "crevasse", 1513, 0, [("cap", 0.55, 0.2, 0.85, 0.42, 0.07)]),
    ("Northern Ice Wall", "cliff", 1514, 0, [("cap", 0.0, -0.62, 0.3, -0.85, 0.07)]),
    ("Glacier Tongue", "crevasse", 1515, 0, [("cap", -0.85, -0.1, -0.55, 0.0, 0.07)]),
]
SEEDS = {CAPITAL: ((0.0, 0.0), "snow"), 464: ((0.55, -0.4), "rockice"), 465: ((0.05, 0.6), "snow"), 466: ((-0.1, -0.78), "rockice"),
         467: ((-0.7, 0.3), "snow"), 468: ((0.5, 0.75), "snow"), 469: ((0.8, -0.05), "rockice")}
STATE_NAMES = {CAPITAL: "Rothana Heavy Engineering", 464: "Acclamator Foundries", 465: "Walker Proving Grounds",
               466: "Northern Ice Cliffs", 467: "Western Landing Fields", 468: "Southern Ice Shelf", 469: "Eastern Snowfields",
               1510: "Great Ice Cliffs", 1511: "Frozen Escarpment", 1512: "Shattered Icefall", 1513: "Rothana Crevasses",
               1514: "Northern Ice Wall", 1515: "Glacier Tongue"}
IMPASSABLE = set(ICE_IDS)
VPS = [(CAPITAL, "Rothana Heavy Engineering", CAPITAL_VP, 15), (464, "Acclamator Foundries", "Acclamator Foundries", 10),
       (465, "Walker Proving Grounds", "Walker Proving Grounds", 5), (467, "Western Landing Fields", "Western Landing Fields", 3),
       (466, "rockice", "Northern Ice Cliffs", 1), (468, "snow", "Southern Ice Shelf", 1), (469, "rockice", "Eastern Snowfields", 1)]

TERRAIN_CFG = dict(
    seed=43, base=4, rough=2, open=(5, 6),
    zones={
        1: dict(relief=("ramp_top", 8, 4, 3), tex=["URBAN", ("SNOWROCK", ">", 0.6)]),                 # the works' gates
        2: dict(relief=("flat", 5), tex=["URBAN", ("SNOWSAND", ">", 0.6)]),                           # the foundries
        3: dict(relief=("rolling", 3, 1, 6), tex=["SNOWSAND", ("ROCK2", ">", 0.7)]),                  # proving grounds
        4: dict(relief=("flat", 4), tex=["URBAN", ("SNOWSAND", ">", 0.6)]),                           # landing fields
        5: dict(relief=("rolling", 5, 3, 6), tex=["SNOWSAND", ("SNOWFARM", ">", 0.6), ("SNOWROCK", ">", 0.92)],
                props=[(210, 0.06)]),                                                                 # snowfields
        6: dict(relief=("rolling", 10, 7, 4), tex=["SNOWROCK", ("SNOWSAND", ">", 0.5), ("ROCK", ">", 0.88)],
                props=[(219, 0.12), (210, 0.1)]),                                                     # rocky ice
        7: dict(relief=("mesa", 6, 36, 2, (4, 0.7)), tex=["SNOWROCK", ("ROCK", ">", 0.6)], props=[(219, 0.15)]),   # cliffs
        8: dict(relief=("rolling", 1, 1, 3), tex=["SNOWROCK", ("ROCK", ">", 0.5)], props=[(210, 0.2)]),
    },
    city={1: 125, 2: 125, 4: 125},   # map/cities.txt 125: RHE factory blocks in the snow (rot_town)
    prop_clear=1.5,
    colors={1: (0.62, 0.64, 0.66), 2: (0.6, 0.6, 0.62), 3: (0.82, 0.84, 0.86), 4: (0.66, 0.66, 0.68), 5: (0.92, 0.94, 0.96),
            6: (0.74, 0.78, 0.84), 7: (0.6, 0.66, 0.76), 8: (0.32, 0.4, 0.56)},   # bright snow, grey-blue cliffs
)


def orbit(ctx):
    """the Rothana shipyards (canon: honeycombed orbital yards of Rothana Heavy Engineering) in orbit beside the disc"""
    (cy, cx), (r, b) = ctx["z"]["centre"], (YARD_AT[0], math.radians(YARD_AT[1]))
    ctx["put"]("hod_rot_yards", 1.0, cy - r * math.sin(b), cx + r * math.cos(b))


PLACEMENT = dict(
    new_models={"hod_rot_works", "hod_rot_foundry", "hod_rot_yards"},
    items=[("hod_rot_works", 1.0, ("at_vp", CAPITAL_VP)), ("hod_rot_foundry", 1.0, ("at_vp", "Acclamator Foundries"))],
    clear={"hod_rot_works": 5.0, "hod_rot_foundry": 4.5},
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
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: {PLANET} (rothana_map.py)\n{imp}"
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
