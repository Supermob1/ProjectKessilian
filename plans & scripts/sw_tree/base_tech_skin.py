"""Star Wars names + icons for the vanilla industry and engineering techs (user 2026-11-09: "replace just the names and icons
of the base tech"). The techs, effects and positions stay vanilla.

    python -B "plans & scripts/sw_tree/base_tech_skin.py"      then tech_tag_names.py (it reads NAMES from here)

- NAMES: tech -> (Republic name, Separatist name, Separatist desc or None, Republic / neutral desc). The plain keys (every
  other country) get the Republic name in localisation/english/replace/hod_base_tech_l_english.yml; tech_tag_names.py
  writes the per-faction ones.
- ICONS: tech -> render of an Empire at War structure (WIPGFX/3d/_renders/buildings/<name>_raw.png). Written 64x64 over the
  vanilla texture path of the tech's sprite (gfx/interface/technologies/...), so no sprite is redefined.
"""
import glob, os, re
from PIL import Image, ImageEnhance, ImageFilter

GAME = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV/"
RENDERS = "../ProjectKessilianWIPGFX/ProjectKessilianWIP/3d/_renders/buildings/"
LOC = "localisation/english/replace/hod_base_tech_l_english.yml"

N = lambda r, c, rd, cd=None: (r, c, cd, rd)
NAMES = {
    # production
    "basic_machine_tools": N("Fabrication Droids", "Assembly Droid Lines", "Fabrication droids take over the simplest jobs on the factory floor.",
                             "Assembly droids stamp out parts around the clock."),
    "improved_machine_tools": N("Precision Fabricators", "Precision Assembly Droids", "Finer fabricators turn out parts that fit first time."),
    "advanced_machine_tools": N("Foundry Worlds", "Geonosian Hive Foundries", "Whole planets given over to war production.",
                                "The Geonosian hives build with an insect's tireless efficiency."),
    "assembly_line_production": N("Kuat Assembly Lines", "Baktoid Assembly Lines", "One standard hull, one standard line, endless output.",
                                  "Baktoid Armor Workshop turns out droids and AATs by the million."),
    "flexible_line": N("Modular Foundry Lines", "Reprogrammable Foundries", "Lines that switch from one design to the next in days.",
                       "Foundry droids are simply reprogrammed for the next design."),
    "streamlined_line": N("Standardised Hull Lines", "Mass Droid Foundries", "Fewer designs, built faster.",
                          "One droid design, built in numbers no living army can match."),
    "improved_equipment_conversion": N("Refit Yards", "Collector Droids", "Engineers refit old equipment to the new standard.",
                                       "Collector droids drag every wreck back to be rebuilt."),
    "advanced_equipment_conversion": N("Battlefield Salvage Teams", "Droid Rebuild Lines", "Every wreck stripped for parts and rebuilt.",
                                       "Damaged droids are rebuilt on the spot."),
    "concentrated_industry": N("Core World Industry I", "Foundry World Industry I", "War production concentrated on the great industrial worlds."),
    "concentrated_industry2": N("Core World Industry II", "Foundry World Industry II", "War production concentrated on the great industrial worlds."),
    "concentrated_industry3": N("Core World Industry III", "Foundry World Industry III", "War production concentrated on the great industrial worlds."),
    "concentrated_industry4": N("Core World Industry IV", "Foundry World Industry IV", "War production concentrated on the great industrial worlds."),
    "concentrated_industry5": N("Core World Industry V", "Foundry World Industry V", "War production concentrated on the great industrial worlds."),
    "dispersed_industry": N("Sector Industry I", "Outer Rim Holdings I", "Small plants on many worlds: no bombardment can stop them all."),
    "dispersed_industry2": N("Sector Industry II", "Outer Rim Holdings II", "Small plants on many worlds: no bombardment can stop them all."),
    "dispersed_industry3": N("Sector Industry III", "Outer Rim Holdings III", "Small plants on many worlds: no bombardment can stop them all."),
    "dispersed_industry4": N("Sector Industry IV", "Outer Rim Holdings IV", "Small plants on many worlds: no bombardment can stop them all."),
    "dispersed_industry5": N("Sector Industry V", "Outer Rim Holdings V", "Small plants on many worlds: no bombardment can stop them all."),
    # fuel, doonium (rubber), refining
    "fuel_silos": N("Fuel Depots", "Fuel Depots", "Tank farms that stock fuel for the fleets and armies."),
    "fuel_refining": N("Tibanna Refining I", "Hyperfuel Refining I", "Better refining gets more fuel out of every load of Tibanna gas."),
    "fuel_refining2": N("Tibanna Refining II", "Hyperfuel Refining II", "Better refining gets more fuel out of every load of Tibanna gas."),
    "fuel_refining3": N("Tibanna Refining III", "Hyperfuel Refining III", "Better refining gets more fuel out of every load of Tibanna gas."),
    "fuel_refining4": N("Tibanna Refining IV", "Hyperfuel Refining IV", "Better refining gets more fuel out of every load of Tibanna gas."),
    "fuel_refining5": N("Tibanna Refining V", "Hyperfuel Refining V", "Better refining gets more fuel out of every load of Tibanna gas."),
    "synth_oil_experiments": N("Hyperfuel Synthesis", "Hyperfuel Synthesis", "Fuel synthesized from local resources where no Tibanna gas is found."),
    "oil_processing": N("Fuel Synthesizers I", "Fuel Synthesizers I", "Synthesizers that make fuel from local resources."),
    "improved_oil_processing": N("Fuel Synthesizers II", "Fuel Synthesizers II", "Synthesizers that make fuel from local resources."),
    "advanced_oil_processing": N("Fuel Synthesizers III", "Fuel Synthesizers III", "Synthesizers that make fuel from local resources."),
    "modern_oil_processing": N("Fuel Synthesizers IV", "Fuel Synthesizers IV", "Synthesizers that make fuel from local resources."),
    "rubber_processing": N("Doonium Synthesis I", "Doonium Synthesis I", "Synthesizers that make doonium from local resources."),
    "improved_rubber_processing": N("Doonium Synthesis II", "Doonium Synthesis II", "Synthesizers that make doonium from local resources."),
    "advanced_rubber_processing": N("Doonium Synthesis III", "Doonium Synthesis III", "Synthesizers that make doonium from local resources."),
    "modern_rubber_processing": N("Doonium Synthesis IV", "Doonium Synthesis IV", "Synthesizers that make doonium from local resources."),
    # construction, extraction
    "construction1": N("Construction Droids I", "Construction Droid Swarms I", "Construction droids raise buildings in days instead of months."),
    "construction2": N("Construction Droids II", "Construction Droid Swarms II", "Construction droids raise buildings in days instead of months."),
    "construction3": N("Prefabricated Structures", "Prefabricated Foundations", "Whole buildings shipped in sections and set down where needed."),
    "construction4": N("Megastructure Engineering", "Hive Megastructures", "Engineering on the scale of whole city blocks."),
    "construction5": N("Planetary Engineering", "Planetary Engineering", "Reshaping the face of a planet for the war effort."),
    "excavation1": N("Mining Droids I", "Mining Droid Swarms I", "Mining droids dig where no living miner could go."),
    "excavation2": N("Mining Droids II", "Mining Droid Swarms II", "Mining droids dig where no living miner could go."),
    "excavation3": N("Asteroid Mining", "Asteroid Mining", "Mining rigs strip the asteroid belts."),
    "excavation4": N("Deep-Core Mining", "Deep-Core Mining", "Shafts sunk down to the planet's core."),
    "excavation5": N("Gas Giant Harvesting", "Gas Giant Harvesting", "Floating rigs harvest whole gas giants."),
    # engineering: comms, sensors, computing, slicing, fire control
    "electronic_mechanical_engineering": N("Galactic Engineering Corps", "Techno Union Laboratories", "The Republic's engineers and scientists put to war work.",
                                           "Techno Union laboratories develop the Confederacy's weapons."),
    "radio": N("Comlinks", "Droid Control Signals", "Secure comlinks from the command post to the front.", "Battle droids take their orders over coded control signals."),
    "improved_radio": N("HoloNet Relays", "Central Control Relays", "Relay stations that link the fleets over the HoloNet.",
                        "Relay ships pass the central computers' orders to every droid."),
    "advanced_radio": N("Hyperwave Transceivers", "Hyperwave Command Uplinks", "Real-time holo-calls across the galaxy.", "The droid armies act as one."),
    "cavity_magnatron": N("Sensor Arrays", "Sensor Arrays", "Sensor arrays that track ships, starfighters and vehicles."),
    "centimetric_radar": N("Long-Range Scanners", "Long-Range Scanners", "Scanners that see enemy fleets long before they arrive."),
    "phased_array": N("Planetary Sensor Grids", "Planetary Sensor Grids", "A sensor net that covers the whole planet."),
    "monopulse_radar": N("Hyperspace Trackers", "Hyperspace Trackers", "Sensors that follow ships into hyperspace."),
    "mechanical_computing": N("Battle Analysis Computers", "Droid Brains", "Computers that help commanders read the battle.",
                              "Better droid brains: the battle droids think a little faster."),
    "computing_machine": N("Strategic Computers", "Tactical Droid Processors", "Computers that plan supply and movement.", "Tactical droids calculate the odds of every battle."),
    "improved_computing_machine": N("Tactical Data Cores", "Super Tactical Droid Cores", "Data cores holding every battle the Republic has fought.",
                                    "Super tactical droids command whole armies by themselves."),
    "advanced_computing_machine": N("HoloNet Strategic Archive", "Central Droid Control Computers", "The war's records and plans in one archive.",
                                    "The central computers that run the whole droid army."),
    "basic_encryption": N("Code Cylinders", "Droid Signal Encryption", "Officers carry code cylinders that open secure channels.", "Coded signals the enemy cannot read."),
    "improved_encryption": N("Rotating Cipher Keys", "Rotating Command Ciphers", "Cipher keys that change with every transmission."),
    "advanced_encryption": N("Republic Cipher Keys", "Quantum-Lock Encryption", "Ciphers that even slicer droids cannot break.", "Encryption no Republic slicer can crack."),
    "basic_decryption": N("Slicer Teams", "Slicer Droids", "Slicers break into enemy computers.", "Droids that slice into enemy networks."),
    "improved_decryption": N("Signal Intelligence", "Signal Interception Droids", "Listening posts that read the enemy's traffic.", "Droids that never stop listening."),
    "advanced_decryption": N("Codebreaking Computers", "Codebreaking Computers", "Computers that crack enemy ciphers in hours."),
    "basic_fire_control_system": N("Targeting Computers", "Targeting Computers", "Computer-aided aim for turbolaser batteries."),
    "improved_fire_control_system": N("Tracking Computers", "Tracking Computers", "Faster computers that lead fast-moving starfighters."),
    "advanced_fire_control_system": N("Predictive Fire Control", "Predictive Fire Control", "Fire control that aims where the enemy will be."),
    # defences, hypermatter
    "basic_fortification_tech": N("Ferrocrete Bunkers", "Droid Bunkers", "Ferrocrete strongpoints for the clone garrisons.", "Armoured bunkers raised by construction droids."),
    "land_fort_tech_1": N("Deflector Shield Generators", "Deflector Shield Generators", "Shield generators that cover a defensive position."),
    "land_fort_tech_2": N("Planetary Shield Generators", "Planetary Shield Generators", "Shield generators that cover a whole battlefield."),
    "coastal_fort_tech_1": N("Turbolaser Batteries", "Turbolaser Batteries", "Turbolaser towers that guard the landing zones."),
    "coastal_fort_tech_2": N("Planetary Ion Cannons", "Planetary Ion Cannons", "Ion cannons that can fire on ships in orbit."),
    "atomic_research": N("Hypermatter Physics", "Hypermatter Physics", "Research into hypermatter, the power behind starship reactors."),
}

