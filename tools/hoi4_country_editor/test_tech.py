"""Self-check of the tech editor on a tiny fake mod: python test_tech.py"""
import os
import tempfile

from hoi4_country_editor import Mod, read_text
from hoi4_tech_editor import (TechFile, add_auto_names, brace_problem, check, earliest_days, research_days, tech_blocks,
                              tech_point_days, tech_tags)

TECH = '''technologies = {
	@960 = 0
	@970 = 3
	@980 = 6

	# the first rifle
	rifle_1 = {
		path = {
			leads_to_tech = rifle_2
			research_cost_coeff = 1
		}
		research_cost = 1.5
		start_year = 960
		folder = {
			name = army_folder
			position = { x = 0 y = @960 }
		}
		categories = { infantry_weapons }
	}

	rifle_2 = {
		research_cost = 2
		start_year = 970
		folder = {
			name = army_folder
			position = { x = 0 y = @970 }
		}
		xor = { carbine }
	}

	carbine = {
		path = {
			research_cost_coeff = 1
		}
		research_cost = 1
		folder = {
			name = nowhere_folder
			position = { x = 2 y = @970 }
		}
	}
}
'''
FILES = {
    'common/technologies/army.txt': TECH,
    'common/technology_tags/tags.txt': 'technology_categories = { infantry_weapons }\n'
                                       'technology_folders = { army_folder = { ledger = army } }\n',
    'common/defines/d.lua': 'NDefines.NTechnology.BASE_TECH_COST = 80\n',
    'localisation/english/t_l_english.yml': '﻿l_english:\n rifle_1:0 "Rifle"\n rifle_1_desc:0 "A rifle"\n',
}

with tempfile.TemporaryDirectory() as d:
    for rel, body in FILES.items():
        os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
        with open(os.path.join(d, rel), 'w', encoding='utf-8') as f:
            f.write(body)
    mod = Mod(d)
    path = os.path.join(d, 'common/technologies/army.txt')
    tf = TechFile(path)
    assert [b[0] for b in tech_blocks(tf.text)] == ['rifle_1', 'rifle_2', 'carbine']
    r1, r2 = tf.focuses['rifle_1'], tf.focuses['rifle_2']
    assert (r1['folder'], r1['y'], r2['y'], r1['leads'], r2['from']) == ('army_folder', 0, 3, [('rifle_2', '1')], ['rifle_1'])
    assert r1['cats'] == ['infantry_weapons'] and r2['xor'] == ['carbine'] and r1['icon'] == 'GFX_rifle_1_medium'

    # research time: BASE_TECH_COST from the mod's defines, earliest = own time + quickest incoming line
    per = tech_point_days(mod)
    assert per == 80 and research_days(r2, per) == 160 and earliest_days(tf, per)['rifle_2'] == 120 + 160

    # checks: empty path, unknown folder, missing names, xor listed one way, all with the right tech
    folders, cats = tech_tags(mod)
    assert folders == {'army_folder'} and cats == {'infantry_weapons'}
    probs = {(tid, msg.split(',')[0].split(' (')[0]) for _, tid, msg, _ in check(tf, mod, {}, {}, (folders, cats))}
    for expected in (('carbine', 'A path = { } has no leads_to_tech'),
                     ('carbine', 'Folder nowhere_folder is not in common/technology_tags technology_folders'),
                     ('rifle_2', 'No name localisation'), ('rifle_2', 'xor with carbine')):
        assert expected in probs, (expected, probs)
    assert not any(tid == 'rifle_1' and 'localisation' in m for tid, m in probs)

    # moving snaps to the file's @rows and keeps the variable; comments and other techs are untouched
    tf.move('rifle_2', 4, 6)
    assert tf.focuses['rifle_2']['yraw'] == '@980' and tf.focuses['rifle_2']['xraw'] == '4'
    assert '# the first rifle' in tf.text and tf.focuses['rifle_1']['yraw'] == '@960'
    tf.undo_step()
    assert tf.focuses['rifle_2']['yraw'] == '@970'

    # add a tech after rifle_2 (path added), make it exclusive (both sides), then delete it (links removed)
    tf.add_focus('rifle_3', 0, 6, prereq='rifle_2', folder='army_folder')
    assert tf.focuses['rifle_3']['yraw'] == '@980' and ('rifle_3', '1') in tf.focuses['rifle_2']['leads']
    tf.link_mutex('rifle_3', 'rifle_1')
    assert 'rifle_1' in tf.focuses['rifle_3']['xor'] and 'rifle_3' in tf.focuses['rifle_1']['xor']
    tf.delete('rifle_3')
    assert 'rifle_3' not in tf.focuses and 'rifle_3' not in tf.text and brace_problem(tf.text) is None
    assert tf.focuses['rifle_2']['leads'] == [] and tf.focuses['rifle_1']['xor'] == []

    # duplicate starts without paths, next to the original; place() moves it to another folder
    tf.duplicate('rifle_1', 'rifle_1b')
    assert tf.focuses['rifle_1b']['leads'] == [] and tf.focuses['rifle_1b']['x'] == 2
    tf.place('rifle_1b', 'army_folder', '6', '@970')
    assert (tf.focuses['rifle_1b']['xraw'], tf.focuses['rifle_1b']['yraw']) == ('6', '@970')
    tf.save()
    assert TechFile(path).text == read_text(path) and 'rifle_1b' in read_text(path)

    # auto names: one write, existing names kept
    n = add_auto_names(tf, mod, os.path.join(d, 'localisation/english/t_l_english.yml'))
    assert n == 3 and mod.loc['rifle_1'] == 'Rifle' and mod.loc['rifle_1b'] == 'Rifle 1b'
print('ok')
