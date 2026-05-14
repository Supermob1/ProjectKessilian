#!/usr/bin/env python3
"""
name_lore.py — Apply lore-friendly names to split states + victory points.

For each split sub-state, identifies its parent planet from the current placeholder
display name ("Naboo A", "Naboo B", ...) or filename, then matches a lore-accurate
regional name to the state by terrain + cardinal position.

For each victory point, assigns a lore city / location name; the most prominent
VP per planet gets the canonical capital, then secondary cities are spread by
state importance and position.

Writes:
    localisation/english/state_names_l_english.yml      (state names: in-place update)
    localisation/english/victory_points_l_english.yml   (NEW – VP labels)
    localisation/english/provinces_l_english.yml        (NEW – matches VP provinces)

Usage:
    python name_lore.py --dry-run
    python name_lore.py
    python name_lore.py --only Naboo,Ryloth
"""

import argparse
import pickle
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MOD_ROOT       = Path(__file__).parent
STATES_DIR     = MOD_ROOT / "history" / "states"
DEF_CSV        = MOD_ROOT / "map" / "definition.csv"
STATE_LOC      = MOD_ROOT / "localisation" / "english" / "state_names_l_english.yml"
VP_LOC         = MOD_ROOT / "localisation" / "english" / "victory_points_l_english.yml"
PROV_LOC       = MOD_ROOT / "localisation" / "english" / "provinces_l_english.yml"
CENTROID_CACHE = MOD_ROOT / ".province_centroids.pkl"

# ---------------------------------------------------------------------------
# LORE DICT  —  one entry per planet
#   "regions": lore-friendly REGIONAL names (≥ sub-state count, ~8–12 each)
#   "cities":  specific city / VP names (~5–8 each; first = canonical capital)
# Names are matched to states by terrain & cardinal position; surplus names go
# unused. Edit / extend freely.
# ---------------------------------------------------------------------------

