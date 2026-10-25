"""HOI4 Tech Tree Editor: draw, edit and check the technology trees of a mod.

Run:  python hoi4_tech_editor.py [mod_folder]            (GUI)
      python hoi4_tech_editor.py [mod_folder] --check   (list problems in every tech file, no GUI)

Built on the focus editor: the tech file's text is the source of truth, every edit is a small text change
(comments, formatting and @year variables are kept), and undo is just the previous text.
"""
import os
import re
import sys

from hoi4_country_editor import (TOKEN, Mod, add_to_block, find_mod_root, get, get_all, parse, read_text, set_in,
                                 set_loc, top_span, write_text)
from hoi4_focus_editor import (FocusFile, auto_name, brace_depth, brace_problem, fmt, fmt_days, hod_calendar, inner,
                               load_settings, save_settings, spans)

# The mod's tech screen runs left to right: y is the column (the @year grid), x the row.
UX, UY = 70, 40  # editor pixels per x step (down) and per y step (across) at zoom 1
BW, BH = 98, 62  # tech box size at zoom 1
ICON_SIZE = (64, 64)  # most of the mod's tech icons


def top_blocks(text):
    """(key, start, end) of every top-level `key = { ... }` in text, in one pass."""
    out, depth, key, start = [], 0, None, 0
    toks = [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text) if not m.group().startswith('#')]
    for i, (t, s, e) in enumerate(toks):
        if t == '{':
            if depth == 0 and i >= 2 and toks[i - 1][0] == '=':
                key, start = toks[i - 2][0], toks[i - 2][1]
            depth += 1
        elif t == '}':
            depth -= 1
            if depth == 0 and key is not None:
                out.append((key, start, e))
                key = None
    return out


def tech_blocks(text):
    """(id, start, end, block_index) of every tech in every top-level technologies = { } block."""
    out = []
    for bi, span in enumerate(spans(text, 'technologies')):
        a, b = inner(text, span)
        out += [(k, a + s, a + e, bi) for k, s, e in top_blocks(text[a:b]) if not k.startswith('@')]
    return out


def tech_text(tid, folder, x, y, cost='1', year=None, categories=()):
    lines = [f'\t{tid} = {{', f'\t\tresearch_cost = {cost}']
    if year:
        lines.append(f'\t\tstart_year = {year}')
    lines += ['\t\tfolder = {', f'\t\t\tname = {folder}', f'\t\t\tposition = {{ x = {x} y = {y} }}', '\t\t}']
    if categories:
        lines.append('\t\tcategories = { ' + ' '.join(categories) + ' }')
    lines += ['\t\tai_will_do = {', '\t\t\tfactor = 1', '\t\t}', '\t}']
    return '\n'.join(lines) + '\n'


def path_values(leads):
    """leads: [(tech, coeff)] -> the path = { } blocks."""
    return [f'{{ leads_to_tech = {t} research_cost_coeff = {c or 1} }}' for t, c in leads if t]


class TechFile(FocusFile):
    """A common/technologies file. Techs are stored in self.focuses so FocusFile's edit, undo and save work as is."""

    def num(self, raw, default=0.0):
        raw = str(raw if raw is not None else '')
        raw = self.vars.get(raw, raw)
        return float(raw) if re.fullmatch(r'-?\d+(\.\d+)?', raw) else default

    def refresh(self):
        self.focuses, self.order, self.vars = {}, [], {}
        for span in spans(self.text, 'technologies'):
            for k, v in parse(self.text[span[0]:span[1]])[0][1]:
                if k.startswith('@') and isinstance(v, str):
                    self.vars[k] = v
        for tid, s, e, bi in tech_blocks(self.text):
            items = parse(self.text[s:e])[0][1]
            folder = get(items, 'folder')
            folder = folder if isinstance(folder, list) else []
            pos = get(folder, 'position')
            pos = pos if isinstance(pos, list) else []
            flat = lambda key: [v for g in get_all(items, key) if isinstance(g, list) for _, v in g]
            t = dict(id=tid, start=s, end=e, tree=bi, folder=get(folder, 'name', ''),
                     xraw=get(pos, 'x', '0'), yraw=get(pos, 'y', '0'),
                     cost=get(items, 'research_cost', ''), year=get(items, 'start_year', ''),
                     leads=[(get(p, 'leads_to_tech', ''), get(p, 'research_cost_coeff', '1'))
                            for p in get_all(items, 'path') if isinstance(p, list)],
                     xor=flat('xor'), cats=flat('categories'), subs=flat('sub_technologies'),
                     deps=[k for g in get_all(items, 'dependencies') if isinstance(g, list) for k, _ in g],
                     special=get(items, 'is_special_project_tech') == 'yes', doctrine=get(items, 'doctrine') == 'yes',
                     icon=f'GFX_{tid}_medium', prereq=[], mutex=[], rel=None)
            t['x'], t['y'] = self.num(t['xraw']), self.num(t['yraw'])
            t['ax'], t['ay'] = t['x'], t['y']
            t['mutex'] = t['xor']
            if tid in self.focuses:
                t['duplicate'] = True
                tid = f'{tid}#{len(self.order)}'  # keep both visible so the duplicate can be fixed
            self.focuses[tid] = t
            self.order.append(tid)
        self.trees = spans(self.text, 'technologies')
        incoming = {}
        for tid, t in self.focuses.items():
            for target, _ in t['leads']:
                incoming.setdefault(target, []).append(t['id'])
        for t in self.focuses.values():
            t['from'] = incoming.get(t['id'], [])
            t['prereq'] = [t['from']] if t['from'] else []  # any one incoming line, like an "or" prerequisite

    @property
    def techs(self):
        return self.focuses

    def _edit_focus(self, text, tid, fn):
        if text is self.text:  # stored offsets also work for duplicated ids ("X#3")
            s, e = self.focuses[tid]['start'], self.focuses[tid]['end']
        else:
            real = self.focuses[tid]['id'] if tid in self.focuses else tid
            _, s, e, _ = next(blk for blk in tech_blocks(text) if blk[0] == real)
        a, b = inner(text, (s, e))
        return text[:a] + fn(text[a:b]) + text[b:]

    def y_value(self, y):
        """A y (column) as written: the @variable holding that value when the file uses them, else the number."""
        uses_vars = any(str(t['yraw']).startswith('@') for t in self.focuses.values())
        if uses_vars:
            for k, v in self.vars.items():
                if self.num(v, None) == y:
                    return k
        return fmt(y)

    def place(self, tid, folder, x, y):
        """Put a tech in a folder at x / y (raw values: numbers or @variables)."""
        def fn(body):
            if top_span(body, 'folder'):
                body = set_in(body, ['folder', 'name'], folder)
                if top_span(inner_text(body, 'folder'), 'position'):
                    for k, v in (('x', x), ('y', y)):
                        body = set_in(body, ['folder', 'position', k], v)
                    return body
                return set_in(body, ['folder', 'position'], f'{{ x = {x} y = {y} }}')
            return self._put(body, 'folder', f'{{\n\t\t\tname = {folder}\n\t\t\tposition = {{ x = {x} y = {y} }}\n\t\t}}')
        self.edit(tid, fn)

    def move(self, tid, ax, ay):
        t = self.focuses[tid]
        self.place(tid, t['folder'], fmt(ax), self.y_value(ay))

    def add_focus(self, tid, ax, ay, prereq=None, tree=0, folder='', year=None, categories=()):
        s, e = spans(self.text, 'technologies')[tree]
        a, b = inner(self.text, (s, e))
        body = self.text[a:b].rstrip() + '\n\n' + tech_text(tid, folder, fmt(ax), self.y_value(ay), '1', year, categories)
        self.apply(self.text[:a] + body + self.text[b:])
        if prereq:
            self.link_path(prereq, tid)

    def link_path(self, src, target):
        t = self.focuses[src]
        if target not in [x for x, _ in t['leads']]:
            self.set_values(src, {'path': path_values(t['leads'] + [(target, '1')])})

    def link_mutex(self, a, b):
        for x, y in ((a, b), (b, a)):
            m = self.focuses[x]['xor']
            if y not in m:
                self.set_values(x, {'xor': ['{ ' + ' '.join(m + [y]) + ' }']})

    def duplicate(self, tid, new_id):
        t = self.focuses[tid]
        block = self.text[t['start']:t['end']]
        block = re.sub(r'^' + re.escape(t['id']) + r'(?=\s*=)', new_id, block, count=1)
        block = re.sub(r'\n\s*path\s*=\s*\{[^{}]*\}', '', block)  # the copy starts without links
        s, e = spans(self.text, 'technologies')[t['tree']]
        a, b = inner(self.text, (s, e))
        self.apply(self.text[:b].rstrip() + '\n\n\t' + block + '\n' + self.text[b:])
        self.move(new_id, t['x'] + 2, t['y'])

    def delete(self, tid):
        """Remove a tech and every path and xor pointing at it in this file."""
        t = self.focuses[tid]
        real, text = t['id'], self.text
        for oid, o in self.focuses.items():
            if oid == tid:
                continue
            values = {}
            if real in [x for x, _ in o['leads']]:
                values['path'] = path_values([(x, c) for x, c in o['leads'] if x != real])
            if real in o['xor']:
                rest = [m for m in o['xor'] if m != real]
                values['xor'] = ['{ ' + ' '.join(rest) + ' }'] if rest else None
            if values:
                text = self._edit_focus(text, oid, lambda body, v=values: self._apply_values(body, v))
        _, s, e, _ = next(blk for blk in tech_blocks(text) if blk[0] == real)
        line = text.rfind('\n', 0, s) + 1
        s = line if not text[line:s].strip() else s
        e = e + 1 if text[e:e + 1] == '\n' else e
        self.apply(text[:s] + text[e:])


