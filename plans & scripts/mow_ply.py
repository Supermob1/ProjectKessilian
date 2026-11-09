"""Men of War: Assault Squad 2 (GEM engine) model -> OBJ + PNG, read straight from a mod's .pak (zip) (2026-11-09, ASV Star Wars).

    python -P -B "plans & scripts/mow_ply.py" PAK.pak "folder/inside/pak/" OUT_DIR NAME [TEXTURE.pak ...]

The folder holds <name>.mdl (text skeleton: bones with Position / Orientation / Matrix34 and {VolumeView "part.ply"}),
EPLY meshes and .mtl / .dds. Every visible part is placed by its bone chain (rest pose); glow / shadow cards are skipped.
EPLY: "EPLY" BNDS(24) MESH(flags, first face, face count, ..., pascal "x.mtl")* VERT(n, stride, flags: pos3 normal3 uv2 ...)
INDX(n, uint16). GEM is Z-up; the OBJ keeps Z-up.
"""
import io, os, re, struct, sys, zipfile
import numpy as np

SKIP = re.compile(r"glow|shadow|light|flash|shield|belt", re.I)


def parse_mdl(t):
    """-> [(ply name, 3x3 R, T)] world transforms, row vectors: p_world = p @ R + T; and {bone name: (R, T)}."""
    out, world = [], {}
    tok = re.finditer(r'\{bone(?:\s+\w+)?\s+"([^"]+)"|\{Position\s+([-\d.e\s]+)\}|\{Orientation\s+([-\d.e\s]+)\}|'
                      r'\{Matrix34\s+([-\d.e\s]+)\}|\{VolumeView\s+"([^"]+)"|(\{)|(\})', t)
    depth, bones = 0, []          # bones: [depth, R, T, local R, local T]
    for m in tok:
        name, pos, ori, mat, view, ob, cb = m.groups()
        if name is not None:
            depth += 1
            bones.append([depth, np.eye(3), np.zeros(3), name])
        elif ob:
            depth += 1
        elif cb:
            if bones and bones[-1][0] == depth:
                world[bones[-1][3]] = chain(bones)
                bones.pop()
            depth -= 1
        elif bones and (pos or ori or mat):
            v = [float(x) for x in (pos or ori or mat).split()]
            if pos:
                bones[-1][2] = np.array(v[:3])
            elif ori:
                bones[-1][1] = np.array(v[:9]).reshape(3, 3)
            else:
                bones[-1][1], bones[-1][2] = np.array(v[:9]).reshape(3, 3), np.array(v[9:12])
        elif view:
            depth += 1                 # {VolumeView ...} closes with its own }
            if not bones:
                continue
            out.append((view, *chain(bones)))
    return out, world


def chain(bones):
    R, T = np.eye(3), np.zeros(3)
    for _, r, p, _ in bones:           # root first: world = local @ parent
        R, T = r @ R, p @ R + T
    return R, T


def read_ply(b):
    assert b[:4] == b"EPLY", "not an EPLY mesh"
    meshes = []
    for m in re.finditer(rb"MESH", b):
        _, first, count = struct.unpack_from("<3I", b, m.end())
        e = b.find(b".mtl", m.end() + 12)          # pascal string: length byte, then the name (may hold '#')
        s = next((s for s in range(e - 1, max(e - 128, 0), -1) if b[s] == e + 4 - s - 1), None) if e > 0 else None
        meshes.append((first, count, b[s + 1:e + 4].decode("latin-1") if s is not None else None))
    i = b.find(b"VERT")
    n, stride, _ = struct.unpack_from("<IHH", b, i + 4)
    raw = np.frombuffer(b, np.uint8, n * stride, i + 12).reshape(n, stride)
    pos = raw[:, 0:12].copy().view("<f4").reshape(n, 3)
    # vertex layouts by stride: 32/48 pos normal uv (+tangent); 36 pos normal colour uv; 40/44/56 pos weight bone-index normal uv
    o = {32: 24, 36: 28, 40: 32, 44: 36, 48: 24, 56: 32}[stride]
    uv = raw[:, o:o + 8].copy().view("<f4").reshape(n, 2)
    a = b.find(b"SKIN", 0, i)          # skinned part: bone names; each vertex's first bone index (1-based) at byte 16
    skin = None
    if a > 0:
        k, at, names = struct.unpack_from("<I", b, a + 4)[0], a + 8, []
        for _ in range(k):
            names.append(b[at + 1:at + 1 + b[at]].decode("latin-1")); at += 1 + b[at]
        skin = [names[j - 1] if 0 < j <= k else None for j in raw[:, 16]]   # shortcut: first bone only, full weight
    j = b.find(b"INDX", i + 12 + n * stride)
    k = struct.unpack_from("<I", b, j + 4)[0]
    idx = np.frombuffer(b, "<u2", k, j + 8).reshape(-1, 3)
    return pos, uv, idx, meshes, skin


_TEX = {}


