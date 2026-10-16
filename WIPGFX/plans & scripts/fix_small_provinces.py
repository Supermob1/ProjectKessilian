"""Grow every land province below the game's minimum (error.log: "Province N has only N pixels around ... Should have
at least 8") by taking border pixels from neighbours of the same state that can spare them (as a last resort from a bigger
neighbour of an adjacent state, a pixel or two): only from neighbours of
at least SPARE pixels, never cutting a neighbour in two, never making an X crossing. Province ids, colours, states and
the strategic regions are unchanged; only map/provinces.bmp is rewritten.

    python -B "WIPGFX/plans & scripts/fix_small_provinces.py" [--dry]

Run from the mod root after any map script (validate_planet.py afterwards).
"""
import csv, glob, os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

MIN_PX, TARGET_PX, SPARE = 8, 9, 10      # the game's minimum; grow to TARGET; a giver must keep >= SPARE - 1 px


def main():
    dry = "--dry" in sys.argv
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import planet_terrain_gen as g
    _land, _cls, pid = g.load_provinces()
    pid = pid.astype(np.int64)
    colour, land = {}, set()
    with open("map/definition.csv", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) > 4 and row[0].isdigit() and int(row[0]) > 0:
                p = int(row[0])
                colour[p] = (int(row[1]), int(row[2]), int(row[3]))
                if row[4].strip() == "land":
                    land.add(p)
    state = {}
    for f in glob.glob("history/states/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        sid = int(re.search(r"\bid\s*=\s*(\d+)", s).group(1))
        m = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        for p in (m.group(1).split() if m else []):
            state[int(p)] = sid
    ids, cnt = np.unique(pid, return_counts=True)
    count = dict(zip(ids.tolist(), cnt.tolist()))
    small = [p for p in ids.tolist() if p in land and count[p] < MIN_PX]
    H, W = pid.shape

    def x_cross(r, c):
        """does a 2x2 block round (r, c) hold an X crossing (four different provinces at one corner: the game's and
        validate_planet's rule) or a diagonal-only touch of one province?"""
        for dr in (-1, 0):
            for dc in (-1, 0):
                r0, c0 = r + dr, c + dc
                if 0 <= r0 < H - 1 and 0 <= c0 < W - 1:
                    a, b, cc, d = pid[r0, c0], pid[r0, c0 + 1], pid[r0 + 1, c0], pid[r0 + 1, c0 + 1]
                    if len({a, b, cc, d}) == 4 or (a == d and b == cc and a != b):
                        return True
        return False

    def repair_x():
        """X crossings anywhere on land: one pixel of the block takes a block-mate's province, if the province it
        leaves keeps >= MIN_PX pixels and stays in one piece, and no new crossing appears"""
        A, B, C, D = pid[:-1, :-1], pid[:-1, 1:], pid[1:, :-1], pid[1:, 1:]
        xs = np.argwhere((A != B) & (A != C) & (A != D) & (B != C) & (B != D) & (C != D))
        fixed = 0
        for r0, c0 in xs.tolist():
            block = [(r0, c0), (r0, c0 + 1), (r0 + 1, c0), (r0 + 1, c0 + 1)]
            if not all(int(pid[r, c]) in land for r, c in block):
                continue
            done = False
            for r, c in block:
                q = int(pid[r, c])
                if count[q] <= MIN_PX:
                    continue
                for rr, cc in block:
                    n = int(pid[rr, cc])
                    if n == q or (abs(rr - r) + abs(cc - c)) != 1:
                        continue
                    y0, y1, x0, x1 = max(r - 12, 0), min(r + 13, H), max(c - 12, 0), min(c + 13, W)
                    win = pid[y0:y1, x0:x1] == q
                    win[r - y0, c - x0] = False
                    if ndi.label(win)[1] > 1:
                        continue
                    pid[r, c] = n
                    if x_cross(r, c):
                        pid[r, c] = q
                        continue
                    count[q] -= 1
                    count[n] += 1
                    changed.append((r, c))
                    done = True
                    break
                if done:
                    break
            fixed += done
        return len(xs), fixed
    report, changed = [], []
    for p in small:
        before = count[p]
        ys, xs = np.nonzero(pid == p)
        cy0, cy1, cx0, cx1 = max(ys.min() - 4, 0), min(ys.max() + 5, H), max(xs.min() - 4, 0), min(xs.max() + 5, W)
        for it in range(80):
            if count[p] >= TARGET_PX:
                break
            any_state = it >= 40                  # fallback: a bigger neighbour of another state gives a pixel
            m = pid[cy0:cy1, cx0:cx1] == p
            ring = np.argwhere(ndi.binary_dilation(m) & ~m) + [cy0, cx0]
            took = False
            for r, c in sorted(ring.tolist(), key=lambda rc: -count.get(int(pid[rc[0], rc[1]]), 0)):
                q = int(pid[r, c])
                if q == p or q not in land or count[q] < (SPARE if not any_state else SPARE + 3):
                    continue
                if state.get(q) != state.get(p) and not any_state:
                    continue
                y0, y1, x0, x1 = max(r - 12, 0), min(r + 13, H), max(c - 12, 0), min(c + 13, W)
                win = pid[y0:y1, x0:x1] == q
                win[r - y0, c - x0] = False
                if ndi.label(win)[1] > 1:                                # would cut q in two (locally)
                    continue
                pid[r, c] = p
                changed.append((r, c))
                if x_cross(r, c):
                    changed.pop()
                    pid[r, c] = q
                    continue
                count[p] += 1
                count[q] -= 1
                took = True
                break
            if not took and any_state:
                break
        report.append((p, before, count[p], state.get(p)))
    n_x, n_fixed = repair_x()
    print(f"X crossings on land: {n_x} found, {n_fixed} fixed")
    for p, a, b, sid in report:
        print(f"province {p} (state {sid}): {a} -> {b} px" + ("" if b >= MIN_PX else "  STILL TOO SMALL"))
    if not dry and changed:
        bmp = np.array(Image.open("map/provinces.bmp").convert("RGB"))
        for r, c in changed:
            bmp[r, c] = colour[int(pid[r, c])]
        Image.fromarray(bmp, "RGB").save("map/provinces.bmp")
        print(f"map/provinces.bmp written ({len(changed)} pixels)")


if __name__ == "__main__":
    main()
