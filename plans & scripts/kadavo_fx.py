"""Kadavo's atmosphere (Wookieepedia: "the planet's atmosphere ... remained filled with smog"; The Clone Wars stills):
black smoke from the processing facility's four stacks, low grey-brown smog banks drifting over the ash plains,
vapour from the great volcanoes' summits, embers rising off the lava in the Great Crater. Particle effects on ambient
map objects (the felucia_mist.py way). Weather: cold all year (Wookieepedia: cold climate).

    python "WIPGFX/plans & scripts/kadavo_fx.py"

Run from the mod root after kadavo_map.py, planet_terrain_gen.py --kadavo and military_buildings.py kadavo_place.
"""
import json, math, os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kadavo_map as km

ZONES, ZJSON = "WIPGFX/Assets/kadavo_zones.png", "WIPGFX/Assets/kadavo_zones.json"
MARK = ("# HOD: Kadavo smoke and smog (kadavo_fx.py)", "# HOD: end of Kadavo smoke and smog")
# hod_kad_facility's chimneys, one at each corner (model x east, y north, top height; plan2.png, K = 0.0308)
STACKS = [(12.0 * math.cos(math.radians(b_)), 12.0 * math.sin(math.radians(b_)), 13.6) for b_ in (90, 210, 330)]
SMOG_CELL, SMOG_EDGE = 16, 9     # one smog emitter per cell of ash plains; px kept from space
REGION = "map/strategicregions/70-Malachor V.txt"                   # Kadavo's own strategic region (old name)
WEATHER = dict(temperature="-22.0 2.0", no_phenomenon="1.500", rain_light="0.000", rain_heavy="0.000")

# name -> (texture, shader, (r, g, b, alpha), box half-size, pitch range, velocity, life, emission, size, grow, max)
EFFECTS = {
    "hod_kadavo_smoke": ("cloud_6", "ParticleAlphaBlend", (34, 30, 28, 200), 0.25, (80, 90), 0.7, 7.0, 3.0, 1.2, 3.0, 24),
    "hod_kadavo_smog": ("cloud_6", "ParticleAlphaBlend", (128, 118, 102, 120), SMOG_CELL / 2, (0, 4), 0.04, 22.0, 0.6, 9.0, 1.5, 14),
    "hod_kadavo_vapour": ("cloud_6", "ParticleAlphaBlend", (190, 184, 172, 120), 1.0, (70, 90), 0.25, 9.0, 0.9, 2.5, 2.5, 10),
    "hod_kadavo_embers": ("cloud_6", "ParticleAdditive", (255, 120, 40, 160), 4.0, (75, 90), 0.5, 3.0, 4.0, 0.35, 0.6, 20),
}
TEMPLATE = """# HOD: Kadavo (kadavo_fx.py)
particle={{
	name="{name}_file"
	subsystem={{
		name="main"
		max_amount={mx}
		slave_particles=0
		sort="depth"
		emitter_type="box"
		box_emitter_x={{ -{b:.3f} {b:.3f} }}
		box_emitter_y={{ 0.000 0.300 }}
		box_emitter_z={{ -{b:.3f} {b:.3f} }}
		invert=no
		trail=no
		local_space=no
		billboard=yes
		texture={{
			file="gfx/particles/{tex}.dds"
			x=1
			y=1
			shader="{shader}"
		}}
		color={{
			x={r}.000
			y={g}.000
			z={bl}.000
			alpha={a}.000,{name}_fade
		}}
		position={{
			x=0.000
			y=0.000
			z=0.000
		}}
		start=0.000
		duration=-1.000
		emitter_yaw={{ 0.000 180.000 }}
		emitter_pitch={{ 0.000 0.000 }}
		velocity_pitch={{ {p0:.3f} {p1:.3f} }}
		velocity_yaw={{ 0.000 180.000 }}
		velocity={v:.3f}
		life={life:.3f}
		emission={em:.3f}
		size={size:.3f},{name}_grow
		rotation=180.000
		force={name}_wind
	}}
	animation={{
		name="{name}_fade"
		start=0.000
		duration=1.000
		repeat=no
		minValue=0.000
		maxValue=1.000
		curve={{
			0.000 0.000 0.200 1.000 0.700 0.700 1.000 0.000
		}}
		op="MUL"
		time="life"
	}}
	animation={{
		name="{name}_grow"
		start=0.000
		duration=1.000
		repeat=no
		minValue=0.000
		maxValue=1.000
		curve={{
			0.000 0.600 1.000 {grow:.3f}
		}}
		op="MUL"
		time="life"
	}}
	force={{
		type="planar"
		name="{name}_wind"
		position={{
			0.000 0.000 0.000
		}}
		direction={{
			0.100 0.000 0.040
		}}
		local_force=no
		yaw=0.000
		division=16
		amount=0.012
	}}
}}
"""


def rw(path, fn):
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    crlf = "\r\n" in s
    s = fn(s.replace("\r\n", "\n"))
    open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + (s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))


