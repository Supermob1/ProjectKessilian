"""Poly Haven (CC0) trees, shrubs and rocks as HOI4 map trees: each asset becomes `mapobject_<index>` in
gfx/entities/trees.gfx, drawn wherever map/trees.bmp holds that palette index (planet_terrain_gen.py paints them).
The tree renderer (gfx/FX/tree.shader) adds random heading, 0.75-1.25 height and terrain slope; it alpha-tests
the diffuse (clip at 0.5), so leaf cards keep their cut-out.

  python "WIPGFX/plans & scripts/flora_props.py" download     glTF 1k + leaf alpha maps -> WIPGFX/3d/polyhaven/<id>/
  python "WIPGFX/plans & scripts/flora_props.py" textures     DDS textures -> gfx/models/mapitems/hod_flora/
  blender -b --factory-startup --python "WIPGFX/plans & scripts/flora_props.py" -- meshes
  blender -b --factory-startup --python "WIPGFX/plans & scripts/flora_props.py" -- procedural
  python "WIPGFX/plans & scripts/flora_props.py" wire         gfx/entities/trees.gfx = vanilla entries + ours
"""
import collections, glob, io, json, os, struct, sys

SRC = "WIPGFX/3d/polyhaven"
OUT = "gfx/models/mapitems/hod_flora"
VANILLA_TREES = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/entities/trees.gfx"
TEX_SIZE = 512          # trees are a few pixels tall on screen
LEAF_SHARE = 0.7        # share of the triangle budget for leaf cards
# trees.bmp index: (Poly Haven id, object name prefix to keep (None = all), triangle budget, largest extent in map units)
# (vanilla tree meshes: ~400-1300 tris, ~2.6 wide x 2 tall)
ASSETS = {
    42: ("quiver_tree_01", None, 1200, 2.4),                       # alien succulent tree: deserts, steppe
    43: ("quiver_tree_02", None, 900, 1.6),
    44: ("searsia_lucida", "searsia_lucida_a", 1200, 2.2),        # bushy shrub-tree: savanna, grassland
    45: ("othonna_cerarioides", "othonna_cerarioides_a", 1000, 1.6),  # desert succulent shrub
    46: ("fern_02", None, 600, 1.0),                               # jungle / swamp understory
    47: ("dead_tree_trunk_02", None, 500, 2.4),                    # fallen trunk: swamps, dead worlds
    48: ("moon_rock_01", "moon_rock_01_LOD0", 500, 1.8),           # bare rock: barren, lava, ice
    49: ("moon_rock_03", None, 500, 1.4),
    50: ("namaqualand_boulder_02", None, 600, 2.2),                # desert boulder
    51: ("rock_moss_set_01", "rock_moss_set_01_rock01", 500, 1.8), # mossy rock: forests, alpine
    52: ("boulder_01", None, 600, 1.6),                            # grey boulder: alpine, steppe
}
# built in Blender by procedural(): photo-scanned giants don't survive a 2k-triangle budget (trunks shred, canopies
# turn to confetti), so these are modelled the game way: simple trunk + canopy clumps of leaf cards.
PROCEDURAL = {
    40: "wroshyr",        # Kashyyyk giant: tall straight trunk, buttress roots, layered canopy platforms
    41: "jungle_giant",   # umbrella canopy on a short thick trunk
    55: "homestead",      # desert homestead: adobe domes + a small vaporator
    # Felucia: a fungal jungle in saturated colours (Star Wars Databank: "immense primitive plants", "enormous pitcher
    # plants and leafy growths", "colour-saturated"; Wookieepedia: giant purple mushrooms form the upper canopy, many
    # life-forms are translucent and colour the sunlight). Bigger than any tree: they tower over the jungle
    58: "fel_mushroom",   # giant purple mushroom: tall pale stalk, broad violet cap, small ones at its foot
    59: "fel_bulbs",      # translucent orange / yellow stalks with bulbous heads (Revenge of the Sith)
    60: "fel_pitcher",    # giant teal pitcher plant with a magenta lip
    61: "fel_fronds",     # giant curling crimson fronds
}
PROC_MATS = {40: ["hod_dead_tree_trunk_02", "hod_foliage_wroshyr"], 41: ["hod_dead_tree_trunk_02", "hod_foliage_jungle"],
             55: ["hod_adobe"], 58: ["hod_fel_stalk", "hod_fel_cap"], 59: ["hod_fel_bulb"], 60: ["hod_fel_pitcher"],
             61: ["hod_fel_frond"]}
# Sketchfab models converted by sketchfab_props.py (meshes land in OUT as hod_flora_<index>_<name>.mesh)
EXTERNAL = {53: "sandcrawler", 54: "vaporators", 56: "wreck_harrower", 57: "wreck_foray"}
LEAF_SRC = "island_tree_01"  # Poly Haven leaf sheet the foliage clumps are composed from


