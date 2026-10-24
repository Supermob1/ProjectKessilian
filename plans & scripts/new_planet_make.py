"""New planets in space (the user, 2026-10-24: the 29 Clone Wars planets of step 2 of "things to be done after we did
first pass on all the planets.txt"): the one-time bootstrap that puts each new landmass on the galaxy map before its
<planet>_map.py lays it out. Generalised from concordia_make.py. Run from the mod root, once:
    python -B "WIPGFX/plans & scripts/new_planet_make.py" [--dry]
For each planet of PLANETS:
- a disc of radius R px at its map position (x east, z north; from its canon grid square fitted on the existing planets,
  moved to the nearest open space at least 60 px from land), painted over the space (sea) provinces there; each keeps
  its pixels elsewhere and stays in one piece
- N new land province ids after the last one in definition.csv (new unique colours, the nearest planet's continent)
- one state "<id>-<Planet>.txt" holding them all (its map script splits it), owned by the given tag
- a strategic region with the nearest planet's weather, named after the planet
- a hyperlane (map/adjacencies.csv) to the nearest existing planet and to LANE_TO when given; the map script re-anchors
  its ends, then run tools/hoi4_country_editor/gen_hyperlanes.py
Refuses if any of the planets exists already, and checks everything before writing."""
import glob, math, os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from felucia_map import split_area

R, N = 32, 56
FIRST_STATE = 1701
# name: ((x, z) map position, canon grid square, owner, extra lane to)   owner None = the nearest planet's owner (uninhabited)
PLANETS = {
    "Rattatak": ((285, 548), "H-16", "RAT", None), "Vassek": ((424, 452), "I-17", "CIS", None),
    "Lotho Minor": ((536, 487), "I-17", "LTM", None), "Bardotta": ((735, 1162), "K-13", "BDT", None),
    "Scipio": ((844, 2693), "K-5", "IBC", None), "Carlac": ((729, 2745), "K-5", "CLC", None),
    "Aleen": ((975, 2280), "L-7", "ALE", None), "Qiilura": ((910, 2466), "L-7", "CIS", None),
    "Kiros": ((1094, 2242), "L-8", "KIR", None), "Shili": ((865, 2185), "L-8", "REP", None),
    "Brentaal IV": ((863, 2019), "L-9", "REP", None), "Skako": ((1247, 1985), "L-9", "TCU", None),
    "Skako Minor": ((1371, 1985), "L-9", "TCU", "Skako"), "Devaron": ((1185, 1259), "M-13", "REP", None),
    "Dagobah": ((1290, 218), "M-19", None, None), "Praesitlyn": ((1401, 145), "M-19", "REP", None),
    "Rugosa": ((1653, 422), "O-17", "TOY", None), "Abafar": ((1788, 2500), "O-6", "ABA", None),
    "Orto Plutonia": ((1994, 174), "P-19", "PAN", "Pantora"), "Gaftikar": ((1861, 2842), "P-5", "CIS", None),
    "Wasskah": ((1976, 1961), "P-9", "HSS", "Kashyyyk"), "Nelvaan": ((2028, 713), "Q-16", "NEL", None),
    "Ord Radama": ((1987, 2770), "Q-5", "CIS", None), "Maridun": ((2004, 2571), "Q-6", "MRD", None),
    "Quell": ((2128, 2577), "Q-6", "REP", None), "Vjun": ((1912, 2488), "Q-6", "CIS", None),
    "Aargonar": ((2007, 2385), "Q-7", "REP", None), "Vanqor": ((2090, 2700), "R-5", None, None),
    "Drongar": ((2613, 2877), "T-5", "REP", None),
}


