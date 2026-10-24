"""HoD tech tree generator: the whole Star Wars tech tree as data (design: military_design.txt).

  python "WIPGFX/plans & scripts/techtree_gen.py" check    validate only (modifiers, buildings, links, layout)
  python "WIPGFX/plans & scripts/techtree_gen.py" write    write common/technologies/hod_*.txt, technology_tags,
                                                           the tab windows in interface/countrytechtreeview.gui,
                                                           placeholder icon sprites and localisation

Layout (as the Republic tab): time runs left to right in four era columns (Old Republic | Battle of Geonosis |
Late War | Imperial Era), each 7 slots of 70 px; a tech is 2 slots wide; every line is a row, 3 slots high.
Each line's first tech roots a tree (gridbox "<tech>_tree" in the tab window); the rest follow by `path`.
Eras per domain (OWB tech levels): the first tech of an era in every line needs that domain's era tech.
"""
import os, re, sys
from collections import OrderedDict

VANILLA = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
ERAS = ["Old Republic", "Battle of Geonosis", "Late War", "Imperial Era"]
ERA_YEARS = [(964, 975), (976, 977), (978, 979), (980, 983)]
ERA_SLOT, TECH_W, ROW_H, SLOT = 7, 2, 3, 70
GRID_X, GRID_Y = 140, 210                         # pixel origin of the first row (as the Republic tab)

# tab key -> (folder, era tech domain, title shown on the era techs)
TABS = OrderedDict([
    ("infantry", ("infantry_folder", "Infantry")),
    ("support", ("support_folder", "Support")),
    ("vehicles", ("armour_folder", "Vehicle")),
    ("air", ("air_techs_folder", "Starfighter")),
    ("fleet", ("naval_folder", "Fleet")),
    ("engineering", ("electronics_folder", "Engineering")),
    ("industry", ("industry_folder", "Industry")),
    ("clone", ("republic_folder", "Cloning")),
    ("droid", ("droid_folder", "Droid")),
])

TECHS = OrderedDict()       # id -> dict
LINES = OrderedDict()       # (tab, row) -> [ids]


def tech(tid, tab, row, era, step, name, desc="", cost=1.5, mods=None, unlock_eq=(), unlock_units=(),
         unlock_modules=(), buildings=(), cats=(), parent="auto", deps=(), xor=(), branch_of=None, ai=1, extra=""):
    """One tech. era 0-3, step 0-2 within the era column. parent: previous tech in the line by default."""
    assert tid not in TECHS, tid
    line = LINES.setdefault((tab, row), [])
    if parent == "auto":
        parent = line[-1] if line else None
    y0, y1 = ERA_YEARS[era]
    TECHS[tid] = dict(id=tid, tab=tab, row=row, era=era, step=step, name=name, desc=desc, cost=cost,
                      mods=mods or {}, eq=list(unlock_eq), units=list(unlock_units), modules=list(unlock_modules),
                      buildings=list(buildings), cats=list(cats), parent=parent, deps=list(deps), xor=list(xor),
                      year=y0 + min(step, y1 - y0), ai=ai, extra=extra, children=[])
    line.append(tid)
    if parent:
        TECHS[parent]["children"].append(tid)
    return tid


def ladder(prefix, tab, row, entries, cats, start_era=0):
    """A line of techs: entries = [(era, step, name, mods, extra kwargs), ...]; ids prefix_1.._n"""
    ids = []
    for i, e in enumerate(entries, 1):
        era, step, name, mods = e[:4]
        kw = dict(e[4]) if len(e) > 4 else {}
        kw.setdefault("cats", cats)                # a tech's own categories override the line's
        ids.append(tech(f"{prefix}_{i}", tab, row, era, step, name, mods=mods, **kw))
    return ids


# ─────────────────────────────── ERAS + ACCESS (hidden techs) ───────────────────────────────
HIDDEN = OrderedDict()       # id -> (name, desc)
ACCESS = OrderedDict([
    ("access_kamino_cloning", ("Kaminoan Cloning", "Access to the cloning facilities of Kamino: clone troopers and their gear.")),
    ("access_droid_foundries", ("Droid Foundries", "Access to battle droid foundries: B1, B2, commando droids and droidekas.")),
    ("access_beskar", ("Beskar Forges", "Access to Mandalorian iron and the clans' war gear.")),
    ("access_force_order", ("The Jedi Order", "Jedi serve in this army's ranks.")),
    ("access_sith", ("The Dark Side", "Sith acolytes and dark side warriors serve this army.")),
])
ERA_COST = [0, 3.0, 4.0, 5.0]


def era_techs():
    """Researchable era techs, the first row (row 0) of every tab (OWB tech levels)."""
    for tab, (folder, dom) in TABS.items():
        prev = None
        for e in range(1, 4):
            prev = tech(f"era_{tab}_{e + 1}", tab, 0, e, 0, f"{ERAS[e]}: {dom}",
                        desc=f"Opens the {ERAS[e]} {dom.lower()} technologies.", cost=ERA_COST[e], cats=["hod_era"],
                        parent=prev, ai=3)


# ─────────────────────────────── INDUSTRY ───────────────────────────────
def industry():
    c = ["industry"]
    ladder("hod_production", "industry", 1, [
        (0, 0, "Assembly Lines", {"production_factory_max_efficiency_factor": 0.05}),
        (0, 2, "Standardised Components", {"production_factory_efficiency_gain_factor": 0.05,
                                            "line_change_production_efficiency_factor": 0.05}),
        (1, 0, "Droid-Assisted Lines", {"production_factory_max_efficiency_factor": 0.05}),
        (1, 2, "Modular Production", {"production_factory_start_efficiency_factor": 0.05,
                                       "line_change_production_efficiency_factor": 0.05}),
        (2, 0, "Automated Foundries", {"production_factory_max_efficiency_factor": 0.05,
                                       "production_factory_efficiency_gain_factor": 0.05}),
        (3, 0, "Foundry Worlds", {"production_factory_max_efficiency_factor": 0.05,
                                  "production_factory_start_efficiency_factor": 0.05}),
    ], c)
    # the vanilla concentrated / dispersed choice: foundry worlds or hidden production
    a = tech("hod_centralised_industry", "industry", 2, 1, 1, "Centralised Foundry Worlds", cats=c,
             parent="hod_production_2", mods={"industrial_capacity_factory": 0.05, "industry_air_damage_factor": 0.1},
             xor=["hod_dispersed_industry"])
    b = tech("hod_dispersed_industry", "industry", 3, 1, 1, "Dispersed Production", cats=c,
             parent="hod_production_2", mods={"industry_air_damage_factor": -0.15, "industry_repair_factor": 0.1},
             xor=["hod_centralised_industry"])
    tech("hod_centralised_industry_2", "industry", 2, 2, 1, "Planetary Manufacturing Hubs", cats=c, parent=a,
         mods={"industrial_capacity_factory": 0.05, "industrial_capacity_dockyard": 0.05})
    tech("hod_dispersed_industry_2", "industry", 3, 2, 1, "Hidden Foundries", cats=c, parent=b,
         mods={"industry_air_damage_factor": -0.15, "industry_repair_factor": 0.1, "industrial_capacity_factory": 0.03})
    ladder("hod_construction", "industry", 4, [
        (0, 0, "Prefabricated Structures", {"production_speed_buildings_factor": 0.1}),
        (0, 2, "Construction Droids", {"production_speed_buildings_factor": 0.1}),
        (1, 1, "Rapid Deployment Modules", {"production_speed_buildings_factor": 0.1, "global_building_slots_factor": 0.1}),
        (2, 1, "Orbital Construction", {"production_speed_buildings_factor": 0.1, "global_building_slots_factor": 0.1}),
        (3, 1, "Imperial Engineering Corps", {"production_speed_buildings_factor": 0.1, "global_building_slots_factor": 0.1}),
    ], c)
    ladder("hod_mining", "industry", 5, [
        (0, 0, "Asteroid Prospecting", {"local_resources_factor": 0.1}),
        (1, 0, "Durasteel Refining", {"local_resources_factor": 0.1}),
        (2, 0, "Deep-Core Mining Droids", {"local_resources_factor": 0.1}),
        (3, 0, "Planetary Strip-Mining", {"local_resources_factor": 0.1}),
    ], c)
    ladder("hod_fuel", "industry", 6, [
        (0, 0, "Fuel Depots", {}, {"buildings": [("fuel_silo", 1)]}),
        (0, 2, "Tibanna Gas Refining", {"fuel_gain_factor": 0.1}, {"buildings": [("synthetic_refinery", 1)]}),
        (1, 1, "Tibanna Processing Platforms", {"fuel_gain_factor": 0.1, "fuel_gain_factor_from_states": 0.1}),
        (2, 1, "Hypermatter Fuel Cells", {"fuel_gain_factor": 0.1, "fuel_gain_factor_from_states": 0.1}),
        (3, 1, "Imperial Fuel Reserves", {"fuel_gain_factor": 0.1, "fuel_gain_factor_from_states": 0.1}),
    ], c)
    ladder("hod_shipyards", "industry", 7, [
        (0, 1, "Orbital Drydocks", {"industrial_capacity_dockyard": 0.1}),
        (1, 1, "Kuat Construction Standards", {"industrial_capacity_dockyard": 0.1}),
        (2, 1, "Starship Assembly Rings", {"industrial_capacity_dockyard": 0.1}),
        (3, 1, "Imperial Fleet Yards", {"industrial_capacity_dockyard": 0.1}),
    ], c)
    ladder("hod_power", "industry", 8, [
        (0, 1, "Fusion Generators", {"energy_gain_factor": 0.1}),
        (1, 1, "Hypermatter Reactors", {"energy_gain_factor": 0.1}),
        (2, 1, "Planetary Power Grids", {"energy_gain_factor": 0.1}),
    ], c)


# ─────────────────────────────── ENGINEERING ───────────────────────────────
def engineering():
    c = ["electronics"]
    ladder("hod_computing", "engineering", 1, [
        (0, 0, "Droid Logic Cores", {"research_speed_factor": 0.03}, {"cats": ["electronics", "computing_tech"]}),
        (0, 2, "Navicomputers", {"research_speed_factor": 0.03}, {"cats": ["electronics", "computing_tech"]}),
        (1, 1, "Tactical Droid Processors", {"research_speed_factor": 0.03}, {"cats": ["electronics", "computing_tech"]}),
        (2, 1, "Holographic Data Cores", {"research_speed_factor": 0.03}, {"cats": ["electronics", "computing_tech"]}),
        (3, 1, "Imperial Data Networks", {"research_speed_factor": 0.03}, {"cats": ["electronics", "computing_tech"]}),
    ], c)
    for kind, row, names in (("encryption", 2, ["Codebook Ciphers", "Holonet Scrambling", "Rotating Cipher Keys"]),
                             ("decryption", 3, ["Signal Interception", "Slicer Droids", "Code Cylinder Analysis"])):
        ladder(f"hod_{kind}", "engineering", row, [
            (0, 2, names[0], {}, {"extra": f"{kind} = 1", "cats": ["electronics", f"{kind}_tech"]}),
            (1, 2, names[1], {}, {"extra": f"{kind} = 1", "cats": ["electronics", f"{kind}_tech"]}),
            (2, 2, names[2], {}, {"extra": f"{kind} = 1", "cats": ["electronics", f"{kind}_tech"]}),
        ], c)
    ladder("hod_sensors", "engineering", 4, [
        (0, 1, "Sensor Arrays", {}, {"buildings": [("radar_station", 2)], "cats": ["electronics", "radar_tech"]}),
        (1, 0, "Long-Range Scanners", {"static_anti_air_hit_chance_factor": 0.05},
         {"buildings": [("radar_station", 2)], "cats": ["electronics", "radar_tech"]}),
        (2, 0, "Hyperspace Tracking", {"static_anti_air_hit_chance_factor": 0.05},
         {"buildings": [("radar_station", 1)], "cats": ["electronics", "radar_tech"]}),
    ], c)
    ladder("hod_holonet", "engineering", 5, [
        (0, 1, "HoloNet Relays", {"coordination_bonus": 0.05}),
        (1, 1, "Encrypted Command Channels", {"coordination_bonus": 0.05, "land_reinforce_rate": 0.02}),
        (2, 1, "Battle Network Coordination", {"coordination_bonus": 0.05, "land_reinforce_rate": 0.02}),
    ], c)
    ladder("hod_medicine", "engineering", 6, [
        (0, 1, "Bacta Treatment", {"land_reinforce_rate": 0.02}),
        (1, 0, "Field Bacta Tanks", {"land_reinforce_rate": 0.02, "experience_loss_factor": -0.05}),
        (2, 0, "Cybernetic Prosthetics", {"experience_loss_factor": -0.1}),
    ], c)
    ladder("hod_hyperdrive", "engineering", 7, [
        (0, 0, "Hyperdrive Theory", {"naval_speed_factor": 0.03}),
        (1, 0, "Class 1 Hyperdrives", {"naval_speed_factor": 0.03}),
        (2, 0, "Hyperspace Lane Mapping", {"naval_speed_factor": 0.03}),
    ], c)
    ladder("hod_shield_theory", "engineering", 8, [
        (0, 1, "Deflector Shield Theory", {}),
        (1, 1, "Ray and Particle Shielding", {}),
        (2, 1, "Planetary Shield Generators", {}),
        (3, 1, "Theater Shield Projectors", {}),
    ], c)
    ladder("hod_missiles", "engineering", 9, [
        (1, 1, "Concussion Missiles", {}, {"buildings": [("rocket_site", 1)], "cats": ["electronics", "rocketry"]}),
        (2, 1, "Orbital Strike Missiles", {}, {"cats": ["electronics", "rocketry"]}),
    ], c)
    ladder("hod_superweapons", "engineering", 10, [
        (1, 2, "Hypermatter Physics", {}, {"buildings": [("nuclear_reactor", 1)], "cats": ["electronics", "nuclear"]}),
        (2, 2, "Orbital Bombardment Doctrine", {}, {"extra": "nuclear_production = 1", "cats": ["electronics", "nuclear"]}),
        (3, 2, "Superlaser Research", {}, {"extra": "nuclear_production = 1", "cats": ["electronics", "nuclear"]}),
    ], c)


# ─────────────────────────────── EQUIPMENT + UNITS ───────────────────────────────
# Structures come from the vanilla definitions (every field the engine accepts), renamed and re-statted.
EQUIP = OrderedDict()   # archetype -> dict(template, type, base stats, variants[])
UNITS = OrderedDict()   # sub-unit -> dict(template, need, overrides, name, desc)
STATS = ("soft_attack", "hard_attack", "ap_attack", "air_attack", "defense", "breakthrough", "armor_value", "hardness",
         "maximum_speed", "reliability", "build_cost_ic")


def archetype(eid, template, name, base, resources, desc="", picture=None):
    EQUIP[eid] = dict(template=template, name=name, desc=desc, base=base, resources=resources, variants=[],
                      picture=picture)


