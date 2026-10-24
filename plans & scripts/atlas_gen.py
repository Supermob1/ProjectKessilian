"""Star Wars terrain atlas: generate 64 aerial landscape textures with the local ComfyUI (Krea 2 Turbo),
make them tileable, derive normal/spec maps, pack map/terrain/atlas{0,1,2}.dds + atlas_normal{0,1,2}.dds
as an 8x8 atlas of 1024px tiles (gfx/FX/constants.fxh overrides MAP_NUM_TILES/TEXELS_PER_TILE to match).

Slot N = `texture = N` in common/terrain/00_terrain.txt; terrain.bmp palette index = 32 + N
(planet_terrain_gen.py paints with these by family).
Generated sources are cached in WIPGFX/Assets/atlas_src/slotNN.png; --regen N redoes one.

Usage (from the mod root, ComfyUI running on 127.0.0.1:8188):
  python "WIPGFX/plans & scripts/atlas_gen.py" --generate            # fill missing sources
  python "WIPGFX/plans & scripts/atlas_gen.py" --regen 9 14          # redo specific slots
  python "WIPGFX/plans & scripts/atlas_gen.py" --seam [N ...]        # make tileable by repainting the seams
  python "WIPGFX/plans & scripts/atlas_gen.py" --preview OUT.png     # contact sheet of the atlas
  python "WIPGFX/plans & scripts/atlas_gen.py" --write               # pack the DDS files
"""
import argparse, io, json, os, random, struct, time, urllib.parse, urllib.request
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

COMFY = "http://127.0.0.1:8188"
SRC = "WIPGFX/Assets/atlas_src"
OUT = "map/terrain"
GRID = 8                       # atlas is GRID x GRID tiles
TILE = 1024                    # top-level tile size (atlas0); atlas1/2 are half/quarter
GEN_SIZE = 1344                # generated, then downscaled to TILE (crisper than generating at TILE)
STYLE = ("high-resolution satellite image, nadir view with the camera pointing straight down at the ground, flat "
         "map-like view, natural landscape only, photorealistic, soft even daylight, features spread evenly over the "
         "whole frame, many small similar features, no single dominant feature, no central focus, "
         "no vehicles, no ships, no wreckage, no animals, no people, no roads, no buildings, no text, no border, "
         "no horizon, no sky, no vignette")
CITY_STYLE = ("high-resolution satellite image, nadir view with the camera pointing straight down, flat map-like "
              "view, photorealistic, soft even daylight, city spread evenly over the whole frame, no single dominant "
              "feature, no central focus, no text, no border, "
              "no horizon, no sky, no vignette")

# family -> (gloss, spec, normal strength); slot -> (family, prompt)
FAMILY = {"temperate": (70, 90, 2.5), "forest": (55, 75, 3.0), "jungle": (60, 80, 3.0), "desert": (45, 65, 2.5),
          "rock": (55, 80, 3.5), "ice": (110, 140, 2.5), "lava": (90, 110, 3.0), "ocean": (200, 200, 1.2),
          "city": (120, 140, 3.0), "barren": (45, 70, 3.0), "exotic": (90, 110, 3.0)}
