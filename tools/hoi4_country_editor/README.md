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
- **Leaders**: every recruited character with their portrait, roles and ideology.
  - **Add leader...** creates a character (country leader, political advisor, general, field marshal or admiral). **Random name** gives a Star Wars-sounding name. It converts any image to a 156x210 `.dds` portrait in `gfx/leaders/TAG/`, adds the character to the country's `common/characters` file and recruits it in the history file.
  - **Edit selected...** (or double-click a row) edits name, gender, portrait, the leader's ideology, description and traits, an advisor's slot and cost, and a commander's skills. It can add or remove roles, **Remove from country** (removes only the `recruit_character` line) or **Delete character**. Only the values you change are rewritten.
- **Suggest names** (Overview): fills the empty ideology name, long name, adjective and party boxes. There are about 15 government names and 10 party names per ideology (e.g. corist gives "Kingdom of X", "X Crown Worlds" or "Royal House of X"). Click again for others; **↻** re-rolls one row. Nothing is saved until **Save overview**.
- **Flag maker...** (Overview): 24 layouts (stripes, crosses, saltire, chevron, quartered, sun rays, checkered...), 4 colours, 18 drawn symbols (stars, crescent, cog, wheel, sunburst, crown...) and **Randomize**. Place the symbol or emblem in the center, the canton or the hoist, or start from an existing flag.
  - **Ready-made emblems**: every flag already in the mod is listed as `from flag: TAG`, with its background removed, so you can reuse the Republic, CIS, Mandalorian or Hutt emblems you already have. Any transparent PNG placed in an `emblems` folder next to the tool/exe, or in the mod's `gfx/emblems`, also shows up. **Recolour emblem** paints it in colour 4 and keeps its shading.
  - It saves the base or an ideology flag in all 3 sizes HOI4 needs (82x52, 41x26, 10x7).
- **National ideas**, **OOB**: the starting national spirits, and divisions or ships per unit file.
- **Edit files**: the raw history, country, character and OOB files. Press **Save (Ctrl+S)** after editing.

**Export missing report** writes a text file for all countries. From the command line: `python hoi4_country_editor.py <mod folder> --report`.

## What counts as missing
- **Required:** tag in `common/country_tags`; a country file with a color; a history file with a capital, a ruling party, and popularities that add up to 100; OOB files that exist, with every division using a template defined in its OOB; flags `TAG.tga` in `gfx/flags`, `medium/` and `small/`; localisation for `TAG`, `TAG_DEF` and `TAG_ADJ`; every recruited character defined; a country leader for the ruling party.
- **Recommended:** graphical culture, starting tech, research slots, a land OOB, a focus tree, party names (`TAG_<ideology>_party`), portrait files that exist.
- **Optional:** per-ideology flags (`TAG_<ideology>.tga`), country names (`TAG_<ideology>`), and leaders for every ideology that has popularity.

Like the game itself, it only reads the top level of `common/*` and `history/*`, so folders such as `common/ideologies/backup` are ignored.

# HOI4 Focus Tree Editor

`HOI4FocusEditor.exe` (or `python hoi4_focus_editor.py`) is built by the same GitHub Action and `build_exe.bat`, and finds the mod the same way.

## Using it
- Pick a tree file at the top, or **New tree...** for a country tag. It writes `common/national_focus/TAG_focus.txt` with a `country` block for that tag and a first focus.
- **The tree view**:
  - drag a focus to move it (it snaps to the grid);
  - double-click empty space to add a focus there;
  - right-click a focus to add a child, add a required prerequisite, add an "or" prerequisite, make it mutually exclusive, duplicate or delete it.
  - Lines: solid = required, dashed = "one of these", red with ⊘ = mutually exclusive.
  - Mouse wheel scrolls (Shift for sideways), middle-drag pans, and Zoom -/+ changes the size.
- **The form** (right): id (renaming updates every reference in the file), name and description (saved to localisation at once), icon, cost, position (absolute, or relative to another focus), prerequisites (one line per required group; `A or B` on a line means either one), and mutually exclusive.
- **Icons**: **Pick...** opens a searchable icon grid. **Import image...** turns any PNG/JPG/DDS into a 94x86 `.dds` in `gfx/interface/goals/TAG/` and adds both the sprite and its `_shine` sprite to your goals `.gfx` files. Click **Game folder...** once (your HOI4 install) to see and use the vanilla icons too.
- **Auto names** (toolbar): gives every focus without a name one made from its id: the tag is dropped and `_` becomes a space (`CIS_A_New_Birth_of_Freedom` → "A New Birth of Freedom"). They are written in one go next to the tree's other texts. Existing names and broken lines are not touched. The **Auto** button next to Name does the same for one focus (press Apply to keep it).
- **Durations** (tab in the sidebar): days per cost come from your mod's `NDefines.NFocus.FOCUS_POINT_DAYS`, or vanilla's 7 if the mod does not set it. Each box on the tree shows its days in the corner. The tab shows:
  - the **longest** and **shortest playthrough**. Each mutually exclusive group keeps one option and loses everything only reachable through the others; every combination is tried, so the numbers are exact.
  - the **longest single chain**, and the plain total of every focus.
  - every **exclusive choice** with the days and number of focuses each option unlocks. ★ marks the options taken in the longest playthrough.
  - the selected focus: its days, when it can be done at the earliest, and how many focuses need it.
  - **end dates** for each of these, as the engine date (from `START_DATE`) and, for Hearts of Durasteel, in the mod's own calendar. That calendar (start year, months, days per month, festival days) is read from the daily counter in `common/on_actions`, so it follows any change you make there. If the counter is not recognised, type the four numbers into **Mod calendar** once; they are remembered. **Tree starts on game day** shifts everything for trees that begin later in the game.
  - years in day counts use the mod's year length (368 days for Hearts of Durasteel).
  - `available = { }` conditions inside focus scripts are not evaluated.
