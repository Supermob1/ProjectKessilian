"""Landmark lore: a state dynamic modifier for every unique building placed on the planets made since Felucia, with
its name, a description and its history up to the game's start (976.1.1, the Separatist Crisis: the Confederacy has
formed under Count Dooku, no shot has been fired yet; the Clone Wars are not mentioned as having happened).

    python "WIPGFX/plans & scripts/landmarks_lore.py"

Each landmark's state is found from where its meshes stand in map/ambient_object.txt (so the modifiers follow the
maps when a planet is redrawn); `state=` pins one that stands in no province (Bonadan's orbital shipyard). Writes
common/dynamic_modifiers/HOD_landmark_dynamic_modifiers.txt, common/on_actions/HOD_landmark_on_actions.txt (added on
startup) and localisation/english/HOD_landmarks_l_english.yml. The effects are small and thematic.
Lore sources: the planets' research dossiers (WIPGFX/research/<planet>/); where a history goes beyond them (dates
of a building, who runs it now) it is a design choice, noted in the comment on its entry.
"""
import csv, glob, os, re, sys
import numpy as np
from PIL import Image

MODS = "common/dynamic_modifiers/HOD_landmark_dynamic_modifiers.txt"
ONACT = "common/on_actions/HOD_landmark_on_actions.txt"
LOC = "localisation/english/HOD_landmarks_l_english.yml"
# (key, meshes (entity names without _entity), icon, {modifier: value}, name, description, pinned state or None)
LANDMARKS = [
    # --- Raxus (canon: Raxus, capital of the Confederacy, its Parliament in Raxulon; TCW "Heroes on Both Sides")
    ("raxulon_parliament", ["hod_raxus_senate"], "GFX_idea_generic_political_support",
     {"compliance_gain": 0.02, "resistance_target": -0.05}, "Parliament of Raxulon",
     "The domed parliament of Raxulon, raised in the days when Raxus was a quiet, wealthy world of gardens far from "
     "the Core. Its chamber has become the Separatist Senate: delegates of the systems that broke with the Republic "
     "under Count Dooku sit here, draft the laws of the Confederacy of Independent Systems and debate, still in "
     "earnest, whether their secession can be won with words alone.", None),
    ("great_alley", ["hod_rax_alley_62", "hod_rax_alley_63"], "GFX_idea_generic_pp_unity_bonus",
     {"resistance_target": -0.03}, "The Great Alley of Raxulon",
     "The tree-lined processional avenue that leads to the parliament, planted with Raxus' golden-crowned trees "
     "generations ago. Delegates arriving from across the Outer Rim walk it to their first session; Raxulon's people "
     "gather along it to cheer them, and to remind them who they speak for.", None),
    # --- Raxus Prime, the galaxy's junkyard (Legends); the refinery and droidworks histories are design choices
    ("rp_refinery", ["hod_bld_rp_factory"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "The Sienar Refinery",
     "A vast reclamation plant that once melted the junk of half the galaxy back into usable metal. Its owners "
     "left long ago; scavenger clans and Jawa crews have kept its furnaces lit ever since, selling ingots to anyone "
     "who lands with credits, and asking no questions about which side of the Senate's quarrel they serve.", None),
    ("rp_derriphan", ["hod_bld_rp_derriphan_bow", "hod_bld_rp_derriphan_stern"], "GFX_idea_generic_navy_cruiser_warfare",
     {"local_resources_factor": 0.05}, "Wreck of a Derriphan Battleship",
     "The broken halves of a Derriphan-class battleship, a capital ship from the wars of the Old Republic thousands "
     "of years ago. How it came to rest on Raxus Prime no record says; scavengers have been cutting plates from its "
     "hull for longer than anyone living remembers, and there is still more ship than scrap.", None),
    ("rp_hammerhead", ["hod_bld_rp_hammerhead_bow", "hod_bld_rp_hammerhead_stern"], "GFX_idea_generic_navy_bonus",
     {"local_resources_factor": 0.05}, "Wreck of a Hammerhead Cruiser",
     "A Hammerhead-class cruiser, the workhorse of the Republic Navy in the age of the Old Republic, broken in two "
     "and half buried in the junk. Its armoured prow still points at the sky. Salvagers say its reactor cores were "
     "never found.", None),
    ("rp_lethisk", ["hod_bld_rp_lethisk"], "GFX_idea_generic_convoys", {"local_resources_factor": 0.05},
     "Wreck of a Lethisk Freighter",
     "The rusting hulk of an old Lethisk-class armed freighter, the kind smugglers and privateers flew when the Old "
     "Republic was young. Every scavenger crew on Raxus Prime claims to have found its hidden cargo hold; none of "
     "them can say what was in it.", None),
    ("rp_droidworks", ["hod_bld_rp_droidworks"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.1}, "The Droidworks",
     "An automated droid foundry buried in the scrap, still assembling droids from salvage for masters who stopped "
     "giving it orders long ago. Lately, quiet buyers from the Techno Union have been seen studying its lines.", None),
    # --- Korriban (Legends; KOTOR: the academy and the tombs of the Valley of the Dark Lords)
    ("sith_academy", ["hod_kor_academy_r2"], "GFX_idea_generic_secret_police", {"resistance_target": 0.05},
     "The Sith Academy",
     "Carved into the rock above Dreshdae, the academy trained the Sith of age after age: the followers of Exar Kun, "
     "Darth Revan's legions, the acolytes of every Sith empire that rose and fell. Since the Sith Order destroyed "
     "itself at Ruusan a thousand years ago its halls stand empty, stripped by tomb robbers. The Republic forbids "
     "landings, and Dreshdae's few settlers will not go near it after dark.", None),
    ("valley_dark_lords", ["hod_kor_obelisks", "hod_kor_twins_r1"], "GFX_idea_generic_oppression",
     {"resistance_target": 0.03}, "The Valley of the Dark Lords",
     "A canyon of tombs where the ancient Sith buried their kings and Dark Lords, its way lined with obelisks and "
     "colossal statues of the dead. The dark side clings to the stone; travellers report voices, cold winds out of "
     "nowhere and lost hours. Archaeologists of the Republic have mapped it twice. Neither expedition came back whole.", None),
    ("tomb_ragnos", ["hod_kor_ragnos_r0"], "GFX_idea_generic_oppression", {"resistance_target": 0.03},
     "Tomb of Marka Ragnos",
     "The tomb of Marka Ragnos, Dark Lord of the Sith some five thousand years ago, whose death set Naga Sadow and "
     "Ludo Kressh at each other's throats and opened the way to the Great Hyperspace War. Legend holds that his "
     "spirit has spoken from it to more than one would-be Sith Lord.", None),
    ("tomb_sadow", ["hod_kor_tomb_d_r1"], "GFX_idea_generic_oppression", {"resistance_target": 0.03},
     "Tomb of Naga Sadow",
     "The tomb raised for Naga Sadow, the Dark Lord who led the old Sith Empire into the Great Hyperspace War against "
     "the Republic and lost it. His followers sealed it with traps no robber has fully mapped.", None),
    ("tomb_pall", ["hod_kor_tomb_a_r7"], "GFX_idea_generic_oppression", {"resistance_target": 0.03},
     "Tomb of Ajunta Pall",
     "The tomb of Ajunta Pall, one of the exiled Dark Jedi who came to Korriban nearly seven thousand years ago and "
     "made himself the first Dark Lord of the Sith. His sword is said to lie with him still.", None),
    ("tomb_hord", ["hod_kor_tomb_a_r5"], "GFX_idea_generic_oppression", {"resistance_target": 0.03},
     "Tomb of Tulak Hord",
     "The tomb of Tulak Hord, the Dark Lord remembered as the greatest warrior of the ancient Sith, who never lost a "
     "battle he chose to fight. His masks and the secrets of his techniques were buried with him.", None),
    ("tomb_kressh", ["hod_kor_tomb_b_r4"], "GFX_idea_generic_oppression", {"resistance_target": 0.03},
     "Tomb of Ludo Kressh",
     "The tomb of Ludo Kressh, Naga Sadow's rival for the throne of the Sith, who fought him for the Empire and died "
     "in the attempt. Its plainer stones tell the story: the victors built it.", None),
    # --- Kadavo (canon: the Zygerrian slave processing facility, TCW "Escape from Kadavo"; the Jedi broke the
    # Zygerrian slave empire long before the war; that the facility kept working quietly is a design choice)
    ("kadavo_facility", ["hod_kad_facility"], "GFX_idea_generic_prisoner",
     {"recruitable_population_factor": -0.2, "compliance_gain": -0.02}, "Kadavo Processing Facility",
     "The tower-fortress where the Zygerrian Slave Empire once processed captives by the thousand before they were "
     "sold. The Jedi broke that empire long ago and the facility fell silent - officially. In Kadavo's smog its "
     "holding pens still fill and empty, discreetly, while Zygerrian nobles speak again of the glory of the old trade.", None),
    ("kadavo_landing", ["hod_kad_dock"], "GFX_idea_generic_convoys", {"local_supplies": 0.1},
     "Slaver Landing Field",
     "The landing field where the slavers' ships set down their cargo. Its beacons are kept dark; ships come and go "
     "without flight plans, and no Republic patrol has ever asked why.", None),
    ("kadavo_pits", ["hod_kad_mine"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Kadavo Ore Pits",
     "Open pits in the ash where captives too weak to sell are put to work digging ore. Their output pays for the "
     "facility's upkeep; their dead are buried in the ash.", None),
    ("kadavo_camps", ["hod_kad_camp"], "GFX_idea_generic_prisoner", {"recruitable_population_factor": -0.1},
     "Slave Camp",
     "A fenced camp of prefab huts out on the ash, where captives wait to be processed under the watch of Zygerrian "
     "overseers and their droids.", None),
    # --- Florrum (canon: Hondo Ohnaka's Weequay pirates, TCW); refinery, outposts, vault and junk market are design
    ("hondo_complex", ["hod_flo_complex"], "GFX_idea_generic_guerilla_warfare",
     {"resistance_target": 0.1, "local_supplies": 0.1}, "Hondo's Complex",
     "The fortified lair of Hondo Ohnaka's Weequay pirate gang, a sprawl of hangars, cantinas and treasure rooms "
     "on Florrum's sulfur plains. Hondo deals with whoever pays - smugglers, the Hutts, Republic and Separatist alike - "
     "and is in no hurry to choose a side in the Senate's quarrel while both still have credits.", None),
    ("florrum_refinery", ["hod_flo_refinery"], "GFX_idea_generic_fuel_reserves", {"local_resources_factor": 0.1},
     "Sulfur Refinery",
     "A sulfur refinery abandoned by a mining concern that left Florrum in a hurry; the pirates moved in and kept it "
     "running. Its fumes can be smelled three canyons away.", None),
    ("florrum_outposts", ["hod_flo_outpost_a", "hod_flo_outpost_b"], "GFX_idea_generic_fortify_the_borders",
     {"local_supplies": 0.05}, "Weequay Outpost",
     "A lookout post of the Ohnaka gang: a few prefab domes, a sensor mast and a landing pad, manned by Weequay who "
     "watch the sky for rivals, bounty hunters and anyone worth robbing.", None),
    ("hondo_vault", ["hod_flo_vault_r5"], "GFX_idea_generic_economic_increase", {"local_supplies": 0.1},
     "Hondo's Vault",
     "A vault cut deep into the Eastern Shelf where Hondo Ohnaka keeps the spoils he does not trust even his own crew "
     "with. Every pirate on Florrum knows it exists; none admit to knowing the way in.", None),
    ("florrum_junk", ["hod_bld_rp_hammerhead_bow", "hod_bld_rp_lethisk"], "GFX_idea_generic_foreign_capital",
     {"local_resources_factor": 0.05}, "Hulks of the Junk Market",
     "The stripped hulks of an old cruiser and an armed freighter, dragged to Florrum as prizes and now the heart of "
     "the Weequay junk market, where anything with a price changes hands.", None),
    # --- Dromund Kaas (Legends: the Sith Empire's capital Kaas City, the Emperor's Citadel, the Dark Temple)
    ("kaas_citadel", ["hod_dk_citadel"], "GFX_idea_generic_secret_police", {"resistance_target": 0.05},
     "Ruins of the Imperial Citadel",
     "The black citadel from which the Sith Emperor ruled the reborn Sith Empire for more than a thousand years. The "
     "Empire is long dead and Kaas City lies in ruins, swallowed by the storm jungle, but the Citadel's tower still "
     "stands above the trees, and lightning strikes it more often than anything else on the planet.", None),
    ("dark_temple", ["hod_dk_dark_temple"], "GFX_idea_generic_oppression", {"resistance_target": 0.05},
     "The Dark Temple",
     "An ancient Sith temple older than Kaas City itself, where the Emperor is said to have performed his darkest "
     "rites. The dark side pools here so thickly that the planet's endless storms seem to circle it.", None),
    # --- Zygerria (canon: the Zygerrian royal palace and slave arena, TCW; Queen Miraj Scintel); fortresses and the
    # landing are design choices
    ("zyg_palace", ["hod_zyg_palace"], "GFX_idea_generic_political_support", {"compliance_gain": 0.02},
     "Royal Palace of Zygerria",
     "The palace of the Zygerrian kings and queens, raised on its mesa when Zygerria ruled a slave empire. Queen "
     "Miraj Scintel holds court here, among nobles who have never forgiven the Jedi for ending the old trade and who "
     "watch the Republic's troubles with growing interest.", None),
    ("zyg_arena", ["hod_zyg_arena"], "GFX_idea_generic_morale_bonus", {"recruitable_population_factor": 0.05},
     "Royal Arena",
     "The great arena beside the palace, where slaves were once auctioned before the assembled nobility. Today it "
     "hosts games and beast fights; the auction block has never been taken down.", None),
    ("zyg_fortress", ["hod_zyg_fortress"], "GFX_idea_generic_mountain_warfare", {"resistance_damage_to_garrison": -0.1},
     "Mesa Fortress",
     "An old stronghold of the Zygerrian nobility on a mesa top, reached by a single ramp. Built to hold down the "
     "provinces in the days of the empire, it is kept garrisoned out of habit - and out of hope.", None),
    ("zyg_landing", ["hod_zyg_landing"], "GFX_idea_generic_convoys", {"local_supplies": 0.1},
     "Slavers' Landing",
     "The landing platforms from which the slave ships of the Zygerrian Empire once departed. Merchant ships use them "
     "now, but the cargo cranes still bear the royal slave-mark.", None),
    # --- Cantonica (canon: Canto Bight, the Westhill cliffs; Canto Bight standing before the war is the user's choice)
    ("westhill_palace", ["hod_cant_westhill"], "GFX_idea_generic_foreign_capital", {"compliance_gain": 0.01},
     "Westhill Palace",
     "A palatial mansion on the Westhill cliffs above Canto Bight, home to the richest of the families who built the "
     "casino city on Cantonica's artificial sea. Arms dealers from both sides of the Separatist crisis are welcome at "
     "its tables, as long as they lose gracefully.", None),
    # --- Bonadan (Legends: Spaceport Southeast II, the Bonadan shipyards, the weather-control station)
    ("bonadan_spaceport", ["hod_bon_spaceport"], "GFX_idea_generic_logistics", {"local_supplies": 0.15},
     "Spaceport Southeast II",
     "The largest of Bonadan's ten spaceports, a ring of landing pads, hangars and cargo halls through which the ore "
     "and machinery of the Corporate Sector's foremost industrial world pour out to the galaxy.", None),
    ("bonadan_shipyards", ["hod_bon_shipyard"], "GFX_idea_generic_navy_bonus",
     {"state_production_speed_dockyard_factor": 0.15}, "Bonadan Shipyards",
     "Orbital yards ringing Bonadan's eastern sky, rated Class IB and able to build ships up to cruisers. Their slips "
     "turn out hulls for the Corporate Sector Authority and for any buyer with credits - and since the Separatist "
     "crisis began, the order books have never been fuller.", 754),
    ("bonadan_weather", ["hod_bon_weather"], "GFX_idea_generic_radar", {"recruitable_population_factor": 0.05},
     "Weather Control Station",
     "A massive weather-control station in the mountains north of the main cities. Its emitter masts raise the "
     "sweeper storms that scour Bonadan's polluted air; without them the factory cities would choke within a season.", None),
    # --- Etti IV (Legends: Mondder, its spaceport, the Dream Emporium, the Free-Flight Dance Dome; canon: Cybot
    # Galactica's Arcoplex)
    ("arcoplex", ["hod_etti_arcoplex"], "GFX_idea_generic_improved_industries",
     {"state_production_speed_buildings_factor": 0.1}, "The Arcoplex",
     "The city-headquarters of Cybot Galactica, the galaxy's foremost maker of droids, rising in stepped arcs around "
     "its corporate spire. The company has begun clearing the forests around it by fire to make room for new "
     "assembly halls, and the smoke of its expansion drifts over the plains.", None),
    ("mondder_spaceport", ["hod_etti_spaceport"], "GFX_idea_generic_logistics", {"local_supplies": 0.15},
     "Mondder Spaceport",
     "The primary spaceport of Mondder, capital of the Corporate Sector: holding bays numbered in the dozens - Docking "
     "Bays 41 and 45 among them - landing pads on pylons, and the Dream Emporium, where the Authority's wealthy and "
     "the Etti themselves come to be entertained.", None),
    ("dance_dome", ["hod_etti_dancedome"], "GFX_idea_generic_conference", {"compliance_gain": 0.02},
     "The Free-Flight Dance Dome",
     "An elegant bistro high above Mondder, its dancers floating free under a glass dome. The executives of the "
     "Corporate Sector Authority seal their deals at its tables; more than one meeting there has ended in blaster fire.", None),
    # --- Ruuria (canon + Legends: the University of Ruuria; Legends: the Ruurians' 143 colonies; the First Colony and
    # the university's age are design choices)
    ("ruuria_university", ["hod_ruu_university"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "University of Ruuria",
     "The oldest seat of learning in the Xappyh sector, its stone halls and library spire grown over the centuries "
     "with the segmented halls of the Ruurians who teach there. Historians from across the Outer Rim come to study "
     "its archives; its students argue the Separatist question late into every night.", None),
    ("great_hive", ["hod_ruu_great_hive"], "GFX_idea_generic_manpower_bonus", {"recruitable_population_factor": 0.1},
     "Great Hive of the First Colony",
     "The great hive of the First Colony, eldest of the 143 colonies into which every Ruurian is born and to which "
     "each belongs for life: a mound of fused silk cocoons, tunnels and stalked pods, lit from within by resin lamps.", None),
    # --- Ossus (canon + Legends: the Great Jedi Library designed by Odan-Urr, Knossa of stone and bronzium, its
    # spaceport round Agorn Mountain, the First Temple / Jedi Praxeum, the Cron Supernova, the Ysanna, the Jedi
    # archaeologists; the Separatists' presence at the start follows the mod's owner, CIS)
    ("great_library", ["hod_oss_library"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "Ruins of the Great Jedi Library",
     "On a hill in the Ooroo Canyon stand the ruins of the Great Jedi Library, which Odan-Urr designed and raised to "
     "honour a promise to his Master Ooroo: once the greatest store of knowledge in the galaxy, a vast unadorned stone "
     "hall with most of its rooms below ground. The Cron Supernova burned it four thousand years ago, and the Jedi "
     "saved only a fraction of its holocrons. Archaeologists of the Order still dig in its lower chambers - now under "
     "the eyes of the Confederacy, whose claim over the system makes the Jedi uneasy.", None),
    ("knossa", ["hod_oss_knossa"], "GFX_idea_generic_political_support", {"resistance_target": -0.03},
     "Ruins of Knossa",
     "Once the greatest city of Ossus, Knossa was built of stone and bronzium, its squat domes climbing the western "
     "Eocho Mountains around the Branch Library that Odan-Urr commissioned for scholars in a hurry. The supernova "
     "emptied it; its domes stand cracked and green with age, and the Ysanna who camp in its streets keep its "
     "shrines without remembering whom they honour.", None),
    ("agorn_spaceport", ["hod_oss_agorn"], "GFX_idea_generic_logistics", {"local_supplies": 0.1},
     "Knossa Spaceport",
     "The Jedi built this spaceport for the pilgrims who came to Ossus by the thousand: a promenade winding round "
     "Agorn Mountain, its landing terraces jutting from every turn. Few ships land there now. Above it, on a nearby "
     "peak, the Force vergence called the Eye of Ashlanae still glows faintly at night.", None),
    ("first_temple", ["hod_oss_temple"], "GFX_idea_generic_morale_bonus", {"compliance_gain": 0.02},
     "Ruins of the First Temple",
     "The First Temple, the Jedi Praxeum where Odan-Urr trained under Master Ooroo, one of the oldest seats of the "
     "Order: a stepped platform, a ring of great columns round a cracked meditation dome, all of it overgrown with "
     "bamboo. The Ysanna call it sacred ground; even the Separatist surveyors who have come to Ossus leave it alone.", None),
    # --- Lola Sayu (canon: the Citadel, built 522 BBY by the Republic and the Jedi for rogue and fallen Jedi, on a
    # bridge between two lakes of yellow lava, geothermal power; its passages recorded in the Jedi Archives; the lost
    # southern hemisphere as an orbital debris belt). The Separatist capture comes only in the war: not mentioned
    ("citadel", ["hod_lola_citadel"], "GFX_idea_generic_prisoner", {"resistance_target": -0.1, "compliance_gain": 0.03},
     "The Citadel",
     "A maximum-security prison raised in 522 BBY by the Republic and the Jedi Order to hold Jedi who had gone rogue or "
     "fallen to the dark side: a dark tower on a pinnacle of basalt, reached only by a causeway between two lakes of "
     "yellow lava whose heat powers it. Its cells have held some of the most dangerous Force-users the Order ever "
     "failed. The plans of its tunnels and caves are kept in the Jedi Archives on Coruscant, and the Order hopes "
     "they will never be needed.", None),
    ("shattered_hemisphere", ["hod_lola_chunk_a0"], "GFX_idea_generic_navy_submarines", {"local_supplies": -0.1},
     "The Shattered Hemisphere",
     "Long before the Republic found it, a cataclysm no record explains tore away nearly the whole southern hemisphere "
     "of Lola Sayu. Its crust still drifts in orbit as a belt of glowing fragments that makes every approach "
     "dangerous, and the surviving half slowly crumbles into the Sulfur Sea, the lava ocean that fills the broken "
     "edge.", 1180),
    # --- Ringo Vinda (canon + Legends: the space station, "a ring-shaped civilian graving dock that encircled the
    # planet", on the Perlemian Trade Route; the surface after the Cato Neimoidia concept art; Vindaport and the
    # Station Lift are invented). The Separatist capture and the battle come only in the war: not mentioned
    ("ringo_ring", ["hod_rv_ring"], "GFX_idea_generic_navy_bonus", {"state_production_speed_dockyard_factor": 0.15},
     "Ringo Vinda Station",
     "A ring of hull plating so vast it encircles the whole planet: the Ringo Vinda space station, a civilian graving "
     "dock on the Perlemian Trade Route where freighters and liners from half the Mid Rim come to be repaired, refitted "
     "and rebuilt. Its decks hold a city's worth of dockworkers, and its slips are never empty. With the Separatist "
     "crisis deepening, Republic officers have begun to look at it with a shipwright's eye.", 81),
    ("vindaport", ["hod_rv_archcity"], "GFX_idea_generic_political_support", {"compliance_gain": 0.02},
     "Vindaport",
     "The capital of Ringo Vinda, hung in tiers of domed houses from a great stone arch between two colossal pillars, "
     "above the head of the Great Mist Chasm. Its people are as proud of their arches as of their accent, which a "
     "Ringo Vindan keeps for life, wherever in the galaxy they end up.", None),
    ("station_lift", ["hod_rv_lift"], "GFX_idea_generic_logistics", {"local_supplies": 0.1},
     "Station Lift",
     "The shuttle port between Vindaport and the ring above: a slender spire of stone and glass with three landing "
     "rings, where the dock crews and their cargo shuttle up to the station and down again at every shift.", None),
    # --- Rhen Var (Legends: the lost civilization's castles, fortresses and temples under the ice; Rhen Var Harbor and
    # the Citadel (Battlefront); the Jedi monument, Ulic Qel-Droma's grave; Darth Mekhis' fortress (Great Galactic
    # War); the Forgotten Rakatan Temple (Levat); Bravo Base). Its fall in the war's first month: not mentioned
    ("bravo_base", ["hod_rh_bravo"], "GFX_idea_generic_fortify_the_borders", {"resistance_target": -0.05, "local_supplies": 0.1},
     "Bravo Base",
     "A Republic military facility on the arctic world of Rhen Var: prefab barracks, a hangar, landing pads and a "
     "sensor mast inside a perimeter of turrets. Its small garrison watches the Slice and the ruins, and with the "
     "Separatist systems drawing their lines ever closer, its commanders have begun asking Coruscant for more men.", None),
    ("rhen_harbor", ["hod_rh_harbor"], "GFX_idea_generic_coastal_navy", {"local_supplies": 0.05},
     "Rhen Var Harbor",
     "The ruins of a harbor town from the age before the ice: stone quays along a bay frozen solid, towers with empty "
     "arched windows, an arched bridge over the inlet and an old ship locked in the ice where its crew left it, "
     "thousands of years ago, when the cold came and never went away.", None),
    ("rhen_citadel", ["hod_rh_citadel"], "GFX_idea_generic_mountain_warfare", {"resistance_damage_to_garrison": -0.1},
     "Rhen Var Citadel",
     "A castle of the lost civilization on a snowy crag: curtain walls, round towers and a spired keep, reached over "
     "an arched bridge. Whoever built it vanished under the ice age, but its walls still stand, and every army that "
     "has come to Rhen Var has wanted to hold them.", None),
    ("jedi_monument", ["hod_rh_monument"], "GFX_idea_generic_morale_bonus", {"compliance_gain": 0.02},
     "Jedi Monument",
     "An old Jedi temple, stepped and plain, with an obelisk over the grave of Ulic Qel-Droma: the Jedi who fell to the "
     "dark side in the Great Sith War, lost his bond to the Force, and came here to die in exile nearly four thousand "
     "years ago. The Order keeps the site quietly; pilgrims say the cold is gentler near the stone.", None),
    ("mekhis_fortress", ["hod_rh_mekhis"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Ruins of Mekhis' Fortress",
     "The broken black walls of the fortress the Sith Lord Darth Mekhis raised in Rhen Var's mountains during the "
     "Great Galactic War, until the Jedi Knight Satele Shan stormed it. Snow fills its courts; its tower still stands.", None),
    ("rakatan_temple", ["hod_rh_rakata"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "Forgotten Rakatan Temple",
     "A dark stepped temple carved with Rakatan script, half sunk in the snow. The Duros archaeologist Levat argued it "
     "was built after the fall of the Infinite Empire, whatever its script says; scholars still argue, and the panels "
     "of script still glow faintly in the polar night.", None),
]

# the planet each landmark is on (meshes are reused between planets: the wrecks stand on Raxus Prime and Florrum)
PLANET_OF = {"raxulon_parliament": "Raxus", "great_alley": "Raxus", "kaas_citadel": "Dromund Kaas",
             "dark_temple": "Dromund Kaas", "westhill_palace": "Cantonica", "arcoplex": "Etti IV",
             "mondder_spaceport": "Etti IV", "dance_dome": "Etti IV", "ruuria_university": "Ruuria", "great_hive": "Ruuria",
             "great_library": "Ossus", "knossa": "Ossus", "agorn_spaceport": "Ossus", "first_temple": "Ossus",
             "citadel": "Lola Sayu", "shattered_hemisphere": "Lola Sayu",
             "ringo_ring": "Ringo Vinda", "vindaport": "Ringo Vinda", "station_lift": "Ringo Vinda",
             **{k: "Rhen Var" for k in ("bravo_base", "rhen_harbor", "rhen_citadel", "jedi_monument", "mekhis_fortress",
                                        "rakatan_temple")},
             **{k: "Korriban" for k in ("sith_academy", "valley_dark_lords", "tomb_ragnos", "tomb_sadow", "tomb_pall",
                                        "tomb_hord", "tomb_kressh")},
             **{k: pl for pre, pl in (("rp_", "Raxus Prime"), ("kadavo_", "Kadavo"), ("hondo_", "Florrum"),
                                      ("florrum_", "Florrum"), ("zyg_", "Zygerria"), ("bonadan_", "Bonadan"))
                for k, *_ in LANDMARKS if k.startswith(pre)}}
assert {k for k, *_ in LANDMARKS} == set(PLANET_OF), "every landmark needs its planet"


def states_of():
    """mesh name -> set of (state id, planet) its placed copies stand in (map/ambient_object.txt)"""
    s = open("map/ambient_object.txt", encoding="utf-8-sig").read()
    img = np.array(Image.open("map/provinces.bmp").convert("RGB"))
    H = img.shape[0]
    col2p = {(int(r[1]), int(r[2]), int(r[3])): int(r[0]) for r in csv.reader(open("map/definition.csv", encoding="utf-8-sig"),
                                                                            delimiter=";") if r and r[0].isdigit()}
    p2s = {}
    for f in glob.glob("history/states/*.txt"):
        t = open(f, encoding="utf-8-sig").read()
        sid = int(re.search(r"\bid\s*=\s*(\d+)", t).group(1))
        planet = re.sub(r"\.txt$", "", os.path.basename(f).split("-", 1)[1]).split(" - ")[0]   # "<id>-<Planet>[ - name]"
        p2s.update({int(p): (sid, planet) for p in re.search(r"provinces\s*=\s*\{([^}]*)\}", t).group(1).split()})
    out = {}
    for m in re.finditer(r'type="(hod_[a-z0-9_]+)_entity"(.*?)\n\}', s, re.S):
        for x, z in re.findall(r"position=\{\s*([\d.]+) [\d.-]+ ([\d.]+)", m.group(2)):
            p = col2p.get(tuple(img[H - 1 - int(round(float(z))), int(round(float(x)))]))
            out.setdefault(m.group(1), set()).add(p2s.get(p, (None, None)))
    return out


def main():
    where = states_of()
    mods, apply_, loc = ["# HOD: landmark lore (landmarks_lore.py)\n"], {}, ["﻿l_english:\n"]
    for key, meshes, icon, effects, name, desc, pin in LANDMARKS:
        found = {sid for sid, pl in set().union(*(where.get(m, set()) for m in meshes)) if pl == PLANET_OF[key]}
        assert pin or found, f"{key}: none of {meshes} is placed on {PLANET_OF[key]}"
        sts = {pin} if pin else found
        assert sts, f"{key}: {meshes} stand in no province; pin a state"
        mid = f"HOD_landmark_{key}"
        mods.append(f"{mid} = {{\n\ticon = {icon}\n\tenable = {{ always = yes }}\n"
                    + "".join(f"\t{k} = {v}\n" for k, v in effects.items()) + "}\n")
        apply_[mid] = sorted(sts)
        q = lambda t: t.replace('"', '\\"')
        loc += [f' {mid}:0 "{q(name)}"\n', f' {mid}_desc:0 "{q(desc)}"\n']
    on = ["# HOD: landmark lore (landmarks_lore.py): each landmark's state gets its dynamic modifier at the start\n",
          "on_actions = {\n\ton_startup = {\n\t\teffect = {\n"]
    for mid, sts in apply_.items():
        lim = " ".join(f"state = {s}" for s in sts)
        on.append(f"\t\t\tevery_state = {{\n\t\t\t\tlimit = {{ OR = {{ {lim} }} }}\n"
                  f"\t\t\t\tadd_dynamic_modifier = {{ modifier = {mid} }}\n\t\t\t}}\n")
    on.append("\t\t}\n\t}\n}\n")
    w = lambda path, lines, enc="utf-8": open(path, "w", encoding=enc, newline="\n").write("".join(lines))
    w(MODS, mods)
    w(ONACT, on)
    w(LOC, loc)
    for mid, sts in apply_.items():
        print(f"{mid:40} states {sts}")


if __name__ == "__main__":
    main()
