"""Source engine (Garry's Mod) static model -> OBJ + PNG textures, for unit_models.py (2026-11-09, GMod workshop models).

    python -B "plans & scripts/source_mdl_to_obj.py" MODEL.mdl MATERIALS_DIR OUT_DIR

Reads MDL (body parts / meshes / materials), VVD (vertices, LOD 0 with fixups) and VTX (.dx90.vtx strips, LOD 0) and
VTF ($basetexture of each material, DXT1/3/5 or uncompressed). Static props only: skinned vertices are written in
their bind pose. Source is Z-up in inches; the OBJ keeps Z-up (import with forward/up set in Blender).
"""
import os, re, struct, sys


def u(fmt, b, o):
    return struct.unpack_from("<" + fmt, b, o)


def cstr(b, o):
    return b[o:b.index(b"\0", o)].decode("latin-1")


def read_vvd(b):
    assert b[:4] == b"IDSV"
    _, _, nlods = u("3i", b, 4)
    nverts0 = u("i", b, 16)[0]
    nfix, fixstart, vstart = u("3i", b, 48)
    raw = [u("8f", b, vstart + i * 48 + 16) for i in range(sum(1 for _ in range(nverts0)))]   # pos3 normal3 uv2
    if nfix:   # LOD 0 order from the fixup table
        out = []
        for k in range(nfix):
            lod, src, n = u("3i", b, fixstart + k * 12)
            if lod >= 0:
                out += [u("8f", b, vstart + (src + j) * 48 + 16) for j in range(n)]
        raw = out
    return raw


