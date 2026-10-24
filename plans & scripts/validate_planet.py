"""Read-only checks of one planet (a battlefield redrawn by <planet>_map.py, or any planet with state files named
"<id>-<Planet> - <name>.txt"), and a labelled preview: states coloured, impassable states dark, victory points ringed.
    python "WIPGFX/plans & scripts/validate_planet.py" kadavo        (or raxus_prime, "Raxus Prime", ...)
Writes only WIPGFX/Assets/<planet>_check.png. Prints ERROR / WARN lines (file:line where known) and exits 1 on errors.
Checks: definition.csv ids/colours (map-wide), province pixels, provinces in exactly one state and one strategic
region, planet land without a state, state id clashes, the map script's state ids, owners/cores, state connectivity,
victory points and province buildings inside their state, X crossings (korriban_map.uncross's rule), coastal flags,
terrain names, zones JSON terrain, units on the planet, adjacencies, STATE_/VICTORY_POINTS_ localisation.
"""
import csv, glob, importlib, json, math, os, re, sys
sys.dont_write_bytecode = True                                            # the __pycache__ is tracked in git
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(HERE)
from felucia_tribes import block  # noqa: E402

errors, warns = [], []
err = lambda where, msg: errors.append(f"ERROR {where}: {msg}")
warn = lambda where, msg: warns.append(f"WARN  {where}: {msg}")


def read(path):
    return open(path, encoding="utf-8-sig", errors="replace").read().replace("\r\n", "\n")


def line_of(path, pattern, text=None):
    text = read(path) if text is None else text
    m = re.search(pattern, text, re.M)
    return f"{path}:{text.count(chr(10), 0, m.start()) + 1}" if m else path


def definition():
    rows, colours = {}, {}
    for n, r in enumerate(csv.reader(open("map/definition.csv", encoding="utf-8-sig"), delimiter=";"), 1):
        if not r or not r[0].strip().isdigit():
            continue
        p = int(r[0])
        if len(r) < 8:
            err(f"map/definition.csv:{n}", f"province {p} has {len(r)} columns, need 8")
            continue
        if p in rows:
            err(f"map/definition.csv:{n}", f"province id {p} defined twice")
        c = (int(r[1]) << 16) | (int(r[2]) << 8) | int(r[3])
        if c in colours and p:
            err(f"map/definition.csv:{n}", f"province {p} reuses the colour of province {colours[c]}")
        colours.setdefault(c, p)
        rows[p] = dict(line=n, colour=c, type=r[4], coastal=r[5] == "true", terrain=r[6])
    gaps = sorted(set(range(max(rows) + 1)) - set(rows))
    if gaps:
        err("map/definition.csv", f"ids not gapless (HOI4 needs 0..N): missing {gaps[:10]}")
    return rows


def province_ids(rows):
    rgb = np.asarray(Image.open("map/provinces.bmp").convert("RGB")).astype(np.int32)
    packed = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    cols = np.array(sorted(r["colour"] for p, r in rows.items() if p))
    ids = np.array([p for c, p in sorted((r["colour"], p) for p, r in rows.items() if p)])
    i = np.clip(np.searchsorted(cols, packed), 0, len(cols) - 1)
    pid = np.where(cols[i] == packed, ids[i], -1)
    if (pid < 0).any():
        y, x = np.argwhere(pid < 0)[0]
        err("map/provinces.bmp", f"{int((pid < 0).sum())} px in colours missing from definition.csv, first at x={x} y={y}")
    return pid


