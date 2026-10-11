"""Old Republic trooper (SWTOR-era armour, Battlefront II mod .msh) -> HOI4 infantry model on the vanilla infantry rig.

  blender -b --factory-startup --python "WIPGFX/plans & scripts/old_republic_trooper.py" -- convert
  python "WIPGFX/plans & scripts/old_republic_trooper.py" textures     texture atlas -> diffuse / normal / spec DDS
  python "WIPGFX/plans & scripts/old_republic_trooper.py" wire         gfx/entities/units_infantry_old_republic.{gfx,asset}

Run from the mod root. The trooper is posed like the clone trooper model (gfx/models/units/clonetrooper/REP_infantry.mesh,
which sits on the vanilla infantry skeleton), scaled onto it, and takes its skin weights, so every vanilla infantry
animation plays on it. Its eight textures are packed into one atlas (one material, one draw call per soldier).
"""
import json, os, sys

SRC = "WIPGFX/3d/SWTOR_era_Republic_Trooper"
MSH = f"{SRC}/rep_inf_tor_trooper.msh"
CLONE = "gfx/models/units/clonetrooper/REP_infantry.mesh"
OUT = "gfx/models/units/old_republic"
NAME = "REP_old_trooper"
ATLAS = f"{SRC}/_atlas.png"
ATLAS_PX = 2048
# texture -> atlas cell (x, y, w, h) in pixels; the chest and torso sheets keep full size, the small ones share a row
CELLS = {"swtortrooperchest.tga": (0, 0, 1024, 1024),
         "swtortroopertorso_DF2.tga": (1024, 0, 1024, 512), "swtortrooperface.tga": (1024, 512, 512, 512),
         "swtortrooperlegs.tga": (1536, 512, 512, 512), "swtortrooperhands.tga": (0, 1024, 256, 256),
         "swtortrooperhand_glove.tga": (256, 1024, 256, 256), "swtortrooperwaist.tga": (512, 1024, 256, 256)}
# trooper limb (bone, child) -> clone limb (bone, child): the trooper is re-posed so these point the same way
LIMBS = [(("bone_{s}_upperarm", "bone_{s}_forearm"), ("{S}Arm", "{S}ForeArm")),
         (("bone_{s}_forearm", "bone_{s}_hand"), ("{S}ForeArm", "{S}Hand")),
         (("bone_{s}_thigh", "bone_{s}_calf"), ("{S}UpLeg", "{S}Leg")),
         (("bone_{s}_calf", "bone_{s}_foot"), ("{S}Leg", "{S}Foot"))]


