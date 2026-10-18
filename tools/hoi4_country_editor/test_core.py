"""Self-check on a tiny fake mod: python test_core.py"""
import os
import tempfile

from hoi4_country_editor import Mod, REQUIRED, parse

FILES = {
    'common/country_tags/t.txt': 'AAA = "countries/A.txt"\n',
    'common/countries/A.txt': 'graphical_culture = x\ncolor = rgb { 1 2 3 }\n',
    'common/ideologies/i.txt': 'ideologies = { good = { types = { good_sub = {} } } bad = { types = { bad_sub = {} } } }',
    'common/ideologies/backup/old.txt': 'ideologies = { ghost = { types = { ghost_sub = {} } } }',
    'common/characters/A.txt': 'characters = { AAA_bob = { name = "Bob" country_leader = { ideology = good_sub } } }',
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

assert parse('a = { b = "x y" c >= 2 { 1 2 } }') == [('a', [('b', 'x y'), ('c', '2'), ('', [('', '1'), ('', '2')])])]
print('ok')
