"""Felucia's provinces redrawn from the hand-drawn plan (felucia map.png, pixel-aligned crop of the planet):
red outlines = passable lowlands of the Separatists, blue = the natives' mountain jungles, black lines = passages
(chains of thin provinces), everything else = impassable jungle.

    python "WIPGFX/plans & scripts/felucia_map.py"          provinces.bmp, definition.csv, zones (step 1)

The planet keeps its 195 province ids and colours (definition.csv numbering, strategic region unchanged); only the
pixels move. Writes WIPGFX/Assets/felucia_zones.json (province -> zone kind and group) and felucia_zones.png for
felucia_tribes.py (states, buildings, unit stacks, adjacencies) and planet_terrain_gen.py --felucia (relief).
Run order: felucia_map.py -> felucia_tribes.py -> planet_terrain_gen.py --felucia -> --globe-texture
-> faction_templates.py.
"""
import csv, json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

PLAN = "felucia map.png"          # palette: 0 white (impassable), 1 red, 2 black (passage), 3 blue, 4 transparent
OFFSET = (594, 2269)              # map (row, col) of the plan's (0, 0)
ZONES_JSON = "WIPGFX/Assets/felucia_zones.json"
ZONES_PNG = "WIPGFX/Assets/felucia_zones.png"
CORRIDOR_LEN = 14                 # map px of passage per province
CORRIDOR_HALF = 1                 # passage half-width (3 px wide provinces)
DENSITY = {"red": 1.7, "blue": 1.4, "white": 1.0}   # provinces per area, relative: passable land gets smaller ones
KIND = {"red": 1, "blue": 2, "corridor": 3, "white": 4}
TERRAIN = {"red": "jungle", "corridor": "hills", "white": "jungle"}     # blue: mountain core, jungle rim
SEED = 81


def felucia_mask():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    labels, n = ndi.label(land, np.ones((3, 3)))
    names = g.planet_names(labels, n, pid)
    fel = np.isin(labels, [l for l in range(1, n + 1) if names[l].split(" - ")[0] == "Felucia"])
    return land, pid, fel


def zones(fel):
    """zone kind per map pixel (0 outside) and group (zone instance) per pixel"""
    plan = np.array(Image.open(PLAN))
    P = np.full(fel.shape, 4, np.uint8)
    r0, c0 = OFFSET
    P[r0:r0 + plan.shape[0], c0:c0 + plan.shape[1]] = plan
    P[~fel] = 4
    red, black, blue = P == 1, P == 2, P == 3
    open_ = fel & ~(red | black | blue)
    comp, nc = ndi.label(open_)                                   # 4-connected: thin lines separate areas
    kind = np.zeros(fel.shape, np.uint8)
    group = np.zeros(fel.shape, np.int32)
    gkind = {}
    for c in range(1, nc + 1):
        m = comp == c
        ring = ndi.binary_dilation(m) & ~m
        nr, nb, nk = (ring & red).sum(), (ring & blue).sum(), (ring & black).sum()
        tot = max(nr + nb + nk, 1)
        k = "blue" if nb / tot > 0.8 else "red" if nr / tot > 0.8 else "white"
        kind[m], group[m], gkind[c] = KIND[k], c, k
    # passages: the black lines widened, wherever they run outside the red / blue areas
    cor = ndi.binary_dilation(black, iterations=CORRIDOR_HALF) & fel & ~np.isin(kind, (KIND["red"], KIND["blue"]))
    cor &= ~(red | blue)
    lines, nl = ndi.label(cor, np.ones((3, 3)))
    for l in range(1, nl + 1):
        m = lines == l
        if m.sum() < 6:
            continue
        gid = nc + l
        kind[m], group[m], gkind[gid] = KIND["corridor"], gid, "corridor"
    # outline pixels and leftovers join the nearest area (red / blue outlines their own inside)
    todo = fel & (group == 0)
    for colour, k in ((red, "red"), (blue, "blue")):
        sel = todo & colour
        src = np.isin(group, [g for g, v in gkind.items() if v == k])
        if src.any():
            _, (iy, ix) = ndi.distance_transform_edt(~src, return_indices=True)
            kind[sel], group[sel] = kind[iy[sel], ix[sel]], group[iy[sel], ix[sel]]
    todo = fel & (group == 0)
    _, (iy, ix) = ndi.distance_transform_edt(group == 0, return_indices=True)
    kind[todo], group[todo] = kind[iy[todo], ix[todo]], group[iy[todo], ix[todo]]
    # tiny white scraps (cut off by passages) join their biggest neighbour
    for gid, k in list(gkind.items()):
        m = group == gid
        if k == "white" and 0 < m.sum() < 120:
            ring = ndi.binary_dilation(m) & ~m & fel
            nbr = np.bincount(group[ring]).argmax()
            kind[m], group[m] = kind[ring][group[ring] == nbr][0], nbr
            del gkind[gid]
    gkind = {g: k for g, k in gkind.items() if (group == g).any()}
    return kind, group, gkind


