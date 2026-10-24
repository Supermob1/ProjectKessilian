"""Sketchfab (CC BY 4.0) Star Wars vehicles -> animated HOI4 unit models for the walker battalions.

  blender -b --factory-startup --python "WIPGFX/plans & scripts/unit_models.py" -- convert [name ...]
  python "WIPGFX/plans & scripts/unit_models.py" textures      source PNGs -> diffuse / normal / spec DDS
  python "WIPGFX/plans & scripts/unit_models.py" wire          gfx/entities/hod_sw_walkers.{gfx,asset}

Models go to gfx/models/units/hod_walkers/<name>.mesh + <name>_<anim>.anim. Rigs are rebuilt for the game: the
source animation is baked onto a small skeleton (dropped bones hand their skin weights to the nearest kept ancestor),
the mesh is decimated, nose to -Y, ground at z = 0 (the vanilla convention, checked against iron_strider.mesh).

CREDITS (CC BY 4.0, author must be credited):
  AT-TE Walker (Animated) - R3negadeAidan   https://sketchfab.com/3d-models/at-te-walker-animated-81ef81cf6c554055b741b43a1a08d69f
  -Star Wars- AAT - ARKON-83                 https://sketchfab.com/3d-models/star-wars-aat-9ed126f4616a482fabee52b0e0d46e52
  AT-RT - Just Ryk                           https://sketchfab.com/3d-models/at-rt-6796698b4d564377838c06319ec96f90
"""
import json, math, os, re, sys

SRC = "WIPGFX/3d/sketchfab"
OUT = "gfx/models/units/hod_walkers"
SIDE = "WIPGFX/3d/sketchfab/_baked/unit_models.json"     # texture sources per material, written by convert
TEX_PX = 1024

# keep: bones of the game rig (regex on source bone names); length: largest horizontal extent in mesh units;
# anims: game animation -> (source action or None, first frame, last frame)
SPECS = {
    "hod_atte": dict(src="at-te_walker_animated", mode="bake", length=10.0, tris=12000, protect=r"Turret",
                     keep=r"(GLTF_created_0_rootJoint|Hips_56|Head_21|Butt_36|Hips_Offset_55|Turret_Base_Pivot_13|Turret_12"
                          r"|Turret_Barrel_11|(Left|Right)(Front|Back)(Shoulder|Leg|LowLeg)_\d+|(Left|Right)Middle(Leg|LowLeg)_\d+"
                          r"|(Left|Right)(Front|Back|Middle)Ankle_\d+)$",
                     gun="Turret_Barrel_11", forward="Head_21", back="Butt_36",   # heading: rear section -> head
                     anims={"idle": (None, 0, 1), "move": (None, 0, 480), "attack": (None, 0, 1)}),
    "hod_aat": dict(src="-star_wars-_aat", mode="bake", length=8.0, tris=7000, keep=r".*", gun="Main Gun_02",
                    forward="Main Gun_end_05", norm_action="Static_Object_9",   # turret centred: the idle swings it
                    anims={"idle": ("Idle_Object_9", 0, 150), "move": ("Idle_Object_9", 0, 150), "attack": ("Static_Object_9", 0, 1)}),
    "hod_atrt": dict(src="at-rt", mode="rebuild", height=6.0, tris=5000),
    # Old Republic lance walker (Battlefront II mod .msh, WIPGFX/3d/old_republic_lance_walker): rigid parts on an
    # AT-ST style skeleton; walk cycle generated here
    "hod_lance_walker": dict(src="WIPGFX/3d/old_republic_lance_walker/orp_walk_lance.msh", mode="msh_walker", height=8.0, tris=6000,
                             texture="WIPGFX/3d/old_republic_lance_walker/Republic_Lance_Walker.tga"),
}
MSH_BONES = ["bone_root", "bone_head"] + [f"bone_{s}_{p}" for s in "lr" for p in ("thigh", "calf", "foot", "ball", "toe")]


