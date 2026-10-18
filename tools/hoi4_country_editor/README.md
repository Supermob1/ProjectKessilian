# HOI4 Country Editor

A small desktop tool to browse every country in the mod, edit its files, and see what each one is missing.

## Get the .exe
- **Easiest:** on GitHub, open *Actions → Build HOI4 Country Editor → latest run → Artifacts* and download `HOI4CountryEditor`.
- **Or build it yourself (Windows):** install Python from python.org, then double-click `build_exe.bat`. The exe ends up in `dist/`.
- **Or just run it:** `pip install pillow`, then `python hoi4_country_editor.py` (without Pillow it still works, minus the map and flag pictures).

Put the exe anywhere inside the mod folder and it finds the mod by itself (it looks for `descriptor.mod`). Anywhere else, it asks you to pick the folder.

## What it shows
Three panels: the country list (flag, tag, number of states, `required / recommended` missing counts), the map, and the selected country.

- **Map**: provinces coloured by owner, by the selected country's cores (red = core, orange = owned but not a core), or by ruling ideology. Use the mouse wheel to zoom and right-drag to move. Click a planet to select its owner. The bottom bar shows the state under the mouse.
- **Overview** (editable): name, long name (`_DEF`), adjective (`_ADJ`) and party name for the default and every ideology; map colour; all flags; capital; stability; war support; research slots; ruling party; elections; popularities (with a live total); the starting leader. **Save overview** only writes the lines you changed: history file values, `color` in the country file, and localisation lines in their existing file. New localisation keys go into the file that already holds the country name.
- **Checklist**: what's there and what's missing, ranked *required* (red), *recommended* (orange), *optional* (grey).
- **Leaders**, **National ideas**, **OOB**: characters with their roles and portraits, the starting national spirits, and divisions or ships per unit file.
- **Edit files**: the raw history, country, character and OOB files. Press **Save (Ctrl+S)** after editing.

**Export missing report** writes a text file for all countries. From the command line: `python hoi4_country_editor.py <mod folder> --report`.

## What counts as missing
- **Required:** tag in `common/country_tags`; a country file with a color; a history file with a capital, a ruling party, and popularities that add up to 100; OOB files that exist, with every division using a template defined in its OOB; flags `TAG.tga` in `gfx/flags`, `medium/` and `small/`; localisation for `TAG`, `TAG_DEF` and `TAG_ADJ`; every recruited character defined; a country leader for the ruling party.
- **Recommended:** graphical culture, starting tech, research slots, a land OOB, a focus tree, party names (`TAG_<ideology>_party`), portrait files that exist.
- **Optional:** per-ideology flags (`TAG_<ideology>.tga`), country names (`TAG_<ideology>`), and leaders for every ideology that has popularity.

Like the game itself, it only reads the top level of `common/*` and `history/*`, so folders such as `common/ideologies/backup` are ignored.
