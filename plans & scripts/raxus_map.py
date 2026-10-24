"""Raxus Secundus ("Raxus" in game), the Confederacy's capital world, as one battlefield: a pastoral world of meadows,
farms, golden woods and villages among scattered mountains, and its capital Raxulon. At the heart of Raxulon the
Separatist Senate curves round the north side of the Senate Plaza in one long arc, its wings stepping down to the
plaza, more halls and towers behind them, a grove of tall trees in the middle of the plaza (Wookieepedia; The Clone
Wars / The Bad Batch stills, Presley's concept art). From the plaza the Great Alley, lined with golden trees and
Confederate banners, runs straight south to the city's edge.

    python "WIPGFX/plans & scripts/raxus_map.py"     provinces.bmp, definition.csv, states, names, map positions

Zones (kind in raxus_zones.png):
  1 senate    the Senate building: impassable scenery (ROOMS)        5 plaza    the Senate Plaza, one province
  2 city      Raxulon's blocks; borders run along its streets         6 alley    the Great Alley (a chain of provinces)
  3 street    city streets (terrain only, inside city provinces)      7 massif   scattered mountains (impassable)
  4 country   meadows, farms, woods, downs and villages               9 lake     Lake Serenea (impassable)
The planet keeps its province ids and colours (strategic region unchanged); only the pixels move, as on Felucia.
Impassable land gets states of its own (IMPASSABLE). Fleets based on Raxus move to its main naval base; land units
standing on what became impassable move to the Senate Plaza.
Run order: raxus_map.py -> planet_terrain_gen.py --raxus -> --globe-texture -> military_buildings.py landmarks.
"""
import csv, glob, json, math, os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from felucia_map import split_area, split_line
from felucia_tribes import block, place, rw

PLANET = "Raxus"
ZONES_JSON = "WIPGFX/Assets/raxus_zones.json"
ZONES_PNG = "WIPGFX/Assets/raxus_zones.png"
# map px from the planet's centre (the planet is ~60 px in radius); angles in degrees, 0 = east, counter-clockwise
PLAZA_R = 9.5                         # the plaza fills the centre and the half-disc south of it
ARC, BACK = (5.5, 10.5), (10.5, 15.0) # the Senate: the curved front range on the plaza, the halls behind it
ALLEY_W = 3.0                         # half-width of the Great Alley
ALLEY_LEN = 7                         # px of alley per province
CITY_R = (30.0, 2.0)                  # city edge: radius, how much it wanders
STREETS, STREET_ROT, STREET_W = 6, 30.0, 0.8   # radial streets (one runs along the Great Alley) + a ring road
LAKE = (205.0, 47.0, 5.0)             # angle, distance, radius
MASSIFS = 5                           # scattered mountains in the countryside, each its own impassable state
MASSIF_R = (3.2, 4.5)                 # each massif is a ridge of 3 overlapping knots of this radius (px)
LONE_PEAKS = 9                        # passable mountains: countryside provinces that rise into a single peak
MASSIF_GAP = 15.0                     # min distance between massif / lake centres
VILLAGES = 14                         # villages in the countryside (terrain + city models; planet_terrain_gen.py)
DENSITY = {"city": 1.7, "country": 0.7}
SEED = 79
# the Senate building (sector in degrees, radial band): just a building, impassable; the fighting is for the plaza
ROOMS = [("Senate front range", (10, 170), ARC), ("Senate halls", (35, 145), BACK)]
SENATE = 1136
CAPITAL = 79
# victory point names from Wookieepedia where it has them (Raxus Secundus, Raxulon: the Bonteri house, the main
# port, the spaceport, the plaza square; Tamwith Bay, a city some distance from the capital); the rest are ours
CITY_STATES = {706: ("Delegates' Quarter", "Bonteri House"), 707: ("Merchants' Quarter", "Raxulon Main Port"),
               708: ("Old Raxulon", "Raxulon Spaceport")}       # outer city, two street sectors each
COUNTRY_STATES = {709: ("Aranth Meadows", "Aranth"), 710: ("Velloran Vales", "Vellora"),
                  711: ("Tamwith Bay", "Tamwith Bay"), 712: ("Halvenmoor Downs", "Halvenmoor")}   # N W S E quadrants
