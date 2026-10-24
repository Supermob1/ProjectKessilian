"""Blender: cut the individual buildings out of the Christophsis Battleground level (Sketchfab, CC BY,
StrangeUsernames1) and save each as its own .glb for sketchfab_props.py to decimate/bake.

  blender -b --factory-startup --python "WIPGFX/plans & scripts/christophsis_extract.py" -- [render]

The level splits a building into several overlapping objects (facade, crystal, roof...) with nearly the same centre.
Sites = tall compact pieces (>= 30 high, <= 160 across) grouped by centre distance; each site then takes every
object standing inside its footprint. Sky, terrain shells, floors, walkways and props are left out.
Output: WIPGFX/3d/sketchfab/christophsis_buildings/site_NN.glb (+ contact.png with `render`).
"""
import math, os, sys
import bpy  # type: ignore
from mathutils import Vector  # type: ignore

SRC = "WIPGFX/3d/sketchfab/Nouveau dossier/christophosis_battleground/scene.gltf"
OUT = "WIPGFX/3d/sketchfab/christophsis_buildings"
SITE_R = 75.0


def bounds(o):
    p = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([min(q[i] for q in p) for i in range(3)]), Vector([max(q[i] for q in p) for i in range(3)])


def main(render=False):
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(SRC))
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and len(o.data.polygons)]
    info = {o: bounds(o) for o in objs}
    tall = [o for o in objs if (info[o][1] - info[o][0]).z >= 30 and
            max((info[o][1] - info[o][0]).x, (info[o][1] - info[o][0]).y) <= 160]
    sites = []                                       # [(centre xy, [objects])]
    for o in sorted(tall, key=lambda o: -(info[o][1] - info[o][0]).z):
        c = (info[o][0] + info[o][1]) / 2
        for s in sites:
            if math.hypot(s[0].x - c.x, s[0].y - c.y) < SITE_R:
                s[1].append(o)
                break
        else:
            sites.append((c, [o]))
    used = set()
    out = []
    for k, (c, members) in enumerate(sites):
        lo = Vector([min(info[o][0][i] for o in members) for i in range(3)])
        hi = Vector([max(info[o][1][i] for o in members) for i in range(3)])
        for o in objs:                               # pieces standing inside the footprint (roofs, details)
            olo, ohi = info[o]
            oc = (olo + ohi) / 2
            if o in members or o in used or max((ohi - olo).x, (ohi - olo).y) > 160:
                continue
            if lo.x - 5 <= oc.x <= hi.x + 5 and lo.y - 5 <= oc.y <= hi.y + 5 and olo.z >= lo.z - 5:
                members.append(o)
        used.update(members)
        for o in bpy.context.scene.objects:
            o.select_set(o in members)
        path = os.path.abspath(f"{OUT}/site_{k:02d}.glb")
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format="GLB")
        tris = sum(len(o.data.polygons) for o in members)
        out.append((k, members, lo, hi))
        print(f"SITE {k:02d}: {len(members)} objects, {tris} faces, {hi.x - lo.x:.0f} x {hi.y - lo.y:.0f} x {hi.z - lo.z:.0f}")
    if render:
        contact(out)


def contact(sites):
    """One small render per site in a grid, for picking."""
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = sc.render.resolution_y = 360
    sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.5, 0.55, 0.62)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3
    sun.rotation_euler = (math.radians(45), 0, math.radians(35))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_end = 1e5
    for k, members, lo, hi in sites:
        for o in bpy.context.scene.objects:
            if o.type == "MESH":
                o.hide_render = o not in members
        c = (lo + hi) / 2
        ext = max(hi - lo)
        cam.location = (c.x, c.y - ext * 1.6, c.z + ext * 0.9)
        cam.rotation_euler = (math.radians(62), 0, 0)
        sc.render.filepath = os.path.abspath(f"{OUT}/render_{k:02d}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(render="render" in args)
