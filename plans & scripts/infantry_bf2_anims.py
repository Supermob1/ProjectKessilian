"""Blender 4.2: Star Wars Battlefront II soldier animations (mod tools SoldierAnimationBank/human_0, LucasArts / Pandemic)
retargeted onto our clone trooper rig (the vanilla 33-joint infantry skeleton) -> HOI4 .anim files.

  blender -b --factory-startup --python "plans & scripts/infantry_bf2_anims.py" -- [mesh ...]

Source: WIP/3d/_glb/bf2_anim/human_rifle.glb (msh_anim_to_glb.py, one action per clip). Per frame, in hierarchy order:
  pelvis / spine / head / hands take the BF2 bone's world rotation change (rest poses of the torso match well enough);
  limb segments (clavicle .. toe) are turned the shortest way onto the BF2 limb direction, so the different rest poses
  (BF2 arms out, ours down) don't matter; the rifle node (Right_Hand_node) follows BF2's hp_weapons hardpoint with a fixed
  offset calibrated so the BF2 shooting pose holds the gun like vanilla's GER_infantry_attack_stand_mg;
  the other weapon / prop nodes are scaled to ~0 like vanilla hides them. Locomotion stays in place.
Output: gfx/models/units/clonetrooper/bf2/REP_bf2_<clip>.anim (+ bf2_anims.asset there; ids wired in infantry_REP.gfx).
"""
import math, os, sys
import bpy  # type: ignore
from mathutils import Matrix, Vector  # type: ignore

sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
from io_pdx_mesh.pdx_blender import blender_import_export as bie  # noqa: E402

WIP = "../ProjectKessilianWIPGFX/ProjectKessilianWIP"
SRC = WIP + "/3d/_glb/bf2_anim/human_rifle.glb"
VANILLA = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/models/units/GER_infantry_attack_stand_mg.anim"
OUT = "gfx/models/units/clonetrooper/bf2"
CLIPS = ["idle", "look", "check", "walk", "run", "shoot", "crouchshoot", "death"]
# BF2 walk / run are lower-body clips (the game lays an aim pose over the upper body; their own spine keys twist the
# trooper round and tip the head back): legs + pelvis from them, spine / arms / rifle from the rifle-ready pose
UPPER_FROM = {"walk": "alert", "run": "alert"}
DELTA = {"Hip": "bone_pelvis", "back_mid": "bone_ribcage", "head": "bone_head"}
HAND = {"LeftHand": ("LeftForeArm", "bone_l_hand", "eff_l_hand"), "RightHand": ("RightForeArm", "bone_r_hand", "eff_r_hand")}
LIMB = {   # our bone: (BF2 joint at its head, BF2 joint it points at)
    "LeftShoulder": ("bone_l_clavicle", "bone_l_upperarm"), "LeftArm": ("bone_l_upperarm", "bone_l_forearm"),
    "LeftForeArm": ("bone_l_forearm", "bone_l_hand"),
    "RightShoulder": ("bone_r_clavicle", "bone_r_upperarm"), "RightArm": ("bone_r_upperarm", "bone_r_forearm"),
    "RightForeArm": ("bone_r_forearm", "bone_r_hand"),
    "LeftUpLeg": ("bone_l_thigh", "bone_l_calf"), "LeftLeg": ("bone_l_calf", "bone_l_foot"), "LeftFoot": ("bone_l_foot", "bone_l_toe"),
    "LeftToeBase": ("bone_l_toe", "eff_l_toe"),
    "RightUpLeg": ("bone_r_thigh", "bone_r_calf"), "RightLeg": ("bone_r_calf", "bone_r_foot"), "RightFoot": ("bone_r_foot", "bone_r_toe"),
    "RightToeBase": ("bone_r_toe", "eff_r_toe"),
}
LIMB_CHILD = {"LeftShoulder": "LeftArm", "LeftArm": "LeftForeArm", "LeftForeArm": "LeftHand", "RightShoulder": "RightArm",
              "RightArm": "RightForeArm", "RightForeArm": "RightHand", "LeftUpLeg": "LeftLeg", "LeftLeg": "LeftFoot",
              "LeftFoot": "LeftToeBase", "RightUpLeg": "RightLeg", "RightLeg": "RightFoot", "RightFoot": "RightToeBase"}
