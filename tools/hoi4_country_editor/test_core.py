"""Self-check on a tiny fake mod: python test_core.py"""
import os
import tempfile

import random

from hoi4_country_editor import (Mod, REQUIRED, ROLES, add_character, block_text, character_text, get, make_flag,
                                 parse, read_text, save_flag, save_portrait, set_loc, set_top, suggest_names)

FILES = {
    'common/country_tags/t.txt': 'AAA = "countries/A.txt"\n',
    'common/countries/A.txt': 'graphical_culture = x\ncolor = rgb { 1 2 3 }\n',
    'common/ideologies/i.txt': 'ideologies = { good = { types = { good_sub = {} } } bad = { types = { bad_sub = {} } } }',
    'common/ideologies/backup/old.txt': 'ideologies = { ghost = { types = { ghost_sub = {} } } }',
    'common/characters/A.txt': 'characters = { AAA_bob = { name = "Bob" country_leader = { ideology = good_sub } } }',
    'history/states/1-x.txt': 'state = { id = 1 name = "STATE_1" provinces = { 5 6 } history = { owner = AAA add_core_of = BBB } }',
    'history/countries/AAA - A.txt': ('capital = 1 # comment\noob = "aaa_oob"\nrecruit_character = AAA_bob\n'
                                      'set_popularities = { good = 70 bad = 20 }\nset_politics = { ruling_party = good }\n'),
    'history/units/AAA_OOB.txt': ('division_template = { name = "Inf" }\n'
                                  'units = { division = { division_template = "Inf" } division = { division_template = "Tank" } }'),
    'gfx/flags/AAA.tga': '',
    'localisation/english/a_l_english.yml': '﻿l_english:\n AAA:0 "Aland"\n AAA_DEF:0 "Aland" # c\n',
}

with tempfile.TemporaryDirectory() as d:
    for rel, body in FILES.items():
        os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
        with open(os.path.join(d, rel), 'w', encoding='utf-8') as f:
            f.write(body)
    mod = Mod(d)
    assert list(mod.ideologies) == ['good', 'bad'], mod.ideologies  # backup/ subfolder ignored like the game does
    c = mod.country('AAA')
    missing = {t for lvl, _, t in c.missing if lvl == REQUIRED}
    assert c.name() == 'Aland'
    assert 'Popularities sum to 100 (now 90)' in missing
    assert 'Localisation key AAA_ADJ' in missing and 'Localisation key AAA_DEF' not in missing
    assert 'Flag gfx/flags/medium/AAA.tga' in missing and 'Flag gfx/flags/AAA.tga' not in missing
    assert 'Division template "Tank" is defined in its OOB' in missing  # case-insensitive oob lookup worked
    assert 'Country leader for the ruling party (good)' not in missing
    assert c.ideo_rows['good']['leader'] == 'AAA_bob'
    assert 'Leader for bad (has popularity)' in {t for _, _, t in c.missing}
    assert mod.color['AAA'] == (1, 2, 3) and mod.prov_state['6'] == '1' and mod.state_count['AAA'] == 1
    assert mod.state_colors('cores', 'BBB')['1'] == (210, 40, 40)

    # editing keeps comments and other lines, replaces blocks, appends missing keys
    hist = read_text(os.path.join(d, 'history/countries/AAA - A.txt'))
    hist = set_top(hist, 'capital', '7')
    hist = set_top(hist, 'set_popularities', block_text([('good', '60'), ('bad', '40')]))
    hist = set_top(hist, 'set_stability', '0.5')
    items = parse(hist)
    assert '# comment' in hist and get(items, 'capital') == '7' and get(items, 'set_stability') == '0.5'
    assert get(items, 'set_popularities') == [('good', '60'), ('bad', '40')] and len(items) == 6
    assert parse(set_top('color = rgb { 1 2 3 }\nx = 1', 'color', 'rgb { 4 5 6 }'))[0][1] == [('', 'rgb'), ('', '4'), ('', '5'), ('', '6')]

    loc = os.path.join(d, 'localisation/english/a_l_english.yml')
    set_loc(mod, 'AAA_DEF', 'the Aland', loc)
    set_loc(mod, 'AAA_ADJ', 'Alandic', loc)
    set_loc(mod, 'AAA', '', loc)
    mod.reload()
    assert mod.loc.get('AAA_DEF') == 'the Aland' and mod.loc.get('AAA_ADJ') == 'Alandic' and 'AAA' not in mod.loc
    assert open(loc, 'rb').read().startswith(b'\xef\xbb\xbf')

    # add leaders of every role: valid script, recruited in history, readable by the checker
    from PIL import Image
    Image.new('RGB', (300, 300), (9, 9, 9)).save(os.path.join(d, 'face.png'))
    pic = save_portrait(mod, 'AAA', 'AAA_ann', os.path.join(d, 'face.png'))
    for i, role in enumerate(ROLES):
        add_character(mod, 'AAA', f'AAA_new{i}', character_text('AAA', f'AAA_new{i}', 'New', role, 'bad_sub', 't1', pic))
        mod.reload()
    c = mod.country('AAA')
    assert [x[0] for x in c.leaders][-5:] == [f'AAA_new{i}' for i in range(5)]
    assert c.ideo_rows['bad']['leader'] == 'AAA_new0' and all(x[4] == pic for x in c.leaders[-5:])
    assert Image.open(mod.path(pic)).size == (156, 210)

    flag = make_flag('three horizontal', [(255, 0, 0), (0, 255, 0), (0, 0, 255)], Image.new('RGBA', (10, 10), 'white'))
    save_flag(mod, 'AAA_bad', flag)
    mod.reload()
    assert mod.country('AAA').ideo_rows['bad']['flag'] == 'AAA_bad.tga'
    assert Image.open(mod.path('gfx/flags/small/AAA_bad.tga')).size == (10, 7)

    n, long, adj, party = suggest_names('corist', 'Aland', 'Alandic', random.Random(1))
    assert n and long and adj == 'Alandic' and party and suggest_names('nope', 'Aland', '', random.Random(1))[0]

assert parse('a = { b = "x y" c >= 2 { 1 2 } }') == [('a', [('b', 'x y'), ('c', '2'), ('', [('', '1'), ('', '2')])])]
print('ok')
