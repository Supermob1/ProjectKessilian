"""Division templates for the Republic and the Separatists, built from the faction techs and units.

    python "WIPGFX/plans & scripts/faction_templates.py"

Run from the mod root, after faction_armour.py. Three kinds of templates:
  START   in the countries' OOBs (history/units), using only units their starting techs unlock
  UNLOCK  handed out when a tech is researched (on_research_complete load_oob, like vanilla's marines / tanks)
  AI      common/ai_templates/HOD_faction_templates.txt, so the AI designs and upgrades the same divisions
A template has regiments (columns of one unit group, at most five battalions), divisional support companies (support,
at most five) and regimental support companies (regimental_support: one per regiment column, x = that column).
"""
import os, re

CIS_BLOC = ("CIS", "TDF", "TCU", "CMG", "IBC")
I, D, B2 = "infantry", "infantry_droid", "heavy_droid"
# support techs both factions start with (all from 976 or earlier): the support companies and the regimental batteries
START_SUPPORT_TECHS = ["tech_support", "support_weapons", "tech_engineers", "tech_recon", "tech_signal_company", "tech_logistics_company",
                       "tech_maintenance_company", "tech_field_hospital", "tech_military_police",
                       "gw_artillery", "interwar_antiair", "interwar_antitank"]


def T(group, columns, support=(), regimental=(), extra=()):
    """columns: [(unit, count), ...] per column; regimental: [(unit, column), ...]"""
    regs = []
    for x, col in enumerate(columns):
        y = 0
        for unit, n in col:
            for _ in range(n):
                regs.append(f"\t\t{unit} = {{ x = {x} y = {y} }}")
                y += 1
    return dict(group=group, regs=regs, support=list(support), regimental=list(regimental), extra=list(extra),
                columns=columns)


CLONE_SUPPORT = ["engineer", "recon", "signal_company", "logistics_company", "field_hospital"]
WALKER_SUPPORT = ["walkers_light_recon", "engineer", "maintenance_company", "logistics_company", "signal_company"]
DROID_SUPPORT = ["engineer", "recon", "signal_company", "logistics_company", "maintenance_company"]

# 976: the clones are not deployed yet. The Republic fields its old army: Republic troopers (SWTOR-era armour) and
# Lance walkers. The clone templates come with the techs (UNLOCK: phase_I_equipment, arc_commandos, ...)
OLD_TROOPER = "override_model = REP_old_trooper_entity"
ARMY_SUPPORT = ["engineer", "recon", "signal_company", "logistics_company", "field_hospital"]
START_REP = {
    "Local Planetary Garrison": T("REP_GAR_01", [[(I, 2)]], ["military_police"], extra=["is_locked = yes", OLD_TROOPER]),
    "Republic Army Division": T("REP_ARMY_01", [[(I, 3)], [(I, 3)], [(I, 3)]], ARMY_SUPPORT,
                                [("fire_support", 0), ("anti_tank_battery", 1), ("anti_air_battery", 2)], [OLD_TROOPER]),
    "Republic Artillery Division": T("REP_ARMY_01", [[(I, 3)], [(I, 3)]], ARMY_SUPPORT,
                                     [("field_guns", 0), ("field_guns", 1)], [OLD_TROOPER]),
    "Lance Walker Company": T("REP_WLK_01", [[(I, 3)], [(I, 3)], [("walkers_light", 2)]], WALKER_SUPPORT,
                              [("fire_support", 0), ("anti_tank_battery", 1)], [OLD_TROOPER]),
}
# clone-era templates an older OOB may still carry
REMOVED_REP = ["Clone Legion", "Clone Commando", "Clone Artillery Legion", "AT-PT Walker Company"]
CLONE_LEGION = T("REP_Inf_01", [[(I, 3)], [(I, 3)], [(I, 3)]], CLONE_SUPPORT,
                 [("fire_support", 0), ("anti_tank_battery", 1), ("anti_air_battery", 2)], ["override_model = REP_infantry_entity"])