ICONS = {   # tech -> render
    **dict.fromkeys(["basic_machine_tools", "improved_machine_tools"], "eb_lightfactory"),
    "advanced_machine_tools": "rb_heavyvehiclefactory", "assembly_line_production": "eb_vehiclefactory",
    "flexible_line": "rb_lightvehiclefactory", "streamlined_line": "ub_droidworks",
    "improved_equipment_conversion": "eb_repairfacility", "advanced_equipment_conversion": "nb_abandon_mining",
    **dict.fromkeys([f"concentrated_industry{i}" for i in ("", 2, 3, 4, 5)], "ub_heavyfactory"),
    **dict.fromkeys([f"dispersed_industry{i}" for i in ("", 2, 3, 4, 5)], "rb_lightvehiclefactory"),
    "fuel_silos": "fuelcellc", **dict.fromkeys([f"fuel_refining{i}" for i in ("", 2, 3, 4, 5)], "tibanna"),
    "synth_oil_experiments": "fuelcella",
    **dict.fromkeys(["oil_processing", "improved_oil_processing", "advanced_oil_processing", "modern_oil_processing"], "fuelcella"),
    **dict.fromkeys(["rubber_processing", "improved_rubber_processing", "advanced_rubber_processing", "modern_rubber_processing"], "nb_cmc22mining"),
    **dict.fromkeys(["construction1", "construction2"], "eb_commandcenter"), "construction3": "nb_bunker",
    "construction4": "eb_governorsquarters", "construction5": "eb_megaadvancedweapons",
    **dict.fromkeys(["excavation1", "excavation2"], "nb_cmc22mining"), "excavation3": "nb_asteroidmining_full",
    "excavation4": "nb_cmc22mining", "excavation5": "tibanna",
    "electronic_mechanical_engineering": "eb_researchfacility",
    **dict.fromkeys(["radio", "improved_radio", "advanced_radio"], "rb_comcenter"),
    **dict.fromkeys(["cavity_magnatron", "centimetric_radar", "phased_array", "monopulse_radar"], "nb_sensornode"),
    "mechanical_computing": "eb_researchfacility", "computing_machine": "rb_researchfacility",
    "improved_computing_machine": "eb_megaadvancedweapons", "advanced_computing_machine": "eb_researchfacility",
    **dict.fromkeys(["basic_encryption", "improved_encryption", "advanced_encryption", "basic_decryption", "improved_decryption",
                     "advanced_decryption"], "nb_commjamstation"),
    **dict.fromkeys(["basic_fire_control_system", "improved_fire_control_system"], "eb_aaturret"), "advanced_fire_control_system": "rb_hypervelocitygun",
    "basic_fortification_tech": "nb_bunker", "land_fort_tech_1": "nb_baseshieldgen", "land_fort_tech_2": "rb_shield-generator",
    "coastal_fort_tech_1": "eb_tltower", "coastal_fort_tech_2": "rb_ioncannon", "atomic_research": "eb_gravcontrolgen",
}