def states():
    out, by_id = {}, {}
    for f in sorted(glob.glob("history/states/*.txt")):
        f = f.replace("\\", "/")
        s = read(f)
        m = re.search(r"\bid\s*=\s*(\d+)", s)
        if not m:
            err(f, "no id")
            continue
        sid = int(m.group(1))
        fm = re.match(r"(\d+)-(.*?)(?: - |\.txt$)", os.path.basename(f))     # "<id>-<Planet> - <name>" or "<id>-<Planet>"
        if fm and int(fm.group(1)) != sid:
            warn(line_of(f, r"\bid\s*="), f"file name says {fm.group(1)}, id = {sid}")
        by_id.setdefault(sid, []).append(f)
        pb = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        hist = block(s, "history")
        out[f] = dict(id=sid, text=s, planet=fm.group(2) if fm else "",
                      provinces=[int(x) for x in pb.group(1).split()] if pb else [],
                      owner=(re.search(r"\bowner\s*=\s*(\w+)", hist) or [None, None])[1],
                      cores=re.findall(r"\badd_core_of\s*=\s*(\w+)", hist),
                      impassable=bool(re.search(r"\bimpassable\s*=\s*yes", s)),
                      vps=[(int(a), b) for a, b in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+([\d.]+)\s*\}", hist)],
                      prov_buildings=[int(x) for x in re.findall(r"\n\s*(\d+)\s*=\s*\{", block(hist, "buildings"))])
    for sid, fs in by_id.items():
        if len(fs) > 1:
            err(fs[0], f"state id {sid} also used by {', '.join(fs[1:])}")
    return out


def planet_files(sts, name):
    want = name.replace("_", " ").lower()
    files = [f for f, st in sts.items() if st["planet"].lower() == want]
    if not files:
        sys.exit(f"no state files named '<id>-{name.replace('_', ' ')} - <name>.txt' in history/states")
    return files, sts[files[0]]["planet"]


def script_ids(name, planet_ids):
    """the state ids <planet>_map.py would write: each must be a state of this planet (kadavo_map.py once named
    Coruscant's states 123-130 and would have overwritten them)"""
    path = os.path.join(HERE, f"{name.lower().replace(' ', '_')}_map.py")
    if not os.path.exists(path):
        return
    try:
        mod = importlib.import_module(os.path.basename(path)[:-3])
    except Exception as e:                                               # noqa: BLE001
        err(os.path.relpath(path), f"cannot import ({type(e).__name__}: {e}); its state ids were not checked")
        return
    rel = (os.path.relpath(mod.__file__) if os.path.splitdrive(mod.__file__)[0].lower() == os.path.splitdrive(os.getcwd())[0].lower() else mod.__file__).replace("\\", "/")
    code = [re.sub(r"#.*", "", x) for x in read(mod.__file__).split("\n")]     # shortcut: also cuts '#' inside strings

    def where(sid, also=""):
        n = next((i for i, x in enumerate(code, 1) if re.search(rf"\b{sid}\b", x) and also in x), None)
        return f"{rel}:{n}" if n else (where(sid) if also else rel)
    used = {}
    for attr in ("STATE_NAMES", "SEEDS"):
        for sid in getattr(mod, attr, {}) or {}:
            used.setdefault(sid, attr)
    for attr in ("IMPASSABLE", "CRATER_STATES"):
        for sid in getattr(mod, attr, ()) or ():
            used.setdefault(sid, attr)
    for f in getattr(mod, "FEATURES", ()) or ():
        if isinstance(f[2], int):
            used.setdefault(f[2], f"FEATURES ({f[0]})")
    for v in getattr(mod, "VPS", ()) or ():
        used.setdefault(v[0], f"VPS ({v[2]})")
    if isinstance(getattr(mod, "CAPITAL", None), int):
        used.setdefault(mod.CAPITAL, "CAPITAL")
    names = getattr(mod, "STATE_NAMES", None)
    for sid, attr in sorted(used.items()):
        at = where(sid, attr.split("(")[1][:-1] if "(" in attr else "")
        if sid not in planet_ids:
            other = next((f for f in ALL if ALL[f]["id"] == sid), None)
            (err if other else warn)(at, f"{attr} names state {sid}, " +
                                     (f"which is {other}" if other else "which has no state file yet (would be new)"))
        elif names is not None and sid not in names:
            err(at, f"{attr} names state {sid}, missing from STATE_NAMES (the script would fail mid-write)")


def loc_keys():
    keys = set()
    for f in glob.glob("localisation/english/**/*.yml", recursive=True):
        keys.update(re.findall(r'^\s*([\w.]+):\d*\s*"', read(f), re.M))
    return keys