def tex_index(paks):
    """basename (no extension) -> [(zip, path)] over the mod's texture paks (GEM looks textures up by bare name)."""
    for p in paks:
        tz = zipfile.ZipFile(p)
        for x in tz.namelist():
            if x.lower().endswith((".dds", ".tga")):
                _TEX.setdefault(os.path.splitext(os.path.basename(x))[0].lower(), []).append((tz, x))


def convert(pak, folder, out, name=None, *tex_paks):
    if tex_paks and not _TEX:
        tex_index(tex_paks)
    z = zipfile.ZipFile(pak)
    key = folder.rstrip("/").split("/")[-1].lower()
    files = {os.path.basename(x).lower(): x for x in z.namelist() if x.startswith(folder) and not x.endswith("/")}
    mdl = next(v for k, v in files.items() if k.endswith(".mdl"))
    name = name or os.path.splitext(os.path.basename(mdl))[0]
    os.makedirs(out, exist_ok=True)
    parts, world = parse_mdl(z.read(mdl).decode("latin-1"))
    V, T, F, mats, base = [], [], [], {}, 0
    for view, R, Tr in parts:
        if SKIP.search(view) or view.lower() not in files:
            continue
        pos, uv, idx, meshes, skin = read_ply(z.read(files[view.lower()]))
        V.append(pos @ R + Tr)         # shortcut: skinned parts (SKIN) placed rigidly on their own bone; their rest-space
                                       # is not the skin bones' (tested 2026-11-09), fine for all but cloth-like belts (SKIP)
        T.append(uv)
        for first, count, mtl in meshes or [(0, len(idx), None)]:
            tex = None
            if mtl and mtl.lower() in files:
                d = re.search(r'\{diffuse\s+"([^"]+)"', z.read(files[mtl.lower()]).decode("latin-1"))
                b = d and os.path.basename(d.group(1)).lower()
                own = next((b + e for e in (".dds", ".tga") if b and b + e in files), None)
                if own:
                    tex = (z, files[own])
                elif b in _TEX:   # shortcut: same-name textures elsewhere -> the one whose path names this model, else the first
                    tex = max(_TEX[b], key=lambda c: (key in c[1].lower(), any(w in c[1].lower() for w in key.split("_") if len(w) > 2)))
            mats.setdefault(tex, len(mats))
            F.append((mats[tex], idx[first:first + count].astype(np.int64) + base))
        base += len(pos)
    assert F, "no visible parts in " + mdl
    V, T = np.concatenate(V), np.concatenate(T)
    from PIL import Image
    mtl_lines, mat_name = [], {}
    for tex, k in mats.items():
        mtl_lines.append(f"newmtl m{k}")
        if tex:
            png = f"{name}_{k}.png"
            Image.open(io.BytesIO(tex[0].read(tex[1]))).convert("RGBA").save(os.path.join(out, png))
            mtl_lines.append(f"map_Kd {png}")
    lines = [f"mtllib {name}.mtl"] + [f"v {x:.4f} {y:.4f} {z_:.4f}" for x, y, z_ in V] + [f"vt {u:.5f} {1 - v:.5f}" for u, v in T]
    for k, tris in F:
        lines.append(f"usemtl m{k}")
        lines += [f"f {a + 1}/{a + 1} {b + 1}/{b + 1} {c + 1}/{c + 1}" for a, b, c in tris]
    open(os.path.join(out, name + ".mtl"), "w").write("\n".join(mtl_lines) + "\n")
    open(os.path.join(out, name + ".obj"), "w").write("\n".join(lines) + "\n")
    print(name, len(V), "verts", sum(len(t) for _, t in F), "tris", len(mats), "materials", "size", np.ptp(V, 0).round(1))


def check_winding(pak, folder):
    """self-check: after the bone transforms (most are mirrored, det -1) faces wind counter-clockwise against the normals"""
    z = zipfile.ZipFile(pak)
    mdl = next(x for x in z.namelist() if x.startswith(folder) and x.endswith(".mdl"))
    ok = tot = 0
    for view, R, _ in parse_mdl(z.read(mdl).decode("latin-1"))[0]:
        x = folder + view
        if x not in z.namelist():
            continue
        b = z.read(x); i = b.find(b"VERT"); n, s, _ = struct.unpack_from("<IHH", b, i + 4)
        if s not in (32, 48):
            continue
        nrm = np.frombuffer(b, np.uint8, n * s, i + 12).reshape(n, s)[:, 12:24].copy().view("<f4").reshape(n, 3) @ R
        pos, _, idx, _, _ = read_ply(b)
        p = pos @ R
        d = (np.cross(p[idx[:, 1]] - p[idx[:, 0]], p[idx[:, 2]] - p[idx[:, 0]]) * nrm[idx].sum(1)).sum(1)
        ok += (d > 0).sum(); tot += len(d)
    assert tot and ok / tot > 0.9, f"world winding disagrees with the normals ({ok}/{tot})"
    return ok / tot


if __name__ == "__main__":
    convert(*sys.argv[1:])
