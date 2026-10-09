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
# region outer radii (map units) from the canonical chart, fitted onto this map
RINGS = [185.0, 320.0, 460.0, 640.0, 850.0, 1200.0, 1600.0]   # deep core, core, colonies, inner, expansion, mid, outer
SHIFT = np.array([0.22, -0.12])                                  # outer regions bulge east and south
GRID_CELL = np.array([191.3, 187.5]); GRID_ORIGIN = np.array([-847.0, 3499.0])


def galaxy(X, Z):
    P = np.stack([X, Z], -1)
    wob = (fbm(X * .002, Z * .002) - .5)
    # distance to the core in "region units": rings are circles whose centres drift east/south as they grow
    d0 = np.hypot(X - CORE[0], Z - CORE[1])
    c = CORE + SHIFT * d0[..., None] * 0.5
    r = np.hypot(X - c[..., 0], Z - c[..., 1]) * (1 + wob * 0.18)
    # region index (fractional) and fills
    edges = np.array(RINGS)
    idx = np.interp(r, np.concatenate([[0], edges]), np.arange(len(edges) + 1))
    fill = np.interp(idx, [0, 1, 2, 3, 4, 5, 6, 7, 8], [1.0, .62, .44, .34, .27, .19, .12, .05, 0])
    # thin outlines at each boundary
    line = np.zeros_like(r)
    for e in edges[1:]:
        line = np.maximum(line, 1 - sat(np.abs(r - e) / 3.5))
    line *= sat(1.3 - r / edges[-1])
    # galactic disk haze + faint outer spiral arms
    th = np.arctan2(Z - CORE[1], X - CORE[0])
    rn = d0 / 1700
    phi = th - np.log(np.maximum(rn, .05)) / .28 + .4 + (fbm(X * .0018, Z * .0018) - .5) * 0.9
    arm = sat(.5 + .5 * np.cos(2 * phi)) ** 4 * sat((rn - .3) * 3) * sat(1.7 - rn)
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
