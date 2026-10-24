"""Repair map/buildings.txt against the real province map: every building whose position does not stand on a land
province of its own state (error.log: "location is not within specified state ... BUILDING IGNORED", "map building
location is not over the land") is moved (coastal / naval buildings, which stand on the water by design, are left) to the centre of the nearest province of that state; malformed lines
("invalid arguments count") are dropped. The cause was felucia_tribes.place putting province buildings at the centre
pixel's corner plus a random nudge, which tipped them into the neighbour on thin provinces (fixed there too).

    python -B "WIPGFX/plans & scripts/fix_building_positions.py" [--dry]

Run from the mod root after any map script; it only touches lines that are wrong and reports them.
Position convention (felucia_tribes.place): x = column, z = H - 1 - row; a position's pixel is (H - 1 - floor(z), floor(x)).
"""
import csv, glob, os, re, sys
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planet_terrain_gen as g


# buildings placed on the sea next to their coastal province (the game accepts these off-land)
NAVAL = {"floating_harbor", "naval_base_spawn", "naval_base", "coastal_bunker", "naval_supply_hub", "naval_headquarters",
         "dockyard", "naval_fuel_depot"}


def state_provinces():
    out = {}
    for f in glob.glob("history/states/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        sid = int(re.search(r"\bid\s*=\s*(\d+)", s).group(1))
        m = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        out[sid] = [int(p) for p in m.group(1).split()] if m else []
    return out


def land_provinces():
    """land provinces, and the coastal ones among them (definition.csv)"""
    land, coastal = set(), set()
    with open("map/definition.csv", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) > 5 and row[0].isdigit() and row[4].strip() == "land":
                land.add(int(row[0]))
                if row[5].strip() == "true":
                    coastal.add(int(row[0]))
    return land, coastal


def main():
    dry = "--dry" in sys.argv
    _land, _, pid = g.load_provinces()
    H, W = pid.shape
    hm = np.asarray(g.load("map/heightmap.bmp").convert("L")).astype(float)
    states = state_provinces()
    prov_state = {p: sid for sid, ps in states.items() for p in ps}
    land, coastal = land_provinces()
    centres = {}

    def centre(p):
        """the province's innermost pixel (row, col)"""
        if p not in centres:
            ys, xs = np.nonzero(pid == p)
            if not len(ys):
                centres[p] = None
            else:
                y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
                m = np.pad(pid[y0:y1, x0:x1] == p, 1)
                d = ndi.distance_transform_edt(m)[1:-1, 1:-1]
                r, c = np.unravel_index(np.argmax(d), d.shape)
                centres[p] = (y0 + r, x0 + c)
        return centres[p]

    lines = open("map/buildings.txt", encoding="utf-8-sig", newline="").readlines()
    end = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    out, moved, dropped = [], [], []
    for i, l in enumerate(lines):
        q = l.rstrip("\r\n").split(";")
        if not q[0].strip().isdigit():
            out.append(l)
            continue
        if len(q) != 7:
            dropped.append((i + 1, l.strip()))
            continue
        sid = int(q[0])
        if q[1] in NAVAL or q[6].strip() not in ("0", ""):    # coastal buildings stand on the water by design
            out.append(l)
            continue
        try:
            x, z = float(q[2]), float(q[4])
        except ValueError:
            dropped.append((i + 1, l.strip()))
            continue
        r, c = H - 1 - int(np.floor(z)), int(np.floor(x))
        p = int(pid[r, c]) if 0 <= r < H and 0 <= c < W else -1
        if prov_state.get(p) == sid and p in land:
            out.append(l)
            continue
        own = [pp for pp in states.get(sid, []) if pp in land and centre(pp) is not None]
        if not own:
            dropped.append((i + 1, l.strip()))
            continue
        best = min(own, key=lambda pp: (centre(pp)[0] - r) ** 2 + (centre(pp)[1] - c) ** 2)
        rr, cc = centre(best)
        q[2], q[3], q[4] = f"{cc + 0.5:.2f}", f"{hm[rr, cc] / 10:.2f}", f"{H - 1 - rr + 0.5:.2f}"
        out.append(";".join(q) + end)
        moved.append((i + 1, sid, q[1], p, best))
    # coastal provinces without a port: the game warns "setup as coastal but has no port building in the nudger. This
    # will likely crash the game" (it did, after fix_small_provinces gave a coast pixel to a neighbour). Each naval
    # group (the lines of one coast point) must stand on a coastal province of its state, one group per such province:
    # stranded or doubled groups move to the outermost coast pixel of a coastal province that has none
    groups = {}                                                       # (state, x, z) -> [line indices in out]
    for i, l in enumerate(out):
        q = l.rstrip(chr(13) + chr(10)).split(";")
        if len(q) == 7 and q[0].strip().isdigit() and q[1] in NAVAL - {"dockyard", "naval_base"}:
            groups.setdefault((int(q[0]), q[2], q[4]), []).append(i)
    by_state = {}
    for (sid, xs_, zs_), idx in groups.items():
        r, c = H - 1 - int(np.floor(float(zs_))), int(np.floor(float(xs_)))
        p = int(pid[r, c]) if 0 <= r < H and 0 <= c < W else -1
        by_state.setdefault(sid, []).append([p, idx])
    for sid, gl in by_state.items():
        have = {}
        for g_ in gl:
            if prov_state.get(g_[0]) == sid and g_[0] in coastal:
                have.setdefault(g_[0], []).append(g_)
        spare = [g_ for g_ in gl if not (prov_state.get(g_[0]) == sid and g_[0] in coastal)]
        spare += [g_ for p_, gs in have.items() for g_ in gs[1:]]
        need = [p_ for p_ in states.get(sid, []) if p_ in coastal and p_ not in have]
        for p_ in need:
            if not spare:
                print(f"state {sid}: coastal province {p_} has no port and no spare naval group to give it")
                continue
            g_ = spare.pop(0)
            ys, xs = np.nonzero(pid == p_)
            y0, y1, x0, x1 = max(ys.min() - 1, 0), ys.max() + 2, max(xs.min() - 1, 0), xs.max() + 2
            sub = pid[y0:y1, x0:x1]
            notland = ~np.isin(sub, list(land))
            ring = np.argwhere((sub == p_) & ndi.binary_dilation(notland))
            cr, cc = centre(p_)
            rr, c2 = max(ring.tolist(), key=lambda t: (t[0] + y0 - cr) ** 2 + (t[1] + x0 - cc) ** 2) if len(ring) else (cr - y0, cc - x0)
            rr, c2 = rr + y0, c2 + x0
            for i in g_[1]:
                q = out[i].rstrip(chr(13) + chr(10)).split(";")
                q[2], q[3], q[4] = f"{c2 + 0.5:.2f}", f"{hm[rr, c2] / 10:.2f}", f"{H - 1 - rr + 0.5:.2f}"
                out[i] = ";".join(q) + end
            moved.append((g_[1][0] + 1, sid, "naval group", g_[0], p_))
    for ln, sid, b, p, best in moved:
        print(f"moved   line {ln}: state {sid} {b}: was on province {p} -> province {best}")
    for ln, l in dropped:
        print(f"dropped line {ln}: {l}")
    print(f"{len(moved)} moved, {len(dropped)} dropped" + (" (dry run, nothing written)" if dry else ""))
    if not dry and (moved or dropped):
        open("map/buildings.txt", "w", encoding="utf-8", newline="").write("".join(out))


if __name__ == "__main__":
    main()