SLOTS = {
    # temperate worlds: Naboo, Alderaan, Chandrila
    0:  ("temperate", "emerald meadows of a peaceful temperate planet with hedgerows and small groves of trees"),
    1:  ("temperate", "satellite map tile of green grassland plains with small scattered blue ponds, perfectly flat orthographic top view"),
    2:  ("temperate", "patchwork of green and golden farm fields in a gentle valley, hedgerows between fields"),
    3:  ("temperate", "green rolling hills with pale limestone outcrops"),
    4:  ("temperate", "high alpine grassland with scattered grey rocks and thin streams"),
    5:  ("temperate", "green river delta wetlands with braided channels and reed beds"),
    6:  ("temperate", "satellite map tile of dry golden savanna grassland with small scattered round shrubs, perfectly flat orthographic top view"),
    7:  ("temperate", "mixed temperate woodland with sunny clearings and meadows"),
    # forest worlds: Endor, Kashyyyk, Takodana
    8:  ("forest", "endless dense canopy of giant redwood trees, deep green, tiny gaps of shadow"),
    9:  ("forest", "colossal ancient tree canopy with low mist drifting between the crowns, deep green and grey"),
    10: ("forest", "alien forest canopy in rusty orange, ochre and green tones"),
    11: ("forest", "dense evergreen forest with many small clearings and creeks"),
    12: ("forest", "dark pine forest on steep ridges with rocky crests"),
    13: ("forest", "dense forest canopy with a few small dark bog pools between the trees"),
    # jungle and swamp worlds: Yavin 4, Dagobah, Felucia
    14: ("jungle", "endless tropical rainforest canopy, lush bright green, patches of low mist"),
    15: ("jungle", "murky swamp forest canopy of grey-green gnarled trees with dark water showing between them"),
    16: ("jungle", "alien fungal jungle canopy in vivid magenta, orange and lime colours"),
    17: ("jungle", "mangrove jungle with a dense web of small brown water channels"),
    18: ("jungle", "jungle-covered steep hills and valleys with clinging mist"),
    19: ("jungle", "green marshland of reeds, mudflats and shallow water channels"),
    # desert worlds: Tatooine, Jakku, Jedha
    20: ("desert", "vast sea of golden sand dunes with sharp crests"),
    21: ("desert", "rocky desert plateau cut by wind-carved buttes and narrow canyons, tan and orange"),
    22: ("desert", "satellite map tile of a flat desert hardpan, pale brown, subtle wind ripples and darker gravel patches"),
    23: ("desert", "eroded sandstone desert hills with gullies"),
    24: ("desert", "white salt flats with a cracked polygon crust"),
    25: ("desert", "sand dunes flowing around dark rocky outcrops"),
    26: ("desert", "dry desert riverbeds and branching wadis in tan sand"),
    27: ("desert", "sandy grey-beige badlands with low ridges"),
    # rocky and red worlds: Geonosis, Ryloth, Lothal highlands
    28: ("rock", "deep red rock canyons with layered cliffs"),
    29: ("rock", "orange mesas and rock spires rising from rust-coloured sand"),
    30: ("rock", "grey barren mountain range with sharp ridges and scree slopes"),
    31: ("rock", "brown rocky mountain peaks with deep valleys"),
    32: ("rock", "satellite map tile of a high grey rocky plateau with cracks and patches of yellow lichen"),
    33: ("rock", "dark volcanic rock ridges with ash-grey slopes"),
    # ice worlds: Hoth, Ilum, Orto Plutonia
    34: ("ice", "endless white snowfield with wind-blown snow drifts"),
    35: ("ice", "blue-white glacier with deep crevasses"),
    36: ("ice", "snow-covered mountain range with sharp icy peaks"),
    37: ("ice", "frozen tundra of patchy snow over dark rock and frozen moss"),
    38: ("ice", "satellite map tile of a frozen lake of cracked blue-white ice with snow drifts"),
    39: ("ice", "satellite map tile of snow-covered hills with irregular dark patches of conifer forest, perfectly flat orthographic top view"),
    # lava worlds: Mustafar, Sullust
    40: ("lava", "glowing orange lava rivers flowing through black basalt plains"),
    41: ("lava", "grey volcanic ash plains with thin glowing red cracks and fissures"),
    42: ("lava", "black volcanic mountains with bright lava streams running down"),
    43: ("lava", "cooled black lava field with ropy cracked basalt"),
    44: ("lava", "sulphur-yellow volcanic flats with steaming vents"),
    # ocean worlds: Kamino, Scarif, Mon Cala
    45: ("ocean", "deep dark blue-grey ocean surface with storm-whipped waves"),
    46: ("ocean", "turquoise tropical shallows with white sandbars"),
    47: ("ocean", "blue sea dotted with small green tropical islands"),
    48: ("ocean", "clear blue coastal shallows over a sandy bottom with scattered dark reef patches"),
    49: ("ocean", "brown and blue tidal mudflats with a dense network of small water channels"),
    # city worlds: Coruscant, Corellia, Kuat
    50: ("city", "orthographic satellite map tile of an endless megacity, flat rooftops of all sizes seen exactly from above, no building sides visible, grey and white, landing pads"),
    51: ("city", "heavy industrial district of rows of rectangular factory roofs, storage tanks and pipelines laid out in a regular grid, grey and rust"),
    52: ("city", "city blocks laid out in a regular grid, each block with a small green courtyard, pale rooftops"),
    53: ("city", "spaceport district of many small circular landing pads and hangar roofs repeated in a regular grid"),
    54: ("city", "dark industrial city grid of rooftops with many small scattered orange lights"),
    55: ("city", "bombed ruined city blocks, rubble and broken rooftops, grey dust"),
    # barren moons and rocks
    56: ("barren", "grey moon surface densely covered with craters of all sizes"),
    57: ("barren", "dusty brown barren plain with small craters"),
    58: ("barren", "jagged rocky asteroid-like terrain with boulders"),
    59: ("barren", "pale grey regolith with soft dust dunes"),
    60: ("barren", "dark basalt plains with old eroded craters"),
    # exotic: Crait, Mygeeto, Mimban
    61: ("exotic", "thin white salt crust over vivid red soil showing through in streaks"),
    62: ("exotic", "frozen ground studded with clusters of small pale blue crystals and snow"),
    63: ("exotic", "grey muddy wetland with pools of murky water and dead reeds"),
}


