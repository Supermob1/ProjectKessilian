"""Republic Commando SkeletalMesh (UE2 v158) -> OBJ: faces / wedges / materials / Points2 (bind pose, static)."""
import struct, sys, math
sys.path.insert(0, __import__("os").path.dirname(__file__)); import upk
def arr(p, size):
    n = p.ci(); o = p.o; p.o += n * size; return n, o
def mesh(p, name):
    e = next(e for e in p.exports if e["name"] == name and e["cls"] == "SkeletalMesh")
    _, o = upk.props(p, e["off"]); b = p.b
    bb = struct.unpack_from("<6f", b, o); p.o = o + 25 + 16
    ver, nvert = struct.unpack_from("<ii", b, p.o); p.o += 8
    arr(p, 4)                                    # Verts (unused for skeletal)
    ntex = p.ci(); tex = [p.objname(p.ci()) for _ in range(ntex)]
    p.o += 12 + 12 + 12                          # scale, origin, rot origin
    arr(p, 2)                                    # FaceLevel
    nf, fo = arr(p, 8); faces = [struct.unpack_from("<4H", b, fo + i * 8) for i in range(nf)]
    arr(p, 2)                                    # CollapseWedgeThus
    nw, wo = arr(p, 10); wedges = [struct.unpack_from("<Hff", b, wo + i * 10) for i in range(nw)]
    nm, mo = arr(p, 8); mats = [struct.unpack_from("<Ii", b, mo + i * 8) for i in range(nm)]
    # Points2: first TArray<FVector> of nvert points inside the bounding box after the LOD fields
    lo, hi = bb[:3], bb[3:]
    end = e["off"] + e["size"]
    for o in range(p.o, end - 12):
        p.o = o; n = p.ci()
        if n != nvert: continue
        pts = struct.unpack_from("<%df" % (3 * n), b, p.o)
        if all(lo[i % 3] - 1 <= v <= hi[i % 3] + 1 for i, v in enumerate(pts)):
            pts = [pts[i:i + 3] for i in range(0, 3 * n, 3)]; break
    else:
        raise SystemExit("Points2 not found")
    return dict(ver=ver, nvert=nvert, tex=tex, faces=faces, wedges=wedges, mats=mats, pts=pts, bb=bb, pts_off=o)
def obj(m, out, stem):
    L = [f"mtllib {stem}.mtl"]
    for x, y, z in m["pts"]: L.append(f"v {x:.4f} {y:.4f} {z:.4f}")
    for _, u, v in m["wedges"]: L.append(f"vt {u:.6f} {1 - v:.6f}")
    cur = None
    for a, b_, c, mi in m["faces"]:
        if mi != cur: L.append(f"usemtl m{m['mats'][mi][1] if mi < len(m['mats']) else 0}"); cur = mi
        w = m["wedges"]
        L.append("f " + " ".join(f"{w[i][0] + 1}/{i + 1}" for i in (a, c, b_)))
    open(f"{out}/{stem}.obj", "w").write("\n".join(L) + "\n")
if __name__ == "__main__":
    p = upk.Pkg(sys.argv[1]); m = mesh(p, sys.argv[2])
    print("ver", m["ver"], "verts", m["nvert"], "faces", len(m["faces"]), "wedges", len(m["wedges"]), "mats", m["mats"], "tex", m["tex"], "pts@", m["pts_off"])
    assert max(w[0] for w in m["wedges"]) < m["nvert"] and max(max(f[:3]) for f in m["faces"]) < len(m["wedges"])
    if len(sys.argv) > 3: obj(m, sys.argv[3], sys.argv[2])
