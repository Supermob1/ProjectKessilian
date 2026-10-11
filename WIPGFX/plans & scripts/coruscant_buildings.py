"""Coruscant city buildings for the map: textures (run with normal Python) + mesh conversion (run inside Blender).

  python "WIPGFX/plans & scripts/coruscant_buildings.py" textures
  blender -b --factory-startup --python "WIPGFX/plans & scripts/coruscant_buildings.py" -- meshes

Source: WIPGFX/3d/coruscant_buildings/ (star-wars-buildings-coruscant.zip: source/Buildings1.fbx = 13 towers,
textures/Facade010_2K_*). Output: gfx/models/buildings/hod_coruscant/ (PdxMeshSnow, Advanced texture layout: diffuse RGB;
normal G/A = xy, B = night emission; properties G = spec, B = metalness, A = gloss).
"""
import io, os, re, struct, sys

SRC = "WIPGFX/3d/coruscant_buildings"
OUT = "gfx/models/buildings/hod_coruscant"
TARGET_POLYS = 1500          # vanilla city meshes are 300-900 polys and are drawn hundreds of times
FOOTPRINT = 1.3              # map units across the widest side (vanilla city meshes ~1)
SHADER = "PdxMeshSnow"         # what every vanilla city mesh uses (cities.txt renderer); same textures as PdxMeshAdvanced
GROUPS = {"facade": ("Windows",), "metal": ("Metal",), "lights": ("Light",)}   # FBX material name -> our material