# Felucian tribes (felucia_tribes.py): light infantry warbands that live off the jungle
START_FLT = {
    "Felucian Warband": T("FLT_INF_01", [[(I, 3)], [(I, 3)]], ["recon"]),
    "Karst Ambushers": T("FLT_INF_01", [[(I, 2)], [(I, 2)]], ["recon", "engineer"]),
}
# Alderaan: a small royal army for a pacifist world
START_ALD = {
    "Alderaanian Planetary Guard": T("ALD_GAR_01", [[(I, 2)]], ["military_police"], extra=["is_locked = yes", OLD_TROOPER]),
    "Alderaanian Royal Army": T("ALD_INF_01", [[(I, 3)], [(I, 3)]], ["engineer", "recon", "signal_company", "field_hospital"],
                                [("fire_support", 0), ("anti_air_battery", 1)], [OLD_TROOPER]),
}
# Thyferra (the user, 2026-10-23): the Vratix hive guard and the two bacta corporations' security droids
THY_START = {
    "THY": {"Vratix Hive Guard": T("THY_INF_01", [[(I, 3)], [(I, 3)]], ["recon", "engineer"])},
    "UTA": {"Utapaun Guard": T("UTA_INF_01", [[(I, 3)], [(I, 3)]], ["recon", "engineer"])},
    "XUC": {"Xucphra Security Force": T("XUC_SEC_01", [[(D, 3)], [(D, 3)]], ["military_police", "recon"])},
    "ZAL": {"Zaltin Security Force": T("ZAL_SEC_01", [[(D, 3)], [(D, 3)]], ["military_police", "recon"])},
}
START_CIS = {
    "Local Planetary Garrison": T("CIS_GAR_01", [[(D, 2)]], ["military_police"], extra=["is_locked = yes"]),
    "CIS Droid Battalion": T("CIS_INF_01", [[(D, 3)], [(D, 3)], [(D, 3)], [(B2, 3)], [(D, 1)]], DROID_SUPPORT,
                             [("fire_support", 0), ("fire_support", 1), ("anti_tank_battery", 2), ("anti_air_battery", 3)]),
    "CIS Droid Commando": T("CIS_INF_01", [[("commando_droid", 3)], [("commando_droid", 3)]], ["engineer", "recon", "signal_company"],
                            [("fire_support", 0)]),
    "AAT Armoured Division": T("CIS_ARM_01", [[("medium_armor", 2)], [("medium_armor", 2)], [(D, 3)], [(D, 3)]], DROID_SUPPORT,
                               [("light_sp_anti_air_support", 0), ("light_sp_anti_air_support", 1), ("anti_tank_battery", 2)]),
    "Octuptarra Strike Group": T("CIS_ARM_01", [[("light_armor", 3)], [(D, 3)]], ["engineer", "recon", "maintenance_company"],
                                 [("light_sp_anti_air_support", 0), ("fire_support", 1)]),
    "Hailfire Artillery Group": T("CIS_INF_01", [[(D, 3)], [(D, 3)], [("light_sp_artillery_brigade", 2)]], DROID_SUPPORT,
                                  [("anti_air_battery", 0), ("anti_tank_battery", 1)]),
}
# tech -> (oob file, name, template, unit that marks "already has one"); only units unlocked by then (the tech's own and
# the starting / earlier ones)
UNLOCK = {
    # the first clones: no unit of their own, so no "already has one" check
    "phase_I_equipment": ("HOD_unlock_clone_legion", "Clone Legion", CLONE_LEGION, None),
    "rep_walker_atte": ("HOD_unlock_atte", "AT-TE Assault Division",
                        T("REP_MEC_01", [[("walkers_medium", 3)], [(I, 3)], [(I, 3)]], WALKER_SUPPORT,
                          [("anti_tank_battery", 0), ("fire_support", 1), ("anti_air_battery", 2)]), "walkers_medium"),
    "rep_walker_atap": ("HOD_unlock_atap", "AT-AP Siege Group",
                        T("REP_MEC_01", [[("walkers_heavy", 2)], [("walkers_medium", 2)], [(I, 3)], [(I, 3)]], WALKER_SUPPORT,
                          [("field_guns", 2), ("fire_support", 3)]), "walkers_heavy"),
    "rep_walker_ataa": ("HOD_unlock_walker_escort", "Walker Escort Battalion",
                        T("REP_MEC_01", [[(I, 3)], [(I, 3)], [("walkers_light", 3)]], WALKER_SUPPORT,
                          [("fire_support", 0), ("walkers_light_support_destroyer", 1), ("walkers_light_support_aa", 2)]),
                        "walkers_light_support_aa"),
    "rep_spg_spham": ("HOD_unlock_spha", "SPHA Artillery Legion",
                      T("REP_Inf_01", [[(I, 3)], [(I, 3)], [("walkers_medium_artillery", 2)]], CLONE_SUPPORT,
                        [("fire_support", 0), ("anti_air_battery", 1)]), "walkers_medium_artillery"),
    "rep_tx130": ("HOD_unlock_tx130", "Clone Armoured Legion",
                  T("REP_Inf_01", [[(I, 3)], [(I, 3)], [(I, 3)]],
                    ["repulsor_tank_company", "engineer", "recon", "logistics_company", "field_hospital"],
                    [("fire_support", 0), ("anti_tank_battery", 1), ("anti_air_battery", 2)]), "repulsor_tank_company"),
    "rep_walker_atat_kuat": ("HOD_unlock_atat", "AT-AT Assault Division",
                             T("REP_MEC_01", [[("walkers_modern", 3)], [("walkers_medium", 2)], [(I, 3)], [(I, 3)]], WALKER_SUPPORT,
                               [("anti_air_battery", 1), ("fire_support", 2), ("anti_tank_battery", 3)]), "walkers_modern"),
    "laat_infantry": ("HOD_unlock_laat", "Clone Air Cavalry Legion",
                      T("REP_PAR_01", [[(I, 3)], [(I, 3)]], ["helicopter_brigade", "engineer", "recon", "signal_company", "field_hospital"],
                        [("fire_support", 0), ("anti_tank_battery", 1)]), "helicopter_brigade"),
    "arc_commandos": ("HOD_unlock_arc", "ARC Trooper Company",
                      T("REP_Inf_01", [[("arc_trooper", 3)], [("arc_trooper", 3)]], ["engineer", "recon", "signal_company"],
                        [("fire_support", 0)], ["override_model = REP_marine_entity"]), "arc_trooper"),
    "cis_haat": ("HOD_unlock_haat", "Heavy Armoured Division",
                 T("CIS_ARM_01", [[("heavy_armor", 2)], [("medium_armor", 2)], [(D, 3)], [(B2, 3)]], DROID_SUPPORT,
                   [("light_sp_anti_air_support", 0), ("light_sp_anti_air_support", 1), ("anti_tank_battery", 2), ("fire_support", 3)]),
                 "heavy_armor"),
    "cis_hailfire_heavy": ("HOD_unlock_heavy_hailfire", "Heavy Hailfire Group",
                           T("CIS_INF_01", [[(B2, 3)], [(D, 3)], [("medium_sp_artillery_brigade", 2)]], DROID_SUPPORT,
                             [("fire_support", 0), ("anti_air_battery", 1)]), "medium_sp_artillery_brigade"),
    "cis_og9": ("HOD_unlock_og9", "OG-9 Siege Group",
                T("CIS_INF_01", [[(D, 3)], [(B2, 3)], [("motorized_rocket_brigade", 2)]], DROID_SUPPORT,
                  [("fire_support", 0), ("anti_tank_battery", 1)]), "motorized_rocket_brigade"),
    "cis_hag": ("HOD_unlock_hag", "Gun Tank Hunter Group",
                T("CIS_ARM_01", [[("medium_armor", 3)], [(D, 3)], [(D, 3)]], DROID_SUPPORT,
                  [("medium_tank_destroyer_support", 0), ("light_sp_anti_air_support", 1), ("fire_support", 2)]),
                "medium_tank_destroyer_support"),
    "hkb3_commando_droid": ("HOD_unlock_droid_commandos", "BX Commando Squad",
                            T("CIS_INF_01", [[("commando_droid", 3)], [("commando_droid", 3)]], ["engineer", "recon", "signal_company"],
                              [("fire_support", 0)]), "commando_droid"),
    "droideka_early": ("HOD_unlock_droidekas", "Droideka Assault Group",
                       T("CIS_INF_01", [[(D, 3)], [(D, 3)], [("droideka_droid", 3)]], DROID_SUPPORT,
                         [("fire_support", 0), ("anti_tank_battery", 1)]), "droideka_droid"),
    "early_magnaguard": ("HOD_unlock_magnaguards", "MagnaGuard Honour Guard",
                         T("CIS_INF_01", [[("magnaguard_droid", 2)], [("magnaguard_droid", 2)]], ["engineer", "recon", "signal_company"]),
                         "magnaguard_droid"),
    "early_spider_droid": ("HOD_unlock_spider_droids", "Spider Droid Battalion",
                           T("CIS_INF_01", [[(D, 3)], [(D, 3)], [("spider_droid", 3)]], DROID_SUPPORT,
                             [("anti_tank_battery", 0), ("fire_support", 1)]), "spider_droid"),
}
# the armour tabs' hooks are written by faction_armour.py (it regenerates those files); the rest are hooked here
TECH_FILES = ("common/technologies/republic_military.txt", "common/technologies/cis_droid_military.txt")


