# Hearts of Durasteel: 3D model catalogue

Every 3D model the mod has, what it is used for now, and palettes to pick from for future planets.
Sizes are map units at scale 1 (width x depth x height; a province is ~8 px = 8 units; vanilla factories are ~2 across).
Pictures: `landmarks.png`, `buildings.png`, `cities.png`, `flora.png` (game-ready models), `sources_empire_at_war.png`,
`sources_raxus_prime_ships.png` (converted sources, not all in the game yet). Leaf / junk cards show as dark squares in
the previews: the game cuts them out.

How models get into the game:

| Kind | Placed by | Made / registered by |
|---|---|---|
| Landmark (one-off, big) | `map/ambient_object.txt` | `military_buildings.py models` + `landmarks`, `raxus_prime_map.py` (wrecks) |
| Building (vanilla building slot) | `gfx/entities/buildings.asset` | `military_buildings.py wire` (EAW_BUILDINGS) |
| City style (city models by `cities.bmp` index) | `map/cities.txt` | `coruscant_buildings.py wire` (CITY_GROUPS) |
| Map prop (trees, rocks, wrecks, junk) | `map/trees.bmp` palette index | `flora_props.py wire` (`gfx/entities/trees.gfx`) |
| Imported model (Sketchfab .gltf, Battlefront / EaW .msh) | any of the above | `msh_to_glb.py` (.msh -> .glb), then `sketchfab_props.py bake` + `textures` (SPECS) |

---

## 1. Landmarks (`gfx/models/buildings/hod_landmarks`, `hod_sw`, `hod_launchpad`)

| Model | Size | Now used for | Source |
|---|---|---|---|
| hod_jedi_temple | 3.5 x 4.3 x 5.6 | Coruscant: Jedi Temple | procedural |
| hod_senate | 4.1 x 4.1 x 3.8 | Coruscant: Galactic Senate | procedural |
| hod_raxus_senate | 23.8 x 24.3 x 27.5 | Raxus: Separatist Senate (map scale) | procedural |
| hod_cis_banner | 0.8 x 0.2 x 4.1 | Raxulon's Great Alley | procedural |
| hod_tipoca | 3.8 x 3.9 x 4.7 | Kamino: Tipoca City | procedural |
| hod_petranaki_arena | 4.8 x 3.2 x 4.9 | Geonosis: Petranaki Arena | procedural |
| hod_stalgasin_hive | 4.1 x 4.2 x 5.8 | Geonosis: Stalgasin hive | procedural |
| hod_droid_foundry | 4.1 x 4.2 x 5.0 | Geonosis: droid foundry | procedural |
| hod_progate_temple | 3.5 x 3.5 x 5.5 | Geonosis: Progate temple | procedural |
| hod_dooku_hangar | 2.4 x 3.1 x 5.2 | Geonosis: Dooku's hangar | procedural |
| hod_massassi_temple | 4.1 x 4.2 x 5.0 | Yavin IV: Great Temple | procedural |
| hod_jabba_palace | 2.7 x 2.3 x 4.6 | Tatooine: Jabba's palace | procedural |
| hod_sundari_dome | 4.1 x 4.1 x 4.1 | Mandalore: Sundari | procedural |
| hod_theed_palace | 4.0 x 1.5 x 4.2 | Naboo: Theed palace | procedural |
| hod_coronet_port | 3.8 x 2.4 x 5.2 | Corellia: Coronet spaceport | procedural |
| hod_castle_serenno | 3.4 x 2.6 x 4.7 | Serenno: Castle Serenno | procedural |
| hod_korriban_valley | 3.8 x 2.8 x 4.9 | Korriban: Valley of the Dark Lords | procedural |
| hod_ion_cannon | 4.0 x 4.3 x 2.1 | anti-air building (all planets) | procedural |
| hod_spacedock | 3.4 x 5.3 x 1.7 | naval base (all planets) | procedural |
| hod_launchpad | 3.3 x 2.6 x 1.5 | air base (all planets) | procedural |
| hod_bld_rp_factory | 7.5 x 6.4 x 3.9 | Raxus Prime: Sienar Refinery | EaW abandoned factory |
| hod_bld_rp_droidworks | 3.5 x 3.5 x 3.3 | Raxus Prime: droid foundry | EaW droid works |
| hod_bld_rp_derriphan_bow / _stern | 1.3 x 7.0 x 2.0 / 2.8 x 3.1 x 5.3 | Raxus Prime: split battleship wreck | Battlefront II mod (Derriphan) |
| hod_bld_rp_hammerhead_bow / _stern | 2.2 x 1.7 x 4.0 / 2.6 x 5.0 x 1.5 | Raxus Prime: split cruiser wreck | Battlefront II mod (Hammerhead) |
| hod_bld_rp_lethisk | 1.5 x 3.2 x 0.9 | Raxus Prime: crashed freighter | Battlefront II mod (Lethisk) |

## 2. Buildings (`gfx/models/buildings/hod_sw`)