def save_dxt5_mips(rgba, path):
    """DXT5 DDS with a full mip chain (Pillow writes one level; concatenate levels and patch the header)."""
    import numpy as np
    from PIL import Image
    levels, im = [], Image.fromarray(np.asarray(rgba, np.uint8), "RGBA")
    while True:
        buf = io.BytesIO()
        im.save(buf, format="DDS", pixel_format="DXT5")
        levels.append(buf.getvalue())
        if im.size == (1, 1):
            break
        im = im.resize((max(1, im.size[0] // 2), max(1, im.size[1] // 2)), Image.BOX)
    hdr = bytearray(levels[0][:128])
    struct.pack_into("<I", hdr, 8, struct.unpack_from("<I", hdr, 8)[0] | 0x20000)
    struct.pack_into("<I", hdr, 28, len(levels))
    struct.pack_into("<I", hdr, 108, struct.unpack_from("<I", hdr, 108)[0] | 0x400008)
    with open(path, "wb") as f:
        f.write(bytes(hdr) + b"".join(l[128:] for l in levels))


def download():
    import urllib.request
    hdr = {"User-Agent": "HoD-mod/1.0"}
    for pid in [a[0] for a in ASSETS.values()] + [LEAF_SRC]:
        d = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.polyhaven.com/files/{pid}", headers=hdr)))
        g = d["gltf"]["1k"]["gltf"]
        files = [(f"{pid}.gltf", g["url"])] + [(rel, v["url"]) for rel, v in g.get("include", {}).items()]
        files += [(f"textures/{os.path.basename(v['1k']['png']['url'])}", v["1k"]["png"]["url"])
                  for k, v in d.items() if "alpha" in k.lower()]
        for rel, url in files:
            path = f"{SRC}/{pid}/{rel}"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not os.path.exists(path):
                urllib.request.urlretrieve(url, path)
        print(pid, len(files), "files")


def materials(pid):
    """[(material name, diffuse path, normal path, alpha path or None)] from the asset's glTF."""
    g = json.load(open(f"{SRC}/{pid}/{pid}.gltf", encoding="utf-8"))
    uri = lambda t: f"{SRC}/{pid}/" + g["images"][g["textures"][t["index"]]["source"]]["uri"]
    out = []
    for m in g["materials"]:
        diff = uri(m["pbrMetallicRoughness"]["baseColorTexture"])
        nrm = uri(m["normalTexture"]) if "normalTexture" in m else None
        alpha = None
        if m.get("alphaMode") in ("BLEND", "MASK"):
            alpha = next((p for p in (f"{SRC}/{pid}/textures/{m['name']}_alpha_1k.png",
                                      f"{SRC}/{pid}/textures/{pid}_alpha_1k.png") if os.path.exists(p)), None)
        out.append((m["name"], diff, nrm, alpha))
    return out


def textures():
    import numpy as np
    from PIL import Image
    os.makedirs(OUT, exist_ok=True)
    rgb = lambda p: np.asarray(Image.open(p).convert("RGB").resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float32)
    leaf, tex = {}, {}

    def save(stem, diff, nrm):
        tex[stem] = (diff, nrm)
        save_dxt5_mips(diff, f"{OUT}/{stem}_diffuse.dds")
        save_dxt5_mips(nrm, f"{OUT}/{stem}_normal.dds")

    for pid, *_ in ASSETS.values():
        for name, diff, nrm, alpha in materials(pid):
            a = (np.asarray(Image.open(alpha).convert("L").resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float32)
                 if alpha else np.full((TEX_SIZE, TEX_SIZE), 255, np.float32))
            n = rgb(nrm) if nrm else np.dstack([np.full((TEX_SIZE, TEX_SIZE), v, np.float32) for v in (128, 128, 255)])
            save(f"hod_{name}", np.dstack([rgb(diff), a]), np.dstack([n, np.full(n.shape[:2], 255, np.float32)]))
            leaf[name] = alpha is not None
    flat = np.zeros((16, 16, 4), np.float32)
    save_dxt5_mips(flat, f"{OUT}/hod_flora_spec.dds")
    flat_n = np.dstack([np.full((TEX_SIZE, TEX_SIZE), v, np.float32) for v in (128, 128, 255, 255)])
    rng = np.random.default_rng(66)
    # foliage clumps: hundreds of small copies of the Poly Haven leaves packed into a soft disc (one leaf card
    # = one clump of foliage, the way game trees are built)
    from scipy import ndimage as ndi
    sheet = np.asarray(Image.open(f"{SRC}/{LEAF_SRC}/textures/{LEAF_SRC}_leaves_diff_1k.jpg").convert("RGB")).astype(np.float32)
    mask = np.asarray(Image.open(f"{SRC}/{LEAF_SRC}/textures/{LEAF_SRC}_leaves_alpha_1k.png").convert("L")) > 128
    lab, n = ndi.label(mask)
    leaves = [(sheet[sl], mask[sl] & (lab[sl] == i + 1)) for i, sl in enumerate(ndi.find_objects(lab))
              if (lab[sl] == i + 1).sum() > 4000]
    for name, tint in (("hod_foliage_wroshyr", (0.55, 0.75, 0.5)), ("hod_foliage_jungle", (0.8, 1.0, 0.6))):
        S = TEX_SIZE
        col = np.zeros((S, S, 3), np.float32)
        alp = np.zeros((S, S), np.float32)
        for _ in range(420):
            c, m = leaves[rng.integers(len(leaves))]
            sc = rng.uniform(0.07, 0.13) * S / max(c.shape[:2])
            ang = rng.uniform(0, 360)
            ci = Image.fromarray(c.astype(np.uint8)).resize((max(2, int(c.shape[1] * sc)), max(2, int(c.shape[0] * sc))))
            mi = Image.fromarray((m * 255).astype(np.uint8)).resize(ci.size)
            ci, mi = np.asarray(ci.rotate(ang, expand=True)).astype(np.float32), np.asarray(mi.rotate(ang, expand=True)) > 128
            r = S * 0.42 * np.sqrt(rng.random())
            a = rng.uniform(0, 6.283)
            y0, x0 = int(S / 2 + r * np.sin(a) - mi.shape[0] / 2), int(S / 2 + r * np.cos(a) - mi.shape[1] / 2)
            ys, xs = np.nonzero(mi)
            ys, xs = ys + y0, xs + x0
            ok = (ys >= 0) & (ys < S) & (xs >= 0) & (xs < S)
            shade = 0.55 + 0.45 * (1 - r / (S * 0.42)) * rng.uniform(0.8, 1.1)    # darker toward the rim, like depth
            col[ys[ok], xs[ok]] = ci[ys[ok] - y0, xs[ok] - x0] * np.array(tint) * shade
            alp[ys[ok], xs[ok]] = 255
        save(name, np.dstack([np.clip(col, 0, 255), alp]), flat_n)
        leaf[name] = True
    # homestead adobe (panelled-surface generator, panels off)
    S = TEX_SIZE
    yy, xx = np.mgrid[0:S, 0:S]

    def surface(stem, colour, panels, streaks):
        grime = ndi.gaussian_filter(rng.random((S, S)), 6)
        grime = (grime - grime.min()) / np.ptp(grime)
        streak = ndi.gaussian_filter(rng.random((S, S)), (24, 1.5))
        streak = (streak - streak.min()) / np.ptp(streak)
        panel = ((xx % 128 < 2) | (yy % 96 < 2)).astype(np.float32) * panels
        base = np.array(colour, np.float32) * (0.75 + 0.35 * grime[..., None]) * (0.85 + 0.25 * streak[..., None])
        base = base * (1 - 0.25 * panel[..., None]) * (1 - streaks * (streak[..., None] > 0.7))
        lum = ndi.gaussian_filter(base.mean(-1) / 255, 1)
        gx, gy = ndi.sobel(lum, 1) * 2, ndi.sobel(lum, 0) * 2
        nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        save(stem, np.dstack([np.clip(base, 0, 255), np.full((S, S), 255, np.float32)]),
             np.dstack([nrm * 127.5 + 127.5, np.full((S, S), 255, np.float32)]))

    surface("hod_adobe", (176, 156, 122), 0, 0.08)

    def organic(stem, stops, spots=None, veins=0.0):
        """Felucian flora: colour by the texture's v (bottom-up = along the lathe profile), soft mottling, optional
        pale spots and vertical veins. stops: [(v, (r, g, b))]"""
        v = 1 - yy / (S - 1)                       # image row 0 = top = Blender v 1
        vs, cs = zip(*stops)
        base = np.stack([np.interp(v, vs, [c[i] for c in cs]) for i in range(3)], -1)
        mott = ndi.gaussian_filter(rng.random((S, S)), 5)
        mott = (mott - mott.min()) / np.ptp(mott)
        base = base * (0.8 + 0.35 * mott[..., None])
        if veins:
            vein = ndi.gaussian_filter(rng.random((S, S)), (30, 1.2))
            vein = (vein - vein.min()) / np.ptp(vein)
            base = base * (1 - veins * (vein[..., None] > 0.72))
        if spots:
            col, n, r = spots
            for _ in range(n):
                cy, cx, rr = rng.integers(0, S), rng.integers(0, S), rng.uniform(0.4, 1.0) * r
                d = np.hypot(np.minimum(abs(yy - cy), S - abs(yy - cy)), np.minimum(abs(xx - cx), S - abs(xx - cx)))
                m = np.clip((rr - d) / 2, 0, 1)[..., None] * (v[..., None] > 0.45)
                base = base * (1 - m) + np.array(col, np.float32) * m
        lum = ndi.gaussian_filter(base.mean(-1) / 255, 1.5)
        gx, gy = ndi.sobel(lum, 1) * 1.5, ndi.sobel(lum, 0) * 1.5
        nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        save(stem, np.dstack([np.clip(base, 0, 255), np.full((S, S), 255, np.float32)]),
             np.dstack([nrm * 127.5 + 127.5, np.full((S, S), 255, np.float32)]))

    # stalk: pale cream foot -> lilac top; cap profile runs underside (gills) -> rim -> crown
    organic("hod_fel_stalk", [(0, (150, 135, 120)), (0.6, (205, 190, 200)), (1, (185, 150, 210))], veins=0.15)
    organic("hod_fel_cap", [(0, (95, 45, 95)), (0.3, (150, 80, 150)), (0.42, (235, 190, 240)), (0.55, (150, 55, 190)),
                            (1, (95, 30, 150))], spots=((240, 215, 120), 26, 14))
    organic("hod_fel_bulb", [(0, (120, 60, 30)), (0.35, (235, 120, 25)), (0.8, (255, 205, 60)), (1, (255, 240, 150))], veins=0.2)
    organic("hod_fel_pitcher", [(0, (25, 70, 65)), (0.55, (40, 165, 160)), (0.82, (90, 210, 200)), (0.9, (225, 45, 140)),
                                (1, (250, 110, 190))], veins=0.25)
    organic("hod_fel_frond", [(0, (70, 15, 30)), (0.5, (200, 30, 60)), (1, (255, 120, 70))], veins=0.3)
    for stem in ("hod_fel_stalk", "hod_fel_cap", "hod_fel_bulb", "hod_fel_pitcher", "hod_fel_frond"):
        leaf[stem] = False
    # one atlas per multi-material model: the tree renderer draws only a mesh's first material (vanilla trees
    # all have one), so trunk + leaves share one texture, one vertical slot each (bottom-up = Blender's v)
    atlas = {idx: [f"hod_{m[0]}" for m in materials(pid)] for idx, (pid, *_r) in ASSETS.items()}
    atlas.update(PROC_MATS)
    atlas = {idx: stems for idx, stems in atlas.items() if len(stems) > 1}
    for idx, stems in atlas.items():
        k = 1 << (len(stems) - 1).bit_length()
        for ch, suffix in ((0, "diffuse"), (1, "normal")):
            img = np.zeros((TEX_SIZE * k, TEX_SIZE, 4), np.float32)
            img[...] = tex[stems[0]][ch][0, 0]
            for slot, stem in enumerate(stems):
                img[(k - 1 - slot) * TEX_SIZE:(k - slot) * TEX_SIZE] = tex[stem][ch]
            save_dxt5_mips(img, f"{OUT}/hod_flora_{idx}_atlas_{suffix}.dds")
    json.dump(atlas, open(f"{OUT}/atlas.json", "w"), indent=1)
    leaf["hod_adobe"] = False
    json.dump(leaf, open(f"{OUT}/leaf_materials.json", "w"), indent=1)
    print("textures:", len(leaf), "materials,", sum(leaf.values()), "with leaf alpha")


def single_material(obj, idx, stems, bie, PDX_SHADER, out_dir):
    """Blender: give the mesh one PDX material. With several, move each face's UVs into its material's slot of
    the atlas written by textures() (atlas.json) and point every face at slot 0."""
    import bpy  # type: ignore

    class Mat:
        def __init__(self, tex):
            self.shader = ["PdxMeshAdvancedSnow"]
            self.diff, self.n, self.spec = [f"{tex}_diffuse.dds"], [f"{tex}_normal.dds"], ["hod_flora_spec.dds"]

    me = obj.data
    used = sorted({p.material_index for p in me.polygons})
    tex = stems[used[0]]
    if len({stems[i] for i in used}) > 1:
        order = json.load(open(f"{OUT}/atlas.json"))[str(idx)]
        k = 1 << (len(order) - 1).bit_length()
        uv = me.uv_layers[0].data
        for p in me.polygons:
            slot = order.index(stems[p.material_index])
            for li in p.loop_indices:
                u, v = uv[li].uv
                uv[li].uv = (u, (slot + min(max(v, 0.0), 1.0)) / k)
            p.material_index = 0
        tex = f"hod_flora_{idx}_atlas"
    else:
        for p in me.polygons:
            p.material_index = 0
    mat = bie.create_shader(Mat(tex), tex, out_dir)
    mat[PDX_SHADER] = "PdxMeshAdvancedSnow"
    me.materials[0] = mat
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.material_slot_remove_unused()


def meshes():
    import random
    import bmesh  # type: ignore
    import bpy  # type: ignore
    import numpy as np
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    leaf = json.load(open(f"{OUT}/leaf_materials.json"))
    out_dir = os.path.abspath(OUT)
    rng = random.Random(1977)

    class Mat:   # minimal stand-in for io_pdx_mesh's parsed PDX material
        def __init__(self, name):
            self.shader = ["PdxMeshAdvancedSnow"]
            self.diff = [f"hod_{name}_diffuse.dds"]
            self.n = [f"hod_{name}_normal.dds"]
            self.spec = ["hod_flora_spec.dds"]

    def tri_count(o):
        return sum(len(p.vertices) - 2 for p in o.data.polygons)

    def apply(o, mod_type, **kw):
        bpy.context.view_layer.objects.active = o
        m = o.modifiers.new("m", mod_type)
        for k, v in kw.items():
            setattr(m, k, v)
        bpy.ops.object.modifier_apply(modifier=m.name)

    def islands(me):
        """(triangles, island label per vertex, island ids, island index per face, triangles per island)."""
        nv, nf = len(me.vertices), len(me.polygons)
        tri = np.empty(nf * 3, np.int64)
        me.polygons.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3)
        lab = np.arange(nv)
        e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]]])
        while True:                                   # label propagation + pointer jumping = connected islands
            old = lab.copy()
            m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
            np.minimum.at(lab, e[:, 0], m)
            np.minimum.at(lab, e[:, 1], m)
            lab = lab[lab]
            if np.array_equal(lab, old):
                break
        isl, inv, cnt = np.unique(lab[tri[:, 0]], return_inverse=True, return_counts=True)
        return tri, lab, isl, inv, cnt

    def thin_leaves(o, budget, grow_cap=4.0, largest_first=False):
        """Keep leaf cards (connected islands) up to the budget, enlarged so the canopy keeps its cover.
        Cards are first collapsed to a few triangles each so many more of them fit. With largest_first (solid
        parts that decimation can't reduce, e.g. loose twigs and pebbles) the biggest pieces survive, unscaled."""
        apply(o, "TRIANGULATE")
        me = o.data
        nf0 = len(me.polygons)
        n_isl = len(islands(me)[2])
        if nf0 > 6 * n_isl and not largest_first:
            apply(o, "DECIMATE", ratio=6 * n_isl / nf0)
            apply(o, "TRIANGULATE")
        nv, nf = len(me.vertices), len(me.polygons)
        tri, lab, isl, inv, cnt = islands(me)
        order = list(np.argsort(-cnt)) if largest_first else list(range(len(isl)))
        if not largest_first:
            rng.shuffle(order)
        keep = np.zeros(len(isl), bool)
        total = 0
        for i in order:
            if total + cnt[i] > budget:
                continue
            keep[i] = True
            total += cnt[i]
        grow = float(np.clip(np.sqrt(nf / max(total, 1)), 1.0, grow_cap))
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        vi = np.searchsorted(isl, lab)                # island index per vertex
        cen = np.stack([np.bincount(vi, co[:, k], len(isl)) for k in range(3)], -1) / np.bincount(vi, minlength=len(isl))[:, None]
        co = cen[vi] + (co - cen[vi]) * grow
        me.vertices.foreach_set("co", co.ravel())
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(~keep[inv])[0]], context="FACES")
        bm.to_mesh(me)
        bm.free()
        return len(isl), int(keep.sum()), grow

    report = []
    only = os.environ.get("HOD_ONLY")
    for idx, (pid, prefix, budget, extent) in ASSETS.items():
        if only and str(idx) not in only.split(","):
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(f"{SRC}/{pid}/{pid}.gltf"))
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and (prefix is None or o.name.startswith(prefix))]
        for o in list(bpy.context.scene.objects):
            if o not in objs:
                bpy.data.objects.remove(o, do_unlink=True)
        for o in bpy.context.scene.objects:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        if len(objs) > 1:
            bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        src_tris = tri_count(obj)
        # split per material: leaf cards are thinned, solid parts decimated, each with its own share of the budget
        # (by sqrt of its size, so a small trunk isn't decimated away next to a huge twig mesh)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.separate(type="MATERIAL")
        bpy.ops.object.mode_set(mode="OBJECT")
        parts = [o for o in bpy.context.scene.objects if o.type == "MESH" and len(o.data.polygons)]
        is_leaf = lambda o: leaf.get(o.data.materials[o.data.polygons[0].material_index].name.split(".")[0], False)
        leaves = [o for o in parts if is_leaf(o)]
        solids = [o for o in parts if not is_leaf(o)]
        solid_budget = budget * (1 - LEAF_SHARE) if leaves else budget
        weight = {o: tri_count(o) ** 0.5 for o in solids}
        note = ""
        for o in solids:
            b = solid_budget * weight[o] / sum(weight.values())
            if tri_count(o) > b:
                apply(o, "DECIMATE", ratio=b / tri_count(o))
            if tri_count(o) > b * 1.3:      # many loose pieces: keep the biggest
                thin_leaves(o, b, grow_cap=1.0, largest_first=True)
        for o in leaves:
            n_isl, kept, grow = thin_leaves(o, budget * LEAF_SHARE / len(leaves))
            note += f", leaf cards {kept}/{n_isl} x{grow:.1f}"
        obj = (solids + leaves)[0]
        # join back, triangulate, PDX materials, second UV set (tree.shader reads uv1 as a per-tree random offset)
        for o in bpy.context.scene.objects:
            o.select_set(o.type == "MESH")
        bpy.context.view_layer.objects.active = obj
        if len(parts) > 1:
            bpy.ops.object.join()
        apply(obj, "TRIANGULATE")
        single_material(obj, idx, [f"hod_{m.name.split('.')[0]}" for m in obj.data.materials], bie, PDX_SHADER, out_dir)
        while len(obj.data.uv_layers) < 2:
            uv = obj.data.uv_layers.new()
            for d in uv.data:
                d.uv = (0.0, 0.0)
        # base on the origin, largest extent scaled to the target
        co = np.empty(len(obj.data.vertices) * 3, np.float32)
        obj.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        lo, hi = co.min(0), co.max(0)
        s = extent / float((hi - lo).max())
        co = (co - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])) * s
        obj.data.vertices.foreach_set("co", co.ravel())
        obj.data.update()
        name = f"hod_flora_{idx}_{pid}"
        obj.name = obj.data.name = name
        bie.export_meshfile(os.path.join(out_dir, name + ".mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
        d = (hi - lo) * s
        per = collections.Counter(obj.data.materials[p.material_index].name for p in obj.data.polygons)
        note += f", {dict(per)}"
        report.append(f"{idx} {pid}: {src_tris} -> {tri_count(obj)} tris, size {d[0]:.2f} x {d[1]:.2f} x {d[2]:.2f}{note}")
    print("\n".join(report))


def procedural():
    """Blender: wroshyr, jungle giant and homestead from primitives (textures from textures())."""
    import math
    import random
    import bmesh  # type: ignore
    import bpy  # type: ignore
    from mathutils import Matrix, Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    out_dir = os.path.abspath(OUT)
    rng = random.Random(4)

    class Mat:
        def __init__(self, tex):
            self.shader = ["PdxMeshAdvancedSnow"]
            self.diff, self.n, self.spec = [f"{tex}_diffuse.dds"], [f"{tex}_normal.dds"], ["hod_flora_spec.dds"]

    def tube(bm, uv, pts, sides, mat, vrep=1.0):
        """Rings of (centre Vector, radius) joined into a tapered tube, cylindrical UVs."""
        rings = []
        for c, r in pts:
            rings.append([bm.verts.new(c + Vector((math.cos(a) * r, math.sin(a) * r, 0)))
                          for a in (2 * math.pi * i / sides for i in range(sides))])
        for k in range(len(rings) - 1):
            for i in range(sides):
                j = (i + 1) % sides
                f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
                f.material_index = mat
                for loop, (u, v) in zip(f.loops, ((i / sides, k / len(rings)), ((i + 1) / sides, k / len(rings)),
                                                  ((i + 1) / sides, (k + 1) / len(rings)), (i / sides, (k + 1) / len(rings)))):
                    loop[uv].uv = (u, v * vrep)

    def limb(bm, uv, a, b, r0, r1, mat, sides=5, segs=3):
        """Tube from a to b (rings oriented along the limb)."""
        d = (b - a)
        rot = d.to_track_quat("Z", "Y").to_matrix()
        rings = []
        for k in range(segs + 1):
            t = k / segs
            c, r = a + d * t, r0 + (r1 - r0) * t
            rings.append([bm.verts.new(c + rot @ Vector((math.cos(x) * r, math.sin(x) * r, 0)))
                          for x in (2 * math.pi * i / sides for i in range(sides))])
        for k in range(segs):
            for i in range(sides):
                j = (i + 1) % sides
                f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
                f.material_index = mat
                for loop, (u, v) in zip(f.loops, ((i / sides, k / segs), ((i + 1) / sides, k / segs),
                                                  ((i + 1) / sides, (k + 1) / segs), (i / sides, (k + 1) / segs))):
                    loop[uv].uv = (u, v)

    def card(bm, uv, c, size, mat):
        """Foliage card facing mostly up (the HOI4 camera looks down), random tilt and spin."""
        n = Vector((rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7), 1.0)).normalized()
        rot = n.to_track_quat("Z", "Y").to_matrix() @ Matrix.Rotation(rng.uniform(0, 6.283), 3, "Z")
        h = size / 2
        vs = [bm.verts.new(c + rot @ Vector(p)) for p in ((-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0))]
        f = bm.faces.new(vs)
        f.material_index = mat
        for loop, q in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[uv].uv = q

    def clump(bm, uv, centre, rx, rz, n, mat, size=(0.9, 1.3)):
        for _ in range(n):
            while True:
                p = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
                if p.length <= 1:
                    break
            card(bm, uv, centre + Vector((p.x * rx, p.y * rx, p.z * rz)), rng.uniform(*size), mat)

    def giant(bm, uv, height, trunk_r, roots, tiers, top, cards):
        """Trunk with buttress roots, branches to canopy clumps. tiers: [(z, count, ring radius, clump radius)]."""
        segs = 7
        tube(bm, uv, [(Vector((rng.uniform(-.04, .04), rng.uniform(-.04, .04), height * k / segs)),
                       trunk_r * (1 - 0.55 * k / segs)) for k in range(segs + 1)], 8, 0)
        for i in range(roots):
            a = 2 * math.pi * (i + rng.uniform(-.2, .2)) / roots
            out = Vector((math.cos(a), math.sin(a), 0))
            limb(bm, uv, out * trunk_r * 0.6 + Vector((0, 0, trunk_r * 2.2)), out * trunk_r * 3 + Vector((0, 0, -0.05)),
                 trunk_r * 0.35, trunk_r * 0.12, 0, sides=4, segs=2)
        clumps = []
        for z, count, ring, cr in tiers:
            for i in range(count):
                a = 2 * math.pi * (i + rng.uniform(-.25, .25)) / count + z
                c = Vector((math.cos(a) * ring, math.sin(a) * ring, z + rng.uniform(-.15, .15)))
                limb(bm, uv, Vector((0, 0, z - 0.45)), c, trunk_r * 0.35, trunk_r * 0.15, 0)
                clumps.append((c, cr))
        clumps.append((Vector((0, 0, top)), tiers[-1][3]))
        per = cards // len(clumps)
        for c, cr in clumps:
            clump(bm, uv, c, cr, cr * 0.35, per, 1)

    def box(bm, uv, lo, hi, mat):
        g = bmesh.ops.create_cube(bm, size=1.0)
        for v in g["verts"]:
            v.co = Vector(lo) + Vector((v.co.x + .5, v.co.y + .5, v.co.z + .5)) * (Vector(hi) - Vector(lo))
        for f in {f for v in g["verts"] for f in v.link_faces}:
            f.material_index = mat

    def dome(bm, uv, centre, r, mat=0):
        g = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=r, calc_uvs=True)
        bmesh.ops.delete(bm, geom=[w for w in g["verts"] if w.co.z < -1e-4], context="VERTS")
        for w in g["verts"]:
            if w.is_valid:
                w.co += Vector(centre)

    def lathe(bm, uv, base, profile, sides, mat, lean=(0, 0)):
        """Surface of revolution: profile [(z, r)] from bottom to top, leaning by (dx, dy) per unit height."""
        tube(bm, uv, [(Vector((base[0] + lean[0] * z, base[1] + lean[1] * z, z)), max(r, 0.01)) for z, r in profile], sides, mat)

    def mushroom(bm, uv, x, y, h, cap):
        lean = (rng.uniform(-.04, .04), rng.uniform(-.04, .04))
        s = cap * 0.16
        lathe(bm, uv, (x, y), [(0, s * 1.6), (0.15 * h, s * 1.1), (0.6 * h, s), (h, s * 0.9)], 9, 0, lean)
        top = (x + lean[0] * h, y + lean[1] * h)
        # cap: underside from the stalk out to the rim, then over the crown (texture v follows the profile)
        lathe(bm, uv, top, [(h - 0.02, s * 0.9), (h + 0.05 * cap, cap * 0.6), (h + 0.02 * cap, cap * 0.97),
                            (h + 0.12 * cap, cap), (h + 0.3 * cap, cap * 0.8), (h + 0.42 * cap, cap * 0.45),
                            (h + 0.47 * cap, 0.02)], 14, 1)

    def bulb_stalk(bm, uv, x, y, h, r):
        lean = (rng.uniform(-.08, .08), rng.uniform(-.08, .08))
        lathe(bm, uv, (x, y), [(0, r * 0.9), (0.1 * h, r * 0.55), (0.55 * h, r * 0.45), (0.72 * h, r * 1.4),
                               (0.84 * h, r * 1.9), (0.95 * h, r * 1.1), (h, 0.02)], 8, 0, lean)

    def frond(bm, uv, a, length, width, curl):
        """Ribbon rising from the ground, arching outward and curling at the tip; built twice with opposite winding
        so both sides render (the map renderer culls back faces)."""
        for back in (False, True):
            ribbon(bm, uv, a, length, width, curl, back)

    def ribbon(bm, uv, a, length, width, curl, back):
        out = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-math.sin(a), math.cos(a), 0))
        segs = 10
        bend = lambda t: (0.15 + curl * t ** 1.6) * math.pi       # 0 = straight up, 1 = curled right over
        c, prev = Vector((0, 0, 0)), None
        for k in range(segs + 1):
            t = k / segs
            if k:
                aj = bend((k - 1) / segs)
                c = c + (out * math.sin(aj) + Vector((0, 0, math.cos(aj)))) * length / segs
            w = width * (1 - 0.85 * t) * (0.6 + 0.4 * math.sin(math.pi * min(t * 1.3, 1)))
            row = [bm.verts.new(c - side * w), bm.verts.new(c + side * w)]
            if back:
                row.reverse()
            if prev:
                f = bm.faces.new((prev[0], prev[1], row[1], row[0]))
                f.material_index = 0
                for loop, q in zip(f.loops, ((0, (k - 1) / segs), (1, (k - 1) / segs), (1, t), (0, t))):
                    loop[uv].uv = q
            prev = row

    def felucia(bm, uv, kind):
        if kind == "fel_mushroom":
            # ~1.7x a vanilla tree: giant, but units (about 2 tall) must stay visible between them
            mushroom(bm, uv, 0, 0, 3.4, 1.6)
            for _ in range(3):
                a, d = rng.uniform(0, 6.283), rng.uniform(0.9, 1.4)
                mushroom(bm, uv, math.cos(a) * d, math.sin(a) * d, rng.uniform(0.8, 1.4), rng.uniform(0.35, 0.6))
        elif kind == "fel_bulbs":
            for i in range(7):
                a, d = rng.uniform(0, 6.283), (0 if i == 0 else rng.uniform(0.35, 1.0))
                bulb_stalk(bm, uv, math.cos(a) * d, math.sin(a) * d, rng.uniform(1.8, 3.4) * (1.2 if i == 0 else 1),
                           rng.uniform(0.12, 0.2))
        elif kind == "fel_pitcher":
            # outside up to the lip, then down the inner wall to the liquid: an open lathe shows nothing from above
            k = 0.6
            lathe(bm, uv, (0, 0), [(z * k, r * k) for z, r in ((0, 0.35), (0.4, 0.9), (1.4, 1.25), (2.4, 0.8), (3.1, 0.55),
                                   (3.6, 0.9), (3.75, 1.25), (3.62, 1.12), (3.4, 0.8), (3.15, 0.5), (3.05, 0.01))], 14, 0)
            for i in range(5):                              # leaves around the foot
                frond(bm, uv, 2 * math.pi * i / 5, 1.0, 0.22, 0.35)
        else:
            for i in range(9):
                frond(bm, uv, 2 * math.pi * (i + rng.uniform(-.3, .3)) / 9, rng.uniform(2.6, 3.6), rng.uniform(0.3, 0.45),
                      rng.uniform(0.35, 0.6))

    def homestead(bm, uv):
        dome(bm, uv, (0, 0, -0.05), 0.45)              # main dome
        dome(bm, uv, (0.75, 0.2, -0.03), 0.22)         # entrance
        dome(bm, uv, (-0.55, 0.55, -0.03), 0.2)
        box(bm, uv, (0.25, -0.12, 0.0), (0.7, 0.12, 0.12), 0)   # corridor to the entrance dome
        vaporator = [(0.0, .05), (.06, .02), (.5, .02), (.52, .04), (.56, .04), (.6, .005)]
        tube(bm, uv, [(Vector((-0.2, -0.75, z)), r) for z, r in vaporator], 6, 0)

    for idx, kind in PROCEDURAL.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        me = bpy.data.meshes.new(kind)
        obj = bpy.data.objects.new(kind, me)
        bpy.context.scene.collection.objects.link(obj)
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new("UVMap")
        if kind == "wroshyr":
            giant(bm, uv, 4.6, 0.32, 5, [(2.6, 3, 1.4, 1.2), (3.5, 3, 1.15, 1.05), (4.4, 3, 0.9, 0.9), (5.2, 2, 0.6, 0.8)],
                  5.7, 700)
            mats = PROC_MATS[idx]
        elif kind == "jungle_giant":
            giant(bm, uv, 2.8, 0.30, 6, [(3.2, 5, 1.5, 1.2), (3.7, 3, 0.8, 1.1)], 4.0, 650)
            mats = PROC_MATS[idx]
        elif kind.startswith("fel_"):
            felucia(bm, uv, kind)
            mats = PROC_MATS[idx]
        else:
            homestead(bm, uv)
            mats = PROC_MATS[idx]
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(bpy.data.materials.new(m))
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if kind not in ("wroshyr", "jungle_giant") and not kind.startswith("fel_"):   # hard-surface props: Blender unwraps
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(island_margin=0.02)
            bpy.ops.object.mode_set(mode="OBJECT")
            for v in me.vertices:
                v.co *= 1.15
        m = obj.modifiers.new("t", "TRIANGULATE")
        bpy.ops.object.modifier_apply(modifier=m.name)
        single_material(obj, idx, [m.name.split(".")[0] for m in me.materials], bie, PDX_SHADER, out_dir)
        uv1 = me.uv_layers.new()
        for d in uv1.data:
            d.uv = (0.0, 0.0)
        name = f"hod_flora_{idx}_{kind}"
        obj.name = me.name = name
        bie.export_meshfile(os.path.join(out_dir, name + ".mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
        zs = [v.co.z for v in me.vertices]
        print(f"{idx} {kind}: {len(me.polygons)} tris, height {max(zs):.2f}")


def wire():
    """gfx/entities/trees.gfx: the vanilla tree entries (the mod file replaces vanilla's) plus ours."""
    van = open(VANILLA_TREES, encoding="utf-8-sig").read().rstrip()
    assert van.endswith("}")
    ours = "\n\t# HOD: Poly Haven (CC0) flora and rocks, WIPGFX/plans & scripts/flora_props.py\n"
    files = {idx: f"hod_flora_{idx}_{pid}" for idx, (pid, *_rest) in ASSETS.items()}
    files.update({idx: f"hod_flora_{idx}_{kind}" for idx, kind in PROCEDURAL.items()})
    files.update({idx: f"hod_flora_{idx}_{name}" for idx, name in EXTERNAL.items()})
    for idx, name in sorted(files.items()):
        ours += (f'\tpdxmesh = {{\n\t\tname = "mapobject_{idx}"\n'
                 f'\t\tfile = "{OUT}/{name}.mesh"\n\t\tscale = 1\n\t}}\n')
    os.makedirs("gfx/entities", exist_ok=True)
    open("gfx/entities/trees.gfx", "w", encoding="utf-8", newline="\n").write(van[:-1] + ours + "}\n")
    print("gfx/entities/trees.gfx:", len(ASSETS), "HOD objects added")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"download": download, "textures": textures, "meshes": meshes, "procedural": procedural, "wire": wire}[args[0]]()
