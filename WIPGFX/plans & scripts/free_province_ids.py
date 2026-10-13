"""Drop every province of map/definition.csv that has no pixels left in map/provinces.bmp (a planet redrawn with
fewer provinces, e.g. korriban_map.py) and keep the ids gapless, as HOI4 needs: the highest ids move down into the
holes. Rewrites every place the mod names a province: the map files, strategic regions, state histories (provinces,
victory points, province buildings), unit histories and victory point names. Refuses if a moved or dropped id appears
anywhere else under common/ or events/ (scripts would then point at the wrong province).

    python "WIPGFX/plans & scripts/free_province_ids.py"
"""
import glob, os, re, sys
import numpy as np
from PIL import Image

ROWS = "map/definition.csv"


def rw(path, fn):
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig", errors="surrogateescape")
    t = fn(s)
    if t != s:
        open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + t.encode("utf-8", errors="surrogateescape"))


def plan():
    lines = open(ROWS, encoding="utf-8-sig").read().splitlines()
    px = np.asarray(Image.open("map/provinces.bmp").convert("RGB")).reshape(-1, 3).astype(np.int64)
    present = set(np.unique(px[:, 0] * 65536 + px[:, 1] * 256 + px[:, 2]).tolist())
    ids = {}
    for l in lines:
        q = l.split(";")
        if q[0].isdigit() and int(q[0]) > 0:
            ids[int(q[0])] = int(q[1]) * 65536 + int(q[2]) * 256 + int(q[3])
    assert sorted(ids) == list(range(1, len(ids) + 1)), "definition.csv ids are not gapless to begin with"
    drop = sorted(p for p, c in ids.items() if c not in present)
    move = {}
    tops = sorted((p for p in ids if p not in drop), reverse=True)
    for h in drop:
        if tops and tops[0] > h:
            move[tops.pop(0)] = h
    return drop, move


