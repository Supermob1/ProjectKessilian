"""CWIC canon pictogram library: subject name (hod_vector/hod_icons vocabulary) -> canon Star Wars source.
Source kinds: a logo/render file in logos/ with a mask mode, or a DRAWN shape list (iconic canon view, 1000x1000 grid,
cwic_icons op format). hod_vector.render() asks coverage() first, so every hod_icons icon of these subjects uses it.

  python -B cwic_library.py      -> library_review.png (every subject at 64, 32 and 20 px)"""
import os, sys
from functools import lru_cache
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cwic_icons import draw_ops, ICONS as PICTO
from logo_icons import mask_of

D = os.path.dirname(os.path.abspath(__file__))
LOGOS = os.path.join(D, 'logos')

def rect(x0, y0, x1, y1): return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

def dodecahedron_ops():
    """Faceted holocron: real dodecahedron, 3/4 view. Silhouette filled, visible edges cut, each front face an inset
    panel, the face nearest the viewer a glowing core."""
    import itertools, math
    g = (1 + 5 ** .5) / 2
    V = [v for v in itertools.product((-1, 1), repeat=3)]
    for a, b in itertools.product((-1, 1), repeat=2):
        V += [(0, a / g, b * g), (a / g, b * g, 0), (a * g, 0, b / g)]
    def rot(v, ax, ay):
        x, y, z = v
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        return x, y, z
    V = [rot(v, 0.45, 0.35) for v in V]
    C = []                                              # face centres = icosahedron directions
    for a, b in itertools.product((-1, 1), repeat=2):
        C += [(0, a * g, b), (a * g, b, 0), (a, 0, b * g)]
    C = [rot(c, 0.45, 0.35) for c in C]
    k = 420 / max(max(abs(x), abs(y)) for x, y, _ in V)
    P = lambda v: (500 + v[0] * k, 500 - v[1] * k)
    ops, faces = [], []
    for c in C:
        idx = sorted(range(20), key=lambda i: -sum(p * q for p, q in zip(V[i], c)))[:5]
        cx, cy = sum(V[i][0] for i in idx) / 5, sum(V[i][1] for i in idx) / 5
        idx.sort(key=lambda i: math.atan2(V[i][1] - cy, V[i][0] - cx))
        faces.append((c[2], [V[i] for i in idx]))
    for _, f in faces:
        ops.append(('F', [P(v) for v in f]))
    front = sorted((f for f in faces if f[0] > 0), key=lambda f: f[0])
    for z, f in front:
        pts = [P(v) for v in f]
        mx, my = sum(x for x, _ in pts) / 5, sum(y for _, y in pts) / 5
        ops += [('CL', pts + [pts[0]], 26)]
        inset = lambda t: [(mx + (x - mx) * t, my + (y - my) * t) for x, y in pts]
        ops += [('C', inset(0.62)), ('F', inset(0.42))]
    z, f = front[-1]
    pts = [P(v) for v in f]; mx, my = sum(x for x, _ in pts) / 5, sum(y for _, y in pts) / 5
    ops += [('CE', (mx - 45, my - 45, mx + 45, my + 45)), ('E', (mx - 22, my - 22, mx + 22, my + 22))]
    return ops

