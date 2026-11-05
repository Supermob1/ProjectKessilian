"""Hearts of Durasteel vector pictograms: our own Star Wars icon set, drawn as shapes in a 100x100 space, rendered
at 8x and scaled down anti-aliased. Style = the mod's toolbar icons: one flat colour (cyan, gold hover/selected,
grey disabled), detail as cut-outs, no shading.

  python -B hod_vector.py --sheet OUT.png       every pictogram on one sheet
"""
import argparse, math
from PIL import Image, ImageDraw

S = 8                       # pixels per unit at draw time (100 units -> 800 px)


class Pen:
    def __init__(self):
        self.im = Image.new("L", (100 * S, 100 * S), 0)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def _p(pts):
        return [(x * S, y * S) for x, y in pts]

    def poly(self, pts, cut=False):
        self.d.polygon(self._p(pts), fill=0 if cut else 255)

    def circle(self, cx, cy, r, cut=False):
        self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=0 if cut else 255)

    def ellipse(self, x0, y0, x1, y1, cut=False):
        self.d.ellipse([x0 * S, y0 * S, x1 * S, y1 * S], fill=0 if cut else 255)

    def ring(self, cx, cy, r, w, cut=False):
        self.circle(cx, cy, r, cut)
        self.circle(cx, cy, r - w, not cut)

    def rect(self, x0, y0, x1, y1, cut=False):
        self.d.rectangle([x0 * S, y0 * S, x1 * S - 1, y1 * S - 1], fill=0 if cut else 255)

    def rrect(self, x0, y0, x1, y1, r, cut=False):
        self.d.rounded_rectangle([x0 * S, y0 * S, x1 * S - 1, y1 * S - 1], r * S, fill=0 if cut else 255)

    def line(self, pts, w, cut=False, caps=True):
        self.d.line(self._p(pts), fill=0 if cut else 255, width=int(w * S), joint="curve")
        if caps:
            for x, y in (pts[0], pts[-1]):
                self.circle(x, y, w / 2, cut)

    def arc(self, cx, cy, r, a0, a1, w, cut=False):
        self.d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], a0, a1, fill=0 if cut else 255,
                   width=int(w * S))

    def reg(self, cx, cy, r, n, rot=0, cut=False):
        self.poly([(cx + r * math.cos(math.radians(rot + 360 * i / n)), cy + r * math.sin(math.radians(rot + 360 * i / n)))
                   for i in range(n)], cut)

    def star(self, cx, cy, r1, r2, n, rot=-90, cut=False):
        pts = []
        for i in range(2 * n):
            r = r1 if i % 2 == 0 else r2
            a = math.radians(rot + 180 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.poly(pts, cut)

    def over(self, fn, gap=3.0):
        """Draws fn(pen) on top with a dark gap around it: the layered look of the toolbar icons."""
        import numpy as np
        from scipy import ndimage
        q = Pen(); fn(q)
        top = np.array(q.im)
        halo = ndimage.distance_transform_edt(top < 128) <= gap * S
        base = np.array(self.im)
        base[halo] = 0
        self.im.paste(Image.fromarray(np.maximum(base, top)))

    def stamp(self, name, cx, cy, size, gap=3.0):
        """Another pictogram (simple form) as a secondary element at (cx, cy), size units wide."""
        im = render(name, int(size * S), int(size * S), simple=True)
        def fn(q):
            q.im.paste(im, (int((cx - size / 2) * S), int((cy - size / 2) * S)))
        self.over(fn, gap)

    def at(self, cx, cy, r, a):
        return (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))

    def sym(self, pts, cut=False):
        """polygon given for the left half (x <= 50); mirrored to a symmetric shape."""
        self.poly(pts + [(100 - x, y) for x, y in reversed(pts)], cut)


ICONS = {}


def icon(*names):
    def reg(fn):
        for n in names:
            ICONS[n] = fn
        return fn
    return reg


# ---------------------------------------------------------------- factions / emblems
@icon("republic")
def _(p):
    p.ring(50, 50, 46, 7)
    for i in range(8):
        a = math.radians(i * 45 - 90)
        b, c = math.radians(i * 45 - 90 - 11), math.radians(i * 45 - 90 + 11)
        p.poly([(50 + 15 * math.cos(a - 0.35), 50 + 15 * math.sin(a - 0.35)), (50 + 38 * math.cos(b), 50 + 38 * math.sin(b)),
                (50 + 38 * math.cos(c), 50 + 38 * math.sin(c)), (50 + 15 * math.cos(a + 0.35), 50 + 15 * math.sin(a + 0.35))])
    p.circle(50, 50, 10)


@icon("cis")
def _(p):
    p.ring(50, 50, 47, 7)
    p.reg(50, 50, 34, 6, -90)
    p.reg(50, 50, 28, 6, -90, cut=True)
    for i in range(6):
        a = math.radians(i * 60 - 90)
        p.line([(50, 50), (50 + 30 * math.cos(a), 50 + 30 * math.sin(a))], 5, caps=False)
    p.circle(50, 50, 11)
    p.circle(50, 50, 5, cut=True)


@icon("ibc")
def _(p):
    p.star(50, 50, 48, 17, 4)
    p.circle(50, 50, 24)
    p.ring(50, 50, 17, 3, cut=True)


@icon("jedi")
def _(p):
    p.rect(46, 10, 54, 72)                     # blade
    p.rrect(42, 72, 58, 92, 2)                 # hilt
    p.rect(42, 78, 58, 80, cut=True)
    for s in (1, -1):                          # wings
        p.poly([(50 - s * 8, 54), (50 - s * 40, 30), (50 - s * 34, 46), (50 - s * 44, 50), (50 - s * 30, 60),
                (50 - s * 38, 68), (50 - s * 8, 66)])
    p.arc(50, 78, 20, 200, 340, 4)


@icon("sith")
def _(p):
    p.reg(50, 50, 46, 6, -90)
    p.reg(50, 50, 38, 6, -90, cut=True)
    p.poly([(50, 18), (60, 50), (50, 82), (40, 50)])
    p.poly([(50, 34), (54, 50), (50, 66), (46, 50)], cut=True)


# ---------------------------------------------------------------- troops & vehicles
@icon("trooper")
def _(p):
    p.circle(50, 42, 32)
    p.rect(18, 42, 82, 72)
    p.poly([(18, 72), (82, 72), (74, 88), (26, 88)])
    p.poly([(24, 38), (76, 38), (76, 48), (56, 48), (56, 74), (44, 74), (44, 48), (24, 48)], cut=True)   # T-visor
    p.rect(30, 78, 38, 82, cut=True)
    p.rect(62, 78, 70, 82, cut=True)
    p.rect(20, 26, 80, 29, cut=True)


