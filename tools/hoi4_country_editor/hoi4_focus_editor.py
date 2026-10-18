"""HOI4 Focus Tree Editor: draw, edit and check national focus trees of a mod.

Run:  python hoi4_focus_editor.py [mod_folder]            (GUI)
      python hoi4_focus_editor.py [mod_folder] --check   (list problems in every tree, no GUI)

The focus file's text is the source of truth: every edit is a small text change, so comments and
formatting are kept, and undo is just the previous text.
"""
import json
import os
import re
import sys

from hoi4_country_editor import (TOKEN, Mod, del_in, find_mod_root, get, get_all, parse, read_text, set_loc,
                                 set_top, top_span, write_text)

UX, UY = 110, 130  # editor pixels per focus grid step at zoom 1 (the game uses 96 x 130)
SETTINGS = os.path.join(os.path.expanduser('~'), '.hoi4_focus_editor.json')


def spans(text, key):
    """All top-level (start, end) spans of `key = {...}` in text."""
    out, off = [], 0
    while True:
        s = top_span(text[off:], key)
        if not s:
            return out
        out.append((off + s[0], off + s[1]))
        off += s[1]


def inner(text, span):
    """(start, end) of the text between the braces of a `key = { ... }` span."""
    o = text.index('{', span[0])
    return o + 1, span[1] - 1


def focus_blocks(text):
    """(id, start, end, tree_index) of every focus in every focus_tree, plus top-level shared_focus blocks."""
    out = []
    for ti, tspan in enumerate(spans(text, 'focus_tree')):
        a, b = inner(text, tspan)
        for s, e in spans(text[a:b], 'focus'):
            out.append((get(parse(text[a + s:a + e])[0][1], 'id', ''), a + s, a + e, ti))
    for s, e in spans(text, 'shared_focus'):
        out.append((get(parse(text[s:e])[0][1], 'id', ''), s, e, -1))
    return out


def brace_depth(text):
    d = 0
    for t in TOKEN.findall(text):
        if not t.startswith('#'):
            d += {'{': 1, '}': -1}.get(t, 0)
    return d


def focus_text(fid, x, y, icon='GFX_goal_unknown', cost=10, prereq=None, rel=None):
    lines = [f'\tfocus = {{', f'\t\tid = {fid}', f'\t\ticon = {icon}', f'\t\tcost = {cost}']
    if rel:
        lines.append(f'\t\trelative_position_id = {rel}')
    if prereq:
        lines.append(f'\t\tprerequisite = {{ focus = {prereq} }}')
    lines += [f'\t\tx = {x}', f'\t\ty = {y}', '\t\tcompletion_reward = {', '\t\t\tadd_political_power = 50',
              '\t\t}', '\t\tai_will_do = {', '\t\t\tfactor = 10', '\t\t}', '\t}']
    return '\n'.join(lines) + '\n'


def tree_text(tree_id, tag, first_focus):
    return (f'focus_tree = {{\n\tid = {tree_id}\n\n\tcountry = {{\n\t\tfactor = 0\n\t\tmodifier = {{\n'
            f'\t\t\tadd = 10\n\t\t\ttag = {tag}\n\t\t}}\n\t}}\n\n\tdefault = no\n\treset_on_civilwar = no\n'
            f'\tinitial_show_position = {{ x = 0 y = 0 }}\n\tcontinuous_focus_position = {{ x = 50 y = 1200 }}\n\n'
            f'{focus_text(first_focus, 0, 0)}}}\n')


