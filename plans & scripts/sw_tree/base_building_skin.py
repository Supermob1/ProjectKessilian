"""Star Wars names + icons for the vanilla buildings (user 2026-11-09: "rename and change the icons for buildings too").
Only names, descriptions and icons: the buildings and their effects stay vanilla.

    python -B "plans & scripts/sw_tree/base_building_skin.py"

- NAMES -> localisation/english/replace/hod_base_buildings_l_english.yml (<key>, <key>_plural, <key>_desc).
- ICONS: icon_frame -> render of an Empire at War structure (WIPGFX/3d/_renders/buildings/<name>_raw.png), painted on the
  vanilla tile into gfx/interface/buildings/building_icon_strip.dds (same path, 31 frames of 46 px), so no sprite changes.
  Frames left out keep their vanilla pictogram (Earth landmarks, dams, canals, rocket site: unused on the planet maps).
"""
from PIL import Image, ImageEnhance, ImageFilter

GAME = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV/"
RENDERS = "../ProjectKessilianWIPGFX/ProjectKessilianWIP/3d/_renders/buildings/"
STRIP = "gfx/interface/buildings/building_icon_strip.dds"
LOC = "localisation/english/replace/hod_base_buildings_l_english.yml"
FRAME = 46

NAMES = {   # key -> (name, plural, desc)
    "infrastructure": ("Planetary Infrastructure", "Planetary Infrastructure", "Landing fields, transit tubes and repulsor roads. Better infrastructure moves troops and supply faster and raises resource output."),
    "arms_factory": ("Droid and Vehicle Foundry", "Droid and Vehicle Foundries", "Foundries that build blasters, droids, walkers and starfighters. Can be converted to civilian fabrication if needed."),
    "industrial_complex": ("Civilian Fabricator", "Civilian Fabricators", "Fabrication plants for civilian goods and for the construction of new buildings. Can be converted to military production if needed."),
    "air_base": ("Landing Platform", "Landing Platforms", "Pads and hangars that base starfighters, bombers and gunships."),
    "supply_node": ("Supply Depot", "Supply Depots", "A depot along the supply lines where the armies draw their supply."),
    "rail_way": ("Repulsor Freight Line", "Repulsor Freight Lines", "Repulsor cargo lines that carry supply from the depots to the front."),
    "naval_facility": ("Starship Research Station", "Starship Research Stations", "A research station where new starship designs are developed."),
    "naval_base": ("Space Station", "Space Stations", "Orbital stations that supply and repair the fleets and extend their range. Allow supply from orbit and the export of resources."),
    "bunker": ("Ferrocrete Bunker", "Ferrocrete Bunkers", "Ferrocrete strongpoints that make the province much harder to take."),
    "coastal_bunker": ("Turbolaser Battery", "Turbolaser Batteries", "Turbolaser towers that cover the landing zones against assault from orbit."),
    "stronghold_network": ("Shielded Stronghold", "Shielded Strongholds", "A network of shielded strongpoints, bunkers and tunnels across the state."),
    "dockyard": ("Orbital Shipyard", "Orbital Shipyards", "Shipyards in orbit that build the fleet's starships."),
    "anti_air_building": ("Anti-Starfighter Battery", "Anti-Starfighter Batteries", "Flak and laser batteries that protect the state from bombers and shoot down starfighters."),
    "synthetic_refinery": ("Fuel Synthesizer", "Fuel Synthesizers", "Synthesizes fuel and some doonium from local resources."),
    "fuel_silo": ("Fuel Depot", "Fuel Depots", "Tank farms that let the nation stockpile more fuel."),
    "radar_station": ("Sensor Array", "Sensor Arrays", "Sensor arrays that track ships, starfighters and vehicles in range."),
    "mega_gun_emplacement": ("Hypervelocity Gun", "Hypervelocity Guns", "A giant hypervelocity cannon that can strike targets far beyond the front."),
    "naval_supply_hub": ("Fleet Supply Hub", "Fleet Supply Hubs", "An orbital hub that keeps the fleets supplied."),
    "naval_headquarters": ("Fleet Command Station", "Fleet Command Stations", "The station from which a sector fleet is commanded."),
    "nuclear_reactor": ("Hypermatter Reactor", "Hypermatter Reactors", "A hypermatter reactor for the research and production of superweapons."),
    "nuclear_reactor_heavy_water": ("Hypermatter Reactor", "Hypermatter Reactors", "A hypermatter reactor for the research and production of superweapons."),
    "commercial_nuclear_reactor": ("Hypermatter Power Plant", "Hypermatter Power Plants", "A hypermatter plant that powers the planet's industry and speeds up construction."),
    "nuclear_facility": ("Hypermatter Research Facility", "Hypermatter Research Facilities", "A research facility for hypermatter and superweapon projects."),
    "air_facility": ("Starfighter Research Facility", "Starfighter Research Facilities", "A research facility for starfighters, bombers and gunships."),
    "land_facility": ("Ground Forces Proving Grounds", "Ground Forces Proving Grounds", "Proving grounds where new walkers, tanks and weapons are tested."),
    "energy_infrastructure": ("Reinforced Power Grid", "Reinforced Power Grids", "Redundant power lines and generators that keep the factories running when the grid is hit."),
    "industrial_infrastructure": ("Industrial Power Grid", "Industrial Power Grids", "High-capacity power lines that let the planet's industry run at full output."),
}

