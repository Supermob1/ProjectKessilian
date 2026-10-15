# Dromund Kaas build log (2026-10-14)
- 19:18:15 start; placeholder confirmed (states 89, 772-778 'Dromund Kaas B..H'; no script/research/assets)
- 19:18:49 research_planet.py 'Dromund Kaas' 26s
- 19:22:34 approvals: --allow-dirty, Clone Wars ruins (Legends), storm-swamp layout, models Citadel + Dark Temple; snapshot 124M in 1s
- 19:23:57 dry run 1 29s
- 19:24:44 dry run 2 (landing moved inward) 29s
- 19:25:21 dry run 3 (base 2 provinces) 30s
- 19:26:04 dry run 4 (landing on the coast) 28s
- 19:26:45 dry run 5 (776 seed east: no sliver) 29s
- 19:31:29 dromund_kaas_map.py --allow-dirty exit=0 275s
- 19:31:36 validate (after map) exit=0: 0 errors, 0 warnings
- 19:31:48 planet_terrain_gen.py --planet 'Dromund Kaas' exit=0 2s
- 19:32:08 terrain re-run (mire level -2.5: partly flooded) exit=0 2s
- 19:33:02 blender models hod_dk exit=0 tracebacks=0 1s
- 19:33:19 blender rebuild hod_dk_citadel (fallen spire tile white -> dark) + previews
- 19:33:33 military_buildings.py place 'Dromund Kaas' exit=0 0s
- 19:33:38 planet_terrain_gen.py --globe-texture exit=0 5s
- 19:33:53 final validate dromund_kaas: 0 errors, 0 warnings
- planet-specific code: 0 lines of terrain / placement code (TERRAIN_CFG + PLACEMENT tables only); map data + layout
  tables; 2 custom models (Kit code in military_buildings.models); shared code copied from zygerria_map.py with
  3 strings parametrised (CAPITAL_VP, PLANET in the state comment / file name)
- manual corrections during the run: landing zone moved onto the coast (dry runs 2-4), 776 seed moved to remove a
  sliver (dry run 5), mire lowered to flood (terrain re-run), fallen spire tile (model rebuild)
- remaining review: model looks (pale fallen-spire face, red stairs from the Korriban stair helper), the sunken sea /
  flooded mire rendering under the water plane in game, swamp water texture share, 776 coastal strip SW, invented names
