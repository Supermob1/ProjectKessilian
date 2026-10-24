"""Flatten a SketchUp Collada export (.dae) into a Wavefront .obj + .mtl that Blender imports cleanly.

    python "WIPGFX/plans & scripts/dae_flatten.py" <model.dae> <out.obj>

SketchUp nests geometry through <instance_node> references into <library_nodes>, which Blender's Collada importer
leaves unlinked (it creates the meshes but no objects). This walks the visual scene, follows instance_node and
instance_geometry with their accumulated matrices, and writes every triangle in world space (inches, Z up, as the
.dae says) with its UVs and material. Lines / polylists other than triangles are skipped.
"""
import os, sys
import xml.etree.ElementTree as ET
import numpy as np


def main(src, out):
    root = ET.parse(src).getroot()
    ns = {"c": root.tag[1:root.tag.index("}")]}
    q = lambda tag: f"{{{ns['c']}}}{tag}"
    byid = {e.get("id"): e for e in root.iter() if e.get("id")}
    # materials -> image file
    images = {i.get("id"): i.find("c:init_from", ns).text for i in root.iter(q("image")) if i.find("c:init_from", ns) is not None}
    effect_img = {}
    for eff in root.iter(q("effect")):
        params = {p.get("sid"): p for p in eff.iter(q("newparam"))}
        for tex in eff.iter(q("texture")):
            ref = tex.get("texture")
            if ref in params and params[ref].find(".//c:source", ns) is not None:      # sampler -> surface
                ref = params[ref].find(".//c:source", ns).text
            if ref in params and params[ref].find(".//c:init_from", ns) is not None:   # surface -> image
                ref = params[ref].find(".//c:init_from", ns).text
            effect_img[eff.get("id")] = images.get(ref, ref)
    mat_img = {}
    for m in root.iter(q("material")):
        ie = m.find("c:instance_effect", ns)
        if ie is not None:
            mat_img[m.get("id")] = effect_img.get(ie.get("url")[1:])
    colours = {}
    for m in root.iter(q("material")):
        ie = m.find("c:instance_effect", ns)
        eff = byid.get(ie.get("url")[1:]) if ie is not None else None
        col = eff.find(".//c:diffuse/c:color", ns) if eff is not None else None
        colours[m.get("id")] = [float(x) for x in col.text.split()[:3]] if col is not None else [0.8, 0.8, 0.8]

    def matrix(node):
        m = np.eye(4)
        for e in node:
            if e.tag == q("matrix"):
                m = m @ np.array([float(x) for x in e.text.split()]).reshape(4, 4)
            elif e.tag == q("translate"):
                t = np.eye(4); t[:3, 3] = [float(x) for x in e.text.split()]; m = m @ t
            elif e.tag == q("scale"):
                m = m @ np.diag([float(x) for x in e.text.split()] + [1.0])
        return m

    verts, uvs, faces = [], [], []          # faces: (material, [(v, vt)] * 3)

    def emit(geom, M, bind):
        mesh = geom.find("c:mesh", ns)
        if mesh is None:
            return
        src = {s.get("id"): np.array([float(x) for x in s.find("c:float_array", ns).text.split()]).reshape(-1, int(s.find(".//c:accessor", ns).get("stride")))
               for s in mesh.findall("c:source", ns) if s.find("c:float_array", ns) is not None and s.find("c:float_array", ns).text}
        vmap = {v.get("id"): v.find("c:input[@semantic='POSITION']", ns).get("source")[1:] for v in mesh.findall("c:vertices", ns)}
        for tri in mesh.findall("c:triangles", ns):
            inputs = tri.findall("c:input", ns)
            stride = max(int(i.get("offset")) for i in inputs) + 1
            pos = uv = None
            for i in inputs:
                s = i.get("source")[1:]
                if i.get("semantic") == "VERTEX":
                    pos = (int(i.get("offset")), src[vmap.get(s, s)])
                elif i.get("semantic") == "TEXCOORD" and uv is None:
                    uv = (int(i.get("offset")), src[s])
            p = tri.find("c:p", ns)
            if p is None or not p.text:
                continue
            idx = np.array(p.text.split(), int).reshape(-1, stride)
            base_v, base_t = len(verts), len(uvs)
            P = pos[1][:, :3]
            W = (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]
            verts.extend(W.tolist())
            if uv is not None:
                uvs.extend(uv[1][:, :2].tolist())
            mat = bind.get(tri.get("material"), tri.get("material"))
            for k in range(0, len(idx), 3):
                faces.append((mat, [(base_v + idx[k + j, pos[0]], (base_t + idx[k + j, uv[0]]) if uv else None) for j in range(3)]))

    def walk(node, M):
        M = M @ matrix(node)
        for ig in node.findall("c:instance_geometry", ns):
            bind = {im.get("symbol"): im.get("target")[1:] for im in ig.iter(q("instance_material"))}
            emit(byid[ig.get("url")[1:]], M, bind)
        for inode in node.findall("c:instance_node", ns):
            walk(byid[inode.get("url")[1:]], M)
        for child in node.findall("c:node", ns):
            walk(child, M)

    scene = root.find(".//c:instance_visual_scene", ns).get("url")[1:]
    for n in byid[scene].findall("c:node", ns):
        walk(n, np.eye(4))
    # SketchUp exports often hold the same face many times (components nested in components): exact copies z-fight.
    # Keep one per position + winding; opposite windings stay (two-sided cloth and quills, culled per side in game)
    seen, kept = set(), []
    for m, tri in faces:
        p = [tuple(np.round(verts[v], 4)) for v, _t in tri]
        k = min(range(3), key=lambda i: p[i])
        key = tuple(p[k:] + p[:k])                          # rotation keeps the winding
        if key not in seen:
            seen.add(key)
            kept.append((m, tri))
    print(f"{len(faces) - len(kept)} duplicate triangles dropped")
    faces = kept
    folder = os.path.dirname(os.path.abspath(src))
    mtl = os.path.splitext(out)[0] + ".mtl"
    with open(mtl, "w") as f:
        for m in sorted({m for m, _ in faces}):
            f.write(f"newmtl {m}\nKd {' '.join(f'{c:.3f}' for c in colours.get(m, [0.8] * 3))}\n")
            if mat_img.get(m):
                f.write(f"map_Kd {os.path.join(folder, mat_img[m]).replace(os.sep, '/')}\n")
    with open(out, "w") as f:
        f.write(f"mtllib {os.path.basename(mtl)}\n")
        f.writelines(f"v {x:.5f} {y:.5f} {z:.5f}\n" for x, y, z in verts)
        f.writelines(f"vt {u:.5f} {v:.5f}\n" for u, v in uvs)
        cur = None
        for m, tri in faces:
            if m != cur:
                f.write(f"usemtl {m}\n")
                cur = m
            f.write("f " + " ".join(f"{v + 1}/{t + 1}" if t is not None else f"{v + 1}" for v, t in tri) + "\n")
    print(f"{len(faces)} triangles, {len(verts)} vertices, materials {sorted({m for m, _ in faces})}, textures {sorted(set(filter(None, mat_img.values())))}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