def read_mdl(b):
    assert b[:4] == b"IDST", "not a Source MDL"
    ntex, texidx = u("2i", b, 204)
    textures = [cstr(b, texidx + i * 64 + u("i", b, texidx + i * 64)[0]) for i in range(ntex)]
    ncd, cdidx = u("2i", b, 212)
    cdirs = [cstr(b, u("i", b, cdidx + i * 4)[0]) for i in range(ncd)]
    nbp, bpidx = u("2i", b, 232)
    parts = []
    for p in range(nbp):
        bo = bpidx + p * 16
        _, nmodels, _, modelidx = u("4i", b, bo)
        models = []
        for m in range(nmodels):
            mo = bo + modelidx + m * 148
            nmesh, meshidx, _, vertidx = u("4i", b, mo + 72)
            meshes = []
            for k in range(nmesh):
                so = mo + meshidx + k * 116
                material, _, nverts, voff = u("4i", b, so)
                meshes.append((material, voff))
            models.append((vertidx // 48, meshes))
        parts.append(models)
    return textures, cdirs, parts


def read_vtx(b):
    """-> [bodypart][model][mesh] = list of (origMeshVertID triangles)"""
    nlods, _, nbp, bpoff = u("4i", b, 20)
    parts = []
    for p in range(nbp):
        bo = bpoff + p * 8
        nmodels, moff = u("2i", b, bo)
        models = []
        for m in range(nmodels):
            mo = bo + moff + m * 8
            _, lodoff = u("2i", b, mo)
            lo = mo + lodoff                       # LOD 0
            nmesh, meshoff = u("2i", b, lo)
            meshes = []
            for k in range(nmesh):
                so = lo + meshoff + k * 9
                nsg, sgoff = u("2i", b, so)
                tris = []
                for g in range(nsg):
                    go = so + sgoff + g * 25
                    nv, voff, ni, ioff = u("4i", b, go)
                    verts = [u("H", b, go + voff + i * 9 + 4)[0] for i in range(nv)]
                    idx = u("%dH" % ni, b, go + ioff)
                    tris += [(verts[idx[i]], verts[idx[i + 1]], verts[idx[i + 2]]) for i in range(0, ni - 2, 3)]
                meshes.append(tris)
            models.append(meshes)
        parts.append(models)
    return parts


def vtf_to_png(src, dst):
    from PIL import Image
    b = open(src, "rb").read()
    assert b[:4] == b"VTF\0"
    w, h = u("2H", b, 16)
    fmt = u("i", b, 52)[0]
    if fmt in (13, 14, 15):        # DXT1 / DXT3 / DXT5: largest mip is the last block of the file
        block = 8 if fmt == 13 else 16
        size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block
        four = {13: b"DXT1", 14: b"DXT3", 15: b"DXT5"}[fmt]
        hdr = struct.pack("<4s7I44x2I4s20x5I", b"DDS ", 124, 0x1007 | 0x80000, h, w, size, 0, 1, 32, 4, four, 0x1000, 0, 0, 0, 0)
        assert len(hdr) == 128
        Image.open(__import__("io").BytesIO(hdr + b[-size:])).convert("RGBA").save(dst)
    elif fmt in (0, 2, 3, 12):     # RGBA8888, RGB888, BGR888, BGRA8888
        bpp = 4 if fmt in (0, 12) else 3
        data = b[-w * h * bpp:]
        mode = {0: "RGBA", 2: "RGB", 3: "BGR", 12: "BGRA"}[fmt]
        Image.frombytes("RGBA" if bpp == 4 else "RGB", (w, h), data, "raw", mode).save(dst)
    else:
        raise ValueError(f"VTF format {fmt} not handled: {src}")


def convert(mdl, matdir, out):
    os.makedirs(out, exist_ok=True)
    stem = os.path.splitext(mdl)[0]
    textures, cdirs, mparts = read_mdl(open(mdl, "rb").read())
    verts = read_vvd(open(stem + ".vvd", "rb").read())
    vparts = read_vtx(open(stem + ".dx90.vtx", "rb").read())
    name = os.path.basename(stem)
    mtl, obj = [], [f"mtllib {name}.mtl"]
    for i, t in enumerate(textures):           # material -> $basetexture -> VTF -> PNG
        vmt = next((os.path.join(matdir, d, t + ".vmt") for d in cdirs if os.path.exists(os.path.join(matdir, d, t + ".vmt"))), None)
        mtl.append(f"newmtl m{i}")
        if vmt:
            base = re.search(r'"?\$basetexture"?\s+"?([^"\s]+)', open(vmt, encoding="latin-1").read(), re.I)
            vtf = os.path.join(matdir, base.group(1).replace("\\", "/") + ".vtf") if base else None
            if vtf and os.path.exists(vtf):
                png = f"{name}_{i}.png"
                vtf_to_png(vtf, os.path.join(out, png))
                mtl.append(f"map_Kd {png}")
    for x, y, z, nx, ny, nz, s, t in verts:
        obj.append(f"v {x:.5f} {y:.5f} {z:.5f}")
    for x, y, z, nx, ny, nz, s, t in verts:
        obj.append(f"vt {s:.6f} {1 - t:.6f}")
    for x, y, z, nx, ny, nz, s, t in verts:
        obj.append(f"vn {nx:.5f} {ny:.5f} {nz:.5f}")
    nt = 0
    for p, models in enumerate(mparts):
        for m, (vstart, meshes) in enumerate(models):
            for k, (material, voff) in enumerate(meshes):
                obj.append(f"usemtl m{material}")
                for tri in vparts[p][m][k]:
                    a, b_, c = (vstart + voff + i + 1 for i in tri)
                    obj.append(f"f {a}/{a}/{a} {c}/{c}/{c} {b_}/{b_}/{b_}")   # Source winding is clockwise
                    nt += 1
    open(os.path.join(out, name + ".mtl"), "w").write("\n".join(mtl) + "\n")
    open(os.path.join(out, name + ".obj"), "w").write("\n".join(obj) + "\n")
    assert nt and len(verts), "empty model"
    print(name, len(verts), "verts", nt, "tris", len(textures), "materials")


if __name__ == "__main__":
    convert(*sys.argv[1:4])