def split_line(m, k):
    """a passage into k pieces along its length (geodesic distance from one end)"""
    ys, xs = np.nonzero(m)
    far = lambda y, x: np.argmax((ys - y) ** 2 + (xs - x) ** 2)
    a = far(ys[0], xs[0])
    dist = np.full(m.shape, -1, np.int32)
    dist[ys[a], xs[a]] = 0
    front = [(ys[a], xs[a])]
    while front:
        nxt = []
        for y, x in front:
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    q = (y + dy, x + dx)
                    if m[q] and dist[q] < 0:
                        dist[q] = dist[y, x] + 1
                        nxt.append(q)
        front = nxt
    d = dist[ys, xs]
    cuts = np.quantile(d, np.linspace(0, 1, k + 1)[1:-1]) if k > 1 else []
    return np.searchsorted(cuts, d, side="right")


def split_area(m, k, rng):
    """k contiguous, compact pieces (k-means on the pixels, stray fragments merged into a neighbour)"""
    ys, xs = np.nonzero(m)
    pts = np.stack([ys, xs], 1).astype(np.float32)
    if k <= 1:
        return np.zeros(len(ys), np.int32)
    cen = [pts[rng.integers(len(pts))]]
    for _ in range(k - 1):                                         # farthest-point start
        d = np.min([((pts - c) ** 2).sum(1) for c in cen], 0)
        cen.append(pts[np.argmax(d)])
    cen = np.array(cen)
    for _ in range(25):
        lab = np.argmin(((pts[:, None] - cen[None]) ** 2).sum(2), 1)
        cen = np.array([pts[lab == i].mean(0) if (lab == i).any() else cen[i] for i in range(k)])
    img = np.full(m.shape, -1, np.int32)
    img[ys, xs] = lab
    for _ in range(4):                                             # contiguity
        for i in range(k):
            pieces, n = ndi.label(img == i)
            if n <= 1:
                continue
            big = np.argmax(np.bincount(pieces.ravel())[1:]) + 1
            for p in range(1, n + 1):
                if p == big:
                    continue
                frag = pieces == p
                ring = ndi.binary_dilation(frag) & ~frag & (img >= 0) & (img != i)
                if ring.any():
                    img[frag] = np.bincount(img[ring]).argmax()
    return img[ys, xs]


