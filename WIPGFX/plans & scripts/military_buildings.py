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
# hod_bonadan atlas (bonadan_atlas; Legends: a polluted industrial world of factories, refineries, docks and shipyards
# on yellow eroded wastes): grimy ochre-grey factory plate, plain and with lit window rows; stained concrete, plain and
# with lit strip windows; rust; soot black; corrugated roof sheet; hazard stripes; warm light; a landing pad;
# steel pipework; hull plating; girder lattice; soot-stained chimney brick; yellow drift dust
B_PLATE, B_PLATE_WIN, B_CONC, B_CONC_WIN = (_cell(i, 0) for i in range(4))
B_RUST, B_SOOT, B_ROOF, B_HAZARD = (_cell(i, 1) for i in range(4))
B_GLOW, B_PAD, B_PIPE, B_HULL = (_cell(i, 2) for i in range(4))
B_GIRDER, B_BRICK, B_DUST, B_DARK = (_cell(i, 3) for i in range(4))
# hod_etti atlas (etti_atlas; Etti IV, the Corporate Sector's rich capital world: Mondder's towers in the Legends comics
# "Mondder streets" / "Imperial Embassy" stills: pale ceramic and teal glass, neon at street level; Cybot Galactica's
# Arcoplex in cobalt and gold): white ceramic panels, plain and with lit window bands; teal glass curtain wall, plain
# and lit; cobalt panels with windows; gold trim; blue-grey steel; roof; warm light; neon; a landing pad; hazard
# stripes; garden; dome glass; concrete; dark
E_CERAMIC, E_CERAMIC_WIN, E_GLASS, E_GLASS_LIT = (_cell(i, 0) for i in range(4))
E_COBALT, E_COBALT_WIN, E_GOLD, E_STEEL = (_cell(i, 1) for i in range(4))
E_ROOF, E_GLOW, E_NEON, E_PAD = (_cell(i, 2) for i in range(4))
E_HAZARD, E_GARDEN, E_DOME, E_DARK = (_cell(i, 3) for i in range(4))
# hod_ruuria atlas (ruuria_atlas; Ruuria: the caterpillar-like Ruurians' colony hives in a humid jungle (Legends), the
# University of Ruuria (canon + Legends); the look is a design choice from the species: silk, chitin, resin):
# woven silk-white cocoon wall, plain and with resin-lit openings; amber chitin plates, plain and with openings;
# pale university stone, plain and with arched windows; green roof moss; warm resin glow; dark openings; bark-brown
# stalk; slate roof; pink river stone; leaf green; bronze; dome glass; mud
R_SILK, R_SILK_WIN, R_CHITIN, R_CHITIN_WIN = (_cell(i, 0) for i in range(4))
R_STONE, R_STONE_WIN, R_MOSS, R_GLOW = (_cell(i, 1) for i in range(4))
R_DARK, R_STALK, R_SLATE, R_PINK = (_cell(i, 2) for i in range(4))
R_LEAF, R_BRONZE, R_DOME, R_MUD = (_cell(i, 3) for i in range(4))
# hod_ossus atlas (ossus_atlas; Ossus four thousand years after the Cron Supernova: Knossa "built from stone and
# bronzium, its squat domes" (canon), the Great Jedi Library "a large, unadorned stone building" (Legends), the masked
# Ysanna tribes (canon + Legends), Jedi archaeologists' digs (Legends)): weathered pale stone, plain and with dark
# empty windows; stone scorched by the supernova; patinated bronzium; moss and vines; rubble; Ysanna hide, timber,
# painted mask red; excavation tarp; scaffold wood; the vergence's pale glow; dark openings; earth
O_STONE, O_STONE_WIN, O_SCORCH, O_BRONZE = (_cell(i, 0) for i in range(4))
O_MOSS, O_RUBBLE, O_HIDE, O_TIMBER = (_cell(i, 1) for i in range(4))
O_MASK, O_TARP, O_SCAFFOLD, O_GLOW = (_cell(i, 2) for i in range(4))
O_DARK, O_EARTH, O_ROCK, O_STONE_CARVED = (_cell(i, 3) for i in range(4))
# hod_lola atlas (lola_atlas; Lola Sayu: the broken volcanic world and the Citadel, the Republic's prison for rogue Jedi
# (canon, TCW "The Citadel"): a dark angular fortress of grey plating with pale window bands, built over lava):
# basalt, plain and with glowing lava cracks; cooled crust; dark grey plating, plain and with lit window bands;
# ribbed metal; lava (bright); sulfur; dark openings; landing pad; pale light; red warning light; Republic blue trim
L_BASALT, L_BASALT_CRACK, L_CRUST, L_PLATE = (_cell(i, 0) for i in range(4))
L_PLATE_WIN, L_RIB, L_LAVA, L_SULFUR = (_cell(i, 1) for i in range(4))
L_DARK, L_PAD, L_GLOW, L_RED = (_cell(i, 2) for i in range(4))
L_TRIM, L_ROCK, L_STRATA, L_SPARE2 = (_cell(i, 3) for i in range(4))   # L_STRATA: the planet's cross-section
# hod_ringo atlas (ringo_atlas; Ringo Vinda: the surface after the early Cato Neimoidia concept art the planet was
# designed from (canon, out-of-universe): pale banded rock pillars and arches, cities of cream stone with green-bronze
# domes hung beneath them; the space station (TCW): a vast grey-tan ring of hull plating): banded pillar rock, plain
# and weathered; cream city stone, plain and with lit windows; green-bronze dome; slate roof; warm light; dark; grey-tan
# hull, plain and with lit window rows; ribbed panels; dock lights; hazard; landing pad; garden; glass
V_ROCK, V_ROCK_DARK, V_STONE, V_STONE_WIN = (_cell(i, 0) for i in range(4))
V_DOME, V_ROOF, V_GLOW, V_DARK = (_cell(i, 1) for i in range(4))
V_HULL, V_HULL_WIN, V_PANEL, V_LIGHT = (_cell(i, 2) for i in range(4))
V_HAZARD, V_PAD, V_GARDEN, V_GLASS = (_cell(i, 3) for i in range(4))
# hod_rhen atlas (rhen_atlas; Rhen Var: the castles, fortresses and temples of a lost civilization engulfed by an ice
# age (Legends; Star Wars: Battlefront "Rhen Var Harbor" / "Rhen Var Citadel"), the Republic's Bravo Base (Legends)):
# frost-weathered blue-grey stone, plain and with dark arched windows; carved stone; snow; ice; dark openings;
# Republic prefab panel, plain and with lit windows; Republic red stripe; dark Sith stone; Rakatan stone with glowing
# script; light; landing pad; hazard; frozen timber
H_STONE, H_STONE_WIN, H_CARVED, H_SNOW = (_cell(i, 0) for i in range(4))
H_ICE, H_DARK, H_PANEL, H_PANEL_WIN = (_cell(i, 1) for i in range(4))
H_RED, H_SITH, H_RAKATA, H_GLOW = (_cell(i, 2) for i in range(4))
H_PAD, H_HAZARD, H_TIMBER, H_ROOF = (_cell(i, 3) for i in range(4))
# the orbital shipyard's arc (bonadan_map.PLACEMENT puts the origin): radius round the planet centre in map units
# (the planet is ~60 px across in radius), its ends as angles (degrees, east = 0, north +: provinces 6525 and 6947),
# and the height its underside floats above the space floor
BON_ORBIT_R, BON_ARC, BON_FLOAT = 72.0, (-51.8, 47.5), 3.0
LOLA_TURNS = 3     # yaw copies of each Lola Sayu chunk
# Ringo Vinda's ring station: radius round the planet centre (map units; the planet is ~32 px in radius and Lola Sayu's
# land is 47 px away to the east), its underside's height over the space floor, its graving docks, the moored ships'
# scale (the converted ships of sketchfab_props.py bon_*)
RV_RING_R, RV_FLOAT, RV_DOCKS, RV_SHIP_SCALE = 38.0, 2.5, 12, 0.85
LOLA_FLOAT = 2.0   # Lola Sayu's debris: the chunks' undersides float this far above the space floor (water plane ~1.1 up)
# its slips from the south end to the north: (ship, share of the hull plated), the ships of sketchfab_props.py bon_*;
# (length, beam, height) of each as baked
BON_SLIPS = [("hammerhead", 1.0), ("derriphan", 0.45), ("foray", 1.0), ("hammerhead", 0.6), ("derriphan", 1.0),
             ("hammerhead", 0.35), ("derriphan", 0.7), ("foray", 0.5)]
BON_SHIP_SCALE = 1.45          # the baked ships (sketchfab_props.py sizes) enlarged to fill their slips
BON_SHIP_DIMS = {k_: tuple(BON_SHIP_SCALE * d for d in v) for k_, v in
                 {"derriphan": (10.5, 2.9, 6.2), "hammerhead": (8.5, 3.85, 3.7), "foray": (6.0, 1.4, 1.0)}.items()}
# the Pammant Docks (pammant_map.PLACEMENT puts the ring's centre out in space): ring radius, the height its underside
# floats over the space floor, where it sits (map units from the planet's centre, bearing in degrees, east = 0,
# north +); the Malevolence's cradle heading (radians) and the piers of the Providence-class ships (bearing round the
# ring, share of the hull plated); the ships' (length, beam, height) as baked (sketchfab_props.py pam_*)
PAM_RING_R, PAM_FLOAT, PAM_AT = 20.0, 3.0, (104.0, 40.0)
PAM_CRADLE = 0.45
PAM_PIERS = [(PAM_CRADLE + math.pi / 2, 1.0), (PAM_CRADLE - math.pi / 2 + 0.6, 1.0), (PAM_CRADLE - math.pi / 2 - 0.6, 0.55)]
PAM_SHIP_DIMS = {"pam_malevolence": (34.0, 9.42, 6.01), "pam_invisible_hand": (14.0, 3.06, 4.73)}
PAM_PORT_A = math.radians(35)  # the lift port's long axis (pammant_map: its rect turned -35 deg in u east / v south)
# the LaserWeb Defense Station in orbit (iego_map.PLACEMENT hook): its centre (map units from the planet's centre,
# bearing in degrees, east = 0, north +) and the height its underside floats over the space floor
# the Lianna shipyards in orbit (lianna_map.PLACEMENT hook): the hub (map units from the planet's centre, bearing in
# degrees, east = 0, north +) and the height its underside floats over the space floor
LIA_YARD_AT, LIA_YARD_FLOAT = (66.0, 0.0), 3.0
BOT_YARD_AT = (96.0, 0.0)   # Botajef's orbital yards (botajef_map.PLACEMENT hook), same convention; east is clear
IEG_WEB_AT, IEG_WEB_FLOAT = (106.0, 0.0), 3.0
IEG_CLIFF_SCALE = 0.42   # Cliffhold's city at this scale on the escarpment's face (iego_map.PLACEMENT hook)
IEG_CLIFF_A = math.radians(6)   # Cliffhold faces the escarpment wall next to its VP (measured: the wall looks out at -84 deg)


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


def bonadan_atlas():
    """hod_bonadan textures (Legends Bonadan: factories, refineries, docks and shipyards under polluted air; the map is
    always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 86)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    sooty = lambda rgb: rgb * (0.78 + 0.28 * grime) * (0.8 + 0.25 * blotch) * (0.75 + 0.3 * streak)
    seams = (((xx % 48) < 2) | ((yy % 32) < 2))[..., None]
    plate = sooty(np.array([150, 140, 112], np.float32)) * (1 - 0.25 * seams)
    put(B_PLATE, plate, sp=60)
    rows = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 16) > 3)
    lit = rows & (rng.random((t, t)) > 0.3)
    warm = np.array([255, 205, 120], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [36, 34, 30], plate)), e=np.where(lit, 220, 0), sp=60)
    conc = sooty(np.array([168, 160, 144], np.float32)) * (1 - 0.15 * ((yy % 40) < 2)[..., None])
    put(B_CONC, conc)
    strip = (np.abs((yy % 40) - 22) < 3) & ((xx % 64) > 4)
    put(B_CONC_WIN, np.where(strip[..., None], warm * (0.9 + 0.1 * grime), conc), e=np.where(strip, 230, 0))
    put(B_RUST, np.array([150, 72, 38], np.float32) * (0.7 + 0.45 * grime) * (0.8 + 0.3 * streak), sp=50)
    put(B_SOOT, np.array([34, 30, 28], np.float32) * (0.8 + 0.4 * grime))
    put(B_ROOF, sooty(np.array([128, 124, 116], np.float32)) * (0.85 + 0.15 * np.sin(xx / 3.0))[..., None], sp=80)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 190, 40], [30, 28, 26]) * (0.8 + 0.25 * grime))
    put(B_GLOW, warm * (1.0 + 0.1 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (110, 108, 102))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(240, 190, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    d.line([(t * 0.2, t * 0.5), (t * 0.8, t * 0.5)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.75 + 0.3 * grime))
    put(B_PIPE, np.array([120, 118, 112], np.float32) * (0.75 + 0.35 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([176, 176, 168], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=90)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 96, 70], [40, 36, 32]) * (0.8 + 0.3 * grime), sp=80)
    brick = 1 - 0.25 * (((yy % 12) < 2) | ((((xx + 12 * ((yy // 12) % 2)) % 24) < 2)))[..., None]
    soot_top = np.clip((t * 0.35 - yy) / (t * 0.35), 0, 1)[..., None]   # v 1 (the top) blackened
    put(B_BRICK, np.array([142, 82, 56], np.float32) * brick * (0.8 + 0.3 * grime) * (1 - 0.75 * soot_top))
    put(B_DUST, np.array([214, 184, 112], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([20, 20, 22], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_bonadan", col, emi, spec)



def pammant_atlas():
    """hod_pammant textures (the Quarren shipbuilders of Pammant and their Separatist yards: Confederacy tan plate and
    grey hull, the Quarren's cool aqua window light; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 78)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    sooty = lambda rgb: rgb * (0.78 + 0.28 * grime) * (0.8 + 0.25 * blotch) * (0.75 + 0.3 * streak)
    seams = (((xx % 48) < 2) | ((yy % 32) < 2))[..., None]
    plate = sooty(np.array([178, 156, 112], np.float32)) * (1 - 0.25 * seams)
    put(B_PLATE, plate, sp=60)
    rows = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 16) > 3)
    lit = rows & (rng.random((t, t)) > 0.3)
    warm = np.array([150, 235, 230], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [36, 34, 30], plate)), e=np.where(lit, 220, 0), sp=60)
    conc = sooty(np.array([150, 150, 146], np.float32)) * (1 - 0.15 * ((yy % 40) < 2)[..., None])
    put(B_CONC, conc)
    strip = (np.abs((yy % 40) - 22) < 3) & ((xx % 64) > 4)
    put(B_CONC_WIN, np.where(strip[..., None], warm * (0.9 + 0.1 * grime), conc), e=np.where(strip, 230, 0))
    put(B_RUST, np.array([132, 78, 52], np.float32) * (0.7 + 0.45 * grime) * (0.8 + 0.3 * streak), sp=50)
    put(B_SOOT, np.array([34, 30, 28], np.float32) * (0.8 + 0.4 * grime))
    put(B_ROOF, sooty(np.array([112, 110, 108], np.float32)) * (0.85 + 0.15 * np.sin(xx / 3.0))[..., None], sp=80)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 190, 40], [30, 28, 26]) * (0.8 + 0.25 * grime))
    put(B_GLOW, warm * (1.0 + 0.1 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (110, 108, 102))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(240, 190, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    d.line([(t * 0.2, t * 0.5), (t * 0.8, t * 0.5)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.75 + 0.3 * grime))
    put(B_PIPE, np.array([120, 118, 112], np.float32) * (0.75 + 0.35 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([168, 170, 172], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=90)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 96, 70], [40, 36, 32]) * (0.8 + 0.3 * grime), sp=80)
    brick = 1 - 0.25 * (((yy % 12) < 2) | ((((xx + 12 * ((yy // 12) % 2)) % 24) < 2)))[..., None]
    soot_top = np.clip((t * 0.35 - yy) / (t * 0.35), 0, 1)[..., None]   # v 1 (the top) blackened
    put(B_BRICK, np.array([96, 92, 88], np.float32) * brick * (0.8 + 0.3 * grime) * (1 - 0.75 * soot_top))
    put(B_DUST, np.array([92, 88, 84], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([20, 20, 22], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_pammant", col, emi, spec)






def saleucami_atlas():
    """hod_saleucami textures (Saleucami: warm terracotta and ochre adobe, grey stone, volcanic black, warm
    window light; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 74)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    sooty = lambda rgb: rgb * (0.78 + 0.28 * grime) * (0.8 + 0.25 * blotch) * (0.75 + 0.3 * streak)
    seams = (((xx % 48) < 2) | ((yy % 32) < 2))[..., None]
    plate = sooty(np.array([200, 160, 116], np.float32)) * (1 - 0.25 * seams)
    put(B_PLATE, plate, sp=60)
    rows = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 16) > 3)
    lit = rows & (rng.random((t, t)) > 0.3)
    warm = np.array([255, 196, 120], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [36, 34, 30], plate)), e=np.where(lit, 220, 0), sp=60)
    conc = sooty(np.array([168, 150, 126], np.float32)) * (1 - 0.15 * ((yy % 40) < 2)[..., None])
    put(B_CONC, conc)
    strip = (np.abs((yy % 40) - 22) < 3) & ((xx % 64) > 4)
    put(B_CONC_WIN, np.where(strip[..., None], warm * (0.9 + 0.1 * grime), conc), e=np.where(strip, 230, 0))
    put(B_RUST, np.array([176, 92, 58], np.float32) * (0.7 + 0.45 * grime) * (0.8 + 0.3 * streak), sp=50)
    put(B_SOOT, np.array([34, 30, 28], np.float32) * (0.8 + 0.4 * grime))
    put(B_ROOF, sooty(np.array([150, 96, 66], np.float32)) * (0.85 + 0.15 * np.sin(xx / 3.0))[..., None], sp=80)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 190, 40], [30, 28, 26]) * (0.8 + 0.25 * grime))
    put(B_GLOW, warm * (1.0 + 0.1 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (110, 108, 102))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(240, 190, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    d.line([(t * 0.2, t * 0.5), (t * 0.8, t * 0.5)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.75 + 0.3 * grime))
    put(B_PIPE, np.array([120, 118, 112], np.float32) * (0.75 + 0.35 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([186, 180, 168], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=90)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 96, 70], [40, 36, 32]) * (0.8 + 0.3 * grime), sp=80)
    brick = 1 - 0.25 * (((yy % 12) < 2) | ((((xx + 12 * ((yy // 12) % 2)) % 24) < 2)))[..., None]
    soot_top = np.clip((t * 0.35 - yy) / (t * 0.35), 0, 1)[..., None]   # v 1 (the top) blackened
    put(B_BRICK, np.array([64, 56, 54], np.float32) * brick * (0.8 + 0.3 * grime) * (1 - 0.75 * soot_top))
    put(B_DUST, np.array([214, 178, 132], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([20, 20, 22], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_saleucami", col, emi, spec)


def telos_atlas():
    """hod_telos textures (Telos, the city-world, after Knights of the Old Republic II's Telos and Citadel Station:
    cream modular plating, blue glass, orange Telosian trim, slate-blue roofs; polar ice and black malab for the
    Academy and the Mirror Caverns; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 76)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    clean = lambda rgb: rgb * (0.9 + 0.12 * grime) * (0.92 + 0.1 * blotch) * (0.9 + 0.12 * streak)
    seams = (((xx % 48) < 2) | ((yy % 32) < 2))[..., None]
    plate = clean(np.array([226, 214, 188], np.float32)) * (1 - 0.18 * seams)
    put(B_PLATE, plate, sp=70)
    rows = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 16) > 3)
    lit = rows & (rng.random((t, t)) > 0.35)
    cool = np.array([170, 214, 246], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], cool, np.where(rows[..., None], [40, 70, 98], plate)), e=np.where(lit, 200, 0), sp=90)
    conc = clean(np.array([186, 184, 176], np.float32)) * (1 - 0.12 * ((yy % 40) < 2)[..., None])
    put(B_CONC, conc)
    glass = ((xx % 24) < 2) | ((yy % 24) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [70, 86, 100], clean(np.array([62, 112, 156], np.float32))),
        e=np.where(glass, 0, 90), sp=160)
    put(B_RUST, clean(np.array([214, 110, 44], np.float32)), sp=80)                     # Telosian orange trim
    put(B_SOOT, np.array([226, 238, 248], np.float32) * (0.88 + 0.14 * noise(1.5)), sp=120)   # polar ice
    put(B_ROOF, clean(np.array([84, 102, 124], np.float32)) * (0.88 + 0.12 * np.sin(xx / 3.0))[..., None], sp=90)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 150, 40], [40, 40, 44]) * (0.85 + 0.2 * grime))
    put(B_GLOW, cool * (1.0 + 0.08 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (150, 150, 146))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(214, 110, 44), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    d.line([(t * 0.2, t * 0.5), (t * 0.8, t * 0.5)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_PIPE, np.array([150, 152, 156], np.float32) * (0.8 + 0.3 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([212, 212, 206], np.float32) * (0.88 + 0.15 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=100)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [150, 150, 150], [50, 52, 56]) * (0.8 + 0.3 * grime), sp=80)
    put(B_BRICK, np.array([18, 18, 22], np.float32) * (0.7 + 0.6 * noise(3)) + 6, sp=255)   # malab: black, lustrous
    put(B_DUST, np.array([204, 200, 188], np.float32) * (0.88 + 0.15 * noise(1.5)))
    put(B_DARK, np.array([20, 22, 26], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_telos", col, emi, spec)


def serenno_atlas():
    """hod_serenno textures (Serenno, the Count's world, after Tales of the Jedi and The Clone Wars: pale ashlar with
    gold-lit arched windows, dark slate roofs, gold trim, grey cliff rock, the red-brown rock of the Aparian Wastes, the
    Spike's cell rows, Separatist tan hulls; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 93)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    clean = lambda rgb: rgb * (0.88 + 0.14 * grime) * (0.92 + 0.1 * blotch) * (0.9 + 0.12 * streak)
    course = ((yy % 24) < 2) | ((((yy // 24) % 2) * 24 + xx) % 48 < 2)                  # ashlar courses and joints
    ashlar = clean(np.array([222, 206, 178], np.float32)) * (1 - 0.2 * course[..., None])
    put(B_PLATE, ashlar, sp=40)
    cx_, cy_ = (xx % 32) - 16, (yy % 64)                                                # tall arched windows
    arch = (np.abs(cx_) < 6) & (cy_ > 14) & ((cy_ < 50) & ((cy_ > 26) | (cx_ ** 2 + (cy_ - 26) ** 2 < 36)))
    lit = arch & (rng.random((t, t)) > 0.2)
    gold = np.array([255, 214, 120], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], gold, np.where(arch[..., None], [60, 48, 40], ashlar)),
        e=np.where(lit, 210, 0), sp=60)
    put(B_CONC, clean(np.array([150, 148, 142], np.float32)) * (1 - 0.15 * course[..., None]))
    cells = ((yy % 20) > 6) & ((yy % 20) < 15) & ((xx % 14) > 4)
    put(B_CONC_WIN, np.where(cells[..., None], [40, 44, 50], clean(np.array([120, 118, 112], np.float32))),
        e=np.where(cells & (rng.random((t, t)) > 0.7), 120, 0), sp=60)
    put(B_RUST, clean(np.array([206, 160, 70], np.float32)), sp=180)                     # gold trim
    put(B_SOOT, np.array([118, 116, 108], np.float32) * (0.75 + 0.35 * noise(3)) * (0.9 + 0.15 * noise(1.2)))   # cliff
    tiles = ((yy % 10) < 1.5) | ((((yy // 10) % 2) * 8 + xx) % 16 < 1.5)
    put(B_ROOF, clean(np.array([66, 72, 86], np.float32)) * (1 - 0.25 * tiles[..., None]), sp=110)   # slate
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 150, 40], [40, 40, 44]) * (0.85 + 0.2 * grime))
    put(B_GLOW, gold * (1.0 + 0.08 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (150, 146, 136))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(206, 160, 70), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 236, 220), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_PIPE, np.array([150, 152, 156], np.float32) * (0.8 + 0.3 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([196, 176, 140], np.float32) * (0.88 + 0.15 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=100)                                                            # Separatist tan
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [150, 150, 150], [50, 52, 56]) * (0.8 + 0.3 * grime), sp=80)
    put(B_BRICK, np.array([142, 92, 66], np.float32) * (0.72 + 0.35 * noise(3)) * (0.9 + 0.15 * noise(1.2)))   # wastes rock
    put(B_DUST, np.array([176, 166, 146], np.float32) * (0.85 + 0.2 * noise(1.5)))      # gravel
    put(B_DARK, np.array([20, 20, 24], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_serenno", col, emi, spec)


def yavin_atlas():
    """hod_yavin textures (Yavin IV's Massassi ruins, after A New Hope and Rogue One's Great Temple: grey stone blocks
    patched with moss, dark window slots, the black stone of Exar Kun's temple, volcanic rock, vines, a Sith-red glow;
    the map is always day: the glow is painted bright)."""
    import numpy as np
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 92)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    moss = np.clip((noise(6) - 0.55) * 4, 0, 1)
    blocks = ((yy % 28) < 2) | ((((yy // 28) % 2) * 30 + xx) % 60 < 2)
    stone = np.array([132, 130, 120], np.float32) * (0.85 + 0.2 * grime) * (0.9 + 0.12 * blotch) \
        * (1 - 0.25 * blocks[..., None])
    stone = stone * (1 - moss) + np.array([74, 102, 58], np.float32) * moss * (0.8 + 0.3 * grime)
    put(B_PLATE, stone)
    slots = ((yy % 56) > 18) & ((yy % 56) < 40) & ((xx % 40) > 16) & ((xx % 40) < 24)
    put(B_PLATE_WIN, np.where(slots[..., None], [26, 26, 24], stone))
    put(B_CONC, np.array([112, 110, 102], np.float32) * (0.8 + 0.25 * noise(3)) * (1 - 0.2 * blocks[..., None]))
    put(B_CONC_WIN, np.array([40, 38, 42], np.float32) * (0.8 + 0.35 * noise(3)) * (1 - 0.3 * blocks[..., None]), sp=120)
    put(B_RUST, np.array([70, 104, 54], np.float32) * (0.7 + 0.4 * noise(1.5)))        # moss
    put(B_SOOT, np.array([58, 54, 54], np.float32) * (0.7 + 0.45 * noise(3)) * (0.9 + 0.2 * noise((20, 1.5))))   # volcanic
    put(B_ROOF, stone * 0.6 + np.array([74, 102, 58], np.float32) * 0.4)                # mossy tops
    put(B_BRICK, np.array([46, 86, 44], np.float32) * (0.6 + 0.6 * noise(1.2)))        # vines
    put(B_GLOW, np.array([255, 70, 50], np.float32) * (0.95 + 0.08 * grime), e=255, sp=200)   # the Sith glow
    put(B_DUST, np.array([104, 84, 60], np.float32) * (0.8 + 0.3 * noise(1.5)))        # jungle earth
    put(B_DARK, np.array([16, 16, 18], np.float32) * (0.8 + 0.4 * grime))
    for c in (B_HAZARD, B_PAD, B_PIPE, B_HULL, B_GIRDER):                               # unused: stone
        put(c, stone)
    _atlas_save("hod_yavin", col, emi, spec)


def celanon_atlas():
    """hod_celanon textures (Celanon, the guild-ruled trade world; a design choice: cream render, verdigris copper,
    terracotta roofs, striped market awnings; Hutt adobe; tribal thatch and logs; the map is always day: lights are
    painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 190)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.88 + 0.14 * grime) * (0.92 + 0.1 * blotch)
    render = clean(np.array([230, 218, 192], np.float32))
    put(B_PLATE, render * (1 - 0.12 * ((yy % 40) < 2)[..., None]), sp=40)
    rows = ((yy % 32) > 10) & ((yy % 32) < 22) & ((xx % 20) > 5)
    lit = rows & (rng.random((t, t)) > 0.3)
    warm = np.array([255, 222, 150], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [56, 70, 80], render)), e=np.where(lit, 200, 0),
        sp=70)
    put(B_CONC, clean(np.array([176, 170, 156], np.float32)) * (1 - 0.15 * (((xx % 32) < 2) | ((yy % 32) < 2)))[..., None])
    glass = ((xx % 24) < 2) | ((yy % 24) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [80, 90, 96], clean(np.array([86, 140, 150], np.float32))),
        e=np.where(glass, 0, 80), sp=160)
    put(B_RUST, clean(np.array([96, 168, 140], np.float32)) * (0.9 + 0.12 * np.sin(xx / 4.0))[..., None], sp=120)   # verdigris
    put(B_SOOT, np.array([184, 156, 96], np.float32) * (0.75 + 0.35 * noise(1.2)) * (0.9 + 0.15 * np.sin(yy / 1.5))[..., None])   # thatch
    tiles = ((yy % 12) < 2) | ((((yy // 12) % 2) * 10 + xx) % 20 < 2)
    put(B_ROOF, clean(np.array([178, 96, 64], np.float32)) * (1 - 0.2 * tiles[..., None]), sp=60)    # terracotta
    stripes = ((xx // 20) % 2)[..., None]
    put(B_HAZARD, np.where(stripes, [214, 70, 56], [236, 226, 200]) * (0.88 + 0.15 * grime))     # awnings
    put(B_GLOW, warm * (1.0 + 0.08 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (150, 148, 140))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(96, 168, 140), width=int(t * 0.05))
    d.line([(t * 0.3, t * 0.5), (t * 0.7, t * 0.5)], fill=(240, 236, 220), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_PIPE, np.array([150, 152, 156], np.float32) * (0.8 + 0.3 * grime), sp=110)
    hull = np.array([200, 196, 186], np.float32) * (0.88 + 0.15 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=100)
    put(B_GIRDER, np.array([110, 84, 58], np.float32) * (0.75 + 0.35 * noise(1.2)) * (0.9 + 0.1 * np.sin(xx / 2.0))[..., None])   # logs
    put(B_BRICK, np.array([196, 160, 116], np.float32) * (0.82 + 0.25 * noise(3)) * (0.92 + 0.1 * grime))   # Hutt adobe
    put(B_DUST, np.array([190, 180, 160], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([22, 20, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_celanon", col, emi, spec)


def botajef_atlas():
    """hod_botajef textures (Botajef, the industrial shipbuilding world; a design choice: grimy steel plate, lit window
    rows, rust, soot brick, corrugated roofs, hazard yellow, freighter hulls, polar ice; the map is always day: lights
    are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 191)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    dirty = lambda rgb: rgb * (0.78 + 0.25 * grime) * (0.85 + 0.15 * blotch) * (0.85 + 0.18 * streak)
    plate = dirty(np.array([150, 146, 138], np.float32)) * (1 - 0.18 * (((xx % 48) < 2) | ((yy % 32) < 2)))[..., None]
    put(B_PLATE, plate, sp=70)
    rows = ((yy % 24) > 8) & ((yy % 24) < 15) & ((xx % 12) > 3)
    lit = rows & (rng.random((t, t)) > 0.4)
    amber = np.array([255, 196, 110], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], amber, np.where(rows[..., None], [36, 38, 42], plate)), e=np.where(lit, 200, 0),
        sp=70)
    put(B_CONC, dirty(np.array([136, 132, 124], np.float32)))
    glass = ((xx % 24) < 2) | ((yy % 24) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [60, 62, 66], dirty(np.array([74, 104, 126], np.float32))),
        e=np.where(glass, 0, 70), sp=160)
    put(B_RUST, dirty(np.array([150, 80, 44], np.float32)), sp=60)
    put(B_SOOT, np.array([226, 236, 244], np.float32) * (0.88 + 0.14 * noise(1.5)), sp=120)     # polar ice
    put(B_ROOF, dirty(np.array([112, 116, 118], np.float32)) * (0.86 + 0.14 * np.sin(xx / 2.5))[..., None], sp=90)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [232, 186, 40], [40, 40, 44]) * (0.8 + 0.25 * grime))
    put(B_GLOW, amber * (1.0 + 0.08 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (130, 128, 124))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(232, 186, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_PIPE, np.array([150, 152, 156], np.float32) * (0.8 + 0.3 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([190, 184, 172], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.18 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=100)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [150, 150, 150], [50, 52, 56]) * (0.8 + 0.3 * grime), sp=80)
    courses = ((yy % 12) < 2) | ((((yy // 12) % 2) * 12 + xx) % 24 < 2)
    put(B_BRICK, dirty(np.array([92, 64, 54], np.float32)) * (1 - 0.3 * courses[..., None]))     # soot brick
    put(B_DUST, np.array([120, 112, 100], np.float32) * (0.8 + 0.25 * noise(1.5)))
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_botajef", col, emi, spec)


def axxila_atlas():
    """hod_axxila textures (Axxila, the cliff-world metropolis of the ore trade; a design choice: ochre stone, lit
    window rows, rust and steel, cliff rock, ore heaps, a neon sign for Fossfog's; the map is always day: lights are
    painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 94)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    dirty = lambda rgb: rgb * (0.82 + 0.2 * grime) * (0.88 + 0.12 * blotch) * (0.88 + 0.14 * streak)
    stone = dirty(np.array([196, 160, 112], np.float32)) * (1 - 0.15 * (((yy % 32) < 2) | ((xx % 64) < 2)))[..., None]
    put(B_PLATE, stone, sp=40)
    rows = ((yy % 28) > 9) & ((yy % 28) < 18) & ((xx % 14) > 4)
    lit = rows & (rng.random((t, t)) > 0.35)
    warm = np.array([255, 210, 140], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [48, 40, 34], stone)), e=np.where(lit, 200, 0),
        sp=60)
    put(B_CONC, dirty(np.array([150, 136, 116], np.float32)))
    glass = ((xx % 24) < 2) | ((yy % 24) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [70, 66, 60], dirty(np.array([90, 112, 120], np.float32))),
        e=np.where(glass, 0, 70), sp=160)
    put(B_RUST, dirty(np.array([156, 82, 46], np.float32)), sp=60)
    put(B_SOOT, np.array([168, 128, 92], np.float32) * (0.7 + 0.4 * noise(3)) * (0.88 + 0.18 * noise((20, 1.5))))   # cliffs
    put(B_ROOF, dirty(np.array([118, 104, 90], np.float32)), sp=60)
    sign = ((yy % 64) > 16) & ((yy % 64) < 48) & (((xx // 10) % 3) > 0)
    put(B_HAZARD, np.where(sign[..., None], [255, 90, 160], [40, 30, 40]), e=np.where(sign, 255, 0), sp=200)   # neon
    put(B_GLOW, warm * (1.0 + 0.08 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (140, 128, 112))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(156, 82, 46), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 230, 210), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_PIPE, np.array([150, 148, 144], np.float32) * (0.8 + 0.3 * grime), sp=110)
    hull = np.array([186, 178, 164], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.18 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=100)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [160, 120, 80], [50, 44, 40]) * (0.8 + 0.3 * grime), sp=80)
    put(B_BRICK, np.array([120, 76, 52], np.float32) * (0.6 + 0.6 * noise(1.2)))           # ore
    put(B_DUST, np.array([170, 150, 122], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([20, 18, 16], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_axxila", col, emi, spec)


def ciutric_atlas():
    """hod_ciutric textures (Ciutric IV, the Hegemony's industrial forest world; a design choice: grey ferrocrete,
    lit window rows, dark brick, slate, Hegemony red, dark stone for Bane's mansion; the map is always day: lights are
    painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 188)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.86 + 0.16 * grime) * (0.9 + 0.12 * blotch)
    ferro = clean(np.array([170, 170, 166], np.float32)) * (1 - 0.12 * (((yy % 40) < 2) | ((xx % 40) < 2)))[..., None]
    put(B_PLATE, ferro, sp=50)
    rows = ((yy % 26) > 8) & ((yy % 26) < 17) & ((xx % 10) > 2)
    lit = rows & (rng.random((t, t)) > 0.35)
    cool = np.array([236, 230, 200], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], cool, np.where(rows[..., None], [40, 46, 54], ferro)), e=np.where(lit, 190, 0),
        sp=70)
    put(B_CONC, clean(np.array([140, 138, 132], np.float32)))
    glass = ((xx % 24) < 2) | ((yy % 24) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [70, 74, 80], clean(np.array([84, 110, 130], np.float32))),
        e=np.where(glass, 0, 70), sp=160)
    put(B_RUST, clean(np.array([150, 36, 36], np.float32)), sp=80)                          # Hegemony red
    put(B_SOOT, np.array([62, 60, 64], np.float32) * (0.75 + 0.35 * noise(3)) * (1 - 0.2 * (((yy % 24) < 2) | ((((yy // 24) % 2) * 20 + xx) % 40 < 2)))[..., None])   # dark stone
    tiles = ((yy % 10) < 1.5) | ((((yy // 10) % 2) * 8 + xx) % 16 < 1.5)
    put(B_ROOF, clean(np.array([70, 74, 82], np.float32)) * (1 - 0.25 * tiles[..., None]), sp=110)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 150, 40], [40, 40, 44]) * (0.85 + 0.2 * grime))
    put(B_GLOW, np.array([255, 60, 40], np.float32) * (0.95 + 0.08 * grime), e=255, sp=200)   # the red window
    pad = Image.new("RGB", (t, t), (140, 140, 136))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(150, 36, 36), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_PIPE, np.array([150, 152, 156], np.float32) * (0.8 + 0.3 * grime), sp=110)
    hull = np.array([200, 200, 196], np.float32) * (0.88 + 0.15 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=100)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [150, 150, 150], [50, 52, 56]) * (0.8 + 0.3 * grime), sp=80)
    courses = ((yy % 12) < 2) | ((((yy // 12) % 2) * 12 + xx) % 24 < 2)
    put(B_BRICK, clean(np.array([118, 62, 50], np.float32)) * (1 - 0.3 * courses[..., None]))   # dark brick
    put(B_DUST, np.array([150, 146, 136], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_ciutric", col, emi, spec)


def cestus_atlas():
    """hod_cestus textures (Ord Cestus, the X'Ting droid world; a design choice: red hive clay with lit openings, tan
    plate, red rock and sand, purple fungus caps; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 189)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    dirty = lambda rgb: rgb * (0.82 + 0.2 * grime) * (0.88 + 0.12 * blotch) * (0.9 + 0.12 * streak)
    clay = dirty(np.array([176, 92, 62], np.float32)) * (1 - 0.12 * ((yy % 22) < 2))[..., None]   # banded hive clay
    put(B_PLATE, clay, sp=20)
    holes = (((yy % 30) - 15) ** 2 / 36 + (((xx + 12 * ((yy // 30) % 2)) % 24) - 12) ** 2 / 16) < 1
    lit = holes & (rng.random((t, t)) > 0.3)
    warm = np.array([255, 200, 120], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(holes[..., None], [40, 22, 16], clay)), e=np.where(lit, 200, 0),
        sp=30)
    put(B_CONC, dirty(np.array([188, 164, 130], np.float32)) * (1 - 0.15 * (((yy % 48) < 2) | ((xx % 64) < 2)))[..., None],
        sp=60)
    glass = ((xx % 24) < 2) | ((yy % 24) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [80, 70, 60], dirty(np.array([96, 120, 128], np.float32))),
        e=np.where(glass, 0, 70), sp=160)
    put(B_RUST, dirty(np.array([140, 70, 40], np.float32)), sp=60)
    put(B_SOOT, np.array([150, 74, 50], np.float32) * (0.7 + 0.4 * noise(3)) * (0.88 + 0.18 * noise((20, 1.5))))   # red rock
    put(B_ROOF, dirty(np.array([130, 92, 72], np.float32)), sp=40)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 160, 40], [40, 36, 34]) * (0.85 + 0.2 * grime))
    put(B_GLOW, warm * (1.0 + 0.08 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (170, 140, 110))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(200, 110, 50), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 230, 210), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_PIPE, np.array([160, 150, 140], np.float32) * (0.8 + 0.3 * grime), sp=110)
    hull = np.array([196, 186, 170], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.18 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=100)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [160, 120, 90], [50, 40, 36]) * (0.8 + 0.3 * grime), sp=80)
    put(B_BRICK, np.array([150, 96, 132], np.float32) * (0.75 + 0.35 * noise(1.5)))        # fungus caps
    put(B_DUST, np.array([186, 104, 70], np.float32) * (0.85 + 0.2 * noise(1.5)))          # red sand
    put(B_DARK, np.array([24, 20, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_cestus", col, emi, spec)


def dathomir_atlas():
    """hod_dathomir textures (Dathomir under its red sky: dark red-grey carved stone, openings lit magick green,
    blood-red cloth, dark thatch, bone, grey basalt; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 95)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    dirty = lambda rgb: rgb * (0.78 + 0.25 * grime) * (0.85 + 0.15 * blotch) * (0.9 + 0.12 * streak)
    courses = ((yy % 20) < 2) | ((((yy // 20) % 2) * 18 + xx) % 36 < 2)
    stone = dirty(np.array([124, 96, 92], np.float32)) * (1 - 0.25 * courses)[..., None]
    put(B_PLATE, stone, sp=20)
    holes = ((yy % 40) > 14) & ((yy % 40) < 30) & ((((xx + 16 * ((yy // 40) % 2)) % 32) > 10) & (((xx + 16 * ((yy // 40) % 2)) % 32) < 22))
    green = np.array([150, 255, 120], np.float32)
    put(B_PLATE_WIN, np.where(holes[..., None], green, stone), e=np.where(holes, 230, 0), sp=30)
    put(B_CONC, np.array([92, 90, 94], np.float32) * (0.75 + 0.35 * noise(3)))            # basalt tops
    put(B_CONC_WIN, np.where(holes[..., None], green, stone), e=np.where(holes, 230, 0), sp=30)
    put(B_RUST, dirty(np.array([150, 26, 30], np.float32)), sp=30)                          # blood-red cloth
    put(B_SOOT, np.array([104, 82, 82], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))   # rock
    thatch = (np.sin(xx * 0.9 + 3 * noise(4)[..., 0]) * 0.5 + 0.5)
    put(B_ROOF, np.array([62, 48, 40], np.float32) * (0.75 + 0.35 * thatch)[..., None] * (0.85 + 0.2 * grime))
    put(B_HAZARD, dirty(np.array([150, 26, 30], np.float32)))
    put(B_GLOW, green * (1.0 + 0.05 * grime), e=255, sp=200)
    pad = Image.new("RGB", (t, t), (90, 64, 60))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.1, t * 0.1, t * 0.9, t * 0.9], outline=(150, 26, 30), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    wood = np.array([70, 52, 42], np.float32) * (0.75 + 0.3 * (np.sin(yy * 0.6 + 4 * noise(6)[..., 0]) * 0.5 + 0.5))[..., None]
    put(B_PIPE, wood)
    put(B_HULL, np.array([214, 204, 182], np.float32) * (0.85 + 0.2 * grime), sp=60)       # bone
    put(B_GIRDER, wood)
    blocks = ((yy % 16) < 2) | ((((yy // 16) % 2) * 14 + xx) % 28 < 2)
    put(B_BRICK, np.array([110, 90, 84], np.float32) * (0.7 + 0.4 * noise(2)) * (1 - 0.35 * blocks)[..., None])
    put(B_DUST, np.array([128, 66, 56], np.float32) * (0.85 + 0.2 * noise(1.5)))           # red earth
    put(B_DARK, np.array([18, 12, 12], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_dathomir", col, emi, spec)


def mandalore_atlas():
    """hod_mandalore textures (Sundari's white cube panels with gold lines and glass, its black dome of dark
    transparisteel, Keldabe's granite, stone and timber, slate, clipped greenery, Mandalorian red, Death Watch blue,
    beskar, white sand; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 96)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.9 + 0.1 * grime) * (0.93 + 0.08 * blotch)
    white = clean(np.array([226, 224, 216], np.float32))
    gold = ((yy % 64) < 3) | ((xx % 64) < 3) | (np.abs(((xx + yy) % 64) - 32) < 1.5)
    put(B_PLATE, np.where(gold[..., None], [196, 160, 80], white), sp=90)
    win = ((yy % 24) > 8) & ((yy % 24) < 17) & ((xx % 16) > 3)
    lit = win & (rng.random((t, t)) > 0.4)
    put(B_PLATE_WIN, np.where(lit[..., None], [255, 236, 190], np.where(win[..., None], [60, 84, 96], white)),
        e=np.where(lit, 170, 0), sp=110)
    put(B_CONC, np.array([150, 148, 144], np.float32) * (0.82 + 0.25 * noise(3)))          # granite
    glass = ((xx % 32) < 2) | ((yy % 32) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [196, 160, 80], clean(np.array([150, 196, 200], np.float32))),
        e=np.where(glass, 0, 40), sp=200)
    put(B_RUST, clean(np.array([168, 48, 36], np.float32)), sp=60)                          # Mandalorian red
    put(B_SOOT, np.array([128, 124, 120], np.float32) * (0.7 + 0.4 * noise(3)) * (0.88 + 0.18 * noise((20, 1.5))))
    tiles = ((yy % 10) < 1.5) | ((((yy // 10) % 2) * 8 + xx) % 16 < 1.5)
    put(B_ROOF, clean(np.array([66, 70, 78], np.float32)) * (1 - 0.25 * tiles[..., None]), sp=100)
    sigil = (np.abs(xx - t / 2) < t * 0.06) | ((np.abs(yy - t * 0.35) < t * 0.05) & (np.abs(xx - t / 2) < t * 0.3))
    put(B_HAZARD, np.where(sigil[..., None], [220, 220, 230], [44, 72, 128]) * (0.9 + 0.12 * grime))   # Death Watch
    hedge = (np.abs(np.sin(xx * 0.35)) * np.abs(np.sin(yy * 0.35)) > 0.6)[..., None]          # clipped greenery
    put(B_GLOW, np.array([74, 118, 62], np.float32) * (0.8 + 0.3 * noise(1.5)) * (1 - 0.15 * hedge), sp=20)
    pad = Image.new("RGB", (t, t), (196, 194, 188))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(168, 48, 36), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(250, 250, 250), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.88 + 0.15 * grime))
    frames = (np.abs(((xx + yy * 0.5) % 40) - 20) < 1.5) | ((yy % 34) < 2)                      # Sundari's black dome
    put(B_PIPE, np.where(frames[..., None], [70, 72, 80], [22, 24, 30]) * (0.9 + 0.15 * grime), sp=230)
    put(B_HULL, np.array([156, 166, 180], np.float32) * (0.85 + 0.2 * noise((6, 2))), sp=220)    # beskar
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [206, 170, 90], [120, 100, 60]) * (0.85 + 0.2 * grime), sp=150)   # gold lattice
    beams = ((xx % 40) < 5) | ((yy % 48) < 4)
    courses = ((yy % 14) < 2) | ((((yy // 14) % 2) * 12 + xx) % 24 < 2)
    stone = np.array([150, 140, 124], np.float32) * (0.75 + 0.3 * noise(2)) * (1 - 0.3 * courses)[..., None]
    put(B_BRICK, np.where(beams[..., None], [92, 66, 46], stone))                          # stone and timber
    put(B_DUST, np.array([222, 218, 206], np.float32) * (0.88 + 0.15 * noise(1.5)))        # white sand
    put(B_DARK, np.array([18, 18, 22], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_mandalore", col, emi, spec)


def taris_atlas():
    """hod_taris textures (the rebuilt city-world: pale tower plate and lit window grids, grimy concrete, blue glass,
    container steel in rust and faded colours, cyan neon; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 99)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    clean = lambda rgb: rgb * (0.9 + 0.12 * grime) * (0.93 + 0.08 * blotch)
    dirty = lambda rgb: rgb * (0.75 + 0.28 * grime) * (0.85 + 0.15 * blotch) * (0.85 + 0.18 * streak)
    plate = clean(np.array([186, 200, 208], np.float32)) * (1 - 0.1 * (((yy % 64) < 2) | ((xx % 48) < 2)))[..., None]
    put(B_PLATE, plate, sp=140)                                                # KOTOR's pale blue-grey plate
    lit = ((yy % 12) > 4) & ((yy % 12) < 8) & ((xx % 16) > 3) & ((xx % 16) < 13) & (noise(6)[..., 0] > 0.25)
    put(B_PLATE_WIN, np.where(lit[..., None], [210, 255, 214], [30, 36, 46]), e=np.where(lit, 220, 0), sp=160)
    put(B_CONC, dirty(np.array([130, 126, 118], np.float32)))
    glass = ((xx % 24) < 2) | ((yy % 24) < 2)
    teal = np.array([60, 168, 176], np.float32) * (0.8 + 0.3 * (1 - yy / t))[..., None] * (0.92 + 0.1 * grime)
    put(B_CONC_WIN, np.where(((xx % 32) < 1)[..., None], [120, 210, 216], teal), e=20, sp=230)   # teal glass
    put(B_RUST, dirty(np.array([176, 120, 80], np.float32)) * (1 - 0.2 * ((xx % 10) < 2))[..., None], sp=50)   # tan
    put(B_SOOT, np.array([84, 80, 74], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    put(B_ROOF, clean(np.array([124, 138, 150], np.float32)), sp=90)
    glyph = (((xx // 10) % 3) > 0) & (((yy // 14) % 4) > 0) & (((xx // 40 + yy // 56) % 3) > 0)
    hue = (((yy // 56) % 2) == 0)[..., None]
    neon = np.where(hue, [255, 90, 200], [90, 230, 255])                        # neon signs, magenta and cyan
    put(B_HAZARD, np.where(glyph[..., None], neon, [24, 22, 30]), e=np.where(glyph, 255, 0), sp=200)
    put(B_GLOW, np.array([200, 255, 210], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)   # pale green light
    put(B_PIPE, np.array([150, 150, 154], np.float32) * (0.8 + 0.3 * grime), sp=110)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [150, 150, 154], [44, 46, 50]) * (0.8 + 0.3 * grime), sp=80)
    band = ((yy // 64) % 4).astype(int)
    palette = np.array([[60, 110, 150], [150, 60, 50], [60, 130, 80], [170, 150, 70]], np.float32)
    put(B_BRICK, dirty(palette[band]) * (1 - 0.25 * ((xx % 10) < 2))[..., None], sp=40)    # faded containers
    put(B_DUST, np.array([120, 112, 96], np.float32) * (0.8 + 0.25 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (150, 150, 154))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(230, 190, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 235), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([196, 192, 184], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None], sp=100)
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_taris", col, emi, spec)


def wayland_atlas():
    """hod_wayland textures (timber, dressed stone and fieldstone, shingles, thatch, mountain rock; the grey plate
    and lit bands of the hidden facility; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 97)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.88 + 0.14 * grime) * (0.92 + 0.1 * blotch)
    plate = clean(np.array([118, 122, 128], np.float32)) * (1 - 0.15 * (((yy % 40) < 2) | ((xx % 56) < 2)))[..., None]
    put(B_PLATE, plate, sp=90)
    win = ((yy % 24) > 9) & ((yy % 24) < 16)
    put(B_PLATE_WIN, np.where(win[..., None], [255, 230, 170], plate), e=np.where(win, 200, 0), sp=100)
    courses = ((yy % 18) < 2) | ((((yy // 18) % 2) * 16 + xx) % 32 < 2)
    put(B_CONC, np.array([168, 160, 146], np.float32) * (0.8 + 0.25 * noise(2)) * (1 - 0.25 * courses)[..., None])
    put(B_CONC_WIN, np.where(win[..., None], [255, 230, 170], plate), e=np.where(win, 200, 0), sp=100)
    straw = np.sin(xx * 0.9 + 3 * noise(4)[..., 0]) * 0.5 + 0.5
    put(B_RUST, np.array([168, 140, 86], np.float32) * (0.75 + 0.35 * straw)[..., None] * (0.85 + 0.2 * grime))   # thatch
    put(B_SOOT, np.array([110, 106, 98], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    shing = ((yy % 12) < 2) | ((((yy // 12) % 2) * 10 + xx) % 20 < 1.5)
    put(B_ROOF, clean(np.array([86, 70, 58], np.float32)) * (1 - 0.3 * shing)[..., None])
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [220, 180, 50], [40, 40, 44]) * (0.85 + 0.2 * grime))
    put(B_GLOW, np.array([255, 200, 120], np.float32) * (1.0 + 0.05 * grime), e=255, sp=200)
    wood = np.array([116, 84, 58], np.float32) * (0.75 + 0.3 * (np.sin(yy * 0.7 + 4 * noise(6)[..., 0]) * 0.5 + 0.5))[..., None]
    put(B_GIRDER, wood * (1 - 0.2 * ((xx % 24) < 2))[..., None])
    put(B_PIPE, wood)
    stones = np.sin(xx * 0.35 + 2 * noise(5)[..., 0]) * np.sin(yy * 0.45 + 2 * noise(5)[..., 0]) > 0.75
    put(B_BRICK, np.array([140, 132, 118], np.float32) * (0.75 + 0.35 * noise(1.2)) * (1 - 0.35 * stones)[..., None])
    put(B_DUST, np.array([120, 104, 80], np.float32) * (0.8 + 0.25 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (150, 144, 132))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(220, 180, 50), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 235), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([196, 192, 184], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None], sp=100)
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_wayland", col, emi, spec)


def concordia_atlas():
    """hod_concordia textures (Mandalorian grey plate with red trim, prefab white, the rust of the old mines,
    camouflage netting, Death Watch blue, forest earth; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 1223)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    clean = lambda rgb: rgb * (0.86 + 0.16 * grime) * (0.9 + 0.1 * blotch)
    plate = clean(np.array([140, 144, 150], np.float32)) * (1 - 0.15 * (((yy % 36) < 2) | ((xx % 48) < 2)))[..., None]
    put(B_PLATE, plate, sp=100)
    win = ((yy % 22) > 8) & ((yy % 22) < 15) & ((xx % 14) > 3)
    lit = win & (rng.random((t, t)) > 0.4)
    put(B_PLATE_WIN, np.where(lit[..., None], [255, 230, 180], np.where(win[..., None], [44, 50, 58], plate)),
        e=np.where(lit, 180, 0), sp=110)
    put(B_CONC, clean(np.array([212, 210, 202], np.float32)), sp=60)                     # prefab white
    glass = ((xx % 24) < 2) | ((yy % 24) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [70, 72, 78], clean(np.array([96, 130, 150], np.float32))),
        e=np.where(glass, 0, 60), sp=200)
    put(B_RUST, np.array([140, 70, 42], np.float32) * (0.7 + 0.35 * grime) * (0.85 + 0.2 * streak), sp=40)   # rust, red trim
    put(B_SOOT, np.array([92, 92, 86], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    put(B_ROOF, clean(np.array([70, 74, 80], np.float32)), sp=80)
    sigil = (np.abs(xx - t / 2) < t * 0.06) | ((np.abs(yy - t * 0.35) < t * 0.05) & (np.abs(xx - t / 2) < t * 0.3))
    put(B_HAZARD, np.where(sigil[..., None], [220, 220, 230], [44, 72, 128]) * (0.9 + 0.12 * grime))   # Death Watch
    put(B_GLOW, np.array([255, 220, 150], np.float32) * (1.0 + 0.05 * grime), e=255, sp=200)
    put(B_PIPE, np.array([150, 152, 156], np.float32) * (0.8 + 0.3 * grime), sp=110)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [130, 132, 136], [48, 50, 52]) * (0.8 + 0.3 * grime), sp=80)
    camo = noise(3)[..., 0] > 0.5
    put(B_BRICK, np.where(camo[..., None], [70, 92, 56], [104, 96, 70]) * (0.8 + 0.3 * noise(1)))   # netting
    put(B_DUST, np.array([60, 90, 52], np.float32) * (0.75 + 0.35 * noise(1.5)))          # forest earth, moss
    pad = Image.new("RGB", (t, t), (150, 150, 150))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(140, 70, 42), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 235), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([196, 192, 184], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None], sp=100)
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_concordia", col, emi, spec)


def bracca_atlas():
    """hod_bracca textures (the Scrapper Guild's world: worn steel, stained concrete, rust, Guild yellow, the orange
    glow of cutting torches, slag; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 197)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    dirty = lambda rgb: rgb * (0.72 + 0.3 * grime) * (0.85 + 0.15 * blotch) * (0.85 + 0.18 * streak)
    rust = (noise(4)[..., 0] > 0.55)[..., None]
    plate = np.where(rust, [130, 74, 42], dirty(np.array([140, 140, 136], np.float32))) * (1 - 0.15 * (((yy % 40) < 2) | ((xx % 56) < 2)))[..., None]
    put(B_PLATE, plate, sp=60)
    win = ((yy % 22) > 8) & ((yy % 22) < 15) & ((xx % 14) > 3)
    lit = win & (rng.random((t, t)) > 0.45)
    put(B_PLATE_WIN, np.where(lit[..., None], [255, 214, 150], np.where(win[..., None], [40, 40, 44], plate)),
        e=np.where(lit, 180, 0), sp=70)
    put(B_CONC, dirty(np.array([150, 144, 134], np.float32)))
    put(B_CONC_WIN, np.where(win[..., None], [255, 214, 150], plate), e=np.where(win, 160, 0), sp=70)
    put(B_RUST, np.array([136, 72, 38], np.float32) * (0.65 + 0.4 * noise(3)) * (0.85 + 0.2 * streak), sp=30)
    put(B_SOOT, np.array([70, 64, 58], np.float32) * (0.7 + 0.4 * noise(3)))                    # slag
    put(B_ROOF, dirty(np.array([96, 92, 88], np.float32)), sp=50)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [232, 184, 40], [36, 34, 32]) * (0.75 + 0.3 * grime))           # Guild yellow
    put(B_GLOW, np.array([255, 150, 60], np.float32) * (1.0 + 0.05 * grime), e=255, sp=200)     # cutting torches
    put(B_PIPE, np.array([140, 136, 130], np.float32) * (0.75 + 0.3 * grime), sp=90)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [160, 120, 60], [44, 40, 36]) * (0.75 + 0.3 * grime), sp=70)
    put(B_BRICK, dirty(np.array([120, 112, 100], np.float32)))
    put(B_DUST, np.array([132, 116, 96], np.float32) * (0.8 + 0.25 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (140, 136, 128))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(232, 184, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 235), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([176, 170, 160], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None], sp=100)
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_bracca", col, emi, spec)


def trandosha_atlas():
    """hod_trandosha textures (battered stone, dark metal roofs, scale-green plate, tanned hide, bone, dark wood, fire;
    the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 119)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.85 + 0.16 * grime) * (0.9 + 0.12 * blotch)
    scales = ((((yy // 10) % 2) * 8 + xx) % 16 - 8) ** 2 / 64 + ((yy % 10) - 5) ** 2 / 25 < 0.8
    put(B_PLATE, clean(np.array([86, 110, 70], np.float32)) * (0.8 + 0.25 * scales)[..., None], sp=60)   # scale plate
    slit = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 20) > 7) & ((xx % 20) < 12)
    stone = np.array([132, 120, 100], np.float32) * (0.75 + 0.3 * noise(2))
    frame = ((xx % 16) < 3) | ((yy % 20) < 3) | ((yy % 64) > 52)                # timber frame round paper screens
    paper = (np.array([255, 226, 170], np.float32) * (0.92 + 0.08 * noise(3)))
    put(B_PLATE_WIN, np.where(frame[..., None], [58, 40, 30], paper), e=np.where(frame, 0, 150), sp=20)
    put(B_CONC, stone)
    put(B_CONC_WIN, np.where(slit[..., None], [255, 180, 90], stone), e=np.where(slit, 220, 0))
    put(B_RUST, np.array([168, 128, 82], np.float32) * (0.8 + 0.25 * noise(1.5)))              # tanned hide
    put(B_SOOT, np.array([104, 96, 86], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    tiles = ((yy % 10) < 2) | ((xx % 12) < 2)
    put(B_ROOF, clean(np.array([60, 66, 64], np.float32)) * (1 - 0.35 * tiles)[..., None], sp=110)   # roof tiles
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.array([196, 52, 34], np.float32) * (0.9 + 0.12 * grime), sp=120)       # vermilion lacquer
    put(B_GLOW, np.array([255, 160, 70], np.float32) * (1.0 + 0.05 * grime), e=255, sp=200)     # fire
    wood = np.array([84, 62, 44], np.float32) * (0.75 + 0.3 * (np.sin(yy * 0.7 + 4 * noise(6)[..., 0]) * 0.5 + 0.5))[..., None]
    put(B_GIRDER, wood)
    put(B_PIPE, np.array([120, 112, 100], np.float32) * (0.8 + 0.3 * grime), sp=90)
    blocks = ((yy % 20) < 2) | ((((yy // 20) % 2) * 18 + xx) % 36 < 2)
    put(B_BRICK, np.array([140, 126, 104], np.float32) * (0.72 + 0.35 * noise(2)) * (1 - 0.35 * blocks)[..., None])
    put(B_DUST, np.array([138, 116, 80], np.float32) * (0.8 + 0.25 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (140, 130, 110))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(170, 60, 30), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 235), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([222, 212, 188], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None], sp=100)
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_trandosha", col, emi, spec)


def nyriaan_atlas():
    """hod_nyriaan textures (a tropical mining frontier: ochre plaster, corrugated metal, rust, timber, Guild orange,
    CIS hull plate, red earth; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 98)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    dirty = lambda rgb: rgb * (0.78 + 0.25 * grime) * (0.86 + 0.14 * blotch) * (0.88 + 0.15 * streak)
    plaster = dirty(np.array([196, 164, 112], np.float32))
    put(B_PLATE, plaster, sp=20)
    win = ((yy % 26) > 9) & ((yy % 26) < 18) & ((xx % 18) > 5) & ((xx % 18) < 13)
    put(B_PLATE_WIN, np.where(win[..., None], [255, 214, 140], plaster), e=np.where(win, 190, 0), sp=30)
    put(B_CONC, dirty(np.array([150, 144, 134], np.float32)))
    put(B_CONC_WIN, np.where(win[..., None], [255, 214, 140], plaster), e=np.where(win, 190, 0))
    corr = np.sin(xx * 0.8) * 0.5 + 0.5
    put(B_ROOF, np.array([126, 138, 130], np.float32) * (0.7 + 0.3 * corr)[..., None] * (0.85 + 0.2 * grime), sp=120)
    put(B_RUST, np.array([140, 76, 40], np.float32) * (0.7 + 0.35 * noise(3)) * (0.85 + 0.2 * streak), sp=30)
    put(B_SOOT, np.array([112, 100, 86], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [232, 130, 40], [40, 36, 32]) * (0.85 + 0.2 * grime))         # Guild orange
    put(B_GLOW, np.array([255, 230, 170], np.float32) * (1.0 + 0.05 * grime), e=255, sp=200)
    wood = np.array([110, 80, 54], np.float32) * (0.75 + 0.3 * (np.sin(yy * 0.7 + 4 * noise(6)[..., 0]) * 0.5 + 0.5))[..., None]
    put(B_GIRDER, wood)
    put(B_BRICK, dirty(np.array([150, 96, 70], np.float32)))
    put(B_DUST, np.array([150, 100, 68], np.float32) * (0.8 + 0.25 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (140, 130, 116))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(232, 130, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 235), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([150, 140, 120], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None], sp=100)
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_PIPE, np.array([140, 138, 134], np.float32) * (0.8 + 0.3 * grime), sp=90)
    _atlas_save("hod_nyriaan", col, emi, spec)


def corsin_atlas():
    """hod_corsin textures (a Republic island resort world: white stucco, terracotta tiles, teal glazed domes, timber
    decking, pale stone, sea-blue pool tile, sand, the selligore's grey-blue hide; the map is always day)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 100)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.92 + 0.08 * grime) * (0.94 + 0.07 * blotch)
    stucco = clean(np.array([236, 232, 220], np.float32))
    put(B_PLATE, stucco, sp=30)
    win = ((yy % 28) > 10) & ((yy % 28) < 20) & ((xx % 18) > 6) & ((xx % 18) < 12)
    put(B_PLATE_WIN, np.where(win[..., None], [60, 90, 110], stucco), sp=40)
    put(B_CONC, clean(np.array([214, 204, 182], np.float32)))
    glaze = np.array([70, 170, 170], np.float32) * (0.85 + 0.2 * noise(3))
    put(B_CONC_WIN, glaze * (1 - 0.15 * ((yy % 16) < 2))[..., None], sp=220)                   # teal domes
    tiles = ((yy % 10) < 2) | ((((yy // 10) % 2) * 6 + xx) % 12 < 1.5)
    put(B_ROOF, clean(np.array([186, 96, 62], np.float32)) * (1 - 0.25 * tiles)[..., None], sp=60)   # terracotta
    put(B_RUST, np.array([96, 112, 128], np.float32) * (0.8 + 0.25 * noise(4)), sp=200)         # selligore hide
    put(B_SOOT, np.array([112, 106, 96], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [200, 60, 50], [236, 232, 220]))
    put(B_GLOW, np.array([255, 236, 180], np.float32) * (1.0 + 0.05 * grime), e=255, sp=200)
    deck = np.array([150, 112, 76], np.float32) * (0.8 + 0.25 * (np.sin(xx * 0.5 + 2 * noise(6)[..., 0]) * 0.5 + 0.5))[..., None]
    put(B_GIRDER, deck * (1 - 0.25 * ((yy % 12) < 1.5))[..., None])
    put(B_BRICK, np.array([70, 150, 190], np.float32) * (0.85 + 0.2 * noise(3)), sp=220)        # pool tile
    put(B_DUST, np.array([226, 206, 160], np.float32) * (0.88 + 0.15 * noise(1.5)))            # sand
    pad = Image.new("RGB", (t, t), (214, 210, 200))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(186, 96, 62), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 235), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([232, 230, 224], np.float32) * (0.85 + 0.18 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None], sp=100)
    put(B_DARK, np.array([18, 18, 20], np.float32) * (0.8 + 0.4 * grime))
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_PIPE, np.array([140, 138, 134], np.float32) * (0.8 + 0.3 * grime), sp=90)
    _atlas_save("hod_corsin", col, emi, spec)


def kashyyyk_atlas():
    """hod_kashyyyk textures (Wookiee building: wroshyr bark, woven wood walls with lit windows, dark timber roofing,
    timber and rope, canopy leaves, worked metal, Republic white and red; the map is always day: lights are painted
    bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 117)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.86 + 0.16 * grime) * (0.9 + 0.12 * blotch)
    grain = np.sin(xx * 0.35 + 6 * noise(5)[..., 0]) * 0.5 + 0.5
    bark = np.array([110, 80, 56], np.float32) * (0.65 + 0.4 * grain)[..., None] * (0.85 + 0.2 * grime)
    put(B_PLATE, bark)
    weave = ((((xx // 8) + (yy // 8)) % 2) * 0.2 + 0.8)
    wall = np.array([150, 112, 72], np.float32) * weave[..., None] * (0.85 + 0.2 * grime)
    win = ((yy % 30) > 11) & ((yy % 30) < 21) & ((xx % 22) > 7) & ((xx % 22) < 15)
    put(B_PLATE_WIN, np.where(win[..., None], [255, 206, 130], wall), e=np.where(win, 200, 0))
    put(B_CONC, clean(np.array([150, 144, 130], np.float32)))
    put(B_CONC_WIN, np.where(win[..., None], [160, 200, 220], np.array([220, 222, 226], np.float32)), sp=120)
    planks = (yy % 9) < 1.5
    put(B_ROOF, np.array([86, 62, 44], np.float32) * (0.7 + 0.3 * grain)[..., None] * (1 - 0.3 * planks)[..., None])
    put(B_RUST, clean(np.array([120, 110, 96], np.float32)) * (1 - 0.15 * ((yy % 24) < 2))[..., None], sp=90)
    put(B_SOOT, np.array([86, 82, 74], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    put(B_HAZARD, np.array([170, 40, 36], np.float32) * (0.9 + 0.12 * grime), sp=90)            # Republic red
    put(B_GLOW, np.array([255, 210, 140], np.float32) * (1.0 + 0.05 * grime), e=255, sp=200)
    put(B_GIRDER, np.array([128, 96, 64], np.float32) * (0.7 + 0.35 * grain)[..., None])
    put(B_PIPE, np.array([130, 124, 116], np.float32) * (0.8 + 0.3 * grime), sp=90)
    put(B_BRICK, np.array([62, 104, 50], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.25 * noise(1)))   # leaves
    put(B_DUST, np.array([196, 180, 140], np.float32) * (0.85 + 0.2 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (150, 140, 120))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(170, 40, 36), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([224, 222, 216], np.float32) * (0.88 + 0.14 * grime) * (1 - 0.15 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None], sp=110)
    put(B_DARK, np.array([22, 20, 18], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_kashyyyk", col, emi, spec)


def onderon_atlas():
    """hod_onderon textures (Iziz: tan stone with lit windows, great wall blocks, slate and teal-patina domes, logs,
    ochre cloth, royal blue and gold; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 116)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    dirty = lambda rgb: rgb * (0.82 + 0.2 * grime) * (0.88 + 0.12 * blotch) * (0.9 + 0.12 * streak)
    courses = ((yy % 22) < 2) | ((((yy // 22) % 2) * 20 + xx) % 40 < 2)
    stone = dirty(np.array([188, 168, 134], np.float32)) * (1 - 0.18 * courses)[..., None]
    put(B_PLATE, stone, sp=20)
    win = ((yy % 32) > 12) & ((yy % 32) < 24) & ((xx % 22) > 8) & ((xx % 22) < 14)
    put(B_PLATE_WIN, np.where(win[..., None], [255, 214, 150], stone), e=np.where(win, 190, 0), sp=30)
    put(B_CONC, dirty(np.array([170, 158, 136], np.float32)))
    put(B_CONC_WIN, np.where(win[..., None], [255, 214, 150], stone), e=np.where(win, 190, 0))
    patina = np.where((noise(4)[..., 0] > 0.45)[..., None], [86, 140, 128], [92, 96, 104]).astype(np.float32)
    put(B_ROOF, patina * (0.8 + 0.25 * grime) * (1 - 0.2 * ((yy % 12) < 2))[..., None], sp=90)   # slate, patina
    put(B_RUST, dirty(np.array([196, 140, 60], np.float32)), sp=30)                         # ochre cloth
    put(B_SOOT, np.array([110, 104, 94], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    band = ((yy % 64) < 10)[..., None]
    put(B_HAZARD, np.where(band, [212, 176, 70], [40, 64, 140]) * (0.9 + 0.12 * grime), sp=80)   # royal colours
    put(B_GLOW, np.array([255, 200, 120], np.float32) * (1.0 + 0.05 * grime), e=255, sp=200)
    logs = np.array([112, 84, 58], np.float32) * (0.72 + 0.32 * (np.sin(yy * 0.5 + 3 * noise(6)[..., 0]) * 0.5 + 0.5))[..., None]
    put(B_GIRDER, logs * (1 - 0.3 * ((xx % 18) < 2))[..., None])
    put(B_PIPE, np.array([130, 124, 116], np.float32) * (0.8 + 0.3 * grime), sp=90)
    blocks = ((yy % 40) < 3) | ((((yy // 40) % 2) * 36 + xx) % 72 < 3)
    put(B_BRICK, dirty(np.array([168, 150, 120], np.float32)) * (1 - 0.3 * blocks)[..., None])    # wall blocks
    put(B_DUST, np.array([120, 104, 80], np.float32) * (0.8 + 0.25 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (160, 150, 130))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(40, 64, 140), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_HULL, np.array([58, 104, 50], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.25 * noise(1)))   # leaves
    put(B_DARK, np.array([22, 20, 18], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_onderon", col, emi, spec)


def umbara_atlas():
    """hod_umbara textures (the shadow world: dark blue-grey plate with cyan window lines, black roofs, cyan and violet
    light, pale fighter grey, the old dark stone and red glow of the Sith ruins; the map is always day: lights are
    painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 120)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.85 + 0.16 * grime) * (0.9 + 0.12 * blotch)
    plate = clean(np.array([52, 58, 72], np.float32)) * (1 - 0.2 * (((yy % 40) < 2) | ((xx % 28) < 2)))[..., None]
    put(B_PLATE, plate, sp=160)
    lines = ((yy % 18) < 3) & ((xx % 40) > 6)
    put(B_PLATE_WIN, np.where(lines[..., None], [110, 230, 255], plate), e=np.where(lines, 230, 0), sp=170)
    put(B_CONC, clean(np.array([60, 62, 70], np.float32)))
    put(B_CONC_WIN, np.where(lines[..., None], [110, 230, 255], plate), e=np.where(lines, 230, 0))
    put(B_ROOF, clean(np.array([28, 30, 38], np.float32)), sp=200)
    put(B_GLOW, np.array([110, 230, 255], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)   # cyan light
    put(B_HAZARD, np.array([190, 110, 255], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200) # violet light
    put(B_HULL, clean(np.array([150, 156, 168], np.float32)) * (1 - 0.15 * ((yy % 24) < 2))[..., None], sp=150)
    blocks = ((yy % 24) < 2) | ((((yy // 24) % 2) * 20 + xx) % 40 < 2)
    put(B_BRICK, np.array([58, 52, 56], np.float32) * (0.7 + 0.4 * noise(2)) * (1 - 0.35 * blocks)[..., None])  # Sith stone
    put(B_RUST, np.array([255, 60, 50], np.float32) * (0.95 + 0.05 * grime), e=255, sp=200)    # red glow
    put(B_SOOT, np.array([40, 44, 46], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    put(B_DUST, np.array([46, 50, 48], np.float32) * (0.8 + 0.25 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (60, 64, 74))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(110, 230, 255), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_DARK, np.array([14, 14, 16], np.float32) * (0.8 + 0.4 * grime))
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 110, 116], [30, 30, 34]) * (0.8 + 0.3 * grime), sp=80)
    put(B_PIPE, np.array([120, 120, 126], np.float32) * (0.8 + 0.3 * grime), sp=110)
    _atlas_save("hod_umbara", col, emi, spec)


def colla_atlas():
    """hod_colla textures (the Colicoid spawnworld: ribbed chitin with amber-lit openings, dark glossy shell plate,
    pale egg ivory, amber light, murky spawning water, droideka bronze, red earth; the map is always day)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 118)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.85 + 0.16 * grime) * (0.9 + 0.12 * blotch)
    ribs = np.sin(xx * 0.4) * 0.5 + 0.5
    chitin = clean(np.array([150, 104, 60], np.float32)) * (0.75 + 0.3 * ribs)[..., None]
    put(B_PLATE, chitin, sp=120)
    holes = (((yy % 34) - 17) ** 2 / 49 + (((xx + 14 * ((yy // 34) % 2)) % 28) - 14) ** 2 / 25) < 1
    put(B_PLATE_WIN, np.where(holes[..., None], [255, 180, 70], chitin), e=np.where(holes, 220, 0), sp=120)
    put(B_CONC, clean(np.array([150, 128, 100], np.float32)))
    put(B_CONC_WIN, np.array([60, 84, 60], np.float32) * (0.8 + 0.3 * noise(3)), sp=220)       # spawning water
    segs = ((yy % 20) < 3)
    put(B_ROOF, clean(np.array([84, 56, 40], np.float32)) * (1 - 0.35 * segs)[..., None], sp=230)   # shell plate
    put(B_HULL, clean(np.array([220, 210, 170], np.float32)), sp=120)                        # egg ivory
    put(B_GLOW, np.array([255, 180, 70], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)  # amber
    put(B_HAZARD, np.array([255, 180, 70], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)
    put(B_RUST, clean(np.array([150, 112, 70], np.float32)) * (1 - 0.2 * ((xx % 16) < 2))[..., None], sp=150)   # bronze
    put(B_SOOT, np.array([104, 80, 60], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    put(B_BRICK, chitin)
    put(B_DUST, np.array([150, 90, 60], np.float32) * (0.8 + 0.25 * noise(1.5)))              # red earth
    pad = Image.new("RGB", (t, t), (150, 128, 100))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(255, 180, 70), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_DARK, np.array([14, 14, 16], np.float32) * (0.8 + 0.4 * grime))
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 110, 116], [30, 30, 34]) * (0.8 + 0.3 * grime), sp=80)
    put(B_PIPE, np.array([120, 120, 126], np.float32) * (0.8 + 0.3 * grime), sp=110)
    _atlas_save("hod_colla", col, emi, spec)


def ruusan_atlas():
    """hod_ruusan textures (the light-side mirror of Korriban: pale Jedi stone with gold-lit windows, verdigris copper
    roofs, gold and blue light, tan fieldstone, weathered canvas, charred stone, brown canyon rock; the map is always
    day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 65)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.85 + 0.16 * grime) * (0.9 + 0.12 * blotch)
    courses = ((yy % 32) < 2) | ((((yy // 32) % 2) * 24 + xx) % 48 < 2)
    stone = clean(np.array([226, 220, 202], np.float32)) * (1 - 0.18 * courses)[..., None]
    put(B_PLATE, stone, sp=90)
    win = ((yy % 40) > 12) & ((yy % 40) < 34) & ((xx % 24) > 8) & ((xx % 24) < 16)
    put(B_PLATE_WIN, np.where(win[..., None], [255, 214, 120], stone), e=np.where(win, 210, 0), sp=100)
    put(B_CONC, clean(np.array([196, 178, 140], np.float32)))
    put(B_CONC_WIN, np.array([70, 110, 120], np.float32) * (0.8 + 0.3 * noise(3)), sp=220)
    seams = (xx % 20) < 2
    put(B_ROOF, clean(np.array([96, 150, 128], np.float32)) * (1 - 0.25 * seams)[..., None], sp=150)   # verdigris
    put(B_GLOW, np.array([255, 214, 120], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)   # gold light
    put(B_HAZARD, np.array([120, 200, 255], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200) # blue light
    put(B_HULL, clean(np.array([200, 188, 160], np.float32)) * (1 - 0.15 * ((yy % 26) < 2))[..., None], sp=110)
    blocks = ((yy % 22) < 2) | ((((yy // 22) % 2) * 18 + xx) % 36 < 2)
    put(B_BRICK, np.array([176, 150, 112], np.float32) * (0.75 + 0.35 * noise(2)) * (1 - 0.3 * blocks)[..., None])
    put(B_RUST, np.array([46, 40, 36], np.float32) * (0.7 + 0.5 * noise(3)))                     # charred stone
    put(B_SOOT, np.array([128, 98, 70], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    put(B_DUST, np.array([140, 116, 80], np.float32) * (0.8 + 0.25 * noise(1.5)))
    pad = Image.new("RGB", (t, t), (196, 178, 140))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(255, 214, 120), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_DARK, np.array([14, 14, 16], np.float32) * (0.8 + 0.4 * grime))
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 100, 84], [44, 38, 30]) * (0.8 + 0.3 * grime), sp=80)
    put(B_PIPE, np.array([120, 112, 100], np.float32) * (0.8 + 0.3 * grime), sp=110)
    _atlas_save("hod_ruusan", col, emi, spec)

def boz_atlas():
    """hod_bozpity textures (Boz Pity: Separatist bronze-grey plate with amber window slots and blue-grey roofs, amber
    and Separatist-blue lights, battle-droid tan; the Gargantelles' carved sandstone and bone; canyon rock, sand and
    still dark water; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 73)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.85 + 0.16 * grime) * (0.9 + 0.12 * blotch)
    panels = ((yy % 36) < 2) | ((xx % 52) < 2)
    plate = clean(np.array([128, 116, 100], np.float32)) * (1 - 0.2 * panels)[..., None]
    put(B_PLATE, plate, sp=120)
    win = ((yy % 36) > 14) & ((yy % 36) < 22) & ((xx % 26) > 6) & ((xx % 26) < 20)
    put(B_PLATE_WIN, np.where(win[..., None], [255, 190, 96], plate), e=np.where(win, 210, 0), sp=130)
    put(B_CONC, clean(np.array([168, 150, 120], np.float32)))
    put(B_CONC_WIN, np.array([44, 58, 60], np.float32) * (0.85 + 0.25 * noise(4)), sp=220)          # still water
    seams = (xx % 22) < 2
    put(B_ROOF, clean(np.array([84, 96, 114], np.float32)) * (1 - 0.25 * seams)[..., None], sp=150)  # blue-grey
    put(B_GLOW, np.array([255, 186, 90], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)         # amber light
    put(B_HAZARD, np.array([110, 170, 255], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)      # Separatist blue
    put(B_HULL, clean(np.array([206, 182, 132], np.float32)), sp=110)                               # droid tan
    blocks = ((yy % 22) < 2) | ((((yy // 22) % 2) * 18 + xx) % 36 < 2)
    carve = (np.abs(np.sin(xx * 0.4) * np.sin(yy * 0.25)) > 0.85) & ((yy % 66) > 44)                # relief bands
    put(B_BRICK, np.array([176, 160, 128], np.float32) * (0.75 + 0.35 * noise(2)) *
        (1 - 0.3 * blocks - 0.18 * carve)[..., None])                                                # Gargantelle stone
    put(B_RUST, np.array([226, 216, 190], np.float32) * (0.82 + 0.22 * noise(3)))                   # bone
    put(B_SOOT, np.array([142, 108, 82], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    put(B_DUST, np.array([196, 172, 126], np.float32) * (0.82 + 0.22 * noise(1.5)))                 # sand
    pad = Image.new("RGB", (t, t), (150, 136, 112))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(110, 170, 255), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_DARK, np.array([14, 14, 16], np.float32) * (0.8 + 0.4 * grime))
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 104, 96], [40, 38, 36]) * (0.8 + 0.3 * grime), sp=80)
    put(B_PIPE, np.array([120, 114, 106], np.float32) * (0.8 + 0.3 * grime), sp=110)
    _atlas_save("hod_bozpity", col, emi, spec)

def ithor_atlas():
    """hod_ithor textures (Ithor's herdships: sage living hull plates with warm round windows, wooden decking, falling
    water, leafy canopy, rust-hued bushes, pink and blue blooms, repulsor glow, vines, pale stone, moss; the map is
    always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 102)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.86 + 0.15 * grime) * (0.9 + 0.12 * blotch)
    seams = (np.abs(np.sin(xx * 0.09 + np.sin(yy * 0.05) * 2)) < 0.06) | ((yy % 46) < 2)
    hull = clean(np.array([196, 198, 168], np.float32)) * (1 - 0.2 * seams)[..., None]
    put(B_PLATE, hull, sp=70)
    win = ((xx % 28 - 14) ** 2 + (yy % 30 - 15) ** 2) < 36
    put(B_PLATE_WIN, np.where(win[..., None], [255, 220, 150], hull), e=np.where(win, 200, 0), sp=80)
    planks = ((yy % 12) < 1.5) | ((((yy // 12) % 3) * 30 + xx) % 90 < 1.5)
    put(B_CONC, np.array([150, 116, 80], np.float32) * (0.8 + 0.3 * noise(2)) * (1 - 0.25 * planks)[..., None])
    streak = noise((24, 1.2))
    put(B_CONC_WIN, np.array([150, 200, 220], np.float32) * (0.75 + 0.35 * streak), sp=220)          # falling water
    put(B_RUST, np.array([170, 96, 58], np.float32) * (0.75 + 0.4 * noise(1.5)))                     # rust bushes
    put(B_SOOT, np.array([92, 86, 76], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    put(B_ROOF, np.array([64, 122, 58], np.float32) * (0.7 + 0.45 * noise(1.2)))                     # canopy
    bloom = noise(1.5)
    put(B_HAZARD, np.where(bloom > 0.5, [226, 128, 196], [108, 140, 232]) * (0.85 + 0.2 * grime))     # blooms
    put(B_GLOW, np.array([200, 236, 255], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)        # repulsors
    pad = Image.new("RGB", (t, t), (170, 168, 146))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(96, 140, 80), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.88 + 0.15 * grime))
    put(B_PIPE, np.array([96, 80, 58], np.float32) * (0.75 + 0.35 * noise((16, 1.5))))              # vines, roots
    put(B_HULL, clean(np.array([112, 120, 104], np.float32)) * (1 - 0.15 * seams)[..., None], sp=90)
    lattice = ((np.abs(((xx + yy) % 40) - 20) < 3) | (np.abs(((xx - yy) % 40) - 20) < 3))[..., None]
    put(B_GIRDER, np.where(lattice, [150, 120, 84], [60, 80, 50]) * (0.85 + 0.2 * grime))
    courses = ((yy % 20) < 2) | ((((yy // 20) % 2) * 16 + xx) % 32 < 2)
    put(B_BRICK, np.array([236, 234, 222], np.float32) * (0.85 + 0.15 * noise(2)) * (1 - 0.12 * courses)[..., None])
    put(B_DUST, np.array([96, 130, 70], np.float32) * (0.75 + 0.35 * noise(1.5)))                    # moss
    put(B_DARK, np.array([18, 20, 18], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_ithor", col, emi, spec)

def ordmantell_atlas():
    """hod_ordmantell textures (Ord Mantell: weathered tan-pink stucco with lit windows, dusty concrete, Corellian
    blue glass, red-brown roofs and brick, rusted scrap, coal and grime, casino neon, amber light and lava, starship
    hull, yellow crane lattice, arid sand; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 103)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.82 + 0.2 * grime) * (0.88 + 0.15 * blotch)
    stucco = clean(np.array([200, 166, 146], np.float32)) * (1 - 0.15 * ((yy % 40) < 2))[..., None]
    put(B_PLATE, stucco, sp=30)
    win = ((yy % 28) > 10) & ((yy % 28) < 20) & ((xx % 20) > 5) & ((xx % 20) < 14)
    lit = win & (rng.random((t, t)) > 0.5)
    put(B_PLATE_WIN, np.where(lit[..., None], [255, 214, 150], np.where(win[..., None], [60, 56, 60], stucco)),
        e=np.where(lit, 180, 0), sp=40)
    put(B_CONC, clean(np.array([164, 154, 142], np.float32)))
    glass = ((xx % 30) < 2) | ((yy % 24) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [90, 80, 74], clean(np.array([96, 140, 176], np.float32))), sp=200)
    put(B_RUST, np.array([132, 76, 46], np.float32) * (0.65 + 0.5 * noise(2)))                      # scrap
    put(B_SOOT, np.array([72, 66, 62], np.float32) * (0.7 + 0.45 * noise(3)))                       # grime, coal
    tiles = ((yy % 10) < 1.5) | ((((yy // 10) % 2) * 8 + xx) % 16 < 1.5)
    put(B_ROOF, clean(np.array([138, 74, 58], np.float32)) * (1 - 0.2 * tiles[..., None]), sp=60)    # red-brown
    neon = ((yy % 16) < 6)[..., None]
    put(B_HAZARD, np.where(neon, [255, 80, 210], [80, 220, 255]) * (1.0 + 0.04 * grime), e=255, sp=200)   # neon
    put(B_GLOW, np.array([255, 150, 60], np.float32) * (0.9 + 0.2 * noise(2)), e=255, sp=200)       # amber, lava
    pad = Image.new("RGB", (t, t), (150, 144, 136))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(230, 190, 60), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(B_PIPE, np.array([140, 140, 140], np.float32) * (0.75 + 0.35 * grime), sp=110)
    panels = ((yy % 34) < 2) | ((xx % 48) < 2)
    put(B_HULL, clean(np.array([196, 196, 190], np.float32)) * (1 - 0.2 * panels)[..., None], sp=120)
    lattice = ((np.abs(((xx + yy) % 40) - 20) < 3) | (np.abs(((xx - yy) % 40) - 20) < 3) | ((yy % 40) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [220, 180, 50], [70, 60, 40]) * (0.85 + 0.2 * grime), sp=80)
    courses = ((yy % 14) < 2) | ((((yy // 14) % 2) * 12 + xx) % 24 < 2)
    put(B_BRICK, np.array([150, 92, 72], np.float32) * (0.78 + 0.3 * noise(2)) * (1 - 0.25 * courses)[..., None])
    put(B_DUST, np.array([204, 172, 132], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([16, 16, 18], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_ordmantell", col, emi, spec)

def garqi_atlas():
    """hod_garqi textures (Garqi: cream stone with tall windows, pale paving, greenhouse glass, barn red, grey bluff
    rock, blue-grey slate, the native plants' purple, warm light, silo metal, freighter hull, lattice, brick, green
    crop rows; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 104)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.88 + 0.12 * grime) * (0.92 + 0.1 * blotch)
    stone = clean(np.array([228, 220, 200], np.float32)) * (1 - 0.1 * ((yy % 36) < 2))[..., None]
    put(B_PLATE, stone, sp=40)
    win = ((yy % 40) > 8) & ((yy % 40) < 30) & ((xx % 22) > 7) & ((xx % 22) < 14)
    put(B_PLATE_WIN, np.where(win[..., None], [70, 84, 100], stone), sp=60)
    put(B_CONC, clean(np.array([196, 190, 176], np.float32)))
    glass = ((xx % 26) < 2) | ((yy % 26) < 2)
    put(B_CONC_WIN, np.where(glass[..., None], [220, 220, 210], clean(np.array([150, 204, 196], np.float32))), sp=220)
    put(B_RUST, clean(np.array([152, 58, 44], np.float32)) * (1 - 0.2 * ((xx % 18) < 2))[..., None])   # barn red
    put(B_SOOT, np.array([120, 112, 116], np.float32) * (0.7 + 0.4 * noise(3)) * (0.85 + 0.2 * noise((20, 1.5))))
    tiles = ((yy % 10) < 1.5) | ((((yy // 10) % 2) * 8 + xx) % 16 < 1.5)
    put(B_ROOF, clean(np.array([84, 98, 120], np.float32)) * (1 - 0.2 * tiles[..., None]), sp=80)       # slate
    put(B_HAZARD, np.array([136, 72, 152], np.float32) * (0.7 + 0.45 * noise(1.2)))                 # purple plants
    put(B_GLOW, np.array([255, 224, 160], np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)
    pad = Image.new("RGB", (t, t), (180, 176, 164))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(136, 72, 152), width=int(t * 0.05))
    put(B_PAD, np.asarray(pad, np.float32) * (0.88 + 0.15 * grime))
    put(B_PIPE, clean(np.array([180, 182, 184], np.float32)) * (1 - 0.15 * ((yy % 30) < 2))[..., None], sp=140)
    panels = ((yy % 34) < 2) | ((xx % 48) < 2)
    put(B_HULL, clean(np.array([186, 180, 166], np.float32)) * (1 - 0.2 * panels)[..., None], sp=120)
    lattice = ((np.abs(((xx + yy) % 40) - 20) < 3) | (np.abs(((xx - yy) % 40) - 20) < 3) | ((yy % 40) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [190, 186, 176], [70, 70, 66]) * (0.85 + 0.2 * grime), sp=80)
    courses = ((yy % 14) < 2) | ((((yy // 14) % 2) * 12 + xx) % 24 < 2)
    put(B_BRICK, np.array([166, 100, 74], np.float32) * (0.8 + 0.3 * noise(2)) * (1 - 0.25 * courses)[..., None])
    rows = (np.abs(np.sin(xx * 0.4)) > 0.5)[..., None]
    put(B_DUST, np.where(rows, [96, 140, 64], [128, 108, 70]) * (0.85 + 0.2 * noise(1.5)))           # crop rows
    put(B_DARK, np.array([16, 16, 18], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_garqi", col, emi, spec)

def _atlas_generic(name, seed, c, lit_rgb=(255, 220, 160)):
    """a planet atlas from a colour table c (B_ cell -> rgb or (rgb, kind)); kinds: 'win' lit window slots over the
    plate colour, 'glass' framed glass, 'tiles' roof tiles, 'courses' stone courses, 'glow' emissive, 'lattice' truss,
    'pad' landing pad ring, 'noise' plain mottled; the map is always day: lights are painted bright"""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, seed)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: np.array(rgb, np.float32) * (0.84 + 0.18 * grime) * (0.9 + 0.12 * blotch)
    for cell, spec_ in c.items():
        rgb, kind = spec_ if isinstance(spec_[0], (tuple, list)) else (spec_, "noise")
        if kind == "win":
            base = clean(c[B_PLATE] if not isinstance(c[B_PLATE][0], (tuple, list)) else c[B_PLATE][0])
            win = ((yy % 28) > 10) & ((yy % 28) < 20) & ((xx % 20) > 5) & ((xx % 20) < 14)
            LIT_RGB, lit = lit_rgb, win & (rng.random((t, t)) > 0.45)
            put(cell, np.where(lit[..., None], list(LIT_RGB), np.where(win[..., None], rgb, base)),
                e=np.where(lit, 170, 0), sp=60)
        elif kind == "glass":
            fr = ((xx % 30) < 2) | ((yy % 24) < 2)
            put(cell, np.where(fr[..., None], [90, 90, 90], clean(rgb)), sp=200)
        elif kind == "tiles":
            tl = ((yy % 10) < 1.5) | ((((yy // 10) % 2) * 8 + xx) % 16 < 1.5)
            put(cell, clean(rgb) * (1 - 0.22 * tl[..., None]), sp=70)
        elif kind == "courses":
            cr = ((yy % 16) < 2) | ((((yy // 16) % 2) * 14 + xx) % 28 < 2)
            put(cell, np.array(rgb, np.float32) * (0.78 + 0.3 * noise(2)) * (1 - 0.25 * cr)[..., None])
        elif kind == "glyphs":
            cr = ((yy % 24) < 2) | ((xx % 36) < 2) | ((np.abs(np.sin(xx * 0.5) * np.sin(yy * 0.3)) > 0.9) & ((yy % 48) > 30))
            put(cell, np.array(rgb, np.float32) * (0.8 + 0.3 * noise(2)) * (1 - 0.3 * cr)[..., None])
        elif kind == "glow":
            put(cell, np.array(rgb, np.float32) * (1.0 + 0.04 * grime), e=255, sp=200)
        elif kind == "lattice":
            lt = ((np.abs(((xx + yy) % 40) - 20) < 3) | (np.abs(((xx - yy) % 40) - 20) < 3) | ((yy % 40) < 4))[..., None]
            put(cell, np.where(lt, rgb, [50, 50, 50]) * (0.85 + 0.2 * grime), sp=80)
        elif kind == "pad":
            pad = Image.new("RGB", (t, t), tuple(int(v) for v in rgb[0]))
            d = ImageDraw.Draw(pad)
            d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=tuple(int(v) for v in rgb[1]), width=int(t * 0.05))
            put(cell, np.asarray(pad, np.float32) * (0.88 + 0.15 * grime))
        elif kind == "plates":
            pl = ((yy % 34) < 2) | ((xx % 48) < 2)
            put(cell, clean(rgb) * (1 - 0.2 * pl)[..., None], sp=120)
        else:
            put(cell, np.array(rgb, np.float32) * (0.8 + 0.3 * noise(1.5)))
    _atlas_save(name, col, emi, spec)


def agamar_atlas():
    """hod_agamar textures (Agamar: cream sandstone, terracotta, sea-blue shell roofs, sea water, dark Rakatan stone
    with glyphs, dry earth)."""
    _atlas_generic("hod_agamar", 107, {
        B_PLATE: ((214, 196, 160), "courses"), B_PLATE_WIN: ((70, 80, 90), "win"), B_CONC: (196, 180, 150),
        B_CONC_WIN: ((90, 150, 160), "glass"), B_RUST: ((178, 98, 64), "tiles"), B_SOOT: (96, 84, 74),
        B_ROOF: ((72, 124, 146), "tiles"), B_HAZARD: (92, 128, 66), B_GLOW: ((255, 220, 150), "glow"),
        B_PAD: (((180, 170, 150), (178, 98, 64)), "pad"), B_PIPE: (150, 150, 150), B_HULL: ((196, 192, 182), "plates"),
        B_GIRDER: ((170, 150, 110), "lattice"), B_BRICK: ((74, 68, 76), "glyphs"), B_DUST: (184, 150, 104),
        B_DARK: (16, 16, 18)})


def ordtrasi_atlas():
    """hod_ordtrasi textures (Ord Trasi: Republic military grey-white plate, red markings, ferrocrete, dark roofing,
    hazard stripes, gantry lattice, raw durasteel ribs, starship hull, dusty ground)."""
    _atlas_generic("hod_ordtrasi", 108, {
        B_PLATE: ((200, 200, 196), "plates"), B_PLATE_WIN: ((50, 60, 70), "win"), B_CONC: (150, 148, 142),
        B_CONC_WIN: ((90, 130, 170), "glass"), B_RUST: (170, 50, 40), B_SOOT: (88, 78, 70),
        B_ROOF: ((74, 76, 80), "tiles"), B_HAZARD: ((230, 190, 40), "lattice"), B_GLOW: ((150, 210, 255), "glow"),
        B_PAD: (((160, 160, 156), (230, 190, 40)), "pad"), B_PIPE: (140, 140, 142), B_HULL: ((206, 206, 200), "plates"),
        B_GIRDER: ((150, 150, 156), "lattice"), B_BRICK: ((120, 116, 110), "plates"), B_DUST: (170, 152, 124),
        B_DARK: (16, 16, 18)})


def dantooine_atlas():
    """hod_dantooine textures (Dantooine: KOTOR's tan Jedi stone, slate-green roofs, weathered ochre, scorched stone,
    dark Rakatan stone with glowing orange lines, grass and earth)."""
    _atlas_generic("hod_dantooine", 110, {
        B_PLATE: ((206, 186, 148), "courses"), B_PLATE_WIN: ((70, 76, 80), "win"), B_CONC: (190, 178, 150),
        B_CONC_WIN: ((110, 160, 190), "glass"), B_RUST: (176, 140, 88), B_SOOT: (70, 64, 58),
        B_ROOF: ((92, 118, 100), "tiles"), B_HAZARD: ((255, 150, 60), "glow"), B_GLOW: ((255, 224, 160), "glow"),
        B_PAD: (((176, 166, 140), (92, 118, 100)), "pad"), B_PIPE: (150, 150, 150), B_HULL: ((196, 192, 182), "plates"),
        B_GIRDER: ((160, 150, 120), "lattice"), B_BRICK: ((66, 60, 60), "glyphs"), B_DUST: (118, 150, 92),
        B_DARK: (16, 16, 18)})

def dubrillion_atlas():
    """hod_dubrillion textures (Dubrillion: white plascrete towers with blue-lit windows, teal roofs, aqua glass and
    water, emerald shark-tank water, coral, sandstone, sand)."""
    _atlas_generic("hod_dubrillion", 111, {
        B_PLATE: ((232, 232, 228), "plates"), B_PLATE_WIN: ((60, 110, 150), "win"), B_CONC: (210, 204, 190),
        B_CONC_WIN: ((120, 200, 210), "glass"), B_RUST: (230, 120, 100), B_SOOT: (100, 96, 90),
        B_ROOF: ((60, 150, 150), "tiles"), B_HAZARD: (40, 150, 110), B_GLOW: ((255, 230, 170), "glow"),
        B_PAD: (((200, 200, 196), (60, 150, 150)), "pad"), B_PIPE: (170, 170, 172), B_HULL: ((220, 220, 214), "plates"),
        B_GIRDER: ((190, 190, 186), "lattice"), B_BRICK: ((206, 186, 150), "courses"), B_DUST: (226, 210, 170),
        B_DARK: (16, 16, 18)})


def bastion_atlas():
    """hod_bastion textures (Bastion: grey dressed granite, dark slate, Braxant red banners, pale paving, blue glass)."""
    _atlas_generic("hod_bastion", 112, {
        B_PLATE: ((150, 150, 154), "courses"), B_PLATE_WIN: ((50, 56, 66), "win"), B_CONC: (186, 184, 178),
        B_CONC_WIN: ((90, 120, 160), "glass"), B_RUST: (156, 36, 36), B_SOOT: (70, 70, 74),
        B_ROOF: ((64, 70, 82), "tiles"), B_HAZARD: ((220, 180, 40), "lattice"), B_GLOW: ((255, 220, 160), "glow"),
        B_PAD: (((160, 160, 160), (156, 36, 36)), "pad"), B_PIPE: (150, 150, 154), B_HULL: ((206, 206, 200), "plates"),
        B_GIRDER: ((150, 150, 156), "lattice"), B_BRICK: ((128, 128, 134), "courses"), B_DUST: (120, 112, 96),
        B_DARK: (16, 16, 18)})


def kalee_atlas():
    """hod_kalee textures (Kalee: ochre carved stone, Kaleesh red, bone white, moss green, dark rock, fire)."""
    _atlas_generic("hod_kalee", 113, {
        B_PLATE: ((176, 140, 96), "glyphs"), B_PLATE_WIN: ((40, 30, 26), "win"), B_CONC: (170, 150, 116),
        B_CONC_WIN: ((70, 120, 120), "glass"), B_RUST: ((150, 46, 36), "courses"), B_SOOT: (78, 70, 62),
        B_ROOF: (76, 112, 58), B_HAZARD: ((255, 140, 50), "glow"), B_GLOW: ((255, 200, 120), "glow"),
        B_PAD: (((160, 140, 110), (150, 46, 36)), "pad"), B_PIPE: (130, 126, 120), B_HULL: ((190, 184, 172), "plates"),
        B_GIRDER: ((150, 130, 100), "lattice"), B_BRICK: ((232, 224, 204), "noise"), B_DUST: (150, 124, 90),
        B_DARK: (14, 12, 12)})


def muunilinst_atlas():
    """hod_muunilinst textures (Muunilinst: pearl-white panels with gold-lit windows, gold crowns, IBC crimson, blue
    glass, dark volcanic rock, lava, dark Damask stone, track sand)."""
    _atlas_generic("hod_muunilinst", 115, {
        B_PLATE: ((236, 234, 228), "plates"), B_PLATE_WIN: ((90, 110, 140), "win"), B_CONC: (214, 210, 200),
        B_CONC_WIN: ((110, 160, 210), "glass"), B_RUST: (150, 30, 40), B_SOOT: (60, 54, 52),
        B_ROOF: ((214, 176, 80), "plates"), B_HAZARD: ((255, 120, 40), "glow"), B_GLOW: ((255, 230, 170), "glow"),
        B_PAD: (((200, 198, 190), (214, 176, 80)), "pad"), B_PIPE: (196, 198, 204), B_HULL: ((220, 218, 210), "plates"),
        B_GIRDER: ((200, 190, 160), "lattice"), B_BRICK: ((50, 46, 56), "plates"), B_DUST: (190, 160, 110),
        B_DARK: (16, 16, 18)})


def mygeeto_atlas():
    """hod_mygeeto textures (Mygeeto: dark blue-grey metal with cool-lit windows, packed ice, crystal glass and glow, IBC
    crimson, Geonosian ochre stone, dark slate, glacier ice, snow)."""
    _atlas_generic("hod_mygeeto", 109, {
        B_PLATE: ((62, 70, 84), "plates"), B_PLATE_WIN: ((40, 46, 58), "win"), B_CONC: (226, 234, 242),
        B_CONC_WIN: ((150, 220, 240), "glass"), B_RUST: (150, 30, 40), B_SOOT: ((150, 110, 70), "noise"),
        B_ROOF: ((44, 50, 60), "plates"), B_HAZARD: ((140, 230, 255), "glow"), B_GLOW: ((255, 230, 170), "glow"),
        B_PAD: (((90, 96, 108), (140, 230, 255)), "pad"), B_PIPE: (150, 156, 166), B_HULL: ((206, 206, 200), "plates"),
        B_GIRDER: ((90, 96, 108), "lattice"), B_BRICK: ((176, 206, 230), "noise"), B_DUST: (236, 240, 246),
        B_DARK: (16, 16, 18)})


def yagaminor_atlas():
    """hod_yaga_minor textures (Yaga Minor: ochre hive resin with amber-lit cells, honeycomb, moss, Republic white and
    red, blue glass, drive-blue glow, dark earth)."""
    _atlas_generic("hod_yaga_minor", 114, {
        B_PLATE: ((176, 146, 96), "noise"), B_PLATE_WIN: ((120, 92, 54), "win"), B_CONC: (226, 224, 216),
        B_CONC_WIN: ((90, 130, 170), "glass"), B_RUST: (150, 40, 36), B_SOOT: (60, 50, 40),
        B_ROOF: ((80, 110, 60), "noise"), B_HAZARD: ((120, 190, 255), "glow"), B_GLOW: ((255, 190, 100), "glow"),
        B_PAD: (((170, 160, 140), (150, 40, 36)), "pad"), B_PIPE: (150, 150, 154), B_HULL: ((210, 206, 196), "plates"),
        B_GIRDER: ((150, 150, 154), "lattice"), B_BRICK: ((196, 160, 90), "tiles"), B_DUST: (120, 100, 70),
        B_DARK: (16, 16, 18)})


def ansion_atlas():
    """hod_ansion textures (Ansion: sandstone, whitewash, terracotta, red and blue cloth, dark felt, weathered wood,
    foliage green, dressed stone, trodden earth)."""
    _atlas_generic("hod_ansion", 106, {
        B_PLATE: ((206, 176, 130), "courses"), B_PLATE_WIN: ((226, 220, 204), "win"), B_CONC: (236, 232, 220),
        B_CONC_WIN: ((90, 140, 180), "glass"), B_RUST: ((170, 50, 40), "lattice"), B_SOOT: ((92, 80, 68), "noise"),
        B_ROOF: ((186, 96, 60), "tiles"), B_HAZARD: ((50, 90, 150), "lattice"), B_GLOW: ((255, 200, 120), "glow"),
        B_PAD: (((180, 170, 150), (170, 50, 40)), "pad"), B_PIPE: (120, 92, 64), B_HULL: ((206, 200, 192), "plates"),
        B_GIRDER: ((92, 126, 60), "noise"), B_BRICK: ((176, 150, 110), "courses"), B_DUST: (170, 150, 112),
        B_DARK: (16, 16, 18)})


def ilum_atlas():
    """hod_ilum textures (Ilum: ancient grey Jedi stone, packed snow, ice, kyber blue glow, Republic red and old
    plating, dark rock, weathered bronze, glacier ice, snow)."""
    _atlas_generic("hod_ilum", 181, {
        B_PLATE: ((150, 152, 156), "courses"), B_PLATE_WIN: ((120, 122, 128), "win"), B_CONC: (236, 240, 246),
        B_CONC_WIN: ((170, 220, 245), "glass"), B_RUST: (150, 40, 36), B_SOOT: ((70, 74, 82), "noise"),
        B_ROOF: ((120, 100, 70), "plates"), B_HAZARD: ((120, 200, 255), "glow"), B_GLOW: ((255, 230, 170), "glow"),
        B_PAD: (((190, 194, 200), (150, 40, 36)), "pad"), B_PIPE: (130, 134, 140), B_HULL: ((176, 178, 176), "plates"),
        B_GIRDER: ((130, 134, 140), "lattice"), B_BRICK: ((186, 214, 236), "noise"), B_DUST: (238, 242, 248),
        B_DARK: (16, 16, 18)})


def dorin_atlas():
    """hod_dorin textures (Dorin: dark basalt with amber-lit windows, pale paving, amber glass and glow, rust-orange
    cloth, soot-dark stone, copper, kand green, coursed stone, dusty earth)."""
    _atlas_generic("hod_dorin", 105, {
        B_PLATE: ((70, 66, 64), "plates"), B_PLATE_WIN: ((56, 52, 50), "win"), B_CONC: (176, 166, 150),
        B_CONC_WIN: ((210, 150, 70), "glass"), B_RUST: (180, 90, 40), B_SOOT: ((48, 44, 42), "noise"),
        B_ROOF: ((166, 104, 66), "plates"), B_HAZARD: ((255, 170, 60), "glow"), B_GLOW: ((255, 200, 120), "glow"),
        B_PAD: (((120, 112, 104), (255, 170, 60)), "pad"), B_PIPE: (150, 120, 90), B_HULL: ((180, 170, 160), "plates"),
        B_GIRDER: ((96, 112, 54), "noise"), B_BRICK: ((96, 88, 80), "courses"), B_DUST: (130, 110, 86),
        B_DARK: (14, 12, 12)})


def yinchorr_atlas():
    """hod_yinchorr textures (Yinchorr: ochre sandstone with slit windows, pale paving, Republic glass and white plates,
    red cloth, weathered dark stone, green-bronze scales, hazard yellow, fire, grey metal, coursed sandstone, bone)."""
    _atlas_generic("hod_yinchorr", 159, {
        B_PLATE: ((176, 120, 76), "plates"), B_PLATE_WIN: ((160, 108, 68), "win"), B_CONC: (206, 182, 140),
        B_CONC_WIN: ((150, 200, 230), "glass"), B_RUST: (160, 38, 30), B_SOOT: ((92, 70, 54), "noise"),
        B_ROOF: ((82, 112, 76), "plates"), B_HAZARD: ((236, 186, 40), "plates"), B_GLOW: ((255, 150, 60), "glow"),
        B_PAD: (((196, 196, 192), (160, 38, 30)), "pad"), B_PIPE: (128, 130, 132), B_HULL: ((226, 224, 216), "plates"),
        B_GIRDER: ((120, 122, 124), "lattice"), B_BRICK: ((168, 116, 74), "courses"), B_DUST: (226, 214, 186),
        B_DARK: (16, 12, 10)})


def chandrila_atlas():
    """hod_chandrila textures (Chandrila: cream stone with tall windows, pale paving, blue glass, blue banners, grey
    stone, patina roofs, gold trim, warm light, white plates, grey metal, garden green, sandy courses, pale rock)."""
    _atlas_generic("hod_chandrila", 187, {
        B_PLATE: ((228, 222, 204), "plates"), B_PLATE_WIN: ((220, 214, 196), "win"), B_CONC: (214, 210, 196),
        B_CONC_WIN: ((120, 180, 220), "glass"), B_RUST: (54, 92, 156), B_SOOT: ((108, 108, 104), "noise"),
        B_ROOF: ((92, 150, 132), "plates"), B_HAZARD: ((220, 180, 80), "plates"), B_GLOW: ((255, 220, 150), "glow"),
        B_PAD: (((200, 200, 196), (54, 92, 156)), "pad"), B_PIPE: (140, 142, 146), B_HULL: ((232, 232, 228), "plates"),
        B_GIRDER: ((72, 124, 60), "noise"), B_BRICK: ((196, 180, 148), "courses"), B_DUST: (176, 170, 160),
        B_DARK: (10, 12, 16)})


def corulag_atlas():
    """hod_corulag textures (Corulag: steel and blue glass, white paving, Sienar red, slate, bamboo green)."""
    _atlas_generic("hod_corulag", 146, {
        B_PLATE: ((150, 154, 160), "plates"), B_PLATE_WIN: ((120, 126, 136), "win"), B_CONC: (220, 220, 214),
        B_CONC_WIN: ((90, 150, 200), "glass"), B_RUST: (150, 40, 36), B_SOOT: ((62, 64, 70), "noise"),
        B_ROOF: ((84, 88, 96), "plates"), B_HAZARD: ((230, 190, 50), "plates"), B_GLOW: ((250, 245, 230), "glow"),
        B_PAD: (((180, 182, 186), (230, 190, 50)), "pad"), B_PIPE: (130, 134, 140), B_HULL: ((228, 230, 232), "plates"),
        B_GIRDER: ((96, 134, 60), "noise"), B_BRICK: ((196, 192, 182), "courses"), B_DUST: (150, 130, 100),
        B_DARK: (12, 12, 14)})


def arkania_atlas():
    """hod_arkania textures (Arkania: white stone, ice-blue glass, Adasca violet, silver, diamond glint, snow)."""
    _atlas_generic("hod_arkania", 148, {
        B_PLATE: ((226, 230, 236), "plates"), B_PLATE_WIN: ((210, 218, 228), "win"), B_CONC: (236, 240, 244),
        B_CONC_WIN: ((150, 200, 240), "glass"), B_RUST: (110, 70, 140), B_SOOT: ((70, 72, 80), "noise"),
        B_ROOF: ((180, 186, 196), "plates"), B_HAZARD: ((230, 245, 255), "glow"), B_GLOW: ((255, 220, 170), "glow"),
        B_PAD: (((200, 204, 210), (110, 70, 140)), "pad"), B_PIPE: (130, 134, 140), B_HULL: ((236, 238, 240), "plates"),
        B_GIRDER: ((120, 124, 130), "lattice"), B_BRICK: ((210, 212, 216), "courses"), B_DUST: (240, 244, 248),
        B_DARK: (10, 12, 16)})


def anaxes_atlas():
    """hod_anaxes textures (Anaxes: Republic grey and white, red bands, concrete, red rock and earth)."""
    _atlas_generic("hod_anaxes", 133, {
        B_PLATE: ((140, 142, 146), "plates"), B_PLATE_WIN: ((130, 132, 138), "win"), B_CONC: (176, 174, 168),
        B_CONC_WIN: ((100, 150, 200), "glass"), B_RUST: (170, 36, 32), B_SOOT: ((90, 50, 44), "noise"),
        B_ROOF: ((70, 72, 78), "plates"), B_HAZARD: ((230, 190, 50), "plates"), B_GLOW: ((250, 245, 230), "glow"),
        B_PAD: (((176, 176, 176), (170, 36, 32)), "pad"), B_PIPE: (128, 130, 134), B_HULL: ((224, 224, 220), "plates"),
        B_GIRDER: ((120, 122, 126), "lattice"), B_BRICK: ((150, 120, 100), "courses"), B_DUST: (150, 80, 60),
        B_DARK: (12, 12, 14)})


def carida_atlas():
    """hod_carida textures (Carida: tan durasteel with lit windows, pale stone, blue glass, Republic red, dark rock, slate roofs, conifer green, sandstone courses, desert sand)."""
    _atlas_generic("hod_carida", 164, {
        B_PLATE: ((176, 160, 132), "plates"), B_PLATE_WIN: ((160, 146, 120), "win"), B_CONC: (214, 206, 188),
        B_CONC_WIN: ((100, 150, 200), "glass"), B_RUST: (164, 38, 32), B_SOOT: ((86, 78, 70), "noise"),
        B_ROOF: ((88, 90, 96), "plates"), B_HAZARD: ((230, 190, 50), "plates"), B_GLOW: ((255, 226, 160), "glow"),
        B_PAD: (((180, 176, 168), (164, 38, 32)), "pad"), B_PIPE: (130, 130, 132), B_HULL: ((228, 226, 220), "plates"),
        B_GIRDER: ((56, 88, 60), "noise"), B_BRICK: ((172, 150, 118), "courses"), B_DUST: (200, 172, 126),
        B_DARK: (12, 12, 12)})


def balmorra_atlas():
    """hod_balmorra textures (Balmorra: grey-brown plate with lit windows, dusty concrete, amber glass, rust, soot, dark steel, furnace glow, Techno Union blue-grey hulls, rusty lattice, ochre stone, ochre dust)."""
    _atlas_generic("hod_balmorra", 16, {
        B_PLATE: ((128, 118, 106), "plates"), B_PLATE_WIN: ((114, 106, 96), "win"), B_CONC: (170, 156, 136),
        B_CONC_WIN: ((210, 160, 80), "glass"), B_RUST: (150, 76, 40), B_SOOT: ((58, 52, 48), "noise"),
        B_ROOF: ((76, 78, 82), "plates"), B_HAZARD: ((226, 180, 46), "plates"), B_GLOW: ((255, 150, 60), "glow"),
        B_PAD: (((150, 144, 134), (226, 180, 46)), "pad"), B_PIPE: (120, 116, 110), B_HULL: ((150, 160, 172), "plates"),
        B_GIRDER: ((120, 70, 42), "lattice"), B_BRICK: ((176, 136, 96), "courses"), B_DUST: (184, 144, 98),
        B_DARK: (12, 10, 10)})


def alderaan_atlas():
    """hod_alderaan textures (Alderaan: white synthstone with tall windows, pale paving, pale blue glass, royal blue, grey stone, slate blue-green roofs, gold trim, warm light, garden green, cream stone courses, earth)."""
    _atlas_generic("hod_alderaan", 6, {
        B_PLATE: ((232, 232, 228), "plates"), B_PLATE_WIN: ((222, 224, 222), "win"), B_CONC: (214, 212, 204),
        B_CONC_WIN: ((140, 190, 222), "glass"), B_RUST: (52, 82, 152), B_SOOT: ((112, 114, 116), "noise"),
        B_ROOF: ((90, 122, 132), "plates"), B_HAZARD: ((212, 182, 92), "plates"), B_GLOW: ((255, 228, 170), "glow"),
        B_PAD: (((204, 204, 200), (52, 82, 152)), "pad"), B_PIPE: (140, 142, 146), B_HULL: ((236, 240, 242), "noise"),
        B_GIRDER: ((70, 130, 64), "noise"), B_BRICK: ((202, 194, 174), "courses"), B_DUST: (134, 112, 88),
        B_DARK: (12, 12, 14)})


def tython_atlas():
    """hod_tython textures (Tython, abandoned: pale weathered stone with empty windows, weathered paving, old blue glass, bronze, dark stone, slate, faded gold, pale light, bleached stone, black durasteel, moss, stone courses, earth)."""
    _atlas_generic("hod_tython", 8, {
        B_PLATE: ((188, 180, 160), "plates"), B_PLATE_WIN: ((170, 162, 144), "win"), B_CONC: (176, 170, 156),
        B_CONC_WIN: ((90, 130, 150), "glass"), B_RUST: (140, 104, 60), B_SOOT: ((88, 86, 80), "noise"),
        B_ROOF: ((86, 90, 92), "plates"), B_HAZARD: ((180, 160, 100), "plates"), B_GLOW: ((236, 236, 220), "glow"),
        B_PAD: (((176, 170, 156), (140, 104, 60)), "pad"), B_PIPE: (34, 34, 38), B_HULL: ((212, 206, 190), "plates"),
        B_GIRDER: ((78, 108, 60), "noise"), B_BRICK: ((166, 156, 134), "courses"), B_DUST: (120, 104, 82),
        B_DARK: (12, 12, 12)})


def fresia_atlas():
    """hod_fresia textures (Fresia: Incom white plate with lit windows, pale aprons, blue glass, Incom orange-red, dark rock, dark grey roofs, yellow, white light, white hull, metal, grey lattice, grey stone, wet sand)."""
    _atlas_generic("hod_fresia", 9, {
        B_PLATE: ((226, 228, 230), "plates"), B_PLATE_WIN: ((210, 214, 218), "win"), B_CONC: (196, 198, 196),
        B_CONC_WIN: ((100, 150, 200), "glass"), B_RUST: (200, 80, 44), B_SOOT: ((70, 72, 74), "noise"),
        B_ROOF: ((70, 74, 80), "plates"), B_HAZARD: ((226, 190, 60), "plates"), B_GLOW: ((250, 248, 236), "glow"),
        B_PAD: (((196, 198, 196), (200, 80, 44)), "pad"), B_PIPE: (130, 134, 140), B_HULL: ((236, 238, 240), "plates"),
        B_GIRDER: ((120, 124, 128), "noise"), B_BRICK: ((150, 150, 148), "courses"), B_DUST: (150, 140, 120),
        B_DARK: (12, 12, 12)})


def foerost_atlas():
    """hod_foerost textures (Foerost: Techno Union blue-grey plate with lit windows, grey concrete, pale green glass, rust, soot, dark steel, yellow, white light, pale hull, metal, old girders, grey stone, earth)."""
    _atlas_generic("hod_foerost", 10, {
        B_PLATE: ((120, 128, 140), "plates"), B_PLATE_WIN: ((106, 114, 126), "win"), B_CONC: (160, 158, 152),
        B_CONC_WIN: ((140, 190, 170), "glass"), B_RUST: (146, 80, 46), B_SOOT: ((56, 56, 60), "noise"),
        B_ROOF: ((66, 70, 78), "plates"), B_HAZARD: ((226, 186, 50), "plates"), B_GLOW: ((250, 246, 230), "glow"),
        B_PAD: (((160, 158, 152), (226, 186, 50)), "pad"), B_PIPE: (122, 124, 128), B_HULL: ((190, 196, 204), "plates"),
        B_GIRDER: ((96, 88, 80), "noise"), B_BRICK: ((140, 138, 134), "courses"), B_DUST: (120, 104, 84),
        B_DARK: (12, 12, 12)})


def corellia_atlas():
    """hod_corellia textures (Corellia: bronze-gold plate with lit windows, weathered paving, amber glass, Corellian red, soot, dark bronze, yellow, amber light, pale hull, metal, green, sandstone courses, earth)."""
    _atlas_generic("hod_corellia", 22, {
        B_PLATE: ((170, 140, 96), "plates"), B_PLATE_WIN: ((150, 124, 86), "win"), B_CONC: (170, 162, 148),
        B_CONC_WIN: ((220, 170, 90), "glass"), B_RUST: (168, 46, 36), B_SOOT: ((60, 54, 50), "noise"),
        B_ROOF: ((96, 74, 52), "plates"), B_HAZARD: ((226, 186, 50), "plates"), B_GLOW: ((255, 200, 120), "glow"),
        B_PAD: (((170, 162, 148), (226, 186, 50)), "pad"), B_PIPE: (130, 126, 120), B_HULL: ((214, 208, 196), "plates"),
        B_GIRDER: ((74, 112, 60), "noise"), B_BRICK: ((176, 150, 112), "courses"), B_DUST: (120, 100, 78),
        B_DARK: (12, 12, 12)})


def kuat_atlas():
    """hod_kuat textures (Kuat: ivory with lit windows, pale paving, blue glass, KDY crimson, grey stone, slate blue, gold trim, warm light, white hull, metal, garden green, cream stone courses, earth)."""
    _atlas_generic("hod_kuat", 15, {
        B_PLATE: ((228, 224, 212), "plates"), B_PLATE_WIN: ((214, 210, 198), "win"), B_CONC: (206, 202, 190),
        B_CONC_WIN: ((120, 170, 210), "glass"), B_RUST: (150, 40, 44), B_SOOT: ((110, 110, 108), "noise"),
        B_ROOF: ((84, 100, 120), "plates"), B_HAZARD: ((214, 182, 96), "plates"), B_GLOW: ((255, 230, 180), "glow"),
        B_PAD: (((206, 202, 190), (150, 40, 44)), "pad"), B_PIPE: (140, 142, 146), B_HULL: ((238, 238, 234), "plates"),
        B_GIRDER: ((64, 124, 62), "noise"), B_BRICK: ((204, 196, 176), "courses"), B_DUST: (130, 110, 86),
        B_DARK: (12, 12, 12)})


def rendilli_atlas():
    """hod_rendili textures (Rendili: StarDrive grey plate with lit windows, pale paving, blue glass, StarDrive orange, dark grey, navy, yellow, ion blue-white light, pale hull, metal, green, grey stone courses, earth)."""
    _atlas_generic("hod_rendili", 23, {
        B_PLATE: ((146, 150, 156), "plates"), B_PLATE_WIN: ((130, 134, 142), "win"), B_CONC: (176, 176, 172),
        B_CONC_WIN: ((110, 160, 210), "glass"), B_RUST: (214, 110, 40), B_SOOT: ((58, 60, 64), "noise"),
        B_ROOF: ((44, 56, 84), "plates"), B_HAZARD: ((226, 186, 50), "plates"), B_GLOW: ((200, 230, 255), "glow"),
        B_PAD: (((176, 176, 172), (214, 110, 40)), "pad"), B_PIPE: (130, 132, 136), B_HULL: ((212, 214, 218), "plates"),
        B_GIRDER: ((74, 116, 60), "noise"), B_BRICK: ((150, 150, 148), "courses"), B_DUST: (120, 104, 84),
        B_DARK: (12, 12, 12)})


def commenor_atlas():
    """hod_commenor textures (Commenor: sandstone with lit windows, pale paving, teal glass, Commenor blue, dark stone, terracotta, gold, warm light, white, metal, green, stone courses, sand)."""
    _atlas_generic("hod_commenor", 17, {
        B_PLATE: ((206, 180, 140), "plates"), B_PLATE_WIN: ((190, 166, 128), "win"), B_CONC: (214, 206, 190),
        B_CONC_WIN: ((90, 176, 170), "glass"), B_RUST: (50, 90, 150), B_SOOT: ((86, 80, 72), "noise"),
        B_ROOF: ((176, 96, 60), "plates"), B_HAZARD: ((214, 182, 96), "plates"), B_GLOW: ((255, 226, 170), "glow"),
        B_PAD: (((214, 206, 190), (50, 90, 150)), "pad"), B_PIPE: (136, 136, 134), B_HULL: ((236, 232, 224), "plates"),
        B_GIRDER: ((72, 124, 62), "noise"), B_BRICK: ((186, 164, 130), "courses"), B_DUST: (196, 170, 124),
        B_DARK: (12, 12, 12)})


def duro_atlas():
    """hod_duro textures (Duro: Duros blue-grey plate with lit windows, grimy concrete, pale blue glass, rust, soot, dark grey, yellow, sickly green light, pale hull, metal, dead green, old stone courses, ash)."""
    _atlas_generic("hod_duro", 20, {
        B_PLATE: ((112, 124, 136), "plates"), B_PLATE_WIN: ((98, 110, 122), "win"), B_CONC: (140, 136, 128),
        B_CONC_WIN: ((140, 180, 210), "glass"), B_RUST: (136, 76, 44), B_SOOT: ((52, 52, 52), "noise"),
        B_ROOF: ((62, 66, 72), "plates"), B_HAZARD: ((220, 180, 50), "plates"), B_GLOW: ((170, 240, 120), "glow"),
        B_PAD: (((140, 136, 128), (220, 180, 50)), "pad"), B_PIPE: (120, 122, 124), B_HULL: ((178, 186, 192), "plates"),
        B_GIRDER: ((88, 96, 66), "noise"), B_BRICK: ((130, 122, 110), "courses"), B_DUST: (120, 112, 102),
        B_DARK: (12, 12, 12)})


def loronar_atlas():
    """hod_loronar textures (Loronar: white plate with lit windows, pale paving, pale green glass, Loronar green, dark grey, slate green, yellow, pale green light, white hull, metal, forest green, grey stone courses, earth)."""
    _atlas_generic("hod_loronar", 21, {
        B_PLATE: ((224, 228, 226), "plates"), B_PLATE_WIN: ((206, 212, 210), "win"), B_CONC: (200, 202, 196),
        B_CONC_WIN: ((150, 210, 180), "glass"), B_RUST: (40, 130, 90), B_SOOT: ((60, 62, 62), "noise"),
        B_ROOF: ((70, 96, 86), "plates"), B_HAZARD: ((226, 190, 60), "plates"), B_GLOW: ((190, 255, 220), "glow"),
        B_PAD: (((200, 202, 196), (40, 130, 90)), "pad"), B_PIPE: (134, 138, 140), B_HULL: ((238, 240, 238), "plates"),
        B_GIRDER: ((52, 110, 60), "noise"), B_BRICK: ((150, 152, 148), "courses"), B_DUST: (120, 104, 84),
        B_DARK: (12, 12, 12)})


def neimodia_atlas():
    """hod_neimoidia textures (Neimoidia: Trade Federation khaki plate with lit windows, tan paving, green-grey glass, red-brown, dark brown, dark khaki, orange, amber light, pale tan hull, metal, jungle green, sandstone, sand)."""
    _atlas_generic("hod_neimoidia", 19, {
        B_PLATE: ((176, 156, 114), "plates"), B_PLATE_WIN: ((160, 140, 102), "win"), B_CONC: (190, 176, 146),
        B_CONC_WIN: ((120, 150, 130), "glass"), B_RUST: (130, 60, 40), B_SOOT: ((70, 54, 40), "noise"),
        B_ROOF: ((120, 104, 74), "plates"), B_HAZARD: ((220, 130, 40), "plates"), B_GLOW: ((255, 200, 110), "glow"),
        B_PAD: (((190, 176, 146), (220, 130, 40)), "pad"), B_PIPE: (130, 126, 118), B_HULL: ((214, 204, 180), "plates"),
        B_GIRDER: ((70, 104, 44), "noise"), B_BRICK: ((180, 156, 116), "courses"), B_DUST: (200, 172, 124),
        B_DARK: (12, 12, 12)})


def mimban_atlas():
    """hod_mimban textures (Mimban: grey prefab plate with lit windows, mud-stained concrete, dim glass, rust, black volcanic stone, reed thatch, yellow, crimson crystal light, pale hull, metal, swamp wood, dark stone, mud)."""
    _atlas_generic("hod_mimban", 28, {
        B_PLATE: ((132, 136, 132), "plates"), B_PLATE_WIN: ((116, 120, 116), "win"), B_CONC: (120, 110, 96),
        B_CONC_WIN: ((110, 130, 130), "glass"), B_RUST: (130, 70, 44), B_SOOT: ((34, 32, 32), "noise"),
        B_ROOF: ((136, 118, 76), "plates"), B_HAZARD: ((220, 180, 50), "plates"), B_GLOW: ((255, 80, 70), "glow"),
        B_PAD: (((120, 110, 96), (220, 180, 50)), "pad"), B_PIPE: (120, 122, 124), B_HULL: ((190, 194, 190), "plates"),
        B_GIRDER: ((92, 76, 54), "noise"), B_BRICK: ((84, 80, 76), "courses"), B_DUST: (96, 84, 66),
        B_DARK: (12, 12, 12)})


def manaan_atlas():
    """hod_manaan textures (Manaan: Ahto white plate with lit windows, pale decks, blue glass, Selkath teal, dark grey, pale blue-grey, yellow, pale blue light, white hull, metal, kelp green, grey courses, wet sand)."""
    _atlas_generic("hod_manaan", 18, {
        B_PLATE: ((228, 232, 234), "plates"), B_PLATE_WIN: ((212, 218, 222), "win"), B_CONC: (214, 218, 216),
        B_CONC_WIN: ((110, 170, 220), "glass"), B_RUST: (60, 150, 150), B_SOOT: ((70, 74, 78), "noise"),
        B_ROOF: ((160, 180, 196), "plates"), B_HAZARD: ((226, 190, 60), "plates"), B_GLOW: ((170, 225, 255), "glow"),
        B_PAD: (((214, 218, 216), (60, 150, 150)), "pad"), B_PIPE: (140, 144, 148), B_HULL: ((240, 242, 244), "plates"),
        B_GIRDER: ((80, 110, 60), "noise"), B_BRICK: ((160, 162, 164), "courses"), B_DUST: (150, 140, 120),
        B_DARK: (12, 12, 12)})


def esseles_atlas():
    """hod_esseles textures (Esseles: cream stone, terracotta, bronze-green and gold domes, garden green)."""
    _atlas_generic("hod_esseles", 139, {
        B_PLATE: ((230, 220, 196), "plates"), B_PLATE_WIN: ((222, 210, 184), "win"), B_CONC: (226, 218, 200),
        B_CONC_WIN: ((90, 170, 160), "glass"), B_RUST: (186, 96, 60), B_SOOT: ((110, 106, 100), "noise"),
        B_ROOF: ((90, 140, 110), "plates"), B_HAZARD: ((226, 180, 70), "plates"), B_GLOW: ((255, 220, 150), "glow"),
        B_PAD: (((200, 196, 186), (186, 96, 60)), "pad"), B_PIPE: (140, 138, 134), B_HULL: ((232, 230, 224), "plates"),
        B_GIRDER: ((70, 128, 58), "noise"), B_BRICK: ((200, 176, 136), "courses"), B_DUST: (210, 180, 130),
        B_DARK: (12, 10, 10)})


def coruscant_atlas():
    """hod_coruscant_lm textures (Coruscant: pale grey plate and white stone, lit window rows, blue-grey glass, Senate
    red, grime, dark grey, neon, warm light, white hull, metal, sandstone and bronze for the Jedi Temple)."""
    _atlas_generic("hod_coruscant_lm", 1, {
        B_PLATE: ((196, 198, 200), "plates"), B_PLATE_WIN: ((170, 174, 180), "win"), B_CONC: (226, 226, 222),
        B_CONC_WIN: ((110, 140, 170), "glass"), B_RUST: (160, 30, 30), B_SOOT: ((70, 70, 74), "noise"),
        B_ROOF: ((96, 98, 104), "plates"), B_HAZARD: ((120, 220, 255), "glow"), B_GLOW: ((255, 160, 60), "glow"),
        B_PAD: (((170, 172, 176), (160, 30, 30)), "pad"), B_PIPE: (140, 142, 146), B_HULL: ((232, 232, 230), "plates"),
        B_GIRDER: ((120, 120, 124), "lattice"), B_BRICK: ((206, 190, 160), "courses"), B_DUST: ((214, 150, 120), "plates"),
        B_DARK: (10, 10, 12)}, lit_rgb=(255, 150, 50))   # Coruscant's orange-lit windows (the user, 2026-10-21)


def jabiim_atlas():
    """hod_jabiim textures (Jabiim, the monsoon world: Republic white and red, Separatist tan, rain-stained
    concrete, mud brick and mud; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 75)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    sooty = lambda rgb: rgb * (0.78 + 0.28 * grime) * (0.8 + 0.25 * blotch) * (0.75 + 0.3 * streak)
    seams = (((xx % 48) < 2) | ((yy % 32) < 2))[..., None]
    plate = sooty(np.array([222, 220, 212], np.float32)) * (1 - 0.25 * seams)
    put(B_PLATE, plate, sp=60)
    rows = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 16) > 3)
    lit = rows & (rng.random((t, t)) > 0.3)
    warm = np.array([255, 204, 128], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [36, 34, 30], plate)), e=np.where(lit, 220, 0), sp=60)
    conc = sooty(np.array([138, 128, 112], np.float32)) * (1 - 0.15 * ((yy % 40) < 2)[..., None])
    put(B_CONC, conc)
    strip = (np.abs((yy % 40) - 22) < 3) & ((xx % 64) > 4)
    put(B_CONC_WIN, np.where(strip[..., None], warm * (0.9 + 0.1 * grime), conc), e=np.where(strip, 230, 0))
    put(B_RUST, np.array([172, 44, 38], np.float32) * (0.7 + 0.45 * grime) * (0.8 + 0.3 * streak), sp=50)
    put(B_SOOT, np.array([34, 30, 28], np.float32) * (0.8 + 0.4 * grime))
    put(B_ROOF, sooty(np.array([92, 92, 94], np.float32)) * (0.85 + 0.15 * np.sin(xx / 3.0))[..., None], sp=80)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 190, 40], [30, 28, 26]) * (0.8 + 0.25 * grime))
    put(B_GLOW, warm * (1.0 + 0.1 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (110, 108, 102))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(240, 190, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    d.line([(t * 0.2, t * 0.5), (t * 0.8, t * 0.5)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.75 + 0.3 * grime))
    put(B_PIPE, np.array([120, 118, 112], np.float32) * (0.75 + 0.35 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([196, 176, 134], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=90)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 96, 70], [40, 36, 32]) * (0.8 + 0.3 * grime), sp=80)
    brick = 1 - 0.25 * (((yy % 12) < 2) | ((((xx + 12 * ((yy // 12) % 2)) % 24) < 2)))[..., None]
    soot_top = np.clip((t * 0.35 - yy) / (t * 0.35), 0, 1)[..., None]   # v 1 (the top) blackened
    put(B_BRICK, np.array([112, 84, 62], np.float32) * brick * (0.8 + 0.3 * grime) * (1 - 0.75 * soot_top))
    put(B_DUST, np.array([98, 80, 60], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([20, 20, 22], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_jabiim", col, emi, spec)

def lianna_atlas():
    """hod_lianna textures (Lianna, Sienar's corporate world: light grey and white plate, dark glass with cool window
    light, Sienar blue accents, pale concrete; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 195)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    sooty = lambda rgb: rgb * (0.78 + 0.28 * grime) * (0.8 + 0.25 * blotch) * (0.75 + 0.3 * streak)
    seams = (((xx % 48) < 2) | ((yy % 32) < 2))[..., None]
    plate = sooty(np.array([206, 208, 212], np.float32)) * (1 - 0.25 * seams)
    put(B_PLATE, plate, sp=60)
    rows = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 16) > 3)
    lit = rows & (rng.random((t, t)) > 0.3)
    warm = np.array([200, 228, 255], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [36, 34, 30], plate)), e=np.where(lit, 220, 0), sp=60)
    conc = sooty(np.array([180, 176, 168], np.float32)) * (1 - 0.15 * ((yy % 40) < 2)[..., None])
    put(B_CONC, conc)
    strip = (np.abs((yy % 40) - 22) < 3) & ((xx % 64) > 4)
    put(B_CONC_WIN, np.where(strip[..., None], warm * (0.9 + 0.1 * grime), conc), e=np.where(strip, 230, 0))
    put(B_RUST, np.array([64, 96, 150], np.float32) * (0.7 + 0.45 * grime) * (0.8 + 0.3 * streak), sp=50)
    put(B_SOOT, np.array([34, 30, 28], np.float32) * (0.8 + 0.4 * grime))
    put(B_ROOF, sooty(np.array([124, 130, 140], np.float32)) * (0.85 + 0.15 * np.sin(xx / 3.0))[..., None], sp=80)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 190, 40], [30, 28, 26]) * (0.8 + 0.25 * grime))
    put(B_GLOW, warm * (1.0 + 0.1 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (110, 108, 102))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(240, 190, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    d.line([(t * 0.2, t * 0.5), (t * 0.8, t * 0.5)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.75 + 0.3 * grime))
    put(B_PIPE, np.array([120, 118, 112], np.float32) * (0.75 + 0.35 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([224, 226, 230], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=90)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 96, 70], [40, 36, 32]) * (0.8 + 0.3 * grime), sp=80)
    brick = 1 - 0.25 * (((yy % 12) < 2) | ((((xx + 12 * ((yy // 12) % 2)) % 24) < 2)))[..., None]
    soot_top = np.clip((t * 0.35 - yy) / (t * 0.35), 0, 1)[..., None]   # v 1 (the top) blackened
    put(B_BRICK, np.array([44, 52, 66], np.float32) * brick * (0.8 + 0.3 * grime) * (1 - 0.75 * soot_top))
    put(B_DUST, np.array([204, 192, 164], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([20, 20, 22], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_lianna", col, emi, spec)

def iego_atlas():
    """hod_iego textures (Iego: weathered tan plate, dark basalt, warm orange window light, bleached bone and
    desert sand; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 76)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    sooty = lambda rgb: rgb * (0.78 + 0.28 * grime) * (0.8 + 0.25 * blotch) * (0.75 + 0.3 * streak)
    seams = (((xx % 48) < 2) | ((yy % 32) < 2))[..., None]
    plate = sooty(np.array([188, 150, 108], np.float32)) * (1 - 0.25 * seams)
    put(B_PLATE, plate, sp=60)
    rows = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 16) > 3)
    lit = rows & (rng.random((t, t)) > 0.3)
    warm = np.array([255, 176, 96], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [36, 34, 30], plate)), e=np.where(lit, 220, 0), sp=60)
    conc = sooty(np.array([96, 92, 92], np.float32)) * (1 - 0.15 * ((yy % 40) < 2)[..., None])
    put(B_CONC, conc)
    strip = (np.abs((yy % 40) - 22) < 3) & ((xx % 64) > 4)
    put(B_CONC_WIN, np.where(strip[..., None], warm * (0.9 + 0.1 * grime), conc), e=np.where(strip, 230, 0))
    put(B_RUST, np.array([150, 82, 46], np.float32) * (0.7 + 0.45 * grime) * (0.8 + 0.3 * streak), sp=50)
    put(B_SOOT, np.array([34, 30, 28], np.float32) * (0.8 + 0.4 * grime))
    put(B_ROOF, sooty(np.array([124, 104, 88], np.float32)) * (0.85 + 0.15 * np.sin(xx / 3.0))[..., None], sp=80)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 190, 40], [30, 28, 26]) * (0.8 + 0.25 * grime))
    put(B_GLOW, warm * (1.0 + 0.1 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (110, 108, 102))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(240, 190, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    d.line([(t * 0.2, t * 0.5), (t * 0.8, t * 0.5)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.75 + 0.3 * grime))
    put(B_PIPE, np.array([120, 118, 112], np.float32) * (0.75 + 0.35 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([172, 166, 156], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=90)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 96, 70], [40, 36, 32]) * (0.8 + 0.3 * grime), sp=80)
    brick = 1 - 0.25 * (((yy % 12) < 2) | ((((xx + 12 * ((yy // 12) % 2)) % 24) < 2)))[..., None]
    soot_top = np.clip((t * 0.35 - yy) / (t * 0.35), 0, 1)[..., None]   # v 1 (the top) blackened
    put(B_BRICK, np.array([58, 56, 60], np.float32) * brick * (0.8 + 0.3 * grime) * (1 - 0.75 * soot_top))
    put(B_DUST, np.array([222, 208, 178], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([20, 20, 22], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_iego", col, emi, spec)

def moncala_atlas():
    """hod_moncala textures (Mon Cala: pale ribbed shell plate, sea-green panels, gold light from the domes, coral
    pink, the Quarren's dark slate; the map is always day: lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 77)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    sooty = lambda rgb: rgb * (0.78 + 0.28 * grime) * (0.8 + 0.25 * blotch) * (0.75 + 0.3 * streak)
    seams = (((xx % 48) < 2) | ((yy % 32) < 2))[..., None]
    plate = sooty(np.array([214, 208, 192], np.float32)) * (1 - 0.25 * seams)
    put(B_PLATE, plate, sp=60)
    rows = ((yy % 32) > 12) & ((yy % 32) < 20) & ((xx % 16) > 3)
    lit = rows & (rng.random((t, t)) > 0.3)
    warm = np.array([255, 214, 130], np.float32)
    put(B_PLATE_WIN, np.where(lit[..., None], warm, np.where(rows[..., None], [36, 34, 30], plate)), e=np.where(lit, 220, 0), sp=60)
    conc = sooty(np.array([118, 160, 150], np.float32)) * (1 - 0.15 * ((yy % 40) < 2)[..., None])
    put(B_CONC, conc)
    strip = (np.abs((yy % 40) - 22) < 3) & ((xx % 64) > 4)
    put(B_CONC_WIN, np.where(strip[..., None], warm * (0.9 + 0.1 * grime), conc), e=np.where(strip, 230, 0))
    put(B_RUST, np.array([228, 124, 106], np.float32) * (0.7 + 0.45 * grime) * (0.8 + 0.3 * streak), sp=50)
    put(B_SOOT, np.array([34, 30, 28], np.float32) * (0.8 + 0.4 * grime))
    put(B_ROOF, sooty(np.array([176, 184, 180], np.float32)) * (0.85 + 0.15 * np.sin(xx / 3.0))[..., None], sp=80)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(B_HAZARD, np.where(haz, [235, 190, 40], [30, 28, 26]) * (0.8 + 0.25 * grime))
    put(B_GLOW, warm * (1.0 + 0.1 * grime) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (110, 108, 102))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(240, 190, 40), width=int(t * 0.05))
    d.line([(t * 0.5, t * 0.2), (t * 0.5, t * 0.8)], fill=(240, 240, 230), width=int(t * 0.04))
    d.line([(t * 0.2, t * 0.5), (t * 0.8, t * 0.5)], fill=(240, 240, 230), width=int(t * 0.04))
    put(B_PAD, np.asarray(pad, np.float32) * (0.75 + 0.3 * grime))
    put(B_PIPE, np.array([120, 118, 112], np.float32) * (0.75 + 0.35 * grime) * (0.9 + 0.1 * np.sin(yy / 2.0))[..., None], sp=110)
    hull = np.array([196, 202, 206], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 64) < 2) | ((yy % 24) < 2)))[..., None]
    put(B_HULL, hull, sp=90)
    lattice = ((np.abs(((xx + yy) % 48) - 24) < 3) | (np.abs(((xx - yy) % 48) - 24) < 3) | ((yy % 48) < 4))[..., None]
    put(B_GIRDER, np.where(lattice, [110, 96, 70], [40, 36, 32]) * (0.8 + 0.3 * grime), sp=80)
    brick = 1 - 0.25 * (((yy % 12) < 2) | ((((xx + 12 * ((yy // 12) % 2)) % 24) < 2)))[..., None]
    soot_top = np.clip((t * 0.35 - yy) / (t * 0.35), 0, 1)[..., None]   # v 1 (the top) blackened
    put(B_BRICK, np.array([64, 72, 82], np.float32) * brick * (0.8 + 0.3 * grime) * (1 - 0.75 * soot_top))
    put(B_DUST, np.array([206, 190, 146], np.float32) * (0.85 + 0.2 * noise(1.5)))
    put(B_DARK, np.array([20, 20, 22], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_moncala", col, emi, spec)

def etti_atlas():
    """hod_etti textures (Etti IV: Mondder's corporate towers, Cybot Galactica's Arcoplex; the map is always day:
    lights are painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 87)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch = noise(2), noise(10)
    clean = lambda rgb: rgb * (0.9 + 0.12 * grime) * (0.94 + 0.08 * blotch)
    seams = (((xx % 64) < 2) | ((yy % 40) < 2))[..., None]
    ceramic = clean(np.array([226, 224, 216], np.float32)) * (1 - 0.12 * seams)
    put(E_CERAMIC, ceramic, sp=80)
    band = (yy % 40 > 14) & (yy % 40 < 26)
    lit = band & ((xx % 20) > 3) & (rng.random((t, t)) > 0.25)
    warm = np.array([255, 214, 150], np.float32)
    put(E_CERAMIC_WIN, np.where(lit[..., None], warm, np.where(band[..., None], [48, 70, 78], ceramic)), e=np.where(lit, 220, 0), sp=80)
    mull = (((xx % 24) < 2) | ((yy % 32) < 2))[..., None]
    glass = np.array([70, 150, 160], np.float32) * (0.85 + 0.25 * blotch) * (1 - 0.35 * mull) + 25 * mull
    put(E_GLASS, glass, sp=220)
    glit = ~mull[..., 0] & (rng.random((t, t)) > 0.55)
    put(E_GLASS_LIT, np.where(glit[..., None], warm * 0.95, glass), e=np.where(glit, 200, 0), sp=220)
    cob = np.array([48, 72, 132], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * seams)
    put(E_COBALT, cob, sp=120)
    cw = ((xx % 16) > 5) & ((yy % 24) > 9) & ((yy % 24) < 17)
    put(E_COBALT_WIN, np.where(cw[..., None], [150, 220, 255], cob), e=np.where(cw, 210, 0), sp=120)
    put(E_GOLD, np.array([214, 172, 80], np.float32) * (0.85 + 0.25 * grime), sp=200)
    put(E_STEEL, np.array([120, 132, 146], np.float32) * (0.85 + 0.25 * grime) * (1 - 0.15 * seams), sp=140)
    put(E_ROOF, clean(np.array([150, 154, 158], np.float32)), sp=60)
    put(E_GLOW, warm + 10, e=255, sp=200)
    stripes = ((yy // 16) % 3)[..., None]
    put(E_NEON, np.where(stripes == 0, [80, 240, 255], np.where(stripes == 1, [255, 80, 200], [255, 230, 120])), e=255, sp=200)
    pad = Image.new("RGB", (t, t), (96, 100, 108))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(90, 230, 240), width=int(t * 0.045))
    d.rectangle([t * 0.44, t * 0.25, t * 0.56, t * 0.75], fill=(230, 230, 225))
    put(E_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(E_HAZARD, np.where(haz, [235, 190, 40], [30, 28, 26]) * (0.85 + 0.2 * grime))
    put(E_GARDEN, np.array([70, 128, 70], np.float32) * (0.7 + 0.5 * noise(1.5)))
    lattice = ((np.abs(((xx + yy) % 40) - 20) < 2) | (np.abs(((xx - yy) % 40) - 20) < 2))[..., None]
    put(E_DOME, np.where(lattice, [235, 235, 240], [150, 200, 215]) * (0.9 + 0.1 * grime), sp=230)
    put(E_DARK, np.array([22, 24, 28], np.float32) * (0.8 + 0.4 * grime))
    _atlas_save("hod_etti", col, emi, spec)


def ruuria_atlas():
    """hod_ruuria textures (Ruurian colony hives and the University of Ruuria; the map is always day: lights are
    painted bright)."""
    import numpy as np
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 88)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    weave = (0.86 + 0.1 * np.sin(xx / 2.5 + 2 * np.sin(yy / 9.0)) * np.sin(yy / 3.0 + xx / 17.0))[..., None]
    silk = np.array([232, 226, 206], np.float32) * weave * (0.9 + 0.12 * blotch)
    put(R_SILK, silk, sp=50)
    holes = ((((xx - 12) % 32) ** 2 / 36 + ((yy - 14) % 40) ** 2 / 64) < 1)
    lit = holes & (rng.random((t, t)) > 0.3)
    resin = np.array([255, 186, 90], np.float32)
    put(R_SILK_WIN, np.where(lit[..., None], resin, np.where(holes[..., None], [60, 44, 30], silk)), e=np.where(lit, 220, 0), sp=50)
    plates = (1 - 0.3 * ((yy % 22) < 3)[..., None]) * (0.8 + 0.3 * grime)
    chitin = np.array([186, 120, 52], np.float32) * plates * (0.85 + 0.2 * streak)
    put(R_CHITIN, chitin, sp=170)
    ch = ((xx % 28) > 9) & ((xx % 28) < 19) & ((yy % 22) > 7) & ((yy % 22) < 17)
    put(R_CHITIN_WIN, np.where(ch[..., None], resin, chitin), e=np.where(ch, 210, 0), sp=170)
    courses = ((yy % 24) < 2)[..., None]
    stone = np.array([214, 206, 188], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.15 * courses)
    put(R_STONE, stone)
    arch = (((xx % 32) > 10) & ((xx % 32) < 22) & ((yy % 48) > 14) & ((yy % 48) < 38)
            & ~(((yy % 48) < 18) & (np.abs((xx % 32) - 16) > 4)))
    al = arch & (rng.random((t, t)) > 0.3)
    put(R_STONE_WIN, np.where(arch[..., None], np.where(al[..., None], resin * 0.95, [40, 36, 32]), stone), e=np.where(al, 200, 0))
    put(R_MOSS, np.array([78, 120, 58], np.float32) * (0.7 + 0.5 * noise(1.5)))
    put(R_GLOW, resin + 10, e=255, sp=200)
    put(R_DARK, np.array([26, 22, 20], np.float32) * (0.8 + 0.4 * grime))
    put(R_STALK, np.array([106, 80, 56], np.float32) * (0.75 + 0.3 * streak) * (0.9 + 0.1 * np.sin(xx / 3.0))[..., None])
    put(R_SLATE, np.array([84, 96, 92], np.float32) * (0.85 + 0.25 * grime) * (1 - 0.2 * (((xx % 20) < 2) | ((yy % 14) < 2)))[..., None], sp=70)
    put(R_PINK, np.array([214, 132, 160], np.float32) * (0.85 + 0.2 * blotch))
    put(R_LEAF, np.array([62, 112, 54], np.float32) * (0.7 + 0.5 * noise(1.5)))
    put(R_BRONZE, np.array([176, 136, 76], np.float32) * (0.8 + 0.3 * grime), sp=150)
    lattice = ((np.abs(((xx + yy) % 36) - 18) < 2) | (np.abs(((xx - yy) % 36) - 18) < 2))[..., None]
    put(R_DOME, np.where(lattice, [190, 160, 90], [170, 214, 196]) * (0.9 + 0.1 * grime), sp=220)
    put(R_MUD, np.array([110, 86, 62], np.float32) * (0.8 + 0.3 * noise(1.5)))
    _atlas_save("hod_ruuria", col, emi, spec)


def ossus_atlas():
    """hod_ossus textures (Ossus' ruins, the Ysanna and the archaeologists; nothing is lit but the vergence)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 194)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    courses = ((yy % 28) < 2)[..., None]
    joints = (((xx + 22 * ((yy // 28) % 2)) % 44) < 2)[..., None] & ~courses
    weather = (0.8 + 0.25 * grime) * (0.85 + 0.2 * blotch) * (0.85 + 0.2 * streak)
    stone = np.array([206, 196, 172], np.float32) * weather * (1 - 0.2 * courses - 0.12 * joints)
    put(O_STONE, stone)
    win = ((xx % 36) > 12) & ((xx % 36) < 24) & ((yy % 56) > 16) & ((yy % 56) < 44) \
        & ~(((yy % 56) < 21) & (np.abs((xx % 36) - 18) > 3))
    put(O_STONE_WIN, np.where(win[..., None], [30, 28, 26], stone))
    soot = smooth = noise(6)
    put(O_SCORCH, stone * (0.35 + 0.5 * soot) * np.array([0.9, 0.85, 0.8]))
    patina = noise(4)
    bronze = np.array([176, 128, 64], np.float32) * (1 - patina * 0.6) + np.array([90, 150, 120], np.float32) * patina * 0.6
    put(O_BRONZE, bronze * (0.8 + 0.25 * grime) * (1 - 0.15 * ((xx % 40) < 2)[..., None]), sp=140)
    put(O_MOSS, np.array([86, 120, 62], np.float32) * (0.65 + 0.55 * noise(1.5)))
    put(O_RUBBLE, np.array([168, 158, 138], np.float32) * (0.6 + 0.6 * noise(1.2)))
    put(O_HIDE, np.array([170, 132, 92], np.float32) * (0.8 + 0.3 * grime) * (0.9 + 0.1 * np.sin(xx / 5.0))[..., None])
    put(O_TIMBER, np.array([112, 82, 54], np.float32) * (0.75 + 0.3 * streak))
    mask = Image.new("RGB", (t, t), (170, 46, 36))
    d = ImageDraw.Draw(mask)
    for i in range(4):                                                    # painted mask bands and eye shapes
        d.rectangle([0, i * t // 4 + t // 10, t, i * t // 4 + t // 7], fill=(226, 196, 120))
        d.ellipse([t * 0.2, i * t // 4 + 4, t * 0.4, i * t // 4 + t // 12], fill=(24, 20, 18))
        d.ellipse([t * 0.6, i * t // 4 + 4, t * 0.8, i * t // 4 + t // 12], fill=(24, 20, 18))
    put(O_MASK, np.asarray(mask, np.float32) * (0.85 + 0.2 * grime))
    put(O_TARP, np.array([92, 112, 96], np.float32) * (0.85 + 0.2 * grime) * (0.9 + 0.1 * np.sin(yy / 4.0))[..., None])
    put(O_SCAFFOLD, np.array([150, 122, 82], np.float32) * (0.8 + 0.3 * streak) * (1 - 0.3 * ((xx % 24) < 3)[..., None]))
    put(O_GLOW, np.array([190, 230, 255], np.float32) + 10, e=255, sp=200)
    put(O_DARK, np.array([22, 20, 18], np.float32) * (0.8 + 0.4 * grime))
    put(O_EARTH, np.array([126, 104, 76], np.float32) * (0.8 + 0.3 * noise(1.5)))
    put(O_ROCK, np.array([138, 130, 118], np.float32) * (0.7 + 0.4 * noise(3)) * (0.9 + 0.15 * streak))
    gl = Image.new("L", (t, t), 0)                                        # carved band of Ossan script
    d = ImageDraw.Draw(gl)
    for i in range(12):
        x0 = i * t / 12 + 3
        for _ in range(3):
            a, b = rng.uniform(0, t / 12 - 6, 2)
            d.line([(x0 + a, t * 0.42 + rng.uniform(0, t * 0.06)), (x0 + b, t * 0.54 + rng.uniform(0, t * 0.06))], fill=255, width=4)
    cut = (np.asarray(gl, np.float32) / 255)[..., None]
    put(O_STONE_CARVED, stone * (1 - 0.5 * cut))
    _atlas_save("hod_ossus", col, emi, spec)


def lola_atlas():
    """hod_lola textures (Lola Sayu's basalt and lava, the Citadel's plating; lava and lights painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 193)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    basalt = np.array([58, 52, 54], np.float32) * (0.7 + 0.45 * noise(1.5)) * (0.85 + 0.25 * blotch)
    put(L_BASALT, basalt, sp=60)
    cr = Image.new("L", (t, t), 0)                                         # a web of glowing cracks
    d = ImageDraw.Draw(cr)
    for _ in range(14):
        x, y = rng.uniform(0, t, 2)
        for _ in range(6):
            x2, y2 = x + rng.uniform(-40, 40), y + rng.uniform(-40, 40)
            d.line([(x, y), (x2, y2)], fill=255, width=int(rng.integers(2, 5)))
            x, y = x2, y2
    c = (np.asarray(cr, np.float32) / 255)[..., None]
    lava = np.array([255, 170, 50], np.float32)
    put(L_BASALT_CRACK, basalt * (1 - c) + lava * c, e=c[..., 0] * 255, sp=60)
    put(L_CRUST, np.array([84, 70, 62], np.float32) * (0.65 + 0.5 * noise(3)), sp=40)
    seams = (((xx % 40) < 2) | ((yy % 24) < 2))[..., None]
    plate = np.array([86, 90, 98], np.float32) * (0.8 + 0.25 * grime) * (1 - 0.3 * seams) * (0.85 + 0.2 * streak)
    put(L_PLATE, plate, sp=120)
    band = (yy % 32 > 13) & (yy % 32 < 19) & ((xx % 12) > 2)
    lit = band & (rng.random((t, t)) > 0.35)
    put(L_PLATE_WIN, np.where(lit[..., None], [235, 236, 220], np.where(band[..., None], [26, 28, 32], plate)),
        e=np.where(lit, 210, 0), sp=120)
    put(L_RIB, plate * (0.75 + 0.3 * (np.sin(xx / 2.5) > 0)[..., None]), sp=140)
    put(L_LAVA, np.array([255, 150, 40], np.float32) * (0.85 + 0.25 * noise(1.5)) + np.array([0, 60, 0]) * noise(3),
        e=255, sp=200)
    put(L_SULFUR, np.array([220, 196, 70], np.float32) * (0.75 + 0.35 * noise(1.5)))
    put(L_DARK, np.array([16, 16, 18], np.float32) * (0.8 + 0.4 * grime))
    pad = Image.new("RGB", (t, t), (70, 74, 80))
    dd = ImageDraw.Draw(pad)
    dd.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(230, 60, 50), width=int(t * 0.045))
    put(L_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(L_GLOW, np.array([240, 240, 225], np.float32) + 10, e=255, sp=200)
    put(L_RED, np.array([255, 60, 40], np.float32), e=255, sp=200)
    put(L_TRIM, np.array([70, 96, 150], np.float32) * (0.85 + 0.2 * grime), sp=150)
    put(L_ROCK, np.array([96, 84, 80], np.float32) * (0.65 + 0.45 * noise(3)) * (0.9 + 0.15 * streak))
    # the cross-section of the planet on a fracture face, v = 1 at the old surface down to v = 0 at the molten core:
    # dark crust, banded rock strata, a red mantle getting hotter, glowing orange, a white-yellow core (emissive with
    # depth); band edges ragged
    depth = yy / t + 0.04 * (noise(1.2)[..., 0] - 0.5)                    # 0 at the surface (v = 1) .. 1 at the core
    stops = [(0.0, (46, 42, 44)), (0.12, (62, 54, 52)), (0.14, (110, 92, 78)), (0.2, (84, 70, 62)), (0.24, (126, 104, 84)),
             (0.3, (92, 66, 56)), (0.42, (130, 52, 34)), (0.58, (220, 92, 30)), (0.75, (255, 160, 50)), (1.0, (255, 236, 170))]
    ds, cs = zip(*stops)
    strata = np.stack([np.interp(depth, ds, [c[i] for c in cs]) for i in range(3)], -1)
    strata *= (0.85 + 0.2 * noise(1.5)) * (1 - 0.12 * ((yy % 9) < 1)[..., None] * (depth < 0.32)[..., None])
    put(L_STRATA, strata, e=np.clip((depth - 0.38) / 0.4, 0, 1) * 255, sp=80)
    put(L_SPARE2, plate)
    _atlas_save("hod_lola", col, emi, spec)


def ringo_atlas():
    """hod_ringo textures (Ringo Vinda's rock arches, hanging cities and orbital ring; lights painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 81)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    bands = (0.85 + 0.15 * np.sin(yy / 5.0 + 3 * noise(4)[..., 0]))[..., None]
    rock = np.array([196, 168, 132], np.float32) * bands * (0.8 + 0.25 * blotch) * (0.85 + 0.2 * streak)
    put(V_ROCK, rock)
    put(V_ROCK_DARK, rock * np.array([0.62, 0.6, 0.6]) * (0.8 + 0.3 * grime))
    courses = ((yy % 22) < 2)[..., None]
    stone = np.array([226, 216, 192], np.float32) * (0.88 + 0.15 * grime) * (1 - 0.14 * courses)
    put(V_STONE, stone)
    win = ((xx % 20) > 6) & ((xx % 20) < 14) & ((yy % 30) > 9) & ((yy % 30) < 22)
    lit = win & (rng.random((t, t)) > 0.35)
    warm = np.array([255, 210, 140], np.float32)
    put(V_STONE_WIN, np.where(lit[..., None], warm, np.where(win[..., None], [52, 50, 48], stone)), e=np.where(lit, 210, 0))
    patina = noise(4)
    put(V_DOME, np.array([110, 150, 120], np.float32) * (0.75 + 0.3 * patina) + np.array([60, 30, 0]) * (1 - patina),
        sp=140)
    put(V_ROOF, np.array([92, 98, 104], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 18) < 2) | ((yy % 12) < 2)))[..., None])
    put(V_GLOW, warm + 10, e=255, sp=200)
    put(V_DARK, np.array([22, 22, 24], np.float32) * (0.8 + 0.4 * grime))
    seams = (((xx % 48) < 2) | ((yy % 28) < 2))[..., None]
    hull = np.array([156, 148, 132], np.float32) * (0.82 + 0.22 * grime) * (1 - 0.25 * seams) * (0.9 + 0.12 * streak)
    put(V_HULL, hull, sp=110)
    rows = (yy % 28 > 11) & (yy % 28 < 17) & ((xx % 10) > 2)
    hl = rows & (rng.random((t, t)) > 0.3)
    put(V_HULL_WIN, np.where(hl[..., None], [240, 236, 210], np.where(rows[..., None], [30, 30, 32], hull)), e=np.where(hl, 220, 0), sp=110)
    put(V_PANEL, hull * (0.7 + 0.35 * (np.sin(xx / 2.0) > 0)[..., None]), sp=130)
    put(V_LIGHT, np.array([200, 230, 255], np.float32) + 10, e=255, sp=200)
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(V_HAZARD, np.where(haz, [230, 180, 40], [30, 28, 26]) * (0.85 + 0.2 * grime))
    pad = Image.new("RGB", (t, t), (110, 108, 104))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(240, 200, 90), width=int(t * 0.045))
    put(V_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    put(V_GARDEN, np.array([86, 128, 72], np.float32) * (0.7 + 0.5 * noise(1.5)))
    put(V_GLASS, np.array([120, 170, 180], np.float32) * (0.85 + 0.2 * blotch), sp=220)
    _atlas_save("hod_ringo", col, emi, spec)


def rhen_atlas():
    """hod_rhen textures (Rhen Var's frozen ruins and Bravo Base; lights painted bright)."""
    import numpy as np
    from PIL import Image, ImageDraw
    t = LM_S // 4
    col, emi, spec, put, noise, rng = _atlas_canvas(LM_S, 82)
    yy, xx = np.mgrid[0:t, 0:t].astype(np.float32)
    grime, blotch, streak = noise(2), noise(10), noise((28, 1.2))
    courses = ((yy % 26) < 2)[..., None]
    joints = (((xx + 20 * ((yy // 26) % 2)) % 40) < 2)[..., None] & ~courses
    frost = np.clip(noise(3) * 1.4 - 0.3, 0, 1)                            # frost settled in patches
    stone = np.array([132, 140, 150], np.float32) * (0.8 + 0.25 * grime) * (1 - 0.2 * courses - 0.12 * joints)
    stone = stone * (1 - 0.5 * frost) + np.array([226, 234, 242]) * 0.5 * frost
    put(H_STONE, stone)
    arch = (((xx % 32) > 10) & ((xx % 32) < 22) & ((yy % 52) > 14) & ((yy % 52) < 42)
            & ~(((yy % 52) < 19) & (np.abs((xx % 32) - 16) > 3)))
    put(H_STONE_WIN, np.where(arch[..., None], [26, 28, 34], stone))
    gl = Image.new("L", (t, t), 0)
    d = ImageDraw.Draw(gl)
    for i in range(10):
        x0 = i * t / 10 + 4
        d.rectangle([x0, t * 0.4, x0 + t / 10 - 10, t * 0.6], outline=255, width=3)
        d.line([(x0 + 4, t * 0.5), (x0 + t / 10 - 14, t * 0.5)], fill=255, width=3)
    put(H_CARVED, stone * (1 - 0.4 * (np.asarray(gl, np.float32) / 255)[..., None]))
    put(H_SNOW, np.array([236, 242, 250], np.float32) * (0.9 + 0.1 * noise(1.5)), sp=60)
    put(H_ICE, np.array([170, 210, 235], np.float32) * (0.85 + 0.2 * blotch) * (0.9 + 0.12 * streak), sp=230)
    put(H_DARK, np.array([20, 22, 28], np.float32) * (0.8 + 0.4 * grime))
    seams = (((xx % 40) < 2) | ((yy % 30) < 2))[..., None]
    panel = np.array([214, 216, 212], np.float32) * (0.88 + 0.14 * grime) * (1 - 0.18 * seams)
    put(H_PANEL, panel, sp=110)
    win = (yy % 30 > 12) & (yy % 30 < 19) & ((xx % 14) > 3)
    lit = win & (rng.random((t, t)) > 0.3)
    put(H_PANEL_WIN, np.where(lit[..., None], [250, 240, 200], np.where(win[..., None], [40, 44, 52], panel)),
        e=np.where(lit, 220, 0), sp=110)
    stripe = (np.abs(yy - t * 0.5) < t * 0.12)[..., None]
    put(H_RED, np.where(stripe, [170, 40, 34], panel), sp=110)
    put(H_SITH, np.array([46, 40, 44], np.float32) * (0.8 + 0.3 * grime) * (1 - 0.25 * courses) * (1 - 0.4 * frost)
        + np.array([200, 210, 220]) * 0.4 * frost)
    rk = Image.new("L", (t, t), 0)                                         # Rakatan script lines
    d = ImageDraw.Draw(rk)
    for i in range(16):
        y = 10 + i * t / 16
        for _ in range(5):
            a, b = rng.uniform(0, t, 2)
            d.line([(a, y), (b, y + rng.uniform(-6, 6))], fill=255, width=2)
    cut = (np.asarray(rk, np.float32) / 255)[..., None]
    rak = np.array([58, 64, 60], np.float32) * (0.8 + 0.3 * grime)
    put(H_RAKATA, rak * (1 - cut) + np.array([120, 255, 160], np.float32) * cut, e=cut[..., 0] * 200)
    put(H_GLOW, np.array([210, 236, 255], np.float32) + 10, e=255, sp=200)
    pad = Image.new("RGB", (t, t), (150, 152, 156))
    d = ImageDraw.Draw(pad)
    d.ellipse([t * 0.08, t * 0.08, t * 0.92, t * 0.92], outline=(180, 40, 34), width=int(t * 0.05))
    put(H_PAD, np.asarray(pad, np.float32) * (0.85 + 0.2 * grime))
    haz = (((xx + yy) // 24) % 2)[..., None]
    put(H_HAZARD, np.where(haz, [230, 180, 40], [30, 28, 26]) * (0.85 + 0.2 * grime))
    put(H_TIMBER, np.array([86, 72, 60], np.float32) * (0.75 + 0.3 * streak))
    put(H_ROOF, np.array([90, 98, 110], np.float32) * (0.85 + 0.2 * grime) * (1 - 0.2 * (((xx % 18) < 2) | ((yy % 12) < 2)))[..., None]
        * (1 - 0.5 * frost) + np.array([230, 236, 244]) * 0.5 * frost)
    _atlas_save("hod_rhen", col, emi, spec)


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
            u = d.cross(Vector((0, 0, 1)))
            u = (u if u.length > 1e-6 else d.cross(Vector((1, 0, 0)))).normalized()   # vertical tubes: zero cross
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
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import arch_kit as ak  # the shared architecture kit and the planets built with it

    def build(name, geometry, shader="PdxMeshAdvancedSnow", out=LM_OUT, tex="hod_landmarks", rot=0.0, extra=None):
        """rot: turn the model about its vertical axis (radians, counter-clockwise seen from above) before export;
        extra(): adds more mesh objects (own materials) to the scene, exported with it"""
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
        if extra:
            extra()
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
    def bon_tank(k, x, y, z0, h, r, sides=12):
        """a storage tank: plate drum under a shallow dome"""
        k.lathe([(r, z0), (r, z0 + h), (r * 0.6, z0 + h + 0.25 * r), (0.0, z0 + h + 0.32 * r)],
                [B_PLATE, B_ROOF, B_ROOF], sides=sides, cx=x, cy=y)

    def bon_hall(k, x, y, z0, h, w, d, a, wall=None, saw=True):
        """a factory hall turned by a: plate walls, a sawtooth roof (or a flat one)"""
        cslab(k, x, y, z0, h, w, d, a, wall or B_PLATE_WIN, B_ROOF)
        if saw:
            n = max(2, int(w / 0.07))
            ca, sa = math.cos(a), math.sin(a)
            for i in range(n):
                px = -w + (2 * i + 1) * w / n
                cslab(k, x + ca * px, y + sa * px, h - 0.005, h + 0.07 + 0.02 * w, w / n, d, a, B_ROOF, B_GLOW, wt=w / n * 0.1)

    def bon_fleet():
        """the orbital shipyard's layout, shared by its structure and its ships: [(kind, x, y, z, heading, built)] in
        model units (origin = the arc's middle); slips along the arc, ships lying along it (heading = tangent), and
        the small craft: Lethisk freighters docked at the end stations, Chela shuttles flying over the slips"""
        R, a0, a1, mid = BON_ORBIT_R, math.radians(BON_ARC[0]), math.radians(BON_ARC[1]), math.radians(sum(BON_ARC) / 2)
        cx, cy, z0 = -R * math.cos(mid), -R * math.sin(mid), BON_FLOAT
        pt = lambda r, t: (cx + r * math.cos(t), cy + r * math.sin(t))
        out = []
        for i, (kind, built) in enumerate(BON_SLIPS):
            t = a0 + (a1 - a0) * (i + 0.5) / len(BON_SLIPS)
            out.append((kind, *pt(R, t), z0 + 0.9, t + math.pi / 2 * (1 if i % 2 else -1), built))
        rng = random.Random("bon_fleet")
        for t, sgn in ((a0, -1), (a1, 1)):                                  # freighters docked on the end stations' rings
            sx, sy = pt(R + 3.0, t + sgn * 0.06)
            away = math.atan2(sgn * math.cos(t), -sgn * math.sin(t))        # along the arc, outward
            for j in (-1, 0, 1):
                b_ = away + j * 0.8
                out.append(("lethisk", sx + 9.6 * math.cos(b_), sy + 9.6 * math.sin(b_), z0 + 1.9, b_, 1.0))
        for j in range(12):                                                 # shuttles over the slips
            t = a0 + (a1 - a0) * rng.random()
            out.append(("chela", *pt(R + rng.uniform(-9, 9), t), z0 + rng.uniform(9.5, 12.0), t + rng.uniform(-0.6, 0.6), 1.0))
        return out, pt, z0

    def bon_shipyard(k):
        # the Bonadan shipyards in orbit (the user, 2026-10-15: a large space shipyard floating round the planet, a long
        # semicircle with ships being built in it, using our ship models, from province 6947 (NE) to 6525 (SE), outside
        # the atmosphere). Legends: Class IB, able to build cruisers. Origin = the arc's middle, stood on the space floor
        # (height 8.5): everything floats from BON_FLOAT up, clear of the water plane (~9.6) that clips meshes.
        # The slips (BON_SLIPS) hold the Battlefront II / EaW ships (sketchfab_props.py bon_*, added by bon_ships);
        # this is the yard round them: an outer spine of two decks (habitat drums, radiator fins, container stacks,
        # masts and dishes on top), a triangulated truss on the inner side, gantry towers and crane bridges between the
        # slips, clamp arms and tractor emitters reaching the hulls, scaffold hoops over the unbuilt parts, a command
        # tower at mid-arc and a ring station at each end
        R, a0, a1 = BON_ORBIT_R, math.radians(BON_ARC[0]), math.radians(BON_ARC[1])
        fleet, pt, z0 = bon_fleet()
        P = lambda r, t, z: (*pt(r, t), z)
        rng = random.Random("hod_bon_shipyard")
        n_seg, slips = 48, len(BON_SLIPS)
        rin, rout = R - 5.2, R + 5.2
        for i in range(n_seg):                                               # the outer spine, two decks
            t0, t1 = a0 + (a1 - a0) * i / n_seg, a0 + (a1 - a0) * (i + 1) / n_seg
            tm, half = (t0 + t1) / 2, (rout + 1.6) * (t1 - t0) / 2 * 1.03
            x, y = pt(rout + 1.6, tm)
            cslab(k, x, y, z0 - 0.8, z0 + 4.2, half, 1.8, tm + math.pi / 2, B_PLATE_WIN, B_ROOF, dt=1.5)    # lower deck
            cslab(k, x, y, z0 - 1.6, z0 - 0.8, half, 1.2, tm + math.pi / 2, B_HULL, B_SOOT)                # keel
            x, y = pt(rout + 2.2, tm)
            cslab(k, x, y, z0 + 4.2, z0 + 5.8, half * 0.98, 1.1, tm + math.pi / 2, B_CONC_WIN, B_ROOF)    # upper deck
            x, y = pt(rout - 0.35, tm)
            cslab(k, x, y, z0 + 1.0, z0 + 1.25, half, 0.35, tm + math.pi / 2, B_HAZARD, B_HAZARD)          # walkway
            x, y = pt(rout + 3.6, tm)
            cslab(k, x, y, z0 + 0.6, z0 + 3.4, half, 0.2, tm + math.pi / 2, B_PIPE, B_GLOW)                # outer gallery
            roll = rng.random()                                              # what stands on the upper deck
            x, y = pt(rout + 2.2 + rng.uniform(-0.5, 0.5), tm)
            if roll < 0.3:                                                   # habitat drum
                k.lathe([(0.8, z0 + 5.8), (0.8, z0 + 7.0), (0.5, z0 + 7.5), (0.0, z0 + 7.6)], [B_CONC_WIN, B_ROOF, B_ROOF],
                        sides=12, cx=x, cy=y)
            elif roll < 0.55:                                                # radiator fins
                for f in (-0.6, 0.0, 0.6):
                    fx, fy = pt(rout + 2.2 + f, tm)
                    cslab(k, fx, fy, z0 + 5.8, z0 + 7.6, half * 0.7, 0.04, tm + math.pi / 2, B_GIRDER, B_GLOW)
            elif roll < 0.8:                                                 # container stacks
                for c in range(rng.randint(2, 4)):
                    cxx, cyy = pt(rout + 2.2 + rng.uniform(-0.6, 0.6), tm + (c - 1.5) * (t1 - t0) * 0.22)
                    cslab(k, cxx, cyy, z0 + 5.8, z0 + 5.8 + 0.45 * rng.randint(1, 3), 0.55, 0.28, tm + math.pi / 2,
                          rng.choice([B_RUST, B_HAZARD, B_PLATE]), B_ROOF)
            else:                                                            # mast and dish
                k.tube((x, y, z0 + 5.8), (x, y, z0 + 9.5), 0.07, B_PIPE, sides=4)
                k.lathe([(0.1, z0 + 7.6), (0.7, z0 + 8.0), (0.85, z0 + 8.4)], [B_HULL, B_HULL], sides=10, cx=x, cy=y)
                k.lathe([(0.1, z0 + 9.5), (0.1, z0 + 9.7)], [B_GLOW], sides=4, cx=x, cy=y, cap=B_GLOW)
        for i in range(n_seg):                                               # the inner truss: 3 chords, diagonals
            t0, t1 = a0 + (a1 - a0) * i / n_seg, a0 + (a1 - a0) * (i + 1) / n_seg
            for r_, z_ in ((rin - 0.6, z0 + 0.4), (rin + 0.6, z0 + 0.4), (rin, z0 + 2.4)):
                k.tube(P(r_, t0, z_), P(r_, t1, z_), 0.1, B_GIRDER, sides=4)
            k.tube(P(rin - 0.6, t0, z0 + 0.4), P(rin, t1, z0 + 2.4), 0.06, B_GIRDER, sides=3)
            k.tube(P(rin + 0.6, t1, z0 + 0.4), P(rin, t0, z0 + 2.4), 0.06, B_GIRDER, sides=3)
            k.tube(P(rin - 0.6, t0, z0 + 0.4), P(rin + 0.6, t1, z0 + 0.4), 0.05, B_GIRDER, sides=3)
        for i in range(slips + 1):                                           # gantries between the slips
            t = a0 + (a1 - a0) * i / slips
            for r_ in (rin, rout - 0.4):                                     # towers
                x, y = pt(r_, t)
                cslab(k, x, y, z0 - 1.0, z0 + 9.0, 0.35, 0.35, t, B_GIRDER, B_RUST)
                for z_ in (2.5, 5.0, 7.5):
                    k.lathe([(0.12, z0 + z_), (0.12, z0 + z_ + 0.15)], [B_GLOW], sides=4, cx=x, cy=y, cap=B_GLOW)
            x, y = pt(R, t)
            cslab(k, x, y, z0 + 8.6, z0 + 9.3, (rout - rin) / 2 + 0.4, 0.3, t, B_GIRDER, B_HAZARD)          # bridge
            cslab(k, x, y, z0 + 9.3, z0 + 9.45, (rout - rin) / 2 + 0.4, 0.4, t, B_HAZARD, B_HAZARD)
            tx_, ty_ = pt(R + rng.uniform(-4, 4), t)                         # the crane trolley and its hook line
            cslab(k, tx_, ty_, z0 + 8.2, z0 + 9.6, 0.5, 0.55, t, B_HAZARD, B_ROOF)
            k.box(tx_ - 0.03, ty_ - 0.03, z0 + 5.0, tx_ + 0.03, ty_ + 0.03, z0 + 8.2, B_DARK)
            k.lathe([(0.25, z0 + 4.7), (0.25, z0 + 5.0)], [B_RUST], sides=6, cx=tx_, cy=ty_, cap=B_RUST)
        for kind, x, y, z, head, built in fleet[:slips]:                      # round each ship in its slip
            L, W, H = BON_SHIP_DIMS[kind]
            ch, sh = math.cos(head), math.sin(head)
            at = lambda u, v, zz: (x + ch * u - sh * v, y + sh * u + ch * v, zz)
            span = R * abs(a1 - a0) / slips / 2 - 0.5
            for u in [span * (j / 3 - 1) for j in range(7)]:                 # the slip's girder floor
                k.tube(at(u, -5.0, z0 - 0.6), at(u, 5.0, z0 - 0.6), 0.09, B_GIRDER, sides=4)
            for v_ in (-3.4, -1.2, 1.2, 3.4):
                k.tube(at(-span, v_, z0 - 0.6), at(span, v_, z0 - 0.6), 0.09, B_GIRDER, sides=4)
            for j in range(6):
                u_, v_ = rng.uniform(-span, span), rng.uniform(-4, 4)        # parts stacked on the floor
                cslab(k, *at(u_, v_, 0)[:2], z0 - 0.5, z0 - 0.5 + rng.uniform(0.3, 0.8), rng.uniform(0.3, 0.7),
                      rng.uniform(0.25, 0.5), head + rng.uniform(-0.3, 0.3), rng.choice([B_RUST, B_HULL, B_HAZARD]), B_ROOF)
            for u in (-0.32, 0.0, 0.32):                                     # clamp arms from both sides
                for side in (-1, 1):
                    hull = at(u * L, side * W * 0.5, z + H * 0.35)
                    root = at(u * L, side * 5.0, z + 1.4)
                    k.tube(root, hull, 0.12, B_HAZARD, sides=5)
                    k.lathe([(0.22, hull[2] - 0.15), (0.22, hull[2] + 0.15)], [B_PIPE], sides=6, cx=hull[0], cy=hull[1])
            for side in (-1, 1):                                             # tractor emitters on the spine side
                ex, ey, _ = at(rng.uniform(-0.3, 0.3) * L, side * 4.8, 0)
                k.lathe([(0.45, z + 3.2), (0.35, z + 3.7), (0.0, z + 3.9)], [B_HULL, B_GLOW], sides=10, cx=ex, cy=ey)
            for j in range(6):                                               # worklights on posts round the slip
                lx, ly, _ = at((j / 5 - 0.5) * L * 1.05, (1 if j % 2 else -1) * 4.4, 0)
                k.tube((lx, ly, z0 - 0.5), (lx, ly, z + H + 0.6), 0.05, B_PIPE, sides=4)
                k.lathe([(0.18, z + H + 0.6), (0.18, z + H + 0.8)], [B_GLOW], sides=6, cx=lx, cy=ly, cap=B_GLOW)
            if built < 1:                                                    # scaffold hoops over the unbuilt part
                u0, u1 = -L / 2 + L * built, L / 2
                n = max(3, int((u1 - u0) / 1.0))
                for j in range(n + 1):
                    u = u0 + (u1 - u0) * j / n
                    taper = 1 - 0.6 * (u - u0) / max(u1 - u0, 1e-3) * (u1 - u0) / L
                    w, h = W * 0.55 * taper + 0.2, H * taper + 0.3
                    k.tube(at(u, -w, z - 0.2), at(u, -w, z + h), 0.06, B_GIRDER, sides=3)
                    k.tube(at(u, w, z - 0.2), at(u, w, z + h), 0.06, B_GIRDER, sides=3)
                    k.tube(at(u, -w, z + h), at(u, w, z + h), 0.06, B_GIRDER, sides=3)
                    k.tube(at(u, -w, z - 0.2), at(u, w, z - 0.2), 0.05, B_GIRDER, sides=3)
                for v_, zz in ((-1, 0.5), (1, 0.5), (-1, 1.0), (1, 1.0)):    # stringers
                    k.tube(at(u0, v_ * (W * 0.55 + 0.2), z + zz * H * 0.8), at(u1, v_ * (W * 0.25 + 0.2), z + zz * H * 0.5),
                           0.05, B_GIRDER, sides=3)
                for _ in range(5):                                           # welding sparks at the seam
                    sx, sy, sz = at(u0 + rng.uniform(-0.2, 0.4), rng.uniform(-W, W) * 0.45, z + rng.uniform(0.2, H))
                    k.box(sx - 0.07, sy - 0.07, sz - 0.07, sx + 0.07, sy + 0.07, sz + 0.07, B_GLOW, top=B_GLOW)
        tm = (a0 + a1) / 2                                                    # the command tower, mid-arc, outside
        x, y = pt(rout + 6.0, tm)
        k.lathe([(2.6, z0 - 2.0), (2.8, z0 + 1.0), (2.2, z0 + 6.0), (1.6, z0 + 12.0)], [B_HULL, B_PLATE_WIN, B_CONC_WIN],
                sides=16, cx=x, cy=y, cap=B_ROOF)
        for zz, r_ in ((4.0, 3.6), (8.0, 3.0), (11.0, 2.6)):
            k.lathe([(r_, z0 + zz), (r_, z0 + zz + 0.35)], [B_GLOW], sides=20, cx=x, cy=y, cap=B_PLATE)
        k.lathe([(1.7, z0 + 12.0), (2.4, z0 + 12.6), (2.4, z0 + 13.4), (1.2, z0 + 14.2), (0.0, z0 + 14.4)],
                [B_PLATE_WIN, B_PLATE_WIN, B_ROOF, B_ROOF], sides=16, cx=x, cy=y)
        k.tube((x, y, z0 + 14.3), (x, y, z0 + 17.5), 0.1, B_PIPE, sides=4)
        for j in range(3):                                                   # its dishes
            dx, dy = x + 2.0 * math.cos(tm + 2.1 * j), y + 2.0 * math.sin(tm + 2.1 * j)
            k.lathe([(0.15, z0 + 13.8), (1.0, z0 + 14.2), (1.2, z0 + 14.6)], [B_HULL, B_HULL], sides=12, cx=dx, cy=dy)
        bx, by = pt(rout + 3.0, tm)                                          # the bridge out to it
        k.tube((bx, by, z0 + 3.0), (x, y, z0 + 3.0), 0.6, B_PLATE_WIN, sides=8)
        for t in (a0, a1):                                                   # ring stations at the ends
            ox = t + (-0.06 if t == a0 else 0.06)
            x, y = pt(R + 3.0, ox)
            k.lathe([(3.2, z0 - 1.5), (3.6, z0 + 1.0), (3.6, z0 + 4.0), (2.4, z0 + 6.5), (0.8, z0 + 8.0)],
                    [B_HULL, B_PLATE_WIN, B_CONC_WIN, B_ROOF], sides=18, cx=x, cy=y, cap=B_ROOF)
            k.tube((x, y, z0 + 8.0), (x, y, z0 + 11.5), 0.12, B_PIPE, sides=4)
            n_ring = 28
            for j in range(n_ring):                                          # the docking ring and its spokes
                b0, b1 = 2 * math.pi * j / n_ring, 2 * math.pi * (j + 1) / n_ring
                p0 = (x + 8.0 * math.cos(b0), y + 8.0 * math.sin(b0), z0 + 2.0)
                p1 = (x + 8.0 * math.cos(b1), y + 8.0 * math.sin(b1), z0 + 2.0)
                k.tube(p0, p1, 0.55, B_PLATE_WIN if j % 2 else B_HULL, sides=8)
                if j % 7 == 0:
                    k.tube((x, y, z0 + 2.0), p0, 0.3, B_GIRDER, sides=5)
                if j % 2 == 0:
                    k.lathe([(0.15, z0 + 2.55), (0.15, z0 + 2.75)], [B_GLOW], sides=4, cx=p0[0], cy=p0[1], cap=B_GLOW)
            k.tube(P(rout + 1.6, t, z0 + 2.0), (x, y, z0 + 2.0), 0.8, B_PLATE_WIN, sides=8)   # joined to the spine
        for kind, x, y, z, head, built in fleet[slips:]:                      # docking cradles for the freighters
            if kind == "lethisk":
                k.lathe([(0.9, z - 0.25), (0.9, z)], [B_HAZARD], sides=10, cx=x, cy=y, cap=B_PAD)

    def bon_ships():
        """the ships in Bonadan's orbital shipyard (place_ships)"""
        place_ships(bon_fleet()[0], lambda kind: BON_SHIP_SCALE if kind in BON_SHIP_DIMS else 1.0)

    def place_ships(fleet, scale_of, prefix="bon_"):
        """ships copied into a model as extra objects: the converted Battlefront II / EaW models (sketchfab_props.py
        bon_*, each with its own baked texture in hod_landmarks); fleet [(kind, x, y, z, heading, built)], unfinished
        hulls cut at `built`, scale_of(kind) -> scale"""
        from mathutils import Matrix  # type: ignore
        parts = {}
        for kind, x, y, z, head, built in fleet:
            if kind not in parts:
                before = set(bpy.data.objects)
                bie.import_meshfile(os.path.abspath(f"{LM_OUT}/hod_bld_{prefix}{kind}.mesh"), imp_mesh=True, imp_skel=False,
                                    imp_locs=False)
                objs = [o for o in bpy.data.objects if o not in set(before) and o.type == "MESH"]
                for o in bpy.data.objects:
                    o.select_set(o in objs)
                bpy.context.view_layer.objects.active = objs[0]
                bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                for o in [o for o in bpy.data.objects if o not in before and o.type != "MESH"]:
                    bpy.data.objects.remove(o, do_unlink=True)
                src = objs[0]
                co = [v.co for v in src.data.vertices]
                ext = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
                if ext[2] > max(ext[0], ext[1]):                             # stood on its tail: lay it down along y
                    src.data.transform(Matrix.Rotation(-math.pi / 2, 4, "X"))
                elif ext[0] > ext[1]:                                        # lying along x: turn it along y
                    src.data.transform(Matrix.Rotation(math.pi / 2, 4, "Z"))
                co = [v.co for v in src.data.vertices]
                lo_ = [min(c[i] for c in co) for i in range(3)]
                hi_ = [max(c[i] for c in co) for i in range(3)]
                src.data.transform(Matrix.Translation((-(lo_[0] + hi_[0]) / 2, -(lo_[1] + hi_[1]) / 2, -lo_[2])))
                parts[kind] = (src, hi_[1] - lo_[1], [])
            src, length, copies = parts[kind]
            c = src.copy()
            c.data = src.data.copy()
            bpy.context.scene.collection.objects.link(c)
            if built < 1:                                                    # only the stern part is plated yet
                bm2 = bmesh.new()
                bm2.from_mesh(c.data)
                bmesh.ops.bisect_plane(bm2, geom=bm2.verts[:] + bm2.edges[:] + bm2.faces[:],
                                       plane_co=(0, -length / 2 + length * built, 0), plane_no=(0, 1, 0), clear_outer=True)
                bm2.to_mesh(c.data)
                bm2.free()
            # model y (its length) along the heading
            sc_ = scale_of(kind)
            c.data.transform(Matrix.Translation((x, y, z)) @ Matrix.Rotation(head - math.pi / 2, 4, "Z") @ Matrix.Scale(sc_, 4))
            copies.append(c)
        for kind, (src, _l, copies) in parts.items():
            bpy.data.objects.remove(src, do_unlink=True)
            for o in bpy.data.objects:
                o.select_set(o in copies)
            bpy.context.view_layer.objects.active = copies[0]
            if len(copies) > 1:
                bpy.ops.object.join()
            m = copies[0].modifiers.new("t", "TRIANGULATE")
            bpy.ops.object.modifier_apply(modifier=m.name)
        print("  ships:", {k_: len(c_) for k_, (_s, _l, c_) in parts.items()})

    def ruu_pod(k, x, y, z0, h, r, mat=None, stalk=0.0, sides=10):
        """a Ruurian cocoon pod: a tapered ellipsoid of silk (resin-lit openings), on a stalk if `stalk` > 0"""
        if stalk:
            k.lathe([(r * 0.18, z0), (r * 0.12, z0 + stalk)], [R_STALK], sides=6, cx=x, cy=y)
            z0 += stalk
        m = mat or R_SILK_WIN
        k.lathe([(r * 0.3, z0), (r * 0.85, z0 + h * 0.18), (r, z0 + h * 0.45), (r * 0.8, z0 + h * 0.75),
                 (r * 0.35, z0 + h * 0.95), (0.0, z0 + h)], [m, m, m, R_SILK, R_SILK], sides=sides, cx=x, cy=y)

    def ruu_segments(k, x0, y0, x1, y1, z0, r, n, mat=R_CHITIN_WIN):
        """a segmented hall like the Ruurians' own bodies: a row of overlapping chitin rings from (x0, y0) to (x1, y1)"""
        for i in range(n):
            f = i / max(n - 1, 1)
            x, y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            rr = r * (0.8 + 0.2 * math.sin(math.pi * f))
            k.lathe([(rr * 0.9, z0), (rr, z0 + rr * 0.5), (rr * 0.85, z0 + rr * 0.95), (0.0, z0 + rr * 1.2)],
                    [mat, R_CHITIN, R_MOSS], sides=10, cx=x, cy=y)

    def ruu_city(k, band, rng):
        # a Ruurian colony (Legends: Ruurian society "made up of 143 colonies, and every Ruurian belonged to a single
        # colony for life"; the look is a design choice from the caterpillar-like species): clusters of silk cocoon
        # pods, some raised on stalks, segmented chitin halls, silk bridges between pods, moss on the roofs; the
        # colony's heart taller. band 1 edge .. 4 heart
        placed = []

        def spot(r, lim=0.85):
            for _ in range(20):
                x, y = rng.uniform(-lim, lim), rng.uniform(-lim, lim)
                if all(math.hypot(x - a, y - b) > r + c for a, b, c in placed):
                    placed.append((x, y, r))
                    return x, y
            return None
        pods = []
        for _ in range(2 + band + rng.randint(0, 1)):                                                     # pods
            r = rng.uniform(0.13, 0.2) + 0.012 * band
            p_ = spot(r * 1.1)
            if p_:
                st = rng.uniform(0.15, 0.4) * (rng.random() < 0.25 + 0.1 * band)
                h = rng.uniform(0.15, 0.3) + 0.12 * band
                ruu_pod(k, *p_, -0.3, h + 0.3, r, stalk=st)
                pods.append((*p_, -0.3 + st + (h + 0.3) * 0.5))
        for _ in range(rng.randint(1, 2)):                                                                # segmented hall
            a = rng.uniform(0, math.pi)
            p_ = spot(0.3)
            if p_:
                L = rng.uniform(0.25, 0.4)
                ruu_segments(k, p_[0] - L * math.cos(a), p_[1] - L * math.sin(a), p_[0] + L * math.cos(a),
                             p_[1] + L * math.sin(a), -0.08, rng.uniform(0.13, 0.18), rng.randint(3, 5))
        for (x0, y0, z0), (x1, y1, z1) in zip(pods, pods[1:3]):                                            # silk bridges
            k.tube((x0, y0, z0), (x1, y1, z1), 0.02, R_SILK, sides=4)
        if band >= 3:                                                                                     # the heart pod
            p_ = spot(0.2)
            if p_:
                ruu_pod(k, *p_, -0.3, 0.9 + 0.25 * band, 0.26, mat=R_CHITIN_WIN, sides=12)

    def ruu_university(k):
        # the University of Ruuria (canon: a university on Ruuria, still teaching in 6 BBY; Legends: the Ruurian
        # historian S. ... wrote there; the look is a design choice): an old academic quarter of pale arched-stone halls
        # round a green quad, a library spire of stacked silk-and-stone rings, a domed observatory, a lecture
        # amphitheatre, and Ruurian segmented halls and cocoon dormitories added round it. ~12 map units
        k.lathe([(5.8, -SKIRT), (5.8, 0.3)], [R_STONE], sides=14, sy=0.9, jitter=0.03, cap=R_MOSS)          # the campus
        k.box(-2.2, -1.6, 0.3, 2.2, 1.6, 0.36, R_LEAF, top=R_LEAF)                                        # the quad
        for sx, sy_, w, d in ((-3.2, 0, 0.9, 2.4), (3.2, 0, 0.9, 2.4), (0, 2.6, 2.6, 0.9)):               # stone halls
            k.box(sx - w, sy_ - d, 0.3, sx + w, sy_ + d, 1.9, R_STONE_WIN, top=R_STONE)
            cslab(k, sx, sy_, 1.9, 2.5, w * 1.05, d * 1.05, 0.0, R_SLATE, R_SLATE, wt=w * 0.3, dt=d * 0.92)
        x, y = 0.0, 3.0                                                                                  # library spire
        for i, (r, h) in enumerate(((1.3, 1.6), (1.1, 1.3), (0.9, 1.2), (0.7, 1.0))):
            z = 0.3 + sum(hh for _r, hh in ((1.3, 1.6), (1.1, 1.3), (0.9, 1.2), (0.7, 1.0))[:i])
            k.lathe([(r, z), (r, z + h * 0.8)], [R_STONE_WIN if i % 2 == 0 else R_SILK_WIN], sides=14, cx=x, cy=y)
            k.lathe([(r * 1.12, z + h * 0.8), (r * 0.9, z + h)], [R_BRONZE], sides=14, cx=x, cy=y)
        k.lathe([(0.55, 5.4), (0.0, 7.0)], [R_BRONZE], sides=10, cx=x, cy=y)
        k.lathe([(1.4, 0.3), (1.4, 1.2), (1.1, 1.9), (0.6, 2.3), (0.0, 2.45)], [R_STONE_WIN, R_DOME, R_DOME, R_DOME],
                sides=18, cx=-3.4, cy=-3.2)                                                              # observatory
        for i in range(5):                                                                               # amphitheatre
            r0 = 1.0 + 0.35 * i
            k.lathe([(r0, 0.3 + 0.12 * i), (r0, 0.42 + 0.12 * i)], [R_STONE], sides=16, cx=3.2, cy=-3.2, cap=R_STONE)
        k.lathe([(0.9, 0.3), (0.9, 0.35)], [R_MUD], sides=16, cx=3.2, cy=-3.2, cap=R_MUD)
        ruu_segments(k, -4.8, 1.2, -4.8, 4.2, 0.3, 0.6, 5)                                               # Ruurian halls
        ruu_segments(k, 4.6, 1.0, 3.2, 4.4, 0.3, 0.55, 5)
        for x, y in ((-1.6, -3.9), (0.2, -4.4), (1.6, -3.8), (-4.2, -1.0)):                               # dormitories
            ruu_pod(k, x, y, 0.3, 1.6, 0.55, stalk=0.4)
        for x, y in ((-1.5, 0.0), (1.5, 0.0), (0.0, -0.9), (0.0, 0.9)):                                  # quad trees
            k.lathe([(0.08, 0.36), (0.06, 0.9)], [R_STALK], sides=5, cx=x, cy=y)
            k.lathe([(0.15, 0.8), (0.45, 1.05), (0.3, 1.35), (0.0, 1.45)], [R_LEAF, R_LEAF, R_LEAF], sides=8, cx=x, cy=y)

    def ruu_great_hive(k):
        # the First Colony's great hive (the oldest of the 143 colonies (Legends: 143 colonies; "first" is invented)):
        # a vast mound of fused cocoon pods rising in tiers to a crown pod, segmented tunnels radiating out, pods on
        # stalks round it, silk cables strung between them, resin light in every opening. ~11 map units
        k.lathe([(5.2, -SKIRT), (5.2, 0.3)], [R_MUD], sides=13, sy=0.9, jitter=0.08, cap=R_MOSS)            # the mound
        k.lathe([(3.6, 0.3), (3.4, 1.6), (2.6, 3.2), (1.6, 4.6), (0.0, 5.4)], [R_SILK_WIN, R_SILK_WIN, R_SILK, R_SILK],
                sides=16, jitter=0.06)
        for i in range(9):                                                                               # fused pods
            a = 2 * math.pi * i / 9
            r_ = 2.6 + 0.4 * (i % 2)
            ruu_pod(k, r_ * math.cos(a), r_ * math.sin(a), 0.3 + 0.6 * (i % 3), 2.2 + 0.4 * (i % 2), 0.8, sides=10)
        ruu_pod(k, 0.0, 0.0, 4.6, 2.4, 0.9, mat=R_CHITIN_WIN, sides=12)                                   # crown pod
        for i in range(4):                                                                               # tunnels
            a = 2 * math.pi * i / 4 + 0.4
            ruu_segments(k, 3.4 * math.cos(a), 3.4 * math.sin(a), 5.0 * math.cos(a), 5.0 * math.sin(a), 0.3, 0.55, 4)
        tops = []
        for i in range(6):                                                                               # stalked pods
            a = 2 * math.pi * (i + 0.5) / 6
            x, y = 4.4 * math.cos(a), 4.4 * math.sin(a)
            ruu_pod(k, x, y, 0.3, 1.1, 0.45, stalk=1.4)
            tops.append((x, y, 2.3))
        for (x0, y0, z0), (x1, y1, z1) in zip(tops, tops[1:] + tops[:1]):                                 # silk cables
            k.tube((x0, y0, z0), (x1, y1, z1), 0.04, R_SILK, sides=4)
        for x, y, z in tops[::2]:
            k.tube((x, y, z), (0.0, 0.0, 4.2), 0.05, R_SILK, sides=4)

    def oss_dome(k, x, y, z0, r, h, broken, rng):
        """a squat Ossan dome of bronzium on a stone drum (Knossa: "its squat domes"); broken ones lose their cap"""
        k.lathe([(r, z0), (r, z0 + h * 0.45)], [O_STONE_WIN], sides=12, cx=x, cy=y)
        prof = [(r * 1.04, z0 + h * 0.45), (r * 0.95, z0 + h * 0.65), (r * 0.72, z0 + h * 0.85), (r * 0.38, z0 + h)]
        if broken:                                                          # the cap fell in: a jagged rim
            k.lathe(prof[:3], [O_BRONZE, O_BRONZE], sides=12, cx=x, cy=y, jitter=0.12)
        else:
            k.lathe(prof + [(0.0, z0 + h * 1.04)], [O_BRONZE, O_BRONZE, O_BRONZE, O_BRONZE], sides=12, cx=x, cy=y)

    def oss_rubble(k, rng, cx, cy, spread, n, size=(0.08, 0.22), z0=-0.05):
        for _ in range(n):
            x, y = cx + rng.uniform(-spread, spread), cy + rng.uniform(-spread, spread)
            w = rng.uniform(*size)
            cslab(k, x, y, z0, z0 + w * rng.uniform(0.5, 1.2), w, w * rng.uniform(0.5, 1.0), rng.uniform(0, math.pi),
                  rng.choice([O_RUBBLE, O_STONE, O_SCORCH]), O_RUBBLE)

    def oss_ruin(k, band, rng):
        # the ruins of Ossus' cities (Knossa: stone and bronzium, squat domes (canon); "the Cron incident destroyed most
        # of the buildings in these cities" (Legends)): broken stone walls and roofless houses, squat bronzium domes,
        # some fallen in, toppled columns, rubble and moss; the heart has the bigger domes. band 1 edge .. 4 heart
        placed = []

        def spot(r, lim=0.85):
            for _ in range(20):
                x, y = rng.uniform(-lim, lim), rng.uniform(-lim, lim)
                if all(math.hypot(x - a, y - b) > r + c for a, b, c in placed):
                    placed.append((x, y, r))
                    return x, y
            return None
        for _ in range(1 + band // 2 + rng.randint(0, 1)):                                                # domes
            r = rng.uniform(0.14, 0.2) + 0.03 * band
            p_ = spot(r * 1.1)
            if p_:
                oss_dome(k, *p_, -0.3, r, 0.42 + 0.05 * band, rng.random() < 0.45, rng)   # squat (canon)
        for _ in range(2 + band):                                                                         # roofless walls
            w, d = rng.uniform(0.1, 0.18), rng.uniform(0.08, 0.14)
            p_ = spot(max(w, d) * 1.1)
            if p_:
                a = rng.uniform(0, math.pi)
                h = rng.uniform(0.12, 0.3) + 0.05 * band
                ca, sa = math.cos(a), math.sin(a)
                for sx, sy, ww, dd in ((0, d, w, 0.02), (0, -d, w, 0.02), (w, 0, 0.02, d), (-w, 0, 0.02, d)):
                    if rng.random() < 0.8:                                                                # a wall stands
                        hh = h * rng.uniform(0.4, 1.0)
                        cslab(k, p_[0] + ca * sx - sa * sy, p_[1] + sa * sx + ca * sy, -0.3, hh, ww, dd, a,
                              rng.choice([O_STONE_WIN, O_STONE, O_SCORCH]), O_MOSS)
        for _ in range(band):                                                                             # columns
            p_ = spot(0.05)
            if p_:
                if rng.random() < 0.5:
                    k.lathe([(0.04, -0.3), (0.035, rng.uniform(0.3, 0.6))], [O_STONE], sides=6, cx=p_[0], cy=p_[1], cap=O_MOSS)
                else:                                                                                     # toppled
                    a = rng.uniform(0, 6.28)
                    k.tube((p_[0], p_[1], 0.04), (p_[0] + 0.4 * math.cos(a), p_[1] + 0.4 * math.sin(a), 0.04), 0.04, O_STONE, sides=6)
        oss_rubble(k, rng, 0.0, 0.0, 0.8, 3 + band)

    def ysanna_camp(k, band, rng):
        # an Ysanna camp (canon + Legends: masked tribes who depend on the kirruk and live in the valleys near the Eocho
        # Mountains, among the ruins they revere; the look is a design choice): conical hide tents on timber poles,
        # a long timber hall, totem poles carved with painted masks, a fire ring, a reused ruin wall
        placed = []

        def spot(r, lim=0.8):
            for _ in range(20):
                x, y = rng.uniform(-lim, lim), rng.uniform(-lim, lim)
                if all(math.hypot(x - a, y - b) > r + c for a, b, c in placed):
                    placed.append((x, y, r))
                    return x, y
            return None
        for _ in range(2 + band):                                                                         # tents
            r = rng.uniform(0.09, 0.14)
            p_ = spot(r * 1.2)
            if p_:
                h = rng.uniform(0.28, 0.4)
                k.lathe([(r, -0.05), (r * 0.25, h), (0.02, h + 0.08)], [O_HIDE, O_TIMBER], sides=7, cx=p_[0], cy=p_[1])
        if band >= 2:                                                                                     # long hall
            p_ = spot(0.25)
            if p_:
                a = rng.uniform(0, math.pi)
                cslab(k, *p_, -0.1, 0.14, 0.22, 0.09, a, O_TIMBER, O_TIMBER)
                cslab(k, *p_, 0.14, 0.26, 0.24, 0.11, a, O_HIDE, O_HIDE, wt=0.24, dt=0.01)
        for _ in range(1 + band // 2):                                                                    # mask totems
            p_ = spot(0.04)
            if p_:
                k.lathe([(0.035, -0.1), (0.03, 0.55)], [O_MASK], sides=6, cx=p_[0], cy=p_[1], cap=O_TIMBER)
        p_ = spot(0.1)
        if p_:                                                                                            # fire ring
            k.lathe([(0.1, -0.05), (0.1, 0.03)], [O_STONE], sides=8, cx=p_[0], cy=p_[1], cap=O_DARK)
        if rng.random() < 0.5:                                                                            # a ruin wall
            p_ = spot(0.2)
            if p_:
                cslab(k, *p_, -0.3, 0.25, 0.2, 0.025, rng.uniform(0, math.pi), O_STONE_CARVED, O_MOSS)

    def oss_library(k):
        # the ruins of the Great Jedi Library (Legends: "located on a hill in the Ooroo Canyon, the Library was a large,
        # unadorned stone building with many of its rooms located below ground"; canon: designed by Odan-Urr, devastated
        # by the Cron Supernova, "its ruins were the only remains of what was once a palatial facility"; Legends: the
        # Academy of Jedi Archaeology and others excavated the ruins): a vast plain stone hall on its hill, roof fallen,
        # walls broken to stumps on one side and scorched, its colonnade toppled, excavation pits opening into the
        # rooms below, the archaeologists' tents, scaffolds and a crane. ~12 map units
        rng = random.Random("hod_oss_library")
        k.lathe([(6.2, -SKIRT), (5.6, 0.4), (4.4, 1.0)], [O_ROCK, O_EARTH], sides=12, sy=0.85, jitter=0.07, cap=O_EARTH)   # hill
        x0, x1, y0, y1, z0 = -3.6, 3.6, -2.2, 2.2, 1.0
        k.box(x0 - 0.3, y0 - 0.3, z0 - 0.6, x1 + 0.3, y1 + 0.3, z0 + 0.15, O_STONE, top=O_STONE)               # plinth
        for i in range(12):                                                                              # long walls
            f0, f1 = i / 12, (i + 1) / 12
            for y, side in ((y0, 0), (y1, 1)):
                h = 3.2 if (side == 0 or i < 7) else rng.uniform(0.6, 1.8)
                k.box(x0 + (x1 - x0) * f0, y - 0.25, z0, x0 + (x1 - x0) * f1 - 0.02, y + 0.25, z0 + h,
                      O_STONE_WIN if h > 2 else O_SCORCH, top=O_MOSS)
        for x, h in ((x0, 3.2), (x1, 2.0)):                                                              # end walls
            k.box(x - 0.25, y0, z0, x + 0.25, y1, z0 + h, O_STONE_CARVED, top=O_MOSS)
        for i in range(4):                                                                               # roof beams left
            x = x0 + 0.8 + 1.2 * i
            k.box(x - 0.15, y0, z0 + 3.0, x + 0.15, y1, z0 + 3.3, O_STONE, top=O_MOSS)
        k.box(-3.3, -1.9, z0 + 0.15, -1.0, 1.9, z0 + 0.2, O_DARK, top=O_DARK)                           # open pits:
        k.box(0.4, -1.2, z0 + 0.15, 2.8, 1.4, z0 + 0.2, O_DARK, top=O_DARK)                             # rooms below
        for x in (-2.2, 1.6):                                                                            # scaffolds
            for y in (-1.6, 1.0):
                k.tube((x, y, z0 + 0.2), (x, y, z0 + 2.4), 0.05, O_SCAFFOLD, sides=4)
            k.box(x - 0.1, -1.7, z0 + 2.3, x + 0.1, 1.1, z0 + 2.4, O_SCAFFOLD, top=O_SCAFFOLD)
        for i in range(8):                                                                               # colonnade
            x = x0 + 0.4 + 0.9 * i
            if i % 3 == 1:                                                                               # toppled
                k.tube((x, y0 - 0.9, z0 - 0.1), (x + 1.0, y0 - 1.5, z0 - 0.3), 0.18, O_STONE, sides=6)
            else:
                k.lathe([(0.2, z0 - 0.4), (0.17, z0 + rng.uniform(1.0, 2.6))], [O_STONE], sides=8, cx=x, cy=y0 - 0.9, cap=O_MOSS)
        oss_rubble(k, rng, 0.0, -3.4, 3.4, 18, size=(0.2, 0.5), z0=z0 - 0.4)
        for x, y in ((-4.6, 3.0), (-3.6, 3.6), (-2.6, 3.4)):                                             # dig camp tents
            k.lathe([(0.5, 0.9), (0.5, 1.3), (0.0, 1.8)], [O_TARP, O_TARP], sides=4, cx=x, cy=y, rot=math.pi / 4)
        k.tube((4.4, 2.6, 0.9), (4.4, 2.6, 4.2), 0.08, O_SCAFFOLD, sides=4)                             # the crane
        k.tube((4.4, 2.6, 4.2), (2.4, 1.0, 4.4), 0.06, O_SCAFFOLD, sides=4)
        k.box(2.37, 0.97, z0 + 1.0, 2.43, 1.03, 4.4, O_DARK)

    def oss_knossa(k):
        # the ruins of Knossa (canon: "built from stone and bronzium, and its squat domes were located high in the
        # western Eocho Mountains"; the Knossa Branch Library commissioned by Odan-Urr; Legends capital): a terraced
        # mountain city of squat bronzium domes on stone drums, many fallen in, the Branch Library's long hall,
        # retaining walls stepping down the slope, broken stairs, rubble. ~11 map units
        rng = random.Random("hod_oss_knossa")
        for i, (r, z) in enumerate(((5.6, 0.0), (4.2, 0.9), (2.8, 1.8))):                               # terraces
            k.lathe([(r + 0.3, -SKIRT if i == 0 else z - 0.9), (r, z + 0.5)], [O_STONE], sides=14, cy=0.3 * i,
                    sy=0.85, jitter=0.04, cap=O_EARTH)
        for i in range(7):                                                                               # domes, ring 1
            a = 2 * math.pi * i / 7 + 0.3
            oss_dome(k, 4.4 * math.cos(a), 0.85 * 4.4 * math.sin(a), 0.5, 0.7, 1.6, i % 3 == 0, rng)
        for i in range(5):                                                                               # ring 2
            a = 2 * math.pi * i / 5 + 0.9
            oss_dome(k, 3.0 * math.cos(a), 0.3 + 0.85 * 3.0 * math.sin(a), 1.4, 0.85, 1.9, i == 2, rng)
        oss_dome(k, 0.0, 0.6, 2.3, 1.5, 2.8, False, rng)                                                # the great dome
        k.box(-2.2, -1.8, 1.4, 0.8, -1.0, 3.0, O_STONE_WIN, top=O_SCORCH)                               # Branch Library
        k.box(-2.2, -1.85, 2.2, 0.8, -1.75, 2.45, O_STONE_CARVED)
        for j in range(6):                                                                               # broken stair
            k.box(1.6 + 0.35 * j, -3.4, -0.3, 1.95 + 0.35 * j, -2.4, 0.15 * j + 0.3, O_STONE, top=O_STONE)
        oss_rubble(k, rng, 0.0, 0.0, 4.8, 22, size=(0.15, 0.4), z0=0.3)

    def oss_agorn(k):
        # the Knossa Spaceport on Agorn Mountain (canon / Legends: "a sprawling promenade wrapped around Agorn Mountain",
        # built by the Jedi for pilgrims; ruined since the Cron Supernova): a rocky peak with a broad stone promenade
        # spiralling up round it, landing terraces jutting out at each turn, broken arches, a pilgrims' gate at the
        # foot; the Eye of Ashlanae vergence on a nearby peak shows as a faint glow at the summit. ~10 map units
        rng = random.Random("hod_oss_agorn")
        k.lathe([(4.6, -SKIRT), (3.6, 1.5), (2.4, 4.0), (1.3, 6.5), (0.4, 8.2), (0.0, 8.6)],
                [O_ROCK, O_ROCK, O_ROCK, O_ROCK, O_ROCK], sides=11, jitter=0.12)                         # the mountain
        turns, steps = 2.25, 40
        for i in range(steps):                                                                           # promenade
            f0, f1 = i / steps, (i + 1) / steps
            a0, a1 = 2 * math.pi * turns * f0, 2 * math.pi * turns * f1
            z0 = 0.4 + 6.4 * f0
            r = 4.0 - 2.6 * f0 + 0.6
            am = (a0 + a1) / 2
            cslab(k, r * math.cos(am), r * math.sin(am), z0 - 0.5, z0, r * (a1 - a0) / 2 * 1.1, 0.65, am + math.pi / 2,
                  O_STONE, O_STONE)
            if i % 4 == 0 and rng.random() < 0.75:                                                       # parapet posts
                k.lathe([(0.08, z0), (0.08, z0 + 0.5)], [O_STONE], sides=4, cx=(r + 0.6) * math.cos(am), cy=(r + 0.6) * math.sin(am))
            if i % 10 == 5:                                                                              # landing terrace
                tx, ty = (r + 1.3) * math.cos(am), (r + 1.3) * math.sin(am)
                k.lathe([(1.0, z0 - 0.8), (1.0, z0)], [O_STONE_CARVED], sides=12, cx=tx, cy=ty, cap=O_STONE)
                k.lathe([(0.15, z0 - 3.5), (0.12, z0 - 0.8)], [O_STONE], sides=6, cx=tx, cy=ty)
        for x in (-0.9, 0.9):                                                                            # the gate
            k.box(x - 0.25, -4.9, -0.3, x + 0.25, -4.4, 2.2, O_STONE_CARVED, top=O_MOSS)
        k.box(-1.15, -4.9, 2.2, 1.15, -4.4, 2.6, O_STONE, top=O_MOSS)
        k.lathe([(0.25, 8.4), (0.25, 8.9)], [O_GLOW], sides=8, cap=O_GLOW)                              # vergence glow
        oss_rubble(k, rng, 0.0, 0.0, 4.6, 14, size=(0.15, 0.45), z0=0.0)

    def oss_temple(k):
        # the ruins of the First Temple, the Jedi Praxeum (canon: "located on the Outer Rim Territories planet Ossus",
        # where Odan-Urr trained under Master Ooroo): a stepped stone platform, a ring of great columns (some fallen)
        # round a cracked meditation dome open to the sky, four stairs, carved lintels, bamboo and moss creeping over
        # all of it. ~10 map units
        rng = random.Random("hod_oss_temple")
        for i, (r, z) in enumerate(((5.0, 0.0), (4.0, 0.7), (3.0, 1.4))):                               # steps
            k.lathe([(r, -SKIRT if i == 0 else z - 0.7), (r, z + 0.7)], [O_STONE_CARVED], sides=4, rot=math.pi / 4,
                    cap=O_STONE if i < 2 else O_MOSS)
        for j in range(4):                                                                               # stairs
            a = math.pi / 2 * j
            for s_ in range(5):
                rr = 5.6 - 0.45 * s_
                cslab(k, rr * math.cos(a), rr * math.sin(a), -0.3, 0.42 * s_ + 0.2, 0.25, 1.0, a, O_STONE, O_STONE)
        for i in range(12):                                                                              # columns
            a = 2 * math.pi * i / 12
            x, y = 2.5 * math.cos(a), 2.5 * math.sin(a)
            if i in (2, 7, 9):                                                                           # fallen
                k.tube((x, y, 2.2), (x + 2.4 * math.cos(a + 0.6), y + 2.4 * math.sin(a + 0.6), 0.9), 0.28, O_STONE, sides=8)
            else:
                h = rng.uniform(3.0, 4.2)
                k.lathe([(0.32, 2.1), (0.28, 2.1 + h)], [O_STONE], sides=8, cx=x, cy=y, cap=O_MOSS)
        for i in range(12):                                                                              # lintels left
            if i in (0, 4, 5, 10):
                a0, a1 = 2 * math.pi * i / 12, 2 * math.pi * (i + 1) / 12
                am = (a0 + a1) / 2
                cslab(k, 2.5 * math.cos(am), 2.5 * math.sin(am), 5.5, 6.0, 0.7, 0.3, am + math.pi / 2, O_STONE_CARVED, O_MOSS)
        k.lathe([(1.6, 2.1), (1.6, 3.0), (1.3, 3.9), (0.6, 4.4)], [O_STONE_WIN, O_BRONZE, O_BRONZE], sides=14, jitter=0.1)
        k.lathe([(0.3, 2.15), (0.3, 2.3)], [O_GLOW], sides=8, cap=O_GLOW)                               # the meditation stone
        oss_rubble(k, rng, 0.0, 0.0, 4.2, 16, size=(0.15, 0.45), z0=1.4)

    def lola_citadel(k):
        # the Citadel (canon, TCW "The Citadel" / "Counter Attack" / "Citadel Rescue"; concept art): a maximum-security
        # prison the Republic and the Jedi built in 522 BBY for rogue and fallen Jedi, "on the north-western side of the
        # planet, along a bridge between two lakes of yellow lava, powered by the geothermal" heat; a dark, angular,
        # many-levelled tower on a sheer rock pinnacle, landing platforms, sentry turrets. Here: the pinnacle of basalt,
        # the tower in stepped octagonal tiers with window bands and angled buttress fins, a crown of spikes and an
        # antenna, a cantilevered landing platform, a walled forecourt with guard towers, the causeway west-east across
        # the two lava lakes on pylons, geothermal pipes plunging into the lava at both ends. ~13 map units long
        k.lathe([(4.2, -SKIRT), (3.6, 1.5), (3.0, 3.2), (2.9, 3.6)], [L_BASALT_CRACK, L_BASALT, L_BASALT], sides=10,
                jitter=0.12, cap=L_PLATE)                                                                # the pinnacle
        z = 3.6
        for i, (r, h) in enumerate(((2.3, 2.0), (1.95, 2.0), (1.6, 1.8), (1.3, 1.6), (1.0, 1.4))):    # the tower tiers
            k.lathe([(r, z), (r * 0.94, z + h)], [L_PLATE_WIN if i % 2 == 0 else L_RIB], sides=8, rot=math.pi / 8)
            k.lathe([(r * 1.06, z + h - 0.1), (r * 0.9, z + h + 0.15)], [L_PLATE], sides=8, rot=math.pi / 8, cap=L_PLATE)
            z += h + 0.15
        for j in range(8):                                                                               # buttress fins
            a = 2 * math.pi * j / 8
            k.tube((2.35 * math.cos(a), 2.35 * math.sin(a), 3.6), (1.35 * math.cos(a), 1.35 * math.sin(a), 9.6),
                   0.16, L_PLATE, sides=4)
        for j in range(6):                                                                               # crown spikes
            a = 2 * math.pi * j / 6
            k.tube((0.85 * math.cos(a), 0.85 * math.sin(a), z), (1.1 * math.cos(a), 1.1 * math.sin(a), z + 1.4), 0.12,
                   L_PLATE, sides=4, r1=0.02)
        k.tube((0, 0, z), (0, 0, z + 3.0), 0.08, L_RIB, sides=4)                                        # antenna
        k.lathe([(0.14, z + 3.0), (0.14, z + 3.2)], [L_RED], sides=6, cx=0, cy=0, cap=L_RED)
        k.box(-1.0, 1.6, 8.0, 1.0, 4.4, 8.3, L_PLATE, top=L_PAD)                                         # landing deck
        for x in (-0.8, 0.8):
            k.tube((x, 1.8, 7.6), (x, 4.0, 8.0), 0.1, L_RIB, sides=4)
        k.box(-3.3, -3.3, 3.6, 3.3, -3.0, 4.6, L_PLATE, top=L_PLATE)                                     # forecourt wall
        k.box(-3.3, -3.3, 3.6, -3.0, 0.8, 4.6, L_PLATE, top=L_PLATE)
        k.box(3.0, -3.3, 3.6, 3.3, 0.8, 4.6, L_PLATE, top=L_PLATE)
        for x, y in ((-3.15, -3.15), (3.15, -3.15), (-3.15, 0.8), (3.15, 0.8)):                         # guard towers
            k.lathe([(0.35, 3.6), (0.3, 5.4)], [L_PLATE_WIN], sides=6, cx=x, cy=y, cap=L_PLATE)
            k.lathe([(0.08, 5.4), (0.08, 5.6)], [L_GLOW], sides=4, cx=x, cy=y, cap=L_GLOW)
        for sx in (-1, 1):                                                                               # the causeway
            k.box(sx * 2.6, -0.5, 2.0, sx * 7.4, 0.5, 2.4, L_PLATE, top=L_RIB)
            k.box(sx * 2.6, -0.55, 2.4, sx * 7.4, -0.45, 2.7, L_TRIM)
            k.box(sx * 2.6, 0.45, 2.4, sx * 7.4, 0.55, 2.7, L_TRIM)
            for x in (3.8, 5.2, 6.6):                                                                    # its pylons
                k.lathe([(0.3, -SKIRT), (0.25, 2.0)], [L_RIB], sides=6, cx=sx * x, cy=0.0)
            for y in (-1.2, 1.2):                                                                        # geothermal taps
                k.tube((sx * 4.4, y, 2.2), (sx * 5.0, y * 1.6, -1.5), 0.22, L_RIB, sides=6)
                k.lathe([(0.3, -1.6), (0.3, -1.2)], [L_LAVA], sides=8, cx=sx * 5.0, cy=y * 1.6, cap=L_LAVA)
            k.box(sx * 7.4 - 0.6, -0.9, 1.6, sx * 7.4 + 0.6, 0.9, 3.4, L_PLATE_WIN, top=L_PLATE)        # gatehouses

    def lola_chunk(k, variant):
        # a piece of Lola Sayu's lost southern hemisphere (canon: "nearly the entire southern hemisphere of the planet
        # had disappeared, forming a gravitational belt of planetary debris in its orbit"; the planet "had suffered an
        # unknown event that caused its molten core to be exposed"): cut out of the planet itself, so it is a piece of a
        # sphere: its outer face a curved patch of the old surface (basalt, glowing cracks, crags), its broken sides the
        # planet's cross-section (crust, rock strata, red mantle, glowing interior: L_STRATA), its inner face molten.
        # A closed grid in (angle a, angle b, radius) space, the fracture walls ragged. Tilted so the cut shows from
        # above; floats from LOLA_FLOAT up (the origin stands on the space floor, under the water plane)
        rng = random.Random(f"hod_lola_chunk_{variant}")
        Rp, A, B, depth, tilt, lift = {"a": (9.0, 0.36, 0.3, 0.5, 0.4, 0.0),      # a deep chunk
                                        "b": (10.0, 0.42, 0.2, 0.18, 0.2, 1.2),    # a slab of crust
                                        "c": (8.0, 0.26, 0.24, 0.72, 0.95, 0.6),   # a wedge cut deep
                                        "d": (9.0, 0.12, 0.4, 0.35, 0.7, 2.0)}[variant]   # a sliver
        na, nb, nr = 22, 20, 9                                             # dense: room for real lumps
        ph = [rng.uniform(0, 6.28) for _ in range(40)]

        def fbm(x, y, z, o=0, octaves=4):
            """smooth fractal noise about -1..1 (sums of products of sines with random phases)"""
            t_, amp, f = 0.0, 1.0, 1.0
            for q in range(octaves):
                p0, p1, p2 = ph[(o + 3 * q) % 40], ph[(o + 3 * q + 1) % 40], ph[(o + 3 * q + 2) % 40]
                t_ += amp * math.sin(f * (1.7 * x + 0.6 * y - 0.9 * z) + p0) * math.sin(f * (-0.8 * x + 1.5 * y + 1.1 * z) + p1)                     * (0.6 + 0.4 * math.sin(f * (0.5 * x - 0.7 * y + 1.9 * z) + p2))
                amp, f = amp * 0.55, f * 2.1
            return t_ * 0.9

        def edge(side, s_, l_):                                            # the outline: lobes and bites, per wall
            return 1 + 0.32 * fbm(3 * s_, 2.2 * l_, side * 1.7, o=side * 5, octaves=3)

        def pos(i, j, l):
            fa, fb, fr = i / na, j / nb, l / nr
            a_lo, a_hi = -A * edge(1, fb, fr), A * edge(2, fb, fr)
            b_lo, b_hi = -B * edge(3, fa, fr), B * edge(4, fa, fr)
            aa, bb = a_lo + (a_hi - a_lo) * fa, b_lo + (b_hi - b_lo) * fb
            r_in = Rp * (1 - depth * (1 + 0.15 * fbm(4 * fa, 4 * fb, 0.0, o=11)))
            r = r_in + (Rp - r_in) * fr
            if l == nr:                                                    # the old surface: hills, crags, gouges
                r += 0.9 * fbm(5 * fa, 5 * fb, 1.0, o=17) + 0.7 * max(0.0, fbm(9 * fa, 9 * fb, 2.0, o=23, octaves=3)) ** 1.5
            elif l == 0:                                                   # the torn inner face, molten and lumpy
                r += 0.5 * fbm(7 * fa, 7 * fb, 3.0, o=29)
            d = (math.tan(aa), math.tan(bb), 1.0)
            n_ = math.sqrt(d[0] ** 2 + d[1] ** 2 + 1)
            x, y, z = r * d[0] / n_, r * d[1] / n_, r / n_
            if 0 < l < nr and (i in (0, na) or j in (0, nb)):              # fracture walls: chunky blocks and scoops
                w = 0.6 * fbm(x * 0.8, y * 0.8, z * 0.8, o=31, octaves=3) + 0.12 * fbm(x * 2.2, y * 2.2, z * 2.2, o=7, octaves=2)
                nx, ny = (-1 if i == 0 else 1 if i == na else 0), (-1 if j == 0 else 1 if j == nb else 0)
                x, y = x + nx * w * 1.2, y + ny * w * 1.2
            g = 0.28                                                       # everything a little warped: no flat facets
            return (x + g * fbm(y, z, x, o=13, octaves=2), y + g * fbm(z, x, y, o=19, octaves=2), z + g * fbm(x, y, z, o=37, octaves=2))

        verts = {}

        def v(i, j, l):
            if (i, j, l) not in verts:
                verts[(i, j, l)] = k.bm.verts.new(pos(i, j, l))
            return verts[(i, j, l)]

        def quad(c4, uvs, rect):
            k.put(k.bm.faces.new([v(*c) for c in c4]), uvs, rect)
        for i in range(na):                                                # outer surface and molten inner face
            for j in range(nb):
                uv = ((i / na, j / nb), ((i + 1) / na, j / nb), ((i + 1) / na, (j + 1) / nb), (i / na, (j + 1) / nb))
                quad([(i, j, nr), (i + 1, j, nr), (i + 1, j + 1, nr), (i, j + 1, nr)], uv,
                     L_BASALT_CRACK if fbm(3 * i / na, 3 * j / nb, 5.0, o=3, octaves=2) > -0.25 else L_CRUST)
                quad([(i, j + 1, 0), (i + 1, j + 1, 0), (i + 1, j, 0), (i, j, 0)], uv, L_LAVA)
        for l in range(nr):                                                # the four fracture walls: the strata
            for i in range(na):
                uv = ((i / na, l / nr), ((i + 1) / na, l / nr), ((i + 1) / na, (l + 1) / nr), (i / na, (l + 1) / nr))
                quad([(i, 0, l), (i + 1, 0, l), (i + 1, 0, l + 1), (i, 0, l + 1)], uv, L_STRATA)
                quad([(i + 1, nb, l), (i, nb, l), (i, nb, l + 1), (i + 1, nb, l + 1)], uv, L_STRATA)
            for j in range(nb):
                uv = ((j / nb, l / nr), ((j + 1) / nb, l / nr), ((j + 1) / nb, (l + 1) / nr), (j / nb, (l + 1) / nr))
                quad([(0, j + 1, l), (0, j, l), (0, j, l + 1), (0, j + 1, l + 1)], uv, L_STRATA)
                quad([(na, j, l), (na, j + 1, l), (na, j + 1, l + 1), (na, j, l + 1)], uv, L_STRATA)
        from mathutils import Matrix  # type: ignore
        piece = list(verts.values())
        bmesh.ops.translate(k.bm, verts=piece, vec=(0.0, 0.0, -Rp))        # the old surface's top at z ~ 0
        bmesh.ops.rotate(k.bm, verts=piece, cent=(0, 0, 0), matrix=Matrix.Rotation(tilt, 3, "X"))   # show the cut
        zmin = min(p_.co.z for p_ in piece)
        bmesh.ops.translate(k.bm, verts=piece, vec=(0.0, 0.0, LOLA_FLOAT + lift - zmin))
        for _ in range(5):                                                 # loose shards drifting round it
            a_ = rng.uniform(0, 6.28)
            d_ = Rp * max(A, B) * rng.uniform(1.4, 2.0)
            x, y, z = d_ * math.cos(a_), d_ * math.sin(a_), LOLA_FLOAT + lift + rng.uniform(0.5, 3.0)
            s_ = rng.uniform(0.2, 0.5)
            k.lathe([(0.0, z - s_), (s_, z), (s_ * 0.5, z + s_ * 0.8), (0.0, z + s_ * 1.3)],
                    [L_STRATA, L_BASALT, L_BASALT], sides=5, cx=x, cy=y, jitter=0.3)

    def rv_pillar(k, x, y, z0, h, r, sides=7):
        """a banded rock pillar, wider at the foot and the crown (Cato Neimoidia's arches)"""
        k.lathe([(r * 1.35, z0), (r, z0 + h * 0.3), (r * 0.85, z0 + h * 0.7), (r * 1.1, z0 + h), (r * 0.7, z0 + h * 1.06)],
                [V_ROCK, V_ROCK, V_ROCK, V_ROCK_DARK], sides=sides, cx=x, cy=y, jitter=0.14)

    def rv_arch(k, p0, p1, z, rise, w, segs=8):
        """a stone arch from pillar top p0 to p1 (x, y), rising `rise` at the middle; returns the arch points"""
        pts = []
        for i in range(segs + 1):
            f = i / segs
            pts.append((p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f, z + rise * math.sin(math.pi * f)))
        for a_, b_ in zip(pts, pts[1:]):
            k.tube(a_, b_, w, V_ROCK_DARK, sides=6)
        return pts

    def rv_hang(k, x, y, ztop, rng, big=1.0):
        """a building hung beneath an arch: a cream stone drum with lit windows under a green dome, cables above"""
        r = rng.uniform(0.08, 0.13) * big
        h = rng.uniform(0.2, 0.35) * big
        zb = ztop - rng.uniform(0.25, 0.5) * big - h
        k.lathe([(r * 0.3, zb - 0.06 * big), (r, zb), (r, zb + h)], [V_STONE, V_STONE_WIN], sides=8, cx=x, cy=y)
        k.lathe([(r * 1.05, zb + h), (r * 0.6, zb + h + r * 0.6), (0.0, zb + h + r * 0.85)], [V_DOME, V_DOME], sides=8, cx=x, cy=y)
        k.tube((x, y, zb + h + r * 0.8), (x, y, ztop), 0.012 * big, V_DARK, sides=3)

    def rv_city(k, band, rng):
        # Ringo Vinda's bridge-cities (canon, out-of-universe: the planet designed from the early Cato Neimoidia concept
        # art: cities slung beneath great rock arches): banded rock pillars joined by arches, buildings hung beneath
        # the arches and perched on the pillar crowns, a few at the feet; the heart has more pillars and taller arches.
        # band 1 edge .. 4 heart
        n = 2 + (band >= 3)
        pil = []
        for i in range(n):
            a = 2 * math.pi * i / n + rng.uniform(-0.4, 0.4)
            d = rng.uniform(0.45, 0.65)
            h = rng.uniform(0.7, 1.0) + 0.25 * band
            x, y = d * math.cos(a), d * math.sin(a)
            rv_pillar(k, x, y, -0.3, h, rng.uniform(0.1, 0.14))
            pil.append((x, y, h - 0.3))
            k.lathe([(0.14, h - 0.3), (0.14, h - 0.12), (0.09, h + 0.02), (0.0, h + 0.08)], [V_STONE_WIN, V_DOME, V_DOME],
                    sides=8, cx=x, cy=y)                                                          # a crown house
        for (x0, y0, h0), (x1, y1, h1) in zip(pil, pil[1:] + pil[:1] if n > 2 else pil[1:]):
            pts = rv_arch(k, (x0, y0), (x1, y1), min(h0, h1) - 0.05, 0.12 + 0.04 * band, 0.035)
            for q in pts[2:-2:2]:                                                                     # hung buildings
                rv_hang(k, q[0], q[1], q[2], rng)
        for _ in range(band):                                                                         # at the feet
            x, y = rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8)
            if all(math.hypot(x - a_, y - b_) > 0.25 for a_, b_, _h in pil):
                cslab(k, x, y, -0.3, rng.uniform(0.1, 0.22), 0.09, 0.07, rng.uniform(0, math.pi), V_STONE_WIN, V_ROOF)

    def rv_archcity(k):
        # Vindaport (invented name; the look after the early Cato Neimoidia concept art Ringo Vinda was designed from):
        # two colossal banded pillars joined by a great stone arch, the city hung beneath it in tiers of domed drums
        # on cables, towers and domes along the arch's back, smaller arches and pillars round them, landing platforms
        # on the crowns. ~13 map units long
        rng = random.Random("hod_rv_archcity")
        for x in (-5.2, 5.2):
            rv_pillar(k, x, 0.0, -SKIRT, 9.0 + SKIRT, 1.3, sides=10)
            k.lathe([(1.7, 8.9), (1.7, 9.1)], [V_STONE], sides=12, cx=x, cy=0.0, cap=V_PAD)              # crown platforms
        pts = rv_arch(k, (-5.2, 0.0), (5.2, 0.0), 8.2, 2.2, 0.55, segs=14)
        for q in pts[1:-1]:                                                                          # along the back
            if rng.random() < 0.7:
                h = rng.uniform(0.5, 1.4)
                k.lathe([(0.35, q[2] + 0.4), (0.32, q[2] + 0.4 + h), (0.2, q[2] + 0.6 + h), (0.0, q[2] + 0.75 + h)],
                        [V_STONE_WIN, V_DOME, V_DOME], sides=8, cx=q[0], cy=q[1] + rng.uniform(-0.2, 0.2))
        for i, q in enumerate(pts[2:-2]):                                                            # the hung city
            for dy in (-0.7, 0.0, 0.7):
                rv_hang(k, q[0] + rng.uniform(-0.2, 0.2), q[1] + dy, q[2] - 0.3, rng, big=4.0)
        for x, y, h in ((-2.6, -3.4, 5.0), (2.4, 3.6, 5.5), (-1.0, 3.8, 4.2), (1.8, -3.6, 4.6)):          # lesser pillars
            rv_pillar(k, x, y, -SKIRT, h + SKIRT, 0.55)
        rv_arch(k, (-2.6, -3.4), (1.8, -3.6), 4.6, 0.8, 0.22)
        rv_arch(k, (-1.0, 3.8), (2.4, 3.6), 4.1, 0.7, 0.22)
        for x in (-0.6, 0.4, 1.2):
            rv_hang(k, x, -3.5, 5.0, rng, big=2.5)
            rv_hang(k, x + 0.4, 3.7, 4.6, rng, big=2.5)

    def rv_lift(k):
        # the Station Lift (invented): the shuttle port between Vindaport and the ring station above (a civilian
        # graving dock, canon): a tall slender spire of cream stone and glass, three landing rings round it, beacon
        # lights at the top, a terminal at its foot. ~9 map units tall
        k.lathe([(3.0, -SKIRT), (3.0, 0.4)], [V_STONE], sides=14, cap=V_PAD)
        k.lathe([(1.2, 0.4), (0.9, 3.0), (0.6, 6.5), (0.3, 8.6), (0.0, 9.6)], [V_STONE_WIN, V_GLASS, V_STONE_WIN, V_HULL],
                sides=10)
        for z, r in ((2.2, 2.2), (4.2, 1.8), (6.0, 1.4)):                                            # landing rings
            k.lathe([(r, z), (r, z + 0.15)], [V_HAZARD], sides=16, cap=V_PAD)
            for j in range(4):
                a = math.pi / 2 * j
                k.tube((0.7 * math.cos(a), 0.7 * math.sin(a), z - 0.6), (r * math.cos(a), r * math.sin(a), z), 0.06, V_PANEL, sides=4)
        k.lathe([(0.15, 9.5), (0.15, 9.8)], [V_LIGHT], sides=6, cap=V_LIGHT)
        for a in (0.5, 2.6, 4.7):                                                                    # terminal halls
            cslab(k, 2.2 * math.cos(a), 2.2 * math.sin(a), 0.4, 1.2, 0.7, 0.45, a, V_STONE_WIN, V_DOME)

    def rv_fleet():
        """ships moored in the ring's graving docks (civilian: blockade runners and freighters, shuttles round it)"""
        R, out = RV_RING_R, []
        cx, cy = -R, 0.0                                                    # the planet's centre (origin: the ring's east)
        rng = random.Random("rv_fleet")
        for i in range(RV_DOCKS):
            t = 2 * math.pi * (i + 0.5) / RV_DOCKS
            x, y = cx + (R + 3.6) * math.cos(t), cy + (R + 3.6) * math.sin(t)
            out.append((rng.choice(["foray", "lethisk", "foray"]), x, y, RV_FLOAT + 1.0, t + math.pi / 2, 1.0))
        for _ in range(10):
            t = rng.uniform(0, 2 * math.pi)
            rr = R + rng.uniform(-2.0, 5.0)
            out.append(("chela", cx + rr * math.cos(t), cy + rr * math.sin(t), RV_FLOAT + rng.uniform(3.0, 5.0), t, 1.0))
        return out

    def rv_ring(k):
        # the Ringo Vinda space station (canon + Legends: "a ring-shaped civilian graving dock that encircled the
        # planet"; TCW: a vast ring of grey-tan hull, its decks fought through in the war): a closed ring round the
        # planet's disc, RV_RING_R map units from its centre (origin = the ring's eastern point, on the space floor;
        # everything floats from RV_FLOAT up, over the water plane). The hull in two decks with lit window rows, an
        # outer dock gallery, RV_DOCKS graving docks reaching out with cradle arms round moored ships (rv_fleet), hab
        # towers and radiator fins on the inner side, beacon lights all round. ~85 map units across
        R, z0 = RV_RING_R, RV_FLOAT
        cx, cy = -R, 0.0
        P = lambda r, t, z: (cx + r * math.cos(t), cy + r * math.sin(t), z)
        n = 96
        rng = random.Random("hod_rv_ring")
        for i in range(n):
            t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            tm, half = (t0 + t1) / 2, R * (t1 - t0) / 2 * 1.04
            x, y, _ = P(R, tm, 0)
            cslab(k, x, y, z0 - 0.4, z0 + 0.4, half, 2.1, tm + math.pi / 2, V_PANEL, V_HULL, dt=2.3)       # keel
            cslab(k, x, y, z0 + 0.4, z0 + 1.6, half, 2.3, tm + math.pi / 2, V_HULL_WIN, V_HULL, dt=2.0)     # lower deck
            cslab(k, x, y, z0 + 1.6, z0 + 2.5, half, 1.6, tm + math.pi / 2, V_HULL_WIN, V_PANEL, dt=1.3)    # upper deck
            x, y, _ = P(R + 2.4, tm, 0)
            cslab(k, x, y, z0 + 0.2, z0 + 1.3, half, 0.2, tm + math.pi / 2, V_PANEL, V_LIGHT)               # dock gallery
            roll = rng.random()                                                                     # its back
            bx, by, _ = P(R + rng.uniform(-0.7, 0.7), tm, 0)
            if roll < 0.3:                                                                          # tower blocks
                cslab(k, bx, by, z0 + 2.5, z0 + 2.5 + rng.uniform(0.8, 2.2), half * 0.6, rng.uniform(0.5, 0.9), tm + math.pi / 2,
                      V_HULL_WIN, V_PANEL)
            elif roll < 0.5:                                                                        # domes
                k.lathe([(0.8, z0 + 2.5), (0.6, z0 + 3.1), (0.0, z0 + 3.4)], [V_HULL, V_HULL], sides=10, cx=bx, cy=by)
            elif roll < 0.7:                                                                        # antenna masts
                k.tube((bx, by, z0 + 2.5), (bx, by, z0 + 4.6), 0.07, V_PANEL, sides=4)
                k.lathe([(0.1, z0 + 4.6), (0.1, z0 + 4.8)], [V_LIGHT], sides=4, cx=bx, cy=by, cap=V_LIGHT)
            if i % 4 == 0:                                                                          # beacons
                lx, ly, _ = P(R - 2.3, tm, 0)
                k.lathe([(0.15, z0 + 1.6), (0.15, z0 + 1.9)], [V_LIGHT], sides=4, cx=lx, cy=ly, cap=V_LIGHT)
            if i % 6 == 3:                                                                          # inner hab drums
                hx, hy, _ = P(R - 2.6, tm, 0)
                k.lathe([(0.7, z0 + 0.0), (0.7, z0 + 2.8), (0.4, z0 + 3.3)], [V_HULL_WIN, V_HULL], sides=10, cx=hx, cy=hy,
                        cap=V_PANEL)
            elif i % 6 == 0:                                                                        # radiator fins
                fx, fy, _ = P(R - 2.4, tm, 0)
                cslab(k, fx, fy, z0 + 1.6, z0 + 3.6, half * 0.9, 0.05, tm + math.pi / 2, V_PANEL, V_PANEL)
        for i in range(RV_DOCKS):                                                                   # graving docks
            t = 2 * math.pi * (i + 0.5) / RV_DOCKS
            for side in (-1, 1):                                                                    # cradle arms
                for f in (3.0, 4.4):
                    a_ = t + side * 0.05
                    k.tube(P(R + 2.4, a_, z0 + 0.9), P(R + f, a_, z0 + 1.0), 0.18, V_PANEL, sides=4)
            k.tube(P(R + 2.4, t, z0 + 0.3), P(R + 4.6, t, z0 + 0.3), 0.25, V_HAZARD, sides=4)        # the keel spine
            for a_ in (t - 0.055, t + 0.055):                                                       # gantry posts
                ex, ey, _ = P(R + 4.4, a_, 0)
                k.lathe([(0.2, z0), (0.2, z0 + 3.0)], [V_PANEL], sides=6, cx=ex, cy=ey)
                k.lathe([(0.16, z0 + 3.0), (0.16, z0 + 3.2)], [V_LIGHT], sides=4, cx=ex, cy=ey, cap=V_LIGHT)
            k.tube(P(R + 4.4, t - 0.055, z0 + 3.0), P(R + 4.4, t + 0.055, z0 + 3.0), 0.14, V_HAZARD, sides=4)

    def rh_tower(k, x, y, z0, h, r, crenel=True, sides=8):
        """a ruined round tower of frost-weathered stone with dark arched windows, snow on its broken top"""
        k.lathe([(r * 1.08, z0), (r, z0 + h)], [H_STONE_WIN], sides=sides, cx=x, cy=y, cap=H_SNOW)
        if crenel:
            for j in range(sides):
                if j % 2 == 0:
                    a = 2 * math.pi * j / sides
                    cslab(k, x + r * 0.9 * math.cos(a), y + r * 0.9 * math.sin(a), z0 + h - 0.02, z0 + h + r * 0.35,
                          r * 0.22, r * 0.12, a + math.pi / 2, H_STONE, H_SNOW)

    def rh_wall(k, p0, p1, z0, h, th, rng, broken=0.0):
        """a curtain wall from p0 to p1 with crenels, broken in places, snow along its top"""
        n = max(2, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 0.6))
        a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        for i in range(n):
            f0, f1 = i / n, (i + 1) / n
            if rng.random() < broken:
                continue
            x, y = p0[0] + (p1[0] - p0[0]) * (f0 + f1) / 2, p0[1] + (p1[1] - p0[1]) * (f0 + f1) / 2
            half = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / n / 2 * 1.02
            hh = h * (rng.uniform(0.5, 1.0) if broken else 1.0)
            cslab(k, x, y, z0, z0 + hh, half, th, a, H_STONE, H_SNOW)
            if i % 2 == 0 and not broken:
                cslab(k, x, y, z0 + hh, z0 + hh + th * 1.4, half * 0.5, th, a, H_STONE, H_SNOW)

    def rh_drift(k, rng, cx, cy, spread, n, z0=-0.1):
        """snow drifts heaped against the ruins"""
        for _ in range(n):
            x, y = cx + rng.uniform(-spread, spread), cy + rng.uniform(-spread, spread)
            r = rng.uniform(0.3, 0.8) * spread / 3
            k.lathe([(r, z0), (r * 0.6, z0 + r * 0.35), (0.0, z0 + r * 0.45)], [H_SNOW, H_SNOW], sides=8, cx=x, cy=y,
                    sy=rng.uniform(0.5, 1.0), jitter=0.15)

    def rh_ruins(k, band, rng):
        # the ruins of Rhen Var's lost civilization (Legends: "castles, fortresses and temples"; "snow engulfed the
        # ruins of their creations"; Battlefront's Rhen Var maps): broken towers, roofless halls, arches, half buried in
        # drifts. band 1 edge .. 4 heart
        placed = []

        def spot(r, lim=0.8):
            for _ in range(20):
                x, y = rng.uniform(-lim, lim), rng.uniform(-lim, lim)
                if all(math.hypot(x - a, y - b) > r + c for a, b, c in placed):
                    placed.append((x, y, r))
                    return x, y
            return None
        for _ in range(1 + band // 2):                                                                # towers
            r = rng.uniform(0.08, 0.13)
            p_ = spot(r * 1.3)
            if p_:
                rh_tower(k, *p_, -0.3, rng.uniform(0.5, 0.9) + 0.2 * band, r, crenel=rng.random() < 0.6)
        for _ in range(1 + band):                                                                     # roofless halls
            w, d = rng.uniform(0.12, 0.2), rng.uniform(0.08, 0.14)
            p_ = spot(max(w, d))
            if p_:
                a = rng.uniform(0, math.pi)
                ca, sa = math.cos(a), math.sin(a)
                h = rng.uniform(0.15, 0.32) + 0.04 * band
                for sx, sy, ww, dd in ((0, d, w, 0.02), (0, -d, w, 0.02), (w, 0, 0.02, d), (-w, 0, 0.02, d)):
                    if rng.random() < 0.8:
                        cslab(k, p_[0] + ca * sx - sa * sy, p_[1] + sa * sx + ca * sy, -0.3, h * rng.uniform(0.5, 1.0), ww, dd,
                              a, H_STONE_WIN, H_SNOW)
        if band >= 2:                                                                                 # an arch
            p_ = spot(0.2)
            if p_:
                a = rng.uniform(0, math.pi)
                pts = [(p_[0] + 0.18 * math.cos(math.pi * i / 6) * math.cos(a), p_[1] + 0.18 * math.cos(math.pi * i / 6) * math.sin(a),
                        0.3 * math.sin(math.pi * i / 6)) for i in range(7)]
                for q0, q1 in zip(pts, pts[1:]):
                    k.tube(q0, q1, 0.035, H_STONE, sides=5)
        rh_drift(k, rng, 0.0, 0.0, 0.8, 3 + band)

    def rh_prefab(k, band, rng):
        # Bravo Base's prefab buildings (Legends: "a Republic military facility"; the look is a design choice): white
        # prefab modules with a red stripe and lit windows, small domes, a few masts. band 1 edge .. 4 heart
        placed = []

        def spot(r, lim=0.8):
            for _ in range(20):
                x, y = rng.uniform(-lim, lim), rng.uniform(-lim, lim)
                if all(math.hypot(x - a, y - b) > r + c for a, b, c in placed):
                    placed.append((x, y, r))
                    return x, y
            return None
        for _ in range(2 + band):
            w, d = rng.uniform(0.12, 0.2), rng.uniform(0.06, 0.09)
            p_ = spot(max(w, d))
            if p_:
                a = rng.choice([0.0, math.pi / 2]) + rng.uniform(-0.1, 0.1)
                cslab(k, *p_, -0.3, rng.uniform(0.12, 0.2), w, d, a, rng.choice([H_PANEL_WIN, H_RED]), H_ROOF)
        for _ in range(1 + band // 2):
            r = rng.uniform(0.08, 0.13)
            p_ = spot(r)
            if p_:
                k.lathe([(r, -0.1), (r * 0.7, r * 0.6), (0.0, r * 0.85)], [H_PANEL, H_PANEL], sides=10, cx=p_[0], cy=p_[1])
        if band >= 3:
            p_ = spot(0.03)
            if p_:
                k.tube((p_[0], p_[1], -0.1), (p_[0], p_[1], 0.9), 0.015, H_PANEL, sides=4)
                k.lathe([(0.04, 0.9), (0.04, 0.96)], [H_GLOW], sides=4, cx=p_[0], cy=p_[1], cap=H_GLOW)

    def rh_citadel(k):
        # the Rhen Var Citadel (Legends; Star Wars: Battlefront "Rhen Var: Citadel"; later an Imperial listening outpost):
        # a castle of the lost civilization on a snowy crag: a tall central keep with a spired tower, an inner
        # courtyard, a square curtain wall with round corner towers, a gatehouse and an arched bridge across a ravine,
        # drifts piled against the walls. ~12 map units
        rng = random.Random("hod_rh_citadel")
        k.lathe([(5.4, -SKIRT), (4.6, 1.2), (4.0, 1.6)], [H_STONE, H_SNOW], sides=11, jitter=0.12, cap=H_SNOW)   # crag
        c = [(-3.0, -3.0), (3.0, -3.0), (3.0, 3.0), (-3.0, 3.0)]
        for i in range(4):
            rh_wall(k, c[i], c[(i + 1) % 4], 1.5, 1.7, 0.28, rng, broken=0.12 if i == 2 else 0.0)
            rh_tower(k, *c[i], 1.5, 2.6, 0.65)
        k.box(-1.3, -1.3, 1.5, 1.3, 1.3, 4.6, H_STONE_WIN, top=H_SNOW)                                # the keep
        rh_tower(k, 0.0, 0.0, 4.6, 3.2, 0.7)
        k.lathe([(0.75, 7.8), (0.0, 9.6)], [H_ROOF], sides=8)                                          # its spire
        for x, y in ((-1.3, -1.3), (1.3, -1.3), (1.3, 1.3), (-1.3, 1.3)):
            rh_tower(k, x, y, 4.6, 0.8, 0.32)
        k.box(-0.8, -3.6, 1.5, 0.8, -2.7, 3.6, H_STONE_WIN, top=H_SNOW)                               # gatehouse
        for x in (-0.6, 0.6):
            rh_tower(k, x, -3.6, 1.5, 2.5, 0.35)
        pts = [(0.0, -3.7 - 3.0 * i / 8, 1.3 + 0.6 * math.sin(math.pi * i / 8)) for i in range(9)]       # the bridge
        for q0, q1 in zip(pts, pts[1:]):
            cslab(k, q0[0], (q0[1] + q1[1]) / 2, q0[2] - 0.3, q0[2], 0.6, abs(q1[1] - q0[1]) / 2 * 1.05, 0.0, H_STONE, H_SNOW)
        for y in (-4.6, -5.8):
            k.lathe([(0.3, -SKIRT), (0.25, 1.0)], [H_STONE], sides=6, cx=0.0, cy=y)
        rh_drift(k, rng, 0.0, 0.0, 4.2, 14, z0=1.4)

    def rh_harbor(k):
        # Rhen Var Harbor (Legends: "an ancient location ... in use before the planet was plunged into an ice-age";
        # Battlefront "Rhen Var: Harbor"): stone quays along a frozen bay, the ice sheet locking an old ship's hulk,
        # tall towers with arched windows, an arched bridge across the inlet, roofless warehouses, drifts. ~13 units
        rng = random.Random("hod_rh_harbor")
        k.box(-6.5, -6.0, -SKIRT, -1.0, 6.0, 0.2, H_ICE, top=H_ICE)                                   # the frozen bay
        k.box(-1.0, -6.0, -SKIRT, 4.5, 6.0, 0.8, H_STONE, top=H_SNOW)                                # the quay
        for i in range(6):                                                                           # quay steps
            k.box(-1.6, -5.0 + 2.0 * i, 0.2, -1.0, -4.2 + 2.0 * i, 0.5, H_STONE, top=H_SNOW)
        hull = [(-0.8, 0.2), (0.8, 0.2), (1.0, 0.9), (-1.0, 0.9)]                                     # the frozen hulk
        k.prism([(y, z) for y, z in hull], -5.6, -2.4, H_TIMBER)
        k.prism([(-0.15, 0.9), (0.15, 0.9), (0.05, 3.6), (-0.05, 3.6)], -4.2, -4.0, H_TIMBER)          # its mast
        for x, y, h in ((1.8, -3.8, 5.2), (3.2, 2.6, 4.2), (0.8, 4.4, 3.4)):                          # towers
            rh_tower(k, x, y, 0.8, h, 0.85)
        pts = [(-1.0 - 5.0 * i / 10, 0.0, 1.5 + 1.2 * math.sin(math.pi * i / 10)) for i in range(11)]   # the bridge
        pts = [(x, -3.0, z) for x, _y, z in pts]
        for q0, q1 in zip(pts, pts[1:]):
            cslab(k, (q0[0] + q1[0]) / 2, -3.0, q0[2] - 0.35, q0[2], abs(q1[0] - q0[0]) / 2 * 1.05, 0.55, 0.0, H_STONE, H_SNOW)
        for x in (-2.6, -4.6):
            k.lathe([(0.35, -SKIRT), (0.3, 1.6)], [H_STONE], sides=6, cx=x, cy=-3.0)
        for x, y in ((2.6, -0.8), (1.0, 1.4)):                                                        # warehouses
            rh_wall(k, (x - 1.0, y - 0.6), (x + 1.0, y - 0.6), 0.8, 1.6, 0.18, rng, broken=0.2)
            rh_wall(k, (x - 1.0, y + 0.6), (x + 1.0, y + 0.6), 0.8, 1.6, 0.18, rng, broken=0.3)
            rh_wall(k, (x - 1.0, y - 0.6), (x - 1.0, y + 0.6), 0.8, 1.6, 0.18, rng)
        rh_drift(k, rng, 1.8, 0.0, 3.0, 12, z0=0.7)

    def rh_monument(k):
        # the Jedi monument (Legends: "an old Jedi temple on the planet Rhen Var and the burial site of Ulic
        # Qel-Droma", who spent his last years in exile here): a stepped stone temple, a ring of standing stones, an
        # obelisk over the tomb with a faint light at its foot, all half drifted over. ~9 map units
        rng = random.Random("hod_rh_monument")
        for i, (r, z) in enumerate(((4.0, 0.0), (3.1, 0.6), (2.2, 1.2))):
            k.lathe([(r, -SKIRT if i == 0 else z - 0.6), (r, z + 0.6)], [H_CARVED], sides=4, rot=math.pi / 4,
                    cap=H_SNOW)
        k.lathe([(0.55, 1.8), (0.4, 6.0), (0.0, 6.6)], [H_CARVED, H_STONE], sides=4, rot=math.pi / 4)   # the obelisk
        k.lathe([(0.3, 1.8), (0.3, 2.0)], [H_GLOW], sides=8, cx=0.0, cy=-0.75, cap=H_GLOW)
        for j in range(10):                                                                          # standing stones
            a = 2 * math.pi * j / 10
            if j % 4 != 3:
                cslab(k, 4.6 * math.cos(a), 4.6 * math.sin(a), -0.3, rng.uniform(1.0, 1.8), 0.22, 0.4, a, H_STONE, H_SNOW)
        rh_drift(k, rng, 0.0, 0.0, 4.0, 10, z0=0.0)

    def rh_bravo(k):
        # Bravo Base (Legends: "a Republic military facility located on the arctic world of Rhen Var"; the look is a
        # design choice): white prefab barracks with a red stripe, a hangar with an arched roof, a command dome with a
        # sensor mast and dish, landing pads, a shield-generator dome, turret emplacements at the corners of a
        # perimeter fence. ~11 map units
        k.box(-5.4, -4.6, -SKIRT, 5.4, 4.6, 0.25, H_SNOW, top=H_SNOW)                                # the cleared plateau
        for x in (-3.2, -1.4):                                                                       # barracks
            cslab(k, x, -2.6, 0.25, 1.1, 0.7, 1.6, 0.0, H_PANEL_WIN, H_ROOF)
            cslab(k, x, -2.6, 0.55, 0.75, 0.72, 1.62, 0.0, H_RED, H_RED)
        k.lathe([(1.5, 0.25), (1.5, 0.9), (1.1, 1.8), (0.0, 2.2)], [H_PANEL_WIN, H_PANEL, H_PANEL], sides=16, cx=0.8, cy=0.4)
        k.tube((0.8, 0.4, 2.2), (0.8, 0.4, 5.4), 0.08, H_PANEL, sides=4)                             # the mast
        k.tube((0.8, 0.4, 4.4), (1.5, 0.4, 4.4), 0.06, H_PANEL, sides=4)                             # the dish arm
        k.lathe([(0.15, 4.3), (0.9, 4.6), (1.1, 5.0)], [H_PANEL, H_PANEL], sides=12, cx=1.6, cy=0.4)
        k.lathe([(0.12, 5.4), (0.12, 5.6)], [H_GLOW], sides=4, cx=0.8, cy=0.4, cap=H_GLOW)
        k.box(2.4, -3.4, 0.25, 4.8, -0.4, 0.4, H_PANEL, top=H_PANEL)                                  # the hangar
        k.prism([(-1.9 - 1.5 * math.cos(math.pi * i / 8), 0.4 + 1.6 * math.sin(math.pi * i / 8)) for i in range(9)],
                2.4, 4.8, H_ROOF)                                                                   # its arched roof
        for x, y in ((-3.0, 2.6), (-0.6, 3.0)):                                                     # landing pads
            k.lathe([(1.05, 0.25), (1.05, 0.45)], [H_HAZARD], sides=16, cx=x, cy=y, cap=H_PAD)
        k.lathe([(1.0, 0.25), (0.8, 1.1), (0.0, 1.5)], [H_PANEL, H_GLOW], sides=12, cx=3.6, cy=2.6)     # shield dome
        for x, y in ((-5.0, -4.2), (5.0, -4.2), (5.0, 4.2), (-5.0, 4.2)):                             # turrets
            k.lathe([(0.45, 0.25), (0.45, 0.8), (0.3, 1.05)], [H_PANEL, H_PANEL], sides=8, cx=x, cy=y, cap=H_ROOF)
            k.tube((x, y, 0.95), (x * 0.86, y * 0.86, 1.1), 0.06, H_DARK, sides=4)
        for (x0, y0), (x1, y1) in (((-5.0, -4.2), (5.0, -4.2)), ((5.0, -4.2), (5.0, 4.2)), ((5.0, 4.2), (-5.0, 4.2)),
                                   ((-5.0, 4.2), (-5.0, -4.2))):                                     # the fence
            k.box(min(x0, x1) - 0.04, min(y0, y1) - 0.04, 0.25, max(x0, x1) + 0.04, max(y0, y1) + 0.04, 0.7, H_PANEL)

    def rh_mekhis(k):
        # the ruins of Darth Mekhis' fortress (Legends: set up "in one of the world's snowy mountainscapes" during the
        # Great Galactic War, breached by Satele Shan): angular dark Sith walls and a broken tower on a ridge, spiked
        # buttresses, a collapsed gate, drifts. ~8 map units
        rng = random.Random("hod_rh_mekhis")
        k.lathe([(4.0, -SKIRT), (3.4, 0.8), (2.8, 1.2)], [H_STONE, H_SNOW], sides=7, jitter=0.15, cap=H_SNOW)
        for i in range(5):
            a0, a1 = 2 * math.pi * i / 5, 2 * math.pi * (i + 1) / 5
            if i == 3:
                continue                                                                             # the breach
            p0, p1 = (2.4 * math.cos(a0), 2.4 * math.sin(a0)), (2.4 * math.cos(a1), 2.4 * math.sin(a1))
            am = (a0 + a1) / 2
            cslab(k, (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, 1.1, 1.1 + rng.uniform(1.0, 2.2),
                  math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 2, 0.3, am + math.pi / 2, H_SITH, H_SNOW, wt=None)
            k.tube((2.6 * math.cos(a0), 2.6 * math.sin(a0), 1.1), (3.1 * math.cos(a0), 3.1 * math.sin(a0), 3.0), 0.18,
                   H_SITH, sides=4, r1=0.02)
        k.lathe([(0.9, 1.1), (0.7, 4.4), (0.0, 5.4)], [H_SITH, H_SITH], sides=6, jitter=0.12)               # broken tower
        rh_drift(k, rng, 0.0, 0.0, 3.0, 9, z0=1.0)

    def rh_rakata(k):
        # the Forgotten Rakatan Temple (Legends: "the presence of the Rakatan script", its date disputed by the Duros
        # archaeologist Levat): a dark angular stepped temple of the Infinite Empire's style, its panels of script
        # still glowing faintly, half sunk in the snow. ~8 map units
        rng = random.Random("hod_rh_rakata")
        for i, (r, z, h) in enumerate(((3.6, -SKIRT, 1.0 + SKIRT), (2.7, 1.0, 1.0), (1.8, 2.0, 1.0), (1.0, 3.0, 1.4))):
            k.lathe([(r, z), (r * 0.92, z + h)], [H_RAKATA if i % 2 else H_SITH], sides=6, cap=H_SITH)
        k.lathe([(0.9, 4.4), (0.0, 5.6)], [H_SITH], sides=6)
        for j in range(3):                                                                           # pylons
            a = 2 * math.pi * j / 3 + 0.5
            k.lathe([(0.35, -0.2), (0.15, 3.2), (0.0, 3.6)], [H_RAKATA, H_SITH], sides=4, cx=4.0 * math.cos(a), cy=4.0 * math.sin(a))
        rh_drift(k, rng, 0.0, 0.0, 3.6, 10, z0=0.0)

    for name_, fn_ in (("hod_rh_citadel", rh_citadel), ("hod_rh_harbor", rh_harbor), ("hod_rh_monument", rh_monument),
                       ("hod_rh_bravo", rh_bravo), ("hod_rh_mekhis", rh_mekhis), ("hod_rh_rakata", rh_rakata)):
        build(name_, fn_, tex="hod_rhen")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_h = random.Random(f"hod_rh_ruin{band}{v}")
            build(f"hod_rh_ruin_{band}{v}", lambda k, band=band, rng=rng_h: rh_ruins(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_rhen")
            rng_p = random.Random(f"hod_rh_prefab{band}{v}")
            build(f"hod_rh_prefab_{band}{v}", lambda k, band=band, rng=rng_p: rh_prefab(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_rhen")
    build("hod_rv_archcity", rv_archcity, tex="hod_ringo")
    build("hod_rv_lift", rv_lift, tex="hod_ringo")
    build("hod_rv_ring", rv_ring, tex="hod_ringo",
          extra=lambda: place_ships(rv_fleet(), lambda kind: RV_SHIP_SCALE if kind in ("foray", "lethisk") else 1.0))
    for band in range(1, 5):
        for v in range(1, 5):
            rng_v = random.Random(f"hod_rv_city{band}{v}")
            build(f"hod_rv_city_{band}{v}", lambda k, band=band, rng=rng_v: rv_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_ringo")
    build("hod_lola_citadel", lola_citadel, tex="hod_lola")
    for v in "abcd":                                                       # three turns of each (map objects are
        for t_ in range(LOLA_TURNS):                                       # placed unrotated)
            build(f"hod_lola_chunk_{v}{t_}", lambda k, v=v: lola_chunk(k, v), tex="hod_lola", rot=2 * math.pi * t_ / LOLA_TURNS + 0.4)
    build("hod_oss_library", oss_library, tex="hod_ossus")
    build("hod_oss_knossa", oss_knossa, tex="hod_ossus")
    build("hod_oss_agorn", oss_agorn, tex="hod_ossus")
    build("hod_oss_temple", oss_temple, tex="hod_ossus")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_o = random.Random(f"hod_oss_ruin{band}{v}")
            build(f"hod_oss_ruin_{band}{v}", lambda k, band=band, rng=rng_o: oss_ruin(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_ossus")
            rng_y = random.Random(f"hod_oss_ysanna{band}{v}")
            build(f"hod_oss_ysanna_{band}{v}", lambda k, band=band, rng=rng_y: ysanna_camp(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_ossus")
    build("hod_ruu_university", ruu_university, tex="hod_ruuria")
    build("hod_ruu_great_hive", ruu_great_hive, tex="hod_ruuria")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_r = random.Random(f"hod_ruu_city{band}{v}")
            build(f"hod_ruu_city_{band}{v}", lambda k, band=band, rng=rng_r: ruu_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_ruuria")
    build("hod_etti_spaceport", ak.etti_spaceport, tex="hod_etti")
    build("hod_etti_arcoplex", ak.etti_arcoplex, tex="hod_etti")
    build("hod_etti_dancedome", ak.etti_dancedome, tex="hod_etti")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_e = random.Random(f"hod_etti_city{band}{v}")
            build(f"hod_etti_city_{band}{v}", lambda k, band=band, rng=rng_e: ak.etti_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_etti")
            rng_a = random.Random(f"hod_etti_arco{band}{v}")
            build(f"hod_etti_arco_{band}{v}", lambda k, band=band, rng=rng_a: ak.arco_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_etti")
    def pam_fleet():
        """the ships at the Pammant Docks, shared by the ring and its ships: [(kind, x, y, z, heading, built)] in model
        units (origin = the ring's centre): the Malevolence in the cradle across the ring, the Providence-class ships
        (Invisible Hand, Colicoid Swarm, Lucid Voice: one model) moored on piers outside it"""
        z0 = PAM_FLOAT
        out = [("pam_malevolence", 0.0, 0.0, z0 + 1.3, PAM_CRADLE, 1.0)]
        L = PAM_SHIP_DIMS["pam_invisible_hand"][0]
        for b, built in PAM_PIERS:
            r = PAM_RING_R + 3.0 + L / 2
            out.append(("pam_invisible_hand", r * math.cos(b), r * math.sin(b), z0 + 0.8, b, built))
        return out

    def pam_docks(k):
        # the Pammant Docks (Legends: "a ring-shaped shipyard that orbited the planet Pammant", Free Dac Volunteers
        # Engineering Corps; canon: Pammant built the Providence-class dreadnoughts and the Subjugator-class
        # Malevolence). The user (2026-10-16): the shipyard in space, holding the Separatist ships of WIPGFX/separatists
        # ships 3d. Its look is a design choice, in Separatist tan and grey: a ring of two decks (RING_R across the
        # middle, lit window rows, an outer dock gallery, pressure domes, radiator fins and antenna masts on its
        # back, beacons), a cradle spanning the ring with the Malevolence clamped in it (girder floor, gantry towers,
        # crane bridges, clamp arms, worklights), three piers out from the ring with a Providence-class ship each
        # (the last one, the Lucid Voice, still half in scaffolding), a command spire between two piers.
        # Origin = the ring's centre; everything floats from PAM_FLOAT up, clear of the water plane. ~76 units across
        R, z0 = PAM_RING_R, PAM_FLOAT
        P = lambda r, t, z: (r * math.cos(t), r * math.sin(t), z)
        rng = random.Random("hod_pam_docks")
        fleet = pam_fleet()
        n = 80
        for i in range(n):                                                   # the ring
            t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            tm, half = (t0 + t1) / 2, R * (t1 - t0) / 2 * 1.04
            x, y, _ = P(R, tm, 0)
            cslab(k, x, y, z0 - 0.6, z0 + 0.3, half, 1.9, tm + math.pi / 2, B_HULL, B_HULL, dt=2.4)        # keel
            cslab(k, x, y, z0 + 0.3, z0 + 1.7, half, 2.4, tm + math.pi / 2, B_PLATE_WIN, B_PLATE)          # lower deck
            cslab(k, x, y, z0 + 1.7, z0 + 2.7, half * 0.98, 1.7, tm + math.pi / 2, B_CONC_WIN, B_ROOF, dt=1.3)
            x, y, _ = P(R + 2.6, tm, 0)
            cslab(k, x, y, z0 + 0.4, z0 + 1.4, half, 0.2, tm + math.pi / 2, B_PIPE, B_GLOW)                # gallery
            bx, by, _ = P(R + rng.uniform(-0.8, 0.8), tm, 0)
            roll = rng.random()
            if roll < 0.25:                                                  # pressure domes
                k.lathe([(0.9, z0 + 2.7), (0.75, z0 + 3.3), (0.0, z0 + 3.7)], [B_HULL, B_HULL], sides=12, cx=bx, cy=by)
            elif roll < 0.45:                                                # radiator fins
                for f in (-0.5, 0.0, 0.5):
                    fx, fy, _ = P(R + f, tm, 0)
                    cslab(k, fx, fy, z0 + 2.7, z0 + 4.2, half * 0.7, 0.05, tm + math.pi / 2, B_GIRDER, B_GLOW)
            elif roll < 0.6:                                                 # antenna masts
                k.tube((bx, by, z0 + 2.7), (bx, by, z0 + 5.5), 0.07, B_PIPE, sides=4)
                k.lathe([(0.12, z0 + 5.5), (0.12, z0 + 5.7)], [B_GLOW], sides=4, cx=bx, cy=by, cap=B_GLOW)
            if i % 5 == 0:                                                   # beacons on the inner rim
                lx, ly, _ = P(R - 2.4, tm, 0)
                k.lathe([(0.15, z0 + 1.7), (0.15, z0 + 2.0)], [B_GLOW], sides=6, cx=lx, cy=ly, cap=B_GLOW)
        # the cradle across the ring, the Malevolence in it
        _k, mx, my, mz, head, _b = fleet[0]
        L, W, H = PAM_SHIP_DIMS["pam_malevolence"]
        ch, sh = math.cos(head), math.sin(head)
        at = lambda u, v, zz: (mx + ch * u - sh * v, my + sh * u + ch * v, zz)
        span, side = R + 1.0, W / 2 + 1.6
        for v_ in (-side, side):                                             # the two rails: decks along the ship
            x, y, _ = at(0, v_, 0)
            cslab(k, x, y, z0 - 0.4, z0 + 1.0, span, 0.9, head, B_PLATE_WIN, B_HAZARD)
        for j in range(int(2 * span / 2.0) + 1):                             # the girder floor under the hull
            u = -span + 2.0 * j
            k.tube(at(u, -side, z0 + 0.2), at(u, side, z0 + 0.2), 0.12, B_GIRDER, sides=4)
        for v_ in (-side / 2, 0.0, side / 2):
            k.tube(at(-span, v_, z0 + 0.2), at(span, v_, z0 + 0.2), 0.1, B_GIRDER, sides=4)
        for u in (-14.0, -7.0, 0.0, 7.0, 14.0):                              # gantry towers and crane bridges
            for v_ in (-side, side):
                x, y, _ = at(u, v_, 0)
                cslab(k, x, y, z0 + 1.0, mz + H + 2.2, 0.35, 0.35, head, B_GIRDER, B_HAZARD)
                for zz in (3.0, 6.0):
                    k.lathe([(0.45, z0 + zz), (0.45, z0 + zz + 0.15)], [B_GLOW], sides=6, cx=x, cy=y, cap=B_GLOW)
            x, y, _ = at(u, 0, 0)
            cslab(k, x, y, mz + H + 1.8, mz + H + 2.5, 0.35, side + 0.4, head, B_GIRDER, B_HAZARD)
            tx_, ty_, _ = at(u, rng.uniform(-side * 0.6, side * 0.6), 0)     # trolley and hook line
            cslab(k, tx_, ty_, mz + H + 1.4, mz + H + 2.7, 0.5, 0.5, head, B_HAZARD, B_ROOF)
            k.box(tx_ - 0.03, ty_ - 0.03, mz + H + 0.3, tx_ + 0.03, ty_ + 0.03, mz + H + 1.4, B_DARK)
        for u in (-0.36, -0.12, 0.12, 0.36):                                 # clamp arms from both rails
            for s_ in (-1, 1):
                hull, root = at(u * L, s_ * W * 0.42, mz + H * 0.3), at(u * L, s_ * side, z0 + 1.0)
                k.tube(root, hull, 0.16, B_HAZARD, sides=5)
                k.lathe([(0.28, hull[2] - 0.18), (0.28, hull[2] + 0.18)], [B_PIPE], sides=6, cx=hull[0], cy=hull[1])
        # the piers and their Providence-class ships
        Lp, Wp, Hp = PAM_SHIP_DIMS["pam_invisible_hand"]
        for kind, x, y, z, b, built in fleet[1:]:
            cb, sb = math.cos(b), math.sin(b)
            at = lambda u, v, zz: (x + cb * u - sb * v, y + sb * u + cb * v, zz)
            for s_ in (-1, 1):                                               # the pier's two arms
                px_, py_, _ = at(-0.5, s_ * (Wp / 2 + 1.1), 0)
                cslab(k, px_, py_, z0 - 0.3, z0 + 1.0, Lp / 2 + 2.0, 0.6, b, B_PLATE_WIN, B_PLATE)
                for u in (-0.3, 0.0, 0.3):                                   # docking arms to the hull
                    hull, root = at(u * Lp, s_ * Wp * 0.45, z + Hp * 0.3), at(u * Lp, s_ * (Wp / 2 + 1.1), z0 + 1.0)
                    k.tube(root, hull, 0.12, B_HAZARD, sides=5)
                ex, ey, _ = at(Lp / 2 + 1.0, s_ * (Wp / 2 + 1.1), 0)         # the arm's end tower
                k.lathe([(0.5, z0 - 0.3), (0.45, z0 + 4.5), (0.2, z0 + 5.2)], [B_HULL, B_CONC_WIN], sides=10, cx=ex, cy=ey,
                        cap=B_GLOW)
            hx, hy, _ = at(-Lp / 2 - 1.0, 0, 0)                              # the pier root on the ring's gallery
            cslab(k, hx, hy, z0 - 0.3, z0 + 1.6, 1.2, Wp / 2 + 1.7, b, B_PLATE_WIN, B_ROOF)
            if built < 1:                                                    # the Lucid Voice: scaffold hoops forward
                u0, u1 = -Lp / 2 + Lp * built, Lp / 2
                m_ = max(3, int((u1 - u0) / 0.9))
                for j in range(m_ + 1):
                    u = u0 + (u1 - u0) * j / m_
                    w, h = Wp * 0.6 + 0.2, Hp * (1 - 0.4 * j / m_) + 0.3
                    k.tube(at(u, -w, z - 0.2), at(u, -w, z + h), 0.06, B_GIRDER, sides=3)
                    k.tube(at(u, w, z - 0.2), at(u, w, z + h), 0.06, B_GIRDER, sides=3)
                    k.tube(at(u, -w, z + h), at(u, w, z + h), 0.06, B_GIRDER, sides=3)
                for v_ in (-1, 1):
                    k.tube(at(u0, v_ * (Wp * 0.6 + 0.2), z + Hp * 0.7), at(u1, v_ * (Wp * 0.6 + 0.2), z + Hp * 0.5), 0.05,
                           B_GIRDER, sides=3)
                for _ in range(5):                                           # welding sparks at the seam
                    sx, sy, sz = at(u0 + rng.uniform(-0.2, 0.4), rng.uniform(-Wp, Wp) * 0.4, z + rng.uniform(0.3, Hp))
                    k.box(sx - 0.08, sy - 0.08, sz - 0.08, sx + 0.08, sy + 0.08, sz + 0.08, B_GLOW, top=B_GLOW)
        # the command spire on the ring between the two piers on one side, a bridge to it
        tc = PAM_CRADLE - math.pi / 2
        x, y, _ = P(R + 5.5, tc, 0)
        k.lathe([(2.2, z0 - 1.5), (2.4, z0 + 1.0), (1.8, z0 + 6.0), (1.2, z0 + 11.0)], [B_HULL, B_PLATE_WIN, B_CONC_WIN],
                sides=16, cx=x, cy=y, cap=B_ROOF)
        for zz, r_ in ((4.0, 3.0), (8.0, 2.4)):
            k.lathe([(r_, z0 + zz), (r_, z0 + zz + 0.3)], [B_GLOW], sides=20, cx=x, cy=y, cap=B_PLATE)
        k.lathe([(1.3, z0 + 11.0), (2.2, z0 + 11.6), (2.2, z0 + 12.4), (0.9, z0 + 13.2), (0.0, z0 + 13.4)],
                [B_PLATE_WIN, B_PLATE_WIN, B_ROOF, B_ROOF], sides=16, cx=x, cy=y)
        k.tube((x, y, z0 + 13.3), (x, y, z0 + 16.5), 0.1, B_PIPE, sides=4)
        k.tube(P(R + 2.4, tc, z0 + 1.5), (x, y, z0 + 1.5), 0.6, B_PLATE_WIN, sides=8)

    def pam_ships():
        """the Separatist ships at the Pammant Docks (place_ships, the baked STLs of sketchfab_props.py pam_*)"""
        place_ships(pam_fleet(), lambda kind: 1.0, prefix="")

    def pam_liftport(k):
        # the QFD Lift Port (invented; canon: Pammant's factories build the Separatist warships, Legends: the Pammant
        # Docks in orbit): the heavy-lift spaceport where the Quarren foundries' prefabricated hull sections are
        # lifted to the orbital docks. A long apron along PAM_PORT_A, three raised hexagonal heavy-lift pads in a row,
        # each with a hull section on its cradle waiting for a lifter, a tug lifting one off the middle pad, a
        # Quarren control tower, hangars and a cargo hall, a rail spur bringing sections from the foundries, beacon
        # masts. ~17 units long
        a = PAM_PORT_A
        ca, sa = math.cos(a), math.sin(a)
        at = lambda u, v, zz: (ca * u - sa * v, sa * u + ca * v, zz)
        cslab(k, 0, 0, -SKIRT, 0.15, 8.5, 4.6, a, B_CONC, B_CONC)                       # the apron
        for i, u in enumerate((-5.2, 0.0, 5.2)):                                       # the heavy-lift pads
            x, y, _ = at(u, 1.0, 0)
            k.lathe([(2.4, 0.1), (2.4, 0.55), (2.2, 0.7)], [B_PLATE_WIN, B_HAZARD], sides=6, cx=x, cy=y, rot=a,
                    cap=B_PAD)
            for j in range(6):                                                         # pad lights
                b = a + math.pi / 3 * j
                k.lathe([(0.12, 0.7), (0.12, 0.9)], [B_GLOW], sides=4, cx=x + 2.1 * math.cos(b), cy=y + 2.1 * math.sin(b),
                        cap=B_GLOW)
            lift = 4.5 if i == 1 else 0.0                                              # the middle one is lifting
            for v_ in (-0.9, 0.9):                                                     # the cradle
                cslab(k, *at(u + v_, 1.0, 0)[:2], 0.7, 1.2, 0.25, 1.4, a + math.pi / 2, B_GIRDER, B_HAZARD)
            p0, p1 = at(u, -0.6, 1.9 + lift), at(u, 2.6, 1.9 + lift)                   # the hull section: a ribbed drum
            k.tube(p0, p1, 1.0, B_HULL, sides=10)
            k.tube(at(u, -0.75, 1.9 + lift), p0, 1.08, B_PLATE, sides=10)
            k.tube(p1, at(u, 2.75, 1.9 + lift), 1.08, B_PLATE, sides=10)
            if lift:                                                                   # the lifter tug above it
                tx, ty, _ = at(u, 1.0, 0)
                k.lathe([(1.4, 3.6 + lift), (1.7, 4.0 + lift), (1.2, 4.6 + lift), (0.0, 4.8 + lift)],
                        [B_PLATE, B_HULL, B_ROOF], sides=8, cx=tx, cy=ty)
                for d in ((-0.7, -0.4), (0.7, -0.4), (-0.7, 2.4), (0.7, 2.4)):
                    k.tube(at(u + d[0], d[1], 2.6 + lift), at(u + d[0] * 0.6, 1.0 + (d[1] - 1.0) * 0.4, 3.6 + lift), 0.06,
                           B_PIPE, sides=4)
                for d in (-1.0, 1.0):                                                  # its engine glow
                    gx, gy, _ = at(u + d, 1.0, 0)
                    k.lathe([(0.3, 3.3 + lift), (0.3, 3.6 + lift)], [B_GLOW], sides=8, cx=gx, cy=gy, cap=B_GLOW)
        tx, ty, _ = at(-7.4, -2.6, 0)                                                  # the control tower
        pam_bulb(k, tx, ty, 0.15, 6.5, 0.9)
        k.tube((tx, ty, 6.5), (tx, ty, 8.0), 0.06, B_PIPE, sides=4)
        for u in (-3.0, 2.6):                                                          # hangars and the cargo hall
            x, y, _ = at(u, -3.0, 0)
            bon_hall(k, x, y, 0.15, 1.5, 1.6, 0.9, a)
        x, y, _ = at(7.2, -3.0, 0)
        bon_hall(k, x, y, 0.15, 1.1, 1.0, 0.8, a, saw=False)
        for v_ in (-1.4, -1.0):                                                        # the rail spur
            k.tube(at(-8.4, v_, 0.25), at(8.4, v_, 0.25), 0.06, B_PIPE, sides=4)
        for u in (-4.0, 1.5):                                                          # flatcars with sections on them
            cslab(k, *at(u, -1.2, 0)[:2], 0.25, 0.6, 1.1, 0.4, a, B_RUST, B_ROOF)
            k.tube(at(u - 0.9, -1.2, 1.1), at(u + 0.9, -1.2, 1.1), 0.5, B_HULL, sides=8)
        for u, v_ in ((-8.0, 4.0), (8.0, 4.0), (8.0, -4.2), (-2.6, 4.2), (2.6, 4.2)):  # beacon masts
            x, y, _ = at(u, v_, 0)
            k.tube((x, y, 0.15), (x, y, 3.2), 0.06, B_PIPE, sides=4)
            k.lathe([(0.2, 3.2), (0.2, 3.45)], [B_GLOW], sides=6, cx=x, cy=y, cap=B_GLOW)

    def pam_bulb(k, x, y, z0, h, r, rng=None):
        """a Quarren tower: a slim stem swelling into rounded lit bulbs, a cap and a mast (organic Calamari-style)"""
        k.lathe([(r * 0.75, z0), (r * 0.55, z0 + h * 0.45), (r, z0 + h * 0.62), (r * 1.05, z0 + h * 0.78),
                 (r * 0.7, z0 + h * 0.92), (0.0, z0 + h)], [B_HULL, B_CONC_WIN, B_PLATE_WIN, B_CONC_WIN, B_ROOF], sides=12,
                cx=x, cy=y)
        k.lathe([(r * 1.07, z0 + h * 0.7), (r * 1.07, z0 + h * 0.73)], [B_GLOW], sides=12, cx=x, cy=y)

    def pam_colony(k):
        # Tessar Deep, the Quarren colony's capital (canon: Pammant's Quarren engineers; the city is invented): a round
        # terrace over the mouth of the colony's main shaft, a tall bulbous Quarren spire, five smaller towers round it
        # joined by sky-tubes, the shaft mouth with its headframe, landing pads. ~11 units across
        k.lathe([(5.4, -SKIRT), (5.4, 0.35)], [B_CONC], sides=14, jitter=0.04, cap=B_CONC)               # the terrace
        pam_bulb(k, 0.0, 0.0, 0.35, 9.0, 1.3)
        ring = []
        for i in range(5):
            t = 2 * math.pi * i / 5 + 0.3
            x, y = 3.4 * math.cos(t), 3.4 * math.sin(t)
            h = 4.0 + 1.2 * (i % 3)
            pam_bulb(k, x, y, 0.35, h, 0.75)
            ring.append((x, y, h))
            k.tube((0.3 * x, 0.3 * y, 0.35 + h * 0.55), (x * 0.8, y * 0.8, 0.35 + h * 0.55), 0.18, B_PLATE_WIN, sides=6)
        for (x0, y0, h0), (x1, y1, h1) in zip(ring, ring[1:] + ring[:1]):      # sky-tubes round the ring
            zz = 0.35 + min(h0, h1) * 0.45
            k.tube((x0, y0, zz), (x1, y1, zz), 0.12, B_PIPE, sides=6)
        sx, sy = 3.6 * math.cos(math.pi * 1.25), 3.6 * math.sin(math.pi * 1.25)  # the shaft mouth and its headframe
        k.lathe([(1.2, 0.35), (1.2, 0.5)], [B_HAZARD], sides=14, cx=sx + 1.4, cy=sy - 0.6, cap=B_DARK)
        for d in (-0.8, 0.8):
            k.tube((sx + 1.4 + d, sy - 0.6, 0.5), (sx + 1.4, sy - 0.6, 3.4), 0.1, B_GIRDER, sides=4)
        k.lathe([(0.5, 3.3), (0.5, 3.5)], [B_RUST], sides=10, cx=sx + 1.4, cy=sy - 0.6, cap=B_RUST)
        for t in (0.95, 2.2, 4.4):                                           # landing pads at the terrace's edge
            k.lathe([(0.8, 0.35), (0.8, 0.55)], [B_HAZARD], sides=12, cx=4.6 * math.cos(t + 0.3), cy=4.6 * math.sin(t + 0.3),
                    cap=B_PAD)

    def pam_city(k, band, rng):
        # Pammant's Quarren foundry towns (canon: Quarren engineers, factories building the Separatist navy; Legends:
        # "tunneled"): rounded Quarren towers and domes, foundry halls, shaft headframes over the tunnels, stacks and
        # tanks. band 1 outskirts .. 4 downtown; laid on a 2-unit grid, turned at random
        placed = []

        def spot(r, lim=0.85):
            for _ in range(20):
                x, y = rng.uniform(-lim, lim), rng.uniform(-lim, lim)
                if all(math.hypot(x - a, y - b) > r + c for a, b, c in placed):
                    placed.append((x, y, r))
                    return x, y
            return None
        for _ in range(rng.randint(1, 2)):                                                             # foundry halls
            w, d = rng.uniform(0.18, 0.28), rng.uniform(0.11, 0.17)
            p_ = spot(max(w, d) * 1.05)
            if p_:
                bon_hall(k, *p_, -0.3, rng.uniform(0.16, 0.24) + 0.03 * band, w, d, rng.uniform(0, math.pi),
                         saw=rng.random() < 0.5)
        for _ in range(1 + band):                                                                      # Quarren towers
            r = rng.uniform(0.06, 0.1)
            p_ = spot(r * 1.4)
            if p_:
                pam_bulb(k, *p_, -0.3, rng.uniform(0.5, 0.8) + 0.25 * band + (0.5 * rng.random() if band >= 3 else 0), r)
        for _ in range(rng.randint(1, 2)):                                                             # hab domes
            r = rng.uniform(0.09, 0.14)
            p_ = spot(r * 1.2)
            if p_:
                k.lathe([(r, -0.3), (r, 0.05), (r * 0.7, 0.05 + r * 0.6), (0.0, 0.05 + r * 0.85)],
                        [B_PLATE_WIN, B_HULL, B_HULL], sides=12, cx=p_[0], cy=p_[1])
        if rng.random() < 0.6:                                                                         # a shaft headframe
            p_ = spot(0.12)
            if p_:
                x, y = p_
                k.lathe([(0.1, -0.3), (0.1, 0.02)], [B_HAZARD], sides=8, cx=x, cy=y, cap=B_DARK)
                for d in (-0.09, 0.09):
                    k.tube((x + d, y, 0.0), (x, y, 0.45 + 0.05 * band), 0.012, B_GIRDER, sides=3)
                k.lathe([(0.05, 0.42 + 0.05 * band), (0.05, 0.47 + 0.05 * band)], [B_RUST], sides=8, cx=x, cy=y, cap=B_RUST)
        for _ in range(rng.randint(0, 2)):                                                             # tanks
            r = rng.uniform(0.06, 0.1)
            p_ = spot(r * 1.3)
            if p_:
                bon_tank(k, *p_, -0.3, rng.uniform(0.3, 0.42), r)
        for _ in range(band >= 2):                                                                     # a stack
            p_ = spot(0.05)
            if p_:
                ak.bon_stack(k, *p_, -0.3, rng.uniform(0.9, 1.2) + 0.15 * band, 0.045)

    def mcl_curve(k, p0, p1, bulge, r0, r1, rect, n=6, sides=6):
        """a curved tube from p0 to p1, bowed up by `bulge` at its middle, tapering r0 -> r1 (coral, buttresses)"""
        pts = [(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t,
                p0[2] + (p1[2] - p0[2]) * t + bulge * 4 * t * (1 - t)) for t in [i / n for i in range(n + 1)]]
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            k.tube(a, b, r0 + (r1 - r0) * i / n, rect, sides=sides, r1=r0 + (r1 - r0) * (i + 1) / n)

    def ieg_cliffhold(k):
        # Cliffhold (canon: "a spaceport city that was built directly into the face of a basalt cliff"; TCW "Mystery
        # of a Thousand Moons": round landing pads jutting from the cliff, a quiet port since the spice convoys
        # stopped). The user (2026-10-16): the first design, much smaller, set into the mountain: the cliff is the
        # map's own basalt escarpment (iego_map), this is the city on its face, placed at the face (PLACEMENT hook,
        # scale IEG_CLIFF_SCALE). Along IEG_CLIFF_A, the face at v ~ 0.9, the rock behind it: basalt columns hiding the
        # seam, rows of carved windows, balconies, a hangar mouth at the foot, round pads on cantilevers at three
        # heights, a rounded plaza with stalls below. ~15 units long at scale 1
        rng = random.Random("hod_ieg_cliffhold")
        a = IEG_CLIFF_A
        ca, sa = math.cos(a), math.sin(a)
        at = lambda u, v, zz: (ca * u - sa * v, sa * u + ca * v, zz)
        L = 15.0
        for i in range(30):                                                   # basalt columns along the face
            u = -L / 2 + 0.25 + i * (L - 0.5) / 29
            h = rng.uniform(6.5, 9.4)
            x, y, _ = at(u, 1.3 + rng.uniform(-0.15, 0.15), 0)
            k.lathe([(0.32, -SKIRT), (0.3, h), (0.2, h + 0.15)], [B_BRICK, B_SOOT], sides=6, cx=x, cy=y, rot=a)
        for zz, n in ((1.4, 7), (3.0, 6), (4.6, 5), (6.2, 4)):                 # carved window rows in the face
            for j in range(n):
                u = -L / 2 + 1.2 + (L - 2.4) * (j + 0.5) / n + rng.uniform(-0.4, 0.4)
                cslab(k, *at(u, 0.85, 0)[:2], zz, zz + 0.9, rng.uniform(0.5, 0.9), 0.12, a, B_CONC_WIN, B_CONC)
                if rng.random() < 0.5:                                        # a rounded balcony under it
                    bx, by, _ = at(u, 0.45, 0)
                    k.lathe([(0.5, zz - 0.12), (0.5, zz)], [B_PLATE], sides=10, cx=bx, cy=by, sy=0.6, cap=B_PLATE)
        hx, hy, _ = at(-1.5, 0.8, 0)                                          # the hangar mouth: an arch
        k.lathe([(1.6, 0.0), (1.6, 1.4), (1.2, 2.0), (0.6, 2.3), (0.0, 2.4)], [B_DARK, B_DARK, B_DARK, B_DARK], sides=12,
                cx=hx, cy=hy, sy=0.35)
        for u, zz, r in ((-5.2, 2.2, 1.0), (3.6, 3.6, 1.2), (-2.4, 5.4, 0.9), (5.8, 1.4, 0.9), (0.8, 6.8, 0.8)):
            px, py, _ = at(u, -r - 0.1, 0)                                    # round pads on cantilevers
            k.lathe([(r * 0.5, zz - 0.5), (r, zz - 0.15), (r, zz)], [B_PLATE, B_PLATE], sides=16, cx=px, cy=py, cap=B_PAD)
            k.tube(at(u, 0.9, zz - 1.4), (px, py, zz - 0.25), 0.12, B_PIPE, sides=6)
            k.tube(at(u, 0.9, zz - 0.1), (px, py, zz - 0.1), 0.14, B_PLATE, sides=8)
            for j in range(4):
                b = 2 * math.pi * j / 4
                k.lathe([(0.07, zz), (0.07, zz + 0.15)], [B_GLOW], sides=6, cx=px + r * 0.9 * math.cos(b),
                        cy=py + r * 0.9 * math.sin(b), cap=B_GLOW)
        px, py, _ = at(0.0, -2.6, 0)                                          # the plaza at its foot: rounded
        k.lathe([(7.6, -SKIRT), (7.6, 0.2)], [B_CONC], sides=24, cx=px, cy=py, rot=a, sy=0.3, cap=B_DUST)
        for _ in range(6):                                                    # stalls with round awnings
            u, v_ = rng.uniform(-5.5, 5.5), rng.uniform(-3.6, -1.6)
            x, y, _ = at(u, v_, 0)
            r = rng.uniform(0.3, 0.5)
            k.lathe([(r, 0.2), (r, 0.6), (r * 1.2, 0.7), (0.0, 0.95)], [rng.choice([B_PLATE, B_CONC_WIN]), B_RUST, B_RUST],
                    sides=8, cx=x, cy=y)

    def ieg_laserweb(k):
        # the LaserWeb Defense Station (canon: the Separatists' station whose laser field kept anyone from leaving
        # Iego, destroyed by Kenobi and Skywalker). The user (2026-10-16): in space, no beams. Placed in orbit east of
        # the planet (iego_map.PLACEMENT hook, IEG_WEB_AT); everything floats from IEG_WEB_FLOAT up. A ribbed core
        # sphere with lit bands and spires, a round tube ring on six spokes, cylindrical hangar pods with vulture
        # droids racked on them, six long truss spars ending in emitter pods with glowing lenses. ~36 across
        z0 = IEG_WEB_FLOAT
        zc = z0 + 6.0
        prof = [(0.0, zc - 5.2)] + [(5.0 * math.sin(math.pi * i / 10), zc - 5.0 * math.cos(math.pi * i / 10))
                                    for i in range(1, 10)] + [(0.0, zc + 5.2)]
        k.lathe(prof, [B_PLATE, B_PLATE_WIN, B_PLATE, B_HULL, B_PLATE_WIN, B_HULL, B_PLATE, B_PLATE_WIN, B_PLATE, B_ROOF],
                sides=24)
        for zz in (zc - 1.6, zc + 1.6):
            r = math.sqrt(max(0.1, 25.0 - (zz - zc) ** 2)) + 0.06
            k.lathe([(r, zz - 0.12), (r, zz + 0.12)], [B_GLOW], sides=24)
        for s_ in (-1, 1):
            k.lathe([(1.2, zc + s_ * 5.0), (0.8, zc + s_ * 6.2), (0.6, zc + s_ * 7.6), (0.15, zc + s_ * 9.5)],
                    [B_HULL, B_PLATE_WIN, B_PLATE], sides=12)
        R, n = 9.0, 40
        for i in range(n):                                                    # the ring: a round tube
            t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            k.tube((R * math.cos(t0), R * math.sin(t0), zc), (R * math.cos(t1), R * math.sin(t1), zc), 0.9,
                   B_PLATE_WIN if i % 4 else B_HULL, sides=10)
        for j in range(6):
            b = 2 * math.pi * j / 6
            ca_, sa_ = math.cos(b), math.sin(b)
            k.tube((4.6 * ca_, 4.6 * sa_, zc), (R * ca_, R * sa_, zc), 0.45, B_HULL, sides=10)        # spoke
            hb = b + math.pi / 6                                              # a hangar pod between the spokes
            hx, hy = (R + 1.8) * math.cos(hb), (R + 1.8) * math.sin(hb)
            k.lathe([(0.0, zc - 1.6), (1.1, zc - 1.2), (1.3, zc - 0.2), (1.3, zc + 0.6), (0.8, zc + 1.4), (0.0, zc + 1.6)],
                    [B_HULL, B_PLATE_WIN, B_PLATE, B_PLATE_WIN, B_ROOF], sides=14, cx=hx, cy=hy)
            k.lathe([(1.32, zc - 0.05), (1.32, zc + 0.15)], [B_GLOW], sides=14, cx=hx, cy=hy)
            for q in (-0.5, 0.5):                                             # vulture droids racked on it
                vx, vy = hx + 1.3 * math.cos(hb + q), hy + 1.3 * math.sin(hb + q)
                for s_ in (-1, 1):
                    k.tube((vx, vy, zc + 1.0), (vx + 0.5 * math.cos(hb + q + s_ * 1.2), vy + 0.5 * math.sin(hb + q + s_ * 1.2),
                                                 zc + 1.4), 0.06, B_HULL, sides=5, r1=0.02)
            L0, L1 = R + 0.8, R + 11.0                                        # the truss spar out to the emitter
            for dz, dv in ((-0.5, -0.5), (-0.5, 0.5), (0.5, 0.0)):
                k.tube((L0 * ca_ - dv * sa_, L0 * sa_ + dv * ca_, zc + dz), (L1 * ca_ - dv * sa_, L1 * sa_ + dv * ca_, zc + dz),
                       0.11, B_GIRDER, sides=6)
            for q in range(8):
                l0, l1 = L0 + (L1 - L0) * q / 8, L0 + (L1 - L0) * (q + 1) / 8
                k.tube((l0 * ca_ + 0.5 * sa_, l0 * sa_ - 0.5 * ca_, zc - 0.5), (l1 * ca_, l1 * sa_, zc + 0.5), 0.05, B_GIRDER,
                       sides=4)
                k.tube((l1 * ca_ - 0.5 * sa_, l1 * sa_ + 0.5 * ca_, zc - 0.5), (l0 * ca_, l0 * sa_, zc + 0.5), 0.05, B_GIRDER,
                       sides=4)
            px, py = (L1 + 1.4) * ca_, (L1 + 1.4) * sa_                       # the emitter pod and its lens
            k.lathe([(0.0, zc - 2.0), (1.0, zc - 1.6), (1.4, zc - 0.4), (1.4, zc + 0.6), (0.9, zc + 1.6), (0.4, zc + 2.0)],
                    [B_HULL, B_PLATE_WIN, B_PLATE, B_HULL, B_GLOW], sides=16, cx=px, cy=py, cap=B_GLOW)
            k.tube((L1 * ca_, L1 * sa_, zc), (px + 1.6 * ca_, py + 1.6 * sa_, zc), 0.55, B_HULL, sides=12, r1=0.85)
            k.lathe([(0.7, zc - 0.1), (0.7, zc + 0.1)], [B_GLOW], sides=16, cx=px + 1.65 * ca_, cy=py + 1.65 * sa_)

    def ieg_choir(k):
        # the Choir Alignment (Legends: a valley "100 meters across and shaped like a nine-pointed star", clearly
        # artificial; iego_map.carve sinks the star into the ground). The user (2026-10-16): nothing square. Rough
        # dry-stone walls of rounded boulders along the star's outline in two courses, a weathered menhir with a
        # carved band at each of the nine points, a ring of rounded stones and a round three-tier dais with a glowing
        # crystal at the centre, tumbled boulders. ~11 units across
        rng = random.Random("hod_ieg_choir")
        pts = []
        for i in range(18):
            b = math.pi * i / 9
            r = 5.2 if i % 2 == 0 else 2.6
            pts.append((r * math.cos(b), r * math.sin(b)))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):               # the walls: boulders, two courses
            ln = math.hypot(x1 - x0, y1 - y0)
            n = max(3, int(ln / 0.55))
            for q in range(n + 1):
                t = q / n
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                r = rng.uniform(0.3, 0.42)
                k.lathe([(r, -SKIRT), (r * 1.05, r * 0.6), (r * 0.7, r * 1.25), (0.0, r * 1.45)], [B_BRICK, B_BRICK, B_SOOT],
                        sides=7, cx=x, cy=y, jitter=0.15, rot=rng.uniform(0, 1))
                if q % 2:                                                     # the upper course
                    r2 = r * 0.75
                    k.lathe([(r2, r * 1.1), (r2 * 1.05, r * 1.1 + r2 * 0.6), (0.0, r * 1.1 + r2 * 1.3)], [B_BRICK, B_SOOT],
                            sides=6, cx=x, cy=y, jitter=0.15, rot=rng.uniform(0, 1))
        for x, y in pts[::2]:                                                 # the menhirs
            ox, oy = x * 1.1, y * 1.1
            k.lathe([(0.75, -SKIRT), (0.8, 0.3), (0.42, 0.55)], [B_DUST, B_DUST], sides=9, cx=ox, cy=oy, jitter=0.12)
            k.lathe([(0.42, 0.5), (0.46, 1.8), (0.4, 3.0), (0.26, 3.9), (0.0, 4.4)], [B_BRICK, B_BRICK, B_BRICK, B_SOOT],
                    sides=8, cx=ox, cy=oy, sy=0.75, jitter=0.07, rot=math.atan2(oy, ox))
            k.lathe([(0.47, 1.6), (0.47, 1.9)], [B_CONC_WIN], sides=8, cx=ox, cy=oy, sy=0.75, rot=math.atan2(oy, ox))
        for j in range(9):                                                    # the inner ring of stones
            b = 2 * math.pi * j / 9 + 0.17
            k.lathe([(0.2, -SKIRT), (0.2, 0.6), (0.12, 0.85), (0.0, 0.95)], [B_BRICK, B_BRICK, B_SOOT], sides=7,
                    cx=1.6 * math.cos(b), cy=1.6 * math.sin(b), jitter=0.1)
        for r, zz in ((1.0, 0.25), (0.75, 0.5), (0.5, 0.75)):                 # the dais
            k.lathe([(r, -SKIRT), (r, zz - 0.05), (r - 0.05, zz)], [B_CONC, B_DUST], sides=18, cap=B_DUST)
        k.lathe([(0.15, 0.75), (0.25, 1.3), (0.0, 1.9)], [B_GLOW, B_GLOW], sides=6)                  # the crystal
        for _ in range(12):                                                   # tumbled boulders
            b, r = rng.uniform(0, 2 * math.pi), rng.uniform(3.0, 6.4)
            s = rng.uniform(0.2, 0.4)
            k.lathe([(s, -0.1), (s * 1.05, s * 0.5), (0.0, s * 1.1)], [B_BRICK, B_SOOT], sides=7, cx=r * math.cos(b),
                    cy=r * math.sin(b), jitter=0.18)

    def ieg_boneyard(k):
        # the Boneyard (Legends: the largest of Iego's bone piles, "gigantic skeletons of unknown creatures", north of
        # the Scatter). One colossal skeleton lying in sand drifts along a gentle S: vertebrae with tall spines and
        # side processes down to a tapering tail, eleven pairs of tapering ribs (some broken), a pelvis, fore and hind
        # limbs ending in claws, a long skull with a lower jaw, rows of teeth, sockets and swept-back horns; a smaller
        # skeleton fallen beside it, loose skulls and bones round. ~20 units long
        rng = random.Random("hod_ieg_boneyard")
        spine = lambda u: (u, 1.1 * math.sin(u * 0.25), 1.2 - 0.04 * max(0.0, -u - 4.0) ** 1.6)
        for _ in range(9):                                                    # sand drifts round the bones
            u = rng.uniform(-9, 9)
            x, y, _ = spine(u)
            k.lathe([(rng.uniform(1.8, 3.0), -SKIRT), (rng.uniform(1.4, 2.2), 0.2), (0.6, rng.uniform(0.5, 0.9))],
                    [B_DUST, B_DUST], sides=9, cx=x + rng.uniform(-2, 2), cy=y + rng.uniform(-2, 2), sy=0.6, jitter=0.2)
        for j in range(26):                                                   # vertebrae, tail to neck
            u = -11.0 + j * 0.78
            x, y, zz = spine(u)
            s = 1.0 if u > -4 else max(0.35, 1.0 - (-4 - u) * 0.09)
            k.lathe([(0.32 * s, zz - 0.3 * s), (0.42 * s, zz), (0.32 * s, zz + 0.3 * s)], [B_DUST, B_DUST], sides=7,
                    cx=x, cy=y, cap=B_DUST)
            k.tube((x, y, zz + 0.2 * s), (x - 0.25 * s, y, zz + (1.4 if -4 < u < 5 else 0.7) * s), 0.12 * s, B_DUST, sides=4,
                   r1=0.04 * s)
            for t in (-1, 1):
                k.tube((x, y, zz), (x, y + t * 0.6 * s, zz + 0.1), 0.08 * s, B_DUST, sides=4, r1=0.03 * s)
        for j in range(11):                                                   # the ribs
            u = -3.2 + j * 0.75
            x, y, zz = spine(u)
            ln = 4.8 - 0.22 * abs(j - 4)
            for t in (-1, 1):
                if rng.random() < 0.18:
                    ln_ = ln * 0.45                                            # a broken one
                else:
                    ln_ = ln
                mid = (x + 0.3, y + t * ln_ * 0.55, zz + ln_ * 0.35)
                end = (x + 0.7, y + t * ln_ * 0.75, -0.3 if ln_ == ln else zz + ln_ * 0.2)
                mcl_curve(k, (x, y + t * 0.3, zz), mid, ln_ * 0.12, 0.2, 0.15, B_DUST, n=4, sides=6)
                mcl_curve(k, mid, end, -ln_ * 0.05, 0.15, 0.06, B_DUST, n=4, sides=6)
        x, y, zz = spine(-4.2)                                                # the pelvis
        k.lathe([(1.1, zz - 0.4), (1.3, zz), (0.8, zz + 0.5)], [B_DUST, B_DUST], sides=8, cx=x, cy=y, sy=1.5, cap=B_SOOT)
        for (u0, side) in ((-4.2, -1), (-4.2, 1), (4.6, -1), (4.6, 1)):         # the limbs and claws
            x, y, zz = spine(u0)
            knee = (x + 0.8 * (1 if u0 > 0 else -1), y + side * 2.2, zz + 0.6)
            foot = (x + 1.6 * (1 if u0 > 0 else -1), y + side * 3.4, -0.2)
            k.tube((x, y + side * 0.8, zz), knee, 0.28, B_DUST, sides=6, r1=0.2)
            k.tube(knee, foot, 0.2, B_DUST, sides=6, r1=0.14)
            for c in (-0.4, 0.0, 0.4):
                k.tube(foot, (foot[0] + 0.9 * math.cos(c + (0 if u0 > 0 else math.pi)),
                              foot[1] + 0.9 * math.sin(c + (0 if u0 > 0 else math.pi)), -0.1), 0.08, B_DUST, sides=4, r1=0.01)
        x, y, zz = spine(9.4)                                                 # the skull
        k.lathe([(0.0, zz - 0.6), (1.3, zz - 0.3), (1.5, zz + 0.4), (1.1, zz + 1.1), (0.0, zz + 1.4)],
                [B_DUST, B_DUST, B_DUST, B_DUST], sides=10, cx=x, cy=y, sy=0.8, jitter=0.05)
        snout_end = (x + 3.6, y, zz - 0.1)
        k.tube((x + 0.8, y, zz + 0.1), snout_end, 0.9, B_DUST, sides=8, r1=0.35)
        k.tube((x + 0.6, y, zz - 0.7), (x + 3.4, y + 0.2, zz - 0.9), 0.5, B_DUST, sides=7, r1=0.25)        # the jaw
        for j in range(7):                                                    # teeth
            tx = x + 1.1 + j * 0.35
            for t in (-1, 1):
                k.tube((tx, y + t * 0.45, zz - 0.35), (tx + 0.05, y + t * 0.45, zz - 0.75), 0.06, B_DUST, sides=3, r1=0.0)
        for t in (-1, 1):
            k.lathe([(0.32, zz + 0.3), (0.32, zz + 0.75)], [B_DARK], sides=7, cx=x + 0.6, cy=y + t * 0.95, cap=B_DARK)
            mcl_curve(k, (x - 0.3, y + t * 0.8, zz + 1.0), (x - 3.2, y + t * 2.2, zz + 3.0), 0.9, 0.32, 0.03, B_DUST,
                      n=6, sides=6)
        for j in range(6):                                                    # the smaller skeleton
            u = -2.5 + j * 0.65
            mcl_curve(k, (u, -6.2, -0.2), (u + 0.5, -3.6, -0.3), 2.2, 0.16, 0.06, B_DUST, n=5, sides=5)
            k.lathe([(0.2, -0.2), (0.26, 0.1), (0.2, 0.3)], [B_DUST, B_DUST], sides=6, cx=u, cy=-6.2, cap=B_DUST)
        for _ in range(4):                                                    # loose skulls
            sx, sy_ = rng.uniform(-9, 9), rng.choice([-1, 1]) * rng.uniform(4.5, 7)
            k.lathe([(0.0, -0.2), (0.5, 0.0), (0.45, 0.4), (0.0, 0.6)], [B_DUST, B_DUST, B_DUST], sides=8, cx=sx, cy=sy_,
                    sy=0.75)
        for _ in range(18):                                                   # loose bones
            bx, by = rng.uniform(-11, 12), rng.uniform(-7.5, 7.5)
            b, ln = rng.uniform(0, math.pi), rng.uniform(0.8, 2.6)
            k.tube((bx, by, 0.0), (bx + ln * math.cos(b), by + ln * math.sin(b), 0.12), rng.uniform(0.08, 0.16), B_DUST, sides=5)

    def ieg_city(k, band, rng):
        # Iegoan towns (canon: Cliffhold and its quiet spaceport; Legends: villages; the look is a design choice; the
        # user, 2026-10-16: nothing square): domed adobe huts, round basalt towers with flared caps, low domes,
        # spice tanks, pads. band 1 outskirts .. 4 downtown; on a 2-unit grid
        placed = []

        def spot(r, lim=0.85):
            for _ in range(20):
                x, y = rng.uniform(-lim, lim), rng.uniform(-lim, lim)
                if all(math.hypot(x - a, y - b) > r + c for a, b, c in placed):
                    placed.append((x, y, r))
                    return x, y
            return None
        for _ in range(2 + band):                                                                  # domed huts
            r = rng.uniform(0.07, 0.12)
            p_ = spot(r * 1.15)
            if p_:
                h = rng.uniform(0.12, 0.22) + 0.04 * band
                k.lathe([(r, -0.3), (r, h), (r * 0.8, h + r * 0.45), (r * 0.4, h + r * 0.75), (0.0, h + r * 0.85)],
                        [B_CONC_WIN, B_DUST, B_DUST, B_DUST], sides=10, cx=p_[0], cy=p_[1], sy=rng.uniform(0.8, 1.0),
                        rot=rng.uniform(0, 1))
        for _ in range(band // 2 + 1):                                                             # round towers
            r = rng.uniform(0.05, 0.075)
            p_ = spot(r * 1.4)
            if p_:
                h = rng.uniform(0.5, 0.8) + 0.2 * band
                k.lathe([(r * 1.1, -0.3), (r, h * 0.6), (r * 0.9, h), (r * 1.3, h + 0.06), (r * 1.2, h + 0.12),
                         (0.0, h + 0.22)], [B_BRICK, B_PLATE_WIN, B_BRICK, B_ROOF, B_ROOF], sides=10, cx=p_[0], cy=p_[1])
        if rng.random() < 0.5:                                                                     # spice tanks
            p_ = spot(0.1)
            if p_:
                bon_tank(k, *p_, -0.3, rng.uniform(0.3, 0.4), 0.07)
        if band >= 2 and rng.random() < 0.35:                                                      # a pad
            p_ = spot(0.14)
            if p_:
                k.lathe([(0.13, -0.3), (0.13, 0.05)], [B_PLATE], sides=14, cx=p_[0], cy=p_[1], cap=B_PAD)
    def lia_hull(k, x, y, z, head, L, built=1.0, cruiser=True):
        """a Republic-era Sienar hull lying along `head` (no TIEs: the user, 2026-10-16): a round tapering body of
        tube sections (pointed prow, a swelling midship, a flared stern with engine glows), a raised bridge blister,
        swept fins; `built` < 1 leaves the prow as bare ribs. Cruiser = long hull with dorsal fin, else a courier: a
        ball cockpit with two down-curving wings (the Star Courier line)"""
        ch, sh = math.cos(head), math.sin(head)
        at = lambda u, v, zz: (x + ch * u - sh * v, y + sh * u + ch * v, z + zz)
        if cruiser:
            prof = [(-0.5, 0.0), (-0.42, 0.06), (-0.3, 0.1), (-0.1, 0.13), (0.15, 0.13), (0.35, 0.11), (0.47, 0.09),
                    (0.5, 0.1)]
            cut = -0.5 + built
            for (u0, r0), (u1, r1) in zip(prof, prof[1:]):
                if u0 >= cut:
                    break
                rr = (lambda q: q * L)
                k.tube(at(rr(u0), 0, rr(0.13)), at(rr(min(u1, cut)), 0, rr(0.13)), max(0.02, rr(r0)), B_HULL, sides=14,
                       r1=max(0.02, rr(r1)))
            if built < 1:                                                    # bare ribs over the unplated prow
                for q in range(9):
                    u = cut + (0.5 - cut) * q / 8
                    r = L * 0.12 * (1 - 0.5 * q / 8)
                    for t in range(8):
                        a0, a1 = 2 * math.pi * t / 8, 2 * math.pi * (t + 1) / 8
                        k.tube(at(u * L, r * math.cos(a0), L * 0.13 + r * math.sin(a0)),
                               at(u * L, r * math.cos(a1), L * 0.13 + r * math.sin(a1)), 0.04, B_GIRDER, sides=3)
                k.tube(at(cut * L, 0, L * 0.13), at(0.5 * L, 0, L * 0.13), 0.08, B_GIRDER, sides=5)
            for s_ in (-1, 1):                                               # engines and swept fins at the stern
                k.tube(at(L * 0.42, s_ * L * 0.07, L * 0.11), at(L * 0.53, s_ * L * 0.07, L * 0.11), L * 0.035, B_PLATE,
                       sides=10)
                k.tube(at(L * 0.53, s_ * L * 0.07, L * 0.11), at(L * 0.54, s_ * L * 0.07, L * 0.11), L * 0.03, B_GLOW,
                       sides=10)
                k.tube(at(L * 0.25, s_ * L * 0.1, L * 0.11), at(L * 0.45, s_ * L * 0.26, L * 0.07), L * 0.018, B_PLATE,
                       sides=6, r1=L * 0.006)
            if built >= 1:
                k.tube(at(-0.05 * L, 0, L * 0.22), at(0.2 * L, 0, L * 0.25), L * 0.035, B_PLATE_WIN, sides=10,
                       r1=L * 0.025)                                         # the bridge blister
                k.tube(at(0.2 * L, 0, L * 0.24), at(0.42 * L, 0, L * 0.36), L * 0.012, B_PLATE, sides=6, r1=L * 0.004)
        else:
            k.lathe([(0.0, z), (L * 0.18, z + L * 0.05), (L * 0.22, z + L * 0.2), (L * 0.18, z + L * 0.35),
                     (0.0, z + L * 0.4)], [B_HULL, B_PLATE_WIN, B_HULL, B_HULL], sides=14, cx=x, cy=y)   # the ball cockpit
            for s_ in (-1, 1):                                               # wings curving down
                mcl_curve(k, at(0, s_ * L * 0.18, L * 0.22), at(L * 0.1, s_ * L * 0.55, -L * 0.05), L * 0.18, L * 0.05,
                          L * 0.03, B_PLATE, n=5, sides=8)
                mcl_curve(k, at(L * 0.18, s_ * L * 0.16, L * 0.22), at(L * 0.3, s_ * L * 0.5, -L * 0.02), L * 0.14,
                          L * 0.03, L * 0.02, B_RUST, n=5, sides=6)
            k.tube(at(L * 0.2, 0, L * 0.2), at(L * 0.48, 0, L * 0.2), L * 0.08, B_PLATE, sides=10, r1=L * 0.05)
            k.tube(at(L * 0.48, 0, L * 0.2), at(L * 0.5, 0, L * 0.2), L * 0.05, B_GLOW, sides=10)

    def lia_shipyard(k):
        # the Lianna shipyards in orbit (Legends: "Class IB civilian shipyards, capable of producing cruisers"; Sienar's
        # yards; the user, 2026-10-16: in space, Republic-era ships, no TIEs). Origin = the hub, placed east of the
        # planet (lianna_map.PLACEMENT hook, LIA_YARD_AT); everything floats from LIA_YARD_FLOAT up. A hexagonal frame
        # of round trusses round a hub station (a ribbed sphere on a ring), three slips radiating from the hub with a
        # cruiser hull in each (one still bare ribs at the prow), gantry arches over them, couriers docked at the
        # frame's corners, beacons. ~44 across
        z0 = LIA_YARD_FLOAT
        zc = z0 + 3.0
        rng = random.Random("hod_lia_yard")
        R = 20.0
        corners = [(R * math.cos(math.pi / 3 * j), R * math.sin(math.pi / 3 * j)) for j in range(6)]
        for (x0, y0), (x1, y1) in zip(corners, corners[1:] + corners[:1]):  # the hexagonal frame: round trusses
            for dz, dv in ((-0.6, 0), (0.6, -0.5), (0.6, 0.5)):
                nx, ny = -(y1 - y0), (x1 - x0)
                nl = math.hypot(nx, ny)
                ox, oy = nx / nl * dv, ny / nl * dv
                k.tube((x0 + ox, y0 + oy, zc + dz), (x1 + ox, y1 + oy, zc + dz), 0.22, B_PLATE, sides=10)
            for q in range(10):
                t0, t1 = q / 10, (q + 1) / 10
                k.tube((x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0, zc - 0.6), (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1, zc + 0.6),
                       0.07, B_GIRDER, sides=4)
        for j, (x, y) in enumerate(corners):                                # corner stations with couriers docked
            k.lathe([(0.0, zc - 2.0), (1.4, zc - 1.4), (1.7, zc), (1.4, zc + 1.4), (0.0, zc + 2.0)],
                    [B_HULL, B_PLATE_WIN, B_PLATE_WIN, B_HULL], sides=18, cx=x, cy=y)
            k.lathe([(1.75, zc - 0.1), (1.75, zc + 0.1)], [B_GLOW], sides=18, cx=x, cy=y)
            out = math.pi / 3 * j
            lia_hull(k, x + 3.4 * math.cos(out), y + 3.4 * math.sin(out), zc - 0.5, out + math.pi, 3.0, cruiser=False)
        prof = [(0.0, zc - 3.6)] + [(3.4 * math.sin(math.pi * i / 8), zc - 3.4 * math.cos(math.pi * i / 8))
                                    for i in range(1, 8)] + [(0.0, zc + 3.6)]
        k.lathe(prof, [B_PLATE, B_PLATE_WIN, B_HULL, B_PLATE_WIN, B_PLATE_WIN, B_HULL, B_PLATE_WIN, B_ROOF], sides=24)   # hub
        for i in range(32):                                                 # the hub's ring
            t0, t1 = 2 * math.pi * i / 32, 2 * math.pi * (i + 1) / 32
            k.tube((5.2 * math.cos(t0), 5.2 * math.sin(t0), zc), (5.2 * math.cos(t1), 5.2 * math.sin(t1), zc), 0.5,
                   B_PLATE_WIN if i % 4 else B_RUST, sides=10)
        for j in range(3):                                                  # spokes to the ring
            b = 2 * math.pi * j / 3 + math.pi / 6
            k.tube((3.2 * math.cos(b), 3.2 * math.sin(b), zc), (5.2 * math.cos(b), 5.2 * math.sin(b), zc), 0.3, B_HULL, sides=8)
        for j in range(3):                                                  # the slips, a cruiser in each
            b = 2 * math.pi * j / 3 - math.pi / 6
            cb, sb = math.cos(b), math.sin(b)
            L = 11.0
            mid = 6.0 + L / 2 + 0.5
            lia_hull(k, mid * cb, mid * sb, zc - L * 0.13, b + math.pi, L, built=0.55 if j == 1 else 1.0)
            for q in range(5):                                              # gantry arches over the slip
                u = 6.5 + L * q / 4
                for t in range(9):
                    a0, a1 = math.pi * t / 9, math.pi * (t + 1) / 9
                    p0 = (u * cb - 2.4 * math.cos(a0) * sb, u * sb + 2.4 * math.cos(a0) * cb, zc - 1.2 + 2.6 * math.sin(a0))
                    p1 = (u * cb - 2.4 * math.cos(a1) * sb, u * sb + 2.4 * math.cos(a1) * cb, zc - 1.2 + 2.6 * math.sin(a1))
                    k.tube(p0, p1, 0.1, B_GIRDER if q % 2 else B_PLATE, sides=6)
                k.lathe([(0.15, zc + 1.4), (0.15, zc + 1.6)], [B_GLOW], sides=6, cx=u * cb, cy=u * sb, cap=B_GLOW)
            for s_ in (-1, 1):                                              # the slip's rails
                k.tube((6.0 * cb - s_ * 2.4 * sb, 6.0 * sb + s_ * 2.4 * cb, zc - 1.2),
                       ((7.0 + L) * cb - s_ * 2.4 * sb, (7.0 + L) * sb + s_ * 2.4 * cb, zc - 1.2), 0.16, B_PLATE, sides=8)
        for _ in range(16):                                                 # beacons along the frame
            j = rng.randrange(6)
            t = rng.random()
            (x0, y0), (x1, y1) = corners[j], corners[(j + 1) % 6]
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            k.lathe([(0.12, zc + 0.8), (0.12, zc + 1.0)], [B_GLOW], sides=6, cx=x, cy=y, cap=B_GLOW)

    def jab_bore(k):
        # the Jobreth Bore (Legends: "huge digging and boring machines continued to cut ever deeper into the surface
        # of the dying planet"; this one and its name are a design choice): a huge tracked machine on the rim of its
        # stepped pit (iego-style carve in jabiim_map), its ribbed drill cone angled down into the pit, a long conveyor
        # arm carrying spoil to a heap, exhaust stacks, a cab, worklights. ~17 long
        rng = random.Random("hod_jab_bore")
        for s_ in (-1, 1):                                                    # the tracks: long rounded belts
            k.tube((-5.0, s_ * 2.2, 0.9), (4.0, s_ * 2.2, 0.9), 0.95, B_SOOT, sides=12)
            for q in range(7):
                k.lathe([(0.55, 0.0), (0.55, 0.2)], [B_PIPE], sides=10, cx=-4.5 + q * 1.4, cy=s_ * 2.85, cap=B_PIPE)
        k.tube((-5.4, 0.0, 2.8), (3.8, 0.0, 2.8), 2.0, B_HULL, sides=16, r1=1.8)                      # the body
        k.tube((-5.6, 0.0, 2.8), (-5.4, 0.0, 2.8), 1.6, B_PLATE, sides=16)
        for q in range(5):                                                    # ribs round the body
            u = -4.5 + q * 2.0
            k.tube((u, 0.0, 2.8), (u + 0.25, 0.0, 2.8), 2.1, B_RUST, sides=16)
        k.lathe([(1.0, 4.4), (1.0, 5.6), (0.7, 6.0)], [B_PLATE_WIN, B_ROOF], sides=12, cx=-3.0, cy=0.0, cap=B_ROOF)   # cab
        for x in (-1.0, 0.4, 1.8):                                            # exhaust stacks
            k.lathe([(0.32, 4.2), (0.26, 7.0), (0.32, 7.2)], [B_SOOT, B_SOOT], sides=10, cx=x, cy=1.0)
        # the drill: a ribbed cone angled down into the pit
        p0, p1 = (4.2, 0.0, 2.6), (9.6, 0.0, -1.6)
        k.tube(p0, (5.2, 0.0, 1.8), 1.6, B_PLATE, sides=16)
        steps = 8
        for q in range(steps):
            t0, t1 = q / steps, (q + 1) / steps
            a = tuple(5.2 + (p1[0] - 5.2) * t0 if i == 0 else (0.0 if i == 1 else 1.8 + (p1[2] - 1.8) * t0) for i in range(3))
            b = tuple(5.2 + (p1[0] - 5.2) * t1 if i == 0 else (0.0 if i == 1 else 1.8 + (p1[2] - 1.8) * t1) for i in range(3))
            k.tube(a, b, 1.7 * (1 - t0) + 0.05, B_GIRDER if q % 2 else B_PIPE, sides=14, r1=1.7 * (1 - t1) + 0.05)
        # the conveyor arm to the spoil heap, the heap
        k.tube((-2.0, 1.6, 4.2), (-6.5, 9.0, 3.2), 0.35, B_GIRDER, sides=6)
        for q in range(6):
            t = q / 5
            x, y = -2.0 - 4.5 * t, 1.6 + 7.4 * t
            k.tube((x, y, 0.0), (x, y, 4.2 - 1.0 * t), 0.12, B_PIPE, sides=5)
        k.lathe([(3.4, -SKIRT), (3.0, 0.8), (1.8, 2.4), (0.0, 3.0)], [B_DUST, B_DUST, B_DUST], sides=12, cx=-6.8, cy=9.4,
                jitter=0.15)
        for _ in range(6):                                                    # worklights
            x, y = rng.uniform(-5, 4), rng.choice([-1, 1]) * 3.4
            k.tube((x, y, 0.0), (x, y, 3.6), 0.05, B_PIPE, sides=4)
            k.lathe([(0.14, 3.6), (0.14, 3.8)], [B_GLOW], sides=6, cx=x, cy=y, cap=B_GLOW)

    build("hod_bon_spaceport", ak.bon_spaceport, tex="hod_bonadan")
    build("hod_bon_shipyard", bon_shipyard, tex="hod_bonadan", extra=bon_ships)
    build("hod_bon_weather", ak.bon_weather, tex="hod_bonadan")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_b = random.Random(f"hod_bon_city{band}{v}")
            build(f"hod_bon_city_{band}{v}", lambda k, band=band, rng=rng_b: ak.bon_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_bonadan")
    build("hod_pam_docks", pam_docks, tex="hod_pammant", extra=pam_ships)
    build("hod_pam_liftport", pam_liftport, tex="hod_pammant")
    build("hod_pam_colony", pam_colony, tex="hod_pammant")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_p = random.Random(f"hod_pam_city{band}{v}")
            build(f"hod_pam_city_{band}{v}", lambda k, band=band, rng=rng_p: pam_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_pammant")
    for name, fn in (("hod_sal_taleucema", ak.sal_taleucema), ("hod_sal_spaceport", ak.sal_spaceport),
                     ("hod_sal_lawquane", ak.sal_lawquane), ("hod_sal_cloning", ak.sal_cloning)):
        build(name, fn, tex="hod_saleucami")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_s = random.Random(f"hod_sal_city{band}{v}")
            build(f"hod_sal_city_{band}{v}", lambda k, band=band, rng=rng_s: ak.sal_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_saleucami")
    for name, fn in (("hod_tel_thani", ak.tel_thani), ("hod_tel_terminal", ak.tel_terminal), ("hod_tel_academy", ak.tel_academy),
                     ("hod_tel_caverns", ak.tel_caverns), ("hod_tel_rz", ak.tel_rz)):
        build(name, fn, tex="hod_telos")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_t = random.Random(f"hod_tel_city{band}{v}")
            build(f"hod_tel_city_{band}{v}", lambda k, band=band, rng=rng_t: ak.tel_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_telos")
    for name, fn in (("hod_ser_carannia", ak.ser_carannia), ("hod_ser_assembly", ak.ser_assembly),
                     ("hod_ser_castle", ak.ser_castle), ("hod_ser_borgin", ak.ser_borgin), ("hod_ser_spike", ak.ser_spike)):
        build(name, fn, tex="hod_serenno")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_r = random.Random(f"hod_ser_city{band}{v}")
            build(f"hod_ser_city_{band}{v}", lambda k, band=band, rng=rng_r: ak.ser_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_serenno")
    for name, fn in (("hod_yav_temple", ak.yav_temple), ("hod_yav_exarkun", ak.yav_exarkun),
                     ("hod_yav_borundi", ak.yav_borundi)):
        build(name, fn, tex="hod_yavin")
    for name, fn in (("hod_cel_city", ak.cel_city_centre), ("hod_cel_control", ak.cel_control),
                     ("hod_cel_hospital", ak.cel_hospital), ("hod_cel_gularg", ak.cel_gularg)):
        build(name, fn, tex="hod_celanon")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_c = random.Random(f"hod_cel_town{band}{v}")
            build(f"hod_cel_town_{band}{v}", lambda k, band=band, rng=rng_c: ak.cel_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_celanon")
            rng_v = random.Random(f"hod_cel_village{band}{v}")
            build(f"hod_cel_village_{band}{v}", lambda k, band=band, rng=rng_v: ak.cel_village(k, band, rng),
                  shader="PdxMeshSnow", tex="hod_celanon")
    for name, fn in (("hod_bot_palace", ak.bot_palace), ("hod_bot_elevator", ak.bot_elevator), ("hod_bot_yards", ak.bot_yards),
                     ("hod_bot_orbital", ak.bot_orbital), ("hod_bot_northbase", ak.bot_northbase), ("hod_bot_southbase", ak.bot_southbase)):
        build(name, fn, tex="hod_botajef")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_b = random.Random(f"hod_bot_city{band}{v}")
            build(f"hod_bot_city_{band}{v}", lambda k, band=band, rng=rng_b: ak.bot_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_botajef")
    for name, fn in (("hod_axx_capital", ak.axx_capital), ("hod_axx_fossfog", ak.axx_fossfog),
                     ("hod_axx_oreport", ak.axx_oreport)):
        build(name, fn, tex="hod_axxila")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_a = random.Random(f"hod_axx_city{band}{v}")
            build(f"hod_axx_city_{band}{v}", lambda k, band=band, rng=rng_a: ak.axx_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_axxila")
    for name, fn in (("hod_cit_daplona", ak.cit_daplona), ("hod_cit_training", ak.cit_training),
                     ("hod_cit_prison", ak.cit_prison), ("hod_cit_mansion", ak.cit_mansion)):
        build(name, fn, tex="hod_ciutric")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_i = random.Random(f"hod_cit_city{band}{v}")
            build(f"hod_cit_city_{band}{v}", lambda k, band=band, rng=rng_i: ak.cit_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_ciutric")
    for name, fn in (("hod_ces_chikatlik", ak.ces_chikatlik), ("hod_ces_cybernetics", ak.ces_cybernetics),
                     ("hod_ces_penitentiary", ak.ces_penitentiary), ("hod_ces_jantos", ak.ces_jantos),
                     ("hod_ces_droidworks", ak.ces_droidworks), ("hod_ces_fungus", ak.ces_fungus)):
        build(name, fn, tex="hod_cestus")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_c = random.Random(f"hod_ces_city{band}{v}")
            build(f"hod_ces_city_{band}{v}", lambda k, band=band, rng=rng_c: ak.ces_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_cestus")
    for name, fn in (("hod_dat_lair", ak.dat_lair), ("hod_dat_village", ak.dat_village), ("hod_dat_arena", ak.dat_arena),
                     ("hod_dat_singing", ak.dat_singing), ("hod_dat_nardithi", ak.dat_nardithi)):
        build(name, fn, tex="hod_dathomir")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_d = random.Random(f"hod_dat_hamlet{band}{v}")
            build(f"hod_dat_hamlet_{band}{v}", lambda k, band=band, rng=rng_d: ak.dat_hamlet(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_dathomir")
    for name, fn in (("hod_man_sundari", ak.man_sundari), ("hod_man_keldabe", ak.man_keldabe),
                     ("hod_man_beskar", ak.man_beskar), ("hod_man_dwcamp", ak.man_dwcamp),
                     ("hod_man_cityofbone", ak.man_cityofbone), ("hod_man_norgbral", ak.man_norgbral)):
        build(name, fn, tex="hod_mandalore")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_m = random.Random(f"hod_man_dome{band}{v}")
            build(f"hod_man_dome_{band}{v}", lambda k, band=band, rng=rng_m: ak.man_dome(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_mandalore")
            rng_t = random.Random(f"hod_man_town{band}{v}")
            build(f"hod_man_town_{band}{v}", lambda k, band=band, rng=rng_t: ak.man_town(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_mandalore")
    for name, fn in (("hod_tar_spires", ak.tar_spires), ("hod_tar_pit", ak.tar_pit), ("hod_tar_swoop", ak.tar_swoop),
                     ("hod_tar_jedi", ak.tar_jedi)):
        build(name, fn, tex="hod_taris")
    for name, fn in (("hod_way_tantiss", ak.way_tantiss), ("hod_way_colony", ak.way_colony),
                     ("hod_way_council", ak.way_council)):
        build(name, fn, tex="hod_wayland")
    for name, fn in (("hod_con_city", ak.con_city), ("hod_con_mines", ak.con_mines), ("hod_con_hideout", ak.con_hideout)):
        build(name, fn, tex="hod_concordia")
    for name, fn in (("hod_bra_yards", ak.bra_yards), ("hod_bra_platform", ak.bra_platform), ("hod_bra_tower", ak.bra_tower),
                     ("hod_bra_rail", ak.bra_rail), ("hod_bra_town", ak.bra_town)):
        build(name, fn, tex="hod_bracca")
    for name, fn in (("hod_tra_forak", ak.tra_forak), ("hod_tra_market", ak.tra_market), ("hod_tra_lodge", ak.tra_lodge),
                     ("hod_tra_shrine", ak.tra_shrine)):
        build(name, fn, tex="hod_trandosha")
    for name, fn in (("hod_nyr_locus", ak.nyr_locus), ("hod_nyr_prosperity", ak.nyr_prosperity), ("hod_nyr_arena", ak.nyr_arena),
                     ("hod_nyr_finalrest", ak.nyr_finalrest)):
        build(name, fn, tex="hod_nyriaan")
    for name, fn in (("hod_crs_port", ak.crs_port), ("hod_crs_retreat", ak.crs_retreat), ("hod_crs_resort", ak.crs_resort),
                     ("hod_crs_station", ak.crs_station)):
        build(name, fn, tex="hod_corsin")
    for name, fn in (("hod_kas_kachirho", ak.kas_kachirho), ("hod_kas_refinery", ak.kas_refinery),
                     ("hod_kas_rwookrrorro", ak.kas_rwookrrorro), ("hod_kas_caverns", ak.kas_caverns),
                     ("hod_kas_wartaki", ak.kas_wartaki)):
        build(name, fn, tex="hod_kashyyyk")
    for name, fn in (("hod_ond_iziz", ak.ond_iziz), ("hod_ond_nest", ak.ond_nest), ("hod_ond_camp", ak.ond_camp),
                     ("hod_ond_kira", ak.ond_kira), ("hod_ond_lodge", ak.ond_lodge)):
        build(name, fn, tex="hod_onderon")
    for name, fn in (("hod_umb_capital", ak.umb_capital), ("hod_umb_airbase", ak.umb_airbase), ("hod_umb_bunker", ak.umb_bunker),
                     ("hod_umb_academy", ak.umb_academy)):
        build(name, fn, tex="hod_umbara")
    for name, fn in (("hod_col_hive", ak.col_hive), ("hod_col_nest", ak.col_nest), ("hod_col_spawn", ak.col_spawn)):
        build(name, fn, tex="hod_colla")
    for name, fn in (("hod_rus_olmondo", ak.rus_olmondo), ("hod_rus_mausoleum", ak.rus_mausoleum),
                     ("hod_rus_cave", ak.rus_cave), ("hod_rus_camp", ak.rus_camp), ("hod_rus_fort", ak.rus_fort)):
        build(name, fn, tex="hod_ruusan")
    for name, fn in (("hod_ith_tafanda", ak.ith_tafanda), ("hod_ith_tarintha", ak.ith_tarintha),
                     ("hod_ith_cloudmother", ak.ith_cloudmother), ("hod_ith_falls", ak.ith_falls)):
        build(name, fn, tex="hod_ithor")
    for name, fn in (("hod_om_city", ak.om_cityhall), ("hod_om_worlport", ak.om_worlport),
                     ("hod_om_junkyard", ak.om_junkyard), ("hod_om_oldcity", ak.om_oldcity), ("hod_om_garnik", ak.om_garnik)):
        build(name, fn, tex="hod_ordmantell")
    for name, fn in (("hod_gar_pesktda", ak.gar_pesktda), ("hod_gar_university", ak.gar_university),
                     ("hod_gar_combine", ak.gar_combine), ("hod_gar_vlassy", ak.gar_vlassy)):
        build(name, fn, tex="hod_garqi")
    build("hod_aga_calna", ak.aga_calna, tex="hod_agamar", extra=lambda: place_ships(ak.AGA_CALNA_FLEET, lambda kind: 1.0))
    for name, fn in (("hod_aga_university", ak.aga_university),
                     ("hod_aga_ruins", ak.aga_ruins), ("hod_aga_bridges", ak.aga_bridges), ("hod_aga_ranch", ak.aga_ranch)):
        build(name, fn, tex="hod_agamar")
    for name, fn in (("hod_ot_depot", ak.ot_depot), ("hod_ot_salvage", ak.ot_salvage)):
        build(name, fn, tex="hod_ordtrasi")
    ot_scale = lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0     # the yards hold our ship models
    build("hod_ot_yards", ak.ot_yards, tex="hod_ordtrasi", extra=lambda: place_ships(ak.OT_YARD_FLEET, ot_scale))
    build("hod_ot_orbital", ak.ot_orbital, tex="hod_ordtrasi", extra=lambda: place_ships(ak.OT_ORBIT_FLEET, ot_scale))
    for name, fn in (("hod_dan_khoonda", ak.dan_khoonda), ("hod_dan_enclave", ak.dan_enclave), ("hod_dan_rakatan", ak.dan_rakatan),
                     ("hod_dan_cave", ak.dan_cave), ("hod_dan_matale", ak.dan_matale), ("hod_dan_sandral", ak.dan_sandral),
                     ("hod_dan_grove", ak.dan_grove)):
        build(name, fn, tex="hod_dantooine")
    for name, fn in (("hod_myg_jygat", ak.myg_jygat), ("hod_myg_city", ak.myg_city), ("hod_myg_mesas", ak.myg_mesas),
                     ("hod_myg_hammertong", ak.myg_hammertong), ("hod_myg_mines", ak.myg_mines)):
        build(name, fn, tex="hod_mygeeto")
    for name, fn in (("hod_yag_hive", ak.yag_hive), ("hod_yag_center", ak.yag_center), ("hod_yag_works", ak.yag_works)):
        build(name, fn, tex="hod_yaga_minor")
    build("hod_yag_spaceport", ak.yag_spaceport, tex="hod_yaga_minor", extra=lambda: place_ships(ak.YAG_PORT_FLEET, lambda kind: 1.0))
    build("hod_yag_yards", ak.yag_yards, tex="hod_yaga_minor",
          extra=lambda: place_ships(ak.YAG_YARD_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    for name, fn in (("hod_ans_cuipernam", ak.ans_cuipernam), ("hod_ans_borokii", ak.ans_borokii),
                     ("hod_ans_dashbalar", ak.ans_dashbalar)):
        build(name, fn, tex="hod_ansion")
    for name, fn in (("hod_ilu_temple", ak.ilu_temple), ("hod_ilu_tonvarr", ak.ilu_tonvarr), ("hod_ilu_circle", ak.ilu_circle),
                     ("hod_ilu_ruins", ak.ilu_ruins)):
        build(name, fn, tex="hod_ilum")
    for name, fn in (("hod_dor_dorshan", ak.dor_dorshan), ("hod_dor_dorgalk", ak.dor_dorgalk), ("hod_dor_barando", ak.dor_barando),
                     ("hod_dor_enclave", ak.dor_enclave), ("hod_dor_caverns", ak.dor_caverns)):
        build(name, fn, tex="hod_dorin")
    for name, fn in (("hod_yin_tolkachorn", ak.yin_tolkachorn), ("hod_yin_garrison", ak.yin_garrison), ("hod_yin_depot", ak.yin_depot),
                     ("hod_yin_daacorp", ak.yin_daacorp), ("hod_yin_zerpen", ak.yin_zerpen)):
        build(name, fn, tex="hod_yinchorr")
    for name, fn in (("hod_cha_hanna", ak.cha_hanna), ("hod_cha_emita", ak.cha_emita), ("hod_cha_nayli", ak.cha_nayli),
                     ("hod_cha_brionelle", ak.cha_brionelle), ("hod_cha_canyons", ak.cha_canyons)):
        build(name, fn, tex="hod_chandrila")
    for name, fn in (("hod_cor_curamelle", ak.cor_curamelle), ("hod_cor_sienar", ak.cor_sienar), ("hod_cor_academy", ak.cor_academy), ("hod_cor_tasjon", ak.cor_tasjon), ("hod_cor_crullov", ak.cor_crullov)):
        build(name, fn, tex="hod_corulag")
    for name, fn in (("hod_ark_adascopolis", ak.ark_adascopolis), ("hod_ark_mines", ak.ark_mines), ("hod_ark_praxeum", ak.ark_praxeum), ("hod_ark_veeshas", ak.ark_veeshas)):
        build(name, fn, tex="hod_arkania")
    for name, fn in (("hod_anx_citadel", ak.anx_citadel), ("hod_anx_works", ak.anx_works), ("hod_anx_college", ak.anx_college), ("hod_anx_fort", ak.anx_fort), ("hod_anx_hydro", ak.anx_hydro)):
        build(name, fn, tex="hod_anaxes")
    for name, fn in (("hod_ess_calamar", ak.ess_calamar), ("hod_ess_esprix", ak.ess_esprix), ("hod_ess_togatto", ak.ess_togatto), ("hod_ess_nurrale", ak.ess_nurrale)):
        build(name, fn, tex="hod_esseles")
    for name, fn in (("hod_cos_senate", ak.cos_senate), ("hod_cos_temple", ak.cos_temple), ("hod_cos_executive", ak.cos_executive),
                     ("hod_cos_courts", ak.cos_courts), ("hod_cos_processional", ak.cos_processional),
                     ("hod_cos_monument", ak.cos_monument), ("hod_cos_republica", ak.cos_republica), ("hod_cos_opera", ak.cos_opera),
                     ("hod_cos_outlander", ak.cos_outlander), ("hod_cos_works", ak.cos_works), ("hod_cos_level1313", ak.cos_level1313),
                     ("hod_cos_diner", ak.cos_diner)):
        build(name, fn, tex="hod_coruscant_lm")
    for name, fn in (("hod_cos_compor", ak.cos_compor), ("hod_cos_exchange", ak.cos_exchange)):
        build(name, fn, tex="hod_coruscant_lm")
    build("hod_ark_novania", ak.ark_novania, tex="hod_arkania", extra=lambda: place_ships(ak.ARK_PORT_FLEET, lambda kind: 1.0))
    build("hod_ess_starport", ak.ess_starport, tex="hod_esseles", extra=lambda: place_ships(ak.ESS_PORT_FLEET, lambda kind: 1.0))
    for name, fn in (("hod_car_academy", ak.car_academy), ("hod_car_district", ak.car_district), ("hod_car_field", ak.car_field), ("hod_car_teeth", ak.car_teeth), ("hod_car_survival", ak.car_survival), ("hod_car_corsairs", ak.car_corsairs)):
        build(name, fn, tex="hod_carida")
    build("hod_car_valor", ak.car_valor, tex="hod_carida",
          extra=lambda: place_ships(ak.CAR_VALOR_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    for name, fn in (("hod_bal_binprime", ak.bal_binprime), ("hod_bal_market", ak.bal_market), ("hod_bal_port", ak.bal_port), ("hod_bal_sobrik", ak.bal_sobrik), ("hod_bal_bugtown", ak.bal_bugtown)):
        build(name, fn, tex="hod_balmorra")
    build("hod_bal_arms", ak.bal_arms, tex="hod_balmorra")
    build("hod_bal_outpost", ak.bal_outpost, tex="hod_balmorra")
    for name, fn in (("hod_ald_palace", ak.ald_palace), ("hod_ald_aldera", ak.ald_aldera), ("hod_ald_university", ak.ald_university), ("hod_ald_crevasse", ak.ald_crevasse), ("hod_ald_sanctuary", ak.ald_sanctuary), ("hod_ald_killik", ak.ald_killik)):
        build(name, fn, tex="hod_alderaan")
    for name, fn in (("hod_tyt_temple", ak.tyt_temple), ("hod_tyt_henge", ak.tyt_henge), ("hod_tyt_retreat", ak.tyt_retreat), ("hod_tyt_banlanding", ak.tyt_banlanding), ("hod_tyt_thoyor", ak.tyt_thoyor)):
        build(name, fn, tex="hod_tython")
    for name, fn in (("hod_fre_incom", ak.fre_incom), ("hod_fre_arches", ak.fre_arches), ("hod_fre_range", ak.fre_range), ("hod_fre_warehouse", ak.fre_warehouse)):
        build(name, fn, tex="hod_fresia")
    for name, fn in (("hod_foe_hajibar", ak.foe_hajibar), ("hod_foe_launch", ak.foe_launch), ("hod_foe_refinery", ak.foe_refinery), ("hod_foe_tower", ak.foe_tower), ("hod_foe_foundry", ak.foe_foundry)):
        build(name, fn, tex="hod_foerost")
    build("hod_foe_hullworks", ak.foe_hullworks, tex="hod_foerost", extra=lambda: place_ships(ak.FOE_HULL_FLEET, lambda kind: 1.0))
    build("hod_foe_oldyards", ak.foe_oldyards, tex="hod_foerost",
          extra=lambda: place_ships(ak.FOE_OLD_FLEET, lambda kind: ak.FOE_SEP_SCALE, prefix="pam_"))
    build("hod_foe_yards", ak.foe_yards, tex="hod_foerost",
          extra=lambda: place_ships(ak.FOE_YARD_FLEET, lambda kind: ak.FOE_SEP_SCALE, prefix="pam_"))
    for name, fn in (("hod_crl_coronet", ak.crl_coronet), ("hod_crl_bottoms", ak.crl_bottoms), ("hod_crl_corsec", ak.crl_corsec), ("hod_crl_korvella", ak.crl_korvella), ("hod_crl_den", ak.crl_den)):
        build(name, fn, tex="hod_corellia")
    build("hod_crl_shiprow", ak.crl_shiprow, tex="hod_corellia",
          extra=lambda: place_ships(ak.CRL_ROW_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    build("hod_crl_yards", ak.crl_yards, tex="hod_corellia",
          extra=lambda: place_ships(ak.CRL_YARD_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    for name, fn in (("hod_kua_city", ak.kua_city), ("hod_kua_gardens", ak.kua_gardens), ("hod_kua_estate", ak.kua_estate)):
        build(name, fn, tex="hod_kuat")
    build("hod_kua_works", ak.kua_works, tex="hod_kuat",
          extra=lambda: place_ships(ak.KUA_WORKS_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    build("hod_kua_yards", ak.kua_yards, tex="hod_kuat",
          extra=lambda: place_ships(ak.KUA_YARD_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    for name, fn in (("hod_ren_city", ak.ren_city), ("hod_ren_hq", ak.ren_hq), ("hod_ren_works", ak.ren_works)):
        build(name, fn, tex="hod_rendili")
    build("hod_ren_base", ak.ren_base, tex="hod_rendili",
          extra=lambda: place_ships(ak.REN_BASE_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    build("hod_ren_yards", ak.ren_yards, tex="hod_rendili",
          extra=lambda: place_ships(ak.REN_YARD_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    for name, fn in (("hod_com_chasin", ak.com_chasin), ("hod_com_arena", ak.com_arena), ("hod_com_university", ak.com_university), ("hod_com_munto", ak.com_munto)):
        build(name, fn, tex="hod_commenor")
    build("hod_com_port", ak.com_port, tex="hod_commenor",
          extra=lambda: place_ships(ak.COM_PORT_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    for name, fn in (("hod_dur_ranadaast", ak.dur_ranadaast), ("hod_dur_tayana", ak.dur_tayana), ("hod_dur_tombs", ak.dur_tombs), ("hod_dur_factory", ak.dur_factory), ("hod_dur_newtayana", ak.dur_newtayana), ("hod_dur_lift", ak.dur_lift), ("hod_dur_spacecity", ak.dur_spacecity)):
        build(name, fn, tex="hod_duro")
    for name, fn in (("hod_lor_city", ak.lor_city), ("hod_lor_hq", ak.lor_hq), ("hod_lor_crystal", ak.lor_crystal), ("hod_lor_labs", ak.lor_labs)):
        build(name, fn, tex="hod_loronar")
    build("hod_lor_port", ak.lor_port, tex="hod_loronar",
          extra=lambda: place_ships(ak.LOR_PORT_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    for name, fn in (("hod_nei_kotosi", ak.nei_kotosi), ("hod_nei_docks", ak.nei_docks), ("hod_nei_kaantay", ak.nei_kaantay), ("hod_nei_hives", ak.nei_hives), ("hod_nei_farms", ak.nei_farms)):
        build(name, fn, tex="hod_neimoidia")
    for name, fn in (("hod_mim_village", ak.mim_village), ("hod_mim_temple", ak.mim_temple), ("hod_mim_wells", ak.mim_wells), ("hod_mim_oubliette", ak.mim_oubliette), ("hod_mim_mine", ak.mim_mine)):
        build(name, fn, tex="hod_mimban")
    for name, fn in (("hod_mnn_ahto", ak.mnn_ahto), ("hod_mnn_swoop", ak.mnn_swoop)):
        build(name, fn, tex="hod_manaan")
    build("hod_anx_yards", ak.anx_yards, tex="hod_anaxes",
          extra=lambda: place_ships(ak.ANX_YARD_FLEET, lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0))
    build("hod_dub_capital", ak.dub_capital, tex="hod_dubrillion")
    build("hod_dub_resort", ak.dub_resort, tex="hod_dubrillion")
    one = lambda kind: ak.OT_SHIP_SCALE if kind == "hammerhead" else 1.0          # our ship models, as in the yards
    build("hod_bas_ravelin", ak.bas_ravelin, tex="hod_bastion")
    build("hod_bas_sartinaynian", ak.bas_sartinaynian, tex="hod_bastion", extra=lambda: place_ships(ak.BAS_PORT_FLEET, one))
    build("hod_bas_customs", ak.bas_customs, tex="hod_bastion", extra=lambda: place_ships(ak.BAS_STATION_FLEET, one))
    for name, fn in (("hod_kal_kaleela", ak.kal_kaleela), ("hod_kal_shrupak", ak.kal_shrupak), ("hod_kal_abesmi", ak.kal_abesmi),
                     ("hod_kal_warruzan", ak.kal_warruzan)):
        build(name, fn, tex="hod_kalee")
    for name, fn in (("hod_muun_harnaidan", ak.muun_harnaidan), ("hod_muun_mariunhus", ak.muun_mariunhus),
                     ("hod_muun_pilaan", ak.muun_pilaan)):
        build(name, fn, tex="hod_muunilinst")
    build("hod_muun_highport", ak.muun_highport, tex="hod_muunilinst", extra=lambda: place_ships(ak.MUUN_PORT_FLEET, one))
    for name, fn in (("hod_boz_base", ak.boz_base), ("hod_boz_foundry", ak.boz_foundry), ("hod_boz_ruins", ak.boz_ruins),
                     ("hod_boz_skeletons", ak.boz_skeletons), ("hod_boz_headstones", ak.boz_headstones)):
        build(name, fn, tex="hod_bozpity")
    for fam, fn, tex in (("hod_tar_upper", ak.tar_upper, "hod_taris"), ("hod_tar_lower", ak.tar_lower, "hod_taris"),
                         ("hod_tar_ruin", ak.tar_ruin, "hod_taris"), ("hod_way_town", ak.way_town, "hod_wayland"), ("hod_way_village", ak.way_village, "hod_wayland"),
                         ("hod_con_town", ak.con_town, "hod_concordia"),
                         ("hod_bra_city", ak.bra_city, "hod_bracca"), ("hod_tra_city", ak.tra_city, "hod_trandosha"),
                         ("hod_nyr_town", ak.nyr_town, "hod_nyriaan"), ("hod_crs_town", ak.crs_town, "hod_corsin"),
                         ("hod_kas_city", ak.kas_city, "hod_kashyyyk"), ("hod_ond_town", ak.ond_town, "hod_onderon"),
                         ("hod_umb_city", ak.umb_city, "hod_umbara"), ("hod_col_city", ak.col_city, "hod_colla"),
                         ("hod_rus_city", ak.rus_city, "hod_ruusan"), ("hod_om_town", ak.om_city, "hod_ordmantell"),
                         ("hod_gar_farm", ak.gar_farm, "hod_garqi"), ("hod_gar_city", ak.gar_city, "hod_garqi"),
                         ("hod_aga_town", ak.aga_town, "hod_agamar"), ("hod_ot_town", ak.ot_town, "hod_ordtrasi"),
                         ("hod_dan_estate", ak.dan_estate, "hod_dantooine"), ("hod_dub_city", ak.dub_city, "hod_dubrillion"),
                         ("hod_bas_town", ak.bas_town, "hod_bastion"), ("hod_kal_town", ak.kal_town, "hod_kalee"),
                         ("hod_muun_town", ak.muun_town, "hod_muunilinst"), ("hod_myg_town", ak.myg_town, "hod_mygeeto"),
                         ("hod_yag_town", ak.yag_town, "hod_yaga_minor"), ("hod_ans_town", ak.ans_town, "hod_ansion"), ("hod_dor_town", ak.dor_town, "hod_dorin"),
                         ("hod_yin_town", ak.yin_town, "hod_yinchorr"),
                         ("hod_cha_town", ak.cha_town, "hod_chandrila"),
                         ("hod_cor_town", ak.cor_town, "hod_corulag"), ("hod_ark_town", ak.ark_town, "hod_arkania"),
                         ("hod_anx_town", ak.anx_town, "hod_anaxes"), ("hod_ess_town", ak.ess_town, "hod_esseles"),
                         ("hod_car_town", ak.car_town, "hod_carida"),
                         ("hod_bal_town", ak.bal_town, "hod_balmorra"),
                         ("hod_ald_town", ak.ald_town, "hod_alderaan"),
                         ("hod_fre_town", ak.fre_town, "hod_fresia"),
                         ("hod_foe_town", ak.foe_town, "hod_foerost"),
                         ("hod_crl_town", ak.crl_town, "hod_corellia"),
                         ("hod_kua_town", ak.kua_town, "hod_kuat"),
                         ("hod_ren_town", ak.ren_town, "hod_rendili"),
                         ("hod_com_town", ak.com_town, "hod_commenor"),
                         ("hod_dur_town", ak.dur_town, "hod_duro"),
                         ("hod_lor_town", ak.lor_town, "hod_loronar"),
                         ("hod_nei_town", ak.nei_town, "hod_neimoidia"),
                         ("hod_mim_town", ak.mim_town, "hod_mimban"),
                         ("hod_mnn_town", ak.mnn_town, "hod_manaan"),
                         ("hod_cos_town", ak.cos_town, "hod_coruscant_lm")):
        for band in range(1, 5):
            for v in range(1, 5):
                rng_f = random.Random(f"{fam}{band}{v}")
                build(f"{fam}_{band}{v}", lambda k, band=band, rng=rng_f, fn=fn: fn(k, band, rng), shader="PdxMeshSnow",
                      tex=tex)
    for name, fn in (("hod_jab_choal", ak.jab_choal), ("hod_jab_bore", jab_bore), ("hod_jab_shelter", ak.jab_shelter),
                     ("hod_jab_cobalt", ak.jab_cobalt), ("hod_jab_aurek", ak.jab_aurek), ("hod_jab_shear", ak.jab_shear)):
        build(name, fn, tex="hod_jabiim")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_j = random.Random(f"hod_jab_city{band}{v}")
            build(f"hod_jab_city_{band}{v}", lambda k, band=band, rng=rng_j: ak.jab_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_jabiim")
    for name, fn in (("hod_lia_hq", ak.lia_hq), ("hod_lia_academy", ak.lia_academy), ("hod_lia_skycity", ak.lia_skycity),
                     ("hod_lia_shipyard", lia_shipyard)):
        build(name, fn, tex="hod_lianna")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_l = random.Random(f"hod_lia_city{band}{v}")
            build(f"hod_lia_city_{band}{v}", lambda k, band=band, rng=rng_l: ak.lia_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_lianna")
    for name, fn in (("hod_ieg_cliffhold", ieg_cliffhold), ("hod_ieg_laserweb", ieg_laserweb), ("hod_ieg_choir", ieg_choir),
                     ("hod_ieg_boneyard", ieg_boneyard)):
        build(name, fn, tex="hod_iego")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_i = random.Random(f"hod_ieg_city{band}{v}")
            build(f"hod_ieg_city_{band}{v}", lambda k, band=band, rng=rng_i: ieg_city(k, band, rng), shader="PdxMeshSnow",
                  tex="hod_iego")
    build("hod_mcl_coral_city", ak.mcl_coral_city, tex="hod_moncala", shader="PdxMeshHodUnderwater")   # seen under the sea:
    build("hod_mcl_drome", ak.mcl_drome, tex="hod_moncala", shader="PdxMeshHodUnderwater")             # gfx/FX/pdxmesh.shader
    build("hod_mcl_quarren_hq", ak.qua_hq, tex="hod_moncala", shader="PdxMeshHodUnderwater")
    for band in range(1, 5):
        for v in range(1, 5):
            rng_m = random.Random(f"hod_mcl_city{band}{v}")
            build(f"hod_mcl_city_{band}{v}", lambda k, band=band, rng=rng_m: ak.mcl_city(k, band, rng), shader="PdxMeshHodUnderwater",
                  tex="hod_moncala")
            rng_q = random.Random(f"hod_mcl_qcity{band}{v}")
            build(f"hod_mcl_qcity_{band}{v}", lambda k, band=band, rng=rng_q: ak.qua_city(k, band, rng), shader="PdxMeshHodUnderwater",
                  tex="hod_moncala")
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
        hooked = set(cfg.get("new_models", ())) if cfg.get("hook") else set()   # a hook may place new meshes itself
        if mesh not in {m for m, _s, _w in cfg["items"]} | hooked or not 0 < foot < 30:
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
    <planet>_place)' and replaced on each run. hook(ctx) may add objects with ctx['put'](mesh, scale, r, c, yaw=0.0), yaw in radians."""
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

    def put(mesh, scale, r, c, yaw=0.0):
        objs.setdefault((mesh, scale), []).append((c, H - 1 - r, yaw))
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
    if cfg.get("clear"):                                                   # no city models or trees inside the big landmarks
        import io
        city = Image.open(io.BytesIO(open("map/cities.bmp", "rb").read()))
        terr = Image.open(io.BytesIO(open("map/terrain.bmp", "rb").read()))
        tree = Image.open(io.BytesIO(open("map/trees.bmp", "rb").read()))
        styles, tidx, tr = np.array(city), np.array(terr), np.array(tree)
        ts = tr.shape[1] / zone.shape[1]                                   # trees.bmp px per map px
        tyy, txx = np.mgrid[0:tr.shape[0], 0:tr.shape[1]]
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
                tr[np.hypot(tyy - cy * ts, txx - cx * ts) <= (foot + CITY_MARGIN) * ts] = 0
        for arr, img, path in ((styles, city, "map/cities.bmp"), (tidx, terr, "map/terrain.bmp"), (tr, tree, "map/trees.bmp")):
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
                          f'\t\t}}\n\t\trotation={{\n\t\t\t0.000 {yaw:.3f} 0.000 \n\t\t}}\n\t}}\n' for i, (x, zz, yaw) in enumerate(pts))
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
     "felucia_atlas": felucia_atlas, "korriban_atlas": korriban_atlas, "zygerria_atlas": zygerria_atlas, "dromund_atlas": dromund_atlas, "cantonica_atlas": cantonica_atlas, "bonadan_atlas": bonadan_atlas, "pammant_atlas": pammant_atlas, "moncala_atlas": moncala_atlas, "iego_atlas": iego_atlas, "lianna_atlas": lianna_atlas, "jabiim_atlas": jabiim_atlas, "saleucami_atlas": saleucami_atlas, "telos_atlas": telos_atlas, "serenno_atlas": serenno_atlas, "yavin_atlas": yavin_atlas, "celanon_atlas": celanon_atlas, "botajef_atlas": botajef_atlas, "axxila_atlas": axxila_atlas, "ciutric_atlas": ciutric_atlas, "cestus_atlas": cestus_atlas, "dathomir_atlas": dathomir_atlas, "mandalore_atlas": mandalore_atlas, "taris_atlas": taris_atlas, "wayland_atlas": wayland_atlas,
            "concordia_atlas": concordia_atlas, "bracca_atlas": bracca_atlas,
            "trandosha_atlas": trandosha_atlas, "nyriaan_atlas": nyriaan_atlas,
            "corsin_atlas": corsin_atlas, "kashyyyk_atlas": kashyyyk_atlas, "onderon_atlas": onderon_atlas, "umbara_atlas": umbara_atlas, "colla_atlas": colla_atlas, "ruusan_atlas": ruusan_atlas, "boz_atlas": boz_atlas, "ithor_atlas": ithor_atlas, "ordmantell_atlas": ordmantell_atlas, "garqi_atlas": garqi_atlas, "agamar_atlas": agamar_atlas, "ordtrasi_atlas": ordtrasi_atlas, "dantooine_atlas": dantooine_atlas, "dubrillion_atlas": dubrillion_atlas, "bastion_atlas": bastion_atlas, "kalee_atlas": kalee_atlas, "muunilinst_atlas": muunilinst_atlas, "mygeeto_atlas": mygeeto_atlas, "yagaminor_atlas": yagaminor_atlas, "ansion_atlas": ansion_atlas, "ilum_atlas": ilum_atlas, "dorin_atlas": dorin_atlas, "yinchorr_atlas": yinchorr_atlas, "chandrila_atlas": chandrila_atlas, "corulag_atlas": corulag_atlas,
            "arkania_atlas": arkania_atlas, "anaxes_atlas": anaxes_atlas, "manaan_atlas": manaan_atlas, "mimban_atlas": mimban_atlas, "neimodia_atlas": neimodia_atlas, "loronar_atlas": loronar_atlas, "duro_atlas": duro_atlas, "commenor_atlas": commenor_atlas, "rendilli_atlas": rendilli_atlas, "kuat_atlas": kuat_atlas, "corellia_atlas": corellia_atlas, "foerost_atlas": foerost_atlas, "fresia_atlas": fresia_atlas, "tython_atlas": tython_atlas, "alderaan_atlas": alderaan_atlas, "balmorra_atlas": balmorra_atlas, "carida_atlas": carida_atlas, "esseles_atlas": esseles_atlas, "coruscant_atlas": coruscant_atlas, "etti_atlas": etti_atlas, "ruuria_atlas": ruuria_atlas, "ossus_atlas": ossus_atlas, "lola_atlas": lola_atlas, "ringo_atlas": ringo_atlas, "rhen_atlas": rhen_atlas, "kadavo_atlas": kadavo_atlas, "korriban_place": korriban_place, "florrum_place": florrum_place, "kadavo_place": kadavo_place, "zygerria_place": lambda: place_planet("Zygerria"), "place": place_planet, "models": models,
     "banner_texture": banner_texture, "raxus_alley": raxus_alley}[args[0]](*args[1:])
