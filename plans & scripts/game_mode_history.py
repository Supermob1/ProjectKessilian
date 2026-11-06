"""The two game modes, written straight into the history (no on_startup setup).

TOTAL WAR = the main bookmark (976.1.1.1). A "976.1.1" block on each state of the Republic's member worlds and the
Confederacy's aligned worlds hands it to REP / CIS: the galaxy starts simplified into two blocs.

BATTLE ROYALE = its own bookmark (976.1.2.1). "976.1.2" blocks, which only that bookmark reaches:
  - every state: its planet's owner, economic buildings cleared; every capital: capital_sector + the same package
  - every country: oob = HOD_BR_basic (only the "Planetary Militia" template: no units, ships, planes or other
    templates), the Battle Royale spirit, factions and subjects ended, keepers renamed after their planet
A planet = a strategic region with states. The tag whose capital is on it keeps it, except REP and CIS: Coruscant, Raxus
and every planet without a capital get a new tag (so no Republic / Confederacy, no custom tech trees or focus trees).

Writes common/country_tags/HOD_battle_royale_tags.txt, common/countries/HOD_BR *.txt, history/countries (new tags +
blocks), history/states (blocks), history/units/HOD_BR_basic.txt, localisation/english/HOD_battle_royale_l_english.yml,
gfx/flags (generated for new tags, copied for the keepers' cosmetic HOD_BR_<region>).
Re-run after adding planets / states / tags (idempotent):  python -B "plans & scripts/game_mode_history.py"
"""
import collections, colorsys, glob, hashlib, importlib.util, os, re, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P = lambda *a: os.path.join(ROOT, *a)
TW_DATE, BR_DATE = '976.1.1', '976.1.2'
TW_MARK, BR_MARK = '# HOD total war (game_mode_history.py)', '# HOD battle royale (game_mode_history.py)'
CIS_WORLDS = ['CMG', 'IBC', 'TDF', 'TCU', 'ZGY', 'SSB', 'KAL', 'GIV', 'COL', 'SKK', 'BTK', 'BLW', 'GAF', 'GEO']  # = confederacy.1
REPLACED = {'REP', 'CIS'}
BASIC_TEMPLATE = 'Planetary Militia'
ECONOMY = ['industrial_complex', 'arms_factory', 'dockyard', 'synthetic_refinery', 'fuel_silo', 'rocket_site',
           'nuclear_reactor', 'radar_station', 'anti_air_building', 'air_base']
CAPITAL_PACKAGE = [('infrastructure', 4), ('industrial_complex', 4), ('arms_factory', 3), ('dockyard', 1), ('air_base', 2)]
TAGS_FILE = P('common/country_tags/HOD_battle_royale_tags.txt')
RESERVED = {'AND', 'NOT', 'ANY', 'ALL', 'FOR', 'NOR', 'XOR', 'NIL', 'THE', 'OOB', 'TAG', 'AIR', 'SEA', 'WAR'}
IDEOLOGIES = ["akaanadocrat", "unitist", "corist", "distributionist", "corporate_consortium", "trade_democrat",
              "ruusanist", "inclusivist", "force_magocracy"]
EMBLEMS = ["sun", "drop", "crown", "ring", "horns", "gear", "flake", "skull"]


def read(path):
    return open(path, encoding='utf-8-sig', errors='ignore').read()


def write(path, text, bom=False):
    open(path, 'w', encoding='utf-8-sig' if bom else 'utf-8', newline='\n').write(text)


def strip_blocks(t):
    """Drop the blocks this script wrote before (each starts with its MARK line, ends with its closing brace)."""
    for mark in (TW_MARK, BR_MARK):
        t = re.sub(r'(?m)^[ \t]*' + re.escape(mark) + r'\r?\n[ \t]*\d+\.\d+\.\d+ = \{.*?\r?\n[ \t]*\}[ \t]*\r?\n', '', t, flags=re.S)
    return t