@icon("droid")
def _(p):
    p.ellipse(28, 12, 72, 52)                  # dome
    p.rect(28, 32, 72, 78)                     # body
    p.circle(50, 26, 6, cut=True)              # eye
    p.rect(34, 40, 66, 44, cut=True)
    p.rect(34, 50, 46, 66, cut=True)
    p.rect(54, 50, 66, 54, cut=True)
    for x in (14, 76):                         # legs
        p.rrect(x, 36, x + 10, 84, 3)
        p.poly([(x - 4, 84), (x + 14, 84), (x + 12, 92), (x - 2, 92)])
    p.poly([(40, 78), (60, 78), (56, 88), (44, 88)])



@icon("walker")
def _(p):
    p.rrect(14, 30, 80, 52, 6)                 # AT-TE body
    p.poly([(80, 34), (94, 38), (94, 48), (80, 50)])
    p.rrect(40, 20, 60, 30, 2)                 # turret
    p.line([(60, 24), (86, 18)], 3)
    for x in (20, 46, 70):                     # legs: thigh up, shin down
        p.line([(x, 50), (x - 8, 62), (x - 2, 84)], 5)
        p.rect(x - 9, 84, x + 5, 89)
    p.rect(22, 38, 72, 42, cut=True)


@icon("tank")
def _(p):
    p.poly([(8, 62), (26, 46), (78, 44), (94, 56), (88, 68), (12, 70)])
    p.rrect(36, 32, 66, 46, 3)
    p.line([(64, 38), (94, 32)], 4)
    for x in (24, 44, 64):
        p.ellipse(x - 8, 66, x + 8, 74, cut=True)
    p.rect(20, 54, 82, 57, cut=True)


@icon("speeder")
def _(p):
    p.poly([(10, 56), (30, 46), (70, 46), (86, 52), (86, 60), (14, 62)])
    p.line([(70, 50), (94, 40)], 3)
    p.line([(70, 58), (94, 48)], 3)
    p.rrect(40, 36, 56, 48, 4)
    p.line([(30, 62), (26, 72)], 3)
    p.line([(64, 62), (68, 72)], 3)


@icon("transport")
def _(p):
    p.poly([(10, 54), (22, 40), (66, 38), (86, 46), (92, 56), (86, 62), (14, 64)])  # LAAT-style hull
    p.poly([(36, 38), (44, 24), (52, 24), (52, 38)])
    p.poly([(22, 46), (2, 36), (4, 44), (20, 52)])
    p.rect(40, 46, 60, 56, cut=True)
    p.rect(64, 46, 72, 52, cut=True)


@icon("fighter")
def _(p):
    p.sym([(50, 6), (44, 34), (42, 60), (8, 70), (8, 78), (42, 74), (44, 88), (50, 94)])
    p.ellipse(46, 26, 54, 40, cut=True)
    p.line([(10, 62), (10, 86)], 3)
    p.line([(90, 62), (90, 86)], 3)


@icon("bomber")
def _(p):
    p.sym([(50, 8), (45, 20), (45, 44), (12, 46), (12, 56), (45, 56), (45, 84), (50, 90)])
    for x in (20, 80):
        p.rrect(x - 6, 30, x + 6, 82, 5)
        p.rect(x - 3, 74, x + 3, 82, cut=True)
    p.ellipse(46, 18, 54, 30, cut=True)


@icon("interceptor")
def _(p):
    p.circle(50, 50, 12)
    p.ring(50, 50, 7, 2, cut=True)
    for s in (1, -1):
        p.poly([(50 + s * 10, 48), (50 + s * 30, 48), (50 + s * 30, 52), (50 + s * 10, 52)])
        p.poly([(50 + s * 30, 14), (50 + s * 44, 30), (50 + s * 44, 70), (50 + s * 30, 86), (50 + s * 36, 50)])


@icon("capital")
def _(p):
    p.sym([(50, 4), (26, 72), (22, 86), (36, 92), (44, 84), (50, 84)])
    p.line([(50, 18), (50, 70)], 3, cut=True)
    p.rect(34, 70, 44, 80)
    p.rect(56, 70, 66, 80)
    p.circle(39, 88, 3, cut=True)
    p.circle(61, 88, 3, cut=True)


@icon("stealth")
def _(p):
    p.sym([(50, 4), (26, 72), (22, 86), (36, 92), (44, 84), (50, 84)])
    p.sym([(50, 14), (32, 72), (30, 80), (36, 84), (44, 76), (50, 76)], cut=True)
    for y in (30, 46, 62):
        p.rect(44, y, 56, y + 6)


@icon("carrier")
def _(p):
    p.sym([(50, 10), (20, 70), (18, 86), (50, 80)])
    p.rect(38, 40, 62, 74, cut=True)
    for x, y in ((50, 46), (50, 62)):
        p.sym([(x, y), (x - 6, y + 10), (x, y + 8)])


@icon("station")
def _(p):
    p.rect(4, 46, 96, 54)
    for x in (4, 82):
        p.rect(x, 22, x + 14, 78)
        p.rect(x + 6, 22, x + 8, 78, cut=True)
    p.circle(50, 50, 20)
    p.rect(30, 48, 70, 52, cut=True)
    p.circle(50, 40, 5, cut=True)


@icon("dropship")
def _(p):
    p.sym([(50, 8), (34, 28), (30, 66), (40, 80), (50, 82)])
    p.rect(34, 40, 66, 46, cut=True)
    for x in (34, 50, 66):
        p.line([(x, 84), (x, 94)], 3)


# ---------------------------------------------------------------- weapons
@icon("blaster")
def _(p):
    p.poly([(6, 40), (70, 40), (78, 34), (94, 34), (94, 42), (78, 44), (72, 52), (40, 52), (34, 70), (22, 70),
            (26, 52), (16, 52), (6, 60)])
    p.rect(30, 30, 54, 36)
    p.rect(50, 42, 66, 46, cut=True)


@icon("sabers", "attack")
def _(p):
    for s in (1, -1):
        x0, x1 = 50 - s * 38, 50 + s * 30
        p.line([(x0, 88), (50 - s * 26, 76)], 9, caps=False)
        p.line([(50 - s * 26, 76), (x1, 12)], 5)
        p.line([(50 - s * 32, 70), (50 - s * 20, 82)], 4)


@icon("artillery", "turbolaser")
def _(p):
    p.poly([(14, 88), (86, 88), (76, 70), (24, 70)])
    p.ellipse(28, 50, 72, 86)
    p.rect(20, 76, 80, 90)
    p.line([(54, 62), (90, 22)], 7)
    p.line([(46, 62), (80, 16)], 4)
    p.rect(30, 80, 70, 83, cut=True)


