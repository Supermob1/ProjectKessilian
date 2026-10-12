"""Terrain atlas (map/terrain/atlas{0,1,2}.dds + atlas_normal{0,1,2}.dds, 4x4 slots of 512/256/128 px, DXT5 + mips).
Slot = `texture =` in common/terrain/00_terrain.txt. Diffuse RGB + A gloss; normal RGB (tangent, the terrain shader
reads .rbg so B is up) + A spec.

  python "WIPGFX/plans & scripts/terrain_atlas.py" revolution   Revolution_Realized's 5x5 aerial atlas (friend's mod,
                                                                 used with permission) + our water/lava  <- in use
  python "WIPGFX/plans & scripts/terrain_atlas.py" polyhaven    Poly Haven (CC0) ground photos (4x4)
  python "WIPGFX/plans & scripts/terrain_atlas.py" satellite    Sentinel-2 cloudless 2016 (CC BY 4.0, credit EOX)
  python "WIPGFX/plans & scripts/terrain_atlas.py" restore      the atlas the mod had before (WIPGFX/Assets/atlas_backup)
  python "WIPGFX/plans & scripts/terrain_atlas.py" scrap        our junk-field tile into slot 19 (Raxus Prime)
Slots not listed in a source keep their current tile (6 water, 14 lava). Each new tile is brightness-matched to the
pre-existing tile it replaces, so planet colours (colormap overlay) stay balanced. Comparison: WIPGFX/terrain_compare.png
"""
import io, json, os, shutil, sys, urllib.request
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flora_props import save_dxt5_mips  # noqa: E402

MAP = "map/terrain"
BACKUP = "WIPGFX/Assets/atlas_backup"
CACHE = "WIPGFX/3d/polyhaven_terrain"
FILES = [f"atlas{i}.dds" for i in range(3)] + [f"atlas_normal{i}.dds" for i in range(3)]
H = {"User-Agent": "HoD-mod/1.0"}
# slot: role -> Poly Haven texture id
POLYHAVEN = {0: "grass_path_2",              # farmland plains (+ snowy plains)
             1: "aerial_grass_rock",         # grass
             2: "aerial_rocks_01",           # grassy hills
             3: "dry_ground_rocks",          # rocky hills
             4: "brown_mud_leaves_01",       # dense forest / jungle floor
             5: "forrest_ground_01",         # forest / jungle
             7: "rocky_terrain_02",          # green mountains
             8: "grass_path_3",              # savanna
             9: "aerial_sand",               # dunes (+ permanent snow)
             10: "aerial_asphalt_01",        # city
             11: "rock_ground",              # rock (+ snowy rock)
             12: "gravelly_sand",            # sand
             13: "cracked_red_ground",       # brown mountain
             15: "red_laterite_soil_stones"}  # red mountain tops
# slot -> (lon, lat, bbox degrees) for the satellite alternative (locations still to be refined, see terrain_compare)
SATELLITE = {1: (-8.3, 53.0, 0.06), 4: (-62.0, -3.3, 0.06), 8: (34.85, -2.35, 0.06), 9: (15.3, -24.72, 0.08),
             11: (8.0, 46.5, 0.08), 15: (118.6, -22.4, 0.08), 10: (31.24, 30.05, 0.03)}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=120).read()


