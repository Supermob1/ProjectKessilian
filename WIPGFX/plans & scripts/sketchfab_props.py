"""Sketchfab (CC Attribution) Star Wars models -> HOI4 map props and supply-train cars.
Each model is decimated to a budget and its many materials are baked (Cycles, diffuse colour) onto one texture
on fresh UVs: the tree renderer draws only a mesh's first material.

  blender -b --factory-startup --python "WIPGFX/plans & scripts/sketchfab_props.py" -- bake [name ...]
  python "WIPGFX/plans & scripts/sketchfab_props.py" textures     baked PNGs -> DDS
  python "WIPGFX/plans & scripts/sketchfab_props.py" wire         trains: gfx/entities/hod_trains.{gfx,asset} +
                                                                   gfx/train_gfx_database/generic.txt
Props are written as gfx/models/mapitems/hod_flora/hod_flora_<index>_<name>.mesh and registered by
flora_props.py wire (EXTERNAL). Sources: WIPGFX/3d/sketchfab/<folder>/scene.gltf (+ license.txt).

CREDITS (CC BY 4.0, author must be credited):
  Harrower Sith Ship - Cpt.Kirk                    https://sketchfab.com/CaptainJamesKirk
  Star Wars: Foray-class Blockade Runner - Daniel  https://sketchfab.com/DanielAndersson
  Star Wars Galaxies - XJ-6 Airspeeder - Zorg_Sinister  https://sketchfab.com/4130ff15fe394c239cc064b5286c43
  Star Wars Moisture Vaporator - gazthing          https://sketchfab.com/gazthing
  Star Wars Sandcrawler (exterior) - tegnemaskin   https://sketchfab.com/tegnemaskin
  Star Wars: X-34 Landspeeder - fccooper           https://sketchfab.com/fccooper
  Venator-class Star Destroyer (WIPGFX/3d/venator-class-star-destroyer, supplied by the user 2026-10-22) - author and
    licence still to fill in before release
"""
import json, os, sys

SRC = "WIPGFX/3d/sketchfab"
BAKED = "WIPGFX/3d/sketchfab/_baked"
OUT = "gfx/models/mapitems/hod_flora"
BAKE_PX = 1024          # bake resolution (downsampled to 512 for the game)
# speeder paint jobs: hue rotation (degrees) of the painted (saturated) parts, None = grey; metal stays as baked
PAINT = {"a": 0, "b": 200, "c": 120, "d": None, "e": 330, "f": 45}
# name: source folder, kind (prop = trees.bmp object / train = supply-train car), trees.bmp index or None,
#       triangle budget, largest extent in map units, yaw (deg, Blender Z) so the nose points to -Y
SPECS = {
    # sandcrawler (prop 53) is procedural now: military_buildings.py models -> hod_flora_53_sandcrawler
    "vaporators": dict(src="star_wars_moisture_vaporator", kind="prop", index=54, budget=300, size=1.1, copies=3),
    "wreck_harrower": dict(src="harrower_sith_ship", kind="prop", index=56, budget=1500, size=5.0, wreck=True, remesh=7),
    "wreck_foray": dict(src="star_wars_foray-class_blockade_runner", kind="prop", index=57, budget=1500, size=4.5,
                        wreck=True, remesh=7),
    "xj6": dict(src="star_wars_galaxies_-_xj-6_airspeeder", kind="train", budget=1200, size=1.6, yaw=0),
    "x34": dict(src="star_wars_x-34_landspeeder", kind="train", budget=1200, size=1.1, yaw=0),
    # buildings (city meshes / building entities): Advanced texture layout, lit windows -> night emission
    "jasperio": dict(src="Nouveau dossier/jasperio_village_-_cmgt_3d_modelling_-_treehouse", kind="building",
                     budget=3000, size=1.6),
    "jedi_temple": dict(src="Nouveau dossier/jedi_temple", kind="building", budget=4000, size=4.0),
    "shield_gen": dict(src="Nouveau dossier/star_wars_shield_generator", kind="building", budget=2500, size=1.4,
                       ao=(150, 152, 156),       # untextured: grey metal x baked ambient occlusion
                       crop_x=(0.0, 0.215)),      # the file is a row of six copies: keep the first
}
# Christophsis towers cut out of the battleground level by christophsis_extract.py (picked from its contact sheet)
for _k in (0, 1, 2, 3, 4, 7):
    SPECS[f"chr_{_k:02d}"] = dict(path=f"WIPGFX/3d/sketchfab/christophsis_buildings/site_{_k:02d}.glb", kind="building",
                                  budget=1500, size=1.8, double=_k in (0, 2, 3),   # single-sided panel towers
                                  lift=(110, (175, 215, 222)))   # level is lit at night: daylight crystal-teal glass
