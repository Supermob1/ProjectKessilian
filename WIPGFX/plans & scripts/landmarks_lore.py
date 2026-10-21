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
    # --- Pammant (canon: Quarren engineers, the Providence-class and Subjugator-class built here, the Malevolence in
    # secret; Legends: the ring-shaped Pammant Docks, Free Dac Volunteers Engineering Corps, "tunneled").
    # Tessar Deep and the dates are design choices
    ("pammant_docks", ["hod_pam_docks"], "GFX_idea_generic_navy_bonus",
     {"state_production_speed_dockyard_factor": 0.2}, "Pammant Docks",
     "A ring-shaped shipyard in orbit over Pammant, run by the Quarren of the Free Dac Volunteers Engineering Corps. "
     "Since the Quarren sided with Count Dooku its berths hold Providence-class carriers built for the Trade "
     "Federation - and, clamped in the great cradle across the ring, a hull far larger than any of them, whose "
     "purpose the Quarren will not discuss.", 700),
    ("pammant_liftport", ["hod_pam_liftport"], "GFX_idea_generic_logistics",
     {"state_production_speed_buildings_factor": 0.1, "local_supplies": 0.1}, "QFD Lift Port",
     "The heavy-lift spaceport of the Free Dac Volunteers Engineering Corps. Hull sections forged in the Quarren "
     "foundries below arrive by rail, wait on its great hexagonal pads and are hauled up by lifter tugs to the docks "
     "in orbit. Republic agents counting the sections lifted have reported more steel than any known warship needs; "
     "none of those reports has yet reached Coruscant.", None),
    ("pammant_tessar", ["hod_pam_colony"], "GFX_idea_generic_political_support",
     {"stability_factor": 0.02, "local_manpower": 0.05}, "Tessar Deep",
     "The capital of Pammant's Quarren colony: rounded towers rising from the mouth of the colony's main shaft, the "
     "city's real bulk lying in the warrens below. Its engineers have built starships for generations; now their "
     "Isolation League speaks for the Confederacy.", None),
    # --- Mon Cala (canon: Coral City, the capital; the Moncaladrome opera house; the Quarren headquarters in Quarren
    # Town, from which Riff Tamson staged the Clone Wars attack). The 976 histories are design choices
    ("mcl_coral_city", ["hod_mcl_coral_city"], "GFX_idea_generic_political_support",
     {"stability_factor": 0.03, "local_manpower": 0.05}, "Coral City",
     "The capital of Mon Cala, its shell domes and spires grown over a living reef and lit gold through the water. "
     "From the royal palace at its heart King Yos Kolina rules both peoples of the ocean world, a union the Mon "
     "Calamari hold sacred and the Quarren increasingly call a cage.", None),
    ("mcl_drome", ["hod_mcl_drome"], "GFX_idea_generic_pp_unity_bonus", {"stability_factor": 0.02}, "Moncaladrome",
     "The great opera house of Mon Cala, three shell vaults whose ribbed halls carry song through the water as well as "
     "the air. Its seasons are the pride of Coral City's society; Quarren rarely attend.", None),
    ("mcl_quarren_hq", ["hod_mcl_quarren_hq"], "GFX_idea_generic_army_support",
     {"local_manpower": 0.08, "resistance_target": 0.05}, "Quarren Headquarters",
     "The seat of the Quarren in the depths of Quarren Town: dark towers on a rock mound, their war room sealed to "
     "Mon Calamari envoys. Separatist agents have been seen coming and going, and the Isolation League now meets "
     "here in the open.", None),
    # --- Iego (canon: Cliffhold, the LaserWeb Defense Station; Legends: the Choir Alignment, the Boneyard). The 976
    # histories (the station already standing, the spice trade's decline) are design choices
    ("ieg_cliffhold", ["hod_ieg_cliffhold"], "GFX_idea_generic_logistics", {"local_supplies": 0.1, "stability_factor": 0.02},
     "Cliffhold", "A spaceport city cut straight into the face of a basalt cliff, its landing pads jutting from the rock "
     "over the desert. Once loud with spice convoys, it has grown quiet since the convoys stopped coming; the Iegoans "
     "who remain say the world of a thousand moons does not let its people leave.", None),
    ("ieg_laserweb", ["hod_ieg_laserweb"], "GFX_idea_generic_radar", {"resistance_target": 0.05},
     "LaserWeb Defense Station", "A Separatist station hung in orbit over Iego by engineers who came as advisers. Its "
     "six emitter pods can wrap the sky in a web of laser fire that no ship escapes; for now it only watches, and the "
     "Iegoans have begun to wonder who it is meant to keep in.", 76),
    ("ieg_choir", ["hod_ieg_choir"], "GFX_idea_generic_pp_unity_bonus", {"stability_factor": 0.02}, "Choir Alignment",
     "A sunken valley a hundred metres across, shaped like a nine-pointed star and plainly not made by nature. Those "
     "who stand at its centre say they hear a choir singing; no one knows who carved it, or when.", None),
    ("ieg_boneyard", ["hod_ieg_boneyard"], "GFX_idea_generic_research_bonus", {"local_supplies": 0.05},
     "The Boneyard", "The largest of Iego's bone piles, north of the Scatter: the skeletons of creatures far larger "
     "than any that live on the planet now, ribs arching over the sand like the frames of buildings.", None),
    # --- Lianna (Legends: the Santhe/Sienar headquarters in Lianna City, the Melford Star Academy, Sky City, the
    # Class IB Lianna shipyards; the Santhe family's rule). The 976 histories are design choices
    ("lia_hq", ["hod_lia_hq"], "GFX_idea_generic_improved_industries",
     {"state_production_speed_buildings_factor": 0.1, "stability_factor": 0.02}, "Santhe/Sienar Headquarters",
     "The towers of Santhe/Sienar Technologies over Lianna City, seat of Sienar, Curich Engineering and Santhe "
     "Passenger and Freight. Valles Santhe runs the planet from its crown as much as any government does; the Republic "
     "buys Sienar's ships, and Lianna intends to stay rich and independent whatever the coming war brings.", None),
    ("lia_academy", ["hod_lia_academy"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Melford Star Academy", "The First Star Academy on Anai's northern coast, where the Tion Cluster's pilots and "
     "officers have trained for generations under its great ribbed dome.", None),
    ("lia_skycity", ["hod_lia_skycity"], "GFX_idea_generic_logistics", {"local_supplies": 0.1}, "Sky City",
     "A city of decks on a single tapering stalk, raised over the Shaltin Strait so the sea lanes run beneath it.", None),
    ("lia_shipyard", ["hod_lia_shipyard"], "GFX_idea_generic_navy_bonus",
     {"state_production_speed_dockyard_factor": 0.15}, "Lianna Shipyards",
     "Sienar's orbital yards over Lianna, rated Class IB and able to build cruisers. Couriers, patrol cruisers and "
     "freighters leave their slips for buyers across the Republic and beyond.", 195),
    # --- Jabiim (Legends: Choal, the mining machines, Shelter Base, Cobalt Station, Camp Aurek, Outpost Shear; the
    # user, 2026-10-16: the bases already stand at the start). The 976 histories are design choices
    ("jab_choal", ["hod_jab_choal"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "local_manpower": 0.05},
     "Choal", "Jabiim's capital, raised on its great drum platform above the floods, its rain houses on stilts and "
     "its council hall loud with argument: the Nationalists want out of the Republic, the loyalists want its help, "
     "and the rain never stops for either.", None),
    ("jab_bore", ["hod_jab_bore"], "GFX_idea_generic_improved_industries", {"state_production_speed_buildings_factor": 0.1},
     "Jobreth Bore", "One of the huge boring machines cutting ever deeper into the dying planet, its drill grinding down "
     "into a stepped pit on the Jobreth Plains while its conveyor builds a hill of spoil.", None),
    ("jab_shelter", ["hod_jab_shelter"], "GFX_idea_generic_army_support", {"local_supplies": 0.1},
     "Shelter Base", "A Republic command post of prefab domes on the northern fens, put up as Jabiim slid towards "
     "secession; its gunships wait on their pads for weather that rarely lets them fly.", None),
    ("jab_cobalt", ["hod_jab_cobalt"], "GFX_idea_generic_army_support", {"local_supplies": 0.05, "resistance_target": -0.05},
     "Cobalt Station", "A Republic fortification just north of Monsoon Mesa: a curved rampart, four heavy turrets and a "
     "shield generator, built to hold the high ground if the planet goes over to the Separatists.", None),
    ("jab_aurek", ["hod_jab_aurek"], "GFX_idea_generic_radar", {"resistance_target": 0.05},
     "Camp Aurek", "A Separatist camp in the south-eastern badlands, raised quietly by Confederate 'advisers' to the "
     "Nationalists: a droid-control spire, racks of folded battle droids and a transport ready to unload more.", None),
    ("jab_shear", ["hod_jab_shear"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Outpost Shear", "Stone bunkers and trenches on the north-eastern ridges, held by the Nationalists' militia. Its guns "
     "point at the Republic's mesa.", None),
    # --- Saleucami (Legends: Taleucema, the Saleucami Cloning Complex in the Magma Caverns; canon: Saleucami town, the
    # Lawquane farmstead). The 976 histories are design choices
    ("sal_taleucema", ["hod_sal_taleucema"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "local_supplies": 0.05},
     "Taleucema", "The capital of Saleucami, its towers joined by tall arcing bridges over the domed assembly hall. "
     "The Techno Union's money built the bridges; the Union's agents now sit in the hall.", None),
    ("sal_spaceport", ["hod_sal_spaceport"], "GFX_idea_generic_logistics", {"local_supplies": 0.1}, "Saleucami Town",
     "A dusty spaceport town of landing bowls and billboards on the eastern plains, where the freighters of the "
     "Outer Rim put in for water and parts.", None),
    ("sal_lawquane", ["hod_sal_lawquane"], "GFX_idea_generic_pp_unity_bonus", {"stability_factor": 0.01}, "Lawquane Farmstead",
     "A domed adobe farm in the wetlands, its crop rows ringed by a fence. Its family keeps to itself, as the wetland "
     "farmers always have.", None),
    ("sal_cloning", ["hod_sal_cloning"], "GFX_idea_generic_research_bonus", {"local_manpower": 0.05, "resistance_target": 0.05},
     "Saleucami Cloning Complex", "A secret installation in the Magma Caverns, its glass tanks lit by the lava below. "
     "The Separatists who built it say nothing of what grows in them.", None),
    # --- Telos (canon: Thani the capital, seat of the Telosian Council; RZ-0031, the Restoration Project and its
    # Ithorians; the Mirror Caverns lined with malab; Legends: the Thani Terminal, Atris's Polar Academy). The user's
    # city-world and the 976 histories (the Council's vote for the Confederacy, the malab quarries) are design choices
    ("tel_thani", ["hod_tel_thani"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Thani", "The capital of Telos, rebuilt tower by tower after Malak's bombardment some four thousand years ago "
     "until the city covered the world. The Telosian Council and the Governor sit in the domed hall below the towers, "
     "the Chodo Habat Parkway carries the capital's traffic past its doors, and the Council has voted to join the "
     "Confederacy.", None),
    ("tel_terminal", ["hod_tel_terminal"], "GFX_idea_generic_logistics", {"local_supplies": 0.15}, "Thani Terminal",
     "Thani's spaceport, a vaulted terminal hall with round docking bays on its landing side. Since the vote for "
     "secession, Separatist freighters and couriers outnumber the Republic liners that once filled them.", None),
    ("tel_academy", ["hod_tel_academy"], "GFX_idea_generic_army_support", {"resistance_target": 0.05},
     "Telos Polar Academy", "A hidden school in the polar ice, built by the Jedi Master Atris after the Jedi Civil War "
     "and empty for millennia. Its round council chamber, laid out like the Jedi Council's on Coruscant, still stands "
     "under the snow; the Jedi know where it is, the Separatist governors do not.", None),
    ("tel_caverns", ["hod_tel_caverns"], "GFX_idea_generic_improved_industries", {"local_resources_factor": 0.1},
     "Mirror Caverns", "Caves in a forest glade high in the snow-capped mountains, lined with malab, a rare black "
     "mineral so slick and lustrous that first-time visitors lose their footing in the shimmering dark. Prospectors "
     "quarry it under licence from the Council.", None),
    ("tel_rz", ["hod_tel_rz"], "GFX_idea_generic_pp_unity_bonus", {"stability_factor": 0.01, "local_supplies": 0.05},
     "RZ-0031", "The first Restoration Zone, where the Ithorians brought Telos's poisoned land back to life behind "
     "shield walls. Its beaches, canyons and grassland of blba trees and blue bachani flowers are kept as a reserve in "
     "the middle of the city, and its old shield pylons and air defense tower as monuments.", None),
    ("ser_carannia", ["hod_ser_carannia"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Carannia", "The capital of Serenno, an old city of pale stone and slate spires among golden forests, rich from "
     "the fortunes of the Great Houses. Its Count, Dooku, left the Jedi Order, took back his family's title and wealth, "
     "and now speaks for the Confederacy of Independent Systems from his own homeworld.", None),
    ("ser_assembly", ["hod_ser_assembly"], "GFX_idea_generic_conference", {"compliance_gain": 0.03},
     "Great Assembly House", "The domed hall of Serenno's Planetary Council in Carannia, where the noble houses "
     "debate under a dome ribbed in gold. The Council long ago gave its loyalty to the Count; its votes for "
     "secession were never close.", None),
    ("ser_castle", ["hod_ser_castle"], "GFX_idea_generic_secret_police", {"resistance_target": -0.05, "local_supplies": 0.1},
     "Castle Serenno", "The ancestral seat of House Serenno on the edge of a cliff over the valley of Serenno City. "
     "Count Dooku has made it his headquarters: Separatist envoys land on its platform, and those who enter its halls "
     "do not always leave them.", None),
    ("ser_borgin", ["hod_ser_borgin"], "GFX_idea_generic_fortify_the_borders", {"resistance_target": -0.03},
     "Borgin Castle", "A hill castle of one of Serenno's lesser houses in the Upper Forest, its curtain wall and slate "
     "towers older than the Republic's hold on the sector. Its lords keep their household guard and pay their dues "
     "to the Count.", None),
    ("ser_spike", ["hod_ser_spike"], "GFX_idea_generic_prisoner", {"resistance_damage_to_garrison": -0.1},
     "The Spike", "An inverted cone of cells sunk deep into the rock of the Aparian Wastes, built by the Confederacy "
     "for prisoners too valuable to kill and too dangerous to keep anywhere else. Officially it does not exist.", None),
    ("yav_temple", ["hod_yav_temple"], "GFX_idea_generic_research_bonus", {"local_supplies": 0.1},
     "Great Temple", "The greatest of the Massassi temples, a stepped ziggurat of grey stone rising above the jungle "
     "canopy, raised for the Sith four thousand years ago and left to the vines when its builders died out. A "
     "Separatist survey team has marked its hollow halls as a possible base.", None),
    ("yav_exarkun", ["hod_yav_exarkun"], "GFX_idea_generic_oppression", {"resistance_target": 0.05},
     "Temple of Exar Kun", "A dark stepped pyramid crowned by an obelisk, built by the enslaved Massassi for the Sith "
     "Lord Exar Kun. Spacers say a red light still burns in its spire at night, and the few who camp near it do not "
     "stay long.", None),
    ("yav_borundi", ["hod_yav_borundi"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Borundi Peak", "A sleeping volcano over Yavin IV's north-eastern highlands, its slopes broken by old lava spurs "
     "and a Massassi shrine climbing its southern flank. Its rivers feed the jungle below.", None),
    ("cel_city", ["hod_cel_city"], "GFX_idea_generic_economic_increase", {"stability_factor": 0.02, "local_supplies": 0.1},
     "Celanon City", "A sprawl of nearly two hundred square kilometres on Cekbar and one of the great markets of the "
     "Outer Rim, governed by its trade guilds from the towers round the exchange. The guilds took the Confederacy's "
     "side when its tariffs promised to be lower than the Republic's.", None),
    ("cel_control", ["hod_cel_control"], "GFX_idea_generic_logistics", {"local_supplies": 0.15},
     "Spaceport Control", "A tower of nearly 140 storeys in the Celanon Spaceport, whose controllers route every ship "
     "in orbit so that the Spur's traffic never collides. Whoever holds the tower holds the planet's sky lanes.", None),
    ("cel_hospital", ["hod_cel_hospital"], "GFX_idea_generic_manpower_bonus", {"local_manpower": 0.1},
     "Merchant Guild Medical Facility", "The Merchant Guild's hospital near the starport, where spacers off every "
     "ship that lands are patched up, for a price the Guild sets.", None),
    ("cel_gularg", ["hod_cel_gularg"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Gularg's Libation Emporium", "Gularg the Hutt's tavern, held to be the rowdiest, seediest and most dangerous "
     "in Celanon City. Smugglers, bounty hunters and both sides' informants drink under the same dome.", None),
    ("bot_palace", ["hod_bot_palace"], "GFX_idea_generic_political_support", {"compliance_gain": 0.03},
     "Governor's Palace", "The planetary governor's seat, raised on a steel podium above the smog of the works. "
     "The yards' owners dictate its policy, and they have chosen the Confederacy's contracts.", None),
    ("bot_elevator", ["hod_bot_elevator"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Space Elevator", "Cables 325 kilometres long climb from this anchor station to the yards in orbit, carrying "
     "hull plate and machinery up by the thousand tonnes every day.", None),
    ("bot_yards", ["hod_bot_yards"], "GFX_idea_generic_navy_bonus", {"state_production_speed_dockyard_factor": 0.1},
     "Botajef Shipyards", "Botajef Shipyards, builders of the AA-9 Coruscant freighter and the SS-54 light "
     "freighter. Hulls are framed in the slips of the orbital yards at the top of the elevator and fitted out in the "
     "starship works of the southern continent. Their freighter lines are being refitted for Separatist logistics.", None),
    ("bot_northbase", ["hod_bot_northbase"], "GFX_idea_generic_radar", {"resistance_target": -0.03},
     "North-Polar Base", "A sensor and communications base on the northern ice, listening to the traffic of the "
     "Celanon Spur.", None),
    ("bot_southbase", ["hod_bot_southbase"], "GFX_idea_generic_army_support", {"local_supplies": 0.1},
     "South-Polar Base", "A base in the south-polar region where the shipyards test drives and weapons far from "
     "the works.", None),
    ("axx_capital", ["hod_axx_capital"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Axxila City", "The heart of a metropolis that has spread over the whole of Axxila's cliffs, its terraces stepping "
     "down the rock faces and its towers crowding the heights. Its council followed the Ciutric Hegemony into the "
     "Confederacy; the Free Axxilans who refused have left for Halmad.", None),
    ("axx_fossfog", ["hod_axx_fossfog"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Fossfog's", "A stone cantina under a neon sign whose wine cellar hides an underworld bounty feed. Hunters come "
     "from across the D'Astan sector to read it.", None),
    ("axx_oreport", ["hod_axx_oreport"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Ore Terminal", "Where Axxila's ores leave the planet: silos, conveyors and bulk freighters loading day and night "
     "for the Hegemony's foundries.", None),
    ("cit_daplona", ["hod_cit_daplona"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Daplona", "The capital of Ciutric IV and of the Hegemony, its finned towers rising over the Daplona River. The "
     "Shine Astara, one of its most exclusive restaurants, turns slowly near the top of the tallest; deals for the "
     "Confederacy are made at its tables.", None),
    ("cit_training", ["hod_cit_training"], "GFX_idea_generic_army_support", {"local_manpower": 0.1},
     "Daplona Base Training Center", "The Hegemony's training base outside Daplona: barracks round a drill field, an "
     "obstacle course and a firing range, where the Hegemony's levies learn to fight beside the droid armies.", None),
    ("cit_prison", ["hod_cit_prison"], "GFX_idea_generic_prisoner", {"resistance_damage_to_garrison": -0.1},
     "Ciutric IV Prison", "A walled prison on a rocky rise below the highlands, where the Hegemony keeps those who "
     "argued against secession.", None),
    ("cit_mansion", ["hod_cit_mansion"], "GFX_idea_generic_oppression", {"resistance_target": 0.03},
     "Bane's Mansion", "A dark stone manor deep in the southern forest, kept a thousand years ago by Darth Bane. Its "
     "owners since have all sold it quickly, and the window at the top of its tower is never dark.", None),
    ("ces_chikatlik", ["hod_ces_chikatlik"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "ChikatLik", "The capital of Ord Cestus, grown round the great hive spires of the X'Ting. Offworlders run its "
     "droid trade from the lower town while the hive queens keep the spires; both are courted by the Confederacy.", None),
    ("ces_cybernetics", ["hod_ces_cybernetics"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Cestus Cybernetics", "The droid maker that made Ord Cestus rich. Its JK-series security droids, too clever for "
     "their makers' comfort, sell to anyone who can pay, and the Separatists pay best.", None),
    ("ces_penitentiary", ["hod_ces_penitentiary"], "GFX_idea_generic_prisoner", {"resistance_damage_to_garrison": -0.1},
     "Cestus Penitentiary", "Built by the Republic in 321 BBY on land the X'Ting gave, its cell blocks reach down under "
     "Kibo Lake. The Kibo Geothermal Station on the shore powers it.", None),
    ("ces_jantos", ["hod_ces_jantos"], "GFX_idea_generic_political_support", {"compliance_gain": 0.02},
     "Jantos", "Ord Cestus' second city, terraced up a red butte with hive spires on its crest.", None),
    ("ces_droidworks", ["hod_ces_droidworks"], "GFX_idea_generic_production_bonus", {"local_building_slots": 1},
     "Cestus Droid Works", "Foundries and assembly halls at Clandes, where droid shells come off the lines by the "
     "thousand for Cestus Cybernetics and its rivals.", None),
    ("ces_fungus", ["hod_ces_fungus"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Barrens Fungus Farms", "Grow vaults and fungus pits round Barrens, raising the fungi Ord Cestus sells offworld "
     "beside its droids.", None),
    ("dat_lair", ["hod_dat_lair"], "GFX_idea_generic_political_support", {"stability_factor": 0.03, "compliance_gain": 0.02},
     "Nightsister Lair", "Mother Talzin's fortress, its chambers cut into a mountain of crooked spires and lit by the "
     "green of the sisters' magick. Below it lies the Hidden Cave, which no one reaches but by magick. Count Dooku's "
     "envoys come and go, and the Nightsisters judge what the Confederacy is worth to them.", None),
    ("dat_village", ["hod_dat_village"], "GFX_idea_generic_army_support", {"local_manpower": 0.1},
     "Nightbrother Village", "The Zabrak warriors' village among the rock spires, where the Nightbrothers live apart "
     "from the sisters, bound to serve them. The strongest of them are chosen and taken to the lair.", None),
    ("dat_arena", ["hod_dat_arena"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Nightbrother Arena", "A ring of stone tiers round a floor of red earth, where the Nightbrothers fight their "
     "trials before their chieftain.", None),
    ("dat_singing", ["hod_dat_singing"], "GFX_idea_generic_army_support", {"resistance_target": -0.03},
     "Singing Mountain", "The walled stronghold of the Singing Mountain clan, witches who keep to the light where the "
     "Nightsisters keep to the dark. Their rancors are penned at the mountain's foot.", None),
    ("dat_nardithi", ["hod_dat_nardithi"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Nardithi Cluster", "A field of hexagonal stone spikes rising out of the jungle, older than any clan's memory.", None),
    ("man_sundari", ["hod_man_sundari"], "GFX_idea_generic_political_support", {"stability_factor": 0.03, "compliance_gain": 0.02},
     "Sundari", "The New Mandalorians' capital, a city of cubes under a vast black dome on the white desert the "
     "Excision left, built over one of the largest beskar mines on Mandalore. The Republic recognises it, not Keldabe, "
     "as the planet's capital; from its Royal Palace by the Peace Park Duchess Satine Kryze keeps Mandalore neutral.", None),
    ("man_keldabe", ["hod_man_keldabe"], "GFX_idea_generic_army_support", {"local_manpower": 0.1},
     "Keldabe", "The clans' capital since before the Mandalorian Wars, a hill-fort town on granite in a bend of the "
     "Kelita River. Its streets are a jumble of plaster houses, warehouses and granite towers; the clan chiefs meet in "
     "the Oyu'baat, and the MandalMotors tower with its mythosaur skull guides pilots home.", None),
    ("man_beskar", ["hod_man_beskar"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.15},
     "Tokursh Beskar Mines", "Deep pits in the Tokursh badlands, the richest beskar country on Mandalore. Clan "
     "smiths guard the secrets of working the iron; the government in Sundari guards the pits.", None),
    ("man_dwcamp", ["hod_man_dwcamp"], "GFX_idea_generic_secret_police", {"resistance_target": 0.05},
     "Death Watch Camp", "A hidden camp of Death Watch, the exiles who would return Mandalore to its warrior past. "
     "Pre Vizsla's fighters train here and wait for allies against the Duchess.", None),
    ("man_cityofbone", ["hod_man_cityofbone"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "City of Bone", "An amusement park an enterprising Mandalorian built in the shape of a giant mythosaur skeleton, "
     "hoping to draw adventure tourists to Mandalore. They never came; its rides stand idle on the plains by Enceri.", None),
    ("man_norgbral", ["hod_man_norgbral"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Norg Bral", "A hill-fort town behind two rings of stone walls, home of Clan Bralor. Its warriors answer to their "
     "chieftain before any council in Sundari.", None),
    ("tar_spires", ["hod_tar_spires"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Upper City", "The towers of Taris' rich, raised again over the ruins the Sith fleet left four thousand years ago "
     "and guarded by private security. From their decks the city looks out over smog and the slums below.", None),
    ("tar_pit", ["hod_tar_pit"], "GFX_idea_generic_secret_police", {"resistance_target": 0.04},
     "Undercity", "A shaft sunk through every level of the city to the ground, where outcasts live in the rubble "
     "among the rakghouls. Below its sewers, the stories say, lies the Promised Land, the city of the first "
     "Tarisians.", None),
    ("tar_swoop", ["hod_tar_swoop"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Tarisian Swoop Track", "The banked track where the Season Opener has been raced since before the bombardment. "
     "The gangs that sponsor the riders settle their scores in the stands.", None),
    ("tar_jedi", ["hod_tar_jedi"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Jedi Tower", "The broken tower of the old Taris Academy at Highport, empty since the bombardment, beside the "
     "walled base where the Republic once sought a cure for the rakghoul plague.", None),
    ("way_tantiss", ["hod_way_tantiss"], "GFX_idea_generic_secret_police", {"resistance_target": -0.03},
     "Mount Tantiss", "A mountain whose southern face has been sealed with blast doors and plated terraces. Whoever "
     "is building inside it pays well and allows no questions.", None),
    ("way_colony", ["hod_way_colony"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Wayland Colony", "The human colonists' palisaded town on its rise, with a stone keep, a market, and a landing "
     "field outside the wall.", None),
    ("way_council", ["hod_way_council"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Council Village", "Where the Psadan and the Myneyrshi meet round a ring of standing stones. Old enemies, they "
     "are of one mind about the colonists.", None),
    ("con_city", ["hod_con_city"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.03},
     "Concordia City", "The walled city from which Pre Vizsla governs Concordia for the Duchess, and from which, in "
     "secret, he leads Death Watch.", None),
    ("con_mines", ["hod_con_mines"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Concordian Mines", "Mines worked out long ago and left to rust. Their galleries make good storehouses for "
     "weapons the Duchess does not know about.", None),
    ("con_hideout", ["hod_con_hideout"], "GFX_idea_generic_army_support", {"local_manpower": 0.1},
     "Death Watch Hideout", "A camp under the forest at the foot of a cliff, where Death Watch trains, hides its ships, "
     "and waits to take Mandalore back from the pacifists.", None),
    ("bra_yards", ["hod_bra_yards"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Scrapper Guild Yards", "Where the Scrapper Guild cuts old starships apart, plate by plate, under its gantries. "
     "An old Derriphan lies here in two halves, and the Republic buys back the steel.", None),
    ("bra_platform", ["hod_bra_platform"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Platform Thirty-Two", "One of the Guild's great raised platforms, where a Hammerhead is being broken. Scrappers "
     "who miss their quota are cut from the roster.", None),
    ("bra_tower", ["hod_bra_tower"], "GFX_idea_generic_radar", {"resistance_target": -0.03},
     "Retired Control Tower", "A control tower from the days when Bracca still built ships, left standing over the "
     "plains it once directed traffic across.", None),
    ("bra_rail", ["hod_bra_rail"], "GFX_idea_generic_production_bonus", {"local_building_slots": 1},
     "Worker Rail Route 213", "The trestle line that carries the scrappers between their towns and the yards on every "
     "shift.", None),
    ("bra_town", ["hod_bra_town"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Scrapper Town", "Habitat boxes stacked round a yard, where the Guild's workers sleep between shifts.", None),
    ("tra_forak", ["hod_tra_forak"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Forak", "The Trandoshan capital behind its spiked walls, where the clans meet in the great hall and count their "
     "hunters' jagannath points.", None),
    ("tra_market", ["hod_tra_market"], "GFX_idea_generic_secret_police", {"resistance_target": 0.04},
     "Slaver Market", "Cages and auction stages where Trandoshan slavers sell their catches, beside the arena where "
     "captives are hunted for points.", None),
    ("tra_lodge", ["hod_tra_lodge"], "GFX_idea_generic_army_support", {"local_manpower": 0.1},
     "Great Hunting Lodge", "A hunters' lodge on a bluff over the jungle, its front hung with the skulls of its "
     "members' finest prey.", None),
    ("tra_shrine", ["hod_tra_shrine"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Scorekeeper's Shrine", "A stepped shrine to the Scorekeeper, the goddess who weighs every Trandoshan's jagannath "
     "points. Hunters bring her their trophies before a great hunt.", None),
    ("nyr_locus", ["hod_nyr_locus"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Locus", "Nyriaan's capital, divided between the Mining Guild Sector and the rest of the city, with the Neutral "
     "Zone at its centre where everyone's business is welcome. The Trade Federation buys the Guild's ore and its "
     "goodwill.", None),
    ("nyr_prosperity", ["hod_nyr_prosperity"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.15},
     "Prosperity Mine", "The pit beside the town of Prosperity, which gave the town its hopes and its name.", None),
    ("nyr_arena", ["hod_nyr_arena"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Nyriaan Gladiator Arena", "A bowl of rusted plate where miners bet their wages on fighters and beasts.", None),
    ("nyr_finalrest", ["hod_nyr_finalrest"], "GFX_idea_generic_radar", {"resistance_target": -0.03},
     "Final Rest", "A narrow plateau a hundred kilometres north of Locus, one of the highest points on Nyriaan. A "
     "sensor outpost on its summit watches the whole region.", None),
    ("crs_port", ["hod_crs_port"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Corsin Port", "The white city on the inner sea where the Republic's governor keeps a domed palace above the "
     "harbour.", None),
    ("crs_retreat", ["hod_crs_retreat"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Corsin Retreat", "The hill retreat where Republic commanders met in 738 BBY to decide the course of a war. Its "
     "rotunda is still offered to the Republic's generals and Jedi.", None),
    ("crs_resort", ["hod_crs_resort"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Tinn'lyi Islands", "Bungalows on stilts over the shallows of the Tinn'lyi Islands, a resort for the Core's "
     "wealthy.", None),
    ("crs_station", ["hod_crs_station"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "Selligore Station", "A platform over the banks where scientists follow the selligore, sea mammals more than "
     "twenty metres long, through their feeding grounds.", None),
    ("kas_kachirho", ["hod_kas_kachirho"], "GFX_idea_generic_political_support", {"stability_factor": 0.03, "compliance_gain": 0.02},
     "Kachirho", "The Wookiee city on the Wawaatt coast, its homes climbing the great wroshyr in rings of timber "
     "platforms over the beach. Chieftains Tarfful and Chewbacca's kin keep watch on the lagoon.", None),
    ("kas_refinery", ["hod_kas_refinery"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Kashyyyk Oil Refinery", "Tanks and a cracking column in timber scaffolding near Kachirho, fuelling the Wookiee "
     "fleet and the coastal defences.", None),
    ("kas_rwookrrorro", ["hod_kas_rwookrrorro"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Rwookrrorro", "A city spread across a web of platforms between six great wroshyrs, high above the forest "
     "floor.", None),
    ("kas_caverns", ["hod_kas_caverns"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Myyydril Caverns", "Caves under the Black Forest, which the Wookiees believe cursed. Webs hang between its "
     "twisted trees and few who go in come back.", None),
    ("kas_wartaki", ["hod_kas_wartaki"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Wartaki Islands", "A Republic outpost on the Wartaki Islands, white prefab bunkers inside a Wookiee palisade, "
     "watching the approaches from the sea.", None),
    ("ond_iziz", ["hod_ond_iziz"], "GFX_idea_generic_political_support", {"stability_factor": 0.03, "compliance_gain": 0.02},
     "Iziz", "Onderon's ancient capital behind the walls raised against the beasts of the jungle, the Unifar Temple "
     "rising over Malgan Market. King Ramsis Dendup rules from it and keeps Onderon out of the war.", None),
    ("ond_nest", ["hod_ond_nest"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "The Nest", "A fort of logs on a peak in the highlands east of Iziz, where young Onderonians who want no "
     "masters train to fight.", None),
    ("ond_camp", ["hod_ond_camp"], "GFX_idea_generic_secret_police", {"resistance_target": 0.05},
     "Saw Gerrera's Camp", "A hidden camp under a cliff in the jungle of Sector S-29, where Saw and Steela Gerrera "
     "gather fighters and stolen weapons.", None),
    ("ond_kira", ["hod_ond_kira"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Kira Fortress", "The fortress of the House of Kira in the wilds outside Iziz, older than most of the city's "
     "walls.", None),
    ("ond_lodge", ["hod_ond_lodge"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Beast Riders' Lodge", "The hunting lodge of the Clazca, a clan of the Beast Riders who tame and fly the drexl "
     "of the highlands.", None),
    ("umb_capital", ["hod_umb_capital"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Umbaran Capital City", "Dark spires lit by cold blue light, the seat of the Umbaran government that holds its seat "
     "in the Senate and listens to Separatist envoys.", None),
    ("umb_airbase", ["hod_umb_airbase"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Umbaran Airbase", "The militia's airbase near Sector Delta, its pads lit in the dusk, home to the Umbarans' "
     "agile starfighters.", None),
    ("umb_bunker", ["hod_umb_bunker"], "GFX_idea_generic_army_support", {"resistance_target": -0.02},
     "Umbaran Bunkers", "Bunkers Grek, Krill and Usk, dug into the dark hills and armoured against any landing.", None),
    ("umb_academy", ["hod_umb_academy"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Sith Academy", "The ruins of the academy the Brotherhood of Darkness founded at the end of the New Sith Wars. "
     "The jungle keeps away from its red-lit crown.", None),
    ("col_hive", ["hod_col_hive"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Colla Hive", "The spires of the Colicoid hive capital, where the Colicoid Creation Nest's masters sell to the "
     "Trade Federation and anyone else who pays.", None),
    ("col_nest", ["hod_col_nest"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.15},
     "Colicoid Creation Nest", "The factory that makes the droidekas, its shell halls rolling out the destroyer droids "
     "the Trade Federation fields.", None),
    ("col_spawn", ["hod_col_spawn"], "GFX_idea_generic_army_support", {"local_manpower": 0.1},
     "Spawning Grounds", "The pools of the Colicoid spawnworld, where eggs are laid by the thousand and guarded by the "
     "hive.", None),
    ("rus_mausoleum", ["hod_rus_mausoleum"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Jedi Mausoleum", "After the last Battle of Ruusan, Johun Othone asked the Senate to raise a mausoleum over "
     "the fallen in the Valley of the Jedi. A thousand years later its statues still raise their blades over the "
     "burnt valley.", None),
    ("rus_cave", ["hod_rus_cave"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Thought-bomb Cave", "The cave where Lord Kaan set off the thought bomb that took the Brotherhood of Darkness "
     "and the Jedi with it. The few who know of it say the souls are still bound there.", None),
    ("rus_camp", ["hod_rus_camp"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Army of Light Encampment", "The earthworks and graves of the Army of Light, the Jedi and Republic troops whom "
     "Lord Hoth and Valenthyne Farfalla led through the seven Battles of Ruusan.", None),
    ("rus_fort", ["hod_rus_fort"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Fort Nowhere", "A walled landing field beside Katarn's Hill, where smugglers, claim jumpers and fugitives of "
     "the Teraab sector put down far from the law.", None),
    ("rus_olmondo", ["hod_rus_olmondo"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Olmondo", "Ruusan's capital, rebuilt in fieldstone after the war burnt the old cities. Its assembly now leans "
     "toward the Separatists, who promise to remember the worlds the Republic forgot.", None),
    # --- Ithor (Legends: the herdship cities over the sacred Mother Jungle, the Falls of Dessiar)
    ("ith_tafanda", ["hod_ith_tafanda"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Tafanda Bay", "The greatest of the Ithorian herdships and the seat of Ithor's elected council, a floating garden "
     "city of living hulls that drifts over the clouds so its people never wound the Mother Jungle below. Offworld "
     "traders land at its balcony to buy Ithorian medicines and botanicals.", None),
    ("ith_tarintha", ["hod_ith_tarintha"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Tree of Tarintha", "A herdship grown round a single colossal tree, its roots trailing far below the hull. Its "
     "herd tends gardens that feed half the Ithorian fleet of cities.", None),
    ("ith_cloudmother", ["hod_ith_cloudmother"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Cloud-Mother", "A herdship of three linked hulls, home of the House of the Healers, where Ithorian healers "
     "treat patients from across the Mid Rim with the medicines of the jungle.", None),
    ("ith_falls", ["hod_ith_falls"], "GFX_idea_generic_political_support", {"compliance_gain": 0.03},
     "Falls of Dessiar", "Waterfalls in a horseshoe of jungle cliffs, renowned across the galaxy for their beauty and "
     "peace. No Ithorian may walk there under the Law of Life; they watch them from the herdships passing over.", None),
    # --- Ord Mantell (Legends first: Worlport; canon: Ord Mantell City, its junkyards and mining tunnels)
    ("om_city", ["hod_om_city"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Ord Mantell City", "The capital, a sprawl of towers and old mining districts over tunnels nobody has mapped in "
     "centuries. Bounty hunters, smugglers and Black Sun's agents do their business in its back streets.", None),
    ("om_worlport", ["hod_om_worlport"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Worlport", "Ord Mantell's great spaceport city, built in the Corellian style of its first settlers in the days "
     "of the Old Republic, with a Casino District that draws gamblers from across the Mid Rim.", None),
    ("om_junkyard", ["hod_om_junkyard"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Ord Mantell Junkyards", "Mountains of scrapped starships and droids on the edge of the capital, where salvagers "
     "strip hulls for parts and anyone can disappear for a price.", None),
    ("om_oldcity", ["hod_om_oldcity"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Old Ord Mantell City", "The ruins of the first capital, abandoned when the settlers moved on. Its broken towers "
     "shelter scavengers, outlaws and the gangs that hunt them.", None),
    ("om_garnik", ["hod_om_garnik"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Fort Garnik", "A Republic stronghold on the volcanic island of Avilatan, its guns covering the Bright Sea from "
     "the black slopes below Mount Avilatan, where lava still runs past the walls.", None),
    # --- Garqi (Legends: Pesktda, the Agricultural University, the Xenobotanical Garden, the Vlassy River)
    ("gar_pesktda", ["hod_gar_pesktda"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Pesktda", "Garqi's capital, a graceful city of broad avenues lined with bimiza trees and dotted with parks, its "
     "Xenobotanical Garden home to a grove of telepathic bafforr trees brought from Ithor.", None),
    ("gar_university", ["hod_gar_university"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.1}, "Garqi Agricultural University", "The leading university of "
     "Garqi, where the agronomists of the Mid Rim learn their trade, and its students argue politics late into the night.", None),
    ("gar_combine", ["hod_gar_combine"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Garqi Agricultural Combine", "The silos and processing works of the Combine that feeds Garqi and ships grain and "
     "caf to the banking worlds of the Core.", None),
    ("gar_vlassy", ["hod_gar_vlassy"], "GFX_idea_generic_political_support", {"compliance_gain": 0.03},
     "Vlassy Nature Preserve", "Forested bluffs and canyons along the Vlassy River, too rough to farm, kept wild and "
     "visited by tourists in the caf off-season.", None),
    # --- Agamar (Legends: Calna Muun, the Council Center, the University, the Crescent Sea ruins, natural bridges)
    ("aga_calna", ["hod_aga_calna"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Calna Muun", "Agamar's capital and spaceport on the shore of the Crescent Sea, where the Agamarian Council meets "
     "in the shell-roofed Council Center. Its farmers and ranchers have lately thrown in their lot with the Confederacy.", None),
    ("aga_university", ["hod_aga_university"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.1}, "University of Agamar", "A college of a frontier world with a "
     "xenoarchaeology faculty respected across the sector, built on what the droughts uncovered in the Crescent Sea.", None),
    ("aga_ruins", ["hod_aga_ruins"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Crescent Shallows Ruins", "The stepped temple of a civilisation that lived under the Crescent Sea in the days of "
     "the Rakatan Infinite Empire, laid bare by drought. Farmers nearby swear the stones still hum at night.", None),
    ("aga_bridges", ["hod_aga_bridges"], "GFX_idea_generic_political_support", {"compliance_gain": 0.03},
     "Stone Bridges", "Great natural arches worn into the red rock of the northern badlands, where Agamarian youngsters "
     "race their repulsorcraft through the gaps.", None),
    ("aga_ranch", ["hod_aga_ranch"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Mugruebe Ranches", "The ranges where Agamar raises its mugruebe, beasts of burden and the meat of the stew the "
     "rest of the galaxy will not eat.", None),
    # --- Ord Trasi (Legends: the Republic's ordnance depot fortress world, the shipyards, the salvage yards)
    ("ot_depot", ["hod_ot_depot"], "GFX_idea_generic_army_support", {"local_manpower": 0.05, "local_supplies": 0.1},
     "Ord Trasi Depot", "An ordnance and regional depot fortress the Republic built to supply its exploration fleets, "
     "its walls bristling with turbolasers over the cold dust plains. Who holds Ord Trasi holds the Braxant Run.", None),
    ("ot_yards", ["hod_ot_yards", "hod_ot_orbital"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.15}, "Ord Trasi Shipyards", "What began as a refuelling stop grew into "
     "one of the Outer Rim's great construction centres for capital ships, with cradles on the flats and slips in orbit "
     "where Dreadnaught cruisers take shape.", None),
    ("ot_salvage", ["hod_ot_salvage"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Ord Trasi Salvage Yards", "Old warships come here to be cut apart; their metal goes back into the yards' new hulls.", None),
    # --- Dantooine (Legends: Khoonda, the ruined Jedi Enclave, the ancient Jedi temple, the Rakatan ruins, the caves)
    ("dan_khoonda", ["hod_dan_khoonda"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Khoonda", "The walled seat of Dantooine's settlers, raised from the old Matale estate after the Jedi Civil War, "
     "where the farmers of the plains govern themselves and keep a militia against raiders.", None),
    ("dan_enclave", ["hod_dan_enclave"], "GFX_idea_generic_political_support", {"compliance_gain": 0.03},
     "Jedi Enclave", "The ruins of the Jedi Enclave of Vodo-Siosk Baas, bombed from orbit by Darth Malak four thousand "
     "years ago and never rebuilt. Grass grows in its courtyard round the ancient tree.", None),
    ("dan_rakatan", ["hod_dan_rakatan"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Ancient Temple", "A temple of the Rakatan Infinite Empire half sunk into a mound north-east of the Enclave, its "
     "doorway still glowing; the Star Map within has been dark since the Jedi Civil War.", None),
    ("dan_matale", ["hod_dan_matale"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Matale Estate", "The walled house of the Matale family on its grounds east of the river, its kath hounds penned in "
     "the yard. The settlers' first council met here before Khoonda was built.", None),
    ("dan_sandral", ["hod_dan_sandral"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Sandral Estate", "The long house of the Sandral family, old rivals of the Matales, with its garden terraces and "
     "landing pad on the south-western grounds.", None),
    ("dan_grove", ["hod_dan_grove"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "The Grove", "A glade where the Jedi of the Enclave meditated round an ancient tree inside a ring of standing "
     "stones. The settlers say something dark still lingers there.", None),
    ("dan_cave", ["hod_dan_cave"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.1},
     "Crystal Caves", "Caves in the Taikaha Hills where kinrath nest, and where Jedi once found kyber crystals in their "
     "eggs.", None),
    # --- Dubrillion (Legends: high-rise resort cities, the Dubrillion Aquarium)
    ("dub_capital", ["hod_dub_capital"], "GFX_idea_generic_political_support", {"stability_factor": 0.02, "compliance_gain": 0.02},
     "Dubrillion City", "The capital of a garden world, its white towers of hotels and luxury suites rising round the "
     "Dubrillion Aquarium, where emerald sharks circle a great cylindrical tank. The banking clan's wealthy come here to "
     "spend what they earn elsewhere.", None),
    ("dub_resort", ["hod_dub_resort"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Sapphire Coast", "Terraced hotels stepping down to the beaches of the eastern shore, their pools on every level.", None),
    # --- Bastion (Legends: Ravelin, Sartinaynian City, the customs station)
    ("bas_ravelin", ["hod_bas_ravelin"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Ravelin", "The stern stone capital of the Braxant sector, its Sector Hall raising a dark spire over the hills. Its "
     "governors already speak of order more than of the Senate.", None),
    ("bas_sartinaynian", ["hod_bas_sartinaynian", "hod_bas_customs"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Sartinaynian City", "The harbour city of the south-eastern coast, its terraces climbing the hill above freighters "
     "at the quays; every ship bound for Bastion first stops at the customs station in orbit.", None),
    ("kal_kaleela", ["hod_kal_kaleela"], "GFX_idea_generic_army_support", {"local_manpower": 0.1},
     "Kaleela", "The Kaleesh capital, its temple-houses climbing the walls of a moss-covered canyon under the mask of "
     "the elders' palace. Fresh from the Huk War, its warriors owe their victory to the Banking Clan's credits.", None),
    ("kal_shrupak", ["hod_kal_shrupak"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Shrupak", "The most sacred temple of the Kaleesh, on the edge of the Ausez Steppes, held by Qymaen jai Sheelal and "
     "Ronderu lij Kummar against the Yam'rii.", None),
    ("kal_abesmi", ["hod_kal_abesmi"], "GFX_idea_generic_political_support", {"compliance_gain": 0.03},
     "Abesmi", "The island-monolith of the Jenuwaa Sea, from which the Kaleesh gods ascended to heaven. Pilgrims climb "
     "its winding stair to the shrine at the top.", None),
    ("kal_warruzan", ["hod_kal_warruzan"], "GFX_idea_generic_secret_police", {"resistance_target": 0.05},
     "Warru'zan", "The bloodhalls of the Kaleesh elders, cut into a canyon wall, where the young are taught the ways of "
     "war and honour.", None),
    # --- Muunilinst (Legends: Harnaidan, High Port, Mariunhus, Pilaan)
    ("muun_harnaidan", ["hod_muun_harnaidan", "hod_muun_highport"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.15}, "Harnaidan", "The greatest Muun city and the headquarters of the "
     "InterGalactic Banking Clan, built round spires four kilometres tall; San Hill rules from his citadel, and a "
     "skyhook climbs from the city to High Port.", None),
    ("muun_mariunhus", ["hod_muun_mariunhus"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.15},
     "Mariunhus", "A vault-spire built round a smoker rich in gold and platinum, out at sea: a mountain of wealth that "
     "can be mined at a moment's notice to guarantee credit anywhere in the galaxy.", None),
    ("muun_pilaan", ["hod_muun_pilaan"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Pilaan Podrace Course", "The course outside Pilaan, one of Muunilinst's largest cities, where podracers fly under "
     "the arches before crowds of Muuns who bet on everything.", None),
    # --- Mygeeto (Legends: Jygat and the Dressian Kiolsh bank, the crystal mines; canon: the spaceport city, the
    # Southern Mesas, the Hammertong facility)
    ("myg_jygat", ["hod_myg_jygat"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Jygat", "A city at the edge of the ice sheets, where the Dressian Kiolsh Merchant Bank has carved its vaults into "
     "the glacier itself. Its doors glow with the crystal that powers every tower on Mygeeto.", None),
    ("myg_city", ["hod_myg_city"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Mygeeto City", "The great spaceport metropolis of the Banking Clan, its dark spires rising out of the ice chasms "
     "with crystal crowns, its bridges strung between them over the drop.", None),
    ("myg_mesas", ["hod_myg_mesas"], "GFX_idea_generic_army_support", {"local_supplies": 0.05},
     "Southern Mesas", "Towers built on top of the sheer southern mesas and joined to one another by bridges, out of "
     "reach of anyone on the ice below.", None),
    ("myg_hammertong", ["hod_myg_hammertong"], "GFX_idea_generic_secret_police", {"resistance_target": 0.05},
     "Hammertong Facility", "A Geonosian research station on the ice, its spires shipped in from Geonosis. What the "
     "drones do to the crystal in its test cradle, the Banking Clan does not say.", None),
    ("myg_mines", ["hod_myg_mines"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.15},
     "Crystal Mines", "Mountains of crystal spurs cut into by the Banking Clan's miners, the source of the synthesized "
     "crystals that power Mygeeto's capacitor towers.", None),
    # --- Yaga Minor (Legends: the Yagai hive, Yavvitiri Spaceport, the Preparation Center, drive units, the shipyards)
    ("yag_hive", ["hod_yag_hive"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Yagai Hive", "The mounds of the Yagai rising out of the forest, home to castes that have built starships for the "
     "galaxy for longer than the Republic has kept records of it.", None),
    ("yag_spaceport", ["hod_yag_spaceport", "hod_yag_yards"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Yaga Minor Shipyards", "Yavvitiri Spaceport on the ground and the shipyards in orbit above it, where Yagai crews "
     "assemble the hulls of Republic cruisers in cradles of curved ribs.", None),
    ("yag_center", ["hod_yag_center"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Preparation Center", "A secluded Republic campus a few kilometres from Yavvitiri, built to train the crews of a "
     "Jedi expedition beyond the galaxy that has not yet been launched.", None),
    ("yag_works", ["hod_yag_works"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Drive Works", "The halls where Yaga Minor's starship drive units are built and fired on their test stands before "
     "being shipped across the galaxy.", None),
    # --- Ansion (Legends: Cuipernam, the Alwari overclan the Borokii, Dashbalar)
    ("ans_cuipernam", ["hod_ans_cuipernam"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Cuipernam", "The walled city of the Sorr-ul-Paan Plateau and seat of the Unity of Community. Separatist agents and "
     "the Hutt Soergg work its markets along Jaaruls Street to set the city against the plains, and through Ansion's "
     "treaties pull whole sectors out of the Republic.", None),
    ("ans_borokii", ["hod_ans_borokii"], "GFX_idea_generic_army_support", {"local_manpower": 0.1},
     "Borokii Camp", "The great camp of the Borokii, the overclan of the Alwari nomads, in the valley that bears their "
     "name. What the Borokii decide, the other clans of the plains follow.", None),
    ("ans_dashbalar", ["hod_ans_dashbalar"], "GFX_idea_generic_production_bonus", {"local_supplies": 0.1},
     "Dashbalar", "A market town round a great caravanserai, the favourite trading centre of the Qulun clan, where "
     "nomads and city folk still do business with each other.", None),
    # --- Ilum (canon: the Jedi Temple over the Crystal Caves; Legends: the Western Ice Shelf, the Circle, Fort Tonvarr)
    ("ilu_temple", ["hod_ilu_temple"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Jedi Temple of Ilum", "One of the Order's earliest temples, cut into an ice mountain over the Crystal Caves where "
     "younglings come to find the kyber crystals of their first lightsabers. Its entrance freezes shut at nightfall.", None),
    ("ilu_ruins", ["hod_ilu_ruins", "hod_ilu_circle", "hod_ilu_tonvarr"], "GFX_idea_generic_army_support", {"local_supplies": 0.05},
     "Ruins of the Ice Shelf", "The Western Ice Shelf keeps the bones of older wars: the broken Jedi shrine at the end "
     "of the Cross-Shelf Corridor, the Circle, and the drifted-over walls of Fort Tonvarr.", None),
    # --- Dorin (Legends: Dor'shan, the Baran Do temple, Dor'galk, the Jedi Enclave, the Caverns of the Hidden One)
    ("dor_dorshan", ["hod_dor_dorshan"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Dor'shan", "The Kel Dor capital, its masked towers breathing the planet's helium-rich air, kand orchards on the "
     "slopes outside it. Off-worlders walk its streets behind breath masks of their own.", None),
    ("dor_dorgalk", ["hod_dor_dorgalk"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Dor'galk", "A plateau city round the atmosphere works whose vents keep the Kel Dor's air as it should be.", None),
    ("dor_barando", ["hod_dor_barando", "hod_dor_caverns"], "GFX_idea_generic_secret_police", {"resistance_target": 0.05},
     "Baran Do Temple", "The sages of the Baran Do climb to their pavilions above Dor'shan to read what is coming, as "
     "they did before the Jedi came to Dorin. Below the plateaus, the Caverns of the Hidden One keep their own secrets.", None),
    ("dor_enclave", ["hod_dor_enclave"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Jedi Enclave of Dorin", "The Order's hall on Dorin, built in the Kel Dor manner, where Force-sensitive Kel Dor "
     "children are taught before they leave for Coruscant.", None),
    # --- Yinchorr (Legends: Tol-Kachorn and its Council of Elders; the Uprising of 33 BBY and the Republic's
    # demilitarisation of the system; DaaCorp and Zerpen kept from the mod's earlier map)
    ("yin_tolkachorn", ["hod_yin_tolkachorn"], "GFX_idea_generic_political_support", {"stability_factor": -0.03, "local_manpower": 0.05},
     "Tol-Kachorn", "Strongest of the Yinchorri city-states, fed by a hundred villages and served by five lesser cities. "
     "Its Council of Elders sent their warriors against the Jedi Temple itself in the Uprising, and lost; the horned "
     "towers still fly the war banners the Republic has not dared to take down.", None),
    ("yin_garrison", ["hod_yin_garrison", "hod_yin_depot"], "GFX_idea_generic_army_support", {"resistance_target": -0.05},
     "Republic Occupation", "Since the Uprising the Republic keeps garrisons north and south of Tol-Kachorn, and at the "
     "southern depot the Yinchorri arsenal - rifles, cannon, the hulls of their warships - is broken up for scrap, "
     "piece by piece, under guard.", None),
    ("yin_mines", ["hod_yin_daacorp", "hod_yin_zerpen"], "GFX_idea_generic_production_bonus", {"local_resources_factor": 0.1},
     "Offworld Concessions", "Scouts once judged Yinchorr too poor to settle. DaaCorp's great pit and the Zerpen mines "
     "came anyway, with the Republic's peace, and Yinchorri labour digs what the corporations ship off-world.", None),
    # --- Chandrila (Legends: Hanna City, Emita and Nayli's spaceports, the Brionelle Memorial Military Academy, the
    # Crystal Canyons)
    ("cha_hanna", ["hod_cha_hanna"], "GFX_idea_generic_political_support", {"stability_factor": 0.05},
     "Hanna City", "The capital between the Silver Sea and Lake Sah'ot, its white terraces looking down on the water. "
     "Chandrila sends its senators to Coruscant from here, and a quieter, older democracy meets under the rotunda's "
     "dome.", None),
    ("cha_ports", ["hod_cha_emita", "hod_cha_nayli"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Spaceports of Chandrila", "Two of the planet's three full spaceports. Emita alone was allowed industry, and its "
     "halls and freight yards work behind the docking bays while the rest of Chandrila keeps its plains green.", None),
    ("cha_brionelle", ["hod_cha_brionelle"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Brionelle Memorial Military Academy", "The academy of the Chandrilan Defense Fleet, which trains nearly every one "
     "of its officers. Cadets swear their oath beneath the Brionelle memorial at the head of the parade ground.", None),
    ("cha_canyons", ["hod_cha_canyons"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Crystal Canyons", "A gallery of rock and crystal around a tight trench above an abyss. Guides lead visitors across "
     "the arch; the rest of the canyon system is mapped by no one.", None),
    # --- Corulag (Legends: Curamelle, Sienar's Advanced Research Division, Tasjon's swoop race; canon: Corulag Academy)
    ("cor_curamelle", ["hod_cor_curamelle", "hod_cor_crullov"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Curamelle", "Corulag's capital of glass towers, the Royal Galaxy Hotel on top of the tallest. The planet's money, "
     "its universities and its schools of commerce turn out the Core's managers, and many of its officers.", None),
    ("cor_sienar", ["hod_cor_sienar"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Sienar Advanced Research Division", "North of Curamelle, Sienar designs, builds and tests its prototypes behind "
     "the fence: the runway and the wind tunnel are never quiet.", None),
    ("cor_academy", ["hod_cor_academy", "hod_cor_tasjon"], "GFX_idea_generic_army_support", {"local_manpower": 0.05},
     "Corulag Academy", "The academy whose cadets fill the officer corps of half the Core. On race days its cadets "
     "slip off to Tasjon to watch the swoops tear round the course.", None),
    # --- Arkania (Legends: Adascopolis and the House of Adasca, the diamond mines, Novania, Arca Jeth's praxeum,
    # Veeshas Tuwan)
    ("ark_adascopolis", ["hod_ark_adascopolis", "hod_ark_novania"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Adascopolis", "The ancient capital on its crag, seat of the House of Adasca. The Arkanians' meritocracy of "
     "brilliance governs from here, and Novania's port ships what their science and their mines produce.", None),
    ("ark_mines", ["hod_ark_mines"], "GFX_idea_generic_exploit_mines", {"local_resources_factor": 0.15},
     "Diamond Mines of Arkania", "Under the ice lie diamond stores beyond counting, opened to the Republic's mining "
     "concerns. The shafts go down further every year.", None),
    ("ark_praxeum", ["hod_ark_praxeum", "hod_ark_veeshas"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Old Arkania", "Snow fills the hall where Master Arca Jeth taught his students, and somewhere under the frozen wastes "
     "the Sith library of Veeshas Tuwan waits for whoever digs deep enough.", None),
    # --- Anaxes (Legends: Pols Anaxes, the Anaxes Citadel, the Republic Navy War College; canon: the shipyards, Fort
    # Anaxes)
    ("anx_citadel", ["hod_anx_citadel"], "GFX_idea_generic_army_support", {"local_manpower": 0.05, "stability_factor": 0.03},
     "Anaxes Citadel", "Training schools, research labs and intelligence centres stacked on the terraces of the Sirpar "
     "Hills: the Republic's military mind lives here.", None),
    ("anx_yards", ["hod_anx_yards", "hod_anx_works"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.15},
     "Anaxes Shipyards", "Slips in orbit and fabrication halls below, building the Republic's warships. If Anaxes fell, the "
     "Core would lose its forge.", None),
    ("anx_college", ["hod_anx_college", "hod_anx_fort", "hod_anx_hydro"], "GFX_idea_generic_army_support", {"local_supplies": 0.1},
     "Republic Navy War College", "Where the Navy's officers learn their trade, guarded by Fort Anaxes in its cave in the "
     "canyon country and supplied by Czerka's waterworks.", None),
    # --- Esseles (Legends: Calamar, the Esprix Estate, Nurrale and the Togatto Speedway, the Esseles starport)
    ("ess_calamar", ["hod_ess_calamar", "hod_ess_starport"], "GFX_idea_generic_political_support", {"stability_factor": 0.05},
     "Calamar", "The domed capital of Esseles, heart of the Darpa sector, its canals and towers busy with the trade of the "
     "starport beside it.", None),
    ("ess_esprix", ["hod_ess_esprix"], "GFX_idea_generic_political_support", {"political_power_factor": 0.05},
     "Esprix Estate", "The residence of the senator of Esseles, built in the Naboo manner: gold-ribbed domes, arcades and "
     "long gardens down to the sea.", None),
    ("ess_togatto", ["hod_ess_togatto", "hod_ess_nurrale"], "GFX_idea_generic_production_bonus", {"stability_factor": 0.03},
     "Togatto Speedway", "The Ferlanis' podracing arena in tropical Nurrale, the most spectacular in the Darpa sector. Half "
     "the sector's fortunes change hands on race day.", None),
    # --- Carida (Legends: the Academy of Carida on the Spinara Plateau, the Caridan district, Tarkin's Teeth, the
    # Forgofshar Desert, the Carida Corsairs' base; canon: the station Valor)
    ("car_academy", ["hod_car_academy", "hod_car_field", "hod_car_valor"], "GFX_idea_generic_army_support",
     {"local_manpower": 0.05, "stability_factor": 0.03},
     "Academy of Carida", "The oldest military academy of the Core, walled on the Spinara Plateau. Under Carida's heavy "
     "gravity cadets of a hundred worlds learn to march, fly and command; the station Valor watches over its landing field "
     "from orbit.", None),
    ("car_district", ["hod_car_district"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Caridan District", "The quarter just outside the Academy's gates, famous for its nightlife. Every cantina here has "
     "seen a cadet spend a month's pay in one night before the Dean's curfew.", None),
    ("car_teeth", ["hod_car_teeth", "hod_car_survival"], "GFX_idea_generic_army_support", {"local_supplies": 0.1},
     "Tarkin's Teeth", "Desolate mountains three hundred kilometres from the Academy, a training ground for centuries. "
     "Squads cross the Teeth on foot, then the Forgofshar Desert with what they carry: few forget either.", None),
    ("car_corsairs", ["hod_car_corsairs"], "GFX_idea_generic_logistics", {"local_supplies": 0.05},
     "Carida Corsairs' Base", "The frozen lair of the pirates who once raided the Perlemian Trade Route, found out by "
     "the Republic long ago. Its hangars stand empty, but the cadets swear the old tunnels go deeper than the maps.", None),
    # --- Balmorra (Legends/SWTOR: Bin Prime, Sobrik, the Balmorran Arms Factory, Bugtown; canon: the outpost, the
    # Swellbottom market, the droid factories)
    ("bal_binprime", ["hod_bal_binprime", "hod_bal_port", "hod_bal_market"], "GFX_idea_generic_political_support",
     {"stability_factor": 0.03, "political_power_factor": 0.05},
     "Bin Prime", "The capital of Balmorra since the government left Sobrik, now run from the council dome in the "
     "Techno Union's interest. Freighters from Alderaan land at its spaceport; whatever they bring is sold in the "
     "Swellbottom market by nightfall.", None),
    ("bal_arms", ["hod_bal_arms"], "GFX_idea_generic_production_bonus", {"local_factories": 0.1},
     "Balmorran Arms Factory", "The great works of the Sundari Flatlands, fought over in every war the planet has seen. "
     "Its foundry pours droid chassis day and night under the Techno Union's contracts.", None),
    ("bal_sobrik", ["hod_bal_sobrik", "hod_bal_outpost"], "GFX_idea_generic_army_support", {"local_supplies": 0.1},
     "Sobrik", "The old capital among the first assembly lines and refineries, its bunkers older than the Republic's "
     "memory. Beyond the Gorinth Canyon an outpost holds the gorges for the Techno Union.", None),
    ("bal_bugtown", ["hod_bal_bugtown"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "Bugtown", "Lab 352, the Farnel Research Facility on Lake Farnell, where genetic research went wrong long ago. "
     "The Broken Valley still swarms with what escaped, and nobody calls it anything but Bugtown.", None),
    # --- Alderaan (canon: Aldera, the Royal Palace, the University, Crevasse City, Sanctuary Coast, the falls;
    # Legends: the Petrified Mounds of the Killiks)
    ("ald_palace", ["hod_ald_palace", "hod_ald_aldera"], "GFX_idea_generic_political_support",
     {"stability_factor": 0.05, "political_power_factor": 0.1},
     "Royal Palace of Alderaan", "The Mountain Palace of the royal house, above its lake among the snow-capped peaks, "
     "with the white towers of Aldera below. From its south terrace the River Wuitho winds away towards the hills.", None),
    ("ald_university", ["hod_ald_university"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "University of Alderaan", "The most renowned university of the Core. Its scholars have argued for centuries over "
     "the stone mounds the Killiks left behind, and over everything else.", None),
    ("ald_crevasse", ["hod_ald_crevasse"], "GFX_idea_generic_production_bonus", {"local_factories": 0.1},
     "Crevasse City", "The first and largest of the canyon cities, built into the walls of a great gorge. From above "
     "there is almost nothing to see; inside, even the heavy industry is hidden in the rock.", None),
    ("ald_sanctuary", ["hod_ald_sanctuary"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Sanctuary Coast", "A sprawling city on enormous stilts at the edge of the inland sea, whose leaders have always "
     "taken in refugees from wars and oppression elsewhere.", None),
    ("ald_falls", ["hod_ald_killik"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Wonders of Alderaan", "The Cloudshape and Istabith Falls, the Glarus Lagoons and the Petrified Mounds of the "
     "Killiks: Alderaan guards its natural wonders the way other worlds guard their fortresses.", None),
    # --- Tython (canon: the Jedi Temple, the Force-henge; Legends: the Je'daii temples round the Tho Yor, the Masters'
    # Retreat, Belia Darzu's fortress, Ban Landing) - abandoned before the Clone Wars
    ("tyt_temple", ["hod_tyt_temple", "hod_tyt_henge"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "Jedi Temple Ruins", "The temple the Jedi kept on Tython after the Great Galactic War, empty for centuries since the "
     "hyperlanes failed. Up on its mountain the Force-henge still holds its seeing stone, and the Order has not forgotten "
     "either.", None),
    ("tyt_retreat", ["hod_tyt_retreat", "hod_tyt_thoyor"], "GFX_idea_generic_research_bonus", {"stability_factor": 0.02},
     "Je'daii Ruins", "The broken temple-cities of the Je'daii round the silent Tho Yor, and the Masters' Retreat on its "
     "lake in the Gnarls: the cradle of the Jedi, given back to the forests and the Force storms.", None),
    ("tyt_banlanding", ["hod_tyt_banlanding"], "GFX_idea_generic_logistics", {"local_supplies": 0.05},
     "Ban Landing", "The empty city at the mouth of the Moon Channel, where Je'daii once crossed to the Moon Islands. Its "
     "quays still stand; the only crossing between Thyr and Kato Zakar runs through its ruins.", None),
    # --- Fresia (Legends: Incom on the Coromon Islands, the Afterburner Arches; canon: the Incom warehouse)
    ("fre_incom", ["hod_fre_incom", "hod_fre_range", "hod_fre_warehouse"], "GFX_idea_generic_production_bonus",
     {"local_factories": 0.1}, "Incom Corporation",
     "Incom's plants and offices fill the Coromon Islands. Its Z-95 Headhunter, built with Subpro, flies over the storm "
     "isles every day, and every navy in the Core wants it.", None),
    ("fre_arches", ["hod_fre_arches"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Afterburner Arches", "Three great natural stone arches off the coast of Prime Coromon. Incom's test pilots fly "
     "through them on their first day, or so the cantinas say.", None),
    # --- Foerost (Legends: the vast and ancient Foerost Shipyards, the Techno Union's in the Clone Wars; Hajibar)
    ("foe_yards", ["hod_foe_yards", "hod_foe_oldyards", "hod_foe_launch", "hod_foe_hullworks"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.15}, "Foerost Shipyards",
     "Some of the oldest shipyards in the galaxy, high in orbit, now worked for the Techno Union. Beside them the Old "
     "Yards' broken ring still holds a hull no one has finished in a thousand years.", None),
    ("foe_hajibar", ["hod_foe_hajibar", "hod_foe_tower"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Hajibar", "Foerost's capital, its old works blocks under the Techno Union's spires. Every order for the yards passes "
     "through its guild hall, and its communications tower talks to the slips day and night.", None),
    ("foe_works", ["hod_foe_refinery", "hod_foe_foundry"], "GFX_idea_generic_production_bonus", {"local_factories": 0.1},
     "Foerost Works", "The refineries and foundries that feed the yards with fuel, alloys and hull plate.", None),
    # --- Corellia (canon/Legends: Coronet City, the Bottoms, Treasure Ship Row, CorSec, Kor Vella, the shipyards)
    ("crl_yards", ["hod_crl_yards", "hod_crl_bottoms"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.15}, "Corellian Shipyards",
     "The Santhe yards over Coronet, where Corellian hulls are laid down, fed by the factories of the Bottoms below, "
     "built on swamp the shipbuilders drained.", None),
    ("crl_coronet", ["hod_crl_coronet", "hod_crl_shiprow", "hod_crl_corsec"], "GFX_idea_generic_political_support",
     {"stability_factor": 0.03, "political_power_factor": 0.05}, "Coronet City",
     "The Golden City: bronze towers, Treasure Ship Row's dealers selling anything that flies, and CorSec keeping some "
     "order among the smugglers.", None),
    ("crl_korvella", ["hod_crl_korvella", "hod_crl_den"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Kor Vella", "The city on its mesa, famous for its tailors' field jackets. In the hills east, the Selonians keep to "
     "their dens, Hunchuzuc among them.", None),
    # --- Kuat (Legends: Kuat City, the Gardens of Tralala, Kuat Drive Yards)
    ("kua_yards", ["hod_kua_yards", "hod_kua_works"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.15}, "Kuat Drive Yards",
     "The most famous shipyards in the galaxy, an arc of the ring that girdles Kuat. The noble houses below keep their "
     "world a garden by building everything above it.", None),
    ("kua_city", ["hod_kua_city", "hod_kua_estate"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Kuat City", "The capital of Kuat, its elegant towers and spires shaped like the yards' dock arms. Tekshar Falls "
     "drops five hundred metres through its entertainment centre, a river turned aside at great expense.", None),
    ("kua_gardens", ["hod_kua_gardens"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Gardens of Tralala", "Terraced gardens and glass conservatories kept by the noble houses, fertilised the old way "
     "with drebin compost.", None),
    # --- Rendili (Legends: Rendili StarDrive, the Dreadnaughts, the Home Defense Fleet)
    ("ren_yards", ["hod_ren_yards", "hod_ren_works"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.15}, "Rendili StarDrive Yards",
     "Where the Dreadnaught heavy cruisers are built, their engines test-fired at the Drive Works below before the hulls "
     "go up to the slips.", None),
    ("ren_hq", ["hod_ren_hq", "hod_ren_city"], "GFX_idea_generic_political_support", {"political_power_factor": 0.05},
     "Rendili StarDrive", "The shipbuilder's headquarters over Rendili City. Its directors sell to the Republic, and "
     "listen to anyone else who pays.", None),
    ("ren_base", ["hod_ren_base"], "GFX_idea_generic_army_support", {"local_supplies": 0.1},
     "Home Defense Fleet Base", "The ground base of the Rendili Home Defense Fleet, whose loyalty both the Republic and "
     "the Separatists are already counting on.", None),
    # --- Commenor (Legends: Chasin City, Anteluma, Munto, the University of Commenor)
    ("com_chasin", ["hod_com_chasin", "hod_com_port"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Chasin City", "One of Commenor's greatest cities, famous across the Core for its restaurants. Traders off the Commenor "
     "Run eat here before they sign anything.", None),
    ("com_university", ["hod_com_university"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "University of Commenor", "Where, in the last days before the war, Senator Amidala told a great peace rally that the "
     "Republic must not answer the Separatists with an army.", None),
    ("com_arena", ["hod_com_arena", "hod_com_munto"], "GFX_idea_generic_political_support", {"stability_factor": 0.02},
     "Anteluma", "The sporting centre of Commenor and home of its major leagues. Half of Munto, terraced up its valley, "
     "comes down to watch on match day.", None),
    # --- Duro (Legends: the space cities, Ranadaast, Tayana, the Valley of Royalty, the Tiercam Dam, New Tayana)
    ("dur_spacecity", ["hod_dur_spacecity", "hod_dur_lift"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.1}, "Duros Space Cities",
     "Twenty cities in orbit, Bburru Station the greatest, where the Duros live above the world their factories poisoned. "
     "The lift fields feed them from the ground.", None),
    ("dur_ranadaast", ["hod_dur_ranadaast", "hod_dur_factory"], "GFX_idea_generic_political_support", {"stability_factor": -0.02},
     "Ranadaast", "The old royal capital, the City of Ashes: half its towers dark, its streets run by whoever pays. The "
     "factory belt still works beyond it, as it has for centuries.", None),
    ("dur_royalty", ["hod_dur_tombs", "hod_dur_tayana", "hod_dur_newtayana"], "GFX_idea_generic_political_support",
     {"stability_factor": 0.02}, "Valley of Royalty",
     "The tombs of Duro's monarchs, the ruins of Tayana in their crater, the old Tiercam Dam and the floating city of New "
     "Tayana: what the Duros left on the ground and still remember.", None),
    # --- Loronar (Legends: the Loronar shipyards, the Jade Moon, the Loronar Corporation)
    ("lor_corp", ["hod_lor_hq", "hod_lor_city", "hod_lor_labs"], "GFX_idea_generic_production_bonus", {"local_factories": 0.1},
     "Loronar Corporation", "The corporation of strike cruisers, needle fighters and synthdroids, run from its crystal tower "
     "over Loronar City.", None),
    ("lor_works", ["hod_lor_port", "hod_lor_crystal"], "GFX_idea_generic_production_bonus",
     {"local_factories": 0.1}, "Crystal Works",
     "Where Loronar grows the synthetic crystals its corporation builds into everything it sells, shipped out through "
     "the spaceport.", None),
    # --- Neimoidia (canon: Koto-Si, the communal hives, the fungus farms; Legends: Kaantay)
    ("nei_kotosi", ["hod_nei_kotosi", "hod_nei_docks", "hod_nei_kaantay"], "GFX_idea_generic_production_bonus",
     {"local_factories": 0.1, "stability_factor": 0.02}, "Koto-Si",
     "The capital of Neimoidia and the heart of the Trade Federation. Freighters land in its great bays every hour; the "
     "Viceroy's dome looks out over all of it.", None),
    ("nei_hives", ["hod_nei_hives", "hod_nei_farms"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Communal Hives", "The hives where every Neimoidian grub is raised, and the fungus farms below them where harvester "
     "beetles tend the crop. A Neimoidian learns greed here before anything else.", None),
    # --- Mimban (canon: the Nanth flatlands' tribes; Legends: the Temple of Pomojema, the Thrella wells, Dreypa's Oubliette)
    ("mim_temple", ["hod_mim_temple", "hod_mim_wells"], "GFX_idea_generic_research_bonus", {"local_building_slots": 1},
     "Temple of Pomojema", "A ziggurat of volcanic rock raised to the god Pomojema, the Kaiburr crystal in its great statue. "
     "Beyond it the Thrella wells drop into the dark.", None),
    ("mim_village", ["hod_mim_village", "hod_mim_mine", "hod_mim_oubliette"], "GFX_idea_generic_political_support",
     {"stability_factor": 0.02}, "Nanth Flatlands",
     "The stilt villages of the Mimbanese in the mist, the prospectors' camp in the mud fields, and somewhere in the deep "
     "forest Dreypa's Oubliette, which nobody local will go near.", None),
    # --- Manaan (canon/Legends: Ahto City, the Hrakert Rift and Station, the swoop track, the Prince of Waves)
    ("mnn_ahto", ["hod_mnn_ahto", "hod_mnn_swoop"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Ahto City", "The Selkath capital floating alone on Manaan's endless sea, white platforms and domes linked by bridges. Its "
     "swoop track draws racers from across the Slice, and its kolto is sold to anyone.", None),
    # --- Coruscant (canon/Legends: the Senate, the Jedi Temple, the Executive Building, the Courts, the Processional
    # Way, Monument Plaza, 500 Republica, the Galaxies Opera House, the landing rings, the Works, Level 1313)
    ("cos_senate", ["hod_cos_senate", "hod_cos_processional", "hod_cos_courts"], "GFX_idea_generic_political_support",
     {"stability_factor": 0.05, "political_power_factor": 0.1},
     "Galactic Senate", "A thousand generations of the Republic have been argued out under this dome. Down the Processional "
     "Way the delegations still come, past the founders' statues, to the Grand Convocation Chamber; the Galactic Courts "
     "sit in judgement beside it.", None),
    ("cos_temple", ["hod_cos_temple"], "GFX_idea_generic_army_support", {"local_manpower": 0.05, "stability_factor": 0.03},
     "Jedi Temple", "The Order's home for millennia: the High Council in its spire, the Archives holding all the "
     "Republic's knowledge, the Room of a Thousand Fountains where Masters still find quiet above the city.", None),
    ("cos_executive", ["hod_cos_executive", "hod_cos_republica", "hod_cos_monument"], "GFX_idea_generic_political_support",
     {"political_power_factor": 0.05}, "Federal District", "The Chancellor's office in the Executive Building, the senators' "
     "apartments in 500 Republica, Umate's bare summit at Monument Plaza: the government lives within sight of itself.", None),
    ("cos_ports", ["hod_cos_exchange", "hod_cos_diner"], "GFX_idea_generic_production_bonus", {"state_production_speed_buildings_factor": 0.1},
     "Commerce District", "The exchange trades in the goods of a thousand worlds under the towers of the north-east. "
     " In CoCo Town Dex's Diner feeds the dockhands, and hears everything.", None),
    ("cos_compor", ["hod_cos_compor"], "GFX_idea_generic_secret_police", {"resistance_target": -0.05, "stability_factor": 0.02},
     "COMPOR Arcology", "A mass of dark stone beside the Senate, raised for the Commission for the Protection of the Republic and "
     "its watchful bureaus. Its analysts read the HoloNet of a thousand worlds; what they do with it is not discussed.", None),
    ("cos_entertainment", ["hod_cos_opera", "hod_cos_outlander"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Entertainment District", "Senators at the Galaxies Opera House, smugglers and bounty hunters at the Outlander Club: "
     "all of Coruscant comes here after dark.", None),
    ("cos_underworld", ["hod_cos_works", "hod_cos_level1313"], "GFX_idea_generic_secret_police", {"resistance_target": 0.05},
     "Coruscant Underworld", "The Works rusts in silence, and below the shining levels Level 1313 swallows whoever the "
     "upper city would rather forget.", None),
    # --- Boz Pity (canon: a Foundry of the Confederacy; Legends: the graveyard planet, the Gargantelle ruins, the
    # Confederacy base)
    ("boz_base", ["hod_boz_base"], "GFX_idea_generic_army_support", {"local_manpower": 0.05, "local_supplies": 0.1},
     "Boz Pity Confederacy Base", "The Techno Union raised this fortress in a canyon of the graveyard planet as soon "
     "as Boz Pity joined Count Dooku's cause. Droid garrisons drill on its parade ground, and a grounded core ship "
     "waits on its landing ring for the day the Confederacy needs a staging point on the Republic's border.", None),
    ("boz_foundry", ["hod_boz_foundry"], "GFX_idea_generic_production_bonus",
     {"state_production_speed_buildings_factor": 0.1}, "Foundry of the Confederacy", "Droid halls and smelters "
     "the Techno Union built on a world nobody else wanted. With Metalorn, Saleucami and Felucia, Boz Pity is "
     "to be one of the forges of the Separatist armies, if the crisis turns to war.", None),
    ("boz_ruins", ["hod_boz_ruins"], "GFX_idea_generic_political_support", {"stability_factor": 0.03},
     "Gargantelle Ruins", "A temple-mountain of the extinct Gargantelles, ringed by a still moat, its lotus towers "
     "crowned with three-faced heads. Legend says the caliphs of Mourn returned to their world when the last "
     "Gargantelle died; the temple has stood empty ever since.", None),
    ("boz_skeletons", ["hod_boz_skeletons"], "GFX_idea_generic_secret_police", {"resistance_target": 0.03},
     "Skeleton Fields", "In this sand valley the bones of the Gargantelles lie where they fell, ribs taller than a "
     "walker and three-faced skulls half sunk in the drifts. Pilgrims from nearby systems still leave stelae "
     "round the valley's edge.", None),
    ("boz_headstones", ["hod_boz_headstones"], "GFX_idea_generic_political_support", {"compliance_gain": 0.03},
     "Headstone Fields", "The great funerary obelisk of the Gargantelles rises over rows of carved stelae, and "
     "round it the graves of every species that has brought its dead to the graveyard planet for a thousand "
     "years.", None),
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
                                      ("florrum_", "Florrum"), ("zyg_", "Zygerria"), ("bonadan_", "Bonadan"), ("pammant_", "Pammant"), ("mcl_", "Mon Calamari"), ("ieg_", "Iego"), ("lia_", "Lianna"), ("jab_", "Jabiim"), ("sal_", "Saleucami"), ("tel_", "Telos"), ("ser_", "Serenno"), ("yav_", "Yavin IV"), ("cel_", "Celanon"), ("bot_", "Botajef"), ("axx_", "Axxila"), ("cit_", "Ciutric"), ("ces_", "Ord Cestus"), ("dat_", "Dathomir"), ("man_", "Mandalore"), ("tar_", "Taris"), ("way_", "Wayland"), ("con_", "Concordia"), ("bra_", "Bracca"), ("tra_", "Trandosha"), ("nyr_", "Nyriaan"), ("crs_", "Corsin"), ("kas_", "Kashyyyk"), ("ond_", "Onderon"), ("umb_", "Umbara"), ("col_", "Colla IV"), ("rus_", "Ruusan"), ("boz_", "Boz Pity"), ("aga_", "Agamar"), ("ot_", "Ord Trasi"), ("dan_", "Dantooine"), ("dub_", "Dubrillion"), ("bas_", "Bastion"), ("kal_", "Kalee"), ("muun_", "Muunilinst"), ("myg_", "Mygeeto"), ("yag_", "Yaga Minor"), ("ans_", "Ansion"), ("ilu_", "Ilum"), ("dor_", "Dorin"), ("yin_", "Yinchorr"), ("cha_", "Chandrila"), ("cor_", "Corulag"), ("ark_", "Arkania"), ("anx_", "Anaxes"), ("ess_", "Esseles"), ("mnn_", "Manaan"), ("mim_", "Mimban"), ("nei_", "Neimodia"), ("lor_", "Loronar"), ("dur_", "Duro"), ("com_", "Commenor"), ("ren_", "Rendilli"), ("kua_", "Kuat"), ("crl_", "Corellia"), ("foe_", "Foerost"), ("fre_", "Fresia"), ("tyt_", "Tython"), ("ald_", "Alderaan"), ("bal_", "Balmorra"), ("car_", "Carida"), ("cos_", "Coruscant"), ("gar_", "Garqi"), ("om_", "Ord Mantell"), ("ith_", "Ithor"))
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
