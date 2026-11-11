"""Convert + render every row of ../ProjectKessilianWIPGFX/ProjectKessilianWIP/models_review/alt_candidates.csv for the keep/drop review (user 2026-11-11).

    python -B "plans & scripts/sw_tree/alt_candidates_convert.py"          glb -> _glb/alt_cand/<source>/, png -> models_review/alt_cand_png/
Skips files already done, so it can be rerun after a crash.
"""
import csv, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(MOD)
B42 = os.path.expandvars("$LOCALAPPDATA/universal-modder/tools/blender-4.2.3-windows-x64/blender.exe")
B52 = "F:/Blender Foundation/Blender 5.2/blender.exe"
GLB = os.path.abspath("../ProjectKessilianWIPGFX/ProjectKessilianWIP/3d/_glb/alt_cand")
PNG = os.path.abspath("../ProjectKessilianWIPGFX/ProjectKessilianWIP/models_review/alt_cand_png")
CHUNK = 20
SHIPS = {"corvette", "frigate", "capital", "supercapital"}


def key(r):
    return r["source"] + "__" + os.path.splitext(r["alo"])[0].lower().replace("'", "")


def chunks(lst):
    return [lst[i:i + CHUNK] for i in range(0, len(lst), CHUNK)]


def main():
    rows = list(csv.DictReader(open("../ProjectKessilianWIPGFX/ProjectKessilianWIP/models_review/alt_candidates.csv", encoding="utf-8")))
    for src in sorted({r["source"] for r in rows}):
        out = os.path.join(GLB, src)
        todo = [r["path"] for r in rows if r["source"] == src
                and not os.path.exists(os.path.join(out, os.path.splitext(r["alo"])[0] + ".glb"))]
        for part in chunks(todo):
            subprocess.run([B42, "-b", "--factory-startup", "--python", "plans & scripts/alo_to_glb.py", "--", out] + part,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(src, "converted", len(part), flush=True)
    for ships in (False, True):
        todo = []
        for r in rows:
            glb = os.path.join(GLB, r["source"], os.path.splitext(r["alo"])[0] + ".glb")
            if (r["kind"] in SHIPS) == ships and os.path.exists(glb) and not os.path.exists(os.path.join(PNG, key(r) + "_raw.png")):
                todo.append(key(r) + "=" + glb)
        env = dict(os.environ, HOD_SHIP_VIEW="1") if ships else os.environ
        for part in chunks(todo):
            subprocess.run([B52, "-b", "--factory-startup", "--python", "plans & scripts/tech_icon_render.py", "--", PNG] + part,
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("rendered", len(part), flush=True)


if __name__ == "__main__":
    main()
