# HOI4 Country Editor

A small desktop tool to browse every country in the mod, edit its files, and see what each one is missing.

## Get the .exe
- **Easiest:** on GitHub, open *Actions → Build HOI4 Country Editor → latest run → Artifacts* and download `HOI4CountryEditor`.
- **Or build it yourself (Windows):** install Python from python.org, then double-click `build_exe.bat`. The exe ends up in `dist/`.
- **Or just run it:** `python hoi4_country_editor.py`

Put the exe anywhere inside the mod folder and it finds the mod by itself (it looks for `descriptor.mod`). Anywhere else, it asks you to pick the folder.

## What it shows
For each country (the list on the left shows `required / recommended` missing counts):
- **Checklist**: what's there and what's missing, ranked *required* (red), *recommended* (orange), *optional* (grey).
- **Overview**: capital, ruling party, stability, war support, ideas, focus tree.
- **Ideologies**: popularity, leader, flag, country name and party name for each ideology.
- **Leaders & characters**: each recruited character, their roles, ideology and portrait.
- **Military**: divisions per template, fleets and ships from the OOB files.
- **Edit files**: open the country's history, country, character or OOB file, change it, then press **Save (Ctrl+S)**. All checks run again after saving.

**Export missing report** writes a text file for all countries. From the command line: `python hoi4_country_editor.py <mod folder> --report`.

## What counts as missing
- **Required:** tag in `common/country_tags`; a country file with a color; a history file with a capital, a ruling party, and popularities that add up to 100; OOB files that exist, with every division using a template defined in its OOB; flags `TAG.tga` in `gfx/flags`, `medium/` and `small/`; localisation for `TAG`, `TAG_DEF` and `TAG_ADJ`; every recruited character defined; a country leader for the ruling party.
- **Recommended:** graphical culture, starting tech, research slots, a land OOB, a focus tree, party names (`TAG_<ideology>_party`), portrait files that exist.
- **Optional:** per-ideology flags (`TAG_<ideology>.tga`), country names (`TAG_<ideology>`), and leaders for every ideology that has popularity.

Like the game itself, it only reads the top level of `common/*` and `history/*`, so folders such as `common/ideologies/backup` are ignored.
