"""Self-check for the focus tree editor on a tiny fake mod: python test_focus.py"""
import os
import tempfile

from hoi4_country_editor import Mod, read_text, write_text
from hoi4_focus_editor import (FocusFile, add_auto_names, auto_name, brace_depth, brace_problem, check, earliest_days,
                               engine_date, fmt_days, focus_point_days, hod_calendar, hod_date, import_icon,
                               playthroughs, tree_text)

TREE = '''# my tree
focus_tree = {
	id = AAA_tree
	country = { factor = 0 modifier = { add = 10 tag = AAA } }
	focus = {
		id = AAA_a # start
		icon = GFX_a
		cost = 10
		x = 2
		y = 0
	}
	focus = {
		id = AAA_b
		icon = GFX_a
		cost = 10
		relative_position_id = AAA_a
		prerequisite = { focus = AAA_a }
		mutually_exclusive = { focus = AAA_c }
		x = -1
		y = 1
	}
	focus = {
		id = AAA_c
		cost = 10
		prerequisite = { focus = AAA_a }
		prerequisite = { focus = AAA_ghost }
		x = 3
		y = 1
	}
}
'''

with tempfile.TemporaryDirectory() as d:
    files = {'common/national_focus/t.txt': TREE, 'common/national_focus/other.txt': tree_text('X', 'BBB', 'AAA_c'),
             'common/defines/x.lua': '-- NDefines.NFocus.FOCUS_POINT_DAYS = 9\nNDefines.NFocus.FOCUS_POINT_DAYS = 5\n',
             'interface/g.gfx': 'spriteTypes = { spriteType = { name = "GFX_a" texturefile = "gfx/a.dds" } }',
             'localisation/english/f_l_english.yml': '﻿l_english:\n AAA_a:0 "A"\n AAA_a_desc:0 "broken\n'}
    for rel, body in files.items():
        os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
        write_text(os.path.join(d, rel), body)
    mod = Mod(d)
    ff = FocusFile(os.path.join(d, 'common/national_focus/t.txt'))
    assert list(ff.focuses) == ['AAA_a', 'AAA_b', 'AAA_c']
    assert (ff.focuses['AAA_b']['ax'], ff.focuses['AAA_b']['ay']) == (1, 1)  # relative position resolved
    assert ff.focuses['AAA_c']['prereq'] == [['AAA_a'], ['AAA_ghost']]

    probs = {(lvl, fid, msg.split(' (')[0]) for lvl, fid, msg, _ in check(ff, mod)}
    assert ('error', 'AAA_c', 'Prerequisite AAA_ghost does not exist in this file') in probs
    assert ('error', 'AAA_c', 'Focus id AAA_c also exists in other.txt') in probs
    assert ('warning', 'AAA_b', 'Exclusive with AAA_c, but AAA_c does not list it back') in probs
    assert ('error', 'AAA_a', 'Broken description localisation line') in probs
    assert ('warning', 'AAA_c', 'No icon') in probs

    # fixes apply as edits
    for lvl, fid, msg, fix in check(ff, mod):
        if fix:
            fix()
    assert ff.focuses['AAA_c']['prereq'] == [['AAA_a']] and ff.focuses['AAA_c']['mutex'] == ['AAA_b']

    # durations: AAA_b and AAA_c need AAA_a (10 cost each); 1 cost = 5 days from the mod's defines
    per = focus_point_days(mod)
    assert per == 5 and earliest_days(ff, per) == {'AAA_a': 50, 'AAA_b': 100, 'AAA_c': 100}
    assert fmt_days(400) == '400 days (1 y 35 d)' and fmt_days(50) == '50 days'
    # exclusives: B and C exclude each other; D needs B, so taking C also loses D
    ff.add_focus('AAA_d', 5, 3, prereq='AAA_b')
    ff.set_values('AAA_d', {'cost': '30'})
    p = playthroughs(ff, per)
    assert p['all'] == 50 + 50 + 50 + 150 and p['exact']
    assert p['longest'] == 50 + 50 + 150 and p['shortest'] == 50 + 50
    assert p['longest_choice'] == ({'AAA_b'},) and len(p['groups']) == 1
    ff.undo_step()
    ff.undo_step()

    # auto names: tag removed, _ -> space, existing and broken names left alone
    assert auto_name('CIS_The_Raxus_Address') == 'The Raxus Address' and auto_name('REP_we_are') == 'We are'
    loc = os.path.join(d, 'localisation/english/f_l_english.yml')
    assert add_auto_names(ff, mod, loc) == 2  # AAA_b, AAA_c (AAA_a already named)
    mod.reload()
    assert mod.loc['AAA_b'] == 'B' and mod.loc['AAA_a'] == 'A' and add_auto_names(ff, mod, loc) == 0

    # moving a relative focus writes its offset, not its absolute position
    ff.move('AAA_b', 5, 4)
    assert (ff.focuses['AAA_b']['x'], ff.focuses['AAA_b']['ay']) == (3, 4)
    ff.add_focus('AAA_d', 6, 5, prereq='AAA_b')
    ff.set_values('AAA_d', {'prerequisite': ff.prereq_values([['AAA_b', 'AAA_c']])})
    assert ff.focuses['AAA_d']['prereq'] == [['AAA_b', 'AAA_c']]
    ff.duplicate('AAA_d', 'AAA_e')
    assert ff.focuses['AAA_e']['prereq'] == [['AAA_b', 'AAA_c']] and ff.focuses['AAA_e']['ax'] == 7
    ff.rename('AAA_b', 'AAA_bee')
    assert ff.focuses['AAA_d']['prereq'] == [['AAA_bee', 'AAA_c']] and ff.focuses['AAA_c']['mutex'] == ['AAA_bee']
    ff.delete('AAA_a')  # AAA_bee was relative to it: becomes absolute, same place on screen
    assert ff.focuses['AAA_bee']['rel'] is None and (ff.focuses['AAA_bee']['ax'], ff.focuses['AAA_bee']['ay']) == (5, 4)
    assert ff.focuses['AAA_c']['prereq'] == [] and brace_depth(ff.text) == 0
    assert '# my tree' in ff.text  # comments survive
    while ff.undo:
        ff.undo_step()
    assert ff.text == read_text(ff.path) and not ff.dirty

    # icon import: dds + sprite + shine sprite
    from PIL import Image
    Image.new('RGBA', (300, 200), (200, 0, 0, 255)).save(os.path.join(d, 'i.png'))
    name = import_icon(mod, os.path.join(d, 'i.png'), 'AAA_icon', 'AAA')
    mod.reload()
    assert name == 'GFX_AAA_icon' and name in mod.sprites and 'GFX_AAA_icon_shine' in mod.sprites
    assert Image.open(mod.find(mod.sprites[name])).size == (94, 86)
    assert brace_depth(read_text(os.path.join(d, 'interface/g.gfx'))) == 0

    # a new tree from the template is valid and has no errors
    new = FocusFile(os.path.join(d, 'new.txt'), tree_text('CCC_focus', 'CCC', 'CCC_start'))
    assert [p for p in check(new, mod, others={}) if p[0] == 'error'] == []
