#!/usr/bin/env python3
"""
populate_states.py — Fill split planet states with manpower, buildings,
resources, victory points, and naval bases.

Idempotent by default: only touches fields that are empty / unset, so re-running
won't clobber states you've hand-edited. Use --force to overwrite everything.

Usage:
    python populate_states.py --dry-run        preview changes
    python populate_states.py                  populate empty fields only
    python populate_states.py --force          overwrite everything
    python populate_states.py --only 44,288    process specific state IDs
"""

import argparse
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MOD_ROOT   = Path(__file__).parent
STATES_DIR = MOD_ROOT / "history" / "states"
DEF_CSV    = MOD_ROOT / "map" / "definition.csv"

# ---------------------------------------------------------------------------
# Per-category templates  (min, max) — script picks a deterministic value per state
# ---------------------------------------------------------------------------

CATEGORY_TEMPLATES: Dict[str, Dict[str, Tuple]] = {
    "capital_sector": {
        "manpower":           (1_200_000, 2_500_000),
        "infrastructure":     (4, 5),
        "industrial_complex": (4, 7),
        "arms_factory":       (3, 5),
        "air_base":           (2, 3),
        "naval_base":         (3, 4),    # if coastal, on chosen coastal prov
        "dockyard":           (1, 2),    # if coastal
        "victory_points":     5,
    },
    "industrial_sector": {
        "manpower":           (700_000, 1_300_000),
        "infrastructure":     (3, 5),
        "industrial_complex": (5, 8),
        "arms_factory":       (4, 7),
        "air_base":           (1, 2),
        "naval_base":         (2, 3),
        "dockyard":           (1, 2),
        "victory_points":     4,
    },
    "economic_sector": {
        "manpower":           (1_500_000, 3_000_000),
        "infrastructure":     (4, 5),
        "industrial_complex": (5, 8),
        "arms_factory":       (1, 3),
        "air_base":           (1, 2),
        "naval_base":         (2, 3),
        "dockyard":           (0, 1),
        "victory_points":     4,
    },
    "agricultural_sector": {
        "manpower":           (300_000, 600_000),
        "infrastructure":     (2, 4),
        "industrial_complex": (1, 3),
        "arms_factory":       (0, 2),
        "air_base":           (0, 1),
        "naval_base":         (1, 2),
        "dockyard":           (0, 1),
        "victory_points":     3,
    },
    "wasteland_sector": {
        "manpower":           (50_000, 200_000),
        "infrastructure":     (1, 2),
        "industrial_complex": (0, 1),
        "arms_factory":       (0, 1),
        "air_base":           (0, 1),
        "naval_base":         (0, 1),
        "dockyard":           (0, 0),
        "victory_points":     2,
    },
    "large_planet": {   # fallback for any unsplit single-state planet
        "manpower":           (800_000, 1_500_000),
        "infrastructure":     (2, 4),
        "industrial_complex": (2, 5),
        "arms_factory":       (1, 3),
        "air_base":           (1, 2),
        "naval_base":         (1, 2),
        "dockyard":           (0, 1),
        "victory_points":     3,
    },
}

# Default for unknown categories
DEFAULT_TEMPLATE = CATEGORY_TEMPLATES["agricultural_sector"]

# Resources keyed by dominant terrain (HOI4 name; Star Wars equiv. in comment)
TERRAIN_RESOURCES: Dict[str, Dict[str, Tuple[int, int]]] = {
    "urban":     {"chromium": (2, 4), "coal":      (1, 3)},   # Circuitry, Credits
    "plains":    {"coal":     (1, 3), "oil":       (0, 2)},   # Credits, Fuel
    "hills":     {"tungsten": (1, 3), "coal":      (0, 2)},   # Minerals, Credits
    "forest":    {"rubber":   (1, 3)},                        # Bacta
    "jungle":    {"rubber":   (1, 4), "oil":       (0, 1)},   # Bacta, Fuel
    "desert":    {"oil":      (1, 4), "aluminium": (0, 2)},   # Fuel, Doonium
    "mountain":  {"tungsten": (2, 5), "steel":     (1, 3),    # Minerals, Alloys, Doonium
                  "aluminium":(0, 2)},
    "marsh":     {"oil":      (1, 3)},
    "ocean":     {},
    "lake":      {},
    "snow":      {"tungsten": (1, 3)},
    "unknown":   {"coal":     (1, 2)},
}

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def load_definition(path: Path) -> Dict[int, Dict]:
    """Returns {pid: {'terrain': str, 'is_coastal': bool}}."""
    result: Dict[int, Dict] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 7:
                continue
            try:
                result[int(parts[0])] = {
                    "terrain":    parts[6].strip(),
                    "is_coastal": parts[5].strip().lower() == "true",
                }
            except (ValueError, IndexError):
                continue
    return result


