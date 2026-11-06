"""Bake Exo 2 into HOI4 bitmap fonts (BMFont text .fnt + uncompressed BGRA .dds / .tga).

Each target keeps the line height / baseline of the font it replaces and is sized so its
average lowercase width stays close to the original, so existing text boxes still fit.
Usage (from mod root):  python -B "plans & scripts/make_fonts.py" [--preview out.png]
"""
import os, re, struct, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TTF = os.path.join(os.path.dirname(__file__), 'fonts', 'Exo2-wght.ttf')
VANILLA = r'F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/fonts'
OUT = os.path.join(ROOT, 'gfx', 'fonts')

# name: (weight, outline px)
TARGETS = {
    'hoi_16mbs': (600, 0), 'hoi_18mbs': (600, 0), 'hoi_18': (500, 0), 'hoi_20b': (700, 0),
    'hoi_22tech': (500, 0), 'cg_16b': (600, 0), 'Arial12': (500, 0),
    'garamond_14': (500, 0), 'garamond_14_bold': (700, 0), 'garamond_16': (500, 0), 'garamond_16_bold': (700, 0),
    'vic_18': (600, 0), 'vic_22': (600, 0),
    'hoi_20bs': (700, 1), 'hoi_24header': (700, 1), 'hoi_30header': (700, 1), 'hoi_33': (700, 1),
    'hoi_36header': (700, 1), 'hoi_30': (600, 1), 'vic_36': (700, 1),
    # dark-ink "inverted" fonts were for vanilla's paper panels; the restyle's panels are dark, so they become white too
    'hoi4_typewriter16_inverted': (500, 0), 'hoi_16typewriter_inverted': (500, 0),
    'hoi4_typewriter22_inverted': (500, 0), 'hoi_22typewriter_inverted': (500, 0),
}
CHARS = list(range(32, 127)) + list(range(160, 384)) + [
    8211, 8212, 8216, 8217, 8218, 8220, 8221, 8222, 8224, 8226, 8230, 8240, 8249, 8250, 8364, 8482]


def target_metrics(name):
    """lineHeight, base, avg lowercase advance and image extensions of the font being replaced."""
    for d in (VANILLA, OUT):  # vanilla first so re-runs do not drift
        p = os.path.join(d, name + '.fnt')
        if os.path.exists(p):
            t = open(p, 'rb').read().decode('latin-1')
            lh = int(re.search(r'lineHeight=(\d+)', t).group(1))
            base = int(re.search(r'base=(\d+)', t).group(1))
            adv = {int(a): int(b) for a, b in re.findall(r'char id=(\d+).*?xadvance=(-?\d+)', t)}
            low = [adv[c] for c in range(97, 123) if c in adv]
            exts = [e for e in ('.dds', '.tga') if os.path.exists(os.path.join(VANILLA, name + e)) or os.path.exists(os.path.join(OUT, name + e))]
            return lh, base, sum(low) / len(low), exts or ['.dds']
    raise SystemExit('no source font for ' + name)


def load(size, weight):
    f = ImageFont.truetype(TTF, size)
    f.set_variation_by_axes([weight])
    return f


def pick_size(lh, low_target, weight):
    best = None
    for s10 in range(60, 800, 5):
        s = s10 / 10
        f = load(s, weight)
        low = sum(f.getlength(chr(c)) for c in range(97, 123)) / 26
        asc, desc = f.getmetrics()
        if low <= low_target * 1.10 and asc + desc <= lh + 3:
            best = s
        else:
            break
    # readability floor: Exo 2 is wider than Garamond, so width-matching alone makes small fonts tiny
    return max(best, min(12.0, lh * 0.8))


def write_dds(path, im):
    w, h = im.size
    r, g, b, a = im.split()
    data = Image.merge('RGBA', (b, g, r, a)).tobytes()  # stored as BGRA
    hdr = struct.pack('<4sIIIIIII44xII4sIIIIIIIII4x', b'DDS ', 124, 0x100F, h, w, w * 4, 0, 1,
                      32, 0x41, b'\0\0\0\0', 32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000, 0x1000, 0, 0, 0)
    open(path, 'wb').write(hdr + data)


