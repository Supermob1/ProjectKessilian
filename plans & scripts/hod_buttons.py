"""Redraws the mod's own (git-tracked) buttons in the house style of hod_ui: navy plate, crisp cyan frame, gold on
hover / pressed / on. The glyph each button carries (toolbar symbol, tick, arrow) is lifted from the old frame and kept.
Originals stay in git: `--undo` restores them with git checkout.

    python -B hod_buttons.py --preview sheet.png
    python -B hod_buttons.py --write | --undo
"""
import argparse, glob, io, os, re, subprocess, sys
import numpy as np
from PIL import Image
import hod_ui

MOD = hod_ui.MOD
LOG = os.path.join(os.path.dirname(__file__), "hod_buttons_written.txt")
PAT = re.compile(r"button|btn|checkbox|_tab\.", re.I)
# icon buttons (toolbar, topbar, arrows, ticks, tech tabs) are the reference art and keep their own look
KEEP = re.compile(r"topbar/|checkbox|closebutton|button_(left|right)|scrollbar_|_tab\.|main_lobby", re.I)
# plain frames that carry a symbol: path -> {frame: (pictogram, colour or None = frame colour)}
GLYPHS = {"gfx/interface/custom_set_button_2.dds": {0: ("cog", None), 1: ("cog", None)},
          "gfx/interface/date_pause_button.dds": {1: ("pause", hod_ui.RED)},
          "gfx/interface/date_pause_button_bg.dds": {0: ("play", hod_ui.GREEN)}}
SKIP = {"gfx/interface/add_national_goal_button.dds"}      # redrawn from scratch below, its old glyph is the weak part
ONOFF = re.compile(r"topbar/toolbar/|checkbox|_tab\.", re.I)  # 2 frames = off / on, not normal / hover


def tracked():
    out = subprocess.run(["git", "ls-files", "gfx/interface"], cwd=MOD, capture_output=True, text=True).stdout
    return [p for p in out.splitlines() if PAT.search(os.path.basename(p)) and not KEEP.search(p)]


def frames_of(path):
    key = path.lower()
    for root in (MOD, hod_ui.VANILLA):
        for f in glob.glob(root + "/interface/**/*.gfx", recursive=True):
            txt = open(f, encoding="utf-8-sig", errors="ignore").read()
            for m in re.finditer(r"spriteType\s*=\s*\{(.*?)\n\s*\}", txt, re.S | re.I):
                t = re.search(r'texturefile\s*=\s*"([^"]+)"', m.group(1), re.I)
                if t and re.sub(r"/+", "/", t.group(1).replace("\\", "/")).lower() == key:
                    n = re.search(r"noOfFrames\s*=\s*(\d+)", m.group(1), re.I)
                    return int(n.group(1)) if n else 1
    return 1


def stamp(f, name, col, left=False):
    """Draws one of our vector symbols onto a frame: centred, or at the left end of a wide button."""
    import hod_vector
    h, w = f.shape[:2]
    n = int(h * 0.8)
    cov = np.array(hod_vector.render(name, n, n, 0.12)).astype(float)[..., None] / 255
    y0, x0 = (h - n) // 2, ((h - n) // 2 + 6 if left else (w - n) // 2)
    reg = f[y0:y0 + n, x0:x0 + n, :3].astype(float)
    f[y0:y0 + n, x0:x0 + n, :3] = (reg * (1 - cov) + np.asarray(col, float) * cov).astype(np.uint8)
    return f


def state(path, frames, k):
    if frames in (3, 4):
        return k
    if frames == 2:
        return 1 if k else 0                           # off/on and normal/hover both go cyan -> gold
    return 0


def new_goal_button(px):
    """Add-national-goal slot: an embossed durasteel plaque (normal, hover, pressed), like vanilla's diplo_goal_button."""
    import hod_plaque
    out = np.hstack([hod_plaque.render(k) for k in range(3)])
    if out.shape[1] < px.shape[1]:
        out = np.hstack([out, np.zeros((px.shape[0], px.shape[1] - out.shape[1], 4), np.uint8)])
    return out


def restyle(path, px, frames):
    if path in SKIP:
        return new_goal_button(px)
    fw = px.shape[1] // max(frames, 1)
    parts = []
    for k in range(max(frames, 1)):
        f = px[:, k * fw:(k + 1) * fw]
        flat = np.zeros_like(f); flat[..., 3] = f[..., 3]  # flat copy: no seams of the old art read as panel lines
        out = hod_ui.draw(flat, None, state(path, frames, k))
        out[(out[..., :3] == hod_ui.STEEL).all(-1)] = (*hod_ui.CYAN, 255)   # buttons are cyan at any width
        st = state(path, frames, k)
        if k in GLYPHS.get(path, {}):
            name, col = GLYPHS[path][k]
            stamp(out, name, hod_ui.CYAN if col is None and st == 0 else hod_ui.GOLD if col is None else col, left=True)
        parts.append(out)
    out = np.hstack(parts)
    if out.shape[1] < px.shape[1]:
        out = np.hstack([out, np.zeros((px.shape[0], px.shape[1] - out.shape[1], 4), np.uint8)])
    return out


def items():
    for p in tracked():
        try:
            px = np.array(Image.open(os.path.join(MOD, p)).convert("RGBA"))
        except Exception as e:
            print("skip", p, e, file=sys.stderr); continue
        yield p, px, frames_of(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview"); ap.add_argument("--write", action="store_true"); ap.add_argument("--undo", action="store_true")
    a = ap.parse_args()
    if a.undo:
        paths = open(LOG).read().splitlines()
        subprocess.run(["git", "checkout", "--"] + paths, cwd=MOD, check=True)
        os.remove(LOG); print("restored", len(paths)); return
    its = list(items())
    if a.preview:
        rows, w = [], 900
        for p, px, n in its:
            new = restyle(p, px, n)
            pair = [Image.fromarray(x) for x in (px, new)]
            sc = min(1.0, (w // 2 - 10) / pair[0].width)
            pair = [im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc)))) for im in pair]
            rows.append((p, n, pair))
        H = sum(r[2][0].height + 18 for r in rows)
        sheet = Image.new("RGB", (w, H), (60, 60, 60))
        from PIL import ImageDraw
        d, y = ImageDraw.Draw(sheet), 0
        for p, n, pair in rows:
            d.text((2, y), f"{p[14:]}  ({n} frames)", fill=(255, 230, 0))
            for k, im in enumerate(pair):
                sheet.paste(im, (k * w // 2, y + 16), im)
            y += pair[0].height + 18
        sheet.save(a.preview); print("preview", a.preview)
    if a.write:
        with open(LOG, "w") as log:
            for p, px, n in its:
                dst = os.path.join(MOD, p)
                buf = io.BytesIO()
                Image.fromarray(restyle(p, px, n)).save(buf, "DDS" if dst.lower().endswith(".dds") else "TGA")
                open(dst, "wb").write(buf.getvalue()); log.write(p + "\n")
        print("wrote", len(its), "->", LOG)


if __name__ == "__main__":
    main()
