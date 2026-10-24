"""Inventory of every landmark model + one sample of each town set, for the model refinement work (2026-10).

    python -B "WIPGFX/plans & scripts/model_inventory.py"

Writes WIPGFX/models_review/review.csv (one row per mesh). Facts are re-read on every run; the hand columns
(priority, status, issues, plan, refs) are kept by mesh name, so the sheet can be edited freely between runs.
Sources: landmarks_lore.LANDMARKS / PLANET_OF (mesh -> planet, title), military_buildings.py (mesh -> geometry function,
atlas), arch_kit.py / military_buildings.py (function -> file:line, first comment line), the planets' PLACEMENT tables
(scale, clear radius, where), gfx/models/buildings/hod_landmarks/*.mesh (size, date).
"""
import csv, glob, os, re, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
os.chdir(ROOT)
OUT = "WIPGFX/models_review/review.csv"
LM = "gfx/models/buildings/hod_landmarks"
HAND = ["priority", "status", "issues", "plan", "refs"]
FACTS = ["mesh", "kind", "planet", "title", "function", "source", "atlas", "scale", "clear", "where", "mesh_kb", "built",
         "render", "path"]


def functions():
    """function name -> (file:line, first comment line of its body)"""
    out = {}
    for f in ("WIPGFX/plans & scripts/arch_kit.py", "WIPGFX/plans & scripts/military_buildings.py"):
        lines = open(f, encoding="utf-8").read().split("\n")
        for i, ln in enumerate(lines):
            m = re.match(r"\s*def (\w+)\(k\b", ln)
            if m and m.group(1) not in out:
                doc = next((l.strip().lstrip("#").strip() for l in lines[i + 1:i + 4] if l.strip().startswith("#")), "")
                out[m.group(1)] = (f"{os.path.basename(f)}:{i + 1}", doc[:160])
    return out


def builds():
    """mesh name (or town family) -> (geometry function, atlas) from military_buildings.models()"""
    s = open("WIPGFX/plans & scripts/military_buildings.py", encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'build\("(hod_\w+)",\s*(?:ak\.)?(\w+)([^\n]*)', s):
        t = re.search(r'tex="(\w+)"', m.group(3))
        out[m.group(1)] = (m.group(2), t.group(1) if t else "hod_landmarks")
    # loops: for name, fn in (("hod_a", ak.a), ...): build(name, fn, tex="hod_x")
    for m in re.finditer(r'for name, fn in \((.*?)\):\s*\n\s*build\(name, fn,[^)]*?tex="(\w+)"', s, re.S):
        for n, fn in re.findall(r'\("(hod_\w+)",\s*(?:ak\.)?(\w+)\)', m.group(1)):
            out[n] = (fn, m.group(2))
    for n, fn, tex in re.findall(r'\("(hod_\w+_(?:town|city|village|ruin)\w*)",\s*ak\.(\w+),\s*"(\w+)"\)', s):
        out.setdefault(n, (fn, tex))                                          # town families
    return out


def placements():
    out = {}
    for f in glob.glob("WIPGFX/plans & scripts/*_map.py"):
        s = open(f, encoding="utf-8").read()
        if "PLACEMENT = dict(" not in s:
            continue
        p = s[s.index("PLACEMENT = dict("):]
        clear = dict(re.findall(r'"(hod_\w+)":\s*([\d.]+)', p[p.find("clear="):p.find("}", p.find("clear="))]))
        for n, sc, where in re.findall(r'\("(hod_\w+)",\s*([\d.]+),\s*\(([^)]*)\)', p):
            out.setdefault(n, (sc, clear.get(n, ""), where.replace('"', "").strip()))
    return out


def main():
    import landmarks_lore as L
    fn_src, mb, pl = functions(), builds(), placements()
    rows = {}
    for key, meshes, *rest in L.LANDMARKS:
        title = next((x for x in rest if isinstance(x, str) and not x.startswith("GFX_")), "")
        for m in meshes:
            rows.setdefault(m, dict(mesh=m, kind="landmark", planet=L.PLANET_OF[key], title=title))
    prefix_planet = {}
    for m, r in rows.items():
        prefix_planet.setdefault(m.split("_")[1], r["planet"])
    for fam in sorted(n for n in mb if re.search(r"_(town|city|village|ruin)$", n)):
        sample = sorted(glob.glob(f"{LM}/{fam}_44.mesh") or glob.glob(f"{LM}/{fam}_*.mesh"))
        if sample:
            m = os.path.basename(sample[-1])[:-5]
            rows.setdefault(m, dict(mesh=m, kind="town", planet=prefix_planet.get(fam.split("_")[1], ""), title=fam))
    old = {}
    if os.path.exists(OUT):
        old = {r["mesh"]: r for r in csv.DictReader(open(OUT, encoding="utf-8-sig"))}
    out = []
    for m, r in rows.items():
        fam = re.sub(r"_(r?\d+|[ab])$", "", m)                       # town cells, rotated / lettered variants
        fn, tex = mb.get(m) or mb.get(fam) or ("", "")
        src, doc = fn_src.get(fn, ("", ""))
        sc, clear, where = pl.get(m, ("", "", ""))
        path = next(iter(glob.glob(f"gfx/models/**/{m}.mesh", recursive=True)), f"{LM}/{m}.mesh").replace("\\", "/")
        r.update(function=fn, source=src, atlas=tex, scale=sc, clear=clear, where=where,
                 mesh_kb=round(os.path.getsize(path) / 1024) if os.path.exists(path) else "MISSING",
                 built=datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if os.path.exists(path) else "",
                 render=f"renders/{m}.png", path=path)
        if not r["title"] or r["kind"] == "town":
            r["title"] = r["title"] or doc
        for h in HAND:
            r[h] = old.get(m, {}).get(h, "")
        out.append(r)
    out.sort(key=lambda r: (r["planet"], r["kind"], r["mesh"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, FACTS + HAND)
        w.writeheader()
        w.writerows(out)
    miss = [r["mesh"] for r in out if r["mesh_kb"] == "MISSING"]
    nofn = [r["mesh"] for r in out if not r["function"]]
    print(f"{len(out)} rows ({sum(r['kind'] == 'landmark' for r in out)} landmarks, "
          f"{sum(r['kind'] == 'town' for r in out)} town samples, {len({r['planet'] for r in out})} planets) -> {OUT}")
    print(f"missing meshes: {len(miss)} {miss[:6]}")
    print(f"no geometry function found: {len(nofn)} {nofn[:8]}")


if __name__ == "__main__":
    main()