ICONS = {   # icon_frame -> render
    1: "eb_lightfactory", 2: "eb_vehiclefactory", 3: "eaw_corBuild1", 4: "eb_station", 5: "nb_basepad", 6: "eb_repairfacility",
    7: "nb_bunker", 8: "eb_tltower", 9: "eb_aaturret", 10: "fuelcella", 11: "nb_sensornode", 13: "eb_gravcontrolgen",
    14: "fuelcellc", 15: "nb_mercenaryoutfitter", 16: "eaw_crates1", 17: "eb_researchfacility", 18: "rb_researchfacility",
    19: "rb_heavyvehiclefactory", 20: "eb_megaadvancedweapons", 23: "rb_shield-generator", 24: "rb_hypervelocitygun",
    27: "eaw_bespinBuilding1", 28: "eaw_corBuild3", 29: "eb_commandcenter", 30: "nb_commjamstation", 31: "ub_heavyfactory",
}


def fit(render, size):
    im = Image.open(RENDERS + render + "_raw.png").convert("RGBA")
    im = im.crop(im.getbbox())
    im.thumbnail((size, size), Image.LANCZOS)
    a = im.getchannel("A")    # EaW greys vanish on the dark tile: brighter, more contrast, a faint light rim
    im = ImageEnhance.Contrast(ImageEnhance.Brightness(im.convert("RGB")).enhance(1.6)).enhance(1.25).convert("RGBA")
    im.putalpha(a)
    rim = Image.new("RGBA", im.size, (210, 220, 230, 0))
    rim.putalpha(a.filter(ImageFilter.MaxFilter(3)).point(lambda v: v * 0.35))
    rim.alpha_composite(im)
    return rim


def strip():
    src = Image.open(GAME + STRIP).convert("RGBA")
    assert src.width // FRAME == 31, src.size
    tile = src.crop((0, 0, FRAME, FRAME))
    px = tile.load()
    bg = px[FRAME // 2, 3]
    for x in range(FRAME):            # the empty tile: frame 1 with its pictogram painted over in the tile colour
        for y in range(FRAME):
            r, g, b, _ = px[x, y]
            if (4 <= x < FRAME - 4 and 4 <= y < FRAME - 4) or max(r, g, b) - min(r, g, b) > 40:
                px[x, y] = bg
    out = src.copy()
    for frame, render in ICONS.items():
        cell = tile.copy()
        im = fit(render, FRAME - 8)
        shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        shadow.putalpha(im.getchannel("A").point(lambda a: a * 0.7).filter(ImageFilter.GaussianBlur(1.5)))
        x, y = (FRAME - im.width) // 2, (FRAME - im.height) // 2
        cell.alpha_composite(shadow, (x + 1, y + 2))
        cell.alpha_composite(im, (x, y))
        out.paste(cell, ((frame - 1) * FRAME, 0))
    out.save(STRIP)


if __name__ == "__main__":
    lines = ["l_english:", " # base_building_skin.py: Star Wars names for the vanilla buildings"]
    for k, (n, p, d) in NAMES.items():
        lines += [f' {k}:0 "{n}"', f' {k}_plural:0 "{p}"', f' {k}_desc:0 "{d}"']
    open(LOC, "w", encoding="utf-8-sig", newline="\n").write("\n".join(lines) + "\n")
    strip()
    print(len(NAMES), "buildings renamed;", len(ICONS), "icons")
