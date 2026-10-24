"""Re-anchor hyperlanes whose end no longer touches the lane's THROUGH space province (error.log: "Adj between A and B
is not adjacent with THROUGH = T"; happens after a map script moves a planet's coast). The end moves to the province of
the same state that touches T, nearest to the old end. Only map/adjacencies.csv is rewritten; run
tools/hoi4_country_editor/gen_hyperlanes.py afterwards (rule names and comments follow the new ends).

    python -B "WIPGFX/plans & scripts/fix_lanes.py" [--dry]

Run from the mod root after the other map fixers.
"""
import glob, os, re, sys
import numpy as np
from scipy import ndimage as ndi


def main():
    dry = "--dry" in sys.argv
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import planet_terrain_gen as g
    _land, _cls, pid = g.load_provinces()
    pid = pid.astype(np.int64)
    pairs = np.concatenate([np.stack([pid[:, :-1].ravel(), pid[:, 1:].ravel()], 1),
                            np.stack([pid[:-1].ravel(), pid[1:].ravel()], 1)])
    pairs = pairs[pairs[:, 0] != pairs[:, 1]]
    touch = {}
    for a, b in np.unique(np.sort(pairs, 1), axis=0).tolist():
        touch.setdefault(a, set()).add(b)
        touch.setdefault(b, set()).add(a)
    state, members = {}, {}
    for f in glob.glob("history/states/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        sid = int(re.search(r"\bid\s*=\s*(\d+)", s).group(1))
        m = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        for p in (m.group(1).split() if m else []):
            state[int(p)] = sid
            members.setdefault(sid, []).append(int(p))
    ids = np.arange(pid.max() + 1)
    cy, cx = (np.array(v) for v in zip(*ndi.center_of_mass(np.ones(pid.shape), pid, ids)))

    raw = open("map/adjacencies.csv", "rb").read().decode("utf-8-sig")
    lines, fixed, failed = raw.splitlines(keepends=True), 0, []
    for i, line in enumerate(lines):
        c = line.rstrip("\r\n").split(";")
        if len(c) < 4 or not c[0].isdigit() or c[2] != "sea" or c[3] in ("-1", ""):
            continue
        t, a, b = int(c[3]), int(c[0]), int(c[1])
        if touch.get(t, set()) & {a, b}:                     # the game only needs one end next to THROUGH
            continue
        best = None
        for k, p in ((0, a), (1, b)):                        # move an end within its state, the shortest hop
            for q in members.get(state.get(p), []):
                if q in touch.get(t, ()):
                    d = (cy[q] - cy[p]) ** 2 + (cx[q] - cx[p]) ** 2
                    if best is None or d < best[0]:
                        best = (d, k, p, q)
        if best:
            _, k, p, q = best
            print(f"line {i + 1}: end {p} -> {q} (state {state.get(p)}, through {t})")
            c[k] = str(q)
        else:                                                # no province of either state touches T: a new THROUGH
            sea = [s for s in touch.get(a, ()) if s not in state]   # space provinces have no state
            if not sea:
                failed.append(f"line {i + 1}: {a};{b} through {t}: no space province next to {a}")
                continue
            s = min(sea, key=lambda s: (cy[s] - cy[b]) ** 2 + (cx[s] - cx[b]) ** 2)
            print(f"line {i + 1}: through {t} -> {s} ({a};{b})")
            c[3] = str(s)
        fixed += 1
        lines[i] = ";".join(c) + line[len(line.rstrip("\r\n")):]
    print(f"{fixed} lanes re-anchored")
    for f in failed:
        print("UNFIXED", f)
    if not dry and fixed:
        bom = "﻿" if raw.startswith("﻿") else ""
        open("map/adjacencies.csv", "wb").write((bom + "".join(lines)).encode("utf-8"))


if __name__ == "__main__":
    main()