def tileable(a):
    """Cross-fade with a half-shifted copy, one axis at a time (satellite crops don't wrap)."""
    for axis in (1, 0):
        n = a.shape[axis]
        sh = np.roll(a, n // 2, axis)
        w = np.clip(np.abs(np.linspace(-1, 1, n)) * 1.6 - 0.6, 0, 1)
        w = w * w * (3 - 2 * w)
        m = (w[None, :] if axis == 1 else w[:, None])[..., None]
        a = a * (1 - m) + sh * m
    return a


def polyhaven_maps(pid):
    """(diffuse RGB, normal RGB, gloss) float arrays at 1k, cached under CACHE."""
    os.makedirs(CACHE, exist_ok=True)
    files = None
    out = []
    for key in ("Diffuse", "nor_gl", "Rough"):
        path = f"{CACHE}/{pid}_{key}.jpg"
        if not os.path.exists(path):
            files = files or json.loads(get(f"https://api.polyhaven.com/files/{pid}"))
            open(path, "wb").write(get(files[key]["1k"]["jpg"]["url"]))
        out.append(np.asarray(Image.open(path).convert("RGB")).astype(np.float32))
    return out[0], out[1], 255 - out[2].mean(-1)


def satellite_maps(lon, lat, bb):
    from scipy import ndimage as ndi
    a = np.asarray(Image.open(io.BytesIO(get(
        "https://tiles.maps.eox.at/wms?service=wms&request=getmap&version=1.1.1&layers=s2cloudless"
        f"&bbox={lon - bb / 2},{lat - bb / 2},{lon + bb / 2},{lat + bb / 2}&width=1024&height=1024"
        "&srs=EPSG:4326&format=image/jpeg"))).convert("RGB")).astype(np.float32)
    a = tileable(a)
    lum = ndi.gaussian_filter(a.mean(-1) / 255, 1.0, mode="wrap")
    gx, gy = ndi.sobel(lum, 1, mode="wrap") * 2.5, ndi.sobel(lum, 0, mode="wrap") * 2.5
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return a, n * 127.5 + 127.5, np.full(a.shape[:2], 70, np.float32)


def build(source):
    if not os.path.exists(f"{BACKUP}/atlas0.dds"):              # first run: keep the pre-existing atlas
        os.makedirs(BACKUP, exist_ok=True)
        for f in FILES:
            shutil.copy2(f"{MAP}/{f}", f"{BACKUP}/{f}")
    ref = np.asarray(Image.open(f"{BACKUP}/atlas0.dds").convert("RGB")).astype(np.float32)
    rt = ref.shape[0] // 4
    tiles = {}
    for slot, spec in source.items():
        diff, nrm, gloss = polyhaven_maps(spec) if isinstance(spec, str) else satellite_maps(*spec)
        old = ref[(slot // 4) * rt:(slot // 4 + 1) * rt, (slot % 4) * rt:(slot % 4 + 1) * rt]
        diff = np.clip(diff * old.mean() / max(diff.mean(), 1), 0, 255)   # keep the slot's brightness
        tiles[slot] = (diff, nrm, gloss)
        print(f"slot {slot:2d} <- {spec}")
    for lvl in range(3):
        for kind in ("atlas", "atlas_normal"):
            im = np.asarray(Image.open(f"{BACKUP}/{kind}{lvl}.dds").convert("RGBA")).copy()
            t = im.shape[0] // 4
            for slot, (diff, nrm, gloss) in tiles.items():
                rgb = diff if kind == "atlas" else nrm
                a = gloss * 0.6 if kind == "atlas" else np.full(gloss.shape, 40, np.float32)
                rgba = np.dstack([rgb, a]).astype(np.uint8)
                im[(slot // 4) * t:(slot // 4 + 1) * t, (slot % 4) * t:(slot % 4 + 1) * t] = \
                    np.asarray(Image.fromarray(rgba, "RGBA").resize((t, t), Image.LANCZOS))
            save_dxt5_mips(im, f"{MAP}/{kind}{lvl}.dds")
    if os.path.exists("gfx/FX/constants.fxh"):             # 4x4 atlas: vanilla constants
        os.remove("gfx/FX/constants.fxh")
    print("atlas written:", ", ".join(FILES))


REVOLUTION = r"F:/Documents/Paradox Interactive/Hearts of Iron IV/mod/Revolution_Realized"
VANILLA_CONSTANTS = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/FX/constants.fxh"
# 5x5 slot -> our 4x4 backup slot to paste in (6 = blue water for inner seas, 14 = lava); 20 is a joke image in
# their atlas (unused by our terrain.bmp) -> copy of their alpine slot 18
REV_FROM_OURS = {6: 6, 14: 14}
REV_COPY = {20: 18}
REV_CONSTANTS = {"TERRAIN_TILE_FREQ": "228.0f", "MAP_NUM_TILES": "5.0f", "TEXELS_PER_TILE": "312.0f"}


def revolution():
    """Their atlas needs their constants (5x5 grid, sharper mips, finer repeat): gfx/FX/constants.fxh = vanilla + those."""
    import re
    for lvl in range(3):
        for kind in ("atlas", "atlas_normal"):
            im = np.asarray(Image.open(f"{REVOLUTION}/map/terrain/{kind}{lvl}.dds").convert("RGBA")).copy()
            ours = np.asarray(Image.open(f"{BACKUP}/{kind}{lvl}.dds").convert("RGBA"))
            t, o = im.shape[0] // 5, ours.shape[0] // 4
            cell = lambda a, n, k, sz: a[(k // n) * sz:(k // n + 1) * sz, (k % n) * sz:(k % n + 1) * sz]
            for dst, src in REV_FROM_OURS.items():
                cell(im, 5, dst, t)[:] = np.asarray(Image.fromarray(cell(ours, 4, src, o).copy()).resize((t, t), Image.LANCZOS))
            for dst, src in REV_COPY.items():
                cell(im, 5, dst, t)[:] = cell(im, 5, src, t).copy()
            save_dxt5_mips(im, f"{MAP}/{kind}{lvl}.dds")
    c = open(VANILLA_CONSTANTS, encoding="utf-8-sig").read()
    for k, v in REV_CONSTANTS.items():
        c, n = re.subn(r"(static const float %s\s*=\s*)[0-9.]+f" % k, r"\g<1>" + v, c)
        assert n == 1, k
    # the note must sit inside the Code [[ ]] block: anything before it breaks the file and every shader using it
    assert c.count("[[") >= 1
    c = c.replace("[[", "[[\n// HOD: vanilla constants.fxh with Revolution_Realized's terrain atlas values (terrain_atlas.py)", 1)
    open("gfx/FX/constants.fxh", "w", encoding="utf-8", newline="\n").write(c)
    print("Revolution_Realized atlas written (5x5) + gfx/FX/constants.fxh")
    scrap()                                                # our own tile on top (Raxus Prime)


def restore():
    for f in FILES:
        shutil.copy2(f"{BACKUP}/{f}", f"{MAP}/{f}")
    if os.path.exists("gfx/FX/constants.fxh"):             # 4x4 atlas again: vanilla constants
        os.remove("gfx/FX/constants.fxh")
    print("restored the pre-existing atlas from", BACKUP)


SCRAP_SLOT = 19      # unused slot of the 5x5 atlas (00_terrain.txt: scrap_28, scrap_town_29)


def scrap_tile(S=1024, seed=19):
    """Raxus Prime's junk fields seen from above, tileable: hull plates, girders, pipes and drums piled on each other,
    rust and grey metal with flecks of old paint, dark gaps between. -> (diffuse RGB, height 0..1)"""
    from PIL import ImageDraw
    from scipy import ndimage as ndi
    rng = np.random.default_rng(seed)
    col = Image.new("RGB", (3 * S, 3 * S), (46, 38, 32))
    hgt = Image.new("L", (3 * S, 3 * S), 0)
    dc, dh = ImageDraw.Draw(col), ImageDraw.Draw(hgt)
    paints = [(150, 70, 50), (70, 90, 120), (160, 140, 70), (90, 110, 80), (170, 170, 165)]
    for k in range(1400):
        x, y = rng.uniform(0, S), rng.uniform(0, S)
        z = int(40 + 215 * k / 1400)                                     # later pieces lie on top
        rust = rng.random()
        base = (np.array([150, 84, 46]) * rust + np.array([118, 116, 112]) * (1 - rust)) * rng.uniform(0.6, 1.15)
        if rng.random() < 0.08:
            base = np.array(paints[rng.integers(len(paints))]) * rng.uniform(0.6, 1.0)
        c = tuple(int(v) for v in np.clip(base, 0, 255))
        kind = rng.random()
        for ox in (-S, 0, S):                                            # drawn into every neighbouring copy: tileable
            for oy in (-S, 0, S):
                cx, cy = x + ox + S, y + oy + S
                if kind < 0.6:                                          # plate
                    w, h, a = rng.uniform(8, 46) * S / 512, rng.uniform(5, 26) * S / 512, rng.uniform(0, np.pi)
                    pts = [(cx + dx * np.cos(a) - dy * np.sin(a), cy + dx * np.sin(a) + dy * np.cos(a))
                           for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]
                    dc.polygon(pts, fill=c, outline=(30, 24, 20))
                    dh.polygon(pts, fill=z)
                elif kind < 0.85:                                       # girder / pipe
                    L, a = rng.uniform(20, 70) * S / 512, rng.uniform(0, np.pi)
                    p0, p1 = (cx - L * np.cos(a), cy - L * np.sin(a)), (cx + L * np.cos(a), cy + L * np.sin(a))
                    wd = int(rng.uniform(2, 6) * S / 512) + 1
                    dc.line([p0, p1], fill=c, width=wd)
                    dh.line([p0, p1], fill=z, width=wd)
                else:                                                   # drum / round tank end
                    r = rng.uniform(4, 14) * S / 512
                    dc.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c, outline=(30, 24, 20))
                    dh.ellipse([cx - r, cy - r, cx + r, cy + r], fill=z)
    col = np.asarray(col, np.float32)[S:2 * S, S:2 * S]
    h = np.asarray(hgt, np.float32)[S:2 * S, S:2 * S] / 255
    grime = ndi.gaussian_filter(rng.random((S, S)), 3, mode="wrap")
    grime = (grime - grime.min()) / np.ptp(grime)
    ao = np.clip(1 - 2.5 * (ndi.gaussian_filter(h, 4, mode="wrap") - h), 0.45, 1)  # dark where pieces overlap
    col = col * (0.8 + 0.35 * grime[..., None]) * ao[..., None]
    return np.clip(col, 0, 255), h


def splice_slot(path, new_path, slot, grid=5):
    """Copy one atlas slot's DXT5 blocks from new_path into path, every mip level whose tiles are whole blocks: the
    other tiles stay byte for byte (re-encoding the whole atlas would recompress every terrain in the game)."""
    import struct

    def levels(b):
        h, w = struct.unpack_from("<II", b, 12)
        assert b[84:88] == b"DXT5"
        off, out = 128, []
        for _ in range(max(1, struct.unpack_from("<I", b, 28)[0])):
            bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
            out.append((off, w, bw))
            off += bw * bh * 16
            w, h = max(1, w // 2), max(1, h // 2)
        return out
    o, n = bytearray(open(path, "rb").read()), open(new_path, "rb").read()
    r, c = divmod(slot, grid)
    for (oo, w, bw), (no, w2, _bw) in zip(levels(o), levels(n)):
        assert w == w2
        t = w // grid
        if t < 4 or t % 4:
            break
        x0, x1 = c * t // 4, (c + 1) * t // 4
        for by in range(r * t // 4, (r + 1) * t // 4):
            a, b = oo + (by * bw + x0) * 16, no + (by * bw + x0) * 16
            o[a:a + (x1 - x0) * 16] = n[b:b + (x1 - x0) * 16]
    open(path, "wb").write(bytes(o))


def scrap():
    """Write the junk tile into SCRAP_SLOT of the current atlas (all 3 levels, diffuse + normal), brightness kept
    close to the brown rock tile so the colormap overlay stays balanced."""
    from scipy import ndimage as ndi
    col, h = scrap_tile()
    gx, gy = ndi.sobel(h, 1, mode="wrap") * 2.0, ndi.sobel(h, 0, mode="wrap") * 2.0
    nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    for lvl in range(3):
        for kind in ("atlas", "atlas_normal"):
            im = np.asarray(Image.open(f"{MAP}/{kind}{lvl}.dds").convert("RGBA")).copy()
            t = im.shape[0] // 5
            cell = lambda a, k: a[(k // 5) * t:(k // 5 + 1) * t, (k % 5) * t:(k % 5 + 1) * t]
            if kind == "atlas":
                ref = cell(im, 13)[..., :3].mean()                     # brown mountain tile
                d = col * ref / max(col.mean(), 1)
                tile = np.dstack([d, np.full(h.shape, 90, np.float32)])           # A = gloss: dull metal
            else:
                n = nrm * 127.5 + 127.5                                 # stored like the other tiles: B is up
                tile = np.dstack([n[..., 0], n[..., 1], n[..., 2], np.full(h.shape, 70, np.float32)])
            cell(im, SCRAP_SLOT)[:] = np.asarray(Image.fromarray(np.clip(tile, 0, 255).astype(np.uint8), "RGBA").resize((t, t), Image.LANCZOS))
            tmp = f"{MAP}/{kind}{lvl}.scrap.dds"
            save_dxt5_mips(im, tmp)
            splice_slot(f"{MAP}/{kind}{lvl}.dds", tmp, SCRAP_SLOT)     # only the slot's blocks change
            os.remove(tmp)
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).resize((512, 512)).save("WIPGFX/scrap_tile_preview.png")
    print("scrap tile written to atlas slot", SCRAP_SLOT)

if __name__ == "__main__":
    {"polyhaven": lambda: build(POLYHAVEN), "satellite": lambda: build(SATELLITE), "restore": restore,
     "revolution": revolution, "scrap": scrap}[sys.argv[1]]()
