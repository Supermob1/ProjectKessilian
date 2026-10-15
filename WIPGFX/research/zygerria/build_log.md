# Zygerria build log (2026-10-14)
- 18:32 `WIPGFX/plans & scripts/validate_planet.py zygerria` exit=0 1s
- 18:32 research_planet.py Zygerria exit=0 26s
- 18:34 research_planet.py Zygerria --gaps 21s
- research total: 48 requests (26 + 21 gaps + 1 batch re-check), brief 5.6 KB; research_planet.py fixed on this planet: media/generic pages
  skipped (lead must name the planet), named regions become state anchors, gap hits not assumed to be cities, capital hint
- validate_planet.py: accepts "<id>-<Planet>.txt" (state 85 was invisible to it); preflight 0 errors, 9 warnings (pre-existing VP names)
- geometry: 203 provinces, 1 land mass, r~60 px, 48 coastal, 4 lane ends, strategic region 71, no units; next state id 1156
- STOP for approval: continuity, layout, models, 6 dirty data files (Florrum-trial leftovers) block the write guard
- snapshot of every writable file before Zygerria: job tmp pre_zygerria/ (133M)
- dry runs: 3 (layout iterations: mesas from hooks to carved blocks), each ~30 s, no writes
- 18:46 zygerria_map.py --allow-dirty exit=1 0s
- guard false positive on 85-Zygerria.txt (no ' - name'): planet_common.guard fixed, nothing had been written
- 18:51 zygerria_map.py --allow-dirty exit=0 281s
- 18:51 validate_planet.py zygerria exit=0 1s: 0 errors, 0 warnings
- 18:53 planet_terrain_gen.py --zygerria exit=0 2s
- 18:55 blender models hod_zyg_palace exit=0 4s
- blender attempt 1: ModuleNotFoundError io_pdx_mesh (exit 0 anyway): needs PYTHONPATH to the extensions folder
- 18:55 blender models hod_zyg_palace exit=0 tracebacks=0 2s
- 18:55 render_mesh.py palace preview 2s
- 18:56 military_buildings.py zygerria_place exit=0 0s
- 18:56 planet_terrain_gen.py --globe-texture exit=0 5s
- 18:56 final validate zygerria: 0 errors, 0 warnings
- final: zygerria 0 errors / 0 warnings; kadavo, florrum, korriban, raxus, felucia 0/0; raxus_prime 5 errors (pre-existing)
- scope check vs snapshot: only Zygerria's 21 state files; every changed map pixel inside Zygerria's bbox; text-file
  lines all about Zygerria provinces (plus one railway stub cut at the planet by place(), as on every planet)
- generator time: research ~2 min, dry runs 3 x 30 s, map 281 s, terrain 2 s, Blender 2 s (+ 2 s render), place <1 s, globe 5 s
- tool calls (whole task, approx.): ~75; failures repaired: guard + validator file-name pattern, Blender PYTHONPATH,
  research_planet media/region/capital heuristics; restarts of the whole pipeline: 0
- manual review: palace model vs TCW stills, city style 8 (Naboo) for the capital, Petranaki arena stand-in, slave camps
  as fortress / outpost stand-ins, cliff and pillar heights in game, invented names (see zygerria_map.py docstring)