DRAWN = {
    # Death Star: sphere, superlaser dish upper-left, equatorial trench
    'death_star': [('E', (20, 20, 980, 980)), ('CE', (230, 170, 530, 470)), ('E', (300, 240, 460, 400)),
                   ('CE', (355, 295, 405, 345)), ('CL', [(20, 520), (980, 520)], 30)],
    # YT-1300 from above, bow right: disc, split mandibles, starboard cockpit tube
    'yt1300': [('E', (60, 170, 720, 830)), ('F', [(560, 300), (960, 400), (960, 480), (600, 480)]),
               ('F', [(560, 700), (960, 600), (960, 520), (600, 520)]), ('C', rect(700, 480, 1000, 520)),
               ('F', [(560, 760), (790, 860), (800, 930), (520, 820)]), ('E', (740, 830, 860, 950)),
               ('CO', (190, 300, 590, 700), 18),
               *[('CL', [(390, 500), p], 16) for p in ((70, 500), (160, 280), (160, 720), (390, 180), (390, 820))],
               ('CE', (300, 410, 480, 590)), ('E', (330, 440, 450, 560)), ('CE', (370, 480, 410, 520)),
               ('CL', [(620, 440), (940, 440)], 12), ('CL', [(620, 560), (940, 560)], 12),
               ('CE', (770, 860, 830, 920))],
    # Republic star destroyer in profile, bow right: long wedge hull, stepped superstructure, bridge tower
    'star_destroyer': [('F', [(40, 560), (970, 610), (970, 640), (40, 770)]), ('F', [(70, 560), (520, 560), (440, 470), (110, 470)]),
                       ('F', rect(170, 330, 330, 470)), ('F', rect(110, 280, 390, 340)), ('F', rect(0, 590, 50, 750)),
                       ('CL', [(60, 640), (900, 625)], 18), ('CL', [(60, 700), (700, 660)], 14),
                       ('C', rect(130, 300, 370, 315)),
                       *[('CL', [(x, 485), (x, 555)], 14) for x in (180, 260, 340, 420)],
                       ('CL', [(200, 360), (300, 360)], 14), ('CL', [(200, 410), (300, 410)], 14),
                       ('CL', [(0, 640), (50, 640)], 14), ('CL', [(0, 700), (50, 700)], 14)],
    # Hush-98 comlink, front view: capsule body, splayed antennas, control plate with slider slots
    'comlink': [('F', rect(300, 260, 700, 800)), ('E', (300, 100, 700, 420)), ('E', (300, 640, 700, 960)),
                ('L', [(400, 160), (290, 0)], 45), ('L', [(600, 160), (710, 0)], 45),
                ('CE', (380, 380, 620, 900)),
                ('F', rect(425, 470, 470, 820)), ('F', rect(530, 440, 575, 800)),
                ('F', rect(400, 600, 495, 650)), ('F', rect(505, 520, 600, 570)), ('CE', (450, 200, 550, 300))],
    # exploded planet: cracked core, flying fragments, flat shockwave ring (Alderaan / Death Star blast)
    'exploded_planet': [('E', (230, 210, 770, 750)),
                        *[('CL', [(500, 480), p], 34) for p in ((400, 220), (760, 380), (600, 750), (240, 600))],
                        ('CE', (440, 420, 560, 540)),
                        ('F', [(120, 150), (210, 130), (230, 210), (140, 230)]), ('F', [(800, 120), (900, 160), (850, 230)]),
                        ('F', [(820, 760), (910, 780), (870, 860), (800, 830)]), ('F', [(90, 780), (180, 750), (160, 850)]),
                        ('CO', (60, 405, 940, 575), 75), ('O', (90, 430, 910, 550), 45)],
    # droid-foundry conveyor: belt loop on rollers carrying crates, assembly claw above
    'conveyor': [('E', (40, 600, 240, 800)), ('E', (760, 600, 960, 800)),
                 ('F', rect(140, 600, 860, 800)), ('C', rect(170, 650, 830, 750)), ('CE', (95, 655, 185, 745)), ('CE', (815, 655, 905, 745)),
                 ('E', (115, 675, 165, 725)), ('E', (835, 675, 885, 725)),
                 *[('E', (x, 680, x + 40, 720)) for x in (300, 440, 580)],
                 ('F', rect(220, 400, 420, 590)), ('C', rect(240, 480, 400, 495)),
                 ('F', rect(560, 430, 740, 590)), ('C', rect(580, 500, 720, 515)),
                 ('F', rect(80, 60, 920, 120)), ('F', rect(620, 120, 670, 270)),
                 ('L', [(645, 270), (590, 360)], 40), ('L', [(645, 270), (700, 360)], 40)],
    # crossed lightsabers: two hilts low, blades crossing in an X
    'sabers': [('L', [(250, 700), (880, 70)], 70), ('L', [(750, 700), (120, 70)], 70),
               ('L', [(140, 810), (270, 680)], 95), ('L', [(860, 810), (730, 680)], 95),
               ('CL', [(175, 735), (215, 775)], 22), ('CL', [(825, 735), (785, 775)], 22),
               ('L', [(260, 690), (300, 650)], 130), ('L', [(740, 690), (700, 650)], 130)],
    # Republic/Imperial officer rank plaque: plate with two rows of code tiles
    'rank_plaque': [('F', rect(80, 280, 920, 720)),
                    *[('C', rect(x, y, x + 150, y + 130)) for y in (340, 530) for x in (150, 345, 540, 735)],
                    *[('F', rect(x + 30, y + 30, x + 120, y + 100)) for x, y in ((150, 340), (345, 340), (540, 530))]],
    # galaxy map: bright core with two curling arms
    'galaxy': [('E', (400, 420, 600, 580)),
               ('A', (300, 330, 820, 670), 180, 360, 75), ('A', (180, 330, 700, 670), 0, 180, 75),
               ('A', (40, 190, 820, 810), 150, 300, 55), ('A', (180, 190, 960, 810), 330, 480, 55),
               ('CE', (475, 475, 525, 525))],
    # ringed planet
    'ringed_planet': [('E', (230, 230, 770, 770)), ('CE', (300, 250, 760, 700)), ('E', (330, 270, 750, 690)),
                      ('CO', (20, 400, 980, 600), 80), ('O', (50, 425, 950, 575), 45)],
    # LAAT/i gunship, front view: cockpit body, broad wing with ball turrets and wingtip pods
    'laat': [('F', [(40, 520), (180, 380), (700, 380), (900, 450), (960, 560), (880, 640), (120, 640)]),
             ('E', (760, 400, 940, 580)), ('CE', (800, 430, 900, 530)), ('CL', [(850, 430), (850, 530)], 14),
             ('F', [(250, 380), (330, 200), (560, 200), (620, 380)]), ('F', rect(300, 150, 580, 210)),
             ('CL', [(320, 290), (590, 290)], 14), ('CL', [(440, 210), (440, 380)], 14),
             ('E', (240, 220, 340, 320)), ('E', (540, 220, 640, 320)), ('CE', (270, 250, 310, 290)), ('CE', (570, 250, 610, 290)),
             ('F', [(40, 520), (0, 380), (100, 380), (160, 470)]),
             ('C', rect(300, 470, 620, 560)), ('F', rect(330, 495, 590, 535)),
             ('CL', [(140, 600), (860, 600)], 18), ('CL', [(200, 420), (700, 420)], 12)],
    # AT-TE, side view, bow right: hull, cab, dorsal cannon, three short splayed legs
    'atte': [('F', [(140, 300), (760, 300), (840, 350), (840, 500), (760, 540), (140, 540), (90, 480), (90, 350)]),
             ('F', [(760, 330), (900, 350), (950, 420), (900, 490), (780, 500)]), ('C', [(860, 385), (915, 395), (925, 425), (865, 425)]),
             ('F', rect(380, 215, 540, 300)), ('F', rect(540, 240, 750, 262)),
             ('CL', [(150, 430), (750, 430)], 14), *[('C', rect(x, 335, x + 70, 380)) for x in (180, 290, 400, 510, 620)],
             *[op for x, d in ((210, -1), (450, 0), (690, 1)) for op in (
                 ('L', [(x, 520), (x + 60 * d, 640)], 58), ('L', [(x + 60 * d, 640), (x + 40 * d, 770)], 50),
                 ('E', (x + 60 * d - 38, 602, x + 60 * d + 38, 678)), ('CE', (x + 60 * d - 14, 626, x + 60 * d + 14, 654)),
                 ('F', rect(x + 40 * d - 65, 760, x + 40 * d + 65, 800)))]],
    # DRK-1 Sith probe droid (spy): sphere, big photoreceptor, side fins, antenna and sensor spikes
    'probe_droid': [('E', (200, 200, 800, 800)), ('CO', (225, 225, 775, 775), 14),
                    ('CE', (320, 320, 680, 680)), ('E', (370, 370, 630, 630)), ('CE', (450, 450, 550, 550)),
                    ('F', [(210, 430), (30, 360), (50, 580), (210, 540)]), ('F', [(790, 430), (970, 360), (950, 580), (790, 540)]),
                    ('L', [(500, 210), (500, 60)], 30), ('E', (465, 20, 535, 90)),
                    ('L', [(420, 780), (370, 970)], 28), ('L', [(500, 795), (500, 990)], 28), ('L', [(580, 780), (630, 970)], 28)],
    # Consular-class diplomatic cruiser, top view, bow up: hammerhead bow, long hull, three round engines
    'consular': [('F', [(150, 120), (330, 60), (670, 60), (850, 120), (800, 230), (600, 290), (400, 290), (200, 230)]),
                 ('C', [(330, 130), (670, 130), (640, 170), (360, 170)]), ('CE', (470, 190, 530, 250)),
                 ('F', [(420, 280), (580, 280), (660, 700), (340, 700)]),
                 ('CL', [(500, 300), (500, 680)], 16), ('CL', [(420, 450), (580, 450)], 14), ('CL', [(400, 560), (600, 560)], 14),
                 ('F', [(300, 640), (700, 640), (760, 760), (240, 760)]),
                 *[op for x0, y0 in ((200, 720), (410, 760), (620, 720)) for op in (
                     ('E', (x0, y0, x0 + 180, y0 + 180)), ('CE', (x0 + 45, y0 + 45, x0 + 135, y0 + 135)),
                     ('E', (x0 + 70, y0 + 70, x0 + 110, y0 + 110)))]],
    # deflector shield generator: dome over a base with energy arcs
    'shield_dome': [('A', (60, 150, 940, 1030), 180, 360, 60), ('A', (200, 290, 800, 890), 180, 360, 40),
                    ('E', (330, 420, 670, 760)), ('F', rect(230, 590, 770, 760)), ('F', rect(120, 760, 880, 830)),
                    ('C', rect(300, 650, 700, 670))],
    # Jedi holocron: isometric cube, faces split, glyph on each face
    'holocron': dodecahedron_ops(),
    # BTL Y-wing, top view, bow up: cockpit pod, neck, cross wing, twin engine nacelles
    'ywing': [('F', [(500, 30), (590, 110), (610, 330), (390, 330), (410, 110)]),            # cockpit pod, pointed nose
              ('CE', (445, 120, 555, 230)), ('CL', [(410, 290), (590, 290)], 16),
              ('F', [(460, 330), (540, 330), (560, 600), (440, 600)]),                           # exposed neck
              ('CL', [(500, 350), (500, 580)], 14),
              ('F', [(350, 570), (650, 570), (680, 720), (320, 720)]),                           # engine block
              ('F', [(150, 610), (850, 610), (830, 680), (170, 680)]),                           # spar
              *[op for x in (120, 740) for op in (
                  ('E', (x, 330, x + 140, 470)), ('F', [(x, 400), (x + 140, 400), (x + 130, 930), (x + 10, 930)]),
                  ('CE', (x + 40, 370, x + 100, 430)),
                  *[('CL', [(x + 5, y), (x + 135, y)], 14) for y in (520, 760, 840)],
                  ('C', rect(x + 35, 880, x + 105, 930)))]],
    # --- canon hardware for the former plain vector subjects ---
    # SPHA-T self-propelled heavy artillery, side: long hull, huge raised barrel, short legs
    'spha': [('F', [(60, 520), (760, 520), (820, 600), (760, 700), (60, 700)]), ('F', rect(140, 430, 520, 525)),
             ('L', [(560, 520), (960, 180)], 90), ('L', [(560, 520), (700, 400)], 150), ('CL', [(700, 330), (760, 420)], 20),
             ('CL', [(80, 610), (740, 610)], 16), *[('C', rect(x, 455, x + 50, 500)) for x in (180, 280, 380)],
             *[op for x in (120, 290, 460, 630) for op in (('L', [(x, 690), (x - 30, 820)], 50), ('L', [(x - 30, 820), (x, 940)], 45),
                                                          ('F', rect(x - 60, 930, x + 50, 970)))]],
    # AV-7 anti-vehicle cannon: tripod, armoured housing, long barrel up-right
    'av7': [('L', [(330, 820), (150, 970)], 45), ('L', [(500, 820), (520, 980)], 45), ('L', [(640, 800), (860, 960)], 45),
            ('F', [(220, 600), (680, 520), (740, 760), (300, 860)]), ('F', [(170, 470), (320, 430), (350, 640), (210, 690)]),
            ('L', [(620, 620), (980, 300)], 70), ('L', [(620, 620), (780, 480)], 125), ('CL', [(800, 420), (850, 480)], 18),
            ('CL', [(260, 700), (690, 630)], 16), ('C', [(380, 610), (560, 580), (570, 620), (390, 650)])],
    # hydrospanner: grip-ringed handle, open jaw head
    'hydrospanner': [('L', [(160, 840), (660, 340)], 110), ('E', (90, 770, 230, 910)),
                     *[('CL', [(x - 45, y - 45), (x + 45, y + 45)], 18) for x, y in ((260, 740), (330, 670), (400, 600))],
                     ('E', (580, 120, 900, 440)), ('CE', (660, 200, 820, 360)), ('C', [(740, 280), (950, 60), (1000, 180), (800, 330)]),
                     ('E', (715, 255, 765, 305))],
    # concussion missile (drawn upright, shown rotated): nose, bands, fins, exhaust
    'missile': [('F', rect(420, 250, 580, 780)), ('F', [(420, 250), (500, 50), (580, 250)]),
                ('F', [(420, 640), (290, 860), (420, 800)]), ('F', [(580, 640), (710, 860), (580, 800)]), ('F', rect(480, 700, 520, 900)),
                ('E', (430, 760, 570, 900)), ('CE', (465, 795, 535, 865)),
                ('CL', [(420, 330), (580, 330)], 18), ('CL', [(420, 600), (580, 600)], 18), ('CE', (470, 410, 530, 470))],
    # ion engine, rear view: hexagonal housing, nozzle ring, glowing core with vanes
    'ion_engine': [('F', [(500 + 470 * __import__('math').cos(a / 3 * 3.14159), 500 + 470 * __import__('math').sin(a / 3 * 3.14159))
                          for a in range(6)]),
                   ('CO', (130, 130, 870, 870), 30), ('CE', (230, 230, 770, 770)), ('E', (290, 290, 710, 710)), ('CE', (380, 380, 620, 620)),
                   ('E', (430, 430, 570, 570)),
                   *[('CL', [(500 + 160 * __import__('math').cos(a), 500 + 160 * __import__('math').sin(a)),
                             (500 + 230 * __import__('math').cos(a), 500 + 230 * __import__('math').sin(a))], 24)
                     for a in (0.5, 1.55, 2.6, 3.65, 4.7, 5.75)]],
    # cargo container, 3/4 view: three faces, panel inset, corner posts, stencil marks
    'cargo': [('F', [(170, 300), (560, 170), (900, 290), (510, 420)]), ('F', [(170, 300), (510, 420), (510, 920), (170, 790)]),
              ('F', [(510, 420), (900, 290), (900, 780), (510, 920)]),
              ('CL', [(170, 300), (510, 420), (900, 290)], 22), ('CL', [(510, 420), (510, 920)], 22),
              ('C', [(230, 400), (450, 480), (450, 820), (230, 740)]), ('F', [(270, 450), (410, 500), (410, 770), (270, 720)]),
              *[('C', [(590 + i * 90, 470 - i * 30), (650 + i * 90, 450 - i * 30), (650 + i * 90, 520 - i * 30), (590 + i * 90, 540 - i * 30)])
                for i in range(3)],
              ('CL', [(560, 700), (850, 600)], 18), ('CL', [(560, 760), (850, 660)], 18)],
    # orbital station: hub, outer ring, spokes, docking pods
    'orbital_station': [('O', (60, 60, 940, 940), 80), ('E', (360, 360, 640, 640)), ('CE', (430, 430, 570, 570)), ('E', (465, 465, 535, 535)),
                        *[('L', [(500 + 140 * dx, 500 + 140 * dy), (500 + 400 * dx, 500 + 400 * dy)], 50) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))],
                        *[('E', (500 + 310 * dx - 70, 500 + 310 * dy - 70, 500 + 310 * dx + 70, 500 + 310 * dy + 70))
                          for dx, dy in ((.707, .707), (-.707, .707), (.707, -.707), (-.707, -.707))],
                        ('CO', (100, 100, 900, 900), 14)],
    # holo-chart: projector base, emitter, light cone, rising bar chart
    'holochart': [('F', [(300, 880), (700, 880), (640, 970), (360, 970)]), ('F', rect(450, 800, 550, 880)),
                  ('L', [(500, 800), (110, 640)], 16), ('L', [(500, 800), (890, 640)], 16),
                  *[('F', rect(x, top, x + 100, 640)) for x, top in ((150, 470), (290, 380), (430, 300), (570, 200), (710, 90))],
                  *[('CL', [(x, 520), (x + 100, 520)], 14) for x in (150, 290, 430, 570, 710)]],
    # macrobinoculars: wide body, two big lenses, rangefinder bar
    'macrobinoculars': [('F', rect(110, 330, 890, 720)), ('E', (40, 330, 240, 720)), ('E', (760, 330, 960, 720)),
                        ('CE', (150, 380, 450, 680)), ('E', (210, 440, 390, 620)), ('CE', (265, 495, 335, 565)),
                        ('CE', (550, 380, 850, 680)), ('E', (610, 440, 790, 620)), ('CE', (665, 495, 735, 565)),
                        ('F', rect(300, 210, 700, 330)), *[('C', rect(x, 240, x + 60, 300)) for x in (340, 470, 600)]],
    # starfighter targeting display: corner brackets, crosshair with gap, centre diamond, range ticks
    'reticle': [*[('L', p, 50) for p in ([(80, 300), (80, 80), (300, 80)], [(700, 80), (920, 80), (920, 300)],
                                          [(80, 700), (80, 920), (300, 920)], [(700, 920), (920, 920), (920, 700)])],
                ('L', [(500, 140), (500, 400)], 40), ('L', [(500, 600), (500, 860)], 40),
                ('L', [(140, 500), (400, 500)], 40), ('L', [(600, 500), (860, 500)], 40),
                ('F', [(500, 420), (580, 500), (500, 580), (420, 500)]),
                ('O', (300, 300, 700, 700), 30), *[('L', [(x, 470), (x, 530)], 24) for x in (200, 300, 700, 800)]],
    # Tibanna gas canister: domed cylinder, valve, bands, gauge window
    'tibanna': [('F', rect(300, 220, 700, 880)), ('E', (300, 140, 700, 300)), ('E', (300, 800, 700, 960)),
                ('F', rect(450, 50, 550, 160)), ('L', [(370, 80), (630, 80)], 34),
                ('CL', [(300, 330), (700, 330)], 22), ('CL', [(300, 770), (700, 770)], 22),
                ('C', rect(410, 420, 590, 680)), ('F', rect(455, 520, 545, 680)), ('CL', [(410, 520), (590, 520)], 10)],
    # twin AA turbolaser turret
    'aa_turret': [('F', [(140, 960), (860, 960), (760, 760), (240, 760)]), ('E', (290, 540, 710, 860)),
                  ('L', [(430, 640), (230, 90)], 60), ('L', [(570, 640), (770, 90)], 60),
                  ('L', [(390, 520), (330, 360)], 95), ('L', [(610, 520), (670, 360)], 95),
                  ('CL', [(200, 870), (800, 870)], 18), ('CE', (440, 640, 560, 760)), ('E', (470, 670, 530, 730))],
    # sensor dish: parabolic dish, feed horn, mount, base
    'sensor_dish': [('E', (120, 120, 820, 820)), ('CE', (220, 20, 920, 720)), ('L', [(450, 560), (700, 310)], 26),
                    ('E', (650, 260, 750, 360)), ('L', [(420, 660), (400, 880)], 70), ('F', rect(230, 870, 590, 960)),
                    ('A', (600, 60, 960, 420), 270, 360, 26), ('A', (520, 0, 1000, 480), 280, 350, 22)],
    # credit chips: three offset chits with notches and centre seal
    'credit_chips': [*[op for dx, dy in ((0, 0), (90, 110), (180, 220)) for op in (
                         ('F', [(100 + dx, 200 + dy), (640 + dx, 200 + dy), (700 + dx, 260 + dy), (700 + dx, 520 + dy), (160 + dx, 520 + dy), (100 + dx, 460 + dy)]),
                         ('CO', (330 + dx, 260 + dy, 470 + dx, 400 + dy), 16), ('CL', [(160 + dx, 470 + dy), (640 + dx, 470 + dy)], 14),
                         ('CL', [(100 + dx, 200 + dy), (700 + dx, 260 + dy)], 6))]],
    # space mine: core with spikes and a band
    'space_mine': [('E', (250, 250, 750, 750)),
                   *[('L', [(500 + 240 * c, 500 + 240 * s), (500 + 470 * c, 500 + 470 * s)], 55)
                     for c, s in ((1, 0), (-1, 0), (0, 1), (0, -1), (.707, .707), (-.707, .707), (.707, -.707), (-.707, -.707))],
                   *[('E', (500 + 470 * c - 45, 500 + 470 * s - 45, 500 + 470 * c + 45, 500 + 470 * s + 45))
                     for c, s in ((1, 0), (-1, 0), (0, 1), (0, -1))],
                   ('CL', [(260, 500), (740, 500)], 24), ('CE', (430, 330, 570, 470)), ('E', (460, 360, 540, 440))],
    # proton torpedo (drawn upright, shown rotated): capsule body, glowing warhead, fins
    'proton_torpedo': [('F', rect(410, 300, 590, 820)), ('E', (380, 80, 620, 320)), ('CO', (400, 100, 600, 300), 26),
                       ('F', [(410, 700), (300, 900), (410, 860)]), ('F', [(590, 700), (700, 900), (590, 860)]),
                       ('CL', [(410, 420), (590, 420)], 18), ('CL', [(410, 720), (590, 720)], 18), ('F', rect(450, 820, 550, 920))],
    # kyber crystal: faceted hexagonal prism
    'kyber': [('F', [(500, 30), (720, 260), (680, 790), (500, 970), (320, 790), (280, 260)]),
              ('CL', [(500, 30), (500, 970)], 20), ('CL', [(280, 260), (500, 360), (720, 260)], 18),
              ('CL', [(320, 790), (500, 700), (680, 790)], 18), ('CL', [(500, 360), (500, 700)], 10)],
    # thermal detonator: sphere, equator band, arming panel with buttons, stud
    'thermal_detonator': [('E', (140, 160, 860, 880)), ('CL', [(140, 470), (860, 470)], 26), ('CL', [(140, 570), (860, 570)], 26),
                          ('C', rect(370, 400, 630, 640)), *[('F', rect(x, 470, x + 50, 570)) for x in (400, 475, 550)],
                          ('F', rect(450, 90, 550, 170)), ('CA', (200, 220, 800, 820), 200, 250, 30)],
    # BARC speeder, side, bow right: long body, front prongs, handlebars, seat, rear engine
    'barc': [('F', [(80, 520), (300, 440), (760, 450), (900, 500), (760, 560), (300, 600)]),
             ('F', [(760, 450), (980, 470), (980, 490), (780, 490)]), ('F', [(760, 540), (980, 520), (980, 540), (780, 560)]),
             ('L', [(560, 450), (640, 330)], 34), ('L', [(600, 330), (700, 330)], 30), ('F', [(330, 440), (480, 440), (450, 390), (350, 390)]),
             ('F', rect(40, 470, 200, 600)), ('CE', (70, 500, 160, 580)), ('CL', [(220, 540), (740, 520)], 16)],
    # bacta tank: glass cylinder with patient, bubbles, base and cap
    'bacta_tank': [('F', rect(270, 160, 730, 880)), ('C', rect(330, 220, 670, 820)),
                   ('E', (460, 280, 540, 360)), ('F', rect(450, 370, 550, 620)), ('L', [(470, 620), (460, 790)], 34), ('L', [(530, 620), (540, 790)], 34),
                   ('L', [(450, 400), (390, 560)], 28), ('L', [(550, 400), (610, 560)], 28),
                   *[('E', (x, y, x + 36, y + 36)) for x, y in ((360, 700), (620, 520), (370, 420), (610, 300))],
                   ('F', rect(200, 860, 800, 960)), ('F', rect(230, 90, 770, 180)), ('C', rect(260, 120, 740, 140))],
}