def template_text(name, t):
    lines = [f'division_template = {{\n\tname = "{name}"\n\tdivision_names_group = {t["group"]}']
    lines += [f"\t{e}" for e in t["extra"]]
    lines.append("\tregiments = {\n" + "\n".join(t["regs"]) + "\n\t}")
    if t["regimental"]:
        lines.append("\tregimental_support = {\n" + "\n".join(f"\t\t{u} = {{ x = {x} y = 0 }}" for u, x in t["regimental"]) + "\n\t}")
    if t["support"]:
        lines.append("\tsupport = {\n" + "\n".join(f"\t\t{u} = {{ x = 0 y = {i} }}" for i, u in enumerate(t["support"])) + "\n\t}")
    return "\n".join(lines) + "\n}"


def rw(path, fn):
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    crlf = "\r\n" in s
    s = fn(s.replace("\r\n", "\n"))
    c = re.sub(r"#[^\n]*", "", s)
    assert c.count("{") == c.count("}"), path
    open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + (s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))


def block_span(s, start):
    i, d = s.index("{", start) + 1, 1
    while d:
        d += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    return i


def write_start(path, templates, removed=()):
    """replace each named template in the OOB (or add it before the units / instant effects); drop the removed ones"""
    def fn(s):
        for name in removed:
            m = re.search(r'division_template\s*=\s*\{\s*name\s*=\s*"%s"' % re.escape(name), s)
            if m:
                s = s[:m.start()].rstrip("\n") + "\n" + s[block_span(s, m.start()):].lstrip("\n")
        for name, t in templates.items():
            new = template_text(name, t)
            m = re.search(r'division_template\s*=\s*\{\s*name\s*=\s*"%s"' % re.escape(name), s)
            if m:
                s = s[:m.start()] + new + s[block_span(s, m.start()):]
            else:
                anchor = re.search(r"\n(units\s*=|instant_effect\s*=)", s)
                at = anchor.start() if anchor else len(s)
                s = s[:at].rstrip("\n") + "\n\n" + new + "\n" + s[at:]
        return s
    rw(path, fn)