@dataclass
class StateFile:
    """A loose representation of a state .txt file that we can mutate."""
    path: Path
    state_id: int
    name_key: str
    provinces: List[int]
    owner: str = ""
    cores: List[str] = field(default_factory=list)
    resources: Dict[str, str] = field(default_factory=dict)   # name -> "value[#comment]"
    manpower: int = 0
    category: str = "wasteland_sector"
    bldg_max_lvl: float = 1.0
    local_supplies: float = 0.0
    state_buildings: Dict[str, int] = field(default_factory=dict)
    province_buildings: Dict[int, Dict[str, int]] = field(default_factory=dict)
    victory_points: List[Tuple[int, int]] = field(default_factory=list)  # (prov, value)


_PROV_BLOCK_RE = re.compile(r"(\d+)\s*=\s*\{([^}]*)\}", re.DOTALL)


def parse_state_file(path: Path) -> Optional[StateFile]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  ERROR reading {path.name}: {e}")
        return None

    sid_m = re.search(r"\bid\s*=\s*(\d+)", content)
    if not sid_m:
        return None
    state_id = int(sid_m.group(1))
    name_m   = re.search(r'\bname\s*=\s*"([^"]+)"', content)
    prov_m   = re.search(r"provinces\s*=\s*\{([^}]*)\}", content, re.DOTALL)
    provinces = [int(x) for x in prov_m.group(1).split()] if prov_m else []
    mp_m   = re.search(r"\bmanpower\s*=\s*(\d+)", content)
    cat_m  = re.search(r"\bstate_category\s*=\s*(\w+)", content)
    bml_m  = re.search(r"\bbuildings_max_level_factor\s*=\s*([\d.]+)", content)
    ls_m   = re.search(r"\blocal_supplies\s*=\s*([\d.]+)", content)
    own_m  = re.search(r"\bowner\s*=\s*([A-Z]{3})\b", content)

    sf = StateFile(
        path=path,
        state_id=state_id,
        name_key=name_m.group(1) if name_m else f"STATE_{state_id}",
        provinces=provinces,
        manpower=int(mp_m.group(1)) if mp_m else 0,
        category=cat_m.group(1) if cat_m else "wasteland_sector",
        bldg_max_lvl=float(bml_m.group(1)) if bml_m else 1.0,
        local_supplies=float(ls_m.group(1)) if ls_m else 0.0,
        owner=own_m.group(1) if own_m else "",
        cores=re.findall(r"\badd_core_of\s*=\s*([A-Z]{3})\b", content),
    )

    # Resources
    res_m = re.search(r"\bresources\s*=\s*\{([^}]*)\}", content, re.DOTALL)
    if res_m:
        for line in res_m.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rm = re.match(r"(\w+)\s*=\s*(\d+)\s*(#.*)?", line)
            if rm and rm.group(1) not in ("id", "manpower"):
                comment = rm.group(3) or ""
                sf.resources[rm.group(1)] = f"{rm.group(2)}{comment}"

    # history.buildings block — split into state-level and province-level entries
    h_m = re.search(r"\bhistory\s*=\s*\{", content)
    if h_m:
        # naive: take everything from history { to its closing brace at indent 1
        start = h_m.end()
        depth = 1
        i = start
        while i < len(content) and depth > 0:
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            i += 1
        history_body = content[start:i - 1]

        # Victory points (may appear multiple times)
        for vp_m in re.finditer(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", history_body):
            sf.victory_points.append((int(vp_m.group(1)), int(vp_m.group(2))))

        # buildings = { ... }
        b_m = re.search(r"buildings\s*=\s*\{", history_body)
        if b_m:
            bstart = b_m.end()
            bdepth = 1
            j = bstart
            while j < len(history_body) and bdepth > 0:
                if history_body[j] == "{":
                    bdepth += 1
                elif history_body[j] == "}":
                    bdepth -= 1
                j += 1
            bbody = history_body[bstart:j - 1]

            # First, pull out province-level blocks: 12345 = { naval_base = 3 }
            consumed_spans: List[Tuple[int, int]] = []
            for m in _PROV_BLOCK_RE.finditer(bbody):
                pid = int(m.group(1))
                inner = m.group(2)
                bldgs = {bm.group(1): int(bm.group(2))
                         for bm in re.finditer(r"(\w+)\s*=\s*(\d+)", inner)}
                if bldgs and pid >= 10:
                    sf.province_buildings.setdefault(pid, {}).update(bldgs)
                    consumed_spans.append(m.span())

            # Then state-level scalar buildings, skipping spans already consumed
            for m in re.finditer(r"^[ \t]*(\w+)\s*=\s*(\d+)\s*(?:#.*)?$", bbody, re.MULTILINE):
                # Is this match inside a consumed province block?
                if any(s <= m.start() < e for s, e in consumed_spans):
                    continue
                bname = m.group(1)
                bval = int(m.group(2))
                if bname.isdigit():   # province id followed by something else; skip
                    continue
                if bval > 0:
                    sf.state_buildings[bname] = bval

    return sf

# ---------------------------------------------------------------------------
# Population rules
# ---------------------------------------------------------------------------

def pick_value(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi) if hi > lo else lo


def dominant_terrain(provinces: List[int], terrain_lookup: Dict) -> str:
    counts: Dict[str, int] = defaultdict(int)
    for p in provinces:
        counts[terrain_lookup.get(p, {}).get("terrain", "unknown")] += 1
    return max(counts, key=lambda k: counts[k]) if counts else "unknown"


def coastal_provinces(provinces: List[int], terrain_lookup: Dict) -> List[int]:
    return [p for p in provinces if terrain_lookup.get(p, {}).get("is_coastal", False)]


def vp_provinces_for_state(state: StateFile, terrain_lookup: Dict, vp_count: int) -> List[Tuple[int, int]]:
    """Pick provinces to host victory points. Total VP value = template value;
       spread across up to 2 provinces for capitals, 1 for everything else."""
    if not state.provinces:
        return []
    # Prefer urban → coastal → first province
    urban = [p for p in state.provinces
             if terrain_lookup.get(p, {}).get("terrain") == "urban"]
    coastal = coastal_provinces(state.provinces, terrain_lookup)
    sorted_p = sorted(state.provinces)
    pool = urban or coastal or sorted_p
    if state.category == "capital_sector" and len(pool) >= 2:
        # Split: bigger share on main province, smaller on a secondary
        main = pool[0]
        second = (urban[1] if len(urban) > 1
                  else coastal[0] if coastal and coastal[0] != main
                  else sorted_p[len(sorted_p) // 2])
        return [(main, vp_count), (second, max(1, vp_count - 2))]
    return [(pool[0], vp_count)]


def populate_state(sf: StateFile, terrain_lookup: Dict, force: bool, rng: random.Random
                   ) -> Dict[str, str]:
    """Mutate state in-place. Returns a dict describing changes for logging."""
    changes: Dict[str, str] = {}
    tmpl = CATEGORY_TEMPLATES.get(sf.category, DEFAULT_TEMPLATE)
    is_coastal = bool(coastal_provinces(sf.provinces, terrain_lookup))
    terrain = dominant_terrain(sf.provinces, terrain_lookup)

    # ── Manpower ───────────────────────────────────────────────────────────
    # Update if forced, or empty, or this state is "freshly split" (no buildings + no VPs yet)
    freshly_split = not sf.state_buildings and not sf.victory_points
    if force or sf.manpower < 25_000 or freshly_split:
        new_mp = pick_value(rng, *tmpl["manpower"])
        # Slight scale for very small/large states (≤10 or ≥80 provinces)
        n = len(sf.provinces)
        if n < 8:
            new_mp = int(new_mp * 0.5)
        elif n > 60:
            new_mp = int(new_mp * 1.4)
        changes["manpower"] = f"{sf.manpower:,} → {new_mp:,}"
        sf.manpower = new_mp

    # ── Resources (terrain-driven) ─────────────────────────────────────────
    if force or not sf.resources:
        added: List[str] = []
        for rname, (lo, hi) in TERRAIN_RESOURCES.get(terrain, {}).items():
            v = pick_value(rng, lo, hi)
            if v > 0:
                sf.resources[rname] = str(v)
                added.append(f"{rname}={v}")
        if added:
            changes["resources"] = "+ " + ", ".join(added)

    # ── State-level buildings ─────────────────────────────────────────────
    if force or not sf.state_buildings:
        added = []
        for key in ("infrastructure", "industrial_complex", "arms_factory", "air_base"):
            v = pick_value(rng, *tmpl[key])
            if v > 0:
                sf.state_buildings[key] = v
                added.append(f"{key}={v}")
        # Dockyard requires coastal access
        if is_coastal:
            v = pick_value(rng, *tmpl.get("dockyard", (0, 0)))
            if v > 0:
                sf.state_buildings["dockyard"] = v
                added.append(f"dockyard={v}")
        if added:
            changes["buildings"] = "+ " + ", ".join(added)

    # ── Naval base on a coastal province (if coastal & none present) ──────
    if is_coastal:
        has_nb = any("naval_base" in b for b in sf.province_buildings.values())
        if not has_nb or force:
            coast = coastal_provinces(sf.provinces, terrain_lookup)
            if coast:
                target = coast[len(coast) // 2]   # middle coastal province
                lvl = pick_value(rng, *tmpl.get("naval_base", (1, 2)))
                if lvl > 0:
                    sf.province_buildings.setdefault(target, {})["naval_base"] = lvl
                    changes["naval_base"] = f"prov {target} = lvl {lvl}"

    # ── Victory points ────────────────────────────────────────────────────
    if force or not sf.victory_points:
        sf.victory_points = vp_provinces_for_state(sf, terrain_lookup, tmpl["victory_points"])
        if sf.victory_points:
            changes["victory_points"] = ", ".join(f"prov {p}={v}" for p, v in sf.victory_points)

    return changes

# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def render_state(sf: StateFile) -> str:
    lines = ["state={", f"\tid={sf.state_id}", f'\tname="{sf.name_key}"', "\tprovinces={"]
    buf = "\t\t"
    for pid in sorted(sf.provinces):
        tok = str(pid) + " "
        if len(buf) + len(tok) > 120:
            lines.append(buf.rstrip())
            buf = "\t\t"
        buf += tok
    if buf.strip():
        lines.append(buf.rstrip())
    lines.append("\t}")

    if sf.resources:
        lines.append("\tresources={")
        for name, val in sf.resources.items():
            lines.append(f"\t\t{name}={val}")
        lines.append("\t}")

    lines.append("\thistory = {")
    # Victory points (one block per province)
    for prov, val in sf.victory_points:
        lines.append("\t\tvictory_points = {")
        lines.append(f"\t\t\t{prov} {val}")
        lines.append("\t\t}")

    # Buildings block: state-level scalars + per-province sub-blocks
    if sf.state_buildings or sf.province_buildings:
        lines.append("\t\tbuildings = {")
        for bname in ("infrastructure", "industrial_complex", "arms_factory",
                      "air_base", "dockyard", "anti_air_building",
                      "synthetic_refinery", "rocket_site", "radar_station",
                      "nuclear_reactor", "nuclear_facility"):
            if bname in sf.state_buildings:
                lines.append(f"\t\t\t{bname} = {sf.state_buildings[bname]}")
        # Any other state-level keys we didn't pre-order
        for bname, lvl in sf.state_buildings.items():
            if bname not in ("infrastructure", "industrial_complex", "arms_factory",
                             "air_base", "dockyard", "anti_air_building",
                             "synthetic_refinery", "rocket_site", "radar_station",
                             "nuclear_reactor", "nuclear_facility"):
                lines.append(f"\t\t\t{bname} = {lvl}")
        # Province-level
        for pid in sorted(sf.province_buildings):
            lines.append(f"\t\t\t{pid} = {{")
            for btype, lvl in sf.province_buildings[pid].items():
                lines.append(f"\t\t\t\t{btype} = {lvl}")
            lines.append("\t\t\t}")
        lines.append("\t\t}")

    lines.append(f"\t\towner = {sf.owner}")
    for c in sf.cores:
        lines.append(f"\t\tadd_core_of = {c}")
    lines.append("\t}")
    lines.append(f"\tmanpower = {sf.manpower}")
    lines.append(f"\tstate_category = {sf.category}")
    lines.append(f"\tbuildings_max_level_factor={sf.bldg_max_lvl:.3f}")
    lines.append(f"\tlocal_supplies={sf.local_supplies:.3f}")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Populate split states.")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview changes without writing files")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing manpower/buildings/resources/VPs")
    p.add_argument("--only", type=str, default="",
                   help="Comma-separated state IDs to process (default: all)")
    args = p.parse_args()

    print("Loading definition.csv...")
    terrain_lookup = load_definition(DEF_CSV)
    print(f"  {len(terrain_lookup):,} provinces.")

    only_set: Optional[Set[int]] = None
    if args.only:
        only_set = {int(x) for x in args.only.split(",") if x.strip().isdigit()}
        print(f"  Restricted to {len(only_set)} state IDs.")

    state_files = sorted(STATES_DIR.glob("*.txt"))
    print(f"Found {len(state_files)} state files.\n")

    touched = 0
    summary = defaultdict(int)
    for path in state_files:
        sf = parse_state_file(path)
        if not sf or not sf.provinces:
            continue
        if only_set is not None and sf.state_id not in only_set:
            continue

        # Per-state deterministic RNG so reruns are stable
        rng = random.Random(sf.state_id * 9173 + 1)

        changes = populate_state(sf, terrain_lookup, args.force, rng)
        if not changes:
            continue

        touched += 1
        for k in changes:
            summary[k] += 1

        bullets = "; ".join(f"{k}: {v}" for k, v in changes.items())
        print(f"  {sf.state_id:>4} {sf.name_key:<14} [{sf.category:<20}] {bullets}")

        if not args.dry_run:
            path.write_text(render_state(sf), encoding="utf-8")

    print(f"\nTouched {touched} state files.")
    for k, v in summary.items():
        print(f"  {k:<16}: {v} states")
    if args.dry_run:
        print("\n[dry-run] No files were written.")


if __name__ == "__main__":
    main()