@icon("antiair")
def _(p):
    p.poly([(16, 88), (84, 88), (72, 70), (28, 70)])
    p.circle(50, 66, 14)
    for dx in (-6, 6):
        p.line([(50 + dx, 62), (70 + dx, 14)], 4)
    p.arc(50, 66, 30, 200, 250, 3)


@icon("missile", "rocket")
def _(p):
    p.sym([(50, 6), (42, 20), (42, 70), (30, 86), (42, 84), (46, 92), (50, 92)])
    p.rect(44, 34, 56, 38, cut=True)


@icon("torpedo")
def _(p):
    p.poly([(10, 44), (70, 44), (90, 50), (70, 56), (10, 56)])
    p.poly([(10, 36), (20, 44), (20, 56), (10, 64)])
    p.rect(52, 47, 58, 53, cut=True)


@icon("bomb")
def _(p):
    p.circle(46, 58, 30)
    p.line([(64, 34), (78, 20)], 6)
    p.star(84, 14, 10, 4, 6)
    p.arc(46, 58, 20, 200, 260, 4, cut=True)


@icon("mine")
def _(p):
    p.circle(50, 50, 26)
    for i in range(8):
        a = math.radians(i * 45)
        p.line([(50 + 26 * math.cos(a), 50 + 26 * math.sin(a)), (50 + 42 * math.cos(a), 50 + 42 * math.sin(a))], 5)
    p.circle(50, 50, 9, cut=True)


@icon("superweapon", "nuke")
def _(p):
    p.circle(50, 50, 44)
    p.circle(36, 36, 13, cut=True)
    p.circle(36, 36, 4)
    p.rect(6, 52, 94, 56, cut=True)
    p.arc(50, 50, 36, 20, 70, 3, cut=True)


@icon("turret")
def _(p):
    p.ellipse(20, 40, 80, 80)
    p.rect(14, 62, 86, 80)
    p.rect(52, 46, 96, 54)
    p.rect(24, 66, 76, 69, cut=True)


@icon("cannon", "gun")
def _(p):
    p.rrect(8, 42, 60, 60, 4)
    p.rect(60, 46, 96, 56)
    p.rect(88, 42, 96, 60)
    p.rect(20, 48, 50, 52, cut=True)


# ---------------------------------------------------------------- state, economy
@icon("senate", "politics")
def _(p):
    p.ellipse(18, 18, 82, 70)
    p.rect(10, 44, 90, 92, cut=True)
    p.rect(12, 46, 88, 52)
    for x in (18, 34, 50, 66, 82):
        p.rect(x - 4, 56, x + 4, 82)
    p.rect(8, 84, 92, 92)


@icon("scales", "stability")
def _(p):
    p.rect(47, 12, 53, 84)
    p.rect(30, 84, 70, 92)
    p.rect(14, 22, 86, 28)
    for x in (24, 76):
        p.line([(x, 28), (x - 12, 58)], 2)
        p.line([(x, 28), (x + 12, 58)], 2)
        p.ellipse(x - 16, 52, x + 16, 70)
        p.rect(x - 18, 50, x + 18, 60, cut=True)


@icon("banner", "warsupport")
def _(p):
    p.rect(20, 6, 26, 94)
    p.poly([(26, 10), (84, 10), (72, 28), (84, 46), (26, 46)])
    p.circle(48, 28, 9, cut=True)


@icon("people", "manpower")
def _(p):
    for x, y, r in ((34, 30, 12), (66, 30, 12)):
        p.circle(x, y, r)
        p.ellipse(x - 22, y + 16, x + 22, y + 70)
    p.rect(0, 80, 100, 100, cut=True)
    p.line([(50, 46), (50, 80)], 3, cut=True)


@icon("person")
def _(p):
    p.circle(50, 28, 16)
    p.ellipse(20, 50, 80, 120)
    p.rect(0, 90, 100, 100, cut=True)


@icon("factory", "industry")
def _(p):
    p.poly([(8, 90), (8, 46), (28, 34), (28, 46), (48, 34), (48, 46), (68, 34), (68, 90)])
    p.rect(74, 14, 86, 90)
    p.rect(8, 84, 92, 92)
    for x in (16, 36, 56):
        p.rect(x, 60, x + 8, 72, cut=True)


@icon("shipyard", "dockyard")
def _(p):
    p.arc(50, 50, 40, 120, 420, 8)
    p.sym([(50, 22), (40, 60), (38, 72), (50, 68)])
    p.rect(14, 46, 26, 54)
    p.rect(74, 46, 86, 54)


@icon("cog", "production", "settings")
def _(p):
    p.circle(50, 50, 30)
    for i in range(8):
        a = math.radians(i * 45)
        c, s = math.cos(a), math.sin(a)
        p.poly([(50 + 26 * c - 7 * s, 50 + 26 * s + 7 * c), (50 + 44 * c - 6 * s, 50 + 44 * s + 6 * c),
                (50 + 44 * c + 6 * s, 50 + 44 * s - 6 * c), (50 + 26 * c + 7 * s, 50 + 26 * s - 7 * c)])
    p.circle(50, 50, 13, cut=True)


@icon("construction")
def _(p):
    ICONS["cog"](p)
    p.line([(20, 80), (78, 22)], 16, cut=True)
    p.line([(24, 76), (74, 26)], 7)
    p.circle(78, 22, 11)
    p.poly([(76, 12), (88, 20), (84, 24)], cut=True)


@icon("wrench", "engineer", "repair")
def _(p):
    p.line([(22, 80), (66, 36)], 10)
    p.circle(72, 28, 18)
    p.poly([(70, 10), (92, 22), (80, 36)], cut=True)
    p.circle(22, 80, 4, cut=True)


@icon("crate", "supply")
def _(p):
    p.poly([(50, 8), (90, 28), (90, 72), (50, 92), (10, 72), (10, 28)])
    p.line([(10, 28), (50, 48), (90, 28)], 4, cut=True, caps=False)
    p.line([(50, 48), (50, 92)], 4, cut=True, caps=False)
    p.line([(30, 18), (70, 38)], 4, cut=True, caps=False)


@icon("credits", "trade", "market")
def _(p):
    for y in (82, 68, 54):
        p.rrect(14, y - 6, 86, y + 6, 6)
    p.ring(50, 24, 20, 6)
    p.rect(46, 12, 54, 36)


@icon("fuel", "tibanna")
def _(p):
    p.rrect(26, 16, 74, 92, 12)
    p.rect(40, 6, 60, 16)
    p.rect(26, 34, 74, 38, cut=True)
    p.rect(26, 70, 74, 74, cut=True)
    p.reg(50, 54, 9, 6, 30, cut=True)


