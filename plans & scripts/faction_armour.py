"""Faction armour trees: the Republic Armour Corps (walkers + self-propelled guns) and the Droid Armour tab
(droid tanks + self-propelled artillery, WIPGFX/techtreeCIS.png). Vanilla's armour tab stays for everyone else.

    python "WIPGFX/plans & scripts/faction_armour.py"

Run from the mod root. Writes common/technologies/hod_rep_armour.txt + hod_cis_armour.txt, the two tab windows and
buttons, the folders, localisation, placeholder icons, and the walker/tank upgrade limits. Re-runnable.
Also lays the hand-written Republic and Droid tabs (HAND_TABS) on the same year grid (YEAR_COL) and rebuilds their windows.
"""
import os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from faction_templates import UNLOCK    # tech -> free division template

V = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
GUI = "interface/countrytechtreeview.gui"
TAGS = "common/technology_tags/00_technology.txt"
UPGRADES = "common/units/equipment/upgrades/land_upgrades.txt"
REP_TAGS, CIS_TAGS = ("REP",), ("CIS", "TDF", "TCU", "CMG", "IBC")

BASE_MODULES = """tank_torsion_bar_suspension tank_riveted_armor tank_gasoline_engine tank_diesel_engine tank_petrol_electric_engine
tank_cast_armor tank_christie_suspension tank_bogie_suspension tank_interleaved_suspension tank_light_one_man_tank_turret
tank_light_two_man_tank_turret tank_light_three_man_tank_turret tank_light_fixed_superstructure_turret
tank_medium_one_man_tank_turret tank_medium_two_man_tank_turret tank_medium_three_man_tank_turret
tank_medium_fixed_superstructure_turret tank_heavy_two_man_tank_turret tank_heavy_three_man_tank_turret
tank_heavy_fixed_superstructure_turret tank_super_heavy_four_man_tank_turret tank_super_heavy_three_man_tank_turret
tank_modern_tank_turret sloped_armor extra_ammo_storage wet_ammo_storage smoke_launchers expanded_fuel_tank""".split()


# ── chassis helpers ──
def walker(size, n, sponson=False):
    base = "walker_chassis" if size == "light" else f"walker_chassis_{size}"
    pre = "walker" if size == "light" else f"walker_{size}"
    out = [f"{base}_{n}"] + [f"{pre}_{r}_chassis_{n}" for r in ("aa", "artillery", "destroyer", "flame")]
    return out + ([f"walker_sponson_chassis_{n}"] if sponson else [])


def tank(size, *ns):
    return [f"{size}_tank{r}_chassis_{n}" for n in ns for r in ("", "_destroyer", "_artillery", "_aa")]


def walker_units(size, roles):
    pre = "walkers_" + size if size != "light" else "walkers_light"
    names = {"base": pre, "artillery": f"{pre}_artillery", "destroyer": f"{pre}_destroyer", "aa": f"{pre}_aa",
             "flame": "walkers_flame" if size == "light" else f"walkers_{size}_flame",
             "support_aa": f"{pre}_support_aa", "support_destroyer": f"{pre}_support_destroyer", "recon": "walkers_light_recon"}
    return [names[r] for r in roles]


ALL = ("light", "medium", "heavy", "modern", "super_heavy")

