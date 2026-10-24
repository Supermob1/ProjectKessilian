"""Point every reference to the old (vanilla-based) technologies at the generated HoD tree (techtree_gen.py).

    python tech_remap.py          dry run: writes tech_remap.txt (old -> new) and lists the files it would touch
    python tech_remap.py apply    rewrites the files, adds the legacy tech, deletes the old tech files

Run from the mod root. Mapping: same category, closest era at or below the old tech's era (vanilla year -> era),
else the same tab's first tech of that era. History files also get the new tech's ancestors and era techs, so
a country's tree has no holes, plus hod_legacy_military (old units/equipment for existing OOBs until the OOB phase).
"""
import os, re, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import techtree_gen as g

g.build()
OLD_FILES = ["MTG_naval.txt", "MTG_naval_Support.txt", "NSB_armor.txt", "air_techs.txt", "armor.txt", "artillery.txt",
             "bba_air_techs.txt", "electronic_mechanical_engineering.txt", "industry.txt", "infantry.txt", "naval.txt",
             "special_projects_tech.txt", "support.txt", "republic_military.txt", "cis_droid_military.txt"]
FOLDER_TAB = {"infantry_folder": "infantry", "support_folder": "support", "armour_folder": "vehicles", "nsb_armour_folder": "vehicles",
              "artillery_folder": "support", "air_techs_folder": "air", "bba_air_techs_folder": "air", "naval_folder": "fleet",
              "mtgnavalfolder": "fleet", "mtgnavalsupportfolder": "fleet", "electronics_folder": "engineering",
              "industry_folder": "industry", "republic_folder": "clone", "droid_folder": "droid"}
MANUAL = {"old_republic_equipment": "hod_blasters_1", "marines": "hod_assault_troopers", "paratroopers": "hod_jump_troopers",
          "tech_mountaineers": "hod_mountain_troopers", "rangers_tech": "hod_mountain_troopers"}
