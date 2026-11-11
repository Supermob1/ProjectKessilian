"""Starfleet tab (2026-11-10, approved mock-up https://claude.ai/artifact/TACj1CHnxTWGVqo7n5bkvc): fixed ships, no designer.

    python -B "plans & scripts/sw_tree/naval_tree.py"

Each tech unlocks one finished ship (no module slots = no ship designer). Fast-fleet meta: cheap ships, 15 dockyards per
line (defines_HOD.lua). Writes, all generator-owned (edit HERE):
  common/technologies/hod_sw_imperial_naval.txt        techs (+ assault-ship invasion bonuses)
  common/units/equipment/hod_sw_zz_imperial_naval_equipment.txt   archetypes + fixed ships
  common/units/hod_sw_imp_naval_subunits.txt           sub-units (stealth gone, assault ship added)
  common/dynamic_modifiers/hod_assault_fleet.txt       bonuses by assault ships in service (5 / 15 / 30)
  interface/hod_sw_render_icons_naval.gfx              tech + ship icons rendered from the ship models
  localisation: per-tag names (faction_names), generic names (hod_sw_tech_l_english), assault modifiers
  history: start fleets (history/units/HOD_*_naval.txt) and the dynamic modifiers (history_inject marker assault_fleet)
  interface/countrytechtreeview.gui: the swnaval_folder gridboxes + year labels
Then run tech_tag_names.py for the <TAG>_<tech> names.
"""
import os, re, sys

MOD = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(MOD, "plans & scripts"))
REP_TAGS, CIS_TAGS = ["REP", "ALD"], ["CIS", "CMG", "IBC", "TCU", "TDF", "XUC", "ZAL"]
ROW = {976: 0, 977: 2, 978: 4, 979: 6, 981: 8, 985: 10}        # year label rows of the other SW tabs (level0..level5)
ICON = "gfx/interface/technologies/hod_render/ship_%s_medium.dds"

# line: archetype, sub-unit, HOI4 role, column, vanilla sprite, tab header
LINES = {
    "dd": ("ship_hull_light_imp", "imp_destroyer", "screen_ship", 0, "destroyer", "Escorts"),
    "cl": ("ship_hull_cruiser_light_imp", "imp_light_cruiser", "screen_ship", 3, "light_cruiser", "Line Cruisers"),
    "ca": ("ship_hull_cruiser_heavy_imp", "imp_heavy_cruiser", "capital_ship", 6, "heavy_cruiser", "Star Destroyers"),
    "cv": ("ship_hull_carrier_imp", "imp_carrier", "carrier", 9, "carrier", "Carriers"),
    "as": ("ship_hull_assault_imp", "imp_assault_ship", "capital_ship", 12, "heavy_cruiser", "Assault Ships"),
    "bb": ("ship_hull_heavy_imp", "imp_battleship", "capital_ship", 15, "battleship", "Flagships"),
}
# stats: lg hg torp aa armor hp speed range surface_det visibility reliability cost manpower dominance carrier_size steel chromium
S = "lg_attack hg_attack torpedo_attack anti_air_attack armor_value max_strength naval_speed naval_range surface_detection " \
    "surface_visibility reliability build_cost_ic manpower naval_dominance_factor carrier_size steel chromium".split()