# Raxus Prime, the junk world: Battlefront II / Empire at War models converted by msh_to_glb.py (WIPGFX/3d/Raxus
# Prime, WIPGFX/3d/SWEAW_prop_conversions). Split ships half buried as landmarks (raxus_prime_map.py places them),
# small wrecks and junk as map props (trees.bmp), junk stacks as scrap-town buildings (city style 12).
_RP, _EAW = "WIPGFX/3d/_glb/raxus_prime", "WIPGFX/3d/_glb/eaw"
SPECS.update({
    # landmarks (ambient objects): broken capital ships, tilt (rad about y, x) and how deep they are buried
    "rp_derriphan_bow": dict(path=f"{_RP}/derriphan_chunk1.glb", kind="building", budget=2500, size=7.0, wreck="rust",
                             tilt=(0.35, 0.1), bury=0.12),
    "rp_derriphan_stern": dict(path=f"{_RP}/derriphan_chunk2.glb", kind="building", budget=2500, size=5.5, wreck="rust",
                               tilt=(-0.25, 0.3), bury=0.15),
    "rp_hammerhead_bow": dict(path=f"{_RP}/hammerhead_chunk1.glb", kind="building", budget=2000, size=4.5, wreck="rust",
                              tilt=(0.5, 0.2), bury=0.2),
    "rp_hammerhead_stern": dict(path=f"{_RP}/hammerhead_chunk2.glb", kind="building", budget=2000, size=5.0, wreck="rust",
                                tilt=(-0.2, -0.15), bury=0.1),
    "rp_lethisk": dict(path=f"{_RP}/orp_fly_lethisk.glb", kind="building", budget=1800, size=3.2, wreck="rust",
                       tilt=(0.25, -0.2), bury=0.08),
    "rp_factory": dict(path=f"{_EAW}/eaw_abandonedFactory.glb", kind="building", budget=4000, size=7.5),
    "rp_droidworks": dict(path=f"{_EAW}/eaw_droidworks.glb", kind="building", budget=2500, size=3.5),
    # map props (trees.bmp index): crashed fighters, the Ebon Hawk, hull chunks, junk heaps, barrel stacks
    "rp_wreck_bloodmark": dict(path=f"{_RP}/sth_fly_bloodmark.glb", kind="prop", index=65, budget=800, size=1.5, wreck="rust"),
    "rp_wreck_chela": dict(path=f"{_RP}/orp_fly_chela.glb", kind="prop", index=66, budget=700, size=1.4, wreck="rust",
                           tilt=(1.2, 0.2), bury=0.15),
    "rp_wreck_b28": dict(path=f"{_RP}/sth_fly_b28bomber.glb", kind="prop", index=67, budget=900, size=1.7, wreck="rust"),
    "rp_wreck_ebonhawk": dict(path=f"{_RP}/ebon_hawk.glb", kind="prop", index=68, budget=1200, size=2.2, wreck="rust"),
    "rp_junk_heap": dict(path=f"{_EAW}/eaw_crates10.glb", kind="prop", index=69, budget=700, size=1.8),
    "rp_barrels": dict(path=f"{_EAW}/eaw_crates3.glb", kind="prop", index=70, budget=600, size=1.0),
    "rp_hull_chunk": dict(path=f"{_RP}/lethisk_chunk2.glb", kind="prop", index=71, budget=600, size=1.6, wreck="rust",
                          tilt=(0.6, 0.4), bury=0.2),
    "rp_wing_chunk": dict(path=f"{_RP}/chela_chunk1.glb", kind="prop", index=72, budget=400, size=1.0, wreck="rust"),
    # scrap-town buildings (city style 12): container stacks, crate blocks, a junk tower
    **{f"rpt_{n}": dict(path=f"{_EAW}/eaw_{n}.glb", kind="building", budget=600, size=sz)
       for n, sz in (("crates4", 1.4), ("crates5", 1.2), ("crates6", 1.3), ("crates9", 1.4), ("crates1", 1.0),
                     ("huttTower", 1.3), ("fuelCellC", 1.4))},
})
# vanilla building replacements (military_buildings.py EAW_BUILDINGS): Empire at War buildings, largest extent in map
# units at entity scale 1 (vanilla factories stand ~2 across)
SPECS.update({f"eaw_{n}": dict(path=f"{_EAW}/eaw_{n}.glb", kind="building", budget=budget, size=size)
              for n, size, budget in (("vehicleFactory", 2.4, 2000), ("lightfactory", 2.2, 2000), ("rebelBarracks", 2.4, 1800),
                                      ("emplacement", 1.8, 1200), ("prison", 2.6, 2000), ("tibannaStation", 1.6, 1200),
                                      ("fuelCellC", 2.0, 1200), ("corBuild4", 2.4, 1200), ("corBuild3", 2.4, 1200),
                                      ("researchAcademy", 2.0, 1800), ("crates9", 1.2, 600), ("crates4", 1.2, 400),
                                      ("officerAcademy", 2.0, 1800), ("infantrybarracks", 2.2, 1800),
                                      ("rebelBuilding1", 2.2, 1800), ("bespinBuilding3", 2.0, 1500), ("droidworks", 2.2, 2000))})
