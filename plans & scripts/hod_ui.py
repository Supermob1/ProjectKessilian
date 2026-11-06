"""Hearts of Durasteel UI chrome, drawn from scratch over vanilla's shapes: flat dark fill, 1px neon edge, the vanilla
sub-panel layout as clean steel lines, square corners. Palette = the mod's own windows and toolbar (navy, steel, cyan, gold on hover).
Icons, glyph buttons and the mod's own interface art are never touched.

  python -B hod_ui.py --preview OUT.png    before/after sheet
  python -B hod_ui.py --write              writes; every path goes to hod_ui_written.txt
  python -B hod_ui.py --undo               deletes everything in hod_ui_written.txt
"""
import argparse, glob, io, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

VANILLA = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG = os.path.join(os.path.dirname(__file__), "hod_ui_written.txt")

# the mod's own toolbar palette (gfx/interface/topbar/toolbar)
PLATE = np.array([0, 1, 22], float)         # navy of the mod's own windows (tiled_window, event_option_entry, header_bg)
STEEL = np.array([0, 88, 137], float)       # their dim frame line on big windows
CYAN = np.array([0, 176, 240], float)
GOLD = np.array([240, 192, 32], float)
GREY = np.array([90, 106, 112], float)
FILL = PLATE
CHROME = re.compile(r"(bg|background|button|btn|frame|box|window|tile|entry|tab|scroll|slider|popup|bar|panel|header|"
                    r"border|plate|holder|dragger|binding|top|bottom|win)", re.I)
SKIP = re.compile(r"(icon|flag|portrait|leader|goals/|ideas/|technolog|techtree|traits|texticon|counters|mapmode|"
                  r"event_pictures|loadingscreen|logo|medal|ribbon|aces/|unit_|_pic|career|pdx_online|propaganda|"
                  r"checkbox|anim|progress|arrow|fill|meter|gauge|strip|overlay|piechart|terrain|endgame|"
                  r"musicplayer|upgrade_frame|_line|line_|glow|shine|highlight|mask|shadow|selection|joint_|"
                  # smooth pictures the detail test can't catch (mission / doctrine / weather art)
                  r"destruction|superiority|strike_bg|fleet_in_being|grand_battleplan|mob_warfare|sup_firepower|"
                  r"tac_operation|interdiction|wonderweapons|screens_bg|images/|weather|topview|diplo_response|pink|"
                  r"equipmentdesigner/(tanks|planes|naval)/(?!.*(bg|frame|slot|box))|transp|opacity|nothing)", re.I)
ART = re.compile(r"^gfx/interface/(ideas|goals|technologies|equipmentdesigner|counters|career_profile|medals|terrains|"
                 r"operations/images|factions/faction_logos|buildings/historical|event|loadingscreen|leaders|portraits|"
                 r"flags|mapicons|special_project/project_icons|inner_circle|bop/bop_.*_side|decisions/|mapmode|"
                 r"military_industrial_organization/department_icons|operatives/agencies|navalcombat/ships|dlc_banners|"
                 r"military_raids/terrains|focusview/titlebar|social/)|logo|strip|_icons?\b", re.I)
BAR = re.compile(r"progress|fill|meter|gauge|_bar|bar_|bar\.", re.I)
FX = re.compile(r"glow|shine|highlight|mask|shadow|anim|overlay|transp|opacity", re.I)