# ─────────────────────────────── Blender side ───────────────────────────────
def convert(*only):
    import bpy  # type: ignore
    from mathutils import Matrix, Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    os.makedirs(OUT, exist_ok=True)
    side = json.load(open(SIDE)) if os.path.exists(SIDE) else {}

    class Mat:
        def __init__(self, stem):
            self.shader = ["PdxMeshAdvanced"]
            self.diff, self.n, self.spec = [f"{stem}_diffuse.dds"], [f"{stem}_normal.dds"], [f"{stem}_spec.dds"]

    def select(objs, active=None):
        bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
        for o in bpy.context.scene.objects:
            o.select_set(o in objs)
        bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)

    def world_box(meshes):
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for o in meshes:
            ev = o.evaluated_get(dg)
            pts += [ev.matrix_world @ v.co for v in ev.data.vertices]
        return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]

    def texture_sources(mat):
        """baseColor / metallicRoughness image paths of a glTF material"""
        out = {}
        if not mat or not mat.use_nodes:
            return out
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                for link in node.outputs["Color"].links:
                    sock = link.to_socket.name
                    kind = "base" if sock == "Base Color" else "mr" if link.to_node.type == "SEPARATE_COLOR" else None
                    if kind:
                        out[kind] = bpy.path.abspath(node.image.filepath)
        return out

    def finish(name, meshes, rig, locs, anims):
        """materials, decimation, export"""
        s = SPECS[name]
        select(meshes, meshes[0])
        if len(meshes) > 1:
            bpy.ops.object.join()
        mesh = bpy.context.view_layer.objects.active
        mesh.data.update()                  # direct vertex edits leave the evaluated (cached) mesh stale
        bpy.context.view_layer.update()
        tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
        if tris > s["tris"]:
            dec = mesh.modifiers.new("dec", "DECIMATE")
            dec.ratio = s["tris"] / tris
            if s.get("protect"):                  # thin parts (gun barrels) collapse under decimation: leave them whole
                prot = mesh.vertex_groups.new(name="_protect")
                ids = {g.index for g in mesh.vertex_groups if re.search(s["protect"], g.name)}
                prot.add([v.index for v in mesh.data.vertices if any(g.group in ids and g.weight > 0.3 for g in v.groups)], 1.0, "REPLACE")
                dec.vertex_group, dec.invert_vertex_group = "_protect", True
            for m in list(mesh.modifiers):        # the armature modifier must come after the decimation
                if m.type == "ARMATURE":
                    mesh.modifiers.remove(m)
            bpy.ops.object.modifier_apply(modifier="dec")
            arm_mod = mesh.modifiers.new("rig", "ARMATURE")
            arm_mod.object = rig
        if mesh.vertex_groups.get("_protect"):
            mesh.vertex_groups.remove(mesh.vertex_groups["_protect"])
        bpy.ops.object.vertex_group_limit_total(limit=4)
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        side[name] = []
        for i, slot in enumerate(mesh.material_slots):
            stem = f"{name}_{i}" if len(mesh.material_slots) > 1 else name
            side[name].append(dict(stem=stem, **texture_sources(slot.material)))
            pm = bie.create_shader(Mat(stem), stem, os.path.abspath(OUT))
            pm[PDX_SHADER] = "PdxMeshAdvanced"
            slot.material = pm
        mesh.name = mesh.data.name = name
        for o in [o for o in bpy.context.scene.objects if o not in (mesh, rig) and o not in locs]:
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.context.scene.frame_set(0)
        bie.export_meshfile(os.path.abspath(f"{OUT}/{name}.mesh"), exp_mesh=True, exp_skel=True, exp_locs=True)
        select([rig], rig)
        for game_anim, (action, f0, f1) in anims.items():
            rig.animation_data.action = bpy.data.actions[action]
            bpy.context.scene.frame_start, bpy.context.scene.frame_end = f0, f1
            bie.export_animfile(os.path.abspath(f"{OUT}/{name}_{game_anim}.anim"), frame_start=f0, frame_end=f1)
        lo, hi = world_box([mesh])
        print(f"{name}: {tris} -> {len(mesh.data.polygons)} faces, {len(rig.data.bones)} bones, "
              f"size {hi[0]-lo[0]:.2f} x {hi[1]-lo[1]:.2f} x {hi[2]-lo[2]:.2f}")

    def add_locator(name, rig, bone, pos):
        e = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(e)
        e.parent, e.parent_type, e.parent_bone = rig, "BONE", bone
        e.matrix_world = Matrix.Translation(pos)
        return e

    def normaliser(meshes, fwd_from, fwd_to, length=None, height=None):
        """an empty above every top-level object: yaw so fwd_from->fwd_to points to -Y, scale, centre, ground"""
        norm = bpy.data.objects.new("norm", None)
        bpy.context.scene.collection.objects.link(norm)
        for o in [o for o in bpy.context.scene.objects if o.parent is None and o is not norm]:
            mw = o.matrix_world.copy()
            o.parent = norm
            o.matrix_world = mw
        d = fwd_to - fwd_from
        yaw = math.atan2(d.x, -d.y)                  # angle that turns d onto -Y
        norm.matrix_world = Matrix.Rotation(yaw, 4, "Z")
        bpy.context.view_layer.update()
        lo, hi = world_box(meshes)
        k = length / max(hi[0] - lo[0], hi[1] - lo[1]) if length else height / (hi[2] - lo[2])
        c = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]))
        norm.matrix_world = Matrix.Scale(k, 4) @ Matrix.Translation(-c) @ norm.matrix_world
        bpy.context.view_layer.update()
        return norm

    def msh_walker(name, s):
        """Battlefront II walker: parts in bind pose, each bound to one skeleton bone; rebuilt rig + walk cycle"""
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import swbf_msh
        from mathutils import Quaternion  # type: ignore
        d = swbf_msh.read(s["src"])
        by = {m["name"]: m for m in d["models"]}
        by_index = {m["index"]: m["name"] for m in d["models"]}
        # the .msh (Softimage XSI export) is right-handed, Y up, +Z ahead; the game wants Z up, -Y ahead
        C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
        W = {}
        def world(n):
            if n not in W:
                t = by[n]["tran"]
                x, y, z, w = t["rot"]
                loc = Matrix.Translation(t["pos"]) @ Quaternion((w, x, y, z)).to_matrix().to_4x4()
                W[n] = (world(by[n]["parent"]) if by[n]["parent"] in by else Matrix()) @ loc
            return W[n]
        def kept(bone):          # a part bound to a bone the game rig drops goes to its nearest kept ancestor
            while bone not in MSH_BONES:
                bone = by[bone]["parent"]
            return bone
        verts, faces, groups = [], [], {}
        for m in d["models"]:
            if m["type"] != 1 or m["hidden"] or not m["envelope"] or m["name"].startswith("polymsh"):
                continue
            bone = kept(by_index[m["envelope"][0]])
            for g in m["segments"]:
                base = len(verts)
                pts = [C @ Vector(p) for p in g["pos"]]
                nrm = [C @ Vector(n) for n in g["nrm"]] if g["nrm"] else None
                verts += pts
                for a, b, c in g["tris"]:
                    f = (base + a, base + b, base + c)
                    if nrm:     # strips and the mirror leave winding mixed: face the way the source normals point
                        if (pts[b] - pts[a]).cross(pts[c] - pts[a]).dot(nrm[a] + nrm[b] + nrm[c]) < 0:
                            f = (f[0], f[2], f[1])
                    faces.append(f)
                groups.setdefault(bone, []).extend(range(base, len(verts)))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        uvs = [uv for m in d["models"] if m["type"] == 1 and not m["hidden"] and m["envelope"] and not m["name"].startswith("polymsh")
               for g in m["segments"] for uv in (g["uv"] or [(0, 0)] * len(g["pos"]))]
        uv = mesh.uv_layers.new(name="uv0")
        uv.data.foreach_set("uv", [c for p in mesh.polygons for li in p.loop_indices
                                   for c in uvs[mesh.loops[li].vertex_index]])   # the .msh V is already bottom-up (tiles wrap)
        o = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(o)
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.abspath(s["texture"]))
        mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        mesh.materials.append(mat)
        for bone, ids in groups.items():
            o.vertex_groups.new(name=bone).add(ids, 1.0, "REPLACE")
        # scale to the game height, centred, feet on the ground
        lo = Vector([min(v[i] for v in verts) for i in range(3)])
        hi = Vector([max(v[i] for v in verts) for i in range(3)])
        k = s["height"] / (hi.z - lo.z)
        N = Matrix.Scale(k, 4) @ Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)))
        mesh.transform(N)
        head = {b: N @ (C @ world(b).translation) for b in MSH_BONES}
        tip = N @ (C @ world("eff_l_toe").translation)
        rig_data = bpy.data.armatures.new("rig")
        rig = bpy.data.objects.new("rig", rig_data)
        bpy.context.scene.collection.objects.link(rig)
        select([rig], rig)
        bpy.ops.object.mode_set(mode="EDIT")
        child = {"bone_root": None, "bone_head": None}
        for sd in "lr":
            chain = [f"bone_{sd}_{p}" for p in ("thigh", "calf", "foot", "ball", "toe")]
            for a, b in zip(chain, chain[1:]):
                child[a] = b
            child[chain[-1]] = None
        for b in MSH_BONES:
            eb = rig_data.edit_bones.new(b)
            eb.head = head[b]
            eb.tail = head[child[b]] if child[b] else head[b] + Vector((0, 0, 0.1 * s["height"]))
            if b.endswith("_toe"):
                eb.tail = N @ (C @ world(f"eff_{b[5]}_toe").translation)
        for b in MSH_BONES[1:]:
            par = by[b]["parent"]
            while par not in MSH_BONES:
                par = by[par]["parent"]
            rig_data.edit_bones[b].parent = rig_data.edit_bones[par]
        bpy.ops.object.mode_set(mode="OBJECT")
        o.modifiers.new("rig", "ARMATURE").object = rig
        # walk: 48-frame loop, legs half a cycle apart. Each leg swings about the hip; the swinging leg folds at the
        # ankle to clear the ground; toes stay level; the body drops so the planted foot stays on the ground
        select([rig], rig)
        bpy.ops.object.mode_set(mode="POSE")
        rig.animation_data_create()
        rig.animation_data.action = bpy.data.actions.new("walk")
        rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
        rot_at = lambda p, ang: Matrix.Translation(p) @ Matrix.Rotation(ang, 4, "X") @ Matrix.Translation(-p)
        swing, fold = math.radians(16), math.radians(22)
        for f in range(49):
            ph = 2 * math.pi * f / 48
            drop = Matrix.Translation((0, 0, -(1 - math.cos(swing)) * (head["bone_l_thigh"].z - tip.z) * abs(math.sin(ph))))
            rig.pose.bones["bone_root"].matrix = drop @ rest["bone_root"]
            rig.pose.bones["bone_head"].matrix = drop @ rest["bone_head"]
            for sd, off in (("l", 0.0), ("r", math.pi)):
                a = -swing * math.sin(ph + off)                              # forward = toward -Y
                b = fold * max(0.0, math.cos(ph + off))                      # fold while the leg swings forward
                hip, ankle, ball = (head[f"bone_{sd}_{p}"] for p in ("thigh", "foot", "ball"))
                m_leg = drop @ rot_at(hip, a)
                m_shin = m_leg @ rot_at(ankle, -b)
                ball_n = m_shin @ ball
                m_toe = Matrix.Translation(ball_n - ball)                    # toes level: no rotation
                for bn, m in ((f"bone_{sd}_thigh", m_leg), (f"bone_{sd}_calf", m_leg), (f"bone_{sd}_foot", m_shin),
                              (f"bone_{sd}_ball", m_toe), (f"bone_{sd}_toe", m_toe)):
                    rig.pose.bones[bn].matrix = m @ rest[bn]
                    bpy.context.view_layer.update()
            for pb in rig.pose.bones:
                pb.keyframe_insert("location", frame=f)
                pb.keyframe_insert("rotation_quaternion", frame=f)
        bpy.ops.object.mode_set(mode="OBJECT")
        barrel = N @ (C @ world("hp_cannon_1").translation)
        locs = [add_locator("barrel", rig, "bone_head", barrel),
                add_locator("smoke", rig, "bone_root", head["bone_root"] + Vector((0, 0.3 * s["height"], 0)))]
        finish(name, [o], rig, locs, {"idle": ("walk", 0, 1), "move": ("walk", 0, 48), "attack": ("walk", 0, 1)})

    for name, s in SPECS.items():
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if s["mode"] == "msh_walker":
            bpy.context.scene.render.fps = 24
            msh_walker(name, s)
            continue
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(f"{SRC}/{s['src']}/scene.gltf"))
        for o in [o for o in bpy.context.scene.objects if o.name.startswith("Icosphere")]:
            bpy.data.objects.remove(o, do_unlink=True)
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        arm = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"][0]
        bpy.context.scene.render.fps = 24

        if s["mode"] == "bake":
            # 1. pose the source at its first frame, normalise around it
            first = bpy.data.actions[s.get("norm_action") or s["anims"]["move"][0]] if (s.get("norm_action") or s["anims"]["move"][0]) else None
            if first:
                arm.animation_data.action = first
            bpy.context.scene.frame_set(0)
            pw = lambda b: arm.matrix_world @ arm.pose.bones[b].head
            normaliser(meshes, pw(s.get("back") or s["gun"]), pw(s["forward"]), length=s["length"])
            # 2. game rig: kept bones at the source's rest positions (world), parented to the nearest kept ancestor
            keep = [b.name for b in arm.data.bones if re.match(s["keep"], b.name) and not b.name.endswith(("_end_05", "_end_06", "_end_07"))]
            def kept_ancestor(bone):
                p = bone.parent
                while p and p.name not in keep:
                    p = p.parent
                return p.name if p else None
            rest = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local) for b in arm.data.bones}
            rig_data = bpy.data.armatures.new("rig")
            rig = bpy.data.objects.new("rig", rig_data)
            bpy.context.scene.collection.objects.link(rig)
            select([rig], rig)
            bpy.ops.object.mode_set(mode="EDIT")
            for n in keep:
                eb = rig_data.edit_bones.new(n)
                h, t = rest[n]
                eb.head, eb.tail = h, t if (t - h).length > 1e-4 else h + Vector((0, 0, 0.05))
                # same rest orientation (roll) as the source bone, or copied world rotations deform the skin wrongly
                eb.align_roll((arm.matrix_world.to_3x3() @ arm.data.bones[n].matrix_local.to_3x3()) @ Vector((0, 0, 1)))
            for n in keep:
                pa = kept_ancestor(arm.data.bones[n])
                if pa:
                    rig_data.edit_bones[n].parent = rig_data.edit_bones[pa]
            bpy.ops.object.mode_set(mode="POSE")
            for n in keep:                            # location + rotation only: the source carries the normaliser scale
                for kind in ("COPY_LOCATION", "COPY_ROTATION"):
                    c = rig.pose.bones[n].constraints.new(kind)
                    c.target, c.subtarget = arm, n
            # 3. bake every source action the game animations use onto the rig
            baked = {}
            for game_anim, (action, f0, f1) in s["anims"].items():
                key = action or "_main"
                if key not in baked:
                    if action:
                        arm.animation_data.action = bpy.data.actions[action]
                    span = max(f1, 1)
                    bpy.ops.nla.bake(frame_start=0, frame_end=span if key != "_main" else s["anims"]["move"][2],
                                     only_selected=False, visual_keying=True, clear_constraints=False,
                                     use_current_action=False, bake_types={"POSE"})
                    baked[key] = rig.animation_data.action.name
            for pb in rig.pose.bones:
                for c in list(pb.constraints):
                    pb.constraints.remove(c)
            anims = {g: (baked[a or "_main"], f0, f1) for g, (a, f0, f1) in s["anims"].items()}
            # 4. meshes: world space, skin weights moved onto kept bones, bound to the rig
            bpy.ops.object.mode_set(mode="OBJECT")
            for o in meshes:
                mw = o.matrix_world.copy()
                o.parent = None
                o.matrix_world = mw
                for m in list(o.modifiers):
                    if m.type == "ARMATURE":
                        o.modifiers.remove(m)
                select([o], o)
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                target = {}
                for g in o.vertex_groups:
                    if g.name in keep:
                        target[g.index] = g.name
                    elif g.name in arm.data.bones:
                        target[g.index] = kept_ancestor(arm.data.bones[g.name]) or keep[0]
                gid = {n: (o.vertex_groups.get(n) or o.vertex_groups.new(name=n)) for n in keep}
                acc = {}
                for v in o.data.vertices:
                    for g in v.groups:
                        if g.group in target and o.vertex_groups[g.group].name not in keep:
                            acc.setdefault((v.index, target[g.group]), 0.0)
                            acc[(v.index, target[g.group])] += g.weight
                for (vi, n), w in acc.items():
                    gid[n].add([vi], w, "ADD")
                for g in [g for g in o.vertex_groups if g.name not in keep]:
                    o.vertex_groups.remove(g)
                # vertices left without weight (groups that were no bone) would stay behind at rest: nearest kept bone
                heads = {n: rest[n][0] for n in keep}
                for v in o.data.vertices:
                    if sum(g.weight for g in v.groups if o.vertex_groups[g.group].name in keep) < 1e-3:
                        n = min(heads, key=lambda b: (heads[b] - v.co).length)
                        gid[n].add([v.index], 1.0, "REPLACE")
                mod = o.modifiers.new("rig", "ARMATURE")
                mod.object = rig
            bpy.data.objects.remove(arm, do_unlink=True)
            bpy.context.view_layer.update()
            gun_tail = rig.matrix_world @ rig.data.bones[s["gun"]].tail_local
            lo, hi = world_box(meshes)
            locs = [add_locator("barrel", rig, s["gun"], gun_tail),
                    add_locator("smoke", rig, keep[0], Vector((0, hi[1] * 0.8, (hi[2] - lo[2]) * 0.55))),
                    add_locator("exhaust", rig, keep[0], Vector((0, hi[1] * 0.8, (hi[2] - lo[2]) * 0.55)))]
            finish(name, meshes, rig, locs, anims)

        else:   # rebuild: the source rig is unusable (Source-engine export); new leg rig from its skin groups
            o = meshes[0]
            # the export stores parts out of place and lets its armature put them back: bake that deformation in
            dg = bpy.context.evaluated_depsgraph_get()
            # a brand-new mesh from plain data: whatever the source mesh carries breaks Blender's modifiers
            src = o.data
            ev = o.evaluated_get(dg).data
            clean = bpy.data.meshes.new(src.name + "_clean")
            clean.from_pydata([o.matrix_world @ v.co for v in ev.vertices], [], [list(p.vertices) for p in src.polygons])
            for m in src.materials:
                clean.materials.append(m)
            clean.polygons.foreach_set("material_index", [p.material_index for p in src.polygons])
            if src.uv_layers:
                uv = clean.uv_layers.new(name="uv0")
                uv.data.foreach_set("uv", [c for d in src.uv_layers[0].data for c in d.uv])
            new_o = bpy.data.objects.new(o.name, clean)
            bpy.context.scene.collection.objects.link(new_o)
            for g in o.vertex_groups:
                ng = new_o.vertex_groups.new(name=g.name)
            for v in src.vertices:
                for g in v.groups:
                    new_o.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
            bpy.data.objects.remove(o, do_unlink=True)
            o = new_o
            clean.update()
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = mw
            for m in list(o.modifiers):
                o.modifiers.remove(m)
            select([o], o)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            for x in [x for x in bpy.context.scene.objects if x is not o]:
                bpy.data.objects.remove(x, do_unlink=True)

            def centroid(prefixes, verts=None):
                ids = {g.index for g in o.vertex_groups if g.name.startswith(prefixes)}
                pts = [v.co.copy() for v in o.data.vertices if any(g.group in ids and g.weight > 0.5 for g in v.groups)]
                return sum(pts, Vector()) / len(pts), pts
            seat, _ = centroid(("rotator", "Lever", "button"))
            footA, _ = centroid(("legA3",))
            gun, _ = centroid(("pulsegun",))
            # orient: seat above the feet (+Z), gun ahead (-Y)
            up = (seat - footA).normalized()
            o.data.transform(up.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4())
            gun, _ = centroid(("pulsegun",))
            seat, _ = centroid(("rotator", "Lever", "button"))
            d = gun - seat
            o.data.transform(Matrix.Rotation(math.atan2(d.x, -d.y), 4, "Z"))
            co = [v.co for v in o.data.vertices]
            lo = Vector([min(c[i] for c in co) for i in range(3)])
            hi = Vector([max(c[i] for c in co) for i in range(3)])
            k = s["height"] / (hi.z - lo.z)
            o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))))
            import bmesh  # type: ignore
            bm = bmesh.new()                                # degenerate source faces make collapse decimation explode
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.002)
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
            gun_at, gun_pts = centroid(("pulsegun",))      # before the skin groups are renamed for the new rig
            gun_tip = min(gun_pts, key=lambda c: c.y)
            def joint(g1, g2):
                """centre of the vertices two skin groups share, else the top of the second group"""
                i1 = {g.index for g in o.vertex_groups if g.name.startswith(g1)}
                i2 = {g.index for g in o.vertex_groups if g.name.startswith(g2)}
                both = [v.co.copy() for v in o.data.vertices if {g.group for g in v.groups} & i1 and {g.group for g in v.groups} & i2]
                if both:
                    return sum(both, Vector()) / len(both)
                top = sorted((v.co.copy() for v in o.data.vertices if {g.group for g in v.groups} & i2), key=lambda c: -c.z)[:20]
                return sum(top, Vector()) / len(top)
            J = {}
            for L in ("A", "B"):
                J[f"hip{L}"] = joint(("root", "rotator"), (f"leg{L}1",))
                J[f"knee{L}"] = joint((f"leg{L}1",), (f"leg{L}2",))
                J[f"ankle{L}"] = joint((f"leg{L}2",), (f"leg{L}3",))
            rig_data = bpy.data.armatures.new("rig")
            rig = bpy.data.objects.new("rig", rig_data)
            bpy.context.scene.collection.objects.link(rig)
            select([rig], rig)
            bpy.ops.object.mode_set(mode="EDIT")
            root = rig_data.edit_bones.new("root")
            root.head, root.tail = Vector((0, 0, J["hipA"].z)), Vector((0, 0, J["hipA"].z + 0.5))
            for L in ("A", "B"):
                th = rig_data.edit_bones.new(f"thigh{L}"); th.head, th.tail, th.parent = J[f"hip{L}"], J[f"knee{L}"], root
                sh = rig_data.edit_bones.new(f"shin{L}"); sh.head, sh.tail, sh.parent = J[f"knee{L}"], J[f"ankle{L}"], th
                ft = rig_data.edit_bones.new(f"foot{L}"); ft.head, ft.parent = J[f"ankle{L}"], sh
                ft.tail = J[f"ankle{L}"] + Vector((0, -0.4, -0.2))
            bpy.ops.object.mode_set(mode="OBJECT")
            remap = {"legA1": "thighA", "legA2": "shinA", "legA3": "footA", "legB1": "thighB", "legB2": "shinB", "legB3": "footB"}
            new = {n: o.vertex_groups.new(name=n) for n in ("root", "thighA", "shinA", "footA", "thighB", "shinB", "footB")}
            old = {g.index: g.name for g in o.vertex_groups if g.name not in new}
            for v in o.data.vertices:
                for g in list(v.groups):
                    if g.group in old:
                        n = next((t for p, t in remap.items() if old[g.group].startswith(p)), "root")
                        new[n].add([v.index], g.weight, "ADD")
            for g in [o.vertex_groups[i] for i in sorted(old, reverse=True)]:
                o.vertex_groups.remove(g)
            mod = o.modifiers.new("rig", "ARMATURE")
            mod.object = rig
            # walk: 48-frame loop, legs half a cycle apart, a slight body bob; feet kept level
            select([rig], rig)
            bpy.ops.object.mode_set(mode="POSE")
            rig.animation_data_create()
            walk = bpy.data.actions.new("walk")
            rig.animation_data.action = walk
            rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
            rot_at = lambda p, ang: Matrix.Translation(p) @ Matrix.Rotation(ang, 4, "X") @ Matrix.Translation(-p)
            for f in range(0, 49):
                ph = 2 * math.pi * f / 48
                bob = Matrix.Translation((0, 0, 0.04 * s["height"] * math.cos(2 * ph)))
                rig.pose.bones["root"].matrix = bob @ rest["root"]
                for L, off in (("A", 0.0), ("B", math.pi)):
                    a = -math.radians(28) * math.sin(ph + off)               # forward swing = toward -Y
                    b = math.radians(30) * max(0.0, math.sin(ph + off + math.pi / 2))
                    hip, knee, ank = J[f"hip{L}"], J[f"knee{L}"], J[f"ankle{L}"]
                    m_th = bob @ rot_at(hip, a)
                    knee_n = m_th @ knee
                    m_sh = Matrix.Translation(knee_n) @ Matrix.Rotation(a + b, 4, "X") @ Matrix.Translation(-knee) @ bob.inverted() @ bob
                    ank_n = m_sh @ ank
                    m_ft = Matrix.Translation(ank_n - ank)
                    for bn, m in ((f"thigh{L}", m_th), (f"shin{L}", m_sh), (f"foot{L}", m_ft)):
                        rig.pose.bones[bn].matrix = m @ rest[bn]
                        bpy.context.view_layer.update()
                for pb in rig.pose.bones:
                    pb.keyframe_insert("location", frame=f)
                    pb.keyframe_insert("rotation_quaternion", frame=f)
            bpy.ops.object.mode_set(mode="OBJECT")
            locs = [add_locator("barrel", rig, "root", gun_tip),
                    add_locator("smoke", rig, "root", Vector((0, 0.5, J["hipA"].z)))]
            finish(name, [o], rig, locs, {"idle": ("walk", 0, 1), "move": ("walk", 0, 48), "attack": ("walk", 0, 1)})

    os.makedirs(os.path.dirname(SIDE), exist_ok=True)
    json.dump(side, open(SIDE, "w"), indent=1)