# old id pattern -> new line (first match wins); techs nothing matches fall back to category, then tab
KEYWORDS = [
    # self-propelled guns / tank destroyers / SPAA are chassis versions of their size
    (r"super_heavy_(art|td|spaa)", "hod_superheavy_chassis"), (r"heavy_(art|td|spaa)", "hod_heavy_chassis"),
    (r"medium_(art|td|spaa)|modern_(art|td)", "hod_medium_chassis"), (r"light_(art|td|spaa)", "hod_light_chassis"),
    (r"paratroop|dropship|airlift|transport_plane", "hod_jump_troopers"), (r"(?<!sub)marine|amphibious_mech|landing|special_forces", "hod_assault_troopers"),
    (r"mountain|ranger|arctic|jungle|desert", "hod_mountain_troopers"), (r"militia|camel|elephant|cavalry|bicycle", "hod_militia_doctrine"),
    (r"support_weapon|heavy_inf|machine_gun|mortar", "hod_heavy_blasters"), (r"night_vision|sniper|marksman", "hod_precision_blasters"),
    (r"infantry_weapons|infantry_arms|improved_infantry|advanced_infantry", "hod_blasters"), (r"armor_scheme|infantry_armou?r|body_armou?r", "hod_body_armour"),
    (r"engineer", "hod_engineering_corps"), (r"recon|scout", "hod_scouts"), (r"field_hospital|medic", "hod_medical_corps"),
    (r"logistics|supply|motorised|motorized|truck|railway|train", "hod_logistics_corps"), (r"maintenance", "hod_maintenance_corps"),
    (r"signal|radio(?!_detection)", "hod_signal_corps"), (r"military_police|police", "hod_police_corps"),
    (r"rocket_art|katyusha", "hod_missile_artillery_tech"), (r"antitank|anti_tank|tank_destroyer|_td\b", "hod_antiarmor_tech"),
    (r"antiair|anti_air|spaa|aa_|flak", "hod_flak_tech"), (r"artillery|_art\b|howitzer", "hod_artillery_tech"),
    (r"fort|bunker|maginot", "hod_fortification"),
    (r"armou?red_car|speeder|bike", "hod_speeders"), (r"super_heavy|superheavy|mega_tank|siege", "hod_superheavy_chassis"),
    (r"heavy_tank|heavy_armor|heavy_droids|main_battle", "hod_heavy_chassis"), (r"medium_tank|medium_armor", "hod_medium_chassis"),
    (r"light_tank|gwtank|tank|chassis|armor_tech|armour_tech", "hod_light_chassis"), (r"engine_tech", "hod_vehicle_engines"),
    (r"amphibious_tank|amphibious_drive|transmission|suspension", "hod_vehicle_drives"),
    (r"strategic_bomber|large_airframe|heavy_bomber", "hod_heavy_bomber_airframe_tech"), (r"cv_|carrier_fighter|naval_bomber|torpedo_bomber|air_torpedo", "hod_carrier_starfighter_airframe_tech"),
    (r"cas|tactical_bomber|medium_airframe|heavy_fighter|close_air", "hod_gunship_airframe_tech"),
    (r"jet|air_engine|aero_engine", "hod_air_engines"), (r"bomb|rocket_mount", "hod_air_ordnance"), (r"air_gun|cannon_mount", "hod_air_guns"),
    (r"fighter|small_airframe|airframe|aircraft|air_", "hod_starfighter_airframe_tech"),
    (r"submarine|stealth|snorkel", "hod_raider_hull_tech"), (r"torpedo", "hod_ship_torpedoes"), (r"carrier|hangar|deck", "hod_carrier_hull_tech"),
    (r"super_heavy_battleship|shbb|super_battleship", "hod_dreadnought_hull_tech"), (r"battleship|battlecruiser|heavy_cruiser|ship_hull_heavy|heavy_battery|capital", "hod_capital_hull_tech"),
    (r"cruiser|ship_hull_cruiser|medium_battery", "hod_cruiser_hull_tech"), (r"armor_scheme|damage_control|ship_armor", "hod_ship_defence"),
    (r"engine|propulsion|turbine|naval_engine", "hod_ship_drives"), (r"fire_control|sonar|radar_ship|smoke|mine|depth_charge|aa_ship", "hod_ship_systems"),
    (r"battery|naval_gun|gun", "hod_ship_weapons"), (r"destroyer|ship_hull_light|transport|coastal_defense|corvette|early_ship", "hod_corvette_hull_tech"),
    (r"decrypt", "hod_decryption"), (r"encrypt", "hod_encryption"), (r"radar|magnatron|phased_array|monopulse|detection", "hod_sensors"),
    (r"computing|computer|electronic|mechanical|calculat", "hod_computing"), (r"nuclear|atomic|reactor", "hod_superweapons"),
    (r"rocket|missile", "hod_missiles"), (r"penicillin|medicine|antibiotic", "hod_medicine"),
    (r"construction|excavation_?\d|excavat", "hod_construction"), (r"fuel|oil|synth", "hod_fuel"), (r"mining|resource", "hod_mining"),
    (r"concentrated_industry|centralised", "hod_centralised_industry"), (r"dispersed_industry", "hod_dispersed_industry"),
    (r"naval_dock|shipyard", "hod_shipyards"), (r"machine_tools|production|industry|assembly|tools", "hod_production"),
    (r"kamino|clone|phase_i|dropship_loadout", "hod_clone_armour"), (r"arc_", "hod_arc_troopers"), (r"commando", "hod_clone_commandos"),
    (r"b2|super_battle", "hod_b2_droids"), (r"bx|commando_droid", "hod_bx_droids"), (r"destroyer_droid|droideka", "hod_droidekas"),
    (r"magna", "hod_magnaguards"), (r"tactical_droid", "hod_tactical_droids"), (r"droid_production|foundr", "hod_droid_production"),
    (r"droid", "hod_b1_droids"),
]
GENERIC = {"hod_era", "hod_misc", "hod_access"}
LEGACY = "hod_legacy_military"
SKIP_DIRS = ("./WIPGFX", "./.git", "./gfx", "./map", "./music", "./sound", "./localisation", "./common/technologies")


def block_end(s, i):
    d = 1
    while d:
        d += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    return i