@icon("crystal", "resource", "kyber")
def _(p):
    p.poly([(50, 4), (74, 26), (68, 80), (50, 96), (32, 80), (26, 26)])
    p.line([(50, 4), (50, 96)], 3, cut=True)
    p.line([(26, 26), (50, 36), (74, 26)], 3, cut=True, caps=False)


@icon("holocron", "research", "science")
def _(p):
    p.reg(50, 50, 44, 6, -90)
    p.line([(50, 50), (50, 92)], 4, cut=True, caps=False)
    p.line([(50, 50), (12, 28)], 4, cut=True, caps=False)
    p.line([(50, 50), (88, 28)], 4, cut=True, caps=False)
    p.reg(50, 50, 13, 6, -90, cut=True)
    p.circle(50, 50, 6)


@icon("accord", "diplomacy")
def _(p):
    p.ring(34, 50, 30, 10)
    p.ring(66, 50, 30, 10)
    p.arc(66, 50, 25, 140, 220, 14, cut=True)
    p.arc(66, 50, 25, 145, 215, 10)


@icon("eye", "intel")
def _(p):
    p.poly([(4, 50), (26, 28), (50, 22), (74, 28), (96, 50), (74, 72), (50, 78), (26, 72)])
    p.circle(50, 50, 20, cut=True)
    p.circle(50, 50, 12)
    p.circle(45, 45, 4, cut=True)


@icon("radar", "detection")
def _(p):
    p.arc(50, 60, 40, 200, 340, 8)
    p.pieslice = None
    p.d.pieslice([10 * S, 20 * S, 90 * S, 100 * S], 200, 340, fill=255)
    p.d.pieslice([18 * S, 28 * S, 82 * S, 92 * S], 200, 340, fill=0)
    p.line([(50, 60), (78, 26)], 4)
    p.circle(50, 60, 7)
    p.rect(40, 66, 60, 92)
    p.rect(26, 88, 74, 94)


@icon("comm", "propaganda", "holoprojector")
def _(p):
    p.poly([(36, 94), (64, 94), (58, 72), (42, 72)])
    p.circle(50, 66, 8)
    for r in (18, 32, 46):
        p.arc(50, 66, r, 225, 315, 5)


@icon("planet", "state", "territory")
def _(p):
    p.circle(46, 54, 40)
    p.poly([(4, 46), (88, 34), (88, 40), (4, 52)], cut=True)
    p.poly([(4, 66), (88, 54), (88, 59), (4, 71)], cut=True)
    p.circle(88, 14, 9)


@icon("hyperspace", "speed")
def _(p):
    for i, y in enumerate((26, 50, 74)):
        p.poly([(10 + i * 4, y - 9), (54 + i * 4, y - 9), (70 + i * 4, y), (54 + i * 4, y + 9), (10 + i * 4, y + 9),
                (26 + i * 4, y)])


@icon("chevrons")
def _(p):
    for x in (10, 38, 66):
        p.poly([(x, 14), (x + 14, 14), (x + 32, 50), (x + 14, 86), (x, 86), (x + 18, 50)])


@icon("shield", "defense", "garrison", "fort")
def _(p):
    p.poly([(14, 10), (86, 10), (86, 52), (50, 92), (14, 52)])
    p.poly([(24, 20), (76, 20), (76, 48), (50, 78), (24, 48)], cut=True)
    p.poly([(32, 28), (68, 28), (68, 46), (50, 66), (32, 46)])


@icon("medic", "medical")
def _(p):
    p.ring(50, 50, 44, 7)
    p.rect(40, 22, 60, 78)
    p.rect(22, 40, 78, 60)


@icon("skull", "casualties", "death")
def _(p):
    p.ellipse(16, 8, 84, 72)
    p.rrect(30, 58, 70, 90, 4)
    p.ellipse(28, 34, 46, 52, cut=True)
    p.ellipse(54, 34, 72, 52, cut=True)
    p.poly([(50, 54), (44, 64), (56, 64)], cut=True)
    for x in (40, 50, 60):
        p.rect(x - 1.5, 76, x + 1.5, 90, cut=True)


@icon("star", "elite", "unique")
def _(p):
    p.star(50, 52, 46, 19, 5)


@icon("rank", "officer", "career", "trait")
def _(p):
    p.rrect(10, 30, 90, 70, 6)
    for i, x in enumerate((20, 40, 60)):
        p.rect(x, 40, x + 14, 60, cut=True)
        if i < 2:
            p.rect(x + 3, 43, x + 11, 57)


@icon("map", "doctrine", "plan", "holotable")
def _(p):
    p.poly([(10, 30), (36, 20), (64, 30), (90, 20), (90, 74), (64, 84), (36, 74), (10, 84)])
    p.line([(36, 20), (36, 74)], 3, cut=True, caps=False)
    p.line([(64, 30), (64, 84)], 3, cut=True, caps=False)
    p.circle(50, 48, 7, cut=True)


@icon("engine", "thruster")
def _(p):
    p.poly([(14, 30), (58, 30), (86, 16), (86, 84), (58, 70), (14, 70)])
    for y in (40, 50, 60):
        p.rect(20, y - 2, 52, y + 2, cut=True)
    p.ellipse(70, 34, 82, 66, cut=True)


@icon("legs", "suspension")
def _(p):
    p.rrect(20, 8, 80, 30, 4)
    for x in (32, 68):
        p.line([(x, 28), (x - 12, 56), (x, 86)], 8)
        p.rect(x - 12, 84, x + 12, 92)


@icon("armor", "plating")
def _(p):
    p.poly([(10, 20), (60, 10), (90, 30), (90, 80), (40, 90), (10, 70)])
    p.line([(10, 45), (90, 55)], 3, cut=True, caps=False)
    p.line([(50, 14), (50, 88)], 3, cut=True, caps=False)
    for x, y in ((24, 30), (70, 34), (24, 74), (70, 72)):
        p.circle(x, y, 3, cut=True)


@icon("binoculars", "recon", "scout")
def _(p):
    for x in (28, 72):
        p.rrect(x - 18, 26, x + 18, 84, 8)
        p.circle(x, 70, 9, cut=True)
    p.rect(40, 36, 60, 56)


@icon("parachute", "airborne")
def _(p):
    p.d.pieslice([10 * S, 10 * S, 90 * S, 80 * S], 180, 360, fill=255)
    for x in (20, 50, 80):
        p.line([(x, 45), (50, 80)], 2)
    p.rect(42, 78, 58, 94)


@icon("mountain")
def _(p):
    p.poly([(4, 88), (36, 28), (52, 52), (66, 34), (96, 88)])
    p.poly([(36, 28), (44, 44), (36, 40), (28, 44)], cut=True)