# ─────────────────────────────── textures ───────────────────────────────
def textures():
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    sys.path.insert(0, os.path.join(os.environ["LOCALAPPDATA"], "universal-modder/tools/blender-4.2.3-windows-x64/4.2/scripts/addons"))
    from io_pdx_mesh.pdx_data import read_meshfile, write_meshfile
    side = json.load(open(SIDE))
    full = lambda v: np.full((TEX_PX, TEX_PX), v, np.float32)
    for name, mats in side.items():
        for m in mats:
            base = np.asarray(Image.open(m["base"]).convert("RGB").resize((TEX_PX, TEX_PX), Image.LANCZOS)).astype(np.float32)
            save_dxt5_mips(np.dstack([base, full(255)]), f"{OUT}/{m['stem']}_diffuse.dds")
            # normal: flat (the walker mod's layout); spec: R 0, G specular, B metal, A gloss from glTF metallic-roughness
            save_dxt5_mips(np.dstack([full(132), full(130), full(0), full(128)]), f"{OUT}/{m['stem']}_normal.dds")
            if m.get("mr"):
                mr = np.asarray(Image.open(m["mr"]).convert("RGB").resize((TEX_PX, TEX_PX), Image.LANCZOS)).astype(np.float32)
                rough, metal = mr[..., 1] / 255, mr[..., 2] / 255
            else:
                rough, metal = full(0.6), full(0.4)
            save_dxt5_mips(np.dstack([full(0), 30 + 50 * metal, 60 * metal, 30 + 180 * (1 - rough)]), f"{OUT}/{m['stem']}_spec.dds")
        mesh = f"{OUT}/{name}.mesh"
        root = read_meshfile(mesh)
        for mat, m in zip(root.iter("material"), mats):
            mat.set("diff", [f"{m['stem']}_diffuse.dds"])
            mat.set("n", [f"{m['stem']}_normal.dds"])
            mat.set("spec", [f"{m['stem']}_spec.dds"])
        write_meshfile(mesh, root)
        print("textures", name, len(mats))