def rewrite(path, blocks, in_history):
    """Remove old blocks, then add `blocks` (text with \\n) before the end of the history block (states) or file."""
    raw = open(path, 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    t = strip_blocks(raw.decode('utf-8-sig'))
    nl = '\r\n' if '\r\n' in t else '\n'
    if blocks:
        add = blocks.replace('\n', nl)
        if in_history:
            h = re.search(r'\bhistory\s*=\s*\{', t)
            d, i = 1, h.end()
            while d:
                d += {'{': 1, '}': -1}.get(t[i], 0)
                i += 1
            close = t.rfind('\n', 0, i - 1) + 1
            t = t[:close] + add + t[close:]
        else:
            t = t.rstrip() + nl + nl + add
    open(path, 'w', encoding='utf-8-sig' if bom else 'utf-8', newline='').write(t)


def block(mark, date, lines, indent):
    tab = '\t' * indent
    return '%s%s\n%s%s = {\n%s%s}\n' % (tab, mark, tab, date, ''.join(tab + '\t' + l + '\n' for l in lines), tab)


def load():
    region_of_prov = {}
    for f in glob.glob(P('map/strategicregions/*.txt')):
        t = read(f)
        rid = int(re.search(r'\bid\s*=\s*(\d+)', t).group(1))
        for q in re.search(r'provinces\s*=\s*\{([^}]*)\}', t).group(1).split():
            region_of_prov[int(q)] = rid
    states, files = {}, {}
    for f in glob.glob(P('history/states/*.txt')):
        t = strip_blocks(read(f))
        sid = int(re.search(r'\bid\s*=\s*(\d+)', t).group(1))
        owner = re.search(r'\bowner\s*=\s*(\w+)', t)
        provs = [int(x) for x in re.search(r'provinces\s*=\s*\{([^}]*)\}', t).group(1).split()]
        regions = collections.Counter(region_of_prov.get(p) for p in provs)
        files[sid] = f
        if owner:
            states[sid] = (owner.group(1), regions.most_common(1)[0][0], len(provs))
    base_tags = dict(re.findall(r'(?m)^\s*([A-Z0-9]{3})\s*=\s*"([^"]+)"', read(P('common/country_tags/HOD_countries.txt'))))
    hist = {}
    for f in glob.glob(P('history/countries/*.txt')):
        if os.path.basename(f)[:3] in base_tags:
            hist[os.path.basename(f)[:3]] = f
    capitals = {}
    for tag, f in hist.items():
        m = re.search(r'^\s*capital\s*=\s*(\d+)', read(f), re.M)
        if m:
            capitals[tag] = int(m.group(1))
    names = {int(a): b for a, b in re.findall(r'^\s*STRATEGICREGION_(\d+):\d*\s*"([^"]*)"',
                                             read(P('localisation/english/strategic_region_names_l_english.yml')), re.M)}
    return states, files, base_tags, hist, capitals, names


def new_tag(name, taken):
    letters = re.sub(r'[^A-Z]', '', name.upper()) + 'XYZQ'
    cands = [letters[:3], letters[0] + letters[1] + letters[-5], letters[0] + letters[2:4]]
    cands += [letters[0] + a + b for a in letters[1:] for b in letters[2:]]
    cands += [letters[0] + a + b for a in 'QXZJVKWY' for b in 'QXZJVKWY']
    for c in cands:
        if len(c) == 3 and c.isalpha() and c not in taken and c not in RESERVED:
            return c
    raise SystemExit('no free tag for ' + name)


def colour(name):
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360, 0.45 + (h >> 9) % 30 / 100, 0.55 + (h >> 17) % 35 / 100)
    return tuple(int(v * 255) for v in (r, g, b)), h


