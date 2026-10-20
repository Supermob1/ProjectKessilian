"""Korriban (Moraband), the Sith homeworld, as one battlefield: the Valley of the Dark Lords fills the planet
(user, 2026-10-13: "centred on the valley", nothing else outside it). References: the Moraband fan maps, Tom Cartos'
Valley of Tombs (tombs cut into the valley sides, an avenue of pillars), TOR's Korriban (the academy at the valley's
head). A broad valley floor walled in by mountains to the planet's edge; the abandoned Sith Academy at its west end, its
own state of several provinces; the ruins of Dreshdae at the east mouth; five tombs in the walls, each its own state:
the entrance on the valley floor and a crypt behind it in the rock to explore (the tarantarek nests). The planet is
abandoned (user): no towns, no city models. Shapes are carved and ragged, not round. All the planet's province ids
are used (~70 passable, the rest in the mountains); every state is one piece. Names: Wookieepedia (korriban_research.md).

    python "WIPGFX/plans & scripts/korriban_map.py"     provinces.bmp, definition.csv, states, names, positions

The planet keeps its province ids and colours (strategic region unchanged); only the pixels move. Writes WIPGFX/Assets/korriban_zones.json + korriban_zones.png (KIND per pixel) for
planet_terrain_gen.py --korriban and military_buildings.py korriban_place.
Run order: korriban_map.py -> planet_terrain_gen.py --korriban -> military_buildings.py korriban_place ->
planet_terrain_gen.py --globe-texture.
"""
import glob, math, os, re, sys
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from felucia_map import split_area
from felucia_tribes import block, place, rw
from raxus_map import mend
import planet_common as pcom

PLANET = "Korriban"
ZONES_JSON = "WIPGFX/Assets/korriban_zones.json"
ZONES_PNG = "WIPGFX/Assets/korriban_zones.png"
KIND = {"tomb": 1, "valley": 2, "academy": 3, "mountain": 4, "ruins": 7, "crypt": 9}
TERRAIN = {"tomb": "hills", "valley": "desert", "academy": "hills", "mountain": "mountain", "ruins": "desert",
           "crypt": "hills"}
SEED = 90
CAPITAL = 90
WARP = (0.09, 9)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
# features, painted in this order over the rock, in planet radii (u east, v south) after the warp: (name, kind,
# state, provinces, shapes), the union of the shapes: ("ell", u, v, ru, rv, deg), ("rect", u, v, hu, hv, deg) or
# ("cap", u0, v0, u1, v1, r); several overlapping pieces each, so nothing comes out round
VALLEY = (0.04, 0.0, 0.68, 0.4)      # the Valley of the Dark Lords: centre and half-axes of its floor
FEATURES = [
    ("Valley of the Dark Lords", "valley", 779, 26, [("ell", *VALLEY, 0), ("ell", -0.2, -0.12, 0.4, 0.3, 12),
                                                      ("ell", 0.3, 0.1, 0.38, 0.3, -18)]),
    ("Sith Academy", "academy", 780, 12, [("rect", -0.66, 0.0, 0.17, 0.26, 4), ("rect", -0.74, -0.2, 0.12, 0.1, -10),
                                          ("rect", -0.72, 0.2, 0.13, 0.09, 8), ("rect", -0.5, 0.02, 0.1, 0.13, 0)]),
    ("Dreshdae", "ruins", CAPITAL, 6, [("ell", 0.78, -0.06, 0.13, 0.16, 25), ("ell", 0.84, 0.12, 0.12, 0.13, -30),
                                      ("cap", 0.82, 0.04, 1.05, 0.0, 0.08)]),
]
# the tombs in the valley walls: (name, state, u along the valley, side -1 north / +1 south); behind each, a passage
# and a chamber in the rock (TOMB_CRYPT: planet radii deeper, chamber radius, passage radius)
TOMBS = [("Tomb of Marka Ragnos", 781, -0.3, -1), ("Tomb of Naga Sadow", 782, 0.05, -1),
         ("Tomb of Ajunta Pall", 783, 0.38, -1), ("Tomb of Tulak Hord", 784, -0.18, 1),
         ("Tomb of Ludo Kressh", 785, 0.22, 1)]
