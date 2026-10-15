"""Lola Sayu's fire (canon: lava cracks "glowing with the heat of the lava", the Sulfur Sea, a world "appearing with a
beautiful purple glow from its orbit"): embers rising off the Sulfur Sea and the lava lakes, and a thin violet sulfur
haze drifting over the planet. Kept thin (the user, on Dromund Kaas 2026-10-14: an opaque deck hid the planet).
Purely visual: the strategic region's weather is not touched. Particle effects on ambient map objects (kadavo_fx.py's
embers, dromund_kaas_fx.py's emitter entities).

    python "WIPGFX/plans & scripts/lola_sayu_fx.py"

Run from the mod root after lola_sayu_map.py (it reads the zones file); re-runs replace the block.
"""
import os, re, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kadavo_fx import TEMPLATE, rw
from dromund_kaas_fx import entity, gfx

ZONES = "WIPGFX/Assets/lola_sayu_zones.png"
MARK = ("# HOD: Lola Sayu fire and haze (lola_sayu_fx.py)", "# HOD: end of Lola Sayu fire and haze")
LAVA = (5, 6)                        # lola_sayu_map.KIND: lava lakes, Sulfur Sea
EMBER_CELL, EMBER_HEIGHT = 6, 0.5    # one ember emitter per cell (px) that is mostly lava
HAZE_CELL, HAZE_HEIGHT = 14, 7.0     # one haze emitter per cell over the planet, above the Citadel's crag
# name -> (texture, shader, (r, g, b, alpha), box half-size, pitch range, velocity, life, emission, size, grow, max)
# as kadavo_fx.EFFECTS
EFFECTS = {
    "hod_lola_embers": ("cloud_6", "ParticleAdditive", (255, 150, 50, 150), EMBER_CELL / 2, (75, 90), 0.5, 3.0, 4.0,
                        0.3, 0.6, 20),
    "hod_lola_haze": ("cloud_6", "ParticleAlphaBlend", (150, 110, 170, 70), HAZE_CELL / 2, (0, 4), 0.04, 22.0, 0.4,
                      8.0, 1.4, 10),
}
TAG = lambda s: s.replace("Dromund Kaas (dromund_kaas_fx.py)", "Lola Sayu (lola_sayu_fx.py)").replace(
    "Kadavo (kadavo_fx.py)", "Lola Sayu (lola_sayu_fx.py)")


def grid(on, cell, height, cover, H):
    ys, xs = np.nonzero(on)
    out = []
    for y in range(ys.min(), ys.max() + 1, cell):
        for x in range(xs.min(), xs.max() + 1, cell):
            cy, cx = np.nonzero(on[y:y + cell, x:x + cell])
            if len(cy) >= cover * cell * cell:
                out.append((x + cx.mean(), height, H - 1 - (y + cy.mean())))
    return out


def main():
    zone = np.asarray(Image.open(ZONES))
    H = zone.shape[0]
    pts = {"hod_lola_embers": grid(np.isin(zone, LAVA), EMBER_CELL, EMBER_HEIGHT, 0.5, H),
           "hod_lola_haze": grid(zone > 0, HAZE_CELL, HAZE_HEIGHT, 0.3, H)}
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
    print("Lola Sayu fire and haze:", {k: len(v) for k, v in pts.items()})


if __name__ == "__main__":
    main()