# subject -> (source file in logos/, mask mode, rotation) or a DRAWN/PICTO key
SOURCES = {
    'republic': ('Republic_Emblem', ('dark', 128)), 'cis': ('CIS_Flag', ('lum', 128)),
    'senate': ('Senate_seal', 'alpha'), 'politics': ('Senate_seal', 'alpha'),
    'jedi': ('Jedi_Order', 'alpha'),
    'trooper': ('hw_Phase_I_clone_trooper_armor', ('cut', 0, 70)), 'people': ('hw_Phase_I_clone_trooper_armor', ('cut', 0, 70)),
    'droid': ('hw_B1_battle_droid', ('cut', 0, 0)),
    'blaster': ('hw_DC-15A_blaster_rifle', ('cut', 0, 40), 35),
    'tension': 'exploded_planet', 'capital': 'star_destroyer', 'transport': 'yt1300', 'superweapon': 'death_star', 'factory': 'conveyor',
    'comm': 'comlink', 'sabers': 'sabers', 'rank': 'rank_plaque', 'eye': 'probe_droid', 'accord': 'consular',
    'map': 'galaxy', 'planet': 'ringed_planet', 'drop': 'laat', 'dropship': 'laat', 'shield': 'shield_dome',
    'holocron': 'holocron', 'bomber': 'ywing', 'fighter': 'incom', 'walker': 'atte',
    'artillery': 'spha', 'cannon': 'av7', 'wrench': 'hydrospanner', 'missile': 'missile@-45', 'engine': 'ion_engine',
    'crate': 'cargo', 'station': 'orbital_station', 'chart': 'holochart', 'binoculars': 'macrobinoculars',
    'target': 'reticle', 'fuel': 'tibanna', 'antiair': 'aa_turret', 'radar': 'sensor_dish', 'credits': 'credit_chips',
    'mine': 'space_mine', 'carrier': 'kdy', 'torpedo': 'proton_torpedo@-60', 'crystal': 'kyber', 'bomb': 'thermal_detonator',
    'speeder': 'barc', 'medic': 'bacta_tank', 'milfactory': 'conveyor',
}