# ── Republic: few, expensive, very armoured walkers that ignore rough ground; deep upgrade chains with refit choices ──
ROUGH = "hills = { attack = 0.05 movement = 0.10 } mountain = { attack = 0.05 movement = 0.10 } forest = { attack = 0.05 movement = 0.10 } jungle = { attack = 0.05 movement = 0.10 } urban = { attack = 0.05 movement = 0.10 }"
REP = {
    "rep_walker_atpt": (0, 9, 974, "AT-PT (Grand Army)", "All Terrain Personal Transports. Walkers stride over ground that stops wheels and repulsors.",
                        dict(eq=walker("light", 0, True), units=walker_units("light", ["base", "recon", "flame"]),
                             modules=BASE_MODULES + ["walker_pneumatic_damper"], template="HOD_unlock_walkers",
                             mods=f"\t\tcategory_walker_all = {{ {ROUGH} }}\n")),
    "rep_walker_atrt": (0, 15, 977, "AT-RT", "All Terrain Recon Transports: fast single-trooper walkers for scouting and flanking.",
                        dict(eq=walker("light", 1, True), modules=["walker_fixed_sponson_turret"], parent="rep_walker_atpt")),
    "rep_atrt_recon": (2, 18, 978, "AT-RT Recon Package", "Long-range sensors and lighter armour turn the AT-RT into the army's eyes.",
                       dict(parent="rep_walker_atrt", xor=["rep_atrt_assault"],
                            mods="\t\twalkers_light_recon = { max_organisation = 5 maximum_speed = 0.15 }\n\t\twalkers_light = { maximum_speed = 0.10 }\n")),
    "rep_atrt_assault": (4, 18, 978, "AT-RT Assault Package", "Repeating blasters and mortar launchers: the AT-RT goes in with the troopers.",
                         dict(parent="rep_walker_atrt", xor=["rep_atrt_recon"],
                              mods="\t\twalkers_light = { soft_attack = 0.10 breakthrough = 0.10 }\n")),
    "rep_walker_atrt_501": (0, 24, 980, "AT-RT (501st Pattern)", "Uprated AT-RTs with heavier repeating blasters, used by the veteran legions.",
                            dict(eq=walker("light", 2, True), parent="rep_walker_atrt")),
    "rep_walker_atst": (0, 33, 983, "AT-ST", "Two-man scout walkers that replace the AT-RT in the Imperial army.",
                        dict(mods="\t\twalkers_light = { soft_attack = 0.10 breakthrough = 0.10 }\n", parent="rep_walker_atrt_501")),
    "rep_walker_atte": (6, 15, 977, "AT-TE", "All Terrain Tactical Enforcers: six-legged assault walkers with a mass-driver cannon and a platoon aboard.",
                        dict(eq=walker("medium", 0), units=walker_units("medium", ["base", "flame"]),
                             modules=["walker_hydropneumatic_recuperator"], parent="rep_walker_atpt",
                             mods="\t\tcategory_walker_all = { max_organisation = 5 }\n")),
    "rep_walker_atte_elite": (6, 21, 979, "Elite AT-TE", "Heavier plating and refined fire control for the veteran walker companies.",
                              dict(eq=walker("medium", 1), modules=["walker_oscillating_autoloader"], parent="rep_walker_atte")),
    "rep_atte_assault": (8, 24, 980, "AT-TE Assault Refit", "Extra cannon ammunition and ram plating: AT-TEs that lead the breakthrough.",
                         dict(parent="rep_walker_atte_elite", xor=["rep_atte_transport"],
                              mods="\t\twalkers_medium = { breakthrough = 0.15 soft_attack = 0.05 }\n")),
    "rep_atte_transport": (10, 24, 980, "AT-TE Transport Refit", "Room for two full platoons: the walker becomes a mobile fortress for its troopers.",
                           dict(parent="rep_walker_atte_elite", xor=["rep_atte_assault"],
                                mods="\t\twalkers_medium = { max_organisation = 10 defense = 0.10 }\n")),
    "rep_atte_spotter": (12, 24, 980, "AT-TE Spotter Refit", "Sensor masts and fire-control links direct the walking artillery behind the line.",
                         dict(parent="rep_walker_atte_elite",
                              mods="\t\tcategory_walker_artillery = { soft_attack = 0.10 }\n\t\twalkers_medium = { soft_attack = 0.03 }\n")),
    "rep_walker_atte_sieges": (6, 27, 981, "AT-TE (Outer Rim Sieges)", "The definitive AT-TE, rebuilt from the lessons of the Outer Rim Sieges.",
                               dict(eq=walker("medium", 2), parent="rep_walker_atte_elite",
                                    mods="\t\tcategory_walker_all = { armor_value = 0.05 defense = 0.05 }\n")),
    "rep_walker_atap": (14, 18, 978, "AT-AP", "All Terrain Attack Pods: walking artillery that braces on a third leg to fire its heavy cannon.",
                        dict(eq=walker("heavy", 0), units=walker_units("heavy", ["base", "flame"]), parent="rep_walker_atte",
                             mods="\t\tcategory_walker_artillery = { soft_attack = 0.05 }\n")),
    "rep_atap_siege": (16, 21, 979, "Siege Configuration", "Bigger shells for fortress walls: AT-APs that crack defended lines.",
                       dict(parent="rep_walker_atap", xor=["rep_atap_antiarmour"],
                            mods="\t\twalkers_heavy = { soft_attack = 0.10 fort = { attack = 0.15 } }\n")),
    "rep_atap_antiarmour": (18, 21, 979, "Anti-Armour Configuration", "Penetrator rounds and target trackers for hunting droid tanks.",
                            dict(parent="rep_walker_atap", xor=["rep_atap_siege"],
                                 mods="\t\twalkers_heavy = { hard_attack = 0.15 ap_attack = 0.10 }\n")),
    "rep_walker_atot": (14, 24, 980, "AT-OT", "All Terrain Open Transports: heavy walkers that carry whole companies behind the battle line.",
                        dict(eq=walker("heavy", 1), parent="rep_walker_atap")),
    "rep_walker_utat": (14, 30, 982, "UT-AT", "Unstable Terrain Artillery Transports: tracked heavy walkers with a twin heavy laser turret.",
                        dict(eq=walker("heavy", 2), parent="rep_walker_atot")),
    "rep_walker_atat_kuat": (20, 27, 981, "AT-AT (Battle of Kuat)", "The first All Terrain Armoured Transports, built at Kuat at the end of the war.",
                             dict(eq=walker("modern", 0), units=walker_units("modern", ["base", "flame"]), parent="rep_walker_atap",
                                  mods="\t\tcategory_walker_main = { breakthrough = 0.10 armor_value = 0.05 }\n")),
    "rep_walker_atat_elite": (20, 33, 983, "Elite AT-AT", "Fully armoured AT-ATs and the giant siege walkers of the Imperial army.",
                              dict(eq=walker("super_heavy", 0) + ["walker_chassis_land_cruiser_1"],
                                   units=walker_units("super_heavy", ["base", "flame"]) + ["walker_land_cruiser"],
                                   modules=["tank_super_heavy_cannon", "walker_lc_load_frame", "walker_lc_800mm_bombard"],
                                   parent="rep_walker_atat_kuat")),
    "rep_spg_av7": (22, 12, 976, "AV-7 Anti-Vehicle Cannon", "A repulsor-mounted cannon that digs in on four legs: the Republic's first self-propelled gun.",
                    dict(units=walker_units("light", ["artillery"]), mods="\t\twalkers_light_artillery = { soft_attack = 0.05 }\n")),
    "rep_spg_spham": (22, 18, 978, "SPHA-M", "Medium Self-Propelled Heavy Artillery walkers accompany the AT-TE companies.",
                      dict(units=walker_units("medium", ["artillery"]), parent="rep_spg_av7")),
    "rep_spg_sphat": (22, 24, 980, "SPHA-T", "The twelve-legged turbolaser platforms that brought down core ships at Geonosis.",
                      dict(units=walker_units("heavy", ["artillery"]) + walker_units("modern", ["artillery"]), parent="rep_spg_spham")),
    "rep_spg_turbo": (22, 33, 983, "Turbolaser Siege Batteries", "Super-heavy siege walkers mounting starship-grade turbolasers.",
                      dict(units=walker_units("super_heavy", ["artillery"]), parent="rep_spg_sphat",
                           mods="\t\tcategory_walker_artillery = { soft_attack = 0.10 }\n")),
    "rep_walker_atar": (24, 15, 977, "AT-AR Anti-Armour Walkers", "Walkers rebuilt around a single heavy anti-armour cannon to hunt droid tanks.",
                        dict(units=[u for s in ALL for u in walker_units(s, ["destroyer"] + (["support_destroyer"] if s != "super_heavy" else []))],
                             parent="rep_walker_atpt")),
    "rep_walker_ataa": (24, 24, 980, "AT-AA", "All Terrain Anti-Aircraft walkers: flak and laser batteries against droid gunships.",
                        dict(units=[u for s in ALL for u in walker_units(s, ["aa"] + (["support_aa"] if s != "super_heavy" else []))],
                             parent="rep_walker_atar")),
    "rep_tx130": (26, 15, 977, "TX-130 Saber Fighter Tank", "Fast repulsor fighter tanks attached to clone divisions as support companies.",
                  dict(eq=["repulsor_tank_equipment_1"], units=["repulsor_tank_company"])),
    "rep_tx130t": (26, 24, 980, "TX-130T", "The improved TX-130 with heavier armour and missile launchers.",
                   dict(eq=["repulsor_tank_equipment_2"], parent="rep_tx130")),
    "rep_tx225": (26, 33, 983, "TX-225 GAVw Occupier", "The Empire's armoured repulsor tank for occupation and convoy duty.",
                  dict(eq=["repulsor_tank_equipment_3"], parent="rep_tx130t")),
}
for i, (y, yr) in enumerate(zip((12, 18, 24, 33), (976, 978, 980, 983)), 1):
    n = ["I", "II", "III", "IV"][i - 1]
    REP[f"rep_gyro_{i}"] = (28, y, yr, f"Gyro-Stabilisers {n}", "Better gyro-stabilisers keep walkers sure-footed on broken ground, and allow stronger motivators (engine upgrade limit).",
                            dict(parent=f"rep_gyro_{i - 1}" if i > 1 else None,
                                 mods="\t\tcategory_walker_all = { marsh = { movement = 0.05 } river = { movement = 0.05 } forest = { movement = 0.05 } }\n"))
    REP[f"rep_durasteel_{i}"] = (30, y, yr, f"Durasteel Armour {n}", "Thicker durasteel hulls: walkers shrug off what would kill a tank (armour upgrade limit).",
                                 dict(parent=f"rep_durasteel_{i - 1}" if i > 1 else None,
                                      mods="\t\tcategory_walker_all = { armor_value = 0.03 }\n",
                                      modules={1: ["tank_welded_armor"], 3: ["lc_armored_skirts"]}.get(i, [])))