Vanilla building slots now on Empire at War models (`military_buildings.py EAW_BUILDINGS`):

| Vanilla building | Model | Size |
|---|---|---|
| civilian factory | hod_bld_eaw_vehicleFactory | 2.2 x 2.4 x 0.9 |
| arms factory | hod_bld_eaw_lightfactory | 1.6 x 2.2 x 1.2 |
| dockyard (3 levels) | hod_bld_eaw_rebelBarracks (hangar) | 2.0 x 2.4 x 0.6 |
| bunker, coastal bunker | hod_bld_eaw_emplacement | 1.8 x 1.8 x 0.3 |
| fortress network | hod_bld_eaw_prison | 2.2 x 2.6 x 1.0 |
| radar station | hod_bld_eaw_tibannaStation | 0.6 x 0.6 x 1.6 |
| synthetic refinery | hod_bld_eaw_fuelCellC | 2.0 x 1.6 x 0.5 |
| rocket site | hod_bld_eaw_corBuild4 (spire) | 0.4 x 0.6 x 2.4 |
| nuclear reactor (all three), nuclear facility | hod_bld_eaw_researchAcademy | 2.0 x 1.7 x 0.8 |
| supply node | hod_bld_eaw_crates9 | 0.8 x 1.2 x 0.8 |
| naval supply hub | hod_bld_eaw_crates4 | 1.2 x 0.7 x 0.4 |
| naval headquarters | hod_bld_eaw_officerAcademy | 2.0 x 1.4 x 1.4 |
| land facility | hod_bld_eaw_infantrybarracks | 1.9 x 2.2 x 0.8 |
| air facility | hod_bld_eaw_rebelBuilding1 | 2.2 x 1.5 x 0.5 |
| naval facility | hod_bld_eaw_bespinBuilding3 (round platform) | 2.0 x 2.0 x 0.9 |
| electronics facility | hod_bld_eaw_droidworks | 2.2 x 2.2 x 2.1 |
| rocket facility | hod_bld_eaw_corBuild3 (tower) | 0.5 x 0.5 x 2.4 |
| air base, anti-air, naval base | ours: hod_launchpad, hod_ion_cannon, hod_spacedock | (see 1) |

Not in a building slot (free to use):

| Model | Size | Notes |
|---|---|---|
| hod_bld_chr_00 .. _04, _07 | ~1.2 x 1.0 x 1.8 | Christophsis crystal-glass towers (were the factories; still in Christophsis city clusters) |
| hod_bld_jedi_temple | 4.0 x 4.0 x 2.5 | Sketchfab Jedi Temple |
| hod_bld_jasperio | 1.6 x 1.4 x 1.0 | treehouse village (tree-world city style) |
| hod_bld_shield_gen | 1.0 x 1.4 x 1.2 | shield generator dish |
| hod_bld_rpt_* (crates1/4/5/6/9, huttTower, fuelCellC) | 0.6-1.4 | Raxus Prime scrap-town pieces (city style 12) |

## 3. City styles (`map/cities.txt`, index in `cities.bmp`)

| Index | Style | Families | Look |
|---|---|---|---|
| 1 | megacity | hod_cor_cluster (+ 1/3 Christophsis) | Coruscant towers |
| 2 | towns | hod_town | generic low town |
| 3 | Christophsis | hod_chr_cluster | crystal-glass towers |
| 4 | tree worlds | hod_bld_jasperio | treehouse villages |
| 5 | ocean worlds | hod_kam_city | stilt domes (Tipoca in miniature) |
| 6 | Mandalore | hod_man_city | dark domes |
| 7 | Geonosis | hod_geo_city | fluted rock hive spires |
| 8 | Naboo | hod_nab_city | Theed domes, colonnades, campaniles |
| 9 | Felucia natives | hod_fel_city | huts and pods round giant mushrooms |
| 10 | Commerce Guild outposts | hod_cmg_outpost | prefab domes, masts, pads |
| 11 | Raxus | hod_rax_city | sandstone blocks + gothic spires |
| 12 | Raxus Prime | hod_bld_rpt_* | scrap towns of containers and junk |

## 4. Map props (`map/trees.bmp` index -> `gfx/entities/trees.gfx` mapobject_N)