def convert(*opts):
    import bpy  # type: ignore
    from mathutils import Matrix, Quaternion, Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    import swbf_msh

    def select(objs, active=None):
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for o in bpy.context.scene.objects:
            o.select_set(o in objs)
        bpy.context.view_layer.objects.active = active or objs[0]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bie.import_meshfile(os.path.abspath(CLONE), join_materials=False)   # its join uses a context override 4.2 rejects
    clone_rig = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"][0]
    clone_meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    cb = lambda n: clone_rig.matrix_world @ clone_rig.data.bones[n].head_local

    # ── the trooper, in its own bind pose, on its own skeleton ──
    d = swbf_msh.read(MSH)
    by = {m["name"]: m for m in d["models"]}
    by_index = {m["index"]: m["name"] for m in d["models"]}
    C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))    # XSI export: right-handed Y-up +Z-ahead -> Z-up -Y-ahead
    W = {}
    def world(n):
        if n not in W:
            t = by[n]["tran"]
            x, y, z, w = t["rot"]
            loc = Matrix.Translation(t["pos"]) @ Quaternion((w, x, y, z)).to_matrix().to_4x4()
            W[n] = (world(by[n]["parent"]) if by[n]["parent"] in by else Matrix()) @ loc
        return W[n]
    poly = [m for m in d["models"] if m["segments"]][0]
    env = [by_index[i] for i in poly["envelope"]]
    pw = C @ world(poly["name"])
    verts, faces, uvs, mats, weights = [], [], [], [], []
    for g in poly["segments"]:
        base = len(verts)
        pts = [pw @ Vector(p) for p in g["pos"]]
        nrm = [(C.to_3x3() @ Vector(n)) for n in g["nrm"]]
        verts += pts
        tex = d["materials"][g["mat"]][1][0]
        for u, v in g["uv"]:
            v = v % 1.0     # the .msh V is bottom-up, stored as -1..0: wrap into the tile
            x, y, w, h = CELLS[tex]
            uvs.append(((x + u * w) / ATLAS_PX, 1 - (y + (1 - v) * h) / ATLAS_PX))
        weights += [[(env[i], wt) for i, wt in vw if wt > 0] for vw in g["weights"]]
        for a, b, c in g["tris"]:
            f = (base + a, base + b, base + c)
            if (pts[b] - pts[a]).cross(pts[c] - pts[a]).dot(nrm[a] + nrm[b] + nrm[c]) < 0:
                f = (f[0], f[2], f[1])
            faces.append(f)
    mesh = bpy.data.meshes.new(NAME)
    mesh.from_pydata(verts, [], faces)
    uvl = mesh.uv_layers.new(name="uv0")
    uvl.data.foreach_set("uv", [c for p in mesh.polygons for li in p.loop_indices for c in uvs[mesh.loops[li].vertex_index]])
    tro = bpy.data.objects.new(NAME, mesh)
    bpy.context.scene.collection.objects.link(tro)
    for vi, vw in enumerate(weights):
        for bone, wt in vw:
            (tro.vertex_groups.get(bone) or tro.vertex_groups.new(name=bone)).add([vi], wt, "ADD")
    # trooper skeleton: every model on the way from a skinning bone to the root
    need = set()
    for b in env:
        while b in by:
            need.add(b)
            b = by[b]["parent"]
    need.update(n for s in "lr" for n in (f"bone_{s}_hand", f"bone_{s}_foot", f"bone_{s}_calf", f"bone_{s}_forearm"))
    t_data = bpy.data.armatures.new("trooper_rig")
    t_rig = bpy.data.objects.new("trooper_rig", t_data)
    bpy.context.scene.collection.objects.link(t_rig)
    select([t_rig])
    bpy.ops.object.mode_set(mode="EDIT")
    for n in need:
        eb = t_data.edit_bones.new(n)
        eb.head = (C @ world(n)).translation
        eb.tail = eb.head + Vector((0, 0, 0.05))
    for n in need:
        if by[n]["parent"] in need:
            t_data.edit_bones[n].parent = t_data.edit_bones[by[n]["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    tro.modifiers.new("trooper_rig", "ARMATURE").object = t_rig

    # ── face the clone's way, then re-pose the limbs like the clone's (shoulders / hips stay) ──
    tb = lambda n: t_rig.matrix_world @ t_rig.data.bones[n].head_local
    c_fwd = (cb("LeftToeBase") - cb("LeftFoot")); c_fwd.z = 0
    t_fwd = (tb("bone_l_toe") - tb("bone_l_foot")) if "bone_l_toe" in t_rig.data.bones else Vector((0, -1, 0)); t_fwd.z = 0
    yaw = t_fwd.to_track_quat("Y", "Z").rotation_difference(c_fwd.to_track_quat("Y", "Z"))
    t_rig.matrix_world = yaw.to_matrix().to_4x4() @ t_rig.matrix_world
    tro.matrix_world = yaw.to_matrix().to_4x4() @ tro.matrix_world
    bpy.context.view_layer.update()
    # same side? the clone's left arm and the trooper's left arm on the same side of the body
    assert (cb("LeftArm").x > cb("RightArm").x) == (tb("bone_l_upperarm").x > tb("bone_r_upperarm").x), "trooper is mirrored"
    select([t_rig])
    bpy.ops.object.mode_set(mode="POSE")
    for side, S in (("l", "Left"), ("r", "Right")):
        for (ta, tc), (ca, cc) in LIMBS:
            ta, tc, ca, cc = ta.format(s=side), tc.format(s=side), ca.format(S=S), cc.format(S=S)
            bpy.context.view_layer.update()
            pb = t_rig.pose.bones[ta]
            h = t_rig.matrix_world @ pb.head
            cur = (t_rig.matrix_world @ t_rig.pose.bones[tc].head) - h
            want = cb(cc) - cb(ca)
            R = cur.rotation_difference(want).to_matrix().to_4x4()
            M = t_rig.matrix_world.inverted() @ Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ t_rig.matrix_world
            pb.matrix = M @ pb.matrix
    bpy.ops.object.mode_set(mode="OBJECT")
    select([tro])
    bpy.ops.object.modifier_apply(modifier="trooper_rig")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.data.objects.remove(t_rig, do_unlink=True)
    tro.vertex_groups.clear()

    # ── onto the clone: same height, feet on the same ground, centred ──
    def box(objs):
        pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
        return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])
    clo, chi = box(clone_meshes)
    tlo, thi = box([tro])
    k = (chi.z - clo.z) / (thi.z - tlo.z)
    mesh.transform(Matrix.Translation(Vector(((clo.x + chi.x) / 2, (clo.y + chi.y) / 2, clo.z)))
                   @ Matrix.Scale(k, 4) @ Matrix.Translation(-Vector(((tlo.x + thi.x) / 2, (tlo.y + thi.y) / 2, tlo.z))))
    mesh.update()

    # ── skin weights from the clone (nearest surface), bound to the clone's skeleton ──
    select(clone_meshes, clone_meshes[0])
    if len(clone_meshes) > 1:
        bpy.ops.object.join()
    src = bpy.context.view_layer.objects.active
    for g in src.vertex_groups:
        tro.vertex_groups.new(name=g.name)
    dt = tro.modifiers.new("weights", "DATA_TRANSFER")
    dt.object = src
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    select([tro])
    bpy.ops.object.modifier_apply(modifier="weights")
    bpy.ops.object.vertex_group_limit_total(limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    bpy.data.objects.remove(src, do_unlink=True)
    tro.parent = clone_rig
    tro.modifiers.new("rig", "ARMATURE").object = clone_rig

    # ── material and export ──
    class Mat:
        shader = ["PdxMeshAdvanced"]
        diff, n, spec = [f"{NAME}_diffuse.dds"], [f"{NAME}_normal.dds"], [f"{NAME}_spec.dds"]
    os.makedirs(OUT, exist_ok=True)
    pm = bie.create_shader(Mat(), NAME, os.path.abspath(OUT))
    pm[PDX_SHADER] = "PdxMeshAdvanced"
    mesh.materials.clear()
    mesh.materials.append(pm)
    tro.name = mesh.name = NAME
    bpy.context.scene.frame_set(0)
    bie.export_meshfile(os.path.abspath(f"{OUT}/{NAME}.mesh"), exp_mesh=True, exp_skel=True, exp_locs=True)
    lo, hi = box([tro])
    print(f"{NAME}: {len(mesh.polygons)} faces, {len(tro.vertex_groups)} groups, size {hi.x-lo.x:.2f} x {hi.y-lo.y:.2f} x {hi.z-lo.z:.2f}")


def textures():
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    atlas = Image.new("RGB", (ATLAS_PX, ATLAS_PX), (90, 90, 90))
    for tex, (x, y, w, h) in CELLS.items():
        atlas.paste(Image.open(f"{SRC}/{tex}").convert("RGB").resize((w, h), Image.LANCZOS), (x, y))
    atlas.save(ATLAS)
    os.makedirs(OUT, exist_ok=True)
    full = lambda v: np.full((ATLAS_PX, ATLAS_PX), v, np.float32)
    save_dxt5_mips(np.dstack([np.asarray(atlas).astype(np.float32), full(255)]), f"{OUT}/{NAME}_diffuse.dds")
    save_dxt5_mips(np.dstack([full(132), full(130), full(0), full(128)]), f"{OUT}/{NAME}_normal.dds")
    save_dxt5_mips(np.dstack([full(0), full(40), full(10), full(90)]), f"{OUT}/{NAME}_spec.dds")
    print("textures", NAME)


ANIMS = ["idle:GER_infantry_mg_idle", "attack:GER_infantry_mg_attack", "support_attack:GER_infantry_mg_support_attack",
         "charge_rifle:GER_infantry_rifle_charge", "charge_rifle_shoot:GER_infantry_rifle_charge_shoot", "move:GER_infantry_mg_moving",
         "march_move:GER_infantry_mg_march", "retreat:GER_infantry_mg_retreat", "death:GER_infantry_mg_death",
         "long_idle01:GER_infantry_mg_long_idle_01", "long_idle02:GER_infantry_mg_long_idle_02", "long_idle03:GER_infantry_mg_long_idle_03",
         "long_idle04:GER_infantry_mg_long_idle_04", "long_idle05:GER_infantry_mg_long_idle_05",
         "cavalry_idle:GER_infantry_cavalry_rider_mg_idle", "cavalry_move:GER_infantry_cavalry_rider_mg_moving",
         "training:GER_infantry_idle_training", "jumping_jacks:GER_infantry_jumping_jacks", "pushup:GER_infantry_pushup",
         "guard_rifle:GER_infantry_guard_rifle", "aim_exercise:GER_infantry_aim_exercise_mg"]


def wire():
    """same animations and attachments as the clone trooper (gfx/entities/infantry_REP.gfx, units_infantry_REP.asset)"""
    anims = "".join(f'\t\tanimation = {{ id = "{a.split(":")[0]}" type = "{a.split(":")[1]}_animation" }}\n' for a in ANIMS)
    open("gfx/entities/units_infantry_old_republic.gfx", "w", encoding="utf-8", newline="\n").write(
        "objectTypes = {\n\t# HOD: Old Republic trooper (old_republic_trooper.py)\n"
        f'\tpdxmesh = {{\n\t\tname = "{NAME}_mesh"\n\t\tfile = "{OUT}/{NAME}.mesh"\n{anims}\t}}\n}}\n')
    # units_ prefix: assets load alphabetically, and the parent (vanilla units_infantry.asset) must come first
    open("gfx/entities/units_infantry_old_republic.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: Old Republic trooper (old_republic_trooper.py): the clone trooper's entity with the old armour\n"
        f'entity = {{\n\tclone = "infantry_rifle_entity"\n\tname = "{NAME}_entity"\n\tpdxmesh = "{NAME}_mesh"\n\n'
        '\tattach = { name = "rifle1" Right_Hand_node = "REP_infantry_weapon_DC15_entity" }\n'
        '\tattach = { name = "rifle2" Left_Hand_node = "REP_infantry_weapon_DC15_entity" }\n'
        '\tattach = { name = "rifle4" Root_node_2 = "REP_infantry_weapon_DC15_entity" }\n'
        '\tattach = { name = "rifle3" mid_back_node = "REP_infantry_weapon_DC15_entity" }\n\n'
        '\tstate = {\n\t\tname = "death" animation = "death"\n'
        '\t\tevent = { time = 0 node = "head" particle = "blood_particle" keep_particle = yes }\n\t}\n}\n')
    print("wired", NAME)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"convert": convert, "textures": textures, "wire": wire}[args[0]](*args[1:])
