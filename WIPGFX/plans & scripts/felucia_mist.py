"""Felucia's jungle mist: a faint white mist lying on the ground of the mountain jungles, drifting slowly. HOI4's
weather types are fixed (rain, snow, sandstorm...), so this is visual only: a particle effect on
ambient map objects (map/ambient_object.txt), always running over the native and impassable jungles.

    python "WIPGFX/plans & scripts/felucia_mist.py"

Run from the mod root after planet_terrain_gen.py --felucia (it reads the zones and the new heightmap).
"""
import os, re
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ZONES = "WIPGFX/Assets/felucia_zones.png"
SPACING = 9                 # map px between emitters
NAME = "hod_felucia_mist"
MARK = ("# HOD: Felucian jungle mist (felucia_mist.py)", "# HOD: end of Felucian jungle mist")
HAZE = (255, 255, 255)       # white mist (the amber haze read as dark smoke)

PARTICLE = """# HOD: Felucian jungle mist (felucia_mist.py): low fog banks + rising wisps, very low alpha
particle={{
	name="{name}_file"
	subsystem={{
		name="fog_bank"
		max_amount=14
		slave_particles=0
		sort="depth"
		emitter_type="point"
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
			x={r}.000
			y={g}.000
			z={b}.000
			alpha=55.000,mist_fade
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
		velocity_pitch={{ 0.000 2.000 }}
		velocity_yaw={{ 0.000 180.000 }}
		velocity=0.040
		life=24.000
		emission=0.550
		size=9.000,mist_grow
		rotation=180.000
		force=mist_wind
	}}
	subsystem={{
		name="wisps"
		max_amount=10
		slave_particles=0
		sort="depth"
		emitter_type="point"
		invert=no
		trail=no
		local_space=no
		billboard=yes
		texture={{
			file="gfx/particles/cloud_6.dds"
			x=1
			y=1
			shader="ParticleAdditive"
		}}
		color={{
			x=38.000
			y=40.000
			z=38.000
			alpha=120.000,mist_fade
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
		velocity_pitch={{ 4.000 4.000 }}
		velocity_yaw={{ 0.000 180.000 }}
		velocity=0.050
		life=16.000
		emission=0.600
		size=5.000,mist_grow
		rotation=180.000
		force=mist_wind
	}}
	animation={{
		name="mist_fade"
		start=0.000
		duration=1.000
		repeat=no
		minValue=0.000
		maxValue=1.000
		curve={{
			0.000 0.000 0.250 1.000 0.700 1.000 1.000 0.000
		}}
		op="MUL"
		time="life"
	}}
	animation={{
		name="mist_grow"
		start=0.000
		duration=1.000
		repeat=no
		minValue=0.000
		maxValue=1.000
		curve={{
			0.000 0.600 1.000 1.400
		}}
		op="MUL"
		time="life"
	}}
	force={{
		type="planar"
		name="mist_wind"
		position={{
			0.000 0.000 0.000
		}}
		direction={{
			0.100 0.020 0.040
		}}
		local_force=no
		yaw=0.000
		division=16
		amount=0.020
	}}
}}
"""


def main():
    zone = np.asarray(Image.open(ZONES))
    h = np.asarray(Image.open("map/heightmap.bmp").convert("L")).astype(float)
    H = h.shape[0]
    jungle = np.isin(zone, (2, 4))
    rng = np.random.default_rng(66)
    ground = ndi.gaussian_filter(h, 1.0)                     # mist lies on the ground itself
    pts = []
    ys, xs = np.nonzero(jungle)
    for y in range(ys.min(), ys.max() + 1, SPACING):
        for x in range(xs.min(), xs.max() + 1, SPACING):
            yy, xx = y + rng.integers(-3, 4), x + rng.integers(-3, 4)
            if 0 <= yy < H and jungle[yy, xx]:
                pts.append((xx, ground[yy, xx] / 10 + 0.15, H - 1 - yy))
    os.makedirs("gfx/particles", exist_ok=True)
    open(f"gfx/particles/{NAME}.asset", "w", encoding="utf-8", newline="\n").write(
        PARTICLE.format(name=NAME, r=HAZE[0], g=HAZE[1], b=HAZE[2]))
    open(f"gfx/entities/{NAME}.gfx", "w", encoding="utf-8", newline="\n").write(
        f'objectTypes = {{\n\t# HOD: Felucian jungle mist (felucia_mist.py)\n\tpdxparticle = {{\n\t\tname = "{NAME}_particle"\n'
        f'\t\ttype = "{NAME}_file"\n\t\tscale = 1\n\t}}\n}}\n')
    open(f"gfx/entities/{NAME}.asset", "w", encoding="utf-8", newline="\n").write(
        f'# HOD: an invisible emitter for the Felucian jungle mist (felucia_mist.py), placed by map/ambient_object.txt\n'
        # mesh-less: needs a cull radius like vanilla's weather entities, or it is culled at once and never drawn
        f'entity = {{\n\tname = "{NAME}_entity"\n\tcull_radius = 20\n\tdefault_state = "idle"\n'
        f'\tstate = {{ name = "idle" state_time = 2 looping = no\n'
        f'\t\tevent = {{ time = 0 particle = "{NAME}_particle" keep_particle = yes }}\n\t}}\n}}\n')
    objs = "".join(f'\tobject={{\n\t\tname="{NAME}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} {y:.3f} {z:.3f} \n\t\t}}\n'
                   f'\t\trotation={{\n\t\t\t0.000 {rng.uniform(0, 6.28):.3f} 0.000 \n\t\t}}\n\t}}\n'
                   for i, (x, y, z) in enumerate(pts))
    block = f'{MARK[0]}\ntype={{\n\ttype="{NAME}_entity"\n\tuse_animation=yes\n\tscale=1.000000\n{objs}}}\n{MARK[1]}\n'
    path = "map/ambient_object.txt"
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    s = re.sub(re.escape(MARK[0]) + r".*?" + re.escape(MARK[1]) + r"\n", "", s, flags=re.S)
    s = s.rstrip("\n") + "\n" + block
    assert s.count("{") == s.count("}")
    open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + (s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
    print(f"{len(pts)} mist emitters over the Felucian jungles")


if __name__ == "__main__":
    main()