@icon("clock", "time")
def _(p):
    p.ring(50, 50, 44, 7)
    p.line([(50, 50), (50, 22)], 6)
    p.line([(50, 50), (70, 62)], 6)


@icon("hourglass")
def _(p):
    p.rect(20, 8, 80, 16)
    p.rect(20, 84, 80, 92)
    p.poly([(26, 16), (74, 16), (54, 50), (74, 84), (26, 84), (46, 50)])
    p.poly([(34, 22), (66, 22), (50, 44)], cut=True)


@icon("lock")
def _(p):
    p.rrect(18, 44, 82, 92, 6)
    p.arc(50, 44, 24, 180, 360, 8)
    p.rect(26, 40, 34, 46)
    p.rect(66, 40, 74, 46)
    p.circle(50, 64, 7, cut=True)
    p.rect(47, 64, 53, 80, cut=True)


@icon("unlock")
def _(p):
    p.rrect(18, 44, 82, 92, 6)
    p.arc(64, 34, 22, 180, 360, 8)
    p.circle(50, 64, 7, cut=True)
    p.rect(47, 64, 53, 80, cut=True)


@icon("search", "magnifier", "filter")
def _(p):
    p.ring(42, 42, 30, 9)
    p.line([(64, 64), (88, 88)], 12)


@icon("trash", "delete")
def _(p):
    p.rect(14, 18, 86, 26)
    p.rect(38, 8, 62, 18)
    p.poly([(20, 30), (80, 30), (74, 92), (26, 92)])
    for x in (38, 50, 62):
        p.rect(x - 2, 40, x + 2, 82, cut=True)


@icon("copy")
def _(p):
    p.rrect(10, 10, 62, 62, 4)
    p.rrect(18, 18, 54, 54, 2, cut=True)
    p.rrect(38, 38, 90, 90, 4)


@icon("merge")
def _(p):
    p.poly([(4, 30), (36, 30), (50, 44), (36, 58), (4, 58), (18, 44)])
    p.poly([(96, 30), (64, 30), (50, 44), (64, 58), (96, 58), (82, 44)])
    p.rect(44, 66, 56, 92)


@icon("split")
def _(p):
    p.poly([(46, 30), (16, 30), (2, 44), (16, 58), (46, 58), (32, 44)])
    p.poly([(54, 30), (84, 30), (98, 44), (84, 58), (54, 58), (68, 44)])


@icon("refresh", "reorganize", "convert")
def _(p):
    p.arc(50, 50, 38, 200, 340, 9)
    p.arc(50, 50, 38, 20, 160, 9)
    p.poly([(82, 22), (92, 46), (68, 42)])
    p.poly([(18, 78), (8, 54), (32, 58)])


@icon("list", "ledger")
def _(p):
    for y in (20, 44, 68):
        p.rect(8, y, 20, y + 12)
        p.rect(28, y, 92, y + 12)


@icon("home", "base", "capital_icon")
def _(p):
    p.poly([(50, 8), (94, 46), (82, 46), (82, 92), (18, 92), (18, 46), (6, 46)])
    p.rect(40, 62, 60, 92, cut=True)


@icon("plus", "add")
def _(p):
    p.rect(40, 8, 60, 92)
    p.rect(8, 40, 92, 60)


@icon("minus", "subtract")
def _(p):
    p.rect(8, 40, 92, 60)


@icon("x", "close", "cancel")
def _(p):
    p.line([(16, 16), (84, 84)], 16)
    p.line([(84, 16), (16, 84)], 16)


@icon("tick", "check", "accept", "ready")
def _(p):
    p.line([(10, 52), (38, 80), (90, 20)], 15)


@icon("question", "unknown")
def _(p):
    p.arc(50, 32, 24, 180, 405, 12)
    p.line([(56, 52), (50, 64)], 12, caps=False)
    p.circle(50, 86, 8)


@icon("exclaim", "alert", "warning")
def _(p):
    p.poly([(40, 6), (60, 6), (56, 68), (44, 68)])
    p.circle(50, 86, 9)


@icon("arrow_r", "right", "next_arrow")
def _(p):
    p.poly([(8, 38), (52, 38), (52, 16), (94, 50), (52, 84), (52, 62), (8, 62)])


@icon("arrow_l", "left")
def _(p):
    p.poly([(92, 38), (48, 38), (48, 16), (6, 50), (48, 84), (48, 62), (92, 62)])


@icon("arrow_u", "up")
def _(p):
    p.poly([(38, 92), (38, 48), (16, 48), (50, 6), (84, 48), (62, 48), (62, 92)])


@icon("arrow_d", "down")
def _(p):
    p.poly([(38, 8), (38, 52), (16, 52), (50, 94), (84, 52), (62, 52), (62, 8)])


@icon("play")
def _(p):
    p.poly([(22, 10), (88, 50), (22, 90)])


@icon("pause")
def _(p):
    p.rect(20, 12, 40, 88)
    p.rect(60, 12, 80, 88)


@icon("stop")
def _(p):
    p.rect(16, 16, 84, 84)


@icon("next")
def _(p):
    p.poly([(12, 12), (64, 50), (12, 88)])
    p.rect(70, 12, 86, 88)


@icon("prev")
def _(p):
    p.poly([(88, 12), (36, 50), (88, 88)])
    p.rect(14, 12, 30, 88)


@icon("flag")
def _(p):
    p.rect(14, 6, 20, 94)
    p.poly([(20, 10), (88, 10), (88, 52), (20, 52)])
    p.line([(20, 24), (88, 24)], 3, cut=True, caps=False)


@icon("chart", "efficiency", "growth")
def _(p):
    for i, x in enumerate((12, 34, 56, 78)):
        p.rect(x, 80 - i * 18, x + 14, 92)
    p.line([(10, 54), (34, 36), (56, 44), (88, 10)], 5)


@icon("heart", "strength", "morale")
def _(p):
    p.circle(32, 36, 22)
    p.circle(68, 36, 22)
    p.poly([(12, 44), (88, 44), (50, 90)])


@icon("lightning", "power", "energy")
def _(p):
    p.poly([(60, 4), (20, 56), (46, 56), (36, 96), (82, 40), (54, 40), (66, 4)])


@icon("moon", "night")
def _(p):
    p.circle(50, 50, 40)
    p.circle(66, 40, 32, cut=True)


@icon("target", "strike", "accuracy")
def _(p):
    p.ring(50, 50, 40, 6)
    p.ring(50, 50, 20, 6)
    for a, b in (((50, 2), (50, 26)), ((50, 74), (50, 98)), ((2, 50), (26, 50)), ((74, 50), (98, 50))):
        p.line([a, b], 5, caps=False)


