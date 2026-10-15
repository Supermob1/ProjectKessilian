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
  python "WIPGFX/plans & scripts/military_buildings.py" place NAME  a planet's models from its map script's PLACEMENT
                                                                 (zygerria_place = place Zygerria)
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


# hod_korriban atlas (4 x 4 cells like hod_landmarks; normal B = night emission): carved red stone with glyph bands,
# plain red masonry, weathered statue stone, dark doorways, glowing bands, the Sith Empire banner, Dreshdae's metal
K_GLYPH, K_STONE, K_STATUE, K_DARK = (_cell(i, 0) for i in range(4))
K_LIGHT, K_BANNER, K_METAL, K_METAL_WIN = (_cell(i, 1) for i in range(4))
K_GOLD, K_SAND, K_CONCRETE, K_RUBBLE = (_cell(i, 2) for i in range(4))
# hod_zygerria atlas (zygerria_atlas; The Clone Wars "Slaves of the Republic" stills): the palace's blue slate, plain and
# with lit windows, terracotta, the city's sandstone, plain and lit, teal tent roofs, bronze domes, dark doorways,
# striped awnings, pale trim stone, dark metal
Z_SLATE, Z_SLATE_WIN, Z_RED, Z_SAND = (_cell(i, 0) for i in range(4))
Z_SAND_WIN, Z_ROOF, Z_BRONZE, Z_DARK = (_cell(i, 1) for i in range(4))
Z_AWNING, Z_PALE, Z_METAL, Z_SPARE = (_cell(i, 2) for i in range(4))
# hod_dromund atlas (dromund_atlas; TOR stills of Kaas City, the Imperial Citadel and the Dark Temple): dark blue-grey
# Sith plating (plain / with mostly dead window slits), pale grey temple stone (clean / weathered with moss), black,
# red glow, the Sith Empire emblem, grey rubble, dark overgrowth, mast steel
D_PLATE, D_PLATE_WIN, D_STONE, D_STONE_WORN = (_cell(i, 0) for i in range(4))
D_DARK, D_LIGHT, D_EMBLEM, D_RUBBLE = (_cell(i, 1) for i in range(4))
D_MOSS, D_METAL, D_SPARE1, D_SPARE2 = (_cell(i, 2) for i in range(4))
# hod_cantonica atlas (cantonica_atlas; Canto Bight in TLJ / Star Wars Outlaws, the user's references 2026-10-14): pale
# beige stone with pilasters, plain and with a lit window band; pale plaster, plain and with small lit windows; dark
# slate roof plates, plain and with the lit band under a dome's lip; warm grey flat roofs; black doorways; warm light;
# dark railings; a landing pad with its red ring; garden green; the ancient Sith ruins' sandstone (plain, carved with
# a glyph band, dark weathered), drift sand
C_STONE, C_STONE_WIN, C_PLASTER, C_PLASTER_WIN = (_cell(i, 0) for i in range(4))
C_SLATE, C_SLATE_LIT, C_ROOF, C_DARK = (_cell(i, 1) for i in range(4))
C_GLOW, C_RAIL, C_PAD, C_GARDEN = (_cell(i, 2) for i in range(4))
C_SITH, C_SITH_GLYPH, C_SITH_DARK, C_SAND = (_cell(i, 3) for i in range(4))


def kadavo_atlas():
    """hod_kadavo texture for the volcanic craters ("Slaves of the Republic", "Escape from Kadavo" stills): irregular
    rounded blocks like pillow lava, each lit from above with a dark crevice round it. Seamless left-right. The top
    half (v 0.5-1) is the weathered grey-olive outside, the bottom half (v 0-0.5) the soot-dark throat."""
    import numpy as np
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    N = LM_S
    rng = np.random.default_rng(83)
    half = N // 2
    yy, xx = np.mgrid[0:half, 0:N].astype(np.float32)

    def pillows(n, base, dark):
        pts = np.stack([rng.uniform(0, half, n), rng.uniform(0, N, n)], 1)
        d1 = np.full((half, N), 1e9, np.float32)
        d2 = np.full((half, N), 1e9, np.float32)
        own = np.zeros((half, N), np.int32)
        for i, (py, px) in enumerate(pts):                                  # periodic in x: seamless left-right
            dx = np.minimum(np.abs(xx - px), N - np.abs(xx - px))
            d = np.hypot((yy - py) * 1.25, dx)                              # blocks a little wider than tall
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            own = np.where(closer, i, own)
            d1 = np.where(closer, d, d1)
        gap = np.clip((d2 - d1) / 6.0, 0, 1)                                # 0 in the crevice
        size = np.sqrt(N * half / n)
        dome = np.clip(1 - d1 / (size * 0.75), 0, 1) ** 0.5                 # each block bulges
        top = np.clip((yy - pts[own, 0]) / size + 0.5, 0, 1)                # lit from above: upper side brighter
        shade = rng.uniform(0.75, 1.15, n)[own]
        rgb = base[None, None] * (0.55 + 0.45 * dome)[..., None] * (1.05 - 0.3 * top)[..., None] * shade[..., None]
        rgb = rgb * gap[..., None] + dark * (1 - gap[..., None])
        return rgb
    outside = pillows(170, np.array([122, 118, 100], np.float32), np.array([28, 27, 24], np.float32))
    inside = pillows(150, np.array([62, 58, 52], np.float32), np.array([14, 13, 12], np.float32))
    grain = ndi.gaussian_filter(rng.random((half, N)), 1.0)
    grain = (grain - grain.min()) / np.ptp(grain)
    col = np.concatenate([outside * (0.85 + 0.25 * grain)[..., None], inside * (0.85 + 0.25 * grain)[..., None]], 0)
    full = lambda v: np.full((N, N), v, np.float32)
    save_dxt5_mips(np.dstack([np.clip(col, 0, 255), full(255)]), f"{LM_OUT}/hod_kadavo_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), full(0), full(128)]), f"{LM_OUT}/hod_kadavo_normal.dds")
    save_dxt5_mips(np.dstack([full(0), full(20), full(0), full(100)]), f"{LM_OUT}/hod_kadavo_properties.dds")
    from PIL import Image
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).resize((512, 512)).save("WIPGFX/kadavo_stone_preview.png")
    print("kadavo crater texture written to", LM_OUT)