def preview(path, pid, sl, pst, sts, files, planet_mask, vps):
    sub = pid[sl]
    k = max(2, min(8, 900 // max(sub.shape)))
    img = np.full(sub.shape + (3,), 24, np.uint8)
    st_of = np.full(sub.shape, -1, np.int32)
    for i, f in enumerate(files):
        rng = np.random.default_rng(sts[f]["id"])
        c = rng.integers(70, 230, 3)
        if sts[f]["impassable"]:
            c = c // 3 + 20
        m = np.isin(sub, sts[f]["provinces"]) & planet_mask[sl]
        img[m] = c
        st_of[m] = i
    big = np.repeat(np.repeat(img, k, 0), k, 1)
    sp = np.repeat(np.repeat(sub, k, 0), k, 1)
    ss = np.repeat(np.repeat(st_of, k, 0), k, 1)
    pb = np.zeros(sp.shape, bool)
    sb = np.zeros(sp.shape, bool)
    pb[:-1] |= sp[:-1] != sp[1:]
    pb[:, :-1] |= sp[:, :-1] != sp[:, 1:]
    sb[:-1] |= ss[:-1] != ss[1:]
    sb[:, :-1] |= ss[:, :-1] != ss[:, 1:]
    big[pb] = big[pb] * 3 // 4
    big[ndi.binary_dilation(sb)] = 0
    legend_w = 340
    canvas = Image.new("RGB", (big.shape[1] + legend_w, max(big.shape[0], 20 + 16 * len(files))), (16, 16, 16))
    canvas.paste(Image.fromarray(big), (0, 0))
    d = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(14)
    small = ImageFont.load_default(11)
    for i, f in enumerate(files):
        if (st_of == i).any():                                             # label at the point deepest inside the state
            y, x = np.unravel_index(np.argmax(ndi.distance_transform_edt(np.pad(st_of == i, 1))[1:-1, 1:-1]), st_of.shape)
            d.text(((x + 0.5) * k, (y + 0.5) * k), str(sts[f]["id"]), fill="white", font=font, anchor="mm",
                   stroke_width=2, stroke_fill="black")
    for p, v in vps:
        ys, xs = np.nonzero(sub == p)
        if len(ys):
            cx, cy, r = (xs.mean() + 0.5) * k, (ys.mean() + 0.5) * k, 3 + 1.5 * float(v) ** 0.5
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 215, 0), width=2)
            d.text((cx + r + 2, cy), f"{v}", fill=(255, 215, 0), font=small, anchor="lm", stroke_width=1,
                   stroke_fill="black")
    x0 = big.shape[1] + 10
    for i, f in enumerate(sorted(files, key=lambda f: sts[f]["id"])):
        st = sts[f]
        name = os.path.basename(f)[:-4].split(" - ", 1)[-1]
        d.text((x0, 8 + 16 * i), f"{st['id']:>5} {'X' if st['impassable'] else ' '} {len(st['provinces']):3}p  {name}"[:44],
               fill="white", font=small)
    canvas.save(path)