BUILDING_OUT = "gfx/models/buildings/hod_sw"
# Bonadan's orbital shipyard (military_buildings.py bon_shipyard): the Old Republic ships of the Battlefront II /
# Empire at War conversions, clean (not wrecked), as parts of the shipyard mesh: written next to it (hod_landmarks)
# so its materials find their textures. size = length in map units
_LM = "gfx/models/buildings/hod_landmarks"
SPECS.update({
    "bon_derriphan": dict(path=f"{_RP}/sth_fly_derriphan.glb", kind="building", budget=2200, size=10.5, out=_LM,
                          lift=(125, (172, 170, 164))),   # Sith-dark grey hull: lifted to the yard's light grey
    "bon_hammerhead": dict(path=f"{_RP}/orp_fly_hammerhead.glb", kind="building", budget=1600, size=8.5, out=_LM),
    "bon_foray": dict(src="star_wars_foray-class_blockade_runner", kind="building", budget=1400, size=6.5, remesh=6,
                      out=_LM),
    "bon_lethisk": dict(path=f"{_RP}/orp_fly_lethisk.glb", kind="building", budget=700, size=2.6, out=_LM),
    "bon_chela": dict(path=f"{_RP}/orp_fly_chela.glb", kind="building", budget=300, size=1.1, out=_LM),
})
# Pammant's orbital docks (military_buildings.py pam_docks): the user's Separatist ship models (STL, untextured: an AO
# bake tinted with the hull paint). Malevolence 4.8 km vs Providence 1 km, shown 34 vs 14 map units
_SEP = "WIPGFX/separatists ships 3d"
SPECS.update({
    "pam_malevolence": dict(path=f"{_SEP}/Malevolence.stl", kind="building", budget=7000, size=34.0, out=_LM,
                            ao=(196, 198, 202)),   # pale grey hull
    "pam_invisible_hand": dict(path=f"{_SEP}/Invisible_Hand.stl", kind="building", budget=6400, size=14.0, out=_LM,
                               ao=(198, 182, 150)),   # Separatist tan-grey hull
})
# the orbital yards' Venators (arch_kit ALN_YARD_FLEET, FON_YARD_FLEET): the user's Venator-class model (FBX + PBR textures), 1.1 km
# long, shown 10 map units
SPECS.update({
    "aln_venator": dict(path="WIPGFX/3d/venator-class-star-destroyer/source/Venator.fbx", kind="building", budget=6000,
                        size=10.0, out=_LM),
})


def mesh_name(name):
    s = SPECS[name]
    return {"prop": f"hod_flora_{s.get('index')}_{name}", "train": f"hod_train_{name}", "building": f"hod_bld_{name}"}[s["kind"]]


def out_of(name):
    return SPECS[name].get("out") or (BUILDING_OUT if SPECS[name]["kind"] == "building" else OUT)