class FocusFile:
    def __init__(self, path, text=None):
        self.path = path
        self.text = read_text(path) if text is None else text
        self.undo, self.redo = [], []
        self.saved_text = self.text
        self.refresh()

    @property
    def dirty(self):
        return self.text != self.saved_text

    def refresh(self):
        self.focuses = {}  # id -> dict
        self.order = []
        for fid, s, e, ti in focus_blocks(self.text):
            items = parse(self.text[s:e])[0][1]
            num = lambda k, d=0: float(get(items, k, d)) if re.fullmatch(r'-?\d+(\.\d+)?', str(get(items, k, d))) else d
            f = dict(id=fid, x=num('x'), y=num('y'), rel=get(items, 'relative_position_id'), cost=get(items, 'cost', ''),
                     icon=get(items, 'icon', ''), tree=ti, start=s, end=e,
                     prereq=[[v for k, v in g if k == 'focus'] for g in get_all(items, 'prerequisite') if isinstance(g, list)],
                     mutex=[v for g in get_all(items, 'mutually_exclusive') if isinstance(g, list) for k, v in g if k == 'focus'])
            f['prereq'] = [g for g in f['prereq'] if g]
            if fid in self.focuses:
                f['duplicate'] = True
                fid = f'{fid}#{len(self.order)}'  # keep both visible so the duplicate can be fixed
            self.focuses[fid] = f
            self.order.append(fid)
        self.trees = [parse(self.text[s:e])[0][1] for s, e in spans(self.text, 'focus_tree')]
        for fid, f in self.focuses.items():
            f['ax'], f['ay'] = self.absolute(fid)

    def absolute(self, fid, seen=None):
        f = self.focuses[fid]
        seen = (seen or set()) | {fid}
        if f['rel'] in self.focuses and f['rel'] not in seen:
            px, py = self.absolute(f['rel'], seen)
            return px + f['x'], py + f['y']
        return f['x'], f['y']

    # ---- edits: each replaces self.text and keeps the old one for undo
    def apply(self, new_text):
        if new_text != self.text:
            self.undo.append(self.text)
            self.redo.clear()
            self.text = new_text
            self.refresh()

    def undo_step(self):
        if self.undo:
            self.redo.append(self.text)
            self.text = self.undo.pop()
            self.refresh()

    def redo_step(self):
        if self.redo:
            self.undo.append(self.text)
            self.text = self.redo.pop()
            self.refresh()

    def _edit_focus(self, text, fid, fn):
        if text is self.text:  # stored offsets also work for duplicated ids ("X#3")
            s, e = self.focuses[fid]['start'], self.focuses[fid]['end']
        else:
            real = self.focuses[fid]['id'] if fid in self.focuses else fid
            _, s, e, _ = next(blk for blk in focus_blocks(text) if blk[0] == real)
        a, b = inner(text, (s, e))
        return text[:a] + fn(text[a:b]) + text[b:]

    def edit(self, fid, fn):
        self.apply(self._edit_focus(self.text, fid, fn))

    @staticmethod
    def _put(body, key, value):
        """Set or (value None) remove every top-level `key` in a focus body."""
        if value is None or isinstance(value, list):
            while top_span(body, key):
                body = del_in(body, [key])
            if not value:
                return body
            return body.rstrip() + ''.join(f'\n\t\t{key} = {v}' for v in value) + '\n\t'
        if top_span(body, key):
            return set_top(body, key, value)
        return body.rstrip() + f'\n\t\t{key} = {value}\n\t'

    def set_values(self, fid, values):
        """values: {key: str | None | [str, ...]} applied in one undo step."""
        def fn(body):
            for k, v in values.items():
                body = self._put(body, k, v)
            return body
        self.edit(fid, fn)

    @staticmethod
    def prereq_values(groups):
        return [('{ ' + ' '.join(f'focus = {g}' for g in grp) + ' }') for grp in groups if grp]

    def move(self, fid, ax, ay):
        f = self.focuses[fid]
        if f['rel'] in self.focuses:
            p = self.focuses[f['rel']]
            ax, ay = ax - p['ax'], ay - p['ay']
        self.set_values(fid, {'x': fmt(ax), 'y': fmt(ay)})

    def add_focus(self, fid, ax, ay, prereq=None, tree=0, icon='GFX_goal_unknown'):
        s, e = spans(self.text, 'focus_tree')[tree]
        a, b = inner(self.text, (s, e))
        body = self.text[a:b].rstrip() + '\n' + focus_text(fid, fmt(ax), fmt(ay), icon, 10, prereq)
        self.apply(self.text[:a] + body + self.text[b:])

    def duplicate(self, fid, new_id):
        f = self.focuses[fid]
        block = self.text[f['start']:f['end']]
        block = re.sub(r'(\bid\s*=\s*)' + re.escape(f['id']) + r'\b', lambda m: m.group(1) + new_id, block, count=1)
        s, e = spans(self.text, 'focus_tree')[max(f['tree'], 0)]
        a, b = inner(self.text, (s, e))
        self.apply(self.text[:b].rstrip() + '\n\t' + block + '\n' + self.text[b:])
        self.move(new_id, f['ax'] + 1, f['ay'])

    def delete(self, fid):
        """Remove a focus and every reference to it, keeping dependants where they are on screen."""
        f = self.focuses[fid]
        text = self.text
        for oid, o in self.focuses.items():
            if oid == fid:
                continue
            values = {}
            if any(fid in g for g in o['prereq']):
                values['prerequisite'] = self.prereq_values([[x for x in g if x != fid] for g in o['prereq']])
            if fid in o['mutex']:
                rest = [m for m in o['mutex'] if m != fid]
                values['mutually_exclusive'] = ['{ ' + ' '.join(f'focus = {m}' for m in rest) + ' }'] if rest else None
            if o['rel'] == fid:
                values.update(relative_position_id=None, x=fmt(o['ax']), y=fmt(o['ay']))
            if values:
                text = self._edit_focus(text, oid, lambda body, v=values: self._apply_values(body, v))
        blocks = {b[0]: b for b in focus_blocks(text)}
        _, s, e, _ = blocks[f['id']]
        line = text.rfind('\n', 0, s) + 1
        s = line if not text[line:s].strip() else s
        e = e + 1 if text[e:e + 1] == '\n' else e
        self.apply(text[:s] + text[e:])

    def _apply_values(self, body, values):
        for k, v in values.items():
            body = self._put(body, k, v)
        return body

    def rename(self, fid, new_id):
        """Rename a focus and every reference to it in this file."""
        self.apply(re.sub(r'(?<![\w.])' + re.escape(fid) + r'(?![\w.])', new_id, self.text))

    def link_mutex(self, a, b):
        for x, y in ((a, b), (b, a)):
            m = self.focuses[x]['mutex']
            if y not in m:
                self.set_values(x, {'mutually_exclusive': ['{ ' + ' '.join(f'focus = {v}' for v in m + [y]) + ' }']})

    def save(self):
        write_text(self.path, self.text)
        self.saved_text = self.text


def fmt(v):
    return str(int(v)) if float(v).is_integer() else f'{v:g}'


def all_focus_ids(mod, skip=None):
    """id -> file for every focus in the mod's other focus files (duplicate ids across files break the game)."""
    out = {}
    for f in mod.files('common/national_focus'):
        if skip and os.path.abspath(f) == os.path.abspath(skip):
            continue
        for fid, *_ in focus_blocks(read_text(f)):
            out.setdefault(fid, f)
    return out


