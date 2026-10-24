"""Bonadan's polluted air (Legends: a "polluted" climate; plant life killed by "abundant pollutants"; the weather-control
station's sweeper storms "cleaned the polluted air"): a thin, low yellow-brown smog drifting over the planet and black
smoke rising off the foundries and Refinery Row. Kept thin (the user, on Dromund Kaas 2026-10-14: an opaque deck hid
the planet). Purely visual: the strategic region's weather is not touched.
Particle effects on ambient map objects (the kadavo_fx.py way; dromund_kaas_fx.py's emitter entities).

    python "WIPGFX/plans & scripts/bonadan_fx.py"

Run from the mod root after bonadan_map.py (it reads the zones files); re-runs replace the block.
"""
import json, os, re, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kadavo_fx import TEMPLATE, rw
from dromund_kaas_fx import entity, gfx

ZONES, ZJSON = "WIPGFX/Assets/bonadan_zones.png", "WIPGFX/Assets/bonadan_zones.json"
MARK = ("# HOD: Bonadan smog and smoke (bonadan_fx.py)", "# HOD: end of Bonadan smog and smoke")
SMOG_CELL, SMOG_HEIGHT = 16, 3.0     # one smog emitter per cell (px), low over the ground
SMOKE_KINDS, SMOKE_HEIGHT = {4, 5}, 2.2   # bonadan_map.KIND: foundries, Refinery Row; one plume per province
# name -> (texture, shader, (r, g, b, alpha), box half-size, pitch range, velocity, life, emission, size, grow, max)
# as kadavo_fx.EFFECTS
EFFECTS = {
    "hod_bon_smog": ("cloud_6", "ParticleAlphaBlend", (156, 134, 92, 95), SMOG_CELL / 2, (0, 4), 0.04, 22.0, 0.5, 9.0, 1.4, 12),
    "hod_bon_smoke": ("cloud_6", "ParticleAlphaBlend", (36, 32, 28, 190), 0.4, (80, 90), 0.6, 7.0, 2.5, 1.0, 3.0, 20),
}
TAG = lambda s: s.replace("Dromund Kaas (dromund_kaas_fx.py)", "Bonadan (bonadan_fx.py)").replace(
    "Kadavo (kadavo_fx.py)", "Bonadan (bonadan_fx.py)")


def points():
    """emitter positions (map x, height, map z): smog per cell over the disc, smoke per foundry / refinery province"""
    zone = np.asarray(Image.open(ZONES))
    H = zone.shape[0]
    on = zone > 0
    ys, xs = np.nonzero(on)
    smog = []
    for y in range(ys.min(), ys.max() + 1, SMOG_CELL):
        for x in range(xs.min(), xs.max() + 1, SMOG_CELL):
            cy, cx = np.nonzero(on[y:y + SMOG_CELL, x:x + SMOG_CELL])
            if len(cy) >= 0.3 * SMOG_CELL ** 2:
                smog.append((x + cx.mean(), SMOG_HEIGHT, H - 1 - (y + cy.mean())))
    prov = json.load(open(ZJSON))["provinces"].values()
    smoke = [(c, SMOKE_HEIGHT, H - 1 - r) for r, c in (p["centre"] for p in prov if p["kind"] in SMOKE_KINDS)]
    return {"hod_bon_smog": smog, "hod_bon_smoke": smoke}


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
    print("Bonadan smog and smoke:", {k: len(v) for k, v in pts.items()})


if __name__ == "__main__":
    main()
