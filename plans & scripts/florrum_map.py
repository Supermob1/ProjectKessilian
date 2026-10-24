"""Florrum, the Ohnaka Gang's sulfur desert (Wookieepedia; The Clone Wars "Dooku Captured", "The Gungan General",
"A Necessary Bond"): olive-ochre dust plains broken by flat-topped, stacked rock shelves; a canyon through the middle;
sulfur geysers on the acid flats; small scattered mercenary bases. The Commerce Guild holds most of the planet; the
Ohnaka Gang keeps a few enclaves: Hondo's complex on the canyon rim (their capital), Hondo's secret ship vault hidden
in the eastern mesa, and the pirates' junk market in a canyon bowl. The mesas are impassable.

    python "WIPGFX/plans & scripts/florrum_map.py"     provinces.bmp, definition.csv, states, names, positions

The planet keeps all its province ids and colours (strategic region 192 unchanged); only the pixels move. The lanes'
Florrum ends that the user chose (21832 from Korriban, 21823 from Felucia) stay on those ids. Writes
WIPGFX/Assets/florrum_zones.json + florrum_zones.png (KIND per pixel) for planet_terrain_gen.py --florrum.
Run order: florrum_map.py -> planet_terrain_gen.py --florrum -> military_buildings.py florrum_place ->
florrum_fx.py -> planet_terrain_gen.py --globe-texture.
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

PLANET = "Florrum"
ZONES_JSON = "WIPGFX/Assets/florrum_zones.json"
ZONES_PNG = "WIPGFX/Assets/florrum_zones.png"
KIND = {"plains": 1, "canyon": 2, "acid": 3, "mesa": 4, "base": 5, "market": 6}
TERRAIN = {"plains": "desert", "canyon": "hills", "acid": "desert", "mesa": "mountain", "base": "urban",
           "market": "hills"}
SEED = 192
CAPITAL = 192
OHN, CMG = "OHN", "CMG"
WARP = (0.08, 7)                     # ragged edges: warp amplitude (planet radii) and noise cell (px)
PX = 52                              # px per province of open ground (plains, canyon, acid flats)
MESA_PX = 130                        # px per impassable mesa province
# the canyon down the middle of the planet, north to south (planet radii, u east, v south), and its half-width
CANYON = [(0.08, -1.05), (0.12, -0.55), (-0.02, -0.15), (0.06, 0.25), (-0.06, 0.6), (0.02, 1.05)]
CANYON_W = 0.1
# features painted over the open ground in this order: (name, kind, state or None = by seed, provinces or 0 = by
# area, shapes); a shape is ("ell", u, v, ru, rv, deg), ("rect", u, v, hu, hv, deg) or ("cap", u0, v0, u1, v1, r)
FEATURES = [
    ("Northern Shelf", "mesa", 1147, 0, [("ell", -0.5, -0.5, 0.32, 0.26, 25), ("ell", -0.28, -0.72, 0.18, 0.14, -10)]),
    ("Eastern Shelf", "mesa", 1148, 0, [("ell", 0.58, 0.05, 0.22, 0.36, -8), ("ell", 0.44, 0.32, 0.15, 0.14, 20)]),
    ("Southern Shelf", "mesa", 1149, 0, [("ell", -0.5, 0.42, 0.25, 0.22, -20), ("ell", -0.32, 0.62, 0.16, 0.12, 15)]),
    ("Hondo's Complex", "base", CAPITAL, 3, [("ell", 0.24, -0.3, 0.2, 0.16, 15)]),
    ("Hondo's Secret Ship Vault", "base", 1033, 1, [("rect", 0.62, 0.0, 0.08, 0.12, -8),
                                                   ("cap", 0.62, 0.0, 0.3, 0.0, 0.05)]),
    ("Weequay Junk Market", "market", 1034, 2, [("ell", -0.12, 0.3, 0.19, 0.15, -20)]),
    ("Acid Flats", "acid", None, 0, [("ell", 0.36, 0.66, 0.3, 0.2, -25)]),
]
# the rest of the open ground goes to the Commerce Guild state with the nearest seed (u, v)
SEEDS = {1035: (-0.7, 0.0), 1036: (0.4, 0.62), 1037: (0.0, -0.75), 1038: (0.62, -0.5), 1039: (-0.1, 0.85)}
OWNER = {CAPITAL: OHN, 1033: OHN, 1034: OHN}           # everything else: the Commerce Guild
STATE_NAMES = {CAPITAL: "Hondo's Complex", 1033: "Hondo's Vault", 1034: "Weequay Junk Market", 1035: "Doshar Fields",
               1036: "Sulfur Acid Flats", 1037: "Guild Sulfur Works", 1038: "Skalder Plains", 1039: "Southern Dustbowl",
               1147: "The Northern Shelf", 1148: "The Eastern Shelf", 1149: "The Southern Shelf"}
IMPASSABLE = {1147, 1148, 1149}
# victory points: (state, feature name or kind, name, value)
VPS = [(CAPITAL, "Hondo's Complex", "Hondo's Complex", 10), (1033, "Hondo's Secret Ship Vault", "Hondo's Secret Ship Vault", 3),
       (1034, "Weequay Junk Market", "Weequay Junk Market", 3), (1035, "plains", "Doshar Fields", 3),
       (1036, "acid", "Guild Sulfur Refinery", 3), (1037, "plains", "Guild Sulfur Works", 2),
       (1038, "plains", "Skalder Plains", 1), (1039, "plains", "Dustbowl Outpost", 1)]
PINNED = {21832: 3180, 21823: 3702, 21843: 7832}   # + Dromund Kaas (user, 2026-10-13)  # Florrum end of a lane -> the province at its other end (adjacencies.csv)


def mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    return land, pid, np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])


def layout(m, rng):
    """feature index per pixel and features [(name, kind, state, provinces)]: the mesas, the canyon, the enclaves,
    the acid flats, then the plains, each open piece split by the nearest Commerce Guild seed"""
    import planet_terrain_gen as g
    ys, xs = np.nonzero(m)
    cy, cx, R = ys.mean(), xs.mean(), math.sqrt(m.sum() / math.pi)
    sl = np.s_[ys.min() - 2:ys.max() + 3, xs.min() - 2:xs.max() + 3]
    yy, xx = np.mgrid[sl].astype(np.float32)
    U0, V0 = (xx - cx) / R, (yy - cy) / R
    U = U0 + (g.noise(U0.shape, WARP[1], rng, 2) - 0.5) * 2 * WARP[0]
    V = V0 + (g.noise(U0.shape, WARP[1], rng, 2) - 0.5) * 2 * WARP[0]
    sm = m[sl]
    kind = np.zeros(sm.shape, np.uint8)
    fid = np.full(sm.shape, -1, np.int32)
    feats = []
    canyon = np.any([shape(("cap", *a, *b, CANYON_W), U, V) for a, b in zip(CANYON, CANYON[1:])], 0)
    for name, k, sid, n, shapes in FEATURES:
        sel = sm & np.any([shape(s_, U, V) for s_ in shapes], 0)
        if k == "mesa":
            sel &= ~canyon                                                # the canyon cuts between the shelves
        feats.append((name, k, sid, n))
        fid[sel] = len(feats) - 1
    kind[sm] = KIND["plains"]
    kind[sm & canyon & (fid < 0)] = KIND["canyon"]
    for i, (name, k, sid, n) in enumerate(feats):
        kind[fid == i] = KIND[k]
    # open ground not in a fixed-state feature: one group per Guild state (nearest seed); the plains, canyon and
    # acid flats in it keep their own look (kind), the provinces take their main kind
    seeds = list(SEEDS.items())
    near = np.argmin(np.stack([np.hypot(U - u, V - v) for _, (u, v) in seeds]), 0)
    free = sm & ((fid < 0) | np.isin(fid, [i for i, f in enumerate(feats) if f[2] is None]))
    for i, (sid, _) in enumerate(seeds):
        feats.append((STATE_NAMES[sid], "plains", sid, 0))
        fid[free & (near == i)] = len(feats) - 1
    full = lambda a, fill: (lambda z: (z.__setitem__(sl, a), z)[1])(np.full(m.shape, fill, a.dtype))
    return full(fid, -1), full(kind, 0), feats


def tidy(lab, feats, m):
    """every feature in one piece and every state in one piece: stray bits join the neighbour of their own state
    with the longest shared border, else the open neighbour they share most border with"""
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
                opn = [k for k in np.nonzero(nb)[0] if feats[k][2] not in IMPASSABLE]
                pick = same or (opn if feats[i][2] not in IMPASSABLE else []) or list(np.nonzero(nb)[0])
                lab[frag] = max(pick, key=lambda k: nb[k])
    return lab


def main():
    pcom.guard(PLANET, STATE_NAMES, [f[2] for f in FEATURES])
    land, pid, m = mask()
    ids = sorted(np.unique(pid[m]).tolist())
    rng = np.random.default_rng(SEED)
    lab, kind, feats = layout(m, rng)
    lab = tidy(lab, feats, m)
    for i, f in enumerate(feats):                                         # moved bits take their new feature's look
        if f[1] in ("mesa", "base", "market"):
            kind[lab == i] = KIND[f[1]]
        else:
            kind[(lab == i) & np.isin(kind, [KIND[k] for k in ("mesa", "base", "market")])] = KIND["plains"]
    for i, f in enumerate(feats):
        assert ndi.label(lab == i)[1] <= 1, f"{f[0]} {f[2]} in pieces"
    passable = m & np.isin(lab, [i for i, f in enumerate(feats) if f[2] not in IMPASSABLE])
    assert ndi.label(passable)[1] == 1, "the open ground is cut in two"
    groups = [dict(name=f[0], kind=f[1], state=f[2], mask=lab == i, n=f[3]) for i, f in enumerate(feats) if (lab == i).any()]
    for g_ in groups:                                                     # by area: open ground, then the mesas
        if not g_["n"] and g_["state"] not in IMPASSABLE:
            g_["n"] = max(1, round(g_["mask"].sum() / PX))
    mesas = [g_ for g_ in groups if g_["state"] in IMPASSABLE]
    left = len(ids) - sum(g_["n"] for g_ in groups)
    area = sum(g_["mask"].sum() for g_ in mesas)
    for g_ in mesas:
        g_["n"] = max(1, int(left * g_["mask"].sum() / area))
    mesas[0]["n"] += len(ids) - sum(g_["n"] for g_ in groups)
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
            ks = np.bincount(kind[ys[part == i], xs[part == i]], minlength=10)
            zone = next(k for k, v in KIND.items() if v == int(ks.argmax()))   # its main look
            prov[p] = dict(zone=zone, kind=KIND[zone], feature=gr["name"] if zone == gr["kind"] else zone,
                           state=gr["state"], group=gi)
    mend(newpid, m, {p: dict(v, state=v["group"]) for p, v in prov.items()})
    uncross(newpid, m)
    for sid in {v["state"] for v in prov.values()}:
        assert ndi.label(np.isin(newpid, [p for p, v in prov.items() if v["state"] == sid]))[1] == 1, f"state {sid} in pieces"
    rows = pcom.definition_rows()
    pcom.measure(prov, newpid, pid, rows, TERRAIN)
    pin(newpid, prov, pid)
    pcom.write_map(newpid, m, rows, prov)
    vp_names = states(prov, land, m, newpid, rng)
    pcom.write_zones(ZONES_JSON, ZONES_PNG, m, kind, vp_names, prov)


def landing_for(far, prov, pid, taken):
    """the passable coastal province place() would land a lane from province `far` on"""
    rs, cs = np.nonzero(pid == far)
    fr, fc = rs.mean(), cs.mean()
    cand = [p for p, v in prov.items() if v["coastal"] and v["state"] not in IMPASSABLE and p not in taken]
    return min(cand, key=lambda p: math.hypot(prov[p]["centre"][0] - fr, prov[p]["centre"][1] - fc))


def pin(newpid, prov, pid):
    """the user's lane ends keep their ids: swap ids so that the province each lane lands on is the pinned id"""
    taken = set()
    for keep, far in PINNED.items():
        p = landing_for(far, prov, pid, taken)
        if p != keep:
            a, b = newpid == p, newpid == keep
            newpid[a], newpid[b] = keep, p
            prov[p], prov[keep] = prov[keep], prov[p]
        taken.add(keep)


