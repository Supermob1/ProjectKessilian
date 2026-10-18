"""HOI4 Country Editor: browse every country of a mod, edit its files, and list what it is missing.

Run:  python hoi4_country_editor.py [mod_folder]           (GUI)
      python hoi4_country_editor.py [mod_folder] --report  (text report, no GUI)
"""
import colorsys
import os
import re
import sys
from collections import Counter, defaultdict

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
                if v in ('rgb', 'hsv', 'hsv360') and pos < len(tokens) and tokens[pos] == '{':
                    pos += 1
                    items.append((t.strip('"'), [('', v)] + block()))  # color = rgb { 1 2 3 } -> [rgb, 1, 2, 3]
                elif v == '{':
                    items.append((t.strip('"'), block()))
                else:
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


def to_rgb(color):
    """Parsed `color = rgb { r g b }` / `hsv { h s v }` / `{ r g b }` -> (r, g, b) or None."""
    if not isinstance(color, list):
        return None
    vals = [v for _, v in color]
    kind = vals.pop(0) if vals and vals[0] in ('rgb', 'hsv', 'hsv360') else 'rgb'
    try:
        nums = [float(v) for v in vals[:3]]
    except ValueError:
        return None
    if len(nums) < 3:
        return None
    if kind == 'rgb':
        return tuple(max(0, min(255, int(n))) for n in nums)
    h, sat, val = (nums[0] / 360, nums[1] / 100, nums[2] / 100) if kind == 'hsv360' else nums
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, sat, val))


def set_top(text, key, value):
    """Replace the first top-level `key = ...` (value or { block }) with `key = value`, or append it.
    Edits the text in place so comments and the rest of the file are kept."""
    toks = [m for m in TOKEN.finditer(text) if not m.group().startswith('#')]
    depth = 0
    for i, m in enumerate(toks):
        t = m.group()
        if t == '{':
            depth += 1
        elif t == '}':
            depth -= 1
        elif depth == 0 and t == key and i + 2 < len(toks) and toks[i + 1].group() == '=':
            j = i + 2
            if toks[j].group() in ('rgb', 'hsv', 'hsv360') and j + 1 < len(toks) and toks[j + 1].group() == '{':
                j += 1
            end = toks[j].end()
            if toks[j].group() == '{':
                d = 0
                for k in range(j, len(toks)):
                    d += {'{': 1, '}': -1}.get(toks[k].group(), 0)
                    if d == 0:
                        end = toks[k].end()
                        break
            return text[:m.start()] + f'{key} = {value}' + text[end:]
    return text.rstrip('\n') + f'\n{key} = {value}\n'


def block_text(pairs):
    return '{\n' + ''.join(f'\t{k} = {v}\n' for k, v in pairs) + '}'


