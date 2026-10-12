"""Raxus Prime, the junk world next to Raxus Secundus, as one battlefield: plains of scrap metal under heaps and
mountains of junk, towns built out of scrap, a toxic mire, and the half-buried, broken hulks of old warships
(Wookieepedia: "a planet covered in junk", the galaxy's scrapyard, Jawa scavengers and the great scrap-processing
works). At its centre stands the Scrap Processing Plant, just scenery like Raxulon's Senate (impassable), ringed by
the junk town of the capital.

    python "WIPGFX/plans & scripts/raxus_prime_map.py"     provinces.bmp, definition.csv, states, names, positions,
                                                           wreck and landmark placement (map/ambient_object.txt)

Zones (kind in raxus_prime_zones.png): 1 plant (impassable), 2 capital junk town, 4 scrap plains, 7 scrap mountains
(impassable), 9 toxic mire (impassable). Towns (city style 12) and wreck sites are recorded in raxus_prime_zones.json.
The planet keeps its province ids and colours, as on Raxus and Felucia.
Run order: raxus_prime_map.py -> planet_terrain_gen.py --raxus-prime -> --globe-texture.
"""
import csv, glob, json, math, os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from felucia_map import split_area
from felucia_tribes import block, place, rw
from raxus_map import geometry, mend

PLANET = "Raxus Prime"
ZONES_JSON = "WIPGFX/Assets/raxus_prime_zones.json"
ZONES_PNG = "WIPGFX/Assets/raxus_prime_zones.png"
PLANT_R, TOWN_R = 4.5, 10.0          # the plant's footprint and the capital junk town round it (px)
TOWN_AT = (45.0, 12.0)               # the capital off the planet's centre: angle (degrees, toward the top right), px
SPRAWL = (0.35, 1.2)                 # passageways the city sprawls along: share of side branches, half-width (px)
TOWN_PROVINCES = 5
# the maze: yards on a grid (px) warped by noise, walls between them (half-width px each side of a grid line), a share
# of extra openings on top of the spanning tree, yards smaller than this many px dropped into the walls
MAZE_CELL, MAZE_WALL, MAZE_WARP, MAZE_LOOPS, MAZE_MIN_CELL = 8.0, 1.0, 2.5, 0.3, 8
UPPER = 0.35                         # share of yards raised onto the upper level of junk plateau
BLOCKS = [(1141, 9), (1138, 7), (1142, 7)]   # whole yards made the toxic pools / junk mountains (impassable)
WALL_STATES, WALL_PROVINCES = [1139, 1140], 3  # the maze's walls: impassable strips, by sector
SEED = 196
CAPITAL = 196
# names from Wookieepedia where it has them (Raxus Prime/Legends: Central Station the capital, Dooku's
# headquarters, the Sienar Refinery, the Raxus Sewer System, the Core (the planet-wide intelligence), the Meeknu clan
# of Jawas who run the heavy machinery, Nikato's Bootheel and its clockwork mechanisms, toxic waste pools); the
# rest are ours
OUTER = {1052: ("The Boneyard", "Boneyard"), 1053: ("Hammerhead Reach", "Hammerhead Wreck"),
         1054: ("Nikato's Bootheel", "Nikato's Bootheel"), 1055: ("Rust Wastes", "Rustwater"),
         1056: ("Jawa Trade Rows", "Meeknu Clan Holdings"), 1057: ("Droid Foundry Sector", "The Core"),
         1058: ("Sludgewater", "Raxus Sewer System")}   # sectors, from east
IMPASSABLE = {1137: "Sienar Refinery", 1138: "Scrapheap Mountains", 1139: "The Girder Walls", 1140: "The Hulk Walls",
              1141: "Toxic Waste Pools", 1142: "The Slag Heaps"}
# big wrecks and landmarks (sketchfab_props.py meshes, gfx/models/buildings/hod_sw): sector of OUTER they lie in,
# offsets of the pieces from the site's centre (px), yaw (degrees)
WRECKS = {"The Boneyard": [("hod_bld_rp_derriphan_bow", (-2.5, 1.0), 25), ("hod_bld_rp_derriphan_stern", (3.0, -1.5), 200)],
          "Hammerhead Reach": [("hod_bld_rp_hammerhead_bow", (-1.8, -1.2), 300), ("hod_bld_rp_hammerhead_stern", (2.2, 1.0), 140)],
          "Rust Wastes": [("hod_bld_rp_lethisk", (0, 0), 70)],
          "Droid Foundry Sector": [("hod_bld_rp_droidworks", (0, 0), 0)]}