@icon("crown", "monarch", "leader")
def _(p):
    p.poly([(10, 80), (10, 30), (30, 54), (50, 20), (70, 54), (90, 30), (90, 80)])
    p.rect(10, 84, 90, 92)
    p.circle(50, 64, 7, cut=True)


@icon("handcuffs", "captured", "prison")
def _(p):
    p.ring(30, 62, 22, 8)
    p.ring(70, 62, 22, 8)
    p.line([(38, 36), (50, 24), (62, 36)], 5)


@icon("drop", "raid", "invasion")
def _(p):
    p.poly([(50, 96), (24, 60), (36, 60), (36, 8), (64, 8), (64, 60), (76, 60)])
    p.rect(44, 16, 56, 50, cut=True)


@icon("fist", "resistance", "revolt")
def _(p):
    p.rrect(22, 30, 78, 72, 8)
    for x in (22, 36, 50, 64):
        p.rrect(x, 18, x + 14, 40, 6)
        p.line([(x + 14, 26), (x + 14, 44)], 2, cut=True, caps=False)
    p.rect(30, 70, 70, 94)
    p.rrect(10, 40, 30, 62, 6)


@icon("building", "buildings", "infrastructure")
def _(p):
    p.rect(14, 30, 46, 92)
    p.rect(52, 10, 86, 92)
    for x in (20, 32):
        for y in (40, 56, 72):
            p.rect(x, y, x + 8, y + 8, cut=True)
    for x in (58, 72):
        for y in (20, 36, 52, 68):
            p.rect(x, y, x + 8, y + 8, cut=True)


# ---------------------------------------------------------------- detailed set (>= DETAIL_MIN px)
# Same subjects, drawn like the toolbar icons: a main shape with panel-line cut-outs and a secondary element set off
# by a dark gap (Pen.over / Pen.stamp). Registered under every alias of the simple icon.
DETAIL = {}


def detail(name):
    def reg(fn):
        for n, f in list(ICONS.items()):
            if f is ICONS[name]:
                DETAIL[n] = fn
        return fn
    return reg


def _saber(q, x0, y0, x1, y1):
    L = math.hypot(x1 - x0, y1 - y0); dx, dy = (x1 - x0) / L, (y1 - y0) / L; nx, ny = -dy, dx
    P = lambda t, o=0: (x0 + dx * t + nx * o, y0 + dy * t + ny * o)
    q.poly([P(-3, -3.5), P(-3, 3.5), P(0, 3.5), P(0, -3.5)])                    # pommel
    q.poly([P(0, -4.5), P(0, 4.5), P(22, 4.5), P(22, -4.5)])                    # grip
    q.poly([P(21, -6.5), P(21, 6.5), P(28, 5), P(28, -5)])                       # emitter shroud
    for t in (5, 9, 13, 17):
        q.line([P(t, -4.6), P(t, 4.6)], 1.4, cut=True, caps=False)              # grip ridges
    q.line([P(31, 0), P(L, 0)], 6.5)                                             # blade
    q.line([P(35, 0), P(L - 4, 0)], 1.6, cut=True)                               # glowing core


@detail("sabers")
def _(p):
    _saber(p, 14, 88, 86, 12)
    p.over(lambda q: _saber(q, 86, 88, 14, 12), 2.5)


@detail("republic")
def _(p):
    p.ring(50, 50, 47, 6)
    for i in range(16):
        a = i * 22.5 + 11.25
        p.line([p.at(50, 50, 48, a), p.at(50, 50, 41.5, a)], 1.6, cut=True, caps=False)
    p.ring(50, 50, 38, 2)
    for i in range(8):
        a = i * 45 - 90
        p.poly([p.at(50, 50, 15, a - 20), p.at(50, 50, 33, a - 9), p.at(50, 50, 33, a + 9), p.at(50, 50, 15, a + 20)])
        p.line([p.at(50, 50, 19, a), p.at(50, 50, 30, a)], 1.5, cut=True, caps=False)
    p.ring(50, 50, 12, 4)
    p.circle(50, 50, 4)


@detail("capital")
def _(p):
    p.poly([(50, 4), (82, 84), (72, 90), (28, 90), (18, 84)])
    p.rect(30, 86, 70, 96)
    for x in (37, 50, 63):
        p.circle(x, 91, 3.2, cut=True)                                           # engine bells
    p.line([(50, 12), (50, 84)], 2.2, cut=True, caps=False)                     # dorsal trench
    for s in (1, -1):
        p.line([(50 - s * 3, 26), (50 - s * 18, 80)], 1.3, cut=True, caps=False)
    p.line([(30, 64), (70, 64)], 1.3, cut=True, caps=False)

    def towers(q):
        for x in (31, 57):
            q.rrect(x, 60, x + 12, 80, 2)
            q.rect(x + 2, 64, x + 10, 66, cut=True)
    p.over(towers, 2.2)


@detail("rank")
def _(p):
    p.rect(26, 20, 34, 30); p.rect(66, 20, 74, 30)                               # clips
    p.rrect(8, 26, 92, 76, 4)
    p.rrect(13, 31, 87, 71, 2, cut=True)
    for i, x in enumerate((19, 35, 51, 67)):
        p.rect(x, 37, x + 13, 50)
        if i % 2:
            p.rect(x + 3, 40, x + 10, 47, cut=True)
    for i, x in enumerate((27, 43, 59)):
        p.rect(x, 55, x + 13, 66)
        if i == 1:
            p.rect(x + 3, 58, x + 10, 63, cut=True)


@detail("eye")
def _(p):
    up = [(8 + 84 * t / 20, 50 - 30 * math.sin(math.pi * t / 20)) for t in range(21)]
    p.poly(up + [(x, 100 - y) for x, y in reversed(up)])
    up2 = [(14 + 72 * t / 20, 50 - 23 * math.sin(math.pi * t / 20)) for t in range(21)]
    p.poly(up2 + [(x, 100 - y) for x, y in reversed(up2)], cut=True)
    p.circle(50, 50, 19)
    p.ring(50, 50, 14, 2, cut=True)
    p.circle(50, 50, 7, cut=True)
    p.circle(46, 46, 2.6)
    for (x, y, sx, sy) in ((4, 8, 1, 1), (96, 8, -1, 1), (4, 92, 1, -1), (96, 92, -1, -1)):
        p.line([(x, y + sy * 14), (x, y), (x + sx * 14, y)], 3, caps=False)    # targeting brackets


