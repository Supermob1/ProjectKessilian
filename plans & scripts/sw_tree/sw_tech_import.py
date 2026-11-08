"""Import the SW Executor Revived (workshop 3734223606) tech tree as the only army/air/naval tree.
Our old folders are hidden (techs stay defined so history/AI/ideas keep parsing).
Industry + electronics go back to vanilla (years -960); rocket techs stay disabled as before.
Run: python -I sw_tech_import.py   (undo = git checkout/clean of the touched paths)"""
import os, re, shutil, sys, glob

W = r"F:\SteamLibrary\steamapps\workshop\content\394360\3734223606"
M = r"F:\Documents\Paradox Interactive\Hearts of Iron IV\mod\ProjectKessilian"
V = r"F:\SteamLibrary\steamapps\common\Hearts of Iron IV"
SHIFT = 960
sys.path.insert(0, os.path.join(M, "plans & scripts"))
import history_inject as HI


def rd(p):
    return open(p, encoding="utf-8-sig", errors="replace").read().replace("\r\n", "\n")


def wr(p, t, bom=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\n").write(t)


def shift_years(t):
    t = re.sub(r"(start_year\s*=\s*)(19\d\d)", lambda m: m.group(1) + str(int(m.group(2)) - SHIFT), t)
    return re.sub(r'(date\s*[<>=]+\s*"?)(19\d\d)', lambda m: m.group(1) + str(int(m.group(2)) - SHIFT), t)


def cheaper(t):  # house rule: military build_cost_ic x0.25
    return re.sub(r"(build_cost_ic\s*=\s*)([\d.]+)", lambda m: m.group(1) + ("%g" % round(float(m.group(2)) * 0.25, 3)), t)


def top_names(t, depth):
    t = re.sub(r"#[^\n]*", "", t)
    out, d = [], 0
    for m in re.finditer(r"([A-Za-z0-9_\-\.]+)\s*=\s*\{|\{|\}", t):
        if m.group(0) == "}":
            d -= 1
            continue
        if d == depth and m.group(1):
            out.append(m.group(1))
        d += 1
    return out


ids = set()

# 1. techs
for f in glob.glob(os.path.join(W, "common", "technologies", "*.txt")):
    t = shift_years(rd(f))
    ids.update(top_names(t, 1))
    wr(os.path.join(M, "common", "technologies", "hod_sw_" + os.path.basename(f)), t)

# 2. their folders/categories, ungated (everyone uses this tree); loads before 00_technology => default tab
t = rd(os.path.join(W, "common", "technology_tags", "empire_tech_tags.txt"))
t = re.sub(r"has_country_flag = star_wars_tech_flag\s*NOT = \{ ?has_country_flag = tech_toggle_imp ?\}", "always = yes", t)
assert "star_wars_tech_flag" not in t
ids.update(re.findall(r"\n\t(sw\w+_folder|imperial_folder) = \{", t))
ids.update(re.findall(r"\n\t(imperial_\w+|cl_tech)\n", t))
wr(os.path.join(M, "common", "technology_tags", "00_hod_sw_tech_tags.txt"), t)

# 3. our folders: hide every old army/air/naval tab, electronics back
p = os.path.join(M, "common", "technology_tags", "00_technology.txt")
t = rd(p)
i = t.index("technology_folders = {")
hide = ["droid_folder", "republic_folder", "hod_rep_armour_folder", "hod_cis_armour_folder", "infantry_folder",
        "support_folder", "armour_folder", "nsb_armour_folder", "artillery_folder", "air_techs_folder",
        "bba_air_techs_folder", "naval_folder", "mtgnavalfolder", "mtgnavalsupportfolder"]
ledger = {"air_techs_folder": "air", "bba_air_techs_folder": "air", "naval_folder": "navy", "mtgnavalfolder": "navy",
          "mtgnavalsupportfolder": "navy"}
blk = "technology_folders = {\n\t# HOD: army/air/naval research = SW tree (00_hod_sw_tech_tags.txt); old tabs hidden, techs kept for history/AI\n"
blk += "".join(f"\t{f} = {{\n\t\tavailable = {{ always = no }}\n\t\tledger = {ledger.get(f, 'army')}\n\t}}\n" for f in hide)
blk += """\tindustry_folder = {
		ledger = civilian
	}
	electronics_folder = {
		ledger = civilian
	}
	land_doctrine_folder = {
		ledger = army
		doctrine = yes
	}
	naval_doctrine_folder = {
		ledger = navy
		doctrine = yes
	}
	air_doctrine_folder = {
		ledger = air
		doctrine = yes
	}
	special_forces_doctrine_folder = {
		available = {
			has_dlc = "Arms Against Tyranny"
		}
		ledger = hidden #For now
		doctrine = yes
	}
}
"""
wr(p, t[:i] + blk, bom=open(p, "rb").read(3) == b"\xef\xbb\xbf")

# 4. vanilla industry + electronics, years shifted, our disabled techs stay disabled
for name in ("industry.txt", "electronic_mechanical_engineering.txt"):
    ours = os.path.join(M, "common", "technologies", name)
    off = re.findall(r"\n\t(\w+) = \{\n\t\tallow = \{ always = no \}", rd(ours))
    t = shift_years(rd(os.path.join(V, "common", "technologies", name)))
    for tech in off:
        t, n = re.subn(r"(\n\t%s = \{\n)" % tech, r"\1\t\tallow = { always = no }\t# HOD: disabled\n", t)
        assert n == 1, tech
    wr(ours, t)
    print(name, "disabled kept:", off)

# 5. units / equipment / unit tags (skip their vanilla-artillery override)
for sub in ("units", "units/equipment", "units/equipment/modules", "units/names", "unit_tags"):
    for f in glob.glob(os.path.join(W, "common", sub, "*.txt")):
        b = os.path.basename(f)
        if b == "zz_imp_artillery_support_fix.txt":
            continue
        t = rd(f)
        if sub.startswith("units/equipment"):
            t = cheaper(t)
        if sub in ("units", "units/equipment"):
            ids.update(top_names(t, 1))
        wr(os.path.join(M, "common", sub, "hod_sw_" + b.replace(" ", "_")), t)

# 6. gfx: copy what they have and we don't (never overwrite ours)
copied = 0
for sub in ("entities", "models", "particles", "interface/technologies", "interface/techtree", "interface/counters",
            "interface/equipmentdesigner", "texticons"):
    for root, _, files in os.walk(os.path.join(W, "gfx", sub)):
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(M, os.path.relpath(s, W))
            if not os.path.exists(d):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
                copied += 1
for f in ("empire_gfx.gfx", "imperial_naval.gfx", "imperial_ship_module_icons.gfx", "imp_texticons.gfx"):
    shutil.copy2(os.path.join(W, "interface", f), os.path.join(M, "interface", "hod_sw_" + f))
os.makedirs(os.path.join(M, "interface", "equipmentdesigner", "ships"), exist_ok=True)
for f in glob.glob(os.path.join(W, "interface", "equipmentdesigner", "ships", "*.gui")):
    shutil.copy2(f, os.path.join(M, "interface", "equipmentdesigner", "ships", os.path.basename(f)))
# sprites in their countrytechtreeview.gfx that vanilla lacks -> own file (don't override vanilla's 1.19 file)
van = set(re.findall(r'name\s*=\s*"(GFX_\w+)"', rd(os.path.join(V, "interface", "countrytechtreeview.gfx"))))
theirs = rd(os.path.join(W, "interface", "countrytechtreeview.gfx"))
blocks = re.findall(r"\n\t(?:spriteType|frameAnimatedSpriteType|corneredTileSpriteType) = \{.*?\n\t\}", theirs, re.S)
new = [b for b in blocks if re.search(r'name\s*=\s*"(GFX_\w+)"', b).group(1) not in van]
wr(os.path.join(M, "interface", "hod_sw_techtree.gfx"), "spriteTypes = {" + "".join(new) + "\n}\n")
# every texture those gfx files point at that exists in theirs but not ours
for g in glob.glob(os.path.join(M, "interface", "hod_sw_*.gfx")):
    for tex in re.findall(r'texturefile\s*=\s*"([^"]+)"', rd(g), re.I):
        tex = re.sub(r"/+", "/", tex)
        s, d = os.path.join(W, tex), os.path.join(M, tex)
        if os.path.exists(s) and not os.path.exists(d):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            copied += 1
print("gfx files copied:", copied, "| extra techtree sprites:", len(new))

# 7. tech screen GUI = theirs, year labels on our calendar
t = rd(os.path.join(W, "interface", "countrytechtreeview.gui"))
t = re.sub(r'(text = ")(19\d\d)(")', lambda m: m.group(1) + str(int(m.group(2)) - SHIFT) + m.group(3), t)
wr(os.path.join(M, "interface", "countrytechtreeview.gui"), t)

# 8. localisation for everything imported (not their state/VP/country text)
keys = {}
for f in glob.glob(os.path.join(W, "localisation", "**", "*.yml"), recursive=True):
    for line in rd(f).split("\n"):
        m = re.match(r"\s*([\w\-\.]+):\d*\s*\"", line)
        if m:
            k = m.group(1)
            base = re.sub(r"(_desc|_short|_name|_medium|_small)$", "", k)
            if k in ids or base in ids:
                keys[k] = line.strip()
wr(os.path.join(M, "localisation", "english", "hod_sw_tech_l_english.yml"),
   "l_english:\n" + "".join(f" {v}\n" for v in keys.values()), bom=True)
print("loc keys:", len(keys))

# 9. every country starts with the tree's root 976 techs (history, not on_actions)
alltech = "".join(rd(f) for f in glob.glob(os.path.join(M, "common", "technologies", "hod_sw_*.txt")))
led_to = set(re.findall(r"leads_to_tech\s*=\s*(\w+)", alltech))
roots = []
for f in glob.glob(os.path.join(M, "common", "technologies", "hod_sw_*.txt")):
    t = rd(f)
    names = top_names(t, 1)
    for n in names:
        b = re.search(r"\n\t%s = \{(.*?)\n\t\}" % re.escape(n), t, re.S)
        if b and "folder" in b.group(1) and "start_year = 976" in b.group(1) and n not in led_to \
                and "always = no" not in b.group(1):
            roots.append(n)
print("start techs:", roots)
line = "set_technology = { " + " ".join(f"{r} = 1" for r in roots) + " popup = no }"
for p in glob.glob(os.path.join(M, "history", "countries", "*.txt")):
    tag = os.path.basename(p).split(" - ")[0]
    HI.set_country(tag, "sw_tree", [line])
