"""Event, event-chain and decision authoring window for HOI4 Country Editor."""
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox

from hoi4_country_editor import Mod, TOKEN, find_mod_root, get, parse, read_text, set_loc, walk, write_text


def block_spans(text, key=None, level=None):
    """Yield (start, end, nesting level) for Clausewitz `key = { ... }` blocks."""
    tokens = [m for m in TOKEN.finditer(text) if not m.group().startswith('#')]
    depth = 0
    out = []
    i = 0
    while i < len(tokens):
        token = tokens[i].group()
        if token == '}':
            depth = max(0, depth - 1)
            i += 1
            continue
        if token == '{':
            depth += 1
            i += 1
            continue
        name_ok = key is None or token.strip('"') == key
        if name_ok and i + 2 < len(tokens) and tokens[i + 1].group() == '=' and tokens[i + 2].group() == '{':
            if level is None or depth == level:
                start = tokens[i].start()
                open_i = i + 2
                brace_depth = 0
                close_i = None
                for j in range(open_i, len(tokens)):
                    if tokens[j].group() == '{':
                        brace_depth += 1
                    elif tokens[j].group() == '}':
                        brace_depth -= 1
                        if brace_depth == 0:
                            close_i = j
                            break
                if close_i is not None:
                    out.append((start, tokens[close_i].end(), depth))
        i += 1
    return out


def replace_block(text, key, old_id, new_script, level=0):
    for start, end, _ in block_spans(text, key, level):
        body = parse(text[start:end])
        block = get(body, key, [])
        # Events carry an explicit id inside their block; decisions use their block key as the id.
        if get(block, 'id') == old_id or key == old_id:
            return text[:start] + new_script.rstrip() + text[end:]
    raise ValueError(f'Could not find {key} {old_id} in file.')


def insert_in_block(text, key, index, snippet, level=0):
    spans = block_spans(text, key, level)
    if index >= len(spans):
        raise ValueError(f'Could not find {key} block {index + 1}.')
    _, end, _ = spans[index]
    close = end - 1
    return text[:close].rstrip() + '\n' + snippet.rstrip() + '\n' + text[close:]


def records(mod):
    events, decisions, namespaces = [], [], {}
    for path in mod.files('events'):
        text = read_text(path)
        for ns in [v for k, v in parse(text) if k == 'add_namespace' and isinstance(v, str)]:
            namespaces.setdefault(ns, path)
        for event_type in ('country_event', 'news_event', 'state_event', 'unit_leader_event'):
            for start, end, _ in block_spans(text, event_type, 0):
                script = text[start:end]
                body = get(parse(script), event_type, [])
                eid = get(body, 'id')
                if eid:
                    events.append(dict(path=path, type=event_type, id=eid, title=get(body, 'title', ''),
                                       desc=get(body, 'desc', ''), script=script))
    for path in mod.files('common/decisions'):
        text = read_text(path)
        for category, body in parse(text):
            if not category or not isinstance(body, list):
                continue
            for decision_id, decision in body:
                if isinstance(decision, list) and get(decision, 'cost') is not None:
                    spans = block_spans(text, decision_id, 1)
                    match = next(((s, e) for s, e, _ in spans
                                  if get(get(parse(text[s:e]), decision_id, []), 'cost') is not None), None)
                    if match:
                        s, e = match
                        decisions.append(dict(path=path, category=category, id=decision_id,
                                              script=text[s:e], title=mod.loc.get(decision_id, '')))
    return events, decisions, namespaces


def event_links(script):
    result = []
    parsed = parse(script)
    if not parsed:
        return result
    body = parsed[0][1]
    for key, value in walk(body):
        if key in ('country_event', 'news_event') and isinstance(value, list):
            eid = get(value, 'id')
            if eid:
                result.append(eid)
    return result