# ── Separatists: cheap, fast repulsor tanks and droid walkers in wide parallel lines (WIPGFX/techtreeCIS.png) ──
CIS = {
    "cis_aat": (4, 6, 970, "Armoured Assault Tank", "Baktoid's AAT. Repulsor tanks race across open ground; droid crews never tire, but cut corners.",
                dict(eq=tank("medium", 0, 1), units=["medium_armor"], modules=BASE_MODULES, template="HOD_unlock_droid_tanks",
                     mods="\t\tcategory_all_armor = { maximum_speed = 0.10 reliability = -0.05 plains = { attack = 0.05 } desert = { attack = 0.05 } }\n")),
    "cis_octuptarra": (0, 12, 976, "Octuptarra Combat Tri-Droid", "Three-legged combat droids whose turreted head fires in every direction.",
                       dict(eq=tank("light", 0, 1), units=["light_armor", "light_sp_anti_air_brigade", "light_sp_anti_air_support"],
                            parent="cis_aat")),
    "cis_crab": (0, 15, 977, "LM-432 Crab Droid", "Six-legged crab droids that wade through swamps and rivers no tank can cross.",
                 dict(eq=tank("light", 2), xor=["cis_dsd1"], parent="cis_octuptarra",
                      mods="\t\tlight_armor = { soft_attack = 0.05 marsh = { attack = 0.10 movement = 0.20 } river = { attack = 0.10 } }\n")),
    "cis_octuptarra_2": (0, 24, 980, "Octuptarra Combat Tri-Droid Mk.II", "Uprated tri-droids with heavier blasters and armour.",
                         dict(eq=tank("light", 3), units=["medium_sp_anti_air_brigade", "medium_sp_anti_air_support"], parent="cis_crab")),
    "cis_dsd1": (2, 15, 977, "DSD1 Dwarf Spider Droid", "Commerce Guild dwarf spider droids that climb cliffs and hold mountain passes.",
                 dict(eq=tank("light", 2), xor=["cis_crab"], parent="cis_octuptarra",
                      mods="\t\tlight_armor = { breakthrough = 0.05 hills = { attack = 0.10 } mountain = { attack = 0.10 movement = 0.10 } }\n")),
    "cis_dsd2": (2, 24, 980, "DSD2 Heavy Dwarf Spider Droid", "A larger dwarf spider carrying the punch of a medium tank.",
                 dict(eq=tank("medium", 3), parent=["cis_dsd1", "cis_gat"])),
    "cis_adsd": (2, 30, 982, "A-DSD Advanced Dwarf Spider Droid", "Advanced dwarf spiders: the last and best of the Commerce Guild's walking tanks.",
                 dict(eq=tank("modern", 1), units=["modern_armor"], parent="cis_dsd2")),
    "cis_gat": (4, 15, 977, "Ground Armoured Tank", "The GAT: a lighter, faster repulsor tank for exploiting breakthroughs.",
                dict(eq=tank("medium", 2), parent="cis_aat", modules=["tank_welded_armor"],
                     mods="\t\tmedium_armor = { maximum_speed = 0.10 breakthrough = 0.05 }\n")),
    "cis_haat": (6, 15, 977, "Heavy Armoured Assault Tank", "The heavy AAT, with thicker hull plating and a bigger main cannon.",
                 dict(eq=tank("heavy", 0, 1), units=["heavy_armor"], parent="cis_aat")),
    "cis_persuader": (6, 24, 980, "NR-N99 Persuader-Class Enforcer", "Corporate Alliance tank droids rolling on a single huge wheel.",
                      dict(eq=tank("heavy", 2), parent="cis_haat", modules=["lc_armored_skirts"])),
    "cis_magna": (6, 33, 983, "Octuptarra Magna Tri-Droid", "Giant tri-droids that tower over the battlefield and crush walkers below them.",
                  dict(eq=tank("heavy", 3) + tank("super_heavy", 1),
                       units=["super_heavy_armor", "heavy_sp_anti_air_brigade", "heavy_sp_anti_air_support",
                              "super_heavy_sp_anti_air_brigade", "modern_sp_anti_air_brigade", "modern_sp_anti_air_support"],
                       modules=["tank_super_heavy_cannon"], parent="cis_persuader")),
    "cis_hailfire": (8, 12, 976, "IG-227 Hailfire-Class Droid", "Hoop-wheeled droids that rain homing missiles on clone positions.",
                     dict(units=["light_sp_artillery_brigade"], mods="\t\tlight_sp_artillery_brigade = { soft_attack = 0.05 }\n")),
    "cis_payloads": (8, 15, 977, "Higher Armament Payloads", "Bigger missile racks: more firepower, slower to redeploy.",
                     dict(xor=["cis_redeploy"], parent="cis_hailfire",
                          mods="\t\tcategory_self_propelled_artillery = { soft_attack = 0.10 }\n")),
    "cis_redeploy": (10, 15, 977, "Rapid Redeployment Capabilities", "Lighter loads and refresher droids keep the batteries on the move.",
                     dict(xor=["cis_payloads"], parent="cis_hailfire",
                          mods="\t\tcategory_self_propelled_artillery = { max_organisation = 5 breakthrough = 0.10 }\n")),
    "cis_hailfire_heavy": (8, 18, 978, "IG-228 Heavy Hailfire Droid", "Heavy Hailfires carry missile batteries fit for a siege.",
                           dict(units=["medium_sp_artillery_brigade", "heavy_sp_artillery_brigade"], parent=["cis_payloads", "cis_redeploy"])),
    "cis_og9": (8, 24, 980, "OG-9 Homing Spider Droid", "Huge spider droids whose dish cannon tracks targets across the battlefield.",
                dict(eq=["motorized_rocket_equipment_1"], units=["motorized_rocket_brigade"], parent="cis_hailfire_heavy")),
    "cis_og9_targeting": (8, 30, 982, "Improved Autonomous Targeting", "Spider droids that pick their own targets without waiting for a tactical droid.",
                          dict(parent="cis_og9", mods="\t\tmotorized_rocket_brigade = { soft_attack = 0.10 hard_attack = 0.10 }\n")),
    "cis_targeting": (10, 24, 980, "Improved Targeting Arrays", "Networked targeting from tactical droids sharpens every battery's aim.",
                      dict(parent="cis_hailfire_heavy", mods="\t\tcategory_self_propelled_artillery = { soft_attack = 0.05 }\n")),
    "cis_production": (10, 27, 981, "Increased Production Efficiency", "Self-propelled artillery comes off the same lines as the battle droids.",
                       dict(parent="cis_hailfire_heavy", extra="\t\tproduction_factory_efficiency_gain_factor = 0.05\n")),
    "cis_protodeka": (10, 33, 983, "Protodeka Mark II", "Colossal artillery droids: the Confederacy's last word in siege warfare.",
                      dict(units=["super_heavy_sp_artillery_brigade", "modern_sp_artillery_brigade"],
                           parent=["cis_targeting", "cis_production"], deps=["cis_targeting", "cis_production"])),
    "cis_hag": (12, 24, 980, "Heavy Artillery Gun Tank", "The HAG: a tracked gun platform built to kill walkers at range.",
                dict(units=["light_tank_destroyer_brigade", "medium_tank_destroyer_brigade", "heavy_tank_destroyer_brigade",
                            "super_heavy_tank_destroyer_brigade", "modern_tank_destroyer_brigade", "light_tank_destroyer_support",
                            "medium_tank_destroyer_support", "heavy_tank_destroyer_support", "modern_tank_destroyer_support"],
                     parent="cis_hailfire_heavy")),
    "cis_long_range": (12, 30, 982, "Long-Range Weaponry", "Longer barrels and better optics let gun tanks fire first.",
                       dict(parent="cis_hag", mods="\t\tcategory_tank_destroyers = { hard_attack = 0.10 ap_attack = 0.10 }\n")),
}
for i, (y, yr) in enumerate(zip((12, 18, 24, 33), (976, 978, 980, 983)), 1):
    n = ["I", "II", "III", "IV"][i - 1]
    CIS[f"cis_repulsor_{i}"] = (14, y, yr, f"Repulsorlift Engines {n}", "Stronger repulsorlift generators: faster tanks and a higher engine upgrade limit.",
                                dict(parent=f"cis_repulsor_{i - 1}" if i > 1 else None,
                                     mods="\t\tcategory_all_armor = { maximum_speed = 0.05 }\n"))
