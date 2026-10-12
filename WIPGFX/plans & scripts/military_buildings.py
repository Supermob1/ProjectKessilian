"""Star Wars replacements for vanilla building models.
  air base   -> launch pad complex: pillars with circular landing pads, control tower (procedural)
  anti-air   -> ion cannon emplacement: dome turret + barrel in a walled pad (procedural)
  naval base -> space dock: shore hangar + tower, pier to a landing pad between two ship gantries (procedural)
  landmarks  -> Jedi Temple, Senate Rotunda, Tipoca City, Petranaki Arena, Great Temple of the Massassi, Jabba's
                palace, Sundari dome (shapes and colours from Wookieepedia stills), placed by `landmarks`

  python "WIPGFX/plans & scripts/military_buildings.py" textures
  blender -b --factory-startup --python "WIPGFX/plans & scripts/military_buildings.py" -- launchpad
  python "WIPGFX/plans & scripts/military_buildings.py" atlas         hod_landmarks textures
  python "WIPGFX/plans & scripts/military_buildings.py" felucia_atlas hod_felucia_city textures (Felucian villages)
  blender -b --factory-startup --python "WIPGFX/plans & scripts/military_buildings.py" -- models [prefix...]  temple,
                                                                 senate, dock... (only names starting with a prefix)
  python "WIPGFX/plans & scripts/military_buildings.py" landmarks     map/ambient_object.txt
  python "WIPGFX/plans & scripts/military_buildings.py" wire     gfx/entities/buildings.asset (vanilla copy, 2 entities
                                                                 swapped) + gfx/entities/hod_buildings.gfx
"""
import math, os, re, shutil, sys

OUT = "gfx/models/buildings/hod_launchpad"
LM_OUT = "gfx/models/buildings/hod_landmarks"
FLORA_OUT = "gfx/models/mapitems/hod_flora"
VANILLA_ASSET = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/entities/buildings.asset"
S = 512


