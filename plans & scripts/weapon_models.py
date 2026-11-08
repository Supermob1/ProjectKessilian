"""Battlefront II infantry rifles (F:/BF2_ModTools, msh_to_glb.py -> WIP/3d/_glb/weapons) -> HOI4 hand-held weapon meshes.

  blender(4.2.3) -b --factory-startup --python "plans & scripts/weapon_models.py" -- build     meshes + texture PNGs
  python -B "plans & scripts/weapon_models.py" textures                                       PNGs -> DDS, mesh material paths

Every gun is laid into the frame of our DC15.mesh (the DC-15S the trooper rigs were set up with): muzzle to -Y, Z up, the
grip where the DC15's grip is (the hand node holds it there), the barrel at the DC15's barrel height, length = DC15
length x ratio; a "muzzle2" locator at the barrel tip for the shot particles. Output: gfx/models/weapons/<name>.mesh.
"""
import json, os, sys

WIP = "../ProjectKessilianWIPGFX/ProjectKessilianWIP"
GLB = WIP + "/3d/_glb/weapons"
OUT = "gfx/models/weapons"
SIDE = GLB + "/weapons.json"
REF = OUT + "/DC15.mesh"
GUNS = {   # name: (source glb, length vs our DC-15S)
    "DC15A": ("rep_weap_inf_rifle", 1.3),        # republic_equipment_1 / REP infantry_equipment_0
    "DC15X": ("rep_weap_inf_sniperrifle", 1.35),  # stand-in for the DC-17 (marksman upper): BF2 has no DC-17m
    "E11": ("imp_weap_inf_rifle", 0.9),
}


def frame(pts):
    """grip y (mean y of the lowest 15 % of the gun), barrel z / x (median of the front 20 %), length, front y"""
    import statistics as st
    ys, zs = [p[1] for p in pts], [p[2] for p in pts]
    y0, y1, z0, z1 = min(ys), max(ys), min(zs), max(zs)
    low = [p for p in pts if p[2] < z0 + 0.15 * (z1 - z0)]
    front = [p for p in pts if p[1] < y0 + 0.2 * (y1 - y0)]
    tip = [p for p in pts if p[1] < y0 + 0.05 * (y1 - y0)]
    return dict(grip_y=st.mean(p[1] for p in low), grip_z=st.mean(p[2] for p in low), grip_x=st.mean(p[0] for p in low),
                tip_z=(min(p[2] for p in tip) + max(p[2] for p in tip)) / 2, tip_x=(min(p[0] for p in tip) + max(p[0] for p in tip)) / 2,
                length=y1 - y0, front=y0)


