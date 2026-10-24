"""Blender: one textured thumbnail per .glb or .mesh (workbench, oblique) + their sizes, for a contact sheet.

  blender -b --factory-startup --python "WIPGFX/plans & scripts/glb_contact.py" -- OUT.png a.glb|a.mesh [...]
"""
import os, sys
import bpy  # type: ignore
from mathutils import Vector  # type: ignore

PX = 320


def thumb(path, out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.endswith(".mesh"):                    # the game's own format (io_pdx_mesh)
        sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
        from io_pdx_mesh.pdx_blender import blender_import_export as bie
        bie.import_meshfile(os.path.abspath(path), imp_mesh=True, imp_skel=False, imp_locs=False)
    else:
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(path))
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not obs:                                   # nothing visible in the file
        return Vector((0, 0, 0))
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c, size = (lo + hi) / 2, max(hi - lo)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.render.resolution_x = sc.render.resolution_y = PX
    sc.world = bpy.data.worlds.new("w")
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = size * 1.25
    cam.location = c + Vector((0.8, -1.0, 0.7)).normalized() * size * 3
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = size * 10
    sc.render.filepath = os.path.abspath(out)
    bpy.ops.render.render(write_still=True)
    return hi - lo


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    out_dir = os.path.splitext(args[0])[0] + "_thumbs"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "sizes.txt"), "w") as f:
        for p in args[1:]:
            try:
                d = thumb(p, os.path.join(out_dir, os.path.splitext(os.path.basename(p))[0] + ".png"))
            except Exception as e:                    # one unreadable model must not stop the sheet
                print("FAILED", p, e)
                continue
            f.write(f"{os.path.splitext(os.path.basename(p))[0]} {d.x:.1f} {d.y:.1f} {d.z:.1f}\n")
    print("thumbs in", out_dir)
