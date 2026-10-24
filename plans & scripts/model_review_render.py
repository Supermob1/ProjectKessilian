"""Render every mesh in WIPGFX/models_review/review.csv and lay out one contact sheet per planet (model refinement work).

    python -B "WIPGFX/plans & scripts/model_review_render.py"                 stale renders only (mesh newer than its png)
    python -B "WIPGFX/plans & scripts/model_review_render.py" hod_csi_ hod_x  only meshes with these prefixes (forced)
    python -B "WIPGFX/plans & scripts/model_review_render.py" --sheets        contact sheets only

Renders: WIPGFX/models_review/renders/<mesh>.png (oblique) and <mesh>_top.png, via render_mesh.py, one Blender per mesh,
JOBS at a time. Sheets: WIPGFX/models_review/sheets/<Planet>.png, landmarks then the town sample, labelled with the mesh
name, title and mesh size. Blender: $HOD_BLENDER, else the universal-modder copy, else F:/blender-4.2.23-windows-x64.
"""
import csv, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(ROOT)
OUT = "WIPGFX/models_review"
JOBS = max(2, (os.cpu_count() or 4) // 2)
BLENDER = next((b for b in (os.environ.get("HOD_BLENDER"),
                            os.path.expandvars("$LOCALAPPDATA/universal-modder/tools/blender-4.2.3-windows-x64/blender.exe"),
                            "F:/blender-4.2.23-windows-x64/blender.exe") if b and os.path.exists(b)), None)


def render(row):
    png = f"{OUT}/renders/{row['mesh']}.png"
    env = dict(os.environ, PYTHONPATH=os.path.expandvars("$APPDATA/Blender Foundation/Blender/4.2/extensions/user_default"))
    tmp = f"{OUT}/renders/_{row['mesh']}.png"
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", f"{HERE}/render_mesh.py", "--", tmp, row["path"]],
                       capture_output=True, text=True, env=env)
    ok = os.path.exists(tmp[:-4] + "_oblique.png")
    if ok:
        shutil.move(tmp[:-4] + "_oblique.png", png)
        if os.path.exists(tmp[:-4] + "_top.png"):
            shutil.move(tmp[:-4] + "_top.png", png[:-4] + "_top.png")
    return row["mesh"], ok, ("Traceback" in r.stdout + r.stderr)


def sheets(rows):
    from PIL import Image, ImageDraw
    W, LBL = 360, 34
    by = {}
    for r in rows:
        by.setdefault(r["planet"] or "_unknown", []).append(r)
    os.makedirs(f"{OUT}/sheets", exist_ok=True)
    for planet, rs in by.items():
        rs.sort(key=lambda r: (r["kind"] != "landmark", r["mesh"]))
        cols = min(4, len(rs))
        sheet = Image.new("RGB", (W * cols, (W + LBL) * ((len(rs) + cols - 1) // cols)), (40, 40, 40))
        d = ImageDraw.Draw(sheet)
        for i, r in enumerate(rs):
            x, y = (i % cols) * W, (i // cols) * (W + LBL)
            png = f"{OUT}/renders/{r['mesh']}.png"
            if os.path.exists(png):
                im = Image.open(png).convert("RGB")
                im.thumbnail((W, W))
                sheet.paste(im, (x, y + LBL))
            d.text((x + 4, y + 3), r["mesh"], fill=(255, 210, 90))
            d.text((x + 4, y + 17), f"{r['title'][:44]}  {r['mesh_kb']}KB  {r['status']}", fill=(220, 220, 220))
        sheet.save(f"{OUT}/sheets/{planet.replace(' ', '_')}.png")
    print(f"{len(by)} sheets -> {OUT}/sheets")


def main(args):
    rows = list(csv.DictReader(open(f"{OUT}/review.csv", encoding="utf-8-sig")))
    if "--sheets" not in args:
        assert BLENDER, "no Blender found: set HOD_BLENDER"
        os.makedirs(f"{OUT}/renders", exist_ok=True)
        pre = [a for a in args if not a.startswith("--")]
        todo = [r for r in rows if os.path.exists(r["path"]) and (
            any(r["mesh"].startswith(p) for p in pre) if pre else
            not os.path.exists(f"{OUT}/renders/{r['mesh']}.png")
            or os.path.getmtime(r["path"]) > os.path.getmtime(f"{OUT}/renders/{r['mesh']}.png"))]
        print(f"rendering {len(todo)} meshes, {JOBS} at a time")
        bad = []
        with ThreadPoolExecutor(JOBS) as ex:
            for i, (m, ok, tb) in enumerate(ex.map(render, todo), 1):
                if not ok:                                                   # a Traceback with a png = io_pdx noise when run in parallel
                    bad.append(m)
                if i % 50 == 0:
                    print(f"  {i}/{len(todo)}", flush=True)
        print(f"failed: {len(bad)} {bad[:10]}")
    sheets(rows)


if __name__ == "__main__":
    main(sys.argv[1:])