# ─────────────────────────────── entities ───────────────────────────────
STATES = """	state = {{ name = "idle"				animation = "idle"   animation_blend_time = 0.3 }}
	state = {{ name = "move"				animation = "move"   animation_blend_time = 0.3
		event = {{ time = 0 node="smoke" particle = "tank_exhaust_particle"  keep_particle = no trigger_once = yes }}
		event = {{ trigger_once = yes sound = {{ soundeffect = "{move_sound}" }} }}
	}}
	state = {{ name = "retreat"			animation = "move"   animation_blend_time = 0.3
		event = {{ trigger_once = yes sound = {{ soundeffect = "{move_sound}" }} }}
	}}
	state = {{ name = "attack"			animation = "attack" animation_blend_time = 0.3
		event = {{ time = 0 node="barrel" particle = "light_tank_attack_barrel_particle"  keep_particle = yes sound = {{ soundeffect = medium_armour_fire }} }}
		event = {{ time = 0 node="barrel" particle = "light_tank_attack_barrel_smoke_particle"  keep_particle = yes }}
	}}
	state = {{ name = "defend"			animation = "attack" animation_blend_time = 0.3
		event = {{ time = 0 node="barrel" particle = "light_tank_attack_barrel_particle"  keep_particle = yes sound = {{ soundeffect = medium_armour_fire }} }}
	}}
	state = {{ name = "support_attack"	animation = "attack" animation_blend_time = 0.3
		event = {{ time = 0 node="barrel" particle = "light_tank_attack_barrel_particle"  keep_particle = yes sound = {{ soundeffect = medium_armour_fire }} }}
	}}
	state = {{ name = "training"			animation = "idle"   animation_blend_time = 0.3 }}
"""
# walker battalion sprite -> (model, scale) for the Republic and for the Separatist members
# scale: the clone trooper stands ~6 units tall in game and a vanilla tank ~2 high / 4.5 long; walkers tower over both
REP_MAP = {"walker_light": ("hod_atrt", 1.1), "walker_iron_strider": ("hod_atte", 1.0), "walker_mech211": ("hod_atte", 1.1),
           "walker_sturmlaufer": ("hod_atte", 1.2), "walker_super_heavy": ("hod_atte", 1.5)}