def check(ff, mod, sprites=None, others=None):
    """Problems as (level, focus id or '', message, fix or None). level: error / warning."""
    sprites = sprites if sprites is not None else mod.sprites
    others = all_focus_ids(mod, ff.path) if others is None else others
    out = []
    if brace_depth(ff.text) != 0:
        out.append(('error', '', f'Braces do not match ({brace_depth(ff.text):+d}): the game will misread the file', None))
    if not ff.trees and not any(f['tree'] == -1 for f in ff.focuses.values()):
        out.append(('error', '', 'No focus_tree block in this file', None))
    for t in ff.trees:
        if not get(t, 'id'):
            out.append(('error', '', 'A focus_tree has no id', None))
        if get(t, 'country') is None and get(t, 'default') != 'yes':
            out.append(('warning', '', f'Tree {get(t, "id", "?")} has no country = {{ }} block, so no country gets it', None))
    pos = {}
    for fid, f in ff.focuses.items():
        real = f['id']
        if f.get('duplicate'):
            out.append(('error', fid, f'Focus id {real} is used twice in this file', None))
        if real in others:
            out.append(('error', fid, f'Focus id {real} also exists in {os.path.basename(others[real])}', None))
        if not real:
            out.append(('error', fid, 'Focus without an id', None))
        for g in f['prereq']:
            for p in g:
                if p not in ff.focuses:
                    out.append(('error', fid, f'Prerequisite {p} does not exist in this file',
                                lambda fid=fid, p=p: ff.set_values(fid, {'prerequisite': ff.prereq_values(
                                    [[x for x in grp if x != p] for grp in ff.focuses[fid]['prereq']])})))
                elif ff.focuses[p]['ay'] >= f['ay']:
                    out.append(('warning', fid, f'Placed at or above its prerequisite {p} (the line goes upward)', None))
        for m in f['mutex']:
            if m not in ff.focuses:
                out.append(('error', fid, f'Mutually exclusive with {m}, which does not exist', None))
            elif fid not in ff.focuses[m]['mutex']:
                out.append(('warning', fid, f'Exclusive with {m}, but {m} does not list it back',
                            lambda a=fid, b=m: ff.link_mutex(a, b)))
        if f['rel'] and f['rel'] not in ff.focuses:
            out.append(('error', fid, f'relative_position_id {f["rel"]} does not exist (position falls back to x/y)',
                        lambda fid=fid: ff.set_values(fid, {'relative_position_id': None})))
        key = (f['ax'], f['ay'])
        if key in pos:
            out.append(('warning', fid, f'Same position as {pos[key]} ({fmt(key[0])}, {fmt(key[1])})', None))
        pos.setdefault(key, fid)
        for key, what in ((real, 'name'), (f'{real}_desc', 'description')):
            if key in mod.loc_broken:
                bf, line = mod.loc_broken[key]
                out.append(('error', fid, f'Broken {what} localisation line (missing closing quote?) in '
                                          f'{os.path.basename(bf)} line {line}', None))
            elif real and key not in mod.loc:
                out.append(('warning', fid, f'No {what} localisation ({key})', None))
        if not f['icon']:
            out.append(('warning', fid, 'No icon', None))
        elif f['icon'] not in sprites:
            out.append(('warning', fid, f'Icon {f["icon"]} is not defined in interface/*.gfx'
                                        + ('' if sprites is not mod.sprites else ' (set the game folder to see vanilla icons)'), None))
        if not f['cost']:
            out.append(('warning', fid, 'No cost (defaults to 10)', None))
    # prerequisite cycles
    state = {}

    def visit(fid, path):
        state[fid] = 1
        for g in ff.focuses[fid]['prereq']:
            for p in g:
                if p in ff.focuses:
                    if state.get(p) == 1:
                        out.append(('error', fid, 'Prerequisite loop: ' + ' -> '.join(path + [p]), None))
                    elif not state.get(p):
                        visit(p, path + [p])
        state[fid] = 2

    for fid in ff.focuses:
        if not state.get(fid):
            visit(fid, [fid])
    return out


GOAL_SIZE = (94, 86)  # vanilla focus icon size