def variant(arch, vid, year, name, stats=None, parent=None, resources=None):
    """a buildable variant: stats override the archetype's; parent = the variant it upgrades from"""
    EQUIP[arch]["variants"].append(dict(id=vid, year=year, name=name, stats=stats or {}, parent=parent,
                                        resources=resources))
    return vid


def unit(uid, template, name, need, desc="", overrides=None):
    UNITS[uid] = dict(template=template, name=name, desc=desc, need=need, overrides=overrides or {})
    return uid


def land_equipment():
    s = lambda **k: k
    # ── infantry small arms: one archetype, branches (heavy / precision) from the Clone Wars era ──
    archetype("hod_blaster_equipment", "infantry_equipment", "Blaster Rifles",
              s(soft_attack=3, hard_attack=0.5, ap_attack=1, defense=20, breakthrough=2, reliability=0.9,
                maximum_speed=4, build_cost_ic=0.45), {"steel": 2}, picture="archetype_infantry_equipment")
    b1 = variant("hod_blaster_equipment", "hod_blaster_equipment_1", 964, "Old Republic Blasters")
    b2 = variant("hod_blaster_equipment", "hod_blaster_equipment_2", 970, "Standard Blaster Rifles",
                 s(soft_attack=3.6, ap_attack=1.5, defense=22, breakthrough=2.4, build_cost_ic=0.5), parent=b1)
    prev = {"": b2, "_heavy": b2, "_precision": b2}
    for era, (year, sa, ha, ap, de, bt, cost) in enumerate(((976, 4.5, 0.7, 2.5, 25, 3, 0.58),
                                                           (978, 5.5, 0.9, 3.5, 28, 3.5, 0.65),
                                                           (980, 6.5, 1.1, 5, 31, 4, 0.72)), 3):
        nm = {3: "Military", 4: "Advanced", 5: "Imperial"}[era]
        prev[""] = variant("hod_blaster_equipment", f"hod_blaster_equipment_{era}", year, f"{nm} Blaster Rifles",
                           s(soft_attack=sa, hard_attack=ha, ap_attack=ap, defense=de, breakthrough=bt, build_cost_ic=cost),
                           parent=prev[""])
        prev["_heavy"] = variant("hod_blaster_equipment", f"hod_blaster_equipment_{era}_heavy", year, f"{nm} Repeating Blasters",
                                 s(soft_attack=round(sa * 1.25, 2), hard_attack=ha, ap_attack=ap - 0.5, defense=de - 1,
                                   breakthrough=bt - 0.5, build_cost_ic=round(cost * 1.12, 2)), parent=prev["_heavy"])
        prev["_precision"] = variant("hod_blaster_equipment", f"hod_blaster_equipment_{era}_precision", year,
                                     f"{nm} Long-Range Rifles",
                                     s(soft_attack=sa, hard_attack=ha + 0.2, ap_attack=round(ap * 1.6, 2), defense=de - 2,
                                       breakthrough=round(bt * 1.5, 2), build_cost_ic=round(cost * 1.12, 2)),
                                     parent=prev["_precision"])
    archetype("hod_jetpack_equipment", "support_equipment", "Jetpacks",
              s(build_cost_ic=1.5, reliability=0.8), {"aluminium": 1}, picture="archetype_support_equipment")
    variant("hod_jetpack_equipment", "hod_jetpack_equipment_1", 976, "Military Jetpacks")
    variant("hod_jetpack_equipment", "hod_jetpack_equipment_2", 980, "Advanced Jetpacks", s(build_cost_ic=1.6, reliability=0.9),
            parent="hod_jetpack_equipment_1")
    # ── support gear, artillery, anti-armour, flak, speeders ──
    archetype("hod_support_equipment", "support_equipment", "Field Support Gear", s(build_cost_ic=1.0, reliability=0.9),
              {"steel": 1}, picture="archetype_support_equipment")
    variant("hod_support_equipment", "hod_support_equipment_1", 966, "Field Support Gear")
    variant("hod_support_equipment", "hod_support_equipment_2", 976, "Military Support Gear", s(build_cost_ic=1.1),
            parent="hod_support_equipment_1")
    variant("hod_support_equipment", "hod_support_equipment_3", 980, "Advanced Support Gear", s(build_cost_ic=1.2),
            parent="hod_support_equipment_2")
    for arch, tmpl, name, pic, res, tiers in (
        ("hod_artillery_equipment", "artillery_equipment", "Artillery", "archetype_artillery_equipment", {"steel": 2},
         [(966, "Mass-Driver Cannons", {}), (976, "Heavy Laser Cannons", s(soft_attack=1.25)),
          (978, "Self-Propelled Heavy Artillery", s(soft_attack=1.5, breakthrough=1.2)),
          (980, "Imperial Siege Batteries", s(soft_attack=1.8, breakthrough=1.4))]),
        ("hod_missile_artillery_equipment", "rocket_artillery_equipment", "Missile Artillery",
         "archetype_rocket_artillery_equipment", {"steel": 1, "tungsten": 1},
         [(976, "Concussion Missile Launchers", {}), (978, "Mobile Missile Batteries", s(soft_attack=1.3)),
          (980, "Imperial Missile Batteries", s(soft_attack=1.6))]),
        ("hod_antiarmor_equipment", "anti_tank_equipment", "Anti-Armour Weapons", "archetype_anti_tank_equipment",
         {"steel": 1, "tungsten": 1},
         [(966, "Rocket Launchers", {}), (976, "Anti-Vehicle Laser Cannons", s(hard_attack=1.3, ap_attack=1.3)),
          (978, "Ion Cannons", s(hard_attack=1.6, ap_attack=1.6)), (980, "Heavy Ion Cannons", s(hard_attack=1.9, ap_attack=1.9))]),
        ("hod_flak_equipment", "anti_air_equipment", "Flak Batteries", "archetype_anti_air_equipment", {"steel": 1},
         [(966, "Anti-Air Repeaters", {}), (976, "Flak Laser Batteries", s(air_attack=1.3)),
          (978, "Tracking Flak Emplacements", s(air_attack=1.6)), (980, "Imperial Point-Defence Batteries", s(air_attack=1.9))]),
        ("hod_speeder_equipment", "motorized_equipment", "Speeders", "archetype_motorized_equipment", {"oil": 1},
         [(966, "Civilian Speeders", {}), (976, "Military Speeder Bikes", s(maximum_speed=1.15)),
          (978, "Armoured Speeders", s(maximum_speed=1.25, reliability=1.05)),
          (980, "Imperial Speeder Bikes", s(maximum_speed=1.35, reliability=1.1))]),
    ):
        archetype(arch, tmpl, name, {}, res, picture=pic)          # base stats: the vanilla archetype's own
        prev = None
        for i, (year, vname, mult) in enumerate(tiers, 1):
            prev = variant(arch, f"{arch}_{i}", year, vname, {f"*{k}": v for k, v in mult.items()}, parent=prev)


def land_units():
    unit("hod_trooper", "infantry", "Troopers", {"hod_blaster_equipment": 100},
         "Line infantry with blaster rifles: the backbone of every army in the galaxy.")
    unit("hod_heavy_trooper", "infantry", "Heavy Troopers", {"hod_blaster_equipment": 80, "hod_support_equipment": 20},
         "Troopers with repeating blasters and launchers: more firepower, slower to move.",
         {"combat_width": 2, "max_organisation": 55, "training_time": 110})
    unit("hod_militia", "infantry", "Planetary Militia", {"hod_blaster_equipment": 80},
         "Local defence forces: cheap and quick to raise, best behind fortifications.",
         {"max_organisation": 40, "training_time": 45, "manpower": 1200, "default_morale": 0.25})
    unit("hod_jump_trooper", "paratrooper", "Jump Troopers", {"hod_blaster_equipment": 100, "hod_jetpack_equipment": 20},
         "Jetpack-equipped troopers dropped from gunships behind enemy lines.")
    unit("hod_assault_trooper", "marine", "Orbital Assault Troopers", {"hod_blaster_equipment": 100},
         "Troopers trained to storm a world from orbit through enemy-held landing zones.")
    unit("hod_mountain_trooper", "mountaineers", "Mountain Troopers", {"hod_blaster_equipment": 100, "hod_support_equipment": 10},
         "Troopers equipped for high-gravity, mountain and arctic worlds.")
    unit("hod_speeder_trooper", "motorized", "Speeder Troopers", {"hod_blaster_equipment": 100, "hod_speeder_equipment": 35},
         "Troopers on speeder bikes and transports: fast, fragile, and everywhere at once.")
    # support companies
    unit("hod_engineers", "engineer", "Combat Engineers", {"hod_blaster_equipment": 20, "hod_support_equipment": 10})
    unit("hod_recon", "recon", "Speeder Scouts", {"hod_blaster_equipment": 20, "hod_speeder_equipment": 10})
    unit("hod_medics", "field_hospital", "Bacta Medics", {"hod_support_equipment": 30})
    unit("hod_logistics", "logistics_company", "Logistics Company", {"hod_support_equipment": 15, "hod_speeder_equipment": 20})
    unit("hod_maintenance", "maintenance_company", "Maintenance Droids", {"hod_support_equipment": 30})
    unit("hod_signal", "signal_company", "HoloNet Communications", {"hod_support_equipment": 15})
    unit("hod_military_police", "military_police", "Military Police", {"hod_blaster_equipment": 20, "hod_support_equipment": 10})
    # fire support: line battalions and support companies
    unit("hod_artillery", "artillery_brigade", "Artillery Battalion", {"hod_artillery_equipment": 12})
    unit("hod_artillery_support", "artillery", "Artillery Company", {"hod_artillery_equipment": 12})
    unit("hod_missile_artillery", "rocket_artillery_brigade", "Missile Battery", {"hod_missile_artillery_equipment": 12})
    unit("hod_missile_artillery_support", "rocket_artillery", "Missile Company", {"hod_missile_artillery_equipment": 12})
    unit("hod_antiarmor", "anti_tank_brigade", "Anti-Armour Battalion", {"hod_antiarmor_equipment": 24})
    unit("hod_antiarmor_support", "anti_tank", "Anti-Armour Company", {"hod_antiarmor_equipment": 24})
    unit("hod_flak", "anti_air_brigade", "Flak Battalion", {"hod_flak_equipment": 20})
    unit("hod_flak_support", "anti_air", "Flak Company", {"hod_flak_equipment": 20})


# ─────────────────────────────── VEHICLE DESIGNER (chassis, roles, modules) ───────────────────────────────
SIZES = [("light", "light", "Light"), ("medium", "medium", "Medium"), ("heavy", "heavy", "Heavy"),
         ("superheavy", "super_heavy", "Super-Heavy")]           # our key, vanilla prefix, display
ROLES = [("aa", "aa", "Flak"), ("artillery", "artillery", "Artillery"), ("destroyer", "destroyer", "Anti-Armour")]
CHASSIS = OrderedDict()      # our chassis archetype -> dict(template, variants[(id, template variant, year, name)])
ROLE_CHASSIS = OrderedDict() # our role chassis -> (archetype, vanilla role chassis template, type)
MODULES = OrderedDict()      # our module -> (vanilla template module, display name)


def vehicle_designer():
    eras = {"light": [(964, 0, "Old Republic"), (976, 1, "Military"), (978, 2, "Advanced"), (980, 3, "Imperial")],
            "medium": [(970, 0, "Old Republic"), (976, 1, "Military"), (978, 2, "Advanced"), (980, 3, "Imperial")],
            "heavy": [(976, 0, "Military"), (978, 1, "Advanced"), (980, 2, "Imperial")],
            "superheavy": [(978, None, "Advanced"), (980, 1, "Imperial")]}
    for key, vp, disp in SIZES:
        arch = f"hod_{key}_vehicle_chassis"
        vs = []
        for i, (year, vi, nm) in enumerate(eras[key], 1):
            tmpl = f"{vp}_tank_chassis" + ("" if vi is None else f"_{vi}")
            vs.append((f"{arch}_{i}", tmpl, year, f"{nm} {disp} Chassis"))
        CHASSIS[arch] = dict(template=f"{vp}_tank_chassis", name=f"{disp} Combat Vehicle", variants=vs, size=key)
        for rk, rv, rdisp in ROLES:
            ROLE_CHASSIS[f"hod_{key}_vehicle_{rk}_chassis"] = (arch, f"{vp}_tank_{rv}_chassis", rdisp)
    m = MODULES
    for size, vp in (("light", "light"), ("medium", "medium"), ("heavy", "heavy")):
        D = size.capitalize()
        m[f"hod_{size}_weapon_mount"] = (f"tank_{vp}_two_man_tank_turret", f"{D} Weapon Mount")
        m[f"hod_{size}_twin_mount"] = (f"tank_{vp}_three_man_tank_turret", f"{D} Twin Turret")
        m[f"hod_{size}_casemate"] = (f"tank_{vp}_fixed_superstructure_turret", f"{D} Casemate")
    m["hod_superheavy_weapon_mount"] = ("tank_super_heavy_three_man_tank_turret", "Super-Heavy Weapon Mount")
    m["hod_superheavy_battle_mount"] = ("tank_super_heavy_four_man_tank_turret", "Super-Heavy Battle Turret")
    for k, v, n in (("hod_repeating_blaster", "tank_heavy_machine_gun", "Repeating Blaster"),
                    ("hod_blaster_cannon", "tank_small_cannon", "Blaster Cannon"),
                    ("hod_twin_blaster_cannon", "tank_small_cannon_2", "Twin Blaster Cannon"),
                    ("hod_rapid_laser", "tank_auto_cannon", "Rapid-Fire Laser"),
                    ("hod_rapid_laser_2", "tank_auto_cannon_2", "Heavy Rapid-Fire Laser"),
                    ("hod_light_flak", "tank_anti_air_cannon", "Light Flak Turret"),
                    ("hod_light_flak_2", "tank_anti_air_cannon_2", "Twin Flak Turret"),
                    ("hod_mortar_launcher", "tank_close_support_gun", "Mortar Launcher"),
                    ("hod_light_ion_cannon", "tank_high_velocity_cannon", "Light Ion Cannon"),
                    ("hod_laser_cannon", "tank_medium_cannon", "Laser Cannon"),
                    ("hod_laser_cannon_2", "tank_medium_cannon_2", "Improved Laser Cannon"),
                    ("hod_ion_cannon", "tank_high_velocity_cannon_2", "Ion Cannon"),
                    ("hod_mass_driver", "tank_medium_howitzer", "Mass-Driver"),
                    ("hod_mass_driver_2", "tank_medium_howitzer_2", "Heavy Mass-Driver"),
                    ("hod_missile_pod", "tank_rocket_launcher", "Missile Pod"),
                    ("hod_missile_pod_2", "tank_rocket_launcher_2", "Heavy Missile Pod"),
                    ("hod_flak_battery", "tank_anti_air_cannon_3", "Flak Battery"),
                    ("hod_heavy_laser_cannon", "tank_heavy_cannon", "Heavy Laser Cannon"),
                    ("hod_heavy_laser_cannon_2", "tank_heavy_cannon_2", "Improved Heavy Laser Cannon"),
                    ("hod_turbolaser_cannon", "tank_heavy_cannon_3", "Mass-Driver Turbolaser"),
                    ("hod_ion_lance", "tank_high_velocity_cannon_3", "Ion Lance"),
                    ("hod_siege_cannon", "tank_heavy_howitzer", "Siege Cannon"),
                    ("hod_heavy_turbolaser", "tank_super_heavy_cannon", "Heavy Turbolaser"),
                    ("hod_tracks", "tank_bogie_suspension", "Tracks"),
                    ("hod_tracks_2", "tank_torsion_bar_suspension", "Reinforced Tracks"),
                    ("hod_walker_legs", "tank_interleaved_suspension", "Walker Legs"),
                    ("hod_repulsorlift", "tank_christie_suspension", "Repulsorlift"),
                    ("hod_repulsor_skids", "tank_wheeled_suspension", "Repulsor Skids"),
                    ("hod_fuel_cell_engine", "tank_gasoline_engine", "Fuel-Cell Engine"),
                    ("hod_fusion_engine", "tank_diesel_engine", "Fusion Engine"),
                    ("hod_power_relay_engine", "tank_petrol_electric_engine", "Power-Relay Drive"),
                    ("hod_hypermatter_engine", "tank_gas_turbine_engine", "Hypermatter Engine"),
                    ("hod_durasteel_plating", "tank_riveted_armor", "Durasteel Plating"),
                    ("hod_laminate_armor", "tank_welded_armor", "Laminate Armour"),
                    ("hod_quadanium_armor", "tank_cast_armor", "Quadanium Armour"),
                    ("hod_holonet_link_1", "tank_radio_1", "Comlink"),
                    ("hod_holonet_link_2", "tank_radio_2", "HoloNet Link"),
                    ("hod_holonet_link_3", "tank_radio_3", "Battle Network Link"),
                    ("hod_deflector_shield", "sloped_armor", "Deflector Shield"),
                    ("hod_targeting_computer", "stabilizer", "Targeting Computer"),
                    ("hod_smoke_screen", "smoke_launchers", "Smoke Screen"),
                    ("hod_power_cells", "extra_ammo_storage", "Extra Power Cells"),
                    ("hod_ablative_skirts", "armor_skirts", "Ablative Skirts"),
                    ("hod_dozer_scoop", "dozer_blade", "Dozer Scoop"),
                    ("hod_auto_loader", "auto_loader", "Cyclic Feed"),
                    ("hod_modular_maintenance", "easy_maintenance", "Modular Maintenance"),
                    ("hod_point_defence", "additional_machine_guns", "Point-Defence Blasters"),
                    ("hod_extended_cells", "expanded_fuel_tank", "Extended Power Cells"),
                    ("hod_anti_personnel_turret", "secondary_turret_hmg", "Anti-Personnel Turret"),
                    ("hod_secondary_blaster", "secondary_turret_small_cannon", "Secondary Blaster Turret")):
        m[k] = (v, n)
    # armour units: each size's tank / tank destroyer / SP artillery / SP flak, needs translated to our chassis
    for key, vp, disp in SIZES:
        unit(f"hod_{key}_armour", f"{vp}_armor", f"{disp} Armour", "chassis")
        unit(f"hod_{key}_destroyer", f"{vp}_tank_destroyer_brigade", f"{disp} Anti-Armour Vehicles", "chassis")
        unit(f"hod_{key}_artillery_vehicle", f"{vp}_sp_artillery_brigade", f"{disp} Artillery Vehicles", "chassis")
        unit(f"hod_{key}_flak_vehicle", f"{vp}_sp_anti_air_brigade", f"{disp} Flak Vehicles", "chassis")