PLANET_LORE: Dict[str, Dict[str, List[str]]] = {

    # ── Core / Deep Core ─────────────────────────────────────────────────
    "Coruscant": {
        "regions": ["Galactic Senate District", "Manarai Mountains", "Eastern Promenade",
                    "Western Sector", "Industrial Districts", "Coruscant Underworld",
                    "Jedi Temple Precinct", "Coco Town", "Federal District", "Southern Reach"],
        "cities":  ["Galactic City", "Coco Town", "Quadrant A-89", "Uscru District",
                    "Monument Plaza", "Senate Plaza", "CoCo Town"],
    },
    "Alderaan": {
        "regions": ["Aldera Province", "Crevasse City Region", "Juran Mountains",
                    "Glarus Valley", "Castle Lands", "Apalis Coast", "Terrarium Cities",
                    "Wuitho Wilds", "Northern Plains", "Southern Pastures"],
        "cities":  ["Aldera", "Crevasse City", "Belleau-a-Lir", "Houje", "Terrarium",
                    "Kaamos", "Chianar"],
    },
    "Naboo": {
        "regions": ["Theed District", "Lake Country", "Gungan Wetlands", "Lianorm Marshes",
                    "Northern Mountains", "Eastern Forests", "Western Plains",
                    "Southern Swamps", "Dee'ja Peak Highlands", "Otoh Gunga Bay"],
        "cities":  ["Theed", "Moenia", "Keren", "Kaadara", "Otoh Gunga", "Dee'ja Peak",
                    "Spinnaker", "Harte Secur"],
    },
    "Corellia": {
        "regions": ["Coronet Metropolitan Area", "Tyrena Coast", "Doaba Guerfel",
                    "Bela Vistal", "CorSec Territories", "Selonian Caverns",
                    "Drall Highlands", "Outer Corellian Zones", "Kor Vella District"],
        "cities":  ["Coronet City", "Tyrena", "Doaba Guerfel", "Bela Vistal", "Kor Vella",
                    "Vagran", "Treyhana"],
    },
    "Kuat": {
        "regions": ["Kuat City", "Drive Yards Orbital Ring", "Northern Estates",
                    "Southern Manufacturing", "Eastern Foundries", "Western Spires",
                    "Coastal Reach", "Highland Estates"],
        "cities":  ["Kuat City", "Drive Yards", "Northern Pier", "Kuat Shipyards", "Vondarc"],
    },
    "Fondor": {
        "regions": ["Fondor City", "Fondor Orbital Ring", "Northern Shipyards",
                    "Southern Drydocks", "Eastern Foundry District", "Western Manufacturing",
                    "Industrial Reach", "Coastal Shipyards"],
        "cities":  ["Fondor City", "Pellaeon Yards", "Fondor Drydocks", "Iron Reach"],
    },
    "Chandrila": {
        "regions": ["Hanna City Province", "Silver Sea Coast", "Bana Sea Lowlands",
                    "Northern Highlands", "Crystal Reefs", "Eastern Vineyards",
                    "Western Pastures", "Rural Heartlands"],
        "cities":  ["Hanna City", "Emita", "Brema", "Crystal Reef Port", "Mon Mothma Plaza"],
    },
    "Carida": {
        "regions": ["Carida City", "Imperial Military Academy", "Northern Plains",
                    "Southern Mountains", "Eastern Frontier", "Western Reaches",
                    "Coastal Training Grounds", "Tarkin Highlands"],
        "cities":  ["Carida City", "Tarkin's Teeth", "Caridan Academy", "Spinara", "Ressl"],
    },
    "Commenor": {
        "regions": ["Munto Codru Province", "Northern Districts", "Southern Settlement",
                    "Eastern Trade Hub", "Western Agricultural Belt", "Coastal Reach",
                    "Highland Territories", "Outer Agri-Zones"],
        "cities":  ["Munto Codru", "Talagrim", "Esan Port", "Outer Reach", "Crion Plaza"],
    },
    "Corulag": {
        "regions": ["Curamelle", "Adascopolis", "Kanti", "Adjesk", "Tasjon",
                    "Crullov Province", "Corulag Sea Coast", "Great Bamboo Forest"],
        "cities":  ["Curamelle", "Adascopolis", "Kanti", "Tasjon", "Adjesk"],
    },
    "Anaxes": {
        "regions": ["Fort Anaxes", "Anaxes Citadel", "Anaxes Shipyards", "Sirpar Hills",
                    "Czerka Oasis", "Czerka Hydro-Extraction", "Anaxes Sea Coast",
                    "Old Calamar Province"],
        "cities":  ["Fort Anaxes", "Anaxes Citadel", "New Calamar", "Old Calamar"],
    },
    "Duro": {
        "regions": ["Orbital City Alpha", "Orbital City Beta", "Orbital City Gamma",
                    "Northern Surface Wasteland", "Southern Toxic Flats",
                    "Eastern Industrial Ruins", "Western Habitation Domes", "Polluted Reaches"],
        "cities":  ["Duro Orbital City", "Bolus Station", "Ramordis Port", "New Bormea"],
    },
    "Rendilli": {
        "regions": ["Rendili City", "StarDrive Orbital Yards", "Northern Settlement",
                    "Eastern Plateau", "Southern Reach", "Western Highlands",
                    "Coastal Districts"],
        "cities":  ["Rendili City", "StarDrive Yards", "Loronar Reach", "Rendili Port"],
    },
    "Foerost": {
        "regions": ["Foerost Shipyard District", "Foerost Orbital Ring",
                    "Northern Territories", "Eastern Reaches", "Southern Industrial Belt",
                    "Western Settlement Zone", "Outer Construction Yards"],
        "cities":  ["Foerost", "Foerost Drydocks", "Shipwright's Quarter", "Yarith Port"],
    },
    "Fresia": {
        "regions": ["Incom Corporation Yards", "Subpro Hangars", "Fresia City",
                    "Northern Plains", "Southern Reaches", "Eastern Forests", "Western Coast"],
        "cities":  ["Fresia", "Incom Yards", "Subpro Hangars", "Fresia Spaceport"],
    },
    "Loronar": {
        "regions": ["Loronar City", "Loronar Corporation HQ", "Northern Manufacturing Belt",
                    "Eastern Steppes", "Western Territories", "Southern Settlement",
                    "Outer Agricultural Zone"],
        "cities":  ["Loronar City", "Loronar HQ", "Eastern Steppe Hub"],
    },
    "Esseles": {
        "regions": ["Calamar Heights", "Northern Plains", "Eastern Forests",
                    "Western Plateau", "Southern Coast"],
        "cities":  ["Calamar", "Calmar Port"],
    },
    "Borleias": {
        "regions": ["Borleias Base", "Northern Jungle", "Southern Plains",
                    "Coastal Outpost", "Eastern Highlands", "Western Reaches"],
        "cities":  ["Blackmoon", "Borleias Base", "Pyria Port"],
    },
    "Brentaal": {
        "regions": ["Brentaal Trade District", "Northern Spaceport", "Southern Markets",
                    "Eastern Industrial Belt", "Coastal Reach", "Western Plains"],
        "cities":  ["Brentaal City", "Brentaal Spaceport", "House Daclif"],
    },
    "Arkania": {
        "regions": ["Arkania Jedi Enclave", "Arkania Wastelands", "Arkania Hyperspace",
                    "Novania", "Trade City Region", "Northern Ice Fields", "Southern Tundra"],
        "cities":  ["Arkania Jedi Enclave", "Adascorp HQ", "Novania", "Trade City"],
    },
    "Byss": {
        "regions": ["Byss Citadel", "Northern Byss Plateau", "Byss Southeast",
                    "Byss Central", "South Byss", "Byss SouthEast", "Northern Byss",
                    "Byss Prison", "Byss Research Lab", "Byss Deep Oceans"],
        "cities":  ["Byss Citadel", "Byss Research Lab", "Byss Prison", "Northern Byss"],
    },
    "Tython": {
        "regions": ["Tython Jedi Temple", "Tython Spaceport", "Kato Zakar", "Tython Highlands",
                    "Northern Jungle", "Southern Reaches", "Eastern Plains", "Western Forest"],
        "cities":  ["Tython Jedi Temple", "Tython Spaceport", "Kato Zakar"],
    },

    # ── Inner Rim ────────────────────────────────────────────────────────
    "Manaan": {
        "regions": ["Ahto City", "Northern Ocean", "Southern Kolto Fields",
                    "Eastern Shallows", "Selkath Deep Territories", "Hrakert Rift",
                    "Western Coral Reefs", "Sub-Oceanic Settlements"],
        "cities":  ["Ahto City", "Hrakert Rift", "Kolto Harvesting Plant",
                    "Selkath Capital", "Coral City"],
    },
    "Atzerri": {
        "regions": ["Free Trader's Plaza", "Northern Settlement Zone", "Eastern Territories",
                    "Southern Plains", "Western Marshlands", "Free Trade District",
                    "Coastal Outpost", "Smuggler's Haven"],
        "cities":  ["Atzerri Spaceport", "Free Trader's Plaza", "Smuggler's Haven", "Drathomir"],
    },
    "Cato Neimoidia": {
        "regions": ["Zarra Bridge City", "Northern Bridge Cities", "Southern Reaches",
                    "Mountain Refuge", "Crater Cities", "Eastern Forge", "Lower Bridge Markets",
                    "Cato Neimoidia Station"],
        "cities":  ["Zarra", "Tarko-se", "Koru Neimoidia", "Khariev", "Cato Station"],
    },
    "Cato Neimodia": {  # filename typo variant
        "regions": ["Zarra Bridge City", "Northern Bridge Cities", "Southern Reaches",
                    "Mountain Refuge", "Crater Cities", "Eastern Forge", "Lower Bridge Markets"],
        "cities":  ["Zarra", "Tarko-se", "Koru Neimoidia", "Khariev"],
    },
    "Bestine IV": {
        "regions": ["Bestine City", "Northern Archipelago", "Ocean Territories",
                    "Southern Settlement Zone", "Eastern Atolls", "Western Reefs",
                    "Trade Coastline", "Deep Sea Reach"],
        "cities":  ["Bestine", "Bestine Port", "Atoll Trading Post"],
    },
    "Allanteen VI": {
        "regions": ["Allanteen Shipyards", "Northern Industrial Zone", "Eastern Settlement",
                    "Southern Reaches", "Open Ocean", "Western Coast", "Orbital Drydocks"],
        "cities":  ["Allanteen Six", "Allanteen Drydocks", "Allanteen Spaceport"],
    },
    "Abregado-Rae": {
        "regions": ["Abregado Spaceport", "Northern Plains", "Southern Wetlands",
                    "Eastern Mountain Ranges", "Outer Territories", "Western Lowlands",
                    "Trade District", "Mining Highlands"],
        "cities":  ["Abregado-Rae", "Abregado Spaceport", "Trader's Crossing", "Highland Reach"],
    },
    "Mechis": {
        "regions": ["Mechis III Factory Core", "Eastern Machinery Yards",
                    "Western Component Storage", "Programming Sector", "Northern Foundry",
                    "Southern Assembly Lines", "Outer Droid Plains"],
        "cities":  ["Mechis III", "Mechis Programming Hub", "Foundry Prime"],
    },
    "Thyferria": {
        "regions": ["Xucphra Bacta Farms", "Zaltin Bacta Facilities", "Iskadrell Peak",
                    "Southern Jungle", "Northern Processing Complex", "Vratix Hives",
                    "Eastern Cultivation Zone", "Alazhi Plantations"],
        "cities":  ["Xucphra", "Zaltin", "Iskadrell", "Thyferra Spaceport"],
    },
    "Bothawui": {
        "regions": ["Drev'starn", "Kothlis Spynet Region", "Southern Forest",
                    "Northern Reaches", "Mountain Ranges", "Eastern Plateau",
                    "Bothan Combat Caverns", "Western Coast"],
        "cities":  ["Drev'starn", "Tal'cara", "Kothlis", "Bothan Spynet HQ", "Sko'tal"],
    },
    "Falleen": {
        "regions": ["Falleen Prime", "Xo's Island", "Mountain Hunting Grounds",
                    "Jungle Interior", "Northern Coast", "Eastern Royal Palace",
                    "Southern Marshes", "Black Sun Territory"],
        "cities":  ["Falleen Prime", "Falleen Royal Court", "Black Sun Quarter", "Xo's Island"],
    },
    "Onderon": {
        "regions": ["Iziz", "Beast Riders Territory", "Northern Jungle",
                    "Southern Highland Reaches", "Eastern Territories", "Western Wilderness",
                    "Mandalore Ruins", "Royal Hunting Preserves"],
        "cities":  ["Iziz", "Beast Rider Camp", "Eshkar Niin", "Old Iziz", "Modon Kira's Hold"],
    },
    "Telos": {
        "regions": ["Telos IV Citadel Station", "Polar Restoration Zone",
                    "Southern Wilderness", "Eastern Plateaus", "Northern Plateau",
                    "Czerka Mining Site", "Restored Agricultural Belt"],
        "cities":  ["Citadel Station", "Telos Restoration Project", "Czerka Site Alpha"],
    },
    "Hapes": {
        "regions": ["Hapes Capital", "Royal Court Province", "Northern Plains",
                    "Eastern Highlands", "Southern Coast", "Western Settlements"],
        "cities":  ["Hapan Court", "Hapes Spaceport", "Lorell Royal Palace"],
    },
    "Ciutric": {
        "regions": ["Ciutric City", "Northern Settlement", "Southern Territories",
                    "Eastern Reaches", "Western Industrial Zone", "Coastal Districts"],
        "cities":  ["Ciutric", "Ciutric Spaceport", "Hegemony Palace"],
    },
    "Sluis Van": {
        "regions": ["Sluis Van Shipyards", "Northern Settlement Zone", "Southern Territories",
                    "Eastern Dockyards", "Western Orbital Yards", "Mining Reach"],
        "cities":  ["Sluis Van", "Sluis Drydocks", "Sluis Spaceport"],
    },
    "Botajef": {
        "regions": ["Botajef City", "Northern Plains", "Southern Territories",
                    "Eastern Reaches", "Western Coast", "Outer Settlement"],
        "cities":  ["Botajef", "Botajef Spaceport"],
    },
    "Aeten II": {
        "regions": ["Aeten Crystal Fields", "Northern Mountains", "Western Desert",
                    "Eastern Mining Complex", "Southern Wasteland", "Stygium Refinery"],
        "cities":  ["Aeten Mining HQ", "Stygium Refinery", "Crystal Foundry"],
    },
    "Tibrin": {
        "regions": ["Iskaayuma Reef", "Ishi Tib Reef Districts", "Open Seas",
                    "Coastal Territories", "Northern Shallows", "Southern Deep Waters",
                    "Eastern Reef Colonies", "Western Atoll Chain"],
        "cities":  ["Iskaayuma", "Ishi Tib Spawning Grounds", "Tibrin Coral City"],
    },
    "Vohai": {
        "regions": ["Vohai City", "Northern Plains", "Southern Jungles",
                    "Eastern Territories", "Western Reach", "Coastal Settlement"],
        "cities":  ["Vohai City", "Vohai Spaceport"],
    },

    # ── Mid Rim ──────────────────────────────────────────────────────────
    "Ryloth": {
        "regions": ["Lessu", "Nabat District", "Resdin Province", "Kala'uun Caverns",
                    "Bright Lands", "Cold Hemisphere", "Eastern Valleys", "Twi'lek Highlands",
                    "Cazne Wastes", "Outer Twi'lek Settlements"],
        "cities":  ["Lessu", "Nabat", "Resdin", "Kala'uun", "Cazne", "Tann"],
    },
    "Mon Calamari": {
        "regions": ["Coral City Region", "Mon Cala Capital", "Calamari Reef",
                    "Quarren Depths", "Kee-Piru", "Open Ocean", "Coral Cities",
                    "Floating Star Yards", "Whaladon Migration Route", "Deep Trench"],
        "cities":  ["Coral City", "Foamwander City", "Heurkea", "Aquarius Reef",
                    "Mon Cala Star Yards"],
    },
    "Ithor": {
        "regions": ["Tafanda Bay", "Mother Jungle Reserve", "Cathor Hills",
                    "Faa River Valley", "Ithorian Sky Cities", "Eastern Herd Grounds",
                    "Northern Forest Cathedral", "Western Sacred Groves"],
        "cities":  ["Tafanda Bay", "Vinya Bay", "Ithor Spaceport", "Cathor Hills"],
    },
    "Mandalore": {
        "regions": ["Sundari Dome", "Keldabe", "Beskar Extraction Areas",
                    "Outer Clan Territories", "Mandalore Wastelands", "Clan Wren Territory",
                    "Clan Visla Territory", "Death Watch Zone"],
        "cities":  ["Sundari", "Keldabe", "Mandalore City", "Concordia"],
    },
    "Kashyyyk": {
        "regions": ["Rwookrrorro", "Kashyyyk Shadowlands", "Wroshyr Forest Lowlands",
                    "Wroshyr Forest", "Kashyyyk Upper Canopy", "Northern Wroshyr",
                    "Eastern Coastlands", "Western Mangroves"],
        "cities":  ["Rwookrrorro", "Kachirho", "Kashyyyk Tree-City", "Wartaki"],
    },
    "Trandosha": {
        "regions": ["Hsskhor", "Kashyyyk Hunting Grounds", "Forest Wilderness",
                    "Southern Coasts", "Northern Mountains", "Eastern Hunting Range",
                    "Wookiee Prison Camps", "Western Slave Pens"],
        "cities":  ["Hsskhor", "Hunt Master's Hall", "Trandoshan Slave Markets"],
    },
    "Rodia": {
        "regions": ["Rodiapolis", "Iskaayuma Region", "Northern Jungle", "Southern Wetlands",
                    "Hunters' Preserves", "Eastern Coast", "Western Marshlands",
                    "Betu River Delta"],
        "cities":  ["Rodiapolis", "Equator City", "Iskaayuma", "Skeeto City"],
    },
    "Malastare": {
        "regions": ["Pixelito Province", "Dug Settlement Territories", "Gran Protectorate",
                    "Fuel Refineries", "Eastern Swamps", "Northern Mountain Range",
                    "Doaba Strana", "Outer Lowlands"],
        "cities":  ["Pixelito", "Doaba Strana", "Malastare Spaceport", "Gran Capital"],
    },
    "Mygeeto": {
        "regions": ["Mygeeto City", "IBC Treasury District", "Crystal Wastes",
                    "Northern Reaches", "Southern Mountain Territory", "Eastern Glacier",
                    "Western Refinery", "Frozen Outlands"],
        "cities":  ["Mygeeto City", "IBC Treasury", "Crystal Mining Hub"],
    },
    "Muunilist": {
        "regions": ["Harnaidan", "IBC Banking Complex", "Northern Lush Fields",
                    "Southern Plains", "Eastern Territories", "Western Reach",
                    "Moneylending Vaults", "Outer Garden Zones"],
        "cities":  ["Harnaidan", "IBC Banking Tower", "Muun Capital"],
    },
    "Sullust": {
        "regions": ["Sullcrom City", "Pinyumb", "Waklan Grottos", "Northern Settlements",
                    "SoroSuub Territory", "Lava Tube Habitats", "Eastern Magma Plains",
                    "Geothermal Refinery Zone"],
        "cities":  ["Sullcrom", "Pinyumb", "Waklan", "SoroSuub Capital"],
    },
    "Yag'Dhul": {
        "regions": ["Yag'Dhul Station", "Dark-Side Hemisphere", "Light-Side Hemisphere",
                    "Gravitational Anomaly Zone", "Northern Outposts", "Twilight Belt",
                    "Givin Capital"],
        "cities":  ["Givin Citadel", "Yag'Dhul Station", "Twilight Outpost"],
    },
    "Christphsis": {
        "regions": ["Christoph City", "Southern Crystal Mines", "Northern Fortifications",
                    "Eastern Crystal Ravines", "Underground Cities", "Republic Garrison",
                    "Western Spires", "Cathedral Caves"],
        "cities":  ["Chaleydonia", "Crystal City", "Christoph Spaceport"],
    },
    "Cerea": {
        "regions": ["Targon", "Northern Settlement Zone", "Southern Cerean Highlands",
                    "Eastern Territories", "Cerean Tribal Lands", "Western Plains",
                    "Coastal Reach", "Ancient Hill Country"],
        "cities":  ["Tecave City", "Targon", "Cerean Capital", "Tieos"],
    },
    "Toydaria": {
        "regions": ["Toydaria City", "Northern Swamps", "Southern Wetlands",
                    "Eastern Territories", "Western Marshlands", "Floating Cities",
                    "Royal Palace Region", "Mire Basin"],
        "cities":  ["Toydaria City", "Toydaria Royal Court", "Floating Markets"],
    },
    "Quesh": {
        "regions": ["Quesh Venom Processing", "Three Families Territory",
                    "Northern Toxic Plains", "Southern Steppes", "Eastern Mining Zone",
                    "Hutt Excavation Pits"],
        "cities":  ["Three Families Compound", "Quesh Refinery", "Toxin Vault"],
    },
    "Ord Mantell": {
        "regions": ["Worlport", "Scraplands", "Mannett Point", "Northern Reaches",
                    "Eastern Territories", "Western Mountain Range", "Old Town"],
        "cities":  ["Worlport", "Mannett Point", "Old Worlport", "Imperial Quarter"],
    },
    "Phelarion": {
        "regions": ["Phelarion City", "Northern Territories", "Southern Reaches",
                    "Eastern Plains", "Western Coast", "Outer Settlement"],
        "cities":  ["Phelarion", "Phelarion Spaceport"],
    },
    "Pammant": {
        "regions": ["Pammant Docks", "Northern Reaches", "Southern Coastal Waters",
                    "Eastern Territories", "Western Shipyards", "Outer Construction Yards"],
        "cities":  ["Pammant Docks", "Pammant Shipyards", "Orbital Drydock"],
    },
    "Nyriaan": {
        "regions": ["Nyriaan City", "Spice Fields", "Northern Jungles", "Southern Territories",
                    "Eastern Reach", "Outer Plantation Zone", "Western Wilderness"],
        "cities":  ["Nyriaan City", "Spice Refinery"],
    },
    "Ringo Vinda": {
        "regions": ["Ringo Vinda Station", "North Quadrant", "South Quadrant",
                    "Eastern Terminal", "Western Gate", "Equatorial Ring",
                    "Inner Habitation Belt", "Outer Defence Platforms"],
        "cities":  ["Ringo Vinda Hub", "North Gate", "South Gate", "Equatorial Station"],
    },
    "Takodana": {
        "regions": ["Maz's Castle", "Northern Forest", "Southern Lake Country",
                    "Eastern Ancient Ruins", "Takodana Coastline", "Western Highlands",
                    "Smuggler's Bay"],
        "cities":  ["Maz's Castle", "Takodana Spaceport", "Smuggler's Bay"],
    },
    "Mindor": {
        "regions": ["Mindor Crystal Plains", "Northern Crystal Fields", "Southern Wastelands",
                    "Eastern Caverns", "Western Reach"],
        "cities":  ["Mindor Capital", "Mindor Caves"],
    },
    "Boz Pity": {
        "regions": ["Boz Pity Healing Compound", "Northern Shores", "Southern Territories",
                    "Eastern Reaches", "Western Burial Grounds", "Ancient Sanctuary"],
        "cities":  ["Boz Pity Sanctuary", "Healers' Compound"],
    },
    "Ruusan": {
        "regions": ["Ruusan Capital", "Valley of the Jedi", "Northern Plains",
                    "Southern Hills", "Eastern Reaches", "Western Wilderness"],
        "cities":  ["Ruusan Capital", "Valley of the Jedi", "Bouncer Sanctuary"],
    },

    # ── Outer Rim ────────────────────────────────────────────────────────
    "Tatooine": {
        "regions": ["Mos Eisley", "Anchorhead", "Mos Espa", "Bestine", "Dune Sea",
                    "Jundland Wastes", "Northern Wastes", "Southern Sand Plains"],
        "cities":  ["Mos Eisley", "Mos Espa", "Mos Entha", "Bestine", "Anchorhead", "Tosche Station"],
    },
    "Geonosis": {
        "regions": ["Stalgasin Hive", "Petranaki Arena", "Trippa Hive", "Golbah Hive",
                    "Gehenbar Hive", "Northern Badlands", "Droid Foundry Complex",
                    "Im'g'twe Hills"],
        "cities":  ["Stalgasin Hive", "Petranaki Arena", "Trippa Hive", "Geonosian Capital"],
    },
    "Hoth": {
        "regions": ["Echo Base Ruins", "Clabburn Range", "Cirque Maj", "Great Rift",
                    "Southern Ice Plains", "Wampa Caves", "Northern Glacier",
                    "Eastern Frozen Waste"],
        "cities":  ["Echo Base", "Hoth Outpost", "Cirque Maj"],
    },
    "Mustafar": {
        "regions": ["Mustafar Mining Facility", "Vader's Fortress", "Minsulla Lava Fields",
                    "Eastern Volcanic Plains", "Fralideja", "Northern Magma Sea",
                    "Western Pyroclastic Flats", "Klegger Corp Drilling Sites"],
        "cities":  ["Mustafar Mining HQ", "Vader's Fortress", "Klegger Corp Outpost"],
    },
    "Endor": {
        "regions": ["Bright Tree Village", "Imperial Shield Generator Ruins", "Ewok Territories",
                    "Northern Forest", "Southern Coastal Shallows", "Eastern Tree-Line",
                    "Yuzzum Lakes", "Western Wilderness"],
        "cities":  ["Bright Tree Village", "Imperial Shield Bunker", "Forest Moon Outpost"],
    },
    "Utapau": {
        "regions": ["Pau City", "Utapau City", "Amfu Sinkhole", "Northern Sinkholes",
                    "Eastern Steppes", "Western Ravines", "Lower Sinkhole System",
                    "Surface Wastes", "Pau'an Tombs"],
        "cities":  ["Pau City", "Amfu Sinkhole", "Pau'an Capital", "Utai Settlements"],
    },
    "Saleucami": {
        "regions": ["Saleucami City", "Southern Oasis Belt", "Northern Desert Wastes",
                    "Cave Network", "Eastern Desert Plains", "Western Refuge Camps",
                    "Volcanic Highlands", "Settler Villages"],
        "cities":  ["Saleucami Capital", "Oasis City", "Settler's Crossroads"],
    },
    "Felucia": {
        "regions": ["Rokak'k Baran Outpost", "Northern Fungal Fields", "Ancient Abyss",
                    "Southern Jungle", "Har Gau Settlement", "Eastern Fungal Plains",
                    "Niango Town", "Sarlacc Pit Region"],
        "cities":  ["Rokak'k Baran", "Har Gau", "Niango", "Kway Teow"],
    },
    "Nal Hutta": {
        "regions": ["Bilbousa", "Hutt Ruling Districts", "Evocar Jungles",
                    "Southern Wetlands", "Northern Toxic Swamps", "Eastern Sludge Plains",
                    "Western Spaceport Zone", "Polluted Coast"],
        "cities":  ["Bilbousa", "Jiguuna", "Hutt Council Palace", "Bashka"],
    },
    "Nar Shaddaa": {
        "regions": ["Refugee Sector", "Promenade District", "Hutt Clan Territory",
                    "Black Sun Quarter", "Lower Underworld", "Smuggler's Run District",
                    "Corellian Sector", "Duros Levels", "Lower Industrial Zone"],
        "cities":  ["Nar Shaddaa Spaceport", "Promenade", "Slag Town", "Corellian Sector",
                    "Black Sun Headquarters"],
    },
    "Korriban": {
        "regions": ["Valley of the Dark Lords", "Dreshdae Spaceport", "Shyrack Caverns",
                    "Sith Academy", "Blood Cliffs", "Wild Region", "Northern Wastes",
                    "Tomb of Ajunta Pall"],
        "cities":  ["Dreshdae", "Sith Academy", "Valley of the Dark Lords", "Tomb of Marka Ragnos"],
    },
    "Dromund Kaas": {
        "regions": ["Kaas City", "Citadel District", "Dark Temple", "Malignant Jungle",
                    "Power Generator Fields", "Sith Sanctuary", "Northern Jungle Reaches",
                    "Southern Lightning Plains"],
        "cities":  ["Kaas City", "Dark Temple", "Sith Citadel", "Mandalorian Enclave"],
    },
    "Bastion": {
        "regions": ["Bastion City", "Northern Industrial Zone", "Southern Territories",
                    "Eastern Garrison District", "Imperial Naval Base", "Western Reach",
                    "Outer Defence Perimeter", "Lower City"],
        "cities":  ["Bastion", "Imperial Capitol", "Bastion Garrison"],
    },
    "Eriadu": {
        "regions": ["Eriadu City", "Phelar Port", "Northern Industrial Zone",
                    "Eastern Mountain Reaches", "Southern Outlands", "Tarkin Family Estate",
                    "Polluted Plains", "Western Trade Spine"],
        "cities":  ["Eriadu City", "Phelar", "Tarkin Estate", "Eriadu Spaceport"],
    },
    "Cantonica": {
        "regions": ["Canto Bight", "Desert Interior", "Northern Reach",
                    "Sinta Glacier Colony", "Outer Territories", "Eastern Casino Strip",
                    "Fathier Racing Grounds", "Western Saltflats"],
        "cities":  ["Canto Bight", "Cantonica Spaceport", "Fathier Track"],
    },
    "Bakura": {
        "regions": ["Salis D'aar", "Northern Plains", "Southern Forest", "Eastern Highlands",
                    "Ssi-ruuvi Incursion Zone", "Western Coast", "Cape Suzu"],
        "cities":  ["Salis D'aar", "Cape Suzu", "Bakura Repulsorlift Plant"],
    },
    "Batuu": {
        "regions": ["Black Spire Outpost", "Surabat River Valley", "Eastern Jungle",
                    "Outskirts Settlements", "Ancient Ruins", "Western Wilds",
                    "Forgotten Spires", "Frontier Trade Posts"],
        "cities":  ["Black Spire Outpost", "Surabat", "Batuu Spaceport"],
    },
    "Dantooine": {
        "regions": ["Khoonda Plains", "Jedi Enclave Ruins", "Eastern Grasslands",
                    "Northern Settlement", "Southern Wilderness", "Western Forest",
                    "Crystal Cave Region", "Salvager Settlement"],
        "cities":  ["Khoonda", "Jedi Enclave", "Crystal Cave"],
    },
    "Dathomir": {
        "regions": ["Nightbrother Village", "Nightsister Fortress", "Rancor Territory",
                    "Northern Jungle", "Southern Marshes", "Eastern Spider Caves",
                    "Western Dathomir Plains", "Ancient Sith Tombs"],
        "cities":  ["Nightsister Fortress", "Nightbrother Village", "Singing Mountain Clan"],
    },
    "Iego": {
        "regions": ["Iego Ruins", "Diathim Moonways", "Desert Wastes", "Northern Reaches",
                    "Ancient City", "Southern Crystal Fields", "Western Pilgrim Roads"],
        "cities":  ["Iego City", "Ancient Iego", "Diathim Settlement"],
    },
    "Florrum": {
        "regions": ["Florrum Desert", "Weequay Pirate Camp", "Northern Wasteland",
                    "Southern Territories", "Eastern Acid Geysers", "Hondo's Stronghold",
                    "Skull Ridge"],
        "cities":  ["Hondo's Stronghold", "Weequay Camp", "Skull Ridge"],
    },
    "Honoghr": {
        "regions": ["Nystao", "Noghri Village", "Mount Honoghr", "Poisoned Steppes",
                    "Recovering Lands", "Imperial Toxic Site", "Eastern Wastes",
                    "Clan Strongholds"],
        "cities":  ["Nystao", "Mount Honoghr", "Bakh'tor Clan Hall"],
    },
    "Kessel": {
        "regions": ["Kessel Spice Mines", "The Maw Approach", "Pyke Territory",
                    "Northern Mining Claims", "Smugglers' Run Approach",
                    "Eastern Glitterstim Vaults", "Western Refinery", "Imperial Mining Zone"],
        "cities":  ["Kessel Spice Mines", "Pyke Citadel", "Mine 13"],
    },
    "Oba Diah": {
        "regions": ["Oba Diah City", "Pyke Syndicate HQ", "Northern Territories",
                    "Southern Reaches", "Eastern Trade Hub", "Spice Vaults"],
        "cities":  ["Pyke Citadel", "Oba Diah Capital", "Spice Vault"],
    },
    "Pantora": {
        "regions": ["Pantora Town", "Northern Ice Plains", "Southern Territories",
                    "Mountain Reaches", "Eastern Glacier", "Western Settlement"],
        "cities":  ["Pantoran Capital", "Northern Ice Outpost"],
    },
    "Zygerria": {
        "regions": ["Zygerrian Capital", "Slave Auction Markets", "Eastern Savannah",
                    "Northern Hunting Grounds", "Sea Coast", "Western Plains",
                    "Royal Slave Pens"],
        "cities":  ["Zygerrian Capital", "Slave Markets", "Royal Palace"],
    },
    "Mimban": {
        "regions": ["Mimbanese Settlement", "Northern Swamp Territories", "Crystal Swamps",
                    "Mimban Mud Fields", "Eastern Mining Camps", "Imperial Excavation Zone",
                    "Southern Bog Country"],
        "cities":  ["Mimban Capital", "Crystal Mining Camp", "Imperial Excavation Site"],
    },
    "Rhen Var": {
        "regions": ["Rhen Var Citadel", "Rhen Var Harbor", "Northern Ice Fields",
                    "Southern Ruins", "Eastern Mountains", "Western Glacier",
                    "Ancient Battlefield"],
        "cities":  ["Rhen Var Citadel", "Rhen Var Harbor", "Ancient Battlefield"],
    },
    "Lola Sayu": {
        "regions": ["Citadel Prison", "Northern Rocky Terrain", "Southern Reaches",
                    "Eastern Territories", "Western Cliffs", "Republic Outpost"],
        "cities":  ["The Citadel", "Citadel Prison", "Cliff Outpost"],
    },
    "Haruun Kal": {
        "regions": ["Al'Har City", "Upland Liberation Front Territory", "Northern Jungle",
                    "Southern Plateau", "Korun Highlands", "Eastern Volcano Range",
                    "Western Jungle Lowlands"],
        "cities":  ["Al'Har", "Korunnai Village", "Highlands Outpost"],
    },
    "Belsavis": {
        "regions": ["Belsavis Vault", "Esh-kha Territories", "Rakata Prison Complex",
                    "Frozen Wastes", "Geothermal Rift", "Tropical Jungle Pockets",
                    "Old Vault Ruins", "Imperial Prison Sector"],
        "cities":  ["Belsavis Prison", "The Vault", "Rakata Prison"],
    },
    "Wayland": {
        "regions": ["Mount Tantiss", "Northern Forests", "Myneyrshi Territory",
                    "Southern Wilds", "Eastern Settlements", "Imperial Storehouse",
                    "Psadan Lowlands"],
        "cities":  ["Mount Tantiss", "Wayland Capital", "Imperial Storehouse"],
    },
    "Despayre": {
        "regions": ["Despayre Prison Colony", "Northern Jungles", "Southern Territories",
                    "Eastern Reaches", "Western Wilds", "Imperial Garrison Zone"],
        "cities":  ["Despayre Prison", "Imperial Garrison", "Death Star Construction Site"],
    },
    "Kalee": {
        "regions": ["Kaleesh Settlement", "Grievous Homeland", "Northern Mountains",
                    "Southern Jungles", "Eastern Coast", "Western Wilderness",
                    "Sacred Lands"],
        "cities":  ["Kaleesh Capital", "Grievous's Homestead", "Sacred Lands"],
    },
    "Yaga Minor": {
        "regions": ["Yaga Minor Shipyards", "Northern Settlement Zone", "Southern Territories",
                    "Eastern Reaches", "Imperial Drydocks", "Outer Defence Ring"],
        "cities":  ["Yaga Minor Drydocks", "Imperial Naval Base"],
    },
    "Colla IV": {
        "regions": ["Colla Prime", "Colicoid Manufacturing Complex", "Southern Jungles",
                    "Northern Wastes", "Eastern Hive Cities", "Western Larval Grounds"],
        "cities":  ["Colla Prime", "Colicoid Hive", "Manufacturing Complex"],
    },
    "Umbara": {
        "regions": ["Umbara City", "Umbaran Militia Territory", "Northern Shadow Forests",
                    "Southern Trenches", "Eastern Umbaran Lines", "Western Phosphorus Plains",
                    "Shadowed Highlands"],
        "cities":  ["Umbara City", "Shadow Forest Capital", "Phosphorus Refinery"],
    },
    "Lehon": {  # Rakata Prime
        "regions": ["Temple of the Ancients", "Rakata Southern Jungles", "Elder Territories",
                    "Eastern Coast", "Northern Wilderness", "Western Beaches"],
        "cities":  ["Temple of the Ancients", "Rakatan Spire", "Elder Settlement"],
    },
    "Mon Cala": {   # alt spelling
        "regions": ["Coral City Region", "Mon Cala Capital", "Calamari Reef",
                    "Quarren Depths"],
        "cities":  ["Coral City", "Heurkea"],
    },
    "Anoat": {
        "regions": ["Anoat City", "Uprising Territories", "Northern Wasteland",
                    "Southern Industrial District", "Eastern Refinery Zone", "Polluted Plains"],
        "cities":  ["Anoat City", "Refinery District"],
    },
    "Terminus": {
        "regions": ["Terminus Port", "Eastern Trade District", "Northern Highlands",
                    "Southern Plains", "Western Reach", "Outer Trade Routes"],
        "cities":  ["Terminus Port", "Trader's Crossroads"],
    },
    "Manpha": {
        "regions": ["Manpha Capital", "Northern Reaches", "Southern Plains",
                    "Eastern Territories", "Western Coast"],
        "cities":  ["Manpha City", "Manpha Spaceport"],
    },
    "Queyta": {
        "regions": ["Queyta Capital", "Northern Territories", "Southern Regions",
                    "Eastern Plains", "Western Coast"],
        "cities":  ["Queyta City"],
    },
    "Maridun": {
        "regions": ["Maridun Plains", "Aleena Settlement", "Northern Steppes",
                    "Southern Grasslands", "Lurmen Village", "Eastern Plains"],
        "cities":  ["Aleena Settlement", "Lurmen Village", "Maridun Capital"],
    },
    "Jabiim": {
        "regions": ["Shelter", "Cobalt Station", "Northern Plateaus", "Endless Mud Flats",
                    "Separatist Stronghold", "Republic Beachhead", "Eastern Mining Camps"],
        "cities":  ["Shelter", "Cobalt Station", "Cobalt Cliffs"],
    },
    "Garqi": {
        "regions": ["Pesktda", "Agri-Farming Plains", "Northern Forests",
                    "Eastern Reaches", "Western Settlement", "Southern Croplands"],
        "cities":  ["Pesktda", "Garqi Farms", "Garqi Spaceport"],
    },
    "Agamar": {
        "regions": ["Calna Muun", "Northern Plains", "Southern Highlands",
                    "Eastern Forests", "Western Reaches", "Rebel Outpost"],
        "cities":  ["Calna Muun", "Agamar Rebel Base"],
    },
    "Dorin": {
        "regions": ["Dorin City", "Northern Gas Fields", "Southern Settlements",
                    "Eastern Atmospheric Zone", "Kel Dor Highlands", "Western Storm Belt"],
        "cities":  ["Dorin Capital", "Kel Dor Settlement"],
    },
    "Dubrillion": {
        "regions": ["Dubrillion Station", "Northern Reaches", "Southern Settlement",
                    "Eastern Territories", "Western Coast", "Outer Trade Post"],
        "cities":  ["Dubrillion Spaceport", "Lando's Folly"],
    },
    "Rishi": {
        "regions": ["Rishi Maze", "Northern Beaches", "Southern Reefs", "Eastern Cliffs",
                    "Western Pirate Cove", "Outer Smuggler's Hideouts"],
        "cities":  ["Rishi Pirate Town", "Rishi Trade Post"],
    },
    "Hypori": {
        "regions": ["Hypori Capital", "Northern Wastes", "Southern Plains", "Eastern Mining",
                    "Western Territories", "Geonosian Forge"],
        "cities":  ["Hypori Capital", "Geonosian Forge"],
    },
    "Teth": {
        "regions": ["B'omarr Monastery", "Western Jungles", "Eastern Cliffside",
                    "Castle Ruins", "Lower River Basin", "Northern Cliff Pass",
                    "Hutt Stronghold"],
        "cities":  ["B'omarr Monastery", "Hutt Stronghold", "Teth Spaceport"],
    },
    "Shola": {
        "regions": ["Shola Capital", "Northern Plains", "Eastern Reaches", "Southern Territories",
                    "Western Highlands"],
        "cities":  ["Shola City", "Shola Port"],
    },
    "Nimban": {
        "regions": ["Nimban Capital", "Northern Plains", "Southern Territories",
                    "Eastern Steppes", "Western Reach", "Hutt Holdings"],
        "cities":  ["Nimban City", "Hutt Outpost"],
    },
    "Rothana": {
        "regions": ["Rothana Heavy Engineering", "Northern Industrial Zone", "Southern Steppes",
                    "Western Sea", "Eastern Plains", "Kaminoan Outpost"],
        "cities":  ["Rothana Engineering HQ", "Kaminoan Outpost"],
    },
    "Kamino": {
        "regions": ["Tipoca City", "Northern Ocean", "Southern Storm Zone",
                    "Eastern Platform Ring", "Clone Training Grounds", "Western Cloning Facility",
                    "Deep Ocean Trench"],
        "cities":  ["Tipoca City", "Clone Barracks", "Kamino Capital"],
    },
    "Bracca": {
        "regions": ["Bracca Shipbreaking Yards", "Northern Wasteland", "Southern Territories",
                    "Eastern Reaches", "Western Hulks", "Scrappers' Slum"],
        "cities":  ["Bracca Scrap Town", "Scrappers' Slum"],
    },
    "Raxus Prime": {
        "regions": ["Raxus Prime Junkyard", "Junk Citadel", "Northern Waste Fields",
                    "Southern Territories", "Eastern Scrapfields", "Imperial Salvage Zone"],
        "cities":  ["Junk Citadel", "Raxus Prime Junkyard"],
    },
    "Raxus": {
        "regions": ["Raxus City", "Separatist Senate District", "Junk Wasteland",
                    "Northern Territories", "Eastern Scrap Regions", "Western Diplomatic Quarter"],
        "cities":  ["Raxus Secundus", "Separatist Senate"],
    },
    "Karfeddion": {
        "regions": ["Karfeddion City", "Northern Territories", "Southern Reaches",
                    "Eastern Plains", "Western Coast", "Outer Settlement"],
        "cities":  ["Karfeddion City"],
    },
    "Farstine": {
        "regions": ["Farstine Station", "Northern Steppes", "Southern Reaches",
                    "Eastern Mining Claims", "Western Coast"],
        "cities":  ["Farstine Station"],
    },
    "Alzoc III": {
        "regions": ["Alzoc Frozen Plains", "Talz Settlement", "Northern Ice Fields",
                    "Southern Mountains", "Eastern Glacier", "Aurorae Caves"],
        "cities":  ["Talz Settlement", "Alzoc Trade Post"],
    },
    "Ord Cestus": {
        "regions": ["Ord Cestus City", "JK-Series Factory", "Northern Territories",
                    "Southern Reaches", "Eastern Mining Zone", "X'Ting Hives"],
        "cities":  ["Ord Cestus Capital", "JK-Series Factory", "X'Ting Hive"],
    },
    "Reltooine": {
        "regions": ["Reltooine Capital", "Northern Plains", "Southern Territories",
                    "Eastern Coast", "Western Settlement"],
        "cities":  ["Reltooine City"],
    },
    "Malachor V": {
        "regions": ["Malachor V Surface", "Trayus Academy", "Northern Wasteland",
                    "Southern Pit", "Eastern Cliffs"],
        "cities":  ["Trayus Academy", "Malachor Pit"],
    },
    "Yavin IV": {
        "regions": ["Massassi Temple", "Northern Jungle", "Southern Jungle",
                    "Eastern Wilderness", "Western Coast"],
        "cities":  ["Massassi Temple", "Yavin Rebel Base"],
    },
    "Hapes": {
        "regions": ["Hapes Capital", "Northern Plains", "Eastern Highlands",
                    "Southern Coast", "Western Settlements"],
        "cities":  ["Hapan Royal Court", "Hapes Spaceport"],
    },

    # ── Unknown Regions / Chiss ───────────────────────────────────────────
    "Csilla": {
        "regions": ["Csaplar", "CEDF Military Zone", "Unknown Regions Buffer",
                    "Northern Ice Plains", "Southern Outposts", "Eastern Glaciers",
                    "Chiss Ascendancy Capital"],
        "cities":  ["Csaplar", "Chiss Capital", "CEDF Headquarters"],
    },
    "Copero": {
        "regions": ["Copero City", "Northern Territories", "Southern Reaches",
                    "Eastern Mountains", "Western Plains"],
        "cities":  ["Copero Capital"],
    },
    "Csaus": {
        "regions": ["Csaus City", "Northern Territories", "Southern Reaches",
                    "Eastern Plains"],
        "cities":  ["Csaus Capital"],
    },
    "Cioral": {
        "regions": ["Cioral City", "Northern Territories", "Southern Reaches",
                    "Eastern Plains", "Western Coast"],
        "cities":  ["Cioral Capital"],
    },
    "Ilum": {
        "regions": ["Ilum Crystal Cave", "Jedi Temple Ruins", "Northern Ice Fields",
                    "Southern Mountains", "Eastern Glacier", "Sacred Crystal Caverns"],
        "cities":  ["Ilum Jedi Temple", "Crystal Cave Entrance"],
    },
    "Jedha": {
        "regions": ["NiJedha City", "Holy Lands", "Jedha Desert Wastes",
                    "Northern Mountains", "Eastern Territory", "Kyber Mining Sites",
                    "Pilgrim Roads"],
        "cities":  ["NiJedha", "Holy City", "Kyber Mines"],
    },
    "Lianna": {
        "regions": ["Lianna City", "Sienar Fleet Systems Complex", "Northern Territories",
                    "Southern Settlement", "Eastern Manufacturing Hub", "Western Reach"],
        "cities":  ["Lianna City", "Sienar Fleet Systems HQ"],
    },
    "Celanon": {
        "regions": ["Celanon City", "Northern Trade District", "Southern Settlement",
                    "Eastern Territories", "Western Commercial Hub"],
        "cities":  ["Celanon Spaceport", "Trade Plaza"],
    },
    "Etti IV": {
        "regions": ["Etti City", "Corporate Sector Headquarters", "Northern Settlement",
                    "Southern Commerce District", "Eastern Resort Coast"],
        "cities":  ["Etti City", "CSA Headquarters", "Etti Resort"],
    },
    "Bonadan": {
        "regions": ["Bonadan City", "Corporate Sector Authority Zone", "Northern Industrial",
                    "Eastern Mining Fields", "Southern Refinery", "Western Spaceport"],
        "cities":  ["Bonadan", "CSA Refinery", "Bonadan Spaceport"],
    },
    "Bonadan IV": {
        "regions": ["Bonadan IV City", "Northern Territories"],
        "cities":  ["Bonadan IV"],
    },

    # ── Smaller / less-documented ─────────────────────────────────────────
    "Ghorman": {
        "regions": ["Ghorman City", "Northern Plains", "Southern Territories",
                    "Eastern Settlement Zone", "Western Industrial Belt", "Coastal Reach"],
        "cities":  ["Ghorman City", "Massacre Plaza"],
    },
    "Balmorra": {
        "regions": ["Bin Prime Sector", "Sobrik Sector", "TUOEE Zone", "Northern Industrial",
                    "Southern Settlement", "Eastern Reaches"],
        "cities":  ["Bin Prime", "Sobrik", "Balmorra Arms Factory"],
    },
    "Axxila": {
        "regions": ["Axxila City", "Northern Territories", "Southern Reaches",
                    "Eastern Plains", "Western Coast"],
        "cities":  ["Axxila Spaceport"],
    },
    "Serenno": {
        "regions": ["Carannia", "Dooku's Palace Grounds", "Northern Mountains",
                    "Southern Valleys", "Eastern Territories", "Western Estates",
                    "Noble Highlands"],
        "cities":  ["Carannia", "Dooku's Palace", "Serenno Royal Court"],
    },
    "Neimodia": {
        "regions": ["Neimodia City", "Northern Settlement", "Southern Territories",
                    "Eastern Mining Zone", "Western Trade Hub"],
        "cities":  ["Neimodia Capital", "Trade Federation HQ"],
    },
    "Sleheyron": {
        "regions": ["Sleheyron Capital", "Hutt Slave Markets", "Northern Plains",
                    "Eastern Reaches", "Southern Volcanic Zone"],
        "cities":  ["Sleheyron Capital", "Slave Market"],
    },
    "Corsin": {
        "regions": ["Corsin City", "Northern Territories", "Southern Reaches"],
        "cities":  ["Corsin City"],
    },
    "Ruuria": {
        "regions": ["Ruuria City", "Northern Territories", "Southern Reaches",
                    "Eastern Plains"],
        "cities":  ["Ruuria Capital"],
    },
    "Mykr": {
        "regions": ["Mykr Capital", "Northern Plains", "Southern Forest"],
        "cities":  ["Mykr Spaceport", "Ysalamiri Reserve"],
    },
    "Taris": {
        "regions": ["Taris Restoration Zone", "Upper City Ruins", "Undercity",
                    "Rakghoul Territories", "Northern Settlement", "Southern Reconstruction"],
        "cities":  ["Taris Capital", "Upper City", "Undercity"],
    },
    "Celegia": {
        "regions": ["Celegia City", "Northern Reaches", "Southern Plains", "Eastern Territories",
                    "Western Frontier"],
        "cities":  ["Celegia Capital"],
    },
    "Bakura": {
        "regions": ["Salis D'aar", "Northern Plains", "Southern Forest", "Eastern Highlands",
                    "Ssi-ruuvi Incursion Zone", "Western Coast", "Cape Suzu"],
        "cities":  ["Salis D'aar", "Cape Suzu"],
    },
    "Ossus": {
        "regions": ["Jedi Temple", "Ossus Wilderness", "New Ossus Settlements",
                    "Old Ossus Ruins", "Northern Reaches", "Southern Wastelands"],
        "cities":  ["Ossus Jedi Temple", "New Ossus", "Old Ossus Ruins"],
    },
}

