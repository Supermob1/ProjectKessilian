"""Umbara's dusk and glow (canon: the shadow world, its plant life bioluminescent; the user, 2026-10-19: "always in the
dark and everything is bioluminescent"): glowing spores in magenta and red drifting up out of the jungle all over the
planet, and a thin dark haze over it. Goes with the ground's own dusk and glowing specks (pdxmap.shader, atlas slot 20)
and the glowing flora (flora_props 167-169, 173). Kept thin (the user, on Dromund Kaas 2026-10-14: an opaque deck hid
the planet). Purely visual: the strategic region's weather is not touched.

    python "WIPGFX/plans & scripts/umbara_fx.py"

Run from the mod root after umbara_map.py (it reads the zones file); re-runs replace the block.
"""
import os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kadavo_fx import TEMPLATE, rw
from dromund_kaas_fx import entity, gfx

ZONES = "WIPGFX/Assets/umbara_zones.png"
MARK = ("# HOD: Umbara dusk and glow (umbara_fx.py)", "# HOD: end of Umbara dusk and glow")
SPORE_CELL, SPORE_HEIGHT, EDGE = 10, 1.2, 5     # one spore emitter per cell (px), low over the ground; px from space
HAZE_CELL, HAZE_HEIGHT = 18, 9.0                # one haze emitter per cell, above the 22-unit capital's middle
# name -> (texture, shader, (r, g, b, alpha), box half-size, pitch range, velocity, life, emission, size, grow, max)
# as kadavo_fx.EFFECTS
EFFECTS = {
    "hod_umb_spores": ("cloud_6", "ParticleAdditive", (255, 90, 230, 200), SPORE_CELL / 2, (60, 90), 0.12, 7.0, 3.0,
                       0.22, 0.8, 26),
    "hod_umb_spores_red": ("cloud_6", "ParticleAdditive", (255, 90, 50, 190), SPORE_CELL / 2, (60, 90), 0.1, 8.0,
                              2.0, 0.26, 0.8, 20),
    "hod_umb_haze": ("cloud_6", "ParticleAlphaBlend", (16, 20, 40, 70), HAZE_CELL / 2, (0, 4), 0.04, 24.0, 0.4, 10.0,
                     1.3, 10),
}
TAG = lambda s: s.replace("Dromund Kaas (dromund_kaas_fx.py)", "Umbara (umbara_fx.py)").replace(
    "Kadavo (kadavo_fx.py)", "Umbara (umbara_fx.py)")


def points():
    """emitter positions (map x, height, map z): spores per small cell inland, haze per big cell over the disc"""
    zone = np.asarray(Image.open(ZONES))
    H = zone.shape[0]
    on = zone > 0
    inland = ndi.distance_transform_edt(on) > EDGE
    ys, xs = np.nonzero(on)

    def grid(mask, cell, height, share):
        out = []
        for y in range(ys.min(), ys.max() + 1, cell):
            for x in range(xs.min(), xs.max() + 1, cell):
                cy, cx = np.nonzero(mask[y:y + cell, x:x + cell])
                if len(cy) >= share * cell * cell:
                    out.append((x + cx.mean(), height, H - 1 - (y + cy.mean())))
        return out
    spores = grid(inland, SPORE_CELL, SPORE_HEIGHT, 0.5)
    return {"hod_umb_spores": spores[0::2], "hod_umb_spores_red": spores[1::2],
            "hod_umb_haze": grid(on, HAZE_CELL, HAZE_HEIGHT, 0.3)}


def main():
    pts = points()
    w = lambda path, text: open(path, "w", encoding="utf-8", newline="\n").write(text)
    for name, (tex, shader, (r, g, bl, a), b, (p0, p1), v, life, em, size, grow, mx) in EFFECTS.items():
        w(f"gfx/particles/{name}.asset", TAG(TEMPLATE.format(name=name, tex=tex, shader=shader, r=r, g=g, bl=bl, a=a, b=b,
                                                              p0=p0, p1=p1, v=v, life=life, em=em, size=size, grow=grow, mx=mx)))
        w(f"gfx/entities/{name}.gfx", TAG(gfx(name)))
        w(f"gfx/entities/{name}.asset", TAG(entity(name, f"{name}_particle", max(int(b * 2), 4))))
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
    print("Umbara dusk and glow:", {k: len(v) for k, v in pts.items()})


if __name__ == "__main__":
    main()