- **Focus script**: the whole `focus = { ... }` block, for rewards, `available`, `bypass`, `ai_will_do` and everything else. **Apply script** checks the braces first.
- **Edit file text...** opens the whole file with a **Check braces** button, for anything the form cannot reach.
- **Save** (Ctrl+S), **Undo** (Ctrl+Z) and **Redo** (Ctrl+Y) work on the whole tree.

Edits change only the lines they touch, so comments and formatting are kept. Moving a focus that uses `relative_position_id` writes the new offset, so its children move with it. Deleting a focus removes every link to it and keeps the focuses that were placed relative to it where they are.

## Problems it catches (bottom list; double-click to jump there or fix it)
- **Errors**:
  - a missing or extra `}`, with the line of the block that is not closed. Double-click it to open **Edit file text...** at that line; until it is fixed the other checks are skipped, because everything after it is misread;
  - a duplicate focus id (also against every other focus file in the mod);
  - a prerequisite or mutually exclusive target, or a `relative_position_id`, that does not exist;
  - prerequisite loops;
  - a tree with no id;
  - localisation lines the game cannot read (missing closing quote), with file and line.
- **Warnings**:
  - an exclusive focus not listed back on the other side (one-click fix);
  - two focuses in the same spot;
  - a focus placed above its prerequisite;
  - missing name or description localisation;
  - a missing icon or an icon sprite that is not defined;
  - a missing cost;
  - a tree with no `country` block.

**Save** warns before writing a tree that still has errors. To check every tree without the GUI, run `python hoi4_focus_editor.py <mod folder> --check`.

# HOI4 Tech Tree Editor

`HOI4TechEditor.exe` (or `python hoi4_tech_editor.py`) is built by the same GitHub Action and `build_exe.bat`, and finds the mod the same way. It works like the focus editor, on the files in `common/technologies`.

- **File** and **Folder** pickers: the tree of one tech folder (`republic_folder`, `droid_folder`...) is drawn as in the mod's tech screen, left to right (y is the column, x the row), with its paths (arrows), `xor` exclusives (red ⊘), research cost (top left), start year (top right) and icon (`GFX_<tech>_medium`). The columns are labelled with the file's `@` variables (the year columns, e.g. `@977`). A path to a tech in another folder shows as "→ tech (folder)". Doctrines are purple.
- **Drag** a tech to move it. In files that use `@` rows, it snaps to the nearest year column and writes the variable, so `y = @977` stays `y = @977`.
- **Right-click** a tech: add the next tech in the next column (with the path), add a path to another tech, make two techs exclusive (written on both sides), duplicate (without its paths), delete (also removes every path and `xor` pointing at it). Right-click empty space to add a tech there.
- **Tech form**: id (renames every reference in the file), name and description (with **Auto** names), icon preview and **Import image...** (converts any image to a 64x64 `.dds` in `gfx/interface/technologies/` and registers `GFX_<tech>_medium`), folder, x / y (numbers, or `@` year columns for y), research cost, start year, categories, the techs it leads to (with their cost coefficient), and `xor`. **Tech script** holds the whole block for equipment, units, modifiers and `ai_will_do`.
- **Research time**: research cost x `BASE_TECH_COST` (read from the mod's defines, else vanilla's 100 days), with one slot and no research bonuses. It also shows when a tech is done at the earliest through its quickest line (a tech unlocks when any one tech leading to it is researched), and the total for the folder with 1 and 3 slots, in years of the mod calendar. The ahead-of-time penalty is not counted.
- **Problems** (double-click to jump or fix): missing or extra braces; a tech defined twice (also across files); a path with no `leads_to_tech` or to a tech that does not exist; `xor` or `dependencies` to unknown techs; `xor` not listed back (one-click fix); a folder or category that is not in `common/technology_tags`; an `@` variable that is not defined; two techs in the same spot; a path going backward; a tech with no folder; missing name or description localisation; a missing icon; a missing research cost. Set **Game folder...** to read vanilla icons and localisation, so vanilla techs copied into the mod don't show as missing.
- **New file...**, **Save** (Ctrl+S), **Undo** (Ctrl+Z), **Redo** (Ctrl+Y), **Auto names**, **Edit file text...**: as in the focus editor.

To check every tech file without the GUI: `python hoi4_tech_editor.py <mod folder> --check`.