def old_techs():
    techs = {}
    for f in OLD_FILES:
        s = open("common/technologies/" + f, encoding="utf-8-sig", errors="ignore").read()
        for m in re.finditer(r"^\t(\w+)\s*=\s*\{", s, re.M):
            b = s[m.end():block_end(s, m.end())]
            year = re.search(r"start_year\s*=\s*(\d+)", b)
            folder = re.search(r"folder\s*=\s*\{\s*name\s*=\s*(\w+)", b)
            cats = re.search(r"categories\s*=\s*\{([^}]*)\}", b)
            unlock = lambda k: re.findall(r"\w+", " ".join(re.findall(k + r"\s*=\s*\{([^}]*)\}", b)))
            techs[m.group(1)] = dict(year=int(year.group(1)) if year else None, folder=folder.group(1) if folder else None,
                                     cats=set(cats.group(1).split()) if cats else set(), eq=unlock("enable_equipments"),
                                     units=unlock("enable_subunits"), modules=unlock("enable_equipment_modules"))
    return techs


def era_of(year):
    if year is None:
        return 0
    if year < 900:                                         # vanilla calendar
        return 0 if year <= 1936 else 1 if year <= 1938 else 2 if year <= 1941 else 3
    return next((e for e, (a, b) in enumerate(g.ERA_YEARS) if year <= b), 3)


def mapping(old):
    new = [t for t in g.TECHS.values() if not t["id"].startswith("era_")]
    by_cat = defaultdict(list)
    for t in new:
        for c in set(t["cats"]) - GENERIC:
            by_cat[c].append(t)
    best = lambda pool, era: (max([t for t in pool if t["era"] <= era] or [min(pool, key=lambda t: (t["era"], t["step"]))],
                                  key=lambda t: (t["era"], -t["row"], t["step"]))["id"] if pool else None)
    out = {}
    for tid, o in old.items():
        e = era_of(o["year"])
        if tid in MANUAL:
            out[tid] = MANUAL[tid]
            continue
        line = next((ln for rx, ln in KEYWORDS if re.search(rx, tid.lower())), None)
        pool = [t for t in new if re.sub(r"_\d+$", "", t["id"]) == line or t["id"] == line] if line else []
        if pool:
            out[tid] = best(pool, e)
            continue
        pool = [t for c in o["cats"] for t in by_cat.get(c, [])]
        tab = FOLDER_TAB.get(o["folder"])
        if tab and any(t["tab"] == tab for t in pool):    # prefer a category match inside the same tab
            pool = [t for t in pool if t["tab"] == tab]
        if not pool and tab:
            pool = [t for t in new if t["tab"] == tab and t["row"] > 0] or [t for t in new if t["tab"] == tab]
        out[tid] = best(pool, e) or "hod_blasters_1"
    return out


START_ERA = 1          # the 976 start: history never grants later eras


def with_ancestors(tid):
    """the tech (or its last ancestor of the start era), its parent chain and its tab's era techs up to its era"""
    while g.TECHS[tid]["era"] > START_ERA and g.TECHS[tid]["parent"]:
        tid = g.TECHS[tid]["parent"]
    t = g.TECHS[tid]
    got = [tid]
    p = t["parent"]
    while p:
        got.append(p)
        p = g.TECHS[p]["parent"]
    got += [f"era_{t['tab']}_{e}" for e in range(2, t["era"] + 2) if f"era_{t['tab']}_{e}" in g.TECHS]
    return got


def files():
    yield "./common/technologies/special_forces_doctrine.txt"
    for root, _d, fs in os.walk("."):
        root = root.replace("\\", "/")
        if root.startswith(SKIP_DIRS):
            continue
        for fn in fs:
            if fn.endswith((".txt", ".gui")):
                yield f"{root}/{fn}"


def rewrite_history(s, mp):
    def fix(m):
        body = m.group(1)
        ids = re.findall(r"(\w+)\s*=\s*1", body)
        keep, seen = [], set()
        for i in ids:
            for n in (with_ancestors(mp[i]) if i in mp else [i]):
                if n not in seen:
                    seen.add(n)
                    keep.append(n)
        if any(i in mp for i in ids):
            if LEGACY not in seen:
                keep.append(LEGACY)
            tabs = {g.TECHS[n]["tab"] for n in keep if n in g.TECHS}
            keep += [a for a, tab in (("access_kamino_cloning", "clone"), ("access_droid_foundries", "droid")) if tab in tabs and a not in seen]
        ind = re.search(r"\n([ \t]*)\w", body)
        ind = ind.group(1) if ind else "\t"
        return "set_technology = {" + "".join(f"\n{ind}{n} = 1" for n in keep) + "\n" + ind[:-1] + "}"
    return re.sub(r"set_technology\s*=\s*\{([^{}]*)\}", fix, s)