IMPASSABLE = {1130: "Mount Aranth", 1131: "The Velloran Spires", 1132: "Serrin Heights", 1133: "Halvenmoor Fells",
              1134: "Kessendra Massif", 1135: "Lake Serenea", SENATE: "Separatist Senate"}   # massifs, lake, Senate
COUNTRY_TERRAIN = [(0.5, "plains"), (0.78, "forest"), (1.0, "hills")]   # by smooth noise at the province centre
FOOTHILLS = (3.0, 7.0)                # province centre this close to a massif (px): mountain, then hills
NAVY_FILES = ["history/units/HOD_CIS_naval.txt"]


def raxus_mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    m = np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])
    return land, pid, m


def geometry(m):
    """centre, radius, and per pixel: distance from the centre and angle"""
    ys, xs = np.nonzero(m)
    cy, cx = ys.mean(), xs.mean()
    R = math.sqrt(m.sum() / math.pi)
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]].astype(np.float32)
    r = np.hypot(yy - cy, xx - cx)
    a = np.degrees(np.arctan2(-(yy - cy), xx - cx)) % 360
    return cy, cx, R, r, a, yy, xx


def wander(a, amp, rng):
    """smooth periodic wobble over the angle (degrees), +-amp"""
    out = np.zeros_like(a)
    for k, w in ((2, 0.5), (3, 0.3), (5, 0.2)):
        out += w * np.sin(np.radians(a) * k + rng.uniform(0, 2 * np.pi))
    return out * amp


def in_sector(a, lo, hi):
    return ((a - lo) % 360) < ((hi - lo) % 360 or 360)


def blob(yy, xx, fy, fx, rad, rng):
    return np.hypot(yy - fy, xx - fx) < rad * (1 + 0.3 * wander(np.degrees(np.arctan2(yy - fy, xx - fx)) % 360, 1, rng))


