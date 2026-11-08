# Clone Wars timeline map for the imported Executor tree.
# 976 = 22 BBY (Geonosis), 979 = 19 BBY (Order 66), 998 = 0 BBY.  year = 998 - BBY
# Old row (current year after the -960 shift) -> new year. Rows keep their grid position.
ROW = {958: 976, 976: 976, 977: 977, 978: 977, 979: 978, 980: 978, 981: 979, 982: 979,
       983: 980, 984: 981, 985: 983, 986: 985, 987: 987, 988: 990}

T = "gfx/interface/technologies/"
GAP = "GAP"  # no fitting icon exists yet

# tech: (name, desc, icon)   icon None = keep current, path = swap, GAP = still needs art
TECH = {
    # ---- Air ----
    "laat": ("RM-09 Shuttle", "A light armed shuttle that lifts a clone platoon into the fight and covers its landing with twin laser cannons.", None),
    "maat": ("LAAT/le Patrol Gunship", "A lighter, faster LAAT variant for patrol, escort and rapid redeployment.", None),
    "idt": ("Nu-class Attack Shuttle", "Armoured shuttles that drop officers, specialists and assault teams behind the lines.", GAP),
    "tie-rp": ("Theta-class T-2c Shuttle", "A late-war armoured shuttle with folding wings, built for fast insertion under fire.", GAP),
    "aal": ("Atmospheric Assault Lander", "Imperial-era landers that set whole companies down in a single wave.", None),
    "torrent": ("T-16 Skyhopper", "Incom's fast civilian airspeeder, pressed into service with a light laser cannon while the clone factories spin up.", None),
    "z-95": ("V-19 Torrent", "The first starfighter mass-produced for the Grand Army: rugged, simple and well armed.", None),
    "tie-rb": ("Eta-2 Actis Interceptor", "A late-war Kuat design, fast and agile, that points the way to the TIE line.", GAP),
    "tie_fighter": ("TIE/ln Starfighter", "Twin ion engines and no shields: a fighter built in vast numbers for the new order.", None),
    "tie-sf": ("TIE/rb Heavy Starfighter", "A heavily armoured TIE with a rotating cannon, built to support ground assaults.", T + "tie-rb.dds"),
    "v_wing": ("Delta-7 Aethersprite", "The Jedi light interceptor: small, nimble and paired with an external hyperdrive ring.", GAP),
    "tie-in": ("Alpha-3 Nimbus V-wing", "A short-range clone interceptor fielded in swarms in the last years of the war.", T + "v_wing.dds"),
    "tie-sk": ("Delta-7B Aethersprite", "The refined Aethersprite, with an astromech socket and better weapons.", GAP),
    "tie-vn": ("TIE/IN Interceptor", "A dagger-winged TIE with four cannons, the fastest fighter in the Imperial fleet.", T + "tie_interceptor.dds"),
    "tie-ba": ("TIE/sk Striker", "An atmospheric TIE for planetary patrol and close air support.", T + "tie-sk.dds"),
    "arc-170": ("ARC-170 Starfighter", "A heavy clone fighter with a tail gunner and the endurance for long patrols.", None),
    "tie_defender": ("TIE Advanced x1", "A shielded, hyperdrive-equipped TIE prototype for elite pilots.", T + "advanced_x1.dds"),
    "y-wing": ("BTL-B Y-wing", "A tough clone bomber with an ion cannon turret and a deep proton bomb bay.", None),
    "skipray": ("BTL-A4 Y-wing", "The late-war Y-wing refit: stripped-down hull, heavier shields and a bigger bomb load.", None),
    "tie-sa": ("NTB-630 Naval Bomber", "The Republic's heavy bomber, flown in waves against capital ships and fortifications.", GAP),
    "scimitar": ("TIE/sa Bomber", "The twin-pod TIE bomber, built for precise orbital and ground strikes.", T + "tie_bomber.dds"),
    # ---- Artillery ----
    "mortar": ("Clone Mortar Teams", "Portable mortars that give every clone company its own indirect fire.", None),
    "spha": ("SPHA Walker", "The Self-Propelled Heavy Artillery walker, whose turbolaser broke the droid lines at Geonosis.", None),
    "spma": ("SPMA-T Turbolaser Artillery", "A self-propelled turbolaser platform for sieges and orbital defence.", None),
    "utat_art": ("UT-AT Artillery Walker", "The Unstable Terrain Artillery Transport: a low armoured hull with twin heavy cannons that shells the line from rough ground.", None),
    "advanced_spg": ("J-1 Proton Cannon", "A walking proton cannon whose shells crack shields and fortress walls from beyond the horizon.", None),
    "atap": ("AT-AP Walker", "The All Terrain Attack Pod: a three-legged walker with a long-range cannon.", None),
    "av7": ("AV-7 Antivehicle Cannon", "A mobile cannon that anchors itself and breaks enemy armour at range.", None),
    "advanced_at": ("AV-7 Mk II Antivehicle Cannon", "A heavier AV-7 that anchors itself and breaks enemy armour at longer range.", None),
    "rx": ("UT-AA Anti-Air Tank", "A tracked anti-air battery that tracks starfighters and gunships.", None),
    "ataa": ("AT-AA Walker", "A four-legged anti-air walker that tracks starfighters and gunships.", None),
    "advanced_aa": ("UT-AA Mk II Air Defence Tank", "An up-gunned UT-AA with better fire control against fast strike craft.", None),
    # ---- Infantry ----
    "republic_weapon1": ("DC-15A Blaster Rifle", "The standard long rifle of the Grand Army of the Republic.", None),
    "imperial_weapons": ("DC-15S Blaster Carbine", "A short carbine that suits close fighting in cities and ships.", T + "phase_I_equipment_medium.dds"),
    "imperial_thermal_detonator": ("Thermal Detonators", "Compact baradium grenades issued to every infantry squad.", None),
    "imperial_weapons2": ("DC-17m Interchangeable Weapon System", "The commando rifle that switches between blaster, sniper and anti-armour modes.", T + "phase_II_equipment_medium.dds"),
    "imperial_anti_tank": ("Infantry Anti-Armour Launchers", "Squad rocket launchers to stop walkers and hover tanks.", T + "REP_infantry_at_medium.dds"),
    "firstorder_weapons": ("E-11 Blaster Rifle", "The compact Imperial service rifle, cheap and reliable.", T + "Imperial_equipment_medium.dds"),
    "special_training": ("Special Training", "Selected troopers learn infiltration, demolition and independent action.", T + "advanced_training_programs_medium.dds"),
    "advanced_special_training": ("ARC Trooper Training", "Advanced Recon Commandos are trained to lead from the front.", T + "arc_commandos_medium.dds"),
    "improved_special_training": ("Kaminoan Conditioning", "Refined genetic conditioning makes troopers tougher and more loyal.", T + "kaminoan_genetic_conditioning_medium.dds"),
    "advanced_special_training2": ("Clone Commando Squads", "Four-man commando squads for the war's most dangerous missions.", T + "arc_commandos_medium.dds"),
    "improved_special_training2": ("Airborne Assault Doctrine", "Troopers train to fight straight out of the gunship.", T + "laat_infantry_medium.dds"),
    "elite_troopers": ("Elite Troopers", "Veterans formed into elite units with the best equipment.", T + "imperial_commandos_medium.dds"),
    "atot": ("AT-OT Walker", "The All Terrain Open Transport carries a full company across any ground.", None),
    "basic_hovercrafts": ("Repulsor Transports", "Mass-produced repulsor craft and Conveyex lines to move armies.", None),
    "rtt": ("Republic Troop Transport", "An armoured repulsor transport for mechanised clone infantry.", None),
    "itt": ("AT-TC Troop Carrier", "A tracked, heavily armoured carrier with twin side turrets that drives a full platoon through fire.", None),
    "itc": ("K79-S80 Troop Transport", "A repulsorlift troop transport with heavy armour and side turrets, fast enough to keep up with the armour.", None),
    "juggernaut": ("HAVw A6 Juggernaut", "A ten-wheeled armoured giant that carries fifty troopers into battle.", None),
    "isp": ("Infantry Support Platform", "A twin-cannon repulsor platform that keeps up with the infantry.", None),
    "barc": ("BARC Speeder", "Fast clone speeder bikes for scouts and dispatch riders.", None),
    "ava": ("614-AvA Speeder", "An armed Imperial-era speeder bike for patrol and pursuit.", None),
    "z_speeder": ("74-Z Speeder Bike", "The light, fast speeder of the scout troopers.", None),
    # ---- Armour ----
    "republic_tank": ("TX-130 Saber Tank", "A fast hover tank built to hunt droid armour.", "gfx/interface/technologies/hod_render/tx130_medium.dds"),
    "tx130t": ("TX-130T Fighter Tank", "An up-gunned Saber with heavier armour and more cannons.", "gfx/interface/technologies/hod_render/tx130t_small.dds"),   # refit tech: small 64 px icon
    "repulsor": ("TX-130S Saber-class Fighter Tank", "The Clone Wars refit of the Saber: twin laser cannons, heavier shields and a gunner in the open hatch.", "gfx/interface/technologies/hod_render/tx130s_medium.dds"),
    "h_repulsor": ("T4-B Heavy Tank", "A twin-turreted repulsorlift heavy tank: slow, but its armour shrugs off most infantry and light vehicle fire.", None),
    "mauler": ("Scout-class 2-M Repulsor Tank", "A faster scout variant of the 2-M Saber; opens armoured scout companies.", "gfx/interface/technologies/hod_render/saber2m_small.dds"),   # refit tech
    "px": ("AAC-1 Speeder Tank", "A heavy repulsorlift hover tank with twin laser cannons and a missile launcher on its turret.", None),
    # 2026-11-08 (user): the crawler tech now unlocks the 2-M Saber (imperialtank); the last tech is a refit
    "crawler": ("2-M Saber-class Repulsor Tank", "A fast repulsor tank with a heavy laser cannon, built to outrun and outgun droid armour.", "gfx/interface/technologies/hod_render/saber2m_medium.dds"),
    "imperial_tank": ("Repulsor Tank Refit", "Better repulsorlifts, shielding and cannons for the newest hover tanks: every assault vehicle battalion hits harder, lasts longer and moves faster.", "gfx/interface/technologies/hod_render/saber2m_small.dds"),
    # walker line shifted one tech (2026-11-08): Lance walker first, AT-DP dropped
    "atrt": ("Lance Walker", "The Old Republic's two-legged Lance walker, still the backbone of planetary guards when the war began.", "gfx/interface/technologies/hod_render/lance_medium.dds"),
    "atrct": ("AT-RT Walker", "A one-trooper recon walker that runs ahead of the main force.", "gfx/interface/technologies/hod_render/atrt_medium.dds"),
    "atpt": ("AT-XT Walker", "An experimental two-legged transport walker of the early war.", "gfx/interface/technologies/hod_render/atxt_medium.dds"),
    "atdp": ("AT-AP Walker", "A tripod artillery walker that braces on its third leg to fire its heavy cannon.", "gfx/interface/technologies/hod_render/atap_medium.dds"),
    "atst": ("AT-ST Walker", "The scout transport walker, first fielded in the last days of the war.", T + "atst.dds"),
    "foatst": ("Heavy AT-ST", "An up-armoured AT-ST with heavier cannons.", None),
    "atte": ("AT-TE Walker", "The six-legged assault walker that carried the Republic through the Clone Wars.", "gfx/interface/technologies/hod_render/atte_medium.dds"),
    "utat": ("UT-AT Walker", "An Unstable Terrain walker with a heavy cannon and room for troops.", None),
    "utat_tech": ("UT-AT Walker", "An Unstable Terrain walker with a heavy cannon and room for troops.", None),
    "atat_tech": ("AT-AT Prototype", "Kuat's first All Terrain Armoured Transports, tested in the war's final months.", T + "rep_walker_atat_kuat_medium.dds"),
    "elite_atat_tech": ("AT-AT Walker", "The four-legged giant of the Imperial army.", None),
    "fo_atat_tech": ("AT-ACT Walker", "A cargo-carrying AT-AT variant for armed logistics.", None),
    "atm6": ("AT-AT Heavy Assault Walker", "A heavier AT-AT built to breach planetary shields and fortresses.", None),
    # ---- Support ----
    "imp_support_eq": ("Support Equipment", "Tools, vehicles and stores for support companies.", None),
    # ---- Naval (space) hulls ----
    "imp_tech_dd_1": ("CR90 Corvette", "A fast Corellian corvette for escort and picket duty.", GAP),
    "imp_tech_dd_2": ("Pelta-class Frigate", "A sturdy frigate serving as escort, medical ship and command post.", GAP),
    "imp_tech_dd_3": ("Raider-class Corvette", "An Imperial-era corvette built to hunt smugglers and raiders.", GAP),
    "imp_tech_cl_1": ("Consular-class Cruiser", "The red diplomatic cruiser, refitted with guns for war.", GAP),
    "imp_tech_cl_2": ("Arquitens-class Light Cruiser", "A light cruiser with heavy turbolaser batteries for its size.", GAP),
    "imp_tech_cl_3": ("Carrack-class Light Cruiser", "A fast Imperial-era light cruiser for patrol and escort.", GAP),
    "imp_tech_ca_1": ("Acclamator I-class Assault Ship", "The assault ship that carried the first clone army to Geonosis.", GAP),
    "imp_tech_ca_2": ("Victory I-class Star Destroyer", "A late-war Star Destroyer built for planetary assault.", GAP),
    "imp_tech_ca_3": ("Victory II-class Star Destroyer", "A faster, better armed Victory for deep-space combat.", GAP),
    "imp_tech_bb_1": ("Dreadnaught-class Heavy Cruiser", "An old Rendili heavy cruiser that still holds the line.", GAP),
    "imp_tech_bb_2": ("Mandator II-class Star Dreadnought", "A huge Kuat dreadnought that rules the space around a world.", GAP),
    "imp_tech_bb_3": ("Imperial I-class Star Destroyer", "The dagger-shaped warship that will become the symbol of the Empire.", GAP),
    "imp_tech_cv_1": ("Acclamator II-class Assault Carrier", "An Acclamator refit with hangars for gunships and fighters.", GAP),
    "imp_tech_cv_2": ("Venator-class Star Destroyer", "The great carrier of the Clone Wars, launching hundreds of fighters.", GAP),
    "imp_tech_cv_3": ("Quasar Fire-class Cruiser-Carrier", "An Imperial-era carrier converted from a bulk cruiser.", GAP),
    "imp_tech_ss_1": ("Stealth Picket Corvette", "A small corvette fitted with an experimental cloaking device.", GAP),
    "imp_tech_ss_2": ("Republic Stealth Corvette", "A cloaked corvette that slips through blockades.", GAP),
    "imp_tech_ss_3": ("Cloaked Raider Frigate", "A larger cloaked raider that strikes shipping from the shadows.", GAP),
    # ---- Naval (space) systems ----
    "imp_tech_artillery_1": ("Light Turbolaser Batteries", "Turbolasers scaled down for frigates and corvettes.", GAP),
    "imp_tech_artillery_2": ("Twin Heavy Turbolasers", "Paired heavy turbolasers for the main batteries of capital ships.", GAP),
    "imp_tech_artillery_3": ("Quad Turbolaser Arrays", "Four-barrelled turbolaser mounts for Star Destroyers.", GAP),
    "imp_tech_armor_1": ("Durasteel Hull Plating", "Thick durasteel plating to soak up enemy fire.", GAP),
    "imp_tech_armor_2": ("Layered Durasteel Armour", "Layered armour that spreads the force of hits.", GAP),
    "imp_tech_armor_3": ("Quadanium Armour Plating", "Hard quadanium plating for the heaviest warships.", GAP),
    "imp_tech_fire_control_1": ("Targeting Computers Mk I", "Ship targeting computers that lead fast-moving targets.", GAP),
    "imp_tech_fire_control_2": ("Targeting Computers Mk II", "Better sensors and processors for faster firing solutions.", GAP),
    "imp_tech_fire_control_3": ("Targeting Computers Mk III", "Fleet-linked fire control for coordinated broadsides.", GAP),
    "imp_tech_torpedo_1": ("Proton Torpedoes", "Warheads that punch through shields and armour.", GAP),
    "imp_tech_torpedo_2": ("Concussion Missiles", "Fast missiles for close-range ship combat.", GAP),
    "imp_tech_torpedo_3": ("Diamond-Boron Missiles", "Heavy missiles that can cripple a capital ship.", GAP),
    "imp_tech_aa_1": ("Point-Defence Laser Cannons", "Rapid-fire lasers that fend off fighters and bombers.", GAP),
    "imp_tech_aa_2": ("Point-Defence Arrays", "Linked point-defence batteries that cover the whole hull.", GAP),
    "imp_tech_secondaries_1": ("Light Ion Cannons", "Ion cannons that knock out enemy shields and systems.", GAP),
    "imp_tech_secondaries_2": ("Heavy Ion Cannons", "Heavy ion batteries that can disable a capital ship.", GAP),
    "imp_tech_engine_1": ("Sublight Ion Engines", "Reliable ion engines for warships of every size.", GAP),
    "imp_tech_engine_2": ("Improved Ion Drives", "More powerful drives for faster fleets.", GAP),
    "imp_tech_engine_3": ("Hypermatter Reactors", "Hypermatter cores that feed the biggest engines and guns.", GAP),
    "imp_tech_sonar_1": ("Sensor Arrays", "Long-range sensors to find enemy ships before they find you.", GAP),
    "imp_tech_sonar_2": ("Advanced Sensor Suites", "Sensors that see through jamming and debris.", GAP),
    "imp_tech_deflector_1": ("Deflector Shields I", "Energy shields that stop turbolaser fire.", GAP),
    "imp_tech_deflector_2": ("Deflector Shields II", "Stronger shield generators for capital ships.", GAP),
    "imp_tech_radar_3": ("Long-Range Sensor Arrays", "Sensors that track fleets across a whole system.", GAP),
    "imp_tech_transport_1": ("Planetary Landing Craft", "Landing craft to put armies onto hostile worlds.", GAP),
    "imp_tech_transport_2": ("Assault Landing Barges", "Armoured barges for landings under fire.", GAP),
    "imp_tech_transport_3": ("Planetary Assault Fleet", "Whole fleets built to invade a planet in one blow.", GAP),
}

