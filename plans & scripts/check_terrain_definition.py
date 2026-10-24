"""Check definition.csv's terrain column against terrain.bmp (plan step 6: terrain.bmp prevails).

    python -B "WIPGFX/plans & scripts/check_terrain_definition.py"          report only
    python -B "WIPGFX/plans & scripts/check_terrain_definition.py" --fix    rewrite mismatching land rows of definition.csv

A province's terrain.bmp type is the gameplay type (common/terrain/00_terrain.txt `terrain = {}` block) of the palette
index covering most of its pixels. Checked: provinces.bmp colours all in definition.csv, terrain.bmp indices all defined,
both maps the same size. --fix only touches land rows of passable states; impassable provinces keep their terrain (their
pixels are often water or ice art, which is not a land terrain), sea / lake rows are never touched.
"""
import collections, csv, glob, io, re, sys
import numpy as np
from PIL import Image

MAP = "map"


def palette_types():
    s = open("common/terrain/00_terrain.txt", encoding="utf-8-sig").read()
    block = s[s.index("\nterrain = {"):]
    return {int(c): t for t, c in re.findall(r"type\s*=\s*(\w+)\s+color\s*=\s*\{\s*(\d+)\s*\}", block)}


def impassable_provinces():
    out = set()
    for f in glob.glob("history/states/*.txt"):
        s = open(f, encoding="utf-8-sig").read()
        if re.search(r"impassable\s*=\s*yes", s):
            m = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
            out.update(int(x) for x in m.group(1).split())
    return out


def main(fix):
    types = palette_types()
    prov = np.asarray(Image.open(f"{MAP}/provinces.bmp").convert("RGB"), dtype=np.uint32)
    ter_im = Image.open(f"{MAP}/terrain.bmp")
    assert ter_im.mode == "P", f"terrain.bmp must be 8-bit indexed, is {ter_im.mode}"
    ter = np.asarray(ter_im)
    assert prov.shape[:2] == ter.shape, f"size mismatch: provinces {prov.shape[:2]} terrain {ter.shape}"
    raw = open(f"{MAP}/definition.csv", "rb").read()
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in text else "\n"
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=";")]
    by_rgb = {(int(r[1]) << 16) | (int(r[2]) << 8) | int(r[3]): i for i, r in enumerate(rows) if r and r[0].isdigit()}

    key = (prov[..., 0] << 16) | (prov[..., 1] << 8) | prov[..., 2]
    errors = 0
    unknown_px = set(np.unique(ter).tolist()) - set(types)
    if unknown_px:
        errors += 1
        print("ERROR terrain.bmp indices with no 00_terrain.txt entry:", sorted(unknown_px))
    keys, inv = np.unique(key.ravel(), return_inverse=True)
    missing = [k for k in keys.tolist() if k not in by_rgb]
    if missing:
        errors += 1
        print(f"ERROR {len(missing)} provinces.bmp colours not in definition.csv, e.g. {[hex(k) for k in missing[:5]]}")

    # dominant terrain.bmp index per province colour
    counts = np.zeros((len(keys), 256), dtype=np.int64)
    np.add.at(counts, (inv, ter.ravel()), 1)
    dom = counts.argmax(1)
    imp = impassable_provinces()
    tally, changed = collections.Counter(), 0
    for k, d in zip(keys.tolist(), dom.tolist()):
        i = by_rgb.get(k)
        if i is None:
            continue
        r = rows[i]
        pid, kind, cur = int(r[0]), r[4], r[6]
        want = types.get(d)
        if kind != "land" or want is None or want == cur or want == "ocean":
            continue
        tally[(pid in imp, cur, want)] += 1
        if fix and pid not in imp:
            r[6] = want
            changed += 1
    for (is_imp, cur, want), n in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"{'impassable' if is_imp else 'passable  '} {cur:>9} -> {want:<9} {n}")
    print(f"{sum(n for (i, _, _), n in tally.items() if not i)} passable / "
          f"{sum(n for (i, _, _), n in tally.items() if i)} impassable land provinces differ from terrain.bmp")
    if fix and changed:
        out = io.StringIO()
        w = csv.writer(out, delimiter=";", lineterminator=nl)
        w.writerows(rows)
        bom = raw.startswith(b"\xef\xbb\xbf")
        open(f"{MAP}/definition.csv", "wb").write((b"\xef\xbb\xbf" if bom else b"") + out.getvalue().encode("utf-8"))
        print(f"fixed {changed} rows")
    return errors


if __name__ == "__main__":
    sys.exit(1 if main("--fix" in sys.argv) else 0)