def zones(m, rng):
    """kind per pixel and the groups provinces are cut from: name -> dict(kind, zone, state, mask, n or None)"""
    cy, cx, R, r, a, yy, xx = geometry(m)
    city_r = CITY_R[0] + wander(a, CITY_R[1], rng)
    south = yy > cy
    groups = {}

    def add(name, kind, zone, state, mask, n=None):
        mask = mask & m & ~taken
        taken[...] |= mask
        groups[name] = dict(kind=kind, zone=zone, state=state, mask=mask, n=n)

    taken = np.zeros(m.shape, bool)
    for i, (room, (lo, hi), (b0, b1)) in enumerate(ROOMS):
        add(f"room{i}", 1, "white", SENATE, (r >= b0) & (r < b1) & in_sector(a, lo, hi), 1)
    add("plaza", 5, "plaza", CAPITAL, r < PLAZA_R, 1)
    add("alley", 6, "corridor", CAPITAL, south & (np.abs(xx - cx) <= ALLEY_W) & (r < city_r), None)
    # the lake and the massifs, scattered over the countryside away from the city and the coast
    ly, lx = cy - LAKE[1] * math.sin(math.radians(LAKE[0])), cx + LAKE[1] * math.cos(math.radians(LAKE[0]))
    feats = [(1135, (ly, lx), LAKE[2], 9)]
    while len(feats) < MASSIFS + 1:
        ang, dist = rng.uniform(0, 360), rng.uniform(CITY_R[0] + 9, R - 8)
        fy, fx = cy - dist * math.sin(math.radians(ang)), cx + dist * math.cos(math.radians(ang))
        if all(math.hypot(fy - c[0], fx - c[1]) >= MASSIF_GAP for _s, c, _r, _k in feats):
            feats.append((list(IMPASSABLE)[len(feats) - 1], (fy, fx), rng.uniform(*MASSIF_R), 7))
    for sid, (fy, fx), rad, kind in feats:
        shape = blob(yy, xx, fy, fx, rad, rng)
        if kind == 7:                                              # a ridge: knots strung along a random heading
            hd = rng.uniform(0, math.pi)
            for k in (-1, 1):
                d = rad * rng.uniform(1.1, 1.5)
                shape |= blob(yy, xx, fy + k * d * math.sin(hd), fx + k * d * math.cos(hd), rad * rng.uniform(0.7, 0.95), rng)
        add(f"feat{sid}", kind, "white", sid, shape & (r >= city_r + 3), 1 if kind == 9 else 2)
    # city: two rings of blocks between the street sectors; the countryside: quadrants
    ring_r = 0.5 * (BACK[1] + CITY_R[0])
    sector = (((a - STREET_ROT) % 360) // (360 / STREETS)).astype(int)
    city = r < city_r
    outer_state = [s for s in CITY_STATES for _ in range(STREETS // len(CITY_STATES))]
    for s in range(STREETS):
        add(f"inner{s}", 2, "city", CAPITAL, city & (r < ring_r) & (sector == s))
        add(f"outer{s}", 2, "city", outer_state[s], city & (r >= ring_r) & (sector == s))
    quad = (((a - 45) % 360) // 90).astype(int)
    for q, sid in enumerate(COUNTRY_STATES):
        add(f"country{q}", 4, "country", sid, quad == q)
    assert not (m & ~taken).any(), "every pixel in a group"
    kind = np.zeros(m.shape, np.uint8)
    for gname, gr in groups.items():
        kind[gr["mask"]] = gr["kind"]
    ang_d = np.minimum((a - STREET_ROT) % (360 / STREETS), 360 / STREETS - (a - STREET_ROT) % (360 / STREETS))
    street = (np.radians(ang_d) * r < STREET_W) | (np.abs(r - ring_r) < STREET_W)
    kind[(kind == 2) & street] = 3
    return kind, groups, (cy, cx, R)


def mend(newpid, m, prov):
    """Stray pieces of a province (its group cut apart by the alley or the Senate) join the neighbour they share
    the longest border with, one of the same state if there is one: every province in one piece."""
    for p in list(prov):
        lab, n = ndi.label(newpid == p)
        if n < 2:
            continue
        keep = np.argmax(np.bincount(lab.ravel())[1:]) + 1
        for i in range(1, n + 1):
            if i == keep:
                continue
            frag = lab == i
            ring = ndi.binary_dilation(frag) & ~frag & m & (newpid != p)
            nb = np.bincount(newpid[ring])
            same = [q for q in np.nonzero(nb)[0] if prov.get(int(q), {}).get("state") == prov[p]["state"]]
            newpid[frag] = max(same, key=lambda q: nb[q]) if same else nb.argmax()
    for p in prov:
        assert ndi.label(newpid == p)[1] == 1, f"province {p} still in pieces"

def main():
    import planet_terrain_gen as g
    land, pid, m = raxus_mask()
    ids = sorted(np.unique(pid[m]).tolist())
    rng = np.random.default_rng(SEED)
    kind, groups, (cy, cx, R) = zones(m, rng)
    # provinces per group: fixed counts, chains by length, the rest by area x density
    for gr in groups.values():
        if gr["n"] is None and gr["kind"] == 6:
            ys, xs = np.nonzero(gr["mask"])
            gr["n"] = max(1, round(math.hypot(np.ptp(ys), np.ptp(xs)) / ALLEY_LEN))
    fixed = sum(gr["n"] for gr in groups.values() if gr["n"])
    free = {k: gr for k, gr in groups.items() if not gr["n"]}
    rest = len(ids) - fixed
    w = {k: gr["mask"].sum() * DENSITY[gr["zone"]] for k, gr in free.items()}
    raw = {k: rest * w[k] / sum(w.values()) for k in w}
    for k in w:
        free[k]["n"] = max(1, int(raw[k]))
    for k in sorted(w, key=lambda k: raw[k] - int(raw[k]), reverse=True)[:rest - sum(free[k]["n"] for k in w)]:
        free[k]["n"] += 1
    assert sum(gr["n"] for gr in groups.values()) == len(ids), (sum(gr["n"] for gr in groups.values()), len(ids))
    newpid = pid.copy()
    it = iter(ids)
    prov = {}
    for k, gr in groups.items():
        gm = gr["mask"]
        part = split_line(gm, gr["n"]) if gr["kind"] == 6 else split_area(gm, gr["n"], rng)
        ys, xs = np.nonzero(gm)
        for i in range(gr["n"]):
            p = next(it)
            newpid[ys[part == i], xs[part == i]] = p
            prov[p] = dict(zone=gr["zone"], kind=int(gr["kind"]), state=gr["state"], group=k)
    mend(newpid, m, prov)
    assert not (set(np.unique(newpid[m]).tolist()) ^ set(ids)), "every id keeps pixels"
    rows = {int(r[0]): r for r in csv.reader(open("map/definition.csv", encoding="utf-8-sig"), delimiter=";") if r and r[0].isdigit()}
    bmp = np.array(Image.open("map/provinces.bmp").convert("RGB"))
    ys, xs = np.nonzero(m)
    bmp[ys, xs] = np.array([[int(rows[p][1]), int(rows[p][2]), int(rows[p][3])] for p in newpid[ys, xs]], np.uint8)
    Image.fromarray(bmp, "RGB").save("map/provinces.bmp")
    # definition.csv: coastal (touching space) and terrain
    sea = np.isin(pid, [i for i, r in rows.items() if r[4] == "sea"])
    field = g.noise(m.shape, 14, np.random.default_rng(SEED + 1), 3)
    lo, hi = np.percentile(field[m], (1, 99))
    by_kind = {1: "urban", 2: "urban", 5: "urban", 6: "urban", 7: "mountain", 9: "marsh"}
    to_massif = ndi.distance_transform_edt(kind != 7)
    for p, v in prov.items():
        pm = newpid == p
        ring = ndi.binary_dilation(pm) & ~pm
        v["coastal"] = bool((ring & sea).any())
        v["sea"] = int(np.bincount(pid[ring & sea]).argmax()) if v["coastal"] else 0
        pcy, pcx = ndi.center_of_mass(pm)
        v["centre"] = [float(pcy), float(pcx)]
        if v["kind"] == 4:
            f = np.clip((field[int(pcy), int(pcx)] - lo) / (hi - lo), 0, 1)
            v["terrain"] = next(t for lim, t in COUNTRY_TERRAIN if f <= lim)
            near = to_massif[int(pcy), int(pcx)]                  # foothills round the massifs
            if near < FOOTHILLS[1]:
                v["terrain"] = "mountain" if near < FOOTHILLS[0] else "hills"
        else:
            v["terrain"] = by_kind[v["kind"]]
    for i, (room, *_r) in enumerate(ROOMS):
        prov[next(p for p, v in prov.items() if v["group"] == f"room{i}")]["room"] = room
    # lone peaks: passable mountains scattered over the countryside (planet_terrain_gen.py raises them)
    peaks = []
    for p in rng.permutation([p for p, v in prov.items() if v["kind"] == 4 and v["terrain"] != "mountain"]):
        c = np.array(prov[int(p)]["centre"])
        if (math.hypot(c[0] - cy, c[1] - cx) > CITY_R[0] + 5 and to_massif[int(c[0]), int(c[1])] > 9
                and all(np.hypot(*(c - prov[q]["centre"])) > 11 for q in peaks)):
            peaks.append(int(p))
            prov[int(p)].update(terrain="mountain", peak=True)
        if len(peaks) == LONE_PEAKS:
            break
    path = "map/definition.csv"
    raw_txt = open(path, "rb").read()
    out = []
    for line in raw_txt.decode("utf-8-sig").splitlines(keepends=True):
        body, end = line.rstrip("\r\n"), line[len(line.rstrip("\r\n")):]
        q = body.split(";")
        if len(q) >= 7 and q[0].isdigit() and int(q[0]) in prov:
            q[5] = "true" if prov[int(q[0])]["coastal"] else "false"
            q[6] = prov[int(q[0])]["terrain"]
        out.append(";".join(q) + end)
    open(path, "wb").write((b"\xef\xbb\xbf" if raw_txt.startswith(b"\xef\xbb\xbf") else b"") + "".join(out).encode("utf-8"))
    os.makedirs(os.path.dirname(ZONES_JSON), exist_ok=True)
    # villages: spread over the open countryside, away from the city, the massifs and each other
    villages = []
    cand = [p for p, v in prov.items() if v["kind"] == 4 and v["terrain"] in ("plains", "hills")]
    for p in rng.permutation(cand):
        c = np.array(prov[int(p)]["centre"])
        if math.hypot(c[0] - cy, c[1] - cx) > CITY_R[0] + 5 and all(np.hypot(*(c - prov[q]["centre"])) > 9 for q in villages):
            villages.append(int(p))
        if len(villages) == VILLAGES:
            break
    json.dump({"centre": [cy, cx], "radius": R, "plaza_r": PLAZA_R, "arc": ARC, "back": BACK, "villages": villages,
               "provinces": {str(p): v for p, v in prov.items()}}, open(ZONES_JSON, "w"), indent=1)
    Image.fromarray(kind).save(ZONES_PNG)
    states(prov, land, m, newpid, rng)


def states(prov, land, m, newpid, rng):
    """state files (provinces, victory points, names), keeping each state's resources, industry and manpower;
    impassable states for the massifs and the lake; then every map position (felucia_tribes.place)"""
    all_ids = [CAPITAL, *CITY_STATES, *COUNTRY_STATES, *IMPASSABLE]
    old = {}
    for f in glob.glob("history/states/*.txt"):
        sid = int(re.search(r"\bid\s*=\s*(\d+)", open(f, encoding="utf-8-sig").read()).group(1))
        if sid in all_ids:
            old[sid] = f
    by_state = {}
    for p, v in prov.items():
        by_state.setdefault(v["state"], []).append(p)
    pc = lambda p: np.array(prov[p]["centre"])
    of = lambda group: [p for p, v in prov.items() if v["group"] == group]
    names = {CAPITAL: "Raxulon", **{s: n for s, (n, _) in CITY_STATES.items()},
             **{s: n for s, (n, _) in COUNTRY_STATES.items()}, **IMPASSABLE}
    vp_names, sts = {}, {}
    plaza = of("plaza")[0]
    cy, cx = np.mean([v["centre"] for v in prov.values()], 0)
    gate = max(of("alley"), key=lambda p: np.hypot(prov[p]["centre"][0] - cy, prov[p]["centre"][1] - cx))
    # naval bases and dockyards need the coast: the city's go to the countryside's coastal states
    moved_docks, moved_naval = 0, []
    for sid in [CAPITAL, *CITY_STATES]:
        b = block(block(open(old[sid], encoding="utf-8-sig").read(), "history"), "buildings")
        moved_docks += sum(int(x) for x in re.findall(r"\bdockyard\s*=\s*(\d+)", b))
        moved_naval += [int(x) for x in re.findall(r"naval_base\s*=\s*(\d+)", b)]
    ports = {}
    for sid, provs in sorted(by_state.items()):
        provs = sorted(provs)
        src = open(old[sid], encoding="utf-8-sig").read() if sid in old else ""
        res = block(src, "resources") or "\n\tresources={\n\t}"
        bld = block(block(src, "history"), "buildings") or "\n\t\tbuildings = {\n\t\t\tinfrastructure = 3\n\t\t}"
        naval = [int(x) for x in re.findall(r"naval_base\s*=\s*(\d+)", bld)]
        bld = re.sub(r"\n\s*\d+\s*=\s*\{[^{}]*\}", "", bld)                    # province buildings (ports) go
        open_p = [p for p in provs if prov[p]["zone"] != "corridor"] or provs
        cen = np.mean([pc(p) for p in open_p], 0)
        main_p = min(open_p, key=lambda p: np.hypot(*(pc(p) - cen)))
        coastal = [p for p in provs if prov[p]["coastal"]]
        man = re.search(r"manpower\s*=\s*(\d+)", src).group(1) if src else "3000"
        cat = re.search(r"state_category\s*=\s*(\w+)", src).group(1) if src else "wasteland_sector"
        imp = ""
        if sid == CAPITAL:
            main_p = plaza
            vps = [(plaza, 10), (gate, 3)]
            vp_names.update({plaza: "Raxulon Plaza Square", gate: "Raxulon City Gate"})
            bld = re.sub(r"\n\s*dockyard\s*=\s*\d+", "", bld)
        elif sid in CITY_STATES:
            vps = [(main_p, 3)]
            vp_names[main_p] = CITY_STATES[sid][1]
            bld = re.sub(r"\n\s*dockyard\s*=\s*\d+", "", bld)
        elif sid in COUNTRY_STATES:
            vps = [(main_p, 3)]
            vp_names[main_p] = COUNTRY_STATES[sid][1]
            k = list(COUNTRY_STATES).index(sid)
            extra = moved_docks // len(COUNTRY_STATES) + (k < moved_docks % len(COUNTRY_STATES))
            if extra:
                d = re.search(r"\bdockyard\s*=\s*(\d+)", bld)
                bld = (bld.replace(d.group(0), f"dockyard = {int(d.group(1)) + extra}") if d else
                       bld.rstrip().rstrip("}") + f"\tdockyard = {extra}\n\t\t}}")
            lv = naval + moved_naval[k:k + 1]
            if lv and coastal:
                port = max(coastal, key=lambda p: -np.hypot(*(pc(p) - cen)))
                ports[port] = max(lv)
                bld = bld.rstrip().rstrip("}") + f"\t\t\t{port} = {{\n\t\t\t\tnaval_base = {max(lv)}\n\t\t\t}}\n\t\t}}"
        else:                                                     # peaks, lake, crags
            vps = []
            imp = f"\timpassable = yes\n\tforce_link_ownership_to = {CAPITAL}\n"
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            res, man, cat = "\n\tresources={\n\t}", "3000", "wasteland_sector"
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {v}\n\t\t}}\n" for p, v in vps)
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: Raxus, {prov[provs[0]]['zone']} (raxus_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = CIS\n\t\tadd_core_of = CIS\n\t}}\n"
                f"\tmanpower = {man}\n\tstate_category = {cat}\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}}\n")
        if sid in old:
            os.remove(old[sid])
        open(f"history/states/{sid}-Raxus - {names[sid].replace(chr(39), '')}.txt", "w", encoding="utf-8",
             newline="\n").write(text)
        kind = "white" if sid in IMPASSABLE else prov[provs[0]]["zone"]
        sts[sid] = dict(kind=kind, provinces=provs, coastal=coastal, main=main_p)
    place(sts, prov, newpid, land, m, set(sts), plaza, CAPITAL, rng)                 # airport on the plaza
    fprov = set(prov)
    # units: fleets to the main naval base, land units off impassable ground to the plaza
    main_port = max(ports, key=ports.get)
    blocked = {p for p, v in prov.items() if v["zone"] == "white"}
    for f in NAVY_FILES:
        rw(f, lambda s: re.sub(r"\b(naval_base|location)(\s*=\s*)(\d+)\b",
                               lambda q: q.group(1) + q.group(2) + (str(main_port) if int(q.group(3)) in fprov else q.group(3)), s))
    for f in glob.glob("history/units/*.txt"):
        if f.replace("\\", "/") not in NAVY_FILES:
            rw(f, lambda s: re.sub(r"\blocation(\s*=\s*)(\d+)\b",
                                   lambda q: "location" + q.group(1) + (str(plaza) if int(q.group(2)) in blocked else q.group(2)), s))

    def fs(s):
        for sid in names:
            s = re.sub(rf'\n STATE_{sid}:\d* "[^"]*"', "", s)
        return s.rstrip("\n") + "\n" + "".join(f' STATE_{sid}:0 "{n}"\n' for sid, n in sorted(names.items()))
    rw("localisation/english/state_names_l_english.yml", fs)

    def fv(s):
        s = re.sub(r'\n VICTORY_POINTS_(\d+):\d* "[^"]*"', lambda q: "" if int(q.group(1)) in fprov else q.group(0), s)
        return s.rstrip("\n") + "\n" + "".join(f' VICTORY_POINTS_{p}:0 "{n}"\n' for p, n in vp_names.items())
    rw("localisation/english/victory_points_l_english.yml", fv)
    for sid, st in sorted(sts.items()):
        print(f"{sid:5} {st['kind']:8} {len(st['provinces']):3} provinces  {names[sid]}")
    print("main naval base", main_port, ports)


if __name__ == "__main__":
    main()
