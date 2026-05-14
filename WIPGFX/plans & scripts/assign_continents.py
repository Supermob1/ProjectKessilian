#!/usr/bin/env python3
"""
assign_continents.py — Assign galactic subregion continents to provinces.

Reads every planet strategic region (skipping space/sector files), groups
each planet into a Star Wars galactic subregion, and writes the corresponding
continent ID into definition.csv column 7.

Also rewrites map/continent.txt and creates a continents_l_english.yml.

Usage:
    python assign_continents.py --dry-run     preview what will change
    python assign_continents.py               write all changes
    python assign_continents.py --list        list planet → continent mapping
"""

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MOD_ROOT      = Path(__file__).parent
SR_DIR        = MOD_ROOT / "map" / "strategicregions"
DEF_CSV       = MOD_ROOT / "map" / "definition.csv"
CONTINENT_TXT = MOD_ROOT / "map" / "continent.txt"
LOC_DIR       = MOD_ROOT / "localisation" / "english"
CONTINENT_LOC = LOC_DIR / "continents_l_english.yml"

# ---------------------------------------------------------------------------
# Continent definitions  (continent 0 = no continent / ocean / unassigned)
# ---------------------------------------------------------------------------

CONTINENTS = [
    ("galactic_core",        "Republican Space"),        # 1
    ("separatist_space",     "Separatist Space"),           # 2
    ("outer_rim",            "Outer Rim"),               # 3
    ("hutt_space",           "Hutt Space"),               # 4
    ("expansion_region",     "Expansion Region"),                 # 5
    ("northern_colonies",    "Northern Colonies"),              # 6
]
# ---------------------------------------------------------------------------
# Planet → galactic subregion mapping
# Names match the strategic-region filename stem exactly (after stripping "ID-").
# Typos in filenames (Christphsis, Cato Neimodia) are intentionally preserved.
# ---------------------------------------------------------------------------

GALACTIC_CORE = [
    "Byss", "Tython", "Fresia", "Foerost",
    "Coruscant", "Alderaan", "Anaxes", "Carida",
    "Chandrila", "Commenor", "Corellia", "Corulag",
    "Duro", "Esseles", "Kuat", "Rendilli",
    "Brentaal", "Borleias", "Arkania", "Loronar",
    "Mindor", "Balmorra", "Neimodia", "Manaan",
    "Abregado-Rae", "Fondor", "Takodana", "Yag'Dhul",
    "Thyferria", "Ghorman", "Cerea", "Mechis",
    "Mimban", "Cato Neimoidia", "Atzerri", "Allanteen VI",
    "Bestine IV",
]
SEPARATIST_SPACE = [
    "Ossus", "Saleucami", "Felucia", "Florrum",
    "Ringo Vinda", "Lola Sayu", "Korriban", "Dromund Kaas", 
    "Ziost", "Roche", "Raxus Prime", "Raxus",
    "Bracca", "Sleheyron", "Zygerria", "Kadavo",
    "Iego", "Mon Calamari", "Pammant", "Lianna",
    "Jabiim", "Bonadan", "Etti IV", "Malachor V",
    "Reltooine",
]
OUTER_RIM = [
    "Batuu", "Bakura", "Endor", "Anoat",
    "Hoth", "Terminus", "Manpha", "Mustafar",
    "Belsavis", "Karfeddion", "Eriadu", "Phelarion",
    "Sluis Van", "Queyta", "Utapau", "Sullust",
    "Tibrin", "Haruun Kal", "Malastare", "Naboo",
    "Lehon", "Rishi", "Kamino", "Rothana",
    "Vohai", "Farstine", "Pantora", "Alzoc III",
    "Falleen", "Bothawui", "Ryloth", "Christphsis",
    "Rodia", "Geonosis", "Tatooine", "Hypori",
]
HUTT_SPACE = [
    "Nal Hutta", "Nar Shaddaa", "Teth", "Shola",
    "Honoghr", "Nimban", "Kessel", "Oba Diah",
    "Boz Pity", "Quesh", "Toydaria",
]
EXPANSION_REGION = [
    "Taris", "Kashyyyk", "Umbara", "Ruusan",
    "Axxila", "Telos", "Ciutric", "Yavin IV", 
    "Wayland", "Serenno", "Nyriaan", "Hapes",
    "Onderon", "Celanon", "Botajef", "Dathomir",
    "Ord Cestus", "Mykr", "Mandalore",
]
NORTHERN_COLONIES = [
    "Bastion", "Dorin", "Dubrillion", "Dantooine", 
    "Muunilist", "Mygeeto", "Yaga Minor", "Ithor",
    "Ord Mantell", "Orinda", "Kalee", "Agamar",
    "Garqi", "Jedha", "Despayre", "Ilum",
    "Csilla", "Copero", "Csaus", "Cioral",
    "Aeten II",
]

# Build planet → continent_id (1-indexed)
PLANET_TO_CONTINENT: Dict[str, int] = {}
for name in GALACTIC_CORE:              PLANET_TO_CONTINENT[name] = 1
for name in SEPARATIST_SPACE:            PLANET_TO_CONTINENT[name] = 2
for name in OUTER_RIM:               PLANET_TO_CONTINENT[name] = 3
for name in HUTT_SPACE:       PLANET_TO_CONTINENT[name] = 4
for name in EXPANSION_REGION:              PLANET_TO_CONTINENT[name] = 5
for name in NORTHERN_COLONIES:                PLANET_TO_CONTINENT[name] = 6
# ---------------------------------------------------------------------------
# Strategic region parser
# ---------------------------------------------------------------------------