def textures():
    """Atlas: left half = landing pad top (polar-mapped), right half = metal panels, top strip = lit windows.
    Advanced layout: normal G/A = xy, B = night emission; properties G spec, B metal, A gloss."""
    import numpy as np
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(3)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    grime = ndi.gaussian_filter(rng.random((S, S)), 3)
    grime = (grime - grime.min()) / np.ptp(grime)
    col = np.zeros((S, S, 3), np.float32)
    emi = np.zeros((S, S), np.float32)
    # pad top: centre (128, 256) radius 120 in image space (u 0..0.5)
    r = np.hypot(xx - 128, yy - 256) / 120
    ang = np.arctan2(yy - 256, xx - 128)
    pad = np.array([88, 90, 94], np.float32) * (0.85 + 0.25 * grime[..., None])
    pad = np.where(((r > 0.78) & (r < 0.84))[..., None], [225, 225, 220], pad)                       # white ring
    hazard = (r > 0.88) & (r < 0.98) & (np.sin(ang * 18) > 0)
    pad = np.where(hazard[..., None], [210, 170, 40], pad)                                           # yellow dashes
    pad = np.where(((r > 0.3) & (r < 0.36))[..., None], [225, 225, 220], pad)
    cross = (r < 0.3) & ((np.abs(xx - 128) < 6) | (np.abs(yy - 256) < 6))
    pad = np.where(cross[..., None], [225, 225, 220], pad)
    lights = (r > 0.985) & (r < 1.0) & (np.sin(ang * 24) > 0.6)
    col[:, :256] = pad[:, :256]
    emi[:, :256] = np.where(lights, 255, 0)[:, :256]
    # metal panels (u 0.5..1), window strip on top (v 0.75..1 = image rows 0..128)
    metal = np.array([120, 124, 130], np.float32) * (0.8 + 0.3 * grime[..., None])
    metal *= 1 - 0.3 * (((xx % 64) < 2) | ((yy % 48) < 2))[..., None]
    win = (yy < 128) & ((xx % 24) > 8) & ((xx % 24) < 18) & ((yy % 32) > 10) & ((yy % 32) < 22)
    metal = np.where(win[..., None], [40, 60, 80], metal)
    col[:, 256:] = metal[:, 256:]
    emi[:, 256:] = np.where(win & (rng.random((S, S)) > -1), 200, 0)[:, 256:]
    full = lambda v: np.full((S, S), v, np.float32)
    save_dxt5_mips(np.dstack([np.clip(col, 0, 255), full(255)]), f"{OUT}/hod_launchpad_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), emi, full(128)]), f"{OUT}/hod_launchpad_normal.dds")
    save_dxt5_mips(np.dstack([full(0), full(70), full(90), full(110)]), f"{OUT}/hod_launchpad_properties.dds")
    print("textures written to", OUT)


def launchpad():
    import math
    import bmesh  # type: ignore
    import bpy  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie

    class Mat:
        def __init__(self):
            self.shader = ["PdxMeshAdvancedSnow"]
            self.diff, self.n, self.spec = (["hod_launchpad_diffuse.dds"], ["hod_launchpad_normal.dds"],
                                            ["hod_launchpad_properties.dds"])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")

    def cylinder(cx, cy, z0, z1, r, sides=20, top_pad=False):
        ring = lambda z: [bm.verts.new((cx + r * math.cos(2 * math.pi * i / sides), cy + r * math.sin(2 * math.pi * i / sides), z))
                          for i in range(sides)]
        lo, hi = ring(z0), ring(z1)
        for i in range(sides):
            j = (i + 1) % sides
            f = bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
            for loop, (u, v) in zip(f.loops, ((i / sides, 0), ((i + 1) / sides, 0), ((i + 1) / sides, 0.7), (i / sides, 0.7))):
                loop[uv].uv = (0.5 + u * 0.5, v * 0.7)                 # metal half
        top = bm.faces.new(hi)
        for loop in top.loops:
            x, y = (loop.vert.co.x - cx) / r, (loop.vert.co.y - cy) / r
            loop[uv].uv = (0.25 + x * 0.235, 0.5 + y * 0.47) if top_pad else (0.75, 0.3)
        bot = bm.faces.new(lo[::-1])
        for loop in bot.loops:
            loop[uv].uv = (0.75, 0.3)

    def box(x0, y0, z0, x1, y1, z1, windows=False):
        g = bmesh.ops.create_cube(bm, size=1.0)
        for v in g["verts"]:
            v.co.x, v.co.y, v.co.z = (x0 + (v.co.x + .5) * (x1 - x0), y0 + (v.co.y + .5) * (y1 - y0), z0 + (v.co.z + .5) * (z1 - z0))
        for f in {f for v in g["verts"] for f in v.link_faces}:
            for loop in f.loops:
                c = loop.vert.co
                along = (c.x - x0) / max(x1 - x0, 1e-6) if abs(f.normal.y) > 0.5 else (c.y - y0) / max(y1 - y0, 1e-6)
                h = (c.z - z0) / max(z1 - z0, 1e-6)
                loop[uv].uv = (0.5 + along * 0.5, (0.78 + h * 0.2) if windows else h * 0.7)

    # three pads on pillars of different heights, each on a squat plinth
    for cx, cy, h, pr in ((0.0, 0.0, 1.1, 0.85), (1.3, 0.65, 0.8, 0.6), (-0.95, 0.9, 0.62, 0.5)):
        cylinder(cx, cy, 0.0, 0.08, 0.38, 12)
        cylinder(cx, cy, 0.08, h, 0.16 + pr * 0.08, 10)
        cylinder(cx, cy, h, h + 0.08, pr, 24, top_pad=True)
    box(0.7, -1.15, 0.0, 1.05, -0.8, 1.25)                     # control tower
    box(0.62, -1.23, 1.25, 1.13, -0.72, 1.5, windows=True)     # tower cab
    box(0.1, -0.95, 1.02, 0.72, -0.85, 1.08)                   # walkway to the main pad
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("hod_launchpad")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("hod_launchpad", me)
    bpy.context.scene.collection.objects.link(obj)
    mat = bie.create_shader(Mat(), "hod_launchpad", os.path.abspath(OUT))
    mat[PDX_SHADER] = "PdxMeshAdvancedSnow"
    me.materials.append(mat)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    m = obj.modifiers.new("t", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=m.name)
    bie.export_meshfile(os.path.abspath(f"{OUT}/hod_launchpad.mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
    print(f"launchpad: {len(me.polygons)} tris")


# hod_landmarks atlas: 4 x 4 cells (u0, v0, u1, v1), v = 1 is the top image row. Top row: walls with lit window rows
# (night emission); second row: the same materials plain; then bronze, deck plating, Geonosis rock, dark panelling.
_cell = lambda col, row: (col * 0.25, 1 - (row + 1) * 0.25, (col + 1) * 0.25, 1 - row * 0.25)
SAND_WIN, METAL_WIN, MOSS_WIN, RUST_WIN = (_cell(i, 0) for i in range(4))
SAND, METAL, MOSS, RUST = (_cell(i, 1) for i in range(4))
BRONZE, DECK, ROCK, DARK = (_cell(i, 2) for i in range(4))
DARK_WIN, LEAF, VERDI, REDROCK = (_cell(i, 3) for i in range(4))
BANNER, BANNER_POLE = (0.0, 0.125, 1.0, 1.0), (0.0, 0.0, 1.0, 0.12)   # hod_cis_banner texture: banner above, pole below
# plain (no windows) materials of the last row: RGB, spec, metalness
LM_PLAIN = {"LEAF": ((62, 90, 46), 20, 0),          # Kachirho canopy
            "VERDI": ((96, 140, 118), 90, 120),     # Theed palace domes: green copper
            "REDROCK": ((132, 66, 50), 30, 0)}      # Korriban: dark red rock
LM_S = 1024
# Felucian villages (city style 9): their own 2 x 2 atlas, same layout as hod_landmarks (normal B = night emission).
# Felucians live among the giant fungi: huts and glowing pods on platforms around mushroom stalks
_fcell = lambda col, row: (col * 0.5, 1 - (row + 1) * 0.5, (col + 1) * 0.5, 1 - row * 0.5)
FCAP, FSTALK, FPOD, FHUT = _fcell(0, 0), _fcell(1, 0), _fcell(0, 1), _fcell(1, 1)
# material: (base RGB, window RGB, spec, metalness); colours from the reference stills (Wookieepedia)
LM_MATS = {
    "SAND": ((214, 196, 160), (70, 58, 44), 60, 0),        # Jedi Temple sandstone
    "METAL": ((186, 194, 204), (34, 46, 62), 60, 60),      # Senate / dock / Tipoca pale blue-grey
    "MOSS": ((108, 116, 96), (60, 52, 34), 40, 0),         # Massassi temple: weathered grey-green stone
    "RUST": ((158, 116, 82), (52, 38, 28), 50, 20),        # Jabba's palace: sand-blasted rust-tan
    "DARK": ((92, 97, 106), (30, 36, 44), 80, 120),        # Sundari dome: dark grey panelling
}


def atlas():
    """Shared atlas for every procedural landmark (temple, senate, dock, ion cannon, Tipoca, arena, Massassi temple,
    Jabba's palace, Sundari). Advanced layout like the launch pad: normal B = night emission."""
    import numpy as np
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    os.makedirs(LM_OUT, exist_ok=True)
    N = LM_S
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    grime = ndi.gaussian_filter(rng.random((N, N)), 2)
    grime = ((grime - grime.min()) / np.ptp(grime))[..., None]
    blotch = ndi.gaussian_filter(rng.random((N, N)), 12)
    blotch = ((blotch - blotch.min()) / np.ptp(blotch))[..., None]
    col = np.zeros((N, N, 3), np.float32)
    emi = np.zeros((N, N), np.float32)
    spec = np.full((N, N), 60, np.float32)
    metal = np.zeros((N, N), np.float32)

    def px(rect):   # image slice of a uv rect
        u0, v0, u1, v1 = rect
        return slice(int(round((1 - v1) * N)), int(round((1 - v0) * N))), slice(int(round(u0 * N)), int(round(u1 * N)))

    win = ((xx % 16) > 5) & ((xx % 16) < 11) & ((yy % 32) > 12) & ((yy % 32) < 24)
    lit = win & (ndi.uniform_filter(rng.random((N, N)), 6) > 0.47)            # some windows dark at night
    courses = ((yy % 32) < 2)[..., None]
    panels = (((xx % 64) < 2) | ((yy % 40) < 2))[..., None]
    for name, (base, wcol, sp, me) in LM_MATS.items():
        tone = np.array(base, np.float32) * (0.88 + 0.2 * grime)
        if name in ("SAND", "MOSS"):
            tone *= 1 - 0.12 * courses                                          # masonry courses
        else:
            tone *= 1 - 0.18 * panels                                           # panel seams
        if name == "MOSS":
            tone = tone * (1 - 0.35 * blotch) + np.array([70, 92, 52], np.float32) * 0.35 * blotch   # moss patches
        if name == "RUST":
            tone *= 0.85 + 0.3 * ndi.gaussian_filter(rng.random((N, N)), (8, 1))[..., None]          # streaks
        for rect, windows in ((globals()[name + "_WIN"] if name + "_WIN" in globals() else None, True),
                              (globals()[name], False)):
            if rect is None:
                continue
            r, c = px(rect)
            col[r, c] = np.where(win[r, c][..., None], wcol, tone[r, c]) if windows else tone[r, c]
            emi[r, c] = np.where(lit[r, c], 230, 0) if windows else 0
            spec[r, c], metal[r, c] = sp, me
    for name, (base, sp, me) in LM_PLAIN.items():
        r, c = px(globals()[name])
        col[r, c] = np.array(base, np.float32) * (0.75 + 0.35 * grime[r, c]) * (0.85 + 0.3 * blotch[r, c])
        spec[r, c], metal[r, c] = sp, me
    r, c = px(BRONZE)
    col[r, c] = np.array([184, 142, 74], np.float32) * (0.8 + 0.3 * grime[r, c])
    spec[r, c], metal[r, c] = 140, 200
    r, c = px(ROCK)                                                            # Geonosis: ochre rock, vertical flutes
    flutes = 0.8 + 0.25 * np.sin(xx[r, c] * 0.35 + 3 * grime[r, c, 0])
    col[r, c] = np.array([176, 108, 66], np.float32) * (0.75 + 0.35 * grime[r, c]) * flutes[..., None]
    spec[r, c] = 30
    r, c = px(DECK)
    ly, lx = yy[r, c] - yy[r, c].min(), xx[r, c] - xx[r, c].min()
    h, w = ly.max() + 1, lx.max() + 1
    edge = np.minimum(np.minimum(ly, h - 1 - ly), np.minimum(lx, w - 1 - lx))
    deck = np.array([96, 99, 104], np.float32) * (0.85 + 0.25 * grime[r, c])
    deck = np.where(((edge < 14) & (((lx + ly) % 24) < 12))[..., None], [205, 165, 40], deck)   # hazard stripes
    deck = np.where(((edge > 20) & (edge < 24))[..., None], [220, 220, 215], deck)
    col[r, c] = deck
    emi[r, c] = np.where((edge < 4) & ((lx + ly) % 32 < 4), 255, 0)                              # edge beacons
    full = lambda v: np.full((N, N), v, np.float32)
    save_dxt5_mips(np.dstack([np.clip(col, 0, 255), full(255)]), f"{LM_OUT}/hod_landmarks_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), emi, full(128)]), f"{LM_OUT}/hod_landmarks_normal.dds")
    save_dxt5_mips(np.dstack([full(0), spec, metal, full(110)]), f"{LM_OUT}/hod_landmarks_properties.dds")
    for kind in ("normal", "properties"):                  # the sandcrawler map prop uses the same atlas...
        shutil.copy2(f"{LM_OUT}/hod_landmarks_{kind}.dds", f"{FLORA_OUT}/hod_flora_53_sandcrawler_{kind}.dds")
    bright = np.dstack([np.clip(col * 1.7 + 12, 0, 255), full(255)])   # ...brightened: props are lit darker in game
    save_dxt5_mips(bright, f"{FLORA_OUT}/hod_flora_53_sandcrawler_diffuse.dds")
    print("atlas written to", LM_OUT)


def felucia_atlas():
    """hod_felucia_city: violet spotted cap, pale ribbed stalk, orange pods and woven huts with lit openings."""
    import numpy as np
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    N = 512
    rng = np.random.default_rng(9)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    mott = ndi.gaussian_filter(rng.random((N, N)), 4)
    mott = ((mott - mott.min()) / np.ptp(mott))[..., None]
    col = np.zeros((N, N, 3), np.float32)
    emi = np.zeros((N, N), np.float32)
    h = N // 2
    cells = {FCAP: (150, 60, 190), FSTALK: (215, 200, 205), FPOD: (240, 130, 35), FHUT: (150, 112, 70)}
    for rect, base in cells.items():
        u0, v0, u1, v1 = rect
        r, c = slice(int(round((1 - v1) * N)), int(round((1 - v0) * N))), slice(int(round(u0 * N)), int(round(u1 * N)))
        ly, lx = yy[r, c] - yy[r, c].min(), xx[r, c] - xx[r, c].min()
        tone = np.array(base, np.float32) * (0.75 + 0.4 * mott[r, c])
        if rect == FCAP:                                    # pale spots
            for _ in range(30):
                cy, cx, rr = rng.uniform(0, h), rng.uniform(0, h), rng.uniform(6, 14)
                m = np.clip((rr - np.hypot(ly - cy, lx - cx)) / 2, 0, 1)[..., None]
                tone = tone * (1 - m) + np.array([240, 215, 120], np.float32) * m
        if rect == FSTALK:                                  # vertical ribs
            tone *= (0.85 + 0.15 * np.sin(lx * 0.4))[..., None]
        if rect == FHUT:                                    # woven bands
            tone *= (0.8 + 0.2 * ((ly % 12) < 6) * ((lx % 12) < 6) + 0.1 * ((ly % 12) >= 6))[..., None]
        if rect in (FPOD, FHUT):                            # openings in a row along the lower third, lit at night
            win = ((lx % 48) > 18) & ((lx % 48) < 30) & (ly > h * 0.55) & (ly < h * 0.8)
            tone = np.where(win[..., None], [60, 30, 20], tone)
            emi[r, c] = np.where(win, 220, 0)
        col[r, c] = tone
    full = lambda v: np.full((N, N), v, np.float32)
    save_dxt5_mips(np.dstack([np.clip(col, 0, 255), full(255)]), f"{LM_OUT}/hod_felucia_city_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), emi, full(128)]), f"{LM_OUT}/hod_felucia_city_normal.dds")
    save_dxt5_mips(np.dstack([full(0), full(40), full(0), full(90)]), f"{LM_OUT}/hod_felucia_city_properties.dds")
    print("felucia atlas written to", LM_OUT)


def models(*only):
    """Blender: build hod_jedi_temple, hod_senate and hod_spacedock (z up, origin on the ground) and export .mesh.
    `only`: name prefixes to build (e.g. hod_raxus_senate hod_rax_city); default all."""
    import bmesh  # type: ignore
    import bpy  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie

    class Mat:
        def __init__(self, shader="PdxMeshAdvancedSnow", tex="hod_landmarks"):
            self.shader = [shader]
            self.diff, self.n, self.spec = [f"{tex}_diffuse.dds"], [f"{tex}_normal.dds"], [f"{tex}_properties.dds"]

    class Kit:
        def __init__(self, bm, uv):
            self.bm, self.uv = bm, uv

        def put(self, f, uvs, rect):
            u0, v0, u1, v1 = rect
            for loop, (a, b) in zip(f.loops, uvs):
                loop[self.uv].uv = (u0 + 0.01 + a * (u1 - u0 - 0.02), v0 + 0.01 + b * (v1 - v0 - 0.02))

        def lathe(self, profile, rects, sides=16, cx=0.0, cy=0.0, rot=0.0, cap=None, sy=1.0, jitter=0.0):
            """Surface of revolution through (r, z) points; rects[i] textures segment i (u around, v along).
            r == 0 at an end closes it to a point; `cap` rect closes flat ends. sy squashes it into an oval along y,
            jitter roughens the radius per vertex (rock)."""
            bm = self.bm
            ang = [rot + 2 * math.pi * i / sides for i in range(sides)]
            rough = lambda i, k: 1 + jitter * math.sin(i * 2.71 + k * 1.37 + cx * 3.1) * math.cos(i * 1.13 - k * 0.7)
            rings = [[bm.verts.new((cx, cy, z))] * sides if r == 0 else
                     [bm.verts.new((cx + r * rough(i, k) * math.cos(a), cy + sy * r * rough(i, k) * math.sin(a), z))
                      for i, a in enumerate(ang)] for k, (r, z) in enumerate(profile)]
            for k in range(len(rings) - 1):
                lo, hi = rings[k], rings[k + 1]
                rect = rects[k] if isinstance(rects, list) else rects
                for i in range(sides):
                    j = (i + 1) % sides
                    a, b = i / sides, (i + 1) / sides
                    if lo[i] is lo[j]:
                        f, uvs = bm.faces.new((lo[i], hi[j], hi[i])), (((a + b) / 2, 0), (b, 1), (a, 1))
                    elif hi[i] is hi[j]:
                        f, uvs = bm.faces.new((lo[i], lo[j], hi[i])), ((a, 0), (b, 0), ((a + b) / 2, 1))
                    else:
                        f, uvs = bm.faces.new((lo[i], lo[j], hi[j], hi[i])), ((a, 0), (b, 0), (b, 1), (a, 1))
                    self.put(f, uvs, rect)
            disc = [(0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)) for a in ang]
            if cap and len(set(rings[0])) > 1:
                self.put(bm.faces.new(rings[0][::-1]), disc[::-1], cap)
            if cap and len(set(rings[-1])) > 1:
                self.put(bm.faces.new(rings[-1]), disc, cap)

        def box(self, x0, y0, z0, x1, y1, z1, rect, top=None):
            bm = self.bm
            v = {(i, j, k): bm.verts.new((x1 if i else x0, y1 if j else y0, z1 if k else z0))
                 for i in (0, 1) for j in (0, 1) for k in (0, 1)}
            quads = [((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)), ((1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),
                     ((0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
                     ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)), ((0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0))]
            for n, q in enumerate(quads):
                self.put(bm.faces.new([v[c] for c in q]), ((0, 0), (1, 0), (1, 1), (0, 1)), top if n == 4 and top else rect)

        def tube(self, p0, p1, r, rect, sides=10, r1=None):
            """Cylinder (cone if r1) between two points (any direction), closed with a flat end at p1."""
            from mathutils import Vector  # type: ignore
            p0, p1 = Vector(p0), Vector(p1)
            d = (p1 - p0).normalized()
            u = d.cross(Vector((0, 0, 1))).normalized()
            w = d.cross(u)
            ring = lambda p: [self.bm.verts.new(p + r * (math.cos(2 * math.pi * i / sides) * u + math.sin(2 * math.pi * i / sides) * w))
                              for i in range(sides)]
            lo = ring(p0)
            r = r if r1 is None else r1
            hi = ring(p1)
            for i in range(sides):
                j = (i + 1) % sides
                self.put(self.bm.faces.new((lo[i], lo[j], hi[j], hi[i])),
                         ((i / sides, 0), ((i + 1) / sides, 0), ((i + 1) / sides, 1), (i / sides, 1)), rect)
            self.put(self.bm.faces.new(hi), [(0.5, 0.5)] * sides, rect)

        def prism(self, profile, x0, x1, rect, end=None):
            """Side profile [(y, z), ...] (counter-clockwise seen from +x) extruded across x0..x1."""
            bm = self.bm
            a = [bm.verts.new((x0, y, z)) for y, z in profile]
            b = [bm.verts.new((x1, y, z)) for y, z in profile]
            n = len(profile)
            for i in range(n):
                j = (i + 1) % n
                self.put(bm.faces.new((a[i], a[j], b[j], b[i])), ((0, 0), (1, 0), (1, 1), (0, 1)), rect)
            ys, zs = [y for y, _ in profile], [z for _, z in profile]
            uv = [((y - min(ys)) / (max(ys) - min(ys)), (z - min(zs)) / (max(zs) - min(zs))) for y, z in profile]
            self.put(bm.faces.new(a[::-1]), uv[::-1], end or rect)
            self.put(bm.faces.new(b), uv, end or rect)

        def arch(self, x0, x1, y0, y1, z0, rect, segs=8):
            """Hangar roof: half-cylinder across x, running along y, standing on z0; `rect` on the end walls."""
            bm = self.bm
            cx, r = (x0 + x1) / 2, (x1 - x0) / 2
            pts = [(cx - r * math.cos(math.pi * i / segs), z0 + r * math.sin(math.pi * i / segs)) for i in range(segs + 1)]
            front = [bm.verts.new((x, y0, z)) for x, z in pts]
            back = [bm.verts.new((x, y1, z)) for x, z in pts]
            for i in range(segs):
                self.put(bm.faces.new((front[i], front[i + 1], back[i + 1], back[i])),
                         ((i / segs, 0), ((i + 1) / segs, 0), ((i + 1) / segs, 1), (i / segs, 1)), METAL)
            end = [((x - x0) / (x1 - x0), (z - z0) / r) for x, z in pts]
            self.put(bm.faces.new(front), end, rect)
            self.put(bm.faces.new(back[::-1]), end[::-1], rect)

    SKIRT = 2.5     # landmark walls run this far below the origin: no gap under them on uneven or lower ground

    def build(name, geometry, shader="PdxMeshAdvancedSnow", out=LM_OUT, tex="hod_landmarks"):
        if only and not name.startswith(only):
            return
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bm = bmesh.new()
        geometry(Kit(bm, bm.loops.layers.uv.new("UVMap")))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        mat = bie.create_shader(Mat(shader, tex), name, os.path.abspath(out))
        mat[PDX_SHADER] = shader
        me.materials.append(mat)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        m = obj.modifiers.new("t", "TRIANGULATE")
        bpy.ops.object.modifier_apply(modifier=m.name)
        bie.export_meshfile(os.path.abspath(f"{out}/{name}.mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
        print(f"{name}: {len(me.polygons)} tris")

    def temple(k):
        # canon Jedi Temple: stepped sandstone ziggurat, flat roof, four corner spires and a taller central one.
        # Square = 4-sided lathe turned 45 degrees (radius = half side * sqrt 2); the plinth starts below ground
        # so uneven terrain never shows a gap under it.
        q = math.sqrt(2)
        k.lathe([(1.75 * q, -SKIRT), (1.75 * q, 0.06), (1.62 * q, 0.06), (1.38 * q, 0.42), (1.26 * q, 0.42),
                 (1.06 * q, 0.74), (0.96 * q, 0.74), (0.84 * q, 0.98)],
                [SAND, SAND, SAND_WIN, SAND, SAND_WIN, SAND, SAND_WIN], sides=4, rot=math.pi / 4, cap=SAND)
        for x, y in ((-0.56, -0.56), (0.56, -0.56), (-0.56, 0.56), (0.56, 0.56)):
            k.lathe([(0.15, 0.98), (0.1, 2.0), (0.14, 2.06), (0.14, 2.12), (0.05, 2.18), (0.0, 2.3)],
                    [SAND_WIN, BRONZE, BRONZE, BRONZE, BRONZE], sides=12, cx=x, cy=y)
        k.lathe([(0.22, 0.98), (0.14, 2.45), (0.2, 2.53), (0.2, 2.6), (0.07, 2.68), (0.015, 3.0), (0.0, 3.05)],
                [SAND_WIN, BRONZE, BRONZE, BRONZE, BRONZE, BRONZE], sides=12)      # fluted spires, flared crowns
        k.box(-0.42, -2.6, -SKIRT, 0.42, -1.75, 0.06, SAND, top=SAND)       # processional way out the front

    def senate(k):
        # Senate Rotunda: mushroom dome on a stem, plaza ringed with statues
        k.lathe([(2.05, -SKIRT), (2.05, 0.06)], METAL, sides=40, cap=METAL)
        k.lathe([(0.78, 0.06), (0.64, 0.36), (0.7, 0.52), (1.22, 0.74), (1.58, 0.93), (1.58, 1.02), (1.32, 1.14),
                 (0.82, 1.24), (0.0, 1.28)],
                [METAL_WIN, METAL, METAL, METAL, METAL_WIN, METAL, METAL, METAL], sides=40)
        for i in range(16):
            a = 2 * math.pi * (i + 0.5) / 16
            k.lathe([(0.05, 0.06), (0.05, 0.3), (0.0, 0.36)], [METAL, METAL], sides=6,
                    cx=1.86 * math.cos(a), cy=1.86 * math.sin(a))

    def dock(k):
        # space dock: shore deck with hangar + tower (y > 0), pier out to sea (-y, like vanilla navalbase_01) to a
        # landing pad between two ship gantries
        k.box(-1.7, -0.25, -0.2, 1.7, 1.25, 0.1, METAL, top=DECK)
        k.box(-1.45, 0.05, 0.1, -0.15, 1.15, 0.22, METAL_WIN)
        k.arch(-1.45, -0.15, 0.05, 1.15, 0.22, METAL_WIN)
        k.lathe([(0.16, 0.1), (0.12, 1.1), (0.28, 1.18), (0.28, 1.32), (0.12, 1.4), (0.0, 1.5)],
                [METAL, METAL, METAL_WIN, METAL, METAL], sides=10, cx=1.0, cy=0.7)
        k.box(0.2, 0.3, 0.1, 0.75, 1.1, 0.42, METAL_WIN)                    # workshops
        k.box(-0.28, -3.3, -0.05, 0.28, -0.25, 0.1, METAL, top=DECK)       # pier
        k.lathe([(0.62, -0.05), (0.62, 0.12)], METAL, sides=24, cy=-3.4, cap=DECK)
        for s in (-1, 1):
            for y in (-3.0, -2.0, -1.0):
                k.box(s * 1.25 - 0.05, y - 0.05, -0.1, s * 1.25 + 0.05, y + 0.05, 0.95, METAL)        # gantry post
                k.box(min(s * 0.28, s * 1.25), y - 0.035, 0.82, max(s * 0.28, s * 1.25), y + 0.035, 0.9, METAL)  # arm
            k.box(s * 1.25 - 0.06, -3.1, 0.9, s * 1.25 + 0.06, -0.9, 0.98, METAL_WIN)              # top beam

    def ion_cannon(k):
        # anti-air: ion cannon emplacement (Stars in Shadow defense base): dome turret with a long barrel on a sloped
        # base, walled round pad with buttresses, gatehouse, sensor domes
        k.lathe([(2.0, -0.4), (2.0, 0.05)], METAL, sides=32, cap=DECK)
        k.lathe([(1.95, 0.05), (1.95, 0.3), (1.78, 0.3), (1.78, 0.05)], [METAL, METAL, METAL], sides=32)   # ring wall
        for i in range(6):
            a = 2 * math.pi * (i + 0.5) / 6
            k.lathe([(0.3, 0.05), (0.27, 0.42), (0.16, 0.46)], [METAL, METAL], sides=4, rot=a + math.pi / 4,
                    cx=1.86 * math.cos(a), cy=1.86 * math.sin(a), cap=METAL)                           # buttress
        k.box(-0.4, -2.2, 0.0, 0.4, -1.65, 0.55, METAL_WIN, top=METAL)                                # gatehouse
        k.lathe([(1.05, 0.05), (0.95, 0.28), (0.72, 0.46), (0.62, 0.5)], [METAL, METAL_WIN, METAL], sides=24)
        k.lathe([(0.6, 0.5), (0.68, 0.64), (0.67, 0.8), (0.59, 0.96), (0.43, 1.1), (0.22, 1.19), (0.0, 1.22)],
                [METAL, METAL_WIN, METAL, METAL, METAL, METAL], sides=24)                              # turret dome
        k.tube((-0.28, 0.28, 0.98), (-0.5, 0.5, 1.12), 0.15, METAL, sides=8)                          # mantlet
        k.tube((-0.45, 0.45, 1.09), (-1.25, 1.25, 1.6), 0.07, METAL)                                  # barrel
        k.tube((-1.15, 1.15, 1.54), (-1.32, 1.32, 1.65), 0.1, BRONZE)                                 # muzzle
        for x, y, r in ((1.1, 0.55, 0.16), (1.25, -0.15, 0.13), (-0.9, -1.0, 0.14)):
            k.lathe([(r, 0.05), (r * 0.8, r * 0.75), (0.0, r)], [METAL, METAL], sides=12, cx=x, cy=y)  # sensor domes
        k.lathe([(0.06, 0.3), (0.06, 0.55), (0.18, 0.6), (0.17, 0.72), (0.0, 0.8)], [METAL, METAL, METAL, METAL],
                sides=12, cy=1.86)                                                                    # radar on the wall

    def tipoca(k):
        # Tipoca City (Kamino): pale saucer domes on stilts over the sea, linked by walkways, needle spires on some
        domes = [(0.0, 0.0, 0.8, 0.75, True), (1.45, 0.35, 0.55, 0.7, True), (-1.3, 0.55, 0.5, 0.68, False),
                 (0.35, 1.45, 0.48, 0.72, False), (-0.45, -1.4, 0.55, 0.66, True), (1.15, -1.15, 0.42, 0.7, False)]
        for x, y, r, z, spire in domes:
            for i in range(3):
                a = 2 * math.pi * i / 3 + x
                k.tube((x + 0.45 * r * math.cos(a), y + 0.45 * r * math.sin(a), -SKIRT),
                       (x + 0.45 * r * math.cos(a), y + 0.45 * r * math.sin(a), z), 0.09, METAL, sides=8)     # stilts
            k.lathe([(0.3 * r, z), (r, z + 0.18), (r, z + 0.26), (0.78 * r, z + 0.42), (0.42 * r, z + 0.54), (0.0, z + 0.58)],
                    [METAL, METAL_WIN, METAL, METAL, METAL], sides=24, cx=x, cy=y)
            if spire:
                k.lathe([(0.1, z + 0.5), (0.05, z + 1.0), (0.0, z + 1.45)], [METAL, METAL], sides=8, cx=x, cy=y)
        for i, j in ((0, 1), (0, 2), (0, 3), (0, 4), (1, 5), (4, 5)):
            (x0, y0, _, z0, _), (x1, y1, _, z1, _) = domes[i], domes[j]
            z = min(z0, z1) + 0.17
            k.tube((x0, y0, z), (x1, y1, z), 0.06, METAL, sides=6)                                       # walkways

    def arena(k):
        # Petranaki Arena (Geonosis): oval bowl cut into a fluted ochre mesa, tiered stands, sand floor; hive spires
        k.lathe([(1.95, -SKIRT), (1.95, 0.0), (1.8, 0.9), (1.66, 1.2), (1.3, 1.22), (1.28, 1.02), (1.14, 0.98),
                 (1.12, 0.78), (0.98, 0.74), (0.96, 0.52), (0.84, 0.48), (0.82, 0.22), (0.0, 0.2)],
                [ROCK, ROCK, ROCK, ROCK, ROCK, ROCK, ROCK, ROCK, ROCK, ROCK, ROCK, SAND], sides=32, sy=0.78, jitter=0.04)
        for x, y, h in ((-1.9, 1.3, 2.4), (1.95, 1.2, 1.9), (2.1, -0.9, 1.5), (-2.0, -1.0, 1.7)):
            k.lathe([(0.34, -SKIRT), (0.34, 0.0), (0.26, h * 0.4), (0.17, h * 0.75), (0.06, h * 0.95), (0.0, h)],
                    ROCK, sides=10, cx=x, cy=y, jitter=0.12)                                              # hive spires

    def massassi(k):
        # Great Temple of the Massassi (Yavin 4): steep stepped pyramid of mossy stone, stepped crown; smaller pyramid
        q = math.sqrt(2)
        steps = [(1.55, 0.0), (1.38, 0.38), (1.22, 0.38), (1.05, 0.76), (0.92, 0.76), (0.76, 1.14), (0.65, 1.14),
                 (0.5, 1.52), (0.41, 1.52), (0.32, 1.9), (0.25, 1.9), (0.21, 2.25), (0.14, 2.25), (0.1, 2.5)]
        k.lathe([(1.55 * q, -SKIRT)] + [(a * q, z) for a, z in steps],
                [MOSS] + [MOSS_WIN if i % 2 == 0 else MOSS for i in range(len(steps) - 1)],
                sides=4, rot=math.pi / 4, cap=MOSS)
        k.lathe([(0.55 * q, -SKIRT), (0.55 * q, 0.0), (0.42 * q, 0.35), (0.34 * q, 0.35), (0.2 * q, 0.75), (0.1 * q, 0.9)],
                [MOSS, MOSS_WIN, MOSS, MOSS_WIN, MOSS], sides=4, rot=math.pi / 4, cx=-1.95, cy=1.5, cap=MOSS)
        k.box(-0.3, -2.2, -SKIRT, 0.3, -1.4, 0.12, MOSS, top=MOSS)                                  # landing apron

    def jabba(k):
        # Jabba's palace (Tatooine): squat rust-tan drum with stacked flared roof rings, slim domed tower beside it
        k.lathe([(1.0, -SKIRT), (1.0, 0.0), (1.0, 0.85), (1.16, 0.9), (1.16, 0.96), (0.86, 1.02), (0.86, 1.12), (0.98, 1.16),
                 (0.98, 1.21), (0.7, 1.27), (0.7, 1.35), (0.45, 1.4), (0.2, 1.47), (0.0, 1.49)],
                [RUST, RUST_WIN, RUST, RUST, RUST, RUST, RUST, RUST, RUST, RUST, RUST, RUST, RUST], sides=28)
        k.lathe([(0.3, -SKIRT), (0.3, 0.0), (0.28, 1.6), (0.38, 1.66), (0.38, 1.72), (0.3, 1.78), (0.32, 1.92), (0.2, 2.03),
                 (0.0, 2.08)], [RUST, RUST_WIN, RUST, RUST, RUST, RUST_WIN, RUST, RUST], sides=16, cx=1.05, cy=0.5)
        k.lathe([(0.42, -SKIRT), (0.42, 0.0), (0.42, 0.55), (0.3, 0.72), (0.0, 0.8)], [RUST, RUST, RUST, RUST],
                sides=16, cx=1.1, cy=-0.45)                                                               # lower dome

    def sundari(k):
        # Sundari (Mandalore): huge dark grey panelled dome on a flared base ring
        prof = [(2.05, -SKIRT), (2.05, 0.05), (1.96, 0.12), (1.82, 0.15)]
        for i in range(9):
            a = math.pi / 2 * i / 8
            prof.append((1.78 * math.cos(a), 0.15 + 1.45 * math.sin(a)))
        k.lathe(prof, [DARK, DARK, DARK, DARK_WIN, DARK_WIN, DARK, DARK_WIN, DARK, DARK, DARK, DARK, DARK], sides=36)

    import random

    def kam_city(kit, band, rng):
        # Kamino stilt city: 1-3 small pale saucer domes on stilts (Tipoca in miniature), bigger/more downtown
        for _ in range(rng.randint(1, 1 + band // 2)):
            x, y = rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7)
            r, z = rng.uniform(0.22, 0.3) + 0.06 * band, rng.uniform(0.35, 0.5)
            for i in range(3):
                a = 2 * math.pi * i / 3
                k_ = (x + 0.45 * r * math.cos(a), y + 0.45 * r * math.sin(a))
                kit.tube((k_[0], k_[1], -0.5), (k_[0], k_[1], z), 0.04, METAL, sides=5)
            kit.lathe([(0.3 * r, z), (r, z + 0.1), (r, z + 0.15), (0.75 * r, z + 0.25), (0.0, z + 0.32)],
                      [METAL, METAL_WIN, METAL, METAL], sides=14, cx=x, cy=y)
            if band >= 3 and rng.random() < 0.6:
                kit.lathe([(0.04, z + 0.28), (0.0, z + 0.28 + 0.25 * band)], [METAL], sides=6, cx=x, cy=y)

    def man_city(kit, band, rng):
        # Mandalore: small dark domes on flared rings (Sundari in miniature) and a few squat towers
        for _ in range(rng.randint(1, 1 + band // 2)):
            x, y = rng.uniform(-0.65, 0.65), rng.uniform(-0.65, 0.65)
            r = rng.uniform(0.2, 0.3) + 0.08 * band
            prof = [(r * 1.15, -0.5), (r * 1.15, 0.03), (r * 1.02, 0.07)]
            prof += [(r * math.cos(math.pi / 2 * i / 5), 0.07 + 0.85 * r * math.sin(math.pi / 2 * i / 5)) for i in range(6)]
            kit.lathe(prof, [DARK, DARK, DARK_WIN, DARK_WIN, DARK, DARK, DARK, DARK], sides=16, cx=x, cy=y)
        if band >= 2:
            x, y = rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6)
            h = 0.25 * band
            kit.lathe([(0.12, -0.5), (0.12, h), (0.0, h + 0.08)], [DARK_WIN, DARK], sides=8, cx=x, cy=y)

    def geo_city(kit, band, rng):
        # Geonosis hives: clusters of fluted rock spires, taller downtown
        for _ in range(rng.randint(2, 2 + band)):
            x, y = rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7)
            h = rng.uniform(0.4, 0.7) * (0.6 + 0.45 * band)
            r = rng.uniform(0.12, 0.2) + 0.03 * band
            kit.lathe([(r, -0.5), (r, 0.0), (r * 0.75, h * 0.4), (r * 0.45, h * 0.8), (0.0, h)], ROCK,
                      sides=8, cx=x, cy=y, jitter=0.15)

    def nab_city(kit, band, rng):
        # Naboo (Theed style), a mix of five building types: domed block, colonnaded hall with corner cupolas,
        # round rotunda, slim campanile, and downtown a palace block with a big central dome
        def dome(x, y, z, r, rect=VERDI):
            kit.lathe([(r, z), (r, z + 0.04), (0.72 * r, z + 0.04 + 0.5 * r), (0.0, z + 0.04 + 0.78 * r)],
                      [SAND, rect, rect], sides=12, cx=x, cy=y)

        def domed_block(x, y):
            w, d, h = rng.uniform(0.16, 0.26) + 0.03 * band, rng.uniform(0.14, 0.22) + 0.02 * band, 0.16 + 0.07 * band
            kit.box(x - w, y - d, -0.5, x + w, y + d, h, SAND_WIN, top=SAND)
            dome(x, y, h, min(w, d) * 0.8)

        def colonnade(x, y):
            w, d, h = rng.uniform(0.3, 0.45), rng.uniform(0.12, 0.18), 0.14 + 0.04 * band
            kit.box(x - w, y - d, -0.5, x + w, y + d, h, SAND, top=SAND)
            for i in range(6):                                                   # columns along the front
                cx_ = x - w + (i + 0.5) * 2 * w / 6
                kit.lathe([(0.025, h * 0.15), (0.025, h)], [SAND], sides=6, cx=cx_, cy=y - d - 0.05)
            kit.box(x - w, y - d - 0.08, h, x + w, y - d, h + 0.04, SAND)
            for sx in (-1, 1):
                dome(x + sx * (w - 0.08), y, h, 0.08)

        def rotunda(x, y):
            r, h = rng.uniform(0.14, 0.2) + 0.02 * band, 0.15 + 0.06 * band
            kit.lathe([(r, -0.5), (r, h)], [SAND_WIN], sides=14, cx=x, cy=y)
            dome(x, y, h, r * 1.05)

        def campanile(x, y):
            h = 0.45 + 0.18 * band
            kit.lathe([(0.07, -0.5), (0.07, h), (0.1, h + 0.04), (0.06, h + 0.12), (0.0, h + 0.17)],
                      [SAND_WIN, SAND, VERDI, VERDI], sides=8, cx=x, cy=y)

        def palace(x, y):
            w, d, h = 0.42, 0.3, 0.3 + 0.06 * band
            kit.box(x - w, y - d, -0.5, x + w, y + d, h, SAND_WIN, top=SAND)
            kit.lathe([(0.2, h), (0.2, h + 0.12)], [SAND_WIN], sides=14, cx=x, cy=y)       # drum
            dome(x, y, h + 0.12, 0.22)
            for sx in (-1, 1):
                dome(x + sx * 0.3, y, h, 0.1)

        kinds = [domed_block, colonnade, rotunda] + [campanile] * (band >= 2) + [palace] * (band >= 4)
        spots = [(-0.45, -0.45), (0.45, -0.4), (-0.4, 0.45), (0.42, 0.42), (0.0, 0.0)]
        rng.shuffle(spots)
        for x, y in spots[:rng.randint(1, 1 + band // 2)]:
            rng.choice(kinds)(x + rng.uniform(-0.1, 0.1), y + rng.uniform(-0.1, 0.1))

    def fel_city(kit, band, rng):
        # Felucian village: woven huts and glowing pods on ring platforms around a giant mushroom's stalk, more
        # platforms and a rope bridge to a second dwelling downtown; small pod huts on the ground at the edge
        def pod(x, y, z, r):
            kit.lathe([(r, z - 0.5 if z <= 0 else z), (r * 1.08, z + 0.35 * r), (0.72 * r, z + 0.85 * r), (0.0, z + 1.05 * r)],
                      [FPOD, FPOD, FPOD], sides=10, cx=x, cy=y)

        def dwelling(x, y, h, cap, levels):
            s = 0.07 + 0.02 * cap
            kit.lathe([(s * 1.5, -0.5), (s * 1.2, 0.1), (s, h)], [FSTALK, FSTALK], sides=10, cx=x, cy=y)
            for i in range(levels):
                z, R = h * (0.35 + 0.5 * i / max(levels, 1)), 0.28 + 0.06 * cap
                kit.lathe([(0.0, z), (R, z), (R, z + 0.035), (0.0, z + 0.035)], [FHUT, FHUT, FHUT], sides=12, cx=x, cy=y)
                for j in range(rng.randint(2, 3)):
                    a = rng.uniform(0, 2 * math.pi)
                    hut = rng.choice((pod, None))
                    px_, py_ = x + 0.8 * R * math.cos(a), y + 0.8 * R * math.sin(a)
                    if hut:
                        pod(px_, py_, z + 0.035, 0.07 + 0.01 * cap)
                    else:
                        kit.lathe([(0.07, z + 0.035), (0.07, z + 0.13), (0.0, z + 0.2)], [FHUT, FHUT], sides=6, cx=px_, cy=py_)
            R = 0.3 + 0.1 * cap
            kit.lathe([(s, h), (R, h + 0.03), (R * 0.95, h + 0.09), (R * 0.6, h + 0.2), (0.0, h + 0.26)],
                      [FCAP, FCAP, FCAP, FCAP], sides=14, cx=x, cy=y)

        if band == 1:
            for _ in range(rng.randint(2, 3)):
                pod(rng.uniform(-0.55, 0.55), rng.uniform(-0.55, 0.55), 0.0, rng.uniform(0.12, 0.18))
        else:
            x, y = rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25)
            h = 0.45 + 0.35 * band
            dwelling(x, y, h, band, band - 1)
            if band == 4:
                x2, y2 = -x * 0.3 + rng.choice((-0.55, 0.55)), -y * 0.3 + rng.choice((-0.5, 0.5))
                dwelling(x2, y2, h * 0.65, 2, 1)
                kit.tube((x, y, h * 0.6), (x2, y2, h * 0.6 * 0.65 + 0.03), 0.02, FHUT, sides=4)
            else:
                pod(rng.choice((-0.55, 0.55)), rng.uniform(-0.5, 0.5), 0.0, 0.13)

    def cmg_outpost(kit, band, rng):
        # Commerce Guild outpost on a frontier world: prefab hab modules, hexagonal domes, a landing pad; downtown a
        # command dome, a sensor dish on a comm mast and a perimeter wall: metal, not homes
        def hab(x, y, w, d, h):
            kit.box(x - w, y - d, -0.5, x + w, y + d, h, METAL_WIN, top=DARK)
            kit.box(x - w * 0.3, y - d - 0.05, 0.0, x + w * 0.3, y - d, h * 0.7, DARK)          # airlock

        def hexdome(x, y, r, h):
            kit.lathe([(r, -0.5), (r, h), (0.8 * r, h + 0.35 * r), (0.0, h + 0.5 * r)], [METAL_WIN, METAL, DARK],
                      sides=6, cx=x, cy=y)

        def pad(x, y, r):
            kit.lathe([(r, -0.5), (r, 0.05)], [DARK], sides=6, cx=x, cy=y, cap=DECK)        # flat deck on top

        def mast(x, y, h):
            kit.lathe([(0.03, -0.5), (0.03, h)], [METAL], sides=5, cx=x, cy=y)
            kit.lathe([(0.0, h - 0.02), (0.16, h + 0.05), (0.13, h + 0.09), (0.0, h + 0.04)], [DARK, METAL, METAL],
                      sides=10, cx=x, cy=y)                                                            # dish

        spots = [(-0.45, -0.4), (0.42, -0.42), (-0.4, 0.45), (0.45, 0.4)]
        rng.shuffle(spots)
        if band == 1:
            for x, y in spots[:rng.randint(1, 2)]:
                hab(x, y, rng.uniform(0.14, 0.2), rng.uniform(0.08, 0.12), 0.12)
        elif band == 2:
            hexdome(spots[0][0], spots[0][1], 0.22, 0.12)
            hab(spots[1][0], spots[1][1], 0.18, 0.1, 0.14)
            pad(spots[2][0], spots[2][1], 0.24)
        elif band == 3:
            hexdome(0.0, 0.0, 0.26, 0.18)
            pad(spots[0][0], spots[0][1], 0.26)
            mast(spots[1][0], spots[1][1], 0.9)
            hab(spots[2][0], spots[2][1], 0.18, 0.1, 0.14)
        else:
            hexdome(0.0, 0.0, 0.36, 0.3)                                                           # command dome
            mast(-0.55, 0.55, 1.3)
            pad(0.5, -0.45, 0.3)
            for sx, sy, w, d in ((0, -0.78, 0.8, 0.03), (0, 0.78, 0.8, 0.03), (-0.78, 0, 0.03, 0.8), (0.78, 0, 0.03, 0.8)):
                kit.box(sx - w, sy - d, -0.5, sx + w, sy + d, 0.16, DARK)                          # perimeter wall

    def rax_city(kit, band, rng):
        # Raxus capital: low flat-roofed sandstone blocks packed close, and slender gothic spires rising out of
        # them, more and taller downtown (the Clone Wars establishing shot)
        spots = [(-0.45, -0.45), (0.45, -0.45), (-0.45, 0.45), (0.45, 0.45), (0.0, 0.0)]
        rng.shuffle(spots)
        for x, y in spots[:rng.randint(2, 3 + band // 2)]:
            w, d = rng.uniform(0.2, 0.34), rng.uniform(0.2, 0.34)
            h = rng.uniform(0.12, 0.22) + 0.05 * band
            x, y = x + rng.uniform(-0.08, 0.08), y + rng.uniform(-0.08, 0.08)
            kit.box(x - w, y - d, -0.5, x + w, y + d, h, SAND_WIN, top=SAND)
            if rng.random() < 0.35:
                kit.box(x - w * 0.6, y - d * 0.6, h, x + w * 0.6, y + d * 0.6, h + 0.1 + 0.03 * band, SAND_WIN, top=SAND)
        for _ in range(rng.randint(0, 1) + (band >= 2) + (band >= 4)):
            x, y = rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6)
            h = rng.uniform(0.6, 1.0) * (0.6 + 0.35 * band)
            kit.lathe([(0.09, -0.5), (0.08, 0.6 * h), (0.11, 0.62 * h), (0.06, 0.85 * h), (0.0, h)],
                      [SAND_WIN, SAND, SAND, BRONZE], sides=6, cx=x, cy=y)

    for band in range(1, 5):
        for v in range(1, 5):
            rng = random.Random(f"hod_cmg_outpost{band}{v}")
            build(f"hod_cmg_outpost_{band}{v}", lambda k, band=band, rng=rng: cmg_outpost(k, band, rng), shader="PdxMeshSnow")

    for band in range(1, 5):
        for v in range(1, 5):
            rng = random.Random(f"hod_fel_city{band}{v}")
            build(f"hod_fel_city_{band}{v}", lambda k, band=band, rng=rng: fel_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_felucia_city")

    for prefix, fn in (("hod_kam_city", kam_city), ("hod_man_city", man_city), ("hod_geo_city", geo_city),
                       ("hod_nab_city", nab_city), ("hod_rax_city", rax_city)):
        for band in range(1, 5):
            for v in range(1, 5):
                rng = random.Random(f"{prefix}{band}{v}")

                build(f"{prefix}_{band}{v}", lambda k, fn=fn, band=band, rng=rng: fn(k, band, rng), shader="PdxMeshSnow")

    def spire(k, x, y, z0, h, r):
        # Geonosian needle spire: thin, segmented with little bulges, slightly rough
        k.lathe([(r, z0), (r * 0.7, z0 + 0.25 * h), (r * 0.9, z0 + 0.32 * h), (r * 0.55, z0 + 0.55 * h), (r * 0.7, z0 + 0.6 * h),
                 (r * 0.32, z0 + 0.82 * h), (r * 0.4, z0 + 0.86 * h), (0.0, z0 + h)], ROCK, sides=8, cx=x, cy=y, jitter=0.06)

    def stalgasin(k):
        # Stalgasin hive (Geonosis): broad flat-topped butte crowned by tall segmented needle spires
        k.lathe([(2.0, -SKIRT), (2.0, 0.0), (1.85, 0.45), (1.6, 0.62), (1.0, 0.64), (0.0, 0.64)], ROCK, sides=22, jitter=0.08)
        for x, y, h, r in ((0.0, 0.1, 2.7, 0.24), (-0.8, 0.5, 1.9, 0.2), (0.7, 0.7, 1.6, 0.18), (0.9, -0.5, 1.3, 0.17),
                           (-0.6, -0.7, 1.1, 0.16), (-1.3, -0.1, 0.8, 0.14)):
            spire(k, x, y, 0.6, h, r)

    def foundry(k):
        # Droid Foundry Complex (Geonosis): rock mound with dark smelters, chimneys and assembly halls
        k.lathe([(2.0, -SKIRT), (2.0, 0.0), (1.75, 0.45), (1.2, 0.72), (0.0, 0.8)], ROCK, sides=22, jitter=0.07)
        for x, y in ((-0.7, 0.4), (0.15, 0.75)):
            k.lathe([(0.45, 0.5), (0.45, 1.5), (0.3, 1.75), (0.12, 1.85)], [DARK_WIN, DARK, DARK], sides=16, cx=x, cy=y)
        for x, y, h in ((-1.1, -0.2, 2.3), (-0.2, 0.0, 2.0), (0.6, 0.2, 2.5)):
            k.tube((x, y, 0.5), (x, y, h), 0.11, DARK, sides=8)
        k.lathe([(0.38, 0.45), (0.38, 1.25), (0.26, 1.45), (0.1, 1.55)], [DARK_WIN, DARK, DARK], sides=16, cx=0.7, cy=-0.55)
        k.tube((-0.4, 0.5, 1.3), (0.55, -0.45, 1.15), 0.07, DARK, sides=6)                          # conveyor
        spire(k, 1.4, 0.9, 0.3, 1.4, 0.18)

    def progate(k):
        # Progate Temple (Geonosis): tall rock fins leaning together into pointed arches, a central spire
        k.lathe([(1.7, -SKIRT), (1.7, 0.0), (1.55, 0.15), (0.0, 0.15)], ROCK, sides=20, jitter=0.05)
        for i in range(7):
            a = 2 * math.pi * i / 7
            k.tube((1.35 * math.cos(a), 1.35 * math.sin(a), -0.3), (0.32 * math.cos(a + 0.25), 0.32 * math.sin(a + 0.25), 2.2),
                   0.32, ROCK, sides=6, r1=0.03)
        spire(k, 0.0, 0.0, 0.1, 2.9, 0.28)

    def dooku_hangar(k):
        # Dooku's hangar (Geonosis): tall rounded rock tower with a lit hangar band and a landing ledge
        k.lathe([(1.15, -SKIRT), (1.15, 0.0), (1.0, 0.8), (0.88, 1.6), (0.62, 2.25), (0.26, 2.65), (0.0, 2.75)], ROCK,
                sides=18, jitter=0.06)
        k.lathe([(1.12, 0.25), (1.12, 0.7)], DARK_WIN, sides=18)
        k.box(-0.45, -1.9, 0.0, 0.45, -1.0, 0.3, METAL, top=DECK)

    def theed(k):
        # Theed Royal Palace (Naboo): tan stone wings with green-copper domes, a big central dome, slim towers
        k.box(-0.9, -0.6, -SKIRT, 0.9, 0.6, 0.75, SAND_WIN, top=SAND)
        k.box(-2.0, -0.4, -SKIRT, -0.9, 0.4, 0.55, SAND_WIN, top=SAND)
        k.box(0.9, -0.4, -SKIRT, 2.0, 0.4, 0.55, SAND_WIN, top=SAND)
        k.lathe([(0.5, 0.75), (0.5, 1.0), (0.42, 1.25), (0.25, 1.42), (0.0, 1.48)], [SAND_WIN, VERDI, VERDI, VERDI], sides=20)
        k.lathe([(0.06, 1.46), (0.06, 1.65), (0.0, 1.72)], [VERDI, VERDI], sides=8)                       # lantern
        for x in (-1.75, -1.15, 1.15, 1.75):
            k.lathe([(0.2, 0.55), (0.2, 0.68), (0.14, 0.82), (0.0, 0.88)], [SAND, VERDI, VERDI], sides=12, cx=x)
        for x, y in ((-0.95, 0.75), (0.95, 0.75)):
            k.lathe([(0.12, -SKIRT), (0.12, 1.5), (0.16, 1.55), (0.1, 1.7), (0.0, 1.75)], [SAND_WIN, SAND, VERDI, VERDI],
                    sides=10, cx=x, cy=y)

    def coronet(k):
        # Coronet City starport (Corellia): quay deck, spherical tanks on legs, a slim control spire, gantry cranes
        k.box(-1.9, -1.2, -SKIRT, 1.9, 1.2, 0.1, METAL, top=DECK)
        for x, y in ((-1.0, 0.5), (0.0, 0.7)):
            for i in range(4):
                a = math.pi / 4 + math.pi / 2 * i
                k.tube((x + 0.3 * math.cos(a), y + 0.3 * math.sin(a), 0.1), (x + 0.2 * math.cos(a), y + 0.2 * math.sin(a), 1.3),
                       0.04, DARK, sides=5)
            prof = [(0.45 * math.sin(math.pi * i / 8), 1.55 - 0.45 * math.cos(math.pi * i / 8)) for i in range(9)]
            k.lathe(prof, [METAL, METAL, METAL_WIN, METAL_WIN, METAL, METAL, METAL, METAL], sides=16, cx=x, cy=y)
        k.lathe([(0.12, 0.1), (0.08, 2.4), (0.0, 2.7)], [METAL_WIN, METAL], sides=8, cx=1.1, cy=0.6)
        k.box(0.5, -1.0, 0.1, 1.5, -0.3, 0.6, METAL_WIN, top=METAL)
        for x in (-1.5, -0.5):
            k.box(x - 0.05, -1.1, 0.1, x + 0.05, -1.0, 1.0, DARK)
            k.box(x - 0.05, -1.1, 0.95, x + 0.05, 0.2, 1.05, DARK)

    # The Separatist Senate on Raxus is a "battlefield" landmark: map scale (11 units round, the Senate's 7 room
    # provinces of raxus_map.py), so its walls tile the atlas every TILE units instead of stretching one cell.
    TILE = 2.0

    def tblock(k, poly, z0, z1, rect, top=None, rows=None, poly_top=None):
        """Prism over a CCW polygon [(x, y)...] from z0 to z1 (to poly_top at z1: battered walls), open at the
        bottom: wall faces tiled every TILE (uv cropped to the tile so window rows keep their size), a flat roof."""
        bm = k.bm
        poly_top = poly_top or poly

        def subdiv(pl, counts):
            out = []
            for i, (xa, ya) in enumerate(pl):
                xb, yb = pl[(i + 1) % len(pl)]
                out += [(xa + (xb - xa) * s / counts[i], ya + (yb - ya) * s / counts[i]) for s in range(counts[i])]
            return out
        counts = [max(1, math.ceil(math.hypot(poly[(i + 1) % len(poly)][0] - x, poly[(i + 1) % len(poly)][1] - y) / TILE - 1e-6))
                  for i, (x, y) in enumerate(poly)]
        lo, hi = subdiv(poly, counts), subdiv(poly_top, counts)
        nz = rows or max(1, math.ceil((z1 - z0) / TILE - 1e-6))
        rings = [[bm.verts.new((a[0] + (b[0] - a[0]) * j / nz, a[1] + (b[1] - a[1]) * j / nz, z0 + (z1 - z0) * j / nz))
                  for a, b in zip(lo, hi)] for j in range(nz + 1)]
        n = len(lo)
        fv = min(1.0, (z1 - z0) / nz / TILE)
        for j in range(nz):
            for i in range(n):
                a, b = lo[i], lo[(i + 1) % n]
                fu = min(1.0, math.hypot(b[0] - a[0], b[1] - a[1]) / TILE)
                k.put(bm.faces.new((rings[j][i], rings[j][(i + 1) % n], rings[j + 1][(i + 1) % n], rings[j + 1][i])),
                      ((0, 0), (fu, 0), (fu, fv), (0, fv)), rect)
        xs, ys = [p[0] for p in hi], [p[1] for p in hi]
        sx, sy = max(max(xs) - min(xs), 1e-3), max(max(ys) - min(ys), 1e-3)
        k.put(bm.faces.new(rings[-1]), [((x - min(xs)) / sx, (y - min(ys)) / sy) for x, y in hi], top or rect)

    def ngon(cx, cy, r, sides, rot=0.0):
        return [(cx + r * math.cos(rot + 2 * math.pi * i / sides), cy + r * math.sin(rot + 2 * math.pi * i / sides))
                for i in range(sides)]

    def polar(r, deg):
        return r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))

    def arc(r0, r1, a0, a1, step=7.5):
        """CCW outline of an annular sector: outer arc a0 -> a1, inner arc back"""
        n = max(2, math.ceil((a1 - a0) / step))
        angs = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
        return [polar(r1, a) for a in angs] + [polar(r0, a) for a in reversed(angs)]

    def pinnacle(k, x, y, z0, h, r=0.22):
        k.lathe([(r, z0), (r * 0.8, z0 + 0.7 * h), (r * 1.1, z0 + 0.74 * h), (0.0, z0 + h)], [SAND, SAND, BRONZE],
                sides=6, cx=x, cy=y)

    def gothic_tower(k, x, y, half, z0, levels, spire, rot=0.0):
        """square setback tower: levels [(half-width, top)], pinnacles on every setback, bronze spire on top"""
        h0 = z0
        for hw, top in levels:
            tblock(k, ngon(x, y, hw * math.sqrt(2), 4, rot + math.pi / 4), h0, top, SAND_WIN, SAND)
            for px, py in ngon(x, y, hw * math.sqrt(2) * 0.92, 4, rot + math.pi / 4):
                pinnacle(k, px, py, top, 0.5 + 0.35 * hw, 0.08 + 0.08 * hw)
            h0 = top
        k.lathe([(levels[-1][0] * 0.9, h0), (levels[-1][0] * 0.5, h0 + 0.35 * spire), (0.0, h0 + spire)],
                [SAND, BRONZE], sides=4, cx=x, cy=y, rot=rot + math.pi / 4)

    def raxus(k):
        # Separatist Senate, Raxulon (The Clone Wars / The Bad Batch stills, Presley's concept art): a long curved
        # range of stepped sandstone halls, battered walls and buttress ramps sloping down to the Senate Plaza, more
        # halls and the great towers behind it, needle spires and sky bridges; the plaza in front with its grove of
        # tall orange-crowned trees opens south onto the Great Alley. Parts sit on the room provinces of raxus_map.py
        # ROOMS (sectors in degrees from east, counter-clockwise; model +x = east, +y = north, as the pdx exporter
        # maps them): front range 10..170 at 5.5..10.5, back halls 35..145 at 10.5..15.
        # front range: tiers stepping down toward the plaza, shorter toward its ends
        tiers = ((5.8, 10.5, -SKIRT, 2.0), (6.9, 10.5, 2.0, 3.8), (8.0, 10.4, 3.8, 5.6), (9.0, 10.3, 5.6, 7.0))
        for i, (r0, r1, z0, z1) in enumerate(tiers):
            batter = 0.35 if i < 3 else 0.2
            a0, a1 = 10 + 5 * i, 170 - 5 * i
            tblock(k, arc(r0, r1, a0, a1), z0, z1, SAND_WIN, SAND, poly_top=arc(r0 + batter, r1 - batter * 0.4, a0 + 1, a1 - 1))
        # back halls: a broad block and a second storey, higher than the front range
        tblock(k, arc(10.3, 14.7, 36, 144), -SKIRT, 7.8, SAND_WIN, SAND, poly_top=arc(10.5, 14.4, 37, 143))
        tblock(k, arc(10.8, 14.0, 46, 134), 7.8, 9.8, SAND_WIN, SAND, poly_top=arc(11.0, 13.8, 47, 133))
        # plaza: paving, a ring of light pylons, the grove on its round planter
        k.lathe([(9.6, -SKIRT), (9.6, 0.05), (0.0, 0.05)], SAND, sides=48)
        k.lathe([(2.3, 0.05), (2.3, 0.3), (2.1, 0.3), (2.1, 0.22), (0.0, 0.22)], [DARK, DARK, DARK, LEAF], sides=28)
        for i in range(10):
            x, y = polar(4.3, 18 + 36 * i)
            k.lathe([(0.12, 0.05), (0.1, 0.9), (0.16, 0.95), (0.0, 1.25)], [DARK_WIN, METAL, METAL], sides=4, cx=x, cy=y)
        rng = __import__("random").Random("raxulon grove")
        for i in range(16):
            ang, dist = rng.uniform(0, 360), 1.9 * math.sqrt(rng.random())
            x, y = polar(dist, ang)
            h = rng.uniform(2.0, 3.6)
            k.tube((x, y, 0.2), (x + rng.uniform(-0.1, 0.1), y + rng.uniform(-0.1, 0.1), h), 0.06, DARK, sides=5)
            for lvl in range(rng.randint(1, 3)):
                cz, cr = h - 0.45 * lvl, rng.uniform(0.32, 0.55) * (1 - 0.2 * lvl)
                k.lathe([(0.04, cz - 0.12), (cr, cz), (cr * 0.8, cz + 0.1), (0.0, cz + 0.14)], [BRONZE, BRONZE, BRONZE],
                        sides=9, cx=x, cy=y)
        # buttress ramps sloping from the front range down to the plaza
        bm = k.bm
        for ang in (28, 62, 118, 152):
            c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            pt = lambda u, v, zz: bm.verts.new((u * c - v * s, u * s + v * c, zz))
            w = 0.45
            v = [pt(5.2, -w, 0.0), pt(5.2, w, 0.0), pt(8.2, w, 0.0), pt(8.2, -w, 0.0), pt(8.2, -w, 5.6), pt(8.2, w, 5.6)]
            for f, uv in (((v[0], v[3], v[4]), ((0, 0), (1, 0), (1, 1))), ((v[1], v[5], v[2]), ((0, 0), (1, 1), (1, 0))),
                          ((v[0], v[4], v[5], v[1]), ((0, 0), (1, 0), (1, 1), (0, 1))),
                          ((v[3], v[2], v[5], v[4]), ((0, 0), (1, 0), (1, 1), (0, 1)))):
                k.put(bm.faces.new(f), uv, SAND)
        # the range's two ends: gothic towers
        for ang in (14, 166):
            gothic_tower(k, *polar(8.2, ang), 1.1, -SKIRT, ((1.1, 8.2), (0.85, 10.2)), 2.8, math.radians(ang))
        # Senate Chamber (front, 55..125): the clock tower in the middle of the range, fluted towers flanking it
        cx_, cy_ = polar(9.3, 90)
        gothic_tower(k, cx_, cy_, 1.5, 7.0, ((1.5, 10.6), (1.15, 13.2), (0.85, 15.0)), 3.6)
        for ang in (68, 112):
            gothic_tower(k, *polar(9.5, ang), 0.95, 7.0, ((0.95, 9.8), (0.7, 11.4)), 2.4, math.radians(ang))
        # Head of State's Office (back, 72..108): the tallest tower, a sky bridge to the clock tower, the needle spire
        hx, hy = polar(12.6, 82)
        gothic_tower(k, hx, hy, 1.3, 9.8, ((1.3, 14.0), (1.0, 16.4), (0.7, 18.0)), 3.4, math.radians(82))
        k.tube((hx, hy, 12.0), (cx_, cy_, 12.0), 0.14, SAND, sides=4)
        nx, ny = polar(12.8, 100)
        k.lathe([(0.5, 9.8), (0.42, 17.0), (0.32, 17.2), (0.26, 20.5), (0.0, 25.0)], [SAND_WIN, SAND, SAND_WIN, BRONZE],
                sides=6, cx=nx, cy=ny)
        k.tube((nx, ny, 14.5), (hx, hy, 14.5), 0.1, SAND, sides=4)
        # Delegates' Wing (back, 108..145): two fluted towers over the halls
        for ang, top in ((122, 13.0), (136, 11.6)):
            gothic_tower(k, *polar(12.6, ang), 0.9, 7.8, ((0.9, top), (0.65, top + 1.6)), 2.2, math.radians(ang))
        # Security Bureau (back, 35..72): octagonal turrets with bronze cones
        for ang, h in ((44, 10.2), (56, 11.4), (66, 10.6)):
            x, y = polar(12.7, ang)
            tblock(k, ngon(x, y, 0.8, 8, math.pi / 8), 7.8, h, SAND_WIN, SAND)
            k.lathe([(0.85, h), (0.0, h + 1.7)], [BRONZE], sides=8, cx=x, cy=y, rot=math.pi / 8)
        # Parliament Archives (front, 125..170): bronze dome on a drum
        ax, ay = polar(9.4, 148)
        k.lathe([(1.4, 7.0), (1.4, 7.9), (1.52, 8.0), (0.0, 8.0)], [SAND_WIN, SAND, SAND], sides=20, cx=ax, cy=ay)
        k.lathe([(1.3, 8.0)] + [(1.3 * math.cos(math.pi / 2 * i / 5), 8.0 + 1.2 * math.sin(math.pi / 2 * i / 5))
                                for i in range(1, 6)], [BRONZE] * 5, sides=20, cx=ax, cy=ay)
        # Senate Landing Platforms (front, 10..55): pads on short pylons above the top tier, a control tower
        for ang, z in ((24, 8.2), (42, 8.9)):
            x, y = polar(9.6, ang)
            k.lathe([(0.25, 7.0), (0.25, z - 0.2)], [SAND], sides=8, cx=x, cy=y)
            k.lathe([(0.9, z - 0.3), (1.1, z - 0.1), (1.1, z)], [SAND, METAL], sides=20, cx=x, cy=y, cap=DECK)
        x, y = polar(10.1, 33)
        k.lathe([(0.3, 7.0), (0.26, 10.6), (0.6, 10.9), (0.6, 11.3), (0.3, 11.6), (0.0, 12.2)],
                [SAND_WIN, SAND, METAL_WIN, SAND, BRONZE], sides=10, cx=x, cy=y)
        # pinnacles along the tier edges
        for i, (r0, r1, z0, z1) in enumerate(tiers[:3]):
            for ang in range(18 + 5 * i, 163 - 5 * i, 12):
                pinnacle(k, *polar(r0 + 0.5, ang), z1, 0.9, 0.16)

    def cis_banner(k):
        # Confederate banner on the Great Alley: navy banner with the white roundel and hexagon, on a metal pole
        k.lathe([(0.06, -0.5), (0.05, 3.3), (0.1, 3.36), (0.0, 3.6)], [BANNER_POLE, BANNER_POLE, BANNER_POLE], sides=6)
        k.box(-0.38, -0.025, 3.02, 0.38, 0.025, 3.08, BANNER_POLE)
        k.box(-0.32, -0.012, 1.1, 0.32, 0.012, 3.0, BANNER, top=BANNER_POLE)

    def serenno(k):
        # Castle Serenno: terrace with a tall capsule-shaped hall ringed by cone spires
        k.box(-1.7, -1.3, -SKIRT, 1.7, 1.3, 0.2, METAL, top=SAND)
        k.lathe([(0.0, 0.2), (0.32, 0.25), (0.45, 0.6), (0.45, 1.65), (0.3, 2.05), (0.0, 2.2)],
                [METAL, METAL, METAL_WIN, METAL, METAL], sides=20)
        for i in range(8):
            a = 2 * math.pi * i / 8
            k.lathe([(0.12, 0.2), (0.0, 0.95)], [METAL], sides=8, cx=1.15 * math.cos(a), cy=0.95 * math.sin(a))
        k.box(-1.6, 0.6, 0.2, -0.7, 1.2, 0.6, METAL_WIN, top=METAL)
        k.box(0.7, 0.6, 0.2, 1.6, 1.2, 0.6, METAL_WIN, top=METAL)

    def korriban(k):
        # Valley of the Dark Lords (Korriban): sharp red rock peaks round a tomb entrance with two dark obelisks
        for x, y, h, r in ((-1.3, 0.7, 2.4, 0.6), (-0.4, 1.2, 1.9, 0.5), (0.6, 1.1, 2.2, 0.55), (1.4, 0.4, 1.6, 0.45),
                           (-1.5, -0.6, 1.4, 0.45), (1.3, -0.8, 1.2, 0.4), (0.1, 0.4, 1.0, 0.35)):
            k.lathe([(r, -SKIRT), (r, 0.0), (0.0, h)], REDROCK, sides=5, cx=x, cy=y, rot=x, jitter=0.1)
        k.box(-0.35, -0.5, -SKIRT, 0.35, 0.0, 0.55, DARK_WIN, top=DARK)                                  # tomb gate
        for x in (-0.6, 0.6):
            k.lathe([(0.09, 0.0), (0.06, 1.1), (0.0, 1.25)], [DARK, DARK], sides=4, cx=x, cy=-0.75, rot=math.pi / 4)

    def sandcrawler(k):
        # Jawa sandcrawler (map prop): rust hull with the overhanging sloped prow, raised rear tower, four tread units
        k.prism([(-1.45, 0.3), (0.85, 0.3), (1.5, 1.15), (-0.25, 1.15), (-0.25, 1.4), (-1.45, 1.4)], -0.5, 0.5, RUST)
        for x in (-0.36, 0.36):
            for y in (-0.95, 0.55):
                k.box(x - 0.16, y - 0.38, 0.0, x + 0.16, y + 0.38, 0.32, DARK)

    build("hod_ion_cannon", ion_cannon)
    build("hod_raxus_senate", raxus)
    build("hod_cis_banner", cis_banner, tex="hod_cis_banner")
    for name, fn in (("hod_stalgasin_hive", stalgasin), ("hod_droid_foundry", foundry), ("hod_progate_temple", progate),
                     ("hod_dooku_hangar", dooku_hangar), ("hod_theed_palace", theed),
                     ("hod_coronet_port", coronet),
                     ("hod_castle_serenno", serenno), ("hod_korriban_valley", korriban)):
        build(name, fn)
    # the prop keeps vanilla tree wiring (gfx/entities/trees.gfx mapobject_53 -> this file), with its own atlas copy
    build("hod_flora_53_sandcrawler", sandcrawler, out=FLORA_OUT, tex="hod_flora_53_sandcrawler")
    build("hod_tipoca", tipoca)
    build("hod_petranaki_arena", arena)
    build("hod_massassi_temple", massassi)
    build("hod_jabba_palace", jabba)
    build("hod_sundari_dome", sundari)
    build("hod_jedi_temple", temple)
    build("hod_senate", senate)
    build("hod_spacedock", dock)


def wire():
    """gfx/entities/buildings.asset = vanilla with the air base entity pointed at our mesh."""
    s = open(VANILLA_ASSET, encoding="utf-8-sig").read()

    def replace_entity(name, body):
        nonlocal s
        m = re.search(r'entity = \{\s*name = "%s"' % name, s)
        assert m, name
        depth, i = 0, m.start()
        while True:                                   # find the entity's closing brace
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        s = s[:m.start()] + body + s[i + 1:]

    replace_entity("building_air_base", """entity = {
	name = "building_air_base"
	pdxmesh = "hod_launchpad_mesh"
	scale = 1.4
	# HOD: launch pad complex (WIPGFX/plans & scripts/military_buildings.py)
	locator = { name = "damage_locator_01"	position = { 0.0 1.2 0.0 } }
	locator = { name = "damage_locator_02"	position = { 1.3 0.9 -0.65 } }
	locator = { name = "damage_locator_03"	position = { 0.9 1.4 1.0 } }

	default_state = "idle"
	state = { name = "idle" }
	state = { name = "damaged"
		event = { time = 0.1 node="damage_locator_01" particle = "building_damaged_particle" }
		event = { time = 0.1 node="damage_locator_02" particle = "building_damaged_particle" }
		event = { time = 0.1 node="damage_locator_03" particle = "building_damaged_particle" }
		event = { time = 0 particle = "bunker_smoke_effect" }
	}
}""")
    replace_entity("building_anti_air_building", """entity = {
	name = "building_anti_air_building"
	pdxmesh = "hod_ion_cannon_mesh"
	scale = 1.0
	# HOD: ion cannon emplacement (WIPGFX/plans & scripts/military_buildings.py); static, so no animations
	locator = { name = "barrel"	position = { -1.32 1.65 1.32 } }
	locator = { name = "damage_locator_01"	position = { 0.8 0.3 0.6 } }
	locator = { name = "damage_locator_02"	position = { -0.3 1.0 -0.2 } }

	default_state = "idle"
	state = { name = "idle" }
	state = { name = "combat_idle" }
	state = { name = "attack"
		event = { time = 0.00 node="barrel" particle = "light_tank_attack_barrel_particle"  keep_particle = yes }
		event = { time = 2.00 node="barrel" particle = "light_tank_attack_barrel_particle"  keep_particle = yes }
		event = { time = 4.00 node="barrel" particle = "light_tank_attack_barrel_particle"  keep_particle = yes }
		event = { time = 6.00 node="barrel" particle = "light_tank_attack_barrel_particle"  keep_particle = yes }
	}
	state = { name = "damaged"
		event = { time = 0.1 node="damage_locator_01" particle = "building_damaged_particle" keep_particle = yes trigger_once = yes }
		event = { time = 0.1 node="damage_locator_02" particle = "building_damaged_particle" keep_particle = yes trigger_once = yes }
	}
}""")
    # naval bases -> space dock; bigger levels just scale up
    for name, scale in (("building_naval_base_spawn", 0.8), ("building_naval_base_1", 0.7), ("building_naval_base_2", 0.8),
                        ("building_naval_base_3", 0.9)):
        m = re.search(r'entity = \{\s*name = "%s".*?\n\}' % name, s, re.S)
        assert m, name
        block = re.sub(r'pdxmesh = "[^"]+"', 'pdxmesh = "hod_spacedock_mesh"', m.group(0))
        if re.search(r"\n\tscale = ", block):
            block = re.sub(r"\n\tscale = [0-9.]+", f"\n\tscale = {scale}", block)
        else:
            block = block.replace('pdxmesh = "hod_spacedock_mesh"', f'pdxmesh = "hod_spacedock_mesh"\n\tscale = {scale}')
        s = s[:m.start()] + block + s[m.end():]
    # Empire at War buildings: mesh and scale swapped; effect nodes the new mesh lacks become locators over its
    # middle so the particles still have somewhere to play; no chimney smoke on the factories
    for ent, (mesh, scale) in EAW_BUILDINGS.items():
        m = re.search(r'entity = \{\s*name = "%s".*?\n\}' % ent, s, re.S)
        assert m, ent
        block = re.sub(r'pdxmesh = "[^"]+"', f'pdxmesh = "{mesh}_mesh"', m.group(0), count=1)
        if re.search(r"\n\tscale = ", block):
            block = re.sub(r"\n\tscale = [0-9.]+", f"\n\tscale = {scale}", block, count=1)
        else:
            block = block.replace(f'pdxmesh = "{mesh}_mesh"', f'pdxmesh = "{mesh}_mesh"\n\tscale = {scale}', 1)
        block = re.sub(r'[ \t]*event = \{[^{}]*node\s*=\s*"factorysmoke2?"[^{}]*\}\n?', "", block)
        # a static mesh has no skeleton: state animations (and their blend / speed settings) go
        block = re.sub(r'[ \t]*animation(_blend_time|_speed)? = ("[^"]*"|[0-9.]+)', "", block)
        have = set(re.findall(r'locator = \{\s*name = "([^"]+)"', block))
        need = sorted(set(re.findall(r'node\s*=\s*"([^"]+)"', block)) - have)
        if need:
            locs = "".join(f'\n\tlocator = {{ name = "{n}"\tposition = {{ 0.0 0.8 0.0 }} }}' for n in need)
            block = block.replace(f'pdxmesh = "{mesh}_mesh"', f'pdxmesh = "{mesh}_mesh"{locs}', 1)
        s = s[:m.start()] + "\t# HOD: Empire at War model (military_buildings.py EAW_BUILDINGS)\n" + block + s[m.end():]
    open("gfx/entities/buildings.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: vanilla gfx/entities/buildings.asset with building_air_base, building_naval_base_* and\n"
        "# building_anti_air_building on our models and the EAW_BUILDINGS entities on Empire at War models\n"
        "# (WIPGFX/plans & scripts/military_buildings.py wire)\n" + s)
    with open("gfx/entities/hod_buildings.gfx", "w", encoding="utf-8", newline="\n") as f:
        f.write('objectTypes = {\n\t# HOD: Star Wars building models (WIPGFX/plans & scripts/military_buildings.py)\n'
                f'\tpdxmesh = {{\n\t\tname = "hod_launchpad_mesh"\n\t\tfile = "{OUT}/hod_launchpad.mesh"\n\t}}\n'
                + "".join(f'\tpdxmesh = {{\n\t\tname = "{m}_mesh"\n\t\tfile = "gfx/models/buildings/hod_sw/{m}.mesh"\n\t}}\n'
                          for m in sorted({m for m, _ in EAW_BUILDINGS.values()})) +
                "".join(f'\tpdxmesh = {{\n\t\tname = "{m}_mesh"\n\t\tfile = "{LM_OUT}/{m}.mesh"\n\t}}\n'
                        for m in ("hod_jedi_temple", "hod_senate", "hod_spacedock", "hod_ion_cannon") + NEW_LANDMARKS
                        if m not in LANDMARK_MESH) + '}\n')
    with open("gfx/entities/hod_landmarks.asset", "w", encoding="utf-8", newline="\n") as f:
        f.write('# HOD: landmarks placed by map/ambient_object.txt (military_buildings.py wire)\n'
                'entity = {\n\tname = "hod_jedi_temple_entity"\n\tpdxmesh = "hod_jedi_temple_mesh"\n\tscale = 1\n}\n'
                'entity = {\n\tname = "hod_senate_entity"\n\tpdxmesh = "hod_senate_mesh"\n\tscale = 1\n}\n'
                + "".join(f'entity = {{\n\tname = "{m}_entity"\n\tpdxmesh = "{LANDMARK_MESH.get(m, (m + "_mesh",))[0]}"\n'
                          f'\tscale = {LANDMARK_MESH.get(m, (0, 1))[1]}\n}}\n' for m in NEW_LANDMARKS))
    print("wrote gfx/entities/buildings.asset + hod_buildings.gfx")


# vanilla building entity -> (mesh in gfx/models/buildings/hod_sw, entity scale): Star Wars: Empire at War buildings
# converted by msh_to_glb.py and baked by sketchfab_props.py (eaw_*); air base, anti-air and naval base stay ours
EAW_BUILDINGS = {
    "building_industrial_complex": ("hod_bld_eaw_vehicleFactory", 1.0),
    "building_arms_factory": ("hod_bld_eaw_lightfactory", 1.0),
    "building_dockyard_1": ("hod_bld_eaw_rebelBarracks", 0.85),     # starship hangars
    "building_dockyard_2": ("hod_bld_eaw_rebelBarracks", 0.95),
    "building_dockyard_3": ("hod_bld_eaw_rebelBarracks", 1.05),
    "building_bunker": ("hod_bld_eaw_emplacement", 0.9),
    "building_coastal_bunker": ("hod_bld_eaw_emplacement", 0.8),
    "building_stronghold_network": ("hod_bld_eaw_prison", 1.0),     # walled fortress
    "building_radar_station": ("hod_bld_eaw_tibannaStation", 1.0),  # sensor sphere on a mast
    "building_synthetic_refinery": ("hod_bld_eaw_fuelCellC", 1.0),
    "building_rocket_site": ("hod_bld_eaw_corBuild4", 1.0),        # launch spire
    "building_rocket_site_spawn": ("hod_bld_eaw_corBuild4", 1.0),
    "building_nuclear_reactor": ("hod_bld_eaw_researchAcademy", 1.0),
    "building_nuclear_reactor_spawn": ("hod_bld_eaw_researchAcademy", 1.0),
    "building_commercial_nuclear_reactor": ("hod_bld_eaw_researchAcademy", 1.0),
    "building_supply_node": ("hod_bld_eaw_crates9", 1.0),
    "building_naval_supply_hub": ("hod_bld_eaw_crates4", 1.0),
    "building_naval_headquarters": ("hod_bld_eaw_officerAcademy", 1.0),
    "building_land_facility": ("hod_bld_eaw_infantrybarracks", 1.0),
    "building_air_facility": ("hod_bld_eaw_rebelBuilding1", 1.0),
    "building_naval_facility": ("hod_bld_eaw_bespinBuilding3", 1.0),   # round platform
    "building_nuclear_facility": ("hod_bld_eaw_researchAcademy", 1.0),
    "building_electronics_facility": ("hod_bld_eaw_droidworks", 1.0),
    "building_rocket_facility": ("hod_bld_eaw_corBuild3", 1.0),
}
LANDMARKS = {   # ambient object: (entity, victory point province it stands on, scale, yaw degrees, footprint radius px)
    "hod_jedi_temple": ("hod_jedi_temple_entity", 4836, 1.3, 0.0, 4.5),     # VICTORY_POINTS_4836 "Jedi Temple"
    "hod_senate": ("hod_senate_entity", 12535, 1.3, 0.0, 3.5),              # VICTORY_POINTS_12535 "Galactic Senate"
    "hod_tipoca": ("hod_tipoca_entity", 6230, 1.2, 0.0, 3.5),               # VICTORY_POINTS_6230 "Tipoca", Kamino
    "hod_petranaki_arena": ("hod_petranaki_arena_entity", 1611, 1.2, 0.0, 3.5),   # "Petranaki Arena", Geonosis
    "hod_massassi_temple": ("hod_massassi_temple_entity", 9060, 1.2, 0.0, 3.5),   # Yavin IV
    "hod_jabba_palace": ("hod_jabba_palace_entity", 1109, 1.2, 0.0, 3.0),         # Tatooine
    "hod_sundari_dome": ("hod_sundari_dome_entity", 9748, 1.2, 0.0, 3.0),         # Mandalore
}
LANDMARKS.update({   # Geonosis set (VP names from victory_points_l_english.yml) and the capitals of famous worlds
    "hod_stalgasin_hive": ("hod_stalgasin_hive_entity", 767, 1.2, 0.0, 3.0),       # "Stalgasin"
    "hod_droid_foundry": ("hod_droid_foundry_entity", 148, 1.2, 0.0, 3.0),         # "Droid Foundry Complex"
    "hod_progate_temple": ("hod_progate_temple_entity", 1954, 1.2, 0.0, 2.5),      # "Progate Temple"
    "hod_dooku_hangar": ("hod_dooku_hangar_entity", 16697, 1.2, 0.0, 2.5),         # "Dooku's Hangar"
    "hod_theed_palace": ("hod_theed_palace_entity", 17479, 1.2, 0.0, 3.0),         # Naboo, Theed
    "hod_kachirho": ("hod_kachirho_entity", 186, 1.0, 0.0, 2.5),                   # Kashyyyk (wroshyr giant)
    "hod_coronet_port": ("hod_coronet_port_entity", 3554, 1.2, 0.0, 3.0),          # Corellia
    "hod_raxus_senate": ("hod_raxus_senate_entity", 194, 1.0, 0.0, 9.5),           # Raxus: map scale, over its rooms;
                                                                                   # stands on the planet's centre (below)
    "hod_castle_serenno": ("hod_castle_serenno_entity", 8479, 1.2, 0.0, 3.0),      # Serenno (city district around it)
    "hod_korriban_valley": ("hod_korriban_valley_entity", 1594, 1.2, 0.0, 3.0),    # Korriban
})
CITY_TERRAIN, PLAZA_TERRAIN = [13], 25   # terrain.bmp: spawn_city urban -> urban_plaza_25 (same texture, no cities)
CITY_MARGIN = 2.0   # px of cities.bmp cleared past a landmark's footprint (city meshes reach ~1.7 map units)
NEW_LANDMARKS = tuple(n for n in LANDMARKS if n not in ("hod_jedi_temple", "hod_senate"))
LANDMARK_MESH = {"hod_kachirho": ("mapobject_40", 0.75)}   # landmarks that reuse an existing pdxmesh (trees.gfx), scale


def landmarks():
    """map/ambient_object.txt: (re)place each landmark on its province centre (y = 0: the game stands ambient
    objects on the terrain and adds y, like vanilla's chinese_wall_entity),
    clear map/cities.bmp and spawn_city terrain (-> urban_plaza_25) under its footprint so no city stands in it, and push map/buildings.txt
    buildings out of it to its edge. Rerun after planet_terrain_gen --write."""
    import io
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from planet_terrain_gen import load_provinces
    land, cls, pid = load_provinces()
    H = pid.shape[0]
    txt = open("map/ambient_object.txt", encoding="utf-8-sig").read()
    city = Image.open(io.BytesIO(open("map/cities.bmp", "rb").read()))     # in memory: we overwrite the file
    terr = Image.open(io.BytesIO(open("map/terrain.bmp", "rb").read()))
    tidx = np.array(terr)
    styles = np.array(city)
    yy, xx = np.mgrid[0:H, 0:pid.shape[1]]
    placed = {}
    for name, (entity, prov, scale, yaw, foot) in LANDMARKS.items():
        ys, xs = np.nonzero(pid == prov)
        cy, cx = int(round(ys.mean())), int(round(xs.mean()))
        if name == "hod_raxus_senate":          # built round the plaza's centre = the planet's (raxus_map.py)
            import json
            cy, cx = (int(round(c)) for c in json.load(open("WIPGFX/Assets/raxus_zones.json"))["centre"])
        clear = np.hypot(yy - cy, xx - cx) <= foot + CITY_MARGIN
        styles[clear] = 0
        tidx[clear & np.isin(tidx, CITY_TERRAIN)] = PLAZA_TERRAIN   # cities also spawn from spawn_city terrain
        placed[name] = (cx, H - cy)
        y = 0.0
        block = (f'type={{\n\ttype="{entity}"\n\tuse_animation=no\n\tscale={scale:.6f}\n\tobject={{\n\t\tname="{name}"\n'
                 f'\t\tposition={{\n\t\t\t{cx:.3f} {y:.3f} {H - cy:.3f} \n\t\t}}\n\t\trotation={{\n\t\t\t0.000 {math.radians(yaw):.3f} 0.000 \n\t\t}}\n\t}}\n}}\n')
        txt = re.sub(r'type=\{\s*type="%s".*?\n\}\n' % entity, "", txt, flags=re.S)     # replace an earlier placement
        txt = txt.rstrip("\n") + "\n" + block
        print(f"{name}: x {cx} z {H - cy}")
    open("map/ambient_object.txt", "w", encoding="utf-8", newline="\n").write(txt)
    # buildings must stay on land inside their own state (the game drops them otherwise), and anything tied to a sea
    # province (naval bases, coastal bunkers: last column) must not move at all, or coastal provinces lose their port
    # and the game crashes on load; naval / coastal buildings stay put too
    state_of = {}
    for fn in os.listdir("history/states"):
        st = open(f"history/states/{fn}", encoding="utf-8-sig").read()
        sid = re.search(r"\bid\s*=\s*(\d+)", st)
        pm = re.search(r"provinces\s*=\s*\{([^}]*)\}", st)
        if sid and pm:
            for pv in pm.group(1).split():
                state_of[int(pv)] = int(sid.group(1))
    lines = []
    for line in open("map/buildings.txt", encoding="utf-8-sig", newline=""):   # keep each line's own CRLF/LF
        body, end = line.rstrip("\r\n"), line[len(line.rstrip("\r\n")):]
        q = body.split(";")
        if len(q) >= 7 and q[2] and q[6].strip() == "0" and not re.search("naval|coastal|floating", q[1]):
            x, z = float(q[2]), float(q[4])
            for name, (entity, prov, scale, yaw, foot) in LANDMARKS.items():
                cx, cz = placed[name]
                if math.hypot(x - cx, z - cz) >= foot + 0.5:
                    continue
                # nearest land pixel of the same state outside the footprint
                r0, c0 = H - 1 - int(round(cz)), int(round(cx))
                win = (slice(max(0, r0 - 14), r0 + 15), slice(max(0, c0 - 14), c0 + 15))
                py, px_ = np.nonzero(land[win])
                py, px_ = py + win[0].start, px_ + win[1].start
                ok = [(math.hypot(c - x, (H - 1 - r) - z), c, H - 1 - r) for r, c in zip(py, px_)
                      if state_of.get(int(pid[r, c])) == int(q[0]) and math.hypot(c - cx, (H - 1 - r) - cz) >= foot + 0.5]
                if ok:
                    _, x, z = min(ok)
                    q[2], q[4] = f"{x:.2f}", f"{z:.2f}"
        lines.append(";".join(q) + end)
    open("map/buildings.txt", "w", encoding="utf-8", newline="").write("".join(lines))
    tout = Image.fromarray(tidx, "P")
    tout.putpalette(terr.getpalette())
    tout.save("map/terrain.bmp")
    out = Image.fromarray(styles, "P")
    out.putpalette(city.getpalette())
    out.save("map/cities.bmp")


def banner_texture():
    """hod_cis_banner: a Confederate banner (navy, gold trim, the white roundel with the CIS hexagon) above a strip of
    pole metal (BANNER / BANNER_POLE rects). Advanced layout like the landmarks: normal B = emission (none)."""
    import numpy as np
    from PIL import Image, ImageDraw
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    W, H = 256, 1024
    im = Image.new("RGB", (W, H), (110, 112, 118))                       # pole metal (bottom 12%)
    d = ImageDraw.Draw(im)
    top = int(H * (1 - BANNER[3])) + 2
    bot = int(H * (1 - BANNER[1]))
    navy, gold, white = (22, 26, 92), (200, 160, 60), (236, 236, 240)
    d.rectangle([0, top, W, bot], fill=navy)
    d.rectangle([10, top + 10, W - 11, bot - 10], outline=gold, width=8)
    cx, cy, r = W / 2, top + (bot - top) * 0.36, W * 0.34
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=white)
    hexr = r * 0.72
    hexagon = [(cx + hexr * math.cos(math.radians(60 * i + 30)), cy + hexr * math.sin(math.radians(60 * i + 30))) for i in range(6)]
    d.polygon(hexagon, outline=navy, width=12)
    for x, y in hexagon:                                                  # the six spokes
        d.line([(cx, cy), (x, y)], fill=navy, width=12)
    d.ellipse([cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2], fill=navy)
    for i in range(3):                                                    # gold chevrons below the roundel
        y = cy + r * 1.5 + i * 60
        d.line([(30, y), (cx, y + 40), (W - 30, y)], fill=gold, width=10)
    col = np.asarray(im).astype(np.float32)
    full = lambda v: np.full((H, W), v, np.float32)
    save_dxt5_mips(np.dstack([col, full(255)]), f"{LM_OUT}/hod_cis_banner_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), full(0), full(128)]), f"{LM_OUT}/hod_cis_banner_normal.dds")
    save_dxt5_mips(np.dstack([full(0), full(50), full(0), full(90)]), f"{LM_OUT}/hod_cis_banner_properties.dds")
    print("banner texture written to", LM_OUT)


ALLEY_MARK = ("# HOD: the Great Alley of Raxulon (military_buildings.py raxus_alley)", "# HOD: end of the Great Alley")
ALLEY_TREES = (2.4, 1.8, 0.85)      # trees: offset from the alley's axis, spacing, scale
ALLEY_BANNERS = (1.4, 3.6)          # banners: offset from the axis, spacing


def raxus_alley():
    """The Great Alley (raxus_map.py zone 6): golden trees (flora_props.py alley copies, alpha-tested) down both
    sides and Confederate banners between them: entities + map/ambient_object.txt block (y = 0: stood on the ground)."""
    import json
    import numpy as np
    from PIL import Image
    z = json.load(open("WIPGFX/Assets/raxus_zones.json"))
    zone = np.asarray(Image.open("WIPGFX/Assets/raxus_zones.png"))
    H = zone.shape[0]
    cy, cx = z["centre"]
    rows = np.nonzero((zone == 6).any(1))[0]
    r0, r1 = rows.min() + 0.8, rows.max() - 0.5
    open("gfx/entities/hod_raxus_alley.gfx", "w", encoding="utf-8", newline="\n").write(
        "objectTypes = {\n\t# HOD: the Great Alley of Raxulon (military_buildings.py raxus_alley)\n"
        + "".join(f'\tpdxmesh = {{\n\t\tname = "hod_rax_alley_{i}_mesh"\n\t\tfile = "{FLORA_OUT}/hod_rax_alley_{i}.mesh"\n\t}}\n'
                  for i in (62, 63))
        + f'\tpdxmesh = {{\n\t\tname = "hod_cis_banner_mesh"\n\t\tfile = "{LM_OUT}/hod_cis_banner.mesh"\n\t}}\n}}\n')
    open("gfx/entities/hod_raxus_alley.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: the Great Alley of Raxulon (military_buildings.py raxus_alley)\n"
        + "".join(f'entity = {{\n\tname = "{n}_entity"\n\tpdxmesh = "{n}_mesh"\n\tscale = 1\n}}\n'
                  for n in ("hod_rax_alley_62", "hod_rax_alley_63", "hod_cis_banner")))
    rng = __import__("random").Random("great alley")
    objs = {"hod_rax_alley_62": [], "hod_rax_alley_63": [], "hod_cis_banner": []}
    row = r0
    while row <= r1:
        for side in (-1, 1):
            name = "hod_rax_alley_62" if rng.random() < 0.6 else "hod_rax_alley_63"
            objs[name].append((cx + side * ALLEY_TREES[0], H - 1 - row, rng.uniform(0, 6.28)))
        row += ALLEY_TREES[1]
    row = r0 + ALLEY_TREES[1] / 2
    while row <= r1:
        for side in (-1, 1):
            objs["hod_cis_banner"].append((cx + side * ALLEY_BANNERS[0], H - 1 - row, 0.0))
        row += ALLEY_BANNERS[1]
    block = ALLEY_MARK[0] + "\n"
    for name, pts in objs.items():
        scale = ALLEY_TREES[2] if "alley" in name else 1.0
        block += f'type={{\n\ttype="{name}_entity"\n\tuse_animation=no\n\tscale={scale:.6f}\n'
        block += "".join(f'\tobject={{\n\t\tname="{name}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} 0.000 {zz:.3f} \n\t\t}}\n'
                         f'\t\trotation={{\n\t\t\t0.000 {yaw:.3f} 0.000 \n\t\t}}\n\t}}\n' for i, (x, zz, yaw) in enumerate(pts))
        block += "}\n"
    block += ALLEY_MARK[1] + "\n"
    path = "map/ambient_object.txt"
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    s = re.sub(re.escape(ALLEY_MARK[0]) + r".*?" + re.escape(ALLEY_MARK[1]) + r"\n", "", s, flags=re.S)
    s = s.rstrip("\n") + "\n" + block
    assert s.count("{") == s.count("}")
    open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + (s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
    print("Great Alley:", {k: len(v) for k, v in objs.items()})

if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"textures": textures, "launchpad": launchpad, "wire": wire, "landmarks": landmarks, "atlas": atlas,
     "felucia_atlas": felucia_atlas, "models": models,
     "banner_texture": banner_texture, "raxus_alley": raxus_alley}[args[0]](*args[1:])
