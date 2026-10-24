"""Felucian warrior ("Felucian warrior" by abdyla, SketchUp 3D Warehouse; Collada flattened by dae_flatten.py) ->
HOI4 infantry model for the Felucian tribes (FLT), on the vanilla infantry rig, with a spear instead of a rifle.

    python "WIPGFX/plans & scripts/dae_flatten.py" "WIPGFX/3d/Felucian warrior by abdyla/model.dae" "WIPGFX/3d/Felucian warrior by abdyla/felucian_warrior.obj"
    blender -b --factory-startup --python "WIPGFX/plans & scripts/felucian_warrior.py" -- convert
    python "WIPGFX/plans & scripts/felucian_warrior.py" textures
    python "WIPGFX/plans & scripts/felucian_warrior.py" wire       gfx/entities/units_infantry_felucian.{gfx,asset}

Run from the mod root. Same method as old_republic_trooper.py: the static model (an A-pose, like the clone trooper)
is turned to face the clone's way, scaled onto the clone trooper (gfx/models/units/clonetrooper/REP_infantry.mesh)
and takes its skin weights, so every vanilla infantry animation plays on it. Two materials (body, head); their UVs
tile, so no atlas. The spear is built here and hangs on the same hand nodes as the clone's DC-15.
"""
import math, os, sys

SRC = "WIPGFX/3d/Felucian warrior by abdyla"
OBJ = f"{SRC}/felucian_warrior.obj"
CLONE = "gfx/models/units/clonetrooper/REP_infantry.mesh"
DC15 = "gfx/models/weapons/DC15.mesh"
OUT = "gfx/models/units/felucian"
NAME, SPEAR = "FLT_warrior", "FLT_spear"
TEX = {"body": f"{SRC}/model/_01_-_Default1.PNG", "head": f"{SRC}/model/_02_-_Default1.PNG"}
MAT_OF = {"ID177": "body", "ID1408": "body", "ID26": "body", "ID8": "head"}      # .dae material -> texture