# (line, tier): year, parent techs, research cost, stats, generic name, REP (name, model, desc), CIS (name, model, desc)
SHIPS = [
    ("dd", 1, 976, [], 1.5, (6, 0, 28, 8, 10, 80, 36, 2600, 30, 9, .87, 420, 250, 30, 0, 3, 1), "Patrol Corvette",
     ("CR90 Corvette", "rv_corvette", "A fast Corellian corvette for escort and picket duty."),
     ("Diamond-class Cruiser", "sev_diamond_cis_refit", "Commerce Guild cruiser that escorted the Separatist fleets from Geonosis on.")),
    ("dd", 2, 978, ["dd_1"], 1.8, (9, 0, 44, 14, 22, 100, 38, 3300, 35, 9, .9, 480, 280, 36, 0, 3, 1), "Escort Frigate",
     ("Pelta-class Frigate", "rev_pelta", "Kuat escort frigate, the workhorse screen of Republic battle groups."),
     ("Wavecrest-class Frigate", "sev_wavecrest", "Givin-built frigate that screens the Separatist battle line.")),
    ("dd", 3, 981, ["dd_2"], 2.0, (12, 0, 62, 20, 38, 130, 40, 4000, 40, 10, .92, 540, 320, 44, 0, 4, 2), "Heavy Escort Frigate",
     ("Charger c70 Retrofit", "rev_light_frigate", "Consular hull rebuilt as a fast, heavily armed escort."),
     ("Separatist Patrol Frigate", "sev_patrol_frigate", "Droid-crewed frigate that patrols the Separatist hyperlanes.")),
    ("cl", 1, 976, [], 1.8, (14, 0, 0, 8, 90, 200, 32, 4500, 35, 18, .87, 900, 450, 75, 0, 4, 2), "Light Cruiser",
     ("Consular-class Cruiser", "fotr_consular_lac", "Republic diplomatic cruiser refitted with guns for the war."),
     ("Munificent-class Star Frigate", "fotr_munificent", "Banking Clan frigate, the most common ship in the Separatist navy.")),
    ("cl", 2, 978, ["cl_1"], 2.0, (20, 0, 0, 14, 140, 250, 33, 5400, 40, 18, .9, 1000, 500, 90, 0, 4, 2), "Line Cruiser",
     ("Arquitens-class Light Cruiser", "rev_lightcruiser", "Kuat light cruiser that fills the Republic battle line."),
     ("Recusant-class Light Destroyer", "fotr_recusant", "Commerce Guild destroyer, all guns and droid crew.")),
    ("cl", 3, 981, ["cl_2"], 2.2, (27, 0, 0, 20, 210, 320, 35, 6300, 45, 19, .92, 1100, 550, 110, 0, 5, 3), "Strike Cruiser",
     ("Centax-class Heavy Frigate", "rev_centax_frigate", "Heavy frigate that brings capital guns to the screen."),
     ("Captor-class Munitions Cruiser", "fotr_captor", "Trade Federation cruiser packed with missile launchers.")),
    ("ca", 1, 976, [], 2.0, (4, 14, 0, 10, 300, 380, 30, 5000, 40, 22, .87, 1800, 900, 100, 0, 5, 2), "Star Destroyer",
     ("Victory I-class Star Destroyer", "fotr_victory1", "Rendili Star Destroyer built to fight inside planetary atmospheres."),
     ("Providence-class Destroyer", "fotr_providence", "Quarren-built destroyer, the core of the Separatist battle fleets.")),
    ("ca", 2, 979, ["ca_1"], 2.2, (6, 22, 0, 16, 400, 470, 31, 5800, 45, 22, .9, 1950, 1000, 125, 0, 5, 3), "Heavy Star Destroyer",
     ("Victory II-class Star Destroyer", "fotr_victory2", "Victory refit with stronger engines and heavier turbolasers."),
     ("Providence-class Dreadnought", "fotr_provdread", "Providence hull with the hangars traded for heavy guns.")),
    ("ca", 3, 985, ["ca_2"], 2.4, (8, 32, 0, 22, 520, 580, 33, 6600, 50, 24, .92, 2100, 1100, 155, 0, 6, 4), "Battlecruiser",
     ("Imperial I-class Star Destroyer", "ev_stardestroyer_mki", "Kuat's successor to the Victory, the ship of the coming Empire."),
     ("Bulwark Mk I Battlecruiser", "sev_bulwark", "Techno Union battlecruiser that outguns any Republic cruiser.")),
    ("cv", 1, 977, ["ca_1"], 2.2, (6, 0, 0, 16, 200, 420, 30, 5000, 50, 30, .87, 1800, 1000, 180, 8, 5, 2), "Escort Carrier",
     ("Venator-class Star Destroyer", "fotr_venator", "Carrier and destroyer in one, the face of the Republic Navy."),
     ("Providence-class Carrier", "fotr_lucid_voice", "Providence hull with hangars for hundreds of droid fighters.")),
    ("cv", 2, 981, ["cv_1"], 2.5, (8, 0, 0, 24, 290, 520, 31, 6000, 55, 30, .9, 2000, 1100, 220, 12, 5, 3), "Fleet Carrier",
     ("Imperial-class Escort Carrier", "tr_escort_carrier", "Kuat carrier built on the Venator's lessons: one long open hangar for whole fighter wings."),
     ("Lucrehulk-class Droid Control Ship", "fotr_lucre_control", "Trade Federation control ship that runs a whole droid fleet.")),
    ("as", 1, 976, [], 2.0, (8, 8, 0, 12, 350, 480, 30, 5000, 35, 26, .87, 1500, 900, 110, 0, 5, 2), "Assault Transport",
     ("Acclamator I-class Assault Ship", "fotr_acclamator1", "The ship that carried the clone army to Geonosis."),
     ("Hardcell-class Transport", "fotr_hardcell", "Techno Union transport that lands droid armies straight onto a planet.")),
    ("as", 2, 979, ["as_1"], 2.5, (10, 12, 0, 18, 450, 560, 31, 6000, 40, 26, .9, 1650, 1000, 135, 0, 6, 3), "Heavy Assault Ship",
     ("Acclamator II-class Assault Ship", "rev_acclamator_assault_ship", "Acclamator refit with more guns to fight its own way in."),
     ("Lucrehulk Core Ship", "sev_supplyship", "The Lucrehulk's core sphere, which lands the droid army on the surface.")),
    ("bb", 1, 976, [], 2.5, (8, 40, 0, 20, 600, 800, 28, 6000, 45, 30, .87, 5000, 2000, 250, 0, 8, 4), "Dreadnaught Heavy Cruiser",
     ("Dreadnaught-class Heavy Cruiser", "fotr_dreadnaught", "Old Rendili heavy cruiser, still the backbone of sector fleets."),
     ("Lucrehulk-class Battleship", "fotr_lucre_bship", "Converted Trade Federation freighter bristling with turbolasers.")),
    ("bb", 2, 979, ["bb_1"], 2.8, (10, 55, 0, 28, 800, 1000, 29, 7000, 50, 30, .9, 5600, 2400, 310, 0, 9, 5), "Star Dreadnought",
     ("Mandator II-class Star Dreadnought", "fotr_mandator2", "Kuat star dreadnought, the largest warship of the Republic."),
     ("Subjugator-class Heavy Cruiser", "fotr_subjugator", "The Malevolence: a giant cruiser with ion cannons that blind whole fleets.")),
]
# hangars: HOI4 ships are carriers OR gun ships, so the fighter groups of non-carrier warships are folded into anti-air
# (escorts carry none; carriers launch real air wings - interceptors, fighters and bombers are all carrier-capable)
HANGAR_AA = {"cl": 6, "ca": 10, "as": 8, "bb": 8}
# assault-ship techs carry the invasion bonuses (folded in from the old transport techs of the removed systems tab)
ASSAULT = {1: "naval_invasion_capacity = 120\n\t\tnaval_invasion_prep_days = -35\n\t\tnaval_invasion_division_cap = 3\n\t\tnaval_invasion_plan_cap = 2\n\t\ttransport_capacity = -0.40",
           2: "naval_invasion_capacity = 60\n\t\tnaval_invasion_prep_days = -35\n\t\tnaval_invasion_division_cap = 6\n\t\tnaval_invasion_plan_cap = 4\n\t\tamphibious_invasion = 0.35"}