for i, (y, yr) in enumerate(zip((12, 21, 30), (976, 979, 982)), 1):
    n = ["I", "II", "III"][i - 1]
    CIS[f"cis_foundry_{i}"] = (16, y, yr, f"Foundry Automation {n}", "Automated foundry worlds stamp out droid tanks faster and cheaper with every generation.",
                               dict(parent=f"cis_foundry_{i - 1}" if i > 1 else None, idea=f"HOD_droid_foundries_{i}",
                                    extra="\t\tline_change_production_efficiency_factor = 0.05\n"))
# armour upgrade limit: Republic durasteel line; Separatists get it with each generation of tanks
ARMOUR_CAPS = {1: ["rep_durasteel_1", "cis_aat"], 2: ["rep_durasteel_2", "cis_gat", "cis_haat"],
               3: ["rep_durasteel_3", "cis_persuader", "cis_dsd2", "cis_octuptarra_2"], 4: ["rep_durasteel_4", "cis_magna", "cis_adsd"]}
ENGINE_CAPS = {i: [f"rep_gyro_{i}", f"cis_repulsor_{i}"] for i in range(1, 5)}
FOUNDRY_COST = {1: -0.10, 2: -0.20, 3: -0.30}   # armour build cost: droid tanks are cheap

FOLDERS = {
    "rep": dict(folder="hod_rep_armour_folder", name="Republic Armour Corps", tree=REP, tags=REP_TAGS, root="rep_walker_atpt",
                rows=[("Light Walkers", 0), ("AT-RT Refits", 2), ("Assault Walkers", 6), ("AT-TE Refits", 8),
                      ("Heavy Walkers", 14), ("AT-AP Configurations", 16), ("Armoured Walkers", 20), ("Self-Propelled Guns", 22),
                      ("Anti-Armour & AA", 24), ("Repulsor Tanks", 26), ("Gyro-Stabilisers", 28), ("Durasteel Armour", 30)]),
    "cis": dict(folder="hod_cis_armour_folder", name="Droid Armour", tree=CIS, tags=("CIS",), root="cis_aat",
                rows=[("Light Droid Tanks", 0), ("Dwarf Spider Droids", 2), ("Assault Tanks", 4), ("Heavy Tanks", 6),
                      ("Hailfire Artillery", 8), ("Artillery Upgrades", 10), ("Anti-Tank", 12), ("Repulsorlift Engines", 14),
                      ("Foundry Automation", 16)]),
}