def vanilla_sprites():
    """texture path -> (frames, cornered tile)."""
    out = {}
    for f in glob.glob(VANILLA + "/interface/**/*.gfx", recursive=True):
        txt = open(f, encoding="utf-8-sig", errors="ignore").read()
        for m in re.finditer(r"(?:corneredTileSpriteType|spriteType)\s*=\s*\{(.*?)\n\s*\}", txt, re.S | re.I):
            t = re.search(r'texturefile\s*=\s*"([^"]+)"', m.group(1), re.I)
            if t:
                n = re.search(r"noOfFrames\s*=\s*(\d+)", m.group(1), re.I)
                key = re.sub(r"/+", "/", t.group(1).replace("\\", "/")).lower()
                out[key] = (int(n.group(1)) if n else 1, "cornered" in m.group(0)[:40].lower() or out.get(key, (0, False))[1])
    root = VANILLA + "/gfx/interface"
    for d, _, fs in os.walk(root):                     # textures no .gfx references still ship with the game
        for f in fs:
            if f.lower().endswith((".dds", ".tga", ".png")):
                key = ("gfx/interface/" + os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/")).lower()
                out.setdefault(key, (1, False))
    return out


def find(root, path):
    """Case-insensitive lookup."""
    cur = root
    for part in path.split("/"):
        hit = next((x for x in os.listdir(cur) if x.lower() == part), None) if os.path.isdir(cur) else None
        if not hit:
            return None
        cur = os.path.join(cur, hit)
    return cur


def artwork(px, cornered):
    """True when the texture is not plain chrome: mostly see-through (glow, overlay, glyph button), or fine detail
    (a symbol, flag, ornament or picture) drawn on it. Window tiles always count as chrome."""
    core = ndimage.binary_erosion(px[..., 3] > 127, iterations=4)
    if core.sum() < 50:
        return True
    if cornered:
        return False
    lum = px[..., :3].astype(float) @ [0.299, 0.587, 0.114]
    detail = np.abs(lum - ndimage.gaussian_filter(lum, 2))[core].mean()
    return detail > 8 or (max(px.shape[:2]) < 96 and lum[core].std() > 22)


CORNERED = set()
BARS = set()
RED = np.array([226, 52, 40], float)
GREEN = np.array([60, 200, 90], float)


def bar_fill(px):
    """A bar's fill: one flat colour in the same shape; red / green / yellow keep their meaning, the rest is cyan."""
    m = px[..., 3] > 16
    rgb = px[..., :3].astype(float)
    if not m.any():
        return px
    r, g, b = np.median(rgb[m], 0)
    mx, mn = max(r, g, b), min(r, g, b)
    sat = (mx - mn) / max(mx, 1)
    col = (RED if r == mx and g < 0.4 * r else GREEN if g == mx and r < 0.75 * g else
           GOLD if r > 150 and b < 0.6 * g else CYAN) if sat > 0.35 else CYAN
    out = np.zeros(px.shape, np.uint8)
    out[..., :3] = col
    out[..., 3] = px[..., 3]
    return out


ONLY = None    # --only FILE: exactly these textures (hand-picked from audit sheets), past the name / detail filters
OUTLINE = set()


def outline(px):
    """Mostly see-through chrome (thin frames, divider lines, rings, highlights): same shape, flat house colour -
    gold for selection / highlight pieces, steel otherwise."""
    out = px.copy()
    out[..., :3] = GOLD if OUTLINE_GOLD.search(CUR) else STEEL
    return out


OUTLINE_GOLD = re.compile(r"select|_hl\b|_hl\.|gold|highlight", re.I)
CUR = ""


def candidates():
    written = set(open(LOG).read().splitlines()) if os.path.exists(LOG) else set()
    if ONLY is not None:
        sprites = vanilla_sprites()
        for path in ONLY:
            src = find(VANILLA, path)
            if src and not (find(MOD, path) and path not in written):
                px = np.array(Image.open(src).convert("RGBA"))
                frames = sprites.get(path, (1, False))[0]
                if (px[..., 3] > 127).mean() < 0.35:
                    OUTLINE.add(path)
                yield path, px, frames
        return
    for path, (frames, cornered) in sorted(vanilla_sprites().items()):
        bar = BAR.search(os.path.basename(path)) and not FX.search(path)
        if not path.startswith("gfx/interface/"):
            continue
        # catch-all: big leftover backgrounds and WWII pictures inside the interface become our panels too
        catch = not ART.search(path) and not FX.search(path) and not re.search(r"icon|check|arrow", path)
        if not bar and not catch and (SKIP.search(path) or not CHROME.search(os.path.basename(path))):
            continue
        if find(MOD, path) and path not in written:
            continue                                   # the mod's own art
        src = find(VANILLA, path)
        if not src:
            continue
        try:
            px = np.array(Image.open(src).convert("RGBA"))
        except Exception:
            continue
        thin = bar and px.shape[0] <= 40 and px.shape[1] // max(frames, 1) >= 2 * px.shape[0]
        fw0 = px.shape[1] // max(frames, 1)
        if not thin and max(fw0, px.shape[0]) <= 64 and not cornered:
            import hod_icons                           # small button with a known subject: hod_icons draws it with its symbol
            if hod_icons.pick(path):
                continue
        if thin:
            BARS.add(path)
        elif min(px.shape[:2]) < 8 or max(px.shape[:2]) < 24:
            continue
        elif artwork(px[:, :px.shape[1] // max(frames, 1)], cornered):
            fw = px.shape[1] // max(frames, 1)
            if not (catch and max(fw, px.shape[0]) >= 96 and (px[:, :fw, 3] > 127).mean() > 0.5):
                continue                               # small art = an icon (hod_icons), or see-through effects
        if cornered:
            CORNERED.add(path)
        yield path, px, frames


def lines(lum, inside, axis):
    """Long straight edges of the vanilla art (its sub-panel layout), as a mask; noise and grunge drop out."""
    g = np.abs(ndimage.sobel(ndimage.gaussian_filter(lum, 1.2), axis))
    hit = (g > max(np.percentile(g[inside], 90) if inside.any() else 0, 60)) & inside
    if axis == 1:
        return lines(lum.T, inside.T, 0).T
    keep = np.zeros_like(hit)
    minrun = max(16, int(hit.shape[1] * 0.4))      # only real dividers, not fragments
    for y in range(hit.shape[0]):
        lab, n = ndimage.label(hit[y])
        for i, s in enumerate(ndimage.find_objects(lab)):
            if s[0].stop - s[0].start >= minrun:
                keep[y, s[0]] = True
    # one line per edge: keep the row with the strongest response among adjacent rows
    lab, n = ndimage.label(keep, structure=[[0, 1, 0], [0, 1, 0], [0, 1, 0]])
    thin = np.zeros_like(keep)
    for i, s in enumerate(ndimage.find_objects(lab), 1):
        rows = (lab[s] == i).sum(1)
        thin[s.__getitem__(0).start + int(np.argmax(rows)), s[1]] |= (lab[s] == i).any(0)
    return thin


def chamfer(m, c):
    """Cut 45-degree corners (top-left and bottom-right) out of a mask: the Star Wars console-panel silhouette."""
    if c < 2:
        return m
    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    yy, xx = np.mgrid[:m.shape[0], :m.shape[1]]
    return m & ~((yy - y0) + (xx - x0) < c) & ~((y1 - yy) + (x1 - xx) < c)


def draw(px, accent, state, cornered=False):
    """state 0 normal, 1 hover, 2 pressed, 3 disabled. Matches the mod's own windows (tiled_window, header_bg,
    pol_view_bg): opaque navy plate, square corners, crisp 2px border (dim steel on big windows, cyan on buttons,
    gold on hover / pressed), vanilla's sub-panel layout as clean full steel lines."""
    m = px[..., 3] > 128
    if not m.any():
        return px
    col = {0: CYAN, 1: GOLD, 2: GOLD, 3: GREY}[state]
    if state == 0 and (cornered or max(px.shape[:2]) >= 150):
        col = STEEL
    h, w = m.shape
    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    if m.sum() > 0.8 * (y1 - y0) * (x1 - x0):      # essentially rectangular: clean box, no vanilla ornaments/notches
        m = np.zeros_like(m)
        m[y0:y1, x0:x1] = True
    rgb = np.broadcast_to(PLATE, (h, w, 3)).copy()
    if state == 2:
        rgb += GOLD * 0.12
    lum = px[..., :3].astype(float) @ [0.299, 0.587, 0.114]
    inner = ndimage.binary_erosion(m, iterations=4)
    struct = lines(lum, inner, 0) | lines(lum, inner, 1)
    rgb[struct] = STEEL if state != 3 else GREY
    edge = m & ~ndimage.binary_erosion(m, iterations=2 if min(h, w) >= 20 else 1)
    rgb[edge] = col
    return np.dstack([np.clip(rgb, 0, 255), np.where(m, 255, 0)]).astype(np.uint8)


def restyle(path, px, frames):
    global CUR
    CUR = path
    if path in OUTLINE:
        return outline(px)
    fw = px.shape[1] // max(frames, 1)
    if path in BARS and not re.search(r"bg|back|frame|border|empty", path):
        return bar_fill(px)
    parts = [draw(px[:, k * fw:(k + 1) * fw], None, (k if frames in (3, 4) else 0) if frames > 1 else 0, path in CORNERED)
             for k in range(max(frames, 1))]
    out = np.hstack(parts)
    if out.shape[1] < px.shape[1]:                     # leftover columns when width isn't a multiple of frames
        out = np.hstack([out, np.zeros((px.shape[0], px.shape[1] - out.shape[1], 4), np.uint8)])
    if "console" in path:                              # console: see-through plate, lines stay solid
        out[..., 3][(out[..., :3] == PLATE).all(-1) & (out[..., 3] > 0)] = 150
    return out


def preview(items, out, cell=150):
    cols, rw = 4, cell * 2 + 10
    sheet = Image.new("RGB", (rw * cols, (cell + 14) * ((len(items) + cols - 1) // cols)), (60, 60, 60))
    d = ImageDraw.Draw(sheet)
    for i, (path, px, frames) in enumerate(items):
        x, y = (i % cols) * rw, (i // cols) * (cell + 14)
        for k, arr in enumerate((px, restyle(path, px, frames))):
            im = Image.fromarray(arr); im.thumbnail((cell, cell))
            sheet.paste(im, (x + k * cell, y + 14), im)
        d.text((x + 2, y), path[14:][-44:], fill=(255, 230, 0))
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview"); ap.add_argument("--write", action="store_true"); ap.add_argument("--undo", action="store_true")
    ap.add_argument("--only", help="file listing texture paths to restyle (added to the log, the rest of it kept)")
    a = ap.parse_args()
    global ONLY
    if a.only:
        ONLY = [l.strip().lower() for l in open(a.only) if l.strip()]
    if a.undo:
        for path in open(LOG).read().splitlines():
            p = find(MOD, path)
            if p:
                os.remove(p)
        os.remove(LOG); print("undone"); return
    items = list(candidates())
    print(len(items), "textures", file=sys.stderr)
    if a.preview:
        preview(items, a.preview)
    if a.write:
        old = set(open(LOG).read().splitlines()) if ONLY is not None and os.path.exists(LOG) else set()
        with open(LOG, "a" if ONLY is not None else "w") as log:   # --only adds to the existing log
            for path, px, frames in items:
                dst = os.path.join(MOD, path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                buf = io.BytesIO()
                Image.fromarray(restyle(path, px, frames)).save(buf, "DDS" if dst.lower().endswith(".dds") else "TGA")
                open(dst, "wb").write(buf.getvalue())
                if path not in old:
                    log.write(path + "\n")
        print("wrote", len(items), "->", LOG)


if __name__ == "__main__":
    main()
