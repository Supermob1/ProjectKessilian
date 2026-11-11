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


def sharpness(im):
    """Laplacian variance of the opaque pixels: drops when the sprite goes soft."""
    import numpy as np
    g = np.asarray(im.convert("L"), float)
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap[np.asarray(im.getchannel("A"))[1:-1, 1:-1] > 200].var())


def emboss(im, angle=130, depth=0.35):
    """Bevel lit from `angle` degrees (Photoshop convention: 0 = right, 90 = up); height = alpha + luminance."""
    import numpy as np
    from PIL import Image, ImageFilter
    a = np.asarray(im.getchannel("A"), float) / 255
    h = np.asarray(Image.fromarray(np.uint8(255 * (0.6 * a + 0.4 * a * np.asarray(im.convert("L"), float) / 255)))
                   .filter(ImageFilter.GaussianBlur(0.7)), float) / 255
    gy, gx = np.gradient(h)
    t = math.radians(angle)
    shade = -(gx * math.cos(t) - gy * math.sin(t))           # image y points down
    rgb = np.asarray(im.convert("RGB"), float) + 255 * depth * np.clip(shade * 4, -1, 1)[..., None]
    out = Image.fromarray(np.uint8(np.clip(rgb, 0, 255)))
    out.putalpha(im.getchannel("A"))
    return out


# user 2026-11-10: legged things lose their legs, the icon shows the top part. Icon-name substring -> share of the
# model's height kept from the top (auto leg detection failed: 3/4-view legs are as thick as the bodies).
LEGS = {"atte": 0.7, "atrt": 0.55, "atxt": 0.6, "atpt": 0.6, "atap": 0.6, "atst": 0.55, "atat": 0.6, "atact": 0.6,
        "lance": 0.55, "spha": 0.7, "spmat": 0.7, "tr_ataa": 0.6, "dsd": 0.82, "crab": 0.6, "lr57": 0.6, "espo": 0.6,
        "protodeka": 0.6, "octuptarra": 0.6, "umbaran_hmc": 0.6, "scorpenek": 0.6, "og9": 0.6,
        "deka": 0.6, "cis_b2": 0.55, "mow_b3": 0.55, "raw_arc": 0.55, "commando": 0.55, "shock": 0.55}


def crop_legs(im, name):
    keep = next((v for k, v in LEGS.items() if k in name.lower()), None)
    return im.crop((0, 0, im.width, round(keep * im.height))) if keep else im


def compose(outdir, W=111, H=50):
    """Renders -> icons: trim, crop legs, brighten, then style()."""
    from PIL import Image, ImageEnhance
    names = sorted(f[:-8] for f in os.listdir(outdir) if f.endswith("_raw.png"))
    done = []
    for n in names:
        im = Image.open(os.path.join(outdir, n + "_raw.png")).convert("RGBA")
        im = im.crop(im.getchannel("A").getbbox())
        im = crop_legs(im, n)
        im = im.crop(im.getchannel("A").getbbox())
        a0 = im.getchannel("A")       # workbench renders read dim beside the painted icons
        im = ImageEnhance.Contrast(ImageEnhance.Brightness(im.convert("RGB")).enhance(1.25)).enhance(1.1).convert("RGBA")
        im.putalpha(a0)
        out = style(im, W, H, n)
        p = os.path.join(outdir, n + "_medium.png")
        out.save(p)
        out.save(p[:-4] + ".dds")
        done.append(out)
    sheet(outdir, done, W, H)


def restyle(outdir, *paths):
    """Existing 2D icons (painted art, no model) -> same canvas size, old soft drop shadow removed, then style()."""
    from PIL import Image
    os.makedirs(outdir, exist_ok=True)
    for p in paths:
        im = Image.open(p).convert("RGBA")
        W, H = im.size
        px = im.load()
        for j in range(H):                 # old baked shadow: dark and see-through
            for i in range(W):
                r, g, b, a = px[i, j]
                if a < 200 and r + g + b < 90:
                    px[i, j] = (0, 0, 0, 0)
        box = im.getchannel("A").point(lambda v: 255 * (v > 24)).getbbox()
        if not box:
            print("  ! empty:", p)
            continue
        n = os.path.splitext(os.path.basename(p))[0]
        style(im.crop(box), W, H, n, grow=False, margin=6).save(os.path.join(outdir, n + ".png"))
    print("restyled:", len(paths))


def style(im, W, H, n, grow=True, margin=8):
    """Steps (2026-11-10 user recipe): fit, unblur, emboss 130deg, small shadow 135deg, dark glow outline, artifact + blur checks."""
    from PIL import Image, ImageFilter
    # 1) fit, leaving 4 px for the glow and shadow (painted art is never blown up: that would blur it)
    k = min((W - margin) / im.width, (H - margin) / im.height, 9 if grow else 1)
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    # 2) unblur: LANCZOS downscale softens edges
    a = im.getchannel("A")
    im = im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1, percent=110, threshold=1)).convert("RGBA")
    im.putalpha(a.point(lambda v: 0 if v < 24 else min(255, v * 5 // 4)))   # crisp silhouette, no grey fringe
    sharp0 = sharpness(im)
    # 3) emboss at 130 deg
    im = emboss(im, 130)
    x, y = (W - 2 - im.width) // 2, (H - 2 - im.height) // 2    # 1 px up-left: room for the 135 deg shadow
    A = Image.new("L", (W, H), 0)
    A.paste(im.getchannel("A"), (x, y))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 4) small shadow at 135 deg (light top-left -> falls down-right)
    sh = Image.new("L", (W, H), 0)
    sh.paste(A.crop((0, 0, W - 2, H - 2)), (2, 2))
    out.putalpha(sh.filter(ImageFilter.GaussianBlur(1.0)).point(lambda v: v * 3 // 5))
    # 5) dark glow = 1 px outline
    glow = A.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.6)).point(lambda v: min(255, v * 2))
    out.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (W, H), 8)] * 3, glow.point(lambda v: v * 4 // 5))))
    out.alpha_composite(im, (x, y))
    # 6) artifacts: stray near-invisible pixels, effects clipped at the frame
    out.putalpha(out.getchannel("A").point(lambda v: 0 if v < 6 else v))
    edge = [out.getpixel((i, j))[3] for i in range(W) for j in (0, H - 1)] + \
           [out.getpixel((i, j))[3] for j in range(H) for i in (0, W - 1)]
    if max(edge) > 100:                    # the glow's faint tail (<100) may touch the frame
        print("  ! %s: clipped at the frame" % n)
    # 7) still unblurred?
    s = sharpness(out.crop((x, y, x + im.width, y + im.height)))
    if s < 0.8 * sharp0:
        print("  ! %s: went soft (%.0f -> %.0f)" % (n, sharp0, s))
    return out


def sheet(outdir, done, W, H):
    from PIL import Image
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
    elif sys.argv[1:2] == ["restyle"]:     # restyle OUTDIR icon.dds [...] -> OUTDIR/<name>.png, originals untouched
        restyle(sys.argv[2], *sys.argv[3:])
