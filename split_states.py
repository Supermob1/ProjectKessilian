#!/usr/bin/env python3
"""
split_states.py — Automated planet state splitter for Hearts of Durasteel

Default mode: splits every planet listed in PLANET_TARGETS (lore-accurate names).
Optionally targets a single state or any state above a province threshold.

Usage:
    python split_states.py --list            list all states; marks which are in PLANET_TARGETS
    python split_states.py                   split every state in PLANET_TARGETS (dry-run first!)
    python split_states.py --dry-run         preview all PLANET_TARGETS splits
    python split_states.py --state 44        split state 44 using its PLANET_TARGETS entry (or generic)
    python split_states.py --state 44 --dry-run
    python split_states.py --all --min-prov 60   split all states >= 60 provinces (generic names)
    python split_states.py --all --min-prov 60 --dry-run
    python split_states.py --all --min-prov 60 --skip 117,288,289,290,291

Options:
    --target-size N   Target province count per child state when no lore count given (default 45)
    --min-group N     Merge terrain groups smaller than N into dominant (default 5)
"""

# ── LORE-ACCURATE SPLIT NAMES ────────────────────────────────────────────────
# Maps state_id → list of sub-state display names.
# The number of names controls exactly how many sub-states are created.
# Order: first name = group with the lowest province-ID cluster (roughly "centre/capital");
# adjust after running if geography doesn't match the lore intent.
# ─────────────────────────────────────────────────────────────────────────────
PLANET_TARGETS = {
    # ── Core / Deep Core ──────────────────────────────────────────────────────
    9:   ["Incom Corporation Yards", "Subpro Hangars", "Fresia City", "Northern Plains", "Southern Reaches",
          "Eastern Forests", "Western Coast"],  # Fresia
    10:  ["Foerost Shipyard District", "Foerost Orbital Ring", "Northern Territories", "Eastern Reaches",
          "Southern Industrial Belt", "Western Settlement Zone", "Outer Construction Yards"],  # Foerost
    14:  ["Fondor City", "Fondor Orbital Ring", "Industrial Complex Alpha", "Industrial Complex Beta",
          "Southern Shipyards", "Northern Manufacturing", "Eastern Drydocks", "Western Outpost"],  # Fondor
    17:  ["Munto Codru", "Commenor Northern Districts", "Commenor Southern Settlement", "Eastern Trade Hub",
          "Western Agricultural Belt", "Outer Agri-Zones", "Coastal Reach", "Highland Territories"],  # Commenor
    20:  ["Duro Orbital City Alpha", "Duro Orbital City Beta", "Duro Orbital City Gamma",
          "Northern Surface Wasteland", "Southern Toxic Flats", "Eastern Industrial Ruins",
          "Western Habitation Domes"],  # Duro
    21:  ["Loronar City", "Loronar Corporation HQ", "Northern Manufacturing Belt", "Eastern Steppes",
          "Western Territories", "Southern Settlement", "Outer Agricultural Zone"],  # Loronar
    22:  ["Coronet City", "Tyrena", "Doaba Guerfel", "Bela Vistal", "CorSec Territories",
          "Outer Corellian Zones", "Selonian Caverns", "Drall Highlands"],  # Corellia
    23:  ["Rendili City", "StarDrive Orbital Yards", "Northern Settlement Zone", "Eastern Plateau",
          "Southern Reach", "Western Highlands", "Coastal Districts"],  # Rendili
    64:  ["Temple of the Ancients", "Rakata Southern Jungles", "Elder Territories", "Eastern Coast",
          "Northern Wilderness", "Western Beaches", "Inland Plateau", "Ancient Sea"],  # Rakata Prime
    65:  ["Celegia City", "Northern Reaches", "Southern Plains", "Eastern Territories",
          "Western Frontier", "Coastal Region", "Highland Settlement"],  # Celegia
    66:  ["Refugee Sector", "Promenade District", "Hutt Clan Territory", "Black Sun Quarter",
          "Lower Underworld", "Smuggler's Run District", "Corellian Sector", "Duros Levels",
          "Lower Industrial Zone"],  # Nar Shaddaa
    89:  ["Kaas City", "Citadel District", "Dark Temple", "Malignant Jungle", "Power Generator Fields",
          "Sith Sanctuary", "Northern Jungle Reaches", "Southern Lightning Plains"],  # Dromund Kaas
    90:  ["Valley of the Dark Lords", "Dreshdae Spaceport", "Shyrack Caverns", "Sith Academy",
          "Blood Cliffs", "Wild Region", "Northern Wastes", "Tomb of Ajunta Pall"],  # Korriban
    91:  ["Telos IV Citadel Station", "Polar Restoration Zone", "Southern Wilderness", "Eastern Plateaus",
          "Northern Plateau", "Czerka Mining Site", "Restored Agricultural Belt"],  # Telos
    99:  ["Taris Restoration Zone", "Upper City Ruins", "Undercity", "Rakghoul Territories",
          "Northern Settlement", "Southern Reconstruction", "Industrial Wastes", "Cathar District"],  # Taris
    109: ["Mygeeto City", "IBC Treasury District", "Crystal Wastes", "Northern Reaches",
          "Southern Mountain Territory", "Eastern Glacier", "Western Refinery", "Frozen Outlands"],  # Mygeeto
    115: ["Harnaidan", "IBC Banking Complex", "Northern Lush Fields", "Southern Plains",
          "Eastern Territories", "Western Reach", "Moneylending Vaults", "Outer Garden Zones"],  # Muunilist

    # ── Inner Rim ────────────────────────────────────────────────────────────
    13:  ["Abregado Spaceport", "Northern Plains", "Southern Wetlands", "Eastern Mountain Ranges",
          "Outer Territories", "Western Lowlands", "Trade District", "Mining Highlands"],  # Abregado-Rae
    18:  ["Ahto City", "Northern Ocean", "Southern Kolto Fields", "Eastern Shallows",
          "Selkath Deep Territories", "Hrakert Rift", "Western Coral Reefs", "Sub-Oceanic Settlement"],  # Manaan
    24:  ["Zarra", "Northern Bridge Cities", "Southern Reaches", "Mountain Refuge",
          "Cato Neimoidia Station", "Lower Bridge Markets", "Crater Cities", "Eastern Forge"],  # Cato Neimoidia
    25:  ["Traders' Plaza", "Northern Settlement Zone", "Eastern Territories", "Southern Plains",
          "Western Marshlands", "Free Trade District", "Coastal Outpost", "Smuggler's Haven"],  # Atzerri
    26:  ["Bestine City", "Northern Archipelago", "Ocean Territories", "Southern Settlement Zone",
          "Eastern Atolls", "Western Reefs", "Trade Coastline", "Deep Sea Reach"],  # Bestine IV
    27:  ["Allanteen Shipyards", "Northern Industrial Zone", "Eastern Settlement District",
          "Southern Reaches", "Open Ocean", "Western Coast", "Orbital Drydocks", "Mining Coast"],  # Allanteen VI
    59:  ["Eriadu City", "Phelar Port", "Northern Industrial Zone", "Eastern Mountain Reaches",
          "Southern Outlands", "Tarkin Family Estate", "Polluted Plains", "Western Trade Spine"],  # Eriadu
    86:  ["Bonadan City", "Corporate Sector Authority Zone", "Northern Industrial Complex",
          "Eastern Mining Fields", "Southern Refinery", "Western Spaceport", "Polluted Reach"],  # Bonadan
    87:  ["Etti City", "Corporate Sector Headquarters", "Northern Settlement Zone",
          "Southern Commerce District", "Eastern Resort Coast", "Western Estates", "Trade Plaza"],  # Etti IV
    88:  ["Ruuria City", "Northern Territories", "Southern Reaches", "Eastern Plains",
          "Western Hills", "Coastal Settlement", "Highland Forest"],  # Ruuria
    100: ["Corsin City", "Northern Territories", "Southern Reaches", "Eastern Plains",
          "Western Coastline", "Outer Settlement", "Highland Region"],  # Corsin
    186: ["NiJedha City", "Holy Lands", "Jedha Desert Wastes", "Northern Mountains",
          "Eastern Territory", "Kyber Mining Sites", "Pilgrim Roads", "Catacombs of Cantham"],  # Jedha
    187: ["Hanna City", "Crystal Fields", "Rural Provinces", "Northern Highlands",
          "Bana Sea Coast", "Silver Sea", "Eastern Vineyards", "Western Plains"],  # Chandrila
    188: ["Ciutric City", "Northern Settlement", "Southern Territories", "Eastern Reaches",
          "Western Industrial Zone", "Coastal Districts", "Highland Outposts"],  # Ciutric
    190: ["Celanon City", "Northern Trade District", "Southern Settlement Zone", "Eastern Territories",
          "Western Commercial Hub", "Outer Markets", "Coastal Trade Route"],  # Celanon
    195: ["Lianna City", "Sienar Fleet Systems Complex", "Northern Territories",
          "Southern Settlement Zone", "Eastern Manufacturing Hub", "Western Reach",
          "Coastal Outpost"],  # Lianna
    205: ["Maz's Castle", "Northern Forest", "Southern Lake Country", "Eastern Ancient Ruins",
          "Takodana Coastline", "Western Highlands", "Smuggler's Bay", "Mountain Reach"],  # Takodana
    206: ["Ghorman City", "Northern Plains", "Southern Territories", "Eastern Settlement Zone",
          "Western Industrial Belt", "Coastal Reach", "Outer Plantations"],  # Ghorman

    # ── Mid Rim ──────────────────────────────────────────────────────────────
    19:  ["Neimodia City", "Northern Settlement Zone", "Southern Territories", "Eastern Mining Zone",
          "Western Trade Hub", "Coastal Districts", "Outer Industrial Belt"],  # Neimodia
    28:  ["Mimbanese Settlement", "Northern Swamp Territories", "Crystal Swamps", "Mimban Mud Fields",
          "Eastern Mining Camps", "Imperial Excavation Zone", "Southern Bog Country"],  # Mimban
    29:  ["Falleen Prime", "Xo's Island", "Mountain Hunting Grounds", "Jungle Interior",
          "Northern Coast", "Eastern Royal Palace", "Southern Marshes", "Black Sun Territory"],  # Falleen
    30:  ["Drev'starn", "Kothlis Spynet Region", "Southern Forest", "Northern Reaches",
          "Mountain Ranges", "Eastern Plateau", "Bothan Combat Caverns", "Western Coast"],  # Bothawui
    31:  ["Nar Shaddaa Gateway", "Evocar Jungles", "Hutt Ruling Districts", "Southern Wetlands",
          "Northern Toxic Swamps", "Eastern Sludge Plains", "Western Spaceport Zone",
          "Polluted Coast"],  # Nal Hutta
    32:  ["Tipoca City", "Northern Ocean", "Southern Storm Zone", "Eastern Platform Ring",
          "Clone Training Grounds", "Western Cloning Facility", "Deep Ocean Trench",
          "Aiwha Migration Route"],  # Kamino
    38:  ["Rodiapolis", "Iskaayuma", "Northern Jungle", "Southern Wetlands", "Hunters' Preserves",
          "Eastern Coast", "Western Marshlands", "Betu River Delta"],  # Rodia
    44:  ["Theed", "Lake Country", "Gungan Sacred Place", "Southern Swamps", "Northern Mountains",
          "Dee'ja Peak", "Naboo Eastern Forests", "Lianorm Swamp", "Otoh Gunga"],  # Naboo
    45:  ["Pixelito", "Dug Settlement Territories", "Gran Protectorate", "Fuel Refineries",
          "Eastern Swamps", "Northern Mountain Range", "Doaba Strana", "Outer Lowlands"],  # Malastare
    46:  ["Iskaayuma", "Ishi Tib Reef Districts", "Open Seas", "Coastal Territories",
          "Northern Shallows", "Southern Deep Waters", "Eastern Reef Colonies",
          "Western Atoll Chain"],  # Tibrin
    47:  ["Yag'Dhul Station", "Dark-Side Hemisphere", "Light-Side Hemisphere",
          "Gravitational Anomaly Zone", "Northern Outposts", "Twilight Belt", "Givin Capital",
          "Outer Construction Zone"],  # Yag'Dhul
    48:  ["Mechis III Factory Core", "Eastern Machinery Yards", "Western Component Storage",
          "Programming Sector", "Northern Foundry", "Southern Assembly Lines", "Outer Droid Plains"],  # Mechis
    50:  ["Xucphra Bacta Farms", "Zaltin Bacta Facilities", "Iskadrell Peak", "Southern Jungle",
          "Northern Processing Complex", "Vratix Hives", "Eastern Cultivation Zone",
          "Alazhi Plantations"],  # Thyferria
    52:  ["Anoat City", "Uprising Territories", "Northern Wasteland", "Southern Industrial District",
          "Eastern Refinery Zone", "Polluted Plains", "Western Settlement"],  # Anoat
    55:  ["Terminus Port", "Eastern Trade District", "Northern Highlands", "Southern Plains",
          "Western Reach", "Outer Trade Routes", "Smuggler's Bay"],  # Terminus
    58:  ["Sluis Van Shipyards", "Northern Settlement Zone", "Southern Territories",
          "Eastern Dockyards", "Western Orbital Yards", "Mining Reach", "Coastal Outpost"],  # Sluis Van
    60:  ["Sullcrom City", "Pinyumb", "Waklan Grottos", "Northern Settlements", "SoroSuub Territory",
          "Lava Tube Habitats", "Eastern Magma Plains", "Geothermal Refinery Zone"],  # Sullust
    62:  ["Bakura City", "Northern Plains", "Southern Forest", "Eastern Highlands",
          "Ssi-ruuvi Incursion Zone", "Western Coast", "Cape Suzu", "Salis D'aar Settlement"],  # Bakura
    67:  ["Toydaria City", "Northern Swamps", "Southern Wetlands", "Eastern Territories",
          "Western Marshlands", "Floating Cities", "Royal Palace Region", "Mire Basin"],  # Toydaria
    68:  ["Shola City", "Northern Plains", "Eastern Reaches", "Southern Territories",
          "Western Highlands", "Coastal Region", "Outer Settlements"],  # Shola
    71:  ["Quesh Venom Processing", "Three Families Territory", "Northern Toxic Plains",
          "Southern Steppes", "Eastern Mining Zone", "Hutt Excavation Pits", "Atmospheric Refinery"],  # Quesh
    72:  ["Nimban City", "Northern Plains", "Southern Territories", "Eastern Steppes",
          "Western Reach", "Hutt Holdings", "Outer Settlement"],  # Nimban
    74:  ["Saleucami City", "Southern Oasis Belt", "Northern Desert Wastes", "Cave Network",
          "Eastern Desert Plains", "Western Refuge Camps", "Volcanic Highlands", "Settler Villages"],  # Saleucami
    78:  ["Pammant Docks", "Northern Reaches", "Southern Coastal Waters", "Eastern Territories",
          "Western Shipyards", "Outer Construction Yards", "Orbital Construction Ring"],  # Pammant
    79:  ["Raxus City", "Separatist Senate District", "Junk Wasteland", "Northern Territories",
          "Eastern Scrap Regions", "Western Diplomatic Quarter", "Outer Plantations",
          "Confederate Military Zone"],  # Raxus
    81:  ["Ringo Vinda Station", "North Quadrant", "South Quadrant", "Eastern Terminal",
          "Western Gate", "Equatorial Ring", "Inner Habitation Belt", "Outer Defence Platforms"],  # Ringo Vinda
    83:  ["Kadavo Processing Facility", "Northern Plateau", "Slave Processing Pens",
          "Southern Wasteland", "Eastern Cliffs", "Western Quarry", "Outer Wastes"],  # Kadavo
    84:  ["Canto Bight", "Desert Interior", "Northern Reach", "Sinta Glacier Colony",
          "Outer Territories", "Eastern Casino Strip", "Fathier Racing Grounds",
          "Western Saltflats"],  # Cantonica
    93:  ["Carannia", "Dooku's Palace Grounds", "Northern Mountains", "Southern Valleys",
          "Eastern Territories", "Western Estates", "Noble Highlands", "Wild Forest"],  # Serenno
    102: ["Tafanda Bay", "Mother Jungle Reserve", "Cathor Hills", "Faa River Valley",
          "Ithorian Sky Cities", "Eastern Herd Grounds", "Northern Forest Cathedral",
          "Western Sacred Groves"],  # Ithor
    103: ["Worlport", "Scraplands", "Mannett Point", "Northern Reaches", "Eastern Territories",
          "Western Mountain Range", "Old Town", "Outer Settlement"],  # Ord Mantell
    110: ["Khoonda Plains", "Jedi Enclave Ruins", "Eastern Grasslands", "Northern Settlement",
          "Southern Wilderness", "Western Forest", "Crystal Cave Region", "Salvager Settlement"],  # Dantooine
    112: ["Bastion City", "Northern Industrial Zone", "Southern Territories",
          "Eastern Garrison District", "Imperial Naval Base", "Western Reach",
          "Outer Defence Perimeter", "Lower City"],  # Bastion
    116: ["Iziz", "Beast Riders Territory", "Northern Jungle", "Southern Highland Reaches",
          "Eastern Territories", "Western Wilderness", "Mandalore Ruins", "Royal Hunting Preserves"],  # Onderon
    119: ["Hsskhor", "Kashyyyk Hunting Grounds", "Forest Wilderness", "Southern Coasts",
          "Northern Mountains", "Eastern Hunting Range", "Wookiee Prison Camps",
          "Western Slave Pens"],  # Trandosha
    191: ["Botajef City", "Northern Plains", "Southern Territories", "Eastern Reaches",
          "Western Coast", "Outer Settlement", "Highland Region"],  # Botajef
    196: ["Raxus Prime Junkyard", "Junk Citadel", "Northern Waste Fields", "Southern Territories",
          "Eastern Scrapfields", "Imperial Salvage Zone", "Western Hulks", "Toxic Lakes"],  # Raxus Prime
    197: ["Bracca Shipbreaking Yards", "Northern Wasteland", "Southern Territories",
          "Eastern Reaches", "Western Hulks", "Capital Hulk Graveyard", "Scrappers' Slum"],  # Bracca
    201: ["Phelarion City", "Northern Territories", "Southern Reaches", "Eastern Plains",
          "Western Coast", "Outer Settlement", "Highland Region"],  # Phelarion
    203: ["Karfeddion City", "Northern Territories", "Southern Reaches", "Eastern Plains",
          "Western Coast", "Outer Settlement", "Highland Region"],  # Karfeddion
    204: ["Targon", "Northern Settlement Zone", "Southern Cerean Highlands", "Eastern Territories",
          "Cerean Tribal Lands", "Western Plains", "Coastal Reach", "Ancient Hill Country"],  # Cerea

    # ── Outer Rim ────────────────────────────────────────────────────────────
    37:  ["Lessu", "Cazne", "Kala'uun Caverns", "Bright Lands", "Cold Hemisphere",
          "Nabat", "Resdin", "Eastern Valleys", "Twi'lek Settlements"],  # Ryloth
    39:  ["Christoph City", "Southern Crystal Mines", "Northern Fortifications",
          "Eastern Crystal Ravines", "Underground Cities", "Republic Garrison",
          "Western Spires", "Cathedral Caves"],  # Christophsis
    40:  ["Farstine Station", "Northern Steppes", "Southern Reaches", "Eastern Mining Claims",
          "Western Coast", "Outer Settlement", "Highland Region"],  # Farstine
    41:  ["Vohai City", "Northern Plains", "Southern Jungles", "Eastern Territories",
          "Western Reach", "Coastal Settlement", "Outer Wilderness"],  # Vohai
    42:  ["Alzoc Frozen Plains", "Talz Settlement", "Northern Ice Fields", "Southern Mountains",
          "Eastern Glacier", "Aurorae Caves", "Western Tundra"],  # Alzoc III
    43:  ["Rothana Heavy Engineering", "Northern Industrial Zone", "Southern Steppes",
          "Western Sea", "Eastern Plains", "Kaminoan Outpost", "Construction Yards"],  # Rothana
    49:  ["Belsavis Vault", "Esh-kha Territories", "Rakata Prison Complex", "Frozen Wastes",
          "Geothermal Rift", "Tropical Jungle Pockets", "Old Vault Ruins", "Imperial Prison Sector"],  # Belsavis
    51:  ["Echo Base Ruins", "Clabburn Range", "Cirque Maj", "Great Rift", "Southern Ice Plains",
          "Wampa Caves", "Northern Glacier", "Eastern Frozen Waste"],  # Hoth
    53:  ["Mustafar Mining Facility", "Vader's Fortress", "Minsulla Lava Fields",
          "Eastern Volcanic Plains", "Fralideja", "Northern Magma Sea", "Western Pyroclastic Flats",
          "Klegger Corp Drilling Sites"],  # Mustafar
    56:  ["Pau City", "Utapau City", "Amfu Sinkhole", "Northern Sinkholes", "Eastern Steppes",
          "Western Ravines", "Lower Sinkhole System", "Surface Wastes", "Pau'an Tombs"],  # Utapau
    57:  ["Queyta City", "Northern Territories", "Southern Regions", "Eastern Plains",
          "Western Coast", "Outer Settlement"],  # Queyta
    61:  ["Bright Tree Village", "Imperial Shield Generator Ruins", "Ewok Territories",
          "Northern Forest", "Southern Coastal Shallows", "Eastern Tree-Line", "Yuzzum Lakes",
          "Western Wilderness"],  # Endor
    63:  ["Black Spire Outpost", "Surabat River Valley", "Eastern Jungle", "Outskirts Settlements",
          "Ancient Ruins", "Western Wilds", "Forgotten Spires", "Frontier Trade Posts"],  # Batuu
    69:  ["B'omarr Monastery", "Western Jungles", "Eastern Cliffside", "Castle Ruins",
          "Lower River Basin", "Northern Cliff Pass", "Hutt Stronghold", "Jungle Lowlands"],  # Teth
    70:  ["Nystao", "Noghri Village", "Mount Honoghr", "Poisoned Steppes", "Recovering Lands",
          "Imperial Toxic Site", "Eastern Wastes", "Clan Strongholds"],  # Honoghr
    73:  ["Boz Pity Healing Compound", "Northern Shores", "Southern Territories",
          "Eastern Reaches", "Western Burial Grounds", "Ancient Sanctuary", "Outer Wilderness"],  # Boz Pity
    75:  ["Shelter", "Cobalt Station", "Northern Plateaus", "Endless Mud Flats",
          "Separatist Stronghold", "Republic Beachhead", "Eastern Mining Camps",
          "Western Battle Plains"],  # Jabiim
    76:  ["Iego Ruins", "Diathim Moonways", "Desert Wastes", "Northern Reaches", "Ancient City",
          "Southern Crystal Fields", "Western Pilgrim Roads", "Crash Site Cluster"],  # Iego
    77:  ["Mon Calamari City", "Calamari Reef", "Quarren Depths", "Kee-Piru", "Open Ocean",
          "Coral Cities", "Floating Star Yards", "Whaladon Migration Route", "Deep Trench"],  # Mon Calamari
    80:  ["Rokak'k Baran Outpost", "Northern Fungal Fields", "Ancient Abyss", "Southern Jungle",
          "Har Gau Settlement", "Eastern Fungal Plains", "Niango Town", "Sarlacc Pit Region"],  # Felucia
    82:  ["Rhen Var Citadel", "Rhen Var Harbor", "Northern Ice Fields", "Southern Ruins",
          "Eastern Mountains", "Western Glacier", "Ancient Battlefield", "Frozen Catacombs"],  # Rhen Var
    85:  ["Zygerrian Capital", "Slave Auction Markets", "Eastern Savannah", "Northern Hunting Grounds",
          "Sea Coast", "Western Plains", "Royal Slave Pens", "Outer Hunting Reserves"],  # Zygerria
    92:  ["Maridun Plains", "Aleena Settlement", "Northern Steppes", "Southern Grasslands",
          "Eastern Plains", "Lurmen Village", "Western Wilderness"],  # Maridun
    94:  ["Axxila City", "Northern Territories", "Southern Reaches", "Eastern Plains",
          "Western Coast", "Outer Settlement", "Highland Region"],  # Axxila
    95:  ["Nightbrother Village", "Nightsister Fortress", "Rancor Territory", "Northern Jungle",
          "Southern Marshes", "Eastern Spider Caves", "Western Dathomir Plains",
          "Ancient Sith Tombs"],  # Dathomir
    97:  ["Mount Tantiss", "Northern Forests", "Myneyrshi Territory", "Southern Wilds",
          "Eastern Settlements", "Imperial Storehouse", "Psadan Lowlands", "Western Plateau"],  # Wayland
    98:  ["Nyriaan City", "Spice Fields", "Northern Jungles", "Southern Territories",
          "Eastern Reach", "Outer Plantation Zone", "Western Wilderness"],  # Nyriaan
    104: ["Pesktda", "Agri-Farming Plains", "Northern Forests", "Eastern Reaches",
          "Western Settlement", "Southern Croplands", "Coastal Region", "Highland Plateau"],  # Garqi
    105: ["Dorin City", "Northern Gas Fields", "Southern Settlements", "Eastern Atmospheric Zone",
          "Kel Dor Highlands", "Western Storm Belt", "Outer Atmospheric Layer",
          "Helium-Hydrogen Refinery"],  # Dorin
    106: ["Aeten Crystal Fields", "Northern Mountains", "Western Desert", "Eastern Mining Complex",
          "Southern Wasteland", "Stygium Refinery", "Outer Quarries"],  # Aeten II
    107: ["Calna Muun", "Northern Plains", "Southern Highlands", "Eastern Forests",
          "Western Reaches", "Coastal Settlement", "Rebel Outpost", "Outer Wilderness"],  # Agamar
    108: ["Despayre Prison Colony", "Northern Jungles", "Southern Territories", "Eastern Reaches",
          "Western Wilds", "Imperial Garrison Zone", "Outer Wilderness"],  # Despayre
    111: ["Dubrillion Station", "Northern Reaches", "Southern Settlement Zone",
          "Eastern Territories", "Western Coast", "Outer Trade Post", "Vong Frontier",
          "Coastal Resort"],  # Dubrillion
    113: ["Kaleesh Settlement", "Grievous Homeland", "Northern Mountains", "Southern Jungles",
          "Eastern Coast", "Western Wilderness", "Sacred Lands", "Outer Clan Territories"],  # Kalee
    114: ["Yaga Minor Shipyards", "Northern Settlement Zone", "Southern Territories",
          "Eastern Reaches", "Western Construction Yard", "Imperial Drydocks",
          "Outer Defence Ring"],  # Yaga Minor
    118: ["Colla Prime", "Colicoid Manufacturing Complex", "Southern Jungles", "Northern Wastes",
          "Eastern Hive Cities", "Western Larval Grounds", "Outer Hatchery Zones"],  # Colla IV
    120: ["Umbara City", "Umbaran Militia Territory", "Northern Shadow Forests", "Southern Trenches",
          "Eastern Umbaran Lines", "Western Phosphorus Plains", "Shadowed Highlands",
          "Bioluminescent Lowlands"],  # Umbara
    192: ["Florrum Desert", "Weequay Pirate Camp", "Northern Wasteland", "Southern Territories",
          "Eastern Acid Geysers", "Western Outpost", "Hondo's Stronghold", "Skull Ridge"],  # Florrum
    193: ["Citadel Prison", "Northern Rocky Terrain", "Southern Reaches", "Eastern Territories",
          "Western Cliffs", "Republic Outpost", "Outer Wastes"],  # Lola Sayu
    198: ["Kessel Spice Mines", "The Maw Approach", "Pyke Territory", "Northern Mining Claims",
          "Smugglers' Run Approach", "Eastern Glitterstim Vaults", "Western Refinery",
          "Imperial Mining Zone"],  # Kessel
    199: ["Oba Diah City", "Pyke Syndicate HQ", "Northern Territories", "Southern Reaches",
          "Eastern Trade Hub", "Spice Vaults", "Western Settlement"],  # Oba Diah
    202: ["Al'Har City", "Upland Liberation Front Territory", "Northern Jungle", "Southern Plateau",
          "Korun Highlands", "Eastern Volcano Range", "Western Jungle Lowlands",
          "Balawai Settlement"],  # Haruun Kal

    # ── Outer Rim – Tatooine (partially split, small remnant) ──────────────
    36:  ["Anchorhead", "Dune Sea", "Northern Wastes", "Southern Sand Plains"],  # Tatooine

    # ── Outer Rim – less documented worlds ─────────────────────────────────
    54:  ["Manpha City", "Northern Reaches", "Southern Plains", "Eastern Territories",
          "Western Coast", "Outer Settlement", "Highland Region"],  # Manpha

    # ── Wild Space / Unknown Regions ─────────────────────────────────────────
    181: ["Ilum Crystal Cave", "Jedi Temple Ruins", "Northern Ice Fields", "Southern Mountains",
          "Eastern Glacier", "Sacred Crystal Caverns", "Frozen Wastes"],  # Ilum
    182: ["Cioral City", "Northern Territories", "Southern Reaches", "Eastern Plains",
          "Western Coast", "Outer Settlement"],  # Cioral
    183: ["Csaplar", "CEDF Military Zone", "Unknown Regions Buffer", "Northern Ice Plains",
          "Southern Outposts", "Eastern Glaciers", "Western Tundra", "Chiss Ascendancy Capital"],  # Csilla
    184: ["Copero City", "Northern Territories", "Southern Reaches", "Eastern Mountains",
          "Western Plains", "Coastal Region", "Outer Settlement"],  # Copero
    185: ["Csaus City", "Northern Territories", "Southern Reaches", "Eastern Plains",
          "Western Coast", "Outer Settlement"],  # Csaus
    189: ["Ord Cestus City", "JK-Series Factory", "Northern Territories", "Southern Reaches",
          "Eastern Mining Zone", "X'Ting Hives", "Western Wasteland"],  # Ord Cestus
    200: ["Pantora Town", "Northern Ice Plains", "Southern Territories", "Mountain Reaches",
          "Eastern Glacier", "Western Settlement", "Outer Wilderness"],  # Pantora

    # NOTE: The following were left out because they are already confirmed split:
    # 1-8 (Coruscant/Alderaan/Tatooine sub-systems, Anaxes, Tython, Arkania, Carida, Byss, Rishi, Hypori, Ossus, Geonosis, Mandalore)
    # 117-291 (Kashyyyk sub-states we just created)
}
# ── Remove duplicate key 54 (Manpha defined twice above) ──────────────────────
# Python takes the last definition.

