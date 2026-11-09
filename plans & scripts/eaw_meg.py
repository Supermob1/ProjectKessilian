"""EaW MEG v1 archive reader (vanilla Empire at War / Forces of Corruption models.meg, textures.meg, Patch.meg):
    python -I -B "plans & scripts/eaw_meg.py" list FILE.meg [regex] | extract FILE.meg OUTDIR regex"""
import os, re, struct, sys
def entries(p):
    f = open(p, "rb"); nn, nf = struct.unpack("<2I", f.read(8))
    names = []
    for _ in range(nn):
        (l,) = struct.unpack("<H", f.read(2)); names.append(f.read(l).decode("latin-1"))
    for _ in range(nf):
        crc, idx, size, start, ni = struct.unpack("<5I", f.read(20)); yield names[ni], start, size
cmd, p = sys.argv[1], sys.argv[2]
rx = re.compile(sys.argv[-1], re.I) if len(sys.argv) > 3 else None
if cmd == "list":
    for n, s, z in entries(p):
        if not rx or rx.search(n): print(n, z)
else:
    out = sys.argv[3]; f = open(p, "rb")
    for n, s, z in entries(p):
        if rx.search(n):
            d = os.path.join(out, n.replace("\\", "/")); os.makedirs(os.path.dirname(d), exist_ok=True)
            f.seek(s); open(d, "wb").write(f.read(z)); print(d)