@detail("accord")
def _(p):
    p.rect(18, 14, 74, 86)
    p.rrect(10, 7, 82, 20, 6.5); p.rrect(10, 80, 82, 93, 6.5)
    p.line([(15, 13.5), (77, 13.5)], 1.4, cut=True, caps=False)
    p.line([(15, 86.5), (77, 86.5)], 1.4, cut=True, caps=False)
    for y, x1 in ((31, 66), (40, 66), (49, 60), (58, 44)):
        p.line([(26, y), (x1, y)], 2.8, cut=True)

    def seal(q):
        q.poly([(62, 78), (56, 99), (64, 94), (70, 84)]); q.poly([(82, 78), (88, 99), (80, 94), (74, 84)])
        q.circle(72, 70, 16)
        q.star(72, 70, 10, 4.2, 5, cut=True)
        q.ring(72, 70, 13, 1.4, cut=True)
    p.over(seal, 3)


def _ring(q, half):
    out, inn = [], []
    r = math.radians(-18)
    for i in range(0, 181 if half else 361, 6):
        t = math.radians(i)
        for lst, a, b in ((out, 50, 13), (inn, 40, 6.5)):
            x, y = a * math.cos(t), b * math.sin(t)
            lst.append((46 + x * math.cos(r) - y * math.sin(r), 54 + x * math.sin(r) + y * math.cos(r)))
    if half:
        q.poly(out + inn[::-1])
    else:
        q.poly(out); q.poly(inn, cut=True)


@detail("planet")
def _(p):
    _ring(p, False)

    def globe(q):
        q.circle(46, 54, 31)
        q.arc(30, 112, 62, 245, 300, 2.6, cut=True)
        q.arc(70, 4, 50, 95, 150, 2.4, cut=True)
        q.circle(36, 46, 4, cut=True)
    p.over(globe, 2.4)
    p.over(lambda q: _ring(q, True), 2.4)

    def moon(q):
        q.circle(85, 15, 9); q.circle(88, 13, 2.5, cut=True); q.circle(82, 19, 1.8, cut=True)
    p.over(moon, 3)


@detail("map")
def _(p):
    p.poly([(6, 22), (34, 12), (34, 80), (6, 90)])
    p.poly([(37, 12), (63, 22), (63, 90), (37, 80)])
    p.poly([(66, 22), (94, 12), (94, 80), (66, 90)])
    route = [(12, 74), (24, 58), (40, 64), (52, 50), (62, 54)]
    for a, b in zip(route, route[1:]):
        for k in (0.15, 0.6):
            p.line([(a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k),
                    (a[0] + (b[0] - a[0]) * (k + 0.28), a[1] + (b[1] - a[1]) * (k + 0.28))], 2.4, cut=True)
    p.line([(9, 28), (18, 37)], 2, cut=True); p.line([(18, 28), (9, 37)], 2, cut=True)        # start X

    def pin(q):
        q.circle(76, 34, 14)
        q.poly([(64, 41), (88, 41), (76, 62)])
        q.circle(76, 34, 5.5, cut=True)
    p.over(pin, 3)


@detail("fighter")
def _(p):
    p.sym([(50, 4), (45, 14), (43, 58), (41, 88), (50, 94)])
    for s in (1, -1):
        X = lambda x: 50 + s * (x - 50)
        p.poly([(X(44), 38), (X(8), 50), (X(8), 64), (X(44), 62)])
        p.rect(min(X(3), X(10)), 30, max(X(3), X(10)), 68)                       # wingtip cannons
        p.line([(X(12), 57), (X(40), 57)], 1.6, cut=True, caps=False)          # S-foil split
        p.rrect(min(X(30), X(39)), 60, max(X(30), X(39)), 90, 3)                 # engine pods
        p.circle(X(34.5), 86, 2.4, cut=True)
    p.ellipse(46, 16, 54, 34, cut=True)
    p.line([(50, 40), (50, 86)], 1.6, cut=True, caps=False)


@detail("trooper")
def _(p):
    p.circle(50, 40, 30); p.rect(20, 40, 80, 70)
    p.poly([(20, 70), (80, 70), (72, 92), (28, 92)])
    p.arc(50, 44, 29, 200, 340, 1.6, cut=True)                                  # brow ridge
    p.line([(50, 11), (50, 26)], 2, cut=True, caps=False)                       # crest
    p.poly([(24, 36), (76, 36), (76, 47), (56, 47), (56, 74), (44, 74), (44, 47), (24, 47)], cut=True)   # T-visor
    for s in (1, -1):
        for i in range(3):
            p.line([(50 - s * 22, 60 + i * 6), (50 - s * 13, 58 + i * 6)], 1.5, cut=True, caps=False)  # cheek vents
    p.rect(42, 79, 58, 87, cut=True)
    for x in (46, 50, 54):
        p.rect(x - 0.7, 79, x + 0.7, 87)

    def ears(q):
        for x in (17, 83):
            q.circle(x, 54, 7); q.circle(x, 54, 2.6, cut=True)
    p.over(ears, 2)


@detail("shield")
def _(p):
    p.sym([(50, 4), (10, 15), (10, 48), (19, 71), (50, 96)])
    p.sym([(50, 11), (16, 20), (16, 47), (24, 67), (50, 88)], cut=True)
    p.sym([(50, 17), (22, 25), (22, 46), (29, 63), (50, 81)])
    p.circle(50, 46, 15, cut=True)
    p.circle(50, 46, 5.5)
    for i in range(6):
        a = i * 60 - 90
        p.line([p.at(50, 46, 5, a), p.at(50, 46, 13, a)], 3, caps=False)
    for y in (66, 72):
        p.line([(42, y), (58, y)], 1.6, cut=True)


@detail("holocron")
def _(p):
    p.poly([(50, 6), (90, 27), (50, 48), (10, 27)])
    p.poly([(9, 32), (47, 52), (47, 95), (9, 74)])
    p.poly([(53, 52), (91, 32), (91, 74), (53, 95)])
    p.poly([(50, 17), (70, 27), (50, 37), (30, 27)], cut=True)
    p.poly([(50, 22), (60, 27), (50, 32), (40, 27)])
    for s in (1, -1):
        X = lambda x: 50 + s * (x - 50)
        p.line([(X(15), 48), (X(26), 54), (X(26), 70), (X(36), 76)], 2, cut=True)
        p.circle(X(38), 77, 3, cut=True)
        p.line([(X(15), 62), (X(20), 65)], 2, cut=True)


@detail("senate")
def _(p):
    p.circle(50, 48, 27)
    p.rect(16, 48, 84, 100, cut=True)
    for x0 in (36, 43, 57, 64):
        p.line([(50, 25), (x0, 47)], 1.4, cut=True, caps=False)                   # dome ribs
    p.rect(48, 10, 52, 22); p.circle(50, 9, 3)
    p.rect(14, 49, 86, 57)
    p.line([(16, 53), (84, 53)], 1.2, cut=True, caps=False)
    for x in range(20, 80, 10):
        p.rect(x, 60, x + 6, 80)
    p.rect(10, 82, 90, 87); p.rect(5, 89, 95, 94)