# ─────────────────────────────────────────────────────────────────────────────

import argparse
import pickle
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from PIL import Image
    import numpy as np
    _HAVE_PIL = True
except ImportError:
    _HAVE_PIL = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MOD_ROOT         = Path(__file__).parent
STATES_DIR       = MOD_ROOT / "history" / "states"
DEF_CSV          = MOD_ROOT / "map" / "definition.csv"
BUILDINGS_TXT    = MOD_ROOT / "map" / "buildings.txt"
LOC_FILE         = MOD_ROOT / "localisation" / "english" / "state_names_l_english.yml"
PROVINCES_BMP    = MOD_ROOT / "map" / "provinces.bmp"
SUPPLY_NODES_TXT = MOD_ROOT / "map" / "supply_nodes.txt"
CENTROID_CACHE   = MOD_ROOT / ".province_centroids.pkl"

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

DEFAULT_MIN_STATES   = 7     # target minimum sub-states per planet
DEFAULT_MAX_STATES   = 10    # target maximum sub-states per planet
DEFAULT_MIN_PROV     = 60    # --all skips states below this

TERRAIN_DISPLAY = {
    "urban":    "City",
    "plains":   "Plains",
    "hills":    "Highlands",
    "forest":   "Forest",
    "jungle":   "Jungle",
    "desert":   "Desert",
    "marsh":    "Wetlands",
    "mountain": "Mountains",
    "ocean":    "Ocean",
    "lake":     "Ocean",
    "unknown":  "Wilderness",
}

