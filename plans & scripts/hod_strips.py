"""Multi-icon strips (each frame is a different icon): frame -> pictogram subject, identified by eye from the vanilla
strips (frame order is engine-defined), plus the building strip read from common/buildings icon_frame.
hod_icons restyles these frame by frame; a frame past the list end keeps the last subject of the list;
None keeps the vanilla frame."""

STRIPS = {
    "gfx/interface/alerts/global_alert_icons.dds": [
        "holocron", "question", "bomb", "walker", "milfactory", "factory", "milfactory", "construction", "wrench", "senate",
        "crate", "sabers", "sabers", "map", "bomb", "trooper", "clock", "fighter", "shipyard", "clock",
        "trooper", "question", "clock", "binoculars", "binoculars", "mountain", "people", "people", "comm", "crystal",
        "fist", "capital", "senate", "station", "transport", "map", "map", "map", "map", "people",
        "people", "factory", "senate", "clock", "bomb", "sabers", "sabers", "planet", "planet", "clock",
        "crystal", "trooper", "eye", "star", "rank", "bomb", "clock", "holocron", "holocron", "holocron",
        "target", "target", "comm", "holocron", "target", "target", "fuel", "station", "crystal", "flag"],
    "gfx/interface/alerts/global_diplorequest_icons.dds": [
        "accord", "unlock", "station", "banner", "banner", "accord", "trooper", "trooper", "walker", "shield",
        "planet", "map", "accord", "banner", "eye", "crate", "accord", "station", "fighter", "accord", "accord"],
    "gfx/interface/mapmode/mapmode_buttons_deselected_small.dds": [
        "question", "question", "question", "eye", "flag", "list", "fuel", "flag", "crate", "fist",
        "star", "people", "trooper", "people", "planet", "mountain", "target", "target"],
    "gfx/interface/strategicair/mission_types.dds": [
        "fighter", "bomber", "fighter", "bomber", "capital", "superweapon", "fighter", "station", "transport",
        "transport", "fighter", "fighter", "mine", "binoculars", "drop", "parachute", "bomber", "fighter", "target"],
    "gfx/interface/occupation/occupation_policy_icon_strip.dds": [
        "handcuffs", "crate", "people", "transport", "star", "trooper", "trooper", "comm", "eye", "people",
        "blaster", "home", "rank", "blaster", "home", "people", "exclaim"],
    "gfx/interface/landcombat/battle_div_modifier_strip.dds": [
        "refresh", "blaster", "drop", "bomb", "mountain", "artillery", "fuel", "parachute", "shield", "shield",
        "shield", "chevrons", "trooper", "artillery", "fist", "fist", "list"],
    "gfx/interface/navalcombat/critical_damage_icons.dds": [
        "list", "cannon", "cannon", "lightning", "bomb", "bomb", "engine", "wrench", "radar", "cannon",
        "torpedo", "cannon", "walker", "artillery", "fuel", "cog"],
    "gfx/interface/alerts/theater_alerts_strip.dds": [
        "trooper", "station", "crate", "bomb", "fighter", "blaster", "binoculars", "station", "map", "skull",
        "list", "fuel", "station", "skull"],
    "gfx/interface/research_folder_strip.dds": [
        "question", "trooper", "walker", "artillery", "fighter", "capital", "factory", "trooper", "station", "antiair",
        "wrench", "holocron"],
    "gfx/interface/landcombat/battle_modifier_strip.dds": [
        "construction", "fighter", "fighter", "station", "bomb", "fuel", "merge", "search", "bomb", "target"],
    "gfx/interface/naviesview/all_missions.dds": [
        "station", "capital", "capital", "capital", "shield", "mine", "target", "cog", "drop", "transport"],
    "gfx/interface/onmap_mission_unit_counter_types.dds": [
        "question", "binoculars", "target", "target", "shield", "bomb", "sabers", "cog", "target", "drop"],
    "gfx/interface/air_overview_plane_strip.dds": [
        "bomber", "fighter", "bomber", "fighter", "bomber", "bomber", "transport", "binoculars", "fighter"],
    "gfx/interface/operatives/operatives_mission_icons.dds": [
        "map", "radar", "eye", "sabers", "banner", "construction", "accord", "comm"],
    "gfx/interface/operatives/operatives_mission_icons_small.dds": [
        "map", "radar", "eye", "sabers", "banner", "construction", "accord", "comm"],
    "gfx/interface/strategicair/damage_types_strip.dds": [
        "capital", "capital", "walker", "fighter", "skull", "artillery", "crate", "walker", "transport", "transport",
        "transport"],
    "gfx/interface/strategicair/airwing_prio_strip.dds": [
        "arrow_d", "minus", "chevrons", "star", "arrow_d", "minus", "chevrons", "star"],
    "gfx/interface/div_priority_strip.dds": ["arrow_d", "minus", "chevrons", "arrow_d", "minus", "chevrons"],
    "gfx/interface/navalcombat/combat_stat_icons.dds": ["station", "cannon", "artillery", "torpedo", "target", "cog"],
    "gfx/interface/naviesview/defensive_stance_strip.dds": ["shield", "exclaim", "station", "blaster", "sabers", "shield"],
    "gfx/interface/strategicair/grouped_mission_types.dds": ["fighter", "capital", "crate"],   # air / naval / supply
    "gfx/interface/strategicair/day_night.dds": ["star", "moon", "moon", "star", "moon", "moon"],
    "gfx/interface/occupation/compliance_tiers_strip.dds": ["accord", "shield", "factory", "people", "accord"],
    "gfx/interface/occupation/compliance_tiers_small_strip.dds": ["accord", "shield", "factory", "people", "accord"],
    "gfx/interface/occupation/resistance_tiers_strip.dds": ["fist", "fist", "bomb", "fist"],
    "gfx/interface/occupation/resistance_tiers_small_strip.dds": ["fist", "fist", "bomb", "fist"],
    "gfx/interface/strategicair/attached_air_types.dds": ["fighter", "bomber", "bomber", "plus", "trash"],
    "gfx/interface/strategicair/wing_types_own.dds": ["fighter", "bomber", "bomber", "antiair"],
    "gfx/interface/strategicair/wing_types_enemy.dds": ["fighter", "bomber", "bomber", "antiair"],
    "gfx/interface/combatlog_atk_def.dds": ["sabers", "bomb", "shield", "shield"],
    # common/buildings icon_frame 1..31: civ factory, mil factory, infrastructure, dockyard, air base, naval base,
    # bunker, coastal bunker, AA, refinery, radar, rocket site, reactor, fuel silo, supply node, railway, air facility,
    # naval facility, land facility, nuclear facility, (unused), landmark, stronghold, mega gun, canal, dam,
    # commercial reactor, naval supply hub, naval HQ, energy infra, industrial infra
    "gfx/interface/buildings/building_icon_strip.dds": [
        "factory", "milfactory", "construction", "shipyard", "fighter", "station", "shield", "shield", "antiair", "fuel",
        "radar", "missile", "lightning", "fuel", "crate", "transport", "fighter", "station", "walker", "superweapon",
        "construction", "star", "shield", "artillery", "map", "lightning", "lightning", "crate", "rank", "lightning",
        "factory"],
}