def run_editor(mod_root, parent=None, selected_tag='REP'):
    mod = Mod(mod_root)
    events, decisions, namespace_files = records(mod)
    if parent is None:
        win = tk.Tk()
    else:
        win = tk.Toplevel(parent)
        win.transient(parent)
    win.title(f'HOI4 Events & Decisions - {mod.root}')
    win.geometry('1480x940')
    active = {'event': None, 'decision': None}
    loc_fallback = mod.path('localisation', 'english', 'HOD_Event_Editor_l_english.yml')

    status = ttk.Label(win, anchor='w', relief='sunken')
    status.pack(side='bottom', fill='x')
    editor_bar = ttk.Frame(win, padding=(8, 4))
    editor_bar.pack(fill='x')
    ttk.Label(editor_bar, text='Open editor:').pack(side='left', padx=(0, 5))

    def open_country_editor():
        from hoi4_country_editor import run_gui
        run_gui(mod.root)

    def open_focus_editor():
        from hoi4_focus_editor import run_gui
        run_gui(mod.root)

    def open_tech_editor():
        from hoi4_tech_editor import run_gui
        run_gui(mod.root)

    ttk.Button(editor_bar, text='Country', command=open_country_editor).pack(side='left', padx=2)
    ttk.Button(editor_bar, text='Focus tree', command=open_focus_editor).pack(side='left', padx=2)
    ttk.Button(editor_bar, text='Technology', command=open_tech_editor).pack(side='left', padx=2)
    tabs = ttk.Notebook(win)
    tabs.pack(fill='both', expand=True, padx=6, pady=6)

    def save_localization(values):
        for key, value in values:
            if key and value:
                set_loc(mod, key, value.replace('"', "'"), loc_fallback)
        mod.reload()

    def edit_localization(title, values):
        dlg = tk.Toplevel(win)
        dlg.title(title)
        dlg.transient(win)
        dlg.grab_set()
        box = ttk.Frame(dlg, padding=10)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text='Edit the English text stored for each localization key.',
                  foreground='#555').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))
        fields = []
        for row, (key, label) in enumerate(values, start=1):
            ttk.Label(box, text=f'{label} ({key}):').grid(row=row, column=0, sticky='w', padx=(0, 8), pady=3)
            value = tk.StringVar(value=mod.loc.get(key, ''))
            ttk.Entry(box, textvariable=value, width=70).grid(row=row, column=1, sticky='we', pady=3)
            fields.append((key, value))

        def save_text():
            save_localization([(key, value.get().strip()) for key, value in fields])
            dlg.destroy()
            refresh_event_preview()
            refresh_chain_roots()
            for selected in event_tree.selection():
                values_now = list(event_tree.item(selected, 'values'))
                if values_now:
                    item = events[int(selected)]
                    values_now[1] = mod.loc.get(item['title'], item['title'])
                    event_tree.item(selected, values=values_now)
            for selected in dc_tree.selection():
                values_now = list(dc_tree.item(selected, 'values'))
                if values_now:
                    item = decisions[int(selected)]
                    values_now[2] = mod.loc.get(item['id'], item['id'])
                    dc_tree.item(selected, values=values_now)

        buttons = ttk.Frame(box)
        buttons.grid(row=len(fields) + 1, column=0, columnspan=2, sticky='e', pady=(8, 0))
        ttk.Button(buttons, text='Save localization', command=save_text).pack(side='left', padx=4)
        ttk.Button(buttons, text='Cancel', command=dlg.destroy).pack(side='left')
        box.columnconfigure(1, weight=1)

    def set_script_field(script, field, value, anchor='id'):
        pattern = rf'(?m)^(\s*){re.escape(field)}\s*=.*(?:\r?\n|$)'
        match = re.search(pattern, script)
        if match:
            if not value:
                return script[:match.start()] + script[match.end():]
            return script[:match.start()] + f'{match.group(1)}{field} = {value}\n' + script[match.end():]
        if not value:
            return script
        anchor_match = re.search(rf'(?m)^(\s*{re.escape(anchor)}\s*=.*(?:\r?\n|$))', script)
        if anchor_match:
            indent = re.match(r'\s*', anchor_match.group(1)).group(0)
            return script[:anchor_match.end()] + f'{indent}{field} = {value}\n' + script[anchor_match.end():]
        return script.rstrip() + f'\n\t{field} = {value}\n'

    def reload_records():
        nonlocal events, decisions, namespace_files
        events, decisions, namespace_files = records(mod)
        refill_events()
        refill_decisions()
        refresh_chain_roots()

    # ----------------------------- Events and event chains
    ev_frame = ttk.Frame(tabs, padding=6)
    tabs.add(ev_frame, text='Events')
    ev_bar = ttk.Frame(ev_frame)
    ev_bar.pack(fill='x', pady=(0, 5))
    event_work = ttk.Panedwindow(ev_frame, orient='horizontal')
    event_work.pack(fill='both', expand=True)
    event_list_panel = ttk.Frame(event_work)
    event_detail_panel = ttk.Frame(event_work)
    event_work.add(event_list_panel, weight=1)
    event_work.add(event_detail_panel, weight=3)
    event_columns = ('id', 'title', 'type', 'file')
    event_tree = ttk.Treeview(event_list_panel, columns=event_columns, show='headings', height=18)
    for col, width in (('id', 150), ('title', 190), ('type', 110), ('file', 280)):
        event_tree.heading(col, text=col.title())
        event_tree.column(col, width=width, stretch=(col in ('id', 'title')))
    event_tree.pack(fill='both', expand=True)
    ev_edit_bar = ttk.Frame(event_detail_panel)
    ev_edit_bar.pack(fill='x', pady=4)
    detail_tabs = ttk.Notebook(event_detail_panel)
    detail_tabs.pack(fill='both', expand=True)
    script_frame = ttk.Frame(detail_tabs, padding=5)
    preview_frame = ttk.Frame(detail_tabs, padding=12)
    detail_tabs.add(script_frame, text='Script')
    detail_tabs.add(preview_frame, text='In-game preview')
    ttk.Label(script_frame, text='Edit the event script directly; comments and unsupported effects are kept.',
              foreground='#555').pack(anchor='w')
    ev_script = tk.Text(script_frame, wrap='none', undo=True, font=('Consolas', 10), height=22)
    ev_scroll = ttk.Scrollbar(script_frame, command=ev_script.yview)
    ev_script.configure(yscrollcommand=ev_scroll.set)
    ev_scroll.pack(side='right', fill='y')
    ev_script.pack(fill='both', expand=True)

    preview_canvas_frame = ttk.Frame(preview_frame)
    preview_canvas_frame.pack(fill='both', expand=True)
    preview_scrollbar = ttk.Scrollbar(preview_canvas_frame, orient='vertical')
    preview_scrollbar.pack(side='right', fill='y')
    preview_canvas = tk.Canvas(preview_canvas_frame, background='#11182b', highlightthickness=0,
                               yscrollcommand=preview_scrollbar.set)
    preview_canvas.pack(side='left', fill='both', expand=True)
    preview_scrollbar.configure(command=preview_canvas.yview)
    preview_state = {'photos': [], 'body': None}
    try:
        from PIL import Image, ImageTk, ImageOps
    except ImportError:
        Image = ImageTk = ImageOps = None
    picture_cache = {}
    game_photo_cache = {}

    def picture_path(key):
        texture = mod.sprites.get(key, key)
        candidates = [texture]
        if texture and not str(texture).lower().startswith('gfx'):
            candidates.append(os.path.join('gfx', texture))
        for candidate in candidates:
            if candidate:
                path = mod.find(candidate)
                if path:
                    return path
        return None

    def picture_photo(key, size, fit=False):
        cache_key = (key, size, fit)
        if cache_key not in picture_cache:
            picture_cache[cache_key] = None
            path = picture_path(key)
            if path and Image and ImageTk:
                try:
                    with Image.open(path) as source:
                        image = source.convert('RGBA')
                        if fit and ImageOps:
                            image = ImageOps.fit(image, size, method=Image.LANCZOS)
                        else:
                            image.thumbnail(size, Image.LANCZOS)
                        picture_cache[cache_key] = ImageTk.PhotoImage(image)
                except (OSError, ValueError):
                    pass
        return picture_cache[cache_key]

    def game_asset_photo(rel_path, size):
        cache_key = (rel_path, size)
        if cache_key not in game_photo_cache:
            game_photo_cache[cache_key] = None
            path = mod.find(rel_path)
            if path and Image and ImageTk:
                try:
                    with Image.open(path) as source:
                        image = source.convert('RGBA').resize(size, Image.LANCZOS)
                        game_photo_cache[cache_key] = ImageTk.PhotoImage(image)
                except (OSError, ValueError):
                    pass
        return game_photo_cache[cache_key]

    def game_text_plain(value):
        palette = {'R': '#ff625d', 'G': '#65ce8a', 'B': '#6bbcff', 'Y': '#ffdf4d',
                   'C': '#34d9ee', 'P': '#d98cff', 'O': '#ffab53', 'L': '#b6c7ff',
                   'g': '#aab2c2', 't': '#aab2c2', 'W': '#ffffff', 'r': '#ff625d', 'b': '#6bbcff'}
        text = str(value or '').replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '\t')
        pattern = re.compile(r'[§$]([RGBYCPOLgtrbW!])')
        segments, color, start = [], '#e7eaf1', 0
        for match in pattern.finditer(text):
            if match.start() > start:
                segments.append((text[start:match.start()], color))
            code = match.group(1)
            color = '#e7eaf1' if code == '!' else palette[code]
            start = match.end()
        if start < len(text):
            segments.append((text[start:], color))
        return ''.join(t for t, _ in segments), next((c for t, c in segments if t.strip()), '#e7eaf1')

    def render_game_text(widget, value):
        palette = {'R': '#ff625d', 'G': '#65ce8a', 'B': '#6bbcff', 'Y': '#ffdf4d',
                   'C': '#34d9ee', 'P': '#d98cff', 'O': '#ffab53', 'L': '#b6c7ff',
                   'g': '#aab2c2', 't': '#aab2c2', 'W': '#ffffff', 'r': '#ff625d',
                   'b': '#6bbcff'}
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.tag_configure('base', foreground='#e7eaf1')
        for code, color in palette.items():
            widget.tag_configure(f'color_{code}', foreground=color)
        text = str(value or '').replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '\t')
        pattern = re.compile(r'[§$]([RGBYCPOLgtrbW!])')
        color_tag = 'base'
        start = 0
        for match in pattern.finditer(text):
            if match.start() > start:
                widget.insert('end', text[start:match.start()], color_tag)
            code = match.group(1)
            color_tag = 'base' if code == '!' else f'color_{code}'
            start = match.end()
        if start < len(text):
            widget.insert('end', text[start:], color_tag)
        widget.configure(state='disabled')

    def choose_sprite_image(parent, current, kind, callback):
        if not Image or not ImageTk:
            messagebox.showerror('Picture browser', 'Pillow is required to browse event and decision pictures.',
                                 parent=parent)
            return
        if kind == 'event':
            keys = sorted(k for k in mod.sprites if k.startswith('GFX_') and 'event' in k.lower()
                          and picture_path(k))
            prefix = 'Event pictures'
        else:
            keys = sorted(k for k in mod.sprites if k.startswith('GFX_decision_') and picture_path(k))
            prefix = 'Decision icons'
        dlg = tk.Toplevel(parent)
        dlg.title(f'Browse {prefix.lower()}')
        dlg.geometry('1120x760')
        dlg.transient(parent)
        dlg.grab_set()
        toolbar = ttk.Frame(dlg, padding=6)
        toolbar.pack(fill='x')
        ttk.Label(toolbar, text='Search:').pack(side='left')
        search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=search_var, width=38).pack(side='left', padx=5)
        ttk.Label(toolbar, text=f'{len(keys)} registered images found', foreground='#666').pack(side='left', padx=8)
        panes = ttk.Panedwindow(dlg, orient='horizontal')
        panes.pack(fill='both', expand=True, padx=6, pady=(0, 6))
        gallery = ttk.Frame(panes)
        detail = ttk.Frame(panes, padding=10)
        panes.add(gallery, weight=3)
        panes.add(detail, weight=2)
        gallery_canvas = tk.Canvas(gallery, background='#26313d', highlightthickness=0)
        gallery_scroll = ttk.Scrollbar(gallery, orient='vertical', command=gallery_canvas.yview)
        gallery_canvas.configure(yscrollcommand=gallery_scroll.set)
        gallery_scroll.pack(side='right', fill='y')
        gallery_canvas.pack(fill='both', expand=True)
        gallery_inner = ttk.Frame(gallery_canvas)
        gallery_window = gallery_canvas.create_window((0, 0), window=gallery_inner, anchor='nw')
        gallery_inner.bind('<Configure>', lambda _e: gallery_canvas.configure(
            scrollregion=gallery_canvas.bbox('all')))
        gallery_canvas.bind('<Configure>', lambda e: gallery_canvas.itemconfigure(gallery_window, width=e.width))
        selected = {'key': current if current in keys else (keys[0] if keys else '')}
        gallery_refs = []
        gallery_tiles = {}
        ttk.Label(detail, text='Selected picture', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        detail_image = ttk.Label(detail, text='No matching image', anchor='center')
        detail_image.pack(fill='both', expand=True, pady=8)
        detail_name = ttk.Label(detail, text='')
        detail_name.pack(fill='x', pady=(0, 8))

        def show_selected(key):
            selected['key'] = key
            photo = picture_photo(key, (430, 360)) if key else None
            detail_image.configure(image=photo, text='' if photo else 'Image could not be loaded')
            detail_image.image = photo
            detail_name.configure(text=key)
            for tile_key, tile in gallery_tiles.items():
                tile.configure(highlightbackground='#e7c75c' if tile_key == key else '#526273')

        def fill_gallery(*_):
            for child in gallery_inner.winfo_children():
                child.destroy()
            gallery_refs.clear()
            gallery_tiles.clear()
            query = search_var.get().strip().lower()
            shown = [key for key in keys if query in key.lower()][:500]
            for index, key in enumerate(shown):
                photo = picture_photo(key, (150, 92))
                tile = tk.Frame(gallery_inner, background='#344252', padx=5, pady=5,
                                highlightthickness=2,
                                highlightbackground='#e7c75c' if key == selected['key'] else '#526273')
                tile.grid(row=index // 4, column=index % 4, padx=4, pady=4, sticky='nsew')
                gallery_tiles[key] = tile
                gallery_refs.append(photo)
                image_label = tk.Label(tile, image=photo, text='' if photo else 'Image unavailable',
                                       background='#26313d', foreground='white', width=19, height=7)
                image_label.pack(fill='both', expand=True)
                name_label = tk.Label(tile, text=key, background='#344252', foreground='white',
                                      wraplength=145, font=('Segoe UI', 8))
                name_label.pack(fill='x', pady=(4, 0))
                for widget in (tile, image_label, name_label):
                    widget.bind('<Button-1>', lambda _e, k=key: show_selected(k))
                    widget.bind('<Double-1>', lambda _e, k=key: (callback(k), dlg.destroy()))
            for col in range(4):
                gallery_inner.columnconfigure(col, weight=1)
            gallery_canvas.configure(scrollregion=gallery_canvas.bbox('all'))

        show_selected(selected['key'])
        fill_gallery()
        search_var.trace_add('write', fill_gallery)
        buttons = ttk.Frame(dlg, padding=6)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='Clear picture', command=lambda: (callback(''), dlg.destroy())).pack(side='left')
        ttk.Button(buttons, text='Use selected picture', command=lambda: (callback(selected['key']), dlg.destroy())).pack(
            side='right', padx=4)
        ttk.Button(buttons, text='Cancel', command=dlg.destroy).pack(side='right')

    def refresh_event_preview(*_):
        for child in preview_canvas.winfo_children():
            child.destroy()
        preview_canvas.delete('all')
        preview_state['photos'] = []
        script = ev_script.get('1.0', 'end-1c')
        parsed = parse(script)
        event_type, body = parsed[0] if parsed else ('country_event', [])
        title_key = get(body, 'title', '')
        desc_key = get(body, 'desc', '')
        picture_key = get(body, 'picture', '')
        title = mod.loc.get(title_key, title_key or 'Select an event').upper()
        description = mod.loc.get(desc_key, desc_key or '')
        options = [v for k, v in body if k == 'option' and isinstance(v, list)]

        scale = 1.0
        panel_w, top_h = 581, 121
        tile_h = 66
        bottom_h = max(206, 16 + len(options) * 48)
        content_w = round(512 * scale)
        body_widget = tk.Text(preview_canvas, wrap='word', background='#11182c', foreground='#e7eaf1',
                              relief='flat', borderwidth=0, font=('Segoe UI', 11, 'bold'),
                              padx=0, pady=2, spacing1=2, spacing3=5)
        render_game_text(body_widget, description)
        body_widget.configure(width=64)
        body_widget.update_idletasks()
        display_lines = body_widget.count('1.0', 'end-1c', 'displaylines')
        line_count = display_lines[0] if display_lines else max(1, description.count('\n') + 1)
        line_h = max(20, int(body_widget.tk.call('font', 'metrics', body_widget.cget('font'), '-linespace')))
        natural_desc_h = max(230, line_count * (line_h + 4) + 24)
        desc_h = min(natural_desc_h, 420)
        visible_lines = max(1, int((desc_h - 16) / max(1, line_h)))
        body_widget.configure(height=visible_lines)

        canvas_w = max(preview_canvas.winfo_width(), panel_w + 36)
        left = max(18, (canvas_w - panel_w) // 2)
        top_photo = game_asset_photo('gfx/interface/event_report_top_win.dds', (panel_w, top_h))
        tile_photo = game_asset_photo('gfx/interface/event_report_tileable_midsection.dds', (panel_w, tile_h))
        bottom_photo = game_asset_photo('gfx/interface/event_report_bottom_win.dds', (panel_w, bottom_h))
        if top_photo:
            preview_canvas.create_image(left, 0, image=top_photo, anchor='nw')
            preview_state['photos'].append(top_photo)
        else:
            preview_canvas.create_rectangle(left, 0, left + panel_w, top_h, fill='#17223a', outline='#45cfff', width=3)
        for y in range(top_h, top_h + desc_h, tile_h):
            if tile_photo:
                preview_canvas.create_image(left, y, image=tile_photo, anchor='nw')
                preview_state['photos'].append(tile_photo)
            else:
                preview_canvas.create_rectangle(left, y, left + panel_w, y + tile_h,
                                                fill='#11182c', outline='')
        if bottom_photo:
            preview_canvas.create_image(left, top_h + desc_h, image=bottom_photo, anchor='nw')
            preview_state['photos'].append(bottom_photo)
        else:
            preview_canvas.create_rectangle(left, top_h + desc_h, left + panel_w,
                                            top_h + desc_h + bottom_h, fill='#17223a', outline='#45cfff', width=3)

        preview_canvas.create_text(left + panel_w / 2, round(40 * scale), text=title,
                                   fill='#f5f6ff', font=('Segoe UI', 25, 'bold'), width=round(500 * scale))
        preview_canvas.create_window(left + round(31 * scale), top_h + round(8 * scale),
                                    window=body_widget, anchor='nw', width=content_w,
                                    height=max(1, desc_h - round(16 * scale)))
        preview_state['body'] = body_widget
        body_widget.bind('<MouseWheel>', lambda e: body_widget.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        body_widget.bind('<Button-4>', lambda _e: body_widget.yview_scroll(-1, 'units'))
        body_widget.bind('<Button-5>', lambda _e: body_widget.yview_scroll(1, 'units'))

        picture_photo_image = picture_photo(picture_key, (round(210 * scale), round(176 * scale)), fit=True) \
            if picture_key else None
        picture_x, picture_y = left + round(5 * scale), top_h + desc_h
        if picture_photo_image:
            preview_canvas.create_image(picture_x, picture_y, image=picture_photo_image, anchor='nw')
            preview_state['photos'].append(picture_photo_image)
        else:
            preview_canvas.create_rectangle(picture_x, picture_y, picture_x + round(213 * scale),
                                            picture_y + round(182 * scale), fill='#0b1325', outline='#46cfff', width=3)
            preview_canvas.create_text(picture_x + round(106 * scale), picture_y + round(90 * scale),
                                       text='No picture' if not picture_key else f'Missing picture:\n{picture_key}',
                                       fill='#dce7f3', font=('Segoe UI', 10), width=round(190 * scale))
        clip_photo = game_asset_photo('gfx/interface/event_pic_clip.dds',
                                      (round(213 * scale), round(182 * scale)))
        if clip_photo:
            preview_canvas.create_image(picture_x, picture_y, image=clip_photo, anchor='nw')
            preview_state['photos'].append(clip_photo)

        option_x = left + round(215 * scale)
        option_bg = game_asset_photo('gfx/interface/event_option_entry.dds',
                                     (round(320 * scale), round(48 * scale)))
        for index, option in enumerate(options):
            key = get(option, 'name', 'Unnamed option')
            label = mod.loc.get(key, key)
            label_text, label_color = game_text_plain(label)
            option_y = picture_y + round(3 * scale) + index * round(51 * scale)
            if option_bg:
                preview_canvas.create_image(option_x, option_y, image=option_bg, anchor='nw')
                preview_state['photos'].append(option_bg)
            else:
                preview_canvas.create_rectangle(option_x, option_y, option_x + round(320 * scale),
                                                option_y + round(48 * scale), fill='#07142d', outline='#1dbcf3', width=2)
            preview_canvas.create_text(option_x + round(160 * scale), option_y + round(24 * scale),
                                       text=label_text, fill=label_color, font=('Segoe UI', 12, 'bold'),
                                       width=round(290 * scale), justify='center')
        if not options:
            preview_canvas.create_text(option_x + round(160 * scale), picture_y + round(24 * scale),
                                       text='No choices in this event', fill='#c5ccd8', font=('Segoe UI', 11))
        preview_canvas.configure(scrollregion=(0, 0, canvas_w, top_h + desc_h + bottom_h))

    def on_preview_resize(event):
        if preview_state.get('canvas_width') != event.width:
            preview_state['canvas_width'] = event.width
            win.after_idle(refresh_event_preview)

    preview_canvas.bind('<Configure>', on_preview_resize)
    preview_canvas.bind('<MouseWheel>', lambda e: preview_canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
    preview_canvas.bind('<Button-4>', lambda e: preview_canvas.yview_scroll(-1, 'units'))
    preview_canvas.bind('<Button-5>', lambda e: preview_canvas.yview_scroll(1, 'units'))

    ev_script.bind('<KeyRelease>', lambda _e: win.after_idle(refresh_event_preview))

    def refill_events():
        selected_id = active['event']['id'] if active['event'] else None
        event_tree.delete(*event_tree.get_children())
        for index, event in enumerate(events):
            title = mod.loc.get(event['title'], event['title'])
            event_tree.insert('', 'end', iid=str(index), values=(event['id'], title, event['type'],
                               os.path.relpath(event['path'], mod.root)))
        selected = next((str(i) for i, event in enumerate(events) if event['id'] == selected_id),
                        '0' if events else None)
        if selected is not None:
            event_tree.selection_set(selected)
            event_tree.focus(selected)
            select_event()
        else:
            active['event'] = None
            ev_script.delete('1.0', 'end')
            refresh_event_preview()

    def select_event(_=None):
        sel = event_tree.selection()
        if not sel:
            return
        event = events[int(sel[0])]
        active['event'] = event
        ev_script.delete('1.0', 'end')
        ev_script.insert('1.0', event['script'])
        ev_script.edit_modified(False)
        refresh_event_preview()
        detail_tabs.select(preview_frame)
        status.configure(text=f"Editing {event['id']} in {os.path.relpath(event['path'], mod.root)}")

    def edit_event_localization():
        event = active['event']
        if not event:
            return
        body = get(parse(ev_script.get('1.0', 'end-1c')), event['type'], [])
        values = []
        for label, key in (('Title', get(body, 'title', '')), ('Description', get(body, 'desc', ''))):
            if key:
                values.append((key, label))
        for index, option in enumerate((v for k, v in body if k == 'option' and isinstance(v, list)), start=1):
            key = get(option, 'name', '')
            if key:
                values.append((key, f'Choice {index}'))
        if values:
            edit_localization(f'Event localization — {event["id"]}', values)

    def set_event_picture():
        if not active['event']:
            return
        script = ev_script.get('1.0', 'end-1c')
        body = get(parse(script), active['event']['type'], [])
        current = get(body, 'picture', '')
        def apply_picture(picture_key):
            ev_script.delete('1.0', 'end')
            ev_script.insert('1.0', set_script_field(script, 'picture', picture_key))
            refresh_event_preview()
            status.configure(text='Picture updated in the editor. Save the event script to write it.')
        choose_sprite_image(win, current, 'event', apply_picture)

    event_tree.bind('<<TreeviewSelect>>', select_event)

    def save_event():
        event = active['event']
        if not event:
            return
        script = ev_script.get('1.0', 'end-1c')
        if script.count('{') != script.count('}'):
            messagebox.showerror('Unbalanced event', 'The event has mismatched braces; it was not saved.', parent=win)
            return
        text = read_text(event['path'])
        try:
            text = replace_block(text, event['type'], event['id'], script)
        except ValueError as exc:
            messagebox.showerror('Save event', str(exc), parent=win)
            return
        write_text(event['path'], text)
        ev_script.edit_modified(False)
        reload_records()
        status.configure(text=f"Saved {event['id']}.")

    def add_followup():
        event = active['event']
        if not event:
            messagebox.showinfo('Add follow-up', 'Select an event first.', parent=win)
            return
        script = ev_script.get('1.0', 'end-1c')
        options = []
        body = get(parse(script), event['type'], [])
        for i, option in enumerate([v for k, v in body if k == 'option' and isinstance(v, list)]):
            opt_key = get(option, 'name', f'Option {i + 1}')
            options.append((i, f"{opt_key}: {mod.loc.get(opt_key, opt_key)}"))
        if not options:
            messagebox.showinfo('Add follow-up', 'This event has no options to attach a follow-up to.', parent=win)
            return
        dlg = tk.Toplevel(win)
        dlg.title(f'Add follow-up to {event["id"]}')
        dlg.transient(win)
        dlg.grab_set()
        box = ttk.Frame(dlg, padding=10)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text='Choice that leads to the next event:').grid(row=0, column=0, sticky='w')
        option_var = tk.StringVar(value=options[0][1])
        ttk.Combobox(box, textvariable=option_var, values=[x[1] for x in options], state='readonly', width=58).grid(
            row=0, column=1, sticky='we', pady=3)
        ttk.Label(box, text='Next event:').grid(row=1, column=0, sticky='w')
        target_values = [f"{e['id']} — {mod.loc.get(e['title'], e['title'])}" for e in events]
        target_var = tk.StringVar(value=target_values[0] if target_values else '')
        ttk.Combobox(box, textvariable=target_var, values=target_values, state='readonly', width=58).grid(
            row=1, column=1, sticky='we', pady=3)
        ttk.Label(box, text='Recipient tag (ROOT = current country):').grid(row=2, column=0, sticky='w')
        tag_values = ['ROOT'] + sorted(mod.tags)
        tag_var = tk.StringVar(value=selected_tag if selected_tag in mod.tags else 'ROOT')
        ttk.Combobox(box, textvariable=tag_var, values=tag_values, state='readonly', width=20).grid(
            row=2, column=1, sticky='w', pady=3)
        ttk.Label(box, text='Delay in days:').grid(row=3, column=0, sticky='w')
        days_var = tk.StringVar(value='1')
        ttk.Entry(box, textvariable=days_var, width=12).grid(row=3, column=1, sticky='w', pady=3)
        ttk.Label(box, text='Add a follow-up link only; save the event script afterward.', foreground='#777').grid(
            row=4, column=0, columnspan=2, sticky='w', pady=5)

        def insert_link():
            target = next((e for e in events if target_var.get().startswith(e['id'] + ' — ')), None)
            if not target:
                messagebox.showerror('Add follow-up', 'Choose a target event.', parent=dlg)
                return
            try:
                days = max(0, int(days_var.get()))
            except ValueError:
                messagebox.showerror('Add follow-up', 'Delay must be a whole number of days.', parent=dlg)
                return
            option_index = next(i for i, label in options if label == option_var.get())
            link = f'country_event = {{ id = {target["id"]} days = {days} }}'
            tag = tag_var.get()
            snippet = link if tag == 'ROOT' else f'{tag} = {{ {link} }}'
            try:
                script_new = insert_in_block(script, 'option', option_index, snippet, level=1)
            except (ValueError, IndexError) as exc:
                messagebox.showerror('Add follow-up', str(exc), parent=dlg)
                return
            ev_script.delete('1.0', 'end')
            ev_script.insert('1.0', script_new)
            dlg.destroy()
            status.configure(text=f"Linked {event['id']} to {target['id']}; save the event to write the link.")

        buttons = ttk.Frame(box)
        buttons.grid(row=5, column=0, columnspan=2, sticky='e', pady=(8, 0))
        ttk.Button(buttons, text='Add link', command=insert_link).pack(side='left', padx=4)
        ttk.Button(buttons, text='Cancel', command=dlg.destroy).pack(side='left')
        box.columnconfigure(1, weight=1)

    def new_event():
        dlg = tk.Toplevel(win)
        dlg.title('Create event')
        dlg.transient(win)
        dlg.grab_set()
        box = ttk.Frame(dlg, padding=10)
        box.pack(fill='both', expand=True)
        existing_ns = sorted(namespace_files)
        ns_var = tk.StringVar(value='SW' if 'SW' in namespace_files else (existing_ns[0] if existing_ns else 'HOD_custom'))
        type_var = tk.StringVar(value='country_event')
        title_var, desc_var = tk.StringVar(), tk.StringVar()
        option_var, picture_var = tk.StringVar(value='Continue'), tk.StringVar()
        ttk.Label(box, text='Namespace:').grid(row=0, column=0, sticky='w')
        ttk.Combobox(box, textvariable=ns_var, values=existing_ns, width=35).grid(row=0, column=1, sticky='w', pady=3)
        ttk.Label(box, text='Event type:').grid(row=1, column=0, sticky='w')
        ttk.Combobox(box, textvariable=type_var, values=('country_event', 'news_event'), state='readonly',
                     width=35).grid(row=1, column=1, sticky='w', pady=3)
        ttk.Label(box, text='English title localization:').grid(row=2, column=0, sticky='w')
        ttk.Entry(box, textvariable=title_var, width=60).grid(row=2, column=1, sticky='we', pady=3)
        ttk.Label(box, text='English description localization:').grid(row=3, column=0, sticky='w')
        ttk.Entry(box, textvariable=desc_var, width=60).grid(row=3, column=1, sticky='we', pady=3)
        ttk.Label(box, text='Event picture (GFX key):').grid(row=4, column=0, sticky='w')
        ttk.Combobox(box, textvariable=picture_var, values=sorted(k for k in mod.sprites if k.startswith('GFX_')),
                     width=58).grid(row=4, column=1, sticky='we', pady=3)
        ttk.Button(box, text='Browse images...',
                   command=lambda: choose_sprite_image(dlg, picture_var.get(), 'event', picture_var.set)).grid(
                       row=4, column=2, padx=4)
        ttk.Label(box, text='First choice localization:').grid(row=5, column=0, sticky='w')
        ttk.Entry(box, textvariable=option_var, width=60).grid(row=5, column=1, sticky='we', pady=3)
        ttk.Label(box, text='Additional choices can be added in the event script after creation.',
                  foreground='#777').grid(row=6, column=0, columnspan=2, sticky='w', pady=5)

        def create():
            ns = re.sub(r'[^A-Za-z0-9_]', '_', ns_var.get().strip())
            if not ns or not title_var.get().strip() or not desc_var.get().strip():
                messagebox.showerror('Create event', 'Namespace, title, and description are required.', parent=dlg)
                return
            nums = [int(e['id'].split('.', 1)[1]) for e in events
                    if e['id'].startswith(ns + '.') and e['id'].split('.', 1)[1].isdigit()]
            eid = f'{ns}.{max(nums, default=0) + 1}'
            path = namespace_files.get(ns) or mod.path('events', f'{ns}_Events.txt')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            file_text = read_text(path) if os.path.exists(path) else f'add_namespace = {ns}\n\n'
            if not any(k == 'add_namespace' and v == ns for k, v in parse(file_text)):
                file_text = f'add_namespace = {ns}\n' + file_text
            option_key = eid + '.a'
            picture_line = f'\tpicture = {picture_var.get().strip()}\n' if picture_var.get().strip() else ''
            script = (f'{type_var.get()} = {{\n\tid = {eid}\n\ttitle = {eid}.t\n\tdesc = {eid}.d\n'
                      f'{picture_line}\tis_triggered_only = yes\n\toption = {{\n\t\tname = {option_key}\n\t}}\n}}')
            write_text(path, file_text.rstrip() + '\n\n' + script + '\n')
            save_localization([(eid + '.t', title_var.get()), (eid + '.d', desc_var.get()),
                               (option_key, option_var.get())])
            dlg.destroy()
            reload_records()
            status.configure(text=f'Created {eid} in {os.path.relpath(path, mod.root)}.')

        b = ttk.Frame(box)
        b.grid(row=7, column=0, columnspan=2, sticky='e', pady=(8, 0))
        ttk.Button(b, text='Create event', command=create).pack(side='left', padx=4)
        ttk.Button(b, text='Cancel', command=dlg.destroy).pack(side='left')
        box.columnconfigure(1, weight=1)
        box.columnconfigure(2, weight=0)

    def delete_event():
        event = active['event']
        if not event or not messagebox.askyesno('Delete event', f"Delete {event['id']} from its file?", parent=win):
            return
        text = read_text(event['path'])
        for start, end, _ in block_spans(text, event['type'], 0):
            snippet = text[start:end]
            if get(get(parse(snippet), event['type'], []), 'id') == event['id']:
                write_text(event['path'], text[:start] + text[end:])
                break
        active['event'] = None
        ev_script.delete('1.0', 'end')
        reload_records()
        status.configure(text=f"Deleted {event['id']}.")

    ttk.Button(ev_bar, text='New event...', command=new_event).pack(side='left', padx=3)
    ttk.Button(ev_bar, text='Refresh', command=reload_records).pack(side='left', padx=3)
    ttk.Button(ev_edit_bar, text='Save event script', command=save_event).pack(side='left', padx=3)
    ttk.Button(ev_edit_bar, text='Edit localization...', command=edit_event_localization).pack(side='left', padx=3)
    ttk.Button(ev_edit_bar, text='Choose picture...', command=set_event_picture).pack(side='left', padx=3)
    ttk.Button(ev_edit_bar, text='Add follow-up event...', command=add_followup).pack(side='left', padx=3)
    ttk.Button(ev_edit_bar, text='Delete event...', command=delete_event).pack(side='left', padx=3)

    # ----------------------------- Visual event-chain browser
    chain_frame = ttk.Frame(tabs, padding=8)
    tabs.add(chain_frame, text='Event chains')
    chain_bar = ttk.Frame(chain_frame)
    chain_bar.pack(fill='x')
    ttk.Label(chain_bar, text='Start event:').pack(side='left')
    chain_root = tk.StringVar()
    chain_pick = ttk.Combobox(chain_bar, textvariable=chain_root, state='readonly', width=72)
    chain_pick.pack(side='left', padx=6)
    chain_tree = ttk.Treeview(chain_frame, columns=('title', 'file'), show='tree headings')
    chain_tree.heading('#0', text='Event ID')
    chain_tree.heading('title', text='Title')
    chain_tree.heading('file', text='File')
    chain_tree.column('#0', width=210)
    chain_tree.column('title', width=310)
    chain_tree.column('file', width=550)
    chain_tree.pack(fill='both', expand=True, pady=8)

    def refresh_chain_roots():
        chain_values = [f"{e['id']} — {mod.loc.get(e['title'], e['title'])}" for e in events]
        chain_pick['values'] = chain_values
        if chain_values and not chain_root.get():
            chain_root.set(chain_values[0])
        draw_chain()

    def draw_chain(*_):
        chain_tree.delete(*chain_tree.get_children())
        root_id = chain_root.get().split(' — ', 1)[0]
        by_id = {e['id']: e for e in events}
        if root_id not in by_id:
            return
        visited = set()

        def add(parent_iid, eid, depth):
            event = by_id.get(eid)
            if not event or depth > 12:
                return
            repeat = eid in visited
            iid = chain_tree.insert(parent_iid, 'end', text=eid + (' ↻' if repeat else ''),
                                    values=(mod.loc.get(event['title'], event['title']),
                                            os.path.relpath(event['path'], mod.root)))
            if repeat:
                return
            visited.add(eid)
            for child in event_links(event['script']):
                add(iid, child, depth + 1)

        add('', root_id, 0)
        for item in chain_tree.get_children(''):
            chain_tree.item(item, open=True)

    chain_pick.bind('<<ComboboxSelected>>', draw_chain)
    ttk.Button(chain_bar, text='Refresh graph', command=draw_chain).pack(side='left')

    # ----------------------------- Decisions
    dc_frame = ttk.Frame(tabs, padding=6)
    tabs.add(dc_frame, text='Decisions')
    dc_bar = ttk.Frame(dc_frame)
    dc_bar.pack(fill='x', pady=(0, 5))
    dc_columns = ('id', 'category', 'title', 'file')
    dc_tree = ttk.Treeview(dc_frame, columns=dc_columns, show='headings', height=11)
    for col, width in (('id', 250), ('category', 230), ('title', 280), ('file', 440)):
        dc_tree.heading(col, text=col.title())
        dc_tree.column(col, width=width, stretch=(col == 'file'))
    dc_tree.pack(fill='x')
    dc_edit_bar = ttk.Frame(dc_frame)
    dc_edit_bar.pack(fill='x', pady=4)
    icon_preview_bar = ttk.Frame(dc_frame)
    icon_preview_bar.pack(fill='x', pady=(0, 4))
    decision_icon_image = ttk.Label(icon_preview_bar)
    decision_icon_image.pack(side='left', padx=(0, 6))
    decision_icon_label = ttk.Label(icon_preview_bar, text='Select a decision to view its icon.')
    decision_icon_label.pack(side='left')
    decision_icon_state = {'photo': None}
    ttk.Label(dc_frame, text='Selected decision script:', foreground='#555').pack(anchor='w')
    dc_script = tk.Text(dc_frame, wrap='none', undo=True, font=('Consolas', 10), height=23)
    dc_scroll = ttk.Scrollbar(dc_frame, command=dc_script.yview)
    dc_script.configure(yscrollcommand=dc_scroll.set)
    dc_scroll.pack(side='right', fill='y')
    dc_script.pack(fill='both', expand=True)

    def refill_decisions():
        dc_tree.delete(*dc_tree.get_children())
        for index, decision in enumerate(decisions):
            dc_tree.insert('', 'end', iid=str(index), values=(decision['id'], decision['category'],
                              decision['title'], os.path.relpath(decision['path'], mod.root)))

    def select_decision(_=None):
        sel = dc_tree.selection()
        if not sel:
            return
        decision = decisions[int(sel[0])]
        active['decision'] = decision
        dc_script.delete('1.0', 'end')
        dc_script.insert('1.0', decision['script'])
        dc_script.edit_modified(False)
        refresh_decision_icon()
        status.configure(text=f"Editing decision {decision['id']}.")

    def decision_icon_choices():
        names = {'generic_operation', 'generic_industry', 'generic_spy', 'mission_icon'}
        for sprite in mod.sprites:
            if sprite.startswith('GFX_decision_'):
                names.add(sprite[len('GFX_decision_'):])
        for decision in decisions:
            body = get(parse(decision['script']), decision['id'], [])
            icon = get(body, 'icon', '')
            if icon:
                names.add(str(icon))
        return sorted(names)

    def refresh_decision_icon():
        decision = active['decision']
        if not decision:
            decision_icon_label.configure(text='Select a decision to view its icon.')
            decision_icon_image.configure(image='')
            decision_icon_state['photo'] = None
            return
        body = get(parse(dc_script.get('1.0', 'end-1c')), decision['id'], [])
        icon = get(body, 'icon', '')
        key = icon if str(icon).startswith('GFX_') else f'GFX_decision_{icon}'
        photo = picture_photo(key, (72, 72)) if icon else None
        decision_icon_state['photo'] = photo
        decision_icon_image.configure(image=photo or '')
        decision_icon_label.configure(text=f'Decision picture: {icon or "no icon set"}')

    def edit_decision_localization():
        decision = active['decision']
        if decision:
            edit_localization(f'Decision localization — {decision["id"]}',
                              [(decision['id'], 'Title'), (decision['id'] + '_desc', 'Description')])

    def set_decision_icon():
        decision = active['decision']
        if not decision:
            return
        script = dc_script.get('1.0', 'end-1c')
        body = get(parse(script), decision['id'], [])
        current = get(body, 'icon', '')
        current_key = current if str(current).startswith('GFX_decision_') else f'GFX_decision_{current}'

        def apply_icon(key):
            icon = key[len('GFX_decision_'):] if key.startswith('GFX_decision_') else key
            dc_script.delete('1.0', 'end')
            dc_script.insert('1.0', set_script_field(script, 'icon', icon))
            refresh_decision_icon()
            status.configure(text='Decision picture updated in the editor. Save the decision script to write it.')
        choose_sprite_image(win, current_key, 'decision', apply_icon)

    dc_tree.bind('<<TreeviewSelect>>', select_decision)

    def save_decision():
        decision = active['decision']
        if not decision:
            return
        script = dc_script.get('1.0', 'end-1c')
        if script.count('{') != script.count('}'):
            messagebox.showerror('Unbalanced decision', 'The decision has mismatched braces; it was not saved.', parent=win)
            return
        text = read_text(decision['path'])
        try:
            text = replace_block(text, decision['id'], decision['id'], script, level=1)
        except ValueError as exc:
            messagebox.showerror('Save decision', str(exc), parent=win)
            return
        write_text(decision['path'], text)
        dc_script.edit_modified(False)
        reload_records()
        status.configure(text=f"Saved decision {decision['id']}.")

    def new_decision():
        dlg = tk.Toplevel(win)
        dlg.title('Create decision')
        dlg.transient(win)
        dlg.grab_set()
        box = ttk.Frame(dlg, padding=10)
        box.pack(fill='both', expand=True)
        category_var = tk.StringVar(value=f'{selected_tag}_episode_decisions')
        id_var = tk.StringVar(value=f'{selected_tag}_episode_decision_1')
        title_var, desc_var = tk.StringVar(), tk.StringVar()
        cost_var, icon_var = tk.StringVar(value='0'), tk.StringVar(value='generic_operation')
        file_var = tk.StringVar(value=os.path.basename(mod.path('common', 'decisions', f'{selected_tag}_decisions.txt')))
        rows = [('Category:', category_var), ('Decision id:', id_var), ('English title localization:', title_var),
                ('English description localization:', desc_var), ('Political power cost:', cost_var),
                ('Decision picture/icon:', icon_var),
                ('File name:', file_var)]
        for row, (label, var) in enumerate(rows):
            ttk.Label(box, text=label).grid(row=row, column=0, sticky='w')
            if var is icon_var:
                ttk.Combobox(box, textvariable=var, values=decision_icon_choices(), width=60).grid(
                    row=row, column=1, sticky='we', pady=3)
                ttk.Button(box, text='Browse images...', command=lambda: choose_sprite_image(
                    dlg, f'GFX_decision_{icon_var.get()}', 'decision',
                    lambda key: icon_var.set(key[len('GFX_decision_'):] if key.startswith('GFX_decision_') else key)
                )).grid(row=row, column=2, padx=4)
            else:
                ttk.Entry(box, textvariable=var, width=62).grid(row=row, column=1, sticky='we', pady=3)
        row = len(rows)
        ttk.Label(box, text='Visible trigger:').grid(row=row, column=0, sticky='nw')
        visible = tk.Text(box, width=60, height=3, font=('Consolas', 9))
        visible.insert('1.0', 'always = yes')
        visible.grid(row=row, column=1, sticky='we', pady=3)
        row += 1
        ttk.Label(box, text='Available trigger:').grid(row=row, column=0, sticky='nw')
        available = tk.Text(box, width=60, height=3, font=('Consolas', 9))
        available.insert('1.0', 'always = yes')
        available.grid(row=row, column=1, sticky='we', pady=3)
        row += 1
        ttk.Label(box, text='Completion effects:').grid(row=row, column=0, sticky='nw')
        effects = tk.Text(box, width=60, height=6, font=('Consolas', 9))
        effects.insert('1.0', 'add_political_power = 10')
        effects.grid(row=row, column=1, sticky='we', pady=3)
        row += 1
        ttk.Label(box, text='Optional event on completion:').grid(row=row, column=0, sticky='w')
        linked_event = tk.StringVar()
        event_values = [''] + [e['id'] for e in events]
        ttk.Combobox(box, textvariable=linked_event, values=event_values, width=58).grid(
            row=row, column=1, sticky='we', pady=3)

        def create():
            did = id_var.get().strip()
            category = category_var.get().strip()
            try:
                cost = float(cost_var.get())
            except ValueError:
                messagebox.showerror('Create decision', 'Cost must be a number.', parent=dlg)
                return
            if not did or not category or not title_var.get().strip() or not desc_var.get().strip():
                messagebox.showerror('Create decision', 'Category, id, title, and description are required.', parent=dlg)
                return
            filename = os.path.basename(file_var.get().strip())
            if not filename.lower().endswith('.txt'):
                filename += '.txt'
            path = mod.path('common', 'decisions', filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            file_text = read_text(path) if os.path.exists(path) else ''
            already = any(d['id'] == did for d in decisions)
            if already:
                messagebox.showerror('Create decision', f'Decision id {did} already exists.', parent=dlg)
                return
            visible_text = visible.get('1.0', 'end-1c').strip() or 'always = yes'
            available_text = available.get('1.0', 'end-1c').strip() or 'always = yes'
            effect_text = effects.get('1.0', 'end-1c').strip()
            if linked_event.get().strip():
                effect_text = (effect_text + '\n' if effect_text else '') + \
                              f'country_event = {{ id = {linked_event.get().strip()} }}'
            visible_text = '\n\t\t'.join(visible_text.splitlines())
            available_text = '\n\t\t'.join(available_text.splitlines())
            effect_text = '\n\t\t'.join(effect_text.splitlines())
            script = (f'{did} = {{\n\tcost = {cost:g}\n\tfire_only_once = yes\n\ticon = {icon_var.get().strip() or "generic_operation"}\n'
                      f'\tvisible = {{\n\t\t{visible_text}\n\t}}\n'
                      f'\tavailable = {{\n\t\t{available_text}\n\t}}\n'
                      f'\tcomplete_effect = {{\n\t\t{effect_text}\n\t}}\n}}')
            category_spans = block_spans(file_text, category, 0)
            if category_spans:
                file_text = insert_in_block(file_text, category, 0, script)
            else:
                file_text = file_text.rstrip() + f'\n\n{category} = {{\n{script}\n}}\n'
            write_text(path, file_text)
            save_localization([(did, title_var.get()), (did + '_desc', desc_var.get())])
            dlg.destroy()
            reload_records()
            status.configure(text=f'Created decision {did} in {os.path.relpath(path, mod.root)}.')

        b = ttk.Frame(box)
        b.grid(row=row + 1, column=0, columnspan=2, sticky='e', pady=(8, 0))
        ttk.Button(b, text='Create decision', command=create).pack(side='left', padx=4)
        ttk.Button(b, text='Cancel', command=dlg.destroy).pack(side='left')
        box.columnconfigure(1, weight=1)
        box.columnconfigure(2, weight=0)

    def delete_decision():
        decision = active['decision']
        if not decision or not messagebox.askyesno('Delete decision', f"Delete {decision['id']}?", parent=win):
            return
        text = read_text(decision['path'])
        try:
            text = replace_block(text, decision['id'], decision['id'], '', level=1)
        except ValueError as exc:
            messagebox.showerror('Delete decision', str(exc), parent=win)
            return
        write_text(decision['path'], text)
        active['decision'] = None
        dc_script.delete('1.0', 'end')
        reload_records()
        status.configure(text=f"Deleted decision {decision['id']}.")

    ttk.Button(dc_bar, text='New decision...', command=new_decision).pack(side='left', padx=3)
    ttk.Button(dc_bar, text='Refresh', command=reload_records).pack(side='left', padx=3)
    ttk.Button(dc_edit_bar, text='Save decision script', command=save_decision).pack(side='left', padx=3)
    ttk.Button(dc_edit_bar, text='Edit localization...', command=edit_decision_localization).pack(side='left', padx=3)
    ttk.Button(dc_edit_bar, text='Choose picture...', command=set_decision_icon).pack(side='left', padx=3)
    ttk.Button(dc_edit_bar, text='Delete decision...', command=delete_decision).pack(side='left', padx=3)

    refill_events()
    refill_decisions()
    refresh_chain_roots()
    win.focus_set()
    if parent is None:
        win.mainloop()
    return win


def main():
    import sys
    from tkinter import filedialog

    mod_root = next((arg for arg in sys.argv[1:] if not arg.startswith('--')), None) or find_mod_root()
    if not mod_root:
        picker = tk.Tk()
        picker.withdraw()
        mod_root = filedialog.askdirectory(title='Pick the mod folder (the one with descriptor.mod)')
        picker.destroy()
    if mod_root:
        run_editor(mod_root)


if __name__ == '__main__':
    main()
