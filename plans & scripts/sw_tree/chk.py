import re, glob, os
M = r"F:\Documents\Paradox Interactive\Hearts of Iron IV\mod\ProjectKessilian"
V = r"F:\SteamLibrary\steamapps\common\Hearts of Iron IV"
rd = lambda p: open(p, encoding="utf-8-sig", errors="replace").read()


def g(pat):
    return [f for b in (V, M) for f in glob.glob(os.path.join(b, pat), recursive=True)]


def names(files, depth=1):
    out = set()
    for f in files:
        t = re.sub(r"#[^\n]*", "", rd(f)); d = 0
        for m in re.finditer(r"([\w\-\.]+)\s*=\s*\{|\{|\}", t):
            if m.group(0) == "}":
                d -= 1; continue
            if d == depth and m.group(1):
                out.add(m.group(1))
            d += 1
    return out


sprites = set()
for f in g("interface/*.gfx") + g("interface/*/*.gfx"):
    sprites |= set(re.findall(r'name\s*=\s*"?(GFX_[\w\-]+)', rd(f), re.I))
gui = rd(os.path.join(M, "interface/countrytechtreeview.gui"))
print("missing GUI sprites:", sorted(set(re.findall(r"(GFX_[\w\-]+)", gui)) - sprites))
eq = names(g("common/units/equipment/*.txt")); su = names(g("common/units/*.txt")); te = names(g("common/technologies/*.txt"))
swf = glob.glob(os.path.join(M, "common/technologies/hod_sw_*.txt"))
sw = "".join(rd(f) for f in swf)
blk = lambda key, t: re.findall(key + r"\s*=\s*\{([^}]*)\}", t)
print("missing equipment:", sorted({x for b in blk("enable_equipments", sw) for x in b.split()} - eq))
print("missing subunits:", sorted({x for b in blk("enable_subunits", sw) for x in b.split()} - su))
print("missing leads_to:", sorted(set(re.findall(r"leads_to_tech\s*=\s*([\w\-]+)", sw)) - te))
icons = [t for t in names(swf) if "GFX_%s_medium" % t not in sprites]
print("techs w/o icon:", len(icons), icons[:20])
units = "".join(rd(f) for f in glob.glob(os.path.join(M, "common/units/hod_sw_*.txt")))
print("unit needs missing equipment:", sorted({x for b in blk("need", units) for x in re.findall(r"([\w\-]+)\s*=", b)} - eq))
tags = "".join(rd(f) for f in g("common/unit_tags/*.txt"))
print("missing unit categories:", sorted(set(re.findall(r"\b(category_\w+)", units)) - set(re.findall(r"\b(category_\w+)", tags))))
folders = set(re.findall(r"name\s*=\s*(\w+_folder)", sw))
print("folders without GUI:", sorted(f for f in folders if 'name = "%s"' % f not in gui))