TOMB_R = (0.11, 0.1)                 # the entrance forecourt: half-width along the wall, depth into it (carved square)
TOMB_N = 2                           # provinces per entrance
TOMB_CRYPT = (0.3, 0.12, 0.05)       # crypt: depth behind the wall, chamber size, passage half-width
CRYPT_N = 3                          # provinces per crypt
# the rock: four impassable states by direction from the valley's centre (degrees, counter-clockwise from east),
# sharing out the province ids left over by area
MOUNTAIN_SECTORS = {1143: (0, 90), 1144: (90, 180), 1146: (180, 270), 1145: (270, 360)}
STATE_NAMES = {CAPITAL: "Dreshdae", 779: "Valley of the Dark Lords", 780: "Sith Academy",
               **{sid: n for n, sid, _, _ in TOMBS},
               1143: "The North-Eastern Spires", 1144: "The North-Western Spires", 1145: "The South-Eastern Spires",
               1146: "The South-Western Spires"}
IMPASSABLE = set(MOUNTAIN_SECTORS)
# victory points: (state, feature, name, value); the tomb entrances get theirs after these
VPS = [(CAPITAL, "Dreshdae", "Dreshdae", 10), (CAPITAL, "Dreshdae", "Old Landing Field", 2),
       (779, "Valley of the Dark Lords", "Valley of the Dark Lords", 5),
       (779, "Valley of the Dark Lords", "Eternal Pyre", 1),
       (780, "Sith Academy", "Sith Academy", 5), (780, "Sith Academy", "Hall of Judgment", 1)]


def mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    return land, pid, np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])


def shape(s, U, V):
    if s[0] == "ell":
        _, u, v, ru, rv, deg = s
        a = math.radians(deg)
        du, dv = U - u, V - v
        x, y = du * math.cos(a) + dv * math.sin(a), -du * math.sin(a) + dv * math.cos(a)
        return (x / ru) ** 2 + (y / rv) ** 2 <= 1
    if s[0] == "rect":
        _, u, v, hu, hv, deg = s
        a = math.radians(deg)
        du, dv = U - u, V - v
        return (np.abs(du * math.cos(a) + dv * math.sin(a)) <= hu) & (np.abs(-du * math.sin(a) + dv * math.cos(a)) <= hv)
    _, u0, v0, u1, v1, r = s
    du, dv = u1 - u0, v1 - v0
    t = np.clip(((U - u0) * du + (V - v0) * dv) / (du * du + dv * dv), 0, 1)
    return np.hypot(U - u0 - t * du, V - v0 - t * dv) <= r