def bake(name, weight, outline):
    lh, base, low_target, exts = target_metrics(name)
    size = pick_size(lh, low_target, weight)
    f = load(size, weight)
    notdef = bytes(f.getmask(chr(0xE000)))
    glyphs = []
    for c in CHARS:
        ch = chr(c)
        if c != 32 and bytes(f.getmask(ch)) == notdef:
            continue  # not in Exo 2
        x0, y0, x1, y1 = f.getbbox(ch, anchor='ls', stroke_width=outline)
        w, h = max(0, x1 - x0), max(0, y1 - y0)
        g = Image.new('RGBA', (max(1, w), max(1, h)), (255, 255, 255, 0))
        if w and h:
            ImageDraw.Draw(g).text((-x0, -y0), ch, font=f, anchor='ls', fill=(255, 255, 255, 255),
                                   stroke_width=outline, stroke_fill=(0, 0, 0, 255))
        glyphs.append((c, g, w, h, x0, base + y0, round(f.getlength(ch))))
    # shelf packing, 1px gap
    W = 256
    while True:
        x = y = row = 0
        pos = []
        for c, g, w, h, *_ in glyphs:
            if x + w + 1 > W:
                x, y, row = 0, y + row + 1, 0
            pos.append((x, y))
            x += w + 1
            row = max(row, h)
        H = 1
        while H < y + row + 1:
            H *= 2
        if H <= W:
            break
        W *= 2
    atlas = Image.new('RGBA', (W, H), (255, 255, 255, 0))
    lines = [f'info face="Exo 2" size={-round(size)} bold={int(weight >= 600)} italic=0 charset="" unicode=1 stretchH=100 '
             f'smooth=1 aa=1 padding=0,0,0,0 spacing=1,1 outline={outline}',
             f'common lineHeight={lh} base={base} scaleW={W} scaleH={H} pages=1 packed=0 alphaChnl=0 redChnl=4 greenChnl=4 blueChnl=4',
             f'page id=0 file="{name}_0.dds"', f'chars count={len(glyphs)}']
    for (c, g, w, h, xo, yo, adv), (px, py) in zip(glyphs, pos):
        atlas.paste(g, (px, py))
        lines.append(f'char id={c} x={px} y={py} width={w} height={h} xoffset={xo} yoffset={yo} xadvance={adv} page=0 chnl=15')
    open(os.path.join(OUT, name + '.fnt'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    for e in exts:
        if e == '.dds':
            write_dds(os.path.join(OUT, name + '.dds'), atlas)
        else:
            atlas.save(os.path.join(OUT, name + '.tga'))
    print(f'{name:18} {size:5.1f}px w{weight} lh={lh} base={base} {len(glyphs)} glyphs {W}x{H} {"+".join(exts)}')


def preview(out):
    """Rebuild text from the baked .fnt/.dds files, so what we see is what the game reads."""
    names = list(TARGETS)
    im = Image.new('RGBA', (760, 46 * len(names) + 10), (12, 16, 40, 255))
    for i, n in enumerate(names):
        t = open(os.path.join(OUT, n + '.fnt')).read()
        ch = {int(m[0]): list(map(int, m[1:])) for m in re.findall(
            r'char id=(\d+) x=(\d+) y=(\d+) width=(\d+) height=(\d+) xoffset=(-?\d+) yoffset=(-?\d+) xadvance=(-?\d+)', t)}
        ext = '.dds' if os.path.exists(os.path.join(OUT, n + '.dds')) else '.tga'
        atlas = Image.open(os.path.join(OUT, n + ext)).convert('RGBA')
        x, y = 10, 10 + 46 * i
        for c in (n + ':  Anti-Militarist Faction (5) - Senate +10% Ébène'):
            if ord(c) not in ch:
                continue
            gx, gy, w, h, xo, yo, adv = ch[ord(c)]
            if w and h:
                g = atlas.crop((gx, gy, gx + w, gy + h))
                im.alpha_composite(g, (x + xo, y + yo)) if x + xo >= 0 else None
            x += adv
    im.save(out)


if __name__ == '__main__':
    if '--preview' in sys.argv:
        preview(sys.argv[sys.argv.index('--preview') + 1])
    else:
        for n, (w, o) in TARGETS.items():
            bake(n, w, o)
