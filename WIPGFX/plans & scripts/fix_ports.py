"""Move naval bases off inland provinces (error.log: "Trying to set invalid province building naval_base to province
#N" and "invalid state building dockyard to state #N"): every naval_base on a province whose definition.csv coastal
flag is false goes to the nearest coastal province of a passable state on the same planet, the state's dockyards go to that
province's state, and fleets based on the old province (history/units naval_base / location) follow. The planet map
scripts used the capital province as the port when the port state had no coast.

    python -B "WIPGFX/plans & scripts/fix_ports.py" [--dry]

Run from the mod root after any map script.
"""
import csv, glob, os, re, sys
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planet_terrain_gen as g
from felucia_tribes import block, rw


def main():
    dry = "--dry" in sys.argv
    coastal, land = set(), set()
    with open("map/definition.csv", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) > 5 and row[0].isdigit():
                if row[4].strip() == "land":
                    land.add(int(row[0]))
                    if row[5].strip() == "true":
                        coastal.add(int(row[0]))
    files, impassable = {}, set()
    for f in glob.glob("history/states/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        sid = int(re.search(r"\bid\s*=\s*(\d+)", s).group(1))
        m = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        files[sid] = (f, [int(p) for p in m.group(1).split()] if m else [])
        if re.search(r"\bimpassable\s*=\s*yes", s):
            impassable.add(sid)
    state_of = {p: sid for sid, (_f, ps) in files.items() for p in ps}
    bad = []
    for sid, (f, _ps) in files.items():
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        for m in re.finditer(r"(\d+)\s*=\s*\{\s*naval_base\s*=\s*(\d+)\s*\}", s):
            p = int(m.group(1))
            if p not in coastal:
                bad.append((sid, p, int(m.group(2))))
    if not bad:
        print("no naval bases on inland provinces")
        return
    land_px, _, pid = g.load_provinces()
    labels, _n = ndi.label(land_px, np.ones((3, 3)))
    for sid, p, level in bad:
        ys, xs = np.nonzero(pid == p)
        planet = labels[ys[0], xs[0]]
        cand = [q for q in np.unique(pid[labels == planet]).tolist()
                if q in coastal and q in state_of and state_of[q] not in impassable]     # a port on passable ground
        if not cand:
            print(f"state {sid}: naval base {p} has no coastal province on its planet: removed")
            new_p, new_sid = None, None
        else:
            cy, cx = ys.mean(), xs.mean()

            def dist(q):
                qy, qx = np.nonzero(pid == q)
                return (qy.mean() - cy) ** 2 + (qx.mean() - cx) ** 2
            new_p = min(cand, key=dist)
            new_sid = state_of[new_p]
            print(f"state {sid}: naval base {level} on inland province {p} -> coastal province {new_p} (state {new_sid})")
        if dry:
            continue
        old_f = files[sid][0]
        s = open(old_f, encoding="utf-8-sig").read()
        s = re.sub(rf"\n\s*{p}\s*=\s*\{{\s*naval_base\s*=\s*\d+\s*\}}", "", s)
        dock = re.search(r"\n\s*dockyard\s*=\s*(\d+)", s)
        if dock and new_sid != sid:
            s = s.replace(dock.group(0), "")
        open(old_f, "w", encoding="utf-8", newline="\n").write(s)
        if new_p is None:
            continue
        new_f = files[new_sid][0]

        def add(s2):
            hist = block(s2, "history")
            bld = block(hist, "buildings") if hist else ""
            if not bld:
                return s2
            nb = bld.rstrip().rstrip("}")
            if dock and new_sid != sid:
                d0 = re.search(r"\bdockyard\s*=\s*(\d+)", nb)
                nb = (nb.replace(d0.group(0), f"dockyard = {int(d0.group(1)) + int(dock.group(1))}") if d0
                      else nb + f"\tdockyard = {dock.group(1)}\n\t\t")
            nb += f"\t{new_p} = {{\n\t\t\t\tnaval_base = {level}\n\t\t\t}}\n\t\t}}"
            return s2.replace(bld, nb, 1)
        rw(new_f, add)
        for uf in glob.glob("history/units/*.txt"):                         # fleets follow the base
            rw(uf, lambda u: re.sub(rf"\b(naval_base|location)(\s*=\s*){p}\b", rf"\g<1>\g<2>{new_p}", u))


if __name__ == "__main__":
    main()
