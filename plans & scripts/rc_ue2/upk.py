"""Minimal Unreal Engine 2 package reader (Republic Commando): header, names, imports, exports."""
import struct, sys
class Pkg:
    def __init__(s, path):
        s.b = b = open(path, "rb").read()
        tag, s.ver, s.lic, flags, nn, no, ne, eo, ni, io = struct.unpack_from("<IHHIIIIIII", b, 0)
        assert tag == 0x9E2A83C1, hex(tag)
        s.o = no; s.names = []
        for _ in range(nn):
            if s.ver >= 64:
                l = s.ci(); s.names.append(b[s.o:s.o + l - 1].decode("latin-1")); s.o += l
            else:
                e = b.index(b"\0", s.o); s.names.append(b[s.o:e].decode("latin-1")); s.o = e + 1
            s.o += 4
        s.o = io; s.imports = []
        for _ in range(ni):
            cp, cn = s.ci(), s.ci(); pk = struct.unpack_from("<i", b, s.o)[0]; s.o += 4; on = s.ci()
            s.imports.append((s.names[cn], s.names[on], pk))
        s.o = eo; s.exports = []
        for _ in range(ne):
            cls, sup = s.ci(), s.ci(); pk = struct.unpack_from("<i", b, s.o)[0]; s.o += 4
            if s.ver >= 159: s.o += 1   # RC v159: one extra byte before the name
            name = s.ci(); fl = struct.unpack_from("<I", b, s.o)[0]; s.o += 4; size = struct.unpack_from("<i", b, s.o)[0]; s.o += 4   # Republic Commando (v158): plain int32 size / offset
            off = 0
            if size > 0: off = struct.unpack_from("<i", b, s.o)[0]; s.o += 4
            s.exports.append(dict(cls=s.objname(cls), name=s.names[name], size=size, off=off, pkg=pk))
    def ci(s):   # compact index
        b = s.b; x = b[s.o]; s.o += 1; neg = x & 0x80; v = x & 0x3F
        if x & 0x40:
            sh = 6
            while True:
                x = b[s.o]; s.o += 1; v |= (x & 0x7F) << sh; sh += 7
                if not x & 0x80: break
        return -v if neg else v
    def objname(s, i):
        if i < 0: return s.imports[-i - 1][1] if -i - 1 < len(s.imports) else "?"
        if i > 0: return "export:%d" % (i - 1)
        return "Class"
if __name__ == "__main__":
    p = Pkg(sys.argv[1]); print("ver", p.ver, "lic", p.lic, "names", len(p.names), "exports", len(p.exports))
    for e in p.exports:
        if len(sys.argv) < 3 or sys.argv[2].lower() in (e["cls"] + e["name"]).lower(): print(e["cls"], e["name"], e["size"], e["off"])


def props(p, off):
    """tagged properties -> (dict name -> raw bytes / int, end offset)"""
    import struct as st
    p.o = off; out = {}
    while True:
        n = p.names[p.ci()]
        if n == "None": return out, p.o
        info = p.b[p.o]; p.o += 1; t = info & 0x0F; sz = (info >> 4) & 7; arr = info & 0x80
        if t == 10: p.ci()                          # struct name
        size = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}.get(sz)
        if size is None:
            fmt = {5: "<B", 6: "<H", 7: "<I"}[sz]; size = st.unpack_from(fmt, p.b, p.o)[0]; p.o += st.calcsize(fmt)
        if arr and t != 3:
            x = p.b[p.o]; p.o += 1
            if x & 0x80: p.o += 1 if not x & 0x40 else 3
        if t == 3: out[n] = bool(arr); continue
        out[n] = p.b[p.o:p.o + size]; p.o += size
