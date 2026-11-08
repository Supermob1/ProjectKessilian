"""Blender 4.2: Battlefront II (ZeroEngine) model .msh + its animation .msh files -> rigged .glb with one action per clip,
for unit_models.py "bake" mode (which rebuilds a small game rig from it).

  blender -b --factory-startup --python "plans & scripts/msh_anim_to_glb.py" -- OUT.glb model.msh clip=a.msh[+b.msh ...] ... [skel=clip_skeleton.msh]

Every MODL node becomes a bone at its TRAN rest; geometry: skinned segments (WGHT -> envelope) keep their weights,
rigid parts go 100 % to their own node. Animation keys (KFR3) are parent-relative like TRAN; a clip of several files
(walk_leftfoot_rightfoot + walk_rightfoot_leftfoot = one full stride) is played back to back. Y up -> Z up.
"""
import os, sys
import bpy  # type: ignore
from mathutils import Matrix, Quaternion, Vector  # type: ignore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swbf_msh  # noqa: E402
from msh_to_glb import SKIP_IN, SKIP_START, texture, world_of  # noqa: E402

YUP = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # (x, y, z) -> (x, -z, y)


def tran(pos, rot):
    x, y, z, w = rot
    return Matrix.Translation(pos) @ Quaternion((w, x, y, z)).to_matrix().to_4x4()