def comfy_graph(prompt, seed, size=GEN_SIZE):
    return {
        "10": {"class_type": "UNETLoader", "inputs": {"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "11": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "13": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": size, "height": size, "batch_size": 1}},
        "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "euler",
                                                   "scheduler": "simple", "denoise": 1.0, "model": ["10", 0],
                                                   "positive": ["6", 0], "negative": ["13", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["12", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "hod_atlas/slot"}},
    }


def http(path, data=None):
    req = urllib.request.Request(COMFY + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def generate(slot, seed=None):
    fam, text = SLOTS[slot]
    prompt = f"{text}. {CITY_STYLE if fam == 'city' else STYLE}"
    seed = seed if seed is not None else random.randrange(2 ** 48)
    pid = json.loads(http("/prompt", {"prompt": comfy_graph(prompt, seed)}))["prompt_id"]
    t0 = time.time()
    while True:
        h = json.loads(http(f"/history/{pid}"))
        if pid in h:
            st = h[pid]["status"]
            if st.get("status_str") == "error":
                raise RuntimeError(f"slot {slot}: ComfyUI error {st.get('messages')}")
            if st.get("completed"):
                img = h[pid]["outputs"]["9"]["images"][0]
                break
        if time.time() - t0 > 600:
            raise TimeoutError(f"slot {slot}: no result after 600 s")
        time.sleep(1)
    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
    data = http(f"/view?{q}")
    os.makedirs(SRC, exist_ok=True)
    Image.open(io.BytesIO(data)).convert("RGB").save(f"{SRC}/slot{slot:02d}.png")
    with open(f"{SRC}/manifest.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"slot": slot, "seed": seed, "prompt": prompt, "comfy_file": img["filename"],
                            "seconds": round(time.time() - t0, 1)}) + "\n")
    print(f"slot {slot:2d} done in {time.time() - t0:.0f}s (seed {seed})", flush=True)


SEAM_BAND = 0.07      # half-width of the repainted cross, as a fraction of the image size
SEAM_FEATHER = 0.035  # extra soft edge where repaint fades into the original
SEAM_DENOISE = 0.8