def write_start_techs():
    import glob
    for tag in ("REP",) + CIS_BLOC:
        p = glob.glob(f"history/countries/{tag} - *.txt")[0]
        def fn(s):
            m = re.search(r"\nset_technology\s*=\s*\{([^{}]*)\}", s)
            have = set(re.findall(r"(\w+)\s*=\s*1", m.group(1)))
            add = "".join(f"\t{t} = 1\n" for t in START_SUPPORT_TECHS if t not in have)
            return s[:m.end(1)].rstrip("\n\t ") + "\n" + add + s[m.end(1):].lstrip("\n") if add else s
        rw(p, fn)


def write_unlocks():
    for tech, (oob, name, t, unit) in UNLOCK.items():
        open(f"history/units/{oob}.txt", "w", encoding="utf-8-sig", newline="\n").write(
            f"# HOD: template handed out by {tech} (faction_templates.py)\n" + template_text(name, t) + "\n")
        hook = (f"\t\t# HOD: free {name} template (faction_templates.py)\n"
                + (f"\t\ton_research_complete_limit = {{ NOT = {{ has_template_containing_unit = {unit} }} }}\n" if unit else "") +
                f"\t\ton_research_complete = {{\n\t\t\thidden_effect = {{ load_oob = \"{oob}\" }}\n"
                f"\t\t\tcustom_effect_tooltip = UNLOCK_DIVISION_TEMPLATE\n\t\t}}\n")
        for path in TECH_FILES:
            s = open(path, encoding="utf-8-sig").read()
            if not re.search(r"^\t%s\s*=\s*\{" % tech, s, re.M):
                continue
            def fn(s, tech=tech, hook=hook, unit=unit):
                m = re.search(r"^\t%s\s*=\s*\{[^\n]*\n" % tech, s, re.M)
                end = block_span(s, m.start())
                body = s[m.end():end]
                if "on_research_complete" in body:          # already hooked (earlier run / hand-written unlock)
                    return s
                extra = "\t\tenable_subunits = { helicopter_brigade }\n" if unit == "helicopter_brigade" and "helicopter_brigade" not in body else ""
                return s[:m.end()] + extra + hook + s[m.end():]
            rw(path, fn)


def names_group(key, title, tags, fallback, names):
    suffix = lambda i: "st" if i % 10 == 1 and i != 11 else "nd" if i % 10 == 2 and i != 12 else "rd" if i % 10 == 3 and i != 13 else "th"
    return (f"\n{key} = {{\n\tname = \"{title}\"\n\n\tfor_countries = {{ {' '.join(tags)} }}\n\n\tcan_use = {{ always = yes }}\n\n"
            f"\tdivision_types = {{ \"infantry\" }}\n\n\tfallback_name = \"{fallback}\"\n\n\tordered = {{\n"
            + "".join(f"\t\t{i} = {{ \"{i}{suffix(i)} {n}\" }}\n" for i, n in enumerate(names, 1)) + "\t}\n}\n")