def convert(out, model, clips, skel=None):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    model = os.path.abspath(model)
    d = swbf_msh.read(model)
    by = {m["name"]: m for m in d["models"]}
    by_index = {m["index"]: m["name"] for m in d["models"]}
    world = world_of(d["models"])
    rest_rel = {n: (tran(m["tran"]["pos"], m["tran"]["rot"]) if m["tran"] else Matrix()) for n, m in by.items()}
    # armature: every node a bone, rest = world matrix (Z up)
    arm = bpy.data.objects.new("rig", bpy.data.armatures.new("rig"))
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for n in by:
        eb = arm.data.edit_bones.new(n)
        eb.head, eb.tail = (0, 0, 0), (0, 0.05, 0)
        eb.matrix = YUP @ world(n)
    for n, m in by.items():
        if m["parent"] in by:
            arm.data.edit_bones[n].parent = arm.data.edit_bones[m["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    # geometry
    mats, by_tex = [], {}
    for name, texs in d["materials"]:
        tex = texture(model, texs[0] if texs else "")
        if tex in by_tex:                        # one material per texture: each becomes its own set of game DDS files
            mats.append(by_tex[tex])
            continue
        mt = by_tex[tex] = bpy.data.materials.new(name or "mat")
        mt.use_nodes = True
        if tex:
            node = mt.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = bpy.data.images.load(tex)
            mt.node_tree.links.new(node.outputs["Color"], mt.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        mats.append(mt)
    parts = 0
    for mdl in d["models"]:
        low = mdl["name"].lower()
        if mdl["hidden"] or not mdl["segments"] or low.startswith(SKIP_START) or any(w in low for w in SKIP_IN):
            continue
        M = YUP @ world(mdl["name"])
        for k, seg in enumerate(mdl["segments"]):
            if not seg["tris"] or not seg["pos"]:
                continue
            me = bpy.data.meshes.new(f"{mdl['name']}_{k}")
            me.from_pydata([tuple(M @ Vector(p)) for p in seg["pos"]], [], list(seg["tris"]))
            if seg["uv"]:
                uv = me.uv_layers.new(name="UVMap")
                for poly in me.polygons:
                    for li in poly.loop_indices:
                        uv.data[li].uv = seg["uv"][me.loops[li].vertex_index]
            if 0 <= seg["mat"] < len(mats):
                me.materials.append(mats[seg["mat"]])
            me.validate()
            o = bpy.data.objects.new(me.name, me)
            bpy.context.scene.collection.objects.link(o)
            groups = {}
            if seg["weights"] and mdl["envelope"]:
                for vi, ws in enumerate(seg["weights"]):
                    for idx, w in ws:
                        if w > 0 and idx < len(mdl["envelope"]):
                            groups.setdefault(by_index[mdl["envelope"][idx]], []).append((vi, w))
            else:
                bone = by_index[mdl["envelope"][0]] if mdl["envelope"] else mdl["name"]
                groups[bone] = [(vi, 1.0) for vi in range(len(seg["pos"]))]
            for bone, vw in groups.items():
                g = o.vertex_groups.get(bone) or o.vertex_groups.new(name=bone)
                for vi, w in vw:
                    g.add([vi], w, "ADD")
            o.parent = arm
            o.modifiers.new("rig", "ARMATURE").object = arm
            parts += 1
    # animations, retargeted through world space: the clip moves the skeleton it was made for (skel=, default the model
    # itself); each target bone gets that bone's world delta. Munged models (Conversion Pack AT-XT) lack the root_*
    # helper nodes the AT-ST clips key, so parent-relative keys can't be copied over.
    sk = swbf_msh.read(os.path.abspath(skel)) if skel else d
    sby = {m["name"].lower(): m for m in sk["models"]}
    s_rest = world_of(sk["models"])
    rest_w = {n: world(n) for n in by}
    order = []                                   # parents before children
    def visit(n):
        if n not in order:
            if by[n]["parent"] in by:
                visit(by[n]["parent"])
            order.append(n)
    for n in by:
        visit(n)
    bpy.context.scene.render.fps = 30
    arm.animation_data_create()
    for clip in clips:
        cname, files = clip.split("=", 1)
        act = bpy.data.actions.new(cname)
        act.use_fake_user = True
        arm.animation_data.action = act
        frames, segs = [], []
        for f in files.split("+"):
            segs.append(len(frames))
            a = swbf_msh.read_anim(f)
            _, _, f0, f1 = a["cycles"][0]
            keyed = {n.lower(): v for n, v in a["bones"].items()}
            for fr in range(f0, f1 + (1 if f is files.split("+")[-1] else 0)):     # stitched clips share the seam frame
                sw = {}
                def s_anim(low):                  # world matrix of a skeleton node at this frame
                    if low not in sw:
                        m, k = sby[low], keyed.get(low)
                        t = m["tran"] or dict(pos=(0, 0, 0), rot=(0, 0, 0, 1), scale=(1, 1, 1))
                        pos = next((v for q, v in reversed(k["t"]) if q <= fr), k["t"][0][1]) if k and k["t"] else t["pos"]
                        rot = next((v for q, v in reversed(k["r"]) if q <= fr), k["r"][0][1]) if k and k["r"] else t["rot"]
                        if low.startswith(("aimer_", "barrel_")):   # engine-aimed in BF2: clips key them in another bone
                            rot = t["rot"]                            # frame (AT-AT head twisted): rest rotation, and
                            if m["parent"].lower().startswith(("aimer_", "barrel_")):   # only the head's own bob
                                pos = t["pos"]
                        loc = tran(pos, rot) @ Matrix.Diagonal((*t["scale"], 1.0))
                        par = m["parent"].lower()
                        sw[low] = (s_anim(par) if par in sby else Matrix()) @ loc
                    return sw[low]
                tw = {}
                for n in order:
                    if n.lower() in sby:
                        tw[n] = s_anim(n.lower()) @ s_rest(sby[n.lower()]["name"]).inverted() @ rest_w[n]
                    else:
                        p = by[n]["parent"]
                        tw[n] = tw[p] @ rest_w[p].inverted() @ rest_w[n] if p in by else rest_w[n]   # unkeyed: rides its parent
                frames.append(tw)
        # in place: every BF2 walk file (half a stride) carries its own locomotion from its own start, so the body walked
        # forward and jumped back at each file seam. Per file, remove the body's horizontal drift (msh space: Y up) at
        # that file's average speed and pin its start to the clip's start.
        ref = next((n for n in by if n.lower() in ("bone_root", "bone_pelvis")), None) or min(
            by, key=lambda n: len(n) if by[n]["parent"] not in by else 1e9)
        flat = lambda v: Vector((v.x, 0.0, v.z))
        p0 = flat(frames[0][ref].translation)
        offs = []
        for k, a0 in enumerate(segs):
            a1 = segs[k + 1] if k + 1 < len(segs) else len(frames)
            ps, pe = flat(frames[a0][ref].translation), flat(frames[a1 - 1][ref].translation)
            vel = (pe - ps) / max(1, a1 - 1 - a0)
            offs += [-(ps - p0) - vel * (i - a0) for i in range(a0, a1)]
        print("DRIFT", cname, ref, [round(x, 2) for x in -offs[-1]])
        for frame, tw in enumerate(frames):
            off = Matrix.Translation(offs[frame])
            for pb in arm.pose.bones:
                n, p = pb.name, by[pb.name]["parent"]
                pb.rotation_mode = "QUATERNION"
                if p in by:
                    pb.matrix_basis = (rest_w[p].inverted() @ rest_w[n]).inverted() @ (tw[p].inverted() @ tw[n])
                else:
                    pb.matrix_basis = rest_w[n].inverted() @ off @ tw[n]     # YUP on both sides cancels
                pb.keyframe_insert("location", frame=frame)
                pb.keyframe_insert("rotation_quaternion", frame=frame)
        print("CLIP", cname, len(frames), "frames")
    arm.animation_data.action = None
    for im in bpy.data.images:
        if im.size[0] and not im.packed_file:
            im.pack()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(out), export_format="GLB", export_animation_mode="ACTIONS", export_skins=True)
    print("MSHANIM", os.path.basename(model), parts, "parts", len(by), "bones ->", out)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    sk = next((x[5:] for x in a if x.startswith("skel=")), None)
    convert(a[0], a[1], [x for x in a[2:] if not x.startswith("skel=")], sk)