PLANT_MESH = "hod_bld_rp_factory"
AMBIENT_MARK = ("# HOD: Raxus Prime wrecks and works (raxus_prime_map.py)", "# HOD: end of Raxus Prime wrecks")
NAVY_FILES = ["history/units/HOD_CIS_naval.txt"]


def mask():
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    return land, pid, np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == PLANET])


def maze(m, cy, cx, rng, town):
    """The dump's labyrinth: a grid of yards warped by noise into organic shapes, carved like a maze (randomised
    depth-first spanning tree, then a share of extra openings so it has loops), the walls between yards left standing.
    -> yard label per pixel (0 = none), wall mask, yard adjacency through openings"""
    import planet_terrain_gen as g
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min() - 3, ys.max() + 4, xs.min() - 3, xs.max() + 4
    sh = (y1 - y0, x1 - x0)
    wy = (g.noise(sh, 9, rng, 2) - 0.5) * 2 * MAZE_WARP
    wx = (g.noise(sh, 9, rng, 2) - 0.5) * 2 * MAZE_WARP
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    u, v = (yy - cy + wy) / MAZE_CELL + 0.5, (xx - cx + wx) / MAZE_CELL + 0.5
    ci, cj = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - ci, v - cj
    w = MAZE_WALL / MAZE_CELL
    near_u, near_v = (fu < w) | (fu > 1 - w), (fv < w) | (fv > 1 - w)
    sub = m[y0:y1, x0:x1]
    r = np.hypot(yy - town[0], xx - town[1])                          # distance from the capital's centre
    out = sub & (r >= TOWN_R + 1.0)                                      # the maze lies outside the capital's town
    inner = out & ~near_u & ~near_v
    cells = {}
    for c, n in zip(*np.unique(np.stack([ci[inner], cj[inner]], 1), axis=0, return_counts=True)):
        if n >= MAZE_MIN_CELL:
            cells[tuple(c)] = n
    nb = lambda c: [(c[0] + dy, c[1] + dx) for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (c[0] + dy, c[1] + dx) in cells]
    # spanning tree from a random cell, then extra openings
    start = list(cells)[rng.integers(len(cells))]
    seen, stack, opened = {start}, [start], set()
    while stack:
        c = stack[-1]
        free = [d for d in nb(c) if d not in seen]
        if not free:
            stack.pop()
            continue
        d = free[rng.integers(len(free))]
        opened.add(frozenset((c, d)))
        seen.add(d)
        stack.append(d)
    for c in cells:
        for d in nb(c):
            if frozenset((c, d)) not in opened and rng.random() < MAZE_LOOPS / 2:
                opened.add(frozenset((c, d)))
    # pixels: yard interiors, opened boundaries joined to the nearer yard, the rest of the grid lines are wall
    lab = np.zeros(sh, np.int32)
    index = {c: k + 1 for k, c in enumerate(cells)}
    key = ci * 100000 + cj
    for c, k in index.items():
        lab[inner & (key == c[0] * 100000 + c[1])] = k
    for pair in opened:
        a, b = sorted(pair)
        if a[0] != b[0]:                                                 # vertical neighbours: a above b
            sel = out & ~near_v & (((ci == a[0]) & (cj == a[1]) & (fu > 1 - w)) | ((ci == b[0]) & (cj == b[1]) & (fu < w)))
            lab[sel & (ci == a[0])], lab[sel & (ci == b[0])] = index[a], index[b]
        else:
            sel = out & ~near_u & (((ci == a[0]) & (cj == a[1]) & (fv > 1 - w)) | ((ci == b[0]) & (cj == b[1]) & (fv < w)))
            lab[sel & (cj == a[1])], lab[sel & (cj == b[1])] = index[a], index[b]
    wall = out & (lab == 0)
    # a street round the capital's town: the ring just outside it joins the nearest yard, open on every side
    ring = sub & (r >= TOWN_R) & (r < TOWN_R + 1.0)
    if (lab > 0).any():
        _, (iy, ix) = ndi.distance_transform_edt(lab == 0, return_indices=True)
        lab[ring] = lab[iy, ix][ring]
        stray = wall & (ndi.distance_transform_edt(~(lab > 0)) > MAZE_WALL * 2.5)   # wall pieces cut off at the coast
        lab[stray] = lab[iy, ix][stray]
        wall &= ~stray
    full_lab = np.zeros(m.shape, np.int32)
    full_wall = np.zeros(m.shape, bool)
    full_lab[y0:y1, x0:x1], full_wall[y0:y1, x0:x1] = lab, wall
    links = {(index[min(p)], index[max(p)]) for p in opened}
    return full_lab, full_wall, links


