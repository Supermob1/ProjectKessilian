"""Tech-tree folder tabs: navy plate (hod_ui) with the folder's pictogram in its domain colour, CWIC glow + shadow.
Frame 1 = active tab (gold border, full colour), frame 2 = idle (cyan border, dimmed glyph); large doctrine tabs
carry the glyph on the left like vanilla.
  python -B tab_icons.py            preview -> tab_review.png
  python -B tab_icons.py --install  writes gfx/interface/techtree/*.dds (hod_ui / hod_icons skip these: TABS)"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D); sys.path.insert(0, os.path.join(D, '..'))
from cwic_library import coverage, colour
from cwic_icons import render
import hod_ui

MOD = os.path.join(D, '..', '..')
T = 'gfx/interface/techtree/'
REPUBLIC, CIS = (235, 70, 55), (95, 145, 255)
TABS = {   # texture -> (subject, colour or None = domain colour)
    'techtree_infantry_tab.dds': ('trooper', None), 'techtree_clone_tab.dds': ('republic', REPUBLIC),
    'techtree_droid_tab.dds': ('cis', CIS), 'techtree_support_tab.dds': ('wrench', None),
    'techtree_tank_tab.dds': ('walker', None), 'techtree_artillery_tab.dds': ('artillery', None),
    'techtree_naval_tab.dds': ('capital', None), 'techtree_naval_support_tab.dds': ('torpedo', None),
    'techtree_air_tab.dds': ('fighter', None), 'techtree_engineering_tab.dds': ('radar', None),
    'techtree_industry_tab.dds': ('factory', None), 'techtree_special_tab.dds': ('superweapon', None),
    'techtree_landdoctrine_tab.dds': ('sabers', None), 'techtree_navaldoctrine_tab.dds': ('capital', None),
    'techtree_airdoctrine_tab.dds': ('bomber', None),
    'techtree_landdoctrine_tab_large.dds': ('trooper', None), 'techtree_airdoctrine_tab_large.dds': ('fighter', None),
    'techtree_navaldoctrine_tab_large.dds': ('capital', None), 'techtree_specialforcesdoctrine_tab_large.dds': ('drop', None),
    # SW Executor tree tabs (2026-11-07): their grey vanilla-style plates -> house style
    'techtree_swinfantry_tab.dds': ('trooper', None), 'techtree_swsupport_tab.dds': ('wrench', None),
    'techtree_swarmour_tab.dds': ('walker', None), 'techtree_swartillery_tab.dds': ('artillery', None),
    'techtree_swair_tab.dds': ('fighter', None), 'techtree_imperial_tab.dds': ('superweapon', None),
}
SW_TABS = {'techtree_swinfantry_tab.dds', 'techtree_swsupport_tab.dds', 'techtree_swarmour_tab.dds',
           'techtree_swartillery_tab.dds', 'techtree_swair_tab.dds', 'techtree_imperial_tab.dds'}
TABS = {T + k: v for k, v in TABS.items()}


def source(path):
    """Vanilla texture for the size / silhouette; the mod's own clone / droid tabs have none."""
    p = hod_ui.find(hod_ui.VANILLA, path)
    if path in (T + 'techtree_clone_tab.dds', T + 'techtree_droid_tab.dds') or os.path.basename(path) in SW_TABS or not p:
        keep = os.path.join(D, 'tab_originals', os.path.basename(path) + '.orig.png')
        if not os.path.exists(keep):                   # first run: keep the mod's original art
            Image.open(os.path.join(MOD, path)).save(keep)
        p = keep
    return np.array(Image.open(p).convert('RGBA'))


def tab(px, subject, col, active):
    h, w = px.shape[:2]
    flat = px.copy(); flat[..., :3] = 0                # silhouette only: vanilla bolts / bevels would trace as lines
    out = hod_ui.draw(flat, None, 1 if active else 0)
    m = out[..., 3] > 0
    ys, xs = np.where(m)
    bh = np.ptp(ys) + 1
    g = int(bh * 0.72)
    large = w > 2.5 * h
    gw = int(g * 1.6) if not large else int(g * 1.4)
    cx = xs.min() + (g if large else (np.ptp(xs) + 1) // 2)
    cy = ys.min() + bh // 2
    mask = coverage(subject, gw, g, 0.05)
    c = col if active else tuple(int(v * 0.62) for v in col)
    glyph = render(mask, c)
    im = Image.fromarray(out)
    im.alpha_composite(glyph, (int(cx - glyph.width / 2), int(cy - glyph.height / 2)))
    return np.array(im)


def build(path):
    subject, col = TABS[path]
    col = col or colour(subject)
    px = source(path)
    fw = px.shape[1] // 2
    return px, np.hstack([tab(px[:, k * fw:(k + 1) * fw], subject, col, k == 0) for k in range(2)])


if __name__ == '__main__':
    rows = [(p, *build(p)) for p in TABS]
    if '--install' in sys.argv:
        for p, _, new in rows:
            Image.fromarray(new).save(os.path.join(MOD, p))
    sheet = Image.new('RGBA', (1100, 70 * len(rows)), (40, 40, 40, 255)); d = ImageDraw.Draw(sheet)
    for i, (p, van, new) in enumerate(rows):
        y = i * 70; d.text((0, y), os.path.basename(p), fill=(255, 230, 0))
        sheet.alpha_composite(Image.fromarray(van), (0, y + 8)); sheet.alpha_composite(Image.fromarray(new), (530, y + 8))
    sheet.save(os.path.join(D, 'tab_review.png')); print('ok', len(rows))
