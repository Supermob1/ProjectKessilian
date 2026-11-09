"""Republic Commando SkeletalMesh (UE2 v158/159) -> OBJ + PNG (bind pose, LOD0, static).
   python -I -B "plans & scripts/rc_ue2/rc_export.py" GameData/Animations/X.ukx MESH GameData/Textures/Y.utx TEXTURE OUTDIR
   then Blender obj -> glb (Z-up, nose +X => SPECS yaw=90). Example: Droid.ukx DwarfSpiderDroid / DroidTextures.utx DwarfSpiderDroid = A-DSD."""
import struct, sys, math, io, os
sys.path.insert(0, os.path.dirname(__file__)); import upk, skel
ukx, mname, utx, tname, out = sys.argv[1:6]
p = upk.Pkg(ukx); m = skel.mesh(p, mname); b = p.b; nv = m["nvert"]
e = next(e for e in p.exports if e["name"] == mname and e["cls"] == "SkeletalMesh"); end = e["off"] + e["size"]
best = None
for o in range(m["pts_off"], end - 4):          # first wedge array directly followed by a face array that indexes it
    p.o = o; n = p.ci(); s = p.o
    if n < 100 or s + n * 10 > end: continue
    W = [struct.unpack_from("<Hff", b, s + i * 10) for i in range(n)]
    if not all(w[0] < nv and math.isfinite(w[1]) and -8 < w[1] < 8 and -8 < w[2] < 8 for w in W): continue
    for gap in range(0, 17):                    # RC puts a few bytes between the wedge and face arrays
        p.o = s + n * 10 + gap; nf = p.ci(); fs = p.o
        if nf < 100 or fs + nf * 8 > end: continue
        F = [struct.unpack_from("<4H", b, fs + i * 8) for i in range(nf)]
        if max(max(f[:3]) for f in F) == n - 1 and all(f[3] < 16 for f in F):
            best = (W, F); break
    if best: break
assert best, "no LOD0 wedges/faces"
W, F = best
need = max(w[0] for w in W) + 1; lo, hi = m["bb"][:3], m["bb"][3:]
for o in range(fs, end - 12):                     # LOD0 points: TArray<FVector> sized max(iVertex)+1, after the faces
    p.o = o; n = p.ci()
    if n != need: continue
    pts = struct.unpack_from("<%df" % (3 * n), b, p.o)
    if all(lo[i % 3] - 1 <= v <= hi[i % 3] + 1 for i, v in enumerate(pts)):
        m["pts"] = [pts[i:i + 3] for i in range(0, 3 * n, 3)]; nv = n; break
else:
    raise SystemExit("LOD0 points not found")
os.makedirs(out, exist_ok=True)
L = [f"mtllib {mname}.mtl", "usemtl m0"] + [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in m["pts"]] + [f"vt {u:.6f} {1 - v:.6f}" for _, u, v in W]
L += ["f " + " ".join(f"{W[i][0] + 1}/{i + 1}" for i in (a, c, bb)) for a, bb, c, _ in F]
open(f"{out}/{mname}.obj", "w").write("\n".join(L) + "\n")
open(f"{out}/{mname}.mtl", "w").write(f"newmtl m0\nmap_Kd {mname}.png\n")
# texture: props then mips; largest mip = first
t = upk.Pkg(utx); te = next(x for x in t.exports if x["name"] == tname and x["cls"] == "Texture")
pr, o = upk.props(t, te["off"]); fmt = pr["Format"][0]; w = struct.unpack("<i", pr["USize"])[0]; h = struct.unpack("<i", pr["VSize"])[0]
t.o = o; t.ci(); t.o += 4; size = t.ci(); data = t.b[t.o:t.o + size]
from PIL import Image
four = {3: b"DXT1", 7: b"DXT3", 8: b"DXT5"}.get(fmt)
if four:
    hdr = struct.pack("<4s7I44x2I4s20x5I", b"DDS ", 124, 0x1007 | 0x80000, h, w, size, 0, 1, 32, 4, four, 0x1000, 0, 0, 0, 0)
    img = Image.open(io.BytesIO(hdr + data))
elif fmt == 5: img = Image.frombytes("RGBA", (w, h), data, "raw", "BGRA")
else: raise SystemExit(f"texture format {fmt}")
img.convert("RGBA").save(f"{out}/{mname}.png")
print(mname, "verts", nv, "wedges", len(W), "faces", len(F), "tex", w, h, "fmt", fmt)
