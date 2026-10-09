"""Star Wars replacements for vanilla building models.
  air base   -> launch pad complex: pillars with circular landing pads, control tower (procedural)

  python "WIPGFX/plans & scripts/military_buildings.py" textures
  blender -b --factory-startup --python "WIPGFX/plans & scripts/military_buildings.py" -- launchpad
  python "WIPGFX/plans & scripts/military_buildings.py" wire     gfx/entities/buildings.asset (vanilla copy, 2 entities
                                                                 swapped) + gfx/entities/hod_buildings.gfx
"""
import math, os, re, sys

OUT = "gfx/models/buildings/hod_launchpad"
VANILLA_ASSET = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/entities/buildings.asset"
S = 512


def textures():
    """Atlas: left half = landing pad top (polar-mapped), right half = metal panels, top strip = lit windows.
    Advanced layout: normal G/A = xy, B = night emission; properties G spec, B metal, A gloss."""
    import numpy as np
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(3)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    grime = ndi.gaussian_filter(rng.random((S, S)), 3)
    grime = (grime - grime.min()) / np.ptp(grime)
    col = np.zeros((S, S, 3), np.float32)
    emi = np.zeros((S, S), np.float32)
    # pad top: centre (128, 256) radius 120 in image space (u 0..0.5)
    r = np.hypot(xx - 128, yy - 256) / 120
    ang = np.arctan2(yy - 256, xx - 128)
    pad = np.array([88, 90, 94], np.float32) * (0.85 + 0.25 * grime[..., None])
    pad = np.where(((r > 0.78) & (r < 0.84))[..., None], [225, 225, 220], pad)                       # white ring
    hazard = (r > 0.88) & (r < 0.98) & (np.sin(ang * 18) > 0)
    pad = np.where(hazard[..., None], [210, 170, 40], pad)                                           # yellow dashes
    pad = np.where(((r > 0.3) & (r < 0.36))[..., None], [225, 225, 220], pad)
    cross = (r < 0.3) & ((np.abs(xx - 128) < 6) | (np.abs(yy - 256) < 6))
    pad = np.where(cross[..., None], [225, 225, 220], pad)
    lights = (r > 0.985) & (r < 1.0) & (np.sin(ang * 24) > 0.6)
    col[:, :256] = pad[:, :256]
    emi[:, :256] = np.where(lights, 255, 0)[:, :256]
    # metal panels (u 0.5..1), window strip on top (v 0.75..1 = image rows 0..128)
    metal = np.array([120, 124, 130], np.float32) * (0.8 + 0.3 * grime[..., None])
    metal *= 1 - 0.3 * (((xx % 64) < 2) | ((yy % 48) < 2))[..., None]
    win = (yy < 128) & ((xx % 24) > 8) & ((xx % 24) < 18) & ((yy % 32) > 10) & ((yy % 32) < 22)
    metal = np.where(win[..., None], [40, 60, 80], metal)
    col[:, 256:] = metal[:, 256:]
    emi[:, 256:] = np.where(win & (rng.random((S, S)) > -1), 200, 0)[:, 256:]
    full = lambda v: np.full((S, S), v, np.float32)
    save_dxt5_mips(np.dstack([np.clip(col, 0, 255), full(255)]), f"{OUT}/hod_launchpad_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), emi, full(128)]), f"{OUT}/hod_launchpad_normal.dds")
    save_dxt5_mips(np.dstack([full(0), full(70), full(90), full(110)]), f"{OUT}/hod_launchpad_properties.dds")
    print("textures written to", OUT)


def launchpad():
    import math
    import bmesh  # type: ignore
    import bpy  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie

    class Mat:
        def __init__(self):
            self.shader = ["PdxMeshAdvancedSnow"]
            self.diff, self.n, self.spec = (["hod_launchpad_diffuse.dds"], ["hod_launchpad_normal.dds"],
                                            ["hod_launchpad_properties.dds"])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")

    def cylinder(cx, cy, z0, z1, r, sides=20, top_pad=False):
        ring = lambda z: [bm.verts.new((cx + r * math.cos(2 * math.pi * i / sides), cy + r * math.sin(2 * math.pi * i / sides), z))
                          for i in range(sides)]
        lo, hi = ring(z0), ring(z1)
        for i in range(sides):
            j = (i + 1) % sides
            f = bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
            for loop, (u, v) in zip(f.loops, ((i / sides, 0), ((i + 1) / sides, 0), ((i + 1) / sides, 0.7), (i / sides, 0.7))):
                loop[uv].uv = (0.5 + u * 0.5, v * 0.7)                 # metal half
        top = bm.faces.new(hi)
        for loop in top.loops:
            x, y = (loop.vert.co.x - cx) / r, (loop.vert.co.y - cy) / r
            loop[uv].uv = (0.25 + x * 0.235, 0.5 + y * 0.47) if top_pad else (0.75, 0.3)
        bot = bm.faces.new(lo[::-1])
        for loop in bot.loops:
            loop[uv].uv = (0.75, 0.3)

    def box(x0, y0, z0, x1, y1, z1, windows=False):
        g = bmesh.ops.create_cube(bm, size=1.0)
        for v in g["verts"]:
            v.co.x, v.co.y, v.co.z = (x0 + (v.co.x + .5) * (x1 - x0), y0 + (v.co.y + .5) * (y1 - y0), z0 + (v.co.z + .5) * (z1 - z0))
        for f in {f for v in g["verts"] for f in v.link_faces}:
            for loop in f.loops:
                c = loop.vert.co
                along = (c.x - x0) / max(x1 - x0, 1e-6) if abs(f.normal.y) > 0.5 else (c.y - y0) / max(y1 - y0, 1e-6)
                h = (c.z - z0) / max(z1 - z0, 1e-6)
                loop[uv].uv = (0.5 + along * 0.5, (0.78 + h * 0.2) if windows else h * 0.7)

    # three pads on pillars of different heights, each on a squat plinth
    for cx, cy, h, pr in ((0.0, 0.0, 1.1, 0.85), (1.3, 0.65, 0.8, 0.6), (-0.95, 0.9, 0.62, 0.5)):
        cylinder(cx, cy, 0.0, 0.08, 0.38, 12)
        cylinder(cx, cy, 0.08, h, 0.16 + pr * 0.08, 10)
        cylinder(cx, cy, h, h + 0.08, pr, 24, top_pad=True)
    box(0.7, -1.15, 0.0, 1.05, -0.8, 1.25)                     # control tower
    box(0.62, -1.23, 1.25, 1.13, -0.72, 1.5, windows=True)     # tower cab
    box(0.1, -0.95, 1.02, 0.72, -0.85, 1.08)                   # walkway to the main pad
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("hod_launchpad")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("hod_launchpad", me)
    bpy.context.scene.collection.objects.link(obj)
    mat = bie.create_shader(Mat(), "hod_launchpad", os.path.abspath(OUT))
    mat[PDX_SHADER] = "PdxMeshAdvancedSnow"
    me.materials.append(mat)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    m = obj.modifiers.new("t", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=m.name)
    bie.export_meshfile(os.path.abspath(f"{OUT}/hod_launchpad.mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
    print(f"launchpad: {len(me.polygons)} tris")


def wire():
    """gfx/entities/buildings.asset = vanilla with the air base entity pointed at our mesh."""
    s = open(VANILLA_ASSET, encoding="utf-8-sig").read()

    def replace_entity(name, body):
        nonlocal s
        m = re.search(r'entity = \{\s*name = "%s"' % name, s)
        assert m, name
        depth, i = 0, m.start()
        while True:                                   # find the entity's closing brace
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        s = s[:m.start()] + body + s[i + 1:]

    replace_entity("building_air_base", """entity = {
	name = "building_air_base"
	pdxmesh = "hod_launchpad_mesh"
	scale = 1.4
	# HOD: launch pad complex (WIPGFX/plans & scripts/military_buildings.py)
	locator = { name = "damage_locator_01"	position = { 0.0 1.2 0.0 } }
	locator = { name = "damage_locator_02"	position = { 1.3 0.9 -0.65 } }
	locator = { name = "damage_locator_03"	position = { 0.9 1.4 1.0 } }

	default_state = "idle"
	state = { name = "idle" }
	state = { name = "damaged"
		event = { time = 0.1 node="damage_locator_01" particle = "building_damaged_particle" }
		event = { time = 0.1 node="damage_locator_02" particle = "building_damaged_particle" }
		event = { time = 0.1 node="damage_locator_03" particle = "building_damaged_particle" }
		event = { time = 0 particle = "bunker_smoke_effect" }
	}
}""")
    # factories -> Christophsis buildings (sketchfab_props.py building kind, 1.8 tall at scale 1); vanilla factory
    # is ~1.9 tall in the world. No chimney smoke on a tower.
    for ent, (mesh, scale) in FACTORIES.items():
        m = re.search(r'entity = \{\s*name = "%s".*?\n\}' % ent, s, re.S)
        assert m, ent
        block = m.group(0).replace(f'pdxmesh = "{ent}"', f'pdxmesh = "{mesh}_mesh"')
        block = re.sub(r"scale = [0-9.]+", f"scale = {scale}", block)
        block = block.replace('event = { time = 0.1 node="factorysmoke" particle = "factory_smoke_particle" }', "")
        s = s[:m.start()] + block + s[m.end():]
    open("gfx/entities/buildings.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: vanilla gfx/entities/buildings.asset with building_air_base, building_industrial_complex and\n"
        "# building_arms_factory swapped\n"
        "# (WIPGFX/plans & scripts/military_buildings.py wire)\n" + s)
    with open("gfx/entities/hod_buildings.gfx", "w", encoding="utf-8", newline="\n") as f:
        f.write('objectTypes = {\n\t# HOD: Star Wars building models (WIPGFX/plans & scripts/military_buildings.py)\n'
                f'\tpdxmesh = {{\n\t\tname = "hod_launchpad_mesh"\n\t\tfile = "{OUT}/hod_launchpad.mesh"\n\t}}\n'
                + "".join(f'\tpdxmesh = {{\n\t\tname = "{m}_mesh"\n\t\tfile = "gfx/models/buildings/hod_sw/{m}.mesh"\n\t}}\n'
                          for m in sorted({m for m, _ in FACTORIES.values()})) +
                '\tpdxmesh = {\n\t\tname = "hod_bld_jedi_temple_mesh"\n\t\tfile = "gfx/models/buildings/hod_sw/hod_bld_jedi_temple.mesh"\n\t}\n}\n')
    with open("gfx/entities/hod_landmarks.asset", "w", encoding="utf-8", newline="\n") as f:
        f.write('# HOD: landmarks placed by map/ambient_object.txt (military_buildings.py wire)\n'
                'entity = {\n\tname = "hod_jedi_temple_entity"\n\tpdxmesh = "hod_bld_jedi_temple_mesh"\n\tscale = 1\n}\n')
    print("wrote gfx/entities/buildings.asset + hod_buildings.gfx")


FACTORIES = {   # vanilla factory entity -> (our building mesh in gfx/models/buildings/hod_sw, entity scale)
    "building_industrial_complex": ("hod_bld_chr_07", 1.1),     # striped Christophsis high-rise block
    "building_arms_factory": ("hod_bld_chr_04", 1.0),           # octagonal Christophsis towers
}
LANDMARKS = {   # ambient object: (entity, state file whose centre it stands on, scale, yaw degrees)
    "hod_jedi_temple": ("hod_jedi_temple_entity", "history/states/128-Jedi Sector.txt", 1.6, 0.0),
}


def landmarks():
    """map/ambient_object.txt: (re)place each landmark at its state's centre, on the heightmap (height = px / 10)."""
    import io
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from planet_terrain_gen import load_provinces
    land, cls, pid = load_provinces()
    hgt = np.asarray(Image.open(io.BytesIO(open("map/heightmap.bmp", "rb").read())).convert("L")).astype(np.float32)
    H = pid.shape[0]
    txt = open("map/ambient_object.txt", encoding="utf-8-sig").read()
    for name, (entity, state, scale, yaw) in LANDMARKS.items():
        provs = [int(x) for x in re.search(r"provinces\s*=\s*\{([^}]*)\}", open(state, encoding="utf-8-sig").read()).group(1).split()]
        ys, xs = np.nonzero(np.isin(pid, provs))
        cy, cx = int(np.median(ys)), int(np.median(xs))
        y = hgt[cy, cx] / 10
        block = (f'type={{\n\ttype="{entity}"\n\tuse_animation=no\n\tscale={scale:.6f}\n\tobject={{\n\t\tname="{name}"\n'
                 f'\t\tposition={{\n\t\t\t{cx:.3f} {y:.3f} {H - cy:.3f} \n\t\t}}\n\t\trotation={{\n\t\t\t0.000 {math.radians(yaw):.3f} 0.000 \n\t\t}}\n\t}}\n}}\n')
        txt = re.sub(r'type=\{\s*type="%s".*?\n\}\n' % entity, "", txt, flags=re.S)     # replace an earlier placement
        txt = txt.rstrip("\n") + "\n" + block
        print(f"{name}: x {cx} z {H - cy} height {y:.1f}")
    open("map/ambient_object.txt", "w", encoding="utf-8", newline="\n").write(txt)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"textures": textures, "launchpad": launchpad, "wire": wire, "landmarks": landmarks}[args[0]]()