GUN, HIDE = "Right_Hand_node", ("Left_Hand_node", "Left_Hand_node_2", "Left_Hand_node_3", "Left_Hand_node_4", "Right_Hand_node_2",
                                "Right_Hand_node_3", "Right_Hand_node_4", "mid_back_node", "Root_node_1", "Root_node_2")
TINY = 1e-4


def rot_between(a, b):
    a, b = a.normalized(), b.normalized()
    return a.rotation_difference(b).to_matrix().to_4x4()


def about(m, pivot):          # rotation m about a world point
    return Matrix.Translation(pivot) @ m @ Matrix.Translation(-pivot)


def run(mesh_path):
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images, bpy.data.actions):
        for x in list(coll):     # not read_factory_settings(use_empty): the 4.2 pdx importer needs a normal scene
            coll.remove(x)
    bpy.context.scene.render.fps = 30
    bie.import_meshfile(os.path.abspath(mesh_path), imp_mesh=True, imp_skel=True, imp_locs=False, join_materials=False)
    tgt = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    # vanilla aiming pose: where the rifle node sits while shooting (calibrates the hp_weapons -> Right_Hand_node offset)
    bpy.context.view_layer.objects.active = tgt
    tgt.select_set(True)
    bie.import_animfile(VANILLA, frame_start=1)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    gun_vanilla = tgt.pose.bones[GUN].matrix.copy()
    tgt.animation_data.action = None
    for pb in tgt.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(SRC))
    src = next(o for o in bpy.data.objects if o.type == "ARMATURE" and o is not tgt)
    for o in [o for o in bpy.data.objects if o.type == "MESH" and o.parent is src]:
        bpy.data.objects.remove(o)
    bpy.context.view_layer.update()
    R = {b.name: b.matrix_local.copy() for b in tgt.data.bones}                # target rest, armature space
    S = {b.name: src.matrix_world @ b.matrix_local for b in src.data.bones}   # source rest, world
    k = (R["Hip"].translation.z) / max(S["bone_pelvis"].translation.z, 1e-3)    # BF2 trooper -> our trooper size
    order = []
    def visit(b):
        order.append(b.name)
        for c in b.children:
            visit(c)
    visit(tgt.data.bones["Root"])
    tgt.animation_data_create()
    # rifle offset: BF2 hp_weapons in its first shooting frame -> vanilla's aiming Right_Hand_node (world rotation)
    src.animation_data.action = next(a for a in bpy.data.actions if a.name.split("_")[0] == "shoot")
    bpy.context.scene.frame_set(0)
    gun_off = (src.matrix_world @ src.pose.bones["hp_weapons"].matrix).to_3x3().inverted() @ gun_vanilla.to_3x3()
    for clip in CLIPS:
        sact = next(a for a in bpy.data.actions if a.name.split("_")[0] == clip or a.name == clip)
        src.animation_data.action = sact
        f0, f1 = (int(x) for x in sact.frame_range)
        upper = []
        if clip in UPPER_FROM:     # the upper-body pose's frames (world), read before the clip itself
            ua = next(a for a in bpy.data.actions if a.name.split("_")[0] == UPPER_FROM[clip])
            src.animation_data.action = ua
            u0, u1 = (int(x) for x in ua.frame_range)
            for uf in range(u0, u1):
                bpy.context.scene.frame_set(uf)
                upper.append({b.name: src.matrix_world @ src.pose.bones[b.name].matrix for b in src.data.bones})
            src.animation_data.action = sact
        top = [b.name for b in src.data.bones["root_a_spine"].children_recursive] + ["root_a_spine"]
        act = bpy.data.actions.new(f"bf2_{clip}")
        tgt.animation_data.action = act
        for f in range(f0, f1 + 1):
            bpy.context.scene.frame_set(f)
            P = {b.name: src.matrix_world @ src.pose.bones[b.name].matrix for b in src.data.bones}   # source pose, world
            if upper:              # upper body rides the walking root, facing as in the ready pose
                U = upper[(f - f0) % len(upper)]
                M = P["bone_root"] @ U["bone_root"].inverted()
                for n in top:
                    P[n] = M @ U[n]
            sp = lambda n: P[n].translation * k
            root_drift = (P["bone_root"].translation - S["bone_root"].translation) * k
            root_drift.z = 0                                                     # in place: drop locomotion
            W = {}
            for n in order:
                b = tgt.data.bones[n]
                par = b.parent.name if b.parent else None
                inherit = (W[par] @ R[par].inverted() @ R[n]) if par else R[n].copy()
                if n == "Hip":
                    d = P[DELTA[n]].to_3x3() @ S[DELTA[n]].to_3x3().inverted() @ R[n].to_3x3()
                    w = d.to_4x4()
                    w.translation = sp("bone_pelvis") - root_drift + (R[n].translation - S["bone_pelvis"].translation * k)
                elif n in DELTA:
                    d = P[DELTA[n]].to_3x3() @ S[DELTA[n]].to_3x3().inverted() @ R[n].to_3x3()
                    w = d.to_4x4()
                    w.translation = inherit.translation
                elif n in HAND:        # rest hands run straight on from the forearm: aim them along BF2's hand
                    fa, a, c = HAND[n]
                    head = inherit.translation
                    w = about(rot_between(head - W[fa].translation, P[c].translation - P[a].translation), head) @ inherit
                elif n == GUN:
                    w = (P["hp_weapons"].to_3x3() @ gun_off).to_4x4()
                    w.translation = W["Hip"].translation + (P["hp_weapons"].translation - P["bone_pelvis"].translation) * k
                elif n in LIMB:
                    a, c = LIMB[n]
                    child = LIMB_CHILD.get(n)
                    head = inherit.translation
                    cur = ((inherit @ R[n].inverted() @ R[child]).translation - head) if child else inherit.to_3x3() @ Vector((0, 1, 0))
                    want = P[c].translation - P[a].translation
                    w = about(rot_between(cur, want), head) @ inherit
                else:
                    w = inherit
                W[n] = w
            for n in order:
                pb = tgt.pose.bones[n]
                pb.rotation_mode = "QUATERNION"
                par = tgt.data.bones[n].parent
                if par:
                    pb.matrix_basis = (R[par.name].inverted() @ R[n]).inverted() @ (W[par.name].inverted() @ W[n])
                else:
                    pb.matrix_basis = R[n].inverted() @ W[n]
                pb.scale = (TINY,) * 3 if n in HIDE else (1, 1, 1)
                pb.keyframe_insert("location", frame=f)
                pb.keyframe_insert("rotation_quaternion", frame=f)
                pb.keyframe_insert("scale", frame=f)
        print("CLIP", clip, f0, f1)
    return tgt


