"""KOTOR UI kit for HOI4: rebuilds vanilla interface chrome out of pieces of KOTOR 'Remastered UI 1.3'.
PERSONAL USE ONLY: the output contains KOTOR / Remastered UI art (not ours to publish).

  window tiles (corneredTile)  -> navy panel, rounded steel-blue corners  (lbl_cg_mcgtopl)
  buttons (2+ frames, flat)    -> navy bar with ( ) brackets: cyan / yellow hover / selected / dimmed  (SCR_DEF_*)
  flat panels and strips       -> navy panel with rounded corners, or bracket bar when thin
  checkboxes (2 frames)        -> KOTOR rings (i_checkbox01/02)
  scroll draggers              -> blue pill (lbl_miscroll_f)
  anything with glyphs/art     -> recoloured onto the KOTOR palette (keeps the glyph)

  python kotor_ui.py --preview OUT.png [--limit N]   before/after sheet
  python kotor_ui.py --mockup OUT.png                a fake HOI4 window built from the generated pieces
  python kotor_ui.py --list | --write                undo: kotor_ui_written.txt lists every path written;
                                                     the mod's own originals are saved in WIPGFX/Assets/ui_backup/
"""
import argparse, glob, io, os, re, shutil, sys
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage

VANILLA = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
KOTOR = r"C:/Users/steve/Desktop/Remastered UI 1.3/Override"
MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOG = os.path.join(os.path.dirname(__file__), "kotor_ui_written.txt")
BACKUP = os.path.join(MOD, "WIPGFX", "Assets", "ui_backup")   # the mod's own textures as they were before kotor_ui

NAVY = (0, 1, 22)
RAMP = np.array([[0, 0, 0], [0, 1, 22], [0, 88, 137], [0, 172, 248], [210, 240, 255]], float)

CHROME = re.compile(r"(bg|background|button|btn|frame|box|window|tile|strip|entry|tab|scroll|slider|"
                    r"checkbox|popup|bar|panel|header|border|overlay|plate|holder|dragger)", re.I)
SKIP = re.compile(r"(techtree_bg|_line|line_|anim|progress|arrow|fill|meter|gauge|propaganda|icon|flag|portrait|leader|equipmentdesigner|counters|goals|ideas|technolog|traits|aces/|"
                  r"pdx_online|event_pictures|loadingscreen|mapmode|texticon|unit_|medal|ribbon|logo|_pic|career)", re.I)


def kimg(name):
    return Image.open(f"{KOTOR}/{name}.tga").convert("RGBA")


# --- KOTOR pieces -----------------------------------------------------------------------------------
# lbl_cg_mcgtopl: top-left rounded corner (steel-blue arc, navy interior towards bottom-right)
def _panel_corner(img):
    """KOTOR draws this piece as an overlay (navy outside the arc, see-through inside); flip it into a filled corner."""
    a = np.array(img).astype(float)
    navy_out = (a[..., 3] > 200) & (np.abs(a[..., :3] - NAVY).sum(-1) < 12)
    lab, _ = ndimage.label(navy_out)
    outside = lab == lab[0, 0]
    alpha = a[..., 3:4] / 255
    rgb = a[..., :3] * alpha + np.array(NAVY) * (1 - alpha)       # line over a navy interior
    out = np.dstack([rgb, np.where(outside, 0, 255)])
    return Image.fromarray(out.astype(np.uint8))


CORNER = _panel_corner(kimg("lbl_cg_mcgtopl"))
_c = np.array(CORNER).astype(float); _line = _c[..., 1] > 30          # steel-blue line -> KOTOR hover yellow
_c[_line, :3] = (_c[_line, 1] / 137)[:, None] * [248, 252, 0]
CORNER_HI = Image.fromarray(np.clip(_c, 0, 255).astype(np.uint8))
BUTTONS = [kimg(n) for n in ("SCR_DEF_NN", "SCR_DEF_NC", "SCR_DEF_SC", "SCR_DEF_NN")]   # normal hover pressed disabled
BUTTONS[3] = Image.fromarray((np.array(BUTTONS[3]) * [0.45, 0.45, 0.45, 1]).astype(np.uint8))
CHECK = [kimg("i_checkbox01"), kimg("i_checkbox02")]
PILL = kimg("lbl_miscroll_f")


