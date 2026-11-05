"""Rewrite each hyperlane's (sea adjacency in map/adjacencies.csv) comment from its province numbers
("Planet to Planet (states A > B)", planets being strategic regions), since hand-written comments drift.

Run again after adding or changing hyperlanes:  python gen_hyperlanes.py [mod_folder]
"""
import sys

from hoi4_country_editor import Mod, find_mod_root, read_text, write_text


def planet_names(mod):
    """Province -> name of its strategic region (in this mod, a region is a planet)."""
    from hoi4_country_editor import get, parse
    out = {}
    for f in mod.files('map/strategicregions'):
        for _, reg in parse(read_text(f)):
            if isinstance(reg, list):
                name = mod.loc.get(get(reg, 'name', ''), get(reg, 'name', '?'))
                for _, p in get(reg, 'provinces', []) or []:
                    out.setdefault(p, name)
    return out


def generate(mod):
    prov_state = mod.prov_state
    planet = planet_names(mod)
    adj_path = mod.path('map', 'adjacencies.csv')
    lines = read_text(adj_path).split('\n')
    n, skipped = 0, []
    for i, line in enumerate(lines):
        c = line.split(';')
        if len(c) < 10 or c[2] != 'sea' or not c[0].isdigit():
            continue
        sa, sb = prov_state.get(c[0]), prov_state.get(c[1])
        if not (sa and sb):  # an end that is not in any state: leave the lane as it is
            skipped.append(c[9])
            continue
        c[9] = f'{planet.get(c[0], "?")} to {planet.get(c[1], "?")} (states {sa} > {sb})'.replace(';', ',')
        lines[i] = ';'.join(c)
        n += 1
    write_text(adj_path, '\n'.join(lines))
    return n, skipped


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else find_mod_root()
    n, skipped = generate(Mod(root))
    print(f'{n} hyperlane comments refreshed.' + (f' Skipped (end not in a state): {skipped}' if skipped else ''))
