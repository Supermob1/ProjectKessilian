"""Florrum's atmosphere: sulfur geysers (steam plumes rising from the acid flats and the plains, The Clone Wars "The
Gungan General") as a particle effect on ambient map objects (the felucia_mist.py way), and its sandstorms: HOI4's
own sandstorm weather in Florrum's strategic region (192), which also slows and hurts the fighting there.

    python "WIPGFX/plans & scripts/florrum_fx.py"

Run from the mod root after florrum_map.py, planet_terrain_gen.py --florrum and military_buildings.py florrum_place
(geysers keep clear of the bases and the provinces' unit positions).
"""
import json, os, re
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ZONES, ZJSON = "WIPGFX/Assets/florrum_zones.png", "WIPGFX/Assets/florrum_zones.json"
NAME = "hod_florrum_geyser"
MARK = ("# HOD: Florrum sulfur geysers (florrum_fx.py)", "# HOD: end of Florrum sulfur geysers")
GEYSERS = {3: 9, 1: 9}         # zone (acid flats, plains) -> how many geysers
SPACING = (4.0, 2.5)           # px from other geysers and the bases, from the provinces' unit positions
REGION = "map/strategicregions/192-Florrum.txt"
# hot and dry all year, sandstorms most of the time (Wookieepedia: "hot and dry", dustbowls)
WEATHER = dict(temperature="20.0 45.0", no_phenomenon="0.400", rain_light="0.000", rain_heavy="0.000",
               sandstorm="0.600")

