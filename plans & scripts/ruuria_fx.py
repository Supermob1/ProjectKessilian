"""Ruuria's air (Legends: "warm and humid", a jungle world): a thin, low, pale-green mist drifting over the jungle and
the pink rivers' delta. Kept thin (the user, on Dromund Kaas 2026-10-14: an opaque deck hid the planet). Purely
visual: the strategic region's weather is not touched. Particle effects on ambient map objects (bonadan_fx.py's way).

    python "WIPGFX/plans & scripts/ruuria_fx.py"

Run from the mod root after ruuria_map.py (it reads the zones file); re-runs replace the block.
"""
import os, re, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kadavo_fx import TEMPLATE, rw
from dromund_kaas_fx import entity, gfx

ZONES = "WIPGFX/Assets/ruuria_zones.png"
MARK = ("# HOD: Ruuria mist (ruuria_fx.py)", "# HOD: end of Ruuria mist")
CELL, HEIGHT, COVER = 16, 2.5, 0.4   # one emitter per cell (px) that is at least COVER jungle / delta, low over the trees
MIST_ZONES = (1, 7)                  # ruuria_map.KIND: jungle, delta
# (texture, shader, (r, g, b, alpha), box half-size, pitch range, velocity, life, emission, size, grow, max) as
# kadavo_fx.EFFECTS
MIST = ("cloud_6", "ParticleAlphaBlend", (200, 216, 196, 70), CELL / 2, (0, 4), 0.03, 22.0, 0.45, 8.0, 1.4, 12)
TAG = lambda s: s.replace("Dromund Kaas (dromund_kaas_fx.py)", "Ruuria (ruuria_fx.py)").replace(
    "Kadavo (kadavo_fx.py)", "Ruuria (ruuria_fx.py)")


def points():
    zone = np.asarray(Image.open(ZONES))
    H = zone.shape[0]
    on = np.isin(zone, MIST_ZONES)
    ys, xs = np.nonzero(on)
    out = []
    for y in range(ys.min(), ys.max() + 1, CELL):
        for x in range(xs.min(), xs.max() + 1, CELL):
            cy, cx = np.nonzero(on[y:y + CELL, x:x + CELL])
            if len(cy) >= COVER * CELL * CELL:
                out.append((x + cx.mean(), HEIGHT, H - 1 - (y + cy.mean())))
    return out


def main():
    pts, name = points(), "hod_ruu_mist"
    tex, shader, (r, g, bl, a), b, (p0, p1), v, life, em, size, grow, mx = MIST
    w = lambda path, text: open(path, "w", encoding="utf-8", newline="\n").write(text)
    w(f"gfx/particles/{name}.asset", TAG(TEMPLATE.format(name=name, tex=tex, shader=shader, r=r, g=g, bl=bl, a=a, b=b,
                                                          p0=p0, p1=p1, v=v, life=life, em=em, size=size, grow=grow, mx=mx)))
    w(f"gfx/entities/{name}.gfx", TAG(gfx(name)))
    w(f"gfx/entities/{name}.asset", TAG(entity(name, f"{name}_particle", int(b * 2))))
    block = (MARK[0] + f'\ntype={{\n\ttype="{name}_entity"\n\tuse_animation=yes\n\tscale=1.000000\n'
             + "".join(f'\tobject={{\n\t\tname="{name}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} {y:.3f} {zz:.3f} \n\t\t}}\n'
                       f'\t\trotation={{\n\t\t\t0.000 0.000 0.000 \n\t\t}}\n\t}}\n' for i, (x, y, zz) in enumerate(pts))
             + "}\n" + MARK[1] + "\n")

    def fix(s):
        s = re.sub(re.escape(MARK[0]) + r".*?" + re.escape(MARK[1]) + r"\n", "", s, flags=re.S)
        s = s.rstrip("\n") + "\n" + block
        assert s.count("{") == s.count("}")
        return s
    rw("map/ambient_object.txt", fix)
    print("Ruuria mist:", len(pts), "emitters")


if __name__ == "__main__":
    main()
