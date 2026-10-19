"""Architecture kit for the planet landmark and city meshes built by military_buildings.py models (Blender), and the
landmarks / city sets of Etti IV, Mon Cala, Lianna, Jabiim, Saleucami, Bonadan, Telos, Serenno, Yavin IV, Celanon,
Botajef, Axxila and Ciutric IV built with it.

The user's review (2026-10-17): every building read as "a big circle slab under a tall tower or a generic building".
So: no round aprons, nothing centred on a disc; shapes come from lofted cross-sections (fluted, rounded, lobed),
sweeps along paths (viaducts, terraces, walls, berms, piers), recessed window bands and fins; city cells grow along
streets that meet their neighbours at the cell edges' midpoints (cells are 2 map units apart), so a city reads as a
street network instead of scattered towers.

Every function takes the Kit `k` of military_buildings.models (k.bm, k.put(face, uvs, rect), k.lathe, k.tube) and
works in map units, z up, the origin on the ground. Walls reach down to -SKIRT (landmarks) or -0.3 (city cells).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from military_buildings import (B_CONC, B_CONC_WIN, B_DARK, B_DUST, B_GIRDER, B_GLOW, B_HAZARD, B_HULL,  # noqa: E402
                                B_PAD, B_PIPE, B_PLATE, B_PLATE_WIN, B_ROOF, B_RUST, B_SOOT, B_BRICK,
                                E_CERAMIC, E_CERAMIC_WIN, E_COBALT, E_COBALT_WIN, E_DOME, E_GARDEN, E_GLASS,
                                E_GLASS_LIT, E_GLOW, E_GOLD, E_HAZARD, E_NEON, E_PAD, E_ROOF, E_STEEL)

SKIRT = 2.5         # landmark walls run this far below the origin (= military_buildings.models SKIRT)
CELL_Z = -0.3       # city-cell walls start here
TAU = 2 * math.pi


# ---------------------------------------------------------------------------------------------------- rings & paths
def turn(x, y, a, u, v):
    """local (u, v) of a frame at (x, y) turned by a -> world (x, y)"""
    return x + u * math.cos(a) - v * math.sin(a), y + u * math.sin(a) + v * math.cos(a)


def ring(cx, cy, z, r, n=16, rot=0.0, sy=1.0):
    return [(cx + r * math.cos(rot + TAU * i / n), cy + sy * r * math.sin(rot + TAU * i / n), z) for i in range(n)]


def rrect(cx, cy, z, w, d, rc, a=0.0, seg=3):
    """rounded rectangle, half sizes w, d, corner radius rc (<= min(w, d)), turned by a: 4 * (seg + 1) points CCW"""
    rc = min(rc, w, d)
    pts = []
    for q, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        ox, oy = sx * (w - rc), sy * (d - rc)
        for s in range(seg + 1):
            t = q * math.pi / 2 + (math.pi / 2) * s / seg
            pts.append(turn(cx, cy, a, ox + rc * math.cos(t), oy + rc * math.sin(t)) + (z,))
    return pts


def star(cx, cy, z, r, depth, ribs, rot=0.0):
    """fluted section: 2 * ribs points, ribs at r, grooves at r * (1 - depth)"""
    return [(cx + rr * math.cos(rot + math.pi * i / ribs), cy + rr * math.sin(rot + math.pi * i / ribs), z)
            for i in range(2 * ribs) for rr in [r if i % 2 == 0 else r * (1 - depth)]]


def lobed(cx, cy, z, r, lobes=3, amp=0.2, n=24, phase=0.0, sy=1.0, amp2=0.08):
    """an organic outline: a circle swollen into lobes (reefs, knolls, mounds) - never a plain disc"""
    out = []
    for i in range(n):
        t = TAU * i / n
        rr = r * (1 + amp * math.sin(lobes * t + phase) + amp2 * math.sin((2 * lobes + 1) * t + 2 * phase))
        out.append((cx + rr * math.cos(t), cy + sy * rr * math.sin(t), z))
    return out


def at_z(pts, z):
    return [(p[0], p[1], z) for p in pts]


def scaled(pts, f, cx=None, cy=None):
    """pts shrunk/grown by f about their centroid (or cx, cy)"""
    cx = sum(p[0] for p in pts) / len(pts) if cx is None else cx
    cy = sum(p[1] for p in pts) / len(pts) if cy is None else cy
    return [(cx + (p[0] - cx) * f, cy + (p[1] - cy) * f, p[2]) for p in pts]


def bezier(p0, p1, p2, n=8):
    """quadratic Bezier p0 -> p1 (control) -> p2, n + 1 points (2D or 3D)"""
    return [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t * t * c for a, b, c in zip(p0, p1, p2))
            for t in (i / n for i in range(n + 1))]


def arc_path(cx, cy, z, r, a0, a1, n=16):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n), z) for i in range(n + 1)]


def offset_path(path, d):
    """a path shifted sideways by d (left of its direction +)"""
    out = []
    for i, (x, y, z) in enumerate(path):
        a, b = path[max(i - 1, 0)], path[min(i + 1, len(path) - 1)]
        h = math.atan2(b[1] - a[1], b[0] - a[0])
        out.append((x - math.sin(h) * d, y + math.cos(h) * d, z))
    return out


def sub_path(path, s0, s1, n=6):
    """the stretch of a path between arc lengths s0 and s1, resampled"""
    return [path_at(path, s0 + (s1 - s0) * i / n)[0] for i in range(n + 1)]


def path_len(path):
    return sum(math.dist(a[:2], b[:2]) for a, b in zip(path, path[1:]))


def path_at(path, s):
    """point and heading at arc length s along a path"""
    for a, b in zip(path, path[1:]):
        L = math.dist(a[:2], b[:2])
        if s <= L or b is path[-1]:
            t = min(1.0, s / L) if L else 0.0
            return tuple(p + (q - p) * t for p, q in zip(a, b)), math.atan2(b[1] - a[1], b[0] - a[0])
        s -= L
    return path[-1], 0.0


# ---------------------------------------------------------------------------------------------------- surfaces
def _cap(k, verts, pts, rect):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    sx, sy = max(max(xs) - min(xs), 1e-4), max(max(ys) - min(ys), 1e-4)
    k.put(k.bm.faces.new(verts), [((p[0] - min(xs)) / sx, (p[1] - min(ys)) / sy) for p in pts], rect)


def loft(k, rings, rects, cap=None, base=None, closed=True):
    """skin through rings of equal length (CCW from above); rects[i] (or one rect) textures segment i, one whole atlas
    cell per face so window rows keep their size; `cap` closes the last ring, `base` the first"""
    vs = [[k.bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    m = n if closed else n - 1
    for s in range(len(vs) - 1):
        rect = rects[s] if isinstance(rects, list) else rects
        lo, hi = vs[s], vs[s + 1]
        for i in range(m):
            j = (i + 1) % n
            k.put(k.bm.faces.new((lo[i], lo[j], hi[j], hi[i])), ((0, 0), (1, 0), (1, 1), (0, 1)), rect)
    if cap:
        _cap(k, vs[-1], rings[-1], cap)
    if base:
        _cap(k, vs[0][::-1], rings[0][::-1], base)


def banded(k, ring_at, z0, z1, floors, wall, win, inset=0.04, ledge=None, cap=None, sill=0.35):
    """a shaft of `floors` storeys: per storey a wall band then a window band set back by `inset` (real recesses
    and ledges, not painted ones). ring_at(z, grow) -> ring, grow = -inset for the window bands"""
    rings, rects = [ring_at(z0, 0.0)], []
    fh = (z1 - z0) / floors
    for f in range(floors):
        za, zs, zb = z0 + f * fh, z0 + f * fh + sill * fh, z0 + (f + 1) * fh
        rings += [ring_at(zs, 0.0), ring_at(zs, -inset), ring_at(zb, -inset), ring_at(zb, 0.0)]
        rects += [wall, ledge or wall, win, ledge or wall]
        del za
    loft(k, rings, rects, cap=cap)


def sweep(k, path, section, rects, caps=None, closed_path=False, open_sec=False):
    """a cross-section [(across, up)...] (CCW looking along the path) carried along path [(x, y, z)...], kept
    upright and mitred at the corners; rects[i] (or one rect) textures section edge i; `caps` closes the ends;
    open_sec leaves out the edge from the last section point back to the first (a buried bottom)"""
    n, frames = len(path), []
    for i, (x, y, z) in enumerate(path):
        prv = path[i - 1] if i > 0 else (path[-1] if closed_path else None)
        nxt = path[i + 1] if i < n - 1 else (path[0] if closed_path else None)
        dirs = []
        for a, b in ((prv, (x, y)), ((x, y), nxt)):
            if a is not None and b is not None:
                L = math.dist(a[:2], b[:2]) or 1e-6
                dirs.append(((b[0] - a[0]) / L, (b[1] - a[1]) / L))
        tx, ty = sum(d[0] for d in dirs), sum(d[1] for d in dirs)
        L = math.hypot(tx, ty) or 1e-6
        tx, ty = tx / L, ty / L
        miter = 1.0 / max(0.35, dirs[0][0] * tx + dirs[0][1] * ty) if len(dirs) == 2 else 1.0
        frames.append([(x - ty * u * miter, y + tx * u * miter, z + h) for u, h in section])
    vs = [[k.bm.verts.new(p) for p in f] for f in frames]
    m = len(section)
    for s in range(len(vs) - (0 if closed_path else 1)):
        lo, hi = vs[s], vs[(s + 1) % len(vs)]
        for e in range(m - 1 if open_sec else m):
            f_ = (e + 1) % m
            rect = rects[e] if isinstance(rects, list) else rects
            k.put(k.bm.faces.new((lo[e], lo[f_], hi[f_], hi[e])), ((0, 0), (1, 0), (1, 1), (0, 1)), rect)
    if caps and not closed_path:
        k.put(k.bm.faces.new(vs[0][::-1]), [(0.5 + 0.5 * math.cos(TAU * i / m), 0.5 + 0.5 * math.sin(TAU * i / m))
                                           for i in range(m)][::-1], caps)
        k.put(k.bm.faces.new(vs[-1]), [(0.5 + 0.5 * math.cos(TAU * i / m), 0.5 + 0.5 * math.sin(TAU * i / m))
                                       for i in range(m)], caps)


def rect_section(w, h, z0=0.0):
    """CCW from the bottom-right: right wall, top, left wall, bottom (the last edge: left out with open_sec)"""
    return [(w / 2, z0), (w / 2, z0 + h), (-w / 2, z0 + h), (-w / 2, z0)]


def trap_section(wb, wt, h, z0=0.0):
    """a berm / dyke / rampart: bottom width wb, top width wt"""
    return [(-wb / 2, z0), (wb / 2, z0), (wt / 2, z0 + h), (-wt / 2, z0 + h)]


def tbox(k, x, y, z0, z1, w, d, a, wall, top, wt=None, dt=None, base=None):
    """a turned box, half sizes w, d at z0 (wt, dt at z1: battered / hipped), open at the bottom"""
    lo = [turn(x, y, a, u, v) + (z0,) for u, v in ((-w, -d), (w, -d), (w, d), (-w, d))]
    wt, dt = w if wt is None else wt, d if dt is None else dt
    hi = [turn(x, y, a, u, v) + (z1,) for u, v in ((-wt, -dt), (wt, -dt), (wt, dt), (-wt, dt))]
    loft(k, [lo, hi], wall, cap=top, base=base)


def prism_at(k, x, y, z, a, length, profile, rect, end=None):
    """a side profile [(across, up)...] (CCW) extruded `length` along the local x axis of a frame at (x, y, z)
    turned by a: gable / sawtooth roofs, tents, ramps, hulls"""
    path = [turn(x, y, a, -length / 2, 0) + (z,), turn(x, y, a, length / 2, 0) + (z,)]
    sweep(k, path, profile, rect, caps=end or (rect[0] if isinstance(rect, list) else rect))


def fin(k, cx, cy, ang, prof, depth, thick, rect):
    """a vertical fin / buttress standing out from a round shaft along bearing ang: prof [(r, z)...] the shaft's
    radius by height (its inner edge), depth how far it stands out"""
    ca, sa = math.cos(ang), math.sin(ang)
    tx, ty = -sa * thick / 2, ca * thick / 2
    rings = []
    for r, z in prof:
        i_, o_ = r - 0.01, r + depth
        rings.append([(cx + ca * i_ - tx, cy + sa * i_ - ty, z), (cx + ca * o_ - tx, cy + sa * o_ - ty, z),
                      (cx + ca * o_ + tx, cy + sa * o_ + ty, z), (cx + ca * i_ + tx, cy + sa * i_ + ty, z)])
    loft(k, rings, rect, cap=rect)


def legs(k, x, y, z0, z1, spread_lo, spread_hi, n, r, rect, rot=0.0, braces=True):
    """n splayed legs from a circle of spread_lo at z0 to spread_hi at z1, with a brace ring half way"""
    for i in range(n):
        a = rot + TAU * i / n
        p0 = (x + spread_lo * math.cos(a), y + spread_lo * math.sin(a), z0)
        p1 = (x + spread_hi * math.cos(a), y + spread_hi * math.sin(a), z1)
        k.tube(p0, p1, r, rect, sides=5)
        if braces:
            b = rot + TAU * (i + 1) / n
            zm, sm = (z0 + z1) / 2, (spread_lo + spread_hi) / 2
            k.tube((x + sm * math.cos(a), y + sm * math.sin(a), zm), (x + sm * math.cos(b), y + sm * math.sin(b), zm),
                   r * 0.6, rect, sides=4)


def curve_tube(k, p0, p1, bulge, r0, r1, rect, n=6, sides=6):
    """a tube from p0 to p1 bowed up by `bulge` in its middle, tapering r0 -> r1 (arches, buttresses, sky-tubes)"""
    pts = [tuple(a + (b - a) * t for a, b in zip(p0, p1)) for t in (i / n for i in range(n + 1))]
    pts = [(p[0], p[1], p[2] + bulge * 4 * (i / n) * (1 - i / n)) for i, p in enumerate(pts)]
    for i in range(n):
        k.tube(pts[i], pts[i + 1], r0 + (r1 - r0) * i / n, rect, sides=sides, r1=r0 + (r1 - r0) * (i + 1) / n)


def dome(k, x, y, z0, r, h, rects, sides=16, sy=1.0, n=4, cap_r=0.0):
    """an elliptic dome (rects per band, bottom up)"""
    prof = [(r * math.cos(math.pi / 2 * i / n), z0 + h * math.sin(math.pi / 2 * i / n)) for i in range(n + 1)]
    if cap_r:
        prof[-1] = (cap_r, prof[-1][1])
    k.lathe(prof, rects if isinstance(rects, list) else [rects] * n, sides=sides, cx=x, cy=y, sy=sy)


def pad(k, x, y, z, r, rim, top, sides=16, under=0.15):
    """a round landing pad: a thin rimmed deck, open beneath (stands on legs / a stalk / a roof)"""
    k.lathe([(r * 0.8, z - under), (r, z - 0.02), (r, z)], [rim, rim], sides=sides, cx=x, cy=y, cap=top)


# ---------------------------------------------------------------------------------------------------- city cells
class Lots:
    """building lots in a city cell (or a landmark site): circles that must not overlap"""

    def __init__(self, rng, lim=1.0):
        self.rng, self.lim, self.taken = rng, lim, []

    def free(self, x, y, r):
        return all(math.hypot(x - a, y - b) > r + c for a, b, c in self.taken)

    def take(self, x, y, r):
        self.taken.append((x, y, r))
        return x, y

    def spot(self, r, tries=30, lim=None):
        lim = self.lim if lim is None else lim
        for _ in range(tries):
            x, y = self.rng.uniform(-lim, lim), self.rng.uniform(-lim, lim)
            if self.free(x, y, r):
                return self.take(x, y, r)
        return None

    def along(self, path, r, off, tries=12):
        """a lot beside a street: (x, y, heading) at `off` + r to either side"""
        L = path_len(path)
        for _ in range(tries):
            (px, py, _z), h = path_at(path, self.rng.uniform(0.05, 0.95) * L)
            side = self.rng.choice((-1, 1)) * (off + r)
            x, y = px - math.sin(h) * side, py + math.cos(h) * side
            if max(abs(x), abs(y)) <= self.lim + 0.15 and self.free(x, y, r):
                self.take(x, y, r)
                return x, y, h
        return None

    def block_path(self, path, w):
        """reserve a street's corridor"""
        L = path_len(path)
        for i in range(int(L / (w * 0.8)) + 1):
            (x, y, _z), _h = path_at(path, i * w * 0.8)
            self.taken.append((x, y, w / 2))


EDGES = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))


def streets(rng, z, wiggle=0.35, n_min=2, curvy=True):
    """street paths in a 2-unit city cell: from the cell centre (jittered) to 2-4 of the edge midpoints, so streets
    run on into the neighbouring cells; curvy bends them through a jittered control point"""
    hub = (rng.uniform(-wiggle, wiggle), rng.uniform(-wiggle, wiggle))
    picks = [e for e in EDGES if rng.random() < 0.6]
    while len(picks) < n_min:
        e = rng.choice([e for e in EDGES if e not in picks])
        picks.append(e)
    out = []
    for ex, ey in picks:
        ctrl = ((hub[0] + ex) / 2 + rng.uniform(-wiggle, wiggle) * (ey != 0),
                (hub[1] + ey) / 2 + rng.uniform(-wiggle, wiggle) * (ex != 0))
        pts = bezier(hub, ctrl, (ex * 1.02, ey * 1.02), 6) if curvy else [hub, (ex * 1.02, ey * 1.02)]
        out.append([(p[0], p[1], z) for p in pts])
    return out, hub


# ==================================================================================================== ETTI IV
# Mondder (Legends; the "Iron Eclipse" comic stills: Mondder streets by night, the spaceport, the Stark Compound, the
# Imperial Embassy): colossal drum towers built of stacked cylinders with ring ledges and teal glass-grid bands, flared
# buttressed feet and needle spires; elevated curving viaducts sweeping between them; streamlined terraces of stacked
# rounded slabs (the Stark Compound); neon at street level.

def etti_drum(k, x, y, z0, h, r, rng, needle=True, sides=16, lite=False):
    """a Mondder drum tower: a flared buttressed foot, stacked drums each set back with a ledge ring, alternating
    ceramic window bands and teal glass grid, a needle or a bulb crown. lite (city cells): painted windows instead of
    recessed bands, no buttresses"""
    foot = max(0.0, -z0) + h * 0.12
    if lite:
        k.lathe([(r * 1.35, z0), (r, z0 + foot)], E_CERAMIC, sides=sides, cx=x, cy=y)
    else:
        k.lathe([(r * 1.45, z0), (r * 1.45, 0.0), (r * 1.2, h * 0.06), (r, z0 + foot)], [E_CERAMIC] * 3, sides=sides,
                cx=x, cy=y)
    ang0 = rng.uniform(0, TAU)
    for a in range(4 if not lite else 0):                                              # foot buttresses
        fin(k, x, y, ang0 + a * TAU / 4, [(r * 1.4, z0), (r, z0 + foot + h * 0.2)], r * 0.25, r * 0.18, E_STEEL)
    z, rr = z0 + foot, r
    stages = rng.choice((2, 3, 3, 4))
    share = [1.0, 0.7, 0.5, 0.35][:stages]
    fh = 0.11 if r < 0.2 else 0.3                                                      # storey height
    for s, f in enumerate(share):
        sh = h * 0.88 * 0.8 * f / sum(share)                                         # h: the height above ground
        mat = E_GLASS_LIT if (s + stages) % 2 else E_CERAMIC_WIN
        if lite:
            k.lathe([(rr, z), (rr, z + sh)], mat, sides=sides, cx=x, cy=y)
        else:
            banded(k, lambda zz, g, rr=rr: ring(x, y, zz, rr + g, sides), z, z + sh, max(1, round(sh / fh)), E_CERAMIC,
                   mat, inset=rr * 0.06)
        z += sh
        ledge = [(rr, z), (rr * 1.18, z + 0.01), (rr * 1.18, z + rr * 0.08), (rr * 0.8, z + rr * 0.1)]
        k.lathe(ledge[1:] if lite else ledge, [E_STEEL, E_ROOF] if lite else [E_STEEL, E_STEEL, E_ROOF], sides=sides,
                cx=x, cy=y)                                                            # the ledge ring
        z += rr * 0.1
        rr *= rng.uniform(0.68, 0.8)
    if needle:
        k.lathe([(rr * 0.6, z), (rr * 0.25, z + h * 0.2), (0.0, z + h * 0.42)], [E_STEEL, E_GOLD], sides=6 if lite else 8,
                cx=x, cy=y)
    else:
        k.lathe([(rr, z), (rr * 1.3, z + rr * 0.5), (rr * 0.9, z + rr * 1.1), (0.0, z + rr * 1.3)],
                [E_GLASS_LIT, E_DOME, E_DOME], sides=sides, cx=x, cy=y)
    return z


def etti_terrace(k, x, y, z0, w, d, a, levels, rng, wall=E_CERAMIC_WIN):
    """Stark Compound streamline: stacked rounded slabs, each shifted and shrunk, a thin overhanging roof lip"""
    z = z0
    for lv in range(levels):
        hh = (0.09 if w < 0.5 else 0.45) * rng.uniform(0.8, 1.2) + (0.3 if lv == 0 else 0.0) * (z0 < 0)
        rc = min(w, d) * 0.95
        loft(k, [rrect(x, y, z, w, d, rc, a), rrect(x, y, z + hh, w, d, rc, a)], wall)
        loft(k, [rrect(x, y, z + hh, w * 1.06, d * 1.1, rc, a), rrect(x, y, z + hh + hh * 0.12, w * 1.06, d * 1.1, rc, a)],
             E_STEEL, cap=E_ROOF)
        z += hh * 1.12
        x, y = turn(x, y, a, rng.uniform(-0.25, 0.25) * w, rng.uniform(-0.2, 0.2) * d)
        w, d = w * rng.uniform(0.62, 0.82), d * rng.uniform(0.75, 0.92)
    return z


def etti_viaduct(k, path, w, rect=E_STEEL, top=E_ROOF, pylons=4, glow=True):
    """an elevated curving roadway on tapering pylons, its edges lined with light"""
    sweep(k, path, [(-w / 2, -0.04), (w / 2, -0.04), (w / 2, 0.02), (-w / 2, 0.02)], [rect, rect, top, rect], caps=rect)
    if glow:
        for sgn in (-1, 1):
            sweep(k, path, [(sgn * w / 2 - 0.006, 0.02), (sgn * w / 2 + 0.006, 0.02), (sgn * w / 2 + 0.006, 0.035),
                            (sgn * w / 2 - 0.006, 0.035)], E_GLOW)
    L = path_len(path)
    for i in range(pylons):
        (px, py, pz), _h = path_at(path, L * (i + 0.5) / pylons)
        k.lathe([(w * 0.35, CELL_Z if pz < 3 else pz - 3), (w * 0.22, pz - 0.15), (w * 0.4, pz - 0.04)], [rect, rect],
                sides=8, cx=px, cy=py)


def etti_slab(k, x, y, z0, h, w, d, a, rng):
    """an Imperial-Embassy style slab tower: a rounded shaft, a wider cantilevered glass storey set off-centre on top,
    a mast"""
    rc = min(w, d) * 0.5
    loft(k, [rrect(x, y, z0, w, d, rc, a, seg=1), rrect(x, y, h, w, d, rc, a, seg=1)], E_CERAMIC_WIN)
    cx, cy = turn(x, y, a, w * rng.uniform(-0.4, 0.4), 0)
    loft(k, [rrect(cx, cy, h, w * 1.25, d * 1.3, rc, a, seg=1), rrect(cx, cy, h + 0.1, w * 1.25, d * 1.3, rc, a, seg=1)],
         E_GLASS_LIT, cap=E_ROOF, base=E_STEEL)
    k.lathe([(0.012, h + 0.1), (0.0, h + 0.1 + h * 0.3)], E_STEEL, sides=3, cx=x, cy=y)


def etti_city(k, band, rng):
    # Mondder blocks: the cell's streets (flyovers ramping down to the cell edges downtown, avenues outside) lined
    # with continuous streamline frontage blocks; drum towers, embassy slabs and joined twin drums beside them
    # (taller and more downtown); glass domes in the gaps; street neon. band 1 outskirts .. 4 downtown.
    # Budget ~1000-1500 tris (vanilla city meshes ~100 KB): painted windows, open-bottomed sweeps
    lots = Lots(rng, 0.95)
    elev = 0.25 + 0.12 * band
    paths, hub = streets(rng, 0.0, wiggle=0.3)
    for p in paths:
        p = p[::2] + ([p[-1]] if len(p) % 2 == 0 else [])
        if band >= 3:                                                              # flyovers, down at the edges
            etti_viaduct(k, [(x, y, 0.02 + elev * (1 - i / (len(p) - 1))) for i, (x, y, _z) in enumerate(p)], 0.12,
                         pylons=1, glow=False)
        else:
            sweep(k, p, rect_section(0.12, 0.32, CELL_Z), [E_STEEL, E_ROOF, E_STEEL], open_sec=True)
        lots.block_path(p, 0.16)
    for p in paths:                                                                # frontage blocks
        L = path_len(p)
        for side in (-1, 1):
            s0 = rng.uniform(0.05, 0.25) * L
            while s0 < L * 0.9:
                s1 = min(L * 0.95, s0 + rng.uniform(0.25, 0.5))
                dpt = rng.uniform(0.11, 0.17)
                seg = offset_path(sub_path(p, s0, s1, 2), side * (0.1 + dpt / 2))
                hh = rng.uniform(0.06, 0.1) + 0.04 * band
                sweep(k, seg, rect_section(dpt, hh - CELL_Z, CELL_Z), [E_CERAMIC_WIN, E_ROOF, E_CERAMIC_WIN],
                      caps=E_CERAMIC_WIN, open_sec=True)
                for q in seg:
                    lots.taken.append((q[0], q[1], dpt * 0.6))
                s0 = s1 + rng.uniform(0.06, 0.15)
    kinds = ["drum", "drum", "slab", "twin"] if band >= 2 else ["drum", "slab"]
    for _ in range(band + rng.randint(0, 1)):                                      # towers
        kind = rng.choice(kinds)
        r = rng.uniform(0.07, 0.1) + 0.012 * band
        p_ = lots.spot(r * (2.6 if kind == "twin" else 1.4))
        if not p_:
            continue
        h = rng.uniform(0.5, 0.8) + 0.32 * band + (rng.uniform(0.3, 0.9) if band == 4 else 0.0)
        if kind == "drum":
            etti_drum(k, p_[0], p_[1], CELL_Z, h, r, rng, needle=rng.random() < 0.5, sides=8, lite=True)
        elif kind == "slab":
            etti_slab(k, p_[0], p_[1], CELL_Z, h * 0.7, r * 1.3, r * 0.7, rng.uniform(0, math.pi), rng)
        else:
            a = rng.uniform(0, TAU)
            q = [turn(p_[0], p_[1], a, sgn * r * 1.3, 0) for sgn in (-1, 1)]
            hs = [h, h * rng.uniform(0.6, 0.85)]
            for (qx, qy), hh in zip(q, hs):
                etti_drum(k, qx, qy, CELL_Z, hh, r * 0.8, rng, needle=False, sides=8, lite=True)
            z = hs[1] * 0.45
            sweep(k, [q[0] + (z,), q[1] + (z,)], rect_section(0.04, 0.035), [E_GLASS_LIT, E_ROOF, E_GLASS_LIT, E_STEEL])
    for _ in range(3 - band // 2):                                                 # glass domes
        r = rng.uniform(0.06, 0.1)
        p_ = lots.spot(r)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.04)], E_CERAMIC_WIN, sides=8, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.04, r, r * 0.7, E_DOME, sides=8, n=2)
    for p in paths[:2]:                                                            # street neon
        (nx, ny, _z), h = path_at(p, path_len(p) * rng.uniform(0.3, 0.7))
        tbox(k, *turn(nx, ny, h, 0, 0.075), 0.0, 0.16, 0.035, 0.006, h, E_NEON, E_NEON)


def etti_arco_block(k, path, steps, depth, sh, base):
    """an arcology terrace swept along a path: a stepped section, high at the back (left of the path), stepping down
    to the right; window walls on the risers, the treads roofed"""
    tw = depth / steps
    sec = [(-depth / 2, base), (depth / 2, base)]
    for s in range(steps):
        u = depth / 2 - s * tw
        sec += [(u, sh * (s + 1)), (u - tw, sh * (s + 1))] if s < steps - 1 else [(u, sh * (s + 1))]
    sec.append((-depth / 2, sh * steps))
    sec = [(-u, z) for u, z in sec]                                                 # high side to the left
    rects = [E_STEEL] + [E_COBALT_WIN if e % 2 else E_ROOF for e in range(1, len(sec) - 1)] + [E_COBALT_WIN]
    sweep(k, path, sec, rects, caps=E_COBALT)


def arco_city(k, band, rng):
    # the Arcoplex's expansion (Cybot Galactica's city-headquarters, "expanding the city by burning the surrounding
    # forests"; look: a design choice): stepped cobalt arcology terraces curving along both sides of the streets,
    # droid-works sheds with sawtooth roofs between them, cranes on the expansion edge. band 1 edge .. 4 core
    lots = Lots(rng, 0.95)
    paths, _hub = streets(rng, 0.0, wiggle=0.25, curvy=True)
    for p in paths:
        sweep(k, p[::2] + [p[-1]], rect_section(0.12, 0.31, CELL_Z), [E_STEEL, E_ROOF, E_STEEL], open_sec=True)
        lots.block_path(p, 0.14)
    for p in paths:                                                                # arcology terraces
        L = path_len(p)
        for side in (-1, 1):
            if rng.random() > 0.35 + 0.15 * band:
                continue
            s0, s1 = rng.uniform(0.0, 0.25) * L, rng.uniform(0.65, 1.0) * L
            depth = 0.16 + 0.035 * band
            pts = offset_path(sub_path(p, s0, s1, 5), side * (0.1 + depth / 2))
            if side > 0:                                                           # high side away from the street
                pts = pts[::-1]
            etti_arco_block(k, pts, 1 + band, depth, 0.1, CELL_Z)
            for x, y, _z in pts:
                lots.taken.append((x, y, depth * 0.7))
    for _ in range(4 - band // 2):                                                 # droid works
        w = rng.uniform(0.12, 0.17)
        p_ = lots.spot(w * 1.2)
        if p_:
            a = rng.uniform(0, math.pi)
            tbox(k, p_[0], p_[1], CELL_Z, 0.08, w, w * 0.6, a, E_STEEL, E_ROOF)
            for i in range(3):
                prism_at(k, *turn(p_[0], p_[1], a, 0, (i - 1) * w * 0.4), 0.08, a, w * 2,
                         [(-w * 0.2, 0), (w * 0.2, 0), (-w * 0.2, 0.07)], [E_ROOF, E_GLASS_LIT, E_ROOF])
    if band <= 2:                                                                  # a crane on the expansion edge
        p_ = lots.spot(0.05)
        if p_:
            k.tube((p_[0], p_[1], CELL_Z), (p_[0], p_[1], 0.9), 0.02, E_HAZARD, sides=4)
            a = rng.uniform(0, TAU)
            k.tube((p_[0] - 0.12 * math.cos(a), p_[1] - 0.12 * math.sin(a), 0.88),
                   (p_[0] + 0.45 * math.cos(a), p_[1] + 0.45 * math.sin(a), 0.88), 0.015, E_HAZARD, sides=4)


def etti_spaceport(k):
    # the Mondder Spaceport (Legends: Etti IV's primary spaceport, its holding bays (Docking Bays 41 and 45) and the
    # Dream Emporium inside it; the "Iron Eclipse" still from above: round pads sunk among pale towers): a long curved
    # streamline terminal along the north, a control drum with a flared glass cab at its west end, pads on stalks at
    # different heights fanned out south of it and joined to it by walkways, the two holding bays sunk as open rings,
    # the Dream Emporium's neon dome in the east, Imperial Pad 693 by the gate. ~11 across
    import random
    rng = random.Random("etti_spaceport")
    term = bezier((-4.8, 1.4), (0.0, 3.6), (4.6, 1.8), 10)
    sweep(k, [(x, y, 0.0) for x, y in term], [(-0.8, -SKIRT), (0.8, -SKIRT), (0.8, 0.55), (0.55, 0.8), (-0.6, 0.8),
                                              (-0.8, 0.6)], [E_CERAMIC, E_CERAMIC_WIN, E_STEEL, E_ROOF, E_STEEL, E_CERAMIC_WIN],
          caps=E_CERAMIC)
    sweep(k, [(x, y, 0.8) for x, y in term[1:-1]], trap_section(1.0, 0.7, 0.45), [E_GLASS_LIT, E_GLASS, E_ROOF, E_GLASS],
          caps=E_GLASS)                                                                         # the glazed upper deck
    etti_drum(k, -4.9, 1.3, -SKIRT, 7.0, 0.55, rng, needle=False)                               # control tower
    pads = [(-3.2, -0.9, 1.6, 0.9), (-1.2, -2.4, 2.4, 1.0), (1.0, -2.2, 1.2, 0.85), (2.9, -0.6, 2.0, 0.95),
            (0.0, -0.2, 0.7, 0.7), (-2.0, 0.5, 2.9, 0.6)]
    for x, y, z, r in pads:
        k.lathe([(r * 0.28, -SKIRT), (r * 0.18, z * 0.6), (r * 0.35, z - 0.2)], [E_STEEL, E_STEEL], sides=10, cx=x, cy=y)
        pad(k, x, y, z, r, E_STEEL, E_PAD)
        tx, ty = min(term, key=lambda p: math.hypot(p[0] - x, p[1] - y))
        etti_viaduct(k, [(x, y, z - 0.02), ((x + tx) / 2, (y + ty) / 2, (z + 0.8) / 2), (tx, ty, 0.75)], 0.22, pylons=1)
    for x, y, r in ((-4.4, -3.4, 1.0), (-2.3, -4.6, 0.85)):                                    # holding bays 41, 45
        k.lathe([(r + 0.25, -SKIRT), (r + 0.25, 0.9), (r + 0.05, 0.95), (r, 0.3), (0.0, 0.3)],
                [E_CERAMIC_WIN, E_STEEL, E_CERAMIC, E_PAD], sides=20, cx=x, cy=y)
    k.lathe([(1.5, -SKIRT), (1.5, 0.4)], E_CERAMIC_WIN, sides=18, cx=3.6, cy=-3.2)              # Dream Emporium
    dome(k, 3.6, -3.2, 0.4, 1.5, 1.3, [E_NEON, E_DOME, E_DOME, E_GLOW], sides=18)
    for a in range(5):
        fin(k, 3.6, -3.2, a * TAU / 5 + 0.3, [(1.5, -0.2), (1.35, 0.9), (0.75, 1.55)], 0.12, 0.1, E_GOLD)
    etti_terrace(k, 5.0, 0.2, -SKIRT, 0.9, 0.55, 1.3, 3, rng)                                   # the gate offices
    k.lathe([(0.12, -SKIRT), (0.08, 2.4), (0.0, 2.9)], [E_STEEL, E_HAZARD], sides=6, cx=5.6, cy=-1.2)


def etti_arcoplex(k):
    # the Arcoplex (canon: Cybot Galactica's city-headquarters on Etti IV; its look is a design choice from its name):
    # a vast crescent of stepped cobalt arcology terraces (gold on every lip, pads on its roof) wrapping a yard open
    # to the south-east, a second lower crescent inside it to the west, the headquarters drum rising off-centre in the
    # crescent's north-east horn, droid-assembly sheds with sawtooth roofs in the yard. ~13 across
    import random
    rng = random.Random("etti_arcoplex")
    outer = [(x, y, 0.0) for x, y in bezier((-5.6, -3.6), (-4.6, 4.6), (0.8, 3.2), 9)[:-1]
             + bezier((0.8, 3.2), (5.2, 2.0), (5.2, -2.6), 8)]
    etti_arco_block(k, outer, 5, 2.0, 0.75, -SKIRT)
    inner = [(x, y, 0.0) for x, y in bezier((-2.4, -2.6), (-2.6, 1.0), (0.2, 0.9), 8)]
    etti_arco_block(k, inner, 3, 1.3, 0.6, -SKIRT)
    for i in (3, 8, 13):                                                                       # roof pads
        (x, y, _z), _h = path_at(outer, path_len(outer) * i / 17)
        pad(k, x, y, 3.8, 0.55, E_STEEL, E_PAD)
        k.lathe([(0.15, 3.0), (0.15, 3.7)], E_STEEL, sides=6, cx=x, cy=y)
    etti_drum(k, 2.6, 0.6, -SKIRT, 10.5, 1.15, rng, needle=True)                               # HQ drum
    for i in range(3):                                                                         # sky-bridges to it
        (x, y, _z), _h = path_at(outer, path_len(outer) * (0.62 + 0.12 * i))
        etti_viaduct(k, [(x, y, 3.3), ((x + 2.6) / 2, (y + 0.6) / 2, 3.6 + 0.8 * i), (2.6, 0.6, 3.6 + 1.6 * i)], 0.25,
                     pylons=0)
    for x, y, a in ((1.1, -2.4, 0.4), (-0.9, -3.7, 0.1), (3.0, -2.6, 1.2)):                     # droid works
        tbox(k, x, y, -SKIRT, 0.55, 0.9, 0.55, a, E_STEEL, E_ROOF)
        for j in range(4):
            prism_at(k, *turn(x, y, a, 0, -0.41 + 0.27 * j), 0.55, a, 1.8,
                     [(-0.13, 0), (0.13, 0), (-0.13, 0.32)], [E_ROOF, E_GLASS_LIT, E_ROOF])
    for p0, p1 in (((-3.0, -3.4), (0.9, -4.6)), ((0.9, -4.6), (3.6, -2.6))):                     # yard road
        sweep(k, [p0 + (0.02,), p1 + (0.02,)], rect_section(0.5, 0.1, -0.08), E_STEEL)


def etti_dancedome(k):
    # the Free-Flight Dance Dome (Legends: a bistro in Mondder with a zero-gravity dance floor; The Essential Guide's
    # drawing): a broad low dome ringed by low banded halls, two great arches springing over it crosswise, two tall
    # bullet towers with slit windows standing either side, a garden terrace before it. ~9 across
    import random
    rng = random.Random("etti_dancedome")
    sweep(k, arc_path(0.0, 0.0, 0.0, 3.0, 0.0, TAU, 28), [(-0.45, -SKIRT), (0.45, -SKIRT), (0.45, 0.4), (0.3, 0.6),
                                                          (-0.45, 0.6)], [E_CERAMIC, E_CERAMIC_WIN, E_STEEL, E_ROOF, E_CERAMIC_WIN],
          closed_path=True)                                                                    # the ring of halls
    k.lathe([(2.6, 0.5), (2.6, 0.75)], E_GLOW, sides=28)
    dome(k, 0.0, 0.0, 0.75, 2.6, 1.8, [E_DOME, E_DOME, E_GLASS_LIT, E_DOME], sides=28, sy=0.85, n=4)
    for a in (0.35, 0.35 + math.pi / 2):                                                        # the crossing arches
        ca, sa = math.cos(a), math.sin(a)
        pts = [(3.6 * math.cos(t) * ca, 3.6 * math.cos(t) * sa, 3.4 * math.sin(t) - 0.4)
               for t in (math.pi * i / 16 for i in range(17))]
        for p0, p1 in zip(pts, pts[1:]):
            k.tube(p0, p1, 0.17, E_CERAMIC, sides=6)
        for sgn in (-1, 1):                                                                     # their feet
            k.lathe([(0.45, -SKIRT), (0.3, 0.2), (0.18, 0.6)], [E_STEEL, E_STEEL], sides=8, cx=3.6 * sgn * ca, cy=3.6 * sgn * sa)
    for x, y in ((-4.3, 0.6), (4.2, -0.4)):                                                     # bullet towers
        k.lathe([(0.6, -SKIRT), (0.62, 1.0), (0.58, 3.5), (0.45, 5.0), (0.2, 5.9), (0.0, 6.1)],
                [E_CERAMIC, E_CERAMIC, E_CERAMIC, E_CERAMIC, E_STEEL], sides=14, cx=x, cy=y)
        for i in range(5):
            fin(k, x, y, i * TAU / 5, [(0.6, 0.6), (0.58, 4.4)], 0.02, 0.07, E_GLASS_LIT)
    garden = lobed(0.4, -4.0, 0.0, 1.5, lobes=2, amp=0.25, n=20, sy=0.55)
    loft(k, [at_z(garden, -SKIRT), at_z(garden, 0.12)], E_CERAMIC, cap=E_GARDEN)
    for i in range(6):
        x, y = 0.4 + 1.2 * math.cos(i), -4.0 + 0.5 * math.sin(i * 1.7)
        k.lathe([(0.03, 0.12), (0.03, 0.5), (0.09, 0.56), (0.0, 0.62)], [E_STEEL, E_GLOW, E_GLOW], sides=5, cx=x, cy=y)
    del rng


# ---------------------------------------------------------------------------------------------------- shared shapes
def vault(k, x, y, z0, a, length, w, h, rects, n=6, taper=1.0, end=None, segs=8):
    """a barrel / shell vault along the local x axis of a frame at (x, y) turned by a: half-ellipse arches (half
    width w, rise h) from -length/2 to +length/2, shrinking to `taper` of their size at the far end"""
    rings = []
    for i in range(n + 1):
        u = -length / 2 + length * i / n
        f = 1 + (taper - 1) * i / n
        rings.append([turn(x, y, a, u, w * f * math.cos(math.pi * j / segs)) + (z0 + h * f * math.sin(math.pi * j / segs),)
                      for j in range(segs + 1)])
    loft(k, rings, rects, closed=False, base=end, cap=end)


def gunship(k, x, y, z, head, L, hull=B_PLATE, glass=B_PLATE_WIN, trim=B_RUST):
    """a Republic gunship at rest: the long body, the cockpit nose, the swept wings with their pods, the tail fin"""
    at = lambda u, v, zz: turn(x, y, head, u, v) + (z + zz,)
    k.tube(at(-L * 0.5, 0, L * 0.12), at(L * 0.3, 0, L * 0.14), L * 0.11, hull, sides=8, r1=L * 0.13)
    k.tube(at(L * 0.3, 0, L * 0.14), at(L * 0.5, 0, L * 0.12), L * 0.13, glass, sides=8, r1=L * 0.05)
    k.tube(at(L * 0.05, -L * 0.45, L * 0.2), at(L * 0.05, L * 0.45, L * 0.2), L * 0.04, trim, sides=6)
    for s_ in (-1, 1):
        k.tube(at(-L * 0.05, s_ * L * 0.42, L * 0.2), at(L * 0.2, s_ * L * 0.42, L * 0.2), L * 0.05, hull, sides=6)
    k.tube(at(-L * 0.5, 0, L * 0.2), at(-L * 0.6, 0, L * 0.42), L * 0.03, trim, sides=5, r1=L * 0.01)


def shuttle(k, x, y, z, head, L, hull, glass):
    """a small courier / freighter at rest: a tapering body, a cockpit cone, two stub wings"""
    at = lambda u, v, zz: turn(x, y, head, u, v) + (z + zz,)
    k.tube(at(-L * 0.5, 0, L * 0.1), at(L * 0.2, 0, L * 0.12), L * 0.1, hull, sides=8, r1=L * 0.12)
    k.tube(at(L * 0.2, 0, L * 0.12), at(L * 0.5, 0, L * 0.1), L * 0.12, glass, sides=8, r1=L * 0.02)
    tbox(k, *at(-L * 0.1, 0, 0)[:2], z + L * 0.08, z + L * 0.11, L * 0.15, L * 0.38, head, hull, hull)


def rock(k, x, y, z0, z1, r, rng, mats, lobes=3, tiers=3, sy=1.0):
    """a lobed knoll / reef / mound: rings shrinking upward, never a plain disc"""
    ph = rng.uniform(0, TAU)
    rings = [lobed(x, y, z0, r, lobes, 0.22, 20, ph, sy)]
    for t in range(1, tiers + 1):
        f = t / tiers
        rings.append(lobed(x, y, z0 + (z1 - z0) * f if z0 >= 0 else z1 * f, r * (1 - 0.55 * f ** 1.4), lobes,
                           0.22 + 0.1 * f, 20, ph + 0.4 * f, sy))
    mats = mats if isinstance(mats, list) else [mats] * tiers
    loft(k, rings, (mats + [mats[-1]] * tiers)[:tiers], cap=mats[-1])


# ==================================================================================================== LIANNA
# Lianna (Legends: Sienar's world, the megalopolis of Lianna City; "Mission to Lianna"'s cover, adapted from Ralph
# McQuarrie's Cloud City matte painting: white fluted towers flaring into wide feet, a dome-topped silo banded in blue,
# needle obelisks, broad paved plazas; Santhe/Sienar's headquarters atrium of glass and gardens; the Lola Curich
# starport map's hexagonal blocks). Atlas hod_lianna (B_ layout): B_HULL white, B_RUST Sienar blue.

def lia_flute(k, x, y, z0, h, r, rng, ribs=8, crown=True, lite=False):
    """a McQuarrie tower: a fluted shaft flaring into a wide foot, slit windows high up, a cornice and a low cap;
    it stands on max(z0, 0) (a deck above ground), h is its top"""
    rot = rng.uniform(0, TAU)
    g = max(z0, 0.0)
    zs = [(1.9, z0), (1.9, g + 0.001), (1.3, g + (h - g) * 0.12), (1.0, g + (h - g) * 0.32), (0.93, g + (h - g) * 0.82),
          (0.9, h)]
    rings = [star(x, y, z, r * f, 0.12, ribs, rot) for f, z in zs]
    loft(k, rings, [B_HULL, B_HULL, B_HULL, B_HULL if lite else B_PLATE_WIN, B_PLATE_WIN], cap=None if crown else B_ROOF)
    if crown:
        k.lathe([(r * 0.9, h), (r * 1.08, h + r * 0.15), (r * 1.08, h + r * 0.25), (r * 0.7, h + r * 0.35),
                 (0.0, h + r * 0.55)], [B_HULL, B_RUST, B_HULL, B_ROOF], sides=ribs if lite else ribs * 2, cx=x, cy=y)


def lia_silo(k, x, y, z0, h, r, bands=6, finial=True, sides=16):
    """the cover's banded silo: a white drum, its upper half ringed with blue bands, a tall rounded dome; it stands
    on max(z0, 0), h is the top of its drum"""
    g = max(z0, 0.0)
    prof, mats = [(r, z0), (r, g + (h - g) * 0.45)], [B_HULL]
    bh = (h - g) * 0.55 / (2 * bands)
    for b in range(2 * bands):
        prof.append((r * (1.0 if b % 2 else 1.015), g + (h - g) * 0.45 + bh * (b + 1)))
        mats.append(B_RUST if b % 2 == 0 else B_HULL)
    prof += [(r * 0.92, h + r * 0.45), (r * 0.6, h + r * 0.85), (0.0, h + r * 1.0)]
    mats += [B_HULL, B_HULL, B_HULL]
    k.lathe(prof, mats, sides=sides, cx=x, cy=y)
    if finial:
        k.lathe([(r * 0.06, h + r * 0.98), (r * 0.03, h + r * 1.5), (r * 0.12, h + r * 1.55), (0.0, h + r * 1.65)],
                [B_HULL, B_HULL, B_HULL], sides=5, cx=x, cy=y)


def lia_needle(k, x, y, z0, h, r):
    """a needle obelisk: a slim fluted cone on a ringed foot (standing on max(z0, 0), h its tip)"""
    g = max(z0, 0.0)
    loft(k, [star(x, y, z0, r * 1.4, 0.15, 4), star(x, y, g + 0.001, r * 1.4, 0.15, 4),
             star(x, y, g + (h - g) * 0.06, r, 0.15, 4),
             star(x, y, h, r * 0.05, 0.15, 4)], [B_HULL, B_RUST, B_HULL], cap=B_HULL)


def lia_podium(k, x, y, z0, h, w, d, a, roof=B_DUST):
    """a low stadium-shaped hall (nothing square on Lianna): window band, a pale roof"""
    loft(k, [rrect(x, y, z0, w, d, d * 0.98, a, 3), rrect(x, y, h, w, d, d * 0.98, a, 3)], B_CONC_WIN, cap=roof)


def lia_city(k, band, rng):
    # Lianna City's megalopolis (the user, 2026-10-16: a real megalopolis, nothing square): paved avenues of the
    # cell (wide and straight, the cover's plazas) lined with fluted towers and banded silos, needles at the
    # crossings, stadium-shaped halls between; denser and taller downtown. band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.25, curvy=False)
    for p in paths:
        sweep(k, [p[0], p[-1]], rect_section(0.16 + 0.03 * band, 0.315, CELL_Z), [B_CONC, B_DUST, B_CONC], open_sec=True)
        lots.block_path(p, 0.2 + 0.03 * band)
    if band >= 2:
        lia_needle(k, hub[0], hub[1], CELL_Z, 0.5 + 0.3 * band, 0.025)
        lots.take(hub[0], hub[1], 0.08)
    for _ in range(band + 1 + rng.randint(0, 1)):                                  # flutes and silos
        silo = rng.random() < 0.35
        r = rng.uniform(0.06, 0.09) + 0.01 * band
        p_ = lots.along(rng.choice(paths), r * 1.9, 0.11 + 0.015 * band) or lots.spot(r * 1.9)
        if not p_:
            continue
        h = rng.uniform(0.5, 0.75) + 0.3 * band + (rng.uniform(0.2, 0.7) if band == 4 else 0.0)
        if silo:
            lia_silo(k, p_[0], p_[1], CELL_Z, h * 0.55, r * 1.4, bands=3, finial=False, sides=10)
        else:
            lia_flute(k, p_[0], p_[1], CELL_Z, h, r, rng, ribs=6, lite=True)
    for _ in range(4 - band // 2):                                                 # stadium halls
        w = rng.uniform(0.14, 0.24)
        p_ = lots.along(rng.choice(paths), w, 0.12)
        if p_:
            lia_podium(k, p_[0], p_[1], CELL_Z, rng.uniform(0.06, 0.12), w, w * rng.uniform(0.35, 0.5), p_[2])
    if band <= 2:                                                                  # Lola Curich hex blocks
        for _ in range(2):
            p_ = lots.spot(0.12)
            if p_:
                k.lathe([(0.11, CELL_Z), (0.11, 0.08), (0.09, 0.1)], [B_CONC_WIN, B_ROOF], sides=6, cx=p_[0], cy=p_[1],
                        rot=rng.uniform(0, 1), cap=B_ROOF)


def lia_hq(k):
    # the Santhe/Sienar Technologies Corporate Headquarters in Lianna City (Legends; the Essential Atlas drawing: a
    # glass atrium of tree-lined terraces between towers; the look round it after the "Mission to Lianna" cover):
    # a long glazed atrium vault running north-south, the great fluted tower rising at its north end, the banded
    # silo-dome to its west, needles along a paved forecourt to the south, landing pads on stalks east. ~12 across
    import random
    rng = random.Random("lia_hq")
    court = rrect(0.0, -3.4, 0.0, 2.2, 1.6, 1.5, 0.15, 3)                                      # the forecourt
    loft(k, [at_z(court, -SKIRT), at_z(court, 0.12)], B_CONC, cap=B_DUST)
    loft(k, [rrect(0.4, 0.6, -SKIRT, 1.3, 3.0, 0.6, 0.15, 2), rrect(0.4, 0.6, 1.2, 1.3, 3.0, 0.6, 0.15, 2)], B_CONC_WIN)
    vault(k, 0.4, 0.6, 1.2, 0.15 + math.pi / 2, 6.0, 1.3, 1.5, [B_PLATE_WIN, B_GLOW, B_PLATE_WIN, B_PLATE_WIN, B_GLOW,
                                                            B_PLATE_WIN], n=6, end=B_PLATE_WIN)  # the atrium
    for i in range(7):                                                                         # its ribs
        u = -3.0 + i
        pts = [turn(0.4, 0.6, 0.15 + math.pi / 2, u, 1.36 * math.cos(math.pi * j / 6)) + (1.2 + 1.56 * math.sin(math.pi * j / 6),)
               for j in range(7)]
        for p0, p1 in zip(pts, pts[1:]):
            k.tube(p0, p1, 0.06, B_HULL, sides=4)
    lia_flute(k, 0.9, 4.6, -SKIRT, 13.0, 1.15, rng, ribs=12)                                   # the great tower
    lia_silo(k, -3.4, 1.4, -SKIRT, 5.2, 1.7, bands=7)                                          # the silo-dome
    for x, y, h in ((-1.8, -4.6, 5.0), (1.6, -4.8, 4.2), (-2.4, -2.2, 3.4), (3.0, -2.6, 6.2)):  # needles
        lia_needle(k, x, y, -SKIRT, h, 0.16)
    for x, y, z in ((4.0, 1.8, 2.6), (4.4, -0.6, 1.8)):                                         # pads east
        k.lathe([(0.3, -SKIRT), (0.18, z * 0.7), (0.4, z - 0.12)], [B_HULL, B_HULL], sides=8, cx=x, cy=y)
        pad(k, x, y, z, 0.9, B_HULL, B_PAD)
    lia_podium(k, -3.6, -1.6, -SKIRT, 0.7, 1.1, 0.5, 1.2)
    sweep(k, [(2.8, 4.0, 0.1), (3.9, 2.4, 2.5)], rect_section(0.35, 0.12), B_HULL, caps=B_HULL)   # a ramp to the pad


def lia_academy(k):
    # the Melford Star Academy (Legends: "the First Star Academy", later the Imperial Naval Academy, at Melford on
    # Anai's northern coast; before the war a Republic naval and flight academy, a design choice): a long parade
    # ground running south from the main hall, the hall a vaulted nave flanked at its door by two fluted towers,
    # curved lecture wings reaching south either side of the ground with observatory domes at their ends, a mast,
    # a training courier on its pad. ~13 across
    import random
    rng = random.Random("lia_academy")
    ground = rrect(0.0, -1.4, 0.0, 1.5, 3.6, 1.4, 0.0, 3)
    loft(k, [at_z(ground, -SKIRT), at_z(ground, 0.08)], B_CONC, cap=B_DUST)
    loft(k, [rrect(0.0, 3.6, -SKIRT, 1.6, 1.9, 0.8, 0.0, 2), rrect(0.0, 3.6, 1.6, 1.6, 1.9, 0.8, 0.0, 2)], B_PLATE_WIN)
    vault(k, 0.0, 3.6, 1.6, math.pi / 2, 3.8, 1.6, 1.3, [B_ROOF, B_RUST, B_ROOF, B_ROOF, B_RUST, B_ROOF], end=B_HULL)
    for sx in (-1, 1):
        lia_flute(k, sx * 1.9, 1.8, -SKIRT, 6.5, 0.55, rng, ribs=8)                             # the door towers
        wing = [(sx * (2.4 + 1.2 * math.sin(t)), 1.4 - 5.4 * t / 1.2, 0.0) for t in (i * 0.15 for i in range(9))]
        sweep(k, wing, [(0.45, -SKIRT), (0.45, 1.0), (0.2, 1.25), (-0.45, 1.25), (-0.45, -SKIRT)],
              [B_PLATE_WIN, B_HULL, B_ROOF, B_PLATE_WIN], caps=B_HULL, open_sec=True)          # lecture wings
        ex, ey, _ = wing[-1]
        k.lathe([(0.75, -SKIRT), (0.75, 1.5)], B_PLATE_WIN, sides=14, cx=ex, cy=ey - 0.4)
        dome(k, ex, ey - 0.4, 1.5, 0.78, 0.7, [B_HULL, B_ROOF, B_ROOF, B_HULL], sides=14)       # observatories
    k.lathe([(0.1, 0.0), (0.06, 6.0), (0.0, 6.4)], [B_HULL, B_RUST], sides=5, cx=0.0, cy=-5.4)   # the mast
    tbox(k, 0.35, -5.4, 5.2, 5.9, 0.3, 0.015, 0.0, B_RUST, B_RUST)
    pad(k, 4.4, -3.6, 0.35, 1.2, B_HULL, B_PAD)
    k.lathe([(0.9, -SKIRT), (0.9, 0.2)], B_CONC, sides=12, cx=4.4, cy=-3.6)
    shuttle(k, 4.4, -3.6, 0.35, 0.6, 2.0, B_HULL, B_PLATE_WIN)                                 # the courier


def lia_skycity(k):
    # Sky City (Legends: a city of Lianna; Orman's Sky Palace in "Mission to Lianna" lies in its gardens; the map
    # floats it over the Shaltin Strait, a design choice honouring the cover's McQuarrie Bespin painting): a deck of
    # two unequal lobes on an off-centre tapering stalk, the towers crowded on the east lobe (a great fluted tower, a
    # banded silo, flutes and needles), the palace gardens on the west lobe, pads on outriggers. Deck ~6 up
    import random
    rng = random.Random("lia_skycity")
    z0 = 5.5
    deck = lobed(0.0, 0.0, 0.0, 5.2, lobes=2, amp=0.28, n=28, phase=0.3, sy=0.75)
    rings = [scaled(at_z(deck, z0 - 2.4), 0.15, 0.9, 0.2), scaled(at_z(deck, z0 - 1.2), 0.55, 0.9, 0.2),
             scaled(at_z(deck, z0 - 0.3), 0.95), at_z(deck, z0 + 0.25), scaled(at_z(deck, z0 + 0.6), 0.97)]
    loft(k, rings, [B_PLATE, B_PLATE_WIN, B_CONC_WIN, B_HULL], cap=B_DUST)                      # the deck
    k.lathe([(0.55, -SKIRT), (0.45, 0.0), (0.55, z0 * 0.4), (0.75, z0 - 2.3)], [B_HULL, B_PLATE, B_PLATE], sides=12,
            cx=0.9, cy=0.2)                                                                     # the stalk
    k.lathe([(1.1, 0.0), (1.3, 0.35), (1.0, 0.7)], [B_GLOW, B_HULL], sides=12, cx=0.9, cy=0.2)
    lia_flute(k, 2.6, 0.2, z0 + 0.5, z0 + 7.5, 0.8, rng, ribs=10)
    lia_silo(k, 1.0, 1.6, z0 + 0.5, z0 + 3.4, 0.9, bands=5)
    for x, y, h in ((3.8, -1.4, 3.0), (1.4, -1.3, 2.4), (4.4, 1.2, 2.0)):
        lia_flute(k, x, y, z0 + 0.5, z0 + 0.5 + h, 0.35, rng, ribs=6)
    lia_needle(k, 3.2, 2.0, z0 + 0.5, z0 + 4.3, 0.12)
    for i in range(9):                                                                           # the palace gardens
        gx, gy = -3.6 + 1.6 * math.cos(i * 2.4) * (i / 9), 0.3 + 1.0 * math.sin(i * 2.4) * (i / 9)
        k.lathe([(0.25, z0 + 0.55), (0.25, z0 + 0.7)], B_CONC, sides=8, cx=gx, cy=gy, cap=B_CONC)
    lia_podium(k, -2.4, -1.2, z0 + 0.55, z0 + 1.1, 0.9, 0.42, 0.5)                              # Orman's palace
    for b in (math.radians(200), math.radians(320)):                                             # pads on outriggers
        px, py = 6.4 * math.cos(b), 4.4 * math.sin(b)
        k.tube((0.7 * px, 0.7 * py, z0 + 0.2), (px, py, z0 + 0.2), 0.16, B_PLATE, sides=6)
        k.lathe([(0.3, z0 - 0.1), (1.0, z0 + 0.25)], B_PLATE, sides=14, cx=px, cy=py, cap=B_PAD)


# ==================================================================================================== MON CALA
# Mon Cala (canon: Dac City in Darth Vader (2017): clusters of tall rounded bullet towers rising from the sea, a great
# low ribbed dome, sky-tubes; TCW "Water War": the cities in the deep lit gold; the Exodus-era floating city (Legends
# art): stacked saucers, ring platforms and long piers). Quarren: dark, angular, tentacle-buttressed. Atlas
# hod_moncala (B_ layout): B_PLATE shell, B_CONC sea green, B_RUST coral, B_BRICK the Quarren's slate.

def mcl_ogive(k, x, y, z0, h, r, ribs=0):
    """a Mon Calamari bullet tower: a soft-shouldered ogive, banded shell and lit gold rows, optional ribs"""
    prof = [(r * 1.12, z0), (r, h * 0.08), (r * 1.05, h * 0.35), (r * 0.92, h * 0.68), (r * 0.62, h * 0.88),
            (r * 0.25, h * 0.98), (0.0, h)]
    k.lathe(prof, [B_PLATE, B_PLATE_WIN, B_PLATE, B_PLATE_WIN, B_PLATE, B_ROOF], sides=12 if ribs else 8, cx=x, cy=y)
    for i in range(ribs):
        fin(k, x, y, TAU * i / ribs + 0.3, prof[1:-2], r * 0.08, r * 0.1, B_HULL)


def mcl_shell(k, x, y, z0, r, h, ribs=8, sides=18):
    """a great low ribbed dome: a lit band at its foot, the shell, ribs from foot to crown"""
    z1 = max(z0, 0.0) + h * 0.12
    k.lathe([(r, z0), (r, z1)], B_PLATE_WIN, sides=sides, cx=x, cy=y)
    prof = [(r * math.cos(math.pi / 2 * i / 4), z1 + (h * 0.88) * math.sin(math.pi / 2 * i / 4)) for i in range(5)]
    k.lathe(prof, [B_PLATE, B_ROOF, B_PLATE_WIN, B_ROOF], sides=sides, cx=x, cy=y)
    for i in range(ribs):
        fin(k, x, y, TAU * i / ribs, prof[:-1], r * 0.04, r * 0.06, B_HULL)


def mcl_pier(k, path, w=0.12, z=0.06, base=CELL_Z):
    sweep(k, path, rect_section(w, z - base, base), [B_HULL, B_CONC, B_HULL], open_sec=True)


def mcl_city(k, band, rng):
    # Mon Calamari sea towns: piers along the cell's streets, bullet towers in tight clusters of two to five beside
    # them joined by sky-tubes, low ribbed domes, ring platforms with small domes on them in the outskirts.
    # band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.35)
    for p in paths:
        mcl_pier(k, p[::2] + [p[-1]])
        lots.block_path(p, 0.14)
    for _ in range(1 + (band + 1) // 2):                                           # tower clusters
        p_ = lots.spot(0.16 + 0.03 * band)
        if not p_:
            continue
        n = rng.randint(2, 2 + band)
        tops = []
        for i in range(n):
            a, d = rng.uniform(0, TAU), rng.uniform(0.0, 0.12 + 0.02 * band) * (i > 0)
            r = rng.uniform(0.05, 0.075) + 0.008 * band
            h = (rng.uniform(0.45, 0.8) + 0.3 * band) * (1.0 if i == 0 else rng.uniform(0.45, 0.85))
            tx, ty = p_[0] + d * math.cos(a), p_[1] + d * math.sin(a)
            mcl_ogive(k, tx, ty, CELL_Z, h, r)
            tops.append((tx, ty, h))
        for (x0, y0, h0), (x1, y1, h1) in zip(tops, tops[1:]):                    # sky-tubes
            z = min(h0, h1) * 0.45
            k.tube((x0, y0, z), (x1, y1, z), 0.015, B_PLATE_WIN, sides=4)
    for _ in range(3 - band // 3):                                                 # ribbed domes
        r = rng.uniform(0.1, 0.16)
        p_ = lots.spot(r)
        if p_:
            mcl_shell(k, p_[0], p_[1], CELL_Z, r, r * 0.8, ribs=0, sides=10)
    if band <= 2:                                                                  # ring platforms
        p_ = lots.spot(0.24)
        if p_:
            ringp = arc_path(p_[0], p_[1], 0.05, 0.2, 0.0, TAU, 10)[:-1]
            sweep(k, ringp, [(0.05, CELL_Z), (0.05, 0.05), (-0.05, 0.05), (-0.05, CELL_Z)], [B_HULL, B_CONC, B_HULL],
                  closed_path=True, open_sec=True)
            for i in range(3):
                a = rng.uniform(0, TAU)
                dome(k, p_[0] + 0.2 * math.cos(a), p_[1] + 0.2 * math.sin(a), 0.05, 0.045, 0.05, B_PLATE_WIN, sides=6, n=2)


def mcl_coral_city(k):
    # Coral City / Dac City, the capital of Mon Cala (canon, Darth Vader (2017) 13: tall rounded bullet towers in
    # clusters and a great low dome rising from the water; "built over a" reef): the royal palace's great ribbed dome
    # set west with a smaller dome on its shoulder, the tower cluster climbing to the north-east (the tallest ~11),
    # three short towers south, reef rock under the east half, sky-tubes between the towers, piers reaching out
    # south and east, coral on the reef. ~13 across
    import random
    rng = random.Random("mcl_coral_city")
    rock(k, 2.0, 1.0, -SKIRT, 0.7, 4.0, rng, [B_DUST, B_CONC, B_CONC], lobes=3)                # the reef
    rock(k, -2.8, -0.4, -SKIRT, 0.4, 3.4, rng, [B_DUST, B_CONC], lobes=2, tiers=2)
    mcl_shell(k, -2.8, -0.4, 0.4, 3.0, 3.0, ribs=12, sides=24)                                 # the palace
    mcl_shell(k, -1.3, 1.2, 2.4, 1.0, 1.0, ribs=6, sides=14)
    towers = [(1.2, 2.6, 11.0, 0.75), (2.6, 1.6, 8.6, 0.65), (0.6, 4.2, 7.4, 0.55), (3.2, 3.6, 9.4, 0.6),
              (4.4, 0.6, 6.0, 0.5), (2.0, 4.6, 5.2, 0.45), (-0.2, 2.8, 6.4, 0.5)]
    for x, y, h, r in towers:
        mcl_ogive(k, x, y, -SKIRT, h, r, ribs=4)
    for x, y, h, r in ((0.4, -3.6, 3.2, 0.5), (1.6, -3.0, 2.4, 0.42), (-0.6, -4.4, 2.0, 0.36)):
        mcl_ogive(k, x, y, -SKIRT, h, r, ribs=3)
    for (x0, y0, h0, _), (x1, y1, h1, _) in zip(towers, towers[1:]):                           # sky-tubes
        z = min(h0, h1) * 0.4
        k.tube((x0, y0, z), (x1, y1, z), 0.1, B_PLATE_WIN, sides=6)
    mcl_pier(k, [(0.6, -1.0, 0.0), (0.8, -3.0, 0.0), (1.8, -5.6, 0.0)], 0.6, 0.15, -SKIRT)      # piers
    mcl_pier(k, [(4.0, 0.0, 0.0), (6.0, -0.8, 0.0), (6.6, -2.4, 0.0)], 0.5, 0.15, -SKIRT)
    for _ in range(12):                                                                         # coral
        a, d = rng.uniform(-1.2, 2.2), rng.uniform(2.6, 4.6)
        cx, cy = 2.0 + d * math.cos(a), 1.0 + d * math.sin(a)
        for j in range(3):
            b = rng.uniform(0, TAU)
            curve_tube(k, (cx, cy, 0.3), (cx + 0.35 * math.cos(b), cy + 0.35 * math.sin(b), 0.9), 0.25, 0.08, 0.03,
                       B_RUST, n=3, sides=4)


def mcl_drome(k):
    # the Moncaladrome, Mon Cala's opera house (canon: an opera house; its look is a design choice): three shell
    # vaults rising in a row from the stage end like opened shells, each turned a little off the last, ribs
    # over them, a lobed reef podium and a pier forecourt. ~9 long
    import random
    rng = random.Random("mcl_drome")
    rock(k, 0.0, 0.0, -SKIRT, 0.35, 4.2, rng, [B_DUST, B_CONC], lobes=2, tiers=2, sy=0.6)
    for x, w, h, L, a in ((-2.4, 1.2, 1.6, 2.0, 0.08), (-0.6, 1.6, 2.6, 2.4, -0.05), (1.6, 2.0, 3.6, 2.8, 0.1)):
        vault(k, x, 0.0, 0.35, a, L, w, h, [B_PLATE, B_PLATE_WIN, B_ROOF, B_ROOF, B_PLATE_WIN, B_PLATE], n=5, taper=0.55,
              end=B_PLATE_WIN)
        for j in (0, 2, 4):                                                                     # ribs
            u = -L / 2 + L * j / 5
            f = 1 - 0.45 * j / 5
            pts = [turn(x, 0.0, a, u, w * f * 1.04 * math.cos(math.pi * q / 6)) + (0.35 + h * f * 1.04 * math.sin(math.pi * q / 6),)
                   for q in range(7)]
            for p0, p1 in zip(pts, pts[1:]):
                k.tube(p0, p1, 0.06, B_HULL, sides=4)
    mcl_pier(k, [(-3.4, 0.0, 0.0), (-5.6, -0.6, 0.0)], 1.2, 0.35, -SKIRT)
    for y in (-0.5, 0.5):
        k.lathe([(0.05, 0.35), (0.04, 1.0), (0.12, 1.06), (0.0, 1.14)], [B_HULL, B_PLATE_WIN, B_PLATE_WIN], sides=5,
                cx=-5.0, cy=y - 0.4)


def qua_tower(k, x, y, z0, h, r, rng, tentacles=3, lite=False):
    """a Quarren tower: an angular five-sided shaft twisting as it narrows, drooping tentacle buttresses round its
    foot, lit slits, a hooded crown leaning over"""
    tw = rng.uniform(-0.5, 0.5)
    zs = [z0, 0.0, h * 0.3, h * 0.65, h * 0.88]
    fs = [1.3, 1.25, 1.0, 0.8, 0.6]
    rings = [ring(x, y, z, r * f, 5, tw * (z - z0) / h) for z, f in zip(zs, fs)]
    loft(k, rings, [B_BRICK, B_BRICK, B_PLATE_WIN, B_BRICK] if not lite else [B_BRICK, B_BRICK, B_CONC_WIN, B_BRICK])
    hx, hy = x + r * 0.25, y + r * 0.1
    loft(k, [ring(x, y, h * 0.88, r * 0.6, 5, tw * (h * 0.88 - z0) / h), ring(hx, hy, h, r * 0.35, 5, tw + 0.3)], B_SOOT,
         cap=B_SOOT)
    for i in range(0 if lite else tentacles):
        a = rng.uniform(0, TAU)
        curve_tube(k, (x + r * 0.8 * math.cos(a), y + r * 0.8 * math.sin(a), h * 0.45),
                   (x + r * 2.4 * math.cos(a), y + r * 2.4 * math.sin(a), -0.2), -h * 0.08, r * 0.22, r * 0.08, B_BRICK,
                   n=4, sides=5)


def qua_hq(k):
    # the Quarren headquarters in Quarren Town (canon: the Quarren capital's seat; Riff Tamson staged the attack on
    # the Mon Calamari from it; its look is a design choice): a dark rock outcrop, the tall twisting Quarren tower
    # off-centre on its crest with tentacle buttresses, four lesser towers in a crescent to the south, the lit
    # war-room drum half sunk in the rock, pads on pylons. ~11 across
    import random
    rng = random.Random("qua_hq")
    rock(k, 0.6, 0.8, -SKIRT, 1.4, 4.4, rng, [B_SOOT, B_BRICK, B_BRICK], lobes=3)
    qua_tower(k, 1.0, 1.6, -SKIRT, 11.0, 1.1, rng, tentacles=5)
    for a, h in ((200, 5.2), (230, 6.6), (262, 4.6), (295, 5.8)):
        x, y = 0.6 + 4.0 * math.cos(math.radians(a)), 0.8 + 4.0 * math.sin(math.radians(a))
        qua_tower(k, x, y, -SKIRT, h, 0.5, rng, tentacles=3)
    k.lathe([(1.6, -SKIRT), (1.6, 1.9), (1.3, 2.3), (0.0, 2.4)], [B_CONC_WIN, B_BRICK, B_SOOT], sides=10, cx=-1.6, cy=0.4)
    for x, y in ((3.8, -1.6), (4.6, 1.4)):
        k.lathe([(0.25, -SKIRT), (0.18, 1.2), (0.3, 1.5)], [B_BRICK, B_BRICK], sides=5, cx=x, cy=y)
        pad(k, x, y, 1.6, 0.8, B_BRICK, B_PAD, sides=10)


def qua_city(k, band, rng):
    # Quarren towns (canon: Quarren Town in the depths, Zeran Town in the north; the look is a design choice): dark
    # twisting five-sided towers on rock lumps along the cell's walkways, low rock domes, lit slits. band 1 .. 4
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.4)
    for p in paths:
        sweep(k, p[::2] + [p[-1]], rect_section(0.08, 0.34, CELL_Z), [B_BRICK, B_SOOT, B_BRICK], open_sec=True)
        lots.block_path(p, 0.1)
    for _ in range(band + 1):
        r = rng.uniform(0.05, 0.08) + 0.008 * band
        p_ = lots.along(rng.choice(paths), r * 1.6, 0.06) or lots.spot(r * 1.6)
        if p_:
            qua_tower(k, p_[0], p_[1], CELL_Z, rng.uniform(0.4, 0.7) + 0.3 * band, r, rng, lite=True)
    for _ in range(3 - band // 2):
        r = rng.uniform(0.08, 0.14)
        p_ = lots.spot(r)
        if p_:
            loft(k, [lobed(p_[0], p_[1], CELL_Z, r, 2, 0.2, 10, 0.0), lobed(p_[0], p_[1], 0.05, r * 0.9, 2, 0.2, 10, 0.0),
                     lobed(p_[0], p_[1], r * 0.6, r * 0.45, 2, 0.2, 10, 0.0)], [B_BRICK, B_CONC_WIN], cap=B_SOOT)


# ==================================================================================================== SALEUCAMI
# Saleucami (canon: TCW "The Deserter" farm, the Bad Batch "Saleucami town" stills: flat-roofed adobe blocks with
# rounded edges, water towers on splayed legs, palms; the impound dock's leaning pylons, the Imperial informational
# station, the billboard concept art; Legends: the oasis cities of Taleucema "stuck in the Outer Rim", stacked
# sandstone towers over domed houses (Republic comic panel), the cloning complex in the magma caverns). Atlas
# hod_saleucami (B_ layout): B_PLATE ochre adobe, B_CONC grey-tan stone, B_RUST / B_ROOF terracotta.

def sal_block(k, x, y, z0, h, w, d, a, rng, wall=B_PLATE_WIN, roof=B_ROOF):
    """an adobe house block: rounded corners, a parapet lip, now and then a second storey set back or a small dome"""
    rc = min(w, d) * 0.3
    loft(k, [rrect(x, y, z0, w, d, rc, a, 1), rrect(x, y, h, w, d, rc, a, 1), rrect(x, y, h, w * 0.88, d * 0.85, rc, a, 1)],
         [wall, B_PLATE], cap=roof)
    roll = rng.random()
    if roll < 0.3:
        cx, cy = turn(x, y, a, w * 0.3, d * 0.15)
        loft(k, [rrect(cx, cy, h, w * 0.5, d * 0.55, rc, a, 1), rrect(cx, cy, h + (h - max(z0, 0)) * 0.7, w * 0.5, d * 0.55,
                                                                      rc, a, 1)], wall, cap=roof)
    elif roll < 0.5:
        cx, cy = turn(x, y, a, -w * 0.3, 0)
        dome(k, cx, cy, h, min(w, d) * 0.45, min(w, d) * 0.4, B_PLATE, sides=6, n=2)


def sal_watertower(k, x, y, z0, h, r):
    """the town's water tower: a banded tank under a low conical roof on four splayed legs"""
    legs(k, x, y, z0, h, r * 1.3, r * 0.8, 4, r * 0.08, B_GIRDER, rot=0.4)
    k.lathe([(r, h), (r, h + r * 1.4), (r * 1.08, h + r * 1.45), (0.0, h + r * 1.9)], [B_PIPE, B_RUST, B_ROOF], sides=8,
            cx=x, cy=y, cap=B_RUST)


def sal_tower(k, x, y, z0, h, w, a, rng, tiers=4):
    """a Taleucema sandstone tower: stacked rounded tiers each set back, window bands, a small dome on top"""
    z, ww = z0, w
    g = max(z0, 0.0)
    for t in range(tiers):
        top = g + (h - g) * (t + 1) / tiers
        loft(k, [rrect(x, y, z, ww, ww * 0.85, ww * 0.35, a, 1), rrect(x, y, top, ww * 0.94, ww * 0.8, ww * 0.35, a, 1)],
             B_CONC_WIN if t % 2 else B_PLATE_WIN, cap=B_CONC)
        z, ww = top, ww * rng.uniform(0.72, 0.85)
    dome(k, x, y, z, ww * 0.8, ww * 0.9, B_RUST, sides=8, n=2)


def sal_city(k, band, rng):
    # Saleucami towns: crooked alleys of the cell walled by adobe blocks turned to them, small domes, a water tower,
    # awnings at the street fronts; a stepped sandstone tower in the centre. band 1 outskirts .. 4 centre
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.45)
    for p in paths:
        lots.block_path(p, 0.12)
    for p in paths:
        for _ in range(2 + band):                                                  # blocks along the alleys
            w = rng.uniform(0.06, 0.1) + 0.01 * band
            p_ = lots.along(p, w * 1.1, 0.07)
            if p_:
                hh = rng.uniform(0.05, 0.09) + 0.02 * band
                sal_block(k, p_[0], p_[1], CELL_Z, hh, w, w * rng.uniform(0.6, 0.9), p_[2], rng)
                if rng.random() < 0.35:                                            # an awning
                    ax, ay = turn(p_[0], p_[1], p_[2], 0, -w * 0.9 * (1 if rng.random() < 0.5 else -1))
                    tbox(k, ax, ay, hh * 0.6, hh * 0.68, w * 0.6, 0.03, p_[2], B_RUST, B_RUST)
    for _ in range(2):                                                             # domed huts
        r = rng.uniform(0.05, 0.08)
        p_ = lots.spot(r)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.03)], B_PLATE_WIN, sides=8, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.03, r, r * 0.9, B_PLATE, sides=8, n=2)
    if band >= 2:
        p_ = lots.spot(0.08)
        if p_:
            sal_watertower(k, p_[0], p_[1], CELL_Z, 0.25 + 0.05 * band, 0.06)
    if band >= 3:
        p_ = lots.spot(0.12)
        if p_:
            sal_tower(k, p_[0], p_[1], CELL_Z, 0.5 + 0.25 * band, 0.1, rng.uniform(0, math.pi), rng, tiers=band)


def sal_taleucema(k):
    # Taleucema, the capital of Saleucami (Legends, the Republic comic panel: a crowd of tall stacked sandstone towers
    # over terraces of domed and flat-roofed houses, pipes, palms; the arcing bridges a design choice after Revenge of
    # the Sith's "bridge planet" concept): a lobed rocky rise, seven sandstone towers packed on its crest, terraces of
    # adobe houses stepping down its south and west slopes, an arcaded gate, two parabolic bridges between the tallest
    # towers. ~13 across
    import random
    rng = random.Random("sal_taleucema")
    rock(k, 0.4, 0.8, -SKIRT, 1.2, 4.6, rng, [B_CONC, B_DUST, B_CONC], lobes=3)
    towers = [(0.6, 1.8, 11.0, 0.9), (-0.8, 2.6, 8.6, 0.8), (1.9, 2.9, 9.4, 0.75), (2.2, 0.8, 7.2, 0.7),
              (-1.2, 0.8, 6.4, 0.7), (0.4, 3.6, 6.0, 0.6), (1.0, -0.4, 5.0, 0.65)]
    for x, y, h, w in towers:
        sal_tower(k, x, y, -SKIRT, h, w, rng.uniform(-0.3, 0.3), rng, tiers=4 + int(h > 8))
    for i in range(16):                                                                        # terraces of houses
        a = math.radians(rng.uniform(160, 330))
        d = rng.uniform(3.0, 5.6)
        x, y = 0.4 + d * math.cos(a), 0.8 + d * math.sin(a)
        z = max(0.2, 1.2 * (1 - (d - 2.4) / 3.0))
        sal_block(k, x, y, -SKIRT, z + rng.uniform(0.35, 0.6), rng.uniform(0.35, 0.55), rng.uniform(0.25, 0.4),
                  a + math.pi / 2, rng)
    for (x0, y0, h0, _), (x1, y1, h1, _) in ((towers[0], towers[3]), (towers[1], towers[2])):  # parabolic bridges
        z = min(h0, h1) * 0.55
        curve_tube(k, (x0, y0, z), (x1, y1, z), 1.4, 0.12, 0.12, B_PLATE, n=8, sides=5)
    for i in range(5):                                                                         # the arcaded gate
        gx, gy = -2.6 + 0.6 * i, -3.6 - 0.15 * i
        prism_at(k, gx, gy, 0.0, -0.25, 0.5, [(-0.28, 0.0), (0.28, 0.0), (0.28, 0.9), (0.0, 1.15), (-0.28, 0.9)],
                 [B_PLATE, B_PLATE, B_ROOF, B_ROOF, B_PLATE], end=B_DARK)
    for x, y in ((-3.6, 0.6), (3.8, -1.2)):
        k.tube((x, y, 0.3), (x + 1.4, y - 1.8, 0.3), 0.12, B_PIPE, sides=6)                    # the pipes


def sal_spaceport(k):
    # Saleucami town's spaceport (canon, The Bad Batch: the impound dock where the Marauder was held, its tall
    # leaning pylons and fences; the Imperial informational station; the billboard concept art): a fenced compound,
    # three pads each overhung by a pair of leaning pylons, an arched hangar, the squat Imperial station, a control
    # tower of adobe with a bulging cab, billboards on tall legs. ~12 across
    fence = [(-5.0, -3.6, 0.0), (4.6, -4.0, 0.0), (5.2, 3.4, 0.0), (-4.2, 4.0, 0.0)]
    sweep(k, fence, [(0.05, -SKIRT), (0.05, 0.5), (-0.05, 0.5), (-0.05, -SKIRT)], [B_GIRDER, B_GIRDER, B_GIRDER],
          closed_path=True, open_sec=True)
    for x, y, a in ((-2.6, -1.4, 0.2), (0.6, -1.8, -0.1), (3.0, 0.6, 0.4)):
        k.lathe([(1.15, -SKIRT), (1.15, 0.12)], B_CONC, sides=14, cx=x, cy=y, cap=B_PAD)
        for s_ in (-1, 1):                                                                     # leaning pylons
            bx, by = turn(x, y, a, s_ * 1.3, -0.4)
            tx, ty = turn(x, y, a, s_ * 0.7, 0.3)
            k.tube((bx, by, -0.5), (tx, ty, 3.2), 0.13, B_HULL, sides=5, r1=0.06)
            k.tube((tx, ty, 3.2), (tx, ty, 3.5), 0.08, B_GLOW, sides=5)
    vault(k, -2.4, 2.4, 0.0, 0.1, 3.0, 1.2, 1.4, [B_ROOF, B_RUST, B_ROOF, B_ROOF, B_RUST, B_ROOF], end=B_PLATE)
    tbox(k, 1.4, 2.4, -SKIRT, 0.8, 0.9, 0.6, 0.1, B_HULL, B_HULL, wt=0.6, dt=0.45)             # Imperial station
    tbox(k, 1.4, 2.4, 0.4, 0.55, 0.92, 0.62, 0.1, B_DARK, B_HULL, wt=0.8, dt=0.55)
    k.lathe([(0.45, -SKIRT), (0.4, 2.6), (0.75, 2.9), (0.75, 3.3), (0.0, 3.5)], [B_PLATE, B_PLATE_WIN, B_PLATE_WIN,
                                                                              B_ROOF], sides=10, cx=4.0, cy=-2.6)
    for x, y, c in ((-4.4, 0.2, B_GLOW), (-3.8, -3.0, B_HAZARD), (4.6, 2.4, B_RUST)):          # billboards
        for s_ in (-0.25, 0.25):
            k.tube((x + s_, y, 0.0), (x + s_, y, 1.6), 0.05, B_GIRDER, sides=4)
        tbox(k, x, y, 1.6, 2.6, 0.5, 0.05, 0.2, c, c)


def sal_lawquane(k):
    # the Lawquane farmstead (canon, TCW "The Deserter": Cut Lawquane's farm in Saleucami's wetlands, among the
    # popper-stalks): a house of three joined adobe domed drums of different sizes, a barn with an arched roof, a
    # water tower on legs, a field of crop rows east of the house, fence lines, a speeder pad. ~9 across
    for x, y, r, h in ((0.0, 0.0, 1.2, 0.9), (1.3, 0.7, 0.8, 0.7), (-1.0, 1.0, 0.65, 0.6)):
        k.lathe([(r, -SKIRT), (r, h)], B_PLATE_WIN, sides=14, cx=x, cy=y)
        dome(k, x, y, h, r, r * 0.75, [B_PLATE, B_PLATE, B_ROOF], sides=14, n=3)
    vault(k, -2.8, -1.6, 0.0, 0.5, 2.2, 0.9, 1.1, [B_ROOF] * 8, end=B_PLATE)                   # the barn
    sal_watertower(k, -1.4, -2.8, -SKIRT, 1.8, 0.35)
    for i in range(7):                                                                          # crop rows
        y = -2.2 + 0.6 * i
        sweep(k, [(2.4, y, 0.0), (5.6, y + 0.3, 0.0)], [(0.15, -SKIRT), (0.0, 0.18), (-0.15, -SKIRT)], [B_DUST, B_CONC],
              open_sec=True)
    sweep(k, [(2.1, -2.6, 0.0), (5.9, -2.3, 0.0), (5.9, 2.0, 0.0), (2.1, 1.8, 0.0)], rect_section(0.04, 0.35),
          [B_GIRDER, B_GIRDER, B_GIRDER], open_sec=True)
    k.lathe([(0.8, -SKIRT), (0.8, 0.1)], B_CONC, sides=12, cx=0.4, cy=-2.6, cap=B_PAD)


def sal_cloning(k):
    # the Saleucami Cloning Complex (Legends: "an installation, overseen by the Dark Jedi Sora Bulq, built in the
    # Magma Caverns" honeycombing the rock under the capital; the comic panel: amber pods in black tubes): a black
    # volcanic mound, the caverns' mouth on its south face glowing, a lava channel winding out of it, the Separatist
    # command dome and spire beside it, a curved rack of amber pod tanks on black pipework, a landing pad. ~11 across
    import random
    rng = random.Random("sal_cloning")
    rock(k, -0.6, 1.0, -SKIRT, 3.2, 4.4, rng, [B_SOOT, B_BRICK, B_SOOT], lobes=3)
    vault(k, -0.6, -2.6, 0.0, 0.0, 1.6, 1.3, 1.6, [B_DARK] * 8, n=2, end=B_GLOW)                # the mouth
    lava = [(-0.6, -2.4, 0.04), (-0.2, -3.6, 0.04), (0.8, -4.4, 0.04), (1.0, -5.6, 0.04)]
    sweep(k, lava, [(0.3, -SKIRT), (0.3, 0.06), (-0.3, 0.06), (-0.3, -SKIRT)], [B_SOOT, B_GLOW, B_SOOT], open_sec=True)
    k.lathe([(1.2, -SKIRT), (1.2, 0.5)], B_HULL, sides=12, cx=3.0, cy=-1.2)                      # command dome
    dome(k, 3.0, -1.2, 0.5, 1.2, 1.0, [B_HULL, B_PLATE_WIN, B_HULL], sides=12, n=3)
    k.lathe([(0.15, 1.4), (0.08, 3.6), (0.0, 3.9)], [B_HULL, B_GLOW], sides=5, cx=3.0, cy=-1.2)
    for i in range(6):                                                                           # pod tanks
        a = math.radians(200 + 18 * i)
        x, y = -0.6 + 3.6 * math.cos(a), 1.0 + 3.6 * math.sin(a)
        k.lathe([(0.3, -SKIRT), (0.3, 0.3), (0.26, 1.7), (0.0, 1.9)], [B_SOOT, B_GLOW, B_SOOT], sides=8, cx=x, cy=y)
        curve_tube(k, (x, y, 1.6), (-0.6 + 2.6 * math.cos(a), 1.0 + 2.6 * math.sin(a), 2.4), 0.3, 0.08, 0.08, B_SOOT,
                   n=3, sides=4)
    k.lathe([(0.9, -SKIRT), (0.9, 0.15)], B_SOOT, sides=12, cx=3.6, cy=2.6, cap=B_PAD)


# ==================================================================================================== JABIIM
# Jabiim (Legends: the monsoon world; Republic 55-57 and Empire 33: Shelter Base, a stepped plated bunker block
# among tents and crates in the mud; Choal's saucer towers on pylons; Outpost Shear on its ridge; the Razor Coast).
# Atlas hod_jabiim (B_ layout): B_PLATE Republic white, B_RUST Republic red, B_HULL Separatist tan, B_BRICK mud
# brick, B_DUST mud.

def jab_stilt_house(k, x, y, z0, r, h, rng, a=0.0):
    """a Jabiimi rain house on stilts: a round drum and a steep conical rain roof, or a longhouse under a steep gable"""
    floor = h * 0.35
    legs(k, x, y, z0, floor, r * 0.75, r * 0.75, 4, r * 0.08, B_GIRDER, rot=a, braces=False)
    if rng.random() < 0.6:
        k.lathe([(r * 0.85, floor), (r * 0.85, h * 0.7), (r * 1.25, h * 0.68), (0.0, h * 1.25)], [B_BRICK, B_ROOF, B_ROOF],
                sides=7, cx=x, cy=y)
    else:
        tbox(k, x, y, floor, h * 0.7, r * 1.2, r * 0.7, a, B_BRICK, B_ROOF)
        prism_at(k, x, y, h * 0.7, a, r * 2.6, [(-r * 0.85, 0), (r * 0.85, 0), (0.0, h * 0.6)], [B_ROOF, B_ROOF, B_ROOF])


def jab_walkway(k, path, w, z, base=CELL_Z, posts=True):
    """a raised plank walkway over the mud on posts"""
    sweep(k, path, [(w / 2, z - 0.02), (w / 2, z), (-w / 2, z), (-w / 2, z - 0.02)], [B_GIRDER, B_ROOF, B_GIRDER, B_GIRDER])
    if posts:
        for p in path[1:-1]:
            k.tube((p[0], p[1], base), (p[0], p[1], z - 0.02), w * 0.12, B_GIRDER, sides=4)


def jab_saucer(k, x, y, z0, h, r):
    """a Choal saucer tower: a tapering pylon, a broad saucer with a lit rim, a smaller collar ring under it"""
    k.lathe([(r * 0.5, z0), (r * 0.28, h * 0.6), (r * 0.22, h)], [B_CONC, B_CONC], sides=8, cx=x, cy=y)
    k.lathe([(r * 0.24, h * 0.55), (r * 0.8, h * 0.6), (r * 0.75, h * 0.64), (r * 0.24, h * 0.66)],
            [B_PLATE, B_PLATE_WIN, B_ROOF], sides=10, cx=x, cy=y)
    k.lathe([(r * 0.24, h - r * 0.3), (r * 2.0, h), (r * 2.0, h + r * 0.12), (r * 1.4, h + r * 0.3), (0.0, h + r * 0.45)],
            [B_PLATE, B_PLATE_WIN, B_ROOF, B_PLATE], sides=14, cx=x, cy=y)


def jab_city(k, band, rng):
    # Jabiimi rain towns: raised walkways along the cell's streets above the mud, rain houses and longhouses on
    # stilts beside them, mud-brick domes, cisterns; a saucer tower in the centre. band 1 outskirts .. 4 centre
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.45)
    for p in paths:
        jab_walkway(k, p[::2] + [p[-1]], 0.06, 0.06)
        lots.block_path(p, 0.08)
    for p in paths:
        for _ in range(3 + band):
            r = rng.uniform(0.06, 0.1)
            p_ = lots.along(p, r * 1.2, 0.05)
            if p_:
                jab_stilt_house(k, p_[0], p_[1], CELL_Z, r, rng.uniform(0.22, 0.32) + 0.03 * band, rng, p_[2])
    for _ in range(3):                                                             # mud-brick domes
        r = rng.uniform(0.06, 0.09)
        p_ = lots.spot(r)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.03)], B_BRICK, sides=8, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.03, r, r * 0.8, B_BRICK, sides=8, n=2)
    p_ = lots.spot(0.06)                                                           # a cistern
    if p_:
        k.lathe([(0.055, CELL_Z), (0.055, 0.12), (0.06, 0.13)], [B_CONC, B_PIPE], sides=8, cx=p_[0], cy=p_[1], cap=B_DARK)
    if band >= 3:
        p_ = lots.spot(0.15)
        if p_:
            jab_saucer(k, p_[0], p_[1], CELL_Z, 0.5 + 0.2 * band, 0.1)


def jab_choal(k):
    # Choal, the capital of Jabiim (Legends: the Republic army under Norcuna was wiped out near it; Republic 56: saucer
    # towers on pylons over the battlefield): the council's stepped mud-brick platform with the great saucer tower on
    # it and two lesser ones beside, rain houses and longhouses on stilts crowding along a winding network of raised
    # walkways, a canal winding past, cisterns, a landing pad. ~13 across
    import random
    rng = random.Random("jab_choal")
    z = -SKIRT
    for t, (w, d) in enumerate(((2.6, 1.9), (2.0, 1.4), (1.4, 0.9))):                         # the platform
        top = 0.5 * (t + 1)
        loft(k, [rrect(-0.6, 0.6, z, w, d, 0.4, 0.2, 1), rrect(-0.6, 0.6, top, w * 0.95, d * 0.93, 0.4, 0.2, 1)],
             B_BRICK, cap=B_DUST)
        z = top
    jab_saucer(k, -0.6, 0.6, 1.5, 9.0, 0.9)
    jab_saucer(k, -2.6, 1.6, 0.5, 5.4, 0.55)
    jab_saucer(k, 1.4, 1.4, 0.5, 4.2, 0.45)
    walks = [[(-0.6, -1.2, 0.0), (0.6, -2.4, 0.0), (2.6, -2.6, 0.0), (4.6, -1.6, 0.0)],
             [(0.6, -2.4, 0.0), (0.2, -4.4, 0.0), (-1.6, -5.2, 0.0)],
             [(-3.0, -0.6, 0.0), (-4.4, -2.0, 0.0), (-4.2, -4.0, 0.0)],
             [(2.0, -0.2, 0.0), (3.6, 1.2, 0.0), (3.4, 3.4, 0.0)]]
    for w_ in walks:
        jab_walkway(k, [(x, y, 0.45) for x, y, _ in w_], 0.4, 0.45, base=-SKIRT)
    lots = Lots(rng, 6.0)
    lots.take(-0.6, 0.6, 3.0)
    for w_ in walks:
        for _ in range(5):
            p_ = lots.along(w_, 0.45, 0.35)
            if p_:
                jab_stilt_house(k, p_[0], p_[1], -SKIRT, rng.uniform(0.35, 0.5), rng.uniform(1.5, 2.1), rng, p_[2])
    canal = [(-5.6, 2.6, 0.0), (-3.6, 3.8, 0.0), (-0.4, 3.6, 0.0), (2.4, 4.6, 0.0), (5.2, 4.0, 0.0)]
    sweep(k, canal, [(0.5, -SKIRT), (0.5, 0.06), (0.35, 0.03), (-0.35, 0.03), (-0.5, 0.06), (-0.5, -SKIRT)],
          [B_BRICK, B_CONC, B_DARK, B_CONC, B_BRICK], open_sec=True)
    for x, y in ((3.0, -4.2), (-2.4, -2.8), (4.6, 2.0)):
        k.lathe([(0.35, -SKIRT), (0.35, 0.7), (0.38, 0.75)], [B_CONC, B_PIPE], sides=8, cx=x, cy=y, cap=B_DARK)
    k.lathe([(0.9, -SKIRT), (0.9, 0.15)], B_CONC, sides=12, cx=4.4, cy=-3.8, cap=B_PAD)


def jab_shelter(k):
    # Shelter Base (Legends, Republic 55: the Republic's command centre in the Battle of Jabiim, a big stepped bunker
    # block of plated tiers rising out of the mud among tents, crates and a domed silo; the user, 2026-10-16: the
    # bases already stand): the four-tier battered bunker with its arched gate, a comm mast and dish on top, the domed
    # silo to the east, rows of tents west, crate stacks, a sandbag berm round the south, two gunship pads. ~12 across
    import random
    rng = random.Random("jab_shelter")
    sq = lambda w, d: [(-w, -d), (w, -d), (w, d), (-w, d)]
    z = -SKIRT
    for t, (w, d, h) in enumerate(((2.8, 2.2, 1.4), (2.3, 1.8, 2.6), (1.8, 1.4, 3.6), (1.2, 0.9, 4.4))):
        lo = [turn(0.2, 0.6, 0.1, u, v) + (z,) for u, v in sq(w, d)]
        hi = [turn(0.2, 0.6, 0.1, u, v) + (h,) for u, v in sq(w * 0.93, d * 0.92)]
        loft(k, [lo, hi], B_CONC_WIN if t % 2 else B_PLATE, cap=B_ROOF)
        z = h
    gx, gy = turn(0.2, 0.6, 0.1, 0.0, -2.25)
    prism_at(k, gx, gy, 0.0, 0.1, 0.4, [(-0.55, 0.0), (0.55, 0.0), (0.55, 0.7), (0.0, 1.1), (-0.55, 0.7)], B_DARK)
    k.lathe([(0.08, 4.4), (0.05, 7.0), (0.0, 7.3)], [B_GIRDER, B_RUST], sides=4, cx=0.6, cy=0.8)  # the mast
    k.lathe([(0.0, 4.9), (0.45, 5.2), (0.5, 5.3)], [B_PLATE, B_PLATE], sides=10, cx=-0.2, cy=0.4)
    k.lathe([(1.1, -SKIRT), (1.1, 1.8)], B_PLATE_WIN, sides=12, cx=4.0, cy=1.4)                 # the domed silo
    dome(k, 4.0, 1.4, 1.8, 1.1, 0.8, [B_PLATE, B_RUST, B_PLATE], sides=12, n=3)
    for i in range(8):                                                                          # tents
        tx, ty = -4.0 + 0.9 * (i % 2), -1.6 + 1.0 * (i // 2)
        prism_at(k, tx, ty, 0.0, 0.0, 0.7, [(-0.32, 0.0), (0.32, 0.0), (0.0, 0.45)], [B_PLATE, B_PLATE, B_PLATE],
                 end=B_PLATE)
    for i in range(10):                                                                         # crates
        cx, cy = rng.uniform(-3.4, 3.6), rng.uniform(-4.2, -3.0)
        tbox(k, cx, cy, -0.2, rng.uniform(0.2, 0.45), 0.2, 0.15, rng.uniform(0, 1), B_HULL, B_ROOF)
    berm = arc_path(0.2, 0.6, 0.0, 5.6, math.radians(200), math.radians(340), 10)
    sweep(k, berm, [(0.4, -SKIRT), (0.15, 0.45), (-0.15, 0.45), (-0.4, -SKIRT)],
          [B_DUST, B_DUST, B_DUST], open_sec=True)
    for x, y, a in ((-3.4, 3.2, 0.6), (3.0, 4.2, -0.4)):
        k.lathe([(1.0, -SKIRT), (1.0, 0.12)], B_CONC, sides=12, cx=x, cy=y, cap=B_PAD)
        gunship(k, x, y, 0.12, a, 1.8)


def jab_cobalt(k):
    # Cobalt Station (Legends: a Republic fortification "just north of Monsoon Mesa"; the bases stand at the start): a
    # rocky knoll, a curved rampart along its south and west brows with a parapet, four gun turrets with twin heavy
    # barrels on it, a domed bunker on the crest, the shield-generator dome with its glowing ring, half-buried
    # ammunition bunkers behind. ~10 across
    import random
    rng = random.Random("jab_cobalt")
    rock(k, 0.4, 0.6, -SKIRT, 1.2, 4.0, rng, [B_DUST, B_CONC, B_CONC], lobes=2)
    ram = [(x, y, 1.0) for x, y in bezier((-3.8, 2.2), (-4.2, -3.6), (3.6, -3.0), 10)]
    sweep(k, ram, [(0.5, -SKIRT), (0.4, 0.7), (0.25, 0.7), (0.25, 0.95), (-0.35, 0.95), (-0.5, -SKIRT)],
          [B_CONC, B_CONC, B_PLATE, B_ROOF, B_CONC], caps=B_CONC, open_sec=True)
    for i in (2, 4, 6, 8):                                                                      # gun turrets
        (x, y, _z), h = path_at(ram, path_len(ram) * i / 10)
        k.lathe([(0.45, 1.9), (0.45, 2.3), (0.32, 2.5), (0.0, 2.55)], [B_PLATE, B_PLATE, B_RUST], sides=10, cx=x, cy=y)
        out = h - math.pi / 2
        for s_ in (-0.12, 0.12):
            bx, by = turn(x, y, out, 0.2, s_)
            k.tube((bx, by, 2.25), (bx + 1.1 * math.cos(out), by + 1.1 * math.sin(out), 2.4), 0.06, B_GIRDER, sides=5)
    k.lathe([(0.9, 0.8), (0.9, 1.7)], B_CONC_WIN, sides=12, cx=0.6, cy=1.0)                      # domed bunker
    dome(k, 0.6, 1.0, 1.7, 0.9, 0.6, [B_PLATE, B_PLATE], sides=12, n=2)
    k.lathe([(0.9, 0.8), (0.9, 1.0)], B_GLOW, sides=14, cx=2.4, cy=2.4)                          # shield generator
    dome(k, 2.4, 2.4, 1.0, 0.85, 0.85, [B_PLATE, B_PLATE_WIN, B_PLATE], sides=14, n=3)
    for x, y in ((-1.2, 2.6), (-0.4, 3.4)):
        prism_at(k, x, y, 0.6, 0.4, 1.0, [(-0.4, 0.0), (0.4, 0.0), (0.25, 0.35), (-0.25, 0.35)], B_CONC, end=B_DARK)


def jab_aurek(k):
    # Aurek base (Legends: a Separatist / Nationalist position in the Battle of Jabiim; its look is a design choice in
    # Separatist tan): the droid-control spire standing north with ribbed bands and an antenna crown, rounded hab
    # pods in a crescent south of it, a parked troop transport, racks of folded battle droids, a dish array, a fence
    # line on posts. ~12 across
    k.lathe([(0.9, -SKIRT), (0.8, 0.6), (0.5, 4.0), (0.35, 8.0), (0.5, 8.4), (0.2, 9.0)],
            [B_HULL, B_HULL, B_PLATE_WIN, B_HULL, B_HULL], sides=10, cx=0.4, cy=3.2)               # the spire
    for i in range(4):
        fin(k, 0.4, 3.2, TAU * i / 4 + 0.4, [(0.85, 0.0), (0.5, 4.0), (0.35, 8.0)], 0.3, 0.12, B_HULL)
        a = TAU * i / 4
        k.tube((0.4 + 0.15 * math.cos(a), 3.2 + 0.15 * math.sin(a), 8.8), (0.4 + 0.6 * math.cos(a), 3.2 + 0.6 * math.sin(a),
                                                                           10.2), 0.04, B_GIRDER, sides=4)
    for i in range(6):                                                                          # hab pods
        a = math.radians(200 + 28 * i)
        x, y = 0.4 + 3.6 * math.cos(a), 1.6 + 3.6 * math.sin(a)
        k.tube((x - 0.5 * math.sin(a), y + 0.5 * math.cos(a), 0.4), (x + 0.5 * math.sin(a), y - 0.5 * math.cos(a), 0.4),
               0.45, B_HULL, sides=8)
        k.lathe([(0.25, -SKIRT), (0.25, 0.1)], B_GIRDER, sides=6, cx=x, cy=y)
    tbox(k, 3.2, 1.8, -SKIRT, 0.6, 0.9, 0.55, 0.3, B_HULL, B_HULL, wt=0.8, dt=0.4)               # the transport
    prism_at(k, *turn(3.2, 1.8, 0.3, 1.2, 0), 0.0, 0.3, 1.1, [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.55)], B_HULL)
    for i in range(3):                                                                          # droid racks
        tbox(k, -3.0 + 0.7 * i, 0.2, 0.0, 0.5, 0.25, 0.6, 0.0, B_GIRDER, B_HULL)
    for x, y in ((-3.4, 2.6), (-2.4, 3.6), (-3.8, 3.8)):                                         # dishes
        k.tube((x, y, 0.0), (x, y, 1.1), 0.06, B_GIRDER, sides=4)
        k.lathe([(0.0, 1.05), (0.5, 1.35), (0.55, 1.4)], [B_HULL, B_HULL], sides=10, cx=x, cy=y)
    sweep(k, [(-5.0, -2.4, 0.0), (-4.4, 4.8, 0.0), (4.6, 5.0, 0.0), (5.2, -2.0, 0.0)], rect_section(0.05, 0.6),
          [B_GIRDER, B_GIRDER, B_GIRDER], open_sec=True)


def jab_shear(k):
    # Outpost Shear (Legends, Republic 56: a defensive position of the Confederacy-allied Jabiimi Nationalists on a
    # ridge, stormed by AT-TEs and first-generation AT-ATs; it stands at the start): rough stone bunkers strung along
    # the ridge line, a zig-zag trench berm before them, two artillery pieces, a watchtower with a lookout cabin, a
    # banner. ~10 long
    import random
    rng = random.Random("jab_shear")
    ridge = [(-4.6, -0.8, 0.0), (-2.0, 0.2, 0.0), (0.8, -0.2, 0.0), (3.4, 0.6, 0.0), (4.8, 0.2, 0.0)]
    sweep(k, ridge, [(1.6, -SKIRT), (0.5, 0.9), (-0.6, 0.9), (-1.8, -SKIRT)], [B_DUST, B_CONC, B_DUST], caps=B_DUST,
          open_sec=True)
    for i in range(4):                                                                          # stone bunkers
        (x, y, _z), h = path_at(ridge, path_len(ridge) * (0.12 + 0.25 * i))
        loft(k, [lobed(x, y, 0.5, 0.7, 2, 0.15, 12, h), lobed(x, y, 1.3, 0.6, 2, 0.15, 12, h),
                 lobed(x, y, 1.55, 0.35, 2, 0.15, 12, h)], [B_BRICK, B_BRICK], cap=B_DUST)
        sx, sy = turn(x, y, h, 0, -0.6)
        tbox(k, sx, sy, 0.95, 1.1, 0.35, 0.03, h, B_DARK, B_DARK)
    zig = [(-4.4 + 1.1 * i, -2.0 + (0.5 if i % 2 else 0.0), 0.0) for i in range(9)]
    sweep(k, zig, [(0.35, -SKIRT), (0.1, 0.35), (-0.1, 0.35), (-0.35, -SKIRT)], B_DUST, open_sec=True)
    for x, y, a in ((-1.0, 1.4, 0.4), (2.0, 1.8, -0.2)):                                         # artillery
        tbox(k, x, y, 0.7, 1.05, 0.35, 0.25, a, B_HULL, B_HULL)
        k.tube((x, y, 1.0), (x + 1.4 * math.cos(a - math.pi / 2), y + 1.4 * math.sin(a - math.pi / 2), 1.5), 0.07,
               B_GIRDER, sides=5)
    legs(k, 4.2, -0.6, 0.6, 3.0, 0.45, 0.3, 4, 0.05, B_GIRDER)                                    # watchtower
    tbox(k, 4.2, -0.6, 3.0, 3.5, 0.4, 0.4, 0.3, B_BRICK, B_ROOF)
    prism_at(k, 4.2, -0.6, 3.5, 0.3, 1.0, [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.35)], B_ROOF)
    k.tube((-3.6, 0.2, 0.6), (-3.6, 0.2, 3.0), 0.05, B_GIRDER, sides=4)                          # the banner
    tbox(k, -3.3, 0.2, 2.2, 2.9, 0.3, 0.02, 0.0, B_HULL, B_HULL)
    del rng


# ==================================================================================================== BONADAN
# Bonadan (Legends: the Corporate Sector's industrial world "covered with factories, refineries, docks, and
# shipbuilding facilities", its air poisoned, ten spaceports; Empire at War's Bonadan: yellow eroded waste with
# smoking vents). The look is a design choice: sawtooth factory halls ranked along streets carrying pipe racks,
# chimney clusters, tank farms, hyperbolic cooling towers, gantry cranes over docking pits.

def bon_chimney(k, x, y, z0, h, r):
    k.lathe([(r * 1.3, z0), (r, h * 0.15), (r * 0.8, h * 0.9), (r * 0.85, h)], [B_BRICK, B_BRICK, B_SOOT], sides=6, cx=x,
            cy=y)


def bon_stack(k, x, y, z0, h, r, sides=10):
    """a factory smokestack: soot-topped brick, a band of lights near the top (Pammant's cities use it too)"""
    k.lathe([(r, z0), (r * 0.72, z0 + h)], [B_BRICK], sides=sides, cx=x, cy=y, cap=B_SOOT)
    k.lathe([(r * 0.8, z0 + h * 0.86), (r * 0.8, z0 + h * 0.89)], [B_GLOW], sides=sides, cx=x, cy=y)


def bon_cooling(k, x, y, z0, h, r, sides=12):
    """a hyperbolic cooling tower"""
    k.lathe([(r, z0), (r, 0.0), (r * 0.62, h * 0.65), (r * 0.7, h)], [B_CONC, B_CONC, B_CONC], sides=sides, cx=x, cy=y)


def bon_sawtooth(k, x, y, z0, h, w, d, a, teeth, wall=B_PLATE_WIN):
    """a factory hall: walls, then a sawtooth roof of `teeth` north-light ridges across its length"""
    tbox(k, x, y, z0, h, w, d, a, wall, B_ROOF)
    tw = 2 * w / teeth
    for i in range(teeth):
        cx, cy = turn(x, y, a, -w + tw * (i + 0.5), 0)
        prism_at(k, cx, cy, h, a + math.pi / 2, 2 * d, [(-tw / 2, 0.0), (tw / 2, 0.0), (-tw / 2, tw * 0.55)],
                 [B_ROOF, B_GLOW, B_ROOF], end=wall)


def bon_piperack(k, path, z, base=CELL_Z, n_pipes=2, w=0.06, posts=True):
    """pipes on a rack along a street: two or three pipes side by side on posts"""
    for j in range(n_pipes):
        off = (j - (n_pipes - 1) / 2) * w * 0.5
        sweep(k, offset_path(path, off), [(w * 0.18, z), (0.0, z + w * 0.18), (-w * 0.18, z), (0.0, z - w * 0.18)],
              B_PIPE)
    if posts:
        for p in path[1:-1]:
            k.tube((p[0], p[1], base), (p[0], p[1], z), w * 0.12, B_GIRDER, sides=4)


def bon_city(k, band, rng):
    # Bonadan's industrial districts: the cell's streets carrying pipe racks, sawtooth factory halls ranked along them,
    # tank farms, chimney clusters, a hyperbolic cooling tower and concrete hab slabs downtown, concrete yards.
    # band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.2, curvy=False)
    for p in paths:
        sweep(k, [p[0], p[-1]], rect_section(0.12, 0.31, CELL_Z), [B_CONC, B_DUST, B_CONC], open_sec=True)
        bon_piperack(k, offset_path([p[0], p[len(p) // 2], p[-1]], 0.075), 0.12)
        lots.block_path(p, 0.18)
    for _ in range(2 + band // 2):                                                 # factory halls
        w = rng.uniform(0.14, 0.22)
        p_ = lots.along(rng.choice(paths), w * 0.9, 0.1)
        if p_:
            bon_sawtooth(k, p_[0], p_[1], CELL_Z, rng.uniform(0.07, 0.11) + 0.02 * band, w, w * 0.55, p_[2],
                         rng.randint(3, 4))
    p_ = lots.spot(0.16)                                                           # a tank farm
    if p_:
        a = rng.uniform(0, math.pi)
        for i in range(4):
            tx, ty = turn(p_[0], p_[1], a, (i % 2 - 0.5) * 0.15, (i // 2 - 0.5) * 0.15)
            k.lathe([(0.06, CELL_Z), (0.06, 0.08), (0.03, 0.11)], [B_PLATE, B_ROOF], sides=8, cx=tx, cy=ty)
    for _ in range(1 + band // 2):                                                 # chimney clusters
        p_ = lots.spot(0.06)
        if p_:
            for i in range(rng.randint(1, 3)):
                bon_chimney(k, p_[0] + 0.05 * i, p_[1] + 0.03 * (i % 2), CELL_Z, rng.uniform(0.7, 1.1) + 0.2 * band, 0.03)
    if band >= 3:
        p_ = lots.spot(0.16)
        if p_:
            bon_cooling(k, p_[0], p_[1], CELL_Z, 0.55 + 0.1 * band, 0.14, sides=10)
        for _ in range(band - 2):                                                  # hab slabs
            w = rng.uniform(0.1, 0.15)
            p_ = lots.along(rng.choice(paths), w, 0.1)
            if p_:
                tbox(k, p_[0], p_[1], CELL_Z, rng.uniform(0.4, 0.7) + 0.15 * band, w, w * 0.45, p_[2], B_CONC_WIN, B_ROOF)
    for _ in range(2):                                                             # concrete yards
        p_ = lots.spot(0.12)
        if p_:
            tbox(k, p_[0], p_[1], CELL_Z, 0.01, 0.12, 0.08, rng.uniform(0, math.pi), B_CONC, B_DUST)


def bon_spaceport(k):
    # Spaceport Southeast II, the largest of Bonadan's ten spaceports (Legends; its look is a design choice): four
    # raised docking pits in a staggered row, gantry cranes spanning them, the long sawtooth terminal along their
    # north side, an angular control tower at its east end, a tank farm and chimneys to the west, pipe racks
    # between. ~11 across
    import random
    rng = random.Random("bon_spaceport")
    pits = [(-2.8, -1.6), (-0.4, -2.2), (2.0, -1.6), (4.2, -2.6)]
    for i, (x, y) in enumerate(pits):
        w = 1.0 if i != 1 else 1.2
        outer, inner = rrect(x, y, 0.0, w, w, 0.35, 0.05 * i, 2), rrect(x, y, 0.0, w * 0.82, w * 0.82, 0.3, 0.05 * i, 2)
        loft(k, [at_z(outer, -SKIRT), at_z(outer, 0.7)], B_CONC_WIN)
        loft(k, [at_z(outer, 0.7), at_z(inner, 0.7)], B_HAZARD)
        loft(k, [at_z(inner, 0.7), at_z(inner, 0.25)], B_PLATE, cap=B_PAD)
        for s_ in (-1, 1):                                                                        # gantry crane
            lx, ly = turn(x, y, 0.05 * i, s_ * w * 1.05, 0)
            k.tube((lx, ly - w * 0.8, 0.0), (lx, ly - w * 0.8, 2.2), 0.08, B_HAZARD, sides=4)
            k.tube((lx, ly + w * 0.8, 0.0), (lx, ly + w * 0.8, 2.2), 0.08, B_HAZARD, sides=4)
            k.tube((lx, ly - w * 0.8, 2.2), (lx, ly + w * 0.8, 2.2), 0.08, B_GIRDER, sides=4)
        tbox(k, x, y, 2.15, 2.4, w * 1.1, 0.12, 0.05 * i, B_GIRDER, B_HAZARD)
    term = [(-4.4, 1.4, 0.0), (0.0, 1.0, 0.0), (4.6, 1.2, 0.0)]
    for (x0, y0, _), (x1, y1, _) in zip(term, term[1:]):
        a = math.atan2(y1 - y0, x1 - x0)
        bon_sawtooth(k, (x0 + x1) / 2, (y0 + y1) / 2, -SKIRT, 1.2, math.hypot(x1 - x0, y1 - y0) / 2, 0.9, a, 6)
    tbox(k, 5.4, 1.6, -SKIRT, 4.2, 0.6, 0.6, 0.3, B_PLATE_WIN, B_ROOF, wt=0.45, dt=0.45)          # control tower
    tbox(k, 5.4, 1.6, 4.2, 4.8, 0.85, 0.75, 0.3, B_CONC_WIN, B_ROOF, wt=0.7, dt=0.6, base=B_SOOT)
    for i in range(6):                                                                          # tank farm
        k.lathe([(0.4, -SKIRT), (0.4, 0.8), (0.2, 1.0)], [B_PLATE, B_ROOF], sides=10, cx=-5.2 + 0.9 * (i % 2),
                cy=-1.8 + 0.9 * (i // 2))
    for i in range(3):
        bon_chimney(k, -3.4 + 0.5 * i, 3.0 + 0.2 * (i % 2), -SKIRT, 4.2 + rng.uniform(0, 1.2), 0.22)
    bon_piperack(k, [(-4.4, -0.2, 0.0), (0.0, -0.4, 0.0), (5.0, -0.4, 0.0)], 0.9, base=-SKIRT, n_pipes=3, w=0.45)


def bon_weather(k):
    # the weather-control station (Legends: "a massive weather-control station lay in the mountains to the north of
    # the main cities; it was used to generate sweeper storms that cleaned the polluted air"; the look is a design
    # choice): concrete terraces stepping up a slope to the north, three lattice emitter masts of unequal height in an
    # uneven triangle with stacked glowing rings, a great dish on a tilted mount, bunker halls cut into the terraces,
    # a pad. ~10 across
    import random
    rng = random.Random("bon_weather")
    for t, (y, w) in enumerate(((-2.6, 4.2), (-0.8, 3.6), (1.0, 3.0), (2.6, 2.2))):            # the terraces
        top = 0.5 * (t + 1)
        loft(k, [rrect(0.4 * t, y, -SKIRT, w, 1.2, 0.2, 0.08 * t, 1), rrect(0.4 * t, y, top, w, 1.15, 0.2, 0.08 * t, 1)],
             B_CONC_WIN if t % 2 else B_CONC, cap=B_DUST)
    for x, y, z, h in ((-2.2, -0.6, 1.0, 7.0), (1.8, 1.2, 1.5, 9.0), (0.6, -2.6, 0.5, 5.4)):   # emitter masts
        legs(k, x, y, z, z + h, 0.55, 0.12, 3, 0.06, B_GIRDER, rot=rng.uniform(0, 1))
        for j in range(3):
            zz = z + h * (0.45 + 0.18 * j)
            r = 0.55 * (1 - 0.6 * (zz - z) / h) + 0.25
            k.lathe([(r, zz), (r * 1.1, zz + 0.12), (r, zz + 0.24)], [B_GLOW, B_PLATE], sides=10, cx=x, cy=y)
    k.tube((2.8, -1.4, 0.5), (2.8, -1.4, 2.0), 0.18, B_GIRDER, sides=6)                        # the dish
    dx, dy, dz = 2.8, -1.4, 2.0
    dish = [[(dx + r * math.cos(t) * 0.8, dy + r * math.sin(t), dz + r * r * 0.18 + r * math.cos(t) * 0.55)
             for t in (TAU * i / 14 for i in range(14))] for r in (0.01, 0.8, 1.6)]
    loft(k, dish, [B_PLATE, B_PLATE])
    for x, y in ((-1.4, 1.0), (-2.8, 2.6)):
        vault(k, x, y, 1.0 + 0.5 * (y > 2), 0.1, 1.4, 0.5, 0.45, [B_CONC] * 8, end=B_CONC_WIN)
    k.lathe([(0.9, -SKIRT), (0.9, 0.15)], B_CONC, sides=12, cx=-3.6, cy=-2.8, cap=B_PAD)


# ==================================================================================================== TELOS
# Telos IV (the user, 2026-10-19: almost entirely a city; the look after Knights of the Old Republic II's Telos and
# Citadel Station: rounded modular blocks of cream plating, blue-glass window bands, orange Telosian trim, slanted
# crowns; canon: Thani the capital, seat of the Telosian Council; the Mirror Caverns lined with black malab; RZ-0031
# behind its restoration shield wall with an air defense tower; Legends: the Thani Terminal, the Polar Academy).
# Atlas hod_telos (B_ layout): B_PLATE cream plating, B_CONC_WIN blue glass, B_RUST orange trim, B_ROOF slate blue,
# B_SOOT polar ice, B_BRICK black malab.

def tel_tower(k, x, y, z0, h, w, a, rng, tiers=3, lite=False):
    """a Telosian tower: rounded-rectangle shafts each set back over an orange trim ledge, blue window bands
    (recessed on landmarks, painted on city cells: lite), a slanted crown and a mast"""
    g = max(z0, 0.0)
    z, ww = z0, w
    for t in range(tiers):
        top = g + (h - g) * (t + 1) / tiers
        d = ww * 0.7
        ring_at = lambda zz, grow, ww=ww, d=d: rrect(x, y, zz, ww + grow, d + grow, (d + grow) * 0.6, a, 2)
        if lite:
            loft(k, [ring_at(z, 0.0), ring_at(top, 0.0)], B_PLATE_WIN, cap=B_ROOF)
        else:
            banded(k, ring_at, z, top, max(2, int((top - max(z, 0.0)) / 0.9)), B_PLATE, B_CONC_WIN, inset=ww * 0.05,
                   cap=B_ROOF)
        lip = ww * 0.12
        loft(k, [ring_at(top - lip, ww * 0.06), ring_at(top, ww * 0.06)], B_RUST, cap=B_ROOF)    # the trim ledge
        z, ww = top, ww * rng.uniform(0.7, 0.82)
    tbox(k, x, y, z, z + ww * 0.9, ww * 0.9, ww * 0.6, a, B_CONC_WIN, B_ROOF, wt=ww * 0.9, dt=ww * 0.1)   # slanted crown
    k.tube((x, y, z + ww * 0.9), (x, y, z + ww * 0.9 + (h - g) * 0.1), ww * 0.08, B_HULL, sides=5, r1=0.005)


def tel_module(k, x, y, z0, h, w, d, a, rng):
    """a low Telosian module: a rounded block with a window band and an orange trim, now and then a roof pad"""
    rc = min(w, d) * 0.5
    loft(k, [rrect(x, y, z0, w, d, rc, a, 2), rrect(x, y, h * 0.8, w, d, rc, a, 2), rrect(x, y, h, w, d, rc, a, 2)],
         [B_PLATE_WIN, B_RUST], cap=B_ROOF)
    if rng.random() < 0.3:
        pad(k, x, y, h + 0.02, min(w, d) * 0.7, B_HULL, B_PAD, sides=10, under=0.02)


def tel_city(k, band, rng):
    # Telos's city to the horizon: straight avenues (the Chodo Habat Parkway's kind) lined with rounded towers, low
    # modules between, a skyway between the two tallest downtown. band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.2, curvy=False)
    for p in paths:
        sweep(k, [p[0], p[-1]], rect_section(0.14 + 0.02 * band, 0.315, CELL_Z), [B_CONC, B_DUST, B_CONC], open_sec=True)
        lots.block_path(p, 0.18 + 0.02 * band)
    towers = []
    for _ in range(band + 2):
        w = rng.uniform(0.07, 0.1) + 0.012 * band
        p_ = lots.along(rng.choice(paths), w * 1.3, 0.1 + 0.012 * band) or lots.spot(w * 1.3)
        if not p_:
            continue
        a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
        h = rng.uniform(0.4, 0.7) + 0.35 * band + (rng.uniform(0.3, 0.9) if band == 4 else 0.0)
        tel_tower(k, p_[0], p_[1], CELL_Z, h, w, a, rng, tiers=2 if band < 3 else 3, lite=True)
        towers.append((p_[0], p_[1], h))
    for _ in range(5 - band):                                                      # low modules
        w = rng.uniform(0.1, 0.18)
        p_ = lots.along(rng.choice(paths), w, 0.1)
        if p_:
            tel_module(k, p_[0], p_[1], CELL_Z, rng.uniform(0.08, 0.16), w, w * rng.uniform(0.45, 0.7), p_[2], rng)
    if band >= 3 and len(towers) >= 2:                                             # a skyway
        (x0, y0, h0), (x1, y1, h1) = sorted(towers, key=lambda t: -t[2])[:2]
        z = min(h0, h1) * 0.6
        sweep(k, [(x0, y0, z), (x1, y1, z)], rect_section(0.05, 0.04), B_PLATE_WIN, caps=B_HULL)


def tel_thani(k):
    # Thani, the capital (canon: the seat of the Telosian Council and the Governor; Legends: the Chodo Habat Parkway
    # runs through it): a lobed civic podium, the Council's rotunda under a slate dome ringed by columns, five
    # Telosian towers behind it joined by skyways, the Parkway sweeping past on pylons along the south. ~14 across
    import random
    rng = random.Random("tel_thani")
    plaza = lobed(0.0, 0.4, 0.0, 4.8, lobes=3, amp=0.18, n=30, phase=0.4, sy=0.8)
    loft(k, [at_z(plaza, -SKIRT), at_z(plaza, 0.5), scaled(at_z(plaza, 0.7), 0.97)], [B_CONC_WIN, B_CONC], cap=B_DUST)
    k.lathe([(1.9, 0.6), (1.9, 2.0), (2.0, 2.15)], [B_PLATE_WIN, B_RUST], sides=24, cx=0.0, cy=-0.6)   # the rotunda
    dome(k, 0.0, -0.6, 2.15, 1.85, 1.3, [B_ROOF, B_ROOF, B_GLOW, B_ROOF], sides=24)
    for i in range(14):                                                                        # its colonnade
        t = TAU * i / 14
        k.tube((2.25 * math.cos(t), -0.6 + 2.25 * math.sin(t), 0.6), (2.25 * math.cos(t), -0.6 + 2.25 * math.sin(t), 2.1),
               0.09, B_PLATE, sides=6)
    towers = [(0.2, 3.4, 13.5, 1.1), (2.7, 2.0, 11.0, 1.0), (-2.5, 2.3, 10.0, 0.9), (3.5, -1.0, 8.0, 0.8),
              (-3.3, -0.6, 7.0, 0.75)]
    for x, y, h, w in towers:
        tel_tower(k, x, y, -SKIRT, h, w, rng.uniform(-0.3, 0.3), rng, tiers=3 + int(h > 10))
    for (x0, y0, h0, _), (x1, y1, h1, _) in ((towers[0], towers[1]), (towers[0], towers[2]), (towers[1], towers[3])):
        z = min(h0, h1) * 0.45
        sweep(k, [(x0, y0, z), (x1, y1, z)], rect_section(0.35, 0.3), B_PLATE_WIN, caps=B_HULL)   # skyways
    park = [(-6.4, -3.4, 1.3), (-2.2, -3.9, 1.5), (2.0, -3.8, 1.5), (6.2, -2.8, 1.3)]           # the Parkway
    sweep(k, park, [(0.45, 0.0), (0.45, 0.16), (-0.45, 0.16), (-0.45, 0.0)], [B_CONC, B_DUST, B_CONC, B_CONC], caps=B_CONC)
    for x, y, z in park:
        k.tube((x, y, -SKIRT), (x, y, z), 0.22, B_CONC, sides=8)


def tel_terminal(k):
    # the Thani Terminal (Legends: Thani's spaceport): a glazed terminal hall vaulted over a podium, three round
    # docking bays on its landing side joined to it by covered gangways, a shuttle in the middle bay, a control
    # tower with a bulging cab, a comm mast. ~12 across
    tbox(k, 0.0, -0.6, -SKIRT, 0.6, 3.4, 1.6, 0.0, B_CONC_WIN, B_DUST)
    vault(k, 0.0, -0.6, 0.6, 0.0, 6.2, 1.5, 1.8, [B_PLATE_WIN, B_GLOW, B_PLATE, B_PLATE, B_GLOW, B_PLATE_WIN], end=B_CONC_WIN)
    for x, y in ((-3.4, 2.8), (0.0, 3.3), (3.4, 2.8)):
        k.lathe([(1.35, -SKIRT), (1.35, 0.45), (1.5, 0.55)], [B_CONC, B_RUST], sides=16, cx=x, cy=y, cap=B_PAD)
        sweep(k, [(x * 0.5, 0.6, 0.9), (x * 0.92, y - 1.2, 0.9)], rect_section(0.4, 0.35), B_PLATE_WIN, caps=B_HULL)
    shuttle(k, 0.0, 3.3, 0.55, 0.0, 2.2, B_HULL, B_PLATE_WIN)
    k.lathe([(0.5, -SKIRT), (0.4, 4.5), (0.95, 4.8), (0.95, 5.3), (0.6, 5.55)], [B_PLATE, B_RUST, B_CONC_WIN, B_ROOF],
            sides=12, cx=4.4, cy=-2.0, cap=B_ROOF)                                              # control tower
    k.lathe([(0.08, 5.5), (0.04, 7.2), (0.0, 7.4)], [B_HULL, B_GLOW], sides=5, cx=4.4, cy=-2.0)
    k.lathe([(0.1, 0.0), (0.06, 4.0), (0.0, 4.3)], [B_HULL, B_RUST], sides=5, cx=-4.4, cy=-2.2)  # comm mast
    tbox(k, -4.4, -2.2, 3.2, 3.8, 0.5, 0.04, 0.4, B_RUST, B_RUST)


def tel_academy(k):
    # the Telos Polar Academy (Legends: Atris's Telosian Jedi Academy hidden in the polar ice, its council chamber
    # laid out like the Jedi Council's on Coruscant): a ridge of ice, a domed entrance hall half sunk in it on the
    # south, the round council tower rising from the ice with its ring of tall windows and orange bands, a hangar door
    # cut into the ice on the west, a landing pad, a comm mast. ~11 across
    import random
    rng = random.Random("tel_academy")
    rock(k, 0.6, 1.2, -SKIRT, 2.4, 4.6, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3)                # the ice
    k.lathe([(1.6, -SKIRT), (1.6, 0.4)], B_PLATE_WIN, sides=20, cx=0.0, cy=-2.6)                # the entrance hall
    dome(k, 0.0, -2.6, 0.4, 1.6, 1.1, [B_PLATE, B_PLATE, B_CONC_WIN, B_PLATE], sides=20)
    k.lathe([(1.0, -SKIRT), (1.0, 4.2), (1.3, 4.4), (1.3, 5.4), (1.05, 5.6), (0.0, 6.1)],
            [B_PLATE, B_RUST, B_CONC_WIN, B_RUST, B_ROOF], sides=12, cx=0.6, cy=1.0)            # the council tower
    k.lathe([(0.06, 6.0), (0.03, 7.4), (0.0, 7.6)], [B_HULL, B_GLOW], sides=5, cx=0.6, cy=1.0)
    tbox(k, -3.0, 0.4, -SKIRT, 1.3, 0.25, 1.1, 0.2, B_DARK, B_SOOT)                             # the hangar door
    pad(k, 3.4, -2.4, 0.35, 1.2, B_HULL, B_PAD)
    k.lathe([(0.9, -SKIRT), (0.9, 0.2)], B_PLATE, sides=12, cx=3.4, cy=-2.4)


def tel_caverns(k):
    # the Mirror Caverns (canon: caves in a forest glade high in the snow-capped stone mountains, lined with malab, a
    # rare lustrous black mineral): a grey stone crag capped with snow, two cave mouths in its south face showing the
    # black malab inside, black malab shards breaking out of the rock, a stone path out of the main mouth. ~9 across
    import random
    rng = random.Random("tel_caverns")
    rock(k, 0.0, 0.8, -SKIRT, 3.6, 3.4, rng, [B_CONC, B_HULL, B_CONC], lobes=4)
    rock(k, 0.2, 1.0, 2.6, 4.6, 1.8, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3)                    # the snow cap
    vault(k, -0.5, -2.2, 0.0, 0.0, 1.4, 1.0, 1.5, [B_BRICK] * 8, n=2, end=B_DARK)               # the cave mouths
    vault(k, 1.9, -1.4, 0.4, 0.6, 1.0, 0.6, 0.9, [B_BRICK] * 8, n=2, end=B_DARK)
    for _ in range(7):                                                                          # malab shards
        a, d = rng.uniform(math.pi, TAU), rng.uniform(2.2, 3.6)
        x, y = d * math.cos(a), 0.8 + d * math.sin(a)
        k.tube((x, y, -0.5), (x + rng.uniform(-0.4, 0.4), y + rng.uniform(-0.4, 0.4), rng.uniform(0.8, 2.2)),
               rng.uniform(0.18, 0.3), B_BRICK, sides=5, r1=0.02)
    sweep(k, [(-0.5, -2.9, 0.02), (-1.0, -4.0, 0.02), (-0.4, -5.0, 0.02)],
          [(0.35, -SKIRT), (0.35, 0.08), (-0.35, 0.08), (-0.35, -SKIRT)], [B_DUST, B_DUST, B_DUST], open_sec=True)


def tel_rz(k):
    # RZ-0031 (canon: the first Restoration Zone, held in by force-field generators against the corrosive atmosphere
    # outside; an air defense tower stood in it; the Ithorians' encampment of warehouses, processing plants and a
    # landing pad; kept by the city as a reserve, a design choice): an arc of the restoration shield wall with its
    # generator pylons, the Ithorians' glass greenhouse vault, their domed station, the air defense tower with twin
    # barrels, a pad with a shuttle. ~12 across
    sweep(k, arc_path(0.0, 0.0, 0.0, 5.0, -0.5, 2.3, 14), [(0.25, -SKIRT), (0.25, 1.3), (-0.25, 1.3), (-0.25, -SKIRT)],
          [B_HULL, B_RUST, B_HULL], open_sec=True)                                             # the shield wall
    for i, (x, y, _z) in enumerate(arc_path(0.0, 0.0, 0.0, 5.0, -0.5, 2.3, 7)):
        k.lathe([(0.32, -SKIRT), (0.26, 3.2), (0.4, 3.4), (0.0, 3.8)], [B_HULL, B_RUST, B_GLOW], sides=8, cx=x, cy=y)
    tbox(k, -0.8, -0.4, -SKIRT, 0.3, 2.2, 1.5, 0.3, B_CONC_WIN, B_DUST)
    vault(k, -0.8, -0.4, 0.3, 0.3, 4.0, 1.4, 1.6, [B_PLATE_WIN, B_GLOW, B_PLATE_WIN, B_PLATE_WIN, B_GLOW, B_PLATE_WIN],
          end=B_PLATE)                                                                          # the greenhouse
    k.lathe([(1.2, -SKIRT), (1.2, 0.8)], B_PLATE_WIN, sides=16, cx=1.6, cy=1.8)                 # the Ithorian station
    dome(k, 1.6, 1.8, 0.8, 1.2, 1.1, [B_PLATE, B_ROOF, B_ROOF, B_PLATE], sides=16)
    k.lathe([(0.6, -SKIRT), (0.35, 3.8), (0.75, 4.0), (0.75, 4.6), (0.4, 4.8)], [B_PLATE, B_RUST, B_CONC_WIN, B_ROOF],
            sides=10, cx=-2.6, cy=2.4, cap=B_ROOF)                                             # air defense tower
    for s_ in (-0.2, 0.2):
        k.tube((-2.6 + s_, 2.4, 4.4), (-2.6 + s_ + 0.4, 2.4 - 1.6, 5.4), 0.08, B_HULL, sides=5)
    pad(k, -3.0, -2.6, 0.35, 1.1, B_HULL, B_PAD)
    k.lathe([(0.8, -SKIRT), (0.8, 0.2)], B_CONC, sides=12, cx=-3.0, cy=-2.6)
    shuttle(k, -3.0, -2.6, 0.35, 0.8, 1.6, B_HULL, B_PLATE_WIN)


# ==================================================================================================== SERENNO
# Serenno (canon: Count Dooku's homeworld of old forests; Carannia the capital with the domed Great Assembly House;
# Castle Serenno on a cliff edge over Serenno City; Borgin Castle; the Spike, an inverted-cone prison sunk in the
# rocky Aparian Wastes. Tales of the Jedi's Serenno: tall pale-stone palaces, steep slate spires, gold-lit arched
# windows among autumn-gold forests; The Clone Wars' Castle Serenno: an angular hall with battered walls, needle
# towers, a round landing platform jutting from the cliff). Atlas hod_serenno (B_ layout): B_PLATE pale ashlar,
# B_PLATE_WIN ashlar with gold-lit arched windows, B_CONC grey granite, B_CONC_WIN prison cell rows, B_RUST gold
# trim, B_ROOF dark slate, B_SOOT cliff rock, B_BRICK red-brown wastes rock, B_HULL Separatist tan hull.

def ser_spire(k, x, y, z0, h, r, rng, lite=False, sides=8):
    """a Serenno tower: an octagonal ashlar shaft (window storeys recessed on landmarks, painted on city cells: lite),
    a gold ledge, a steep slate spire with a gold finial"""
    g = max(z0, 0.0)
    shaft = g + (h - g) * rng.uniform(0.6, 0.7)
    if lite:
        k.lathe([(r, z0), (r, shaft)], B_PLATE_WIN, sides=sides, cx=x, cy=y)
    else:
        banded(k, lambda zz, grow: ring(x, y, zz, r + grow, sides, rot=TAU / sides / 2), z0, shaft,
               max(2, int((shaft - g) / 0.9)), B_PLATE, B_PLATE_WIN, inset=r * 0.08)
    k.lathe([(r * 1.14, shaft), (r * 1.14, shaft + r * 0.25), (r * 0.96, shaft + r * 0.3), (0.0, h)],
            [B_RUST, B_RUST, B_ROOF], sides=sides, cx=x, cy=y, cap=B_RUST)
    k.lathe([(r * 0.08, h - 0.02), (0.0, h + (h - g) * 0.1)], B_RUST, sides=4, cx=x, cy=y)


def ser_hall(k, x, y, z0, h, w, d, a, roof=0.65, wall=B_PLATE_WIN):
    """a steep-roofed ashlar hall (half sizes w, d along heading a): window walls, a slate gable roof, stone gables"""
    tbox(k, x, y, z0, h, w, d, a, wall, B_ROOF)
    prism_at(k, x, y, h, a, 2 * w * 1.04, [(d * 1.08, 0.0), (0.0, d * roof * 2), (-d * 1.08, 0.0)],
             [B_ROOF, B_ROOF, B_ROOF], end=B_PLATE)


def ser_city(k, band, rng):
    # Serenno's towns (Carannia, Serenno City, Saffia, Fiyaro): curving gravel streets lined with steep-roofed ashlar
    # manors, slender slate-spired towers rising between, a gold-ribbed dome downtown. band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.35)
    for p in paths:
        sweep(k, p, rect_section(0.12 + 0.02 * band, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.16 + 0.02 * band)
    for _ in range(band * 2 + 4):                                                  # manors along the streets
        w = rng.uniform(0.1, 0.16)
        p_ = lots.along(rng.choice(paths), w * 1.2, 0.09) or lots.spot(w * 1.2)
        if not p_:
            continue
        p_ = p_ if len(p_) > 2 else p_ + (rng.uniform(0, math.pi),)
        h = rng.uniform(0.12, 0.2) + 0.06 * band
        ser_hall(k, p_[0], p_[1], CELL_Z, h, w, w * rng.uniform(0.45, 0.6), p_[2])
        if rng.random() < 0.3 + 0.12 * band:                                      # a corner tower
            cx, cy = turn(p_[0], p_[1], p_[2], w, w * 0.5)
            ser_spire(k, cx, cy, CELL_Z, h + rng.uniform(0.25, 0.45) + 0.1 * band, w * 0.3, rng, lite=True)
    for _ in range(band - 1):                                                      # tall towers
        r = rng.uniform(0.06, 0.09) + 0.01 * band
        p_ = lots.spot(r * 1.6)
        if p_:
            ser_spire(k, p_[0], p_[1], CELL_Z, rng.uniform(0.7, 1.1) + 0.3 * band, r, rng, lite=True)
    p_ = lots.spot(0.22) if band >= 3 else None
    if p_:                                                                         # a gold-ribbed dome
        k.lathe([(0.2, CELL_Z), (0.2, 0.35)], B_PLATE_WIN, sides=12, cx=p_[0], cy=p_[1])
        dome(k, p_[0], p_[1], 0.35, 0.2, 0.22, [B_ROOF, B_RUST, B_ROOF, B_RUST], sides=12)


def ser_carannia(k):
    # Carannia, the capital (canon; the look after Tales of the Jedi's Serenno): a terraced civic podium, three long
    # steep-roofed palaces round a court, five slate-spired towers (the tallest the Count's city palace), an arched
    # gate between two towers onto the court, a pad with a shuttle by the Trannon side. ~14 across
    import random
    rng = random.Random("ser_carannia")
    plaza = lobed(0.0, 0.0, 0.0, 5.2, lobes=3, amp=0.16, n=30, phase=0.9, sy=0.78)
    loft(k, [at_z(plaza, -SKIRT), at_z(plaza, 0.45), scaled(at_z(plaza, 0.6), 0.97)], [B_CONC, B_CONC], cap=B_DUST)
    terrace = lobed(0.6, 0.9, 0.6, 2.8, lobes=4, amp=0.12, n=24, phase=0.3, sy=0.8)
    loft(k, [at_z(terrace, 0.0), at_z(terrace, 1.1)], B_PLATE, cap=B_DUST)
    for x, y, h, w, d, a in ((0.6, 2.6, 3.0, 2.6, 0.75, 0.0), (-1.6, 0.6, 2.6, 1.9, 0.65, 1.57), (2.9, 0.6, 2.4, 1.8, 0.6, 1.57)):
        ser_hall(k, x, y, 1.1 if abs(x) < 2.5 and y > 2 else 0.6, h + 1.1, w, d, a, wall=B_PLATE_WIN)
    for x, y, h, r in ((0.6, 3.6, 12.5, 0.85), (-2.6, 2.4, 9.0, 0.7), (3.6, 2.6, 8.5, 0.65), (-3.4, -1.6, 7.0, 0.6),
                       (4.0, -1.4, 6.5, 0.55)):
        ser_spire(k, x, y, -SKIRT, h, r, rng)
    for x in (-0.7, 1.9):                                                          # the gate onto the court
        ser_spire(k, x, -1.9, -SKIRT, 4.2, 0.42, rng)
    curve_tube(k, (-0.7, -1.9, 2.4), (1.9, -1.9, 2.4), 0.9, 0.28, 0.28, B_PLATE, n=8)
    pad(k, -4.0, 0.9, 0.7, 1.0, B_RUST, B_PAD)
    k.lathe([(0.7, -SKIRT), (0.7, 0.55)], B_CONC, sides=12, cx=-4.0, cy=0.9)
    shuttle(k, -4.0, 0.9, 0.7, 0.5, 1.5, B_HULL, B_CONC_WIN)


def ser_assembly(k):
    # the Great Assembly House (canon: the imposing domed seat of Serenno's Planetary Council in Carannia): a broad
    # octagonal drum of arched window storeys on a stepped base, a great slate dome ribbed in gold under a lantern,
    # four corner pavilions with their own domes, a columned portico and steps on the south. ~12 across
    import random
    rng = random.Random("ser_assembly")
    tbox(k, 0.0, 0.0, -SKIRT, 0.5, 4.4, 4.0, 0.0, B_CONC, B_DUST)
    tbox(k, 0.0, 0.0, 0.5, 0.9, 3.8, 3.5, 0.0, B_PLATE, B_DUST)
    banded(k, lambda zz, grow: ring(0.0, 0.3, zz, 2.6 + grow, 8, rot=TAU / 16), 0.9, 3.6, 3, B_PLATE, B_PLATE_WIN,
           inset=0.12)
    k.lathe([(2.8, 3.6), (2.8, 3.9), (2.6, 4.0)], [B_RUST, B_RUST], sides=16, cx=0.0, cy=0.3, cap=B_RUST)
    dome(k, 0.0, 0.3, 4.0, 2.55, 2.4, [B_ROOF, B_ROOF, B_ROOF, B_ROOF], sides=24, cap_r=0.45)
    for i in range(12):                                                            # the gold ribs
        t = TAU * i / 12
        pts = [(math.cos(t) * 2.6 * math.cos(math.pi / 2 * j / 6), 0.3 + math.sin(t) * 2.6 * math.cos(math.pi / 2 * j / 6),
                4.0 + 2.45 * math.sin(math.pi / 2 * j / 6)) for j in range(6)]
        for p0, p1 in zip(pts, pts[1:]):
            k.tube(p0, p1, 0.07, B_RUST, sides=4)
    k.lathe([(0.45, 6.4), (0.45, 7.0), (0.55, 7.05), (0.0, 7.7)], [B_PLATE_WIN, B_RUST, B_RUST], sides=8, cx=0.0, cy=0.3)
    for x, y in ((-3.2, -2.8), (3.2, -2.8), (-3.2, 3.0), (3.2, 3.0)):             # corner pavilions
        k.lathe([(0.75, 0.5), (0.75, 2.4)], B_PLATE_WIN, sides=8, cx=x, cy=y, cap=B_ROOF)
        dome(k, x, y, 2.4, 0.8, 0.8, [B_ROOF, B_RUST, B_ROOF, B_ROOF], sides=12)
    tbox(k, 0.0, -3.0, 0.5, 2.6, 1.5, 0.7, 0.0, B_PLATE, B_ROOF)                   # the portico
    prism_at(k, 0.0, -3.3, 2.6, 0.0, 3.2, [(1.0, 0.0), (0.0, 0.8), (-1.0, 0.0)], [B_ROOF, B_ROOF, B_ROOF], end=B_PLATE)
    for i in range(6):
        x = -1.25 + 0.5 * i
        k.lathe([(0.13, 0.5), (0.11, 2.55)], B_PLATE, sides=8, cx=x, cy=-3.95)
    for i in range(4):                                                             # the steps
        tbox(k, 0.0, -4.4 - 0.3 * i, -SKIRT, 0.5 - 0.12 * i, 1.8 - 0.05 * i, 0.16, 0.0, B_CONC, B_DUST)


def ser_castle(k):
    # Castle Serenno (canon, The Clone Wars: Dooku's palace on the edge of a cliff over the valley of Serenno City):
    # the cliff top of grey rock, the great hall with battered walls and a steep slate roof, a tall keep, three needle
    # towers along the cliff edge, a long wing, the round landing platform jutting out over the drop on a sloping
    # strut. ~13 across
    import random
    rng = random.Random("ser_castle")
    rock(k, 0.0, 0.8, -SKIRT, 1.0, 5.6, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.75)
    tbox(k, 0.0, 0.8, 0.6, 4.2, 2.4, 1.3, 0.1, B_PLATE_WIN, B_ROOF, wt=2.2, dt=1.1)                   # the great hall
    prism_at(k, 0.0, 0.8, 4.2, 0.1, 4.6, [(1.2, 0.0), (0.0, 2.2), (-1.2, 0.0)], [B_ROOF, B_ROOF, B_ROOF], end=B_PLATE)
    tbox(k, -2.8, 1.6, 0.6, 7.0, 1.0, 1.0, 0.1, B_PLATE_WIN, B_ROOF, wt=0.85, dt=0.85)               # the keep
    k.lathe([(1.25, 7.0), (0.0, 9.8)], B_ROOF, sides=4, cx=-2.8, cy=1.6, rot=0.1 + math.pi / 4, cap=B_RUST)
    ser_hall(k, 3.4, 1.9, 0.6, 2.8, 1.6, 0.7, 1.67)                                                   # the wing
    for x, y, h, r in ((-1.4, -1.1, 9.5, 0.42), (1.2, -1.2, 8.0, 0.38), (3.4, -0.4, 6.5, 0.34), (-3.8, -0.3, 7.5, 0.36)):
        ser_spire(k, x, y, -SKIRT, h, r, rng)
    k.lathe([(1.7, 2.3), (1.85, 2.45), (1.85, 2.6)], [B_HULL, B_RUST], sides=20, cx=0.4, cy=-4.4, cap=B_PAD)   # platform
    k.tube((0.4, -4.4, 2.2), (0.4, -1.4, -0.6), 0.32, B_PLATE, sides=8)
    sweep(k, [(0.4, -2.7, 2.5), (0.4, -0.9, 2.5)], rect_section(0.6, 0.15), B_DUST, caps=B_DUST)       # its causeway


def ser_borgin(k):
    # Borgin Castle (canon, nothing more told: drawn as a hill castle of the Serenno houses): a curtain wall on a
    # ragged hill-top ring with round towers under conical slate roofs, a gatehouse, a square keep with a steep roof
    # and a corner spire, a hall along the inner wall. ~10 across
    import random
    rng = random.Random("ser_borgin")
    rock(k, 0.0, 0.0, -SKIRT, 0.6, 4.6, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4)
    wall = lobed(0.0, 0.0, 0.0, 3.6, lobes=5, amp=0.1, n=10, phase=0.4, sy=0.85)
    sweep(k, [(x, y, 0.4) for x, y, _z in wall], trap_section(0.6, 0.45, 1.6, -0.6), B_CONC, closed_path=True)
    for x, y, _z in wall[::2]:
        k.lathe([(0.55, -0.6), (0.5, 2.3)], B_CONC, sides=10, cx=x, cy=y, cap=B_ROOF)
        k.lathe([(0.62, 2.3), (0.0, 3.6)], B_ROOF, sides=10, cx=x, cy=y, cap=B_RUST)
    gx, gy, _z = wall[7]
    tbox(k, gx, gy, -0.6, 2.4, 0.6, 0.7, math.atan2(gy, gx), B_PLATE_WIN, B_ROOF)                      # gatehouse
    tbox(k, 0.4, 0.4, 0.4, 4.6, 1.1, 1.1, 0.2, B_PLATE_WIN, B_ROOF)                                    # the keep
    k.lathe([(1.55, 4.6), (0.0, 6.8)], B_ROOF, sides=4, cx=0.4, cy=0.4, rot=0.2 + math.pi / 4, cap=B_RUST)
    ser_spire(k, 1.4, 1.4, 0.4, 7.4, 0.3, rng)
    ser_hall(k, -1.3, -1.2, 0.4, 2.0, 1.3, 0.6, 0.6)


def ser_spike(k):
    # the Spike (canon: an underground, inverted-cone prison the Confederacy built in the rocky Aparian Wastes just
    # before the war; the user, 2026-10-19: a fortress over the pit, the cone mostly hidden): an octagonal Separatist
    # rampart with gun towers on four corners, a raised courtyard with the pit's mouth in it showing the cone's top
    # cell rows, the tall six-sided spike of the shaft-head rising out of the pit with lit slits, bridges to it from
    # the rampart, a gatehouse, a pad with a shuttle outside. ~13 across
    import random
    rng = random.Random("ser_spike")
    oct_ = [(5.0 * math.cos(TAU * i / 8 + TAU / 16), 5.0 * math.sin(TAU * i / 8 + TAU / 16), 0.0) for i in range(8)]
    sweep(k, oct_, trap_section(1.8, 1.0, 1.9 + SKIRT, -SKIRT), [B_HULL, B_HULL, B_DUST, B_HULL], closed_path=True)
    prof = [(4.6, 1.2), (3.1, 1.2), (3.1, 0.85), (2.7, 0.85), (2.7, 0.5), (2.3, 0.5), (2.3, 0.15), (1.0, 0.15)]
    k.lathe(prof, [B_DUST, B_CONC_WIN, B_CONC, B_CONC_WIN, B_CONC, B_CONC_WIN, B_DARK], sides=24)   # courtyard, pit
    k.lathe([(1.15, -SKIRT), (1.15, 0.6), (0.95, 3.4), (1.35, 3.7), (1.35, 4.5), (0.9, 4.9), (0.75, 7.2), (0.55, 7.5),
             (0.0, 10.5)], [B_HULL, B_HULL, B_RUST, B_CONC_WIN, B_RUST, B_HULL, B_GLOW, B_HULL], sides=6, rot=0.26)
    for i in range(4):                                                         # gun towers and bridges
        x, y, _z = oct_[2 * i]
        a = math.atan2(y, x)
        tbox(k, x, y, -SKIRT, 3.4, 0.95, 0.95, a, B_HULL, B_ROOF, wt=0.65, dt=0.65)
        dome(k, x, y, 3.4, 0.6, 0.45, [B_HULL, B_HULL, B_ROOF, B_ROOF], sides=8)
        for s_ in (-0.15, 0.15):
            k.tube((x + s_ * math.sin(a), y - s_ * math.cos(a), 3.6),
                   (x + 1.5 * math.cos(a) + s_ * math.sin(a), y + 1.5 * math.sin(a) - s_ * math.cos(a), 4.2), 0.07, B_DARK,
                   sides=5)
        bx, by = math.cos(a + TAU / 16), math.sin(a + TAU / 16)
        sweep(k, [(bx * 4.4, by * 4.4, 1.9), (bx * 1.1, by * 1.1, 2.6)], rect_section(0.45, 0.2), B_HULL, caps=B_HULL)
    tbox(k, 0.0, -5.1, -SKIRT, 2.6, 1.1, 0.8, 0.0, B_HULL, B_ROOF, wt=0.9, dt=0.6)            # the gatehouse
    tbox(k, 0.0, -5.95, -SKIRT, 1.2, 0.5, 0.06, 0.0, B_DARK, B_DARK)
    pad(k, -4.6, -6.6, 0.45, 1.2, B_HULL, B_PAD)
    k.lathe([(0.9, -SKIRT), (0.9, 0.3)], B_HULL, sides=12, cx=-4.6, cy=-6.6)
    shuttle(k, -4.6, -6.6, 0.45, 0.6, 1.8, B_HULL, B_CONC_WIN)
    for _ in range(6):                                                         # wastes rocks
        a, d = rng.uniform(0, TAU), rng.uniform(6.2, 7.2)
        rock(k, d * math.cos(a), d * math.sin(a), -SKIRT, rng.uniform(0.6, 1.4), rng.uniform(0.5, 0.9), rng,
             [B_BRICK] * 3, lobes=3)


# ==================================================================================================== YAVIN IV
# Yavin IV (canon: the Great Temple of the Massassi, a vast stepped ziggurat of grey stone rising over the jungle
# canopy with a great opening at its foot (A New Hope, Rogue One); Legends: the Temple of Exar Kun, a dark stepped
# pyramid crowned by a tall obelisk; Borundi Peak, an inactive volcano). User: a wild moon, the ruins are the
# landmarks. Atlas hod_yavin (B_ layout): B_PLATE Massassi stone blocks, B_PLATE_WIN stone with dark openings,
# B_CONC weathered stone, B_CONC_WIN black Sith stone, B_RUST moss, B_ROOF mossy stone tops, B_SOOT volcanic rock,
# B_BRICK jungle vines, B_GLOW the Sith-red glow (painted bright: the map is always day), B_DUST jungle earth.

def yav_steps(k, x, y, z0, tiers, w, d, h, shrink, a, wall, top, batter=0.94):
    """a stepped pyramid: `tiers` battered blocks, each `shrink` of the one under it; returns the top height"""
    z = z0
    for t in range(tiers):
        z1 = (max(z, 0.0) if t else 0.0) + h
        tbox(k, x, y, z, z1, w, d, a, wall if t else B_PLATE, top, wt=w * batter, dt=d * batter)
        z, w, d = z1, w * shrink, d * shrink
    return z, w / shrink, d / shrink


def yav_temple(k):
    # the Great Temple of the Massassi (canon; the later rebel Base One): a broad stepped ziggurat in grey stone, its
    # tall upper block with dark window slots and a flat top, the great dark opening of the hangar at its foot under a
    # stone lintel, low stepped side wings, a stair climbing the east face; moss in the stone texture. ~16 across
    z, w, d = yav_steps(k, 0.0, 0.0, -SKIRT, 3, 6.4, 5.4, 2.0, 0.8, 0.0, B_PLATE, B_ROOF)
    tbox(k, 0.0, 0.3, z, z + 3.0, w * 0.72, d * 0.72, 0.0, B_PLATE_WIN, B_ROOF, wt=w * 0.66, dt=d * 0.66)   # upper block
    tbox(k, 0.0, 0.3, z + 3.0, z + 3.5, w * 0.7, d * 0.7, 0.0, B_CONC, B_ROOF, wt=w * 0.62, dt=d * 0.62)
    tbox(k, 0.0, -5.45, -SKIRT, 1.5, 2.2, 0.2, 0.0, B_DARK, B_DARK)                                  # the hangar mouth
    tbox(k, 0.0, -5.6, 1.5, 2.1, 2.6, 0.3, 0.0, B_CONC, B_ROOF)                                      # its lintel
    for s_ in (-1, 1):                                                                               # side wings
        yav_steps(k, s_ * 7.6, -0.8, -SKIRT, 2, 1.6, 3.4, 1.1, 0.8, 0.0, B_PLATE, B_ROOF)
    sweep(k, [(6.6, 2.6, 0.0), (4.6, 2.6, 4.2)], rect_section(1.2, 0.2, -0.2), [B_CONC, B_DUST, B_CONC, B_CONC],
          caps=B_CONC)                                                                               # the east stair


def yav_exarkun(k):
    # the Temple of Exar Kun (Legends: the Sith Lord's temple raised by the Massassi in the jungle): a narrow dark
    # stepped pyramid in black stone, a tall tapering obelisk on its top with a red-lit slot, two lesser obelisks on
    # the approach, a causeway of grey stone running up to its door. ~11 across
    z, w, d = yav_steps(k, 0.0, 0.0, -SKIRT, 5, 3.6, 3.6, 1.15, 0.78, 0.0, B_CONC_WIN, B_CONC, batter=0.9)
    tbox(k, 0.0, 0.0, z, z + 5.2, w * 0.45, d * 0.45, 0.0, B_CONC_WIN, B_CONC_WIN, wt=w * 0.12, dt=d * 0.12)   # obelisk
    tbox(k, 0.0, -d * 0.4, z + 1.6, z + 2.6, w * 0.1, 0.06, 0.0, B_GLOW, B_GLOW)
    tbox(k, 0.0, -3.7, -SKIRT, 1.6, 0.8, 0.3, 0.0, B_DARK, B_CONC)                                   # the door
    for x in (-2.2, 2.2):
        tbox(k, x, -5.6, -SKIRT, 3.8, 0.35, 0.35, 0.0, B_CONC_WIN, B_CONC_WIN, wt=0.06, dt=0.06)
    sweep(k, [(0.0, -7.6, 0.25), (0.0, -3.9, 0.25)], [(0.9, -SKIRT), (0.9, 0.0), (-0.9, 0.0), (-0.9, -SKIRT)],
          [B_PLATE, B_CONC, B_PLATE], open_sec=True)


def yav_borundi(k):
    # Borundi Peak (Legends: an inactive volcano on Yavin IV): a ragged cone of dark volcanic rock streaked grey, the
    # caldera rim, a crater dropping inside, old lava spurs breaking the flanks, a Massassi shrine of stepped stone with
    # its stair on the southern flank. ~14 across
    import random
    rng = random.Random("yav_borundi")
    ph = rng.uniform(0, TAU)
    up = [(-SKIRT, 6.8), (0.8, 5.6), (2.4, 4.2), (4.0, 3.0), (5.4, 2.1), (6.4, 1.8)]
    rings = [lobed(0.0, 0.0, z, r, 5, 0.12 + 0.02 * i, 40, ph + 0.5 * i, 0.9, amp2=0.1) for i, (z, r) in enumerate(up)]
    rings += [lobed(0.0, 0.0, z, r, 5, 0.1, 40, ph + 2.5, 0.9) for z, r in ((6.1, 1.3), (5.2, 0.6))]   # the crater
    loft(k, rings, [B_SOOT, B_SOOT, B_CONC, B_SOOT, B_SOOT, B_DARK, B_DARK], cap=B_DARK)
    for _ in range(5):                                                                               # lava spurs
        a = rng.uniform(0, TAU)
        rock(k, math.cos(a) * 5.4, math.sin(a) * 4.8, -SKIRT, rng.uniform(1.0, 2.0), rng.uniform(1.0, 1.6), rng,
             [B_SOOT] * 3, lobes=3)
    zs, _w, _d = yav_steps(k, 0.6, -6.2, -SKIRT, 3, 1.4, 1.1, 0.9, 0.75, 0.15, B_PLATE, B_ROOF)    # the shrine
    sweep(k, [(0.6, -7.6, 0.0), (0.6, -6.6, zs - 0.4)], rect_section(0.6, 0.15, -0.15), [B_CONC, B_DUST, B_CONC, B_CONC],
          caps=B_CONC)


# ==================================================================================================== CELANON
# Celanon (Legends: a trade world ruled by merchant guilds; Celanon City a sprawl of two hundred square kilometres; the
# spaceport's Control tower of nearly 140 storeys; the Merchant Guild Medical Facility; Gularg the Hutt's tavern; tribal
# country beyond the city). Architecture is not described: a design choice, a guild city of cream towers crowned with
# verdigris domes over striped market arcades; Hutt adobe for Gularg's; thatched round huts for the tribes.
# Atlas hod_celanon (B_ layout): B_PLATE cream render, B_PLATE_WIN window bands, B_RUST verdigris copper, B_ROOF
# terracotta, B_HAZARD market awning stripes, B_SOOT thatch, B_BRICK Hutt adobe, B_GIRDER palisade logs.

def cel_tower(k, x, y, z0, h, r, rng, lite=False, sides=8):
    """a guild tower: an octagonal shaft (recessed storeys on landmarks, painted on city cells), a cornice, a
    verdigris onion crown and a spike"""
    g = max(z0, 0.0)
    shaft = g + (h - g) * 0.8
    if lite:
        k.lathe([(r, z0), (r, shaft)], B_PLATE_WIN, sides=sides, cx=x, cy=y)
    else:
        banded(k, lambda zz, grow: ring(x, y, zz, r + grow, sides), z0, shaft, max(2, int((shaft - g) / 0.8)),
               B_PLATE, B_PLATE_WIN, inset=r * 0.08)
    c = h - shaft
    k.lathe([(r * 1.12, shaft), (r * 1.12, shaft + c * 0.12), (r * 1.0, shaft + c * 0.2), (r * 1.15, shaft + c * 0.45),
             (r * 0.5, shaft + c * 0.85), (0.0, h)], [B_PLATE, B_PLATE, B_RUST, B_RUST, B_RUST], sides=sides, cx=x, cy=y,
            cap=B_PLATE)
    k.lathe([(r * 0.06, h - 0.02), (0.0, h + c * 0.6)], B_RUST, sides=4, cx=x, cy=y)


def cel_arcade(k, path, w, h, base=CELL_Z):
    """a market arcade along a street: a low terracotta-roofed block with a striped awning over the street side"""
    sweep(k, path, [(w, base), (w, h), (0.0, h + w * 0.5), (-w, h), (-w, base)], [B_PLATE_WIN, B_ROOF, B_ROOF, B_PLATE_WIN],
          caps=B_PLATE, open_sec=True)
    sweep(k, offset_path(path, w + 0.04), [(0.06, h * 0.55), (0.0, h * 0.75), (-0.06, h * 0.75)], B_HAZARD, open_sec=True)


def cel_city(k, band, rng):
    # Celanon City and the Cekbar towns: winding streets lined with market arcades, guild towers with verdigris
    # crowns rising behind them, a domed guild hall downtown. band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.3)
    for p in paths:
        sweep(k, p, rect_section(0.12 + 0.02 * band, 0.315, CELL_Z), [B_CONC, B_DUST, B_CONC], open_sec=True)
        lots.block_path(p, 0.16 + 0.02 * band)
        if rng.random() < 0.5 + 0.12 * band:                                       # an arcade along one side
            side = offset_path(sub_path(p, 0.15 * path_len(p), 0.85 * path_len(p)), (0.14 + 0.02 * band) * rng.choice((-1, 1)))
            cel_arcade(k, side, 0.06, 0.08 + 0.02 * band)
            lots.block_path(side, 0.16)
    for _ in range(band + 2):                                                      # guild towers
        r = rng.uniform(0.06, 0.09) + 0.008 * band
        p_ = lots.along(rng.choice(paths), r * 1.4, 0.12) or lots.spot(r * 1.5)
        if p_:
            cel_tower(k, p_[0], p_[1], CELL_Z, rng.uniform(0.35, 0.6) + 0.3 * band, r, rng, lite=True)
    for _ in range(4 - band // 2):                                                 # houses
        w = rng.uniform(0.08, 0.13)
        p_ = lots.spot(w * 1.3)
        if p_:
            tbox(k, p_[0], p_[1], CELL_Z, rng.uniform(0.08, 0.16), w, w * 0.7, rng.uniform(0, math.pi), B_PLATE_WIN, B_ROOF)
    p_ = lots.spot(0.2) if band >= 3 else None
    if p_:                                                                         # a domed guild hall
        k.lathe([(0.18, CELL_Z), (0.18, 0.3)], B_PLATE_WIN, sides=10, cx=p_[0], cy=p_[1])
        dome(k, p_[0], p_[1], 0.3, 0.19, 0.2, [B_RUST, B_RUST, B_RUST, B_RUST], sides=10)


def cel_village(k, band, rng):
    # a tribal village of the rural continents: thatched round huts with conical roofs scattered round a trodden
    # yard, a longhouse, a palisade of logs along part of the edge, a watch post. band = how many huts
    lots = Lots(rng, 0.8)
    yard = lots.take(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0.18)
    for _ in range(3 + band):
        r = rng.uniform(0.07, 0.11)
        p_ = lots.spot(r * 1.3)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.07)], B_BRICK, sides=8, cx=p_[0], cy=p_[1])
            k.lathe([(r * 1.3, 0.06), (0.0, 0.07 + r * 1.6)], B_SOOT, sides=8, cx=p_[0], cy=p_[1], cap=B_SOOT)
    p_ = lots.spot(0.2)
    if p_:                                                                         # the longhouse
        a = rng.uniform(0, math.pi)
        tbox(k, p_[0], p_[1], CELL_Z, 0.06, 0.18, 0.08, a, B_BRICK, B_SOOT)
        prism_at(k, p_[0], p_[1], 0.06, a, 0.4, [(0.1, 0.0), (0.0, 0.12), (-0.1, 0.0)], [B_SOOT] * 3, end=B_BRICK)
    a0 = rng.uniform(0, TAU)                                                       # the palisade
    arc = arc_path(yard[0], yard[1], 0.0, 0.75, a0, a0 + rng.uniform(1.5, 2.6), 9)
    for x, y, _z in arc:
        k.tube((x, y, CELL_Z), (x + rng.uniform(-0.02, 0.02), y + rng.uniform(-0.02, 0.02), 0.16), 0.025, B_GIRDER, sides=4)
    x, y, _z = arc[len(arc) // 2]
    legs(k, x, y, CELL_Z, 0.3, 0.06, 0.04, 4, 0.012, B_GIRDER, braces=False)          # the watch post
    tbox(k, x, y, 0.3, 0.34, 0.07, 0.07, 0.0, B_GIRDER, B_GIRDER)
    k.lathe([(0.1, 0.34), (0.0, 0.46)], B_SOOT, sides=4, cx=x, cy=y)


def cel_city_centre(k):
    # Celanon City's heart (Legends: the guild-ruled hub of Outer Rim commerce): a broad paved plaza, the Merchant
    # Guild's tall tower with its great verdigris crown, five lesser guild towers round it, a domed exchange hall,
    # market arcades along the plaza's edges, a skybridge between two towers. ~13 across
    import random
    rng = random.Random("cel_city")
    plaza = lobed(0.0, 0.0, 0.0, 5.0, lobes=3, amp=0.15, n=30, phase=1.2, sy=0.82)
    loft(k, [at_z(plaza, -SKIRT), at_z(plaza, 0.4), scaled(at_z(plaza, 0.5), 0.97)], [B_CONC, B_CONC], cap=B_DUST)
    towers = [(0.4, 1.6, 12.0, 1.0), (-2.8, 1.8, 8.5, 0.7), (3.0, 2.2, 9.0, 0.75), (-3.4, -1.4, 7.0, 0.6),
              (3.6, -1.2, 6.5, 0.6), (-0.6, 3.6, 7.5, 0.6)]
    for x, y, h, r in towers:
        cel_tower(k, x, y, -SKIRT, h, r, rng)
    k.lathe([(1.4, 0.5), (1.4, 1.8)], B_PLATE_WIN, sides=16, cx=0.0, cy=-1.4)                    # the exchange
    dome(k, 0.0, -1.4, 1.8, 1.45, 1.3, [B_RUST, B_RUST, B_RUST, B_RUST], sides=16)
    k.lathe([(0.25, 3.05), (0.0, 3.6)], B_RUST, sides=6, cx=0.0, cy=-1.4)
    for path in ([(-4.2, -3.2, 0.5), (-1.8, -3.9, 0.5), (1.6, -3.9, 0.5), (4.0, -3.0, 0.5)],
                 [(-4.6, -0.2, 0.5), (-4.4, 2.4, 0.5)], [(4.6, 0.2, 0.5), (4.2, 2.8, 0.5)]):
        cel_arcade(k, path, 0.45, 1.1, base=-SKIRT)
    sweep(k, [(0.4, 1.6, 5.0), (-2.8, 1.8, 5.0)], rect_section(0.4, 0.3), B_PLATE_WIN, caps=B_PLATE)


def cel_control(k):
    # the Celanon Spaceport and Spaceport Control (Legends: a tower of nearly 140 storeys directing the routes of every
    # ship in orbit): the needle tower on a flared, buttressed foot, its broad control cab ringed with windows, comm
    # masts above; round landing bays round the foot, a freighter on one, a terminal hall. ~12 across, ~19 high
    import random
    rng = random.Random("cel_control")
    k.lathe([(2.0, -SKIRT), (1.9, 0.4), (1.1, 2.4), (0.75, 4.0)], [B_PLATE, B_PLATE, B_PLATE], sides=12)
    for i in range(4):
        fin(k, 0.0, 0.0, TAU * i / 4 + 0.4, [(1.9, 0.0), (1.2, 2.2), (0.76, 4.0), (0.62, 7.0)], 0.5, 0.25, B_PLATE)
    banded(k, lambda zz, grow: ring(0.0, 0.0, zz, 0.62 + grow, 12), 4.0, 14.0, 12, B_PLATE, B_PLATE_WIN, inset=0.05)
    k.lathe([(0.62, 14.0), (2.1, 14.6), (2.1, 15.6), (1.6, 16.1), (0.5, 16.4)], [B_PLATE, B_CONC_WIN, B_PLATE, B_RUST],
            sides=16, cap=B_RUST)                                                              # the control cab
    for a in (0.3, 2.4, 4.4):
        k.tube((0.3 * math.cos(a), 0.3 * math.sin(a), 16.3), (0.3 * math.cos(a), 0.3 * math.sin(a), 19.0 - a * 0.3),
               0.05, B_HULL, sides=4, r1=0.01)
    for i, (x, y) in enumerate(((-4.2, -2.0), (4.2, -2.2), (-3.6, 3.4), (3.8, 3.2))):         # landing bays
        k.lathe([(1.25, -SKIRT), (1.25, 0.4), (1.4, 0.5)], [B_CONC, B_RUST], sides=14, cx=x, cy=y, cap=B_PAD)
        if i == 1:
            shuttle(k, x, y, 0.5, 2.0, 2.2, B_HULL, B_CONC_WIN)
    tbox(k, 0.0, -4.0, -SKIRT, 1.0, 2.4, 0.8, 0.0, B_PLATE_WIN, B_ROOF)                     # the terminal hall
    vault(k, 0.0, -4.0, 1.0, 0.0, 4.6, 0.8, 0.7, [B_CONC_WIN] * 8, end=B_PLATE)


def cel_hospital(k):
    # the Celanon Merchant Guild Medical Facility (Legends: a hospital near the starport): white wards on an H plan
    # joined by a glazed atrium, window bands, a red-cross-free guild crown, a medevac pad on the roof. ~9 across
    for x in (-2.2, 2.2):
        banded(k, lambda zz, grow, x=x: rrect(x, 0.0, zz, 1.0 + grow, 2.8 + grow, 0.4, 0.0, 2), -SKIRT, 3.2, 4,
               B_PLATE, B_PLATE_WIN, inset=0.06, cap=B_ROOF)
    tbox(k, 0.0, 0.0, -SKIRT, 2.2, 1.3, 0.8, 0.0, B_CONC_WIN, B_CONC_WIN)                      # the atrium
    vault(k, 0.0, 0.0, 2.2, 0.0, 2.4, 0.8, 0.6, [B_CONC_WIN] * 8, end=B_CONC_WIN)
    pad(k, 2.2, 1.2, 3.35, 0.85, B_RUST, B_PAD)
    k.lathe([(0.3, 3.2), (0.3, 3.3)], B_PLATE, sides=8, cx=2.2, cy=1.2)
    cel_tower(k, -2.2, -1.8, 3.2, 5.6, 0.45, __import__("random").Random("cel_hospital"))


def cel_gularg(k):
    # Gularg's Libation Emporium (Legends: the Hutt's bar, the rowdiest and most dangerous in Celanon City): Hutt
    # adobe - a round tower with a bulbous domed top like a Hutt palace's, a low domed tavern hall beside it, a walled
    # yard with a gate, speeders out front. ~9 across
    k.lathe([(1.2, -SKIRT), (1.1, 3.4), (1.45, 3.9), (1.2, 4.6), (0.5, 5.1), (0.0, 5.2)],
            [B_BRICK, B_BRICK, B_BRICK, B_BRICK, B_BRICK], sides=16, cx=-1.6, cy=0.6)        # the tower
    k.lathe([(1.12, 2.4), (1.12, 2.6)], B_DARK, sides=16, cx=-1.6, cy=0.6)
    k.lathe([(2.0, -SKIRT), (2.0, 0.9)], B_BRICK, sides=16, cx=1.1, cy=0.2)                   # the hall
    dome(k, 1.1, 0.2, 0.9, 2.0, 1.4, [B_BRICK, B_BRICK, B_BRICK, B_BRICK], sides=16, sy=0.8)
    tbox(k, 1.1, -1.55, -SKIRT, 0.9, 0.5, 0.25, 0.0, B_DARK, B_BRICK)                         # its door
    wall = lobed(0.0, 0.0, 0.0, 3.6, lobes=3, amp=0.08, n=12, phase=0.5, sy=0.8)
    sweep(k, [(x, y, 0.0) for x, y, _z in wall[:10]], trap_section(0.35, 0.25, 0.7 + SKIRT, -SKIRT), B_BRICK, caps=B_BRICK)
    for x, y, a in ((0.8, -3.6, 0.2), (2.2, -3.2, -0.4)):                                      # speeders
        tbox(k, x, y, 0.15, 0.3, 0.5, 0.2, a, B_HULL, B_HULL)


# ==================================================================================================== BOTAJEF
# Botajef (canon: the Governor's palace, the north- and south-polar bases; Legends: Botajef Shipyards, maker of the
# AA-9 Coruscant freighter and the SS-54, with yards and test grounds over the whole southern continent; elevator cables
# 325 km long up to the orbiting yards; the user: an industrial world). Architecture is a design choice: grimy
# sawtooth factory halls, chimneys, gantry cranes, slab hab blocks, a steel palace. Atlas hod_botajef (B_ layout):
# B_PLATE grimy steel plate, B_PLATE_WIN lit window rows, B_RUST rust, B_HAZARD hazard stripes, B_SOOT polar ice,
# B_ROOF corrugated roofs, B_BRICK soot brick, B_HULL freighter hull.

def bot_hall(k, x, y, z0, h, w, d, a, teeth=3):
    """a factory hall: grimy walls and a sawtooth roof of `teeth` north lights"""
    tbox(k, x, y, z0, h, w, d, a, B_PLATE_WIN, B_ROOF)
    for i in range(teeth):
        v = -d + d * 2 * (i + 0.5) / teeth
        cx, cy = turn(x, y, a, 0.0, v)
        t = d / teeth
        prism_at(k, cx, cy, h, a, 2 * w, [(t, 0.0), (-t * 0.6, t * 1.1), (-t, 0.0)], [B_ROOF, B_PLATE_WIN, B_ROOF],
                 end=B_PLATE)


def bot_chimney(k, x, y, z0, h, r):
    k.lathe([(r * 1.3, z0), (r, h * 0.2), (r * 0.8, h), (r * 0.9, h + 0.02)], [B_BRICK, B_BRICK, B_RUST], sides=8, cx=x,
            cy=y, cap=B_DARK)


def bot_crane(k, x, y, z0, h, a, reach):
    """a gantry crane: two legs, a beam across, a trolley"""
    p = [turn(x, y, a, 0.0, s_ * reach / 2) for s_ in (-1, 1)]
    for px, py in p:
        k.tube((px, py, z0), (px, py, h), reach * 0.03, B_HAZARD, sides=4)
    sweep(k, [p[0] + (h,), p[1] + (h,)], rect_section(reach * 0.06, reach * 0.06), B_HAZARD, caps=B_HAZARD)
    tbox(k, x, y, h - reach * 0.08, h + reach * 0.02, reach * 0.05, reach * 0.06, a, B_RUST, B_RUST)


def bot_city(k, band, rng):
    # Botajef's industry to the horizon: rail-straight roads, sawtooth factory halls along them, chimneys, slab hab
    # blocks, a gantry crane over a yard. band 1 outskirts .. 4 the heavy works
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.15, curvy=False)
    for p in paths:
        sweep(k, [p[0], p[-1]], rect_section(0.14 + 0.02 * band, 0.315, CELL_Z), [B_CONC, B_DUST, B_CONC], open_sec=True)
        lots.block_path(p, 0.18 + 0.02 * band)
    for _ in range(band + 2):                                                      # factory halls
        w = rng.uniform(0.14, 0.22)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.12)
        if p_:
            bot_hall(k, p_[0], p_[1], CELL_Z, rng.uniform(0.1, 0.16) + 0.02 * band, w, w * 0.6, p_[2])
            if rng.random() < 0.5 + 0.1 * band:
                cx, cy = turn(p_[0], p_[1], p_[2], w * 0.8, w * 0.75)
                bot_chimney(k, cx, cy, CELL_Z, rng.uniform(0.5, 0.8) + 0.15 * band, 0.035)
    for _ in range(3 - band // 2):                                                 # hab slabs
        w = rng.uniform(0.07, 0.1)
        p_ = lots.spot(w * 1.4)
        if p_:
            tbox(k, p_[0], p_[1], CELL_Z, rng.uniform(0.3, 0.6) + 0.1 * band, w, w * 0.45, rng.uniform(0, math.pi),
                 B_PLATE_WIN, B_ROOF)
    p_ = lots.spot(0.25) if band >= 2 else None
    if p_:
        bot_crane(k, p_[0], p_[1], CELL_Z, 0.35 + 0.05 * band, rng.uniform(0, math.pi), 0.45)


def bot_palace(k):
    # the Governor's palace (canon, Governor Quesl's in the Imperial era; here the planetary governor's seat): a
    # stepped steel podium over the smog, the palace hall with a slanted glass front, a tall command spire, two wings,
    # a private landing pad on a cantilever, banners of the Confederacy. ~11 across
    tbox(k, 0.0, 0.0, -SKIRT, 1.4, 4.4, 3.4, 0.0, B_CONC, B_DUST, wt=4.1, dt=3.1)
    tbox(k, 0.0, 0.4, 1.4, 4.0, 2.6, 1.6, 0.0, B_PLATE_WIN, B_ROOF, wt=2.4, dt=1.1)
    tbox(k, 0.0, -1.0, 1.4, 3.6, 2.4, 0.3, 0.0, B_CONC_WIN, B_CONC_WIN, wt=2.2, dt=0.05)        # the glass front
    for s_ in (-1, 1):
        tbox(k, s_ * 3.4, 0.6, 1.4, 3.0, 0.9, 1.6, 0.0, B_PLATE_WIN, B_ROOF)
    k.lathe([(0.8, 4.0), (0.6, 8.5), (0.95, 9.0), (0.95, 9.8), (0.3, 10.4), (0.0, 12.0)],
            [B_PLATE, B_RUST, B_CONC_WIN, B_PLATE, B_HULL], sides=6, cx=0.0, cy=1.0)            # the spire
    sweep(k, [(3.4, -0.6, 3.0), (5.6, -2.2, 3.0)], rect_section(0.5, 0.25), B_PLATE, caps=B_PLATE)
    pad(k, 5.8, -2.5, 3.3, 1.1, B_HAZARD, B_PAD)
    k.tube((5.8, -2.5, 3.15), (4.6, -1.6, -0.5), 0.2, B_PLATE, sides=6)
    for x in (-1.6, 1.6):                                                                      # banners
        tbox(k, x, -1.2, 2.0, 3.9, 0.3, 0.03, 0.0, B_RUST, B_RUST)


def bot_elevator(k):
    # the space elevator (Legends: elevator cables 325 kilometres long from the surface to the orbiting yards): the
    # anchor station, a massive stepped pyramid of steel with buttress fins, the cable rising straight up out of the
    # map with cargo climbers on it, guy stays to four pylons, freight sheds and rail spurs at its foot. ~13 across,
    # the cable ~40 high
    z, w = -SKIRT, 4.2
    for t, (h, f) in enumerate(((1.6, 0.8), (3.2, 0.75), (4.8, 0.7))):                         # the anchor
        tbox(k, 0.0, 0.0, z, h, w, w, TAU / 8, B_PLATE_WIN if t else B_CONC, B_ROOF, wt=w * 0.92, dt=w * 0.92)
        z, w = h, w * f
    for i in range(4):
        a = TAU * i / 4 + TAU / 8
        fin(k, 0.0, 0.0, a, [(w * 1.1, 4.8), (w * 0.8, 7.5)], 0.6, 0.35, B_RUST)
    k.lathe([(w * 1.1, 4.8), (w * 0.7, 7.5), (0.5, 8.2)], [B_PLATE, B_HAZARD], sides=8, cap=B_GLOW)
    k.lathe([(0.18, 8.0), (0.18, 42.0)], B_HULL, sides=6, cap=B_GLOW)                           # the cable
    for zc in (14.0, 27.0):                                                                    # climbers
        k.lathe([(0.2, zc), (0.7, zc + 0.4), (0.7, zc + 1.4), (0.2, zc + 1.8)], [B_HAZARD, B_PLATE, B_HAZARD], sides=8)
    for i in range(4):                                                                         # pylons, stays
        a = TAU * i / 4
        x, y = 5.6 * math.cos(a), 5.6 * math.sin(a)
        k.lathe([(0.35, -SKIRT), (0.2, 6.0)], B_RUST, sides=6, cx=x, cy=y, cap=B_HAZARD)
        k.tube((x, y, 6.0), (0.0, 0.0, 16.0), 0.04, B_HULL, sides=4)
    for x, y, a in ((-5.0, 3.0, 0.5), (4.6, -3.6, -0.6)):
        bot_hall(k, x, y, -SKIRT, 1.2, 1.4, 0.8, a)


def bot_aa9(k, x, y, z, head, L, built=1.0):
    """an AA-9 Coruscant freighter lying along `head`, its underside at z (Legends: Botajef's big passenger-cargo
    liner; the shape is an approximation): a long round hull, a broad flat prow block with the bridge on it, a deck
    block on the back, a stern of three engines; `built` < 1 leaves the fore part bare ribs"""
    at = lambda u, v, zz: turn(x, y, head, u, v) + (z + zz,)
    zc, cut = L * 0.11, -0.5 + built                                   # hull axis height; the plating stops here
    k.tube(at(-L * 0.42, 0, zc), at(min(L * 0.28, cut * L), 0, zc), L * 0.1, B_HULL, sides=12, r1=L * 0.09)
    for s_ in (-1, 0, 1):                                              # the engines
        k.tube(at(-L * 0.52, s_ * L * 0.07, zc), at(-L * 0.4, s_ * L * 0.07, zc), L * 0.045, B_PLATE, sides=10)
        k.tube(at(-L * 0.53, s_ * L * 0.07, zc), at(-L * 0.52, s_ * L * 0.07, zc), L * 0.04, B_GLOW, sides=10)
    tbox(k, *at(-L * 0.12, 0, 0)[:2], z + zc, z + L * 0.26, L * 0.16, L * 0.07, head, B_PLATE_WIN, B_ROOF,
         wt=L * 0.13, dt=L * 0.05)                                     # the deck block
    for s_ in (-1, 1):                                                 # stub wings
        tbox(k, *at(-L * 0.28, s_ * L * 0.13, 0)[:2], z + zc - L * 0.01, z + zc + L * 0.01, L * 0.08, L * 0.06, head,
             B_PLATE, B_PLATE, base=B_PLATE)
    if built >= 1:
        tbox(k, *at(L * 0.38, 0, 0)[:2], z + L * 0.02, z + L * 0.2, L * 0.13, L * 0.13, head, B_PLATE_WIN, B_HULL,
             wt=L * 0.1, dt=L * 0.11, base=B_HULL)                     # the prow block
        tbox(k, *at(L * 0.4, 0, 0)[:2], z + L * 0.2, z + L * 0.25, L * 0.06, L * 0.06, head, B_CONC_WIN, B_ROOF,
             wt=L * 0.04, dt=L * 0.05)                                 # the bridge
        return
    for q in range(8):                                                 # bare ribs over the unplated fore part
        u = cut + (0.5 - cut) * q / 7
        for t in range(8):
            a0, a1 = TAU * t / 8, TAU * (t + 1) / 8
            r = L * 0.1
            k.tube(at(u * L, r * math.cos(a0), zc + r * math.sin(a0)), at(u * L, r * math.cos(a1), zc + r * math.sin(a1)),
                   0.04, B_GIRDER, sides=3)
    k.tube(at(cut * L, 0, zc), at(0.5 * L, 0, zc), 0.07, B_GIRDER, sides=5)


def bot_ss54(k, x, y, z, head, L):
    """an SS-54 light freighter (Legends, Botajef Shipyards; the shape is an approximation): a flat wedge body, a
    cockpit pod on the prow, two engine nacelles"""
    at = lambda u, v, zz: turn(x, y, head, u, v) + (z + zz,)
    tbox(k, x, y, z, z + L * 0.16, L * 0.45, L * 0.28, head, B_HULL, B_PLATE, wt=L * 0.38, dt=L * 0.2, base=B_HULL)
    k.tube(at(L * 0.3, 0, L * 0.12), at(L * 0.55, 0, L * 0.1), L * 0.09, B_CONC_WIN, sides=8, r1=L * 0.03)
    for s_ in (-1, 1):
        k.tube(at(-L * 0.5, s_ * L * 0.3, L * 0.1), at(0, s_ * L * 0.3, L * 0.1), L * 0.08, B_PLATE, sides=8)
        k.tube(at(-L * 0.52, s_ * L * 0.3, L * 0.1), at(-L * 0.5, s_ * L * 0.3, L * 0.1), L * 0.07, B_GLOW, sides=8)


def bot_yards(k):
    # Botajef Shipyards on the ground (Legends: builders of the AA-9 Coruscant freighter and the SS-54 light
    # freighter; the user, 2026-10-19: starships, not boats - the main yards float in orbit, bot_orbital): a starship
    # works on a concrete apron - an AA-9 hull on a cradle of trestles under a gantry, SS-54s on landing pads, an
    # assembly hall with a sawtooth roof and chimneys. ~15 across
    tbox(k, 0.0, 0.0, -SKIRT, 0.4, 7.2, 4.4, 0.0, B_CONC, B_DUST)
    for x in (-3.4, -1.0, 1.4):                                                               # the cradle
        for s_ in (-0.6, 0.6):
            k.lathe([(0.18, 0.4), (0.14, 1.2)], B_RUST, sides=6, cx=x, cy=-1.4 + s_, cap=B_HAZARD)
    bot_aa9(k, -0.8, -1.4, 1.1, 0.0, 9.0)                                                      # the AA-9
    for x in (-4.6, 3.0):                                                                     # the gantry
        for s_ in (-1.7, 1.7):
            k.lathe([(0.15, 0.4), (0.15, 4.4)], B_GIRDER, sides=4, cx=x, cy=-1.4 + s_)
        tbox(k, x, -1.4, 4.2, 4.6, 0.25, 1.9, 0.0, B_HAZARD, B_HAZARD, base=B_HAZARD)
    tbox(k, -0.8, -1.4, 4.6, 4.8, 3.9, 0.2, 0.0, B_GIRDER, B_HAZARD, base=B_GIRDER)
    for x in (-3.4, 0.0):                                                                     # pads, SS-54s
        pad(k, x, 2.2, 0.4, 1.3, B_HAZARD, B_PAD)
        bot_ss54(k, x, 2.2, 0.62, 0.3, 2.0)
    bot_hall(k, 5.0, 1.6, 0.4, 2.6, 1.6, 2.0, 0.0, teeth=4)
    for x in (4.2, 6.2):
        bot_chimney(k, x, 3.6, 0.4, 6.5, 0.28)


def bot_orbital(k):
    # Botajef Shipyards in orbit (the user, 2026-10-19: a space shipyard building starships; Legends: the elevator
    # cables climb to orbiting yards; the layout is a design choice), floated in the space east of the planet
    # (botajef_map.PLACEMENT hook, military_buildings.BOT_YARD_AT), clear of the water plane from z 3 up: a long spine
    # with the station at its middle (stacked drums, a docking ring), four box-truss slips off its sides - an AA-9
    # finished, one mostly plated, one still half ribs, three SS-54s in the last - crane trolleys on the slips,
    # radiator fans and end stations, tugs. ~44 across
    import random
    rng = random.Random("hod_bot_orbital")
    zc = 3.0 + 4.2
    k.tube((-21.0, 0.0, zc), (21.0, 0.0, zc), 0.9, B_PLATE, sides=12)                         # the spine
    for i in range(-5, 6):
        k.tube((i * 3.8 - 0.3, 0.0, zc), (i * 3.8 + 0.3, 0.0, zc), 1.15, B_RUST, sides=12)
    k.lathe([(0.0, zc - 4.2), (2.6, zc - 3.4), (3.2, zc - 1.4), (3.2, zc + 1.2), (2.4, zc + 2.6), (2.4, zc + 3.6),
             (1.2, zc + 4.4), (0.0, zc + 4.6)], [B_HULL, B_PLATE_WIN, B_PLATE_WIN, B_HULL, B_PLATE_WIN, B_ROOF, B_ROOF],
            sides=24)                                                                         # the station
    for i in range(32):                                                                       # its docking ring
        t0, t1 = TAU * i / 32, TAU * (i + 1) / 32
        k.tube((5.4 * math.cos(t0), 5.4 * math.sin(t0), zc), (5.4 * math.cos(t1), 5.4 * math.sin(t1), zc), 0.45,
               B_PLATE_WIN if i % 4 else B_HAZARD, sides=10)
    for j in range(4):
        b = TAU * j / 4 + TAU / 8
        k.tube((3.0 * math.cos(b), 3.0 * math.sin(b), zc), (5.4 * math.cos(b), 5.4 * math.sin(b), zc), 0.3, B_HULL, sides=8)
    k.lathe([(0.1, zc + 4.6), (0.06, zc + 8.0)], B_PIPE, sides=4, cap=B_GLOW)                  # mast
    for sx in (-21.5, 21.5):                                                                  # end stations, fans
        k.lathe([(0.0, zc - 2.2), (1.8, zc - 1.4), (2.1, zc), (1.8, zc + 1.4), (0.0, zc + 2.2)],
                [B_HULL, B_PLATE_WIN, B_PLATE_WIN, B_HULL], sides=16, cx=sx)
        for s_ in (-1, 1):
            tbox(k, sx * 0.9, s_ * 3.6, zc - 0.05, zc + 0.05, 1.4, 2.4, 0.0, B_GIRDER, B_GLOW, base=B_GIRDER)
            k.tube((sx * 0.9, 0.0, zc), (sx * 0.9, s_ * 1.2, zc), 0.15, B_PIPE, sides=4)
    ships = {(-11.0, -1): ("aa9", 1.0), (-11.0, 1): ("aa9", 0.75), (11.0, -1): ("aa9", 0.45), (11.0, 1): ("ss54", 0)}
    for (sx, side), (kind, built) in ships.items():                                           # the slips
        y0, y1, hw, hz = side * 2.0, side * 17.0, 3.2, 2.6
        for u, w in ((-hw, -hz), (hw, -hz), (-hw, hz), (hw, hz)):                             # chords
            k.tube((sx + u, y0, zc + w), (sx + u, y1, zc + w), 0.16, B_PLATE, sides=6)
        for q in range(7):                                                                    # hoops and diagonals
            y = y0 + (y1 - y0) * q / 6
            for (u0, w0), (u1, w1) in (((-hw, -hz), (hw, -hz)), ((hw, -hz), (hw, hz)), ((hw, hz), (-hw, hz)),
                                       ((-hw, hz), (-hw, -hz))):
                k.tube((sx + u0, y, zc + w0), (sx + u1, y, zc + w1), 0.1, B_GIRDER if q % 2 else B_HAZARD, sides=4)
            if q < 6:
                yn = y0 + (y1 - y0) * (q + 1) / 6
                for u in (-hw, hw):
                    k.tube((sx + u, y, zc - hz), (sx + u, yn, zc + hz), 0.06, B_GIRDER, sides=3)
            k.lathe([(0.14, zc + hz), (0.14, zc + hz + 0.2)], [B_GLOW], sides=6, cx=sx - hw, cy=y, cap=B_GLOW)
        ty = side * rng.uniform(6.0, 13.0)                                                    # the crane trolley
        tbox(k, sx, ty, zc + hz - 0.1, zc + hz + 0.6, hw + 0.3, 0.5, 0.0, B_HAZARD, B_ROOF, base=B_HAZARD)
        k.box(sx - 0.04, ty - 0.04, zc + 0.8, sx + 0.04, ty + 0.04, zc + hz - 0.1, B_DARK)
        k.tube((sx, side * 0.8, zc), (sx, y0, zc), 0.45, B_HULL, sides=8)                     # the access tube
        head = math.pi / 2 if side > 0 else -math.pi / 2
        if kind == "aa9":
            bot_aa9(k, sx, side * 9.5, zc - 14.0 * 0.11, head, 14.0, built)
        else:
            for q in range(3):
                bot_ss54(k, sx, side * (5.0 + q * 4.5), zc - 0.4, head, 3.4)
    for x, y, a in ((-6.0, -20.0, 1.2), (7.0, 19.5, -2.0), (16.0, -19.0, 2.4), (-17.0, 18.0, -0.7)):   # tugs
        shuttle(k, x, y, zc - 0.5, a, 3.0, B_HULL, B_CONC_WIN)


def bot_polar(k, south):
    """a polar base on the ice: a snow mound, prefab domes joined by tubes, a hangar vault, a pad, a mast; north the
    comm dish, south the test launch tower"""
    import random
    rng = random.Random("bot_polar" + str(south))
    rock(k, 0.0, 0.0, -SKIRT, 0.5, 5.2, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4)
    domes = [(-1.8, -0.6, 1.3), (0.6, -1.4, 1.0), (1.2, 1.2, 1.1)]
    for x, y, r in domes:
        k.lathe([(r, -0.5), (r, 0.6)], B_PLATE_WIN, sides=14, cx=x, cy=y)
        dome(k, x, y, 0.6, r, r * 0.8, [B_PLATE, B_PLATE, B_HAZARD, B_PLATE], sides=14)
    for (x0, y0, _), (x1, y1, _) in zip(domes, domes[1:]):
        k.tube((x0, y0, 0.5), (x1, y1, 0.5), 0.25, B_PLATE, sides=6)
    tbox(k, -1.0, 2.6, -SKIRT, 0.5, 1.6, 1.0, 0.2, B_PLATE, B_ROOF)
    vault(k, -1.0, 2.6, 0.5, 0.2, 3.2, 1.0, 1.0, [B_PLATE] * 8, end=B_DARK)                   # the hangar
    pad(k, 3.4, -1.8, 0.6, 1.0, B_HAZARD, B_PAD)
    k.lathe([(0.7, -SKIRT), (0.7, 0.45)], B_PLATE, sides=12, cx=3.4, cy=-1.8)
    if south:                                                                                  # launch tower
        legs(k, 3.2, 2.0, -SKIRT, 6.0, 0.9, 0.35, 4, 0.08, B_HAZARD)
        k.lathe([(0.3, 0.6), (0.3, 5.2), (0.0, 6.0)], [B_HULL, B_RUST], sides=8, cx=3.2, cy=2.6)
    else:                                                                                      # the comm dish
        k.lathe([(0.25, -SKIRT), (0.18, 3.0)], B_PLATE, sides=6, cx=3.0, cy=2.2)
        k.lathe([(0.1, 3.0), (1.5, 3.5), (1.7, 3.9)], [B_PLATE, B_PLATE], sides=16, cx=3.0, cy=2.2, rot=0.3)
        k.lathe([(0.05, 3.1), (0.0, 4.6)], B_HULL, sides=4, cx=3.0, cy=2.2)
    k.lathe([(0.08, 0.0), (0.04, 5.0), (0.0, 5.3)], [B_HULL, B_GLOW], sides=5, cx=-3.4, cy=-2.0)   # mast


def bot_northbase(k):
    # the North-Polar Base (canon, nothing more told): a comm and sensor base on the northern ice. ~11 across
    bot_polar(k, False)


def bot_southbase(k):
    # the South-Polar Base (canon: a base in the south-polar region; here the shipyards' test base): ~11 across
    bot_polar(k, True)


# ==================================================================================================== AXXILA
# Axxila (canon: cliffs, an ore-exporting world; Legends: a worldspanning metropolis; Fossfog's with its bounty feed in
# the wine cellar). Architecture is not described: a design choice, a city built on and into cliffs - stepped ochre
# terrace blocks cantilevered over the drops, slab towers, bridges between them; the ore trade in rust and steel.
# Atlas hod_axxila (B_ layout): B_PLATE ochre stone, B_PLATE_WIN window rows, B_SOOT cliff rock, B_BRICK ore heaps,
# B_RUST rust, B_GLOW warm light, B_HAZARD neon sign.

def axx_terrace(k, x, y, z0, h, w, d, a, steps, rng, lite=False):
    """a cliff terrace block: `steps` stacked slabs, each set back on one side so the block steps up like a hillside,
    window walls, flat roofs (a roof garden on the lowest)"""
    z = z0
    for i in range(steps):
        z1 = max(z, 0.0) + h / steps
        off = -d * 0.25 * i
        cx, cy = turn(x, y, a, 0.0, off)
        tbox(k, cx, cy, z, z1, w, d * (1 - 0.25 * i), a, B_PLATE_WIN, B_ROOF)
        z = z1


def axx_city(k, band, rng):
    # Axxila's metropolis: straight streets on the cliff top, stepped terrace blocks along them, slab towers, a bridge
    # between two of them downtown. band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.2, curvy=False)
    for p in paths:
        sweep(k, [p[0], p[-1]], rect_section(0.14 + 0.02 * band, 0.315, CELL_Z), [B_CONC, B_DUST, B_CONC], open_sec=True)
        lots.block_path(p, 0.18 + 0.02 * band)
    for _ in range(band + 3):                                                      # terrace blocks
        w = rng.uniform(0.1, 0.17)
        p_ = lots.along(rng.choice(paths), w * 1.2, 0.1) or lots.spot(w * 1.2)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            axx_terrace(k, p_[0], p_[1], CELL_Z, rng.uniform(0.15, 0.3) + 0.08 * band, w, w * 0.8, a, 2 + band // 2, rng)
    towers = []
    for _ in range(band):                                                          # slab towers
        w = rng.uniform(0.06, 0.09)
        p_ = lots.spot(w * 1.6)
        if p_:
            h = rng.uniform(0.5, 0.9) + 0.3 * band
            a = rng.uniform(0, math.pi)
            tbox(k, p_[0], p_[1], CELL_Z, h, w, w * 0.55, a, B_PLATE_WIN, B_ROOF)
            tbox(k, p_[0], p_[1], h, h + 0.06, w * 1.15, w * 0.7, a, B_RUST, B_ROOF)
            towers.append((p_[0], p_[1], h))
    if len(towers) >= 2:
        (x0, y0, h0), (x1, y1, h1) = towers[:2]
        z = min(h0, h1) * 0.55
        sweep(k, [(x0, y0, z), (x1, y1, z)], rect_section(0.05, 0.04), B_RUST, caps=B_RUST)


def axx_capital(k):
    # Axxila City (invented name; Legends: a worldspanning metropolis on a cliff-world): a great cliff of ochre rock,
    # the city's terrace blocks stepping down its face, slab towers crowded on the top joined by bridges, a tall
    # government tower, a cantilevered pad over the drop with a shuttle. ~14 across
    import random
    rng = random.Random("axx_city")
    rock(k, 0.0, 0.0, -SKIRT, 3.2, 5.6, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.8)
    for i, (x, y, z, a) in enumerate(((-3.6, -2.4, -0.5, 0.6), (-1.0, -3.8, -0.5, 0.1), (2.2, -3.6, -0.5, -0.3),
                                      (4.2, -1.2, -0.5, -1.1))):
        axx_terrace(k, x, y, z, 3.2, 1.3, 0.9, a, 3, rng)                              # terraces down the face
    towers = [(0.4, 1.0, 12.0, 0.9), (-1.8, 0.4, 9.0, 0.7), (2.2, 0.0, 8.5, 0.7), (-0.6, 2.6, 7.5, 0.6),
              (1.6, 2.4, 7.0, 0.6), (-2.6, 2.2, 6.0, 0.55)]
    for x, y, h, w in towers:
        tbox(k, x, y, 2.0, h, w, w * 0.6, rng.uniform(-0.3, 0.3), B_PLATE_WIN, B_ROOF, wt=w * 0.85, dt=w * 0.5)
        tbox(k, x, y, h, h + 0.4, w * 1.1, w * 0.7, 0.0, B_RUST, B_ROOF)
    for (x0, y0, h0, _), (x1, y1, h1, _) in ((towers[0], towers[1]), (towers[0], towers[2]), (towers[1], towers[3])):
        sweep(k, [(x0, y0, min(h0, h1) * 0.6), (x1, y1, min(h0, h1) * 0.6)], rect_section(0.3, 0.25), B_PLATE_WIN,
              caps=B_RUST)
    k.lathe([(0.5, 12.4), (0.3, 14.5), (0.0, 15.2)], [B_RUST, B_HULL], sides=6, cx=0.4, cy=1.0)   # the mast
    sweep(k, [(-4.2, 1.0, 3.0), (-6.0, 1.6, 3.0)], rect_section(0.5, 0.25), B_PLATE, caps=B_PLATE)
    pad(k, -6.4, 1.8, 3.3, 1.0, B_RUST, B_PAD)
    k.tube((-6.4, 1.8, 3.15), (-4.8, 1.2, -0.5), 0.18, B_PLATE, sides=6)
    shuttle(k, -6.4, 1.8, 3.3, 0.3, 1.6, B_HULL, B_CONC_WIN)


def axx_fossfog(k):
    # Fossfog's (Legends: an establishment on Axxila with an underworld bounty feed in its wine cellar): a squat stone
    # cantina under a slanted roof, a big lit sign across its front, the ramp down to the cellar, an outbuilding,
    # cargo crates and two speeders in the yard. ~8 across
    tbox(k, 0.0, 0.4, -SKIRT, 1.6, 2.4, 1.6, 0.0, B_PLATE, B_ROOF, wt=2.3, dt=1.4)
    prism_at(k, 0.0, 0.4, 1.6, 0.0, 4.8, [(1.5, 0.0), (1.5, 0.3), (-1.5, 1.0), (-1.5, 0.0)], [B_ROOF] * 4, end=B_PLATE)
    tbox(k, 0.0, -1.25, 1.0, 1.9, 1.6, 0.08, 0.0, B_HAZARD, B_HAZARD)                         # the sign
    tbox(k, -0.8, -1.25, -SKIRT, 0.9, 0.45, 0.1, 0.0, B_DARK, B_PLATE)                        # the door
    sweep(k, [(1.6, -2.4, 0.05), (1.6, -1.3, -0.8)], [(0.4, -SKIRT), (0.4, 0.0), (-0.4, 0.0), (-0.4, -SKIRT)],
          [B_PLATE, B_DARK, B_PLATE], open_sec=True)                                          # the cellar ramp
    tbox(k, 3.2, 1.0, -SKIRT, 1.0, 0.8, 0.8, 0.3, B_PLATE_WIN, B_ROOF)
    import random
    rng = random.Random("axx_fossfog")
    for _ in range(5):
        tbox(k, rng.uniform(-3.4, -2.0), rng.uniform(-1.0, 1.6), -0.2, rng.uniform(0.3, 0.6), 0.25, 0.25,
             rng.uniform(0, 1.5), B_RUST, B_RUST)
    for x, y, a in ((0.6, -2.8, 0.1), (-1.4, -3.0, -0.3)):
        tbox(k, x, y, 0.15, 0.3, 0.55, 0.22, a, B_HULL, B_HULL)


def axx_oreport(k):
    # the Ore Terminal (invented; canon: Axxila exported ores): ore silos in a row, a conveyor gantry running from the
    # ore heaps up to a bulk freighter on its pad, a loading crane, a control block. ~13 across
    import random
    rng = random.Random("axx_oreport")
    for i in range(4):                                                                         # the silos
        k.lathe([(0.9, -SKIRT), (0.9, 3.6), (0.5, 4.2), (0.2, 4.4)], [B_PLATE, B_RUST, B_PLATE], sides=12,
                cx=-3.6 + i * 1.9, cy=2.4, cap=B_RUST)
    for x, y, r in ((-4.0, -2.0, 1.6), (-1.6, -3.0, 1.3)):                                     # ore heaps
        rock(k, x, y, -SKIRT, 1.4, r, rng, [B_BRICK] * 3, lobes=3)
    sweep(k, [(-2.6, -2.4, 1.2), (0.0, -0.6, 3.2), (3.0, 0.4, 3.2)], rect_section(0.4, 0.35), B_GIRDER, caps=B_RUST)
    for x, y, z in ((-1.4, -1.6, 2.2), (0.0, -0.6, 3.2), (1.6, -0.1, 3.2)):
        k.tube((x, y, -SKIRT), (x, y, z), 0.12, B_RUST, sides=5)
    k.lathe([(2.6, -SKIRT), (2.6, 0.4), (2.8, 0.5)], [B_CONC, B_HAZARD], sides=16, cx=4.0, cy=-0.6, cap=B_PAD)
    tbox(k, 4.0, -0.6, 0.5, 2.0, 1.7, 0.9, 0.3, B_HULL, B_HULL, wt=1.5, dt=0.8)               # the bulk freighter
    tbox(k, 5.4, -0.2, 0.5, 2.6, 0.4, 0.6, 0.3, B_CONC_WIN, B_HULL)
    bot_crane(k, 2.6, -2.6, 0.0, 4.0, 0.4, 3.0)
    tbox(k, -0.6, 3.6, -SKIRT, 1.6, 1.0, 0.6, 0.0, B_PLATE_WIN, B_ROOF)


# ==================================================================================================== CIUTRIC IV
# Ciutric IV (Legends: the heart of the Ciutric Hegemony, industrial and forested, eleven billion people; Daplona the
# capital on the Daplona River, with the Shine Astara among its most exclusive restaurants; a mansion of Darth Bane's;
# a prison; the Daplona base training center). Architecture is not described: a design choice, grey ferrocrete towers
# ribbed with vertical fins over dark brick factory halls with chimneys, slate roofs, the Hegemony's red.
# Atlas hod_ciutric (B_ layout): B_PLATE grey ferrocrete, B_PLATE_WIN window rows, B_BRICK dark brick, B_RUST
# Hegemony red, B_ROOF slate, B_SOOT dark stone (the mansion), B_DUST paving, B_HULL ship hull.

def cit_tower(k, x, y, z0, h, w, a, rng, lite=False):
    """a Daplona tower: a rectangular shaft (window storeys recessed on landmarks), vertical fins on its faces, a
    red-banded crown"""
    g = max(z0, 0.0)
    d = w * rng.uniform(0.55, 0.8)
    if lite:
        tbox(k, x, y, z0, h, w, d, a, B_PLATE_WIN, B_ROOF)
    else:
        banded(k, lambda zz, grow: rrect(x, y, zz, w + grow, d + grow, 0.02, a, 1), z0, h, max(2, int((h - g) / 0.8)),
               B_PLATE, B_PLATE_WIN, inset=w * 0.06, cap=B_ROOF)
        for s_ in (-0.5, 0.5):
            for side in (-1, 1):
                fx, fy = turn(x, y, a, s_ * w, side * d)
                tbox(k, fx, fy, g, h * 0.96, w * 0.05, w * 0.12, a, B_PLATE, B_PLATE)
    tbox(k, x, y, h, h + (h - g) * 0.05, w * 0.92, d * 0.92, a, B_RUST, B_ROOF)


def cit_city(k, band, rng):
    # Ciutric's towns and Daplona's districts: avenues lined with brick factory halls and blocks, finned towers rising
    # downtown, chimneys, a green square. band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.25)
    for p in paths:
        sweep(k, p, rect_section(0.13 + 0.02 * band, 0.315, CELL_Z), [B_CONC, B_DUST, B_CONC], open_sec=True)
        lots.block_path(p, 0.17 + 0.02 * band)
    for _ in range(band + 3):                                                      # brick blocks and halls
        w = rng.uniform(0.1, 0.17)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.1) or lots.spot(w * 1.2)
        if not p_:
            continue
        a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
        h = rng.uniform(0.1, 0.18) + 0.04 * band
        tbox(k, p_[0], p_[1], CELL_Z, h, w, w * 0.6, a, B_BRICK, B_ROOF)
        prism_at(k, p_[0], p_[1], h, a, 2 * w, [(w * 0.62, 0.0), (0.0, w * 0.35), (-w * 0.62, 0.0)], [B_ROOF] * 3,
                 end=B_BRICK)
        if rng.random() < 0.35:
            cx, cy = turn(p_[0], p_[1], a, w * 0.7, 0.0)
            k.lathe([(0.035, CELL_Z), (0.028, h + 0.45 + 0.1 * band)], B_BRICK, sides=6, cx=cx, cy=cy, cap=B_DARK)
    for _ in range(band - 1):                                                      # finned towers
        w = rng.uniform(0.07, 0.1)
        p_ = lots.spot(w * 1.5)
        if p_:
            cit_tower(k, p_[0], p_[1], CELL_Z, rng.uniform(0.6, 1.0) + 0.35 * band, w, rng.uniform(0, math.pi), rng, lite=True)


def cit_daplona(k):
    # Daplona, the capital (Legends): a riverside quay with an arched bridge over a canal of the Daplona River, the
    # Hegemony's domed hall on the plaza, five finned towers, the tallest carrying the Shine Astara's restaurant disc
    # near its top. ~14 across
    import random
    rng = random.Random("cit_daplona")
    plaza = lobed(0.0, 0.6, 0.0, 4.8, lobes=3, amp=0.14, n=30, phase=0.2, sy=0.75)
    loft(k, [at_z(plaza, -SKIRT), at_z(plaza, 0.5), scaled(at_z(plaza, 0.6), 0.97)], [B_PLATE, B_PLATE], cap=B_DUST)
    sweep(k, [(-6.0, -3.4, 0.05), (0.0, -3.9, 0.05), (6.0, -3.2, 0.05)],
          [(0.9, -SKIRT), (0.9, 0.05), (-0.9, 0.05), (-0.9, -SKIRT)], [B_PLATE, B_CONC_WIN, B_PLATE], open_sec=True)   # canal
    curve_tube(k, (-0.6, -5.2, 0.5), (-0.4, -2.6, 0.5), 0.9, 0.35, 0.35, B_PLATE, n=8)              # the bridge
    towers = [(0.8, 2.6, 13.0, 1.0), (-2.6, 2.0, 10.0, 0.8), (3.4, 1.4, 9.0, 0.75), (-3.4, -0.8, 7.0, 0.65),
              (3.6, -1.6, 6.5, 0.6)]
    for x, y, h, w in towers:
        cit_tower(k, x, y, -SKIRT, h, w, rng.uniform(-0.2, 0.2), rng)
    k.lathe([(0.5, 10.6), (2.0, 11.0), (2.0, 11.6), (0.6, 12.0)], [B_PLATE, B_CONC_WIN, B_PLATE], sides=20, cx=0.8, cy=2.6)
    k.lathe([(1.5, 0.6), (1.5, 1.9)], B_PLATE_WIN, sides=16, cx=-0.4, cy=-0.6)                   # the Hegemony hall
    dome(k, -0.4, -0.6, 1.9, 1.55, 1.2, [B_ROOF, B_ROOF, B_RUST, B_ROOF], sides=16)
    for x in (-1.2, 0.4):                                                                       # banners
        tbox(k, x, -2.2, 0.9, 2.3, 0.25, 0.03, 0.0, B_RUST, B_RUST)


def cit_training(k):
    # the Daplona base training center (Legends): rows of barracks round a drill field, a command block with a
    # tower, an obstacle course of walls and towers, a firing range, a pad with a transport. ~11 across
    for i in range(4):
        tbox(k, -3.8 + i * 1.9, 2.8, -SKIRT, 0.9, 0.8, 0.5, 0.0, B_PLATE_WIN, B_ROOF)
    tbox(k, 0.0, 0.0, -0.2, 0.08, 3.4, 1.6, 0.0, B_DUST, B_DUST)                                # the drill field
    tbox(k, -4.4, -0.6, -SKIRT, 1.6, 0.9, 1.2, 0.0, B_PLATE_WIN, B_ROOF)                        # command block
    k.lathe([(0.35, 1.6), (0.3, 3.8), (0.6, 4.0), (0.6, 4.5), (0.0, 4.8)], [B_PLATE, B_RUST, B_CONC_WIN, B_ROOF], sides=8,
            cx=-4.4, cy=-0.6)
    for x, y, h in ((-1.6, -2.6, 0.6), (-0.4, -2.8, 0.9), (0.8, -2.5, 0.5), (2.0, -2.8, 1.1)):  # obstacle course
        tbox(k, x, y, -0.3, h, 0.4, 0.08, 0.2, B_PLATE, B_PLATE)
    legs(k, 3.0, -2.4, -SKIRT, 1.8, 0.4, 0.3, 4, 0.05, B_RUST)
    tbox(k, 3.0, -2.4, 1.8, 1.9, 0.4, 0.4, 0.0, B_RUST, B_RUST)
    pad(k, 4.4, 0.6, 0.4, 1.1, B_RUST, B_PAD)
    k.lathe([(0.8, -SKIRT), (0.8, 0.25)], B_PLATE, sides=12, cx=4.4, cy=0.6)
    shuttle(k, 4.4, 0.6, 0.4, 1.2, 1.8, B_HULL, B_CONC_WIN)


def cit_prison(k):
    # the Ciutric IV prison (Legends; later where Ysanne Isard's clone held the Lusankya's captives): on a rocky rise,
    # a square curtain wall with guard towers at the corners, a stepped cell block in the middle with slit windows, a
    # gate, a landing pad inside. ~10 across
    import random
    rng = random.Random("cit_prison")
    rock(k, 0.0, 0.0, -SKIRT, 0.6, 5.0, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4)
    sq = [(3.4, -3.0, 0.0), (3.4, 3.0, 0.0), (-3.4, 3.0, 0.0), (-3.4, -3.0, 0.0)]
    sweep(k, sq, trap_section(0.55, 0.4, 2.0 + 0.6, -0.6), B_PLATE, closed_path=True)
    for x, y, _z in sq:
        tbox(k, x, y, -0.6, 3.2, 0.55, 0.55, 0.0, B_PLATE, B_ROOF)
        tbox(k, x, y, 3.2, 3.8, 0.7, 0.7, 0.0, B_CONC_WIN, B_ROOF)
    tbox(k, 0.0, 0.4, 0.4, 2.6, 2.0, 1.4, 0.0, B_PLATE_WIN, B_ROOF)                            # the cell block
    tbox(k, 0.0, 0.4, 2.6, 4.0, 1.4, 0.9, 0.0, B_PLATE_WIN, B_ROOF)
    tbox(k, 0.0, -3.1, -0.6, 2.4, 0.9, 0.5, 0.0, B_PLATE, B_RUST)                              # the gate
    pad(k, -2.0, -1.6, 0.55, 0.8, B_RUST, B_PAD)


def cit_mansion(k):
    # Darth Bane's mansion (Legends: Bane kept a mansion on Ciutric IV, a millennium before the war): a dark stone
    # manor deep in the forest - a long hall under steep slate roofs, a squat square tower with a single red-lit
    # window, a walled garden with a reflecting pool, a gatehouse on the drive. ~10 across
    tbox(k, 0.0, 0.6, -SKIRT, 1.6, 2.8, 1.0, 0.0, B_SOOT, B_ROOF)
    prism_at(k, 0.0, 0.6, 1.6, 0.0, 5.8, [(1.05, 0.0), (0.0, 1.3), (-1.05, 0.0)], [B_ROOF] * 3, end=B_SOOT)
    for x in (-2.4, 2.4):                                                                       # wings
        tbox(k, x, -0.6, -SKIRT, 1.4, 0.7, 1.0, 0.0, B_SOOT, B_ROOF)
        prism_at(k, x, -0.6, 1.4, math.pi / 2, 2.2, [(0.75, 0.0), (0.0, 0.9), (-0.75, 0.0)], [B_ROOF] * 3, end=B_SOOT)
    tbox(k, 0.0, 1.9, -SKIRT, 3.8, 0.75, 0.75, 0.0, B_SOOT, B_ROOF)                              # the tower
    k.lathe([(1.05, 3.8), (0.0, 5.4)], B_ROOF, sides=4, cx=0.0, cy=1.9, rot=math.pi / 4)
    tbox(k, 0.0, 1.13, 2.6, 3.2, 0.12, 0.03, 0.0, B_GLOW, B_GLOW)
    garden = [(-2.8, -1.8, 0.0), (2.8, -1.8, 0.0), (2.8, -4.2, 0.0), (-2.8, -4.2, 0.0)]
    sweep(k, garden, trap_section(0.25, 0.2, 0.9 + SKIRT, -SKIRT), B_SOOT, closed_path=True)
    tbox(k, 0.0, -3.0, -0.2, 0.05, 1.2, 0.5, 0.0, B_CONC_WIN, B_CONC_WIN)                       # the pool
    tbox(k, 0.0, -5.6, -SKIRT, 1.4, 0.7, 0.4, 0.0, B_SOOT, B_ROOF)                              # gatehouse


# ==================================================================================================== ORD CESTUS
# Ord Cestus (Legends: an arid red world of mountains and volcanic craters; the X'Ting, an insectoid people whose
# hives ChikatLik grew round; Cestus Cybernetics' droid works; fungus exports; the Republic's Cestus Penitentiary on
# and under Kibo Lake). Architecture is a design choice: lobed hive spires of red clay like termite towers, pierced
# with lit openings, rounded clay houses, droid works of tan plate with sawtooth halls.
# Atlas hod_cestus (B_ layout): B_PLATE red hive clay, B_PLATE_WIN clay with lit openings, B_CONC tan plate, B_CONC_WIN
# glass, B_SOOT red rock, B_BRICK fungus cap purple, B_DUST red sand, B_RUST rust, B_HULL ship hull.
def ces_spire(k, x, y, z0, h, r, rng, lite=False):
    """an X'Ting hive spire: a lobed clay tower narrowing up to a point, bulging at a third of its height, bands of
    lit openings"""
    ph = rng.uniform(0, TAU)
    lobes = rng.choice((3, 4, 5))
    prof = [(0.0, 1.0), (0.3, 1.08), (0.55, 0.78), (0.75, 0.55), (0.9, 0.3), (1.0, 0.06)]
    if lite:
        prof = [(0.0, 1.0), (0.45, 0.75), (1.0, 0.08)]
    rings = [lobed(x, y, z0 + (h - z0) * t, r * f, lobes=lobes, amp=0.18, n=18, phase=ph + t * 0.6) for t, f in prof]
    rects = [B_PLATE if i % 2 == 0 or lite else B_PLATE_WIN for i in range(len(rings) - 1)]
    loft(k, rings, rects, cap=B_PLATE)


def ces_house(k, x, y, z0, r, rng):
    """a rounded clay house: a squat drum under a low dome"""
    k.lathe([(r, z0), (r, max(z0, 0.0) + r * 0.5)], B_PLATE_WIN, sides=10, cx=x, cy=y)
    dome(k, x, y, max(z0, 0.0) + r * 0.5, r, r * 0.6, B_PLATE, sides=10, n=3)


def ces_city(k, band, rng):
    # Ord Cestus' towns and ChikatLik's districts: winding lanes of red dust, rounded clay houses in clusters, hive
    # spires rising downtown, droid workshops (flat tan halls) on the outskirts. band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.35)
    for p in paths:
        sweep(k, p, rect_section(0.12 + 0.02 * band, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.16 + 0.02 * band)
    for _ in range(4 + band * 2):                                                  # clay houses
        r = rng.uniform(0.06, 0.11)
        p_ = lots.along(rng.choice(paths), r, 0.09) or lots.spot(r * 1.1)
        if p_:
            ces_house(k, p_[0], p_[1], CELL_Z, r, rng)
    for _ in range(max(0, 3 - band)):                                              # droid workshops
        w = rng.uniform(0.12, 0.18)
        p_ = lots.spot(w * 1.2)
        if p_:
            tbox(k, p_[0], p_[1], CELL_Z, 0.14 + 0.03 * band, w, w * 0.6, rng.uniform(0, math.pi), B_CONC, B_ROOF)
    for _ in range(band):                                                          # hive spires
        r = rng.uniform(0.15, 0.22)
        p_ = lots.spot(r * 1.2)
        if p_:
            ces_spire(k, p_[0], p_[1], CELL_Z, rng.uniform(0.45, 0.7) + 0.18 * band, r, rng, lite=True)


def ces_chikatlik(k):
    # ChikatLik, the capital (Legends: the city grew round the X'Ting hives): a cluster of great lobed hive spires on
    # a ragged red rock base, the tallest ~15 high, linked by high walkways, a lower town of rounded clay houses at
    # their feet, a landing platform jutting off the rock with a shuttle. ~15 across
    import random
    rng = random.Random("ces_chikatlik")
    rock(k, 0.0, 0.0, -SKIRT, 0.9, 6.0, rng, [B_SOOT, B_SOOT, B_DUST], lobes=4, sy=0.85)
    spires = [(0.4, 0.6, 15.0, 1.6), (-2.4, -0.4, 11.0, 1.2), (2.6, -1.4, 10.0, 1.1), (-1.0, 2.8, 9.0, 1.0),
              (2.8, 2.2, 8.0, 0.95), (-3.6, 2.0, 6.5, 0.85), (-0.6, -2.8, 7.0, 0.9)]
    for x, y, h, r in spires:
        ces_spire(k, x, y, -SKIRT, h, r, rng)
    for (x0, y0, h0, _), (x1, y1, h1, _) in ((spires[0], spires[1]), (spires[0], spires[2]), (spires[0], spires[3]),
                                             (spires[1], spires[5])):
        z = min(h0, h1) * 0.42
        sweep(k, [(x0, y0, z), ((x0 + x1) / 2, (y0 + y1) / 2, z + 0.4), (x1, y1, z)], rect_section(0.25, 0.2), B_PLATE,
              caps=B_PLATE)
    for _ in range(26):                                                            # the lower town
        a, d = rng.uniform(0, TAU), rng.uniform(3.0, 5.6)
        x, y = d * math.cos(a), d * math.sin(a) * 0.85
        if all(math.hypot(x - sx, y - sy) > sr + 0.6 for sx, sy, _, sr in spires):
            ces_house(k, x, y, -0.5, rng.uniform(0.35, 0.6), rng)
    sweep(k, [(4.6, -3.2, 1.2), (6.4, -4.2, 1.2)], rect_section(0.5, 0.25), B_CONC, caps=B_CONC)
    pad(k, 6.8, -4.4, 1.45, 1.1, B_RUST, B_PAD)
    k.tube((6.8, -4.4, 1.3), (5.4, -3.6, -0.5), 0.16, B_CONC, sides=6)
    shuttle(k, 6.8, -4.4, 1.45, 2.2, 1.6, B_HULL, B_CONC_WIN)


def ces_cybernetics(k):
    # Cestus Cybernetics (Legends: the droid maker that made Ord Cestus rich, builders of the JK-13 self-aware
    # security droid): the corporate headquarters, a battered tan slab tower with a lit crown and a sign band; long
    # sawtooth assembly halls behind it; a test yard where JK droids (dark domed bodies on spidery legs) stand in
    # rows; a shipping pad with a freighter. ~14 across
    import random
    rng = random.Random("ces_cybernetics")
    tbox(k, 0.0, 0.0, -SKIRT, 0.3, 7.0, 4.6, 0.0, B_CONC, B_DUST)
    tbox(k, -3.6, 1.2, 0.3, 11.0, 1.4, 1.0, 0.0, B_CONC_WIN, B_ROOF, wt=1.0, dt=0.7)            # the tower
    tbox(k, -3.6, 1.2, 11.0, 12.0, 1.15, 0.85, 0.0, B_HAZARD, B_ROOF, wt=0.9, dt=0.6)           # its lit crown
    tbox(k, -3.6, 0.15, 8.0, 8.8, 1.25, 0.1, 0.0, B_GLOW, B_GLOW)                                # the sign band
    k.lathe([(0.12, 12.0), (0.06, 14.0)], B_PIPE, sides=4, cx=-3.6, cy=1.2, cap=B_GLOW)
    for i, y in enumerate((2.6, 0.6)):                                                         # assembly halls
        bot_hall(k, 1.6, y, 0.3, 2.2, 3.6, 0.8, 0.0, teeth=6)
    for i in range(3):                                                                         # JK droids in rows
        for j in range(4):
            x, y = -1.2 + j * 1.0, -1.6 - i * 0.8
            for q in range(4):
                a = TAU * q / 4 + 0.4
                k.tube((x, y, 0.55), (x + 0.4 * math.cos(a), y + 0.4 * math.sin(a), 0.3), 0.04, B_DARK, sides=3)
            dome(k, x, y, 0.5, 0.26, 0.3, B_DARK, sides=8, n=2)
    pad(k, 5.0, -2.6, 0.55, 1.3, B_HAZARD, B_PAD)
    shuttle(k, 5.0, -2.6, 0.55, 0.6, 2.2, B_HULL, B_CONC_WIN)


def ces_penitentiary(k):
    # Cestus Penitentiary (Legends: a Republic prison of 321 BBY on land the X'Ting gave, near and under Kibo Lake) and
    # the Kibo Geothermal Station beside it: a stepped grey cell block on a rock island in the lake, its lower levels
    # going down into the water, a walled causeway to the shore with a gatehouse; on the shore the geothermal station's
    # two flared cooling towers, a turbine hall and pipes. ~13 across
    import random
    rng = random.Random("ces_penitentiary")
    rock(k, -1.2, 0.0, -SKIRT, 0.5, 3.4, rng, [B_SOOT] * 3, lobes=3)
    for i, (w, d, z1) in enumerate(((2.4, 1.8, 2.0), (1.8, 1.3, 3.6), (1.1, 0.8, 5.0))):         # the cell block
        tbox(k, -1.2, 0.0, -SKIRT if i == 0 else z1 - 1.6, z1, w, d, 0.0, B_PLATE_WIN, B_ROOF)
    for x, y in ((-3.4, -1.8), (-3.4, 1.8), (1.0, -1.8), (1.0, 1.8)):                           # guard towers
        k.lathe([(0.3, -SKIRT), (0.3, 2.8), (0.5, 3.0), (0.5, 3.5), (0.0, 3.7)], [B_CONC, B_CONC, B_CONC_WIN, B_ROOF],
                sides=8, cx=x, cy=y)
    sweep(k, [(1.4, 0.0, 0.4), (4.0, 0.4, 0.4)], [(0.5, -SKIRT), (0.5, 0.4), (-0.5, 0.4), (-0.5, -SKIRT)],
          [B_CONC, B_DUST, B_CONC], open_sec=True)                                            # the causeway
    for s_ in (-1, 1):
        sweep(k, [(1.4, 0.0 + s_ * 0.5, 0.4), (4.0, 0.4 + s_ * 0.5, 0.4)], rect_section(0.08, 0.6, 0.4), B_CONC,
              caps=B_CONC)
    tbox(k, 4.4, 0.4, -SKIRT, 1.6, 0.6, 0.9, 0.1, B_CONC, B_ROOF)                              # the gatehouse
    for x, y in ((6.0, 2.4), (6.6, -1.6)):                                                     # cooling towers
        k.lathe([(1.5, -SKIRT), (1.4, 0.0), (1.0, 2.6), (0.95, 3.4), (1.1, 4.4)], [B_CONC] * 4, sides=18, cx=x, cy=y)
        k.lathe([(1.1, 4.4), (1.0, 4.35), (0.0, 3.0)], [B_CONC, B_DARK], sides=18, cx=x, cy=y)
    tbox(k, 6.2, 0.4, -SKIRT, 1.4, 1.0, 0.7, 0.0, B_PLATE_WIN, B_ROOF)                         # turbine hall
    for y in (-0.6, 1.4):
        k.tube((5.2, y, 0.6), (3.0, y * 0.3, 0.6), 0.14, B_PIPE, sides=6)


def ces_jantos(k):
    # Jantos (Legends: a large city of Ord Cestus; its look is a design choice): a city on a red butte - flat-roofed
    # clay blocks terraced up its sides, a ring of hive spires on the crest round a broad central spire, a road
    # switching up the slope, a walled lower town. ~13 across
    import random
    rng = random.Random("ces_jantos")
    rock(k, 0.0, 0.0, -SKIRT, 2.6, 5.4, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.9)
    for _ in range(30):                                                            # terraces up the butte
        a, d = rng.uniform(0, TAU), rng.uniform(2.6, 5.0)
        x, y = d * math.cos(a), d * math.sin(a) * 0.9
        z = 2.6 * (1 - (d - 2.6) / 2.6) - 0.2
        tbox(k, x, y, -SKIRT, z + rng.uniform(0.4, 0.8), rng.uniform(0.35, 0.6), rng.uniform(0.3, 0.45), a, B_PLATE_WIN,
             B_ROOF)
    ces_spire(k, 0.0, 0.2, 2.0, 11.0, 1.4, rng)
    for i in range(5):
        a = TAU * i / 5 + 0.3
        ces_spire(k, 2.0 * math.cos(a), 2.0 * math.sin(a) * 0.9, 2.0, rng.uniform(5.0, 7.0), 0.6, rng)
    sweep(k, [(-5.6, -3.0, 0.0), (-3.0, -3.8, 1.0), (-1.2, -3.0, 2.2)], rect_section(0.4, 0.25), B_DUST, caps=B_DUST)
    sq = [(-6.4, 1.0, 0.0), (-6.4, 4.4, 0.0), (-3.0, 5.4, 0.0)]                         # the lower town's wall
    sweep(k, sq, trap_section(0.4, 0.3, 1.2, -0.6), B_PLATE)


def ces_droidworks(k):
    # the Cestus Droid Works at Clandes (an invented name for the droid factories Ord Cestus lived by): two long
    # sawtooth halls, a foundry block with four stacks, droid shells stacked in the yard, storage tanks, a rail spur
    # with freight cars. ~13 across
    import random
    rng = random.Random("ces_droidworks")
    tbox(k, 0.0, 0.0, -SKIRT, 0.3, 6.4, 4.4, 0.0, B_CONC, B_DUST)
    for y in (2.2, 0.2):
        bot_hall(k, -1.2, y, 0.3, 2.0, 4.2, 0.85, 0.0, teeth=7)
    tbox(k, 3.8, 1.2, 0.3, 3.2, 1.4, 1.8, 0.0, B_CONC, B_ROOF)                                 # the foundry
    for y in (0.0, 0.8, 1.6, 2.4):
        bot_chimney(k, 3.8, y, 3.2, 7.0, 0.26)
    for _ in range(14):                                                            # droid shells in the yard
        x, y = rng.uniform(-5.0, 1.0), rng.uniform(-3.6, -1.6)
        dome(k, x, y, 0.3, 0.22, 0.25, B_DARK, sides=8, n=2)
    for x in (3.2, 4.4, 5.6):                                                      # tanks
        k.lathe([(0.5, -SKIRT), (0.5, 1.4), (0.3, 1.7), (0.0, 1.75)], [B_PIPE, B_PIPE, B_PIPE], sides=12, cx=x, cy=-2.6)
    for i in range(4):                                                             # the rail spur, freight cars
        tbox(k, -5.0 + i * 1.5, -4.0, 0.3, 0.9, 0.65, 0.3, 0.0, B_RUST, B_ROOF)
    sweep(k, [(-6.4, -4.0, 0.3), (6.4, -4.0, 0.3)], rect_section(0.35, 0.05, 0.3), B_PIPE, caps=B_PIPE)


def ces_fungus(k):
    # the Barrens fungus farms (Legends: Ord Cestus exported fungi; the farms are a design choice): long half-buried
    # grow vaults in rows, open pits of giant cultivated fungus with broad purple caps, a processing shed, water tanks
    # and a sprayer gantry. ~12 across
    import random
    rng = random.Random("ces_fungus")
    for i in range(4):                                                             # grow vaults
        vault(k, -3.4 + i * 1.5, 1.8, -0.4, TAU / 4, 4.0, 0.6, 0.8, [B_CONC_WIN] * 6, end=B_CONC)
    for cx_, cy_ in ((-2.6, -2.2), (1.4, -2.4)):                                   # fungus pits
        k.lathe([(1.8, 0.1), (1.6, -0.3), (0.0, -0.35)], [B_SOOT, B_DUST], sides=16, cx=cx_, cy=cy_)
        for _ in range(7):
            a, d = rng.uniform(0, TAU), rng.uniform(0.0, 1.3)
            x, y = cx_ + d * math.cos(a), cy_ + d * math.sin(a)
            h, r = rng.uniform(0.8, 2.0), rng.uniform(0.35, 0.6)
            k.lathe([(0.1, -0.3), (0.08, h)], B_CONC, sides=6, cx=x, cy=y)
            k.lathe([(0.06, h - 0.1), (r, h), (r * 0.85, h + 0.15), (0.0, h + 0.28)], [B_BRICK, B_BRICK, B_BRICK], sides=12,
                    cx=x, cy=y)
    tbox(k, 4.4, 1.6, -SKIRT, 1.4, 1.2, 1.0, 0.0, B_CONC, B_ROOF)                              # the shed
    for y in (-0.6, -2.0):
        k.lathe([(0.45, -SKIRT), (0.45, 1.6), (0.0, 1.8)], [B_PIPE, B_PIPE], sides=10, cx=4.6, cy=y)
    for x in (-0.6, 3.4):                                                          # the sprayer gantry
        k.lathe([(0.08, -SKIRT), (0.08, 2.2)], B_GIRDER, sides=4, cx=x, cy=-2.3)
    tbox(k, 1.4, -2.3, 2.1, 2.3, 2.1, 0.12, 0.0, B_GIRDER, B_HAZARD, base=B_GIRDER)


# ==================================================================================================== DATHOMIR
# Dathomir (canon, The Clone Wars: the Nightsister lair, a stone fortress built into a mountain of crooked rock
# spires, lit by green magick; the Nightbrothers' village of rough stone huts among rock spires, and their arena;
# the Nardithi Cluster of hexagonal spikes. Legends: the Singing Mountain clan's walled fortress). Everything under a
# blood-red sky: dark red-grey stone, green-glowing openings, blood-red cloth, bone.
# Atlas hod_dathomir (B_ layout): B_PLATE carved dark stone, B_PLATE_WIN stone with green-lit openings, B_SOOT dark
# rock, B_ROOF dark thatch, B_RUST blood-red cloth, B_BRICK rough stone blocks, B_DUST red earth, B_GLOW magick green,
# B_CONC grey basalt, B_HULL bone, B_GIRDER / B_PIPE dark wood.
def dat_spire(k, x, y, z0, h, r, rng, mats=None, lean=0.25):
    """a crooked rock spire: lobed rings bulging and narrowing, each shifted a little, leaning"""
    ph, la = rng.uniform(0, TAU), rng.uniform(0, TAU)
    lobes = rng.choice((3, 4))
    prof = [(0.0, 1.0), (0.2, 0.75), (0.4, 0.9), (0.6, 0.6), (0.8, 0.5), (0.93, 0.3), (1.0, 0.08)]
    rings = []
    for t, f in prof:
        dx, dy = lean * r * t * math.cos(la) * 2, lean * r * t * math.sin(la) * 2
        rings.append(lobed(x + dx + rng.uniform(-0.08, 0.08) * r, y + dy + rng.uniform(-0.08, 0.08) * r, z0 + (h - z0) * t,
                           r * f, lobes=lobes, amp=0.22, n=14, phase=ph + t))
    loft(k, rings, mats or [B_SOOT] * (len(rings) - 1), cap=B_SOOT)
    return [(rr[0][0] * 0 + sum(p[0] for p in rr) / len(rr), sum(p[1] for p in rr) / len(rr), rr[0][2]) for rr in rings]


def dat_hut(k, x, y, z0, r, rng):
    """a rough stone hut: a low drum of stone blocks under a steep dark thatch cone"""
    g = max(z0, 0.0)
    k.lathe([(r, z0), (r * 0.95, g + r * 0.7)], B_BRICK, sides=8, cx=x, cy=y)
    k.lathe([(r * 1.15, g + r * 0.65), (0.0, g + r * 1.6)], B_ROOF, sides=8, cx=x, cy=y)


def dat_hamlet(k, band, rng):
    # Dathomir's clan villages (the cities.txt 43 set: a few, thinly spread): stone huts with thatch cones in loose
    # rings round a fire, crooked rock spires, a palisade of dark poles hung with red cloth. band 1 .. 4: bigger
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.45, n_min=1)
    for p in paths:
        sweep(k, p, rect_section(0.08, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.1)
    for _ in range(3 + band * 2):                                                  # huts
        r = rng.uniform(0.07, 0.12)
        p_ = lots.spot(r * 1.2)
        if p_:
            dat_hut(k, p_[0], p_[1], CELL_Z, r, rng)
    for _ in range(1 + band // 2):                                                 # rock spires
        r = rng.uniform(0.1, 0.16)
        p_ = lots.spot(r * 1.1)
        if p_:
            dat_spire(k, p_[0], p_[1], CELL_Z, rng.uniform(0.35, 0.55) + 0.08 * band, r, rng)
    for _ in range(band):                                                          # palisade runs, red cloth
        p_ = lots.spot(0.05)
        if p_:
            a = rng.uniform(0, TAU)
            for q in range(5):
                x, y = turn(p_[0], p_[1], a, (q - 2) * 0.05, 0.0)
                k.lathe([(0.012, CELL_Z), (0.01, 0.16 + 0.02 * (q % 2))], B_GIRDER, sides=4, cx=x, cy=y)
            tbox(k, p_[0], p_[1], 0.08, 0.15, 0.1, 0.004, a, B_RUST, B_RUST)


def dat_lair(k):
    # the Nightsister lair (canon, "Nightsisters" / "Massacre": a stone fortress built into the side of a mountain,
    # home of Mother Talzin, the Hidden Cave below): a mass of crooked red-grey rock spires, the tallest ~16 high,
    # carved with stacked stone chambers whose openings glow green, stone bridges and stairs between the spires, the
    # great arched gate at the foot, the ritual terrace with a green pool before it, gnarled trees. ~15 across
    import random
    rng = random.Random("dat_lair")
    rock(k, 0.0, 0.0, -SKIRT, 1.4, 6.2, rng, [B_SOOT, B_SOOT, B_DUST], lobes=4, sy=0.85)
    spires = [(0.6, 1.2, 16.0, 2.0), (-2.6, 0.4, 12.0, 1.6), (2.8, -0.4, 11.0, 1.4), (-0.8, 3.4, 10.0, 1.3),
              (3.0, 2.8, 8.5, 1.1), (-3.6, 2.6, 7.0, 1.0), (-1.4, -1.6, 6.0, 1.0)]
    axes = [dat_spire(k, x, y, -SKIRT, h, r, rng) for x, y, h, r in spires]
    for (x, y, h, r), ax in zip(spires, axes):                                     # carved chambers on the spires
        for t in (2, 3, 4):
            cx, cy, cz = ax[t]
            a = math.atan2(cy - 0.0, cx - 0.0) if (cx, cy) != (0.0, 0.0) else 0.0
            w = r * 0.55 * (1.2 - 0.25 * t / 4)
            px, py = turn(cx, cy, a, r * 0.55, 0.0)
            tbox(k, px, py, cz - 0.5, cz + 0.6, w * 0.6, w, a, B_PLATE_WIN, B_PLATE, wt=w * 0.5, dt=w * 0.8)
    for i, j in ((0, 1), (0, 2), (0, 3), (1, 5), (2, 4)):                          # bridges between them
        (x0, y0, z0_), (x1, y1, z1_) = axes[i][2], axes[j][2]
        z = min(z0_, z1_)
        sweep(k, [(x0, y0, z), ((x0 + x1) / 2, (y0 + y1) / 2, z - 0.5), (x1, y1, z)], rect_section(0.35, 0.25), B_PLATE,
              caps=B_PLATE)
    vault(k, 0.4, -2.8, -0.5, TAU / 4, 2.2, 1.0, 2.6, [B_PLATE] * 6, end=B_DARK)        # the gate
    for s_ in (-1, 1):
        k.lathe([(0.45, -SKIRT), (0.4, 3.6), (0.0, 4.4)], [B_PLATE, B_PLATE], sides=6, cx=0.4 + s_ * 1.3, cy=-2.9)
        k.lathe([(0.2, 3.6), (0.2, 3.9)], B_GLOW, sides=6, cx=0.4 + s_ * 1.3, cy=-2.9, cap=B_GLOW)
    k.lathe([(2.0, 1.45), (1.9, 1.5)], B_PLATE, sides=18, cx=-1.6, cy=-3.8, cap=B_PLATE)            # ritual terrace
    k.lathe([(0.8, 1.52), (0.8, 1.56)], B_GLOW, sides=14, cx=-1.6, cy=-3.8, cap=B_GLOW)           # the green pool
    for q in range(6):
        a = TAU * q / 6
        k.lathe([(0.12, 1.5), (0.08, 2.4)], B_HULL, sides=4, cx=-1.6 + 1.6 * math.cos(a), cy=-3.8 + 1.6 * math.sin(a))


def dat_village(k):
    # the Nightbrother village (canon, "Monster": the Zabrak warriors' village, built into the rock among spires):
    # rough stone huts with dark thatch cones clustered on rock shelves round three tall crooked spires, the chieftain's
    # long hall cut into the largest, rope-and-pole bridges, a palisade with red banners, the training ground. ~14
    # across
    import random
    rng = random.Random("dat_village")
    rock(k, 0.0, 0.0, -SKIRT, 0.6, 6.0, rng, [B_SOOT, B_DUST, B_DUST], lobes=3, sy=0.8)
    spires = [(1.4, 1.0, 11.0, 1.6), (-2.2, 1.6, 8.5, 1.3), (2.6, -2.4, 7.0, 1.1)]
    axes = [dat_spire(k, x, y, -SKIRT, h, r, rng) for x, y, h, r in spires]
    for (x, y, h, r), ax in zip(spires, axes):                                     # shelves with huts on the spires
        for t in (2, 4):
            cx, cy, cz = ax[t]
            k.lathe([(r * 1.25, cz - 0.3), (r * 1.3, cz)], B_PLATE, sides=10, cx=cx, cy=cy, cap=B_PLATE)
            for q in range(3):
                a = TAU * q / 3 + t
                dat_hut(k, cx + r * 1.0 * math.cos(a), cy + r * 1.0 * math.sin(a), cz, 0.32, rng)
    tbox(k, 1.0, -0.2, 0.4, 2.0, 1.4, 0.6, 0.3, B_PLATE_WIN, B_ROOF)                            # the long hall
    prism_at(k, 1.0, -0.2, 2.0, 0.3, 2.8, [(0.7, 0.0), (0.0, 0.8), (-0.7, 0.0)], [B_ROOF] * 3, end=B_PLATE)
    for _ in range(18):                                                            # huts on the ground
        a, d = rng.uniform(0, TAU), rng.uniform(2.6, 5.4)
        x, y = d * math.cos(a), d * math.sin(a) * 0.8
        if all(math.hypot(x - sx, y - sy) > sr + 0.5 for sx, sy, _, sr in spires):
            dat_hut(k, x, y, -0.4, rng.uniform(0.4, 0.6), rng)
    for (x0, y0, z0_), (x1, y1, z1_) in ((axes[0][3], axes[1][3]), (axes[0][3], axes[2][3])):   # rope bridges
        z = min(z0_, z1_)
        curve_tube(k, (x0, y0, z), (x1, y1, z), -0.6, 0.12, 0.12, B_GIRDER, n=8, sides=4)
    for q in range(16):                                                            # the palisade with red banners
        a = -0.6 + 1.8 * q / 15
        x, y = 5.6 * math.cos(a + math.pi), 5.6 * math.sin(a + math.pi) * 0.8
        k.lathe([(0.1, -SKIRT), (0.08, 1.6), (0.0, 1.9)], [B_GIRDER, B_GIRDER], sides=4, cx=x, cy=y)
        if q % 4 == 0:
            tbox(k, x, y, 0.6, 1.5, 0.02, 0.3, a, B_RUST, B_RUST)


def dat_arena(k):
    # the Nightbrother arena (canon: by the village, where Savage Opress was chosen): a sunken round fighting floor of
    # red earth inside a ring of stepped stone tiers, crooked rock spires round the rim, a chieftain's dais with bone
    # trophies, braziers. ~9 across
    import random
    rng = random.Random("dat_arena")
    k.lathe([(4.6, -SKIRT), (4.4, 0.8), (3.2, 1.2), (2.9, 0.7), (2.6, 0.3), (2.3, -0.1), (2.0, -0.4)],
            [B_SOOT, B_PLATE, B_BRICK, B_PLATE, B_BRICK, B_PLATE], sides=24)           # the tiers, stepping down
    k.lathe([(2.0, -0.4), (0.0, -0.42)], B_DUST, sides=24)                              # the floor
    for q in range(5):
        a = TAU * q / 5 + 0.4
        dat_spire(k, 3.9 * math.cos(a), 3.9 * math.sin(a), -SKIRT, rng.uniform(3.5, 5.5), 0.6, rng)
    tbox(k, 0.0, 3.4, 0.8, 1.6, 0.9, 0.6, 0.0, B_PLATE, B_PLATE)                               # the dais
    for s_ in (-0.6, 0.6):
        k.lathe([(0.1, 1.6), (0.06, 2.6)], B_HULL, sides=4, cx=s_, cy=3.5)
        dome(k, s_, 3.5, 2.6, 0.18, 0.2, B_HULL, sides=6, n=2)
    for a in (1.2, 2.4, 3.9, 5.2):                                                 # braziers
        x, y = 3.0 * math.cos(a), 3.0 * math.sin(a)
        k.lathe([(0.15, 1.2), (0.25, 1.6), (0.2, 1.7)], [B_PLATE, B_GLOW], sides=6, cx=x, cy=y, cap=B_GLOW)


def dat_singing(k):
    # the Singing Mountain clan's fortress (Legends, "The Courtship of Princess Leia": the witches' stronghold high on
    # Singing Mountain, its walls of rough stone, rancor pens below): a tall ragged mountain, a curtain wall of stone
    # blocks round its shoulder with squat round towers, stone halls with thatch roofs inside, a gate and a winding
    # path up, the rancor pen walled at the foot. ~14 across
    import random
    rng = random.Random("dat_singing")
    rock(k, 0.0, 0.0, -SKIRT, 3.4, 6.4, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4, sy=0.9)
    dat_spire(k, 0.6, 0.8, 3.0, 11.5, 2.4, rng, lean=0.12)                          # the summit
    ring_ = [(3.8 * math.cos(TAU * q / 9) - 0.2, 3.2 * math.sin(TAU * q / 9), 3.2) for q in range(9)]
    sweep(k, ring_, trap_section(0.55, 0.4, 1.5, -0.4), B_BRICK, closed_path=True)     # the curtain wall
    for x, y, _z in ring_[::2]:
        k.lathe([(0.6, 2.6), (0.6, 5.2), (0.75, 5.3), (0.0, 6.4)], [B_BRICK, B_BRICK, B_ROOF], sides=10, cx=x, cy=y)
    for x, y, a in ((-1.6, -1.0, 0.3), (1.8, -1.4, -0.4), (-2.0, 1.4, 1.2)):        # halls inside
        tbox(k, x, y, 2.8, 4.2, 0.9, 0.5, a, B_PLATE_WIN, B_ROOF)
        prism_at(k, x, y, 4.2, a, 1.9, [(0.55, 0.0), (0.0, 0.7), (-0.55, 0.0)], [B_ROOF] * 3, end=B_BRICK)
    vault(k, 0.6, -3.4, 3.0, TAU / 4, 1.0, 0.6, 1.4, [B_BRICK] * 6, end=B_DARK)      # the gate
    sweep(k, [(0.6, -3.6, 3.0), (2.8, -4.6, 1.8), (4.6, -3.6, 0.6), (5.8, -5.0, 0.0)], rect_section(0.35, 0.2), B_DUST,
          caps=B_DUST)                                                            # the path up
    pen = [(-3.6, -4.2, 0.0), (-1.4, -5.2, 0.0), (-2.2, -6.6, 0.0), (-4.6, -6.0, 0.0)]
    sweep(k, pen, trap_section(0.4, 0.3, 1.4, -0.4), B_BRICK, closed_path=True)      # the rancor pen


def dat_hexcol(k, x, y, z0, h, r, top=B_CONC):
    """a hexagonal basalt column"""
    k.lathe([(r, z0), (r, h)], B_SOOT, sides=6, cx=x, cy=y, cap=top)


def dat_nardithi(k):
    # the Nardithi Cluster (canon: a collection of hexagonal spikes on Dathomir; Oteroa Zero-Twenty later stood in the
    # jungle near it): a great field of hexagonal basalt columns packed edge to edge, rising in steps to a core of tall
    # leaning spikes (~12 high) with sheared tops, a few broken columns lying among them. ~15 across
    import random
    rng = random.Random("dat_nardithi")
    r = 0.42
    for i in range(-11, 12):                                                       # the packed hex field
        for j in range(-9, 10):
            x, y = i * r * 1.5, (j + 0.5 * (i % 2)) * r * math.sqrt(3)
            d = math.hypot(x, y * 1.15) + rng.uniform(-0.6, 0.6)
            if d > 7.2:
                continue
            h = max(0.2, 9.0 * math.exp(-(d / 3.2) ** 2) + rng.uniform(-0.4, 0.8))
            if d < 2.4 and rng.random() < 0.5:                                     # the core's spikes
                tilt = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6))
                hh = h + rng.uniform(1.0, 3.0)
                k.lathe([(r * 0.98, -SKIRT), (r * 0.98, h), (r * 0.6, hh), (0.05, hh + 0.6)], [B_SOOT, B_SOOT, B_CONC],
                        sides=6, cx=x, cy=y)
                continue
            dat_hexcol(k, x, y, -SKIRT, h, r * 0.98)
    for _ in range(5):                                                             # broken columns lying around
        a, d = rng.uniform(0, TAU), rng.uniform(6.0, 7.4)
        x, y = d * math.cos(a), d * math.sin(a)
        b = rng.uniform(0, TAU)
        k.tube((x, y, 0.3), (x + 2.0 * math.cos(b), y + 2.0 * math.sin(b), 0.3), r, B_SOOT, sides=6)


# ==================================================================================================== MANDALORE
# Mandalore (canon, The Clone Wars: Sundari, the New Mandalorians' domed capital of cube-shaped white buildings with
# the Duchess's Royal Palace, set in the white desert left by the ancient wars; Legends: Keldabe on a flat granite
# hill by the Kelita River, its hundred-metre MandalMotors tower; beskar; Death Watch, the warrior exiles).
# Atlas hod_mandalore (B_ layout): B_PLATE white panels with gold lines, B_PLATE_WIN white with window grids, B_CONC
# grey granite, B_CONC_WIN pale glass, B_RUST Mandalorian red, B_SOOT granite rock, B_ROOF dark slate, B_HAZARD Death
# Watch blue, B_GIRDER gold lattice, B_HULL beskar, B_BRICK Keldabe stone and timber, B_DUST white sand.
def man_cube(k, x, y, z0, s, h, a, rng, lite=False):
    """a Sundari block: a white cube, sometimes a smaller cube set on it, a gold lattice band, a glass roof light"""
    tbox(k, x, y, z0, h, s, s, a, B_PLATE_WIN, B_PLATE)
    if not lite and rng.random() < 0.5:
        s2 = s * rng.uniform(0.5, 0.7)
        tbox(k, x, y, h, h + s2 * 1.4, s2, s2, a + 0.0, B_PLATE_WIN, B_PLATE)
        h = h + s2 * 1.4
    tbox(k, x, y, h, h + s * 0.08, s * 0.5, s * 0.5, a, B_CONC_WIN, B_CONC_WIN)


def man_dome(k, band, rng):
    # Mandalore's domed cities and desert outposts: straight white streets, white cube blocks with gold bands, small
    # glass domes over courts, a few taller cube towers downtown. band 1 outskirts .. 4 downtown
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.15, curvy=False)
    for p in paths:
        sweep(k, [p[0], p[-1]], rect_section(0.13 + 0.02 * band, 0.315, CELL_Z), [B_DUST, B_PLATE, B_DUST], open_sec=True)
        lots.block_path(p, 0.17 + 0.02 * band)
    a0 = rng.uniform(0, math.pi / 2)
    for _ in range(band + 4):                                                      # cube blocks
        s = rng.uniform(0.08, 0.14)
        p_ = lots.along(rng.choice(paths), s * 1.3, 0.09) or lots.spot(s * 1.3)
        if p_:
            man_cube(k, p_[0], p_[1], CELL_Z, s, rng.uniform(0.12, 0.25) + 0.06 * band, a0, rng)
    for _ in range(1 + band // 2):                                                 # glass domes
        r = rng.uniform(0.08, 0.12)
        p_ = lots.spot(r * 1.1)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.05)], B_PLATE, sides=10, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.05, r, r * 0.8, [B_CONC_WIN, B_CONC_WIN, B_GIRDER], sides=10, n=3)
    for _ in range(band - 1):                                                      # cube towers
        s = rng.uniform(0.07, 0.1)
        p_ = lots.spot(s * 1.5)
        if p_:
            man_cube(k, p_[0], p_[1], CELL_Z, s, rng.uniform(0.35, 0.5) + 0.1 * band, a0, rng)


def man_house(k, x, y, z0, w, d, h, a):
    """a clan house: stone and timber walls under a steep dark slate roof"""
    tbox(k, x, y, z0, h, w, d, a, B_BRICK, B_ROOF)
    prism_at(k, x, y, h, a, 2 * w, [(d * 1.1, 0.0), (0.0, d * 1.1), (-d * 1.1, 0.0)], [B_ROOF] * 3, end=B_BRICK)


def man_town(k, band, rng):
    # the clan towns of the green north (Keldabe's districts, Bralsin, Norg Bral): winding lanes, stone and timber
    # houses under steep slate roofs, round watch towers, a walled yard. band 1 hamlet .. 4 town centre
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.35)
    for p in paths:
        sweep(k, p, rect_section(0.1 + 0.02 * band, 0.315, CELL_Z), [B_CONC, B_DUST, B_CONC], open_sec=True)
        lots.block_path(p, 0.14 + 0.02 * band)
    for _ in range(3 + band * 2):                                                  # houses
        w = rng.uniform(0.07, 0.12)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.08) or lots.spot(w * 1.1)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            man_house(k, p_[0], p_[1], CELL_Z, w, w * 0.6, rng.uniform(0.1, 0.16) + 0.03 * band, a)
    for _ in range(max(1, band // 2)):                                             # watch towers
        r = rng.uniform(0.05, 0.07)
        p_ = lots.spot(r * 1.4)
        if p_:
            h = rng.uniform(0.35, 0.5) + 0.1 * band
            k.lathe([(r, CELL_Z), (r, h), (r * 1.3, h + 0.02), (0.0, h + r * 2.2)], [B_BRICK, B_BRICK, B_ROOF], sides=8,
                    cx=p_[0], cy=p_[1])


def man_sundari(k):
    # Sundari, the capital (canon, The Clone Wars: a city of cube-shaped buildings inside a dome on the white desert,
    # the Royal Palace of Duchess Satine at its heart): a low square base wall of glass panels round the city, a dome
    # of gold lattice ribs (open, so the city shows), packed white cube blocks inside, the Royal Palace a tall stack of
    # set-back cubes with a great glass front facing its plaza, landing pads on the wall for the transports. ~16 across
    import random
    rng = random.Random("man_sundari")
    R = 7.0
    base = rrect(0.0, 0.0, 0.0, R, R, 2.2, 0.0, 4)
    loft(k, [at_z(base, -SKIRT), at_z(base, 1.6), scaled(at_z(base, 1.8), 0.97)], [B_CONC_WIN, B_PLATE], cap=B_DUST)
    for q in range(8):                                                             # the dome's ribs
        a = TAU * q / 8
        ca, sa = math.cos(a), math.sin(a)
        rr = R * (1.22 if q % 2 else 1.0) * 0.97              # odd ribs run to the corners
        pts = []
        for i in range(10):
            t = math.pi / 2 * i / 9
            pts.append((rr * math.cos(t) * ca, rr * math.cos(t) * sa, 1.8 + 9.0 * math.sin(t)))
        for p0, p1 in zip(pts, pts[1:]):
            k.tube(p0, p1, 0.16, B_GIRDER, sides=5)
    for z in (4.8, 7.8):                                                           # hoops round the ribs
        t = math.asin((z - 1.8) / 9.0)
        hoop = rrect(0.0, 0.0, z, R * 0.97 * math.cos(t), R * 0.97 * math.cos(t), 2.2 * math.cos(t), 0.0, 3)
        for p0, p1 in zip(hoop, hoop[1:] + hoop[:1]):
            k.tube(p0, p1, 0.1, B_GIRDER, sides=4)
    k.lathe([(0.6, 10.6), (0.4, 11.0), (0.0, 11.2)], [B_GIRDER, B_GIRDER], sides=8)                # the crown
    lots = Lots(rng, R - 0.8)
    lots.take(0.0, 0.6, 2.4)                                                       # the palace and its plaza
    lots.take(0.0, -2.0, 1.0)
    for _ in range(60):                                                            # the cube blocks
        s = rng.uniform(0.45, 0.8)
        p_ = lots.spot(s * 1.25, tries=20)
        if p_:
            man_cube(k, p_[0], p_[1], 1.8, s, 1.8 + rng.uniform(0.8, 2.8) * (1.4 - math.hypot(*p_) / R), 0.0, rng)
    for i, (s, z1) in enumerate(((2.2, 4.6), (1.7, 6.8), (1.2, 8.6))):            # the Royal Palace
        tbox(k, 0.0, 0.8, 1.8 if i == 0 else z1 - 2.2, z1, s, s, 0.0, B_PLATE_WIN, B_PLATE)
    tbox(k, 0.0, -1.42, 2.4, 6.4, 1.3, 0.06, 0.0, B_CONC_WIN, B_CONC_WIN)                      # the great window
    tbox(k, 0.0, 0.8, 8.6, 8.8, 1.3, 1.3, 0.0, B_GIRDER, B_GIRDER)
    tbox(k, 0.0, -2.0, 1.8, 1.85, 0.9, 0.9, 0.0, B_PLATE, B_DUST)                               # the plaza
    for x, y in ((R - 0.2, -R * 0.6), (-R + 0.2, R * 0.5)):                        # pads on the wall
        pad(k, x * 1.08, y, 1.8, 1.0, B_RUST, B_PAD)
        shuttle(k, x * 1.08, y, 1.8, 0.4, 1.7, B_PLATE, B_CONC_WIN)


def man_keldabe(k):
    # Keldabe (Legends: on a flat granite hill in a bend of the Kelita River; the MandalMotors headquarters tower, a
    # hundred metres tall, and the Oyu'baat inn): a steep flat-topped granite hill, the town's stone and timber houses
    # packed on its top and stepping down one flank, a ring wall with round towers, the MandalMotors tower rising from
    # the middle with its T-visor crown, the Oyu'baat a long hall on the square, a bridge down to the river. ~14 across
    import random
    rng = random.Random("man_keldabe")
    hill = lobed(0.0, 0.0, 0.0, 6.0, lobes=4, amp=0.14, n=28, phase=0.4, sy=0.85)
    loft(k, [at_z(hill, -SKIRT), at_z(scaled(hill, 0.92), 1.6), at_z(scaled(hill, 0.82), 3.0),
             at_z(scaled(hill, 0.8), 3.1)], [B_SOOT, B_SOOT, B_CONC], cap=B_CONC)
    top = scaled(hill, 0.78)
    sweep(k, [(x, y, 3.1) for x, y, _z in top[::2]], trap_section(0.3, 0.22, 0.8, -0.2), B_BRICK, closed_path=True)
    for x, y, _z in top[::5]:
        k.lathe([(0.35, 2.8), (0.35, 4.6), (0.45, 4.7), (0.0, 5.6)], [B_BRICK, B_BRICK, B_ROOF], sides=8, cx=x, cy=y)
    lots = Lots(rng, 4.0)
    lots.take(0.4, 0.2, 1.5)
    lots.take(-1.6, -1.4, 1.2)
    for _ in range(36):                                                            # houses on the top
        w = rng.uniform(0.4, 0.7)
        p_ = lots.spot(w * 1.1, tries=20)
        if p_ and math.hypot(p_[0], p_[1] / 0.85) < 4.2:
            man_house(k, p_[0], p_[1], 2.8, w, w * 0.6, 3.1 + rng.uniform(0.6, 1.1), rng.uniform(0, math.pi))
    for i in range(10):                                                            # houses down the south flank
        a = -math.pi / 2 + (i - 4.5) * 0.18
        d = 5.4
        man_house(k, d * math.cos(a), d * math.sin(a) * 0.85, -SKIRT, 0.5, 0.35, 1.0 + 0.3 * (i % 3), a + math.pi / 2)
    # the MandalMotors tower: a tapering hexagonal shaft, a T-visor crown (a dark T slot in a helmet-shaped head)
    k.lathe([(1.3, 2.8), (1.0, 8.0), (0.8, 12.0)], [B_PLATE_WIN, B_PLATE_WIN], sides=6, cx=0.4, cy=0.2)
    k.lathe([(0.8, 12.0), (1.15, 12.4), (1.15, 14.0), (0.9, 14.6), (0.0, 14.8)], [B_HULL, B_HULL, B_HULL, B_HULL], sides=12,
            cx=0.4, cy=0.2)
    tbox(k, 0.4, 0.2 - 1.13, 13.2, 13.5, 0.75, 0.05, 0.0, B_DARK, B_DARK)                      # the T: the brow slot
    tbox(k, 0.4, 0.2 - 1.13, 12.3, 13.2, 0.18, 0.05, 0.0, B_DARK, B_DARK)                      # and the stem
    k.lathe([(0.06, 14.8), (0.04, 16.6)], B_PIPE, sides=4, cx=0.4, cy=0.2, cap=B_GLOW)
    tbox(k, -1.6, -1.4, 2.8, 4.0, 1.1, 0.55, 0.3, B_BRICK, B_ROOF)                              # the Oyu'baat
    prism_at(k, -1.6, -1.4, 4.0, 0.3, 2.3, [(0.65, 0.0), (0.0, 0.7), (-0.65, 0.0)], [B_ROOF] * 3, end=B_BRICK)
    sweep(k, [(3.8, 3.0, 3.0), (5.6, 4.6, 1.2), (7.2, 5.6, 0.4)], rect_section(0.35, 0.2), B_CONC, caps=B_CONC)   # bridge


def man_beskar(k):
    # the beskar mines (the user's choice of site; canon: beskar is mined on Mandalore): a deep stepped open pit cut
    # into the badlands, a ramp spiralling down, a headframe over a shaft on the rim, conveyors to a smelter with
    # stacks and a yard of beskar ingots, haul trucks. ~14 across
    import random
    rng = random.Random("man_beskar")
    steps = [(6.4, 0.6), (6.2, 0.6), (5.2, 0.0), (5.0, 0.0), (4.0, -0.8), (3.8, -0.8), (2.8, -1.6), (2.6, -1.6),
             (1.6, -2.3), (0.0, -2.4)]
    k.lathe(steps, [B_SOOT, B_DUST, B_SOOT, B_DUST, B_SOOT, B_DUST, B_SOOT, B_DUST, B_DUST], sides=24, cx=-1.0, cy=0.0, sy=0.85)
    k.lathe([(7.4, -SKIRT), (7.0, 0.5), (6.4, 0.6)], [B_SOOT, B_DUST], sides=24, cx=-1.0, cy=0.0, sy=0.85)
    for i in range(14):                                                            # the haul ramp
        t0, t1 = i / 14, (i + 1) / 14
        r0, r1 = 6.0 - 4.0 * t0, 6.0 - 4.0 * t1
        a0, a1 = 1.6 * TAU * t0, 1.6 * TAU * t1
        sweep(k, [(-1.0 + r0 * math.cos(a0), 0.85 * r0 * math.sin(a0), 0.4 - 2.6 * t0),
                  (-1.0 + r1 * math.cos(a1), 0.85 * r1 * math.sin(a1), 0.4 - 2.6 * t1)], rect_section(0.3, 0.1), B_DUST)
    legs(k, 5.6, 3.6, -SKIRT, 5.0, 1.0, 0.4, 4, 0.1, B_GIRDER)                     # the headframe
    k.lathe([(0.6, 4.6), (0.6, 5.0)], B_RUST, sides=10, cx=5.6, cy=3.6, cap=B_RUST)
    tbox(k, 5.4, -3.2, -SKIRT, 2.4, 1.2, 1.0, 0.2, B_CONC, B_ROOF)                              # the smelter
    for x in (4.8, 5.8):
        bot_chimney(k, x, -2.8, 2.4, 6.4, 0.28)
    sweep(k, [(3.4, -0.4, 0.4), (5.0, -2.4, 2.2)], rect_section(0.25, 0.25), B_GIRDER, caps=B_RUST)
    sweep(k, [(5.6, 3.0, 2.6), (5.6, -2.2, 2.2)], rect_section(0.25, 0.25), B_GIRDER, caps=B_RUST)
    for i in range(3):                                                             # beskar ingots
        for j in range(4):
            tbox(k, 3.0 + j * 0.45, -4.6 + i * 0.3, 0.4, 0.62, 0.18, 0.1, 0.0, B_HULL, B_HULL)
    for x, y, a in ((2.6, 2.6, 0.8), (-4.0, 4.6, -0.3)):                           # haul trucks
        tbox(k, x, y, 0.4, 1.0, 0.7, 0.35, a, B_RUST, B_RUST)


def man_dwcamp(k):
    # a Death Watch camp (the user's choice of site; canon: Death Watch, the Mandalorian warrior exiles under Pre
    # Vizsla): hidden in a rocky outcrop of the wastes - prefab shelters and tents in the lee of the rocks, a command
    # shelter with a comm mast and dish, weapon racks, a training ring, a landing pad with a Kom'rk-style fighter, the
    # Death Watch sigil on a banner. ~11 across
    import random
    rng = random.Random("man_dwcamp")
    for x, y, h, r in ((-3.4, 2.4, 4.2, 2.4), (2.6, 3.2, 3.0, 2.0), (-2.6, -3.0, 2.4, 1.6)):
        rock(k, x, y, -SKIRT, h, r, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3)
    for x, y, a in ((-0.8, 1.4, 0.3), (0.8, 1.6, -0.2), (-1.8, -0.4, 1.2)):         # prefab shelters
        vault(k, x, y, 0.0, a, 1.8, 0.55, 0.7, [B_CONC] * 6, end=B_HAZARD)
    tbox(k, 1.0, -0.6, -SKIRT, 1.2, 0.9, 0.7, 0.2, B_PLATE_WIN, B_ROOF)                        # command shelter
    k.lathe([(0.06, 1.2), (0.04, 5.2)], B_PIPE, sides=4, cx=1.4, cy=-0.4, cap=B_GLOW)
    k.lathe([(0.1, 3.6), (0.9, 4.0), (1.0, 4.3)], [B_PLATE, B_PLATE], sides=12, cx=1.4, cy=-0.4, rot=0.4)
    for q in range(5):                                                             # tents
        x, y = -4.2 + q * 0.9, -0.8 + (q % 2) * 0.7
        prism_at(k, x, y, 0.0, 0.2, 0.9, [(0.35, 0.0), (0.0, 0.45), (-0.35, 0.0)], [B_ROOF] * 3, end=B_ROOF)
    k.lathe([(1.0, 0.02), (1.0, 0.06)], B_DUST, sides=14, cx=-1.0, cy=-2.0, cap=B_DUST)       # training ring
    for q in range(8):
        a = TAU * q / 8
        k.lathe([(0.05, 0.0), (0.05, 0.5)], B_GIRDER, sides=4, cx=-1.0 + math.cos(a), cy=-2.0 + math.sin(a))
    for x in (2.6, 3.0):                                                           # weapon racks
        tbox(k, x, 0.8, 0.0, 0.5, 0.05, 0.4, 0.0, B_GIRDER, B_GIRDER)
    pad(k, 3.4, -2.6, 0.5, 1.4, B_HAZARD, B_PAD)
    k.lathe([(1.2, -SKIRT), (1.2, 0.35)], B_CONC, sides=14, cx=3.4, cy=-2.6)
    shuttle(k, 3.4, -2.6, 0.5, 2.6, 2.2, B_HULL, B_CONC_WIN)
    for s_ in (-1, 1):                                                             # its swept wings, Kom'rk style
        x0, y0 = turn(3.4, -2.6, 2.6, -0.2, 0.0)
        x1, y1 = turn(3.4, -2.6, 2.6, -0.7, s_ * 1.1)
        k.tube((x0, y0, 0.75), (x1, y1, 1.15), 0.08, B_HULL, sides=4, r1=0.04)
    k.lathe([(0.05, 0.0), (0.04, 3.0)], B_PIPE, sides=4, cx=-0.2, cy=3.2)          # the banner
    tbox(k, 0.25, 3.2, 1.8, 2.9, 0.45, 0.02, 0.0, B_HAZARD, B_HAZARD)


# ==================================================================================================== TARIS
# Taris (canon: a city-world again; the wealthy in massive guarded towers, middle-class cities round them, tenements of
# shipping containers and crashed starships stacked under yellow smog, Talinn overgrown with vines; Legends: the
# Upper City's spires over the Lower City and the Undercity, the Jedi Tower at Highport, the swoop races).
# Atlas hod_taris (B_ layout): B_PLATE pale blue-grey plate, B_PLATE_WIN dark slots of pale-green lit windows,
# B_HAZARD neon signs, B_CONC grimy concrete,
# B_CONC_WIN blue glass, B_RUST container steel, B_BRICK container stripes, B_SOOT grime and ruin, B_GLOW cyan neon,
# B_HAZARD yellow-black, B_HULL ship hull.
def tar_tower(k, x, y, z0, h, w, d, a, rng, lite=False, ring=False, pad_top=False):
    """a KOTOR Upper City tower (the user's still, 2026-10-19): a massive capsule-plan shaft of pale blue-grey plate
    with a rounded top, a dark vertical slot of lit windows down its faces, standing on a bulging podium ringed with a
    glowing slit band; `ring` adds a platform ring with a glowing rim round the shaft, `pad_top` a landing pad"""
    g = max(z0, 0.0)
    H = h - g
    seg = 2 if lite else 3
    rr = lambda f, z: rrect(x, y, z, w * f, d * f, min(w, d) * f * 0.95, a, seg)
    loft(k, [rr(1.32, z0), rr(1.32, g + H * 0.12), rr(1.24, g + H * 0.125), rr(1.24, g + H * 0.15),
             rr(1.32, g + H * 0.155), rr(1.3, g + H * 0.2), rr(1.0, g + H * 0.21)],
         [B_PLATE, B_PLATE, B_GLOW, B_PLATE, B_PLATE, B_ROOF])                     # the podium, a glowing slit
    top = h if not pad_top else g + H * 0.92
    loft(k, [rr(1.0, g + H * 0.2), rr(0.97, top - H * 0.09), rr(0.85, top - H * 0.02), rr(0.6 if pad_top else 0.5, top)],
         [B_PLATE, B_PLATE, B_ROOF], cap=B_ROOF)                                  # the shaft
    for s_ in ((1,) if lite else (1, -1)):                                        # the window slots
        sx, sy = turn(x, y, a, 0.0, s_ * d * 0.97)
        tbox(k, sx, sy, g + H * 0.24, top - H * 0.12, w * 0.2, d * 0.06, a, B_PLATE_WIN, B_PLATE_WIN)
    if ring:                                                                      # a platform ring
        zr = g + H * 0.62
        loft(k, [rr(1.0, zr - H * 0.02), rr(1.55, zr), rr(1.55, zr + H * 0.012), rr(1.0, zr + H * 0.02)],
             [B_PLATE, B_GLOW, B_ROOF])
    if pad_top:
        pad(k, x, y, top + 0.02, max(w, d) * 0.9, B_GLOW, B_PAD, sides=12)
    elif not lite:
        for s_ in (-1, 1):
            k.lathe([(w * 0.04, h - H * 0.02), (0.0, h + H * 0.08)], B_PIPE, sides=4, cx=x + s_ * w * 0.3, cy=y)


def tar_twin(k, x, y, z0, h, w, a, rng, lite=False):
    """twin capsule towers joined high up by a rounded sky lobby with a glowing band"""
    g = max(z0, 0.0)
    pts = [turn(x, y, a, s_ * w * 1.7, 0.0) for s_ in (-1, 1)]
    for (px, py), f in zip(pts, (1.0, 0.86)):
        tar_tower(k, px, py, z0, g + (h - g) * f, w, w * 0.75, a, rng, lite=lite)
    zl = g + (h - g) * 0.6
    ring = lambda z, f: rrect(x, y, z, w * 1.9 * f, w * 0.6 * f, w * 0.55 * f, a, 2)
    loft(k, [ring(zl, 0.9), ring(zl + (h - g) * 0.02, 1.0), ring(zl + (h - g) * 0.07, 1.0), ring(zl + (h - g) * 0.08, 0.9)],
         [B_PLATE, B_PLATE_WIN, B_GLOW], cap=B_ROOF, base=B_PLATE)


def tar_ribbon(k, x, y, z0, h, L, w, a):
    """a long low Upper City building: a stadium plan whose front slopes back in a rounded shoulder, slit windows in a
    dark band, a glowing strip along its foot"""
    g = max(z0, 0.0)
    H = h - g
    st = lambda z, fw, fl: rrect(x, y, z, L * fl, w * fw, w * fw * 0.9, a, 2)
    loft(k, [st(z0, 1.0, 1.0), st(g + H * 0.08, 1.0, 1.0), st(g + H * 0.1, 0.97, 0.99), st(g + H * 0.45, 0.97, 0.99),
             st(g + H * 0.55, 1.0, 1.0), st(g + H * 0.62, 1.0, 1.0), st(g + H * 0.9, 0.7, 0.96), st(h, 0.45, 0.92)],
         [B_PLATE, B_GLOW, B_PLATE_WIN, B_PLATE, B_PLATE, B_PLATE, B_ROOF], cap=B_ROOF)


def tar_shell(k, x, y, z0, h, r, a, rng, lite=False):
    """a KOTOR Upper City shell building: pointed petal shells of pale plate with a tan stripe, a second smaller shell
    nested beside the first, on a long low podium with a glowing slit"""
    g = max(z0, 0.0)
    H = h - g
    tbox(k, x, y, z0, g + H * 0.12, r * 1.5, r * 0.9, a, B_PLATE, B_ROOF)
    tbox(k, x, y, g + H * 0.05, g + H * 0.07, r * 1.52, r * 0.92, a, B_GLOW, B_GLOW, base=B_GLOW)
    for f, off in ((1.0, 0.0), (0.72, -0.75)):
        cx, cy = turn(x, y, a, off * r, 0.0)
        hh = H * f
        prof = [(r * f, g), (r * f * 1.08, g + hh * 0.2), (r * f * 1.0, g + hh * 0.45), (r * f * 0.76, g + hh * 0.72),
                (r * f * 0.38, g + hh * 0.92), (0.02, g + hh)]
        k.lathe(prof, [B_PLATE, B_PLATE, B_RUST, B_PLATE, B_ROOF], sides=10 if lite else 16, cx=cx, cy=cy, rot=a, sy=0.5)


def tar_slab(k, x, y, z0, h, w, a, lite=False):
    """a pale Taris skyscraper of the background: a broad block with a window strip, set back twice near the top,
    rooftop masts"""
    g = max(z0, 0.0)
    d = w * 0.62
    for i, (f, z1) in enumerate(((1.0, 0.72), (0.82, 0.88), (0.62, 1.0))):
        za = z0 if i == 0 else g + (h - g) * (0.72 if i == 1 else 0.88)
        zb = g + (h - g) * z1
        tbox(k, x, y, za, zb, w * f, d * f, a, B_PLATE, B_ROOF)
        sx, sy = turn(x, y, a, 0.0, d * f)
        tbox(k, sx, sy, max(za, g) + (zb - max(za, g)) * 0.1, zb - (zb - max(za, g)) * 0.08, w * f * 0.6, d * 0.04, a,
             B_PLATE_WIN, B_PLATE_WIN)
    if not lite:
        for s_ in (-0.4, 0.4):
            fx, fy = turn(x, y, a, s_ * w * 0.62, 0.0)
            k.lathe([(w * 0.03, h), (0.0, h + (h - g) * 0.1)], B_PIPE, sides=4, cx=fx, cy=fy)


def tar_plaza(k, x, y, z, r, sculpture=True):
    """a round raised plaza with a glowing rim, and (the user's still) the sculpture of two great curved blades"""
    k.lathe([(r, z - 0.3), (r, z - 0.04), (r * 0.98, z)], [B_GLOW, B_PLATE], sides=24, cx=x, cy=y, cap=B_CONC)
    if sculpture:
        for s_ in (-1, 1):
            pts = [(x + s_ * r * (0.12 + 0.18 * math.sin(math.pi * t)), y + r * 0.1 * s_, z + r * 1.4 * t) for t in
                   (i / 6 for i in range(7))]
            for p0, p1 in zip(pts, pts[1:]):
                k.tube(p0, p1, r * 0.08, B_BRICK, sides=4)


def tar_speeder(k, x, y, z, a, L):
    """an airspeeder in flight: a short tapered hull, a canopy, a glowing tail"""
    at = lambda u: turn(x, y, a, u, 0.0) + (z,)
    k.tube(at(-L * 0.5), at(L * 0.5), L * 0.16, B_HULL, sides=6, r1=L * 0.05)
    k.tube(at(-L * 0.56), at(-L * 0.5), L * 0.12, B_GLOW, sides=6)


def tar_upper(k, band, rng):
    # Taris' Upper and Middle City cells (KOTOR's Upper City, the user's still): pale avenues; massive capsule towers
    # with dark window slots on glowing podiums, some with platform rings or rooftop pads, twin towers joined by sky
    # lobbies, long low ribbon buildings, pointed shell buildings, pale skyscrapers, round plazas with the blade
    # sculpture, arched bridges, airspeeders in the lanes. band 1 Middle City .. 4 Upper City core
    lots = Lots(rng, 0.98)
    paths, hub = streets(rng, 0.0, wiggle=0.12, curvy=False)
    for p in paths:
        sweep(k, [p[0], p[-1]], rect_section(0.11 + 0.01 * band, 0.315, CELL_Z), [B_CONC, B_CONC, B_CONC], open_sec=True)
        lots.block_path(p, 0.14 + 0.01 * band)
    tops = []
    if band >= 2 and rng.random() < 0.45:                                          # twin towers
        w = rng.uniform(0.12, 0.15)
        p_ = lots.spot(w * 2.4)
        if p_:
            tar_twin(k, p_[0], p_[1], CELL_Z, rng.uniform(0.9, 1.1) + 0.25 * band, w, rng.uniform(0, math.pi), rng, lite=True)
    for _ in range(1 + band // 2):                                                 # capsule towers
        w = rng.uniform(0.15, 0.21)
        p_ = lots.spot(w * 1.45)
        if p_:
            h = rng.uniform(0.7, 0.9) + 0.22 * band
            tar_tower(k, p_[0], p_[1], CELL_Z, h, w, w * 0.75, rng.uniform(0, math.pi), rng, lite=True,
                      ring=rng.random() < 0.3, pad_top=rng.random() < 0.25)
            tops.append((p_[0], p_[1], h))
    for _ in range(1 + band // 3):                                                 # ribbon buildings
        L = rng.uniform(0.28, 0.4)
        p_ = lots.spot(L * 1.05)
        if p_:
            tar_ribbon(k, p_[0], p_[1], CELL_Z, rng.uniform(0.2, 0.3) + 0.04 * band, L, L * 0.32, rng.uniform(0, math.pi))
    if rng.random() < 0.6:                                                         # a shell building
        r = rng.uniform(0.16, 0.22)
        p_ = lots.spot(r * 1.6)
        if p_:
            tar_shell(k, p_[0], p_[1], CELL_Z, rng.uniform(0.4, 0.55) + 0.08 * band, r, rng.uniform(0, math.pi), rng,
                      lite=True)
    for _ in range(band // 2):                                                     # pale skyscrapers
        w = rng.uniform(0.1, 0.14)
        p_ = lots.spot(w * 1.2)
        if p_:
            tar_slab(k, p_[0], p_[1], CELL_Z, rng.uniform(0.6, 0.9) + 0.25 * band, w, rng.uniform(0, math.pi), lite=True)
    if rng.random() < 0.4:                                                         # a round plaza
        p_ = lots.spot(0.16)
        if p_:
            tar_plaza(k, p_[0], p_[1], 0.04, 0.15, sculpture=rng.random() < 0.6)
    for _ in range(5):                                                             # low podium blocks in the gaps
        w = rng.uniform(0.07, 0.11)
        p_ = lots.spot(w * 1.15, tries=12)
        if p_:
            ring_ = rrect(p_[0], p_[1], 0, w, w * 0.7, w * 0.6, 0.0, 2)
            hh = rng.uniform(0.12, 0.25)
            loft(k, [at_z(ring_, CELL_Z), at_z(ring_, hh - 0.04), at_z(ring_, hh)], [B_PLATE, B_GLOW], cap=B_ROOF)
    for (x0, y0, h0), (x1, y1, h1) in zip(tops, tops[1:]):                         # arched bridges
        z = min(h0, h1) * rng.uniform(0.3, 0.45)
        curve_tube(k, (x0, y0, z), (x1, y1, z), 0.12, 0.025, 0.025, B_PLATE, n=6, sides=5)
    for _ in range(rng.randint(0, 2)):                                             # airspeeders in the lanes
        tar_speeder(k, rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), rng.uniform(0.6, 1.2) + 0.1 * band,
                    rng.uniform(0, TAU), 0.12)


def tar_tenement(k, x, y, z0, h, w, d, a, rng, lite=False):
    """a Lower City tenement: floors stacked slightly askew, a walkway ledge on one side, a neon sign, rooftop clutter
    (a fan housing, a water tank, a dish)"""
    g = max(z0, 0.0)
    n = 3 if lite else 5
    z = z0
    for i in range(n):                                                             # the floors, askew
        z1 = g + (h - g) * (i + 1) / n
        ox, oy = turn(0.0, 0.0, a, rng.uniform(-0.08, 0.08) * w, rng.uniform(-0.08, 0.08) * d)
        tbox(k, x + ox, y + oy, z, z1, w * rng.uniform(0.92, 1.05), d * rng.uniform(0.92, 1.05),
             a + rng.uniform(-0.06, 0.06), B_CONC if i % 2 == 0 else B_PLATE_WIN, B_ROOF)
        z = z1
    lx, ly = turn(x, y, a, 0.0, d * 1.1)                                          # the walkway ledge
    tbox(k, lx, ly, g + (h - g) * 0.45, g + (h - g) * 0.47, w * 1.05, d * 0.12, a, B_GIRDER, B_GIRDER, base=B_GIRDER)
    sx, sy = turn(x, y, a, w * 1.02, 0.0)                                         # the neon sign
    tbox(k, sx, sy, g + (h - g) * 0.55, g + (h - g) * 0.8, w * 0.04, d * 0.45, a, B_HAZARD, B_HAZARD)
    k.lathe([(w * 0.25, h), (w * 0.25, h + (h - g) * 0.05)], B_PIPE, sides=8, cx=x - w * 0.3, cy=y, cap=B_DARK)   # fan
    k.lathe([(w * 0.18, h), (w * 0.18, h + (h - g) * 0.1), (0.0, h + (h - g) * 0.12)], [B_RUST, B_RUST], sides=8,
            cx=x + w * 0.4, cy=y + d * 0.2)                                         # water tank


def tar_lower(k, band, rng):
    # the Lower City and the container slums (KOTOR's Lower City; canon's container tenements): narrow lanes under
    # pipe runs, tenements stacked askew with walkway ledges, neon signs and rooftop fans, a cantina dome with neon, dark
    # industrial blocks, container stacks in rust and faded colours, a crashed hull lived in, a speeder or two.
    # band 1 slums .. 4 Lower City core
    lots = Lots(rng, 0.98)
    paths, hub = streets(rng, 0.0, wiggle=0.3)
    for p in paths:
        sweep(k, p, rect_section(0.09 + 0.01 * band, 0.315, CELL_Z), [B_SOOT, B_DUST, B_SOOT], open_sec=True)
        lots.block_path(p, 0.12 + 0.01 * band)
    blocks = []
    for _ in range(2 + band):                                                      # tenements
        w = rng.uniform(0.08, 0.13)
        p_ = lots.along(rng.choice(paths), w * 1.15, 0.07) or lots.spot(w * 1.15)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            h = rng.uniform(0.3, 0.5) + 0.12 * band
            tar_tenement(k, p_[0], p_[1], CELL_Z, h, w, w * 0.75, a, rng, lite=True)
            blocks.append((p_[0], p_[1], h))
    for (x0, y0, h0), (x1, y1, h1) in zip(blocks, blocks[1:]):                     # pipe runs between them
        z = min(h0, h1) * 0.7
        k.tube((x0, y0, z), (x1, y1, z), 0.012, B_PIPE, sides=4)
    if rng.random() < 0.35:                                                        # a cantina
        p_ = lots.spot(0.14)
        if p_:
            k.lathe([(0.13, CELL_Z), (0.13, 0.08)], B_CONC, sides=12, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.08, 0.13, 0.08, [B_ROOF, B_ROOF, B_HAZARD], sides=12, n=3)
            sx, sy = p_[0] + 0.13, p_[1]
            tbox(k, sx, sy, 0.05, 0.14, 0.01, 0.07, 0.0, B_HAZARD, B_HAZARD)
    for _ in range(1 + band // 2):                                                 # industrial blocks
        w = rng.uniform(0.09, 0.14)
        p_ = lots.spot(w * 1.1)
        if p_:
            a = rng.uniform(0, math.pi)
            h = rng.uniform(0.2, 0.35) + 0.06 * band
            tbox(k, p_[0], p_[1], CELL_Z, h, w, w * 0.7, a, B_CONC, B_ROOF)
            k.lathe([(0.03, h), (0.025, h + 0.2)], B_SOOT, sides=6, cx=p_[0], cy=p_[1], cap=B_DARK)
    for _ in range(3 + band):                                                      # container stacks
        p_ = lots.spot(0.1, tries=12)
        if p_:
            a = rng.uniform(0, math.pi)
            z = CELL_Z
            for q in range(rng.randint(1, 2 + band // 2)):
                z1 = max(z, 0.0) + 0.06
                cx_, cy_ = turn(p_[0], p_[1], a + q * 0.4, rng.uniform(-0.02, 0.02), 0.0)
                tbox(k, cx_, cy_, z, z1, 0.09, 0.035, a + q * rng.uniform(-0.4, 0.4), rng.choice((B_RUST, B_BRICK)), B_RUST)
                z = z1
    if rng.random() < 0.3:                                                         # a crashed hull, lived in
        p_ = lots.spot(0.18)
        if p_:
            shuttle(k, p_[0], p_[1], -0.05, rng.uniform(0, TAU), 0.4, B_HULL, B_CONC_WIN)
    if rng.random() < 0.5:
        tar_speeder(k, rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), rng.uniform(0.4, 0.8), rng.uniform(0, TAU), 0.1)


def tar_broken(k, x, y, z0, h, w, a, rng):
    """a broken capsule tower of the bombardment: the pale shaft snapped off, girders standing out of the break, its
    podium cracked"""
    g = max(z0, 0.0)
    H = h - g
    rr = lambda f, z: rrect(x, y, z, w * f, w * 0.75 * f, w * 0.7 * f, a, 2)
    loft(k, [rr(1.3, z0), rr(1.3, g + H * 0.15), rr(1.0, g + H * 0.17)], [B_SOOT, B_ROOF])
    loft(k, [rr(1.0, g + H * 0.15), rr(0.97, h)], [B_PLATE], cap=B_SOOT)
    sx, sy = turn(x, y, a, 0.0, w * 0.73)
    tbox(k, sx, sy, g + H * 0.25, h - H * 0.05, w * 0.2, w * 0.05, a, B_SOOT, B_SOOT)
    for q in range(5):                                                             # girders out of the break
        bx, by = turn(x, y, a, rng.uniform(-0.7, 0.7) * w, rng.uniform(-0.5, 0.5) * w)
        k.tube((bx, by, h - 0.02), (bx + rng.uniform(-0.05, 0.05), by + rng.uniform(-0.05, 0.05), h + rng.uniform(0.1, 0.35)),
               w * 0.06, B_GIRDER, sides=4)


def tar_ruin(k, band, rng):
    # the Ruined Sectors and the Quarantine Zone (the bombardment's ruins, walled off for the rakghoul plague): broken
    # capsule towers with girders standing out of the breaks, a toppled tower section, rubble heaps, quarantine walls
    # with warning beacons. band 1 .. 4: taller wrecks
    lots = Lots(rng, 0.98)
    for _ in range(1 + band // 2):                                                 # broken towers
        w = rng.uniform(0.13, 0.18)
        p_ = lots.spot(w * 1.4)
        if p_:
            tar_broken(k, p_[0], p_[1], CELL_Z, rng.uniform(0.4, 0.7) + 0.2 * band, w, rng.uniform(0, math.pi), rng)
    if rng.random() < 0.6:                                                         # a toppled section
        p_ = lots.spot(0.25)
        if p_:
            a = rng.uniform(0, TAU)
            k.tube(turn(p_[0], p_[1], a, -0.25, 0.0) + (0.05,), turn(p_[0], p_[1], a, 0.25, 0.0) + (0.12,), 0.1, B_PLATE,
                   sides=8)
    for _ in range(6):                                                             # rubble heaps
        r = rng.uniform(0.06, 0.12)
        p_ = lots.spot(r * 1.1, tries=12)
        if p_:
            k.lathe([(r, CELL_Z), (r * 0.6, rng.uniform(0.04, 0.12)), (0.0, rng.uniform(0.12, 0.18))], [B_SOOT, B_DUST],
                    sides=6, cx=p_[0], cy=p_[1])
    if rng.random() < 0.45:                                                        # a quarantine wall, beacons
        a = rng.uniform(0, math.pi)
        p0, p1 = turn(0.0, 0.0, a, -0.9, 0.0), turn(0.0, 0.0, a, 0.9, 0.0)
        sweep(k, [p0 + (0.0,), p1 + (0.0,)], rect_section(0.04, 0.3, CELL_Z), B_RUST, caps=B_RUST)
        for t in (0.2, 0.5, 0.8):
            bx, by = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
            k.lathe([(0.02, 0.0), (0.02, 0.06)], B_GLOW, sides=4, cx=bx, cy=by, cap=B_GLOW)


def tar_spires(k):
    # the Upper City (KOTOR, the user's still 2026-10-19; canon: the wealthy in massive guarded towers): a pale deck
    # cut by a broad avenue; at its head the Upper City Tower, the tallest capsule tower (~26) with two platform rings,
    # massive capsule towers and a pair of twins along the avenue, pointed shell buildings, long ribbon buildings
    # lining it, a round plaza with the two-blade sculpture, arched bridges, banners, airspeeders, shuttles on pads.
    # ~18 across (placed at 1.35)
    import random
    rng = random.Random("tar_spires")
    deck = lobed(0.0, 0.0, 0.0, 8.4, lobes=4, amp=0.08, n=28, phase=0.3, sy=0.85)
    loft(k, [at_z(deck, -SKIRT), at_z(deck, 0.9), scaled(at_z(deck, 1.0), 0.98)], [B_PLATE, B_GLOW], cap=B_CONC)
    tar_tower(k, 0.6, 3.6, 1.0, 26.0, 2.2, 1.6, 0.1, rng, ring=True)            # the Upper City Tower
    loft(k, [rrect(0.6, 3.6, 18.6 + dz, 2.2 * f, 1.6 * f, 1.5 * f, 0.1, 3) for dz, f in ((-0.3, 1.0), (0.0, 1.45),
                                                                                    (0.2, 1.45), (0.4, 1.0))],
         [B_PLATE, B_GLOW, B_ROOF])                                               # its second ring
    caps = [(-4.0, 0.8, 17.0, 1.7, 1.2, 0.2, False), (4.2, -1.6, 16.0, 1.6, 1.1, 0.5, True),
            (-5.6, 4.4, 12.0, 1.3, 0.9, 1.0, False)]
    for x, y, h, w, d, a, pt in caps:
        tar_tower(k, x, y, 1.0, h, w, d, a, rng, pad_top=pt)
    tar_twin(k, -3.4, -4.2, 1.0, 14.0, 1.2, -0.3, rng)
    for x, y, h, r, a in ((4.8, 2.6, 7.5, 1.3, 1.2), (0.8, -5.8, 6.5, 1.1, 0.2)):
        tar_shell(k, x, y, 1.0, h, r, a, rng)
    for x, y, a in ((-1.8, -1.2, 1.6), (2.4, -0.6, 1.6)):                          # ribbons along the avenue
        tar_ribbon(k, x, y, 1.0, 3.6, 2.6, 0.9, a)
    for x, y, h, w, a in ((6.6, 5.4, 13.0, 1.2, 0.2), (-7.2, -1.4, 11.0, 1.0, 0.5)):
        tar_slab(k, x, y, 1.0, h, w, a)
    tar_plaza(k, 0.3, -2.4, 1.15, 1.6)
    for i, j in ((0, 2), (0, 1)):                                                  # arched bridges
        (x0, y0, h0, *_), (x1, y1, h1, *_) = caps[i], caps[j]
        z = min(h0, h1) * 0.45
        curve_tube(k, (x0, y0, z), (x1, y1, z), 0.9, 0.22, 0.22, B_PLATE, n=8, sides=6)
    x, y, h, *_ = caps[1]
    shuttle(k, x, y, h - (h - 1.0) * 0.08 + 0.1, 0.7, 2.0, B_HULL, B_CONC_WIN)
    for q in range(6):                                                             # banners along the avenue
        bx, by = -1.0 + q * 0.5, -4.6
        k.lathe([(0.04, 1.0), (0.03, 2.6)], B_PIPE, sides=4, cx=bx, cy=by)
        tbox(k, bx + 0.12, by, 1.8, 2.5, 0.1, 0.01, 0.0, B_RUST if q % 2 else B_HAZARD, B_RUST)
    for x, y, z, a in ((-1.0, 1.0, 8.0, 0.4), (2.0, 0.0, 10.0, 2.6), (-6.0, -3.0, 9.0, 1.2), (5.6, 4.0, 7.0, -0.8)):
        tar_speeder(k, x, y, z, a, 0.9)


def tar_pit(k):
    # the Undercity and the Promised Land (Legends, KOTOR: the mechanical wilderness on Taris' ground under the city
    # levels, the outcasts' village there, the sewers, and the legendary city beneath): a great shaft sunk through the
    # city levels - its walls ringed with level after level of lit windows and broken balconies, a catwalk bridge
    # across it with work lights, rubble slopes at the bottom with the outcasts' shacks and their fires, an elevator
    # tower down the side, the arched sewer gate to the Promised Land; Lower City tenements crowd the rim. ~14 across
    import random
    rng = random.Random("tar_pit")
    k.lathe([(7.0, -SKIRT), (7.0, 1.2), (5.0, 1.2)], [B_CONC, B_CONC], sides=24)               # the rim deck
    prof = [(5.0, 1.2), (4.9, 0.4), (4.7, 0.3), (4.6, -0.5), (4.4, -0.6), (4.3, -1.4), (4.1, -1.5), (4.0, -2.2),
            (2.0, -2.3), (0.0, -2.35)]
    k.lathe(prof, [B_PLATE_WIN, B_SOOT, B_PLATE_WIN, B_SOOT, B_PLATE_WIN, B_SOOT, B_PLATE_WIN, B_DUST, B_DUST], sides=24)
    for _ in range(8):                                                             # rubble heaps on the floor
        a, d = rng.uniform(0, TAU), rng.uniform(1.0, 3.4)
        rock(k, d * math.cos(a), d * math.sin(a), -2.4, -1.8 + rng.uniform(0.0, 0.5), rng.uniform(0.4, 0.8), rng,
             [B_SOOT] * 3, lobes=2, tiers=2)
    for _ in range(12):                                                            # the outcasts' shacks, fires
        a, d = rng.uniform(0, TAU), rng.uniform(0.6, 3.6)
        x, y = d * math.cos(a), d * math.sin(a)
        tbox(k, x, y, -2.35, -1.9, 0.25, 0.18, a, B_RUST, B_RUST)
        if rng.random() < 0.4:
            k.lathe([(0.08, -2.35), (0.08, -2.25)], B_GLOW, sides=5, cx=x + 0.35, cy=y, cap=B_GLOW)
    sweep(k, [(-5.0, 0.6, 0.4), (5.0, -0.6, 0.4)], rect_section(0.35, 0.18), B_GIRDER, caps=B_GIRDER)   # the catwalk
    for t in (-3.0, 0.0, 3.0):
        k.lathe([(0.06, 0.4), (0.06, 0.9)], B_GLOW, sides=4, cx=t, cy=-t * 0.12, cap=B_GLOW)
    k.lathe([(0.5, -2.3), (0.5, 3.5), (0.7, 3.8), (0.0, 4.2)], [B_PIPE, B_PLATE, B_ROOF], sides=8, cx=3.8, cy=2.2)   # lift
    sweep(k, [(3.3, 1.9, 3.2), (5.6, 3.3, 1.2)], rect_section(0.3, 0.2), B_PLATE, caps=B_PLATE)
    vault(k, -3.6, -1.6, -2.35, 0.4, 1.2, 0.7, 1.0, [B_SOOT] * 6, end=B_DARK)                   # the sewer gate
    k.lathe([(0.25, -2.35), (0.25, -2.0)], B_GLOW, sides=6, cx=-2.6, cy=-1.2, cap=B_GLOW)
    for q in range(10):                                                            # tenements round the rim
        a = TAU * q / 10 + rng.uniform(-0.15, 0.15)
        x, y = 6.1 * math.cos(a), 6.1 * math.sin(a)
        tar_tenement(k, x, y, 1.0, 1.0 + rng.uniform(1.6, 3.4), 0.6, 0.45, a + math.pi / 2, rng)


def tar_swoop(k):
    # the Tarisian swoop track (Legends: swoop racing on Taris, the Season Opener; KOTOR's Lower City track): a long
    # banked oval on a raised deck with glowing edge lines, a pale ribbon grandstand along the straight, the race
    # control tower (a capsule tower) at the line, the start gantry with lights, gang garages with neon signs behind,
    # swoop bikes on the grid and in the far turn. ~15 across
    import random
    rng = random.Random("tar_swoop")
    oval = [(5.8 * math.cos(TAU * i / 32), 3.2 * math.sin(TAU * i / 32), 0.6) for i in range(32)]
    base = rrect(0.0, 0.0, 0, 7.4, 4.6, 3.0, 0.0, 4)
    loft(k, [at_z(base, -SKIRT), at_z(base, 0.3), at_z(base, 0.4)], [B_PLATE, B_GLOW], cap=B_CONC)
    sweep(k, oval, [(0.7, 0.4), (0.7, 0.75), (-0.7, 0.6), (-0.7, 0.4)], [B_GLOW, B_ROOF, B_PLATE, B_PLATE],
          closed_path=True)
    tar_ribbon(k, -0.8, -4.6, 0.4, 2.6, 3.6, 0.7, 0.0)                              # the grandstand
    tar_tower(k, 3.6, -4.2, 0.4, 6.0, 0.6, 0.45, 0.0, rng, ring=True)                # race control
    for s_ in (-1, 1):                                                             # the start gantry
        k.lathe([(0.12, 0.4), (0.12, 2.2)], B_GIRDER, sides=4, cx=1.6, cy=-3.2 + s_ * 1.0)
    tbox(k, 1.6, -3.2, 2.1, 2.4, 0.15, 1.2, 0.0, B_GIRDER, B_GLOW, base=B_GIRDER)
    for i in range(4):                                                             # gang garages
        tar_tenement(k, -3.6 + i * 2.2, 4.4, 0.4, 1.6, 0.85, 0.5, 0.0, rng, lite=True)
    for x, y, a in ((1.2, -3.0, 0.0), (1.2, -3.4, 0.0), (0.6, -2.9, 0.0), (-5.2, 1.6, 1.9), (4.8, 2.0, -1.4)):   # swoops
        k.tube(turn(x, y, a, -0.3, 0.0) + (0.85,), turn(x, y, a, 0.35, 0.0) + (0.85,), 0.09, B_RUST, sides=6, r1=0.04)
        k.tube(turn(x, y, a, -0.36, 0.0) + (0.85,), turn(x, y, a, -0.3, 0.0) + (0.85,), 0.06, B_GLOW, sides=6)


def tar_jedi(k):
    # the Jedi Tower at Highport (Legends: the Taris Academy, a Jedi outpost before and during the Mandalorian Wars,
    # ruined since the bombardment) beside the Tarisian military base (Legends: once the Republic's, where scientists
    # sought a cure for the rakghoul plague): the tower a broken pale capsule shaft with girders out of its break and a
    # fallen section across the court, overgrown stones round it; the base walled beside it - ribbon barracks, a lab
    # block with a glowing band, round bunkers, a pad with a shuttle, a mast. ~15 across
    import random
    rng = random.Random("tar_jedi")
    tbox(k, -2.6, 0.0, -SKIRT, 0.6, 3.6, 3.6, 0.0, B_CONC, B_DUST)
    tar_broken(k, -2.6, 0.4, 0.6, 12.0, 1.5, 0.3, rng)
    k.tube((-3.4, -2.0, 0.9), (0.4, -3.2, 0.5), 0.9, B_PLATE, sides=8)                         # the fallen section
    for _ in range(10):                                                            # overgrown stones
        a, d = rng.uniform(0, TAU), rng.uniform(1.8, 3.2)
        rock(k, -2.6 + d * math.cos(a), 0.4 + d * math.sin(a), 0.4, 0.7 + rng.uniform(0, 0.6), 0.35, rng,
             [B_SOOT] * 3, lobes=2, tiers=2)
    wall = [(1.4, -3.6, 0.0), (7.0, -3.6, 0.0), (7.0, 3.6, 0.0), (1.4, 3.6, 0.0)]
    sweep(k, wall, trap_section(0.35, 0.25, 1.4, -0.5), B_PLATE, closed_path=True)             # the base
    tar_ribbon(k, 4.2, 2.4, -0.5, 1.8, 2.2, 0.6, 0.0)                               # barracks
    tbox(k, 4.4, 0.2, -SKIRT, 2.4, 1.2, 0.9, 0.0, B_PLATE, B_ROOF)                               # the lab block
    tbox(k, 4.4, 0.2, 1.5, 1.7, 1.22, 0.92, 0.0, B_GLOW, B_GLOW)
    for x, y in ((2.6, -2.2), (5.6, -2.2)):                                        # bunkers
        dome(k, x, y, 0.0, 0.9, 0.7, [B_PLATE] * 4, sides=12)
    pad(k, 2.4, 1.2, 0.4, 0.9, B_GLOW, B_PAD)
    shuttle(k, 2.4, 1.2, 0.4, 0.4, 1.5, B_HULL, B_CONC_WIN)
    k.lathe([(0.06, 2.4), (0.04, 4.6)], B_PIPE, sides=4, cx=5.0, cy=0.6, cap=B_GLOW)


# ==================================================================================================== WAYLAND
# Wayland (canon: forests and mountains, Mount Tantiss and the base inside it; Legends: forests and jungles, the native
# Psadan and Myneyrshi, human colonists, Palpatine's storehouse in the mountain). Colonists' timber and stone, native
# stone domes and thatch longhouses, the grey plate of the hidden facility.
# Atlas hod_wayland (B_ layout): B_PLATE facility grey, B_PLATE_WIN lit window bands, B_CONC dressed stone, B_GIRDER /
# B_PIPE timber, B_BRICK fitted fieldstone, B_ROOF shingles, B_RUST thatch, B_SOOT mountain rock, B_HULL ship hull.
def way_house(k, x, y, z0, w, d, h, a):
    """a colonist house: timber walls on a stone footing under a shingled roof"""
    tbox(k, x, y, z0, h, w, d, a, B_GIRDER, B_ROOF)
    prism_at(k, x, y, h, a, 2 * w * 1.08, [(d * 1.15, 0.0), (0.0, d * 0.9), (-d * 1.15, 0.0)], [B_ROOF] * 3, end=B_GIRDER)


def way_town(k, band, rng):
    # the colonists' towns and farms: lanes, timber houses with shingled roofs, barns, fenced plots, a stone hall in
    # the bigger towns. band 1 farmstead .. 4 town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.35)
    for p in paths:
        sweep(k, p, rect_section(0.08 + 0.015 * band, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.12 + 0.015 * band)
    for _ in range(2 + band * 2):                                                  # houses
        w = rng.uniform(0.07, 0.11)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.08) or lots.spot(w * 1.1)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            way_house(k, p_[0], p_[1], CELL_Z, w, w * 0.6, rng.uniform(0.08, 0.13), a)
    for _ in range(max(0, 3 - band)):                                              # barns, fenced plots
        p_ = lots.spot(0.16)
        if p_:
            a = rng.uniform(0, math.pi)
            way_house(k, p_[0], p_[1], CELL_Z, 0.14, 0.09, 0.14, a)
            for q in range(6):
                x, y = turn(p_[0], p_[1], a, -0.15 + q * 0.06, 0.2)
                k.lathe([(0.008, CELL_Z), (0.008, 0.06)], B_GIRDER, sides=3, cx=x, cy=y)
    if band >= 3:                                                                  # the stone hall
        p_ = lots.spot(0.16)
        if p_:
            tbox(k, p_[0], p_[1], CELL_Z, 0.28, 0.15, 0.1, rng.uniform(0, math.pi), B_CONC, B_ROOF)


def way_village(k, band, rng):
    # the native villages: Psadan houses of fitted fieldstone under low domes, Myneyrshi thatched longhouses on posts,
    # a ring of standing stones. band 1 .. 4 bigger
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.45, n_min=1)
    for p in paths:
        sweep(k, p, rect_section(0.07, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.1)
    for _ in range(2 + band):                                                      # Psadan stone domes
        r = rng.uniform(0.07, 0.1)
        p_ = lots.spot(r * 1.1)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.04)], B_BRICK, sides=10, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.04, r, r * 0.8, B_BRICK, sides=10, n=3)
    for _ in range(1 + band // 2):                                                 # Myneyrshi longhouses
        p_ = lots.spot(0.14)
        if p_:
            a = rng.uniform(0, math.pi)
            tbox(k, p_[0], p_[1], 0.04, 0.1, 0.13, 0.06, a, B_GIRDER, B_RUST)
            prism_at(k, p_[0], p_[1], 0.1, a, 0.3, [(0.08, 0.0), (0.0, 0.12), (-0.08, 0.0)], [B_RUST] * 3, end=B_RUST)
            for q in (-1, 1):
                for s_ in (-1, 1):
                    x, y = turn(p_[0], p_[1], a, q * 0.11, s_ * 0.05)
                    k.lathe([(0.01, CELL_Z), (0.01, 0.05)], B_GIRDER, sides=3, cx=x, cy=y)


def way_tantiss(k):
    # Mount Tantiss (canon and Legends: the mountain that hid the base, and in Legends Palpatine's storehouse with its
    # Spaarti cloning cylinders): a great mountain with ridged flanks rising to ~15, the facility built into its
    # southern face - armoured blast doors at the foot, terraces of lit grey plate stepping up the face, a landing
    # platform cantilevered off it with a shuttle, an observation spire on the shoulder, a perimeter wall and towers
    # on the approach. ~16 across
    import random
    rng = random.Random("way_tantiss")
    rock(k, 0.0, 1.4, -SKIRT, 7.0, 7.0, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4, sy=0.85)
    dat_spire(k, 0.2, 1.8, 6.0, 15.0, 3.0, rng, lean=0.08)                         # the summit
    for i, (y, z0, z1, w) in enumerate(((-3.6, -SKIRT, 2.0, 3.0), (-2.8, 1.6, 3.8, 2.4), (-2.0, 3.4, 5.6, 1.8))):
        tbox(k, 0.0, y, z0, z1, w, 0.8, 0.0, B_PLATE_WIN, B_PLATE)                    # terraces up the face
    vault(k, 0.0, -4.4, -0.4, TAU / 4, 1.0, 1.4, 2.0, [B_PLATE] * 6, end=B_DARK)        # the blast doors
    tbox(k, 0.0, -4.95, -0.4, 1.6, 1.3, 0.06, 0.0, B_HAZARD, B_HAZARD)
    sweep(k, [(2.6, -2.6, 3.6), (5.0, -3.6, 3.6)], rect_section(0.5, 0.25), B_PLATE, caps=B_PLATE)
    pad(k, 5.6, -3.8, 3.7, 1.2, B_HAZARD, B_PAD)                                       # the landing platform
    k.tube((5.6, -3.8, 3.5), (3.6, -2.4, 0.5), 0.2, B_PLATE, sides=6)
    shuttle(k, 5.6, -3.8, 3.7, 2.2, 1.9, B_HULL, B_CONC_WIN)
    k.lathe([(0.5, 5.0), (0.4, 9.0), (0.7, 9.3), (0.7, 9.9), (0.0, 10.6)], [B_PLATE, B_PLATE, B_PLATE_WIN, B_ROOF], sides=8,
            cx=-2.8, cy=-0.6)                                                            # the observation spire
    wall = [(-6.0, -5.6, 0.0), (6.4, -5.6, 0.0)]
    sweep(k, wall, trap_section(0.4, 0.3, 1.2, -0.5), B_PLATE, caps=B_PLATE)
    for x in (-6.0, -2.0, 2.4, 6.4):
        k.lathe([(0.4, -SKIRT), (0.4, 2.0), (0.55, 2.1), (0.0, 2.7)], [B_PLATE, B_PLATE_WIN, B_ROOF], sides=8, cx=x, cy=-5.6)


def way_colony(k):
    # the colonists' city (Legends: human colonists lived on Wayland among the Psadan and Myneyrshi; the city and its
    # name are a design choice): a palisaded town on a rise - a ring of timber stakes with gate towers, a stone keep
    # with a slate roof at the top, timber houses packed round the square, a market with awnings, a landing field
    # outside the wall with a freighter. ~14 across
    import random
    rng = random.Random("way_colony")
    rock(k, 0.0, 0.0, -SKIRT, 1.0, 5.6, rng, [B_DUST, B_DUST, B_DUST], lobes=3, sy=0.85)
    ring_ = [(4.8 * math.cos(TAU * q / 28), 4.1 * math.sin(TAU * q / 28)) for q in range(28)]
    for q, (x, y) in enumerate(ring_):                                             # the palisade
        if q in (6, 7, 20):
            continue
        k.lathe([(0.2, -0.5), (0.18, 2.0), (0.0, 2.4)], [B_GIRDER, B_GIRDER], sides=5, cx=x, cy=y)
    for q in (5, 8, 19, 21):                                                       # gate towers
        x, y = ring_[q]
        tbox(k, x, y, -0.5, 3.0, 0.45, 0.45, TAU * q / 28, B_GIRDER, B_ROOF)
        prism_at(k, x, y, 3.0, TAU * q / 28, 1.0, [(0.5, 0.0), (0.0, 0.6), (-0.5, 0.0)], [B_ROOF] * 3, end=B_GIRDER)
    tbox(k, -0.8, 1.2, 0.8, 4.4, 1.3, 1.0, 0.2, B_CONC, B_ROOF)                               # the keep
    k.lathe([(0.55, 0.8), (0.55, 5.8), (0.7, 5.9), (0.0, 7.0)], [B_CONC, B_CONC, B_ROOF], sides=10, cx=0.4, cy=2.0)
    lots = Lots(rng, 3.8)
    lots.take(-0.8, 1.2, 1.8)
    lots.take(0.6, -1.2, 1.0)
    for _ in range(30):                                                            # houses
        w = rng.uniform(0.35, 0.55)
        p_ = lots.spot(w * 1.1, tries=20)
        if p_ and math.hypot(p_[0] / 4.4, p_[1] / 3.7) < 1:
            way_house(k, p_[0], p_[1], 0.5, w, w * 0.65, 0.9 + rng.uniform(0.6, 1.2), rng.uniform(0, math.pi))
    for x, y in ((0.2, -1.0), (1.2, -1.4), (0.6, -0.6)):                           # market awnings
        tbox(k, x, y, 1.4, 1.5, 0.35, 0.3, 0.3, B_RUST, B_RUST, base=B_RUST)
        k.lathe([(0.03, 0.9), (0.03, 1.4)], B_GIRDER, sides=3, cx=x, cy=y)
    pad(k, 6.6, -2.8, 0.3, 1.4, B_DUST, B_PAD)                                       # the landing field
    k.lathe([(1.2, -SKIRT), (1.2, 0.2)], B_CONC, sides=14, cx=6.6, cy=-2.8)
    shuttle(k, 6.6, -2.8, 0.3, 1.0, 2.4, B_HULL, B_CONC_WIN)


def way_council(k):
    # the Psadan-Myneyrshi council village (Legends: Wayland's two native peoples; the village is a design choice): a
    # clearing with a ring of tall standing stones round a fire pit, the Psadan's fitted-stone dome houses on the
    # hillside, the Myneyrshi's thatched longhouses on posts by the stream, carved totem poles, a lookout on a rock.
    # ~12 across
    import random
    rng = random.Random("way_council")
    tbox(k, 0.0, 0.0, -SKIRT, 0.2, 6.0, 4.6, 0.0, B_DUST, B_DUST)
    for q in range(10):                                                            # the standing stones
        a = TAU * q / 10
        x, y = 2.0 * math.cos(a), 2.0 * math.sin(a)
        tbox(k, x, y, 0.0, rng.uniform(1.4, 2.2), 0.22, 0.16, a, B_SOOT, B_SOOT, wt=0.16, dt=0.12)
    k.lathe([(0.5, 0.2), (0.5, 0.35)], B_BRICK, sides=10, cap=B_GLOW)                         # the fire pit
    for _ in range(9):                                                             # Psadan stone domes
        a, d = rng.uniform(math.pi * 0.9, math.pi * 1.9), rng.uniform(3.2, 5.0)
        x, y = d * math.cos(a), d * math.sin(a) * 0.85
        r = rng.uniform(0.5, 0.75)
        k.lathe([(r, -0.2), (r, 0.3)], B_BRICK, sides=10, cx=x, cy=y)
        dome(k, x, y, 0.3, r, r * 0.8, B_BRICK, sides=10, n=3)
    for i in range(4):                                                             # Myneyrshi longhouses on posts
        x, y, a = 2.6 + (i % 2) * 1.6, -1.6 + i * 1.3, 0.3 + i * 0.2
        tbox(k, x, y, 0.5, 1.1, 0.9, 0.4, a, B_GIRDER, B_RUST)
        prism_at(k, x, y, 1.1, a, 2.0, [(0.55, 0.0), (0.0, 0.8), (-0.55, 0.0)], [B_RUST] * 3, end=B_RUST)
        for q in (-1, 1):
            for s_ in (-1, 1):
                px, py = turn(x, y, a, q * 0.8, s_ * 0.35)
                k.lathe([(0.06, -0.3), (0.06, 0.5)], B_GIRDER, sides=4, cx=px, cy=py)
    for x, y in ((-0.6, 2.8), (0.9, 2.6)):                                         # totem poles
        k.lathe([(0.15, 0.0), (0.18, 1.0), (0.14, 2.0), (0.2, 2.6), (0.0, 3.0)], [B_GIRDER, B_RUST, B_GIRDER, B_RUST],
                sides=6, cx=x, cy=y)
    rock(k, -4.6, 3.0, -SKIRT, 2.4, 1.4, rng, [B_SOOT] * 3, lobes=2)
    tbox(k, -4.6, 3.0, 2.2, 3.2, 0.4, 0.4, 0.3, B_GIRDER, B_RUST)


# ==================================================================================================== CONCORDIA
# Concordia (canon: Mandalore's forested moon; a city where Governor Pre Vizsla ruled; the long-worked Concordian
# mines; the Death Watch hideout in the forest, "The Mandalore Plot"). Mandalorian grey plate with red trim, prefab
# colony domes, the dull rust of the old mines, Death Watch blue.
# Atlas hod_concordia (B_ layout): B_PLATE Mandalorian grey plate, B_PLATE_WIN lit windows, B_CONC prefab white,
# B_CONC_WIN glass, B_RUST mine rust, B_SOOT rock, B_ROOF dark plate, B_HAZARD Death Watch blue, B_GLOW warm,
# B_GIRDER steel lattice, B_BRICK camouflage netting, B_HULL ship hull, B_DUST forest earth.
def con_town(k, band, rng):
    # Concordia's colony towns: prefab domes and boxy habitat blocks in Mandalorian grey with red trim, small pads,
    # comm masts. band 1 outpost .. 4 town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.3)
    for p in paths:
        sweep(k, p, rect_section(0.09 + 0.015 * band, 0.315, CELL_Z), [B_DUST, B_PLATE, B_DUST], open_sec=True)
        lots.block_path(p, 0.13 + 0.015 * band)
    for _ in range(2 + band):                                                      # prefab domes
        r = rng.uniform(0.07, 0.11)
        p_ = lots.spot(r * 1.1)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.05)], B_PLATE_WIN, sides=10, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.05, r, r * 0.7, B_CONC, sides=10, n=3)
    for _ in range(1 + band):                                                      # habitat blocks
        w = rng.uniform(0.08, 0.13)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.08) or lots.spot(w * 1.1)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            h = rng.uniform(0.12, 0.2) + 0.05 * band
            tbox(k, p_[0], p_[1], CELL_Z, h, w, w * 0.6, a, B_PLATE_WIN, B_ROOF)
            tbox(k, p_[0], p_[1], h, h + 0.02, w * 1.02, w * 0.62, a, B_RUST, B_RUST)
    if band >= 2:
        p_ = lots.spot(0.03)
        if p_:
            k.lathe([(0.012, CELL_Z), (0.008, 0.6 + 0.1 * band)], B_PIPE, sides=4, cx=p_[0], cy=p_[1], cap=B_GLOW)


def con_city(k):
    # the Governor's city on Concordia (canon: Pre Vizsla governed Concordia from a city there in the Clone Wars; its
    # name and look are a design choice): a walled colonial city of angular Mandalorian blocks in grey with red trim,
    # the Governor's residence a tall stepped block on the central rise with a pad on its roof, a hangar, the comm
    # mast, prefab domes on the outskirts. ~14 across
    import random
    rng = random.Random("con_city")
    rock(k, 0.0, 0.0, -SKIRT, 0.8, 6.0, rng, [B_DUST, B_DUST, B_DUST], lobes=3, sy=0.85)
    oct_ = [(5.2 * math.cos(TAU * q / 8 + 0.4), 4.4 * math.sin(TAU * q / 8 + 0.4), 0.6) for q in range(8)]
    sweep(k, oct_, trap_section(0.45, 0.3, 1.6, -0.5), B_PLATE, closed_path=True)              # the wall
    for x, y, _z in oct_:
        tbox(k, x, y, -0.5, 2.6, 0.5, 0.5, 0.0, B_PLATE, B_RUST)
    for i, (w, d, z1) in enumerate(((1.8, 1.4, 3.4), (1.3, 1.0, 6.0), (0.9, 0.7, 8.2))):        # the residence
        tbox(k, 0.0, 0.6, 0.6 if i == 0 else z1 - 2.6, z1, w, d, 0.15, B_PLATE_WIN, B_ROOF, wt=w * 0.9, dt=d * 0.9)
        tbox(k, 0.0, 0.6, z1, z1 + 0.15, w * 0.95, d * 0.95, 0.15, B_RUST, B_RUST)
    pad(k, 0.0, 0.6, 8.4, 0.75, B_HAZARD, B_PAD)
    lots = Lots(rng, 4.0)
    lots.take(0.0, 0.6, 2.2)
    for _ in range(26):                                                            # the city blocks
        w = rng.uniform(0.4, 0.7)
        p_ = lots.spot(w * 1.15, tries=20)
        if p_ and math.hypot(p_[0] / 4.6, p_[1] / 3.8) < 1:
            h = 0.6 + rng.uniform(1.0, 2.6)
            tbox(k, p_[0], p_[1], 0.6, h, w, w * 0.65, rng.choice((0.15, 0.15 + math.pi / 2)), B_PLATE_WIN, B_ROOF,
                 wt=w * 0.85, dt=w * 0.55)
            tbox(k, p_[0], p_[1], h, h + 0.1, w * 0.86, w * 0.56, 0.15, B_RUST, B_RUST)
    vault(k, 6.4, 2.2, -0.3, 0.3, 2.6, 1.3, 1.6, [B_PLATE] * 6, end=B_DARK)                     # the hangar
    k.lathe([(0.08, 0.6), (0.05, 6.2)], B_PIPE, sides=4, cx=-3.2, cy=-1.8, cap=B_GLOW)          # comm mast
    for x, y in ((-6.4, -1.0), (-5.8, 1.6), (6.0, -2.4)):                          # prefab domes outside
        k.lathe([(0.8, -SKIRT), (0.8, 0.3)], B_PLATE_WIN, sides=12, cx=x, cy=y)
        dome(k, x, y, 0.3, 0.8, 0.6, B_CONC, sides=12, n=3)


def con_mines(k):
    # the Concordian mines (canon: mines on Concordia, worked out long before the Clone Wars): a derelict processing
    # plant stepped into a hillside - a tall headframe over the main shaft, ore bins and a long conveyor gallery down
    # the slope, the stepped plant with broken windows, rusted tanks, a tunnel adit in the rock, spoil heaps. ~13
    # across
    import random
    rng = random.Random("con_mines")
    rock(k, -2.4, 1.6, -SKIRT, 4.4, 4.6, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.9)
    for i, (x, y, z0, z1) in enumerate(((-1.0, -0.4, 2.2, 4.4), (0.6, -1.2, 1.0, 3.2), (2.2, -2.0, -SKIRT, 2.0))):
        tbox(k, x, y, z0, z1, 1.4, 0.9, 0.4, B_PLATE_WIN, B_ROOF)                              # the stepped plant
    legs(k, -2.6, 1.0, 4.0, 10.0, 1.1, 0.45, 4, 0.12, B_RUST)                          # the headframe
    k.lathe([(0.7, 9.6), (0.7, 10.2)], B_RUST, sides=12, cx=-2.6, cy=1.0, cap=B_RUST)
    k.tube((-2.6, 1.0, 10.0), (-0.4, -0.2, 4.6), 0.06, B_PIPE, sides=4)
    sweep(k, [(-0.6, -0.2, 4.0), (2.4, -2.0, 2.2), (5.6, -3.4, 1.0)], rect_section(0.35, 0.4), B_RUST, caps=B_RUST)   # gallery
    for x, y in ((3.4, -2.8), (5.2, -3.2)):
        k.tube((x, y, -SKIRT), (x, y, 1.8), 0.12, B_RUST, sides=5)
    tbox(k, 6.0, -3.6, -SKIRT, 1.2, 0.8, 0.7, 0.3, B_RUST, B_RUST, wt=0.5, dt=0.4)            # ore bin
    for x, y in ((4.2, 0.6), (5.4, 1.2)):                                          # rusted tanks
        k.lathe([(0.6, -SKIRT), (0.6, 1.6), (0.35, 1.9), (0.0, 1.95)], [B_RUST, B_RUST, B_RUST], sides=12, cx=x, cy=y)
    vault(k, -5.6, -0.6, -0.5, 0.5, 1.2, 0.7, 1.1, [B_SOOT] * 6, end=B_DARK)                    # the adit
    for x, y, r in ((1.8, 3.4, 1.4), (4.0, 3.2, 1.0)):                              # spoil heaps
        rock(k, x, y, -SKIRT, 1.0, r, rng, [B_DUST] * 3, lobes=2, tiers=2)


def con_hideout(k):
    # the Death Watch hideout (canon, "The Mandalore Plot": Death Watch's camp in Concordia's forest): under the trees
    # at the foot of a cliff - a cave mouth in the rock with a blast door, tents and prefab shelters in the clearing,
    # a Kom'rk-style fighter under camouflage netting, speeder bikes, weapon racks, the comm mast, a sentry tower, the
    # Death Watch banner; torrent wisp trees round it. ~13 across
    import random
    rng = random.Random("con_hideout")
    rock(k, -1.0, 3.6, -SKIRT, 5.2, 5.0, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.6)
    vault(k, -1.0, 1.0, -0.4, TAU / 4, 1.0, 1.2, 1.8, [B_SOOT] * 6, end=B_DARK)                  # the cave mouth
    tbox(k, -1.0, 0.5, -0.4, 1.3, 1.1, 0.06, 0.0, B_HAZARD, B_HAZARD)
    for x, y, a in ((-3.6, -0.8, 0.2), (1.8, -0.4, -0.4)):                          # prefab shelters
        vault(k, x, y, 0.0, a, 1.8, 0.6, 0.8, [B_PLATE] * 6, end=B_HAZARD)
    for q in range(4):                                                             # tents
        x, y = -2.4 + q * 1.1, -2.4 - (q % 2) * 0.6
        prism_at(k, x, y, 0.0, 0.3, 1.0, [(0.4, 0.0), (0.0, 0.55), (-0.4, 0.0)], [B_BRICK] * 3, end=B_BRICK)
    shuttle(k, 3.6, -2.8, 0.2, 2.4, 2.4, B_HULL, B_CONC_WIN)                         # the fighter
    for s_ in (-1, 1):
        x0, y0 = turn(3.6, -2.8, 2.4, -0.2, 0.0)
        x1, y1 = turn(3.6, -2.8, 2.4, -0.8, s_ * 1.2)
        k.tube((x0, y0, 0.45), (x1, y1, 0.85), 0.08, B_HULL, sides=4, r1=0.04)
    tbox(k, 3.6, -2.8, 1.5, 1.55, 1.6, 1.6, 0.3, B_BRICK, B_BRICK, base=B_BRICK)            # the netting
    for x, y in ((2.2, -4.2), (5.0, -1.4), (2.0, -1.4), (5.2, -4.2)):
        k.lathe([(0.04, 0.0), (0.04, 1.5)], B_GIRDER, sides=3, cx=x, cy=y)
    for x, y, a in ((0.4, -3.6, 0.3), (0.0, -4.0, 0.5)):                            # speeder bikes
        k.tube(turn(x, y, a, -0.35, 0.0) + (0.4,), turn(x, y, a, 0.4, 0.0) + (0.4,), 0.1, B_PLATE, sides=6, r1=0.05)
    k.lathe([(0.06, 0.0), (0.04, 5.0)], B_PIPE, sides=4, cx=2.8, cy=0.8, cap=B_GLOW)           # comm mast
    legs(k, -4.6, 1.4, -SKIRT, 3.2, 0.7, 0.4, 4, 0.06, B_GIRDER)                       # the sentry tower
    tbox(k, -4.6, 1.4, 3.2, 3.9, 0.55, 0.55, 0.0, B_GIRDER, B_ROOF)
    k.lathe([(0.05, 0.0), (0.04, 3.0)], B_PIPE, sides=4, cx=0.6, cy=0.0)            # the banner
    tbox(k, 1.05, 0.0, 1.8, 2.9, 0.45, 0.02, 0.0, B_HAZARD, B_HAZARD)
    for _ in range(9):                                                             # torrent wisp trees round it
        a, d = rng.uniform(math.pi * 1.1, math.pi * 2.9), rng.uniform(5.2, 6.4)
        x, y = d * math.cos(a), d * math.sin(a) * 0.85
        h = rng.uniform(4.0, 5.5)
        k.lathe([(0.15, -SKIRT), (0.1, h * 0.5)], B_GIRDER, sides=5, cx=x, cy=y)
        k.lathe([(0.1, h * 0.4), (0.7, h * 0.6), (0.6, h * 0.85), (0.0, h)], [B_DUST, B_DUST, B_DUST], sides=7, cx=x, cy=y)


# ==================================================================================================== BRACCA
# Bracca (canon: the Scrapper Guild's shipbreaking world of rocky plains and junkyards; its platforms, Worker Rail
# Route 213, the Retired Control Tower; the user: "kinda like raxus prime"). Rusted steel, Guild yellow, the orange
# glow of cutting torches. The hulls in the yards are Raxus Prime's wreck meshes, placed by bracca_map.wrecks.
# Atlas hod_bracca (B_ layout): B_PLATE worn steel, B_PLATE_WIN lit window rows, B_CONC stained concrete, B_RUST
# rust, B_HAZARD Guild yellow-black, B_GLOW cutting-torch orange, B_GIRDER lattice, B_HULL hull plate, B_SOOT slag.
def bra_gantry(k, x, y, z0, span, h, a, rng):
    """a shipbreaking gantry crane: two lattice legs, a yellow bridge, a trolley with its hook line and magnet"""
    for s_ in (-1, 1):
        lx, ly = turn(x, y, a, 0.0, s_ * span / 2)
        legs(k, lx, ly, z0, h, 0.5, 0.3, 4, 0.06, B_GIRDER)
    tbox(k, x, y, h, h + 0.4, 0.3, span / 2 + 0.3, a, B_HAZARD, B_HAZARD, base=B_HAZARD)
    tx, ty = turn(x, y, a, 0.0, rng.uniform(-0.3, 0.3) * span)
    tbox(k, tx, ty, h - 0.3, h + 0.5, 0.45, 0.4, a, B_RUST, B_ROOF)
    k.tube((tx, ty, h - 0.3), (tx, ty, h * 0.45), 0.03, B_DARK, sides=4)
    k.lathe([(0.4, h * 0.45 - 0.2), (0.4, h * 0.45)], B_RUST, sides=10, cx=tx, cy=ty, cap=B_RUST)


def bra_plate(k, x, y, z0, w, t, h, a, lean, rect):
    """a hull plate stood on edge and leaning: a thin slab whose top is pushed `lean` sideways"""
    lx, ly = turn(0.0, 0.0, a, 0.0, lean)
    lo = [turn(x, y, a, u, v) + (z0,) for u, v in ((-w, -t), (w, -t), (w, t), (-w, t))]
    hi = [(px + lx, py + ly, z0 + h) for px, py, _z in lo]
    loft(k, [lo, hi], rect, cap=rect)


def bra_pile(k, x, y, z0, r, h, rng, plates=3):
    """a scrap pile: a low broad heap of rust and slag, hull plates stuck into it at angles, girders and pipes standing
    out, smaller debris strewn round its foot"""
    g = max(z0, 0.0)
    rock(k, x, y, z0, g + h * 0.55, r * 1.15, rng, [B_SOOT, B_RUST, B_SOOT], lobes=rng.choice((3, 4)), tiers=2, sy=0.8)
    for _ in range(plates * 2):
        a = rng.uniform(0, TAU)
        d = r * rng.uniform(0.1, 0.8)
        bra_plate(k, x + d * math.cos(a), y + d * math.sin(a), g + h * 0.1, r * rng.uniform(0.2, 0.45), r * 0.03,
                  h * rng.uniform(0.4, 1.0), a + rng.uniform(-0.8, 0.8), r * rng.uniform(-0.4, 0.4),
                  rng.choice((B_HULL, B_RUST, B_PLATE, B_RUST)))
    for _ in range(3):
        a = rng.uniform(0, TAU)
        k.tube((x, y, g + h * 0.3), (x + r * 1.3 * math.cos(a), y + r * 1.3 * math.sin(a), g + h * rng.uniform(0.4, 1.3)),
               r * 0.03, rng.choice((B_GIRDER, B_PIPE)), sides=4)
    for _ in range(5):                                                             # debris round its foot
        a, d = rng.uniform(0, TAU), r * rng.uniform(1.0, 1.5)
        w = r * rng.uniform(0.08, 0.18)
        tbox(k, x + d * math.cos(a), y + d * math.sin(a), z0, g + w * 0.8, w, w * 0.6, rng.uniform(0, math.pi),
             rng.choice((B_RUST, B_HULL, B_SOOT)), B_RUST)


def bra_hab(k, x, y, z0, h, w, a, rng):
    """a scrapper's salvage habitat: an old tank or hull drum stood up as a home with a patched roof cap, a hull
    section lying beside it, a leaning plate awning, a stack pipe, a lamp"""
    g = max(z0, 0.0)
    k.lathe([(w * 0.55, z0), (w * 0.55, h * 0.85), (w * 0.4, h), (w * 0.1, h + w * 0.1)],
            [rng.choice((B_PLATE_WIN, B_RUST)), B_ROOF, B_ROOF], sides=8, cx=x, cy=y)
    sx, sy = turn(x, y, a, w * 0.9, 0.0)
    ex, ey = turn(x, y, a, w * 0.9 + w * rng.uniform(0.9, 1.4), 0.0)
    k.tube((sx, sy, g + w * 0.3), (ex, ey, g + w * 0.3), w * 0.35, rng.choice((B_HULL, B_RUST)), sides=8)
    bra_plate(k, *turn(x, y, a, 0.0, -w * 0.75), g, w * 0.5, w * 0.03, h * 0.6, a, -w * 0.25, B_HULL)
    k.lathe([(w * 0.07, g), (w * 0.06, h + w * 0.9)], B_SOOT, sides=5, cx=x - w * 0.3, cy=y + w * 0.3, cap=B_DARK)
    k.lathe([(w * 0.06, h * 0.7), (w * 0.06, h * 0.75)], B_GLOW, sides=4, cx=x + w * 0.5, cy=y - w * 0.3, cap=B_GLOW)


def bra_city(k, band, rng):
    # Bracca's scrapper housing (the cities.txt 52 set; the user, 2026-10-19: "more organic, more trashy, full of
    # scrap metal"): winding dirt lanes, salvage habitats of stood-up tanks and hull drums with lying hull sections
    # and leaning plate awnings, scrap piles bristling with plates and girders, a small wreck, a salvage crane.
    # band 1 camp .. 4 yard town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.45)
    for p in paths:
        sweep(k, p, rect_section(0.08 + 0.01 * band, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.11 + 0.01 * band)
    for _ in range(2 + band):                                                      # salvage habitats
        w = rng.uniform(0.09, 0.13)
        p_ = lots.along(rng.choice(paths), w * 1.4, 0.07) or lots.spot(w * 1.4)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, TAU)
            bra_hab(k, p_[0], p_[1], CELL_Z, rng.uniform(0.12, 0.2) + 0.04 * band, w, a, rng)
    for _ in range(3 + band // 2):                                                 # scrap piles
        r = rng.uniform(0.09, 0.16)
        p_ = lots.spot(r, tries=12)
        if p_:
            bra_pile(k, p_[0], p_[1], CELL_Z, r, rng.uniform(0.06, 0.14), rng, plates=rng.randint(1, 3))
    if rng.random() < 0.35:                                                        # a small wreck
        p_ = lots.spot(0.2)
        if p_:
            shuttle(k, p_[0], p_[1], -0.06, rng.uniform(0, TAU), 0.45, B_RUST, B_DARK)
    if band >= 3:                                                                  # a salvage crane
        p_ = lots.spot(0.12)
        if p_:
            b_ = rng.uniform(0, TAU)
            k.lathe([(0.02, CELL_Z), (0.016, 0.55)], B_HAZARD, sides=4, cx=p_[0], cy=p_[1])
            k.tube((p_[0], p_[1], 0.55), (p_[0] + 0.3 * math.cos(b_), p_[1] + 0.3 * math.sin(b_), 0.6), 0.012, B_HAZARD,
                   sides=4)


def bra_ground(k, r, rng, sy=0.7, h=0.25):
    """a ragged apron of trampled slag, a few rust stains, for a yard or a town"""
    g = lobed(0.0, 0.0, 0.0, r, lobes=5, amp=0.12, n=30, phase=rng.uniform(0, TAU), sy=sy, amp2=0.1)
    loft(k, [at_z(g, -SKIRT), at_z(g, h * 0.6), scaled(at_z(g, h), 0.96)], [B_SOOT, B_SOOT], cap=B_DUST)


def bra_yards(k):
    # the Scrapper Guild Yards (canon: the Guild breaks old starships on Bracca; the hulls here are Raxus Prime's
    # Derriphan wreck meshes, cut in two, placed beside this by bracca_map.wrecks): a ragged apron of slag, two
    # gantry cranes straddling the hulls' berths, cutting rigs with orange torch glows, scrap piles bristling with cut
    # plates all round, leaning stacks of plate, the Guild hall in a salvaged hull section with drums round it, worker
    # habitats, a pad with a hauler. ~18 across
    import random
    rng = random.Random("bra_yards")
    bra_ground(k, 9.0, rng, sy=0.55)
    for x in (-3.6, 3.6):
        bra_gantry(k, x, 0.0, 0.25, 6.8, 6.5, math.pi / 2, rng)
    for x, y in ((-5.6, 2.0), (-1.4, -2.2), (1.8, 2.2), (6.0, -2.0)):              # cutting rigs, torches
        legs(k, x, y, 0.25, 2.4, 0.4, 0.2, 3, 0.05, B_GIRDER)
        k.lathe([(0.25, 2.2), (0.3, 2.5)], B_GLOW, sides=6, cx=x, cy=y, cap=B_GLOW)
    for _ in range(12):                                                            # scrap piles round the edge
        a = rng.uniform(0, TAU)
        x, y = 8.0 * math.cos(a) * rng.uniform(0.8, 1.05), 4.4 * math.sin(a) * rng.uniform(0.8, 1.05)
        bra_pile(k, x, y, -0.5, rng.uniform(0.8, 1.4), rng.uniform(0.8, 1.8), rng)
    for _ in range(10):                                                            # leaning stacks of cut plate
        x, y = rng.uniform(-7.0, 7.0), rng.choice((-3.6, 3.6)) + rng.uniform(-0.5, 0.5)
        bra_plate(k, x, y, 0.2, rng.uniform(0.4, 0.8), 0.06, rng.uniform(0.6, 1.3), rng.uniform(0, math.pi),
                  rng.uniform(-0.3, 0.3), rng.choice((B_HULL, B_RUST)))
    vault(k, 0.0, 5.0, -0.3, 0.1, 4.0, 1.2, 1.7, [B_HULL, B_RUST, B_HULL, B_HULL, B_RUST, B_HULL], end=B_PLATE_WIN)   # hall
    for x in (-2.6, 2.6):
        k.lathe([(0.7, -0.5), (0.7, 1.8), (0.5, 2.2), (0.0, 2.3)], [B_RUST, B_ROOF, B_ROOF], sides=10, cx=x, cy=5.4)
    tbox(k, 0.0, 3.9, 1.1, 1.5, 1.2, 0.05, 0.1, B_HAZARD, B_HAZARD)
    for x, y, a in ((-6.0, 5.0, 0.3), (5.6, 5.4, -0.4)):
        bra_hab(k, x, y, -0.3, 1.6, 0.9, a, rng)
    pad(k, 7.6, -5.2, 0.4, 1.1, B_HAZARD, B_PAD)
    k.lathe([(0.9, -SKIRT), (0.9, 0.3)], B_RUST, sides=12, cx=7.6, cy=-5.2)
    shuttle(k, 7.6, -5.2, 0.4, 2.0, 2.0, B_HULL, B_PLATE_WIN)


def bra_platform(k):
    # Platform Thirty-Two (canon: one of the Scrapper Guild's platforms; a Hammerhead's hull, Raxus Prime's wreck mesh,
    # is placed on it by bracca_map.wrecks): a great ragged deck raised on massive patched pillars over the junk, a
    # gantry at each end, cutting rigs, scrap piles on the deck and under it, the control hut on a mast, a ramp. ~14
    # across
    import random
    rng = random.Random("bra_platform")
    for x in (-5.0, -1.6, 1.6, 5.0):                                               # the pillars
        for y in (-2.4, 2.4):
            k.lathe([(0.6, -SKIRT), (0.45, 1.3), (0.75, 1.5)], [B_RUST, B_RUST], sides=8, cx=x, cy=y)
    deck = lobed(0.0, 0.0, 0.0, 6.8, lobes=4, amp=0.08, n=28, phase=0.4, sy=0.55)
    loft(k, [at_z(deck, 1.5), at_z(deck, 1.9)], [B_GIRDER], cap=B_DUST, base=B_SOOT)
    for x in (-5.4, 5.4):
        bra_gantry(k, x, 0.0, 1.9, 6.0, 6.5, math.pi / 2, rng)
    for x, y in ((-2.4, 2.6), (2.6, -2.6)):
        legs(k, x, y, 1.9, 3.6, 0.3, 0.16, 3, 0.04, B_GIRDER)
        k.lathe([(0.2, 3.4), (0.25, 3.7)], B_GLOW, sides=6, cx=x, cy=y, cap=B_GLOW)
    for x, y in ((-3.6, 2.8), (3.8, 2.6), (0.0, -2.9)):                            # piles on the deck
        bra_pile(k, x, y, 1.6, 0.7, 0.8, rng)
    for _ in range(6):                                                             # and under it
        bra_pile(k, rng.uniform(-6.0, 6.0), rng.choice((-4.4, 4.4)), -0.5, rng.uniform(0.8, 1.2), rng.uniform(0.6, 1.2), rng)
    k.lathe([(0.15, -SKIRT), (0.12, 6.0)], B_GIRDER, sides=4, cx=6.4, cy=3.6)                # the control hut
    k.lathe([(0.6, 6.0), (0.6, 6.7), (0.45, 7.0), (0.0, 7.1)], [B_PLATE_WIN, B_ROOF, B_ROOF], sides=8, cx=6.4, cy=3.6)
    sweep(k, [(-6.6, -2.4, 1.7), (-8.4, -2.8, 0.0)], rect_section(0.5, 0.15), B_RUST, caps=B_RUST)   # ramp


def bra_tower(k):
    # the Retired Control Tower (canon: a facility on Bracca, where Cal Kestis fought the Second Sister): a tall
    # weathered stem patched with hull plate, a lift shaft up its side, a flared control room with a band of windows
    # and a bent antenna, rusted catwalk rings, the junk drifted round its foot. ~10 across, ~14 high
    import random
    rng = random.Random("bra_tower")
    k.lathe([(1.6, -SKIRT), (1.4, 0.6), (0.9, 1.4), (0.8, 10.0)], [B_CONC, B_CONC, B_CONC], sides=10)
    tbox(k, 0.9, 0.0, 0.6, 10.4, 0.3, 0.35, 0.0, B_RUST, B_ROOF)                                # the lift shaft
    for _ in range(7):                                                             # patches of hull plate
        a, z = rng.uniform(0, TAU), rng.uniform(2.0, 9.0)
        bra_plate(k, 0.86 * math.cos(a), 0.86 * math.sin(a), z, 0.35, 0.04, rng.uniform(0.6, 1.2), a + math.pi / 2, 0.0,
                  rng.choice((B_RUST, B_HULL)))
    k.lathe([(0.8, 10.0), (2.4, 11.0), (2.5, 12.2), (2.0, 12.6), (0.6, 12.9)], [B_PLATE, B_PLATE_WIN, B_ROOF, B_ROOF],
            sides=10)
    for z in (4.0, 7.0):
        k.lathe([(1.3, z - 0.05), (1.3, z)], B_RUST, sides=10, cap=B_RUST)
    k.tube((0.4, 0.2, 12.9), (0.9, 0.6, 15.0), 0.06, B_PIPE, sides=4)                         # the bent antenna
    k.tube((0.9, 0.6, 15.0), (1.6, 0.4, 15.4), 0.05, B_PIPE, sides=4)
    for _ in range(9):                                                             # junk drifted round its foot
        a, d = rng.uniform(0, TAU), rng.uniform(2.4, 4.6)
        bra_pile(k, d * math.cos(a), d * math.sin(a), -0.5, rng.uniform(0.6, 1.1), rng.uniform(0.4, 1.1), rng)


def bra_rail(k):
    # Worker Rail Route 213 (canon: the Scrapper Guild's worker train line on Bracca): a long trestle of lattice pylons
    # striding over the junk, the rail beam on top, a worker train of rounded cars, a station built in a salvaged tank
    # with a stair, scrap piled between the pylons, a signal mast. ~16 long
    import random
    rng = random.Random("bra_rail")
    for i in range(9):                                                             # the trestle
        x = -8.0 + i * 2.0
        legs(k, x, 0.0, -SKIRT, 2.8, 0.7, 0.35, 2, 0.08, B_GIRDER, rot=math.pi / 2)
        if i % 2:
            bra_pile(k, x + 1.0, rng.uniform(-1.2, 1.2), -0.5, rng.uniform(0.6, 1.0), rng.uniform(0.4, 0.9), rng)
    tbox(k, 0.0, 0.0, 2.8, 3.1, 8.4, 0.35, 0.0, B_GIRDER, B_PIPE, base=B_GIRDER)
    for i in range(4):                                                             # the train: rounded cars
        x = -4.6 + i * 1.9
        k.tube((x - 0.85, 0.0, 3.55), (x + 0.85, 0.0, 3.55), 0.42, B_HAZARD if i == 0 else B_PLATE_WIN, sides=10)
    k.lathe([(0.3, 3.15), (0.3, 3.5)], B_GLOW, sides=6, cx=-5.6, cy=0.0, cap=B_GLOW)
    k.lathe([(1.2, -SKIRT), (1.2, 2.9), (0.9, 3.4), (0.0, 3.5)], [B_RUST, B_ROOF, B_ROOF], sides=10, cx=7.0, cy=1.4)   # station
    sweep(k, [(5.0, 1.6, 0.0), (6.0, 1.6, 2.9)], rect_section(0.3, 0.1), B_RUST, caps=B_RUST)
    k.lathe([(0.06, -SKIRT), (0.05, 4.4)], B_PIPE, sides=4, cx=8.4, cy=-0.6, cap=B_GLOW)


def bra_town(k):
    # a scrapper town (Bracca's workers' housing; the town is a design choice): salvage habitats of stood-up tanks
    # and hull drums crowded round a yard of slag, walkways strung between them, a mess hall in a salvaged hull
    # section, a water tower, a salvage crane, scrap piled round the edges. ~12 across
    import random
    rng = random.Random("bra_town")
    bra_ground(k, 5.8, rng, sy=0.85)
    habs = []
    for _ in range(14):
        a, d = rng.uniform(0, TAU), rng.uniform(2.0, 4.6)
        x, y = d * math.cos(a), d * math.sin(a) * 0.85
        h = rng.uniform(1.4, 3.2)
        bra_hab(k, x, y, -0.3, h, rng.uniform(0.7, 1.0), a + math.pi / 2, rng)
        habs.append((x, y, h))
    for (x0, y0, h0), (x1, y1, h1) in zip(habs[::2], habs[1::2]):                  # walkways
        z = min(h0, h1) * 0.6
        sweep(k, [(x0, y0, z), (x1, y1, z)], rect_section(0.12, 0.06), B_GIRDER, caps=B_GIRDER)
    vault(k, 0.0, 0.0, 0.2, 0.3, 3.0, 1.0, 1.2, [B_RUST, B_HULL, B_RUST, B_HULL, B_RUST, B_HULL], end=B_PLATE_WIN)
    legs(k, -1.6, -1.8, 0.2, 3.0, 0.5, 0.35, 4, 0.05, B_GIRDER)                       # the water tower
    k.lathe([(0.6, 3.0), (0.6, 3.8), (0.0, 4.1)], [B_RUST, B_ROOF], sides=10, cx=-1.6, cy=-1.8)
    for _ in range(8):
        a = rng.uniform(0, TAU)
        bra_pile(k, 5.4 * math.cos(a), 4.6 * math.sin(a), -0.5, rng.uniform(0.6, 1.0), rng.uniform(0.5, 1.0), rng)
    k.lathe([(0.08, 0.2), (0.07, 4.2)], B_HAZARD, sides=4, cx=2.2, cy=1.4)
    k.tube((2.2, 1.4, 4.2), (4.0, 2.2, 4.4), 0.06, B_HAZARD, sides=4)



# ==================================================================================================== TRANDOSHA
# Trandosha (Legends: the Trandoshans, reptilian hunters and slavers who serve the Scorekeeper and count their
# jagannath points; Forak their capital; jungles, savannahs and deserts). Trandoshan architecture is barely shown: a
# design choice in a Japanese manner (the user, 2026-10-19) - halls on battered stone footings, dark timber walls with
# lit paper screens, upswept hip roofs with horns for ridge ornaments, pagodas, vermilion torii, stone lanterns,
# trophy skulls.
# Atlas hod_trandosha (B_ layout): B_PLATE scale-green plate, B_PLATE_WIN timber with lit paper screens, B_BRICK
# rough stone, B_ROOF dark roof tiles, B_HAZARD vermilion lacquer, B_RUST tanned hide, B_HULL bone, B_GIRDER dark
# timber, B_SOOT rock, B_GLOW fire.
def tra_roof(k, x, y, z, w, d, a, h, horns=True):
    """a hip roof with upswept eaves (the user, 2026-10-19: Trandosha in a Japanese manner): the eave ring lifted at
    the corners, a steep slope to a short ridge, horns at the ridge ends in place of ridge ornaments"""
    def ring(s_w, s_d, zz, lift):
        out = []
        for (cu, cv), corner in (((1, 1), True), ((0, 1), False), ((-1, 1), True), ((-1, 0), False), ((-1, -1), True),
                                 ((0, -1), False), ((1, -1), True), ((1, 0), False)):
            out.append(turn(x, y, a, cu * w * s_w, cv * d * s_d) + (zz + (lift if corner else 0.0),))
        return out
    loft(k, [ring(1.3, 1.38, z, h * 0.32), ring(1.27, 1.34, z + h * 0.08, h * 0.32), ring(0.82, 0.8, z + h * 0.5, h * 0.06),
             ring(0.5, 0.06, z + h, 0.0)], [B_ROOF, B_ROOF, B_ROOF], cap=B_ROOF, base=B_ROOF)
    if horns:
        for s_ in (-1, 1):
            hx, hy = turn(x, y, a, s_ * w * 0.5, 0.0)
            ex, ey = turn(x, y, a, s_ * w * 0.75, 0.0)
            k.tube((hx, hy, z + h), (ex, ey, z + h * 1.55), h * 0.07, B_HULL, sides=4, r1=h * 0.01)


def tra_hall(k, x, y, z0, h, w, d, a, lite=False):
    """a Trandoshan hall: a battered stone footing, dark timber walls with lit paper-screen windows, an upswept hip roof
    with horns at the ridge ends"""
    g = max(z0, 0.0)
    H = h - g
    tbox(k, x, y, z0, g + H * 0.22, w * 1.08, d * 1.1, a, B_BRICK, B_BRICK, wt=w, dt=d)
    tbox(k, x, y, g + H * 0.22, g + H * 0.62, w * 0.94, d * 0.9, a, B_PLATE_WIN, B_GIRDER)
    tra_roof(k, x, y, g + H * 0.62, w * 0.94, d * 0.9, a, H * 0.38, horns=not lite)


def tra_pagoda(k, x, y, z0, tiers, w, th, a, base=True):
    """a pagoda: a stone base, `tiers` storeys of timber each under an upswept roof, shrinking upward, a spire of
    rings on the top"""
    g = max(z0, 0.0)
    z = g
    if base:
        tbox(k, x, y, z0, g + th * 0.5, w * 1.3, w * 1.3, a, B_BRICK, B_BRICK, wt=w * 1.18, dt=w * 1.18)
        z = g + th * 0.5
    for i in range(tiers):
        f = 1.0 - 0.14 * i
        tbox(k, x, y, z, z + th * 0.55, w * f * 0.8, w * f * 0.8, a, B_PLATE_WIN, B_GIRDER)
        tra_roof(k, x, y, z + th * 0.55, w * f * 0.8, w * f * 0.8, a, th * 0.42, horns=(i == tiers - 1))
        z += th * 0.97
    top = z - th * 0.97 + th * 0.55 + th * 0.42
    k.lathe([(w * 0.06, top), (w * 0.05, top + th * 1.4)], B_PIPE, sides=6, cx=x, cy=y)
    for q in range(4):
        zr = top + th * (0.4 + 0.22 * q)
        k.lathe([(w * 0.14, zr), (w * 0.14, zr + th * 0.05)], B_PIPE, sides=8, cx=x, cy=y, cap=B_PIPE)


def tra_torii(k, x, y, z0, h, span, a):
    """a torii gate in vermilion lacquer: two pillars, a tie beam, a dark top beam sweeping up at its ends, a skull on
    the plaque"""
    for s_ in (-1, 1):
        px, py = turn(x, y, a, 0.0, s_ * span / 2)
        k.lathe([(span * 0.07, z0), (span * 0.06, h)], B_HAZARD, sides=8, cx=px, cy=py)
    tbox(k, x, y, h * 0.78, h * 0.84, span * 0.05, span * 0.62, a, B_HAZARD, B_HAZARD, base=B_HAZARD)
    for s_ in (-1, 1):
        p0 = turn(x, y, a, 0.0, 0.0) + (h * 0.98,)
        p1 = turn(x, y, a, 0.0, s_ * span * 0.72) + (h * 1.08,)
        k.tube(p0, p1, span * 0.06, B_ROOF, sides=6)
    dome(k, *turn(x, y, a, span * 0.04, 0.0), h * 0.86, span * 0.08, span * 0.08, B_HULL, sides=6, n=2)


def tra_lantern(k, x, y, z0, h):
    """a stone lantern: a post, a lit firebox, a small upswept cap"""
    k.lathe([(h * 0.12, z0), (h * 0.06, max(z0, 0.0) + h * 0.55), (h * 0.14, max(z0, 0.0) + h * 0.6)],
            [B_BRICK, B_BRICK], sides=6, cx=x, cy=y)
    k.lathe([(h * 0.1, max(z0, 0.0) + h * 0.6), (h * 0.1, max(z0, 0.0) + h * 0.78)], B_GLOW, sides=6, cx=x, cy=y)
    k.lathe([(h * 0.22, max(z0, 0.0) + h * 0.78), (0.0, max(z0, 0.0) + h)], B_BRICK, sides=6, cx=x, cy=y)


def tra_city(k, band, rng):
    # the Trandoshan towns (the cities.txt 53 set; the user: in a Japanese manner): lanes, halls on stone footings
    # under upswept roofs, a small pagoda in the bigger towns, a torii over a lane, stone lanterns, trophy poles.
    # band 1 village .. 4 town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.3)
    for p in paths:
        sweep(k, p, rect_section(0.08 + 0.01 * band, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.11 + 0.01 * band)
    for _ in range(2 + band):                                                      # halls
        w = rng.uniform(0.09, 0.13)
        p_ = lots.along(rng.choice(paths), w * 1.3, 0.08) or lots.spot(w * 1.3)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            tra_hall(k, p_[0], p_[1], CELL_Z, rng.uniform(0.16, 0.24) + 0.03 * band, w, w * 0.6, a, lite=True)
    if band >= 3:                                                                  # a pagoda
        p_ = lots.spot(0.14)
        if p_:
            tra_pagoda(k, p_[0], p_[1], CELL_Z, 2 + band // 2, 0.09, 0.14, rng.uniform(0, math.pi / 2))
    if paths and rng.random() < 0.5:                                               # a torii over a lane
        (px, py, _z), hd = path_at(paths[0], path_len(paths[0]) * 0.5)
        tra_torii(k, px, py, CELL_Z, 0.2, 0.16, hd)
    for _ in range(2):                                                             # lanterns, trophy poles
        p_ = lots.spot(0.03)
        if p_:
            tra_lantern(k, p_[0], p_[1], CELL_Z, 0.12)
    for _ in range(band // 2):
        p_ = lots.spot(0.03)
        if p_:
            k.lathe([(0.01, CELL_Z), (0.008, 0.25)], B_GIRDER, sides=3, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.22, 0.025, 0.03, B_HULL, sides=5, n=2)


def tra_forak(k):
    # Forak, the capital (Legends: the capital of Trandosha; its look is a design choice, a castle town in the
    # Japanese manner the user asked for): a great battered stone platform with the keep on it - five storeys of dark
    # timber under upswept roofs crowned with horns - stone curtain walls round the town with turrets roofed the same
    # way, halls packed inside, a vermilion torii before the gate hung with trophy skulls, stone lanterns along the
    # approach, a landing pad outside the wall with a Trandoshan ship. ~15 across
    import random
    rng = random.Random("tra_forak")
    rock(k, 0.0, 0.0, -SKIRT, 0.7, 6.4, rng, [B_DUST, B_DUST, B_DUST], lobes=3, sy=0.85)
    ring_ = [(5.4 * math.cos(TAU * q / 8 + 0.4), 4.5 * math.sin(TAU * q / 8 + 0.4), 0.6) for q in range(8)]
    sweep(k, ring_, trap_section(0.6, 0.4, 1.6, -0.5), B_BRICK, closed_path=True)              # the walls
    for x, y, _z in ring_:                                                          # turrets
        a = math.atan2(y, x)
        tbox(k, x, y, -0.5, 2.0, 0.75, 0.75, a, B_BRICK, B_BRICK, wt=0.65, dt=0.65)
        tbox(k, x, y, 2.0, 2.7, 0.55, 0.55, a, B_PLATE_WIN, B_GIRDER)
        tra_roof(k, x, y, 2.7, 0.55, 0.55, a, 0.6, horns=False)
    tbox(k, 0.0, 0.6, 0.6, 2.6, 2.6, 2.2, 0.15, B_BRICK, B_BRICK, wt=2.2, dt=1.85)             # the keep's platform
    tra_pagoda(k, 0.0, 0.6, 2.6, 5, 2.0, 1.55, 0.15, base=False)                     # the keep
    lots = Lots(rng, 4.2)
    lots.take(0.0, 0.6, 3.0)
    lots.take(0.4, -3.6, 1.0)
    for _ in range(18):                                                            # halls inside
        w = rng.uniform(0.5, 0.75)
        p_ = lots.spot(w * 1.3, tries=20)
        if p_ and math.hypot(p_[0] / 4.8, p_[1] / 4.0) < 1:
            tra_hall(k, p_[0], p_[1], 0.4, 0.4 + rng.uniform(1.1, 1.6), w, w * 0.6, rng.choice((0.15, 0.15 + math.pi / 2)),
                     lite=True)
    tra_torii(k, 0.4, -5.6, -0.3, 3.0, 2.2, 0.0)                                   # the torii before the gate
    for x in (-0.6, 1.4):
        for y in (-6.6, -7.4):
            tra_lantern(k, x, y, -0.3, 1.0)
    pad(k, 7.2, -2.6, 0.4, 1.3, B_HAZARD, B_PAD)
    k.lathe([(1.1, -SKIRT), (1.1, 0.3)], B_BRICK, sides=12, cx=7.2, cy=-2.6)
    shuttle(k, 7.2, -2.6, 0.4, 2.6, 2.2, B_PLATE, B_PLATE_WIN)


def tra_market(k):
    # the slaver market and arena (Legends: Trandoshan slavers; the site is a design choice): market halls under
    # upswept roofs round a yard of girder cages and an auction stage with its own roof on posts, the arena beside it
    # - an oval pit with spiked walls and stepped stands, a roofed pavilion for the judges at each end - a torii at the
    # yard's entrance, a slave ship on its pad. ~16 across
    import random
    rng = random.Random("tra_market")
    tbox(k, -2.0, 0.0, -SKIRT, 0.25, 4.6, 4.2, 0.0, B_DUST, B_DUST)
    for i in range(3):                                                             # cage rows
        for j in range(4):
            x, y = -5.0 + j * 1.2, -2.6 + i * 1.1
            for s_ in ((-0.45, -0.4), (0.45, -0.4), (-0.45, 0.4), (0.45, 0.4)):
                k.lathe([(0.04, 0.25), (0.04, 1.1)], B_GIRDER, sides=4, cx=x + s_[0], cy=y + s_[1])
            tbox(k, x, y, 1.1, 1.18, 0.5, 0.45, 0.0, B_GIRDER, B_ROOF, base=B_GIRDER)
    k.lathe([(1.0, 0.25), (1.0, 0.7)], B_BRICK, sides=10, cx=-1.4, cy=1.8, cap=B_DUST)              # the stage
    for s_ in ((-0.8, -0.7), (0.8, -0.7), (-0.8, 0.7), (0.8, 0.7)):
        k.lathe([(0.06, 0.7), (0.06, 1.9)], B_HAZARD, sides=6, cx=-1.4 + s_[0], cy=1.8 + s_[1])
    tra_roof(k, -1.4, 1.8, 1.9, 0.85, 0.75, 0.0, 0.8)
    tra_hall(k, -2.4, -3.8, -0.3, 2.6, 1.8, 0.7, 0.0)                               # the slavers' hall
    tra_hall(k, -5.8, 2.6, -0.3, 2.2, 1.0, 0.6, math.pi / 2, lite=True)
    k.lathe([(4.2, -SKIRT), (4.0, 1.4), (3.4, 1.8), (3.1, 1.2), (2.8, 0.7), (2.5, 0.2), (2.2, -0.3)],
            [B_BRICK, B_BRICK, B_BRICK, B_PLATE, B_BRICK, B_PLATE], sides=20, cx=4.2, cy=0.6, sy=0.75)   # the arena
    k.lathe([(2.2, -0.3), (0.0, -0.32)], B_DUST, sides=20, cx=4.2, cy=0.6, sy=0.75)
    for q in range(14):                                                            # spikes round the pit
        b = TAU * q / 14
        k.lathe([(0.07, -0.3), (0.0, 0.5)], B_HULL, sides=4, cx=4.2 + 2.25 * math.cos(b), cy=0.6 + 1.69 * math.sin(b))
    for x in (0.6, 7.8):                                                           # the judges' pavilions
        tbox(k, x, 0.6, 1.4, 2.4, 0.55, 0.5, math.pi / 2, B_PLATE_WIN, B_GIRDER)
        tra_roof(k, x, 0.6, 2.4, 0.55, 0.5, math.pi / 2, 0.6)
    tra_torii(k, 1.6, -4.2, 0.0, 2.4, 1.6, 0.0)
    pad(k, -4.6, 3.8, 0.4, 1.2, B_HAZARD, B_PAD)
    shuttle(k, -4.6, 3.8, 0.4, 0.6, 2.2, B_PLATE, B_PLATE_WIN)


def tra_lodge(k):
    # the great hunting lodge (Legends: Trandoshan hunters; the lodge is a design choice, in the Japanese manner): on a
    # rocky bluff over the jungle, a long timber hall raised on posts with a veranda, under a great upswept roof
    # crowned with horns, a trophy wall of skulls along its front, two pagoda watchtowers, beast cages, lanterns, a
    # landing pad with the hunters' ship. ~13 across
    import random
    rng = random.Random("tra_lodge")
    rock(k, 0.0, 0.0, -SKIRT, 2.6, 6.0, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.8)
    for x in (-3.0, -1.0, 1.0, 3.0):                                               # the posts
        for y in (-0.6, 1.4):
            k.lathe([(0.12, 2.0), (0.12, 3.0)], B_GIRDER, sides=6, cx=x, cy=y)
    tbox(k, 0.0, 0.4, 3.0, 3.1, 3.6, 1.4, 0.0, B_GIRDER, B_GIRDER, base=B_GIRDER)               # the veranda
    tbox(k, 0.0, 0.5, 3.1, 4.6, 3.2, 1.0, 0.0, B_PLATE_WIN, B_GIRDER)
    tra_roof(k, 0.0, 0.5, 4.6, 3.2, 1.0, 0.0, 1.6)
    for q in range(9):                                                             # the trophy wall
        x = -3.0 + q * 0.75
        k.lathe([(0.05, 3.1), (0.05, 4.2)], B_GIRDER, sides=4, cx=x, cy=-0.95)
        dome(k, x, -1.0, 4.2, 0.18, 0.2, B_HULL, sides=6, n=2)
        k.tube((x - 0.15, -1.0, 4.3), (x - 0.35, -1.05, 4.7), 0.04, B_HULL, sides=3, r1=0.01)
        k.tube((x + 0.15, -1.0, 4.3), (x + 0.35, -1.05, 4.7), 0.04, B_HULL, sides=3, r1=0.01)
    for x in (-4.4, 4.4):                                                          # pagoda watchtowers
        tra_pagoda(k, x, 2.0, 2.2, 3, 0.8, 1.2, 0.0)
    for x in (-2.0, -0.8):                                                         # beast cages
        for s_ in ((-0.4, -0.35), (0.4, -0.35), (-0.4, 0.35), (0.4, 0.35)):
            k.lathe([(0.04, 2.4), (0.04, 3.3)], B_GIRDER, sides=4, cx=x + s_[0], cy=3.0 + s_[1])
        tbox(k, x, 3.0, 3.3, 3.38, 0.45, 0.4, 0.0, B_GIRDER, B_ROOF, base=B_GIRDER)
    for x in (-1.0, 1.0):
        tra_lantern(k, x, -2.2, 2.4, 0.9)
    pad(k, 3.0, -3.4, 2.5, 1.1, B_HAZARD, B_PAD)
    shuttle(k, 3.0, -3.4, 2.5, 0.4, 1.9, B_PLATE, B_PLATE_WIN)


def tra_shrine(k):
    # a shrine of the Scorekeeper (Legends: the Trandoshans' goddess, who weighs each hunter's jagannath points; the
    # temple is a design choice, in the Japanese manner): on a rock plateau, stone terraces climbing to a five-storey
    # pagoda, a path of vermilion torii up the stair, the Scorekeeper's statue before the pagoda - a robed reptilian
    # figure holding up her scales - stone lanterns lining the path, braziers on the terrace. ~12 across
    import random
    rng = random.Random("tra_shrine")
    rock(k, 0.0, 0.0, -SKIRT, 1.4, 5.8, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4, sy=0.9)
    for i, (w, z0, z1) in enumerate(((3.4, 1.2, 1.9), (2.7, 1.9, 2.6))):           # the terraces
        tbox(k, 0.0, 1.0, z0 if i else -SKIRT, z1, w, w * 0.85, 0.0, B_BRICK, B_DUST, wt=w * 0.97, dt=w * 0.83)
    tra_pagoda(k, 0.0, 1.8, 2.6, 5, 1.5, 1.3, 0.0)
    sweep(k, [(0.0, -4.6, 1.2), (0.0, -1.6, 2.6)], rect_section(0.55, 0.12), B_BRICK, caps=B_BRICK)   # the stair
    for i, y in enumerate((-4.6, -3.6, -2.6)):                                     # torii up the path
        tra_torii(k, 0.0, y, 1.2 + 0.45 * i, 1.2 + 0.45 * i + 1.8, 1.4, math.pi / 2)
    for x in (-1.0, 1.0):
        for y in (-4.1, -3.1):
            tra_lantern(k, x, y, 1.2, 0.8)
    zs = 2.6                                                                        # the Scorekeeper's statue
    k.lathe([(0.45, zs), (0.5, zs + 0.8), (0.32, zs + 2.0), (0.24, zs + 2.6)], [B_BRICK, B_BRICK, B_BRICK], sides=8,
            cx=0.0, cy=-0.9)
    k.lathe([(0.24, zs + 2.6), (0.28, zs + 2.9), (0.0, zs + 3.3)], [B_BRICK, B_BRICK], sides=8, cx=0.0, cy=-0.9)
    k.tube((0.0, -0.8, zs + 3.05), (0.0, -1.5, zs + 2.95), 0.11, B_BRICK, sides=6, r1=0.05)
    for s_ in (-1, 1):
        k.tube((s_ * 0.28, -0.9, zs + 2.0), (s_ * 0.85, -0.9, zs + 2.9), 0.08, B_BRICK, sides=5)
    k.tube((-0.95, -0.9, zs + 3.0), (0.95, -0.9, zs + 3.0), 0.04, B_PIPE, sides=4)
    for s_ in (-1, 1):
        k.lathe([(0.0, zs + 2.5), (0.28, zs + 2.58), (0.24, zs + 2.66)], [B_PIPE, B_PIPE], sides=8, cx=s_ * 0.95, cy=-0.9)
        k.tube((s_ * 0.95, -0.9, zs + 3.0), (s_ * 0.95, -0.9, zs + 2.62), 0.012, B_PIPE, sides=3)
    for x, y in ((-2.6, -1.2), (2.6, -1.2)):                                       # braziers
        k.lathe([(0.22, 2.6), (0.35, 3.1), (0.3, 3.2)], [B_BRICK, B_GLOW], sides=6, cx=x, cy=y, cap=B_GLOW)


# ==================================================================================================== NYRIAAN
# Nyriaan (Legends: a tropical mining world of plains, low hills and boggy valleys; Locus the capital with the
# Mining Guild Sector and the Neutral Zone; Prosperity and its mine; Silence, a prospecting town; the plateau Final
# Rest; the CIS took it in 21 BBY. Canon: a gladiatorial arena). The look is a design choice: a tropical mining
# frontier - houses on stilts under curved metal roofs with verandas, prefab domes, rusted plant.
# Atlas hod_nyriaan (B_ layout): B_PLATE ochre plaster, B_PLATE_WIN lit windows, B_ROOF corrugated metal, B_RUST rust,
# B_GIRDER timber, B_CONC concrete, B_HULL CIS hull plate, B_HAZARD Guild orange, B_SOOT rock, B_DUST red earth.
def nyr_house(k, x, y, z0, w, a, rng, lite=False):
    """a frontier house on stilts: a plastered body raised over the wet, a curved corrugated roof, a veranda deck"""
    g = max(z0, 0.0)
    lift = w * 0.4
    for su in (-1, 1):
        for sv in (-1, 1):
            px, py = turn(x, y, a, su * w * 0.85, sv * w * 0.5)
            k.lathe([(w * 0.06, z0), (w * 0.06, g + lift)], B_GIRDER, sides=4, cx=px, cy=py)
    tbox(k, x, y, g + lift, g + lift + w * 0.7, w, w * 0.55, a, B_PLATE_WIN if not lite else B_PLATE, B_ROOF, base=B_GIRDER)
    vault(k, x, y, g + lift + w * 0.7, a, w * 2.2, w * 0.66, w * 0.4, [B_ROOF] * 6, end=B_PLATE)
    vx, vy = turn(x, y, a, 0.0, w * 0.8)
    tbox(k, vx, vy, g + lift - w * 0.04, g + lift, w * 0.9, w * 0.25, a, B_GIRDER, B_GIRDER, base=B_GIRDER)


def nyr_town(k, band, rng):
    # Nyriaan's mining towns (the cities.txt 54 set): muddy lanes, houses on stilts under curved metal roofs, prefab
    # domes, sheds, a water tower, a small drill derrick. band 1 camp .. 4 town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.4)
    for p in paths:
        sweep(k, p, rect_section(0.08 + 0.01 * band, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.11 + 0.01 * band)
    for _ in range(3 + band):                                                      # stilt houses
        w = rng.uniform(0.07, 0.1)
        p_ = lots.along(rng.choice(paths), w * 1.4, 0.08) or lots.spot(w * 1.4)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            nyr_house(k, p_[0], p_[1], CELL_Z, w, a, rng, lite=True)
    for _ in range(1 + band // 2):                                                 # prefab domes
        r = rng.uniform(0.06, 0.09)
        p_ = lots.spot(r * 1.1)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.03)], B_CONC, sides=10, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.03, r, r * 0.7, B_ROOF, sides=10, n=3)
    if rng.random() < 0.5:                                                         # a water tower
        p_ = lots.spot(0.06)
        if p_:
            legs(k, p_[0], p_[1], CELL_Z, 0.35, 0.05, 0.035, 4, 0.006, B_GIRDER, braces=False)
            k.lathe([(0.05, 0.35), (0.05, 0.45), (0.0, 0.48)], [B_RUST, B_ROOF], sides=8, cx=p_[0], cy=p_[1])
    if band <= 2 and rng.random() < 0.5:                                           # a drill derrick
        p_ = lots.spot(0.06)
        if p_:
            legs(k, p_[0], p_[1], CELL_Z, 0.5, 0.06, 0.012, 4, 0.006, B_HAZARD, braces=False)


def nyr_locus(k):
    # Locus, the capital (Legends: the capital of Nyriaan, with the Mining Guild Sector and the Neutral Zone at its
    # centre; the look is a design choice): sectors walled off from one another - in the middle the Neutral Zone's
    # round plaza with a domed market hall and cantinas round it; the Mining Guild Sector to the east with its
    # refinery towers, silos, conveyors and Guild hall; houses on stilts filling the west; landing pads; a wall with
    # gates between the sectors. ~15 across
    import random
    rng = random.Random("nyr_locus")
    g = lobed(0.0, 0.0, 0.0, 7.4, lobes=5, amp=0.1, n=30, phase=0.7, sy=0.72, amp2=0.08)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.15), scaled(at_z(g, 0.25), 0.97)], [B_SOOT, B_SOOT], cap=B_DUST)
    k.lathe([(2.2, 0.25), (2.2, 0.35)], B_CONC, sides=20, cap=B_CONC)                          # the Neutral Zone
    k.lathe([(1.2, 0.35), (1.2, 1.2)], B_PLATE_WIN, sides=14)
    dome(k, 0.0, 0.0, 1.2, 1.3, 1.1, [B_ROOF, B_ROOF, B_RUST, B_ROOF], sides=14)
    for q in range(6):                                                             # cantinas round the plaza
        b = TAU * q / 6 + 0.3
        x, y = 2.8 * math.cos(b), 2.8 * math.sin(b) * 0.85
        tbox(k, x, y, 0.25, 1.1, 0.55, 0.45, b, B_PLATE_WIN, B_ROOF)
        vault(k, x, y, 1.1, b + math.pi / 2, 1.0, 0.5, 0.3, [B_ROOF] * 6, end=B_PLATE)
    for s_ in (-1, 1):                                                             # the sector walls
        sweep(k, [(s_ * 3.6, -5.0, 0.25), (s_ * 3.6, 5.0, 0.25)], trap_section(0.25, 0.18, 1.2, -0.3), B_CONC, caps=B_CONC)
    for i, (x, y, h) in enumerate(((4.8, -2.6, 5.0), (5.8, -1.0, 4.0), (4.8, 1.4, 3.4))):      # Mining Guild refinery
        k.lathe([(0.55, -SKIRT), (0.5, h), (0.3, h + 0.4), (0.12, h + 0.5)], [B_RUST, B_ROOF, B_ROOF], sides=10, cx=x, cy=y)
    for y in (2.8, 3.8):                                                           # silos
        k.lathe([(0.45, -SKIRT), (0.45, 2.4), (0.0, 2.7)], [B_CONC, B_ROOF], sides=10, cx=6.2, cy=y)
    sweep(k, [(4.8, -2.6, 3.0), (6.2, 3.3, 2.0)], rect_section(0.2, 0.2), B_GIRDER, caps=B_RUST)       # conveyor
    tbox(k, 5.4, -4.2, 0.25, 1.6, 1.1, 0.6, 0.0, B_PLATE_WIN, B_ROOF)                              # the Guild hall
    tbox(k, 5.4, -4.82, 1.0, 1.4, 0.8, 0.03, 0.0, B_HAZARD, B_HAZARD)
    for _ in range(14):                                                            # stilt houses in the west
        x, y = rng.uniform(-6.6, -4.2), rng.uniform(-4.4, 4.4)
        nyr_house(k, x, y, 0.25, rng.uniform(0.4, 0.55), rng.choice((0.0, math.pi / 2)), rng)
    for x, y in ((-1.2, 4.2), (1.6, -4.0)):                                        # landing pads
        pad(k, x, y, 0.5, 0.9, B_HAZARD, B_PAD)
        k.lathe([(0.7, 0.25), (0.7, 0.45)], B_CONC, sides=12, cx=x, cy=y)
    shuttle(k, 1.6, -4.0, 0.5, 0.6, 1.6, B_HULL, B_PLATE_WIN)


def nyr_prosperity(k):
    # Prosperity and the Prosperity Mine (Legends: a town on Nyriaan and the mine near it): a stepped open pit with a
    # haul road spiralling down, a headframe over the shaft on its lip, the ore plant and a conveyor to the loading
    # silos, the town's stilt houses and a hall on the other side. ~13 across
    import random
    rng = random.Random("nyr_prosperity")
    steps = [(4.4, 0.4), (4.2, 0.4), (3.4, -0.3), (3.2, -0.3), (2.4, -1.0), (2.2, -1.0), (1.2, -1.6), (0.0, -1.7)]
    k.lathe(steps, [B_SOOT, B_DUST, B_SOOT, B_DUST, B_SOOT, B_DUST, B_DUST], sides=20, cx=-1.6, cy=0.0, sy=0.85)
    k.lathe([(5.2, -SKIRT), (4.8, 0.35), (4.4, 0.4)], [B_SOOT, B_DUST], sides=20, cx=-1.6, cy=0.0, sy=0.85)
    for i in range(10):                                                            # the haul road
        t0, t1 = i / 10, (i + 1) / 10
        r0, r1 = 4.0 - 2.8 * t0, 4.0 - 2.8 * t1
        a0, a1 = 1.3 * TAU * t0, 1.3 * TAU * t1
        sweep(k, [(-1.6 + r0 * math.cos(a0), 0.85 * r0 * math.sin(a0), 0.3 - 1.9 * t0),
                  (-1.6 + r1 * math.cos(a1), 0.85 * r1 * math.sin(a1), 0.3 - 1.9 * t1)], rect_section(0.25, 0.08), B_DUST)
    legs(k, 2.6, -2.6, -SKIRT, 4.2, 0.9, 0.35, 4, 0.08, B_RUST)                     # the headframe
    k.lathe([(0.5, 3.9), (0.5, 4.3)], B_HAZARD, sides=10, cx=2.6, cy=-2.6, cap=B_RUST)
    tbox(k, 3.6, 0.0, -SKIRT, 1.8, 1.0, 0.8, 0.2, B_PLATE_WIN, B_ROOF)                           # the ore plant
    vault(k, 3.6, 0.0, 1.8, 0.2 + math.pi / 2, 2.0, 0.8, 0.5, [B_ROOF] * 6, end=B_PLATE)
    sweep(k, [(3.6, 0.0, 1.4), (5.2, 2.2, 2.2)], rect_section(0.18, 0.18), B_GIRDER, caps=B_RUST)
    for y in (2.0, 2.9):
        k.lathe([(0.4, -SKIRT), (0.4, 2.0), (0.0, 2.3)], [B_RUST, B_ROOF], sides=10, cx=5.4, cy=y)
    for _ in range(8):                                                             # the town's stilt houses
        x, y = rng.uniform(1.6, 5.6), rng.uniform(3.4, 5.2)
        nyr_house(k, x, y, 0.0, rng.uniform(0.4, 0.55), rng.uniform(0, math.pi), rng)


def nyr_arena(k):
    # the Nyriaan gladiator arena (canon: a gladiatorial arena built on Nyriaan, later run by Jenkes; its look is a
    # design choice): a round bowl of rusted plate and girders, stands stepping up round a sandy pit, beast gates with
    # cages behind them, the owner's box under a curved roof, floodlight masts, banners, a pad for the fighters' ship.
    # ~11 across
    import random
    rng = random.Random("nyr_arena")
    k.lathe([(4.6, -SKIRT), (4.6, 1.6), (4.3, 1.8), (3.6, 1.3), (3.3, 0.8), (3.0, 0.4), (2.7, 0.0), (2.5, -0.2)],
            [B_RUST, B_RUST, B_ROOF, B_PLATE, B_ROOF, B_PLATE, B_ROOF], sides=24)       # the stands, stepping down
    k.lathe([(2.5, -0.2), (0.0, -0.22)], B_DUST, sides=24)                              # the pit
    for q in range(12):                                                            # girder ribs outside
        b = TAU * q / 12
        k.tube((4.7 * math.cos(b), 4.7 * math.sin(b), -0.5), (4.5 * math.cos(b), 4.5 * math.sin(b), 2.4), 0.1, B_GIRDER,
               sides=4)
    for b in (0.4, 2.0, 3.6, 5.2):                                                 # beast gates and cages
        gx, gy = 2.6 * math.cos(b), 2.6 * math.sin(b)
        tbox(k, gx, gy, -0.2, 0.6, 0.12, 0.4, b, B_DARK, B_RUST)
    k.lathe([(0.9, 1.8), (0.9, 2.6)], B_PLATE_WIN, sides=10, cx=0.0, cy=4.4)            # the owner's box
    dome(k, 0.0, 4.4, 2.6, 1.0, 0.6, B_ROOF, sides=10, n=3)
    for b in (0.8, 2.4, 3.9, 5.5):                                                 # floodlight masts
        x, y = 4.9 * math.cos(b), 4.9 * math.sin(b)
        k.lathe([(0.08, -0.5), (0.06, 4.0)], B_GIRDER, sides=4, cx=x, cy=y)
        tbox(k, x, y, 4.0, 4.3, 0.35, 0.1, b, B_GLOW, B_GLOW, base=B_GLOW)
    pad(k, 6.2, -2.4, 0.4, 1.0, B_HAZARD, B_PAD)
    shuttle(k, 6.2, -2.4, 0.4, 1.2, 1.7, B_HULL, B_PLATE_WIN)


def nyr_finalrest(k):
    # Final Rest (Legends: a narrow flat plateau about 100 km north of Locus, one of the highest points on Nyriaan;
    # the outpost on it is a design choice - the CIS took the world in 21 BBY): a tall narrow mesa with sheer ribbed
    # flanks, on its flat top a Separatist sensor outpost - a comm tower with dishes, droid bunkers, a landing pad
    # with a transport - and a lift tower clinging to the cliff. ~13 long
    import random
    rng = random.Random("nyr_finalrest")
    top = lobed(0.0, 0.0, 0.0, 5.6, lobes=3, amp=0.1, n=24, phase=0.4, sy=0.38)
    loft(k, [at_z(scaled(top, 1.18), -SKIRT), at_z(scaled(top, 1.08), 2.0), at_z(scaled(top, 1.02), 5.0),
             at_z(top, 6.2)], [B_SOOT, B_SOOT, B_SOOT], cap=B_DUST)
    k.lathe([(0.35, 6.2), (0.2, 10.5)], B_HULL, sides=6, cx=1.2, cy=0.0)                      # the comm tower
    for z, r in ((8.0, 0.9), (9.6, 0.7)):
        k.lathe([(0.1, z), (r, z + 0.3), (r * 1.1, z + 0.55)], [B_HULL, B_HULL], sides=12, cx=1.2, cy=0.0, rot=0.4)
    for x in (-1.6, -0.2):                                                         # droid bunkers
        dome(k, x, 0.6, 6.2, 0.8, 0.6, [B_HULL, B_HULL, B_HAZARD, B_HULL], sides=12)
    pad(k, -3.6, -0.2, 6.35, 1.0, B_HAZARD, B_PAD)
    shuttle(k, -3.6, -0.2, 6.35, 0.2, 1.7, B_HULL, B_PLATE_WIN)
    tbox(k, 4.6, -1.6, -SKIRT, 6.8, 0.35, 0.35, 0.0, B_GIRDER, B_ROOF)                           # the lift tower


# ==================================================================================================== CORSIN
# Corsin (Legends: a beautiful world of landmasses and oceans, warm in its tropics; the Tinn'lyi Islands; the Corsin
# Retreat where Republic commanders met in 738 BBY; the selligore, sea mammals over twenty metres long). The look is
# a design choice: a Republic island resort world - white stucco under terracotta and teal domes, colonnades,
# terraces, timber boardwalks.
# Atlas hod_corsin (B_ layout): B_PLATE white stucco, B_PLATE_WIN stucco with shaded windows, B_ROOF terracotta tile,
# B_CONC_WIN teal dome glaze, B_GIRDER timber decking, B_CONC pale stone, B_HULL Republic white hull, B_BRICK sea-blue
# pool tile, B_DUST sand, B_RUST selligore hide.
def crs_house(k, x, y, z0, w, h, a, rng, lite=False):
    """a white island house: a stucco block, a terracotta hip roof or a flat terrace with a small teal dome"""
    g = max(z0, 0.0)
    tbox(k, x, y, z0, h, w, w * 0.7, a, B_PLATE_WIN, B_PLATE)
    if rng.random() < 0.55:
        prism_at(k, x, y, h, a, 2 * w * 1.05, [(w * 0.78, 0.0), (0.0, w * 0.45), (-w * 0.78, 0.0)], [B_ROOF] * 3,
                 end=B_ROOF)
    else:
        dome(k, *turn(x, y, a, w * 0.3, 0.0), h, w * 0.35, w * 0.3, B_CONC_WIN, sides=8, n=2)


def crs_town(k, band, rng):
    # Corsin's island towns (the cities.txt 55 set): pale stone lanes, white houses under terracotta roofs and small
    # teal domes, a domed hall in the bigger towns, a plaza with a fountain pool. band 1 village .. 4 town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.35)
    for p in paths:
        sweep(k, p, rect_section(0.08 + 0.01 * band, 0.315, CELL_Z), [B_CONC, B_CONC, B_CONC], open_sec=True)
        lots.block_path(p, 0.11 + 0.01 * band)
    for _ in range(3 + band * 2):                                                  # houses
        w = rng.uniform(0.07, 0.11)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.07) or lots.spot(w * 1.1)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            crs_house(k, p_[0], p_[1], CELL_Z, w, rng.uniform(0.08, 0.14) + 0.03 * band, a, rng, lite=True)
    if band >= 3:                                                                  # a domed hall
        p_ = lots.spot(0.14)
        if p_:
            k.lathe([(0.12, CELL_Z), (0.12, 0.2)], B_PLATE_WIN, sides=12, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.2, 0.13, 0.12, B_CONC_WIN, sides=12, n=3)
    if rng.random() < 0.5:                                                         # a plaza with a pool
        p_ = lots.spot(0.1)
        if p_:
            k.lathe([(0.09, -0.05), (0.09, 0.02)], B_CONC, sides=10, cx=p_[0], cy=p_[1], cap=B_BRICK)


def crs_port(k):
    # Corsin Port, the capital (invented: a Republic port city on the inner sea): a city of white terraces climbing a
    # hill to the governor's domed palace, quays round its foot with piers running out and boats moored at them, a
    # lighthouse on the breakwater, a landing field with a Republic cruiser's shuttle. ~15 across
    import random
    rng = random.Random("crs_port")
    hill = lobed(0.0, 0.0, 0.0, 5.0, lobes=3, amp=0.1, n=24, phase=0.2, sy=0.9)
    loft(k, [at_z(hill, -SKIRT), at_z(scaled(hill, 0.9), 0.6), at_z(scaled(hill, 0.62), 1.6),
             at_z(scaled(hill, 0.36), 2.6), at_z(scaled(hill, 0.34), 2.7)], [B_CONC, B_CONC, B_CONC, B_CONC], cap=B_CONC)
    for ring_r, z, n in ((4.2, 0.6, 16), (2.9, 1.6, 11), (1.9, 2.6, 6)):           # houses up the terraces
        for q in range(n):
            b = TAU * q / n + rng.uniform(-0.1, 0.1)
            x, y = ring_r * math.cos(b), ring_r * math.sin(b) * 0.9
            crs_house(k, x, y, z - 0.6, rng.uniform(0.35, 0.5), z + rng.uniform(0.5, 0.9), b + math.pi / 2, rng)
    k.lathe([(1.2, 2.6), (1.2, 3.6)], B_PLATE_WIN, sides=14)                                   # the palace
    for q in range(8):                                                             # its colonnade
        b = TAU * q / 8
        k.lathe([(0.08, 2.6), (0.08, 3.6)], B_PLATE, sides=6, cx=1.45 * math.cos(b), cy=1.45 * math.sin(b))
    k.lathe([(1.55, 3.6), (1.55, 3.7)], B_PLATE, sides=14, cap=B_PLATE)
    dome(k, 0.0, 0.0, 3.7, 1.1, 1.0, B_CONC_WIN, sides=14)
    for b in (0.4, 2.2, 3.8, 5.3):                                                 # piers and boats
        x0, y0 = 5.0 * math.cos(b), 5.0 * math.sin(b) * 0.9
        x1, y1 = 7.0 * math.cos(b), 7.0 * math.sin(b) * 0.9
        sweep(k, [(x0, y0, 0.15), (x1, y1, 0.15)], rect_section(0.35, 0.12, 0.0), B_GIRDER, caps=B_GIRDER)
        for s_ in (-1, 1):
            bx, by = turn((x0 + x1) / 2, (y0 + y1) / 2, b, 0.0, s_ * 0.7)
            k.tube(turn(bx, by, b, -0.5, 0.0) + (0.15,), turn(bx, by, b, 0.5, 0.0) + (0.15,), 0.18, B_HULL, sides=6,
                   r1=0.05)
    k.lathe([(0.3, -0.3), (0.25, 3.0), (0.4, 3.1), (0.4, 3.5), (0.0, 3.8)], [B_PLATE, B_PLATE, B_GLOW, B_ROOF], sides=8,
            cx=6.8, cy=-2.4)                                                       # the lighthouse
    pad(k, -5.6, 3.0, 0.3, 1.1, B_ROOF, B_PAD)
    shuttle(k, -5.6, 3.0, 0.3, 0.6, 1.8, B_HULL, B_CONC_WIN)


def crs_retreat(k):
    # the Corsin Retreat (Legends: where Republic commanders gathered in 738 BBY to discuss the war; its look is a
    # design choice): on a green hill, a domed rotunda in the Republic manner ringed by columns, a long court with a
    # reflecting pool between two colonnaded lodge wings, garden terraces stepping down, a landing pad for the
    # commanders' shuttles. ~12 across
    import random
    rng = random.Random("crs_retreat")
    rock(k, 0.0, 0.0, -SKIRT, 1.4, 5.4, rng, [B_SOOT, B_SOOT, B_DUST], lobes=3, sy=0.85)
    tbox(k, 0.0, 0.0, 1.0, 1.5, 3.4, 2.4, 0.0, B_CONC, B_CONC)                                  # the platform
    k.lathe([(1.3, 1.5), (1.3, 3.0)], B_PLATE_WIN, sides=16, cx=0.0, cy=1.4)                  # the rotunda
    for q in range(12):
        b = TAU * q / 12
        k.lathe([(0.09, 1.5), (0.09, 3.0)], B_PLATE, sides=6, cx=1.6 * math.cos(b), cy=1.4 + 1.6 * math.sin(b))
    k.lathe([(1.75, 3.0), (1.75, 3.15)], B_PLATE, sides=16, cx=0.0, cy=1.4, cap=B_PLATE)
    dome(k, 0.0, 1.4, 3.15, 1.4, 1.2, B_CONC_WIN, sides=16)
    tbox(k, 0.0, -1.0, 1.5, 1.52, 0.5, 1.0, 0.0, B_BRICK, B_BRICK)                              # the reflecting pool
    for s_ in (-1, 1):                                                             # lodge wings with colonnades
        tbox(k, s_ * 2.2, -0.8, 1.5, 2.4, 0.6, 1.3, 0.0, B_PLATE_WIN, B_ROOF)
        prism_at(k, s_ * 2.2, -0.8, 2.4, math.pi / 2, 2.8, [(0.68, 0.0), (0.0, 0.45), (-0.68, 0.0)], [B_ROOF] * 3,
                 end=B_PLATE)
        for q in range(5):
            k.lathe([(0.06, 1.5), (0.06, 2.3)], B_PLATE, sides=6, cx=s_ * 1.4, cy=-2.0 + q * 0.6)
    for i, (w, z) in enumerate(((3.8, 0.4), (4.4, -0.2))):                         # garden terraces
        tbox(k, 0.0, -2.6 - i * 0.8, z, z + 0.6, w, 0.4, 0.0, B_CONC, B_DUST)
    pad(k, 3.8, 2.6, 1.3, 0.9, B_ROOF, B_PAD)
    shuttle(k, 3.8, 2.6, 1.3, 0.8, 1.5, B_HULL, B_CONC_WIN)


def crs_resort(k):
    # the Tinn'lyi resort (Legends: the Tinn'lyi Islands; the resort is a design choice): a curve of bungalows on stilts
    # over the shallows joined by boardwalks, a main lodge under a great sweeping shell roof, beach pavilions, a pool
    # terrace, a landing pad. ~13 across
    import random
    rng = random.Random("crs_resort")
    k.lathe([(5.6, -SKIRT), (5.4, 0.1), (0.0, 0.2)], [B_DUST, B_DUST], sides=20, sy=0.7)             # the beach
    for q in range(9):                                                             # stilt bungalows on a curve
        b = -0.3 + q * 0.42
        x, y = 5.2 * math.cos(b), 3.8 * math.sin(b)
        for su in (-1, 1):
            for sv in (-1, 1):
                k.lathe([(0.06, -0.6), (0.06, 0.5)], B_GIRDER, sides=4, cx=x + su * 0.35, cy=y + sv * 0.3)
        tbox(k, x, y, 0.5, 1.0, 0.45, 0.38, b, B_PLATE_WIN, B_ROOF)
        k.lathe([(0.62, 1.0), (0.0, 1.6)], B_ROOF, sides=8, cx=x, cy=y)
        bx, by = 3.9 * math.cos(b), 2.85 * math.sin(b)
        sweep(k, [(bx, by, 0.5), (x * 0.92, y * 0.92, 0.5)], rect_section(0.15, 0.05), B_GIRDER, caps=B_GIRDER)
    pts = [(3.9 * math.cos(-0.3 + q * 0.42), 2.85 * math.sin(-0.3 + q * 0.42), 0.5) for q in range(9)]
    sweep(k, pts, rect_section(0.2, 0.05), B_GIRDER, caps=B_GIRDER)                             # the boardwalk
    tbox(k, -1.2, -0.4, 0.2, 1.4, 1.6, 1.0, 0.2, B_PLATE_WIN, B_PLATE)                         # the main lodge
    k.lathe([(2.4, 1.4), (2.2, 1.7), (1.2, 2.6), (0.0, 3.0)], [B_ROOF, B_ROOF, B_ROOF], sides=12, cx=-1.2, cy=-0.4,
            sy=0.7, rot=0.2)
    tbox(k, 1.4, -1.4, 0.2, 0.3, 1.0, 0.6, 0.0, B_CONC, B_BRICK)                                 # the pool terrace
    for x, y in ((0.4, 1.8), (-2.6, 1.6)):                                         # beach pavilions
        for su in (-1, 1):
            for sv in (-1, 1):
                k.lathe([(0.05, 0.2), (0.05, 0.9)], B_GIRDER, sides=4, cx=x + su * 0.4, cy=y + sv * 0.4)
        k.lathe([(0.7, 0.9), (0.0, 1.4)], B_ROOF, sides=8, cx=x, cy=y)
    pad(k, -4.2, -2.2, 0.4, 0.9, B_ROOF, B_PAD)
    shuttle(k, -4.2, -2.2, 0.4, 0.4, 1.5, B_HULL, B_CONC_WIN)


def crs_station(k):
    # the selligore watching station (invented: Corsin's waters are home to the selligore, sea mammals over twenty
    # metres long): a platform on piles over the banks, an observation tower with a glazed gallery, research domes, a
    # boat dock with skiffs, and a selligore surfacing beside it - a long smooth back, a blowhole spray, the tail
    # fluke rising. ~14 across
    import random
    rng = random.Random("crs_station")
    for x in (-3.0, -1.0, 1.0, 3.0):                                               # the piles
        for y in (-1.6, 1.6):
            k.lathe([(0.18, -SKIRT), (0.18, 0.8)], B_CONC, sides=6, cx=x, cy=y)
    tbox(k, 0.0, 0.0, 0.8, 1.0, 3.6, 2.0, 0.0, B_GIRDER, B_GIRDER, base=B_GIRDER)               # the platform
    k.lathe([(0.45, 1.0), (0.35, 4.6), (0.9, 4.8), (0.9, 5.6), (0.6, 5.9), (0.0, 6.1)],
            [B_PLATE, B_PLATE, B_CONC_WIN, B_ROOF, B_ROOF], sides=12, cx=2.4, cy=0.6)      # the observation tower
    for x, y, r in ((-2.0, 0.6, 0.9), (-0.2, -0.6, 0.7)):                          # research domes
        k.lathe([(r, 1.0), (r, 1.4)], B_PLATE_WIN, sides=12, cx=x, cy=y)
        dome(k, x, y, 1.4, r, r * 0.8, B_PLATE, sides=12, n=3)
    sweep(k, [(0.0, -2.0, 0.5), (0.0, -3.8, 0.5)], rect_section(0.3, 0.08), B_GIRDER, caps=B_GIRDER)   # the dock
    for s_ in (-1, 1):
        k.tube((s_ * 0.6, -3.4, 0.2), (s_ * 0.6, -2.4, 0.2), 0.2, B_HULL, sides=6, r1=0.06)
    # the selligore surfacing: a long smooth back, the blowhole's spray, the tail fluke
    k.tube((-6.5, 3.6, 0.0), (-3.0, 3.6, 0.55), 0.75, B_RUST, sides=10, r1=0.95)
    k.tube((-3.0, 3.6, 0.55), (0.5, 3.6, 0.3), 0.95, B_RUST, sides=10, r1=0.6)
    k.tube((0.5, 3.6, 0.3), (2.2, 3.6, -0.2), 0.6, B_RUST, sides=10, r1=0.25)
    k.lathe([(0.15, 1.1), (0.4, 2.2), (0.1, 2.6)], [B_CONC, B_CONC], sides=8, cx=-3.4, cy=3.6)        # the spray
    for s_ in (-1, 1):
        k.tube((2.2, 3.6, -0.2), (3.0, 3.6 + s_ * 1.0, 0.7), 0.18, B_RUST, sides=6, r1=0.05)


# ==================================================================================================== KASHYYYK
# Kashyyyk (canon: the Wookiee homeworld of wroshyr-tree forests; Kachirho, the coastal city built round great
# wroshyr trees in Revenge of the Sith, with its oil refinery; Rwookrrorro, a city across the treetops; the cursed
# Black Forest and the Myyydril Caverns; the Wartaki Islands). Wookiee building: rounded huts of timber and woven wood
# under sweeping blade-shaped roofs, set on ring platforms round the trunks, joined by sagging bridges.
# Atlas hod_kashyyyk (B_ layout): B_PLATE wroshyr bark, B_PLATE_WIN woven wood with lit windows, B_ROOF dark timber
# roofing, B_GIRDER timber and rope, B_BRICK canopy leaves, B_RUST worked metal, B_HULL Republic white, B_HAZARD
# Republic red, B_SOOT rock, B_DUST sand.
def kas_trunk(k, x, y, z0, h, r, rng, canopy=True, crown=1.0, leaf=B_BRICK):
    """a wroshyr tree: a tall trunk on buttress roots, tapering up; near the top boughs reaching out, each ending in an
    irregular clump of leaves, the clumps at different heights"""
    g = max(z0, 0.0)
    k.lathe([(r * 1.45, z0), (r * 1.1, g + r * 1.4), (r, g + r * 3.0), (r * 0.8, h * 0.75), (r * 0.55, h)],
            [B_PLATE] * 4, sides=12, cx=x, cy=y)
    for q in range(5):                                                             # buttress roots
        a = TAU * q / 5 + rng.uniform(-0.2, 0.2)
        k.tube((x + r * 0.85 * math.cos(a), y + r * 0.85 * math.sin(a), g + r * 2.2),
               (x + r * 2.2 * math.cos(a), y + r * 2.2 * math.sin(a), z0), r * 0.26, B_PLATE, sides=5, r1=r * 0.1)
    if not canopy:
        return
    n = 6
    for q in range(n):                                                             # boughs and leaf clumps
        a = TAU * q / n + rng.uniform(-0.3, 0.3)
        zb = h * rng.uniform(0.72, 0.92)
        reach = r * rng.uniform(2.2, 3.4) * crown
        ex, ey = x + reach * math.cos(a), y + reach * math.sin(a)
        ez = zb + r * rng.uniform(0.8, 1.6)
        k.tube((x, y, zb), (ex, ey, ez), r * 0.22, B_PLATE, sides=5, r1=r * 0.1)
        cr = r * rng.uniform(1.4, 2.0) * crown
        ring_ = lobed(ex, ey, ez - cr * 0.25, cr, lobes=4, amp=0.25, n=14, phase=rng.uniform(0, TAU))
        loft(k, [ring_, at_z(scaled(ring_, 0.9), ez + cr * 0.25), at_z(scaled(ring_, 0.45), ez + cr * 0.55)],
             [leaf, leaf], cap=leaf, base=leaf)
    ring_ = lobed(x, y, h - r * 0.2, r * 2.0 * crown, lobes=5, amp=0.2, n=16, phase=rng.uniform(0, TAU))
    loft(k, [ring_, at_z(scaled(ring_, 0.85), h + r * 0.6), at_z(scaled(ring_, 0.4), h + r * 1.1)], [leaf, leaf],
         cap=leaf, base=leaf)


def kas_hut(k, x, y, z, r, a):
    """a Wookiee hut: a rounded body of woven wood with lit windows under a sweeping blade-shaped roof"""
    k.lathe([(r * 0.85, z), (r, z + r * 0.5), (r * 0.9, z + r * 0.9)], [B_PLATE_WIN, B_PLATE_WIN], sides=10, cx=x, cy=y)
    tip = turn(x, y, a, r * 1.6, 0.0)
    lo = rrect(x, y, z + r * 0.9, r * 1.15, r * 1.0, r * 0.9, a, 2)
    loft(k, [lo, [(px + (tip[0] - x) * 0.3, py + (tip[1] - y) * 0.3, pz + r * 0.7) for px, py, pz in scaled(lo, 0.55)]],
         [B_ROOF], cap=B_ROOF, base=B_ROOF)


def kas_platform(k, x, y, z, r_in, r_out, rng, huts=5):
    """a ring platform round a trunk at height z: a timber deck on struts, huts on it, a rail"""
    k.lathe([(r_in, z - 0.12), (r_out, z - 0.05), (r_out, z)], [B_GIRDER, B_GIRDER], sides=14, cx=x, cy=y, cap=B_GIRDER)
    for q in range(6):                                                             # struts under it
        a = TAU * q / 6
        k.tube((x + r_in * math.cos(a), y + r_in * math.sin(a), z - r_out * 0.5),
               (x + r_out * 0.9 * math.cos(a), y + r_out * 0.9 * math.sin(a), z - 0.08), 0.05, B_GIRDER, sides=4)
    for q in range(huts):
        a = TAU * q / huts + rng.uniform(-0.2, 0.2)
        d = (r_in + r_out) / 2
        kas_hut(k, x + d * math.cos(a), y + d * math.sin(a), z, (r_out - r_in) * 0.38, a)


def kas_bridge(k, p0, p1, sag=0.6):
    """a sagging timber-and-rope bridge"""
    curve_tube(k, p0, p1, -sag, 0.08, 0.08, B_GIRDER, n=8, sides=4)


def kas_city(k, band, rng):
    # the Wookiee tree towns (the cities.txt 56 set): young wroshyr trees with platforms of huts round them, huts on
    # the ground under blade roofs, bridges between the trees. band 1 village .. 4 town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.45, n_min=1)
    for p in paths:
        sweep(k, p, rect_section(0.07, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.1)
    trees = []
    for _ in range(1 + band // 2):                                                 # trees with platforms
        r = rng.uniform(0.04, 0.06)
        p_ = lots.spot(0.26)
        if p_:
            h = rng.uniform(0.9, 1.3) + 0.15 * band
            kas_trunk(k, p_[0], p_[1], CELL_Z, h, r, rng)
            kas_platform(k, p_[0], p_[1], h * 0.45, r, r + 0.16, rng, huts=3)
            trees.append((p_[0], p_[1], h * 0.45))
    for (x0, y0, z0), (x1, y1, z1) in zip(trees, trees[1:]):
        kas_bridge(k, (x0, y0, z0), (x1, y1, z1), sag=0.05)
    for _ in range(2 + band):                                                      # ground huts
        r = rng.uniform(0.06, 0.09)
        p_ = lots.spot(r * 1.3)
        if p_:
            kas_hut(k, p_[0], p_[1], CELL_Z + 0.3, r, rng.uniform(0, TAU))


def kas_kachirho(k):
    # Kachirho (canon, Revenge of the Sith: the Wookiee city on the Wawaatt coast built round a giant wroshyr tree,
    # where the Republic and the Wookiees held the beach against the droid army): the great tree ~26 high, its trunk
    # ringed by five platforms of huts climbing it, four lesser wroshyrs round it with their own platforms, bridges
    # between them, at its foot the beach front - a curved timber sea wall, Wookiee catamarans drawn up, a pier, the
    # landing deck. ~16 across
    import random
    rng = random.Random("kas_kachirho")
    k.lathe([(7.6, -SKIRT), (7.2, 0.2), (0.0, 0.3)], [B_DUST, B_DUST], sides=24, sy=0.8)               # the shore
    kas_trunk(k, 0.0, 0.6, -SKIRT, 26.0, 2.0, rng)
    for i, z in enumerate((4.5, 8.0, 11.5, 15.0, 18.5)):
        kas_platform(k, 0.0, 0.6, z, 1.9 - 0.12 * i, 3.6 - 0.25 * i, rng, huts=6 - i // 2)
    lesser = [(-4.6, 1.8, 15.0, 0.9), (4.4, 2.2, 14.0, 0.85), (-3.4, -3.2, 12.0, 0.8), (3.8, -2.6, 13.0, 0.8)]
    for x, y, h, r in lesser:
        kas_trunk(k, x, y, -SKIRT, h, r, rng)
        kas_platform(k, x, y, h * 0.4, r, r + 1.2, rng, huts=3)
        kas_platform(k, x, y, h * 0.65, r * 0.9, r + 0.9, rng, huts=2)
        kas_bridge(k, (0.0, 0.6, 8.0), (x, y, h * 0.4), sag=0.8)
    wall = [(-6.4, -4.8, 0.3), (-3.0, -5.8, 0.3), (0.6, -6.0, 0.3), (4.0, -5.6, 0.3), (6.8, -4.2, 0.3)]
    sweep(k, wall, trap_section(0.4, 0.25, 1.4, -0.4), B_GIRDER, caps=B_GIRDER)               # the sea wall
    for x in (-5.0, -1.6, 2.0, 5.2):
        k.lathe([(0.35, -0.2), (0.35, 2.2), (0.5, 2.4), (0.0, 2.9)], [B_GIRDER, B_GIRDER, B_ROOF], sides=8, cx=x,
                cy=-5.6)
    for x, a in ((-2.8, 0.2), (1.0, -0.1), (4.4, 0.3)):                            # catamarans
        for s_ in (-1, 1):
            hx, hy = turn(x, -7.2, a, 0.0, s_ * 0.35)
            k.tube(turn(hx, hy, a, -0.9, 0.0) + (0.2,), turn(hx, hy, a, 0.9, 0.0) + (0.25,), 0.18, B_PLATE, sides=6,
                   r1=0.06)
        tbox(k, x, -7.2, 0.35, 0.45, 0.6, 0.4, a, B_GIRDER, B_GIRDER, base=B_GIRDER)
    sweep(k, [(6.0, -1.0, 0.4), (8.6, -1.6, 0.4)], rect_section(0.4, 0.1), B_GIRDER, caps=B_GIRDER)   # the pier


def kas_refinery(k):
    # the Kashyyyk oil refinery near Kachirho (canon: the Separatists tried to destroy it in the Battle of Kashyyyk):
    # metal storage tanks and a cracking column inside timber scaffolding, pipe runs on wooden trestles, a flare stack,
    # a pumping hall under a blade roof, two wroshyrs left standing over it. ~12 across
    import random
    rng = random.Random("kas_refinery")
    g = lobed(0.0, 0.0, 0.0, 5.8, lobes=4, amp=0.1, n=26, phase=0.5, sy=0.78)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.1), scaled(at_z(g, 0.2), 0.97)], [B_SOOT, B_SOOT], cap=B_DUST)
    for x, y, r in ((-3.4, -1.6, 1.0), (-3.4, 1.0, 1.0), (-1.0, 2.6, 0.9)):        # storage tanks
        k.lathe([(r, 0.2), (r, 2.0), (r * 0.6, 2.4), (0.0, 2.5)], [B_RUST, B_RUST, B_RUST], sides=12, cx=x, cy=y)
    k.lathe([(0.5, 0.2), (0.45, 6.0), (0.3, 6.4)], [B_RUST, B_RUST], sides=10, cx=1.0, cy=-0.6, cap=B_DARK)   # column
    legs(k, 1.0, -0.6, 0.2, 5.4, 1.1, 0.8, 4, 0.06, B_GIRDER)                       # its scaffold
    k.lathe([(0.15, 0.2), (0.1, 7.6)], B_RUST, sides=6, cx=3.4, cy=1.8)              # the flare stack
    k.lathe([(0.2, 7.6), (0.1, 8.4)], B_GLOW, sides=6, cx=3.4, cy=1.8, cap=B_GLOW)
    for (x0, y0), (x1, y1) in (((-3.4, -1.6), (1.0, -0.6)), ((-3.4, 1.0), (1.0, -0.6)), ((-1.0, 2.6), (3.4, 1.8))):
        k.tube((x0, y0, 1.4), (x1, y1, 1.4), 0.1, B_PIPE, sides=5)
        for t in (0.33, 0.66):
            k.lathe([(0.08, 0.2), (0.08, 1.4)], B_GIRDER, sides=4, cx=x0 + (x1 - x0) * t, cy=y0 + (y1 - y0) * t)
    k.lathe([(1.0, 0.2), (1.0, 1.4)], B_PLATE_WIN, sides=10, cx=3.2, cy=-2.6)        # the pumping hall
    kas_hut(k, 3.2, -2.6, 1.4, 1.0, 0.3)
    for x, y in ((-5.0, 3.6), (5.2, 3.4)):
        kas_trunk(k, x, y, -SKIRT, 11.0, 0.7, rng)


def kas_rwookrrorro(k):
    # Rwookrrorro (canon; the capital in Legends: a Wookiee city built across the tops of wroshyr trees): six great
    # wroshyrs carrying between their trunks a broad web of timber platforms at mid-height, huts and halls crowding
    # the web, the chieftain's great hall in its middle under a high blade roof, lift lines down to the forest floor,
    # the canopies closing over it. ~16 across
    import random
    rng = random.Random("kas_rwookrrorro")
    trunks = [(-4.6, -2.4, 20.0, 1.2), (0.4, -4.6, 22.0, 1.3), (5.0, -1.6, 19.0, 1.1), (4.0, 3.6, 21.0, 1.2),
              (-1.0, 4.6, 20.0, 1.2), (-5.2, 2.6, 18.0, 1.0)]
    for x, y, h, r in trunks:
        kas_trunk(k, x, y, -SKIRT, h + 4.0, r, rng, crown=0.6)
    web = lobed(0.0, 0.0, 0.0, 5.4, lobes=6, amp=0.12, n=30, phase=0.3)
    loft(k, [at_z(web, 8.6), at_z(web, 9.0)], [B_GIRDER], cap=B_GIRDER, base=B_GIRDER)            # the platform web
    for x, y, h, r in trunks:
        kas_bridge(k, (x * 0.7, y * 0.7, 9.0), (x, y, 9.0), sag=0.1)
    lots = Lots(rng, 4.6)
    lots.take(0.0, 0.0, 1.6)
    for _ in range(26):
        r = rng.uniform(0.45, 0.7)
        p_ = lots.spot(r * 1.3, tries=20)
        if p_ and math.hypot(*p_) < 4.8:
            kas_hut(k, p_[0], p_[1], 9.0, r, rng.uniform(0, TAU))
    k.lathe([(1.4, 9.0), (1.5, 10.4)], B_PLATE_WIN, sides=12)                                   # the great hall
    kas_hut(k, 0.0, 0.0, 10.4, 1.6, 0.6)
    for x, y in ((2.6, -0.6), (-2.4, 1.0)):                                        # lift lines
        k.tube((x, y, 9.0), (x, y, -0.5), 0.04, B_GIRDER, sides=3)
    for x, y, h, r in trunks:                                                      # upper platforms
        kas_platform(k, x, y, h * 0.7, r * 0.8, r + 1.0, rng, huts=3)


def kas_caverns(k):
    # the Black Forest and the Myyydril Caverns (canon: a forest the Wookiees believed cursed; the caverns): a dark
    # rock mound split by cave mouths with a faint glow inside, twisted black trees round it hung with web, web sheets
    # strung between them, bones at the mouths. ~12 across
    import random
    rng = random.Random("kas_caverns")
    rock(k, 0.0, 0.6, -SKIRT, 4.2, 5.0, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4, sy=0.85)
    for x, y, a in ((-1.6, -3.4, 0.3), (1.8, -3.0, -0.4), (3.6, 0.4, -1.4)):      # cave mouths
        vault(k, x, y, -0.4, a, 1.2, 1.0, 1.6, [B_SOOT] * 6, end=B_DARK)
        k.lathe([(0.3, -0.4), (0.3, -0.2)], B_GLOW, sides=6, cx=x * 1.05, cy=y * 1.05, cap=B_GLOW)
    trees = []
    for q in range(11):                                                            # twisted black trees
        a = TAU * q / 11 + rng.uniform(-0.15, 0.15)
        x, y = 6.0 * math.cos(a), 0.6 + 5.0 * math.sin(a)
        h = rng.uniform(6.0, 9.0)
        p0 = (x, y, -SKIRT)
        for seg in range(4):
            p1 = (p0[0] + rng.uniform(-0.6, 0.6), p0[1] + rng.uniform(-0.6, 0.6), p0[2] + h / 4 + (SKIRT if seg == 0 else 0))
            k.tube(p0, p1, 0.4 * (1 - seg * 0.2), B_DARK, sides=6, r1=0.4 * (1 - (seg + 1) * 0.2))
            p0 = p1
        for _ in range(3):
            b = rng.uniform(0, TAU)
            k.tube(p0, (p0[0] + 1.6 * math.cos(b), p0[1] + 1.6 * math.sin(b), p0[2] - rng.uniform(0.2, 1.4)), 0.1, B_DARK,
                   sides=4, r1=0.03)
        trees.append(p0)
    for p0, p1 in zip(trees, trees[1:] + trees[:1]):                               # web sheets
        if rng.random() < 0.6:
            m = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            loft(k, [[(p0[0], p0[1], p0[2] - 0.6), (p1[0], p1[1], p1[2] - 0.6)],
                     [(m[0], m[1], min(p0[2], p1[2]) - 2.4), (m[0] + 0.01, m[1] + 0.01, min(p0[2], p1[2]) - 2.4)]],
                 [B_CONC], closed=False)
    for _ in range(6):                                                             # bones at the mouths
        x, y = rng.uniform(-2.4, 4.0), rng.uniform(-4.4, -2.6)
        k.tube((x, y, 0.05), (x + rng.uniform(-0.4, 0.4), y + rng.uniform(-0.4, 0.4), 0.1), 0.06, B_HULL, sides=4)


def kas_wartaki(k):
    # the Wartaki Islands outpost (canon: the Wartaki Islands of Kashyyyk; the outpost is a design choice for the
    # Republic's presence there in the Clone Wars): on a rocky island, white clone prefab bunkers and a command
    # centre, two turbolaser towers, a landing pad with a gunship, sensor masts, a Wookiee timber palisade round it
    # with a gate, wroshyrs at the island's edge. ~12 across
    import random
    rng = random.Random("kas_wartaki")
    rock(k, 0.0, 0.0, -SKIRT, 1.2, 5.6, rng, [B_SOOT, B_SOOT, B_DUST], lobes=4, sy=0.85)
    for q in range(26):                                                            # the palisade
        a = TAU * q / 26
        if q in (19, 20):
            continue
        k.lathe([(0.16, 0.6), (0.14, 2.0), (0.0, 2.3)], [B_GIRDER, B_GIRDER], sides=5, cx=4.4 * math.cos(a),
                cy=3.7 * math.sin(a))
    tbox(k, -0.8, 0.8, 1.0, 2.4, 1.4, 1.0, 0.1, B_HULL, B_HULL)                                   # command centre
    tbox(k, -0.8, 0.8, 2.4, 3.0, 0.8, 0.6, 0.1, B_CONC_WIN, B_HULL)
    tbox(k, -0.8, -0.18, 1.8, 2.0, 1.2, 0.03, 0.1, B_HAZARD, B_HAZARD)
    for x, y in ((1.6, 1.8), (-2.8, -1.2)):                                        # prefab bunkers
        vault(k, x, y, 1.0, 0.2, 1.6, 0.6, 0.7, [B_HULL] * 6, end=B_HAZARD)
    for x, y in ((2.6, -1.6), (-3.0, 2.2)):                                        # turbolaser towers
        k.lathe([(0.6, 1.0), (0.45, 3.4), (0.6, 3.6), (0.6, 4.1), (0.0, 4.3)], [B_HULL, B_HULL, B_HULL, B_HULL], sides=10,
                cx=x, cy=y)
        for s_ in (-0.15, 0.15):
            k.tube((x + s_, y, 3.9), (x + s_, y - 1.6, 4.2), 0.08, B_RUST, sides=5)
    pad(k, 1.6, -0.4, 1.2, 1.2, B_HAZARD, B_PAD)
    shuttle(k, 1.6, -0.4, 1.2, 0.6, 2.0, B_HULL, B_CONC_WIN)
    k.lathe([(0.06, 1.0), (0.04, 5.6)], B_PIPE, sides=4, cx=-1.6, cy=1.6, cap=B_GLOW)
    for x, y in ((-4.8, -2.8), (5.0, 2.6), (-4.4, 3.4)):
        kas_trunk(k, x, y, -SKIRT, 10.0, 0.7, rng)


# ==================================================================================================== ONDERON
# Onderon (canon, The Clone Wars: Iziz, an ancient city behind massive walls raised against the jungle's beasts, of
# tan stone under domes and stepped roofs, the Unifar Temple at its heart, Malgan Market; the rebels' nest, a wooden
# fort on a mountain in the highlands; Saw Gerrera's camp in the jungle of Sector S-29. Legends: the Kira Fortress in
# the wilds outside Iziz; the Beast Riders' hunting lodge, the riders of the drexl).
# Atlas hod_onderon (B_ layout): B_PLATE tan stone, B_PLATE_WIN stone with lit windows, B_ROOF slate and teal-patina
# domes, B_BRICK great wall blocks, B_GIRDER logs, B_RUST ochre cloth, B_HAZARD royal blue and gold, B_CONC paving.
def ond_house(k, x, y, z0, w, h, a, rng, lite=False):
    """an Iziz house: a tan stone block, a stepped roof or a small dome"""
    g = max(z0, 0.0)
    tbox(k, x, y, z0, h, w, w * 0.75, a, B_PLATE_WIN, B_PLATE)
    if rng.random() < 0.5:
        tbox(k, x, y, h, h + (h - g) * 0.18, w * 0.7, w * 0.5, a, B_PLATE, B_ROOF)
    else:
        dome(k, x, y, h, w * 0.6, w * 0.55, B_ROOF, sides=8, n=3)


def ond_town(k, band, rng):
    # Onderon's villages and Iziz's districts (the cities.txt 57 set): paved lanes, tan stone houses with domes and
    # stepped roofs, a domed shrine in the bigger towns, a stretch of beast wall. band 1 village .. 4 town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.3)
    for p in paths:
        sweep(k, p, rect_section(0.08 + 0.01 * band, 0.315, CELL_Z), [B_CONC, B_CONC, B_CONC], open_sec=True)
        lots.block_path(p, 0.11 + 0.01 * band)
    for _ in range(3 + band * 2):
        w = rng.uniform(0.07, 0.11)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.07) or lots.spot(w * 1.1)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            ond_house(k, p_[0], p_[1], CELL_Z, w, rng.uniform(0.12, 0.2) + 0.04 * band, a, rng, lite=True)
    if band >= 3:
        p_ = lots.spot(0.12)
        if p_:
            k.lathe([(0.1, CELL_Z), (0.1, 0.3)], B_PLATE_WIN, sides=10, cx=p_[0], cy=p_[1])
            k.lathe([(0.11, 0.3), (0.13, 0.36), (0.08, 0.46), (0.0, 0.5)], [B_ROOF, B_ROOF, B_ROOF], sides=10, cx=p_[0],
                    cy=p_[1])
    if band <= 2 and rng.random() < 0.5:                                           # a stretch of beast wall
        a = rng.uniform(0, math.pi)
        sweep(k, [turn(0.0, 0.0, a, -0.9, 0.85) + (0.0,), turn(0.0, 0.0, a, 0.9, 0.85) + (0.0,)],
              trap_section(0.06, 0.04, 0.4, CELL_Z), B_BRICK, caps=B_BRICK)


def ond_iziz(k):
    # Iziz (canon, The Clone Wars: the capital behind its great walls against the jungle's beasts, the Unifar Temple
    # at its heart, Malgan Market): a ring of massive battered stone walls with square gate towers, the city packed
    # inside - tan stone houses under domes and stepped roofs climbing toward the middle - the Unifar Temple, a tall
    # stepped tower crowned with a bulbous dome on its terraced plaza, the market's awnings below it, the royal banners.
    # ~17 across
    import random
    rng = random.Random("ond_iziz")
    g = lobed(0.0, 0.0, 0.0, 7.6, lobes=5, amp=0.06, n=30, phase=0.2, sy=0.85)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.3), scaled(at_z(g, 0.4), 0.97)], [B_SOOT, B_SOOT], cap=B_CONC)
    ring_ = [(6.8 * math.cos(TAU * q / 14), 5.8 * math.sin(TAU * q / 14), 0.4) for q in range(14)]
    sweep(k, ring_, trap_section(0.9, 0.55, 3.2, -0.5), B_BRICK, closed_path=True)            # the beast wall
    for q, (x, y, _z) in enumerate(ring_):
        if q % 2 == 0:
            a = TAU * q / 14
            tbox(k, x, y, -0.5, 4.2, 0.9, 0.9, a, B_BRICK, B_PLATE, wt=0.8, dt=0.8)
            tbox(k, x, y, 4.2, 4.7, 0.95, 0.95, a, B_PLATE, B_ROOF)
    lots = Lots(rng, 5.6)
    lots.take(0.0, 0.4, 2.4)
    lots.take(0.0, -2.8, 1.0)
    for _ in range(46):                                                            # the houses
        w = rng.uniform(0.45, 0.75)
        p_ = lots.spot(w * 1.05, tries=20)
        if p_ and math.hypot(p_[0] / 6.0, p_[1] / 5.0) < 1:
            d = math.hypot(p_[0] / 6.0, p_[1] / 5.0)
            ond_house(k, p_[0], p_[1], 0.0, w, 0.4 + rng.uniform(1.0, 1.8) + 2.2 * (1 - d), rng.uniform(-0.2, 0.2), rng)
    for i, (w, z0, z1) in enumerate(((2.0, 0.4, 1.4), (1.6, 1.4, 2.4))):         # the temple's terraces
        tbox(k, 0.0, 0.4, z0 if i else -SKIRT, z1, w, w, 0.0, B_BRICK, B_CONC, wt=w * 0.96, dt=w * 0.96)
    for i, (w, z0, z1) in enumerate(((1.1, 2.4, 5.6), (0.85, 5.6, 8.0), (0.65, 8.0, 9.6))):   # the Unifar Temple
        tbox(k, 0.0, 0.4, z0, z1, w, w, 0.0, B_PLATE_WIN, B_PLATE, wt=w * 0.92, dt=w * 0.92)
    k.lathe([(0.66, 9.6), (0.85, 10.4), (0.7, 11.4), (0.25, 12.0), (0.0, 12.4)], [B_ROOF] * 4, sides=12, cx=0.0, cy=0.4)
    for s_ in (-1, 1):                                                             # banners
        tbox(k, s_ * 1.12, 0.4, 3.0, 5.0, 0.02, 0.4, 0.0, B_HAZARD, B_HAZARD)
    for x, y in ((-0.6, -2.6), (0.4, -3.0), (1.0, -2.4), (-0.2, -3.4)):            # Malgan Market
        tbox(k, x, y, 0.9, 1.0, 0.35, 0.3, 0.3, B_RUST, B_RUST, base=B_RUST)
        k.lathe([(0.03, 0.4), (0.03, 0.9)], B_GIRDER, sides=3, cx=x, cy=y)


def ond_nest(k):
    # the nest (canon, The Clone Wars: the Onderon rebels' wooden fort on a mountain in the highlands): a steep
    # rock peak, on its top a palisade of logs round timber platforms on stilts, lookout towers, a long hut, rope
    # bridges to a lesser crag, a ladder of platforms down the face. ~10 across
    import random
    rng = random.Random("ond_nest")
    rock(k, 0.0, 0.0, -SKIRT, 6.0, 4.4, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.85)
    rock(k, 3.6, 2.4, -SKIRT, 4.4, 1.6, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=2)
    k.lathe([(2.4, 5.6), (2.2, 6.0)], B_GIRDER, sides=12, cap=B_GIRDER)                       # the deck
    for q in range(20):                                                            # the palisade
        a = TAU * q / 20
        k.lathe([(0.14, 5.6), (0.12, 7.0), (0.0, 7.3)], [B_GIRDER, B_GIRDER], sides=5, cx=2.3 * math.cos(a),
                cy=2.3 * math.sin(a))
    for x, y in ((1.6, 1.0), (-1.6, -1.2)):                                        # lookout towers
        legs(k, x, y, 6.0, 9.0, 0.5, 0.35, 4, 0.06, B_GIRDER)
        tbox(k, x, y, 9.0, 9.6, 0.5, 0.5, 0.0, B_GIRDER, B_ROOF)
        prism_at(k, x, y, 9.6, 0.0, 1.1, [(0.55, 0.0), (0.0, 0.5), (-0.55, 0.0)], [B_ROOF] * 3, end=B_GIRDER)
    tbox(k, -0.4, 0.6, 6.0, 7.0, 1.0, 0.5, 0.4, B_GIRDER, B_ROOF)                                # the long hut
    prism_at(k, -0.4, 0.6, 7.0, 0.4, 2.1, [(0.6, 0.0), (0.0, 0.55), (-0.6, 0.0)], [B_ROOF] * 3, end=B_GIRDER)
    curve_tube(k, (1.8, 1.2, 6.0), (3.6, 2.4, 4.6), -0.4, 0.06, 0.06, B_GIRDER, n=8, sides=4)   # rope bridge
    for z in (1.0, 2.6, 4.2):                                                      # platforms down the face
        tbox(k, -2.6, -2.0, z, z + 0.12, 0.6, 0.4, 0.6, B_GIRDER, B_GIRDER, base=B_GIRDER)


def ond_camp(k):
    # Saw Gerrera's camp (canon, The Clone Wars: the rebels' secret base in the jungle of Sector S-29): under a rock
    # overhang at the foot of a cliff, tents and crates, a weapons rack, a speeder and a gunship under netting, a
    # fire, the trees close round it. ~9 across
    import random
    rng = random.Random("ond_camp")
    rock(k, -1.0, 2.4, -SKIRT, 4.8, 3.6, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.6)
    tbox(k, -0.6, 0.8, 3.4, 3.9, 2.6, 1.2, 0.0, B_SOOT, B_SOOT, base=B_SOOT)                       # the overhang
    for q in range(4):                                                             # tents
        x = -2.4 + q * 1.3
        prism_at(k, x, -0.2 + (q % 2) * 0.5, 0.0, 0.1, 1.0, [(0.45, 0.0), (0.0, 0.6), (-0.45, 0.0)], [B_RUST] * 3,
                 end=B_RUST)
    for _ in range(6):                                                             # crates
        tbox(k, rng.uniform(-2.6, 2.6), rng.uniform(-2.0, -1.0), 0.0, 0.3, 0.2, 0.2, rng.uniform(0, 1), B_GIRDER, B_GIRDER)
    k.tube((2.4, -1.6, 0.3), (3.4, -1.4, 0.3), 0.18, B_PLATE, sides=6, r1=0.08)                  # a speeder
    shuttle(k, 2.8, 1.4, 0.0, 2.6, 2.0, B_PLATE, B_PLATE_WIN)
    tbox(k, 2.8, 1.4, 1.2, 1.25, 1.3, 1.2, 0.3, B_RUST, B_RUST, base=B_RUST)                      # netting
    k.lathe([(0.2, 0.0), (0.2, 0.1)], B_GLOW, sides=6, cx=0.0, cy=-1.2, cap=B_GLOW)
    for _ in range(6):                                                             # trees close round it
        a = rng.uniform(math.pi, TAU)
        x, y = 4.2 * math.cos(a), 3.4 * math.sin(a)
        kas_trunk(k, x, y, -SKIRT, rng.uniform(5.0, 7.0), 0.3, rng, crown=1.2, leaf=B_HULL)


def ond_kira(k):
    # the Kira Fortress (Legends: the House of Kira's fortress in the wilds outside Iziz): on a rocky rise, a square
    # curtain wall of great stone blocks with domed corner towers, a tall keep with a stepped crown and a teal dome, a
    # gatehouse, the royal banners, the jungle at its foot. ~11 across
    import random
    rng = random.Random("ond_kira")
    rock(k, 0.0, 0.0, -SKIRT, 1.6, 5.4, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4, sy=0.9)
    sq = [(3.4, -3.0, 1.2), (3.4, 3.0, 1.2), (-3.4, 3.0, 1.2), (-3.4, -3.0, 1.2)]
    sweep(k, sq, trap_section(0.6, 0.45, 2.4, -0.4), B_BRICK, closed_path=True)
    for x, y, _z in sq:
        k.lathe([(0.8, 0.8), (0.75, 4.2), (0.85, 4.3)], [B_BRICK, B_PLATE], sides=10, cx=x, cy=y, cap=B_PLATE)
        dome(k, x, y, 4.3, 0.75, 0.7, B_ROOF, sides=10)
    tbox(k, 0.0, 0.4, 1.2, 6.4, 1.4, 1.4, 0.0, B_PLATE_WIN, B_PLATE, wt=1.3, dt=1.3)                # the keep
    tbox(k, 0.0, 0.4, 6.4, 7.4, 1.0, 1.0, 0.0, B_PLATE, B_PLATE)
    k.lathe([(0.9, 7.4), (1.0, 8.0), (0.6, 8.8), (0.0, 9.2)], [B_ROOF] * 3, sides=12, cx=0.0, cy=0.4)
    tbox(k, 0.0, -3.1, 0.8, 3.4, 1.0, 0.6, 0.0, B_BRICK, B_PLATE)                                    # the gatehouse
    for s_ in (-1, 1):
        tbox(k, s_ * 1.42, 0.4, 3.0, 5.2, 0.02, 0.4, 0.0, B_HAZARD, B_HAZARD)


def ond_lodge(k):
    # the Beast Riders' hunting lodge (Legends: the gathering point of the Clazca, a Beast Riders clan, the riders
    # of the flying drexl): a long timber hall under a steep roof, a tall roost tower of logs with perches for the
    # beasts, pens of stakes, trophy poles, a fire ring, the jungle round it. ~10 across
    import random
    rng = random.Random("ond_lodge")
    tbox(k, -0.8, 0.0, -SKIRT, 1.4, 2.4, 0.9, 0.2, B_GIRDER, B_ROOF)                               # the hall
    prism_at(k, -0.8, 0.0, 1.4, 0.2, 5.0, [(1.1, 0.0), (0.0, 1.3), (-1.1, 0.0)], [B_ROOF] * 3, end=B_GIRDER)
    legs(k, 2.8, 1.6, -SKIRT, 6.6, 1.0, 0.5, 4, 0.1, B_GIRDER)                           # the roost tower
    for z in (3.0, 4.6, 6.2):
        for q in range(4):
            a = TAU * q / 4 + z
            k.tube((2.8, 1.6, z), (2.8 + 1.4 * math.cos(a), 1.6 + 1.4 * math.sin(a), z + 0.2), 0.08, B_GIRDER, sides=4)
    tbox(k, 2.8, 1.6, 6.6, 7.0, 0.8, 0.8, 0.0, B_GIRDER, B_GIRDER, base=B_GIRDER)
    for q in range(16):                                                            # pens of stakes
        a = -0.4 + 1.6 * q / 15
        k.lathe([(0.07, -0.3), (0.06, 1.0), (0.0, 1.2)], [B_GIRDER, B_GIRDER], sides=4, cx=-1.0 + 2.4 * math.cos(a + math.pi),
                cy=-2.4 + 1.4 * math.sin(a + math.pi))
    for x in (0.6, 1.4):                                                           # trophy poles
        k.lathe([(0.06, 0.0), (0.05, 2.6)], B_GIRDER, sides=4, cx=x, cy=-1.4)
        dome(k, x, -1.4, 2.5, 0.2, 0.22, B_PLATE, sides=6, n=2)
    k.lathe([(0.4, 0.0), (0.4, 0.12)], B_GLOW, sides=8, cx=1.0, cy=0.4, cap=B_GLOW)
    for _ in range(6):
        a = rng.uniform(0, TAU)
        kas_trunk(k, 4.8 * math.cos(a), 3.8 * math.sin(a), -SKIRT, rng.uniform(5.0, 7.0), 0.3, rng, crown=1.2,
                  leaf=B_HULL)


# ==================================================================================================== UMBARA
# Umbara (canon, The Clone Wars: the shadow world of permanent dusk, its jungle glowing; the Umbaran capital of dark
# slender spires lit by cold blue light; the Umbaran airbase the 501st took, Umbaran starfighters. Legends: the bunkers
# Grek, Krill and Usk; the Sith Academy of the Brotherhood of Darkness). Umbaran building: dark plate, curved and
# bladed shapes, cyan light bands and window lines.
# Atlas hod_umbara (B_ layout): B_PLATE dark blue-grey plate, B_PLATE_WIN dark plate with cyan window lines, B_GLOW
# cyan light, B_HAZARD violet light, B_ROOF black plate, B_HULL pale fighter grey, B_BRICK old dark stone (the Sith
# ruins), B_RUST deep red glow, B_SOOT dark rock, B_CONC dark paving.
def umb_spire(k, x, y, z0, h, r, rng, lite=False):
    """an Umbaran spire: a dark shaft swelling and narrowing, ringed with cyan light bands, flaring at mid-height into
    hooked blades and ending in a needle"""
    g = max(z0, 0.0)
    H = h - g
    prof = [(r * 1.3, z0), (r, g + H * 0.1), (r * 0.8, g + H * 0.4), (r * 1.15, g + H * 0.62), (r * 0.6, g + H * 0.8),
            (r * 0.18, g + H * 0.97), (0.0, h)]
    k.lathe(prof, [B_PLATE, B_PLATE_WIN, B_PLATE_WIN, B_PLATE, B_PLATE_WIN, B_ROOF], sides=8 if lite else 12, cx=x, cy=y)
    for f in ((0.3, 0.55) if lite else (0.25, 0.45, 0.7)):                         # light bands
        zb = g + H * f
        rb = r * (0.85 + 0.3 * (f > 0.5))
        k.lathe([(rb * 1.04, zb), (rb * 1.04, zb + H * 0.012)], B_GLOW, sides=8 if lite else 12, cx=x, cy=y)
    for q in range(3 if lite else 4):                                              # hooked blades
        a = TAU * q / (3 if lite else 4) + rng.uniform(-0.2, 0.2)
        p0 = (x + r * 0.9 * math.cos(a), y + r * 0.9 * math.sin(a), g + H * 0.5)
        p1 = (x + r * 2.2 * math.cos(a), y + r * 2.2 * math.sin(a), g + H * 0.72)
        k.tube(p0, p1, r * 0.18, B_ROOF, sides=4, r1=r * 0.03)


def umb_block(k, x, y, z0, h, w, a):
    """a low Umbaran building: sloped dark walls, a glowing band under the roof edge"""
    g = max(z0, 0.0)
    tbox(k, x, y, z0, h, w, w * 0.7, a, B_PLATE_WIN, B_ROOF, wt=w * 0.75, dt=w * 0.5)
    tbox(k, x, y, h - (h - g) * 0.12, h - (h - g) * 0.06, w * 0.8, w * 0.55, a, B_GLOW, B_GLOW)


def umb_fighter(k, x, y, z, a, L):
    """an Umbaran starfighter: a ball cockpit, two long curved wings sweeping forward"""
    k.lathe([(0.0, z), (L * 0.18, z + L * 0.08), (L * 0.2, z + L * 0.2), (0.0, z + L * 0.32)], [B_HULL, B_GLOW, B_HULL],
            sides=10, cx=x, cy=y)
    for s_ in (-1, 1):
        p0 = turn(x, y, a, -L * 0.05, s_ * L * 0.18) + (z + L * 0.16,)
        p1 = turn(x, y, a, L * 0.45, s_ * L * 0.55) + (z + L * 0.1,)
        curve_tube(k, p0, p1, L * 0.08, L * 0.05, L * 0.02, B_HULL, n=4, sides=4)


def umb_city(k, band, rng):
    # the Umbaran towns and the capital's districts (the cities.txt 58 set): dark lanes edged with light, low sloped
    # blocks under glowing bands, slender spires downtown, a glowing pad. band 1 outpost .. 4 city
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.25)
    for p in paths:
        sweep(k, p, rect_section(0.09 + 0.01 * band, 0.315, CELL_Z), [B_GLOW, B_CONC, B_GLOW], open_sec=True)
        lots.block_path(p, 0.12 + 0.01 * band)
    for _ in range(3 + band):
        w = rng.uniform(0.08, 0.13)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.07) or lots.spot(w * 1.1)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            umb_block(k, p_[0], p_[1], CELL_Z, rng.uniform(0.14, 0.24) + 0.04 * band, w, a)
    for _ in range(band):
        r = rng.uniform(0.05, 0.07)
        p_ = lots.spot(r * 2.4)
        if p_:
            umb_spire(k, p_[0], p_[1], CELL_Z, rng.uniform(0.6, 0.9) + 0.25 * band, r, rng, lite=True)
    if rng.random() < 0.4:
        p_ = lots.spot(0.1)
        if p_:
            pad(k, p_[0], p_[1], 0.06, 0.09, B_GLOW, B_PAD, sides=10)


def umb_capital(k):
    # the Umbaran capital city (canon, The Clone Wars: the capital the 501st fought toward through the dark): a broad
    # dark deck lined with light, a cluster of slender spires up to ~22 with hooked blades and cyan bands, the tallest
    # the seat of the Umbaran government, glowing sky-bridges between them, low sloped blocks round their feet,
    # starfighters on pads at the edge. ~16 across
    import random
    rng = random.Random("umb_capital")
    g = lobed(0.0, 0.0, 0.0, 7.6, lobes=5, amp=0.08, n=30, phase=0.4, sy=0.85)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.4), scaled(at_z(g, 0.5), 0.98)], [B_PLATE, B_GLOW], cap=B_CONC)
    spires = [(0.0, 0.4, 22.0, 1.2), (-2.8, -0.8, 16.0, 0.9), (2.6, -1.4, 17.0, 0.9), (-1.6, 3.0, 14.0, 0.8),
              (2.4, 2.6, 13.0, 0.8), (-4.6, 2.2, 10.0, 0.7), (4.8, 0.6, 11.0, 0.7), (0.4, -3.6, 12.0, 0.75)]
    for x, y, h, r in spires:
        umb_spire(k, x, y, 0.5, h, r, rng)
    for i, j in ((0, 1), (0, 2), (0, 3), (0, 4), (1, 5), (2, 6), (0, 7)):
        (x0, y0, h0, _), (x1, y1, h1, _) = spires[i], spires[j]
        z = min(h0, h1) * 0.4
        sweep(k, [(x0, y0, z), (x1, y1, z)], rect_section(0.18, 0.12), B_GLOW, caps=B_PLATE)
    for _ in range(18):                                                            # low blocks round their feet
        a, d = rng.uniform(0, TAU), rng.uniform(4.2, 6.8)
        umb_block(k, d * math.cos(a), d * math.sin(a) * 0.85, 0.0, 0.5 + rng.uniform(0.8, 1.8), rng.uniform(0.5, 0.8),
                  a + math.pi / 2)
    for x, y, a in ((6.6, -3.2, 2.4), (-6.4, -3.0, 0.6)):
        pad(k, x, y, 0.55, 1.0, B_GLOW, B_PAD)
        umb_fighter(k, x, y, 0.6, a, 1.6)


def umb_airbase(k):
    # the Umbaran airbase (canon, "Darkness on Umbara": the airbase the 501st captured, near Sector Delta): a dark
    # platform field edged with light, glowing landing pads with Umbaran starfighters on them, two long curved hangars,
    # the control tower (a spire with a glazed head), fuel tanks, AA emplacements. ~16 across
    import random
    rng = random.Random("umb_airbase")
    g = lobed(0.0, 0.0, 0.0, 8.0, lobes=4, amp=0.07, n=28, phase=0.2, sy=0.62)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.3), scaled(at_z(g, 0.4), 0.98)], [B_PLATE, B_GLOW], cap=B_CONC)
    for x, y in ((-4.6, -1.4), (-1.6, -2.2), (1.6, -2.2), (4.6, -1.4)):            # pads and fighters
        pad(k, x, y, 0.5, 1.1, B_GLOW, B_PAD)
        umb_fighter(k, x, y, 0.55, rng.uniform(0, TAU), 1.7)
    for x in (-3.0, 3.0):                                                          # curved hangars
        vault(k, x, 2.4, 0.4, 0.0, 4.2, 1.3, 1.7, [B_ROOF, B_PLATE, B_ROOF, B_PLATE, B_ROOF, B_PLATE], end=B_PLATE_WIN)
        tbox(k, x, 2.4 - 1.32, 0.4, 0.5, 2.0, 0.04, 0.0, B_GLOW, B_GLOW)
    k.lathe([(0.5, 0.4), (0.35, 6.0), (0.9, 6.4), (0.9, 7.2), (0.4, 7.6), (0.0, 8.6)],
            [B_PLATE, B_PLATE, B_PLATE_WIN, B_ROOF, B_ROOF], sides=10, cx=0.0, cy=1.8)              # control tower
    k.lathe([(0.92, 6.7), (0.92, 6.8)], B_GLOW, sides=10, cx=0.0, cy=1.8)
    for x in (6.4, 7.2):                                                           # fuel tanks
        k.lathe([(0.5, -0.2), (0.5, 1.4), (0.0, 1.7)], [B_PLATE, B_ROOF], sides=10, cx=x, cy=1.8)
    for x, y in ((-7.0, 0.6), (6.8, -2.6)):                                        # AA emplacements
        k.lathe([(0.6, 0.0), (0.6, 0.6), (0.4, 0.9)], [B_PLATE, B_ROOF], sides=8, cx=x, cy=y, cap=B_ROOF)
        for s_ in (-0.12, 0.12):
            k.tube((x + s_, y, 0.8), (x + s_, y - 1.1, 1.6), 0.06, B_PLATE, sides=4)


def umb_bunker(k):
    # an Umbaran bunker (Legends: the underground bunkers Grek, Krill and Usk; one model for the three): dug into a
    # dark hill, an armoured dome with glowing firing slits, a blast door in a sloped portal, a twin AA turret, sensor
    # masts with lights, glowing spines growing over the slopes. ~8 across
    import random
    rng = random.Random("umb_bunker")
    rock(k, 0.0, 0.6, -SKIRT, 1.6, 4.0, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3, sy=0.85)
    dome(k, 0.0, 0.4, 1.0, 1.8, 1.3, [B_PLATE, B_PLATE, B_ROOF, B_ROOF], sides=14)
    k.lathe([(1.82, 1.5), (1.82, 1.6)], B_GLOW, sides=14, cx=0.0, cy=0.4)                      # firing slits
    tbox(k, 0.0, -2.4, -0.4, 1.4, 1.0, 0.7, 0.0, B_PLATE, B_ROOF, wt=0.8, dt=0.4)               # the portal
    tbox(k, 0.0, -3.08, -0.3, 0.9, 0.6, 0.04, 0.0, B_HAZARD, B_HAZARD)
    k.lathe([(0.5, 2.2), (0.5, 2.6), (0.3, 2.8)], [B_PLATE, B_ROOF], sides=8, cx=0.0, cy=0.4, cap=B_ROOF)    # turret
    for s_ in (-0.14, 0.14):
        k.tube((s_, 0.4, 2.6), (s_, -1.0, 3.4), 0.06, B_PLATE, sides=4)
    for x, y in ((-2.2, 1.4), (2.4, 1.0)):
        k.lathe([(0.05, 0.6), (0.04, 3.6)], B_PIPE, sides=4, cx=x, cy=y, cap=B_GLOW)
    for _ in range(10):                                                            # glowing spines on the slopes
        a, d = rng.uniform(0, TAU), rng.uniform(2.2, 3.6)
        x, y = d * math.cos(a), 0.6 + d * math.sin(a) * 0.85
        k.lathe([(0.06, 0.0), (0.02, rng.uniform(0.8, 1.6))], B_GLOW, sides=4, cx=x, cy=y)


def umb_academy(k):
    # the Sith Academy of Umbara (Legends: founded by the Brotherhood of Darkness near the end of the New Sith Wars, a
    # ruin a thousand years on): a broken stepped pyramid of dark stone with a red glow in its open crown, a ruined
    # colonnade of square pillars leading to it, toppled statues, a cracked obelisk, the glowing jungle creeping over
    # the stones. ~12 across
    import random
    rng = random.Random("umb_academy")
    rock(k, 0.0, 0.0, -SKIRT, 0.8, 6.0, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=4, sy=0.85)
    for i, (w, z0, z1) in enumerate(((3.4, 0.6, 1.8), (2.7, 1.8, 3.0), (2.0, 3.0, 4.2), (1.3, 4.2, 5.2))):
        tbox(k, 0.0, 1.0, z0 if i else -SKIRT, z1, w, w, 0.0, B_BRICK, B_BRICK, wt=w * 0.92, dt=w * 0.92)
    k.lathe([(0.9, 5.2), (0.9, 5.3)], B_RUST, sides=8, cx=0.0, cy=1.0, cap=B_RUST)            # the red glow
    for q in range(5):                                                             # the broken crown
        a = TAU * q / 5
        k.tube((1.0 * math.cos(a), 1.0 + 1.0 * math.sin(a), 5.2), (1.0 * math.cos(a), 1.0 + 1.0 * math.sin(a),
                                                                  5.2 + rng.uniform(0.4, 1.4)), 0.25, B_BRICK, sides=4)
    for i in range(6):                                                             # the colonnade
        for s_ in (-1, 1):
            h = rng.choice((0.6, 1.2, 2.4, 2.4))
            tbox(k, s_ * 1.0, -2.6 - i * 0.7, 0.4, 0.4 + h, 0.18, 0.18, 0.0, B_BRICK, B_BRICK)
    for x, y, a in ((-2.6, -4.4, 0.7), (2.4, -4.0, -0.4)):                          # toppled statues
        k.tube((x, y, 0.5), (x + 1.8 * math.cos(a), y + 1.8 * math.sin(a), 0.6), 0.4, B_BRICK, sides=6, r1=0.3)
    tbox(k, 4.0, -1.0, -0.4, 4.6, 0.3, 0.3, 0.2, B_BRICK, B_BRICK, wt=0.12, dt=0.12)            # the obelisk
    for _ in range(10):                                                            # glowing jungle over the stones
        a, d = rng.uniform(0, TAU), rng.uniform(3.4, 5.6)
        k.lathe([(0.07, 0.4), (0.02, rng.uniform(0.8, 1.6))], B_GLOW, sides=4, cx=d * math.cos(a), cy=d * math.sin(a) * 0.85)


# ==================================================================================================== COLLA IV
# Colla IV (Legends: the tropical spawnworld of the Colicoids, the insectoid makers of the droideka, whose factory there
# was the main source of them). The look is a design choice from the droideka's own form: ribbed chitin hive spires
# with amber-lit openings, segmented beetle-shell halls, tunnels, rolled droidekas in rows.
# Atlas hod_colla (B_ layout): B_PLATE ribbed chitin, B_PLATE_WIN chitin with amber-lit openings, B_ROOF dark glossy
# shell plate, B_HULL pale egg ivory, B_GLOW amber, B_CONC_WIN murky spawning water, B_RUST droideka bronze, B_GIRDER
# / B_PIPE metal, B_SOOT earth, B_DUST red earth.
def col_spire(k, x, y, z0, h, r, rng, lite=False):
    """a Colicoid hive spire: a fluted chitin shaft bulging and narrowing like a termite tower, lit openings in bands"""
    g = max(z0, 0.0)
    H = h - g
    ribs = 6 if lite else 9
    rot = rng.uniform(0, 1)
    prof = [(1.25, 0.0), (1.0, 0.2), (1.1, 0.45), (0.75, 0.7), (0.4, 0.9), (0.08, 1.0)]
    rings = [star(x, y, (z0 if t == 0 else g + H * t), r * f, 0.16, ribs, rot + t) for f, t in prof]
    loft(k, rings, [B_PLATE, B_PLATE_WIN, B_PLATE, B_PLATE_WIN, B_PLATE], cap=B_PLATE)


def col_shell(k, x, y, z0, L, w, h, a, n=4):
    """a segmented beetle-shell hall: overlapping arched shell segments stepping down toward its tail"""
    seg = L / n
    for i in range(n):
        f = 1.0 - 0.12 * i
        cx, cy = turn(x, y, a, L / 2 - seg * (i + 0.5), 0.0)
        vault(k, cx, cy, z0, a, seg * 1.15, w * f, h * f, [B_ROOF, B_ROOF, B_PLATE, B_ROOF, B_ROOF, B_PLATE], end=B_PLATE_WIN)


def col_droideka(k, x, y, z, s):
    """a droideka rolled into its wheel form"""
    k.lathe([(s * 0.2, z), (s * 0.45, z + s * 0.1), (s * 0.5, z + s * 0.5), (s * 0.45, z + s * 0.9), (s * 0.2, z + s)],
            [B_RUST, B_RUST, B_RUST, B_RUST], sides=10, cx=x, cy=y)


def col_city(k, band, rng):
    # the Colicoid hive towns (the cities.txt 59 set): earthen lanes, hive spires, low chitin dome cells clustered,
    # shell halls, tunnel tubes between the spires. band 1 cluster .. 4 hive town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.4)
    for p in paths:
        sweep(k, p, rect_section(0.08 + 0.01 * band, 0.315, CELL_Z), [B_DUST, B_DUST, B_DUST], open_sec=True)
        lots.block_path(p, 0.11 + 0.01 * band)
    tops = []
    for _ in range(1 + band // 2):
        r = rng.uniform(0.08, 0.12)
        p_ = lots.spot(r * 1.6)
        if p_:
            h = rng.uniform(0.5, 0.8) + 0.2 * band
            col_spire(k, p_[0], p_[1], CELL_Z, h, r, rng, lite=True)
            tops.append((p_[0], p_[1], h))
    for (x0, y0, h0), (x1, y1, h1) in zip(tops, tops[1:]):
        k.tube((x0, y0, min(h0, h1) * 0.4), (x1, y1, min(h0, h1) * 0.4), 0.03, B_PLATE, sides=6)
    for _ in range(3 + band):                                                      # dome cells
        r = rng.uniform(0.06, 0.1)
        p_ = lots.spot(r * 1.05)
        if p_:
            k.lathe([(r, CELL_Z), (r, 0.02)], B_PLATE_WIN, sides=8, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.02, r, r * 0.8, B_ROOF, sides=8, n=3)
    if band >= 2:
        p_ = lots.spot(0.2)
        if p_:
            col_shell(k, p_[0], p_[1], CELL_Z, 0.36, 0.1, 0.3, rng.uniform(0, math.pi), n=3)


def col_hive(k):
    # the Colicoid hive capital (invented: the Legends sources name no city): a mass of fluted chitin hive spires up
    # to ~18, packed together and joined by tunnel tubes at several heights, low dome cells round their feet, a
    # segmented shell hall for the hive council, amber light in every opening, a landing pad. ~15 across
    import random
    rng = random.Random("col_hive")
    g = lobed(0.0, 0.0, 0.0, 7.2, lobes=5, amp=0.12, n=30, phase=0.3, sy=0.85)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.3), scaled(at_z(g, 0.4), 0.97)], [B_SOOT, B_SOOT], cap=B_DUST)
    spires = [(0.4, 0.4, 18.0, 1.6), (-2.6, -0.6, 13.0, 1.2), (2.8, -1.4, 12.0, 1.1), (-1.0, 3.0, 11.0, 1.1),
              (2.8, 2.6, 10.0, 1.0), (-4.2, 2.2, 8.0, 0.9), (-0.6, -3.4, 9.0, 0.95), (4.6, 0.6, 7.5, 0.85)]
    for x, y, h, r in spires:
        col_spire(k, x, y, 0.3, h, r, rng)
    for i, j in ((0, 1), (0, 2), (0, 3), (0, 4), (1, 5), (1, 6), (2, 7), (3, 5)):
        (x0, y0, h0, _), (x1, y1, h1, _) = spires[i], spires[j]
        for f in (0.3, 0.55):
            z = min(h0, h1) * f
            k.tube((x0, y0, z), (x1, y1, z), 0.28, B_PLATE, sides=8)
    for _ in range(18):                                                            # dome cells
        a, d = rng.uniform(0, TAU), rng.uniform(4.4, 6.6)
        x, y, r = d * math.cos(a), d * math.sin(a) * 0.85, rng.uniform(0.5, 0.8)
        k.lathe([(r, 0.0), (r, 0.4)], B_PLATE_WIN, sides=10, cx=x, cy=y)
        dome(k, x, y, 0.4, r, r * 0.8, B_ROOF, sides=10, n=3)
    col_shell(k, -3.4, -3.6, 0.3, 3.6, 1.0, 1.8, 0.5)                               # the council hall
    pad(k, 5.6, -3.4, 0.5, 1.0, B_GLOW, B_PAD)


def col_nest(k):
    # the Colicoid Creation Nest (Legends: the factory on Colla IV that was the main source of the droidekas): three
    # great segmented shell halls side by side, conveyor tubes running out of them to a yard where rolled droidekas
    # stand in ranks, test rings where they uncurl, vent spires of chitin breathing heat, a cargo pad with a Trade
    # Federation freighter. ~16 across
    import random
    rng = random.Random("col_nest")
    g = lobed(0.0, 0.0, 0.0, 8.0, lobes=4, amp=0.07, n=28, phase=0.6, sy=0.66)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.25), scaled(at_z(g, 0.35), 0.98)], [B_SOOT, B_SOOT], cap=B_CONC)
    for y in (-2.0, 0.0, 2.0):                                                     # the shell halls
        col_shell(k, -2.0, y * 1.1, 0.3, 7.0, 1.0, 2.4 - abs(y) * 0.15, 0.0, n=5)
    for y in (-2.2, 0.0, 2.2):                                                     # conveyors to the yard
        k.tube((1.6, y, 0.9), (4.0, y * 0.6, 0.9), 0.22, B_PIPE, sides=6)
    for i in range(5):                                                             # droidekas in ranks
        for j in range(4):
            col_droideka(k, 4.6 + i * 0.6, -1.2 + j * 0.65, 0.35, 0.5)
    for x, y in ((5.4, 2.6), (6.6, 2.6)):                                          # test rings
        k.lathe([(0.7, 0.3), (0.7, 0.4)], B_GLOW, sides=14, cx=x, cy=y, cap=B_CONC)
    for x, y in ((-5.8, -3.2), (-4.2, 3.4), (0.4, -3.8)):                          # vent spires
        col_spire(k, x, y, 0.3, rng.uniform(5.0, 7.0), 0.6, rng)
    pad(k, 3.0, -4.6, 0.6, 1.4, B_GLOW, B_PAD)
    shuttle(k, 3.0, -4.6, 0.6, 0.0, 2.6, B_HULL, B_PLATE_WIN)


def col_spawn(k):
    # the Colicoid spawning grounds (invented: Colla IV was the Colicoids' spawnworld): pools of murky water in a
    # swampy hollow, pale egg clusters heaped on mud banks between them, ribbed organic arches over the pools, brood
    # mounds round the edge with lit openings, tunnels into the ground. ~12 across
    import random
    rng = random.Random("col_spawn")
    for x, y, r in ((-2.0, 0.6, 2.0), (2.0, -0.6, 1.8), (0.4, 2.8, 1.4), (-0.6, -2.6, 1.5)):   # the pools
        k.lathe([(r * 1.2, -SKIRT), (r * 1.15, 0.2), (r, 0.15), (0.0, -0.1)], [B_SOOT, B_DUST, B_CONC_WIN], sides=14,
                cx=x, cy=y)
    for _ in range(14):                                                            # egg clusters on the banks
        a, d = rng.uniform(0, TAU), rng.uniform(0.0, 4.4)
        x, y = d * math.cos(a), d * math.sin(a) * 0.85
        for q in range(rng.randint(3, 6)):
            ex, ey = x + rng.uniform(-0.4, 0.4), y + rng.uniform(-0.4, 0.4)
            r = rng.uniform(0.18, 0.3)
            k.lathe([(r * 0.5, 0.1), (r, 0.1 + r * 0.6), (r * 0.7, 0.1 + r * 1.5), (0.0, 0.1 + r * 1.9)],
                    [B_HULL, B_HULL, B_HULL], sides=8, cx=ex, cy=ey)
    for x0, y0, x1, y1 in ((-3.6, -1.4, -0.4, 2.4), (0.6, -2.6, 3.6, 1.4)):         # ribbed arches over the pools
        curve_tube(k, (x0, y0, 0.0), (x1, y1, 0.0), 3.2, 0.3, 0.3, B_PLATE, n=10, sides=8)
    for _ in range(9):                                                             # brood mounds round the edge
        a = rng.uniform(0, TAU)
        col_spire(k, 5.4 * math.cos(a), 4.6 * math.sin(a), -SKIRT, rng.uniform(2.4, 4.0), 0.6, rng)
    for x, y, a in ((-4.6, 2.6, 0.6), (4.4, -2.8, 2.4)):                            # tunnels
        vault(k, x, y, -0.4, a, 1.0, 0.6, 0.8, [B_PLATE] * 6, end=B_DARK)


# ==================================================================================================== RUUSAN
# Ruusan (Legends: the last battles of the New Sith Wars, the Valley of the Jedi and the mausoleum raised over the
# fallen, the Army of Light under Lord Hoth and Valenthyne Farfalla, Olmondo the old capital, Fort Nowhere beside
# Katarn's Hill; the user, 2026-10-19: the light-side mirror of Korriban). Pale Jedi stone, verdigris roofs and gold
# where Korriban has dark stone and red; the towns of tan fieldstone under green roofs.
# Atlas hod_ruusan (B_ layout): B_PLATE pale Jedi stone, B_PLATE_WIN pale stone with gold-lit windows, B_GLOW gold
# light, B_HAZARD blue light (the blades, the souls in the cave), B_ROOF verdigris copper, B_BRICK tan fieldstone,
# B_HULL weathered canvas and hull, B_RUST charred stone, B_SOOT brown canyon rock, B_CONC sand paving, B_DUST earth.
def rus_statue(k, x, y, z0, h, a, blade=True):
    """a robed Jedi on a plinth: the robe flaring to the ground, hooded head, a blade raised in salute"""
    tbox(k, x, y, z0 - 0.4, z0 + h * 0.12, h * 0.2, h * 0.2, a, B_PLATE, B_PLATE)
    z = z0 + h * 0.12
    k.lathe([(h * 0.17, z), (h * 0.12, z + h * 0.4), (h * 0.09, z + h * 0.62), (h * 0.11, z + h * 0.7),
             (h * 0.05, z + h * 0.76)], [B_PLATE] * 4, sides=8, cx=x, cy=y)
    k.lathe([(h * 0.06, z + h * 0.75), (h * 0.065, z + h * 0.82), (0.0, z + h * 0.88)], [B_PLATE, B_PLATE], sides=8,
            cx=x, cy=y)
    if blade:
        hx, hy = turn(x, y, a, h * 0.1, 0.0)
        k.tube((hx, hy, z + h * 0.55), (hx, hy, z + h * 1.15), h * 0.02, B_HAZARD, sides=4)


def rus_house(k, x, y, z0, w, d, h, a):
    """a Ruusanian house: tan fieldstone under a green gabled roof"""
    tbox(k, x, y, z0, h, w, d, a, B_BRICK, B_ROOF)
    prism_at(k, x, y, h, a, 2 * w * 1.08, [(d * 1.15, 0.0), (0.0, d * 0.8), (-d * 1.15, 0.0)], [B_ROOF] * 3, end=B_BRICK)


def rus_city(k, band, rng):
    # the Ruusanian towns and Olmondo's quarters (the cities.txt 60 set): earth lanes, fieldstone houses under green
    # roofs, fenced plots on the edges of the small ones, a domed shrine in the bigger towns. band 1 village .. 4 town
    lots = Lots(rng, 0.95)
    paths, hub = streets(rng, 0.0, wiggle=0.35)
    for p in paths:
        sweep(k, p, rect_section(0.08 + 0.012 * band, 0.315, CELL_Z), [B_DUST, B_CONC, B_DUST], open_sec=True)
        lots.block_path(p, 0.12 + 0.012 * band)
    for _ in range(3 + band * 2):
        w = rng.uniform(0.07, 0.11)
        p_ = lots.along(rng.choice(paths), w * 1.1, 0.08) or lots.spot(w * 1.1)
        if p_:
            a = p_[2] if len(p_) > 2 else rng.uniform(0, math.pi)
            rus_house(k, p_[0], p_[1], CELL_Z, w, w * 0.65, rng.uniform(0.1, 0.15) + 0.02 * band, a)
    if band >= 3:
        p_ = lots.spot(0.13)
        if p_:
            k.lathe([(0.11, CELL_Z), (0.11, 0.3)], B_PLATE_WIN, sides=10, cx=p_[0], cy=p_[1])
            dome(k, p_[0], p_[1], 0.3, 0.12, 0.13, [B_ROOF] * 4, sides=10)
    for _ in range(max(0, 3 - band)):                                              # fenced plots
        p_ = lots.spot(0.15)
        if p_:
            a = rng.uniform(0, math.pi)
            sq = [turn(p_[0], p_[1], a, u, v) + (0.0,) for u, v in ((-0.13, -0.1), (0.13, -0.1), (0.13, 0.1), (-0.13, 0.1))]
            sweep(k, sq, rect_section(0.012, 0.06, CELL_Z), B_GIRDER, closed_path=True)


def rus_mausoleum(k):
    # the Jedi Mausoleum (Legends: the grand mausoleum Johun Othone had the Senate raise over the fallen in the Valley
    # of the Jedi; its form a design choice, the light-side answer to Korriban's academy): a broad stepped terrace of
    # pale stone, a domed rotunda in a ring of columns with gold-lit windows and a gold lantern, four slender corner
    # towers, a ring of robed Jedi statues raising their blades round it and an avenue of statues leading east down the
    # valley. ~18 across
    import random
    rng = random.Random("rus_mausoleum")
    g = lobed(0.0, 0.0, 0.0, 7.2, lobes=4, amp=0.04, n=32, phase=0.3, sy=0.9)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.5), scaled(at_z(g, 0.5), 0.86), scaled(at_z(g, 1.2), 0.86)],
         [B_PLATE, B_CONC, B_PLATE], cap=B_CONC)
    k.lathe([(3.0, 1.2), (3.0, 1.6), (2.6, 1.6)], [B_PLATE, B_PLATE], sides=24, cx=0.0, cy=0.0, cap=B_CONC)   # podium
    k.lathe([(2.2, 1.6), (2.2, 5.6)], B_PLATE_WIN, sides=20, cx=0.0, cy=0.0)                  # the rotunda
    for q in range(16):                                                            # its colonnade
        a = TAU * q / 16
        k.lathe([(0.16, 1.6), (0.13, 5.2), (0.2, 5.5)], [B_PLATE, B_PLATE], sides=6, cx=2.85 * math.cos(a),
                cy=2.85 * math.sin(a))
    k.lathe([(3.15, 5.5), (3.15, 6.0), (2.5, 6.0)], [B_PLATE, B_GLOW], sides=24, cx=0.0, cy=0.0)            # entablature
    dome(k, 0.0, 0.0, 6.0, 2.6, 2.6, [B_ROOF, B_ROOF, B_ROOF, B_GLOW], sides=20, cap_r=0.5)
    k.lathe([(0.5, 8.6), (0.5, 9.4), (0.0, 10.4)], [B_GLOW, B_GLOW], sides=8, cx=0.0, cy=0.0)                  # lantern
    for sx, sy_ in ((-1, -1), (1, -1), (1, 1), (-1, 1)):                           # corner towers
        x, y = sx * 4.4, sy_ * 3.9
        tbox(k, x, y, 1.2, 7.4, 0.55, 0.55, 0.0, B_PLATE, B_PLATE, wt=0.4, dt=0.4)
        tbox(k, x, y, 6.6, 7.0, 0.42, 0.42, 0.0, B_PLATE_WIN, B_PLATE_WIN)
        k.lathe([(0.45, 7.4), (0.0, 9.0)], B_ROOF, sides=4, cx=x, cy=y, rot=math.pi / 4)
    for q in range(10):                                                            # the ring of statues
        a = TAU * (q + 0.5) / 10
        rus_statue(k, 4.6 * math.cos(a), 4.6 * math.sin(a) * 0.9, 1.2, 2.6, a)
    for i in range(4):                                                             # the avenue east
        for s_ in (-1, 1):
            rus_statue(k, 7.4 + i * 1.5, s_ * 1.3, 0.3, 2.2, -s_ * math.pi / 2)
    sweep(k, [(6.2, 0.0, 0.0), (12.4, 0.0, 0.0)], rect_section(0.7, 0.35, -0.4), B_CONC, caps=B_PLATE)
    for _ in range(8):                                                             # fallen stones of the old battle
        a, d = rng.uniform(0, TAU), rng.uniform(6.6, 8.2)
        rock(k, d * math.cos(a), d * math.sin(a) * 0.9, -0.2, 0.3 + rng.uniform(0, 0.4), 0.35, rng, [B_RUST] * 3,
             lobes=2, tiers=2)


def rus_cave(k):
    # the Thought-bomb Cave (invented name: Legends, the cave in the Valley of the Jedi where Kaan detonated the thought
    # bomb that took the Brotherhood of Darkness and the Jedi with them, their souls bound there): a scorched rock
    # outcrop, a broad dark cave mouth glowing blue within, its entrance half walled up in pale stone, a white obelisk
    # in front, a ring of standing stones, charred snags. ~10 across
    import random
    rng = random.Random("rus_cave")
    rock(k, 0.0, 1.6, -SKIRT, 2.8, 5.2, rng, [B_SOOT, B_SOOT, B_RUST], lobes=5, sy=0.7)
    rock(k, -2.4, 2.4, 0.0, 3.6, 2.0, rng, [B_SOOT, B_SOOT, B_SOOT], lobes=3)                    # the crags over it
    rock(k, 2.2, 2.0, 0.0, 3.2, 1.8, rng, [B_SOOT, B_SOOT, B_RUST], lobes=3)
    tbox(k, 0.0, -1.9, -0.4, 2.6, 2.0, 0.9, 0.0, B_SOOT, B_SOOT, wt=1.3, dt=0.7)                # the mouth's frame
    tbox(k, 0.0, -2.82, -0.3, 2.2, 1.5, 0.04, 0.0, B_DARK, B_DARK, wt=0.9)                      # the dark
    tbox(k, 0.0, -2.84, 0.2, 1.5, 0.9, 0.03, 0.0, B_HAZARD, B_HAZARD, wt=0.45)                  # the souls' glow
    for s_ in (-1, 1):                                                             # the half-built seal
        tbox(k, s_ * 1.25, -2.95, -0.4, 1.0 + 0.5 * (s_ > 0), 0.4, 0.2, 0.0, B_PLATE, B_PLATE)
    tbox(k, 0.0, -5.4, -0.4, 4.2, 0.35, 0.35, 0.0, B_PLATE, B_PLATE, wt=0.18, dt=0.18)          # the obelisk
    k.lathe([(0.2, 4.2), (0.0, 4.8)], B_GLOW, sides=4, cx=0.0, cy=-5.4, rot=math.pi / 4)
    for q in range(9):                                                             # standing stones
        a = -math.pi / 2 + (q - 4) * 0.32
        x, y = 3.4 * math.cos(a), -2.6 + 2.4 * math.sin(a)
        tbox(k, x, y, -0.4, rng.uniform(0.8, 1.5), 0.25, 0.18, a, B_PLATE, B_PLATE)
    for _ in range(6):                                                             # charred snags
        a, d = rng.uniform(0, TAU), rng.uniform(4.4, 5.6)
        x, y = d * math.cos(a), 1.2 + d * math.sin(a) * 0.8
        k.tube((x, y, -0.2), (x + rng.uniform(-0.3, 0.3), y + rng.uniform(-0.3, 0.3), rng.uniform(1.4, 2.6)), 0.14,
               B_RUST, sides=5, r1=0.04)


def rus_camp(k):
    # an Army of Light encampment (Legends: Lord Hoth's and Valenthyne Farfalla's army of Jedi and Republic troops in
    # the Ruusan campaign; one model for both camps, a thousand years on): an earthwork ring, the general's statue on
    # a tall plinth, rows of grave stelae, weathered banners on poles, the frames of the old command tents, a
    # repulsortank hull rusting by the gate. ~11 across
    import random
    rng = random.Random("rus_camp")
    ring = lobed(0.0, 0.0, 0.0, 4.6, lobes=3, amp=0.05, n=24, phase=0.7, sy=0.85)
    sweep(k, ring, trap_section(0.9, 0.4, 0.8, -0.4), B_DUST, closed_path=True)              # the earthwork
    tbox(k, 0.0, 0.6, -0.4, 1.6, 0.9, 0.9, 0.0, B_PLATE, B_PLATE, wt=0.7, dt=0.7)                # the plinth
    rus_statue(k, 0.0, 0.6, 1.6, 3.4, -math.pi / 2)
    for i in range(4):                                                             # grave stelae
        for j in range(5):
            tbox(k, -2.4 + j * 0.6, -1.4 - i * 0.55, -0.3, 0.5, 0.16, 0.06, 0.0, B_PLATE, B_PLATE)
    for x, y in ((-2.6, 1.8), (2.6, 1.8), (-1.2, 2.8), (1.2, 2.8)):                 # banners
        k.lathe([(0.05, 0.0), (0.04, 3.2)], B_GIRDER, sides=4, cx=x, cy=y, cap=B_GLOW)
        tbox(k, x + 0.4, y, 1.8, 3.0, 0.36, 0.02, 0.0, B_HULL, B_HULL)
    for x, y, a in ((2.6, -1.0, 0.3), (2.8, 0.6, -0.2)):                           # tent frames
        prism_at(k, x, y, -0.2, a, 1.6, [(0.6, 0.0), (0.0, 0.9), (-0.6, 0.0)], [B_HULL] * 3, end=B_GIRDER)
    k.tube((-3.0, -3.6, 0.3), (-1.4, -4.2, 0.4), 0.55, B_RUST, sides=6, r1=0.45)                 # the old hull
    for _ in range(6):
        a, d = rng.uniform(0, TAU), rng.uniform(5.4, 6.4)
        rock(k, d * math.cos(a), d * math.sin(a) * 0.85, -0.2, 0.5, 0.35, rng, [B_SOOT] * 3, lobes=2, tiers=2)


def rus_fort(k):
    # Fort Nowhere (Legends: the smugglers' settlement beside Katarn's Hill, Ruusan's spaceport for the spacers and
    # fugitives of the sector; here already a smugglers' haunt): a ring wall of salvaged plate, prefab domes, a
    # cantina block with a lit sign, a landing pad with a light freighter on it, stacked crates, a comm mast. ~11 across
    import random
    rng = random.Random("rus_fort")
    wall = [(-4.6, -3.4, 0.0), (4.2, -3.8, 0.0), (5.0, 2.6, 0.0), (-0.4, 4.2, 0.0), (-4.8, 2.4, 0.0)]
    sweep(k, wall, trap_section(0.5, 0.35, 1.5, -0.5), B_HULL, closed_path=True)
    for x, y in ((-4.6, -3.4), (4.2, -3.8), (5.0, 2.6), (-4.8, 2.4)):               # watch posts
        k.lathe([(0.5, -0.4), (0.45, 2.4), (0.6, 2.6)], [B_HULL, B_HULL], sides=8, cx=x, cy=y, cap=B_ROOF)
    for x, y, r in ((-2.6, 1.6, 1.0), (-3.0, -1.4, 0.8), (-0.6, 2.6, 0.7)):         # prefab domes
        dome(k, x, y, -0.2, r, r * 0.85, [B_PLATE, B_PLATE, B_PLATE, B_ROOF], sides=12)
    tbox(k, 0.0, -1.6, -0.4, 1.5, 1.2, 0.8, 0.2, B_BRICK, B_ROOF)                               # the cantina
    tbox(k, 0.0, -1.6, 1.0, 1.3, 1.22, 0.82, 0.2, B_GLOW, B_GLOW)
    pad(k, 2.6, 0.4, 0.3, 1.5, B_CONC, B_PAD)                                       # the pad and its freighter
    shuttle(k, 2.6, 0.4, 0.3, 2.2, 2.6, B_HULL, B_PLATE_WIN)
    for _ in range(8):                                                             # crates
        x, y = rng.uniform(-1.6, 1.0), rng.uniform(0.6, 1.8)
        tbox(k, x, y, -0.2, rng.uniform(0.25, 0.5), 0.2, 0.2, rng.uniform(0, 1), B_HULL, B_ROOF)
    k.lathe([(0.08, 0.0), (0.05, 5.0)], B_GIRDER, sides=4, cx=-1.6, cy=-3.0, cap=B_GLOW)         # the mast
    k.tube((-1.6, -3.0, 4.2), (-0.8, -3.0, 4.4), 0.3, B_PLATE, sides=8, r1=0.05)


def rus_olmondo(k):
    # Olmondo (Legends: Ruusan's capital; its form a design choice: a living old town, the Korriban mirror's Dreshdae
    # alive): a raised oval of the old town in fieldstone and green roofs packed round a central square, the domed
    # assembly hall and its bell tower over it, a stone gate on the valley road, the starport's pads with freighters
    # on the edge, town walls of tan stone. ~18 across
    import random
    rng = random.Random("rus_olmondo")
    g = lobed(0.0, 0.0, 0.0, 8.0, lobes=5, amp=0.07, n=32, phase=0.1, sy=0.8)
    loft(k, [at_z(g, -SKIRT), at_z(g, 0.6), scaled(at_z(g, 0.6), 0.97)], [B_BRICK, B_CONC], cap=B_CONC)
    tbox(k, 0.0, 0.0, 0.4, 3.6, 1.8, 1.4, 0.0, B_PLATE_WIN, B_PLATE)                            # the assembly hall
    dome(k, 0.0, 0.0, 3.6, 1.5, 1.6, [B_ROOF, B_ROOF, B_ROOF, B_GLOW], sides=16, cap_r=0.3)
    tbox(k, 2.4, -0.6, 0.4, 7.2, 0.5, 0.5, 0.0, B_PLATE, B_PLATE, wt=0.42, dt=0.42)               # the bell tower
    tbox(k, 2.4, -0.6, 6.2, 6.8, 0.46, 0.46, 0.0, B_PLATE_WIN, B_PLATE_WIN)
    k.lathe([(0.55, 7.2), (0.0, 8.6)], B_ROOF, sides=4, cx=2.4, cy=-0.6, rot=math.pi / 4)
    lots = Lots(rng, 7.0)
    lots.taken = [(0.0, 0.0, 2.8), (2.4, -0.6, 0.9), (5.6, -2.6, 1.8), (-5.2, -2.8, 1.8)]
    for _ in range(600):                                                           # the old town
        a, d = rng.uniform(0, TAU), rng.uniform(2.6, 7.0)
        x, y = d * math.cos(a), d * math.sin(a) * 0.8
        w = rng.uniform(0.35, 0.6)
        if lots.free(x, y, w * 1.05):
            lots.take(x, y, w * 1.05)
            rus_house(k, x, y, 0.4, w, w * 0.65, 0.9 + rng.uniform(0.3, 1.0) * (1.4 - d / 7), a + math.pi / 2)
    for x, y, h in ((5.6, -2.6, 0.7), (-5.2, -2.8, 0.7)):                          # the starport pads
        pad(k, x, y, h, 1.5, B_CONC, B_PAD)
        shuttle(k, x, y, h, rng.uniform(0, TAU), 2.2, B_HULL, B_PLATE_WIN)
    gx, gy = 7.6, 0.6                                                              # the valley gate
    for s_ in (-1, 1):
        tbox(k, gx, gy + s_ * 0.9, -0.4, 2.8, 0.5, 0.45, 0.0, B_BRICK, B_ROOF)
    tbox(k, gx, gy, 2.0, 2.8, 0.5, 0.5, 0.0, B_BRICK, B_ROOF)
