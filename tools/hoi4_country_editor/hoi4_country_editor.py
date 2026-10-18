"""HOI4 Country Editor: browse every country of a mod, edit its files, and list what it is missing.

Run:  python hoi4_country_editor.py [mod_folder]           (GUI)
      python hoi4_country_editor.py [mod_folder] --report  (text report, no GUI)
"""
import os
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------- Paradox script parser

TOKEN = re.compile(r'#[^\n]*|"(?:[^"\\]|\\.)*"|[<>!]?=|[<>]|[{}]|[^\s{}=<>#"]+')


def parse(text):
    """Parse Clausewitz script into a list of (key, value); value is a str or a nested list."""
    tokens = [t for t in TOKEN.findall(text) if not t.startswith('#')]
    pos = 0

    def block():
        nonlocal pos
        items = []
        while pos < len(tokens):
            t = tokens[pos]
            pos += 1
            if t == '}':
                return items
            if t == '{':  # anonymous block, e.g. a list of colours
                items.append(('', block()))
                continue
            if pos < len(tokens) and tokens[pos] in ('=', '<', '>', '<=', '>=', '!='):
                pos += 1
                if pos >= len(tokens):
                    break
                v = tokens[pos]
                pos += 1
                if v == '{':
                    items.append((t.strip('"'), block()))
                else:
                    if v in ('rgb', 'hsv', 'hsv360') and pos < len(tokens) and tokens[pos] == '{':
                        pos += 1
                        block()
                    items.append((t.strip('"'), v.strip('"')))
            else:  # bare value inside a list: { a b c }
                items.append(('', t.strip('"')))
        return items

    return block()


def get(items, key, default=None):
    for k, v in items:
        if k == key:
            return v
    return default


def get_all(items, key):
    return [v for k, v in items if k == key]


def walk(items):
    """Yield every (key, value) pair at every depth."""
    for k, v in items:
        yield k, v
        if isinstance(v, list):
            yield from walk(v)


def read_text(path):
    with open(path, 'rb') as f:
        return f.read().decode('utf-8-sig', errors='replace')


def write_text(path, text):
    """Save keeping the file's BOM state (HOI4 needs the BOM on .yml files)."""
    bom = False
    if os.path.exists(path):
        with open(path, 'rb') as f:
            bom = f.read(3) == b'\xef\xbb\xbf'
    elif path.lower().endswith('.yml'):
        bom = True
    with open(path, 'wb') as f:
        f.write((b'\xef\xbb\xbf' if bom else b'') + text.replace('\r\n', '\n').encode('utf-8'))


# ---------------------------------------------------------------- Mod model

LOC_LINE = re.compile(r'^\s*([^\s#:]+):\d*\s*"(.*)"\s*(?:#.*)?$')