OLD_REP_NAMES = {
    "REP_ARMY_01": ("Republic Army Divisions", "%dth Republic Army Division",
                    ["Coruscant Security Division", "Coruscant Guard Division", "Senate District Division", "Byss Defence Division",
                     "Chandrila Division", "Tython Division", "Core Worlds Division", "Abregado Division", "Duros Division",
                     "Commenor Division", "Loronar Division", "Arkanian Division", "Byss Artillery Division", "Coruscant Artillery Division"]),
    "REP_WLK_01": ("Republic Lance Walker Companies", "%dth Lance Walker Company",
                   ["Coruscant Lance Walker Company", "Senate Lance Walker Company", "Byss Lance Walker Company", "Chandrila Lance Walker Company"]),
}
FLT_NAMES = {
    "FLT_INF_01": ("Felucian Warbands", "%dth Warband", ["Nui Da Voi Warband", "Ancient Abyss Rancor Riders", "Ban Nam Stalkers",
                                                          "Rung Tham Hunters", "Suong Mu Shadow Band", "Thach Lam Warband"]),
}
THY_NAMES = {
    "THY": {"THY_INF_01": ("Vratix Hive Guard", "%dth Hive Guard", ["Xozhixi Hive Guard", "Vrelnid Hive Guard"])},
    "UTA": {"UTA_INF_01": ("Utapaun Guard", "%dth Utapaun Guard", ["Pau City Guard", "Dactillion Riders"])},
    "XUC": {"XUC_SEC_01": ("Xucphra Security", "%dth Xucphra Security Force", ["Xucphra City Security", "Bacta Vats Security"])},
    "ZAL": {"ZAL_SEC_01": ("Zaltin Security", "%dth Zaltin Security Force", ["Zalxuc Docks Security"])},
}
ALD_NAMES = {
    "ALD_GAR_01": ("Alderaanian Planetary Guard", "%dth Planetary Guard", ["Aldera Guard", "Apalis Coast Guard", "Castle Lands Guard"]),
    "ALD_INF_01": ("Royal Alderaanian Army", "%dth Royal Regiment", ["House Organa Regiment", "House Antilles Regiment"]),
}


def write_names():
    p = "common/units/names_divisions/REP_names_divisions.txt"
    add = "".join(names_group(k, t, ("REP",), f, n) for k, (t, f, n) in OLD_REP_NAMES.items() if f"\n{k} = {{" not in open(p, encoding="utf-8-sig").read())
    if add:
        rw(p, lambda s: s.rstrip("\n") + "\n" + add)
    open("common/units/names_divisions/FLT_names_divisions.txt", "w", encoding="utf-8-sig", newline="\n").write(
        "# HOD: Felucian tribes (faction_templates.py)\n" + "".join(names_group(k, t, ("FLT",), f, n) for k, (t, f, n) in FLT_NAMES.items()))
    open("common/units/names_divisions/ALD_names_divisions.txt", "w", encoding="utf-8-sig", newline="\n").write(
        "# HOD: Alderaan (faction_templates.py)\n" + "".join(names_group(k, t, ("ALD",), f, n) for k, (t, f, n) in ALD_NAMES.items()))
    for tag, groups in THY_NAMES.items():
        open(f"common/units/names_divisions/{tag}_names_divisions.txt", "w", encoding="utf-8-sig", newline="\n").write(
            "# HOD: Thyferra (faction_templates.py)\n" + "".join(names_group(k, t, (tag,), f, n) for k, (t, f, n) in groups.items()))
    p = "common/units/names_divisions/CIS_names_divisions.txt"
    s = open(p, encoding="utf-8-sig").read()
    if "CIS_ARM_01" in s:
        return
    names = ["Trade Federation Armoured Column", "Techno Union Assault Group", "Baktoid Armour Division", "Hypori Tank Group",
             "Geonosis Armoured Division", "Commerce Guild Armour Corps", "Mygeeto Armoured Division", "Felucia Tank Group"]
    block = ("\nCIS_ARM_01 = {\n\tname = \"Droid Armour Divisions\"\n\n\tfor_countries = { " + " ".join(CIS_BLOC) + " }\n\n"
             "\tcan_use = { always = yes }\n\n\tdivision_types = { \"armor\" }\n\n\tfallback_name = \"%dth Droid Armour Division\"\n\n"
             "\tordered = {\n" + "".join(f"\t\t{i} = {{ \"{i}{'st' if i == 1 else 'nd' if i == 2 else 'rd' if i == 3 else 'th'} {n}\" }}\n"
                                       for i, n in enumerate(names, 1)) + "\t}\n}\n")
    rw(p, lambda s: s.rstrip("\n") + "\n" + block)