TERRAIN_CATEGORY = {
    "urban":    "capital_sector",
    "plains":   "agricultural_sector",
    "hills":    "agricultural_sector",
    "forest":   "agricultural_sector",
    "jungle":   "agricultural_sector",
    "desert":   "wasteland_sector",
    "marsh":    "wasteland_sector",
    "mountain": "wasteland_sector",
    "ocean":    "wasteland_sector",
    "lake":     "wasteland_sector",
    "unknown":  "wasteland_sector",
}

REGION_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StateData:
    state_id: int
    name_key: str
    provinces: List[int]
    owner: str = ""
    cores: List[str] = field(default_factory=list)
    resources: Dict[str, str] = field(default_factory=dict)
    resource_comments: Dict[str, str] = field(default_factory=dict)
    manpower: int = 0
    category: str = "wasteland_sector"
    bldg_max_lvl: float = 1.0
    local_supplies: float = 0.0
    province_buildings: Dict[int, Dict[str, int]] = field(default_factory=dict)


@dataclass
class ChildGroup:
    provinces: List[int]
    terrain: str
    label: str
    category: str
    manpower: int
    has_naval_base: bool = False
    center: Tuple[float, float] = (0.0, 0.0)   # mean pixel position of the group's provinces
    seed: int = 0                                # the seed province this group grew from

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def load_definition(path: Path) -> Dict[int, Dict]:
    result: Dict[int, Dict] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 7:
                continue
            try:
                result[int(parts[0])] = {
                    "terrain":    parts[6].strip(),
                    "is_coastal": parts[5].strip().lower() == "true",
                }
            except (ValueError, IndexError):
                continue
    return result


