"""Candidate models for the variant picker from the EaW mods (user 2026-11-11: FotR + full RaW + Thrawn's Revenge).

    python -B "plans & scripts/sw_tree/alt_candidates.py"   -> ../ProjectKessilianWIPGFX/ProjectKessilianWIP/models_review/alt_candidates.csv

Reads every SpaceUnit / UniqueUnit / GroundVehicle in each mod's XML (not the raw .alo list: that is mostly props, FX
and hardpoint parts), keeps ships / fighters / bombers / vehicles, and drops: models we already use (alo stem named in
unit_models.py), the same .alo used by several units, and byte-identical .alo files across mods (first source wins).
"""
import csv, hashlib, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, "..", ".."))
B = "F:/SteamLibrary/steamapps/common/Star Wars Battlefront II Classic"
SOURCES = [("fotr", B + "/FotR14/FotR14/Data"),
           ("raw", "F:/SteamLibrary/steamapps/workshop/content/32470/1129810972/Data"),
           ("tr", B + "/ThrawnsRevenge33/ThrawnsRevenge33/Data")]
OUT = os.path.join(MOD, "../ProjectKessilianWIPGFX/ProjectKessilianWIP/models_review/alt_candidates.csv")

OBJ = re.compile(r"<(SpaceUnit|UniqueUnit|GroundVehicle)\s+Name\s*=\s*\"([^\"]+)\"(.*?)</\1>", re.S | re.I)
TAG = lambda t: re.compile(r"<%s>\s*([^<]*?)\s*</%s>" % (t, t), re.I)
SPACE_M, LAND_M, CAT = TAG("Space_Model_Name"), TAG("Land_Model_Name"), TAG("CategoryMask")
AFFIL = TAG("Affiliation")
KINDS = [("fighter", "fighter"), ("bomber", "bomber"), ("corvette", "corvette"), ("frigate", "frigate"),
         ("supercapital", "supercapital"), ("capital", "capital"), ("vehicle", "vehicle"), ("transport", "transport")]
SKIP_NAME = re.compile(r"dummy|death|_dead|debris|proxy|marker|test|_hero|tutorial|upgrade|hulk|wreck|_player|container", re.I)


def kind_of(cat, tag):
    c = re.sub(r"anti\w+", "", cat.lower())     # "Frigate | AntiFighter" is a frigate
    for key, kind in KINDS:
        if key in c:
            return kind
    return "vehicle" if tag.lower() == "groundvehicle" else None


def used_stems():
    txt = ""
    for f in ("unit_models.py", "sw_tree/unit_models_sw.py", "sw_tree/naval_tree.py"):
        p = os.path.join(MOD, "plans & scripts", f)
        if os.path.exists(p):
            txt += open(p, encoding="utf-8", errors="ignore").read().lower()
    stems = set(re.findall(r"([\w\-]+)\.(?:alo|glb)", txt))
    # every .alo already converted (alo_to_glb.py keeps the stem) is in game or already in the picker
    glb = os.path.join(MOD, "../ProjectKessilianWIPGFX/ProjectKessilianWIP/3d/_glb")
    for d in ("eaw", "eaw2", "eaw_vanilla", "fotr", "raw", "raw_anim", "thrawn"):
        if os.path.isdir(os.path.join(glb, d)):
            stems |= {os.path.splitext(f)[0].lower() for f in os.listdir(os.path.join(glb, d))}
    return stems


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def main():
    used = used_stems()
    rows, seen_model, seen_hash = [], set(), {}
    for src, data in SOURCES:
        models = {f.lower(): os.path.join(data, "Art/Models", f) for f in os.listdir(os.path.join(data, "Art/Models"))}
        for root, _, files in os.walk(os.path.join(data, "XML")):
            for f in files:
                if not f.lower().endswith(".xml"):
                    continue
                txt = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
                for tag, name, body in OBJ.findall(txt):
                    m = (SPACE_M.search(body) or LAND_M.search(body))
                    cat = CAT.search(body)
                    kind = kind_of(cat.group(1) if cat else "", tag)
                    if not m or not kind or SKIP_NAME.search(name) or "hero" in (cat.group(1).lower() if cat else ""):
                        continue
                    alo = m.group(1).strip().lower()
                    alo = alo if alo.endswith(".alo") else alo + ".alo"
                    path = models.get(alo)
                    stem = alo[:-4]
                    if not path or stem in used or (src, alo) in seen_model:
                        continue
                    seen_model.add((src, alo))
                    h = md5(path)
                    if h in seen_hash:
                        continue
                    seen_hash[h] = name
                    aff = AFFIL.search(body)
                    rows.append(dict(source=src, kind=kind, unit=name, affiliation=(aff.group(1) if aff else "")[:40],
                                     alo=os.path.basename(path), kb=os.path.getsize(path) // 1024, path=path))
    rows.sort(key=lambda r: (r["kind"], r["source"], r["unit"].lower()))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by[(r["source"], r["kind"])] = by.get((r["source"], r["kind"]), 0) + 1
    print(len(rows), "candidates ->", OUT)
    for k in sorted(by):
        print(" ", k, by[k])


if __name__ == "__main__":
    main()
