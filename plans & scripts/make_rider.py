"""A seated clone trooper for walkers with a rider (AT-RT): pose the game trooper mesh, bake it, save a .glb.

    blender(5.2) -b --factory-startup --python "plans & scripts/make_rider.py" -- <trooper.mesh> <out.glb> [preview.png]

Run from the mod root. The glb has the pose baked in, nose -Y, the pelvis (Hip bone) at the origin; unit_models.py
(spec rider=...) scales it and sits it on the saddle. Pose = world-space swings about each bone's head.
"""
import math, os, sys
import bpy  # type: ignore
from mathutils import Matrix, Vector  # type: ignore
sys.path.insert(0, bpy.utils.user_resource("EXTENSIONS", path="user_default"))
from io_pdx_mesh.pdx_blender import blender_import_export as bie  # noqa: E402

# bone: [(world axis, degrees), ...] applied in order, parents first (- about X swings a limb forward, to -Y)
POSE = [
    ("LeftUpLeg", [("X", -80), ("Y", -18)]), ("RightUpLeg", [("X", -80), ("Y", 18)]),
    ("LeftLeg", [("X", 85)]), ("RightLeg", [("X", 85)]),
    ("LeftFoot", [("X", -10)]), ("RightFoot", [("X", -10)]),
    ("back_mid", [("X", -12)]),
    ("LeftArm", [("Y", 35), ("X", -45)]), ("RightArm", [("Y", -35), ("X", -45)]),
    ("LeftForeArm", [("X", -35)]), ("RightForeArm", [("X", -35)]),
]


def main(src, out, preview=None):
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.armatures):
        for o in list(coll):
            coll.remove(o)
    bie.import_meshfile(os.path.abspath(src), imp_mesh=True, imp_skel=True, imp_locs=False)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = [o for o in bpy.data.objects if o.type == "MESH" and o.vertex_groups]
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for bone, swings in POSE:
        pb = arm.pose.bones[bone]
        for axis, deg in swings:
            bpy.context.view_layer.update()
            h = pb.head.copy()                              # armature space = world (rig at the origin)
            pb.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-h) @ pb.matrix
    bpy.context.view_layer.update()
    hip = arm.matrix_world @ arm.pose.bones["Hip"].head
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in body:                                          # bake the pose into the mesh, drop the rig
        bpy.context.view_layer.objects.active = o
        for m in list(o.modifiers):
            if m.type == "ARMATURE":
                bpy.ops.object.modifier_apply(modifier=m.name)
        o.parent = None
        o.vertex_groups.clear()
        o.data.transform(Matrix.Translation(-hip))
    for o in [o for o in bpy.data.objects if o not in body]:
        bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(out), use_selection=True, export_format="GLB", export_skins=False,
                              export_animations=False, export_image_format="AUTO")
    pts = [o.matrix_world @ v.co for o in body for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    print("RIDER", out, "box", tuple(round(v, 2) for v in lo), tuple(round(v, 2) for v in hi))
    if preview:      # side + front check render
        sc = bpy.context.scene
        sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.color_type = "TEXTURE"
        sc.render.resolution_x, sc.render.resolution_y = 500, 500
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
        cam.data.type, cam.data.ortho_scale = "ORTHO", (hi - lo).length * 1.05
        c = (lo + hi) / 2
        for tag, d in (("side", Vector((-1, 0, 0.1))), ("front", Vector((0.25, -1, 0.15)))):
            cam.location = c + d.normalized() * 30
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = os.path.abspath(preview[:-4] + f"_{tag}.png")
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main(*sys.argv[sys.argv.index("--") + 1:])