def parse_state_file(path: Path) -> Optional[StateData]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  ERROR reading {path.name}: {e}")
        return None

    try:
        sid_m  = re.search(r"\bid\s*=\s*(\d+)", content)
        if not sid_m:
            return None
        state_id = int(sid_m.group(1))
        name_m   = re.search(r'\bname\s*=\s*"([^"]+)"', content)
        name_key = name_m.group(1) if name_m else f"STATE_{state_id}"
        prov_m   = re.search(r"provinces\s*=\s*\{([^}]*)\}", content, re.DOTALL)
        provinces = [int(x) for x in prov_m.group(1).split()] if prov_m else []
        mp_m     = re.search(r"\bmanpower\s*=\s*(\d+)", content)
        manpower = int(mp_m.group(1)) if mp_m else 0
        cat_m    = re.search(r"\bstate_category\s*=\s*(\w+)", content)
        category = cat_m.group(1) if cat_m else "wasteland_sector"
        bml_m    = re.search(r"\bbuildings_max_level_factor\s*=\s*([\d.]+)", content)
        bldg_max_lvl = float(bml_m.group(1)) if bml_m else 1.0
        ls_m     = re.search(r"\blocal_supplies\s*=\s*([\d.]+)", content)
        local_supplies = float(ls_m.group(1)) if ls_m else 0.0
        own_m    = re.search(r"\bowner\s*=\s*([A-Z]{3})\b", content)
        owner    = own_m.group(1) if own_m else ""
        cores    = re.findall(r"\badd_core_of\s*=\s*([A-Z]{3})\b", content)
    except Exception as e:
        print(f"  ERROR parsing {path.name}: {e}")
        return None

    resources: Dict[str, str] = {}
    resource_comments: Dict[str, str] = {}
    res_m = re.search(r"\bresources\s*=\s*\{([^}]*)\}", content, re.DOTALL)
    if res_m:
        for line in res_m.group(1).splitlines():
            rm = re.match(r"\s*(\w+)\s*=\s*(\d+)\s*(#.*)?", line)
            if rm and rm.group(1) not in ("id", "manpower"):
                resources[rm.group(1)] = rm.group(2)
                if rm.group(3):
                    resource_comments[rm.group(1)] = rm.group(3)

    province_buildings: Dict[int, Dict[str, int]] = {}
    for m in re.finditer(r"(\d+)\s*=\s*\{([^}]*)\}", content):
        pid = int(m.group(1))
        if pid < 10:
            continue
        bldgs = {bm.group(1): int(bm.group(2)) for bm in re.finditer(r"(\w+)\s*=\s*(\d+)", m.group(2))}
        if bldgs:
            province_buildings[pid] = bldgs

    return StateData(
        state_id=state_id, name_key=name_key, provinces=provinces,
        owner=owner, cores=cores, resources=resources,
        resource_comments=resource_comments, manpower=manpower,
        category=category, bldg_max_lvl=bldg_max_lvl,
        local_supplies=local_supplies, province_buildings=province_buildings,
    )