class Mod:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.reload()

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def find(self, rel):
        """Case-insensitive file lookup (HOI4 runs on Windows, so 'HOD_Rep' finds 'HOD_REP.txt')."""
        cur = self.root
        for part in re.split(r'[\\/]', rel):
            if not part:
                continue
            exact = os.path.join(cur, part)
            if os.path.exists(exact):
                cur = exact
                continue
            try:
                match = next((n for n in os.listdir(cur) if n.lower() == part.lower()), None)
            except (FileNotFoundError, NotADirectoryError):
                return None
            if match is None:
                return None
            cur = os.path.join(cur, match)
        return cur

    def files(self, folder, ext='.txt'):
        """Files the game loads: top level only, except localisation which is read recursively."""
        base = self.path(folder)
        out = []
        for dirpath, dirs, names in os.walk(base):
            out += [os.path.join(dirpath, n) for n in sorted(names) if n.lower().endswith(ext)]
            if folder != 'localisation':
                break
        return out

    def reload(self):
        self.tags = {}  # TAG -> common/countries/... file (relative to common/)
        for f in self.files('common/country_tags'):
            items = parse(read_text(f))
            if get(items, 'dynamic_tags') == 'yes':
                continue
            for k, v in items:
                if re.fullmatch(r'[A-Z0-9]{3}', k) and isinstance(v, str):
                    self.tags[k] = v

        self.ideologies = {}  # ideology -> [subtypes]
        self.subtype_to_ideology = {}
        for f in self.files('common/ideologies'):
            for ideo, body in get(parse(read_text(f)), 'ideologies', []) or []:
                if not isinstance(body, list):
                    continue
                subs = [k for k, _ in (get(body, 'types', []) or []) if k]
                self.ideologies[ideo] = subs
                for s in subs:
                    self.subtype_to_ideology[s] = ideo

        self.loc = {}
        self.loc_file = {}
        for f in self.files('localisation', '.yml'):
            for line in read_text(f).splitlines():
                m = LOC_LINE.match(line)
                if m:
                    self.loc[m.group(1)] = m.group(2)
                    self.loc_file.setdefault(m.group(1), f)

        self.characters = {}  # id -> (body, file)
        for f in self.files('common/characters'):
            for cid, body in get(parse(read_text(f)), 'characters', []) or []:
                if isinstance(body, list):
                    self.characters[cid] = (body, f)

        self.history = {}  # TAG -> history file
        for f in self.files('history/countries'):
            m = re.match(r'([A-Z0-9]{3})\b', os.path.basename(f))
            if m:
                self.history.setdefault(m.group(1), f)

        self.focus_trees = defaultdict(list)  # TAG -> [focus tree ids]
        for f in self.files('common/national_focus'):
            for k, tree in parse(read_text(f)):
                if k != 'focus_tree' or not isinstance(tree, list):
                    continue
                tid = get(tree, 'id', os.path.basename(f))
                for _, mod in (get(tree, 'country', []) or []):
                    if isinstance(mod, list) and get(mod, 'tag') and get(mod, 'add', '0') not in ('0', '-0'):
                        self.focus_trees[get(mod, 'tag')].append(tid)

        self.sprites = set()
        for f in self.files('interface', '.gfx'):
            self.sprites.update(re.findall(r'name\s*=\s*"?(GFX_[^\s"}]+)', read_text(f)))

    def country(self, tag):
        return Country(self, tag)


REQUIRED, RECOMMENDED, OPTIONAL = 'required', 'recommended', 'optional'