def main(name):
    global ALL
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    os.chdir(root)
    rows = definition()
    pid = province_ids(rows)
    ALL = sts = states()
    files, planet = planet_files(sts, name)
    slug = planet.lower().replace(" ", "_")
    pst = {}                                                               # planet province -> state file
    owner_of = {}                                                          # any province -> state files
    for f, st in sts.items():
        for p in st["provinces"]:
            owner_of.setdefault(p, []).append(f)
    for f in files:
        for p in sts[f]["provinces"]:
            pst[p] = f
    pids = set(pst)
    planet_ids = {sts[f]["id"] for f in files}

    # provinces: defined, land, with pixels, in exactly one state
    present = np.bincount(pid[pid >= 0].ravel(), minlength=max(rows) + 1)
    for p, f in pst.items():
        where = line_of(f, rf"\b{p}\b", sts[f]["text"])
        if p not in rows:
            err(where, f"province {p} is not in definition.csv")
            continue
        if present[p] == 0:
            err(where, f"province {p} has no pixels in provinces.bmp")
        if rows[p]["type"] != "land":
            err(where, f"province {p} is {rows[p]['type']} in definition.csv:{rows[p]['line']}")
        if len(owner_of[p]) > 1:
            err(where, f"province {p} is also in {', '.join(x for x in owner_of[p] if x != f)}")

    # the planet: the land masses its provinces lie on (as planet_terrain_gen.py labels planets)
    land_ids = np.array([p for p, r in rows.items() if r["type"] == "land" and p])
    land = np.isin(pid, land_ids)
    mine = np.isin(pid, list(pids))
    lab, _ = ndi.label(land, np.ones((3, 3)))
    planet_mask = np.isin(lab, np.unique(lab[mine]))
    ys, xs = np.nonzero(planet_mask)
    sl = np.s_[max(ys.min() - 2, 0):ys.max() + 3, max(xs.min() - 2, 0):xs.max() + 3]
    sub = pid[sl]
    pm = planet_mask[sl]
    for p in sorted(set(np.unique(sub[pm]).tolist()) - pids):
        y, x = np.argwhere(sub == p)[0] + (sl[0].start, sl[1].start)
        if p in owner_of:
            err(f"map/provinces.bmp x={x} y={y}", f"province {p} on {planet}'s land belongs to {owner_of[p][0]}")
        else:
            err(f"map/provinces.bmp x={x} y={y}", f"province {p} on {planet}'s land is in no state")

    # strategic regions
    region_of = {}
    for f in glob.glob("map/strategicregions/*.txt"):
        b = re.search(r"provinces\s*=\s*\{([^}]*)\}", read(f))
        for p in (int(x) for x in b.group(1).split()) if b else ():
            if p in pids:
                region_of.setdefault(p, []).append(f.replace("\\", "/"))
    for p in sorted(pids):
        r = region_of.get(p, [])
        if len(r) != 1:
            err(line_of(pst[p], rf"\b{p}\b", sts[pst[p]]["text"]),
                f"province {p} is in {len(r)} strategic regions {r[:3]}")

    # the map script's state ids
    script_ids(planet, planet_ids)

    # states: owner, cores, connectivity, victory points, province buildings
    tags = set()
    for f in glob.glob("common/country_tags/*.txt"):
        tags.update(re.findall(r"^\s*([A-Z0-9]{3})\s*=", read(f), re.M))
    keys = loc_keys()
    vps = []
    for f in files:
        st = sts[f]
        if not st["owner"]:
            err(line_of(f, r"\bhistory\s*="), "no owner")
        elif st["owner"] not in tags:
            err(line_of(f, r"\bowner\s*="), f"owner {st['owner']} is not in common/country_tags")
        if st["owner"] and st["owner"] not in st["cores"] and not st["impassable"]:
            warn(line_of(f, r"\bowner\s*="), f"owner {st['owner']} has no core")
        provs = [p for p in st["provinces"] if p in rows]
        if provs:
            n = ndi.label(np.isin(sub, provs) & pm)[1]
            if n > 1:                                                      # split scenery blocks nothing
                (warn if st["impassable"] else err)(line_of(f, r"\bprovinces\s*="), f"state {st['id']} is in {n} pieces")
        for p, v in st["vps"]:
            vps.append((p, v))
            if p not in st["provinces"]:
                err(line_of(f, rf"^\s*{p}\s+{re.escape(v)}"), f"victory point {p} is not a province of this state")
            if f"VICTORY_POINTS_{p}" not in keys:
                warn(line_of(f, rf"^\s*{p}\s+{re.escape(v)}"), f"no VICTORY_POINTS_{p} localisation (shows the id)")
        for p in st["prov_buildings"]:
            if p not in st["provinces"]:
                err(line_of(f, rf"^\s*{p}\s*=\s*\{{"), f"buildings in province {p}, not a province of this state")
        if f"STATE_{st['id']}" not in keys:
            err(line_of(f, r"\bname\s*="), f"no STATE_{st['id']} key in localisation/english")
        if st["impassable"] and st["vps"]:
            warn(f, "impassable state has victory points")

    # provinces in several pieces (HOI4 accepts them, but the planet scripts never make them)
    for p in sorted(pids):
        if p in rows and present[p] and ndi.label(sub == p)[1] > 1:
            y, x = np.argwhere(sub == p)[0] + (sl[0].start, sl[1].start)
            warn(f"map/provinces.bmp x={x} y={y}", f"province {p} is in several pieces")

    # X crossings: four provinces meeting at one corner (korriban_map.uncross's rule, read only)
    A, B, C, D = sub[:-1, :-1], sub[1:, :-1], sub[:-1, 1:], sub[1:, 1:]
    x = (A != B) & (A != C) & (A != D) & (B != C) & (B != D) & (C != D) & pm[:-1, :-1] & pm[1:, 1:]
    if x.any():
        pts = np.argwhere(x)[:5] + (sl[0].start, sl[1].start)
        err("map/provinces.bmp", f"{int(x.sum())} X crossings, first at " + ", ".join(f"x={c} y={r}" for r, c in pts))

    # definition.csv: coastal flag (a 4-neighbour pixel of a sea province) and terrain
    sea = np.isin(sub, [p for p, r in rows.items() if r["type"] == "sea"])
    cats = set(re.findall(r"^\t(\w+)\s*=\s*\{", block("\n" + read("common/terrain/00_terrain.txt"), "categories"), re.M))
    from check_terrain_definition import palette_types
    ter_types = palette_types()
    ter_sub = np.asarray(Image.open("map/terrain.bmp"))[sl]
    zones = {}
    zpath = f"WIPGFX/Assets/{slug}_zones.json"
    if os.path.exists(zpath):
        zones = {int(p): v for p, v in json.load(open(zpath))["provinces"].items()}
        if set(zones) != pids:
            warn(zpath, f"{len(set(zones) ^ pids)} provinces differ from the state files (stale, or free_province_ids.py ran)")
    for p in sorted(pids):
        if p not in rows or not present[p]:
            continue
        r, where = rows[p], f"map/definition.csv:{rows[p]['line']}"
        m = sub == p
        coastal = bool((ndi.binary_dilation(m) & ~m & sea).any())
        if coastal != r["coastal"]:
            warn(where, f"province {p} coastal={str(r['coastal']).lower()}, pixels say {str(coastal).lower()}")
        if r["terrain"] not in cats:
            err(where, f"province {p} terrain '{r['terrain']}' is not a category in common/terrain/00_terrain.txt")
        elif r["type"] == "land" and not sts[pst[p]]["impassable"]:
            want = ter_types.get(int(np.bincount(ter_sub[m]).argmax()))     # terrain.bmp prevails (user, 2026-10-24)
            if want and want != "ocean" and want != r["terrain"]:
                warn(where, f"province {p} terrain {r['terrain']}, terrain.bmp says {want} (check_terrain_definition.py --fix)")

    # units based on the planet
    impassable = {p for p in pids if sts[pst[p]]["impassable"]}
    for f in glob.glob("history/units/*.txt"):
        s = read(f)
        if not any(int(q) in pids for q in re.findall(r"\b(?:location|naval_base)\s*=\s*(\d+)", s)):
            continue
        f = f.replace("\\", "/")
        for q in re.finditer(r"\b(location|naval_base)\s*=\s*(\d+)", s):
            p = int(q.group(2))
            if p not in pids:
                continue
            where = f"{f}:{s.count(chr(10), 0, q.start()) + 1}"
            if p in impassable:
                warn(where, f"{q.group(1)} {p} is in impassable state {sts[pst[p]]['id']}")
            if q.group(1) == "naval_base" and not rows[p]["coastal"]:
                err(where, f"naval_base {p} is not coastal")

    # adjacencies naming the planet's provinces
    for n, r in enumerate(csv.reader(open("map/adjacencies.csv", encoding="utf-8-sig"), delimiter=";"), 1):
        if len(r) > 3 and r[0].lstrip("-").isdigit() and (int(r[0]) in pids or int(r[1]) in pids):
            for c in (r[0], r[1], r[3]):
                if c.lstrip("-").isdigit() and int(c) > 0 and int(c) not in rows:
                    err(f"map/adjacencies.csv:{n}", f"province {c} is not in definition.csv")

    out = f"WIPGFX/Assets/{slug}_check.png"
    preview(out, pid, sl, pst, sts, files, planet_mask, vps)
    n_imp = sum(sts[f]["impassable"] for f in files)
    print(f"{planet}: {len(files)} states ({n_imp} impassable), {len(pids)} provinces "
          f"({len(pids) - len(impassable)} passable), {len(vps)} victory points -> {out}")
    for line in errors + warns:
        print(line)
    print(f"{len(errors)} errors, {len(warns)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