def nine(corner, w, h, b):
    """Panel of w x h with b-px corners cut from the KOTOR corner piece; edges/centre stretched."""
    b = max(2, min(b, w // 2, h // 2))
    c = corner.resize((b, b), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), NAVY + (255,))
    edge_t = c.crop((b - 1, 0, b, b)).resize((max(w - 2 * b, 1), b))       # last column of the corner = top edge
    edge_l = c.crop((0, b - 1, b, b)).resize((b, max(h - 2 * b, 1)))       # last row = left edge
    out.paste(edge_t, (b, 0)); out.paste(ImageOps.flip(edge_t), (b, h - b))
    out.paste(edge_l, (0, b)); out.paste(ImageOps.mirror(edge_l), (w - b, b))
    for img, pos in ((c, (0, 0)), (ImageOps.mirror(c), (w - b, 0)), (ImageOps.flip(c), (0, h - b)),
                     (ImageOps.flip(ImageOps.mirror(c)), (w - b, h - b))):
        out.paste(img, pos)
    return out


def bracket_bar(src, w, h):
    """3-slice a SCR_DEF button: keep the ( ) caps at their aspect, stretch the plain middle."""
    s = h / src.height
    cap = max(1, min(int(round(30 * s)), w // 2))
    srccap = int(round(cap / s))
    l = src.crop((0, 0, srccap, src.height)).resize((cap, h), Image.LANCZOS)
    r = src.crop((src.width - srccap, 0, src.width, src.height)).resize((cap, h), Image.LANCZOS)
    mid = src.crop((srccap, 0, src.width - srccap, src.height)).resize((max(w - 2 * cap, 1), h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h)); out.paste(l, (0, 0)); out.paste(mid, (cap, 0)); out.paste(r, (w - cap, 0))
    return out


def fit(src, w, h):
    im = src.copy(); im.thumbnail((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h)); out.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return out


def tint(px):
    rgb, a = px[..., :3].astype(float), px[..., 3]
    lum = rgb @ [0.299, 0.587, 0.114]
    vis = lum[a > 16]
    lo, hi = np.percentile(vis, [5, 98]) if vis.size else (0, 255)
    t = np.clip((lum - lo) / max(hi - lo, 1), 0, 1) * (len(RAMP) - 1)
    i = np.minimum(t.astype(int), len(RAMP) - 2)
    f = (t - i)[..., None]
    return np.dstack([RAMP[i] * (1 - f) + RAMP[i + 1] * f, a]).astype(np.uint8)


# --- vanilla sprites ----------------------------------------------------------------------------------
def read(p):
    return open(p, encoding="utf-8-sig", errors="ignore").read()


def vanilla_sprites():
    """texture path -> (frames, borderSize or None)."""
    out = {}
    for f in glob.glob(VANILLA + "/interface/**/*.gfx", recursive=True):
        for m in re.finditer(r"(spriteType|corneredTileSpriteType)\s*=\s*\{(.*?)\n\s*\}", read(f), re.S | re.I):
            body = m.group(2)
            t = re.search(r'texturefile\s*=\s*"([^"]+)"', body, re.I)
            if not t:
                continue
            path = re.sub(r"/+", "/", t.group(1).replace("\\", "/")).lower()
            n = re.search(r"noOfFrames\s*=\s*(\d+)", body, re.I)
            bs = re.search(r"borderSize\s*=\s*\{\s*x\s*=\s*(\d+)", body, re.I)
            cornered = m.group(1).lower().startswith("cornered")
            out[path] = (int(n.group(1)) if n else 1, int(bs.group(1)) if cornered and bs else None)
    return out


def mod_file(path):
    """The mod's own file for a vanilla texture path (case-insensitive), or None."""
    d, b = os.path.split(os.path.join(MOD, path))
    if os.path.isdir(d):
        for x in os.listdir(d):
            if x.lower() == b.lower():
                return os.path.join(d, x)
    return None


def candidates():
    """(path, source, frames, border). Source = vanilla, or the mod's own pre-kotor file (from BACKUP once saved)."""
    written = set(l.strip() for l in open(LOG)) if os.path.exists(LOG) else set()
    for path, (frames, border) in sorted(vanilla_sprites().items()):
        if not (border is not None or (CHROME.search(os.path.basename(path)) and not SKIP.search(path))):
            continue
        if mod_file(path) and path not in written:
            continue                     # the mod's own art: never touched (user: those looked fine)
        src = os.path.join(VANILLA, path)
        if os.path.exists(src):
            yield path, src, frames, border


def screen(px, corner):
    """Big detailed backgrounds: KOTOR navy screen, the vanilla layout (slots, dividers) traced as thin steel lines."""
    h, w = px.shape[:2]
    base = np.array(nine(corner, w, h, min(32, min(w, h) // 6))).astype(float)
    lum = ndimage.gaussian_filter(px[..., :3].astype(float) @ [0.299, 0.587, 0.114], 1.2)
    mag = np.hypot(ndimage.sobel(lum, 0), ndimage.sobel(lum, 1))
    thr = max(np.percentile(mag, 96), 40)
    line = np.clip((mag - thr) / thr, 0, 1)[..., None] * 0.8     # ponytail: plain edge trace; noisy art gives noisy lines
    base[..., :3] = base[..., :3] * (1 - line) + np.array([0, 88, 137]) * line
    base[..., 3] = np.minimum(base[..., 3], px[..., 3])            # keep the vanilla silhouette
    return base.astype(np.uint8)


def restyle(src, frames, border):
    px = np.array(Image.open(src).convert("RGBA"))
    h, w = px.shape[:2]
    fw = w // max(frames, 1)
    name = os.path.basename(src).lower()
    corner = CORNER_HI if re.search(r"select|highlight|hover", name) else CORNER
    if border is not None:
        return np.array(nine(corner, w, h, max(border // 2, 6))), "window"
    if "drager" in name or "dragger" in name:
        return np.array(fit(PILL, w, h)), "pill"
    f0 = px[:, :fw]
    core = ndimage.binary_erosion(f0[..., 3] > 127, iterations=3)
    lum = f0[..., :3].astype(float) @ [0.299, 0.587, 0.114]
    flat = core.sum() > 0 and lum[core].std() < 18
    if "checkbox" in name and frames == 2 and fw / h < 2 and (flat or core.sum() == 0):
        return np.hstack([np.array(fit(c, fw, h)) for c in CHECK]), "checkbox"
    if not flat and max(w, h) < 96:
        return tint(px), "tint"                                     # icons / glyph buttons: keep the glyph
    if frames >= 2 and (flat or fw >= 60):
        return np.hstack([np.array(bracket_bar(BUTTONS[min(k, 3)], fw, h)) for k in range(frames)]), "button"
    if frames >= 2:
        return tint(px), "tint"
    if h < 48 or w / h > 5:
        return np.array(bracket_bar(BUTTONS[0], w, h)), "bar"
    return screen(px, corner), ("screen" if not flat else "panel")


def save(arr, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im = Image.fromarray(arr, "RGBA")
    buf = io.BytesIO()
    im.save(buf, "DDS" if dst.lower().endswith(".dds") else "TGA")   # uncompressed, like the mod's UI textures
    open(dst, "wb").write(buf.getvalue())


def preview(items, out, cell=160):
    rows = []
    for path, src, frames, border in items:
        before = Image.open(src).convert("RGBA")
        after, mode = restyle(src, frames, border)
        row = Image.new("RGB", (cell * 2 + 260, cell), (90, 90, 90))
        for i, im in enumerate((before, Image.fromarray(after))):
            im = im.copy(); im.thumbnail((cell, cell))
            row.paste(im, (i * cell, 0), im)
        ImageDraw.Draw(row).text((cell * 2 + 4, 4), f"{mode} x{frames}\n{path[-40:]}", fill=(255, 255, 0))
        rows.append(row)
    sheet = Image.new("RGB", (rows[0].width * 3, cell * ((len(rows) + 2) // 3)))
    for i, r in enumerate(rows):
        sheet.paste(r, ((i % 3) * r.width, (i // 3) * cell))
    sheet.save(out)


def mockup(out):
    """What a HOI4 window looks like with the kit: window tile, list bars, buttons in each state, checkboxes."""
    W, H = 900, 560
    bg = Image.new("RGBA", (W + 80, H + 80), (40, 44, 52, 255))
    bg.alpha_composite(nine(CORNER, W, H, 48), (40, 40))
    d = ImageDraw.Draw(bg)
    d.text((80, 62), "PROJECT KESSILIAN - DIPLOMACY", fill=(0, 172, 248))
    for i in range(6):   # list rows
        bg.alpha_composite(bracket_bar(BUTTONS[0] if i != 2 else BUTTONS[2], 420, 44), (80, 110 + i * 54))
        d.text((120, 125 + i * 54), f"Entry {i + 1}", fill=(200, 230, 255))
    bg.alpha_composite(nine(CORNER, 340, 330, 24), (560, 110))
    for i, lab in enumerate(("Normal", "Hover", "Pressed", "Disabled")):
        bg.alpha_composite(bracket_bar(BUTTONS[i], 190, 40), (80 + i * 205, 480))
        d.text((140 + i * 205, 492), lab, fill=(200, 230, 255) if i < 3 else (90, 90, 100))
    for i, c in enumerate(CHECK):
        bg.alpha_composite(fit(c, 32, 32), (590 + i * 50, 140))
    bg.alpha_composite(fit(PILL, 28, 120), (860, 160))
    bg.convert("RGB").save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview"); ap.add_argument("--limit", type=int, default=60); ap.add_argument("--mockup")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.mockup:
        mockup(args.mockup)
    items = list(candidates()) if (args.list or args.preview or args.write) else []
    if args.list:
        for it in items:
            print(it[0])
        print(len(items), "textures", file=sys.stderr)
    if args.preview:
        preview(items[:args.limit], args.preview)
    if args.write:
        done = set(l.strip() for l in open(LOG)) if os.path.exists(LOG) else set()
        n = 0
        with open(LOG, "a") as log:
            for path, src, frames, border in items:
                arr, mode = restyle(src, frames, border)
                own = mod_file(path)
                mod_art = own and path not in done
                if mod_art and mode in ("tint", "screen"):
                    continue                     # the mod's own artwork (detailed): leave it as the author made it
                bak = os.path.join(BACKUP, path)
                if mod_art and not os.path.exists(bak):
                    os.makedirs(os.path.dirname(bak), exist_ok=True)
                    shutil.copy2(own, bak)       # original kept for undo
                save(arr, own or os.path.join(MOD, path)); n += 1
                if path not in done:
                    log.write(path + "\n")
        # paths written by an earlier run that the rules now exclude: give them back to vanilla / the mod original
        keep = {it[0] for it in items}
        for path in set(l.strip() for l in open(LOG)) - keep:
            bak, own = os.path.join(BACKUP, path), mod_file(path)
            if os.path.exists(bak):
                shutil.copy2(bak, own or os.path.join(MOD, path))
            elif own:
                os.remove(own)
        lines = [l for l in open(LOG) if l.strip() in keep]
        open(LOG, "w").writelines(lines)
        print("wrote", n, "textures; list in", LOG, "; mod originals in", BACKUP)


if __name__ == "__main__":
    main()
