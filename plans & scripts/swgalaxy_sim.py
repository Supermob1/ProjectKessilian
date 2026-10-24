"""Numpy twin of GalaxyColor() in gfx/FX/pdxwater.shader (Star Wars chart layout). Keep the two in sync."""
import io, sys
import numpy as np
from PIL import Image

fr = lambda x: x - np.floor(x)
sat = lambda a: np.clip(a, 0, 1)


def hsh(x, y):
    p = np.stack([fr(x * 0.1031), fr(y * 0.1031), fr(x * 0.1031)], -1)
    p = p + (p * (p[..., [1, 2, 0]] + 33.33)).sum(-1, keepdims=True)
    return fr((p[..., 0] + p[..., 1]) * p[..., 2])


def vn(x, y):
    ix, iy = np.floor(x), np.floor(y); fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b, c, d = hsh(ix, iy), hsh(ix + 1, iy), hsh(ix, iy + 1), hsh(ix + 1, iy + 1)
    return (a + (b - a) * ux) + ((c + (d - c) * ux) - (a + (b - a) * ux)) * uy


def fbm(x, y):
    v = 0; amp = .5
    for _ in range(5):
        v = v + amp * vn(x, y); x, y = x * 2.03 + 17.1, y * 2.03 + 9.2; amp *= .5
    return v


CORE = np.array([880.0, 1700.0])
CELL = 215.0   # map units per canon chart square (starwars.com galaxy map, DK 2025), sized so the Outer Rim covers the planets
# canon regions as ellipses (cells, +x east, +z north): centre offset from the Deep Core, radius x, radius z, line strength
REGIONS = [  # deep core, core, colonies, inner rim, expansion, mid rim, outer rim
    ((0.00, 0.00), 1.25, 1.25, 0.0), ((0.16, -0.04), 2.31, 2.15, 1.0), ((0.18, 0.00), 2.90, 2.73, 1.0),
    ((0.39, -0.12), 3.56, 3.82, 1.0), ((0.70, -0.37), 4.23, 4.45, 1.0), ((1.53, -0.92), 5.49, 5.85, 1.0),
    ((2.59, -0.14), 7.08, 9.89, 0.45)]
FILLS = [1.0, .62, .44, .34, .27, .19, .12, .05]   # brightness at each boundary, centre outwards
HUTT = ((7.48, -0.18), 1.32, 2.55)                  # Hutt Space sector, outline only
GRID_CELL = np.array([CELL, CELL]); GRID_ORIGIN = np.array([860.6, 1778.0])   # deep core sits at canon grid L/M-11


def ellipse_e(X, Z, c, rx, rz, wob):
    """normalised elliptical radius (1 on the boundary) and an approximate distance to the boundary in map units"""
    e = np.hypot((X - CORE[0] - c[0] * CELL) / (rx * CELL), (Z - CORE[1] - c[1] * CELL) / (rz * CELL)) * wob
    return e, np.abs(e - 1) * min(rx, rz) * CELL


def galaxy(X, Z):
    P = np.stack([X, Z], -1)
    wob = 1 + (fbm(X * .002, Z * .002) - .5) * 0.18
    rag = wob + (fbm(X * .006 + 11, Z * .006 + 11) - .5) * 0.22    # ragged Outer Rim / Hutt edge
    es = []
    line = np.zeros_like(X)
    for i, (c, rx, rz, ls) in enumerate(REGIONS):
        e, dist = ellipse_e(X, Z, c, rx, rz, rag if i == 6 else wob)
        es.append(e)
        line = np.maximum(line, (1 - sat(dist / 3.5)) * ls)
    e, dist = ellipse_e(X, Z, HUTT[0], HUTT[1], HUTT[2], rag)
    line = np.maximum(line, (1 - sat(dist / 3.5)) * .7)
    # fill: outside the Outer Rim fades out, each band blends from its outer to its inner boundary value
    fill = np.maximum(FILLS[7] - (es[6] - 1) * .3, 0)
    for i in range(6, 0, -1):
        u = sat((1 - es[i]) / np.maximum((1 - es[i]) + (es[i - 1] - 1), 1e-4))
        fill = np.where(es[i] < 1, FILLS[i + 1] + (FILLS[i] - FILLS[i + 1]) * u, fill)
    fill = np.where(es[0] < 1, FILLS[1] + (FILLS[0] - FILLS[1]) * (1 - es[0]), fill)
    d0 = np.hypot(X - CORE[0], Z - CORE[1])
    # galactic disk haze + faint outer spiral arms
    th = np.arctan2(Z - CORE[1], X - CORE[0])
    rn = d0 / 1700
    phi = th - np.log(np.maximum(rn, .05)) / .28 + .4 + (fbm(X * .0018, Z * .0018) - .5) * 0.9
    arm = sat(.5 + .5 * np.cos(2 * phi)) ** 4 * sat((rn - .3) * 3) * sat(1.7 - rn)
    arm *= .3 + .7 * sat((es[5] - .95) * 5)   # canon chart: arms swirl outside the Mid Rim, not through known space
    grain = fbm(X * .03 + 3, Z * .03 + 3)
    haze = np.exp(-rn / .45) * (.6 + .5 * fbm(X * .006 + 40, Z * .006 + 40))
    col = np.zeros(X.shape + (3,))
    col += np.array([.08, .17, .25]) * (haze * 0.32)[..., None]
    col += np.array([.20, .40, .52]) * (arm * (.35 + .9 * grain) * .6)[..., None]
    col += np.array([.30, .50, .62]) * (fill * .28)[..., None]
    col += np.array([.55, .78, .90]) * (line * .22)[..., None]
    col += np.array([1.0, .97, .92]) * (np.exp(-(d0 / 150) ** 2) * 1.15)[..., None]          # deep core
    col += np.array([.75, .88, 1.0]) * (np.exp(-(d0 / 330) ** 2) * .35)[..., None]          # core glow
    # Unknown Regions: murky west
    west = sat((CORE[0] - 350 - X) / 400) * sat(1.4 - np.abs(Z - CORE[1]) / 1400)
    murk = .35 + .4 * fbm(X * .004 + 70, Z * .004 + 70)
    col *= (1 - west[..., None] * (1 - murk)[..., None] * .9)
    # coordinate grid
    g = np.abs(fr((P - GRID_ORIGIN) / GRID_CELL) - .5) * GRID_CELL
    grid = 1 - sat(np.minimum(g[..., 0], g[..., 1]) / 1.0)
    col += np.array([.35, .45, .5]) * (grid * .10)[..., None]
    return col + np.array([.003, .005, .012])


if __name__ == "__main__":
    out = sys.argv[1]; step = 4
    X, row = np.meshgrid(np.arange(0, 3072, step) + .5, np.arange(0, 3328, step) + .5); Z = 3328 - row
    c = galaxy(X, Z)
    img = np.clip(c * .85, 0, 1) ** (1 / 2.2)
    land = np.array(Image.open(io.BytesIO(open(sys.argv[2], "rb").read())).convert("L"))[::step, ::step] > 95
    img[land] = img[land] * .3 + np.array([.55, .5, .45]) * .7
    Image.fromarray((img * 255).astype(np.uint8)).save(out)
