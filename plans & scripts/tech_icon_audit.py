"""Which model each equipment tech's icon should show, per side, against the icon it shows now.

    python -B "plans & scripts/tech_icon_audit.py"            -> table on stdout + WIPGFX/tech_icon_audit.csv

Model = the one the unit carries in game (plans & scripts/sw_tree/unit_models_sw.py): land equipment -> archetype ->
sub-units whose first `need` is that archetype -> entity at the equipment's visual_level; planes -> PLANES.
Icon now = GFX_<TAG>_<tech>_medium (REP / CIS) else GFX_<tech>_medium, as the engine looks them up.
"""
import csv, glob, os, re, sys

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(MOD, "tools", "hoi4_country_editor"), os.path.join(MOD, "plans & scripts"), os.path.join(MOD, "plans & scripts", "sw_tree")]
from hoi4_country_editor import parse, get, get_all   # noqa: E402
import unit_models_sw as U                             # noqa: E402

SIDES = (("REP", U.REP, 0), ("CIS", U.CIS, 1), ("IND", U.IND, 0))   # IND = everyone else (independents): the generic sprites


def blocks(pattern):
    for p in sorted(glob.glob(os.path.join(MOD, pattern))):
        yield p, parse(open(p, encoding="utf-8-sig", errors="replace").read())


def tables():
    techs = {}                                              # tech -> [equipment]
    for _, top in blocks("common/technologies/*.txt"):
        for body in get_all(top, "technologies"):
            for name, t in body:
                if isinstance(t, list) and name and not name.startswith("@"):
                    eqs = [v for l in get_all(t, "enable_equipments") for _, v in l]
                    if eqs:
                        techs[name] = eqs
    equip = {}                                              # equipment -> (archetype, visual_level)
    for _, top in blocks("common/units/equipment/*.txt"):
        for body in get_all(top, "equipments"):
            for name, e in body:
                if isinstance(e, list):
                    equip[name] = (get(e, "archetype", name), get(e, "visual_level"))
    for n, (arch, vl) in list(equip.items()):               # visual_level inherits from the archetype
        if vl is None:
            equip[n] = (arch, equip.get(arch, (arch, None))[1])
    needs = {}                                              # archetype -> sub-units needing it first
    for _, top in blocks("common/units/*.txt"):
        for body in get_all(top, "sub_units"):
            for name, s in body:
                need = get(s, "need") if isinstance(s, list) else None
                if need:     # armoured transports carry the model on their `transport` equipment, not the first need
                    needs.setdefault(get(s, "transport") or need[0][0], []).append(name)
    sprites = {}
    for p in glob.glob(os.path.join(MOD, "interface", "*.gfx")):
        for m in re.finditer(r'name\s*=\s*"?(GFX_[\w-]+)"?\s+texturefile\s*=\s*"([^"]+)"', open(p, encoding="utf-8-sig", errors="replace").read()):
            sprites[m.group(1)] = m.group(2)
    return techs, equip, needs, sprites


def model(eq, equip, needs, table, side):
    if eq in U.PLANES:
        return U.PLANES[eq][side].replace("_entity", ""), "plane"
    arch, vl = equip.get(eq, (None, None))
    for unit in needs.get(arch, []):
        if unit in table:
            lv = table[unit]
            m = lv.get(int(vl) if vl is not None and int(vl) in lv else None)
            if m:
                return m[0].replace("_entity", ""), unit
    return None, None


def audit():
    techs, equip, needs, sprites = tables()
    for _, tech in WEAPONS:              # support-weapon techs enable no equipment
        techs.setdefault(tech, [])
    rows = []
    for tech, eqs in sorted(techs.items()):
        row = {"tech": tech, "equipment": " ".join(eqs)}
        for tag, table, side in SIDES:
            m, unit = next(((m, u) for m, u in (model(e, equip, needs, table, side) for e in eqs) if m), (None, None))
            spr = "GFX_%s_%s_medium" % (tag, tech)
            row[tag + "_model"], row[tag + "_unit"] = m or "", unit or ""
            row[tag + "_icon"] = sprites.get(spr) or sprites.get("GFX_%s_medium" % tech, "")
            row[tag + "_own"] = spr in sprites
        if row["REP_model"] or row["CIS_model"] or any(t == tech for _, t in WEAPONS):
            rows.append(row)
    return rows


