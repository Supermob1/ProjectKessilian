"""Headless Blender: print objects, sizes and materials of an FBX, and the bounds of a vanilla HOI4 mesh.
blender -b --factory-startup --python blender_inspect.py -- <file.fbx> [vanilla.mesh]"""
import os
import sys
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
# io_pdx_mesh lives in the portable Blender's scripts/addons; make it importable as a package
sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
import io_pdx_mesh  # noqa: E402,F401


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=args[0])
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
print(f"FBX {args[0]}: {len(meshes)} mesh objects, {len(bpy.data.materials)} materials, "
      f"{len(bpy.data.images)} images")
tot = 0
for o in sorted(meshes, key=lambda o: -len(o.data.polygons))[:40]:
    lo, hi = bounds([o])
    d = hi - lo
    tot += len(o.data.polygons)
    print(f"  {o.name:40s} polys {len(o.data.polygons):7d}  size {d.x:8.2f} {d.y:8.2f} {d.z:8.2f}  "
          f"loc {o.location.x:8.2f} {o.location.y:8.2f}  mats {[s.material.name if s.material else None for s in o.material_slots]}"
          f"  uv {len(o.data.uv_layers)}")
print("total polys (top 40):", tot, " all:", sum(len(o.data.polygons) for o in meshes))
lo, hi = bounds(meshes)
print("scene bounds", tuple(round(v, 2) for v in lo), tuple(round(v, 2) for v in hi))
for img in bpy.data.images:
    print("  image", img.name, img.filepath, tuple(img.size))

if len(args) > 1:
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bie.import_meshfile(args[1], imp_mesh=True, imp_skel=False, imp_locs=True)
    vm = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    lo, hi = bounds(vm)
    print(f"VANILLA {args[1]}: {len(vm)} meshes, polys {sum(len(o.data.polygons) for o in vm)}, "
          f"bounds {tuple(round(v, 3) for v in lo)} {tuple(round(v, 3) for v in hi)}")
    for o in vm:
        for s in o.material_slots:
            if s.material:
                print("   material", s.material.name, dict((k, str(v)) for k, v in s.material.items()))
