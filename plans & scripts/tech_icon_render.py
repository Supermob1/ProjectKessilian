"""Tech icons from our 3D models: a 3/4 side view, transparent, then a drop shadow like the vanilla equipment icons.

  1) blender -b --factory-startup --python "plans & scripts/tech_icon_render.py" -- OUTDIR name=model[@x_degrees] [...]
     (Blender 5.2, F:/Blender Foundation/Blender 5.2/blender.exe, STNH io_pdx_mesh; .mesh / .glb / .gltf / .fbx / .stl models)
  2) python -B "plans & scripts/tech_icon_render.py" compose OUTDIR [W H]     -> OUTDIR/<name>_medium.png (+ .dds), sheet.png

Starships: set HOD_SHIP_VIEW=1 for the render, compose with 285 56.
Composition: trimmed render fitted in W x H (default 111 x 50, our tech icon size) with a 2 px margin, sitting on a soft dark
shadow (alpha blurred, offset down-right), as in the vanilla / Republic Equipment icons.
"""
import math, os, sys

VIEW = (-1.0, -0.55, 0.32)     # camera from the left side, a little in front and above (model nose = -Y)
SHIP_VIEW = (-1.0, -0.08, 0.14)  # starships: near-flat side view, as the 285 x 56 hull icons (compose OUTDIR 285 56)


def render(outdir, *pairs):
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore
    sys.path.insert(0, bpy.utils.user_resource("EXTENSIONS", path="user_default"))   # Blender 5.2 + STNH io_pdx_mesh
    os.makedirs(outdir, exist_ok=True)
    for pair in pairs:
        name, path = pair.split("=", 1)
        path, _, rx = path.partition("@")          # model@90: turn it about X first (some baked .mesh rigs lie on their back)
        for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images):  # one model at a time
            for o in list(coll): coll.remove(o)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".mesh":
            from io_pdx_mesh.pdx_blender import blender_import_export as bie  # noqa
            bie.import_meshfile(os.path.abspath(path), imp_mesh=True, imp_skel=False, imp_locs=False)
        elif ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=os.path.abspath(path))
        elif ext == ".stl":       # untextured print model: shaded in its material grey
            bpy.ops.wm.stl_import(filepath=os.path.abspath(path))
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=os.path.abspath(path))
        objs = [o for o in bpy.data.objects if o.type == "MESH"]
        # textures saved with the author's folder layout: find them by file name near the model
        root = os.path.dirname(os.path.dirname(os.path.abspath(path)))
        key = lambda f: os.path.basename(f).lower().replace("_", "").replace(" ", "")   # BaseColor ~ Base_Color
        found = {key(f): os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs}
        for i in bpy.data.images:
            if i.source == "FILE" and i.size[0] == 0 and key(i.filepath) in found:
                i.filepath = found[key(i.filepath)]
                i.reload()
        if rx:                                     # model@x or model@x,z (degrees; Alamo .alo models nose +X: @0,-90)
            x, _, z = rx.partition(",")
            for o in bpy.data.objects:
                if o.parent is None:
                    o.rotation_mode = "XYZ"        # glTF imports are quaternion: euler edits were ignored
                    o.rotation_euler.rotate_axis("X", math.radians(float(x or 0)))
                    o.rotation_euler.z += math.radians(float(z or 0))
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        centre, size = (lo + hi) / 2, (hi - lo).length
        sc = bpy.context.scene
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.display.shading.light = "STUDIO"
        sc.display.shading.color_type = "TEXTURE"
        sc.display.shading.show_cavity = True
        sc.render.film_transparent = True
        sc.render.resolution_x, sc.render.resolution_y = 1000, 1000
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = size * 1.05
        ext_x, ext_y = (hi - lo).x, (hi - lo).y     # look at the long side, whichever horizontal axis it lies on
        v = SHIP_VIEW if os.environ.get("HOD_SHIP_VIEW") else VIEW
        view = Vector(v) if ext_y >= ext_x else Vector((v[1], v[0], v[2]))
        if any(i.size[0] == 0 for i in bpy.data.images if i.source == "FILE"):   # textures missing: the materials' own colours
            sc.display.shading.color_type = "MATERIAL"
        cam.location = centre + view.normalized() * size * 3
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.clip_end = size * 10
        sc.render.filepath = os.path.abspath(os.path.join(outdir, name + "_raw.png"))
        bpy.ops.render.render(write_still=True)


def compose(outdir, W=111, H=50):
    from PIL import Image, ImageEnhance, ImageFilter
    names = sorted(f[:-8] for f in os.listdir(outdir) if f.endswith("_raw.png"))
    done = []
    for n in names:
        im = Image.open(os.path.join(outdir, n + "_raw.png")).convert("RGBA")
        im = im.crop(im.getchannel("A").getbbox())
        a0 = im.getchannel("A")       # workbench renders read dim beside the painted icons
        im = ImageEnhance.Contrast(ImageEnhance.Brightness(im.convert("RGB")).enhance(1.25)).enhance(1.1).convert("RGBA")
        im.putalpha(a0)
        k = min((W - 6) / im.width, (H - 6) / im.height)
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
        x, y = (W - 2 - im.width) // 2, (H - 2 - im.height) // 2
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        a = Image.new("L", (W, H), 0)
        a.paste(im.getchannel("A"), (x + 2, y + 2))
        a = a.filter(ImageFilter.GaussianBlur(1.6)).point(lambda v: int(v * 0.75))
        shadow.putalpha(a)
        out = shadow.copy()
        out.alpha_composite(im, (x, y))
        p = os.path.join(outdir, n + "_medium.png")
        out.save(p)
        out.save(p[:-4] + ".dds")
        done.append(out)
    # review sheet: 3x zoom on the tech-screen navy
    sheet = Image.new("RGBA", (W * 3 * min(4, len(done)), H * 3 * math.ceil(len(done) / 4)), (36, 52, 74, 255))
    for i, o in enumerate(done):
        sheet.alpha_composite(o.resize((W * 3, H * 3), Image.LANCZOS), ((i % 4) * W * 3, (i // 4) * H * 3))
    sheet.save(os.path.join(outdir, "sheet.png"))
    assert done, "no renders in " + outdir
    print("icons:", len(done))


if __name__ == "__main__":
    if "--" in sys.argv:
        a = sys.argv[sys.argv.index("--") + 1:]
        render(a[0], *a[1:])
    elif sys.argv[1:2] == ["compose"]:
        compose(sys.argv[2], *map(int, sys.argv[3:5]))
