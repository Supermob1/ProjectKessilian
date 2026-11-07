"""Test: CWIC-style flat manufacturer idea icons (cyan + gold), drawn as vector shapes.
Shapes on a 1000x1000 grid; F = filled polygon, C = cut (erased) polygon, L/CL = filled/cut line, E/CE = ellipse.
Output: 64x64 RGBA TGA per icon/colour + review sheet at 1x/2x/8x."""
import sys, os
from PIL import Image, ImageDraw, ImageFilter, ImageChops

OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
SIZE, PAD, SS = 64, 5, 1000
CYAN, GOLD = (0, 176, 240), (240, 192, 32)

def rect(x0, y0, x1, y1): return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

ICONS = {
  # BlasTech: DC-15A blaster rifle, drawn pointing right, tilted up
  'blastech': dict(rot=28, ops=[
    ('F', [(40, 470), (250, 450), (260, 560), (120, 640), (40, 640)]),      # stock
    ('C', [(90, 520), (200, 505), (200, 540), (120, 585), (90, 585)]),      # stock cut-out
    ('F', rect(240, 430, 640, 560)),                                         # receiver
    ('F', rect(620, 455, 820, 535)),                                         # shroud
    ('F', rect(800, 478, 960, 512)),                                         # barrel
    ('F', rect(940, 462, 985, 528)),                                         # muzzle
    ('F', rect(320, 350, 580, 400)), ('F', rect(360, 395, 395, 435)), ('F', rect(505, 395, 540, 435)),  # scope + mounts
    ('F', [(330, 555), (400, 555), (380, 690), (300, 690)]),                 # grip
    ('F', [(450, 555), (530, 555), (540, 660), (470, 672)]),                 # magazine
    ('CL', [(255, 495), (625, 495)], 14),                                    # receiver seam
    *[('C', rect(x, 470, x + 18, 520)) for x in (650, 690, 730, 770)],       # vents
    ('C', rect(330, 368, 360, 382)),                                         # scope lens
  ]),
  # Rothana Heavy Engineering: AT-TE walker, side view
  'rothana': dict(rot=0, ops=[
    ('F', [(180, 330), (770, 330), (850, 390), (850, 520), (770, 560), (180, 560), (130, 500), (130, 390)]),  # hull
    ('F', [(770, 360), (900, 385), (945, 450), (905, 520), (790, 530)]),    # cab
    ('C', [(845, 420), (905, 430), (915, 455), (850, 455)]),                 # cab window
    ('F', rect(400, 255, 560, 335)), ('F', rect(555, 275, 760, 300)),        # turret + gun
    ('CL', [(190, 445), (760, 445)], 14),                                    # hull seam
    *[('C', rect(x, 370, x + 70, 410)) for x in (230, 340, 450, 560, 670)],  # side panels
    *[op for x in (230, 470, 700) for op in (
        ('L', [(x, 520), (x + 70, 640)], 55),                               # thigh
        ('L', [(x + 70, 640), (x + 25, 800)], 50),                          # shin
        ('F', rect(x - 30, 790, x + 85, 830)),                              # foot
        ('E', (x + 40, 605, x + 100, 665)))],                               # knee
  ]),
  # Kuat Drive Yards: Venator star destroyer, top view
  'kdy': dict(rot=0, ops=[
    ('F', [(500, 60), (850, 830), (690, 900), (310, 900), (150, 830)]),     # hull
    ('C', [(500, 170), (535, 600), (465, 600)]),                             # flight deck trench
    ('CL', [(500, 120), (230, 820)], 12), ('CL', [(500, 120), (770, 820)], 12),
    ('C', rect(395, 640, 605, 790)),                                         # tower gap
    ('F', rect(415, 655, 480, 775)), ('F', rect(520, 655, 585, 775)),        # twin bridge towers
    ('F', rect(330, 900, 670, 950)),                                         # engine block
    *[('C', rect(x, 905, x + 40, 945)) for x in (360, 440, 520, 600)],       # thrusters
  ]),
  # Incom: ARC-170 starfighter, top view
  'incom': dict(rot=0, ops=[
    ('F', [(470, 60), (530, 60), (565, 280), (575, 820), (425, 820), (435, 280)]),  # fuselage
    ('C', [(485, 150), (515, 150), (525, 260), (475, 260)]),                 # canopy
    ('F', [(110, 500), (890, 500), (890, 650), (110, 650)]),                 # S-foils
    ('CL', [(120, 575), (420, 575)], 14), ('CL', [(580, 575), (880, 575)], 14),
    ('F', rect(120, 230, 175, 520)), ('F', rect(825, 230, 880, 520)),        # wingtip cannons
    ('F', rect(350, 430, 420, 760)), ('F', rect(580, 430, 650, 760)),        # engines
    ('C', rect(365, 700, 405, 745)), ('C', rect(595, 700, 635, 745)),
    ('F', [(425, 760), (300, 900), (360, 900), (440, 820)]),                 # tail fins
    ('F', [(575, 760), (700, 900), (640, 900), (560, 820)]),
  ]),
  # Baktoid Combat Automata: B1 battle droid head, side view
  'baktoid': dict(rot=0, ops=[
    ('F', [(130, 360), (420, 290), (590, 320), (900, 560), (880, 640), (590, 600), (330, 640), (160, 560)]),
    ('CE', (360, 370, 470, 480)), ('E', (385, 395, 445, 455)),               # eye ring + pupil
    ('CL', [(590, 330), (580, 600)], 14),                                    # snout joint
    ('CL', [(620, 470), (860, 595)], 12),                                    # mouth line
    ('F', [(270, 630), (420, 615), (440, 860), (250, 860)]),                 # neck
    ('C', rect(300, 700, 410, 720)), ('C', rect(300, 760, 410, 780)),
  ]),
  # Haor Chall: Vulture droid, top view (flight mode)
  'haor_chall': dict(rot=0, ops=[
    ('F', [(470, 300), (530, 300), (560, 700), (440, 700)]),                 # spine
    ('F', [(440, 380), (90, 250), (60, 330), (440, 520)]),                   # upper wings
    ('F', [(560, 380), (910, 250), (940, 330), (560, 520)]),
    ('F', [(440, 560), (110, 780), (150, 840), (450, 680)]),                 # lower wings
    ('F', [(560, 560), (890, 780), (850, 840), (550, 680)]),
    ('F', [(455, 130), (545, 130), (580, 320), (420, 320)]),                 # head
    ('CE', (470, 180, 530, 240)),
    ('CL', [(430, 450), (110, 300)], 12), ('CL', [(570, 450), (890, 300)], 12),
    ('CL', [(440, 620), (140, 800)], 12), ('CL', [(560, 620), (860, 800)], 12),
  ]),
}

