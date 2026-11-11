"""Blender 4.2: Empire at War (Alamo) .alo models -> static .glb with their diffuse textures (Republic at War assets).

  blender -b --factory-startup --python "plans & scripts/alo_to_glb.py" -- OUT_DIR file.alo [file.alo ...]
  ... -- OUT_DIR main.alo+Bone=part.alo+Bone2=part2.alo   static, hardpoint parts (turrets, guns) placed on main's bones
  ... -- --anim OUT_DIR file.alo ...   rigged: armature + every <name>_*.ala as an action (unit_models.py "bake" mode);
                                       bone-attached rigid parts become one-bone skins

Uses the ALAMO importer (github.com/Gaukler/Blender-ALAMO-Plugin, patched for Blender 4.2, in
ProjectKessilianWIPGFX/tools_ext). Keeps visible geometry only (no collision, shadow volumes, lower LODs, muzzle flashes,
light / glow cards), bakes bone-attached parts into world space, one Principled material per part with its diffuse
texture. Output: OUT_DIR/<alo stem>.glb.
Republic at War credit lines (credits.txt) must be copied EXACTLY into our credits for every model used.
"""
import os, re, sys
import bpy  # type: ignore

PLUGIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../ProjectKessilianWIPGFX/tools_ext/Blender-ALAMO-Plugin")
sys.path.insert(0, os.path.abspath(PLUGIN))
import io_alamo_tools  # noqa: E402
io_alamo_tools.register()
IMPORT = getattr(bpy.ops, "import")          # operator id is "import.alo"

SKIP = re.compile(r"collision|shadow|shields up|muzzle|flash|light|glow|engine|_lod[1-9]|^p_|^c_|hp_|proxy|goblin|bone|girder|_alt[1-9]", re.I)   # girder = build-up scaffold, _ALTn = damage states
AUX = re.compile(r"(_?b|_?g|_?gloss|_?spec|_?normal|_?n|_?bump\w*|td|tb|glow|black|_bc(_d\d)?|[-_][ln]m)$", re.I)   # not the diffuse map (_BC = EaW structure normal map)


def diffuse(mat):
    if not mat or not mat.use_nodes:
        return None
    ims = [n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and n.image.size[0]]
    main = [i for i in ims if not AUX.search(os.path.splitext(i.name)[0])]
    return (main or ims or [None])[0]


LIFTED = set()
LIGHT_ONLY = re.compile(r"[-_]lm(\.dds)?$|blast|thruster_on", re.I)   # FotR light-map / engine-glow cards drew as black slabs


REP_COLOUR = (0.62, 0.13, 0.10)     # EaW paints the faction colour into the alpha mask: Republic red
TEAM_COLOUR = {"rep": REP_COLOUR, "cis": (0.23, 0.36, 0.66)}   # HOD_TEAM=cis: Separatist blue (as the CIS TIE droid repaint)
CAMO = re.compile(r"arf", re.I)       # ARF scout troopers wear green camo: Republic clone white instead


def lift(img, target=0.45):
    """EaW's shader brightens its mid-grey diffuse maps; HOI4 shows them nearly black: scale the painted pixels (not the
    empty black of the atlas, which made sparse sheets like the AT-RT blow out to white) up to a mid grey"""
    if img.name in LIFTED:
        return
    LIFTED.add(img.name)
    import numpy as np
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    rgb = px[:, :3]
    painted = rgb.max(1) > 0.04
    mean = rgb[painted].mean() if painted.any() else 0
    if 0.02 < mean < target:
        rgb *= target / mean
    team = px[:, 3] > 0.5
    colour = TEAM_COLOUR.get(os.environ.get("HOD_TEAM")) or (REP_COLOUR if re.match(r"re", img.name, re.I) else None)
    if colour and painted.any() and team[painted].mean() < 0.3:   # small mask = team colour, big = gloss
        lum = rgb[team].mean(1, keepdims=True)
        rgb[team] = lum * np.array(colour) * 1.8
    if CAMO.search(img.name):
        lum = rgb.mean(1, keepdims=True)
        rgb[:] = 0.3 + 0.7 * lum / max(lum.max(), 1e-3)
    px[:, :3] = np.clip(rgb, 0, 1)
    px[:, 3] = 1.0                      # alpha is EaW's colorize / gloss mask, not transparency
    img.pixels.foreach_set(px.ravel())
    img.update()


