"""Etti IV's weather (Legends: "a hot, stormy and dense planet") and the Arcoplex's fires (canon: Cybot Galactica
"burning the surrounding forests" in 19 BBY): a thin storm haze drifting over the planet with lightning flashing in
cells across it (dromund_kaas_fx.py's flash, renamed), and dark smoke rising off the burnt belt (bonadan_fx.py's
smoke, its own colour). Kept thin (the user, on Dromund Kaas 2026-10-14: an opaque deck hid the planet). Purely
visual: the strategic region's weather is not touched.

    python "WIPGFX/plans & scripts/etti_iv_fx.py"

Run from the mod root after etti_iv_map.py (it reads the zones files); re-runs replace the block.
"""
import json, os, re, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kadavo_fx import TEMPLATE, rw
from dromund_kaas_fx import entity, gfx, lightning_particle

ZONES, ZJSON = "WIPGFX/Assets/etti_iv_zones.png", "WIPGFX/Assets/etti_iv_zones.json"
MARK = ("# HOD: Etti IV storm and fires (etti_iv_fx.py)", "# HOD: end of Etti IV storm and fires")
HAZE_CELL, HAZE_HEIGHT = 18, 14.0    # one haze emitter per cell (px), above the Arcoplex's ~10-unit spire
FLASH_CELL, FLASH_HEIGHT = 34, 12.0  # one lightning emitter per cell
SMOKE_KIND, SMOKE_HEIGHT = 6, 1.5    # etti_iv_map.KIND burn: one plume per burnt province
# name -> (texture, shader, (r, g, b, alpha), box half-size, pitch range, velocity, life, emission, size, grow, max)
# as kadavo_fx.EFFECTS
EFFECTS = {
    "hod_etti_haze": ("cloud_6", "ParticleAlphaBlend", (70, 78, 92, 85), HAZE_CELL / 2, (0, 4), 0.06, 22.0, 0.4, 10.0, 1.3, 10),
    "hod_etti_smoke": ("cloud_6", "ParticleAlphaBlend", (46, 40, 36, 180), 0.5, (78, 90), 0.5, 8.0, 2.0, 1.1, 3.2, 20),
}
TAG = lambda s: s.replace("Dromund Kaas (dromund_kaas_fx.py)", "Etti IV (etti_iv_fx.py)").replace(
    "Kadavo (kadavo_fx.py)", "Etti IV (etti_iv_fx.py)")


def points():
    """emitter positions (map x, height, map z): haze and lightning per cell over the disc, smoke per burnt province"""
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
    prov = json.load(open(ZJSON))["provinces"].values()
    smoke = [(c, SMOKE_HEIGHT, H - 1 - r) for r, c in (p["centre"] for p in prov if p["kind"] == SMOKE_KIND)]
    return {"hod_etti_haze": grid(HAZE_CELL, HAZE_HEIGHT), "hod_etti_lightning": grid(FLASH_CELL, FLASH_HEIGHT),
            "hod_etti_smoke": smoke}


def main():
    pts = points()
    w = lambda path, text: open(path, "w", encoding="utf-8", newline="\n").write(text)
    for name, (tex, shader, (r, g, bl, a), b, (p0, p1), v, life, em, size, grow, mx) in EFFECTS.items():
        w(f"gfx/particles/{name}.asset", TAG(TEMPLATE.format(name=name, tex=tex, shader=shader, r=r, g=g, bl=bl, a=a, b=b,
                                                              p0=p0, p1=p1, v=v, life=life, em=em, size=size, grow=grow, mx=mx)))
        w(f"gfx/entities/{name}.gfx", TAG(gfx(name)))
        w(f"gfx/entities/{name}.asset", TAG(entity(name, f"{name}_particle", max(int(b * 2), 4))))
    w("gfx/particles/hod_etti_lightning.asset", lightning_particle().replace("hod_dk_lightning_file", "hod_etti_lightning_file")
      .replace("# HOD: Dromund Kaas (dromund_kaas_fx.py)", "# HOD: Etti IV (etti_iv_fx.py)"))
    w("gfx/entities/hod_etti_lightning.gfx", TAG(gfx("hod_etti_lightning")))
    w("gfx/entities/hod_etti_lightning.asset", TAG(entity("hod_etti_lightning", "hod_etti_lightning_particle", 20)))
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
    print("Etti IV storm and fires:", {k: len(v) for k, v in pts.items()})


if __name__ == "__main__":
    main()