# support lines: neutral names (no "Imperial"), icons are generic so they stay
for base, label in [("imp_tech_engineers", "Combat Engineers"), ("imp_tech_recon", "Scout Company"),
                    ("imp_tech_military_police", "Military Police"), ("imp_tech_maintenance_company", "Maintenance Company"),
                    ("imp_tech_field_hospital", "Medical Corps"), ("imp_tech_logistics_company", "Logistics Company"),
                    ("imp_tech_signal_company", "Communications Corps")]:
    for i, r in enumerate(["I", "II", "III", "IV"]):
        TECH[base + ("" if i == 0 else str(i + 1))] = (f"{label} {r}", f"Better training and kit for the {label.lower()}.", None)

# equipment / sub-unit / folder / category display names
NAME = {
    "laat_equipment": "RM-09", "laati_equipment": "LAAT/i Gunship", "maat_equipment": "LAAT/le",
    "maat_gunship_equipment": "LAAT/le Gunship", "idt_equipment": "Nu-class Shuttle",
    "idt_gunship_equipment": "Nu-class Attack Shuttle", "tie-rp_equipment": "Theta-class Shuttle",
    "tie-rp_gunship_equipment": "Theta-class Assault Shuttle", "aal_equipment": "Assault Lander",
    "aal_gunship_equipment": "Assault Lander Gunship", "torrent_equipment": "T-16 Skyhopper",
    "z-95_equipment": "V-19 Torrent", "tie-rb_equipment": "Eta-2 Actis", "tie_fighter_equipment": "TIE/ln",
    "tie-sf_equipment": "TIE/rb", "v_wing_equipment": "Delta-7 Aethersprite", "tie-in_equipment": "V-wing",
    "tie-sk_equipment": "Delta-7B Aethersprite", "tie-vn_equipment": "TIE/IN Interceptor", "tie-ba_equipment": "TIE/sk Striker",
    "arc-170_equipment": "ARC-170", "tie_defender_equipment": "TIE Advanced x1", "y-wing_equipment": "BTL-B Y-wing",
    "skipray_equipment": "BTL-A4 Y-wing", "tie_bomber_equipment": "NTB-630 Bomber", "scimitar_equipment": "TIE/sa Bomber",
    "imp_fighter_equipment": "Starfighter", "imp_bomber_equipment": "Bomber", "imp_interceptor_equipment": "Interceptor",
    "imp_defender_equipment": "Heavy Starfighter", "imp_gunship_equipment": "Gunship",
    "imperial_transport_plane_equipment": "Transport Gunship",
    "imperial_equipment_1": "DC-15S Blaster Carbine", "imperial_equipment_2": "DC-17m ICWS", "imperial_equipment_3": "E-11 Blaster Rifle",
    "republic_equipment_1": "DC-15A Blaster Rifle", "imperial_support_equipment_1": "Support Equipment",
    "imperial_support_equipment": "Support Equipment",
    "republictank": "TX-130 Saber", "tx130t_equipment": "TX-130T", "repulsor_equipment": "2-M Saber",
    "h_repulsor_equipment": "T4-B Heavy Tank", "px_equipment": "AAC-1",
    "crawler_equipment": "TIE/ca Crawler", "imperialtank": "2-M Saber", "atrct_equipment": "AT-RT",
    "atrt_equipment": "Lance Walker", "atpt_equipment": "AT-XT", "atdp_equipment": "AT-AP", "atst_equipment": "AT-ST", "fo_atst_equipment": "Heavy AT-ST", "atat_equipment": "AT-AT Prototype",
    "elite_atat_equipment": "AT-AT", "fo_atat_equipment": "AT-ACT", "atm6_equipment": "AT-AT Heavy Assault",
    "itt_equipment": "AT-TC", "itc_equipment": "K79-S80 Transport", "rtt_equipment": "Republic Troop Transport",
    "mortar_equipment": "Clone Mortar", "rx_equipment": "RX-200 Falchion", "advanced_spg_equipment": "HAVr A10 Siege Platform",
    "advanced_at_equipment": "HAVr A10 Tank Destroyer", "advanced_aa_equipment": "HAVr A10 Air Defence",
    "stormtrooper": "Shock Troopers", "imp_engineer": "Combat Engineers", "imp_recon": "Scout Company",
    "imp_military_police": "Military Police", "imp_maintenance_company": "Maintenance Company",
    "imp_field_hospital": "Medical Corps", "imp_signal_company": "Communications Corps", "imp_logistics_company": "Logistics Company",
    "stormtrooper_tech": "Shock Troopers", "stormtrooper_mountain": "Integrate Mountain Troopers",
    "stormtrooper_marine": "Integrate Marines", "stormtrooper_paratrooper": "Integrate Airborne Troopers",
    "swnaval_folder": "Starship Hulls", "swnaval_support_folder": "Starship Systems", "imperial_folder": "Special Projects",
    "imperial_tech": "Military Tech", "imperial_support": "Support Equipment", "imperial_aircraft_tech": "Starfighters",
    "tie_fighter": "Starfighter", "tie_heavy_fighter": "Heavy Starfighter", "tie_interceptor": "Interceptor",
    "tie_bomber": "Bomber", "tie_gunship": "Gunship",
    "ship_hull_light_imp": "Corvette Hull", "ship_hull_cruiser_light_imp": "Light Cruiser Hull",
    "ship_hull_cruiser_heavy_imp": "Star Destroyer Hull", "ship_hull_heavy_imp": "Dreadnought Hull",
    "ship_hull_carrier_imp": "Carrier Hull", "ship_hull_submarine_imp": "Stealth Ship Hull",
}
HULL = {"light": "dd", "cruiser_light": "cl", "cruiser_heavy": "ca", "heavy": "bb", "carrier": "cv", "submarine": "ss"}
for h, k in HULL.items():
    for i in (1, 2, 3):
        NAME[f"ship_hull_{h}_imp_{i}"] = TECH[f"imp_tech_{k}_{i}"][0]
        NAME[f"ship_hull_{h}_imp_{i}_short"] = TECH[f"imp_tech_{k}_{i}"][0].split("-class")[0]