def bake(*only):
    import math
    import random
    import bpy  # type: ignore
    from mathutils import Matrix, Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    os.makedirs(BAKED, exist_ok=True)
    rng = random.Random(9)

    class Mat:
        def __init__(self, tex, shader, train):
            self.shader = [shader]
            self.diff = [f"{tex}_diffuse.dds"]
            self.n = [f"{tex}_normal.dds"]
            self.spec = [f"{tex}_properties.dds" if train else "hod_flora_spec.dds"]

    for name, s in SPECS.items():
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        src_path = os.path.abspath(s.get("path") or f"{SRC}/{s['src']}/scene.gltf")
        if src_path.lower().endswith(".stl"):
            bpy.ops.wm.stl_import(filepath=src_path)
        elif src_path.lower().endswith(".fbx"):
            bpy.ops.import_scene.fbx(filepath=src_path)
            tex_dir = os.path.join(os.path.dirname(os.path.dirname(src_path)), "textures")   # <model>/source/x.fbx + <model>/textures
            key = lambda f: os.path.splitext(f)[0].replace("_", "").replace(" ", "").lower()
            have = {key(f): os.path.join(tex_dir, f) for f in (os.listdir(tex_dir) if os.path.isdir(tex_dir) else [])}
            for im in bpy.data.images:          # textures the FBX points elsewhere: by file name, "_"/case-blind (BaseColor = Base_Color)
                cand = have.get(key(os.path.basename(im.filepath.replace("\\", "/"))))
                if im.source == "FILE" and not os.path.exists(bpy.path.abspath(im.filepath)) and cand:
                    im.filepath = cand
                    im.reload()
        else:
            bpy.ops.import_scene.gltf(filepath=src_path)
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        for o in bpy.context.scene.objects:
            o.select_set(o in meshes)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for o in [o for o in bpy.context.scene.objects if o.type != "MESH"]:
            bpy.data.objects.remove(o, do_unlink=True)
        if len(meshes) > 1:
            bpy.ops.object.join()
        hi = bpy.context.view_layer.objects.active
        if s.get("crop_x"):                          # keep faces whose centre lies in this slice of the x range
            import bmesh  # type: ignore
            xs = [v.co.x for v in hi.data.vertices]
            x0, x1 = min(xs) + (max(xs) - min(xs)) * s["crop_x"][0], min(xs) + (max(xs) - min(xs)) * s["crop_x"][1]
            bm3 = bmesh.new()
            bm3.from_mesh(hi.data)
            bmesh.ops.delete(bm3, geom=[f for f in bm3.faces if not x0 <= f.calc_center_median().x <= x1], context="FACES")
            bmesh.ops.delete(bm3, geom=[v for v in bm3.verts if not v.link_faces], context="VERTS")   # orphans skew the size
            bm3.to_mesh(hi.data)
            bm3.free()
        # normalise: yaw, largest extent = size, centred, base on z = 0
        hi.data.transform(Matrix.Rotation(math.radians(s.get("yaw", 0)), 4, "Z"))
        co = [v.co for v in hi.data.vertices]
        lo_ = Vector([min(c[i] for c in co) for i in range(3)])
        hi_ = Vector([max(c[i] for c in co) for i in range(3)])
        k = s["size"] / max(hi_ - lo_)
        centre = Vector(((lo_.x + hi_.x) / 2, (lo_.y + hi_.y) / 2, lo_.z))
        hi.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation(-centre))
        if s["kind"] == "train":     # train cars: back at y = 0, nose toward -y (PDX -Z forward)
            ymax = max(v.co.y for v in hi.data.vertices)
            hi.data.transform(Matrix.Translation((0, -ymax, 0)))
        # diffuse-colour bake must see the base colour: metal bakes black, glass bakes empty
        for m in hi.data.materials:
            if m and m.use_nodes:
                for n in m.node_tree.nodes:
                    if n.type == "BSDF_PRINCIPLED":
                        for inp, val in (("Metallic", 0.0), ("Transmission Weight", 0.0), ("Alpha", 1.0)):
                            if inp in n.inputs:
                                for l in list(n.inputs[inp].links):
                                    m.node_tree.links.remove(l)
                                n.inputs[inp].default_value = val
        # low-poly copy with its own UVs
        lo = hi.copy()
        lo.data = hi.data.copy()
        bpy.context.scene.collection.objects.link(lo)
        bpy.context.view_layer.objects.active = lo
        for o in bpy.context.scene.objects:
            o.select_set(o is lo)
        tris = sum(len(p.vertices) - 2 for p in lo.data.polygons)
        if s.get("remesh"):
            # big hard-surface models (hundreds of thousands of loose greebles): one clean shell first (octree
            # remesh, tiny disconnected bits dropped), so the decimation below has a sane surface to work on
            m = lo.modifiers.new("remesh", "REMESH")
            m.mode = "SHARP"
            m.octree_depth = s["remesh"]
            m.scale = 0.95
            m.use_remove_disconnected = True
            m.threshold = 0.2
            bpy.ops.object.modifier_apply(modifier=m.name)
        if sum(len(p.vertices) - 2 for p in lo.data.polygons) > s["budget"]:
            m = lo.modifiers.new("dec", "DECIMATE")
            m.ratio = s["budget"] / sum(len(p.vertices) - 2 for p in lo.data.polygons)
            bpy.ops.object.modifier_apply(modifier=m.name)
        m = lo.modifiers.new("tri", "TRIANGULATE")
        bpy.ops.object.modifier_apply(modifier=m.name)
        if len(lo.data.polygons) > s["budget"] * 1.3:
            # many loose greebles that decimation can't merge: keep the biggest pieces (the bake keeps the rest's
            # look). Islands labelled with numpy; Blender's separate-by-loose takes ages on thousands of pieces.
            import bmesh  # type: ignore
            import numpy as np
            me = lo.data
            tri = np.empty(len(me.polygons) * 3, np.int64)
            me.polygons.foreach_get("vertices", tri)
            tri = tri.reshape(-1, 3)
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            lab = np.arange(len(me.vertices))
            e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]]])
            while True:                               # label propagation + pointer jumping = connected pieces
                old = lab.copy()
                m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
                np.minimum.at(lab, e[:, 0], m)
                np.minimum.at(lab, e[:, 1], m)
                lab = lab[lab]
                if np.array_equal(lab, old):
                    break
            isl, vi = np.unique(lab, return_inverse=True)
            ext = np.zeros(len(isl))
            for k in range(3):                        # piece size = largest bounding-box side
                lo_k = np.full(len(isl), np.inf)
                hi_k = np.full(len(isl), -np.inf)
                np.minimum.at(lo_k, vi, co[:, k])
                np.maximum.at(hi_k, vi, co[:, k])
                ext = np.maximum(ext, hi_k - lo_k)
            fi = vi[tri[:, 0]]
            cnt = np.bincount(fi, minlength=len(isl))
            keep = np.zeros(len(isl), bool)
            total = 0
            for i in np.argsort(-ext):
                if total + cnt[i] <= s["budget"] * 1.2 or total == 0:
                    keep[i] = True
                    total += cnt[i]
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(~keep[fi])[0]], context="FACES")
            bm.to_mesh(me)
            bm.free()
            print(f"  {name}: kept {int(keep.sum())}/{len(isl)} pieces, {len(me.polygons)} tris")
            if len(lo.data.polygons) > s["budget"] * 1.3:
                m = lo.modifiers.new("dec", "DECIMATE")
                m.ratio = s["budget"] / len(lo.data.polygons)
                bpy.ops.object.modifier_apply(modifier=m.name)
                m = lo.modifiers.new("tri", "TRIANGULATE")
                bpy.ops.object.modifier_apply(modifier=m.name)
        if s.get("double"):                          # single-sided panels: add flipped copies so no side is culled
            import bmesh  # type: ignore
            bm2 = bmesh.new()
            bm2.from_mesh(lo.data)
            dup = bmesh.ops.duplicate(bm2, geom=bm2.faces[:])["geom"]
            bmesh.ops.reverse_faces(bm2, faces=[g for g in dup if isinstance(g, bmesh.types.BMFace)])
            bm2.to_mesh(lo.data)
            bm2.free()
        while lo.data.uv_layers:
            lo.data.uv_layers.remove(lo.data.uv_layers[0])
        lo.data.uv_layers.new(name="UVMap")
        lo.data.materials.clear()
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
        bpy.ops.object.mode_set(mode="OBJECT")
        img = bpy.data.images.new(f"bake_{name}", BAKE_PX, BAKE_PX)
        bm = bpy.data.materials.new("bake")
        bm.use_nodes = True
        tn = bm.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = img
        bm.node_tree.nodes.active = tn
        lo.data.materials.append(bm)
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = 4
        sc.render.bake.use_selected_to_active = True
        sc.render.bake.use_pass_direct = False
        sc.render.bake.use_pass_indirect = False
        sc.render.bake.use_pass_color = True
        sc.render.bake.cage_extrusion = 0.02 * s["size"]
        sc.render.bake.max_ray_distance = 0.06 * s["size"]
        sc.render.bake.margin = 4
        hi.select_set(True)
        lo.select_set(True)
        bpy.context.view_layer.objects.active = lo
        if s.get("ao"):                              # untextured model: shading detail from ambient occlusion
            sc.cycles.samples = 32
            bpy.ops.object.bake(type="AO")
        else:
            bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})
        img.filepath_raw = os.path.abspath(f"{BAKED}/{name}.png")
        img.file_format = "PNG"
        img.save()
        bpy.data.objects.remove(hi, do_unlink=True)
        # poses: wrecks nose-down, rolled and half buried; vaporators as a group of three
        if s.get("wreck"):
            ty, tx = s.get("tilt", (0.2, 0.15))
            lo.data.transform(Matrix.Rotation(ty, 4, "Y") @ Matrix.Rotation(tx, 4, "X"))
            zmin = min(v.co.z for v in lo.data.vertices)
            lo.data.transform(Matrix.Translation((0, 0, -zmin - s.get("bury", 0.045) * s["size"])))
        if s.get("copies"):
            parts = [lo]
            for x, y, sc_ in ((0.75, 0.35, 0.85), (-0.4, 0.7, 0.9))[: s["copies"] - 1]:
                c = lo.copy()
                c.data = lo.data.copy()
                c.data.transform(Matrix.Translation((x, y, 0)) @ Matrix.Scale(sc_, 4) @
                                 Matrix.Rotation(rng.uniform(0, 6.28), 4, "Z"))
                bpy.context.scene.collection.objects.link(c)
                parts.append(c)
            for o in bpy.context.scene.objects:
                o.select_set(o in parts)
            bpy.context.view_layer.objects.active = lo
            bpy.ops.object.join()
        stem = mesh_name(name)
        out_dir = os.path.abspath(out_of(name))
        os.makedirs(out_dir, exist_ok=True)
        train = s["kind"] != "prop"                  # trains and buildings: Advanced layout with a properties map
        shader = {"train": "PdxMeshTrain", "prop": "PdxMeshAdvancedSnow", "building": "PdxMeshSnow"}[s["kind"]]
        mat = bie.create_shader(Mat(stem, shader, train), stem, out_dir)
        mat[PDX_SHADER] = shader
        lo.data.materials[0] = mat
        uv1 = lo.data.uv_layers.new(name="uv1")      # tree.shader reads uv1 as a per-instance random offset
        for d in uv1.data:
            d.uv = (0.0, 0.0)
        lo.name = lo.data.name = stem
        bie.export_meshfile(os.path.join(out_dir, stem + ".mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
        d = [max(v.co[i] for v in lo.data.vertices) - min(v.co[i] for v in lo.data.vertices) for i in range(3)]
        print(f"{name}: {tris} -> {len(lo.data.polygons)} tris, size {d[0]:.2f} x {d[1]:.2f} x {d[2]:.2f}")


def textures(*only):
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    for name, s in SPECS.items():
        path = f"{BAKED}/{name}.png"
        if only and name not in only or not os.path.exists(path):
            continue
        im = np.asarray(Image.open(path).convert("RGB").resize((512, 512), Image.LANCZOS)).astype(np.float32)
        full = lambda v: np.full((512, 512), v, np.float32)
        stem = mesh_name(name)
        OUT_ = out_of(name)
        if s.get("wreck"):
            im = rusted(im) if s["wreck"] == "rust" else burnt(im)
        if s.get("ao"):
            im = im.mean(-1, keepdims=True) / 255 * np.array(s["ao"], np.float32)
        emi_src = im
        if s.get("lift"):
            im = lift(im, *s["lift"])
        save_dxt5_mips(np.dstack([im, full(255)]), f"{OUT_}/{stem}_diffuse.dds")
        if s["kind"] == "train":
            for v, hue in PAINT.items():
                save_dxt5_mips(np.dstack([repaint(im, hue), full(255)]), f"{OUT_}/{stem}_{v}_diffuse.dds")
        if s["kind"] != "prop":      # Advanced layout (normal G/A = xy, B = night emission; props G spec, B metal, A gloss)
            # ships (out = the shipyard) get no "lit windows": their white hull paint glowed as white dots
            emi = windows(emi_src) if s["kind"] == "building" and not name.startswith(("bon_", "pam_")) else full(0)
            save_dxt5_mips(np.dstack([full(0), full(128), emi, full(128)]), f"{OUT_}/{stem}_normal.dds")
            save_dxt5_mips(np.dstack([full(0), full(70), full(0), full(90)]), f"{OUT_}/{stem}_properties.dds")
        else:
            save_dxt5_mips(np.dstack([full(128), full(128), full(255), full(255)]), f"{OUT_}/{stem}_normal.dds")
        # bake() exports before these DDS exist, so the exporter leaves the material's texture names empty:
        # write them into the .mesh now
        sys.path.insert(0, os.path.join(os.environ["LOCALAPPDATA"], "universal-modder/tools/blender-4.2.3-windows-x64/4.2/scripts/addons"))
        from io_pdx_mesh.pdx_data import read_meshfile, write_meshfile
        mesh = f"{OUT_}/{stem}.mesh"
        root = read_meshfile(mesh)
        for mat in root.iter("material"):
            mat.set("diff", [f"{stem}_diffuse.dds"])
            mat.set("n", [f"{stem}_normal.dds"])
            mat.set("spec", [f"{stem}_properties.dds" if s["kind"] != "prop" else "hod_flora_spec.dds"])
        write_meshfile(mesh, root)
        print("textures", stem)


def lift(im, target, tint):
    """Brighten a dark bake toward mean luminance `target` (soft-clipped so lit windows don't blow out), tinted by `tint`."""
    import numpy as np
    lum = im.mean(-1)
    ref = max(lum[lum > 4].mean() if (lum > 4).any() else 1.0, 1.0)     # skip the black padding between UV islands
    x = 1 - np.exp(-im / ref * target / 255 * 1.6)
    shade = x.mean(-1, keepdims=True)
    return np.clip(x * 255 * 0.7 + np.array(tint, np.float32) * shade * 0.3 * 1.6, 0, 255)


def windows(im):
    """Night emission for baked buildings: lit windows = bright, warm or cyan pixels well above their surroundings."""
    import numpy as np
    from scipy import ndimage as ndi
    lum = im.mean(-1)
    local = ndi.uniform_filter(lum, 9)
    lit = (lum > 150) & (lum > local * 1.25)
    return np.where(lit, 230, 0).astype(np.float32)


def burnt(im):
    """Wrecks: soot-darkened, scorch blotches, a few bare-metal patches left."""
    import numpy as np
    from scipy import ndimage as ndi
    rng = np.random.default_rng(5)
    n = ndi.gaussian_filter(rng.random(im.shape[:2]), 18)
    n = (n - n.min()) / np.ptp(n)
    fine = ndi.gaussian_filter(rng.random(im.shape[:2]), 2)
    fine = (fine - fine.min()) / np.ptp(fine)
    grey = im.mean(-1, keepdims=True)
    out = (im * 0.4 + grey * 0.6) * (0.25 + 0.35 * n[..., None] + 0.15 * fine[..., None])
    out += np.array([18, 8, 2], np.float32) * (n[..., None] < 0.3)          # rusty-brown scorch edges
    return np.clip(out, 0, 255)


def rusted(im):
    """Old hulks left to the weather (Raxus Prime): paint kept but faded, rust patches and streaks running down."""
    import numpy as np
    from scipy import ndimage as ndi
    rng = np.random.default_rng(6)
    n = ndi.gaussian_filter(rng.random(im.shape[:2]), 14)
    n = (n - n.min()) / np.ptp(n)
    streak = ndi.gaussian_filter(rng.random(im.shape[:2]), (20, 1.5))
    streak = (streak - streak.min()) / np.ptp(streak)
    rust = np.clip((0.45 - n) / 0.2, 0, 1)[..., None] * 0.7 + (streak[..., None] > 0.72) * 0.35
    lum = im.mean(-1, keepdims=True)
    out = (im * 0.75 + lum * 0.25) * (0.8 + 0.2 * n[..., None])
    out = out * (1 - rust) + np.array([150, 82, 44], np.float32) * (0.6 + lum / 255) * rust
    return np.clip(out, 0, 255)


def repaint(im, hue):
    """Speeder paint job: rotate the hue of saturated pixels (None = desaturate to grey)."""
    import numpy as np
    from PIL import Image
    hsv = np.asarray(Image.fromarray(im.astype(np.uint8)).convert("HSV")).astype(np.float32)
    painted = hsv[..., 1] > 70
    if hue is None:
        hsv[..., 1] = np.where(painted, hsv[..., 1] * 0.15, hsv[..., 1])
    else:
        hsv[..., 0] = np.where(painted, (hsv[..., 0] + hue / 360 * 255) % 255, hsv[..., 0])
    return np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")).astype(np.float32)


def wire():
    """Supply trains: speeder convoys (gfx/train_gfx_database/generic.txt replaces vanilla's). Each paint job is
    its own pdxmesh entry on the same .mesh with an overriding texture_diffuse; each train equipment level gets
    its own lead colour, the cars pick randomly from every colour of both speeders."""
    ents = {}
    with open("gfx/entities/hod_trains.gfx", "w", encoding="utf-8", newline="\n") as f:
        f.write("objectTypes = {\n\t# HOD: speeder convoys instead of trains (WIPGFX/plans & scripts/sketchfab_props.py)\n")
        for n in ("xj6", "x34"):
            stem = mesh_name(n)
            for v in PAINT:
                f.write(f'\tpdxmesh = {{\n\t\tname = "{stem}_{v}_mesh"\n\t\tfile = "{OUT}/{stem}.mesh"\n'
                        f'\t\tmeshsettings = {{\n\t\t\tname = "{stem}"\n\t\t\tindex = 0\n'
                        f'\t\t\ttexture_diffuse = "{stem}_{v}_diffuse.dds"\n\t\t\ttexture_normal = "{stem}_normal.dds"\n'
                        f'\t\t\ttexture_specular = "{stem}_properties.dds"\n\t\t\tshader = "PdxMeshTrain"\n\t\t}}\n\t}}\n')
                ents.setdefault(n, []).append(f"{stem}_{v}_entity")
        f.write("}\n")
    with open("gfx/entities/hod_trains.asset", "w", encoding="utf-8", newline="\n") as f:
        for n in ("xj6", "x34"):
            for v in PAINT:
                f.write(f'entity = {{\n\tname = "{mesh_name(n)}_{v}_entity"\n\tpdxmesh = "{mesh_name(n)}_{v}_mesh"\n}}\n\n')
    body = ("# HOD: supply trains are speeder convoys (WIPGFX/plans & scripts/sketchfab_props.py wire).\n"
            "# rotation/shift/length as vanilla's wagon_data; speeders hover a little higher than rail cars.\n\n")
    for n, length in (("xj6", 2.0), ("x34", 1.5)):
        for ent in ents[n]:
            body += (f"wagon_data = {{\n\tentity = {ent}\n\tscale = 1\n\trotation = 90\n"
                     f"\tshift = {{ 0.0 0.9 0.0 }}\n\tlength = {length}\n}}\n\n")
    cars = ents["x34"] + ents["xj6"]
    body += "default = {\n"
    for k, eq in enumerate(("train_equipment_1", "train_equipment_2", "train_equipment_3")):
        x = ents["x34"]
        body += (f"\t{eq} = {{\n\t\twagon_0 = {ents['xj6'][k]}\n\t\twagon_1 = {x[(k + 1) % len(x)]}\n"
                 f"\t\twagon_2 = {x[(k + 3) % len(x)]}\n\t\twagon_last = {x[(k + 5) % len(x)]}\n\t\twagons = {{\n"
                 + "".join(f"\t\t\t{c}\n" for c in cars) + "\t\t}\n\t}\n")
    body += "}\n"
    os.makedirs("gfx/train_gfx_database", exist_ok=True)
    open("gfx/train_gfx_database/generic.txt", "w", encoding="utf-8", newline="\n").write(body)
    print("trains wired")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"bake": bake, "textures": textures, "wire": wire}[args[0]](*args[1:])