def main():
    land, pid, fel = felucia_mask()
    ids = sorted(np.unique(pid[fel]).tolist())
    kind, group, gkind = zones(fel)
    rng = np.random.default_rng(SEED)
    # provinces per group: passages by length, areas by size x density, total = the planet's 195 ids
    area = {g: int((group == g).sum()) for g in gkind}
    want = {g: max(1, round(area[g] / (CORRIDOR_HALF * 2 + 1) / CORRIDOR_LEN)) for g, k in gkind.items() if k == "corridor"}
    rest = len(ids) - sum(want.values())
    w = {g: area[g] * DENSITY[k] for g, k in gkind.items() if k != "corridor"}
    raw = {g: rest * w[g] / sum(w.values()) for g in w}
    for g in w:
        want[g] = max(1, int(raw[g]))
    for g in sorted(w, key=lambda g: raw[g] - int(raw[g]), reverse=True)[:len(ids) - sum(want.values())]:
        want[g] += 1
    assert sum(want.values()) == len(ids), (sum(want.values()), len(ids))
    newpid = pid.copy()
    it = iter(ids)
    prov_info = {}
    for g, k in sorted(gkind.items()):
        m = group == g
        part = split_line(m, want[g]) if k == "corridor" else split_area(m, want[g], rng)
        ys, xs = np.nonzero(m)
        for i in range(want[g]):
            p = next(it)
            newpid[ys[part == i], xs[part == i]] = p
            prov_info[p] = {"zone": k, "group": int(g)}
    assert not (set(np.unique(newpid[fel]).tolist()) ^ set(ids)), "every id keeps pixels"
    # provinces.bmp: same colours, new shapes
    rows = {int(r[0]): r for r in csv.reader(open("map/definition.csv", encoding="utf-8-sig"), delimiter=";") if r and r[0].isdigit()}
    bmp = np.array(Image.open("map/provinces.bmp").convert("RGB"))
    ys, xs = np.nonzero(fel)
    colours = np.array([[int(rows[p][1]), int(rows[p][2]), int(rows[p][3])] for p in newpid[ys, xs]], np.uint8)
    bmp[ys, xs] = colours
    Image.fromarray(bmp, "RGB").save("map/provinces.bmp")
    # definition.csv: coastal (touching a sea province) and terrain by zone; blue cores are mountains
    sea_ids = {i for i, r in rows.items() if r[4] == "sea"}
    sea = np.isin(pid, list(sea_ids))
    core = ndi.distance_transform_edt(kind == KIND["blue"])
    for p in ids:
        m = newpid == p
        ring = ndi.binary_dilation(m) & ~m
        z = prov_info[p]["zone"]
        prov_info[p]["coastal"] = bool((ring & sea).any())
        prov_info[p]["sea"] = int(np.bincount(pid[ring & sea]).argmax()) if prov_info[p]["coastal"] else 0
        prov_info[p]["terrain"] = ("mountain" if core[m].mean() > 3 else "jungle") if z == "blue" else TERRAIN[z]
        cy, cx = ndi.center_of_mass(m)
        prov_info[p]["centre"] = [float(cy), float(cx)]
    path = "map/definition.csv"
    raw_txt = open(path, "rb").read()
    out = []
    for line in raw_txt.decode("utf-8-sig").splitlines(keepends=True):
        body, end = line.rstrip("\r\n"), line[len(line.rstrip("\r\n")):]
        q = body.split(";")
        if len(q) >= 7 and q[0].isdigit() and int(q[0]) in prov_info:
            q[5] = "true" if prov_info[int(q[0])]["coastal"] else "false"
            q[6] = prov_info[int(q[0])]["terrain"]
        out.append(";".join(q) + end)
    open(path, "wb").write((b"\xef\xbb\xbf" if raw_txt.startswith(b"\xef\xbb\xbf") else b"") + "".join(out).encode("utf-8"))
    # zones for the next steps
    os.makedirs(os.path.dirname(ZONES_JSON), exist_ok=True)
    json.dump({"groups": {str(g): k for g, k in gkind.items()}, "provinces": {str(p): v for p, v in prov_info.items()}},
              open(ZONES_JSON, "w"), indent=1)
    Image.fromarray(kind).save(ZONES_PNG)
    count = lambda k: sum(1 for v in prov_info.values() if v["zone"] == k)
    print(f"Felucia redrawn: {len(ids)} provinces - red {count('red')}, blue {count('blue')}, passages {count('corridor')}, "
          f"impassable {count('white')}; groups {dict(sorted((k, sum(1 for v in gkind.values() if v == k)) for k in KIND))}; "
          f"coastal {sum(v['coastal'] for v in prov_info.values())}")


if __name__ == "__main__":
    main()