def simple_material(o):
    img = diffuse(o.material_slots[0].material if o.material_slots else None)
    if img:
        lift(img)
    key = "hodmat_" + (img.name if img else "plain")       # one material per texture, not per part
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    if img:
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = img
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def rest_world(o):
    """Alamo stores a part's vertices relative to its bone: world = armature @ bone rest @ part (the plugin's CHILD_OF
    inverse cancels the bone and drops every part on the origin)"""
    c = next((c for c in o.constraints if c.type == "CHILD_OF" and c.target and c.subtarget), None)
    if not c:
        return o.matrix_world.copy(), None
    return c.target.matrix_world @ c.target.data.bones[c.subtarget].matrix_local @ o.matrix_basis, c.subtarget


def rig_parts(keep, arm):
    """rest pose: rigid CHILD_OF parts baked into place and skinned 100 % to their bone; skinned parts keep their groups"""
    for o in keep:
        mw, bone = rest_world(o)
        for c in list(o.constraints):
            o.constraints.remove(c)
        o.parent = None
        o.data.transform(mw)
        o.matrix_world = arm.matrix_world.inverted() @ arm.matrix_world   # identity
        skinned = any(v.groups for v in o.data.vertices)
        if bone and not skinned:     # rigid part (the plugin may still have added an empty armature modifier)
            (o.vertex_groups.get(bone) or o.vertex_groups.new(name=bone)).add(range(len(o.data.vertices)), 1.0, "REPLACE")
        if not any(m.type == "ARMATURE" for m in o.modifiers):
            m = o.modifiers.new("rig", "ARMATURE"); m.object = arm
        o.parent = arm


