"""Concordia, Mandalore's moon (user, 2026-10-19: a new planet for the Death Watch tag): the one-time bootstrap that
puts a new landmass in space before concordia_map.py lays it out. Run from the mod root, once:
    python -B "WIPGFX/plans & scripts/concordia_make.py"
- a disc of radius CON_R px at CON_AT (south-east of Mandalore, 120 px from its centre: open space, 60 px from any
  land), painted over the space (sea) provinces there; each keeps its pixels elsewhere and stays in one piece
- CON_N new land province ids after the last one in definition.csv (new unique colours, continent 5 as Mandalore)
- one state CON_STATE "<id>-Concordia - Concordia.txt" holding them all, owned by DWA (concordia_map.py splits it)
- a new strategic region map/strategicregions/<id>-Concordia.txt (Mandalore's weather) and its name
Refuses to run twice (any Concordia state file) and checks everything before writing."""
import csv, glob, os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from felucia_map import split_area

CON_AT, CON_R, CON_N, CON_STATE = (972, 1700), 28, 48, 1223
CONTINENT = "5"                     # Mandalore's continent in definition.csv
WEATHER_FROM = "map/strategicregions/60-Mandalore.txt"


def main():
    assert not glob.glob("history/states/*-Concordia*.txt"), "Concordia already exists"
    assert not glob.glob(f"history/states/{CON_STATE}-*.txt"), f"state {CON_STATE} exists"
    bmp = np.array(Image.open("map/provinces.bmp").convert("RGB"))
    key = (bmp[..., 0].astype(np.int64) << 16) | (bmp[..., 1].astype(np.int64) << 8) | bmp[..., 2]
    lines = open("map/definition.csv", "rb").read().decode("utf-8-sig").splitlines(keepends=True)
    rows = [l.rstrip("\r\n").split(";") for l in lines]
    defs = {int(r[0]): r for r in rows if r and r[0].isdigit()}
    k2id = {(int(r[1]) << 16) | (int(r[2]) << 8) | int(r[3]): i for i, r in defs.items()}
    H, W = key.shape
    yy, xx = np.mgrid[0:H, 0:W]
    disc = np.hypot(yy - CON_AT[0], xx - CON_AT[1]) <= CON_R
    under = {k2id[k] for k in np.unique(key[disc])}
    assert all(defs[i][4] == "sea" for i in under), f"land under the disc: {under}"
    for i in under:                                                        # the space provinces keep a single piece
        left = (key == next(k for k, v in k2id.items() if v == i)) & ~disc
        assert left.sum() > 2000 and ndi.label(left)[1] == 1, f"sea province {i} would be cut ({left.sum()} px left)"
    first = max(defs) + 1
    ids = list(range(first, first + CON_N))
    rng = np.random.default_rng(1223)
    used = set(k2id)
    cols = []
    while len(cols) < CON_N:                                               # new colours, unique
        c = tuple(int(v) for v in rng.integers(16, 240, 3))
        k = (c[0] << 16) | (c[1] << 8) | c[2]
        if k not in used:
            used.add(k)
            cols.append(c)
    part = split_area(disc, CON_N, rng)
    ys, xs = np.nonzero(disc)
    for n in range(CON_N):
        bmp[ys[part == n], xs[part == n]] = cols[n]
    Image.fromarray(bmp, "RGB").save("map/provinces.bmp")
    end = lines[-1][len(lines[-1].rstrip("\r\n")):] or "\r\n"
    if not lines[-1].endswith(("\n", "\r")):
        lines[-1] += end
    lines += [f"{i};{c[0]};{c[1]};{c[2]};land;false;forest;{CONTINENT}{end}" for i, c in zip(ids, cols)]
    raw = open("map/definition.csv", "rb").read()
    open("map/definition.csv", "wb").write((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"")
                                           + "".join(lines).encode("utf-8"))
    open(f"history/states/{CON_STATE}-Concordia - Concordia.txt", "w", encoding="utf-8", newline="\n").write(
        f"state={{\n\tid={CON_STATE}\n\tname=\"STATE_{CON_STATE}\"\n\tprovinces={{\n\t\t{' '.join(map(str, ids))}\n\t}}\n"
        "\tresources={\n\t\tsteel=8\n\t\tchromium=2\n\t}\n"
        "\thistory = {\n\t\tbuildings = {\n\t\t\tinfrastructure = 3\n\t\t\tindustrial_complex = 2\n\t\t\tarms_factory = 3\n"
        "\t\t\tair_base = 1\n\t\t}\n\t\towner = DWA\n\t\tadd_core_of = DWA\n\t}\n"
        "\tmanpower = 450000\n\tstate_category = large_planet\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}\n")
    sr = max(int(os.path.basename(f).split("-")[0]) for f in glob.glob("map/strategicregions/*.txt")) + 1
    weather = re.search(r"\n\tweather=\{.*\n\t\}\n", open(WEATHER_FROM, encoding="utf-8-sig").read(), re.S).group(0)
    open(f"map/strategicregions/{sr}-Concordia.txt", "w", encoding="utf-8", newline="\r\n").write(
        f"strategic_region={{\n\tid={sr}\n\tname=\"STRATEGICREGION_{sr}\"\n\tprovinces={{\n\t\t{' '.join(map(str, ids))} \n\t}}"
        f"{weather}}}\n")
    loc = "localisation/english/strategic_region_names_l_english.yml"
    s = open(loc, encoding="utf-8-sig").read()
    open(loc, "w", encoding="utf-8-sig", newline="\r\n").write(s.rstrip("\n") + f'\n STRATEGICREGION_{sr}:0 "Concordia"\n')
    print(f"Concordia: provinces {ids[0]}-{ids[-1]}, state {CON_STATE}, strategic region {sr}, over sea {sorted(under)}")


if __name__ == "__main__":
    main()