def flag_maker():
    spec = importlib.util.spec_from_file_location('new_tags', os.path.join(os.path.dirname(__file__), 'new_tags.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.flag


def new_tag_history(tag, cap, parent_hist):
    t = read(P('history/countries/UTA - Utapau.txt'))
    t = strip_blocks(t)
    t = re.sub(r'(?m)^\s*recruit_character\s*=.*\n?', '', t)
    t = re.sub(r'(?m)^\s*oob\s*=.*\n?', '', t)
    t = re.sub(r'(?m)^# HOD: new leaders.*\n?', '', t)
    t = t.replace('capital = 56', 'capital = %d' % cap).replace('producer = UTA', 'producer = %s' % tag)
    for key in ('set_popularities', 'set_politics'):  # the old owner's politics
        m = parent_hist and re.search(key + r'\s*=\s*\{.*?\n\}', parent_hist, re.S)
        if m:
            t = re.sub(key + r'\s*=\s*\{.*?\n\}', lambda _: m.group(0), t, flags=re.S)
    assert 'UTA' not in t, tag
    return ('# GENERATED by plans & scripts/game_mode_history.py: owns land only in the Battle Royale bookmark\n'
            + t.rstrip() + '\noob = "HOD_BR_basic"\n')


def main():
    states, files, base_tags, hist, capitals, names = load()
    flag = flag_maker()

    # ---- Total War: the blocs absorb their worlds (976.1.1, main bookmark)
    rep_members = re.findall(r'(?m)^\s*add_to_faction\s*=\s*([A-Z0-9]{3})', read(hist['REP']))
    tw_owner = {s: ('REP' if o in rep_members else 'CIS') for s, (o, _, _) in states.items()
                if o in rep_members or o in CIS_WORLDS}

    # ---- Battle Royale planets
    planets = collections.defaultdict(lambda: collections.defaultdict(list))
    for sid, (owner, rid, _) in sorted(states.items()):
        planets[rid][owner].append(sid)
    keeper = {}
    for rid, owners in planets.items():
        cands = [t for t in owners if capitals.get(t) in owners[t] and t not in REPLACED]
        if cands and not any(capitals.get(t) in owners[t] for t in REPLACED & set(owners)):  # Coruscant, Raxus: new tag
            keeper[rid] = max(cands, key=lambda t: len(owners[t]))

    for f in glob.glob(P('common/countries/HOD_BR *.txt')) + glob.glob(P('gfx/flags/**/HOD_BR_*.tga'), recursive=True):
        os.remove(f)
    if os.path.exists(TAGS_FILE):
        for tag in re.findall(r'(?m)^([A-Z]{3})\s*=', read(TAGS_FILE)):
            for f in glob.glob(P('history/countries/%s - *.txt' % tag)) + glob.glob(P('gfx/flags/**/%s.tga' % tag), recursive=True):
                os.remove(f)

    taken = set(base_tags)
    tag_lines = ['# GENERATED by plans & scripts/game_mode_history.py: planet countries of the Battle Royale bookmark']
    loc = ['l_english:', ' # GENERATED by plans & scripts/game_mode_history.py']
    br_owner, br_capital, cosmetic, featured = {}, {}, {}, {}
    for rid in sorted(planets):
        owners, name = planets[rid], names.get(rid, 'Planet %d' % rid)
        safe = name.replace('"', "'")
        k = keeper.get(rid)
        all_states = [s for ss in owners.values() for s in ss]
        if k:
            cos = 'HOD_BR_%d' % rid
            cosmetic[k] = cos
            loc += [' %s:0 "%s"' % (cos, safe), ' %s_ADJ:0 "%s"' % (cos, safe), ' %s_DEF:0 "%s"' % (cos, safe)]
            for sub in ('', 'medium', 'small'):
                if os.path.exists(P('gfx/flags', sub, k + '.tga')):
                    shutil.copyfile(P('gfx/flags', sub, k + '.tga'), P('gfx/flags', sub, cos + '.tga'))
            owner, cap = k, capitals[k]
        else:
            tag = new_tag(name, taken)
            taken.add(tag)
            parent = max(owners, key=lambda t: (len(owners[t]), t))
            old_caps = [capitals[t] for t in sorted(owners) if capitals.get(t) in all_states]
            cap = old_caps[0] if old_caps else max(all_states, key=lambda s: (states[s][2], -s))  # old capital, else biggest
            col, h = colour(name)
            fname = 'HOD_BR %s.txt' % re.sub(r'[^\w\- ]', '', name)
            tag_lines.append('%s = "countries/%s"  # %s' % (tag, fname, name))
            write(P('common/countries', fname), 'graphical_culture = western_european_gfx\n'
                  'graphical_culture_2d = western_european_2d\n\ncolor = rgb { %d %d %d }\n' % col)
            write(P('history/countries', '%s - %s.txt' % (tag, re.sub(r'[^\w\- ]', '', name))),
                  new_tag_history(tag, cap, read(hist[parent]) if parent in hist else None), bom=True)
            loc += [' %s:0 "%s"' % (tag, safe), ' %s_DEF:0 "%s"' % (tag, safe), ' %s_ADJ:0 "%s"' % (tag, safe)]
            loc += [' %s_%s%s:0 "%s"' % (tag, i, sfx, safe) for i in IDEOLOGIES for sfx in ('', '_DEF', '_ADJ')]
            accent = tuple(255 - (255 - c) // 4 if sum(col) < 380 else c // 4 for c in col)
            flag(tag, col, accent, EMBLEMS[h % len(EMBLEMS)])
            owner = tag
            if name in ('Coruscant', 'Raxus'):
                featured[name] = tag
        br_capital[owner] = cap
        for s in all_states:
            br_owner[s] = owner

    # ---- state history
    for sid, f in files.items():
        blocks = ''
        if sid in tw_owner:
            o = tw_owner[sid]
            blocks += block(TW_MARK, TW_DATE, ['owner = %s' % o, 'controller = %s' % o, 'add_core_of = %s' % o], 2)
        if sid in br_owner:
            o = br_owner[sid]
            lines = ['owner = %s' % o, 'controller = %s' % o, 'add_core_of = %s' % o]
            if br_capital.get(o) == sid:  # same capital everywhere: 25 slots and the same package
                lines += ['set_state_category = capital_sector',
                          'buildings = { %s }' % ' '.join('%s = %d' % kv for kv in CAPITAL_PACKAGE + [
                              (b, 0) for b in ECONOMY if b not in dict(CAPITAL_PACKAGE)])]
            else:
                lines.append('buildings = { %s }' % ' '.join('%s = 0' % b for b in ECONOMY))
            blocks += block(BR_MARK, BR_DATE, lines, 2)
        rewrite(f, blocks, in_history=True)

    # ---- country history: every base country gets the Battle Royale block (harmless for those without land)
    for tag, f in sorted(hist.items()):
        lines = ['oob = "HOD_BR_basic"  # only the basic template: no units, ships, planes or starting templates',
                 'add_ideas = HOD_br_every_world_for_itself',
                 'if = { limit = { is_faction_leader = yes } dismantle_faction = yes }',
                 'every_other_country = { limit = { is_subject_of = ROOT } ROOT = { end_puppet = PREV } }']
        if tag in cosmetic:
            lines.append('set_cosmetic_tag = %s' % cosmetic[tag])
        rewrite(f, block(BR_MARK, BR_DATE, lines, 0), in_history=False)
    for name, tag in featured.items():
        f = glob.glob(P('history/countries/%s - *.txt' % tag))[0]
        extra = ['set_global_flag = HOD_battle_royale'] if name == 'Coruscant' else []
        rewrite(f, block(BR_MARK, BR_DATE, extra + ['add_ideas = HOD_br_every_world_for_itself'], 0), in_history=False)
    for f in glob.glob(P('history/countries/*.txt')):
        tag = os.path.basename(f)[:3]
        if tag not in hist and tag not in featured.values() and tag in taken:
            rewrite(f, block(BR_MARK, BR_DATE, ['add_ideas = HOD_br_every_world_for_itself'], 0), in_history=False)

    write(P('history/units/HOD_BR_basic.txt'), '# GENERATED by plans & scripts/game_mode_history.py: Battle Royale start\n'
          'division_template = {\n\tname = "%s"\n\tregiments = {\n%s\t}\n}\n' % (
              BASIC_TEMPLATE, ''.join('\t\tinfantry = { x = %d y = %d }\n' % (x, y) for x in range(2) for y in range(3))))
    write(TAGS_FILE, '\n'.join(tag_lines) + '\n')
    write(P('localisation/english/HOD_battle_royale_l_english.yml'), '\n'.join(loc) + '\n', bom=True)
    assert len(br_owner) == len(states), 'every owned state needs a Battle Royale owner'
    print('Total War: %d states to REP/CIS. Battle Royale: %d planets, %d keepers, %d new tags (Coruscant %s, Raxus %s)'
          % (len(tw_owner), len(planets), len(keeper), len(planets) - len(keeper), featured.get('Coruscant'), featured.get('Raxus')))


if __name__ == '__main__':
    main()