MESHES = [f"gfx/models/units/clonetrooper/{m}.mesh" for m in ("REP_infantry", "REP_infantry_p2", "REP_infantry_empire")] +          ["gfx/models/units/old_republic/REP_old_trooper.mesh"]
# HOI4 animation id -> BF2 clip (training / cavalry / exercise ids stay vanilla)
IDS = {"idle": "idle", "long_idle01": "look", "long_idle02": "check", "long_idle03": "idle", "long_idle04": "look",
       "long_idle05": "check", "attack": "crouchshoot", "support_attack": "shoot", "charge_rifle": "run",
       "charge_rifle_shoot": "shoot", "move": "walk", "march_move": "walk", "retreat": "run", "death": "death"}


def wire():
    """plain python: bf2_anims.asset next to the .anim files + the clone meshes' animation ids in gfx/entities/*.gfx"""
    import codecs, glob, re
    lines = ["# HOD: Battlefront II soldier animations on the clone rigs (plans & scripts/infantry_bf2_anims.py)"]
    for m in MESHES:
        stem = os.path.splitext(os.path.basename(m))[0]
        lines += [f'animation = {{ name = "REP_bf2_{stem}_{c}_animation" file = "{stem}_{c}.anim" }}' for c in CLIPS]
    open(f"{OUT}/bf2_anims.asset", "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    files = {os.path.basename(m): os.path.splitext(os.path.basename(m))[0] for m in MESHES}
    for g in glob.glob("gfx/entities/*.gfx"):
        raw = open(g, "rb").read()
        bom = raw.startswith(codecs.BOM_UTF8)
        txt = raw.decode("utf-8-sig")
        out, n, pos = [], 0, 0
        for mt in re.finditer(r"pdxmesh\s*=\s*\{", txt):
            if mt.start() < pos:
                continue
            depth, i = 0, mt.end() - 1
            while True:
                depth += {"{": 1, "}": -1}.get(txt[i], 0)
                if depth == 0:
                    break
                i += 1
            block = txt[mt.start():i + 1]
            f = re.search(r'file\s*=\s*"[^"]*/([^"/]+\.mesh)"', block)
            if f and f.group(1) in files:
                stem = files[f.group(1)]
                def sub(m2):
                    return f'{m2.group(1)}"REP_bf2_{stem}_{IDS[m2.group(2)]}_animation"'
                block, k = re.subn(r'(id\s*=\s*"(' + "|".join(IDS) + r')"\s+type\s*=\s*)"[^"]+"', sub, block)
                n += k
            out.append(txt[pos:mt.start()] + block)
            pos = i + 1
        if n:
            out.append(txt[pos:])
            open(g, "wb").write((codecs.BOM_UTF8 if bom else b"") + "".join(out).encode("utf-8"))
            print("wired", g, n)


def render(tgt, out, frames):
    """check sheet: the soldier at a few frames of every clip (-- --render OUT_PREFIX)"""
    sc = bpy.context.scene
    for o in [o for o in bpy.data.objects if o.type == "ARMATURE" and o is not tgt]:
        for c in list(o.children):
            bpy.data.objects.remove(c)
        bpy.data.objects.remove(o)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 240, 320
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (Vector((-3.0, 0, 0.5)) if os.environ.get("HOD_SIDE") else Vector((-1.9, -2.4, 0.9))) * (tgt.data.bones["head"].head_local.z / 1.6)
    cam.rotation_euler = (Vector((0, 0, tgt.data.bones["Hip"].head_local.z)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    for clip in CLIPS:
        tgt.animation_data.action = bpy.data.actions[f"bf2_{clip}"]
        f0, f1 = (int(x) for x in tgt.animation_data.action.frame_range)
        for i in range(frames):
            sc.frame_set(f0 + (f1 - f0) * i // frames)
            sc.render.filepath = f"{out}_{clip}_{i}.png"
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__" and "bpy" in sys.modules:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if a and a[0] == "--render":
        t = run("gfx/models/units/clonetrooper/REP_infantry.mesh")
        print("XX tgt", t.matrix_world.to_euler(), t.data.bones["Hip"].head_local, t.data.bones["head"].head_local)
        render(t, a[1], 4)
    elif a and a[0] == "wire":
        wire()
    else:
        os.makedirs(OUT, exist_ok=True)
        for m in a or MESHES:
            t = run(m)
            stem = os.path.splitext(os.path.basename(m))[0]
            bpy.context.view_layer.objects.active = t
            t.select_set(True)
            for clip in CLIPS:
                t.animation_data.action = bpy.data.actions[f"bf2_{clip}"]
                f0, f1 = (int(x) for x in t.animation_data.action.frame_range)
                bpy.context.scene.frame_start, bpy.context.scene.frame_end = f0, f1
                bie.export_animfile(os.path.abspath(f"{OUT}/{stem}_{clip}.anim"), frame_start=f0, frame_end=f1)
            print("ANIMS", stem, len(CLIPS))