# domain colours for the normal state (hover / selected stays gold, disabled grey)
PALETTE = {
    'army': (0, 176, 240), 'space': (135, 145, 255), 'air': (40, 225, 180), 'industry': (255, 145, 35),
    'politics': (215, 225, 240), 'danger': (240, 75, 60), 'science': (185, 115, 255), 'life': (85, 215, 105),
    'military': (70, 150, 75),   # military factories: dark green
}
DOMAIN = {
    'army': 'trooper people droid blaster walker sabers artillery cannon antiair parachute mountain speeder drop dropship '
            'armor legs shield tank',
    'space': 'capital carrier transport station torpedo mine stealth shipyard engine hyperspace',
    'air': 'fighter bomber interceptor',
    'industry': 'factory construction wrench crate fuel crystal cog credits chart',
    'politics': 'senate politics republic cis accord banner flag crown rank star comm person home',
    'danger': 'eye skull handcuffs bomb superweapon tension target missile fist',
    'science': 'holocron radar binoculars lightning map planet moon clock',
    'life': 'medic heart jedi',
    'military': 'milfactory',
}
COLOUR = {s: PALETTE[d] for d, subs in DOMAIN.items() for s in subs.split()}

def colour(subject, default=(0, 176, 240)):
    return COLOUR.get(subject, default)