def techs():
    out = []
    for f in ("industry", "electronic_mechanical_engineering"):
        t = open(f"common/technologies/{f}.txt", encoding="utf-8-sig").read()
        out += [k for k, b in re.findall(r"\n\t(\w+) = \{(.*?)\n\t\}", t, re.S) if re.search(r"name = (industry|electronics)_folder", b)]
    return out


def sprite_textures():
    spr = {}
    for f in glob.glob(GAME + "interface/*.gfx"):
        for m in re.finditer(r'name\s*=\s*"(GFX_\w+_medium)"\s*texture[fF]ile\s*=\s*"([^"]+)"', open(f, encoding="utf-8-sig", errors="ignore").read()):
            spr.setdefault(m.group(1), m.group(2))
    return spr


def icon(render):
    im = Image.open(RENDERS + render + "_raw.png").convert("RGBA")
    im = im.crop(im.getbbox())
    im.thumbnail((60, 60), Image.LANCZOS)
    a = im.getchannel("A")   # EaW greys vanish on the dark tech items: brighter, more contrast, a faint light rim
    im = ImageEnhance.Contrast(ImageEnhance.Brightness(im.convert("RGB")).enhance(1.6)).enhance(1.25).convert("RGBA")
    im.putalpha(a)
    rim = Image.new("RGBA", im.size, (210, 220, 230, 0))
    rim.putalpha(a.filter(ImageFilter.MaxFilter(3)).point(lambda v: v * 0.35))
    rim.alpha_composite(im)
    cell = Image.new("RGBA", (64, 64))
    shadow = Image.new("RGBA", rim.size, (0, 0, 0, 0))
    shadow.putalpha(a.point(lambda v: v * 0.6).filter(ImageFilter.GaussianBlur(2)))
    x, y = (64 - rim.width) // 2, (64 - rim.height) // 2
    cell.alpha_composite(shadow, (x + 2, y + 2))
    cell.alpha_composite(rim, (x, y))
    return cell


if __name__ == "__main__":
    ts = techs()
    assert set(ts) == set(NAMES) == set(ICONS), (set(ts) ^ set(NAMES), set(ts) ^ set(ICONS))
    spr = sprite_textures()
    done = {}
    for t in ts:
        path = spr[f"GFX_{t}_medium"]
        assert done.setdefault(path, ICONS[t]) == ICONS[t], (t, path)   # techs sharing a texture must share the render
        os.makedirs(os.path.dirname(path), exist_ok=True)
        icon(ICONS[t]).save(path)
    lines = ["l_english:", " # base_tech_skin.py: Star Wars names for the vanilla industry / engineering techs"]
    lines += [f' {t}:0 "{NAMES[t][0]}"\n {t}_desc:0 "{NAMES[t][3]}"' for t in ts]
    open(LOC, "w", encoding="utf-8-sig", newline="\n").write("\n".join(lines) + "\n")
    print(len(ts), "techs named;", len(done), "icon textures")