def upload(png_bytes, name):
    """POST an image to ComfyUI's input folder (multipart form), return the stored name."""
    boundary = "----hodseam" + str(random.randrange(10 ** 12))
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + png_bytes + \
           (f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue"
            f"\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(COMFY + "/upload/image", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["name"]


def seam_masks(n):
    """Cross through the middle: hard mask for the model, feathered mask for compositing."""
    d = np.abs(np.arange(n) - (n - 1) / 2) / n
    dist = np.minimum(d[None, :], d[:, None])              # distance to the nearer centre line
    hard = (dist < SEAM_BAND + SEAM_FEATHER).astype(np.float32)
    soft = np.clip(1 - (dist - SEAM_BAND) / SEAM_FEATHER, 0, 1)
    return hard, soft * soft * (3 - 2 * soft)


def run_graph(graph, out_node, timeout=600):
    pid = json.loads(http("/prompt", {"prompt": graph}))["prompt_id"]
    t0 = time.time()
    while True:
        h = json.loads(http(f"/history/{pid}"))
        if pid in h:
            st = h[pid]["status"]
            if st.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI error {st.get('messages')}")
            if st.get("completed"):
                img = h[pid]["outputs"][out_node]["images"][0]
                break
        if time.time() - t0 > timeout:
            raise TimeoutError("no result")
        time.sleep(1)
    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
    return Image.open(io.BytesIO(http(f"/view?{q}"))).convert("RGB")


def seam_inpaint(slot, seed=None):
    """Make slot tileable without ghosting: roll by half (edges now wrap perfectly, seams form a centre cross),
    let the model repaint only that cross, composite it back. Writes SRC/slotNN_tile.png."""
    fam, text = SLOTS[slot]
    prompt = f"{text}. {CITY_STYLE if fam == 'city' else STYLE}"
    a = np.array(Image.open(f"{SRC}/slot{slot:02d}.png").convert("RGB"))
    n = a.shape[0]
    rolled = np.roll(np.roll(a, n // 2, 0), n // 2, 1)
    hard, soft = seam_masks(n)
    buf = io.BytesIO(); Image.fromarray(rolled).save(buf, "PNG")
    img_name = upload(buf.getvalue(), f"hod_seam_{slot:02d}.png")
    buf = io.BytesIO(); Image.fromarray((hard * 255).astype(np.uint8)).save(buf, "PNG")
    mask_name = upload(buf.getvalue(), f"hod_seam_{slot:02d}_mask.png")
    g = comfy_graph(prompt, seed if seed is not None else random.randrange(2 ** 48))
    del g["5"]
    g["20"] = {"class_type": "LoadImage", "inputs": {"image": img_name}}
    g["21"] = {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}}
    g["22"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["20", 0], "vae": ["12", 0]}}
    g["23"] = {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["22", 0], "mask": ["21", 0]}}
    g["3"]["inputs"]["latent_image"] = ["23", 0]
    g["3"]["inputs"]["denoise"] = SEAM_DENOISE
    g["9"]["inputs"]["filename_prefix"] = "hod_atlas/seam"
    t0 = time.time()
    out = np.array(run_graph(g, "9").resize((n, n), Image.LANCZOS)).astype(np.float32)
    comp = rolled * (1 - soft[..., None]) + out * soft[..., None]
    Image.fromarray(np.clip(comp, 0, 255).astype(np.uint8)).save(f"{SRC}/slot{slot:02d}_tile.png")
    print(f"slot {slot:2d} seam repainted in {time.time() - t0:.0f}s", flush=True)