def save_dxt5_mips(rgba, path):
    import numpy as np
    from PIL import Image
    levels, im = [], Image.fromarray(np.asarray(rgba, np.uint8), "RGBA")
    while True:
        buf = io.BytesIO()
        im.save(buf, format="DDS", pixel_format="DXT5")
        levels.append(buf.getvalue())
        if im.size == (1, 1):
            break
        im = im.resize((max(1, im.size[0] // 2), max(1, im.size[1] // 2)), Image.BOX)
    hdr = bytearray(levels[0][:128])
    struct.pack_into("<I", hdr, 8, struct.unpack_from("<I", hdr, 8)[0] | 0x20000)
    struct.pack_into("<I", hdr, 28, len(levels))
    struct.pack_into("<I", hdr, 108, struct.unpack_from("<I", hdr, 108)[0] | 0x400008)
    with open(path, "wb") as f:
        f.write(bytes(hdr) + b"".join(l[128:] for l in levels))


def textures():
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    os.makedirs(OUT, exist_ok=True)
    tex = f"{SRC}/textures/Facade010_2K_"
    size = 1024
    col = np.array(Image.open(tex + "Color.jpg").convert("RGB").resize((size, size), Image.LANCZOS)).astype(np.float32)
    met = np.array(Image.open(tex + "Metalness.jpg").convert("L").resize((size, size), Image.LANCZOS)).astype(np.float32)
    emi = np.array(Image.open(tex + "Emission.jpg").convert("L").resize((size, size), Image.LANCZOS)).astype(np.float32)
    lum = ndi.gaussian_filter(col.mean(-1) / 255, 1.0, mode="wrap")
    gx, gy = ndi.sobel(lum, 1, mode="wrap") * 2.0, ndi.sobel(lum, 0, mode="wrap") * 2.0
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    full = lambda v: np.full((size, size), v, np.float32)
    # facade: the source is dark tinted glass (mean ~37); lift it towards Coruscant's pale grey towers
    col = np.clip(col * 2.2 + 45, 0, 255)
    save_dxt5_mips(np.dstack([col, full(255)]), f"{OUT}/hod_cor_facade_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), n[..., 0] * 127.5 + 127.5, np.clip(emi, 0, 255), 255 - (n[..., 1] * 127.5 + 127.5)]),
                   f"{OUT}/hod_cor_facade_normal.dds")
    # properties B = metalness: the shader zeroes diffuse on metal, so anything near 255 renders as a black mirror
    save_dxt5_mips(np.dstack([full(0), full(110), met * 0.15, full(110) + met * 0.2]), f"{OUT}/hod_cor_facade_properties.dds")
    # brushed metal
    s = 256
    rng = np.random.default_rng(7)
    streak = ndi.gaussian_filter(rng.random((s, s)), (0.5, 12), mode="wrap")
    streak = (streak - streak.min()) / (np.ptp(streak) + 1e-6)
    g = 120 + streak * 40
    full_s = lambda v: np.full((s, s), v, np.float32)
    save_dxt5_mips(np.dstack([g, g + 4, g + 10, full_s(255)]), f"{OUT}/hod_cor_metal_diffuse.dds")
    save_dxt5_mips(np.dstack([full_s(0), full_s(128), full_s(0), full_s(128)]), f"{OUT}/hod_cor_metal_normal.dds")
    save_dxt5_mips(np.dstack([full_s(0), full_s(130), full_s(70), full_s(130)]), f"{OUT}/hod_cor_metal_properties.dds")
    # lights: pale blue-white, fully emissive at night
    s = 64
    full_s = lambda v: np.full((s, s), v, np.float32)
    save_dxt5_mips(np.dstack([full_s(205), full_s(225), full_s(255), full_s(255)]), f"{OUT}/hod_cor_lights_diffuse.dds")
    save_dxt5_mips(np.dstack([full_s(0), full_s(128), full_s(255), full_s(128)]), f"{OUT}/hod_cor_lights_normal.dds")
    save_dxt5_mips(np.dstack([full_s(0), full_s(60), full_s(0), full_s(80)]), f"{OUT}/hod_cor_lights_properties.dds")
    # plaster for towns: warm stucco, faint blocks, scattered lit windows at night (normal B = emission)
    s = 256
    rng = np.random.default_rng(11)
    yy, xx = np.mgrid[0:s, 0:s]
    grain = ndi.gaussian_filter(rng.random((s, s)), 1.5, mode="wrap")
    grain = (grain - grain.min()) / np.ptp(grain)
    blotch = ndi.gaussian_filter(rng.random((s, s)), 10, mode="wrap")
    blotch = (blotch - blotch.min()) / np.ptp(blotch)
    # layout: 4 colour variants as 64 px rows (variant c at v = c/4 .. (c+1)/4, bottom-up); left half = walls with
    # windows, right half = roofs (no windows, no night glow). towns() maps each building into one variant.
    tints = np.array([(150, 132, 104), (132, 106, 82), (124, 122, 116), (146, 120, 82)], np.float32)
    row = tints[3 - yy // 64]
    plaster = row * (0.85 + 0.1 * grain[..., None] + 0.12 * blotch[..., None])
    roof = xx >= s // 2
    plaster *= np.where(roof, 0.8 - 0.1 * blotch, 1 - 0.12 * ((yy % 16 < 1) & ~roof))[..., None]
    win = ((xx % 16 > 5) & (xx % 16 < 10) & (yy % 16 > 5) & (yy % 16 < 11) & ~roof).astype(np.float32)
    lit = win * (ndi.zoom(rng.random((s // 16, s // 16)), 16, order=0) > 0.6)
    plaster = plaster * (1 - 0.45 * win[..., None])
    full_s = lambda v: np.full((s, s), v, np.float32)
    save_dxt5_mips(np.dstack([plaster, full_s(255)]), f"{OUT}/hod_town_plaster_diffuse.dds")
    save_dxt5_mips(np.dstack([full_s(0), full_s(128), lit * 230, full_s(128)]), f"{OUT}/hod_town_plaster_normal.dds")
    save_dxt5_mips(np.dstack([full_s(0), full_s(40), full_s(0), full_s(60)]), f"{OUT}/hod_town_plaster_properties.dds")
    print("textures written to", OUT)


def meshes(target=TARGET_POLYS, prefix="hod_cor_building"):
    target = int(target)
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie

    class Mat:   # minimal stand-in for io_pdx_mesh's parsed PDX material
        def __init__(self, key):
            self.shader = [SHADER]
            self.diff = [f"hod_cor_{key}_diffuse.dds"]
            self.n = [f"hod_cor_{key}_normal.dds"]
            self.spec = [f"hod_cor_{key}_properties.dds"]

    fbx = os.path.abspath(f"{SRC}/source/Buildings1.fbx")
    out_dir = os.path.abspath(OUT)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    names = sorted((o.name for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda n: int("".join(c for c in n if c.isdigit()) or 0))
    report = []
    for idx, name in enumerate(names, 1):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=fbx)
        for o in list(bpy.context.scene.objects):
            if o.name != name:
                bpy.data.objects.remove(o, do_unlink=True)
        obj = bpy.data.objects[name]
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # 7 FBX materials -> 3 PDX materials
        old = [s.material.name if s.material else "" for s in obj.material_slots]
        mats = {k: bie.create_shader(Mat(k), f"hod_cor_{k}", out_dir) for k in GROUPS}
        for k, m in mats.items():
            m[PDX_SHADER] = SHADER
        keys = list(GROUPS)
        remap = []
        for nm in old:
            remap.append(next((i for i, k in enumerate(keys) if any(t.lower() in nm.lower() for t in GROUPS[k])), 1))
        mi = [p.material_index for p in obj.data.polygons]
        obj.data.materials.clear()
        for k in keys:
            obj.data.materials.append(mats[k])
        for p, m in zip(obj.data.polygons, mi):
            p.material_index = remap[m] if m < len(remap) else 1

        # decimate to the city budget
        polys = len(obj.data.polygons)
        if polys > target:
            mod = obj.modifiers.new("dec", "DECIMATE")
            mod.ratio = target / polys
            bpy.ops.object.modifier_apply(modifier=mod.name)
        tri = obj.modifiers.new("tri", "TRIANGULATE")     # exporter needs tris/quads for tangents
        bpy.ops.object.modifier_apply(modifier=tri.name)
        # drop unused material slots so the exporter doesn't write empty sub-meshes
        used = sorted({p.material_index for p in obj.data.polygons})
        bpy.ops.object.material_slot_remove_unused()
        # base centred on the origin, scaled to a vanilla-like footprint
        vs = [v.co for v in obj.data.vertices]
        lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        s = FOOTPRINT / max(hi.x - lo.x, hi.y - lo.y)
        for v in obj.data.vertices:
            v.co = (v.co - centre) * s
        obj.location = (0, 0, 0)
        obj.data.name = f"{prefix}_{idx:02d}"
        out = os.path.join(out_dir, f"{prefix}_{idx:02d}.mesh")
        bie.export_meshfile(out, exp_mesh=True, exp_skel=False, exp_locs=False)
        report.append(f"{idx:02d} {name}: {polys} -> {len(obj.data.polygons)} polys, height {(hi.z - lo.z) * s:.2f}, "
                      f"materials {[keys[i] for i in used]}")
    print("\n".join(report))


LP_PREFIX = "hod_cor_tower_lp"   # low-poly towers for clusters: `meshes 800 hod_cor_tower_lp` (decimated from source)
CLUSTER_R = 1.7      # cluster radius in map units; cities.txt spawns one every 2 px, so neighbours overlap into one fabric
MIN_GAP = 0.42       # minimum distance between tower centres
VARIANTS = 4
# per distance band (1 = edge of the urban area ... 4 = downtown): candidate towers, tower count, scale, height boost
BANDS = {1: ((6, 11, 1, 9), (3, 4), (0.24, 0.32), 0.7),
         2: ((1, 2, 9, 10, 11, 13), (4, 5), (0.26, 0.34), 0.85),
         3: ((2, 3, 5, 8, 10, 12, 13), (5, 6), (0.28, 0.36), 1.0),
         4: ((3, 4, 5, 7, 8, 12), (6, 7), (0.3, 0.38), 1.15)}
# Christophsis towers (sketchfab_props.py building kind, 1.8 tall at scale 1): 07 striped, 04 octagonal, 01/00/02/03 crystal
SW = "gfx/models/buildings/hod_sw"
CHR_BANDS = {1: ((4, 7), (2, 3), (0.42, 0.55), 0.75),
             2: ((1, 4, 7), (3, 4), (0.46, 0.6), 0.85),
             3: ((0, 1, 2, 3, 4), (3, 5), (0.5, 0.68), 1.0),
             4: ((0, 1, 2, 3), (4, 5), (0.55, 0.75), 1.15)}
CLUSTER_KINDS = {   # kind: (bands, source mesh path pattern, output dir, mesh prefix, minimum gap)
    "cor": (BANDS, OUT + "/" + LP_PREFIX + "_{:02d}.mesh", OUT, "hod_cor_cluster", 0.42),
    "chr": (CHR_BANDS, SW + "/hod_bld_chr_{:02d}.mesh", SW, "hod_chr_cluster", 0.62),
}


def tex_key(m):
    """A Blender material's diffuse image name (materials imported from .mesh files), else its name."""
    return next((n.image.name for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and "diffuse" in n.image.name),
                m.name)


def clusters(kind="cor"):
    """Organic city clusters: towers scattered (Poisson-disc) inside an irregular blob, tallest at the core,
    any heading. Single towers on HOI4's spawn grid read as rows of needles; overlapping blobs hide the grid.
    kind: cor = Coruscant towers, chr = Christophsis buildings (CLUSTER_KINDS)."""
    import math
    import random
    import bpy  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    bands, src, out, prefix, min_gap = CLUSTER_KINDS[kind]
    out_dir = os.path.abspath(out)
    rng = random.Random(1138)
    report = []
    for band, (towers, (nmin, nmax), (smin, smax), boost) in bands.items():
        for v in range(1, VARIANTS + 1):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            lobes, phase = rng.choice((2, 3, 4)), rng.uniform(0, 6.283)
            pts = []
            for _ in range(400):                      # dart throwing inside a lobed blob
                if len(pts) >= rng.randint(nmin, nmax):
                    break
                a, u = rng.uniform(0, 6.283), math.sqrt(rng.random())
                r = u * CLUSTER_R * (0.75 + 0.25 * math.sin(lobes * a + phase))
                p = (r * math.cos(a), r * math.sin(a))
                if all(math.dist(p, q) >= min_gap for q in pts):
                    pts.append(p)
            parts = []
            for x, y in pts:
                before = set(bpy.data.objects)
                bie.import_meshfile(os.path.abspath(src.format(rng.choice(towers))),
                                    imp_skel=False, imp_locs=False, join_materials=False)
                new = [o for o in set(bpy.data.objects) - before if o.type == "MESH"]   # one object per material
                core = 1 - 0.55 * math.hypot(x, y) / CLUSTER_R              # tall core, low rim
                s = rng.uniform(smin, smax)
                sz = boost * core * rng.uniform(0.7, 1.2)
                rot = rng.uniform(0, 6.283)
                for obj in new:
                    obj.scale = (s, s, s * sz)
                    obj.rotation_euler[2] += rot
                    obj.location = (x, y, 0)
                parts += new
            for o in bpy.data.objects:
                o.select_set(o in parts)
            bpy.context.view_layer.objects.active = parts[0]
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            bpy.ops.object.join()
            obj = bpy.context.view_layer.objects.active
            # every import brought its own copy of its materials: fold them by diffuse texture
            first = {}
            slot_of = [first.setdefault(tex_key(m), k) for k, m in enumerate(obj.data.materials)]
            for p in obj.data.polygons:
                p.material_index = slot_of[p.material_index]
            bpy.ops.object.material_slot_remove_unused()
            name = f"{prefix}_{band}{v}"
            obj.name = obj.data.name = name
            bie.export_meshfile(os.path.join(out_dir, name + ".mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
            hz = max(c.co.z for c in obj.data.vertices)
            report.append(f"{name}: {len(pts)} towers, {len(obj.data.polygons)} tris, height {hz:.2f}")
    print("\n".join(report))


TOWN_R = 1.5        # town cluster radius (map units)
# per band: number of houses, dome share, house size range, small towers (from the low-poly set)
TOWN_BANDS = {1: (4, 0.6, (0.10, 0.18), 0), 2: (6, 0.5, (0.12, 0.22), 0), 3: (8, 0.45, (0.14, 0.26), 1),
              4: (9, 0.4, (0.16, 0.3), 2)}


def towns():
    """Small towns for worlds that aren't ecumenopolises: stucco domes and flat-roofed blocks scattered in a blob,
    a short tower or two downtown. Same spawn bands as the clusters (1 = edge ... 4 = centre)."""
    import math
    import random
    import bmesh  # type: ignore
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    out_dir = os.path.abspath(OUT)
    rng = random.Random(77)

    class Mat:
        def __init__(self, key):
            self.shader = [SHADER]
            self.diff, self.n, self.spec = ([f"hod_town_{key}_diffuse.dds"], [f"hod_town_{key}_normal.dds"],
                                            [f"hod_town_{key}_properties.dds"])

    report = []
    for band, (count, domes, (smin, smax), towers) in TOWN_BANDS.items():
        for v in range(1, VARIANTS + 1):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            pts = []
            for _ in range(500):
                if len(pts) >= count + towers:
                    break
                a, u = rng.uniform(0, 6.283), math.sqrt(rng.random())
                q = (u * TOWN_R * math.cos(a), u * TOWN_R * math.sin(a))
                if all(math.dist(q, o) >= smax * 1.6 for o in pts):
                    pts.append(q)
            parts = []
            for i, (x, y) in enumerate(pts[:towers]):          # short towers near the centre
                before = set(bpy.data.objects)
                bie.import_meshfile(os.path.join(out_dir, f"{LP_PREFIX}_{rng.choice((1, 5, 9, 11, 13)):02d}.mesh"),
                                    imp_skel=False, imp_locs=False, join_materials=False)
                for o in [o for o in set(bpy.data.objects) - before if o.type == "MESH"]:
                    sc = rng.uniform(0.16, 0.22)
                    o.scale = (sc, sc, sc * rng.uniform(0.35, 0.6))
                    o.rotation_euler[2] = rng.uniform(0, 6.283)
                    o.location = (x * 0.3, y * 0.3, 0)
                    parts.append(o)
            me = bpy.data.meshes.new("houses")
            houses = bpy.data.objects.new("houses", me)
            bpy.context.scene.collection.objects.link(houses)
            bm = bmesh.new()
            uvl = bm.loops.layers.uv.new("UVMap")

            def paint(faces, variant):
                """UVs into the variant's row of hod_town_plaster: walls (windows) left, roofs (plain) right."""
                for fc in faces:
                    fc.normal_update()
                    x0 = 0.52 if fc.normal.z > 0.6 else 0.02
                    for lp in fc.loops:
                        u, w = lp[uvl].uv
                        lp[uvl].uv = (x0 + min(max(u, 0), 1) * 0.46, variant * 0.25 + 0.02 + min(max(w, 0), 1) * 0.21)

            for x, y in pts[towers:]:
                sz = rng.uniform(smin, smax)
                variant = rng.randrange(4)
                if rng.random() < domes:                       # dome, sometimes with a smaller one next to it
                    for k in range(1 if rng.random() < 0.6 else 2):
                        r = sz * (1 if k == 0 else 0.6)
                        g = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=r, calc_uvs=True)
                        off = Vector((x, y, -r * 0.2)) + (Vector((r * 1.3, 0, 0)) if k else Vector())
                        bmesh.ops.delete(bm, geom=[w for w in g["verts"] if w.co.z < -1e-4], context="VERTS")
                        kept = [w for w in g["verts"] if w.is_valid]
                        for w in kept:
                            w.co += off
                        paint({fc for w in kept for fc in w.link_faces}, variant)
                else:                                          # flat-roofed block
                    g = bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
                    h = sz * rng.uniform(0.8, 1.8)
                    rot = rng.uniform(0, 6.283)
                    for w in g["verts"]:
                        lx, ly = w.co.x * sz * 1.6, w.co.y * sz * rng.uniform(1.0, 1.4)
                        w.co = Vector((x + lx * math.cos(rot) - ly * math.sin(rot), y + lx * math.sin(rot) + ly * math.cos(rot),
                                       (w.co.z + 0.5) * h))
                    paint({fc for w in g["verts"] for fc in w.link_faces}, variant)
            bm.to_mesh(me)
            bm.free()
            mat = bie.create_shader(Mat("plaster"), "hod_town_plaster", out_dir)
            mat[PDX_SHADER] = SHADER
            me.materials.append(mat)
            parts.append(houses)
            for o in bpy.data.objects:
                o.select_set(o in parts)
            bpy.context.view_layer.objects.active = houses
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            bpy.ops.object.join()
            obj = bpy.context.view_layer.objects.active
            tri = obj.modifiers.new("t", "TRIANGULATE")
            bpy.ops.object.modifier_apply(modifier=tri.name)
            # each tower import brought its own copies of the facade/metal/lights materials: fold by diffuse texture
            key = lambda m: next((n.image.name for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image
                                  and "diffuse" in n.image.name), m.name)
            first = {}
            slot_of = [first.setdefault(key(m), k) for k, m in enumerate(obj.data.materials)]
            for p in obj.data.polygons:
                p.material_index = slot_of[p.material_index]
            bpy.ops.object.material_slot_remove_unused()
            name = f"hod_town_{band}{v}"
            obj.name = obj.data.name = name
            bie.export_meshfile(os.path.join(out_dir, name + ".mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
            report.append(f"{name}: {len(pts)} buildings, {len(obj.data.polygons)} tris, "
                          f"height {max(c.co.z for c in obj.data.vertices):.2f}, {len(obj.data.materials)} materials")
    print("\n".join(report))


# cities.bmp palette index (painted by planet_terrain_gen.py) -> (spawn density, [mesh families mixed in])
# family: prefix -> folder; every family has <prefix>_<band><variant> meshes, except single meshes (SINGLE)
LM = "gfx/models/buildings/hod_landmarks"     # procedural families from military_buildings.py models
FAMILIES = {"hod_cor_cluster": OUT, "hod_town": OUT, "hod_chr_cluster": SW,
            "hod_kam_city": LM, "hod_man_city": LM, "hod_geo_city": LM, "hod_nab_city": LM, "hod_fel_city": LM,
            "hod_cmg_outpost": LM}
SINGLE = {"hod_bld_jasperio": SW}          # one mesh used for every band (Ewok-style treehouse village)
CITY_GROUPS = {15: (0.35, ["hod_cor_cluster"]), 0: (0.00001, ["hod_cor_cluster"]),
               1: (0.35, ["hod_cor_cluster", "hod_cor_cluster", "hod_chr_cluster"]),  # megacities: ~1/3 Christophsis
               2: (0.3, ["hod_town"]),                                                  # every other world: towns
               3: (0.35, ["hod_chr_cluster"]),                                          # Christophsis
               4: (0.15, ["hod_bld_jasperio"]),                                         # tree worlds: treehouse villages
               5: (0.2, ["hod_kam_city"]),                                              # ocean worlds: stilt domes
               6: (0.3, ["hod_man_city"]),                                              # Mandalore: domed cities
               7: (0.3, ["hod_geo_city"]),                                              # Geonosis: hive spires
               8: (0.3, ["hod_nab_city"]),                                              # Naboo: Theed-style domes
               9: (0.3, ["hod_fel_city"]),                                              # Felucia: mushroom villages
               10: (0.3, ["hod_cmg_outpost"])}                                          # Felucia: Guild outposts


def wire():
    """Write gfx/entities/hod_coruscant_buildings.{gfx,asset} and map/cities.txt for every city style."""
    meshes = {f"{pre}_{b}{v}": d for pre, d in FAMILIES.items() for b in BANDS for v in range(1, VARIANTS + 1)}
    meshes.update(SINGLE)
    with open("gfx/entities/hod_coruscant_buildings.gfx", "w", encoding="utf-8", newline="\n") as f:
        f.write("objectTypes = {\n\t# HOD: city meshes (WIPGFX/plans & scripts/coruscant_buildings.py)\n")
        for n, d in meshes.items():
            f.write(f'\tpdxmesh = {{\n\t\tname = "{n}_mesh"\n\t\tfile = "{d}/{n}.mesh"\n\t}}\n')
        f.write("}\n")
    with open("gfx/entities/hod_coruscant_buildings.asset", "w", encoding="utf-8", newline="\n") as f:
        f.write("# HOD: city meshes used by map/cities.txt\n")
        for n in meshes:
            f.write(f'\nentity = {{\n\tname = "{n}_entity"\n\tpdxmesh = "{n}_mesh"\n\tscale = 1\n}}\n')
    with open("map/cities.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write("# HOD: written by WIPGFX/plans & scripts/coruscant_buildings.py wire. map/cities.bmp (planet_terrain_gen.py)\n"
                "# picks the style per pixel: 1 megacity, 2 towns, 3 Christophsis, 4 treehouse villages,\n"
                "# 5 ocean-world stilt domes, 6 Mandalore domes, 7 Geonosis hives, 8 Naboo, 9 Felucian villages, 10 Guild outposts.\n"
                'types_source = "map/cities.bmp"\npixel_step_x = 2\npixel_step_y = 2\n')
        for idx, (dens, fams) in CITY_GROUPS.items():
            f.write(f"city_group = {{\n\tcolor_index = {idx}\n\tdensity = {format(dens, '.5f').rstrip('0')}\n"
                    "\t# sorted by distance to the edge of the urban area (map pixels): low outskirts, tall downtown\n")
            for b in BANDS:
                names = [fam if fam in SINGLE else f"{fam}_{b}{v}" for fam in fams for v in range(1, VARIANTS + 1)]
                body = "".join(f'\t\t\t"{n}_entity"\n' for n in names)
                f.write(f"\tbuilding = {{\n\t\tdistance = {b}\n\t\tmesh = {{\n{body}\t\t}}\n\t}}\n")
            f.write("}\n")
    print("wrote entities + map/cities.txt for", len(meshes), "city meshes")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"textures": textures, "meshes": meshes, "clusters": clusters, "towns": towns, "wire": wire}[args[0]](*args[1:])
