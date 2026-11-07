"""Topbar stat icons from canon SW emblems, CWIC style (domain colour, shadow, glow), at the vanilla sizes.
  python -B topbar_icons.py            preview sheet -> topbar_review.png (vanilla next to new, 1x and 4x)
  python -B topbar_icons.py --install  writes the DDS overrides into gfx/interface (undo: delete them, files are new)"""
import os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from cwic_icons import render, GOLD
from logo_icons import mask_of

D = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(D, '..', '..')
VANILLA = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
# target texture -> (logo, mask mode, crop)
ICONS = {
    'gfx/interface/pol_power_icon.dds': ('Senate_seal', 'alpha', None),
    'gfx/interface/stability_icon.dds': ('Jedi_Order', 'alpha', None),
    # canon hardware cutouts (Wookieepedia infobox renders): ('cut', bg lum, detail-cut lum)
    'gfx/interface/manpower_icon.dds': ('hw_Phase_I_clone_trooper_armor', ('cut', 0, 70), None),
    'gfx/interface/war_support_icon.dds': ('hw_DC-15A_blaster_rifle', ('cut', 0, 40), None, 35),
    'gfx/interface/ships_icon.dds': ('star_destroyer', 'alpha', None),
    'gfx/interface/topbar/topbar_convoys.dds': ('yt1300', 'alpha', None),
    'gfx/interface/topbar/nuke_icon.dds': ('death_star', 'alpha', None),
    # nothing canon fits: Aurebesh abbreviation (UNI)
    'gfx/interface/industrial_capacity_icon.dds': ('conveyor', 'alpha', None),
    'gfx/interface/command_power_icon.dds': ('comlink', 'alpha', None, -20),
    'gfx/interface/world_tension_icon.dds': ('exploded_planet', 'alpha', None),
    'gfx/interface/unity_icon.dds': (('Usk', 'Nern', 'Isk'), 'alpha', None),
}

LOGOS = os.path.join(D, 'logos')

def aurebesh_word(letters):
    """Glue Aurebesh letter renders side by side (same height) -> logos/aurebesh_word_<letters>.png."""
    ims = [Image.open(os.path.join(LOGOS, f'aurebesh_{l}.png')).convert('RGBA') for l in letters]
    ims = [im.crop(im.getchannel('A').getbbox()) for im in ims]
    h = max(im.height for im in ims); ims = [im.resize((round(im.width * h / im.height), h)) for im in ims]
    gap = h // 5
    out = Image.new('RGBA', (sum(im.width for im in ims) + gap * (len(ims) - 1), h), (0, 0, 0, 0)); x = 0
    for im in ims: out.alpha_composite(im, (x, 0)); x += im.width + gap
    name = 'aurebesh_word_' + ''.join(letters); out.save(os.path.join(LOGOS, name + '.png')); return name

from cwic_library import DRAWN, PALETTE

# each stat in its domain colour (same palette as the interface icons)
DOMAIN_OF = {'gfx/interface/pol_power_icon.dds': 'politics', 'gfx/interface/stability_icon.dds': 'life',
             'gfx/interface/manpower_icon.dds': 'army', 'gfx/interface/war_support_icon.dds': 'danger',
             'gfx/interface/ships_icon.dds': 'space', 'gfx/interface/topbar/topbar_convoys.dds': 'space',
             'gfx/interface/topbar/nuke_icon.dds': 'danger', 'gfx/interface/industrial_capacity_icon.dds': 'industry',
             'gfx/interface/command_power_icon.dds': 'politics', 'gfx/interface/world_tension_icon.dds': 'danger',
             'gfx/interface/unity_icon.dds': 'politics'}

def drawn(name):
    from cwic_icons import draw_ops
    m = draw_ops(DRAWN[name]); im = Image.new('RGBA', m.size, (255, 255, 255, 0)); im.putalpha(m)
    im.save(os.path.join(LOGOS, f'drawn_{name}.png')); return f'drawn_{name}'

def frames(dst, van):
    """Vanilla strips: industrial_capacity has 2 frames (normal, selected=gold)."""
    return 2 if 'industrial_capacity' in dst else 1

if __name__ == '__main__':
    rows = []
    for dst, (logo, mode, crop, *rot) in ICONS.items():
        van = Image.open(os.path.join(VANILLA, dst)).convert('RGBA')
        if isinstance(logo, tuple): logo = aurebesh_word(logo)
        elif logo in DRAWN: logo = drawn(logo)
        n = frames(dst, van); fw = van.width // n
        m = mask_of(logo, ('lum', 0) if mode == 'alpha' else mode, size=(fw, van.height), pad=1, crop=crop, rot=rot[0] if rot else 0)
        assert m.getbbox(), logo
        new = Image.new('RGBA', van.size, (0, 0, 0, 0))
        for i, col in enumerate((PALETTE[DOMAIN_OF[dst]], GOLD)[:n]): new.alpha_composite(render(m, col), (i * fw, 0))
        if '--install' in sys.argv:
            new.save(os.path.join(MOD, dst))
        rows.append((van, new))
    sheet = Image.new('RGBA', (2 * 70 * 5 + 60, 140 * len(rows)), (0, 1, 22, 255))
    for r, (van, new) in enumerate(rows):
        x, y = 0, r * 140
        for im, k in ((van, 1), (new, 1), (van, 4), (new, 4)):
            sheet.alpha_composite(im.resize((im.width * k, im.height * k), Image.NEAREST), (x, y)); x += im.width * k + 12
    sheet.save(os.path.join(D, 'topbar_review.png')); print('ok', len(rows))