class Country:
    def __init__(self, mod, tag):
        self.mod, self.tag = mod, tag
        self.checks = []  # (level, ok, text)
        self.files = {}   # label -> path, for the editor
        self.ideo_rows = {}
        self.leaders = []
        self.units = {}
        self.history = []
        self._analyse()

    def check(self, level, ok, text):
        self.checks.append((level, bool(ok), text))
        return ok

    @property
    def missing(self):
        return [c for c in self.checks if not c[1]]

    def name(self):
        return self.mod.loc.get(self.tag, '')

    def _analyse(self):
        m, tag = self.mod, self.tag

        # common/countries
        cfile = m.find(os.path.join('common', m.tags.get(tag, ''))) if tag in m.tags else None
        self.check(REQUIRED, tag in m.tags, 'Tag listed in common/country_tags')
        if self.check(REQUIRED, cfile, f'Country file common/{m.tags.get(tag, "?")} exists'):
            self.files['Country file (color, culture)'] = cfile
            citems = parse(read_text(cfile))
            self.check(REQUIRED, get(citems, 'color'), 'Country file has a color')
            self.check(RECOMMENDED, get(citems, 'graphical_culture'), 'Country file has graphical_culture')

        # history
        hfile = m.history.get(tag)
        if self.check(REQUIRED, hfile, f'History file history/countries/{tag} - ....txt exists'):
            self.files['History (start situation)'] = hfile
            self.history = parse(read_text(hfile))
        h = self.history
        self.check(REQUIRED, get(h, 'capital'), 'History sets a capital')
        pol = get(h, 'set_politics', []) or []
        ruling = get(pol, 'ruling_party')
        self.check(REQUIRED, ruling, 'History sets a ruling_party (set_politics)')
        pops = {k: float(v) for k, v in (get(h, 'set_popularities', []) or []) if _is_num(v)}
        total = sum(pops.values())
        self.check(REQUIRED, pops and abs(total - 100) < 0.01, f'Popularities sum to 100 (now {total:g})')
        self.check(RECOMMENDED, get(h, 'set_technology'), 'History sets starting technology')
        self.check(RECOMMENDED, get(h, 'set_research_slots'), 'History sets research slots')
        self.popularities, self.ruling = pops, ruling

        # OOBs
        for key, label in (('oob', 'Land OOB'), ('set_naval_oob', 'Naval OOB'), ('set_air_oob', 'Air OOB')):
            name = get(h, key)
            if not name:
                if key == 'oob':
                    self.check(RECOMMENDED, False, 'History loads a land OOB (oob = "...")')
                continue
            f = m.find(f'history/units/{name}.txt')
            if self.check(REQUIRED, f, f'{label} history/units/{name}.txt exists'):
                self.files[f'{label} ({name})'] = f
                self.units[label] = summarize_oob(parse(read_text(f)), self)

        # Focus tree
        trees = m.focus_trees.get(tag, [])
        loaded = get(h, 'load_focus_tree')
        self.focus = trees or ([loaded] if loaded else [])
        self.check(RECOMMENDED, self.focus, 'Has a national focus tree (else uses generic)')

        # Flags
        for size in ('', 'medium/', 'small/'):
            f = m.find(f'gfx/flags/{size}{tag}.tga')
            self.check(REQUIRED, f, f'Flag gfx/flags/{size}{tag}.tga')

        # Localisation
        for key in (tag, f'{tag}_DEF', f'{tag}_ADJ'):
            self.check(REQUIRED, key in m.loc, f'Localisation key {key}')

        # Leaders / characters
        recruited = [v for k, v in walk(h) if k == 'recruit_character']
        by_ideo = defaultdict(list)
        for cid in recruited:
            if not self.check(REQUIRED, cid in m.characters, f'Character {cid} is defined in common/characters'):
                continue
            body, f = m.characters[cid]
            self.files.setdefault(f'Characters ({os.path.basename(f)})', f)
            roles = [r for r in ('country_leader', 'advisor', 'corps_commander', 'field_marshal', 'navy_leader')
                     if get(body, r) is not None]
            ideo = ''
            for cl in get_all(body, 'country_leader'):
                sub = get(cl, 'ideology', '')
                ideo = m.subtype_to_ideology.get(sub, sub)
                by_ideo[ideo].append(cid)
            name = get(body, 'name', cid)
            pic = self._portrait(body)
            self.leaders.append((cid, m.loc.get(name, name), ', '.join(roles), ideo, pic))
            if pic is not None:
                self.check(RECOMMENDED, pic, f'Portrait for {cid} exists')
        self.check(REQUIRED, ruling in by_ideo, f'Country leader for the ruling party ({ruling})')

        # Per-ideology matrix
        for ideo in m.ideologies:
            flag = m.find(f'gfx/flags/{tag}_{ideo}.tga')
            row = {
                'popularity': pops.get(ideo, 0),
                'leader': ', '.join(by_ideo.get(ideo, [])),
                'flag': os.path.basename(flag) if flag else '',
                'name': m.loc.get(f'{tag}_{ideo}', ''),
                'party': m.loc.get(f'{tag}_{ideo}_party', ''),
            }
            self.ideo_rows[ideo] = row
            self.check(RECOMMENDED, row['party'], f'Party name {tag}_{ideo}_party')
            if pops.get(ideo, 0) > 0 or ideo == ruling:
                self.check(OPTIONAL, row['leader'], f'Leader for {ideo} (has popularity)')
            self.check(OPTIONAL, row['flag'], f'Ideology flag {tag}_{ideo}.tga')
            self.check(OPTIONAL, row['name'], f'Ideology country name {tag}_{ideo}')

    def _portrait(self, body):
        """None = no portrait set, '' = set but missing, else the path/sprite."""
        port = get(body, 'portraits')
        if not port:
            return None
        for _, v in walk(port):
            if isinstance(v, str) and v:
                if v.startswith('GFX_'):
                    return v if v in self.mod.sprites else ''
                return v if self.mod.find(v) else ''
        return None


def summarize_oob(items, country):
    templates = {get(t, 'name') for t in get_all(items, 'division_template')}
    divs = defaultdict(int)
    ships = 0
    fleets = 0
    for units in get_all(items, 'units'):
        for d in get_all(units, 'division'):
            t = get(d, 'division_template', '?')
            divs[t] += 1
            country.check(REQUIRED, t in templates or t == '?', f'Division template "{t}" is defined in its OOB')
        for fleet in get_all(units, 'fleet'):
            fleets += 1
            ships += sum(1 for k, _ in walk(fleet) if k == 'ship')
    lines = [f'{n} x {t}' for t, n in sorted(divs.items())]
    lines.append(f'{len(templates)} division templates, {sum(divs.values())} divisions')
    if fleets:
        lines.append(f'{fleets} fleets, {ships} ships')
    air = sum(1 for k, _ in walk(items) if k == 'air_wings')
    if air:
        lines.append(f'{air} air wing groups')
    return lines


