"""Reader for Star Wars Battlefront II (ZeroEngine) .msh models: models, transforms, geometry segments, skin weights.

    python "WIPGFX/plans & scripts/swbf_msh.py" <file.msh>      dump the structure
"""
import struct, sys


def chunks(b, i, end):
    while i + 8 <= end:
        tag = b[i:i + 4].decode("latin1")
        size = struct.unpack_from("<I", b, i + 4)[0]
        yield tag, i + 8, i + 8 + size
        i += 8 + size   # no padding: sizes already include it (and this exporter writes odd sizes)


def cstr(b, i, j):
    return b[i:j].split(b"\0")[0].decode("latin1")


def read(path):
    """-> dict(materials=[(name, [textures])], models=[dict(name, parent, index, type, hidden, tran, segments)])"""
    b = open(path, "rb").read()
    out = dict(materials=[], models=[])
    def walk(i, end):
        for tag, s, e in chunks(b, i, end):
            if tag in ("HEDR", "MSH2"):
                walk(s, e)
            elif tag == "MATL":
                for t2, s2, e2 in chunks(b, s + 4, e):
                    if t2 == "MATD":
                        name, tex = "", []
                        for t3, s3, e3 in chunks(b, s2, e2):
                            if t3 == "NAME":
                                name = cstr(b, s3, e3)
                            elif t3.startswith("TX") and t3.endswith("D"):
                                tex.append(cstr(b, s3, e3))
                        out["materials"].append((name, tex))
            elif tag == "MODL":
                m = dict(name="", parent="", index=-1, type=0, hidden=False, tran=None, segments=[], envelope=[])
                for t2, s2, e2 in chunks(b, s, e):
                    if t2 == "NAME":
                        m["name"] = cstr(b, s2, e2)
                    elif t2 == "PRNT":
                        m["parent"] = cstr(b, s2, e2)
                    elif t2 == "MNDX":
                        m["index"] = struct.unpack_from("<I", b, s2)[0]
                    elif t2 == "MTYP":
                        m["type"] = struct.unpack_from("<I", b, s2)[0]
                    elif t2 == "FLGS":
                        m["hidden"] = bool(struct.unpack_from("<I", b, s2)[0] & 1)
                    elif t2 == "TRAN":
                        v = struct.unpack_from("<10f", b, s2)
                        m["tran"] = dict(scale=v[0:3], rot=v[3:7], pos=v[7:10])   # rot: x y z w
                    elif t2 == "GEOM":
                        for t3, s3, e3 in chunks(b, s2, e2):
                            if t3 == "ENVL":
                                n = struct.unpack_from("<I", b, s3)[0]
                                m["envelope"] = list(struct.unpack_from(f"<{n}I", b, s3 + 4))
                            elif t3 == "SEGM":
                                m["segments"].append(segment(b, s3, e3))
                out["models"].append(m)
    walk(0, len(b))
    return out


def segment(b, s, e):
    g = dict(mat=0, pos=[], nrm=[], uv=[], tris=[], weights=[])
    for t, s2, e2 in chunks(b, s, e):
        n = struct.unpack_from("<I", b, s2)[0] if e2 - s2 >= 4 else 0
        if t == "MATI":
            g["mat"] = n
        elif t == "POSL":
            g["pos"] = [struct.unpack_from("<3f", b, s2 + 4 + 12 * k) for k in range(n)]
        elif t == "NRML":
            g["nrm"] = [struct.unpack_from("<3f", b, s2 + 4 + 12 * k) for k in range(n)]
        elif t == "UV0L":
            g["uv"] = [struct.unpack_from("<2f", b, s2 + 4 + 8 * k) for k in range(n)]
        elif t == "WGHT":
            g["weights"] = [[struct.unpack_from("<If", b, s2 + 4 + 32 * k + 8 * j) for j in range(4)] for k in range(n)]
        elif t == "NDXT":
            g["tris"] = [struct.unpack_from("<3H", b, s2 + 4 + 6 * k) for k in range(n)]
        elif t == "STRP" and not g["tris"]:
            g["tris"] = strips(struct.unpack_from(f"<{n}H", b, s2 + 4))
    return g


def strips(idx):
    """ZeroEngine strips: the first two indices of each strip have the 0x8000 bit set"""
    tris, cur = [], []
    for k, v in enumerate(idx):
        if v & 0x8000 and (k + 1 < len(idx) and idx[k + 1] & 0x8000):
            cur = []
        cur.append(v & 0x7FFF)
        if len(cur) >= 3:
            a, bb, c = cur[-3:]
            if len(set((a, bb, c))) == 3:
                tris.append((a, bb, c) if (len(cur) - 3) % 2 == 0 else (bb, a, c))
    return tris


if __name__ == "__main__":
    d = read(sys.argv[1])
    print("materials:", d["materials"])
    for m in d["models"]:
        segs = [(len(g["pos"]), len(g["tris"]), g["mat"], bool(g["weights"])) for g in m["segments"]]
        print(f'{m["index"]:3} {m["name"]:32} parent={m["parent"]:24} type={m["type"]} hidden={m["hidden"]} '
              f'pos={tuple(round(x, 2) for x in m["tran"]["pos"]) if m["tran"] else None} segs={segs} env={len(m["envelope"])}')