def korriban_atlas():
    """hod_korriban textures (korriban_research.md): red-ochre stone with incised glyph rows and masonry courses,
    pale weathered statue stone, black doorways, a red-gold glowing band, a red banner with the black Sith Empire
    emblem, grey Dreshdae plating (plain and with lit windows), tarnished gold, red dust."""
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    N = LM_S
    t = N // 4
    rng = np.random.default_rng(66)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime = ndi.gaussian_filter(rng.random((t, t)), 2)
    grime = ((grime - grime.min()) / np.ptp(grime))[..., None]
    blotch = ndi.gaussian_filter(rng.random((t, t)), 10)
    blotch = ((blotch - blotch.min()) / np.ptp(blotch))[..., None]
    col = np.zeros((N, N, 3), np.float32)
    emi = np.zeros((N, N), np.float32)
    spec = np.full((N, N), 30, np.float32)
    red = np.array([168, 84, 58], np.float32)

    def put(rect, rgb, e=None, sp=30):
        u0, v0, u1, v1 = rect
        r, c = slice(int(round((1 - v1) * N)), int(round((1 - v0) * N))), slice(int(round(u0 * N)), int(round(u1 * N)))
        col[r, c] = np.clip(rgb, 0, 255)
        if e is not None:
            emi[r, c] = e
        spec[r, c] = sp

    courses = (yy % 32) < 2
    # ages of sand and wind: vertical streaks, cracks, chipped blotches, sand drifted up the foot of every wall
    streak = ndi.gaussian_filter(rng.random((t, t)), (28, 1.2))
    streak = ((streak - streak.min()) / np.ptp(streak))[..., None]
    crack = np.zeros((t, t), np.float32)
    for _ in range(40):
        y_, x_ = rng.uniform(0, t), rng.uniform(0, t)
        for _s in range(int(rng.integers(8, 30))):
            a_ = rng.uniform(0, 6.283)
            y2, x2 = y_ + 3 * math.sin(a_) + 2, x_ + 3 * math.cos(a_)
            n_ = 6
            for q in range(n_):
                yi, xi = int((y_ + (y2 - y_) * q / n_) % t), int((x_ + (x2 - x_) * q / n_) % t)
                crack[yi, xi] = 1
            y_, x_ = y2, x2
    crack = np.clip(ndi.gaussian_filter(crack, 0.6) * 3, 0, 1)[..., None]
    drift = np.clip((yy - t * 0.72) / (t * 0.28), 0, 1)[..., None] * (0.6 + 0.4 * blotch)
    sandc = np.array([186, 118, 82], np.float32)

    def aged(rgb):
        rgb = rgb * (0.78 + 0.32 * streak) * (1 - 0.45 * crack) * (0.82 + 0.3 * blotch)
        return rgb * (1 - drift) + sandc * (0.85 + 0.2 * grime) * drift
    stone = aged(red * (0.78 + 0.3 * grime) * (1 - 0.18 * courses[..., None]))
    put(K_STONE, stone)
    glyph = Image.new("L", (t, t), 0)
    d = ImageDraw.Draw(glyph)
    for row in range(t // 32):                                           # rows of incised glyphs between courses
        y = row * 32 + 8
        x = 4
        while x < t - 12:
            w = int(rng.integers(6, 14))
            kind = rng.integers(4)
            if kind == 0:
                d.rectangle([x, y, x + w, y + 14], outline=255, width=2)
            elif kind == 1:
                d.line([(x, y), (x + w, y + 14)], fill=255, width=2)
                d.line([(x + w, y), (x, y + 14)], fill=255, width=2)
            elif kind == 2:
                d.ellipse([x, y, x + w, y + 14], outline=255, width=2)
            else:
                d.line([(x + w // 2, y), (x + w // 2, y + 14)], fill=255, width=2)
                d.line([(x, y + 7), (x + w, y + 7)], fill=255, width=2)
            x += w + int(rng.integers(4, 9))
    g = np.asarray(glyph, np.float32)[..., None] / 255
    put(K_GLYPH, stone * (1 - 0.32 * g * (0.4 + 0.6 * blotch)))          # glyphs worn faint in places
    put(K_STATUE, aged(np.array([170, 128, 108], np.float32) * (0.72 + 0.35 * grime)))
    put(K_DARK, np.array([26, 18, 18], np.float32) * (0.8 + 0.4 * grime))
    band = np.abs(yy - t / 2) / (t / 2)
    put(K_LIGHT, np.array([255, 120, 60], np.float32) * (1.1 - 0.5 * band)[..., None], e=255 * (1 - band), sp=80)
    # the Sith Empire emblem (hexagon, six blades round a hub) in black on a crimson banner with a gold hem
    ban = Image.new("RGB", (t, t), (150, 18, 22))
    d = ImageDraw.Draw(ban)
    d.rectangle([0, 0, t - 1, t - 1], outline=(190, 150, 60), width=8)
    cx, cy, R = t / 2, t * 0.42, t * 0.3
    hexa = [(cx + R * math.cos(math.radians(60 * i + 30)), cy + R * math.sin(math.radians(60 * i + 30))) for i in range(6)]
    d.polygon(hexa, outline=(15, 10, 10), width=10)
    for i in range(6):
        a0, a1 = math.radians(60 * i + 10), math.radians(60 * i + 40)
        d.polygon([(cx + 0.25 * R * math.cos(a0), cy + 0.25 * R * math.sin(a0)), (cx + 0.8 * R * math.cos(a0), cy + 0.8 * R * math.sin(a0)),
                   (cx + 0.8 * R * math.cos(a1), cy + 0.8 * R * math.sin(a1))], fill=(15, 10, 10))
    d.ellipse([cx - 0.18 * R, cy - 0.18 * R, cx + 0.18 * R, cy + 0.18 * R], fill=(15, 10, 10))
    put(K_BANNER, np.asarray(ban, np.float32) * (0.85 + 0.2 * grime))
    panels = (((xx % 48) < 2) | ((yy % 40) < 2))[..., None]
    metal = np.array([150, 148, 150], np.float32) * (0.8 + 0.3 * grime) * (1 - 0.2 * panels)
    put(K_METAL, metal, sp=70)
    win = ((xx % 16) > 5) & ((xx % 16) < 11) & ((yy % 32) > 12) & ((yy % 32) < 22)
    put(K_METAL_WIN, np.where(win[..., None], [70, 60, 50], metal), e=np.where(win & (rng.random((t, t)) > 0.3), 220, 0), sp=70)
    put(K_GOLD, np.array([170, 128, 64], np.float32) * (0.75 + 0.35 * grime), sp=120)
    put(K_SAND, np.array([182, 104, 72], np.float32) * (0.85 + 0.25 * grime))
    # the academy's ferrocrete: grey-red slabs, formwork seams, rust and soot stains running down, sand at the foot
    seams = (((xx % 96) < 2) | ((yy % 72) < 2))[..., None]
    soot = ndi.gaussian_filter(rng.random((t, t)), (36, 3))
    soot = ((soot - soot.min()) / np.ptp(soot))[..., None]
    conc = np.array([128, 112, 106], np.float32) * (0.8 + 0.3 * grime) * (1 - 0.25 * seams) * (1 - 0.45 * (soot > 0.62))
    put(K_CONCRETE, aged(conc))
    rub = np.array([150, 100, 80], np.float32) * (0.55 + 0.6 * ndi.gaussian_filter(rng.random((t, t)), 1.5)[..., None])
    put(K_RUBBLE, rub)
    full = lambda v: np.full((N, N), v, np.float32)
    save_dxt5_mips(np.dstack([col, full(255)]), f"{LM_OUT}/hod_korriban_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), emi, full(128)]), f"{LM_OUT}/hod_korriban_normal.dds")
    save_dxt5_mips(np.dstack([full(0), spec, full(0), full(100)]), f"{LM_OUT}/hod_korriban_properties.dds")
    Image.fromarray(col.astype(np.uint8)).resize((512, 512)).save("WIPGFX/korriban_atlas_preview.png")
    print("korriban atlas written to", LM_OUT)

def _atlas_canvas(N, seed):
    """a 4 x 4 cell atlas being painted: (col, emi, spec, put, noise) where put(cell, rgb, e=None, sp=30) fills one
    _cell and noise(sigma) is a smooth 0..1 field the size of a cell"""
    import numpy as np
    from scipy import ndimage as ndi
    rng = np.random.default_rng(seed)
    col = np.zeros((N, N, 3), np.float32)
    emi = np.zeros((N, N), np.float32)
    spec = np.full((N, N), 30, np.float32)

    def put(rect, rgb, e=None, sp=30):
        u0, v0, u1, v1 = rect
        r, c = slice(int(round((1 - v1) * N)), int(round((1 - v0) * N))), slice(int(round(u0 * N)), int(round(u1 * N)))
        col[r, c] = np.clip(rgb, 0, 255)
        if e is not None:
            emi[r, c] = e
        spec[r, c] = sp

    def noise(sigma):
        a = ndi.gaussian_filter(rng.random((N // 4, N // 4)), sigma)
        return ((a - a.min()) / np.ptp(a))[..., None]
    return col, emi, spec, put, noise, rng


def _atlas_save(name, col, emi, spec):
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    N = col.shape[0]
    full = lambda v: np.full((N, N), v, np.float32)
    save_dxt5_mips(np.dstack([col, full(255)]), f"{LM_OUT}/{name}_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), emi, full(128)]), f"{LM_OUT}/{name}_normal.dds")
    save_dxt5_mips(np.dstack([full(0), spec, full(0), full(100)]), f"{LM_OUT}/{name}_properties.dds")
    os.makedirs("WIPGFX/research/previews", exist_ok=True)
    Image.fromarray(col.astype(np.uint8)).resize((512, 512)).save(f"WIPGFX/research/previews/{name}_atlas.png")
    print(name, "atlas written to", LM_OUT)


def dromund_atlas():
    """hod_dromund textures from the TOR stills (Kaas City, the Imperial Citadel, the Dark Temple pass)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 89)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    panels = (((xx % 64) < 2) | ((yy % 48) < 2))[..., None]
    plate = np.array([74, 82, 100], np.float32) * (0.8 + 0.3 * grime) * (1 - 0.3 * panels) * (0.8 + 0.3 * streak)
    put(D_PLATE, plate, sp=60)
    slit = ((xx % 20) > 7) & ((xx % 20) < 12) & ((yy % 40) > 6) & ((yy % 40) < 30)
    lit = slit & (rng.random((t, t)) > 0.9)                                  # a few windows still glow, most are dead
    put(D_PLATE_WIN, np.where(slit[..., None], [18, 20, 26], plate), e=np.where(lit, 160, 0), sp=60)
    courses = ((yy % 28) < 2)[..., None]
    stone = np.array([168, 170, 172], np.float32) * (0.82 + 0.25 * grime) * (1 - 0.2 * courses) * (0.85 + 0.2 * blotch)
    put(D_STONE, stone)
    moss = np.clip((blotch - 0.55) * 3, 0, 1) * (0.5 + 0.5 * streak)
    put(D_STONE_WORN, stone * (1 - 0.6 * moss) + np.array([40, 70, 50], np.float32) * moss * 0.9)
    put(D_DARK, np.array([16, 16, 20], np.float32) * (0.8 + 0.4 * grime))
    band = np.abs(yy - t / 2) / (t / 2)
    put(D_LIGHT, np.array([255, 70, 55], np.float32) * (1.35 - 0.35 * band)[..., None] + 40, e=255 * (1 - band), sp=200)  # always
                                                          # day on this map (no night emission): the glow is painted bright
    ban = Image.new("RGB", (t, t), (150, 18, 22))                            # the Sith Empire emblem on crimson
    d = ImageDraw.Draw(ban)
    cx, cy, R = t / 2, t / 2, t * 0.36
    hexa = [(cx + R * math.cos(math.radians(60 * i + 30)), cy + R * math.sin(math.radians(60 * i + 30))) for i in range(6)]
    d.polygon(hexa, outline=(15, 10, 10), width=10)
    for i in range(6):
        a0, a1 = math.radians(60 * i + 10), math.radians(60 * i + 40)
        d.polygon([(cx + 0.25 * R * math.cos(a0), cy + 0.25 * R * math.sin(a0)), (cx + 0.8 * R * math.cos(a0), cy + 0.8 * R * math.sin(a0)),
                   (cx + 0.8 * R * math.cos(a1), cy + 0.8 * R * math.sin(a1))], fill=(15, 10, 10))
    d.ellipse([cx - 0.18 * R, cy - 0.18 * R, cx + 0.18 * R, cy + 0.18 * R], fill=(15, 10, 10))
    put(D_EMBLEM, np.asarray(ban, np.float32) * (0.85 + 0.2 * grime), e=60)
    put(D_RUBBLE, np.array([100, 102, 108], np.float32) * (0.5 + 0.7 * noise(1.5)))
    put(D_MOSS, np.array([34, 58, 44], np.float32) * (0.7 + 0.5 * grime))
    put(D_METAL, np.array([90, 94, 104], np.float32) * (0.8 + 0.3 * grime), sp=110)
    put(D_SPARE1, plate)
    put(D_SPARE2, stone)
    _atlas_save("hod_dromund", col, emi, spec)


def cantonica_atlas():
    """hod_cantonica textures from the user's Canto Bight references (TLJ casino and drum building, Star Wars Outlaws
    view of the city) and the ancient Sith ruins (design choice). The map is always day: lights are painted bright."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 84)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    aged = lambda rgb: rgb * (0.82 + 0.25 * grime) * (0.88 + 0.18 * blotch)
    pil = ((xx % 32) < 5)[..., None]                                          # pilasters: u runs round a drum
    stone = aged(np.array([214, 200, 172], np.float32)) * (1 - 0.18 * ((yy % 40) < 2)[..., None]) * (1 + 0.08 * pil)
    put(C_STONE, stone)
    band = (np.abs(yy - t / 2) < t * 0.2)                                     # one window band round the middle
    win = band & ((xx % 32) > 8) & ((xx % 32) < 28)
    warm = np.array([255, 196, 110], np.float32)
    put(C_STONE_WIN, np.where(win[..., None], warm * (0.85 + 0.2 * grime), stone), e=np.where(win, 230, 0))
    plaster = aged(np.array([226, 214, 190], np.float32))
    put(C_PLASTER, plaster)
    small = ((xx % 22) > 8) & ((xx % 22) < 14) & ((yy % 30) > 10) & ((yy % 30) < 20)
    lit = small & (rng.random((t, t)) > 0.45)
    put(C_PLASTER_WIN, np.where(lit[..., None], warm, np.where(small[..., None], [60, 52, 44], plaster)), e=np.where(lit, 220, 0))
    seams = (((xx % 24) < 2) | ((yy % 18) < 2))[..., None]
    slate = np.array([70, 76, 88], np.float32) * (0.85 + 0.25 * grime) * (1 - 0.25 * seams)
    put(C_SLATE, slate, sp=70)
    lip = yy < t * 0.3                                                        # v 0 (the lathe's lower ring) lit
    put(C_SLATE_LIT, np.where(lip[..., None], warm * (0.9 + 0.1 * grime), slate), e=np.where(lip, 230, 0), sp=70)
    put(C_ROOF, aged(np.array([150, 140, 128], np.float32)))
    put(C_DARK, np.array([24, 22, 22], np.float32) * (0.8 + 0.4 * grime))
    put(C_GLOW, warm * (1.0 + 0.1 * grime) + 10, e=255, sp=200)
    put(C_RAIL, np.array([52, 54, 60], np.float32) * (0.8 + 0.3 * grime), sp=90)
    pad = Image.new("RGB", (t, t), (150, 148, 142))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(255, 70, 70), width=int(t * 0.05))   # the red ring
    d.ellipse([t * 0.3, t * 0.3, t * 0.7, t * 0.7], outline=(90, 90, 90), width=int(t * 0.03))
    put(C_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(C_GARDEN, np.array([78, 112, 66], np.float32) * (0.7 + 0.5 * noise(1.5)))
    sith = aged(np.array([186, 150, 106], np.float32)) * (1 - 0.25 * ((yy % 48) < 3)[..., None]) * (0.85 + 0.25 * streak)
    put(C_SITH, sith)
    gl = Image.new("L", (t, t), 0)                                            # a band of carved glyphs
    d = ImageDraw.Draw(gl)
    for i in range(10):
        x0 = i * t / 10 + 4
        for _ in range(3):
            a, b = rng.uniform(0, t / 10 - 8, 2)
            d.line([(x0 + a, t * 0.38 + rng.uniform(0, t * 0.1)), (x0 + b, t * 0.52 + rng.uniform(0, t * 0.1))], fill=255, width=5)
    cut = (np.asarray(gl, np.float32) / 255)[..., None]
    put(C_SITH_GLYPH, sith * (1 - 0.55 * cut) * (1 - 0.3 * (np.abs(yy - t * 0.5) < t * 0.2)[..., None] * 0.4))
    put(C_SITH_DARK, aged(np.array([120, 84, 62], np.float32)))
    put(C_SAND, np.array([212, 172, 118], np.float32) * (0.85 + 0.2 * noise(1.5)))
    _atlas_save("hod_cantonica", col, emi, spec)


def zygerria_atlas():
    """hod_zygerria textures from the TCW stills of the Zygerrian capital: slate-blue palace stone in battered courses
    (and with rows of lit arched windows), terracotta brick, warm sandstone (plain and lit), teal tent-roof cloth,
    bronze, black doorways, red / orange / cream striped awnings, pale trim stone, dark metal."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    N = LM_S
    t = N // 4
    rng = np.random.default_rng(85)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    norm = lambda a: (a - a.min()) / np.ptp(a)
    grime = norm(ndi.gaussian_filter(rng.random((t, t)), 2))[..., None]
    blotch = norm(ndi.gaussian_filter(rng.random((t, t)), 10))[..., None]
    streak = norm(ndi.gaussian_filter(rng.random((t, t)), (28, 1.2)))[..., None]
    col = np.zeros((N, N, 3), np.float32)
    emi = np.zeros((N, N), np.float32)
    spec = np.full((N, N), 30, np.float32)

    def put(rect, rgb, e=None, sp=30):
        u0, v0, u1, v1 = rect
        r, c = slice(int(round((1 - v1) * N)), int(round((1 - v0) * N))), slice(int(round(u0 * N)), int(round(u1 * N)))
        col[r, c] = np.clip(rgb, 0, 255)
        if e is not None:
            emi[r, c] = e
        spec[r, c] = sp
    aged = lambda rgb: rgb * (0.8 + 0.3 * streak) * (0.85 + 0.25 * blotch)
    courses = ((yy % 24) < 2)[..., None]
    joints = (((xx + 20 * ((yy // 24) % 2)) % 40) < 2)[..., None] & ~courses
    block = 1 - 0.22 * courses - 0.12 * joints
    slate = aged(np.array([92, 112, 140], np.float32) * (0.8 + 0.3 * grime) * block)
    put(Z_SLATE, slate)
    arch = (((xx % 32) > 10) & ((xx % 32) < 22) & ((yy % 48) > 14) & ((yy % 48) < 38)
            & ~(((yy % 48) < 18) & (np.abs((xx % 32) - 16) > 4)))                # tall slits with arched heads
    lit = arch & (rng.random((t, t)) > 0.35)
    put(Z_SLATE_WIN, np.where(arch[..., None], [40, 36, 30], slate), e=np.where(lit, 210, 0))
    put(Z_RED, aged(np.array([150, 70, 52], np.float32) * (0.8 + 0.3 * grime) * (1 - 0.25 * ((yy % 12) < 2)[..., None])))
    sand = aged(np.array([196, 160, 116], np.float32) * (0.82 + 0.25 * grime) * (1 - 0.15 * courses))
    put(Z_SAND, sand)
    win = ((xx % 24) > 8) & ((xx % 24) < 16) & ((yy % 32) > 10) & ((yy % 32) < 22)
    put(Z_SAND_WIN, np.where(win[..., None], [52, 44, 36], sand), e=np.where(win & (rng.random((t, t)) > 0.4), 200, 0))
    folds = (0.85 + 0.15 * np.sin(xx / 6.0))[..., None]
    put(Z_ROOF, np.array([70, 128, 118], np.float32) * (0.8 + 0.25 * grime) * folds)
    put(Z_BRONZE, np.array([168, 128, 70], np.float32) * (0.75 + 0.35 * grime), sp=120)
    put(Z_DARK, np.array([22, 20, 22], np.float32) * (0.8 + 0.4 * grime))
    stripes = ((xx // 20) % 3)[..., None]
    put(Z_AWNING, np.where(stripes == 0, [196, 70, 40], np.where(stripes == 1, [230, 150, 50], [226, 210, 170])) * (0.85 + 0.2 * grime))
    put(Z_PALE, aged(np.array([200, 196, 180], np.float32) * (0.85 + 0.2 * grime)))
    put(Z_METAL, np.array([70, 70, 76], np.float32) * (0.8 + 0.3 * grime), sp=90)
    put(Z_SPARE, sand)
    full = lambda v: np.full((N, N), v, np.float32)
    save_dxt5_mips(np.dstack([col, full(255)]), f"{LM_OUT}/hod_zygerria_diffuse.dds")
    save_dxt5_mips(np.dstack([full(0), full(128), emi, full(128)]), f"{LM_OUT}/hod_zygerria_normal.dds")
    save_dxt5_mips(np.dstack([full(0), spec, full(0), full(100)]), f"{LM_OUT}/hod_zygerria_properties.dds")
    Image.fromarray(col.astype(np.uint8)).resize((512, 512)).save("WIPGFX/research/previews/zygerria_atlas.png")
    print("zygerria atlas written to", LM_OUT)


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

    def build(name, geometry, shader="PdxMeshAdvancedSnow", out=LM_OUT, tex="hod_landmarks", rot=0.0):
        """rot: turn the model about its vertical axis (radians, counter-clockwise seen from above) before export"""
        if only and not name.startswith(only):
            return
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bm = bmesh.new()
        geometry(Kit(bm, bm.loops.layers.uv.new("UVMap")))
        if rot:
            from mathutils import Matrix  # type: ignore
            bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(rot, 3, "Z"))
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

    # ---- Korriban (korriban_research.md: KOTOR, The Old Republic, The Clone Wars, comics) ---------------------------
    def kstatue(k, x, y, h, base=True):
        """hooded robed Sith lord, arms crossed, facing -y (the Valley's statues, tomb guardians)"""
        if base:
            k.box(x - 0.24 * h, y - 0.24 * h, -SKIRT, x + 0.24 * h, y + 0.24 * h, 0.08 * h, K_STONE)
        z0 = 0.08 * h if base else 0.0
        k.lathe([(0.2 * h, z0), (0.17 * h, z0 + 0.35 * h), (0.13 * h, z0 + 0.62 * h), (0.15 * h, z0 + 0.72 * h),
                 (0.11 * h, z0 + 0.8 * h), (0.09 * h, z0 + 0.93 * h), (0.0, z0 + h)],
                [K_STATUE] * 6, sides=10, cx=x, cy=y, sy=0.8)
        k.box(x - 0.12 * h, y - 0.16 * h, z0 + 0.52 * h, x + 0.12 * h, y - 0.1 * h, z0 + 0.6 * h, K_STATUE)   # arms
        k.box(x - 0.06 * h, y - 0.1 * h, z0 + 0.8 * h, x + 0.06 * h, y - 0.08 * h, z0 + 0.88 * h, K_DARK)    # face in shadow

    def kobelisk(k, x, y, h, w=0.22):
        k.box(x - w * 1.3, y - w * 1.3, -SKIRT, x + w * 1.3, y + w * 1.3, 0.12, K_STONE)
        k.lathe([(w * 1.41, 0.12), (w * 1.0, h), (0.0, h + w * 1.5)], [K_GLYPH, K_GOLD], sides=4, cx=x, cy=y,
                rot=math.pi / 4)

    def kstairs(k, x0, x1, y0, y1, z1, steps=5):
        """steps rising from y0 (low, front) to y1 at height z1"""
        for i in range(steps):
            t0 = i / steps
            k.box(x0, y0 + (y1 - y0) * t0, -SKIRT, x1, y1, z1 * (i + 1) / steps, K_STONE)

    def krubble(k, rng, x0, x1, y0, y1, n, size=(0.15, 0.45)):
        """broken blocks strewn about, a few tilted"""
        for _ in range(n):
            x, y, w = rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(*size)
            k.box(x - w, y - w * 0.8, -0.3, x + w, y + w * 0.8, w * rng.uniform(0.6, 1.4), K_RUBBLE)

    def kfallen(k, x, y, h, ang):
        """a toppled statue lying on the ground, broken in two"""
        c, s_ = math.cos(ang), math.sin(ang)
        k.tube((x, y, 0.15), (x + c * h * 0.55, y + s_ * h * 0.55, 0.2), 0.16 * h, K_STATUE, sides=8, r1=0.13 * h)
        k.tube((x + c * h * 0.68, y + s_ * h * 0.68, 0.12), (x + c * h * 0.95, y + s_ * h * 0.95, 0.1), 0.1 * h, K_STATUE,
               sides=8, r1=0.04 * h)

    def ksand(k, x0, x1, y0, y1, z):
        """a drift of sand banked against a wall (wedge from z at y1 down to the ground at y0)"""
        bm = k.bm
        v = [bm.verts.new(q) for q in ((x0, y0, -0.2), (x1, y0, -0.2), (x1, y1, z), (x0, y1, z), (x0, y1, -0.2), (x1, y1, -0.2))]
        for f_, uv in (((v[0], v[1], v[2], v[3]), ((0, 0), (1, 0), (1, 1), (0, 1))), ((v[0], v[3], v[4]), ((0, 0), (1, 1), (1, 0))),
                       ((v[1], v[5], v[2]), ((0, 0), (1, 0), (1, 1)))):
            k.put(bm.faces.new(f_), uv, K_SAND)

    def korriban_tomb(k, variant):
        """a tomb cut into the cliff: only its entrance stands out of the rock. The block behind (+y) runs into the
        mountain; the portal faces -y. Aged: guardians broken or toppled, steps half buried in sand, rubble about."""
        rng = random.Random("tomb" + variant)
        tblock(k, [(-2.0, 0.2), (2.0, 0.2), (2.0, 4.0), (-2.0, 4.0)], -SKIRT, 3.2, K_GLYPH, K_STONE)     # into the rock
        if variant in "ac":                    # pylon portal: two battered pylons, a heavy lintel (cracked through)
            for x in (-1.15, 1.15):
                tblock(k, [(x - 0.55, -0.4), (x + 0.55, -0.4), (x + 0.55, 0.4), (x - 0.55, 0.4)], -SKIRT, 3.0, K_GLYPH, K_STONE,
                       poly_top=[(x - 0.42, -0.28), (x + 0.42, -0.28), (x + 0.42, 0.3), (x - 0.42, 0.3)])
            k.box(-1.75, -0.45, 3.0, -0.05, 0.4, 3.55, K_STONE)
            k.box(0.08, -0.4, 2.95, 1.75, 0.4, 3.45, K_STONE)                                       # the broken half sagged
            k.box(-0.6, -0.12, 0.0, 0.6, 0.25, 2.6, K_DARK)
        else:                                  # stepped frame: nested receding frames round a narrow door
            for i_, (w, h, d) in enumerate(((1.8, 3.2, -0.5), (1.4, 2.8, -0.3), (1.0, 2.4, -0.1))):
                k.box(-w, d, -SKIRT, w, d + 0.25, h, K_GLYPH if i_ % 2 == 0 else K_STONE)
            k.box(-0.45, -0.55, 0.0, 0.45, -0.48, 2.0, K_DARK)
            if variant == "d":                 # the face of a sleeping king over the door, half its brow fallen
                k.lathe([(0.9, 2.6), (0.85, 3.3), (0.6, 3.9), (0.0, 4.1)], [K_STATUE] * 3, sides=10, cx=0, cy=-0.1, sy=0.6)
                k.box(-0.3, -0.62, 3.0, -0.08, -0.52, 3.15, K_DARK)
                k.box(0.08, -0.62, 3.0, 0.3, -0.52, 3.15, K_DARK)
        # guardians: one standing (a third of the time headless), the other toppled on the steps
        side = rng.choice((-1, 1))
        kstatue(k, side * 1.9, -1.0, rng.uniform(1.8, 2.3))
        kfallen(k, -side * 1.6, -1.4, 2.0, rng.uniform(-2.6, -0.5))
        kstairs(k, -0.9, 0.9, -1.9, -0.5, 0.45, 3)
        ksand(k, -2.2, 2.2, -2.4, -0.5, 0.9)                                                         # sand blown in
        krubble(k, rng, -2.4, 2.4, -3.0, -0.6, 9)
        if variant == "b":                     # a broken obelisk before the door
            kobelisk(k, 1.4, -2.6, 0.9, 0.18)
            k.tube((-0.4, -2.9, 0.15), (-1.8, -2.4, 0.3), 0.16, K_GLYPH, sides=4, r1=0.12)

    def korriban_ragnos(k):
        # Tomb of Marka Ragnos (KOTOR): a horned colossus seated in the cliff, a stair running up into its chest
        k.box(-2.2, -0.2, -SKIRT, 2.2, 2.6, 1.2, K_STONE)                                 # throne base
        for x in (-0.9, 0.9):
            k.box(x - 0.55, -1.2, 1.2, x + 0.55, 0.6, 2.2, K_STATUE)                     # thighs
            k.box(x - 0.5, -1.3, -SKIRT, x + 0.5, -0.7, 1.2, K_STATUE)                   # shins
        tblock(k, [(-1.4, 0.4), (1.4, 0.4), (1.4, 2.0), (-1.4, 2.0)], 2.2, 4.4, K_STATUE, K_STATUE,
               poly_top=[(-1.1, 0.6), (1.1, 0.6), (1.1, 1.8), (-1.1, 1.8)])
        for x in (-1.9, 1.9):                                                             # forearms on the throne
            k.box(x - 0.35, -0.6, 2.2, x + 0.35, 1.6, 2.7, K_STATUE)
        k.lathe([(0.8, 4.4), (0.75, 5.2), (0.5, 5.8), (0.0, 6.0)], [K_STATUE] * 3, sides=10, cx=0, cy=1.1, sy=0.85)
        for sx in (-1, 1):                                                                # horns
            k.tube((sx * 0.6, 1.0, 5.4), (sx * 1.3, 0.8, 6.6), 0.16, K_STATUE, sides=6, r1=0.05)
        k.box(-0.35, 0.35, 2.4, 0.35, 0.45, 3.6, K_DARK)                                  # door in the chest
        kstairs(k, -0.4, 0.4, -2.4, 0.4, 2.4, 8)
        for x in (-0.9, 0.9):
            kstatue(k, x, -2.6, 1.3)

    def korriban_twins(k):
        # the Sith temple of Moraband (canon): two colossal hooded statues guarding a gate cut in the rock
        k.box(-3.2, 0.0, -SKIRT, 3.2, 2.0, 3.0, K_STONE, top=K_STONE)
        k.box(-0.8, -0.06, 0.0, 0.8, 0.02, 2.4, K_DARK)
        for x in (-1.9, 1.9):
            kstatue(k, x, -0.6, 6.5)
        kstairs(k, -1.0, 1.0, -2.0, -0.1, 0.5, 4)

    def korriban_head(k):
        # colossal stone head of a fallen statue, half buried, tilted
        k.lathe([(0.0, -0.6), (0.9, -0.3), (1.05, 0.6), (0.9, 1.4), (0.5, 1.9), (0.0, 2.0)], [K_STATUE] * 5,
                sides=12, cy=0, sy=0.85, jitter=0.04)
        k.box(-0.55, -0.92, 0.5, 0.55, -0.7, 1.4, K_STATUE)
        k.box(-0.4, -0.95, 1.05, -0.12, -0.85, 1.2, K_DARK)
        k.box(0.12, -0.95, 1.05, 0.4, -0.85, 1.2, K_DARK)

    def korriban_academy(k):
        # the Sith Academy (TOR's temple at the valley's head), long abandoned: a battered red-stone temple on a
        # platform, a huge dark portal between two colossal hooded guardians (one fallen), a stepped upper tier whose
        # spire broke off and lies across the platform, the right wing collapsed, sand drifted up the steps, broken
        # obelisks down the approach. Faces -y.
        rng = random.Random("academy")
        tblock(k, [(-5.6, -3.6), (5.6, -3.6), (5.6, 4.6), (-5.6, 4.6)], -SKIRT, 0.8, K_STONE, K_STONE)        # platform
        tblock(k, [(-3.6, -2.2), (3.6, -2.2), (3.6, 3.8), (-3.6, 3.8)], 0.8, 5.6, K_GLYPH, K_STONE,
               poly_top=[(-2.9, -1.5), (2.9, -1.5), (2.9, 3.1), (-2.9, 3.1)])                                  # temple
        tblock(k, [(-2.3, -0.9), (2.3, -0.9), (2.3, 2.6), (-2.3, 2.6)], 5.6, 7.4, K_GLYPH, K_STONE,
               poly_top=[(-1.8, -0.4), (1.8, -0.4), (1.8, 2.1), (-1.8, 2.1)])                                  # upper tier
        k.lathe([(0.75, 7.4), (0.55, 9.6), (0.42, 10.1)], [K_GLYPH, K_STONE], sides=4, cx=0.0, cy=0.85,
                rot=math.pi / 4)                                                                               # spire stump
        k.tube((2.6, -1.0, 0.95), (5.2, -3.0, 1.3), 0.4, K_GLYPH, sides=4, r1=0.12)                          # ...fallen
        for x0, x1 in ((-1.35, -0.95), (0.95, 1.35)):                                                       # portal frame
            k.box(x0, -2.45, 0.8, x1, -2.0, 4.6, K_STONE)
        k.box(-1.35, -2.45, 4.3, 1.35, -2.0, 4.9, K_STONE)
        k.box(-0.95, -2.3, 0.8, 0.95, -2.1, 4.3, K_DARK)
        kstairs(k, -1.3, 1.3, -3.6, -2.2, 0.8, 4)
        kstatue(k, -2.3, -2.9, 4.4)                                                                          # guardians
        kfallen(k, 2.0, -3.1, 4.2, -0.4)
        tblock(k, [(-5.3, -1.6), (-3.6, -1.6), (-3.6, 3.0), (-5.3, 3.0)], 0.8, 3.2, K_GLYPH, K_STONE)        # left wing
        tblock(k, [(3.6, -1.6), (5.3, -1.6), (5.3, 3.0), (3.6, 3.0)], 0.8, 1.5, K_GLYPH, K_RUBBLE)           # right: fallen
        krubble(k, rng, 3.5, 5.8, -2.0, 3.4, 14, (0.25, 0.6))
        for x, y, z0, z1 in ((-4.7, -1.65, 1.4, 2.6), (-2.0, -2.25, 2.4, 3.6), (2.4, 2.1, 5.8, 6.8)):        # holes
            k.box(x - 0.3, y - 0.05, z0, x + 0.3, y + 0.05, z1, K_DARK)
        for x, y, h in ((-1.8, -5.0, 2.2), (1.8, -5.0, 0.8), (-1.8, -6.8, 1.1), (1.8, -6.8, 2.0)):          # approach
            kobelisk(k, x, y, h, 0.2)
        ksand(k, -5.8, 5.8, -5.2, -3.6, 1.0)
        krubble(k, rng, -6.0, 6.0, -7.5, -3.8, 18, (0.15, 0.45))

    def korriban_ziggurat(k):
        # the Sith Citadel: an ancient stepped ziggurat, a stair up its face (-y) to a dark shrine, one corner
        # slumped into rubble, obelisks at the foot of the stair
        rng = random.Random("ziggurat")
        for i in range(5):
            w0, w1, z0 = 4.2 - 0.75 * i, 4.2 - 0.75 * i - 0.2, 0.95 * i
            tblock(k, [(-w0, -w0), (w0, -w0), (w0, w0), (-w0, w0)], -SKIRT if i == 0 else z0, z0 + 0.95, K_GLYPH, K_STONE,
                   poly_top=[(-w1, -w1), (w1, -w1), (w1, w1), (-w1, w1)])
        k.box(-0.6, -0.4, 4.75, 0.6, 0.6, 5.9, K_STONE)                                                     # shrine
        k.box(-0.3, -0.45, 4.75, 0.3, -0.38, 5.5, K_DARK)
        kstairs(k, -0.7, 0.7, -5.4, -1.2, 4.75, 9)
        krubble(k, rng, 2.0, 4.6, 2.0, 4.6, 16, (0.3, 0.7))                                                  # slumped corner
        for x in (-1.6, 1.6):
            kobelisk(k, x, -5.6, 1.8 if x < 0 else 0.9, 0.2)
        krubble(k, rng, -5.0, 5.0, -6.5, -4.4, 10, (0.12, 0.35))

    def kcolumn(k, x, y, h, r=0.22):
        """a round column on a square base; h is what still stands"""
        k.box(x - r * 1.4, y - r * 1.4, -SKIRT, x + r * 1.4, y + r * 1.4, 0.18, K_STONE)
        k.lathe([(r, 0.18), (r * 0.92, h)], [K_GLYPH], sides=8, cx=x, cy=y, cap=K_STONE)

    def korriban_ruin(k, variant):
        """ruins strewn on the valley floor (Valley of Tombs map, KOTOR): a broken colonnade, a collapsed gateway, a
        fallen colossus, a roofless shrine; all half sunk in sand, rubble about"""
        rng = random.Random("ruin" + variant)
        if variant == "a":                     # colonnade: two rows, most broken, one lintel still up, drums fallen
            for row in (-0.8, 0.8):
                for i, x in enumerate((-2.1, -0.7, 0.7, 2.1)):
                    h = 2.6 if (row < 0 and i in (1, 2)) else rng.choice((0.4, 0.8, 1.3, 1.9))
                    kcolumn(k, x, row, h)
            k.box(-1.0, -1.05, 2.6, 1.0, -0.55, 2.95, K_STONE)
            for _ in range(4):
                x, y, a = rng.uniform(-2.4, 2.4), rng.uniform(-0.3, 0.3), rng.uniform(0, math.pi)
                k.tube((x, y, 0.15), (x + math.cos(a) * 0.7, y + math.sin(a) * 0.7, 0.15), 0.2, K_GLYPH, sides=8)
        elif variant == "b":                   # gateway: two battered pylons, the lintel fallen and broken in two
            for x in (-1.3, 1.3):
                tblock(k, [(x - 0.6, -0.5), (x + 0.6, -0.5), (x + 0.6, 0.5), (x - 0.6, 0.5)], -SKIRT, 2.8 if x < 0 else 2.1,
                       K_GLYPH, K_STONE, poly_top=[(x - 0.45, -0.38), (x + 0.45, -0.38), (x + 0.45, 0.38), (x - 0.45, 0.38)])
            k.box(-0.9, -1.4, -0.1, 0.4, -0.9, 0.45, K_STONE)
            k.tube((0.6, -1.0, 0.15), (2.0, -1.9, 0.3), 0.26, K_STONE, sides=4)
            kstatue(k, -2.5, -0.9, 1.6)
        elif variant == "c":                   # fallen colossus: the plinth with its feet, the body broken on the sand
            k.box(-1.0, -0.8, -SKIRT, 1.0, 0.8, 0.7, K_STONE)
            for x in (-0.4, 0.4):
                k.box(x - 0.28, -0.45, 0.7, x + 0.28, 0.35, 1.3, K_STATUE)
            kfallen(k, 0.6, 1.4, 5.0, 0.35)
            k.lathe([(0.0, -0.3), (0.55, -0.1), (0.62, 0.45), (0.5, 0.9), (0.0, 1.05)], [K_STATUE] * 4, sides=10,
                    cx=-1.6, cy=2.6, sy=0.85)
        else:                                  # roofless shrine: stepped base, three broken walls, an altar
            tblock(k, [(-1.8, -1.6), (1.8, -1.6), (1.8, 1.6), (-1.8, 1.6)], -SKIRT, 0.35, K_STONE, K_STONE)
            tblock(k, [(-1.5, -1.3), (1.5, -1.3), (1.5, 1.3), (-1.5, 1.3)], 0.35, 0.7, K_STONE, K_STONE)
            k.box(-1.4, 0.95, 0.7, 1.4, 1.25, 2.4, K_GLYPH)
            k.box(-1.4, -0.9, 0.7, -1.1, 1.0, 1.7, K_GLYPH)
            k.box(1.1, -0.2, 0.7, 1.4, 1.0, 1.1, K_GLYPH)
            k.box(-0.4, 0.2, 0.7, 0.4, 0.7, 1.25, K_DARK, top=K_GOLD)
            ksand(k, -1.9, 1.9, -2.6, -1.6, 0.6)
        krubble(k, rng, -2.8, 2.8, -2.6, 2.6, 10, (0.12, 0.35))

    # ---- Florrum (The Clone Wars: Hondo's complex, the pirates' outposts, Hondo's secret ship vault) ------------------
    def ffin(k, a, r0, r1, rt, h, z0, thick, rect):
        """a tall triangular fin standing on a disc at angle a: base from radius r0 to r1 at z0, its tip at radius rt,
        height h (leaning in when rt < r0)"""
        bm = k.bm
        c, s_ = math.cos(a), math.sin(a)
        px, py = -s_ * thick / 2, c * thick / 2
        pts = [(r0, z0), (r1, z0), (rt, z0 + h)]
        sides = [[bm.verts.new((c * r + sg * px, s_ * r + sg * py, z)) for r, z in pts] for sg in (-1, 1)]
        a_, b_ = sides
        uv = [(0, 0), (1, 0), (0.5, 1)]
        k.put(bm.faces.new(a_[::-1]), uv[::-1], rect)
        k.put(bm.faces.new(b_), uv, rect)
        for i in range(3):
            j = (i + 1) % 3
            k.put(bm.faces.new((a_[i], a_[j], b_[j], b_[i])), ((0, 0), (1, 0), (1, 1), (0, 1)), rect)

    def fblade(k, pts, y0, y1, rect):
        """a flat blade: polygon [(x, z), ...] (counter-clockwise seen from -y) extruded from y0 to y1"""
        bm = k.bm
        fr = [bm.verts.new((x, y0, z)) for x, z in pts]
        bk = [bm.verts.new((x, y1, z)) for x, z in pts]
        xs, zs = [x for x, _ in pts], [z for _, z in pts]
        uv = [((x - min(xs)) / (max(xs) - min(xs)), (z - min(zs)) / (max(zs) - min(zs))) for x, z in pts]
        k.put(bm.faces.new(fr), uv, rect)
        k.put(bm.faces.new(bk[::-1]), uv[::-1], rect)
        for i in range(len(pts)):
            j = (i + 1) % len(pts)
            k.put(bm.faces.new((fr[j], fr[i], bk[i], bk[j])), ((0, 0), (1, 0), (1, 1), (0, 1)), rect)

    def florrum_complex(k):
        # Hondo's complex ("Dooku Captured" establishing shot): a round drum walled by Y-shaped struts, a panelled
        # skirt flaring out above it, a flat deck ringed by a raised outer ring; the spire is two tall blades with a
        # slit between them, standing OFF centre on a block at the ring's front edge (-y); a big turbine lies at the foot
        k.lathe([(2.5, -SKIRT), (2.5, 1.0)], [DARK_WIN], sides=24)                                # the drum
        for i in range(10):                                                                      # Y struts round it
            a = 2 * math.pi * i / 10
            c, s_ = math.cos(a), math.sin(a)
            k.tube((2.62 * c, 2.62 * s_, 0.0), (2.62 * c, 2.62 * s_, 0.55), 0.07, METAL, sides=5)
            for d in (-0.22, 0.22):
                k.tube((2.62 * c, 2.62 * s_, 0.55), (2.65 * math.cos(a + d), 2.65 * math.sin(a + d), 0.95), 0.06, METAL, sides=5)
        k.lathe([(2.55, 0.95), (3.35, 1.55), (3.35, 1.62)], [SAND_WIN, SAND], sides=32)            # flared skirt
        k.lathe([(3.35, 1.62), (2.5, 1.66)], [DECK], sides=32, cap=DECK)                         # the deck
        k.lathe([(3.15, 1.6), (3.7, 1.6), (3.7, 1.95), (3.15, 1.95), (3.15, 1.6)], [METAL, SAND, METAL, SAND], sides=32)
        k.lathe([(2.0, 1.66), (2.25, 1.66), (2.25, 1.85), (2.0, 1.85), (2.0, 1.66)], [METAL, SAND, METAL, SAND], sides=24)
        # the spire: a block at the ring's front edge, two blades rising from it with a slit between
        k.box(-0.75, -3.4, 1.6, 0.75, -2.5, 2.45, SAND_WIN, top=SAND)
        fblade(k, [(-0.07, 2.4), (-0.07, 7.6), (-0.7, 2.4)][::-1], -3.25, -2.65, SAND)
        fblade(k, [(0.07, 2.4), (0.7, 2.4), (0.07, 7.2)], -3.25, -2.65, SAND)
        k.tube((1.4, -3.3, 0.35), (3.0, -2.6, 0.45), 0.42, RUST, sides=10)                       # the turbine at its foot
        for x, y in ((-3.9, -2.3), (3.6, 2.9)):                                                  # gate posts (lit pink in the show)
            for dx in (-0.25, 0.25):
                k.box(x + dx - 0.06, y - 0.06, -0.2, x + dx + 0.06, y + 0.06, 0.6, METAL)
            k.box(x - 0.31, y - 0.06, 0.6, x + 0.31, y + 0.06, 0.68, METAL)

    def florrum_outpost(k, variant):
        rng = random.Random("flo" + variant)
        if variant == "a":                     # pirate post: a two-tier disc with two fins and a pad
            k.lathe([(1.25, -SKIRT), (1.25, 0.35), (0.95, 0.5), (0.85, 0.85)], [SAND, SAND_WIN, SAND], sides=16, cap=DECK)
            for a in (0.4, 0.4 + math.pi):
                ffin(k, a, 0.4, 1.1, 0.2, 1.8, 0.8, 0.16, SAND)
            k.lathe([(0.6, -SKIRT), (0.6, 0.15)], [METAL], sides=12, cx=1.9, cy=0.4, cap=DECK)
        else:                                  # mercenary keep ("A Necessary Bond"): a battered block, two great fins
            tblock(k, [(-1.3, -1.0), (1.3, -1.0), (1.3, 1.0), (-1.3, 1.0)], -SKIRT, 1.1, SAND_WIN, SAND,
                   poly_top=[(-0.9, -0.7), (0.9, -0.7), (0.9, 0.7), (-0.9, 0.7)])
            for a, lean in ((0.0, 0.6), (math.pi, 0.6)):
                ffin(k, a, 0.6, 1.5, 1.5 + lean, 2.4, 1.0, 0.2, SAND)
            k.box(-0.4, -1.05, 0.0, 0.4, -0.98, 0.7, DARK_WIN)
        for _ in range(4):                                                                       # crates
            x, y, w = rng.uniform(-1.8, 1.8), rng.uniform(-1.8, 1.8), rng.uniform(0.12, 0.22)
            if math.hypot(x, y) > 1.4:
                k.box(x - w, y - w, -0.2, x + w, y + w, w * 1.6, RUST)

    def florrum_refinery(k):
        # a Commerce Guild sulfur works: domed tanks, a drill derrick over the acid flat, pipes, a pump house
        for x, y, r in ((-1.0, 0.6, 0.55), (0.1, 0.9, 0.45), (-0.4, -0.5, 0.5)):
            k.lathe([(r, -SKIRT), (r, 0.9), (r * 0.7, 1.15), (0.0, 1.25)], [METAL, METAL, METAL], sides=12, cx=x, cy=y)
        for dx, dy in ((-0.35, -0.35), (0.35, -0.35), (0.35, 0.35), (-0.35, 0.35)):                  # derrick
            k.tube((1.3 + dx, -0.3 + dy, 0.0), (1.3 + dx * 0.25, -0.3 + dy * 0.25, 2.6), 0.05, RUST, sides=5)
        k.box(1.1, -0.5, 2.5, 1.5, -0.1, 2.75, RUST)
        k.tube((-1.0, 0.6, 0.5), (1.3, -0.3, 0.3), 0.08, BRONZE, sides=6)
        k.tube((-0.4, -0.5, 0.4), (1.3, -0.3, 0.3), 0.08, BRONZE, sides=6)
        k.box(0.5, 0.4, -SKIRT, 1.5, 1.2, 0.6, METAL_WIN, top=METAL)

    def florrum_vault(k):
        # Hondo's secret ship vault: a blast door in a rock face (front -y), a ramp down to it, a pad before it
        k.lathe([(1.9, -SKIRT), (1.8, 0.9), (1.3, 1.9), (0.6, 2.4), (0.0, 2.5)], [REDROCK] * 4, sides=9, cy=1.4,
                sy=0.8, jitter=0.12)
        k.box(-0.8, -0.05, -SKIRT, 0.8, 0.25, 1.3, METAL)
        k.box(-0.62, -0.1, 0.0, 0.62, -0.04, 1.1, DARK_WIN)
        k.box(-0.65, -1.3, -SKIRT, 0.65, -0.05, 0.08, DECK)
        k.lathe([(0.7, -SKIRT), (0.7, 0.1)], [METAL], sides=12, cx=0.0, cy=-2.1, cap=DECK)

    # ---- Kadavo (The Clone Wars "Escape from Kadavo": the slave processing facility over its crater) ----------------
    KAD_ARMS = (90, 210, 330)        # = kadavo_map.ARMS: the girder arms' bearings (degrees, counter-clockwise from east)
    KAD_RIM = 6.8                    # the crater rim above the model's origin (the bowl floor under the hub;
                                     # planet_terrain_gen.py (KAD_DECK - KAD_FLOOR - 1) / 10)

    def kadavo_facility(k):
        # the slave processing facility, measured off the user's plan2.png (side view, one arm; 2026-10-13). Plan pixels
        # -> model: K units per px, plan x 910 = the axis, plan y 1070 = the crater rim (KAD_RIM above the origin, the
        # bowl floor). Bottom to top: antenna; "lower circular prob, slaves facilities" (round, chamfered top); the
        # "circular/closest to hexagonal facility"; the long triangular platform surrounding the station; the quarters
        # (triangular, full of windows) with a tall block at each corner; a trapezoid deck, pillars, and the tall tower
        # with a notched top. In front of each side a small two-stage tower. At each corner a chimney (spike below), a
        # short double strut out to a pod, then two struts down to the ground beyond the rim. Three arms (KAD_ARMS).
        K = 0.0308
        KAD_DROP = 5.5                   # how far the station sits below the plan's ground line (user: into the crater)
        Z = lambda y: KAD_RIM - KAD_DROP + (1070 - y) * K                                      # the station sunk into the bowl
        P = lambda x: (x - 910) * K
        tri = lambda r, bs=KAD_ARMS: [(r * math.cos(math.radians(b_)), r * math.sin(math.radians(b_))) for b_ in bs]
        k.lathe([(0.12, Z(1015)), (0.0, Z(1103))], [DARK], sides=6)                              # antenna
        k.lathe([(0.0, Z(1015)), (P(1017), Z(1015)), (P(1068), Z(908)), (P(1035), Z(890)), (0.0, Z(890))],
                [METAL, METAL_WIN, METAL, METAL], sides=16)                                        # lower slave facility
        k.lathe([(P(1080), Z(888)), (P(1098), Z(815))], [METAL_WIN], sides=6, cap=METAL)          # the hexagonal facility
        tblock(k, tri(12.5), Z(838), Z(817), DECK, DECK)                                           # the triangular platform
        tblock(k, tri(9.0), Z(815), Z(740), METAL_WIN, METAL)                                      # the quarters
        for bearing in KAD_ARMS:                                                                   # the corner blocks
            c, s_ = math.cos(math.radians(bearing)), math.sin(math.radians(bearing))
            rot = lambda u, v: (c * u - s_ * v, s_ * u + c * v)
            tblock(k, [rot(P(1190), -1.1), rot(P(1247), -1.1), rot(P(1247), 1.1), rot(P(1190), 1.1)], Z(863), Z(697),
                   METAL_WIN, METAL)
        k.lathe([(P(1048), Z(740)), (P(1025), Z(662))], [METAL_WIN], sides=6, cap=METAL)          # the trapezoid deck
        for i in range(4):                                                                         # its pillars
            a_ = math.pi / 4 + i * math.pi / 2
            k.tube((2.6 * math.cos(a_), 2.6 * math.sin(a_), Z(664)), (2.6 * math.cos(a_), 2.6 * math.sin(a_), Z(588)),
                   0.3, METAL, sides=6)
        w0, w1 = P(1015), P(969)                                                                   # the tall tower
        tblock(k, [(-w0, -w0), (w0, -w0), (w0, w0), (-w0, w0)], Z(590), Z(318), METAL_WIN, METAL,
               poly_top=[(-w1, -w1), (w1, -w1), (w1, w1), (-w1, w1)])
        for x0, x1 in ((-w1, -0.85), (0.85, w1)):                                                  # its notched top
            k.box(x0, -w1, Z(318), x1, w1, Z(298), METAL, top=METAL)
        for bearing in (30, 150, 270):                                                             # the small front towers
            cx, cy = 5.4 * math.cos(math.radians(bearing)), 5.4 * math.sin(math.radians(bearing))
            k.lathe([(P(972) * 0.98, Z(815)), (P(943) - P(910) + 0.2, Z(716))], [METAL_WIN], sides=4, rot=math.pi / 4,
                    cx=cx, cy=cy, cap=METAL)
            k.lathe([(0.45, Z(716)), (0.45, Z(695))], [DARK], sides=6, cx=cx, cy=cy)
            k.lathe([(P(940) + 0.06, Z(695)), (P(928) + 0.06, Z(563))], [METAL_WIN], sides=4, rot=math.pi / 4,
                    cx=cx, cy=cy, cap=METAL)
        for bearing in KAD_ARMS:
            c, s_ = math.cos(math.radians(bearing)), math.sin(math.radians(bearing))
            px, py = -s_, c
            at = lambda r, z, t=0.0: (c * r + px * t, s_ * r + py * t, z)
            rc = (P(1267) + P(1335)) / 2                                                           # the chimney
            k.lathe([(0.48, Z(671)), (0.9, Z(740)), (1.05, Z(762)), (1.05, Z(900)), (0.6, Z(915)), (0.0, Z(922))],
                    [RUST, METAL, METAL_WIN, METAL, METAL], sides=10, cx=c * rc, cy=s_ * rc, cap=DARK)
            k.lathe([(0.1, Z(918)), (0.0, Z(990))], [DARK], sides=5, cx=c * rc, cy=s_ * rc)
            for t in (-0.35, 0.35):                                                                # chimney -> pod
                k.tube(at(P(1335), Z(825), t), at(P(1437), Z(880), t), 0.09, METAL, sides=5)
                k.tube(at(P(1335), Z(862), t), at(P(1425), Z(905), t), 0.09, METAL, sides=5)
            rp = (P(1430) + P(1490)) / 2                                                           # the pod
            k.lathe([(0.0, Z(970)), (0.36, Z(970)), (0.36, Z(940)), (0.92, Z(920)), (0.92, Z(865)), (0.28, Z(836)),
                     (0.0, Z(834))], [METAL, METAL, DARK_WIN, METAL_WIN, METAL, METAL], sides=10, cx=c * rp, cy=s_ * rp)
            for (x0, y0), (x1, y1) in (((1490, 882), (1690, 1068)), ((1492, 910), (1690, 1068))):  # struts to one footing
                za, zb = Z(y0), KAD_RIM                                                            # pod -> footing on the rim
                for t in (-0.35, 0.35):
                    k.tube(at(P(x0), za, t), at(P(x1), zb - 0.4, t), 0.13, METAL, sides=5)
                n_ = 7
                for i in range(1, n_):
                    f = i / n_
                    xx, zz_ = x0 + (x1 - x0) * f, za + (zb - 0.4 - za) * f
                    k.tube(at(P(xx), zz_, -0.35), at(P(xx), zz_, 0.35), 0.05, METAL, sides=4)
                if y0 != 882:
                    continue                                                                       # one footing per arm
                rf = P(x1)                                                                         # the footing
                tblock(k, [(c * rf - 0.7, s_ * rf - 0.7), (c * rf + 0.7, s_ * rf - 0.7), (c * rf + 0.7, s_ * rf + 0.7),
                           (c * rf - 0.7, s_ * rf + 0.7)], KAD_RIM - 2.0, KAD_RIM + 0.5, METAL, METAL)

    KAD_CRATER_PROFILES = {
        # (r, z) from the foot round the shoulder to the lip and down the throat; the lip index splits outside/inside
        "a": ([(1.0, -0.25), (1.03, 0.12), (1.0, 0.34), (0.92, 0.55), (0.8, 0.7), (0.66, 0.78), (0.56, 0.77)],
              [(0.5, 0.68), (0.47, 0.4), (0.44, 0.0), (0.4, -0.35)], 3.2),               # a high bulging beehive
        "b": ([(1.0, -0.2), (1.0, 0.06), (0.95, 0.18), (0.86, 0.27), (0.77, 0.3)],
              [(0.7, 0.24), (0.66, 0.1), (0.62, -0.1), (0.55, -0.3)], 4.6),               # a low wide ring
        "c": ([(1.0, -0.25), (1.02, 0.15), (0.97, 0.38), (0.86, 0.55), (0.72, 0.64), (0.6, 0.64)],
              [(0.54, 0.55), (0.5, 0.25), (0.46, -0.3)], 2.6),                             # a rounded dome
        "d": ([(1.0, -0.25), (1.0, 0.2), (0.88, 0.5), (0.7, 0.68), (0.55, 0.7)],
              [(0.48, 0.6), (0.44, 0.2), (0.4, -0.3)], 1.4),                               # a little pit cone
    }

    def kadavo_crater(k, variant):
        """a volcanic crater of Kadavo: a bulging dome of pillowed blocks with a wide round mouth dropping into a dark
        throat (stills). Built here rather than by lathe(): the texture must repeat round the dome, not stretch."""
        import bmesh  # type: ignore
        outer, inner, R = KAD_CRATER_PROFILES[variant]
        prof = [(r * R, z * R) for r, z in outer + inner]
        n_out = len(outer)
        sides = 40
        rng_ = random.Random("crater" + variant)
        ph = [rng_.uniform(0, 6.28) for _ in range(3)]
        wob = [1 + 0.035 * math.sin(2 * math.pi * i / sides * 2 + ph[0]) + 0.02 * math.sin(2 * math.pi * i / sides * 3 + ph[1])
               for i in range(sides)]                                                    # gently out of round
        rings = [[k.bm.verts.new((r * wob[i] * math.cos(2 * math.pi * i / sides), r * wob[i] * math.sin(2 * math.pi * i / sides), z))
                  for i in range(sides)] for r, z in prof]
        circ = 2 * math.pi * R
        seg = [0.0]
        for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
            seg.append(seg[-1] + math.hypot(r1 - r0, z1 - z0))
        reps = max(2, round(circ / (seg[n_out - 1] * 1.6)))                                    # blocks keep their shape
        for kk in range(len(prof) - 1):
            inside = kk >= n_out - 1
            span = (seg[n_out - 1] if not inside else seg[-1] - seg[n_out - 1]) or 1
            base = 0.0 if not inside else seg[n_out - 1]
            v0 = (seg[kk] - base) / span
            v1 = (seg[kk + 1] - base) / span
            vv = (lambda v: 0.51 + 0.48 * (1 - v)) if not inside else (lambda v: 0.49 - 0.48 * v)  # outside: top half
            for i in range(sides):
                j = (i + 1) % sides
                f = k.bm.faces.new((rings[kk][i], rings[kk][j], rings[kk + 1][j], rings[kk + 1][i]))
                f.smooth = True                                                                  # a rounded dome, no facets
                u0, u1 = i / sides * reps, (i + 1) / sides * reps
                for loop, uv in zip(f.loops, ((u0, vv(v0)), (u1, vv(v0)), (u1, vv(v1)), (u0, vv(v1)))):
                    loop[k.uv].uv = uv

    def kadavo_tower(k):
        # a ray-shield tower ("Escape from Kadavo"; comic: a tall tower held by cables): tapering shaft, a ring of
        # emitters, a domed top, three anchor cables
        k.lathe([(1.0, -SKIRT), (1.0, 0.6), (0.7, 1.0), (0.55, 7.0), (0.8, 7.4), (0.8, 7.9), (0.5, 8.4), (0.0, 8.8)],
                [METAL, METAL, METAL_WIN, METAL, DARK_WIN, METAL, METAL], sides=12)
        for i in range(3):
            a = 2 * math.pi * i / 3 + 0.4
            k.tube((0.45 * math.cos(a), 0.45 * math.sin(a), 6.2), (3.6 * math.cos(a), 3.6 * math.sin(a), -0.2), 0.04, DARK, sides=4)
            k.box(3.6 * math.cos(a) - 0.25, 3.6 * math.sin(a) - 0.25, -SKIRT, 3.6 * math.cos(a) + 0.25,
                  3.6 * math.sin(a) + 0.25, 0.3, METAL)

    def kadavo_dock(k):
        # the slavers' landing field: two raised pads, a control block with a mast, cargo
        for x, y in ((-1.6, 0.4), (1.7, -0.3)):
            k.lathe([(1.25, -SKIRT), (1.25, 0.35)], [METAL], sides=16, cx=x, cy=y, cap=DECK)
        k.box(-0.6, 1.4, -SKIRT, 0.9, 2.6, 1.3, METAL_WIN, top=METAL)
        k.tube((0.6, 2.2, 1.3), (0.6, 2.2, 2.8), 0.05, METAL, sides=5)
        for x in (-0.2, 0.25):
            k.box(x - 0.2, -1.8, -0.2, x + 0.2, -1.4, 0.3, RUST)

    def kadavo_mine(k):
        # an ore pit's rig: a gantry crane over the pit, a conveyor up to heaps of red Kadavo ore
        for x in (-1.6, 1.6):
            for y in (-0.8, 0.8):
                k.tube((x, y, -0.5), (x, y, 2.2), 0.08, RUST, sides=5)
        k.box(-1.8, -0.9, 2.1, 1.8, 0.9, 2.35, RUST)
        k.box(-0.3, -0.3, 1.2, 0.3, 0.3, 2.1, METAL)
        k.tube((1.6, 0.0, 1.8), (3.6, 0.6, 0.4), 0.12, METAL, sides=4)
        for x, y, r in ((3.9, 0.9, 0.7), (3.0, 1.6, 0.5)):
            k.lathe([(r, -0.3), (r * 0.6, r * 0.5), (0.0, r * 0.8)], [REDROCK, REDROCK], sides=8, cx=x, cy=y, jitter=0.2)

    def kadavo_camp(k):
        # a Zygerrian slave camp: a fenced compound of low huts, a watchtower at the gate
        for i in range(10):
            a = 2 * math.pi * i / 10
            k.tube((1.6 * math.cos(a), 1.6 * math.sin(a), -0.3), (1.6 * math.cos(a), 1.6 * math.sin(a), 0.6), 0.04, DARK, sides=4)
        for x, y in ((-0.6, -0.4), (0.5, -0.5), (-0.4, 0.6), (0.6, 0.5)):
            k.box(x - 0.35, y - 0.25, -0.2, x + 0.35, y + 0.25, 0.35, METAL, top=RUST)
        k.tube((1.6, 0.0, -0.2), (1.6, 0.0, 1.9), 0.08, METAL, sides=5)
        k.box(1.3, -0.3, 1.9, 1.9, 0.3, 2.3, DARK_WIN, top=METAL)

    def korriban_banner(k):
        k.lathe([(0.07, -0.5), (0.06, 3.2), (0.0, 3.4)], [K_GOLD, K_GOLD], sides=6)
        k.box(-0.42, -0.04, 1.0, 0.42, 0.04, 3.1, K_BANNER)

    def korriban_obelisks(k):
        for x, y, h in ((0.0, 0.0, 2.2), (0.9, 0.5, 1.5), (-0.8, 0.6, 1.2)):
            kobelisk(k, x, y, h)

    def dre_city(kit, band, rng):
        # Dreshdae (KOTOR, comics): round metal halls and domes, a squat tower with lit windows, dishes and masts
        for _ in range(rng.randint(1, 2 + band // 2)):
            x, y = rng.uniform(-0.55, 0.55), rng.uniform(-0.55, 0.55)
            r, h = rng.uniform(0.22, 0.32) + 0.03 * band, rng.uniform(0.2, 0.3) + 0.06 * band
            kit.lathe([(r, -0.5), (r, h), (r * 0.9, h + 0.05), (r * 0.5, h + 0.18), (0.0, h + 0.22)],
                      [K_METAL_WIN, K_METAL, K_METAL, K_METAL], sides=12, cx=x, cy=y)
        if band >= 2:
            x, y = rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)
            kit.lathe([(0.03, 0.0), (0.03, 0.6 + 0.2 * band), (0.0, 0.65 + 0.2 * band)], [K_METAL, K_LIGHT], sides=5, cx=x, cy=y)
            kit.lathe([(0.0, 0.25), (0.22, 0.33), (0.2, 0.36)], [K_METAL, K_METAL], sides=10, cx=-x, cy=-y)

    for band in range(1, 5):
        for v in range(1, 5):
            rng = random.Random(f"hod_dre_city{band}{v}")
            build(f"hod_dre_city_{band}{v}", lambda k, band=band, rng=rng: dre_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_korriban")
    # HOI4 ignores an ambient object's rotation (every model faced south in game): the models that face somewhere
    # come in KOR_TURNS turned copies, <name>_r<i> turned i * 360 / KOR_TURNS degrees counter-clockwise
    for name, fn in (("hod_kor_academy", korriban_academy), ("hod_kor_ragnos", korriban_ragnos),
                     ("hod_kor_twins", korriban_twins), ("hod_kor_statue", lambda k: kstatue(k, 0, 0, 3.0))) +             tuple((f"hod_kor_tomb_{v}", lambda k, v=v: korriban_tomb(k, v)) for v in "abcd"):
        for i_ in range(KOR_TURNS):
            build(f"{name}_r{i_}", fn, tex="hod_korriban", rot=2 * math.pi * i_ / KOR_TURNS)
    for v in "abcd":
        build(f"hod_kor_ruin_{v}", lambda k, v=v: korriban_ruin(k, v), tex="hod_korriban")
    def dk_citadel(k):
        # the Imperial Citadel of Kaas City (TOR still "Imperial Citadel"), ruined by the Clone Wars era (Legends): a very
        # tall chamfered dark tower with vertical ribs and window bands, two great diagonal buttress struts down to
        # needle masts with red tip lights, lit lower wings either side, the red Sith emblem over the gate. Ruin: the
        # crown broken off, the east strut snapped and fallen, the east mast broken, rubble. Map-scale (user rule).
        rng = random.Random("dk_citadel2")
        sq = lambda x, y: [(-x, -y), (x, -y), (x, y), (-x, y)]
        tblock(k, sq(9.0, 6.5), -SKIRT, 0.8, D_PLATE, D_PLATE)                                  # platform
        for sx in (-1, 1):                                                                           # lower wings
            k.box(min(3.2 * sx, 8.2 * sx), -3.4, 0.8, max(3.2 * sx, 8.2 * sx), 3.4, 4.6, D_PLATE, top=D_PLATE)
            for z in (1.6, 2.6, 3.6):                                                                # dark window rows
                k.box(min(3.6 * sx, 7.8 * sx), -3.45, z, max(3.6 * sx, 7.8 * sx), -3.38, z + 0.35, D_DARK)
        k.lathe([(3.0, 0.8), (2.8, 8.0), (2.3, 14.0), (1.7, 19.0), (1.4, 21.0)], [D_PLATE] * 4, sides=8, rot=math.pi / 8,
                cap=D_RUBBLE)                                                                          # broken top, closed
        for x, y in ((0.0, -2.78), (-1.97, -1.97), (1.97, -1.97)):                                   # ribs on the tapering faces
            k.tube((x, y, 1.0), (x * 0.6, y * 0.6, 18.5), 0.17, D_DARK, sides=4)
        for z in (9.0, 11.0, 13.0):
            k.box(-1.0, -2.55 + 0.04 * z, z, 1.0, -2.45 + 0.04 * z, z + 0.5, D_PLATE_WIN)
        for x, y, h in ((-0.9, -0.5, 1.6), (0.4, 0.6, 1.0), (0.9, -0.6, 0.6)):                       # the broken crown
            k.box(x - 0.45, y - 0.45, 21.0, x + 0.45, y + 0.45, 21.0 + h, D_PLATE, top=D_RUBBLE)
        k.tube((-1.8, 0.0, 13.0), (-7.4, 0.0, 6.2), 0.45, D_DARK, sides=4, r1=0.3)                    # west strut
        k.tube((1.8, 0.0, 13.0), (3.9, 0.0, 10.4), 0.45, D_DARK, sides=4, r1=0.4)                     # east strut, snapped
        k.tube((5.0, 1.8, 1.2), (8.6, 3.4, 0.9), 0.4, D_DARK, sides=4, r1=0.3)                        # ...its fallen end
        for sx, top, lean in ((-1, 15.0, 0.0), (1, 9.0, 0.6)):                                       # needle masts
            x = 7.6 * sx
            k.box(x - 0.8, -0.8, 0.8, x + 0.8, 0.8, 6.4, D_PLATE, top=D_PLATE)
            k.tube((x, 0.0, 6.4), (x + lean * sx, 0.15, top), 0.3, D_PLATE, sides=6, r1=0.1)
            if top > 10:
                k.box(x - 0.15, -0.15, top, x + 0.15, 0.15, top + 0.3, D_LIGHT)                       # red tip light
        k.box(-1.0, -3.1, 0.8, 1.0, -2.85, 3.6, D_DARK)                                             # the gate
        k.box(-1.1, -3.15, 3.9, 1.1, -2.95, 6.1, D_EMBLEM)                                           # the Sith emblem
        for _ in range(10):
            x, y = rng.uniform(-8.5, 8.5), rng.uniform(-6.0, 6.0)
            if abs(x) > 3.4 or abs(y) > 3.6:
                r = rng.uniform(0.5, 1.2)
                k.lathe([(r, 0.75), (r * 0.6, 0.75 + r * 0.5), (0.0, 0.75 + r * 0.7)], [D_RUBBLE, D_RUBBLE], sides=7,
                        cx=x, cy=y, jitter=0.25)

    def dk_dark_temple(k):
        # the Dark Temple in its pass (TOR still "Dark Temple pass"; largely collapsed since 3640 BBY, Legends): a tall
        # pale stone slab tower with a dark vertical recess, flanked by two great curved blade pylons curving inward,
        # on a stepped base, reached by a walled approach whose walls have broken down. Ruin: the east blade's tip gone.
        sq = lambda x, y: [(-x, -y), (x, -y), (x, y), (-x, y)]
        tblock(k, sq(6.2, 4.6), -SKIRT, 1.2, D_STONE, D_STONE)                                  # base
        tblock(k, sq(4.6, 3.4), 1.2, 2.2, D_STONE, D_STONE, poly_top=sq(4.3, 3.1))
        k.box(-1.3, -1.0, 2.2, 1.3, 1.0, 11.6, D_STONE_WORN, top=D_STONE)                              # the slab tower
        k.box(-0.45, -1.06, 2.2, 0.45, -0.98, 10.2, D_DARK)                                          # its recess
        k.box(-1.5, -1.2, 11.6, 1.5, 1.2, 12.2, D_STONE, top=D_STONE)                          # cap
        for sx, segs in ((-1, 4), (1, 3)):                                                          # the curved blades
            pts = [(3.9 * sx, 0.0, 2.2), (4.4 * sx, 0.0, 5.5), (4.2 * sx, 0.0, 8.6), (3.3 * sx, 0.0, 11.0), (2.1 * sx, 0.0, 12.6)]
            for n_ in range(segs):
                r0, r1 = 0.75 - 0.12 * n_, 0.75 - 0.12 * (n_ + 1)
                k.tube(pts[n_], pts[n_ + 1], r0, D_STONE_WORN, sides=4, r1=r1)
        k.box(-0.8, -3.35, 1.2, 0.8, -3.1, 3.2, D_DARK)                                              # door
        for n_ in range(4):                                                                          # stair
            k.box(-1.4, -4.6 - 0.45 * (3 - n_), 0.2 * n_, 1.4, -3.4, 0.2 * (n_ + 1) + 1.0 * (n_ == 3), D_STONE, top=D_STONE)
        for sx in (-1, 1):                                                                           # approach walls
            for n_, h in enumerate((1.4, 0.6, 1.1, 0.3)):
                y0 = -6.2 - 1.6 * n_
                k.box(1.8 * sx - 0.25, y0 - 1.4, -SKIRT, 1.8 * sx + 0.25, y0, h, D_STONE, top=D_RUBBLE)
        tblock(k, [(3.0, -4.6), (6.2, -4.6), (6.2, -1.0), (3.0, -1.0)], 1.2, 1.8, D_RUBBLE, D_RUBBLE)     # caved-in corner

    def kaas_ruin(k, band, rng):
        # Kaas City's towers 3600 years after the Empire fell (TOR "Kaas City" still: dark ribbed towers in setbacks,
        # needle spires, skybridges), ruined. The game lays city meshes on a grid, so nothing here is square or axis-
        # aligned (user: "massive squary cities, not organic"): no podium, towers at random spots and angles, jagged
        # stumps, wall fragments and slabs as turned slabs (lathe, 4 sides, squashed), skybridges as angled spans,
        # irregular rubble mounds; some cells hold only rubble; everything spreads over the whole 2-unit cell and past it,
        # so neighbouring cells blend and the grid's rows disappear. band 1 outskirts .. 4 downtown
        slab = lambda x, y, z0, z1, w, d, a, mat: k.lathe([(w, z0), (w, z1)], [mat], sides=4, cx=x, cy=y, rot=a,
                                                        sy=d / w, cap=D_RUBBLE)
        for _ in range(rng.randint(2, 4)):                                                            # rubble mounds
            x, y, r = rng.uniform(-0.85, 0.85), rng.uniform(-0.85, 0.85), rng.uniform(0.2, 0.5)   # spill into the next cells
            k.lathe([(r, -0.05), (r * 0.6, r * 0.25), (0.0, r * 0.35)], [D_RUBBLE, D_RUBBLE], sides=7, cx=x, cy=y,
                    jitter=0.35, sy=rng.uniform(0.6, 1.0), rot=rng.uniform(0, 6.283))
        n_towers = 0 if (band == 1 and rng.random() < 0.4) else rng.randint(1, 2) + (band >= 3)
        towers = []
        for _ in range(n_towers):
            for _try in range(12):
                x, y, r = rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), rng.uniform(0.1, 0.18)   # anywhere in the cell
                if all(math.hypot(x - a, y - b) > r + c + 0.05 for a, b, c, _h in towers):
                    break
            else:
                continue
            h = rng.uniform(0.35, 0.6) * (0.5 + 0.6 * band)
            towers.append((x, y, r, h))
            broken = rng.random() < 0.75
            top = h * (rng.uniform(0.5, 0.8) if broken else 1.0)
            rot = rng.uniform(0, 6.283)
            prof = [(r, -0.3), (r, top * 0.45), (r * 0.82, top * 0.47), (r * 0.82, top * 0.78), (r * 0.66, top * 0.8), (r * 0.66, top)]
            k.lathe(prof, [D_PLATE_WIN, D_PLATE, D_PLATE_WIN, D_PLATE, D_PLATE_WIN], sides=rng.choice([6, 8]), cx=x, cy=y,
                    rot=rot, cap=D_RUBBLE)                                                           # setback tiers
            if broken:                                                                               # jagged stump
                for _b in range(rng.randint(2, 3)):
                    a = rng.uniform(0, 6.283)
                    w = r * rng.uniform(0.2, 0.35)
                    slab(x + math.cos(a) * r * 0.35, y + math.sin(a) * r * 0.35, top - 0.02, top + rng.uniform(0.05, 0.2),
                         w, w * rng.uniform(0.5, 1.0), rng.uniform(0, 6.283), D_PLATE)
                if rng.random() < 0.6:                                                               # a floor slab out
                    a = rng.uniform(0, 6.283)
                    z = top * rng.uniform(0.6, 0.9)
                    slab(x + math.cos(a) * r * 0.9, y + math.sin(a) * r * 0.9, z, z + 0.025, 0.1, 0.06, a, D_METAL)
            elif band >= 3:                                                                          # an intact needle
                k.lathe([(r * 0.2, top), (0.0, top + 0.35 + 0.1 * band)], [D_METAL], sides=4, cx=x, cy=y)
        if len(towers) >= 2 and rng.random() < 0.6:                                                  # a broken skybridge
            (x0, y0, r0, h0), (x1, y1, r1, h1) = towers[0], towers[1]
            z = min(h0, h1) * 0.35
            k.tube((x0, y0, z), (x0 + (x1 - x0) * 0.55, y0 + (y1 - y0) * 0.55, z - 0.04), 0.035, D_METAL, sides=4)
        for _ in range(rng.randint(1, 3) if band <= 2 else rng.randint(0, 2)):                       # wall fragments
            x, y = rng.uniform(-0.85, 0.85), rng.uniform(-0.85, 0.85)
            slab(x, y, -0.1, rng.uniform(0.06, 0.25), rng.uniform(0.08, 0.2), 0.025, rng.uniform(0, 6.283), D_PLATE_WIN)
        if band >= 2 and rng.random() < 0.4:                                                         # a fallen section
            a = rng.uniform(0, 6.283)
            x, y = rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6)
            k.tube((x, y, 0.1), (x + math.cos(a) * 0.45, y + math.sin(a) * 0.45, 0.06), 0.07, D_PLATE_WIN, sides=6, r1=0.06)

    def zygerria_palace(k):
        # the Royal Palace of Zygerria (TCW "Slaves of the Republic" stills): a massive stepped pyramid of blue slate with
        # battered walls in four tiers, a red band, rows of lit arched windows, a crowned tower on top bristling with
        # upright prongs; a domed hall to its west, a tall slanted-topped obelisk tower and a terracotta tower in front;
        # the grand stair and gate south to the city; north (+y, over the mesa's cliff) the balcony with the hanging cage
        sq = lambda x, y: [(-x, -y), (x, -y), (x, y), (-x, y)]
        tblock(k, sq(8.4, 7.4), -SKIRT, 0.6, Z_SAND, Z_SAND)                                         # the terrace
        tiers = [(7.2, 6.2, 0.6, 4.0, 6.4, 5.5), (5.7, 4.9, 4.4, 7.6, 5.0, 4.2), (4.3, 3.6, 7.6, 10.4, 3.7, 3.0),
                 (3.0, 2.5, 10.4, 12.6, 2.4, 2.0)]                                                   # inset: ledges
        for n_, (x0, y0, z0, z1, x1, y1) in enumerate(tiers):
            tblock(k, sq(x0, y0), z0, z1, Z_SLATE_WIN if n_ % 2 == 0 else Z_SLATE, Z_SLATE, poly_top=sq(x1, y1))
            if n_ == 0:
                tblock(k, sq(6.45, 5.55), 4.0, 4.4, Z_RED, Z_SLATE)                                   # the red band
        k.box(-1.5, -1.2, 12.6, 1.5, 1.2, 15.4, Z_SLATE_WIN, top=Z_SLATE)                            # the crowned tower
        for x, y in ((-1.3, -1.0), (0.0, -1.0), (1.3, -1.0), (-1.3, 1.0), (1.3, 1.0), (0.0, 1.0)):   # its prongs
            k.box(x - 0.18, y - 0.18, 15.4, x + 0.18, y + 0.18, 17.0 + 0.5 * (x == 0.0), Z_SLATE, top=Z_PALE)
        k.box(-10.4, -4.2, 0.6, -7.0, 0.2, 5.4, Z_SAND_WIN, top=Z_SAND)                              # domed west hall
        k.lathe([(1.6, 5.4), (1.55, 6.2), (1.2, 7.3), (0.6, 8.0), (0.0, 8.2)], [Z_BRONZE] * 4, sides=14, cx=-8.7, cy=-2.0)
        k.lathe([(0.9, 0.6), (0.7, 11.0), (0.0, 12.6)], [Z_SAND, Z_PALE], sides=4, cx=-10.0, cy=-6.4, rot=math.pi / 4)  # obelisk
        k.box(7.8, -7.6, 0.6, 9.6, -5.8, 9.2, Z_RED, top=Z_SLATE)                                    # terracotta tower
        for x, y in ((7.8, -7.6), (9.2, -7.6), (7.8, -6.2), (9.2, -6.2)):
            k.box(x + 0.05, y + 0.05, 9.15, x + 0.35, y + 0.35, 9.8, Z_RED, top=Z_RED)
        for n_ in range(6):                                                                          # the grand stair
            k.box(-2.2, -7.4 - 0.5 * (5 - n_), 0.6 + 0.55 * n_, 2.2, -6.2, 0.6 + 0.55 * (n_ + 1), Z_PALE, top=Z_PALE)
        k.box(-1.3, -6.35, 3.9, 1.3, -6.1, 7.0, Z_DARK)                                              # the gate (tier 2)
        for x in (-4.8, 4.8):                                                                        # awnings over the front
            k.box(x - 1.4, -6.6, 2.4, x + 1.4, -6.0, 2.55, Z_AWNING, top=Z_AWNING)
        k.box(-1.6, 5.3, 6.6, 1.6, 7.6, 7.0, Z_PALE, top=Z_PALE)                                     # the balcony (north)
        k.tube((0.0, 7.2, 7.0), (0.0, 8.8, 8.4), 0.12, Z_METAL, sides=5)                            # the gibbet arm
        k.box(-0.04, 8.76, 6.6, 0.04, 8.84, 8.4, Z_METAL)                                           # the chain
        k.lathe([(0.45, 5.6), (0.45, 6.5), (0.0, 6.7)], [Z_METAL, Z_METAL], sides=8, cx=0.0, cy=8.8)   # the cage

    def zyg_arena(k):
        # the Royal Slave Auction's courtyard (TCW "Slaves of the Republic"): an open square of sand walled in by high
        # slate walls with lit galleries, crenellated corner towers, the raised stepped stage in the middle, the
        # queen's balcony under a red canopy on the north wall (+y)
        sq = lambda x, y: [(-x, -y), (x, -y), (x, y), (-x, y)]
        k.box(-4.45, -4.45, -SKIRT, 4.45, 4.45, 0.4, Z_SAND, top=Z_SAND)                             # the sand floor, inset
        for x0, y0, x1, y1 in ((-4.6, -4.6, 4.6, -3.8), (-4.6, 3.8, 4.6, 4.6), (-4.6, -3.8, -3.8, 3.8), (3.8, -3.8, 4.6, 3.8)):
            k.box(x0, y0, -0.3, x1, y1, 2.6, Z_SLATE_WIN, top=Z_SLATE)                              # walls, galleries
        for x in (-4.6, 3.6):                                                                        # corner towers
            for y in (-4.6, 3.6):
                k.box(x - 0.15, y - 0.15, -0.3, x + 1.15, y + 1.15, 3.6, Z_SLATE, top=Z_SLATE)   # proud of the walls
                for cx, cy in ((x, y), (x + 0.75, y), (x, y + 0.75), (x + 0.75, y + 0.75)):
                    k.box(cx - 0.05, cy - 0.05, 3.55, cx + 0.2, cy + 0.2, 3.95, Z_SLATE, top=Z_PALE)
        for n_ in range(3):                                                                          # the stepped stage
            w = 1.6 - 0.45 * n_
            tblock(k, sq(w, w), 0.3 + 0.3 * n_, 0.7 + 0.3 * n_, Z_PALE, Z_PALE)
        k.box(-1.6, 3.2, 1.4, 1.6, 3.8, 1.6, Z_PALE, top=Z_PALE)                                     # the queen's balcony
        k.box(-1.6, 3.2, 2.4, 1.6, 3.8, 2.55, Z_RED, top=Z_RED)                                      # its canopy
        for x in (-1.5, 1.5):
            k.box(x - 0.08, 3.25, 1.6, x + 0.08, 3.4, 2.4, Z_BRONZE, top=Z_BRONZE)
        k.box(-0.9, -4.75, -0.3, 0.9, -4.55, 1.8, Z_DARK)                                            # the south gate
        for x in (-2.6, 2.6):                                                                        # awnings on the walls
            k.box(x - 1.0, -3.85, 1.2, x + 1.0, -3.3, 1.3, Z_AWNING, top=Z_AWNING)

    def zyg_fortress(k):
        # a mesa-top fortress (canon: fortresses built on the mesas with slave labour; shape: the palace's language):
        # battered curtain walls, corner towers with teal tent roofs, a slate keep crowned with prongs, the gate south
        sq = lambda x, y: [(-x, -y), (x, -y), (x, y), (-x, y)]
        tblock(k, sq(3.6, 3.6), -SKIRT, 1.9, Z_SAND, Z_SAND, poly_top=sq(3.3, 3.3))                    # curtain wall
        tblock(k, sq(2.9, 2.9), 1.9, 2.0, Z_SAND, Z_SAND)                                            # inner court
        for x in (-3.6, 2.6):
            for y in (-3.6, 2.6):
                k.box(x - 0.15, y - 0.15, -0.3, x + 1.15, y + 1.15, 3.0, Z_SAND_WIN, top=Z_SAND)
                k.lathe([(0.75, 3.0), (0.0, 3.9)], [Z_ROOF], sides=4, cx=x + 0.5, cy=y + 0.5, rot=math.pi / 4)
        tblock(k, sq(1.6, 1.4), 2.0, 4.6, Z_SLATE_WIN, Z_SLATE, poly_top=sq(1.3, 1.1))               # the keep
        for x in (-0.9, 0.0, 0.9):
            k.box(x - 0.15, -0.15, 4.6, x + 0.15, 0.15, 5.5 + 0.4 * (x == 0.0), Z_SLATE, top=Z_PALE)
        k.box(-0.7, -3.75, 0.0, 0.7, -3.5, 1.5, Z_DARK)                                              # the gate
        k.box(-1.2, -3.9, 1.6, 1.2, -3.55, 1.7, Z_RED, top=Z_RED)                                    # red band over it

    def zyg_landing(k):
        # the slavers' landing field (Zygerrian capital landing platform, comics): metal decks on arched sandstone piers,
        # a cargo crane, a control tower under a tent roof, cargo crates; ships are not part of the model
        for x0, x1 in ((-5.0, -0.6), (0.6, 5.0)):
            k.box(x0, -2.4, 1.2, x1, 2.4, 1.45, Z_METAL, top=Z_METAL)                                # the decks
            for x in (x0 + 0.5, (x0 + x1) / 2, x1 - 0.5):                                            # piers
                k.box(x - 0.35, -2.0, -SKIRT, x + 0.35, 2.0, 1.2, Z_SAND, top=Z_SAND)
        k.box(-0.6, -0.8, -SKIRT, 0.6, 0.8, 3.6, Z_SAND_WIN, top=Z_SAND)                             # control tower
        k.lathe([(0.95, 3.6), (0.0, 4.5)], [Z_ROOF], sides=4, rot=math.pi / 4)
        k.box(-0.65, -0.85, 2.8, 0.65, 0.85, 3.0, Z_AWNING, top=Z_AWNING)
        k.box(4.15, 1.85, 1.45, 4.45, 2.15, 4.3, Z_METAL, top=Z_METAL)                               # the crane's mast
        k.tube((4.3, 2.0, 4.1), (2.2, 0.6, 4.4), 0.08, Z_METAL, sides=5)
        k.box(2.17, 0.57, 2.6, 2.23, 0.63, 4.4, Z_DARK)                                             # its cable
        for x, y in ((-4.2, 1.6), (-3.6, 1.6), (-4.2, 1.0), (3.4, -1.6), (2.8, -1.7)):              # crates
            k.box(x - 0.25, y - 0.25, 1.45, x + 0.25, y + 0.25, 1.9, Z_RED, top=Z_RED)

    def zyg_city(k, band, rng):
        # the Zygerrian capital (TCW stills): crenellated sandstone and terracotta blocks, peaked teal tent roofs,
        # striped awnings, towers and bronze domes downtown. band 1 outskirts .. 4 downtown
        sq = lambda x, y, w, d: (x - w, y - d, x + w, y + d)
        for _ in range(rng.randint(2, 3)):
            x, y = rng.uniform(-0.45, 0.45), rng.uniform(-0.45, 0.45)
            w, d = rng.uniform(0.14, 0.22), rng.uniform(0.14, 0.22)
            h = rng.uniform(0.18, 0.3) + 0.12 * band
            mat = rng.choice([Z_SAND_WIN, Z_SAND_WIN, Z_RED])
            x0, y0, x1, y1 = sq(x, y, w, d)
            k.box(x0, y0, -0.3, x1, y1, h, mat, top=Z_SAND)
            if rng.random() < 0.55:                                                                   # a peaked tent roof
                k.lathe([(max(w, d) * 1.25, h), (0.0, h + 0.18 + 0.05 * band)], [Z_ROOF], sides=4, cx=x, cy=y, rot=math.pi / 4)
            else:                                                                                     # crenellations
                for cx_, cy_ in ((x0, y0), (x1 - 0.05, y0), (x0, y1 - 0.05), (x1 - 0.05, y1 - 0.05)):
                    k.box(cx_ + 0.01, cy_ + 0.01, h - 0.02, cx_ + 0.05, cy_ + 0.05, h + 0.06, mat, top=mat)
            if rng.random() < 0.5:                                                                    # an awning
                k.box(x0, y0 - 0.06, h * 0.35, x1, y0, h * 0.35 + 0.03, Z_AWNING, top=Z_AWNING)
        if band >= 2 and rng.random() < 0.45 + 0.15 * band:                                          # a tower
            x, y = rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4)
            h = 0.6 + 0.25 * band
            k.box(x - 0.08, y - 0.08, -0.3, x + 0.08, y + 0.08, h, rng.choice([Z_RED, Z_SAND_WIN]), top=Z_SAND)
            k.lathe([(0.11, h), (0.0, h + 0.22)], [Z_ROOF if rng.random() < 0.5 else Z_PALE], sides=4, cx=x, cy=y, rot=math.pi / 4)
        if band >= 3 and rng.random() < 0.5:                                                         # a bronze dome
            x, y, r = rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(0.16, 0.24)
            k.box(x - r, y - r, -0.3, x + r, y + r, 0.35 + 0.1 * band, Z_SAND_WIN, top=Z_SAND)
            k.lathe([(r * 0.95, 0.35 + 0.1 * band), (r * 0.7, 0.5 + 0.1 * band), (0.0, 0.6 + 0.1 * band)], [Z_BRONZE, Z_BRONZE],
                    sides=10, cx=x, cy=y)

    def cslab(k, x, y, z0, z1, w, d, a, mat, top, wt=None, dt=None):
        """a turned box: half sizes w, d at z0 (wt, dt at z1: a frustum, e.g. a hip roof), turned by a; each wall
        gets the whole atlas cell, `top` closes it, the bottom stays open (sunk into the ground)"""
        ca, sa = math.cos(a), math.sin(a)
        ring = lambda hw, hd, z: [k.bm.verts.new((x + ca * px - sa * py, y + sa * px + ca * py, z))
                                  for px, py in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))]
        lo, hi = ring(w, d, z0), ring(w if wt is None else wt, d if dt is None else dt, z1)
        for i in range(4):
            j = (i + 1) % 4
            k.put(k.bm.faces.new((lo[i], lo[j], hi[j], hi[i])), ((0, 0), (1, 0), (1, 1), (0, 1)), mat)
        k.put(k.bm.faces.new(hi), ((0, 0), (1, 0), (1, 1), (0, 1)), top)

    def canto_drum(k, x, y, z0, h, r, saucers=1, mast=False, sides=12):
        """a Canto Bight drum: a pale stone cylinder with its lit window band under wide shallow slate saucer roofs
        (TLJ casino: two or three stacked, each smaller, the lit band under every lip)"""
        k.lathe([(r, z0), (r, z0 + h)], [C_STONE_WIN], sides=sides, cx=x, cy=y, cap=C_ROOF)
        z, rr = z0 + h, r
        for n_ in range(saucers):
            w = rr * (1.5 - 0.1 * n_)
            k.lathe([(rr * 0.98, z - 0.02), (w, z + 0.03 * w), (w * 0.97, z + 0.08 * w), (rr * 0.55, z + 0.3 * w),
                     (0.0, z + 0.36 * w)], [C_SLATE_LIT, C_SLATE, C_SLATE, C_SLATE], sides=sides * 2, cx=x, cy=y)
            if n_ + 1 < saucers:                                         # the next drum stands on the roof
                rr *= 0.62
                k.lathe([(rr, z + 0.2 * w), (rr, z + 0.2 * w + 0.6 * h)], [C_STONE_WIN], sides=sides, cx=x, cy=y)
                z += 0.2 * w + 0.6 * h
        if mast:
            k.lathe([(0.03 * r / 0.2, z + 0.3 * rr), (0.0, z + 0.3 * rr + 0.9 * r)], [C_RAIL], sides=4, cx=x, cy=y)

    def canto_city(k, band, rng):
        # Canto Bight (the user's Star Wars Outlaws reference: the city seen from the sea; TLJ stills): pale stone and
        # plaster houses under low slate hip roofs or flat roofs, packed tight, round drum buildings with wide shallow
        # slate saucer roofs and a warm window band between them; downtown (the casino district) taller stone blocks
        # and drums with stacked saucers. Nothing square or axis-aligned (the game lays these on a 2-unit grid):
        # turned houses at random spots over the whole cell and past it. band 1 outskirts .. 4 downtown
        placed = []

        def spot(r, lim=0.85):
            for _ in range(20):
                x, y = rng.uniform(-lim, lim), rng.uniform(-lim, lim)
                if all(math.hypot(x - a, y - b) > r + c for a, b, c in placed):
                    placed.append((x, y, r))
                    return x, y
            return None
        for _ in range(rng.randint(2, 3) + (band >= 3)):                                              # drums
            r = rng.uniform(0.12, 0.2) * (1 + 0.12 * band)
            p_ = spot(r * 1.45)
            if p_:
                tall = band >= 3 and rng.random() < 0.5
                canto_drum(k, *p_, -0.3, rng.uniform(0.32, 0.45) + 0.12 * band + 0.3 * tall, r,
                           saucers=1 + tall + (band == 4 and rng.random() < 0.3), mast=tall and rng.random() < 0.4)
        for _ in range(4 + 2 * band):                                                                 # houses
            w, d = rng.uniform(0.08, 0.15), rng.uniform(0.06, 0.12)
            p_ = spot(max(w, d) * 1.2)
            if not p_:
                continue
            a = rng.uniform(0, math.pi)
            h = rng.uniform(0.14, 0.26) + 0.08 * band + (0.35 * rng.random() if band >= 3 else 0.0)
            wall = C_STONE_WIN if band >= 3 and rng.random() < 0.5 else C_PLASTER_WIN
            if rng.random() < 0.6:                                                                    # a low hip roof
                cslab(k, *p_, -0.3, h, w, d, a, wall, C_ROOF)
                cslab(k, *p_, h - 0.005, h + 0.1, w * 1.12, d * 1.12, a, C_SLATE, C_SLATE, wt=w * 0.55, dt=d * 0.12)
            else:                                                                                     # a flat roof
                cslab(k, *p_, -0.3, h, w, d, a, wall, C_ROOF)
                if rng.random() < 0.4:                                                                # a small roof dome
                    k.lathe([(min(w, d) * 0.7, h - 0.01), (min(w, d) * 0.45, h + 0.07), (0.0, h + 0.1)], [C_SLATE, C_SLATE],
                            sides=10, cx=p_[0], cy=p_[1])
        if band >= 3 and rng.random() < 0.6:                                                          # a lit plaza lamp
            p_ = spot(0.05)
            if p_:
                k.lathe([(0.025, -0.1), (0.025, 0.3)], [C_RAIL], sides=4, cx=p_[0], cy=p_[1])
                k.lathe([(0.05, 0.3), (0.05, 0.36)], [C_GLOW], sides=6, cx=p_[0], cy=p_[1], cap=C_GLOW)

    def sith_ruin(k, band, rng):
        # ancient Sith ruins half-buried in Cantonica's sand (the user, 2026-10-14: "the ruins are ancient Sith ruins";
        # the shapes follow the Sith architecture of Korriban / Dromund Kaas: tapering pylons, trapezoid gateways,
        # colonnades of square pillars, glyph-carved walls, stepped ziggurat stumps), all broken and drifted over;
        # spread over the whole cell and past it, turned at random. band 1 outskirts .. 4 the heart of the necropolis
        for _ in range(rng.randint(3, 4)):                                                            # sand drifts
            x, y, r = rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(0.25, 0.5)
            k.lathe([(r, -0.05), (r * 0.6, r * 0.2), (0.0, r * 0.3)], [C_SAND, C_SAND], sides=7, cx=x, cy=y,
                    jitter=0.3, sy=rng.uniform(0.5, 0.9), rot=rng.uniform(0, 6.283))
        for _ in range(rng.randint(1, 2) + (band >= 3)):                                              # pylons
            x, y, a = rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(0, math.pi)
            w, h = rng.uniform(0.07, 0.12), rng.uniform(0.3, 0.55) * (0.6 + 0.3 * band)
            top = h * (rng.uniform(0.45, 0.8) if rng.random() < 0.6 else 1.0)
            f = 1 - 0.4 * top / h                                                                     # tapering
            cslab(k, x, y, -0.3, top, w, w * 0.7, a, C_SITH_GLYPH, C_SITH_DARK, wt=w * f, dt=w * 0.7 * f)
        if rng.random() < 0.5 + 0.1 * band:                                                           # a gateway
            x, y, a = rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), rng.uniform(0, math.pi)
            h, half = rng.uniform(0.3, 0.45) + 0.08 * band, rng.uniform(0.14, 0.2)
            ca, sa = math.cos(a), math.sin(a)
            for sx in (-1, 1):
                k.lathe([(0.1, -0.3), (0.065, h)], [C_SITH], sides=4, cx=x + sx * half * ca, cy=y + sx * half * sa,
                        rot=a + math.pi / 4, cap=C_SITH_DARK)
            if rng.random() < 0.6:                                                                    # its lintel
                cslab(k, x, y, h - 0.02, h + 0.06, half + 0.08, 0.06, a, C_SITH_GLYPH, C_SITH_DARK)
            else:                                                                                     # ...fallen
                k.tube((x + 0.2 * sa, y - 0.2 * ca, 0.05), (x + 0.2 * sa + 0.3 * ca, y - 0.2 * ca + 0.3 * sa, 0.08),
                       0.05, C_SITH, sides=4)
        for _ in range(rng.randint(0, 2) + (band <= 2)):                                              # colonnade stumps
            x, y, a = rng.uniform(-0.95, 0.95), rng.uniform(-0.95, 0.95), rng.uniform(0, math.pi)
            for i in range(rng.randint(3, 5)):
                px, py = x + math.cos(a) * 0.14 * i, y + math.sin(a) * 0.14 * i
                k.lathe([(0.04, -0.2), (0.035, rng.uniform(0.05, 0.35))], [C_SITH], sides=4, cx=px, cy=py,
                        rot=a + math.pi / 4, cap=C_SITH_DARK)
        for _ in range(rng.randint(1, 2)):                                                            # wall fragments
            x, y = rng.uniform(-1.05, 1.05), rng.uniform(-1.05, 1.05)
            cslab(k, x, y, -0.2, rng.uniform(0.08, 0.22), rng.uniform(0.1, 0.22), 0.025, rng.uniform(0, math.pi),
                  C_SITH_GLYPH, C_SITH_DARK)
        if band >= 3 and rng.random() < 0.6:                                                          # a ziggurat stump
            x, y, a = rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7), rng.uniform(0, math.pi)
            r = rng.uniform(0.25, 0.35)
            for n_ in range(3):
                rr = r * (1 - 0.25 * n_)
                k.lathe([(rr * 1.41, -0.3 if n_ == 0 else 0.12 * n_ - 0.01), (rr * 1.3, 0.12 * (n_ + 1))],
                        [C_SITH if n_ % 2 else C_SITH_GLYPH], sides=4, cx=x, cy=y, rot=a + math.pi / 4, cap=C_SITH_DARK)
        if rng.random() < 0.4:                                                                        # a toppled obelisk
            x, y, a = rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9), rng.uniform(0, 6.283)
            k.tube((x, y, 0.04), (x + math.cos(a) * 0.5, y + math.sin(a) * 0.5, 0.1), 0.07, C_SITH, sides=4, r1=0.04)

    def westhill(k):
        # Westhill Palace on the Westhill cliffs (Star Wars Outlaws still "Westhill cliffs": domed mansions along a
        # cliff top over the sea, a round landing pad with a red light; the user's TLJ still for the building: a
        # round drum of pale stone with pilasters, a lit window band, a ring balcony with railings, a slate dome with a
        # lip, flanking pale blocks behind, a slate-domed round pavilion beside it). Front (-y) faces the sea.
        k.lathe([(4.6, -SKIRT), (4.6, 0.4)], [C_STONE], sides=11, cy=0.4, sy=0.85, jitter=0.06, cap=C_ROOF)   # cliff-top
        k.lathe([(2.5, -SKIRT), (2.5, 0.3)], [C_STONE], sides=14, cy=-4.4, cap=C_STONE)                # lower terrace
        k.lathe([(1.9, 0.29), (1.9, 0.38)], [C_STONE], sides=24, cy=-4.9, cap=C_PAD)                  # the landing pad
        for x in (-1.0, 1.0):                                                                        # its red lights
            k.lathe([(0.12, 0.38), (0.12, 0.5)], [C_GLOW], sides=6, cx=x, cy=-6.75, cap=C_GLOW)
        k.box(-0.5, -3.0, 0.3, 0.5, -1.9, 0.47, C_STONE, top=C_STONE)                               # the stair down to it
        cx, cy = 0.0, 0.6                                                                           # the main mansion
        k.lathe([(2.3, 0.35), (2.3, 2.1)], [C_STONE_WIN], sides=24, cx=cx, cy=cy)
        for i in range(12):                                                                          # pilasters
            a = 2 * math.pi * i / 12
            cslab(k, cx + 2.36 * math.cos(a), cy + 2.36 * math.sin(a), 0.35, 2.2, 0.16, 0.09, a + math.pi / 2, C_STONE,
                  C_STONE)
        k.lathe([(3.1, 2.1), (3.1, 2.24)], [C_STONE], sides=24, cx=cx, cy=cy, cap=C_ROOF)          # ring balcony
        k.lathe([(3.05, 2.24), (3.05, 2.5)], [C_RAIL], sides=24, cx=cx, cy=cy)                     # its railing
        k.lathe([(1.85, 2.2), (1.85, 3.35)], [C_STONE_WIN], sides=20, cx=cx, cy=cy)                 # upper drum
        for i in range(8):
            a = 2 * math.pi * (i + 0.5) / 8
            cslab(k, cx + 1.9 * math.cos(a), cy + 1.9 * math.sin(a), 2.2, 3.4, 0.14, 0.08, a + math.pi / 2, C_STONE, C_STONE)
        k.lathe([(1.83, 3.33), (2.15, 3.42), (2.1, 3.56), (1.6, 4.0), (0.9, 4.32), (0.0, 4.45)],
                [C_SLATE_LIT, C_SLATE, C_SLATE, C_SLATE, C_SLATE], sides=24, cx=cx, cy=cy)            # the dome
        for sx in (-1, 1):                                                                           # pale blocks behind
            k.box(sx * 1.2 - 0.9, 2.2, 0.35, sx * 1.2 + 0.9, 3.6, 3.7, C_STONE, top=C_ROOF)
            k.box(sx * 1.2 - 0.6, 2.15, 1.0, sx * 1.2 + 0.6, 2.21, 3.0, C_PLASTER_WIN)
        canto_drum(k, 3.2, -1.7, 0.35, 0.8, 0.85, sides=14)                                           # the pavilion
        k.lathe([(1.05, 0.33), (1.05, 0.5)], [C_STONE], sides=16, cx=3.2, cy=-1.7, cap=C_ROOF)       # its round terrace
        canto_drum(k, -3.1, 1.2, 0.35, 1.3, 1.1, saucers=2, sides=14)                                 # a second mansion
        canto_drum(k, -2.4, -2.2, 0.35, 0.7, 0.65, sides=12)                                          # a garden house
        for x, y, r in ((1.4, -2.6, 0.9), (-0.9, -2.9, 0.7), (3.4, 1.6, 0.8)):                       # gardens
            k.lathe([(r, 0.38), (r, 0.46)], [C_GARDEN], sides=9, cx=x, cy=y, jitter=0.15, cap=C_GARDEN)
        for x, y in ((-1.6, -3.4), (1.6, -3.4), (2.6, -3.0), (-2.9, -3.0)):                          # lamp posts
            k.lathe([(0.05, 0.4), (0.05, 1.1)], [C_RAIL], sides=4, cx=x, cy=y)
            k.lathe([(0.12, 1.1), (0.12, 1.25)], [C_GLOW], sides=6, cx=x, cy=y, cap=C_GLOW)

    for name, fn in (("hod_kad_facility", kadavo_facility), ("hod_kad_tower", kadavo_tower), ("hod_kad_dock", kadavo_dock),
                     ("hod_kad_mine", kadavo_mine), ("hod_kad_camp", kadavo_camp)):
        build(name, fn)
    for v in "abcd":
        build(f"hod_kad_crater_{v}", lambda k, v=v: kadavo_crater(k, v), tex="hod_kadavo")
    build("hod_zyg_palace", zygerria_palace, tex="hod_zygerria")
    for name_, fn_, rot_ in (("hod_zyg_arena", zyg_arena, 0.0), ("hod_zyg_fortress", zyg_fortress, math.pi / 4),   # fortresses
                             ("hod_zyg_landing", zyg_landing, 0.0)):                                            # face SE
        build(name_, fn_, tex="hod_zygerria", rot=rot_)
    for band in range(1, 5):
        for v in range(1, 5):
            rng_z = random.Random(f"hod_zyg_city{band}{v}")
            build(f"hod_zyg_city_{band}{v}", lambda k, band=band, rng=rng_z: zyg_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_zygerria")
    build("hod_dk_citadel", dk_citadel, tex="hod_dromund", rot=-math.pi / 2)          # faces west, back to the sea
    build("hod_dk_dark_temple", dk_dark_temple, tex="hod_dromund", rot=math.pi / 4)   # faces south-east, down the pass
    for band in range(1, 5):
        for v in range(1, 5):
            rng_k = random.Random(f"hod_kaas_ruin{band}{v}")
            build(f"hod_kaas_ruin_{band}{v}", lambda k, band=band, rng=rng_k: kaas_ruin(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_dromund")
    build("hod_cant_westhill", westhill, tex="hod_cantonica", rot=-math.pi / 4)   # faces south-west, out to sea
    for band in range(1, 5):
        for v in range(1, 5):
            rng_c = random.Random(f"hod_cant_city{band}{v}")
            build(f"hod_cant_city_{band}{v}", lambda k, band=band, rng=rng_c: canto_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_cantonica")
            rng_s = random.Random(f"hod_cant_sith_ruin{band}{v}")
            build(f"hod_cant_sith_ruin_{band}{v}", lambda k, band=band, rng=rng_s: sith_ruin(k, band, rng),
                  shader="PdxMeshSnow", tex="hod_cantonica")
    build("hod_flo_complex", florrum_complex)
    build("hod_flo_refinery", florrum_refinery)
    for v in "ab":
        build(f"hod_flo_outpost_{v}", lambda k, v=v: florrum_outpost(k, v))
    for i_ in range(KOR_TURNS):                                            # faces out of its rock: turned copies
        build(f"hod_flo_vault_r{i_}", florrum_vault, rot=2 * math.pi * i_ / KOR_TURNS)
    for name, fn in (("hod_kor_head", korriban_head), ("hod_kor_obelisks", korriban_obelisks),
                     ("hod_kor_ziggurat", korriban_ziggurat), ("hod_kor_banner", korriban_banner)):
        build(name, fn, tex="hod_korriban")

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
        # whole lines only: vanilla has some of these commented out, and eating just the event left its "#" to comment
        # out the brace on the next line (every entity after building_nuclear_reactor_spawn broke)
        block = re.sub(r'(?m)^[ \t]*#?[ \t]*event = \{[^{}\n]*node\s*=\s*"factorysmoke2?"[^{}\n]*\}[ \t]*\n', "", block)
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
})
CITY_TERRAIN, PLAZA_TERRAIN = [13], 25   # terrain.bmp: spawn_city urban -> urban_plaza_25 (same texture, no cities)
NO_SPAWN = {13: 25, 26: 5, 29: 28, 30: 9, 32: 7}  # every spawn_city texture -> the same look without city models (place_planet)
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

KOR_MARK = ("# HOD: Korriban (military_buildings.py korriban_place)", "# HOD: end of Korriban")
KOR_TURNS = 8          # turned copies of the Korriban models (their front is -y: south on the map, unturned)
KOR_TOMB_MODEL = {"Tomb of Marka Ragnos": "hod_kor_ragnos"}
KOR_TOMB_BACK = 1.5    # px a tomb sits back from its niche's middle, against the rock
KOR_STATUE_STEP = 7.0  # px between the statues lining the valley walls
KOR_AVENUE = (9.0, 4.0)  # obelisks in pairs down the valley (Valley of Tombs map): px apart along, across
KOR_RUINS = (12, 6.0, 3.0)  # ruins on the valley floor: how many, px from other models, px from unit positions
KOR_SCALE = {"tomb": 0.9, "hod_kor_academy": 1.0, "hod_kor_twins": 0.7}


def korriban_place():
    """map/ambient_object.txt for korriban_map.py's layout: a tomb model in each tomb niche facing the valley, hooded
    statues lining the valley walls, an avenue of obelisks down it, the twin-statue gate between the valley and
    Dreshdae, the ruined academy at the valley's head facing down it (y = 0: stood on the ground). HOI4 ignores the
    objects' rotation, so each facing model is one of its KOR_TURNS turned copies. Entities in
    gfx/entities/hod_korriban.{gfx,asset}. Run after korriban_map.py, free_province_ids.py and
    planet_terrain_gen.py --korriban."""
    import json
    import random
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    z = json.load(open("WIPGFX/Assets/korriban_zones.json"))
    zone = np.asarray(Image.open("WIPGFX/Assets/korriban_zones.png"))
    H = zone.shape[0]
    rng = random.Random("korriban")
    prov = z["provinces"]
    valley = zone == 2
    _, (vy, vx) = ndi.distance_transform_edt(~valley, return_indices=True)
    to_mtn = ndi.distance_transform_edt(zone != 4)
    to_space = ndi.distance_transform_edt(zone > 0)
    objs = {}

    def put(mesh, r, c, scale=1.0):
        objs.setdefault((mesh, round(scale, 2)), []).append((c, H - 1 - r, 0.0))

    def facing(mesh, r, c, r1, c1, scale=1.0):        # the turned copy whose front looks from (r, c) toward (r1, c1)
        turn = math.atan2(-(r1 - r), c1 - c) + math.pi / 2               # map rows grow south; unturned front: south
        put(f"{mesh}_r{round(turn / (2 * math.pi / KOR_TURNS)) % KOR_TURNS}", r, c, scale)
    centre = lambda feat: np.mean([v["centre"] for v in prov.values() if v["feature"] == feat], 0)
    # tombs: against the back of each niche, facing out onto the valley floor
    plain = ["hod_kor_tomb_a", "hod_kor_tomb_b", "hod_kor_tomb_c", "hod_kor_tomb_d"]
    tombs = sorted({v["feature"] for v in prov.values() if v["zone"] == "tomb"})       # one per tomb, not per province
    for i, name in enumerate(tombs):
        r, c = centre(name)
        ri, ci = int(round(r)), int(round(c))
        dr, dc = vy[ri, ci] - r, vx[ri, ci] - c
        n_ = math.hypot(dr, dc) or 1
        r, c = r - dr / n_ * KOR_TOMB_BACK, c - dc / n_ * KOR_TOMB_BACK
        facing(KOR_TOMB_MODEL.get(name, plain[i % 4]), r, c, r + dr, c + dc, KOR_SCALE["tomb"])
    # hooded statues along the valley walls, facing into the valley (not in front of the tombs)
    gy, gx = np.gradient(ndi.gaussian_filter(to_mtn, 1.0))
    near_tomb = ndi.distance_transform_edt(zone != 1) < 3
    edge = np.argwhere(valley & (to_mtn <= 1.5) & (to_space > 2) & ~near_tomb)
    taken = []
    for k in sorted(range(len(edge)), key=lambda _: rng.random()):
        r, c = edge[k]
        if all((r - a) ** 2 + (c - b) ** 2 >= KOR_STATUE_STEP ** 2 for a, b in taken):
            taken.append((r, c))
            facing("hod_kor_statue", r, c, r + gy[r, c], c + gx[r, c], rng.uniform(0.85, 1.05))
    # the avenue: obelisk pairs either side of the valley floor's long axis
    vf = np.argwhere(valley & (to_mtn > 2))
    cen = vf.mean(0)
    ax = np.linalg.svd(vf - cen, full_matrices=False)[2][0]
    t = (vf - cen) @ ax
    for d in np.arange(t.min() + KOR_AVENUE[0], t.max() - KOR_AVENUE[0] / 2, KOR_AVENUE[0]):
        r, c = cen + ax * d
        for side in (-1, 1):
            orr, oc = r + side * ax[1] * KOR_AVENUE[1], c - side * ax[0] * KOR_AVENUE[1]
            if valley[int(round(orr)), int(round(oc))] and to_mtn[int(round(orr)), int(round(oc))] > 2:
                put("hod_kor_obelisks", orr, oc, 0.7)
    # ruins here and there on the valley floor: clear of the walls, the avenue and the provinces' unit positions
    taken = [(r, c) for (m_, _s), pts in objs.items() for c, zz, _y in pts for r in [H - 1 - zz]]
    units = [v["centre"] for v in prov.values()]
    spots = np.argwhere(valley & (to_mtn > 4))
    n_ruin = 0
    for k in sorted(range(len(spots)), key=lambda _: rng.random()):
        r, c = spots[k]
        if all(math.hypot(r - a, c - b) >= KOR_RUINS[1] for a, b in taken) and \
                all(math.hypot(r - a, c - b) >= KOR_RUINS[2] for a, b in units):
            taken.append((r, c))
            put(f"hod_kor_ruin_{'abcd'[n_ruin % 4]}", r, c, rng.uniform(0.7, 0.9))
            n_ruin += 1
            if n_ruin == KOR_RUINS[0]:
                break
    # the gate: the twin statues where Dreshdae opens onto the valley, looking out toward Dreshdae
    town, vc = centre("Dreshdae"), centre("Valley of the Dark Lords")
    town_px = np.argwhere(zone == 7)
    gate = town_px[np.argmin(np.hypot(*(town_px - vc).T))]               # Dreshdae's edge nearest the valley
    gr, gc = gate + (vc - gate) / (np.hypot(*(vc - gate)) or 1) * 3
    facing("hod_kor_twins", gr, gc, *town, KOR_SCALE["hod_kor_twins"])
    # the ruined academy in the middle of its grounds, facing down the valley
    ac = centre("Sith Academy")
    facing("hod_kor_academy", ac[0], ac[1], *vc, KOR_SCALE["hod_kor_academy"])
    meshes = sorted({m for m, _ in objs})
    open("gfx/entities/hod_korriban.gfx", "w", encoding="utf-8", newline="\n").write(
        "objectTypes = {\n\t# HOD: Korriban (military_buildings.py korriban_place)\n"
        + "".join(f'\tpdxmesh = {{\n\t\tname = "{m}_mesh"\n\t\tfile = "{LM_OUT}/{m}.mesh"\n\t}}\n' for m in meshes) + "}\n")
    open("gfx/entities/hod_korriban.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: Korriban (military_buildings.py korriban_place)\n"
        + "".join(f'entity = {{\n\tname = "{m}_entity"\n\tpdxmesh = "{m}_mesh"\n\tscale = 1\n}}\n' for m in meshes))
    block_ = KOR_MARK[0] + "\n"
    for (mesh, scale), pts in sorted(objs.items()):
        block_ += f'type={{\n\ttype="{mesh}_entity"\n\tuse_animation=no\n\tscale={scale:.6f}\n'
        block_ += "".join(f'\tobject={{\n\t\tname="{mesh}_{int(scale * 100)}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} 0.000 {zz:.3f} \n'
                          f'\t\t}}\n\t\trotation={{\n\t\t\t0.000 {yaw:.3f} 0.000 \n\t\t}}\n\t}}\n' for i, (x, zz, yaw) in enumerate(pts))
        block_ += "}\n"
    block_ += KOR_MARK[1] + "\n"

    def fix(s):
        s = re.sub(re.escape(KOR_MARK[0]) + r".*?" + re.escape(KOR_MARK[1]) + r"\n", "", s, flags=re.S)
        s = re.sub(r'type=\{\s*type="hod_korriban_valley_entity".*?\n\}\n', "", s, flags=re.S)   # the old landmark
        return s.rstrip("\n") + "\n" + block_
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from felucia_tribes import rw
    rw("map/ambient_object.txt", fix)
    count = {}
    for (mesh, _s), pts in objs.items():
        count[mesh] = count.get(mesh, 0) + len(pts)
    print("Korriban:", count)

FLO_MARK = ("# HOD: Florrum (military_buildings.py florrum_place)", "# HOD: end of Florrum")
FLO_SCALE = {"hod_flo_complex": 0.85, "hod_flo_refinery": 0.8, "hod_flo_outpost": 0.75, "hod_flo_vault": 0.7}
FLO_OFF = 2.5           # px a base stands off its province's unit position
FLO_SCATTER = (5, 6.0)  # extra outposts on the plains: how many, px apart from everything else


def florrum_place():
    """map/ambient_object.txt for florrum_map.py's layout (y = 0: stood on the ground): Hondo's complex in its enclave,
    the vault door in the eastern shelf facing out, the junk market's wrecks and crates (Raxus Prime models), a
    mercenary outpost at each Commerce Guild victory point, the sulfur refinery on the acid flats, a few outposts
    scattered on the plains; all off the provinces' unit positions. Entities in gfx/entities/hod_florrum.{gfx,asset}
    (the wrecks and crates are already defined by Raxus Prime). Run after florrum_map.py and --florrum."""
    import json
    import random
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    z = json.load(open("WIPGFX/Assets/florrum_zones.json"))
    zone = np.asarray(Image.open("WIPGFX/Assets/florrum_zones.png"))
    H = zone.shape[0]
    rng = random.Random("florrum")
    prov = z["provinces"]
    units = [v["centre"] for v in prov.values()]
    vp_at = {n: prov[p]["centre"] for p, n in z["vp_names"].items()}
    open_ = np.isin(zone, (1, 2, 3, 5, 6))
    to_shelf = ndi.distance_transform_edt(zone != 4)
    to_space = ndi.distance_transform_edt(zone > 0)
    objs, taken = {}, []

    def put(mesh, r, c, scale=1.0):
        objs.setdefault((mesh, round(scale, 2)), []).append((c, H - 1 - r, 0.0))
        taken.append((r, c))

    def off(r, c):                                   # a spot a little off a unit position, on open ground
        for _ in range(40):
            a = rng.uniform(0, 6.28)
            rr, cc = r + FLO_OFF * math.sin(a), c + FLO_OFF * math.cos(a)
            ri, ci = int(round(rr)), int(round(cc))
            if open_[ri, ci] and to_space[ri, ci] > 2 and all(math.hypot(rr - a_, cc - b_) > 2.0 for a_, b_ in units):
                return rr, cc
        return r, c
    centre = lambda feat: np.mean([v["centre"] for v in prov.values() if v["feature"] == feat], 0)
    # Hondo's complex: in the middle of its enclave
    cr, cc = centre("Hondo's Complex")
    put("hod_flo_complex", cr, cc, FLO_SCALE["hod_flo_complex"])
    # the vault: its door at the back of its pocket in the shelf, facing out toward the way in
    vr, vc = vp_at["Hondo's Secret Ship Vault"]
    dr, dc = cr - vr, cc - vc                                            # out of the pocket: toward the complex
    n_ = math.hypot(dr, dc) or 1
    r0, c0 = vr - dr / n_ * 1.5, vc - dc / n_ * 1.5                     # back against the rock
    turn = math.atan2(-dr, dc) + math.pi / 2                             # front (south when unturned) faces out
    put(f"hod_flo_vault_r{round(turn / (math.pi / 4)) % 8}", r0, c0, FLO_SCALE["hod_flo_vault"])
    # the junk market: wrecked ships and scrap among the stalls
    mk = np.argwhere(zone == 6)
    for mesh, sc in (("hod_bld_rp_lethisk", 0.8), ("hod_bld_rp_hammerhead_bow", 0.5), ("hod_bld_rpt_crates1", 0.8),
                     ("hod_bld_rpt_crates5", 0.8), ("hod_bld_rpt_crates9", 0.8), ("hod_bld_rpt_huttTower", 0.6)):
        for _ in range(60):
            r, c = mk[rng.randrange(len(mk))]
            if all(math.hypot(r - a, c - b) > 1.8 for a, b in taken + units):
                put(mesh, r, c, sc)
                break
    # Commerce Guild posts at their victory points, the refinery on the acid flats
    for name in ("Doshar Fields", "Guild Sulfur Works", "Skalder Plains", "Dustbowl Outpost"):
        r, c = off(*vp_at[name])
        put(f"hod_flo_outpost_{'ab'[len(taken) % 2]}", r, c, FLO_SCALE["hod_flo_outpost"])
    r, c = off(*vp_at["Guild Sulfur Refinery"])
    put("hod_flo_refinery", r, c, FLO_SCALE["hod_flo_refinery"])
    # a few more mercenary outposts on the open plains
    spots = np.argwhere((zone == 1) & (to_shelf > 2) & (to_space > 3))
    n_out = 0
    for k in sorted(range(len(spots)), key=lambda _: rng.random()):
        r, c = spots[k]
        if all(math.hypot(r - a, c - b) >= FLO_SCATTER[1] for a, b in taken) and \
                all(math.hypot(r - a, c - b) >= 2.5 for a, b in units):
            put(f"hod_flo_outpost_{'ab'[n_out % 2]}", r, c, FLO_SCALE["hod_flo_outpost"])
            n_out += 1
            if n_out == FLO_SCATTER[0]:
                break
    own = sorted({m for m, _ in objs if m.startswith("hod_flo_")})
    open("gfx/entities/hod_florrum.gfx", "w", encoding="utf-8", newline="\n").write(
        "objectTypes = {\n\t# HOD: Florrum (military_buildings.py florrum_place)\n"
        + "".join(f'\tpdxmesh = {{\n\t\tname = "{m}_mesh"\n\t\tfile = "{LM_OUT}/{m}.mesh"\n\t}}\n' for m in own) + "}\n")
    open("gfx/entities/hod_florrum.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: Florrum (military_buildings.py florrum_place)\n"
        + "".join(f'entity = {{\n\tname = "{m}_entity"\n\tpdxmesh = "{m}_mesh"\n\tscale = 1\n}}\n' for m in own))
    block_ = FLO_MARK[0] + "\n"
    for (mesh, scale), pts in sorted(objs.items()):
        block_ += f'type={{\n\ttype="{mesh}_entity"\n\tuse_animation=no\n\tscale={scale:.6f}\n'
        block_ += "".join(f'\tobject={{\n\t\tname="{mesh}_flo_{int(scale * 100)}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} 0.000 {zz:.3f} \n'
                          f'\t\t}}\n\t\trotation={{\n\t\t\t0.000 0.000 0.000 \n\t\t}}\n\t}}\n' for i, (x, zz, _y) in enumerate(pts))
        block_ += "}\n"
    block_ += FLO_MARK[1] + "\n"
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from felucia_tribes import rw
    rw("map/ambient_object.txt", lambda s: re.sub(re.escape(FLO_MARK[0]) + r".*?" + re.escape(FLO_MARK[1]) + r"\n", "", s,
                                                    flags=re.S).rstrip("\n") + "\n" + block_)
    count = {}
    for (mesh, _s), pts in objs.items():
        count[mesh] = count.get(mesh, 0) + len(pts)
    print("Florrum:", count)

KAD_MARK = ("# HOD: Kadavo (military_buildings.py kadavo_place)", "# HOD: end of Kadavo")
KAD_SCALE = {"hod_kad_facility": 1.0, "hod_kad_tower": 0.7, "hod_kad_dock": 1.0, "hod_kad_mine": 0.9, "hod_kad_camp": 1.0}
KAD_OFF = 2.6                    # px a model stands off a unit position
KAD_CRATERS = 50                 # volcanic crater models scattered over the planet
KAD_CRATER_R = {"a": 3.2, "b": 4.6, "c": 2.6, "d": 1.4}                 # footprint radii at scale 1 (KAD_CRATER_PROFILES)
KAD_CRATER_SCALE = {"a": (0.5, 1.0), "b": (0.45, 0.85), "c": (0.5, 1.0), "d": (0.7, 1.4)}
KAD_CRATER_MOUTH = 0.5           # the mouth's share of the footprint: no unit position inside it


def kadavo_place():
    """map/ambient_object.txt for kadavo_map.py's layout (y = 0: stood on the ground): the processing facility on the
    prison deck in the Great Crater (its girder arms along the causeways to bastions on the rim), the
    slavers' dock, rigs in the ore pits, a slave camp at each plains victory point; all off the unit positions.
    Entities in gfx/entities/hod_kadavo.{gfx,asset}. Run after kadavo_map.py and planet_terrain_gen.py --kadavo."""
    import json
    import random
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    z = json.load(open("WIPGFX/Assets/kadavo_zones.json"))
    zone = np.asarray(Image.open("WIPGFX/Assets/kadavo_zones.png"))
    H = zone.shape[0]
    rng = random.Random("kadavo")
    prov = z["provinces"]
    units = [v["centre"] for v in prov.values()]
    vp_at = {n: prov[p]["centre"] for p, n in z["vp_names"].items()}
    objs, taken = {}, []

    def put(mesh, r, c):
        objs.setdefault((mesh, KAD_SCALE[mesh]), []).append((c, H - 1 - r, 0.0))
        taken.append((r, c))

    def clear(r, c, d=KAD_OFF):
        return all(math.hypot(r - a, c - b) >= d for a, b in units)

    def near(r, c, zones):                           # a spot on these zones a little off (r, c) and the unit positions
        for rad in (KAD_OFF, KAD_OFF + 1, KAD_OFF + 2, KAD_OFF + 3):
            for _ in range(30):
                a = rng.uniform(0, 6.28)
                rr, cc = r + rad * math.sin(a), c + rad * math.cos(a)
                if zone[int(round(rr)), int(round(cc))] in zones and clear(rr, cc) and \
                        all(math.hypot(rr - a_, cc - b_) > 3 for a_, b_ in taken):
                    return rr, cc
        return r, c
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kadavo_map as km
    (pcy, pcx), R = z["centre"], z["radius"]
    hub = (pcy + km.HUB[1] * R, pcx + km.HUB[0] * R)                     # the prison deck's middle (the arms' origin)
    put("hod_kad_facility", *hub)
    put("hod_kad_dock", *near(*vp_at["Slaver Landing Field"], (5,)))
    inner = ndi.distance_transform_edt(zone == 6) > 2.5                  # inside the pits, not on their rims
    pits = [q for q in np.argwhere(inner) if clear(*q, 2.6)]
    for _ in range(2):
        q = max(pits, key=lambda q: min(math.hypot(*(q - np.array(t))) for t in taken))
        put("hod_kad_mine", *q)
    for name in ("Northern Slave Camp", "Cinder Outpost", "Crater Field Watchpost", "Smog Flats Camp"):
        put("hod_kad_camp", *near(*vp_at[name], (1,)))
    # volcanic crater models (the stills): on the plains, the great dome's flank and the lava flows; a unit may stand
    # beside one but not in its mouth; none over another model or off the planet's edge
    edge = ndi.distance_transform_edt(zone > 0)
    spots = np.argwhere(np.isin(zone, (1, 2, 4)) & (edge > 3))
    unit_arr = np.array(units)
    stats = {"edge": 0, "unit": 0, "model": 0}
    placed = 0
    for i in sorted(range(len(spots)), key=lambda _: rng.random()):
        r, c = spots[i]
        v = rng.choices("abcd", weights=(25, 15, 25, 35))[0]
        sc = rng.uniform(*KAD_CRATER_SCALE[v])
        foot = KAD_CRATER_R[v] * sc
        if edge[r, c] <= foot + 0.5:
            stats["edge"] += 1
            continue
        if np.min(np.hypot(unit_arr[:, 0] - r, unit_arr[:, 1] - c)) < foot * KAD_CRATER_MOUTH + 0.5:
            stats["unit"] += 1
            continue
        if any(math.hypot(r - a_, c - b_) < foot + 0.8 for a_, b_ in taken):
            stats["model"] += 1
            continue
        objs.setdefault((f"hod_kad_crater_{v}", round(sc, 1)), []).append((c, H - 1 - r, 0.0))
        taken.append((r, c))
        placed += 1
        if placed == KAD_CRATERS:
            break
    print("craters placed", placed, "rejected", stats)
    meshes = sorted({m for m, _ in objs})
    open("gfx/entities/hod_kadavo.gfx", "w", encoding="utf-8", newline="\n").write(
        "objectTypes = {\n\t# HOD: Kadavo (military_buildings.py kadavo_place)\n"
        + "".join(f'\tpdxmesh = {{\n\t\tname = "{m}_mesh"\n\t\tfile = "{LM_OUT}/{m}.mesh"\n\t}}\n' for m in meshes) + "}\n")
    open("gfx/entities/hod_kadavo.asset", "w", encoding="utf-8", newline="\n").write(
        "# HOD: Kadavo (military_buildings.py kadavo_place)\n"
        + "".join(f'entity = {{\n\tname = "{m}_entity"\n\tpdxmesh = "{m}_mesh"\n\tscale = 1\n}}\n' for m in meshes))
    block_ = KAD_MARK[0] + "\n"
    for (mesh, scale), pts in sorted(objs.items()):
        block_ += f'type={{\n\ttype="{mesh}_entity"\n\tuse_animation=no\n\tscale={scale:.6f}\n'
        block_ += "".join(f'\tobject={{\n\t\tname="{mesh}_{int(scale * 100)}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} 0.000 {zz:.3f} \n'
                          f'\t\t}}\n\t\trotation={{\n\t\t\t0.000 0.000 0.000 \n\t\t}}\n\t}}\n' for i, (x, zz, _y) in enumerate(pts))
        block_ += "}\n"
    block_ += KAD_MARK[1] + "\n"
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from felucia_tribes import rw
    rw("map/ambient_object.txt", lambda s: re.sub(re.escape(KAD_MARK[0]) + r".*?" + re.escape(KAD_MARK[1]) + r"\n", "", s,
                                                    flags=re.S).rstrip("\n") + "\n" + block_)
    count = {}
    for (m, _s), p in objs.items():
        count[m] = count.get(m, 0) + len(p)
    print("Kadavo:", count)

def _planet_module(name):
    import importlib
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    return importlib.import_module(name.lower().replace(" ", "_") + "_map")


def check_placement_cfg(mod):
    """problems with a planet's PLACEMENT (empty list = fine): missing meshes, entities defined twice or nowhere,
    unknown VP names or zones"""
    import glob
    import json
    cfg, errs = getattr(mod, "PLACEMENT", None), []
    if cfg is None:
        return [f"{mod.__name__}: no PLACEMENT"]
    slug = mod.PLANET.lower().replace(" ", "_")
    own = f"gfx/entities/hod_{slug}.asset"
    defined = {}
    for f in glob.glob("gfx/entities/*.asset"):
        for n in re.findall(r'name\s*=\s*"([^"]+)_entity"', open(f, encoding="utf-8", errors="replace").read()):
            defined.setdefault(n, []).append(f.replace("\\", "/"))
    if not os.path.exists(mod.ZONES_JSON):
        return errs + [f"{mod.ZONES_JSON} missing: run {mod.__name__}.py first"]
    vps = set(json.load(open(mod.ZONES_JSON))["vp_names"].values())
    kinds = set(mod.KIND.values())
    for mesh, scale, where in cfg["items"]:
        if not os.path.exists(f"{LM_OUT}/{mesh}.mesh"):
            errs.append(f"{mesh}: no {LM_OUT}/{mesh}.mesh" + (" (build it: models " + mesh + ")" if mesh in cfg["new_models"] else ""))
        elsewhere = [f for f in defined.get(mesh, []) if f != own]
        if mesh in cfg["new_models"] and elsewhere:
            errs.append(f"{mesh}: listed as new but already defined in {elsewhere}")
        if mesh not in cfg["new_models"] and not elsewhere:
            errs.append(f"{mesh}: reused but no {mesh}_entity in gfx/entities (add it to new_models?)")
        if not 0 < scale <= 5:
            errs.append(f"{mesh}: scale {scale}")
        if where[0] == "zone_centre" and where[1] not in kinds:
            errs.append(f"{mesh}: zone_centre {where[1]} is not a KIND value")
        elif where[0] == "near_vp":
            for n in [where[1]] if isinstance(where[1], str) else where[1]:
                if n not in vps:
                    errs.append(f"{mesh}: VP '{n}' not in {mod.ZONES_JSON}")
            if not set(where[2]) <= kinds:
                errs.append(f"{mesh}: zones {where[2]} not all KIND values")
        elif where[0] == "at_vp":
            for n in [where[1]] if isinstance(where[1], str) else where[1]:
                if n not in vps:
                    errs.append(f"{mesh}: VP '{n}' not in {mod.ZONES_JSON}")
        elif where[0] not in ("zone_centre", "near_vp"):
            errs.append(f"{mesh}: unknown placement {where[0]!r} (zone_centre, near_vp, at_vp)")
    for mesh, foot in cfg.get("clear", {}).items():
        if mesh not in {m for m, _s, _w in cfg["items"]} or not 0 < foot < 30:
            errs.append(f"clear: {mesh} {foot} (a placed mesh, footprint 0-30 px)")
    return errs


def place_planet(name):
    """map/ambient_object.txt for a planet whose map script has a PLACEMENT (y = 0: stood on the ground):
        PLACEMENT = dict(new_models={meshes this planet defines}, items=[(mesh, scale, where), ...], hook=None,
                     clear={mesh: footprint radius px})   # no city models inside these (cities.bmp + terrain.bmp)
        where: ("zone_centre", kind)               the middle of that zone
               ("near_vp", name or [names], kinds)  a spot on those zones a little off the VP and off unit positions
               ("at_vp", name or [names])           on the VP province's centre (big landmarks)
    Items are placed in order; meshes in new_models get entities in gfx/entities/hod_<planet>.{gfx,asset}, the rest
    must already be defined. The block in ambient_object.txt is marked '# HOD: <Planet> (military_buildings.py
    <planet>_place)' and replaced on each run. hook(ctx) may add objects with ctx['put'](mesh, scale, r, c)."""
    import json
    import random
    import numpy as np
    from PIL import Image
    mod = _planet_module(name)
    errs = check_placement_cfg(mod)
    if errs:                                                               # nothing written
        sys.exit(f"{mod.__name__}.PLACEMENT:\n  " + "\n  ".join(errs))
    cfg, planet = mod.PLACEMENT, mod.PLANET
    slug = planet.lower().replace(" ", "_")
    tag = cfg.get("tag", slug[:3])
    mark = (f"# HOD: {planet} (military_buildings.py {slug}_place)", f"# HOD: end of {planet}")
    z = json.load(open(mod.ZONES_JSON))
    zone = np.asarray(Image.open(mod.ZONES_PNG))
    H = zone.shape[0]
    rng = random.Random(slug)
    units = [v["centre"] for v in z["provinces"].values()]
    vp_at = {n: z["provinces"][p]["centre"] for p, n in z["vp_names"].items()}
    objs, taken = {}, []

    def put(mesh, scale, r, c):
        objs.setdefault((mesh, scale), []).append((c, H - 1 - r, 0.0))
        taken.append((r, c))

    def clear(r, c, d=KAD_OFF):
        return all(math.hypot(r - a, c - b) >= d for a, b in units)

    def near(r, c, zones):                           # a spot on these zones a little off (r, c) and the unit positions
        for rad in (KAD_OFF, KAD_OFF + 1, KAD_OFF + 2, KAD_OFF + 3):
            for _ in range(30):
                a = rng.uniform(0, 6.28)
                rr, cc = r + rad * math.sin(a), c + rad * math.cos(a)
                if zone[int(round(rr)), int(round(cc))] in zones and clear(rr, cc) and \
                        all(math.hypot(rr - a_, cc - b_) > 3 for a_, b_ in taken):
                    return rr, cc
        print("  no clear spot near", (round(r), round(c)), "zones", zones, "- placed on the VP")
        return r, c
    for mesh, scale, where in cfg["items"]:
        if where[0] == "zone_centre":
            put(mesh, scale, *np.argwhere(zone == where[1]).mean(0))
        elif where[0] == "at_vp":                                          # big landmarks: on the VP province itself
            for n in [where[1]] if isinstance(where[1], str) else where[1]:
                put(mesh, scale, *vp_at[n])
        else:
            for n in [where[1]] if isinstance(where[1], str) else where[1]:
                put(mesh, scale, *near(*vp_at[n], where[2]))
    if cfg.get("hook"):
        cfg["hook"](dict(put=put, near=near, clear=clear, zone=zone, z=z, rng=rng, taken=taken, vp_at=vp_at))
    if cfg.get("clear"):                                                   # no city models inside the big landmarks
        import io
        city = Image.open(io.BytesIO(open("map/cities.bmp", "rb").read()))
        terr = Image.open(io.BytesIO(open("map/terrain.bmp", "rb").read()))
        styles, tidx = np.array(city), np.array(terr)
        yy, xx = np.mgrid[0:H, 0:zone.shape[1]]
        for (mesh, _sc), pts in objs.items():
            foot = cfg["clear"].get(mesh)
            for x, zz, _y in pts if foot else ():
                cy, cx = H - 1 - zz, x
                win = np.s_[max(int(cy - foot - CITY_MARGIN - 1), 0):int(cy + foot + CITY_MARGIN + 2),
                            max(int(cx - foot - CITY_MARGIN - 1), 0):int(cx + foot + CITY_MARGIN + 2)]
                inside = np.hypot(yy[win] - cy, xx[win] - cx) <= foot + CITY_MARGIN
                styles[win][inside] = 0
                t_ = tidx[win]
                for spawn, plain in NO_SPAWN.items():                      # spawn_city textures -> their plain twins
                    t_[inside & (t_ == spawn)] = plain
        for arr, img, path in ((styles, city, "map/cities.bmp"), (tidx, terr, "map/terrain.bmp")):
            out = Image.fromarray(arr.astype(np.uint8), "P")
            out.putpalette(img.getpalette())
            out.save(path)
    new = sorted({m for m, _ in objs if m in cfg["new_models"]})
    open(f"gfx/entities/hod_{slug}.gfx", "w", encoding="utf-8", newline="\n").write(
        f"objectTypes = {{\n\t{mark[0]}\n"
        + "".join(f'\tpdxmesh = {{\n\t\tname = "{m}_mesh"\n\t\tfile = "{LM_OUT}/{m}.mesh"\n\t}}\n' for m in new) + "}\n")
    open(f"gfx/entities/hod_{slug}.asset", "w", encoding="utf-8", newline="\n").write(
        f"{mark[0]}\n" + "".join(f'entity = {{\n\tname = "{m}_entity"\n\tpdxmesh = "{m}_mesh"\n\tscale = 1\n}}\n' for m in new))
    block_ = mark[0] + "\n"
    for (mesh, scale), pts in sorted(objs.items()):
        block_ += f'type={{\n\ttype="{mesh}_entity"\n\tuse_animation=no\n\tscale={scale:.6f}\n'
        block_ += "".join(f'\tobject={{\n\t\tname="{mesh}_{tag}_{int(scale * 100)}_{i}"\n\t\tposition={{\n\t\t\t{x:.3f} 0.000 {zz:.3f} \n'
                          f'\t\t}}\n\t\trotation={{\n\t\t\t0.000 0.000 0.000 \n\t\t}}\n\t}}\n' for i, (x, zz, _y) in enumerate(pts))
        block_ += "}\n"
    block_ += mark[1] + "\n"
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from felucia_tribes import rw
    rw("map/ambient_object.txt", lambda s: re.sub(re.escape(mark[0]) + r".*?" + re.escape(mark[1]) + r"\n", "", s,
                                                    flags=re.S).rstrip("\n") + "\n" + block_)
    print(f"{planet}:", {m: len(p) for (m, _s), p in objs.items()})


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"textures": textures, "launchpad": launchpad, "wire": wire, "landmarks": landmarks, "atlas": atlas,
     "felucia_atlas": felucia_atlas, "korriban_atlas": korriban_atlas, "zygerria_atlas": zygerria_atlas, "dromund_atlas": dromund_atlas, "cantonica_atlas": cantonica_atlas, "kadavo_atlas": kadavo_atlas, "korriban_place": korriban_place, "florrum_place": florrum_place, "kadavo_place": kadavo_place, "zygerria_place": lambda: place_planet("Zygerria"), "place": place_planet, "models": models,
     "banner_texture": banner_texture, "raxus_alley": raxus_alley}[args[0]](*args[1:])
