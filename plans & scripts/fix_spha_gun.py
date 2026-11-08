"""SPHA (FotR Self_Propelled_Heavy_Artillery + SPHA-T.alo on Attach_00): the attached turbolaser comes in unrotated, lying
along +X inside the hull. Turn it to point forward (-Y, the front legs' side), seat its mount on the hull top over Attach_00.
  blender -b --factory-startup --python "plans & scripts/fix_spha_gun.py" -- IN.glb OUT.glb
Runs on the alo_to_glb.py --anim output (rest pose; the gun is rigid on Attach_00, which the clips don't move)."""
import bpy, sys, math
from mathutils import Matrix, Vector
src, dst = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
gun = [o for o in bpy.data.objects if o.type == "MESH" and "Attach_00" in o.name]          # Turbo_ + TurboBase_
body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name == "Walker")
base = next(o for o in gun if o.name.startswith("TurboBase"))
W = lambda o: [o.matrix_world @ v.co for v in o.data.vertices]
bp = W(base); c = sum(bp, Vector()) / len(bp); zlo = min(p.z for p in bp)
att = arm.matrix_world @ arm.pose.bones["Attach_00"].head
top = max(p.z for p in W(body) if abs(p.y - att.y) < 25 and abs(p.x - att.x) < 25)    # hull top over the hardpoint
M = Matrix.Translation(Vector((att.x, att.y, top - 6))) @ Matrix.Rotation(-math.pi / 2, 4, "Z") @ Matrix.Translation(-Vector((c.x, c.y, zlo)))
for o in gun:
    o.data.transform(o.matrix_world.inverted() @ M @ o.matrix_world)
g = [o.matrix_world @ v.co for o in gun for v in o.data.vertices]
print("SPHA gun y %.0f..%.0f z %.0f..%.0f (hull top %.0f at the hardpoint)" % (min(p.y for p in g), max(p.y for p in g), min(p.z for p in g), max(p.z for p in g), top))
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_animations=True, export_yup=True)