@lru_cache(None)
def _source(name):
    """-> (file stem in logos/, mode, rot) for a subject, writing drawn shapes to logos/drawn_*.png once."""
    src = SOURCES[name]
    if isinstance(src, tuple):
        return src[0], src[1], (src[2] if len(src) > 2 else 0)
    src, _, rot = src.partition('@')                   # 'missile@-45': drawn upright, shown rotated
    ops = DRAWN.get(src) or PICTO[src]['ops']
    m = draw_ops(ops)
    im = Image.new('RGBA', m.size, (255, 255, 255, 0)); im.putalpha(m)
    im.save(os.path.join(LOGOS, f'drawn_{src}.png'))
    return f'drawn_{src}', 'alpha', int(rot) if rot else (PICTO[src]['rot'] if src in PICTO else 0)

def coverage(name, w, h, pad=0.0):
    """'L' coverage w x h, like hod_vector.render, or None if the library has no canon source for this subject."""
    if name not in SOURCES or w < 4 or h < 4:
        return None
    stem, mode, rot = _source(name)
    p = max(0, round(min(w, h) * pad / 2))
    return mask_of(stem, ('lum', 0) if mode == 'alpha' else mode, size=(w, h), pad=p, rot=rot)

if __name__ == '__main__':
    from cwic_icons import render, CYAN
    names = list(SOURCES)
    cell = 64 + 32 + 20 + 40
    sheet = Image.new('RGBA', (cell * 6, 80 * ((len(names) + 5) // 6)), (0, 1, 22, 255))
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        x, y = (i % 6) * cell, (i // 6) * 80
        for s in (64, 32, 20):
            m = coverage(n, s, s, 0.1); assert m.getbbox(), n
            sheet.alpha_composite(render(m, CYAN), (x, y + 12)); x += s + 6
        d.text(((i % 6) * cell, y), n, fill=(240, 192, 32))
    sheet.save(os.path.join(D, 'library_review.png')); print('ok', len(names))
