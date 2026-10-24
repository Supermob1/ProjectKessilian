"""Alderaan flag + national spirit icons (simple vector art, drawn at 8x then downscaled).

    python "WIPGFX/plans & scripts/alderaan_gfx.py"      run from the mod root
"""
from PIL import Image, ImageDraw

SKY, DEEP, WHITE, GOLD = (126, 178, 232, 255), (34, 70, 128, 255), (245, 247, 250, 255), (222, 180, 70, 255)
K = 8


def crest(d, cx, cy, r, fg, bg):
    """Alderaan's crest: a disc with the three peaks of the Juran mountains"""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fg)
    for dx, h in ((-0.45, 0.55), (0, 0.8), (0.45, 0.55)):
        x = cx + dx * r
        d.polygon([(x - 0.38 * r, cy + 0.45 * r), (x, cy + 0.45 * r - h * r), (x + 0.38 * r, cy + 0.45 * r)], fill=bg)


def flag():
    w, h = 82 * K, 52 * K
    im = Image.new("RGBA", (w, h), SKY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, h * 0.40, w, h * 0.60], fill=WHITE)
    d.rectangle([0, 0, w, h * 0.06], fill=DEEP)
    d.rectangle([0, h * 0.94, w, h], fill=DEEP)
    crest(d, w / 2, h / 2, h * 0.30, DEEP, WHITE)
    for size, path in (((82, 52), "gfx/flags/ALD.tga"), ((41, 26), "gfx/flags/medium/ALD.tga"), ((10, 7), "gfx/flags/small/ALD.tga")):
        im.resize(size, Image.LANCZOS).save(path)


def icon(name, draw):
    s = 65 * K
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([3 * K, 3 * K, s - 3 * K, s - 3 * K], radius=8 * K, fill=DEEP, outline=GOLD, width=2 * K)
    draw(d, s)
    im.resize((65, 65), Image.LANCZOS).save(f"gfx/interface/ideas/{name}.tga")


def pacifism(d, s):     # an olive branch over the crest
    crest(d, s / 2, s / 2, s * 0.30, SKY, DEEP)
    d.arc([s * 0.18, s * 0.18, s * 0.82, s * 0.82], 200, 340, fill=WHITE, width=3 * K)
    for a in range(5):
        x = s * (0.26 + a * 0.12)
        d.ellipse([x - 3 * K, s * 0.22 - 2 * K + abs(a - 2) * 3 * K, x + 3 * K, s * 0.22 + 2 * K + abs(a - 2) * 3 * K], fill=WHITE)


def crown(d, s):        # the royal house
    b = s * 0.68
    d.polygon([(s * 0.2, b), (s * 0.2, s * 0.38), (s * 0.35, s * 0.52), (s * 0.5, s * 0.3), (s * 0.65, s * 0.52),
               (s * 0.8, s * 0.38), (s * 0.8, b)], fill=GOLD)
    d.rectangle([s * 0.2, b, s * 0.8, b + 6 * K], fill=GOLD)
    for x in (0.2, 0.5, 0.8):
        d.ellipse([s * x - 4 * K, s * (0.38 if x != 0.5 else 0.3) - 4 * K - 4 * K, s * x + 4 * K, s * (0.38 if x != 0.5 else 0.3) + 4 * K - 4 * K], fill=WHITE)


def jewel(d, s):        # the cultural jewel of the Core
    d.polygon([(s * 0.5, s * 0.2), (s * 0.78, s * 0.42), (s * 0.5, s * 0.8), (s * 0.22, s * 0.42)], fill=SKY)
    d.polygon([(s * 0.5, s * 0.2), (s * 0.62, s * 0.42), (s * 0.5, s * 0.8), (s * 0.38, s * 0.42)], fill=WHITE)
    d.line([(s * 0.22, s * 0.42), (s * 0.78, s * 0.42)], fill=DEEP, width=2 * K)


if __name__ == "__main__":
    flag()
    icon("ALD_alderaanian_pacifism", pacifism)
    icon("ALD_royal_house_of_organa", crown)
    icon("ALD_cultural_jewel_of_the_core", jewel)
    print("written")