def layout(m, rng):
    """feature index per pixel, features [(name, kind, state, provinces)]: FEATURES, each tomb's entrance and crypt,
    then the rock by sector"""
    import planet_terrain_gen as g
    ys, xs = np.nonzero(m)
    cy, cx, R = ys.mean(), xs.mean(), math.sqrt(m.sum() / math.pi)
    sl = np.s_[ys.min() - 2:ys.max() + 3, xs.min() - 2:xs.max() + 3]
    yy, xx = np.mgrid[sl].astype(np.float32)
    U0, V0 = (xx - cx) / R, (yy - cy) / R
    U = U0 + (g.noise(U0.shape, WARP[1], rng, 2) - 0.5) * 2 * WARP[0]
    V = V0 + (g.noise(U0.shape, WARP[1], rng, 2) - 0.5) * 2 * WARP[0]
    sm = m[sl]
    lab = np.full(sm.shape, -1, np.int32)
    feats = []
    for name, kind, sid, n, shapes in FEATURES:
        feats.append((name, kind, sid, n))
        lab[sm & np.any([shape(s_, U, V) for s_ in shapes], 0)] = len(feats) - 1
    for name, sid, u, side in TOMBS:
        uu = VALLEY[0] + u
        v = VALLEY[1] + side * VALLEY[3] * math.sqrt(max(0.0, 1 - (u / VALLEY[2]) ** 2))
        feats.append((name, "tomb", sid, TOMB_N))                         # the forecourt, cut square into the wall
        lab[sm & (lab < 0) & shape(("rect", uu, v + side * TOMB_R[1] * 0.6, TOMB_R[0], TOMB_R[1], 0), U, V)] = len(feats) - 1
        deep, bend = v + side * TOMB_CRYPT[0], (0.06 if u < 0 else -0.06)
        mid = v + side * TOMB_CRYPT[0] * 0.55
        c, w = TOMB_CRYPT[1], TOMB_CRYPT[2]
        feats.append((name.replace("Tomb of", "Crypt of"), "crypt", sid, CRYPT_N))   # crooked passage, ragged chamber
        crypt = [("cap", uu, v + side * TOMB_R[1], uu + bend, mid, w), ("cap", uu + bend, mid, uu, deep, w),
                 ("rect", uu, deep, c, c * 0.6, 15 * side), ("rect", uu + bend, deep + side * c * 0.4, c * 0.6, c * 0.5, -20)]
        lab[sm & (lab < 0) & np.any([shape(q, U, V) for q in crypt], 0)] = len(feats) - 1
    ang = np.degrees(np.arctan2(-(V0 - VALLEY[1]), U0 - VALLEY[0])) % 360
    rock = sm & (lab < 0)
    for sid, (a0, a1) in MOUNTAIN_SECTORS.items():
        feats.append((STATE_NAMES[sid], "mountain", sid, 0))             # provinces: the ids left over (main)
        lab[rock & (ang >= a0) & (ang < a1)] = len(feats) - 1
    full = np.full(m.shape, -1, np.int32)
    full[sl] = lab
    return full, feats


def tidy(lab, feats, m):
    """every feature in one piece: stray bits join the neighbour they share most border with (its own state first)"""
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
            lab[frag] = max(same, key=lambda k: nb[k]) if same else int(nb.argmax())
    return lab


def main():
    pcom.guard(PLANET, STATE_NAMES, [f[2] for f in FEATURES])
    land, pid, m = mask()
    ids = sorted(np.unique(pid[m]).tolist())
    rng = np.random.default_rng(SEED)
    lab, feats = layout(m, rng)
    lab = tidy(lab, feats, m)
    for i, f in enumerate(feats):
        assert ndi.label(lab == i)[1] == 1, f"{f[0]} in pieces"
    passable = m & np.isin(lab, [i for i, f in enumerate(feats) if f[2] not in IMPASSABLE])
    assert ndi.label(passable)[1] == 1, "the open ground is cut in two"
    groups = []
    for i, (name, kind, sid, n) in enumerate(feats):
        a = lab == i
        groups.append(dict(name=name, kind=kind, state=sid, mask=a, n=n))
    rest = [g_ for g_ in groups if not g_["n"]]                           # the mountains share the ids left over
    left = len(ids) - sum(g_["n"] for g_ in groups)
    area = sum(g_["mask"].sum() for g_ in rest)
    for g_ in rest:
        g_["n"] = max(1, int(left * g_["mask"].sum() / area))
    rest[0]["n"] += len(ids) - sum(g_["n"] for g_ in groups)
    assert sum(g_["n"] for g_ in groups) == len(ids) and rest[0]["n"] >= 1
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
    spare = [p for p in ids if p not in prov]
    mend(newpid, m, {p: dict(v, state=v["group"]) for p, v in prov.items()})
    uncross(newpid, m)
    for sid in {v["state"] for v in prov.values()}:
        assert ndi.label(np.isin(newpid, [p for p, v in prov.items() if v["state"] == sid]))[1] == 1, f"state {sid} in pieces"
    rows = pcom.definition_rows()
    pcom.measure(prov, newpid, pid, rows, TERRAIN)
    pcom.write_map(newpid, m, rows, prov)
    vp_names = states(prov, land, m, newpid, spare, rng)
    kind = np.zeros(m.shape, np.uint8)
    for p, v in prov.items():
        kind[newpid == p] = v["kind"]
    pcom.write_zones(ZONES_JSON, ZONES_PNG, m, kind, vp_names, prov)
    assert not spare, "every id should have pixels"