def retarget(s, mp, pat):
    """old ids only where they name a technology: equipment, units, buildings and roles share some of these names"""
    ids = pat.pattern[2:-2]
    s = re.sub(r"(\b(?:has_tech|TECH|EXTRA_TECH|technology|is_researching_technology|leads_to_tech)\s*=\s*)%s\b" % ids,
               lambda m: m.group(1) + mp[m.group(2)], s)
    s = re.sub(r"(tech_effect\|)%s\b" % ids, lambda m: m.group(1) + mp[m.group(2)], s)
    return re.sub(r"(set_technology\s*=\s*\{)([^{}]*)\}",
                  lambda b: b.group(1) + re.sub(r"\b%s(\s*=\s*1)" % ids, lambda m: mp[m.group(1)] + m.group(2), b.group(2)) + "}", s)


def legacy_tech(old):
    eq = sorted({x for o in old.values() for x in o["eq"]})
    un = sorted({x for o in old.values() for x in o["units"]})
    mo = sorted({x for o in old.values() for x in o["modules"]})
    j = lambda xs: "\n\t\t\t".join(" ".join(xs[i:i + 6]) for i in range(0, len(xs), 6))
    return f"""
	# the old units and equipment the existing OOB templates use, until the OOB phase replaces them (tech_remap.py)
	{LEGACY} = {{
		allow = {{ always = no }}
		enable_equipments = {{
			{j(eq)}
		}}
		enable_subunits = {{
			{j(un)}
		}}
		enable_equipment_modules = {{
			{j(mo)}
		}}
		research_cost = 1
		start_year = 964
		categories = {{ hod_access }}
	}}
"""


def main(apply):
    old = old_techs()
    mp = mapping(old)
    pat = re.compile(r"\b(%s)\b" % "|".join(sorted(mp, key=len, reverse=True)))
    with open("WIPGFX/plans & scripts/tech_remap.txt", "w", encoding="utf-8") as f:
        for k in sorted(mp):
            f.write(f"{k:45} {old[k]['year']}  {old[k]['folder']}  ->  {mp[k]}\n")
    touched = {}
    for p in files():
        raw = open(p, "rb").read()
        s = raw.decode("utf-8-sig", errors="ignore")
        if not pat.search(s):
            continue
        n = s
        if p.startswith("./history/"):
            n = rewrite_history(n, mp)
        n = retarget(n, mp, pat)
        if n != s:
            touched[p] = len(pat.findall(s))
            if apply:
                open(p, "wb").write((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + n.encode("utf-8"))
    for p, c in sorted(touched.items(), key=lambda x: -x[1]):
        print(c, p)
    print(f"{len(mp)} old techs mapped, {len(touched)} files", "rewritten" if apply else "would change")
    if apply:
        # its own file: techtree_gen.py rewrites hod_tech_access.txt
        # (the applied version was rebuilt by hand from git HEAD with comments stripped and names checked against the mod)
        open("common/technologies/hod_tech_legacy.txt", "w", encoding="utf-8", newline="\n").write("technologies = {" + legacy_tech(old) + "}\n")
        for f in OLD_FILES:
            os.remove("common/technologies/" + f)
        d = open("descriptor.mod", encoding="utf-8-sig").read()
        if 'replace_path="common/technologies"' not in d:
            open("descriptor.mod", "w", encoding="utf-8").write(d.rstrip("\n") + '\nreplace_path="common/technologies"\n')


def cap_history():
    """one-off for files already remapped before START_ERA existed"""
    late = {k for k, t in g.TECHS.items() if t["era"] > START_ERA}
    for p in files():
        if not p.startswith("./history/"):
            continue
        raw = open(p, "rb").read()
        s = raw.decode("utf-8-sig", errors="ignore")
        n = re.sub(r"\n[ \t]*(%s)\s*=\s*1\b" % "|".join(sorted(late, key=len, reverse=True)), "", s)
        if n != s:
            print("capped", p)
            open(p, "wb").write((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + n.encode("utf-8"))


if __name__ == "__main__":
    if sys.argv[1:] == ["cap"]:
        cap_history()
        sys.exit()
    main(len(sys.argv) > 1 and sys.argv[1] == "apply")
