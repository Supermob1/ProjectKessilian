"""Dromund Kaas's permanent storm (Legends: "the atmosphere was heavily charged with electricity to the point that
lightning was a near-constant sight in the almost perpetually clouded sky"; TOR concept art "Dromund Kaas lightning"):
a thin dark haze drifting high over the planet and lightning flashing in cells across it (the vanilla thunderstorm's
flash subsystem, its rain sheets dropped, scaled to a ~60 px planet). The user (2026-10-14) found the first version
(an opaque cloud deck + the full vanilla storms with rain) hid the planet: keep it thin.
Purely visual: the strategic region's weather is not touched (region 72 is shared, and weather changes gameplay).
Particle effects on ambient map objects (the kadavo_fx.py way, its template and helpers).

    python "WIPGFX/plans & scripts/dromund_kaas_fx.py"

Run from the mod root after dromund_kaas_map.py (it reads the zones file); re-runs replace the block.
"""
import os, re, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kadavo_fx import TEMPLATE, rw

ZONES = "WIPGFX/Assets/dromund_kaas_zones.png"
MARK = ("# HOD: Dromund Kaas storm (dromund_kaas_fx.py)", "# HOD: end of Dromund Kaas storm")
HAZE_CELL, HAZE_HEIGHT = 18, 26.0    # one haze emitter per cell (px); height: above the citadel's 22-unit tower
FLASH_CELL, FLASH_HEIGHT = 36, 16.0  # one lightning emitter per cell
# the haze: (texture, shader, (r, g, b, alpha), box half-size, pitch range, velocity, life, emission, size, grow, max)
# as kadavo_fx.EFFECTS
HAZE = ("cloud_6", "ParticleAlphaBlend", (48, 54, 76, 105), HAZE_CELL / 2, (0, 4), 0.05, 24.0, 0.45, 10.0, 1.3, 10)
# user: alpha 150 hid the planet, 60 was invisible; 105 in between
VANILLA_STORM = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/particles/environment/lightning_storm.asset"
# the flash, scaled (vanilla: radius 25, size 55, alpha 80, centred 25 up and 30 out)
FLASH = {"sphere_emitter_radius": "{ 8.000 6.000 }", "size": "{ 16.000 8.000 }", "alpha": "{ 45.000,flashing 15.000 }"}
LEFTOVERS = ["hod_dk_storm", "hod_dk_stormclouds", "hod_dk_storm_small"]   # entity files of the first version


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
    return {"hod_dk_stormdeck": grid(HAZE_CELL, HAZE_HEIGHT), "hod_dk_lightning": grid(FLASH_CELL, FLASH_HEIGHT)}


def blocks(s, key):
    """[(start, end)] of the top-level `key={...}` blocks of a particle file"""
    out, i = [], s.find(key + "={")
    while i >= 0:
        depth, j = 0, s.index("{", i)
        while True:
            depth += {"{": 1, "}": -1}.get(s[j], 0)
            j += 1
            if depth == 0:
                break
        out.append((i, j))
        i = s.find(key + "={", j)
    return out


def lightning_particle():
    """the vanilla thunderstorm with only its lightning_flash subsystem, scaled by FLASH"""
    s = open(VANILLA_STORM, encoding="utf-8-sig").read()
    subs = blocks(s, "subsystem")
    keep = [(a, b) for a, b in subs if 'name="lightning_flash"' in s[a:b]]
    assert len(keep) == 1, "vanilla lightning_storm.asset changed: no single lightning_flash subsystem"
    a, b = keep[0]
    flash = s[a:b]
    for k, v in FLASH.items():
        flash, n = re.subn(rf"(\n\s*){k}=\{{[^}}]*\}}", lambda m: m.group(1) + f"{k}={v}", flash)
        assert n == 1, k
    flash = re.sub(r"(position=\{\s*x=)[\d.]+(\s*y=)[\d.]+(\s*z=)[\d.]+", r"\g<1>0.000\g<2>0.000\g<3>0.000", flash)
    rest = s[:subs[0][0]] + flash + s[subs[-1][1]:]                       # head + the flash + the animations
    return ("# HOD: Dromund Kaas (dromund_kaas_fx.py): vanilla lightning_storm's flashes only, scaled\n"
            + rest.replace('name="lightning_storm_file"', 'name="hod_dk_lightning_file"'))


def entity(name, particle, cull):
    # mesh-less: needs a cull radius like vanilla's weather entities, or it is culled at once and never drawn
    return (f'# HOD: an invisible emitter for Dromund Kaas (dromund_kaas_fx.py), placed by map/ambient_object.txt\n'
            f'entity = {{\n\tname = "{name}_entity"\n\tcull_radius = {cull}\n\tdefault_state = "idle"\n'
            f'\tstate = {{ name = "idle" state_time = 2 looping = no\n'
            f'\t\tevent = {{ time = 0 particle = "{particle}" keep_particle = yes }}\n\t}}\n}}\n')


def gfx(name):
    return (f'objectTypes = {{\n\t# HOD: Dromund Kaas (dromund_kaas_fx.py)\n\tpdxparticle = {{\n\t\tname = "{name}_particle"\n'
            f'\t\ttype = "{name}_file"\n\t\tscale = 1\n\t}}\n}}\n')


def main():
    pts = points()
    tex, shader, (r, g, bl, a), b, (p0, p1), v, life, em, size, grow, mx = HAZE
    w = lambda path, text: open(path, "w", encoding="utf-8", newline="\n").write(text)
    w("gfx/particles/hod_dk_stormdeck.asset", TEMPLATE.format(
        name="hod_dk_stormdeck", tex=tex, shader=shader, r=r, g=g, bl=bl, a=a, b=b, p0=p0, p1=p1, v=v, life=life,
        em=em, size=size, grow=grow, mx=mx).replace("# HOD: Kadavo (kadavo_fx.py)", "# HOD: Dromund Kaas (dromund_kaas_fx.py)"))
    w("gfx/entities/hod_dk_stormdeck.gfx", gfx("hod_dk_stormdeck"))
    w("gfx/entities/hod_dk_stormdeck.asset", entity("hod_dk_stormdeck", "hod_dk_stormdeck_particle", int(b * 2)))
    w("gfx/particles/hod_dk_lightning.asset", lightning_particle())
    w("gfx/entities/hod_dk_lightning.gfx", gfx("hod_dk_lightning"))
    w("gfx/entities/hod_dk_lightning.asset", entity("hod_dk_lightning", "hod_dk_lightning_particle", 20))
    for name in LEFTOVERS:                                                # this script's own first-version files
        if os.path.exists(f"gfx/entities/{name}.asset"):
            os.remove(f"gfx/entities/{name}.asset")
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
    print("Dromund Kaas storm:", {k: len(v) for k, v in pts.items()})


if __name__ == "__main__":
    main()