def inner_text(text, key):
    span = top_span(text, key)
    a, b = inner(text, span)
    return text[a:b]


def tech_point_days(mod):
    """Days of research per research_cost point with 1 slot and no bonuses: NDefines.NTechnology.BASE_TECH_COST
    (last file wins), else vanilla's 100."""
    days = 100.0
    for f in mod.files('common/defines', '.lua'):
        for m in re.finditer(r'^[^-\n]*BASE_TECH_COST\s*=\s*(\d+(?:\.\d+)?)', read_text(f), re.M):
            days = float(m.group(1))
    return days


def research_days(t, per_cost):
    try:
        return float(t['cost'] or 1) * per_cost
    except ValueError:
        return per_cost


def earliest_days(tf, per_cost):
    """Days until each tech can be finished at the earliest with one slot: its own time plus its quickest
    incoming line (any one researched tech leading to it unlocks it)."""
    memo = {}

    def go(tid, seen):
        if tid not in memo:
            t = tf.focuses[tid]
            options = [go(p, seen | {tid}) for p in t['from'] if p in tf.focuses and p not in seen]
            memo[tid] = (min(options) if options else 0.0) + research_days(t, per_cost)
        return memo[tid]

    for tid in tf.focuses:
        go(tid, frozenset())
    return memo


def tech_tags(mod):
    """(folder names, category names) from common/technology_tags."""
    folders, cats = set(), set()
    for f in mod.files('common/technology_tags'):
        items = parse(read_text(f))
        for k, v in items:
            if k == 'technology_folders' and isinstance(v, list):
                folders |= {name if name else val for name, val in v}
            elif k == 'technology_categories' and isinstance(v, list):
                cats |= {val if not name else name for name, val in v}
    return folders, cats


def all_tech_ids(mod, skip=None):
    """id -> file for every tech in the mod's other tech files."""
    out = {}
    for f in mod.files('common/technologies'):
        if skip and os.path.abspath(f) == os.path.abspath(skip):
            continue
        for tid, *_ in tech_blocks(read_text(f)):
            out.setdefault(tid, f)
    return out