# Generic fallback names for planets not in PLANET_LORE
GENERIC_REGION_TEMPLATE = [
    "{p} Capital District", "{p} Northern Province", "{p} Southern Reach",
    "{p} Eastern Territories", "{p} Western Plains", "{p} Coastal Region",
    "{p} Highland Province", "{p} Outer Settlement", "{p} Inland Reach",
    "{p} Frontier Province",
]
GENERIC_CITY_TEMPLATE = [
    "{p} Capital", "New {p}", "{p} Spaceport", "Old {p}", "{p} Outpost",
]

# Keyword → terrain class
NAME_TERRAIN_KEYWORDS: Dict[str, List[str]] = {
    "urban":    ["city", "town", "district", "spaceport", "station", "citadel",
                 "industrial", "manufacturing", "shipyard", "drydock", "factory",
                 "refinery", "foundry", "complex", "yards", "outpost", "capital",
                 "headquarters", "hq", "settlement", "settlements", "port",
                 "fortress", "palace", "temple", "ring", "facility", "depot",
                 "academy", "monastery", "vault", "compound", "village"],
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

# ---------------------------------------------------------------------------
# Parsers (lightweight — we only need to read existing state files)
# ---------------------------------------------------------------------------

@dataclass
class StateInfo:
    state_id: int
    name_key: str
    display_name: str              # from localisation, e.g. "Naboo C"
    planet: str                    # parsed from display, e.g. "Naboo"
    provinces: List[int]
    category: str
    victory_points: List[Tuple[int, int]] = field(default_factory=list)


def load_definition(path: Path) -> Dict[int, Dict]:
    res: Dict[int, Dict] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 7:
                continue
            try:
                res[int(parts[0])] = {
                    "terrain":    parts[6].strip(),
                    "is_coastal": parts[5].strip().lower() == "true",
                }
            except (ValueError, IndexError):
                continue
    return res


def load_centroids() -> Dict[int, Tuple[float, float]]:
    if not CENTROID_CACHE.exists():
        print("  WARNING: centroid cache missing. Run split_states.py once to build it.")
        return {}
    try:
        with open(CENTROID_CACHE, "rb") as f:
            data = pickle.load(f)
        if isinstance(data, tuple):
            return data[0]
        return data
    except Exception as e:
        print(f"  WARNING: failed to load centroids: {e}")
        return {}


def load_localisation() -> Dict[str, str]:
    res: Dict[str, str] = {}
    if not STATE_LOC.exists():
        return res
    for line in STATE_LOC.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"\s*(STATE_\d+):0\s+\"([^\"]*)\"", line)
        if m:
            res[m.group(1)] = m.group(2)
    return res