def main():
    drop, move = plan()
    if not drop:
        print("nothing to free")
        return
    dropped = set(drop)
    touched = dropped | set(move)
    # scripts naming any of these ids by number would silently break: refuse
    num = re.compile(r"(?<![\w.])(\d+)(?![\w.])")
    risky = []
    for f in glob.glob("common/**/*.txt", recursive=True) + glob.glob("events/**/*.txt", recursive=True):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        for mt in re.finditer(r"(province|location|naval_base|capital_province)\s*=\s*\{?\s*(?:id\s*=\s*)?(\d+)", s):
            if int(mt.group(2)) in touched:
                risky.append((f, mt.group(0)))
    assert not risky, f"scripts name provinces that would move: {risky[:10]}"
    ren = lambda p: str(move.get(int(p), int(p)))
    # definition.csv
    def defs(s):
        out = []
        for l in s.splitlines(True):
            q = l.split(";")
            if q[0].isdigit() and int(q[0]) in dropped:
                continue
            if q[0].isdigit():
                q[0] = ren(q[0])
            out.append(";".join(q))
        head = [l for l in out if not l.split(";")[0].isdigit()]
        body = sorted((l for l in out if l.split(";")[0].isdigit()), key=lambda l: int(l.split(";")[0]))
        end = "\r\n" if body[0].endswith("\r\n") else "\n"
        return "".join(head) + "".join(l if l.endswith(("\n", "\r\n")) else l + end for l in body)
    rw(ROWS, defs)
    # adjacencies.csv: from;to;type;through;...
    def adj(s):
        out = []
        for l in s.splitlines(True):
            q = l.split(";")
            if len(q) > 3 and q[0].lstrip("-").isdigit() and q[1].lstrip("-").isdigit():
                if int(q[0]) in dropped or int(q[1]) in dropped:
                    continue
                q[0], q[1] = ren(q[0]), ren(q[1])
                if q[3].lstrip("-").isdigit():
                    q[3] = "-1" if int(q[3]) in dropped else ren(q[3])
            out.append(";".join(q))
        return "".join(out)
    rw("map/adjacencies.csv", adj)
    # buildings.txt: state;type;x;y;z;rot;adjacent sea province
    def bld(s):
        out = []
        for l in s.splitlines(True):
            q = l.rstrip("\r\n").split(";")
            if len(q) == 7 and q[6].strip().isdigit():
                q[6] = "0" if int(q[6]) in dropped else ren(q[6])
                l = ";".join(q) + l[len(l.rstrip("\r\n")):]
            out.append(l)
        return "".join(out)
    rw("map/buildings.txt", bld)
    # unitstacks.txt: province;...   supply_nodes.txt: level province
    rw("map/unitstacks.txt", lambda s: "".join(
        (";".join([ren(l.split(";")[0])] + l.split(";")[1:]) if l.split(";")[0].isdigit() else l)
        for l in s.splitlines(True) if not (l.split(";")[0].isdigit() and int(l.split(";")[0]) in dropped)))
    rw("map/supply_nodes.txt", lambda s: "".join(
        (" ".join([l.split()[0], ren(l.split()[1])]) + "\n" if len(l.split()) > 1 else l)
        for l in s.splitlines(True) if not (len(l.split()) > 1 and int(l.split()[1]) in dropped)))
    # railways.txt: level count p1 .. pn (a dropped province cuts the line)
    def rails(s):
        out = []
        for l in s.splitlines():
            q = l.split()
            if len(q) < 3:
                continue
            seg = []
            for p in q[2:]:
                if int(p) in dropped:
                    if len(seg) > 1:
                        out.append((q[0], seg))
                    seg = []
                else:
                    seg.append(ren(p))
            if len(seg) > 1:
                out.append((q[0], seg))
        return "".join(f"{lvl} {len(sg)} {' '.join(sg)} \n" for lvl, sg in out)
    rw("map/railways.txt", rails)
    # lists of provinces inside braces
    def plist(m_):                                    # ids renamed or dropped in place, the layout kept
        body = re.sub(r"[ 	]*(?<!\S)(\d+)(?!\S)", lambda t: "" if int(t.group(1)) in dropped
                      else t.group(0)[:t.start(1) - t.start(0)] + ren(t.group(1)), m_.group(2))
        return m_.group(1) + body + m_.group(3)
    for f in ["map/airports.txt", "map/rocketsites.txt"]:
        rw(f, lambda s: re.sub(r"(\b\d+\s*=\s*\{)([^{}]*)(\})", plist, s))
    for f in glob.glob("map/strategicregions/*.txt"):
        rw(f, lambda s: re.sub(r"(provinces\s*=\s*\{)([^{}]*)(\})", plist, s))
    for f in glob.glob("history/states/*.txt"):
        def st(s):
            s = re.sub(r"(provinces\s*=\s*\{)([^{}]*)(\})", plist, s)
            s = re.sub(r"(victory_points\s*=\s*\{\s*)(\d+)", lambda m_: m_.group(1) + ren(m_.group(2)), s)
            return re.sub(r"(?m)^(\s*)(\d+)(\s*=\s*\{)", lambda m_: m_.group(1) + ren(m_.group(2)) + m_.group(3), s)
        rw(f, st)
    for f in glob.glob("history/units/*.txt"):
        rw(f, lambda s: re.sub(r"\b(location|naval_base)(\s*=\s*)(\d+)\b",
                               lambda m_: m_.group(1) + m_.group(2) + ren(m_.group(3)), s))
    for f in glob.glob("localisation/**/*victory_points*.yml", recursive=True):
        rw(f, lambda s: "".join(l for l in s.splitlines(True)
                                if not (re.match(r"\s*VICTORY_POINTS_(\d+):", l) and int(re.match(r"\s*VICTORY_POINTS_(\d+):", l).group(1)) in dropped)))
        rw(f, lambda s: re.sub(r"(VICTORY_POINTS_)(\d+)(:)", lambda m_: m_.group(1) + ren(m_.group(2)) + m_.group(3), s))
    print(f"dropped {len(drop)} provinces, moved {len(move)} ids down: {min(move, default=0)}..{max(move, default=0)}")
    return move


def check():
    """every id 1..N used once by pixels, in definition order, and every state province exists"""
    lines = [l.split(";") for l in open(ROWS, encoding="utf-8-sig").read().splitlines() if l.split(";")[0].isdigit()]
    ids = [int(q[0]) for q in lines if int(q[0]) > 0]
    assert ids == list(range(1, len(ids) + 1)), "ids not gapless"
    px = np.asarray(Image.open("map/provinces.bmp").convert("RGB")).reshape(-1, 3).astype(np.int64)
    present = set(np.unique(px[:, 0] * 65536 + px[:, 1] * 256 + px[:, 2]).tolist())
    cols = {int(q[0]): int(q[1]) * 65536 + int(q[2]) * 256 + int(q[3]) for q in lines if int(q[0]) > 0}
    missing = [p for p, c in cols.items() if c not in present]
    assert not missing, f"{len(missing)} ids without pixels"
    n = len(ids)
    for f in glob.glob("history/states/*.txt") + glob.glob("map/strategicregions/*.txt"):
        m_ = re.search(r"provinces\s*=\s*\{([^{}]*)\}", open(f, encoding="utf-8-sig", errors="replace").read())
        bad = [t for t in (m_.group(1).split() if m_ else []) if int(t) > n]
        assert not bad, f"{f}: {bad}"
    print(f"ok: {n} provinces, gapless, all with pixels")


if __name__ == "__main__":
    check() if "--check" in sys.argv else (main(), check())