def check(tf, mod, sprites=None, others=None, tags=None, game_loc=frozenset()):
    """Problems as (level, tech id or '', message, fix or None). level: error / warning.
    game_loc: localisation keys of the base game, for vanilla techs copied into the mod."""
    sprites = sprites if sprites is not None else mod.sprites
    others = all_tech_ids(mod, tf.path) if others is None else others
    folders, cats = tags if tags is not None else tech_tags(mod)
    out = []
    broken = brace_problem(tf.text)
    if broken:  # everything after a missing brace is misread, so other checks would only add noise
        return [('error', '', broken[1] + '. Double-click to open the file text there. '
                 '(Other checks wait until this is fixed.)', None)]
    if not tf.trees:
        out.append(('error', '', 'No technologies = { } block in this file', None))
    known = set(others) | {t['id'] for t in tf.focuses.values()}
    subs = {s for t in tf.focuses.values() for s in t['subs']}
    pos = {}
    for tid, t in tf.focuses.items():
        real = t['id']
        if t.get('duplicate'):
            out.append(('error', tid, f'Tech {real} is defined twice in this file', None))
        if real in others:
            out.append(('error', tid, f'Tech {real} also exists in {os.path.basename(others[real])}', None))
        for target, _ in t['leads']:
            if not target:
                out.append(('error', tid, 'A path = { } has no leads_to_tech', None))
            elif target not in known:
                out.append(('error', tid, f'Path leads to {target}, which does not exist',
                            lambda tid=tid, x=target: tf.set_values(tid, {'path': path_values(
                                [(a, c) for a, c in tf.focuses[tid]['leads'] if a != x])})))
            elif target in tf.focuses and tf.focuses[target]['folder'] == t['folder'] \
                    and tf.focuses[target]['y'] < t['y']:
                out.append(('warning', tid, f'Leads to {target}, which is placed before it (the line goes backward)', None))
        for m in t['xor']:
            if m not in known:
                out.append(('error', tid, f'xor with {m}, which does not exist', None))
            elif m in tf.focuses and real not in tf.focuses[m]['xor']:
                out.append(('warning', tid, f'xor with {m}, but {m} does not list it back',
                            lambda a=tid, b=m: tf.link_mutex(a, b)))
        for d in t['deps']:
            if d not in known:
                out.append(('error', tid, f'Depends on {d}, which does not exist', None))
        for c in t['cats']:
            if cats and c not in cats:
                out.append(('warning', tid, f'Category {c} is not in common/technology_tags', None))
        if t['folder']:
            if folders and t['folder'] not in folders:
                out.append(('error', tid, f'Folder {t["folder"]} is not in common/technology_tags technology_folders', None))
            for axis in ('xraw', 'yraw'):
                if str(t[axis]).startswith('@') and t[axis] not in tf.vars:
                    out.append(('error', tid, f'Position uses {t[axis]}, which is not defined in this file', None))
            key = (t['folder'], t['x'], t['y'])
            if key in pos:
                out.append(('warning', tid, f'Same place as {pos[key]} in {t["folder"]}', None))
            pos.setdefault(key, tid)
        elif real not in subs and not t['special']:
            out.append(('warning', tid, 'No folder: it does not show in the tech screen', None))
        for key, what in ((real, 'name'), (f'{real}_desc', 'description')):
            if key in mod.loc_broken:
                bf, line = mod.loc_broken[key]
                out.append(('error', tid, f'Broken {what} localisation line (missing closing quote?) in '
                                          f'{os.path.basename(bf)} line {line}', None))
            elif key not in mod.loc and key not in game_loc and (what == 'name' or t['folder']):
                out.append(('warning', tid, f'No {what} localisation ({key})', None))
        if t['folder'] and t['icon'] not in sprites:
            out.append(('warning', tid, f'No icon: {t["icon"]} is not defined in interface/*.gfx'
                                        + ('' if sprites is not mod.sprites else ' (set the game folder to see vanilla icons)'), None))
        if not t['cost']:
            out.append(('warning', tid, 'No research_cost', None))
    if tf.closed_at_end:
        out.append(('warning', '', f'The file ends without its last "}}" ({tf.closed_at_end} missing). HOI4 accepts '
                                   'that, so the editor added it too; Save writes it to the file.', None))
    return out


def tech_sprites(game_dir):
    """Vanilla tech icon sprites (name -> absolute texture path) from the game's interface/*.gfx."""
    out = {}
    folder = os.path.join(game_dir or '', 'interface')
    if not game_dir or not os.path.isdir(folder):
        return out
    for n in os.listdir(folder):
        if n.endswith('.gfx'):
            for m in re.finditer(r'name\s*=\s*"(GFX_\w+_medium)"\s*texturefile\s*=\s*"([^"]+)"',
                                 read_text(os.path.join(folder, n)), re.I):
                out[m.group(1)] = os.path.join(game_dir, m.group(2))
    return out


def game_loc_keys(game_dir):
    """Every English localisation key of the base game (empty without a game folder)."""
    folder = os.path.join(game_dir or '', 'localisation', 'english')
    keys = set()
    if game_dir and os.path.isdir(folder):
        for dirpath, _, names in os.walk(folder):
            for n in names:
                if n.endswith('.yml'):
                    keys |= set(re.findall(r'^\s*([\w.\-]+):\d*\s*"', read_text(os.path.join(dirpath, n)), re.M))
    return keys


