"""Paint a logo onto a model's texture by projecting it straight down (-Z) onto the top faces, in UV space.

    python -B "plans & scripts/uv_decal.py" MODEL.obj OUT.png SIZE CX CY RADIUS [ZMIN]

Writes an RGBA overlay (SIZE x SIZE, same UV layout as the model's texture) that unit_models.py textures() lays over the
diffuse after any tint (SPECS decal=OUT.png). Only faces facing up (|n.z| > 0.5) above ZMIN and inside RADIUS of (CX, CY)
get the logo. The logo is the Separatist (CIS) emblem, drawn here: blue hexagon, light ring, six spokes, hub.
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw


def cis_logo(px=512):
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, R = px / 2, px * 0.48
    hexa = [(c + R * math.cos(math.radians(60 * i + 30)), c + R * math.sin(math.radians(60 * i + 30))) for i in range(6)]
    d.polygon(hexa, fill=(38, 70, 150, 255))                                   # Separatist blue
    inner = [(c + R * 0.86 * math.cos(math.radians(60 * i + 30)), c + R * 0.86 * math.sin(math.radians(60 * i + 30))) for i in range(6)]
    d.line(inner + inner[:1], fill=(205, 218, 238, 255), width=int(px * 0.035))
    r = R * 0.6
    d.ellipse([c - r, c - r, c + r, c + r], outline=(205, 218, 238, 255), width=int(px * 0.06))
    for i in range(6):                                                          # spokes, between the hexagon corners
        a = math.radians(60 * i)
        d.line([(c + R * 0.16 * math.cos(a), c + R * 0.16 * math.sin(a)), (c + r * math.cos(a), c + r * math.sin(a))],
               fill=(205, 218, 238, 255), width=int(px * 0.05))
    h = R * 0.16
    d.ellipse([c - h, c - h, c + h, c + h], fill=(205, 218, 238, 255))
    return np.asarray(im, np.float32) / 255.0


def read_obj(path):
    V, T, F = [], [], []
    for l in open(path):
        if l.startswith("v "):
            V.append([float(x) for x in l.split()[1:4]])
        elif l.startswith("vt "):
            T.append([float(x) for x in l.split()[1:3]])
        elif l.startswith("f "):
            F.append([tuple(int(x) - 1 for x in p.split("/")[:2]) for p in l.split()[1:4]])
    return np.array(V), np.array(T), F


def decal(obj, out, size, cx, cy, radius, zmin=-1e9):
    V, T, F = read_obj(obj)
    logo = cis_logo()
    L = logo.shape[0]
    over = np.zeros((size, size, 4), np.float32)
    n_faces = 0
    for f in F:
        p = V[[i for i, _ in f]]
        uv = T[[t for _, t in f]]
        nrm = np.cross(p[1] - p[0], p[2] - p[0])
        if np.linalg.norm(nrm) == 0 or abs(nrm[2]) / np.linalg.norm(nrm) < 0.5 or p[:, 2].mean() < zmin:
            continue
        if np.min(np.hypot(p[:, 0] - cx, p[:, 1] - cy)) > radius:
            continue
        n_faces += 1
        q = np.stack([uv[:, 0] * size, (1 - uv[:, 1]) * size], 1)              # texel space (image rows go down)
        x0, y0 = np.floor(q.min(0)).astype(int)
        x1, y1 = np.ceil(q.max(0)).astype(int)
        den = (q[1, 1] - q[2, 1]) * (q[0, 0] - q[2, 0]) + (q[2, 0] - q[1, 0]) * (q[0, 1] - q[2, 1])
        if abs(den) < 1e-9:
            continue
        for y in range(max(y0, 0), min(y1 + 1, size)):
            for x in range(max(x0, 0), min(x1 + 1, size)):
                a = ((q[1, 1] - q[2, 1]) * (x + .5 - q[2, 0]) + (q[2, 0] - q[1, 0]) * (y + .5 - q[2, 1])) / den
                b = ((q[2, 1] - q[0, 1]) * (x + .5 - q[2, 0]) + (q[0, 0] - q[2, 0]) * (y + .5 - q[2, 1])) / den
                g = 1 - a - b
                if min(a, b, g) < -0.02:
                    continue
                w = a * p[0] + b * p[1] + g * p[2]
                lu, lv = (w[0] - cx) / (2 * radius) + 0.5, (w[1] - cy) / (2 * radius) + 0.5
                if 0 <= lu < 1 and 0 <= lv < 1:
                    over[y, x] = logo[int(lv * L), int(lu * L)]
    assert n_faces, "no faces under the decal: check CX CY RADIUS ZMIN"
    Image.fromarray((over * 255).astype(np.uint8), "RGBA").save(out)
    print("decal faces", n_faces, "texels", int((over[..., 3] > 0).sum()), "->", out)


if __name__ == "__main__":
    a = sys.argv[1:]
    decal(a[0], a[1], int(a[2]), float(a[3]), float(a[4]), float(a[5]), float(a[6]) if len(a) > 6 else -1e9)
