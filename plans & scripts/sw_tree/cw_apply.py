"""Apply cw_map.py: redate rows, relabel GUI years, swap icons, rename. Idempotent only from the
post-import state (ROW keys are the import-time years) -> keep a done-marker file."""
import os, re, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cw_map import ROW, TECH, NAME, GAP, tech_blocks, enables

M = r"F:\Documents\Paradox Interactive\Hearts of Iron IV\mod\ProjectKessilian"
MARK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cw_dates_done")
rd = lambda p: open(p, encoding="utf-8-sig").read()
def wr(p, t, bom=False): open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\n").write(t)
techfiles = glob.glob(os.path.join(M, "common", "technologies", "hod_sw_*.txt"))

# 1+2. dates (once)
if not os.path.exists(MARK):
    for f in techfiles:
        t = re.sub(r"(start_year\s*=\s*)(\d+)", lambda m: m.group(1) + str(ROW.get(int(m.group(2)), int(m.group(2)))), rd(f))
        t = re.sub(r'(date\s*[<>=]+\s*"?)(9\d\d)\b', lambda m: m.group(1) + str(ROW.get(int(m.group(2)), int(m.group(2)))), t)
        wr(f, t)
    g = os.path.join(M, "interface", "countrytechtreeview.gui")
    t = re.sub(r'(text = ")(9[5-9]\d)(")', lambda m: m.group(1) + str(ROW.get(int(m.group(2)), int(m.group(2)))) + m.group(3), rd(g))
    wr(g, t)
    open(MARK, "w").write("done")

# 3. icons: tech sprite + the equipment it unlocks (ships excluded: hull icons are separate)
BLOCKS = {k: v for f in techfiles for k, v in tech_blocks(rd(f)).items()}
sprites = {}  # GFX name -> (file, texture)
for f in glob.glob(os.path.join(M, "interface", "*.gfx")):
    for m in re.finditer(r'name\s*=\s*"(GFX_[\w\-]+)"\s*texturefile\s*=\s*"([^"]+)"', rd(f), re.I):
        sprites.setdefault(m.group(1), (f, m.group(2)))
new, missing, gaps = [], [], []
def set_sprite(name, tex):
    if name in sprites and os.path.basename(sprites[name][0]).startswith("hod_sw_") and not sprites[name][0].endswith("hod_sw_cw_icons.gfx"):
        f = sprites[name][0]
        t = re.sub(r'(name\s*=\s*"%s"\s*texturefile\s*=\s*")[^"]+(")' % re.escape(name), lambda m: m.group(1) + tex + m.group(2), rd(f))
        wr(f, t)
    else:
        new.append(f'\tspriteType = {{\n\t\tname = "{name}"\n\t\ttexturefile = "{tex}"\n\t}}\n')
for tech, (_, _, icon) in TECH.items():
    if icon is None:
        continue
    if icon == GAP:
        gaps.append(tech); continue
    if not os.path.exists(os.path.join(M, icon)):  # our icons are often sprite aliases: GFX_<basename>
        alias = sprites.get("GFX_" + os.path.splitext(os.path.basename(icon))[0])
        if not alias or not os.path.exists(os.path.join(M, alias[1])):
            missing.append(icon); continue
        icon = alias[1]
    set_sprite(f"GFX_{tech}_medium", icon)
    for eq in enables(BLOCKS.get(tech, "")):
        if not eq.startswith("ship_hull"):
            set_sprite(f"GFX_{eq}_medium", icon)
wr(os.path.join(M, "interface", "hod_sw_cw_icons.gfx"), "spriteTypes = {\n" + "".join(new) + "}\n")
assert not missing, missing

# 4. names: rewrite the imported loc file in place
p = os.path.join(M, "localisation", "english", "hod_sw_tech_l_english.yml")
loc = {}
for l in rd(p).split("\n")[1:]:
    m = re.match(r"\s*([\w\-\.]+):\d*\s*\"(.*)\"\s*$", l)
    if m:
        loc[m.group(1)] = m.group(2)
for k, (n, d, _) in TECH.items():
    loc[k], loc[k + "_desc"] = n, d
for k, v in NAME.items():
    loc[k] = v
for k in list(loc):  # equipment descriptions written from the Empire's point of view -> drop the story, keep the name
    if k.endswith("_desc") and re.search(r"Imperial|Empire|stormtrooper|First Order|this planet|Earth", loc[k], re.I) \
            and k[:-5] not in TECH:
        loc[k] = loc.get(k[:-5], "")
esc = lambda s: s.replace('"', "'")
wr(p, "l_english:\n" + "".join(f' {k}:0 "{esc(v)}"\n' for k, v in loc.items()), bom=True)
left = [f"{k}: {v}" for k, v in loc.items() if not k.endswith("_desc") and re.search(r"Imperial|Empire|stormtrooper|First Order|TIE Reaper|Vengeance|Baron", v)]
print("icons swapped:", sum(1 for _, _, i in TECH.values() if i not in (None, GAP)), "| new sprites:", len(new))
print("still need art (%d):" % len(gaps), " ".join(gaps))
print("names still Imperial-flavoured:", left)
