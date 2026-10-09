"""Coruscant 3D globe shown over the planet when zoomed out (fades out up close, see HodPlanetGlobe in
gfx/FX/pdxmesh.shader). Textures with normal Python, mesh inside Blender:

  python "WIPGFX/plans & scripts/coruscant_globe.py" textures
  blender -b --factory-startup --python "WIPGFX/plans & scripts/coruscant_globe.py" -- mesh

Source: WIPGFX/3d/coruscant_planet/ (coruscant.zip). Output: gfx/models/planets/hod_coruscant_globe.mesh + DDS.
"""
import os, sys

SRC = "WIPGFX/3d/coruscant_planet"
OUT = "gfx/models/planets"
SIZE = 2048
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def textures():
    import numpy as np
    from PIL import Image
    from coruscant_buildings import save_dxt5_mips
    os.makedirs(OUT, exist_ok=True)
    t = f"{SRC}/textures/"
    rd = lambda f, mode: np.array(Image.open(t + f).convert(mode).resize((SIZE, SIZE), Image.LANCZOS)).astype(np.float32)
    albedo, emis = rd("planet_albedo.jpg", "RGB"), rd("courscant_planet_Emissive.jpg", "L")
    cloud, cop = rd("clouds_albedo.jpg", "RGB"), rd("clouds_opacity.jpg", "L")[..., None] / 255 * 0.85
    col = albedo * (1 - cop) + cloud * cop                                 # clouds baked in
    emis = emis * (1 - cop[..., 0])                                          # clouds hide the city lights
    full = lambda v: np.full((SIZE, SIZE), v, np.float32)
    save_dxt5_mips(np.dstack([col, full(255)]), f"{OUT}/hod_coruscant_globe_diffuse.dds")
    # PdxMeshAdvanced normal: G/A = xy (flat), B = emission (night-side city lights)
    save_dxt5_mips(np.dstack([full(0), full(128), emis, full(128)]), f"{OUT}/hod_coruscant_globe_normal.dds")
    save_dxt5_mips(np.dstack([full(0), full(80), full(30), full(110)]), f"{OUT}/hod_coruscant_globe_properties.dds")
    print("textures written to", OUT)


def mesh():
    import bpy  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie

    class Mat:
        shader = ["HodPlanetGlobe"]
        diff = ["hod_coruscant_globe_diffuse.dds"]
        n = ["hod_coruscant_globe_normal.dds"]
        spec = ["hod_coruscant_globe_properties.dds"]

    out_dir = os.path.abspath(OUT)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.abspath(f"{SRC}/source/courscant.fbx"))
    for o in list(bpy.context.scene.objects):
        if o.name != "planet":
            bpy.data.objects.remove(o, do_unlink=True)
    obj = bpy.data.objects["planet"]
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    tri = obj.modifiers.new("tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=tri.name)
    mat = bie.create_shader(Mat(), "hod_coruscant_globe", out_dir)
    mat[PDX_SHADER] = "HodPlanetGlobe"
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    obj.data.name = "hod_coruscant_globe"
    bie.export_meshfile(os.path.join(out_dir, "hod_coruscant_globe.mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
    print("globe mesh written:", len(obj.data.polygons), "tris")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"textures": textures, "mesh": mesh}[args[0]]()
