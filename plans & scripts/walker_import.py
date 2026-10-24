"""Bring the "Walkers Special Project plus" workshop mod (3770877230) into HoD as part of the armour tech tree.

    python "WIPGFX/plans & scripts/walker_import.py"

Run from the mod root. Copies its walker chassis, units, modules, unit categories, doctrine, AI and graphics, and
rewires everything that waited on its special projects or its hidden unlock techs to the armour-tree techs that now
hand out walker chassis (NSB_armor.txt). Not copied: the special projects, the monthly unlock sync (on_actions /
scripted effects), the hidden unlock techs, land-cruiser shell decisions, MIOs, the vanilla-country AI templates and
its override of vanilla's tank chassis (zz_tank_chassis_autoloader.txt).
"""
import os, re, shutil

W = "F:/SteamLibrary/steamapps/workshop/content/394360/3770877230"

COPY = [
    "common/units/walkers.txt",
    "common/units/equipment/walkers_chassis.txt",
    "common/units/equipment/x_walkers_chassis.txt",
    "common/units/equipment/modules/00_walker_modules.txt",
    "common/unit_tags/walker_categories.txt",
    "common/doctrines/subdoctrines/land/walker_doctrine.txt",
    "common/ai_equipment/generic_walker.txt",
    "common/ai_strategy/walker_ai_strategy.txt",
    "localisation/english/walkers_l_english.yml",
    "localisation/english/walker_doctrine_l_english.yml",
]
COPY_TREES = ["gfx", "interface"]   # models, entities, icons, designer GUIs: all new file names

# special project / hidden-tech conditions -> the Republic Armour Corps tech that gives the same thing
# (walkers are the Republic's: hod_rep_armour.txt, faction_armour.py); the mod's own checks for vanilla tank techs
# ("does this country have tanks yet") map the same way, since walker countries never research those
LIGHT, LIGHT2, LIGHT3 = "rep_walker_atpt", "rep_walker_atrt", "rep_walker_atrt_501"
MED, MED2, MED3 = "rep_walker_atte", "rep_walker_atte_elite", "rep_walker_atte_sieges"
HEAVY, HEAVY2, HEAVY3 = "rep_walker_atap", "rep_walker_atot", "rep_walker_utat"
MODERN, SUPER = "rep_walker_atat_kuat", "rep_walker_atat_elite"
TECH = {
    "walker_unlock_light_early": LIGHT, "walker_unlock_sponson_early": LIGHT,
    "walker_unlock_light_improved": LIGHT2, "walker_unlock_sponson_improved": LIGHT2,
    "walker_unlock_light_advanced": LIGHT3, "walker_unlock_sponson_advanced": LIGHT3,
    "walker_unlock_medium_basic": MED, "walker_unlock_medium_improved": MED2, "walker_unlock_medium_advanced": MED3,
    "walker_unlock_heavy_basic": HEAVY, "walker_unlock_heavy_improved": HEAVY2, "walker_unlock_heavy_advanced": HEAVY3,
    "walker_unlock_modern": MODERN, "walker_unlock_super_heavy": SUPER,
    "walker_unlock_land_cruiser": SUPER, "walker_lc_800mm_unlock": SUPER,
    "gwtank_chassis": LIGHT, "basic_light_tank_chassis": LIGHT, "basic_light_tank": LIGHT,
    "improved_light_tank_chassis": LIGHT2, "improved_light_tank": LIGHT2,
    "advanced_light_tank_chassis": LIGHT3, "advanced_light_tank": LIGHT3,
    "basic_medium_tank_chassis": MED, "basic_medium_tank": MED, "improved_medium_tank_chassis": MED2,
    "improved_medium_tank": MED2, "advanced_medium_tank_chassis": MED3, "advanced_medium_tank": MED3,
    "basic_heavy_tank_chassis": HEAVY, "basic_heavy_tank": HEAVY, "improved_heavy_tank_chassis": HEAVY2,
    "improved_heavy_tank": HEAVY2, "advanced_heavy_tank_chassis": HEAVY3, "advanced_heavy_tank": HEAVY3,
    "main_battle_tank_chassis": MODERN, "main_battle_tank": MODERN, "super_heavy_tank_chassis": SUPER, "super_heavy_tank": SUPER,
}
CONDITIONS = [
    (r"has_country_flag\s*=\s*sp_land_walkers_completed", f"has_tech = {LIGHT}"),
    (r"has_country_flag\s*=\s*sp_walker_modules_completed", f"has_tech = {MED}"),
    (r"is_special_project_completed\s*=\s*sp:sp_land_land_cruiser", f"has_tech = {SUPER}"),
    (r"is_special_project_completed\s*=\s*sp:sp_walker_modules", f"has_tech = {MED}"),
    (r"is_special_project_completed\s*=\s*sp:sp_land_walkers", f"has_tech = {LIGHT}"),
]


def rewire(text):
    for pat, rep in CONDITIONS:
        text = re.sub(pat, rep, text)
    return re.sub(r"\b(%s)\b" % "|".join(TECH), lambda m: TECH[m.group(1)], text)


def main():
    for rel in COPY:
        os.makedirs(os.path.dirname(rel), exist_ok=True)
        raw = open(f"{W}/{rel}", "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig") if rel.endswith(".yml") else rewire(raw.decode("utf-8-sig"))   # loc keys stay as they are
        open(rel, "wb").write((b"\xef\xbb\xbf" if bom or rel.endswith(".yml") else b"") + text.encode("utf-8"))
    n = 0
    for tree in COPY_TREES:
        for root, _d, files in os.walk(f"{W}/{tree}"):
            for f in files:
                src = os.path.join(root, f)
                rel = os.path.relpath(src, W).replace("\\", "/")
                if "special_project" in rel:
                    continue
                if os.path.exists(rel):            # already copied on an earlier run
                    continue
                os.makedirs(os.path.dirname(rel), exist_ok=True)
                shutil.copy2(src, rel)
                n += 1
    # the doctrine is no longer gated by the special project: any country with walkers can pick it
    print(f"copied {len(COPY)} script files (rewired) and {n} graphics/interface files")


if __name__ == "__main__":
    main()