def vehicles():
    c = ["armor"]
    ladder("hod_speeders", "vehicles", 1, [
        (0, 0, "Civilian Speeders", {}, {"unlock_eq": ["hod_speeder_equipment_1"], "unlock_units": ["hod_speeder_trooper"],
                                         "cats": ["motorized_equipment"]}),
        (1, 0, "Military Speeder Bikes", {}, {"unlock_eq": ["hod_speeder_equipment_2"], "cats": ["motorized_equipment"]}),
        (2, 0, "Armoured Speeders", {}, {"unlock_eq": ["hod_speeder_equipment_3"], "cats": ["motorized_equipment"]}),
        (3, 0, "Imperial Speeder Bikes", {}, {"unlock_eq": ["hod_speeder_equipment_4"], "cats": ["motorized_equipment"]}),
    ], c)
    first_mods = {"light": ["hod_light_weapon_mount", "hod_light_casemate", "hod_repeating_blaster", "hod_blaster_cannon",
                            "hod_tracks", "hod_fuel_cell_engine", "hod_durasteel_plating"],
                  "medium": ["hod_medium_weapon_mount", "hod_medium_casemate", "hod_laser_cannon", "hod_mass_driver"],
                  "heavy": ["hod_heavy_weapon_mount", "hod_heavy_casemate", "hod_heavy_laser_cannon", "hod_siege_cannon"],
                  "superheavy": ["hod_superheavy_weapon_mount", "hod_heavy_turbolaser"]}
    cat = {"light": "cat_light_armor", "medium": "cat_medium_armor", "heavy": "cat_heavy_armor", "superheavy": "cat_heavy_armor"}
    for row, (key, vp, disp) in enumerate(SIZES, 2):
        ch = CHASSIS[f"hod_{key}_vehicle_chassis"]
        prev = None
        for i, (vid, _t, year, name) in enumerate(ch["variants"]):
            era = 0 if year < 976 else (1 if year < 978 else (2 if year < 980 else 3))
            kw = dict(unlock_eq=[vid], cats=["armor", cat[key]], parent=prev)
            if i == 0:
                kw["unlock_units"] = [f"hod_{key}_armour", f"hod_{key}_destroyer", f"hod_{key}_artillery_vehicle",
                                      f"hod_{key}_flak_vehicle"]
                kw["unlock_modules"] = first_mods[key]
            prev = tech(f"hod_{key}_chassis_{i + 1}", "vehicles", row, era, 1 if (key == "medium" and era == 0) else 0,
                        name.replace("Chassis", "Vehicles"), **kw)
    def mods(prefix, row, entries):
        prev = None
        for i, (era, step, name, ms) in enumerate(entries, 1):
            prev = tech(f"{prefix}_{i}", "vehicles", row, era, step, name, cats=c, unlock_modules=ms, parent=prev)
    mods("hod_vehicle_weapons_light", 6, [(0, 1, "Rapid-Fire Lasers", ["hod_rapid_laser", "hod_light_flak", "hod_mortar_launcher"]),
                                           (1, 1, "Twin Blaster Cannons", ["hod_twin_blaster_cannon", "hod_light_ion_cannon", "hod_light_twin_mount"]),
                                           (2, 1, "Heavy Rapid-Fire Lasers", ["hod_rapid_laser_2", "hod_light_flak_2"])])
    mods("hod_vehicle_weapons_medium", 7, [(1, 2, "Ion Cannons", ["hod_ion_cannon", "hod_missile_pod", "hod_flak_battery", "hod_medium_twin_mount"]),
                                            (2, 2, "Improved Laser Cannons", ["hod_laser_cannon_2", "hod_mass_driver_2", "hod_missile_pod_2"])])
    mods("hod_vehicle_weapons_heavy", 8, [(2, 1, "Improved Heavy Laser Cannons", ["hod_heavy_laser_cannon_2", "hod_ion_lance", "hod_heavy_twin_mount"]),
                                           (3, 1, "Mass-Driver Turbolasers", ["hod_turbolaser_cannon", "hod_superheavy_battle_mount"])])
    mods("hod_vehicle_drives", 9, [(0, 1, "Repulsorlift Drives", ["hod_repulsorlift", "hod_repulsor_skids"]),
                                    (1, 1, "Walker Legs", ["hod_walker_legs"]),
                                    (2, 1, "Reinforced Tracks", ["hod_tracks_2"])])
    mods("hod_vehicle_engines", 10, [(0, 2, "Fusion Engines", ["hod_fusion_engine"]), (2, 0, "Power-Relay Drives", ["hod_power_relay_engine"]),
                                      (3, 0, "Hypermatter Engines", ["hod_hypermatter_engine"])])
    mods("hod_vehicle_armour", 11, [(1, 0, "Laminate Armour", ["hod_laminate_armor", "hod_ablative_skirts"]),
                                     (2, 2, "Quadanium Armour", ["hod_quadanium_armor"])])
    mods("hod_vehicle_systems", 12, [(0, 1, "Vehicle Comlinks", ["hod_holonet_link_1", "hod_smoke_screen", "hod_anti_personnel_turret", "hod_dozer_scoop"]),
                                      (1, 1, "Targeting Computers", ["hod_targeting_computer", "hod_power_cells", "hod_secondary_blaster", "hod_holonet_link_2"]),
                                      (2, 1, "Vehicle Deflector Shields", ["hod_deflector_shield", "hod_point_defence", "hod_extended_cells"]),
                                      (3, 1, "Battle Network Integration", ["hod_holonet_link_3", "hod_auto_loader", "hod_modular_maintenance"])])
    TECHS["hod_vehicle_systems_3"]["deps"].append("hod_shield_theory_2")


# ─────────────────────────────── STARFIGHTERS (plane designer) ───────────────────────────────
AIRFRAMES = OrderedDict()     # ours -> dict(template, variants[(id, template variant, year, name)])
ROLE_FRAMES = OrderedDict()   # ours -> (our archetype, vanilla role frame template, display)
PLANE_MODULES = OrderedDict()  # ours -> (vanilla template, display)


def air_designer():
    frames = [("hod_starfighter_airframe", "small_plane_airframe", "Starfighter", [(966, 1), (976, 2), (978, 3), (980, 4)]),
              ("hod_carrier_starfighter_airframe", "cv_small_plane_airframe", "Carrier Starfighter",
               [(976, 1), (978, 2), (980, 3)]),
              ("hod_gunship_airframe", "medium_plane_airframe", "Gunship", [(970, 1), (976, 2), (978, 3), (980, 4)]),
              ("hod_heavy_bomber_airframe", "large_plane_airframe", "Heavy Bomber", [(976, 1), (978, 2), (980, 3)])]
    for arch, tmpl, disp, tiers in frames:
        AIRFRAMES[arch] = dict(template=tmpl, name=f"{disp} Frame",
                               variants=[(f"{arch}_{i}", f"{tmpl}_{vi}", year, f"{['Old Republic', 'Military', 'Advanced', 'Imperial'][min(3, max(0, (year - 974) // 2))]} {disp}")
                                         for i, (year, vi) in enumerate(tiers, 1)])
    for ours, arch, tmpl, disp in (("hod_starfighter_attack_airframe", "hod_starfighter_airframe", "small_plane_cas_airframe", "Assault Starfighter"),
                                   ("hod_carrier_starfighter_attack_airframe", "hod_carrier_starfighter_airframe", "cv_small_plane_cas_airframe", "Carrier Assault Starfighter"),
                                   ("hod_starfighter_bomber_airframe", "hod_starfighter_airframe", "small_plane_naval_bomber_airframe", "Starfighter Bomber"),
                                   ("hod_carrier_starfighter_bomber_airframe", "hod_carrier_starfighter_airframe", "cv_small_plane_naval_bomber_airframe", "Carrier Starfighter Bomber"),
                                   ("hod_heavy_starfighter_airframe", "hod_gunship_airframe", "medium_plane_fighter_airframe", "Heavy Starfighter"),
                                   ("hod_recon_craft_airframe", "hod_gunship_airframe", "medium_plane_scout_plane_airframe", "Recon Craft"),
                                   ("hod_patrol_craft_airframe", "hod_heavy_bomber_airframe", "large_plane_maritime_patrol_plane_airframe", "Patrol Craft")):
        ROLE_FRAMES[ours] = (arch, tmpl, disp)
    pm = PLANE_MODULES
    sizes = [("1x", "", "Ion Engine"), ("2x", "twin_", "Twin Ion Engines"), ("3x", "triple_", "Triple Ion Engines"),
             ("4x", "quad_", "Quad Ion Engines"), ("6x", "capital_", "Heavy Sublight Drives")]
    for suf, pre, disp in sizes:
        for t in range(1, 5):
            pm[f"hod_{pre}ion_engine_{t}"] = (f"engine_{t}_{suf}", f"{disp} {['I', 'II', 'III', 'IV'][t - 1]}")
    for k, v, n in (("hod_light_lasers_2x", "light_mg_2x", "Twin Light Lasers"), ("hod_light_lasers_4x", "light_mg_4x", "Quad Light Lasers"),
                    ("hod_laser_cannons_2x", "heavy_mg_2x", "Twin Laser Cannons"), ("hod_laser_cannons_4x", "heavy_mg_4x", "Quad Laser Cannons"),
                    ("hod_heavy_laser_1x", "aircraft_cannon_1_1x", "Heavy Laser Cannon"), ("hod_heavy_laser_2x", "aircraft_cannon_1_2x", "Twin Heavy Laser Cannons"),
                    ("hod_ion_cannon_1x", "aircraft_cannon_2_1x", "Ion Cannon"), ("hod_ion_cannon_2x", "aircraft_cannon_2_2x", "Twin Ion Cannons"),
                    ("hod_heavy_ion_1x", "large_aircraft_cannon_1x", "Heavy Ion Cannon"), ("hod_heavy_ion_2x", "large_aircraft_cannon_2x", "Twin Heavy Ion Cannons"),
                    ("hod_proton_bombs", "bomb_locks", "Proton Bomb Racks"), ("hod_heavy_proton_bombs", "heavy_bomb_locks", "Heavy Proton Bomb Racks"),
                    ("hod_shaped_charges", "armor_piercing_bomb_locks", "Shaped Charge Bombs"), ("hod_concussion_rockets", "rocket_rails", "Concussion Rocket Rails"),
                    ("hod_light_bomb_bay", "small_bomb_bay", "Light Bomb Bay"), ("hod_ion_pods", "tank_buster_1", "Anti-Armour Ion Pods"),
                    ("hod_ion_pods_2", "tank_buster_2", "Heavy Anti-Armour Ion Pods"), ("hod_bomb_bay", "medium_bomb_bay", "Bomb Bay"),
                    ("hod_heavy_bomb_bay", "large_bomb_bay", "Heavy Bomb Bay"), ("hod_seismic_charges", "earthshaker_bomb_release", "Seismic Charges"),
                    ("hod_guided_bombs", "rocket_propelled_bombs", "Guided Proton Bombs"), ("hod_guided_bombs_2", "improved_rocket_propelled_bombs", "Smart Proton Bombs"),
                    ("hod_proton_torpedoes", "torpedo_mounting", "Proton Torpedoes"), ("hod_proton_torpedoes_2", "torpedo_mounting_2", "Improved Proton Torpedoes"),
                    ("hod_proton_torpedoes_3", "torpedo_mounting_3", "Heavy Proton Torpedoes"), ("hod_guided_missiles_air", "guided_anti_ship_missile", "Guided Concussion Missiles"),
                    ("hod_sensor_pod", "recon_camera", "Sensor Pod"), ("hod_mine_dispenser", "airdropped_mines", "Space Mine Dispenser"),
                    ("hod_light_deflector", "armor_plate_small", "Light Deflector Shield"), ("hod_power_cells_small", "fuel_tanks_small", "Extra Power Cells"),
                    ("hod_sealed_cells_small", "self_sealing_fuel_tanks_small", "Shielded Power Cells"), ("hod_cheap_frame_small", "non_strategic_materials_small", "Mass-Production Frame"),
                    ("hod_hyperdrive_ring", "drop_tanks", "Hyperdrive Ring"), ("hod_repulsor_brakes", "dive_brakes_small", "Repulsor Brakes"),
                    ("hod_medium_deflector", "armor_plate_medium", "Deflector Shield"), ("hod_power_cells_medium", "fuel_tanks_medium", "Extra Power Cells"),
                    ("hod_sealed_cells_medium", "self_sealing_fuel_tanks_medium", "Shielded Power Cells"), ("hod_cheap_frame_medium", "non_strategic_materials_medium", "Mass-Production Frame"),
                    ("hod_heavy_deflector", "armor_plate_large", "Heavy Deflector Shield"), ("hod_power_cells_large", "fuel_tanks_large", "Extra Power Cells"),
                    ("hod_sealed_cells_large", "self_sealing_fuel_tanks_large", "Shielded Power Cells"), ("hod_cheap_frame_large", "non_strategic_materials_large", "Mass-Production Frame"),
                    ("hod_bomb_targeting_1", "bomb_sights_1", "Bombing Computer"), ("hod_bomb_targeting_2", "bomb_sights_2", "Advanced Bombing Computer"),
                    ("hod_navicomputer_1", "radio_navigation_1", "Navicomputer"), ("hod_navicomputer_2", "radio_navigation_2", "Advanced Navicomputer"),
                    ("hod_ground_scanner_1", "air_ground_radar_1", "Ground Scanner"), ("hod_ground_scanner_2", "air_ground_radar_2", "Advanced Ground Scanner"),
                    ("hod_target_scanner_1", "air_air_radar_1", "Target Scanner"), ("hod_target_scanner_2", "air_air_radar_2", "Advanced Target Scanner"),
                    ("hod_tail_gunner_light", "lmg_defense_turret", "Tail Blaster"), ("hod_tail_gunner_heavy", "hmg_defense_turret", "Tail Laser Turret"),
                    ("hod_tail_gunner_cannon", "cannon_defense_turret", "Tail Ion Turret"), ("hod_tail_gunner_light_2x", "lmg_defense_turret_2x", "Twin Tail Blasters"),
                    ("hod_tail_gunner_heavy_2x", "hmg_defense_turret_2x", "Twin Tail Laser Turrets"), ("hod_tail_gunner_cannon_2x", "cannon_defense_turret_2x", "Twin Tail Ion Turrets")):
        pm[k] = (v, n)
    for uid, tmpl, name, need in (("hod_starfighter", "fighter", "Starfighters", "hod_starfighter_airframe"),
                                  ("hod_carrier_starfighter", "cv_fighter", "Carrier Starfighters", "hod_carrier_starfighter_airframe"),
                                  ("hod_assault_starfighter", "cas", "Assault Starfighters", "hod_starfighter_attack_airframe"),
                                  ("hod_carrier_assault_starfighter", "cv_cas", "Carrier Assault Starfighters", "hod_carrier_starfighter_attack_airframe"),
                                  ("hod_starfighter_bomber", "nav_bomber", "Starfighter Bombers", "hod_starfighter_bomber_airframe"),
                                  ("hod_carrier_starfighter_bomber", "cv_nav_bomber", "Carrier Starfighter Bombers", "hod_carrier_starfighter_bomber_airframe"),
                                  ("hod_gunship", "tac_bomber", "Gunships", "hod_gunship_airframe"),
                                  ("hod_heavy_starfighter", "heavy_fighter", "Heavy Starfighters", "hod_heavy_starfighter_airframe"),
                                  ("hod_recon_craft", "scout_plane", "Recon Craft", "hod_recon_craft_airframe"),
                                  ("hod_heavy_bomber", "strat_bomber", "Heavy Bombers", "hod_heavy_bomber_airframe"),
                                  ("hod_patrol_craft", "maritime_patrol_plane", "Patrol Craft", "hod_patrol_craft_airframe"),
                                  ("hod_dropship", "transport_plane", "Dropships", "hod_dropship_equipment")):
        unit(uid, tmpl, name, {need: 1})
    archetype("hod_dropship_equipment", "transport_plane_equipment", "Dropships", {}, {"aluminium": 1}, picture="archetype_transport_plane_equipment")
    variant("hod_dropship_equipment", "hod_dropship_equipment_1", 976, "Military Dropships")
    variant("hod_dropship_equipment", "hod_dropship_equipment_2", 980, "Imperial Dropships", parent="hod_dropship_equipment_1")


