# Cantonica build log (2026-10-14)
- 23:19:02 start
- 23:19:16 research 10s
- 23:19:43 research --gaps

## Visual references (viewed in Chrome, 2026-10-14)
- Canto_Bight_TLJ.png / CantoCasino-CGSWG.png (TLJ): the Canto Casino: a tall pale cylinder ringed by 2-3 wide dark slate saucer roofs stacked upward, mast on top; round plaza with a statue in front; the oval fathier racetrack (tiered stands) behind it; smaller domed round buildings around; city backed by dark steep mountains.
- CantoBight-SWBC49.png: the city fills a bay between two steep mountain ridges, Mediterranean old town of pale stone blocks climbing the slopes, the casino tower in the middle; pink/purple dusk sky.
- CantonicaSea.png (comic): the casino from above the sea: deep blue sea, rocky islands, green scrub on the shore.
- CantoCasino-CantoBight-SoH.png: tiered saucer roofs, desert mountains behind, racetrack stands.
- WesthillCliffs-Outlaws.jpg: Westhill Palace: domed mansions on a cliff top over the sea, round landing pad.
- CasinoDistrict-Cantonica-Outlaws.jpg: dense city of pale blocks with domes at night.
- Cantonica_TLJVD.png / storybook: from space the planet is orange-ochre desert with pale sand patches, no visible sea (the sea is small on a planetary scale).

## User decisions (2026-10-14)
- --allow-dirty approved for Cantonica.
- Era: Canto Bight present + ancient ruins, and the ruins are ANCIENT SITH ruins (design choice, not canon).
- Layout as proposed: bay city between two ridges on the Sea of Cantonica (~15%), Westhill cliffs, desert/mesas/mountains, ruins inland; ~45/19.
- Models: city sets + ruins, Westhill Palace. (Casino tower / racetrack not picked.)
- City reference (user): Star Wars Outlaws "Incredible view" (escapistmagazine 2024/08): Canto Bight from the sea: a quay wall along the water; a dense lower town of low pale-stone blocks with flat/low-pitched slate roofs and scattered round drum buildings with wide shallow slate saucer domes and a warm window band; above it a huge buttressed retaining wall; the upper casino town behind it, taller, domes, warm orange light; the casino at the top with searchlights; dark mountains around.
- Building reference (user): TLJ still (cloudfront 5987cd390b2c4ce9): round drum building of pale beige stone with vertical pilaster buttresses, a recessed window band (warm lit), a slate dome cap with a lip, a ring balcony with railings, a round slate-domed pavilion beside it. Used for Westhill Palace and the city's drum buildings.

## Build (2026-10-14)
- cantonica_map.py (copy of dromund_kaas_map.py's code + Cantonica data): 64 ids kept, 44 passable / 20 impassable,
  11 states (8 old + new impassable 1165 Sea of Cantonica, 1166 Cantonican Highlands, 1167 Southern Badlands), owner CSA,
  port in 741 South Stretch (rim coast). Sea drawn as lobes + a bay to the quay (no round shapes).
- Terrain: TERRAIN_CFG; new graphical terrain desert_town_32 (sand that spawns city models) for the Sith ruins.
- Cities: map/cities.txt 17 = hod_cant_city (Canto Bight + South Stretch), 18 = hod_cant_sith_ruin.
- Models: hod_cant_westhill (rot -45 deg: faces SW to the sea), atlas hod_cantonica (military_buildings cantonica_atlas).
- Flora 88 canto_chinar, 89 canto_cactus, 90 canto_scrub, 91 canto_rubble (flora_props; PLANET_SOLID textures).
- Validate: 0 errors, 0 warnings. Previews: WIPGFX/research/previews/cantonica_*.png
- Not done (not chosen by the user): Canto Casino tower, racetrack, FX (purple sea glow).