def set_loc(mod, key, value, fallback):
    """Write one localisation key: change its line where it lives, append to `fallback` if new, delete if empty."""
    path = mod.loc_file.get(key)
    line = re.compile(rf'^[ \t]*{re.escape(key)}:\d*[ \t]*".*(\n|$)', re.M)
    if path:
        text = read_text(path)
        text = line.sub(lambda m: f' {key}:0 "{value}"' + m.group(1) if value else '', text, count=1)
    elif value:
        path = fallback
        text = read_text(path) if os.path.exists(path) else 'l_english:\n'
        text = text.rstrip('\n') + f'\n {key}:0 "{value}"\n'
    else:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_text(path, text)
    mod.loc[key], mod.loc_file[key] = value, path


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
        for f in self.files('localisation', '_l_english.yml'):
            for line in read_text(f).splitlines():
                m = LOC_LINE.match(line)
                if m:
                    self.loc[m.group(1)] = m.group(2)
                    self.loc_file[m.group(1)] = f

        self.characters = {}  # id -> (body, file)
        for f in self.files('common/characters'):
            for cid, body in get(parse(read_text(f)), 'characters', []) or []:
                if isinstance(body, list):
                    self.characters[cid] = (body, f)

        self.history = {}  # TAG -> history file
        self.ruling = {}
        for f in self.files('history/countries'):
            m = re.match(r'([A-Z0-9]{3})\b', os.path.basename(f))
            if m and m.group(1) not in self.history:
                self.history[m.group(1)] = f
                self.ruling[m.group(1)] = get(get(parse(read_text(f)), 'set_politics', []) or [], 'ruling_party')

        self.color = {}  # TAG -> (r, g, b) map colour
        self.ideo_color = {i: to_rgb(get(b, 'color')) for f in self.files('common/ideologies')
                           for i, b in (get(parse(read_text(f)), 'ideologies', []) or []) if isinstance(b, list)}
        for tag, rel in self.tags.items():
            f = self.find(os.path.join('common', rel))
            if f:
                self.color[tag] = to_rgb(get(parse(read_text(f)), 'color'))

        self.states = {}  # id -> dict(name, provinces, owner, cores, file)
        self.prov_state = {}
        for f in self.files('history/states'):
            for st in get_all(parse(read_text(f)), 'state'):
                hist = get(st, 'history', []) or []
                sid = get(st, 'id')
                name = get(st, 'name', '')
                provs = [v for _, v in (get(st, 'provinces', []) or [])]
                self.states[sid] = dict(name=self.loc.get(name, name), provinces=provs, owner=get(hist, 'owner'),
                                        cores=get_all(hist, 'add_core_of'), file=f)
                for p in provs:
                    self.prov_state[p] = sid
        self.state_count = Counter(s['owner'] for s in self.states.values())

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

    def state_colors(self, mode, tag=None):
        """State id -> colour for a map mode: 'countries', 'cores' (of tag) or 'ideology'."""
        out = {}
        for sid, st in self.states.items():
            owner = st['owner']
            if mode == 'cores':
                c = (210, 40, 40) if tag in st['cores'] else (240, 170, 60) if owner == tag else (95, 95, 95)
            elif mode == 'ideology':
                c = self.ideo_color.get(self.ruling.get(owner))
            else:
                c = self.color.get(owner)
            out[sid] = c or (95, 95, 95)
        return out


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
    from tkinter import ttk, filedialog, messagebox, colorchooser
    try:
        from PIL import Image, ImageTk
    except ImportError:
        Image = None  # still usable: no map and no flag pictures

    root = tk.Tk()
    root.title('HOI4 Country Editor')
    root.geometry('1600x950')

    if not mod_root:
        mod_root = filedialog.askdirectory(title='Pick your mod folder (the one with common/, history/, gfx/)')
        if not mod_root:
            return
    mod = Mod(mod_root)
    root.title(f'HOI4 Country Editor - {mod.root}')
    state = {'country': None}
    flags = {}

    def flag_photo(name, size):
        if (name, size) not in flags:
            f = mod.find(f'gfx/flags/{name}.tga')
            flags[name, size] = None
            if f and Image:
                try:
                    flags[name, size] = ImageTk.PhotoImage(Image.open(f).convert('RGBA').resize(size, Image.LANCZOS))
                except OSError:
                    pass
        return flags[name, size]

    status = ttk.Label(root, anchor='w')
    status.pack(side='bottom', fill='x')
    # classic PanedWindow: per-pane minsize so no panel can start collapsed (ttk sashpos runs before Windows sizes it)
    panes = tk.PanedWindow(root, orient='horizontal', sashwidth=6, sashrelief='raised')
    panes.pack(fill='both', expand=True)

    # ---------------- left: country list
    left = ttk.Frame(panes)
    panes.add(left, width=470, minsize=250, stretch='never')
    top = ttk.Frame(left)
    top.pack(fill='x', padx=4, pady=4)
    ttk.Label(top, text='Search:').pack(side='left')
    search = tk.StringVar()
    ttk.Entry(top, textvariable=search).pack(side='left', fill='x', expand=True)
    countries = ttk.Treeview(left, columns=('tag', 'states', 'miss'), show='tree headings')
    for col, txt, w in (('#0', 'Country', 230), ('tag', 'Tag', 45), ('states', 'States', 50), ('miss', 'Missing req/rec', 95)):
        countries.heading(col, text=txt)
        countries.column(col, width=w, anchor='w' if col == '#0' else 'center')
    lsb = ttk.Scrollbar(left, command=countries.yview)
    countries.configure(yscrollcommand=lsb.set)
    btns = ttk.Frame(left)
    btns.pack(side='bottom', fill='x', padx=4, pady=4)
    lsb.pack(side='right', fill='y')
    countries.pack(fill='both', expand=True, padx=(4, 0))

    # ---------------- middle: map
    mid = ttk.Frame(panes)
    panes.add(mid, width=600, minsize=250, stretch='always')
    modes = ttk.Frame(mid)
    modes.pack(fill='x', padx=4, pady=4)
    map_mode = tk.StringVar(value='countries')
    ttk.Label(modes, text='Map:').pack(side='left')
    for val, txt in (('countries', 'Countries'), ('cores', 'Cores of the selected'), ('ideology', 'Ruling ideology')):
        ttk.Radiobutton(modes, text=txt, value=val, variable=map_mode, command=lambda: redraw(True)).pack(side='left')
    ttk.Label(modes, text='  wheel: zoom, right-drag: move', foreground='#777').pack(side='left')
    canvas = tk.Canvas(mid, background='#1b2238', highlightthickness=0)
    canvas.pack(fill='both', expand=True)
    mp = {'full': None, 'rgb': {}, 'sea': set(), 'lut': None, 'scale': None, 'x0': 0, 'y0': 0, 'photo': None}
    SEA, NONE = (27, 34, 56), (95, 95, 95)

    prov_file, def_file = mod.find('map/provinces.bmp'), mod.find('map/definition.csv')
    if Image and prov_file and def_file:
        mp['full'] = Image.open(prov_file).convert('RGB')
        for line in read_text(def_file).splitlines():
            p = line.split(';')
            if len(p) >= 5 and p[0].isdigit() and p[0] != '0':
                mp['rgb'][int(p[1]), int(p[2]), int(p[3])] = p[0]
                if p[4] in ('sea', 'lake'):
                    mp['sea'].add(p[0])
    else:
        canvas.create_text(20, 20, anchor='nw', fill='white',
                           text='No map: needs map/provinces.bmp, map/definition.csv and Pillow (pip install pillow).')

    def redraw(new_colors=False):
        full = mp['full']
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if not full or w < 10 or h < 10:
            return
        if new_colors or mp['lut'] is None:
            tag = getattr(state['country'], 'tag', None)
            sc = mod.state_colors(map_mode.get(), tag)
            mp['lut'] = {c: SEA if pid in mp['sea'] else sc.get(mod.prov_state.get(pid), NONE)
                         for c, pid in mp['rgb'].items()}
        fit = max(full.width / w, full.height / h)
        if mp['scale'] is None:
            mp['scale'] = fit
            mp['x0'], mp['y0'] = (full.width - w * fit) / 2, (full.height - h * fit) / 2
        s, x0, y0 = mp['scale'], mp['x0'], mp['y0']
        view = full.crop((int(x0), int(y0), int(x0 + w * s), int(y0 + h * s))).resize((w, h), Image.NEAREST)
        lut = mp['lut']
        pixels = view.get_flattened_data() if hasattr(view, 'get_flattened_data') else view.getdata()
        img = Image.new('RGB', (w, h))
        img.putdata([lut.get(p, SEA) for p in pixels])
        mp['photo'] = ImageTk.PhotoImage(img)
        canvas.delete('all')
        canvas.create_image(0, 0, anchor='nw', image=mp['photo'])

    def state_at(x, y):
        full = mp['full']
        if not full or mp['scale'] is None:
            return None
        fx, fy = int(mp['x0'] + x * mp['scale']), int(mp['y0'] + y * mp['scale'])
        if not (0 <= fx < full.width and 0 <= fy < full.height):
            return None
        return mod.prov_state.get(mp['rgb'].get(full.getpixel((fx, fy))))

    def on_zoom(e):
        if mp['scale'] is None:
            return
        up = getattr(e, 'delta', 0) > 0 or getattr(e, 'num', 0) == 4
        fx, fy = mp['x0'] + e.x * mp['scale'], mp['y0'] + e.y * mp['scale']
        full = mp['full']
        fit = max(full.width / canvas.winfo_width(), full.height / canvas.winfo_height())
        mp['scale'] = min(fit, max(0.25, mp['scale'] * (0.8 if up else 1.25)))
        mp['x0'], mp['y0'] = fx - e.x * mp['scale'], fy - e.y * mp['scale']
        redraw()

    def on_drag_start(e):
        mp['drag'] = (e.x, e.y)

    def on_drag(e):
        if mp['scale'] is None:
            return
        dx, dy = mp['drag']
        mp['x0'] -= (e.x - dx) * mp['scale']
        mp['y0'] -= (e.y - dy) * mp['scale']
        mp['drag'] = (e.x, e.y)
        redraw()

    def state_label(sid):
        st = mod.states[sid]
        o = st['owner']
        return f'{st["name"]} ({sid})  -  {mod.loc.get(o, o or "unowned")} ({o or "-"})'

    def on_motion(e):
        sid = state_at(e.x, e.y)
        status['text'] = state_label(sid) if sid else ''

    def on_click(e):
        sid = state_at(e.x, e.y)
        owner = sid and mod.states[sid]['owner']
        if owner in mod.tags:
            if not countries.exists(owner):
                search.set('')
            countries.selection_set(owner)
            countries.see(owner)

    canvas.bind('<Configure>', lambda e: redraw())
    canvas.bind('<MouseWheel>', on_zoom)
    canvas.bind('<Button-4>', on_zoom)
    canvas.bind('<Button-5>', on_zoom)
    canvas.bind('<ButtonPress-3>', on_drag_start)
    canvas.bind('<B3-Motion>', on_drag)
    canvas.bind('<Motion>', on_motion)
    canvas.bind('<Button-1>', on_click)

    # ---------------- right: country page
    right = ttk.Frame(panes)
    panes.add(right, width=720, minsize=450, stretch='never')
    head = ttk.Frame(right)
    head.pack(fill='x', padx=6, pady=6)
    head_flag = ttk.Label(head)
    head_flag.pack(side='left')
    head_name = ttk.Label(head, font=('Segoe UI', 14, 'bold'))
    head_name.pack(side='left', padx=10)
    head_info = ttk.Label(right, foreground='#555')
    head_info.pack(fill='x', padx=6)

    nb = ttk.Notebook(right)
    nb.pack(fill='both', expand=True, padx=4, pady=4)
    overview = ttk.Frame(nb, padding=6)
    nb.add(overview, text='Overview')

    def tab(title, columns, widths=None):
        frame = ttk.Frame(nb)
        nb.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=(widths or {}).get(col, 140))
        sb = ttk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        return tree

    checklist = tab('Checklist', ('status', 'level', 'check'), {'status': 70, 'level': 90, 'check': 480})
    checklist.tag_configure('bad_required', foreground='#c00000')
    checklist.tag_configure('bad_recommended', foreground='#b06000')
    checklist.tag_configure('bad_optional', foreground='#777777')
    leaders = tab('Leaders', ('id', 'name', 'roles', 'ideology', 'portrait'))
    ideas = tab('National ideas', ('idea', 'name'), {'idea': 250, 'name': 300})
    units = tab('OOB', ('oob', 'content'), {'oob': 150, 'content': 420})

    ed_frame = ttk.Frame(nb)
    nb.add(ed_frame, text='Edit files')
    bar = ttk.Frame(ed_frame)
    bar.pack(fill='x')
    file_pick = ttk.Combobox(bar, state='readonly', width=45)
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

    def after_save():
        mod.reload()
        flags.clear()
        refresh_list()
        redraw(True)
        show(state['country'].tag)

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
        after_save()

    file_pick.bind('<<ComboboxSelected>>', load_file)
    ttk.Button(bar, text='Save (Ctrl+S)', command=save_file).pack(side='left', padx=4)
    ttk.Button(bar, text='Reload from disk', command=load_file).pack(side='left')
    root.bind('<Control-s>', lambda e: save_file() if nb.index('current') == nb.index(ed_frame) else None)

    def fill(tree, rows, tags=None):
        tree.delete(*tree.get_children())
        for i, r in enumerate(rows):
            tree.insert('', 'end', values=r, tags=(tags[i],) if tags else ())

    def open_folder(path):
        if hasattr(os, 'startfile'):
            os.startfile(path)
        else:
            import subprocess
            subprocess.Popen(['xdg-open', path])

    # ---------------- overview form
    def build_overview(c):
        for w in overview.winfo_children():
            w.destroy()
        tag, h = c.tag, c.history
        ideologies = list(mod.ideologies)
        names = {}  # loc key -> StringVar
        g = ttk.Frame(overview)
        g.pack(fill='x')
        for col, txt in enumerate(('Names', 'Name', 'Long name (_DEF)', 'Adjective (_ADJ)', 'Party name')):
            ttk.Label(g, text=txt, font=('Segoe UI', 9, 'bold') if col == 0 else None).grid(row=0, column=col, sticky='w')
        for r, ideo in enumerate([''] + ideologies, 1):
            ttk.Label(g, text=ideo or 'default').grid(row=r, column=0, sticky='w', padx=(0, 6))
            base = f'{tag}_{ideo}' if ideo else tag
            keys = [base, f'{base}_DEF', f'{base}_ADJ'] + ([f'{tag}_{ideo}_party'] if ideo else [])
            for col, key in enumerate(keys, 1):
                names[key] = tk.StringVar(value=mod.loc.get(key, ''))
                ttk.Entry(g, textvariable=names[key], width=14).grid(row=r, column=col, padx=1, pady=1)
        ttk.Label(overview, foreground='#777', text='Empty ideology names fall back to the default one. New keys are '
                  'saved next to the existing country name localisation.').pack(anchor='w', pady=(2, 6))
        ttk.Separator(overview).pack(fill='x', pady=4)

        cf = ttk.Frame(overview)
        cf.pack(fill='x')
        color = list(mod.color.get(tag) or (128, 128, 128))
        ttk.Label(cf, text='Map colour:').grid(row=0, column=0, sticky='w')
        swatch = tk.Label(cf, width=8, relief='solid', background='#%02x%02x%02x' % tuple(color))
        swatch.grid(row=0, column=1, sticky='w', padx=6)

        def pick():
            rgb, hexa = colorchooser.askcolor(swatch['background'], parent=root)
            if rgb:
                color[:] = [int(x) for x in rgb]
                swatch['background'] = hexa

        ttk.Button(cf, text='Pick...', command=pick).grid(row=0, column=2)
        ttk.Label(cf, text='Flags:').grid(row=1, column=0, sticky='nw', pady=4)
        fl = ttk.Frame(cf)
        fl.grid(row=1, column=1, columnspan=8, sticky='w', pady=4)
        for i, ideo in enumerate([''] + ideologies):
            img = flag_photo(f'{tag}_{ideo}' if ideo else tag, (54, 36))
            ttk.Label(fl, image=img or '', text='' if img else '(none)').grid(row=i // 5 * 2, column=i % 5, padx=6)
            ttk.Label(fl, text=(ideo or 'base')[:14], font=('Segoe UI', 8)).grid(row=i // 5 * 2 + 1, column=i % 5)
        ttk.Separator(overview).pack(fill='x', pady=4)

        ff = ttk.Frame(overview)
        ff.pack(fill='x')
        pol = get(h, 'set_politics', []) or []
        v = {k: tk.StringVar(value=val) for k, val in (
            ('capital', get(h, 'capital', '')), ('set_stability', get(h, 'set_stability', '')),
            ('set_war_support', get(h, 'set_war_support', '')), ('set_research_slots', get(h, 'set_research_slots', '')),
            ('ruling_party', get(pol, 'ruling_party', '')), ('last_election', get(pol, 'last_election', '')),
            ('election_frequency', get(pol, 'election_frequency', '')))}
        elections = tk.BooleanVar(value=get(pol, 'elections_allowed') == 'yes')
        row = 0
        for key, txt in (('capital', 'Capital (state id):'), ('set_stability', 'Stability (0-1):'),
                         ('set_war_support', 'War support (0-1):'), ('set_research_slots', 'Research slots:')):
            ttk.Label(ff, text=txt).grid(row=row, column=0, sticky='w')
            ttk.Entry(ff, textvariable=v[key], width=12).grid(row=row, column=1, sticky='w', pady=1)
            row += 1
        cap_name = ttk.Label(ff, foreground='#555')
        cap_name.grid(row=0, column=2, sticky='w', padx=8)
        v['capital'].trace_add('write', lambda *_: cap_name.configure(
            text=mod.states.get(v['capital'].get(), {}).get('name', 'unknown state')))
        v['capital'].set(v['capital'].get())
        ttk.Label(ff, text='Ruling party:').grid(row=row, column=0, sticky='w')
        ttk.Combobox(ff, textvariable=v['ruling_party'], values=ideologies, state='readonly', width=18).grid(
            row=row, column=1, columnspan=2, sticky='w')
        row += 1
        ttk.Label(ff, text='Last election / every (months):').grid(row=row, column=0, sticky='w')
        ttk.Entry(ff, textvariable=v['last_election'], width=12).grid(row=row, column=1, sticky='w')
        ttk.Entry(ff, textvariable=v['election_frequency'], width=6).grid(row=row, column=2, sticky='w', padx=8)
        ttk.Checkbutton(ff, text='Elections allowed', variable=elections).grid(row=row, column=3, sticky='w')
        row += 1
        ttk.Label(ff, text='Popularities (%):').grid(row=row, column=0, sticky='nw')
        pf = ttk.Frame(ff)
        pf.grid(row=row, column=1, columnspan=4, sticky='w')
        pops = {}
        total = ttk.Label(pf)
        for i, ideo in enumerate(ideologies):
            pops[ideo] = tk.StringVar(value=f'{c.popularities.get(ideo, 0):g}')
            ttk.Label(pf, text=ideo[:12] + ':').grid(row=i // 3, column=(i % 3) * 2, sticky='e')
            ttk.Spinbox(pf, from_=0, to=100, textvariable=pops[ideo], width=5).grid(
                row=i // 3, column=(i % 3) * 2 + 1, sticky='w', padx=(2, 8), pady=1)

        def upd_total(*_):
            try:
                t = sum(float(x.get() or 0) for x in pops.values())
                total.configure(text=f'total {t:g}', foreground='#080' if abs(t - 100) < 0.01 else '#c00')
            except ValueError:
                total.configure(text='not a number', foreground='#c00')

        for x in pops.values():
            x.trace_add('write', upd_total)
        upd_total()
        total.grid(row=(len(ideologies) + 2) // 3, column=0, columnspan=2, sticky='w')
        row += 1
        ttk.Label(ff, text='Leader at start:').grid(row=row, column=0, sticky='w')
        leader = c.ideo_rows.get(c.ruling, {}).get('leader', '')
        ttk.Label(ff, text=leader or 'none for the ruling party').grid(row=row, column=1, columnspan=3, sticky='w')

        def save():
            try:
                for key in ('set_stability', 'set_war_support'):
                    if v[key].get() and not 0 <= float(v[key].get()) <= 1:
                        raise ValueError(f'{key} must be between 0 and 1')
                for key in ('capital', 'set_research_slots', 'election_frequency'):
                    if v[key].get() and not v[key].get().isdigit():
                        raise ValueError(f'{key} must be a whole number')
                popv = {i: float(x.get() or 0) for i, x in pops.items()}
            except ValueError as e:
                messagebox.showerror('Not saved', str(e))
                return
            if v['capital'].get() and v['capital'].get() not in mod.states:
                if not messagebox.askyesno('Capital', f'State {v["capital"].get()} does not exist. Save anyway?'):
                    return
            if abs(sum(popv.values()) - 100) > 0.01:
                if not messagebox.askyesno('Popularities', f'They add up to {sum(popv.values()):g}, not 100. Save anyway?'):
                    return
            hfile = mod.history.get(tag) or mod.path('history', 'countries', f'{tag} - {c.name() or tag}.txt')
            old = read_text(hfile) if os.path.exists(hfile) else ''
            new = old
            for key in ('capital', 'set_stability', 'set_war_support', 'set_research_slots'):
                if v[key].get():
                    new = set_top(new, key, v[key].get())
            p = dict((k, val) for k, val in (get(parse(new), 'set_politics', []) or []) if isinstance(val, str))
            p.update(ruling_party=v['ruling_party'].get(), elections_allowed='yes' if elections.get() else 'no')
            if v['last_election'].get():
                p['last_election'] = f'"{v["last_election"].get()}"'
            if v['election_frequency'].get():
                p['election_frequency'] = v['election_frequency'].get()
            if p != dict((k, val) for k, val in (get(parse(old), 'set_politics', []) or []) if isinstance(val, str)):
                new = set_top(new, 'set_politics', block_text(p.items()))
            if {i: x for i, x in popv.items() if x} != {i: x for i, x in c.popularities.items() if x}:
                new = set_top(new, 'set_popularities', block_text((i, f'{x:g}') for i, x in popv.items()))
            if new != old:
                write_text(hfile, new)
            cfile = c.files.get('Country file (color, culture)')
            if cfile and tuple(color) != mod.color.get(tag):
                write_text(cfile, set_top(read_text(cfile), 'color', 'rgb {{ {} {} {} }}'.format(*color)))
            fallback = mod.loc_file.get(tag) or mod.path('localisation', 'english', 'country_editor_l_english.yml')
            for key, var in names.items():
                if var.get().strip() != mod.loc.get(key, ''):
                    set_loc(mod, key, var.get().strip().replace('"', "'"), fallback)
            after_save()
            status['text'] = f'Saved {tag}.'

        bf = ttk.Frame(overview)
        bf.pack(fill='x', pady=8)
        ttk.Button(bf, text='Save overview', command=save).pack(side='left')
        ttk.Button(bf, text='Edit history file', command=lambda: (nb.select(ed_frame))).pack(side='left', padx=4)
        ttk.Button(bf, text='Open flags folder', command=lambda: open_folder(mod.path('gfx', 'flags'))).pack(side='left')

    def show(tag):
        c = mod.country(tag)
        state['country'] = c
        head_flag.configure(image=flag_photo(tag, (82, 52)) or '')
        head_name.configure(text=f'{c.name() or "(no name)"}  ({tag})')
        hf = mod.history.get(tag)
        head_info.configure(text=f'{mod.state_count.get(tag, 0)} states on the map    '
                                 f'{os.path.relpath(hf, mod.root) if hf else "no history file"}')
        build_overview(c)
        order = {REQUIRED: 0, RECOMMENDED: 1, OPTIONAL: 2}
        rows = sorted(c.checks, key=lambda x: (x[1], order[x[0]]))
        fill(checklist, [('OK' if ok else 'MISSING', lvl, txt) for lvl, ok, txt in rows],
             ['ok' if ok else f'bad_{lvl}' for lvl, ok, _ in rows])
        fill(leaders, [(cid, name, roles, ideo, 'none' if pic is None else (pic or 'MISSING FILE'))
                       for cid, name, roles, ideo, pic in c.leaders])
        fill(ideas, [(i, mod.loc.get(i, '')) for _, i in (get(c.history, 'add_ideas', []) or [])])
        fill(units, [(k, line) for k, lines in c.units.items() for line in lines])
        file_pick['values'] = list(c.files)
        if c.files:
            file_pick.current(next((i for i, k in enumerate(c.files) if k.startswith('History')), 0))
            load_file()
        if map_mode.get() == 'cores':
            redraw(True)

    def refresh_list(*_):
        sel = countries.selection()
        countries.delete(*countries.get_children())
        q = search.get().lower()
        for tag in sorted(mod.tags, key=lambda t: (mod.loc.get(t) or t).lower()):
            c = mod.country(tag)
            if q and q not in f'{tag} {c.name()}'.lower():
                continue
            req = sum(1 for x in c.missing if x[0] == REQUIRED)
            rec = sum(1 for x in c.missing if x[0] == RECOMMENDED)
            countries.insert('', 'end', iid=tag, text=c.name() or tag, image=flag_photo(tag, (24, 16)) or '',
                             values=(tag, mod.state_count.get(tag, 0), f'{req} / {rec}'))
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
        flags.clear()
        refresh_list()
        redraw(True)

    countries.bind('<<TreeviewSelect>>', on_select)
    search.trace_add('write', refresh_list)
    ttk.Button(btns, text='Reload mod', command=reload_all).pack(side='left')
    ttk.Button(btns, text='Export missing report', command=export).pack(side='left', padx=4)
    refresh_list()
    if countries.get_children():  # open on the first country so the right panel is never blank
        countries.selection_set(countries.get_children()[0])
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