def convert(path, out_dir, anim=False):
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images,
                 bpy.data.collections, bpy.data.actions):
        LIFTED.clear() if coll is bpy.data.images else None
        for x in list(coll):    # not read_factory_settings: the plugin's scene properties must stay registered
            coll.remove(x)
    path, *parts = path.split("+")
    IMPORT.alo(filepath=os.path.abspath(path).replace("/", "\\"), importAnimations=anim)
    old = list(bpy.data.objects)
    if parts:
        main_arm = next(o for o in old if o.type == "ARMATURE")
        print("ALO bones", [b.name for b in main_arm.data.bones])
    visible = [o for o in old if o.type == "MESH" and not o.hide_get() and not SKIP.search(o.name) and len(o.data.polygons)
               and not LIGHT_ONLY.search(getattr(diffuse(o.material_slots[0].material if o.material_slots else None), "name", ""))]
    # per LOD group with a hidden LOD0 (inverted numbering: TR AT-AA, FotR UV_MAL), keep its highest visible LOD;
    # ALT1+ are damage states of ALT0
    groups = {}
    for o in old:
        m = re.search(r"_lod(\d)$", o.name, re.I)
        if o.type == "MESH" and m and len(o.data.polygons) and not re.search(r"_alt[1-9]", o.name, re.I):
            groups.setdefault(o.name[:m.start()], []).append((int(m.group(1)), o))
    for lods in groups.values():
        if not any(n == 0 and not o.hide_get() for n, o in lods):
            shown = [(n, o) for n, o in lods if not o.hide_get()]
            if shown and max(shown, key=lambda t: t[0])[1] not in visible:
                visible.append(max(shown, key=lambda t: t[0])[1])
    if not visible:    # some mods number LODs the other way round (LOD2 = full detail): keep the highest visible LOD
        lods = [o for o in old if o.type == "MESH" and not o.hide_get() and len(o.data.polygons)
                and re.search(r"_lod(\d)", o.name, re.I) and not SKIP.search(re.sub(r"_lod\d", "", o.name, flags=re.I))]
        top = max((int(re.search(r"_lod(\d)", o.name, re.I).group(1)) for o in lods), default=None)
        visible = [o for o in lods if int(re.search(r"_lod(\d)", o.name, re.I).group(1)) == top]
    if anim:
        arm = next(o for o in old if o.type == "ARMATURE")
        for o in old:
            if o not in visible and o is not arm:
                bpy.data.objects.remove(o)
        keep = visible
        for o in keep:
            mat = simple_material(o)
            o.data.materials.clear(); o.data.materials.append(mat)
        rig_parts(keep, arm)
        for spec in parts:                  # Bone=part.alo on a rigged model: the part rides that bone (100 % skin)
            bone, part = spec.split("=", 1)
            bm = arm.matrix_world @ arm.data.bones[bone].matrix_local   # copy now: the part's import invalidates Bone refs
            before = set(bpy.data.objects)
            IMPORT.alo(filepath=os.path.abspath(part).replace("/", "\\"), importAnimations=False)
            new = [o for o in bpy.data.objects if o not in before]
            dg = bpy.context.evaluated_depsgraph_get()
            for o in new:
                if o.type == "MESH" and not o.hide_get() and not SKIP.search(o.name) and len(o.data.polygons):
                    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
                    me.transform(bm @ rest_world(o)[0])
                    mat = simple_material(o); me.materials.clear(); me.materials.append(mat)
                    ob = bpy.data.objects.new(o.name + "_" + bone, me); bpy.context.scene.collection.objects.link(ob)
                    ob.vertex_groups.new(name=bone).add(range(len(me.vertices)), 1.0, "REPLACE")
                    m = ob.modifiers.new("rig", "ARMATURE"); m.object = arm; ob.parent = arm
                    keep.append(ob)
            for o in new:
                bpy.data.objects.remove(o)
        for a in bpy.data.actions:
            a.use_fake_user = True
        arm.animation_data.action = None
    else:
        dg = bpy.context.evaluated_depsgraph_get()
        keep = []
        for o in visible:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))   # armature deformation applied
            me.transform(rest_world(o)[0])                                # bone-attached parts into place
            mat = simple_material(o)
            me.materials.clear()
            me.materials.append(mat)
            keep.append(bpy.data.objects.new(o.name + "_baked", me))
        hp = {b.name.lower(): main_arm.matrix_world @ b.matrix_local for b in main_arm.data.bones} if parts else {}
        for o in old:
            bpy.data.objects.remove(o)
        for spec in parts:                  # Bone=part.alo: the part's visible geometry moved onto the main model's bone
            bone, part = spec.split("=", 1)
            before = set(bpy.data.objects)
            IMPORT.alo(filepath=os.path.abspath(part).replace("/", "\\"), importAnimations=False)
            new = [o for o in bpy.data.objects if o not in before]
            dg = bpy.context.evaluated_depsgraph_get()
            for o in new:
                if o.type == "MESH" and not o.hide_get() and not SKIP.search(o.name) and len(o.data.polygons):
                    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
                    me.transform(hp[bone.lower()] @ rest_world(o)[0])
                    mat = simple_material(o); me.materials.clear(); me.materials.append(mat)
                    keep.append(bpy.data.objects.new(o.name + "_baked", me))
            for o in new:
                bpy.data.objects.remove(o)
        for o in keep:
            bpy.context.scene.collection.objects.link(o)
    if not keep:
        print("ALO", os.path.basename(path), "no visible geometry"); return
    for im in bpy.data.images:                  # dds sources: pack so the glb carries them as png (keeps the lifted pixels)
        if im.size[0] and (im.is_dirty or not im.packed_file):
            im.pack()
    out = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0].lower() + ".glb")
    kw = dict(export_animation_mode="ACTIONS", export_skins=True) if anim else {}
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(out), export_format="GLB", export_image_format="AUTO", **kw)
    print("ALO", os.path.basename(path), len(keep), "parts", sum(len(o.data.polygons) for o in keep),
          "actions", [a.name for a in bpy.data.actions] if anim else "", "->", out)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    anim = a[0] == "--anim"
    a = a[1:] if anim else a
    os.makedirs(a[0], exist_ok=True)
    for p in a[1:]:
        try:
            convert(p, a[0], anim)
        except Exception as e:      # one bad model must not stop the batch
            import traceback; traceback.print_exc(); print("ALO FAIL", os.path.basename(p), repr(e)[:300])