# bonuses by assault ships in service: (minimum ships, modifiers); all reached tiers stack
FLEET = [(5, {"naval_invasion_capacity": 20, "naval_invasion_prep_speed": 0.25, "amphibious_invasion": 0.15}),
         (15, {"naval_invasion_capacity": 40, "naval_invasion_prep_speed": 0.25, "amphibious_invasion": 0.2, "naval_invasion_penalty": -0.15}),
         (30, {"naval_invasion_capacity": 60, "naval_invasion_prep_speed": 0.5, "amphibious_invasion": 0.25, "naval_invasion_penalty": -0.15, "naval_invasion_division_cap": 4})]
# start fleets: legacy definition -> (sub-unit, equipment); stealth ships are gone
CARRIER_FLEETS = {"REP", "CIS"}       # start fleets with carriers (history/units/HOD_<TAG>_naval.txt), checked in fleets()
FLEETS = {"destroyer": "dd", "light_cruiser": "cl", "heavy_cruiser": "ca", "carrier": "cv", "battleship": "bb", "battle_cruiser": "bb"}


def eq(line, tier):
    return "%s_%d" % (LINES[line][0], tier)


def w(path, text, bom=False):
    open(os.path.join(MOD, path), "wb").write((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def techs():
    out = ["technologies = {", "# generated by plans & scripts/sw_tree/naval_tree.py - edit there", ""]
    kids = {}
    for line, tier, year, parents, *_ in SHIPS:
        for p in parents:
            kids.setdefault(p, []).append("%s_%d" % (line, tier))
    for line, tier, year, parents, cost, stats, *_ in SHIPS:
        tid = "%s_%d" % (line, tier)
        paths = "".join("\n\t\tpath = { leads_to_tech = imp_tech_%s research_cost_coeff = 1 }" % k for k in kids.get(tid, []))
        bonus = ("\n\t\t" + ASSAULT[tier]) if line == "as" else ""
        out.append("\timp_tech_%s = {\n\t\tenable_equipments = { %s }%s%s\n\t\tresearch_cost = %s\n\t\tstart_year = %d\n"
                   "\t\tfolder = { name = swnaval_folder position = { x = %d y = %d } }\n"
                   "\t\tcategories = { naval_equipment %s_tech imperial_tech imperial_naval_tech }\n\t\tai_will_do = { factor = 4 }\n\t}"
                   % (tid, eq(line, tier), bonus, paths, cost, year, LINES[line][3], ROW[year], line if line != "as" else "tp"))
    w("common/technologies/hod_sw_imperial_naval.txt", "\n".join(out) + "\n}\n")


def equipment():
    out = ["equipments = {", "# generated by plans & scripts/sw_tree/naval_tree.py - edit there",
           "# Fixed ships: no module_slots, so no ship designer; each tech unlocks one finished ship.", ""]
    for line, (arch, unit, role, col, sprite, head) in LINES.items():
        cat = "interface_category_screen_ships" if role == "screen_ship" else "interface_category_capital_ships"
        out.append("\t%s = {\n\t\tyear = 1936\n\t\tis_archetype = yes\n\t\tis_buildable = no\n\t\ttype = %s\n\t\tinterface_category = %s\n"
                   "\t\tpriority = %d\n\t\tsub_attack = 0\n\t\tsub_detection = 4\n\t\tfuel_consumption = 0\n\t\tnaval_weather_penalty_factor = 1\n\t}"
                   % (arch, role, cat, 2000 - 100 * col))
        for l2, tier, year, parents, cost, stats, *_ in SHIPS:
            if l2 != line:
                continue
            st = dict(zip(S, stats))
            st["anti_air_attack"] += HANGAR_AA.get(line, 0)
            body = ["abbreviation = \"%s%d\"" % (line, tier), "year = %d" % (1935 + tier), "archetype = %s" % arch,
                    "visual_level = %d" % (tier - 1), "priority = %d" % (2000 - 100 * col)]
            if tier > 1:
                body.append("parent = %s" % eq(line, tier - 1))
            for k in S[:15]:
                if k == "carrier_size" and not st[k]:
                    continue
                v = st[k]
                body.append("%s = %s" % (k, ("%g" % v) if isinstance(v, float) else v))
            body.append("resources = { steel = %d chromium = %d }" % (st["steel"], st["chromium"]))
            out.append("\t%s = {\n\t\t%s\n\t}" % (eq(line, tier), "\n\t\t".join(body)))
        out.append("")
    w("common/units/equipment/hod_sw_zz_imperial_naval_equipment.txt", "\n".join(out) + "}\n")


def subunits():
    org = {"dd": (35, .04), "cl": (40, .16), "ca": (40, .24), "cv": (40, .8), "as": (45, .3), "bb": (50, .56)}
    out = ["sub_units = {", "# generated by plans & scripts/sw_tree/naval_tree.py - edit there", ""]
    for line, (arch, unit, role, col, sprite, head) in LINES.items():
        crit = "destroyed_ammo_storage broken_propeller on_fire damaged_flight_deck" if role == "carrier" else \
            "rudder_jammed destroyed_ammo_storage broken_propeller on_fire"
        out.append("\t%s = {\n\t\tsprite = %s\n\t\tmap_icon_category = ship\n\t\tpriority = %d\n\t\tactive = yes\n\t\ttype = { %s }\n"
                   "\t\tneed = { %s = 1 }\n\t\tmax_organisation = %d\n\t\tsupply_consumption = %g\n\t\tcritical_parts = { %s }\n"
                   "\t\tcritical_part_damage_chance_mult = 1\n\t\thit_profile_mult = 1.0\n\t}"
                   % (unit, sprite, {"dd": 3, "cl": 5, "ca": 6, "cv": 10, "as": 7, "bb": 9}[line], role, arch, org[line][0], org[line][1], crit))
    w("common/units/hod_sw_imp_naval_subunits.txt", "\n".join(out) + "\n}\n")


def dynamic_modifiers():
    out = ["# generated by plans & scripts/sw_tree/naval_tree.py - edit there",
           "# assault ships in service -> invasion bonuses; added to every country in history (history_inject marker assault_fleet)"]
    for i, (n, mods) in enumerate(FLEET, 1):
        out.append("hod_assault_fleet_%d = {\n\tenable = { has_navy_size = { size > %d unit = imp_assault_ship } }\n\ticon = GFX_idea_generic_navy_bonus\n%s\n}"
                   % (i, n - 1, "\n".join("\t%s = %g" % kv for kv in mods.items())))
    w("common/dynamic_modifiers/hod_assault_fleet.txt", "\n".join(out) + "\n")
    import history_inject as H
    roots = " ".join("imp_tech_%s_%d = 1" % (s[0], s[1]) for s in SHIPS if not s[3] and s[2] == 976)   # like the other tabs' 976 roots (sw_tech_import.py)
    for p in sorted(os.listdir(os.path.join(MOD, "history", "countries"))):
        tag = p.split(" - ")[0]
        H.set_country(tag, "assault_fleet", ["add_dynamic_modifier = { modifier = hod_assault_fleet_%d }" % i for i in range(1, len(FLEET) + 1)])
        # no create_equipment_variant: the engine makes one default design per researched ship (named after the ship);
        # named designs on top doubled every ship in production. Fleets with carriers need the carrier tech at start
        # (a ship whose type is not researched has no design and the OOB crashes on it).
        extra = " imp_tech_cv_1 = 1" if tag in CARRIER_FLEETS else ""
        H.set_country(tag, "naval_start", ["set_technology = { %s%s popup = no }" % (roots, extra)])
    H.clear("naval_designs", "countries")


def icons():
    lines = ["# generated by plans & scripts/sw_tree/naval_tree.py: ship icons rendered from each ship's own model", "spriteTypes = {"]
    seen = set()

    def add(name, model):
        if name not in seen:
            seen.add(name)
            lines.append('\tspriteType = { name = "%s" texturefile = "%s" }' % (name, ICON % model))
    for line, tier, year, parents, cost, stats, gen, rep, cis in SHIPS:
        for tags, (_, model, _) in ((REP_TAGS, rep), (CIS_TAGS, cis)):
            for t in tags:
                add("GFX_%s_imp_tech_%s_%d_medium" % (t, line, tier), model)
                add("GFX_%s_%s_medium" % (t, eq(line, tier)), model)
        add("GFX_imp_tech_%s_%d_medium" % (line, tier), rep[1])       # everyone else: the Republic-built ship
        add("GFX_%s_medium" % eq(line, tier), rep[1])
    missing = [m for m in {s[7][1] for s in SHIPS} | {s[8][1] for s in SHIPS} if not os.path.exists(os.path.join(MOD, ICON % m))]
    assert not missing, missing
    w("interface/hod_sw_render_icons_naval.gfx", "\n".join(lines) + "\n}\n")


def ship_entities():
    """map models: the engine looks up <TAG>_<equipment>_entity / <equipment>_entity (vanilla ship_hull_super_carrier_entity),
    then <TAG>_<sub-unit>_entity / <sub-unit>_entity (vanilla ENG_battleship_entity); meshes from unit_models.py hod_ship_*"""
    out, seen = ["# generated by plans & scripts/sw_tree/naval_tree.py - clones need the zz_ file name (loaded after the meshes)"], set()

    def ent(name, model):
        if name not in seen:
            seen.add(name)
            out.append('entity = { name = "%s" clone = "hod_ship_%s_entity" }' % (name, model))
    for line, tier, year, parents, cost, stats, gen, rep, cis in SHIPS:
        e, unit = eq(line, tier), LINES[line][1]
        for tags, (_, model, _) in ((REP_TAGS, rep), (CIS_TAGS, cis)):
            for t in tags:
                ent("%s_%s_entity" % (t, e), model)
                ent("%s_%s_%d_entity" % (t, unit, tier - 1), model)   # ships pick <TAG>_<sub-unit>_<visual_level> per tier
                if tier == 1:
                    ent("%s_%s_entity" % (t, unit), model)
        ent("%s_entity" % e, rep[1])                # everyone else: the Republic-built ship
        ent("%s_%d_entity" % (unit, tier - 1), rep[1])
        if tier == 1:
            ent("%s_entity" % unit, rep[1])
    w("gfx/entities/zz_hod_sw_ship_models.asset", "\n".join(out) + "\n")


def _replace_block(path, keep, new_lines, anchor_after=None):
    """drop every loc line `keep(key)` is true for, insert new_lines where the first one was (or at the end)"""
    raw = open(os.path.join(MOD, path), "rb").read()
    bom, t = raw.startswith(b"\xef\xbb\xbf"), raw.decode("utf-8-sig")
    out, at = [], None
    for L in t.split("\n"):
        m = re.match(r"\s*([\w.-]+):\d*\s", L)
        if m and keep(m.group(1)):
            if at is None:
                at = len(out)
            continue
        out.append(L)
    if at is None:
        at = len(out) - (1 if out and not out[-1].strip() else 0)
    out[at:at] = new_lines
    w(path, "\n".join(out), bom)


def localisation():
    hull = re.compile(r"^(\w+_)?ship_hull_(light|cruiser_light|cruiser_heavy|heavy|carrier|submarine|assault)_imp(_\d)?(_desc|_short)?$")
    tag_lines, gen_lines = [], []
    for line, tier, year, parents, cost, stats, gen, rep, cis in SHIPS:
        e = eq(line, tier)
        for tags, (name, _, desc) in ((REP_TAGS, rep), (CIS_TAGS, cis)):
            for t in tags:
                tag_lines += [' %s_%s:0 "%s"' % (t, e, name), ' %s_%s_desc:0 "%s"' % (t, e, desc), ' %s_%s_short:0 "%s"' % (t, e, name)]
        gen_lines += [' %s:0 "%s"' % (e, gen), ' %s_short:0 "%s"' % (e, gen),
                      ' %s_desc:0 "%s, built or bought by worlds that answer to neither Republic nor Confederacy."' % (e, gen)]
    for line, (arch, unit, role, col, sprite, head) in LINES.items():
        gen_lines.append(' %s:0 "%s"' % (arch, head[:-1] if head.endswith("s") else head))
    def tagged(k):
        m = hull.match(k)
        return bool(m and m.group(1) and m.group(1)[:-1] in REP_TAGS + CIS_TAGS)
    _replace_block("localisation/english/hod_sw_faction_names_l_english.yml", tagged, tag_lines)
    old_tech = re.compile(r"^imp_tech_(dd|cl|ca|bb|cv|ss|as|artillery|armor|fire_control|torpedo|aa|secondaries|engine|sonar|deflector|radar|transport)_\d(_desc)?$")
    tech_lines = []
    for line, tier, year, parents, cost, stats, gen, rep, cis in SHIPS:
        tech_lines += [' imp_tech_%s_%d:0 "%s"' % (line, tier, gen), ' imp_tech_%s_%d_desc:0 "%s"' % (line, tier, "Unlocks the " + gen + ".")]
    tech_lines += [' imp_assault_ship:0 "Assault Ship"', ' imp_assault_ship_desc:0 "Armoured troop ship: it fights in the battle line, and every one in service makes landings faster and bigger."']
    for i, (n, mods) in enumerate(FLEET, 1):
        tech_lines.append(' hod_assault_fleet_%d:0 "Assault Fleet: %d+ Assault Ships"' % (i, n))
    _replace_block("localisation/english/hod_sw_tech_l_english.yml",
                   lambda k: (bool(hull.match(k)) and hull.match(k).group(1) is None) or bool(old_tech.match(k))
                   or k in ("imp_assault_ship", "imp_assault_ship_desc") or k.startswith("hod_assault_fleet_")
                   or bool(re.match(r"^imp_(ship_\w+|\w+_ship_engine_\d)(_desc)?$", k)), gen_lines + tech_lines)   # modules are gone


def fleets():
    import glob
    for p in glob.glob(os.path.join(MOD, "history/units/HOD_*.txt")):     # naval OOBs + the (unused) test space garrison
        raw = open(p, "rb").read()
        bom, t = raw.startswith(b"\xef\xbb\xbf"), raw.decode("utf-8-sig")
        t = re.sub(r"\n[ \t]*ship = \{[^\n]*definition = submarine[^\n]*", "", t)       # stealth ships are gone

        units = {LINES[l][1]: l for l in LINES}

        def sub(m):     # groups: 1 definition (legacy or ours), 2 equipment, 3 owner; the ship spawns as the owner's design
            line = FLEETS.get(m.group(1)) or units[m.group(1)]
            tier = int(m.group(2)[-1]) if m.group(1) in units else 1
            return 'definition = %s equipment = { %s = { amount = 1 owner = %s } }' % (LINES[line][1], eq(line, tier), m.group(3))
        t = re.sub(r"definition = (\w+) equipment = \{ (\w+) = \{ amount = 1 owner = (\w+)[^}]*\} \}", sub, t)
        # every start ship must be a type its owner has researched at start (else no design -> crash)
        bad = [m for m in re.findall(r"equipment = \{ (\w+) = \{ amount = 1 owner = (\w+)", t)
               if not m[0].endswith("_1") or (m[0].startswith("ship_hull_carrier") and m[1] not in CARRIER_FLEETS)]
        assert not bad, (p, bad[:3])
        open(p, "wb").write((b"\xef\xbb\xbf" if bom else b"") + t.encode("utf-8"))


def gui():
    p = os.path.join(MOD, "interface/countrytechtreeview.gui")
    t = open(p, encoding="utf-8-sig").read()
    a = t.index('name = "swnaval_folder"')
    s = t.index("\t\t\t# Hull chains", a)
    e = t.index('\t\tcontainerWindowType = {\n\t\t\tname = "swnaval_support_folder"', a)
    years = sorted(ROW)
    labels = "".join('\t\t\t\tinstantTextBoxType = { name = "naval_level%d" position = { x = 40 y = %d } textureFile = "" font = "hoi_36header" '
                     'borderSize = { x = 0 y = 4 } text = "level%d" maxWidth = 240 maxHeight = 32 format = left Orientation = "UPPER_LEFT" }\n'
                     % (i, 40 + 70 * ROW[y], i) for i, y in enumerate(years))
    heads = "".join('\t\t\tinstantTextBoxType = { name = "naval_head_%s" position = { x = %d y = 100 } textureFile = "" font = "hoi_24header" '
                    'borderSize = { x = 0 y = 4 } text = "%s" maxWidth = 220 maxHeight = 32 format = left Orientation = "UPPER_LEFT" }\n'
                    % (line, 340 + 70 * col - 70, head) for line, (arch, unit, role, col, sprite, head) in LINES.items())
    roots = ["%s_%d" % (l, n) for l, n, y, par, *_ in SHIPS if not par]
    boxes = "".join('\t\t\tgridboxtype = {\n\t\t\t\tname = "imp_tech_%s_tree"\n\t\t\t\tposition = { x = 340 y = 180 }\n'      # same grid + card as the air tab
                    '\t\t\t\tslotsize = { width = 70 height = 70 }\n\t\t\t\tformat = "UP"\n\t\t\t}\n' % r for r in roots)
    block = ("\t\t\t# Hull chains: generated by plans & scripts/sw_tree/naval_tree.py - one gridbox per root tech, years down the left\n"
             "\t\t\tcontainerWindowType = {\n\t\t\t\tname = \"naval_era_left\"\n\t\t\t\tposition = { x = 10 y = 140 }\n"
             "\t\t\t\tsize = { width = 80 height = 100%% }\n\t\t\t\torientation = upper_left\n" + labels + "\t\t\t}\n" + heads + boxes + "\t\t}\n\n")
    open(p, "w", encoding="utf-8", newline="\n").write(t[:s] + block + t[e:])


if __name__ == "__main__":
    assert all(p.split("_")[0] in LINES and any("%s_%d" % (s[0], s[1]) == p for s in SHIPS) for s0 in SHIPS for p in s0[3])
    assert all(s[2] in ROW for s in SHIPS) and len({(s[0], s[1]) for s in SHIPS}) == len(SHIPS)
    techs(); equipment(); subunits(); icons(); localisation(); fleets(); gui(); dynamic_modifiers(); ship_entities()
    print("naval tree:", len(SHIPS), "techs / ships")
