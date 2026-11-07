"""Law series icons (conscription, trade): each law its own composition of canon pictograms, and the ring colour
climbs green -> red with how hard the law pushes, so a series reads at a glance in the law picker.
  python -B law_icons.py            preview -> law_review.png (vanilla next to new)
  python -B law_icons.py --install  writes gfx/interface/ideas/idea_<law>.dds (hod_icons skips these: LAWS)"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D); sys.path.insert(0, os.path.join(D, '..'))
from cwic_library import coverage
from logo_icons import mask_of
import hod_ui

MOD = os.path.join(D, '..', '..')
VANILLA = hod_ui.VANILLA
RAMP = [(85, 215, 105), (40, 225, 180), (0, 176, 240), (240, 210, 60), (255, 145, 35), (240, 75, 60)]
SILVER = (215, 225, 240)
CRIMSON = (215, 35, 70)       # past red: total mobilisation

# glyph = list of (subject or logo:STEM, cx, cy, size) in units of the inner box (0..1); '-slash' / '-lock' /
# '-arrow' / '-bar' are drawn marks
LAWS = {
    # mobilization_laws (no_conscription keeps the mod's own art)
    'disarmed_nation': (SILVER, [('blaster', .5, .5, 1.15), ('-slash',)]),
    'volunteer_only': (RAMP[0], [('trooper', .5, .5, 1.15)]),
    'limited_conscription': (RAMP[1], [('trooper', .3, .5, 1.05), ('trooper', .7, .5, 1.05)]),
    'extensive_conscription': (RAMP[2], [('trooper', .18, .55, .9), ('trooper', .82, .55, .9), ('trooper', .5, .48, 1.0)]),
    'service_by_requirement': (RAMP[3], [('trooper', x, .3, .66) for x in (.12, .37, .63, .88)] +
                               [('trooper', x, .72, .7) for x in (.25, .5, .75)]),
    'all_adults_serve': (RAMP[4], [('trooper', x, .22, .5) for x in (.1, .3, .5, .7, .9)] +
                         [('trooper', x, .52, .52) for x in (.2, .4, .6, .8)] +
                         [('trooper', x, .84, .54) for x in (.1, .3, .5, .7, .9)]),
    'scraping_the_barrel': (RAMP[5], [('logo:Clone_cadet', .5, .5, 1.1)]),
    # trade laws
    'generic_free_trade': (RAMP[0], [('transport', .5, .42, .9), ('credits', .78, .8, .42)]),
    'generic_export_focus': (RAMP[2], [('crate', .38, .58, .72), ('-arrow',)]),
    'generic_limited_exports': (RAMP[3], [('crate', .5, .58, .72), ('-bar',)]),
    'generic_closed_economy': (RAMP[5], [('crate', .36, .45, .7), ('-lock',)]),
    # economy laws: from a sealed-off world to everything on the war machine
    'undisturbed_isolation': (RAMP[0], [('planet', .5, .5, 1.1)]),
    'isolation': (RAMP[1], [('shield', .5, .5, .95), ('crate', .5, .66, .34)]),
    'civilian_economy': (RAMP[2], [('credits', .5, .5, 1.05)]),
    'low_economic_mobilisation': (RAMP[3], [('factory', .5, .5, 1.1)]),
    'partial_economic_mobilisation': (RAMP[4], [('blaster', .32, .5, .95), ('walker', .7, .62, .62)]),
    'war_economy': (RAMP[5], [('walker', .34, .62, .72), ('capital', .66, .3, .7)]),
    'tot_economic_mobilisation': (CRIMSON, [('superweapon', .5, .5, 1.05)]),
}


def mark(kind, n):
    """Drawn overlay marks on an n x n inner box, 8x supersampled: (add coverage, cut coverage)."""
    S = n * 8
    add, cut = Image.new('L', (S, S), 0), Image.new('L', (S, S), 0)
    a, c = ImageDraw.Draw(add), ImageDraw.Draw(cut)
    w = S // 9
    if kind == '-slash':                               # "no": slash across, with a dark gap so it reads over the glyph
        c.line([(S * .05, S * .05), (S * .95, S * .95)], fill=255, width=int(w * 2.2))   # across the rifle, not along it
        a.line([(S * .08, S * .08), (S * .92, S * .92)], fill=255, width=w)
    elif kind == '-arrow':                             # outbound arrow, upper right
        pts = [(.55, .42), (.75, .42), (.75, .3), (1., .5), (.75, .7), (.75, .58), (.55, .58)]
        c.polygon([((x - .03) * S, (y - .32) * S) for x, y in pts], fill=255)
        a.polygon([(x * S, (y - .3) * S) for x, y in pts], fill=255)
    elif kind == '-bar':                               # barrier gate across the top: half-closed
        c.rectangle([0, S * .1, S, S * .3], fill=255)
        a.rectangle([0, S * .14, S, S * .26], fill=255)
        for x in (.08, .28, .48, .68, .88):
            c.rectangle([S * (x - .02), S * .14, S * (x + .06), S * .26], fill=255)
    elif kind == '-lock':                              # padlock, lower right
        c.rounded_rectangle([S * .4, S * .4, S * 1.05, S * 1.05], S * .08, fill=255)
        a.rounded_rectangle([S * .46, S * .58, S * .99, S * 1.0], S * .06, fill=255)
        a.arc([S * .54, S * .3, S * .91, S * .76], 180, 360, fill=255, width=w)
        a.line([(S * .54, S * .53), (S * .54, S * .6)], fill=255, width=w); a.line([(S * .91 - w, S * .53), (S * .91 - w, S * .6)], fill=255, width=w)
        cut2 = ImageDraw.Draw(add)
        cut2.ellipse([S * .67, S * .68, S * .78, S * .79], fill=0)
        cut2.rectangle([S * .705, S * .74, S * .745, S * .9], fill=0)
    return [np.array(im.resize((n, n), Image.LANCZOS)) / 255.0 for im in (add, cut)]


def glyph(parts, n):
    cov = np.zeros((n, n))
    for p in parts:
        if p[0].startswith('-'):
            add, cut = mark(p[0], n)
            cov = np.maximum(cov * (1 - cut), add)
            continue
        name, cx, cy, s = p
        k = max(4, round(n * s))
        m = (mask_of(name[5:], ('lum', 160), size=(k, k), pad=0) if name.startswith('logo:') else coverage(name, k, k))
        g = np.array(m) / 255.0
        x0, y0 = round(cx * n - k / 2), round(cy * n - k / 2)
        sx, sy = slice(max(0, x0), min(n, x0 + k)), slice(max(0, y0), min(n, y0 + k))
        piece = g[sy.start - y0:sy.stop - y0, sx.start - x0:sx.stop - x0]
        # each figure gets a dark rim so overlapping troopers stay separate
        from scipy import ndimage
        rim = ndimage.grey_dilation(piece, size=3)
        cov[sy, sx] = np.maximum(cov[sy, sx] * (1 - rim), piece)
    return cov


def badge(px, col, parts):
    """Same badge as hod_icons: navy disc, coloured ring, glyph inside."""
    h, w = px.shape[:2]
    m = px[..., 3] > 127
    ys, xs = np.where(m)
    r = (np.ptp(xs) + 1) / 2
    cx, cy = (xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2
    out = np.zeros((h, w, 4), float)
    yy, xx = np.mgrid[:h, :w]
    disc = (yy + .5 - cy) ** 2 + (xx + .5 - cx) ** 2 <= (r - 1) ** 2
    out[disc, :3] = hod_ui.PLATE; out[disc, 3] = 245
    ring = Image.new('L', (w * 8, h * 8), 0)
    ImageDraw.Draw(ring).ellipse([(cx - r) * 8 + 2, (cy - r) * 8 + 2, (cx + r) * 8 - 2, (cy + r) * 8 - 2], outline=255,
                                 width=max(8, int(r * 0.9)))
    cov = np.array(ring.resize((w, h), Image.LANCZOS)) / 255.0
    n = int(r * 1.3)
    g = np.zeros((h, w)); x0, y0 = int(cx - n / 2), int(cy - n / 2)
    g[y0:y0 + n, x0:x0 + n] = glyph(parts, n)
    for c, a in ((col, cov), (col, g)):
        out[..., :3] = out[..., :3] * (1 - a[..., None]) + np.array(c) * a[..., None]
        out[..., 3] = np.maximum(out[..., 3], a * 255)
    return np.clip(out, 0, 255).astype(np.uint8)


def paths(law):
    return f'gfx/interface/ideas/idea_{law}.dds'


if __name__ == '__main__':
    rows = []
    for law, (col, parts) in LAWS.items():
        van = np.array(Image.open(os.path.join(VANILLA, paths(law))).convert('RGBA'))
        new = badge(van, col, parts)
        assert new[..., 3].any(), law
        if '--install' in sys.argv:
            Image.fromarray(new).save(os.path.join(MOD, paths(law)))
        rows.append((law, van, new))
    sheet = Image.new('RGBA', (230 + 64 * 2 + 64 * 3 + 40, 70 * len(rows)), (20, 24, 34, 255)); d = ImageDraw.Draw(sheet)
    for i, (law, van, new) in enumerate(rows):
        y = i * 70; d.text((0, y + 28), law, fill=(240, 192, 32))
        sheet.alpha_composite(Image.fromarray(van), (230, y)); sheet.alpha_composite(Image.fromarray(new), (300, y))
        sheet.alpha_composite(Image.fromarray(new).resize((32, 32), Image.LANCZOS), (380, y + 16))
    sheet.save(os.path.join(D, 'law_review.png')); print('ok', len(rows))