def build():
    import bpy  # type: ignore
    from mathutils import Matrix, Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie

    def clear():
        for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images):
            for x in list(coll):
                coll.remove(x)

    clear()
    bie.import_meshfile(os.path.abspath(REF), imp_mesh=True, imp_skel=False, imp_locs=False)
    ref = next(o for o in bpy.data.objects if o.type == "MESH")
    ref_f = frame([ref.matrix_world @ v.co for v in ref.data.vertices])
    side = {}
    for name, (src, ratio) in GUNS.items():
        clear()
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(f"{GLB}/{src}.glb"))
        objs = [o for o in bpy.data.objects if o.type == "MESH"]
        for o in objs:
            o.data.transform(o.matrix_world)
            o.parent = None
            o.matrix_world = Matrix()
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        gun = bpy.context.view_layer.objects.active
        for o in [o for o in bpy.data.objects if o is not gun]:
            bpy.data.objects.remove(o)
        me = gun.data
        pts = [v.co.copy() for v in me.vertices]
        if max(p.x for p in pts) - min(p.x for p in pts) > max(p.y for p in pts) - min(p.y for p in pts):
            me.transform(Matrix.Rotation(-1.5708, 4, "Z"))           # long axis onto Y
            pts = [v.co.copy() for v in me.vertices]
        ys = [p.y for p in pts]
        y0, y1 = min(ys), max(ys)
        tall = lambda a, b: (lambda s: max(s) - min(s) if s else 0)([p.z for p in pts if a <= p.y <= b])
        # BF2 guns come muzzle -Y already; the thin-end test misreads the E-11 (flash hider vs thin folded stock)
        if name != "E11" and tall(y0, y0 + 0.08 * (y1 - y0)) > tall(y1 - 0.08 * (y1 - y0), y1):   # thin barrel end must be -Y
            me.transform(Matrix.Rotation(3.14159, 4, "Z"))
        f = frame([v.co for v in me.vertices])
        k = ref_f["length"] * ratio / f["length"]
        me.transform(Matrix.Scale(k, 4))
        f = frame([v.co for v in me.vertices])
        t = Vector((ref_f["grip_x"] - f["grip_x"], ref_f["grip_y"] - f["grip_y"], ref_f["grip_z"] - f["grip_z"]))
        if name == "E11":       # its lowest part is the folded stock: put its BF2 hand point (origin) where the DC-15A's went
            t = side["_hand"]
        elif name == "DC15A":
            side["_hand"] = t.copy()
        me.transform(Matrix.Translation(t))     # the hand holds the grip
        f = frame([v.co for v in me.vertices])
        loc = bpy.data.objects.new("muzzle2", None)
        bpy.context.scene.collection.objects.link(loc)
        loc.location = (f["tip_x"], f["front"], f["tip_z"])
        loc.rotation_euler = (0, 0, -1.5708)     # local X down the barrel (-Y): blaster bolt particles fly along X
        side[name] = []
        for i, slot in enumerate(gun.material_slots):
            stem = f"{name}_{i}" if len(gun.material_slots) > 1 else name
            img = next((n.image for n in slot.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None) \
                if slot.material and slot.material.use_nodes else None
            png = None
            if img:
                png = os.path.abspath(f"{GLB}/{stem}.png")
                img.filepath_raw, img.file_format = png, "PNG"
                img.save()
            side[name].append(dict(stem=stem, base=png))
            pm = bie.create_shader(type("M", (), {"shader": ["PdxMeshAdvanced"], "diff": [f"{stem}_diffuse.dds"],
                                                  "n": [f"{stem}_normal.dds"], "spec": [f"{stem}_spec.dds"]})(),
                                   stem, os.path.abspath(OUT))
            pm[PDX_SHADER] = "PdxMeshAdvanced"
            slot.material = pm
        gun.name = me.name = name
        bpy.ops.object.select_all(action="SELECT")
        bie.export_meshfile(os.path.abspath(f"{OUT}/{name}.mesh"), exp_mesh=True, exp_skel=False, exp_locs=True)
        print("GUN", name, src, "scale %.3f" % k, len(me.polygons), "faces", len(side[name]), "materials")
    side.pop("_hand", None)
    json.dump(side, open(SIDE, "w"), indent=1)


def textures():
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    sys.path.insert(0, os.path.join(os.environ["LOCALAPPDATA"], "universal-modder/tools/blender-4.2.3-windows-x64/4.2/scripts/addons"))
    from io_pdx_mesh.pdx_data import read_meshfile, write_meshfile
    full = lambda v, n: np.full((n, n), v, np.float32)
    for name, mats in json.load(open(SIDE)).items():
        for m in mats:
            base = np.asarray(Image.open(m["base"]).convert("RGB").resize((256, 256), Image.LANCZOS)).astype(np.float32) \
                if m["base"] else np.dstack([full(120, 256)] * 3)
            base = np.maximum(base, 0) * max(1.0, 110 / max(base.mean(), 1))     # < ~100 RGB renders black in game
            save_dxt5_mips(np.dstack([np.clip(base, 0, 255), full(255, 256)]), f"{OUT}/{m['stem']}_diffuse.dds")
            save_dxt5_mips(np.dstack([full(132, 64), full(130, 64), full(0, 64), full(128, 64)]), f"{OUT}/{m['stem']}_normal.dds")
            save_dxt5_mips(np.dstack([full(0, 64), full(60, 64), full(40, 64), full(150, 64)]), f"{OUT}/{m['stem']}_spec.dds")
        root = read_meshfile(f"{OUT}/{name}.mesh")
        for mat, m in zip(root.iter("material"), mats):
            mat.set("diff", [f"{m['stem']}_diffuse.dds"])
            mat.set("n", [f"{m['stem']}_normal.dds"])
            mat.set("spec", [f"{m['stem']}_spec.dds"])
        write_meshfile(f"{OUT}/{name}.mesh", root)
        print("textures", name, len(mats))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"build": build, "textures": textures}[args[0]]()