def air():
    c = ["air_equipment"]
    first = {"hod_starfighter_airframe": (["hod_starfighter", "hod_assault_starfighter", "hod_starfighter_bomber"],
                                          ["hod_ion_engine_1", "hod_light_lasers_2x", "hod_proton_bombs", "hod_proton_torpedoes"], ["light_fighter"]),
             "hod_carrier_starfighter_airframe": (["hod_carrier_starfighter", "hod_carrier_assault_starfighter", "hod_carrier_starfighter_bomber"],
                                                  [], ["naval_air"]),
             "hod_gunship_airframe": (["hod_gunship", "hod_heavy_starfighter", "hod_recon_craft"],
                                      ["hod_twin_ion_engine_1", "hod_triple_ion_engine_1", "hod_bomb_bay", "hod_sensor_pod"], ["tactical_bomber"]),
             "hod_heavy_bomber_airframe": (["hod_heavy_bomber", "hod_patrol_craft"],
                                           ["hod_quad_ion_engine_1", "hod_capital_ion_engine_1", "hod_heavy_bomb_bay"], ["cat_strategic_bomber"])}
    for row, (arch, d) in enumerate(AIRFRAMES.items(), 1):
        units_, mods_, cats = first[arch]
        prev = None
        for i, (vid, _t, year, name) in enumerate(d["variants"]):
            era = 0 if year < 976 else (1 if year < 978 else (2 if year < 980 else 3))
            kw = dict(unlock_eq=[vid], cats=c + cats, parent=prev)
            if i == 0:
                kw.update(unlock_units=units_, unlock_modules=mods_)
                if arch == "hod_carrier_starfighter_airframe":
                    kw["deps"] = ["hod_starfighter_airframe_tech_2"]
            prev = tech(f"{arch}_tech_{i + 1}", "air", row, era, 0, name + "s", **kw)
    def mods(prefix, row, entries, cats=c):
        prev = None
        for i, (era, step, name, ms) in enumerate(entries, 1):
            prev = tech(f"{prefix}_{i}", "air", row, era, step, name, cats=cats, unlock_modules=ms, parent=prev)
    mods("hod_air_engines", 5, [(0, 1, "Improved Ion Engines", ["hod_ion_engine_2", "hod_twin_ion_engine_2", "hod_triple_ion_engine_2", "hod_quad_ion_engine_2", "hod_capital_ion_engine_2"]),
                                (1, 1, "Military Ion Engines", ["hod_ion_engine_3", "hod_twin_ion_engine_3", "hod_triple_ion_engine_3", "hod_quad_ion_engine_3", "hod_capital_ion_engine_3"]),
                                (3, 1, "Imperial Ion Engines", ["hod_ion_engine_4", "hod_twin_ion_engine_4", "hod_triple_ion_engine_4", "hod_quad_ion_engine_4", "hod_capital_ion_engine_4"])])
    mods("hod_air_guns", 6, [(0, 2, "Starfighter Laser Cannons", ["hod_light_lasers_4x", "hod_laser_cannons_2x", "hod_tail_gunner_light"]),
                             (1, 2, "Heavy Starfighter Lasers", ["hod_laser_cannons_4x", "hod_heavy_laser_1x", "hod_tail_gunner_heavy", "hod_tail_gunner_light_2x"]),
                             (2, 2, "Starfighter Ion Cannons", ["hod_heavy_laser_2x", "hod_ion_cannon_1x", "hod_ion_cannon_2x", "hod_tail_gunner_heavy_2x"]),
                             (3, 2, "Heavy Ion Cannons", ["hod_heavy_ion_1x", "hod_heavy_ion_2x", "hod_tail_gunner_cannon", "hod_tail_gunner_cannon_2x"])])
    mods("hod_air_ordnance", 7, [(1, 0, "Concussion Rockets", ["hod_concussion_rockets", "hod_heavy_proton_bombs", "hod_light_bomb_bay", "hod_proton_torpedoes_2"]),
                                 (2, 0, "Anti-Armour Ion Pods", ["hod_ion_pods", "hod_shaped_charges", "hod_guided_bombs", "hod_proton_torpedoes_3"]),
                                 (3, 0, "Smart Ordnance", ["hod_ion_pods_2", "hod_guided_bombs_2", "hod_guided_missiles_air", "hod_seismic_charges", "hod_mine_dispenser"])])
    mods("hod_air_systems", 8, [(0, 2, "Starfighter Navicomputers", ["hod_navicomputer_1", "hod_power_cells_small", "hod_power_cells_medium", "hod_power_cells_large", "hod_cheap_frame_small", "hod_cheap_frame_medium", "hod_cheap_frame_large"]),
                                (1, 2, "Hyperdrive Rings", ["hod_hyperdrive_ring", "hod_repulsor_brakes", "hod_bomb_targeting_1", "hod_target_scanner_1", "hod_ground_scanner_1"]),
                                (2, 1, "Starfighter Deflector Shields", ["hod_light_deflector", "hod_medium_deflector", "hod_heavy_deflector", "hod_sealed_cells_small", "hod_sealed_cells_medium", "hod_sealed_cells_large"]),
                                (3, 2, "Advanced Avionics", ["hod_navicomputer_2", "hod_bomb_targeting_2", "hod_target_scanner_2", "hod_ground_scanner_2"])])
    TECHS["hod_air_systems_3"]["deps"].append("hod_shield_theory_2")
    tech("hod_dropships_1", "air", 9, 1, 1, "Dropships", cats=c, unlock_units=["hod_dropship"], unlock_eq=["hod_dropship_equipment_1"],
         deps=["hod_gunship_airframe_tech_2"])
    tech("hod_dropships_2", "air", 9, 3, 1, "Imperial Dropships", cats=c, unlock_eq=["hod_dropship_equipment_2"])


# ─────────────────────────────── FLEET (ship designer) ───────────────────────────────
HULLS = OrderedDict()          # ours -> dict(template archetype, variants[(id, template variant, year, name)])
SHIP_MODULES = OrderedDict()   # ours -> (vanilla template, display)


def fleet_designer():
    roman = ["I", "II", "III", "IV"]
    for arch, tmpl, disp, tiers in (("hod_corvette_hull", "ship_hull_light", "Corvette", [(964, 1), (976, 2), (978, 3), (980, 4)]),
                                    ("hod_cruiser_hull", "ship_hull_cruiser", "Cruiser", [(964, 1), (976, 2), (978, 3), (980, 4)]),
                                    ("hod_capital_hull", "ship_hull_heavy", "Star Destroyer", [(970, 1), (976, 2), (978, 3), (980, 4)]),
                                    ("hod_dreadnought_hull", "ship_hull_super_heavy", "Dreadnought", [(978, None)]),
                                    ("hod_carrier_hull", "ship_hull_carrier", "Carrier", [(976, 1), (978, 2), (980, 3)]),
                                    ("hod_raider_hull", "ship_hull_submarine", "Stealth Raider", [(970, 1), (976, 2), (978, 3), (980, 4)])):
        vs = []
        for i, (year, vi) in enumerate(tiers, 1):
            vt = "ship_hull_super_heavy_1" if vi is None else f"{tmpl}_{vi}"
            vs.append((f"{arch}_{i}", vt, year, f"{disp} Hull {roman[i - 1]}"))
        HULLS[arch] = dict(template="ship_hull_heavy" if tmpl == "ship_hull_super_heavy" else tmpl, name=f"{disp} Hull", variants=vs)
    sm = SHIP_MODULES
    for t in range(1, 5):
        r = roman[t - 1]
        for k, v, n in ((f"hod_light_turbolasers_{t}", f"ship_light_battery_{t}", f"Light Turbolaser Battery {r}"),
                        (f"hod_dual_lasers_{t}", f"dp_light_battery_{t}", f"Dual-Purpose Laser Battery {r}"),
                        (f"hod_medium_turbolasers_{t}", f"ship_medium_battery_{t}", f"Turbolaser Battery {r}"),
                        (f"hod_heavy_turbolasers_{t}", f"ship_heavy_battery_{t}", f"Heavy Turbolaser Battery {r}"),
                        (f"hod_point_defence_{t}", f"ship_anti_air_{t}", f"Point-Defence Lasers {r}"),
                        (f"hod_targeting_array_{t}", f"ship_fire_control_system_{t - 1}", f"Targeting Array {r}"),
                        (f"hod_ship_sensors_{t}", f"ship_radar_{t}", f"Sensor Suite {r}"),
                        (f"hod_corvette_drive_{t}", f"light_ship_engine_{t}", f"Corvette Sublight Drive {r}"),
                        (f"hod_cruiser_drive_{t}", f"cruiser_ship_engine_{t}", f"Cruiser Sublight Drive {r}"),
                        (f"hod_capital_drive_{t}", f"heavy_ship_engine_{t}", f"Capital Sublight Drive {r}"),
                        (f"hod_carrier_drive_{t}", f"carrier_ship_engine_{t}", f"Carrier Sublight Drive {r}"),
                        (f"hod_raider_drive_{t}", f"sub_ship_engine_{t}", f"Raider Sublight Drive {r}"),
                        (f"hod_torpedo_launchers_{t}", f"ship_torpedo_{t}", f"Proton Torpedo Launchers {r}"),
                        (f"hod_raider_torpedoes_{t}", f"ship_torpedo_sub_{t}", f"Raider Torpedo Tubes {r}"),
                        (f"hod_ion_pulse_charges_{t}", f"ship_depth_charge_{t}", f"Ion Pulse Charges {r}"),
                        (f"hod_cloak_detectors_{t}", f"ship_sonar_{t}", f"Cloak Detectors {r}"),
                        (f"hod_cruiser_armour_{t}", f"ship_armor_cruiser_{t}", f"Cruiser Shields and Armour {r}")):
            sm[k] = (v, n)
    for t in range(1, 4):
        r = roman[t - 1]
        sm[f"hod_capital_armour_{t}"] = (f"ship_armor_bb_{t}", f"Capital Shields and Armour {r}")
        sm[f"hod_strike_armour_{t}"] = (f"ship_armor_bc_{t}", f"Strike Shields and Armour {r}")
    for k, v, n in (("hod_quad_turbolasers", "ship_super_heavy_battery_1", "Quad Heavy Turbolasers"),
                    ("hod_point_defence_secondaries_1", "ship_secondaries_1", "Secondary Laser Batteries"),
                    ("hod_point_defence_secondaries_2", "ship_secondaries_2", "Improved Secondary Lasers"),
                    ("hod_dreadnought_armour", "ship_armor_shbb", "Dreadnought Shields and Armour"),
                    ("hod_carrier_armour", "ship_armor_carrier_deck", "Hangar Deck Shielding"),
                    ("hod_hangar_bay", "ship_deck_space", "Hangar Bay"), ("hod_large_hangar_bay", "big_ship_deck_space", "Large Hangar Bay"),
                    ("hod_space_mine_layer", "ship_mine_layer_1", "Space Mine Layer"), ("hod_mine_sweeper", "ship_mine_sweeper_1", "Mine Sweeper"),
                    ("hod_extended_supplies", "ship_extra_fuel_tank", "Extended Supply Holds"),
                    ("hod_cloaking_field_1", "ship_sub_snorkel_1", "Cloaking Field"), ("hod_cloaking_field_2", "ship_sub_snorkel_2", "Improved Cloaking Field"),
                    ("hod_sensor_baffles", "ship_anechoic_tile", "Sensor Baffles"), ("hod_raider_deck_gun", "ship_light_battery_sub", "Raider Laser Turret")):
        sm[k] = (v, n)
    for uid, tmpl, name in (("hod_corvette", "destroyer", "Corvette"), ("hod_frigate", "light_cruiser", "Frigate"),
                            ("hod_cruiser", "heavy_cruiser", "Cruiser"), ("hod_star_destroyer", "battleship", "Star Destroyer"),
                            ("hod_strike_cruiser", "battle_cruiser", "Strike Cruiser"), ("hod_dreadnought", "battleship", "Dreadnought"),
                            ("hod_carrier", "carrier", "Carrier"), ("hod_stealth_raider", "submarine", "Stealth Raider")):
        unit(uid, tmpl, name, "hull")