def load_all_states(states_dir: Path) -> Dict[int, StateData]:
    states: Dict[int, StateData] = {}
    for f in sorted(states_dir.glob("*.txt")):
        sd = parse_state_file(f)
        if sd and sd.provinces:
            states[sd.state_id] = sd
    return states


def load_localisation(loc_path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in loc_path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"\s*(STATE_\d+):0\s+\"([^\"]*)\"", line)
        if m:
            result[m.group(1)] = m.group(2)
    return result


def load_buildings(buildings_path: Path) -> List[Tuple]:
    content = buildings_path.read_text(encoding="utf-8", errors="replace").strip()
    fields  = content.split(";")
    entries: List[Tuple] = []
    i = 0
    while i + 6 < len(fields):
        try:
            entries.append((
                int(fields[i]), fields[i+1],
                float(fields[i+2]), float(fields[i+3]), float(fields[i+4]),
                float(fields[i+5]), fields[i+6],
            ))
        except (ValueError, IndexError):
            pass
        i += 7
    return entries

# ---------------------------------------------------------------------------
# Supply nodes + province centroids
# ---------------------------------------------------------------------------

def load_supply_nodes(path: Path) -> Set[int]:
    """
    Parse supply_nodes.txt. Format is `level prov_id` per line.
    Returns the set of province IDs that are supply hubs.
    """
    nodes: Set[int] = set()
    if not path.exists():
        return nodes
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            try:
                nodes.add(int(parts[1]))
            except ValueError:
                continue
    return nodes