def parse_state_brief(path: Path) -> Optional[StateInfo]:
    """Parse just what we need for naming: id, name_key, provinces, category, VPs."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    sid_m = re.search(r"\bid\s*=\s*(\d+)", content)
    if not sid_m:
        return None
    state_id = int(sid_m.group(1))
    name_m = re.search(r'\bname\s*=\s*"([^"]+)"', content)
    prov_m = re.search(r"provinces\s*=\s*\{([^}]*)\}", content, re.DOTALL)
    cat_m  = re.search(r"\bstate_category\s*=\s*(\w+)", content)
    provinces = [int(x) for x in prov_m.group(1).split()] if prov_m else []
    vps: List[Tuple[int, int]] = []
    for vp_m in re.finditer(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", content):
        vps.append((int(vp_m.group(1)), int(vp_m.group(2))))
    return StateInfo(
        state_id=state_id,
        name_key=name_m.group(1) if name_m else f"STATE_{state_id}",
        display_name="",
        planet="",
        provinces=provinces,
        category=cat_m.group(1) if cat_m else "wasteland_sector",
        victory_points=vps,
    )


def derive_planet_name(display_name: str) -> str:
    """Strip trailing ' A'..' Z' or ' - <whatever>' to get the parent planet name."""
    # Trailing single letter (e.g. "Naboo C")
    m = re.match(r"^(.*?)\s+[A-Z]$", display_name)
    if m:
        return m.group(1).strip()
    # Hyphenated descriptors (e.g. "Kashyyyk - Shadowlands")
    m = re.match(r"^([^-]+?)\s*-\s+.+$", display_name)
    if m:
        return m.group(1).strip()
    return display_name.strip()

# ---------------------------------------------------------------------------
# Semantic matching
# ---------------------------------------------------------------------------

def dominant_terrain(provinces: List[int], lookup: Dict) -> str:
    counts: Dict[str, int] = defaultdict(int)
    for p in provinces:
        counts[lookup.get(p, {}).get("terrain", "unknown")] += 1
    return max(counts, key=lambda k: counts[k]) if counts else "unknown"


def state_center(provinces: List[int], centroids: Dict[int, Tuple[float, float]]
                 ) -> Tuple[float, float]:
    xs, ys = [], []
    for p in provinces:
        if p in centroids:
            xs.append(centroids[p][0])
            ys.append(centroids[p][1])
    return (sum(xs) / len(xs), sum(ys) / len(ys)) if xs else (0.0, 0.0)


def parse_name_hints(name: str) -> Tuple[Optional[str], Optional[str]]:
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


def state_directions(center: Tuple[float, float],
                     planet_center: Tuple[float, float],
                     spread: float) -> Set[str]:
    dx = center[0] - planet_center[0]
    dy = center[1] - planet_center[1]
    threshold = spread * 0.15
    dirs: Set[str] = set()
    if dy < -threshold: dirs.add("north")
    if dy >  threshold: dirs.add("south")
    if dx >  threshold: dirs.add("east")
    if dx < -threshold: dirs.add("west")
    return dirs


def match_names_to_states(
    names: List[str],
    states: List[StateInfo],
    terrains: Dict[int, str],
    centers: Dict[int, Tuple[float, float]],
) -> Dict[int, str]:
    """Greedy bipartite matching: each state → best-fitting name."""
    if not states:
        return {}
    n = len(states)
    # Planet centre & spread for direction calc
    xs = [c[0] for c in centers.values()]
    ys = [c[1] for c in centers.values()]
    pc = (sum(xs)/len(xs), sum(ys)/len(ys)) if xs else (0.0, 0.0)
    spread = max(1.0, max((c[0]-pc[0])**2 + (c[1]-pc[1])**2 for c in centers.values()) ** 0.5)

    dirs = {s.state_id: state_directions(centers[s.state_id], pc, spread) for s in states}

    # Score every (name, state) pair
    pairs: List[Tuple[float, int, int]] = []  # (score, name_idx, state_idx)
    for ni, name in enumerate(names):
        t_hint, d_hint = parse_name_hints(name)
        is_capital_name = (ni == 0)
        for si, st in enumerate(states):
            score = 0.0
            terrain = terrains[st.state_id]
            if t_hint:
                if t_hint == terrain:
                    score += 10.0
                elif terrain in TERRAIN_SIMILAR.get(t_hint, set()):
                    score += 4.0
            if d_hint and d_hint in dirs[st.state_id]:
                score += 8.0
            # Strongly bias the first lore name (canonical capital) → capital_sector
            if is_capital_name and st.category == "capital_sector":
                score += 25.0   # overwhelming: capital name MUST land on capital state
            if is_capital_name and terrain == "urban":
                score += 4.0
            pairs.append((score, ni, si))

    pairs.sort(key=lambda p: -p[0])
    assigned: Dict[int, str] = {}
    used_n: Set[int] = set()
    used_s: Set[int] = set()
    for score, ni, si in pairs:
        if score <= 0:
            break
        if ni in used_n or si in used_s:
            continue
        assigned[states[si].state_id] = names[ni]
        used_n.add(ni)
        used_s.add(si)

    # Leftover states get leftover names in order
    leftover_names = [names[i] for i in range(min(len(names), n)) if i not in used_n]
    leftover_states = [s for i, s in enumerate(states) if i not in used_s]
    for nm, st in zip(leftover_names, leftover_states):
        assigned[st.state_id] = nm

    # Final fallback for any state still nameless
    for st in states:
        if st.state_id not in assigned:
            assigned[st.state_id] = st.display_name or f"STATE_{st.state_id}"

    return assigned


def assign_cities_to_vps(
    cities: List[str],
    states: List[StateInfo],
    matched_state_names: Dict[int, str],
) -> List[Tuple[int, str]]:
    """Return list of (province_id, city_name) for every VP across this planet.
    Canonical cities are spent first (highest-priority state's biggest VP wins),
    then secondary VPs fall back to '<state region name> Settlement / Outpost'.
    """
    rank = {"capital_sector": 0, "economic_sector": 1, "industrial_sector": 2,
            "agricultural_sector": 3, "wasteland_sector": 4}
    states_sorted = sorted(states,
                           key=lambda s: (rank.get(s.category, 5),
                                          -sum(v for _, v in s.victory_points)))
    suffixes = ["Settlement", "Outpost", "Port", "Town", "Crossing", "Hold", "Reach"]
    vp_assignments: List[Tuple[int, str]] = []
    city_idx = 0
    fallback_idx = 0
    for st in states_sorted:
        region = matched_state_names.get(st.state_id, st.display_name)
        sorted_vps = sorted(st.victory_points, key=lambda x: -x[1])
        for prov, _val in sorted_vps:
            if city_idx < len(cities):
                vp_assignments.append((prov, cities[city_idx]))
                city_idx += 1
            else:
                # Derive from the matched region name + a rotating suffix
                suf = suffixes[fallback_idx % len(suffixes)]
                # Strip trailing "District", "Province", etc. for cleaner concat
                base = re.sub(r"\s+(District|Province|Region|Sector|Territories?|Zone|Reach(es)?|Lands)$",
                              "", region)
                vp_assignments.append((prov, f"{base} {suf}"))
                fallback_idx += 1
    return vp_assignments

# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_state_loc(new_names: Dict[int, str], state_keys: Dict[int, str]) -> None:
    """In-place update of state_names_l_english.yml."""
    if not STATE_LOC.exists():
        print(f"  WARNING: {STATE_LOC} not found.")
        return
    content = STATE_LOC.read_text(encoding="utf-8-sig")
    lines = content.splitlines()
    updated = []
    seen_keys: Set[str] = set()
    for line in lines:
        m = re.match(r"(\s*)(STATE_\d+):0\s+\"([^\"]*)\"", line)
        if m:
            key = m.group(2)
            sid = int(key.split("_")[1])
            if sid in new_names:
                updated.append(f' {key}:0 "{new_names[sid]}"')
                seen_keys.add(key)
                continue
        updated.append(line)
    # Add any new-name entries that weren't already in the file
    for sid, name in new_names.items():
        key = state_keys.get(sid, f"STATE_{sid}")
        if key not in seen_keys:
            updated.append(f' {key}:0 "{name}"')
    STATE_LOC.write_text("\n".join(updated) + "\n", encoding="utf-8-sig")


def write_vp_loc(vp_assignments: List[Tuple[int, str]]) -> None:
    """Write/overwrite victory_points_l_english.yml."""
    lines = ["l_english:"]
    for prov, name in sorted(vp_assignments):
        # HOI4 VP localisation key: VICTORY_POINTS_<prov>
        lines.append(f' VICTORY_POINTS_{prov}:0 "{name}"')
    VP_LOC.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def write_prov_loc(vp_assignments: List[Tuple[int, str]]) -> None:
    """Write/overwrite provinces_l_english.yml — same names, in case the
    mod prefers the PROV_<id> key style. Harmless if unused."""
    lines = ["l_english:"]
    for prov, name in sorted(vp_assignments):
        lines.append(f' PROV_{prov}:0 "{name}"')
    PROV_LOC.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only",    type=str, default="",
                    help="Comma-separated planet names to process (e.g. Naboo,Ryloth)")
    args = ap.parse_args()

    only_planets: Optional[Set[str]] = None
    if args.only:
        only_planets = {p.strip() for p in args.only.split(",") if p.strip()}

    print("Loading definition.csv...")
    terrain_lookup = load_definition(DEF_CSV)
    print("Loading centroid cache...")
    centroids = load_centroids()
    print(f"  {len(centroids):,} centroids.")
    print("Loading state_names_l_english.yml...")
    loc = load_localisation()

    print("Parsing state files...")
    by_planet: Dict[str, List[StateInfo]] = defaultdict(list)
    state_keys: Dict[int, str] = {}
    for path in sorted(STATES_DIR.glob("*.txt")):
        info = parse_state_brief(path)
        if not info or not info.provinces:
            continue
        info.display_name = loc.get(info.name_key, info.name_key)
        info.planet = derive_planet_name(info.display_name)
        if only_planets and info.planet not in only_planets:
            continue
        by_planet[info.planet].append(info)
        state_keys[info.state_id] = info.name_key

    if not by_planet:
        print("Nothing to process.")
        return

    print(f"\n{len(by_planet)} planet groups, {sum(len(v) for v in by_planet.values())} states total.\n")

    all_new_names: Dict[int, str] = {}
    all_vp_names: List[Tuple[int, str]] = []
    summary_lore = 0
    summary_generic = 0

    for planet, states in sorted(by_planet.items()):
        if len(states) < 1:
            continue

        # Pull lore lists (with generic fallback)
        lore = PLANET_LORE.get(planet)
        if lore:
            regions = lore["regions"]
            cities  = lore.get("cities", [])
            summary_lore += 1
        else:
            regions = [tpl.format(p=planet) for tpl in GENERIC_REGION_TEMPLATE]
            cities  = [tpl.format(p=planet) for tpl in GENERIC_CITY_TEMPLATE]
            summary_generic += 1

        # Compute per-state terrain + centre
        terrains = {s.state_id: dominant_terrain(s.provinces, terrain_lookup) for s in states}
        centers  = {s.state_id: state_center(s.provinces, centroids) for s in states}

        # Match region names → states
        matched = match_names_to_states(regions, states, terrains, centers)

        # Match cities → VPs (uses matched state names for fallback labels)
        vp_assignments = assign_cities_to_vps(cities, states, matched)

        # Report
        print(f"{planet} ({len(states)} states, "
              f"{sum(len(s.victory_points) for s in states)} VPs)"
              f"{' [LORE]' if lore else ' [generic]'}:")
        for s in sorted(states, key=lambda x: x.state_id):
            nm = matched.get(s.state_id, "?")
            print(f"  {s.state_id:>4}  was '{s.display_name}' → '{nm}'  [{s.category}]")
        for prov, cname in vp_assignments:
            print(f"        VP prov {prov:>5} → '{cname}'")

        all_new_names.update(matched)
        all_vp_names.extend(vp_assignments)
        print()

    print(f"Touched {len(by_planet)} planet groups "
          f"({summary_lore} with lore, {summary_generic} generic).")
    print(f"  {len(all_new_names)} states renamed, {len(all_vp_names)} VPs labelled.")

    if args.dry_run:
        print("\n[dry-run] No files were written.")
        return

    print("\nWriting state_names_l_english.yml...")
    write_state_loc(all_new_names, state_keys)
    print(f"Writing {VP_LOC.name}...")
    write_vp_loc(all_vp_names)
    print(f"Writing {PROV_LOC.name}...")
    write_prov_loc(all_vp_names)
    print("Done.")


if __name__ == "__main__":
    main()