# Shared grid of every HoD tab (Republic, Droid, both armour tabs), Old World Blues style: lines in rows (x), time
# across (y). A tech card is 183x84 px on a 70 px grid, so a year step is 3 columns and a line takes 2 rows.
YEAR_COL = {960: 0, 964: 3, 970: 6, 974: 9, 976: 12, 977: 15, 978: 18, 979: 21, 980: 24, 981: 27, 982: 30, 983: 33, 985: 36}
ERAS = [("Old Republic", 0), ("Battle of Geonosis", 12), ("Late War", 21), ("Imperial Era", 30)]
GRID_X, GRID_Y, SLOT = 300, 140, 70


def check_layout(name, pos, parents, years):
    """pos {tech: (row, col)}: no two cards overlap, none sits left of its year, children are right of their parents"""
    for a, (ra, ca) in pos.items():
        for b, (rb, cb) in pos.items():
            assert a == b or abs(ra - rb) >= 2 or abs(ca - cb) >= 3, f"{name}: {a} and {b} overlap"
        assert ca >= YEAR_COL[years[a]], f"{name}: {a} sits left of its start year"
        for p in parents(a):
            assert ca > pos[p][1], f"{name}: {a} is not right of its parent {p}"


def year_col(col):
    """column as its year constant (@977); every card sits on a year column"""
    return "@" + str({c: y for y, c in YEAR_COL.items()}[col])


def tech_block(tid, row, col, year, folder, spec, tree):
    parents = lambda v: [v[5]["parent"]] if isinstance(v[5].get("parent"), str) else (v[5].get("parent") or [])
    kids = [t for t, v in tree.items() if tid in parents(v)]
    b = [f"\t{tid} = {{"]
    if spec.get("mods"):
        b.append(spec["mods"].rstrip("\n"))
    if spec.get("extra"):
        b.append(spec["extra"].rstrip("\n"))
    for key, val in (("enable_equipments", spec.get("eq")), ("enable_subunits", spec.get("units")),
                     ("enable_equipment_modules", spec.get("modules"))):
        if val:
            b.append(f"\t\t{key} = {{\n" + "".join(f"\t\t\t{x}\n" for x in val) + "\t\t}")
    if spec.get("template"):
        unit = {"HOD_unlock_walkers": "walkers_light", "HOD_unlock_droid_tanks": "medium_armor"}[spec["template"]]
        b.append(f"\t\ton_research_complete_limit = {{ NOT = {{ has_template_containing_unit = {unit} }} }}\n"
                 f"\t\ton_research_complete = {{\n\t\t\thidden_effect = {{ load_oob = \"{spec['template']}\" }}\n"
                 f"\t\t\tcustom_effect_tooltip = UNLOCK_DIVISION_TEMPLATE\n\t\t}}")
    if tid in UNLOCK and not spec.get("template"):     # free division template (faction_templates.py)
        oob, _name, _t, unit = UNLOCK[tid]
        b.append(f"\t\ton_research_complete_limit = {{ NOT = {{ has_template_containing_unit = {unit} }} }}\n"
                 f"\t\ton_research_complete = {{\n\t\t\thidden_effect = {{ load_oob = \"{oob}\" }}\n"
                 f"\t\t\tcustom_effect_tooltip = UNLOCK_DIVISION_TEMPLATE\n\t\t}}")
    for k in kids:
        b.append(f"\t\tpath = {{ leads_to_tech = {k} research_cost_coeff = 1 }}")
    if spec.get("xor"):
        b.append("\t\tXOR = { " + " ".join(spec["xor"]) + " }")
    if spec.get("deps"):
        b.append("\t\tdependencies = { " + " ".join(f"{d} = 1" for d in spec["deps"]) + " }")
    if spec.get("idea"):     # foundry automation: swaps in the next droid foundry spirit
        b.append(f"\t\ton_research_complete = {{\n\t\t\tHOD_set_droid_foundries = yes\n\t\t\tcustom_effect_tooltip = {spec['idea']}_tt\n\t\t}}")
    support = any(w in tid for w in ("gyro", "durasteel", "repulsor_", "foundry", "_recon", "_assault", "_transport",
                                     "_spotter", "_siege", "_antiarmour", "payloads", "redeploy"))
    b.append(f"\t\tresearch_cost = {1.5 if support else 2}")
    b.append(f"\t\tstart_year = {year}")
    b.append(f"\t\tfolder = {{ name = {folder} position = {{ x = {row} y = {year_col(col)} }} }}")
    b.append("\t\tcategories = { armor }")
    b.append(f"\t\tai_will_do = {{ factor = 1 modifier = {{ factor = 2 date > \"{year}.1.1\" }} }}")
    b.append("\t}")
    return "\n".join(b)


def write_techs():
    for key, f in FOLDERS.items():
        tree = f["tree"]
        par = lambda t: [tree[t][5]["parent"]] if isinstance(tree[t][5].get("parent"), str) else (tree[t][5].get("parent") or [])
        check_layout(f["folder"], {t: v[:2] for t, v in tree.items()}, par, {t: v[2] for t, v in tree.items()})
        out = [f"technologies = {{\n\t# HOD: {f['name']} (faction_armour.py). Rows (x) are lines, columns (y) the shared HoD year grid\n"
               + "".join(f"\t@{y} = {c}\n" for y, c in YEAR_COL.items())]
        for tid, (row, col, year, _n, _d, spec) in tree.items():
            out.append(tech_block(tid, row, col, year, f["folder"], spec, tree))
        open(f"common/technologies/hod_{key}_armour.txt", "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n}\n")


def rw(path, fn):
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    crlf = "\r\n" in s
    s = fn(s.replace("\r\n", "\n"))
    c = re.sub(r"#[^\n]*", "", s)
    assert c.count("{") == c.count("}"), path
    open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + (s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))


def lineage(tags, root):
    return "OR = { " + " ".join(f"original_tag = {t}" for t in tags) + f" has_tech = {root} }}"