def is_planet_region(content: str) -> bool:
    """A planet region has no `naval_terrain=` line; space regions do."""
    return not re.search(r"^\s*naval_terrain\s*=", content, re.MULTILINE)


def parse_strategic_region(path: Path) -> Tuple[str, List[int]]:
    """
    Return (planet_name_from_filename, [province_ids]).
    Filename format is "<id>-<planet_name>.txt".
    """
    stem = path.stem
    name = re.sub(r"^\d+-\s*", "", stem)   # strip leading "ID-"
    content = path.read_text(encoding="utf-8", errors="replace")
    prov_m = re.search(r"provinces\s*=\s*\{([^}]*)\}", content, re.DOTALL)
    provinces = [int(x) for x in prov_m.group(1).split()] if prov_m else []
    return name, provinces, content


def collect_planet_provinces() -> Tuple[Dict[int, int], Dict[str, int], List[str]]:
    """
    Walk strategicregions/ and build:
      - province_to_continent[province_id] = continent_id
      - planet_counts[planet_name] = province_count   (planet regions only)
      - unmapped[]                  list of planet names we don't know
    """
    province_to_continent: Dict[int, int] = {}
    planet_counts: Dict[str, int] = defaultdict(int)
    unmapped: List[str] = []

    for f in sorted(SR_DIR.glob("*.txt")):
        name, provinces, content = parse_strategic_region(f)
        if not is_planet_region(content):
            continue
        if "Sector" in name or "Sector" in f.stem:
            continue

        cid = PLANET_TO_CONTINENT.get(name)
        if cid is None:
            unmapped.append(name)
            continue

        planet_counts[name] += len(provinces)
        for pid in provinces:
            province_to_continent[pid] = cid

    return province_to_continent, planet_counts, unmapped

# ---------------------------------------------------------------------------
# Definition.csv I/O
# ---------------------------------------------------------------------------

def load_definition_rows(path: Path) -> List[List[str]]:
    rows: List[List[str]] = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line:
                continue
            rows.append(line.split(";"))
    return rows


def write_definition_rows(path: Path, rows: List[List[str]]) -> None:
    out = "\n".join(";".join(r) for r in rows) + "\n"
    path.write_text(out, encoding="utf-8")


def apply_continents(rows: List[List[str]], p2c: Dict[int, int]) -> Tuple[int, int]:
    """Mutates rows; returns (changed_count, unchanged_count)."""
    changed = 0
    unchanged = 0
    for row in rows:
        if len(row) < 8:
            continue
        try:
            pid = int(row[0])
        except ValueError:
            continue
        new_cid = p2c.get(pid)
        if new_cid is None:
            unchanged += 1
            continue
        if row[7] != str(new_cid):
            row[7] = str(new_cid)
            changed += 1
    return changed, unchanged

# ---------------------------------------------------------------------------
# Continent files
# ---------------------------------------------------------------------------

def write_continent_txt() -> None:
    keys = [k for k, _ in CONTINENTS]
    content = "continents = {\n" + "".join(f"\t{k}\n" for k in keys) + "}\n"
    CONTINENT_TXT.write_text(content, encoding="utf-8")


def write_continent_localisation() -> None:
    lines = ["l_english:"]
    for key, name in CONTINENTS:
        lines.append(f' {key}:0 "{name}"')
    CONTINENT_LOC.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--list",    action="store_true",
                   help="Print planet→continent table and exit")
    args = p.parse_args()

    if args.list:
        print(f"{'Planet':<25}  {'Continent':<20}")
        print("-" * 50)
        for cid in range(1, len(CONTINENTS) + 1):
            cname = CONTINENTS[cid - 1][1]
            planets = sorted(n for n, c in PLANET_TO_CONTINENT.items() if c == cid)
            for pn in planets:
                print(f"  {pn:<23}  {cname}")
            print()
        return

    print("Reading strategic regions...")
    province_to_continent, planet_counts, unmapped = collect_planet_provinces()
    print(f"  {len(planet_counts)} planet regions mapped, {len(province_to_continent):,} provinces assigned.")
    if unmapped:
        print(f"  WARNING: {len(unmapped)} planet regions had no continent mapping:")
        for n in unmapped:
            print(f"    - {n!r}")

    # Per-continent summary
    print("\nProvinces per continent:")
    per_cont = defaultdict(int)
    for cid in province_to_continent.values():
        per_cont[cid] += 1
    for cid in range(1, len(CONTINENTS) + 1):
        key, name = CONTINENTS[cid - 1]
        print(f"  {cid}. {name:<24}  {per_cont[cid]:>6,} provinces")

    print("\nReading definition.csv...")
    rows = load_definition_rows(DEF_CSV)
    print(f"  Loaded {len(rows):,} rows.")

    changed, unchanged = apply_continents(rows, province_to_continent)
    print(f"  Will change continent on {changed:,} provinces; {unchanged:,} provinces unaffected.")

    if args.dry_run:
        print("\n[dry-run] No files were written.")
        return

    print("\nWriting definition.csv...")
    write_definition_rows(DEF_CSV, rows)
    print("Writing continent.txt...")
    write_continent_txt()
    print("Writing continents_l_english.yml...")
    write_continent_localisation()
    print("Done.")


if __name__ == "__main__":
    main()