def states(prov, land, m, newpid, rng):
    """state files keeping resources, industry and manpower; owners (Ohnaka Gang enclaves, the Guild elsewhere),
    victory points, names, map positions, units"""
    old = pcom.old_states(STATE_NAMES)
    pc = lambda p: np.array(prov[p]["centre"])
    by_state = {}
    for p, v in prov.items():
        by_state.setdefault(v["state"], []).append(p)
    vp_names, vps = {}, {}
    for sid, feat, name, val in VPS:
        cand = [p for p in by_state[sid] if (prov[p]["feature"] == feat or prov[p]["zone"] == feat) and p not in vp_names]
        cen = np.mean([pc(p) for p in cand], 0)
        p = min(cand, key=lambda q: np.hypot(*(pc(q) - cen)))
        vp_names[p], vps[p] = name, val
    capital_p = next(p for p, n in vp_names.items() if n == "Hondo's Complex")
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
        owner = OWNER.get(sid, CMG)
        imp = ""
        coastal = [p for p in provs if prov[p]["coastal"]]
        if sid == CAPITAL and coastal:                                    # the pirates' port and yards: Hondo's complex
            port = min(coastal, key=lambda p: np.hypot(*(pc(p) - pc(capital_p))))
            if docks:
                bld = bld.rstrip().rstrip("}") + f"\tdockyard = {docks}\n\t\t}}"
            if naval:
                bld = bld.rstrip().rstrip("}") + f"\t\t\t{port} = {{\n\t\t\t\tnaval_base = {max(naval)}\n\t\t\t}}\n\t\t}}"
        if sid in IMPASSABLE:
            imp = f"\timpassable = yes\n"
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            res, man, cat, owner = "\n\tresources={\n\t}", "1000", "wasteland_sector", CMG
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {vps[p]}\n\t\t}}\n" for p in provs if p in vps)
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: Florrum (florrum_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {owner}\n\t\tadd_core_of = {owner}\n\t}}\n"
                f"\tmanpower = {man}\n\tstate_category = {cat}\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}}\n")
        if sid in old:
            os.remove(old[sid])
        open(f"history/states/{sid}-Florrum - {STATE_NAMES[sid].replace(chr(39), '')}.txt", "w", encoding="utf-8",
             newline="\n").write(text)
        cen = np.mean([pc(p) for p in provs], 0)
        main_p = capital_p if sid == CAPITAL else next((p for p in provs if p in vps),
                                                      min(provs, key=lambda p: np.hypot(*(pc(p) - cen))))
        sts[sid] = dict(kind="white" if sid in IMPASSABLE else "open", provinces=provs, coastal=coastal, main=main_p)
    for sid in set(old) - set(sts):
        os.remove(old[sid])
    port = next((p for p in sts[CAPITAL]["coastal"]), capital_p)
    place(sts, {p: dict(v, zone="white" if v["state"] in IMPASSABLE else v["zone"]) for p, v in prov.items()},
          newpid, land, m, set(sts) | set(old), port, CAPITAL, rng)
    fprov = set(prov)
    blocked = {p for p, v in prov.items() if v["state"] in IMPASSABLE}
    ohn = [p for p, v in prov.items() if OWNER.get(v["state"]) == OHN]
    for f in glob.glob("history/units/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        if any(int(x) in fprov for x in re.findall(r"naval_base\s*=\s*(\d+)", s)):   # fleets: to the pirates' port
            rw(f, lambda s_: re.sub(r"\b(naval_base|location)(\s*=\s*)(\d+)\b",
                                    lambda q: q.group(1) + q.group(2) + (str(port) if int(q.group(3)) in fprov else q.group(3)), s_))
        elif any(int(x) in fprov for x in re.findall(r"\blocation\s*=\s*(\d+)", s)):  # armies: back on their own ground
            mine = ohn if "OHN" in os.path.basename(f) else [p for p in fprov if p not in blocked and p not in ohn]
            rw(f, lambda s_: re.sub(r"\blocation(\s*=\s*)(\d+)\b",
                                    lambda q: "location" + q.group(1) + (str(mine[int(q.group(2)) % len(mine)])
                                                                         if int(q.group(2)) in fprov else q.group(2)), s_))

    pcom.state_names_loc(STATE_NAMES)

    def fv(s):
        s = re.sub(r'\n ?VICTORY_POINTS_(\d+):\d* "[^"]*"', lambda q: "" if int(q.group(1)) in fprov else q.group(0), s)
        return s.rstrip("\n") + "\n" + "".join(f' VICTORY_POINTS_{p}:0 "{n}"\n' for p, n in vp_names.items())
    rw("localisation/english/victory_points_l_english.yml", fv)
    for sid, st in sorted(sts.items()):
        print(f"{sid:5} {OWNER.get(sid, CMG) if sid not in IMPASSABLE else '---'} {st['kind']:5} {len(st['provinces']):3} "
              f"provinces  {STATE_NAMES[sid]}")
    return vp_names


if __name__ == "__main__":
    pcom.run(main)
