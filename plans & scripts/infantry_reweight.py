"""Fix infantry skinning: copy skin weights from the vanilla GER_infantry body onto a trooper mesh (same 33-bone skeleton).
    blender(5.2) -b --factory-startup --python "plans & scripts/infantry_reweight.py" -- <vanilla GER_infantry.mesh> OUTDIR a.mesh [b.mesh ...]
Used 2026-11-07 on REP_infantry / _p2 / _empire / REP_old_trooper (their own weights tore legs and feet in the vanilla anims)."""
import bpy, sys, os
sys.path.insert(0, bpy.utils.user_resource("EXTENSIONS", path="user_default"))
from io_pdx_mesh.pdx_blender import blender_import_export as bie
a = sys.argv[sys.argv.index("--") + 1:]
ref_path, out_dir, meshes = a[0], a[1], a[2:]
os.makedirs(out_dir, exist_ok=True)
def sel(objs, active):
    for o in bpy.data.objects: o.select_set(o in objs)
    bpy.context.view_layer.objects.active = active
for mp in meshes:
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.armatures, bpy.data.materials):
        for o in list(coll): coll.remove(o)
    bie.import_meshfile(os.path.abspath(ref_path), imp_mesh=True, imp_skel=True, imp_locs=False)
    ref = [o for o in bpy.data.objects if o.type == "MESH" and len(o.vertex_groups) > 0]
    sel(ref, ref[0])
    if len(ref) > 1: bpy.ops.object.join()
    src = bpy.context.view_layer.objects.active
    src.parent = None
    for m in list(src.modifiers): src.modifiers.remove(m)
    for o in list(bpy.data.objects):          # the importer would reuse this rig for the trooper
        if o is not src: bpy.data.objects.remove(o, do_unlink=True)
    for arm in list(bpy.data.armatures): bpy.data.armatures.remove(arm)
    src.name = "zz_weight_src"
    for m in src.data.materials: m.name = "zz_src_mat"
    bie.import_meshfile(os.path.abspath(mp), imp_mesh=True, imp_skel=True, imp_locs=True)
    targets = [o for o in bpy.data.objects if o.type == "MESH" and o is not src]
    for t in targets:
        for g in list(t.vertex_groups): t.vertex_groups.remove(g)
        for g in src.vertex_groups: t.vertex_groups.new(name=g.name)
        m = t.modifiers.new("dt", "DATA_TRANSFER")
        m.object = src; m.use_vert_data = True; m.data_types_verts = {"VGROUP_WEIGHTS"}
        m.vert_mapping = "POLYINTERP_NEAREST"; m.layers_vgroup_select_src = "ALL"; m.layers_vgroup_select_dst = "NAME"
        sel([t], t)
        bpy.ops.object.modifier_move_to_index(modifier="dt", index=0)
        bpy.ops.object.modifier_apply(modifier="dt")
        bpy.ops.object.vertex_group_limit_total(limit=4)
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    bpy.data.objects.remove(src, do_unlink=True)
    print("DBG", [(t.name, len(t.vertex_groups), [(m.type, m.object and m.object.name) for m in t.modifiers]) for t in targets])
    sel(list(bpy.data.objects), targets[0])
    bie.export_meshfile(os.path.join(os.path.abspath(out_dir), os.path.basename(mp)), exp_mesh=True, exp_skel=True, exp_locs=True)
    print("REWEIGHTED", mp)