| Index | Model | Size | Look / use |
|---|---|---|---|
| 40 | wroshyr | 5.9 x 5.5 x 6.4 | Kashyyyk giant tree |
| 41 | jungle_giant | 6.3 x 6.3 x 4.8 | umbrella jungle giant |
| 42, 43 | quiver_tree_01/02 | ~1 x 1 x 2 | alien succulent trees (deserts, steppe) |
| 44 | searsia_lucida | 0.9 x 1.0 x 1.1 | bushy shrub-tree (savanna) |
| 45 | othonna_cerarioides | 1.0 x 0.9 x 1.5 | desert succulent |
| 46 | fern_02 | 1.0 x 0.9 x 0.2 | jungle / swamp understory |
| 47 | dead_tree_trunk_02 | 2.4 x 0.5 x 0.6 | fallen trunk (swamps, dead worlds) |
| 48, 49 | moon_rock_01/03 | ~1.5 x 1 x 0.6 | bare rock (barren, lava, ice) |
| 50 | namaqualand_boulder_02 | 2.2 x 1.1 x 0.8 | desert boulder |
| 51 | rock_moss_set_01 | 1.2 x 1.8 x 0.8 | mossy rocks (forest, alpine) |
| 52 | boulder_01 | 0.3 x 0.6 x 0.5 | grey boulder |
| 53 | sandcrawler | 1.0 x 3.0 x 1.4 | Jawa sandcrawler |
| 54 | vaporators | 1.4 x 0.9 x 0.7 | moisture vaporators (Tatooine farms) |
| 55 | homestead | 2.0 x 1.8 x 0.7 | desert homestead domes |
| 56, 57 | wreck_harrower / wreck_foray | ~4.5 long | burnt starship wrecks |
| 58-61 | fel_mushroom / bulbs / pitcher / fronds | 1.5-5 | Felucia giant fungal flora |
| 62, 63 | rax_tree / rax_tiered | 4.1 x 4.1 x 4.3 / 2.7 x 2.3 x 3.4 | Raxus golden-orange trees |
| 64 | rax_shrubs | 2.5 x 1.5 x 0.9 | crimson shrubs |
| 65-68 | rp_wreck_bloodmark / chela / b28 / ebonhawk | 1.4-2.2 | small crashed ships (rusted) |
| 69, 70 | rp_junk_heap / rp_barrels | 1.3-1.8 | EaW junk pile, barrel stack |
| 71, 72 | rp_hull_chunk / rp_wing_chunk | 1.0-1.5 | ship debris |
| 73-78 | rp_heap_a / b / c / ridge / tangle / slabs | ~5 across | junk heaps (merge into a dump) |
| (trains) | hod_train_x34 / xj6 | ~1.2 | supply convoys (speeders) |

## 5. Converted sources not used yet (`WIPGFX/3d/_glb`)

Ready to bake with a `sketchfab_props.py` SPECS entry (see `sources_*.png`):

- **Empire at War** (`_glb/eaw`): alderaanBldg1-3, alderaanBuilding4-5 (white Alderaan spires and domes),
  bespinBuilding1-4 (cloud-city towers and platforms), corBuild1-6 (Coruscant towers, pads, spires), commandcenter* /
  commanderQuarters* / treeCluster1* (*no visible mesh), crates1-10, emplacement, feluciaPlantA-C, fuelCellA,
  huttPalace, huttPalace2, huttTower, imerialPalace (Imperial palace spire), moncalBuilding (fragments only),
  palace (dark tower), rockSpire, rockSpire2, theedPalace, twilekBuilding (Ryloth), abandonedFactory, droidworks.
- **Battlefront II ships** (`_glb/raxus_prime`): Derriphan battleship (+2 chunks), Hammerhead cruiser (+2 chunks),
  Lethisk freighter (+2 chunks), Ebon Hawk, Chela fighter (+chunk), B-28 bomber (+chunk), Bloodmark fighter, Old
  Republic speeder bike.

## 6. Palettes for future planets

| Planet type | Landmark ideas | City style | Props |
|---|---|---|---|
| Desert (Tatooine, Jakku, Geonosis) | huttPalace, huttPalace2, jabba_palace, wrecks (harrower, foray, rp_* ships) | 2 towns or 7 Geonosis | 42, 43, 45, 50, 53, 54, 55, 56, 57 |
| Ecumenopolis (Coruscant) | jedi_temple, senate, imerialPalace, corBuild1-6 | 1 megacity | none |
| Ocean / cloud (Kamino, Bespin) | tipoca, bespinBuilding1-4 | 5 stilt domes | none |
| Royal / garden (Naboo, Alderaan, Raxus) | theed_palace, theedPalace, alderaanBldg1-3 / 4-5 | 8 Naboo, 11 Raxus | 62-64, 44, 51 |
| Jungle / tree (Kashyyyk, Yavin, Felucia) | massassi_temple, kachirho (40), feluciaPlantA-C | 4 treehouse, 9 Felucia | 40, 41, 46, 58-61 |
| Junk / industrial (Raxus Prime, Lotho Minor) | rp_factory, droidworks, abandonedFactory, split ship wrecks | 12 scrap towns | 65-78 |
| Sith / dark (Korriban, Dathomir, Mustafar) | korriban_valley, palace (dark tower), rockSpire 1-2 | 2 towns | 47, 48, 49 |
| Military frontier / outpost (Christophsis, Ryloth) | prison, emplacement, commandcenter*, twilekBuilding | 3 Christophsis, 10 Guild outposts | 52, 71, 72 |
| Mandalore | sundari_dome | 6 Mandalore domes | 48, 49 |
