"""Faction and intelligence-agency logos -> canon Star Wars organisation emblems, CWIC style, at the vanilla sizes.
  python -B emblem_icons.py            preview -> emblem_review.png
  python -B emblem_icons.py --install  writes the overrides into gfx/interface (all new files: undo = delete them)"""
import os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cwic_icons import render, CYAN, GOLD
from logo_icons import mask_of

D = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(D, '..', '..')
VANILLA = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
# emblem -> mask mode (black/white emblems keep the black parts)
EMBLEMS = {
    'Republic_Emblem': ('dark', 128), 'CIS_Flag': ('lum', 128), 'org_Trade_Federation': ('dark', 128),
    'org_Commerce_Guild': 'alpha', 'org_Mandalorian_Guard': ('dark', 128), 'org_Mando_serpent': 'alpha',
    'org_Blacksun': ('dark', 100), 'org_Pyke_syndicate': 'alpha', 'org_Desilijic_clan_vector': 'alpha',
    'org_Crimson_dawn': 'alpha', 'org_Shadow_Collective_-_insignia': ('dark', 128), 'org_Sith_Emblem': ('dark', 100),
    'org_Nightsisters_symbol_-_JFO': ('dark', 128), 'org_Oldrepublic_crest': 'alpha', 'org_High_Republic_symbol': 'alpha',
    'org_Kamino_Security_emblem': ('dark', 128), 'org_Mining_Guild': ('dark', 128), 'org_Senateglasswheel': ('dark', 128),
    'Senate_seal': 'alpha', 'Jedi_Order': 'alpha',
}
F = 'gfx/interface/factions/faction_logos/'
A = 'gfx/interface/operatives/agencies/'
POOL = list(EMBLEMS)[:18]
TARGETS = {F + 'faction_logo_generic.dds': 'Republic_Emblem', F + 'faction_logo_generic_miniature.dds': 'Republic_Emblem',
           F + 'faction_icon_allies.dds': 'Republic_Emblem', F + 'faction_logo_generic_democratic.dds': 'Senate_seal',
           F + 'faction_logo_generic_democratic_miniature.dds': 'Senate_seal', F + 'faction_logo_generic_fascist.dds': 'org_Sith_Emblem'}
TARGETS.update({F + f'faction_logo_generic_{i}.dds': POOL[i - 1] for i in range(2, 19)})
TARGETS.update({F + f'faction_logo_generic_{i}_miniature.dds': POOL[i - 1] for i in range(2, 19) if i != 16})
TARGETS.update({F + 'faction_logo_generic_16_miniatur.dds': POOL[15], F + 'faction_logo_generic_fascist_miniature.dds': 'org_Sith_Emblem',
                F + 'faction_icon_allies_miniature.dds': 'Republic_Emblem'})
AGENCY = ['org_Blacksun', 'org_Pyke_syndicate', 'org_Crimson_dawn', 'org_Shadow_Collective_-_insignia', 'org_Nightsisters_symbol_-_JFO',
          'org_Kamino_Security_emblem', 'org_Senateglasswheel', 'Jedi_Order', 'org_Mando_serpent']
TARGETS.update({A + f'agency_logo_generic_{i}.dds': AGENCY[i - 1] for i in range(1, 10)})
TARGETS.update({A + 'agency_logo_bel.dds': 'org_Mandalorian_Guard', A + 'agency_logo_prc.dds': 'org_Sith_Emblem'})

def frames():
    """texture -> noOfFrames from the vanilla .gfx (logos are 2-frame: normal / highlighted)."""
    sys.path.insert(0, os.path.join(D, '..'))
    import hod_ui
    return {k: v[0] for k, v in hod_ui.vanilla_sprites().items()}

if __name__ == '__main__':
    nf = frames()
    tiles = []
    for dst, emb in TARGETS.items():
        src = os.path.join(VANILLA, dst)
        if not os.path.exists(src):
            continue
        van = Image.open(src).convert('RGBA')
        mode = EMBLEMS[emb]
        n = nf.get(dst.lower(), 1); fw = van.width // n
        m = mask_of(emb, ('lum', 0) if mode == 'alpha' else mode, size=(fw, van.height), pad=max(1, min(fw, van.height) // 16))
        assert m.getbbox(), emb
        new = Image.new('RGBA', van.size, (0, 0, 0, 0))
        for k, col in enumerate((CYAN, GOLD)[:n]):        # frame 2 = highlighted -> gold
            new.alpha_composite(render(m, col), (k * fw, 0))
        if '--install' in sys.argv:
            os.makedirs(os.path.dirname(os.path.join(MOD, dst)), exist_ok=True)
            new.save(os.path.join(MOD, dst))
        tiles.append((van, new))
    cell = 120
    sheet = Image.new('RGBA', (cell * 2 * 6, cell * ((len(tiles) + 5) // 6)), (0, 1, 22, 255))
    for i, (van, new) in enumerate(tiles):
        for k, im in enumerate((van, new)):
            im = im.copy(); im.thumbnail((cell - 8, cell - 8))
            sheet.alpha_composite(im, ((i % 6) * cell * 2 + k * cell, (i // 6) * cell))
    sheet.save(os.path.join(D, 'emblem_review.png')); print('ok', len(tiles))
