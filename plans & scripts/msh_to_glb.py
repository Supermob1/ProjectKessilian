"""Blender: Star Wars Battlefront II / Empire at War (ZeroEngine) static .msh models -> .glb with their textures, so
sketchfab_props.py can decimate and bake them like any glTF (Raxus Prime wrecks, debris, EaW buildings).

  blender -b --factory-startup --python "WIPGFX/plans & scripts/msh_to_glb.py" -- OUT_DIR file.msh [file.msh ...]

Each model's visible geometry (collision, shadow volumes, low-res and hidden parts dropped) in world space, Y up ->
Z up; one Principled material per .msh material with its first texture (found next to the .msh or anywhere in the
asset's folder). Output: OUT_DIR/<msh stem>.glb.
"""
import glob, os, sys
import bpy  # type: ignore
from mathutils import Matrix, Quaternion, Vector  # type: ignore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swbf_msh  # noqa: E402

SKIP_START = ("p_", "c_", "sv_", "hp_")                           # hardpoints, collision primitives, shadow volumes
SKIP_IN = ("collision", "shadowvolume", "lowrez", "lowres", "_low1", "_lod")


def world_of(models):
    by = {m["name"]: m for m in models}
    cache = {}

    def mat(name):
        if name in cache:
            return cache[name]
        m = by.get(name)
        if m is None or not m["tran"]:
            out = Matrix.Identity(4)
        else:
            t = m["tran"]
            x, y, z, w = t["rot"]
            local = (Matrix.Translation(t["pos"]) @ Quaternion((w, x, y, z)).to_matrix().to_4x4() @
                     Matrix.Diagonal((*t["scale"], 1.0)))
            out = (mat(m["parent"]) if m["parent"] else Matrix.Identity(4)) @ local
        cache[name] = out
        return out
    return mat


def texture(path, name):
    if not name:
        return None
    root = os.path.dirname(path)
    for d in (root, os.path.dirname(root)):
        hits = [h for h in glob.glob(os.path.join(d, "**", "*"), recursive=True) if os.path.basename(h).lower() == name.lower()]
        if hits:
            return hits[0]
    return None


def convert(path, out_dir):
    path = os.path.abspath(path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    d = swbf_msh.read(path)
    mats = []
    for name, texs in d["materials"]:
        m = bpy.data.materials.new(name or "mat")
        m.use_nodes = True
        tex = texture(path, texs[0] if texs else "")
        if tex:
            node = m.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = bpy.data.images.load(tex)
            m.node_tree.links.new(node.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        mats.append(m)
    world = world_of(d["models"])
    yup = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # (x, y, z) -> (x, -z, y)
    count = 0
    for mdl in d["models"]:
        low = mdl["name"].lower()
        if mdl["hidden"] or not mdl["segments"] or low.startswith(SKIP_START) or any(w in low for w in SKIP_IN):
            continue
        M = yup @ world(mdl["name"])
        for k, seg in enumerate(mdl["segments"]):
            if not seg["tris"] or not seg["pos"]:
                continue
            me = bpy.data.meshes.new(f"{mdl['name']}_{k}")
            me.from_pydata([tuple(M @ Vector(p)) for p in seg["pos"]], [], [t for t in seg["tris"]])
            if seg["uv"]:
                uv = me.uv_layers.new(name="UVMap")
                for poly in me.polygons:
                    for li in poly.loop_indices:
                        uv.data[li].uv = seg["uv"][me.loops[li].vertex_index]
            if 0 <= seg["mat"] < len(mats):
                me.materials.append(mats[seg["mat"]])
            me.validate()
            obj = bpy.data.objects.new(me.name, me)
            bpy.context.scene.collection.objects.link(obj)
            count += 1
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + ".glb")
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(out), export_format="GLB")
    print(f"{os.path.basename(path)}: {count} parts -> {out}")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    for p in args[1:]:
        try:
            convert(p, args[0])
        except Exception as e:                       # one broken file must not stop the batch
            print(f"FAILED {p}: {e}")
