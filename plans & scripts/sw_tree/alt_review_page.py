"""Keep/drop review page for the variant picker (user 2026-11-11): the models in the picker today (alt_models.catalog)
and the new mod candidates (alt_candidates.csv + renders from alt_candidates_convert.py).

    python -B "plans & scripts/sw_tree/alt_review_page.py"   -> ../ProjectKessilianWIPGFX/ProjectKessilianWIP/models_review/alt_review.html (published as an Artifact)
The page's "Copy choices" text lists `keep new:` and `drop current:` keys for alt_models.py.
"""
import base64, csv, html, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alt_models as A                                       # noqa: E402  (chdirs to the mod root)
from alt_candidates_convert import PNG, key, SHIPS           # noqa: E402
from PIL import Image                                        # noqa: E402

OUT = "../ProjectKessilianWIPGFX/ProjectKessilianWIP/models_review/alt_review.html"
LABEL = {"extra_light_equipment": "Scout walkers", "light_equipment": "Light vehicles", "speeder_equipment": "Speeders",
         "heavy_equipment": "Heavy walkers", "assault_equipment": "Assault tanks", "mobile_art_equipment": "Artillery",
         "mobile_aa_equipment": "Anti-air", "troop_transport_equipment": "Troop transports",
         "heavy_troop_transport_equipment": "Heavy transports", "imp_fighter_equipment": "Fighters",
         "imp_defender_equipment": "Heavy fighters", "imp_interceptor_equipment": "Interceptors",
         "imp_bomber_equipment": "Bombers", "imperial_transport_plane_equipment": "Transport craft",
         "imp_gunship_equipment": "Gunships", "dd": "Destroyers", "cl": "Light cruisers", "ca": "Heavy cruisers",
         "cv": "Carriers", "as": "Assault ships", "bb": "Battleships",
         "fighter": "Fighters", "bomber": "Bombers", "transport": "Transports", "corvette": "Corvettes",
         "frigate": "Frigates", "capital": "Capital ships", "supercapital": "Super-capitals", "vehicle": "Ground vehicles"}
SRC = {"fotr": "Fall of the Republic", "raw": "Republic at War", "tr": "Thrawn's Revenge"}


def thumb(im, w, h):
    im = im.convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if not box:
        return None
    im = im.crop(box)
    im.thumbnail((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=72)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def norm(unit):
    return re.sub(r"^(template|generic)_|_(walker|tank|starfighter|fighter|class|cruiser)$", "", unit.lower())


def main():
    cur = []
    for kind, models in A.catalog().items():
        for model, side, _ in models:
            p = A.icon_file(model)
            img = thumb(Image.open(p), 240, 120) if os.path.exists(p) else None
            cur.append(dict(id="cur:" + model, group=LABEL.get(kind, kind), name=model.replace("hod_", "").replace("_", " "),
                            meta={"r": "Republic", "c": "Separatist"}.get(side, "Any side"), img=img))
    new, broken = [], []
    rows = list(csv.DictReader(open("../ProjectKessilianWIPGFX/ProjectKessilianWIP/models_review/alt_candidates.csv", encoding="utf-8")))
    rows.sort(key=lambda r: (r["kind"], norm(r["unit"]), r["source"]))
    for r in rows:
        p = os.path.join(PNG, key(r) + "_raw.png")
        img = thumb(Image.open(p), 240, 120 if r["kind"] not in SHIPS else 90) if os.path.exists(p) else None
        if not img:
            broken.append(r["unit"])
            continue
        new.append(dict(id="new:" + key(r), group=LABEL.get(r["kind"], r["kind"]), name=r["unit"].replace("_", " "),
                        meta="%s, %s" % (SRC[r["source"]], r["affiliation"] or "no faction"), kb=int(r["kb"]), img=img))
    tpl = open(os.path.join(HERE, "alt_review_template.html"), encoding="utf-8").read()
    data = json.dumps(dict(cur=cur, new=new), separators=(",", ":"))
    open(OUT, "w", encoding="utf-8").write(tpl.replace("/*DATA*/null", data))
    print("current", len(cur), "new", len(new), "failed to convert/render", len(broken), "->", OUT)
    if broken:
        print("  ", ", ".join(broken[:40]))


if __name__ == "__main__":
    main()
