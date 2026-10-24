"""Blender: preview .mesh files with their diffuse texture (workbench), oblique and top-down, to a PNG.

  blender -b --factory-startup --python "WIPGFX/plans & scripts/render_mesh.py" -- OUT.png a.mesh [b.mesh ...]

Several meshes are laid out in a row, 3 units apart (or by their own size, whichever is bigger).
"""
import math, os, sys
import bpy  # type: ignore
from mathutils import Vector  # type: ignore

sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
from io_pdx_mesh.pdx_blender import blender_import_export as bie  # noqa: E402


def main(out, *meshes):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    x = 0.0
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for path in meshes:
        before = set(bpy.data.objects)
        bie.import_meshfile(os.path.abspath(path), imp_mesh=True, imp_skel=False, imp_locs=False)
        objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        bb = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        w = max(max(p.x for p in bb) - min(p.x for p in bb), 3.0)
        for o in objs:
            o.location.x += x - min(p.x for p in bb)
        bpy.context.view_layer.update()
        for o in objs:
            for c in o.bound_box:
                p = o.matrix_world @ Vector(c)
                lo = Vector(map(min, lo, p))
                hi = Vector(map(max, hi, p))
        x += w * 1.15
    for m in bpy.data.materials:                     # leaf cards: cut out by the diffuse alpha, as the game does
        nodes = m.node_tree.nodes if m.use_nodes and m.node_tree else []
        diff = next((n for n in nodes if n.type == "TEX_IMAGE" and n.image and "diffuse" in n.image.name), None)
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if diff and bsdf and "_flora_" in diff.image.name:   # foliage atlases only: buildings keep alpha for night lights
            diff.image.alpha_mode = "STRAIGHT"
            m.node_tree.links.new(diff.outputs["Alpha"], bsdf.inputs["Alpha"])
            m.node_tree.nodes.active = diff
            m.blend_method, m.alpha_threshold = "CLIP", 0.5
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.display.shading.show_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1400
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("w")
    scene.world = world
    centre = (lo + hi) / 2
    size = max((hi - lo).x, (hi - lo).y, (hi - lo).z)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    shots = []
    for name, d, scale in (("oblique", Vector((0.15, -1.0, 0.55)), 1.3), ("top", Vector((0, 0, 1)), 1.05)):
        cam.location = centre + d.normalized() * size * 3
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = size * scale
        path = out.replace(".png", f"_{name}.png")
        scene.render.filepath = os.path.abspath(path)
        bpy.ops.render.render(write_still=True)
        shots.append(path)
    print("rendered", shots)


if __name__ == "__main__":
    main(*sys.argv[sys.argv.index("--") + 1:])