NAME.update({"imp_destroyer": "Corvette", "imp_light_cruiser": "Light Cruiser", "imp_heavy_cruiser": "Star Destroyer",
             "imp_battleship": "Dreadnought", "imp_carrier": "Carrier", "imp_submarine": "Stealth Ship"})
del NAME["tie_fighter"]  # same key as the tech; TECH name wins
TECH["tie_defender"] = TECH["tie_defender"][:2] + (T + "tie_avenger.dds",)
TECH["small_repeater2"] = ("Macrobinocular Visors I", "Helmet optics that let troopers see and shoot in the dark.", T + "REP_night_vision_medium.dds")
TECH["medium_repeater2"] = ("Macrobinocular Visors II", "Better helmet optics with range-finding and thermal modes.", T + "REP_night_vision2_medium.dds")
TECH["improved_special_training2"] = TECH["improved_special_training2"][:2] + (T + "REP_support_weapons3_medium.dds",)  # user: phase II helmet
NAME.update({"imperial_equipment": "Blaster Rifle", "heavy_troop_transport_equipment": "Heavy Troop Transport"})


def tech_blocks(text):
    """{tech: block text} for every depth-1 entry of a technologies = { } file (brace-depth, comment-safe)."""
    import re
    t = re.sub(r"#[^\n]*", "", text)
    out, d, start, name = {}, 0, None, None
    for m in re.finditer(r"([\w\-\.@]+)\s*=\s*\{|\{|\}", t):
        if m.group(0) == "}":
            d -= 1
            if d == 1 and start is not None:
                out[name] = t[start:m.end()]; start = None
            continue
        if d == 1 and m.group(1):
            name, start = m.group(1), m.start()
        d += 1
    return out


def enables(block):
    import re
    return sum((x.split() for x in re.findall(r"enable_equipments\s*=\s*\{([^}]*)\}", block)), [])

# 2026-11-07: icons rendered from our 3D models (plans & scripts/tech_icon_render.py, side view + drop shadow)
for _t, _f in (("imp_tech_cv_2", "venator"), ("imp_tech_dd_1", "foray"), ("imp_tech_cl_1", "hammerhead"),
           ("atot", "atot"), ("rtt", "atot"), ("itt", "itt"), ("itc", "itt"), ("juggernaut", "juggernaut")):
    TECH[_t] = TECH[_t][:2] + (f"gfx/interface/technologies/hod_render/{_f}_medium.dds",)
