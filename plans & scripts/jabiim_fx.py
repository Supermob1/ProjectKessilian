"""Jabiim's monsoon (Legends: a world of endless rain; the user, 2026-10-16: add the rain): thin slanting rain over
the whole planet (vanilla rain_small, dimmed and scaled to a ~60 px planet) and a very thin grey overcast drifting
high above it. Kept light on purpose: Dromund Kaas's first, opaque storm hid its planet (user, 2026-10-14).
Purely visual: the strategic region's weather is not touched (weather changes gameplay).
Particle effects on ambient map objects (the dromund_kaas_fx.py way: its helpers, kadavo_fx's template).

    python "WIPGFX/plans & scripts/jabiim_fx.py"

Run from the mod root after jabiim_map.py (it reads the zones file); re-runs replace the block.
"""
import os, re, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kadavo_fx import TEMPLATE, rw
from dromund_kaas_fx import entity as dk_entity, gfx as dk_gfx

ZONES = "WIPGFX/Assets/jabiim_zones.png"
MARK = ("# HOD: Jabiim monsoon (jabiim_fx.py)", "# HOD: end of Jabiim monsoon")
RAIN_CELL, RAIN_HEIGHT = 14, 10.0      # one rain emitter per cell (px), set at about ground height
CLOUD_CELL, CLOUD_HEIGHT = 20, 24.0    # one overcast emitter per cell, high over the tallest models
VANILLA_RAIN = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/particles/environment/rain_small.asset"
# the rain, scaled (vanilla: radius 12/11, starts 25 up, alpha 255, emission 80, size 6): it starts 13 over its
# emitter and falls ~12 in its life, so it ends at the ground; dimmed to keep the planet readable
RAIN = {"sphere_emitter_radius": "{ 8.000 7.000 }", "emission": "45.000", "size": "{ 4.000 0.800 }",
        "alpha": "{ 120.000,smoke_fade 20.000 }"}
RAIN_START = 13.0
# the overcast: (texture, shader, (r, g, b, alpha), box half-size, pitch range, velocity, life, emission, size, grow,
# max) as kadavo_fx.EFFECTS; far thinner than Dromund Kaas's storm deck (alpha 105)
CLOUD = ("cloud_6", "ParticleAlphaBlend", (120, 126, 132, 55), CLOUD_CELL / 2, (0, 4), 0.06, 24.0, 0.35, 12.0, 1.3, 8)


def points():
    """emitter positions: (map x, height, map z) per cell over the planet's disc"""
    zone = np.asarray(Image.open(ZONES))
    H = zone.shape[0]
    on = zone > 0
    ys, xs = np.nonzero(on)

    def grid(cell, height):
        out = []
        for y in range(ys.min(), ys.max() + 1, cell):
            for x in range(xs.min(), xs.max() + 1, cell):
                cy, cx = np.nonzero(on[y:y + cell, x:x + cell])
                if len(cy) >= 0.3 * cell * cell:
                    out.append((x + cx.mean(), height, H - 1 - (y + cy.mean())))
        return out
    return {"hod_jab_rain": grid(RAIN_CELL, RAIN_HEIGHT), "hod_jab_overcast": grid(CLOUD_CELL, CLOUD_HEIGHT)}


def rain_particle():
    """vanilla rain_small, its keys rescaled by RAIN and its start height by RAIN_START"""
    s = open(VANILLA_RAIN, encoding="utf-8-sig").read()
    for k, v in RAIN.items():
        if k == "alpha":
            s, n = re.subn(r"alpha=\{[^}]*\}", f"alpha={v}", s)
        elif v.startswith("{"):
            s, n = re.subn(rf"(\n\s*){k}=\{{[^}}]*\}}", lambda m: m.group(1) + f"{k}={v}", s)
        else:
            s, n = re.subn(rf"(\n\s*){k}=[\d.]+", lambda m: m.group(1) + f"{k}={v}", s)
        assert n == 1, f"vanilla rain_small.asset changed: {k}"
    s, n = re.subn(r"(position=\{\s*x=[\d.]+\s*y=)[\d.]+", rf"\g<1>{RAIN_START:.3f}", s)
    assert n == 1, "vanilla rain_small.asset changed: position"
    s = s.replace('name="rain_small_file"', 'name="hod_jab_rain_file"')
    assert 'name="hod_jab_rain_file"' in s
    return "# HOD: Jabiim (jabiim_fx.py): vanilla rain_small, dimmed and scaled\n" + s


def main():
    pts = points()
    w = lambda path, text: open(path, "w", encoding="utf-8", newline="\n").write(text)
    tag = lambda text: text.replace("Dromund Kaas (dromund_kaas_fx.py)", "Jabiim (jabiim_fx.py)")
    tex, shader, (r, g, bl, a), b, (p0, p1), v, life, em, size, grow, mx = CLOUD
    w("gfx/particles/hod_jab_overcast.asset", TEMPLATE.format(
        name="hod_jab_overcast", tex=tex, shader=shader, r=r, g=g, bl=bl, a=a, b=b, p0=p0, p1=p1, v=v, life=life,
        em=em, size=size, grow=grow, mx=mx).replace("# HOD: Kadavo (kadavo_fx.py)", "# HOD: Jabiim (jabiim_fx.py)"))
    w("gfx/entities/hod_jab_overcast.gfx", tag(dk_gfx("hod_jab_overcast")))
    w("gfx/entities/hod_jab_overcast.asset", tag(dk_entity("hod_jab_overcast", "hod_jab_overcast_particle", int(b * 2))))
    w("gfx/particles/hod_jab_rain.asset", rain_particle())
    w("gfx/entities/hod_jab_rain.gfx", tag(dk_gfx("hod_jab_rain")))
    w("gfx/entities/hod_jab_rain.asset", tag(dk_entity("hod_jab_rain", "hod_jab_rain_particle", 24)))
    block = MARK[0] + "\n"
    for name, p in pts.items():
        block += f'type={{\n\ttype="{name}_entity"\n\tuse_animation=yes\n\tscale=1.000000\n'
        block += "".join(f'\tobject={{\n\t\tname="{name}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} {y:.3f} {zz:.3f} \n\t\t}}\n'
                         f'\t\trotation={{\n\t\t\t0.000 0.000 0.000 \n\t\t}}\n\t}}\n' for i, (x, y, zz) in enumerate(p))
        block += "}\n"
    block += MARK[1] + "\n"

    def fix(s):
        s = re.sub(re.escape(MARK[0]) + r".*?" + re.escape(MARK[1]) + r"\n", "", s, flags=re.S)
        s = s.rstrip("\n") + "\n" + block
        assert s.count("{") == s.count("}")
        return s
    rw("map/ambient_object.txt", fix)
    print("Jabiim monsoon:", {k: len(v) for k, v in pts.items()})


if __name__ == "__main__":
    main()