def draw_ops(ops):
    m = Image.new('L', (SS, SS), 0)
    d = ImageDraw.Draw(m)
    for op in ops:
        k, a = op[0], op[1]
        fill = 0 if k.startswith('C') else 255
        if k in ('F', 'C'): d.polygon(a, fill=fill)
        elif k in ('L', 'CL'): d.line(a, fill=fill, width=op[2])
        elif k in ('E', 'CE'): d.ellipse(a, fill=fill)
        elif k in ('O', 'CO'): d.ellipse(a, outline=fill, width=op[2])  # ellipse ring
        elif k in ('A', 'CA'): d.arc(a, op[2], op[3], fill=fill, width=op[4])  # arc: box, start, end, width
    return m

def mask_of(spec):
    m = draw_ops(spec['ops'])
    if spec['rot']: m = m.rotate(spec['rot'], resample=Image.BICUBIC, expand=True)
    m = m.crop(m.getbbox())
    box = SIZE - 2 * PAD
    s = box / max(m.size)
    m = m.resize((max(1, round(m.width * s)), max(1, round(m.height * s))), Image.LANCZOS)
    out = Image.new('L', (SIZE, SIZE), 0)
    out.paste(m, ((SIZE - m.width) // 2, (SIZE - m.height) // 2))
    return out.point(lambda v: max(0, min(255, (v - 50) * 255 // 160)))  # crisper edges

def render(mask, col):
    glow = mask.filter(ImageFilter.GaussianBlur(2.2 * min(mask.size) / SIZE + 0.4)).point(lambda v: v * 6 // 10)
    shadow = ImageChops.offset(mask, 1, 1).point(lambda v: v * 8 // 10)
    im = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    for colour, a in ((col, glow), ((0, 0, 0), shadow), (col, mask)):
        layer = Image.new('RGBA', mask.size, colour + (0,))
        layer.putalpha(a)
        im.alpha_composite(layer)
    return im

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    tiles = []
    for name, spec in ICONS.items():
        m = mask_of(spec)
        assert m.getbbox(), name
        pair = []
        for tag, col in (('cyan', CYAN), ('gold', GOLD)):
            im = render(m, col)
            im.save(os.path.join(OUT, f'idea_{name}_{tag}.tga'))
            pair.append(im)
        tiles.append((name, pair))
    # review sheet: per icon row -> cyan 1x, gold 1x, cyan 2x, gold 2x, cyan 8x on idea-slot navy
    bg = (0, 1, 22, 255)
    W, rowh = 64 + 64 + 128 + 128 + 512 + 60, 512 + 10
    sheet = Image.new('RGBA', (W, rowh * len(tiles)), bg)
    for r, (name, (c, g)) in enumerate(tiles):
        x, y = 0, r * rowh
        for im, k in ((c, 1), (g, 1), (c, 2), (g, 2), (c, 8)):
            sheet.alpha_composite(im.resize((64 * k, 64 * k), Image.NEAREST), (x, y)); x += 64 * k + 12
    sheet.save(os.path.join(OUT, 'review_sheet.png'))
    print('ok', len(tiles))