def uncross(newpid, m):
    """No four provinces meeting at one corner (HOI4 logs X crossings): one pixel of the 2 x 2 joins a neighbour,
    if its own province stays in one piece. Works on the planet's bounding box and checks the province in a window
    round the pixel (whole-map labelling per crossing took minutes on Ithor's narrow sky-lanes, 2026-10-20)."""
    ys, xs = np.nonzero(m)
    y0, x0 = max(ys.min() - 1, 0), max(xs.min() - 1, 0)
    a, mm = newpid[y0:ys.max() + 2, x0:xs.max() + 2], m[y0:ys.max() + 2, x0:xs.max() + 2]   # views: edits go through
    W = 40                                                               # window half size: provinces are far smaller
    for _ in range(200000):
        A, B, C, D = a[:-1, :-1], a[1:, :-1], a[:-1, 1:], a[1:, 1:]
        x = (A != B) & (A != C) & (A != D) & (B != C) & (B != D) & (C != D) & mm[:-1, :-1] & mm[1:, 1:]
        if not x.any():
            return
        r, c = np.argwhere(x)[0]
        for (pr, pc), (qr, qc) in (((r, c), (r + 1, c)), ((r + 1, c + 1), (r, c + 1)), ((r, c), (r, c + 1)),
                                   ((r + 1, c + 1), (r + 1, c))):
            old = a[pr, pc]
            a[pr, pc] = a[qr, qc]
            win = a[max(pr - W, 0):pr + W + 1, max(pc - W, 0):pc + W + 1] == old
            if mm[pr, pc] and ndi.label(win)[1] == 1:
                break
            a[pr, pc] = old
        else:
            raise AssertionError(f"X crossing at {r + y0}, {c + x0} could not be fixed")
    raise AssertionError("uncross: X crossings keep reappearing")