def zones(m, rng):
    """kind per pixel and groups: name -> dict(kind, zone, state, mask, n or part (label image -> provinces))"""
    cy, cx, R, r, a, yy, xx = geometry(m)
    groups, taken = {}, np.zeros(m.shape, bool)

    def add(name, kind, zone, state, msk, n=None, part=None):
        msk = msk & m & ~taken
        taken[...] |= msk
        groups[name] = dict(kind=kind, zone=zone, state=state, mask=msk, n=n, part=part)

    ty = cy - TOWN_AT[1] * math.sin(math.radians(TOWN_AT[0]))
    tx = cx + TOWN_AT[1] * math.cos(math.radians(TOWN_AT[0]))
    rt = np.hypot(yy - ty, xx - tx)
    add("plant", 1, "white", 1137, rt < PLANT_R, 1)
    add("town", 2, "town", CAPITAL, rt < TOWN_R, TOWN_PROVINCES)
    lab, wall, links = maze(m, cy, cx, rng, (ty, tx))
    yards = [k for k in np.unique(lab[lab > 0])]
    cen = {k: ndi.center_of_mass(lab == k) for k in yards}
    rad = {k: math.hypot(cen[k][0] - cy, cen[k][1] - cx) for k in yards}
    rad_t = {k: math.hypot(cen[k][0] - ty, cen[k][1] - tx) for k in yards}
    # whole yards turned into junk mountains and the toxic pools (impassable), away from the town and each other
    picks, order = [], sorted(yards, key=lambda k: rng.random())
    for gap in (2.2, 1.6, 1.1):                      # spacing relaxed until every block has a yard
        for k in order:
            if len(picks) == len(BLOCKS):
                break
            if k not in picks and TOWN_R + 9 < rad_t[k] and rad[k] < R - MAZE_CELL and                     all(math.hypot(cen[k][0] - cen[q][0], cen[k][1] - cen[q][1]) > gap * MAZE_CELL for q in picks):
                picks.append(k)
    assert len(picks) == len(BLOCKS), "no room for the scrap mountains and the pools"
    for k, (sid, kind) in zip(picks, BLOCKS):
        add(f"block{sid}", kind, "white", sid, lab == k, 1)
    # the walls: impassable strips, a few provinces per state by sector
    wsec = (((a - 30) % 360) // (360 / len(WALL_STATES))).astype(int)
    for i, sid in enumerate(WALL_STATES):
        add(f"wall{sid}", 5, "white", sid, wall & (wsec == i), WALL_PROVINCES)
    # yards: one province each (merged or split to fit the planet's ids later), state by the sector they lie in
    ysec = {k: int(((math.degrees(math.atan2(-(cen[k][0] - cy), cen[k][1] - cx)) % 360) // (360 / len(OUTER)))) for k in yards}
    for i, sid in enumerate(OUTER):
        sel = [k for k in yards if k not in picks and ysec[k] == i]
        part = np.where(np.isin(lab, sel), lab, 0)
        add(f"yards{sid}", 4, "plains", sid, part > 0, part=part)
    leftover = m & ~taken                                               # stray pixels: nearest group
    if leftover.any():
        owner = np.zeros(m.shape, np.int32)
        names = list(groups)
        for k, gname in enumerate(names):
            owner[groups[gname]["mask"]] = k + 1
        _, (iy, ix) = ndi.distance_transform_edt(owner == 0, return_indices=True)
        for k, gname in enumerate(names):
            sel = leftover & (owner[iy, ix] == k + 1)
            gr = groups[gname]
            gr["mask"] |= sel
            if gr["part"] is not None:
                _, (jy, jx) = ndi.distance_transform_edt(gr["part"] == 0, return_indices=True)
                gr["part"][sel] = gr["part"][jy, jx][sel]
    kind = np.zeros(m.shape, np.uint8)
    for gr in groups.values():
        kind[gr["mask"]] = gr["kind"]
    return kind, groups, (cy, cx, R), links, lab, (ty, tx)


def fit_yards(groups, n_free, links, rng):
    """Yard provinces: merge the smallest yard into an open neighbour, or split the biggest, until they fill the ids
    left. Returns {group: [pixel masks]}"""
    pieces = {}
    for gname, gr in groups.items():
        if gr["part"] is not None:
            pieces[gname] = [gr["part"] == k for k in np.unique(gr["part"][gr["part"] > 0])]
    count = lambda: sum(len(v) for v in pieces.values())
    while count() > n_free:
        for gname, i in sorted(((g_, i_) for g_, v in pieces.items() for i_ in range(len(v)) if len(v) > 1),
                               key=lambda t: pieces[t[0]][t[1]].sum()):
            ring = ndi.binary_dilation(pieces[gname][i]) & ~pieces[gname][i]
            touch = [j_ for j_ in range(len(pieces[gname])) if j_ != i and (ring & pieces[gname][j_]).any()]
            if touch:
                j = max(touch, key=lambda j_: (ring & pieces[gname][j_]).sum())
                pieces[gname][j] = pieces[gname][j] | pieces[gname][i]
                pieces[gname].pop(i)
                break
        else:
            raise RuntimeError("no two yards of a state touch: too many yards for the planet's ids")
    while count() < n_free:
        gname, i = max(((g_, i_) for g_, v in pieces.items() for i_ in range(len(v))), key=lambda t: pieces[t[0]][t[1]].sum())
        big = pieces[gname].pop(i)
        part = split_area(big, 2, rng)
        ys, xs = np.nonzero(big)
        for k in range(2):
            p = np.zeros(big.shape, bool)
            p[ys[part == k], xs[part == k]] = True
            pieces[gname].append(p)
    return pieces


def passages(lab, links, town_c, towns, rng):
    """The routes the city sprawls along: from the capital through the maze's openings to every outer town (fewest
    yards crossed), plus a share of side branches off them. Each link is drawn yard centre -> opening -> yard centre.
    -> list of polylines [[y, x], ...]"""
    import collections
    yards = [int(k) for k in np.unique(lab[lab > 0])]
    cen = {k: ndi.center_of_mass(lab == k) for k in yards}
    graph = collections.defaultdict(set)
    for a, b in links:
        graph[a].add(b)
        graph[b].add(a)
    near_town = min(yards, key=lambda k: math.hypot(cen[k][0] - town_c[0], cen[k][1] - town_c[1]))

    def opening(a, b):
        ma, mb = lab == a, lab == b
        touch = (ndi.binary_dilation(ma) & mb) | (ndi.binary_dilation(mb) & ma)
        return ndi.center_of_mass(touch) if touch.any() else ((cen[a][0] + cen[b][0]) / 2, (cen[a][1] + cen[b][1]) / 2)
    prev = {near_town: None}
    queue = collections.deque([near_town])
    while queue:                                                         # breadth first from the capital
        k = queue.popleft()
        for d in graph[k]:
            if d not in prev:
                prev[d] = k
                queue.append(d)
    used = set()
    for ty, tx in towns:
        k = int(lab[int(round(ty)), int(round(tx))]) or min(yards, key=lambda q: math.hypot(cen[q][0] - ty, cen[q][1] - tx))
        while k in prev and prev[k] is not None:
            used.add(frozenset((k, prev[k])))
            k = prev[k]
    on_route = {k for pair in used for k in pair}
    for a, b in links:
        if (a in on_route or b in on_route) and frozenset((a, b)) not in used and rng.random() < SPRAWL[0]:
            used.add(frozenset((a, b)))
    paths = [[[float(c) for c in cen[near_town]], [float(town_c[0]), float(town_c[1])]]]   # out of the capital
    for pair in used:
        a, b = sorted(pair)
        o = opening(a, b)
        paths.append([[float(cen[a][0]), float(cen[a][1])], [float(o[0]), float(o[1])], [float(cen[b][0]), float(cen[b][1])]])
    print(f"passages: {len(used)} links between {len({k for p_ in used for k in p_})} yards")
    return paths


def main():
    land, pid, m = mask()
    H = pid.shape[0]
    ids = sorted(np.unique(pid[m]).tolist())
    rng = np.random.default_rng(SEED)
    kind, groups, (cy, cx, R), links, lab, town_c = zones(m, rng)
    fixed = sum(gr["n"] for gr in groups.values() if gr["n"])
    pieces = fit_yards(groups, len(ids) - fixed, links, rng)
    newpid = pid.copy()
    it = iter(ids)
    prov = {}
    for k, gr in groups.items():
        if gr["part"] is None:
            part = split_area(gr["mask"], gr["n"], rng)
            ys, xs = np.nonzero(gr["mask"])
            masks = []
            for i in range(gr["n"]):
                mk = np.zeros(m.shape, bool)
                mk[ys[part == i], xs[part == i]] = True
                masks.append(mk)
        else:
            masks = pieces[k]
        for mk in masks:
            p = next(it)
            newpid[mk] = p
            prov[p] = dict(zone=gr["zone"], kind=int(gr["kind"]), state=gr["state"], group=k,
                           level=int(gr["kind"] == 4 and rng.random() < UPPER))
    mend(newpid, m, prov)
    rows = {int(r[0]): r for r in csv.reader(open("map/definition.csv", encoding="utf-8-sig"), delimiter=";") if r and r[0].isdigit()}
    bmp = np.array(Image.open("map/provinces.bmp").convert("RGB"))
    ys, xs = np.nonzero(m)
    bmp[ys, xs] = np.array([[int(rows[p][1]), int(rows[p][2]), int(rows[p][3])] for p in newpid[ys, xs]], np.uint8)
    Image.fromarray(bmp, "RGB").save("map/provinces.bmp")
    sea = np.isin(pid, [i for i, r in rows.items() if r[4] == "sea"])
    for p, v in prov.items():
        pm = newpid == p
        ring = ndi.binary_dilation(pm) & ~pm
        v["coastal"] = bool((ring & sea).any())
        v["sea"] = int(np.bincount(pid[ring & sea]).argmax()) if v["coastal"] else 0
        pcy, pcx = ndi.center_of_mass(pm)
        v["centre"] = [float(pcy), float(pcx)]
        v["terrain"] = {1: "urban", 2: "urban", 5: "mountain", 7: "mountain", 9: "marsh"}.get(v["kind"]) or \
            ("hills" if v["level"] else "desert")                          # junk yards: the plateaus count as hills
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
    towns, sites = states(prov, land, m, newpid, rng, town_c)
    paths = passages(lab, links, town_c, [prov[t]["centre"] for t in towns if prov[t]["kind"] == 4], rng)
    json.dump({"centre": [cy, cx], "radius": R, "town_centre": list(town_c), "towns": towns, "sites": sites,
               "passages": paths,
               "provinces": {str(p): v for p, v in prov.items()}}, open(ZONES_JSON, "w"), indent=1)
    Image.fromarray(kind).save(ZONES_PNG)
    ambient(sites, town_c, H)


def states(prov, land, m, newpid, rng, town_c):
    """state files keeping resources, industry and manpower; impassable states for the plant, the scrap mountains and
    the mire; map positions (felucia_tribes.place); fleets to the main port, land units off impassable ground.
    Returns (scrap-town province ids, wreck sites {state name: centre})"""
    all_ids = [CAPITAL, *OUTER, *IMPASSABLE]
    old = {}
    for f in glob.glob("history/states/*.txt"):
        sid = int(re.search(r"\bid\s*=\s*(\d+)", open(f, encoding="utf-8-sig").read()).group(1))
        if sid in all_ids:
            old[sid] = f
    by_state = {}
    for p, v in prov.items():
        by_state.setdefault(v["state"], []).append(p)
    pc = lambda p: np.array(prov[p]["centre"])
    names = {CAPITAL: "Raxus Prime", **{s: n for s, (n, _) in OUTER.items()}, **IMPASSABLE}
    vp_names, sts, ports, towns, sites = {}, {}, {}, [], {}
    b = block(block(open(old[CAPITAL], encoding="utf-8-sig").read(), "history"), "buildings")
    moved_docks = sum(int(x) for x in re.findall(r"\bdockyard\s*=\s*(\d+)", b))
    moved_naval = [int(x) for x in re.findall(r"naval_base\s*=\s*(\d+)", b)]
    for sid, provs in sorted(by_state.items()):
        provs = sorted(provs)
        src = open(old[sid], encoding="utf-8-sig").read() if sid in old else ""
        res = block(src, "resources") or "\n\tresources={\n\t}"
        bld = block(block(src, "history"), "buildings") or "\n\t\tbuildings = {\n\t\t\tinfrastructure = 2\n\t\t}"
        naval = [int(x) for x in re.findall(r"naval_base\s*=\s*(\d+)", bld)]
        bld = re.sub(r"\n\s*\d+\s*=\s*\{[^{}]*\}", "", bld)
        cen = np.mean([pc(p) for p in provs], 0)
        main_p = min(provs, key=lambda p: np.hypot(*(pc(p) - cen)))
        coastal = [p for p in provs if prov[p]["coastal"]]
        man = re.search(r"manpower\s*=\s*(\d+)", src).group(1) if src else "2000"
        cat = re.search(r"state_category\s*=\s*(\w+)", src).group(1) if src else "wasteland_sector"
        imp = ""
        if sid == CAPITAL:
            south = max(provs, key=lambda p: pc(p)[0])                    # the town's gate faces the camera
            vps = [(main_p, 5), (south, 3)]
            vp_names.update({main_p: "Central Station", south: "Dooku's Headquarters"})
            bld = re.sub(r"\n\s*dockyard\s*=\s*\d+", "", bld)
            towns += provs
        elif sid in OUTER:
            vps = [(main_p, 3)]
            vp_names[main_p] = OUTER[sid][1]
            towns.append(main_p)
            inland = [q for q in provs if not prov[q]["coastal"] and prov[q]["kind"] == 4] or provs
            site = max(inland, key=lambda q: min(np.hypot(*(pc(q) - pc(main_p))),            # wrecks lie away from
                                                 np.hypot(*(pc(q) - np.array(town_c)))))     # the towns and capital
            sites[OUTER[sid][0]] = [float(c) for c in pc(site)]
            k = list(OUTER).index(sid)
            extra = moved_docks // 3 + (k < moved_docks % 3) if k < 3 else 0
            if extra:
                d = re.search(r"\bdockyard\s*=\s*(\d+)", bld)
                bld = (bld.replace(d.group(0), f"dockyard = {int(d.group(1)) + extra}") if d else
                       bld.rstrip().rstrip("}") + f"\tdockyard = {extra}\n\t\t}}")
            lv = naval + (moved_naval if k == 0 else [])
            if lv and coastal:
                port = max(coastal, key=lambda p: -np.hypot(*(pc(p) - cen)))
                ports[port] = max(lv)
                bld = bld.rstrip().rstrip("}") + f"\t\t\t{port} = {{\n\t\t\t\tnaval_base = {max(lv)}\n\t\t\t}}\n\t\t}}"
        else:
            vps = []
            imp = f"\timpassable = yes\n\tforce_link_ownership_to = {CAPITAL}\n"
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            res, man, cat = "\n\tresources={\n\t}", "2000", "wasteland_sector"
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {v}\n\t\t}}\n" for p, v in vps)
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: Raxus Prime, {prov[provs[0]]['zone']} (raxus_prime_map.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = CIS\n\t\tadd_core_of = CIS\n\t}}\n"
                f"\tmanpower = {man}\n\tstate_category = {cat}\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}}\n")
        if sid in old:
            os.remove(old[sid])
        open(f"history/states/{sid}-Raxus Prime - {names[sid].replace(chr(39), '')}.txt", "w", encoding="utf-8",
             newline="\n").write(text)
        sts[sid] = dict(kind="white" if sid in IMPASSABLE else prov[provs[0]]["zone"], provinces=provs, coastal=coastal,
                        main=main_p)
    for sid in set(old) - set(sts):                  # a state left without land: its file and positions go
        os.remove(old[sid])
    place(sts, prov, newpid, land, m, set(sts) | set(old), sts[CAPITAL]["main"], CAPITAL, rng)
    fprov = set(prov)
    capital_p = sts[CAPITAL]["main"]
    blocked = {p for p, v in prov.items() if v["zone"] == "white"}
    if ports:
        main_port = max(ports, key=ports.get)
        for f in NAVY_FILES:
            rw(f, lambda s: re.sub(r"\b(naval_base|location)(\s*=\s*)(\d+)\b",
                                   lambda q: q.group(1) + q.group(2) + (str(main_port) if int(q.group(3)) in fprov else q.group(3)), s))
    for f in glob.glob("history/units/*.txt"):
        if f.replace("\\", "/") not in NAVY_FILES:
            rw(f, lambda s: re.sub(r"\blocation(\s*=\s*)(\d+)\b",
                                   lambda q: "location" + q.group(1) + (str(capital_p) if int(q.group(2)) in blocked else q.group(2)), s))

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
        print(f"{sid:5} {st['kind']:7} {len(st['provinces']):3} provinces  {names[sid]}")
    print("ports", ports)
    return towns, sites


