"""Canon SW company logos (Wookieepedia SVG renders) -> single-colour CWIC-style idea icons.
mode ('lum', T): keep pixels brighter than T.  'edges': whole logo, colour boundaries cut out."""
import os, sys
from PIL import Image, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(__file__))
from cwic_icons import render, SIZE, PAD, CYAN, GOLD

D = os.path.dirname(os.path.abspath(__file__))
LOGOS = {'blastech': ('BlasTech', 'stars'), 'ksy': ('KDY', ('lum', 128)),
         'kse': ('Kuat_Systems_Engineering', ('lum', 128)), 'incom': ('Incom', ('lum', 235)),
         'baktoid': ('Baktoid', 'edges')}

def svg_mask(fn, idx, px):
    """Rasterise path #idx of a simple SVG (M/L/l/Z only, even-odd) at px wide."""
    import re
    from PIL import ImageDraw
    svg = open(os.path.join(D, 'logos', fn + '.svg')).read()
    vb = float(re.search(r'viewBox="0 0 ([\d.]+)', svg).group(1)); k = px / vb
    d = re.findall(r' d="([^"]+)"', svg)[idx]
    m = Image.new('L', (px, px), 0)
    for sub in re.findall(r'M[^M]+', d):
        pts, x, y, cmd = [], 0, 0, 'M'
        toks = re.findall(r'[MLlZz]|-?\d*\.?\d+', sub)
        i = 0
        while i < len(toks):
            t = toks[i]
            if t in 'MLlZz': cmd = t; i += 1; continue
            dx, dy = float(toks[i]), float(toks[i + 1]); i += 2
            if cmd == 'l': x, y = x + dx, y + dy
            else: x, y = dx, dy
            if cmd == 'M': cmd = 'L'
            pts.append((x * k, y * k))
        sm = Image.new('L', (px, px), 0); ImageDraw.Draw(sm).polygon(pts, fill=255)
        m = ImageChops.logical_xor(m.convert('1'), sm.convert('1')).convert('L')  # even-odd
    return m

def mask_of(fn, mode, size=(SIZE, SIZE), pad=PAD, crop=None, rot=0):
    im = Image.open(os.path.join(D, 'logos', fn + '.png')).convert('RGBA')
    if crop:  # fractional (l, t, r, b) box, e.g. to drop a text ring
        im = im.crop(tuple(round(c * im.size[i % 2]) for i, c in enumerate(crop)))
    a = im.getchannel('A').point(lambda v: 255 if v > 128 else 0)
    if mode == 'stars':  # BlasTech: two star outlines from the SVG; light star passes under the dark one with a gap
        light, dark = (svg_mask('BlasTech', i, 1000) for i in (0, 1))
        gap = dark.filter(ImageFilter.MaxFilter(27))
        m = ImageChops.add(ImageChops.subtract(light, gap), dark)
    elif mode == 'edges':
        q = im.convert('RGB').quantize(8).convert('RGB')
        e = q.filter(ImageFilter.FIND_EDGES).convert('L').point(lambda v: 255 if v > 20 else 0)
        e = e.filter(ImageFilter.MaxFilter(max(3, im.width // 60 | 1)))
        e = ImageChops.multiply(e, a.filter(ImageFilter.MinFilter(max(3, im.width // 40 | 1))))  # keep outer edge
        m = ImageChops.subtract(a, e)
    elif mode[0] == 'dark':  # emblem drawn in black on a light field
        m = ImageChops.multiply(a, im.convert('L').point(lambda v: 255 if v < mode[1] else 0))
    elif mode[0] == 'cut':  # cutout photo/render: silhouette = alpha & brighter than bg, darkest areas cut as detail
        _, bg, cut = mode
        L = im.convert('L')
        m = ImageChops.multiply(a, L.point(lambda v: 255 if v > bg else 0))
        m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))  # close specks in the silhouette
        k = max(3, round(im.width / size[0] * 0.9)) | 1  # cut lines survive the downscale as ~1px
        m = ImageChops.subtract(m, ImageChops.multiply(L.point(lambda v: 255 if v < cut else 0).filter(ImageFilter.MaxFilter(k)),
                                                       m.filter(ImageFilter.MinFilter(k))))  # keep the outline intact
    else:
        m = ImageChops.multiply(a, im.convert('L').point(lambda v: 255 if v >= mode[1] else 0))
    if rot: m = m.rotate(rot, resample=Image.BICUBIC, expand=True)
    m = m.crop(m.getbbox())
    s = min((size[0] - 2 * pad) / m.width, (size[1] - 2 * pad) / m.height)
    m = m.resize((max(1, round(m.width * s)), max(1, round(m.height * s))), Image.LANCZOS)
    out = Image.new('L', size, 0)
    out.paste(m, ((size[0] - m.width) // 2, (size[1] - m.height) // 2))
    return out.point(lambda v: max(0, min(255, (v - 50) * 255 // 160)))

def holo(im):  # hologram scanlines: every other row dimmed
    px = im.load()
    for y in range(1, SIZE, 2):
        for x in range(SIZE):
            r, g, b, al = px[x, y]
            px[x, y] = (r, g, b, al * 6 // 10)
    return im

if __name__ == '__main__':
    out = os.path.join(D, 'logo_out'); os.makedirs(out, exist_ok=True)
    install = '--install' in sys.argv  # cyan version -> mod idea textures
    IDEAS = os.path.join(D, '..', '..', 'gfx', 'interface', 'ideas')
    rows = []
    for name, (fn, mode) in LOGOS.items():
        m = mask_of(fn, mode); assert m.getbbox(), name
        c, g = render(m, CYAN), render(m, GOLD)
        h = holo(render(m, CYAN))
        for tag, im in (('cyan', c), ('gold', g), ('holo', h)):
            im.save(os.path.join(out, f'idea_{name}_{tag}.tga'))
        if install: c.save(os.path.join(IDEAS, f'idea_{name}.tga'))
        rows.append((c, g, h))
    sheet = Image.new('RGBA', (64 * 3 + 128 * 3 + 512 + 80, 522 * len(rows)), (0, 1, 22, 255))
    for r, (c, g, h) in enumerate(rows):
        x = 0
        for im, k in ((c, 1), (g, 1), (h, 1), (c, 2), (g, 2), (h, 2), (c, 8)):
            sheet.alpha_composite(im.resize((64 * k, 64 * k), Image.NEAREST), (x, r * 522)); x += 64 * k + 10
    sheet.save(os.path.join(D, 'logo_review.png')); print('ok', len(rows))