def make_tileable(a):
    """Make opposite edges match, one axis at a time: cross-fade with a copy shifted half a tile along that axis.
    The shifted copy's own seam runs through the middle, exactly where its blend weight is 0."""
    for axis in (1, 0):
        n = a.shape[axis]
        sh = np.roll(a, n // 2, axis)
        t = np.clip(np.abs(np.linspace(-1, 1, n)) * 1.6 - 0.6, 0, 1)   # 0 in the middle, 1 at the edges
        t = t * t * (3 - 2 * t)
        m = (t[None, :] if axis == 1 else t[:, None])[..., None]
        a = a * (1 - m) + sh * m
    return a


def tile_maps(slot, size=TILE):
    gloss, spec, strength = FAMILY[SLOTS[slot][0]]
    tiled = f"{SRC}/slot{slot:02d}_tile.png"
    if os.path.exists(tiled):                              # seam-inpainted: already wraps, no blending needed
        a = np.array(Image.open(tiled).convert("RGB")).astype(np.float32) / 255
    else:
        a = make_tileable(np.array(Image.open(f"{SRC}/slot{slot:02d}.png").convert("RGB")).astype(np.float32) / 255)
    a = np.array(Image.fromarray((a * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)).astype(np.float32) / 255
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    hgt = ndi.gaussian_filter(lum, 1.0, mode="wrap")
    gx = ndi.sobel(hgt, 1, mode="wrap")
    gy = ndi.sobel(hgt, 0, mode="wrap")
    n = np.stack([-gx * strength, -gy * strength, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    detail = (lum - lum.mean()) * 60
    diffuse = np.dstack([a * 255, np.clip(gloss + detail, 0, 255)])
    normal = np.dstack([n * 127.5 + 127.5, np.clip(spec + detail, 0, 255)])
    return diffuse.astype(np.uint8), normal.astype(np.uint8)


def atlas(size_tile):
    d = np.zeros((size_tile * GRID, size_tile * GRID, 4), np.uint8)
    n = np.zeros_like(d)
    for s in range(GRID * GRID):
        dt, nt = tile_maps(s, size_tile)
        r, c = divmod(s, GRID)
        d[r * size_tile:(r + 1) * size_tile, c * size_tile:(c + 1) * size_tile] = dt
        n[r * size_tile:(r + 1) * size_tile, c * size_tile:(c + 1) * size_tile] = nt
    return d, n


def save_dxt5_mips(rgba, path):
    """DXT5 with a full mip chain (Pillow writes one level; we concatenate the levels' block data)."""
    levels, im = [], Image.fromarray(rgba, "RGBA")
    while True:
        buf = io.BytesIO()
        im.save(buf, format="DDS", pixel_format="DXT5")
        levels.append(buf.getvalue())
        if im.size[0] == 1 and im.size[1] == 1:
            break
        im = im.resize((max(1, im.size[0] // 2), max(1, im.size[1] // 2)), Image.BOX)
    hdr = bytearray(levels[0][:128])
    struct.pack_into("<I", hdr, 8, struct.unpack_from("<I", hdr, 8)[0] | 0x20000)       # DDSD_MIPMAPCOUNT
    struct.pack_into("<I", hdr, 28, len(levels))
    struct.pack_into("<I", hdr, 108, struct.unpack_from("<I", hdr, 108)[0] | 0x400008)  # COMPLEX | MIPMAP
    with open(path, "wb") as f:
        f.write(bytes(hdr) + b"".join(l[128:] for l in levels))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--regen", type=int, nargs="*")
    ap.add_argument("--seam", type=int, nargs="*", help="repaint seams (no numbers = all slots missing a _tile.png)")
    ap.add_argument("--preview")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    todo = list(a.regen or [])
    if a.generate:
        todo += [s for s in SLOTS if not os.path.exists(f"{SRC}/slot{s:02d}.png")]
    for s in todo:
        generate(s)
        if os.path.exists(f"{SRC}/slot{s:02d}_tile.png"):
            os.remove(f"{SRC}/slot{s:02d}_tile.png")        # stale: source changed
    if a.seam is not None:
        for s in (a.seam or [s for s in SLOTS if not os.path.exists(f"{SRC}/slot{s:02d}_tile.png")]):
            seam_inpaint(s)
    if a.preview:
        d, _ = atlas(160)
        Image.fromarray(d[..., :3]).save(a.preview)
        print("preview", a.preview)
    if a.write:
        for lvl, tile in enumerate((TILE, TILE // 2, TILE // 4)):
            d, n = atlas(tile)
            save_dxt5_mips(d, f"{OUT}/atlas{lvl}.dds")
            save_dxt5_mips(n, f"{OUT}/atlas_normal{lvl}.dds")
            del d, n
        print("atlas files written")


if __name__ == "__main__":
    main()
