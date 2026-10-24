# Korriban: research notes and build plan (2026-10-12)

Plan image: `korriban idea.png` (repo root), pixel-aligned with the planet: OFFSET (row, col) = (460, 2135), 11299 px,
same count as the planet mask. Colours: red (255,42,0) = Sith tombs and antechambers, blue (127,150,255) = valleys
and open areas (main N-S Valley of the Dark Lords + side valleys), green (0,255,38) = academy city (NW), white =
impassable red rock mountains. Outlines only (1 px), like felucia map.png: flood-fill the enclosed areas.

Planet: 208 provinces, states 90 (capital, owner CMG, capital_sector, naval base 1533) + 779-785 (CMG, wasteland).
Old landmark hod_korriban_valley (military_buildings.py LANDMARKS, province 1594) to be replaced.

## Names (Wookieepedia, canon + Legends)
- Cities: Dreshdae (capital, spaceport: Dreshdae Spaceport, Korriban Arrival Port), Kaniset, Vardin.
- Academy area: Sith Academy (pyramid at the valley's back wall), Dark Council Chambers.
- Valleys / open places: Valley of the Dark Lords (once the Valley of the Sleeping Kings), Valley of Golg, Lower Wilds,
  Eternal Pyre, Hall of Judgment, Chambers of Persuasion, Shyrack cave, Lord Khreusis's stronghold, Sorzus Syn's
  throne, Mongrel Altar, Sith Citadel, Wilds Laboratory.
- Tombs: Ajunta Pall, Tulak Hord, Marka Ragnos, Naga Sadow, Ludo Kressh, XoXaan (+ XoXaan's Temple), Hakagram Graush,
  Dathka Graush, Din Grrut, Darth Bane, Crassus, Sanctum of Sakkra-Kla, Cloister of Bilious Torment, Great Temple.
  Canon (Moraband): Sith temple with twin hooded statues.

## Visual language (30+ reference images: KOTOR, TOR, TCW, comics)
- Sheer smoothed red-ochre canyon walls; red-orange dusty haze.
- Giant hooded robed Sith statues (arms crossed) lining the valley; colossal half-buried stone heads; broken statues.
- Obelisks / monoliths with glyph bands; ruined columns.
- Tomb facades cut into cliffs: stepped, glyph relief bands, statues in niches, dark doorways, stairs.
- Marka Ragnos: giant horned seated statue, stair leading into it. Ajunta Pall: tall mausoleum, obelisks in front.
- Sith Academy / Great Temple (TOR): great pyramid with a dark central spire and a band of lights, red banners with
  the Sith Empire emblem.
- Moraband (TCW): mountains as a field of razor-sharp pyramidal spires.
- Dreshdae (KOTOR, comics): round metal domed buildings, antennas, dishes, on a mesa.
- Fan render idea: tomb fused with a colossus statue.

## Build plan
1. korriban_map.py (felucia_map.py pattern): provinces from the plan, ids kept; tombs = provinces/states with canon
   tomb VPs; valley states; academy capital state; impassable mountain states (new ids); definition terrain.
2. planet_terrain_gen.py --korriban: canyon floors, sheer walls, needle-spire mountains, tomb forecourts, academy mesa;
   keep the original globe (GLOBE_TERRAIN_KEEP).
3. Models: hod_korriban atlas (carved red stone + glyph bands, statue stone, dark doors, banner with Sith emblem,
   light band); landmarks (academy pyramid, tomb facades x several, Ragnos colossus, twin-statue temple), statue rows
   along the valley walls (ambient objects), Dreshdae city style 13, props (spires, obelisks, fallen statues, heads,
   rubble).