# division / ship counter unit icons (2 frames each, same unit): unit name -> pictogram
_C = "gfx/interface/counters/divisions_large/"
STRIPS.update({_C + f"{k}_icon.dds": [v, None] for k, v in {   # frame 2 = NATO symbol: kept
    "support_unit_art": "artillery", "support_unit_field_guns": "artillery", "support_unit_fire_support": "artillery",
    "support_unit_light_spaa": "antiair", "support_unit_light_tank_destroyer": "cannon", "unit_amphibious_tank": "walker",
    "unit_anti_air": "antiair", "unit_at": "cannon", "unit_cavalry": "speeder", "unit_engineer": "wrench",
    "unit_helicopter_brigade": "drop", "unit_infantry": "trooper", "unit_light_tank_antiair": "antiair",
    "unit_light_tank_artillery": "artillery", "unit_light_tank_at": "cannon", "unit_marine": "drop",
    "unit_mot_art": "artillery", "unit_mot_at": "cannon", "unit_motorized": "speeder", "unit_mountain": "mountain",
    "unit_paratroop": "parachute", "unit_railway_gun": "artillery", "unit_ranger_battalion": "trooper",
    "unit_rocket_art": "missile", "unit_super_heavy_armor": "walker", "unit_bicycle_battalion": "speeder",
    "unit_bicycle_infantry": "speeder", "unit_integralist_militia": "trooper", "unit_militia": "trooper"}.items()})
STRIPS.update({"gfx/interface/counters/ships_small/onmap_carrier.dds": ["carrier"],
               "gfx/interface/counters/ships_small/onmap_sh_battleship_inverted.dds": ["capital"],
               "gfx/interface/counters/ships_small/onmap_transport.dds": ["transport"]})

# strips whose frames are rising levels: frame k gets k+1 pips
TIERS = {"gfx/interface/occupation/compliance_tiers_strip.dds", "gfx/interface/occupation/compliance_tiers_small_strip.dds",
         "gfx/interface/occupation/resistance_tiers_strip.dds", "gfx/interface/occupation/resistance_tiers_small_strip.dds"}

ALERTS = {"gfx/interface/alerts/global_alert_icons.dds"}   # plates carrying a coloured "!" that encodes urgency


def subjects(path):
    return STRIPS.get(path)


if __name__ == "__main__":
    assert len(STRIPS["gfx/interface/buildings/building_icon_strip.dds"]) == 31
    assert len(STRIPS["gfx/interface/alerts/global_alert_icons.dds"]) == 70
    assert len(STRIPS["gfx/interface/alerts/global_diplorequest_icons.dds"]) == 21