def load_province_centroids(force_rebuild: bool = False
) -> Tuple[Dict[int, Tuple[float, float]], Dict[int, Set[int]]]:
    """
    Compute & cache, in one pass over provinces.bmp:
      • centroids:  {province_id: (x, y)}  pixel-space mean position
      • adjacency:  {province_id: {neighbour_id, ...}} 4-connected neighbours
    Cached as a (centroids, adjacency) tuple in .province_centroids.pkl.
    """
    if not _HAVE_PIL:
        print("  WARNING: Pillow + numpy not installed — using degenerate fallback.")
        print("           Install with:  pip install pillow numpy")
        return {}, {}

    if CENTROID_CACHE.exists() and not force_rebuild:
        try:
            with open(CENTROID_CACHE, "rb") as f:
                cached = pickle.load(f)
            if isinstance(cached, tuple) and len(cached) == 2:
                return cached  # (centroids, adjacency)
            # Old cache (centroids only) → rebuild to get adjacency
        except Exception:
            pass

    print("  Building province centroid + adjacency index from provinces.bmp...")

    # 1. RGB → province_id from definition.csv
    color_to_pid: Dict[Tuple[int, int, int], int] = {}
    with open(DEF_CSV, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 4:
                continue
            try:
                color_to_pid[(int(parts[1]), int(parts[2]), int(parts[3]))] = int(parts[0])
            except (ValueError, IndexError):
                continue

    items = sorted(color_to_pid.items(), key=lambda kv: (kv[0][0] << 16) | (kv[0][1] << 8) | kv[0][2])
    sorted_keys = np.array([(c[0] << 16) | (c[1] << 8) | c[2] for c, _ in items], dtype=np.uint32)
    sorted_pids = np.array([pid for _, pid in items], dtype=np.int32)

    img = Image.open(PROVINCES_BMP).convert("RGB")
    arr = np.asarray(img)
    h, w, _ = arr.shape
    print(f"    provinces.bmp {w}x{h}, scanning {len(items):,} province colours...")

    pix_keys = (
        (arr[:, :, 0].astype(np.uint32) << 16)
        | (arr[:, :, 1].astype(np.uint32) << 8)
        | arr[:, :, 2].astype(np.uint32)
    ).ravel()

    idx = np.searchsorted(sorted_keys, pix_keys)
    idx_clamped = np.minimum(idx, len(sorted_keys) - 1)
    valid = sorted_keys[idx_clamped] == pix_keys
    pid_arr = np.where(valid, sorted_pids[idx_clamped], -1)

    # Centroids via bincount
    mask = pid_arr >= 0
    pids = pid_arr[mask]
    ys, xs = np.indices((h, w))
    xs_v = xs.ravel()[mask]
    ys_v = ys.ravel()[mask]

    if len(pids) == 0:
        print("    WARNING: no province pixels matched.")
        return {}, {}

    max_pid = int(pids.max()) + 1
    counts = np.bincount(pids, minlength=max_pid)
    sum_x = np.bincount(pids, weights=xs_v.astype(np.float64), minlength=max_pid)
    sum_y = np.bincount(pids, weights=ys_v.astype(np.float64), minlength=max_pid)

    centroids: Dict[int, Tuple[float, float]] = {}
    for pid in range(max_pid):
        if counts[pid] > 0:
            centroids[pid] = (float(sum_x[pid] / counts[pid]), float(sum_y[pid] / counts[pid]))

    print(f"    {len(centroids):,} centroids done. Building adjacency...")

    # Adjacency: 4-connected neighbours from the 2-D pid grid
    grid = pid_arr.reshape(h, w)
    pairs_list = []
    # Horizontal pairs
    a, b = grid[:, :-1], grid[:, 1:]
    m = (a >= 0) & (b >= 0) & (a != b)
    if m.any():
        pairs_list.append(np.column_stack([a[m], b[m]]))
    # Vertical pairs
    a, b = grid[:-1, :], grid[1:, :]
    m = (a >= 0) & (b >= 0) & (a != b)
    if m.any():
        pairs_list.append(np.column_stack([a[m], b[m]]))

    adjacency: Dict[int, Set[int]] = defaultdict(set)
    if pairs_list:
        pairs = np.vstack(pairs_list)
        pairs.sort(axis=1)
        # Dedup: pack into a single int key, unique, unpack
        keys = pairs[:, 0].astype(np.int64) * (max_pid + 1) + pairs[:, 1].astype(np.int64)
        unique_keys = np.unique(keys)
        for k in unique_keys:
            a_i = int(k // (max_pid + 1))
            b_i = int(k % (max_pid + 1))
            adjacency[a_i].add(b_i)
            adjacency[b_i].add(a_i)

    # Convert defaultdict to plain dict for cleaner pickling
    adjacency_plain = {pid: set(neighs) for pid, neighs in adjacency.items()}
    print(f"    {len(adjacency_plain):,} provinces have neighbours, "
          f"{sum(len(v) for v in adjacency_plain.values())//2:,} unique adjacency pairs.")

    try:
        with open(CENTROID_CACHE, "wb") as f:
            pickle.dump((centroids, adjacency_plain), f)
    except Exception as e:
        print(f"    (could not write cache: {e})")

    return centroids, adjacency_plain

# ---------------------------------------------------------------------------
# Splitting logic — supply-node-seeded Voronoi
# ---------------------------------------------------------------------------

def dominant_terrain(provinces: List[int], terrain_lookup: Dict) -> str:
    counts: Dict[str, int] = defaultdict(int)
    for p in provinces:
        counts[terrain_lookup.get(p, {}).get("terrain", "unknown")] += 1
    return max(counts, key=lambda k: counts[k]) if counts else "unknown"


def _d2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _farthest_first(
    pool: List[int],
    starting: List[int],
    n: int,
    centroids: Dict[int, Tuple[float, float]],
) -> List[int]:
    """k-means++ style farthest-point selection."""
    chosen = list(starting)
    avail = [p for p in pool if p not in chosen and p in centroids]

    if not chosen and avail:
        cx = sum(centroids[p][0] for p in avail) / len(avail)
        cy = sum(centroids[p][1] for p in avail) / len(avail)
        first = min(avail, key=lambda p: _d2(centroids[p], (cx, cy)))
        chosen.append(first)
        avail.remove(first)

    while len(chosen) < n and avail:
        far = max(avail, key=lambda p: min(_d2(centroids[p], centroids[s]) for s in chosen))
        chosen.append(far)
        avail.remove(far)

    return chosen


def _select_seeds(
    state_provs: List[int],
    centroids: Dict[int, Tuple[float, float]],
    supply_nodes: Set[int],
    target: int,
) -> List[int]:
    """
    Pick `target` seed provinces for a state.
      • Prefer real supply-node provinces (the hubs the player sees on the map).
      • Too few SNs  → augment with the provinces farthest from existing seeds.
      • Too many SNs → trim down using farthest-first to keep the most spread out.
    """
    pool = [p for p in state_provs if p in centroids]
    if not pool:
        return []

    sns = [p for p in pool if p in supply_nodes]

    if len(sns) == target:
        return sns
    if len(sns) > target:
        return _farthest_first(sns, [sns[0]], target, centroids)
    return _farthest_first(pool, sns, target, centroids)


def _region_grow(
    state_provs: List[int],
    seeds: List[int],
    adjacency: Dict[int, Set[int]],
    centroids: Dict[int, Tuple[float, float]],
) -> Dict[int, List[int]]:
    """
    Round-robin parallel BFS from each seed using province adjacency.
    Each step every seed's frontier claims its unclaimed neighbours, so cell
    boundaries follow real province topology — producing organic blob shapes
    instead of geometric Voronoi pie slices.
    Any province that's an isolated island (no adjacency path to any seed) is
    handed to its nearest seed by centroid distance as a fallback.
    """
    state_set = set(state_provs)
    claimed: Dict[int, int] = {}        # pid -> seed_index
    frontiers: List[Set[int]] = []
    for i, s in enumerate(seeds):
        claimed[s] = i
        frontiers.append({s})

    # BFS until every frontier is empty
    while any(frontiers):
        for i in range(len(seeds)):
            new_frontier: Set[int] = set()
            for prov in frontiers[i]:
                for neigh in adjacency.get(prov, ()):
                    if neigh in state_set and neigh not in claimed:
                        claimed[neigh] = i
                        new_frontier.add(neigh)
            frontiers[i] = new_frontier

    # Orphan provinces (no adjacency path to any seed) → nearest-by-centroid
    for p in state_provs:
        if p in claimed:
            continue
        if p in centroids:
            nearest_i = min(
                range(len(seeds)),
                key=lambda i: _d2(centroids[p], centroids[seeds[i]]) if seeds[i] in centroids else float("inf"),
            )
        else:
            nearest_i = 0
        claimed[p] = nearest_i

    # Group provinces by seed index
    groups: Dict[int, List[int]] = {s: [] for s in seeds}
    for prov, idx in claimed.items():
        groups[seeds[idx]].append(prov)
    return groups


def compute_groups(
    state: StateData,
    terrain_lookup: Dict,
    centroids: Dict[int, Tuple[float, float]],
    adjacency: Dict[int, Set[int]],
    supply_nodes: Set[int],
    min_states: int = DEFAULT_MIN_STATES,
    max_states: int = DEFAULT_MAX_STATES,
    force_n: Optional[int] = None,
) -> List[ChildGroup]:
    """
    Supply-node-seeded splitter with topology-aware region growing.

    Strategy:
      1. Decide how many sub-states to make (force_n if lore names provided,
         otherwise the supply-node count clamped to [min_states, max_states]).
      2. Pick that many SEED provinces — prefer real supply-node provinces.
      3. Region-grow each seed via province adjacency (parallel BFS), so cell
         boundaries follow actual map topology and look organic.
    """
    if not state.provinces:
        return []

    state_provs = list(state.provinces)
    total = len(state_provs)
    if total < 2:
        return []

    # 1. Decide seed count
    if force_n is not None:
        target_n = force_n
    else:
        sn_count = sum(1 for p in state_provs if p in supply_nodes)
        target_n = max(min_states, min(max_states, sn_count if sn_count > 0 else min_states))
    target_n = max(1, min(target_n, total))

    # 2. Pick seeds (supply nodes preferred, farthest-first to fill / trim)
    seeds = _select_seeds(state_provs, centroids, supply_nodes, target_n)
    if len(seeds) < target_n:
        # Fallback: no centroid data — even slicing of sorted provinces
        sp = sorted(state_provs)
        chunks: List[List[int]] = []
        base, rem = divmod(total, target_n)
        idx = 0
        for i in range(target_n):
            size = base + (1 if i < rem else 0)
            chunks.append(sp[idx:idx + size])
            idx += size
        groups: List[ChildGroup] = []
        for i, chunk in enumerate(chunks):
            if not chunk:
                continue
            terrain = dominant_terrain(chunk, terrain_lookup)
            groups.append(ChildGroup(
                provinces=chunk, terrain=terrain,
                label=f"Region {REGION_LABELS[i]}",
                category=TERRAIN_CATEGORY.get(terrain, "wasteland_sector"),
                manpower=round(state.manpower * len(chunk) / total),
                has_naval_base=any("naval_base" in state.province_buildings.get(p, {}) for p in chunk),
            ))
        if groups and not any(g.terrain == "urban" for g in groups):
            groups[0].category = "capital_sector"
        return groups

    # 3. Region-grow from each seed
    seed_provs = _region_grow(state_provs, seeds, adjacency, centroids)

    # 4. Order groups roughly left-to-right by seed X for stable labelling
    seeds_ordered = sorted(seeds, key=lambda s: centroids.get(s, (0.0, 0.0))[0])
    groups: List[ChildGroup] = []
    for i, seed in enumerate(seeds_ordered):
        provs = seed_provs[seed]
        if not provs:
            continue
        terrain = dominant_terrain(provs, terrain_lookup)
        cat = TERRAIN_CATEGORY.get(terrain, "wasteland_sector")
        if seed in supply_nodes and terrain == "urban":
            cat = "capital_sector"
        has_nb = any("naval_base" in state.province_buildings.get(p, {}) for p in provs)
        # Compute group center from province centroids (mean position)
        c_x_acc, c_y_acc, c_n = 0.0, 0.0, 0
        for p in provs:
            if p in centroids:
                c_x_acc += centroids[p][0]
                c_y_acc += centroids[p][1]
                c_n += 1
        center = (c_x_acc / c_n, c_y_acc / c_n) if c_n else centroids.get(seed, (0.0, 0.0))
        groups.append(ChildGroup(
            provinces=provs,
            terrain=terrain,
            label=f"Region {REGION_LABELS[i]}",
            category=cat,
            manpower=round(state.manpower * len(provs) / total),
            has_naval_base=has_nb,
            center=center,
            seed=seed,
        ))

    # Capital fallback: promote first supply-node-seeded group, else first group
    if groups and not any(g.category == "capital_sector" for g in groups):
        cap_idx = 0
        for i, seed in enumerate(seeds_ordered):
            if seed in supply_nodes:
                cap_idx = i
                break
        groups[cap_idx].category = "capital_sector"

    return groups

# ---------------------------------------------------------------------------
# Building assignment
# ---------------------------------------------------------------------------

def assign_buildings_to_groups(
    entries: List[Tuple],
    old_state_id: int,
    groups_with_ids: List[Tuple],   # [(new_state_id, ChildGroup), ...]
) -> List[Tuple]:
    old_indices = [(i, e) for i, e in enumerate(entries) if e[0] == old_state_id]
    if not old_indices or len(groups_with_ids) == 0:
        return entries

    result = list(entries)
    n_groups = len(groups_with_ids)

    if n_groups == 1:
        new_sid = groups_with_ids[0][0]
        for orig_idx, e in old_indices:
            result[orig_idx] = (new_sid,) + e[1:]
        return result

    groups_sorted = sorted(groups_with_ids, key=lambda gs: min(gs[1].provinces))
    old_sorted    = sorted(old_indices, key=lambda ie: ie[1][2])   # sort by X coord
    n = len(old_sorted)
    for rank, (orig_idx, e) in enumerate(old_sorted):
        g_idx   = min(int(rank * n_groups / n), n_groups - 1)
        new_sid = groups_sorted[g_idx][0]
        result[orig_idx] = (new_sid,) + e[1:]

    return result

# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def render_state_file(
    state_id: int, name_key: str, provinces: List[int],
    owner: str, cores: List[str],
    resources: Dict[str, str], resource_comments: Dict[str, str],
    province_buildings: Dict[int, Dict[str, int]],
    manpower: int, category: str, bldg_max_lvl: float, local_supplies: float,
) -> str:
    lines = ["state={", f"\tid={state_id}", f'\tname="{name_key}"', "\tprovinces={"]
    buf = "\t\t"
    for pid in sorted(provinces):
        tok = str(pid) + " "
        if len(buf) + len(tok) > 120:
            lines.append(buf.rstrip())
            buf = "\t\t"
        buf += tok
    if buf.strip():
        lines.append(buf.rstrip())
    lines.append("\t}")

    if resources:
        lines.append("\tresources={")
        for res, val in resources.items():
            lines.append(f"\t\t{res}={val}{resource_comments.get(res, '')}")
        lines.append("\t}")

    lines.append("\thistory = {")
    pset = set(provinces)
    relevant = {pid: b for pid, b in province_buildings.items() if pid in pset}
    if relevant:
        lines.append("\t\tbuildings = {")
        for pid in sorted(relevant):
            lines.append(f"\t\t\t{pid} = {{")
            for btype, blvl in relevant[pid].items():
                lines.append(f"\t\t\t\t{btype} = {blvl}")
            lines.append("\t\t\t}")
        lines.append("\t\t}")
    lines.append(f"\t\towner = {owner}")
    for c in cores:
        lines.append(f"\t\tadd_core_of = {c}")
    lines.append("\t}")
    lines += [
        f"\tmanpower = {manpower}",
        f"\tstate_category = {category}",
        f"\tbuildings_max_level_factor={bldg_max_lvl:.3f}",
        f"\tlocal_supplies={local_supplies:.3f}",
        "}", "",
    ]
    return "\n".join(lines)


def write_buildings(path: Path, entries: List[Tuple]) -> None:
    parts: List[str] = []
    for sid, btype, x, y, z, rot, level in entries:
        parts += [str(sid), btype, f"{x:.2f}", f"{y:.2f}", f"{z:.2f}", f"{rot:.2f}", str(level)]
    path.write_text(";".join(parts), encoding="utf-8")


def update_localisation(
    loc_path: Path,
    old_key: str,
    new_entries: List[Tuple[str, str]],
) -> None:
    lines   = loc_path.read_text(encoding="utf-8-sig").splitlines()
    first_k, first_n = new_entries[0]
    updated = []
    for line in lines:
        if re.match(rf"\s*{re.escape(old_key)}:0\s+\"", line):
            updated.append(f' {old_key}:0 "{first_n}"')
        else:
            updated.append(line)
    for key, name in new_entries[1:]:
        updated.append(f' {key}:0 "{name}"')
    loc_path.write_text("\n".join(updated) + "\n", encoding="utf-8-sig")

# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------

def find_next_state_id(states: Dict[int, StateData]) -> int:
    return max(states.keys()) + 1 if states else 292


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


# ---------------------------------------------------------------------------
# Semantic lore-name matching
# ---------------------------------------------------------------------------

# Keyword → terrain class that the name implies
NAME_TERRAIN_KEYWORDS: Dict[str, List[str]] = {
    "urban":    ["city", "town", "district", "spaceport", "station", "citadel",
                 "industrial", "manufacturing", "shipyard", "drydock", "factory",
                 "refinery", "foundry", "complex", "yards", "outpost", "capital",
                 "headquarters", "hq", "settlement", "settlements", "port",
                 "fortress", "palace", "temple", "ring", "facility", "depot"],
    "jungle":   ["jungle", "jungles", "rainforest"],
    "forest":   ["forest", "forests", "woods", "woodland", "groves", "trees"],
    "desert":   ["desert", "deserts", "dunes", "sand", "wastes", "wasteland",
                 "wastelands", "sandflats", "saltflats", "badlands", "flats"],
    "mountain": ["mountain", "mountains", "highland", "highlands", "peak", "peaks",
                 "hills", "ridge", "ravine", "ravines", "cliff", "cliffs",
                 "plateau", "plateaus", "range"],
    "plains":   ["plains", "plain", "grass", "grassland", "grasslands",
                 "steppes", "fields", "savannah", "prairie", "valley", "valleys",
                 "lowlands", "croplands", "pastures"],
    "marsh":    ["marsh", "marshes", "marshland", "marshlands", "swamp", "swamps",
                 "wetland", "wetlands", "mire", "bog", "bayou", "mud", "delta",
                 "sacred place"],
    "lake":     ["ocean", "oceans", "sea", "seas", "reef", "reefs", "shallows",
                 "coast", "coastal", "coastline", "atoll", "shore", "shores",
                 "bay", "harbor", "harbour", "waters", "depths", "lagoon",
                 "lake", "lakes", "archipelago", "ice fields", "glacier"],
}

DIRECTION_KEYWORDS: Dict[str, List[str]] = {
    "north": ["north", "northern", "upper"],
    "south": ["south", "southern", "lower"],
    "east":  ["east", "eastern"],
    "west":  ["west", "western"],
}

# Terrains that we treat as compatible for soft matching (half score)
TERRAIN_SIMILAR: Dict[str, Set[str]] = {
    "jungle":   {"forest", "marsh"},
    "forest":   {"jungle", "plains"},
    "plains":   {"forest", "hills"},
    "hills":    {"mountain", "plains"},
    "mountain": {"hills"},
    "marsh":    {"jungle", "lake"},
    "lake":     {"marsh", "ocean"},
    "ocean":    {"lake"},
    "desert":   {"plains"},
}


def _parse_name_hints(name: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (terrain_hint, direction_hint) from a lore name. Both may be None."""
    lower = name.lower()
    terrain_hint = None
    for terrain, kws in NAME_TERRAIN_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            terrain_hint = terrain
            break
    direction_hint = None
    for direction, kws in DIRECTION_KEYWORDS.items():
        if any(re.search(r"\b" + kw + r"\b", lower) for kw in kws):
            direction_hint = direction
            break
    return terrain_hint, direction_hint


def _group_directions(group: "ChildGroup", planet_center: Tuple[float, float],
                      planet_radius: float) -> Set[str]:
    """Cardinal directions a group sits in, relative to planet centre."""
    dx = group.center[0] - planet_center[0]
    dy = group.center[1] - planet_center[1]
    threshold = planet_radius * 0.15   # ignore very-near-centre groups
    dirs: Set[str] = set()
    if dy < -threshold: dirs.add("north")
    if dy >  threshold: dirs.add("south")
    if dx >  threshold: dirs.add("east")
    if dx < -threshold: dirs.add("west")
    return dirs


def match_lore_names_to_groups(
    lore_names: List[str],
    groups: List[ChildGroup],
) -> List[str]:
    """
    Reorder lore_names so each group gets the name that best fits its terrain
    and geographic position. Uses keyword parsing + greedy bipartite matching.
    Returns a list parallel to `groups` (same length).
    """
    n = len(groups)
    if len(lore_names) != n or n == 0:
        return list(lore_names) + [f"Region {REGION_LABELS[i]}" for i in range(len(lore_names), n)]

    # Planet centre & rough "radius" for direction thresholding
    pc_x = sum(g.center[0] for g in groups) / n
    pc_y = sum(g.center[1] for g in groups) / n
    planet_center = (pc_x, pc_y)
    spread = max(1.0, max(
        max((g.center[0] - pc_x) ** 2 + (g.center[1] - pc_y) ** 2 for g in groups) ** 0.5,
        1.0,
    ))

    group_dirs = [_group_directions(g, planet_center, spread) for g in groups]

    # Score every (name, group) pair
    pairs: List[Tuple[float, int, int]] = []  # (score, name_idx, group_idx)
    for ni, name in enumerate(lore_names):
        t_hint, d_hint = _parse_name_hints(name)
        is_first = (ni == 0)
        for gi, g in enumerate(groups):
            score = 0.0
            if t_hint:
                if t_hint == g.terrain:
                    score += 10.0
                elif g.terrain in TERRAIN_SIMILAR.get(t_hint, set()):
                    score += 4.0
            if d_hint and d_hint in group_dirs[gi]:
                score += 8.0
            # First name is conventionally the capital → bias toward urban groups
            if is_first and g.terrain == "urban":
                score += 6.0
            if is_first and g.category == "capital_sector":
                score += 3.0
            pairs.append((score, ni, gi))

    # Greedy assignment: take highest score pair, fill remaining positionally
    pairs.sort(key=lambda p: -p[0])
    result: List[Optional[str]] = [None] * n
    used_names: Set[int] = set()
    used_groups: Set[int] = set()
    for score, ni, gi in pairs:
        if score <= 0:
            break
        if ni in used_names or gi in used_groups:
            continue
        result[gi] = lore_names[ni]
        used_names.add(ni)
        used_groups.add(gi)

    # Leftover names → leftover groups in original order
    leftover_names = [lore_names[i] for i in range(n) if i not in used_names]
    leftover_groups = [i for i in range(n) if i not in used_groups]
    for ni, gi in zip(range(len(leftover_names)), leftover_groups):
        result[gi] = leftover_names[ni]

    return [r if r is not None else f"Region {REGION_LABELS[i]}" for i, r in enumerate(result)]


def split_one_state(
    state_id: int,
    states: Dict[int, StateData],
    terrain_lookup: Dict,
    centroids: Dict[int, Tuple[float, float]],
    adjacency: Dict[int, Set[int]],
    supply_nodes: Set[int],
    loc_names: Dict[str, str],
    buildings: List[Tuple],
    min_states: int,
    max_states: int,
    dry_run: bool,
    next_id_ref: List[int],
) -> Optional[List[Tuple]]:

    state = states.get(state_id)
    if not state:
        print(f"  ERROR: State {state_id} not found.")
        return None

    display_name = loc_names.get(state.name_key, state.name_key)
    lore_names   = PLANET_TARGETS.get(state_id)
    force_n      = len(lore_names) if lore_names else None

    groups = compute_groups(
        state, terrain_lookup, centroids, adjacency, supply_nodes,
        min_states=min_states, max_states=max_states, force_n=force_n,
    )

    if len(groups) <= 1:
        print(f"  State {state_id} ({display_name}): {len(state.provinces)} provinces → only 1 group, skipping.")
        return buildings

    # Generic placeholder labels: "<Planet> A", "<Planet> B", ... — rename in-game later
    for i, g in enumerate(groups):
        g.label = f"{display_name} {REGION_LABELS[i]}"

    # Capital: urban-terrain group wins, otherwise the first sub-state
    urban_idx = next((i for i, g in enumerate(groups) if g.terrain == "urban"), None)
    capital_idx = urban_idx if urban_idx is not None else 0
    for g in groups:
        if g.category == "capital_sector":
            g.category = TERRAIN_CATEGORY.get(g.terrain, "wasteland_sector")
    groups[capital_idx].category = "capital_sector"

    # Assign IDs: group 0 keeps original; rest get new IDs
    groups_with_ids: List[Tuple[int, ChildGroup]] = []
    preview_ids = []
    for i, g in enumerate(groups):
        if i == 0:
            new_id = state_id
        else:
            new_id = next_id_ref[0]
            next_id_ref[0] += 1
        groups_with_ids.append((new_id, g))
        preview_ids.append(new_id)

    sn_in_state = sum(1 for p in state.provinces if p in supply_nodes)
    source = "LORE" if lore_names else "supply-nodes"
    print(f"\nState {state_id} ({display_name}): {len(state.provinces)} provinces, "
          f"{sn_in_state} supply nodes → {len(groups)} sub-states  [{source}]")
    for new_id, g in groups_with_ids:
        nb_warn = "  ⚠ add spaceport" if not g.has_naval_base else ""
        print(f"  {new_id:4d}  {g.label:<45}  {len(g.provinces):3d} provs  {g.category}{nb_warn}")

    if dry_run:
        return None

    updated_buildings = assign_buildings_to_groups(buildings, state_id, groups_with_ids)

    for i, (new_id, g) in enumerate(groups_with_ids):
        is_primary  = (i == 0)
        new_name_key = state.name_key if is_primary else f"STATE_{new_id}"

        content = render_state_file(
            state_id=new_id,
            name_key=new_name_key,
            provinces=g.provinces,
            owner=state.owner,
            cores=state.cores,
            resources=state.resources if is_primary else {},
            resource_comments=state.resource_comments if is_primary else {},
            province_buildings=state.province_buildings,
            manpower=g.manpower,
            category=g.category,
            bldg_max_lvl=state.bldg_max_lvl,
            local_supplies=state.local_supplies,
        )

        if is_primary:
            orig_files = list(STATES_DIR.glob(f"{state_id}-*.txt")) + list(STATES_DIR.glob(f"{state_id}.txt"))
            target_path = orig_files[0] if orig_files else STATES_DIR / f"{state_id}-{safe_filename(display_name)}.txt"
            target_path.write_text(content, encoding="utf-8")
            print(f"    Updated {target_path.name}")
        else:
            child_name = f"{display_name} - {g.label}"
            fname = STATES_DIR / f"{new_id}-{safe_filename(child_name)}.txt"
            fname.write_text(content, encoding="utf-8")
            print(f"    Created {fname.name}")

    loc_entries = []
    for i, (new_id, g) in enumerate(groups_with_ids):
        key  = state.name_key if i == 0 else f"STATE_{new_id}"
        name = g.label   # lore name if available, else terrain-based
        loc_entries.append((key, name))

    update_localisation(LOC_FILE, state.name_key, loc_entries)
    print(f"    Updated localisation ({len(loc_entries)} entries)")

    return updated_buildings

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Supply-node-seeded planet splitter.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list",  action="store_true")
    mode.add_argument("--state", type=int)
    mode.add_argument("--all",   action="store_true")

    parser.add_argument("--min-prov",   type=int, default=DEFAULT_MIN_PROV)
    parser.add_argument("--skip",       type=str, default="")
    parser.add_argument("--min-states", type=int, default=DEFAULT_MIN_STATES,
                        help="Minimum sub-states per planet (default 5)")
    parser.add_argument("--max-states", type=int, default=DEFAULT_MAX_STATES,
                        help="Maximum sub-states per planet (default 7)")
    parser.add_argument("--rebuild-centroids", action="store_true",
                        help="Force-rebuild the province centroid cache")
    parser.add_argument("--dry-run",    action="store_true")
    args = parser.parse_args()

    print("Loading definition.csv...")
    terrain_lookup = load_definition(DEF_CSV)
    print("Loading state files...")
    states = load_all_states(STATES_DIR)
    print("Loading localisation...")
    loc_names = load_localisation(LOC_FILE)
    print("Loading supply nodes...")
    supply_nodes = load_supply_nodes(SUPPLY_NODES_TXT)
    print(f"  {len(supply_nodes):,} supply-node provinces.")
    print("Loading province centroids + adjacency...")
    centroids, adjacency = load_province_centroids(force_rebuild=args.rebuild_centroids)
    print(f"  {len(centroids):,} centroids, {len(adjacency):,} adjacency entries ready.")

    # ── --list ──────────────────────────────────────────────────────────────
    if args.list:
        rows = sorted(
            [(sid, s, loc_names.get(s.name_key, s.name_key)) for sid, s in states.items()],
            key=lambda r: len(r[1].provinces), reverse=True,
        )
        print(f"\n{'ID':>5}  {'Provinces':>10}  {'Lore?':>6}  {'Category':<24}  Name")
        print("-" * 80)
        for sid, s, name in rows:
            marker = " [LORE]" if sid in PLANET_TARGETS else ""
            print(f"{sid:>5}  {len(s.provinces):>10}  {'yes' if sid in PLANET_TARGETS else '':>6}  {s.category:<24}  {name}{marker}")
        return

    # ── Determine target IDs ─────────────────────────────────────────────────
    skip_ids = {int(x) for x in args.skip.split(",") if x.strip().isdigit()}

    if args.state:
        target_ids = [args.state]
    elif args.all:
        target_ids = sorted(
            sid for sid, s in states.items()
            if len(s.provinces) >= args.min_prov and sid not in skip_ids
        )
        print(f"\nFound {len(target_ids)} states with >= {args.min_prov} provinces.")
    else:
        # Default: process only PLANET_TARGETS entries that exist in states dict
        target_ids = sorted(
            sid for sid in PLANET_TARGETS
            if sid in states and sid not in skip_ids
        )
        print(f"\nProcessing {len(target_ids)} PLANET_TARGETS states.")

    if not target_ids:
        print("No states to process.")
        return

    # ── Load buildings (heavy) ───────────────────────────────────────────────
    if not args.dry_run:
        print("Loading buildings.txt...")
        buildings = load_buildings(BUILDINGS_TXT)
        print(f"  Loaded {len(buildings):,} entries.")
    else:
        buildings = []

    next_id_ref = [find_next_state_id(states)]
    print(f"Next available state ID: {next_id_ref[0]}\n")

    for sid in target_ids:
        result = split_one_state(
            state_id=sid, states=states, terrain_lookup=terrain_lookup,
            centroids=centroids, adjacency=adjacency, supply_nodes=supply_nodes,
            loc_names=loc_names, buildings=buildings,
            min_states=args.min_states, max_states=args.max_states,
            dry_run=args.dry_run, next_id_ref=next_id_ref,
        )
        if result is not None:
            buildings = result

    if not args.dry_run and buildings:
        print(f"\nWriting buildings.txt ({len(buildings):,} entries)...")
        write_buildings(BUILDINGS_TXT, buildings)
        print("Done.")
    elif args.dry_run:
        print("\n[dry-run] No files were written.")


if __name__ == "__main__":
    main()