@detail("credits")
def _(p):
    for y in (80, 69, 58):
        p.rrect(6, y, 58, y + 10, 5)
        for x in range(14, 54, 6):
            p.line([(x, y + 2.5), (x, y + 7.5)], 1.2, cut=True, caps=False)

    def coin(q):
        q.circle(68, 38, 27)
        q.ring(68, 38, 21, 2, cut=True)
        q.circle(68, 38, 9, cut=True)
        q.circle(68, 38, 3.5)
        for i in range(6):
            a = i * 60 - 90
            q.line([q.at(68, 38, 3, a), q.at(68, 38, 8, a)], 2.2, caps=False)
    p.over(coin, 3)


@detail("search")
def _(p):
    p.ring(40, 40, 32, 7)
    p.line([(63, 63), (90, 90)], 12)
    p.line([(66, 66), (86, 86)], 2, cut=True, caps=False)
    p.arc(40, 40, 22, 200, 260, 3)                                              # lens glint
    p.circle(40, 40, 9)
    p.circle(40, 40, 4, cut=True)


@detail("chart")
def _(p):
    for x, h in ((10, 22), (30, 38), (50, 30), (70, 56)):
        p.rect(x, 92 - h, x + 15, 92)
        p.line([(x + 3, 92 - h + 4), (x + 12, 92 - h + 4)], 1.4, cut=True, caps=False)
    p.rect(4, 94, 96, 98)

    def trend(q):
        q.line([(10, 54), (34, 34), (52, 44), (80, 14)], 5)
        q.poly([(70, 8), (90, 4), (86, 24)])
    p.over(trend, 2.5)


@detail("drop")
def _(p):
    p.circle(50, 112, 52)                                                       # planet horizon
    p.arc(50, 112, 44, 225, 315, 2.4, cut=True)
    p.rect(0, 96, 100, 100, cut=True)

    def arrow(q):
        q.rect(41, 2, 59, 36); q.poly([(24, 34), (76, 34), (50, 64)])
        q.line([(50, 8), (50, 34)], 2.2, cut=True, caps=False)
        for s in (1, -1):
            q.line([(50 - s * 30, 10), (50 - s * 30, 26)], 3)                    # speed streaks
    p.over(arrow, 3)


# simple silhouette + a secondary pictogram badge, layered with a gap
_BADGES = {"factory": ("cog", 76, 76, 38), "bomber": ("bomb", 80, 80, 30), "carrier": ("fighter", 78, 76, 34),
           "transport": ("trooper", 80, 22, 30), "comm": ("planet", 80, 80, 32), "wrench": ("cog", 26, 76, 36),
           "engine": ("lightning", 80, 20, 30), "crate": ("arrow_d", 82, 18, 26), "parachute": ("trooper", 50, 82, 30),
           "crown": ("star", 50, 20, 24), "walker": ("trooper", 18, 18, 28), "binoculars": ("eye", 80, 82, 32),
           "target": ("arrow_r", 20, 80, 28), "people": ("republic", 80, 80, 30), "radar": ("eye", 22, 78, 30),
           "superweapon": ("lightning", 80, 80, 30), "crystal": ("sabers", 78, 78, 34),
           "artillery": ("target", 18, 20, 28), "armor": ("shield", 80, 80, 30), "fist": ("lightning", 82, 18, 26)}


def _badged(base, badge):
    def fn(p):
        ICONS[base](p)
        p.stamp(*badge)
    return fn


for _b, _v in _BADGES.items():
    detail(_b)(_badged(_b, _v))


DETAIL_MIN = 28     # px: below this the simple silhouette reads better than the detailed one


def render(name, w, h, pad=0.0, simple=False):
    """-> 'L' coverage image of w x h with the pictogram fitted (aspect kept) and centred."""
    p = Pen()
    fn = None if simple or min(w, h) * (1 - pad) < DETAIL_MIN else DETAIL.get(name)   # drawn size decides
    (fn or ICONS[name])(p)
    im = p.im
    bb = im.getbbox()
    out = Image.new("L", (w, h), 0)
    if not bb or w < 2 or h < 2:
        return out
    im = im.crop(bb)
    tw, th = max(1, int(w * (1 - pad))), max(1, int(h * (1 - pad)))
    k = min(tw / im.width, th / im.height)
    nw, nh = max(1, round(im.width * k)), max(1, round(im.height * k))
    small = im.resize((nw, nh), Image.LANCZOS, reducing_gap=3.0)
    out.paste(small, ((w - nw) // 2, (h - nh) // 2))
    return out


def sheet(out, cell=96):
    names = list(ICONS)
    seen, uniq = set(), []
    for n in names:
        if ICONS[n] not in seen:
            seen.add(ICONS[n]); uniq.append(n)
    cols = 10
    im = Image.new("RGB", (cols * cell, ((len(uniq) + cols - 1) // cols) * (cell + 14)), (0, 16, 16))
    d = ImageDraw.Draw(im)
    for i, n in enumerate(uniq):
        x, y = (i % cols) * cell, (i // cols) * (cell + 14)
        m = render(n, cell - 24, cell - 24)
        im.paste((0, 176, 240), (x + 12, y + 16), m)
        small = render(n, 24, 24)
        im.paste((240, 192, 32), (x + cell - 26, y + 16), small)
        d.text((x + 4, y + 2), n, fill=(150, 170, 170))
    im.save(out)


FLAGS = {"CIS": ((22, 24, 92), (235, 238, 245), "cis"),      # navy field, white Separatist roundel
         "IBC": ((236, 232, 222), (214, 172, 70), "ibc")}    # ivory field, gold Banking Clan star


def flags(mod):
    """Our own vector faction flags at HOI4's three sizes (large 82x52, medium 41x26, small 10x7)."""
    import os
    for tag, (field, ink, emblem) in FLAGS.items():
        for sub, (w, h) in (("", (82, 52)), ("medium/", (41, 26)), ("small/", (10, 7))):
            im = Image.new("RGBA", (w, h), field + (255,))
            e = max(3, int(h * 0.78))
            im.paste(ink, ((w - e) // 2, (h - e) // 2), render(emblem, e, e))
            dst = os.path.join(mod, "gfx", "flags", sub + tag + ".tga")
            im.save(dst)
            print("wrote", dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet"); ap.add_argument("--flags", action="store_true")
    a = ap.parse_args()
    if a.sheet:
        sheet(a.sheet)
    if a.flags:
        import os
        flags(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