def write_tags():
    def fn(s):
        s = re.sub(r"\n\t(hod_rep_armour_folder|hod_cis_armour_folder) = \{[^{}]*(\{[^{}]*(\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}", "", s)
        s = re.sub(r"(\n\tnsb_armour_folder = \{)[^{}]*(\{[^{}]*(\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}", r"\1\n\t\tledger = army\n\t}", s)
        own = " ".join([lineage(FOLDERS["rep"]["tags"], "rep_walker_atpt"), lineage(FOLDERS["cis"]["tags"], "cis_aat")])
        s = s.replace("\n\tnsb_armour_folder = {\n\t\tledger = army\n\t}",
                      "\n\tnsb_armour_folder = {\n\t\t# HOD: Republic and Separatist lineages use their own armour tabs\n"
                      f"\t\tavailable = {{ NOT = {{ OR = {{ {own} }} }} }}\n\t\tledger = army\n\t}}")
        add = "".join(f"\n\t{f['folder']} = {{\n\t\tavailable = {{ {lineage(f['tags'], f['root'])} }}\n\t\tledger = army\n\t}}"
                      for f in FOLDERS.values())
        return s.replace("\n\tnsb_armour_folder = {", add + "\n\tnsb_armour_folder = {", 1)
    rw(TAGS, fn)