def import_tech_icon(mod, src, tid):
    """Convert an image to gfx/interface/technologies/<tid>.dds and register GFX_<tid>_medium. Returns the sprite."""
    from PIL import Image
    sprite, rel = f'GFX_{tid}_medium', f'gfx/interface/technologies/{tid}.dds'
    os.makedirs(os.path.dirname(mod.path(rel)), exist_ok=True)
    img = Image.open(src).convert('RGBA')
    img.thumbnail(ICON_SIZE, Image.LANCZOS)
    canvas = Image.new('RGBA', ICON_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(img, ((ICON_SIZE[0] - img.width) // 2, (ICON_SIZE[1] - img.height) // 2))
    canvas.save(mod.path(rel))
    gfx = next((f for f in mod.files('interface', '.gfx') if 'technolog' in os.path.basename(f).lower()),
               mod.path('interface', 'tech_editor_technologies.gfx'))
    text = read_text(gfx) if os.path.exists(gfx) else ''
    if f'"{sprite}"' not in text:
        key = next((k for k in ('spriteTypes', 'SpriteTypes', 'spritetypes') if top_span(text, k)), 'spriteTypes')
        write_text(gfx, add_to_block(text, key, f'\tspriteType = {{\n\t\tname = "{sprite}"\n\t\ttexturefile = "{rel}"\n\t}}'))
    mod.sprites[sprite] = rel
    return sprite


def add_auto_names(tf, mod, path):
    """Write a name for every tech of the file that has none, in one write."""
    new = [(t['id'], auto_name(t['id'])) for t in tf.focuses.values()
           if t['id'] and t['id'] not in mod.loc and t['id'] not in mod.loc_broken]
    if not new:
        return 0
    text = read_text(path) if os.path.exists(path) else 'l_english:\n'
    text = text.rstrip('\n') + '\n' + ''.join(f' {k}:0 "{v}"\n' for k, v in new)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_text(path, text)
    for k, v in new:
        mod.loc[k], mod.loc_file[k] = v, path
    return len(new)


# ---------------------------------------------------------------- GUI

def run_gui(mod_root):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    try:
        from PIL import Image, ImageTk
    except ImportError:
        Image = None

    root = tk.Tk()
    root.title('HOI4 Tech Tree Editor')
    root.geometry('1600x950')
    if not mod_root:
        mod_root = filedialog.askdirectory(title='Pick your mod folder (the one with common/, history/, gfx/)')
        if not mod_root:
            return
    mod = Mod(mod_root)
    settings = load_settings()
    per_cost = tech_point_days(mod)
    cal = hod_calendar(mod) or settings.get('calendar')
    year_len = cal['months'] * cal['month_days'] + cal['fest_days'] if cal else 365
    tags = tech_tags(mod)
    st = {'tf': None, 'sel': None, 'zoom': 0.9, 'link': None, 'drag': None, 'folder': '',
          'vanilla': tech_sprites(settings.get('game_dir')), 'game_loc': game_loc_keys(settings.get('game_dir'))}
    icons = {}

    def sprite_file(name):
        if name in mod.sprites:
            game = os.path.join(settings.get('game_dir') or '', mod.sprites[name])
            return mod.find(mod.sprites[name]) or (game if settings.get('game_dir') and os.path.exists(game) else None)
        return st['vanilla'].get(name) if os.path.exists(st['vanilla'].get(name, '')) else None

    def icon_photo(name, size):
        if (name, size) not in icons:
            icons[name, size] = None
            f = sprite_file(name)
            if f and Image:
                try:
                    img = Image.open(f).convert('RGBA')
                    img.thumbnail(size, Image.LANCZOS)
                    icons[name, size] = ImageTk.PhotoImage(img)
                except OSError:
                    pass
        return icons[name, size]

    def all_sprites():
        return {**st['vanilla'], **mod.sprites}

    # ---------------- toolbar
    bar = ttk.Frame(root, padding=4)
    bar.pack(fill='x')
    files = [os.path.relpath(f, mod.root) for f in mod.files('common/technologies')]
    file_pick = ttk.Combobox(bar, values=files, state='readonly', width=40)
    file_pick.pack(side='left')
    ttk.Label(bar, text=' Folder').pack(side='left')
    folder_pick = ttk.Combobox(bar, state='readonly', width=24)
    folder_pick.pack(side='left', padx=2)

    def open_events_editor():
        from hoi4_event_editor import run_editor
        run_editor(mod.root, root, 'REP')

    def open_focus_editor():
        from hoi4_focus_editor import run_gui
        run_gui(mod.root)

    def open_country_editor():
        from hoi4_country_editor import run_gui
        run_gui(mod.root)

    ttk.Button(bar, text='Events & decisions', command=open_events_editor).pack(side='right', padx=2)
    ttk.Button(bar, text='Focus tree', command=open_focus_editor).pack(side='right', padx=2)
    ttk.Button(bar, text='Country', command=open_country_editor).pack(side='right', padx=2)
    status = ttk.Label(root, anchor='w')
    status.pack(side='bottom', fill='x')

    panes = tk.PanedWindow(root, orient='horizontal', sashwidth=6, sashrelief='raised')
    panes.pack(fill='both', expand=True)
    left = ttk.Frame(panes)
    panes.add(left, width=1050, minsize=400, stretch='always')
    right = ttk.Frame(panes)
    panes.add(right, width=520, minsize=380, stretch='never')
    vpanes = tk.PanedWindow(left, orient='vertical', sashwidth=6, sashrelief='raised')
    vpanes.pack(fill='both', expand=True)
    cframe = ttk.Frame(vpanes)
    vpanes.add(cframe, height=700, minsize=200, stretch='always')
    canvas = tk.Canvas(cframe, background='#23282f', highlightthickness=0)
    hs = ttk.Scrollbar(cframe, orient='horizontal', command=canvas.xview)
    vs = ttk.Scrollbar(cframe, orient='vertical', command=canvas.yview)
    canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
    hs.pack(side='bottom', fill='x')
    vs.pack(side='right', fill='y')
    canvas.pack(fill='both', expand=True)
    pframe = ttk.Frame(vpanes)
    vpanes.add(pframe, height=180, minsize=80, stretch='never')
    plabel = ttk.Label(pframe, text='Problems')
    plabel.pack(fill='x', padx=4)
    problems = ttk.Treeview(pframe, columns=('level', 'tech', 'problem'), show='headings', height=6)
    for col, w in (('level', 70), ('tech', 260), ('problem', 700)):
        problems.heading(col, text=col)
        problems.column(col, width=w, stretch=col == 'problem')
    problems.tag_configure('error', foreground='#c00000')
    problems.tag_configure('warning', foreground='#a06000')
    psb = ttk.Scrollbar(pframe, command=problems.yview)
    problems.configure(yscrollcommand=psb.set)
    psb.pack(side='right', fill='y')
    problems.pack(fill='both', expand=True)
    fixes = {}

    # ---------------- drawing
    def shown():
        tf = st['tf']
        return {tid: t for tid, t in tf.focuses.items() if t['folder'] == st['folder']} if tf else {}

    def origin():
        tf = st['tf']
        ts = shown().values()
        return min((t['x'] for t in ts), default=0), min((t['y'] for t in ts), default=0)

    def pos(t):
        z, (ox, oy) = st['zoom'], origin()
        return (t['y'] - oy) * UY * z + 70 * z, (t['x'] - ox) * UX * z + 60 * z

    def redraw():
        canvas.delete('all')
        tf = st['tf']
        if not tf:
            return
        z = st['zoom']
        w, h = BW * z, BH * z
        here = shown()
        ox, oy = origin()
        small = ('Segoe UI', max(6, int(7 * z)))
        # columns named by the file's @variables (the mod uses them for years)
        for k, v in sorted(tf.vars.items(), key=lambda kv: tf.num(kv[1])):
            cx = (tf.num(v) - oy) * UY * z + 70 * z
            if cx >= 0 and any(t['y'] == tf.num(v) for t in here.values()):
                canvas.create_text(cx, 8, anchor='n', text=k.lstrip('@'), fill='#7d8796', font=small)
                canvas.create_line(cx, 24 * z, cx, 4000 * z, fill='#2f3540', dash=(2, 6))
        by_id = {t['id']: t for t in here.values()}
        for tid, t in here.items():
            x, y = pos(t)
            for target, _ in t['leads']:
                if target in by_id:
                    tx, ty = pos(by_id[target])
                    canvas.create_line(x + w / 2, y, (x + tx) / 2, y, (x + tx) / 2, ty, tx - w / 2, ty,
                                       fill='#d8c890', width=2, arrow='last')
                else:
                    other = tf.focuses.get(target, {}).get('folder') or 'another file'
                    canvas.create_text(x + w / 2 + 4, y, anchor='w', text=f'→ {target} ({other})', fill='#a0b8d0',
                                       font=small)
            for m in t['xor']:
                if m in by_id and m > t['id']:
                    mx, my = pos(by_id[m])
                    canvas.create_line(x, y, mx, my, fill='#e04040', width=2)
                    canvas.create_text((x + mx) / 2, (y + my) / 2, text='⊘', fill='#ff6060',
                                       font=('Segoe UI', int(14 * z) or 1))
        for tid, t in here.items():
            x, y = pos(t)
            sel = tid == st['sel']
            fill = '#5a4a70' if t['doctrine'] else '#3d4757'
            canvas.create_rectangle(x - w / 2, y - h / 2, x + w / 2, y + h / 2, fill='#5a6a90' if sel else fill,
                                    outline='#ffd040' if sel else '#8890a0', width=3 if sel else 1, tags=('tech', tid))
            img = icon_photo(t['icon'], (int(44 * z) or 1, int(30 * z) or 1))
            if img:
                canvas.create_image(x, y - h / 2 + 18 * z, image=img, tags=('tech', tid))
            canvas.create_text(x, y + h / 2 - 15 * z, text=mod.loc.get(t['id'], t['id']), width=w - 4, fill='white',
                               font=('Segoe UI', max(6, int(8 * z))), tags=('tech', tid))
            canvas.create_text(x + w / 2 - 3, y - h / 2 + 2, anchor='ne', fill='#c8d0e0', font=small, tags=('tech', tid),
                               text=f'{t["year"]}' if t['year'] else '')
            canvas.create_text(x - w / 2 + 3, y - h / 2 + 2, anchor='nw', fill='#c8d0e0', font=small, tags=('tech', tid),
                               text=f'{t["cost"] or "?"}')
        canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 1, 1))
        root.title(f'HOI4 Tech Tree Editor - {os.path.relpath(tf.path, mod.root)}' + (' *' if tf.dirty else ''))

    def refresh_folders():
        tf = st['tf']
        names = sorted({t['folder'] for t in tf.focuses.values()}, key=lambda n: (n == '', n)) if tf else []
        names = names or ['']
        folder_pick['values'] = [n or '(no folder)' for n in names]
        if st['folder'] not in names:
            st['folder'] = names[0]
        folder_pick.set(st['folder'] or '(no folder)')

    def refresh_problems():
        tf = st['tf']
        problems.delete(*problems.get_children())
        fixes.clear()
        if not tf:
            return
        out = check(tf, mod, all_sprites(), st.get('others'), tags, st['game_loc'])
        out.sort(key=lambda p: (p[0] != 'error', p[1]))
        for i, (lvl, tid, msg, fix) in enumerate(out):
            problems.insert('', 'end', iid=str(i), values=(lvl, tid, msg + ('   [double-click to fix]' if fix else '')),
                            tags=(lvl,))
            fixes[str(i)] = (tid, fix)
        errs = sum(1 for p in out if p[0] == 'error')
        plabel.configure(text=f'Problems: {errs} errors, {len(out) - errs} warnings   '
                              '(double-click a row to go to the tech or apply its fix)')

    def changed(keep_form=False):
        refresh_folders()
        redraw()
        refresh_problems()
        if not keep_form:
            fill_form()

    # ---------------- tech form
    form = ttk.Frame(right, padding=6)
    form.pack(fill='both', expand=True)
    fv = {k: tk.StringVar() for k in ('id', 'name', 'folder', 'x', 'y', 'cost', 'year', 'cats', 'xor')}
    r = 0
    for key, label in (('id', 'Tech id'), ('name', 'Name')):
        ttk.Label(form, text=label).grid(row=r, column=0, sticky='w')
        ttk.Entry(form, textvariable=fv[key], width=44).grid(row=r, column=1, columnspan=2, sticky='we', pady=1)
        r += 1
    ttk.Button(form, text='Auto', width=5, command=lambda: fv['name'].set(auto_name(fv['id'].get().strip()))).grid(
        row=r - 1, column=3, sticky='w')
    ttk.Label(form, text='Description').grid(row=r, column=0, sticky='nw')
    desc = tk.Text(form, height=3, width=44, wrap='word', font=('Segoe UI', 9))
    desc.grid(row=r, column=1, columnspan=3, sticky='we', pady=1)
    r += 1
    ttk.Label(form, text='Icon').grid(row=r, column=0, sticky='w')
    icon_row = ttk.Frame(form)
    icon_row.grid(row=r, column=1, columnspan=3, sticky='w')
    icon_prev = ttk.Label(icon_row)
    icon_prev.pack(side='left')
    ttk.Button(icon_row, text='Import image...', command=lambda: import_icon_dialog()).pack(side='left', padx=6)
    icon_name = ttk.Label(icon_row, foreground='#555')
    icon_name.pack(side='left')
    r += 1
    ttk.Label(form, text='Folder').grid(row=r, column=0, sticky='w')
    folder_box = ttk.Combobox(form, textvariable=fv['folder'], values=sorted(tags[0]), width=30)
    folder_box.grid(row=r, column=1, columnspan=2, sticky='w', pady=1)
    r += 1
    ttk.Label(form, text='Position x / y').grid(row=r, column=0, sticky='w')
    xy = ttk.Frame(form)
    xy.grid(row=r, column=1, columnspan=3, sticky='w')
    ttk.Entry(xy, textvariable=fv['x'], width=7).pack(side='left')
    y_box = ttk.Combobox(xy, textvariable=fv['y'], width=9)
    y_box.pack(side='left', padx=4)
    ttk.Label(xy, foreground='#777', text='y = column: number or @year').pack(side='left')
    r += 1
    ttk.Label(form, text='Research cost').grid(row=r, column=0, sticky='w')
    cy = ttk.Frame(form)
    cy.grid(row=r, column=1, columnspan=3, sticky='w')
    ttk.Entry(cy, textvariable=fv['cost'], width=7).pack(side='left')
    ttk.Label(cy, text='  start year').pack(side='left')
    ttk.Entry(cy, textvariable=fv['year'], width=7).pack(side='left', padx=4)
    r += 1
    duration = ttk.Label(form, foreground='#555', wraplength=400, justify='left')
    duration.grid(row=r, column=1, columnspan=3, sticky='w')
    r += 1
    ttk.Label(form, text='Categories').grid(row=r, column=0, sticky='w')
    ttk.Entry(form, textvariable=fv['cats'], width=44).grid(row=r, column=1, columnspan=3, sticky='we', pady=1)
    r += 1
    ttk.Label(form, text='Leads to').grid(row=r, column=0, sticky='nw')
    leads = tk.Text(form, height=3, width=44, font=('Consolas', 9))
    leads.grid(row=r, column=1, columnspan=3, sticky='we', pady=1)
    r += 1
    ttk.Label(form, foreground='#777', text='one tech per line, then optionally its cost coeff'
              ).grid(row=r, column=1, columnspan=3, sticky='w')
    r += 1
    ttk.Label(form, text='Exclusive (xor)').grid(row=r, column=0, sticky='w')
    ttk.Entry(form, textvariable=fv['xor'], width=44).grid(row=r, column=1, columnspan=3, sticky='we', pady=1)
    r += 1
    fb = ttk.Frame(form)
    fb.grid(row=r, column=0, columnspan=4, sticky='w', pady=6)
    ttk.Button(fb, text='Apply', command=lambda: apply_form()).pack(side='left')
    ttk.Button(fb, text='Add next tech', command=lambda: add_child()).pack(side='left', padx=4)
    ttk.Button(fb, text='Duplicate', command=lambda: duplicate()).pack(side='left')
    ttk.Button(fb, text='Delete', command=lambda: delete()).pack(side='left', padx=4)
    r += 1
    ttk.Label(form, text='Tech script (effects, equipment, units, modifiers, ai_will_do... everything)').grid(
        row=r, column=0, columnspan=4, sticky='w', pady=(8, 0))
    r += 1
    script = tk.Text(form, height=16, width=60, wrap='none', undo=True, font=('Consolas', 9))
    script.grid(row=r, column=0, columnspan=4, sticky='nsew')
    form.rowconfigure(r, weight=1)
    form.columnconfigure(1, weight=1)
    r += 1
    ttk.Button(form, text='Apply script', command=lambda: apply_script()).grid(row=r, column=0, sticky='w', pady=4)
    summary = ttk.Label(form, foreground='#555', wraplength=400, justify='left')
    summary.grid(row=r + 1, column=0, columnspan=4, sticky='w')

    def loc_file():
        """Where new tech texts go: the file already holding most of this file's texts, else one named after it."""
        from collections import Counter
        used = Counter(mod.loc_file[t['id']] for t in st['tf'].focuses.values() if t['id'] in mod.loc_file)
        if used:
            return used.most_common(1)[0][0]
        stem = re.sub(r'\W+', '_', os.path.splitext(os.path.basename(st['tf'].path))[0])
        return mod.path('localisation', 'english', f'{stem}_l_english.yml')

    def fill_summary():
        tf = st['tf']
        here = shown()
        total = sum(research_days(t, per_cost) for t in here.values())
        summary.configure(text=(
            f'1 research cost = {per_cost:g} days with one slot and no research bonuses (BASE_TECH_COST).\n'
            f'Folder {st["folder"] or "(none)"}: {len(here)} techs, {fmt_days(total, year_len)} with one slot'
            + (f', about {fmt_days(total / 3, year_len)} with 3 slots' if here else '')
            + ('. Years use the mod calendar.' if cal else '.')) if tf else '')

    def fill_form():
        tf, tid = st['tf'], st['sel']
        t = tf.focuses.get(tid) if tf else None
        for v in fv.values():
            v.set('')
        for box in (desc, leads, script):
            box.delete('1.0', 'end')
        icon_prev.configure(image='')
        icon_name.configure(text='')
        duration.configure(text='')
        fill_summary()
        if not t:
            return
        early = earliest_days(tf, per_cost)
        duration.configure(text=f'= {fmt_days(research_days(t, per_cost), year_len)} of research; done at the earliest '
                                f'after {fmt_days(early[tid], year_len)} through its quickest line'
                                + (f'\nunlocked by: {", ".join(t["from"])}' if t['from'] else '\nstarts a line'))
        fv['id'].set(t['id'])
        fv['name'].set(mod.loc.get(t['id'], ''))
        desc.insert('1.0', mod.loc.get(f'{t["id"]}_desc', '').replace('\\n', '\n'))
        fv['folder'].set(t['folder'])
        fv['x'].set(t['xraw'])
        fv['y'].set(t['yraw'])
        y_box['values'] = sorted(tf.vars, key=lambda k: tf.num(tf.vars[k]))
        fv['cost'].set(t['cost'])
        fv['year'].set(t['year'])
        fv['cats'].set(' '.join(t['cats']))
        fv['xor'].set(' '.join(t['xor']))
        leads.insert('1.0', '\n'.join(x if c in ('1', '', None) else f'{x} {c}' for x, c in t['leads']))
        script.insert('1.0', tf.text[t['start']:t['end']])
        icon_prev.configure(image=icon_photo(t['icon'], ICON_SIZE) or '')
        icon_name.configure(text=t['icon'] + ('' if t['icon'] in all_sprites() else '  (missing)'))

    def apply_form():
        tf, tid = st['tf'], st['sel']
        if not tf or tid not in tf.focuses:
            return
        t = tf.focuses[tid]
        new_id = fv['id'].get().strip()
        new_leads = []
        for line in leads.get('1.0', 'end').splitlines():
            parts = line.replace(',', ' ').split()
            if parts:
                new_leads.append((parts[0], parts[1] if len(parts) > 1 else '1'))
        xor = fv['xor'].get().replace(',', ' ').split()
        known = set(tf.focuses) | set(st.get('others') or {})
        unknown = [x for x, _ in new_leads if x not in known] + [m for m in xor if m not in known]
        if unknown and not messagebox.askyesno('Unknown tech', f'Not found in the mod: {", ".join(unknown)}. Apply anyway?'):
            return
        x, y = fv['x'].get().strip() or '0', fv['y'].get().strip() or '0'
        for label, v in (('x', x), ('y', y), ('research cost', fv['cost'].get().strip() or '0'),
                         ('start year', fv['year'].get().strip() or '0')):
            if not re.fullmatch(r'-?\d+(\.\d+)?', v) and not (label in 'xy' and v in tf.vars):
                messagebox.showerror('Not applied', f'{label} must be a number' + (' or a defined @variable' if label in 'xy' else ''))
                return
        values = {'research_cost': fv['cost'].get().strip() or None, 'start_year': fv['year'].get().strip() or None}
        if new_leads != t['leads']:
            values['path'] = path_values(new_leads)
        if xor != t['xor']:
            values['xor'] = ['{ ' + ' '.join(xor) + ' }'] if xor else None
        cats = fv['cats'].get().replace(',', ' ').split()
        if cats != t['cats']:
            values['categories'] = ['{ ' + ' '.join(cats) + ' }'] if cats else None
        tf.set_values(tid, values)
        folder = fv['folder'].get().strip()
        if folder and (folder, x, y) != (t['folder'], t['xraw'], t['yraw']):
            tf.place(tid, folder, x, y)
            st['folder'] = folder
        for m in xor:  # exclusivity has to be listed on both sides
            if m in tf.focuses and t['id'] not in tf.focuses[m]['xor']:
                tf.link_mutex(tid, m)
        name, text = fv['name'].get().strip(), desc.get('1.0', 'end').strip().replace('\n', '\\n')
        real = t['id']
        if new_id and new_id != real:
            if new_id in tf.focuses or new_id in (st.get('others') or {}):
                messagebox.showerror('Rename', f'{new_id} is already used')
            elif re.fullmatch(r'[A-Za-z0-9_.\-]+', new_id):
                tf.rename(real, new_id)
                for old_key in (real, f'{real}_desc'):
                    if old_key in mod.loc:
                        set_loc(mod, old_key, '', loc_file())
                real = st['sel'] = new_id
        if name != mod.loc.get(real, ''):
            set_loc(mod, real, name.replace('"', "'"), mod.loc_file.get(real) or loc_file())
        if text != mod.loc.get(f'{real}_desc', ''):
            set_loc(mod, f'{real}_desc', text.replace('"', "'"), mod.loc_file.get(f'{real}_desc') or loc_file())
        status['text'] = f'Applied {real}. Localisation is saved at once; the tech file on Save (Ctrl+S).'
        changed()

    def apply_script():
        tf, tid = st['tf'], st['sel']
        if not tf or tid not in tf.focuses:
            return
        body = script.get('1.0', 'end').rstrip()
        if brace_depth(body) != 0:
            messagebox.showerror('Not applied', 'The braces { } in this script do not match.')
            return
        m = re.match(r'\s*([A-Za-z0-9_.\-]+)\s*=\s*\{', body)
        if not m or len(top_blocks(body)) != 1:
            messagebox.showerror('Not applied', 'The script must stay a single tech_id = { ... } block.')
            return
        t = tf.focuses[tid]
        tf.apply(tf.text[:t['start']] + body + tf.text[t['end']:])
        st['sel'] = m.group(1) if m.group(1) in tf.focuses else None
        changed()

    def new_id(base):
        tf = st['tf']
        i = 1
        while f'{base}_{i}' in tf.focuses or f'{base}_{i}' in (st.get('others') or {}):
            i += 1
        return f'{base}_{i}'

    def add_child(at=None):
        tf = st['tf']
        if not tf or not tf.trees:
            return
        parent = tf.focuses.get(st['sel'])
        tid = new_id(f'{parent["id"]}_next' if parent else 'new_tech')
        if at:
            ax, ay = at
        elif parent:
            rows = sorted({tf.num(v) for v in tf.vars.values()})
            later = [r for r in rows if r > parent['y']]
            ax, ay = parent['x'], later[0] if later else parent['y'] + 3
            while any(o['folder'] == parent['folder'] and o['x'] == ax and o['y'] == ay for o in tf.focuses.values()):
                ax += 1
        else:
            ax, ay = 0, 0
        folder = parent['folder'] if parent else st['folder'] or (sorted(tags[0]) or [''])[0]
        tf.add_focus(tid, ax, ay, prereq=st['sel'] if parent and not at else None,
                     tree=parent['tree'] if parent else 0, folder=folder,
                     categories=parent['cats'] if parent else ())
        st['sel'], st['folder'] = tid, folder
        changed()

    def duplicate():
        tf, tid = st['tf'], st['sel']
        if tf and tid in tf.focuses:
            nid = new_id(tf.focuses[tid]['id'])
            tf.duplicate(tid, nid)
            st['sel'] = nid
            changed()

    def delete():
        tf, tid = st['tf'], st['sel']
        if tf and tid in tf.focuses and messagebox.askyesno('Delete', f'Delete {tid} and the paths to it?'):
            tf.delete(tid)
            st['sel'] = None
            changed()

    def import_icon_dialog():
        tf, tid = st['tf'], st['sel']
        if not tf or tid not in tf.focuses or not Image:
            return
        src = filedialog.askopenfilename(title='Tech icon image (PNG with transparency is best)',
                                         filetypes=[('Images', '*.png *.dds *.tga *.jpg *.jpeg *.webp'), ('All', '*')])
        if not src:
            return
        try:
            sprite = import_tech_icon(mod, src, tf.focuses[tid]['id'])
        except OSError as e:
            messagebox.showerror('Import icon', f'Cannot read this image: {e}')
            return
        icons.clear()
        status['text'] = f'Imported {sprite}: .dds written and sprite registered.'
        changed()

    # ---------------- canvas interaction
    def tech_at(e):
        x, y = canvas.canvasx(e.x), canvas.canvasy(e.y)
        for it in reversed(canvas.find_overlapping(x, y, x, y)):
            tags_ = canvas.gettags(it)
            if 'tech' in tags_:
                return tags_[1]
        return None

    def grid_at(e):
        z, (ox, oy) = st['zoom'], origin()
        return (round((canvas.canvasy(e.y) - 60 * z) / (UX * z)) + ox,
                round((canvas.canvasx(e.x) - 70 * z) / (UY * z)) + oy)

    def on_press(e):
        tid = tech_at(e)
        tf = st['tf']
        if st['link'] and tid and tf:
            kind, src = st['link']
            st['link'] = None
            canvas.configure(cursor='')
            if tid != src:
                if kind == 'path':
                    tf.link_path(src, tf.focuses[tid]['id'])
                else:
                    tf.link_mutex(src, tid)
                changed()
            return
        st['sel'] = tid
        st['drag'] = (tid, grid_at(e)) if tid else None
        fill_form()
        redraw()

    def on_release(e):
        tf, drag = st['tf'], st['drag']
        st['drag'] = None
        if not tf or not drag:
            return
        tid, start = drag
        gx, gy = grid_at(e)
        if (gx, gy) != start and tid in tf.focuses:
            t = tf.focuses[tid]
            ny = t['y'] + gy - start[1]
            rows = sorted({tf.num(v) for v in tf.vars.values()})
            if rows and str(t['yraw']).startswith('@'):  # snap to the nearest @ year column
                ny = min(rows, key=lambda r: abs(r - ny))
            tf.move(tid, t['x'] + gx - start[0], ny)
            changed()

    def on_motion(e):
        tid = tech_at(e)
        tf = st['tf']
        gx, gy = grid_at(e)
        status['text'] = (f'{tid}  (x {tf.focuses[tid]["xraw"]}, y {tf.focuses[tid]["yraw"]})' if tf and tid
                          else f'grid ({fmt(gx)}, {fmt(gy)})') + ('   - click the other tech to link' if st['link'] else '')

    def start_link(kind):
        if st['sel']:
            st['link'] = (kind, st['sel'])
            canvas.configure(cursor='crosshair')
            status['text'] = 'Click the tech to link to (Esc cancels).'

    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label='Add next tech (next column)', command=lambda: add_child())
    menu.add_command(label='Add path (leads to)...', command=lambda: start_link('path'))
    menu.add_command(label='Make exclusive (xor) with...', command=lambda: start_link('xor'))
    menu.add_command(label='Duplicate', command=lambda: duplicate())
    menu.add_separator()
    menu.add_command(label='Delete', command=lambda: delete())
    empty_menu = tk.Menu(root, tearoff=0)

    def on_right(e):
        tid = tech_at(e)
        if tid:
            st['sel'] = tid
            fill_form()
            redraw()
            menu.tk_popup(e.x_root, e.y_root)
        elif st['tf']:
            at = grid_at(e)
            empty_menu.delete(0, 'end')
            empty_menu.add_command(label=f'Add tech here ({fmt(at[0])}, {fmt(at[1])})',
                                   command=lambda: (st.update(sel=None), add_child(at)))
            empty_menu.tk_popup(e.x_root, e.y_root)

    canvas.bind('<ButtonPress-1>', on_press)
    canvas.bind('<ButtonRelease-1>', on_release)
    canvas.bind('<Motion>', on_motion)
    canvas.bind('<Button-3>', on_right)
    canvas.bind('<MouseWheel>', lambda e: (canvas.xview_scroll if e.state & 1 else canvas.yview_scroll)(
        -1 if e.delta > 0 else 1, 'units'))
    canvas.bind('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
    canvas.bind('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))
    canvas.bind('<ButtonPress-2>', lambda e: canvas.scan_mark(e.x, e.y))
    canvas.bind('<B2-Motion>', lambda e: canvas.scan_dragto(e.x, e.y, gain=1))
    root.bind('<Escape>', lambda e: (st.update(link=None), canvas.configure(cursor='')))

    def on_problem(_):
        sel = problems.selection()
        if not sel:
            return
        tid, fix = fixes[sel[0]]
        line = re.search(r'line (\d+)', problems.item(sel[0], 'values')[2])
        tf = st['tf']
        if fix:
            fix()
            changed()
        elif not tid and line:
            edit_file_text(int(line.group(1)))
        elif tid in tf.focuses:
            st['sel'], st['folder'] = tid, tf.focuses[tid]['folder']
            changed()

    problems.bind('<Double-1>', on_problem)

    # ---------------- file actions
    def confirm_discard():
        tf = st['tf']
        return not tf or not tf.dirty or messagebox.askyesno('Unsaved', 'Discard unsaved changes to this file?')

    def open_file(path):
        if not confirm_discard():
            file_pick.set(os.path.relpath(st['tf'].path, mod.root) if st['tf'] else '')
            return
        st['tf'] = TechFile(path)
        st['others'] = all_tech_ids(mod, path)
        st['sel'], st['folder'] = None, ''
        file_pick.set(os.path.relpath(path, mod.root))
        changed()
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    def save():
        tf = st['tf']
        if not tf:
            return
        errs = [p for p in check(tf, mod, all_sprites(), st.get('others'), tags, st['game_loc']) if p[0] == 'error']
        if errs and not messagebox.askyesno('Errors', f'{len(errs)} errors, e.g. "{errs[0][2]}". Save anyway?'):
            return
        tf.save()
        redraw()
        status['text'] = f'Saved {os.path.relpath(tf.path, mod.root)}.'

    def new_file():
        if not confirm_discard():
            return
        name = simpledialog.askstring('New tech file', 'File name (e.g. HOD_ALD_military):', parent=root)
        if not name or not re.fullmatch(r'[\w\-]+', name.strip()):
            return
        path = mod.path('common', 'technologies', f'{name.strip()}.txt')
        if os.path.exists(path):
            messagebox.showerror('New tech file', f'{os.path.relpath(path, mod.root)} already exists.')
            return
        folder = sorted(tags[0])[0] if tags[0] else 'infantry_folder'
        write_text(path, 'technologies = {\n' + tech_text(f'{name.strip()}_tech_1', folder, 0, 0) + '}\n')
        files.append(os.path.relpath(path, mod.root))
        file_pick['values'] = files
        st['tf'] = None
        open_file(path)
        status['text'] = f'Created {os.path.relpath(path, mod.root)}: pick its folder in the form.'

    def set_game_dir():
        d = filedialog.askdirectory(title='Hearts of Iron IV install folder (the one with interface/ and gfx/)')
        if d:
            settings['game_dir'] = d
            save_settings(settings)
            st['vanilla'], st['game_loc'] = tech_sprites(d), game_loc_keys(d)
            icons.clear()
            changed(keep_form=True)
            status['text'] = f'{len(st["vanilla"])} vanilla tech icons found.'

    def edit_file_text(line=1):
        """Whole-file editor, for problems the form cannot reach (like a missing brace)."""
        tf = st['tf']
        if not tf:
            return
        dlg = tk.Toplevel(root)
        dlg.title(f'File text - {os.path.basename(tf.path)}')
        dlg.geometry('900x700')
        info = ttk.Label(dlg, anchor='w')
        info.pack(side='bottom', fill='x')
        txt = tk.Text(dlg, wrap='none', undo=True, font=('Consolas', 10))
        sb = ttk.Scrollbar(dlg, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', tf.text)
        txt.tag_configure('hit', background='#ffe08a')

        def mark(n):
            txt.tag_remove('hit', '1.0', 'end')
            txt.tag_add('hit', f'{n}.0', f'{n}.end+1c')
            txt.see(f'{n}.0')

        def check_text():
            b = brace_problem(txt.get('1.0', 'end-1c'))
            info.configure(text=b[1] if b else 'Braces match.', foreground='#c00000' if b else '#008000')
            if b:
                mark(b[0])

        def apply():
            tf.apply(txt.get('1.0', 'end-1c'))
            dlg.destroy()
            st['sel'] = None
            changed()

        bar2 = ttk.Frame(dlg)
        bar2.pack(side='bottom', fill='x')
        ttk.Button(bar2, text='Check braces', command=check_text).pack(side='left', padx=4, pady=4)
        ttk.Button(bar2, text='Apply to file', command=apply).pack(side='left')
        mark(line)
        check_text()

    def auto_names():
        tf = st['tf']
        if not tf:
            return
        missing = [t['id'] for t in tf.focuses.values() if t['id'] not in mod.loc and t['id'] not in mod.loc_broken]
        if not missing:
            messagebox.showinfo('Auto names', 'Every tech already has a name.')
            return
        target = loc_file()
        if not messagebox.askyesno('Auto names', f'Write a name for {len(missing)} techs, e.g.\n{missing[0]} -> '
                                   f'"{auto_name(missing[0])}"\ninto {os.path.relpath(target, mod.root)}?'):
            return
        n = add_auto_names(tf, mod, target)
        status['text'] = f'Added {n} names to {os.path.relpath(target, mod.root)}. Existing names were not touched.'
        changed(keep_form=True)

    def zoom(f):
        st['zoom'] = max(0.3, min(2.0, st['zoom'] * f))
        icons.clear()
        redraw()

    def undo():
        if st['tf']:
            st['tf'].undo_step()
            changed()

    def redo():
        if st['tf']:
            st['tf'].redo_step()
            changed()

    def on_folder(_):
        v = folder_pick.get()
        st['folder'], st['sel'] = ('' if v == '(no folder)' else v), None
        fill_form()
        redraw()
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    file_pick.bind('<<ComboboxSelected>>', lambda e: open_file(mod.path(file_pick.get())))
    folder_pick.bind('<<ComboboxSelected>>', on_folder)
    for text, cmd in (('New file...', new_file), ('Save', save), ('Undo', undo), ('Redo', redo),
                      ('Zoom -', lambda: zoom(0.8)), ('Zoom +', lambda: zoom(1.25)),
                      ('Add tech', lambda: add_child()), ('Auto names', auto_names),
                      ('Edit file text...', lambda: edit_file_text()), ('Game folder...', set_game_dir)):
        ttk.Button(bar, text=text, command=cmd).pack(side='left', padx=2)
    ttk.Label(bar, foreground='#777', text='  drag = move, right-click = paths/xor/add/delete').pack(side='left')
    root.bind('<Control-s>', lambda e: save())
    root.bind('<Control-z>', lambda e: undo() if root.focus_get() not in (script, desc, leads) else None)
    root.bind('<Control-y>', lambda e: redo() if root.focus_get() not in (script, desc, leads) else None)
    root.protocol('WM_DELETE_WINDOW', lambda: confirm_discard() and root.destroy())
    if files:
        open_file(mod.path(next((f for f in files if 'republic' in f.lower()), files[0])))
    root.mainloop()


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root_dir = args[0] if args else find_mod_root()
    if '--check' in sys.argv:
        if not root_dir:
            sys.exit('usage: hoi4_tech_editor.py MOD_FOLDER --check')
        m = Mod(root_dir)
        game_dir = load_settings().get('game_dir')
        sprites, game_loc = {**tech_sprites(game_dir), **m.sprites}, game_loc_keys(game_dir)
        tags = tech_tags(m)
        for f in m.files('common/technologies'):
            tf = TechFile(f)
            if not tf.focuses:
                continue
            probs = check(tf, m, sprites, tags=tags, game_loc=game_loc)
            print(f'== {os.path.basename(f)}: {len(tf.focuses)} techs, {len(probs)} problems')
            for lvl, tid, msg, _ in probs:
                print(f'   [{lvl}] {tid}: {msg}')
    else:
        run_gui(root_dir)