WPN =os.path.join(os.path.dirname(MOD), "ProjectKessilianWIPGFX", "ProjectKessilianWIP", "3d", "_glb", "weapons")
# rifle techs show the rifle, not the trooper (REP: the guns weapon_models.py puts in the clones' hands per visual level)
WEAPONS = {("CIS", "republic_weapon1"): ("cis_e5", "cis_1st_weap_inf_rifle.glb"), ("CIS", "imperial_weapons"): ("cis_e5c", "cis_weap_inf_rifle.glb"),
           ("CIS", "imperial_weapons2"): ("cis_e5s", "cis_weap_inf_sniperrifle.glb"),
           ("CIS", "firstorder_weapons"): ("cis_e5mk2", "cis_1st_weap_inf_sniperrifle.glb"),
           ("CIS", "imperial_anti_tank"): ("cis_launcher", "cis_weap_inf_launcher.glb"),
           ("REP", "republic_weapon1"): ("rep_dc15a", "rep_weap_inf_rifle.glb"), ("REP", "imperial_weapons"): ("rep_dc15s", "../../../../../ProjectKessilian/gfx/models/weapons/DC15.mesh"),
           ("REP", "imperial_weapons2"): ("rep_dc15x", "rep_weap_inf_sniperrifle.glb"), ("REP", "firstorder_weapons"): ("rep_e11", "imp_weap_inf_rifle.glb")}
TURN = {"imp_fly_tiefighter": "@0,140", "x_raw_ginivex": "@30,45"}   # Fanblade: tilted so the hull shows next to the open fan   # icon name -> "@x,z" degrees for render() when the auto side view is wrong
# rigged .mesh files import in their bind pose (T-pose troopers, folded legs): render unit_models.py's posed source instead
FROM_SOURCE = {"hod_x_raw_arc", "hod_x_raw_commando", "hod_x_imp_shock", "hod_x_imp_commando", "hod_rev_atrt", "hod_tr_atrt",
               "hod_x_mow_scorpenek"}
TAGS = {"REP": U.REP_TAGS, "CIS": U.CIS_TAGS}
BLENDER = "F:/Blender Foundation/Blender 5.2/blender.exe"
OUT = "gfx/interface/technologies/hod_render"
GFX = {"REP": "interface/hod_sw_render_icons_rep.gfx", "CIS": "interface/hod_sw_render_icons_cis.gfx"}


def meshes():
    txt = "".join(open(p, encoding="utf-8-sig", errors="replace").read() for p in
                  glob.glob(os.path.join(MOD, "gfx/entities/*.asset")) + glob.glob(os.path.join(MOD, "gfx/entities/*.gfx")))
    ent = dict(re.findall(r'name\s*=\s*"(\w+_entity)"\s+pdxmesh\s*=\s*"(\w+)"', txt))
    mesh = dict(re.findall(r'name\s*=\s*"(\w+)"\s+file\s*=\s*"([^"]+\.mesh)"', txt))
    return lambda m: mesh.get(ent.get(m + "_entity"))