def points():
    """emitter positions per effect: (map x, height above the ground, map z)"""
    zone = np.asarray(Image.open(ZONES))
    H = zone.shape[0]
    zj = json.load(open(ZJSON))
    (pcy, pcx), R = zj["centre"], zj["radius"]
    pts = {k: [] for k in EFFECTS}
    hr, hc = pcy + km.HUB[1] * R, pcx + km.HUB[0] * R                    # the facility's hub (kadavo_place puts it there)
    for x, y, top in STACKS:
        pts["hod_kadavo_smoke"].append((hc + x, top, H - 1 - (hr - y)))
    crater = np.argwhere(zone == 3)                                       # embers off the lava, one per crater piece
    lab, n = ndi.label(zone == 3)
    for i in range(1, n + 1):
        r, c = np.argwhere(lab == i).mean(0)
        pts["hod_kadavo_embers"].append((c, 0.5, H - 1 - r))
    for name, kind, sid, n, shapes in km.FEATURES:                        # each great volcano's summit
        if kind == "volcano":
            _, u, v, *_ = shapes[0]
            r, c = pcy + v * R, pcx + u * R
            pts["hod_kadavo_vapour"].append((c, 9.0, H - 1 - r))
    plains = (zone == 1) & (ndi.distance_transform_edt(zone > 0) >= SMOG_EDGE)
    ys, xs = np.nonzero(plains)
    for y in range(ys.min(), ys.max() + 1, SMOG_CELL):
        for x in range(xs.min(), xs.max() + 1, SMOG_CELL):
            cy, cx = np.nonzero(plains[y:y + SMOG_CELL, x:x + SMOG_CELL])
            if len(cy) >= 0.3 * SMOG_CELL ** 2:
                pts["hod_kadavo_smog"].append((x + cx.mean(), 1.0, H - 1 - (y + cy.mean())))
    return pts


def main():
    pts = points()
    os.makedirs("gfx/particles", exist_ok=True)
    block = MARK[0] + "\n"
    for name, (tex, shader, (r, g, bl, a), b, (p0, p1), v, life, em, size, grow, mx) in EFFECTS.items():
        open(f"gfx/particles/{name}.asset", "w", encoding="utf-8", newline="\n").write(TEMPLATE.format(
            name=name, tex=tex, shader=shader, r=r, g=g, bl=bl, a=a, b=b, p0=p0, p1=p1, v=v, life=life, em=em,
            size=size, grow=grow, mx=mx))
        open(f"gfx/entities/{name}.gfx", "w", encoding="utf-8", newline="\n").write(
            f'objectTypes = {{\n\t# HOD: Kadavo (kadavo_fx.py)\n\tpdxparticle = {{\n\t\tname = "{name}_particle"\n'
            f'\t\ttype = "{name}_file"\n\t\tscale = 1\n\t}}\n}}\n')
        # mesh-less: needs a cull radius like vanilla's weather entities, or it is culled at once and never drawn
        open(f"gfx/entities/{name}.asset", "w", encoding="utf-8", newline="\n").write(
            f'# HOD: an invisible emitter for Kadavo (kadavo_fx.py), placed by map/ambient_object.txt\n'
            f'entity = {{\n\tname = "{name}_entity"\n\tcull_radius = {max(6, int(b * 2))}\n\tdefault_state = "idle"\n'
            f'\tstate = {{ name = "idle" state_time = 2 looping = no\n'
            f'\t\tevent = {{ time = 0 particle = "{name}_particle" keep_particle = yes }}\n\t}}\n}}\n')
        block += f'type={{\n\ttype="{name}_entity"\n\tuse_animation=yes\n\tscale=1.000000\n'
        block += "".join(f'\tobject={{\n\t\tname="{name}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} {y:.3f} {zz:.3f} \n\t\t}}\n'
                         f'\t\trotation={{\n\t\t\t0.000 0.000 0.000 \n\t\t}}\n\t}}\n' for i, (x, y, zz) in enumerate(pts[name]))
        block += "}\n"
    block += MARK[1] + "\n"

    def fix(s):
        s = re.sub(re.escape(MARK[0]) + r".*?" + re.escape(MARK[1]) + r"\n", "", s, flags=re.S)
        s = s.rstrip("\n") + "\n" + block
        assert s.count("{") == s.count("}")
        return s
    rw("map/ambient_object.txt", fix)

    def weather(s):
        for k, v in WEATHER.items():
            s, n = re.subn(rf"(\n\s*{k}\s*=\s*)(\{{[^}}]*\}}|[\d.]+)", lambda m: m.group(1) + ("{ " + v + " }" if k == "temperature" else v), s)
            assert n, k
        return s
    rw(REGION, weather)
    print("Kadavo effects:", {k: len(v) for k, v in pts.items()}, "| weather:", WEATHER)


if __name__ == "__main__":
    main()