def ambient(sites, centre, H):
    """map/ambient_object.txt: the plant on the centre, the split hulks and the droid works at their sites (y = 0: the
    game stands ambient objects on the ground); entities in gfx/entities/hod_raxus_prime.{gfx,asset}"""
    meshes = [PLANT_MESH] + sorted({m_ for pieces in WRECKS.values() for m_, _o, _y in pieces})
    open("gfx/entities/hod_raxus_prime.gfx", "w", encoding="utf-8", newline="\n").write(
        "objectTypes = {\n\t# HOD: Raxus Prime wrecks and works (raxus_prime_map.py)\n"
        + "".join(f'\tpdxmesh = {{\n\t\tname = "{n}_mesh"\n\t\tfile = "gfx/models/buildings/hod_sw/{n}.mesh"\n\t}}\n' for n in meshes)
        + "}\n")
    open("gfx/entities/hod_raxus_prime.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: Raxus Prime wrecks and works (raxus_prime_map.py)\n"
        + "".join(f'entity = {{\n\tname = "{n}_entity"\n\tpdxmesh = "{n}_mesh"\n\tscale = 1\n}}\n' for n in meshes))
    objs = {PLANT_MESH: [(centre[1], H - 1 - centre[0], 0.0)]}
    for site, pieces in WRECKS.items():
        sy, sx = sites[site]
        for mesh, (dx, dy), yaw in pieces:
            objs.setdefault(mesh, []).append((sx + dx, H - 1 - (sy + dy), math.radians(yaw)))
    block_ = AMBIENT_MARK[0] + "\n"
    for name, pts in objs.items():
        block_ += f'type={{\n\ttype="{name}_entity"\n\tuse_animation=no\n\tscale=1.000000\n'
        block_ += "".join(f'\tobject={{\n\t\tname="{name}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} 0.000 {z:.3f} \n\t\t}}\n'
                          f'\t\trotation={{\n\t\t\t0.000 {yaw:.3f} 0.000 \n\t\t}}\n\t}}\n' for i, (x, z, yaw) in enumerate(pts))
        block_ += "}\n"
    block_ += AMBIENT_MARK[1] + "\n"

    def put(s):
        s = re.sub(re.escape(AMBIENT_MARK[0]) + r".*?" + re.escape(AMBIENT_MARK[1]) + r"\n", "", s, flags=re.S)
        return s.rstrip("\n") + "\n" + block_
    rw("map/ambient_object.txt", put)
    print("ambient:", {k: len(v) for k, v in objs.items()})


if __name__ == "__main__":
    main()