PARTICLE = """# HOD: Florrum sulfur geyser (florrum_fx.py): a column of yellow-white steam and a low drifting cloud
particle={{
	name="{name}_file"
	subsystem={{
		name="column"
		max_amount=24
		slave_particles=0
		sort="depth"
		emitter_type="box"
		box_emitter_x={{ -0.150 0.150 }}
		box_emitter_y={{ 0.000 0.200 }}
		box_emitter_z={{ -0.150 0.150 }}
		invert=no
		trail=no
		local_space=no
		billboard=yes
		texture={{
			file="gfx/particles/cloud_6.dds"
			x=1
			y=1
			shader="ParticleAlphaBlend"
		}}
		color={{
			x=255.000
			y=246.000
			z=196.000
			alpha=170.000,geyser_fade
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
		velocity_pitch={{ 84.000 90.000 }}
		velocity_yaw={{ 0.000 180.000 }}
		velocity=0.900
		life=3.500
		emission=6.000
		size=0.800,geyser_grow
		rotation=180.000
		force=geyser_wind
	}}
	subsystem={{
		name="cloud"
		max_amount=6
		slave_particles=0
		sort="depth"
		emitter_type="box"
		box_emitter_x={{ -0.600 0.600 }}
		box_emitter_y={{ 0.000 0.300 }}
		box_emitter_z={{ -0.600 0.600 }}
		invert=no
		trail=no
		local_space=no
		billboard=yes
		texture={{
			file="gfx/particles/cloud_6.dds"
			x=1
			y=1
			shader="ParticleAlphaBlend"
		}}
		color={{
			x=225.000
			y=220.000
			z=150.000
			alpha=110.000,geyser_fade
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
		velocity_pitch={{ 10.000 30.000 }}
		velocity_yaw={{ 0.000 180.000 }}
		velocity=0.100
		life=9.000
		emission=0.600
		size=2.500,geyser_grow
		rotation=180.000
		force=geyser_wind
	}}
	animation={{
		name="geyser_fade"
		start=0.000
		duration=1.000
		repeat=no
		minValue=0.000
		maxValue=1.000
		curve={{
			0.000 0.000 0.150 1.000 0.600 0.700 1.000 0.000
		}}
		op="MUL"
		time="life"
	}}
	animation={{
		name="geyser_grow"
		start=0.000
		duration=1.000
		repeat=no
		minValue=0.000
		maxValue=1.000
		curve={{
			0.000 0.500 1.000 2.200
		}}
		op="MUL"
		time="life"
	}}
	force={{
		type="planar"
		name="geyser_wind"
		position={{
			0.000 0.000 0.000
		}}
		direction={{
			0.100 0.000 0.050
		}}
		local_force=no
		yaw=0.000
		division=16
		amount=0.020
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


def geysers():
    zone = np.asarray(Image.open(ZONES))
    H = zone.shape[0]
    z = json.load(open(ZJSON))
    units = [tuple(v["centre"]) for v in z["provinces"].values()]
    keep_off = []
    amb = open("map/ambient_object.txt", encoding="utf-8-sig").read()
    blk = amb[amb.index("# HOD: Florrum (military_buildings.py"):amb.index("# HOD: end of Florrum\n")]
    keep_off += [(H - 1 - float(zz), float(x)) for x, zz in re.findall(r"position=\{\s*([\d.]+) [\d.-]+ ([\d.]+)", blk)]
    rng = np.random.default_rng(192)
    inland = ndi.distance_transform_edt(zone > 0) > 3
    pts = []
    for zk, n in GEYSERS.items():
        cand = np.argwhere((zone == zk) & inland)
        got = 0
        for i in rng.permutation(len(cand)):
            r, c = cand[i]
            if all((r - a) ** 2 + (c - b) ** 2 >= SPACING[0] ** 2 for a, b in keep_off + pts) and \
                    all((r - a) ** 2 + (c - b) ** 2 >= SPACING[1] ** 2 for a, b in units):
                pts.append((r, c))
                got += 1
                if got == n:
                    break
    os.makedirs("gfx/particles", exist_ok=True)
    open(f"gfx/particles/{NAME}.asset", "w", encoding="utf-8", newline="\n").write(PARTICLE.format(name=NAME))
    open(f"gfx/entities/{NAME}.gfx", "w", encoding="utf-8", newline="\n").write(
        f'objectTypes = {{\n\t# HOD: Florrum sulfur geysers (florrum_fx.py)\n\tpdxparticle = {{\n\t\tname = "{NAME}_particle"\n'
        f'\t\ttype = "{NAME}_file"\n\t\tscale = 1\n\t}}\n}}\n')
    open(f"gfx/entities/{NAME}.asset", "w", encoding="utf-8", newline="\n").write(
        f'# HOD: an invisible emitter for Florrum\'s sulfur geysers (florrum_fx.py), placed by map/ambient_object.txt\n'
        # mesh-less: needs a cull radius like vanilla's weather entities, or it is culled at once and never drawn
        f'entity = {{\n\tname = "{NAME}_entity"\n\tcull_radius = 6\n\tdefault_state = "idle"\n'
        f'\tstate = {{ name = "idle" state_time = 2 looping = no\n'
        f'\t\tevent = {{ time = 0 particle = "{NAME}_particle" keep_particle = yes }}\n\t}}\n}}\n')
    objs = "".join(f'\tobject={{\n\t\tname="{NAME}_{i}"\n\t\tposition={{\n\t\t\t{c:.3f} 0.100 {H - 1 - r:.3f} \n\t\t}}\n'
                   f'\t\trotation={{\n\t\t\t0.000 0.000 0.000 \n\t\t}}\n\t}}\n' for i, (r, c) in enumerate(pts))
    block = f'{MARK[0]}\ntype={{\n\ttype="{NAME}_entity"\n\tuse_animation=yes\n\tscale=1.000000\n{objs}}}\n{MARK[1]}\n'

    def fix(s):
        s = re.sub(re.escape(MARK[0]) + r".*?" + re.escape(MARK[1]) + r"\n", "", s, flags=re.S)
        s = s.rstrip("\n") + "\n" + block
        assert s.count("{") == s.count("}")
        return s
    rw("map/ambient_object.txt", fix)
    print(f"{len(pts)} sulfur geysers")


def weather():
    def fix(s):
        for k, v in WEATHER.items():
            s, n = re.subn(rf"(\n\s*{k}\s*=\s*)(\{{[^}}]*\}}|[\d.]+)", lambda m: m.group(1) + ("{ " + v + " }" if k == "temperature" else v), s)
            assert n, k
        return s
    rw(REGION, fix)
    print("Florrum weather:", WEATHER)


if __name__ == "__main__":
    geysers()
    weather()