def states(prov, land, m, newpid, spare, rng):
    """state files keeping resources, industry and manpower (owner kept); victory points, names, map positions,
    units. Lanes and rails through the spare ids go through the capital first, so place() re-anchors them too."""
    old = pcom.old_states(STATE_NAMES)
    owner = re.search(r"owner\s*=\s*(\w+)", open(old[CAPITAL], encoding="utf-8-sig").read()).group(1)
    pc = lambda p: np.array(prov[p]["centre"])
    by_state = {}
    for p, v in prov.items():
        by_state.setdefault(v["state"], []).append(p)
    vp_names, vps = {}, {}
    for sid, feat, name, val in VPS:
        cand = [p for p in by_state[sid] if prov[p]["feature"] == feat and p not in vp_names]
        if name == "Old Landing Field":                                    # the port: on the planet's edge
            cand = [p for p in cand if prov[p]["coastal"]] or cand
        cen = np.mean([pc(p) for p in prov if prov[p]["feature"] == feat], 0)    # the middle of the feature
        p = min(cand, key=lambda q: np.hypot(*(pc(q) - cen)))
        vp_names[p], vps[p] = name, val
    for name in dict.fromkeys(v["feature"] for v in prov.values() if v["zone"] == "tomb"):   # one per tomb, on its biggest
        # province; in layout order (a set's order follows PYTHONHASHSEED and changed the output between runs)
        p = max((q for q, v in prov.items() if v["feature"] == name), key=lambda q: prov[q]["area"])
        vp_names[p], vps[p] = name, 5 if name == "Tomb of Marka Ragnos" else 3
    capital_p = next(p for p, n in vp_names.items() if n == "Dreshdae")
    port = next(p for p, n in vp_names.items() if n == "Old Landing Field")
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
        bld = re.sub(r"\n\s*\d+\s*=\s*\{[^{}]*\}", "", bld)                    # province buildings (ports) go
        bld = re.sub(r"\n\s*dockyard\s*=\s*\d+", "", bld)
        man = re.search(r"manpower\s*=\s*(\d+)", src).group(1) if src else "2000"
        cat = re.search(r"state_category\s*=\s*(\w+)", src).group(1) if src else "wasteland_sector"
        imp = ""
        if sid == CAPITAL:                                                 # the planet's yards and port: Dreshdae
            if docks:
                bld = bld.rstrip().rstrip("}") + f"\tdockyard = {docks}\n\t\t}}"
            if naval:
                bld = bld.rstrip().rstrip("}") + f"\t\t\t{port} = {{\n\t\t\t\tnaval_base = {max(naval)}\n\t\t\t}}\n\t\t}}"
        if sid in IMPASSABLE:
            imp = f"\timpassable = yes\n\tforce_link_ownership_to = {CAPITAL}\n"
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            res, man, cat = "\n\tresources={\n\t}", "2000", "wasteland_sector"
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {vps[p]}\n\t\t}}\n" for p in provs if p in vps)
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: Korriban (korriban_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {owner}\n\t\tadd_core_of = {owner}\n\t}}\n"
                f"\tmanpower = {man}\n\tstate_category = {cat}\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}}\n")
        if sid in old:
            os.remove(old[sid])
        open(f"history/states/{sid}-Korriban - {STATE_NAMES[sid].replace(chr(39), '')}.txt", "w", encoding="utf-8",
             newline="\n").write(text)
        cen = np.mean([pc(p) for p in provs], 0)
        main_p = capital_p if sid == CAPITAL else next((p for p in provs if p in vps and prov[p]["zone"] != "tomb"),
                                                      min(provs, key=lambda p: np.hypot(*(pc(p) - cen))))
        sts[sid] = dict(kind="white" if sid in IMPASSABLE else "open", provinces=provs,
                        coastal=[p for p in provs if prov[p]["coastal"]], main=main_p)
    for sid in set(old) - set(sts):
        os.remove(old[sid])
    sp = {str(p) for p in spare}
    rw("map/adjacencies.csv", lambda s: "".join(";".join(str(capital_p) if i in (0, 1) and x in sp else x
                                                         for i, x in enumerate(l.split(";"))) for l in s.splitlines(True)))
    rw("map/railways.txt", lambda s: "".join(" ".join(str(capital_p) if i > 1 and x in sp else x
                                                      for i, x in enumerate(l.split(" "))) for l in s.splitlines(True)))
    place(sts, prov, newpid, land, m, set(sts) | set(old), port, CAPITAL, rng)
    fprov = set(prov) | set(spare)
    blocked = {p for p, v in prov.items() if v["state"] in IMPASSABLE} | set(spare)
    for f in glob.glob("history/units/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        if any(int(x) in fprov for x in re.findall(r"naval_base\s*=\s*(\d+)", s)):   # fleets: to the spaceport
            rw(f, lambda s_: re.sub(r"\b(naval_base|location)(\s*=\s*)(\d+)\b",
                                    lambda q: q.group(1) + q.group(2) + (str(port) if int(q.group(3)) in fprov else q.group(3)), s_))
        else:
            rw(f, lambda s_: re.sub(r"\blocation(\s*=\s*)(\d+)\b",
                                    lambda q: "location" + q.group(1) + (str(capital_p) if int(q.group(2)) in blocked else q.group(2)), s_))

    pcom.state_names_loc(STATE_NAMES)

    def fv(s):
        s = re.sub(r'\n VICTORY_POINTS_(\d+):\d* "[^"]*"', lambda q: "" if int(q.group(1)) in fprov else q.group(0), s)
        return s.rstrip("\n") + "\n" + "".join(f' VICTORY_POINTS_{p}:0 "{n}"\n' for p, n in vp_names.items())
    rw("localisation/english/victory_points_l_english.yml", fv)
    for sid, st in sorted(sts.items()):
        print(f"{sid:5} {st['kind']:5} {len(st['provinces']):3} provinces  {STATE_NAMES[sid]}")
    return vp_names


if __name__ == "__main__":
    pcom.run(main)
