"""Division counter unit icons (counters/divisions_large, 2 frames: unit picture + NATO symbol) in the look of the
mod's own walker counters (Assets.psd treatment): olive-green silhouette with a top-lit gradient, bevel and a soft
dark drop shadow. Frame 2 (NATO symbol) stays vanilla.
  python -B counter_icons.py            preview -> counter_review.png (walker reference, vanilla, new)
  python -B counter_icons.py --install  writes the textures (hod_icons skips these: COUNTERS)"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D); sys.path.insert(0, os.path.join(D, '..'))
from cwic_library import coverage
import hod_strips, hod_vector   # hod_vector: plain pictograms with no canon source yet

MOD = os.path.join(D, '..', '..')
VANILLA = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
COUNTERS = {p: subs[0] for p, subs in hod_strips.STRIPS.items() if '/divisions_large/' in p}
TOP, BOTTOM = np.array([150, 188, 132.]), np.array([66, 104, 64.])   # sampled from unit_walkers_light_icon
LINE = np.array([38, 56, 38.])
SS = 4


def unit(cov):
    """cov: float coverage (h x w, supersampled) -> RGBA float in the walker counter style."""
    h, w = cov.shape
    solid = ndimage.binary_fill_holes(cov > .5)
    holes = solid & (cov < .5)                         # cut detail lines -> dark lines, not see-through
    body = np.maximum(cov, holes.astype(float))
    ys = np.where(body.any(1))[0]
    t = np.clip((np.arange(h) - ys.min()) / max(np.ptp(ys), 1), 0, 1)[:, None]
    rgb = TOP * (1 - t[..., None]) + BOTTOM * t[..., None]
    rgb = np.broadcast_to(rgb, (h, w, 3)).copy()
    b = ndimage.gaussian_filter(body, 1.5 * SS)
    light = -(ndimage.sobel(b, 0) + ndimage.sobel(b, 1))   # top-left lit bevel
    rgb += np.clip(light * 90, -45, 45)[..., None]
    rgb[holes] = LINE
    out = np.zeros((h, w, 4))
    sh = ndimage.shift(ndimage.gaussian_filter(body, 1.2 * SS), (1.5 * SS, 1.5 * SS))   # soft dark drop shadow
    out[..., 3] = sh * 200
    a = body[..., None]
    out[..., :3] = rgb * a
    out[..., 3] = np.maximum(out[..., 3], body * 255)
    return out


def render(path, subject):
    van = np.array(Image.open(os.path.join(VANILLA, path)).convert('RGBA'))
    h, W = van.shape[:2]
    fw = W // 2
    x0, y0, x1, y1 = 6, 2, min(fw - 12, 62), h - 3    # walker counters' picture box
    bw, bh = (x1 - x0) * SS, (y1 - y0) * SS
    cov = np.zeros((h * SS, fw * SS))
    cov[y0 * SS:y0 * SS + bh, x0 * SS:x0 * SS + bw] = np.array(coverage(subject, bw, bh) or hod_vector.render(subject, bw, bh)) / 255.0
    big = unit(cov)
    small = np.array(Image.fromarray(np.clip(big, 0, 255).astype(np.uint8)).resize((fw, h), Image.LANCZOS))
    out = van.copy()
    out[:, :fw] = small
    f0 = van[:, :fw].astype(int)                       # keep vanilla's blue "+" (support company / attachment marker)
    plus = (f0[..., 3] > 60) & (f0[..., 2] > f0[..., 0] + 60) & (f0[..., 2] > f0[..., 1] + 30)
    out[:, :fw][plus] = van[:, :fw][plus]
    return van, out


if __name__ == '__main__':
    rows = []
    for path, subject in sorted(COUNTERS.items()):
        van, new = render(path, subject)
        if '--install' in sys.argv:
            Image.fromarray(new).save(os.path.join(MOD, path))
        rows.append((path, van, new))
    ref = Image.open(os.path.join(MOD, 'gfx/interface/counters/divisions_large/unit_walkers_light_icon.dds')).convert('RGBA')
    sheet = Image.new('RGBA', (3 * 2 * 160 + 40, 90 * ((len(rows) + 1) // 2)), (60, 60, 60, 255)); d = ImageDraw.Draw(sheet)
    for i, (path, van, new) in enumerate(rows):
        x, y = (i % 2) * 500, (i // 2) * 90
        d.text((x, y), os.path.basename(path), fill=(255, 230, 0))
        for j, im in enumerate((ref, Image.fromarray(van), Image.fromarray(new))):
            sheet.alpha_composite(im.crop((0, 0, im.width // 2, im.height)).resize((im.width, im.height * 2), Image.NEAREST),
                                  (x + j * 160, y + 12))
    sheet.save(os.path.join(D, 'counter_review.png')); print('ok', len(rows))