def import_icon(mod, src, sprite, folder='custom'):
    """Convert an image to a focus icon .dds and register both its sprite and its _shine sprite. Returns the sprite name."""
    from PIL import Image
    if not sprite.startswith('GFX_'):
        sprite = 'GFX_' + sprite
    stem = sprite[4:]
    rel = f'gfx/interface/goals/{folder}/{stem}.dds'
    os.makedirs(os.path.dirname(mod.path(rel)), exist_ok=True)
    img = Image.open(src).convert('RGBA')
    img.thumbnail(GOAL_SIZE, Image.LANCZOS)
    canvas = Image.new('RGBA', GOAL_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(img, ((GOAL_SIZE[0] - img.width) // 2, (GOAL_SIZE[1] - img.height) // 2))
    canvas.save(mod.path(rel))
    from hoi4_country_editor import add_to_block
    ifaces = [f for f in mod.files('interface', '.gfx') if 'spritetypes' in read_text(f).lower()]
    goals = next((f for f in ifaces if f.lower().endswith('goals.gfx')), mod.path('interface', 'focus_editor_goals.gfx'))
    shine = next((f for f in ifaces if f.lower().endswith('goals_shine.gfx')),
                 mod.path('interface', 'focus_editor_goals_shine.gfx'))
    anim = lambda rot: (f'\t\tanimation = {{\n\t\t\tanimationmaskfile = "{rel}"\n'
                        f'\t\t\tanimationtexturefile = "gfx/interface/goals/shine_overlay.dds"\n'
                        f'\t\t\tanimationrotation = {rot}\n\t\t\tanimationlooping = no\n\t\t\tanimationtime = 0.75\n'
                        f'\t\t\tanimationdelay = 0\n\t\t\tanimationblendmode = "add"\n\t\t\tanimationtype = "scrolling"\n'
                        f'\t\t\tanimationrotationoffset = {{ x = 0.0 y = 0.0 }}\n'
                        f'\t\t\tanimationtexturescale = {{ x = 1.0 y = 1.0 }}\n\t\t}}\n')
    for path, entry in (
            (goals, f'\tspriteType = {{\n\t\tname = "{sprite}"\n\t\ttexturefile = "{rel}"\n\t}}'),
            (shine, f'\tSpriteType = {{\n\t\tname = "{sprite}_shine"\n\t\ttexturefile = "{rel}"\n'
                    f'\t\teffectFile = "gfx/FX/buttonstate.lua"\n{anim("-90.0")}{anim("90.0")}'
                    f'\t\tlegacy_lazy_load = no\n\t}}')):
        text = read_text(path) if os.path.exists(path) else ''
        if f'"{sprite}"' in text or f'"{sprite}_shine"' in text:
            continue
        key = next((k for k in ('spriteTypes', 'SpriteTypes', 'spritetypes') if top_span(text, k)), 'spriteTypes')
        write_text(path, add_to_block(text, key, entry))
    mod.sprites[sprite] = rel
    return sprite


def load_settings():
    try:
        with open(SETTINGS, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        with open(SETTINGS, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except OSError:
        pass


def game_sprites(game_dir):
    """Vanilla focus icon sprites (name -> absolute texture path) from the game's interface/*goals*.gfx."""
    out = {}
    folder = os.path.join(game_dir or '', 'interface')
    if not game_dir or not os.path.isdir(folder):
        return out
    for n in os.listdir(folder):
        if n.endswith('.gfx') and 'goal' in n.lower() and 'shine' not in n.lower():
            for k, v in parse(read_text(os.path.join(folder, n))):
                for kk, sp in (v if isinstance(v, list) else []):
                    if kk.lower() == 'spritetype' and isinstance(sp, list):
                        tex = next((x for k2, x in sp if k2.lower() == 'texturefile'), '')
                        out[get(sp, 'name', '')] = os.path.join(game_dir, tex)
    return out


# ---------------------------------------------------------------- GUI

def run_gui(mod_root):
    import random
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    try:
        from PIL import Image, ImageTk
    except ImportError:
        Image = None

    root = tk.Tk()
    root.title('HOI4 Focus Tree Editor')
    root.geometry('1600x950')
    if not mod_root:
        mod_root = filedialog.askdirectory(title='Pick your mod folder (the one with common/, history/, gfx/)')
        if not mod_root:
            return
    mod = Mod(mod_root)
    settings = load_settings()
    st = {'ff': None, 'sel': None, 'zoom': 0.7, 'link': None, 'drag': None, 'vanilla': game_sprites(settings.get('game_dir'))}
    icons = {}

    def sprite_file(name):
        if name in mod.sprites:  # mod sprite; its picture may still be a vanilla file
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
        return {**{k: v for k, v in st['vanilla'].items()}, **mod.sprites}

    # ---------------- toolbar
    bar = ttk.Frame(root, padding=4)
    bar.pack(fill='x')
    files = [os.path.relpath(f, mod.root) for f in mod.files('common/national_focus')]
    file_pick = ttk.Combobox(bar, values=files, state='readonly', width=48)
    file_pick.pack(side='left')
    status = ttk.Label(root, anchor='w')
    status.pack(side='bottom', fill='x')

    # ---------------- panes
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
    canvas = tk.Canvas(cframe, background='#2b2f3a', highlightthickness=0)
    hs = ttk.Scrollbar(cframe, orient='horizontal', command=canvas.xview)
    vs = ttk.Scrollbar(cframe, orient='vertical', command=canvas.yview)
    canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
    hs.pack(side='bottom', fill='x')
    vs.pack(side='right', fill='y')
    canvas.pack(fill='both', expand=True)

    pframe = ttk.Frame(vpanes)
    vpanes.add(pframe, height=180, minsize=80, stretch='never')
    pbar = ttk.Frame(pframe)
    pbar.pack(fill='x')
    plabel = ttk.Label(pbar, text='Problems')
    plabel.pack(side='left', padx=4)
    problems = ttk.Treeview(pframe, columns=('level', 'focus', 'problem'), show='headings', height=6)
    for col, w in (('level', 70), ('focus', 260), ('problem', 700)):
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
    BW, BH = 92, 92

    def pos(f):
        z = st['zoom']
        return f['ax'] * UX * z + 60 * z, f['ay'] * UY * z + 40 * z

    def redraw():
        canvas.delete('all')
        ff = st['ff']
        if not ff:
            return
        z = st['zoom']
        w, h = BW * z, BH * z
        for fid, f in ff.focuses.items():
            x, y = pos(f)
            for g in f['prereq']:
                for p in g:
                    if p in ff.focuses:
                        px, py = pos(ff.focuses[p])
                        canvas.create_line(px, py + h / 2, px, py + h / 2 + 12 * z, x, y - h / 2 - 12 * z, x, y - h / 2,
                                           fill='#d8c890', width=2, dash=(6, 4) if len(g) > 1 else None)
            for m in f['mutex']:
                if m in ff.focuses and m > fid:
                    mx, my = pos(ff.focuses[m])
                    canvas.create_line(x, y, mx, my, fill='#e04040', width=2)
                    canvas.create_text((x + mx) / 2, (y + my) / 2, text='⊘', fill='#ff6060', font=('Segoe UI', int(14 * z) or 1))
        for fid, f in ff.focuses.items():
            x, y = pos(f)
            sel = fid == st['sel']
            canvas.create_rectangle(x - w / 2, y - h / 2, x + w / 2, y + h / 2, fill='#40485a' if not sel else '#5a6a90',
                                    outline='#ffd040' if sel else '#8890a0', width=3 if sel else 1, tags=('focus', fid))
            img = icon_photo(f['icon'], (int(60 * z) or 1, int(55 * z) or 1))
            if img:
                canvas.create_image(x, y - h / 2 + 32 * z, image=img, tags=('focus', fid))
            else:
                canvas.create_text(x, y - h / 2 + 30 * z, text='?', fill='#9aa', font=('Segoe UI', int(20 * z) or 1),
                                   tags=('focus', fid))
            name = mod.loc.get(f['id'], f['id'])
            canvas.create_text(x, y + h / 2 - 16 * z, text=name, width=w - 4, fill='white',
                               font=('Segoe UI', max(6, int(8 * z))), tags=('focus', fid))
        canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 1, 1))
        title = f'HOI4 Focus Tree Editor - {os.path.relpath(ff.path, mod.root)}' + (' *' if ff.dirty else '')
        root.title(title)

    def refresh_problems():
        ff = st['ff']
        problems.delete(*problems.get_children())
        fixes.clear()
        if not ff:
            return
        out = check(ff, mod, all_sprites(), st.get('others'))
        out.sort(key=lambda p: (p[0] != 'error', p[1]))
        for i, (lvl, fid, msg, fix) in enumerate(out):
            problems.insert('', 'end', iid=str(i), values=(lvl, fid, msg + ('   [double-click to fix]' if fix else '')),
                            tags=(lvl,))
            fixes[str(i)] = (fid, fix)
        errs = sum(1 for p in out if p[0] == 'error')
        plabel.configure(text=f'Problems: {errs} errors, {len(out) - errs} warnings   '
                              '(double-click a row to go to the focus or apply its fix)')

    def changed(keep_form=False):
        redraw()
        refresh_problems()
        if not keep_form:
            fill_form()

    # ---------------- focus form
    form = ttk.Frame(right, padding=6)
    form.pack(fill='both', expand=True)
    fv = {k: tk.StringVar() for k in ('id', 'name', 'icon', 'cost', 'x', 'y', 'rel', 'prereq', 'mutex')}
    r = 0
    for key, label in (('id', 'Focus id'), ('name', 'Name')):
        ttk.Label(form, text=label).grid(row=r, column=0, sticky='w')
        ttk.Entry(form, textvariable=fv[key], width=44).grid(row=r, column=1, columnspan=3, sticky='we', pady=1)
        r += 1
    ttk.Label(form, text='Description').grid(row=r, column=0, sticky='nw')
    desc = tk.Text(form, height=4, width=44, wrap='word', font=('Segoe UI', 9))
    desc.grid(row=r, column=1, columnspan=3, sticky='we', pady=1)
    r += 1
    ttk.Label(form, text='Icon').grid(row=r, column=0, sticky='w')
    ttk.Entry(form, textvariable=fv['icon'], width=30).grid(row=r, column=1, sticky='we')
    icon_prev = ttk.Label(form)
    icon_prev.grid(row=r, column=2, rowspan=3, padx=4)
    ib = ttk.Frame(form)
    ib.grid(row=r + 1, column=1, sticky='w')
    ttk.Button(ib, text='Pick...', command=lambda: pick_icon()).pack(side='left')
    ttk.Button(ib, text='Import image...', command=lambda: import_icon_dialog()).pack(side='left', padx=4)
    r += 3
    ttk.Label(form, text='Cost').grid(row=r, column=0, sticky='w')
    ttk.Entry(form, textvariable=fv['cost'], width=8).grid(row=r, column=1, sticky='w')
    r += 1
    ttk.Label(form, text='Position x / y').grid(row=r, column=0, sticky='w')
    xy = ttk.Frame(form)
    xy.grid(row=r, column=1, columnspan=3, sticky='w')
    ttk.Entry(xy, textvariable=fv['x'], width=6).pack(side='left')
    ttk.Entry(xy, textvariable=fv['y'], width=6).pack(side='left', padx=4)
    ttk.Label(xy, text='relative to').pack(side='left')
    rel_box = ttk.Combobox(xy, textvariable=fv['rel'], width=26)
    rel_box.pack(side='left', padx=4)
    r += 1
    ttk.Label(form, text='Prerequisites').grid(row=r, column=0, sticky='nw')
    pre = tk.Text(form, height=4, width=44, font=('Consolas', 9))
    pre.grid(row=r, column=1, columnspan=3, sticky='we', pady=1)
    r += 1
    ttk.Label(form, foreground='#777', text='one line per required group; "A or B" on a line = either one',
              ).grid(row=r, column=1, columnspan=3, sticky='w')
    r += 1
    ttk.Label(form, text='Mutually exclusive').grid(row=r, column=0, sticky='w')
    ttk.Entry(form, textvariable=fv['mutex'], width=44).grid(row=r, column=1, columnspan=3, sticky='we', pady=1)
    r += 1
    fb = ttk.Frame(form)
    fb.grid(row=r, column=0, columnspan=4, sticky='w', pady=6)
    ttk.Button(fb, text='Apply', command=lambda: apply_form()).pack(side='left')
    ttk.Button(fb, text='Add child', command=lambda: add_child()).pack(side='left', padx=4)
    ttk.Button(fb, text='Duplicate', command=lambda: duplicate()).pack(side='left')
    ttk.Button(fb, text='Delete', command=lambda: delete()).pack(side='left', padx=4)
    r += 1
    ttk.Label(form, text='Focus script (rewards, available, bypass, ai_will_do... everything)').grid(
        row=r, column=0, columnspan=4, sticky='w', pady=(8, 0))
    r += 1
    script = tk.Text(form, height=18, width=60, wrap='none', undo=True, font=('Consolas', 9))
    script.grid(row=r, column=0, columnspan=4, sticky='nsew')
    form.rowconfigure(r, weight=1)
    form.columnconfigure(1, weight=1)
    r += 1
    ttk.Button(form, text='Apply script', command=lambda: apply_script()).grid(row=r, column=0, sticky='w', pady=4)

    def loc_file():
        """Where new focus texts go: the file already holding most of this tree's texts, else one named after it."""
        from collections import Counter
        used = Counter(mod.loc_file[f['id']] for f in st['ff'].focuses.values() if f['id'] in mod.loc_file)
        if used:
            return used.most_common(1)[0][0]
        stem = re.sub(r'\W+', '_', os.path.splitext(os.path.basename(st['ff'].path))[0])
        return mod.path('localisation', 'english', f'{stem}_l_english.yml')

    def fill_form():
        ff, fid = st['ff'], st['sel']
        f = ff.focuses.get(fid) if ff else None
        for v in fv.values():
            v.set('')
        desc.delete('1.0', 'end')
        pre.delete('1.0', 'end')
        script.delete('1.0', 'end')
        icon_prev.configure(image='')
        if not f:
            return
        fv['id'].set(f['id'])
        fv['name'].set(mod.loc.get(f['id'], ''))
        desc.insert('1.0', mod.loc.get(f'{f["id"]}_desc', '').replace('\\n', '\n'))
        fv['icon'].set(f['icon'])
        fv['cost'].set(f['cost'])
        fv['x'].set(fmt(f['x']))
        fv['y'].set(fmt(f['y']))
        fv['rel'].set(f['rel'] or '')
        rel_box['values'] = [''] + sorted(ff.focuses)
        pre.insert('1.0', '\n'.join(' or '.join(g) for g in f['prereq']))
        fv['mutex'].set(', '.join(f['mutex']))
        script.insert('1.0', ff.text[f['start']:f['end']])
        icon_prev.configure(image=icon_photo(f['icon'], (60, 55)) or '')

    def apply_form():
        ff, fid = st['ff'], st['sel']
        if not ff or fid not in ff.focuses:
            return
        f = ff.focuses[fid]
        new_id = fv['id'].get().strip()
        groups = [[p.strip() for p in re.split(r'\s+or\s+|,|\|', line) if p.strip()]
                  for line in pre.get('1.0', 'end').splitlines() if line.strip()]
        mutex = [m.strip() for m in re.split(r'[,\s]+', fv['mutex'].get()) if m.strip()]
        unknown = [p for g in groups for p in g if p not in ff.focuses] + [m for m in mutex if m not in ff.focuses]
        if unknown and not messagebox.askyesno('Unknown focus', f'Not in this file: {", ".join(unknown)}. Apply anyway?'):
            return
        for key in ('x', 'y', 'cost'):
            if fv[key].get() and not re.fullmatch(r'-?\d+(\.\d+)?', fv[key].get().strip()):
                messagebox.showerror('Not applied', f'{key} must be a number')
                return
        rel = fv['rel'].get().strip() or None
        if rel and rel not in ff.focuses:
            messagebox.showerror('Not applied', f'relative_position_id {rel} is not a focus of this file')
            return
        values = {'icon': fv['icon'].get().strip() or None, 'cost': fv['cost'].get().strip() or None,
                  'x': fv['x'].get().strip() or '0', 'y': fv['y'].get().strip() or '0', 'relative_position_id': rel}
        if groups != f['prereq']:
            values['prerequisite'] = ff.prereq_values(groups)
        if mutex != f['mutex']:
            values['mutually_exclusive'] = ['{ ' + ' '.join(f'focus = {m}' for m in mutex) + ' }'] if mutex else None
        ff.set_values(fid, values)
        for m in mutex:  # exclusivity has to be listed on both sides
            if m in ff.focuses and fid not in ff.focuses[m]['mutex']:
                ff.link_mutex(fid, m)
        name, text = fv['name'].get().strip(), desc.get('1.0', 'end').strip().replace('\n', '\\n')
        real = f['id']
        if new_id and new_id != real:
            if new_id in ff.focuses or new_id in (st.get('others') or {}):
                messagebox.showerror('Rename', f'{new_id} is already used')
            elif re.fullmatch(r'[A-Za-z0-9_.\-]+', new_id):
                ff.rename(real, new_id)
                for old_key, new_key in ((real, new_id), (f'{real}_desc', f'{new_id}_desc')):
                    if old_key in mod.loc:
                        set_loc(mod, old_key, '', loc_file())
                real = st['sel'] = new_id
        if name != mod.loc.get(real, ''):
            set_loc(mod, real, name.replace('"', "'"), mod.loc_file.get(real) or loc_file())
        if text != mod.loc.get(f'{real}_desc', ''):
            set_loc(mod, f'{real}_desc', text.replace('"', "'"), mod.loc_file.get(f'{real}_desc') or loc_file())
        status['text'] = f'Applied {real}. Localisation is saved at once; the focus file on Save (Ctrl+S).'
        changed()

    def apply_script():
        ff, fid = st['ff'], st['sel']
        if not ff or fid not in ff.focuses:
            return
        body = script.get('1.0', 'end').rstrip()
        if brace_depth(body) != 0:
            messagebox.showerror('Not applied', 'The braces { } in this script do not match.')
            return
        if not re.match(r'\s*(focus|shared_focus)\s*=\s*\{', body):
            messagebox.showerror('Not applied', 'The script must stay a single focus = { ... } block.')
            return
        f = ff.focuses[fid]
        ff.apply(ff.text[:f['start']] + body + ff.text[f['end']:])
        new = get(parse(body)[0][1], 'id', fid)
        st['sel'] = new if new in ff.focuses else None
        changed()

    def new_id(base):
        ff = st['ff']
        i = 1
        while f'{base}_{i}' in ff.focuses:
            i += 1
        return f'{base}_{i}'

    def tag_prefix():
        ff = st['ff']
        f = ff.focuses.get(st['sel']) or (ff.focuses[ff.order[0]] if ff.order else None)
        return f['id'].split('_')[0] if f and '_' in f['id'] else 'focus'

    def add_child(at=None):
        ff = st['ff']
        if not ff or not ff.trees:
            return
        parent = ff.focuses.get(st['sel'])
        fid = new_id(f'{tag_prefix()}_new_focus')
        if at:
            ax, ay = at
        elif parent:
            ax, ay = parent['ax'], parent['ay'] + 1
            while any(o['ax'] == ax and o['ay'] == ay for o in ff.focuses.values()):
                ax += 1
        else:
            ax, ay = 0, 0
        ff.add_focus(fid, ax, ay, prereq=parent['id'] if parent and not at else None,
                     tree=max(parent['tree'], 0) if parent else 0)
        st['sel'] = fid
        changed()

    def duplicate():
        ff, fid = st['ff'], st['sel']
        if ff and fid in ff.focuses:
            nid = new_id(ff.focuses[fid]['id'])
            ff.duplicate(fid, nid)
            st['sel'] = nid
            changed()

    def delete():
        ff, fid = st['ff'], st['sel']
        if ff and fid in ff.focuses and messagebox.askyesno('Delete', f'Delete {fid} and its links?'):
            ff.delete(fid)
            st['sel'] = None
            changed()

    # ---------------- icons
    def pick_icon():
        if not st['ff']:
            return
        dlg = tk.Toplevel(root)
        dlg.title('Pick a focus icon')
        dlg.geometry('760x600')
        q = tk.StringVar()
        top = ttk.Frame(dlg, padding=4)
        top.pack(fill='x')
        ttk.Label(top, text='Search:').pack(side='left')
        ttk.Entry(top, textvariable=q).pack(side='left', fill='x', expand=True)
        cv = tk.Canvas(dlg, background='#2b2f3a')
        sb = ttk.Scrollbar(dlg, command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        cv.pack(fill='both', expand=True)
        names = sorted(n for n in all_sprites() if not n.endswith('_shine') and ('goal' in n.lower() or 'focus' in n.lower()
                       or n in {f['icon'] for f in st['ff'].focuses.values()} or mod.sprites.get(n, '').find('goals') >= 0))

        def show(*_):
            cv.delete('all')
            words = q.get().lower().split()
            shown = [n for n in names if all(w in n.lower() for w in words)][:240]
            cols = 7
            for i, n in enumerate(shown):
                x, y = (i % cols) * 104 + 54, (i // cols) * 110 + 50
                img = icon_photo(n, (80, 74))
                tag = f'n{i}'
                if img:
                    cv.create_image(x, y, image=img, tags=(tag,))
                cv.create_text(x, y + 46, text=n[4:28], fill='white', font=('Segoe UI', 7), tags=(tag,))
                cv.tag_bind(tag, '<Button-1>', lambda e, n=n: (fv['icon'].set(n), dlg.destroy(), apply_form()))
            cv.configure(scrollregion=cv.bbox('all') or (0, 0, 1, 1))
            dlg.title(f'Pick a focus icon - {len(shown)} shown of {len(names)}'
                      + ('' if st['vanilla'] else ' (set Game folder... for vanilla icons)'))

        q.trace_add('write', show)
        cv.bind('<MouseWheel>', lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        show()

    def import_icon_dialog():
        ff, fid = st['ff'], st['sel']
        if not ff or fid not in ff.focuses or not Image:
            return
        src = filedialog.askopenfilename(title='Focus icon image (PNG with transparency is best)',
                                         filetypes=[('Images', '*.png *.dds *.tga *.jpg *.jpeg *.webp'), ('All', '*')])
        if not src:
            return
        real = ff.focuses[fid]['id']
        name = simpledialog.askstring('Sprite name', 'Sprite name for this icon:', initialvalue=f'GFX_{real}', parent=root)
        if not name:
            return
        try:
            sprite = import_icon(mod, src, name.strip(), real.split('_')[0] if '_' in real else 'custom')
        except OSError as e:
            messagebox.showerror('Import icon', f'Cannot read this image: {e}')
            return
        icons.clear()
        fv['icon'].set(sprite)
        apply_form()
        status['text'] = f'Imported {sprite}: .dds, sprite and shine sprite written.'

    # ---------------- canvas interaction
    def focus_at(e):
        items = canvas.find_overlapping(canvas.canvasx(e.x), canvas.canvasy(e.y), canvas.canvasx(e.x), canvas.canvasy(e.y))
        for it in reversed(items):
            tags = canvas.gettags(it)
            if 'focus' in tags:
                return tags[1]
        return None

    def grid_at(e):
        z = st['zoom']
        return round((canvas.canvasx(e.x) - 60 * z) / (UX * z)), round((canvas.canvasy(e.y) - 40 * z) / (UY * z))

    def on_press(e):
        fid = focus_at(e)
        ff = st['ff']
        if st['link'] and fid and ff:
            kind, src = st['link']
            st['link'] = None
            canvas.configure(cursor='')
            if fid != src:
                if kind == 'prereq':
                    groups = ff.focuses[src]['prereq'] + [[ff.focuses[fid]['id']]]
                    ff.set_values(src, {'prerequisite': ff.prereq_values(groups)})
                elif kind == 'or':
                    groups = ff.focuses[src]['prereq'] or [[]]
                    groups[-1] = groups[-1] + [ff.focuses[fid]['id']]
                    ff.set_values(src, {'prerequisite': ff.prereq_values(groups)})
                else:
                    ff.link_mutex(src, fid)
                changed()
            return
        st['sel'] = fid
        st['drag'] = (fid, grid_at(e)) if fid else None
        fill_form()
        redraw()

    def on_release(e):
        ff, drag = st['ff'], st['drag']
        st['drag'] = None
        if not ff or not drag:
            return
        fid, start = drag
        gx, gy = grid_at(e)
        if (gx, gy) != start and fid in ff.focuses:
            f = ff.focuses[fid]
            ff.move(fid, f['ax'] + gx - start[0], f['ay'] + gy - start[1])
            changed()

    def on_motion(e):
        fid = focus_at(e)
        ff = st['ff']
        gx, gy = grid_at(e)
        status['text'] = (f'{fid}  ({fmt(ff.focuses[fid]["ax"])}, {fmt(ff.focuses[fid]["ay"])})' if ff and fid
                          else f'grid ({gx}, {gy})') + ('   - click the other focus to link' if st['link'] else '')

    def start_link(kind):
        if st['sel']:
            st['link'] = (kind, st['sel'])
            canvas.configure(cursor='crosshair')
            status['text'] = 'Click the focus to link to (Esc cancels).'

    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label='Add child focus below', command=lambda: add_child())
    menu.add_command(label='Add prerequisite (required)...', command=lambda: start_link('prereq'))
    menu.add_command(label='Add "or" prerequisite...', command=lambda: start_link('or'))
    menu.add_command(label='Make mutually exclusive with...', command=lambda: start_link('mutex'))
    menu.add_command(label='Duplicate', command=lambda: duplicate())
    menu.add_separator()
    menu.add_command(label='Delete', command=lambda: delete())
    empty_menu = tk.Menu(root, tearoff=0)

    def on_right(e):
        fid = focus_at(e)
        if fid:
            st['sel'] = fid
            fill_form()
            redraw()
            menu.tk_popup(e.x_root, e.y_root)
        elif st['ff']:
            at = grid_at(e)
            empty_menu.delete(0, 'end')
            empty_menu.add_command(label=f'Add focus here ({at[0]}, {at[1]})', command=lambda: add_child(at))
            empty_menu.tk_popup(e.x_root, e.y_root)

    canvas.bind('<ButtonPress-1>', on_press)
    canvas.bind('<ButtonRelease-1>', on_release)
    canvas.bind('<Motion>', on_motion)
    canvas.bind('<Button-3>', on_right)
    canvas.bind('<Double-Button-1>', lambda e: None if focus_at(e) else add_child(grid_at(e)))
    canvas.bind('<MouseWheel>', lambda e: (canvas.xview_scroll if e.state & 1 else canvas.yview_scroll)(
        -1 if e.delta > 0 else 1, 'units'))
    canvas.bind('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
    canvas.bind('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))
    canvas.bind('<ButtonPress-2>', lambda e: canvas.scan_mark(e.x, e.y))
    canvas.bind('<B2-Motion>', lambda e: canvas.scan_dragto(e.x, e.y, gain=1))
    root.bind('<Escape>', lambda e: (st.update(link=None), canvas.configure(cursor='')))
    root.bind('<Delete>', lambda e: delete() if root.focus_get() in (canvas, None) or root.focus_get() is root else None)

    def on_problem(_):
        sel = problems.selection()
        if not sel:
            return
        fid, fix = fixes[sel[0]]
        if fix:
            fix()
            changed()
        elif fid in st['ff'].focuses:
            st['sel'] = fid
            fill_form()
            redraw()
            x, y = pos(st['ff'].focuses[fid])
            bb = canvas.bbox('all')
            if bb:
                canvas.xview_moveto(max(0, (x - bb[0] - canvas.winfo_width() / 2) / max(1, bb[2] - bb[0])))
                canvas.yview_moveto(max(0, (y - bb[1] - canvas.winfo_height() / 2) / max(1, bb[3] - bb[1])))

    problems.bind('<Double-1>', on_problem)

    # ---------------- file actions
    def confirm_discard():
        ff = st['ff']
        return not ff or not ff.dirty or messagebox.askyesno('Unsaved', 'Discard unsaved changes to this tree?')

    def open_file(path):
        if not confirm_discard():
            file_pick.set(os.path.relpath(st['ff'].path, mod.root) if st['ff'] else '')
            return
        st['ff'] = FocusFile(path)
        st['others'] = all_focus_ids(mod, path)
        st['sel'] = None
        file_pick.set(os.path.relpath(path, mod.root))
        changed()
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    def save():
        ff = st['ff']
        if not ff:
            return
        errs = [p for p in check(ff, mod, all_sprites(), st.get('others')) if p[0] == 'error']
        if errs and not messagebox.askyesno('Errors', f'{len(errs)} errors, e.g. "{errs[0][2]}". Save anyway?'):
            return
        ff.save()
        redraw()
        status['text'] = f'Saved {os.path.relpath(ff.path, mod.root)}.'

    def new_tree():
        if not confirm_discard():
            return
        tag = simpledialog.askstring('New focus tree', 'Country tag (e.g. ALD):', parent=root)
        if not tag or not re.fullmatch(r'[A-Z0-9]{3}', tag.strip().upper()):
            return
        tag = tag.strip().upper()
        path = mod.path('common', 'national_focus', f'{tag}_focus.txt')
        if os.path.exists(path):
            messagebox.showerror('New focus tree', f'{os.path.relpath(path, mod.root)} already exists.')
            return
        write_text(path, tree_text(f'{tag}_focus', tag, f'{tag}_start'))
        files.append(os.path.relpath(path, mod.root))
        file_pick['values'] = files
        st['ff'] = None
        open_file(path)
        status['text'] = f'Created {os.path.relpath(path, mod.root)} for {tag}.'

    def tree_settings():
        ff = st['ff']
        if not ff or not ff.trees:
            return
        s, e = spans(ff.text, 'focus_tree')[0]
        a, b = inner(ff.text, (s, e))
        t = ff.trees[0]
        tags = [v for k, v in walk_items(get(t, 'country') or []) if k == 'tag']
        dlg = tk.Toplevel(root)
        dlg.title('Tree settings')
        v = {'id': tk.StringVar(value=get(t, 'id', '')), 'tags': tk.StringVar(value=' '.join(tags)),
             'default': tk.StringVar(value=get(t, 'default', 'no'))}
        for i, (k, label) in enumerate((('id', 'Tree id'), ('tags', 'Country tags (space separated)'),
                                        ('default', 'Default tree (yes/no)'))):
            ttk.Label(dlg, text=label).grid(row=i, column=0, sticky='w', padx=6, pady=2)
            ttk.Entry(dlg, textvariable=v[k], width=30).grid(row=i, column=1, padx=6, pady=2)

        def ok():
            body = ff.text[a:b]
            body = set_top(body, 'id', v['id'].get().strip())
            body = set_top(body, 'default', 'yes' if v['default'].get().strip() == 'yes' else 'no')
            new_tags = v['tags'].get().upper().split()
            if new_tags != tags:
                mods = ''.join(f'\t\tmodifier = {{\n\t\t\tadd = 10\n\t\t\ttag = {x}\n\t\t}}\n' for x in new_tags)
                body = set_top(body, 'country', f'{{\n\t\tfactor = 0\n{mods}\t}}')
            ff.apply(ff.text[:a] + body + ff.text[b:])
            dlg.destroy()
            changed()

        ttk.Button(dlg, text='OK', command=ok).grid(row=3, column=1, sticky='e', padx=6, pady=6)

    def set_game_dir():
        d = filedialog.askdirectory(title='Hearts of Iron IV install folder (the one with interface/ and gfx/)')
        if d:
            settings['game_dir'] = d
            save_settings(settings)
            st['vanilla'] = game_sprites(d)
            icons.clear()
            changed(keep_form=True)
            status['text'] = f'{len(st["vanilla"])} vanilla focus icons found.'

    def zoom(f):
        st['zoom'] = max(0.3, min(2.0, st['zoom'] * f))
        icons.clear()
        redraw()

    def undo():
        if st['ff']:
            st['ff'].undo_step()
            changed()

    def redo():
        if st['ff']:
            st['ff'].redo_step()
            changed()

    file_pick.bind('<<ComboboxSelected>>', lambda e: open_file(mod.path(file_pick.get())))
    for text, cmd in (('New tree...', new_tree), ('Save', save), ('Undo', undo), ('Redo', redo),
                      ('Zoom -', lambda: zoom(0.8)), ('Zoom +', lambda: zoom(1.25)),
                      ('Add focus', lambda: add_child()), ('Tree settings...', tree_settings),
                      ('Game folder...', set_game_dir)):
        ttk.Button(bar, text=text, command=cmd).pack(side='left', padx=2)
    ttk.Label(bar, foreground='#777', text='  drag = move, right-click = links/add/delete, double-click empty = new focus'
              ).pack(side='left')
    root.bind('<Control-s>', lambda e: save())
    root.bind('<Control-z>', lambda e: undo() if root.focus_get() not in (script, desc, pre) else None)
    root.bind('<Control-y>', lambda e: redo() if root.focus_get() not in (script, desc, pre) else None)
    root.protocol('WM_DELETE_WINDOW', lambda: confirm_discard() and root.destroy())
    if files:
        open_file(mod.path(next((f for f in files if 'HOD_' in f or 'focus' in f.lower()), files[0])))
    root.mainloop()


def walk_items(items):
    for k, v in items:
        yield k, v
        if isinstance(v, list):
            yield from walk_items(v)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root_dir = args[0] if args else find_mod_root()
    if '--check' in sys.argv:
        if not root_dir:
            sys.exit('usage: hoi4_focus_editor.py MOD_FOLDER --check')
        m = Mod(root_dir)
        vanilla = game_sprites(load_settings().get('game_dir'))
        for f in m.files('common/national_focus'):
            ff = FocusFile(f)
            if not ff.focuses:
                continue
            probs = check(ff, m, {**vanilla, **m.sprites})
            print(f'== {os.path.basename(f)}: {len(ff.focuses)} focuses, {len(probs)} problems')
            for lvl, fid, msg, _ in probs:
                print(f'   [{lvl}] {fid}: {msg}')
    else:
        run_gui(root_dir)