def fleet():
    c = ["naval_equipment"]
    first = {"hod_corvette_hull": (["hod_corvette"], ["hod_light_turbolasers_1", "hod_point_defence_1", "hod_corvette_drive_1", "hod_torpedo_launchers_1", "hod_ion_pulse_charges_1", "hod_cloak_detectors_1", "hod_space_mine_layer", "hod_mine_sweeper"], ["dd_tech"]),
             "hod_cruiser_hull": (["hod_frigate", "hod_cruiser"], ["hod_medium_turbolasers_1", "hod_dual_lasers_1", "hod_cruiser_drive_1", "hod_cruiser_armour_1", "hod_targeting_array_1", "hod_point_defence_secondaries_1"], ["ca_tech"]),
             "hod_capital_hull": (["hod_star_destroyer", "hod_strike_cruiser"], ["hod_heavy_turbolasers_1", "hod_capital_drive_1", "hod_capital_armour_1", "hod_strike_armour_1"], ["bb_tech"]),
             "hod_dreadnought_hull": (["hod_dreadnought"], ["hod_quad_turbolasers", "hod_dreadnought_armour"], ["shbb_tech"]),
             "hod_carrier_hull": (["hod_carrier"], ["hod_hangar_bay", "hod_large_hangar_bay", "hod_carrier_drive_1", "hod_carrier_armour"], ["cv_tech"]),
             "hod_raider_hull": (["hod_stealth_raider"], ["hod_raider_drive_1", "hod_raider_torpedoes_1", "hod_raider_deck_gun", "hod_cloaking_field_1"], ["ss_tech"])}
    for row, (arch, d) in enumerate(HULLS.items(), 1):
        units_, mods_, cats = first[arch]
        prev = None
        for i, (vid, _t, year, name) in enumerate(d["variants"]):
            era = 0 if year < 976 else (1 if year < 978 else (2 if year < 980 else 3))
            kw = dict(unlock_eq=[vid], cats=c + cats, parent=prev)
            if i == 0:
                kw.update(unlock_units=units_, unlock_modules=mods_)
            if arch == "hod_dreadnought_hull":
                kw["deps"] = ["hod_capital_hull_tech_3"]
            prev = tech(f"{arch}_tech_{i + 1}", "fleet", row, era, 0, name.replace("Hull", "Class").replace(" I", " I").strip(), **kw)
    def mods(prefix, row, entries):
        prev = None
        for i, (era, step, name, ms) in enumerate(entries, 1):
            prev = tech(f"{prefix}_{i}", "fleet", row, era, step, name, cats=c + ["ship_modules_tech"], unlock_modules=ms, parent=prev)
    tiers = lambda t, *keys: [f"hod_{k}_{t}" for k in keys]
    mods("hod_ship_weapons", 7, [(0, 2, "Improved Turbolasers", tiers(2, "light_turbolasers", "medium_turbolasers", "heavy_turbolasers", "dual_lasers")),
                                 (1, 2, "Military Turbolasers", tiers(3, "light_turbolasers", "medium_turbolasers", "heavy_turbolasers", "dual_lasers") + ["hod_point_defence_secondaries_2"]),
                                 (3, 2, "Imperial Turbolasers", tiers(4, "light_turbolasers", "medium_turbolasers", "heavy_turbolasers", "dual_lasers"))])
    mods("hod_ship_defence", 8, [(0, 1, "Improved Point-Defence", tiers(2, "point_defence", "cruiser_armour") + ["hod_capital_armour_2", "hod_strike_armour_2"]),
                                 (1, 1, "Ray-Shielded Hulls", tiers(3, "point_defence", "cruiser_armour") + ["hod_capital_armour_3", "hod_strike_armour_3"]),
                                 (2, 1, "Imperial Point-Defence", tiers(4, "point_defence", "cruiser_armour"))])
    TECHS["hod_ship_defence_2"]["deps"].append("hod_shield_theory_2")
    mods("hod_ship_drives", 9, [(0, 0, "Improved Sublight Drives", tiers(2, "corvette_drive", "cruiser_drive", "capital_drive", "carrier_drive", "raider_drive")),
                                (1, 0, "Military Sublight Drives", tiers(3, "corvette_drive", "cruiser_drive", "capital_drive", "carrier_drive", "raider_drive") + ["hod_extended_supplies"]),
                                (3, 0, "Imperial Sublight Drives", tiers(4, "corvette_drive", "cruiser_drive", "capital_drive", "carrier_drive", "raider_drive"))])
    mods("hod_ship_systems", 10, [(0, 2, "Targeting Arrays", ["hod_targeting_array_2", "hod_ship_sensors_1"]),
                                  (1, 2, "Fleet Sensor Suites", ["hod_targeting_array_3", "hod_ship_sensors_2"]),
                                  (2, 2, "Advanced Targeting", ["hod_targeting_array_4", "hod_ship_sensors_3"]),
                                  (3, 2, "Imperial Sensor Networks", ["hod_ship_sensors_4"])])
    mods("hod_ship_torpedoes", 11, [(0, 1, "Improved Torpedo Launchers", tiers(2, "torpedo_launchers", "raider_torpedoes")),
                                    (1, 1, "Heavy Torpedo Launchers", tiers(3, "torpedo_launchers", "raider_torpedoes")),
                                    (3, 1, "Imperial Torpedo Launchers", tiers(4, "torpedo_launchers", "raider_torpedoes"))])
    mods("hod_ship_stealth", 12, [(0, 2, "Raider Countermeasures", tiers(2, "ion_pulse_charges", "cloak_detectors")),
                                  (1, 1, "Cloaking Fields", ["hod_cloaking_field_2", "hod_sensor_baffles"] + tiers(3, "ion_pulse_charges", "cloak_detectors")),
                                  (2, 2, "Advanced Cloak Detection", tiers(4, "ion_pulse_charges", "cloak_detectors"))])


# ─────────────────────────────── CLONES + DROIDS (faction tabs, behind access techs) ───────────────────────────────
def faction_equipment():
    s = lambda **k: k
    archetype("hod_clone_armor_equipment", "infantry_equipment", "Clone Trooper Armour",
              s(soft_attack=4, hard_attack=0.7, ap_attack=2, defense=24, breakthrough=3, reliability=0.95, maximum_speed=4,
                build_cost_ic=0.6), {"steel": 2}, picture="archetype_infantry_equipment")
    prev = None
    for i, (year, name, st) in enumerate(((970, "Kaminoan Prototype Armour", {}),
                                          (976, "Phase I Clone Armour", s(soft_attack=4.8, ap_attack=3, defense=27, breakthrough=3.5)),
                                          (978, "Phase II Clone Armour", s(soft_attack=5.8, ap_attack=4, defense=30, breakthrough=4.2, build_cost_ic=0.68)),
                                          (980, "Improved Phase II Armour", s(soft_attack=6.8, ap_attack=5.2, defense=33, breakthrough=4.8, build_cost_ic=0.75))), 1):
        prev = variant("hod_clone_armor_equipment", f"hod_clone_armor_equipment_{i}", year, name, st, parent=prev)
    for arch, name, base, res, tiers in (
        ("hod_b1_equipment", "B1 Battle Droids",
         s(soft_attack=2.6, hard_attack=0.4, ap_attack=1, defense=16, breakthrough=1.6, reliability=0.85, maximum_speed=4, build_cost_ic=0.42),
         {"steel": 2},
         [(970, "B1 Battle Droids", {}), (976, "Improved B1 Battle Droids", s(soft_attack=3.2, defense=18, breakthrough=2)),
          (978, "B1 Heavy Battle Droids", s(soft_attack=3.9, defense=20, breakthrough=2.4)),
          (980, "B1 Late-War Battle Droids", s(soft_attack=4.5, defense=22, breakthrough=2.8))]),
        ("hod_b2_equipment", "B2 Super Battle Droids",
         s(soft_attack=4.8, hard_attack=1, ap_attack=3, defense=26, breakthrough=4, armor_value=2, hardness=0.2, reliability=0.9,
           maximum_speed=3.5, build_cost_ic=0.9), {"steel": 3},
         [(976, "B2 Super Battle Droids", {}), (978, "B2-HA Super Battle Droids", s(soft_attack=5.8, ap_attack=4, breakthrough=4.8)),
          (980, "B2 Rocket Droids", s(soft_attack=6.8, ap_attack=5, breakthrough=5.6))]),
        ("hod_bx_equipment", "BX Commando Droids",
         s(soft_attack=5, hard_attack=0.9, ap_attack=3, defense=24, breakthrough=4.5, reliability=0.9, maximum_speed=5, build_cost_ic=1.0),
         {"steel": 2},
         [(976, "BX Commando Droids", {}), (980, "Advanced BX Commando Droids", s(soft_attack=6.2, breakthrough=5.6, defense=27))]),
        ("hod_droideka_equipment", "Droidekas",
         s(soft_attack=6, hard_attack=2, ap_attack=6, defense=30, breakthrough=3, armor_value=4, hardness=0.4, reliability=0.85,
           maximum_speed=3, build_cost_ic=2.5), {"steel": 2, "tungsten": 1},
         [(970, "Droidekas", {}), (978, "Droideka Series II", s(soft_attack=7.5, defense=36, ap_attack=8))])):
        archetype(arch, "infantry_equipment", name, base, res, picture="archetype_infantry_equipment")
        prev = None
        for i, (year, vname, st) in enumerate(tiers, 1):
            prev = variant(arch, f"{arch}_{i}", year, vname, st, parent=prev)
    # units: clones man well, droids need very little manpower
    unit("hod_clone_trooper", "infantry", "Clone Troopers", {"hod_clone_armor_equipment": 100},
         "Clone soldiers bred and trained on Kamino: disciplined, uniform, and loyal to the chain of command.",
         {"max_organisation": 65, "default_morale": 0.35})
    unit("hod_arc_trooper", "infantry", "ARC Troopers", {"hod_clone_armor_equipment": 100, "hod_jetpack_equipment": 10},
         "Advanced Recon Commandos: elite clones trained for independent action.", {"max_organisation": 70, "training_time": 140})
    unit("hod_clone_commando", "marine", "Clone Commandos", {"hod_clone_armor_equipment": 100, "hod_support_equipment": 20},
         "Four-man squads in Katarn armour, built for sabotage and assaults behind the lines.")
    unit("hod_b1_droid", "infantry", "B1 Battle Droids", {"hod_b1_equipment": 120},
         "Mass-produced battle droids: cheap, numerous, and needing no recruits.",
         {"manpower": 150, "max_organisation": 40, "training_time": 45, "default_morale": 0.2})
    unit("hod_b2_droid", "infantry", "B2 Super Battle Droids", {"hod_b2_equipment": 80},
         "Armoured super battle droids with built-in wrist blasters.",
         {"manpower": 100, "max_organisation": 45, "training_time": 60})
    unit("hod_bx_droid", "infantry", "BX Commando Droids", {"hod_bx_equipment": 100},
         "Fast, agile commando droids for raids and infiltration.", {"manpower": 100, "max_organisation": 55})
    unit("hod_magnaguard", "infantry", "IG-100 MagnaGuards", {"hod_bx_equipment": 100, "hod_support_equipment": 20},
         "Bodyguard droids armed with electrostaffs, trained in combat against Jedi.", {"manpower": 100, "max_organisation": 60})
    unit("hod_droideka", "anti_tank", "Droideka Company", {"hod_droideka_equipment": 24},
         "Shielded destroyer droids that roll into position and pin down infantry.", {"manpower": 50})


def clones():
    c = ["infantry_weapons", "hod_clone"]
    ladder("hod_clone_armour", "clone", 1, [
        (0, 1, "Kaminoan Prototypes", {}, {"unlock_eq": ["hod_clone_armor_equipment_1"], "unlock_units": ["hod_clone_trooper"],
                                           "deps": ["access_kamino_cloning"]}),
        (1, 0, "Phase I Clone Armour", {}, {"unlock_eq": ["hod_clone_armor_equipment_2"]}),
        (2, 0, "Phase II Clone Armour", {}, {"unlock_eq": ["hod_clone_armor_equipment_3"]}),
        (3, 0, "Improved Phase II Armour", {}, {"unlock_eq": ["hod_clone_armor_equipment_4"]}),
    ], c)
    tech("hod_arc_troopers", "clone", 2, 1, 1, "ARC Troopers", cats=c, unlock_units=["hod_arc_trooper"], deps=["access_kamino_cloning", "hod_jump_troopers"])
    tech("hod_arc_troopers_2", "clone", 2, 2, 1, "ARC Field Command", cats=c, extra="hod_arc_trooper = { breakthrough = 0.1 max_organisation = 5 }")
    tech("hod_clone_commandos", "clone", 3, 1, 2, "Clone Commandos", cats=c, unlock_units=["hod_clone_commando"], deps=["access_kamino_cloning"])
    tech("hod_clone_commandos_2", "clone", 3, 3, 0, "Katarn Armour", cats=c, extra="hod_clone_commando = { soft_attack = 0.1 defense = 0.1 }")
    ladder("hod_growth_acceleration", "clone", 4, [
        (0, 0, "Growth Acceleration", {"monthly_population": 0.05}, {"deps": ["access_kamino_cloning"]}),
        (1, 1, "Expanded Cloning Vats", {"monthly_population": 0.1, "recruitable_population_factor": 0.05}),
        (2, 1, "Accelerated Clone Batches", {"monthly_population": 0.1, "recruitable_population_factor": 0.05}),
    ], c)
    ladder("hod_flash_training", "clone", 5, [
        (0, 2, "Flash Training", {"training_time_army_factor": -0.05}, {"deps": ["access_kamino_cloning"]}),
        (1, 2, "Learning Modules", {"training_time_army_factor": -0.05},
         {"extra": "hod_clone_trooper = { max_organisation = 5 }"}),
        (2, 2, "Veteran Clone Cadres", {"training_time_army_factor": -0.05},
         {"extra": "hod_clone_trooper = { soft_attack = 0.05 defense = 0.05 }"}),
    ], c)


