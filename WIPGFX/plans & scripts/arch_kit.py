"""Architecture kit for the planet landmark and city meshes built by military_buildings.py models (Blender), and the
landmarks / city sets of Etti IV, Mon Cala, Lianna, Jabiim, Saleucami and Bonadan built with it.

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