# ── starting armies (976): divisions on the big worlds, and the walker / tank designs they are built from ──
GAR, BAT = "Local Planetary Garrison", "CIS Droid Battalion"
# tag -> (oob file, {planet (strategic region): [(template, divisions)]}); one division per state of the planet,
# biggest state first, going round again when there are more divisions than states
ARMIES = {
    "REP": ("history/units/HOD_REP.txt", {
        "Coruscant": [(GAR, 6), ("Republic Army Division", 3), ("Republic Artillery Division", 1), ("Lance Walker Company", 2)],
        "Byss": [(GAR, 1), ("Republic Army Division", 2), ("Lance Walker Company", 1)],
        "Chandrila": [(GAR, 1), ("Republic Army Division", 1), ("Lance Walker Company", 1)],
        "Tython": [(GAR, 1), ("Republic Army Division", 1)],
        "Abregado-Rae": [(GAR, 1), ("Republic Army Division", 1)],
        "Duro": [(GAR, 1), ("Republic Army Division", 1)],
        "Commenor": [(GAR, 1), ("Republic Army Division", 1)],
        "Loronar": [(GAR, 1), ("Republic Army Division", 1)],
        "Arkania": [(GAR, 1), ("Republic Army Division", 1)]}),
    "FLT": ("history/units/HOD_FLT.txt", {
        "Felucia": [("Felucian Warband", 4), ("Karst Ambushers", 2)]}),
    "ALD": ("history/units/HOD_ALD.txt", {
        "Alderaan": [("Alderaanian Planetary Guard", 3), ("Alderaanian Royal Army", 2)]}),
    "CIS": ("history/units/HOD_CIS.txt", {
        "Raxus": [(GAR, 1), (BAT, 2), ("AAT Armoured Division", 1)],
        "Serenno": [(BAT, 1), ("Octuptarra Strike Group", 1)],
        "Geonosis": [(BAT, 1)]}),
    "THY": ("history/units/HOD_THY.txt", {"Thyferria": [("Vratix Hive Guard", 2)]}),
    "UTA": ("history/units/HOD_UTA.txt", {"Utapau": [("Utapaun Guard", 2)]}),
    "XUC": ("history/units/HOD_XUC.txt", {"Thyferria": [("Xucphra Security Force", 2)]}),
    "ZAL": ("history/units/HOD_ZAL.txt", {"Thyferria": [("Zaltin Security Force", 1)]}),
    "TDF": ("history/units/HOD_TDF.txt", {
        "Cato Neimoidia": [(GAR, 1), (BAT, 2), ("AAT Armoured Division", 1)], "Neimodia": [(BAT, 1)], "Colla IV": [(BAT, 1)]}),
    "TCU": ("history/units/HOD_TCU.txt", {
        "Foerost": [(BAT, 1), ("Octuptarra Strike Group", 1)], "Balmorra": [(BAT, 1)], "Mechis": [(BAT, 1)],
                 "Boz Pity": [(BAT, 1)]}),   # Boz Pity is TCU's (its map script)
    "CMG": ("history/units/HOD_CMG.txt", {"Felucia": [(BAT, 1)], "Sullust": [(BAT, 1)], "Dromund Kaas": [(BAT, 1)]}),
    "IBC": ("history/units/HOD_IBC.txt", {"Muunilinst": [(GAR, 1), (BAT, 1)], "Mygeeto": [(BAT, 1)], "Kalee": [(BAT, 1)]}),
}


def variant(name, type_, modules, model=None):
    mods = "".join(f"\t\t\t{slot} = {m}\n" for slot, m in modules.items())
    return (f"\tcreate_equipment_variant = {{\n\t\tname = \"{name}\"\n\t\ttype = {type_}\n\t\tparent_version = 0\n"
            f"\t\tmodules = {{\n{mods}\t\t}}\n\t\tupgrades = {{ tank_nsb_engine_upgrade = 1 tank_nsb_armor_upgrade = 1 }}\n"
            + (f"\t\tmodel = {model}\n" if model else "") + "\t}\n")


WALKER = dict(turret_type_slot="tank_light_two_man_tank_turret", main_armament_slot="tank_small_cannon",
              armor_type_slot="tank_riveted_armor", engine_type_slot="tank_gasoline_engine", special_type_slot_1="walker_pneumatic_damper")
LIGHT = dict(turret_type_slot="tank_light_one_man_tank_turret", main_armament_slot="tank_heavy_machine_gun",
             suspension_type_slot="tank_christie_suspension", armor_type_slot="tank_riveted_armor", engine_type_slot="tank_gasoline_engine")
# a design without a model falls back to a vanilla tank: name the droid tank entities (unit_models.py CIS_MAP)
def droid_designs(tag):
    return [variant("AAT", "medium_tank_chassis_1", dict(LIGHT, turret_type_slot="tank_medium_two_man_tank_turret",
                                                         main_armament_slot="tank_small_cannon", suspension_type_slot="tank_bogie_suspension"),
                    f"{tag}_medium_armor_entity"),
            variant("Octuptarra Tri-Droid", "light_tank_chassis_1", LIGHT, f"{tag}_light_armor_entity"),
            variant("Octuptarra AA Tri-Droid", "light_tank_aa_chassis_1", dict(LIGHT, main_armament_slot="tank_anti_air_cannon"),
                    f"{tag}_light_armor_entity")]
DESIGNS = {
    "REP": [variant("Lance Walker", "walker_chassis_0", WALKER, "hod_lance_walker_entity"),
            variant("Lance Walker Scout", "walker_chassis_0", dict(WALKER, turret_type_slot="tank_light_one_man_tank_turret",
                                                                   main_armament_slot="tank_heavy_machine_gun"), "hod_lance_walker_entity")],
    **{t: droid_designs(t) for t in CIS_BLOC},
}


