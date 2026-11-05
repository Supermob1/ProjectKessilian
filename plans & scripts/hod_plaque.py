"""Embossed durasteel plaque (lit height map, brushed metal): add_national_goal_button, 3 frames of 259x83."""
import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import hod_vector

W, H, SS = 259, 83, 4


def shapes():
    """Height map at SS x: bevelled plate, recessed field, raised emblem, corner brackets, grooves."""
    w, h = W * SS, H * SS
    hm = np.zeros((h, w))
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy]) / SS
    hm += np.clip(edge / 4.0, 0, 1) * 1.0                                   # outer bevel
    field = Image.new("L", (w, h), 0); d = ImageDraw.Draw(field)
    c = 6 * SS
    d.polygon([(9 * SS + c, 9 * SS), (w - 9 * SS - c, 9 * SS), (w - 9 * SS, 9 * SS + c), (w - 9 * SS, h - 9 * SS - c),
               (w - 9 * SS - c, h - 9 * SS), (9 * SS + c, h - 9 * SS), (9 * SS, h - 9 * SS - c), (9 * SS, 9 * SS + c)], fill=255)
    f = ndimage.gaussian_filter(np.array(field) / 255.0, 1.2 * SS)
    hm -= 0.6 * f                                                           # recessed field with soft walls
    br = Image.new("L", (w, h), 0); d = ImageDraw.Draw(br)                  # angular corner brackets
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        x0 = 14 * SS if sx > 0 else w - 14 * SS
        y0 = 14 * SS if sy > 0 else h - 14 * SS
        pts = [(x0, y0 + sy * 18 * SS), (x0, y0 + sy * 4 * SS), (x0 + sx * 4 * SS, y0), (x0 + sx * 30 * SS, y0)]
        d.line(pts, fill=255, width=int(2.4 * SS), joint="curve")
        d.line([(x0 + sx * 36 * SS, y0), (x0 + sx * 44 * SS, y0)], fill=255, width=int(2.4 * SS))
    hm += 0.55 * ndimage.gaussian_filter(np.array(br) / 255.0, 0.6 * SS)
    gr = Image.new("L", (w, h), 0); d = ImageDraw.Draw(gr)                  # side grooves (vents)
    for sx in (1, -1):
        for i in range(4):
            x = (26 + i * 6) * SS if sx > 0 else w - (26 + i * 6) * SS
            d.line([(x, 30 * SS), (x, h - 30 * SS)], fill=255, width=int(1.6 * SS))
    hm -= 0.35 * ndimage.gaussian_filter(np.array(gr) / 255.0, 0.5 * SS)
    em = 58 * SS                                                            # raised emblem: Republic cog in a ring
    cov = np.array(hod_vector.render("republic", em, em, 0.0, simple=True)) / 255.0
    ring = Image.new("L", (em + 16 * SS, em + 16 * SS), 0)
    ImageDraw.Draw(ring).ellipse([2 * SS, 2 * SS, em + 14 * SS, em + 14 * SS], outline=255, width=int(2.2 * SS))
    E = np.zeros((h, w))
    y0, x0 = (h - em) // 2, (w - em) // 2
    E[y0:y0 + em, x0:x0 + em] = cov
    R = np.zeros((h, w)); r = np.array(ring) / 255.0
    R[y0 - 8 * SS:y0 - 8 * SS + r.shape[0], x0 - 8 * SS:x0 - 8 * SS + r.shape[1]] = r[:h - (y0 - 8 * SS), :]
    hm += 0.7 * ndimage.gaussian_filter(E, 0.9 * SS) + 0.5 * ndimage.gaussian_filter(R, 0.7 * SS)
    return hm, E


def render(state, seed=3):
    hm, E = shapes()
    rng = np.random.default_rng(seed)
    noise = ndimage.gaussian_filter(rng.standard_normal(hm.shape), (0.4 * SS, 16 * SS))   # brushed metal
    grain = ndimage.gaussian_filter(rng.standard_normal(hm.shape), 3 * SS)                # wear
    gy, gx = np.gradient(hm * 6 * SS + noise * 0.35)
    n = np.dstack([-gx, -gy, np.full(hm.shape, 1.0)]) / SS
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([-0.55, -0.7, 0.6]); L /= np.linalg.norm(L)
    lam = np.clip(n @ L, 0, 1)
    spec = np.clip(n @ (L + [0, 0, 1]) / np.linalg.norm(L + [0, 0, 1]), 0, 1) ** 40
    base = np.array([22, 40, 62], float)                                    # blue-grey durasteel
    yy = np.linspace(0, 1, hm.shape[0])[:, None, None]
    grad = 1.12 - 0.28 * yy                                                 # light falls from the top
    col = base * (0.35 + 1.1 * lam[..., None]) * grad * (1 + 0.05 * grain[..., None] / grain.std())
    col += spec[..., None] * np.array([120, 170, 210])
    accent = np.array([0, 176, 240]) if state == 0 else np.array([240, 192, 32])
    glow = ndimage.gaussian_filter(E, 4 * SS)                               # faint light behind the emblem
    col += glow[..., None] * accent * (0.25 if state == 0 else 0.45)
    h, w = hm.shape
    trim = np.zeros((h, w), bool)                                           # thin lit trim around the field
    t = 5 * SS
    trim[t:t + SS, t:w - t] = trim[h - t - SS:h - t, t:w - t] = True
    trim[t:h - t, t:t + SS] = trim[t:h - t, w - t - SS:w - t] = True
    col[trim] = col[trim] * 0.3 + accent * 0.75
    if state == 2:
        col *= 0.8
    im = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    return np.dstack([np.array(im), np.full((H, W), 255, np.uint8)])


if __name__ == "__main__":
    out = np.hstack([render(k) for k in range(3)])
    Image.fromarray(out).save(sys.argv[1])
    big = Image.fromarray(out).resize((out.shape[1] * 2, out.shape[0] * 2), Image.LANCZOS)
    big.save(sys.argv[1].replace(".png", "_2x.png"))