def droids():
    c = ["infantry_weapons", "hod_droid"]
    def line(prefix, row, arch, steps, unit_ids):
        ids = []
        for i, (era, step, name) in enumerate(steps, 1):
            kw = dict(unlock_eq=[f"{arch}_{i}"], cats=c)
            if i == 1:
                kw.update(unlock_units=unit_ids, deps=["access_droid_foundries"])
            ids.append(tech(f"{prefix}_{i}", "droid", row, era, step, name, **kw))
        return ids
    line("hod_b1_droids", 1, "hod_b1_equipment", [(0, 1, "B1 Battle Droids"), (1, 0, "Improved B1 Programming"),
                                                  (2, 0, "B1 Heavy Battle Droids"), (3, 0, "Late-War B1 Droids")], ["hod_b1_droid"])
    line("hod_b2_droids", 2, "hod_b2_equipment", [(1, 1, "B2 Super Battle Droids"), (2, 1, "B2-HA Super Battle Droids"),
                                                  (3, 1, "B2 Rocket Droids")], ["hod_b2_droid"])
    line("hod_bx_droids", 3, "hod_bx_equipment", [(1, 2, "BX Commando Droids"), (3, 2, "Advanced BX Droids")], ["hod_bx_droid"])
    tech("hod_magnaguards", "droid", 4, 1, 2, "IG-100 MagnaGuards", cats=c, unlock_units=["hod_magnaguard"],
         deps=["access_droid_foundries", "hod_bx_droids_1"])
    line("hod_droidekas", 5, "hod_droideka_equipment", [(0, 2, "Droidekas"), (2, 2, "Droideka Series II")], ["hod_droideka"])
    ladder("hod_tactical_droids", "droid", 6, [
        (0, 0, "Tactical Droids", {"planning_speed": 0.05}, {"deps": ["access_droid_foundries"]}),
        (1, 1, "T-Series Tactical Droids", {"planning_speed": 0.05, "max_planning": 0.05}),
        (2, 1, "Super Tactical Droids", {"planning_speed": 0.05, "max_planning": 0.05}),
    ], c)
    ladder("hod_droid_production", "droid", 7, [
        (0, 0, "Droid Foundries", {"industrial_capacity_factory": 0.03}, {"deps": ["access_droid_foundries"]}),
        (1, 0, "Mass Droid Production", {"industrial_capacity_factory": 0.03}),
        (2, 0, "Automated Droid Factories", {"industrial_capacity_factory": 0.04}),
    ], c)


# ─────────────────────────────── INFANTRY ───────────────────────────────
def infantry():
    c = ["infantry_weapons"]
    eq = lambda *v: {"unlock_eq": list(v)}
    ladder("hod_blasters", "infantry", 1, [
        (0, 0, "Old Republic Blasters", {}, dict(eq("hod_blaster_equipment_1"), unlock_units=["hod_trooper", "hod_militia"])),
        (0, 2, "Standard Blaster Rifles", {}, eq("hod_blaster_equipment_2")),
        (1, 0, "Military Blaster Rifles", {}, eq("hod_blaster_equipment_3")),
        (2, 0, "Advanced Blaster Rifles", {}, eq("hod_blaster_equipment_4")),
        (3, 0, "Imperial Blaster Rifles", {}, eq("hod_blaster_equipment_5")),
    ], c)
    tech("hod_heavy_blasters_1", "infantry", 2, 1, 1, "Repeating Blasters", cats=c, parent="hod_blasters_3",
         unlock_eq=["hod_blaster_equipment_3_heavy"], unlock_units=["hod_heavy_trooper"])
    tech("hod_heavy_blasters_2", "infantry", 2, 2, 1, "Advanced Repeating Blasters", cats=c, unlock_eq=["hod_blaster_equipment_4_heavy"])
    tech("hod_heavy_blasters_3", "infantry", 2, 3, 1, "Imperial Repeating Blasters", cats=c, unlock_eq=["hod_blaster_equipment_5_heavy"])
    tech("hod_precision_blasters_1", "infantry", 3, 1, 2, "Long-Range Blaster Rifles", cats=c, parent="hod_blasters_3",
         unlock_eq=["hod_blaster_equipment_3_precision"])
    tech("hod_precision_blasters_2", "infantry", 3, 2, 2, "Advanced Marksman Rifles", cats=c, unlock_eq=["hod_blaster_equipment_4_precision"])
    tech("hod_precision_blasters_3", "infantry", 3, 3, 2, "Imperial Marksman Rifles", cats=c, unlock_eq=["hod_blaster_equipment_5_precision"])
    ladder("hod_body_armour", "infantry", 4, [
        (0, 1, "Padded Armour Weave", {}, {"extra": "category_all_infantry = { defense = 0.03 }"}),
        (1, 1, "Plastoid Body Armour", {}, {"extra": "category_all_infantry = { defense = 0.05 max_strength = 0.05 }"}),
        (2, 1, "Composite Armour Plates", {}, {"extra": "category_all_infantry = { defense = 0.05 max_strength = 0.05 }"}),
        (3, 1, "Imperial Armour Standards", {}, {"extra": "category_all_infantry = { defense = 0.05 breakthrough = 0.05 }"}),
    ], ["infantry_tech"])
    ladder("hod_training", "infantry", 5, [
        (0, 1, "Academy Drill", {}, {"extra": "category_all_infantry = { max_organisation = 2 }"}),
        (1, 1, "Live-Fire Exercises", {}, {"extra": "category_all_infantry = { max_organisation = 3 default_morale = 0.05 }"}),
        (2, 1, "Veteran Cadres", {}, {"extra": "category_all_infantry = { max_organisation = 3 soft_attack = 0.05 }"}),
    ], ["infantry_tech"])
    ladder("hod_field_gear", "infantry", 6, [
        (0, 2, "Ration Bars and Medpacs", {"land_reinforce_rate": 0.01}),
        (1, 2, "Environment Suits", {"attrition": -0.05}),
        (2, 2, "Survival Kits", {"attrition": -0.05, "land_reinforce_rate": 0.01}),
    ], ["infantry_tech"])
    ladder("hod_militia_doctrine", "infantry", 7, [
        (0, 0, "Planetary Defence Forces", {}, {"extra": "hod_militia = { defense = 0.1 }"}),
        (1, 1, "Garrison Fortifications", {}, {"extra": "hod_militia = { defense = 0.1 max_organisation = 5 }"}),
    ], ["infantry_tech"])
    tech("hod_jump_troopers", "infantry", 8, 1, 0, "Jump Troopers", cats=["para_tech"], unlock_units=["hod_jump_trooper"],
         unlock_eq=["hod_jetpack_equipment_1"])
    tech("hod_jump_troopers_2", "infantry", 8, 3, 0, "Advanced Jetpacks", cats=["para_tech"], unlock_eq=["hod_jetpack_equipment_2"],
         extra="hod_jump_trooper = { soft_attack = 0.1 breakthrough = 0.1 }")
    tech("hod_assault_troopers", "infantry", 9, 0, 2, "Orbital Assault Troopers", cats=["marine_tech"],
         unlock_units=["hod_assault_trooper"])
    tech("hod_assault_troopers_2", "infantry", 9, 2, 0, "Drop-Pod Assault", cats=["marine_tech"],
         extra="hod_assault_trooper = { breakthrough = 0.1 max_organisation = 5 }")
    tech("hod_mountain_troopers", "infantry", 10, 1, 2, "Mountain and Arctic Troopers", cats=["mountaineers_tech"],
         unlock_units=["hod_mountain_trooper"])
    tech("hod_mountain_troopers_2", "infantry", 10, 2, 2, "Extreme Environment Training", cats=["mountaineers_tech"],
         extra="hod_mountain_trooper = { soft_attack = 0.1 defense = 0.1 }")


# ─────────────────────────────── SUPPORT ───────────────────────────────
def support():
    c = ["support_tech"]
    ladder("hod_support_gear", "support", 1, [
        (0, 0, "Field Support Gear", {}, {"unlock_eq": ["hod_support_equipment_1"]}),
        (1, 0, "Military Support Gear", {}, {"unlock_eq": ["hod_support_equipment_2"]}),
        (3, 0, "Advanced Support Gear", {}, {"unlock_eq": ["hod_support_equipment_3"]}),
    ], c)
    for row, pre, names, unit_id, cat, bonus in (
        (2, "hod_engineering_corps", ["Combat Engineers", "Field Fortification Droids", "Assault Engineers"], "hod_engineers",
         "engineers_tech", "hod_engineers = { defense = 0.1 }"),
        (3, "hod_scouts", ["Speeder Scouts", "Probe Droids", "Deep Recon Units"], "hod_recon", "recon_tech",
         "hod_recon = { soft_attack = 0.1 }"),
        (4, "hod_medical_corps", ["Bacta Medics", "Mobile Bacta Stations"], "hod_medics", "support_tech",
         "hod_medics = { max_organisation = 5 }"),
        (5, "hod_logistics_corps", ["Logistics Companies", "Repulsorlift Haulers", "Hyperlane Supply Chains"], "hod_logistics",
         "support_tech", "hod_logistics = { max_organisation = 5 }"),
        (6, "hod_maintenance_corps", ["Maintenance Droids", "Field Repair Bays"], "hod_maintenance", "support_tech",
         "hod_maintenance = { max_organisation = 5 }"),
        (7, "hod_signal_corps", ["HoloNet Communications", "Battlefield Coordination Droids"], "hod_signal", "support_tech",
         "hod_signal = { max_organisation = 5 }"),
        (8, "hod_police_corps", ["Military Police", "Security Droids"], "hod_military_police", "support_tech",
         "hod_military_police = { max_organisation = 5 }")):
        steps = [(0, 1), (1, 1), (2, 1)][:len(names)]
        ladder(pre, "support", row, [
            (e, st, nm, {}, {"cats": [cat], **({"unlock_units": [unit_id]} if i == 0 else {"extra": bonus})})
            for i, ((e, st), nm) in enumerate(zip(steps, names))], [cat])
    for row, pre, arch, names, units_, cat in (
        (9, "hod_artillery_tech", "hod_artillery_equipment",
         ["Mass-Driver Cannons", "Heavy Laser Artillery", "Self-Propelled Heavy Artillery", "Imperial Siege Batteries"],
         ["hod_artillery", "hod_artillery_support"], "artillery"),
        (10, "hod_missile_artillery_tech", "hod_missile_artillery_equipment",
         ["Concussion Missile Launchers", "Mobile Missile Batteries", "Imperial Missile Batteries"],
         ["hod_missile_artillery", "hod_missile_artillery_support"], "artillery"),
        (11, "hod_antiarmor_tech", "hod_antiarmor_equipment",
         ["Rocket Launchers", "Anti-Vehicle Laser Cannons", "Ion Cannons", "Heavy Ion Cannons"],
         ["hod_antiarmor", "hod_antiarmor_support"], "cat_anti_tank"),
        (12, "hod_flak_tech", "hod_flak_equipment",
         ["Anti-Air Repeaters", "Flak Laser Batteries", "Tracking Flak Emplacements", "Imperial Point-Defence Batteries"],
         ["hod_flak", "hod_flak_support"], "cat_anti_air")):
        eras = [0, 1, 2, 3] if len(names) == 4 else [1, 2, 3]
        ladder(pre, "support", row, [
            (e, 0 if e else 1, nm, {}, {"unlock_eq": [f"{arch}_{i + 1}"], **({"unlock_units": units_} if i == 0 else {})})
            for i, (e, nm) in enumerate(zip(eras, names))], [cat])
    ladder("hod_fortification", "support", 13, [
        (0, 2, "Hardened Bunkers", {"max_dig_in": 1}),
        (1, 2, "Deflector Shield Bunkers", {"max_dig_in": 2, "dig_in_speed_factor": 0.1}, {"deps": ["hod_shield_theory_2"]}),
        (2, 2, "Planetary Shield Generators", {"max_dig_in": 2, "dig_in_speed_factor": 0.15}, {"deps": ["hod_shield_theory_3"]}),
    ], ["cat_fortification"])


# ─────────────────────────────── output ───────────────────────────────
def era_dependency(t):
    """the era tech this tech needs, if it opens an era in its line (first tech of era >= 1 in the line)"""
    if t["era"] == 0 or t["id"].startswith("era_"):
        return None
    p = TECHS.get(t["parent"]) if t["parent"] else None
    if p and p["era"] == t["era"]:
        return None
    return f"era_{t['tab']}_{t['era'] + 1}"


def root_of(tid):
    while TECHS[tid]["parent"]:
        tid = TECHS[tid]["parent"]
    return tid


def position(t):
    r = TECHS[root_of(t["id"])]
    return ERA_SLOT * t["era"] + TECH_W * t["step"], (t["row"] - r["row"]) * ROW_H


def tech_block(t):
    x, y = position(t)
    out = [f"\t{t['id']} = {{"]
    if t["eq"]:
        # a chassis/airframe variant also unlocks its role versions (vanilla lists them the same way)
        roles = {**ROLE_CHASSIS, **ROLE_FRAMES}
        dups = [r + e[len(a):] for e in t["eq"] for r, (a, _t, _n) in roles.items() if re.fullmatch(re.escape(a) + r"_\d+", e)]
        out.append("\t\tenable_equipments = { " + " ".join(t["eq"] + dups) + " }")
    if t["units"]:
        out.append("\t\tenable_subunits = { " + " ".join(t["units"]) + " }")
    if t["modules"]:
        out.append("\t\tenable_equipment_modules = { " + " ".join(t["modules"]) + " }")
    for b, lvl in t["buildings"]:
        out.append(f"\t\tenable_building = {{ building = {b} level = {lvl} }}")
    for k, v in t["mods"].items():
        out.append(f"\t\t{k} = {v:g}")
    if t["extra"]:
        out.append(f"\t\t{t['extra']}")
    for c in t["children"]:
        out.append(f"\t\tpath = {{ leads_to_tech = {c} research_cost_coeff = 1 }}")
    deps = list(t["deps"]) + ([era_dependency(t)] if era_dependency(t) else [])
    if deps:
        out.append("\t\tdependencies = { " + " ".join(f"{d} = 1" for d in deps) + " }")
    if t["xor"]:
        out.append("\t\tXOR = { " + " ".join(t["xor"]) + " }")
    out += [f"\t\tresearch_cost = {t['cost']:g}", f"\t\tstart_year = {t['year']}",
            f"\t\tfolder = {{ name = {TABS[t['tab']][0]} position = {{ x = {x} y = {y} }} }}",
            "\t\tcategories = { " + " ".join(t["cats"] or ["hod_misc"]) + " }",
            f"\t\tai_will_do = {{ factor = {t['ai']} }}", "\t}"]
    return "\n".join(out)