def planets():
    """strategic region name -> [(state id, owner, manpower, victory point or first province)], biggest first"""
    import glob
    rname = dict(re.findall(r'^\s*STRATEGICREGION_(\d+):\d*\s*"([^"]*)"', open(
        "localisation/english/strategic_region_names_l_english.yml", encoding="utf-8-sig").read(), re.M))
    prov_region = {}
    for f in glob.glob("map/strategicregions/*.txt"):
        s = open(f, encoding="utf-8-sig", errors="replace").read()
        p = re.search(r"provinces\s*=\s*\{([^}]*)\}", s)
        for prov in (p.group(1).split() if p else []):
            prov_region[int(prov)] = rname.get(re.search(r"\bid\s*=\s*(\d+)", s).group(1))
    out = {}
    for f in glob.glob("history/states/*.txt"):
        s = re.sub(r"#[^\n]*", "", open(f, encoding="utf-8-sig", errors="replace").read())
        provs = [int(p) for p in re.search(r"provinces\s*=\s*\{([^}]*)\}", s).group(1).split()]
        vps = [(int(v), int(p)) for p, v in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)", s) if int(p) in provs]
        where = max(vps)[1] if vps else provs[0]
        owner = re.search(r"owner\s*=\s*(\w+)", s).group(1)
        if re.search(r"impassable\s*=\s*yes", s):          # no units can stand there
            continue
        out.setdefault(prov_region.get(provs[0]), []).append(
            (int(re.search(r"\bid\s*=\s*(\d+)", s).group(1)), owner, int(re.search(r"manpower\s*=\s*(\d+)", s).group(1)), where))
    return {k: sorted(v, key=lambda x: -x[2]) for k, v in out.items()}


def write_armies():
    worlds = planets()
    for tag, (path, plan) in ARMIES.items():
        divs = []
        for planet, groups in plan.items():
            states = [st for st in worlds.get(planet, []) if st[1] == tag]
            assert states, f"{tag}: owns no state on {planet}"
            i = 0
            for template, n in groups:
                for _ in range(n):
                    divs.append((template, states[i % len(states)][3]))
                    i += 1
        units = "units = {\n" + "".join(
            f"\tdivision = {{\n\t\tdivision_template = \"{t}\"\n\t\tlocation = {loc}\n\t\tstart_experience_factor = 0.2\n\t}}\n"
            for t, loc in divs) + "}"
        def fn(s):
            for name in {t for t, _ in divs}:
                assert f'name = "{name}"' in s, f"{path}: no template {name}"
            m = re.search(r"\nunits\s*=\s*\{", s)
            if m:
                return s[:m.start() + 1] + units + s[block_span(s, m.start() + 1):]
            anchor = re.search(r"\ninstant_effect\s*=", s)
            at = anchor.start() if anchor else len(s)
            return s[:at].rstrip("\n") + "\n\n" + units + "\n" + s[at:]
        rw(path, fn)


def write_designs():
    import glob
    for tag, designs in DESIGNS.items():
        block = ("# HOD: starting walker / tank designs (faction_templates.py)\nif = {\n\tlimit = { has_dlc = \"No Step Back\" }\n"
                 + "".join(designs) + "}\n# HOD: end of starting designs\n")
        def fn(s):
            s = re.sub(r"# HOD: starting walker / tank designs.*?# HOD: end of starting designs\n", "", s, flags=re.S)
            return s.rstrip("\n") + "\n\n" + block
        rw(glob.glob(f"history/countries/{tag} - *.txt")[0], fn)


# ── AI: the same divisions as AI targets ──
def ai_entry(key, t, req):
    count = {}
    for col in t["columns"]:
        for unit, n in col:
            count[unit] = count.get(unit, 0) + n
    regi = {}
    for u, _x in t["regimental"]:
        regi[u] = regi.get(u, 0) + 1
    return (f"\t{key} = {{\n\t\tupgrade_prio = {{ base = 1 }}" +
            (f"\n\t\tcan_upgrade_in_field = {{ has_tech = {req} }}" if req else "") +
            "\n\t\ttarget_template = {\n\t\t\tsupport = {\n" + "".join(f"\t\t\t\t{u} = 1\n" for u in t["support"]) + "\t\t\t}\n" +
            ("\t\t\tregimental_support = {\n" + "".join(f"\t\t\t\t{u} = {n}\n" for u, n in regi.items()) + "\t\t\t}\n" if regi else "") +
            "\t\t\tregiments = {\n" + "".join(f"\t\t\t\t{u} = {n}\n" for u, n in count.items()) + "\t\t\t}\n\t\t}\n\t\ttarget_min_match = 0.6\n\t}")