def plan(rows):
    """-> {icon: source model}, {side: [(sprite, icon)]}, {generic texture: icon}"""
    mesh_of, src, sprites, generic = meshes(), {}, {"REP": [], "CIS": []}, {}

    def source(side, r):
        if (side, r["tech"]) in WEAPONS:
            icon, glb = WEAPONS[side, r["tech"]]
            return icon, os.path.normpath(os.path.join(WPN, glb))
        m = r[side + "_model"]
        path = m.startswith("hod_") and mesh_of(m)
        if not path:
            return None, None
        if m in FROM_SOURCE:
            import unit_models
            return m[4:], os.path.normpath(os.path.join(MOD, unit_models.SPECS[m]["src"]))
        return m[4:], os.path.join(MOD, path)

    for r in rows:
        for side in ("REP", "CIS"):
            icon, path = source(side, r)
            if icon:
                src[icon] = path
                for tag in TAGS[side]:
                    sprites[side] += [("GFX_%s_%s_medium" % (tag, n), icon) for n in [r["tech"]] + r["equipment"].split()]
    clash = set()
    for r in rows:          # generic GFX_<tech>_medium file -> the independents' model, written over the old picture
        icon, path = source("IND", r)
        tex = r["IND_icon"]
        if not icon or not tex or not os.path.exists(os.path.join(MOD, tex)) or tex in {"%s/%s_medium.dds" % (OUT, i) for i in src}:
            continue
        if generic.get(tex, icon) != icon:
            clash.add(tex)
        src[icon], generic[tex] = path, icon
    for t in clash:          # one picture shared by techs with different models: keep the (restyled) picture
        print("  shared, kept:", t)
        generic.pop(t)
    return src, sprites, generic


def install(outdir, rows):
    import shutil
    src, sprites, generic = plan(rows)
    for icon in src:
        shutil.copy(os.path.join(outdir, icon + "_medium.dds"), os.path.join(MOD, OUT, icon + "_medium.dds"))
    backup = os.path.join(os.path.dirname(MOD), "ProjectKessilianWIPGFX", "icons_parked", "pre_restyle_2026-11-10")
    for tex, icon in generic.items():
        b = os.path.join(backup, tex)
        if not os.path.exists(b):
            os.makedirs(os.path.dirname(b), exist_ok=True)
            shutil.copy2(os.path.join(MOD, tex), b)
        shutil.copy(os.path.join(outdir, icon + "_medium.dds"), os.path.join(MOD, tex))
    print("generic pictures replaced:", len(generic))
    for side, lst in sprites.items():
        lines = ["# HOD 2026-11-10: %s tech / equipment icons rendered from the unit's own 3D model" % side,
                 "# generated by plans & scripts/tech_icon_audit.py (render + compose in tech_icon_render.py) - edit there", "spriteTypes = {"]
        lines += ['\tspriteType = { name = "%s" texturefile = "%s/%s_medium.dds" }' % (s, OUT, i) for s, i in dict(lst).items()]
        open(os.path.join(MOD, GFX[side]), "w", encoding="utf-8", newline="\n").write("\n".join(lines + ["}"]) + "\n")
    print("installed", len(src), "icons,", {k: len(dict(v)) for k, v in sprites.items()}, "sprites")


if __name__ == "__main__":
    rows = audit()
    if sys.argv[1:2] == ["render"]:         # render [OUTDIR] [icon ...]: Blender raws + compose, nothing installed
        import subprocess
        pick = sys.argv[3:]
        pairs = ["%s=%s%s" % (i, p, TURN.get(i, "")) for i, p in sorted(plan(rows)[0].items()) if not pick or i in pick]
        here = os.path.join(MOD, "plans & scripts", "tech_icon_render.py")
        subprocess.run([BLENDER, "-b", "--factory-startup", "--python", here, "--", sys.argv[2]] + pairs, check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, "-B", here, "compose", sys.argv[2]], check=True)
        sys.exit()
    if sys.argv[1:2] == ["install"]:
        install(sys.argv[2], rows)
        sys.exit()
    out = os.path.join(os.path.dirname(MOD), "ProjectKessilianWIPGFX", "tech_icon_audit.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        same = "SAME" if r["REP_icon"] == r["CIS_icon"] else ""
        print("%-28s REP %-26s %-45s | CIS %-26s %-45s %s" % (r["tech"], r["REP_model"], os.path.basename(r["REP_icon"]),
              r["CIS_model"], os.path.basename(r["CIS_icon"]), same))
    print(len(rows), "techs ->", out)