def _is_num(v):
    return isinstance(v, str) and re.fullmatch(r'-?\d+(\.\d+)?', v) is not None


def report(mod, tags=None, level=OPTIONAL):
    order = [REQUIRED, RECOMMENDED, OPTIONAL]
    keep = order[:order.index(level) + 1]
    out = []
    for tag in tags or sorted(mod.tags):
        c = mod.country(tag)
        miss = [x for x in c.missing if x[0] in keep]
        out.append(f'== {tag} {c.name()}: {len(miss)} missing')
        out += [f'   [{lvl}] {txt}' for lvl, _, txt in miss]
    return '\n'.join(out)


# ---------------------------------------------------------------- GUI

def run_gui(mod_root):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title('HOI4 Country Editor')
    root.geometry('1250x780')

    if not mod_root:
        mod_root = filedialog.askdirectory(title='Pick your mod folder (the one with common/, history/, gfx/)')
        if not mod_root:
            return
    mod = Mod(mod_root)
    state = {'country': None}

    # left: country list
    left = ttk.Frame(root)
    left.pack(side='left', fill='y')
    search = tk.StringVar()
    ttk.Entry(left, textvariable=search).pack(fill='x', padx=4, pady=4)
    countries = ttk.Treeview(left, columns=('miss',), show='tree headings', height=40)
    countries.heading('#0', text='Country')
    countries.heading('miss', text='Missing (req/rec)')
    countries.column('#0', width=230)
    countries.column('miss', width=110, anchor='center')
    countries.pack(fill='y', expand=True, padx=4)
    btns = ttk.Frame(left)
    btns.pack(fill='x', padx=4, pady=4)

    nb = ttk.Notebook(root)
    nb.pack(side='left', fill='both', expand=True)

    def tab(title, columns):
        frame = ttk.Frame(nb)
        nb.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=140)
        sb = ttk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        return tree

    checklist = tab('Checklist', ('status', 'level', 'check'))
    checklist.column('status', width=60, anchor='center')
    checklist.column('level', width=100)
    checklist.column('check', width=700)
    checklist.tag_configure('bad_required', foreground='#c00000')
    checklist.tag_configure('bad_recommended', foreground='#b06000')
    checklist.tag_configure('bad_optional', foreground='#777777')
    overview = tab('Overview', ('field', 'value'))
    overview.column('value', width=700)
    ideos = tab('Ideologies', ('ideology', 'popularity', 'leader', 'flag', 'name', 'party'))
    leaders = tab('Leaders & characters', ('id', 'name', 'roles', 'ideology', 'portrait'))
    units = tab('Military', ('oob', 'content'))
    units.column('content', width=700)

    # editor tab
    ed_frame = ttk.Frame(nb)
    nb.add(ed_frame, text='Edit files')
    bar = ttk.Frame(ed_frame)
    bar.pack(fill='x')
    file_pick = ttk.Combobox(bar, state='readonly', width=80)
    file_pick.pack(side='left', padx=4, pady=4)
    text = tk.Text(ed_frame, wrap='none', undo=True, font=('Consolas', 10))
    ysb = ttk.Scrollbar(ed_frame, command=text.yview)
    text.configure(yscrollcommand=ysb.set)
    ysb.pack(side='right', fill='y')
    text.pack(fill='both', expand=True)
    ed = {'path': None}

    def load_file(_=None):
        c = state['country']
        if not c or not file_pick.get():
            return
        ed['path'] = c.files[file_pick.get()]
        text.delete('1.0', 'end')
        text.insert('1.0', read_text(ed['path']))
        text.edit_modified(False)

    def save_file():
        if not ed['path']:
            return
        body = text.get('1.0', 'end-1c')
        if body.count('{') != body.count('}'):
            if not messagebox.askyesno('Unbalanced braces',
                                       f'{body.count("{")} "{{" vs {body.count("}")} "}}". Save anyway?'):
                return
        write_text(ed['path'], body)
        text.edit_modified(False)
        mod.reload()
        refresh_list()
        show(state['country'].tag)

    file_pick.bind('<<ComboboxSelected>>', load_file)
    ttk.Button(bar, text='Save (Ctrl+S)', command=save_file).pack(side='left', padx=4)
    ttk.Button(bar, text='Reload from disk', command=load_file).pack(side='left')
    root.bind('<Control-s>', lambda e: save_file())

    def fill(tree, rows, tags=None):
        tree.delete(*tree.get_children())
        for i, r in enumerate(rows):
            tree.insert('', 'end', values=r, tags=(tags[i],) if tags else ())

    def show(tag):
        c = mod.country(tag)
        state['country'] = c
        order = {REQUIRED: 0, RECOMMENDED: 1, OPTIONAL: 2}
        rows = sorted(c.checks, key=lambda x: (x[1], order[x[0]]))
        fill(checklist, [('OK' if ok else 'MISSING', lvl, txt) for lvl, ok, txt in rows],
             ['ok' if ok else f'bad_{lvl}' for lvl, ok, _ in rows])
        h = c.history
        fill(overview, [
            ('Tag', tag), ('Name', c.name()), ('Adjective', mod.loc.get(f'{tag}_ADJ', '')),
            ('Capital state', get(h, 'capital', '')), ('Ruling party', c.ruling or ''),
            ('Elections', get(get(h, 'set_politics', []) or [], 'elections_allowed', '')),
            ('Stability', get(h, 'set_stability', '')), ('War support', get(h, 'set_war_support', '')),
            ('Research slots', get(h, 'set_research_slots', '')),
            ('Focus tree', ', '.join(c.focus)),
            ('Ideas / national spirits', ' '.join(v for _, v in (get(h, 'add_ideas', []) or []))),
            ('Technologies', str(len(get(h, 'set_technology', []) or []))),
            ('History file', mod.history.get(tag, '')),
        ])
        fill(ideos, [(i, f'{r["popularity"]:g}', r['leader'], r['flag'], r['name'], r['party'])
                     for i, r in c.ideo_rows.items()])
        fill(leaders, [(cid, name, roles, ideo, 'none' if pic is None else (pic or 'MISSING FILE'))
                       for cid, name, roles, ideo, pic in c.leaders])
        fill(units, [(k, line) for k, lines in c.units.items() for line in lines])
        file_pick['values'] = list(c.files)
        if c.files:
            file_pick.current(next((i for i, k in enumerate(c.files) if k.startswith('History')), 0))
            load_file()

    def refresh_list(*_):
        sel = countries.selection()
        countries.delete(*countries.get_children())
        q = search.get().lower()
        for tag in sorted(mod.tags):
            c = mod.country(tag)
            label = f'{tag}  {c.name()}'
            if q and q not in label.lower():
                continue
            req = sum(1 for x in c.missing if x[0] == REQUIRED)
            rec = sum(1 for x in c.missing if x[0] == RECOMMENDED)
            countries.insert('', 'end', iid=tag, text=label, values=(f'{req} / {rec}',))
        if sel and countries.exists(sel[0]):
            countries.selection_set(sel[0])

    def on_select(_):
        sel = countries.selection()
        if sel and sel[0] != getattr(state['country'], 'tag', None):
            if text.edit_modified() and not messagebox.askyesno('Unsaved', 'Discard unsaved edits?'):
                return
            show(sel[0])

    def export():
        f = filedialog.asksaveasfilename(defaultextension='.txt', initialfile='missing_report.txt')
        if f:
            with open(f, 'w', encoding='utf-8') as out:
                out.write(report(mod))

    def reload_all():
        mod.reload()
        refresh_list()

    countries.bind('<<TreeviewSelect>>', on_select)
    search.trace_add('write', refresh_list)
    ttk.Button(btns, text='Reload mod', command=reload_all).pack(side='left')
    ttk.Button(btns, text='Export missing report', command=export).pack(side='left', padx=4)
    refresh_list()
    root.mainloop()


def find_mod_root():
    """Walk up from the script/exe until a folder with descriptor.mod is found."""
    start = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
    d = start
    while True:
        if os.path.exists(os.path.join(d, 'descriptor.mod')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root_dir = args[0] if args else find_mod_root()
    if '--report' in sys.argv:
        if not root_dir:
            sys.exit('usage: hoi4_country_editor.py MOD_FOLDER --report')
        print(report(Mod(root_dir)))
    else:
        run_gui(root_dir)