def ai_role(key, tags, role, entries, prio):
    return "\n".join([f"{key} = {{", "\tavailable_for = { " + " ".join(tags) + " }", f"\trole = {role}",
                      f"\tupgrade_prio = {{ base = {prio} }}"] + [ai_entry(k, t, req) for k, (t, req) in entries.items()] + ["}"])


def write_ai():
    rep, U = ("REP",), {k: v[2] for k, v in UNLOCK.items()}
    blocks = [
        ai_role("hod_rep_infantry", rep, "infantry", {"hod_rep_army_division": (START_REP["Republic Army Division"], None),
                                                      "hod_rep_clone_legion": (U["phase_I_equipment"], "phase_I_equipment"),
                                                      "hod_rep_clone_armoured_legion": (U["rep_tx130"], "rep_tx130"),
                                                      "hod_rep_air_cavalry": (U["laat_infantry"], "laat_infantry")}, 3),
        ai_role("hod_rep_walkers", rep, "armor", {"hod_rep_lance_company": (START_REP["Lance Walker Company"], None),
                                                  "hod_rep_atte_division": (U["rep_walker_atte"], "rep_walker_atte"),
                                                  "hod_rep_atat_division": (U["rep_walker_atat_kuat"], "rep_walker_atat_kuat")}, 2),
        ai_role("hod_rep_garrison", rep, "garrison", {"hod_rep_garrison": (START_REP["Local Planetary Garrison"], None)}, 1),
        ai_role("hod_cis_infantry", CIS_BLOC, "infantry", {"hod_cis_droid_battalion": (START_CIS["CIS Droid Battalion"], None)}, 3),
        ai_role("hod_cis_armour", CIS_BLOC, "armor", {"hod_cis_aat_division": (START_CIS["AAT Armoured Division"], None),
                                                      "hod_cis_heavy_division": (U["cis_haat"], "cis_haat")}, 3),
        ai_role("hod_cis_garrison", CIS_BLOC, "garrison", {"hod_cis_garrison": (START_CIS["Local Planetary Garrison"], None)}, 1),
    ]
    open("common/ai_templates/HOD_faction_templates.txt", "w", encoding="utf-8", newline="\n").write(
        "# HOD: AI division templates for the Republic and the Separatists (faction_templates.py)\n\n" + "\n\n".join(blocks) + "\n")
    # the generic vanilla roles would have them design tank / motorised divisions they cannot build
    def fn(s):
        tags = ("REP",) + CIS_BLOC
        for role_key in re.findall(r"^(\w+)\s*=\s*\{\s*\n(?:\s*#[^\n]*\n)*\s*(?:blocked_for\s*=\s*\{[^}]*\}[^\n]*\n\s*)?role\s*=\s*(?:armor|infantry|garrison)\b", s, re.M):
            m = re.search(r"^%s\s*=\s*\{" % role_key, s, re.M)
            end = block_span(s, m.start())
            body = s[m.end():end]
            b = re.search(r"blocked_for\s*=\s*\{([^}]*)\}", body)
            if b:
                add = [t for t in tags if t not in set(b.group(1).split())]
                if add:
                    body = body[:b.end(1)] + " " + " ".join(add) + " " + body[b.end(1):]
            else:
                body = "\n\tblocked_for = { " + " ".join(tags) + " }   # HOD: faction templates in HOD_faction_templates.txt" + body
            s = s[:m.end()] + body + s[end:]
        return s
    rw("common/ai_templates/generic.txt", fn)


if __name__ == "__main__":
    write_names()
    write_start_techs()
    write_start("history/units/HOD_REP.txt", START_REP, REMOVED_REP)
    write_start("history/units/HOD_CIS.txt", START_CIS)
    for tag in CIS_BLOC[1:]:
        write_start(f"history/units/HOD_{tag}.txt", {k: v for k, v in START_CIS.items() if k != "CIS Droid Commando"})
    for tag, start in (("FLT", START_FLT),):
        if not os.path.exists(f"history/units/HOD_{tag}.txt"):
            open(f"history/units/HOD_{tag}.txt", "w", encoding="utf-8-sig", newline="\n").write(f"# HOD: {tag} (faction_templates.py)\n")
        write_start(f"history/units/HOD_{tag}.txt", start)
    if not os.path.exists("history/units/HOD_ALD.txt"):
        open("history/units/HOD_ALD.txt", "w", encoding="utf-8-sig", newline="\n").write("# HOD: Alderaan (faction_templates.py)\n")
    write_start("history/units/HOD_ALD.txt", START_ALD)
    for tag, start in THY_START.items():
        if not os.path.exists(f"history/units/HOD_{tag}.txt"):
            open(f"history/units/HOD_{tag}.txt", "w", encoding="utf-8-sig", newline="\n").write(f"# HOD: {tag} (faction_templates.py)\n")
        write_start(f"history/units/HOD_{tag}.txt", start)
    write_armies()
    write_designs()
    write_unlocks()
    write_ai()
    print("templates written")