def convert():
    import bpy  # type: ignore
    import bmesh  # type: ignore
    from mathutils import Matrix, Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie

    def select(objs, active=None):
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for o in bpy.context.scene.objects:
            o.select_set(o in objs)
        bpy.context.view_layer.objects.active = active or objs[0]

    def box(objs):
        pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
        return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])

    class Mat:
        def __init__(self, stem):
            self.shader = ["PdxMeshAdvanced"]
            self.diff, self.n, self.spec = [f"{stem}_diffuse.dds"], [f"{stem}_normal.dds"], [f"{stem}_spec.dds"]

    os.makedirs(OUT, exist_ok=True)
    # ── the warrior on the clone's rig ──
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bie.import_meshfile(os.path.abspath(CLONE), join_materials=False)
    rig = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"][0]
    clone = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    cb = lambda n: rig.matrix_world @ rig.data.bones[n].head_local
    bpy.ops.wm.obj_import(filepath=os.path.abspath(OBJ), up_axis="Z", forward_axis="Y")
    war = [o for o in bpy.context.scene.objects if o.type == "MESH" and o not in clone][0]
    # face the clone's way: the warrior faces -Y (checked on renders: its crest of quills sweeps back, so a "face juts
    # forward" guess fails); the clone's toes point forward, snapped to its nearest axis
    w_fwd = Vector((0, -1, 0))
    c_fwd = cb("LeftToeBase") - cb("LeftFoot")
    c_fwd.z = 0
    i = max(range(2), key=lambda i: abs(c_fwd[i]))
    c_fwd = Vector([math.copysign(1, c_fwd[i]) if j == i else 0 for j in range(3)])
    print("clone forward", tuple(c_fwd))
    yaw = w_fwd.to_track_quat("Y", "Z").rotation_difference(c_fwd.to_track_quat("Y", "Z"))
    war.matrix_world = yaw.to_matrix().to_4x4() @ war.matrix_world
    select([war])
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    clo, chi = box(clone)
    tlo, thi = box([war])
    k = (chi.z - clo.z) / (thi.z - tlo.z)
    war.data.transform(Matrix.Translation(Vector(((clo.x + chi.x) / 2, (clo.y + chi.y) / 2, clo.z)))
                       @ Matrix.Scale(k, 4) @ Matrix.Translation(-Vector(((tlo.x + thi.x) / 2, (tlo.y + thi.y) / 2, tlo.z))))
    war.data.update()
    # weights from the clone (nearest surface)
    select(clone, clone[0])
    if len(clone) > 1:
        bpy.ops.object.join()
    src = bpy.context.view_layer.objects.active
    for g in src.vertex_groups:
        war.vertex_groups.new(name=g.name)
    dt = war.modifiers.new("weights", "DATA_TRANSFER")
    dt.object = src
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    select([war])
    bpy.ops.object.modifier_apply(modifier="weights")
    bpy.ops.object.vertex_group_limit_total(limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    bpy.data.objects.remove(src, do_unlink=True)
    # two PDX materials; the untextured bits (ID26) take a pale spot of the body texture
    me = war.data
    slots = [MAT_OF.get(m.name.split(".")[0], "body") for m in me.materials]
    uv = me.uv_layers[0].data
    for p in me.polygons:
        if me.materials[p.material_index].name.split(".")[0] == "ID26":
            for li in p.loop_indices:
                uv[li].uv = (0.43, 0.38)
    mats = {}
    for kind in ("body", "head"):
        pm = bie.create_shader(Mat(f"{NAME}_{kind}"), f"{NAME}_{kind}", os.path.abspath(OUT))
        pm[PDX_SHADER] = "PdxMeshAdvanced"
        mats[kind] = pm
    idx = [slots[p.material_index] for p in me.polygons]
    me.materials.clear()
    me.materials.append(mats["body"])
    me.materials.append(mats["head"])
    for p, kind in zip(me.polygons, idx):
        p.material_index = 0 if kind == "body" else 1
    war.name = me.name = NAME
    war.parent = rig
    war.modifiers.new("rig", "ARMATURE").object = rig
    bpy.context.scene.frame_set(0)
    bie.export_meshfile(os.path.abspath(f"{OUT}/{NAME}.mesh"), exp_mesh=True, exp_skel=True, exp_locs=True)
    lo, hi = box([war])
    print(f"{NAME}: {len(me.polygons)} faces, {len(war.vertex_groups)} groups, size {hi.x-lo.x:.2f} x {hi.y-lo.y:.2f} x {hi.z-lo.z:.2f}")

    # ── the spear: laid along the DC-15's long axis, grip at the same place ──
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bie.import_meshfile(os.path.abspath(DC15), join_materials=False)
    gun = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    lo, hi = box(gun)
    span = hi - lo
    ax = max(range(3), key=lambda i: span[i])
    fwd = 1 if abs(hi[ax]) > abs(lo[ax]) else -1            # the barrel runs the long way from the grip
    for o in list(bpy.context.scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    length = span[ax] * 1.5
    def axis_vec(t, r, a):
        v = [0.0, 0.0, 0.0]
        v[ax] = fwd * t
        o1, o2 = [i for i in range(3) if i != ax]
        v[o1], v[o2] = r * math.cos(a), r * math.sin(a)
        return Vector(v)
    sides = 6
    # (position along the spear, radius, texture v): shaft, binding, leaf blade
    prof = [(-0.35 * length, 0.05, 0.0), (0.55 * length, 0.05, 0.6), (0.58 * length, 0.08, 0.65),
            (0.62 * length, 0.07, 0.7), (0.66 * length, 0.13, 0.8), (0.8 * length, 0.09, 0.9), (0.92 * length, 0.0, 1.0)]
    rings = [[bm.verts.new(axis_vec(t, r, 2 * math.pi * i / sides)) for i in range(sides)] for t, r, _v in prof]
    for k in range(len(rings) - 1):
        for i in range(sides):
            j = (i + 1) % sides
            f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
            for loop, (u, v) in zip(f.loops, ((i / sides, prof[k][2]), (j / sides, prof[k][2]), (j / sides, prof[k + 1][2]), (i / sides, prof[k + 1][2]))):
                loop[uvl].uv = (u, v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    sm = bpy.data.meshes.new(SPEAR)
    bm.to_mesh(sm)
    bm.free()
    so = bpy.data.objects.new(SPEAR, sm)
    bpy.context.scene.collection.objects.link(so)
    pm = bie.create_shader(Mat(SPEAR), SPEAR, os.path.abspath(OUT))
    pm[PDX_SHADER] = "PdxMeshAdvanced"
    sm.materials.append(pm)
    select([so])
    m = so.modifiers.new("t", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=m.name)
    bie.export_meshfile(os.path.abspath(f"{OUT}/{SPEAR}.mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
    print(f"{SPEAR}: {len(sm.polygons)} faces, {length:.2f} long on axis {'xyz'[ax]}")


def textures():
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    os.makedirs(OUT, exist_ok=True)
    flat = lambda n: np.dstack([np.full((n, n), v, np.float32) for v in (132, 130, 0, 128)])
    spec = lambda n: np.dstack([np.full((n, n), v, np.float32) for v in (0, 40, 0, 70)])
    for kind, path in TEX.items():
        im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
        stem = f"{OUT}/{NAME}_{kind}"
        save_dxt5_mips(np.dstack([im, np.full(im.shape[:2], 255, np.float32)]), f"{stem}_diffuse.dds")
        save_dxt5_mips(flat(im.shape[0]), f"{stem}_normal.dds")
        save_dxt5_mips(spec(im.shape[0]), f"{stem}_spec.dds")
    # spear: dark wood shaft, a bound grip, a pale bone-like leaf blade (texture v runs grip -> tip)
    n = 128
    v = np.linspace(1, 0, n)[:, None] * np.ones((1, n))
    col = np.where(v[..., None] < 0.6, [92, 64, 40], np.where(v[..., None] < 0.72, [150, 60, 120], [220, 210, 180]))
    col = col * (0.85 + 0.15 * np.random.default_rng(3).random((n, n, 1)))
    save_dxt5_mips(np.dstack([col.astype(np.float32), np.full((n, n), 255, np.float32)]), f"{OUT}/{SPEAR}_diffuse.dds")
    save_dxt5_mips(flat(n), f"{OUT}/{SPEAR}_normal.dds")
    save_dxt5_mips(spec(n), f"{OUT}/{SPEAR}_spec.dds")
    print("textures", NAME, SPEAR)


def wire():
    """FLT_infantry_entity: the game picks <TAG>_infantry_entity for the tribes' infantry by itself"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from old_republic_trooper import ANIMS
    anims = "".join(f'\t\tanimation = {{ id = "{a.split(":")[0]}" type = "{a.split(":")[1]}_animation" }}\n' for a in ANIMS)
    # units_ prefix: assets load alphabetically, and the parent (vanilla units_infantry.asset) must come first
    open("gfx/entities/units_infantry_felucian.gfx", "w", encoding="utf-8", newline="\n").write(
        "objectTypes = {\n\t# HOD: Felucian warrior and spear (felucian_warrior.py)\n"
        f'\tpdxmesh = {{\n\t\tname = "{NAME}_mesh"\n\t\tfile = "{OUT}/{NAME}.mesh"\n{anims}\t}}\n'
        f'\tpdxmesh = {{\n\t\tname = "{SPEAR}_mesh"\n\t\tfile = "{OUT}/{SPEAR}.mesh"\n\t}}\n}}\n')
    open("gfx/entities/units_infantry_felucian.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: Felucian tribes' infantry (felucian_warrior.py): the warrior on the infantry rig, spears for rifles\n"
        f'entity = {{\n\tname = "{SPEAR}_entity"\n\tpdxmesh = "{SPEAR}_mesh"\n\tget_state_from_parent = yes\n'
        '\tdefault_state = "idle"\n\tstate = { name = "idle" }\n\tstate = { name = "move" }\n\tstate = { name = "attack" }\n'
        '\tstate = { name = "defend" }\n}\n'
        f'entity = {{\n\tclone = "infantry_rifle_entity"\n\tname = "FLT_infantry_entity"\n\tpdxmesh = "{NAME}_mesh"\n\n'
        + "".join(f'\tattach = {{ name = "{a}" {n} = "{SPEAR}_entity" }}\n'
                  for a, n in (("rifle1", "Right_Hand_node"), ("rifle2", "Left_Hand_node"), ("rifle4", "Root_node_2"),
                               ("rifle3", "mid_back_node")))
        + '\n\tstate = {\n\t\tname = "death" animation = "death"\n'
        '\t\tevent = { time = 0 node = "head" particle = "blood_particle" keep_particle = yes }\n\t}\n}\n')
    print("wired FLT_infantry_entity")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"convert": convert, "textures": textures, "wire": wire}[args[0]]()
