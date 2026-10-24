"""Merge the provinces of every impassable state into fewer, bigger ones to free province ids for new planets (the map
is at the province limit). A merged province is at most CAP x the planet's average passable province; only provinces of
the same impassable state merge, only with neighbours, so every merged province is one piece and no state changes shape.
A province that anything names by id (a VP, a province building, an adjacency, a unit, a script) keeps its id and never
absorbs another named one. Then free_province_ids.py drops the emptied ids and keeps definition.csv gapless.

    python "WIPGFX/plans & scripts/merge_impassable.py" [--dry | --coastal]   --dry: report only; --coastal: only refresh coastal flags
"""
import glob, os, re, sys, collections
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CAP = 3.0


def load():
    img = Image.open("map/provinces.bmp").convert("RGB")
    px = np.asarray(img).astype(np.int64)
    key = (px[..., 0] << 16) | (px[..., 1] << 8) | px[..., 2]
    rows = {}
    for l in open("map/definition.csv", encoding="utf-8-sig"):
        q = l.split(";")
        if q[0].isdigit() and int(q[0]) > 0:
            rows[int(q[0])] = (int(q[1]) << 16) | (int(q[2]) << 8) | int(q[3])
    cols = np.array(sorted(rows.values()))
    col_id = {c: p for p, c in rows.items()}
    ids = np.array([col_id[c] for c in cols.tolist()])
    i = np.clip(np.searchsorted(cols, key), 0, len(cols) - 1)
    assert (cols[i] == key).all(), "provinces.bmp has colours definition.csv does not list"
    pid = ids[i]
    return img.mode, pid, rows


def states():
    out = []
    for f in glob.glob("history/states/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        m = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        if m:
            planet = os.path.basename(f).split("-", 1)[1].split(" - ")[0].replace(".txt", "").strip()
            out.append((planet, bool(re.search(r"impassable\s*=\s*yes", s)), [int(x) for x in m.group(1).split()], s))
    return out


def named(sts):
    """ids something names: VPs, province buildings, adjacencies, units, scripts"""
    n = set()
    for _, _, _, s in sts:
        n |= {int(x) for x in re.findall(r"victory_points\s*=\s*\{\s*(\d+)", s)}
        n |= {int(x) for x in re.findall(r"(?m)^\s*(\d+)\s*=\s*\{", s)}
    for l in open("map/adjacencies.csv", encoding="utf-8-sig", errors="replace"):
        q = l.split(";")
        n |= {int(x) for x in q[:4] if x.strip().isdigit()}
    for f in glob.glob("history/units/*.txt"):
        n |= {int(x) for x in re.findall(r"\b(?:location|naval_base)\s*=\s*(\d+)", open(f, encoding="utf-8-sig", errors="replace").read())}
    for f in glob.glob("common/**/*.txt", recursive=True) + glob.glob("events/**/*.txt", recursive=True):
        n |= {int(m.group(2)) for m in re.finditer(r"(province|location|naval_base|capital_province)\s*=\s*\{?\s*(?:id\s*=\s*)?(\d+)",
                                                   open(f, encoding="utf-8-sig", errors="replace").read())}
    return n


def plan(pid, sts, keep):
    area = collections.Counter(pid.ravel().tolist())
    pair = set()
    for a, b in ((pid[:, :-1], pid[:, 1:]), (pid[:-1, :], pid[1:, :])):
        d = a != b
        pair |= set(zip(a[d].tolist(), b[d].tolist()))
    nb = collections.defaultdict(set)
    for a, b in pair:
        nb[a].add(b); nb[b].add(a)
    avg = collections.defaultdict(list)
    for planet, imp, provs, _ in sts:
        if not imp:
            avg[planet] += [area[p] for p in provs]
    into = {}                                          # absorbed id -> keeper id
    for planet, imp, provs, _ in sts:
        if not imp or len(provs) < 2:
            continue
        cap = CAP * (np.mean(avg[planet]) if avg[planet] else np.mean([area[p] for p in provs]))
        inside = set(provs)
        grp = {p: p for p in provs}                    # province -> group head
        mem = {p: {p} for p in provs}
        size = {p: area[p] for p in provs}
        fixed = set()
        while True:
            live = sorted((h for h in mem if h not in fixed), key=lambda h: size[h])
            if not live:
                break
            g = live[0]
            cand = {grp[q] for p in mem[g] for q in nb[p] if q in inside} - {g}
            cand = [h for h in cand if size[h] + size[g] <= cap and not (mem[h] & keep and mem[g] & keep)]
            if not cand:
                fixed.add(g)
                continue
            h = min(cand, key=lambda h: size[h])
            for p in mem[g]:
                grp[p] = h
            mem[h] |= mem.pop(g); size[h] += size.pop(g)
            fixed.discard(h)
        for h, ms in mem.items():
            k = next(iter(ms & keep), None) or max(ms, key=lambda p: area[p])
            for p in ms - {k}:
                into[p] = k
    return into


def fix_coastal():
    """definition.csv coastal flags of impassable-state provinces, from the pixels (merging changes who touches sea)"""
    _, pid, _ = load()
    lines = open("map/definition.csv", encoding="utf-8-sig").read().splitlines(True)
    sea = set(int(l.split(";")[0]) for l in lines if l.split(";")[0].isdigit() and l.split(";")[4] == "sea")
    imp = {p for _, i, provs, _ in states() if i for p in provs}
    is_sea = np.isin(pid, sorted(sea))
    touch = set()
    for a, b, sb in ((pid[:, :-1], pid[:, 1:], is_sea[:, 1:]), (pid[:, 1:], pid[:, :-1], is_sea[:, :-1]),
                     (pid[:-1, :], pid[1:, :], is_sea[1:, :]), (pid[1:, :], pid[:-1, :], is_sea[:-1, :])):
        touch |= set(np.unique(a[sb & (a != b)]).tolist())
    n = 0
    for i, l in enumerate(lines):
        q = l.split(";")
        if q[0].isdigit() and int(q[0]) in imp:
            want = "true" if int(q[0]) in touch else "false"
            if q[5] != want:
                q[5] = want; lines[i] = ";".join(q); n += 1
    open("map/definition.csv", "w", encoding="utf-8", newline="").write("".join(lines))
    print(f"coastal flag fixed on {n} impassable provinces")


def main():
    mode, pid, rows = load()
    sts = states()
    into = plan(pid, sts, named(sts))
    n_imp = sum(len(p) for _, imp, p, _ in sts if imp)
    print(f"impassable provinces {n_imp} -> {n_imp - len(into)}: {len(into)} ids to free")
    if "--dry" in sys.argv:
        return
    lut = np.arange(pid.max() + 1)
    for a, k in into.items():
        lut[a] = k
    newpid = lut[pid]
    out = np.zeros(pid.shape + (3,), np.uint8)
    col = np.zeros((pid.max() + 1,), np.int64)
    for p, c in rows.items():
        col[p] = c
    c = col[newpid]
    out[..., 0], out[..., 1], out[..., 2] = c >> 16, (c >> 8) & 255, c & 255
    old = open("map/provinces.bmp", "rb").read()
    Image.fromarray(out, "RGB").save("map/provinces.bmp")
    import free_province_ids
    try:
        free_province_ids.main()
    except AssertionError:
        open("map/provinces.bmp", "wb").write(old)          # refused before writing anything else
        raise
    free_province_ids.check()
    fix_coastal()


if __name__ == "__main__":
    fix_coastal() if "--coastal" in sys.argv else main()