def main(dry):
    for p in PLANETS:
        assert not glob.glob(f"history/states/*-{p}.txt") and not glob.glob(f"history/states/*-{p} - *.txt"), f"{p} exists"
    assert not any(glob.glob(f"history/states/{FIRST_STATE + i}-*.txt") for i in range(len(PLANETS))), "state ids taken"
    bmp = np.array(Image.open("map/provinces.bmp").convert("RGB"))
    key = (bmp[..., 0].astype(np.int64) << 16) | (bmp[..., 1].astype(np.int64) << 8) | bmp[..., 2]
    H, W = key.shape
    raw = open("map/definition.csv", "rb").read()
    lines = raw.decode("utf-8-sig").splitlines(keepends=True)
    defs = {int(q[0]): q for q in (l.rstrip("\r\n").split(";") for l in lines) if q and q[0].isdigit()}
    k2id = {(int(q[1]) << 16) | (int(q[2]) << 8) | int(q[3]): i for i, q in defs.items()}
    cols_sorted = np.array(sorted(k2id)); ids_sorted = np.array([k2id[c] for c in cols_sorted.tolist()])
    pid = ids_sorted[np.searchsorted(cols_sorted, key)]

    # existing planets: strategic regions with land, their centres, owners, weather, coastal passable provinces
    st_of, owner_of, imp = {}, {}, set()
    for f in glob.glob("history/states/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        m = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        o = re.search(r"owner\s*=\s*(\w+)", s)
        for q in (m.group(1).split() if m else []):
            st_of[int(q)] = f
            owner_of[int(q)] = o.group(1) if o else None
            if re.search(r"impassable\s*=\s*yes", s):
                imp.add(int(q))
    regions = []
    for f in glob.glob("map/strategicregions/*.txt"):
        s = open(f, encoding="utf-8-sig").read()
        provs = [int(q) for q in re.search(r"provinces\s*=\s*\{([^}]*)\}", s).group(1).split()]
        land = [p for p in provs if defs[p][4] == "land"]
        if land:
            regions.append((f, land))
    centre = {}
    idx = ndi.find_objects(pid)
    for p, sl in enumerate(idx, 1):
        if sl is not None:
            ys, xs = np.nonzero(pid[sl] == p)
            centre[p] = (ys.mean() + sl[0].start, xs.mean() + sl[1].start)
    planet_c = []
    for f, land in regions:
        ys = np.mean([centre[p][0] for p in land if p in centre]); xs = np.mean([centre[p][1] for p in land if p in centre])
        planet_c.append((f, land, ys, xs))

    yy, xx = np.mgrid[0:H, 0:W]
    first = max(defs) + 1
    rng = np.random.default_rng(1701)
    used = set(k2id)
    sr_next = max(int(os.path.basename(f).split("-")[0]) for f in glob.glob("map/strategicregions/*.txt")) + 1
    adj_new, plan = [], []
    disc_all = np.zeros((H, W), bool)
    for n_, (name, ((x, z), grid, owner, lane_to)) in enumerate(PLANETS.items()):
        def fits(row, col):                     # only space under it, apart from the others, no space province cut
            disc = np.hypot(yy - row, xx - col) <= R
            if (np.hypot(yy - row, xx - col) <= R + 30)[disc_all].any():
                return None
            for i in np.unique(pid[disc]).tolist():
                left = (pid == i) & ~disc & ~disc_all
                if defs[i][4] != "sea" or left.sum() < 1500 or ndi.label(left)[1] != 1:
                    return None
            return disc
        for rad, a in [(0, 0)] + [(r_, k_) for r_ in range(6, 61, 6) for k_ in range(12)]:   # nudge up to 60 px
            row, col = int(round(H - 1 - z + rad * math.sin(math.pi * a / 6))), int(round(x + rad * math.cos(math.pi * a / 6)))
            disc = fits(row, col)
            if disc is not None:
                break
        assert disc is not None, f"{name}: no room within 60 px of {x, z}"
        disc_all |= disc
        ids = list(range(first, first + N)); first += N
        cols = []
        while len(cols) < N:
            c = tuple(int(v) for v in rng.integers(16, 240, 3))
            k = (c[0] << 16) | (c[1] << 8) | c[2]
            if k not in used:
                used.add(k); cols.append(c)
        near = sorted(planet_c, key=lambda t: math.hypot(t[2] - row, t[3] - col))
        ends = []                                                         # (province, its centre, planet name)
        for f, land, ry, rx in [near[0]] + [t for t in near if lane_to and planet_label(t[0]) == lane_to][:1]:
            cand = [p for p in land if defs[p][5] == "true" and p not in imp and p in centre]
            to = min(cand, key=lambda p: math.hypot(centre[p][0] - row, centre[p][1] - col))
            if planet_label(f) not in [e[2] for e in ends]:
                ends.append((to, centre[to], planet_label(f)))
        if lane_to in PLANETS:                                            # a new partner (made earlier in the table)
            q_ = next(q for q in plan if q["name"] == lane_to)
            ends.append((q_["ids"][0], q_["rc"], lane_to))
        assert not lane_to or lane_to in [e[2] for e in ends], f"{name}: no lane to {lane_to}"
        lanes = []
        for to, (ty, tx), label in ends:
            through = None
            for t_ in np.linspace(0.5, 0.9, 9):                          # a space province on the segment, mid first
                for s_ in (t_, 1 - t_):
                    py, px = int(row + (ty - row) * s_), int(col + (tx - col) * s_)
                    q = int(pid[py, px])
                    if defs[q][4] == "sea" and not disc_all[py, px]:
                        through = q; break
                if through:
                    break
            assert through, f"{name}: no space province between it and {label}"
            lanes.append((to, through, label))
        f0 = near[0][0]
        weather = re.search(r"\n\s*weather\s*=\s*\{.*\n\t\}\n", open(f0, encoding="utf-8-sig").read(), re.S)
        cont = defs[ends[0][0]][7]
        own = owner or owner_of[ends[0][0]]
        plan.append(dict(name=name, ids=ids, cols=cols, disc=disc, sid=FIRST_STATE + n_, sr=sr_next + n_, owner=own,
                         lanes=lanes, rc=(row, col), weather=weather.group(0) if weather else "\n", cont=cont, grid=grid))
        print(f"{name:14s} {grid:5s} at {col, H - 1 - row} state {FIRST_STATE + n_} region {sr_next + n_} ids {ids[0]}-{ids[-1]} owner {own} "
              f"lanes to {', '.join(l for _, _, l in lanes)}")
    if dry:
        print("dry run: nothing written"); return

    for p in plan:
        part = split_area(p["disc"], N, rng)
        ys, xs = np.nonzero(p["disc"])
        for n in range(N):
            bmp[ys[part == n], xs[part == n]] = p["cols"][n]
    Image.fromarray(bmp, "RGB").save("map/provinces.bmp")
    end = "\r\n" if lines[-1].endswith("\r\n") or "\r\n" in lines[0] else "\n"
    if not lines[-1].endswith(("\n", "\r")):
        lines[-1] += end
    for p in plan:
        lines += [f"{i};{c[0]};{c[1]};{c[2]};land;false;plains;{p['cont']}{end}" for i, c in zip(p["ids"], p["cols"])]
    open("map/definition.csv", "wb").write((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + "".join(lines).encode("utf-8"))
    loc = "localisation/english/strategic_region_names_l_english.yml"
    s = open(loc, encoding="utf-8-sig").read().rstrip("\n") + "\n"
    adj = open("map/adjacencies.csv", encoding="utf-8-sig", newline="").read()
    adj_lines = adj.splitlines(keepends=True)
    tail = [l for l in adj_lines if l.strip().startswith("-1")]           # the engine's end marker stays last
    body = [l for l in adj_lines if not l.strip().startswith("-1")]
    aend = "\r\n" if body and body[0].endswith("\r\n") else "\n"
    for p in plan:
        open(f"history/states/{p['sid']}-{p['name']}.txt", "w", encoding="utf-8", newline="\n").write(
            f"state={{\n\tid={p['sid']}\n\tname=\"STATE_{p['sid']}\"\n\tprovinces={{\n\t\t{' '.join(map(str, p['ids']))}\n\t}}\n"
            "\thistory = {\n\t\tbuildings = {\n\t\t\tinfrastructure = 2\n\t\t}\n"
            f"\t\towner = {p['owner']}\n\t\tadd_core_of = {p['owner']}\n\t}}\n"
            "\tmanpower = 100000\n\tstate_category = wasteland_sector\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}\n")
        open(f"map/strategicregions/{p['sr']}-{p['name']}.txt", "w", encoding="utf-8", newline="\r\n").write(
            f"strategic_region={{\n\tid={p['sr']}\n\tname=\"STRATEGICREGION_{p['sr']}\"\n\tprovinces={{\n\t\t"
            f"{' '.join(map(str, p['ids']))} \n\t}}{p['weather']}}}\n")
        s += f' STRATEGICREGION_{p["sr"]}:0 "{p["name"]}"\n'
        for to, through, f in p["lanes"]:
            a = p["ids"][0]
            body.append(f"{a};{to};sea;{through};-1;-1;-1;-1;HOD_lane_{a}_{to};{p['name']} to {f}{aend}")
    open(loc, "w", encoding="utf-8-sig", newline="\r\n").write(s)
    open("map/adjacencies.csv", "w", encoding="utf-8", newline="").write("".join(body + tail))
    print(f"wrote {len(plan)} planets: provinces {plan[0]['ids'][0]}-{plan[-1]['ids'][-1]}, states {plan[0]['sid']}-{plan[-1]['sid']}")


def planet_label(f):
    """a strategic region's planet name (its localisation)"""
    sr = os.path.basename(f).split("-")[0]
    for l in open("localisation/english/strategic_region_names_l_english.yml", encoding="utf-8-sig"):
        m = re.match(rf'\s*STRATEGICREGION_{sr}:\d*\s*"([^"]*)"', l)
        if m:
            return m.group(1)
    return os.path.basename(f)


if __name__ == "__main__":
    main("--dry" in sys.argv)