def hidden_block():
    out = ["technologies = {", "\t# HOD: hidden access techs (OWB style): never researchable, set in history or by focus / event"]
    for tid in ACCESS:
        out += [f"\t{tid} = {{", "\t\tresearch_cost = 1", "\t\tstart_year = 2000", "\t\tallow = { always = no }",
                "\t\tcategories = { hod_access }", "\t\tai_will_do = { factor = 0 }", "\t}"]
    return "\n".join(out + ["}", ""])


def vanilla_names(sub, key=r"^	(\w+) = \{"):
    import glob
    out = set()
    for f in glob.glob(f"{VANILLA}/common/units/{sub}*.txt"):
        out |= set(re.findall(key, open(f, encoding="utf-8-sig", errors="ignore").read(), re.M))
    return out


def check_templates():
    """every template we copy must exist in vanilla"""
    errs = []
    units_v = vanilla_names("")
    equip_v = vanilla_names("equipment/")
    mods_v = vanilla_names("equipment/modules/")
    for u, d in UNITS.items():
        if d["template"] not in units_v:
            errs.append(f"unit {u}: no vanilla template {d['template']}")
    for e, d in EQUIP.items():
        if d["template"] not in equip_v:
            errs.append(f"equipment {e}: no vanilla template {d['template']}")
    for c, d in CHASSIS.items():
        for v in [d["template"]] + [x[1] for x in d["variants"]]:
            if v not in equip_v:
                errs.append(f"chassis {c}: no vanilla template {v}")
    for r, (_a, tmpl, _n) in ROLE_CHASSIS.items():
        if tmpl not in equip_v:
            errs.append(f"role chassis {r}: no vanilla template {tmpl}")
    for mo, (tmpl, _n) in list(MODULES.items()) + list(PLANE_MODULES.items()) + list(SHIP_MODULES.items()):
        if tmpl not in mods_v:
            errs.append(f"module {mo}: no vanilla template {tmpl}")
    for c, d in list(AIRFRAMES.items()) + list(HULLS.items()):
        for v in [d["template"]] + [x[1] for x in d["variants"]]:
            if v not in equip_v:
                errs.append(f"design base {c}: no vanilla template {v}")
    for r, (_a, tmpl, _n) in ROLE_FRAMES.items():
        if tmpl not in equip_v:
            errs.append(f"role frame {r}: no vanilla template {tmpl}")
    return errs


def check():
    doc = open(f"{VANILLA}/documentation/modifiers_documentation.md", encoding="utf-8").read()
    known_mods = set(re.findall(r"^## (\w+)$", doc, re.M))
    blds = set()
    for f in ("common/buildings/00_buildings.txt", "common/buildings/01_landmark_buildings.txt"):
        s = re.sub(r"#.*", "", open(f, encoding="utf-8-sig").read())
        blds |= set(re.findall(r"^\t(\w+)\s*=\s*\{", s, re.M))
    errors = []
    slots = {}
    for t in TECHS.values():
        for m in t["mods"]:
            if m not in known_mods:
                errors.append(f"{t['id']}: unknown modifier {m}")
        for b, _ in t["buildings"]:
            if b not in blds:
                errors.append(f"{t['id']}: unknown building {b}")
        for d in t["deps"] + t["xor"] + ([t["parent"]] if t["parent"] else []):
            if d not in TECHS and d not in ACCESS:
                errors.append(f"{t['id']}: unknown tech {d}")
        variants = ({v["id"] for e in EQUIP.values() for v in e["variants"]} | {v[0] for c in CHASSIS.values() for v in c["variants"]}
                    | {v[0] for c in AIRFRAMES.values() for v in c["variants"]} | {v[0] for c in HULLS.values() for v in c["variants"]})
        for e in t["eq"]:
            if e not in variants:
                errors.append(f"{t['id']}: unknown equipment {e}")
        for u in t["units"]:
            if u not in UNITS:
                errors.append(f"{t['id']}: unknown unit {u}")
        for mo in t["modules"]:
            if mo not in MODULES and mo not in PLANE_MODULES and mo not in SHIP_MODULES:
                errors.append(f"{t['id']}: unknown module {mo}")
        x, y = position(t)
        key = (t["tab"], TECHS[root_of(t["id"])]["row"] * ROW_H + y, x)
        if key in slots:
            errors.append(f"{t['id']} overlaps {slots[key]} in {t['tab']}")
        slots[key] = t["id"]
        if t["parent"] and TECHS[t["parent"]]["era"] > t["era"]:
            errors.append(f"{t['id']} comes before its parent in time")
    unlocked_eq = {e for t in TECHS.values() for e in t["eq"]}
    unlocked_units = {u for t in TECHS.values() for u in t["units"]}
    for e in EQUIP.values():
        for v in e["variants"]:
            if v["id"] not in unlocked_eq:
                errors.append(f"equipment {v['id']} is never unlocked")
    for c in list(CHASSIS.values()) + list(AIRFRAMES.values()) + list(HULLS.values()):
        for v in c["variants"]:
            if v[0] not in unlocked_eq:
                errors.append(f"design base {v[0]} is never unlocked")
    unlocked_mods = {mo for t in TECHS.values() for mo in t["modules"]}
    for mo in list(MODULES) + list(PLANE_MODULES) + list(SHIP_MODULES):
        if mo not in unlocked_mods:
            errors.append(f"module {mo} is never unlocked")
    for u, d in UNITS.items():
        if u not in unlocked_units:
            errors.append(f"unit {u} is never unlocked")
        if d["need"] in ("chassis", "hull"):
            continue
        for need in d["need"]:
            if need not in EQUIP and need not in AIRFRAMES and need not in ROLE_FRAMES:
                errors.append(f"unit {u} needs unknown equipment {need}")
    errors += check_templates()
    print(f"{len(TECHS)} techs, {len(ACCESS)} access techs, {sum(len(e['variants']) for e in EQUIP.values())} equipment "
          f"variants, {sum(len(c['variants']) for c in list(CHASSIS.values()) + list(AIRFRAMES.values()) + list(HULLS.values()))} design bases, "
          f"{len(MODULES) + len(PLANE_MODULES) + len(SHIP_MODULES)} modules, "
          f"{len(UNITS)} units, {len(errors)} problems")
    for e in errors:
        print("  ", e)
    return not errors


# ─────────────────────────────── WRITERS ───────────────────────────────
OUT_TECH = "common/technologies"
OUT_EQ = "common/units/equipment"
OUT_UNITS = "common/units"
OUT_LOC = "localisation/english/hod_techtree_l_english.yml"
OUT_ICONS_GFX = "interface/hod_techtree_icons.gfx"
GUI = "interface/countrytechtreeview.gui"
TAGS = "common/technology_tags/00_technology.txt"
PLACEHOLDER = {"infantry": "infantry_weapons", "support": "support_weapons", "vehicles": None, "air": "early_fighter",
               "fleet": "early_destroyer", "industry": "basic_machine_tools", "engineering": None,
               "clone": "gfx/interface/technologies/phase_I_equipment_medium.dds",
               "droid": "gfx/interface/technologies/early_droid_infantry_medium.dds"}
_VB = {}


def vanilla_block(sub, name):
    """the `\\t<name> = { ... }` block of a vanilla definition under common/units/<sub>"""
    import glob
    if sub not in _VB:
        _VB[sub] = {}
        for f in glob.glob(f"{VANILLA}/common/units/{sub}*.txt"):
            s = open(f, encoding="utf-8-sig", errors="ignore").read().replace("\r\n", "\n")
            for m in re.finditer(r"^\t(\w+) = \{", s, re.M):
                i, d = m.end(), 1
                while d:
                    d += {"{": 1, "}": -1}.get(s[i], 0)
                    i += 1
                _VB[sub].setdefault(m.group(1), s[m.start():i])
    return _VB[sub][name]


def strip_block(text, key):
    """remove every `key = { ... }` sub-block"""
    while True:
        m = re.search(r"\n\s*%s\s*=\s*\{" % key, text)
        if not m:
            return text
        i, d = m.end(), 1
        while d:
            d += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        text = text[:m.start()] + text[i:]


def set_field(text, key, value):
    """set `key = value` at the block's top level (replace if present, else insert before the closing brace)"""
    pat = re.compile(r"(\n\t\t%s\s*=\s*)[^\n{]+" % re.escape(key))
    if pat.search(text):
        return pat.sub(lambda m: m.group(1) + str(value), text, count=1)
    return text[:text.rstrip().rfind("}")] + f"\t\t{key} = {value}\n\t}}"


def rename(text, old, new):
    return re.sub(r"^\t%s = \{" % re.escape(old), f"\t{new} = {{", text, count=1)


def num_stats(text):
    return {k: float(v) for k, v in re.findall(r"\n\t\t(\w+)\s*=\s*(-?[0-9.]+)\s*(?:#[^\n]*)?\n", text) if k in STATS}


def write_equipment():
    out = ["equipments = {", "\t# HOD: generated by WIPGFX/plans & scripts/techtree_gen.py (vanilla structures, our names)"]
    for arch, d in EQUIP.items():
        b = rename(vanilla_block("equipment/", d["template"]), d["template"], arch)
        b = strip_block(b, "can_be_produced")
        b = strip_block(b, "resources")
        base = num_stats(b)
        for k, v in d["base"].items():
            b = set_field(b, k, v)
            base[k] = v
        if d["picture"]:
            b = set_field(b, "picture", d["picture"])
        b = set_field(b, "active", "no")
        b = b[:b.rstrip().rfind("}")] + "\t\tresources = { " + " ".join(f"{k} = {v}" for k, v in d["resources"].items()) + " }\n\t}"
        out.append(b)
        for i, v in enumerate(d["variants"]):
            lines = [f"\t{v['id']} = {{", f"\t\tyear = {v['year']}", f"\t\tarchetype = {arch}"]
            if v["parent"]:
                lines.append(f"\t\tparent = {v['parent']}")
            lines += [f"\t\tpriority = {10 + i * 5}", f"\t\tvisual_level = {i}", "\t\tactive = no"]
            for k, val in v["stats"].items():
                if k.startswith("*"):
                    k = k[1:]
                    val = round(base.get(k, 0) * val, 3)
                lines.append(f"\t\t{k} = {val:g}")
            out.append("\n".join(lines + ["\t}"]))
    return "\n".join(out + ["}", ""])


def designer_equipment(families, roles, mod_map, prefix_map):
    """chassis / airframes / hulls: archetype + variants copied from vanilla, role sub-archetypes, our modules"""
    rev = {tmpl: ours for ours, (tmpl, _n) in mod_map.items()}
    out = []
    for arch, d in families.items():
        b = rename(vanilla_block("equipment/", d["template"]), d["template"], arch)
        b = strip_block(b, "can_be_produced")
        def fix_defaults(text):
            m = re.search(r"default_modules\s*=\s*\{([^}]*)\}", text)
            if not m:
                return text
            body = re.sub(r"=\s*(\w+)", lambda mm: "= " + (rev.get(mm.group(1), "empty") if mm.group(1) != "empty" else "empty"), m.group(1))
            return text[:m.start(1)] + body + text[m.end(1):]
        b = fix_defaults(b)
        b = re.sub(r"\n\s*module_count_limit\s*=\s*\{\s*module\s*=\s*(\w+)\s*count\s*<\s*\d+\s*\}",
                   lambda m: m.group(0).replace(m.group(1), rev[m.group(1)]) if m.group(1) in rev else "", b)
        out.append(b)
        prev = None
        for vid, tmpl, year, _name in d["variants"]:
            v = rename(vanilla_block("equipment/", tmpl), tmpl, vid)
            v = re.sub(r"\n(\s*)archetype\s*=\s*\w+", f"\n\\1archetype = {arch}", v)
            v = re.sub(r"\n\s*parent\s*=\s*\w+", "", v)
            v = re.sub(r"\n(\s*)derived_variant_name\s*=\s*\w+", lambda m: f"\n{m.group(1)}derived_variant_name = {vid.replace('_chassis', '_equipment').replace('_airframe', '').replace('_hull', '')}", v)
            v = set_field(v, "year", year)
            if prev:
                v = set_field(v, "parent", prev)
            v = fix_defaults(v)
            v = strip_block(v, "can_be_produced")
            out.append(v)
            prev = vid
    role_rev = {tmpl: ours for ours, (_a, tmpl, _n) in roles.items()}
    for ours, (arch, tmpl, _n) in roles.items():
        v = rename(vanilla_block("equipment/", tmpl), tmpl, ours)
        v = re.sub(r"\n(\s*)archetype\s*=\s*\w+", f"\n\\1archetype = {arch}", v)
        # explicit variant names (planes) follow our variants: <role>_<n> = <role minus _airframe>_<n>
        v = re.sub(r"variant_name\s*=\s*\{[^{}]*\}", lambda m: "variant_name = {" + "".join(
            f"\n\t\t\t{n} = {loc}" for n, loc in role_variants(ours, arch)) + "\n\t\t}", v)
        v = re.sub(r"\n(\s*)substitute\s*=\s*(\w+)", lambda m: f"\n{m.group(1)}substitute = {role_rev[m.group(2)]}" if m.group(2) in role_rev else "", v)
        ROLE_OUT.append(v)
    return out


ROLE_OUT = []   # duplicate_archetypes blocks: must load after the archetypes (x_hod_roles.txt)


def role_variants(role, arch):
    """(duplicated variant, its localisation key) for each variant of the archetype"""
    fam = {**CHASSIS, **AIRFRAMES}[arch]
    loc = role.replace("_chassis", "_equipment") if role.endswith("_chassis") else role.replace("_airframe", "")
    return [(role + vid[len(arch):], loc + vid[len(arch):]) for vid, _t, _y, _n in fam["variants"]]


_PARTS = set()


def known_parts(text):
    """keep only critical parts the mod defines (it replaces common/units, so some vanilla parts don't exist)"""
    import glob
    if not _PARTS:
        for f in glob.glob(f"{OUT_UNITS}/critical_parts/*.txt"):
            _PARTS.update(re.findall(r"^\t(\w+)\s*=\s*\{", open(f, encoding="utf-8-sig", errors="ignore").read(), re.M))
    return re.sub(r"(critical_parts\s*=\s*\{)([^}]*)\}",
                  lambda m: m.group(1) + " " + " ".join(p for p in m.group(2).split() if p in _PARTS) + " }", text)