def window(folder, rows, roots, max_col, bg=None):
    """a horizontal tech tab on the shared grid: era headers across the top, line names down the left column"""
    gx = GRID_X
    text = lambda name, x, y, t, font, w, fmt: f'''
				instantTextBoxType = {{
					name = "{name}"
					position = {{ x = {x} y = {y} }}
					textureFile = ""
					font = "{font}"
					borderSize = {{ x = 0 y = 0}}
					text = "{t}"
					maxWidth = {w}
					maxHeight = 62
					format = {fmt}
					Orientation = "UPPER_LEFT"
				}}'''
    ends = [c for _t, c in ERAS[1:]] + [max_col + 3]
    heads = "".join(text(f"{folder}_era{i}", gx + (c0 + c1) * SLOT // 2 - 55 - 150, 50, t, "hoi_36header", 300, "center")
                    for i, ((t, c0), c1) in enumerate(zip(ERAS, ends)))
    labs = "".join(text(f"{folder}_row{i}", 20, GRID_Y + x * SLOT + 12, t, "hoi_33", 260, "left") for i, (t, x) in enumerate(rows))
    width = gx + (max_col + 3) * SLOT
    height = GRID_Y + (max(x for _t, x in rows) + 4) * SLOT
    grids = "".join(f'''
			gridboxtype = {{
				name = "{t}_tree"
				position = {{ x = {gx} y = {GRID_Y} }}
				slotsize = {{ width = {SLOT} height = {SLOT} }}
				format = "LEFT"
			}}''' for t in roots)
    return f'''containerWindowType = {{
			name = "{folder}"
			position = {{ x=0 y=47 }}
			size = {{ width = 100%% height = 100%% }}
			margin = {{ top = 13 left = 13 bottom = 24 right = 25}}
			drag_scroll = {{ left middle }}
			verticalScrollbar = "right_vertical_slider"
			horizontalScrollbar = "bottom_horizontal_slider"
			scroll_wheel_factor = 40

			background = {{
				name = "Background"
				quadTextureSprite ="GFX_tiled_window_2b_border"
			}}

			containerWindowType = {{
				name = "techtree_stripes"
				position = {{ x= 0 y= 0 }}
				size = {{
					width = {width} height = {height}
					min = {{ width = 100%% height = 100%% }}
				}}
				clipping = no

				iconType = {{
					name ="{folder}_bg"
					spriteType = "{bg or 'GFX_infantry_techtree_bg'}"
					position = {{ x=0 y=0 }}
					alwaystransparent = yes
				}}
				# HOD: faction_armour.py{heads}
{labs}
			}}
{grids}
		}}'''


# Hand-written tabs on the same grid: this only moves their techs onto the year columns and rebuilds their windows
HAND_TABS = [
    dict(file="common/technologies/republic_military.txt", folder="republic_folder",
         rows=[("Clone Equipment", 0), ("ARC Troopers", 2), ("LAAT Air Cavalry", 4), ("Ion Weapons", 6)]),
    dict(file="common/technologies/cis_droid_military.txt", folder="droid_folder",
         rows=[("Commando Droids", 0), ("Infantry Droids", 2), ("Droideka", 4), ("MagnaGuard", 6), ("Heavy Droids", 8),
               ("Spider Droids", 10)]),
]


def block_end(s, i):
    d = 1
    while d:
        d += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    return i


def write_hand_tabs():
    for tab in HAND_TABS:
        s = open(tab["file"], encoding="utf-8-sig").read().replace("\r\n", "\n")
        s = s.replace("\n\t# HOD: columns (y) are the shared HoD year grid (faction_armour.py)", "")
        body = s.index("{") + 1
        consts = dict(re.findall(r"^\t@(\w+) = (\d+)", s, re.M))
        techs = {}
        for m in re.finditer(r"^\t(\w+) = \{", s, re.M):
            b = s[m.end():block_end(s, m.end())]
            x = re.search(r"position = \{ x = (@?\w+)", b).group(1)
            techs[m.group(1)] = dict(year=int(re.search(r"start_year = (\d+)", b).group(1)),
                                     row=int(consts.get(x[1:], x) if x[0] == "@" else x), x=x,
                                     kids=re.findall(r"leads_to_tech = (\w+)", re.sub(r"#[^\n]*", "", b)))
        par = lambda t: [p for p, v in techs.items() if t in v["kids"]]
        pos = {}
        def place(t):
            if t not in pos:
                pos[t] = (techs[t]["row"], max([YEAR_COL[techs[t]["year"]]] + [place(p)[1] + 3 for p in par(t)]))
            return pos[t]
        for t in techs:
            place(t)
        check_layout(tab["folder"], pos, par, {t: v["year"] for t, v in techs.items()})
        # header: the shared year constants replace the tab's own column constants (row constants stay)
        rows_used = {v["x"][1:] for v in techs.values() if v["x"][0] == "@"}
        s = re.sub(r"^\t@(\w+) = \d+\n", lambda m: m.group(0) if m.group(1) in rows_used else "", s, flags=re.M)
        s = s[:body] + "\n\t# HOD: columns (y) are the shared HoD year grid (faction_armour.py)\n" \
            + "".join(f"\t@{y} = {c}\n" for y, c in YEAR_COL.items()) + "\n" + s[body:].lstrip("\n")
        for t, (_r, c) in pos.items():
            s = re.sub(rf"(^\t{t} = \{{.*?position = \{{ x = @?\w+ y = )[^ }}]+", rf"\g<1>{year_col(c)}", s, count=1, flags=re.M | re.S)
        rw(tab["file"], lambda _old: s)
        roots = [t for t in techs if not par(t)]
        rw(GUI, lambda g: (lambda j, k: g[:j] + window(tab["folder"], tab["rows"], roots, max(c for _r, c in pos.values())) + g[k:])(*span(g, tab["folder"])))


def armour_window(f):
    roots = [t for t, v in f["tree"].items() if not v[5].get("parent")]
    return window(f["folder"], f["rows"], roots, max(v[1] for v in f["tree"].values()))


def span(g, name):
    i = g.index(f'name = "{name}"')
    j = g.rfind("containerWindowType", 0, i)
    k, d = g.index("{", j) + 1, 1
    while d:
        d += {"{": 1, "}": -1}.get(g[k], 0)
        k += 1
    return j, k


def write_gui():
    def fn(g):
        for f in FOLDERS.values():
            if f'name = "{f["folder"]}"' in g:
                j, k = span(g, f["folder"])
                g = g[:j] + armour_window(f) + g[k:]
            else:                              # new window: right after the vanilla armour tab's window
                j, k = span(g, "nsb_armour_folder")
                g = g[:k] + "\n\t\t" + armour_window(f) + g[k:]
        # every tech tab needs its own item templates (techtree_<folder>_item / _small_item): the armour tab's
        for f in FOLDERS.values():
            for kind in ("item", "small_item"):
                name = f"techtree_{f['folder']}_{kind}"
                if f'name = "{name}"' not in g:
                    j, k = span(g, f"techtree_nsb_armour_folder_{kind}")
                    g = g[:k] + "\n\t" + g[j:k].replace(f'"techtree_nsb_armour_folder_{kind}"', f'"{name}"', 1) + g[k:]
        # tab buttons: same slot as the vanilla armour tab (never both visible)
        m = re.search(r'\n(\t*)buttonType = \{[^{}]*?name = "nsb_armour_folder_tab"[^{}]*?(\{[^{}]*\}[^{}]*?)*\}', g)
        nsb = m.group(0)
        for f in FOLDERS.values():
            if f'name = "{f["folder"]}_tab"' not in g:
                g = g[:m.end()] + nsb.replace('"nsb_armour_folder_tab"', f'"{f["folder"]}_tab"') + g[m.end():]
        return g
    rw(GUI, fn)


def write_loc():
    out = ["l_english:", " # HOD: faction armour tabs (faction_armour.py)"]
    for f in FOLDERS.values():
        out.append(f' {f["folder"]}:0 "{f["name"]}"')
        for tid, (_r, _c, _y, n, d, _s) in f["tree"].items():
            out += [f' {tid}:0 "{n}"', f' {tid}_desc:0 "{d}"']
    for i, cost in FOUNDRY_COST.items():
        name = ["Droid Foundries", "Automated Foundry Worlds", "Total Foundry Automation"][i - 1]
        out += [f' HOD_droid_foundries_{i}:0 "{name}"',
                f' HOD_droid_foundries_{i}_desc:0 "The Confederacy\'s foundry worlds build droid tanks by the thousand, at a fraction of what a walker costs the Republic."',
                f' HOD_droid_foundries_{i}_tt:0 "Gain the national spirit §Y{name}§!: armour costs §G{int(cost * 100)}%§!."']
    # droid tank chassis per Separatist member, from the tree (vanilla tank chassis, droid names)
    names = {"light_tank_chassis": ["Octuptarra Tri-Droid", "Octuptarra Combat Tri-Droid", "DSD1 Dwarf Spider Droid", "Octuptarra Tri-Droid Mk.II"],
             "medium_tank_chassis": ["Armoured Assault Tank", "AAT Mk.II", "Ground Armoured Tank", "DSD2 Heavy Dwarf Spider Droid"],
             "heavy_tank_chassis": ["Heavy Armoured Assault Tank", "HAAT Mk.II", "NR-N99 Persuader-Class Enforcer", "Octuptarra Magna Tri-Droid"],
             "super_heavy_tank_chassis": [None, "Octuptarra Magna Siege Droid"], "modern_tank_chassis": [None, "A-DSD Advanced Dwarf Spider Droid"]}
    for tag in CIS_TAGS:
        for base, ns in names.items():
            for i, n in enumerate(ns):
                if n:
                    out += [f' {tag}_{base}_{i}:0 "{n}"', f' {tag}_{base}_{i}_short:0 "{n}"']
    open("localisation/english/HOD_faction_armour_l_english.yml", "w", encoding="utf-8-sig", newline="\n").write("\n".join(out) + "\n")


ICONS = {   # placeholder art: HoD's Republic vehicle icons, vanilla tank icons for the droid tanks
    "rep_walker_atpt": "Republic Equipment/REP_armored_car1_medium.dds", "rep_walker_atrt": "Republic Equipment/REP_armored_car2_medium.dds",
    "rep_walker_atrt_501": "Republic Equipment/REP_armored_car3_medium.dds", "rep_walker_atst": "Republic Equipment/REP_support_weapons4_medium.dds",
    "rep_walker_atte": "Republic Equipment/REP_mechanised_infantry3_medium.dds", "rep_walker_atte_elite": "Republic Equipment/REP_mechanised_infantry3_medium.dds",
    "rep_walker_atte_sieges": "Republic Equipment/REP_mechanised_infantry3_medium.dds", "rep_walker_atap": "Republic Equipment/REP_motorised_infantry_medium.dds",
    "rep_walker_atot": "Republic Equipment/REP_motorised_infantry_medium.dds", "rep_walker_utat": "Republic Equipment/REP_motorised_infantry_medium.dds",
    "rep_walker_atat_kuat": "Republic Equipment/REP_mechanised_infantry3_medium.dds", "rep_walker_atat_elite": "Republic Equipment/REP_mechanised_infantry3_medium.dds",
    "rep_spg_av7": "Republic Equipment/REP_advanced_infantry_weapons2_medium.dds", "rep_spg_spham": "Republic Equipment/REP_advanced_infantry_weapons2_medium.dds",
    "rep_spg_sphat": "Republic Equipment/REP_advanced_infantry_weapons2_medium.dds", "rep_spg_turbo": "Republic Equipment/REP_advanced_infantry_weapons2_medium.dds",
    "rep_walker_atar": "Republic Equipment/REP_infantry_at2_medium.dds", "rep_walker_ataa": "Republic Equipment/REP_infantry_at_medium.dds",
    "rep_tx130": "Republic Equipment/REP_mechanised_infantry_medium.dds", "rep_tx130t": "Republic Equipment/REP_mechanised_infantry_medium.dds",
    "rep_tx225": "Republic Equipment/REP_mechanised_infantry2_medium.dds",
    "rep_atrt_recon": "Republic Equipment/REP_night_vision_medium.dds", "rep_atrt_assault": "Republic Equipment/REP_improved_infantry_weapons_2_medium.dds",
    "rep_atte_assault": "Republic Equipment/REP_infantry_at2_medium.dds", "rep_atte_transport": "Republic Equipment/REP_support_weapons_medium.dds",
    "rep_atte_spotter": "Republic Equipment/REP_night_vision2_medium.dds", "rep_atap_siege": "Republic Equipment/REP_advanced_infantry_weapons2_medium.dds",
    "rep_atap_antiarmour": "Republic Equipment/REP_infantry_at2_medium.dds",
}
VANILLA_ICONS = {"light": "basic_light_tank", "medium": "basic_medium_tank", "heavy": "basic_heavy_tank", "art": "artillery1",
                 "at": "antitank1", "gear": "engine_tech_1", "armor": "armor_tech_1"}


def write_icons():
    os.makedirs("gfx/interface/technologies/hod_armour", exist_ok=True)
    have = {}
    for k, v in VANILLA_ICONS.items():
        src = f"{V}/gfx/interface/technologies/{v}_medium.dds"
        if not os.path.exists(src):
            src = next((f"{V}/gfx/interface/technologies/{x}" for x in sorted(os.listdir(f"{V}/gfx/interface/technologies"))
                        if x.startswith(v.split("_")[0]) and x.endswith(".dds")), None)
        if src:
            dst = f"gfx/interface/technologies/hod_armour/{k}.dds"
            shutil.copy2(src, dst)
            have[k] = dst
    pick = lambda tid: ("light" if any(w in tid for w in ("octuptarra", "crab", "dsd")) else
                        "heavy" if any(w in tid for w in ("haat", "persuader", "magna")) else
                        "art" if any(w in tid for w in ("hailfire", "payload", "redeploy", "og9", "targeting", "protodeka", "production")) else
                        "at" if any(w in tid for w in ("hag", "long_range")) else
                        "gear" if ("repulsor_" in tid or "gyro" in tid) else "armor" if ("durasteel" in tid or "foundry" in tid) else "medium")
    out = ["spriteTypes = {", "\t# HOD: placeholder icons for the faction armour tabs (faction_armour.py)"]
    for f in FOLDERS.values():
        for tid in f["tree"]:
            tex = f"gfx/interface/technologies/{ICONS[tid]}" if tid in ICONS else have.get(pick(tid))
            if tex and os.path.exists(tex):
                out.append(f'\tspriteType = {{ name = "GFX_{tid}_medium" texturefile = "{tex}" }}')
    open("interface/hod_faction_armour_icons.gfx", "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n}\n")


def write_upgrades():
    """designer upgrade limits: vanilla's engine / armour techs, or each faction's own (ENGINE_CAPS / ARMOUR_CAPS)"""
    def fn(s):
        for kind, caps in (("engine_tech", ENGINE_CAPS), ("armor_tech", ARMOUR_CAPS)):
            for i, ours in caps.items():
                cond = "OR = { " + " ".join(f"has_tech = {t}" for t in [f"{kind}_{i}"] + ours) + " }"
                # a previous run's OR block, or vanilla's single condition
                s = re.sub(r"OR = \{ has_tech = %s_%d\b[^{}]*\}" % (kind, i), cond, s)
                s = re.sub(r"(?<!OR = \{ )has_tech = %s_%d\b(?! has_tech)" % (kind, i), cond, s)
        return s
    rw(UPGRADES, fn)


def write_foundries():
    """droid foundry spirits: cheaper armour with each Foundry Automation tech"""
    ideas = ["ideas = {", "\tcountry = {", "\t\t# HOD: Droid Armour tab, Foundry Automation (faction_armour.py)"]
    for i, cost in FOUNDRY_COST.items():
        ideas.append(f"\t\tHOD_droid_foundries_{i} = {{\n\t\t\tallowed = {{ always = no }}\n\t\t\tremoval_cost = -1\n"
                     f"\t\t\tequipment_bonus = {{\n\t\t\t\tarmor = {{ build_cost_ic = {cost} instant = yes }}\n\t\t\t}}\n\t\t}}")
    open("common/ideas/HOD_droid_foundries.txt", "w", encoding="utf-8", newline="\n").write("\n".join(ideas + ["\t}", "}", ""]))
    eff = ["# HOD: the best Foundry Automation level researched sets the droid foundry spirit (faction_armour.py)",
           "HOD_set_droid_foundries = {"]
    for i in FOUNDRY_COST:
        eff.append(f"\tif = {{ limit = {{ has_idea = HOD_droid_foundries_{i} }} remove_ideas = HOD_droid_foundries_{i} }}")
    for n, i in enumerate(sorted(FOUNDRY_COST, reverse=True)):
        eff.append(f"\t{'if' if n == 0 else 'else_if'} = {{ limit = {{ has_tech = cis_foundry_{i} }} add_ideas = HOD_droid_foundries_{i} }}")
    open("common/scripted_effects/HOD_droid_foundries_effects.txt", "w", encoding="utf-8", newline="\n").write("\n".join(eff + ["}", ""]))


def write_templates():
    open("history/units/HOD_unlock_droid_tanks.txt", "w", encoding="utf-8-sig", newline="\n").write(
        "# HOD: template added by the Armoured Assault Tank tech (hod_cis_armour.txt)\n"
        "division_template = {\n\tname = \"AAT Armoured Division\"\n\tdivision_names_group = CIS_INF_01\n\n\tregiments = {\n"
        + "".join(f"\t\tmedium_armor = {{ x = 0 y = {y} }}\n" for y in range(3))
        + "".join(f"\t\tinfantry_droid = {{ x = 1 y = {y} }}\n" for y in range(3)) + "\t}\n}\n")


if __name__ == "__main__":
    write_techs()
    write_tags()
    write_gui()
    write_hand_tabs()
    write_loc()
    write_icons()
    write_upgrades()
    write_templates()
    write_foundries()
    print("written:", {k: len(f["tree"]) for k, f in FOLDERS.items()})