# a missing } is reported at the focus that lost it, and is the only problem shown
broken = TREE.replace('\t\tx = 2\n\t\ty = 0\n\t}', '\t\tx = 2\n\t\ty = 0\n')
assert brace_problem(TREE) is None
assert brace_problem(broken)[0] == 5, brace_problem(broken)
assert brace_problem(TREE + '}')[1].startswith('Extra')
assert brace_problem(TREE.rstrip()[:-1])[1].startswith('The file ends with 1 block')  # focus_tree not closed at the end
with tempfile.TemporaryDirectory() as d:
    write_text(os.path.join(d, 'x.txt'), broken)
    probs = check(FocusFile(os.path.join(d, 'x.txt')), Mod(d), others={})
    assert len(probs) == 1 and 'line 5' in probs[0][2]
    write_text(os.path.join(d, 'y.txt'), TREE.rstrip()[:-1])
    ff = FocusFile(os.path.join(d, 'y.txt'))
    probs = check(ff, Mod(d), others={})  # like HOI4: loads anyway, warns, and writes the } only on save
    assert len(ff.focuses) == 3 and ff.dirty and not [p for p in probs if 'brace' in p[2] or 'block' in p[2]]
    assert any('without its last' in p[2] for p in probs)
# the mod calendar matches its on_actions counter, simulated day by day exactly as the script does it
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, 'common/on_actions'))
    write_text(os.path.join(d, 'common/on_actions/a.txt'), read_text(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..', 'common', 'on_actions', '00_on_actions.txt')))
    cal = hod_calendar(Mod(d))
    assert cal == {'start_year': -24, 'month_days': 35, 'months': 10, 'fest_days': 19}, cal
    day, month, year, bby = 1, 1, -24, 0
    names = ['Alderensis', 'Corelliensis', 'Coruscensis', 'Durensis', 'Chandrilensis', 'Bentaensis', 'Anaxensis',
             'Kuensis', 'Hosniensis', 'Esselensis', 'Festivities']
    for n in range(369 * 30):
        assert hod_date(n, cal) == f'{day} {names[month - 1]} {year} {"ABY" if bby else "BBY"}', (n, hod_date(n, cal))
        day += 1
        if day == 20 and month == 11:
            day, month, year = 1, 1, year + 1
        if day == 36:
            month, day = month + 1, 1
        if year == 0:
            bby, year = 1, year + 1
assert engine_date(0, '976.1.1.12') == '976.1.1' and engine_date(365, '976.1.1') == '977.1.1'
assert engine_date(59, '976.1.1') == '976.3.1'
print('ok')