def write_modules(mod_map):
    out = ["equipment_modules = {", "\t# HOD: generated by techtree_gen.py (vanilla module structures, our names)"]
    for ours, (tmpl, _n) in mod_map.items():
        out.append(known_parts(rename(vanilla_block("equipment/modules/", tmpl), tmpl, ours)))
    return "\n".join(out + ["}", ""])


def write_units():
    chassis_map = {}
    for key, vp, _d in SIZES:
        chassis_map[f"{vp}_tank_chassis"] = f"hod_{key}_vehicle_chassis"
        for rk, rv, _r in ROLES:
            chassis_map[f"{vp}_tank_{rv}_chassis"] = f"hod_{key}_vehicle_{rk}_chassis"
    hull_map = {d["template"]: arch for arch, d in HULLS.items() if arch != "hod_dreadnought_hull"}
    out = ["sub_units = {", "\t# HOD: generated by techtree_gen.py (vanilla unit structures, our names and equipment)"]
    for uid, d in UNITS.items():
        b = rename(vanilla_block("", d["template"]), d["template"], uid)
        # ships also name their armour modules: ours where mapped, unmapped ones dropped
        rev = {tmpl: ours for ours, (tmpl, _n) in SHIP_MODULES.items()}
        b = re.sub(r"\n(\s*)(ship_armor_\w+)(\s*=\s*1)", lambda mm: f"\n{mm.group(1)}{rev[mm.group(2)]}{mm.group(3)}" if mm.group(2) in rev else "", b)
        m = re.search(r"need(?:_equipment)?\s*=\s*\{([^}]*)\}", b)
        if d["need"] in ("chassis", "hull"):
            mp = chassis_map if d["need"] == "chassis" else ({"ship_hull_heavy": "hod_dreadnought_hull"} if uid == "hod_dreadnought" else hull_map)
            body = re.sub(r"(\w+)(\s*=)", lambda mm: mp.get(mm.group(1), mm.group(1)) + mm.group(2), m.group(1))
        else:
            body = " " + " ".join(f"{k} = {v}" for k, v in d["need"].items()) + " "
        b = b[:m.start(1)] + body + b[m.end(1):] if m else b[:b.rstrip().rfind("}")] + f"\t\tneed = {{{body}}}\n\t}}"
        b = known_parts(b)
        b = set_field(b, "active", "no")
        for k, v in d["overrides"].items():
            b = set_field(b, k, v)
        out.append(b)
    return "\n".join(out + ["}", ""])


def tech_files():
    files = OrderedDict()
    for t in TECHS.values():
        files.setdefault(t["tab"], []).append(tech_block(t))
    return {f"hod_tech_{tab}.txt": "technologies = {\n\t# HOD: generated by WIPGFX/plans & scripts/techtree_gen.py\n" + "\n".join(blocks) + "\n}\n"
            for tab, blocks in files.items()}


def folder_window(tab, bg_sprite):
    folder = TABS[tab][0]
    roots = [t for t in TECHS.values() if t["tab"] == tab and not t["parent"]]
    rows = max(t["row"] for t in TECHS.values() if t["tab"] == tab) + 1
    w, h = GRID_X + 4 * ERA_SLOT * SLOT + 200, GRID_Y + rows * ROW_H * SLOT + 120
    heads = "".join(f'''
				instantTextBoxType = {{
					name = "{folder}_era{e}"
					position = {{ x = {GRID_X + e * ERA_SLOT * SLOT - 40} y = 50 }}
					font = "hoi_36header"
					borderSize = {{ x = 0 y = 0 }}
					text = "HOD_ERA_{e}"
					maxWidth = 300
					maxHeight = 32
					format = center
					Orientation = "UPPER_LEFT"
				}}''' for e in range(4))
    grids = "".join(f'''
			gridboxtype = {{
				name = "{t['id']}_tree"
				position = {{ x = {GRID_X} y = {GRID_Y + t['row'] * ROW_H * SLOT} }}
				slotsize = {{ width = {SLOT} height = {SLOT} }}
				format = "LEFT"
			}}''' for t in roots)
    return f'''		containerWindowType = {{
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
					width = {w} height = {h}
					min = {{ width = 100%% height = 100%% }}
				}}
				clipping = no

				iconType = {{
					name ="{folder}_bg"
					spriteType = "{bg_sprite}"
					position = {{ x=0 y=0 }}
					alwaystransparent = yes
				}}{heads}
			}}
{grids}
		}}'''


def find_window(gui, name):
    """span of the `containerWindowType` whose name is `name` (first match)"""
    i = gui.index(f'name = "{name}"')
    j = gui.rfind("containerWindowType", 0, i)
    k, d = gui.index("{", j) + 1, 1
    while d:
        d += {"{": 1, "}": -1}.get(gui[k], 0)
        k += 1
    return j, k


def write_gui():
    raw = open(GUI, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    g = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in g else "\n"
    g = g.replace("\r\n", "\n")
    for tab, (folder, _d) in TABS.items():
        j, k = find_window(g, folder)
        old = g[j:k]
        bg = re.search(r'spriteType\s*=\s*"(GFX_\w+techtree_bg\w*)"', old)
        g = g[:j] + folder_window(tab, bg.group(1) if bg else "GFX_infantry_techtree_bg").lstrip("\t") + g[k:]
    # tab bar: our nine tabs side by side, the dropped folders' buttons removed
    j, k = find_window(g, "folder_tabs")
    bar = g[j:k]
    for dead in ("nsb_armour_folder_tab", "artillery_folder_tab", "mtgnavalfolder_tab", "mtgnavalsupportfolder_tab", "bba_air_techs_folder_tab"):
        i = bar.find(f'name = "{dead}"')
        if i < 0:
            continue
        a = bar.rfind("\n", 0, bar.rfind("buttonType", 0, i))
        b, d = bar.index("{", a) + 1, 1
        while d:                                   # the button holds nested blocks (position = { ... })
            d += {"{": 1, "}": -1}.get(bar[b], 0)
            b += 1
        bar = bar[:a] + bar[b:]
    # tab highlights sit on their tab
    for hl, folder in (("highlight_infantry_folder", "infantry_folder"), ("highlight_engineering_folder", "electronics_folder"),
                       ("highlight_industry_folder", "industry_folder")):
        x = 22 + 89 * [f for f, _d in TABS.values()].index(folder)
        bar = re.sub(r'(name = "%s"[^}]*?position = \{ ?x ?= ?)-?\d+' % hl, lambda m: m.group(1) + str(x), bar)
    for n, (tab, (folder, _d)) in enumerate(TABS.items()):
        bar = re.sub(r'(buttonType = \{[^{}]*?)position = \{ x = \d+ y = 0 \}([^{}]*?name = "%s_tab")' % folder,
                     lambda m: m.group(1) + f"position = {{ x = {22 + 89 * n} y = 0 }}" + m.group(2), bar)
        bar = re.sub(r'(buttonType = \{[^{}]*?name = "%s_tab"[^{}]*?)position = \{ x = \d+ y = 0 \}' % folder,
                     lambda m: m.group(1) + f"position = {{ x = {22 + 89 * n} y = 0 }}", bar)
    g = g[:j] + bar + g[k:]
    open(GUI, "wb").write((b"\xef\xbb\xbf" if bom else b"") + g.replace("\n", nl).encode("utf-8"))


def write_tags():
    raw = open(TAGS, "rb").read()
    s = raw.decode("utf-8-sig").replace("\r\n", "\n")
    cats = set(c for t in TECHS.values() for c in t["cats"]) | {"hod_access", "hod_misc"}
    m = re.search(r"technology_categories\s*=\s*\{([^}]*)\}", s)
    have = set(m.group(1).split())
    add = sorted(cats - have)
    s = s[:m.end(1)] + "".join(f"\t{c}\n" for c in add) + s[m.end(1):]
    f = s.index("technology_folders")
    i, d = s.index("{", f) + 1, 1
    while d:
        d += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    old = s[f:i]
    keep = [m.group(0) for m in re.finditer(r"\n\t(\w+_doctrine_folder) = \{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", old)]
    avail = {"republic_folder": "\t\tavailable = { has_tech = access_kamino_cloning }\n",
             "droid_folder": "\t\tavailable = { has_tech = access_droid_foundries }\n"}
    ledger = {"air_techs_folder": "air", "naval_folder": "navy", "industry_folder": "civilian", "electronics_folder": "civilian"}
    body = "technology_folders = {\n\t# HOD: the nine tabs of the generated tree (techtree_gen.py) + doctrine folders\n"
    for tab, (folder, _d) in TABS.items():
        body += f"\t{folder} = {{\n{avail.get(folder, '')}\t\tledger = {ledger.get(folder, 'army')}\n\t}}\n"
    body += "".join(keep).lstrip("\n") + "\n}"
    s = s[:f] + body + s[i:]
    open(TAGS, "wb").write((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + s.encode("utf-8"))


def write_icons():
    import shutil, glob
    os.makedirs("gfx/interface/technologies/hod", exist_ok=True)
    vt = f"{VANILLA}/gfx/interface/technologies"
    pick = dict(PLACEHOLDER)
    pick["vehicles"] = next((os.path.basename(p)[:-4] for p in sorted(glob.glob(vt + "/*tank*.dds"))), "infantry_weapons")
    pick["engineering"] = next((os.path.basename(p)[:-4] for p in sorted(glob.glob(vt + "/*radio*.dds")) + sorted(glob.glob(vt + "/*electr*.dds"))), "infantry_weapons")
    tex = {}
    for tab, src in pick.items():
        if src.startswith("gfx/"):   # HoD's own art
            tex[tab] = src
        else:
            dst = f"gfx/interface/technologies/hod/placeholder_{tab}.dds"
            shutil.copy2(f"{vt}/{src}.dds", dst)
            tex[tab] = dst
    out = ["spriteTypes = {", "\t# HOD: placeholder tech icons (techtree_gen.py): one per tab until art exists"]
    for t in TECHS.values():
        out.append(f'\tspriteType = {{ name = "GFX_{t["id"]}_medium" texturefile = "{tex[t["tab"]]}" }}')
    open(OUT_ICONS_GFX, "w", encoding="utf-8", newline="\n").write("\n".join(out + ["}", ""]))


def write_loc():
    q = lambda s: s.replace('"', "'")
    out = ["l_english:", " # HOD: generated by WIPGFX/plans & scripts/techtree_gen.py"]
    for e, nm in enumerate(ERAS):
        out.append(f' HOD_ERA_{e}:0 "{nm}"')
    for tid, (nm, desc) in ACCESS.items():
        out += [f' {tid}:0 "{q(nm)}"', f' {tid}_desc:0 "{q(desc)}"']
    for t in TECHS.values():
        out += [f' {t["id"]}:0 "{q(t["name"])}"', f' {t["id"]}_desc:0 "{q(t["desc"])}"']
    for arch, d in EQUIP.items():
        out += [f' {arch}:0 "{q(d["name"])}"', f' {arch}_desc:0 "{q(d["desc"])}"']
        for v in d["variants"]:
            out += [f' {v["id"]}:0 "{q(v["name"])}"', f' {v["id"]}_short:0 "{q(v["name"])}"']
    for fam in (CHASSIS, AIRFRAMES, HULLS):
        for arch, d in fam.items():
            out.append(f' {arch}:0 "{q(d["name"])}"')
            for vid, _t, _y, nm in d["variants"]:
                out += [f' {vid}:0 "{q(nm)}"', f' {vid}_short:0 "{q(nm)}"']
    for r, (a, _t, nm) in list(ROLE_CHASSIS.items()) + list(ROLE_FRAMES.items()):
        out.append(f' {r}:0 "{q(nm)}"')
        for (dup, loc), (_v, _tm, _y, vnm) in zip(role_variants(r, a), {**CHASSIS, **AIRFRAMES}[a]["variants"]):
            label = f"{vnm.split()[0]} {nm}"
            out += [f' {dup}:0 "{q(label)}"', f' {loc}:0 "{q(label)}"', f' {loc}_short:0 "{q(label)}"']
    for mo, (_t, nm) in list(MODULES.items()) + list(PLANE_MODULES.items()) + list(SHIP_MODULES.items()):
        out.append(f' {mo}:0 "{q(nm)}"')
    for u, d in UNITS.items():
        out += [f' {u}:0 "{q(d["name"])}"', f' {u}_desc:0 "{q(d["desc"])}"']
    open(OUT_LOC, "w", encoding="utf-8-sig", newline="\n").write("\n".join(out) + "\n")


def write_all():
    for name, text in tech_files().items():
        open(f"{OUT_TECH}/{name}", "w", encoding="utf-8", newline="\n").write(text)
    open(f"{OUT_TECH}/hod_tech_access.txt", "w", encoding="utf-8", newline="\n").write(hidden_block())
    open(f"{OUT_EQ}/hod_equipment.txt", "w", encoding="utf-8", newline="\n").write(write_equipment())
    open(f"{OUT_EQ}/hod_designs.txt", "w", encoding="utf-8", newline="\n").write(
        "equipments = {\n\t# HOD: generated by techtree_gen.py (chassis, airframes, hulls and their role versions)\n"
        + "\n".join(designer_equipment(CHASSIS, ROLE_CHASSIS, MODULES, None)
                    + designer_equipment(AIRFRAMES, ROLE_FRAMES, PLANE_MODULES, None)
                    + designer_equipment(HULLS, {}, SHIP_MODULES, None)) + "\n}\n")
    open(f"{OUT_EQ}/x_hod_roles.txt", "w", encoding="utf-8", newline="\n").write(
        "# HOD: generated by techtree_gen.py. Must load after hod_designs.txt (role versions of our chassis and airframes)\n"
        "duplicate_archetypes = {\n" + "\n".join(ROLE_OUT) + "\n}\n")
    ROLE_OUT.clear()
    for name, mm in (("hod_vehicle_modules.txt", MODULES), ("hod_plane_modules.txt", PLANE_MODULES), ("hod_ship_modules.txt", SHIP_MODULES)):
        open(f"{OUT_EQ}/modules/{name}", "w", encoding="utf-8", newline="\n").write(write_modules(mm))
    open(f"{OUT_UNITS}/hod_units.txt", "w", encoding="utf-8", newline="\n").write(write_units())
    write_tags()
    write_gui()
    write_icons()
    write_loc()
    print("written: techs, tags, tab windows, icons, localisation, equipment, designs, modules, units")


def build():
    era_techs()
    land_equipment()
    land_units()
    vehicle_designer()
    air_designer()
    fleet_designer()
    faction_equipment()
    industry()
    engineering()
    infantry()
    support()
    vehicles()
    air()
    fleet()
    clones()
    droids()


if __name__ == "__main__":
    build()
    ok = check()
    if len(sys.argv) > 1 and sys.argv[1] == "write" and ok:
        write_all()
