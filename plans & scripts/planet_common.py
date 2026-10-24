"""What kadavo_map.py, florrum_map.py and korriban_map.py share, word for word: the guard before the first write, the
per-province measurements, writing provinces.bmp / definition.csv / the zones files, the old state files, their
naval bases and dockyards, and the state name localisation. Run from the mod root, like the planet scripts."""
import csv, glob, json, math, os, re, subprocess, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from felucia_tribes import rw

# everything a planet script (and felucia_tribes.place) rewrites
WRITES = ["map/provinces.bmp", "map/definition.csv", "map/adjacencies.csv", "map/buildings.txt", "map/railways.txt",
          "map/airports.txt", "map/rocketsites.txt",
          "map/supply_nodes.txt", "map/unitstacks.txt", "history/states", "history/units",
          "localisation/english/state_names_l_english.yml", "localisation/english/victory_points_l_english.yml"]


def guard(planet, state_names, feature_states=()):
    """Before anything is written: refuse uncommitted changes in the files the script rewrites (pass --allow-dirty to
    override), state ids that belong to another planet, and feature states missing from STATE_NAMES (the script would
    stop half-way, after provinces.bmp and definition.csv are written)."""
    if "--allow-dirty" not in sys.argv:
        r = subprocess.run(["git", "status", "--porcelain", "--", *WRITES], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"git status failed ({r.stderr.strip()}); pass --allow-dirty to run without the check")
        if r.stdout.strip():
            sys.exit("uncommitted changes in files this script rewrites (commit or stash them, or pass --allow-dirty):\n"
                     + r.stdout)
    missing = sorted(set(feature_states) - set(state_names) - {None})
    if missing:
        sys.exit(f"FEATURES name states {missing} that are not in STATE_NAMES")
    for f in glob.glob("history/states/*.txt"):
        sid = int(re.search(r"\bid\s*=\s*(\d+)", open(f, encoding="utf-8-sig").read()).group(1))
        base = os.path.basename(f)                                       # "<id>-<Planet> - <name>.txt" or "<id>-<Planet>.txt"
        if sid in state_names and not (base.startswith(f"{sid}-{planet} - ") or base == f"{sid}-{planet}.txt"):
            sys.exit(f"state {sid} ({state_names[sid]}) is {f}, not a {planet} state")


def run(main):
    """main(), and if it fails part-way, say which files may be half-written"""
    try:
        main()
    except BaseException as e:
        if not isinstance(e, SystemExit):
            print("Stopped part-way: files may be half-written. They were clean before (unless --allow-dirty); "
                  "inspect with  git status -- " + " ".join(f'"{w}"' for w in WRITES), file=sys.stderr)
        raise


def definition_rows():
    return {int(r[0]): r for r in csv.reader(open("map/definition.csv", encoding="utf-8-sig"), delimiter=";") if r and r[0].isdigit()}


def measure(prov, newpid, pid, rows, terrain):
    """coastal, the sea next to it, centre, area and gameplay terrain of every province"""
    sea = np.isin(pid, [i for i, r in rows.items() if r[4] == "sea"])
    for p, v in prov.items():
        pm = newpid == p
        ring = ndi.binary_dilation(pm) & ~pm
        v["coastal"] = bool((ring & sea).any())
        v["sea"] = int(np.bincount(pid[ring & sea]).argmax()) if v["coastal"] else 0
        v["centre"] = [float(c) for c in ndi.center_of_mass(pm)]
        v["area"] = int(pm.sum())
        v["terrain"] = terrain[v["zone"]]


def write_map(newpid, m, rows, prov):
    """the planet's pixels into provinces.bmp; coastal and terrain into definition.csv (BOM and line ends kept)"""
    bmp = np.array(Image.open("map/provinces.bmp").convert("RGB"))
    ys, xs = np.nonzero(m)
    bmp[ys, xs] = np.array([[int(rows[p][1]), int(rows[p][2]), int(rows[p][3])] for p in newpid[ys, xs]], np.uint8)
    Image.fromarray(bmp, "RGB").save("map/provinces.bmp")
    path = "map/definition.csv"
    raw_txt = open(path, "rb").read()
    out = []
    for line in raw_txt.decode("utf-8-sig").splitlines(keepends=True):
        body, end = line.rstrip("\r\n"), line[len(line.rstrip("\r\n")):]
        q = body.split(";")
        if len(q) >= 7 and q[0].isdigit() and int(q[0]) in prov:
            q[5] = "true" if prov[int(q[0])]["coastal"] else "false"
            q[6] = prov[int(q[0])]["terrain"]
        out.append(";".join(q) + end)
    open(path, "wb").write((b"\xef\xbb\xbf" if raw_txt.startswith(b"\xef\xbb\xbf") else b"") + "".join(out).encode("utf-8"))


def write_zones(json_path, png_path, m, kind, vp_names, prov):
    """the zones the terrain and placement steps read: <planet>_zones.json and the KIND per pixel png"""
    ys, xs = np.nonzero(m)
    json.dump({"centre": [float(ys.mean()), float(xs.mean())], "radius": math.sqrt(m.sum() / math.pi),
               "vp_names": {str(p): n for p, n in vp_names.items()},
               "provinces": {str(p): v for p, v in prov.items()}}, open(json_path, "w"), indent=1)
    Image.fromarray(np.where(m, kind, 0).astype(np.uint8)).save(png_path)


def old_states(state_names):
    """state id -> its current file, for the planet's states"""
    old = {}
    for f in glob.glob("history/states/*.txt"):
        sid = int(re.search(r"\bid\s*=\s*(\d+)", open(f, encoding="utf-8-sig").read()).group(1))
        if sid in state_names:
            old[sid] = f
    return old


def state_names_loc(state_names):
    """STATE_<id> names of the planet's states, replacing the old ones"""
    def fs(s):
        for sid in state_names:
            s = re.sub(rf'\n STATE_{sid}:\d* "[^"]*"', "", s)
        return s.rstrip("\n") + "\n" + "".join(f' STATE_{sid}:0 "{n}"\n' for sid, n in sorted(state_names.items()))
    rw("localisation/english/state_names_l_english.yml", fs)