CIS_MAP = {   # Separatist tanks (vanilla tank units, Droid Armour tab): all AATs, bigger by class
    "light_armor": ("hod_aat", 0.45), "medium_armor": ("hod_aat", 0.55), "heavy_armor": ("hod_aat", 0.65)}
CIS_TAGS = ("CIS", "TDF", "TCU", "CMG", "IBC")


def wire():
    gfx = ["objectTypes = {", "\t# HOD: Star Wars walker / tank unit models (unit_models.py)"]
    asset = ["# HOD: Star Wars walker / tank unit entities (unit_models.py). Republic: AT-RT / AT-TE; Separatists: AAT"]
    anims = ["# HOD: animations of the Star Wars unit models (unit_models.py wire)"]
    for name in SPECS:
        gfx.append(f'\tpdxmesh = {{\n\t\tname = "{name}_mesh"\n\t\tfile = "{OUT}/{name}.mesh"\n'
                   + "".join(f'\t\tanimation = {{ id = "{a}" type = "{name}_{a}_animation" }}\n' for a in ("idle", "move", "attack"))
                   + "\t}")
        # animation files resolve against their .asset's own folder: declared next to the models, like the walker mod
        anims += [f'animation = {{ name = "{name}_{a}_animation" file = "{name}_{a}.anim" }}' for a in ("idle", "move", "attack")]
        sound = "tank_engine_light_move" if name == "hod_aat" else "tank_engine_medium_move"
        asset.append(f'entity = {{\n\tname = "{name}_entity"\n\tpdxmesh = "{name}_mesh"\n' + STATES.format(move_sound=sound) + "\tscale = 1.0\n}")
    for tags, table in ((("REP",), REP_MAP), (CIS_TAGS, CIS_MAP)):
        for tag in tags:
            for sprite, (model, scale) in table.items():
                asset.append(f'entity = {{ name = "{tag}_{sprite}_entity" clone = "{model}_entity" scale = {scale} }}')
    open("gfx/entities/hod_sw_walkers.gfx", "w", encoding="utf-8", newline="\n").write("\n".join(gfx + ["}", ""]))
    open("gfx/entities/hod_sw_walkers.asset", "w", encoding="utf-8", newline="\n").write("\n".join(asset) + "\n")
    open(f"{OUT}/hod_walkers_anims.asset", "w", encoding="utf-8", newline="\n").write("\n".join(anims) + "\n")
    print("wired", len(asset), "entries")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"convert": convert, "textures": textures, "wire": wire}[args[0]](*args[1:])
